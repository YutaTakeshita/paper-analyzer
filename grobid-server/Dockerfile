# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential cmake git wget ca-certificates \
      libpoppler-dev libfreetype6-dev libfontconfig1-dev \
      autoconf automake libtool pkg-config \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh \
 && bash -x ./install_deps.sh \
 && mkdir build

# テンプレートから aconf.h を生成（zconf.h は存在しないので除外）
RUN sed 's|@PACKAGE_@|pdfalto|g' \
       xpdf-4.03/aconf.h.in > xpdf-4.03/aconf.h

# ビルドディレクトリでコンパイル
RUN cd build \
 && cmake .. -DCMAKE_CXX_FLAGS="-I/opt/pdfalto/xpdf-4.03" \
 && make -j"$(nproc)" \
 && cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/
COPY grobid-service.jar grobid-home /opt/grobid/

ENV GROBID_HOME=/opt/grobid/grobid-home
ENTRYPOINT ["sh","-c","envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml && java -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
