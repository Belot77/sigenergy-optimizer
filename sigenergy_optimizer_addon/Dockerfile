ARG BUILD_FROM=docker.io/library/python:3.12-alpine
FROM ${BUILD_FROM}
ARG BUILD_VERSION
ARG SOURCE_REF

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apk add --no-cache bash ca-certificates git

COPY buildstamp.txt /tmp/buildstamp.txt
COPY config.yaml /tmp/addon-config.yaml

SHELL ["/bin/sh", "-o", "pipefail", "-c"]

RUN if [ -n "${SOURCE_REF:-}" ]; then \
        case "${SOURCE_REF}" in *[!0-9a-fA-F]*) echo "SOURCE_REF must be a full commit SHA" >&2; exit 1 ;; esac; \
        [ "${#SOURCE_REF}" -eq 40 ] || { echo "SOURCE_REF must be a full commit SHA" >&2; exit 1; }; \
        source_ref="$(printf '%s' "${SOURCE_REF}" | tr '[:upper:]' '[:lower:]')"; \
    else \
        printf '%s\n' "${BUILD_VERSION:-}" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+-haos[0-9]+$' \
            || { echo "Missing or invalid release BUILD_VERSION" >&2; exit 1; }; \
        source_ref="refs/tags/v${BUILD_VERSION}"; \
    fi \
    && echo "Building source ref: ${source_ref}" \
    && echo "Build stamp: $(cat /tmp/buildstamp.txt)" \
    && git clone --depth 1 --no-checkout https://github.com/Belot77/sigenergy-optimizer /tmp/src \
    && cd /tmp/src \
    && git fetch --depth 1 origin "${source_ref}" \
    && git checkout -q --detach FETCH_HEAD \
    && if [ -n "${SOURCE_REF:-}" ]; then [ "$(git rev-parse HEAD)" = "${source_ref}" ]; fi \
    && git rev-parse HEAD > /app/.source_commit \
    && echo "Resolved source commit: $(cat /app/.source_commit)" \
    && cp /tmp/src/requirements.txt /app/requirements.txt \
    && cp -r /tmp/src/app /app/app \
    && cp -r /tmp/src/templates /app/templates \
    && cp -r /tmp/src/static /app/static \
    && cp /tmp/src/.env.example /app/.env.example \
    && sed -i 's/^uvicorn\[standard\]/uvicorn/' /app/requirements.txt \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /app/requirements.txt \
    && rm -rf /tmp/src /tmp/buildstamp.txt /tmp/addon-config.yaml

COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 7123

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget -qO- http://127.0.0.1:7123/api/health >/dev/null || exit 1

CMD ["/run.sh"]
