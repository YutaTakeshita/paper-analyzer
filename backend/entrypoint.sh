#!/usr/bin/env bash

set -eo pipefail

: "${CERMINE_JAR_PATH:?Environment variable CERMINE_JAR_PATH must be set}"

if [ -z "$1" ]; then
  echo "ERROR: Usage: entrypoint.sh gs://bucket/file.pdf" >&2
  exit 1
fi

PDF_URI="$1"
TMP_DIR=$(mktemp -d)

# PDF_URIからjob_idを抽出 (エラー発生時のFirestore更新で使用)
# gs://bucket/path/to/filename.pdf -> filename
JOB_ID_FOR_ERROR_TRAP=""
if [ -n "${PDF_URI}" ]; then
    TEMP_FILENAME="${PDF_URI##*/}" # filename.pdf
    JOB_ID_FOR_ERROR_TRAP="${TEMP_FILENAME%.pdf}" # filename
fi
echo "INFO: Initial job_id for error trapping: ${JOB_ID_FOR_ERROR_TRAP}" >&2


cleanup_and_set_error_status() {
  EXIT_CODE=$?
  echo "INFO: Trap received exit code ${EXIT_CODE}. Cleaning up ${TMP_DIR}..." >&2
  rm -rf "${TMP_DIR}"

  # 0以外のエラーコードで、かつJOB_ID_FOR_ERROR_TRAPが空でない場合のみFirestoreを'failed'に更新
  if [ "${EXIT_CODE}" -ne 0 ] && [ -n "${JOB_ID_FOR_ERROR_TRAP}" ]; then
    echo "ERROR: Job failed. Attempting to set Firestore status to 'failed' for job_id: ${JOB_ID_FOR_ERROR_TRAP}" >&2
    
    # 環境変数を設定してPythonスクリプトを呼び出す
    export JOB_ID_FOR_ERROR_TRAP # Python側でこれを参照する
    export JOB_STATUS_TO_SET="failed"
    export ERROR_MESSAGE_FROM_SHELL="Job failed with exit code ${EXIT_CODE} at shell level."
    
    # update_firestore_status.py は /app ディレクトリにあると仮定
    if python3 /app/update_firestore_status.py; then
      echo "INFO: Firestore status 'failed' update attempt finished (via trap)." >&2
    else
      echo "ERROR: Python script for setting 'failed' status itself failed (via trap)." >&2
    fi
  fi
  echo "INFO: Trap cleanup finished." >&2
}
# スクリプト終了時(正常・異常問わず)に cleanup_and_set_error_status を実行
trap cleanup_and_set_error_status EXIT


echo "INFO: Starting job for PDF: ${PDF_URI}" >&2
echo "INFO: Temporary directory: ${TMP_DIR}" >&2

echo "INFO: Copying ${PDF_URI} to ${TMP_DIR} ..." >&2
gsutil cp "${PDF_URI}" "${TMP_DIR}/"
echo "INFO: PDF copy complete." >&2

echo "INFO: Running CERMINE ..." >&2
java -jar "$CERMINE_JAR_PATH" \
     -path "${TMP_DIR}" \
     -outputs jats
echo "INFO: CERMINE execution finished." >&2

# CERMINE実行後のファイルリスト表示 (デバッグ用、必要ならコメントアウト)
echo "DEBUG: Listing contents of ${TMP_DIR} after CERMINE:" >&2
ls -la "${TMP_DIR}" >&2

OUT_XML_PATH=""
for ext in cermxml jats.xml xml nxml; do
    found_file=$(find "${TMP_DIR}" -maxdepth 1 -type f -name "*.${ext}" -print -quit)
    if [ -n "${found_file}" ]; then
        OUT_XML_PATH="${found_file}"
        break
    fi
done

if [ -z "${OUT_XML_PATH}" ] || [ ! -f "${OUT_XML_PATH}" ]; then
  echo "ERROR: Output XML/CERMXML file not found in ${TMP_DIR} after CERMINE execution." >&2
  exit 1 # trap がエラー処理を行う
fi
echo "INFO: Found output file: ${OUT_XML_PATH}" >&2

# GCSのアップロード先URIを構築
PDF_FILENAME_WITHOUT_EXT="${PDF_URI##*/}"
PDF_FILENAME_WITHOUT_EXT="${PDF_FILENAME_WITHOUT_EXT%.pdf}"
DEST_URI_FILENAME="${PDF_FILENAME_WITHOUT_EXT}.xml"
PDF_DIR_PATH=${PDF_URI%/*}/
DEST_URI="${PDF_DIR_PATH}${DEST_URI_FILENAME}"
echo "INFO: Destination URI for GCS upload is '${DEST_URI}'" >&2

echo "INFO: Uploading ${OUT_XML_PATH} to ${DEST_URI} ..." >&2
gsutil cp "${OUT_XML_PATH}" "${DEST_URI}"
echo "INFO: GCS upload complete." >&2

# 正常完了時のFirestoreステータス更新
echo "INFO: Executing Python script to update Firestore status to 'done' for ${DEST_URI}..." >&2
export DEST_URI_FOR_PYTHON="${DEST_URI}" # Pythonスクリプトがこれを読み取る
export JOB_STATUS_TO_SET="done"
export ERROR_MESSAGE_FROM_SHELL="" # 正常時はエラーメッセージなし

# update_firestore_status.py は /app ディレクトリにあると仮定
if ! python3 /app/update_firestore_status.py; then
    echo "ERROR: Python script for setting 'done' status failed." >&2
    # この場合、trapがEXIT_CODEを見て 'failed' にしようとする (Pythonスクリプトが非0で終了した場合)
    exit 1 # 明示的にエラーで終了
fi

echo "INFO: ✅ Job finished successfully for ${PDF_URI}." >&2
# trapが実行されるが、ここでの終了コードは0なので、'failed'にはならない