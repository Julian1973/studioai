#!/usr/bin/env python3
"""THE GATE MECHANIC — fire a pipeline gate for a scene, properly, from the framework.

    python3 cb_pipeline.py <gate> <scene>      # fire a gate (1 Director / 2 DP keyframes / 3 Camera clips / 4 Post)
    python3 cb_pipeline.py approve <gate> <scene>   # sign off a gate (unlocks the next one)

Gates fire the relevant skill's discipline IN CODE (config + cb_prompts builders), then STOP for
sign-off. A gate will NOT run until the previous gate is approved (gated workflow, no run-through).
"""
import sys, os, json, subprocess
import cb_gen, cb_scene, cb_post, cb_continuity, cb_context, cb_qa, cb_beats, cb_voice, cb_seedance, cb_retake, cb_prompts as P

EP = "Ep1"
def _resolve_pkg():
    """The current episode's beat package — resolved by glob so ANY episode title works (never a hardcoded name)."""
    import glob
    cands = (glob.glob(f"../cb-output/{EP}_*beat_package.json")
             or glob.glob(f"../cb-output/{EP}_*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else f"../cb-output/{EP}_The_Adventure_Begins_beat_package.json"
PKG = _resolve_pkg()
LOCK = "locked.json"

GATE_SEQ = ["1", "2a", "2b", "3", "4", "5"]  # 2 split into 2a (anchors) + 2b (coverage); 5 = Post, locked behind Gate 4
# ⚠ DUPLICATED (deliberately, not shared) in cb-studio/serve.py — a separate process, imported nowhere near this
# file. If a gate is ever added/renamed/reordered, update BOTH lists in the SAME change, or the HTTP-layer guard
# (serve.py) and this process-layer guard could silently disagree on what "the previous gate" is.

def _lock():  return json.load(open(LOCK)) if os.path.exists(LOCK) else {}
def _save(d): json.dump(d, open(LOCK, "w"), indent=1)

# ── GATE-1 CASCADE-RELOCK (bug fix, 2026-07-02, Julian) ─────────────────────────────────────────────────────────
# A Gate-1 deliverable change — HOWEVER it happened (a Director redirect, a retake brief, or a direct data edit —
# there is no single mutation choke-point to hook, beat-package writes happen from many places) — must automatically
# relock every downstream sign-off. Before this fix, the studio kept showing a scene's Gate 2/3/4/5 as "signed off"
# after its Scene-1 restructure (4 beats -> 5) even though the approved storyboard no longer existed; nothing
# detected the drift. Fixed with the SAME lazy content-hash pattern as scene_cache_stale() (T33 Ruling 3): a
# fingerprint of the scene's beats is stored when Gate 1 is approved; every gate-readiness check recomputes the
# CURRENT fingerprint and cascade-clears (exactly like unapprove("1", scene)) the moment they differ — a passive
# read never returns a stale "signed off" again. ⚠ DUPLICATED in cb-studio/serve.py (a separate process with no
# engine import) — same convention as GATE_SEQ above; update BOTH the SAME way if the fingerprinted fields change.
def _scene_beats_fingerprint(pkg_path, scene):
    """A content hash of every beat belonging to `scene` — the Gate-1 deliverable. Hashes the FULL beat dicts (sorted
    by beatCode, sorted keys) so it changes on ANY story edit: beats added/removed/renamed, cuts/dialogue/camera/
    duration/etc. changed. Nothing downstream (Gate 2/3/4/5) writes back into a beat's own fields, so hashing the
    whole dict is safe — there is nothing to exclude."""
    import hashlib
    d = json.load(open(pkg_path))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
    blob = json.dumps(beats, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

def _relock_if_stale(scene, episode=None):
    """Lazy invalidation — call before ANY gate-readiness read. Returns True (and cascade-clears "1" + every
    downstream gate + every per-beat audio/keyframe/clip lock for this scene, exactly like unapprove("1", scene))
    if Gate 1 is approved with a recorded fingerprint that no longer matches the beat package on disk."""
    episode = episode or EP
    d = _lock()
    sd = d.get(episode, {}).get(str(scene), {})
    if not sd.get("1") or not sd.get("1_fp"):
        return False   # never signed, or signed before this fix shipped (no fingerprint to compare) — nothing to do
    try:
        current = _scene_beats_fingerprint(PKG, scene)
    except Exception:
        return False    # fail-open: a package read error must never brick gate status
    if sd["1_fp"] == current:
        return False
    stale_fp = sd["1_fp"]
    for g in ("1", "2a", "2b", "3", "4", "5", "2", "1_fp"):
        sd.pop(g, None)
    sd["beats"] = {}
    d.setdefault(episode, {})[str(scene)] = sd
    _save(d)
    print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — Gate 1 deliverable changed since sign-off "
          f"(fingerprint {current} != approved {stale_fp}); every downstream gate + per-beat lock reset.", flush=True)
    return True

# ── FRAME CHAIN cascade (doctrine, 2026-07-02, Julian) ───────────────────────────────────────────────────────────
# "A retake upstream marks downstream opening frames dirty through the cascade." A beat's keyframe now chains off
# the PREVIOUS beat's ENDING FRAME (cb_scene.chain_source_for) rather than its opening frame — so if that upstream
# beat's clip is retaken (a new ending frame composed), every beat built from the OLD ending frame is stale, exactly
# like the Gate-1 cascade above but scoped to the per-beat keyframe/clip locks, not the scene gates.
def _beat_end_frame_hash(episode, code, slug):
    """Content hash of a beat's composed ENDING FRAME (see cb_scene.build_ending_frame) — None if it doesn't exist."""
    import hashlib
    p = f"media/{episode}_{code}_{slug}_end.png"
    if not os.path.exists(p):
        return None
    return hashlib.sha1(open(p, "rb").read()).hexdigest()[:16]

def record_chain_source(scene, code, episode=None):
    """Stamp the upstream ending-frame hash THIS beat's keyframe was just built from — the baseline
    _relock_chain_if_dirty compares against. Call right after a continuation beat's keyframe is (re)built."""
    episode = episode or EP
    d = json.load(open(PKG))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
    i = next((k for k, b in enumerate(beats) if str(b.get("beatCode") or b.get("shotCode")) == str(code)), None)
    if i is None or i == 0:
        return   # not found, or the scene anchor (chains off the plate, not a previous beat's ending frame)
    prev = beats[i - 1]
    prev_code = prev.get("beatCode") or prev.get("shotCode")
    prev_slug = prev.get("slug", str(prev_code).replace(".", "_"))
    fp = _beat_end_frame_hash(episode, prev_code, prev_slug)
    if fp is None:
        return   # the upstream beat hasn't rendered a clip yet — this keyframe chained off its OPENING frame instead
    lk = _lock()
    beats_locks = lk.setdefault(episode, {}).setdefault(str(scene), {}).setdefault("beats", {})
    bs = beats_locks.setdefault(str(code), {"audio": False, "keyframe": False, "clip": False})
    bs["chain_source_fp"] = fp
    _save(lk)

def _relock_chain_if_dirty(scene, episode=None):
    """Lazy invalidation, same pattern as _relock_if_stale — call before any gate-readiness read. Walks the scene's
    beats in order; the first one whose recorded chain_source_fp no longer matches its upstream beat's CURRENT
    ending-frame hash, and every beat after it (their own chain sources are now suspect too), get "keyframe" and
    "clip" cleared. Returns True if anything changed."""
    episode = episode or EP
    d = _lock()
    beats_locks = d.get(episode, {}).get(str(scene), {}).get("beats", {})
    if not beats_locks:
        return False
    try:
        pkg = json.load(open(PKG))
    except Exception:
        return False
    scene_beats = [b for b in (pkg.get("beats") or pkg.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    scene_beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
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
        return False
    changed = False
    for b in scene_beats[dirty_from:]:
        code = str(b.get("beatCode") or b.get("shotCode"))
        bl = beats_locks.get(code)
        if bl and (bl.get("keyframe") or bl.get("clip")):
            bl["keyframe"] = False; bl["clip"] = False
            changed = True
    if changed:
        _save(d)
        print(f"⚠ FRAME CHAIN DIRTY — {EP if episode is None else episode} scene {scene}: an upstream ending frame "
              f"changed (a retake); {len(scene_beats) - dirty_from} downstream beat(s) marked needing keyframe "
              f"review.", flush=True)
    return changed

def _approved(scene, gate):
    _relock_if_stale(scene)
    _relock_chain_if_dirty(scene)
    d = _lock().get(EP, {}).get(str(scene), {})
    return bool(d.get(str(gate).lower()))   # explicit per-gate sign-off only (no legacy whole-gate-2 shortcut —
                                            # a bare "2" never locked the plate as master, so it must NOT satisfy 2a)
def _prev_gate(gate):
    gate = str(gate).lower()
    return GATE_SEQ[GATE_SEQ.index(gate) - 1] if gate in GATE_SEQ and GATE_SEQ.index(gate) > 0 else None

# ── TICKET 4 — PER-BEAT cascade locks. These live under locked[EP][scene]["beats"][beatCode] =
#    {"audio":bool, "keyframe":bool, "clip":bool} — a SEPARATE namespace from the scene-gate locks
#    (locked[EP][scene]["1"|"2a"|"2b"|"3"|"4"]), which they NEVER touch.
_BEAT_STAGES = ("audio", "keyframe", "clip")
def _beat_locks(scene, episode=None):
    """The per-beat lock dict for a scene: {beatCode: {"audio":bool,"keyframe":bool,"clip":bool}}.
    `episode=None` (NOT `episode=EP`) is deliberate: a default bound to `EP` at DEFINITION time freezes to whatever
    EP equalled at module-import time ("Ep1") and never picks up the --episode=EpN CLI flag that reassigns the EP
    global afterward — every per-beat lock would silently keep reading/writing "Ep1" regardless of which episode was
    actually selected. Resolving `episode or EP` INSIDE the body reads the CURRENT global at call time instead."""
    episode = episode or EP
    return _lock().get(episode, {}).get(str(scene), {}).get("beats", {})
def _set_beat_lock(scene, code, stage, value=True, episode=None):
    """Set ONE beat's ONE stage lock (audio|keyframe|clip), preserving the scene-gate locks alongside.
    episode=None -> resolved to the CURRENT EP global at call time (see _beat_locks' docstring — same early-binding hazard)."""
    episode = episode or EP
    stage = str(stage).lower()
    if stage not in _BEAT_STAGES:
        raise ValueError(f"unknown beat stage {stage!r} — use one of {_BEAT_STAGES}")
    d = _lock()
    beats = d.setdefault(episode, {}).setdefault(str(scene), {}).setdefault("beats", {})
    bs = beats.setdefault(str(code), {"audio": False, "keyframe": False, "clip": False})
    bs[stage] = bool(value)
    _save(d)
    return bs
def _lock_plate_as_master(scene):
    """On Gate 2A sign-off, the signed-off empty PLATE becomes the scene master that coverage derives from,
    AND is stored in the reusable LOCATIONS LIBRARY (keyed by locationId) for reuse across the show."""
    plate = f"media/{EP}_S{scene}_plate.png"
    if not os.path.exists(plate): return
    locp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "locations.json")
    L = json.load(open(locp))
    sc = L.get(EP, {}).get(str(scene), {})
    if sc.get("master") != plate:
        sc["master"] = plate
        json.dump(L, open(locp, "w"), indent=1, ensure_ascii=False)
        print(f"  ✓ scene {scene} master set to the signed-off PLATE: {plate}")
    lid = sc.get("locationId")
    if lid:
        ref = P.register_location(lid, sc.get("sceneShotName") or sc.get("name", ""), plate,
                                  sc.get("location", ""), sc.get("look", ""), f"{EP} scene {scene}",
                                  episode=EP, scene=str(scene))
        if ref:
            print(f"  ✓ scene shot STORED in the locations library: {os.path.basename(ref)} "
                  f"(locationId '{lid}') — reusable as a reference anywhere this place appears", flush=True)

def approve(gate, scene):
    gate = str(gate).lower()
    d = _lock(); sd = d.setdefault(EP, {}).setdefault(str(scene), {}); sd[gate] = True
    if gate == "1":
        sd["1_fp"] = _scene_beats_fingerprint(PKG, scene)   # the cascade-relock baseline (see _relock_if_stale)
    _save(d)
    if gate == "2a":
        _lock_plate_as_master(scene)
    print(f"✓ approved {EP} scene {scene} gate {gate} — next gate unlocked")

def unapprove(gate, scene):
    """REVERSE a sign-off so you can go back and alter an earlier step. Removes THIS gate's sign-off AND every gate
    after it (they depend on it), so un-signing Step 1 (2a) also re-locks Step 2 (2b). If the FOUNDATION (2a) or the
    plan (1) is un-signed, the scene master is reset to None — the plate is no longer a locked foundation, so a stale
    plate can never satisfy Gate 2b, and you can rebuild/alter the foundation cleanly before re-signing."""
    gate = str(gate).lower(); scene = str(scene)
    d = _lock(); sd = d.setdefault(EP, {}).setdefault(scene, {})
    order = ["1", "2a", "2b", "3", "4", "5"]
    if gate in order:
        for g in order[order.index(gate):]:   # this gate + everything downstream
            sd.pop(g, None)
    sd.pop("2", None)                          # drop any legacy whole-gate-2 flag too
    if gate == "1":
        sd.pop("1_fp", None)                   # drop the cascade-relock baseline too — a fresh approve() recomputes it
    # ── TICKET 4 reconciliation — a scene-gate unapprove MUST also clear the DEPENDENT per-beat cascade approvals
    #    (locked[EP][scene]["beats"][code]) for THIS scene ONLY; otherwise a stale beats{} approval survives an
    #    un-signed gate (a keyframe/clip still reads "approved" after its gate was reopened). Each gate clears the
    #    beat stages that it + everything downstream invalidate; scope is sd["beats"] — this scene, never another.
    _gate_clears = {"1": _BEAT_STAGES, "2a": ("keyframe", "clip"), "2b": ("keyframe", "clip"),
                    "3": ("clip",), "4": ()}
    _cleared = []
    for _code, _bs in (sd.get("beats") or {}).items():
        if isinstance(_bs, dict):
            _hit = [st for st in _gate_clears.get(gate, ()) if _bs.get(st)]
            for _st in _hit:
                _bs[_st] = False
            if _hit:
                _cleared.append(f"{_code}:{'+'.join(_hit)}")
    _save(d)
    if _cleared:
        print(f"  ↺ cleared dependent per-beat approvals in scene {scene}: {', '.join(_cleared)}", flush=True)
    if gate in ("1", "2a"):                    # foundation un-signed -> the locked plate is no longer the master
        locp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "locations.json")
        if os.path.exists(locp):
            L = json.load(open(locp)); s = L.get(EP, {}).get(scene, {})
            if s.get("master") is not None:
                s["master"] = None; json.dump(L, open(locp, "w"), indent=1, ensure_ascii=False)
                print(f"  ✓ scene {scene} master reset (foundation un-signed) — Gate 2b re-locked", flush=True)
    print(f"↺ un-signed {EP} scene {scene} gate {gate} (+ all downstream) — alter it, then re-sign.", flush=True)

def _shots(scene):
    d = json.load(open(PKG)); items = [s for s in (d.get("beats") or d.get("shots") or []) if str(s.get("sceneNumber")) == scene]
    for s in items:
        s.setdefault("shotCode", s.get("beatCode"))
    return items

NOTES = "notes.json"
def _notes():  return json.load(open(NOTES)) if os.path.exists(NOTES) else {}
def save_note(shot_code, note):
    d = _notes()
    if note.strip(): d[shot_code] = note.strip()
    else: d.pop(shot_code, None)
    json.dump(d, open(NOTES, "w"), indent=1)

def regen(scene, shot_code, kind, note, target="both"):
    """Regenerate ONE shot/beat with a human correction note. kind = 'keyframe' (default) or 'clip'.
    target (keyframe only) = 'both' | 'start' | 'end'."""
    need = "2b" if kind == "clip" else "2a"   # a keyframe regen needs the FOUNDATION (2a) signed; a clip regen needs the keyframes (2b)
    if not _approved(scene, need):
        print(f"⛔ Gate {need} not signed off for {EP} scene {scene} — sign it off before regenerating ({kind}).", flush=True); return
    save_note(shot_code, note)
    s = next((x for x in _shots(scene) if x["shotCode"] == shot_code), None)
    if not s:
        print(f"REGEN: shot {shot_code} not found in scene {scene}"); return
    if kind == "clip":
        # ── UNIFIED RENDER PATH — Gate 3 ≡ clip regen (they MUST stay on the same path) ──────────────────────────
        # A clip regen renders through the EXACT same path as Gate 3: cb_beats.run → cb_prompts.seedance_json →
        # cb_gen.generate_video_seedance_ref. That path honours the beat's seedancePromptOverride, the @Audio1
        # ElevenLabs V3 lip-sync track, and Seedance-scored SFX + MUSIC. If Gate 3 and clip regen ever diverge, a
        # re-rendered beat comes from a DIFFERENT system than the rest of the scene and POST stitches a mismatched
        # take. (Was cb_dialogue.run / build_ref2vid_prompt — SFX-only, NO music — now DEPRECATED; see cb_dialogue.py.)
        # The correction `note` is recorded via save_note() above; per-render prompt changes go through the beat's
        # seedancePromptOverride (which this path honours), not an ad-hoc prompt note.
        print(f"REGEN clip {shot_code} via the Gate-3 beat path (cb_beats.run codes=[{shot_code}]) | note: {note[:80]!r}", flush=True)
        cb_beats.run(PKG, scene, EP, codes=[shot_code])
    else:
        cb_scene.regen_shot(PKG, scene, shot_code, EP, note, target)

def build_master(scene, rounds=2):
    """STRUCTURAL master-build: (re)build the scene's establishing MASTER with the full reference + identity lock,
    then VERIFY it visually before the scene derives from it. The foundation must be right — everything inherits it."""
    code = _shots(scene)[0]["shotCode"]
    print(f"BUILD MASTER — {EP} scene {scene} (establishing shot {code}, full refs + identity lock)", flush=True)
    for rnd in range(1, rounds + 1):
        cb_scene.regen_shot(PKG, scene, code, EP, "", "start")
        m = next((r for r in cb_qa.check_scene(PKG, scene, EP, only=code) if r["shot"] == code), None)
        ok = bool(m and m["ok"])
        print(f"  master QA round {rnd}: {'PASS — locked' if ok else 'FLAG: ' + ((m or {}).get('verdict','') or '')[:160]}", flush=True)
        if ok:
            cb_scene.regen_shot(PKG, scene, code, EP, "", "end")  # the master's end, from the verified start
            return True
    print("  master still flagged after rebuild — review before deriving.", flush=True)
    return False

def autofix(scene, rounds=2):
    """REPORT-ONLY QA pass. Runs the visual QA ONCE and reports flags per shot — it does NOT auto-regenerate.
    Auto-regen was destructive: a single (often FALSE) flag would overwrite a GOOD frame with a worse one — e.g. it
    turned a correct bee into a bear. Regeneration is now a DELIBERATE, reviewed, per-shot action (the studio's Fix
    button / the `regen` command), never an automatic in-place overwrite. (`rounds` kept for signature compat.)"""
    res = cb_qa.check_scene(PKG, scene, EP)
    flagged = [r for r in res if r["ok"] is False]
    print(f"--- visual QA (REPORT-ONLY — flags only, never overwrites): scene {scene} ---", flush=True)
    for r in res:
        tag = "PASS" if r["ok"] else ("FLAG" if r["ok"] is False else "ERR ")
        line = "" if r["ok"] else f": {r['verdict'].replace('FLAG', '', 1).strip().splitlines()[0][:110]}"
        print(f"   [{tag}] {r['shot']}{line}", flush=True)
    if flagged:
        print(f"   {len(flagged)} shot(s) flagged for REVIEW — regenerate deliberately if real; no frame was overwritten.", flush=True)
    else:
        print("   ✓ scene is CLEAN.", flush=True)
    return not flagged

def gate1(scene):
    global PKG
    PKG = _resolve_pkg()   # pick up the real package up-front (covers a re-fire where it already exists)
    # THE DIRECTOR — if no shot package exists yet, break the uploaded script down first (world-class
    # script analysis via cb_director), then display the plan. Once authored, Gate 1 just displays it.
    if not os.path.exists(PKG):
        import glob, cb_director
        scripts = sorted(glob.glob(f"../cb-studio/data/scripts/{EP}_*.txt"))
        if not scripts:
            print(f"⛔ GATE 1 — no script for {EP}. Upload the script in the studio first, then fire Gate 1."); return
        script = scripts[0]
        title = os.path.basename(script)[len(EP) + 1:].rsplit(".", 1)[0].replace("_", " ")
        print(f"GATE 1 — THE DIRECTOR: no shot package yet — reading the script and breaking it down "
              f"({os.path.basename(script)}). This is the real script analysis; it takes a few minutes.", flush=True)
        r = cb_director.direct(script, EP, title)
        PKG = r["package"]   # use the EXACT path the Director wrote (its title may differ from any default)
        print(f"  ✓ Director complete: {r['scenes']} scenes, {r.get('beats', r.get('shots'))} beats → {os.path.basename(r['package'])}", flush=True)
    print(f"GATE 1 — Director BEAT plan, {EP} scene {scene}:")
    for s in _shots(scene):
        code = s.get("beatCode", s.get("shotCode"))
        print(f"  {code} | {s.get('durationSec','?')}s | bands={s.get('keenWristbands')} | {s.get('characters')}")
        print(f"     {s.get('storyBeat', s.get('action',''))}")
        for c in (s.get("cuts") or []):
            line = f"  «{c['dialogue']}»" if c.get("dialogue") else ""
            print(f"       · {c.get('framing','')}: {c.get('action','')}{line}")

def redirect(scene="1"):
    """FORCE a Gate-1 RE-BREAK — back up + remove the existing beat package, then re-author the WHOLE episode with the
    CURRENT Director prompt (use after hardening it: pacing / character-presence). The old package is kept as a `.bak`.
    Exists because gate1() is idempotent — it only authors when NO package exists, so a plain 're-fire' just re-displays
    the old beats and silently ignores Director-prompt changes."""
    global PKG
    PKG = _resolve_pkg()
    if os.path.exists(PKG):
        import shutil
        bak = PKG + ".bak-redirect"
        shutil.copy2(PKG, bak); os.remove(PKG)
        print(f"GATE 1 — FORCE RE-BREAK: backed up + removed {os.path.basename(PKG)} (→ {os.path.basename(bak)}); "
              f"re-authoring the whole episode fresh with the current Director.", flush=True)
    gate1(scene)

def _scene_chars(scene):
    return P.scene_characters(_shots(scene))

def anchors(scene):
    """GATE 2A — the scene FOUNDATION: EACH character's OWN locked 4-way turnaround (turn4) + an EMPTY scene
    PLATE (world, no characters). Build/verify, STOP for sign-off. On sign-off the plate becomes the scene
    master. One sheet PER character — each is its turn4, exactly what the keyframes render from (no merged
    sheet, no generation, no drift)."""
    print(f"GATE 2A — SCENE FOUNDATION (per-character turn4 sheets + empty PLATE), {EP} scene {scene}:", flush=True)
    chars = _scene_chars(scene); sc = P.scene_cfg(EP, str(scene))
    # Each character's OWN locked sheet = its turn4 (one per character, from the library)
    print("  Character sheets — one per character (its own locked 4-way turnaround):", flush=True)
    for c in chars:
        try:
            print(f"    {c}: {os.path.basename(P.char_identity_ref(c))}", flush=True)
        except Exception as e:
            print(f"    {c}: ⛔ {e}", flush=True)
    # A1 — empty scene PLATE (the world)
    plate = f"media/{EP}_S{scene}_plate.png"
    if sc.get("master") == plate and os.path.exists(plate):
        print(f"  scene PLATE is the locked master = {plate} — keeping it.", flush=True)
    else:
        # (re)build a FRESH plate on every fire UNTIL the foundation is signed off,
        # so "Rebuild foundation" actually regenerates (not just re-verifies the old one).
        plate = cb_scene.build_plate(PKG, scene, EP)
    v1 = cb_qa.check_plate(plate, sc["location"], sc.get("master"))
    print(f"  PLATE QA: {'PASS' if v1['ok'] else 'FLAG: ' + ((v1.get('verdict') or '')[:200])}", flush=True)
    print(f"  --- FOUNDATION BUILT. Review the plate ({plate}) + each character's own turnaround sheet; sign off:", flush=True)
    print(f"        python3 cb_pipeline.py approve 2a {scene}   (locks the plate as the scene master)", flush=True)

def coverage(scene):
    """GATE 2B — derive every shot from the FROZEN master (the scene plate) + the character turnarounds, built as a
    sequential CHAIN (start -> end -> next start off the prior end). NO QA pass — review in the studio. Requires 2A."""
    print(f"GATE 2B — COVERAGE (chained build, NO QA), {EP} scene {scene}:", flush=True)
    if not _approved(scene, "2a"):   # the LIVE foundation sign-off, independent of any leftover master on disk
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — build + sign off the foundation first.", flush=True); return
    sc = P.scene_cfg(EP, str(scene))
    if not (sc.get("master") and os.path.exists(sc["master"])):
        print(f"  ⛔ no scene plate (master) — fire gate 2a first.", flush=True); return
    cb_scene.run(PKG, scene, EP)  # chained build off the Director's words + library turnarounds
    # FOUNDATION QA — the keyframes are what the WHOLE clip is built from, so audit every beat's opening frame against
    # the Definition of Done. REPORT-ONLY (never auto-overwrites a good frame); you review + regen the flagged in the studio.
    print(f"  --- KEYFRAME QA — every beat's opening frame vs the Definition of Done (report-only):", flush=True)
    try:
        res = cb_qa.check_scene(PKG, scene, EP)
        for r in res:
            print(f"      {r.get('shot','?')}: {r.get('verdict','')}", flush=True)
        npass = sum(1 for r in res if r.get("ok") is True)
        flagged = [r.get("shot", "?") for r in res if r.get("ok") is False]
        print(f"  --- {npass}/{len(res)} keyframes PASS"
              + ("  ·  ⚑ FLAGGED (review + regen before sign-off): " + ", ".join(flagged) if flagged
                 else "  ·  all clean ✓"), flush=True)
    except Exception as e:
        print(f"  --- keyframe QA skipped ({str(e)[:120]})", flush=True)
    print(f"=== GATE 2B done — {EP} scene {scene} built + QA'd; review the flagged, then sign off ===", flush=True)

def rebuild(scene):
    """CLEAN REBUILD of ALL keyframes for the scene — delete every stale opening frame and re-render each beat FRESH
    (force, no resume-keep). Use after un-signing Gate 2B / changing the template or references. Requires 2A signed."""
    print(f"GATE 2B — CLEAN REBUILD (all keyframes, force), {EP} scene {scene}:", flush=True)
    if not _approved(scene, "2a"):
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — sign off the foundation first.", flush=True); return
    sc = P.scene_cfg(EP, str(scene))
    if not (sc.get("master") and os.path.exists(sc["master"])):
        print(f"  ⛔ no scene plate (master) — fire gate 2a first.", flush=True); return
    cb_scene.run(PKG, scene, EP, force=True)   # force = clean each stale keyframe, then rebuild ALL fresh
    print(f"  --- KEYFRAME QA — every beat's opening frame vs the Definition of Done (report-only):", flush=True)
    try:
        res = cb_qa.check_scene(PKG, scene, EP)
        for r in res:
            print(f"      {r.get('shot','?')}: {r.get('verdict','')}", flush=True)
        npass = sum(1 for r in res if r.get("ok") is True)
        flagged = [r.get("shot", "?") for r in res if r.get("ok") is False]
        print(f"  --- {npass}/{len(res)} keyframes PASS"
              + ("  ·  ⚑ FLAGGED (review + regen before sign-off): " + ", ".join(flagged) if flagged
                 else "  ·  all clean ✓"), flush=True)
    except Exception as e:
        print(f"  --- keyframe QA skipped ({str(e)[:120]})", flush=True)
    print(f"=== CLEAN REBUILD done — {EP} scene {scene} all keyframes rebuilt fresh; review + sign off ===", flush=True)

def set_master(scene, beat_code, character, episode=None, scope="location", force=False):
    """★ Set the CHARACTER MASTER (Flow 'use this image as subject') for `character` from beat `beat_code`'s keyframe.
    Guards (each overridable only with force): Gate 2A signed · the character is in the beat · a SOLO opening frame
    (a 2-up frame bleeds identity) · the frame passes keyframe QA. Keyed per-location so it reuses when the place
    returns. After this, every later keyframe of `character` in this location anchors to it (rebuild to apply)."""
    episode = episode or EP
    d = json.load(open(PKG)); beats = d.get("beats") or d.get("shots") or []
    beat = next((b for b in beats if (b.get("beatCode") or b.get("shotCode") or b.get("id")) == beat_code), None)
    if not beat:
        print(f"  ⛔ beat '{beat_code}' not found in the package.", flush=True); return
    if character not in (beat.get("characters") or []):
        print(f"  ⛔ {character} is not in beat {beat_code} (cast: {beat.get('characters')}).", flush=True); return
    framed = P.opening_cast(beat)
    if framed != [character] and not force:
        print(f"  ⛔ {beat_code}'s opening frame holds {framed} — a master must come from a SOLO frame of {character} "
              f"(a 2-up frame bleeds identity). Use a solo hero keyframe, or pass force.", flush=True); return
    code = beat.get("beatCode") or beat.get("shotCode"); slug = beat.get("slug", (code or "").replace(".", "_"))
    kf = f"media/{episode}_{code}_{slug}.png"
    if not os.path.exists(kf):
        print(f"  ⛔ no keyframe on disk for {beat_code} ({kf}) — build it first.", flush=True); return
    if not _approved(scene, "2a"):
        print(f"  ⛔ Gate 2A not signed off for {episode} scene {scene} — sign off the foundation first.", flush=True); return
    sc = P.scene_cfg(episode, str(scene)); loc = sc.get("locationId")
    if not loc:
        print(f"  ⛔ scene {scene} has no locationId in locations.json — cannot key the master.", flush=True); return
    qa = cb_qa.check_done_frame(beat, kf, sc, episode)
    if qa.get("ok") is not True and not force:
        print(f"  ⛔ {beat_code} keyframe is NOT QA-clean (verdict: {qa.get('verdict')}; "
              f"{', '.join(qa.get('reasons') or [])}) — a master must be on-model. Perfect/regen it first, or pass force.", flush=True)
        return
    p = P.register_master(character, loc, kf, episode=episode, scene=str(scene), beat=code, scope=scope, approved_by="studio")
    tag = f"#{episode}" if scope == "episode" else ""
    print(f"  ★ MASTER SET — {character}@{loc}{tag}  ←  {os.path.basename(kf)}  (QA {qa.get('verdict')})", flush=True)
    print(f"     stored: {p}", flush=True)
    print(f"     every later keyframe of {character} in '{loc}' now anchors to this — rebuild the scene to apply.", flush=True)

def clear_master_cmd(scene, character, episode=None):
    """Retire `character`'s master for this scene's location → falls back to the grey-bg Character Box."""
    episode = episode or EP
    sc = P.scene_cfg(episode, str(scene)); loc = sc.get("locationId")
    if not loc:
        print(f"  ⛔ scene {scene} has no locationId.", flush=True); return
    n = P.clear_master(character, loc, episode)
    print(f"  cleared {n} master(s) for {character}@{loc} — back to the Character Box. Rebuild to apply.", flush=True)

def regen_anchor(scene, which, note=""):
    """Re-roll ONE foundation element with a correction note (notes → re-roll only the flagged one)."""
    if which.lower() in ("a1", "plate", "world", "scene"):
        plate = cb_scene.build_plate(PKG, scene, EP, note=note)
        sc = P.scene_cfg(EP, str(scene))
        v = cb_qa.check_plate(plate, sc["location"], sc.get("master"))
        print(f"  PLATE QA: {'PASS' if v['ok'] else 'FLAG: ' + ((v.get('verdict') or '')[:200])}", flush=True)
    elif which.lower() in ("a2", "sheet", "charsheet"):
        cb_scene.build_charsheet(PKG, scene, EP, note=note)
        v = cb_qa.check_charsheet(f"media/{EP}_S{scene}_charsheet.png", _scene_chars(scene), EP)
        print(f"  SHEET QA: {'PASS' if v['ok'] else 'FLAG: ' + ((v.get('verdict') or '')[:200])}", flush=True)
    else:
        print(f"  unknown element '{which}' — use a1 (plate) | a2 (sheet)", flush=True)

# ── TICKET 4 — the per-beat CASCADE subcommands (the linear gated UI fires these one beat at a time).
def _beat_in(scene, code):
    """Find ONE beat dict in the package by code, scoped to a scene."""
    d = json.load(open(PKG)); scene = str(scene)
    beats = d.get("beats") or d.get("shots") or []
    return next((b for b in beats
                 if str(b.get("sceneNumber")) == scene
                 and (b.get("beatCode") or b.get("shotCode") or b.get("id")) == code), None)

def _scene_beat_order(scene):
    """Beat codes for a scene, in package (beat) order — used to compute NEXT in the cascade."""
    d = json.load(open(PKG)); scene = str(scene)
    return [(b.get("beatCode") or b.get("shotCode")) for b in (d.get("beats") or d.get("shots") or [])
            if str(b.get("sceneNumber")) == scene]

def build_beat(scene, code, chain_from=None):
    """Build ONE beat's opening keyframe (CASCADE unit). chain_from = the previous beat's APPROVED keyframe path."""
    kf = cb_scene.build_one_beat(PKG, scene, code, EP, chain_from=(chain_from or None))
    if kf:
        record_chain_source(scene, code)   # FRAME CHAIN doctrine baseline — see _relock_chain_if_dirty
    print(f"KEYFRAME={kf}", flush=True)
    return kf

def gen_audio(scene, code):
    """Build THIS beat's V3 dialogue track and report its measured duration (drives the per-beat HOLD math)."""
    beat = _beat_in(scene, code)
    if not beat:
        print(f"  ⛔ beat '{code}' not found in scene {scene}.", flush=True); return
    _vd = cb_seedance.director_voice_direction(PKG, code, EP)   # SAME director source as Gate 3 — the voice ACTS the beat
    t = cb_voice.build_dialogue_track(beat, out=f"vo_{EP}_{code}.mp3", voice_direction=_vd)
    # A wordless/silent beat (no speakers, no voiceScript, no cut dialogue) yields None — that's valid, not an error.
    # Report a zero-duration track so the cascade treats it as "audio done with no VO" (mirrors cb_beats' None-guard).
    if t is None:
        print("  (beat has no dialogue — wordless; no voice track needed)", flush=True)
        _set_beat_lock(scene, code, "audio", True)   # voices are AUTOMATIC — no manual listen / sign-off (auto-lock on gen)
        print("  ✓ audio auto-locked (wordless)", flush=True)
        print("AUDIO_DUR=0.0", flush=True)
        print("TRACK=", flush=True)
        return None
    track = t.get("track")
    dur = 0.0
    if track and os.path.exists(track):
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                  "-of", "csv=p=0", track], capture_output=True, text=True, timeout=30)
            dur = round(float(out.stdout.strip()), 2)
        except Exception:
            dur = 0.0
    _set_beat_lock(scene, code, "audio", True)       # voices are AUTOMATIC — generated + locked, no manual listen / sign-off
    print(f"AUDIO_DUR={dur}", flush=True)
    print(f"TRACK={track}", flush=True)
    print("  ✓ audio auto-locked", flush=True)
    return track

def render_beat(scene, code):
    """Render ONE beat as its Seedance take (the Gate-3 beat method, scoped to a single beat)."""
    clips = cb_beats.run(PKG, scene, EP, codes=[code])
    clip = clips[0] if clips else None
    _set_beat_lock(scene, code, "audio", True)   # the clip render generates the V3 voice inline — audio is AUTOMATIC
    print(f"CLIP={clip}", flush=True)
    return clip

def approve_beat(scene, code, stage, value=True):
    """Lock (value=True) or UNLOCK (value=False) ONE beat's ONE stage (audio|keyframe|clip). On a keyframe APPROVAL,
    print the NEXT beat in scene order so the studio can auto-fire the chain."""
    _set_beat_lock(scene, code, stage, value)
    print(f"{'✓ approved' if value else '↺ unlocked'} {EP} scene {scene} beat {code} stage {stage}", flush=True)
    if value and str(stage).lower() == "keyframe":
        order = _scene_beat_order(scene)
        nxt = None
        if code in order:
            i = order.index(code)
            nxt = order[i + 1] if i + 1 < len(order) else None
        print(f"NEXT={nxt or 'NONE'}", flush=True)

def gate3(scene):
    # GATE 3 = Camera. THE BEAT METHOD (the first-ever FLOW, 2026-06-23): group the scene's shots into ~10-12s BEATS
    # and render each beat as ONE multi-shot Seedance take (Seedance directs its OWN internal cuts + camera + timing —
    # where the flow comes from), chained last-frame -> next-beat start, then assemble. THE RULE: one Seedance take per
    # beat, 10-12 seconds. Native voice rides in the take; the acted V3 voice is swapped in Post (Voice Changer keeps
    # timing). This REPLACES the per-shot ref2vid path, which chopped the scene into 8 isolated clips and felt clunky.
    print("GATE 3 — Camera: MULTI-SHOT BEATS (one 10-12s Seedance take per beat — the flow method):", flush=True)
    cb_beats.run(PKG, scene, EP)

def gate4(scene):
    cb_retake.process_retakes(PKG, scene, EP)   # RETAKES — off the Gate-3 sign-off: regen flagged shots + splice + re-conform

def gate5(scene):
    cb_post.run(PKG, scene, EP)                 # POST — master the mix + export stems (once, after retakes)

GATES = {"1": gate1, "2a": anchors, "2b": coverage, "3": gate3, "4": gate4, "5": gate5}
_GENERATIVE = ("2a", "2b", "3")  # gates that render → run the pre-flight + continuity checks around them

def fire(gate, scene):
    gate = str(gate).lower()
    if gate not in GATES:
        print(f"unknown gate '{gate}' — use one of {list(GATES)}"); return
    prev = _prev_gate(gate)
    if prev and not _approved(scene, prev):
        print(f"⛔ Gate {prev} not signed off for {EP} scene {scene}. Review it, then:")
        print(f"     python3 cb_pipeline.py approve {prev} {scene}")
        return
    print(f"=== FIRE GATE {gate} — {EP} scene {scene} ===", flush=True)
    if gate in _GENERATIVE:
        print("--- pre-flight: context completeness audit (everything pulled in & locked?) ---", flush=True)
        cb_context.run(PKG, scene, EP)
    GATES[gate](scene)
    if gate in _GENERATIVE:
        print("--- continuity check (cross-scene, data) ---", flush=True)
        cb_continuity.run(PKG, EP)
    print(f"=== gate {gate} done — REVIEW, then sign off:  python3 cb_pipeline.py approve {gate} {scene} ===", flush=True)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    # EPISODE SELECTION — accept --episode=EpN ANYWHERE in argv (order-independent) and retarget this invocation to
    # it BEFORE any command runs. Every function below reads the EP/PKG module globals directly (not as a parameter),
    # so reassigning them here retargets the ENTIRE script to the right episode with one small patch, instead of
    # threading an `episode` argument through every individual function signature. The flag is stripped out of
    # sys.argv first, so every command's EXISTING positional argv[2]/argv[3]/... parsing is completely untouched.
    # Without this, EP stayed hardcoded to "Ep1" for every gate action regardless of which episode was selected in
    # the studio — firing/approving/regenerating on Episode 3 would have silently acted on Episode 1's package.
    _epflag = next((a for a in sys.argv[1:] if a.startswith("--episode=")), None)
    if _epflag:
        sys.argv = [a for a in sys.argv if a != _epflag]
        EP = _epflag.split("=", 1)[1].strip() or EP
        PKG = _resolve_pkg()
    cmd = sys.argv[1].lower()
    if cmd == "approve":
        approve(sys.argv[2], sys.argv[3])
    elif cmd == "unapprove":
        unapprove(sys.argv[2], sys.argv[3])
    elif cmd == "autofix":
        autofix(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    elif cmd in ("master", "build-master"):
        build_master(sys.argv[2])
    elif cmd == "anchor":
        # anchor <scene> <a1|a2> [note]   — re-roll one anchor at Gate 2A
        regen_anchor(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "regen":
        # regen <scene> <shotCode> <kind> [note] [target]
        regen(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "keyframe",
              sys.argv[5] if len(sys.argv) > 5 else "",
              sys.argv[6] if len(sys.argv) > 6 else "both")
    elif cmd == "rebuild":
        # rebuild <scene>  — CLEAN rebuild of ALL keyframes (force; deletes stale frames, re-renders every beat)
        rebuild(sys.argv[2])
    elif cmd in ("redirect", "rebreak"):
        # redirect [scene]  — FORCE a Gate-1 re-break (back up + remove the package, re-author with the current Director)
        redirect(sys.argv[2] if len(sys.argv) > 2 else "1")
    elif cmd == "set-master":
        # set-master <scene> <beatCode> <character> [episode] [scope=location|episode] [force]
        set_master(sys.argv[2], sys.argv[3], sys.argv[4],
                   sys.argv[5] if len(sys.argv) > 5 else None,
                   sys.argv[6] if len(sys.argv) > 6 else "location",
                   (len(sys.argv) > 7 and str(sys.argv[7]).lower() in ("force", "1", "true")))
    elif cmd == "clear-master":
        # clear-master <scene> <character> [episode]
        clear_master_cmd(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "build-beat":
        # build-beat <scene> <beatCode> [chain_from]  — CASCADE: build one beat's opening keyframe
        build_beat(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif cmd == "gen-audio":
        # gen-audio <scene> <beatCode>  — build + measure this beat's V3 dialogue track
        gen_audio(sys.argv[2], sys.argv[3])
    elif cmd == "render-beat":
        # render-beat <scene> <beatCode>  — render one beat's Seedance take
        render_beat(sys.argv[2], sys.argv[3])
    elif cmd == "approve-beat":
        # approve-beat <scene> <beatCode> <stage> [value]  — lock (default) or unlock (value=false) one beat stage
        approve_beat(sys.argv[2], sys.argv[3], sys.argv[4], value=(len(sys.argv) < 6 or str(sys.argv[5]).lower() != "false"))
    elif cmd == "director-eye":
        # director-eye  — Gate 1.5: flag-and-report review of the beat package vs the show bible (changes NOTHING)
        import cb_director_eye
        cb_director_eye.run(PKG, EP)
    else:
        fire(cmd.replace("gate", "").strip(), sys.argv[2])
