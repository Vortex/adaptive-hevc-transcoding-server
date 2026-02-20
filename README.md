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

## Run (direct app, no TLS)

```bash
adaptive-hevc-transcoding-server --host 0.0.0.0 --port 8765
```

Environment variables:

- `AHC_TS_HOST` (default `0.0.0.0`)
- `AHC_TS_PORT` (default `8765`)
- `AHC_TS_FFMPEG_PATH` (default `ffmpeg`)
- `AHC_TS_TEMP_DIR` (default system temp dir)
- `AHC_TS_MAX_CONCURRENT_JOBS` (default `1`) — max encodes at once; each encode uses all CPU cores (x265 `pools=+`). Increase to match client `--transcode-server-concurrency` if you want parallel chunk encodes.
- `AHC_TS_MAX_UPLOAD_BYTES` (default `1073741824`)
- `AHC_TS_FFMPEG_TIMEOUT_SECONDS` (default `7200`)
- `AHC_TS_AUTH_TOKEN` (optional bearer token)

## Run with Caddy TLS on port 8765

This repository includes a `docker-compose.yml` + `Caddyfile` that puts the app behind Caddy with `tls internal`.

- Client URL becomes: `https://<transcoder_local_ip>:8765`
- Caddy owns host port `8765`.
- The Python app is only reachable inside the Docker network.

### 1) Set the host/IP that clients will use (required for HTTPS)

**On the machine where Docker runs**, set `TRANSCODER_HOST` to the **exact** IP or hostname your client uses in the URL. If you use `https://192.168.3.18:8765`, set:

```bash
export TRANSCODER_HOST=192.168.3.18
```

Or copy `.env.example` to `.env` and set `TRANSCODER_HOST` there. If this doesn’t match the client URL, Caddy won’t have a matching cert and you’ll get `TLSV1_ALERT_INTERNAL_ERROR`.

### 2) Start services

```bash
docker compose up -d --build
```

### 3) Why do I need a certificate? (browsers don’t ask for one)

Normal HTTPS sites use certificates signed by **public** CAs (e.g. Let’s Encrypt). Your OS and browser already trust those, so no extra step.

With **`tls internal`**, Caddy creates its **own** CA and signs the server cert with it. That CA is not in your system trust store. In a **browser** you get a warning and click “Advanced” → “Proceed” — you’re making a one-time exception. **Scripts** (Python, curl) can’t do that; they either need to be told which CA to trust, or you disable verification (insecure). So we need to give the converter Caddy’s root cert once (or install it into the system store so nothing needs to be passed).

### 4) Where is the certificate and how to get it

The file lives **inside** the Caddy container. Caddy creates it on **first use** (first request to `https://...:8765`). If the path doesn’t exist yet, trigger that once (e.g. open `https://<TRANSCODER_HOST>:8765/healthz` in the browser and accept the warning), then copy it out:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
```

You now have `./caddy-root.crt` on your machine. Use it as below, or install it into your **system** trust store so you never need to pass it again (e.g. on Debian/Ubuntu: `sudo cp caddy-root.crt /usr/local/share/ca-certificates/caddy-local.crt` then `sudo update-ca-certificates`).

### 5) Use trusted HTTPS from adaptive-hevc-converter

Either set the CA once in the environment, or pass it on the command line (no need for `SSL_CERT_FILE`):

```bash
# Option A: env (e.g. in ~/.bashrc)
export AHC_TRANSCODE_SERVER_CA=/path/to/caddy-root.crt

# Option B: flag
adaptive-hevc-converter input.mp4 \
  --transcode-server https://192.168.1.50:8765 \
  --transcode-server-ca ./caddy-root.crt
```

With token auth:

```bash
adaptive-hevc-converter input.mp4 \
  --transcode-server https://192.168.1.50:8765 \
  --transcode-server-ca ./caddy-root.crt \
  --transcode-server-token secret-token
```

### 6) If you see `TLSV1_ALERT_INTERNAL_ERROR`

1. **On the server** (where Docker runs), `TRANSCODER_HOST` must be set to the same IP the client uses (e.g. `192.168.3.18`) **before** starting Caddy. If it was unset or wrong, Caddy’s cert and `default_sni` are for the wrong host. Set it, then restart:
   ```bash
   export TRANSCODER_HOST=192.168.3.18
   docker compose down && docker compose up -d
   ```
2. If you already had Caddy running with a different host, remove the volume so Caddy issues a new cert for the new host: `docker compose down -v`, set `TRANSCODER_HOST`, then `docker compose up -d`. Re-export the root cert and point the client at it again.

### 7) Verify endpoint with curl

```bash
curl --cacert ./caddy-root.crt https://192.168.1.50:8765/healthz
```

## API

- `GET /healthz`
- `POST /v1/encode-chunk` multipart form:
  - `chunk`: uploaded matroska chunk
  - `params`: JSON string (at least `quality`, optional `hardware`, `bitrate_mbps`)

Example `params`:

```json
{"quality":"efficient","hardware":true}
```

## Using with adaptive-hevc-converter (direct HTTP)

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

