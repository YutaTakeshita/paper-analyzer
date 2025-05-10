###############################################################################
# ステージ1: JAR をビルド
###############################################################################
# ※Gradle版の例。Maven の場合は maven:3.8-jdk17 などに置き換えてください
FROM gradle:7.5-jdk17 AS builder

# ソースを丸ごとコピー（必要に応じてパスを調整）
COPY grobid-service /home/gradle/project/grobid-service
WORKDIR /home/gradle/project/grobid-service

# テストスキップでビルド
RUN gradle clean assemble -x test

###############################################################################
# ステージ2: 実行イメージ
###############################################################################
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# 1) arm64 PDFalto_server を取得して配置
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64 && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 2) grobid-home と grobid-service の残りをコピー
COPY --from=lfoppiano/grobid:0.8.0 /opt/grobid/grobid-home    /opt/grobid/grobid-home
COPY --from=lfoppiano/grobid:0.8.0 /opt/grobid/grobid-service /opt/grobid/grobid-service

# 3) builder ステージから JAR を取り込み
COPY --from=builder \
     /home/gradle/project/grobid-service/build/libs/grobid-service-*-onejar.jar \
     /opt/grobid/grobid-service/lib/grobid-service.jar

# 4) カスタム設定とモデルを上書き（必要に応じて）
COPY grobid-home/config/grobid.yaml  /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-home/models              /opt/grobid/grobid-home/models

# 5) 実行権限と一時ディレクトリ
RUN chmod +x /opt/grobid/grobid-service/bin/grobid-service && \
    mkdir -p /opt/grobid/grobid-home/tmp

# 6) ポート
ENV PORT=8070
EXPOSE ${PORT}

# 7) JVM + Dropwizard 起動オプション
ENV JAVA_TOOL_OPTIONS="\
  -Xms512m -Xmx2g \
  -Dorg.grobid.config=/opt/grobid/grobid-home/config/grobid.yaml \
  -Dgrobid.pdf.pdfalto.path=/usr/local/bin/pdfalto_server \
  -Ddw.server.applicationConnectors[0].port=\${PORT} \
  -Ddw.server.adminConnectors[0].port=8071"

# 8) 起動コマンド
ENTRYPOINT ["java","-jar","/opt/grobid/grobid-service/lib/grobid-service.jar","server","/opt/grobid/grobid-home/config/grobid.yaml"]
