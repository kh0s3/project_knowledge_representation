FROM eclipse-temurin:21-jre

# Fuseki release to download. Change it with: docker compose build --build-arg FUSEKI_VERSION=x.y.z
ARG FUSEKI_VERSION=6.1.0

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir /fuseki \
 && curl -fsSL "https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-${FUSEKI_VERSION}.tar.gz" \
    | tar xz --strip-components=1 -C /fuseki

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENV FUSEKI_HOME=/fuseki JVM_ARGS="-Xmx2g"
WORKDIR /fuseki
EXPOSE 3030
ENTRYPOINT ["/entrypoint.sh"]
