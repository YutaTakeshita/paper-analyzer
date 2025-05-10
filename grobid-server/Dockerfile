# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# unzip は不要なので省略。gettext-base を入れて envsubst を使えるようにする
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

# ビルド済み Jar をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar

# grobid-home フォルダ（config/models/pdfalto/resources）を丸ごとコピー
COPY grobid-home /opt/grobid/grobid-home

# 環境変数
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070

WORKDIR /opt/grobid
EXPOSE 8070

# 起動時にテンプレートを envsubst してからサーバ起動
ENTRYPOINT [ "sh", "-c", "envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar grobid-service.jar server /tmp/grobid.yaml" ]