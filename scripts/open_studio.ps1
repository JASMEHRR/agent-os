# Waits for Post Studio to answer, then opens it in its own window.
#
# Two jobs the launcher cannot do itself. `serve.py` blocks once it is running,
# so anything after it in the batch file never executes, and opening the
# browser *before* the server binds shows "cannot connect" for the second it
# takes to start. Polling the port fixes the order without a fixed sleep that
# is either too short on a cold start or wasted on a warm one.
#
# The window is an app window (Chrome or Edge `--app=`) rather than a tab:
# no address bar, its own taskbar entry, and it looks like the tool it is
# rather than like a page. Falls back to the default browser when neither is
# installed, which still works and just looks less like an app.

param(
    [int]$Port = 8765,
    [int]$TimeoutSeconds = 30
)

$url = "http://127.0.0.1:$Port"

function Test-Listening {
    param([int]$Port)
    $client = New-Object Net.Sockets.TcpClient
    try {
        # Connect throws when nothing is listening, which is the normal case
        # for most of this loop rather than an error worth reporting.
        $client.Connect('127.0.0.1', $Port)
        return $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while (-not (Test-Listening -Port $Port)) {
    if ((Get-Date) -gt $deadline) {
        Write-Host "  Post Studio did not start within $TimeoutSeconds seconds."
        Write-Host "  The window that launched this should say why."
        exit 1
    }
    Start-Sleep -Milliseconds 250
}

# Chrome first, then Edge, both in app mode. Edge is on every Windows machine,
# so the fallback to a plain browser is rare in practice.
$browsers = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "${env:LocalAppData}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
)

foreach ($browser in $browsers) {
    if (Test-Path $browser) {
        Start-Process $browser -ArgumentList "--app=$url"
        exit 0
    }
}

Start-Process $url
exit 0
