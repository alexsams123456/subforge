# SubForge one-step setup: venv, pip, ffmpeg, optional shortcut.
param(
    [switch]$Recreate,
    [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Set-Location $ProjectRoot

if ($Recreate -and (Test-Path $VenvDir)) {
    Write-Host "SubForge: removing .venv..."
    Remove-Item -Recurse -Force $VenvDir
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "SubForge: creating venv..."
    python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "python -m venv failed. Install Python 3.10+ and ensure it is on PATH."
    }
}

Write-Host "SubForge: installing dependencies..."
& $VenvPip install -r (Join-Path $ProjectRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "pip install failed."
}

Write-Host "SubForge: ffmpeg..."
& powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "install_ffmpeg.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Error "install_ffmpeg.ps1 failed."
}

if (-not $NoShortcut) {
    Write-Host "SubForge: shortcut..."
    & powershell -ExecutionPolicy Bypass -File (Join-Path $ProjectRoot "create_shortcut.ps1")
}

Write-Host ""
Write-Host "Done. Run: .\.venv\Scripts\Activate.ps1 ; python main.py"
Write-Host "Or double-click SubForge.lnk on the desktop."
