Param(
    [switch]$PortableFfmpeg
)

# Build a single-file Windows EXE using PyInstaller
# Usage (from Windows PowerShell):
#   pwsh -File build_windows.ps1
# or
#   powershell -ExecutionPolicy Bypass -File build_windows.ps1

$ErrorActionPreference = 'Stop'

function Resolve-PythonCmd {
    if (Get-Command py -ErrorAction SilentlyContinue) { return 'py -3' }
    if (Get-Command python -ErrorAction SilentlyContinue) { return 'python' }
    if (Get-Command python3 -ErrorAction SilentlyContinue) { return 'python3' }
    throw 'Python introuvable. Installez Python 3.x et relancez.'
}

$pythonCmd = Resolve-PythonCmd

Write-Host "Creating Python venv..."
if (-not (Test-Path .venv)) {
    & $pythonCmd -m venv .venv
}

$venvPython = ".\\.venv\\Scripts\\python.exe"
& $venvPython -m pip install --upgrade pip
if (Test-Path 'requirements.txt') {
    & $venvPython -m pip install -r requirements.txt
} else {
    & $venvPython -m pip install pyinstaller
}

Write-Host "Building EXE..."
Remove-Item -Recurse -Force dist  -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue

$script = "compressor_gui.py"

& $venvPython -m PyInstaller `
  --name "VideoCompressor" `
  --onefile `
  --noconsole `
  --add-data "$script;." `
  $script

Write-Host "EXE created at: dist/VideoCompressor.exe"

if ($PortableFfmpeg) {
    Write-Host "Copying portable ffmpeg/ffprobe next to the EXE (if present in current dir)..."
    foreach ($bin in @("ffmpeg.exe", "ffprobe.exe")) {
        if (Test-Path $bin) {
            Copy-Item $bin -Destination "dist/$bin" -Force
        }
    }
}

Write-Host "Done."


