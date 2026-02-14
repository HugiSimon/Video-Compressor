import logging
import os
import threading
from pathlib import Path

from video_compressor.i18n.strings import t
from video_compressor.model.compression import (
    build_output_path,
    check_disk_space,
    estimate_size,
)
from video_compressor.model.ffmpeg import (
    build_ffmpeg_cmd,
    ensure_ffmpeg_tools,
    probe_media,
    run_ffmpeg,
)
from video_compressor.model.settings import CompressionSettings, MediaInfo
from video_compressor.utils import human_readable_size
from video_compressor.view.main_window import MainView

log = logging.getLogger("video_compressor.controller")


class AppController:
    def __init__(self, view: MainView) -> None:
        self.view = view
        self.ffmpeg_path: str | None = None
        self.ffprobe_path: str | None = None
        self.media_info = MediaInfo()
        self._cancel_event = threading.Event()
        self._current_dst: str | None = None

        # Discover FFmpeg
        try:
            self.ffmpeg_path, self.ffprobe_path = ensure_ffmpeg_tools()
        except FileNotFoundError as exc:
            self.view.show_error(t("ffmpeg_missing_title"), str(exc))
            self.view.destroy()
            return

        # Wire callbacks
        self.view.on_browse = self._handle_browse
        self.view.on_compress = self._handle_compress
        self.view.on_cancel = self._handle_cancel
        self.view.on_setting_changed = self._handle_setting_changed

        # If input already set (drag-and-drop), probe it
        if self.view.input_path_var.get():
            self._on_input_changed()
        else:
            self.view.after(100, self._handle_browse)

    def _get_settings(self) -> CompressionSettings:
        return CompressionSettings(
            resolution=self.view.resolution_var.get(),
            fps=self.view.fps_var.get(),
            video_kbps=self.view.video_kbps_var.get(),
            include_audio=self.view.include_audio_var.get(),
            output_format=self.view.format_var.get(),
        )

    def _handle_browse(self) -> None:
        path = self.view.ask_open_file()
        if path:
            self.view.input_path_var.set(path)
            self._on_input_changed()

    def _on_input_changed(self) -> None:
        path = self.view.input_path_var.get()
        if not path or not os.path.exists(path):
            self.view.show_warning(t("file_not_found"), t("select_valid_video"))
            return
        try:
            self.media_info = probe_media(self.ffprobe_path, path)
        except Exception as exc:
            self.view.show_error(t("analysis_error"), str(exc))
            self.media_info = MediaInfo()
        self._update_estimate()

    def _handle_setting_changed(self) -> None:
        self._update_estimate()

    def _update_estimate(self) -> None:
        path = self.view.input_path_var.get()
        if not path or self.media_info.duration <= 0:
            self.view.set_estimate_text(f"{t('estimate_prefix')}: -")
            return
        settings = self._get_settings()
        est_bytes = estimate_size(
            settings, self.media_info.duration,
            self.media_info.width, self.media_info.height, self.media_info.fps,
        )
        self.view.set_estimate_text(
            f"{t('estimate_prefix')}: {human_readable_size(est_bytes)}"
        )

    def _handle_compress(self) -> None:
        src = self.view.input_path_var.get()
        if not src or not os.path.exists(src):
            self.view.show_warning(t("file_not_found"), t("select_valid_video"))
            return

        settings = self._get_settings()

        # Build output path
        try:
            out_path = build_output_path(src, settings)
        except OSError:
            self.view.show_error(t("invalid_location"), t("cannot_write"))
            return

        # Estimate size
        est_bytes = 0
        if self.media_info.duration > 0:
            est_bytes = estimate_size(
                settings, self.media_info.duration,
                self.media_info.width, self.media_info.height, self.media_info.fps,
            )

        # Check disk space
        if est_bytes > 0 and not check_disk_space(out_path.parent, est_bytes):
            if not self.view.ask_confirm(t("disk_space_title"), t("disk_space_message")):
                return

        # Confirm
        if est_bytes > 0:
            human = human_readable_size(est_bytes)
            if not self.view.ask_confirm(t("confirmation"), t("confirm_size", size=human)):
                return

        # Build command
        dst = str(out_path)
        self._current_dst = dst
        cmd = build_ffmpeg_cmd(settings, src, dst, self.ffmpeg_path)

        # Show progress and start
        self._cancel_event.clear()
        self.view.show_progress()

        def worker():
            run_ffmpeg(
                cmd,
                self.media_info.duration,
                self._cancel_event,
                on_progress=self._on_progress,
                on_done=lambda rc, stderr: self._on_ffmpeg_done(rc, dst, stderr),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _handle_cancel(self) -> None:
        log.info("User requested cancellation")
        self._cancel_event.set()

    def _on_progress(self, fraction: float) -> None:
        self.view.after(0, self.view.update_progress, fraction)

    def _on_ffmpeg_done(self, returncode: int, dst: str, stderr: str) -> None:
        def _finish():
            self.view.close_progress()

            if returncode == -2:
                # Cancelled — clean up partial file
                try:
                    p = Path(dst)
                    if p.exists():
                        p.unlink()
                        log.info("Removed partial file: %s", dst)
                except Exception:
                    pass
                self.view.show_info(t("cancelled_title"), t("cancelled_message"))
                return

            if returncode == 0 and os.path.exists(dst):
                size_bytes = os.path.getsize(dst)
                human = human_readable_size(size_bytes)
                log.info("Compression done: %s (%s)", dst, human)
                self.view.show_completion(dst, human)
            else:
                log.error("FFmpeg failed (rc=%d): %s", returncode, stderr[:500])
                self.view.show_error(
                    t("fail_title"),
                    t("fail_message", details=stderr[:2000]),
                )

        self.view.after(0, _finish)
