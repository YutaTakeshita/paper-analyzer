FROM python:3.11-slim AS runner
WORKDIR /app

# Google Cloud SDK のインストールに必要なパッケージと Javaランタイム、pipをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    default-jre-headless \
    python3-pip \
 && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
 && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
 && apt-get update -y && apt-get install -y google-cloud-sdk \
 && pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*

# ローカルのJARファイルをDockerコンテナ内にコピー
COPY jar/cermine-impl-1.13-jar-with-dependencies.jar /app/jar/cermine-impl-1.13-jar-with-dependencies.jar
ENV CERMINE_JAR_PATH=/app/jar/cermine-impl-1.13-jar-with-dependencies.jar

# Python依存パッケージのインストール
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt pdfplumber Pillow tabula-py[jpype]

# アプリケーションコードをコピー
# この段階で backend ディレクトリ以下のファイル (main.py, entrypoint.sh, update_firestore_status.py, app/ など) が
# /app ディレクトリにコピーされることを想定しています。
# もし update_firestore_status.py が backend/app/ の中にある場合は、
# COPY app/update_firestore_status.py /app/app/update_firestore_status.py のように個別に指定するか、
# COPY . . で backend ディレクトリ全体を /app にコピーしていることを確認してください。
COPY . .

# entrypoint.sh と update_firestore_status.py に実行権限を付与
RUN chmod +x /app/entrypoint.sh \
 && chmod +x /app/update_firestore_status.py # <--- 追加 (もし直接実行しないなら不要な場合もある)

# ポートを公開
EXPOSE 8080

# FastAPIサーバを起動（main.pyのappオブジェクトを参照）
CMD ["sh","-c","exec uvicorn main:app --host 0.0.0.0 --port $PORT"]