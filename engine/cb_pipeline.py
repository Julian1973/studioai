#!/usr/bin/env python3
"""THE GATE MECHANIC — fire a pipeline gate for a scene, properly, from the framework.

    python3 cb_pipeline.py <gate> <scene>      # fire a gate (1 Director / 1.6 Previz reel / 2a DP anchors /
                                                #             2b DP coverage / 3 Camera clips / 4 Retakes / 5 Post)
    python3 cb_pipeline.py approve <gate> <scene>   # sign off a gate (unlocks the next one)

Gates fire the relevant skill's discipline IN CODE (config + cb_prompts builders), then STOP for
sign-off. A gate will NOT run until the previous gate is approved (gated workflow, no run-through).
"""
import sys, os, json, subprocess, datetime
import cb_scene, cb_post, cb_continuity, cb_context, cb_qa, cb_beats, cb_voice, cb_seedance, cb_retake, cb_prompts as P
import cb_previz
import paths as _paths   # FIXED 2026-07-12 (loose-ends pass): this module's own 3 inline
                          # os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "locations.json")
                          # builds (paths.py's own docstring already named this exact migration as "real and
                          # worth doing" but out of its own scope) — now paths.LOCATIONS (same file).

EP = "Ep1"
def _resolve_pkg():
    """The current episode's beat package — resolved by glob so ANY episode title works (never a hardcoded name)."""
    import glob
    cands = (glob.glob(f"../cb-output/{EP}_*beat_package.json")
             or glob.glob(f"../cb-output/{EP}_*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else f"../cb-output/{EP}_The_Adventure_Begins_beat_package.json"
PKG = _resolve_pkg()
LOCK = "locked.json"

GATE_SEQ = ["1", "1.6", "2a", "2b", "3", "4", "5"]  # 2 split into 2a (anchors) + 2b (coverage); 5 = Post,
# locked behind Gate 4. "1.6" = THE PREVIZ REEL (2026-07-08, Story/Editorial + Pipeline TD panel finding,
# cb_previz.py) — a human sign-off stage between Gate 1 and Gate 2a: scratch VO + placeholder/keyframe
# cards, near-zero cost, so Julian hears dialogue timing/rhythm before the first paid render (Gate 2a's
# plate) fires. Named "1.6" (not "1.5") to avoid colliding with the ALREADY-established "Gate 1.5" —
# Director's Eye (cb_director_eye.py), an unrelated automatic flag-only bible review with no lock state
# of its own and never a member of this list; see cb_previz.py's own module docstring for the full note.
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
    import hashlib, cb_preflight
    d = json.load(open(pkg_path))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    # FIXED 2026-07-11 (full-codebase audit): a plain lexicographic sort misorders any scene with 10+ beats
    # ("1.B10" sorts before "1.B2") — the same bug class already fixed at every other beat-order site via
    # cb_preflight._beat_sort_key (cb_beats, cb_director, cb_previz, cb_replicator, this file's own
    # export_storyboard). Functionally harmless here (only used to build a self-consistent hash blob), but kept
    # consistent with every sibling sort in this file rather than left as the one exception.
    beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
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
    # Derived from the module constant (not hand-duplicated) — the exact duplication-drift bug class
    # unapprove() below was already fixed for; a future GATE_SEQ edit only needs to happen in one place.
    for g in list(GATE_SEQ) + ["2", "1_fp"]:
        sd.pop(g, None)
    sd["beats"] = {}
    d.setdefault(episode, {})[str(scene)] = sd
    _save(d)
    # FIXED 2026-07-11 (full-codebase audit): this cascade cleared locked.json's gate flags but never reset
    # locations.json's scene `master` field the way unapprove()'s own manual path already does (lines ~409-415)
    # — the only thing cb_scene.build_one_beat's "needs-plate" guard actually reads (via P.scene_cfg) is that
    # `master` field, never locked.json's "2a" flag. Without this, an auto-relock from a Gate-1 edit left the
    # STALE plate looking like a valid master, so Gate 2b's "needs foundation" guard never actually re-armed.
    locp = _paths.LOCATIONS
    if os.path.exists(locp):
        try:
            L = json.load(open(locp)); s = L.get(episode, {}).get(str(scene), {})
            if s.get("master") is not None:
                s["master"] = None; json.dump(L, open(locp, "w"), indent=1, ensure_ascii=False)
        except Exception:
            pass   # fail-open, same convention as the fingerprint read above — never brick gate status
    print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — Gate 1 deliverable changed since sign-off "
          f"(fingerprint {current} != approved {stale_fp}); every downstream gate + per-beat lock reset "
          f"(including the scene plate master).", flush=True)
    return True

# ── FRAME CHAIN cascade (doctrine, 2026-07-02, Julian; frame source updated 2026-07-03 — THE HARVEST) ──────────
# "A retake upstream marks downstream opening frames dirty through the cascade." A beat's keyframe/relay opens off
# the PREVIOUS beat's HARVESTED SETTLE FRAME (cb_scene.chain_source_for / relay_source_for) rather than its opening
# frame — so if that upstream beat's clip is retaken (a new settle frame harvested), every beat built from the OLD
# settle frame is stale, exactly like the Gate-1 cascade above but scoped to the per-beat keyframe/clip locks, not
# the scene gates. "Ending frames are harvested, never composed" (2026-07-03) — this hash now reads the harvested
# settle frame, not the retired "composed" ending frame.
def _beat_end_frame_hash(episode, code, slug):
    """Content hash of a beat's HARVESTED SETTLE FRAME (see cb_scene.harvest_settle_frame) — None if it doesn't exist."""
    import hashlib
    p = f"media/{episode}_{code}_{slug}_settle.png"
    if not os.path.exists(p):
        return None
    return hashlib.sha1(open(p, "rb").read()).hexdigest()[:16]

def _pkg_for_episode(episode):
    """FIXED 2026-07-11 (full-codebase audit): record_chain_source/_relock_chain_if_dirty accepted an `episode`
    parameter that scoped the LOCK-file lookup but silently read the beat package via the module-global PKG
    regardless — half-wired, since nothing currently calls either with an episode different from the current
    EP (dormant, not yet a live bug), but a real trap for a future caller. Resolves the same way _resolve_pkg()
    does, just parameterized instead of reading the EP global, and falls back to the live PKG when the episode
    matches the current one (zero behaviour change for every existing call site)."""
    if episode == EP:
        return PKG
    import glob
    cands = (glob.glob(f"../cb-output/{episode}_*beat_package.json")
             or glob.glob(f"../cb-output/{episode}_*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else PKG

def record_chain_source(scene, code, episode=None):
    """Stamp the upstream ending-frame hash THIS beat's keyframe was just built from — the baseline
    _relock_chain_if_dirty compares against. Call right after a continuation beat's keyframe is (re)built."""
    episode = episode or EP
    import cb_preflight
    d = json.load(open(_pkg_for_episode(episode)))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
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
    import cb_preflight
    try:
        pkg = json.load(open(_pkg_for_episode(episode)))
    except Exception:
        return False
    scene_beats = [b for b in (pkg.get("beats") or pkg.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    scene_beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
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
    locp = _paths.LOCATIONS
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

def export_storyboard(pkg_path, scene_num=None, episode=None):
    """THE GATE-1 EXTERNAL REVIEW DOCUMENT (CLAUDE.md rule 37 / MANIFEST.md, 2026-07-06 — "the storyboard
    exports as a single document for Julian's own creative review outside the studio first... the export
    mechanism itself is not yet built"). Renders one clean Markdown document — a scene, or the whole
    episode when scene_num is None — of exactly the fields Julian's own doctrine says he reads before
    signing Gate 1: storyBeat, want/need/crystalTruth, kidRead/adultRead, the dialogue in order, endState.
    Returns the Markdown text (the caller decides where to write it — see /api/export-storyboard)."""
    episode = episode or EP
    d = json.load(open(pkg_path))
    beats = [b for b in (d.get("beats") or d.get("shots") or [])
             if scene_num is None or str(b.get("sceneNumber")) == str(scene_num)]
    # FIXED 2026-07-08 (independent-review find): a plain lexicographic string sort misorders any scene with
    # 10+ beats ("1.B10" sorts between "1.B1" and "1.B2") — the exact bug class already fixed elsewhere this
    # session (cb_beats.fire_next_beat, cb_previz._beats_for_scene, cb_replicator.walk_scene,
    # cb_director._derive_performance_throughline) via cb_preflight._beat_sort_key. Scene number is cast to int
    # (not string) as the PRIMARY key here — unlike those 4 call sites, this function can run in whole-episode
    # mode across multiple scenes, not just within one already-filtered scene.
    import cb_preflight
    beats.sort(key=lambda b: (int(b.get("sceneNumber") or 0), cb_preflight._beat_sort_key(b.get("beatCode") or "")))
    scenes = {str(s.get("sceneNumber")): s for s in (d.get("scenes") or [])}

    lines = [f"# {episode} — Storyboard for external review",
             "*Exported for reading outside the Studio, per the Gate-1 external review rule "
             "(CLAUDE.md rule 37) — sign Gate 1 only after reading this, not from inside the tool.*", ""]
    last_scene = None
    for b in beats:
        sn = str(b.get("sceneNumber") or "")
        if sn != last_scene:
            sc = scenes.get(sn, {})
            lines.append(f"\n## Scene {sn} — {sc.get('name') or '(unnamed)'}")
            if sc.get("emotionalCore"):
                lines.append(f"*{sc['emotionalCore']}*")
            last_scene = sn
        code = b.get("beatCode") or b.get("shotCode") or "?"
        lines.append(f"\n### {code}")
        if b.get("storyBeat"):
            lines.append(f"**Story:** {b['storyBeat']}")
        if b.get("want") or b.get("need"):
            lines.append(f"**Want / Need:** {b.get('want', '—')} / {b.get('need', '—')}")
        if b.get("crystalTruth"):
            lines.append(f"**Crystal truth:** {b['crystalTruth']}")
        if b.get("kidRead") or b.get("adultRead"):
            lines.append(f"**Kid read / Adult read:** {b.get('kidRead', '—')} / {b.get('adultRead', '—')}")
        dlg = [c.get("dialogue") for c in (b.get("cuts") or []) if c.get("dialogue")]
        if dlg:
            lines.append("**Dialogue:**")
            lines.extend(f"> {d}" for d in dlg)
        if b.get("endState"):
            lines.append(f"**Ends on:** {b['endState']}")
    return "\n".join(lines) + "\n"


def _manifest_gate_scene(scene, gate="1", label=None, list_gaps=False):
    """THE SCENE-LEVEL MANIFEST CHOKE-POINT — the scene-scoped sibling of _manifest_gate_beat (below), which
    already does this same job one level down for the per-beat cascade. FOUND DUPLICATED, HAND-COPIED, ACROSS
    THREE SEPARATE SCENE-LEVEL CALL SITES (approve(), regen(), fire()) — the exact "same choke-point pattern
    re-typed instead of shared" bug class this codebase's own standing rule (CLAUDE.md rule 49/56 — "software-
    wide fixes must not leave a second, silently-drifting copy") already exists to catch; extracted here so a
    future change to this block (a new gate, a wording tweak, a stricter check) lands in ONE place instead of
    three. Returns True if clear to proceed, False (a refusal has already been printed) if not — same bool
    contract as _manifest_gate_beat.

    gate: the raw gate string ("1", "2a", "2b", "3", "4", "5", "1.6") — defaults to "1" to match manifest_ok's
    own default AND regen()'s pre-existing call (which never passed a gate at all, relying on that default).
    Gate "1.6" (the Previz Reel) has no plate/keyframe of its own to check — same manifest scope as Gate 1;
    mapped here exactly once for every caller (approve() used to need "1" OR "1.6" -> "1"; fire() only ever
    reaches this with "1.6" since it exempts "1" itself upstream — folding both into one `in (...)` check is
    safe for both, since fire() never passes "1" here regardless).

    label: what to call the thing being refused in the printed message ("gate {gate}" by default; regen()
    passes its own f"regen of {shot_code}" so its refusal still names the shot, not just the gate).

    list_gaps: approve()'s own richer behaviour — name up to 10 individual BLOCK gaps (with a "cannot arm"
    verb, matching its pre-existing wording exactly) instead of the plain block-count-only "cannot fire" line
    fire()/regen() both use. Kept as a flag rather than forked into a separate function, since every OTHER
    part of the block (the gate mapping, the manifest_ok call, the exception handling) is identical — the one
    genuinely irreducible difference is this one line's shape, not the whole mechanism."""
    _manifest_gate = "1" if gate in ("1", "1.6") else gate
    label = label or f"gate {gate}"
    try:
        import cb_preflight
        ok, block_count, gaps = cb_preflight.manifest_ok(PKG, scene=scene, episode=EP, gate=_manifest_gate)
        if not ok:
            if list_gaps:
                named = [g.line().strip() for g in gaps if g.kind == "BLOCK"][:10]
                print(f"✗ REFUSED — {EP} scene {scene} {label} cannot arm: {block_count} manifest BLOCK(s), "
                      f"including:\n  " + "\n  ".join(named)
                      + ("\n  ... (see: python3 cb_preflight.py --scene=" + str(scene) + ")" if block_count > 10 else ""),
                      flush=True)
            else:
                print(f"✗ REFUSED — {EP} scene {scene} {label} cannot fire: {block_count} manifest BLOCK(s) "
                      f"outstanding (run: python3 cb_preflight.py --scene={scene})", flush=True)
            return False
    except Exception as e:
        print(f"  (manifest check could not run — {str(e)[:120]} — proceeding without it; fix cb_preflight.py)", flush=True)
    return True

def approve(gate, scene, reviewed_by="Julian"):
    """Returns True if the gate was actually signed, False if refused (manifest BLOCK). Deliberately never
    calls sys.exit itself — this function is called both as a CLI entry point (see __main__, which DOES exit
    non-zero on a False return) and in-process by other Python code (test_gate_cascade.py's own approve()
    calls, in particular) — an in-process sys.exit() here would kill the calling process outright instead of
    just failing this one call.

    reviewed_by (2026-07-08, Production Management panel finding — "no reviewer/role concept in code at
    all"): records WHO signed this gate, not just that it was signed. Not a real auth system (this is a
    1-2 person operation, that would be disproportionate) — just an identity string on the lock, so the
    infrastructure exists BEFORE a second reviewer ever joins rather than being retrofitted after. Every
    reader of sd[gate] elsewhere in this file/serve.py/app.html already does a plain truthy check
    (confirmed: `not sd.get(gate)`, `bool(d.get(...))`, JS `!!lk[gate]`) — a non-empty dict is truthy in
    both Python and JS, so changing the VALUE shape here needed zero reader-side changes."""
    gate = str(gate).lower()
    # FIXED 2026-07-11 (full-codebase audit): fire() already guards `gate not in GATES`; approve() had no
    # equivalent, so a typo'd or made-up gate string (e.g. "approve foo 1") silently wrote an unvalidated
    # sign-off into locked.json with no error surfaced.
    if gate not in GATE_SEQ:
        print(f"unknown gate '{gate}' — use one of {GATE_SEQ}"); return False
    # GATE ORDER (2026-07-08, independent-review find): fire() already refuses to fire a gate whose predecessor
    # isn't signed off (_prev_gate/_approved, both defined above and already proven correct via fire()'s own
    # use of them) — approve() never checked this at all, so a gate could be SIGNED OFF with none of its
    # predecessors ever fired or approved (e.g. approve("5", scene) would succeed today as long as the scene's
    # beat-package DATA has zero manifest BLOCKs, with Gates 1/1.6/2a/2b/3/4 never touched). Same reused logic,
    # no new mechanism invented.
    prev = _prev_gate(gate)
    if prev and not _approved(scene, prev):
        print(f"⛔ Gate {prev} not signed off for {EP} scene {scene} — approve it before approving gate {gate}:")
        print(f"     python3 cb_pipeline.py approve {prev} {scene}")
        return False
    # THE MANIFEST (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's ruling — "Gate N cannot arm... without
    # both manifests green"): every gate sign-off, not just Gate 1, is refused while a BLOCK-kind gap exists in
    # this scene's scope. The plate is never part of what BLOCKs (its own QA, cb_qa.check_plate, already runs
    # automatically at Gate-2a build time) — the `gate` param is threaded through for forward compatibility only.
    # (shared choke-point: _manifest_gate_scene, above — list_gaps=True is approve()'s own richer behaviour.)
    if not _manifest_gate_scene(scene, gate=gate, list_gaps=True):
        return False
    # THE CONTINUITY GATE (2026-07-14, closing a real gap found by the full-pipeline verification audit):
    # cb_continuity.run() has always FIRED at every generative gate (fire()'s own _GENERATIVE loop, below)
    # and genuinely distinguishes hard BLOCK from advisory NOTE — but nothing ever READ its return value.
    # A real canon violation (a Keen-wristband regression, a vision citing a scene with no master yet, the
    # episode's day running backwards) could be flagged there and then silently signed off anyway, since
    # fire()'s own call only ever prints the findings for a human to notice, never gates on them. This is
    # the SAME "computed but discarded" bug class as the manifest checks this pipeline already gates on —
    # closed the identical way, at the identical choke point (approve(), the actual human sign-off).
    # Scoped conservatively: only gates 2a onward (Gate 1/1.6 approve the STORY, before any visual master
    # exists for the checker to reason about — the vision/recurring/stateful-location rules below all key
    # off master/plate file existence, so checking them at Gate 1/1.6 would just report "not built yet" for
    # everything, every time, which is not useful new information at that stage). Only a BLOCK whose own
    # `scene` field matches the scene being approved, OR a genuinely global finding (scene=="-", e.g. a
    # canon-sync drift), gates this specific approval — cb_continuity.check() is deliberately CROSS-scene
    # (its own docstring: "catches what a single-scene build can't see"), so a real BLOCK about a DIFFERENT
    # scene must not block signing off THIS one; that finding gates the OTHER scene's own approval instead,
    # when its turn comes.
    if gate not in ("1", "1.6"):
        _cblocks = [f for f in cb_continuity.check(PKG, EP) if f["level"] == "BLOCK" and f["scene"] in ("-", str(scene))]
        if _cblocks:
            print(f"⛔ Gate {gate} refused for {EP} scene {scene} — {len(_cblocks)} continuity BLOCK(s):")
            for f in _cblocks:
                print(f"     [BLOCK] scene {f['scene']} shot {f['shot']}: {f['msg']}")
            return False
    # THE CONTEXT GATE — added 2026-07-15 (guardrail-fidelity audit): cb_context.run() has always fired at
    # every generative gate (fire()'s own pre-flight call, below) purely as printed, discarded output —
    # exactly the "computed but discarded" gap already closed for cb_continuity above, just missed for this
    # sibling check. cb_context.check() verifies the beat's own declared reference stack (hero items named
    # in the script but not reference-locked, a character with no canon anchor) is actually resolvable before
    # a real paid render fires — confirmed live it already computes real BLOCK findings on the current package
    # (scenes 2/3/4). Same scope/exemption as the continuity gate above (never at Gate 1/1.6, before any
    # reference stack exists to check); already single-scene-scoped by its own `scene=` parameter, so no
    # cross-scene filtering is needed the way cb_continuity's global findings require.
    if gate not in ("1", "1.6"):
        _cxblocks = [f for f in cb_context.check(PKG, EP, str(scene)) if f["level"] == "BLOCK"]
        if _cxblocks:
            print(f"⛔ Gate {gate} refused for {EP} scene {scene} — {len(_cxblocks)} context BLOCK(s):")
            for f in _cxblocks:
                print(f"     [BLOCK] {f['shot']}: {f['msg']}")
            return False
    d = _lock(); sd = d.setdefault(EP, {}).setdefault(str(scene), {})
    sd[gate] = {"approved": True, "reviewed_by": reviewed_by, "at": datetime.datetime.now().isoformat()}
    if gate == "1":
        sd["1_fp"] = _scene_beats_fingerprint(PKG, scene)   # the cascade-relock baseline (see _relock_if_stale)
    _save(d)
    if gate == "2a":
        _lock_plate_as_master(scene)
    print(f"✓ approved {EP} scene {scene} gate {gate} — next gate unlocked")
    return True

def unapprove(gate, scene):
    """REVERSE a sign-off so you can go back and alter an earlier step. Removes THIS gate's sign-off AND every gate
    after it (they depend on it), so un-signing Step 1 (2a) also re-locks Step 2 (2b). If the FOUNDATION (2a) or the
    plan (1) is un-signed, the scene master is reset to None — the plate is no longer a locked foundation, so a stale
    plate can never satisfy Gate 2b, and you can rebuild/alter the foundation cleanly before re-signing."""
    gate = str(gate).lower(); scene = str(scene)
    # FIXED 2026-07-11 (full-codebase audit): same guard as approve()'s own fix above — a bogus gate string
    # was already mostly harmless here (GATE_SEQ-membership checks below just no-op), but printed a misleading
    # "un-signed" success message instead of a clear error.
    if gate not in GATE_SEQ:
        print(f"unknown gate '{gate}' — use one of {GATE_SEQ}"); return False
    d = _lock(); sd = d.setdefault(EP, {}).setdefault(scene, {})
    # FIXED 2026-07-08 (contradiction sweep): this used to hand-duplicate GATE_SEQ's value as a fresh local
    # literal instead of referencing the module constant already used idiomatically elsewhere in this same
    # file (_prev_gate) — a third, undocumented copy beyond the two cross-file ones the header comment at
    # line 24 already warns about. A future edit to GATE_SEQ (e.g. inserting a new gate) would have updated
    # this docstring's own review copy while silently leaving this cascade-clear loop on the stale sequence.
    if gate in GATE_SEQ:
        for g in GATE_SEQ[GATE_SEQ.index(gate):]:   # this gate + everything downstream
            sd.pop(g, None)
    sd.pop("2", None)                          # drop any legacy whole-gate-2 flag too
    if gate == "1":
        sd.pop("1_fp", None)                   # drop the cascade-relock baseline too — a fresh approve() recomputes it
    # ── TICKET 4 reconciliation — a scene-gate unapprove MUST also clear the DEPENDENT per-beat cascade approvals
    #    (locked[EP][scene]["beats"][code]) for THIS scene ONLY; otherwise a stale beats{} approval survives an
    #    un-signed gate (a keyframe/clip still reads "approved" after its gate was reopened). Each gate clears the
    #    beat stages that it + everything downstream invalidate; scope is sd["beats"] — this scene, never another.
    # FIXED 2026-07-08 (independent-review find): "1.6" (the Previz Reel) was missing from this map entirely —
    # un-signing it correctly cascade-cleared the scene-level 2a/2b/3/4/5 sign-offs (via the GATE_SEQ loop above)
    # but left every beat's own per-beat keyframe/clip locks stuck approved, inconsistent with what un-signing "1"
    # itself already does. "1.6" sits between "1" and "2a" with nothing beat-level of its own produced in between
    # (no plate, no keyframe render happens at 1.6) — so un-signing it invalidates the SAME beat stages un-signing
    # "1" does, reusing the already-defined _BEAT_STAGES constant rather than inventing a new tuple.
    _gate_clears = {"1": _BEAT_STAGES, "1.6": _BEAT_STAGES, "2a": ("keyframe", "clip"), "2b": ("keyframe", "clip"),
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
        locp = _paths.LOCATIONS
        if os.path.exists(locp):
            L = json.load(open(locp)); s = L.get(EP, {}).get(scene, {})
            if s.get("master") is not None:
                s["master"] = None; json.dump(L, open(locp, "w"), indent=1, ensure_ascii=False)
                print(f"  ✓ scene {scene} master reset (foundation un-signed) — Gate 2b re-locked", flush=True)
    print(f"↺ un-signed {EP} scene {scene} gate {gate} (+ all downstream) — alter it, then re-sign.", flush=True)

# ── GATE-STATE RECONCILIATION (2026-07-14, Julian's front-to-back wiring pass — "we're putting a lot of
# stuff into it, but we're not netting it all together... those files that sit there with zero firing"):
# locked.json's scene-level sign-offs are written ONLY by approve() above — but real production work
# (the Previz Reel, the plate, keyframes, rendered clips, per-beat approval sidecars) has always progressed
# through its own separate, independently-tracked mechanisms (cb_previz.py, _lock_plate_as_master, cb_scene's
# keyframe build, beat_approval_status). Nothing ever kept the two in sync — confirmed live: Scene 1 has a
# real previz reel, a locked plate, a real 1.B1 keyframe, and four rendered+QA'd clips (one, 1.B2, with an
# explicit Julian approval sidecar) — yet locked.json shows `{"beats": {}}`, not one gate signed. This is
# the read/write pair that closes that gap, permanently, for every future scene, not just this one.
def gate_state_report(scene, episode=None):
    """READ-ONLY. For each gate in GATE_SEQ, compares locked.json's sign-off against REAL evidence on disk —
    the artifact each gate's own deliverable actually requires. Returns an ordered dict
    {gate: {"locked": bool, "ready": bool, "detail": str}}. "ready" cascades — a gate can only be ready if
    every gate before it is also ready — matching GATE_SEQ's own sequential-gate contract (approve() already
    refuses out-of-order sign-off; this mirrors that, read-only, so a report never claims something's ready
    that approve() would actually refuse).

    Gate 3's readiness deliberately does NOT mean "every beat has a rendered clip with clean QA" — it means
    every beat has been through beat_approval_status's real, Julian-recorded verdict ("approved", never
    merely "pending"/"unrendered"). CLAUDE.md's own Step 7 doctrine: an unreviewed take is pending, not
    approved — Julian's Eye is the one gate no machine owns, and a clean QA pass is not a substitute for it."""
    episode = episode or EP
    scene = str(scene)
    d = _lock()
    sd = d.get(episode, {}).get(scene, {})
    pkg = json.load(open(_pkg_for_episode(episode)))
    import cb_preflight
    beats = [b for b in (pkg.get("beats") or pkg.get("shots") or []) if str(b.get("sceneNumber")) == scene]
    beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
    report = {}

    # Gate 1 — the storyboard itself: real beats authored, clean against the manifest's own gate-1 scope.
    ok1, block_count1, _ = cb_preflight.manifest_ok(_pkg_for_episode(episode), scene=scene, episode=episode, gate="1")
    report["1"] = {"locked": bool(sd.get("1")), "ready": bool(beats) and ok1,
                    "detail": f"{len(beats)} beat(s) authored, {block_count1} manifest BLOCK(s)"}

    # Gate 1.6 — the Previz Reel artifact (cb_previz.assemble_scene_previz's own output path).
    previz = f"media/{episode}_Scene{scene}_previz.mp4"
    report["1.6"] = {"locked": bool(sd.get("1.6")), "ready": report["1"]["ready"] and os.path.exists(previz),
                      "detail": f"previz reel {'present' if os.path.exists(previz) else 'MISSING'} ({previz})"}

    # Gate 2a — the scene plate (the same file _lock_plate_as_master reads at real approve("2a", ...) time).
    plate = f"media/{episode}_S{scene}_plate.png"
    report["2a"] = {"locked": bool(sd.get("2a")), "ready": report["1.6"]["ready"] and os.path.exists(plate),
                     "detail": f"plate {'present' if os.path.exists(plate) else 'MISSING'} ({plate})"}

    # Gate 2b — every beat that OWNS a keyframe (opener/vision only — rule 64, THE RELAY CHAIN — a
    # continuation beat never gets its own Gate-2b keyframe by design) must have that file on disk.
    missing_kf = []
    for b in beats:
        code = b.get("beatCode") or b.get("shotCode"); slug = b.get("slug", (code or "").replace(".", "_"))
        try:
            _, _, info = cb_scene.keyframe_for(beats, code, episode)
            status = (info.get("chain") or {}).get("status")
        except Exception:
            status = None
        if status in ("first", "vision") and not os.path.exists(f"media/{episode}_{code}_{slug}.png"):
            missing_kf.append(code)
    report["2b"] = {"locked": bool(sd.get("2b")), "ready": report["2a"]["ready"] and not missing_kf,
                     "detail": "all owning keyframes present" if not missing_kf else f"missing keyframe(s): {', '.join(missing_kf)}"}

    # Gate 3 — every beat in the scene carries a REAL, recorded Julian approval (see docstring above).
    not_approved = []
    for b in beats:
        code = b.get("beatCode") or b.get("shotCode"); slug = b.get("slug", (code or "").replace(".", "_"))
        status, _ = cb_beats.beat_approval_status(episode, code, slug)
        if status != "approved":
            not_approved.append(f"{code}:{status}")
    report["3"] = {"locked": bool(sd.get("3")), "ready": report["2b"]["ready"] and not not_approved,
                    "detail": "every beat approved" if not not_approved else f"not yet approved: {', '.join(not_approved)}"}

    # Gate 4/5 have no independent artifact this function checks (retake sidecars / the post master) — their
    # readiness is simply their own prerequisite gate, same as approve()'s prev-gate chain requires anyway.
    report["4"] = {"locked": bool(sd.get("4")), "ready": report["3"]["ready"], "detail": "prerequisite: gate 3"}
    report["5"] = {"locked": bool(sd.get("5")), "ready": bool(sd.get("4")), "detail": "prerequisite: gate 4 signed"}
    return report


def reconcile_gate_state(scene, episode=None, apply=False, reviewed_by="Julian"):
    """THE WRITE SIDE of gate_state_report. Walks GATE_SEQ in order; for every gate that is READY (per real
    evidence) but not yet LOCKED, either reports what WOULD be signed (apply=False, the default — a dry run,
    changes nothing) or actually calls the real approve() for it (apply=True — never writes locked.json
    directly, so every existing guard — manifest_ok, the prev-gate chain, the Gate-1 cascade fingerprint —
    stays fully live). Stops at the first not-ready gate; a later-ready gate behind an earlier ungated one is
    correctly left alone, matching GATE_SEQ's own sequential contract (never skips ahead)."""
    episode = episode or EP
    report = gate_state_report(scene, episode)
    applied, blocked_at = [], None
    for gate in GATE_SEQ:
        row = report[gate]
        if row["locked"]:
            continue
        if not row["ready"]:
            blocked_at = gate
            break
        if apply:
            if not approve(gate, scene, reviewed_by=reviewed_by):
                blocked_at = gate   # approve() itself refused (manifest/prev-gate) — stop, don't skip ahead
                break
            applied.append(gate)
            report = gate_state_report(scene, episode)   # re-read — approve() may have changed downstream state
        else:
            applied.append(gate)   # dry run: record what WOULD be applied, keep walking the rest

    print(f"\n=== gate-state reconciliation — {episode} scene {scene} ({'APPLY' if apply else 'DRY RUN'}) ===")
    for gate in GATE_SEQ:
        row = report[gate]
        if row["locked"]:
            mark = "✓ locked"
        elif gate in applied:
            mark = "✓ signed now" if apply else "→ would sign"
        elif row["ready"]:
            mark = "· ready"
        else:
            mark = "✗ not ready"
        print(f"  gate {gate:>3}: {mark:<14} — {row['detail']}")
    if blocked_at:
        print(f"  stopped at gate {blocked_at} — not enough evidence yet.")
    if apply and applied:
        print(f"  ✓ applied: {', '.join(applied)}")
    elif not apply and applied:
        print(f"  (dry run — re-run with --apply to actually sign {', '.join(applied)})")
    return {"report": report, "applied": applied, "blocked_at": blocked_at}


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
    target (keyframe only) = 'both' | 'start' | 'end'. Returns True if it actually fired, False on any refusal
    (never sys.exit itself — see approve()'s docstring for why)."""
    need = "2b" if kind == "clip" else "2a"   # a keyframe regen needs the FOUNDATION (2a) signed; a clip regen needs the keyframes (2b)
    if not _approved(scene, need):
        print(f"⛔ Gate {need} not signed off for {EP} scene {scene} — sign it off before regenerating ({kind}).", flush=True); return False
    # THE MANIFEST (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06): a regen is a fire, same as any other arming
    # path — refused on a red manifest for this scene, same choke-point as fire()/approve().
    # (shared choke-point: _manifest_gate_scene, above — no gate of its own, so the "1" default scope is used,
    # matching this call's pre-existing manifest_ok(...) call, which never passed a gate= either.)
    if not _manifest_gate_scene(scene, label=f"regen of {shot_code}"):
        return False
    save_note(shot_code, note)
    s = next((x for x in _shots(scene) if x["shotCode"] == shot_code), None)
    if not s:
        print(f"REGEN: shot {shot_code} not found in scene {scene}"); return False
    # STALENESS ON REGEN (2026-07-08, independent-review find): a regen replaces content a downstream gate/
    # per-beat lock may already have signed off, but this used to leave that sign-off reading "approved" against
    # footage that no longer exists — the same staleness class _relock_if_stale already exists to prevent for
    # Gate-1 edits, just never triggered here. Reuses the existing, already-tested unapprove() primitive rather
    # than inventing new logic — it cascade-clears the scene gate + every per-beat lock that gate's own
    # _gate_clears mapping says depends on it.
    if kind == "clip":
        if _approved(scene, "3"):
            unapprove("3", scene)
            print(f"  ⚠ REGEN of {shot_code}'s clip forced a relock of Gate 3 — every downstream gate + "
                  f"per-beat lock reset", flush=True)
        # The per-beat "sign off this beat's clip" flow is independent of the scene-level Gate 3 sign-off (a
        # beat can be individually approved via approve_beat without the whole scene's Gate 3 ever being
        # signed) — clear THIS beat's own clip lock unconditionally, not only when unapprove("3", ...) fired.
        _set_beat_lock(scene, shot_code, "clip", False)
        # ── UNIFIED RENDER PATH — Gate 3 ≡ clip regen (they MUST stay on the same path) ──────────────────────────
        # A clip regen renders through the EXACT same path as Gate 3: cb_beats.run → cb_segprompt.shipped_prompt →
        # cb_gen.generate_video_seedance_ref. That path always recompiles fresh from the beat's own cuts[] (the
        # @Audio1 ElevenLabs V3 lip-sync track and Seedance-scored SFX + MUSIC ride along). If Gate 3 and clip
        # regen ever diverge, a re-rendered beat comes from a DIFFERENT system than the rest of the scene and POST
        # stitches a mismatched take. (Was cb_dialogue.run / build_ref2vid_prompt — SFX-only, NO music — now
        # DEPRECATED; see cb_dialogue.py.) The correction `note` is recorded via save_note() above (context only,
        # not sent to the model); per-render prompt changes now go through editing the beat's own cuts[] in the
        # Studio (seedancePromptOverride RETIRED 2026-07-07 — it was silently overwritten by the v5 recompile the
        # moment gate3_prepare returned, for every beat that has a cb_segprompt segment).
        print(f"REGEN clip {shot_code} via the Gate-3 beat path (cb_beats.run codes=[{shot_code}]) | note: {note[:80]!r}", flush=True)
        cb_beats.run(PKG, scene, EP, codes=[shot_code])
    else:
        if _approved(scene, "2b"):
            unapprove("2b", scene)
            print(f"  ⚠ REGEN of {shot_code}'s keyframe forced a relock of Gate 2b — every downstream gate + "
                  f"per-beat lock reset", flush=True)
        cb_scene.regen_shot(PKG, scene, shot_code, EP, note, target)
    return True

def build_master(scene, rounds=2):
    """STRUCTURAL master-build: (re)build the scene's establishing MASTER with the full reference + identity lock,
    then VERIFY it visually before the scene derives from it. The foundation must be right — everything inherits it."""
    shots = _shots(scene)
    if not shots:
        print(f"⛔ BUILD MASTER — {EP} scene {scene} has no beats yet (check the scene number, or fire Gate 1 first).",
              flush=True)
        return False
    # FIXED 2026-07-11 (full-codebase audit): a live, billed generation entry point with no manifest check at
    # all, unlike every sibling generative function in this file (rebuild/regen/fire all call this same
    # choke-point). A scene with an outstanding BLOCK could fire real image generation through this command.
    if not _manifest_gate_scene(scene, label="build-master"):
        return False
    # FIXED 2026-07-14 (full-pipeline verification audit — see regen_anchor's identical note above, the same
    # gate-order gap the 2026-07-11 sweep missed): this function regenerates the scene's establishing MASTER —
    # Gate 2a's own foundation content — so it needs the same "1.6" predecessor gate signed that firing 2a
    # itself requires, not the (not-yet-existing) "2a" it's producing.
    if not _approved(scene, "1.6"):
        print(f"  ⛔ Gate 1.6 (previz) not signed off for {EP} scene {scene} — sign it off before building the "
              f"master.", flush=True)
        return False
    code = shots[0]["shotCode"]
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
            print(f"⛔ GATE 1 — no script for {EP}. Upload the script in the studio first, then fire Gate 1."); return False
        script = scripts[0]
        title = os.path.basename(script)[len(EP) + 1:].rsplit(".", 1)[0].replace("_", " ")
        print(f"GATE 1 — THE DIRECTOR: no shot package yet — reading the script and breaking it down "
              f"({os.path.basename(script)}). This is the real script analysis; it takes a few minutes.", flush=True)
        # THE GATE-0 PROVENANCE HARD BLOCK (2026-07-14): cb_director.direct() itself refuses (a plain
        # RuntimeError, never sys.exit) if this script has no matching Gate-0 (Writers' Room) sidecar —
        # caught here and turned into the same clean refusal/return-False convention gate4()/gate5()
        # already use, rather than letting a raw traceback escape through fire()'s own "never sys.exit
        # itself" promise.
        try:
            r = cb_director.direct(script, EP, title)
        except RuntimeError as e:
            print(f"⛔ {e}", flush=True)
            return False
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
    return True

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

def previz_reel(scene):
    """GATE 1.6 — THE PREVIZ REEL (cb_previz.py): scratch VO + placeholder/keyframe cards, hard-cut together,
    near-zero cost. Lets Julian hear the scene's dialogue timing/rhythm before Gate 2a's plate — the first
    real paid render — ever fires. Not a final take of anything; see cb_previz.py's own module docstring."""
    print(f"GATE 1.6 — THE PREVIZ REEL, {EP} scene {scene}:", flush=True)
    out = cb_previz.assemble_scene_previz(PKG, scene, episode=EP)
    if not out:
        print(f"⛔ GATE 1.6 — no previz produced for {EP} scene {scene} (no beats found?)", flush=True)
        return False
    # THE PIXAR-CRAFT SCORE (2026-07-14, CLAUDE.md rule 80/85, corrected same day by the full-pipeline
    # verification audit): the original "had ZERO live callers anywhere in the pipeline until this line"
    # claim was already false the moment it was written — cb_previz.assemble_scene_previz (called above) had
    # ALSO been calling craft_score_for_scene internally, so every real Gate-1.6 fire ran the real-cost,
    # two-LLM-call craft judge TWICE with the second write clobbering the first. That internal call is now
    # removed; THIS is the sole call site, matching test_cb_previz.py's own assemble-then-craft-score
    # ordering test. FAIL-SOFT: craft_score_for_scene never raises (it catches internally and returns None)
    # — this call is deliberately NOT wrapped in its own try/except, since a previz reel that built
    # successfully must always return True regardless of whether the advisory score could be computed.
    cb_previz.craft_score_for_scene(PKG, scene, episode=EP)
    return True

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
    return True

def _print_keyframe_qa(scene):
    """FOUNDATION QA — the keyframes are what the WHOLE clip is built from, so audit every beat's opening frame
    against the Definition of Done. REPORT-ONLY (never auto-overwrites a good frame); you review + regen the
    flagged in the studio. EXTRACTED 2026-07-11 (full-codebase audit — duplication): this exact block used to
    be copy-pasted verbatim in both coverage() and rebuild(), risking the two silently drifting apart."""
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

def coverage(scene):
    """GATE 2B — derive every shot from the FROZEN master (the scene plate) + the character turnarounds, built as a
    sequential CHAIN (start -> end -> next start off the prior end). NO QA pass — review in the studio. Requires 2A."""
    print(f"GATE 2B — COVERAGE (chained build, NO QA), {EP} scene {scene}:", flush=True)
    if not _approved(scene, "2a"):   # the LIVE foundation sign-off, independent of any leftover master on disk
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — build + sign off the foundation first.", flush=True); return False
    sc = P.scene_cfg(EP, str(scene))
    if not (sc.get("master") and os.path.exists(sc["master"])):
        print(f"  ⛔ no scene plate (master) — fire gate 2a first.", flush=True); return False
    cb_scene.run(PKG, scene, EP)  # chained build off the Director's words + library turnarounds
    _print_keyframe_qa(scene)
    print(f"=== GATE 2B done — {EP} scene {scene} built + QA'd; review the flagged, then sign off ===", flush=True)
    return True

def rebuild(scene):
    """CLEAN REBUILD of ALL keyframes for the scene — delete every stale opening frame and re-render each beat FRESH
    (force, no resume-keep). Use after un-signing Gate 2B / changing the template or references. Requires 2A signed."""
    print(f"GATE 2B — CLEAN REBUILD (all keyframes, force), {EP} scene {scene}:", flush=True)
    if not _approved(scene, "2a"):
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — sign off the foundation first.", flush=True); return False
    sc = P.scene_cfg(EP, str(scene))
    if not (sc.get("master") and os.path.exists(sc["master"])):
        print(f"  ⛔ no scene plate (master) — fire gate 2a first.", flush=True); return False
    # FIXED 2026-07-07 (contradiction-audit, the same sweep-the-pattern find as _manifest_gate_beat's own
    # 2026-07-07 fix): rebuild() renders every keyframe in the scene fresh but never checked the manifest —
    # a beat with an outstanding BLOCK (e.g. an invented dialogue line) could still have its keyframe rebuilt.
    # gate="2b" (2026-07-09): this is the keyframe-build stage, same as build_beat's own call below.
    if not _manifest_gate_beat(scene, None, gate="2b"):
        return False
    # STALENESS ON REBUILD (2026-07-08, independent-review find): rebuilding every keyframe in the scene
    # replaces content Gate 2b (and everything downstream) may already have signed off, but this used to leave
    # that sign-off reading "approved" against frames that no longer exist. Reuses the existing, already-tested
    # unapprove() primitive — it cascade-clears Gate 2b + 3 + 4 + 5 AND every per-beat keyframe/clip lock in the
    # scene, exactly what "the same template/references changed for every beat" warrants.
    if _approved(scene, "2b"):
        unapprove("2b", scene)
        print(f"⚠ REBUILD forced a relock of Gate 2b — every downstream gate + per-beat lock reset", flush=True)
    cb_scene.run(PKG, scene, EP, force=True)   # force = clean each stale keyframe, then rebuild ALL fresh
    _print_keyframe_qa(scene)
    print(f"=== CLEAN REBUILD done — {EP} scene {scene} all keyframes rebuilt fresh; review + sign off ===", flush=True)
    return True

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
    # FIXED 2026-07-11 (full-codebase audit): a live, billed generation entry point (plate or charsheet) with
    # no manifest check at all, unlike every sibling generative function in this file.
    if not _manifest_gate_scene(scene, label=f"regen-anchor ({which})"):
        return False
    # FIXED 2026-07-14 (full-pipeline verification audit — this was the ONE gate-order bypass the 2026-07-11
    # sweep above missed; CLAUDE.md rule 66's own text claimed all 8 named functions got this fix, this one
    # and build_master below were the two it actually didn't reach): the plate/charsheet ARE Gate 2a's own
    # foundation content — the same bootstrap reasoning that lets fire() generate gate "2a" itself off only
    # "1.6" being signed (never "2a", which doesn't exist yet) applies here identically, since this function
    # re-rolls that exact same foundation content on demand.
    if not _approved(scene, "1.6"):
        print(f"  ⛔ Gate 1.6 (previz) not signed off for {EP} scene {scene} — sign it off before regenerating "
              f"the foundation.", flush=True)
        return False
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

def _manifest_gate_beat(scene, code, gate="1"):
    """FIXED 2026-07-07 (front-to-back audit): rule 37's own text names manifest_ok as the choke-point for
    'every Studio button that fires or approves a gate' — but the PER-BEAT cascade (build_beat/gen_audio/
    render_beat, exposed by serve.py's /api/gen-keyframe, /api/gen-audio, /api/render-beat) never called it
    at all, only the whole-scene gate3()/regen() path did. A beat with an outstanding manifest BLOCK could
    still have its keyframe built, its audio generated, or its clip rendered through the per-beat UI buttons.
    Returns True if clear to proceed, False (already printed a refusal) if not.

    gate (2026-07-09, cross-call-site-consistency finding): every OTHER manifest_ok caller in this codebase
    passes the real production-stage gate it's arming (_manifest_gate_scene's own "1"/"2a"/"2b"/"3"/... map,
    cb_beats.fire_next_beat's "3", cb_replicator.walk_scene's "3") — this one silently defaulted to "1"
    regardless of caller. Zero behaviour change today (cb_preflight.check_scene_technical's own docstring:
    "the gate param... does not currently change this function's behaviour") — this only matters the day that
    documented future gate-scoped behaviour (e.g. a plate check gated on gate>=2) actually ships, at which
    point a mismatched gate here would silently mis-scope the check. Defaults to "1" so an un-migrated caller
    is unaffected."""
    try:
        import cb_preflight
        ok, block_count, _ = cb_preflight.manifest_ok(PKG, scene=scene, episode=EP, gate=gate)
        if not ok:
            print(f"  ⛔ REFUSED — {block_count} manifest BLOCK(s) outstanding for {EP} scene {scene}; "
                  f"never arms on a red manifest (run: python3 cb_preflight.py --scene={scene})", flush=True)
            return False
    except Exception as e:
        print(f"  (manifest check could not run — {str(e)[:120]} — proceeding without it; fix cb_preflight.py)", flush=True)
    return True

def build_beat(scene, code, chain_from=None):
    """Build ONE beat's opening keyframe (CASCADE unit). chain_from = the previous beat's APPROVED keyframe path."""
    # Returns False on manifest refusal, or None on a genuine build failure (cb_scene.build_one_beat returned
    # nothing) — unlike gen_audio, there is no valid "None means success" case here, so __main__'s build-beat
    # dispatch correctly uses a plain falsy check (`if not build_beat(...)`), not the `is False`-specific
    # distinction gen_audio's dispatch needs.
    # gate="2b" (2026-07-09): this fires the Gate-2b keyframe build.
    if not _manifest_gate_beat(scene, code, gate="2b"):
        return False
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass): this whole per-beat cascade (build_beat,
    # gen_audio, render_beat, approve_beat, relay_prepare, relay_approve below) only ever checked manifest
    # CONTENT completeness, never the scene's actual GATE_SEQ sign-off state — unlike rebuild()/regen() in
    # this same file, which both call _approved(). A direct CLI/automation call bypassed gate order entirely;
    # serve.py's HTTP layer patched this for SOME of these endpoints, inconsistently, but cb_pipeline.py itself
    # never enforced it for any caller that imports it directly. A keyframe needs the FOUNDATION (2a) signed.
    if not _approved(scene, "2a"):
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — sign it off before building a keyframe.", flush=True)
        return False
    kf = cb_scene.build_one_beat(PKG, scene, code, EP, chain_from=(chain_from or None))
    if kf:
        record_chain_source(scene, code)   # FRAME CHAIN doctrine baseline — see _relock_chain_if_dirty
    print(f"KEYFRAME={kf}", flush=True)
    return kf

def gen_audio(scene, code):
    """Build THIS beat's V3 dialogue track and report its measured duration (drives the per-beat HOLD math)."""
    # `is False` is the manifest-refusal signal specifically — a wordless beat legitimately returns None further
    # down ("that's valid, not an error"), so refusal must use a DIFFERENT sentinel than the wordless-success
    # path, or __main__'s exit-code check would wrongly treat a valid wordless beat as a failure.
    # gate="3" (2026-07-09): this is the Gate-3 voice pass (Stage 3).
    if not _manifest_gate_beat(scene, code, gate="3"):
        return False
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass, see build_beat's own note above): the voice
    # pass (Stage 3) requires the FOUNDATION (2a) signed — matching serve.py's own /api/gen-audio precondition.
    if not _approved(scene, "2a"):
        print(f"  ⛔ Gate 2A (foundation) not signed off for {EP} scene {scene} — sign it off before generating audio.", flush=True)
        return False
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
        # FIXED 2026-07-12 (loose-ends pass): was a hand-rolled ffprobe subprocess call, duplicated across
        # 6 files — cb_post._dur() (already imported above) is the canonical probe.
        dur = round(cb_post._dur(track), 2)
    _set_beat_lock(scene, code, "audio", True)       # voices are AUTOMATIC — generated + locked, no manual listen / sign-off
    print(f"AUDIO_DUR={dur}", flush=True)
    print(f"TRACK={track}", flush=True)
    print("  ✓ audio auto-locked", flush=True)
    return track

def render_beat(scene, code):
    """Render ONE beat as its Seedance take (the Gate-3 beat method, scoped to a single beat)."""
    # gate="3" (2026-07-09): this is the actual Gate-3 render/launch step.
    if not _manifest_gate_beat(scene, code, gate="3"):
        return False
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass, see build_beat's own note above): a clip
    # render requires the KEYFRAMES (2b) signed — matching serve.py's own /api/render-beat precondition.
    if not _approved(scene, "2b"):
        print(f"  ⛔ Gate 2B (keyframes) not signed off for {EP} scene {scene} — sign it off before rendering a clip.", flush=True)
        return False
    clips = cb_beats.run(PKG, scene, EP, codes=[code])
    clip = clips[0] if clips else None
    _set_beat_lock(scene, code, "audio", True)   # the clip render generates the V3 voice inline — audio is AUTOMATIC
    print(f"CLIP={clip}", flush=True)
    return clip

def approve_beat(scene, code, stage, value=True):
    """Lock (value=True) or UNLOCK (value=False) ONE beat's ONE stage (audio|keyframe|clip). On a keyframe APPROVAL,
    print the NEXT beat in scene order so the studio can auto-fire the chain."""
    # FIXED 2026-07-07 (contradiction-audit): a scene-level approve() has always refused to arm on a red
    # manifest; this per-beat sign-off never did, despite being the same class of action (locking in a stage as
    # done). Gated only on value=True (LOCKING) — unlocking, like the scene-level unapprove(), is always a safe,
    # reversible "go back and fix it" action and stays ungated.
    # gate (2026-07-09): derived from the stage actually being locked — "keyframe" is the Gate-2b sign-off,
    # anything else (audio/clip) is the Gate-3 sign-off.
    if value and not _manifest_gate_beat(scene, code, gate=("2b" if str(stage).lower() == "keyframe" else "3")):
        return False
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass): LOCKING a stage requires the corresponding
    # scene gate signed first, matching gen-keyframe/render-beat's own precondition (2a for keyframe/audio,
    # 2b for clip) — unlocking (value=False) stays ungated, same as the scene-level unapprove().
    if value:
        _need = "2a" if str(stage).lower() in ("keyframe", "audio") else "2b"
        if not _approved(scene, _need):
            print(f"  ⛔ Gate {_need.upper()} not signed off for {EP} scene {scene} — sign it off before approving this beat's {stage}.", flush=True)
            return False
    _set_beat_lock(scene, code, stage, value)
    print(f"{'✓ approved' if value else '↺ unlocked'} {EP} scene {scene} beat {code} stage {stage}", flush=True)
    if value and str(stage).lower() == "keyframe":
        order = _scene_beat_order(scene)
        nxt = None
        if code in order:
            i = order.index(code)
            nxt = order[i + 1] if i + 1 < len(order) else None
        print(f"NEXT={nxt or 'NONE'}", flush=True)
    return True

# ── THE RELAY, front door (Julian, 2026-07-03 — "everything through the front door now") — thin CLI wrappers
# around cb_beats.fire_next_beat, persisting the prepared-anchor state to relay_state.json so the Studio can
# display it without re-deriving/re-calling NB2 on every page load. Two phases, same as the terminal flow:
# relay_prepare (harvest winner's own official clip -> re-mint -> drift-check -> STOP) and relay_approve (launch
# the next beat under the one-render economy). The UI's Approve Anchor button is the ONLY caller of
# relay_approve — see cb-studio/serve.py. THE ONE-RENDER ECONOMY (Julian, 2026-07-05): there is no seed to pick
# anymore — a beat has exactly one official clip (auto-retried once internally on a failed gate) — so both
# phases dropped their `winner_seed_path`/`seeds` parameters along with the "pick a winner among several" UI.
RELAY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "relay_state.json")

def _relay_all():
    return json.load(open(RELAY)) if os.path.exists(RELAY) else {}

def _relay_save(d):
    json.dump(d, open(RELAY, "w"), indent=1)

def relay_state_for(scene, episode=None):
    """Read-only: the prepared (unapproved) anchor for this scene, or None if nothing is waiting."""
    episode = episode or EP
    return _relay_all().get(episode, {}).get(str(scene))

def relay_prepare(scene, winner_code, episode=None, fast=False):
    """PHASE 1 (front door): harvest winner_code's OWN official clip's settle frame, re-mint it (seamless next
    join only), run the drift check, then STOP — persisting the result for the UI to display. Mirrors
    cb_beats.fire_next_beat(..., approved=False) exactly; this IS that call, not a reimplementation.
    fast=False default (the one-render economy, 2026-07-05): standard tier is the production default now."""
    episode = episode or EP
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass): cb_replicator.walk_scene (a parallel,
    # independent caller of this same cb_beats.fire_next_beat) already checks Gate 2b signed before firing any
    # beat — this front door, the Studio's own "Approve Anchor" path (per this section's own header comment),
    # had no equivalent check at all.
    if not _approved(scene, "2b"):
        print(f"  ⛔ Gate 2B (keyframes) not signed off for {EP} scene {scene} — sign it off before relaying.", flush=True)
        return None
    r = cb_beats.fire_next_beat(PKG, scene, episode, winner_code, dry_run=False, approved=False, fast=fast)
    d = _relay_all()
    scene_d = d.setdefault(episode, {})
    if r:
        # rule 32 (2026-07-05, RE-MINT SCOPING): "remint" is None for an intentional_next_shot next beat (the
        # default) — no NB2 pass ran, since @图1 is a state reference for that junction type, not a pixel-perfect
        # anchor. "anchor" is ALWAYS populated (the re-mint when one ran, the raw harvest otherwise) — the UI
        # must display/gate on "anchor"/driftCheck-may-be-null, never assume "remint" is the only anchor shape.
        scene_d[str(scene)] = {"winnerCode": winner_code, "nextCode": r.get("next_code"),
                                "harvested": r.get("harvested"), "remint": r.get("remint"), "anchor": r.get("anchor"),
                                "driftCheck": r.get("drift_check")}
    else:
        scene_d.pop(str(scene), None)
    _relay_save(d)
    print(f"RELAY_PREPARED={json.dumps(scene_d.get(str(scene)))}", flush=True)
    return r

def relay_approve(scene, winner_code, episode=None, fast=False):
    """PHASE 2 (front door): the ONLY path that may launch the next beat — fires it under the one-render
    economy (one take, one automatic re-fire on a failed gate, then a hard stop naming the layer at fault) off
    the anchor an earlier relay_prepare already produced and cleared for approval. Clears the prepared state on
    success so the UI stops showing an anchor that has already launched.
    fast=False default (the one-render economy, 2026-07-05): standard tier is the production default now."""
    episode = episode or EP
    # FIXED 2026-07-11 (full-codebase audit — gate-order bypass): same check as relay_prepare's own note above.
    if not _approved(scene, "2b"):
        print(f"  ⛔ Gate 2B (keyframes) not signed off for {EP} scene {scene} — sign it off before relaying.", flush=True)
        return None
    r = cb_beats.fire_next_beat(PKG, scene, episode, winner_code, dry_run=False, approved=True, fast=fast)
    if r:
        d = _relay_all()
        d.get(episode, {}).pop(str(scene), None)
        _relay_save(d)
    print(f"RELAY_LAUNCHED={json.dumps(r)}", flush=True)
    return r

def gate3(scene):
    # GATE 3 = Camera. THE BEAT METHOD (the first-ever FLOW, 2026-06-23): group the scene's shots into ~10-12s BEATS
    # and render each beat as ONE multi-shot Seedance take (Seedance directs its OWN internal cuts + camera + timing —
    # where the flow comes from), chained last-frame -> next-beat start, then assemble. THE RULE: one Seedance take per
    # beat, now 15s under the Handle Doctrine (rule 20). Law 5 (2026-07-08 correction — this comment used to describe
    # a forbidden post voice swap): the acted V3 performance is fired in as @Audio1 and drives generation directly
    # (lip-synced in the render itself); there is no native-voice fallback and no post voice swap, ever — cb_post has
    # no swap function by design. This REPLACES the per-shot ref2vid path, which chopped the scene into 8 isolated
    # clips and felt clunky.
    #
    # FIXED 2026-07-15 (live, found by Julian himself mid-session — "surely it should only render the first
    # b1"): this used to call cb_beats.run(PKG, scene, EP) directly — a raw loop over EVERY beat in the scene,
    # no stopping point. Because each beat's own clip is written to disk INSIDE that same loop, by the time
    # the loop reached beat 2 its predecessor's clip already existed on disk, so cb_scene.relay_source_for
    # reported "relay" and the loop fired beat 2 immediately too — then 3, then 4, then 5, ALL IN ONE CALL,
    # with zero human review checkpoint between any of them. That is exactly the runaway cascade THE
    # ONE-RENDER ECONOMY (rule 28) and cb_replicator.walk_scene's own "halts after every single fire for
    # Julian's Eye, never auto-advances through green machine gates" design (rule 44) were built to prevent —
    # but the Studio's actual "Fire Gate 3" button never routed through walk_scene at all; it always called
    # this raw batch loop instead, meaning the whole escorted-walk discipline this project documented
    # extensively was never actually wired to the front door. Fixed by routing through walk_scene here: it
    # fires exactly ONE beat (or resumes exactly one already-rendered-but-unreviewed beat) per call, then
    # halts — the Studio's own re-fire semantics (a fresh "Fire Gate 3" click after cb_beats.record_approval
    # marks the previous beat approved) now naturally walk the scene one beat at a time, matching every other
    # gate's own one-checkpoint-at-a-time discipline.
    print("GATE 3 — Camera: THE ESCORTED WALK (cb_replicator.walk_scene) — fires exactly ONE beat, then halts "
          "for Julian's Eye before the next; never a batch.", flush=True)
    import cb_replicator
    r = cb_replicator.walk_scene(EP, scene, fast=False)
    reason = r.get("reason", "")
    print(f"walk_scene: status={r.get('status')} beats_done={r.get('beats_done')} "
          f"halted_at={r.get('halted_at')} reason={reason}", flush=True)
    # A HALT is the EXPECTED, successful outcome the moment any beat fires (Julian's Eye is the gate no
    # machine owns — walk_scene halts on purpose after every render). Only treat it as a real refusal when
    # the reason names an actual pre-fire or in-flight failure — nothing rendered, or a rendered take failed
    # a hard gate — matching the same failure-vocabulary walk_scene's own _halt() call sites use throughout.
    FAILURE_MARKERS = ("MANIFEST BLOCK", "not signed", "LINT BLOCK", "RE-MINT DRIFT", "failed", "HARD STOP", "refused")
    if r.get("status") == "HALTED" and any(m in reason for m in FAILURE_MARKERS):
        return False
    return True

def gate4(scene):
    # RETAKES — off the Gate-3 sign-off: regen flagged shots + splice + re-conform. Wrapped in try/except
    # 2026-07-07 (front-to-back audit): cb_retake.process_retakes' own per-retake loop had no guard around a
    # bad/stale package path or scene mismatch, so an uncaught exception here used to propagate as a raw
    # traceback through fire() — whose own docstring promises it "never sys.exit itself... only returns
    # True/False." ROOT-CAUSED 2026-07-14 (the follow-up ticket this comment used to defer, now closed):
    # cb_retake.process_retakes' own per-retake loop now catches a bad-path/regen exception per item, converts
    # it to the same {ok:False, ref, error} shape regen_shot's own controlled failures already use, and
    # continues with the rest of the batch instead of losing every result. This wrapper stays in place as
    # defense-in-depth (the same belt-and-braces pattern this codebase already uses elsewhere, e.g. rule 47)
    # for anything genuinely outside process_retakes' own loop (read_retakes, the re-conform step) — never a
    # substitute for the real fix, which now lives at the source.
    try:
        cb_retake.process_retakes(PKG, scene, EP)
        return True
    except Exception as e:
        print(f"⛔ Gate 4 crashed ({str(e)[:200]}) — refusing cleanly instead of raising; fix cb_retake.py's "
              f"process_retakes and re-fire.", flush=True)
        return False

def gate5(scene):
    # POST — master the mix + export stems (once, after retakes). Same safety-net wrapping as gate4() above.
    try:
        cb_post.run(PKG, scene, EP)
        return True
    except Exception as e:
        print(f"⛔ Gate 5 crashed ({str(e)[:200]}) — refusing cleanly instead of raising; fix cb_post.py and "
              f"re-fire.", flush=True)
        return False

GATES = {"1": gate1, "1.6": previz_reel, "2a": anchors, "2b": coverage, "3": gate3, "4": gate4, "5": gate5}
_GENERATIVE = ("2a", "2b", "3")  # gates that render → run the pre-flight + continuity checks around them

def fire(gate, scene):
    """Returns True if the gate actually fired, False on any refusal (unknown gate, prev gate unsigned, or a
    red manifest) — same never-sys.exit-itself convention as approve() (see its own docstring): this function
    is called in-process as well as from the CLI, so only the __main__ dispatch below decides the process exit
    code. Found in the SAME sweep as approve()'s own missing exit-code signal (rule 11): a refusal here used to
    just print and return, leaving the CLI process exit 0 — the Studio's job-status check reads only the
    subprocess return code, so a refused fire was silently reported as "done"."""
    gate = str(gate).lower()
    if gate not in GATES:
        print(f"unknown gate '{gate}' — use one of {list(GATES)}"); return False
    prev = _prev_gate(gate)
    if prev and not _approved(scene, prev):
        print(f"⛔ Gate {prev} not signed off for {EP} scene {scene}. Review it, then:")
        print(f"     python3 cb_pipeline.py approve {prev} {scene}")
        return False
    # THE MANIFEST (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's ruling — "no retakes, no fires" while
    # a manifest is red): firing a gate is refused the same as approving one — same choke-point as approve().
    # Gate 1 itself is EXEMPT: it's the step that PRODUCES the manifest's own content (the Director turns the
    # script into the beat package) — gating its own fire on manifest completeness would be a bootstrap loop
    # (you could never generate the content because the content doesn't exist yet). Its APPROVAL (sign-off)
    # still requires the manifest, same as every other gate — see approve() — this exemption is for the FIRE
    # (generate/regenerate) action only.
    # (shared choke-point: _manifest_gate_scene, above; its "1"/"1.6" mapping already covers the "1.6" case
    # here — this branch never reaches it with gate=="1", so folding both mappings into one is safe.)
    if gate != "1" and not _manifest_gate_scene(scene, gate=gate):
        return False
    print(f"=== FIRE GATE {gate} — {EP} scene {scene} ===", flush=True)
    if gate in _GENERATIVE:
        print("--- pre-flight: context completeness audit (everything pulled in & locked?) ---", flush=True)
        cb_context.run(PKG, scene, EP)
    # FIXED 2026-07-11 (full-codebase audit): this return value used to be discarded, and fire() would print
    # "done" + return True unconditionally — even when the dispatched gate function itself printed a refusal
    # or hit its own caught exception (e.g. previz_reel finding no beats, gate4/gate5 catching a crash). Every
    # function in GATES now returns an explicit bool; a False here is a real refusal, not "done."
    ok = GATES[gate](scene)
    if ok is False:
        print(f"=== gate {gate} did NOT complete for {EP} scene {scene} — see the refusal above; nothing to sign off ===", flush=True)
        return False
    if gate in _GENERATIVE:
        print("--- continuity check (cross-scene, data) ---", flush=True)
        cb_continuity.run(PKG, EP)
    print(f"=== gate {gate} done — REVIEW, then sign off:  python3 cb_pipeline.py approve {gate} {scene} ===", flush=True)
    return True

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
    # TIER SELECTION (Julian, 2026-07-04, "single seed, standard tier" -> generalized 2026-07-05 as THE
    # ONE-RENDER ECONOMY): same order-independent stripped-flag pattern as --episode= above. Standard tier
    # (fast=False) is now the production default everywhere — the old fast=True/seed-exploration default is
    # retired along with the multi-seed picker it existed to serve; --fast=true is the explicit opt-in left for
    # exploratory work outside the escorted production line.
    _fastflag = next((a for a in sys.argv[1:] if a.startswith("--fast=")), None)
    _fast = False
    if _fastflag:
        sys.argv = [a for a in sys.argv if a != _fastflag]
        _fast = _fastflag.split("=", 1)[1].strip().lower() not in ("false", "0", "no")
    # REVIEWER IDENTITY (2026-07-08): same order-independent stripped-flag pattern as --episode=/--fast= above —
    # keeps every command's existing positional argv[2]/argv[3]/... parsing completely untouched.
    _revflag = next((a for a in sys.argv[1:] if a.startswith("--reviewed-by=")), None)
    _reviewer = "Julian"
    if _revflag:
        sys.argv = [a for a in sys.argv if a != _revflag]
        _reviewer = _revflag.split("=", 1)[1].strip() or _reviewer
    cmd = sys.argv[1].lower()
    if cmd == "approve":
        if not approve(sys.argv[2], sys.argv[3], reviewed_by=_reviewer):
            sys.exit(1)
    elif cmd == "unapprove":
        unapprove(sys.argv[2], sys.argv[3])
    elif cmd == "export":
        # export [scene]   — omit scene for the whole episode
        _scene_arg = sys.argv[2] if len(sys.argv) > 2 else None
        print(export_storyboard(PKG, _scene_arg))
    elif cmd == "autofix":
        autofix(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 2)
    elif cmd in ("master", "build-master"):
        build_master(sys.argv[2])
    elif cmd == "anchor":
        # anchor <scene> <a1|a2> [note]   — re-roll one anchor at Gate 2A
        regen_anchor(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "regen":
        # regen <scene> <shotCode> <kind> [note] [target]
        if not regen(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "keyframe",
                     sys.argv[5] if len(sys.argv) > 5 else "",
                     sys.argv[6] if len(sys.argv) > 6 else "both"):
            sys.exit(1)
    elif cmd == "rebuild":
        # rebuild <scene>  — CLEAN rebuild of ALL keyframes (force; deletes stale frames, re-renders every beat)
        if not rebuild(sys.argv[2]):
            sys.exit(1)
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
        # FIXED 2026-07-07 (contradiction-audit): build-beat/gen-audio/render-beat/approve-beat all had a
        # working manifest_ok refusal inside their Python functions, but __main__ never checked the return value
        # and never exited non-zero — so serve.py's job-status poll (which reads ONLY the subprocess return
        # code, cb-studio/serve.py:323-324) reported a REFUSED action as "done." The exact bug class rule 11's
        # own fire()/approve() fix already named ("a refused fire was silently reported as done") had never been
        # swept into this whole per-beat command family. Fixed for all four below.
        if not build_beat(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None):
            sys.exit(1)
    elif cmd == "gen-audio":
        # gen-audio <scene> <beatCode>  — build + measure this beat's V3 dialogue track
        # `is False` specifically (not a plain truthiness check) — a wordless beat legitimately returns None,
        # which must NOT be treated as a failure the way a manifest-refusal False must be.
        if gen_audio(sys.argv[2], sys.argv[3]) is False:
            sys.exit(1)
    elif cmd == "render-beat":
        # render-beat <scene> <beatCode>  — render one beat's Seedance take
        if not render_beat(sys.argv[2], sys.argv[3]):
            sys.exit(1)
    elif cmd == "approve-beat":
        # approve-beat <scene> <beatCode> <stage> [value]  — lock (default) or unlock (value=false) one beat stage
        if not approve_beat(sys.argv[2], sys.argv[3], sys.argv[4], value=(len(sys.argv) < 6 or str(sys.argv[5]).lower() != "false")):
            sys.exit(1)
    elif cmd == "relay-prepare":
        # relay-prepare <scene> <winnerCode>  — Phase 1: harvest+re-mint+drift-check winner's own official clip, STOP
        relay_prepare(sys.argv[2], sys.argv[3], fast=_fast)
    elif cmd == "relay-approve":
        # relay-approve <scene> <winnerCode>  — Phase 2: the ONLY path that launches the next beat (one-render economy)
        relay_approve(sys.argv[2], sys.argv[3], fast=_fast)
    elif cmd == "relay-state":
        # relay-state <scene>  — read-only; prints the prepared anchor JSON (or 'null')
        print(json.dumps(relay_state_for(sys.argv[2])))
    elif cmd == "director-eye":
        # director-eye  — Gate 1.5: flag-and-report review of the beat package vs the show bible (changes NOTHING)
        import cb_director_eye
        cb_director_eye.run(PKG, EP)
    elif cmd == "masters":
        # masters <scene> [platforms=youtube,netflix,amazon]  — real, per-platform loudness-mastered
        # deliverables from the scene's already-assembled picture (fire gate 5 first).
        _plats = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("youtube", "netflix", "amazon")
        cb_post.build_platform_masters(PKG, sys.argv[2], EP, _plats)
    elif cmd == "reconcile":
        # reconcile <scene> [--apply]  — read-only report by default; --apply actually signs whatever's ready
        # via the real approve() (2026-07-14, closes the locked.json-vs-real-evidence desync).
        _apply = "--apply" in sys.argv
        if _apply:
            sys.argv = [a for a in sys.argv if a != "--apply"]
        reconcile_gate_state(sys.argv[2], apply=_apply, reviewed_by=_reviewer)
    else:
        if not fire(cmd.replace("gate", "").strip(), sys.argv[2]):
            sys.exit(1)
