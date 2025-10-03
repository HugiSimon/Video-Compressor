import os
import sys
import json
import math
import shutil
import subprocess
from pathlib import Path
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) is True


def app_base_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_executable(executable_name: str) -> str | None:
    # 1) Check adjacent to the app (portable ffmpeg.exe/ffprobe.exe placed next to the EXE)
    local_path = app_base_dir() / (executable_name + (".exe" if os.name == "nt" and not executable_name.endswith(".exe") else ""))
    if local_path.exists():
        return str(local_path)
    # 2) Check PATH
    found = shutil.which(executable_name)
    if found:
        return found
    # 3) Also try with .exe explicitly on Windows
    if os.name == "nt" and not executable_name.endswith(".exe"):
        found = shutil.which(executable_name + ".exe")
        if found:
            return found
    return None


def ensure_ffmpeg_tools() -> tuple[str, str]:
    ffmpeg_path = find_executable("ffmpeg")
    ffprobe_path = find_executable("ffprobe")
    if not ffmpeg_path or not ffprobe_path:
        message = (
            "FFmpeg n'est pas disponible.\n\n"
            "Veuillez placer 'ffmpeg.exe' et 'ffprobe.exe' dans le même dossier que cet EXE,\n"
            "ou bien installer FFmpeg et l'ajouter au PATH système."
        )
        raise FileNotFoundError(message)
    return ffmpeg_path, ffprobe_path


def probe_media(ffprobe_path: str, input_path: str) -> dict:
    # Use ffprobe to get duration, width, height, frame rate
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        input_path,
    ]
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
    return {
        "duration": max(duration, 0.0),
        "width": width,
        "height": height,
        "fps": fps,
    }


def human_readable_size(bytes_count: int) -> str:
    # Decimal units (MB, GB) as typically displayed to users
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_count)
    for unit in units:
        if size < 1000.0:
            return f"{size:.2f} {unit}"
        size /= 1000.0
    return f"{size:.2f} PB"


def compute_upper_bound_size_bytes(duration_sec: float, video_kbps: int, include_audio: bool, audio_kbps: int = 128) -> int:
    # We conservatively under-drive actual video bitrate a bit to ensure final size <= estimate
    # Estimate uses user's selected kbps as the MAX cap
    chosen_video_kbps = max(50, int(video_kbps))
    planned_video_kbps = max(50, int(math.floor(chosen_video_kbps * 0.97)))  # encoder target
    total_kbps = planned_video_kbps + (audio_kbps if include_audio else 0)
    base_bytes = duration_sec * (total_kbps * 1000.0) / 8.0
    safety_bytes = math.ceil(base_bytes * 1.05)  # 5% safety margin for container + encoder variability
    return int(safety_bytes)


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


class App(tk.Tk):
    def __init__(self, initial_input: str | None = None) -> None:
        super().__init__()
        self.title("Compresseur Vidéo")
        self.minsize(520, 320)

        self.ffmpeg_path = None
        self.ffprobe_path = None
        try:
            self.ffmpeg_path, self.ffprobe_path = ensure_ffmpeg_tools()
        except FileNotFoundError as exc:
            messagebox.showerror("FFmpeg manquant", str(exc))
            self.destroy()
            return

        self.input_path_var = tk.StringVar(value=initial_input or "")
        self.duration_sec: float = 0.0

        # UI Variables
        self.resolution_var = tk.StringVar(value="Source")
        self.fps_var = tk.StringVar(value="Source")
        self.video_kbps_var = tk.IntVar(value=1500)
        self.include_audio_var = tk.BooleanVar(value=True)
        self.estimate_label_var = tk.StringVar(value="Estimation taille maximale: -")

        self._build_ui()

        # If we already have an input via argv, probe it immediately; otherwise prompt for a file
        if self.input_path_var.get():
            self._on_input_changed()
        else:
            # Prompt immediately on startup to match requested behavior
            self.after(100, self._choose_input)

    def _build_ui(self) -> None:
        padding = {"padx": 10, "pady": 8}

        # Input chooser
        input_frame = ttk.LabelFrame(self, text="Vidéo source")
        input_frame.pack(fill="x", **padding)
        input_entry = ttk.Entry(input_frame, textvariable=self.input_path_var)
        input_entry.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=8)
        browse_btn = ttk.Button(input_frame, text="Choisir...", command=self._choose_input)
        browse_btn.pack(side="left", padx=(0, 10), pady=8)

        # Settings frame
        settings = ttk.LabelFrame(self, text="Paramètres de compression")
        settings.pack(fill="x", **padding)

        # Resolution
        ttk.Label(settings, text="Résolution").grid(row=0, column=0, sticky="w", padx=10, pady=6)
        res_combo = ttk.Combobox(settings, state="readonly", textvariable=self.resolution_var,
                                 values=["Source", "1080p", "720p", "480p", "360p", "240p"])
        res_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=6)
        res_combo.bind("<<ComboboxSelected>>", lambda e: self._update_estimate())

        # FPS
        ttk.Label(settings, text="FPS").grid(row=0, column=2, sticky="w", padx=10, pady=6)
        fps_combo = ttk.Combobox(settings, state="readonly", textvariable=self.fps_var,
                                 values=["Source", "24", "25", "30", "50", "60"])
        fps_combo.grid(row=0, column=3, sticky="ew", padx=10, pady=6)
        fps_combo.bind("<<ComboboxSelected>>", lambda e: self._update_estimate())

        # Video bitrate slider
        ttk.Label(settings, text="Vidéo kb/s").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        bitrate_scale = ttk.Scale(settings, from_=100, to=10000, orient="horizontal",
                                  command=lambda v: self._on_bitrate_changed(v))
        bitrate_scale.set(self.video_kbps_var.get())
        bitrate_scale.grid(row=1, column=1, columnspan=3, sticky="ew", padx=10, pady=6)
        self.bitrate_value_lbl = ttk.Label(settings, text=f"{self.video_kbps_var.get()} kb/s")
        self.bitrate_value_lbl.grid(row=1, column=4, sticky="w", padx=(0, 10), pady=6)

        # Include audio checkbox
        audio_chk = ttk.Checkbutton(settings, text="Garder l'audio", variable=self.include_audio_var,
                                    command=self._update_estimate)
        audio_chk.grid(row=2, column=0, sticky="w", padx=10, pady=6)

        # Estimation label
        estimate_frame = ttk.Frame(self)
        estimate_frame.pack(fill="x", **padding)
        ttk.Label(estimate_frame, textvariable=self.estimate_label_var).pack(side="left", padx=10)

        # Action buttons
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", **padding)
        compress_btn = ttk.Button(action_frame, text="Compresser", command=self._on_compress)
        compress_btn.pack(side="right", padx=10)

        # Grid config
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

    def _choose_input(self) -> None:
        filetypes = [
            ("Vidéos", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"),
            ("Tous les fichiers", "*.*"),
        ]
        path = filedialog.askopenfilename(title="Choisir une vidéo", filetypes=filetypes)
        if path:
            self.input_path_var.set(path)
            self._on_input_changed()

    def _on_bitrate_changed(self, val_str: str) -> None:
        # The callback passes the scale current value as a string
        try:
            value = int(float(val_str))
        except Exception:
            value = self.video_kbps_var.get()
        value = max(50, min(10000, value))
        self.video_kbps_var.set(value)
        self.bitrate_value_lbl.configure(text=f"{value} kb/s")
        self._update_estimate()

    def _on_input_changed(self) -> None:
        path = self.input_path_var.get()
        if not path or not os.path.exists(path):
            messagebox.showwarning("Fichier introuvable", "Veuillez sélectionner une vidéo valide.")
            return
        try:
            info = probe_media(self.ffprobe_path, path)
            self.duration_sec = info.get("duration", 0.0) or 0.0
        except Exception as exc:
            messagebox.showerror("Erreur d'analyse", str(exc))
            self.duration_sec = 0.0
        self._update_estimate()

    def _update_estimate(self) -> None:
        if not self.input_path_var.get() or self.duration_sec <= 0:
            self.estimate_label_var.set("Estimation taille maximale: -")
            return
        video_kbps = self.video_kbps_var.get()
        include_audio = self.include_audio_var.get()
        est_bytes = compute_upper_bound_size_bytes(self.duration_sec, video_kbps, include_audio)
        self.estimate_label_var.set(f"Estimation taille maximale: {human_readable_size(est_bytes)}")

    def _build_ffmpeg_cmd(self, src: str, dst: str) -> list[str]:
        video_kbps = self.video_kbps_var.get()
        chosen_video_kbps = max(50, int(video_kbps))
        planned_video_kbps = max(50, int(math.floor(chosen_video_kbps * 0.97)))
        include_audio = self.include_audio_var.get()

        vf_filters: list[str] = []

        # Resolution scaling (keep aspect ratio, height fixed, width computed; ensure mod2)
        res_choice = self.resolution_var.get()
        if res_choice != "Source":
            target_h = int(res_choice.replace("p", ""))
            vf_filters.append(f"scale='trunc(oh*a/2)*2':{target_h}")

        # FPS
        fps_choice = self.fps_var.get()
        r_args: list[str] = []
        if fps_choice != "Source":
            try:
                r_value = int(fps_choice)
                r_args = ["-r", str(r_value)]
            except ValueError:
                r_args = []

        vf_args = []
        if vf_filters:
            vf_args = ["-vf", ",".join(vf_filters)]

        # Audio
        audio_args = ["-an"]
        if include_audio:
            audio_args = [
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "48000",
            ]

        cmd = [
            self.ffmpeg_path,
            "-y",
            "-hide_banner",
            "-v",
            "warning",
            "-i",
            src,
            *vf_args,
            *r_args,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-preset", "medium",
            "-b:v", f"{planned_video_kbps}k",
            "-maxrate", f"{chosen_video_kbps}k",
            "-bufsize", f"{chosen_video_kbps * 2}k",
            "-x264-params", "nal-hrd=cbr:force-cfr=1",
            *audio_args,
            "-movflags", "+faststart",
            dst,
        ]
        return cmd

    def _on_compress(self) -> None:
        src = self.input_path_var.get()
        if not src or not os.path.exists(src):
            messagebox.showwarning("Fichier introuvable", "Veuillez sélectionner une vidéo valide.")
            return
        # Determine output directory
        src_path = Path(src)
        out_dir = src_path.parent
        if not can_write_to_directory(out_dir):
            # Fallback to Downloads
            downloads = Path.home() / "Downloads"
            if can_write_to_directory(downloads):
                out_dir = downloads
            else:
                messagebox.showerror("Emplacement invalide", "Impossible d'écrire dans le dossier source ou Téléchargements.")
                return

        # Build output filename
        parts = []
        if self.resolution_var.get() != "Source":
            parts.append(self.resolution_var.get())
        if self.fps_var.get() != "Source":
            parts.append(f"{self.fps_var.get()}fps")
        parts.append(f"{self.video_kbps_var.get()}kbps")
        if not self.include_audio_var.get():
            parts.append("noaudio")
        tag = "_" + "_".join(parts) if parts else "_compressed"

        out_ext = src_path.suffix if src_path.suffix.lower() in {".mp4", ".m4v", ".mov", ".mkv", ".webm"} else ".mp4"
        out_name = f"{src_path.stem}{tag}{out_ext}"
        out_path = unique_output_path(out_dir / out_name)

        # Confirm estimated max size before starting
        if self.duration_sec > 0:
            max_bytes = compute_upper_bound_size_bytes(self.duration_sec, self.video_kbps_var.get(), self.include_audio_var.get())
            human = human_readable_size(max_bytes)
            if not messagebox.askokcancel("Confirmation", f"Taille maximale estimée: {human}\n\nContinuer ?"):
                return

        # Run ffmpeg in background thread
        self._run_ffmpeg_async(src, str(out_path))

    def _run_ffmpeg_async(self, src: str, dst: str) -> None:
        cmd = self._build_ffmpeg_cmd(src, dst)

        progress = tk.Toplevel(self)
        progress.title("Compression en cours…")
        ttk.Label(progress, text="Compression en cours… Cela peut prendre un moment.").pack(padx=16, pady=12)
        pb = ttk.Progressbar(progress, mode="indeterminate")
        pb.pack(fill="x", padx=16, pady=(0, 16))
        pb.start(10)
        progress.transient(self)
        progress.grab_set()

        def worker():
            try:
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                returncode = proc.returncode
                stderr = proc.stderr
            except Exception as exc:
                returncode = -1
                stderr = str(exc)
            finally:
                self.after(0, lambda: self._on_ffmpeg_done(progress, returncode, dst, stderr))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ffmpeg_done(self, dlg: tk.Toplevel, returncode: int, dst: str, stderr: str) -> None:
        try:
            dlg.grab_release()
        except Exception:
            pass
        dlg.destroy()
        if returncode == 0 and os.path.exists(dst):
            size_bytes = os.path.getsize(dst)
            human = human_readable_size(size_bytes)
            if messagebox.askyesno("Terminé", f"Compression terminée.\nFichier: {dst}\nTaille: {human}\n\nOuvrir le dossier ?"):
                try:
                    if os.name == "nt":
                        subprocess.Popen(["explorer", "/select,", dst])
                    else:
                        subprocess.Popen(["open", "-R", dst])
                except Exception:
                    pass
        else:
            messagebox.showerror("Échec", f"La compression a échoué.\n\n{stderr[:2000]}")


def main() -> None:
    # Handle drag-and-drop onto EXE icon: Windows passes the file as argv[1]
    initial_input = None
    if len(sys.argv) >= 2:
        # If spaces, the shell already handled quoting; join only if multiple args (rare)
        initial_input = sys.argv[1]
    app = App(initial_input)
    if app.winfo_exists():
        app.mainloop()


if __name__ == "__main__":
    main()


