# Creates shortcuts to dist\SubForge\SubForge.exe (release build).
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

if (-not $DistExe) {
    Write-Error "Not found: dist\SubForge\SubForge.exe or dist2\SubForge\SubForge.exe. Run build_exe.ps1 first."
}

$Wsh = New-Object -ComObject WScript.Shell

function New-ReleaseShortcut {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ShortcutPath
    )

    $shortcut = $Wsh.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $DistExe
    $shortcut.WorkingDirectory = Split-Path -Parent $DistExe
    $shortcut.WindowStyle = 1
    $shortcut.Description = "SubForge - speech to embedded subtitles"
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,137"
    $shortcut.Save()
    Write-Host "Created shortcut: $ShortcutPath"
}

$distShortcut = Join-Path (Split-Path -Parent $DistExe) "SubForge.lnk"
New-ReleaseShortcut -ShortcutPath $distShortcut

$desktop = [Environment]::GetFolderPath("Desktop")
$desktopShortcut = Join-Path $desktop "SubForge.lnk"
New-ReleaseShortcut -ShortcutPath $desktopShortcut

Write-Host "Done. Double-click SubForge.lnk to start the release build."
