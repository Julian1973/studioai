#!/usr/bin/env python3
"""Crystal Bears Studio — local server. Episodes + shared Show Bible + script storage."""
import os, re, json, http.server, pathlib, subprocess, threading, time, zipfile, signal, sys, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent   # Desktop/8Th Hour
CBGEN = ROOT / "engine"
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
    # ONLY this server's own source. engine modules are reloaded fresh by each per-render SUBPROCESS, so they never
    # need a serve.py reload — watching them would needlessly re-exec and DROP the UI's open connections on every
    # engine edit ("can't reach server"). serve.py is the only long-lived code, so it's the only thing to watch.
    try: return os.path.getmtime(os.path.abspath(__file__))
    except OSError: return 0.0
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
    all (approve_gate/unapprove_gate/set_master_studio/clear_master_studio's blocking subprocess.run calls, every
    read-only preview endpoint, _serve_static's own chunked video/range streaming loop). os.execv() replaces the
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
# subprocess.run in approve_gate/set_master_studio, a preview-endpoint subprocess, _serve_static's chunked
# streaming loop) — so the idle-reload guard could fire mid-request. _INFLIGHT counts every live HTTP request
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

def _pkg_name(episode="Ep1"):
    """The current episode's beat-package FILENAME (basename only) — the default `package` for beat previews.
    Resolved by glob so any episode title works (mirrors cb_pipeline._resolve_pkg, but returns the bare name).
    FIXED 2026-07-12 (full-codebase audit continued): this pre-sorted candidates by filename before taking
    max-mtime, while cb_pipeline._resolve_pkg() takes max-mtime over an UNSORTED glob() result — on a genuine
    mtime tie, Python's max() keeps the FIRST candidate in iteration order, so the two resolvers could pick
    different files (the exact "display != fire" class of bug this project already hit once). Dropped the
    pre-sort so both use the same glob-order tie-break; masked in practice by the enforced
    one-package-per-episode convention, but no longer a silent divergence risk if that's ever broken."""
    cands = list(OUT.glob(f"{episode}_*beat_package.json")) or list(OUT.glob(f"{episode}_*shot_package.json"))
    return (max(cands, key=lambda p: p.stat().st_mtime).name if cands
            else f"{episode}_The_Adventure_Begins_beat_package.json")
PKG_NAME = _pkg_name()

# ── GATE-1 CASCADE-RELOCK (bug fix, 2026-07-02, Julian) — ⚠ DUPLICATED from engine/cb_pipeline.py's
#    _scene_beats_fingerprint/_relock_if_stale (a separate process, no engine import here — same convention as
#    the already-duplicated GATE_SEQ above). See cb_pipeline.py for the full rationale. Every read of locked_state()
#    (the studio's ONLY path to gate-status data) re-checks every episode/scene it finds and cascade-clears a
#    scene's "1"/"2a"/"2b"/"3"/"4"/"5" + per-beat locks the moment its Gate-1 deliverable no longer matches the
#    fingerprint recorded when Gate 1 was approved, AND (via _relock_chain_stale_scenes below) cascade-clears
#    any downstream per-beat keyframe/clip lock whose upstream chain source has since been retaken — so the
#    Pipeline page can never show a stale "signed off" again, for either mechanism.
def _beat_sort_key(code):
    """Natural sort on the trailing beat number ('3.B10' -> 10, never a lexicographic '3.B10' < '3.B9' bug) —
    mirrors cb_preflight._beat_sort_key (a separate process, no engine import here — same convention as
    GATE_SEQ/_scene_beats_fingerprint above). ADDED 2026-07-12 (full-codebase audit continued): this file's
    own beat-code sort was still the plain lexicographic form after cb_pipeline.py's identical mirror was
    already corrected (2026-07-11) — the two had silently diverged. Used everywhere this file orders beats."""
    m = re.search(r"[Bb](\d+)\s*$", str(code or ""))
    return int(m.group(1)) if m else 0

def _scene_beats_fingerprint(episode, scene):
    # NOTE: this function must stay FULLY SELF-CONTAINED (its own local `import re`, its own nested sort-key
    # helper, never a reference to a module-level name like _beat_sort_key above) — engine/test_gate_cascade.py's
    # test_serve_py pulls this exact function's source out via ast and execs it in a minimal namespace
    # ({json, pathlib, hashlib, GATE_SEQ} only), so any dependency on another module-level name here raises a
    # bare NameError the moment the test calls it directly. Confirmed live 2026-07-12 (full-codebase audit
    # continued) when the natural-sort fix below was first written to call the shared _beat_sort_key — the test
    # crashed immediately; this local, duplicated form is the fix.
    import hashlib, re as _re
    def _bkey(code):
        m = _re.search(r"[Bb](\d+)\s*$", str(code or ""))
        return int(m.group(1)) if m else 0
    # FIXED 2026-07-12 (full-codebase audit continued): dropped the filename pre-sort (see _pkg_name's own
    # note above) so this resolves the SAME candidate cb_pipeline._resolve_pkg() would on a genuine mtime tie.
    cands = list(OUT.glob(f"{episode}_*beat_package.json")) or list(OUT.glob(f"{episode}_*shot_package.json"))
    if not cands:
        return None
    pkg = max(cands, key=lambda p: p.stat().st_mtime)
    d = json.loads(pkg.read_text())
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    # FIXED 2026-07-12 (full-codebase audit continued): a plain lexicographic sort misorders any scene with
    # 10+ beats ("1.B10" sorts before "1.B2") — cb_pipeline.py's own copy of this exact function was already
    # corrected to natural-sort (2026-07-11); this one hadn't been, so the two independently-computed hashes
    # could diverge the moment a scene reaches 10+ beats (harmless today — no live scene is that large yet —
    # but sd["1_fp"] is WRITTEN by cb_pipeline.approve() using its own fingerprint function and compared HERE
    # against this one, so the two must keep producing byte-identical hashes for identical input).
    beats.sort(key=lambda b: _bkey(b.get("beatCode") or b.get("shotCode") or ""))
    blob = json.dumps(beats, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

def _relock_stale_scenes(d):
    """Mutates `d` (the parsed locked.json) in place, cascade-clearing any scene whose Gate-1 fingerprint has
    drifted. Returns True if anything changed (caller persists it back to disk)."""
    changed = False
    for episode, escenes in list(d.items()):
        if not isinstance(escenes, dict):
            continue
        for scene, sd in list(escenes.items()):
            if not isinstance(sd, dict) or not sd.get("1") or not sd.get("1_fp"):
                continue
            try:
                current = _scene_beats_fingerprint(episode, scene)
            except Exception:
                continue
            if current is None or current == sd["1_fp"]:
                continue
            print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — Gate 1 deliverable changed since sign-off "
                  f"(fingerprint {current} != approved {sd['1_fp']}); every downstream gate + per-beat lock reset.", flush=True)
            for g in list(GATE_SEQ) + ["2", "1_fp"]:
                sd.pop(g, None)
            sd["beats"] = {}
            changed = True
    return changed

# ── FRAME CHAIN cascade mirror (doctrine, 2026-07-02/03, Julian) — ADDED 2026-07-12 (full-codebase audit
#    continued, HIGH severity): locked_state() cascade-cleared a scene's Gate-1 fingerprint drift (above) but
#    never mirrored cb_pipeline.py's SEPARATE frame-chain cascade (_beat_end_frame_hash/_relock_chain_if_dirty)
#    — a retaken upstream clip (a new harvested settle frame) left every downstream beat's per-beat
#    "keyframe"/"clip" lock showing a stale "✓ signed off" (app.html's beatStageLocked/renderRelayPanel read
#    these flags straight off locked_state()'s payload) until some UNRELATED gate action for that scene
#    happened to call cb_pipeline's own _approved() and re-trigger the real cascade. Mirrors the LOGIC (not
#    the import) of cb_pipeline._beat_end_frame_hash/_relock_chain_if_dirty — same convention as every other
#    duplicate above.
def _beat_end_frame_hash(episode, code, bslug):
    """Content hash of a beat's HARVESTED SETTLE FRAME. None if it doesn't exist yet (the upstream beat hasn't
    rendered a clip) — mirrors cb_pipeline._beat_end_frame_hash exactly."""
    import hashlib
    p = MEDIA / f"{episode}_{code}_{bslug}_settle.png"
    if not p.exists():
        return None
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return None

def _relock_chain_stale_scenes(d):
    """Mutates `d` in place, same pattern as _relock_stale_scenes above: for every scene with recorded
    per-beat locks, walks its beats in order and clears "keyframe"/"clip" on the first one (and every one
    after it) whose recorded chain_source_fp no longer matches its upstream beat's CURRENT ending-frame hash
    — their own chain sources are now suspect too, exactly like cb_pipeline._relock_chain_if_dirty. Returns
    True if anything changed."""
    changed = False
    for episode, escenes in list(d.items()):
        if not isinstance(escenes, dict):
            continue
        for scene, sd in list(escenes.items()):
            if not isinstance(sd, dict):
                continue
            beats_locks = sd.get("beats") or {}
            if not beats_locks:
                continue
            try:
                cands = (list(OUT.glob(f"{episode}_*beat_package.json"))
                          or list(OUT.glob(f"{episode}_*shot_package.json")))
                if not cands:
                    continue
                pkg = json.loads(max(cands, key=lambda p: p.stat().st_mtime).read_text())
            except Exception:
                continue
            scene_beats = [b for b in (pkg.get("beats") or pkg.get("shots") or [])
                           if str(b.get("sceneNumber")) == str(scene)]
            scene_beats.sort(key=lambda b: _beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
            dirty_from = None
            for i, b in enumerate(scene_beats):
                if i == 0:
                    continue   # the scene anchor chains off the PLATE, not a previous beat's ending frame
                code = str(b.get("beatCode") or b.get("shotCode"))
                bl = beats_locks.get(code)
                if not bl or not bl.get("keyframe") or not bl.get("chain_source_fp"):
                    continue
                prev = scene_beats[i - 1]
                prev_code = prev.get("beatCode") or prev.get("shotCode")
                prev_slug = prev.get("slug", str(prev_code).replace(".", "_"))
                current_fp = _beat_end_frame_hash(episode, prev_code, prev_slug)
                if current_fp and current_fp != bl["chain_source_fp"]:
                    dirty_from = i
                    break
            if dirty_from is None:
                continue
            scene_changed = False
            for b in scene_beats[dirty_from:]:
                code = str(b.get("beatCode") or b.get("shotCode"))
                bl = beats_locks.get(code)
                if bl and (bl.get("keyframe") or bl.get("clip")):
                    bl["keyframe"] = False; bl["clip"] = False
                    scene_changed = True
            if scene_changed:
                print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — an upstream ending frame changed (a retake); "
                      f"{len(scene_beats) - dirty_from} downstream beat(s) marked needing keyframe review.", flush=True)
                changed = True
    return changed

def locked_state():
    f = CBGEN / "locked.json"
    try:
        d = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}
    try:
        # FIXED 2026-07-12 (full-codebase audit continued): only _relock_stale_scenes ran here — see
        # _relock_chain_stale_scenes's own comment above for why that left the frame-chain cascade unmirrored.
        changed = _relock_stale_scenes(d)
        if _relock_chain_stale_scenes(d):
            changed = True
        if changed:
            f.write_text(json.dumps(d, indent=1))
    except Exception:
        pass   # fail-open: a relock error must never brick gate-status reads
    return d

def notes_state():
    f = CBGEN / "notes.json"
    try: return json.loads(f.read_text()) if f.exists() else {}
    except Exception: return {}

def relay_state_all():
    """The FULL relay_state.json, straight off disk — {"Ep1": {"1": {winnerCode, nextCode, harvested, remint,
    anchor, driftCheck, ...}}}. Exposed on /api/pipeline (the payload every page already fetches) so Gate 3's
    own panel can render a pending anchor SYNCHRONOUSLY (no extra round-trip, no per-beat modal needed to
    discover it exists). RE-MINT SCOPING (rule 32, 2026-07-05): "remint" and "driftCheck" are both null for an
    intentional_next_shot next beat (the default) — no NB2 pass ran. "anchor" is ALWAYS populated (the re-mint
    when one ran, the raw harvest otherwise); the UI reads "anchor", never assumes "remint" is the only shape."""
    f = CBGEN / "relay_state.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}

def visions_state():
    """{"Ep1": ["2.V1", ...], ...} — every declared vision shot code per episode, straight off continuity.json.
    Lets the Studio's relay-truth walk-back (app.html's keyframesFor) skip vision beats exactly like the
    engine's own cb_prompts.vision_for does server-side — a vision never chains and is never chained through."""
    f = CBGEN / "config" / "continuity.json"
    try:
        d = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}
    out = {}
    for ep, block in d.items():
        if isinstance(block, dict):
            out[ep] = [v.get("shot") for v in (block.get("visions") or []) if isinstance(v, dict) and v.get("shot")]
    return out

def continuity_state():
    try:
        p = subprocess.run(["python3", "cb_continuity.py", "--json"], cwd=str(CBGEN),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return json.loads(p.stdout or "[]")
    except Exception as e:
        return [{"level": "NOTE", "scene": "-", "shot": "-", "msg": f"continuity check error: {e}"}]

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

def fire_gate(scene, gate, force=False, episode="Ep1"):
    # Gate 1 is idempotent (a plain re-fire just re-displays the existing beats); a FORCE re-fire runs `redirect`,
    # which backs up + removes the package and re-authors the whole episode with the current (hardened) Director.
    # --episode=<ep> retargets cb_pipeline.py's EP/PKG globals for THIS invocation (see cb_pipeline.py __main__) —
    # without it every gate action silently ran against Ep1 regardless of which episode was actually selected.
    if str(gate) == "1" and force:
        return _start(_jid(f"g1s{scene}"), gate, scene,
                      ["cb_pipeline.py", "redirect", str(scene), f"--episode={episode}"])
    return _start(_jid(f"g{gate}s{scene}"), gate, scene,
                  ["cb_pipeline.py", str(gate), str(scene), f"--episode={episode}"])

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

def approve_gate(scene, gate, episode="Ep1", reviewed_by="Julian"):
    args = ["python3", "cb_pipeline.py", "approve", str(gate), str(scene), f"--episode={episode}"]
    if reviewed_by:
        args.append(f"--reviewed-by={reviewed_by}")
    p = subprocess.run(args, cwd=str(CBGEN), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return p.returncode == 0, (p.stdout + p.stderr).strip()

def unapprove_gate(scene, gate, episode="Ep1"):
    """Reverse a sign-off (un-sign a step) — clears the gate + everything downstream, and resets the scene master
    if the foundation is un-signed (cb_pipeline.unapprove)."""
    p = subprocess.run(["python3", "cb_pipeline.py", "unapprove", str(gate), str(scene), f"--episode={episode}"],
                       cwd=str(CBGEN), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return p.returncode == 0, (p.stdout + p.stderr).strip()

def set_master_studio(scene, beat_code, character, episode="Ep1", scope="location", force=False):
    """★ Set a CHARACTER MASTER from a beat's keyframe (synchronous; QA-gated inside cb_pipeline). Returns (ok, log)."""
    args = ["python3", "cb_pipeline.py", "set-master", str(scene), str(beat_code), str(character), str(episode), str(scope)]
    if force: args.append("force")
    p = subprocess.run(args, cwd=str(CBGEN), capture_output=True, text=True, timeout=150, stdin=subprocess.DEVNULL)
    out = (p.stdout + p.stderr).strip()
    return ("★ MASTER SET" in out), out

def clear_master_studio(scene, character, episode="Ep1"):
    """Retire a character's master for this scene's location (→ falls back to the Character Box). Returns (ok, log)."""
    p = subprocess.run(["python3", "cb_pipeline.py", "clear-master", str(scene), str(character), str(episode)],
                       cwd=str(CBGEN), capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
    out = (p.stdout + p.stderr).strip()
    return ("cleared" in out), out

# server-side gate guard (defense in depth — the HTTP boundary itself refuses to fire/regen past an unsigned step)
# ⚠ DUPLICATED (deliberately, not shared) from engine/cb_pipeline.py's own GATE_SEQ — a separate process. If a gate
# is ever added/renamed/reordered, update BOTH lists in the SAME change, or this HTTP-layer guard and cb_pipeline's
# process-layer guard could silently disagree on what "the previous gate" is.
GATE_SEQ = ["1", "1.6", "2a", "2b", "3", "4", "5"]   # 1.6 = THE PREVIZ REEL (2026-07-08) · …3 Animation ·
# 4 Retakes · 5 Post. Named "1.6" (not "1.5") to avoid colliding with the already-established "Gate 1.5" —
# Director's Eye (cb_director_eye.py), an unrelated automatic flag-only review with no lock state of its
# own, never a member of this list. See engine/cb_previz.py's module docstring for the full note.
def _scene_locks(scene, episode="Ep1"):
    return locked_state().get(episode or "Ep1", {}).get(str(scene), {})
def _gate_ready(scene, gate, episode="Ep1"):
    """(ok, msg) — is this gate fireable? Its previous gate must be signed off."""
    g = str(gate).lower()
    if g not in GATE_SEQ or GATE_SEQ.index(g) == 0:
        return True, ""
    prev = GATE_SEQ[GATE_SEQ.index(g) - 1]
    if _scene_locks(scene, episode).get(prev):
        return True, ""
    return False, f"Gate {prev} not signed off for scene {scene} — sign it off first."

def regen_shot(scene, shot_code, kind, note, target="both", episode="Ep1"):
    return _start(_jid(f"regen_{kind}_{shot_code}"), f"regen:{shot_code}", scene,
                  ["cb_pipeline.py", "regen", str(scene), str(shot_code), kind, note or "", target, f"--episode={episode}"])

# ---- TICKET 4: per-beat Linear Gated Cascade drivers (mirror the gate drivers above) ----
def gen_audio_beat(scene, beat, episode="Ep1"):
    """Generate the dialogue track for ONE beat (job; cb_pipeline gen-audio prints AUDIO_DUR + the track path)."""
    return _start(_jid(f"audio_{beat}"), f"audio:{beat}", scene,
                  ["cb_pipeline.py", "gen-audio", str(scene), str(beat), f"--episode={episode}"])

def gen_keyframe_beat(scene, beat, chain_from=None, episode="Ep1"):
    """Build ONE beat's opening keyframe (job; optionally chained off the previous beat's last frame)."""
    args = ["cb_pipeline.py", "build-beat", str(scene), str(beat)]
    if chain_from:
        args.append(str(chain_from))
    args.append(f"--episode={episode}")
    return _start(_jid(f"kf_{beat}"), f"keyframe:{beat}", scene, args)

def render_beat_clip(scene, beat, episode="Ep1"):
    """Render ONE beat's 10-12s Seedance take (job; cb_pipeline render-beat -> cb_beats.run for that beat)."""
    return _start(_jid(f"render_{beat}"), f"render:{beat}", scene,
                  ["cb_pipeline.py", "render-beat", str(scene), str(beat), f"--episode={episode}"])

def approve_beat(scene, beat, stage, episode="Ep1", value=True):
    """Lock (value=True) or UNLOCK (value=False) ONE beat's stage (audio|keyframe|clip) synchronously (mirror approve_gate).
    Returns (ok, log, next). For a keyframe approval, cb_pipeline prints 'NEXT=<code>'/'NEXT=NONE' — parsed for the chain auto-fire."""
    p = subprocess.run(["python3", "cb_pipeline.py", "approve-beat", str(scene), str(beat), str(stage),
                        ("true" if value else "false"), f"--episode={episode}"],
                       cwd=str(CBGEN), capture_output=True, text=True, stdin=subprocess.DEVNULL)
    out = (p.stdout + p.stderr).strip()
    nxt = None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("NEXT="):
            val = line[len("NEXT="):].strip()
            nxt = None if val.upper() == "NONE" or not val else val
    return p.returncode == 0, out, nxt

def rebuild_keyframes(scene, episode="Ep1"):
    """CLEAN rebuild of ALL keyframes for a scene — deletes stale frames + re-renders every beat fresh.
    Tagged gate '2b' so the studio shows it LIVE as a keyframe build (progress bar + storyboard populating)."""
    return _start(_jid(f"rebuild_kf_{scene}"), "2b", scene,
                  ["cb_pipeline.py", "rebuild", str(scene), f"--episode={episode}"])

# ── THE RELAY, front door (Julian, 2026-07-03) — job-launch wrappers around cb_pipeline.relay_prepare/
#    relay_approve. relay_approve_beat is the ONLY function in this file that may fire fire_next_beat's
#    approved=True launch — the Approve Anchor button in app.html is the only caller of it.
#    THE ONE-RENDER ECONOMY (Julian, 2026-07-05): both phases dropped their seed/seed-path parameters — a beat
#    has exactly one official clip now (auto-retried once internally on a failed gate), so there is no seed to
#    designate and no "how many candidates" choice left to make.
def relay_prepare_beat(scene, winner_code, episode="Ep1", fast=False):
    """PHASE 1: harvest the winner's own official clip, re-mint (seamless joins only), drift-check, STOP for
    approval (job). fast=False default: standard tier is the production default under the one-render economy."""
    return _start(_jid(f"relayprep_{winner_code}"), f"relay-prepare:{winner_code}", scene,
                  ["cb_pipeline.py", "relay-prepare", str(scene), str(winner_code),
                   f"--episode={episode}", f"--fast={str(bool(fast)).lower()}"])

def relay_approve_beat(scene, winner_code, episode="Ep1", fast=False):
    """PHASE 2: launch the next beat off the anchor an earlier relay_prepare_beat already produced (job) — one
    take, one automatic re-fire on a failed gate, then a hard stop naming the layer at fault.
    fast=False default: standard tier is the production default under the one-render economy."""
    return _start(_jid(f"relayapprove_{winner_code}"), f"relay-approve:{winner_code}", scene,
                  ["cb_pipeline.py", "relay-approve", str(scene), str(winner_code),
                   f"--episode={episode}", f"--fast={str(bool(fast)).lower()}"])

# ── THE SHOT PIPELINE (cb_engine.py design → cb_render.py render loop) — ADDITIVE, 2026-07-16 ──────────────────────
# A separate, parallel surface for the shot-sized production packages (cb-output/{ep}_scene{N}_production_
# package.json). Nothing here touches GATE_SEQ, the beat pipeline, or any existing route — the two endpoints
# (/api/shot-package GET, /api/shot-run POST) plus these helpers are the whole footprint. Jobs run through the
# SAME _jid/_start/_stream runner every existing gate action uses (fresh subprocess, argv list, never a shell).
SHOT_CMDS = ("design", "voice", "animatic", "keyframe", "fire", "next", "approve", "reject", "stitch")
# "animatic" stays the CLI verb (cb_render.py keeps it as an accepted alias) — but the ARTIFACT it builds is
# the TIMING SLATE (Julian's 2026-07-16 reclassification: Seedance is a probabilistic candidate generator;
# this artifact approves dialogue accuracy / voice assignment / durations / line position ONLY, never
# staging, physical comedy or final rhythm).
REJECT_CATEGORIES = ("identity", "geography", "action-timing", "instruction-ignored", "other")
_SPEND_TOKEN_RE = re.compile(r"^[a-f0-9]{16,64}$")   # the SERVER-ISSUED single-use spend token (2026-07-16
# spend-protection contract): fire/next without one stores pendingSpendAuth on the shot's ledger and REFUSES;
# with one, the engine re-validates the binding hash (prompt/keyframe/refs/audio/duration/settings/rate/count)
# and refuses if ANYTHING drifted. Lowercase hex only — never a path, never shell-meaningful.
_SHOT_TOKEN = re.compile(r"^[A-Za-z0-9._-]+$")   # scene / episode / shotId — plain tokens, never a path

def _shot_pkg_path(scene, episode="Ep1"):
    """Mirrors engine/cb_render.py's _pkg_path (a separate process, no engine import here — the same
    deliberate-duplication convention as GATE_SEQ/_scene_beats_fingerprint above)."""
    return OUT / f"{episode}_scene{scene}_production_package.json"

def shot_media_map(pkg, scene, episode="Ep1"):
    """Server-computed existence map of every shot's media (vo / keyframe / clip / harvested final frame)
    plus the scene-level animatic + stitched picture. Filenames mirror cb_render.py's own writers; the URLs
    are /engine/media/... paths the existing static route already serves (shots/ is a subfolder of the
    approved /engine/media/ root — prefix + extension both pass _static_blocked with zero policy change)."""
    shots_dir = MEDIA / "shots"
    def _url(p):
        return ("/engine/media/" + p.relative_to(MEDIA).as_posix()) if p.exists() else None
    shots = {}
    for s in pkg.get("shots") or []:
        sid = s.get("shotId")
        if not sid:
            continue
        shots[sid] = {"vo":         _url(shots_dir / f"{episode}_{sid}_vo.mp3"),
                      "keyframe":   _url(shots_dir / f"{episode}_{sid}_keyframe.png"),
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
            "picture": _url(MEDIA / f"{episode}_Scene{scene}_shots_picture.mp4")}

def shot_run_job(cmd, scene, episode="Ep1", shot_id=None, correction=None,
                 candidates=None, spend_token=None, category=None, candidate=None):
    """Map one validated shot-pipeline command onto the job runner. Argument order per cb_engine.py /
    cb_render.py's own CLIs (2026-07-16 spend-token contract — the approve-spend boolean is GONE):
      design  -> cb_engine.py <scene> [episode]
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
    if cmd == "design":
        return _start(_jid(f"shotdesign_s{scene}"), "shot:design", scene,
                      ["cb_engine.py", str(scene), str(episode)])
    args = ["cb_render.py", cmd, str(scene)]
    if cmd in ("fire", "keyframe", "approve", "reject"):
        args.append(str(shot_id))
    if cmd == "approve" and candidate is not None:
        args.append(str(candidate))
    if cmd == "reject":
        args.append(str(correction))
        if category:
            args += ["--category", str(category)]
    args.append(str(episode))
    if cmd in ("fire", "next"):
        if candidates is not None:
            args += ["--candidates", str(candidates)]
        if spend_token:
            args += ["--spend-token", str(spend_token)]
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
        if self.path == "/" or self.path == "":
            self.send_response(302)
            self.send_header("Location", "/cb-studio/app.html")
            self.end_headers()
            return
        if self.path == "/api/pipeline":
            # pkgMtime (2026-07-15, THE STALE-JOB-LOG ATTRIBUTION BUG): a Gate-3 job log from a PREVIOUS
            # package (found live — a stopped job from the day before the whole-episode restart) was being
            # parsed for per-beat lint flags and attributed to the freshly re-authored beats, purely because
            # the beat codes matched. The client compares each job's own `ended` timestamp against this
            # mtime and suppresses lint attribution from any job older than the current package.
            try:
                _pkg_mtime = (OUT / _pkg_name()).stat().st_mtime
            except Exception:
                _pkg_mtime = 0
            return self._json(200, {"locked": locked_state(), "jobs": JOBS, "notes": notes_state(),
                                    "visions": visions_state(), "relay": relay_state_all(),
                                    "pkgMtime": _pkg_mtime})
        if self.path == "/api/health":
            return self._json(200, {"stale": _is_stale(), "started": _STARTED_FP,
                                    "current": _source_fingerprint(), "running": len(PROCS)})
        if self.path == "/api/continuity":
            return self._json(200, {"findings": continuity_state()})
        if self.path == "/api/masters":
            # READ-ONLY, informational: the whole character-master library (cb_prompts.masters_index — "for
            # the studio to display + audit", its own stated intent). Never feeds a render prompt.
            import sys as _sys
            try:
                r = subprocess.run([_sys.executable, "masters_preview.py"], cwd=str(ROOT / "engine"),
                                   capture_output=True, text=True, timeout=40, stdin=subprocess.DEVNULL)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"error": (r.stderr or "no output")[:400]}
                return self._json(200, obj)
            except Exception as e:
                return self._json(400, {"error": str(e)})
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
        if self.path.startswith("/api/keyframe-prompt"):
            import sys as _sys
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            pkg = (q.get("package") or [""])[0]; beat = (q.get("beat") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not pkg or not beat or "/" in pkg or ".." in pkg:
                return self._json(400, {"error": "package and beat required"})
            try:
                r = subprocess.run([_sys.executable, "kf_preview.py", pkg, beat, ep],
                                   cwd=str(ROOT / "engine"), capture_output=True, text=True, timeout=40,
                                   stdin=subprocess.DEVNULL)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"error": (r.stderr or "no output")[:400]}
                return self._json(200, obj)
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/voice-prompt"):
            import sys as _sys
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            pkg = (q.get("package") or [""])[0]; beat = (q.get("beat") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not pkg or not beat or "/" in pkg or ".." in pkg:
                return self._json(400, {"error": "package and beat required"})
            try:
                r = subprocess.run([_sys.executable, "voice_preview.py", pkg, beat, ep],
                                   cwd=str(ROOT / "engine"), capture_output=True, text=True, timeout=40,
                                   stdin=subprocess.DEVNULL)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"error": (r.stderr or "no output")[:400]}
                return self._json(200, obj)
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/beat-sound-brief"):
            # READ-ONLY, informational: cb_prompts._music_line/_sfx_line for one beat (a scratch music/SFX
            # BRIEF, mirroring cb_post.music_brief's own "advisory, never fed into the render prompt" pattern —
            # the v5 engine deliberately keeps per-beat music/SFX direction OUT of the shipped Seedance prompt,
            # see CLAUDE.md rule 42). Never writes anything, never touches a render.
            import sys as _sys
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            pkg = (q.get("package") or [""])[0]; beat = (q.get("beat") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not pkg or not beat or "/" in pkg or ".." in pkg:
                return self._json(400, {"error": "package and beat required"})
            try:
                r = subprocess.run([_sys.executable, "sound_brief_preview.py", pkg, beat, ep],
                                   cwd=str(ROOT / "engine"), capture_output=True, text=True, timeout=40,
                                   stdin=subprocess.DEVNULL)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"error": (r.stderr or "no output")[:400]}
                return self._json(200, obj)
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/relay-state"):
            # read-only: the prepared (unapproved) anchor for this scene, straight off relay_state.json — never
            # re-derives or re-calls NB2. Empty {} if nothing is waiting (no anchor prepared, or already launched).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            f = CBGEN / "relay_state.json"
            try:
                d = json.loads(f.read_text()) if f.exists() else {}
            except Exception:
                d = {}
            return self._json(200, d.get(ep, {}).get(scene) or {})
        if self.path.startswith("/api/keyframe-qa"):
            # READ-ONLY, zero-cost: reads the cached media/{ep}_{code}_{slug}.keyframe_qa.json sidecars
            # cb_qa.check_scene writes whenever Gate 2b actually runs the Definition-of-Done check (real
            # vision API calls — never recomputed here on a bare page load/poll, only read back). Built
            # 2026-07-14 (Julian: "we're doing this in the prompt, it needs to be done in the studio") —
            # this flag existed and ran correctly on the backend the whole time but was never surfaced
            # anywhere in the Studio UI Julian actually reviews from.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            out = {}
            if scene:
                for f in (CBGEN / "media").glob(f"{ep}_{scene}.B*.keyframe_qa.json"):
                    try:
                        row = json.loads(f.read_text())
                        code = row.get("shot")
                        if code:
                            out[code] = row
                    except Exception:
                        continue
            return self._json(200, out)
        if self.path.startswith("/api/craft-score"):
            # READ-ONLY, zero-cost: reads the cached media/{ep}_Scene{N}_previz.craft.json sidecar
            # cb_previz.craft_score_for_scene writes whenever Gate 1.6's previz reel actually fires (a real,
            # two-LLM-read cb_craft.score_scene_craft call — never recomputed here on a bare page load/poll,
            # only read back). Built 2026-07-14 (task #315, closing the "built but orphaned" gap this whole
            # session has repeatedly found: the craft judge existed and worked since rule 48 but had no live
            # caller and nowhere to surface in the Studio Julian actually reviews from). {} if the previz
            # hasn't been fired since this wiring landed, or if the LLM score itself failed (fail-soft by
            # design — the reel still exists and is still watchable either way).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            out = {}
            if scene:
                f = CBGEN / "media" / f"{ep}_Scene{scene}_previz.craft.json"
                if f.exists():
                    try:
                        out = json.loads(f.read_text())
                    except Exception:
                        out = {}
            return self._json(200, out)
        if self.path.startswith("/api/beat-prompt"):
            # TICKET 4 — the editable JSON the Cascade panel surfaces: kind=seedance (clip take) | keyframe (image).
            import sys as _sys
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; beat = (q.get("beat") or [""])[0]
            kind = (q.get("kind") or ["seedance"])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            pkg = (q.get("package") or [PKG_NAME])[0]
            if not scene or not beat or "/" in pkg or ".." in pkg:
                return self._json(400, {"error": "scene and beat required"})
            try:
                r = subprocess.run([_sys.executable, "beat_preview.py", pkg, scene, beat, ep, kind],
                                   cwd=str(ROOT / "engine"), capture_output=True, text=True, timeout=40,
                                   stdin=subprocess.DEVNULL)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"error": (r.stderr or "no output")[:400]}
                return self._json(200, obj)
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/beat-state"):
            # TICKET 4 — the per-beat lock dict for a scene (drives the stage rail + cascade timeline).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene:
                return self._json(400, {"error": "scene required"})
            beats = (_scene_locks(scene, ep) or {}).get("beats", {})
            return self._json(200, {"beats": beats})
        if self.path.startswith("/api/retake-log"):   # the before/after retake log for a scene (per-shot old-vs-new)
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene:
                return self._json(400, {"error": "scene required"})
            p = CBGEN / "media" / f"{ep}_Scene{scene}_retake_log.json"
            try:
                obj = json.loads(p.read_text()) if p.exists() else {"entries": []}
            except Exception:
                obj = {"entries": []}
            return self._json(200, obj)
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
                                                 f"({p.name}) — run Design scene (cb_engine.py) first"})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            return self._json(200, {"package": pkg, "media": shot_media_map(pkg, scene, ep), "file": p.name})
        if "/cb-studio/data/" in self.path:
            reindex_media(); reindex_episodes()
        return self._serve_static()       # range-aware (video streams + seeks), not the no-Range super().do_GET()

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    @_tracked
    def do_POST(self):
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
        if self.path == "/api/fire":
            try:
                d = self._body(); scene = str(d["scene"]); gate = str(d["gate"]); episode = d.get("episode", "Ep1")
                ready, msg = _gate_ready(scene, gate, episode)
                if not ready:
                    self._json(409, {"error": msg}); return
                self._json(200, {"ok": True, "jobId": fire_gate(scene, gate, bool(d.get("force")), episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/retakes":      # IN-APP retakes — save the {ref/timecode, change} run-list, then fire Gate 4
            try:                              # (firing a retake is NOT a sign-off — iterate as many times as you like)
                d = self._body(); scene = str(d["scene"]); episode = d.get("episode", "Ep1"); retakes = d.get("retakes") or []
                (CBGEN / "media").mkdir(parents=True, exist_ok=True)
                (CBGEN / "media" / f"{episode}_Scene{scene}_retakes.json").write_text(json.dumps(retakes, indent=2))
                ready, msg = _gate_ready(scene, "4", episode)   # Gate 4 = Retakes; needs only Gate 3 (Animation) signed
                if not ready:
                    self._json(409, {"error": msg}); return
                self._json(200, {"ok": True, "jobId": fire_gate(scene, "4", False, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/retake-brief":  # DIRECTOR CHECK — preview how the Director rewrites a plain note into retake wording (NO render)
            try:
                import sys as _sys
                d = self._body()
                payload = json.dumps({
                    "pkg": _pkg_name(d.get("episode", "Ep1")),
                    "scene": str(d.get("scene", "")),
                    "locator": (d.get("ref") or d.get("timecode") or d.get("locator") or "").strip(),
                    "issue": d.get("issue", ""), "change": d.get("change", ""),
                    "episode": d.get("episode", "Ep1"),
                })
                r = subprocess.run([_sys.executable, "retake_preview.py"], cwd=str(ROOT / "engine"),
                                   input=payload, capture_output=True, text=True, timeout=60)
                out = (r.stdout or "").strip()
                obj = json.loads(out.splitlines()[-1]) if out else {"ok": False, "error": (r.stderr or "no output")[:400]}
                self._json(200, obj)
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/retake-csv":   # AMENDED retake sheet uploaded — save it, drop the in-app run-list, run Gate 4 off the CSV
            try:
                d = self._body(); scene = str(d["scene"]); episode = d.get("episode", "Ep1"); csv = d.get("csv") or ""
                (CBGEN / "media").mkdir(parents=True, exist_ok=True)
                (CBGEN / "media" / f"{episode}_Scene{scene}_RETAKES.csv").write_text(csv, encoding="utf-8")
                try: (CBGEN / "media" / f"{episode}_Scene{scene}_retakes.json").unlink()   # CSV route → ignore any form run-list
                except FileNotFoundError: pass
                ready, msg = _gate_ready(scene, "4", episode)
                if not ready:
                    self._json(409, {"error": msg}); return
                self._json(200, {"ok": True, "jobId": fire_gate(scene, "4", False, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/stop":
            try:
                d = self._body(); jid = d.get("jobId")
                stopped = [jid] if (jid and stop_job(jid)) else ([] if jid else stop_all())
                self._json(200, {"ok": True, "stopped": stopped, "jobs": JOBS})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/export-storyboard":
            # THE GATE-1 EXTERNAL REVIEW RULE (CLAUDE.md rule 37) — a one-click render of
            # cb_pipeline.export_storyboard, matching this file's own fresh-subprocess convention (never a
            # direct Python import of cb_pipeline — every fire/approve/export shells out so the Studio
            # never runs stale engine code).
            try:
                d = self._body()
                episode = d.get("episode", "Ep1")
                args = ["python3", "cb_pipeline.py", "export"]
                if d.get("scene") is not None:
                    args.append(str(d["scene"]))
                args.append(f"--episode={episode}")
                p = subprocess.run(args, cwd=str(CBGEN), capture_output=True, text=True,
                                    stdin=subprocess.DEVNULL, timeout=30)
                if p.returncode != 0:
                    self._json(400, {"error": (p.stdout + p.stderr).strip()[:2000]}); return
                self._json(200, {"ok": True, "markdown": p.stdout})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/approve":
            try:
                d = self._body()
                ok, log = approve_gate(str(d["scene"]), str(d["gate"]), d.get("episode", "Ep1"),
                                        reviewed_by=str(d.get("reviewedBy") or "Julian"))
                self._json(200, {"ok": ok, "log": log, "locked": locked_state()})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/unapprove":
            try:
                d = self._body(); ok, log = unapprove_gate(str(d["scene"]), str(d["gate"]), d.get("episode", "Ep1"))
                self._json(200, {"ok": ok, "log": log, "locked": locked_state()})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/rebuild":
            try:
                d = self._body(); scene = str(d["scene"]); episode = d.get("episode", "Ep1")
                if not _scene_locks(scene, episode).get("2a"):
                    self._json(409, {"error": f"Gate 2a (foundation) not signed off for scene {scene} — sign it off before rebuilding keyframes."}); return
                self._json(200, {"ok": True, "jobId": rebuild_keyframes(scene, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/set-master":
            try:
                d = self._body()
                ok, log = set_master_studio(str(d["scene"]), str(d["beatCode"]), str(d["character"]),
                                            d.get("episode", "Ep1"), d.get("scope", "location"), bool(d.get("force")))
                self._json(200, {"ok": ok, "log": log})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/clear-master":
            try:
                d = self._body()
                ok, log = clear_master_studio(str(d["scene"]), str(d["character"]), d.get("episode", "Ep1"))
                self._json(200, {"ok": ok, "log": log})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/regen":
            try:
                d = self._body(); scene = str(d["scene"]); kind = d.get("kind", "keyframe"); episode = d.get("episode", "Ep1")
                need = "2b" if kind == "clip" else "2a"   # keyframe regen needs the foundation (2a); clip regen needs keyframes (2b)
                if not _scene_locks(scene, episode).get(need):
                    self._json(409, {"error": f"Gate {need} not signed off for scene {scene} — sign it off before regenerating."}); return
                jobId = regen_shot(scene, str(d["shotCode"]),
                                   kind, d.get("note", ""), d.get("target", "both"), episode)
                self._json(200, {"ok": True, "jobId": jobId})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/gen-audio":
            try:
                d = self._body(); scene = str(d["scene"]); beat = str(d["beat"]); episode = d.get("episode", "Ep1")
                if not _scene_locks(scene, episode).get("2a"):   # matches /api/rebuild's gate — per-beat cascade needs the foundation first
                    self._json(409, {"error": f"Gate 2a (foundation) not signed off for scene {scene} — sign it off before generating audio."}); return
                self._json(200, {"ok": True, "jobId": gen_audio_beat(scene, beat, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/gen-keyframe":
            try:
                d = self._body(); scene = str(d["scene"]); beat = str(d["beat"]); episode = d.get("episode", "Ep1")
                chain_from = d.get("chain_from") or None
                if not _scene_locks(scene, episode).get("2a"):   # matches /api/rebuild's gate — same underlying action, one beat at a time
                    self._json(409, {"error": f"Gate 2a (foundation) not signed off for scene {scene} — sign it off before building keyframes."}); return
                self._json(200, {"ok": True, "jobId": gen_keyframe_beat(scene, beat, chain_from, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/render-beat":
            try:
                d = self._body(); scene = str(d["scene"]); beat = str(d["beat"]); episode = d.get("episode", "Ep1")
                if not _scene_locks(scene, episode).get("2b"):   # matches /api/regen's kind=clip gate — clips need signed keyframes
                    self._json(409, {"error": f"Gate 2b (keyframes) not signed off for scene {scene} — sign it off before rendering clips."}); return
                self._json(200, {"ok": True, "jobId": render_beat_clip(scene, beat, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/approve-beat":
            try:
                d = self._body()
                scene = str(d["scene"]); beat = str(d["beat"]); stage = str(d["stage"]); episode = d.get("episode", "Ep1")
                ok, log, nxt = approve_beat(scene, beat, stage, episode, value=d.get("value", True))
                self._json(200, {"ok": ok, "log": log, "next": nxt})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/relay-prepare":
            # PHASE 1 (front door): "Prepare anchor" calls this. THE ONE-RENDER ECONOMY (2026-07-05) retired the
            # seed-pick step — there is exactly one official clip per beat now, so this harvests ITS settle
            # frame directly, re-mints it (seamless joins only), runs the drift check, then STOPS.
            try:
                d = self._body()
                scene = str(d["scene"]); code = str(d["code"])
                episode = d.get("episode", "Ep1"); fast = bool(d.get("fast", False))
                self._json(200, {"ok": True, "jobId": relay_prepare_beat(scene, code, episode, fast=fast)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/relay-approve":
            # PHASE 2 (front door): the Approve Anchor button — the ONLY caller of this route, which is the
            # ONLY thing allowed to launch the next beat (fire_next_beat approved=True) — one take, one
            # automatic re-fire on a failed gate, then a hard stop naming the layer at fault.
            try:
                d = self._body()
                scene = str(d["scene"]); code = str(d["code"])
                episode = d.get("episode", "Ep1"); fast = bool(d.get("fast", False))
                self._json(200, {"ok": True, "jobId": relay_approve_beat(scene, code, episode, fast=fast)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/director-eye":
            try:
                d = self._body(); episode = d.get("episode", "Ep1")   # episode-level review; the package is resolved engine-side
                jid = _start(_jid("directoreye"), "1.5", "1",
                             ["cb_pipeline.py", "director-eye", f"--episode={episode}"])
                self._json(200, {"ok": True, "jobId": jid})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/masters":
            # THE PLATFORM MASTERS BUTTON (task #316, 2026-07-14): cb_post.build_platform_masters existed and
            # worked (CLI-only, "python3 cb_post.py masters ..." / "cb_pipeline.py masters <scene>") but had no
            # HTTP route and no Studio button — the same "built but orphaned" pattern this session found and
            # closed repeatedly elsewhere. Requires Gate 5's own picture.mp4 to already exist (fire Gate 5
            # first) — build_platform_masters itself refuses cleanly and names why if it doesn't, surfaced via
            # the job log exactly like every other gate action.
            try:
                d = self._body()
                scene = str(d["scene"]); episode = d.get("episode", "Ep1")
                plats = d.get("platforms") or ["youtube", "netflix", "amazon"]
                jid = _start(_jid(f"masters_s{scene}"), "masters", scene,
                             ["cb_pipeline.py", "masters", scene, ",".join(plats), f"--episode={episode}"])
                self._json(200, {"ok": True, "jobId": jid})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
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
        if self.path == "/api/beat-update":
            try:
                d = self._body()
                pkg = str(d.get("package", "")).strip()
                code = str(d.get("beatCode", "")).strip()
                if not pkg or not code:
                    raise ValueError("package and beatCode required")
                if "/" in pkg or ".." in pkg:
                    raise ValueError("bad package name")
                pf = ROOT / "cb-output" / pkg
                if not pf.exists():
                    raise ValueError("package not found: " + pkg)
                data = json.loads(pf.read_text())
                beats = data.get("beats") or data.get("shots") or []
                target = next((b for b in beats if str(b.get("beatCode") or b.get("shotCode")) == code), None)
                if target is None:
                    raise ValueError("beat not found: " + code)
                for k, v in (d.get("updates") or {}).items():
                    if isinstance(v, dict):
                        cur = target.get(k) if isinstance(target.get(k), dict) else {}
                        # was `if vv not in (None, "")` — skipped every blank sub-field, so a user could never
                        # actively CLEAR a nested field (opensOn/fidelityAllocation/performance/continuity) via
                        # the Studio UI (found 2026-07-08). The only caller (app.html's ebSave) always sends the
                        # FULL current state of every sub-field on every save, never a partial patch, so
                        # excluding only None (not "") is safe — nothing relies on blank-means-leave-alone here.
                        cur.update({kk: vv for kk, vv in v.items() if vv is not None})
                        target[k] = cur
                    elif v is not None:
                        target[k] = v
                if isinstance(d.get("cuts"), list):
                    target["cuts"] = d["cuts"]
                try:
                    (ROOT / "cb-output" / (pkg + ".bak")).write_text(pf.read_text())  # one-step undo backup
                except Exception:
                    pass
                pf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "beatCode": code})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-update":
            # THE SCENE-LOOK LAW + THE SCENE BUBBLE LAW's three locked constants (sceneLook, ambientBed,
            # parentLine) had no write path at all before this — found in the 2026-07-08 software-wide audit.
            # Mirrors /api/beat-update's own generic merge pattern, targeting data["scenes"] instead of
            # data["beats"]/data["shots"].
            try:
                d = self._body()
                pkg = str(d.get("package", "")).strip()
                sn = str(d.get("sceneNumber", "")).strip()
                if not pkg or not sn:
                    raise ValueError("package and sceneNumber required")
                if "/" in pkg or ".." in pkg:
                    raise ValueError("bad package name")
                pf = ROOT / "cb-output" / pkg
                if not pf.exists():
                    raise ValueError("package not found: " + pkg)
                data = json.loads(pf.read_text())
                scenes = data.get("scenes") or []
                target = next((s for s in scenes if str(s.get("sceneNumber")) == sn), None)
                if target is None:
                    raise ValueError("scene not found: " + sn)
                for k, v in (d.get("updates") or {}).items():
                    if isinstance(v, dict):
                        cur = target.get(k) if isinstance(target.get(k), dict) else {}
                        # same nested-clearing fix as /api/beat-update above (2026-07-08) — excludes only None.
                        cur.update({kk: vv for kk, vv in v.items() if vv is not None})
                        target[k] = cur
                    elif v is not None:
                        target[k] = v
                try:
                    (ROOT / "cb-output" / (pkg + ".bak")).write_text(pf.read_text())  # one-step undo backup
                except Exception:
                    pass
                pf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "sceneNumber": sn})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
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
                if cmd in ("fire", "keyframe", "approve", "reject") and (not shot_id or not _SHOT_TOKEN.match(shot_id)):
                    self._json(400, {"error": f"{cmd} needs a shotId (e.g. 1.B1.S1)"}); return
                if cmd == "reject" and not correction:
                    self._json(400, {"error": "reject needs a one-sentence correction"}); return
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
                    if cmd not in ("fire", "next"):
                        self._json(400, {"error": "spendToken applies to fire/next only"}); return
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
                self._json(200, {"ok": True, "jobId": shot_run_job(cmd, scene, episode, shot_id, correction,
                                                                    candidates=candidates,
                                                                    spend_token=spend_token,
                                                                    category=category, candidate=candidate)})
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
