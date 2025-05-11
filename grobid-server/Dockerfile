# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

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
      libicu-dev \             # ← ICU 開発パッケージを追加
      autoconf \
      automake \
      libtool \
      pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pdfalto
# …（install_deps.sh 実行など）…

# ビルドディレクトリでコンパイル
RUN mkdir build && cd build \
 && cmake .. \
      -DUSE_SYSTEM_ICU=ON \            # ← システム ICU を明示的に指定
      -DICU_INCLUDE_DIR=/usr/include \
      -DICU_LIBRARY=/usr/lib/x86_64-linux-gnu/libicuuc.so \
      -DICU_I18N_LIBRARY=/usr/lib/x86_64-linux-gnu/libicui18n.so \
 && make -j"$(nproc)" \
 && cp pdfalto_server /usr/local/bin/pdfalto_server
 
# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/
COPY grobid-service.jar grobid-home /opt/grobid/

ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
