FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

WORKDIR /app

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    git protobuf-compiler

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . ./

RUN protoc --proto_path=bot/model/gtfs/proto \ 
    --python_out=bot/model/gtfs/proto \
    gtfs-realtime.proto

ENTRYPOINT ["python", "app.py"]