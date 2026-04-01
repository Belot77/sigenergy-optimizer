ARG BUILD_FROM=docker.io/library/python:3.12-alpine
FROM ${BUILD_FROM}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk add --no-cache bash ca-certificates

COPY buildstamp.txt /tmp/buildstamp.txt

COPY requirements.txt /app/requirements.txt
RUN echo "Building source stamp: $(cat /tmp/buildstamp.txt)" \
    && sed -i 's/^uvicorn\[standard\]/uvicorn/' /app/requirements.txt \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app
COPY templates /app/templates
COPY static /app/static
COPY .env.example /app/.env.example

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 7123

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:7123/health >/dev/null || exit 1

CMD ["/run.sh"]
