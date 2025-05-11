# ─────────────────────────────────────────────────────────────
# Build GROBID image with debug logs
# ─────────────────────────────────────────────────────────────
FROM lfoppiano/grobid:0.7.2

# 1) root に切り替えて envsubst をインストール
USER root
RUN echo "=== INSTALLING DEBUG TOOLS ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      gettext-base \
 && rm -rf /var/lib/apt/lists/*

# 2) カスタム設定ファイルをコピー（必要に応じて）
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml

# 3) デバッグ：GROBID ディレクトリ構造を確認
RUN echo "=== DEBUG: LIST /opt/grobid ===" \
 && ls -R /opt/grobid

# 4) デバッグ：JAR の存在確認
RUN echo "=== DEBUG: VERIFY JAR PATH ===" \
 && ls -l /opt/grobid/grobid-service/grobid-service.jar

# 5) デバッグ：設定ファイルの中身確認
RUN echo "=== DEBUG: SHOW CONFIG SNIPPET ===" \
 && sed -n '1,20p' /opt/grobid/grobid-home/config/grobid.yaml

# 6) ENTRYPOINT を 1 行で記述
ENTRYPOINT ["sh","-c","echo \"Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}\"; envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL:-INFO} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service/grobid-service.jar server /tmp/grobid.yaml"]
