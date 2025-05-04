# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid
COPY config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
RUN chmod +x /opt/grobid/grobid-service

# Ensure the Dockerfile itself and the config directory are tracked by Git
# (Add these comments to remind to add new files)

EXPOSE 8070
ENTRYPOINT ["/opt/grobid/grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]