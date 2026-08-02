# Creates SubForge.lnk in the project folder and on the Desktop.
# Prefers dist\SubForge\SubForge.exe when present; otherwise pythonw + launch.py (dev).
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistExe = $null
foreach ($relative in @("dist\SubForge\SubForge.exe", "dist2\SubForge\SubForge.exe")) {
    $candidate = Join-Path $ProjectRoot $relative
    if (Test-Path $candidate) {
        $DistExe = $candidate
        break
    }
}
$PythonW = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
$LaunchPy = Join-Path $ProjectRoot "launch.py"

$UseRelease = $null -ne $DistExe

if (-not $UseRelease) {
    if (-not (Test-Path $PythonW)) {
        Write-Error "Not found: $PythonW. Create venv and install requirements first, or run build_exe.ps1."
    }
}

$Wsh = New-Object -ComObject WScript.Shell

function New-SubForgeShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ShortcutPath
    )

    $shortcut = $Wsh.CreateShortcut($ShortcutPath)
    if ($UseRelease) {
        $shortcut.TargetPath = $DistExe
        $shortcut.WorkingDirectory = Split-Path -Parent $DistExe
        $shortcut.Arguments = ""
    }
    else {
        $shortcut.TargetPath = $PythonW
        $shortcut.Arguments = "`"$LaunchPy`""
        $shortcut.WorkingDirectory = $ProjectRoot
    }
    $shortcut.WindowStyle = 1
    $shortcut.Description = "SubForge - speech to embedded subtitles"
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,137"
    $shortcut.Save()
    Write-Host "Created shortcut: $ShortcutPath"
}

if ($UseRelease) {
    Write-Host "Using release exe: $DistExe"
}
else {
    Write-Host "Using dev launcher: $PythonW launch.py"
}

$projectShortcut = Join-Path $ProjectRoot "SubForge.lnk"
New-SubForgeShortcut -ShortcutPath $projectShortcut

$desktop = [Environment]::GetFolderPath("Desktop")
$desktopShortcut = Join-Path $desktop "SubForge.lnk"
New-SubForgeShortcut -ShortcutPath $desktopShortcut

Write-Host "Done. Double-click SubForge.lnk to start."
