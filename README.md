# Adaptive HEVC Transcoding Server

Chunked HTTP transcoding worker for `adaptive-hevc-converter`.

This server accepts uploaded chunk files, transcodes each chunk to HEVC, and returns the encoded chunk in the response. It is designed to minimize server-side storage by using temporary per-request workspaces.

## Features

- HTTP API for chunk encoding (`/v1/encode-chunk`)
- Optional bearer-token authentication
- Configurable upload-size limits and ffmpeg timeout
- Configurable concurrency limit for encoding jobs
- `-v/--version` support in CLI

## Installation

```bash
pip install -e .
```

## Run

```bash
adaptive-hevc-transcoding-server --host 0.0.0.0 --port 8765
```

Environment variables:

- `AHC_TS_HOST` (default `0.0.0.0`)
- `AHC_TS_PORT` (default `8765`)
- `AHC_TS_FFMPEG_PATH` (default `ffmpeg`)
- `AHC_TS_TEMP_DIR` (default system temp dir)
- `AHC_TS_MAX_CONCURRENT_JOBS` (default `1`)
- `AHC_TS_MAX_UPLOAD_BYTES` (default `1073741824`)
- `AHC_TS_FFMPEG_TIMEOUT_SECONDS` (default `7200`)
- `AHC_TS_AUTH_TOKEN` (optional bearer token)

## API

- `GET /healthz`
- `POST /v1/encode-chunk` multipart form:
  - `chunk`: uploaded matroska chunk
  - `params`: JSON string (at least `quality`, optional `hardware`, `bitrate_mbps`)

Example `params`:

```json
{"quality":"efficient","hardware":true}
```

## Using with adaptive-hevc-converter

```bash
adaptive-hevc-converter input.mp4 \
  --transcode-server http://127.0.0.1:8765 \
  --transcode-server-chunk-duration 300 \
  --transcode-server-concurrency 2
```

With token auth:

```bash
AHC_TS_AUTH_TOKEN="secret-token" adaptive-hevc-transcoding-server
adaptive-hevc-converter input.mp4 \
  --transcode-server http://127.0.0.1:8765 \
  --transcode-server-token secret-token
```

