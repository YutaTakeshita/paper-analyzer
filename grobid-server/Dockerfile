# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
WORKDIR /opt/grobid
COPY grobid-home /opt/grobid/grobid-home
EXPOSE 8070
ENTRYPOINT ["./grobid-service", "server", "/opt/grobid/grobid-home/config/grobid.yaml"]