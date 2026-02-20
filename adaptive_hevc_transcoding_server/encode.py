import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from adaptive_hevc_converter.converter import AdaptiveHEVCConverter
from adaptive_hevc_converter.presets import QualityPresets


@dataclass
class EncodeParams:
    quality: str = "original"
    hardware: bool = False
    bitrate_mbps: Optional[float] = None
    analysis: Optional[Dict[str, Any]] = None
    stream_map: Optional[Dict[str, Any]] = None


def _detect_stream_intent(converter: AdaptiveHEVCConverter, input_file: str) -> tuple[Optional[int], Optional[int], bool]:
    streams = converter.analyzer.get_streams(input_file)
    main_video_index: Optional[int] = None
    cover_video_index: Optional[int] = None
    has_mov_text_subs = False

    for stream in streams:
        if stream.get("codec_type") != "video":
            if stream.get("codec_type") == "subtitle":
                codec_name = (stream.get("codec_name") or "").lower()
                if codec_name == "mov_text":
                    has_mov_text_subs = True
            continue
        disposition = stream.get("disposition", {}) or {}
        idx = stream.get("index")
        if idx is None:
            continue
        if disposition.get("attached_pic", 0) == 1:
            cover_video_index = idx
        elif main_video_index is None:
            main_video_index = idx

    return main_video_index, cover_video_index, has_mov_text_subs


def build_encode_command(
    *,
    input_file: str,
    output_file: str,
    ffmpeg_path: str,
    params: EncodeParams,
) -> tuple[list[str], Dict[str, str]]:
    converter = AdaptiveHEVCConverter(ffmpeg_path=ffmpeg_path, hardware_accel=params.hardware)
    analysis = converter.analyzer.analyze_video(input_file)
    preset_obj = QualityPresets.get_preset(params.quality)
    rate_control_mode = getattr(preset_obj, "rate_control", "crf") or "crf"
    x265_params = QualityPresets.get_x265_params(params.quality, analysis)
    # Use all CPU cores for encoding (pools=+ = all cores on NUMA node). Without this,
    # libx265 may default to 2 threads and you see only ~200% CPU on the server.
    if ":pools=" not in x265_params and "pools=" not in x265_params:
        x265_params = f"{x265_params}:pools=+"
    ffmpeg_preset = QualityPresets.get_ffmpeg_preset(params.quality, analysis)

    crf: Optional[int] = None
    target_bitrate_bps: Optional[int] = None
    target_bitrate_mbps_effective: Optional[float] = None

    if rate_control_mode == "crf":
        crf = QualityPresets.calculate_adaptive_crf(params.quality, analysis)
    else:
        if params.bitrate_mbps is None:
            default_mbps = getattr(preset_obj, "default_bitrate_mbps", None)
            params.bitrate_mbps = float(default_mbps) if default_mbps is not None else 1.0
        target_bitrate_mbps_effective = float(params.bitrate_mbps)
        if target_bitrate_mbps_effective <= 0:
            raise ValueError("bitrate_mbps must be > 0 for capped preset")
        target_bitrate_bps = int(round(target_bitrate_mbps_effective * 1_000_000))
        x265_params = f"{x265_params}:nal-hrd=cbr"

    use_nvenc = converter.hardware_accel and converter.check_nvenc_available()
    if use_nvenc:
        converter._validate_nvenc_quality_preset(params.quality)
    if rate_control_mode == "crf" and use_nvenc and crf is not None:
        crf = converter._apply_experimental_nvenc_adjustments(
            quality_preset=params.quality,
            cq=crf,
            use_nvenc=use_nvenc,
        )

    main_video_index, cover_video_index, has_mov_text_subs = _detect_stream_intent(converter, input_file)
    cmd = converter._build_ffmpeg_command(
        input_file=input_file,
        output_file=output_file,
        crf=crf,
        preset=ffmpeg_preset,
        quality_preset=params.quality,
        x265_params=x265_params,
        use_nvenc=use_nvenc,
        is_10bit=analysis.get("is_10bit", False),
        main_video_index=main_video_index,
        cover_video_index=cover_video_index,
        convert_mov_text_subs=has_mov_text_subs,
        rate_control_mode=rate_control_mode,
        target_bitrate_bps=target_bitrate_bps,
    )
    headers = {
        "X-AHC-Encoder": "hevc_nvenc" if use_nvenc else "libx265",
        "X-AHC-RateControl": rate_control_mode,
    }
    if rate_control_mode == "crf" and crf is not None:
        headers["X-AHC-CRF"] = str(crf)
    if rate_control_mode == "cbr" and target_bitrate_bps is not None:
        headers["X-AHC-BitrateBps"] = str(target_bitrate_bps)
    return cmd, headers


def run_encode_command(cmd: list[str], timeout_seconds: int) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"ffmpeg timed out after {timeout_seconds}s") from exc
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}: {result.stderr}")


def validate_output_exists(output_file: str) -> None:
    if not Path(output_file).exists():
        raise RuntimeError("encoding finished without producing output file")

