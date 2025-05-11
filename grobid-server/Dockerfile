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
      ca-certificates \
      libpoppler-dev \
      libfreetype6-dev \
      libfontconfig1-dev \
      libicu-dev \                   
      autoconf \
      automake \
      libtool \
      pkg-config \
 && rm -rf /var/lib/apt/lists/*

# PDFalto のソースをクローンし、install_deps.sh を実行
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 && ./install_deps.sh

# ビルドディレクトリを作成し、CMake に ICU のパスを伝えてビルド
RUN mkdir build && cd build \
 && cmake .. \
      -DCMAKE_CXX_FLAGS="-I/usr/include" \
      -DICU_INCLUDE_DIR=/usr/include \
      -DICU_LIBRARY=/usr/lib/x86_64-linux-gnu/libicuuc.so \
 && make -j"$(nproc)"

# ビルド済みバイナリを最終ステージへコピーしやすく配置
RUN cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# envsubst 用ユーティリティをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# PDFalto バイナリをコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# GROBID サービス本体をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home       /opt/grobid/grobid-home

# 起動時に環境変数を YAML に埋め込んで実行
ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh", "-c", "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && exec java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
