# ─────────────────────────────────────────────────────────────
# Stage 1: Build PDFalto server from source with debug logs
# ─────────────────────────────────────────────────────────────
FROM debian:bullseye-slim AS pdfalto-builder

# 1) 必要なビルドツールとライブラリをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    wget \
    ca-certificates \
    libpoppler-dev \
    libfreetype6-dev \
    libfontconfig1-dev \
    autoconf \
    automake \
    libtool \
    pkg-config \
    libicu-dev \
    zlib1g-dev \
    libpcre3-dev \
  && rm -rf /var/lib/apt/lists/*

# 2) ソースをクローンし、install_deps.sh をパッチ
WORKDIR /opt/pdfalto
RUN git clone --recursive https://github.com/kermitt2/pdfalto.git . \
  && chmod +x install_deps.sh \
  && sed -i 's/sudo //g' install_deps.sh \
  && sed -i '/cp .*xpdfrc/d' install_deps.sh

# 3) デバッグ: インストール前の構成を出力
RUN echo "=== BEFORE install_deps.sh ===" \
  && ls -R /opt/pdfalto

# 4) install_deps.sh を実行（失敗時はログ出力して中断）
RUN echo "=== RUNNING install_deps.sh ===" \
  && bash -x ./install_deps.sh > /tmp/install_deps.log 2>&1 \
  || (echo "=== install_deps.sh FAILED (first 200 lines) ===" \
      && head -n200 /tmp/install_deps.log \
      && false)

# 5) デバッグ: インストール後の構成を出力
RUN echo "=== AFTER install_deps.sh ===" \
  && ls -R /opt/pdfalto

# 6) aconf.h.in から aconf.h を生成（リポジトリによっては zconf.h.in がない）
RUN if [ -f xpdf-4.03/aconf.h.in ]; then \
      sed 's|@PACKAGE_@|pdfalto|g' xpdf-4.03/aconf.h.in > xpdf-4.03/aconf.h; \
    fi

# 7) CMakeLists.txt の存在チェック
RUN echo "=== CHECK: CMakeLists.txt exists? ===" \
  && if [ -f /opt/pdfalto/CMakeLists.txt ]; then echo "OK"; else echo "MISSING CMakeLists.txt"; false; fi

# 8) ビルド
RUN mkdir build \
  && cd build \
  && echo "=== START cmake ===" \
  && cmake .. -DUSE_SYSTEM_ICU=ON -DICU_INCLUDE_DIR=/usr/include -DICU_LIBRARY=/usr/lib/x86_64-linux-gnu/libicuuc.so -DICU_I18N_LIBRARY=/usr/lib/x86_64-linux-gnu/libicui18n.so \
  && echo "=== START make ===" \
  && make -j"$(nproc)" VERBOSE=1 \
  && cp pdfalto_server /usr/local/bin/pdfalto_server

# ─────────────────────────────────────────────────────────────
# Stage 2: Build final GROBID image
# ─────────────────────────────────────────────────────────────
FROM openjdk:11-jre-slim

# 9) envsubst 用ユーティリティをインストール
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/grobid

# 10) PDFalto バイナリをコピー
COPY --from=pdfalto-builder /usr/local/bin/pdfalto_server /usr/local/bin/pdfalto_server

# 11) GROBID の JAR と設定をコピー
COPY grobid-service.jar /opt/grobid/grobid-service.jar
COPY grobid-home       /opt/grobid/grobid-home

# 12) 環境変数設定と起動スクリプト
ENV GROBID_HOME=/opt/grobid/grobid-home
ENV LOG_LEVEL=DEBUG

ENTRYPOINT ["sh","-c","echo \"Starting GROBID with LOG_LEVEL=${LOG_LEVEL}\"; envsubst < $GROBID_HOME/config/grobid.yaml > /tmp/grobid.yaml; exec java -Dorg.slf4j.simpleLogger.defaultLogLevel=${LOG_LEVEL} -Ddw.serverConfigResource=/tmp/grobid.yaml -jar /opt/grobid/grobid-service.jar server /tmp/grobid.yaml"]
