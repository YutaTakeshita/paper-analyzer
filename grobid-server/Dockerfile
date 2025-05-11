FROM openjdk:11-jre-slim

# 1) 必要ツールのインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base wget ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# 2) PDFalto バイナリをダウンロード
RUN wget -O /usr/local/bin/pdfalto_server \
     https://github.com/kermitt2/pdfalto/releases/download/0.4/pdfalto_server-linux-amd64 \
 && chmod +x /usr/local/bin/pdfalto_server

# 3) GROBID の JAR と設定を配置
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home     /opt/grobid/grobid-home

# 4) 環境変数と起動コマンド
ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
