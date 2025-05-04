# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
WORKDIR /opt/grobid/grobid-home
COPY grobid-home/config/grobid.yaml ./config/grobid.yaml
EXPOSE 8070
ENTRYPOINT ["./grobid-service"]