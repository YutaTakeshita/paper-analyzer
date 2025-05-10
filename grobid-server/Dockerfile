# ──────────────────────────────────────────────────────────────
# GROBID 0.8.0 + arm64 PDFalto （Science-Miner 公開版）同梱
# Render / Apple Silicon 向け
# ──────────────────────────────────────────────────────────────
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# 1) arm64版 pdfalto_server を取得して配置
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64 && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 2) GROBID 本体＋profiles/default.properties をコピー
#    （Docker ビルドコンテキストは grobid-server 以下を想定）
COPY grobid-home      /opt/grobid/grobid-home
COPY grobid-service/profiles /opt/grobid/grobid-service/profiles

# 3) 必要なら追加のモデルや設定 override
# COPY grobid-home/models      /opt/grobid/grobid-home/models
# COPY grobid-home/config/...  /opt/grobid/grobid-home/config/...

# 4) ポート公開
ENV PORT=8070
EXPOSE ${PORT}

# 5) Entrypoint：プロファイル設定を直接指定
ENTRYPOINT [
  "/opt/grobid/grobid-service/bin/grobid-service",
  "server",
  "/opt/grobid/grobid-service/profiles/default.properties"
]
