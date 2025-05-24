#!/bin/bash

# エラーが発生したらスクリプトを終了する
set -eo pipefail

# ------------------------------------------------------------------------------
# 環境変数の設定 (必要に応じて値を変更してください)
# ------------------------------------------------------------------------------
# GCPプロジェクトID (gcloud config get-value project で現在の設定を取得)
PROJECT_ID_VAR=$(gcloud config get-value project)

# Artifact RegistryとCloud Runサービスのリージョン
REGION_VAR="asia-northeast1"

# Artifact Registryのリポジトリ名 (事前に作成しておく必要があります)
AR_REPOSITORY_VAR="cermine-repo" # 例: cermine, paper-analyzer-imagesなど

# Cloud Runサービス用のイメージ名
SERVICE_IMAGE_NAME_VAR="cermine-service"

# イメージタグ (ビルドごとにユニークな値を生成 - 例: YYYYMMDD-HHMMSS)
SERVICE_IMAGE_TAG_VAR=$(date +%Y%m%d-%H%M%S)

# 完全なイメージURI
SERVICE_IMAGE_URI_VAR="${REGION_VAR}-docker.pkg.dev/${PROJECT_ID_VAR}/${AR_REPOSITORY_VAR}/${SERVICE_IMAGE_NAME_VAR}:${SERVICE_IMAGE_TAG_VAR}"

# Cloud Runサービスの設定値 (必要に応じて変更)
SERVICE_PLATFORM_VAR="managed"
SERVICE_ALLOW_UNAUTHENTICATED_VAR="true" # true または false
SERVICE_MEMORY_VAR="2Gi"
SERVICE_TIMEOUT_VAR="300" # 秒単位

# ------------------------------------------------------------------------------
# 事前チェック (任意ですが推奨)
# ------------------------------------------------------------------------------
echo "------------------------------------"
echo "Deployment Configuration:"
echo "------------------------------------"
echo "Project ID:             ${PROJECT_ID_VAR}"
echo "Region:                 ${REGION_VAR}"
echo "Artifact Repository:    ${AR_REPOSITORY_VAR}"
echo "Service Image Name:     ${SERVICE_IMAGE_NAME_VAR}"
echo "Service Image Tag:      ${SERVICE_IMAGE_TAG_VAR}"
echo "Full Service Image URI: ${SERVICE_IMAGE_URI_VAR}"
echo "------------------------------------"
read -p "上記の設定でデプロイを開始しますか？ (y/N): " confirmation
if [[ "$confirmation" != "y" && "$confirmation" != "Y" ]]; then
    echo "デプロイメントがキャンセルされました。"
    exit 0
fi

# ------------------------------------------------------------------------------
# 1. DockerイメージのビルドとArtifact Registryへのプッシュ
# ------------------------------------------------------------------------------
echo ""
echo "ステップ1: Dockerイメージをビルドし、Artifact Registryにプッシュします..."
echo "イメージURI: ${SERVICE_IMAGE_URI_VAR}"

gcloud builds submit . \
    --tag "${SERVICE_IMAGE_URI_VAR}" \
    --project "${PROJECT_ID_VAR}"

if [ $? -ne 0 ]; then
    echo "エラー: Dockerイメージのビルドまたはプッシュに失敗しました。"
    exit 1
fi
echo "ステップ1完了: イメージのビルドとプッシュが成功しました。"

# ------------------------------------------------------------------------------
# 2. Cloud Runサービス (cermine-service) のデプロイ/更新
# ------------------------------------------------------------------------------
echo ""
echo "ステップ2: Cloud Runサービス '${SERVICE_IMAGE_NAME_VAR}' を更新/デプロイします..."
echo "使用イメージ: ${SERVICE_IMAGE_URI_VAR}"

# --allow-unauthenticated フラグの処理
allow_unauthenticated_flag=""
if [ "${SERVICE_ALLOW_UNAUTHENTICATED_VAR}" = "true" ]; then
    allow_unauthenticated_flag="--allow-unauthenticated"
fi

gcloud run deploy "${SERVICE_IMAGE_NAME_VAR}" \
    --image "${SERVICE_IMAGE_URI_VAR}" \
    --platform "${SERVICE_PLATFORM_VAR}" \
    --region "${REGION_VAR}" \
    ${allow_unauthenticated_flag} \
    --memory "${SERVICE_MEMORY_VAR}" \
    --timeout "${SERVICE_TIMEOUT_VAR}" \
    --project "${PROJECT_ID_VAR}"
    # 他に必要なフラグがあればここに追加してください。
    # 例: --update-env-vars=KEY1=VALUE1,KEY2=VALUE2
    # 例: --service-account=your-service-account@your-project.iam.gserviceaccount.com

if [ $? -ne 0 ]; then
    echo "エラー: Cloud Runサービス '${SERVICE_IMAGE_NAME_VAR}' のデプロイ/更新に失敗しました。"
    exit 1
fi
echo "ステップ2完了: Cloud Runサービス '${SERVICE_IMAGE_NAME_VAR}' が正常に更新/デプロイされました。"
echo ""
echo "デプロイメントプロセスが完了しました。"