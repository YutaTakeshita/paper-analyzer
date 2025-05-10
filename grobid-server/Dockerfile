# ─────────────────────────────────────────────
# マルチプラットフォーム対応：pdfalto_server を自動で選択
# ─────────────────────────────────────────────
# Stage0: pdfalto バイナリのダウンロード
FROM docker.io/library/debian:bookworm-slim AS pdfalto
ARG BUILDPLATFORM
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && \
    if [ "${BUILDPLATFORM##*/}" = "arm64" ]; then \
      URL=https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64; \
    else \
      URL=https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-x86_64; \
    fi \
 && curl -L -o /usr/local/bin/pdfalto_server "$URL" \
 && chmod +x /usr/local/bin/pdfalto_server \
 && ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# Stage1: 真の GROBID イメージ
FROM lfoppiano/grobid:0.8.0 AS grobid
USER root

# pdfalto をステージ0 からコピー
COPY --from=pdfalto /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server
COPY --from=pdfalto /usr/local/bin/pdfalto        /usr/local/bin/pdfalto

# GROBID 本体＋設定
COPY grobid-home      /opt/grobid/grobid-home
COPY grobid-service   /opt/grobid/grobid-service

EXPOSE 8070

ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]
