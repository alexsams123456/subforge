# Install ffmpeg for SubForge (winget).
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BinDir = Join-Path $ProjectRoot "bin"
$Target = Join-Path $BinDir "ffmpeg.exe"

Write-Host "SubForge: installing ffmpeg..."

if (Test-Path $Target) {
    Write-Host "Already exists: $Target"
    exit 0
}

$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "Trying winget install Gyan.FFmpeg ..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
}

$found = $null
if (Test-Path $BinDir) {
    $found = Get-ChildItem -Path $BinDir -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
}

if (-not $found) {
    $local = [Environment]::GetFolderPath("LocalApplicationData")
    $packages = Join-Path $local "Microsoft\WinGet\Packages"
    if (Test-Path $packages) {
        $found = Get-ChildItem -Path $packages -Filter ffmpeg.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    }
}

if ($found) {
    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    Copy-Item -Path $found.FullName -Destination $Target -Force
    $ProbeSource = Join-Path $found.DirectoryName "ffprobe.exe"
    if (Test-Path $ProbeSource) {
        Copy-Item -Path $ProbeSource -Destination (Join-Path $BinDir "ffprobe.exe") -Force
    }
    Write-Host "Copied to: $Target"
    exit 0
}

Write-Host "Could not install automatically."
Write-Host "Manual steps:"
Write-Host "  1. winget install Gyan.FFmpeg"
Write-Host "  2. Or download from https://www.gyan.dev/ffmpeg/builds/"
Write-Host "  3. Put ffmpeg.exe into: $BinDir"
exit 1
