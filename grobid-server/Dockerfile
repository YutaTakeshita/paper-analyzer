FROM lfoppiano/grobid:0.7.2

USER root
# デバッグ用ツールをインストール
RUN echo "=== INSTALL DEBUG TOOLS ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# カスタム設定ファイルをコピー（必要に応じて）
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml

# デバッグ: grobid ディレクトリ構成を確認
RUN echo "=== DEBUG: LIST /opt/grobid ===" && ls -R /opt/grobid

# ENTRYPOINT は必ず 1 行で記述、JAR のパスも修正
ENTRYPOINT ["sh","-c","echo \"Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}\"; envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL:-INFO} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service/lib/grobid-service-0.7.2.jar server /tmp/grobid.yaml"]
