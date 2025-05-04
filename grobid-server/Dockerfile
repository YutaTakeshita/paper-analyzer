FROM lfoppiano/grobid:0.7.2
USER root
 # Install envsubst and curl
RUN apt-get update && apt-get install -y gettext-base curl

# Download PDFalto binary and place it under grobid-home/pdfalto/lin-64
RUN mkdir -p /opt/grobid/grobid-home/pdfalto/lin-64 && \
    curl -L https://github.com/pdfalto/pdfalto/releases/download/v0.4.0/pdfalto-0.4.0-linux-x86_64.tar.gz \
      | tar xvz -C /opt/grobid/grobid-home/pdfalto/lin-64 --strip-components=1 && \
    chmod +x /opt/grobid/grobid-home/pdfalto/lin-64/pdfalto
WORKDIR /opt/grobid

# Copy full grobid-home directory (config, models, tmp)
COPY grobid-home /opt/grobid/grobid-home

# Ensure the grobid-service binary is executable
RUN chmod +x /opt/grobid/grobid-service/bin/grobid-service

# Expose the default GROBID port
EXPOSE 8070

# Set default PORT if not provided, substitute into YAML, and start GROBID service
ENTRYPOINT ["/bin/sh", "-c", "export PORT=${PORT:-8070} && envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /opt/grobid/grobid-home/config/runtime-config.yaml && exec /opt/grobid/grobid-service/bin/grobid-service server /opt/grobid/grobid-home/config/runtime-config.yaml"]