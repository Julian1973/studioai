# update-studio.ps1 (T63, 2026-09-01) - bring this PC's copy of the studio to the tip of the working
# branch WITHOUT ever discarding local work. Double-click update-studio.cmd.
#
#   1. anything uncommitted (edited OR new files - e.g. today's characters.json edits, a project folder
#      built here) is put in a named git stash first - never deleted;
#   2. fetch + checkout the branch + fast-forward to origin;
#   3. Windows symlink support is switched on (the studio relies on real symlinks for one release);
#   4. the .venv is rebuilt only when requirements.txt changed;
#   5. the compatibility-link check runs and the commit landed on is printed.
#
# The branch defaults to the restructure branch; pass another name as the first argument once it has
# been merged:  update-studio.cmd integration/reconciled-studioai

param([string]$Branch = "t40/projects")

# git and pip report progress on stderr; "Stop" would turn that into a crash. Exit codes are checked instead.
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
function Fail($msg) { Write-Host ("!! " + $msg) -ForegroundColor Red; exit 1 }

$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $studioRoot

function Say($msg) { Write-Host ("== " + $msg) -ForegroundColor Cyan }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is not installed or not on PATH." }
if (-not (Test-Path -LiteralPath (Join-Path $studioRoot ".git"))) { Fail "This folder is not a git checkout: $studioRoot" }

$before = (git rev-parse --short HEAD).Trim()
$beforeBranch = (git rev-parse --abbrev-ref HEAD).Trim()
Say "Studio at $studioRoot - currently $beforeBranch @ $before"

# 1. keep local work - EDITED tracked files go to a named git stash; NEW files (a project folder built
#    here, notes, anything untracked) are MOVED into a dated side folder, never deleted. (git stash -u
#    tried to delete thousands of files inside .venv and OneDrive refused every one - so nothing is
#    deleted any more; .venv, caches and OneDrive's own files are simply left where they are.)
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$edited = @(git status --porcelain --untracked-files=no | Where-Object { $_ })
$dirty = $edited.Count
if ($dirty -gt 0) {
    $label = "local-edits-before-update-$stamp"
    Say "Saving $dirty edited file(s) to git stash '$label' (nothing is deleted)"
    git stash push --message $label | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Could not save the local edits to a stash - stopping before anything is touched." }
    Say "Recover later with:  git stash list   /   git stash show -p stash@{0}   /   git checkout stash@{0} -- <path>"
} else {
    Say "No edited tracked files to save"
}
$untracked = @(git ls-files --others --exclude-standard | Where-Object { $_ -and -not ($_ -like ".venv/*") -and -not ($_ -like ".pytest_cache/*") -and -not ($_ -like "*__pycache__*") -and -not ($_ -like "studio-update.bundle") -and -not ($_ -like "update-studio.*") -and -not ($_ -like "HANDOVER_*") })
if ($untracked.Count -gt 0) {
    $aside = Join-Path $studioRoot ("_local-work-" + $stamp)
    Say ("Moving " + $untracked.Count + " new local file(s) aside into " + $aside + " (nothing is deleted)")
    foreach ($rel in $untracked) {
        $src = Join-Path $studioRoot $rel
        $dst = Join-Path $aside $rel
        $dstDir = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
        try { Move-Item -LiteralPath $src -Destination $dst -Force } catch { Write-Host ("   could not move " + $rel + ": " + $_.Exception.Message) -ForegroundColor Yellow }
    }
}

# 2. real symlinks - the studio refuses to start without them (tools/check_links.py)
git config core.symlinks true
$requirementsBefore = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsBefore = (Get-FileHash requirements.txt).Hash }

Say "Fetching origin"
git fetch origin | Out-Host
# A bundle beside this script (studio-update.bundle) carries commits that have not reached GitHub
# yet - a hand-delivered update. It is fetched too, and wins when it is ahead of origin.
$bundle = Join-Path $studioRoot "studio-update.bundle"
$source = "origin/$Branch"
if (Test-Path -LiteralPath $bundle) {
    Say "Fetching hand-delivered update from studio-update.bundle"
    git fetch $bundle "refs/heads/${Branch}:refs/remotes/bundle/$Branch" | Out-Host
    $originHas = (git rev-parse --verify --quiet "origin/$Branch")
    $bundleAhead = $false
    if ($originHas) {
        git merge-base --is-ancestor "origin/$Branch" "bundle/$Branch"
        $bundleAhead = ($LASTEXITCODE -eq 0)
    }
    if (-not $originHas -or $bundleAhead) {
        $source = "bundle/$Branch"
    }
}
Say "Switching to $Branch (from $source)"
if ((git branch --list $Branch).Trim()) {
    git checkout $Branch | Out-Host
} else {
    git checkout -b $Branch $source | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Could not create branch $Branch from $source." }
    if ($source -eq "origin/$Branch") { git branch --set-upstream-to "origin/$Branch" $Branch | Out-Null }
}
git merge --ff-only $source | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "Fast-forward to $source failed - the local branch has commits of its own. Nothing was discarded; ask Claude." }
if ($source -like "bundle/*") { Say "This update came from the bundle - publish it with:  git push -u origin $Branch" }
# symlinks written as text files by an older checkout become real links on re-checkout
git checkout -- . | Out-Host

# 3. the virtual environment - rebuilt only when requirements changed or it is missing
$python = Join-Path $studioRoot ".venv\Scripts\python.exe"
$requirementsAfter = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsAfter = (Get-FileHash requirements.txt).Hash }
if (-not (Test-Path -LiteralPath $python) -or ($requirementsBefore -ne $requirementsAfter)) {
    Say "Rebuilding .venv (requirements changed or environment missing)"
    if (Test-Path -LiteralPath ".venv") { Rename-Item -LiteralPath ".venv" -NewName (".venv-old-" + $stamp) -Force }
    py -3 -m venv .venv
    & $python -m pip install --upgrade pip | Out-Host
    & $python -m pip install -r requirements.txt | Out-Host
} else {
    Say ".venv unchanged (requirements identical)"
}

# 4. prove the checkout can run - real symlinks need Developer Mode (or admin) on Windows.
Say "Checking compatibility links"
& $python "tools\check_links.py" | Out-Host
if ($LASTEXITCODE -ne 0) {
    Say "Symlinks are not real yet - switching Developer Mode on (Windows will ask for permission once: click Yes)"
    $reg = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
    $cmd = "reg add `"$reg`" /v AllowDevelopmentWithoutDevLicense /t REG_DWORD /d 1 /f"
    try {
        Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait -ArgumentList "-NoProfile", "-Command", $cmd
    } catch {
        Write-Host "Could not switch Developer Mode on (permission refused). Turn it on yourself: Settings > For developers > Developer Mode, then run this script again." -ForegroundColor Yellow
    }
    # re-create the links now that the permission exists: remove the text-file stand-ins, check out again
    $links = @("shows", "cb-output", "engine\config", "cb-studio\data\scripts",
               "CRYSTAL_BEARS_LOCKED_CANON.md", "CRYSTAL_BEARS_STUDIO_BIBLE.md", "EP1_GATE1_STORYBOARD.md",
               "projects\crystal-bears\assets",
               "skills\crystal-bears-writer\SKILL.md", "skills\crystal-bears-director\SKILL.md",
               "skills\crystal-bears-cinematographer\SKILL.md", "skills\crystal-bears-voice-director\SKILL.md",
               "skills\crystal-bears-composer\SKILL.md", "skills\crystal-bears-continuity\SKILL.md",
               "skills\crystal-bears-post\SKILL.md", "skills\seedance-production-director\SKILL.md")
    foreach ($l in $links) {
        if ((Test-Path -LiteralPath $l) -and -not ((Get-Item -LiteralPath $l -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            try {
                if (Test-Path -LiteralPath $l -PathType Container) { Remove-Item -LiteralPath $l -Recurse -Force } else { Remove-Item -LiteralPath $l -Force }
            } catch { Write-Host ("   could not replace " + $l + ": " + $_.Exception.Message) -ForegroundColor Yellow }
        }
    }
    git checkout -- . | Out-Host
    & $python "tools\check_links.py" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host "The links are still not real. Log out and back in (Developer Mode takes effect at sign-in), then run this script again." -ForegroundColor Yellow
    }
}

$after = (git rev-parse --short HEAD).Trim()
$subject = (git log -1 --format=%s).Trim()
Say ("Updated: " + $beforeBranch + " @ " + $before + "  ->  " + $Branch + " @ " + $after)
Say $subject
if ($dirty -gt 0) { Say "Your edited files are safe in git stash (git stash list)." }
if ($untracked.Count -gt 0) { Say ("Your new local files are in " + $aside) }
