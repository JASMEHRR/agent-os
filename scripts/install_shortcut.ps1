# Puts a "Post Studio" shortcut on the Desktop and in the Start menu.
#
#     powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1
#
# Run it once. Then right-click the shortcut and choose "Pin to taskbar", which
# Windows offers for a .lnk and refuses for a .bat, which is the whole reason
# this file exists rather than a line in the README telling you to pin the
# batch file.
#
# The shortcut runs the same PostStudio.bat you would double-click, so there is
# one way in and nothing to keep in sync.

$ErrorActionPreference = 'Stop'

$repo = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $repo 'PostStudio.bat'

if (-not (Test-Path $launcher)) {
    Write-Host "  Could not find PostStudio.bat next to this script."
    Write-Host "  Run it from inside the repository: scripts\install_shortcut.ps1"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$targets = @(
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Post Studio.lnk'),
    (Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\Post Studio.lnk')
)

foreach ($path in $targets) {
    $parent = Split-Path -Parent $path
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }

    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $launcher
    # Without this the console opens in system32 and every relative path in the
    # launcher resolves somewhere else.
    $link.WorkingDirectory = $repo
    $link.Description = 'Write a note, read the drafts, send what you approve'
    # Windows has no icon for a .bat worth looking at on a taskbar. Its own
    # generic app icon is the least bad option that needs no asset shipped.
    $link.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,13"
    $link.Save()
    Write-Host "  Created $path"
}

Write-Host ""
Write-Host "  Right-click the Desktop shortcut and choose 'Pin to taskbar'."
Write-Host ""
