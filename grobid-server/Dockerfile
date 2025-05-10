# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 必要なビルドツールとライブラリを一括インストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      git \
      wget \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
      ca-certificates \
      autoconf \
      automake \
      libtool \
      pkg-config \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# PDFalto のソースをクローン
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && cd /opt/pdfalto \
 && sed -i 's/sudo //g' install_deps.sh \
 && ./install_deps.sh

# コンパイル＆バイナリをコピー
RUN mkdir build \
 && cd build \
 && cmake .. \
 && make -j"$(nproc)" \
 && cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# envsubst 用ユーティリティと CA 証明書をインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gettext-base \
      ca-certificates \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# PDFalto バイナリをビルドステージからコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# GROBID 用 JAR と設定をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home     /opt/grobid/grobid-home

# 起動時に環境変数を置換
ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
