FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JASSIM_HOST=0.0.0.0 \
    JASSIM_PORT=8787 \
    JASSIM_DATA_DIR=/data

WORKDIR /app
# Copy the complete backend package so auth.py and future modules are included.
COPY backend/ /app/

RUN pip install --no-cache-dir 'psycopg[binary]>=3.2,<4' \
    && useradd --system --uid 10001 --create-home jassim \
    && mkdir -p /data \
    && chown -R jassim:jassim /app /data

USER root
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/ready', timeout=3)"

CMD ["python", "/app/entrypoint.py"]
