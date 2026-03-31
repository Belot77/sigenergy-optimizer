ARG BUILD_FROM=docker.io/library/python:3.12-alpine
FROM ${BUILD_FROM}

WORKDIR /app

RUN apk add --no-cache bash ca-certificates git

ARG REPO_URL="https://github.com/Belot77/sigenergy-optimizer.git"
ARG REPO_REF="main"

RUN git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" /src \
    && sed -i 's/^uvicorn\[standard\]/uvicorn/' /src/requirements.txt \
    && pip3 install --no-cache-dir -r /src/requirements.txt \
    && cp -r /src/app /src/templates /src/static /app/ \
    && cp /src/.env.example /app/.env.example \
    && rm -rf /src

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 7123

CMD ["/run.sh"]
