# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# 必要なパッケージのインストール（envsubst 用 gettext-base と pdfalto_server 用 wget）
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gettext-base \
      wget \
 && rm -rf /var/lib/apt/lists/*

# pdfalto_server を Render（amd64 Linux）用バイナリで配置
RUN wget -O /usr/local/bin/pdfalto_server \
      https://github.com/kermitt2/pdfalto/releases/download/vX.Y.Z/pdfalto_server-linux-amd64 \
 && chmod +x /usr/local/bin/pdfalto_server

# ビルド済みJarをコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar

# GROBID-HOMEフォルダを丸ごとコピー（config 以下を含む）
COPY grobid-home /opt/grobid/grobid-home

# 環境変数設定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070
ENV ADMIN_PORT=8071

WORKDIR /opt/grobid

# ポート開放
EXPOSE ${PORT} ${ADMIN_PORT}

# 起動時に設定ファイル内の ${PORT}/${ADMIN_PORT} を展開し、一時ファイル経由で Dropwizard に渡す
ENTRYPOINT ["sh", "-c", "envsubst < ${GROBID_HOME}/config/grobid.yaml > /tmp/grobid.yaml && java -Dorg.grobid.config=/tmp/grobid.yaml -jar grobid-service.jar server /tmp/grobid.yaml"]
