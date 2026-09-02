$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $studioRoot ".venv\Scripts\python.exe"
# credentials: api.rtf beside the studio folder, or inside it, or beside the original OneDrive copy
$apiFile = Join-Path (Split-Path -Parent $studioRoot) "api.rtf"
foreach ($candidate in @((Join-Path (Split-Path -Parent $studioRoot) "api.rtf"), (Join-Path $studioRoot "api.rtf"), (Join-Path $env:USERPROFILE "OneDrive\Desktop\api.rtf"), (Join-Path $env:USERPROFILE "Desktop\api.rtf"))) {
    if (Test-Path -LiteralPath $candidate) { $apiFile = $candidate; break }
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Windows environment missing. Build .venv before starting the studio."
}
if (-not (Test-Path -LiteralPath $apiFile)) {
    throw "Credential file not found: $apiFile"
}

$raw = Get-Content -LiteralPath $apiFile -Raw
$matches = [regex]::Matches($raw, '(?m)([A-Z][A-Z0-9_]+)=([^\\\r\n}]*)')
foreach ($match in $matches) {
    $name = $match.Groups[1].Value.Trim()
    $value = $match.Groups[2].Value.Trim()
    if ($value) {
        Set-Item -Path ("Env:" + $name) -Value $value
    }
}

Set-Location -LiteralPath $studioRoot
# The studio reloads itself (new code, project switch) by exiting with code 75 -
# relaunch it in this same window, same credentials, until it stops for real.
# 2026-09-02: the window used to vanish the moment the studio stopped for any other reason, so
# a crash read as "the studio can't be reached" with nothing to look at. A stop that is not a
# reload is now printed and the window stays open until Enter; a crash restarts once per minute
# up to five times before giving up (a bad code edit prints its traceback each time).
$crashes = 0
do {
    & $python "cb-studio\serve.py"
    $code = $LASTEXITCODE
    if ($code -eq 75) { Write-Host "Studio is reloading with the latest code..."; continue }
    if ($code -ne 0 -and $crashes -lt 5) {
        $crashes += 1
        Write-Host ("!! The studio stopped with exit code " + $code + " - restarting in 60 s (attempt " + $crashes + " of 5). Read the error above.") -ForegroundColor Yellow
        Start-Sleep -Seconds 60
        $code = 75
    }
} while ($code -eq 75)
Write-Host ("The studio has stopped (exit code " + $code + ").") -ForegroundColor Yellow
Read-Host "Press Enter to close this window"
