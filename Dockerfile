FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QUEUEMAIL_DATA=/data \
    QUEUEMAIL_HOST=0.0.0.0 \
    QUEUEMAIL_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py serve.py np_rules.json server.json signature.txt ./
COPY templates ./templates

RUN mkdir -p /data/logs \
    && cp signature.txt /data/signature.txt \
    && useradd --create-home --uid 1000 queuemail \
    && chown -R queuemail:queuemail /app /data

USER queuemail

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=3)"

CMD ["python", "serve.py"]
