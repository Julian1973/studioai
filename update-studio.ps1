$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

# update-studio.ps1 (T63, 2026-09-01) — bring this PC's copy of the studio to the tip of the working
# branch WITHOUT ever discarding local work. Double-click update-studio.cmd.
#
#   1. anything uncommitted (edited OR new files — e.g. today's characters.json edits, a project folder
#      built here) is put in a named git stash first — never deleted;
#   2. fetch + checkout the branch + fast-forward to origin;
#   3. Windows symlink support is switched on (the studio relies on real symlinks for one release);
#   4. the .venv is rebuilt only when requirements.txt changed;
#   5. the compatibility-link check runs and the commit landed on is printed.
#
# The branch defaults to the restructure branch; pass another name as the first argument once it has
# been merged:  update-studio.cmd integration/reconciled-studioai

param([string]$Branch = "t40/projects")

$studioRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $studioRoot

function Say($msg) { Write-Host ("== " + $msg) -ForegroundColor Cyan }

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not installed or not on PATH." }
if (-not (Test-Path -LiteralPath (Join-Path $studioRoot ".git"))) { throw "This folder is not a git checkout: $studioRoot" }

$before = (git rev-parse --short HEAD).Trim()
$beforeBranch = (git rev-parse --abbrev-ref HEAD).Trim()
Say "Studio at $studioRoot — currently $beforeBranch @ $before"

# 1. keep local work — stash everything uncommitted (tracked edits AND untracked files), named + dated
$dirty = (git status --porcelain --untracked-files=all | Measure-Object -Line).Lines
if ($dirty -gt 0) {
    $stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
    $label = "local-work-before-update-$stamp"
    Say "Saving $dirty uncommitted change(s) to git stash '$label' (nothing is deleted)"
    git stash push --include-untracked --message $label | Out-Host
    Say "Recover later with:  git stash list   /   git stash show -p stash@{0}   /   git checkout stash@{0} -- <path>"
} else {
    Say "No uncommitted local work to save"
}

# 2. real symlinks — the studio refuses to start without them (tools/check_links.py)
git config core.symlinks true
$requirementsBefore = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsBefore = (Get-FileHash requirements.txt).Hash }

Say "Fetching origin"
git fetch --prune origin | Out-Host
# A bundle beside this script (studio-update.bundle) carries commits that have not reached GitHub
# yet — a hand-delivered update. It is fetched too, and wins when it is ahead of origin.
$bundle = Join-Path $studioRoot "studio-update.bundle"
$source = "origin/$Branch"
if (Test-Path -LiteralPath $bundle) {
    Say "Fetching hand-delivered update from studio-update.bundle"
    git fetch $bundle "refs/heads/${Branch}:refs/remotes/bundle/$Branch" | Out-Host
    $originHas = (git rev-parse --verify --quiet "origin/$Branch")
    if (-not $originHas -or (git merge-base --is-ancestor "origin/$Branch" "bundle/$Branch"; $LASTEXITCODE -eq 0)) {
        $source = "bundle/$Branch"
    }
}
Say "Switching to $Branch (from $source)"
if ((git branch --list $Branch).Trim()) {
    git checkout $Branch | Out-Host
} else {
    git checkout -b $Branch $source | Out-Host
    if ($source -eq "origin/$Branch") { git branch --set-upstream-to "origin/$Branch" $Branch | Out-Null }
}
git merge --ff-only $source | Out-Host
if ($source -like "bundle/*") { Say "This update came from the bundle — publish it with:  git push -u origin $Branch" }
# symlinks written as text files by an older checkout become real links on re-checkout
git checkout -- . 2>$null

# 3. the virtual environment — rebuilt only when requirements changed or it is missing
$python = Join-Path $studioRoot ".venv\Scripts\python.exe"
$requirementsAfter = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsAfter = (Get-FileHash requirements.txt).Hash }
if (-not (Test-Path -LiteralPath $python) -or ($requirementsBefore -ne $requirementsAfter)) {
    Say "Rebuilding .venv (requirements changed or environment missing)"
    if (Test-Path -LiteralPath ".venv") { Remove-Item -LiteralPath ".venv" -Recurse -Force }
    py -3 -m venv .venv
    & $python -m pip install --upgrade pip | Out-Host
    & $python -m pip install -r requirements.txt | Out-Host
} else {
    Say ".venv unchanged (requirements identical)"
}

# 4. prove the checkout can run
Say "Checking compatibility links"
& $python "tools\check_links.py" | Out-Host
if ($LASTEXITCODE -ne 0) {
    Write-Host "Symlinks are not real on this checkout. Enable Developer Mode (Settings > For developers), then re-run this script." -ForegroundColor Yellow
}

$after = (git rev-parse --short HEAD).Trim()
$subject = (git log -1 --format=%s).Trim()
Say "Updated: $beforeBranch @ $before  ->  $Branch @ $after"
Say $subject
if ($dirty -gt 0) { Say "Your local work is safe in git stash (git stash list)." }
