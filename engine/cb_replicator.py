#!/usr/bin/env python3
"""cb_replicator.py — THE REPLICATOR (Julian, 2026-07-05; doctrine now in PRODUCTION_DOCTRINE.md's Stage 5 —
REPLICATOR.md itself retired into that single document, 2026-07-06, THE DEFINITIVE BUILD).

ONE command: walk_scene(episode, scene). It takes the show profile, the scene data and the director's cut as
its only inputs (all resolved from episode+scene through the SAME path/config conventions cb_pipeline.py and
cb_beats.py already use — no new lookup mechanism) and runs Gate 3 end to end for that scene under the
ESCORTED-RUN RULES: assemble each prompt from the rule-28 skeleton, pre-fire lint (cb_qa.check_gate3_lint's
unified Step-4 checks — word budgets, banned vocabulary, Law 5 dialogue-leak, appearance-prose leak, the
anti-slop lexicon, negation scoping, structural §4a/§4b congruence and a source citation map; hard-block on a
blocker, flags on advisories — FIXED 2026-07-12 (full-codebase audit continued): this line used to describe the
retired twelve-Layer-1-law check_prompt_laws lint; the code below (lines 178/250) has always called
cb_qa.check_gate3_lint, the unified check that superseded it — only this paragraph hadn't caught up), fire, QA
+ join-check + anti-hold (last-frame extraction), harvest, re-mint, drift check, thread endStateStill forward as
the next beat's photograph, assemble the next prompt, fire — halting the instant anything comes back non-green,
evidence pack to Downloads throughout.

ESCORTED, NOT AUTONOMOUS. "Escorted" here means: the mechanical steps run themselves for as long as every
check is green, because a clean automated verdict is not something a human glancing at the same evidence would
catch differently — but the moment ANY check is non-green (a lint blocker, a refused fire, a re-mint DRIFT, a
clip QA block, a broken join), walk_scene stops immediately and hands the evidence to a human. It fires exactly
ONE seed per beat (standard tier) — there is no "pick a winner among several" step, because CLIP QA and the
join-check ARE the escort for a single take; a human is only useful once something is ambiguous or wrong, and
this module doesn't manufacture ambiguity by producing options nobody asked for.

THE HARD RULE THIS FILE OBEYS: no prompt text is ever authored or edited by hand here, or anywhere downstream
of it. Every prompt walk_scene ships is built by cb_segprompt.shipped_prompt — called by cb_beats.run and
cb_beats.fire_next_beat, never composed or patched by this module. walk_scene's only job is to decide, from
each step's verdict, whether to keep going.

SCENE BOUNDARIES RESET TO CANON AUTOMATICALLY: walk_scene operates on ONE scene's beat list, filtered by
sceneNumber exactly like every other caller in this codebase. cb_scene.relay_source_for can only ever see the
beats it's handed, so a scene's own first beat always resolves "first" (builds from ITS OWN signed Gate-2b
keyframe) — there is no code path by which it could relay off a different scene's settle frame. Nothing new
was needed to guarantee this; it falls out of the existing per-scene-filtered convention.

    python3 cb_replicator.py <episode> <scene>
"""
import os, sys, glob, json, shutil, subprocess
# FIXED 2026-07-12 (full-codebase audit continued): cb_scene/cb_segprompt were imported here but never called —
# every occurrence of either name elsewhere in this file lives in a docstring/comment describing what OTHER
# modules (cb_beats, cb_pipeline) do internally, never an actual cb_scene.X(...)/cb_segprompt.X(...) call site.
# Removed; cb_beats/cb_qa/cb_preflight/cb_pipeline (the four imports that DO have real call sites) are unaffected.
import cb_beats, cb_qa, cb_preflight, cb_pipeline

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCK_PATH = os.path.join(_ENGINE_DIR, "locked.json")
_DOWNLOADS = os.path.expanduser("~/Downloads")

def _resolve_pkg(episode):
    """SAME glob convention as cb_pipeline._resolve_pkg — the current episode's beat package, newest by mtime.
    Deliberately re-derived here rather than imported: cb_pipeline.PKG is resolved ONCE at import time against
    its own hardcoded EP global, so importing it would freeze to whatever episode happened to be current when
    cb_pipeline was first imported — the same early-binding hazard cb_pipeline._beat_locks already documents
    for its own EP default."""
    cands = (glob.glob(os.path.join(_ENGINE_DIR, "..", "cb-output", f"{episode}_*beat_package.json"))
             or glob.glob(os.path.join(_ENGINE_DIR, "..", "cb-output", f"{episode}_*shot_package.json")))
    if not cands:
        raise SystemExit(f"walk_scene: no beat package found for {episode} under cb-output/")
    return max(cands, key=os.path.getmtime)

def _gate2b_signed(episode, scene, pkg_path):
    """Reads locked.json directly (mirrors cb_pipeline._approved / serve.py's _scene_locks) rather than calling
    cb_pipeline._approved, which reads the module-level EP global instead of taking episode as an argument —
    the same hazard _resolve_pkg's docstring names. GATES ARE HARD LOCKS (CLAUDE.md rule 1): walk_scene
    automates Gate 3 onward; it never substitutes for a human's own Gate 2b sign-off, and never builds one.

    FIXED 2026-07-08 (confirmed HIGH bug): a raw read of locked.json's "2b" flag bypassed the cascade-relock
    staleness check every OTHER gate-status read in the codebase runs first (cb_pipeline._approved calls
    _relock_if_stale + _relock_chain_if_dirty; serve.py's locked_state() calls _relock_stale_scenes) — so a
    Gate-1 beat-data edit made after Gate 2b was signed would leave walk_scene reading a stale "2b": true and
    rendering off keyframes that may no longer match the current beats. Can't just call cb_pipeline._approved()
    itself (same early-binding hazard as _resolve_pkg's docstring already names — _relock_if_stale reads
    cb_pipeline's own module-level PKG, resolved once at import time against ITS hardcoded EP="Ep1", which would
    fingerprint the WRONG package for any other episode). Instead, mirror _relock_if_stale's own fingerprint
    comparison directly: cb_pipeline._scene_beats_fingerprint(pkg_path, scene) takes pkg_path explicitly, so
    it's safe to call in isolation. If the Gate-1 fingerprint recorded at Gate-1 sign-off ("1_fp") no longer
    matches the CURRENT beat data, _relock_if_stale would have already cleared "2b" (along with everything else
    in GATE_SEQ) the moment any other code path read this scene's status — so we treat it as unsigned here too,
    without ever calling that function or its EP-bound PKG global."""
    try:
        d = json.load(open(_LOCK_PATH))
    except Exception:
        d = {}
    sd = d.get(episode, {}).get(str(scene), {})
    if not sd.get("2b"):
        return False
    stored_fp = sd.get("1_fp")
    if sd.get("1") and stored_fp:
        try:
            current_fp = cb_pipeline._scene_beats_fingerprint(pkg_path, scene)
        except Exception:
            return bool(sd.get("2b"))   # fail-open, same as _relock_if_stale — a read error must never brick gate status
        if stored_fp != current_fp:
            return False   # stale — _relock_if_stale would have cleared "2b" the moment this scene's status was next read
    return bool(sd.get("2b"))

# FIXED 2026-07-12 (full-codebase audit continued): _scene_dict(pkg, scene) used to live here — its only call
# site (walk_scene's own `scene_dict = _scene_dict(d, scene)`) never used the result afterward, and grepping the
# whole repo confirms zero other callers ever existed. Removed along with that dead assignment below, rather
# than kept as an unused helper nobody was going to remember to wire up.
def _copy_evidence(name, path):
    if path and os.path.exists(path):
        try:
            shutil.copyfile(path, os.path.join(_DOWNLOADS, name))
            return os.path.join(_DOWNLOADS, name)
        except Exception:
            return None
    return None

def _extract_frame(clip, out_path, last=False):
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    args += (["-sseof", "-1", "-i", clip, "-update", "1"] if last else ["-i", clip, "-vframes", "1"])
    args += ["-q:v", "2", out_path]
    try:
        subprocess.run(args, capture_output=True, timeout=60, check=False)
    except Exception:
        return None
    return out_path if os.path.exists(out_path) else None

def _halt(scene, done, code, reason, evidence):
    print(f"walk_scene: HALT at {code} — {reason}", flush=True)
    return {"status": "HALTED", "scene": scene, "beats_done": done, "halted_at": code,
            "reason": reason, "evidence": [e for e in evidence if e]}

def walk_scene(episode, scene, fast=False):
    """THE REPLICATOR's one command. Returns {status: "COMPLETE"|"HALTED", scene, beats_done, halted_at,
    reason, evidence}. fast=False (standard tier) matches the studio's current production default — the same
    configuration the 1.B2 camera-lock test used, so any future maiden-run comparison stays apples to apples.
    THE ONE-RENDER ECONOMY (Julian, 2026-07-05, PRODUCTION_DOCTRINE.md): every beat gets exactly one fire, one
    automatic re-fire if a gate comes back non-green, then a HARD STOP naming the layer at fault (CLAUDE.md
    rule 3) — never a third roll, and never a "pick a winner among several" ceremony (retired the same day;
    there is now only ever one official clip per beat). The scene's opening beat gets this directly via
    cb_beats._fire_gated; every beat after it gets it from cb_beats.fire_next_beat, which now runs the same
    economy internally. Resumable by construction: every state it reads (official clips, remint anchors, lock
    file) is on disk, so calling walk_scene again after fixing whatever halted it picks up from the same beat,
    not from scratch — it never re-fires a beat that already has a clean, QA-passed official clip."""
    pkg_path = _resolve_pkg(episode)
    # FIXED 2026-07-12 (full-codebase audit continued): this used to re-implement cb_beats._load_scene_beats'
    # own load+filter (json.load, then filter beats by str(sceneNumber) equality) inline, byte-for-byte — a
    # second, unreconciled copy of the exact convention cb_beats.fire_next_beat already gets from the shared
    # helper (this module already imports cb_beats at module level, and calls its other underscore-prefixed
    # helpers elsewhere in this file, so there was no real module-boundary reason to duplicate it here instead
    # of calling it). `d` (the full parsed package) is discarded — nothing in this function reads it once the
    # now-removed dead `scene_dict = _scene_dict(d, scene)` line is gone (see the `_copy_evidence` comment above).
    _, beats = cb_beats._load_scene_beats(pkg_path, scene)
    # Natural sort on the trailing beat number (cb_preflight._beat_sort_key) — a lexicographic sort on the raw
    # code string would misorder any scene with 10+ beats ('1.B10' < '1.B2'); found in the 2026-07-08 audit,
    # the same bug class as cb_beats.py/cb_director.py/cb_previz.py.
    beats.sort(key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
    if not beats:
        return _halt(scene, [], None, f"no beats found for {episode} scene {scene}", [])

    # THE MANIFEST (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's ruling — "Gate N cannot arm... without
    # both manifests green"): walk_scene never arms a scene with a BLOCK-kind manifest gap outstanding, same
    # choke-point cb_pipeline.approve now enforces for the Studio's gate sign-offs.
    try:
        # FIXED 2026-07-12 (full-codebase audit, adversarial verification — critical finding): this redundant
        # local `import cb_preflight` (cb_preflight is already a module-level import, line 44) made cb_preflight
        # a LOCAL variable for walk_scene's ENTIRE body the instant Python parsed this assignment anywhere in
        # the function — including the lambda at line 150, which runs BEFORE this line but still resolved
        # cb_preflight as the (not-yet-assigned) local rather than the module global, raising NameError on
        # every real call. Removed; the module-level import already covers this whole function.
        first_code = beats[0].get("beatCode") or beats[0].get("shotCode")
        # gate="3" (2026-07-09, cross-call-site-consistency finding): walk_scene is the Gate-3 escorted walk —
        # every other manifest_ok caller passes the real production-stage gate it's arming; this one silently
        # defaulted to gate="1". Zero behaviour change today (check_scene_technical's own docstring: the gate
        # param doesn't change its output yet) — matters once gate-scoped checks (e.g. plate presence) ship.
        ok, block_count, _gaps = cb_preflight.manifest_ok(pkg_path, scene=scene, episode=episode, gate="3")
        if not ok:
            return _halt(scene, [], first_code,
                         f"MANIFEST BLOCK — {block_count} gap(s) outstanding for this scene; walk_scene never "
                         f"arms on a red manifest (run: python3 cb_preflight.py --scene={scene})", [])
    except Exception as e:
        print(f"walk_scene: manifest check could not run ({str(e)[:120]}) — proceeding without it; fix cb_preflight.py", flush=True)

    if not _gate2b_signed(episode, scene, pkg_path):
        first_code = beats[0].get("beatCode") or beats[0].get("shotCode")
        return _halt(scene, [], first_code,
                     "Gate 2b is not signed for this scene — walk_scene never advances past an unsigned gate", [])

    done, evidence = [], []

    # BEAT 1 — no predecessor to relay from; fires directly off its own signed Gate-2b keyframe.
    first = beats[0]
    first_code = first.get("beatCode") or first.get("shotCode")
    first_slug = first.get("slug", (first_code or "").replace(".", "_"))
    first_clip = f"media/{episode}_{first_code}_{first_slug}.mp4"
    # STEP 7 — RESUME BY APPROVAL STATUS, NEVER FILE EXISTENCE (GATE3_ANIMATION_DOCTRINE.md §1 Step 7).
    status, _detail = cb_beats.beat_approval_status(episode, first_code, first_slug)
    if status == "pending":
        return _halt(scene, done, first_code,
                     "a rendered take exists with no recorded verdict yet — Julian's Eye is the gate no "
                     "machine owns; call cb_beats.record_approval(...) before walk_scene can resume", evidence)
    if status == "unrendered":
        # STEP 4 — THE UNIFIED LINT (GATE3_ANIMATION_DOCTRINE.md §1 — "Fail = the prompt never fires. Fix at
        # data, recompile."). Blockers halt walk_scene outright; flags are advisory, printed but non-fatal.
        lint = cb_qa.check_gate3_lint(pkg_path, first_code, episode)
        for fl in lint["flags"]:
            print(f"walk_scene: {first_code} [LINT FLAG] {fl}", flush=True)
        if not lint["ok"]:
            return _halt(scene, done, first_code, "STEP 4 LINT BLOCK: " + "; ".join(lint["blockers"]), evidence)
        # FIXED 2026-07-12 (full-codebase audit continued): an "assembled prompt is empty" check used to sit
        # here, reading lint["prompt"] after the `if not lint["ok"]` guard above already returned — but
        # cb_qa.check_gate3_lint itself unconditionally returns ok=False with a "compiled prompt is empty"
        # blocker the moment its own compiled prompt is blank (checked before it ever accumulates blockers/
        # flags, and `prompt` is never reassigned between that check and its own final return). So the guard
        # above always halts first whenever the prompt is empty — this second check could never actually fire.
        # Removed; the relay loop's equivalent lint call (below) never had this redundant check either.
        # THE ONE-RENDER ECONOMY (rule 3 / PRODUCTION_DOCTRINE.md): one fire, one automatic re-fire on a failed
        # gate, then a hard stop naming the layer at fault — the scene's opening beat gets the identical
        # discipline every relay beat gets inside cb_beats.fire_next_beat.
        _, ok, reasons = cb_beats._fire_gated(pkg_path, scene, episode, first_code, first_slug, fast)
        if not ok:
            print(f"walk_scene: {first_code} attempt 1 failed a gate — {'; '.join(reasons)} — ONE automatic re-fire", flush=True)
            _, ok, reasons = cb_beats._fire_gated(pkg_path, scene, episode, first_code, first_slug, fast)
        if not os.path.exists(first_clip):
            return _halt(scene, done, first_code,
                         "beat refused or failed to render (Law 3/5-class refusal, or a render error) — see console log", evidence)
        if not ok:
            return _halt(scene, done, first_code,
                         f"one-render economy HARD STOP — {'; '.join(reasons)}. Diagnosis: {cb_beats._layer_diagnosis(reasons)}", evidence)
        return _halt(scene, done, first_code,
                     "rendered — awaiting Julian's Eye (Step 7): review the clip in Downloads, then call "
                     "cb_beats.record_approval(...) and re-run walk_scene to continue", evidence + [
                         _copy_evidence(f"walk_scene_{first_code}_clip.mp4", first_clip)])
    # status == "approved"
    evidence.append(_copy_evidence(f"walk_scene_{first_code}_clip.mp4", first_clip))
    done.append(first_code)

    # BEATS 2..N — the relay chain, one escorted step per transition: PREPARE (harvest, re-mint, drift-check;
    # dry_run=True reuses the predecessor's own official clip — there is no seed-pick, ever, under the
    # one-render economy) -> if the drift-check is clean, LINT the next beat's actual assembled prompt ->
    # LAUNCH (approved=True — this now runs the full one-render economy INSIDE fire_next_beat itself: one fire,
    # one automatic re-fire on a failed gate, a hard stop naming the layer at fault on a second failure) ->
    # capture the evidence pack either way -> if fire_next_beat reports clean, continue; otherwise halt with
    # its own diagnosis. walk_scene no longer re-derives CLIP QA/JOIN CHECK verdicts fire_next_beat already
    # computed and persisted — that would just be the same vision calls run twice.
    for i in range(1, len(beats)):
        prev, cur = beats[i - 1], beats[i]
        prev_code = prev.get("beatCode") or prev.get("shotCode")
        cur_code = cur.get("beatCode") or cur.get("shotCode")
        cur_slug = cur.get("slug", (cur_code or "").replace(".", "_"))
        cur_clip = f"media/{episode}_{cur_code}_{cur_slug}.mp4"

        # STEP 7 — RESUME BY APPROVAL STATUS, NEVER FILE EXISTENCE (GATE3_ANIMATION_DOCTRINE.md §1 Step 7).
        status, _detail = cb_beats.beat_approval_status(episode, cur_code, cur_slug)
        if status == "approved":
            evidence.append(_copy_evidence(f"walk_scene_{cur_code}_clip.mp4", cur_clip))
            done.append(cur_code)
            continue
        if status == "pending":
            evidence.append(_copy_evidence(f"walk_scene_{cur_code}_clip.mp4", cur_clip))
            return _halt(scene, done, cur_code,
                         "a rendered take exists with no recorded verdict yet — Julian's Eye is the gate no "
                         "machine owns; call cb_beats.record_approval(...) before walk_scene can resume", evidence)

        prep = cb_beats.fire_next_beat(pkg_path, scene, episode, prev_code, fast=fast, dry_run=True)
        if not prep:
            return _halt(scene, done, cur_code, f"prepare step failed (harvest/re-mint) for {cur_code} — see console log", evidence)
        # rule 32 (2026-07-05, RE-MINT SCOPING): the prepared anchor is the re-mint ONLY for a seamless_continuation
        # beat; an intentional_next_shot beat (the default) uses the raw harvest directly — prep["anchor"] is
        # whichever one actually applies (prep["remint"] is None for an intentional beat).
        anchor = prep.get("anchor")
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_anchor.png", anchor))
        drift = prep.get("drift_check") or {}
        if drift.get("ok") is False:
            return _halt(scene, done, cur_code, "RE-MINT DRIFT: " + drift.get("verdict", ""), evidence)

        # STEP 4 — THE UNIFIED LINT, same choke-point as the opener. A relay beat with no predecessor CLIP yet
        # correctly checks as an opener-shape prompt here (cb_scene.relay_source_for's own resolution); once
        # the predecessor's clip exists this naturally checks the real relay wording instead — never a second,
        # divergent lint path.
        lint = cb_qa.check_gate3_lint(pkg_path, cur_code, episode)
        for fl in lint["flags"]:
            print(f"walk_scene: {cur_code} [LINT FLAG] {fl}", flush=True)
        if not lint["ok"]:
            return _halt(scene, done, cur_code, "STEP 4 LINT BLOCK: " + "; ".join(lint["blockers"]), evidence)

        launched = cb_beats.fire_next_beat(pkg_path, scene, episode, prev_code, fast=fast, approved=True)
        if not launched or not os.path.exists(cur_clip):
            return _halt(scene, done, cur_code, f"launch step failed for {cur_code} — see console log", evidence)

        first_frame = f"media/{episode}_{cur_code}_{cur_slug}_walkframe1.png"
        _extract_frame(cur_clip, first_frame)
        last_frame = f"media/{episode}_{cur_code}_{cur_slug}_walklast.png"
        _extract_frame(cur_clip, last_frame, last=True)
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_frame1.png", first_frame))
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_lastframe.png", last_frame))
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_clip.mp4", cur_clip))

        if launched.get("status") == "HARD_STOP":
            return _halt(scene, done, cur_code,
                         f"one-render economy HARD STOP — {'; '.join(launched.get('reasons') or [])}. "
                         f"Diagnosis: {launched.get('diagnosis', '')}", evidence)
        # STEP 7 — machine gates are clean, but nothing self-advances past Julian's own eye (doctrine §1).
        return _halt(scene, done, cur_code,
                     "rendered — awaiting Julian's Eye (Step 7): review the clip in Downloads, then call "
                     "cb_beats.record_approval(...) and re-run walk_scene to continue", evidence)

    print(f"walk_scene: COMPLETE — {episode} scene {scene}, {len(done)}/{len(beats)} beats: {', '.join(done)}", flush=True)
    return {"status": "COMPLETE", "scene": scene, "beats_done": done, "halted_at": None, "reason": "",
            "evidence": [e for e in evidence if e]}

if __name__ == "__main__":
    os.chdir(_ENGINE_DIR)
    episode = sys.argv[1] if len(sys.argv) > 1 else "Ep1"
    scene = sys.argv[2] if len(sys.argv) > 2 else "1"
    result = walk_scene(episode, scene)
    print(json.dumps(result, indent=1, ensure_ascii=False))
