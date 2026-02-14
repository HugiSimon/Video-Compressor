import logging
import math
import shutil
from pathlib import Path

from video_compressor.model.settings import CompressionSettings
from video_compressor.utils import human_readable_size

log = logging.getLogger("video_compressor.model.compression")


def estimate_gif_size_bytes(
    duration_sec: float,
    src_width: int | None,
    src_height: int | None,
    src_fps: float | None,
    res_choice: str,
    fps_choice: str,
) -> int:
    try:
        effective_fps = float(int(fps_choice)) if fps_choice != "Source" else float(src_fps or 30.0)
    except Exception:
        effective_fps = float(src_fps or 30.0)

    if res_choice == "Source" or not src_width or not src_height:
        out_h = int(src_height or 480)
        base_w = int(src_width or 640)
    else:
        out_h = int(res_choice.replace("p", ""))
        base_w = int(src_width)

    aspect = (float(base_w) / float(src_height or out_h)) if (src_height or out_h) else 1.0
    out_w = int((out_h * aspect) // 2 * 2) or 2

    frames = max(0.0, duration_sec) * max(1.0, effective_fps)
    est = frames * float(out_w) * float(out_h) / 6.0
    est *= 1.05
    return int(max(0, math.ceil(est)))


def compute_upper_bound_size_bytes(
    duration_sec: float, video_kbps: int, include_audio: bool, audio_kbps: int = 128
) -> int:
    chosen_video_kbps = max(50, int(video_kbps))
    planned_video_kbps = max(50, int(math.floor(chosen_video_kbps * 0.97)))
    total_kbps = planned_video_kbps + (audio_kbps if include_audio else 0)
    base_bytes = duration_sec * (total_kbps * 1000.0) / 8.0
    safety_bytes = math.ceil(base_bytes * 1.05)
    return int(safety_bytes)


def estimate_size(
    settings: CompressionSettings,
    duration_sec: float,
    src_width: int | None = None,
    src_height: int | None = None,
    src_fps: float | None = None,
) -> int:
    fmt = settings.output_format.upper()
    if fmt == "GIF":
        return estimate_gif_size_bytes(
            duration_sec, src_width, src_height, src_fps,
            settings.resolution, settings.fps,
        )
    return compute_upper_bound_size_bytes(duration_sec, settings.video_kbps, settings.include_audio)


def unique_output_path(preferred_path: Path) -> Path:
    if not preferred_path.exists():
        return preferred_path
    stem = preferred_path.stem
    suffix = preferred_path.suffix
    parent = preferred_path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def can_write_to_directory(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        test_file = directory / "__write_test__.tmp"
        with open(test_file, "wb") as fh:
            fh.write(b"ok")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def check_disk_space(directory: Path, estimated_bytes: int) -> bool:
    try:
        usage = shutil.disk_usage(str(directory))
        return usage.free >= estimated_bytes
    except Exception:
        log.warning("Could not check disk space for %s", directory)
        return True


def build_output_path(src: str, settings: CompressionSettings) -> Path:
    src_path = Path(src)
    out_dir = src_path.parent
    if not can_write_to_directory(out_dir):
        downloads = Path.home() / "Downloads"
        if can_write_to_directory(downloads):
            out_dir = downloads
        else:
            raise OSError("Cannot write to source directory or Downloads")

    parts: list[str] = []
    if settings.resolution != "Source":
        parts.append(settings.resolution)
    if settings.fps != "Source":
        parts.append(f"{settings.fps}fps")
    parts.append(f"{settings.video_kbps}kbps")
    fmt = settings.output_format.upper()
    if not settings.include_audio and fmt != "GIF":
        parts.append("noaudio")
    tag = "_" + "_".join(parts) if parts else "_compressed"

    ext_map = {"GIF": ".gif", "MKV": ".mkv", "WEBM": ".webm"}
    out_ext = ext_map.get(fmt, ".mp4")

    out_name = f"{src_path.stem}{tag}{out_ext}"
    return unique_output_path(out_dir / out_name)
