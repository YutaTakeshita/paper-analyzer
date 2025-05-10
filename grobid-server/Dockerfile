# syntax=docker/dockerfile:1
FROM openjdk:11-jre-slim

# 不要なパッケージは省いて軽量化
RUN apt-get update \
 && rm -rf /var/lib/apt/lists/*

# ビルド済みJarをコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar

# GROBID-HOMEフォルダを丸ごとコピー（config 以下を含む）
COPY grobid-home /opt/grobid/grobid-home

# 環境変数設定
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV PORT=8070

WORKDIR /opt/grobid
EXPOSE 8070

ENTRYPOINT ["java", "-jar", "grobid-service.jar", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]
