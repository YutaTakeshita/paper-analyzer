# backend/app/notion_utils.py
import os
import logging
import json
from typing import List, Optional, Dict, Set # Set をインポート
from notion_client import Client, APIResponseError # APIResponseError をインポート
from datetime import datetime
try:
    from zoneinfo import ZoneInfo # Python 3.9+
except ImportError:
    ZoneInfo = None 
    # 代替としてpytzを使う場合の例 (pip install pytz が必要)
    # import pytz
    # logger.warning("zoneinfo module not found. Consider using pytz for full JST support if needed.")


logger = logging.getLogger(__name__)

# Secret Manager からシークレットを取得するためのヘルパー関数
GCP_PROJECT_ID_NOTION = os.getenv("GCP_PROJECT", "grobid-461112") # main.pyと共通のGCP_PROJECT_IDを参照

def _get_notion_secret(secret_id_in_sm: str, project_id: str = GCP_PROJECT_ID_NOTION, version_id: str = "latest") -> Optional[str]:
    # google-cloud-secret-manager ライブラリが main.py でインポートされている前提
    # もしこのファイル単独で実行する場合は、ここでもimportが必要になるが、FastAPIアプリとしてはmain.py経由で呼ばれる
    try:
        # main.py にある get_secret を使うか、ここで再定義する。
        # ここでは main.py の get_secret を使うことを想定せず、独立して機能するように再定義する。
        # ただし、main.pyで初期化時に呼び出す場合は、main.py側のget_secretが使われる。
        # このファイルのグローバルスコープで呼び出す場合は、下記のコードが実行される。
        # よりクリーンなのは、main.pyでキーとDB IDを取得し、Clientインスタンスだけをここに渡すことです。
        # しかし、現状の構造に合わせています。
        secretmanager_client = None
        try:
            from google.cloud import secretmanager as sm_client_module
            secretmanager_client = sm_client_module.SecretManagerServiceClient()
        except ImportError:
            logger.warning("google-cloud-secret-manager library is not available in notion_utils.py scope. Cannot fetch from Secret Manager directly here.")
            return None # ライブラリがなければNoneを返す

        if not secretmanager_client:
            return None

        name = f"projects/{project_id}/secrets/{secret_id_in_sm}/versions/{version_id}"
        response = secretmanager_client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8")
        logger.info(f"Successfully accessed secret '{secret_id_in_sm}' from Secret Manager in notion_utils.")
        return payload
    except Exception as e:
        logger.warning(f"Failed to access secret '{secret_id_in_sm}' from Secret Manager (project: {project_id}) in notion_utils: {e}")
        return None

# Secret Managerでのシークレット名
NOTION_API_KEY_SECRET_NAME = os.getenv("NOTION_API_KEY_SECRET_NAME", "NOTION_API_KEY")
NOTION_DATABASE_ID_SECRET_NAME = os.getenv("NOTION_DATABASE_ID_SECRET_NAME", "NOTION_DATABASE_ID")

# Secret Manager または環境変数から値を取得
NOTION_API_KEY = _get_notion_secret(NOTION_API_KEY_SECRET_NAME)
if NOTION_API_KEY is None:
    NOTION_API_KEY = os.getenv("NOTION_API_KEY")
    if NOTION_API_KEY:
        logger.info("Notion API Key loaded from environment variable as fallback.")

NOTION_DATABASE_ID = _get_notion_secret(NOTION_DATABASE_ID_SECRET_NAME)
if NOTION_DATABASE_ID is None:
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    if NOTION_DATABASE_ID:
        logger.info("Notion Database ID loaded from environment variable as fallback.")

notion_client_instance: Optional[Client] = None
if NOTION_API_KEY and NOTION_DATABASE_ID:
    try:
        notion_client_instance = Client(auth=NOTION_API_KEY)
        logger.info("Notion client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Notion client: {e}", exc_info=True)
else:
    logger.warning("NOTION_API_KEY or NOTION_DATABASE_ID could not be loaded. Notion integration will be disabled.")


def get_all_existing_tags_from_notion(tag_property_name: str = "タグ") -> List[str]:
    """
    指定されたNotionデータベースのMulti-Selectプロパティから全ての既存タグ名を取得する。
    Args:
        tag_property_name (str): Notionデータベース内のタグプロパティの正確な名前。
                                  デフォルトは "タグ"。
    Returns:
        List[str]: 既存タグ名のリスト。取得失敗時は空リスト。
    """
    if not notion_client_instance or not NOTION_DATABASE_ID:
        logger.warning("Notion client or Database ID is not configured. Cannot fetch existing tags.")
        return []
    
    try:
        logger.info(f"Fetching database properties for database_id: {NOTION_DATABASE_ID} to get existing tags from property '{tag_property_name}'...")
        # データベースのプロパティ情報を取得
        db_info = notion_client_instance.databases.retrieve(database_id=NOTION_DATABASE_ID)
        
        properties = db_info.get("properties", {})
        tag_property_definition = properties.get(tag_property_name)

        if tag_property_definition and tag_property_definition.get("type") == "multi_select":
            options = tag_property_definition.get("multi_select", {}).get("options", [])
            existing_tags = [option["name"] for option in options if "name" in option]
            logger.info(f"Successfully fetched {len(existing_tags)} existing tags from Notion property '{tag_property_name}'.")
            return existing_tags
        else:
            logger.warning(f"Tag property '{tag_property_name}' not found or is not a multi-select type in Notion database '{NOTION_DATABASE_ID}'.")
            return []
    except APIResponseError as e:
        logger.error(f"Notion API error while fetching existing tags: {e.status} - {e.code} - {e.message}", exc_info=True)
        if hasattr(e, 'body'):
            try:
                error_body_str = e.body.decode('utf-8', 'ignore') if isinstance(e.body, bytes) else str(e.body)
                logger.error(f"Notion API error body (raw): {error_body_str}")
            except Exception as parse_e:
                logger.error(f"Unexpected error parsing Notion API error body: {parse_e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error while fetching existing tags from Notion: {e}", exc_info=True)
        return []

# ★★★ Notionデータベースから現在の最大IDを取得する関数 (新規追加) ★★★
def get_current_max_id_from_notion(id_property_name: str = "ID") -> int:
    """
    指定されたNotionデータベースの数値プロパティから現在の最大値を取得する。
    Args:
        id_property_name (str): Notionデータベース内のIDプロパティの正確な名前。
    Returns:
        int: 現在の最大ID。ページが存在しないかIDプロパティがなければ0を返す。
    """
    logger.info(f"▶ get_current_max_id_from_notion を呼び出しました。プロパティ名 = {id_property_name}")
    if not notion_client_instance or not NOTION_DATABASE_ID:
        logger.warning("Notion client or Database ID not configured. Cannot fetch max ID.")
        return 0 # フォールバックとして0を返す

    max_id_found = 0
    try:
        logger.info(f"Fetching pages from database_id: {NOTION_DATABASE_ID} to find max ID in property '{id_property_name}'...")
        
        # Notion APIでIDプロパティで降順ソートして最初の1ページを取得するクエリ
        # これが可能であれば、全ページ取得より効率的
        # 注意: Notion APIのソート機能が数値プロパティで期待通りに動作するか確認が必要
        query_params = {
            "database_id": NOTION_DATABASE_ID,
            "sorts": [
                {
                    "property": id_property_name,
                    "direction": "descending",
                }
            ],
            "page_size": 1 # 最新のIDを持つページ1つだけ取得
        }
        
        # response = notion_client_instance.databases.query(**query_params) # 同期クライアントの場合
        # FastAPIのバックグラウンドタスク内なので、同期的な呼び出しでも良いが、
        # もしメインスレッドをブロックしたくない場合は run_in_threadpool を使う
        
        # ここでは、まず全ページを取得して最大値を探すシンプルな方法を示す (ページ数が多いと非効率)
        # より効率的なのは上記のソートとページサイズ指定だが、APIの挙動確認が必要
        
        has_more = True
        next_cursor = None
        all_pages_ids = []

        while has_more:
            query_response = notion_client_instance.databases.query(
                database_id=NOTION_DATABASE_ID,
                filter={"property": id_property_name, "number": {"is_not_empty": True}}, # IDプロパティが空でないものだけ
                start_cursor=next_cursor,
                page_size=100 # 一度に取得するページ数 (最大100)
            )
            results = query_response.get("results", [])
            logger.info(f"  • this batch has {len(results)} pages. has_more={query_response.get('has_more')}")
            for page in results:
                properties = page.get("properties", {})
                id_prop_value = properties.get(id_property_name, {}).get("number")
                if isinstance(id_prop_value, (int, float)): # 数値であることを確認
                    all_pages_ids.append(int(id_prop_value))
            
            has_more = query_response.get("has_more", False)
            next_cursor = query_response.get("next_cursor")

        if all_pages_ids:
            max_id_found = max(all_pages_ids)
            logger.info(f"Max ID found in Notion property '{id_property_name}': {max_id_found}")
        else:
            logger.info(f"No pages with ID property '{id_property_name}' found, or property is empty. Starting ID from 0.")

    except APIResponseError as e:
        logger.error(f"Notion API error while fetching max ID: {e.status} - {e.code} - {e.message}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error while fetching max ID from Notion: {e}", exc_info=True)
    logger.info(f"▶ get_current_max_id_from_notion: 集計した ID 値一覧 = {all_pages_ids}")
    return max_id_found

# create_notion_page 関数の引数に new_id を追加

def create_notion_page(
    new_id: int,  # 新規ページのID (数値型)
    title: str,
    authors: Optional[List[str]] = None,
    journal: Optional[str] = None,
    published_date: Optional[str] = None, 
    doi: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    pdf_google_drive_url: Optional[str] = None, 
    short_abstract: Optional[str] = None,
    tags: Optional[List[str]] = None,
    rating: Optional[str] = None,
    memo: Optional[str] = None
) -> Dict:
    logger.debug(
        f"create_notion_page called with: title='{title[:50]}...', authors={authors}, journal='{journal}', "
        f"published_date='{published_date}', doi='{doi}', pdf_filename='{pdf_filename}', "
        f"pdf_google_drive_url='{pdf_google_drive_url}', "
        f"short_abstract_len={len(short_abstract) if short_abstract else 0}, tags={tags}, rating='{rating}', memo_len={len(memo) if memo else 0}"
    )

    if not notion_client_instance or not NOTION_DATABASE_ID:
        logger.error("Notion client or Database ID is not configured for create_notion_page.")
        return {"error": "Notion integration is not configured on the server."}

    parent_db = {"database_id": NOTION_DATABASE_ID}
    page_properties: Dict[str, Any] = {} # 型ヒントをより具体的に

    # --- Notionデータベースの実際のプロパティ名に合わせてキーを正確に設定してください ---

    # ★★★ IDプロパティの設定 ★★★
    page_properties["ID"] = { # Notionデータベースの「ID」プロパティ名に合わせてください
        "number": new_id
    }

    # 例: Notion側でプロパティ名が「論文タイトル」なら、キーも "論文タイトル" にする
    page_properties["タイトル"] = { # または "Name" など、ご自身のDBのタイトル列のプロパティ名
        "title": [{"text": {"content": title if title and title.strip() else "Untitled Paper"}}]
    }

    if authors:
        page_properties["著者"] = { # 実際のプロパティ名に修正 (例: "著者")
            "rich_text": [{"text": {"content": ", ".join(authors)}}]
        }
    
    if journal:
        page_properties["雑誌名"] = { # 実際のプロパティ名に修正 (例: "雑誌名")
            "rich_text": [{"text": {"content": journal}}]
        }

    if published_date:
        try:
            # 簡単な形式チェック (YYYY-MM-DD)
            datetime.strptime(published_date, '%Y-%m-%d')
            page_properties["発行日"] = { # 実際のプロパティ名に修正 (例: "発行日")
                "date": {"start": published_date}
            }
        except ValueError:
            logger.warning(f"Invalid date format for published_date: '{published_date}'. Must be YYYY-MM-DD. Skipping date property.")

    if doi:
        page_properties["DOI"] = { # 大文字・小文字など実際のプロパティ名に合わせる
            "rich_text": [{"text": {"content": doi}}]
        }
    
    if pdf_google_drive_url:
        page_properties["PDF"] = {  # 「PDF」プロパティがURLタイプの場合
            "url": pdf_google_drive_url
        }
    # pdf_filename は、もし別のテキストプロパティでファイル名も保存したい場合などに使用
    # elif pdf_filename: 
    #     page_properties["PDFファイル名"] = { 
    #         "rich_text": [{"text": {"content": pdf_filename}}]
    #     }


    if short_abstract:
        # Notionのテキストプロパティは2000文字制限があるため、超過する場合は丸める
        summary_to_save = short_abstract[:1997] + '...' if len(short_abstract) > 2000 else short_abstract
        page_properties["簡易アブスト"] = { # 実際のプロパティ名に修正 (例: "短縮概要")
            "rich_text": [{"text": {"content": summary_to_save}}]
        }

    if tags: # フロントエンドでユーザーが最終選択したタグのリスト
        page_properties["タグ"] = { # 実際のプロパティ名に修正 (Multi-select型を想定)
            "multi_select": [{"name": tag.strip()} for tag in tags if tag.strip()]
        }
    
    if rating:
        page_properties["Rating"] = { # 実際のプロパティ名に修正 (Select型を想定)
            "select": {"name": rating}
        }
    
    if memo:
        page_properties["メモ"] = { # 実際のプロパティ名に修正 (例: "メモ")
            "rich_text": [{"text": {"content": memo}}]
        }
    
    # ★★★ 追加日の設定 (JST対応) ★★★
    try:
        if ZoneInfo:
            now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
        else:
            logger.warning("zoneinfo module not available, using system's current time (likely UTC on Cloud Run) for '登録日'.")
            now_jst = datetime.now()
            
        current_date_iso_jst = now_jst.strftime('%Y-%m-%d')
        # Notionデータベースの「登録日」という名前の「日付」タイプのプロパティを想定
        # 実際のプロパティ名に合わせて変更してください。
        page_properties["登録日"] = {
            "date": {
                "start": current_date_iso_jst
            }
        }
        logger.info(f"登録日をJST ({current_date_iso_jst}) で設定します。")
    except Exception as e_date:
        logger.error(f"登録日のJST変換または設定中にエラー: {e_date}", exc_info=True)
        # エラーが発生しても、他のプロパティでページ作成を試みる
    # ★★★ ここまで ★★★

    logger.debug(f"Constructed properties for Notion API: {json.dumps(page_properties, indent=2, ensure_ascii=False)}")

    try:
        logger.info(f"Attempting to create Notion page with title: '{title[:50]}...' and ID: {new_id}")
        created_page = notion_client_instance.pages.create(parent=parent_db, properties=page_properties)
        logger.info(f"Successfully created Notion page. Page ID: {created_page.get('id')}, URL: {created_page.get('url')}")
        return {"success": True, "page_id": created_page.get("id"), "url": created_page.get("url")}
    except APIResponseError as e:
        logger.error(f"Failed to create Notion page (Notion APIResponseError): {e.status} - {e.code} - {e.message}", exc_info=True)
        error_detail = e.message
        if hasattr(e, 'body'):
            try:
                error_body_str = e.body.decode('utf-8', 'ignore') if isinstance(e.body, bytes) else str(e.body)
                error_body_json = json.loads(error_body_str)
                error_detail = error_body_json.get("message", error_body_str)
                logger.error(f"Notion API error body (parsed): {error_body_json}")
            except Exception as parse_e:
                logger.error(f"Failed to parse Notion API error body (raw): {error_body_str if 'error_body_str' in locals() else str(e.body)}. Parse error: {parse_e}")
                error_detail = error_body_str if 'error_body_str' in locals() and error_body_str else str(e)
        return {"error": f"Failed to create Notion page: {error_detail}"}
    except Exception as e:
        logger.error(f"Failed to create Notion page (EXCEPTION): {e}", exc_info=True)
        return {"error": f"Failed to create Notion page: {str(e)}"}