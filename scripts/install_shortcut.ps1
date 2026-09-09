# Puts a "Post Studio" shortcut on the Desktop and in the Start menu.
#
#     powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1
#
# Run it once, then pin the shortcut to the taskbar.
#
# WHY THE TARGET IS cmd.exe AND NOT PostStudio.bat. Windows decides whether a
# shortcut can be pinned by what it points at, and it refuses a .bat: the first
# version of this script targeted the batch file directly and the option simply
# was not in the menu. Pointing at cmd.exe with the batch file as an argument
# is the same launch by a route Windows will pin.
#
# `call` matters too. `cmd /c "some path"` has a quoting rule that eats the
# outer quotes in some cases and breaks on the space in "agentic os"; going
# through `call` parses the quoted path as one token.
#
# It still runs the same PostStudio.bat you would double-click, so there is one
# way in and nothing to keep in sync.

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
    $link.TargetPath = "$env:SystemRoot\System32\cmd.exe"
    $link.Arguments = "/c call `"$launcher`""
    # Without this the console opens in system32 and every relative path in the
    # launcher resolves somewhere else.
    $link.WorkingDirectory = $repo
    $link.Description = 'Write a note, read the drafts, send what you approve'
    # Windows has no icon for this worth looking at on a taskbar. Its own
    # generic app icon is the least bad option that needs no asset shipped.
    $link.IconLocation = "$env:SystemRoot\System32\SHELL32.dll,13"
    $link.Save()
    Write-Host "  Created $path"
}

Write-Host ""
Write-Host "  To pin it: right-click the Desktop shortcut, choose 'Show more"
Write-Host "  options' if you are on Windows 11, then 'Pin to taskbar'."
Write-Host ""
Write-Host "  If it is still not offered, open Start, type Post Studio, and"
Write-Host "  right-click the result instead. Same shortcut, different menu."
Write-Host ""
