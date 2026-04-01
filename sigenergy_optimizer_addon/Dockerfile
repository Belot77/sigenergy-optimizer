ARG BUILD_FROM=docker.io/library/python:3.12-alpine
FROM ${BUILD_FROM}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk add --no-cache bash ca-certificates git

SHELL ["/bin/sh", "-o", "pipefail", "-c"]

COPY buildstamp.txt /tmp/buildstamp.txt

RUN echo "Building source stamp: $(cat /tmp/buildstamp.txt)" \
    && git clone --depth 1 https://github.com/Belot77/sigenergy-optimizer /tmp/src \
    && cp /tmp/src/requirements.txt /app/requirements.txt \
    && cp -r /tmp/src/app /app/app \
    && cp -r /tmp/src/templates /app/templates \
    && cp -r /tmp/src/static /app/static \
    && cp /tmp/src/.env.example /app/.env.example \
    && sed -i 's/^uvicorn\[standard\]/uvicorn/' /app/requirements.txt \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /app/requirements.txt \
    && rm -rf /tmp/src

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 7123

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:7123/health >/dev/null || exit 1

CMD ["/run.sh"]
