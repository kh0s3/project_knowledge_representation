FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY ./requirement/requirements.txt ./requirement/
COPY ./requirement/requirements-nodeps.txt ./requirement/

RUN pip install --no-cache-dir -r ./requirement/requirements.txt
RUN pip install --no-cache-dir --no-deps -r ./requirement/requirements-nodeps.txt

COPY . .

CMD ["tail", "-f", "/dev/null"]