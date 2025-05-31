#!/bin/bash

# エラーが発生したらスクリプトを終了する
set -eo pipefail

# ------------------------------------------------------------------------------
# 環境変数の設定 (GROBIDサービス用)
# ------------------------------------------------------------------------------
# GCPプロジェクトIDを明示的に設定
PROJECT_ID_VAR="grobid-461112"
if [ -z "${PROJECT_ID_VAR}" ]; then
  echo "エラー: GCPプロジェクトIDがスクリプト内で設定されていません。"
  exit 1
fi
echo "使用するGCPプロジェクトID: ${PROJECT_ID_VAR}"

# Artifact RegistryとCloud Runサービスのリージョン (GCP用)
GCP_REGION_VAR="asia-northeast1"
# Artifact Registryのリポジトリ名 (GROBIDイメージが保存されているリポジトリ)
AR_REPOSITORY_VAR="grobid-images"
# Cloud Runサービス用のサービス名
SERVICE_NAME_VAR="grobid-service"
# ★★★ 使用するGROBIDイメージのタグ ★★★
# 最新の安定版 (0.8.2) を指定する場合の例。必要に応じて変更してください。
# SERVICE_IMAGE_TAG_VAR="0.8.2"
# もし "latest-full" を引き続き使用する場合はそのままでOK
SERVICE_IMAGE_TAG_VAR="latest-full"

# Artifact Registry内のイメージ名
# スクリーンショットと以前の会話から "grobid-server" と判断
ARTIFACT_IMAGE_NAME_VAR="grobid-server"

# 完全なイメージURI
# 変数展開を修正
SERVICE_IMAGE_URI_VAR="${GCP_REGION_VAR}-docker.pkg.dev/${PROJECT_ID_VAR}/${AR_REPOSITORY_VAR}/${ARTIFACT_IMAGE_NAME_VAR}:${SERVICE_IMAGE_TAG_VAR}"

# Cloud Runサービスの設定値 (grobid-service に合わせて調整)
SERVICE_PLATFORM_VAR="managed"
SERVICE_ALLOW_UNAUTHENTICATED_VAR="true" # 公開APIとして運用する場合
SERVICE_MEMORY_VAR="8Gi"                 # メモリを8GiBに増やした設定
SERVICE_CPU_VAR="4"                      # CPUを4に増やした設定
SERVICE_TIMEOUT_VAR="600"                # GROBIDサービスのタイムアウト (秒)
SERVICE_PORT_VAR="8070"                  # GROBIDコンテナがリッスンするポート
SERVICE_CONCURRENCY_VAR="10"             # GROBIDサービスの推奨同時実行数 (リソースに応じて調整)
MIN_INSTANCES_VAR="0"                    # コールドスタートを許容する場合は0、避ける場合は1以上

# ------------------------------------------------------------------------------
# 事前チェック
# ------------------------------------------------------------------------------
echo "------------------------------------"
echo "Deployment Configuration (GROBID Service):"
echo "------------------------------------"
echo "Project ID:             ${PROJECT_ID_VAR}"
echo "GCP Region:             ${GCP_REGION_VAR}"
echo "Artifact Repository:    ${AR_REPOSITORY_VAR}"
echo "Artifact Image Name:    ${ARTIFACT_IMAGE_NAME_VAR}"
echo "Service Name:           ${SERVICE_NAME_VAR}"
echo "Service Image Tag:      ${SERVICE_IMAGE_TAG_VAR}"
echo "Full Service Image URI: ${SERVICE_IMAGE_URI_VAR}" # ここで正しく展開されるか確認
echo "Memory:                 ${SERVICE_MEMORY_VAR}"
echo "CPU:                    ${SERVICE_CPU_VAR}"
echo "Timeout:                ${SERVICE_TIMEOUT_VAR}s"
echo "Port:                   ${SERVICE_PORT_VAR}"
echo "Concurrency:            ${SERVICE_CONCURRENCY_VAR}"
echo "Min Instances:          ${MIN_INSTANCES_VAR}"
echo "------------------------------------"
read -p "上記の設定でGROBIDサービスをデプロイ/更新しますか？ (y/N): " confirmation
if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
  echo "デプロイメントがキャンセルされました。"
  exit 0
fi

# ------------------------------------------------------------------------------
# 1. DockerイメージがArtifact Registryに存在することを確認
# ------------------------------------------------------------------------------
echo ""
echo "ステップ1: Artifact Registryでイメージ ${SERVICE_IMAGE_URI_VAR} が利用可能であることを確認してください。"
echo "もしイメージをまだプッシュしていない場合は、先に以下の手順などでプッシュ作業を行ってください："
echo "  1. docker pull lfoppiano/grobid:${SERVICE_IMAGE_TAG_VAR} (または対象のイメージ)"
echo "  2. docker tag lfoppiano/grobid:${SERVICE_IMAGE_TAG_VAR} ${SERVICE_IMAGE_URI_VAR}"
echo "  3. gcloud auth configure-docker ${GCP_REGION_VAR}-docker.pkg.dev (必要に応じて)"
echo "  4. docker push ${SERVICE_IMAGE_URI_VAR}"
read -p "指定されたイメージはArtifact Registryにプッシュ済みですか？ (y/N): " image_ready_confirmation
if [[ "$image_ready_confirmation" != "y" && "$image_ready_confirmation" != "Y" ]]; then
  echo "イメージの準備ができていないため、デプロイを中止します。"
  exit 0
fi

# ------------------------------------------------------------------------------
# 2. Cloud Runサービス のデプロイ/更新
# ------------------------------------------------------------------------------
echo ""
echo "ステップ2: Cloud Runサービス '${SERVICE_NAME_VAR}' を更新/デプロイします..."
echo "使用イメージ: ${SERVICE_IMAGE_URI_VAR}" # ここでも正しく展開されるか確認

allow_unauthenticated_flag=""
if [ "${SERVICE_ALLOW_UNAUTHENTICATED_VAR}" = "true" ]; then
  allow_unauthenticated_flag="--allow-unauthenticated"
fi

min_instances_flag=""
if [ "${MIN_INSTANCES_VAR}" -gt "0" ]; then
  min_instances_flag="--min-instances ${MIN_INSTANCES_VAR}"
fi

# gcloud run deploy コマンド
# 各オプションが正しく展開され、1行に連結されるように注意
# バックスラッシュによる行継続を使用する場合は、\ の直後に改行のみを置く
gcloud run deploy "${SERVICE_NAME_VAR}" \
  --image "${SERVICE_IMAGE_URI_VAR}" \
  --platform "${SERVICE_PLATFORM_VAR}" \
  --region "${GCP_REGION_VAR}" \
  ${allow_unauthenticated_flag} \
  --memory "${SERVICE_MEMORY_VAR}" \
  --cpu "${SERVICE_CPU_VAR}" \
  --timeout "${SERVICE_TIMEOUT_VAR}s" \
  --port "${SERVICE_PORT_VAR}" \
  --concurrency "${SERVICE_CONCURRENCY_VAR}" \
  ${min_instances_flag} \
  --project "${PROJECT_ID_VAR}"

if [ $? -ne 0 ]; then
  echo "エラー: Cloud Runサービス '${SERVICE_NAME_VAR}' のデプロイ/更新に失敗しました。"
  exit 1
fi

echo "ステップ2完了: Cloud Runサービス '${SERVICE_NAME_VAR}' が正常に更新/デプロイされました。"

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME_VAR}" \
  --platform managed \
  --region "${GCP_REGION_VAR}" \
  --project "${PROJECT_ID_VAR}" \
  --format 'value(status.url)')

echo "サービスURL: ${SERVICE_URL}"
echo ""
echo "デプロイメントプロセスが完了しました。"
