FROM python:3.11-slim AS runner
WORKDIR /app

# Javaランタイムとpipをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless python3-pip \
 && pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*

# ローカルのJARファイルをDockerコンテナ内にコピー
COPY jar/cermine-impl-1.13-jar-with-dependencies.jar /app/jar/cermine-impl-1.13-jar-with-dependencies.jar
ENV CERMINE_JAR_PATH=/app/jar/cermine-impl-1.13-jar-with-dependencies.jar

# Python依存パッケージのインストール
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt pdfplumber Pillow tabula-py[jpype]

# アプリケーションコードをコピー
COPY . .

# ポートを公開
EXPOSE 8080

# FastAPIサーバを起動（main.pyのappオブジェクトを参照）
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port $PORT"]