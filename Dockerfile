FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ffmpeg \
      build-essential \
      libsndfile1 \
      libasound2 \
      libatlas3-base \
      libsqlite3-dev \
      wget \
      ca-certificates && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home appuser

WORKDIR /home/appuser

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/birdnet_uploads && \
    chown -R appuser:appuser /tmp/birdnet_uploads /home/appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
