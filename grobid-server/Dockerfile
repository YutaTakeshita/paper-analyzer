FROM lfoppiano/grobid:0.7.2

# 1) envsubst を含むシェルユーティリティを追加インストール
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# 2) 必要なら、設定ファイルを上書き
#    例: grobid-home/config/grobid.yaml をカスタムする場合
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml

# JAR の配置確認
RUN echo "=== VERIFY JAR LOCATION ===" \
 && ls -l /opt/grobid \
 && ls -l /opt/grobid/grobid-home/config \
 && ls -l /opt/grobid/grobid-service.jar
 
# 3) ENTRYPOINT を一行で記述
ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}'; envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL:-INFO} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
