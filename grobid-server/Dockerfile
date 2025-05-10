# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# 不要なパッケージは省いて軽量化
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base wget \
 && rm -rf /var/lib/apt/lists/*

# Grobid 用ディレクトリを作成
WORKDIR /opt/grobid

# pdfalto_server を Render（amd64 Linux）用バイナリで配置
RUN wget -O /usr/local/bin/pdfalto_server \
      https://github.com/kermitt2/pdfalto/releases/download/0.4/pdfalto_server-linux-amd64 \
 && chmod +x /usr/local/bin/pdfalto_server

# ビルド済みJarをコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar

# GROBID-HOME 配下を丸ごとコピー（config 以下を含む）
COPY grobid-home /opt/grobid/grobid-home

# 環境変数設定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070
ENV ADMIN_PORT=8071

EXPOSE ${PORT} ${ADMIN_PORT}

# Dropwizard の server サブコマンドに設定ファイルを渡す
ENTRYPOINT ["sh", "-c", "java -jar grobid-service.jar server ${GROBID_HOME}/config/grobid.yaml"]
