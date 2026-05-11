FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# system deps for Pillow/numpy (libjpeg/zlib) — slim already has zlib; libjpeg for JPEG
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app.py ./
COPY lib ./lib
COPY assets ./assets
COPY public ./public

EXPOSE 8000
ENV SQLITE_PATH=/data/pure-design.db
VOLUME ["/data"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
