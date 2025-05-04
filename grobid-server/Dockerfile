# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
WORKDIR /opt/grobid
COPY grobid-home/config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
RUN chmod +x /opt/grobid/grobid-service
EXPOSE 8070
ENTRYPOINT ["./grobid-service"]