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
    # DEFINITIVE BYPASS — a beat with a working cb_segprompt.shipped_prompt prose (for_beat_v2, or the loud v1
    # fallback) ships THAT text, never this compact JSON, so the compact validator's opinion of a JSON nobody sends must
    # not block the render. get_seedance_prompt()/render_readiness() already apply exactly this bypass; this
    # function silently lacked it, so a beat render_readiness reported READY_TO_RENDER could still be refused HERE
    # (the function cb_beats.run actually calls to decide whether to render) on a compact-JSON complaint that had
    # nothing to do with the prose actually being sent. Confirmed live: Julian fired Gate 3 on 4 READY beats and
    # all 4 were refused for exactly this reason before this fix.
    definitive = False
    try:
        import cb_segprompt
        _d = json.load(open(pkg_path))
        _scene = None
        if beat.get("sceneNumber") is not None and _d.get("scenes"):
            _sn = str(beat.get("sceneNumber"))
            _scene = next((s for s in _d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
        _, _, definitive = cb_segprompt.shipped_prompt(beat, _scene)   # THE single shipping decision — v2 first, v1 loud fallback
    except Exception:
        definitive = False
    if definitive:
        both_ok = auth["ok"]
        reason = "; ".join([] if auth["ok"] else ["authoring/source: " + x for x in auth["rejects"]])
    else:
        both_ok = auth["ok"] and rep["ok"]
        reason = "; ".join(([] if rep["ok"] else rep["rejects"]) + ([] if auth["ok"] else ["authoring/source: " + x for x in auth["rejects"]]))
    return {"builder": "cb_seedance", "format": "COMPACT_TIMED_JSON", "prompt": prompt, "report": rep, "authoring": r["authoring"],
            "refuse": not both_ok, "reason": reason}

def gate3_dryrun(pkg_path, code, episode="Ep1"):
    """PROMPT-ONLY proof that Gate 3 would use the selected builder — NO Seedance call, NO render. Returns the
    builder, the Episode-Director classification and the validator result for one beat (the acceptance check).
    Mirrors run()'s OWN override logic exactly (cb_segprompt.shipped_prompt wins whenever it returns non-empty
    prose) — this used to report ONLY the cb_seedance fallback, which is NOT what actually fires for a definitive
    beat. THE SAME shipped_prompt() call as run() and get_seedance_prompt() — preview == fire, provably."""
    d = json.load(open(pkg_path))
    beat = next(b for b in (d.get("beats") or d.get("shots") or [])
                if (b.get("beatCode") or b.get("shotCode")) == code)
    audio_dur = _audio_dur(os.path.join("media", f"vo_{episode}_{code}.mp3"))
    prep = gate3_prepare(pkg_path, beat, episode, audio_dur=audio_dur)
    a = prep.get("authoring") or {}
    prompt, builder, raw = prep["prompt"], prep["builder"], False
    try:
        import cb_segprompt, cb_scene
        _scene = None
        if d.get("scenes"):
            _sn = str(beat.get("sceneNumber"))
            _scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
        # relay-aware (rule 21) — mirrors run()'s own check, so the preview matches what would actually fire
        _scene_beats = [b for b in (d.get("beats") or d.get("shots") or [])
                        if str(b.get("sceneNumber")) == str(beat.get("sceneNumber"))]
        _, _relay_status, _ = cb_scene.relay_source_for(_scene_beats, code, episode)
        _def, _builder_label, _ = cb_segprompt.shipped_prompt(beat, _scene, relay=(_relay_status == "relay"))
        if _def:
            prompt, builder, raw = _def, _builder_label, True
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
        # THE CONTINUITY BLOCK on banned world vocabulary (Fable's code review, 2026-07-03) — a corrected-away
        # scene name/description reappearing anywhere (e.g. Scene 1's old "Rainforest Pollen Run") is drift, not
        # a taste call; hard-blocks the render exactly like the scene-cache staleness check above.
        import cb_qa
        vocab = cb_qa.check_scene_vocabulary(pkg_path, beat.get("sceneNumber"), episode)
        if not vocab["ok"]:
            blockers.append("banned vocabulary: " + vocab["verdict"])
    if not g["authoring_validator"]["ok"] or rstat == "NEEDS_SOURCE_DATA_FIX":
        status = "NEEDS_SOURCE_DATA_FIX"
    elif blockers:
        status = "BLOCKED"
    else:
        status = "READY_TO_RENDER"
    return {"status": status, "blockers": blockers}

def run(pkg_path, scene_num, episode="Ep1", codes=None, fast=False):
    """GATE 3 (beat-native) — each beat is ALREADY a 10-12s unit (the Director designed it). Render each beat as
    ONE Seedance take from its OWN signed-off opening keyframe (Gate 2b) using the beat's i2vPrompt (the Director's
    multi-cut take prompt — Seedance directs the internal cuts). Then stitch the scene. NOT eight per-shot clips.
    fast=True is RENDER ECONOMY LAW (Julian, 2026-07-03) — fal's cheaper/quicker Seedance endpoint variant, for
    exploratory seeds; leave False for a beat's real delivery fire."""
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
        # THE RELAY CHAIN (Julian, 2026-07-03, CLAUDE.md rule 21): a continuation beat whose predecessor already
        # has a rendered clip opens directly off that clip's HARVESTED SETTLE FRAME for @图1 — no Gate-2b keyframe
        # generation for THIS beat at all. Falls back to the beat's own Gate-2b keyframe (unchanged behaviour)
        # when there's no predecessor (the scene's first beat) or the predecessor has no clip yet to harvest from.
        import cb_scene
        relay_frame, relay_status, relay_prev = cb_scene.relay_source_for(beats, code, episode)
        if relay_status == "relay":
            start = relay_frame
            print(f"  {code}: RELAY CHAIN — opening off {relay_prev}'s harvested settle frame ({os.path.basename(start)}), no keyframe generation for this beat", flush=True)
        else:
            start = f"media/{episode}_{code}_{slug}.png"          # the beat's OWN opening keyframe (Gate 2b)
            if relay_status == "no_predecessor_clip":
                print(f"  {code}: relay not ready ({relay_prev} has no rendered clip yet) — falling back to this beat's own keyframe", flush=True)
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
        # ── BIBLE (Gate 3): the DEFINITIVE Seedance prompt comes from cb_segprompt.shipped_prompt — for_beat_v2
        #    (the faithful translator: motionTempo/pauseHold/physicalFeeling/soundIntent/light/cameraArc/speaker map)
        #    is THE shipping builder; for_beat (v1) is a loud, logged fallback only if v2 returns empty. Same call
        #    the studio preview (gate3_dryrun/get_seedance_prompt) uses → preview == fire, provably. Sent VERBATIM (raw).
        builder_label = prep["builder"]
        try:
            import cb_segprompt
            _scene = None
            if d.get("scenes"):
                _sn = str(b.get("sceneNumber"))
                _scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
            _def, _builder_label, _ = cb_segprompt.shipped_prompt(b, _scene, relay=(relay_status == "relay"))   # THE single routing point — identical to the studio preview path
            if _def:
                prompt = _def; raw = True; builder_label = _builder_label
        except Exception as _se:
            print(f"  {code}: cb_segprompt unavailable ({str(_se)[:80]}) — falling back to {prep['builder']}", flush=True)
        print(f"  {code}: prompt builder = {builder_label}"
              + (f" | director_mode={prep['authoring']['director_mode']} shot_style={prep['authoring']['shot_style']}" if (not raw and prep.get("authoring")) else ""), flush=True)
        empty = (not (prompt.get("visual_prompt") or prompt.get("timeline") or prompt.get("direction") or prompt.get("cuts") or prompt.get("subject") or prompt.get("action"))
                 if isinstance(prompt, dict) else not str(prompt or "").strip())
        if empty:
            print(f"  {code}: empty Seedance prompt — skipping", flush=True); continue
        dur = int(b.get("durationSec") or 11); dur = max(8, min(15, dur))   # a take ≤~15s holds 1-3 whole moments
        out = f"{episode}_{code}_{slug}.mp4"
        # THE SAME character list cb_segprompt.shipped_prompt used to build the @图N role labels (openingCast, falling back
        # to characters) — MUST match exactly, or the uploaded image at position N no longer corresponds to the @图N
        # identity the prompt text asserts (e.g. a beat where openingCast omits/reorders someone in `characters`
        # would silently upload the wrong species/character at that reference slot).
        _chars = b.get("openingCast") or b.get("characters") or []
        imgs = [start] + [a for c in _chars if (a := _anchor(c))]
        if relay_status == "relay":
            # THE RELAY CHAIN's 4th reference (CLAUDE.md rule 21): the scene's plate anchors the world's canonical
            # look/palette/light WITHOUT forcing the frame (the harvested settle already IS the frame) — @图1 is
            # the harvested settle, @图2/@图3... the character turnarounds, the plate always comes last.
            _plate = f"media/{episode}_S{scene_num}_plate.png"
            if os.path.exists(_plate):
                imgs.append(_plate)
        # T2 ruling (2026-07-02, Julian): a temporary state resolves WITHIN the take it started in — it never carries
        # across a take boundary. The continuity-tail chaining (appending the previous clip's last frame as a
        # reference + a "flow continuously from it" instruction) is retired; each take starts clean from its own keyframe.
        said = " | ".join(f"{l['character']}: {l['text']}" for l in track["lines"]) if track else "(no dialogue)"
        aud = [track["track"]] if (track and track.get("track")) else None
        print(f"  beat {code}: {dur}s ref2vid | audio {audio_dur:.1f}s -> hold {max(0.0, dur - audio_dur):.1f}s | imgs={len(imgs)} | "
              f"V3 {'@Audio1 lip-sync' if aud else 'none'}; Seedance scores SFX+music\n         {said}", flush=True)
        try:
            cb_gen.generate_video_seedance_ref(prompt, imgs, audio_urls=aud, duration=dur, out=out, raw_prompt=raw, fast=fast)
            clips.append(f"media/{out}")
            try:    # THE HARVEST doctrine (Julian, 2026-07-03 — "ending frames are harvested, never composed"):
                    # sample the clip's settle window and keep the SHARPEST frame, not a blind EOF grab. This is
                    # what the NEXT beat's relay opens from (rule 21). Fail-open: an extraction hiccup must never
                    # break the render loop or the stitch.
                    import cb_scene
                    settlef = cb_scene.harvest_settle_frame(episode, code, slug)
                    print(f"  [HARVEST] {code}: {'settle frame -> ' + settlef if settlef else 'skipped (extraction failed)'}", flush=True)
            except Exception as ee:
                print(f"  beat {code}: settle-frame harvest skipped ({str(ee)[:120]})", flush=True)
            try:    # THE JOIN CHECK (item EIGHT, Julian, 2026-07-03) — automatic, advisory: compare this clip's
                    # ACTUAL first rendered frame against the settle it was told to open from, before this ever
                    # reaches Julian's review. Only meaningful for a relay beat (one that had a carried settle to
                    # check against); a first-of-scene beat has nothing to compare against.
                    if relay_status == "relay" and relay_frame:
                        import cb_qa, subprocess, tempfile
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as _tf:
                            _first = _tf.name
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"media/{out}",
                                        "-vframes", "1", _first], capture_output=True)
                        jv = cb_qa.check_join(relay_frame, _first)
                        print(f"  [JOIN CHECK] {code}: {'CONTINUOUS' if jv['ok'] else 'BROKEN'} — {jv['verdict'][:200]}", flush=True)
                        os.remove(_first)
            except Exception as je:
                print(f"  beat {code}: join check skipped ({str(je)[:120]})", flush=True)
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

def fire_next_beat(pkg_path, scene_num, episode, winner_code, winner_seed_path=None, seeds=2, dry_run=False, approved=False):
    """THE RELAY — the ONE serial-advance function (Julian, 2026-07-03, item ONE). Takes Julian's WINNER for the
    beat just decided (winner_code + the exact seed file he picked), designates it as that beat's official signed
    clip, harvests its settle frame, RE-MINTS it (Julian's ruling, 2026-07-03 — standard for every link now, not
    QA-triggered; see cb_scene.remint_settle_frame), runs the drift check (cb_qa.check_remint), then STOPS —
    presenting the cleaned anchor for Julian's approval. It does NOT fire the next beat until called again with
    approved=True. No parallel beats, no auto-advance: production within a scene is strictly serial through
    Julian's sign-offs.

    dry_run=True (Fable's code review, 2026-07-03, item TWO — "prove the relay injection"): NO file mutation
    (winner_seed_path is ignored; harvests from winner_code's CURRENT official clip, whatever is already there),
    but the harvest + re-mint + drift-check ARE real (they only read the clip and write derived images). Returns
    {prompt, builder, images, ...} built from the re-minted anchor for inspection instead of firing.

    approved=True: skips designation/harvest/re-mint (reuses the anchor an earlier, unapproved call already
    produced) and fires the next beat's `seeds` takes, render economy law. Call this only after you have actually
    looked at the re-minted anchor from the prepare call."""
    import shutil, cb_scene, cb_segprompt, cb_qa
    d = json.load(open(pkg_path))
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: str(b.get("beatCode") or b.get("shotCode") or ""))
    idx = next((i for i, b in enumerate(beats) if (b.get("beatCode") or b.get("shotCode")) == winner_code), None)
    if idx is None:
        print(f"fire_next_beat: {winner_code} not found in scene {scene_num}", flush=True); return None
    if idx + 1 >= len(beats):
        print(f"fire_next_beat: {winner_code} is the scene's last beat — nothing to fire next", flush=True); return None

    wb = beats[idx]
    w_slug = wb.get("slug", (winner_code or "").replace(".", "_"))
    official = f"media/{episode}_{winner_code}_{w_slug}.mp4"
    remint_path = f"media/{episode}_{winner_code}_{w_slug}_remint.png"
    next_b = beats[idx + 1]
    next_code = next_b.get("beatCode") or next_b.get("shotCode")
    next_slug = next_b.get("slug", (next_code or "").replace(".", "_"))

    if not approved:
        # PHASE 1 — PREPARE: designate (unless dry_run), harvest, RE-MINT, drift-check, then STOP for approval.
        if dry_run:
            print(f"fire_next_beat [DRY RUN]: using {winner_code}'s CURRENT official clip as-is (no file changes)", flush=True)
            if not os.path.exists(official):
                print(f"fire_next_beat [DRY RUN]: {official} doesn't exist yet — nothing to harvest", flush=True); return None
        else:
            # DESIGNATE THE WINNER — copy Julian's picked seed to the beat's OFFICIAL clip path (what every
            # downstream consumer — the relay, the stitch, the QA — treats as "this beat's signed clip").
            if not winner_seed_path or not os.path.exists(winner_seed_path):
                print(f"fire_next_beat: winner seed {winner_seed_path!r} not found", flush=True); return None
            shutil.copyfile(winner_seed_path, official)
            print(f"fire_next_beat: {winner_code} winner designated -> {official} (from {winner_seed_path})", flush=True)

        # HARVEST — the sharpest frame in the winner's settle window. Real in both modes (only reads the clip and
        # writes a derived _settle.png — never touches the official clip itself).
        settlef = cb_scene.harvest_settle_frame(episode, winner_code, w_slug)
        print(f"fire_next_beat: harvested -> {settlef or '(FAILED — check the clip)'}", flush=True)
        if not settlef:
            print("fire_next_beat: cannot proceed without a harvested settle frame; stopping.", flush=True); return None

        # RE-MINT — standard for every link now (Julian's ruling, 2026-07-03, superseding the earlier NB2-refresh
        # rejection). A real NB2 call in both modes — the restoration pass is the thing being proven/prepared.
        cast = wb.get("openingCast") or wb.get("characters") or []
        remint_out = cb_scene.remint_settle_frame(episode, winner_code, w_slug, cast, settlef)
        print(f"fire_next_beat: re-minted -> {remint_out or '(FAILED)'}", flush=True)
        if not remint_out:
            print("fire_next_beat: cannot proceed without a re-minted anchor; stopping.", flush=True); return None

        turnarounds = [a for c in cast if (a := _anchor(c))]
        drift = cb_qa.check_remint(settlef, remint_out, turnarounds)
        print(f"fire_next_beat: RE-MINT DRIFT CHECK -> {'CLEAN' if drift['ok'] else 'BLOCK'} — {drift['verdict']}", flush=True)

        if dry_run:
            # PROVE THE INJECTION — the next beat's real shipped prompt (relay=True), @图1 = the re-minted anchor.
            _scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(scene_num)), None)
            prompt, builder, is_v3 = cb_segprompt.shipped_prompt(next_b, _scene, relay=True)
            _chars = next_b.get("openingCast") or next_b.get("characters") or []
            imgs = [remint_out] + [a for c in _chars if (a := _anchor(c))]
            _plate = f"media/{episode}_S{scene_num}_plate.png"
            if os.path.exists(_plate):
                imgs.append(_plate)
            print(f"fire_next_beat [DRY RUN]: {next_code} shipped prompt (builder={builder}):\n{prompt}", flush=True)
            print(f"fire_next_beat [DRY RUN]: would upload {len(imgs)} images: {imgs}", flush=True)
            print(f"=== fire_next_beat [DRY RUN] complete for {next_code} — nothing fired, nothing mutated. ===", flush=True)
            return {"prompt": prompt, "builder": builder, "is_v3": is_v3, "images": imgs, "harvested": settlef,
                    "remint": remint_out, "drift_check": drift, "next_code": next_code}

        print(f"=== fire_next_beat STOPPED — {winner_code}'s cleaned anchor is ready for your approval:\n"
              f"    {remint_out}\n"
              f"    Review it, then call fire_next_beat(..., approved=True) to launch {next_code}. Sign nothing else. ===",
              flush=True)
        return {"harvested": settlef, "remint": remint_out, "drift_check": drift, "next_code": next_code}

    # PHASE 2 — approved=True: the anchor was already prepared; this call's only job is to launch.
    if not os.path.exists(remint_path):
        print(f"fire_next_beat: approved=True but no re-minted anchor at {remint_path} — call without approved "
              f"first to prepare it.", flush=True); return None
    print(f"fire_next_beat: {winner_code}'s re-minted anchor APPROVED -> launching {next_code}", flush=True)
    official_next = f"media/{episode}_{next_code}_{next_slug}.mp4"
    results = []
    for i in range(1, seeds + 1):
        print(f"fire_next_beat: {next_code} — seed {i}/{seeds} (fast endpoint, render economy law)", flush=True)
        run(pkg_path, scene_num, episode, codes=[next_code], fast=True)
        seed_out = f"media/{episode}_{next_code}_seed{i}.mp4"
        if os.path.exists(official_next):
            shutil.copyfile(official_next, seed_out)
            official_qa = f"media/{episode}_{next_code}_{next_slug}.qa.json"
            if os.path.exists(official_qa):    # preserve THIS seed's own QA verdict — the next loop iteration
                shutil.copyfile(official_qa, f"media/{episode}_{next_code}_seed{i}.qa.json")  # overwrites official_qa before it's copied
            results.append(seed_out)
            print(f"  -> {seed_out}", flush=True)
        else:
            print(f"  {next_code} seed {i}: no clip produced — check the render log above", flush=True)
    print(f"=== fire_next_beat STOPPED after {next_code} ({len(results)}/{seeds} seeds) — no auto-advance. "
          f"Pick a winner, then call fire_next_beat again. Sign nothing. ===", flush=True)
    return results

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
