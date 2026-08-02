# Build SubForge standalone exe (PyInstaller onedir + CUDA torch).
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvPip = Join-Path $ProjectRoot ".venv\Scripts\pip.exe"
$DistDir = Join-Path $ProjectRoot "dist\SubForge"
$DistBin = Join-Path $DistDir "bin"
$DistExe = Join-Path $DistDir "SubForge.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Not found: $VenvPython. Create venv and install requirements first."
}

Set-Location $ProjectRoot

Write-Host "SubForge: installing runtime dependencies..."
& $VenvPip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install requirements.txt failed."
}

Write-Host "SubForge: installing build dependencies..."
& $VenvPip install -r (Join-Path $ProjectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install requirements-build.txt failed."
}

Write-Host "SubForge: installing CUDA torch/torchaudio (cu124)..."
& $VenvPip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install torch CUDA failed."
}

Write-Host "SubForge: re-syncing project dependencies after torch..."
& $VenvPip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install requirements.txt failed after torch."
}

Write-Host "SubForge: running PyInstaller..."
& $VenvPython -m PyInstaller --noconfirm (Join-Path $ProjectRoot "SubForge.spec")
if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed."
}

if (-not (Test-Path $DistExe)) {
    Write-Error "Build finished but exe not found: $DistExe"
}

Write-Host "SubForge: bundling ffmpeg into dist..."
New-Item -ItemType Directory -Force -Path $DistBin | Out-Null

$ProjectBin = Join-Path $ProjectRoot "bin"
$ProjectFfmpeg = Join-Path $ProjectBin "ffmpeg.exe"
$ProjectFfprobe = Join-Path $ProjectBin "ffprobe.exe"

if (-not (Test-Path $ProjectFfmpeg)) {
    Write-Host "Project bin/ffmpeg.exe missing - running install_ffmpeg.ps1..."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "install_ffmpeg.ps1")
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not install ffmpeg automatically. Copy ffmpeg.exe to $DistBin manually."
    }
}

if (Test-Path $ProjectFfmpeg) {
    Copy-Item -Path $ProjectFfmpeg -Destination (Join-Path $DistBin "ffmpeg.exe") -Force
    Write-Host "Copied ffmpeg.exe to $DistBin"
}
if (Test-Path $ProjectFfprobe) {
    Copy-Item -Path $ProjectFfprobe -Destination (Join-Path $DistBin "ffprobe.exe") -Force
    Write-Host "Copied ffprobe.exe to $DistBin"
}

Write-Host ""
Write-Host "Build complete: $DistExe"
Write-Host "Distribution folder: $DistDir"
Write-Host "Expected size: about 2-4 GB (CUDA + ML stack)."
Write-Host "Optional: powershell -ExecutionPolicy Bypass -File .\create_shortcut_release.ps1"
