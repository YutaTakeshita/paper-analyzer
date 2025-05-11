# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 基本的なビルドツールとライブラリをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cmake \
      git \
      wget \
      ca-certificates \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
      autoconf \
      automake \
      libtool \
      pkg-config \
 && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /opt/pdfalto

# PDFalto のソースをクローンし、依存スクリプトを調整＆実行
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 && ./install_deps.sh

# ─── デバッグ: aconf.h の位置をビルドログに出力 ─────────────────
RUN echo "=== LOCATING aconf.h ===" \
 && find . -type f | grep aconf.h || echo "aconf.h not found"

# ─── ヘッダを適切な場所へコピー ─────────────────────────────
# （上記ログ出力を確認の上、正しいパスに書き換えてください）
RUN cp xpdf-4.03/xpdf/aconf.h /usr/include/ \
 && cp xpdf-4.03/xpdf/zconf.h /usr/include/

# ビルドディレクトリでコンパイル
RUN mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)"

# ビルド済みバイナリを取り出しやすく配置
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# envsubst 用シェルユーティリティをインストール
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

# 環境変数とポート設定を反映して起動
ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh", "-c", "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
