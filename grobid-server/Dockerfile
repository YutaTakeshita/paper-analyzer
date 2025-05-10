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
      autoconf \
      automake \
      libtool \
      pkg-config \
 && rm -rf /var/lib/apt/lists/*

# ソースをクローンし、install_deps.sh 内の不要処理を除去して実行
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/s/^/#/' install_deps.sh \
 && ./install_deps.sh

# ビルド
RUN mkdir build \
 && cd build \
 && cmake .. \
 && make -j"$(nproc)"

# ビルド済みバイナリを別ステージに渡す
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# envsubst 用ユーティリティをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリ
WORKDIR /opt/grobid

# PDFalto バイナリをコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# GROBID 本体をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home /opt/grobid/grobid-home

# 設定ファイルのパス置換＆起動
ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
