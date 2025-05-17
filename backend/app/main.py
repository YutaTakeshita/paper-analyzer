import os
import time
import requests
import openai
import boto3
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Load environment variables from a .env file for local development
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, File, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from .utils import extract_sections_from_tei
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from google.cloud import storage, firestore
from googleapiclient.discovery import build

CERMINE_API_URL = os.environ["CERMINE_API_URL"]

app = FastAPI()
logger = logging.getLogger("uvicorn.error")
logger.info(f"Using CERMINE_API_URL={CERMINE_API_URL}")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load API keys
openai.api_key = os.getenv("OPENAI_API_KEY")
# Initialize Polly client, defaulting to ap-northeast-1 if AWS_REGION is unset
aws_region = os.getenv("AWS_REGION", "ap-northeast-1")
polly = boto3.client("polly", region_name=aws_region)

# —————————————————————————
# GCP clients for CERMINE workflow
storage_client   = storage.Client()
firestore_client = firestore.Client()
run_client       = build("run", "v2")

# Replace <YOUR_PROJECT_ID> with your GCP project ID or set via env var GCP_PROJECT
PROJECT_ID = os.getenv("GCP_PROJECT", "<YOUR_PROJECT_ID>")
LOCATION   = "asia-northeast1"
JOB_NAME   = "cermine-worker"
# —————————————————————————

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/cermine/isalive")
async def cermine_isalive():
    # Cold start や一時的な遅延に備えてリトライを行う
    for attempt in range(3):
        try:
            # タイムアウトを 30 秒に延長
            resp = requests.get(f"{CERMINE_API_URL}/isalive", timeout=30)
            resp.raise_for_status()
            if "true" in resp.text.lower():
                return {"grobid": "alive"}
            raise HTTPException(status_code=502, detail="Unexpected response from CERMINE at /isalive")
        except requests.exceptions.RequestException as e:
            # 最大 3 回まで、2 秒待って再試行
            if attempt < 2:
                time.sleep(2)
                continue
            # すべて失敗したら 502 を返却
            logger.error(f"Error in /cermine/isalive after retries: {e}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail=f"CERMINE service unavailable: {e}"
            )

@app.post("/cermine/process")
async def cermine_process(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1] or ".pdf"
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as tmp:
        tmp.write(await file.read())
    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{CERMINE_API_URL}/processFulltextDocument",
                files={"input": (file.filename, f, "application/pdf")},
                timeout=120
            )
            try:
                resp.raise_for_status()
            except requests.HTTPError as e:
                # Return a clear error if the PDF conversion failed
                detail_msg = resp.text or str(e)
                raise HTTPException(status_code=502, detail=f"CERMINE process error: {detail_msg}")
        if resp.status_code == 200:
            return {"tei": resp.text}
        logger.error(f"CERMINE returned status {resp.status_code}: {resp.text}")
        raise HTTPException(status_code=502, detail=f"CERMINE process error: {resp.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"CERMINE connection error: {e}")
    finally:
        os.remove(tmp_path)

@app.post("/cermine/parse")
async def cermine_parse(file: UploadFile = File(...)):
    try:
        result = await cermine_process(file)
        tei_xml = result.get("tei", "")
        sections = extract_sections_from_tei(tei_xml)
        if not sections:
            # Fallback: return full TEI as a single section
            sections = {"FullText": tei_xml}
        return {"sections": sections}
    except Exception as e:
        logger.error("Error in cermine_parse:", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

class SummarizeRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = 1500

@app.post("/summarize")
async def summarize(request: SummarizeRequest):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "\n".join([
                        "あなたは医療・保健学分野に精通した研究者です。",
                        "渡された論文の各セクションを、",
                        "1) 医療保健分野の読者に最適化した自然な日本語で、",
                        "2) 研究の方法・手法については、",
                        "   - その方法や手法、統計処理が何を目的としたものか、",
                        "   - どのように実施されるのか簡潔に補足し、",
                        "   - 当該分野における背景や意義も踏まえて解説し、",
                        "3) 要約文には適宜改行を入れて、読みやすいレイアウトにしてください。",
                        "4) 原文のレファレンスの番号は要約にも反映させてください。",
                    ])
                },
                {"role": "user", "content": request.text},
            ],
            max_tokens=request.max_tokens
        )
        summary = response.choices[0].message.content.strip()
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI API error: {e}")

@app.post("/tts")
async def tts(request: dict):
    text = request.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Field 'text' is required")
    try:
        resp = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId="Mizuki",
            Engine="standard"
        )
        audio_stream = resp["AudioStream"].read()
        return Response(content=audio_stream, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Polly error: {e}")

@app.post("/cermine/upload")
async def cermine_upload(file: UploadFile = File(...)):
    """
    Upload PDF → GCS → Firestore(pending) → Cloud Run Job
    """
    job_id  = uuid.uuid4().hex
    tmp_pdf = f"/tmp/{job_id}.pdf"
    with open(tmp_pdf, "wb") as f:
        f.write(await file.read())

    # 1) Upload to GCS
    bucket = storage_client.bucket("cermine_paket")
    blob   = bucket.blob(f"{job_id}.pdf")
    blob.upload_from_filename(tmp_pdf)

    # 2) Register pending job in Firestore
    firestore_client.collection("jobs").document(job_id).set({
        "status": "pending",
        "pdfPath": f"gs://cermine_paket/{job_id}.pdf"
    })

    # 3) Invoke Cloud Run Job
    parent = f"projects/{PROJECT_ID}/locations/{LOCATION}/jobs/{JOB_NAME}"
    run_client.projects().locations().jobs().executions().create(
        parent=parent,
        body={"execution": {"arguments": [f"gs://cermine_paket/{job_id}.pdf"]}}
    ).execute()

    return {"jobId": job_id}

@app.get("/cermine/status")
async def cermine_status(jobId: str):
    """
    Return job status from Firestore.
    If done, include downloadUrl for the resulting XML.
    """
    doc = firestore_client.collection("jobs").document(jobId).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Job not found")
    data   = doc.to_dict()
    status = data.get("status", "unknown")
    result = {"status": status}
    if status == "done":
        result["downloadUrl"] = f"https://storage.googleapis.com/cermine_paket/{jobId}.xml"
    return result