# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# ─────────────────────────────────────────────────────────────
# 1. 必要なビルドツールとライブラリをインストール
#    PDFalto をソースからビルドするために必要
# ─────────────────────────────────────────────────────────────
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      git \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
      gettext-base \
      wget \
 && rm -rf /var/lib/apt/lists/*

# ─────────────────────────────────────────────────────────────
# 2. PDFalto をサブモジュール込みでクローン＆ビルド
#    xpdf-4.03 サブディレクトリも含めて再帰的に取得し、
#    ビルド後バイナリを /usr/local/bin/ に配置
# ─────────────────────────────────────────────────────────────
WORKDIR /opt
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git \
 && cd pdfalto \
 && mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)" \
 && cp pdfalto_server /usr/local/bin/ \
 && cd /opt \
 && rm -rf pdfalto

# ─────────────────────────────────────────────────────────────
# 3. GROBID サービス用 JAR と設定／モデル類をコピー
# ─────────────────────────────────────────────────────────────
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home       /opt/grobid/grobid-home

# 環境変数設定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070
ENV ADMIN_PORT=8071

WORKDIR /opt/grobid

# 外部に公開するポート
EXPOSE 8070 8071

# ─────────────────────────────────────────────────────────────
# 4. コンテナ起動時コマンド
#    envsubst で設定ファイル中の ${PORT}, ${ADMIN_PORT} を置換し、
#    Dropwizard の server サブコマンドで起動
# ─────────────────────────────────────────────────────────────
ENTRYPOINT ["sh", "-c", \
  "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && \
   java -jar grobid-service.jar server /tmp/grobid.yaml" ]
