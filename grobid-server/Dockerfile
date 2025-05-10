###############################################################################
# GROBID 0.8.x + arm64 PDFalto（Science-Miner 公開版）同梱
# Render / Apple Silicon 向け
###############################################################################

# 1) arm64 固定のベースイメージ
FROM --platform=linux/arm64 lfoppiano/grobid:0.8.0
USER root

# 2) arm64 PDFalto_server の取得と配置
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -L -o /usr/local/bin/pdfalto_server \
      https://github.com/Science-Miner/pdfalto/releases/download/v0.5/pdfalto_server-0.5-linux-aarch64 && \
    chmod +x /usr/local/bin/pdfalto_server && \
    ln -sf /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto

# 3) grobid-home と grobid-service 一式をコピー
COPY --from=lfoppiano/grobid:0.8.0 /opt/grobid/grobid-home    /opt/grobid/grobid-home
COPY --from=lfoppiano/grobid:0.8.0 /opt/grobid/grobid-service /opt/grobid/grobid-service

# 4) ローカルビルドの one-jar でサービス JAR を上書き
COPY grobid-service/build/libs/grobid-service-0.8.2-SNAPSHOT-onejar.jar \
     /opt/grobid/grobid-service/lib/grobid-service-0.8.2-SNAPSHOT-onejar.jar

# 5) カスタム設定とモデルを上書き
COPY grobid-home/config/grobid.yaml  /opt/grobid/grobid-home/config/grobid.yaml
COPY grobid-home/models              /opt/grobid/grobid-home/models

# 6) 実行権限と一時ディレクトリ準備
RUN chmod +x /opt/grobid/grobid-service/bin/grobid-service && \
    mkdir -p /opt/grobid/grobid-home/tmp

# 7) ポート設定
ENV PORT=8070
EXPOSE ${PORT}

# 8) JVM + Dropwizard 起動オプション
ENV JAVA_TOOL_OPTIONS="\
  -Xms512m -Xmx2g \
  -Dorg.grobid.config=/opt/grobid/grobid-home/config/grobid.yaml \
  -Dgrobid.pdf.pdfalto.path=/usr/local/bin/pdfalto_server \
  -Ddw.server.applicationConnectors[0].port=\${PORT} \
  -Ddw.server.adminConnectors[0].port=8071"

# 9) サービス起動
ENTRYPOINT ["java","-jar","/opt/grobid/grobid-service/lib/grobid-service-0.8.2-SNAPSHOT-onejar.jar","server","/opt/grobid/grobid-home/config/grobid.yaml"]
