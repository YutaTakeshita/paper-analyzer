#!/usr/bin/env bash

set -eo pipefail

# Ensure CERMINE_JAR_PATH is set (defaults to /app/cermine-impl-1.13-jar-with-dependencies.jar)
: "${CERMINE_JAR_PATH:?Environment variable CERMINE_JAR_PATH must be set}"

if [ -z "$1" ]; then
  echo "Usage: entrypoint.sh gs://bucket/file.pdf"
  exit 1
fi

PDF_URI="$1"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Copying ${PDF_URI} ..."
gsutil cp "${PDF_URI}" "${TMP_DIR}/"

echo "Running CERMINE ..."
java -jar "$CERMINE_JAR_PATH" \
     -path "${TMP_DIR}" \
     -outputs jats

OUT_XML=$(ls "${TMP_DIR}"/*.xml | head -n 1)
if [ ! -f "${OUT_XML}" ]; then
  echo "JATS output not found—conversion failed."
  exit 1
fi

DEST_URI="${PDF_URI%.pdf}.xml"
echo "Uploading to ${DEST_URI} ..."
gsutil cp "${OUT_XML}" "${DEST_URI}"

# Firestoreステータスをdoneに更新（失敗時は即終了・エラー内容も表示）
python3 - <<EOF
from google.cloud import firestore
import sys
job_id="${DEST_URI##*/}"
job_id="${job_id%.xml}"
try:
    firestore.Client().collection("jobs").document(job_id).update({"status":"done"})
    print("Firestore update: success")
except Exception as e:
    print("Firestore update: failed", e, file=sys.stderr)
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
  echo "❌ Firestore status update failed"
  exit 1
fi

echo "✅ Finished successfully."