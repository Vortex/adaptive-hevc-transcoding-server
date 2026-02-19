# Changelog

All notable changes to the Adaptive HEVC Transcoding Server package will be documented in this file.

The format is based on Keep a Changelog and this project adheres to Semantic Versioning.

## [0.2.0] - 2026-02-19

### Added
- Docker deployment files to run the transcoding service behind Caddy (`Dockerfile`, `docker-compose.yml`, `Caddyfile`).
- HTTPS reverse proxy on host port `8765` using Caddy `tls internal`.
- Persisted Caddy `/data` and `/config` volumes for stable local CA state.

### Changed
- README now documents Caddy TLS workflow, CA export, and `SSL_CERT_FILE` usage for `adaptive-hevc-converter` clients.

## [0.1.0] - 2026-02-19

### Added
- Initial package scaffold.
- FastAPI app with `/healthz` and `/v1/encode-chunk`.
- CLI entrypoint with `-v/--version`.
- Configurable auth, upload-size limit, timeout, and concurrency controls.

