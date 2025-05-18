FROM python:3.11-slim AS runner
WORKDIR /app

# Javaランタイムとpipをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless python3-pip \
 && pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*

# ローカルのJARファイルをDockerコンテナ内にコピー
COPY ../jar/cermine-impl-1.13-jar-with-dependencies.jar /app/jar/cermine-impl-1.13-jar-with-dependencies.jar
ENV CERMINE_JAR_PATH=/app/jar/cermine-impl-1.13-jar-with-dependencies.jar

# Python依存パッケージのインストール
COPY ../requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt pdfplumber Pillow tabula-py[jpype]

# アプリケーションコードをコピー
COPY . .
# 必要であれば下記も有効化
# COPY templates ./templates
# COPY static ./static

# ポートを公開
EXPOSE 8080

# FastAPIサーバを起動（backend.main.py の app オブジェクトを参照）
CMD ["sh","-c","exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT"]