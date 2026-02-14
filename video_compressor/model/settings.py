from dataclasses import dataclass


@dataclass
class CompressionSettings:
    resolution: str = "Source"
    fps: str = "Source"
    video_kbps: int = 1500
    include_audio: bool = True
    output_format: str = "MP4"


@dataclass
class MediaInfo:
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    fps: float | None = None
