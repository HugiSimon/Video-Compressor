import json
import logging
import math
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable

from video_compressor.model.settings import CompressionSettings, MediaInfo
from video_compressor.utils import app_base_dir

log = logging.getLogger("video_compressor.model.ffmpeg")


def find_executable(executable_name: str) -> str | None:
    local_path = app_base_dir() / (
        executable_name + (".exe" if os.name == "nt" and not executable_name.endswith(".exe") else "")
    )
    if local_path.exists():
        return str(local_path)
    found = shutil.which(executable_name)
    if found:
        return found
    if os.name == "nt" and not executable_name.endswith(".exe"):
        found = shutil.which(executable_name + ".exe")
        if found:
            return found
    return None


def ensure_ffmpeg_tools() -> tuple[str, str]:
    ffmpeg_path = find_executable("ffmpeg")
    ffprobe_path = find_executable("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        raise FileNotFoundError(
            "FFmpeg n'est pas disponible.\n\n"
            "Veuillez placer 'ffmpeg.exe' et 'ffprobe.exe' dans le même dossier que cet EXE,\n"
            "ou bien installer FFmpeg et l'ajouter au PATH système."
        )
    log.info("ffmpeg=%s  ffprobe=%s", ffmpeg_path, ffprobe_path)
    return ffmpeg_path, ffprobe_path


def probe_media(ffprobe_path: str, input_path: str) -> MediaInfo:
    cmd = [
        ffprobe_path, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate",
        "-show_entries", "format=duration",
        "-of", "json",
        input_path,
    ]
    log.debug("probe cmd: %s", cmd)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe a échoué: {proc.stderr}")
    data = json.loads(proc.stdout or "{}")
    duration = 0.0
    width = None
    height = None
    fps = None
    try:
        if "format" in data and "duration" in data["format"]:
            duration = float(data["format"]["duration"])
        if "streams" in data and data["streams"]:
            s0 = data["streams"][0]
            width = int(s0.get("width", 0) or 0)
            height = int(s0.get("height", 0) or 0)
            afr = s0.get("avg_frame_rate") or "0/1"
            num, den = (afr.split("/") + ["1"])[:2]
            try:
                num_f = float(num)
                den_f = float(den)
                fps = num_f / den_f if den_f else 0.0
            except ValueError:
                fps = 0.0
    except Exception as exc:
        raise RuntimeError(f"Analyse des métadonnées impossible: {exc}")
    info = MediaInfo(duration=max(duration, 0.0), width=width, height=height, fps=fps)
    log.info("probed %s -> %s", input_path, info)
    return info


def build_ffmpeg_cmd(
    settings: CompressionSettings, src: str, dst: str, ffmpeg_path: str
) -> list[str]:
    video_kbps = max(50, settings.video_kbps)
    planned_video_kbps = max(50, int(math.floor(video_kbps * 0.97)))
    fmt = settings.output_format.upper()
    dst_lower = dst.lower()

    # GIF branch
    if fmt == "GIF" or dst_lower.endswith(".gif"):
        pre_filters: list[str] = []
        if settings.resolution != "Source":
            target_h = int(settings.resolution.replace("p", ""))
            pre_filters.append(f"scale='trunc(oh*a/2)*2':{target_h}")
        if settings.fps != "Source":
            try:
                r_value = int(settings.fps)
                pre_filters.insert(0, f"fps={r_value}")
            except ValueError:
                pass
        if pre_filters:
            pre = ",".join(pre_filters)
            fc = f"[0:v]{pre},split[v0][v1];[v0]palettegen=stats_mode=full[p];[v1][p]paletteuse=dither=bayer:bayer_scale=5"
        else:
            fc = "[0:v]split[v0][v1];[v0]palettegen=stats_mode=full[p];[v1][p]paletteuse=dither=bayer:bayer_scale=5"
        return [
            ffmpeg_path, "-y", "-hide_banner", "-v", "warning",
            "-i", src, "-filter_complex", fc, "-an", dst,
        ]

    # Video filters
    vf_filters: list[str] = []
    if settings.resolution != "Source":
        target_h = int(settings.resolution.replace("p", ""))
        vf_filters.append(f"scale='trunc(oh*a/2)*2':{target_h}")

    r_args: list[str] = []
    if settings.fps != "Source":
        try:
            r_value = int(settings.fps)
            r_args = ["-r", str(r_value)]
        except ValueError:
            pass

    vf_args = ["-vf", ",".join(vf_filters)] if vf_filters else []

    # Audio
    if settings.include_audio:
        audio_args = ["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000"]
    else:
        audio_args = ["-an"]

    # Codec
    if fmt == "WEBM" or dst_lower.endswith(".webm"):
        vcodec_args = [
            "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p",
            "-b:v", f"{planned_video_kbps}k",
            "-maxrate", f"{video_kbps}k",
            "-bufsize", f"{video_kbps * 2}k",
            "-row-mt", "1", "-deadline", "good",
        ]
        container_tail: list[str] = []
    else:
        vcodec_args = [
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-preset", "medium",
            "-b:v", f"{planned_video_kbps}k",
            "-maxrate", f"{video_kbps}k",
            "-bufsize", f"{video_kbps * 2}k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
        ]
        if dst_lower.endswith((".mp4", ".m4v", ".mov")):
            container_tail = ["-movflags", "+faststart"]
        else:
            container_tail = []

    return [
        ffmpeg_path, "-y", "-hide_banner", "-v", "warning",
        "-i", src, *vf_args, *r_args, *vcodec_args, *audio_args, *container_tail, dst,
    ]


def run_ffmpeg(
    cmd: list[str],
    duration_sec: float,
    cancel_event: threading.Event,
    on_progress: Callable[[float], None],
    on_done: Callable[[int, str], None],
) -> None:
    """Run an FFmpeg command with real-time progress and cancellation support.

    Must be called from a worker thread. Callbacks will be called from that thread;
    the controller is responsible for dispatching to the UI thread.
    """
    # Insert -progress pipe:1 right after the executable
    run_cmd = list(cmd)
    run_cmd.insert(1, "-progress")
    run_cmd.insert(2, "pipe:1")

    log.info("ffmpeg cmd: %s", run_cmd)

    try:
        proc = subprocess.Popen(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as exc:
        log.error("Failed to start ffmpeg: %s", exc)
        on_done(-1, str(exc))
        return

    stderr_lines: list[str] = []

    def _read_stderr():
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_lines.append(line)

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if cancel_event.is_set():
                proc.terminate()
                log.info("FFmpeg cancelled by user")
                break
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    us = int(line.split("=", 1)[1])
                    if duration_sec > 0:
                        fraction = min(1.0, max(0.0, (us / 1_000_000) / duration_sec))
                        on_progress(fraction)
                except (ValueError, ZeroDivisionError):
                    pass
    except Exception:
        pass

    proc.wait()
    stderr_thread.join(timeout=5)
    stderr_text = "".join(stderr_lines)

    if cancel_event.is_set():
        log.info("FFmpeg process terminated (cancel), rc=%d", proc.returncode)
        on_done(-2, "Cancelled")
    else:
        log.info("FFmpeg done, rc=%d", proc.returncode)
        on_done(proc.returncode, stderr_text)
