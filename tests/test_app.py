import json
from pathlib import Path

from fastapi.testclient import TestClient

from adaptive_hevc_transcoding_server import app as app_module
from adaptive_hevc_transcoding_server.config import ServerConfig


def _set_config(monkeypatch, cfg: ServerConfig) -> None:
    monkeypatch.setattr(app_module, "config", cfg)
    monkeypatch.setattr(app_module, "job_semaphore", app_module.asyncio.Semaphore(cfg.max_concurrent_jobs))


def test_healthz():
    client = TestClient(app_module.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()


def test_encode_chunk_requires_auth_when_configured(monkeypatch, tmp_path):
    _set_config(
        monkeypatch,
        ServerConfig(
            temp_dir=str(tmp_path),
            auth_token="token",
        ),
    )
    client = TestClient(app_module.app)
    response = client.post(
        "/v1/encode-chunk",
        files={"chunk": ("seg.mkv", b"abc", "video/x-matroska")},
        data={"params": json.dumps({"quality": "original"})},
    )
    assert response.status_code == 401


def test_encode_chunk_success(monkeypatch, tmp_path):
    _set_config(
        monkeypatch,
        ServerConfig(
            temp_dir=str(tmp_path),
            auth_token=None,
            max_upload_bytes=1024 * 1024,
            max_concurrent_jobs=1,
        ),
    )

    def fake_build_encode_command(*, input_file, output_file, ffmpeg_path, params):
        return ["ffmpeg", "-i", input_file, "-y", output_file], {"X-AHC-Encoder": "libx265", "X-AHC-RateControl": "crf"}

    def fake_run_encode_command(cmd, timeout_seconds):
        out = Path(cmd[-1])
        out.write_bytes(b"encoded-bytes")

    def fake_validate_output_exists(output_file):
        assert Path(output_file).exists()

    monkeypatch.setattr(app_module, "build_encode_command", fake_build_encode_command)
    monkeypatch.setattr(app_module, "run_encode_command", fake_run_encode_command)
    monkeypatch.setattr(app_module, "validate_output_exists", fake_validate_output_exists)

    client = TestClient(app_module.app)
    response = client.post(
        "/v1/encode-chunk",
        files={"chunk": ("seg.mkv", b"input-bytes", "video/x-matroska")},
        data={"params": json.dumps({"quality": "original"})},
    )
    assert response.status_code == 200
    assert response.content == b"encoded-bytes"
    assert response.headers["x-ahc-encoder"] == "libx265"
    assert response.headers["content-type"].startswith("video/x-matroska")


def test_encode_chunk_enforces_max_upload(monkeypatch, tmp_path):
    _set_config(
        monkeypatch,
        ServerConfig(
            temp_dir=str(tmp_path),
            max_upload_bytes=3,
        ),
    )
    client = TestClient(app_module.app)
    response = client.post(
        "/v1/encode-chunk",
        files={"chunk": ("seg.mkv", b"1234", "video/x-matroska")},
        data={"params": json.dumps({"quality": "original"})},
    )
    assert response.status_code == 413

