FROM python:3.11-slim AS runner
WORKDIR /app

# 必要なシステムパッケージをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    default-jre-headless \
 && rm -rf /var/lib/apt/lists/*

# ★★★ JAVA_HOME 環境変数を設定 ★★★
# default-jre-headless (openjdk-17-jre-headless) の一般的なパスで、
# Cloud Build ログで update-alternatives が使用しているパスを参考にしています。
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# pipをアップグレード
RUN pip install --upgrade pip

# Python依存パッケージのインストール
COPY requirements.txt .
# ★★★ requirements.txt に jpype1 が記載されていることをご確認ください ★★★
# 例: jpype1>=1.0
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ポートを公開
EXPOSE 8080

# FastAPIサーバを起動
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]