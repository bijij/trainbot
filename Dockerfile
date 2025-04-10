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

COPY bot/gtfs/proto/gtfs-realtime.proto ./bot/gtfs/proto/

RUN protoc --proto_path=bot/gtfs/proto \ 
    --python_out=bot/gtfs/proto \
    gtfs-realtime.proto

COPY . ./

ENTRYPOINT ["python", "-O", "app.py"]