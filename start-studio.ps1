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
& $python "cb-studio\serve.py"
