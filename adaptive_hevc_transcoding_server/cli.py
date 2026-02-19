import argparse

import uvicorn

from adaptive_hevc_transcoding_server import __version__
from adaptive_hevc_transcoding_server.config import ServerConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adaptive-hevc-transcoding-server",
        description="Chunked HTTP transcoding worker for Adaptive HEVC Converter.",
    )
    parser.add_argument("--host", default=None, help="Bind host (default from env or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default from env or 8765)")
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable/disable auto reload (default: disabled)",
    )
    parser.add_argument("-v", "--version", action="store_true", help="Print version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.version:
        print(__version__)
        return 0

    cfg = ServerConfig.from_env()
    host = args.host or cfg.host
    port = args.port or cfg.port

    uvicorn.run(
        "adaptive_hevc_transcoding_server.app:app",
        host=host,
        port=port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

