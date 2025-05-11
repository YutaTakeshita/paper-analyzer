# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source with debug logs
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 1) 必要ツールのインストール
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential cmake git wget ca-certificates \
      libpoppler-dev libfreetype6-dev libfontconfig1-dev \
      autoconf automake libtool pkg-config \
      libc6-dev zlib1g-dev libicu-dev libunistring-dev \
 && rm -rf /var/lib/apt/lists/*

# 2) ソースをクローン＆install_deps.sh をパッチ
WORKDIR /opt/pdfalto
RUN echo "=== CLONING PDFalto SOURCE ===" \
 && git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && echo "=== PATCHING install_deps.sh ===" \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh

# 3) install_deps.sh 実行（ログを残す）
RUN echo "=== BEFORE install_deps.sh: LIST /opt/pdfalto ===" \
 && ls -R /opt/pdfalto \
 && echo "=== RUNNING install_deps.sh ===" \
 && bash -x ./install_deps.sh > /tmp/install_deps.log 2>&1 \
 || (echo "=== install_deps.sh FAILED (first 200 lines) ===" \
     && head -n200 /tmp/install_deps.log \
     && false) \
 && echo "=== AFTER install_deps.sh: LIST /opt/pdfalto ===" \
 && ls -R /opt/pdfalto

# 4) *.in → *.h ヘッダ生成（zconf.h.in の行は削除）
RUN echo "=== GENERATING aconf.h ===" \
 && sed 's|@PACKAGE_@|pdfalto|g' xpdf-4.03/aconf.h.in > xpdf-4.03/aconf.h

# 5) CMap.cc パッチ：ヘッダ追加 & 関数シグネチャ修正
RUN echo "=== PATCHING CMap.cc ===" \
 && sed -i '1i#include <cstdio>\n#include <cstring>' xpdf-4.03/xpdf/CMap.cc \
 && sed -i 's/\bfindCMapFile\s*(\([^,]*\),\s*\([^)]*\))/findFontFile(\1->c_str(), \2->c_str())/g' xpdf-4.03/xpdf/CMap.cc

# 6) CMakeLists.txt の存在チェック
RUN echo "=== CHECK: CMakeLists.txt exists? ===" \
 && [ -f /opt/pdfalto/CMakeLists.txt ] && echo "OK" || (echo "MISSING CMakeLists.txt" && false)

# 7) ビルド
RUN echo "=== STARTING BUILD ===" \
 && mkdir build && cd build \
 && echo "=== START cmake ===" \
 && cmake .. \
     -DUSE_SYSTEM_ICU=ON \
     -DICU_INCLUDE_DIR=/usr/include \
     -DICU_LIBRARY=/usr/lib/x86_64-linux-gnu/libicuuc.so \
     -DICU_I18N_LIBRARY=/usr/lib/x86_64-linux-gnu/libicui18n.so \
     -DUNISTRING_INCLUDE_DIR=/usr/include \
 && echo "=== START make ===" \
 && make -j"$(nproc)" VERBOSE=1 \
 && echo "=== COPYING BINARY ===" \
 && cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# 8) ランタイム依存のインストール
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# 9) PDFalto バイナリをコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# 10) GROBID の JAR と設定をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home     /opt/grobid/grobid-home

# 11) 環境変数とエントリーポイント
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV LOG_LEVEL=DEBUG

ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL}'; envsubst < \"${GROBID_HOME}/config/grobid.yaml\" > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
