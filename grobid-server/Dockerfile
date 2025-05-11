# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 基本的なビルドツールとライブラリをインストール
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
     build-essential cmake git wget ca-certificates \
     libpoppler-dev libfreetype6-dev libfontconfig1-dev \
     autoconf automake libtool pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pdfalto

# ソースをクローンし、依存スクリプトを修正して実行
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 && ./install_deps.sh

# ─── テンプレートヘッダを実体化 ────────────────────────────────
# find で aconf.h.in の存在を確認
RUN echo "=== LOCATING templates ===" \
 && find xpdf-4.03 -type f | grep '\.in$'

# aconf.h.in → aconf.h, zconf.h.in → zconf.h を生成
RUN sed 's|@PACKAGE_@|pdfalto|g' xpdf-4.03/aconf.h.in > xpdf-4.03/aconf.h \
 && sed 's|@PACKAGE_@|pdfalto|g' xpdf-4.03/zconf.h.in   > xpdf-4.03/zconf.h

# または、単純にテンプレートをそのままコピーするだけでも可
# RUN cp xpdf-4.03/aconf.h.in xpdf-4.03/aconf.h
# RUN cp xpdf-4.03/zconf.h.in   xpdf-4.03/zconf.h

# ─── CMake でビルド ───────────────────────────────────────────
RUN mkdir build && cd build \
 && cmake .. \
 && make -j"$(nproc)"

# バイナリを取り出しやすく配置
RUN cp build/pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server
COPY grobid-service.jar      /opt/grobid/grobid-service.jar
COPY grobid-home             /opt/grobid/grobid-home

ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
