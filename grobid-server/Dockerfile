# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid/grobid-home
COPY config/grobid.yaml ./config/grobid.yaml
RUN chmod +x /opt/grobid/grobid-service
EXPOSE 8070
ENTRYPOINT ["/opt/grobid/grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]