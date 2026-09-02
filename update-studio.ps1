# update-studio.ps1 (T63, 2026-09-01; v9 2026-09-02) - bring this PC's copy of the studio to the tip of
# the working branch WITHOUT ever discarding local work. Double-click update-studio.cmd.
#
# v9 - THE MOVE OUT OF ONEDRIVE. A git checkout inside a OneDrive folder cannot be updated: OneDrive
# refuses to let git delete or replace folders ("Deletion of directory ... failed. Should I try again?"),
# and the restructure branch replaces several folders with links. So when this script finds itself inside
# OneDrive it builds a FRESH checkout at  %USERPROFILE%\AiStudio  (outside OneDrive), fetches the branch
# there, copies the assets, media and studio state across, builds the .venv there, and puts a
# "Start AI Studio" launcher on the Desktop. The OneDrive copy is never modified - it stays as a backup.
# Pass -InPlace to update the current folder instead (only sensible outside OneDrive).
#
#   1. (in-place only) anything uncommitted is put in a named git stash / moved aside - never deleted;
#   2. fetch origin + the hand-delivered bundle, check out the branch, fast-forward;
#   3. real symlinks (Developer Mode or administrator) - the studio relies on them for one release;
#   4. the .venv is built / rebuilt when missing or when requirements.txt changed;
#   5. the compatibility-link check runs and the commit landed on is printed.
#
# The branch defaults to the restructure branch; pass another name as the first argument once it has
# been merged:  update-studio.cmd integration/reconciled-studioai

param([string]$Branch = "t40/projects", [switch]$InPlace)

# git and pip report progress on stderr; "Stop" would turn that into a crash. Exit codes are checked instead.
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
function Fail($msg) { Write-Host ("!! " + $msg) -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }
function Say($msg) { Write-Host ("== " + $msg) -ForegroundColor Cyan }
function Warn($msg) { Write-Host ("   " + $msg) -ForegroundColor Yellow }

# 0. symlink permission - Windows lets an ordinary account create symlinks only with Developer Mode on
#    (Settings > System > For developers). Without it the script re-launches as administrator (click Yes).
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$devMode = $false
try {
    $dm = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock" -Name AllowDevelopmentWithoutDevLicense -ErrorAction Stop
    $devMode = ($dm.AllowDevelopmentWithoutDevLicense -eq 1)
} catch { $devMode = $false }
if ($devMode -and -not $isAdmin) { Say "Developer Mode is on - running without the administrator prompt" }
if (-not $isAdmin -and -not $devMode) {
    Say "Re-launching as administrator (Windows will ask for permission: click Yes)"
    $self = $MyInvocation.MyCommand.Path
    $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ('"' + $self + '"'), $Branch)
    if ($InPlace) { $argList += "-InPlace" }
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList
    exit 0
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Fail "git is not installed or not on PATH." }

# 0b. stop any running studio FIRST (2026-09-02). Updating underneath a live server made it reload
#     itself mid-update and the browser then said "Can't reach the studio server". The updater now
#     owns the whole cycle: stop -> update -> start -> open the browser.
$running = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*serve.py*" }
if ($running) {
    Say ("Stopping the running studio (" + @($running).Count + " process(es))")
    foreach ($p in $running) { try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch {} }
    Start-Sleep -Seconds 2
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $scriptRoot ".git"))) { Fail "This folder is not a git checkout: $scriptRoot" }
$bundle = Join-Path $scriptRoot "studio-update.bundle"
# a bundle hand-delivered into the original OneDrive folder is honoured from the new location too
if (-not (Test-Path -LiteralPath $bundle)) {
    foreach ($alt in @((Join-Path $env:USERPROFILE "OneDrive\Desktop\Ai Studio\studio-update.bundle"), (Join-Path $env:USERPROFILE "Desktop\Ai Studio\studio-update.bundle"))) {
        if (Test-Path -LiteralPath $alt) { $bundle = $alt; break }
    }
}
$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"

# --- where does the studio live? -------------------------------------------------------------------
$studioRoot = $scriptRoot
$relocated = $false
$fresh = $false
if (-not $InPlace -and ($scriptRoot -like "*\OneDrive\*")) {
    $newRoot = Join-Path $env:USERPROFILE "AiStudio"
    $relocated = $true
    Say "This copy sits inside OneDrive, which stops git from replacing folders."
    Say "The studio will run from  $newRoot  from now on (the OneDrive copy is left exactly as it is)."
    if (Test-Path -LiteralPath (Join-Path $newRoot ".git")) {
        Say "$newRoot already exists - updating it"
    } else {
        Say "Creating the new checkout (copying the git history locally, no download)"
        git clone --no-checkout --quiet "$scriptRoot" "$newRoot" | Out-Host
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $newRoot ".git"))) { Fail "Could not create $newRoot" }
        git -C "$newRoot" remote set-url origin "https://github.com/Julian1973/studioai.git"
        $fresh = $true
    }
    $studioRoot = $newRoot
}
Set-Location -LiteralPath $studioRoot

# A previous run that was closed mid-way can leave git's own lock/housekeeping files behind; git refuses to
# run while they exist. Nothing of Julian's lives in these three files.
foreach ($stale in @(".git\index.lock", ".git\gc.log", ".git\gc.pid")) {
    if (Test-Path -LiteralPath $stale) {
        try { Remove-Item -LiteralPath $stale -Force; Say "Removed stale $stale from an interrupted run" } catch { Warn ("could not remove " + $stale + ": " + $_.Exception.Message) }
    }
}

# OneDrive (and an interrupted run) make git's automatic housekeeping ask "try again? (y/n)" for every
# folder it cannot delete. Switch the housekeeping off for this checkout; real symlinks on.
git config core.symlinks true
git config gc.auto 0
git config gc.autoDetach false
git config fetch.prune false
# never convert line endings on this checkout - the script store verifies every screenplay by SHA-256,
# and a CRLF checkout changed the bytes (.gitattributes pins LF for every text file as well)
git config core.autocrlf false

$before = "-"
$beforeBranch = "-"
if (-not $fresh) {
    $before = (git rev-parse --short HEAD 2>$null)
    $beforeBranch = (git rev-parse --abbrev-ref HEAD 2>$null)
    if ($before) { $before = "$before".Trim() } else { $before = "-" }
    if ($beforeBranch) { $beforeBranch = "$beforeBranch".Trim() } else { $beforeBranch = "-" }
}
Say "Studio at $studioRoot - currently $beforeBranch @ $before"

# 1. keep local work (in-place updates only - a fresh checkout has nothing local yet).
#    2026-09-02 CORRECTION: the studio's own production data lives INSIDE this folder (each project's
#    episodes/output, media, assets, canon lock, the studio's data/ state). An earlier version of this
#    step stashed EVERY edited tracked file and moved EVERY new file aside, which silently removed the
#    Box Monsters' approved Story & Direction, its beat package and its scene directions on each update.
#    Now: only a tracked file that BOTH has local edits AND is changed by the incoming update is stashed
#    (git could not fast-forward over it otherwise); every other edited file and every new file stays
#    exactly where it is. Untracked files never block a fast-forward unless the branch tracks them - those
#    few are moved aside in step 2, nothing else.
$dirty = 0
$aside = $null
$requirementsBefore = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsBefore = (Get-FileHash requirements.txt).Hash }

# 2. fetch - origin first, then the hand-delivered bundle, which wins when it is ahead of origin.
Say "Fetching origin"
git fetch origin | Out-Host
$source = "origin/$Branch"
if (Test-Path -LiteralPath $bundle) {
    Say "Fetching hand-delivered update from studio-update.bundle"
    git fetch "$bundle" "refs/heads/${Branch}:refs/remotes/bundle/$Branch" | Out-Host
    $originHas = (git rev-parse --verify --quiet "origin/$Branch")
    $bundleHas = (git rev-parse --verify --quiet "bundle/$Branch")
    $bundleAhead = $false
    if ($originHas -and $bundleHas) {
        git merge-base --is-ancestor "origin/$Branch" "bundle/$Branch"
        $bundleAhead = ($LASTEXITCODE -eq 0)
    }
    if ($bundleHas -and (-not $originHas -or $bundleAhead)) { $source = "bundle/$Branch" }
}
$sourceOk = (git rev-parse --verify --quiet $source)
if (-not $sourceOk) { Fail "Neither origin nor the bundle has a branch called $Branch." }

# A file hand-delivered into this folder that the target branch also tracks would make git refuse the
# checkout ("untracked working tree files would be overwritten"). Move those copies aside first.
if (-not $fresh) {
    $targetFiles = @(git ls-tree -r --name-only $source)
    $blocking = @(git ls-files --others --exclude-standard | Where-Object { $_ -and ($targetFiles -contains $_) })
    if ($blocking.Count -gt 0) {
        if (-not $aside) { $aside = Join-Path $studioRoot ("_local-work-" + $stamp) }
        Say ("Moving " + $blocking.Count + " hand-delivered file(s) aside (the branch carries its own copy of each)")
        foreach ($rel in $blocking) {
            $src = Join-Path $studioRoot $rel
            $dst = Join-Path (Join-Path $aside "_replaced-by-checkout") $rel
            $dstDir = Split-Path -Parent $dst
            if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
            try { Move-Item -LiteralPath $src -Destination $dst -Force } catch { Warn ("could not move " + $rel + ": " + $_.Exception.Message) }
        }
    }
}

if (-not $fresh) {
    $edited = @(git status --porcelain --untracked-files=no | Where-Object { $_ } | ForEach-Object { $_.Substring(3).Trim().Trim('"') })
    $incoming = @(git diff --name-only HEAD $source | Where-Object { $_ })
    $conflicting = @($edited | Where-Object { $incoming -contains $_ })
    $dirty = $conflicting.Count
    if ($dirty -gt 0) {
        $label = "local-edits-before-update-$stamp"
        Say "Saving $dirty edited file(s) the update also changes to git stash '$label' (nothing is deleted)"
        git stash push --message $label -- $conflicting | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "Could not save the local edits to a stash - stopping before anything is touched." }
        Say "Recover later with:  git stash list   /   git stash show -p stash@{0}   /   git checkout stash@{0} -- <path>"
    } else {
        Say "No edited file collides with this update - all local work stays in place"
    }
}

Say "Switching to $Branch (from $source)"
$haveLocal = (git rev-parse --verify --quiet "refs/heads/$Branch")
if ($haveLocal) {
    git checkout $Branch | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Could not check out $Branch." }
    git merge --ff-only $source | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Fast-forward to $source failed - the local branch has commits of its own. Nothing was discarded; ask Claude." }
} else {
    git checkout -b $Branch $source | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "Could not create branch $Branch from $source." }
    if ($source -eq "origin/$Branch") { git branch --set-upstream-to "origin/$Branch" $Branch | Out-Null }
}
if ($source -like "bundle/*") { Say "This update came from the bundle - publish it with:  git push -u origin $Branch" }
# (a blanket "git checkout -- ." used to run here; it discarded the studio's own edits to tracked
#  state files - removed 2026-09-02. Text-file links are repaired individually in step 3.)
$probe = Join-Path $studioRoot "projects\crystal-bears\episodes\scripts\Ep1_The_Adventure_Begins.txt"
if (Test-Path -LiteralPath $probe) {
    $bytes = [IO.File]::ReadAllBytes($probe)
    if ($bytes -contains 13) {
        Say "Line endings were converted on an earlier checkout - rewriting every tracked file from git (LF)"
        $keep = @(git status --porcelain --untracked-files=no | Where-Object { $_ } | ForEach-Object { $_.Substring(3).Trim().Trim('"') })
        if ($keep.Count -gt 0) { git stash push --message "line-ending-rewrite-$stamp" -- $keep | Out-Host }
        git rm -r -q --cached . | Out-Null
        git reset -q --hard HEAD | Out-Host
        if ($keep.Count -gt 0) { git stash pop | Out-Host }
        $bytes = [IO.File]::ReadAllBytes($probe)
        if ($bytes -contains 13) { Warn "the checkout still carries CRLF line endings - tell Claude" } else { Say "Line endings are LF again" }
    } else {
        Say "Line endings OK (LF)"
    }
}

# 2b. relocation - carry the assets, media and studio state across. robocopy /XC /XN /XO never overwrites
#     a file that already exists in the new checkout, and nothing is ever removed from the OneDrive copy.
if ($relocated) {
    Say "Copying assets, media and studio state from the OneDrive copy (nothing there is removed)"
    $sources = @($scriptRoot) + @(Get-ChildItem -LiteralPath $scriptRoot -Directory -Filter "_local-work-*" | ForEach-Object { $_.FullName })
    # each entry: relative folder to copy whole, or a file
    $folders = @("cb-seed", "engine\media", "engine\_director_pass", "cb-output\state", "cb-output\research", "cb-output\logs", "cb-output\director-chat", "cb-output\archive", "cb-output\creative\archive", "cb-output\asset-registry")
    $files = @("engine\locked.json", "engine\relay_state.json", "engine\notes.json", "engine\cost_ledger.jsonl", "cb-studio\data\media-index.json", "cb-studio\data\episodes.json", "cb-studio\data\project-workbench-state.json", ".env", "engine\.env", "cb-studio\.env")
    foreach ($srcRoot in $sources) {
        foreach ($rel in $folders) {
            $from = Join-Path $srcRoot $rel
            if (Test-Path -LiteralPath $from -PathType Container) {
                $to = Join-Path $studioRoot $rel
                robocopy "$from" "$to" /E /XC /XN /XO /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
                Say ("  copied " + $rel)
            }
        }
        foreach ($rel in $files) {
            $from = Join-Path $srcRoot $rel
            $to = Join-Path $studioRoot $rel
            if ((Test-Path -LiteralPath $from -PathType Leaf) -and -not (Test-Path -LiteralPath $to)) {
                $toDir = Split-Path -Parent $to
                if (-not (Test-Path -LiteralPath $toDir)) { New-Item -ItemType Directory -Path $toDir -Force | Out-Null }
                Copy-Item -LiteralPath $from -Destination $to
                Say ("  copied " + $rel)
            }
        }
        # every project's own assets and media (the old layout kept them at the same relative paths)
        $projDir = Join-Path $srcRoot "projects"
        if (Test-Path -LiteralPath $projDir -PathType Container) {
            foreach ($p in (Get-ChildItem -LiteralPath $projDir -Directory)) {
                foreach ($sub in @("assets", "episodes\media", "episodes\output\state", "episodes\output\research", "episodes\output\logs", "episodes\output\archive")) {
                    $from = Join-Path $p.FullName $sub
                    if (Test-Path -LiteralPath $from -PathType Container) {
                        $to = Join-Path (Join-Path (Join-Path $studioRoot "projects") $p.Name) $sub
                        robocopy "$from" "$to" /E /XC /XN /XO /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
                        Say ("  copied projects\" + $p.Name + "\" + $sub)
                    }
                }
            }
        }
    }
    # prove the copy landed - a OneDrive placeholder (cloud-only file) can defeat robocopy silently
    $newProj = Join-Path $studioRoot "projects"
    if (Test-Path -LiteralPath $newProj -PathType Container) {
        foreach ($p in (Get-ChildItem -LiteralPath $newProj -Directory)) {
            $assetDir = Join-Path $p.FullName "assets"
            if (-not (Test-Path -LiteralPath $assetDir -PathType Container)) { continue }
            $n = @(Get-ChildItem -LiteralPath $assetDir -File -Recurse | Where-Object { $_.Name -ne ".gitkeep" }).Count
            if ($n -eq 0) {
                foreach ($srcRoot in $sources) {
                    $from = Join-Path (Join-Path (Join-Path $srcRoot "projects") $p.Name) "assets"
                    if (Test-Path -LiteralPath $from -PathType Container) {
                        Get-ChildItem -LiteralPath $from -File -Recurse | ForEach-Object {
                            $rel = $_.FullName.Substring($from.Length).TrimStart("\")
                            $dst = Join-Path $assetDir $rel
                            $dstDir = Split-Path -Parent $dst
                            if (-not (Test-Path -LiteralPath $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
                            if (-not (Test-Path -LiteralPath $dst)) { try { Copy-Item -LiteralPath $_.FullName -Destination $dst -Force } catch { Warn ("could not copy " + $_.FullName + ": " + $_.Exception.Message) } }
                        }
                    }
                }
                $n = @(Get-ChildItem -LiteralPath $assetDir -File -Recurse | Where-Object { $_.Name -ne ".gitkeep" }).Count
            }
            if ($n -eq 0) { Warn ("projects\" + $p.Name + "\assets is EMPTY in the new studio - the source files could not be read (cloud-only OneDrive files?). Tell Claude.") } else { Say ("  projects\" + $p.Name + "\assets: " + $n + " file(s)") }
        }
    }
    # the credentials file lives beside the OneDrive copy; the launcher looks there too, but a copy next to
    # the studio makes the new location self-contained.
    $api = Join-Path (Split-Path -Parent $scriptRoot) "api.rtf"
    if ((Test-Path -LiteralPath $api) -and -not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $studioRoot) "api.rtf"))) {
        Copy-Item -LiteralPath $api -Destination (Join-Path (Split-Path -Parent $studioRoot) "api.rtf")
        Say "  copied api.rtf (credentials) beside the new studio folder"
    }
}

# 3. the virtual environment - built when missing, rebuilt when requirements changed
$python = Join-Path $studioRoot ".venv\Scripts\python.exe"
$requirementsAfter = ""
if (Test-Path -LiteralPath "requirements.txt") { $requirementsAfter = (Get-FileHash requirements.txt).Hash }
if (-not (Test-Path -LiteralPath $python) -or ($requirementsBefore -ne $requirementsAfter)) {
    Say "Building .venv (this takes a few minutes the first time)"
    if (Test-Path -LiteralPath ".venv") { Rename-Item -LiteralPath ".venv" -NewName (".venv-old-" + $stamp) -Force }
    # find a real Python 3: the one the old .venv was built from (pyvenv.cfg 'home = ...'), the py
    # launcher, python on PATH (not the Microsoft Store stub), or the usual install folders.
    $basePy = $null
    foreach ($cfg in @((Join-Path $scriptRoot ".venv\pyvenv.cfg"), (Join-Path $studioRoot ".venv-old-$stamp\pyvenv.cfg"))) {
        if (-not $basePy -and (Test-Path -LiteralPath $cfg)) {
            $home_ = (Get-Content -LiteralPath $cfg | Where-Object { $_ -match '^\s*home\s*=' } | ForEach-Object { ($_ -split '=', 2)[1].Trim() } | Select-Object -First 1)
            if ($home_ -and (Test-Path -LiteralPath (Join-Path $home_ "python.exe"))) { $basePy = Join-Path $home_ "python.exe" }
        }
    }
    if (-not $basePy) {
        $cands = @()
        $cands += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA "Programs\Python") -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName "python.exe" }
        $cands += Get-ChildItem -Path "C:\" -Directory -Filter "Python3*" -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName "python.exe" }
        $cands += Get-ChildItem -Path "C:\Program Files" -Directory -Filter "Python3*" -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName "python.exe" }
        foreach ($c in $cands) { if (-not $basePy -and (Test-Path -LiteralPath $c)) { $basePy = $c } }
    }
    if ($basePy) {
        Say "Using Python at $basePy"
        & $basePy -m venv .venv | Out-Host
    } else {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) { py -3 -m venv .venv | Out-Host } else { python -m venv .venv | Out-Host }
    }
    if (-not (Test-Path -LiteralPath $python)) { Fail "Python could not create .venv - is Python 3 installed? (https://www.python.org/downloads/ - tick 'Add python.exe to PATH')" }
    & $python -m pip install --upgrade pip | Out-Host
    & $python -m pip install -r requirements.txt | Out-Host
} else {
    Say ".venv unchanged (requirements identical)"
}

# 4. prove the checkout can run - real symlinks
Say "Checking compatibility links"
& $python "tools\check_links.py" | Out-Host
if ($LASTEXITCODE -ne 0) {
    Say "Symlinks are not real yet - re-creating them"
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
            } catch { Warn ("could not replace " + $l + ": " + $_.Exception.Message) }
        }
    }
    git checkout -- $links | Out-Host
    & $python "tools\check_links.py" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Warn "The links are still not real. Turn on Developer Mode (Settings > System > For developers), sign out and back in, then run this script again."
    }
}

# 5. a launcher on the Desktop for the new location
if ($relocated) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $launcher = Join-Path $desktop "Start AI Studio.cmd"
    $body = "@echo off`r`ncd /d `"$studioRoot`"`r`ncall `"$studioRoot\start-studio.cmd`"`r`n"
    Set-Content -LiteralPath $launcher -Value $body -Encoding ASCII
    $updater = Join-Path $desktop "Update AI Studio.cmd"
    $ubody = "@echo off`r`ncd /d `"$studioRoot`"`r`ncall `"$studioRoot\update-studio.cmd`" -InPlace`r`n"
    Set-Content -LiteralPath $updater -Value $ubody -Encoding ASCII
    Say "Desktop launchers written: 'Start AI Studio' and 'Update AI Studio'"
}

$after = (git rev-parse --short HEAD).Trim()
$subject = (git log -1 --format=%s).Trim()
Say ("Updated: " + $beforeBranch + " @ " + $before + "  ->  " + $Branch + " @ " + $after)
Say $subject
Say ("The studio now lives at: " + $studioRoot)
if ($dirty -gt 0) { Say "Your edited files are safe in git stash (git stash list)." }
if ($aside) { Say ("Your new local files are in " + $aside) }

# 6. start the studio again and open the Productions page (the stop happened in step 0b)
$startCmd = Join-Path $studioRoot "start-studio.cmd"
if (Test-Path -LiteralPath $startCmd) {
    Say "Starting the studio..."
    Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", ('"' + $startCmd + '"')) -WorkingDirectory $studioRoot
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/api/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $ready = $true }
        } catch {
            try { $null = (New-Object Net.Sockets.TcpClient).Connect("127.0.0.1", 8765); $ready = $true } catch {}
        }
    }
    if ($ready) {
        Say "The studio is up - opening it in your browser"
        Start-Process "http://127.0.0.1:8765/cb-studio/app.html"
    } else {
        Warn "The studio has not answered yet - look at the 'AI Studio' window for its message, then open http://127.0.0.1:8765/cb-studio/app.html"
    }
}
Read-Host "Done. Press Enter to close"
