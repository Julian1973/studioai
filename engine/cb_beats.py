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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import tools.backup_media as _backup   # off-machine backup on approval (2026-07-08 operational-risk fix)

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
    builder is cb_seedance (COMPACT_TIMED_JSON). The old cb_prompts.seedance_json JSON builder has been REMOVED —
    there is no way to select it. (Beats that DO have a cb_segprompt segment never reach here for their final
    prompt: cb_beats.run overrides with the definitive prose.)
    THE DEAD OVERRIDE, RETIRED (2026-07-07, Julian's Studio-editing feature request): this function used to honour
    a manual `seedancePromptOverride` verbatim — but for every beat that DOES have a cb_segprompt segment (every
    real beat in this production), `cb_beats.run` always recompiled via `cb_segprompt.shipped_prompt` immediately
    after calling this function and overwrote whatever it returned — so the override silently never took effect,
    while the Studio UI's "Save & use this exact prompt" button told the user it had. Removed rather than left as
    a trap; editing now happens on the beat's own `cuts[]` (the Studio's shots editor), which both this function's
    fallback AND the definitive v5 compile always read from — one source of truth, never a shadow copy.
    Returns {builder, prompt, report, authoring, refuse, reason}."""
    code = beat.get("beatCode") or beat.get("shotCode")
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
        _, _relay_status, _relay_prev = cb_scene.relay_source_for(_scene_beats, code, episode)
        _prev_end_state, _prev_carry_marks = None, None
        if _relay_status == "relay" and _relay_prev:
            _prev_b = next((bb for bb in _scene_beats if (bb.get("beatCode") or bb.get("shotCode")) == _relay_prev), None)
            _prev_end_state = _prev_b.get("endStateStill") if _prev_b else None
            _prev_carry_marks = _prev_b.get("carryMarks") if _prev_b else None   # rules 33/34, 2026-07-05
        _def, _builder_label, _ = cb_segprompt.shipped_prompt(beat, _scene, relay=(_relay_status == "relay"),
                                                              prev_end_state_still=_prev_end_state,
                                                              prev_carry_marks=_prev_carry_marks)
        if _def:
            prompt, builder, raw = _def, _builder_label, True
    except Exception:
        pass
    word_count = None
    if raw:
        try:
            import cb_segprompt
            word_count = cb_segprompt._v5_word_count(prompt)
        except Exception:
            pass
    return {"builder": builder, "format": ("DEFINITIVE_PROSE" if raw else prep.get("format", "?")), "beat": code,
            "refuse": (False if raw else prep["refuse"]), "reason": ("" if raw else prep["reason"]),
            "director_mode": a.get("director_mode"), "audience_feeling_target": a.get("audience_feeling_target"),
            "physical_action_archetype": a.get("physical_action_archetype"),
            "shot_style": a.get("shot_style"), "gag_lock": a.get("script_gag_lock_id"),
            "validator_ok": (True if raw else prep["report"]["ok"]), "rejects": ([] if raw else prep["report"]["rejects"]),
            "length": (len(prompt) if raw else prep["report"].get("length")),
            "word_count": word_count,   # THE V5 WORD BUDGET (Julian, 2026-07-06) — printed on every emit
            "prompt": prompt}

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
    # THE RELAY (found live, 2026-07-04 — fire_next_beat's very first real approved=True fire hard-blocked on
    # this): a continuation beat never gets its own keyframe PNG — it opens off its predecessor's harvested/
    # re-minted settle frame instead (cb_scene.relay_source_for). This check used to look ONLY at THIS beat's
    # own keyframe path, which every relay beat correctly never has, silently BLOCKING every relay render while
    # fire_next_beat still reported RELAY_LAUNCHED success (it copies the stale existing official clip to the
    # seed path either way — that copy is not evidence the render happened). Same resolution gate3_dryrun (line
    # ~110) and cb_seedance.build_for_beat already use, so this can't drift from what actually ships.
    kf_path = f"media/{episode}_{beat_code}_{slug}.png"
    if beat is not None:
        try:
            import cb_scene
            _scene_beats = [b for b in (d.get("beats") or d.get("shots") or [])
                            if str(b.get("sceneNumber")) == str(beat.get("sceneNumber"))]
            _relay_frame, _relay_status, _ = cb_scene.relay_source_for(_scene_beats, beat_code, episode)
            if _relay_status == "relay" and _relay_frame:
                kf_path = _relay_frame
        except Exception:
            pass
    if not os.path.exists(kf_path):
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
    # PROMPT LAWS AUDIT (PROMPT_LAWS_AUDIT.md, CLAUDE.md rule 28) — Laws 4/7/8's flag-only authoring checks.
    # Deliberately NOT added to `blockers`: Julian's ruling (2026-07-04) was flag-only for these three, only
    # Law 3's reference-alignment gets a hard block (that one's below, in run()'s imgs assertion — a shifted
    # reference slot is a silent wrong-render, not a taste call). Advisory, additive key — existing callers
    # reading status/blockers are unaffected.
    flags = []
    if beat is not None:
        import cb_qa
        scene = None
        if d.get("scenes"):
            _sn = str(beat.get("sceneNumber"))
            scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
        es = cb_qa.check_endstate_still(beat.get("endStateStill"))
        if not es["ok"]:
            flags.append("Law 4 (endStateStill): " + es["verdict"])
        amb = cb_qa.check_ambience_overlap(beat.get("atmosphere"), (scene or {}).get("ambientBed"))
        if not amb["ok"]:
            flags.append("Law 7 (ambience): " + amb["verdict"])
        cam = cb_qa.check_camera_lock_conflict(beat)
        if not cam["ok"]:
            flags.append("Law 8 (camera lock): " + cam["verdict"])
        # SETTLE-AUTHORING STRENGTHENING (Julian, 2026-07-05, lock-in night) — the beat's own endState must
        # read as its own distinct moment, not a restatement of the predecessor's. Same isolated try/except
        # pattern as the relay keyframe-path lookup above; never breaks render_readiness on a lookup hiccup.
        try:
            import cb_scene
            _scene_beats3 = [b for b in (d.get("beats") or d.get("shots") or [])
                             if str(b.get("sceneNumber")) == str(beat.get("sceneNumber"))]
            _, _relay_status3, _relay_prev3 = cb_scene.relay_source_for(_scene_beats3, beat_code, episode)
            if _relay_status3 == "relay" and _relay_prev3:
                _prev_beat3 = next((bb for bb in _scene_beats3
                                    if (bb.get("beatCode") or bb.get("shotCode")) == _relay_prev3), None)
                settle = cb_qa.check_settle_distinctiveness(beat.get("endState"), (_prev_beat3 or {}).get("endState"))
                if not settle["ok"]:
                    flags.append("Settle distinctiveness: " + settle["verdict"])
        except Exception:
            pass
    return {"status": status, "blockers": blockers, "flags": flags}

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
        for _fl in _ready.get("flags") or []:    # PROMPT LAWS AUDIT flags (Laws 4/7/8) — advisory, never blocks
            print(f"  {code}: [PROMPT LAW FLAG] {_fl}", flush=True)
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
            import cb_segprompt, cb_qa
            _scene = None
            if d.get("scenes"):
                _sn = str(b.get("sceneNumber"))
                _scene = next((s for s in d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
            _prev_end_state, _prev_carry_marks = None, None
            if relay_status == "relay" and relay_prev:
                _prev_b = next((bb for bb in beats if (bb.get("beatCode") or bb.get("shotCode")) == relay_prev), None)
                _prev_end_state = _prev_b.get("endStateStill") if _prev_b else None
                _prev_carry_marks = _prev_b.get("carryMarks") if _prev_b else None   # rules 33/34, 2026-07-05
            try:
                _def, _builder_label, _ = cb_segprompt.shipped_prompt(b, _scene, relay=(relay_status == "relay"),
                                                                      prev_end_state_still=_prev_end_state,
                                                                      prev_carry_marks=_prev_carry_marks)   # THE single routing point — identical to the studio preview path
            except cb_qa.ManifestFieldMissing as _mfm:
                # THE MANIFEST (rule 37, 2026-07-06): a missing TECHNICAL-contract field is a REFUSAL, never a
                # reason to degrade to an older/weaker builder — the generic `except Exception` below is for a
                # genuine emitter crash (import error, bug), not for "the data is honestly incomplete." Re-raise
                # so the outer except sees it and skips the beat instead of silently falling back.
                print(f"  {code}: REFUSED — {_mfm} (Manifest BLOCK, rule 37: no retakes, no fires until the "
                      f"beat's own data is complete — fix the named field and re-fire)", flush=True)
                continue
            if _def:
                prompt = _def; raw = True; builder_label = _builder_label
        except Exception as _se:
            print(f"  {code}: cb_segprompt unavailable ({str(_se)[:80]}) — falling back to {prep['builder']}", flush=True)
        _wc_note = ""
        if raw:
            try:
                import cb_preflight as _PF
                _wc_note = (f" | {cb_segprompt._v5_word_count(prompt)} words (target {_PF.WORD_BUDGET_TARGET}, "
                            f"hard block {_PF.WORD_BUDGET_BLOCK})")
            except Exception:
                pass
        print(f"  {code}: prompt builder = {builder_label}{_wc_note}"
              + (f" | director_mode={prep['authoring']['director_mode']} shot_style={prep['authoring']['shot_style']}" if (not raw and prep.get("authoring")) else ""), flush=True)
        empty = (not (prompt.get("visual_prompt") or prompt.get("timeline") or prompt.get("direction") or prompt.get("cuts") or prompt.get("subject") or prompt.get("action"))
                 if isinstance(prompt, dict) else not str(prompt or "").strip())
        if empty:
            print(f"  {code}: empty Seedance prompt — skipping", flush=True); continue
        # THE HANDLE DOCTRINE (CLAUDE.md rule 20): every beat renders at HANDLE_TOTAL now, superseding the old
        # per-beat durationSec 8-15s range this line used to clamp to. Found live 2026-07-06 (Julian: "it's meant
        # to be twelve seconds of action, then the rest is doing whatever" — 1.B1's actual render came out ~10s
        # because this line was still using the beat's own stale durationSec (10) as the real API duration
        # parameter, while the shipped v4 prompt's own timing clock unconditionally described a 15s/13s+2s
        # structure — Seedance was told two different lengths at once). durationSec is retired for this purpose.
        try:
            from cb_segprompt import HANDLE_TOTAL as _handle_total
        except Exception:
            _handle_total = 15
        dur = _handle_total
        out = f"{episode}_{code}_{slug}.mp4"
        # THE SAME character list cb_segprompt.shipped_prompt used to build the @图N role labels (openingCast, falling back
        # to characters) — MUST match exactly, or the uploaded image at position N no longer corresponds to the @图N
        # identity the prompt text asserts (e.g. a beat where openingCast omits/reorders someone in `characters`
        # would silently upload the wrong species/character at that reference slot).
        _chars = b.get("openingCast") or b.get("characters") or []
        # LAW 3 HARD ASSERTION (PROMPT_LAWS_AUDIT.md, CLAUDE.md rule 28) — the prompt's @图N labels are built
        # from THIS SAME _chars list, unconditionally, one label per character (cb_segprompt.emit_json_v3 /
        # _v3_subjects). The upload list below used to filter out any character with no resolvable anchor
        # (_anchor() returns None), silently shortening imgs relative to the label count — every later slot,
        # the scene plate especially, would then shift one position left of what the prompt text claims it
        # is. Confirmed live-reachable in PROMPT_LAWS_AUDIT.md's Law 3 finding. Refuse loudly instead of
        # shipping a shifted reference stack — same style as the Law 5 voice-refusal below.
        _missing_anchors = [c for c in _chars if not _anchor(c)]
        if _missing_anchors:
            print(f"  {code}: REFUSED — no resolvable identity reference for {', '.join(_missing_anchors)} "
                  f"(Law 3: @图N labels and the uploaded image list must align 1:1 — a missing anchor here "
                  f"would silently shift every later reference slot, including the scene plate); fix the "
                  f"character's turnaround reference and re-fire", flush=True)
            continue
        imgs = [start] + [a for c in _chars if (a := _anchor(c))]
        # THE PLATE IS A STANDING ANCHOR, NOT A RELAY-ONLY ONE (Julian's ruling, 2026-07-06 — "scene 1, beat 1
        # should have the scene slate, Fuzzby, Zenny, and the keyframe that's been signed off... there
        # shouldn't be any re-mint in... any first opening shot of a scene, because it's starting the role"):
        # the scene's OPENING beat was never re-minted — that part was already correct, it fires straight from
        # its own signed Gate-2b keyframe — but it was missing the scene plate as a 4th reference entirely,
        # gated behind `relay_status == "relay"` for no principled reason. The plate anchors the world's
        # canonical look/palette/light for the WHOLE clip regardless of which beat is firing; a single keyframe
        # only shows what's visible in that one frame, and the plate covers whatever the camera reveals beyond
        # it. By the time ANY beat's own opening image exists (its keyframe, or a relay anchor), Gate 2a (the
        # plate) is already signed too, so this is always available. Confirmed live: cb_scene.keyframe_for
        # already composites the plate into 1.B1's own keyframe for exactly this reason — the beat's actual
        # FIRE was the one place that dropped it. Unconditional now, every beat, opener included.
        _plate = f"media/{episode}_S{scene_num}_plate.png"
        if os.path.exists(_plate):
            imgs.append(_plate)
        # THE VIDEO REFERENCE, RETIRED (Julian, 2026-07-07, watching 1.B2's actual footage — "the video I
        # don't like it either, I think it confuses things"): rule 26's "FIFTH ANCHOR" (2026-07-04, additive
        # video-clip reference alongside the still-frame anchor) is removed. A relay beat now opens from the
        # still-frame anchor only (@图1) — see cb_segprompt.py's module docstring, "THE FIFTH ANCHOR, RETIRED".
        # T2 ruling (2026-07-02, Julian): a temporary state resolves WITHIN the take it started in — it never carries
        # across a take boundary. The continuity-tail chaining (appending the previous clip's last frame as a
        # reference + a "flow continuously from it" instruction) is retired; each take starts clean from its own keyframe.
        said = " | ".join(f"{l['character']}: {l['text']}" for l in track["lines"]) if track else "(no dialogue)"
        aud = [track["track"]] if (track and track.get("track")) else None
        print(f"  beat {code}: {dur}s ref2vid | audio {audio_dur:.1f}s -> hold {max(0.0, dur - audio_dur):.1f}s | imgs={len(imgs)}"
              f" | V3 {'@Audio1 lip-sync' if aud else 'none'}; Seedance scores SFX+music\n         {said}", flush=True)
        try:
            cb_gen.generate_video_seedance_ref(prompt, imgs, audio_urls=aud, video_urls=None, duration=dur, out=out, raw_prompt=raw, fast=fast)
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
            try:    # THE JOIN CHECK (item EIGHT, Julian, 2026-07-03; two-tier per rule 31, 2026-07-05; STATE
                    # scoped to declared carryMarks per rule 36, 2026-07-05) — automatic, advisory: compare
                    # this clip's ACTUAL first rendered frame against the settle it was told to open from,
                    # before this ever reaches Julian's review. Only meaningful for a relay beat (one that had
                    # a carried settle to check against); a first-of-scene beat has nothing to compare against.
                    # junction (rule 31) is THIS beat's own declared junction type — state continuity is the
                    # hard gate either way; frame-identity only applies when this beat declared its shot as an
                    # unbroken continuation of the previous one. carry_marks (rule 36) is THIS beat's own
                    # declared carryMarks — the ONLY thing STATE hard-gates on; anything else visible (a held
                    # prop, say) is advisory only.
                    if relay_status == "relay" and relay_frame:
                        import cb_qa, cb_segprompt, subprocess, tempfile
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as _tf:
                            _first = _tf.name
                        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"media/{out}",
                                        "-vframes", "1", _first], capture_output=True)
                        _junction = cb_segprompt._junction_type(b)
                        jv = cb_qa.check_join(relay_frame, _first, junction=_junction, carry_marks=b.get("carryMarks"))
                        print(f"  [JOIN CHECK] {code} ({_junction}): {'CONTINUOUS' if jv['ok'] else 'BROKEN'} — {jv['verdict'][:200]}", flush=True)
                        for _fl in jv.get("flags") or []:
                            print(f"  [JOIN CHECK] {code}: FLAG (advisory, non-blocking) — {_fl}", flush=True)
                        os.remove(_first)
                        # Persisted (mirrors the CLIP QA .qa.json sidecar below) so the one-render economy's
                        # gate-check in fire_next_beat/walk_scene can read this verdict back without re-deriving
                        # it — the join check itself stays a real vision call, run exactly once per fire.
                        with open(f"media/{episode}_{code}_{slug}.join.json", "w") as _jf:
                            json.dump(jv, _jf, indent=2)
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

def _layer_diagnosis(reasons):
    """Maps a gate failure's own reported text to CLAUDE.md hard rule 3's four-layer taxonomy (keyframe / brief /
    reference / take) — a starting hypothesis for a human's own diagnosis, never a verdict. THE ONE-RENDER
    ECONOMY (Julian, 2026-07-05, PRODUCTION_DOCTRINE.md): a fault that survives one automatic re-fire gets named
    by layer, then STOPS — it is never rolled a third time hoping something different happens."""
    text = " ".join(reasons).lower()
    if "drift" in text or "re-mint" in text or "remint" in text:
        return "keyframe — the anchor image itself may be off (re-mint/drift is a pre-fire check on the still, not the render)"
    if "no clip produced" in text or "render error" in text or "failed to render" in text:
        return "take — the generation itself didn't complete (a transient render failure, not a data problem)"
    if "identity" in text or "reference" in text or "anchor" in text:
        return "reference — an identity/anchor image may not resolve to what the prompt names"
    if "empty" in text or "prompt" in text:
        return "brief — the assembled prompt itself may be malformed or empty"
    return "take — the specific render came out wrong; nothing in the setup itself looks obviously at fault"


# ══════════ APPROVAL AS DATA (GATE3_ANIMATION_DOCTRINE.md §1 Step 7, 2026-07-06) ══════════
# "Approval or rejection is recorded as data on the take... Resume logic reads approval status — never file
# existence." Previously deferred (CLAUDE.md rule 41's infrastructure freeze, LAB_BACKLOG.md item 0) — built
# now on Julian's own explicit instruction. A beat's status is one of four: "unrendered" (no clip at its
# normal path), "pending" (a clip exists, no verdict recorded yet — Julian hasn't looked), "approved" (a
# verdict of approved is on file), "rejected" is a TRANSIENT state that `record_approval` resolves immediately
# by archiving the clip away, so a rejected take never lingers at a path that could be mistaken for ready —
# it becomes "unrendered" again, ready for a corrected re-fire, with the rejection's own record preserved in
# the archive folder (never deleted) for the audit trail.
import datetime

def _approval_path(episode, code, slug):
    return f"media/{episode}_{code}_{slug}.approval.json"

def beat_approval_status(episode, code, slug):
    """Returns ("unrendered"|"pending"|"approved", detail_dict_or_None). Reads the approval sidecar, never
    just trusts the clip's presence — the doctrine's whole point. A clip with no approval sidecar yet is
    "pending", not "approved": Julian's Eye (Step 7) is the gate no machine owns, so an unreviewed take must
    never be treated as ready to anchor/harvest/resume from."""
    clip = f"media/{episode}_{code}_{slug}.mp4"
    if not os.path.exists(clip):
        return "unrendered", None
    ap = _approval_path(episode, code, slug)
    if not os.path.exists(ap):
        return "pending", None
    try:
        data = json.load(open(ap))
    except Exception:
        return "pending", None
    return ("approved" if data.get("approved") else "pending"), data

def record_approval(episode, code, slug, approved, correction=None, scene_num=None):
    """THE Step 7 data-recording call — the ONLY way a take's verdict becomes real. approved=True writes the
    approval sidecar in place; the clip stays exactly where it is (the official, anchorable take).
    approved=False immediately archives the clip + its .qa.json/.join.json/_settle.png/_remint.png sidecars to
    media/archive/<episode>_scene<N>_rejected/<code>_<timestamp>/ together with a .REJECTED.json marker
    naming Julian's own one-sentence correction (doctrine: "rejection names ONE correction in one sentence")
    — then the beat's own normal path is clean again (status reverts to "unrendered"), ready for the data fix
    + one re-fire the doctrine calls for. A rejected take NEVER anchors, sources or resumes anything again —
    archived, not deleted, so the full history survives for the record. Returns the status string that
    resulted ("approved" or "unrendered")."""
    clip = f"media/{episode}_{code}_{slug}.mp4"
    if approved:
        with open(_approval_path(episode, code, slug), "w") as f:
            json.dump({"approved": True, "correction": None,
                       "recorded_at": datetime.datetime.now().isoformat()}, f, indent=2)
        print(f"record_approval: {code} APPROVED — official take stands at {clip}", flush=True)
        # OFF-MACHINE BACKUP (2026-07-08 operational-risk fix): the moment a take becomes official is exactly
        # the moment it's worth protecting — copy it + its sidecars to the 5t drive backup (Julian's own
        # choice of destination) the instant it's signed, rather than relying on someone remembering to run a
        # manual full-sync later. Never blocks or fails the approval itself if the drive isn't mounted.
        for p in [clip, f"media/{episode}_{code}_{slug}.qa.json", f"media/{episode}_{code}_{slug}.join.json",
                  _approval_path(episode, code, slug)]:
            if os.path.exists(p):
                _backup.backup_one(os.path.abspath(p))
        return "approved"

    if scene_num is None:
        scene_num = code.split(".")[0] if "." in str(code) else "unknown"
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    dest = f"media/archive/{episode}_scene{scene_num}_rejected/{code}_{stamp}"
    # THE COLLISION FIX (found in the 2026-07-08 contradiction sweep): the stamp above is second-resolution
    # only, no monotonic counter — two rejections of the SAME beat landing in the same wall-clock second
    # (e.g. a retry-after-exception pattern) used to compute the identical dest, and the os.replace calls
    # below would silently overwrite the first rejection's archived clip + its one-sentence correction, in
    # direct violation of this function's own stated guarantee ("archived, not deleted, so the full history
    # survives for the record"). If dest already exists, disambiguate with a numeric suffix rather than
    # silently clobbering it.
    if os.path.exists(dest):
        n = 2
        while os.path.exists(f"{dest}_{n}"):
            n += 1
        dest = f"{dest}_{n}"
    os.makedirs(dest, exist_ok=True)
    sidecars = [clip, f"media/{episode}_{code}_{slug}.qa.json", f"media/{episode}_{code}_{slug}.join.json",
                f"media/{episode}_{code}_{slug}_settle.png", f"media/{episode}_{code}_{slug}_remint.png",
                _approval_path(episode, code, slug)]
    moved = []
    for p in sidecars:
        if os.path.exists(p):
            target = os.path.join(dest, os.path.basename(p))
            os.replace(p, target)
            moved.append(target)
    with open(os.path.join(dest, f"{code}.REJECTED.json"), "w") as f:
        json.dump({"beat": code, "correction": correction, "recorded_at": datetime.datetime.now().isoformat(),
                   "archived_files": moved}, f, indent=2)
    print(f"record_approval: {code} REJECTED — {correction!r}. Archived to {dest}; beat is unrendered again, "
          f"ready for the data fix + one re-fire.", flush=True)
    return "unrendered"


def _fire_gated(pkg_path, scene_num, episode, next_code, next_slug, fast):
    """ONE economy fire of next_code (cb_beats.run) — then reads back the gates run() itself already ran and
    persisted (CLIP QA's .qa.json, the JOIN CHECK's .join.json) to decide pass/fail, without re-deriving either
    verdict. Returns (clip_path_or_None, ok, reasons)."""
    run(pkg_path, scene_num, episode, codes=[next_code], fast=fast)
    clip = f"media/{episode}_{next_code}_{next_slug}.mp4"
    if not os.path.exists(clip):
        return None, False, ["no clip produced — check the render log above"]
    reasons = []
    qa_p = f"media/{episode}_{next_code}_{next_slug}.qa.json"
    if os.path.exists(qa_p):
        try:
            qa = json.load(open(qa_p))
            if qa.get("ok") is False:
                reasons.append("CLIP QA BLOCK: " + "; ".join(qa.get("reasons") or [qa.get("verdict", "")]))
        except Exception:
            pass
    join_p = f"media/{episode}_{next_code}_{next_slug}.join.json"
    if os.path.exists(join_p):
        try:
            jv = json.load(open(join_p))
            if jv.get("ok") is False:
                reasons.append("JOIN DISCONTINUITY: " + jv.get("verdict", ""))
        except Exception:
            pass
    return clip, (not reasons), reasons


def fire_next_beat(pkg_path, scene_num, episode, winner_code, dry_run=False, approved=False, fast=False):
    """THE RELAY — the ONE serial-advance function (Julian, 2026-07-03, item ONE). Takes winner_code (the beat
    just decided) and prepares the NEXT beat's anchor from winner_code's own official clip — there is exactly
    one official clip per beat now (THE ONE-RENDER ECONOMY, Julian, 2026-07-05: one fire, one automatic re-fire
    on a failed gate, then a hard stop — never a "pick a winner among several" ceremony, which this function
    used to run and no longer does). Harvests the winner's settle frame, then EITHER re-mints it or uses it raw
    — depending on the NEXT beat's own declared junction type (RE-MINT SCOPING, rule 32): a `seamless_continuation`
    next beat gets the NB2 cleanup pass (cb_scene.remint_settle_frame) plus the pre-fire drift check
    (cb_qa.check_remint); an `intentional_next_shot` next beat (the DEFAULT) skips both — its @图1 is a state
    reference, not a pixel-perfect anchor, so re-mint buys nothing, and state continuity is verified AFTER the
    fact by the two-tier join-check on the actual rendered clip instead (cb_qa.check_join, wired into run()).
    Either way, STOPS after preparing the anchor, presenting it for Julian's approval; does NOT fire the next
    beat until called again with approved=True. No parallel beats, no auto-advance: production within a scene
    is strictly serial through Julian's sign-offs.

    fast=False default (Julian, 2026-07-04/07-05, "single seed, standard tier" -> the one-render economy):
    standard tier is now the default for every fire this function makes — the fast/cheap endpoint variant is
    an explicit opt-in for exploratory work outside the escorted line, not the production default.

    dry_run=True (Fable's code review, 2026-07-03, item TWO — "prove the relay injection"): NO file mutation —
    harvests from winner_code's CURRENT official clip, whatever is already there — but the harvest + (conditional)
    re-mint + drift-check ARE real (they only read the clip and write derived images). Returns
    {prompt, builder, images, ...} built from the actual anchor (re-mint or raw harvest, whichever applies) for
    inspection instead of firing.

    approved=True: reuses the anchor an earlier, unapproved call already produced, then fires the next beat under
    the one-render economy — ONE take, ONE automatic re-fire if either gate (Clip QA or the join-check) comes
    back non-green, then a HARD STOP naming the layer at fault (CLAUDE.md rule 3) if the re-fire fails too. Call
    this only after you have actually looked at the anchor from the prepare call."""
    import cb_scene, cb_segprompt, cb_qa
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
    settle_path = f"media/{episode}_{winner_code}_{w_slug}_settle.png"
    remint_path = f"media/{episode}_{winner_code}_{w_slug}_remint.png"
    next_b = beats[idx + 1]
    next_code = next_b.get("beatCode") or next_b.get("shotCode")
    next_slug = next_b.get("slug", (next_code or "").replace(".", "_"))
    # RE-MINT SCOPING — THE RE-MINT CORRECTION (Julian, 2026-07-06, superseding rule 32's junction-type-only
    # trigger — "do not re-mint the last frame every time by default... use the approved raw harvested settle
    # frame... re-mint only if the harvested frame is degraded, blurred, off-model, or unsuitable... constant
    # re-minting can introduce drift because Nano Banana may 'beautify' or subtly change the character"). A
    # `seamless_continuation` next beat still ALWAYS re-mints (unchanged — @图1 is used as literal first-frame
    # pixels there, so the cleanup pass earns its keep regardless of quality). An `intentional_next_shot` next
    # beat (the default) no longer skips re-mint unconditionally — it re-mints ONLY when the actual harvested
    # frame fails cb_scene.harvest_needs_remint's quality gate (sharpness today; off-model/identity drift is a
    # flagged future check, not yet built — see that function's own docstring for why).
    junction = cb_segprompt._junction_type(next_b)
    always_remint = junction == cb_segprompt.JUNCTION_SEAMLESS

    if not approved:
        # PHASE 1 — PREPARE: harvest winner_code's own official clip (there is only ever one — the one-render
        # economy fires exactly once per beat, auto-retried once internally on a failed gate — so there is no
        # separate "pick a winner among candidates" step left to run here), then re-mint only when the seamless
        # rule or the quality gate calls for it, then STOP for approval.
        if not os.path.exists(official):
            print(f"fire_next_beat: {winner_code} has no official clip yet at {official} — fire it (Gate 3) first, then prepare", flush=True); return None
        if dry_run:
            print(f"fire_next_beat [DRY RUN]: using {winner_code}'s CURRENT official clip as-is (no file changes)", flush=True)

        # HARVEST — the sharpest frame in the winner's settle window. Real in both modes (only reads the clip and
        # writes a derived _settle.png — never touches the official clip itself). Always runs, both junction types.
        settlef = cb_scene.harvest_settle_frame(episode, winner_code, w_slug)
        print(f"fire_next_beat: harvested -> {settlef or '(FAILED — check the clip)'}", flush=True)
        if not settlef:
            print("fire_next_beat: cannot proceed without a harvested settle frame; stopping.", flush=True); return None

        cast = wb.get("openingCast") or wb.get("characters") or []
        quality_needs_remint, quality_reason = cb_scene.harvest_needs_remint(settlef)
        needs_remint = always_remint or quality_needs_remint
        print(f"fire_next_beat: re-mint quality gate — {quality_reason}", flush=True)
        remint_out, drift, anchor = None, None, settlef
        if needs_remint:
            why = "seamless_continuation" if always_remint else f"quality gate: {quality_reason}"
            remint_out = cb_scene.remint_settle_frame(episode, winner_code, w_slug, cast, settlef)
            print(f"fire_next_beat: re-minted -> {remint_out or '(FAILED)'} ({next_code}: {why})", flush=True)
            if not remint_out:
                print("fire_next_beat: cannot proceed without a re-minted anchor; stopping.", flush=True); return None
            turnarounds = [a for c in cast if (a := _anchor(c))]
            drift = cb_qa.check_remint(settlef, remint_out, turnarounds)
            print(f"fire_next_beat: RE-MINT DRIFT CHECK -> {'CLEAN' if drift['ok'] else 'BLOCK'} — {drift['verdict']}", flush=True)
            anchor = remint_out
        else:
            print(f"fire_next_beat: no re-mint — {quality_reason}; the raw harvested frame IS @图1 directly; "
                  f"state continuity moves to the post-fire join-check", flush=True)

        if dry_run:
            # PROVE THE INJECTION — the next beat's real shipped prompt (relay=True), @图1 = the actual anchor.
            _scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(scene_num)), None)
            prompt, builder, is_v3 = cb_segprompt.shipped_prompt(next_b, _scene, relay=True,
                                                                 prev_end_state_still=wb.get("endStateStill"),
                                                                 prev_carry_marks=wb.get("carryMarks"))
            _chars = next_b.get("openingCast") or next_b.get("characters") or []
            imgs = [anchor] + [a for c in _chars if (a := _anchor(c))]
            _plate = f"media/{episode}_S{scene_num}_plate.png"
            if os.path.exists(_plate):
                imgs.append(_plate)
            # @Video1 RETIRED (Julian, 2026-07-07 — "the video I don't like it either, I think it confuses
            # things"): no video reference is built or uploaded any more; see cb_segprompt.py's module
            # docstring, "THE FIFTH ANCHOR, RETIRED".
            print(f"fire_next_beat [DRY RUN]: {next_code} shipped prompt (builder={builder}):\n{prompt}", flush=True)
            print(f"fire_next_beat [DRY RUN]: would upload {len(imgs)} images: {imgs}", flush=True)
            print(f"=== fire_next_beat [DRY RUN] complete for {next_code} — nothing fired, nothing mutated. ===", flush=True)
            return {"prompt": prompt, "builder": builder, "is_v3": is_v3, "images": imgs,
                    "harvested": settlef, "remint": remint_out, "anchor": anchor, "drift_check": drift, "next_code": next_code}

        print(f"=== fire_next_beat STOPPED — {winner_code}'s anchor is ready for your approval:\n"
              f"    {anchor}\n"
              f"    Review it, then call fire_next_beat(..., approved=True) to launch {next_code}. Sign nothing else. ===",
              flush=True)
        return {"harvested": settlef, "remint": remint_out, "anchor": anchor, "drift_check": drift, "next_code": next_code}

    # PHASE 2 — approved=True: the anchor was already prepared; this call's only job is to launch. Which file
    # to expect depends on the SAME junction-type decision the prepare phase made (rule 32) — but `needs_remint`
    # is a LOCAL variable only ever assigned inside the `if not approved:` branch above (line ~724), so this is
    # a genuinely SEPARATE call to `fire_next_beat` (per this function's own docstring: prepare, then approve —
    # two distinct invocations) and cannot see phase 1's locals at all. FIXED 2026-07-07 (front-to-back audit —
    # a 100% reproducible UnboundLocalError on every approved=True call, i.e. every relay beat cb_replicator.
    # walk_scene launches from 1.B2 onward): re-derive the SAME decision here, reading the already-harvested
    # settle frame phase 1 left on disk (it must exist by now — phase 1 never returns without it).
    if not os.path.exists(settle_path):
        print(f"fire_next_beat: approved=True but no harvested settle frame at {settle_path} — call without "
              f"approved first to prepare it.", flush=True); return None
    _quality_needs_remint, _quality_reason = cb_scene.harvest_needs_remint(settle_path)
    needs_remint = always_remint or _quality_needs_remint
    expected_anchor = remint_path if needs_remint else settle_path
    if not os.path.exists(expected_anchor):
        print(f"fire_next_beat: approved=True but no prepared anchor at {expected_anchor} — call without approved "
              f"first to prepare it.", flush=True); return None
    # THE MANIFEST (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's ruling — "Gate N cannot arm... without
    # both manifests green"): fire_next_beat refuses to launch on a red manifest, same choke-point every other
    # arming path (cb_pipeline.approve, cb_replicator.walk_scene, the Studio's fire/approve endpoints) enforces.
    try:
        import cb_preflight
        _ok, _block_count, _ = cb_preflight.manifest_ok(pkg_path, scene=scene_num, episode=episode)
        if not _ok:
            print(f"fire_next_beat: REFUSED — {_block_count} manifest BLOCK(s) outstanding for scene {scene_num}; "
                  f"never arms on a red manifest (run: python3 cb_preflight.py --scene={scene_num})", flush=True)
            return None
    except Exception as _e:
        print(f"fire_next_beat: manifest check could not run ({str(_e)[:120]}) — proceeding without it; fix cb_preflight.py", flush=True)
    print(f"fire_next_beat: {winner_code}'s anchor APPROVED -> launching {next_code} under the one-render economy "
          f"(one fire, one automatic re-fire on a failed gate, then a hard stop — never a third roll)", flush=True)
    clip, ok, reasons = _fire_gated(pkg_path, scene_num, episode, next_code, next_slug, fast)
    attempt = 1
    if not ok:
        print(f"fire_next_beat: {next_code} attempt 1 failed a gate — {'; '.join(reasons)} — ONE automatic "
              f"re-fire (the one-render economy)", flush=True)
        clip, ok, reasons = _fire_gated(pkg_path, scene_num, episode, next_code, next_slug, fast)
        attempt = 2
    if not ok:
        diagnosis = _layer_diagnosis(reasons)
        print(f"=== fire_next_beat HARD STOP — {next_code} failed its gate on both the fire and the one "
              f"permitted re-fire. Reasons: {'; '.join(reasons)}. Diagnosis: {diagnosis}. Never a third blind "
              f"roll (CLAUDE.md rule 3) — fix the named layer, then re-fire by hand when ready. Sign nothing. ===",
              flush=True)
        return {"status": "HARD_STOP", "next_code": next_code, "clip": clip, "reasons": reasons, "diagnosis": diagnosis}
    print(f"=== fire_next_beat: {next_code} fired clean {'on the first try' if attempt == 1 else 'on the one permitted re-fire'} "
          f"-> {clip}. No auto-advance — review it, sign it off, then continue the relay when ready. ===", flush=True)
    return {"status": "OK", "next_code": next_code, "clip": clip, "attempt": attempt}

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
