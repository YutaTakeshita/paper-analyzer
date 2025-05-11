# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source with debug logs
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 1) 必要ツールのインストール
RUN echo "=== INSTALL BUILD DEPENDENCIES ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential cmake git wget ca-certificates \
      libpoppler-dev libfreetype6-dev libfontconfig1-dev \
      autoconf automake libtool pkg-config \
      libc6-dev zlib1g-dev libicu-dev \
 && rm -rf /var/lib/apt/lists/*

# 2) ソースをクローン＆install_deps.sh 修正
WORKDIR /opt/pdfalto
RUN echo "=== CLONING PDFalto SOURCE ===" \
 && git clone --recursive https://github.com/kermitt2/pdfalto.git . \
 && echo "=== PATCH install_deps.sh ===" \
 && chmod +x install_deps.sh \
 && sed -i 's/sudo //g' install_deps.sh \
 && sed -i '/cp .*xpdfrc/d' install_deps.sh

# 3) デバッグ: install_deps.sh 実行前の状況
RUN echo "=== BEFORE install_deps.sh ===" && ls -R /opt/pdfalto

# 4) install_deps.sh 実行（失敗時はログ先頭200行を出力）
RUN echo "=== RUNNING install_deps.sh ===" \
 && bash -x ./install_deps.sh > /tmp/install_deps.log 2>&1 \
 || (echo "=== install_deps.sh FAILED (first 200 lines) ===" && head -n200 /tmp/install_deps.log && false)

# 5) デバッグ: install_deps.sh 実行後の状況
RUN echo "=== AFTER install_deps.sh ===" && ls -R /opt/pdfalto

# 6) パッチ: aconf.h を生成
RUN echo "=== GENERATING aconf.h ===" \
 && sed 's|@PACKAGE_@|pdfalto|g' xpdf-4.03/aconf.h.in > xpdf-4.03/aconf.h

# 7) パッチ: 各 .cc ファイルにヘッダ追加 & 関数シグネチャ修正
RUN echo "=== PATCHING ALL RELEVANT .cc FILES ===" \
 && for f in \
      xpdf-4.03/xpdf/CMap.cc \
      xpdf-4.03/xpdf/CharCodeToUnicode.cc \
      xpdf-4.03/xpdf/Catalog.cc; do \
      sed -i '1i#include <cstdio>\n#include <cstring>' "$f"; \
    done \
 && sed -i 's/\bfindCMapFile\s*(\([^,]*\),\s*\([^)]*\))/findFontFile(\1->c_str(), \2->c_str())/g' xpdf-4.03/xpdf/CMap.cc

# 8) ビルド前チェック
RUN echo "=== CHECK: CMakeLists.txt exists? ===" \
 && if [ -f /opt/pdfalto/CMakeLists.txt ]; then echo "OK"; else echo "MISSING CMakeLists.txt"; false; fi

# 9) ビルド
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

# 10) ランタイム依存ツール
RUN echo "=== INSTALL RUNTIME DEPENDENCIES ===" \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# 11) PDFalto バイナリをコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# 12) GROBID の JAR と設定をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home     /opt/grobid/grobid-home

# 13) 環境変数設定・起動コマンド
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV LOG_LEVEL=DEBUG
ENTRYPOINT ["sh","-c","echo 'Starting GROBID with LOG_LEVEL=${LOG_LEVEL}'; envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
