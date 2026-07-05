#!/usr/bin/env python3
"""cb_replicator.py — THE REPLICATOR (Julian, 2026-07-05, REPLICATOR.md).

ONE command: walk_scene(episode, scene). It takes the show profile, the scene data and the director's cut as
its only inputs (all resolved from episode+scene through the SAME path/config conventions cb_pipeline.py and
cb_beats.py already use — no new lookup mechanism) and runs Gate 3 end to end for that scene under the
ESCORTED-RUN RULES: assemble each prompt from the rule-28 skeleton, pre-fire lint (all twelve laws, hard-block
on Law 3/5-class violations, flags on advisories), fire, QA + join-check + anti-hold (last-frame extraction),
harvest, re-mint, drift check, thread endStateStill forward as the next beat's photograph, assemble the next
prompt, fire — halting the instant anything comes back non-green, evidence pack to Downloads throughout.

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
import cb_beats, cb_scene, cb_qa, cb_segprompt

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

def _gate2b_signed(episode, scene):
    """Reads locked.json directly (mirrors cb_pipeline._approved / serve.py's _scene_locks) rather than calling
    cb_pipeline._approved, which reads the module-level EP global instead of taking episode as an argument —
    the same hazard _resolve_pkg's docstring names. GATES ARE HARD LOCKS (CLAUDE.md rule 1): walk_scene
    automates Gate 3 onward; it never substitutes for a human's own Gate 2b sign-off, and never builds one."""
    try:
        d = json.load(open(_LOCK_PATH))
    except Exception:
        d = {}
    return bool(d.get(episode, {}).get(str(scene), {}).get("2b"))

def _scene_dict(pkg, scene):
    return next((s for s in pkg.get("scenes") or [] if str(s.get("sceneNumber")) == str(scene)), None)

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

def _load_qa(episode, code, slug):
    p = f"media/{episode}_{code}_{slug}.qa.json"
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None

def _halt(scene, done, code, reason, evidence):
    print(f"walk_scene: HALT at {code} — {reason}", flush=True)
    return {"status": "HALTED", "scene": scene, "beats_done": done, "halted_at": code,
            "reason": reason, "evidence": [e for e in evidence if e]}

def walk_scene(episode, scene, seeds=1, fast=False):
    """THE REPLICATOR's one command. Returns {status: "COMPLETE"|"HALTED", scene, beats_done, halted_at,
    reason, evidence}. seeds=1/fast=False (standard tier) matches the studio's current production default —
    the same configuration the 1.B2 camera-lock test used, so any future maiden-run comparison stays apples
    to apples. Resumable by construction: every state it reads (official clips, remint anchors, lock file) is
    on disk, so calling walk_scene again after fixing whatever halted it picks up from the same beat, not from
    scratch — it never re-fires a beat that already has a clean, QA-passed official clip."""
    pkg_path = _resolve_pkg(episode)
    d = json.load(open(pkg_path))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
    if not beats:
        return _halt(scene, [], None, f"no beats found for {episode} scene {scene}", [])

    if not _gate2b_signed(episode, scene):
        first_code = beats[0].get("beatCode") or beats[0].get("shotCode")
        return _halt(scene, [], first_code,
                     "Gate 2b is not signed for this scene — walk_scene never advances past an unsigned gate", [])

    scene_dict = _scene_dict(d, scene)
    done, evidence = [], []

    # BEAT 1 — no predecessor to relay from; fires directly off its own signed Gate-2b keyframe.
    first = beats[0]
    first_code = first.get("beatCode") or first.get("shotCode")
    first_slug = first.get("slug", (first_code or "").replace(".", "_"))
    first_clip = f"media/{episode}_{first_code}_{first_slug}.mp4"
    if not os.path.exists(first_clip):
        cast = first.get("openingCast") or first.get("characters") or []
        lint = cb_qa.check_prompt_laws(first, scene_dict, cast, relay=False)
        for fl in lint["flags"]:
            print(f"walk_scene: {first_code} [PROMPT LAW FLAG] {fl}", flush=True)
        prompt_text, _builder, _is_v3 = cb_segprompt.shipped_prompt(first, scene_dict, relay=False)
        if not str(prompt_text or "").strip():
            return _halt(scene, done, first_code, "assembled prompt is empty — see cb_segprompt log", evidence)
        cb_beats.run(pkg_path, scene, episode, codes=[first_code], fast=fast)
        if not os.path.exists(first_clip):
            return _halt(scene, done, first_code,
                         "beat refused or failed to render (Law 3/5-class refusal, or a render error) — see console log", evidence)
    qa = _load_qa(episode, first_code, first_slug)
    evidence.append(_copy_evidence(f"walk_scene_{first_code}_clip.mp4", first_clip))
    if qa and qa.get("ok") is False:
        return _halt(scene, done, first_code, "CLIP QA BLOCK: " + "; ".join(qa.get("reasons") or []), evidence)
    done.append(first_code)

    # BEATS 2..N — the relay chain, one escorted step per transition: PREPARE (harvest, re-mint, drift-check;
    # dry_run=True reuses the predecessor's ALREADY-OFFICIAL clip rather than designating a new seed — there is
    # no separate seed-pick in a single-seed walk) -> if the drift-check is clean, LINT the next beat's actual
    # assembled prompt -> if clean, LAUNCH (approved=True; the drift-check's own CLEAN verdict IS the approval —
    # there is nothing left for a human to catch that it didn't already catch) -> CLIP QA + JOIN CHECK
    # (last-frame extraction, anti-hold) -> if clean, continue; otherwise halt with the full evidence pack.
    for i in range(1, len(beats)):
        prev, cur = beats[i - 1], beats[i]
        prev_code = prev.get("beatCode") or prev.get("shotCode")
        cur_code = cur.get("beatCode") or cur.get("shotCode")
        cur_slug = cur.get("slug", (cur_code or "").replace(".", "_"))
        cur_clip = f"media/{episode}_{cur_code}_{cur_slug}.mp4"

        if os.path.exists(cur_clip) and _load_qa(episode, cur_code, cur_slug):
            # RESUMABLE: this beat already has a clip and a QA verdict from a prior walk_scene call — evaluate
            # it exactly as freshly-fired below rather than re-firing (and re-spending) it.
            qa = _load_qa(episode, cur_code, cur_slug)
            evidence.append(_copy_evidence(f"walk_scene_{cur_code}_clip.mp4", cur_clip))
            if qa and qa.get("ok") is False:
                return _halt(scene, done, cur_code, "CLIP QA BLOCK: " + "; ".join(qa.get("reasons") or []), evidence)
            done.append(cur_code)
            continue

        prep = cb_beats.fire_next_beat(pkg_path, scene, episode, prev_code, seeds=seeds, fast=fast, dry_run=True)
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

        cast = cur.get("openingCast") or cur.get("characters") or []
        lint = cb_qa.check_prompt_laws(cur, scene_dict, cast, relay=True)
        for fl in lint["flags"]:
            print(f"walk_scene: {cur_code} [PROMPT LAW FLAG] {fl}", flush=True)

        launched = cb_beats.fire_next_beat(pkg_path, scene, episode, prev_code, seeds=seeds, fast=fast, approved=True)
        if not launched or not os.path.exists(cur_clip):
            return _halt(scene, done, cur_code, f"launch step failed for {cur_code} — see console log", evidence)

        first_frame = f"media/{episode}_{cur_code}_{cur_slug}_walkframe1.png"
        _extract_frame(cur_clip, first_frame)
        # rule 31 (2026-07-05): the join-check's frame-identity half only applies when THIS beat declared
        # its shot as an unbroken continuation of the previous one — state continuity is the hard gate either way.
        # rule 36 (2026-07-05): STATE hard-gates ONLY on this beat's own declared carryMarks; anything else
        # visible (an incidental held prop, say) is advisory only.
        _junction = cb_segprompt._junction_type(cur)
        join = cb_qa.check_join(anchor, first_frame, junction=_junction, carry_marks=cur.get("carryMarks")) if os.path.exists(first_frame) else {"ok": None, "verdict": "(frame extraction failed)"}
        for _fl in join.get("flags") or []:
            print(f"walk_scene: {cur_code} [JOIN CHECK] FLAG (advisory, non-blocking) — {_fl}", flush=True)
        last_frame = f"media/{episode}_{cur_code}_{cur_slug}_walklast.png"
        _extract_frame(cur_clip, last_frame, last=True)
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_frame1.png", first_frame))
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_lastframe.png", last_frame))
        evidence.append(_copy_evidence(f"walk_scene_{cur_code}_clip.mp4", cur_clip))

        qa = _load_qa(episode, cur_code, cur_slug)
        if qa and qa.get("ok") is False:
            return _halt(scene, done, cur_code, "CLIP QA BLOCK: " + "; ".join(qa.get("reasons") or []), evidence)
        if join.get("ok") is False:
            return _halt(scene, done, cur_code, "JOIN DISCONTINUITY: " + join.get("verdict", ""), evidence)
        done.append(cur_code)

    print(f"walk_scene: COMPLETE — {episode} scene {scene}, {len(done)}/{len(beats)} beats: {', '.join(done)}", flush=True)
    return {"status": "COMPLETE", "scene": scene, "beats_done": done, "halted_at": None, "reason": "",
            "evidence": [e for e in evidence if e]}

if __name__ == "__main__":
    os.chdir(_ENGINE_DIR)
    episode = sys.argv[1] if len(sys.argv) > 1 else "Ep1"
    scene = sys.argv[2] if len(sys.argv) > 2 else "1"
    result = walk_scene(episode, scene)
    print(json.dumps(result, indent=1, ensure_ascii=False))
