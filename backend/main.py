# backend/main.py
import os
import uuid
import shutil
import logging
import tempfile

import requests
import openai # OpenAIライブラリ
import boto3
import urllib3
from fastapi import FastAPI, HTTPException, File, UploadFile, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from google.cloud import secretmanager

from app.tei_utils import (
    extract_sections_from_tei, 
    extract_references_from_tei
)
from app.meta_utils import extract_meta_from_tei
from app.pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf
from app.tei2json import convert_xml_to_json

# ─── 環境変数・クライアント初期化 ──────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_env = __import__("dotenv").load_dotenv
load_env()

app = FastAPI(title="Paper Analyzer API with GROBID")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GCPプロジェクトIDとSecret Managerから認証情報を取得する関数 ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT", "grobid-461112") # ご自身のプロジェクトIDに

def get_secret(secret_id, project_id=GCP_PROJECT_ID, version_id="latest"):
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to access secret {secret_id} in project {project_id}: {e}")
        return None

# --- OpenAI APIキーの設定 (Secret Managerから取得) ---
OPENAI_API_KEY_FROM_SM = get_secret("openai-api-key") # Secret Managerでのシークレット名
if OPENAI_API_KEY_FROM_SM:
    openai.api_key = OPENAI_API_KEY_FROM_SM
    logger.info("OpenAI API key configured successfully from Secret Manager.")
else:
    openai.api_key = os.getenv("OPENAI_API_KEY") # フォールバックとして環境変数を試みる
    if openai.api_key:
        logger.warning("OpenAI API key configured from environment variable as fallback.")
    else:
        logger.error("OpenAI API key could not be configured from Secret Manager or environment variable.")
# OPENAI_SUMMARY_MODEL は環境変数から取得のままでも良いか、固定値にする
OPENAI_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1-mini")


# --- AWS Polly クライアントの初期化 (Secret Manager対応) ---
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
AWS_POLLY_VOICE_ID = os.getenv("AWS_POLLY_VOICE_ID", "Tomoko")
AWS_POLLY_OUTPUT_FORMAT = os.getenv("AWS_POLLY_OUTPUT_FORMAT", "mp3")
AWS_POLLY_ENGINE = os.getenv("AWS_POLLY_ENGINE", "neural")
polly = None 

try:
    aws_access_key_id_val = get_secret("aws-access-key-id")
    aws_secret_access_key_val = get_secret("aws-secret-access-key")

    if aws_access_key_id_val and aws_secret_access_key_val:
        polly = boto3.client(
            "polly",
            region_name=AWS_REGION,
            aws_access_key_id=aws_access_key_id_val,
            aws_secret_access_key=aws_secret_access_key_val
        )
        logger.info("AWS Polly client initialized successfully using credentials from Secret Manager.")
    else:
        logger.warning("Could not retrieve one or both AWS credentials from Secret Manager. Polly client not initialized.")
except Exception as e:
    logger.error(f"Error during Polly client initialization with Secret Manager: {e}", exc_info=True)

# ★ GROBID Service URL
GROBID_SERVICE_URL = "https://grobid-service-974272343256.asia-northeast1.run.app/api/processFulltextDocument"



# ─── ヘルスチェック (変更なし) ───────────────────────────────────
@app.get("/health")
async def health():
    # 元のシンプルなステータス応答に戻す
    return {"status": "ok"}

@app.get("/isalive")
async def isalive():
    return {"status": "alive"}

@app.get("/api/isalive")
async def api_isalive():
    return Response(content="true", media_type="text/plain")

# ─── 新しいPDF処理エンドポイント (GROBID利用) ─────────────────────
@app.post("/api/parse")
async def api_parse_with_grobid(file: UploadFile = File(...)):
    logger.info(f"Received file for GROBID processing: {file.filename}")
    
    temp_pdf_path = None
    temp_dir = None 

    try:
        temp_dir = tempfile.mkdtemp() 
        safe_filename = os.path.basename(file.filename if file.filename else "uploaded.pdf")
        temp_pdf_path = os.path.join(temp_dir, safe_filename)
        
        with open(temp_pdf_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
        logger.info(f"Uploaded PDF saved temporarily to: {temp_pdf_path}")

        with open(temp_pdf_path, 'rb') as f_pdf:
            files_for_grobid = {'input': (safe_filename, f_pdf, file.content_type)}
            logger.info(f"Sending PDF to GROBID service: {GROBID_SERVICE_URL}")
            
            grobid_response = requests.post(GROBID_SERVICE_URL, files=files_for_grobid, timeout=300) 
            grobid_response.raise_for_status()
            
            tei_xml_string = grobid_response.text
            logger.info("Successfully received TEI XML from GROBID service.")

        json_output = convert_xml_to_json(tei_xml_string, pdf_path=temp_pdf_path)
        logger.info("TEI XML successfully converted to final JSON structure.")

        # アブストラクトがあれば、その要約も取得する
        if json_output.get('meta') and json_output['meta'].get('abstract'):
            abstract_text = json_output['meta']['abstract']
            try:
                # SummarizeRequest と summarize 関数を再利用する形で要約を取得
                # (この部分は summarize 関数を直接呼び出すか、ロジックをここに展開する必要がある)
                # 以下は summarize 関数のロジックを展開する例
                system_prompt_for_abstract = """あなたは医療保健分野の学術論文を専門とする高度なAIアシスタントです。提供された学術論文のアブストラクト（抄録）を読み、その内容を起承転結をつけて日本語の自然な文章としてまとめてください。また、当該分野での現在の潮流や背景文脈を考慮し、必要であればそれを簡潔に補足情報として含めてください。"""
                user_prompt_for_abstract = f"""以下のアブストラクトを上記の指示に従って要約してください。\n\n---アブストラクトここから---\n{abstract_text}\n---アブストラクトここまで---\n\n要約（日本語）:"""
                
                if openai.api_key: # APIキーが設定されているか確認
                    logger.info(f"Requesting summary for abstract from OpenAI. Model: {OPENAI_SUMMARY_MODEL}")
                    resp_abstract_summary = openai.chat.completions.create(
                        model=OPENAI_SUMMARY_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt_for_abstract},
                            {"role": "user", "content": user_prompt_for_abstract}
                        ],
                        max_tokens=1000, 
                        temperature=0.3,
                    )
                    abstract_summary_text = resp_abstract_summary.choices[0].message.content.strip()
                    json_output['meta']['abstract_summary'] = abstract_summary_text
                    logger.info("Abstract summary received from OpenAI successfully.")
                else:
                    logger.warning("OpenAI API key not configured, skipping abstract summary.")
                    json_output['meta']['abstract_summary'] = "OpenAI APIキーが設定されていないため、アブストラクトの自動要約は利用できません。"

            except Exception as e_summary:
                logger.error(f"Error summarizing abstract: {e_summary}", exc_info=True)
                json_output['meta']['abstract_summary'] = "アブストラクトの自動要約中にエラーが発生しました。"
        
        return JSONResponse(content=json_output)

    except requests.exceptions.Timeout as e:
        logger.error(f"Request to GROBID service timed out: {e}", exc_info=True)
        raise HTTPException(status_code=504, detail=f"GROBID service request timed out: {str(e)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling GROBID service: {e}", exc_info=True)
        status_code = e.response.status_code if e.response is not None else 502
        error_detail = str(e)
        if e.response is not None and e.response.text:
            error_detail = f"GROBID service error ({status_code}): {e.response.text[:500]}"
        raise HTTPException(status_code=status_code, detail=error_detail)
    except ValueError as e: 
        logger.error(f"Error processing TEI XML or PDF data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
    except HTTPException as e: 
        raise e
    except Exception as e:
        logger.error(f"An unexpected error occurred in /api/parse: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            logger.info(f"Temporary PDF deleted: {temp_pdf_path}")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Temporary directory deleted: {temp_dir}")
        if file: 
            await file.close()

# ─── 要約 ───────────────────────────────────────────────────
class SummarizeRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = 10000

@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    if not openai.api_key: # OpenAI APIキーが設定されていなければエラー
        logger.error("OpenAI API key is not configured. Cannot perform summarization.")
        raise HTTPException(status_code=503, detail="Summarization service is currently unavailable due to configuration issues.")

    system_prompt = """あなたは、医療および保健分野の学術論文を専門とする高度なAIアシスタントです。
提供された論文のセクション（原文）を読み解き、以下の指示に従って日本語で要約を生成してください。

指示:
1. 原文の内容を正確に捉え、主要なポイントを抽出し、文体は文語調にしてください。
2. 関連する現在の医学的・科学的な潮流や背景文脈を考慮し、必要であればそれを簡潔に補足情報として含めてください。ただし、原文にない情報を過度に推測したり、付け加えたりしないでください。
3. もし原文中に引用や参考文献への言及（例: [1], (Smith et al., 2020) など）があれば、それらを省略せず、要約文中の対応する箇所に適切に含めてください。
4. **重要: 生成される要約文は、`<p>`, `<br>`, `<em>`, `<strong>` を含む一切のHTMLタグを含まず、純粋なプレーンテキストとしてください。段落は、段落間に1つの空行を挿入することで表現してください。箇条書きが適切な場合は、各項目の先頭に「・」や「1. 」のような記号を使用し、HTMLのリストタグ (`<ul>`, `<ol>`, `<li>`) は使用しないでください。**
5. 専門用語は保持しつつも、可能な範囲で平易な表現を心がけてください。
6. もし原文中に統計解析手法（例: t検定, ANOVA, カイ二乗検定, ロジスティック回帰分析など）に関する記述があれば、その手法がどのような目的で使われるものか、ごく簡潔な補足説明（例：t検定は2群間の平均値の差を比較する手法）を括弧書きなどで加えてください。ただし、補足は10～30字程度に留め、冗長にならないようにしてください。
7. 要約は、客観的かつ中立的な視点を保ってください。"""

    user_prompt = f"""以下の論文セクションを上記の指示に従って要約してください。

---原文ここから---
{req.text}
---原文ここまで---

要約（日本語）:"""
    try:
        model_to_use = OPENAI_SUMMARY_MODEL
        logger.info(f"Requesting summary from OpenAI. Model: {model_to_use}. Max tokens: {req.max_tokens}")
        resp = openai.chat.completions.create(
            model=model_to_use,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=req.max_tokens, 
            temperature=0.2,
        )
        summary_text = resp.choices[0].message.content.strip()
        logger.info("Summary received from OpenAI successfully.")
        return {"summary": summary_text}
    except openai.APIError as e:
        logger.error(f"OpenAI API returned an API Error: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"OpenAI API Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred while calling OpenAI API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during summarization: {e}")

# ─── TTS ──────────────────────────────────────────────────────────────
@app.post("/tts")
async def tts(body: dict):
    global polly 
    if not polly: 
        logger.error("AWS Polly client is not initialized. Cannot perform TTS.")
        raise HTTPException(status_code=503, detail="TTS service is currently unavailable due to configuration issues.")

    text = body.get("text") or ""
    if not text:
        logger.warn("TTS request received with no text.")
        raise HTTPException(status_code=400, detail="Field 'text' is required")
    
    try:
        logger.info(f"Requesting TTS from AWS Polly. VoiceId: {AWS_POLLY_VOICE_ID}, Engine: {AWS_POLLY_ENGINE}, Format: {AWS_POLLY_OUTPUT_FORMAT}")
        
        request_params = {
            'Text': text,
            'OutputFormat': AWS_POLLY_OUTPUT_FORMAT,
            'VoiceId': AWS_POLLY_VOICE_ID,
            'Engine': AWS_POLLY_ENGINE
        }
        audio_response = polly.synthesize_speech(**request_params)
        
        logger.info("TTS audio received from AWS Polly successfully.")
        return Response(content=audio_response["AudioStream"].read(), media_type="audio/mpeg")
    
    except Exception as e: 
        logger.error(f"AWS Polly TTS error: {str(e)}", exc_info=True)
        error_detail = f"TTS generation failed: {type(e).__name__}"
        if hasattr(e, 'response') and 'Error' in e.response: 
            error_detail += f" - Code: {e.response['Error']['Code']}, Message: {e.response['Error']['Message']}"
        else:
            error_detail += f" - {str(e)}"
        raise HTTPException(status_code=500, detail=error_detail)