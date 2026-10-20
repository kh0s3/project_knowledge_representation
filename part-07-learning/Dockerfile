FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir torch-geometric==2.8.0.post1 pykeen==1.11.1 numpy==2.3.5 flask==3.1.0 werkzeug==3.1.3

COPY . .

EXPOSE 5000

CMD ["python", "ui.py"]
