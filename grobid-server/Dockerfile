# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image (修正版)
# ─────────────────────────────────────────────────────────────
FROM lfoppiano/grobid:0.7.2

USER root

# 1) envsubst を含むシェルユーティリティを追加インストール
RUN echo "=== INSTALL DEBUG TOOLS ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# 2) Grobid 設定ファイルを配置
#    - /opt/grobid/grobid-home/config/grobid.yaml は既存の読み込み先
#    - /opt/grobid/config/grobid.yaml は内部で参照されるパス
RUN echo "=== PREPARE CONFIG DIRECTORIES ===" \
 && mkdir -p /opt/grobid/config \
 && echo "=== COPY CUSTOM grobid.yaml TO BOTH LOCATIONS ==="
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-home/config/grobid.yaml /opt/grobid/config/grobid.yaml

# 3) デバッグ: 実際にファイルが配置されたことを確認
RUN echo "=== DEBUG: VERIFY CONFIG FILES ===" \
 && ls -l /opt/grobid/grobid-home/config/grobid.yaml \
 && ls -l /opt/grobid/config/grobid.yaml

# 4) ENTRYPOINT を一行で記述
ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}'; envsubst < /opt/grobid/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL:-INFO} -jar /opt/grobid/grobid-service/lib/grobid-service-0.7.2.jar server /tmp/grobid.yaml"]
