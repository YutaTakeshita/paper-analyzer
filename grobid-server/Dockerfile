# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source with debug logs
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

RUN echo "=== INSTALLING BUILD DEPENDENCIES ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential cmake git wget ca-certificates \
      libpoppler-dev libfreetype6-dev libfontconfig1-dev \
      autoconf automake libtool pkg-config \
      libc6-dev zlib1g-dev libicu-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/pdfalto
RUN echo "=== CLONING PDFalto SOURCE ===" \
 && git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && echo "=== PATCHING install_deps.sh ===" \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh

RUN echo "=== BEFORE install_deps.sh: LIST /opt/pdfalto ===" \
 && ls -R /opt/pdfalto

RUN echo "=== RUNNING install_deps.sh ===" \
 && bash -x ./install_deps.sh > /tmp/install_deps.log 2>&1 \
 || (echo "=== install_deps.sh FAILED (first 200 lines) ===" && head -n200 /tmp/install_deps.log && false)

RUN echo "=== AFTER install_deps.sh: LIST /opt/pdfalto ===" \
 && ls -R /opt/pdfalto

RUN echo "=== PATCHING SOURCE FILES BEFORE BUILD ===" \
 && sed -i '1i#include <cstdio>\n#include <cstring>' xpdf-4.03/xpdf/CMap.cc \
 && sed -i 's/\bfindCMapFile\b/findFontFile/g' xpdf-4.03/xpdf/CMap.cc

RUN echo "=== CHECK: CMakeLists.txt exists? ===" \
 && if [ -f /opt/pdfalto/CMakeLists.txt ]; then echo "OK"; else echo "MISSING CMakeLists.txt"; false; fi

RUN echo "=== STARTING BUILD ===" \
 && mkdir build && cd build \
 && echo "=== START cmake ===" \
 && cmake .. \
 && echo "=== START make ===" \
 && make -j"$(nproc)" VERBOSE=1 \
 && echo "=== COPYING BINARY ===" \
 && cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

RUN echo "=== INSTALLING RUNTIME DEPENDENCIES ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home     /opt/grobid/grobid-home

ENV GROBID_HOME=/opt/grobid/grobid-home
ENV LOG_LEVEL=DEBUG

ENTRYPOINT sh -c "echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL}'; envsubst < \$GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=\${LOG_LEVEL} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"
