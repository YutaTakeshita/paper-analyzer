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

# PDFalto のソースをクローンし、依存スクリプトをデバッグ実行
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 # デバッグ用にシェルの実行ログを残す
 && echo "=== RUNNING install_deps.sh with debug xtrace ===" \
 && bash -x ./install_deps.sh \
 || (echo "=== install_deps.sh FAILED, dumping first 200 lines ===" && sed -n '1,200p' /tmp/install_deps.log && false)

# xpdf-4.03 のヘッダを手動でインクルードパスにコピー
RUN cp xpdf-4.03/config/aconf.h /usr/include/ \
 && cp xpdf-4.03/config/zconf.h /usr/include/

# ビルドディレクトリでコンパイル（こちらもデバッグ出力付き）
RUN mkdir build && cd build \
 && cmake .. -DCMAKE_CXX_FLAGS="-I/usr/include -g" \
 && make -j"$(nproc)" VERBOSE=1

# ビルド済みバイナリを取り出しやすく配置
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image with debug logging enabled
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

# デフォルトログレベルを DEBUG に設定できるよう
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV LOG_LEVEL=DEBUG

# 起動時に envsubst とともに JVM オプションでデバッグ出力を有効化
ENTRYPOINT ["sh", "-c", "\
  echo \"Starting GROBID with LOG_LEVEL=${LOG_LEVEL}\"; \
  envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml; \
  exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL} \
            -Ddw.serverConfigResource=/tmp/grobid.yaml \
            -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
