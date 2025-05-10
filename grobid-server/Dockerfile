# ──────────────────────────────────────────────────────────────
# 1) ビルドステージ：Gradle で one-jar を組み立てる
# ──────────────────────────────────────────────────────────────
FROM gradle:7.5-jdk11 AS builder
WORKDIR /workspace
COPY grobid-server/grobid-service/settings.gradle ./
COPY grobid-server/grobid-service/build.gradle    ./
COPY grobid-server/grobid-service/src             ./src
RUN gradle clean assemble -x test

# ──────────────────────────────────────────────────────────────
# 2) ランタイムステージ：GROBID ベースイメージに pdfalto を追加
# ──────────────────────────────────────────────────────────────
FROM lfoppiano/grobid:0.8.0
USER root

#x86_64 用 pdfalto_server の取得
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-x86_64 \
 && chmod +x /usr/local/bin/pdfalto_server \
 && ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# GROBID の設定ファイルとモデルを丸ごとコピー
COPY grobid-server/grobid-home/config/grobid.yaml       /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-server/grobid-home/models                   /opt/grobid/grobid-home/models

# builder から組み立てた one-jar を持ってくる
COPY --from=builder \
     /workspace/grobid-service/build/libs/grobid-service-*-onejar.jar \
     /opt/grobid/grobid-service/lib/grobid-service-onejar.jar

# ポート公開／エントリポイント
ENV PORT=8070
EXPOSE ${PORT}
ENTRYPOINT ["java","-jar","/opt/grobid/grobid-service/lib/grobid-service-onejar.jar","server","/opt/grobid/grobid-home/config/grobid.yaml"]

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

ENTRYPOINT ["sh", "-c", "java -jar grobid-service.jar -gH ${GROBID_HOME} -p ${PORT}"]
