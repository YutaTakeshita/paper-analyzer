FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid

# Copy full grobid-home directory (config, models, tmp)
COPY COPY grobid-home /opt/grobid/grobid-home

# Ensure the grobid-service binary is executable
RUN chmod +x /opt/grobid/grobid-service/bin/grobid-service

# Expose the default GROBID port
EXPOSE 8070

# Start the service, passing the config path; allow PORT override via environment
ENTRYPOINT ["/opt/grobid/grobid-service/bin/grobid-service"]
CMD ["server", "/opt/grobid/grobid-home/config/grobid.yaml", "--port", "${PORT:-8070}"]