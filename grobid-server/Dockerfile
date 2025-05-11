FROM lfoppiano/grobid:0.7.2

USER root
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# (必要なら grobid.yaml を上書き)
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml

# デバッグ: JAR と起動スクリプトの存在確認
RUN echo "=== DEBUG: VERIFY FILES ===" \
 && ls -l /opt/grobid/grobid-service/lib/grobid-service-*.jar \
 && ls -l /opt/grobid/grobid-service/bin/grobid-service

# ENTRYPOINT は 1 行で、公式スクリプトを呼び出す
ENTRYPOINT ["sh","-c","echo \"Starting GROBID with LOG_LEVEL=${LOG_LEVEL:-INFO}\"; envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /tmp/grobid.yaml; exec /opt/grobid/grobid-service/bin/grobid-service server /tmp/grobid.yaml"]
