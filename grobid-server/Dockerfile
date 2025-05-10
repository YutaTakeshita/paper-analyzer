# ──────────────────────────────────────────────────────────────
# GROBID 0.8.0 + arm64 PDFalto 同梱（Render／Apple Silicon対応）
# ──────────────────────────────────────────────────────────────
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# 1) arm64版 pdfalto_server を取得＆配置
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    if [ "$(uname -m)" = "aarch64" ]; then \
      URL=https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64; \
    else \
      URL=https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-x86_64; \
    fi && \
    curl -L -o /usr/local/bin/pdfalto_server "$URL" && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 2) 必要なファイルだけコピー
COPY grobid-home/config/grobid.yaml       /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-home/models                   /opt/grobid/grobid-home/models
# （※ grobid-service はベースイメージに含まれているため、ここでは一切触りません）

# 3) ポート設定
ENV PORT=8070
EXPOSE 8070

# 4) エントリポイントはサービス起動スクリプトを１行で
ENTRYPOINT /opt/grobid/grobid-service/bin/grobid-service server /opt/grobid/grobid-home/config/grobid.yaml
