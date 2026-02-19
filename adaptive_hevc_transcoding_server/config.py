import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    ffmpeg_path: str = "ffmpeg"
    temp_dir: str = tempfile.gettempdir()
    max_concurrent_jobs: int = 1
    max_upload_bytes: int = 1024 * 1024 * 1024
    ffmpeg_timeout_seconds: int = 7200
    auth_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ServerConfig":
        temp_dir = os.getenv("AHC_TS_TEMP_DIR", tempfile.gettempdir())
        Path(temp_dir).mkdir(parents=True, exist_ok=True)
        token = os.getenv("AHC_TS_AUTH_TOKEN")
        return cls(
            host=os.getenv("AHC_TS_HOST", "0.0.0.0"),
            port=int(os.getenv("AHC_TS_PORT", "8765")),
            ffmpeg_path=os.getenv("AHC_TS_FFMPEG_PATH", "ffmpeg"),
            temp_dir=temp_dir,
            max_concurrent_jobs=max(1, int(os.getenv("AHC_TS_MAX_CONCURRENT_JOBS", "1"))),
            max_upload_bytes=max(1, int(os.getenv("AHC_TS_MAX_UPLOAD_BYTES", str(1024 * 1024 * 1024)))),
            ffmpeg_timeout_seconds=max(1, int(os.getenv("AHC_TS_FFMPEG_TIMEOUT_SECONDS", "7200"))),
            auth_token=token if token else None,
        )

