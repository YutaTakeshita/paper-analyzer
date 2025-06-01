# backend/app/notion_utils.py
import os
import logging
import json # ログ出力用にjsonをインポート
from typing import List, Optional, Dict
from notion_client import Client
from datetime import datetime

# google-cloud-secret-manager をインポート
try:
    from google.cloud import secretmanager
except ImportError:
    secretmanager = None # ライブラリがない場合はフォールバック用

logger = logging.getLogger(__name__)

# Secret Manager からシークレットを取得するためのヘルパー関数
GCP_PROJECT_ID_NOTION = os.getenv("GCP_PROJECT", "grobid-461112")

def _get_notion_secret(secret_id_in_sm: str, project_id: str = GCP_PROJECT_ID_NOTION, version_id: str = "latest") -> Optional[str]:
    if not secretmanager:
        logger.warning("google-cloud-secret-manager library is not installed. Cannot fetch from Secret Manager.")
        return None
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_id_in_sm}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        logger.info(f"Successfully accessed secret '{secret_id_in_sm}' from Secret Manager.")
        return payload
    except Exception as e:
        logger.warning(f"Failed to access secret '{secret_id_in_sm}' from Secret Manager (project: {project_id}): {e}")
        return None

NOTION_API_KEY_SECRET_NAME = os.getenv("NOTION_API_KEY_SECRET_NAME", "NOTION_API_KEY")
NOTION_DATABASE_ID_SECRET_NAME = os.getenv("NOTION_DATABASE_ID_SECRET_NAME", "NOTION_DATABASE_ID")

NOTION_API_KEY = _get_notion_secret(NOTION_API_KEY_SECRET_NAME)
NOTION_DATABASE_ID = _get_notion_secret(NOTION_DATABASE_ID_SECRET_NAME)

if NOTION_API_KEY is None:
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    if NOTION_API_KEY:
        logger.info("Notion API Key loaded from environment variable as fallback.")
if NOTION_DATABASE_ID is None:
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    if NOTION_DATABASE_ID:
        logger.info("Notion Database ID loaded from environment variable as fallback.")

notion_client_instance = None
if NOTION_API_KEY and NOTION_DATABASE_ID:
    try:
        notion_client_instance = Client(auth=NOTION_API_KEY)
        logger.info("Notion client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Notion client: {e}", exc_info=True)
else:
    logger.warning("NOTION_API_KEY or NOTION_DATABASE_ID could not be loaded. Notion integration will be disabled.")

def create_notion_page(
    title: str,
    authors: Optional[List[str]] = None,
    journal: Optional[str] = None,
    published_date: Optional[str] = None, 
    doi: Optional[str] = None,
    pdf_filename: Optional[str] = None, # 元のファイル名、ログやフォールバック用に残すのは良い
    pdf_google_drive_url: Optional[str] = None, 
    short_abstract: Optional[str] = None,
    tags: Optional[List[str]] = None,
    rating: Optional[str] = None,
    memo: Optional[str] = None
) -> Dict:
    logger.debug(
        f"create_notion_page called with: title='{title}', authors={authors}, journal='{journal}', "
        f"published_date='{published_date}', doi='{doi}', pdf_filename='{pdf_filename}', "
        f"pdf_google_drive_url='{pdf_google_drive_url}', "
        f"short_abstract_len={len(short_abstract) if short_abstract else 0}, tags={tags}, rating='{rating}', memo_len={len(memo) if memo else 0}"
    )

    if not notion_client_instance or not NOTION_DATABASE_ID:
        logger.error("Notion client or Database ID is not configured for create_notion_page.")
        return {"error": "Notion integration is not configured on the server."}

    parent_db = {"database_id": NOTION_DATABASE_ID}
    page_properties = {}

    page_properties["タイトル"] = {
        "title": [{"text": {"content": title if title else "Untitled Paper"}}]
    }

    if authors:
        page_properties["著者"] = {
            "rich_text": [{"text": {"content": ", ".join(authors)}}]
        }
    
    if journal:
        page_properties["雑誌名"] = {
            "rich_text": [{"text": {"content": journal}}]
        }

    if published_date:
        try:
            datetime.strptime(published_date, '%Y-%m-%d')
            page_properties["発行日"] = {
                "date": {"start": published_date}
            }
        except ValueError:
            logger.warning(f"Invalid date format for published_date: '{published_date}'. Must be YYYY-MM-DD. Skipping date property.")

    if doi:
        page_properties["doi"] = {
            "rich_text": [{"text": {"content": doi}}]
        }

    # ★★★ 「PDF」プロパティの処理を修正 ★★★
    # Notionデータベースの "PDF" プロパティが「URL」タイプであることを強く推奨します。
    # そのプロパティ名を "PDF" と仮定しています。実際のプロパティ名に合わせてください。
    if pdf_google_drive_url:
        page_properties["PDF"] = {  # Notionデータベースの実際の「PDF」プロパティ名（URLタイプ）
            "url": pdf_google_drive_url
        }
    elif pdf_filename: 
        # Google Drive URLがない場合のフォールバックとしてファイル名を「PDF」(URLタイプ)プロパティに入れることはできません。
        # もし「PDF」プロパティが「リッチテキスト」タイプで、ファイル名をどうしても入れたい場合は、
        # 下のコメントアウトを解除し、Notion側のプロパティタイプと合わせてください。
        # ただし、その場合、URLは単なるテキストとして表示されます。
        # page_properties["PDF"] = {
        #     "rich_text": [{"text": {"content": pdf_filename}}]
        # }
        logger.info(f"Google Drive URL is not available for '{title}'. 'PDF' property will be empty or not set if it's a URL type.")
    # ★★★ ここまで ★★★

    # 以前の "PDFリンク (Drive)" プロパティの設定は削除 (またはコメントアウト)
    # if pdf_google_drive_url:
    #     page_properties["PDFリンク (Drive)"] = { # これはもう不要
    #         "url": pdf_google_drive_url
    #     }

    if short_abstract:
        summary_to_save = short_abstract[:1997] + '...' if len(short_abstract) > 2000 else short_abstract
        page_properties["簡易アブスト"] = {
            "rich_text": [{"text": {"content": summary_to_save}}]
        }

    if tags:
        page_properties["タグ"] = {
            "multi_select": [{"name": tag.strip()} for tag in tags if tag.strip()]
        }
    
    if rating:
        page_properties["Rating"] = {
            "select": {"name": rating}
        }
    
    if memo:
        page_properties["メモ"] = {
            "rich_text": [{"text": {"content": memo}}]
        }
    
    current_date_iso = datetime.now().strftime('%Y-%m-%d')
    # Notionデータベースで "登録日" という名前の「日付」タイプのプロパティを想定
    # 実際のプロパティ名に合わせて変更してください。
    page_properties["登録日"] = {
        "date": {
            "start": current_date_iso
        }
    }

    logger.debug(f"Constructed properties for Notion API: {json.dumps(page_properties, indent=2, ensure_ascii=False)}")

    try:
        logger.info(f"Attempting to create Notion page with title: '{title}'")
        created_page = notion_client_instance.pages.create(parent=parent_db, properties=page_properties)
        logger.info(f"Successfully created Notion page. Page ID: {created_page.get('id')}, URL: {created_page.get('url')}")
        return {"success": True, "page_id": created_page.get("id"), "url": created_page.get("url")}
    except Exception as e:
        logger.error(f"Failed to create Notion page (EXCEPTION): {e}", exc_info=True)
        error_detail = str(e)
        error_body_str = ""
        if hasattr(e, 'body'):
            try:
                if isinstance(e.body, bytes):
                    error_body_str = e.body.decode('utf-8', 'ignore')
                else:
                    error_body_str = str(e.body)
                
                error_body_json = json.loads(error_body_str)
                error_detail = error_body_json.get("message", error_body_str)
                logger.error(f"Notion API error body (parsed): {error_body_json}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse Notion API error body (raw): {error_body_str}")
                error_detail = error_body_str if error_body_str else str(e)
            except Exception as parse_e:
                logger.error(f"Unexpected error parsing Notion API error body: {parse_e}")
                error_detail = error_body_str if error_body_str else str(e)
        return {"error": f"Failed to create Notion page: {error_detail}"}