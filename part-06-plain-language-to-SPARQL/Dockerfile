FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV HOST=0.0.0.0 PORT=8000 KG_DIR=/data STATE_DIR=/state PRELOAD=1 PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "[ -f /state/void.ttl ] || python make_void.py; exec python serve.py"]