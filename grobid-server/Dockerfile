FROM lfoppiano/grobid:0.7.2

# envsubst を含むシェルユーティリティを追加
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# カスタム設定を上書き（必要なら）
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/

# JAR を正しい場所にコピー
COPY grobid-service.jar /opt/grobid/grobid-service/grobid-service.jar

# JAR の配置確認
RUN echo "=== VERIFY JAR LOCATION ===" \
 && ls -l /opt/grobid \
 && ls -l /opt/grobid/grobid-home/config \
 && ls -l /opt/grobid/grobid-service.jar
 
# エントリーポイントを１行で
ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}'; envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL:-INFO} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service/grobid-service.jar server /tmp/grobid.yaml"]
