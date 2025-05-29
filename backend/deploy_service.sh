#!/bin/bash

# エラーが発生したらスクリプトを終了する
set -eo pipefail

# ------------------------------------------------------------------------------
# 環境変数の設定 (必要に応じて値を変更してください)
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

# AWSサービス用のリージョン名 (boto3が期待する形式)
AWS_SDK_REGION_VAR="ap-northeast-1"

# Artifact Registryのリポジトリ名
AR_REPOSITORY_VAR="paper-analyzer-backend-repo" 

# Cloud Runサービス用のサービス名
SERVICE_NAME_VAR="paper-analyzer-backend" 

# イメージタグ
SERVICE_IMAGE_TAG_VAR=$(date +%Y%m%d-%H%M%S)

# 完全なイメージURI
SERVICE_IMAGE_URI_VAR="${GCP_REGION_VAR}-docker.pkg.dev/${PROJECT_ID_VAR}/${AR_REPOSITORY_VAR}/${SERVICE_NAME_VAR}:${SERVICE_IMAGE_TAG_VAR}"

# Cloud Runサービスの設定値
SERVICE_PLATFORM_VAR="managed"
SERVICE_ALLOW_UNAUTHENTICATED_VAR="true" 
SERVICE_MEMORY_VAR="1Gi"                 
SERVICE_CPU_VAR="1"                      
SERVICE_TIMEOUT_VAR="600"                
SERVICE_CONCURRENCY_VAR="80"             

ENVIRONMENT_VARIABLES="GROBID_SERVICE_URL=https://grobid-service-974272343256.asia-northeast1.run.app/api/processFulltextDocument"
ENVIRONMENT_VARIABLES+=",GCP_PROJECT=${PROJECT_ID_VAR}"
ENVIRONMENT_VARIABLES+=",AWS_REGION=${AWS_SDK_REGION_VAR}" 
ENVIRONMENT_VARIABLES+=",OPENAI_SUMMARY_MODEL=gpt-4.1-mini" 
ENVIRONMENT_VARIABLES+=",AWS_POLLY_VOICE_ID=Tomoko"      

SERVICE_ACCOUNT_EMAIL="paper-analyzer-backend-sa@${PROJECT_ID_VAR}.iam.gserviceaccount.com"

# ------------------------------------------------------------------------------
# 事前チェック
# ------------------------------------------------------------------------------
echo "------------------------------------"
echo "Deployment Configuration (Backend Application):"
echo "------------------------------------"
echo "Project ID:             ${PROJECT_ID_VAR}"
echo "GCP Region:             ${GCP_REGION_VAR}"
echo "AWS SDK Region:         ${AWS_SDK_REGION_VAR}"
echo "Artifact Repository:    ${AR_REPOSITORY_VAR}"
echo "Service Name:           ${SERVICE_NAME_VAR}"
echo "Service Image Tag:      ${SERVICE_IMAGE_TAG_VAR}"
echo "Full Service Image URI: ${SERVICE_IMAGE_URI_VAR}"
echo "Memory:                 ${SERVICE_MEMORY_VAR}"
echo "CPU:                    ${SERVICE_CPU_VAR}"
echo "Timeout:                ${SERVICE_TIMEOUT_VAR}s"
echo "Service Account:        ${SERVICE_ACCOUNT_EMAIL}"
echo "Environment Variables:  ${ENVIRONMENT_VARIABLES}"
echo "------------------------------------"
read -p "上記の設定でバックエンドアプリケーションのデプロイを開始しますか？ (y/N): " confirmation
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
# 2. Cloud Runサービス のデプロイ/更新
# ------------------------------------------------------------------------------
echo ""
echo "ステップ2: Cloud Runサービス '${SERVICE_NAME_VAR}' を更新/デプロイします..."
echo "使用イメージ: ${SERVICE_IMAGE_URI_VAR}"

allow_unauthenticated_flag=""
if [ "${SERVICE_ALLOW_UNAUTHENTICATED_VAR}" = "true" ]; then
    allow_unauthenticated_flag="--allow-unauthenticated"
fi

# ★ コメントをコマンド引数の行から分離
gcloud run deploy "${SERVICE_NAME_VAR}" \
    --image "${SERVICE_IMAGE_URI_VAR}" \
    --platform "${SERVICE_PLATFORM_VAR}" \
    --region "${GCP_REGION_VAR}" \
    ${allow_unauthenticated_flag} \
    --memory "${SERVICE_MEMORY_VAR}" \
    --cpu "${SERVICE_CPU_VAR}" \
    --timeout "${SERVICE_TIMEOUT_VAR}" \
    --concurrency "${SERVICE_CONCURRENCY_VAR}" \
    --service-account="${SERVICE_ACCOUNT_EMAIL}" \
    --set-env-vars "${ENVIRONMENT_VARIABLES}" \
    --project "${PROJECT_ID_VAR}"
    # ポートはDockerfileのCMDで$PORTを参照していれば自動的に8080が使われることが多いので指定は任意
    # --port 8080 

if [ $? -ne 0 ]; then
    echo "エラー: Cloud Runサービス '${SERVICE_NAME_VAR}' のデプロイ/更新に失敗しました。"
    exit 1
fi
echo "ステップ2完了: Cloud Runサービス '${SERVICE_NAME_VAR}' が正常に更新/デプロイされました。"
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME_VAR}" --platform managed --region "${GCP_REGION_VAR}" --project "${PROJECT_ID_VAR}" --format 'value(status.url)')
echo "サービスURL: ${SERVICE_URL}"
echo ""
echo "デプロイメントプロセスが完了しました。"