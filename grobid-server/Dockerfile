# ─────────────────────────────────────────────
# Render / x86_64 環境向け Grobid 0.8.0 + pdfalto
# ─────────────────────────────────────────────
FROM lfoppiano/grobid:0.8.0
USER root

# 1) x86_64 用 pdfalto_server を取得して配置
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-x86_64 \
 && chmod +x /usr/local/bin/pdfalto_server \
 && ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 2) GROBID の設定とモデルを丸ごとコピー
COPY grobid-home/config/grobid.yaml       /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-home/models                   /opt/grobid/grobid-home/models

# 3) HTTP ポート公開
EXPOSE 8070

# 4) Entrypoint：YAML を直接指定して起動
ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service","server","/opt/grobid/grobid-home/config/grobid.yaml"]
