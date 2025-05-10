# ─────────────────────────────────────────────────────────────
# Stage1: PDFalto ビルド
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential cmake git wget \
      libpoppler-dev libfreetype6-dev libfontconfig1-dev \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh

# ─── デバッグ用: スクリプト内部をトレースしつつ実行 ──────────────────
RUN echo "=== BEFORE INSTALL_DEPS ===" \
 && ls -R . \
 && echo "=== RUNNING install_deps.sh with -x ===" \
 # bash -x で全コマンド表示、かつ stdout/stderr をログに残す
 && bash -x ./install_deps.sh > /tmp/install.log 2>&1 \
 || (echo "=== INSTALL_DEPS FAILED: dump /tmp/install.log ===" \
     && sed -n '1,200p' /tmp/install.log \
     && false) \
 # ビルド
 && mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)" \
 \
 # バイナリ配置
 && cp pdfalto_server /usr/local/bin/

# ─────────────────────────────────────────────────────────────
# Stage 2: Final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home /opt/grobid/grobid-home

ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
