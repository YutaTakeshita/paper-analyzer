###############################################################################
# GROBID 0.8.0  (arm64 pdfalto 同梱版)  Cloud Run / Apple Silicon 用
###############################################################################
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# ---- 1. arm64 版 pdfalto_server 取得（Science‑Miner 公開ビルド）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64 && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# ---- 2. JVM オプション：pdfalto の場所を統一
ENV PORT=8070
ENV JAVA_TOOL_OPTIONS="-Xms512m -Xmx2g \
  -Dorg.grobid.config=/opt/grobid/grobid-home/config/grobid.yaml \
  -Dgrobid.pdf.pdfalto.path=/usr/local/bin/pdfalto_server \
  -Dorg.grobid.pdf2xml.path=/usr/local/bin/pdfalto_server \
  -Ddw.server.applicationConnectors[0].port=${PORT} \
  -Ddw.server.adminConnectors[0].port=8071"

EXPOSE ${PORT}

# ---- 3. 追加のモデルや設定をコピーしたい場合はここで
# COPY grobid-home/models /opt/grobid/grobid-home/models
# COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml

# ---- 4. 0.8.0 には grobid ラッパースクリプトが入っている
ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]