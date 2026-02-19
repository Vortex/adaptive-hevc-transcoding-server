FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install adaptive-hevc-converter from local copy (build context is toolbox root)
COPY adaptive-hevc-converter /tmp/adaptive-hevc-converter
RUN pip install --no-cache-dir /tmp/adaptive-hevc-converter

# Install server and its dependencies
COPY adaptive-hevc-transcoding-server/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY adaptive-hevc-transcoding-server/ ./
RUN pip install --no-cache-dir -e .

EXPOSE 8765

CMD ["adaptive-hevc-transcoding-server", "--host", "0.0.0.0", "--port", "8765"]

