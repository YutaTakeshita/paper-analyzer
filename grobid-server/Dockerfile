FROM lfoppiano/grobid:0.7.2

# 任意で環境変数を追加
ENV LOG_LEVEL=DEBUG

# 設定ファイルだけ差し替えたい場合
COPY grobid-home/config/grobid.yaml /opt/grobid/config/

ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL}'; envsubst < /opt/grobid/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
