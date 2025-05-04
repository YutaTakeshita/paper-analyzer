# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid
COPY config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
RUN chmod +x /opt/grobid/grobid-service
EXPOSE 8070
CMD ["./grobid-service", "server", "grobid-home/config/grobid.yaml"]