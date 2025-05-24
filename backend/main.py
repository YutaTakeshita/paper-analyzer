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
from app.tei_utils import extract_jats_sections, extract_jats_references # extract_jats_sections を確認
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
    allow_origins=["*"], # 本番環境ではより厳密なオリジンを指定することを推奨
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
from google.cloud import storage, firestore # storage を import
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
        # print("tei_xml:", repr(tei_xml[:500])) # デバッグ用、運用時はコメントアウト推奨
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
    # print("DEBUG: Using external CERMINE API" if CERMINE_API_URL else "DEBUG: Using local JAR") # デバッグ用
    if CERMINE_API_URL:
        resp = await cermine_api_parse(file)
        try:
            json_obj = resp['tei']
            if isinstance(json_obj, str):
                import json
                json_obj = json.loads(json_obj)
        except Exception as e:
            logger.exception("cermine_upload failed when parsing external API JSON")
            raise HTTPException(500, f"parse external CERMINE API JSON failed: {e}")
        return JSONResponse(content=json_obj)

    job_id  = uuid.uuid4().hex
    workdir = f"/tmp/{job_id}"
    os.makedirs(workdir, exist_ok=True)
    pdf_path_for_tei2json = None # convert_xml_to_json に渡すPDFパス
    try:
        content = await file.read()
        pdf_filename = file.filename if file.filename else "uploaded_file.pdf"
        pdf_path_for_tei2json = os.path.join(workdir, pdf_filename) # PDFパスを保存
        with open(pdf_path_for_tei2json, 'wb') as f:
            f.write(content)

        if not CERMINE_JAR:
            raise HTTPException(500, detail="CERMINE_JAR_PATH is not set")
        cmd = ["java", "-jar", CERMINE_JAR, "-path", workdir, "-outputs", "jats"]
        subprocess.run(cmd, check=True, stderr=subprocess.PIPE, timeout=CERMINE_TIMEOUT)

        logger.debug("Workdir contents after CERMINE: %s", os.listdir(workdir))
        xml_file_path = next(
            (os.path.join(workdir, fn) for fn in os.listdir(workdir)
             if fn.lower().endswith(('.xml', '.cermxml', '.nxml'))),
            None
        )
        if not xml_file_path:
            raise HTTPException(500, detail="No CERMINE output XML found in workdir")

        tei_xml_string = open(xml_file_path, encoding='utf-8').read()
        
        # convert_xml_to_json を呼び出す際に、オリジナルのPDFパスを渡す
        json_output = convert_xml_to_json(tei_xml_string, pdf_path=pdf_path_for_tei2json)
        
        return JSONResponse(content=json_output)

    except subprocess.TimeoutExpired:
        logger.error("CERMINE process timed out for /api/parse")
        raise HTTPException(504, detail="CERMINE timed out")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode(errors="ignore")
        logger.error("CERMINE process error for /api/parse: %s", err)
        raise HTTPException(500, detail=f"CERMINE execution failed: {err}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled exception in /api/parse")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
    finally:
        if os.path.exists(workdir): # workdir が存在する場合のみ削除
             shutil.rmtree(workdir, ignore_errors=True)


# ─── 要約 ─────────────────────────────────────────────────────────────
class SummarizeRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = 1500

@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    resp = openai.chat.completions.create(
        model="gpt-4o-mini", # または設定に応じたモデル
        messages=[{"role":"system","content":"You are a helpful assistant that summarizes academic paper sections."}, {"role":"user","content":f"Please summarize the following text:\n\n{req.text}"}],
        max_tokens=req.max_tokens
    )
    return {"summary": resp.choices[0].message.content.strip()}

# ─── TTS ──────────────────────────────────────────────────────────────
@app.post("/tts")
async def tts(body: dict):
    text = body.get("text") or ""
    if not text:
        raise HTTPException(400, "Field 'text' is required")
    try:
        audio_response = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId="Mizuki") # 例: Mizuki (日本語女性)
        return Response(content=audio_response["AudioStream"].read(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"AWS Polly TTS error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

# ─── GCS アップロード & Cloud Run Job ─────────────────────────────────
@app.post("/api/cermine/upload")
async def cermine_upload(file: UploadFile = File(...)):
    job_id = uuid.uuid4().hex
    if not job_id or job_id.strip() == "" or "/" in job_id: # job_idのバリデーション
        logger.error(f"Invalid jobId generated or received: {job_id}")
        raise HTTPException(400, "Invalid jobId")

    tmp_pdf_dir = "/tmp" # 一時ファイルの保存先
    os.makedirs(tmp_pdf_dir, exist_ok=True) # ディレクトリがなければ作成
    tmp_pdf_path = os.path.join(tmp_pdf_dir, f"{job_id}.pdf")

    try:
        with open(tmp_pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f) # file.read()より効率的な場合がある
        logger.info(f"Uploaded file saved temporarily to {tmp_pdf_path} for jobId {job_id}")
    except Exception as e:
        logger.error(f"Failed to save uploaded file to {tmp_pdf_path} for jobId {job_id}. Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")
    finally:
        await file.close()


    bucket_name = "cermine_paket" # バケット名を一箇所で管理
    gcs_pdf_blob_name = f"{job_id}.pdf"
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(gcs_pdf_blob_name)
        blob.upload_from_filename(tmp_pdf_path)
        logger.info(f"File {tmp_pdf_path} uploaded to gs://{bucket_name}/{gcs_pdf_blob_name} for jobId {job_id}")
    except Exception as e:
        logger.error(f"Failed to upload file to GCS for jobId {job_id}. Error: {e}", exc_info=True)
        if os.path.exists(tmp_pdf_path): # GCSアップロード失敗時は一時ファイルを削除
            os.remove(tmp_pdf_path)
        raise HTTPException(status_code=500, detail="Failed to upload file to Cloud Storage.")
    
    if os.path.exists(tmp_pdf_path): # GCSアップロード成功後も一時ファイルを削除
        os.remove(tmp_pdf_path)

    try:
        firestore_client.collection("jobs").document(job_id).set({
            "status": "pending",
            "pdfPath": f"gs://{bucket_name}/{gcs_pdf_blob_name}",
            "createdAt": firestore.SERVER_TIMESTAMP # 作成日時を記録
        })
        logger.info(f"Job {job_id} status set to pending in Firestore.")
    except Exception as e:
        logger.error(f"Failed to set job status in Firestore for jobId {job_id}. Error: {e}", exc_info=True)
        # ここでエラーが発生した場合、GCSにアップロードされたファイルの後処理も考慮が必要
        raise HTTPException(status_code=500, detail="Failed to set job status in Firestore.")


    # Cloud Run Jobの起動
    job_name_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/jobs/{JOB_NAME}"
    arguments = [f"gs://{bucket_name}/{gcs_pdf_blob_name}"]

    try:
        run_client.projects().locations().jobs().run(
            name=job_name_path, # 変数名修正
            body={
                "overrides": {
                    "containerOverrides": [
                        {
                            "args": arguments
                        }
                    ]
                }
            }
        ).execute()
        logger.info(f"Successfully triggered Cloud Run Job {JOB_NAME} for jobId {job_id} with PDF {gcs_pdf_blob_name}")
    except Exception as e:
        logger.error(f"Failed to trigger Cloud Run Job for jobId {job_id}. Error: {e}", exc_info=True)
        # Job起動失敗時はFirestoreのステータスを 'failed' に更新することも検討
        try:
            firestore_client.collection("jobs").document(job_id).update({
                "status": "failed",
                "errorMessage": f"Failed to trigger Cloud Run Job: {str(e)}"
            })
        except Exception as fe:
            logger.error(f"Additionally failed to update Firestore to 'failed' for jobId {job_id} after Job trigger failure. Error: {fe}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger Cloud Run Job: {str(e)}")

    return {"jobId": job_id}

@app.get("/api/cermine/status")
async def cermine_status(jobId: str):
    try:
        doc_ref = firestore_client.collection("jobs").document(jobId)
        doc = doc_ref.get()
        if not doc.exists:
            logger.warn(f"JobId {jobId} not found in Firestore for status check.")
            raise HTTPException(status_code=404, detail="Job not found")
        
        data = doc.to_dict()
        status = data.get("status", "unknown")
        res = {"status": status}
        
        if status == "done":
            # downloadUrl はフロントエンドが直接GCSにアクセスする代わりに、
            # 新しいエンドポイント(/api/get-result-json)を使うので、このURLは必須ではなくなる。
            # ただし、互換性やデバッグのために残しても良い。
            res["downloadUrl"] = f"https://storage.googleapis.com/cermine_paket/{jobId}.xml"
            # 必要であれば、他の情報（例：処理完了日時など）もここに追加できる
            if "errorMessage" in data: # エラーステータスの場合も考慮
                res["errorMessage"] = data["errorMessage"]

        elif status == "failed" and "errorMessage" in data:
             res["errorMessage"] = data["errorMessage"]
        
        logger.info(f"Status check for jobId {jobId}: {res}")
        return res
    except HTTPException as http_exc:
        raise http_exc # HTTPExceptionはそのまま上に投げる
    except Exception as e:
        logger.error(f"Error fetching status for jobId {jobId} from Firestore. Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching job status: {str(e)}")


# backend/main.py の適切な場所に追加（他のエンドポイント定義の後など）
# 必要なimport文がファイルの先頭にあることを確認してください:
# from google.cloud import storage
# from app.tei2json import convert_xml_to_json
# from fastapi.responses import JSONResponse
# from fastapi import HTTPException
# import os # osモジュールも必要になる場合があります
# import logging # logger を使用する場合
# logger = logging.getLogger("uvicorn.error") # グローバルに定義されているものを使用

@app.get("/api/get-result-json")
async def get_result_json(jobId: str):
    try:
        # FirestoreからジョブのステータスとGCSパス（XMLとPDFのパス）を確認
        doc_ref = firestore_client.collection("jobs").document(jobId)
        doc = doc_ref.get()
        if not doc.exists:
            logger.warn(f"JobId {jobId} not found in Firestore for get-result-json.")
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_data = doc.to_dict()
        if job_data.get("status") != "done":
            logger.warn(f"JobId {jobId} is not yet 'done'. Current status: {job_data.get('status')}")
            # エラーメッセージもあればフロントに返す
            error_message = job_data.get("errorMessage", f"Job not yet completed. Status: {job_data.get('status')}")
            raise HTTPException(status_code=400, detail=error_message)

        # GCSからXMLファイルの内容を取得
        bucket_name = "cermine_paket" 
        xml_blob_name = f"{jobId}.xml"
        
        bucket = storage_client.bucket(bucket_name) # storage_client はグローバルなもの
        xml_blob = bucket.blob(xml_blob_name)

        if not xml_blob.exists():
            logger.error(f"Result XML gs://{bucket_name}/{xml_blob_name} not found in GCS for jobId: {jobId}.")
            raise HTTPException(status_code=404, detail="Result XML not found in Cloud Storage, though job marked as done.")
        
        xml_content_string = xml_blob.download_as_text()
        logger.info(f"Successfully downloaded XML from GCS for jobId: {jobId} to be converted to JSON.")

        # オリジナルのPDFのGCSパスを取得
        original_pdf_gcs_path = job_data.get("pdfPath") # Firestoreに保存したPDFのGCSパス
        json_output = {}
        temp_pdf_for_conversion_path = None # finallyで確実に削除するために初期化

        if not original_pdf_gcs_path:
            logger.warn(f"Original PDF path not found in Firestore for jobId {jobId}. Figures/tables from PDF will not be extracted.")
            json_output = convert_xml_to_json(xml_content_string, pdf_path=None)
        else:
            tmp_pdf_dir = "/tmp" # Cloud Runの書き込み可能ディレクトリ
            os.makedirs(tmp_pdf_dir, exist_ok=True)
            # job_id に加えて、ファイル名が一意になるように少し工夫 (同時リクエストでの衝突回避)
            temp_pdf_for_conversion_path = os.path.join(tmp_pdf_dir, f"{jobId}_orig_for_json_{uuid.uuid4().hex[:8]}.pdf")
            
            try:
                if original_pdf_gcs_path.startswith(f"gs://{bucket_name}/"):
                    pdf_blob_name = original_pdf_gcs_path[len(f"gs://{bucket_name}/"):]
                else:
                    logger.error(f"Unexpected GCS path format for PDF: {original_pdf_gcs_path} for jobId {jobId}")
                    # PDFパスが不正でもXMLからの処理は試みる（図表なし）
                    json_output = convert_xml_to_json(xml_content_string, pdf_path=None)
                    logger.warn(f"Proceeding with XML data only due to invalid PDF path for jobId {jobId}.")
                    # この処理の後、正常にレスポンスを返すためにreturnする
                    return JSONResponse(content=json_output)


                pdf_blob_to_download = bucket.blob(pdf_blob_name)
                if pdf_blob_to_download.exists():
                    pdf_blob_to_download.download_to_filename(temp_pdf_for_conversion_path)
                    logger.info(f"Original PDF gs://{bucket_name}/{pdf_blob_name} downloaded to {temp_pdf_for_conversion_path} for tei2json (jobId: {jobId}).")
                    # XML文字列と、ダウンロードしたPDFのパスを渡す
                    json_output = convert_xml_to_json(xml_content_string, pdf_path=temp_pdf_for_conversion_path)
                else:
                    logger.warn(f"Original PDF gs://{bucket_name}/{pdf_blob_name} not found in GCS for jobId {jobId}. Figures/tables from PDF will not be extracted.")
                    json_output = convert_xml_to_json(xml_content_string, pdf_path=None)
            finally:
                if temp_pdf_for_conversion_path and os.path.exists(temp_pdf_for_conversion_path):
                    os.remove(temp_pdf_for_conversion_path)
                    logger.info(f"Temporary PDF {temp_pdf_for_conversion_path} deleted for jobId {jobId}.")
        
        logger.info(f"Successfully converted XML to JSON for jobId: {jobId}. Figures: {len(json_output.get('figures', []))}, Tables: {len(json_output.get('tables', []))}")
        return JSONResponse(content=json_output)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"Error in /api/get-result-json for jobId: {jobId}. ErrorType: {type(e).__name__}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving or processing result: {str(e)}")