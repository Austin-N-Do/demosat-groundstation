FROM python:3.12-slim

WORKDIR /app

COPY ground/ingest/requirements.txt ./ground/ingest/requirements.txt
RUN pip install --no-cache-dir -r ground/ingest/requirements.txt

COPY shared/ ./shared/
COPY ground/ ./ground/

CMD ["python", "-m", "ground.ingest.main"]
