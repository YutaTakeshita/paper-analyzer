# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source with install_deps.sh
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

# PDFalto のソースをクローンし、依存関係をインストールするスクリプトでセットアップ
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && ./install_deps.sh

# ビルドディレクトリでコンパイル
WORKDIR /opt/pdfalto
RUN mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)"

# ビルド済みバイナリを外へコピー
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server


# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# 簡易シェルユーティリティをインストール（envsubst 用）
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

# 環境変数のデフォルトを設定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070
ENV ADMIN_PORT=8071

# ポート設定など環境変数を置換してから起動
ENTRYPOINT ["sh","-c", "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
