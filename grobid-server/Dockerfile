# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid
RUN mkdir -p config
COPY config/grobid.yaml config/grobid.yaml
EXPOSE 8070
ENTRYPOINT ["./grobid-service"]
CMD ["server", "config/grobid.yaml"]