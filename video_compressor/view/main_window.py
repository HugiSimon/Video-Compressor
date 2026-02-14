import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable

from video_compressor.i18n.strings import t
from video_compressor.view.widgets import BitrateControl

log = logging.getLogger("video_compressor.view.main_window")


class MainView(tk.Tk):
    def __init__(self, initial_input: str | None = None) -> None:
        super().__init__()
        self.title(t("app_title"))
        self.minsize(560, 340)

        # Tk variables
        self.input_path_var = tk.StringVar(value=initial_input or "")
        self.resolution_var = tk.StringVar(value="Source")
        self.fps_var = tk.StringVar(value="Source")
        self.video_kbps_var = tk.IntVar(value=1500)
        self.include_audio_var = tk.BooleanVar(value=True)
        self.format_var = tk.StringVar(value="MP4")
        self.estimate_label_var = tk.StringVar(value=f"{t('estimate_prefix')}: -")

        # Callbacks set by controller
        self.on_browse: Callable[[], None] | None = None
        self.on_compress: Callable[[], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.on_setting_changed: Callable[[], None] | None = None

        # Progress dialog references
        self._progress_dlg: tk.Toplevel | None = None
        self._progress_bar: ttk.Progressbar | None = None
        self._progress_label: ttk.Label | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 8}

        # Input chooser
        input_frame = ttk.LabelFrame(self, text=t("source_video"))
        input_frame.pack(fill="x", **padding)
        input_entry = ttk.Entry(input_frame, textvariable=self.input_path_var)
        input_entry.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=8)
        browse_btn = ttk.Button(
            input_frame, text=t("choose"),
            command=lambda: self.on_browse() if self.on_browse else None,
        )
        browse_btn.pack(side="left", padx=(0, 10), pady=8)

        # Settings frame
        settings = ttk.LabelFrame(self, text=t("compression_settings"))
        settings.pack(fill="x", **padding)

        # Resolution
        ttk.Label(settings, text=t("resolution")).grid(row=0, column=0, sticky="w", padx=10, pady=6)
        res_combo = ttk.Combobox(
            settings, state="readonly", textvariable=self.resolution_var,
            values=["Source", "1080p", "720p", "480p", "360p", "240p"],
        )
        res_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        res_combo.bind("<<ComboboxSelected>>", lambda e: self._fire_setting_changed())

        # FPS
        ttk.Label(settings, text="FPS").grid(row=0, column=2, sticky="w", padx=10, pady=6)
        fps_combo = ttk.Combobox(
            settings, state="readonly", textvariable=self.fps_var,
            values=["Source", "24", "25", "30", "50", "60"],
        )
        fps_combo.grid(row=0, column=3, sticky="ew", padx=10, pady=6)
        fps_combo.bind("<<ComboboxSelected>>", lambda e: self._fire_setting_changed())

        # Video bitrate
        ttk.Label(settings, text=t("video_kbps")).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        self.bitrate_control = BitrateControl(
            settings, variable=self.video_kbps_var,
            on_change=self._fire_setting_changed,
        )
        self.bitrate_control.grid(row=1, column=1, columnspan=4, sticky="ew", padx=10, pady=6)

        # Include audio
        self.audio_chk = ttk.Checkbutton(
            settings, text=t("keep_audio"), variable=self.include_audio_var,
            command=self._fire_setting_changed,
        )
        self.audio_chk.grid(row=2, column=0, sticky="w", padx=10, pady=6)

        # Format selector
        ttk.Label(settings, text=t("format")).grid(row=2, column=2, sticky="w", padx=10, pady=6)
        format_combo = ttk.Combobox(
            settings, state="readonly", textvariable=self.format_var,
            values=["MP4", "MKV", "WEBM", "GIF"],
        )
        format_combo.grid(row=2, column=3, sticky="ew", padx=10, pady=6)
        format_combo.bind("<<ComboboxSelected>>", lambda e: self._on_format_changed())

        # GIF hint
        self.gif_hint_label = ttk.Label(settings, text=t("gif_hint"))
        self.gif_hint_label.grid(row=3, column=0, columnspan=5, sticky="w", padx=10, pady=(0, 6))
        self.gif_hint_label.grid_remove()

        # Estimate label
        estimate_frame = ttk.Frame(self)
        estimate_frame.pack(fill="x", **padding)
        ttk.Label(estimate_frame, textvariable=self.estimate_label_var).pack(side="left", padx=10)

        # Action buttons
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **padding)
        compress_btn = ttk.Button(
            action_frame, text=t("compress"),
            command=lambda: self.on_compress() if self.on_compress else None,
        )
        compress_btn.pack(side="right", padx=10)

        # Grid config
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        # Initialize format-dependent state
        self._on_format_changed()

    def _fire_setting_changed(self) -> None:
        if self.on_setting_changed:
            self.on_setting_changed()

    def _on_format_changed(self) -> None:
        fmt = (self.format_var.get() or "MP4").upper()
        if fmt == "GIF":
            self.include_audio_var.set(False)
            self.audio_chk.state(["disabled"])
            self.gif_hint_label.grid()
            self.bitrate_control.set_state(False)
        else:
            self.audio_chk.state(["!disabled"])
            self.gif_hint_label.grid_remove()
            self.bitrate_control.set_state(True)
        self._fire_setting_changed()

    # --- Methods called by controller ---

    def set_estimate_text(self, text: str) -> None:
        self.estimate_label_var.set(text)

    def show_progress(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title(t("compressing"))
        dlg.resizable(False, False)

        ttk.Label(dlg, text=t("compressing_detail")).pack(padx=16, pady=(12, 6))

        self._progress_label = ttk.Label(dlg, text="0 %")
        self._progress_label.pack(padx=16, pady=(0, 4))

        pb = ttk.Progressbar(dlg, mode="determinate", maximum=1.0, length=350)
        pb.pack(fill="x", padx=16, pady=(0, 8))
        pb["value"] = 0.0

        cancel_btn = ttk.Button(
            dlg, text=t("cancel"),
            command=lambda: self.on_cancel() if self.on_cancel else None,
        )
        cancel_btn.pack(pady=(0, 12))

        dlg.transient(self)
        dlg.grab_set()
        dlg.protocol("WM_DELETE_WINDOW", lambda: self.on_cancel() if self.on_cancel else None)

        self._progress_dlg = dlg
        self._progress_bar = pb

    def update_progress(self, fraction: float) -> None:
        if self._progress_bar:
            self._progress_bar["value"] = fraction
        if self._progress_label:
            self._progress_label.configure(text=f"{int(fraction * 100)} %")

    def close_progress(self) -> None:
        if self._progress_dlg:
            try:
                self._progress_dlg.grab_release()
            except Exception:
                pass
            self._progress_dlg.destroy()
            self._progress_dlg = None
            self._progress_bar = None
            self._progress_label = None

    def show_error(self, title: str, message: str) -> None:
        messagebox.showerror(title, message)

    def show_warning(self, title: str, message: str) -> None:
        messagebox.showwarning(title, message)

    def show_info(self, title: str, message: str) -> None:
        messagebox.showinfo(title, message)

    def ask_confirm(self, title: str, message: str) -> bool:
        return messagebox.askokcancel(title, message)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message)

    def ask_open_file(self) -> str | None:
        filetypes = [
            (t("videos_filter"), "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"),
            (t("all_files_filter"), "*.*"),
        ]
        path = filedialog.askopenfilename(title=t("choose_video"), filetypes=filetypes)
        return path or None

    def show_completion(self, dst: str, size_text: str) -> None:
        msg = t("done_message", path=dst, size=size_text)
        if self.ask_yes_no(t("done_title"), msg):
            try:
                if os.name == "nt":
                    import subprocess
                    subprocess.Popen(["explorer", "/select,", dst])
                else:
                    import subprocess
                    subprocess.Popen(["open", "-R", dst])
            except Exception:
                pass
