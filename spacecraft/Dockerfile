FROM python:3.12-slim

WORKDIR /app

COPY spacecraft/requirements.txt ./spacecraft/requirements.txt
RUN pip install --no-cache-dir -r spacecraft/requirements.txt

COPY shared/ ./shared/
COPY spacecraft/ ./spacecraft/

CMD ["python", "-m", "spacecraft.main"]
