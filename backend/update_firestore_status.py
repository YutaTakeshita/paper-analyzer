# backend/update_firestore_status.py
import sys
import os
from google.cloud import firestore

def update_status(job_id: str, status_to_set: str, error_message: str = ""):
    """Firestoreのジョブステータスを更新する"""
    try:
        client = firestore.Client()
        doc_ref = client.collection("jobs").document(job_id)
        update_data = {"status": status_to_set}
        if error_message:
            update_data["errorMessage"] = error_message
        
        doc_ref.update(update_data)
        print(f"Python: Firestore status set to '{status_to_set}' for job_id='{job_id}' successfully.", file=sys.stderr if status_to_set == "failed" else sys.stdout)
        return 0
    except Exception as e:
        print(f"Python ERROR: Failed to set Firestore status to '{status_to_set}' for job_id='{job_id}'. ErrorType: {type(e).__name__}, Error: {e}", file=sys.stderr)
        return 1

def main():
    print("Python: update_firestore_status.py STARTED.", file=sys.stderr)

    dest_uri = os.environ.get('DEST_URI_FOR_PYTHON')
    job_status_to_set = os.environ.get('JOB_STATUS_TO_SET', 'done') # デフォルトは 'done'
    error_msg_from_shell = os.environ.get('ERROR_MESSAGE_FROM_SHELL', '')


    if not dest_uri and job_status_to_set == 'done': # 'done' の時だけ dest_uri が必須
        print("Python ERROR: DEST_URI_FOR_PYTHON environment variable not set for 'done' status.", file=sys.stderr)
        sys.exit(1)
    
    job_id_from_py = ""
    if dest_uri: # dest_uri があれば job_id を抽出
        try:
            file_name_with_ext = dest_uri.split('/')[-1]
            job_id_from_py = file_name_with_ext.split('.xml', 1)[0]
        except Exception as e_parse:
            print(f"Python ERROR: Failed to parse job_id from DEST_URI='{dest_uri}'. Error: {e_parse}", file=sys.stderr)
            # 'failed' ステータスを設定しようとしている場合は、job_idが取れなくても処理を試みる（job_idなしでエラーを記録）
            if job_status_to_set == 'failed' and not os.environ.get('JOB_ID_FOR_ERROR_TRAP'):
                 sys.exit(1) # JOB_ID_FOR_ERROR_TRAPもなければ諦める
            job_id_from_py = os.environ.get('JOB_ID_FOR_ERROR_TRAP', 'unknown_job_id_parse_error')

    # 'failed' ステータスの場合で、かつ job_id_from_py がまだ設定されていなければ、JOB_ID_FOR_ERROR_TRAP を使う
    if job_status_to_set == 'failed' and not job_id_from_py:
        job_id_from_py = os.environ.get('JOB_ID_FOR_ERROR_TRAP')
        if not job_id_from_py:
            print("Python ERROR: No job_id available to set 'failed' status.", file=sys.stderr)
            sys.exit(1) # job_id がどうしても取れない場合はエラー終了

    if not job_id_from_py: # 'done' の時、job_id がどうしても取れなかった場合
        print(f"Python ERROR: Extracted an empty job_id from DEST_URI='{dest_uri}'. Cannot set 'done' status.", file=sys.stderr)
        sys.exit(1)

    print(f"Python: Attempting to set status '{job_status_to_set}' for job_id='{job_id_from_py}'.", file=sys.stderr)
    
    exit_code = update_status(job_id_from_py, job_status_to_set, error_msg_from_shell)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()