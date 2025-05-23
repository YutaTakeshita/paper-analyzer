# backend/main.py
import os
import time
import uuid
import shutil
import subprocess
import logging
from io import BytesIO

import requests
import openai
import boto3
import urllib3
from fastapi import FastAPI, HTTPException, File, UploadFile, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from lxml import etree

# TEI/JSON orchestrator and utilities
from app.tei_utils import extract_jats_sections, extract_jats_references
from app.meta_utils import extract_meta
from app.pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf
from app.tei2json import convert_xml_to_json

# ─── 環境変数・クライアント初期化 ──────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_env = __import__("dotenv").load_dotenv
load_env()

app = FastAPI(title="Paper Analyzer API")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

# AWS Polly
aws_region = os.getenv("AWS_REGION", "ap-northeast-1")
polly = boto3.client("polly", region_name=aws_region)

# GCP clients
from google.cloud import storage, firestore
from googleapiclient.discovery import build

storage_client   = storage.Client()
firestore_client = firestore.Client()
run_client       = build("run", "v2")

# GCP プロジェクト ID を環境変数から取得。未設定なら ADC から自動検出
PROJECT_ID = os.getenv("GCP_PROJECT")
if not PROJECT_ID:
    import google.auth
    _, PROJECT_ID = google.auth.default()

LOCATION   = "asia-northeast1"
JOB_NAME   = "cermine-worker"

# CERMINE 設定
CERMINE_JAR     = os.getenv("CERMINE_JAR_PATH", "/cermine-impl-1.13-jar-with-dependencies.jar")
CERMINE_TIMEOUT = int(os.getenv("CERMINE_TIMEOUT", "300"))

# 外部 CERMINE API（既存クラウド）URL
CERMINE_API_URL = os.getenv("CERMINE_API_URL", "").rstrip("/")

# ─── ヘルスチェック ───────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/isalive")
async def isalive():
    return {"status": "alive"}

@app.get("/api/isalive")
async def api_isalive():
    return Response(content="true", media_type="text/plain")

# ─── 外部 CERMINE API 経由パススルー ─────────────────────────────────
@app.get("/api/cermine/isalive")
async def cermine_api_isalive():
    for attempt in range(3):
        try:
            resp = requests.get(f"{CERMINE_API_URL}/api/isalive", timeout=30)
            resp.raise_for_status()
            if "true" in resp.text.lower():
                return {"cermine": "alive"}
            raise HTTPException(502, "Unexpected CERMINE response")
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
                continue
            logger.error("CERMINE isalive failed", exc_info=True)
            raise HTTPException(502, detail=str(e))

@app.post("/api/cermine/parse")
async def cermine_api_parse(file: UploadFile = File(...)):
    tmp = f"/tmp/{uuid.uuid4().hex}.pdf"
    with open(tmp, "wb") as f:
        f.write(await file.read())
    try:
        with open(tmp, "rb") as f:
            resp = requests.post(
                f"{CERMINE_API_URL}/api/parse",
                files={"file": (file.filename, f, "application/pdf")},
                timeout=120
            )
            resp.raise_for_status()
        return {"tei": resp.text}
    except Exception as e:
        raise HTTPException(502, detail=str(e))
    finally:
        os.remove(tmp)

# ─── CERMINE JAR ローカル実行 ───────────────────────────────────────────
async def run_cermine(file: UploadFile):
    job_id = uuid.uuid4().hex
    workdir = f"/tmp/{job_id}"
    os.makedirs(workdir, exist_ok=True)

    try:
        pdf_path = os.path.join(workdir, file.filename)
        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        cmd = ["java", "-jar", CERMINE_JAR, "-path", workdir, "-outputs", "jats"]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, timeout=CERMINE_TIMEOUT)

        output_file = next(
            (os.path.join(workdir, n) for n in os.listdir(workdir)
             if n.lower().endswith((".xml", ".cermxml", ".nxml"))),
            None
        )
        if not output_file:
            raise HTTPException(500, "No CERMINE output")

        tei_xml = open(output_file, encoding="utf-8").read()
        print("tei_xml:", repr(tei_xml[:500]))
        if not tei_xml.strip():
            raise HTTPException(500, "CERMINE output XML is empty")

        if tei_xml.lstrip().startswith("{"):
            import json
            try:
                return json.loads(tei_xml)
            except Exception as e:
                raise HTTPException(500, f"Invalid JSON output from CERMINE: {str(e)}")
        return tei_xml

    except subprocess.TimeoutExpired:
        raise HTTPException(504, "CERMINE timed out")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")
        logger.error("CERMINE error: %s", err)
        raise HTTPException(500, detail=err)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

@app.post("/cermine/parse")
async def cermine_parse_internal(file: UploadFile = File(...)):
    return await run_cermine(file)

# ─── TEI 解析 + PDF・図表・セクション抽出 ─────────────────────────────────
@app.post("/api/parse")
async def api_parse(file: UploadFile = File(...)):
    print("DEBUG: Using external CERMINE API" if CERMINE_API_URL else "DEBUG: Using local JAR")
    if CERMINE_API_URL:
        resp = await cermine_api_parse(file)
        try:
            json_obj = resp['tei']
            if isinstance(json_obj, str):
                import json
                json_obj = json.loads(json_obj)
        except Exception as e:
            logger.exception("cermine_upload failed")
            raise HTTPException(500, f"parse external CERMINE API JSON failed: {e}")
        return JSONResponse(content=json_obj)

    job_id  = uuid.uuid4().hex
    workdir = f"/tmp/{job_id}"
    os.makedirs(workdir, exist_ok=True)
    try:
        content = await file.read()
        pdf_path = os.path.join(workdir, file.filename)
        with open(pdf_path, 'wb') as f:
            f.write(content)

        if not CERMINE_JAR:
            raise HTTPException(500, detail="CERMINE_JAR_PATH is not set")
        cmd = ["java", "-jar", CERMINE_JAR, "-path", workdir, "-outputs", "jats"]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, timeout=CERMINE_TIMEOUT)

        # Debug: list all files in workdir to see CERMINE outputs
        logger.debug("Workdir contents: %s", os.listdir(workdir))
        # Accept XML, CERMXML, and NXML extensions
        xml_file = next(
            (os.path.join(workdir, fn) for fn in os.listdir(workdir)
             if fn.lower().endswith(('.xml', '.cermxml', '.nxml'))),
            None
        )
        if not xml_file:
            raise HTTPException(500, detail="No CERMINE output XML")

        tei_xml = open(xml_file, encoding='utf-8').read()
        try:
            root = etree.fromstring(tei_xml)
        except Exception as e:
            raise HTTPException(500, detail=f"Invalid XML from CERMINE: {e}")

        meta      = extract_meta(root)
        figures   = extract_figures_from_pdf(pdf_path)
        tables    = extract_tables_from_pdf(pdf_path)
        json_body = convert_xml_to_json(tei_xml, pdf_path)

        result = {
            'meta':       meta,
            'sections':   json_body.get('sections', []),
            'references': json_body.get('references', []),
            'figures':    figures,
            'tables':     tables,
        }
        return JSONResponse(content=result)

    except subprocess.TimeoutExpired:
        raise HTTPException(504, detail="CERMINE timed out")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")
        logger.error("CERMINE error: %s", err)
        raise HTTPException(500, detail=err)
    except HTTPException:
        raise
    except Exception as e:
        # Log full stack trace for debugging
        logger.exception("Unhandled exception in /api/parse")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# ─── 要約 ─────────────────────────────────────────────────────────────
class SummarizeRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = 1500

@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":"あなたは…"}, {"role":"user","content":req.text}],
        max_tokens=req.max_tokens
    )
    return {"summary": resp.choices[0].message.content.strip()}

# ─── TTS ──────────────────────────────────────────────────────────────
@app.post("/tts")
async def tts(body: dict):
    text = body.get("text") or ""
    if not text:
        raise HTTPException(400, "Field 'text' is required")
    audio = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Mizuki")["AudioStream"].read()
    return Response(content=audio, media_type="audio/mpeg")

# ─── GCS アップロード & Cloud Run Job ─────────────────────────────────
@app.post("/api/cermine/upload")
async def cermine_upload(file: UploadFile = File(...)):
    job_id = uuid.uuid4().hex
    if not job_id or job_id.strip() == "" or "/" in job_id:
        raise HTTPException(400, "jobIdが不正です")

    tmp_pdf = f"/tmp/{job_id}.pdf"
    with open(tmp_pdf, "wb") as f:
        f.write(await file.read())

    bucket = storage_client.bucket("cermine_paket")
    blob = bucket.blob(f"{job_id}.pdf")
    blob.upload_from_filename(tmp_pdf)

    firestore_client.collection("jobs").document(job_id).set({
        "status": "pending",
        "pdfPath": f"gs://cermine_paket/{job_id}.pdf"
    })

    job_name = f"projects/{PROJECT_ID}/locations/{LOCATION}/jobs/{JOB_NAME}"

    # arguments を渡す場合、コンテナ側がそれを受け取れることを確認してください
    arguments = [f"gs://cermine_paket/{job_id}.pdf"]

    try:
        run_client.projects().locations().jobs().run(
            name=job_name,
            body={
                "taskOverrides": {
                    "args": arguments
                }
            }
        ).execute()
    except Exception as e:
        logger.error(f"Cloud Run Job起動に失敗: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

    return {"jobId": job_id}

@app.get("/api/cermine/status")
async def cermine_status(jobId: str):
    doc = firestore_client.collection("jobs").document(jobId).get()
    if not doc.exists:
        raise HTTPException(404, "Job not found")
    data = doc.to_dict()
    status = data.get("status", "unknown")
    res = {"status": status}
    if status == "done":
        res["downloadUrl"] = f"https://storage.googleapis.com/cermine_paket/{jobId}.xml"
    return res
