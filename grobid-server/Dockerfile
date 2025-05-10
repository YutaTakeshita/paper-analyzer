# ────────────────────────────────────────────────────
# Render (x86_64) 向け：GROBID 0.8.0 + PDFalto x86_64
# ────────────────────────────────────────────────────
FROM --platform=linux/amd64 lfoppiano/grobid:0.8.0
USER root

# PDFalto x86_64 バイナリを取得して配置
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-x86_64 && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# GROBID 本体＋プロファイルをコピー
COPY grobid-home      /opt/grobid/grobid-home
COPY grobid-service/profiles /opt/grobid/grobid-service/profiles

# 環境変数とポート公開
ENV PORT=8070
EXPOSE ${PORT}

# Entrypoint：1 行で指定
ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service", \
            "server", \
            "/opt/grobid/grobid-home/config/grobid.yaml"]
