# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# 必要なビルドツールとライブラリをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      git \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
 && rm -rf /var/lib/apt/lists/*

# PDFalto のソースをクローンしてビルド
WORKDIR /opt
RUN git clone https://github.com/kermitt2/pdfalto.git \
 && cd pdfalto \
 && mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)" \
 && cp pdfalto_server /usr/local/bin/ \
 && cd /opt \
 && rm -rf pdfalto

# GROBID 用ディレクトリ構造を作成
WORKDIR /opt/grobid
COPY grobid-service.jar ./grobid-service.jar
COPY grobid-home ./grobid-home

# ポートは Dropwizard の server サブコマンドで指定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070
EXPOSE ${PORT}

# エントリーポイント：設定ファイルを使ってサーバ起動
ENTRYPOINT ["sh", "-c", "java -jar grobid-service.jar server ${GROBID_HOME}/config/grobid.yaml"]
