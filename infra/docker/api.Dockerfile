FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/README.md ./
COPY apps/api/app ./app
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic
COPY data ./data
COPY infra/docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN pip install --upgrade pip && pip install . \
    && chmod +x /usr/local/bin/api-entrypoint.sh
RUN mkdir -p /app/data/artifacts && useradd --create-home --uid 10001 aegis && chown -R aegis:aegis /app
USER aegis
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
