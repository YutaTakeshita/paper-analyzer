# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
WORKDIR /opt/grobid
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
EXPOSE 8070
CMD ["./grobid-service"]