#!/usr/bin/env python3
"""Structured scene driver (config-driven) — fires the DP discipline IN CODE so keyframes are
consistent BY CONSTRUCTION, never freestyle.

For a scene it: derives EVERY shot from the scene's locked MASTER frame, auto-assembles strong
references from the SSOT (config/characters.json — all characters + Keen's wristband state), and
builds prompts via cb_prompts (reference-only character + rich cinematic scene). Reads the shot
package's own keyframePrompt/i2vPrompt seeds. No hardcoded references or prompts.

    python3 cb_scene.py <package.json> <sceneNumber> [episode=Ep1]
"""
import cb_gen, cb_prompts as P, cb_qa, json, sys, os, traceback

def preflight(pkg_path, scene_num, episode="Ep1"):
    """THE GATE CHECK — verify a scene is production-ready BEFORE spending a single API call.
    Confirms the scene PLATE exists and EVERY character in the scene has a clean turn4 identity lock
    (no legacy grid, no missing reference). Prints a green/red report; returns True only when the gate
    can open. run() calls this and ABORTS if anything is wrong — the lock never renders a broken scene."""
    d = json.load(open(pkg_path))
    scene_num = str(scene_num)
    units = [s for s in (d.get("beats") or d.get("shots") or []) if str(s.get("sceneNumber")) == scene_num]
    unit = "beats" if d.get("beats") else "shots"
    sc = P.scene_cfg(episode, scene_num)
    print(f"GATE preflight: {episode} scene {scene_num} '{sc.get('name','')}' — {len(units)} {unit}", flush=True)
    ok = True
    plate = sc.get("master")
    if plate and os.path.exists(plate):
        print(f"  OK   scene plate: {plate}", flush=True)
    else:
        print(f"  FAIL scene plate missing: {plate!r} — build it: python3 cb_scene.py plate {pkg_path} {scene_num} {episode}", flush=True)
        ok = False
    for c in P.scene_characters(units):
        try:
            ref = P.char_identity_ref(c)
            print(f"  OK   {c}: {os.path.basename(ref)}", flush=True)
        except Exception as e:
            print(f"  FAIL {e}", flush=True); ok = False
    print(("GATE OPEN — scene is production-ready; the build will run cleanly." if ok
           else "GATE CLOSED — fix the FAIL(s) above before rendering. Nothing was rendered."), flush=True)
    return ok

def _beat_as_shot(b):
    """Map a BEAT to the shot-shape build_keyframe_prompt expects — so a beat's ONE opening keyframe is built
    through the SAME system (the [Image N] identity locks + the plate + the char turnarounds pulled from config).
    The opening cut's framing becomes the shot framing; startState is the opening pose; no endState (a beat has
    no payoff frame — Seedance animates it forward at Gate 3)."""
    cuts = b.get("cuts") or []
    f0 = ((cuts[0] or {}).get("framing") or "") if cuts else ""
    sh = dict(b)
    sh["shotCode"] = b.get("beatCode") or b.get("shotCode")
    sh["shotSize"] = (f0.split("(")[0].split(",")[0].strip() or "wide establishing shot") if f0 else "wide establishing shot"
    sh["startState"] = b.get("startState", "")
    sh["endState"] = ""
    sh["action"] = b.get("storyBeat", "")
    return sh

def _run_beats(d, scene_num, episode, codes=None, force=False):
    """GATE 2B (beat-native) — build ONE opening keyframe per beat from the FROZEN plate master + the locked
    character turnarounds (char_identity_ref), via build_keyframe_prompt. A vision beat builds from its own
    scene's master (build_vision_prompt). No START+END pairs."""
    beats = [b for b in d["beats"] if str(b.get("sceneNumber")) == scene_num]
    sc = P.scene_cfg(episode, scene_num); master = sc.get("master")
    print(f"BEAT keyframes: {episode} scene {scene_num} '{sc.get('name','')}', {len(beats)} beats, master={master}", flush=True)
    for b in beats:
        code = b.get("beatCode"); slug = b.get("slug", (code or "").replace(".", "_"))
        out = f"{episode}_{code}_{slug}.png"; outpath = f"media/{out}"
        if codes and code not in codes:
            continue
        if os.path.exists(outpath):
            if force:
                os.remove(outpath)   # CLEAN rebuild — delete the stale keyframe so it re-renders fresh
                print(f"  {code} = cleaned for rebuild", flush=True)
            else:
                print(f"  {code} = kept (already built — resume)", flush=True); continue
        try:
            prompt, refs, info = keyframe_for(d["beats"], code, episode)   # SINGLE source of truth (in-scene chain)
            ch = info.get("chain", {})
            if ch.get("status") == "pending":      # continuation whose chain frame isn't rendered yet — build it first
                print(f"  {code} SKIPPED — continuation of {ch.get('prev')}, which isn't rendered yet (build it first).", flush=True); continue
            if ch.get("status") == "needs-plate":  # an anchor needs the blank scene plate (Image 3) — build the foundation first
                print(f"  {code} SKIPPED — anchor needs the scene foundation (the blank scene shot, Image 3). Build the foundation first.", flush=True); continue
            print(f"  {code} {info.get('kind')} -> {out} | {ch.get('status')}"
                  + (f" off {ch.get('prev')}" if ch.get('status') == 'chained' else "") + f" | refs={len(refs)}", flush=True)
            cb_gen.generate_image(prompt, refs, "16:9", out)
        except Exception as e:
            print(f"  FAIL {code}: {e}", flush=True); traceback.print_exc()
    print("=== BEAT KEYFRAMES DONE ===", flush=True)

def beat_frame_path(b, episode="Ep1"):
    """The keyframe file path a beat renders to — SAME naming as build_one_beat / build_keyframes."""
    code = b.get("beatCode") or b.get("shotCode") or ""
    slug = b.get("slug", (code or "").replace(".", "_"))
    return f"media/{episode}_{code}_{slug}.png"

def beat_end_frame_path(b, episode="Ep1"):
    """RETIRED (Julian, 2026-07-03 — "ending frames are harvested, never composed"). Kept for rollback/reference
    only; no active caller. Superseded by beat_settle_frame_path + harvest_settle_frame below, which pick the
    SHARPEST frame anywhere in the settle window instead of blindly grabbing the literal last decodable frame."""
    code = b.get("beatCode") or b.get("shotCode") or ""
    slug = b.get("slug", (code or "").replace(".", "_"))
    return f"media/{episode}_{code}_{slug}_end.png"

def build_ending_frame(episode, code, slug):
    """RETIRED (Julian, 2026-07-03 — "ending frames are harvested, never composed"). Kept for rollback/reference
    only; no active caller. This "composed" a frame by blindly seeking to EOF (-sseof -1), which could land on a
    soft/motion-blurred frame; harvest_settle_frame below samples the whole settle window and scores each
    candidate for sharpness instead."""
    import subprocess
    clip = f"media/{episode}_{code}_{slug}.mp4"
    if not os.path.exists(clip):
        return None
    out = f"media/{episode}_{code}_{slug}_end.png"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-1", "-i", clip,
                        "-update", "1", "-q:v", "2", out], capture_output=True)
    return out if (not r.returncode and os.path.exists(out)) else None

def beat_settle_frame_path(b, episode="Ep1"):
    """THE HARVEST doctrine's path helper (Julian, 2026-07-03) — mirrors beat_end_frame_path's signature but
    points at the HARVESTED settle frame (see harvest_settle_frame), the sole active "ending frame" concept now:
    ending frames are harvested, never composed."""
    code = b.get("beatCode") or b.get("shotCode") or ""
    slug = b.get("slug", (code or "").replace(".", "_"))
    return f"media/{episode}_{code}_{slug}_settle.png"

SETTLE_WINDOW = 2.0   # matches cb_segprompt.HANDLE_SETTLE — kept as a plain local constant (no cross-module import,
                      # same convention as this file's other standalone doctrine constants) so cb_scene never needs
                      # to import the prompt-emitter module just to know the settle's length.

def _clip_dur(clip):
    import subprocess
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nk=1:nw=1", clip], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0

def _laplacian_sharpness(path):
    """Shared sharpness metric (Laplacian variance, plain numpy, no cv2) — used both to PICK the sharpest
    frame in a harvest window and, separately, to SCORE the frame actually harvested (harvest_needs_remint,
    below). A low score means blurred/degraded, not necessarily "the wrong pose" — this is a quality check,
    not an identity check."""
    import numpy as np
    from PIL import Image
    try:
        arr = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
        lap = (-4 * arr + np.roll(arr, 1, axis=0) + np.roll(arr, -1, axis=0)
                      + np.roll(arr, 1, axis=1) + np.roll(arr, -1, axis=1))
        return float(lap.var())
    except Exception:
        return -1.0

def harvest_settle_frame(episode, code, slug, window=SETTLE_WINDOW, samples=12):
    """THE RELAY CHAIN's harvest (Julian, 2026-07-03, CLAUDE.md rule 21): the SHARPEST frame anywhere in a beat's
    final `window` seconds — its Handle Doctrine settle (rule 20) — not a prayer that the literal last frame is
    clean. Scored by a Laplacian-variance sharpness metric over a plain numpy array (no cv2 dependency). Returns
    the harvested frame's path, or None if the clip doesn't exist yet (a relay beat then blocks rather than
    guessing — CLAUDE.md rule 21)."""
    import subprocess, tempfile, glob
    from PIL import Image
    clip = f"media/{episode}_{code}_{slug}.mp4"
    if not os.path.exists(clip):
        return None
    dur = _clip_dur(clip)
    if dur <= 0:
        return None
    start = max(0.0, dur - window)
    out_path = f"media/{episode}_{code}_{slug}_settle.png"
    with tempfile.TemporaryDirectory() as tmp:
        pattern = os.path.join(tmp, "f_%03d.png")
        fps = max(1.0, samples / max(window, 0.1))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", clip,
                        "-t", f"{window:.3f}", "-vf", f"fps={fps:.3f}", pattern], capture_output=True)
        frames = sorted(glob.glob(os.path.join(tmp, "f_*.png")))
        if not frames:
            return None
        best_path, best_score = None, -1.0
        for f in frames:
            score = _laplacian_sharpness(f)
            if score > best_score:
                best_score, best_path = score, f
        if not best_path:
            return None
        Image.open(best_path).convert("RGB").save(out_path)
    return out_path if os.path.exists(out_path) else None

SETTLE_SHARPNESS_MIN = 40.0   # THE RE-MINT CORRECTION (Julian, 2026-07-06 — "do not re-mint the last frame
# every time by default... re-mint only if the harvested frame is degraded, blurred, off-model, or
# unsuitable... constant re-minting can introduce drift because Nano Banana may 'beautify' or subtly change
# the character"). Threshold picked conservatively low: harvest_settle_frame already picks the SHARPEST frame
# in the settle window before this is even checked, so a genuinely usable frame should clear this easily; this
# only catches a settle window that was uniformly poor (motion blur throughout, compression artifacting).
# Calibrate against real rendered clips once more are on hand — no real-clip sample exists yet to tune this
# against beyond 1.B1's single render.

def harvest_needs_remint(path):
    """Quality gate for THE RE-MINT CORRECTION: does this ALREADY-HARVESTED frame need the NB2 cleanup pass,
    or is it good enough to use raw? Returns (needs_remint: bool, reason: str). Checks SHARPNESS now (real,
    testable, no external API); does NOT yet check off-model/identity drift on the raw harvest itself — that
    would need a vision-model call (the same class of call cb_qa.check_remint already makes AFTER a re-mint,
    just run instead BEFORE deciding whether to re-mint at all) and this project's vision-QA API is currently
    quota-blocked end to end (see cb_qa.VISION_MODEL's 2026-07-06 note) — flagged here, not silently skipped,
    so a future session wires it in rather than assuming sharpness alone is the whole check."""
    if not path or not os.path.exists(path):
        return True, "harvested frame missing"
    score = _laplacian_sharpness(path)
    if score < 0:
        return True, "sharpness check failed to run (corrupt/unreadable frame) — re-mint to be safe"
    if score < SETTLE_SHARPNESS_MIN:
        return True, f"harvested frame sharpness {score:.1f} below the {SETTLE_SHARPNESS_MIN} floor — likely blurred/degraded"
    return False, f"harvested frame sharpness {score:.1f} — clears the floor, used raw (no re-mint)"

def remint_settle_frame(episode, code, slug, cast, harvested_path):
    """THE RE-MINT step (Julian's ruling, 2026-07-03) — now STANDARD for every relay link, not QA-triggered;
    supersedes the earlier "NB2 chain refresh, rejected as routine" backlog note (LAB_BACKLOG.md) — the director
    overrides the lab. Runs the harvested settle frame through NB2 with the LOCKED, deliberately minimal re-mint
    prompt (cb_prompts.build_remint_prompt): turnarounds attached ONLY to hold identity while cleaning, artifacts
    and blur removed, same everything else. Returns the re-minted frame's path, or None on failure."""
    turnarounds = [a for c in cast if (a := P.char_identity_ref(c)) and os.path.exists(a)]
    prompt = P.build_remint_prompt()
    out = f"{episode}_{code}_{slug}_remint.png"
    outpath = f"media/{out}"
    cb_gen.generate_image(prompt, [harvested_path] + turnarounds, "16:9", out)
    return outpath if os.path.exists(outpath) else None

def relay_source_for(beats, code, episode="Ep1"):
    """THE RELAY CHAIN's source (Julian, 2026-07-03, CLAUDE.md rule 21; RE-MINT SCOPING superseded by THE
    RE-MINT CORRECTION, 2026-07-06 — "do not re-mint the last frame every time by default... use the
    approved raw harvested settle frame... re-mint only if the harvested frame is degraded, blurred,
    off-model, or unsuitable") — distinct from chain_source_for (which feeds Gate 2b's KEYFRAME generation).
    Returns (frame_path_or_None, status, prev_code):
      first          the scene's first beat (or a vision beat, or no previous beat) — no relay source; this beat
                     keeps its own Gate-2b-generated keyframe, exactly as before this doctrine.
      no_predecessor_clip   there IS a previous beat, but it has no rendered clip yet to harvest from — blocks
                     the relay at this beat rather than guessing; falls back to this beat's own keyframe.
      relay          the previous beat has a rendered clip. A `seamless_continuation` beat still ALWAYS prefers
                     its predecessor's RE-MINTED anchor (unchanged — @图1 is used as literal first-frame pixels
                     there, falling back to the raw harvest if no re-mint exists yet, so a beat fired outside
                     the fire_next_beat ceremony still degrades gracefully). An `intentional_next_shot` beat
                     (the DEFAULT) now decides by the harvested frame's own QUALITY (harvest_needs_remint), not
                     by junction type alone: a good-quality raw harvest is used directly, ALWAYS, even if a
                     stale re-mint file happens to exist on disk (constant re-minting risks NB2 quietly
                     "beautifying" the character — drift, not fidelity); a degraded harvest prefers an
                     already-prepared re-mint if fire_next_beat's prepare step already made one, falling back to
                     the raw harvest anyway if it hasn't (this function is a pure lookup — it never generates a
                     re-mint itself; only fire_next_beat's prepare step does that, gated on Julian's approval).
                     Either way, skips keyframe generation for THIS beat entirely."""
    import cb_segprompt
    idx = next((i for i, b in enumerate(beats)
                if str(b.get("beatCode") or b.get("shotCode")) == str(code)), None)
    if idx is None or idx == 0:
        return None, "first", None
    if P.vision_for(episode, str(code)):
        return None, "first", None
    j = idx - 1
    while j >= 0 and P.vision_for(episode, str(beats[j].get("beatCode") or beats[j].get("shotCode"))):
        j -= 1
    if j < 0:
        return None, "first", None
    prev = beats[j]
    prev_code = prev.get("beatCode") or prev.get("shotCode")
    prev_slug = prev.get("slug", (prev_code or "").replace(".", "_"))
    harvested_path = f"media/{episode}_{prev_code}_{prev_slug}_settle.png"
    remint_path = f"media/{episode}_{prev_code}_{prev_slug}_remint.png"
    junction = cb_segprompt._junction_type(beats[idx])
    if junction == cb_segprompt.JUNCTION_SEAMLESS:
        if os.path.exists(remint_path):
            return remint_path, "relay", prev_code
        harvested = harvest_settle_frame(episode, prev_code, prev_slug)
        if not harvested:
            return None, "no_predecessor_clip", prev_code
        return harvested, "relay", prev_code
    # intentional_next_shot (the default): quality-gated, per THE RE-MINT CORRECTION.
    harvested = harvested_path if os.path.exists(harvested_path) else harvest_settle_frame(episode, prev_code, prev_slug)
    if not harvested:
        return None, "no_predecessor_clip", prev_code
    needs_remint, _reason = harvest_needs_remint(harvested)
    if needs_remint and os.path.exists(remint_path):
        return remint_path, "relay", prev_code
    return harvested, "relay", prev_code

def chain_source_for(beats, code, episode="Ep1"):
    """The Lock & Chain source for a beat's KEYFRAME (Gate 2b) — the fallback path, used only when the Relay
    Chain (rule 21, relay_source_for) isn't ready yet (this beat's predecessor has no signed clip to harvest
    from), so this beat still needs its OWN keyframe generated. Returns (prev_frame_path_or_None, status, prev_code):
      first        the scene's first beat — builds from its plate master (anchor; no chain)
      vision       a vision beat — its own POV; never chains, never a chain source
      continuation any later beat — chains off the previous NON-VISION beat's frame in the SAME scene. THE HARVEST
                   doctrine (2026-07-03, superseding the old FRAME CHAIN "composed ending frame"): prefers that
                   beat's HARVESTED SETTLE FRAME (the sharpest frame in its rendered clip's settle window) when one
                   exists, falling back to its OPENING frame when it doesn't (not yet rendered through Gate 3) —
                   so this never regresses a beat that hasn't reached Gate 3 yet. The path is returned whether or
                   not that frame is rendered yet; the caller checks existence for the file + label."""
    idx = next((i for i, b in enumerate(beats)
                if str(b.get("beatCode") or b.get("shotCode")) == str(code)), None)
    if idx is None:
        return None, "first", None
    if P.vision_for(episode, str(code)):
        return None, "vision", None
    j = idx - 1                                  # walk back to the previous NON-VISION beat (a vision is its own POV)
    while j >= 0 and P.vision_for(episode, str(beats[j].get("beatCode") or beats[j].get("shotCode"))):
        j -= 1
    if j < 0:
        return None, "first", None
    prev = beats[j]
    prev_code = prev.get("beatCode") or prev.get("shotCode")
    settle_path = beat_settle_frame_path(prev, episode)
    chosen = settle_path if os.path.exists(settle_path) else beat_frame_path(prev, episode)
    return chosen, "continuation", prev_code

def keyframe_for(all_beats, code, episode="Ep1", note=""):
    """THE SINGLE keyframe call for a beat — returns the EXACT (prompt, refs, info) the image API receives AND the
    beat card shows. Generation (_run_beats / build_one_beat), the previews (kf_preview / beat_preview) AND manual
    regen (regen_shot) ALL route through here, so the beat card is 100% representative of the API send (WYSIWYG).
    Chain is SCENE-scoped: a scene's first beat builds from that scene's plate master; later beats chain off the
    previous beat's frame in the SAME scene. `note` = a human correction appended to the prompt (manual regen).
    Returns (prompt, refs, info) where info = {kind, chain:{status, prev}}."""
    b = next((x for x in all_beats if str(x.get("beatCode") or x.get("shotCode")) == str(code)), None)
    if not b:
        return None, [], {"error": f"beat {code} not found", "kind": "opening keyframe", "chain": {"status": "first", "prev": None}}
    scene = str(b.get("sceneNumber") or "")
    sc = P.scene_cfg(episode, scene)
    sh = _beat_as_shot(b)
    vision = P.vision_for(episode, str(code))
    if vision:
        of_sc = P.scene_cfg(episode, vision["ofScene"])
        prompt, refs = P.build_vision_prompt(sh, vision, of_sc, note=note, episode=episode)
        return prompt, refs, {"kind": "vision keyframe", "chain": {"status": "vision", "prev": None}}
    scene_beats = [x for x in all_beats if str(x.get("sceneNumber")) == scene]
    cref, cstatus, pcode = chain_source_for(scene_beats, code, episode)
    is_cont = cstatus == "continuation"
    prompt, refs = P.build_keyframe_prompt(sh, sc, master_path=sc.get("master"), episode=episode,
                                           chain_ref=(cref if is_cont else None), note=note)
    if is_cont:
        # the prompt is continuation-format always; the FILE/label depend on whether the previous frame is rendered yet
        sub = "chained" if (cref and os.path.exists(cref)) else "pending"
    else:
        # an ANCHOR must reference the blank SCENE PLATE (Image 3) — it requires the foundation (Gate 2a) built first
        master = sc.get("master")
        has_plate = bool(master and os.path.exists(master)) or bool(b.get("extraScenes"))
        sub = cstatus if has_plate else "needs-plate"
    # THE GATE-2 LINT (2026-07-08 software-wide fix batch): check_gate3_lint's anti-slop + Character Vocabulary
    # Law checks had no Gate-2 sibling at all — this is the SINGLE choke-point every keyframe-prompt consumer
    # (generation, preview, manual regen) routes through, so the lint is computed HERE, once, and every caller
    # reads info["lint"] rather than each re-deriving it. A manual override (keyframePromptOverride) is Julian's
    # own hand-typed text, not compiled from beat data — build_keyframe_prompt already returns it verbatim
    # before any of the logic above runs, so skip the lint entirely rather than judge hand-authored text.
    if str(sh.get("keyframePromptOverride") or "").strip():
        lint = {"ok": True, "blockers": [], "flags": ["manual override — lint skipped"]}
    else:
        lint = cb_qa.check_keyframe_lint(prompt, chars=P.opening_cast(sh))
    return prompt, refs, {"kind": "opening keyframe", "chain": {"status": sub, "prev": pcode}, "lint": lint}

def build_one_beat(pkg_path, scene_num, code, episode="Ep1", chain_from=None, force=True):
    """CASCADE UNIT (Lock & Chain) — build ONE beat's opening keyframe. chain_from = the PREVIOUS beat's APPROVED
    keyframe path; when set, this beat is generated as a SEQUENTIAL DELTA off it (world/lighting/identity/positions
    locked, only the action + framing change). Beat 1 passes chain_from=None (builds from the approved plate master).
    Returns the keyframe path. This is the per-beat unit the approve-to-unlock UI auto-fires (Ticket 4)."""
    d = json.load(open(pkg_path)); scene_num = str(scene_num)
    b = next((x for x in d.get("beats", []) if str(x.get("sceneNumber")) == scene_num and x.get("beatCode") == code), None)
    if not b:
        print(f"build_one_beat: beat {code} not found in scene {scene_num}", flush=True); return None
    slug = b.get("slug", (code or "").replace(".", "_")); out = f"{episode}_{code}_{slug}.png"; outpath = f"media/{out}"
    if os.path.exists(outpath) and force:
        os.remove(outpath)
    # chain is resolved INSIDE keyframe_for (chain_source_for) so generation == the beat-card preview (WYSIWYG).
    # chain_from is accepted for back-compat but no longer needed — the resolver derives the same previous frame.
    prompt, refs, info = keyframe_for(d["beats"], code, episode)
    ch = info.get("chain", {})
    if ch.get("status") == "pending":          # continuation whose chain frame isn't rendered yet — gate it
        print(f"  {code} BLOCKED — continuation of {ch.get('prev')}, which isn't rendered yet. Build & approve it first.", flush=True)
        return None
    if ch.get("status") == "needs-plate":      # an anchor needs the blank scene plate (Image 3) — build the foundation first
        print(f"  {code} BLOCKED — anchor needs the scene foundation (the blank scene shot, Image 3). Build the foundation first.", flush=True)
        return None
    lint = info.get("lint") or {}
    if not lint.get("ok", True):
        print(f"  {code} BLOCKED — keyframe lint failed: {'; '.join(lint.get('blockers') or [])}", flush=True)
        return None
    for f in (lint.get("flags") or []):
        if f != "manual override — lint skipped":
            print(f"  {code} (keyframe lint flag) {f}", flush=True)
    print(f"  {code} {info.get('kind')} -> {out} | {ch.get('status')}"
          + (f" off {ch.get('prev')}" if ch.get('status') == 'chained' else "") + f" | refs={len(refs)}", flush=True)
    cb_gen.generate_image(prompt, refs, "16:9", out)
    return outpath

def run(pkg_path, scene_num, episode="Ep1", codes=None, force=False):
    if not preflight(pkg_path, scene_num, episode):
        raise SystemExit("LOCK: gate closed — scene not production-ready. Nothing was rendered.")
    d = json.load(open(pkg_path)); scene_num = str(scene_num)
    if d.get("beats"):                         # BEAT-NATIVE: one OPENING keyframe per beat
        return _run_beats(d, scene_num, episode, codes, force)
    shots = [s for s in d["shots"] if str(s.get("sceneNumber")) == scene_num]
    sc = P.scene_cfg(episode, scene_num)
    master = sc.get("master")  # may be None (not built yet)
    print(f"Structured build (FROZEN master + CHAINING): {episode} scene {scene_num} '{sc['name']}', "
          f"{len(shots)} shots, master={master}", flush=True)
    prev_end = None  # the previous shot's END frame — the handshake into the next shot's start
    for i, s in enumerate(shots):
        code = s["shotCode"]; slug = s.get("slug", code.replace(".", "_"))
        out = f"{episode}_{code}_{slug}.png"; outpath = f"media/{out}"
        endout = f"{episode}_{code}_{slug}_end.png"
        if codes and code not in codes:    # shot-range filter (e.g. build only 1.1..1.6)
            continue
        try:
            vision = P.vision_for(episode, code)
            if vision:  # a vision is a different space — it does NOT join the chain
                of_sc = P.scene_cfg(episode, vision["ofScene"])
                prompt, refs = P.build_vision_prompt(s, vision, of_sc, episode=episode)
                print(f"  {code} = VISION of scene {vision['ofScene']} (own master; breaks the chain) | refs={len(refs)}", flush=True)
                cb_gen.generate_image(prompt, refs, "16:9", out)
                eprompt, erefs = P.build_end_prompt(s, sc, master_path=master, start_path=outpath, episode=episode)
                cb_gen.generate_image(eprompt, erefs, "16:9", endout)
                continue  # prev_end unchanged — the next real shot chains from the last real shot
            if master and outpath == master:
                print(f"  {code} start = FROZEN MASTER (kept)", flush=True)
            elif os.path.exists(outpath) and not force:         # RESUME: already built (e.g. after a crash) — keep it (force = rebuild)
                print(f"  {code} start = kept (already built — resume)", flush=True)
                if master is None: master = outpath
            elif master is None and i == 0:
                prompt, refs = P.build_keyframe_prompt(s, sc, master_path=None, episode=episode)  # establishing master
                print(f"  {code} start = NEW MASTER (establishing) | refs={len(refs)}", flush=True)
                cb_gen.generate_image(prompt, refs, "16:9", out)
                master = outpath
            else:  # derive from the frozen master (the plate) + the locked character turnarounds — NO cross-shot
                   # chaining. Passing the previous shot's RENDER forward compounded drift down the scene (1.1 clean
                   # -> each later shot inherited the last one's errors). Every shot is built independently from the
                   # SAME plate + SAME turnarounds = the canonical template, identical for every shot.
                prompt, refs = P.build_keyframe_prompt(s, sc, master_path=master, episode=episode)
                print(f"  {code} start -> {out} (plate + turnarounds, no chain) | refs={len(refs)}", flush=True)
                cb_gen.generate_image(prompt, refs, "16:9", out)
            if os.path.exists(f"media/{endout}") and not force:  # RESUME: end already built — keep it (force = rebuild)
                print(f"  {code} end = kept (already built — resume)", flush=True)
            else:
                eprompt, erefs = P.build_end_prompt(s, sc, master_path=master, start_path=outpath, episode=episode)
                cb_gen.generate_image(eprompt, erefs, "16:9", endout)  # end = same structure + start as motion anchor
                print(f"  {code} end -> {endout} | refs={len(erefs)} (START frame + scene plate + turnaround(s))", flush=True)
            prev_end = f"media/{endout}"  # this shot's end (readable path) becomes the next shot's handshake
        except Exception as e:
            print(f"  FAIL {code}: {e}", flush=True); traceback.print_exc()
    print("=== STRUCTURED SCENE BUILD DONE ===", flush=True)

def _derive_master(shots, s, sc, episode):
    """The master frame this shot derives from (None if this shot IS the establishing master)."""
    master = sc.get("master")
    code = s["shotCode"]; slug = s.get("slug", code.replace(".", "_"))
    if master:
        return None if f"media/{episode}_{code}_{slug}.png" == master else master
    first = shots[0]
    if code == first["shotCode"]:
        return None
    fslug = first.get("slug", first["shotCode"].replace(".", "_"))
    fpath = f"media/{episode}_{first['shotCode']}_{fslug}.png"
    return fpath if os.path.exists(fpath) else None

def regen_shot(pkg_path, scene_num, shot_code, episode="Ep1", note="", target="both"):
    """Regenerate ONE shot's keyframe(s), feeding the human correction note into the prompt.
    target = 'both' (start then end-from-start) | 'start' (leave end) | 'end' (from existing start, leave start)."""
    d = json.load(open(pkg_path))
    shots = [s for s in (d.get("beats") or d.get("shots") or []) if str(s.get("sceneNumber")) == scene_num]
    for _s in shots:
        _s.setdefault("shotCode", _s.get("beatCode"))
    raw = next((x for x in shots if x["shotCode"] == shot_code), None)
    if not raw:
        print(f"REGEN: shot {shot_code} not found in scene {scene_num}", flush=True); return
    is_beat = bool(raw.get("beatCode")) and bool(d.get("beats"))
    code = raw["shotCode"]; slug = raw.get("slug", code.replace(".", "_"))
    out = f"{episode}_{code}_{slug}.png"; outpath = f"media/{out}"
    endout = f"{episode}_{code}_{slug}_end.png"
    print(f"REGEN keyframe {code} | target={target} | note: {note[:80]!r}", flush=True)
    if is_beat:
        # BEAT-NATIVE: regen through the SAME single source of truth as the cascade (chain + override + contamination split
        # + anchor/continuation format + gates), so a manually-regenerated keyframe is IDENTICAL to the fire-path. Opening
        # frame only (the cascade has no end frames). chain_from/note honoured inside keyframe_for.
        prompt, refs, info = keyframe_for(d.get("beats") or [], code, episode, note=note)
        st = (info.get("chain") or {}).get("status")
        if st == "pending":
            print(f"  REGEN BLOCKED — {code} continues {(info.get('chain') or {}).get('prev')}, not rendered yet. Build the previous beat first.", flush=True); return
        if st == "needs-plate":
            print(f"  REGEN BLOCKED — {code} anchor needs the scene foundation (the blank scene shot). Build the foundation first.", flush=True); return
        lint = info.get("lint") or {}
        if not lint.get("ok", True):
            print(f"  REGEN BLOCKED — {code} keyframe lint failed: {'; '.join(lint.get('blockers') or [])}", flush=True); return
        cb_gen.generate_image(prompt, refs, "16:9", out)
        print(f"  start -> {out} ({info.get('kind')}, {st}, refs={len(refs)})", flush=True)
        print("REGEN done", flush=True); return
    s = _beat_as_shot(raw) if raw.get("beatCode") else raw
    sc = P.scene_cfg(episode, scene_num)
    if target in ("both", "start"):
        vision = P.vision_for(episode, code)
        if vision:
            of_sc = P.scene_cfg(episode, vision["ofScene"])
            prompt, refs = P.build_vision_prompt(s, vision, of_sc, note=note, episode=episode)
            cb_gen.generate_image(prompt, refs, "16:9", out)
            print(f"  start -> {out} (VISION of scene {vision['ofScene']}, refs={len(refs)})", flush=True)
        else:
            mp = _derive_master(shots, s, sc, episode)
            prompt, refs = P.build_keyframe_prompt(s, sc, master_path=mp, note=note, episode=episode)
            cb_gen.generate_image(prompt, refs, "16:9", out)
            print(f"  start -> {out} ({'derive' if mp else 'establishing'}, refs={len(refs)})", flush=True)
    if target in ("both", "end"):
        if not os.path.exists(outpath):
            print(f"  end SKIPPED: no start frame at {outpath} — regenerate the start first", flush=True); return
        eprompt, erefs = P.build_end_prompt(s, sc, start_path=outpath, episode=episode, note=note)
        cb_gen.generate_image(eprompt, erefs, "16:9", endout)
        print(f"  end -> {endout} (from start)", flush=True)
    print("REGEN done", flush=True)

def build_plate(pkg_path, scene_num, episode="Ep1", note=""):
    """A1 — build the scene's EMPTY ENVIRONMENT PLATE (no characters). Returns its path. The world
    authority; coverage places characters into it. Uses the scene's location anchor (if any) + the current
    establishing master as a LAYOUT guide (characters removed)."""
    sc = P.scene_cfg(episode, str(scene_num))
    out = f"{episode}_S{scene_num}_plate.png"
    prior_plate, changes = P.location_history(episode, scene_num)  # stateful locations (this episode)
    lib_ref = P.loclib_ref(sc.get("locationId"))   # the persistent SIGNED-OFF scene shot for this place (library)
    if prior_plate:
        layout = prior_plate                       # RETURNING location this episode: derive from its last-seen state
    elif lib_ref:
        layout = lib_ref                           # KNOWN place from the LIBRARY: build consistent with the approved scene shot
    else:
        layout = sc.get("master")                  # first visit: establish from the master/anchor
        if layout and layout.endswith(f"S{scene_num}_plate.png"):
            layout = None
    loc = sc.get("sceneAnchor") or lib_ref
    prompt, refs = P.build_plate_prompt(sc, episode, scene_num, layout_ref=layout, location_ref=loc, changes=changes, note=note)
    tag = (f"RETURNING — derives from {os.path.basename(prior_plate)} + {len(changes)} world change(s)"
           if prior_plate else "establishing")
    print(f"  scene PLATE ({tag}, no characters) -> {out} | refs={len(refs)}", flush=True)
    cb_gen.generate_image(prompt, refs, "16:9", out)
    return f"media/{out}"

def build_charsheet(pkg_path, scene_num, episode="Ep1", note=""):
    """A2 — build the per-scene CHARACTER-SHEET anchor (clean on-model group line-up). Returns its path."""
    d = json.load(open(pkg_path))
    shots = [s for s in d["shots"] if str(s.get("sceneNumber")) == str(scene_num)]
    sc = P.scene_cfg(episode, str(scene_num))
    out = f"{episode}_S{scene_num}_charsheet.png"
    prompt, refs = P.build_charsheet_prompt(shots, sc, episode, note=note)
    print(f"  A2 character sheet -> {out} | chars={P.scene_characters(shots)} | refs={len(refs)}", flush=True)
    cb_gen.generate_image(prompt, refs, "16:9", out)
    return f"media/{out}"

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) > 1 and sys.argv[1] == "preflight":
        ok = preflight(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Ep1")
        sys.exit(0 if ok else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == "charsheet":
        build_charsheet(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Ep1")
    elif len(sys.argv) > 1 and sys.argv[1] == "plate":
        build_plate(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Ep1")
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1")
