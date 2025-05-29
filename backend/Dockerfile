FROM python:3.11-slim AS runner
WORKDIR /app

# 必要なシステムパッケージをインストール (Pythonとpipはベースイメージに含まれる)
# Javaランタイムは不要になったため削除
# Google Cloud SDKも、PythonクライアントライブラリでGCPサービスにアクセスする場合は必須ではない
# もしgsutilなどを直接使いたい場合は残すが、通常はPythonライブラリで十分
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    # gnupg \ # SDKをインストールしないなら不要な場合が多い
    # apt-transport-https \ # SDKをインストールしないなら不要な場合が多い
    ca-certificates \
    default-jre-headless \
 && rm -rf /var/lib/apt/lists/*

# Google Cloud SDK のインストール部分はコメントアウトまたは削除
# RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
#  && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
#  && apt-get update -y && apt-get install -y google-cloud-sdk

# pipをアップグレード (任意だが推奨)
RUN pip install --upgrade pip

# CERMINE JAR関連の行は削除
# COPY jar/cermine-impl-1.13-jar-with-dependencies.jar /app/jar/cermine-impl-1.13-jar-with-dependencies.jar
# ENV CERMINE_JAR_PATH=/app/jar/cermine-impl-1.13-jar-with-dependencies.jar

# Python依存パッケージのインストール
COPY requirements.txt .
# --break-system-packages はPython 3.11以降では非推奨または不要な場合がある。
# ベースイメージがslimなので、システムパッケージとの衝突リスクは低い。
# 依存関係にある pdfplumber, Pillow, tabula-py[jpype] は requirements.txt に含めるのが一般的
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# entrypoint.sh と update_firestore_status.py の実行権限付与は不要になったため削除
# RUN chmod +x /app/entrypoint.sh \
#  && chmod +x /app/update_firestore_status.py

# ポートを公開 (Cloud Runでは$PORT環境変数が使われるので、EXPOSEはドキュメンテーション的な意味合いが強い)
EXPOSE 8080 

# FastAPIサーバを起動（main.pyのappオブジェクトを参照）
# $PORT 環境変数はCloud Runによって自動的に設定される (通常は8080)
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]