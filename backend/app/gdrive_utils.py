# backend/app/gdrive_utils.py

import os
import json # JSON文字列のパースに必要
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import logging # ロギングを追加

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_gdrive_service_from_json_key(sa_key_json_content_str: str):
    """
    サービスアカウントキーのJSON文字列からGoogle Drive APIサービスオブジェクトを取得する。

    Args:
        sa_key_json_content_str (str): サービスアカウントキーのJSONファイルの内容（文字列）。

    Returns:
        googleapiclient.discovery.Resource: Google Drive APIサービスオブジェクト。
                                            エラー時はNoneを返す。
    """
    if not sa_key_json_content_str:
        logger.error("Google DriveのサービスアカウントキーJSONコンテンツが提供されていません。")
        return None
    try:
        # JSON文字列をPythonの辞書オブジェクトに変換
        sa_info = json.loads(sa_key_json_content_str)
        
        # 辞書から認証情報オブジェクトを作成
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=SCOPES)
        
        # APIクライアントをビルド
        # cache_discovery=False は、一部環境での警告やエラーを回避するために推奨
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        logger.info("Google Drive API サービスへの接続に成功しました (JSONキーコンテンツ使用)。")
        return service
    except json.JSONDecodeError as e:
        logger.error(f"サービスアカウントキーのJSON文字列のパースに失敗しました: {e}")
        return None
    except Exception as e:
        logger.error(f"サービスアカウントキーJSONからのサービス構築中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return None

def upload_file_to_drive(service, local_file_path: str, filename_on_drive: str, folder_id: str, make_public: bool = True):
    """
    指定されたローカルファイルをGoogle Driveの指定フォルダにアップロードし、
    オプションで公開パーミッションを設定して共有可能なリンクを取得する。

    Args:
        service: Google Drive APIサービスオブジェクト。
        local_file_path (str): アップロードするローカルファイルのパス。
        filename_on_drive (str): Google Drive上でのファイル名。
        folder_id (str): アップロード先のフォルダID。必須。
        make_public (bool, optional): Trueの場合、「リンクを知っている全員が閲覧者」に設定。デフォルトはTrue。

    Returns:
        dict: アップロードされたファイルのメタデータ (id, name, webViewLinkなどを含む)。
              エラー時はNoneを返す。
    """
    if not service:
        logger.error("Google Driveサービスオブジェクトが無効です。アップロードできません。")
        return None
    if not os.path.exists(local_file_path):
        logger.error(f"ローカルファイルが見つかりません: {local_file_path}")
        return None
    if not folder_id:
        logger.error("アップロード先のGoogle DriveフォルダIDが指定されていません。")
        return None
    if not filename_on_drive:
        logger.error("Google Drive上でのファイル名が指定されていません。")
        return None


    file_metadata = {
        'name': filename_on_drive,
        'parents': [folder_id] # 親フォルダを指定
    }

    media = MediaFileUpload(local_file_path, resumable=True)
    try:
        logger.info(f"Google Driveへファイルをアップロード開始: '{filename_on_drive}' (ローカルパス: {local_file_path})")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, webContentLink'  # 取得したい情報を指定
        ).execute()
        logger.info(f"ファイル '{file.get('name')}' (ID: {file.get('id')}) がGoogle Driveにアップロードされました。")

        if make_public and file.get('id'):
            if set_file_permissions_anyone_with_link(service, file.get('id')):
                 # パーミッション設定後に再度ファイル情報を取得して最新のリンクを得る
                updated_file_info = service.files().get(
                    fileId=file.get('id'),
                    fields='id, name, webViewLink, webContentLink' # webContentLinkも有用な場合がある
                ).execute()
                logger.info(f"  公開リンク (webViewLink): {updated_file_info.get('webViewLink')}")
                return updated_file_info
            else:
                logger.warning("ファイルの公開パーミッション設定に失敗しました。リンクは非公開のままかもしれません。")
                return file # パーミッション設定失敗でもファイル情報自体は返す
        else:
            logger.info("ファイルは公開設定されませんでした（make_public=False またはファイルIDなし）。")
            return file

    except HttpError as error:
        logger.error(f"ファイルアップロード中にGoogle Drive APIエラーが発生しました: {error.resp.status} - {error._get_reason()}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"ファイルアップロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return None

def set_file_permissions_anyone_with_link(service, file_id: str) -> bool:
    """指定されたファイルのパーミッションを「リンクを知っている全員が閲覧者」に設定する"""
    if not service:
        logger.error("Google Driveサービスオブジェクトが無効です。パーミッションを設定できません。")
        return False
    if not file_id:
        logger.error("ファイルIDが無効です。パーミッションを設定できません。")
        return False
        
    try:
        permission_body = {'type': 'anyone', 'role': 'reader'}
        service.permissions().create(fileId=file_id, body=permission_body).execute()
        logger.info(f"ファイルID '{file_id}' のパーミッションを「リンクを知っている全員が閲覧者」に設定しました。")
        return True
    except HttpError as error:
        logger.error(f"パーミッション設定中にGoogle Drive APIエラーが発生しました: {error.resp.status} - {error._get_reason()}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"パーミッション設定中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return False

# --- このスクリプトを直接実行した際のテストコード (main.pyからの利用が主になるため、簡略化または削除も検討) ---
# 以下のテストコードは、環境変数やSecret Managerから直接キーやIDを取得するようにはなっていません。
# main.py側で初期化されたgdrive_serviceオブジェクトとfolder_idを使ってテストする方が実践的です。
# もしこのファイル単独でテストしたい場合は、get_secret関数などをここに持ち込むか、
# テスト用のキー情報とフォルダIDを直接記述する必要があります。
if __name__ == '__main__':
    logger.warning("このスクリプトは通常、main.pyから呼び出されるユーティリティです。")
    logger.warning("単独でテスト実行する場合、Google Driveの認証情報とフォルダIDを別途設定する必要があります。")
    
    # 以下は単体テストを行う場合のサンプル（環境変数を直接読み込むなど、適宜変更が必要）
    # from dotenv import load_dotenv
    # dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env') # backend/.env を想定
    # if os.path.exists(dotenv_path):
    #     load_dotenv(dotenv_path)
    # else:
    #     logger.error(f".envファイルが見つかりません: {dotenv_path}。テストを実行できません。")
    #     exit()

    # TEST_SA_KEY_JSON_CONTENT = os.getenv("YOUR_TEST_SA_KEY_JSON_CONTENT_ENV_VAR") # 例: .envにキーのJSON文字列を設定
    # TEST_FOLDER_ID = os.getenv("YOUR_TEST_GDRIVE_FOLDER_ID_ENV_VAR")

    # if not TEST_SA_KEY_JSON_CONTENT or not TEST_FOLDER_ID:
    #     logger.error("テスト用のサービスアカウントキーJSONコンテンツまたはフォルダIDが環境変数に設定されていません。")
    #     exit()

    # test_service = get_gdrive_service_from_json_key(TEST_SA_KEY_JSON_CONTENT)
    # if test_service:
    #     logger.info("テスト用Google Driveサービスオブジェクトの取得に成功。")
    #     # ここにアップロードテストなどを記述
    #     # test_local_file = "test_dummy.txt"
    #     # with open(test_local_file, "w") as f: f.write("Hello Drive from gdrive_utils test.")
    #     # uploaded = upload_file_to_drive(test_service, test_local_file, "gdrive_utils_standalone_test.txt", TEST_FOLDER_ID)
    #     # if uploaded: logger.info(f"テストアップロード成功: {uploaded.get('webViewLink')}")
    #     # if os.path.exists(test_local_file): os.remove(test_local_file)
    # else:
    #     logger.error("テスト用Google Driveサービスオブジェクトの取得に失敗。")

    logger.info("gdrive_utils.py の単体テスト処理（サンプル）を終了します。")