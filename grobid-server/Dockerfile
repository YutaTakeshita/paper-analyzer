# grobid-server/Dockerfile
FROM lfoppiano/grobid:0.7.2
USER root
WORKDIR /opt/grobid/grobid-home
RUN mkdir -p /opt/grobid/grobid-home/config
COPY config/grobid.yaml /opt/grobid/grobid-home/config/grobid.yaml
RUN chmod +x /opt/grobid/grobid-home/grobid-service
EXPOSE 8070
ENTRYPOINT ["/opt/grobid/grobid-home/grobid-service"]
CMD ["server", "config/grobid.yaml"]