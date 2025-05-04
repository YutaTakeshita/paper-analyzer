# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
WORKDIR /opt/grobid
COPY grobid-server/grobid /opt/grobid/grobid-home
EXPOSE 8070
ENTRYPOINT ["./grobid-service"]