FROM python:3.12-slim

WORKDIR /app

COPY ground/api/requirements.txt ./ground/api/requirements.txt
RUN pip install --no-cache-dir -r ground/api/requirements.txt

COPY shared/ ./shared/
COPY ground/ ./ground/

CMD ["uvicorn", "ground.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
