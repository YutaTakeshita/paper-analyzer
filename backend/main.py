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

# Google Drive連携用ユーティリティとテキストユーティリティのインポート
from app.gdrive_utils import get_gdrive_service_from_json_key, upload_file_to_drive
from app.text_utils import sanitize_filename


# ─── 環境変数・クライアント初期化 ──────────────────────────────────────
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_env = __import__("dotenv").load_dotenv
load_env()

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
        logger.error(f"シークレット {secret_id} (プロジェクト: {project_id}) の取得に失敗しました: {e}")
        return None

OPENAI_API_KEY_SECRET_NAME = os.getenv("OPENAI_API_KEY_SECRET_NAME", "openai-api-key")
OPENAI_API_KEY = get_secret(OPENAI_API_KEY_SECRET_NAME)
if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if OPENAI_API_KEY: logger.warning("OpenAI APIキーを環境変数からフォールバックとして設定しました。")
    else: logger.error("OpenAI APIキーが設定できませんでした。")

sync_openai_client = None
openai_aclient = None
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
    sync_openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
    openai_aclient = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAIクライアント (同期・非同期) を設定しました。")
else:
    logger.error("OpenAI APIキーが利用できないため、クライアントは初期化されませんでした。")
OPENAI_SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-4.1-mini")
logger.info(f"OpenAI要約モデルとして '{OPENAI_SUMMARY_MODEL}' を使用します。")

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
        logger.info("AWS Pollyクライアントを初期化しました。")
    except Exception as e:
        logger.error(f"AWS Pollyクライアントの初期化中にエラーが発生しました: {e}", exc_info=True)
else:
    logger.warning("AWS Pollyの認証情報が見つからないため、クライアントは初期化されませんでした。")

GROBID_SERVICE_URL = os.getenv("GROBID_SERVICE_URL", "http://localhost:8070/api/processFulltextDocument")
logger.info(f"GROBIDサービスURLとして '{GROBID_SERVICE_URL}' を使用します。")

GDRIVE_SA_KEY_JSON_SECRET_NAME = os.getenv("GDRIVE_SA_KEY_JSON_SECRET_NAME", "gdrive-sa-key-json")
GDRIVE_FOLDER_ID_SECRET_NAME = os.getenv("GDRIVE_FOLDER_ID_SECRET_NAME", "gdrive-folder-id")
gdrive_sa_key_json_content_str = None
GDRIVE_FOLDER_ID_FROM_SECRET = None
gdrive_service = None
try:
    gdrive_sa_key_json_content_str = get_secret(GDRIVE_SA_KEY_JSON_SECRET_NAME)
    GDRIVE_FOLDER_ID_FROM_SECRET = get_secret(GDRIVE_FOLDER_ID_SECRET_NAME)
    if gdrive_sa_key_json_content_str:
        gdrive_service = get_gdrive_service_from_json_key(gdrive_sa_key_json_content_str)
        if gdrive_service:
            logger.info("Google DriveサービスをSecret Manager経由で正常に初期化しました。")
        else:
            logger.error("Secret Managerからのキーを使用してGoogle Driveサービスの初期化に失敗しました。")
    else:
        logger.error(f"Google Drive用のサービスアカウントキーJSONがSecret Managerに見つかりません (シークレット名: {GDRIVE_SA_KEY_JSON_SECRET_NAME})。")
    if not GDRIVE_FOLDER_ID_FROM_SECRET:
        logger.error(f"Google DriveフォルダIDがSecret Managerに見つかりません (シークレット名: {GDRIVE_FOLDER_ID_SECRET_NAME})。Google Driveへのアップロードは失敗する可能性があります。")
    else:
        logger.info(f"Google Driveアップロード先フォルダID: {GDRIVE_FOLDER_ID_FROM_SECRET}")
except Exception as e:
    logger.error(f"Google Driveシークレットの取得またはサービスの初期化中にエラーが発生しました: {e}", exc_info=True)

processing_jobs: Dict[str, Dict[str, Any]] = {}

# ★★★ 詳細な進捗メッセージの定義を修正・調整 ★★★
PROGRESS_MESSAGES = {
    "queued": "解析キューに追加されました。順番をお待ちください...",
    "contacting_grobid": "GROBIDサービスと通信し、解析処理を待機中です (サーバーの初回起動時は時間がかかる場合があります)...", # ★ GROBID応答待ち用
    "data_extraction_formatting": "GROBIDによる解析結果を処理し、データ（本文、メタ情報、図、表など）を抽出・整形中です...",
    "gdrive_uploading": "Google DriveへPDFを保存中です...",
    "summarizing_abstract_long": "アブストラクトの要約を生成中です...",
    "processing_complete": "最終処理を行い、結果をまとめています...",
    "error_occurred": "エラーが発生しました。詳細を確認しています...",
}

def update_job_status_detail(job_id: str, status_key: str, custom_message: Optional[str] = None):
    if job_id in processing_jobs:
        message = custom_message if custom_message else PROGRESS_MESSAGES.get(status_key, "処理中です...")
        processing_jobs[job_id].update({"status_detail": message, "timestamp": datetime.utcnow().isoformat()})
        logger.info(f"[ジョブ {job_id}] 詳細ステータス更新: {message}")

@app.get("/health", summary="ヘルスチェックエンドポイント")
async def health(): return {"status": "ok"}
@app.get("/isalive", summary="生存確認エンドポイント (エイリアス)")
async def isalive(): return {"status": "alive"}
@app.get("/api/isalive", summary="API生存確認エンドポイント (テキスト応答)")
async def api_isalive(): return Response(content="true", media_type="text/plain")

async def process_pdf_in_background(
    job_id: str,
    temp_pdf_path: str,
    original_filename: str,
    content_type: Optional[str],
    temp_dir_to_clean: str
):
    logger.info(f"[ジョブ {job_id}] バックグラウンド処理を開始しました: {original_filename}")
    # ★★★ 初期詳細ステータスを "contacting_grobid" に設定 ★★★
    processing_jobs[job_id].update({"status": "processing", "status_detail": PROGRESS_MESSAGES.get("contacting_grobid"), "timestamp": datetime.utcnow().isoformat()})
    
    json_output: Dict[str, Any] = {}
    google_drive_url: Optional[str] = None
    global gdrive_service, GDRIVE_FOLDER_ID_FROM_SECRET

    try:
        tei_xml_string: Optional[str] = None
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(temp_pdf_path, 'rb') as f_pdf:
                files_for_grobid = {'input': (original_filename, f_pdf, content_type)}
                
                logger.info(f"[ジョブ {job_id}] PDFをGROBIDに送信し、応答待機中: {GROBID_SERVICE_URL}")
                # この時点でフロントエンドには "contacting_grobid" のメッセージが表示されている

                try:
                    start_time_grobid = time.time()
                    grobid_response = await client.post(GROBID_SERVICE_URL, files=files_for_grobid) # ここでGROBIDの処理を待つ
                    grobid_response.raise_for_status()
                    tei_xml_string = grobid_response.text
                    end_time_grobid = time.time()
                    logger.info(f"[ジョブ {job_id}] GROBIDからTEI XMLを受信しました。処理時間: {end_time_grobid - start_time_grobid:.2f}秒")

                except httpx.HTTPStatusError as e:
                    error_detail = e.response.text[:500] if e.response else str(e)
                    logger.error(f"[ジョブ {job_id}] GROBIDサービスエラー ({e.response.status_code if e.response else 'N/A'}): {error_detail}", exc_info=True)
                    update_job_status_detail(job_id, "error_occurred", custom_message=f"GROBIDサービスエラー: {error_detail}")
                    raise Exception(f"GROBIDサービスエラー ({e.response.status_code if e.response else 'N/A'}): {error_detail}")
                except httpx.RequestError as e:
                    logger.error(f"[ジョブ {job_id}] GROBIDリクエストエラー: {str(e)}", exc_info=True)
                    update_job_status_detail(job_id, "error_occurred", custom_message=f"GROBIDリクエストエラー: {str(e)}")
                    raise Exception(f"GROBIDリクエストエラー: {str(e)}")

        if not tei_xml_string:
            logger.error(f"[ジョブ {job_id}] GROBIDからTEI XMLを受信できませんでした。")
            update_job_status_detail(job_id, "error_occurred", custom_message="GROBIDからTEI XMLを受信できませんでした。")
            raise Exception("GROBIDからTEI XMLを受信できませんでした。")

        # ★★★ GROBID完了後、次のデータ抽出・整形フェーズのメッセージに更新 ★★★
        update_job_status_detail(job_id, "data_extraction_formatting")
        logger.info(f"[ジョブ {job_id}] TEI XMLをJSONに変換中 (図表抽出含む): {original_filename}")
        start_time_conversion = time.time()
        json_output = convert_xml_to_json(
            tei_xml_string,
            pdf_path=temp_pdf_path
        )
        end_time_conversion = time.time()
        logger.info(f"[ジョブ {job_id}] TEI XMLからJSONへの変換が完了しました。処理時間: {end_time_conversion - start_time_conversion:.2f}秒")

        update_job_status_detail(job_id, "gdrive_uploading")
        extracted_title = json_output.get('meta', {}).get('title', None)
        fallback_drive_filename_base = os.path.splitext(original_filename)[0] if original_filename else "untitled_document"
        drive_filename = sanitize_filename(extracted_title, fallback_name=fallback_drive_filename_base)
        logger.info(f"[ジョブ {job_id}] Google Drive用ファイル名を生成しました: {drive_filename}")

        if gdrive_service and GDRIVE_FOLDER_ID_FROM_SECRET:
            logger.info(f"[ジョブ {job_id}] Google Driveへアップロード中: {temp_pdf_path} を {drive_filename} として")
            start_time_gdrive = time.time()
            uploaded_file_info = await run_in_threadpool(
                upload_file_to_drive,
                service=gdrive_service,
                local_file_path=temp_pdf_path,
                filename_on_drive=drive_filename,
                folder_id=GDRIVE_FOLDER_ID_FROM_SECRET,
                make_public=True
            )
            end_time_gdrive = time.time()
            if uploaded_file_info and uploaded_file_info.get('webViewLink'):
                google_drive_url = uploaded_file_info.get('webViewLink')
                json_output['google_drive_url'] = google_drive_url
                logger.info(f"[ジョブ {job_id}] Google Driveへのアップロードに成功しました。URL: {google_drive_url}。処理時間: {end_time_gdrive - start_time_gdrive:.2f}秒")
            else:
                logger.error(f"[ジョブ {job_id}] Google DriveへのアップロードまたはURL取得に失敗しました。処理時間: {end_time_gdrive - start_time_gdrive:.2f}秒")
                json_output['google_drive_url'] = None
        else:
            if not gdrive_service: logger.error(f"[ジョブ {job_id}] Google Driveサービスが初期化されていません。アップロードをスキップします。")
            if not GDRIVE_FOLDER_ID_FROM_SECRET: logger.error(f"[ジョブ {job_id}] Google DriveフォルダIDが設定されていません。アップロードをスキップします。")
            json_output['google_drive_url'] = None
        
        update_job_status_detail(job_id, "summarizing_abstract_long")
        if json_output.get('meta') and json_output['meta'].get('abstract') and openai_aclient:
            abstract_text = json_output['meta']['abstract']
            if abstract_text and abstract_text.strip():
                try:
                    start_time_openai_long_abs = time.time()
                    system_prompt_for_abstract = """あなたは医療保健分野の学術論文を専門とする高度なAIアシスタントです。提供された学術論文のアブストラクト（抄録）を読み、その内容を起承転結をつけて日本語の自然な文章としてまとめてください。また、当該分野での現在の潮流や背景文脈を考慮し、必要であればそれを簡潔に補足情報として含めてください。"""
                    user_prompt_for_abstract = f"""以下のアブストラクトを上記の指示に従って、HTMLタグを一切含まず、段落間は空行で区切るプレーンテキスト形式で要約してください。\n\n---アブストラクトここから---\n{abstract_text}\n---アブストラクトここまで---\n\n要約（日本語、HTMLタグなし、段落間は空行）:"""
                    
                    logger.info(f"[ジョブ {job_id}] OpenAIに長文アブストラクト要約をリクエスト中 (モデル: {OPENAI_SUMMARY_MODEL})...")
                    response = await openai_aclient.chat.completions.create(
                        model=OPENAI_SUMMARY_MODEL,
                        messages=[
                            {"role": "system", "content": system_prompt_for_abstract},
                            {"role": "user", "content": user_prompt_for_abstract}
                        ],
                        max_tokens=1000,
                        temperature=0.2,
                    )
                    json_output['meta']['abstract_summary'] = response.choices[0].message.content.strip()
                    end_time_openai_long_abs = time.time()
                    logger.info(f"[ジョブ {job_id}] 長文アブストラクト要約を受信しました。処理時間: {end_time_openai_long_abs - start_time_openai_long_abs:.2f}秒")
                except Exception as e_summary:
                    logger.error(f"[ジョブ {job_id}] 長文アブストラクトの要約中にエラーが発生しました: {e_summary}", exc_info=True)
                    json_output['meta']['abstract_summary'] = "アブストラクトの自動要約中にエラーが発生しました。"
            else:
                logger.warning(f"[ジョブ {job_id}] アブストラクトが空のため、長文要約をスキップします。")
                json_output['meta']['abstract_summary'] = "アブストラクトが空のため要約できませんでした。"
        elif not openai_aclient and json_output.get('meta'):
             json_output['meta']['abstract_summary'] = "OpenAIクライアント未設定のため、自動要約は利用できません。"
        elif json_output.get('meta') and not json_output['meta'].get('abstract'):
            logger.warning(f"[ジョブ {job_id}] アブストラクトが見つからないため、長文要約をスキップします。")
            json_output['meta']['abstract_summary'] = "アブストラクトが見つからないため要約できませんでした。"

        update_job_status_detail(job_id, "processing_complete")
        processing_jobs[job_id].update({"status": "completed", "result": json_output, "timestamp": datetime.utcnow().isoformat()})
        logger.info(f"[ジョブ {job_id}] バックグラウンド処理が正常に完了しました: {original_filename}")

    except Exception as e:
        logger.error(f"[ジョブ {job_id}] バックグラウンド処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        error_message_for_user = f"エラーが発生しました: {str(e)[:100]}..."
        update_job_status_detail(job_id, "error_occurred", custom_message=error_message_for_user)
        processing_jobs[job_id].update({"status": "failed", "error": str(e), "timestamp": datetime.utcnow().isoformat()})
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
                logger.info(f"[ジョブ {job_id}] 一時PDFファイルを削除しました: {temp_pdf_path}")
            except Exception as e_clean_file:
                logger.error(f"[ジョブ {job_id}] 一時PDFファイルのクリーンアップ中にエラー: {e_clean_file}")
        if temp_dir_to_clean and os.path.exists(temp_dir_to_clean):
            try:
                shutil.rmtree(temp_dir_to_clean)
                logger.info(f"[ジョブ {job_id}] 一時ディレクトリを削除しました: {temp_dir_to_clean}")
            except Exception as e_clean_dir:
                logger.error(f"[ジョブ {job_id}] 一時ディレクトリのクリーンアップ中にエラー: {e_clean_dir}")
        
@app.post("/api/parse_async", status_code=status.HTTP_202_ACCEPTED, summary="PDFを非同期で解析開始")
async def api_parse_async_endpoint(
    file: UploadFile = File(..., description="解析するPDFファイル"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    job_id = str(uuid.uuid4())
    temp_pdf_path = None
    temp_dir_for_job = None

    try:
        temp_dir_for_job = tempfile.mkdtemp(prefix=f"paperanalyzer_job_{job_id}_")
        original_filename = file.filename if file.filename else "uploaded.pdf"
        base_filename = os.path.basename(original_filename)
        safe_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in base_filename)
        if not safe_filename: 
            safe_filename = f"{job_id}_uploaded.pdf"
        temp_pdf_path = os.path.join(temp_dir_for_job, safe_filename)

        with open(temp_pdf_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
        logger.info(f"ジョブID {job_id} のアップロードPDFを保存しました: {temp_pdf_path}")

        processing_jobs[job_id] = {
            "status": "queued", 
            "filename": original_filename,
            "status_detail": PROGRESS_MESSAGES.get("queued"), 
            "timestamp": datetime.utcnow().isoformat()
        }
        
        background_tasks.add_task(
            process_pdf_in_background,
            job_id,
            temp_pdf_path,
            original_filename,
            file.content_type,
            temp_dir_for_job
        )
        
        logger.info(f"ジョブ {job_id} (ファイル: {original_filename}) をバックグラウンド処理キューに追加しました。")
        return {"message": "PDF処理をバックグラウンドで開始しました。", "job_id": job_id, "status": "queued", "status_detail": PROGRESS_MESSAGES.get("queued")}

    except Exception as e:
        logger.error(f"非同期解析の開始中にエラーが発生しました (ファイル: {file.filename if file else '不明'}): {e}", exc_info=True)
        if temp_pdf_path and os.path.exists(temp_pdf_path): os.remove(temp_pdf_path)
        if temp_dir_for_job and os.path.exists(temp_dir_for_job): shutil.rmtree(temp_dir_for_job)
        raise HTTPException(status_code=500, detail=f"PDF処理の開始に失敗しました: {str(e)}")
    finally:
        if file:
            await file.close()

@app.get("/api/parse_status/{job_id}", summary="指定されたジョブIDの解析状況を取得")
async def get_parse_status_endpoint(job_id: str):
    job = processing_jobs.get(job_id)
    if not job:
        logger.warning(f"存在しないジョブIDがリクエストされました: {job_id}")
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"job_id": job_id, "status": "not_found", "error": "Job ID not found.", "status_detail": "ジョブが見つかりません。"}
        )
    return job

class SummarizeRequest(BaseModel):
    text: str = Field(..., description="要約するテキスト")
    max_tokens: Optional[int] = Field(1000, description="生成する最大トークン数")

@app.post("/summarize", summary="指定されたテキストを要約")
async def summarize(req: SummarizeRequest):
    if not sync_openai_client:
        logger.error("OpenAI同期クライアントが初期化されていません。要約を実行できません。")
        raise HTTPException(status_code=503, detail="要約サービスは現在利用できません。")
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="要約するテキストが必要です。")

    system_prompt_section = """あなたは、医療および保健分野の学術論文を専門とする高度なAIアシスタントです。提供された論文のセクション（原文）を読み解き、以下の指示に従って日本語で要約を生成してください。指示: 1. 原文の内容を正確に捉え、主要なポイントを抽出してください。2. 関連する現在の医学的・科学的な潮流や背景文脈を考慮し、必要であればそれを簡潔に補足情報として含めてください。ただし、原文にない情報を過度に推測したり、付け加えたりしないでください。3. もし原文中に引用や参考文献への言及（例: [1], (Smith et al., 2020) など）があれば、それらを省略せず、要約文中の対応する箇所に適切に含めてください。4. **重要: 生成される要約文は、`<p>`, `<br>`, `<em>`, `<strong>` を含む一切のHTMLタグを含まず、純粋なプレーンテキストとしてください。段落は、段落間に1つの空行を挿入することで表現してください。箇条書きが適切な場合は、各項目の先頭に「・」や「1. 」のような記号を使用し、HTMLのリストタグ (`<ul>`, `<ol>`, `<li>`) は使用しないでください。** 5. 専門用語は保持しつつも、可能な範囲で平易な表現を心がけてください。6. もし原文中に統計解析手法（例: t検定, ANOVA, カイ二乗検定, ロジスティック回帰分析など）に関する記述があれば、その手法がどのような目的で使われるものか、ごく簡潔な補足説明（例：t検定は2群間の平均値の差を比較する手法）を括弧書きなどで加えてください。ただし、補足は10～30字程度に留め、冗長にならないようにしてください。7. 要約は、客観的かつ中立的な視点を保ってください。"""
    user_prompt_section = f"""以下の論文セクションを上記の指示に従って、HTMLタグを一切含まず、段落間は空行で区切るプレーンテキスト形式で要約してください。\n\n---原文ここから---\n{req.text}\n---原文ここまで---\n\n要約（日本語、HTMLタグなし、段落間は空行）:"""
    try:
        logger.info(f"セクション要約をリクエスト中 (モデル: {OPENAI_SUMMARY_MODEL}, テキスト長: {len(req.text)})")
        resp = sync_openai_client.chat.completions.create(
            model=OPENAI_SUMMARY_MODEL,
            messages=[{"role": "system", "content": system_prompt_section}, {"role": "user", "content": user_prompt_section}],
            max_tokens=req.max_tokens,
            temperature=0.2,
        )
        summary_content = resp.choices[0].message.content.strip()
        logger.info(f"セクション要約を生成しました (生成長: {len(summary_content)})")
        return {"summary": summary_content}
    except Exception as e:
        logger.error(f"セクション要約中にエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"要約中にエラーが発生しました: {str(e)}")

class TTSRequest(BaseModel):
    text: str = Field(..., description="音声合成するテキスト")

@app.post("/tts", response_class=StreamingResponse, summary="指定されたテキストを音声合成")
async def tts(req: TTSRequest):
    global polly
    if not polly:
        logger.error("AWS Pollyクライアントが初期化されていません。TTSを実行できません。")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="TTSサービスは現在利用できません。")
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="音声合成するテキストが必要です。")
    try:
        logger.info(f"TTSリクエストを受信しました (テキスト長: {len(req.text)})")
        audio_response = polly.synthesize_speech(
            Text=req.text,
            OutputFormat=AWS_POLLY_OUTPUT_FORMAT,
            VoiceId=AWS_POLLY_VOICE_ID_JA,
            Engine=AWS_POLLY_ENGINE,
            LanguageCode='ja-JP'
        )
        if "AudioStream" in audio_response:
            logger.info("TTS音声ストリームの生成に成功しました。")
            return StreamingResponse(io.BytesIO(audio_response["AudioStream"].read()), media_type=f"audio/{AWS_POLLY_OUTPUT_FORMAT}")
        else:
            logger.error("TTS APIレスポンスにAudioStreamが含まれていませんでした。")
            raise HTTPException(status_code=500, detail="音声ストリームの生成に失敗しました。")
    except NoCredentialsError:
        logger.error("AWS認証情報が見つからないため、TTSリクエストに失敗しました。", exc_info=True)
        raise HTTPException(status_code=500, detail="TTSサービス認証エラー。")
    except (BotoCoreError, ClientError) as e:
        logger.error(f"AWS Polly API呼び出し中にエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTSサービスでエラーが発生しました: {str(e)}")
    except Exception as e:
        logger.error(f"TTS処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS処理中にエラーが発生しました: {str(e)}")

class NotionPageRequest(BaseModel):
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
    if not abstract_text or not abstract_text.strip() or not openai_aclient:
        logger.warning("Notion用短縮アブストラクトを生成できません: テキストが空か、OpenAIクライアントが未初期化です。")
        return "アブストラクトが空か、OpenAI設定不備のため短縮要約は利用できません。"
    try:
        logger.info(f"Notion用短縮アブストラクトをリクエスト中 (モデル: {OPENAI_SUMMARY_MODEL}, アブストラクト先頭: {abstract_text[:50]}...)")
        system_prompt_short = "You are a helpful assistant. Summarize the following abstract into one or two concise Japanese sentences."
        user_prompt_short = f"Abstract:\n\"\"\"\n{abstract_text}\n\"\"\"\n\nOne to two sentence Japanese summary:"
        
        logger.debug(f"OpenAI 短縮要約 - モデル: {OPENAI_SUMMARY_MODEL}")
        logger.debug(f"OpenAI 短縮要約 - システムプロンプト: {system_prompt_short[:100]}")
        logger.debug(f"OpenAI 短縮要約 - ユーザープロンプト (先頭100文字): {user_prompt_short[:100]}")

        start_time_openai_short_abs = time.time()
        response = await openai_aclient.chat.completions.create(
            model=OPENAI_SUMMARY_MODEL,
            messages=[
                {"role": "system", "content": system_prompt_short},
                {"role": "user", "content": user_prompt_short}
            ],
            max_tokens=200,
            temperature=0.3,
            n=1,
            stop=None,
        )
        summary_text = response.choices[0].message.content.strip()
        end_time_openai_short_abs = time.time()
        logger.info(f"Notion用短縮アブストラクトを生成しました。処理時間: {end_time_openai_short_abs - start_time_openai_short_abs:.2f}秒")
        return summary_text
    except Exception as e:
        logger.error(f"Notion用短縮アブストラクトの生成中にエラーが発生しました: {e}", exc_info=True)
        return f"短縮アブストラクトの生成中にエラーが発生しました: {str(e)}"

@app.post("/api/save_to_notion", summary="解析結果をNotionデータベースに保存")
async def save_to_notion_endpoint(request_data: NotionPageRequest):
    if not notion_utils_client or not NOTION_DB_ID_FROM_UTILS:
        logger.error("NotionクライアントまたはデータベースIDが設定されていません。")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Notion連携が設定されていません。")
    
    short_abstract_text_for_notion: Optional[str] = None
    if request_data.original_abstract:
        short_abstract_text_for_notion = await generate_short_abstract_for_notion(request_data.original_abstract)
    
    notion_page_data = {
        "title": request_data.title,
        "authors": request_data.authors,
        "journal": request_data.journal,
        "published_date": request_data.published_date,
        "doi": request_data.doi,
        "pdf_filename": request_data.pdf_filename, 
        "pdf_google_drive_url": request_data.pdf_google_drive_url,
        "short_abstract": short_abstract_text_for_notion,
        "tags": request_data.tags,
        "rating": request_data.rating,
        "memo": request_data.memo,
    }
    logger.info(f"Notionへ保存中: {request_data.title[:50]}...")
    start_time_notion_save = time.time()
    try:
        result = await run_in_threadpool(create_notion_page, **notion_page_data)
        end_time_notion_save = time.time()
        if "error" in result:
            logger.error(f"Notionへの保存中にエラーが発生しました: {result['error']}。処理時間: {end_time_notion_save - start_time_notion_save:.2f}秒")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result["error"])
        logger.info(f"Notionへの保存に成功しました: {request_data.title[:50]}。処理時間: {end_time_notion_save - start_time_notion_save:.2f}秒")
        return result
    except Exception as e:
        end_time_notion_save = time.time()
        logger.error(f"Notionへの保存中に予期せぬ例外が発生しました: {str(e)}。処理時間: {end_time_notion_save - start_time_notion_save:.2f}秒", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Notionへの保存中にエラーが発生しました: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info("Uvicornをローカル開発モードで起動します。")
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)