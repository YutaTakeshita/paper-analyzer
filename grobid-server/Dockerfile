# ─────────────────────────────────────────────
# GROBID 0.8.0 + arm64 pdfalto (Science-Miner)
# Render / Apple Silicon 向け
# ─────────────────────────────────────────────
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# 1) arm64版 pdfalto_server を取得して配置
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64 \
 && chmod +x /usr/local/bin/pdfalto_server \
 && ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 2) GROBID ホームとサービスのプロファイルをコピー
COPY grobid-home       /opt/grobid/grobid-home
COPY grobid-service/   /opt/grobid/grobid-service/

# 3) 必要に応じてモデルや設定を上書き
# COPY grobid-home/models /opt/grobid/grobid-home/models

# 4) ポート公開
EXPOSE 8070

# 5) Entrypoint（exec 形式・一行）
ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]
