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

# PDFalto のソースをクローンし、依存スクリプトを実行
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 # root 実行なので sudo は不要
 && sed -i 's/sudo //g' install_deps.sh \
 # xpdfrc コピー処理を削除
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 && ./install_deps.sh

# aconf.h が xpdf-4.03 サブモジュール内にあるので、インクルードパスにコピー
RUN cp xpdf-4.03/config/aconf.h /usr/include/ \
 && cp xpdf-4.03/config/zconf.h /usr/include/

# ビルドディレクトリでコンパイル
RUN mkdir build && cd build \
 && cmake .. -DCMAKE_CXX_FLAGS="-I/usr/include" \
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
