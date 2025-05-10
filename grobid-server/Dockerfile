# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 必要なビルドツールとライブラリをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      git \
      wget \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
 && rm -rf /var/lib/apt/lists/*

# PDFalto のソースをクローンし、依存スクリプトを実行（install_deps.sh 内の sudo はすべて削除済み）
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && ./install_deps.sh

# ビルドディレクトリでコンパイル
RUN mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)"

# ビルド済みバイナリを次ステージにコピーしやすい場所へ配置
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# envsubst 用ユーティリティをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /opt/grobid

# PDFalto サーババイナリをビルドステージからコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# GROBID の JAR とホームフォルダをコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home /opt/grobid/grobid-home

# 環境変数設定
ENV GROBID_HOME=/opt/grobid/grobid-home

# ポート設定など環境変数を置換して起動
ENTRYPOINT ["sh", "-c", "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
