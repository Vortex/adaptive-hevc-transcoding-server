import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from adaptive_hevc_transcoding_server import __version__
from adaptive_hevc_transcoding_server.config import ServerConfig
from adaptive_hevc_transcoding_server.encode import (
    EncodeParams,
    build_encode_command,
    run_encode_command,
    validate_output_exists,
)

logger = logging.getLogger(__name__)
config = ServerConfig.from_env()
job_semaphore = asyncio.Semaphore(config.max_concurrent_jobs)

app = FastAPI(title="Adaptive HEVC Transcoding Server", version=__version__)


@app.middleware("http")
async def request_logging_middleware(request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "Request failed",
            extra={"request_id": request_id, "path": str(request.url.path), "elapsed_ms": elapsed_ms},
        )
        raise
    elapsed_ms = int((time.monotonic() - started) * 1000)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "Request completed",
        extra={
            "request_id": request_id,
            "path": str(request.url.path),
            "method": request.method,
            "status_code": response.status_code,
            "elapsed_ms": elapsed_ms,
        },
    )
    return response


def _require_auth(authorization: Optional[str]) -> None:
    if not config.auth_token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if token != config.auth_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


async def _save_upload_with_limit(upload: UploadFile, output_path: Path, max_bytes: int) -> None:
    total = 0
    with output_path.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=413, detail="Uploaded chunk exceeds configured size limit")
            fh.write(chunk)


def _parse_params(params_str: str) -> EncodeParams:
    try:
        raw = json.loads(params_str)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid params JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="params must be a JSON object")
    return EncodeParams(
        quality=str(raw.get("quality", "original")),
        hardware=bool(raw.get("hardware", False)),
        bitrate_mbps=raw.get("bitrate_mbps"),
        analysis=raw.get("analysis"),
        stream_map=raw.get("stream_map"),
    )


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": __version__})


@app.post("/v1/encode-chunk")
async def encode_chunk(
    chunk: UploadFile = File(...),
    params: str = Form(...),
    authorization: Optional[str] = Header(default=None),
):
    _require_auth(authorization)
    encode_params = _parse_params(params)
    workdir = Path(tempfile.mkdtemp(prefix="ahc-ts-", dir=config.temp_dir))
    input_path = workdir / "input.mkv"
    output_path = workdir / "output.mkv"

    try:
        await _save_upload_with_limit(chunk, input_path, config.max_upload_bytes)
        async with job_semaphore:
            cmd, headers = build_encode_command(
                input_file=str(input_path),
                output_file=str(output_path),
                ffmpeg_path=config.ffmpeg_path,
                params=encode_params,
            )
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, run_encode_command, cmd, config.ffmpeg_timeout_seconds)
            validate_output_exists(str(output_path))

        response_headers = dict(headers)
        response_headers["X-AHC-Version"] = __version__
        return FileResponse(
            path=str(output_path),
            media_type="video/x-matroska",
            filename="encoded_chunk.mkv",
            headers=response_headers,
            background=BackgroundTask(shutil.rmtree, str(workdir), True),
        )
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except TimeoutError as exc:
        logger.warning("Chunk encoding timed out: %s", exc)
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ValueError as exc:
        logger.warning("Invalid encoding request: %s", exc)
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Chunk encoding failed")
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await chunk.close()

