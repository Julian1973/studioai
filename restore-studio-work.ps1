# restore-studio-work.ps1 (2026-09-02) - put back the studio's own production data that earlier
# versions of update-studio.ps1 moved aside (_local-work-<stamp> folders) or stashed
# (git stash "local-edits-before-update-<stamp>") on every update. Nothing is deleted: the side
# folders are renamed to _restored-<stamp> afterwards and the stashes are kept.
#
# Order: oldest first, so the newest copy of every file wins.
param([string]$StudioRoot = (Join-Path $env:USERPROFILE "AiStudio"))
$ErrorActionPreference = "Continue"
function Say($msg) { Write-Host ("== " + $msg) -ForegroundColor Cyan }
function Warn($msg) { Write-Host ("   " + $msg) -ForegroundColor Yellow }

if (-not (Test-Path -LiteralPath (Join-Path $StudioRoot ".git"))) { Write-Host "!! not a studio checkout: $StudioRoot"; Read-Host "Press Enter to close"; exit 1 }
Set-Location -LiteralPath $StudioRoot

# stop the studio so nothing is written underneath us
$running = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*serve.py*" }
if ($running) {
    Say ("Stopping the running studio (" + @($running).Count + " process(es))")
    foreach ($p in $running) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {} }
    Start-Sleep -Seconds 2
}

# 1. files moved aside -> back where they were (newest wins)
$side = @(Get-ChildItem -LiteralPath $StudioRoot -Directory -Filter "_local-work-*" | Sort-Object Name)
$restored = 0
foreach ($dir in $side) {
    $files = @(Get-ChildItem -LiteralPath $dir.FullName -Recurse -File | Where-Object { $_.FullName -notlike "*\_replaced-by-checkout\*" })
    Say ("Restoring " + $files.Count + " file(s) from " + $dir.Name)
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($dir.FullName.Length).TrimStart("\")
        $dst = Join-Path $StudioRoot $rel
        $dstDir = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
        try { Copy-Item -LiteralPath $f.FullName -Destination $dst -Force; $restored++ } catch { Warn ("could not restore " + $rel + ": " + $_.Exception.Message) }
    }
    try { Rename-Item -LiteralPath $dir.FullName -NewName ($dir.Name -replace "^_local-work-", "_restored-") } catch {}
}
Say "$restored file(s) restored"

# 2. edited tracked files that were stashed -> back, oldest stash first so the newest edit wins
$entries = @(git stash list | Where-Object { $_ -match "local-edits-before-update-" })
$ordered = @($entries | ForEach-Object { if ($_ -match "^stash@\{(\d+)\}") { [int]$matches[1] } } | Sort-Object -Descending)
$stashedBack = 0
foreach ($i in $ordered) {
    $paths = @(git stash show --name-only "stash@{$i}" | Where-Object { $_ })
    foreach ($p in $paths) {
        git checkout "stash@{$i}" -- $p 2>$null
        if ($LASTEXITCODE -eq 0) { $stashedBack++ } else { Warn ("could not restore " + $p + " from stash@{" + $i + "}") }
    }
}
git reset -q 2>$null
Say "$stashedBack stashed edit(s) restored (the stash entries are kept)"

# 3. start the studio again
$startCmd = Join-Path $StudioRoot "start-studio.cmd"
if (Test-Path -LiteralPath $startCmd) {
    Say "Starting the studio..."
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", ('"' + $startCmd + '"')) -WorkingDirectory $StudioRoot
    $ready = $false
    for ($k = 0; $k -lt 60 -and -not $ready; $k++) {
        Start-Sleep -Seconds 2
        try { $null = (New-Object Net.Sockets.TcpClient).Connect("127.0.0.1", 8765); $ready = $true } catch {}
    }
    if ($ready) { Say "The studio is up"; Start-Process "http://127.0.0.1:8765/cb-studio/app.html" } else { Warn "The studio has not answered yet - look at the AI Studio window" }
}
Read-Host "Done. Press Enter to close"
