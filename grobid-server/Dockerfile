FROM lfoppiano/grobid:0.7.2
USER root
# Install envsubst for runtime configuration substitution
RUN apt-get update && apt-get install -y gettext-base
WORKDIR /opt/grobid

# Copy full grobid-home directory (config, models, tmp)
COPY grobid-home /opt/grobid/grobid-home

# Ensure the grobid-service binary is executable
RUN chmod +x /opt/grobid/grobid-service/bin/grobid-service

# Expose the default GROBID port
EXPOSE 8070

# Substitute PORT into the YAML and start GROBID service
ENTRYPOINT ["/bin/sh", "-c", "envsubst < /opt/grobid/grobid-home/config/grobid.yaml > /opt/grobid/grobid-home/config/runtime-config.yaml && exec /opt/grobid/grobid-service/bin/grobid-service server /opt/grobid/grobid-home/config/runtime-config.yaml"]