# SSL warning suppression for requests
import os
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

GROBID_URL = os.getenv("GROBID_API_BASE_URL", "https://cloud.grobid.org")

app = FastAPI()

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

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/grobid/isalive")
async def grobid_isalive():
    resp = requests.get(f"{GROBID_URL}/api/isalive", timeout=5, verify=False)
    if resp.status_code == 200 and "true" in resp.text.lower():
        return {"grobid": "alive"}
    raise HTTPException(status_code=502, detail="GROBID is not responding")

@app.post("/grobid/process")
async def grobid_process(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[1] or ".pdf"
    tmp_path = f"/tmp/{file.filename}"
    with open(tmp_path, "wb") as tmp:
        tmp.write(await file.read())
    try:
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                f"{GROBID_URL}/api/processFulltextDocument",
                files={"input": (file.filename, f, "application/pdf")},
                verify=False
            )
        if resp.status_code == 200:
            return {"tei": resp.text}
        raise HTTPException(status_code=502, detail=f"GROBID process error: {resp.status_code}")
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"GROBID connection error: {e}")
    finally:
        os.remove(tmp_path)

@app.post("/grobid/parse")
async def grobid_parse(file: UploadFile = File(...)):
    try:
        result = await grobid_process(file)
        tei_xml = result.get("tei", "")
        sections = extract_sections_from_tei(tei_xml)
        if not sections:
            # Fallback: return full TEI as a single section
            sections = {"FullText": tei_xml}
        return {"sections": sections}
    except Exception as e:
        import traceback, logging
        logger = logging.getLogger("uvicorn.error")
        logger.error("Error in grobid_parse:", exc_info=True)
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
                        "3) 要約文には適宜改行を入れて、読みやすいレイアウトにしてください。"
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
