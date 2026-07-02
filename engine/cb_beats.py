#!/usr/bin/env python3
"""Scene BEAT driver — one Seedance take per BEAT (10-12s), rendered from the beat's own signed-off opening keyframe.

THE RULE: each beat is ONE Seedance reference-to-video generation — Seedance directs its OWN internal cuts, camera and
timing (that's where the flow comes from) — chained last-frame -> next-beat start, then the scene is assembled.

THE PROMPT (Gate 3, signed off): the DEFINITIVE 6-section prose from cb_segprompt (REFERENCE LAW -> SCENE -> ACTION ->
CAMERA -> AUDIO -> NEGATIVES) is THE prompt for any beat that has a segment — references are law, Seedance does the heavy
lifting. Beats with no segment yet fall back to the cb_seedance compact. There is NO other builder (the old
cb_prompts.seedance_json JSON path was removed). THE VOICE RIDES IN THE RENDER: the ElevenLabs V3 track is supplied as
@Audio1 and the characters speak it (lip-synced) — it is NOT swapped in Post.

    python3 cb_beats.py <package.json> <sceneNumber> [episode=Ep1]
"""
import os, sys, json, subprocess
import cb_gen, cb_prompts as P, cb_voice, cb_seedance

def _audio_dur(path):
    """Exact duration (seconds) of an audio file via ffprobe — drives the per-beat action/HOLD math (Ticket 3)."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30)
        return round(float(out.stdout.strip()), 2)
    except Exception:
        return 0.0

def _anchor(c):
    """Each character's identity reference for ref2vid lip-sync (the locked turnaround)."""
    try:
        a = P.char_identity_ref(c)
        return a if a and os.path.exists(a) else None
    except Exception:
        return None

def gate3_prepare(pkg_path, beat, episode="Ep1", audio_dur=0.0):
    """SAFE Gate-3 prompt source selector for beats WITHOUT a cb_segprompt segment — NEVER calls Seedance. The ONLY
    builder is cb_seedance (COMPACT_TIMED_JSON); a manual seedancePromptOverride is honoured verbatim (stale-guarded).
    The old cb_prompts.seedance_json JSON builder has been REMOVED — there is no way to select it. (Beats that DO have a
    cb_segprompt segment never reach here for their final prompt: cb_beats.run overrides with the definitive prose.)
    Returns {builder, prompt, report, authoring, refuse, reason}."""
    code = beat.get("beatCode") or beat.get("shotCode")
    ovr = str(beat.get("seedancePromptOverride") or "").strip()
    if ovr:
        try: prompt = json.loads(ovr)            # legacy JSON override
        except Exception: prompt = ovr            # flattened-text override (the current format)
        stale = cb_seedance.detect_stale_prompt(prompt)   # the stale guard applies to overrides too — no old language sneaks in
        return {"builder": "manual_override", "prompt": prompt,
                "report": {"ok": not stale, "rejects": stale, "warnings": ["manual override — bypasses the cb_seedance build"], "length": len(ovr)},
                "authoring": None, "refuse": bool(stale),
                "reason": ("override contains stale language: " + "; ".join(stale)) if stale else ""}
    r = cb_seedance.build_for_beat(pkg_path, code, episode)
    fmt = os.environ.get("SEEDANCE_PROMPT_FORMAT", "compact")   # compact (COMPACT_TIMED_JSON) is the ONLY shipping format
    if fmt != "compact":                          # the flattened production-bible prompt is REVIEW/DEBUG only — never shipped
        return {"builder": "cb_seedance", "format": "FLATTENED_REVIEW", "prompt": None,
                "report": {"ok": False, "rejects": [f"format {fmt!r} is review/debug only — the shipping format MUST be COMPACT_TIMED_JSON"],
                           "warnings": [], "length": 0},
                "authoring": r["authoring"], "refuse": True,
                "reason": "shipping format must be COMPACT_TIMED_JSON (SEEDANCE_PROMPT_FORMAT=full is review/debug only)"}
    prompt, rep = r["compact"], r["compact_report"]
    auth = r["report"]                            # render needs BOTH: the authoring/source validator AND the shipping format
    both_ok = auth["ok"] and rep["ok"]
    reason = "; ".join(([] if rep["ok"] else rep["rejects"]) + ([] if auth["ok"] else ["authoring/source: " + x for x in auth["rejects"]]))
    return {"builder": "cb_seedance", "format": "COMPACT_TIMED_JSON", "prompt": prompt, "report": rep, "authoring": r["authoring"],
            "refuse": not both_ok, "reason": reason}

def gate3_dryrun(pkg_path, code, episode="Ep1"):
    """PROMPT-ONLY proof that Gate 3 would use the selected builder — NO Seedance call, NO render. Returns the
    builder, the Episode-Director classification and the validator result for one beat (the acceptance check).
    Mirrors run()'s OWN override logic exactly (cb_segprompt.for_beat wins whenever it returns non-empty prose) —
    this used to report ONLY the cb_seedance fallback, which is NOT what actually fires for a definitive beat."""
    d = json.load(open(pkg_path))
    beat = next(b for b in (d.get("beats") or d.get("shots") or [])
                if (b.get("beatCode") or b.get("shotCode")) == code)
    audio_dur = _audio_dur(os.path.join("media", f"vo_{episode}_{code}.mp3"))
    prep = gate3_prepare(pkg_path, beat, episode, audio_dur=audio_dur)
    a = prep.get("authoring") or {}
    prompt, builder, raw = prep["prompt"], prep["builder"], False
    try:
        import cb_segprompt
        _scene = None
        if d.get("scenes"):
            _sn = str(beat.get("sceneNumber"))
            _scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
        _def = cb_segprompt.for_beat(beat, _scene)
        if _def:
            prompt, builder, raw = _def, "cb_segprompt (DEFINITIVE)", True
    except Exception:
        pass
    return {"builder": builder, "format": ("DEFINITIVE_PROSE" if raw else prep.get("format", "?")), "beat": code,
            "refuse": (False if raw else prep["refuse"]), "reason": ("" if raw else prep["reason"]),
            "director_mode": a.get("director_mode"), "audience_feeling_target": a.get("audience_feeling_target"),
            "physical_action_archetype": a.get("physical_action_archetype"),
            "shot_style": a.get("shot_style"), "gag_lock": a.get("script_gag_lock_id"),
            "validator_ok": (True if raw else prep["report"]["ok"]), "rejects": ([] if raw else prep["report"]["rejects"]),
            "length": (len(prompt) if raw else prep["report"].get("length")), "prompt": prompt}

def render_readiness(pkg_path, beat_code, episode="Ep1"):
    """PERMANENT RENDER GATE. READY_TO_RENDER requires BOTH the authoring/full validator AND the compact validator to
    pass (a clean compact never overrides failing source data) + archetype + keyframe + clean audio. A failing
    authoring/source validator yields NEEDS_SOURCE_DATA_FIX. Returns {status, blockers}."""
    g = cb_seedance.get_seedance_prompt(pkg_path, beat_code, mode="render", episode=episode)
    a = g["authoring"]; blockers = []
    definitive = bool(g.get("raw")) or "cb_segprompt" in str(g.get("builder", ""))   # a definitive cb_segprompt beat sends
    #    hand-authored PROSE — the cb_seedance validators/archetype don't apply (get_seedance_prompt already passes them).
    if not g["authoring_validator"]["ok"]:
        blockers.append("authoring/source validator FAIL: " + "; ".join(g["authoring_validator"]["rejects"]))
    if not g["compact_validator"]["ok"]:
        blockers.append("compact validator FAIL: " + "; ".join(g["compact_validator"]["rejects"]))
    if not definitive and (not a.get("physical_action_archetype") or a.get("physical_action_archetype") == cb_seedance.NEEDS_EXPLICIT):
        blockers.append("physical_action_archetype missing/unresolved")
    rstat = g.get("readiness_status")
    if rstat == "NEEDS_KEYFRAME_REVIEW":
        blockers.append("keyframe not yet built/approved for this beat")
    d = json.load(open(pkg_path))
    beat = next((b for b in (d.get("beats") or d.get("shots") or []) if (b.get("beatCode") or b.get("shotCode")) == beat_code), None)
    slug = (beat.get("slug") if beat else None) or beat_code.replace(".", "_")
    if not os.path.exists(f"media/{episode}_{beat_code}_{slug}.png"):
        blockers.append("keyframe missing")
    va = [p for p in cb_voice.audit_attribution(pkg_path) if p.startswith(beat_code)]
    if va:
        blockers.append("audio attribution: " + "; ".join(va))
    # T33 Ruling 3: config/locations.json is a CACHE of the beat package's own scene data — a stale cache used to
    # diverge silently (a beat-package scene edit never reaching keyframe/plate/Seedance prompts, with no signal).
    # Now a hard BLOCK, not a silent divergence.
    if beat is not None:
        stale = P.scene_cache_stale(episode, beat.get("sceneNumber"), pkg_path=pkg_path)
        if stale:
            blockers.append("scene cache: " + stale)
    if not g["authoring_validator"]["ok"] or rstat == "NEEDS_SOURCE_DATA_FIX":
        status = "NEEDS_SOURCE_DATA_FIX"
    elif blockers:
        status = "BLOCKED"
    else:
        status = "READY_TO_RENDER"
    return {"status": status, "blockers": blockers}

def run(pkg_path, scene_num, episode="Ep1", codes=None):
    """GATE 3 (beat-native) — each beat is ALREADY a 10-12s unit (the Director designed it). Render each beat as
    ONE Seedance take from its OWN signed-off opening keyframe (Gate 2b) using the beat's i2vPrompt (the Director's
    multi-cut take prompt — Seedance directs the internal cuts). Then stitch the scene. NOT eight per-shot clips."""
    d = json.load(open(pkg_path)); scene_num = str(scene_num)
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == scene_num]
    if not beats:
        print(f"BEAT driver: no beats for {episode} scene {scene_num}"); return []
    print(f"BEAT driver: {episode} scene {scene_num} — {len(beats)} beats (one 10-12s take each, from its own keyframe)", flush=True)
    clips = []
    for _i, b in enumerate(beats):
        code = b.get("beatCode") or b.get("shotCode"); slug = b.get("slug", (code or "").replace(".", "_"))
        if codes and code not in codes:
            continue
        start = f"media/{episode}_{code}_{slug}.png"          # the beat's OWN opening keyframe (Gate 2b)
        if not os.path.exists(start):
            print(f"  {code}: opening keyframe missing ({os.path.basename(start)}) — fire Gate 2b first; skipping", flush=True); continue
        # THE PERMANENT RENDER GATE — was computed by render_readiness() but never actually CALLED anywhere, so a
        # beat that failed authoring/compact validation or had no built keyframe could render anyway with nothing
        # to catch it. Now actually gates.
        _ready = render_readiness(pkg_path, code, episode)
        if _ready["status"] != "READY_TO_RENDER":
            print(f"  {code}: NOT READY ({_ready['status']}) — {'; '.join(_ready['blockers'])}; skipping (no clip)", flush=True); continue
        # ── TICKET 3 — AUDIO-FIRST: build + measure THIS beat's V3 voice BEFORE the prompt, so the action/HOLD timeline is
        #    computed from its REAL audio length (per-beat, decoupled from episode runtime). Then VOICE-FLIP (Ticket 2):
        #    inject that track as @Audio1 so Seedance lip-syncs to it; generate_audio stays ON for SFX + the underscore.
        track = None
        # The Director's Pass directs the VOICE too — the SAME single source every voice path uses, so the ElevenLabs acting matches the picture.
        _vd = cb_seedance.director_voice_direction(pkg_path, code, episode)
        # CB_REUSE_VOICE — keep an already-approved @Audio1 EXACTLY (no re-synthesis) when re-rendering visuals only.
        _vo = str(cb_gen.MEDIA / f"vo_{episode}_{code}.mp3")
        if os.environ.get("CB_REUSE_VOICE") and os.path.exists(_vo):
            track = {"track": _vo, "lines": [], "speakers": []}
            print(f"  {code}: reusing existing voice track (CB_REUSE_VOICE) — no re-synthesis", flush=True)
        else:
            try:
                track = cb_voice.build_dialogue_track(b, out=f"vo_{episode}_{code}.mp3", voice_direction=_vd)
            except Exception as e:
                print(f"  {code}: voice track failed ({str(e)[:120]})", flush=True)
        # T1 (Law 5): the voice lives IN the render. A beat WITH dialogue whose V3 track failed REFUSES to render —
        # no silent fallback to Seedance's native voice, ever. Wordless beats render fine with no track.
        _has_dlg = bool(b.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (b.get("cuts") or []))
        if _has_dlg and not (track and track.get("track")):
            print(f"  {code}: REFUSED — beat has dialogue but no V3 @Audio1 track (Law 5: no native-voice fallback); fix the voice and re-fire", flush=True)
            continue
        audio_dur = _audio_dur(track["track"]) if (track and track.get("track")) else 0.0
        # ── MANUAL OVERRIDE: a human-edited exact Seedance JSON ("Save & use this exact prompt") is sent VERBATIM
        #    (mirrors how build_keyframe_prompt honors keyframePromptOverride). Otherwise build it as now.
        # ── GATE-3 PROMPT SOURCE — the SAFE selector (default cb_seedance; old path refused unless overridden) ──
        prep = gate3_prepare(pkg_path, b, episode, audio_dur=audio_dur)
        if prep["refuse"]:
            print(f"  {code}: Gate 3 REFUSED to render — {prep['reason']}; skipping (no clip)", flush=True); continue
        prompt = prep["prompt"]; raw = False
        # ── BIBLE (Gate 3): the DEFINITIVE Seedance prompt is the 6-section model GENERATED from this beat by
        #    cb_segprompt.for_beat (REFERENCE LAW / SCENE / ACTION / CAMERA / AUDIO / NEGATIVES + the wing law for bees).
        #    Same call the studio preview uses (get_seedance_prompt) → preview == fire. Sent VERBATIM (raw).
        try:
            import cb_segprompt
            _scene = None
            if d.get("scenes"):
                _sn = str(b.get("sceneNumber"))
                _scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
            _def = cb_segprompt.for_beat(b, _scene)   # THE single routing point — identical to the studio preview path
            if _def:
                prompt = _def; raw = True
        except Exception as _se:
            print(f"  {code}: cb_segprompt unavailable ({str(_se)[:80]}) — falling back to {prep['builder']}", flush=True)
        print(f"  {code}: prompt builder = {'cb_segprompt (DEFINITIVE)' if raw else prep['builder']}"
              + (f" | director_mode={prep['authoring']['director_mode']} shot_style={prep['authoring']['shot_style']}" if (not raw and prep.get("authoring")) else ""), flush=True)
        empty = (not (prompt.get("visual_prompt") or prompt.get("timeline") or prompt.get("direction") or prompt.get("cuts") or prompt.get("subject") or prompt.get("action"))
                 if isinstance(prompt, dict) else not str(prompt or "").strip())
        if empty:
            print(f"  {code}: empty Seedance prompt — skipping", flush=True); continue
        dur = int(b.get("durationSec") or 11); dur = max(8, min(15, dur))   # a take ≤~15s holds 1-3 whole moments
        out = f"{episode}_{code}_{slug}.mp4"
        # THE SAME character list cb_segprompt.for_beat used to build the @图N role labels (openingCast, falling back
        # to characters) — MUST match exactly, or the uploaded image at position N no longer corresponds to the @图N
        # identity the prompt text asserts (e.g. a beat where openingCast omits/reorders someone in `characters`
        # would silently upload the wrong species/character at that reference slot).
        _chars = b.get("openingCast") or b.get("characters") or []
        imgs = [start] + [a for c in _chars if (a := _anchor(c))]
        # T2 ruling (2026-07-02, Julian): a temporary state resolves WITHIN the take it started in — it never carries
        # across a take boundary. The continuity-tail chaining (appending the previous clip's last frame as a
        # reference + a "flow continuously from it" instruction) is retired; each take starts clean from its own keyframe.
        said = " | ".join(f"{l['character']}: {l['text']}" for l in track["lines"]) if track else "(no dialogue)"
        aud = [track["track"]] if (track and track.get("track")) else None
        print(f"  beat {code}: {dur}s ref2vid | audio {audio_dur:.1f}s -> hold {max(0.0, dur - audio_dur):.1f}s | imgs={len(imgs)} | "
              f"V3 {'@Audio1 lip-sync' if aud else 'none'}; Seedance scores SFX+music\n         {said}", flush=True)
        try:
            cb_gen.generate_video_seedance_ref(prompt, imgs, audio_urls=aud, duration=dur, out=out, raw_prompt=raw)
            clips.append(f"media/{out}")
            try:    # Gate-3 CLIP QA — automatic, advisory; NEVER let a QA hiccup kill the render loop or the stitch
                import cb_qa
                v = cb_qa.check_clip(b, clip=f"media/{out}", keyframe=start, anchors=imgs[1:],
                                     episode=episode, prompt=prompt,
                                     next_beat=(beats[_i+1] if _i+1 < len(beats) else None))
                print(f"  [CLIP QA] {code}: {v['verdict']}", flush=True)
                with open(f"media/{episode}_{code}_{slug}.qa.json", "w") as _qf:
                    json.dump(v, _qf, indent=2)
            except Exception as qe:
                print(f"  beat {code}: CLIP QA skipped ({str(qe)[:140]})", flush=True)
        except Exception as e:
            print(f"  beat {code}: FAILED — {str(e)[:200]} (continuing)", flush=True)
    if clips:
        if codes:
            # SUBSET re-render (a clip regen on this SAME Gate-3 path). The requested beat clip was already
            # regenerated by the loop above. Only re-stitch the WHOLE scene if EVERY expected beat clip for the
            # scene exists on disk — if ANY are missing, leave the existing scene stitch UNTOUCHED rather than
            # overwrite it with a PARTIAL preview, and report which clips are missing. A full Gate-3 run
            # (codes=None) is unaffected and keeps its original behaviour exactly (below).
            expected = []
            for bb in beats:
                bc = bb.get("beatCode") or bb.get("shotCode"); bs = bb.get("slug", (bc or "").replace(".", "_"))
                expected.append((bc, f"media/{episode}_{bc}_{bs}.mp4"))
            missing = [bc for bc, cp in expected if not os.path.exists(cp)]
            if missing:
                print(f"  subset regen: scene {scene_num} stitch SKIPPED — {len(missing)}/{len(expected)} beat clip(s) "
                      f"missing: {', '.join(missing)}. Existing scene stitch left untouched (no partial preview).", flush=True)
            else:
                stitch([cp for _bc, cp in expected], f"media/{episode}_Scene{scene_num}_beats.mp4")  # all present → full scene, beat order
                print(f"  subset regen: all {len(expected)} beat clips present — scene {scene_num} re-stitched.", flush=True)
        else:
            stitch(clips, f"media/{episode}_Scene{scene_num}_beats.mp4")
    # GATE-3 REVIEW COPY + retake sheet — the timecoded completed animation, to mark up in Gate-4 Retakes (off this sign-off).
    try:
        import cb_post, cb_address
        _stitched = f"media/{episode}_Scene{scene_num}_beats.mp4"
        if os.path.exists(_stitched):
            cb_post.burn_review_overlay(_stitched, cb_address.scene_shot_windows(pkg_path, scene_num, episode),
                                        f"media/{episode}_Scene{scene_num}_REVIEW.mp4")
            cb_address.write_retake_csv(pkg_path, scene_num, episode)
            print("  Gate-3 review copy (timecode + shot burned in) + retake sheet ready — mark up in Gate-4 Retakes.", flush=True)
    except Exception as _e:
        print(f"  Gate-3 review/sheet skipped ({str(_e)[:120]})", flush=True)
    print("=== BEAT DRIVER DONE ===", flush=True)
    return clips

def stitch(clips, out):
    lst = cb_gen.MEDIA / "_beats_concat.txt"
    lst.write_text("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "256k", out], check=True, capture_output=True)
    print(f"  stitched {len(clips)} beats -> {out}", flush=True)
    return out

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) > 1 and sys.argv[1] == "dryrun":     # python3 cb_beats.py dryrun <pkg> <beatCode> [ep] — NO render
        out = gate3_dryrun(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Ep1")
        out_print = {k: v for k, v in out.items() if k != "prompt"}
        print(json.dumps(out_print, indent=1, ensure_ascii=False))
    else:
        run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1")
