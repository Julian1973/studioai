#!/usr/bin/env python3
"""Crystal Bears Studio — local server. Episodes + shared Show Bible + script storage."""
import os, re, json, http.server, pathlib, subprocess, threading, time, zipfile, signal, sys, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent   # Desktop/8Th Hour
CBGEN = ROOT / "engine"
sys.path.insert(0, str(CBGEN))   # FIXED 2026-07-17 (state-integrity checkpoint): every OTHER
# engine-touching operation runs in its own subprocess (cwd=CBGEN), which is why THAT never
# needed this — but /api/rates (and /api/learning, same bug) import an engine module directly
# in-process, which raised "No module named 'cb_costs'" until now. cb_costs.py is a pure,
# side-effect-free module at import time (constants + a path string) — safe to add once, here.
MEDIA = ROOT / "engine" / "media"
OUT = ROOT / "cb-output"
DATA = ROOT / "cb-studio" / "data"
SCRIPTS = DATA / "scripts"
DATA.mkdir(parents=True, exist_ok=True)
SCRIPTS.mkdir(parents=True, exist_ok=True)

# ── SOFTWARE-FRESHNESS GUARD ──────────────────────────────────────────────────────────────────────────────────
# The UI is the ONLY way we fire, so the server behind it must NEVER run stale code. We fingerprint every Python
# source a fire depends on (this server + the whole engine engine — Director, prompt builder, voice, pipeline) at
# startup. If any changes on disk the server is STALE: it REFUSES to fire (so a fire can never run old code) AND it
# auto-reloads itself the moment it's idle, so the UI always has the latest software behind it without anyone
# remembering to restart. (The render itself already runs in a fresh subprocess; this closes the serve.py gap.)
def _source_fingerprint():
    # THE IN-PROCESS-IMPORT GAP, CLOSED (2026-07-22, Julian: "get rid of all the old code
    # stale prompts and gates" — traced live from a real, reproducible discrepancy: a fresh
    # one-off script always reported S1.SH1's Voice direction as current, while this exact
    # long-running server, hit via curl, kept reporting it STALE, request after request,
    # for the same package on disk). Root cause: this function's own comment claimed "engine
    # modules are reloaded fresh by each per-render SUBPROCESS" — true for the OLD beat-
    # pipeline (subprocess.run per fire), but the shot pipeline's whole read/decide surface
    # (/api/departments, /api/shot-*-status, /api/shot-check-structure, /api/fire, /api/
    # approve, etc.) does `import cb_render as _CBR` DIRECTLY INSIDE THE REQUEST HANDLER — in
    # CPython, a second `import` of an already-imported module is a no-op that returns the
    # SAME cached sys.modules object, no matter how many times the file changes on disk. This
    # server had been running since well before tonight's fixes landed and was silently
    # serving whatever cb_render.py (and everything IT imports — cb_engine/cb_gen/cb_post/
    # cb_departments/paths) looked like at its own first import, with /api/health confidently
    # reporting "stale: false" throughout — exactly the class of invisible drift Julian's
    # directive named. Fixed by watching every .py file under engine/ (CBGEN) in addition to
    # this server's own file, so ANY change anywhere in that in-process-imported surface is
    # detected — this is what the function's own original comment already claimed to do
    # ("this server + the whole engine engine") without actually doing it.
    try:
        latest = os.path.getmtime(os.path.abspath(__file__))
        for root, _dirs, files in os.walk(CBGEN):
            for name in files:
                if name.endswith(".py"):
                    try:
                        m = os.path.getmtime(os.path.join(root, name))
                        if m > latest:
                            latest = m
                    except OSError:
                        pass
        return latest
    except OSError:
        return 0.0
_STARTED_FP = _source_fingerprint()
def _is_stale():
    return _source_fingerprint() > _STARTED_FP + 0.5      # 0.5s slop for save races
def _reexec():
    """Reload the studio process with the CURRENT code (idle auto-reload + the restart endpoint)."""
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
def _freshness_watch():
    """Self-heal: when the source changes and NO job is running, reload with the latest code (seamless when idle).
    FIXED 2026-07-12 (full-codebase audit continued): this only ever checked PROCS (async render jobs) — several
    handlers do real, non-trivial SYNCHRONOUS work in their own request thread and were never tracked there at
    all (the old beat-pipeline gate family's blocking subprocess.run calls — since removed in the 2026-07-16
    cutover, see the note above GATE_SEQ — plus every read-only preview endpoint and _serve_static's own
    chunked video/range streaming loop, both still live today). os.execv() replaces the
    WHOLE process image — per POSIX every thread but the caller is killed instantly, and Python sockets are
    close-on-exec by default — so a reload mid-request silently dropped that client's connection even if a
    spawned subprocess went on to finish and write locked.json unseen. Now also waits for _INFLIGHT == 0 (see its
    definition, near PROCS below), incremented/decremented around every HTTP entry point via @_tracked."""
    while True:
        time.sleep(3)
        try:
            if _is_stale() and not PROCS and _INFLIGHT == 0:
                print("⟳ studio source changed — reloading with the latest code…", flush=True)
                _reexec()
        except Exception:
            pass

def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "Untitled"

def extract_doc_text(raw, name=""):
    """Extract plain text from an uploaded script document (base64). Supports
    txt/md/fountain (direct), docx (built-in zip+xml), rtf (basic), pdf (if a lib is installed)."""
    import base64, io, html as _html
    if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    blob = base64.b64decode(raw)
    ext = (name.rsplit(".", 1)[-1].lower() if "." in name else "")
    if ext in ("txt", "md", "markdown", "fountain", "text", ""):
        return blob.decode("utf-8", "ignore")
    if ext == "docx":
        try:
            z = zipfile.ZipFile(io.BytesIO(blob))
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = (xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
                      .replace("<w:br/>", "\n").replace("<w:br></w:br>", "\n"))
            return _html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()
        except Exception as e:
            return f"[could not read .docx: {e}]"
    if ext == "rtf":
        t = blob.decode("latin-1", "ignore")
        t = re.sub(r"\\par[d]?\b", "\n", t)
        t = re.sub(r"\\'[0-9a-fA-F]{2}", "", t)
        t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
        return t.replace("{", "").replace("}", "").strip()
    if ext == "pdf":
        for lib in ("pypdf", "PyPDF2"):
            try:
                mod = __import__(lib)
                r = mod.PdfReader(io.BytesIO(blob))
                return "\n".join((p.extract_text() or "") for p in r.pages).strip()
            except Exception:
                continue
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                return "\n".join((pg.extract_text() or "") for pg in pdf.pages).strip()
        except Exception:
            return "[PDF received but no PDF text library is installed — paste the text or upload .docx/.txt instead.]"
    return blob.decode("utf-8", "ignore")

def reindex_media():
    files = sorted(p.name for p in MEDIA.glob("*")
                   if p.suffix.lower() in (".png", ".mp4", ".mp3")) if MEDIA.exists() else []
    (DATA / "media-index.json").write_text(json.dumps(files))
    return files

def reindex_episodes():
    """Merge shot packages (cb-output) + stored scripts (data/scripts) into one episode list."""
    eps = {}
    if OUT.exists():
        # prefer the BEAT package; fall back to a legacy shot package for older episodes.
        # Order by MTIME (oldest first, so the NEWEST wins the per-episode update) — this MATCHES the fire path
        # (cb_pipeline._resolve_pkg uses max-mtime), so the studio DISPLAYS the exact package it FIRES. If these two
        # disagreed (they used to: display=alphabetical, fire=newest), a re-fire would regenerate a package the studio
        # never shows → "the keyframes aren't repopulating." Same key on both = they can never diverge again.
        _mt = lambda p: p.stat().st_mtime
        for p in sorted(OUT.glob("*_beat_package.json"), key=_mt) + sorted(OUT.glob("*_shot_package.json"), key=_mt):
            try:
                d = json.loads(p.read_text())
                n = d.get("episode")
                if n is None:
                    continue
                e = eps.setdefault(n, {"number": n})
                if e.get("package") and p.name.endswith("_shot_package.json"):
                    continue   # a beat package already claimed this episode — don't overwrite with the legacy one
                units = d.get("beats", d.get("shots", []))
                e.update({"title": d.get("title", p.stem), "logline": d.get("logline", ""),
                          "leadBear": d.get("leadBear", ""), "format": d.get("format", ""),
                          "unit": d.get("unit", "shot"),
                          "beatCount": len(units), "shotCount": len(units),
                          "package": p.name, "shotPackage": p.name})
            except Exception:
                pass
    # THE SHOT PIPELINE'S OWN PACKAGES (2026-07-22, low-priority cleanup pass) — the legacy loop above only
    # ever globs *_beat_package.json/*_shot_package.json, the RETIRED beat-pipeline shape (cb_pipeline.py,
    # deleted whole in THE DESTRUCTIVE CUTOVER, 2026-07-16). The live shot pipeline (cb_engine.py/cb_render.py)
    # writes one file PER SCENE instead — {episode}_scene{N}_production_package.json — which this function
    # never looked at, so an episode already deep in real, paid shot-pipeline production (Ep1: 5 real shots
    # fired across scene 1 alone) still showed its stale, months-old legacy beat count ("43 beats," last
    # touched Jul 20) on the Episode-list card instead of what's actually live today. Aggregate real shot
    # counts across every scene package found, per episode, and let that WIN over the stale legacy count for
    # the same episode (title/logline/leadBear from the legacy pass are left alone — only the ready-count).
    if OUT.exists():
        scene_totals = {}   # episode number -> {"shots": int, "scenes": set, "files": [name, ...]}
        for p in sorted(OUT.glob("*_scene*_production_package.json")):
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            m = re.match(r"Ep(\d+)", str(d.get("episode") or ""))
            if not m:
                continue
            n = int(m.group(1))
            t = scene_totals.setdefault(n, {"shots": 0, "scenes": set(), "files": []})
            t["shots"] += len(d.get("shots") or d.get("beats") or [])
            if d.get("sceneNumber") is not None:
                t["scenes"].add(d["sceneNumber"])
            t["files"].append(p.name)
        for n, t in scene_totals.items():
            e = eps.setdefault(n, {"number": n})
            e.update({"unit": "shot", "beatCount": t["shots"], "shotCount": t["shots"],
                      "package": ", ".join(sorted(t["files"])), "shotPackage": None})
    for p in sorted(SCRIPTS.glob("Ep*.txt")):
        m = re.match(r"Ep(\d+)_", p.name)
        if not m:
            continue
        n = int(m.group(1))
        e = eps.setdefault(n, {"number": n})
        e["script"] = p.name
        e.setdefault("title", p.stem.split("_", 1)[-1].replace("_", " "))
    out = []
    for n in sorted(eps):
        e = eps[n]
        _tf = SCRIPTS / f"Ep{n}.title"                 # the EXACT user-typed title (preserves apostrophes/case) — authoritative
        if _tf.exists():
            try:
                _t = _tf.read_text().strip()
                if _t:
                    e["title"] = _t
            except Exception:
                pass
        e["status"] = (("Beats ready" if e.get("unit") == "beat" else "Shot list ready")
                       if e.get("package") else ("Script uploaded" if e.get("script") else "New"))
        out.append(e)
    (DATA / "episodes.json").write_text(json.dumps(out, indent=1))
    return out

# ---- pipeline driver: fire/approve gates via cb_pipeline (renders run in a background thread) ----
JOBS = {}  # jobId -> {jobId, scene, gate, status, log, started, ended}
PROCS = {}  # jobId -> Popen (live process group, so a firing can be stopped mid-run)

# ADDED 2026-07-12 (full-codebase audit continued, alongside the _freshness_watch fix above): PROCS only ever
# tracked async render jobs, never a synchronous request thread doing real work of its own (a blocking
# subprocess.run in the old beat-pipeline gate family — removed 2026-07-16, see the note above GATE_SEQ —
# plus a preview-endpoint subprocess and _serve_static's chunked streaming loop, both still live today) — so
# the idle-reload guard could fire mid-request. _INFLIGHT counts every live HTTP request
# (incremented/decremented by the @_tracked decorator wrapping do_GET/do_HEAD/do_POST below); _freshness_watch
# now waits for it to hit zero too, not just PROCS.
_INFLIGHT = 0
_INFLIGHT_LOCK = threading.Lock()
def _tracked(fn):
    """Wrap an HTTP handler method so it counts toward _INFLIGHT for its ENTIRE body — including an early
    return or a raised exception (both are common: nearly every handler below returns as soon as it matches
    self.path). Applied to do_GET/do_HEAD/do_POST, the three real HTTP entry points."""
    def _wrapped(self, *a, **kw):
        global _INFLIGHT
        with _INFLIGHT_LOCK:
            _INFLIGHT += 1
        try:
            return fn(self, *a, **kw)
        finally:
            with _INFLIGHT_LOCK:
                _INFLIGHT -= 1
    return _wrapped

def _jid(prefix):
    """A job ID that can NEVER collide — a second-resolution timestamp alone lets two fast fires on the same
    beat/scene overwrite each other in JOBS/PROCS, orphaning the first process with no way to track or stop it."""
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

def _humanise(line):
    """Turn a raw pipeline log line into a friendly 'current step' for the UI."""
    l = line.strip()
    low = l.lower()
    if "writers' room" in low or "writers’ room" in low: return "Writers’ Room — opening the room…"
    if "passes 0-3" in low or "heart lock" in low: return "Writers’ Room — Heart Lock · the Game · the Outline…"
    if "passes 4-7" in low or "draft locked" in low: return "Writers’ Room — drafting · co-watch · Braintrust · lock…"
    if "the scorecard" in low or "below the bar" in low or "scorecard —" in low: return "Writers’ Room — scoring the script /10…"
    if "ready for gate 1" in low: return "Writers’ Room — script written + scored ✓"
    if "the director:" in low or "reading the script" in low: return "Director — reading the script…"
    if "stage a" in low or "beat map" in low: return "Director — beat map (scenes, Pillars, emotional cores)…"
    if "stage b" in low or "beats: scene" in low or "coverage: scene" in low:
        m = re.search(r"scene (\d+)", low); return f"Director — beats: scene {m.group(1)}…" if m else "Director — beat design…"
    if "braintrust" in low: return "Director — Braintrust remake…"
    if "director complete" in low: return "Director — plan written ✓"
    if "pre-flight" in low or "context audit" in low: return "Checking the context is complete…"
    if "self-correct round" in low: return "Self-correcting — " + l.split("self-correct",1)[1].strip(": ")
    if "visual qa" in low: return "Visual QA — checking the rendered frames…"
    if "continuity check" in low or "CONTINUITY —" in l: return "Continuity check…"
    if "start =" in low and "master" in low: return f"Keeping the locked master ({l.split()[0]})…"
    if "beat keyframes:" in low: return "Building the beat keyframes…"
    if "opening keyframe ->" in low: return f"Rendering beat {l.split()[0].strip()} keyframe…"
    if "= vision of scene" in low: return f"Rendering beat {l.split()[0].strip()} (vision keyframe)…"
    if low.startswith("beat ") and "take" in low: return f"Rendering {l.split(':')[0].strip()} (the 10-12s take)…"
    if "beat driver:" in low: return "Rendering the beat takes…"
    if "scene plate (" in low or "scene plate is" in low: return "Building the scene shot (the empty plate)…"
    if "start ->" in low: return f"Rendering keyframe {l.split()[0]} (start)…"
    if "end ->" in low: return f"Rendering keyframe {l.split()[0]} (end)…"
    if l.startswith("REGEN") or "regenerat" in low or "change " in low[:8]: return "Regenerating a flagged shot…"
    if "seedance" in low or "-> Ep3_" in l and ".mp4" in l: return "Rendering the clip…"
    if "STITCH" in l: return "Stitching the scene…"
    if "POST" in l or "picture" in low or "stems" in low: return "Post — mixing + stems…"
    if "STRUCTURED SCENE BUILD DONE" in l: return "Keyframes done — verifying…"
    if "CLEAN" in l: return "Clean — it stays."
    return l[:90]

def _stream(jobId, args):
    """Run cb_pipeline streaming, so the job's current STEP is live (not blank until it finishes)."""
    job = JOBS[jobId]
    try:
        p = subprocess.Popen(["python3"] + args, cwd=str(CBGEN),
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                             stdin=subprocess.DEVNULL,   # THE STDIN-INHERITANCE BUG (2026-07-07, found while
                             # building the Studio shots editor): without this, every render/regen/fire spawned
                             # from here inherited serve.py's own stdin — if anything in the child's import chain
                             # ever reads stdin, it hangs until the caller's own timeout (or forever, for this
                             # streaming path, which sets none). Confirmed live: /api/beat-prompt's own subprocess
                             # (same missing-stdin pattern) reproducibly hung ~40s when spawned from the running
                             # server, but ran in <0.5s invoked directly from a terminal — the server's own stdin
                             # is what differs. Swept to every subprocess.run/Popen call in this file (rule 11).
                             start_new_session=True)   # own process group, so STOP kills the gate + every render it spawns
        PROCS[jobId] = p; job["pid"] = p.pid
        lines = []; _last_reindex = 0.0
        for line in p.stdout:
            line = line.rstrip()
            if not line: continue
            lines.append(line)
            job["log"] = "\n".join(lines[-250:])
            job["step"] = _humanise(line)
            # a batch job (e.g. Gate 2b building every beat in a scene) is ONE long subprocess — without this,
            # a beat finished early in the batch stays invisible until the WHOLE batch exits. Throttled to ~2s
            # so a chatty subprocess doesn't turn this into a reindex-per-line hot loop.
            now = time.time()
            if now - _last_reindex > 2:
                try: reindex_media()
                except Exception: pass
                _last_reindex = now
        p.wait()
        if job.get("stopped"):
            job["status"] = "stopped"; job["step"] = "Stopped by user."
        else:
            job["status"] = "done" if p.returncode == 0 else "failed"
            job["step"] = "Done." if p.returncode == 0 else "Failed — see log."
    except Exception as e:
        job["log"] = job.get("log", "") + f"\n{type(e).__name__}: {e}"
        job["status"] = "failed"; job["step"] = "Failed — see log."
    finally:
        PROCS.pop(jobId, None)
        # THE central completion point for every gate action fired from the studio (keyframes, clips, voice,
        # retakes, ...) — reindex here regardless of outcome (done/failed/stopped can all have left new files
        # on disk) so the UI's next media-index.json fetch reflects reality instead of the stale server-start snapshot.
        try: reindex_media()
        except Exception: pass
    job["ended"] = time.time()

def _start(jobId, gate, scene, args):
    if _is_stale():     # NEVER fire on stale code — the studio is reloading itself to the latest; re-fire in a moment
        JOBS[jobId] = {"jobId": jobId, "scene": str(scene), "gate": str(gate), "status": "failed",
                       "step": "⟳ Studio is loading the latest code — re-fire in a few seconds.",
                       "log": "The studio detected changed source and is reloading itself so every fire runs the "
                              "current software. Wait a moment, then fire again.",
                       "started": time.time(), "ended": time.time()}
        return jobId
    JOBS[jobId] = {"jobId": jobId, "scene": str(scene), "gate": str(gate),
                   "status": "running", "step": "Starting…", "log": "", "started": time.time(), "ended": None}
    threading.Thread(target=_stream, args=(jobId, args), daemon=True).start()
    return jobId

def write_script(seed, episode="Ep1"):
    """GATE 0 — the Writers' Room: turn a seed into a finished, scored, LOCKED screenplay (cb_writer)."""
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    seedpath = SCRIPTS / f"_seed_{episode}.json"
    seedpath.write_text(json.dumps(seed, ensure_ascii=False))
    return _start(_jid(f"write{episode}"), "write", "0",
                  ["cb_writer.py", str(seedpath), str(episode)])

def stop_job(jobId):
    """Hard-stop a firing gate: kill its whole process group (the pipeline + every render child it spawned)."""
    job = JOBS.get(jobId)
    if job: job["stopped"] = True
    p = PROCS.get(jobId)
    if p:
        try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            try: p.kill()
            except Exception: pass
    if job and job.get("status") == "running":
        job["status"] = "stopped"; job["step"] = "Stopped by user."; job["ended"] = time.time()
    PROCS.pop(jobId, None)
    return bool(p)

def stop_all():
    """Stop every currently-running firing."""
    ids = [jid for jid, j in JOBS.items() if j.get("status") == "running"]
    for jid in ids: stop_job(jid)
    return ids

# 2026-07-19 (full front-to-back audit): the OLD beat-pipeline gate family (fire_gate/approve_gate/
# unapprove_gate/set_master_studio/clear_master_studio/_scene_locks/_gate_ready/regen_shot/gen_audio_beat/
# gen_keyframe_beat/render_beat_clip/approve_beat/rebuild_keyframes/relay_prepare_beat/relay_approve_beat)
# was removed here — all of it called cb_pipeline.py, deleted whole in THE DESTRUCTIVE CUTOVER (89dc9a7,
# 2026-07-16). Every one of those routes is already refused at the HTTP boundary by _legacy_gone() before
# any of this dead handler code could run; confirmed via grep that nothing live still called any of them.
# GATE_SEQ below is now FULLY VESTIGIAL (2026-07-22, low-priority cleanup pass) — CORRECTED: an earlier
# comment here claimed it was "genuinely still live, read by _relock_stale_scenes()," but that whole
# Gate-1 cascade-relock subsystem (_pkg_name/_scene_beats_fingerprint/_relock_stale_scenes/
# _beat_end_frame_hash/_relock_chain_stale_scenes/locked_state — all of it a mirror of engine/
# cb_pipeline.py, itself deleted whole in THE DESTRUCTIVE CUTOVER, 89dc9a7, 2026-07-16) was found to have
# zero callers anywhere in this file or app.html and was removed the same pass. GATE_SEQ has no functional
# reader left — kept only as a documented constant a few comments elsewhere in this file still cite by
# name as an example of the "duplicate the logic, never the import" convention (_shot_pkg_path/
# scene_lineage below are the LIVE examples of that same convention today).
GATE_SEQ = ["1", "1.6", "2a", "2b", "3", "4", "5"]

# ── THE SHOT PIPELINE (cb_engine.py design → cb_render.py render loop) — ADDITIVE, 2026-07-16 ──────────────────────
# A separate, parallel surface for the shot-sized production packages (cb-output/{ep}_scene{N}_production_
# package.json). Nothing here touches GATE_SEQ, the beat pipeline, or any existing route — the two endpoints
# (/api/shot-package GET, /api/shot-run POST) plus these helpers are the whole footprint. Jobs run through the
# SAME _jid/_start/_stream runner every existing gate action uses (fresh subprocess, argv list, never a shell).
SHOT_CMDS = ("voice", "regen-voice", "animatic", "scenelook", "approve-scenelook", "reject-scenelook",
             "unapprove-scenelook", "unapprove-keyframe", "unapprove-voice", "unapprove-shot",
             "keyframe", "approve-keyframe", "reject-keyframe",
             "select-upload", "select-library", "select-previous",
             "select-scenelook-upload", "select-scenelook-library",
             "approve-voice", "reject-voice",
             "fire", "next", "approve", "reject", "stitch",
             # THE THREE-STOP LOOP'S FRONT DOOR (2026-07-21): resolves lineage/department
             # freshness/redesign-eligibility on its own and stops only at a genuine human
             # moment (storyboard read, keyframe look, clip watch) — see cb_render.advance_shot
             # and app.html's shRunAdvance/shJobHTML. Never spends on the big clip render
             # itself (that stays the explicit fire/next spend-token dance, unchanged).
             "advance")
# THE OPENING-FRAME SOURCE CHOICE (2026-07-18, Julian's directive): select-upload/select-library/
# select-previous are the three NON-GENERATION opening-frame sources (cb_render.select_keyframe_source) —
# each only ever COPIES an existing file into a new immutable candidate; none calls cb_gen. Routed through
# the identical job runner as every other shot action for one reason: cb_render.py's own ledger-mutation
# lock discipline (refuse-if-a-candidate-is-already-pending) lives in the engine, not the server, and the
# job runner is the one place that already serialises shot mutations per scene.
# "animatic" stays the CLI verb (cb_render.py keeps it as an accepted alias) — but the ARTIFACT it builds is
# the TIMING SLATE (Julian's 2026-07-16 reclassification: Seedance is a probabilistic candidate generator;
# this artifact approves dialogue accuracy / voice assignment / durations / line position ONLY, never
# staging, physical comedy or final rhythm).
# 2026-07-19: THREE-WAY duplication, not two — confirmed by audit. Keep in sync with
# app.html's REJECT_CATS AND engine/cb_render.py's FAILURE_CATEGORIES (a third,
# independently-named copy this pair alone never accounted for).
REJECT_CATEGORIES = ("identity", "geography", "action-timing", "instruction-ignored", "other")
# 2026-07-19: kept in sync with (never shared code with, across the subprocess boundary)
# engine/cb_render.py's _DEPARTMENT_WORKERS dict keys — that's the authoritative validity
# list; this is the HTTP-layer allowlist mirroring it. Confirmed in sync by audit; no test
# ties the two together yet.
DEPARTMENT_STAGES = ("look", "cinematography", "voice", "animation",
                     "review-keyframe", "review-animation", "review-final")
_SPEND_TOKEN_RE = re.compile(r"^[a-f0-9]{16,64}$")   # the SERVER-ISSUED single-use spend token (2026-07-16
# spend-protection contract): fire/next without one stores pendingSpendAuth on the shot's ledger and REFUSES;
# with one, the engine re-validates the binding hash (prompt/keyframe/refs/audio/duration/settings/rate/count)
# and refuses if ANYTHING drifted. Lowercase hex only — never a path, never shell-meaningful.
_SHOT_TOKEN = re.compile(r"^[A-Za-z0-9._-]+$")   # scene / episode / shotId — plain tokens, never a path

def _shot_pkg_path(scene, episode="Ep1"):
    """Mirrors engine/cb_render.py's _pkg_path (a separate process, no engine import here — the same
    deliberate-duplication convention as GATE_SEQ/_scene_beats_fingerprint above)."""
    return OUT / f"{episode}_scene{scene}_production_package.json"

def _storyboard_file(scene, episode="Ep1"):
    return OUT / "creative" / f"{episode}_scene{scene}_storyboard.json"


def scene_lineage(pkg, scene, episode="Ep1"):
    """THE state-integrity checkpoint's server-side lineage check (2026-07-17): mirrors
    cb_render.lineage_status EXACTLY (deliberately duplicated, never imported — the same
    no-engine-import convention this file already uses for GATE_SEQ/_shot_pkg_path/etc., so
    serve.py never needs a subprocess for a plain hash comparison). Only the server can do
    this at all: the client only ever sees pkg as already-parsed JSON, never raw file bytes,
    so it cannot itself hash the live storyboard file to check it still matches what the
    package claims it was built from. "current" is True ONLY when both hashes are present
    AND equal — never inferred true by omission."""
    sb_path = _storyboard_file(scene, episode)
    live_md5 = None
    if sb_path.exists():
        import hashlib
        live_md5 = hashlib.md5(sb_path.read_bytes()).hexdigest()
    pkg_md5 = (pkg.get("sourceStoryboard") or {}).get("md5")
    return {"current": bool(pkg_md5) and bool(live_md5) and pkg_md5 == live_md5,
            "packageStoryboardMd5": pkg_md5, "liveStoryboardMd5": live_md5,
            "packageRevision": pkg.get("revision")}


def _url_from_abs(abs_path):
    """Converts an ABSOLUTE filesystem path (as stored in continuityLedger's keyframeApproval/
    keyframeCandidate 'path' fields) into a servable /engine/media/... URL, the same
    convention shot_media_map's own _url() already uses for its conventional-filename
    lookups. Returns None for anything missing, unresolvable, or outside the approved
    media root (defence in depth — this must never become a path-traversal door)."""
    if not abs_path:
        return None
    try:
        p = pathlib.Path(abs_path).resolve()
        if not p.exists() or not p.is_relative_to(MEDIA.resolve()):
            return None
        return "/engine/media/" + p.relative_to(MEDIA.resolve()).as_posix()
    except Exception:
        return None


def shot_media_map(pkg, scene, episode="Ep1"):
    """Server-computed existence map of every shot's media (vo / keyframe / clip / harvested final frame)
    plus the scene-level animatic + stitched picture. Filenames mirror cb_render.py's own writers; the URLs
    are /engine/media/... paths the existing static route already serves (shots/ is a subfolder of the
    approved /engine/media/ root — prefix + extension both pass _static_blocked with zero policy change).

    FILE EXISTENCE HERE VERIFIES AN ASSET EXISTS — IT NEVER GRANTS APPROVAL OR STAGE STATE
    (2026-07-17 state-integrity checkpoint): this map is evidence for the client's own
    deriveSceneState, which reads the REAL approval truth from pkg.continuityLedger's
    keyframeApproval/keyframeCandidate/keyframeRejected fields plus the "lineage" block below
    — never from whether a file happens to sit at a conventional path.

    KEYFRAME URL, CORRECTED (2026-07-18, production-safety directive): a keyframe candidate/
    approval no longer lands at one fixed, conventional filename — the two-phase, non-
    destructive lifecycle (cb_render.keyframe_shot) writes every candidate to its OWN
    uniquely-named path, specifically so a fresh generation can never collide with (and
    silently overwrite) an already-approved file at a shared name. The keyframe URL is
    therefore read from the ledger's OWN recorded path (keyframeApproval, else
    keyframeCandidate) via _url_from_abs, never guessed from a filename convention."""
    shots_dir = MEDIA / "shots"
    def _url(p):
        return ("/engine/media/" + p.relative_to(MEDIA).as_posix()) if p.exists() else None
    ledger_by_id = {e.get("shotId"): e for e in (pkg.get("continuityLedger") or [])}
    shots = {}
    for s in pkg.get("shots") or []:
        sid = s.get("shotId")
        if not sid:
            continue
        led = ledger_by_id.get(sid) or {}
        kf_path = ((led.get("keyframeApproval") or {}).get("path")
                   or (led.get("keyframeCandidate") or {}).get("path"))
        shots[sid] = {"vo":         _url(shots_dir / f"{episode}_{sid}_vo.mp3"),
                      "keyframe":   _url_from_abs(kf_path),
                      # THE PENDING-CANDIDATE URL, ALWAYS EXPOSED SEPARATELY (2026-07-20,
                      # found live: S1.SH1 had a real approval AND a real, unreviewed newer
                      # candidate at the same time — "keyframe" above always prefers the
                      # approval, by design, for every OTHER screen that just wants "the
                      # current best frame". The one screen that must show the CANDIDATE
                      # itself (awaiting Julian's approve/reject) needs its own URL, never
                      # silently falling back to displaying the OLD approved image while a
                      # newer, different one is what's actually pending a decision.
                      "keyframeCandidateUrl": _url_from_abs((led.get("keyframeCandidate") or {}).get("path")),
                      "clip":       _url(shots_dir / f"{episode}_{sid}_clip.mp4"),
                      "finalFrame": _url(shots_dir / f"{episode}_{sid}_final_frame.png"),
                      # THE CANDIDATE BATCH (2026-07-16): fire/next now generate 1-4 candidates per shot
                      # ({ep}_{shotId}_c1..cN.mp4, ledger status "candidates-pending") — existence-checked
                      # here, same as every other entry, so the UI never depends on media-index.json.
                      "candidates": [c for c in ({"n": i, "url": _url(shots_dir / f"{episode}_{sid}_c{i}.mp4")}
                                                 for i in range(1, 5)) if c["url"]]}
    return {"shots": shots,
            # THE TIMING SLATE (2026-07-16 reclassification): new filename first; the pre-reclassification
            # animatic filename kept as a fallback so an older existing render still shows.
            "timingSlate": (_url(MEDIA / f"{episode}_Scene{scene}_timing_slate.mp4")
                            or _url(MEDIA / f"{episode}_Scene{scene}_animatic.mp4")),
            "animatic": _url(MEDIA / f"{episode}_Scene{scene}_animatic.mp4"),
            "picture": _url(MEDIA / f"{episode}_Scene{scene}_shots_picture.mp4"),
            "lineage": scene_lineage(pkg, scene, episode)}


# ── SCENE LOOK — server-side mirror of cb_render.scenelook_status (2026-07-18, Julian's
# gate directive): deliberately duplicated, never imported — the same no-engine-import
# convention this file already uses for GATE_SEQ/_shot_pkg_path/scene_lineage/etc. ──────────
def _scenelook_path(scene, episode="Ep1"):
    return OUT / f"{episode}_scenelook_scene{scene}.json"


def _scenelook_input_signature_server(scene, episode="Ep1"):
    """Mirrors cb_render._scenelook_input_signature exactly (deliberately duplicated, never
    imported — see this file's own standing convention). The plate's brief is a pure
    function of locations.json + style.txt — NEVER the storyboard — so this signature is
    what actually decides staleness now (2026-07-18 direct-input-lineage correction),
    replacing the old storyboard-md5 comparison below entirely."""
    import hashlib
    loc_path = ROOT / "shows" / "crystal-bears" / "canon" / "locations.json"
    style_path = ROOT / "shows" / "crystal-bears" / "laws" / "style.txt"
    locs = json.loads(loc_path.read_text()) if loc_path.exists() else {}
    entry = (locs.get(episode) or {}).get(str(scene)) or {}
    style = style_path.read_text().strip() if style_path.exists() else ""
    parts = [style] if style else []
    for key in ("look", "lighting", "weather", "colorTemperature", "definingFeature"):
        v = (entry.get(key) or "").strip()
        if v:
            parts.append(v)
    brief = " ".join(parts)
    return {"briefHash": hashlib.sha256(brief.encode()).hexdigest(), "referenceHashes": {}}


def _scenelook_load_rec_server(scene, episode="Ep1"):
    """Mirrors cb_render._load_scenelook_rec's migration exactly: an old flat-shape sidecar
    ({'status','platePath','plateHash',...}) is read as {'approved','candidate','history'}
    in memory, never written back by a read. A legacy 'approved' entry with no recorded
    inputSignature is backfilled with the CURRENT signature — honest, since the plate's
    brief is a pure function of already-unchanged canon files."""
    sc_path = _scenelook_path(scene, episode)
    if not sc_path.exists():
        return {"approved": None, "candidate": None, "history": []}
    rec = json.loads(sc_path.read_text())
    if "approved" in rec or "candidate" in rec:
        return rec
    approved = None
    if rec.get("status") == "approved" and rec.get("platePath"):
        approved = {"path": rec["platePath"], "hash": rec.get("plateHash"),
                    "inputSignature": _scenelook_input_signature_server(scene, episode),
                    "approvedAt": rec.get("approvedAt"), "reviewedBy": rec.get("reviewedBy")}
    return {"approved": approved, "candidate": None, "history": list(rec.get("history") or [])}


def _scene_cast_server(scene, episode="Ep1"):
    """Read-only: which characters appear in this scene, and the exact canonical turnaround
    (characters.json's own 'anchor' field) used as their identity reference downstream — for
    display alongside the Look Development review (Julian, 2026-07-19: "I want to see the
    characters who are in the scene and the turnarounds we are using as their references").
    The Look Development plate itself is environment-only (no characters in the fired prompt,
    by design — see continuityRules on the candidate) — this is pure context for the human
    reviewing it, never an input to the plate's own generation. Cast is the union of every
    beat's participatingCharacters in the scene's storyboard; anchor resolution mirrors
    cb_render._char_ref EXACTLY (relative to engine/, never via the characters.json symlink's
    own resolved location, which points at a different directory and would silently break
    this) — deliberately duplicated rather than imported, the same no-engine-import convention
    already used for GATE_SEQ/_shot_pkg_path/scene_lineage. Never raises: a missing storyboard
    or an unresolvable anchor degrades to an empty/partial list, never a 500."""
    try:
        sb = _storyboard_file(scene, episode)
        if not sb.exists():
            return []
        d = json.loads(sb.read_text())
        cast, seen = [], set()
        for b in (d.get("beats") or []):
            for name in (b.get("participatingCharacters") or []):
                if name not in seen:
                    seen.add(name); cast.append(name)
    except Exception:
        return []
    try:
        cf = ROOT / "engine" / "config" / "characters.json"
        chars = json.loads(cf.read_text()) if cf.exists() else {}
    except Exception:
        chars = {}
    out = []
    for name in cast:
        rec = chars.get(name) if isinstance(chars.get(name), dict) else None
        url = None
        rel = (rec or {}).get("anchor")
        if rel:
            try:
                p = (CBGEN / rel).resolve()
                if p.exists() and p.is_relative_to(ROOT.resolve()):
                    url = "/" + p.relative_to(ROOT.resolve()).as_posix()
            except Exception:
                url = None
        out.append({"name": name, "turnaroundUrl": url})
    return out


def scenelook_status_server(scene, episode="Ep1"):
    """Mirrors cb_render.scenelook_status exactly (2026-07-18 correction: the two-phase,
    non-destructive candidate lifecycle + direct-input signature, never a filename glob or
    the storyboard md5) — but returns paths as servable URLs (never raw filesystem paths —
    the client only ever sees already-approved /engine/media/ URLs, same discipline as
    shot_media_map's own _url helper)."""
    rec = _scenelook_load_rec_server(scene, episode)
    approved, candidate = rec.get("approved"), rec.get("candidate")
    # THE SIGNATURE AUTHORITY FIX (2026-07-25, Julian live-blocked on a phantom "stale"):
    # the hand-mirrored _scenelook_input_signature_server had genuinely DRIFTED from
    # cb_render._scenelook_input_signature (engine hashes the RESOLVED Look prompt;
    # the mirror hashed a hand-built field concatenation) — so the Studio showed "stale"
    # while the engine's own fire gate said "approved", an impossible-to-resolve
    # disagreement for the human in the UI. The engine is the authority (its gate is what
    # actually blocks fires) — delegate to it, same in-handler import pattern the
    # department-status route already uses; the local mirror stays only as the
    # never-500 fallback.
    try:
        import cb_render as _CBR
        current_sig = _CBR._scenelook_input_signature(scene, episode)
    except Exception:
        current_sig = _scenelook_input_signature_server(scene, episode)
    history = rec.get("history", [])
    cast = _scene_cast_server(scene, episode)

    def _as_url(entry):
        if not entry:
            return None
        return {**entry, "url": _url_from_abs(entry.get("path"))}

    if candidate:
        return {"status": "awaiting", "current": False, "approved": _as_url(approved),
                "candidate": _as_url(candidate), "history": history, "cast": cast,
                # back-compat top-level fields some older UI reads may still expect
                "plateUrl": _as_url(candidate)["url"] if candidate else None,
                "plateHash": candidate.get("hash")}
    if approved:
        approved_ok = bool(_url_from_abs(approved.get("path")))
        sig_current = approved.get("inputSignature") == current_sig
        status = "approved" if (approved_ok and sig_current) else "stale"
        au = _as_url(approved)
        return {"status": status, "current": (status == "approved"), "approved": au,
                "candidate": None, "history": history, "cast": cast,
                "plateUrl": au["url"], "plateHash": approved.get("hash")}
    last = history[-1] if history else None
    status = "rejected" if (last and last.get("outcome") == "rejected") else "none"
    return {"status": status, "current": False, "approved": None, "candidate": None,
            "history": history, "cast": cast, "plateUrl": None, "plateHash": None}



# ── THE LEGACY PIPELINE IS GONE (Julian's destructive cutover, 2026-07-16) ────────────────────
# Every route of the old beat/gate pipeline returns 410 GONE — never a redirect, never another
# generator. The single production path is: Studio disclosure -> sealed request envelope ->
# spend approval -> cb_render candidate batch -> fal provider adapter (/api/shot-*).
LEGACY_GONE_ROUTES = ['/api/fire', '/api/retakes', '/api/retake-brief', '/api/retake-csv', '/api/export-storyboard', '/api/approve', '/api/unapprove', '/api/rebuild', '/api/set-master', '/api/clear-master', '/api/regen', '/api/gen-audio', '/api/gen-keyframe', '/api/render-beat', '/api/approve-beat', '/api/relay-prepare', '/api/relay-approve', '/api/director-eye', '/api/masters', '/api/keyframe-prompt', '/api/voice-prompt', '/api/beat-sound-brief', '/api/relay-state', '/api/keyframe-qa', '/api/craft-score', '/api/beat-prompt', '/api/beat-state', '/api/retake-log', '/api/continuity', '/api/pipeline']


def _legacy_gone(handler):
    path = handler.path.split("?")[0]
    for r in LEGACY_GONE_ROUTES:
        if path == r or path.startswith(r + "/"):
            handler._json(410, {"error": "GONE — the legacy pipeline was permanently removed "
                                          "(2026-07-16 cutover). Use the Shots pipeline "
                                          "(/api/shot-package, /api/shot-run)."})
            return True
    return False

def shot_run_job(cmd, scene, episode="Ep1", shot_id=None, correction=None,
                 candidates=None, spend_token=None, category=None, candidate=None,
                 dry_run=False, source_path=None, resolution=None):
    """Map one validated shot-pipeline command onto the job runner. Argument order per cb_engine.py /
    cb_render.py's own CLIs (2026-07-16 spend-token contract — the approve-spend boolean is GONE):
      fire    -> cb_render.py fire <scene> <shotId> [episode] [--candidates N] [--spend-token <token>]
      next    -> cb_render.py next <scene> [episode] [--candidates N] [--spend-token <token>]
      approve -> cb_render.py approve <scene> <shotId> <candidateN> [episode]
      reject  -> cb_render.py reject <scene> <shotId> <correction> [--category X] [episode]
      others  -> cb_render.py <cmd> <scene> [episode]
    WITHOUT --spend-token, fire/next run fresh validation, print the SPEND DISCLOSURE, store the single-use
    token on the shot's ledger (pendingSpendAuth) and exit 1 REFUSED — the job reports "failed" with the
    disclosure in its log; that IS the designed step 1, not a malfunction. Re-posting with a mid-batch
    token resumes: only the missing candidates generate (ledger batch.status == "generating").
    Every value travels as its own argv element — never a shell string."""
    args = ["cb_render.py", cmd, str(scene)]
    if cmd in ("fire", "keyframe", "approve", "reject", "approve-keyframe", "reject-keyframe",
               "select-upload", "select-library", "select-previous",
               "approve-voice", "reject-voice", "regen-voice", "advance"):
        args.append(str(shot_id))
    if cmd == "approve" and candidate is not None:
        args.append(str(candidate))
    if cmd == "reject":
        args.append(str(correction))
        if category:
            args += ["--category", str(category)]
    if cmd == "reject-keyframe":
        args.append(str(correction))
    if cmd == "reject-scenelook":
        args.append(str(correction))
    if cmd == "reject-voice":
        args.append(str(correction))
    if cmd in ("select-upload", "select-library"):
        # THE non-generation opening-frame sources (2026-07-18): the upload/library file's own
        # path travels as its own argv element, matching cb_render.py's own CLI shape
        # (select-upload/select-library <scene> <shotId> <path> [episode]) — never a shell string.
        args.append(str(source_path))
    if cmd in ("select-scenelook-upload", "select-scenelook-library"):
        # THE non-generation SCENE LOOK sources (2026-07-19 — "still not letting me upload a
        # library image, i select it then it wants to generate"): the scene-scoped mirror of
        # select-upload/select-library above — no shotId, so the path travels right after
        # scene, matching cb_render.py's own CLI shape (select-scenelook-upload/-library
        # <scene> <path> [episode]) — never a shell string.
        args.append(str(source_path))
    args.append(str(episode))
    if cmd == "scenelook" and source_path:
        # THE SCENE LOOK PROVIDER-ROUTING FIX (2026-07-19): an OPTIONAL, explicitly-selected
        # reference travels as its own trailing argv element — cb_render.py scenelook <scene>
        # <episode> [referencePath]; omitted entirely (the normal case) means no reference at
        # all, which now correctly routes to text-to-image rather than a guaranteed-422 edit call.
        args.append(str(source_path))
    if cmd in ("fire", "next"):
        if candidates is not None:
            args += ["--candidates", str(candidates)]
        if spend_token:
            args += ["--spend-token", str(spend_token)]
        if dry_run:
            args += ["--dry-run"]      # sealed-envelope preview: no token issued, nothing stored
        if resolution:
            # THE RESOLUTION CHOICE (2026-07-23, Studio wiring): 480p is the cheap test tier,
            # 720p the final tier — validated at the HTTP boundary (do_POST) to exactly those
            # two values; the engine's own binding hash/sealed envelope already carry
            # resolution, so a disclosure at one tier can never silently fire at another.
            args += ["--resolution", str(resolution)]
    if cmd == "keyframe":
        # THE KEYFRAME SEAL, WIRED THROUGH (2026-07-22, Julian — "ensure the prompts I see in
        # the studio are the exact prompts that go to the API... your mistakes have cost me
        # money"): keyframe_shot gained the identical disclose-then-confirm spend-token seal
        # fire/next have carried since 2026-07-16 (cb_render.py's own _keyframe_binding_hash
        # docstring has the full forensic reasoning — this route had NO seal at all before
        # tonight). Mirrors the fire/next block above exactly, minus --candidates (a keyframe
        # is always exactly one candidate per fire).
        if spend_token:
            args += ["--spend-token", str(spend_token)]
        if dry_run:
            args += ["--dry-run"]
    label = "shot:" + cmd + ((":" + str(shot_id)) if shot_id else "")
    return _start(_jid(f"shot{cmd}_s{scene}"), label, scene, args)


# ── STATIC FILE HARDENING (security) ──────────────────────────────────────────────────────────────────────────
# The studio serves files from the repo ROOT, so WITHOUT this guard a browser could read engine/.env (API keys),
# *.py source, *.bak snapshots, *.log, internal config/state, node_modules and audit/archive/unpack folders.
# Policy = ALLOW-LIST by approved ROOT + extension: everything is BLOCKED by default; a file is served ONLY if it
# sits under an approved root with an approved extension, OR is an explicitly-approved exact file. Blocked → 404
# (hides existence). STATIC-SERVING ONLY: every /api route is handled in do_GET/do_POST and returns before any
# static fall-through; do_GET/do_HEAD call _serve_static() directly (never super().do_GET()/do_HEAD()), and
# _serve_static's own _static_blocked(...) call (below) is the real, single chokepoint — corrected 2026-07-08
# (full-codebase audit) after finding a dead send_head() override that this comment used to describe as the
# chokepoint; it was never actually reachable and has been removed.
#
# Approved EXACT files the UI fetches by name (case-insensitive):
_APPROVED_FILES = {
    "/cb-studio/app.html",                # the SPA entry
    "/engine/config/characters.json",     # character reference the UI reads (Show Bible + character pages)
    "/crystal_bears_locked_canon.md",     # the show-bible doc the UI renders (projects.json showBibleFile)
}                                         # add a new project's showBibleFile / configBase characters.json here if it differs
_MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
              ".mp4", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".m4a", ".ogg",
              ".csv", ".srt"}   # retake sheet (csv) + review-overlay labels (srt) download/serve
_IMG_EXT   = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
# Approved ROOTS (path-prefix → the extensions allowed under it). Nothing outside these is served.
_APPROVED_ROOTS = (
    ("/engine/media/",   _MEDIA_EXT),               # generated review media (keyframes, clips, voice)
    ("/cb-seed/assets/", _IMG_EXT),                 # character/location reference images (turnarounds, masters)
    ("/cb-output/",      {".json"}),                # output packages — FURTHER limited to *_beat_package.json (below)
    ("/cb-studio/data/", {".json", ".txt"}),        # registries (episodes/media-index/projects) + scripts the UI reads
    ("/cb-studio/",      {".css", ".js", ".ico"}),  # frontend assets, if any (app.html is an exact-approved file above)
    ("/projects/",       {".json", ".md", ".txt"} | _MEDIA_EXT),  # per-project scaffold (meta/characters/bible/episodes + its own assets/media)
)
# "projects-index.json" is retired/dead data (kept in the deny list defensively, costs nothing). "projects.json"
# is the LIVE project-registry filename (see the two real call sites reading it under cb-studio/data/) — it was
# missing from this list entirely (2026-07-08 full-codebase audit fix), meaning it was servable under the
# approved "/cb-studio/data/" root + .json extension, the exact "internal state / stale registry" class this
# list exists to refuse.
_DENY_NAMES = {"locked.json", "notes.json", "projects-index.json", "projects.json"}

def _static_blocked(urlpath):
    """True UNLESS this static path is explicitly approved (an approved exact file, OR an approved root + extension).
    Blocked by DEFAULT: all source folders, config/state files, docs, and any JSON/MD/TXT outside an approved root,
    plus all backup/temp/audit/archive folders, dotfiles and path traversal."""
    import urllib.parse
    p = urllib.parse.unquote(urllib.parse.urlparse(urlpath or "").path).split("#")[0]
    if not p.startswith("/"):
        p = "/" + p
    segs = [s for s in p.split("/") if s not in ("", ".")]
    if not segs:                              return True     # bare root / directory — no listing
    if any(s == ".." for s in segs):          return True     # path traversal
    if any(s.startswith(".") for s in segs):  return True     # dotfiles (.env, .git, .replit, .DS_Store)
    pl, name = p.lower(), segs[-1].lower()
    if name in _DENY_NAMES:                   return True     # state/stale registry, even if under an approved root
    if pl in _APPROVED_FILES:                 return False    # explicitly-approved exact file
    ext = os.path.splitext(name)[1]
    for root, exts in _APPROVED_ROOTS:
        if pl.startswith(root) and ext in exts:
            if root == "/cb-output/" and not name.endswith("_beat_package.json"):
                return True                                   # cb-output: ONLY the beat package the UI reads
            return False                                      # approved
    return True                                               # default: BLOCKED
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # CORS only here. Caching is set per-response: media revalidates (no-cache + Last-Modified + 304 in _serve_static)
        # so a regenerated keyframe/clip is never stale AND videos still stream/seek efficiently; the JSON API is no-store.
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, head=False):
        """Range-aware static serving. SimpleHTTPRequestHandler sends the whole file with a 200 (no Range), so large
        clips can't stream or seek and Safari/WebKit won't play them at all — the cause of buffering / 'some don't load'.
        This honours HTTP byte ranges (206), so videos stream in chunks and seek, and (with the threaded server) many
        load at once. Security: same _static_blocked chokepoint first."""
        if _static_blocked(self.path):
            return self.send_error(404, "Not Found")
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.isfile(path):
            return self.send_error(404, "Not Found")
        try:
            size = os.path.getsize(path); mtime = os.path.getmtime(path)
        except OSError:
            return self.send_error(404, "Not Found")
        # FRESHNESS: media is regenerated in place (a re-fired keyframe/clip keeps its filename), so the browser must
        # REVALIDATE, never serve a stale cached copy. no-cache = "check with the server first"; a 304 fast-path keeps
        # it cheap when nothing changed. This kills the "it hasn't changed" stale-image problem for good.
        ims = self.headers.get("If-Modified-Since")
        if ims and not self.headers.get("Range"):
            try:
                import email.utils
                _t = email.utils.parsedate_tz(ims)
                if _t and int(mtime) <= email.utils.mktime_tz(_t):
                    self.send_response(304)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Last-Modified", self.date_time_string(int(mtime)))
                    self.end_headers(); return
            except Exception:
                pass
        try:
            f = open(path, "rb")
        except OSError:
            return self.send_error(404, "Not Found")
        ext = os.path.splitext(path)[1].lower()
        ctype = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/x-m4v",
                 ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}.get(ext) \
                or (self.guess_type(path) or "application/octet-stream")
        try:
            start, end, partial = 0, size - 1, False
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"\s*bytes=(\d*)-(\d*)\s*$", rng)
                if m and (m.group(1) or m.group(2)):
                    if m.group(1) == "":
                        start = max(0, size - int(m.group(2)))
                    else:
                        start = int(m.group(1))
                        if m.group(2): end = min(int(m.group(2)), size - 1)
                    if start > end or start >= size:
                        self.send_response(416); self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers(); return
                    partial = True
            length = end - start + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Last-Modified", self.date_time_string(int(mtime)))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head:
                return
            f.seek(start); remaining = length
            while remaining > 0:
                chunk = f.read(min(262144, remaining))
                if not chunk: break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)
        finally:
            f.close()

    @_tracked
    def do_HEAD(self):
        return self._serve_static(head=True)

    @_tracked
    def do_GET(self):
        if _legacy_gone(self):
            return
        if self.path == "/" or self.path == "":
            self.send_response(302)
            self.send_header("Location", "/cb-studio/app.html")
            self.end_headers()
            return
        # [removed 2026-07-16 cutover: /api/pipeline — handled by the 410 gate above]
        if self.path.startswith("/api/learning"):
            # THE CREATIVE LEARNING SYSTEM, read-only view (2026-07-17): evidence counts,
            # patterns awaiting the user's decision, active human-approved principles,
            # and the improvement measures. Never mutates anything.
            try:
                import cb_learning
                self._json(200, {"metrics": cb_learning.metrics(),
                                   "patterns": cb_learning.patterns(),
                                   "activeMemory": cb_learning.active_memory()})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path.startswith("/api/storyboard"):
            # THE CREATIVE ROOM's storyboard packages (2026-07-16): read-only view of
            # cb-output/creative/. ?episode=Ep1[&scene=N] — scene omitted lists what exists.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            sc = (q.get("scene") or [None])[0]
            base = ROOT / "cb-output" / "creative"
            if sc:
                f = base / f"{ep}_scene{sc}_storyboard.json"
                if not f.exists():
                    self._json(404, {"error": f"no storyboard for scene {sc} yet"}); return
                self._json(200, json.load(open(f))); return
            vision = base / f"{ep}_episode_vision.json"
            scenes = sorted(x.name.split("_scene")[1].split("_")[0]
                             for x in base.glob(f"{ep}_scene*_storyboard.json"))
            self._json(200, {"episode": ep,
                              "vision": json.load(open(vision)) if vision.exists() else None,
                              "scenes": scenes}); return
        if self.path == "/api/jobs":
            # THE SHOT PIPELINE's own job feed (2026-07-16 cutover): the legacy /api/pipeline
            # route that incidentally carried JOBS is GONE; this is the clean replacement.
            self._json(200, {"jobs": JOBS}); return
        if self.path == "/api/health":
            return self._json(200, {"stale": _is_stale(), "started": _STARTED_FP,
                                    "current": _source_fingerprint(), "running": len(PROCS)})
        if self.path == "/api/rates":
            # Read-only, zero-risk: exposes cb_costs.py's own RATES table so the UI's pre-generation cost
            # estimates come from the same single source of truth the real spend ledger uses, rather than a
            # second, hand-typed copy in JS that could silently drift. Never mutates anything; not a pricing
            # decision surface — billing_profile.json remains the actual confirmed-plan source for spend.
            try:
                import cb_costs
                self._json(200, {"rates": {k: {"usd": v[0], "unit": v[1], "confidence": v[2]}
                                            for k, v in cb_costs.RATES.items()},
                                  "updated": cb_costs.RATES_UPDATED})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        # [removed 2026-07-16 cutover: /api/continuity — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/masters — handled by the 410 gate above]
        if self.path == "/api/loclib":
            manifest = {}
            mf = ROOT / "cb-seed" / "assets" / "locations" / "_manifest.json"
            try:
                if mf.exists():
                    manifest = json.loads(mf.read_text())
            except Exception:
                manifest = {}
            reuse = {}
            lf = ROOT / "engine" / "config" / "locations.json"
            try:
                if lf.exists():
                    locs = json.loads(lf.read_text())
                    block = locs.get("Ep1", {}) if isinstance(locs, dict) else {}
                    scene_loc = {}
                    if isinstance(block, dict):
                        for scene, sc in block.items():
                            lid = sc.get("locationId") if isinstance(sc, dict) else None
                            if lid:
                                scene_loc.setdefault(lid, []).append(scene)
                    elif isinstance(block, list):
                        for sc in block:
                            if not isinstance(sc, dict):
                                continue
                            lid = sc.get("locationId")
                            scn = sc.get("scene")
                            if lid and scn is not None:
                                scene_loc.setdefault(lid, []).append(scn)
                    for lid, scenes in scene_loc.items():
                        if len(scenes) >= 1:
                            reuse[lid] = scenes
            except Exception:
                reuse = {}
            # EVERY episode scene + its scene-shot plate (so the studio shows all scenes, not just approved ones)
            scenes = []
            try:
                locs2 = json.loads(lf.read_text()) if lf.exists() else {}
                block2 = locs2.get("Ep1", {}) if isinstance(locs2, dict) else {}
                if isinstance(block2, dict):
                    for scn, sc in sorted(block2.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 999):
                        if not isinstance(sc, dict):
                            continue
                        plate = f"Ep1_S{scn}_plate.png"
                        scenes.append({"scene": scn, "name": sc.get("name", ""), "locationId": sc.get("locationId", ""),
                                       "location": sc.get("location", ""), "look": sc.get("look", ""),
                                       "time": sc.get("time", ""), "weather": sc.get("weather", ""),
                                       "master": sc.get("master"),
                                       "shots": sc.get("shots") or [],
                                       "plate": (plate if (MEDIA / plate).exists() else None)})
            except Exception:
                scenes = []
            # uploaded scene reference images on disk (so the studio surfaces every scene shot you've dropped in,
            # even ones not yet linked to a scene plate)
            refs = []
            try:
                ad = ROOT / "cb-seed" / "assets"
                paths = list((ad / "ep1").glob("CB_Scene_*")) + list(ad.glob("CB_*_plate.*"))
                for p in sorted(set(paths)):
                    if not p.is_file():
                        continue
                    nm = (p.stem.replace("CB_Scene_", "").replace("CB_", "").replace("_anchor", "")
                            .replace("_plate", "").replace("_", " ").strip())
                    refs.append({"file": os.path.relpath(str(p), str(ROOT)), "name": nm or p.stem})
            except Exception:
                refs = []
            return self._json(200, {"manifest": manifest, "reuse": reuse, "scenes": scenes, "uploadedRefs": refs})
        if self.path == "/api/houses":
            houses = []
            try:
                cf = ROOT / "engine" / "config" / "characters.json"
                cfg = json.loads(cf.read_text()) if cf.exists() else {}
                for char, v in cfg.items():
                    if not isinstance(v, dict):
                        continue
                    h = v.get("house")
                    if not isinstance(h, dict):
                        continue
                    houses.append({"character": char,
                                   "interior": h.get("interior"), "interiorMulticam": h.get("interiorMulticam"),
                                   "exterior": h.get("exterior"), "exteriorMulticam": h.get("exteriorMulticam"),
                                   "interiorDesc": h.get("interiorDesc"), "exteriorDesc": h.get("exteriorDesc")})
            except Exception:
                houses = []
            return self._json(200, {"houses": houses})
        if self.path == "/api/projects":
            projs = []
            try:
                pf = ROOT / "cb-studio" / "data" / "projects.json"
                if pf.exists():
                    d = json.loads(pf.read_text()); projs = d.get("projects", []) if isinstance(d, dict) else []
                for p in projs:
                    pid = p.get("id", "")
                    cfgbase = p.get("configBase") or ("projects/" + pid)
                    epfile = p.get("episodesFile") or ("projects/" + pid + "/episodes.json")
                    try:
                        epf = ROOT / epfile; ed = json.loads(epf.read_text()) if epf.exists() else []
                        p["episodeCount"] = len(ed) if isinstance(ed, list) else len(ed.get("episodes", []))
                    except Exception:
                        p["episodeCount"] = 0
                    try:
                        cf = ROOT / cfgbase / "characters.json"; cd = json.loads(cf.read_text()) if cf.exists() else {}
                        p["characterCount"] = len([k for k, v in cd.items() if isinstance(v, dict) and k != "sizeClasses"])
                    except Exception:
                        p["characterCount"] = 0
            except Exception:
                projs = []
            return self._json(200, {"projects": projs})
        if self.path == "/api/reindex":
            reindex_media()
            return self._json(200, {"ok": True, "episodes": reindex_episodes()})
        # [removed 2026-07-16 cutover: /api/keyframe-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/voice-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-sound-brief — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-state — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/keyframe-qa — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/craft-score — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-state — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-log — handled by the 410 gate above]
        if self.path.startswith("/api/departments"):
            # The actual people behind the existing production stages. Read-only: returns
            # their real SKILL.md load state and any awaiting/approved work from the existing
            # scene/shot ledger. It never runs a worker or calls a provider.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            shot_id = (q.get("shotId") or [None])[0]
            stage = (q.get("stage") or [None])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if (not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                    (shot_id and not _SHOT_TOKEN.match(shot_id)) or
                    (stage and stage not in DEPARTMENT_STAGES)):
                return self._json(400, {"error": "valid scene, optional shotId/stage and episode required"})
            try:
                import cb_render as _CBR
                return self._json(200, _CBR.department_status(scene, shot_id, ep, stage))
            except _CBR.Refused as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/story-intake-status"):
            # THE DIRECTOR'S SCRIPT INTAKE (2026-07-19): read-only status for the ONE
            # department stage that runs before any scene package exists — a genuinely
            # different scope from every other department (episode-wide, not scene+shot),
            # so it is deliberately its own read route rather than reusing
            # department_status(), which always requires a package to already exist.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "valid episode required"})
            try:
                import cb_intake as _CBI
                return self._json(200, _CBI.intake_status(ep))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/scene-roster"):
            # THE CANONICAL SCENE ROSTER (2026-07-19): the approved beat package is the ONLY
            # authority for which scenes exist, their order/numbers and headings — this is
            # deliberately NOT /api/loclib (that stays the persistent, cross-episode reusable
            # location-asset manifest and is never touched by or used to derive scene
            # existence). Read-only; scenes=[] until story intake has been approved.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "valid episode required"})
            try:
                import cb_intake as _CBI
                return self._json(200, _CBI.scene_roster(ep))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/shot-package"):
            # THE SHOT PIPELINE (additive, 2026-07-16): read-only — the production package cb_engine.py
            # compiled + validated, plus a server-computed media-existence map (shot_media_map above).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/shot-package?scene=1&episode=Ep1"})
            p = _shot_pkg_path(scene, ep)
            if not p.exists():
                return self._json(404, {"error": f"no production package for {ep} scene {scene} "
                                                 f"({p.name}) — approve the storyboard to hand it to production"})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            return self._json(200, {"package": pkg, "media": shot_media_map(pkg, scene, ep), "file": p.name})
        if self.path == "/api/scenelook" or self.path.startswith("/api/scenelook?"):
            # THE SCENE LOOK GATE (additive, 2026-07-18): read-only status — never writes,
            # never assumes a file's mere presence means approval (scenelook_status_server).
            # (2026-07-19 routing fix: was a bare startswith("/api/scenelook"), which also
            # matched /api/scenelook-library — a real prefix collision that silently shadowed
            # the newer, more specific route below with this status endpoint's own response
            # shape. Narrowed to an exact match or a real query string on this exact path.)
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/scenelook?scene=1&episode=Ep1"})
            return self._json(200, scenelook_status_server(scene, ep))
        if self.path.startswith("/api/scenelook-working-status"):
            # THE SCENE LOOK WORKING PROMPT, READ SIDE (2026-07-19, Julian's directive: "edit
            # the prompts to the APIs in every section and save them") — the scene-scoped
            # sibling of /api/shot-seedance-status etc. above. READ-ONLY, zero cost.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                return self._json(200, _CBR.scenelook_working_status(scene, ep))
            except _CBR.Refused as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/shot-reassess"):
            # DIRECT-INPUT LINEAGE, READ-ONLY, ZERO SPEND (2026-07-18 production-safety
            # directive, item 3/4): for every opener shot in the scene, compares its
            # existing keyframe candidate/approval's recorded input signature against what
            # those SAME inputs (its own card, the approved plate, its own references, the
            # compiled brief, model/settings) resolve to RIGHT NOW — never the whole
            # storyboard/package md5. This is the one place engine code is imported directly
            # rather than mirrored (unlike GATE_SEQ/scene_lineage/scenelook_status_server
            # above) — reassess_keyframe is read-only and never touches cb_gen, so importing
            # it is safe; duplicating its several helper functions here would not be.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/shot-reassess?scene=1&episode=Ep1"})
            p = _shot_pkg_path(scene, ep)
            if not p.exists():
                return self._json(200, {"shots": {}})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            out = {}
            for s in pkg.get("shots") or []:
                sid = s.get("shotId")
                if not sid or s.get("sourceType") != "opener":
                    continue
                try:
                    r = _CBR.reassess_keyframe(scene, sid, ep)
                    out[sid] = {"verdict": r["verdict"], "changed": r["changed"]}
                except Exception as e:
                    out[sid] = {"verdict": "error", "changed": [], "error": str(e)[:200]}
            return self._json(200, {"shots": out})
        if self.path.startswith("/api/shot-departments"):
            # THE DEPARTMENT-DIRECTION SUMMARY, PER SHOT, READ-ONLY, ZERO SPEND (2026-07-19,
            # found live: Julian's own words — "you're not firing in the director's
            # section, so it's coming through without any directing in it"). The scene-wide
            # status strip (deriveSceneState) and the per-shot pipeline card
            # (shotPipelineState) had ALWAYS derived "Cinematography ✓ Approved" / "Voice
            # ready" purely from the LEGACY keyframeApproval/voiceApproval/ledger fields —
            # a human clicking approve on a generated image, with ZERO reference anywhere to
            # whether a real Cinematographer/DP or Voice Director/Animation Director consult
            # (the department-gate hardening's own THE CORE LAW) had ever been prepared and
            # approved. Confirmed live: S1.SH1's keyframeApproval/voiceApproval are both
            # approved (reviewedBy Julian, 2026-07-19 07:0x, hours before the department
            # system existed) while its departmentWork is a bare {} — the top strip showed
            # "Cinematography ✓ Approved" for a shot with NO specialist direction on record
            # at all. This endpoint exposes department_readiness's own real
            # approvalCurrent/directionCurrent per shot/stage so the UI can stop claiming a
            # direction happened when it didn't — same read-only precedent as
            # /api/shot-reassess just above (cb_render imported directly, never mirrored).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/shot-departments?scene=1&episode=Ep1"})
            p = _shot_pkg_path(scene, ep)
            if not p.exists():
                return self._json(200, {"shots": {}})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            out = {}
            for s in pkg.get("shots") or []:
                sid = s.get("shotId")
                if not sid:
                    continue
                per_stage = {}
                for stage in ("cinematography", "voice", "animation"):
                    try:
                        r = _CBR.department_readiness(pkg, scene, stage, sid, ep)
                        per_stage[stage] = {"applicable": r["applicable"],
                                            "prepared": r["prepared"],
                                            "approvalCurrent": r["approvalCurrent"]}
                    except Exception as e:
                        per_stage[stage] = {"applicable": True, "prepared": False,
                                            "approvalCurrent": False, "error": str(e)[:200]}
                out[sid] = per_stage
            return self._json(200, {"shots": out})
        if self.path.startswith("/api/shot-keyframe-library"):
            # THE OPENING-FRAME LIBRARY/HISTORY, READ-ONLY, ZERO SPEND (2026-07-18, Julian's
            # source-choice directive): every prior opening-frame artefact for ONE shot the
            # human may deliberately re-select — the currently-pending candidate (so it's
            # never lost the moment a fresh source-choice screen opens), the currently-
            # approved keyframe, every rejected candidate, every superseded approval. Listing
            # never mutates anything; re-selecting a listed item is a separate, explicit
            # select-library action. Imports cb_render directly (read-only, same precedent as
            # /api/shot-reassess above).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
               or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene, shotId (and optional episode) required as plain "
                                                 "tokens, e.g. /api/shot-keyframe-library?scene=1&shotId=1.B1.S1&episode=Ep1"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                items = _CBR.keyframe_library_for_shot(scene, sid, ep)
            except Exception as e:
                return self._json(400, {"error": str(e)})
            out = [{"path": it["path"], "url": _url_from_abs(it["path"]), "at": it.get("at"),
                    "outcome": it.get("outcome"), "note": it.get("note")} for it in items]
            return self._json(200, {"items": out})
        if self.path.startswith("/api/scenelook-library"):
            # THE SCENE LOOK REFERENCE LIBRARY, READ-ONLY, ZERO SPEND (2026-07-19 UX fix —
            # exposing the button, not a redesign): every prior Scene Look artefact for ONE
            # scene the human may deliberately pick as a REFERENCE for a fresh generation.
            # Unlike /api/shot-keyframe-library's items (which become the candidate
            # directly), a picked item here is always fed to the 'scenelook' cmd's
            # sourcePath — a real generate_scenelook_plate call still fires. Same
            # direct-import, read-only precedent as /api/shot-keyframe-library above.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain "
                                                 "tokens, e.g. /api/scenelook-library?scene=1&episode=Ep1"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                items = _CBR.scenelook_reference_library(scene, ep)
            except Exception as e:
                return self._json(400, {"error": str(e)})
            out = [{"path": it["path"], "url": _url_from_abs(it["path"]), "at": it.get("at"),
                    "outcome": it.get("outcome"), "note": it.get("note")} for it in items]
            return self._json(200, {"items": out})
        # ── CONTAINED CREATIVE CONTROLS — Voice/Animation working versions + the free
        # structure check (2026-07-19, Julian's directive). All four are READ-ONLY, ZERO
        # COST, direct in-process reads (same precedent as /api/shot-reassess and
        # /api/shot-keyframe-library above — cb_render's own functions already guarantee
        # no cb_gen call happens on a read).
        if self.path.startswith("/api/shot-references"):
            # THE VISIBLE REFERENCE STACK (2026-07-23, Julian — "I also want to see the
            # references that are being used on the prompt"): READ-ONLY resolution of the
            # shot's reference slots via the SAME branch logic cb_render._slot_paths uses at
            # fire time — but per-slot fault-tolerant (a missing file reports as missing,
            # never a refused response), and it never fires anything. URLs are built only
            # for files provably inside the two already-approved static roots (engine/media,
            # cb-seed/assets) via Path.is_relative_to — the existing containment discipline;
            # anything else returns url:null and the UI shows a marked missing state.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
               or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            def _ref_url(p):
                if not p:
                    return None
                try:
                    rp = pathlib.Path(p).resolve()
                    roots = (MEDIA.resolve(), (ROOT / "cb-seed" / "assets").resolve())
                    if not rp.exists() or not any(rp.is_relative_to(r) for r in roots):
                        return None
                    return "/" + rp.relative_to(ROOT.resolve()).as_posix()
                except Exception:
                    return None
            try:
                pkg, _p = _CBR.load_pkg(scene, ep)
                shot = _CBR._shot(pkg, sid)
                led = _CBR._ledger(pkg, sid)
                anchor, anchor_err = None, None
                try:
                    anchor = _CBR._anchor_for(pkg, shot)
                except Exception as e:
                    anchor_err = str(e)
                chars = _CBR._characters_cfg()
                shots_dir = MEDIA / "shots"
                out = []
                slots = shot.get("referenceSlots") or {}
                for slot in sorted((k for k in slots if k.startswith("@图")), key=lambda k: int(k[2:])):
                    role = slots[slot]; path = None; err = None
                    try:
                        if role in ("opening keyframe", "previous shot final frame"):
                            path = anchor; err = None if anchor else (anchor_err or "no anchor resolved yet")
                        elif role == "scene plate":
                            path = _CBR._plate_path(scene, ep)
                        elif str(role).startswith("pollen effect target"):
                            path = str(shots_dir / f"{ep}_{sid}_effect_target.png")
                        elif str(role).startswith("face state"):
                            path = str(shots_dir / f"{ep}_{sid}_face_state.png")
                        else:
                            path = _CBR._char_ref(role, chars)
                    except Exception as e:
                        err = str(e)
                    exists = bool(path and os.path.exists(path))
                    out.append({"slot": slot, "role": role, "exists": exists,
                                 "url": _ref_url(path) if exists else None,
                                 "error": err if not exists else None})
                audio = None
                if slots.get("@Audio1") or led.get("voPath"):
                    vp = led.get("voPath")
                    ex = bool(vp and os.path.exists(vp if os.path.isabs(str(vp)) else str(CBGEN / vp)))
                    audio = {"slot": "@Audio1", "role": slots.get("@Audio1") or "voice track",
                             "exists": ex,
                             "url": _ref_url(vp if os.path.isabs(str(vp)) else str(CBGEN / vp)) if ex else None,
                             "error": None if ex else "no take on the ledger yet"}
                return self._json(200, {"shotId": sid, "references": out, "audio": audio})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/shot-voice-status") or self.path.startswith("/api/shot-seedance-status") \
           or self.path.startswith("/api/shot-keyframe-status") or self.path.startswith("/api/shot-check-structure") \
           or self.path.startswith("/api/shot-redesign-eligibility"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
               or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                if self.path.startswith("/api/shot-voice-status"):
                    return self._json(200, _CBR.voice_performance_status(scene, sid, ep))
                if self.path.startswith("/api/shot-seedance-status"):
                    return self._json(200, _CBR.seedance_working_status(scene, sid, ep))
                if self.path.startswith("/api/shot-keyframe-status"):
                    return self._json(200, _CBR.keyframe_working_status(scene, sid, ep))
                # THE BOUNDED REDESIGN-RECOVERY ACTION, READ SIDE (2026-07-20): read-only,
                # zero cost, zero provider calls — same precedent as every other route in
                # this block. Only ever surfaces the FULL eligibility report (§1); it never
                # offers a partial/generic reset shortcut of its own.
                if self.path.startswith("/api/shot-redesign-eligibility"):
                    return self._json(200, _CBR.redesign_eligibility(scene, sid, ep))
                return self._json(200, _CBR.check_seedance_structure(scene, sid, ep))
            except _CBR.Refused as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if "/cb-studio/data/" in self.path:
            reindex_media(); reindex_episodes()
        return self._serve_static()       # range-aware (video streams + seeks), not the no-Range super().do_GET()

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    @_tracked
    def do_POST(self):
        if _legacy_gone(self):
            return
        if self.path == "/api/write":
            try:
                d = self._body(); seed = d.get("seed") or {}; episode = d.get("episode", "Ep1")
                self._json(200, {"ok": True, "jobId": write_script(seed, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/restart":     # reload the studio with the latest code (refused if a job is running)
            if PROCS:
                self._json(409, {"error": "a job is running — stop it or let it finish, then restart"}); return
            self._json(200, {"ok": True, "reloading": True})
            threading.Thread(target=lambda: (time.sleep(0.3), _reexec()), daemon=True).start()
            return
        # [removed 2026-07-16 cutover: /api/fire — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retakes — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-brief — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-csv — handled by the 410 gate above]
        if self.path == "/api/stop":
            try:
                d = self._body(); jid = d.get("jobId")
                stopped = [jid] if (jid and stop_job(jid)) else ([] if jid else stop_all())
                self._json(200, {"ok": True, "stopped": stopped, "jobs": JOBS})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        # [removed 2026-07-16 cutover: /api/export-storyboard — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/approve — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/unapprove — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/rebuild — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/set-master — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/clear-master — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/regen — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/gen-audio — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/gen-keyframe — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/render-beat — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/approve-beat — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-prepare — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-approve — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/director-eye — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/masters — handled by the 410 gate above]
        if self.path == "/api/episode":
            try:
                # FIXED 2026-07-12 (full-codebase audit continued): this handler re-implemented _body()'s exact
                # Content-Length/json.loads logic inline instead of calling the shared method every other POST
                # handler in this class already uses — a future hardening of _body() (a size cap, chunked-
                # encoding support, a clearer malformed-header error) would silently never apply to episode
                # uploads. Delegate instead.
                data = self._body()
                num = int(data.get("number"))
                title = (data.get("title") or "").strip() or f"Episode {num}"
                script = data.get("script") or ""
                if data.get("docData"):   # an uploaded script document — extract its text
                    script = extract_doc_text(data["docData"], data.get("docName", "")) or script
                fname = f"Ep{num}_{slug(title)}.txt"
                for old in SCRIPTS.glob(f"Ep{num}_*.txt"):          # one script per episode — replace, don't duplicate
                    if old.name != fname:
                        try: old.unlink()
                        except Exception: pass
                for old in SCRIPTS.glob(f"Ep{num}_*.score.json"):   # an uploaded script carries no Writers'-Room scorecard
                    try: old.unlink()
                    except Exception: pass
                (SCRIPTS / fname).write_text(script)
                (SCRIPTS / f"Ep{num}.title").write_text(title)   # the exact typed title (apostrophes/case preserved)
                eps = reindex_episodes()
                self._json(200, {"ok": True, "script": fname, "episodes": eps})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/episode-rename":
            # RENAME an episode's title AFTER saving — no re-upload. The number is the stable key; only the title
            # (and the title-slug in the script + package filenames, and the package "title" field) changes.
            try:
                d = self._body()
                num = int(d.get("number"))
                title = (d.get("title") or "").strip()
                if not title:
                    raise ValueError("a new name is required")
                newslug = slug(title)
                # rename the stored script (one per episode) + its sidecar scorecard
                for old in list(SCRIPTS.glob(f"Ep{num}_*.txt")):
                    new = SCRIPTS / f"Ep{num}_{newslug}.txt"
                    if old.name != new.name and not new.exists():
                        old.rename(new)
                for old in list(SCRIPTS.glob(f"Ep{num}_*.score.json")):
                    new = SCRIPTS / f"Ep{num}_{newslug}.score.json"
                    if old.name != new.name and not new.exists():
                        old.rename(new)
                # update the "title" field of any package + rename its file to match
                for pk in list(OUT.glob(f"Ep{num}_*_beat_package.json")) + list(OUT.glob(f"Ep{num}_*_shot_package.json")):
                    try:
                        pd = json.loads(pk.read_text()); pd["title"] = title
                        pk.write_text(json.dumps(pd, indent=1, ensure_ascii=False))
                        kind = "_beat_package.json" if pk.name.endswith("_beat_package.json") else "_shot_package.json"
                        newpk = OUT / f"Ep{num}_{newslug}{kind}"
                        if pk.name != newpk.name and not newpk.exists():
                            pk.rename(newpk)
                    except Exception:
                        pass
                (SCRIPTS / f"Ep{num}.title").write_text(title)   # exact title, authoritative for display
                eps = reindex_episodes()
                self._json(200, {"ok": True, "title": title, "episodes": eps})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-shot":
            try:
                import base64, shutil
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                if not scene:
                    raise ValueError("scene required")
                episode = str(d.get("episode") or "Ep1").strip() or "Ep1"
                fname = f"{episode}_S{scene}_plate.png"
                MEDIA.mkdir(parents=True, exist_ok=True)
                src = d.get("fromFile")
                if src:   # PULL from the library — copy an existing image to this scene's plate
                    sp = (ROOT / str(src).lstrip("/")).resolve()
                    if not (sp.is_relative_to(ROOT) and sp.is_file()):
                        raise ValueError("fromFile not found")
                    shutil.copy(str(sp), str(MEDIA / fname))
                else:     # UPLOAD — decode the image data
                    raw = d.get("imageData") or ""
                    if not raw:
                        raise ValueError("imageData or fromFile required")
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    (MEDIA / fname).write_bytes(base64.b64decode(raw))
                reindex_media()   # the file exists on disk now — without this, media-index.json (what the UI
                                  # re-fetches right after this call) stays stale and the plate never appears
                self._json(200, {"ok": True, "plate": fname})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        # [removed 2026-07-22, low-priority cleanup pass: /api/beat-update, /api/scene-update — both operated
        # exclusively on the RETIRED beat-pipeline package shape (a top-level data["beats"]/data["scenes"]
        # array, keyed by beatCode/sceneNumber, editing manifest-layer fields like opensOn/fidelityAllocation/
        # sceneLook/ambientBed that belonged solely to that now-deleted subsystem, cb_pipeline.py — gone whole
        # in THE DESTRUCTIVE CUTOVER, 2026-07-16). Confirmed zero callers anywhere in app.html (their one-time
        # caller, the old beat editor's ebSave, was removed in the same cutover) before deletion.]
        if self.path == "/api/project":
            try:
                import base64, datetime
                d = self._body()
                name = str(d.get("name", "")).strip()
                if not name:
                    raise ValueError("project name required")
                pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
                base_pid = pid; i = 2
                while (ROOT / "projects" / pid).exists():
                    pid = base_pid + "-" + str(i); i += 1
                pdir = ROOT / "projects" / pid
                (pdir / "assets").mkdir(parents=True, exist_ok=True)
                chars = {}
                for ch in (d.get("characters") or []):
                    cn = str(ch.get("name", "")).strip()
                    if not cn:
                        continue
                    entry = {"key_features": str(ch.get("keyFeatures", "")).strip()}
                    raw = ch.get("imageData") or ""
                    if raw:
                        if raw.strip().startswith("data:") and "," in raw:
                            raw = raw.split(",", 1)[1]
                        safe = re.sub(r"[^A-Za-z0-9]+", "", cn) or "Char"
                        fn = "CB_" + safe + "_anchor.png"
                        (pdir / "assets" / fn).write_bytes(base64.b64decode(raw))
                        rel = "../projects/" + pid + "/assets/" + fn
                        entry["anchor"] = rel; entry["refs"] = [rel]
                    chars[cn] = entry
                (pdir / "characters.json").write_text(json.dumps(chars, indent=2, ensure_ascii=False))
                (pdir / "show_bible.md").write_text(str(d.get("showBible", "")))
                (pdir / "episodes.json").write_text("[]")
                meta = {
                    "id": pid, "name": name, "primary": False,
                    "animationType": d.get("animationType", ""), "style": d.get("style", ""),
                    "premise": d.get("premise", ""), "audience": d.get("audience", ""),
                    "episodeLength": d.get("episodeLength", ""), "aspectRatio": d.get("aspectRatio", ""),
                    "voiceProvider": d.get("voiceProvider", ""), "musicStyle": d.get("musicStyle", ""),
                    "configBase": "projects/" + pid, "showBibleFile": "projects/" + pid + "/show_bible.md",
                    "episodesFile": "projects/" + pid + "/episodes.json", "mediaBase": "projects/" + pid + "/media",
                    "createdAt": str(datetime.date.today()),
                }
                (pdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
                pf = ROOT / "cb-studio" / "data" / "projects.json"
                pdata = json.loads(pf.read_text()) if pf.exists() else {"projects": []}
                if not isinstance(pdata, dict):
                    pdata = {"projects": []}
                pdata.setdefault("projects", []).append(meta)
                pf.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "id": pid, "project": meta})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-ref":
            try:
                import base64
                d = self._body()
                name = str(d.get("name", "")).strip()
                raw = d.get("imageData") or ""
                if not name:
                    raise ValueError("name required")
                if not raw:
                    raise ValueError("imageData required")
                if raw.strip().startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                safe = re.sub(r"[^A-Za-z0-9]+", "", name) or "Scene"
                outdir = ROOT / "cb-seed" / "assets" / "ep1"
                outdir.mkdir(parents=True, exist_ok=True)
                fn = f"CB_Scene_{safe}_anchor.png"
                (outdir / fn).write_bytes(base64.b64decode(raw))
                self._json(200, {"ok": True, "file": f"cb-seed/assets/ep1/{fn}", "name": name})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/character":
            try:
                import base64
                d = self._body()
                name = (d.get("name") or "").strip()
                if not name:
                    raise ValueError("name required")
                cpath = CBGEN / "config" / "characters.json"
                C = json.loads(cpath.read_text())
                entry = C.get(name) if isinstance(C.get(name), dict) else {}
                if d.get("anchorData"):
                    raw = d["anchorData"]
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    ext = (d.get("anchorName", "") or "").rsplit(".", 1)[-1].lower()
                    if ext not in ("png", "jpg", "jpeg", "webp"):
                        ext = "png"
                    safe = "CB_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + "_anchor." + ext
                    (ROOT / "cb-seed" / "assets").mkdir(parents=True, exist_ok=True)
                    (ROOT / "cb-seed" / "assets" / safe).write_bytes(base64.b64decode(raw))
                    entry["anchor"] = "../cb-seed/assets/" + safe
                if d.get("turnData"):
                    raw = d["turnData"]
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    ext = (d.get("turnName", "") or "").rsplit(".", 1)[-1].lower()
                    if ext not in ("png", "jpg", "jpeg", "webp"):
                        ext = "png"
                    safe = "CB_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + "_turn4." + ext
                    (ROOT / "cb-seed" / "assets").mkdir(parents=True, exist_ok=True)
                    (ROOT / "cb-seed" / "assets" / safe).write_bytes(base64.b64decode(raw))
                    turn_path = "../cb-seed/assets/" + safe
                    entry["turn4"] = turn_path
                    entry.setdefault("refs", [])
                    if turn_path not in entry["refs"]:
                        entry["refs"].insert(0, turn_path)
                for k in ("key_features", "voiceId", "size", "sizeRef", "cadence",
                          "tier", "crystal", "feeling", "colour", "note", "home"):
                    if d.get(k) not in (None, ""):
                        entry[k] = d[k]
                if str(d.get("sizeRank", "")).strip().isdigit():
                    entry["sizeRank"] = int(d["sizeRank"])
                C[name] = entry
                cpath.write_text(json.dumps(C, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "name": name, "character": entry})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/department-run":
            # One explicit specialist thinking call. The subprocess can use the LLM but its
            # cb_render command has no path to cb_gen: it stores an awaiting-approval brief
            # and stops. Existing approved work remains untouched on failure.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or "-"
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid != "-" and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                if stage not in ("look", "review-final") and sid == "-":
                    self._json(400, {"error": f"{stage} needs a shotId"}); return
                args = ["cb_render.py", "department-prepare", scene, stage, sid, ep]
                job = _start(_jid(f"department_{stage}_{sid}"),
                             f"department:{stage}:{sid}", scene, args)
                self._json(200, {"ok": True, "jobId": job})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        # THE UNBOUNDLOCALERROR CRASH, CLOSED (2026-07-22, Julian's full-audit directive — a
        # real, confirmed bug found across ~9 routes below this point): each imported its own
        # engine module (cb_render/cb_handover/cb_intake) INSIDE its own try block, AFTER
        # body-parsing code that can itself raise (a malformed/atypical POST body). The very
        # next except clause then named that module's own exception class directly (`except
        # _CBR.Refused as e:`) — but if the import line itself never ran, Python has to
        # evaluate `_CBR.Refused` to check the match and finds `_CBR` unbound, raising a raw
        # UnboundLocalError the sibling `except Exception` in the SAME try never catches (it
        # already failed to match on the first clause) — it propagates out of do_POST
        # entirely, crashing the request with a bare traceback instead of the intended clean
        # {"error": ...} JSON. Every one of those specific-exception clauses did the byte-
        # identical thing as its own following `except Exception` clause (confirmed by direct
        # comparison before removing any of them), so the fix was simply to delete the
        # redundant specific clause at each site — the generic `except Exception as e:` left
        # in place catches everything the removed clause did, plus the crash case it couldn't.
        if self.path in ("/api/department-save", "/api/department-decide"):
            # Plain ledger edits/decisions: no LLM and no media provider call.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or None
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                import cb_render as _CBR
                if self.path == "/api/department-save":
                    rec = _CBR.save_department_candidate(
                        scene, stage, text=d.get("text"), lines=d.get("lines"), shot_id=sid,
                        episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                else:
                    rec = _CBR.decide_department(
                        scene, stage, str(d.get("verdict") or ""), shot_id=sid,
                        note=str(d.get("note") or ""), episode=ep,
                        reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "record": rec})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-override-dialogue":
            # THE SCRIPT-OVERRIDE AUTHORITY (2026-07-20, Julian — "I have the ability to
            # override the script, no one else"): the ONE route that can change the actual
            # WORDS of a locked dialogue line, deliberately separate from
            # /api/department-save's per-line editor (which can only touch acting-direction
            # [tags], never the words — cb_departments.validate_voice_direction hard-refuses
            # a word change there, by design). Synchronous, in-process, zero LLM/provider —
            # same cost profile as department-save/decide above — but it DOES touch story
            # content, so unlike those routes it is never auto-fired by anything; every call
            # here is a deliberate, named human action, logged with `by`.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                sid = str(d.get("shotId", "")).strip()
                line_index = d.get("lineIndex")
                new_text = d.get("newText")
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        not sid or not _SHOT_TOKEN.match(sid) or
                        not isinstance(line_index, int) or line_index < 0):
                    self._json(400, {"error": "scene, episode, shotId and a non-negative "
                                               "integer lineIndex are required"}); return
                import cb_handover as _CBH
                rec = _CBH.override_locked_dialogue(
                    str(_storyboard_file(scene, ep)), int(scene), sid, line_index, new_text,
                    episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "record": rec})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/department-revalidate":
            # THE BOUNDED LEGACY-APPROVAL REVALIDATION PATH (Julian's directive, 2026-07-20
            # — "Do not Refire any direction, generate media, call an LLM/provider, or
            # change creative content"): zero LLM, zero provider, zero job/subprocess — the
            # identical synchronous, in-process pattern as decide/save above, never the
            # department-run job path (which exists only because THAT route makes a real
            # specialist call). Re-binds an already-approved, content-unchanged direction to
            # the corrected dependency-signature formula; refuses outright if the record
            # isn't genuinely eligible right now (cb_render.revalidate_department re-derives
            # eligibility fresh against the just-loaded package, never trusting a cached
            # read from an earlier status check).
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or None
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                import cb_render as _CBR
                event = _CBR.revalidate_department(
                    scene, stage, shot_id=sid, episode=ep,
                    reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "event": event})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/department-restore-history":
            # THE HISTORY-MATCH RESTORE PATH (2026-07-20, found investigating the REAL
            # S1.SH1 record against the sealed-evidence mechanism above — a DIFFERENT,
            # more consequential action than /api/department-revalidate, which only ever
            # re-stamps an unchanged approval's version. This one changes WHICH text is
            # live: it is shown ONLY when a later decision superseded the exact
            # Cinematography Direction that sealed keyframe evidence proves actually
            # generated and was approved against the current keyframe (the "no refiring
            # an unchanged specialist direction merely to repair technical lineage"
            # mistake this whole directive exists to prevent). Cinematography-only —
            # matches cb_render.py's own bounded scope for this mechanism. Zero LLM, zero
            # provider, zero job/subprocess.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                sid = str(d.get("shotId", "")).strip() or None
                if not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or not sid:
                    self._json(400, {"error": "invalid scene, episode or shotId"}); return
                import cb_render as _CBR
                event = _CBR.restore_cinematography_from_history(
                    scene, sid, episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "event": event})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/department-unapprove":
            # THE ALWAYS-AVAILABLE "REJECT" FOR AN ALREADY-APPROVED DIRECTION (2026-07-20,
            # Julian — "every stage should have an approve and reject and refire button"):
            # decide_department's own reject only ever resolves a PENDING candidate; this is
            # the sibling action for a direction that's already approved, so the same three
            # verbs are available no matter what state a stage is in. Moves the current
            # approval to history (never deleted) and clears it. Zero LLM, zero provider,
            # zero job/subprocess — the identical synchronous, in-process pattern as
            # decide/save/revalidate above.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or None
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                import cb_render as _CBR
                event = _CBR.unapprove_department(
                    scene, stage, shot_id=sid, episode=ep,
                    note=str(d.get("note") or ""), reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "event": event})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/story-intake-run":
            # THE DIRECTOR'S SCRIPT INTAKE — one real thinking call (2026-07-19). Episode-
            # scoped, runs BEFORE any scene package exists, so it cannot reuse
            # /api/department-run (which always requires one). Background job, matching
            # every other specialist-thinking call in this studio — no media provider is
            # reachable from cb_intake.py at all.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "valid episode required"}); return
                args = ["cb_intake.py", "run", ep]
                job = _start(_jid(f"storyintake_{ep}"), "storyintake", "-", args)
                self._json(200, {"ok": True, "jobId": job})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/story-intake-decide":
            # Approve/reject the visible candidate. No LLM, no media provider — approve()
            # is the ONLY place that writes the canonical beat package + episode vision
            # that unlock cb_creative.py's own scene/storyboard process; reject() archives
            # the candidate (never deletes) and leaves no canonical package.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                verdict = str(d.get("verdict") or "").strip()
                if not _SHOT_TOKEN.match(ep) or verdict not in ("approve", "reject"):
                    self._json(400, {"error": "episode and verdict (approve|reject) required"})
                    return
                import cb_intake as _CBI
                rec = _CBI.decide_intake(ep, verdict, note=str(d.get("note") or ""),
                                         reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "record": rec})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/creative-run":
            # THE CREATIVE ROOM job runner (2026-07-16): vision / scene passes — OpenAI text
            # calls only; no media provider, no spend token (cb_creative imports no adapter).
            try:
                d = self._body()
                cmd = str(d.get("cmd", "")).strip()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if cmd not in ("vision", "scene", "envelope", "migrate"):
                    self._json(400, {"error": "cmd must be vision|scene|envelope|migrate"}); return
                if cmd == "scene" and not re.match(r"^\w+$", scene):
                    self._json(400, {"error": "scene must be a plain token"}); return
                args = ["cb_creative.py", cmd] + ([scene, ep] if cmd == "scene" else [ep])
                self._json(200, {"ok": True,
                                  "jobId": _start(_jid(f"creative_{cmd}_{scene or ep}"),
                                                   "creative:" + cmd, scene or "-", args)})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/api/storyboard-approve":
            # HUMAN GATE A: approve/annotate at episode/scene/beat/shot level — a plain
            # creative note in the user's own words; no compiler fields exposed.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                sc = str(d.get("scene", "")).strip()
                f = ROOT / "cb-output" / "creative" / f"{ep}_scene{sc}_storyboard.json"
                if not f.exists():
                    self._json(404, {"error": "no storyboard"}); return
                original_storyboard = f.read_bytes()
                pkg = json.load(open(f))
                target = str(d.get("target", "scene"))     # scene | beatId | shotId
                verdict = str(d.get("verdict", "approved"))
                note = str(d.get("note", "")).strip()
                stamp = {"state": verdict, "note": note, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": str(d.get("by") or "Julian")}
                if target == "scene":
                    pkg["approvalState"] = verdict
                    pkg["humanNote"] = note
                else:
                    for coll in ("beats", "shots"):
                        for item in pkg.get(coll, []):
                            if item.get("beatId") == target or item.get("shotId") == target:
                                item["approvalState"] = verdict
                                item["humanNote"] = note
                pkg.setdefault("approvalLog", []).append({"target": target, **stamp})
                json.dump(pkg, open(f, "w"), indent=1, ensure_ascii=False)
                handover = None
                if target == "scene" and verdict == "approved":
                    # Approval is the one real doorway into production. Build/validate the
                    # canonical package transactionally, then carry forward the untouched
                    # ledger for every byte-identical shot. If handover fails, restore the
                    # storyboard decision rather than displaying a false green approval.
                    try:
                        import cb_handover
                        shot_ids = [s.get("shotId") for s in (pkg.get("shots") or []) if s.get("shotId")]
                        preview, _ = cb_handover.promote_to_canonical(
                            str(f), sc, shot_ids, ep, dry_run=True, log=lambda *a, **k: None)
                        if not (preview.get("validation") or {}).get("passed"):
                            issues = [x for x in (preview.get("validation") or {}).get("issues", [])
                                      if x.get("severity") == "ERROR"]
                            raise RuntimeError("production handover validation failed" +
                                               (f": {issues[0].get('code')}" if issues else ""))
                        promoted, archived = cb_handover.promote_to_canonical(
                            str(f), sc, shot_ids, ep, dry_run=False, log=lambda *a, **k: None)
                        handover = {"revision": promoted.get("revision"),
                                    # 2026-07-20 rename (Julian's "no straitjacket" ruling —
                                    # see cb_handover.promote_to_canonical): the ledger now
                                    # always carries forward; "reset" no longer exists as a
                                    # concept here, only an advisory contentChanged list.
                                    "carriedForward": (promoted.get("handover") or {}).get(
                                        "carriedForwardShots", []),
                                    "contentChanged": (promoted.get("handover") or {}).get(
                                        "contentChangedShots", []),
                                    "archivedPrevious": str(archived) if archived else None}
                    except Exception as he:
                        f.write_bytes(original_storyboard)
                        self._json(409, {"error": f"Storyboard was not approved because production "
                                                        f"handover failed safely: {he}"})
                        return
                # THE CREATIVE LEARNING SYSTEM (2026-07-17): every human review verdict is
                # evidence. The user's plain-language note is preserved verbatim; the system
                # proposes a classification but PROMOTES NOTHING — promotion is an explicit,
                # separate action (/api/learning-promote). Fail-soft: learning capture never
                # breaks the approval itself.
                learning = None
                try:
                    import cb_learning
                    learning = cb_learning.human_feedback(
                        verdict, note, scene=sc,
                        beat=target if ".B" in target and ".S" not in target else None,
                        shot=target if ".SH" in target or ".S" in target else None,
                        episode=ep, asset=f.name, by=stamp["by"])
                    learning = {k: (v if k != "evidenceCaptured" else
                                     {"evidenceId": v["evidenceId"], "outcome": v["outcome"]})
                                 for k, v in learning.items()}
                except Exception as le:
                    learning = {"captureError": str(le)}
                self._json(200, {"ok": True, "learning": learning, "handover": handover})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/api/learning-promote":
            # THE EXPLICIT 'Promote to Creative Memory' ACTION — never silent, never automatic
            try:
                import cb_learning
                d = self._body()
                rec = cb_learning.promote(str(d.get("patternId", "")),
                                            by=str(d.get("by") or "Julian"),
                                            applied_source_ref=str(d.get("ref") or ""),
                                            decision=str(d.get("decision") or ""),
                                            activation_note=str(d.get("note", "")))
                self._json(200, {"ok": True, "activated": rec})
            except Exception as e:
                self._json(409, {"error": str(e)})
            return
        if self.path == "/api/shot-keyframe-upload":
            # THE UPLOAD SOURCE, STEP 1 OF 2 (2026-07-18, Julian's source-choice directive):
            # decodes a base64 image (same data-URI-or-raw convention as extract_doc_text's own
            # script-upload path above) and writes it to a holding file under the approved
            # engine/media tree — NOT yet a keyframe candidate. Step 2 is the client's own
            # follow-up /api/shot-run {cmd:"select-upload", sourcePath: <this path>} call, which
            # does the actual preserve-original + immutable-candidate-copy work in cb_render.py.
            # This endpoint alone never touches any shot's ledger.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                raw = d.get("dataB64"); filename = str(d.get("filename") or "upload.png")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                import base64
                if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                blob = base64.b64decode(raw)
                ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ".png"
                if ext not in (".png", ".jpg", ".jpeg", ".webp"):
                    ext = ".png"
                incoming = MEDIA / "uploads_incoming"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{ep}_{sid}_incoming_{uuid.uuid4().hex[:8]}{ext}"
                out.write_bytes(blob)
                self._json(200, {"ok": True, "sourcePath": str(out)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-approve-stage":
            # ONE CLICK PER HUMAN DECISION (2026-07-23, Julian live — "i approved the voice
            # and its not moving it"; forensics: his three approve-voice clicks all REFUSED
            # outright, "no voice track to approve" — the UI had presented a stray on-disk
            # file as a take while the LEDGER's voPath was None, and the separate Voice
            # DIRECTION approval was a second click he reasonably read as the same decision).
            # This endpoint performs the WHOLE chain one human "approve" logically implies,
            # each step still individually recorded on the ledger under his name — the audit
            # trail stays complete; only the UX collapses:
            #   voice:      approve the Voice Director's pending direction candidate (if
            #               any), then approve the generated take IF the ledger has one
            #               (voPath — a file on disk is never a take). No take -> the chain
            #               STOPS and says so; the paid generation is never auto-fired by an
            #               approve click.
            #   animation:  prepare the direction first if nothing is prepared (a text-only
            #               specialist consult, no media spend), then approve the pending
            #               candidate.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                by = str(d.get("by") or "Julian")
                stage = str(d.get("stage", "")).strip()
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if stage not in ("voice", "animation"):
                    self._json(400, {"error": "stage must be voice or animation"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                _quiet = lambda *a, **k: None
                steps = []
                pkg, _p = _CBR.load_pkg(scene, ep)
                work, _sv = _CBR._department_container(pkg, scene, sid, stage, ep)
                has_cand = bool(work.get("candidate")); has_appr = bool(work.get("approved"))
                if stage == "animation" and not has_cand and not has_appr:
                    _CBR.prepare_department(scene, stage, sid, ep, log=_quiet)
                    steps.append("direction prepared (specialist consult — no media, no spend)")
                    has_cand = True
                if has_cand:
                    _CBR.decide_department(scene, stage, "approved", shot_id=sid, episode=ep,
                                            reviewed_by=by, log=_quiet)
                    steps.append("direction approved")
                elif has_appr:
                    steps.append("direction already approved")
                if stage == "voice":
                    pkg2, _p2 = _CBR.load_pkg(scene, ep)
                    led = _CBR._ledger(pkg2, sid)
                    if led.get("voPath"):
                        if (led.get("voiceApproval") or {}).get("approved"):
                            steps.append("take already approved")
                        else:
                            _CBR.approve_voice(scene, sid, ep, reviewed_by=by, log=_quiet)
                            steps.append("take approved")
                        complete = True
                        msg = "Voice complete — direction and take both approved."
                    else:
                        complete = False
                        msg = ("Voice direction approved. No take exists on the ledger yet — "
                               "Generate voice (a paid ElevenLabs call) is the next step; "
                               "it is never auto-fired by an approve click.")
                else:
                    complete = True
                    msg = "Animation Direction approved."
                self._json(200, {"ok": True, "stage": stage, "steps": steps,
                                  "complete": complete, "message": msg})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-promote":
            # THE DRAFT-SHOT PROMOTION (2026-07-23, Julian live — "I have no way of going to
            # the next shot"): promotes ONE storyboard-drafted shot into the canonical
            # production package via cb_handover.promote_to_canonical. THAT CALL IS A
            # WHOLE-ARRAY REPLACE — so this endpoint ALWAYS passes the full cumulative shot
            # list (every already-promoted shot, in storyboard order) PLUS the new one;
            # passing only the new shot would silently delete the approved shots from the
            # package. The promotion is transactional server-side (a failing candidate never
            # touches the live package; the old package is archived, never deleted) and the
            # ledger ALWAYS carries forward for shots with a prior entry, so S1.SH1/SH2's
            # approvals survive intact. Zero LLM, zero provider calls. A dry run validates
            # and reports without writing anything at all.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                sb_path = _storyboard_file(scene, ep)
                if not sb_path.exists():
                    self._json(404, {"error": f"no storyboard for scene {scene}"}); return
                sb = json.loads(sb_path.read_text())
                draft_ids = [s.get("shotId") for s in (sb.get("shots") or []) if s.get("shotId")]
                if sid not in draft_ids:
                    self._json(404, {"error": f"{sid} is not in scene {scene}'s storyboard"}); return
                pkg_path = _shot_pkg_path(scene, ep)
                existing = []
                if pkg_path.exists():
                    try:
                        existing = [s.get("shotId") for s in (json.loads(pkg_path.read_text()).get("shots") or [])
                                    if s.get("shotId")]
                    except Exception:
                        existing = []
                if sid in existing:
                    self._json(400, {"error": f"{sid} is already promoted"}); return
                # cumulative list in STORYBOARD order (the story's own sequence), plus —
                # defensively — any already-promoted shot the storyboard no longer names
                # (never silently dropped from the package by this endpoint).
                keep = set(existing) | {sid}
                shot_ids = [i for i in draft_ids if i in keep] + [i for i in existing if i not in draft_ids]
                import cb_handover as _CBH
                preview, _ = _CBH.promote_to_canonical(str(sb_path), scene, shot_ids, ep,
                                                        dry_run=True, log=lambda *a, **k: None)
                rep = (preview.get("validation") or {})
                if not rep.get("passed"):
                    errs = [x for x in rep.get("issues", []) if x.get("severity") == "ERROR"]
                    self._json(409, {"error": "promotion refused — the candidate package failed design "
                                               "validation" + (f": {errs[0].get('code')}" if errs else ""),
                                      "issues": errs[:5]}); return
                if d.get("dryRun"):
                    self._json(200, {"ok": True, "dryRun": True, "wouldPromote": shot_ids,
                                      "carriedForward": (preview.get("handover") or {}).get("carriedForwardShots", [])})
                    return
                promoted, archived = _CBH.promote_to_canonical(str(sb_path), scene, shot_ids, ep,
                                                                dry_run=False, log=lambda *a, **k: None)
                self._json(200, {"ok": True, "promoted": sid, "shotIds": shot_ids,
                                  "revision": promoted.get("revision"),
                                  "carriedForward": (promoted.get("handover") or {}).get("carriedForwardShots", []),
                                  "contentChanged": (promoted.get("handover") or {}).get("contentChangedShots", []),
                                  "archivedPrevious": str(archived) if archived else None})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-special-ref-upload":
            # THE SPECIAL-REFERENCE UPLOAD (2026-07-23, Studio wiring for Julian's split-
            # generation block): writes a prepared FACE-STATE or EFFECT-TARGET reference to
            # the exact fixed, deterministic path cb_render._slot_paths already resolves
            # ({episode}_{shotId}_face_state.png / _effect_target.png under engine/media/
            # shots/) AND registers the matching referenceSlots role on the canonical
            # package (next free @图N slot) so the next fire actually attaches it. A slot
            # whose role already matches only gets its FILE refreshed (and its role note
            # updated if a new one is supplied) — never a duplicate slot. Zero provider
            # calls; changing referenceSlots deliberately invalidates any pending spend
            # token via the engine's own binding hash (that is the seal working, not a bug).
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                kind = str(d.get("kind", "")).strip()
                raw = d.get("dataB64")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if kind not in ("face_state", "effect_target"):
                    self._json(400, {"error": "kind must be face_state or effect_target"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                import base64
                if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                blob = base64.b64decode(raw)
                shots_dir = MEDIA / "shots"
                shots_dir.mkdir(parents=True, exist_ok=True)
                out = shots_dir / f"{ep}_{sid}_{kind}.png"
                if blob[:8] == b"\x89PNG\r\n\x1a\n":
                    out.write_bytes(blob)
                else:
                    # the resolver's contract path is .png — convert honestly rather than
                    # writing mislabelled JPEG/WebP bytes at a .png path.
                    try:
                        import io as _io
                        from PIL import Image
                        Image.open(_io.BytesIO(blob)).convert("RGB").save(out, "PNG")
                    except Exception:
                        self._json(400, {"error": "the image must be a PNG (or install Pillow so "
                                                   "the studio can convert it)"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                pkg, ppath = _CBR.load_pkg(scene, ep)
                shot = _CBR._shot(pkg, sid)
                slots = shot.setdefault("referenceSlots", {})
                prefix = "face state" if kind == "face_state" else "pollen effect target"
                default_role = ("pollen effect target — material and colour only"
                                if kind == "effect_target"
                                else "face state — prepared reference image (see attached frame)")
                note = str(d.get("note") or "").strip()
                role = (prefix + " — " + note) if note else default_role
                existing = next((k for k, v in slots.items() if str(v).startswith(prefix)), None)
                if existing:
                    slot = existing
                    if note:
                        slots[existing] = role
                    role = slots[existing]
                else:
                    nums = [int(k[2:]) for k in slots if k.startswith("@图") and k[2:].isdigit()]
                    slot = "@图" + str((max(nums) if nums else 0) + 1)
                    slots[slot] = role
                _CBR._save(pkg, ppath)
                reindex_media()
                self._json(200, {"ok": True, "path": str(out), "slot": slot, "role": role,
                                  "url": "/engine/media/shots/" + out.name})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-vo-pad-master":
            # THE 15s PADDED VOICE MASTER (2026-07-23, Studio wiring): a purely MECHANICAL
            # ffmpeg pad of the shot's already-approved take — leading silence (adelay) +
            # silent tail (apad) trimmed to exactly 15.0s — matching the hand-built
            # Ep1_S1.SH2_vo_master15.mp3 precedent (voProvenance carriedFrom/md5/note shape
            # mirrored exactly). Never a new voice generation, never an ElevenLabs call; the
            # audio content itself is unaltered. Re-approves via the SAME cb_render.
            # approve_voice every manual approval uses, with reviewed_by naming the pad as
            # mechanical — so the provenance chain is honest on the ledger, never implied.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                by = str(d.get("by") or "Julian")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                try:
                    offset = float(d.get("offsetSec") or 0.0)
                except (TypeError, ValueError):
                    offset = -1.0
                # THE TARGET DURATION (2026-07-24, S1.SH3 retiming): the master's length was
                # hardcoded 15.0 — but a shot whose own durationSec is shorter deserves a
                # duration-MATCHED master (cb_render._handle_duration now fires exactly the
                # master's length when it matches the shot's floor). Default stays 15.0.
                try:
                    target = float(d.get("targetSec") or 15.0)
                except (TypeError, ValueError):
                    target = -1.0
                if not (1.0 <= target <= 15.0):
                    self._json(400, {"error": "targetSec must be a number between 1 and 15"}); return
                if not (0.0 <= offset <= target - 0.5):
                    self._json(400, {"error": f"offsetSec must be a number between 0 and {target - 0.5}"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                pkg, ppath = _CBR.load_pkg(scene, ep)
                led = _CBR._ledger(pkg, sid)
                vo = led.get("voPath")
                if not vo:
                    self._json(400, {"error": f"{sid} has no voice track — generate and approve one first"}); return
                if not (led.get("voiceApproval") or {}).get("approved"):
                    self._json(400, {"error": f"{sid}'s take is not approved — the 15s master pads an "
                                               f"ALREADY-APPROVED take, never an unreviewed one"}); return
                src = pathlib.Path(vo)
                if not src.is_absolute():
                    src = CBGEN / vo          # cb_render stores engine-relative paths when run via its CLI
                if not src.exists():
                    self._json(400, {"error": f"{sid}'s approved take file is missing on disk ({vo})"}); return
                shots_dir = MEDIA / "shots"
                shots_dir.mkdir(parents=True, exist_ok=True)
                tgt_label = f"{target:g}"
                out = shots_dir / f"{ep}_{sid}_vo_master{tgt_label}.mp3"
                if src.resolve() == out.resolve():
                    self._json(400, {"error": f"{sid}'s current take IS already the {tgt_label}s master — "
                                               f"pad from the original take (voProvenance.carriedFrom), "
                                               f"or regenerate the voice first"}); return
                ms = int(round(offset * 1000))
                p = subprocess.run(["ffmpeg", "-y", "-i", str(src),
                                     "-af", f"adelay={ms}:all=1,apad", "-t", f"{target}", str(out)],
                                    capture_output=True, text=True, timeout=180)
                if p.returncode != 0 or not out.exists():
                    self._json(500, {"error": "ffmpeg failed building the padded master: " +
                                               (p.stderr or "")[-300:]}); return
                import hashlib
                md5_8 = hashlib.md5(out.read_bytes()).hexdigest()[:8]
                led["voPath"] = str(out)
                led["voProvenance"] = {
                    "carriedFrom": str(vo), "md5": md5_8,
                    "note": (f"{tgt_label}s padded master built mechanically with ffmpeg "
                             f"(adelay {offset}s + apad, -t {target}) from the already-approved take; "
                             f"audio content unaltered, no new voice generation. "
                             f"Built via the Studio by {by}.")}
                _CBR._save(pkg, ppath)
                approval = _CBR.approve_voice(
                    scene, sid, ep,
                    reviewed_by=f"{by} (mechanical {tgt_label}s pad of the already-approved take, "
                                 f"offset {offset}s — no new voice generation)",
                    log=lambda *a, **k: None)
                reindex_media()
                self._json(200, {"ok": True, "voPath": str(out),
                                  "url": "/engine/media/shots/" + out.name,
                                  "provenance": led["voProvenance"], "approval": approval})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scenelook-upload":
            # THE SCENE LOOK UPLOAD SOURCE (2026-07-19 UX fix): scene-scoped mirror of
            # /api/shot-keyframe-upload above — no shotId, since Scene Look has no shot.
            # Decodes a base64 image and writes it to the same holding tree; the client's
            # own follow-up /api/shot-run {cmd:"scenelook", sourcePath: <this path>} call is
            # what actually fires generate_scenelook_plate with it as reference_path. This
            # endpoint alone never touches any ledger and never calls cb_gen.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                raw = d.get("dataB64"); filename = str(d.get("filename") or "upload.png")
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene (and optional episode) required as plain tokens"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                import base64
                if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                blob = base64.b64decode(raw)
                ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ".png"
                if ext not in (".png", ".jpg", ".jpeg", ".webp"):
                    ext = ".png"
                incoming = MEDIA / "uploads_incoming"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{ep}_S{scene}_scenelook_incoming_{uuid.uuid4().hex[:8]}{ext}"
                out.write_bytes(blob)
                self._json(200, {"ok": True, "sourcePath": str(out)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path in ("/api/scenelook-working-save", "/api/scenelook-working-restore"):
            # THE SCENE LOOK WORKING PROMPT, WRITE SIDE (2026-07-19) — scene-scoped (not
            # shot-scoped, since Scene Look is one plate per scene), otherwise the exact same
            # contract as the shot-level save/restore block below: never calls cb_gen, saving
            # or restoring only changes which text the NEXT generate_scenelook_plate fire
            # would submit.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene (and optional episode) required as plain tokens"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                if self.path == "/api/scenelook-working-save":
                    rec = _CBR.save_scenelook_working(scene, str(d.get("prompt") or ""), ep)
                    self._json(200, {"ok": True, "saved": rec})
                else:
                    _CBR.restore_scenelook_working(scene, ep)
                    self._json(200, {"ok": True})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path in ("/api/shot-voice-save", "/api/shot-voice-restore",
                         "/api/shot-voice-restore-take",
                         "/api/shot-seedance-save", "/api/shot-seedance-restore",
                         "/api/shot-keyframe-save", "/api/shot-keyframe-restore"):
            # CONTAINED CREATIVE CONTROLS, WRITE SIDE (2026-07-19): direct, synchronous,
            # in-process calls — a quick, guaranteed-cheap mutation doesn't need the
            # job-runner's streaming-log machinery. NONE of these call cb_gen — saving,
            # restoring a working version, or swapping back to a superseded audio TAKE
            # (restore-voice-take, 2026-07-19 — "show the old one and the new one... get
            # rid of one or the other") never generates audio or animation; the latter only
            # moves already-generated files that voice_shot itself archived on regeneration.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                if self.path == "/api/shot-voice-save":
                    lines = d.get("lines") or []
                    rec = _CBR.save_voice_working(scene, sid, lines, ep)
                    self._json(200, {"ok": True, "saved": rec})
                elif self.path == "/api/shot-voice-restore":
                    _CBR.restore_voice_working(scene, sid, ep)
                    self._json(200, {"ok": True})
                elif self.path == "/api/shot-voice-restore-take":
                    _CBR.restore_previous_voice_take(scene, sid, ep)
                    self._json(200, {"ok": True})
                elif self.path == "/api/shot-seedance-save":
                    # dialogueInPromptConfirmed (2026-07-23, Julian's directed experiment): the
                    # ONE lawful, explicit, on-the-record Law-6 bypass — never a default; the
                    # engine banner-logs it and records the confirmer on the ledger
                    # (cb_render.save_seedance_working's own docstring has the full contract).
                    rec = _CBR.save_seedance_working(
                        scene, sid, str(d.get("prompt") or ""), ep,
                        reviewed_by=str(d.get("by") or "Julian"),
                        dialogueInPromptConfirmed=bool(d.get("dialogueInPromptConfirmed")))
                    self._json(200, {"ok": True, "saved": rec})
                elif self.path == "/api/shot-seedance-restore":
                    _CBR.restore_seedance_working(scene, sid, ep)
                    self._json(200, {"ok": True})
                elif self.path == "/api/shot-keyframe-save":
                    rec = _CBR.save_keyframe_working(scene, sid, str(d.get("prompt") or ""), ep)
                    self._json(200, {"ok": True, "saved": rec})
                else:
                    _CBR.restore_keyframe_working(scene, sid, ep)
                    self._json(200, {"ok": True})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-acknowledge-redesign":
            # THE BOUNDED REDESIGN-RECOVERY ACTION, WRITE SIDE (2026-07-20): a direct,
            # synchronous, in-process call — same precedent as the write-side block just
            # above (a cheap, guaranteed-fast mutation, no job-runner needed). Calls the
            # SAME protected backend function the CLI's own acknowledge-redesign subcommand
            # calls — there is no separate Studio-only shortcut. Makes zero provider calls;
            # cb_render.acknowledge_redesign itself refuses outright unless every
            # eligibility condition holds, so this route cannot bypass anything the backend
            # doesn't already enforce.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                event = _CBR.acknowledge_redesign(scene, sid, ep, reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "event": event})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-run":
            # THE SHOT PIPELINE, front door (additive, 2026-07-16; extended same day for the probabilistic-
            # candidate contract, then the single-use SPEND-TOKEN contract): validates cmd against the exact
            # allowlist, then clones the /api/fire pattern — same _jid/_start job runner, same
            # {"ok": True, "jobId": ...} response shape. cb_render.py's own refusals (the SPEND DISCLOSURE +
            # token issue on a no-token fire/next, a stale/consumed token, red validation, relay-before-
            # approval, model-limited, an UNCONFIRMED billing_profile.json — which hard-blocks ALL paid
            # generation by design until Julian confirms his plans — and Law 5/6) all surface through the
            # job log as a failed job; for the no-token disclosure step and the billing-profile block that
            # refusal is EXPECTED protective behaviour, not a malfunction.
            try:
                d = self._body()
                cmd = str(d.get("cmd", "")).strip()
                if cmd not in SHOT_CMDS:
                    self._json(400, {"error": "unknown cmd %r — allowed: %s" % (cmd, ", ".join(SHOT_CMDS))}); return
                scene = str(d.get("scene", "")).strip()
                episode = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                shot_id = str(d.get("shotId")).strip() if d.get("shotId") not in (None, "") else None
                correction = str(d.get("correction")).strip() if d.get("correction") not in (None, "") else None
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(episode):
                    self._json(400, {"error": "scene and episode must be plain tokens (e.g. 1, Ep1)"}); return
                if cmd in ("fire", "keyframe", "approve", "reject", "approve-keyframe", "reject-keyframe",
                           "select-upload", "select-library", "select-previous",
                           "approve-voice", "reject-voice", "regen-voice", "advance") \
                   and (not shot_id or not _SHOT_TOKEN.match(shot_id)):
                    self._json(400, {"error": f"{cmd} needs a shotId (e.g. 1.B1.S1)"}); return
                if cmd == "reject" and not correction:
                    self._json(400, {"error": "reject needs a one-sentence correction"}); return
                if cmd == "reject-keyframe" and not correction:
                    self._json(400, {"error": "reject-keyframe needs a plain-language reason"}); return
                if cmd == "reject-scenelook" and not correction:
                    self._json(400, {"error": "reject-scenelook needs a plain-language note"}); return
                if cmd == "reject-voice" and not correction:
                    self._json(400, {"error": "reject-voice needs a plain-language reason"}); return
                # THE NON-GENERATION OPENING-FRAME SOURCES (2026-07-18): 'select-upload' needs a
                # server-side path from a prior /api/shot-keyframe-upload call; 'select-library'
                # needs an item's path from /api/shot-keyframe-library — both validated as real,
                # existing files ROOTED under the approved engine/media tree (never an arbitrary
                # client-supplied path — the same containment discipline _url_from_abs enforces
                # in the other direction).
                source_path = d.get("sourcePath")
                if cmd in ("select-upload", "select-library"):
                    if not source_path or not isinstance(source_path, str):
                        self._json(400, {"error": f"{cmd} needs a sourcePath"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        if not sp.exists() or not sp.is_relative_to(MEDIA.resolve()):
                            self._json(400, {"error": "sourcePath must be an existing file under engine/media"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif cmd in ("select-scenelook-upload", "select-scenelook-library"):
                    # THE NON-GENERATION SCENE LOOK SOURCES (2026-07-19 — "still not letting me
                    # upload a library image, i select it then it wants to generate"): the
                    # scene-scoped mirror of select-upload/select-library above — no shotId,
                    # and the reusable-library root (cb-seed/assets) is allowed alongside
                    # engine/media, same as the scenelook cmd's own optional reference below.
                    if not source_path or not isinstance(source_path, str):
                        self._json(400, {"error": f"{cmd} needs a sourcePath"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        _roots = (MEDIA.resolve(), (ROOT / "cb-seed" / "assets").resolve())
                        if not sp.exists() or not any(sp.is_relative_to(r) for r in _roots):
                            self._json(400, {"error": "sourcePath must be an existing file under "
                                                       "engine/media or cb-seed/assets"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif cmd == "scenelook" and source_path is not None:
                    # THE SCENE LOOK PROVIDER-ROUTING FIX (2026-07-19): OPTIONAL for this cmd — an
                    # explicitly selected location/style reference, never auto-picked from the Asset
                    # Library by this endpoint itself; omitting sourcePath entirely is the normal
                    # no-reference case. WIDENED (2026-07-19, correction — "the library has to come
                    # from the scenes houses etc"): a Scene Look reference legitimately comes from
                    # the REAL reusable library (cb-seed/assets/locations/_manifest.json entries,
                    # character house imagery, uploaded scene refs — the same sources the Scenes/
                    # Houses nav pages and /api/loclib + /api/houses already serve), not only a
                    # scene's own generation history under engine/media. Both roots are already
                    # part of the trusted static-serve allowlist (see the static-file guard below);
                    # select-upload/select-library above stay scoped to MEDIA only, since those
                    # remain the shot-owned candidate-copy mechanism, unrelated to this reference.
                    if not isinstance(source_path, str):
                        self._json(400, {"error": "sourcePath must be a string"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        _roots = (MEDIA.resolve(), (ROOT / "cb-seed" / "assets").resolve())
                        if not sp.exists() or not any(sp.is_relative_to(r) for r in _roots):
                            self._json(400, {"error": "sourcePath must be an existing file under "
                                                       "engine/media or cb-seed/assets"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif source_path is not None:
                    self._json(400, {"error": "sourcePath applies to select-upload/select-library/"
                                               "select-scenelook-upload/select-scenelook-library/"
                                               "scenelook only"}); return
                # THE PROBABILISTIC-CANDIDATE + SPEND-TOKEN CONTRACT (2026-07-16): candidates and the
                # single-use spendToken for fire/next, category for reject, candidate index for approve —
                # each validated, each optional.
                candidates = d.get("candidates")
                if candidates is not None:
                    if cmd not in ("fire", "next"):
                        self._json(400, {"error": "candidates applies to fire/next only"}); return
                    try:
                        candidates = int(candidates)
                    except (TypeError, ValueError):
                        candidates = -1
                    if not (1 <= candidates <= 4):
                        self._json(400, {"error": "candidates must be an integer 1-4"}); return
                spend_token = str(d.get("spendToken")).strip() if d.get("spendToken") not in (None, "") else None
                if spend_token is not None:
                    # "keyframe" added 2026-07-22 alongside its own new disclose-then-confirm
                    # seal (cb_render.keyframe_shot) — matching fire/next's existing contract.
                    if cmd not in ("fire", "next", "keyframe"):
                        self._json(400, {"error": "spendToken applies to fire/next/keyframe only"}); return
                    if not _SPEND_TOKEN_RE.match(spend_token):
                        self._json(400, {"error": "spendToken must be 16-64 lowercase hex characters"}); return
                category = str(d.get("category")).strip() if d.get("category") not in (None, "") else None
                if category is not None:
                    if cmd != "reject":
                        self._json(400, {"error": "category applies to reject only"}); return
                    if category not in REJECT_CATEGORIES:
                        self._json(400, {"error": "category must be one of: " + ", ".join(REJECT_CATEGORIES)}); return
                candidate = d.get("candidate")
                if candidate is not None:
                    if cmd != "approve":
                        self._json(400, {"error": "candidate applies to approve only"}); return
                    try:
                        candidate = int(candidate)
                    except (TypeError, ValueError):
                        candidate = -1
                    if not (1 <= candidate <= 4):
                        self._json(400, {"error": "candidate must be an integer 1-4"}); return
                # THE RESOLUTION CHOICE (2026-07-23): "720p" (final) or "480p" (cheap test
                # tier) — fire/next only; anything else is refused here, before any job spawns.
                resolution = str(d.get("resolution")).strip() if d.get("resolution") not in (None, "") else None
                if resolution is not None:
                    if cmd not in ("fire", "next"):
                        self._json(400, {"error": "resolution applies to fire/next only"}); return
                    if resolution not in ("720p", "480p"):
                        self._json(400, {"error": "resolution must be 720p or 480p"}); return
                self._json(200, {"ok": True, "jobId": shot_run_job(cmd, scene, episode, shot_id, correction,
                                                                    candidates=candidates,
                                                                    spend_token=spend_token,
                                                                    category=category, candidate=candidate,
                                                                    dry_run=bool(d.get("dryRun")),
                                                                    source_path=source_path,
                                                                    resolution=resolution)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass

os.chdir(ROOT)
PORT = 8765
reindex_media(); eps = reindex_episodes()
http.server.ThreadingHTTPServer.allow_reuse_address = True
threading.Thread(target=_freshness_watch, daemon=True).start()   # self-heal: reload on any source change when idle
# THREADED: each request in its own (daemon) thread, so concurrent clip loads don't serialise behind one another.
with http.server.ThreadingHTTPServer(("", PORT), H) as httpd:
    print(f"Crystal Bears Studio  →  http://localhost:{PORT}/cb-studio/app.html")
    print(f"Serving {ROOT}  ({len(eps)} episodes)  — threaded + byte-range; freshness guard ON (fp={_STARTED_FP:.0f})")
    httpd.serve_forever()
