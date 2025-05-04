FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid

# Copy custom GROBID config
COPY config/grobid.yaml /opt/grobid/config/grobid.yaml

# Ensure the grobid-service binary is executable
RUN chmod +x /opt/grobid/grobid-service

# Expose the default GROBID port
EXPOSE 8070

# Start the service, passing the config path; allow PORT override via environment
ENTRYPOINT ["/opt/grobid/grobid-service"]
CMD ["server", "/opt/grobid/config/grobid.yaml"]