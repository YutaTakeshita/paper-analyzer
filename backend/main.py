# backend/main.py
import os
import uuid
import shutil
import logging
import tempfile
import io
# import requests
import httpx
import openai
import boto3
import urllib3
from fastapi import FastAPI, HTTPException, File, UploadFile, Response, status, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from google.cloud import secretmanager
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from contextlib import closing
from datetime import datetime

from fastapi.concurrency import run_in_threadpool
import time

# ユーティリティ関数
from app.tei_utils import extract_sections_from_tei, extract_references_from_tei
from app.meta_utils import extract_meta_from_tei
from app.pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf
from app.tei2json import convert_xml_to_json
# Notion連携用モジュール
from app.notion_utils import create_notion_page
from app.notion_utils import notion_client_instance as notion_utils_client
from app.notion_utils import NOTION_DATABASE_ID as NOTION_DB_ID_FROM_UTILS

# ★★★ Google Drive連携用ユーティリティとテキストユーティリティのインポート (修正) ★★★
from app.gdrive_utils import get_gdrive_service_from_json_key, upload_file_to_drive
from app.text_utils import sanitize_filename
# ★★★ ここまで ★★★


# ─── 環境変数・クライアント初期化 ──────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_env = __import__("dotenv").load_dotenv
load_env() # .env ファイルを読み込む

app = FastAPI(title="Paper Analyzer API with GROBID and Async Processing")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GCP_PROJECT_ID = os.getenv("GCP_PROJECT", "grobid-461112")

def get_secret(secret_id, project_id=GCP_PROJECT_ID, version_id="latest"):
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        logger.error(f"Failed to access secret {secret_id} in project {project_id}: {e}")
        return None

# --- OpenAI クライアント初期化 ---
OPENAI_API_KEY_SECRET_NAME = os.getenv("OPENAI_API_KEY_SECRET_NAME", "openai-api-key")
OPENAI_API_KEY = get_secret(OPENAI_API_KEY_SECRET_NAME)
if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # フォールバック
    if OPENAI_API_KEY: logger.warning("OpenAI API key configured from environment variable as fallback.")
    else: logger.error("OpenAI API key could not be configured.")
sync_openai_client = None
openai_aclient = None
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    sync_openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    openai_aclient = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI clients (sync & async) configured.")
else:
    logger.error("OpenAI API key not available, clients not initialized.")
OPENAI_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1-mini") # モデル名を修正

# --- AWS Polly クライアント初期化 ---
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
AWS_POLLY_VOICE_ID_JA = os.getenv("AWS_POLLY_VOICE_ID_JA", "Tomoko")
AWS_POLLY_OUTPUT_FORMAT = os.getenv("AWS_POLLY_OUTPUT_FORMAT", "mp3")
AWS_POLLY_ENGINE = os.getenv("AWS_POLLY_ENGINE", "neural")
polly = None
AWS_ACCESS_KEY_ID_SECRET_NAME = os.getenv("AWS_ACCESS_KEY_ID_SECRET_NAME", "aws-access-key-id")
AWS_SECRET_ACCESS_KEY_SECRET_NAME = os.getenv("AWS_SECRET_ACCESS_KEY_SECRET_NAME", "aws-secret-access-key")
aws_access_key_id_val = get_secret(AWS_ACCESS_KEY_ID_SECRET_NAME)
aws_secret_access_key_val = get_secret(AWS_SECRET_ACCESS_KEY_SECRET_NAME)
if not aws_access_key_id_val: aws_access_key_id_val = os.getenv("AWS_ACCESS_KEY_ID")
if not aws_secret_access_key_val: aws_secret_access_key_val = os.getenv("AWS_SECRET_ACCESS_KEY")
if aws_access_key_id_val and aws_secret_access_key_val:
    try:
        polly = boto3.client(
            "polly", region_name=AWS_REGION,
            aws_access_key_id=aws_access_key_id_val,
            aws_secret_access_key=aws_secret_access_key_val
        )
        logger.info("AWS Polly client initialized.")
    except Exception as e:
        logger.error(f"Error during Polly client initialization: {e}", exc_info=True)
else:
    logger.warning("AWS credentials for Polly not found. Polly client not initialized.")

# --- GROBID 設定 ---
GROBID_SERVICE_URL = os.getenv("GROBID_SERVICE_URL", "http://localhost:8070/api/processFulltextDocument")


# ★★★ Google Drive クライアント初期化 (Secret Manager経由) ★★★
GDRIVE_SA_KEY_JSON_SECRET_NAME = os.getenv("GDRIVE_SA_KEY_JSON_SECRET_NAME", "gdrive-sa-key-json")
GDRIVE_FOLDER_ID_SECRET_NAME = os.getenv("GDRIVE_FOLDER_ID_SECRET_NAME", "gdrive-folder-id")

gdrive_sa_key_json_content_str = None
GDRIVE_FOLDER_ID_FROM_SECRET = None # Secret Managerから取得したフォルダIDを格納
gdrive_service = None # 初期化されたGoogle Driveサービスオブジェクトを保持

try:
    gdrive_sa_key_json_content_str = get_secret(GDRIVE_SA_KEY_JSON_SECRET_NAME)
    GDRIVE_FOLDER_ID_FROM_SECRET = get_secret(GDRIVE_FOLDER_ID_SECRET_NAME)

    if gdrive_sa_key_json_content_str:
        # gdrive_utils.py の関数を使ってサービスオブジェクトを初期化
        gdrive_service = get_gdrive_service_from_json_key(gdrive_sa_key_json_content_str)
        if gdrive_service:
            logger.info("Google Drive service initialized successfully via Secret Manager.")
        else:
            logger.error("Failed to initialize Google Drive service using key from Secret Manager.")
    else:
        logger.error(f"Service account key JSON for Google Drive not found in Secret Manager (secret name: {GDRIVE_SA_KEY_JSON_SECRET_NAME}).")
    
    if not GDRIVE_FOLDER_ID_FROM_SECRET:
        logger.error(f"Google Drive Folder ID not found in Secret Manager (secret name: {GDRIVE_FOLDER_ID_SECRET_NAME}). Google Drive uploads might fail or use a default if applicable elsewhere.")

except Exception as e:
    logger.error(f"Error during Google Drive secrets fetching or service initialization: {e}", exc_info=True)
# ★★★ ここまで ★★★


# --- 非同期処理のためのインメモリジョブストア ---
processing_jobs: Dict[str, Dict[str, Any]] = {}

# ─── ヘルスチェック ───────────────────────────────────
@app.get("/health")
async def health(): return {"status": "ok"}
@app.get("/isalive")
async def isalive(): return {"status": "alive"}
@app.get("/api/isalive")
async def api_isalive(): return Response(content="true", media_type="text/plain")


# ─── バックグラウンド処理関数 (変更箇所) ─────────────────────────────
async def process_pdf_in_background(
    job_id: str,
    temp_pdf_path: str,
    original_filename: str,
    content_type: Optional[str],
    temp_dir_to_clean: str
):
    logger.info(f"[Job {job_id}] Background processing started for: {original_filename}")
    processing_jobs[job_id].update({"status": "processing", "timestamp": datetime.utcnow().isoformat()})
    json_output = {}
    google_drive_url = None
    # ★★★ グローバルに初期化された gdrive_service と GDRIVE_FOLDER_ID_FROM_SECRET を参照 ★★★
    global gdrive_service, GDRIVE_FOLDER_ID_FROM_SECRET

    try:
        tei_xml_string = None
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(temp_pdf_path, 'rb') as f_pdf:
                files_for_grobid = {'input': (original_filename, f_pdf, content_type)}
                logger.info(f"[Job {job_id}] Sending PDF to GROBID: {GROBID_SERVICE_URL}")
                try:
                    start_time_grobid = time.time()
                    grobid_response = await client.post(GROBID_SERVICE_URL, files=files_for_grobid)
                    grobid_response.raise_for_status()
                    tei_xml_string = grobid_response.text
                    end_time_grobid = time.time()
                    logger.info(f"[Job {job_id}] Received TEI XML from GROBID. Took {end_time_grobid - start_time_grobid:.2f} seconds.")
                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text[:500] if e.response else str(e)
                    raise Exception(f"GROBID service error ({e.response.status_code if e.response else 'N/A'}): {error_detail}")
                except httpx.RequestError as e:
                    raise Exception(f"GROBID request error: {str(e)}")

        if not tei_xml_string:
            raise Exception("No TEI XML received from GROBID.")

        logger.info(f"[Job {job_id}] Converting TEI XML to JSON for {original_filename} (synchronous)...")
        start_time_conversion = time.time()
        json_output = convert_xml_to_json(
            tei_xml_string,
            pdf_path=temp_pdf_path
        )
        end_time_conversion = time.time()
        logger.info(f"[Job {job_id}] TEI XML to JSON conversion for {original_filename} took {end_time_conversion - start_time_conversion:.2f} seconds.")

        # ★★★ Google Driveへのアップロード処理 (修正) ★★★
        extracted_title = json_output.get('meta', {}).get('title', None)
        fallback_drive_filename_base = os.path.splitext(original_filename)[0] if original_filename else "untitled_document"
        drive_filename = sanitize_filename(extracted_title, fallback_name=fallback_drive_filename_base)
        logger.info(f"[Job {job_id}] Generated Google Drive filename: {drive_filename}")

        if gdrive_service and GDRIVE_FOLDER_ID_FROM_SECRET: # ★★★ 初期化済みサービスとフォルダIDをチェック ★★★
            logger.info(f"[Job {job_id}] Uploading to Google Drive: {temp_pdf_path} as {drive_filename}")
            start_time_gdrive = time.time()
            # ★★★ gdrive_utils.upload_file_to_drive を呼び出し ★★★
            uploaded_file_info = await run_in_threadpool(
                upload_file_to_drive,
                service=gdrive_service, # 初期化済みサービスオブジェクト
                local_file_path=temp_pdf_path,
                filename_on_drive=drive_filename,
                folder_id=GDRIVE_FOLDER_ID_FROM_SECRET, # Secret Managerから取得したフォルダID
                make_public=True
            )
            end_time_gdrive = time.time()
            if uploaded_file_info and uploaded_file_info.get('webViewLink'):
                google_drive_url = uploaded_file_info.get('webViewLink')
                json_output['google_drive_url'] = google_drive_url
                logger.info(f"[Job {job_id}] Successfully uploaded to Google Drive. URL: {google_drive_url}. Took {end_time_gdrive - start_time_gdrive:.2f} seconds.")
            else:
                logger.error(f"[Job {job_id}] Failed to upload to Google Drive or get URL. Took {end_time_gdrive - start_time_gdrive:.2f} seconds.")
                json_output['google_drive_url'] = None
        else:
            if not gdrive_service:
                logger.error(f"[Job {job_id}] Google Drive service is not initialized. Skipping upload.")
            if not GDRIVE_FOLDER_ID_FROM_SECRET:
                logger.error(f"[Job {job_id}] Google Drive Folder ID is not configured (from Secret Manager). Skipping upload.")
            json_output['google_drive_url'] = None
        # ★★★ ここまでGoogle Drive処理 ★★★

        if json_output.get('meta') and json_output['meta'].get('abstract') and openai_aclient:
            abstract_text = json_output['meta']['abstract']
            try:
                # ... (OpenAI要約処理 - モデル名が修正されていることを確認) ...
                logger.info(f"[Job {job_id}] Requesting long abstract summary from OpenAI with model: {OPENAI_SUMMARY_MODEL}...")
                response = await openai_aclient.chat.completions.create(
                    model=OPENAI_SUMMARY_MODEL, # ★★★ モデル名を確認 ★★★
                    # ...
                )
                json_output['meta']['abstract_summary'] = response.choices[0].message.content.strip()
                # ...
            except Exception as e_summary:
                logger.error(f"[Job {job_id}] Error summarizing abstract (long): {e_summary}", exc_info=True)
                json_output['meta']['abstract_summary'] = "アブストラクトの自動要約中にエラーが発生しました。"
        elif not openai_aclient and json_output.get('meta'):
             json_output['meta']['abstract_summary'] = "OpenAIクライアント未設定のため、自動要約は利用できません。"

        processing_jobs[job_id].update({"status": "completed", "result": json_output, "timestamp": datetime.utcnow().isoformat()})
        logger.info(f"[Job {job_id}] Background processing completed for {original_filename}.")

    except Exception as e:
        logger.error(f"[Job {job_id}] Error during background processing: {e}", exc_info=True)
        processing_jobs[job_id].update({"status": "failed", "error": str(e), "timestamp": datetime.utcnow().isoformat()})
    finally:
        # --- ここからが finally ブロック ---
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
                logger.info(f"[Job {job_id}] Temporary PDF file deleted: {temp_pdf_path}")
            except Exception as e_clean_file:
                logger.error(f"[Job {job_id}] Error cleaning up temp PDF file: {e_clean_file}")
        if temp_dir_to_clean and os.path.exists(temp_dir_to_clean):
            try:
                shutil.rmtree(temp_dir_to_clean)
                logger.info(f"[Job {job_id}] Temporary directory deleted: {temp_dir_to_clean}")
            except Exception as e_clean_dir:
                logger.error(f"[Job {job_id}] Error cleaning up temp directory: {e_clean_dir}")
        # --- ここまでが finally ブロック ---

# ─── ★ 非同期PDF処理受付エンドポイント ─────────────────────────
@app.post("/api/parse_async", status_code=status.HTTP_202_ACCEPTED)
async def api_parse_async_endpoint(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    job_id = str(uuid.uuid4())
    temp_pdf_path = None
    temp_dir_for_job = None

    try:
        temp_dir_for_job = tempfile.mkdtemp(prefix=f"paperanalyzer_job_{job_id}_")
        # ★★★ ファイル名を安全にする処理を追加 ★★★
        # file.filename が None の場合や、悪意のあるパスを含む可能性を考慮
        if file.filename:
            base_filename = os.path.basename(file.filename)
            # さらにサニタイズが必要ならここで行うが、ひとまず basename でディレクトリトラバーサルは防ぐ
            safe_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in base_filename)
            if not safe_filename: # サニタイズの結果空になったらデフォルト名
                safe_filename = "uploaded.pdf"
        else:
            safe_filename = "uploaded.pdf"
        temp_pdf_path = os.path.join(temp_dir_for_job, safe_filename)
        # ★★★ ここまで ★★★


        with open(temp_pdf_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
        logger.info(f"Uploaded PDF for Job ID {job_id} saved to: {temp_pdf_path}")

        processing_jobs[job_id] = {"status": "queued", "filename": file.filename, "timestamp": datetime.utcnow().isoformat()}
        
        background_tasks.add_task(
            process_pdf_in_background,
            job_id,
            temp_pdf_path,
            file.filename, # ★★★ ここは元のファイル名で良い ★★★
            file.content_type,
            temp_dir_for_job
        )
        
        logger.info(f"Job {job_id} for file {file.filename} queued for background processing.")
        return {"message": "PDF processing started in background.", "job_id": job_id}

    except Exception as e:
        logger.error(f"Error initiating async parse for {file.filename if file else 'unknown_file'}: {e}", exc_info=True) # ★★★ fileがNoneの場合も考慮 ★★★
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
        if temp_dir_for_job and os.path.exists(temp_dir_for_job): shutil.rmtree(temp_dir_for_job)
        raise HTTPException(status_code=500, detail=f"Failed to start PDF processing: {str(e)}")
    finally:
        if file:
            await file.close()

# ─── ★ 処理状況確認エンドポイント ─────────────────────────
@app.get("/api/parse_status/{job_id}")
async def get_parse_status_endpoint(job_id: str):
    job = processing_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job ID not found.")
    
    logger.debug(f"Status check for Job ID {job_id}: Current status is {job['status']}")
    return job


# ─── セクション要約 (/summarize) ──────────────────────────────────
class SummarizeRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = 10000

@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    if not sync_openai_client:
        logger.error("OpenAI sync client not initialized. Cannot perform summarization.")
        raise HTTPException(status_code=503, detail="Summarization service is currently unavailable.")
    system_prompt_section = """あなたは、医療および保健分野の学術論文を専門とする高度なAIアシスタントです。提供された論文のセクション（原文）を読み解き、以下の指示に従って日本語で要約を生成してください。指示: 1. 原文の内容を正確に捉え、主要なポイントを抽出してください。2. 関連する現在の医学的・科学的な潮流や背景文脈を考慮し、必要であればそれを簡潔に補足情報として含めてください。ただし、原文にない情報を過度に推測したり、付け加えたりしないでください。3. もし原文中に引用や参考文献への言及（例: [1], (Smith et al., 2020) など）があれば、それらを省略せず、要約文中の対応する箇所に適切に含めてください。4. **重要: 生成される要約文は、`<p>`, `<br>`, `<em>`, `<strong>` を含む一切のHTMLタグを含まず、純粋なプレーンテキストとしてください。段落は、段落間に1つの空行を挿入することで表現してください。箇条書きが適切な場合は、各項目の先頭に「・」や「1. 」のような記号を使用し、HTMLのリストタグ (`<ul>`, `<ol>`, `<li>`) は使用しないでください。** 5. 専門用語は保持しつつも、可能な範囲で平易な表現を心がけてください。6. もし原文中に統計解析手法（例: t検定, ANOVA, カイ二乗検定, ロジスティック回帰分析など）に関する記述があれば、その手法がどのような目的で使われるものか、ごく簡潔な補足説明（例：t検定は2群間の平均値の差を比較する手法）を括弧書きなどで加えてください。ただし、補足は10～30字程度に留め、冗長にならないようにしてください。7. 要約は、客観的かつ中立的な視点を保ってください。"""
    user_prompt_section = f"""以下の論文セクションを上記の指示に従って、HTMLタグを一切含まず、段落間は空行で区切るプレーンテキスト形式で要約してください。\n\n---原文ここから---\n{req.text}\n---原文ここまで---\n\n要約（日本語、HTMLタグなし、段落間は空行）:"""
    try:
        resp = sync_openai_client.chat.completions.create(
            model=OPENAI_SUMMARY_MODEL,
            messages=[{"role": "system", "content": system_prompt_section}, {"role": "user", "content": user_prompt_section}],
            max_tokens=req.max_tokens, temperature=0.2,
        )
        return {"summary": resp.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"Error during summarization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during summarization: {str(e)}")

# ─── TTS (/tts) ───────────────────────────────────────────────────
class TTSRequest(BaseModel):
    text: str

@app.post("/tts", response_class=StreamingResponse)
async def tts(req: TTSRequest):
    global polly
    if not polly: raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTS unavailable.")
    if not req.text: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Text required.")
    try:
        audio_response = polly.synthesize_speech(Text=req.text, OutputFormat=AWS_POLLY_OUTPUT_FORMAT, VoiceId=AWS_POLLY_VOICE_ID_JA, Engine=AWS_POLLY_ENGINE, LanguageCode='ja-JP')
        if "AudioStream" in audio_response:
            return StreamingResponse(io.BytesIO(audio_response["AudioStream"].read()), media_type=f"audio/{AWS_POLLY_OUTPUT_FORMAT}")
        else: raise HTTPException(status_code=500, detail="Could not stream audio.")
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


# ─── Notion連携用エンドポイント (/api/save_to_notion) ─────────────────
class NotionPageRequest(BaseModel): # このモデルは変更なし (pdf_google_drive_url は既に存在)
    title: str
    authors: Optional[List[str]] = Field(default_factory=list)
    journal: Optional[str] = None
    published_date: Optional[str] = None
    doi: Optional[str] = None
    pdf_filename: Optional[str] = None
    pdf_google_drive_url: Optional[str] = None
    original_abstract: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    rating: Optional[str] = None
    memo: Optional[str] = None

async def generate_short_abstract_for_notion(abstract_text: str) -> Optional[str]:
    # ... (OpenAIモデル名が修正されていることを確認) ...
    if not abstract_text or not openai_aclient:
        # ...
        return "アブストラクトの短縮要約は利用できません（OpenAI設定不備）。"
    try:
        logger.info(f"Requesting short summary for Notion (abstract starts with): {abstract_text[:50]} using model: {OPENAI_SUMMARY_MODEL}")
        response = await openai_aclient.chat.completions.create(
            model=OPENAI_SUMMARY_MODEL, # ★★★ モデル名を確認 ★★★
            # ...
        )
        # ...
        return response.choices[0].message.content.strip()
    except Exception as e:
        # ...
        return f"短縮アブストラクトの生成中にエラーが発生しました: {str(e)}"


@app.post("/api/save_to_notion")
async def save_to_notion_endpoint(request_data: NotionPageRequest):
    if not notion_utils_client or not NOTION_DB_ID_FROM_UTILS:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Notion integration not configured.")
    
    short_abstract_text_for_notion = None
    if request_data.original_abstract:
        short_abstract_text_for_notion = await generate_short_abstract_for_notion(request_data.original_abstract)
    
    notion_page_data = {
        "title": request_data.title, "authors": request_data.authors, "journal": request_data.journal,
        "published_date": request_data.published_date, "doi": request_data.doi,
        "pdf_filename": request_data.pdf_filename, 
        "pdf_google_drive_url": request_data.pdf_google_drive_url, # ここは既に正しく渡される想定
        "short_abstract": short_abstract_text_for_notion,
        "tags": request_data.tags, "rating": request_data.rating, "memo": request_data.memo,
    }
    logger.info(f"Saving to Notion: {request_data.title[:50]}...")
    start_time_notion_save = time.time()
    try:
        result = await run_in_threadpool(create_notion_page, **notion_page_data)
        end_time_notion_save = time.time()
        if "error" in result:
            logger.error(f"Error saving to Notion: {result['error']}. Took {end_time_notion_save - start_time_notion_save:.2f} seconds.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
        logger.info(f"Successfully saved to Notion: {request_data.title[:50]}. Took {end_time_notion_save - start_time_notion_save:.2f} seconds.")
        return result
    except Exception as e:
        end_time_notion_save = time.time()
        logger.error(f"Exception saving to Notion: {str(e)}. Took {end_time_notion_save - start_time_notion_save:.2f} seconds.", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving to Notion: {str(e)}")


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn for local development.")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)