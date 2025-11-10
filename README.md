## Video Compressor (Windows EXE)

A small Windows GUI app (Tkinter + FFmpeg) to compress a single video. You can drag a video file onto the EXE icon or launch the app and pick a file via the file dialog. Configure resolution, FPS, video bitrate (kb/s), and choose to keep or remove audio. Before starting, the app shows a conservative upper-bound size estimate that the final output will not exceed.

### Features
- Drag-and-drop onto the EXE or pick a file when launching
- Resolution selector: Source, 1080p, 720p, 480p, 360p, 240p
- FPS selector: Source, 24, 25, 30, 50, 60
- Video bitrate slider (kb/s)
- Toggle to keep or remove audio
- Displays a maximum size estimate (upper bound) before compressing
- Writes the output next to the source video (fallback to Downloads if needed)
- Export to GIF while respecting the selected Resolution/FPS (bitrate is ignored for GIF)

### Requirements
- To run the compiled EXE:
  - `ffmpeg.exe` and `ffprobe.exe` must be available either next to `VideoCompressor.exe` or on the system PATH.
- To build from source on Windows:
  - Windows 10/11
  - Python 3.10+
  - PowerShell (or PowerShell 7)

### Download / Run
- Download `VideoCompressor.exe` from the GitHub Releases page and place `ffmpeg.exe` and `ffprobe.exe` next to it (or have FFmpeg on PATH). Then double‑click to launch, or drag a file onto the EXE icon.

### Build from source (PowerShell)
From a PowerShell prompt in the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

- The EXE will be created at `dist/VideoCompressor.exe`.
- Optional: pass `-PortableFfmpeg` to copy `ffmpeg.exe` and `ffprobe.exe` (if present in the current folder) next to the EXE:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1 -PortableFfmpeg
```

If you prefer manual setup:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
pyinstaller --name VideoCompressor --onefile --noconsole compressor_gui.py
```

### How it works (brief)
- The app estimates an upper-bound output size using: size ≈ duration × (total kb/s) / 8, with a safety margin and capped video bitrate (x264 CBR-like via `-maxrate`/`-bufsize`) and 128 kb/s audio when audio is kept.
- Output is written to the same directory as the input video. If the app can’t write there, it falls back to the user’s Downloads folder.
- For GIF exports, a dedicated FFmpeg palette workflow is used (`palettegen`/`paletteuse`). The bitrate slider does not apply to GIF; control size/quality using Resolution and FPS. The shown size estimate for GIF is heuristic (based on frames and pixels) and provided for guidance.

### Troubleshooting
- “FFmpeg not available”: place `ffmpeg.exe` and `ffprobe.exe` next to `VideoCompressor.exe`, or install FFmpeg and add it to PATH.
- Cannot write to the source folder: the app will fall back to `Downloads`.

### License
- MIT. See `LICENSE`.

### Acknowledgements
- Powered by FFmpeg (`ffmpeg` and `ffprobe`).
