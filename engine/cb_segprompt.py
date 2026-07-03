#!/usr/bin/env python3
"""GATE 3 — the SINGLE SOURCE OF TRUTH for the Seedance video prompt.

THE DEFINITIVE STRUCTURE is v3 (spec freeze, 2026-07-02, Julian) — ONE mechanical assembler (for_beat_v3 /
_v3_shots, zero LLM: cuts become shots, durations become per-shot seconds, dialogue order becomes per-shot
speaker binding) feeding TWO emitters: emit_prose_v3 (multi-shot native prose, for a beat with 0-1 distinct
speakers) and emit_json_v3 (light JSON shots, for a beat with 2+ distinct speakers, giving per-shot dialogue
binding an exchange needs). shipped_prompt() is the one entry point every caller uses; for_beat (v1) and
for_beat_v2 are RETIRED — kept for rollback/reference, never called except as the loud, logged fallback chain.

The governing principle carries forward from v1/v2: REFERENCES ARE LAW (they own identity + look); the TEXT owns
only motion, performance, camera freedom and audio rules. Prose-first (fal's own I2V calls are plain prose; the
"light JSON" emitter is just a more structured flavour of the same text field) — this module is the internal spec
that emits both.

Rules baked in (so they can never drift):
  • NO character DESCRIPTION in the text — identity comes ENTIRELY from @图1 (keyframe) + @图2/@图3 (turnarounds). The
    highest-ROI fix: kills the "copy exactly" vs "Pixar-quality" contradiction that makes the model redesign faces.
  • ROLE LABELS, not names — "the larger bee" / "the smaller bee" (avoids the name-trap; names still live in @AudioN).
  • VOICE lives IN the render: each speaker "says @AudioN" (the fal-documented pattern → Seedance OUTPUTS the supplied
    11Labs voice), lip-synced, no other speech. generate_audio stays TRUE so Seedance ALSO scores ambience/SFX/underscore.
  • CAMERA is loose — Seedance directs cinematically; we only forbid chaos and demand every character stay readable + on-model.
  • A take is action-dense (8-15s): if a beat drifts past its budget, split it into another beat rather than rewriting.
"""

import os, re, json
import paths as P                             # T30 Phase 3 — show-specific "laws" load from the show's tenant dir

# WING LAW — a bee in the air ALWAYS has beating wings. Seedance must never render a mid-air bee with still/frozen wings.
# T30 Phase 3: loaded from the show's laws/ (a Crystal-Bears-specific rule — a different show has no bees, no wing law).
# The inline string is the fallback if the law file is ever missing, so a broken/misconfigured show tenant fails loud
# via an empty/wrong WING_LAW rather than an ImportError, but a normal run always reads the file.
_WING_LAW_FILE = os.path.join(os.path.dirname(P.CONFIG), "laws", "wing_law.txt")
try:
    WING_LAW = open(_WING_LAW_FILE, encoding="utf-8").read().strip()
except Exception:
    WING_LAW = ("WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, "
        "a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, "
        "gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee "
        "that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.")

# STYLE LAW — the show's confirmed style line (Julian, 2026-07-03, item THREE of Fable's code review), loaded
# from the show profile (shows/crystal-bears/laws/style.txt, declared in profile.json's laws.style key) the same
# way as WING_LAW above. The inline string is the fallback if the law file is ever missing.
_STYLE_LAW_FILE = os.path.join(os.path.dirname(P.CONFIG), "laws", "style.txt")
try:
    STYLE_LAW = open(_STYLE_LAW_FILE, encoding="utf-8").read().strip()
except Exception:
    STYLE_LAW = ("Premium 3D animated feature film aesthetic for children aged 4 to 8, bright hyper saturated "
        "colours, warm golden hour sunlight with volumetric rays, glowing magical particles, lighthearted highly "
        "expressive slapstick comedy")

# ══════════════════ GENERATE THE DEFINITIVE 6-SECTION PROMPT FROM ANY DIRECTOR BEAT ══════════════════
# The Director brings the script to life; this turns each faithful beat into the SIGNED-OFF Seedance model — for EVERY
# beat of EVERY episode, not just the hand-authored ones. Same structure: 12s/16:9 → REFERENCE LAW (@图1 keyframe +
# @图2/@图3… turnarounds) → SCENE → ACTION/PERFORMANCE → CAMERA → AUDIO (single @Audio1) → NEGATIVES, + the WING law for
# bees. The dialogue is NEVER written into the prose (it lives in @Audio1); the prose carries only motion, staging and rules.

_CHARS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "characters.json")
def _load_chars():
    try:
        d = json.load(open(_CHARS_PATH)); return d.get("characters", d)
    except Exception:
        return {}
_CHARS = _load_chars()

def _char_meta(name):
    """(role_label, is_bee) for a character — from config promptRole/isBee, with a title-derived fallback."""
    c = _CHARS.get(name) or {}
    role = c.get("promptRole")
    if not role:
        import re
        t = ((c.get("bible") or {}).get("title") or "") if isinstance(c.get("bible"), dict) else ""
        m = re.search(r"the [a-z' ]+?(bee|bear|cub|dolphin)", t.lower())
        role = m.group(0) if m else str(name)
    is_bee = bool(c.get("isBee")) or ("bee" in (role or "").lower())
    return role, is_bee

_REFLAW_HEAD = ("REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the character(s) EXACTLY as drawn (no redesign, no "
    "morphing, no rescale, no new accessories) and copy the environment and lighting from it.")
_REFLAW_TAIL = (" Their turnarounds lock proportions, markings and features. Add ONLY motion and performance. No extra "
    "characters, no redesign.")
CAMERA_GENERIC = ("Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they "
    "help the storytelling — but keep every character readable and on-model at all times. No chaotic camera.")
NEGATIVES_GENERIC = ("no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, "
    "no on-screen text or subtitles, no logos or watermarks, no foreign-language speech")
_BEE_NEG = (", no crystals on or attached to the bees, no still/frozen/motionless wings on any bee that is airborne, "
    "no bee gliding or hovering with static wings")

def _scene_for(beat, scene):
    # SCENE = the WORLD only (never character positions). Prefer the derived scene PLATE; fall back to the location name.
    if scene:
        parts = [str(scene.get(k)) for k in ("look", "definingFeature", "location") if scene.get(k)]
        if parts:
            return " — ".join(dict.fromkeys(parts)).strip()
    loc = str(beat.get("scene") or "").strip()
    return ((loc + " — rendered exactly as the world in the references (environment and lighting only)").strip(" —")
            or "the approved scene environment exactly as the references show it")

def _action_for(beat):
    bits = []
    sb = (beat.get("storyBeat") or "").strip()
    if sb: bits.append(sb)
    for c in (beat.get("cuts") or []):
        a = (c.get("action") or "").strip()
        if a and a not in bits: bits.append(a)
    action = " ".join(bits).strip()
    return (action + " Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional "
            "timing; the performance carried in the eyes, the breath and the weight.").strip()

def _audio_for(beat):
    has = bool(beat.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))
    if beat.get("wordlessHeld") or not has:
        return ("this beat has NO character dialogue — generate no speech or voices at all. Seedance generates and mixes the "
                "scene ambience, gentle character SFX and a light underscore that fits the moment (no sung lyrics).")
    return ("use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US lip-sync, each "
            "mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other "
            "speech. Seedance generates and mixes everything else: the scene ambience, gentle character SFX and a light "
            "playful underscore kept low under the voice (no sung lyrics).")

def for_beat(beat, scene=None):
    """RETIRED (spec freeze, 2026-07-02, Julian) — superseded by for_beat_v3 (mechanical, per-shot assembler). Kept
    for rollback/reference only; never called except as shipped_prompt()'s should-never-happen final fallback,
    which fires a loud log line if it ever actually runs. Do not call this directly, and do not build on it.

    (Original docstring, for historical context:) Generate the 6-section Seedance prompt from a Director beat —
    the FIRST signed-off model, for any beat of any episode. `scene` = optional scene-plate dict (look/
    definingFeature/location). References are law; the faithful dialogue lives in @Audio1 (never in the prose)."""
    dur = int(beat.get("durationSec") or 12); dur = max(8, min(15, dur))
    chars = beat.get("openingCast") or beat.get("characters") or []
    ref_bits, any_bee = [], False
    for i, name in enumerate(chars):
        role, is_bee = _char_meta(name); any_bee = any_bee or is_bee
        ref_bits.append(f"@图{i + 2} is {role}")
    reflaw = _REFLAW_HEAD + ((" " + "; ".join(ref_bits) + ".") if ref_bits else "") + _REFLAW_TAIL
    cam = CAMERA_GENERIC + ((" " + str(beat.get("cameraArc")).strip()) if beat.get("cameraArc") else "")
    neg = NEGATIVES_GENERIC + (_BEE_NEG if any_bee else ".")
    out = f"{dur} seconds, 16:9.\n\n{reflaw}\n\n"
    if any_bee:
        out += WING_LAW + "\n\n"
    out += (f"SCENE: {_scene_for(beat, scene)}\n\n"
            f"ACTION / PERFORMANCE: {_action_for(beat)}\n\n"
            f"CAMERA: {cam}\n\n"
            f"AUDIO: {_audio_for(beat)}\n\n"
            f"NEGATIVES: {neg}")
    return out

# ══════════ FOR_BEAT V2 — the FAITHFUL TRANSLATOR (T7, dispatch 001, 2 Jul 2026) ══════════
# for_beat (above) discards the Director's actual direction (performance, pauseHold, motionTempo, physicalFeeling,
# soundIntent, light, atmosphere, cameraArc) and stitches storyBeat + cuts instead; it can also ship the keyframe
# PLATE text ("No characters.") as SCENE, and leaves character NAMES in the prose (the name-trap). v2 ships the
# Director's own direction inside the same baked law. Deterministic — zero LLM. ADDITIVE / UNROUTED — nothing calls
# this yet; T7's own ticket is reading the regenerated prompts against for_beat before switching the routing point.

def _short_role(role):
    """'the larger, eager, manic bee' -> 'the larger bee' — first descriptor + species."""
    parts = [p.strip() for p in str(role).split(",")]
    if len(parts) < 2: return role
    species = parts[-1].split()[-1]
    return f"{parts[0]} {species}"

def _delabel(text, cast, used=None):
    """Names -> role labels in prose (names live ONLY in @Audio1). Full label on FIRST mention,
    the short label after — the gold-standard cadence, not a six-times mouthful."""
    import re as _re
    out = str(text or "")
    used = used if used is not None else set()
    for name in cast:
        role, _ = _char_meta(name); short = _short_role(role)
        def _sub(m, n=name, r=role, s=short):
            poss = m.group(0).endswith("'s")
            label = r if n not in used else s
            used.add(n)
            return label + ("'s" if poss else "")
        out = _re.sub(rf"\b{name}(?:'s)?\b", _sub, out)
    return out

def _strip_spoken_words(text):
    """The dialogue's WORDS never appear in the prose — they live only in @Audio1. Quoted lines
    become a reference to the track, so Seedance never renders text or invents a second voice.
    A bare possessive apostrophe (Zenny's, the bee's) is NOT a quote — the old pattern's quote-char
    class included the plain "'", so it could open (or close) a "match" on a possessive apostrophe
    and then greedily swallow everything up to the NEXT quote-like character (including a real
    quoted line further on), replacing that whole span and leaving a stray "Zennythe line in
    @Audio1" behind. Fixed with boundaries: a quote delimiter is never immediately between two
    letters (that's a possessive), so "Zenny's" is skipped, but a possessive INSIDE a real quoted
    line ("A Storm's coming.") still passes through as ordinary matched content. Run this AFTER
    _delabel (not before) so every character mention is delabeled — and counted for first-mention
    tracking — before any text is removed."""
    import re as _re
    return _re.sub(
        r'(?<![A-Za-z])["“‘\']'                                        # open: not immediately after a letter (excludes a possessive)
        r'((?:[^"“‘’”\']|(?<=[A-Za-z])[\'’](?=[a-zA-Z])){2,80})'       # body: non-quote chars; a possessive apostrophe (straight OR
                                                                        # curly — the actual authored text uses curly ’) passes through
        r'["”’\'](?![A-Za-z])',                                        # close: not immediately before a letter (excludes a possessive)
        "the line in @Audio1", str(text or ""))

def _scene_v2(beat, scene):
    """SCENE = the WORLD as the Director lit it: light + atmosphere + the location's look.
    NEVER the empty keyframe plate text (that is Gate-2 language; 'No characters.' in a
    video prompt actively fights the performance)."""
    bits = []
    for k in ("light", "atmosphere"):
        v = str(beat.get(k) or "").strip()
        if v: bits.append(v)
    if scene:
        for k in ("definingFeature", "location"):
            v = str(scene.get(k) or "").strip()
            if v and v not in bits: bits.append(v); break   # one look line, not three restatements
    if not bits:
        loc = str(beat.get("scene") or "").strip()
        bits = [loc + " — rendered exactly as the world in the references (environment and lighting only)"]
    return " ".join(bits)   # delabeled + de-quoted by the caller

def _action_v2(beat, cast, used=None):
    """ACTION = the Director's direction, in performance order:
    the tempo/contrast frame -> the cuts as continuous directed prose -> the HELD BEAT -> physics
    coloured by how the moment should FEEL. All delabeled."""
    bits = []
    mt = str(beat.get("motionTempo") or "").strip()
    if mt: bits.append(mt)                                   # the contrast frame (her grace vs his chaos)
    for c in (beat.get("cuts") or []):
        a = str(c.get("action") or "").strip()
        if a and a not in bits: bits.append(a)
    ph = str(beat.get("pauseHold") or "").strip()
    if ph: bits.append(ph)                                   # the Docter held beat — the laugh lands in stillness
    tail = ("Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional "
            "timing; the performance carried in the eyes, the breath and the weight.")
    pf = str(beat.get("physicalFeeling") or "").strip()
    if pf: tail += " The take should feel like: " + pf
    bits.append(tail)
    # delabel FIRST (every mention counted, in order, for the first-mention/short-label tracking), THEN strip the
    # now-delabeled text's quoted dialogue — never the reverse (stripping first can eat a mention before delabel
    # ever sees it, and — the bug this fixed — a bare possessive apostrophe is not a quote to strip in either order).
    return _strip_spoken_words(_delabel(" ".join(bits), cast, used=used))

def _speaker_map(beat, cast):
    """LINE INDEX -> ROLE LABEL, in the order the lines are actually voiced — built from the SAME parser cb_voice
    uses to cut and attribute the real @Audio1 track (_cut_segments/_resolve_speaker), so the prompt's claim about
    who is speaking can never drift from what the track actually contains. This is the fix for the ambiguous-speaker
    class of bug (a beat where only one on-screen character has lines still let Seedance guess, and it guessed
    wrong — "Nailed it." rendered in Zenny's mouth instead of Fuzzby's): naming the mapping explicitly, and naming
    who stays silent, removes the guess. Returns '' when the beat has no dialogue (nothing to map)."""
    try:
        import cb_voice as V
    except Exception:
        return ""
    speakers = []
    for c in (beat.get("cuts") or []):
        dlg = (c.get("dialogue") or "").strip()
        if not dlg:
            continue
        for label, text in V._cut_segments(dlg):
            if text:
                speakers.append(V._resolve_speaker(label, beat))
    if not speakers:
        return ""
    lines = "; ".join(f"line {i + 1} → {_short_role(_char_meta(name)[0])}" for i, name in enumerate(speakers) if name)
    speaking = list(dict.fromkeys(n for n in speakers if n))
    silent = [n for n in cast if n not in speaking]
    tail = ""
    if len(speaking) == 1 and silent:
        solo = _short_role(_char_meta(speaking[0])[0])
        others = ", ".join(_short_role(_char_meta(n)[0]) for n in silent)
        tail = f" Only {solo} speaks in this beat; {others} has no lines and must stay visibly silent throughout — no mouth movement, no voice."
    return f"SPEAKER MAP: {lines}.{tail}"

def _audio_v2(beat, cast):
    has = bool(beat.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))
    if beat.get("wordlessHeld") is True or not has:
        base = ("this beat has NO character dialogue — generate no speech or voices at all. Seedance generates and "
                "mixes the scene ambience, gentle character SFX and a light underscore that fits the moment (no sung lyrics).")
    else:
        base = ("use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US "
                "lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate "
                "voice, and no other speech. Seedance generates and mixes everything else")
        si = _strip_spoken_words(_delabel(str(beat.get("soundIntent") or "").strip(), cast, used=set(cast)))
        base += (": " + si if si else ": the scene ambience, gentle character SFX and a light playful underscore")                 + " — kept low under the voice (no sung lyrics)."
        smap = _speaker_map(beat, cast)
        if smap:
            base += " " + smap
    return base

_SIDES = ["frame-LEFT", "frame-RIGHT", "frame-CENTRE"]

def for_beat_v2(beat, scene=None):
    """RETIRED (spec freeze, 2026-07-02, Julian) — superseded by for_beat_v3 (mechanical, per-shot assembler; the
    prompt trials found v2's section-of-prose shape, its rules blocks and its physics/emotional-arc paragraphs were
    token tax with no quality payoff). Kept for rollback/reference only; never called except as shipped_prompt()'s
    loud fallback if for_beat_v3 ever returns empty. Do not call this directly, and do not build on it.

    (Original docstring, for historical context:) The SECOND-generation 6-section prompt, carrying the Director's
    ACTUAL direction (motionTempo/pauseHold/physicalFeeling/soundIntent/light/atmosphere/cameraArc) that v1 discarded."""
    dur = int(beat.get("durationSec") or 12); dur = max(8, min(15, dur))
    chars = beat.get("openingCast") or beat.get("characters") or []
    ref_bits, any_bee = [], False
    for i, name in enumerate(chars):
        role, is_bee = _char_meta(name); any_bee = any_bee or is_bee
        side = _SIDES[min(i, 2)] if len(chars) > 1 else None
        ref_bits.append(f"@图{i + 2} is {role}" + (f" ({side})" if side else ""))
    reflaw = _REFLAW_HEAD + ((" " + "; ".join(ref_bits) + ".") if ref_bits else "") + _REFLAW_TAIL
    cam = CAMERA_GENERIC + ((" " + _strip_spoken_words(_delabel(str(beat.get("cameraArc")).strip(), chars, used=set(chars)))) if beat.get("cameraArc") else "")
    neg = NEGATIVES_GENERIC + (_BEE_NEG if any_bee else ".")
    out = f"{dur} seconds, 16:9.\n\n{reflaw}\n\n"
    if any_bee:
        out += WING_LAW + "\n\n"
    _used = set()
    out += (f"SCENE: {_delabel(_scene_v2(beat, scene), chars, used=_used)}\n\n"
            f"ACTION / PERFORMANCE: {_action_v2(beat, chars, used=_used)}\n\n"
            f"CAMERA: {cam}\n\n"
            f"AUDIO: {_audio_v2(beat, chars)}\n\n"
            f"NEGATIVES: {neg}")
    return out

# ══════════ FOR_BEAT V3 — THE MECHANICAL ASSEMBLER (spec freeze, 2026-07-02, Julian) ══════════
# The prompt trials are complete and crowned. ONE assembler builds ONE shot data structure mechanically from the
# Director's EXISTING fields — cuts become shots (camera first, from framing), durations become PER-SHOT seconds
# (weighted by how much is happening in each shot — the same weighting convention the legacy compact builder
# used), dialogue order becomes PER-SHOT speaker binding (via the SAME cb_voice parser that cuts the real @Audio1
# track, so a shot's claimed speaker can never drift from the actual voice file). ZERO LLM — pure field-to-shape
# derivation, same discipline as v2 but now organized by SHOT, not by section-of-prose.
#
# TWO emitters consume the SAME shot list. The trials proved rules blocks, per-shot SFX lists and physics/emotional-
# arc sections were token tax — cut. Match the two worked examples' weight and shape exactly; they are verbatim law:
#   A — PROSE, multi-shot native, for a beat with 0-1 distinct speakers (Julian's crowned 1.B1): SUBJECTS (role
#       labels + frame homes + the ONE-line wing law) -> ENVIRONMENT (@图1 is TRUTH, then the plate + one breeze
#       force) -> STYLE (one line) -> SHOT n (lens+move first, then action, then one minimal sound cue) -> AUDIO
#       (the law sentence + the speaker map, now shot-indexed) -> NEGATIVES (six).
#   B — LIGHT JSON, for a beat with 2+ distinct speakers (Julian's crowned 1.B2): duration/aspect/style/references/
#       voices, then a shots[] array — each shot carries seconds, camera, action, and (if it has dialogue) a
#       dialogue object binding ONE speaker to THAT shot. The "line" field is NEVER the actual words — always the
#       fixed string "the line in @Audio1 during this shot" (rule 5: dialogue lives only in @Audio1); "voices" names
#       the ElevenLabs law, not a per-character descriptor (the trial's voice placeholders are retired).
#
# Speaker-count routing (0-1 -> prose, 2+ -> JSON) is the shape that matches BOTH worked examples: 1.B1 has dialogue
# (two lines) but ONE speaker, and is prose; 1.B2 has TWO speakers in exchange, and needs the JSON's per-shot
# binding to stay unambiguous — a single beat-level "line 1/line 2" map (v2's mechanism) can't express WHICH SHOT a
# multi-speaker exchange's line lands in, only a light-JSON shot-by-shot binding can.
_WING_LAW_ONE_LINE = ("Wings beat rapidly and continuously whenever airborne — never still, frozen or motionless "
                      "in flight.")

# ══════════ THE HANDLE DOCTRINE (Julian, 2026-07-03) ══════════
# "Every shot shoots long so the cutter has meat to trim into." All beats now render at 15s — superseding the old
# per-beat durationSec-driven 8-15s range. 13s is the story-action budget (split across the beat's own shots by
# weight, exactly as before); the final 2s are a DIRECTED LIVING SETTLE appended to the closing shot, never dead
# air (the dead-time-causes-hallucinations rule) — the relay's harvest window (the sharpest frame anywhere in
# those 2s, not a prayer that the literal last frame is clean) AND Gate 4's trim handle (the editor cuts into the
# settle per join — CLAUDE.md rule 19).
HANDLE_TOTAL = 15
HANDLE_SETTLE = 2
HANDLE_ACTION = HANDLE_TOTAL - HANDLE_SETTLE

def _v3_shots(beat, cast):
    """THE mechanical assembler — see the module note above. Returns (shots, dur) where each shot is
    {n, seconds, camera, action, speaker (short role label or None)}; seconds always sum to dur (15, Handle
    Doctrine) — action shots split HANDLE_ACTION (13s) by weight, then the closing shot gets +HANDLE_SETTLE (2s)
    added on top for its directed living settle (see _v3_settle)."""
    import cb_voice as V
    dur = HANDLE_TOTAL
    cuts = beat.get("cuts") or []
    used = set()
    raw = []
    for c in cuts:
        action = _strip_spoken_words(_delabel(str(c.get("action") or "").strip(), cast, used=used))
        camera = _strip_spoken_words(_delabel(str(c.get("framing") or "").strip(), cast, used=set(cast)))
        speaker = None
        dlg = (c.get("dialogue") or "").strip()
        if dlg:
            segs = V._cut_segments(dlg)
            if segs:
                name = V._resolve_speaker(segs[0][0], beat)
                if name:
                    speaker = _short_role(_char_meta(name)[0])
        weight = max(1, len(action) + (40 if speaker else 0))   # dialogue shots get real screen time, never squeezed
        raw.append({"action": action, "camera": camera, "speaker": speaker, "weight": weight})
    if not raw:
        return [], dur
    total_w = sum(s["weight"] for s in raw) or 1
    shots, running = [], 0
    for i, s in enumerate(raw):
        sec = max(1, HANDLE_ACTION - running) if i == len(raw) - 1 else max(1, round(HANDLE_ACTION * s["weight"] / total_w))
        running += sec
        shots.append({"n": i + 1, "seconds": sec, "camera": s["camera"], "action": s["action"], "speaker": s["speaker"]})
    shots[-1]["seconds"] += HANDLE_SETTLE   # the closing shot's extra 2s IS the directed living settle
    return shots, dur

def _v3_settle(beat):
    """THE HANDLE DOCTRINE's directed living settle text — built from the Director's own endState field when
    authored; a universal idle-life guarantee is ALWAYS appended (wings, breeze, pollen, held expressions, camera
    locked) so the closing shot never reads as dead air even before endState is written for every beat.
    Mechanical: renders what's authored, never invents a specific pose."""
    es = str(beat.get("endState") or "").strip()
    idle = ("wings beating, the breeze moving the flowers, pollen drifting, held expressions, camera locked — "
            "nothing freezes, nothing new happens")
    if es:
        return f" SETTLE: {es.rstrip('.')}. Idle life continues through the hold — {idle}."
    return f" SETTLE: hold the frame at rest, camera locked. Idle life continues through the hold — {idle}."

def _v3_subjects(cast):
    """REFERENCE STACK doctrine (Julian, 2026-07-03): every reference declares its JOB, not just its identity —
    the turnarounds are the identity reference EVERY beat, the anti-drift anchor pulling each chain link back to
    canon, stated explicitly here rather than left implicit."""
    ref_bits, any_bee = [], False
    for i, name in enumerate(cast):
        role, is_bee = _char_meta(name); any_bee = any_bee or is_bee
        side = _SIDES[min(i, 2)] if len(cast) > 1 else None
        ref_bits.append(f"@图{i + 2} is {role}" + (f" ({side})" if side else ""))
    line = ("; ".join(ref_bits) + " — the identity reference every beat, the anti-drift anchor pulling this "
            "chain link back to canon.") if ref_bits else ""
    if any_bee:
        line = (line + " " + _WING_LAW_ONE_LINE).strip()
    return line

def _v3_environment(beat, scene, cast, relay=False, plate_n=None):
    """RELAY CHAIN aware (Julian, 2026-07-03, CLAUDE.md rule 21): a relay beat's @图1 is the HARVESTED SETTLE
    FRAME, not a fresh keyframe — it IS the scene continuing, not a reference to copy FROM, so the wording changes
    accordingly; the scene's canonical world look/palette/light then comes from a separate plate reference
    (@图{plate_n}, always last) instead, stated so it never competes with or forces the harvested frame."""
    if relay:
        bits = ["@图1 is the harvested settle frame from the previous beat's signed clip — the scene continues "
                "from exactly this moment, use it as the first frame."]
    else:
        bits = ["@图1 is TRUTH — copy the environment and lighting from it exactly."]
    loc = ""
    if scene:
        for k in ("definingFeature", "location"):
            v = str(scene.get(k) or "").strip()
            if v:
                loc = v; break
    if not loc:
        loc = str(beat.get("scene") or "the approved scene").strip()
    bits.append(loc.rstrip(".") + ".")
    atmo = str(beat.get("atmosphere") or "").strip()
    if atmo:
        first = re.split(r"(?<=[.!?])\s+", atmo)[0]          # ONE breeze/atmosphere force, not the whole paragraph
        bits.append(_strip_spoken_words(_delabel(first, cast, used=set(cast))))
    if relay and plate_n:
        bits.append(f"@图{plate_n} is the scene's plate: reference for the world's canonical look, palette and "
                    "light only — it never forces the frame, the harvested settle already IS the frame.")
    return " ".join(bits)

def _v3_style():
    return STYLE_LAW

def _v3_negatives(any_bee):
    """Returns the 6 negative-constraint PHRASES as a list (each phrase may itself contain an internal comma —
    callers that want a single line join them with ", "; the JSON emitter ships the list as-is, never re-split)."""
    core = ["no morphing, redesign or rescale of the characters", "no extra characters or props",
            "no on-screen text, subtitles, logos or watermarks", "no foreign-language speech"]
    core += (["no crystals on or attached to the bees", "no still or frozen wings while airborne"] if any_bee
             else ["no flicker or compression artifacts", "no continuity break in lighting or palette"])
    return core[:6]

def _v3_shot_sounds(beat, n):
    """ONE minimal sound cue per shot — mechanically sliced from the beat's OWN soundIntent (already-authored
    prose, never re-invented), never a per-shot SFX list. Falls back to a generic ambience note if soundIntent
    has fewer clauses than shots."""
    intent = str(beat.get("soundIntent") or "").strip()
    parts = [p.strip() for p in re.split(r"[;,]", intent) if p.strip()] if intent else []
    if n - 1 < len(parts):
        return parts[n - 1].rstrip(".")
    return "ambient sound continues" if parts else "quiet ambience"

def _v3_speaker_map(shots, cast):
    speaking = [(s["n"], s["speaker"]) for s in shots if s["speaker"]]
    if not speaking:
        return ""
    smap = "; ".join(f"shot {n} → {spk}" for n, spk in speaking)
    distinct = list(dict.fromkeys(spk for _, spk in speaking))
    tail = ""
    if len(distinct) == 1:
        silent = [_short_role(_char_meta(c)[0]) for c in cast if _short_role(_char_meta(c)[0]) != distinct[0]]
        if silent:
            tail = f" Only {distinct[0]} speaks in this beat; {', '.join(silent)} stays visibly silent throughout."
    return f"SPEAKER MAP: {smap}.{tail}"

def emit_prose_v3(beat, scene, shots, dur, cast, relay=False):
    """Worked example A — PROSE, multi-shot native. Verbatim law: SUBJECTS -> ENVIRONMENT -> STYLE -> SHOT n... ->
    AUDIO -> NEGATIVES. No rules blocks, no per-shot SFX lists, no physics/emotional-arc sections. The closing
    SHOT carries the Handle Doctrine's directed living-settle block (Julian, 2026-07-03) — see _v3_settle.
    relay=True (RELAY CHAIN, rule 21): @图1 is the harvested settle frame, not a fresh keyframe, and a 4th
    reference (the scene plate, @图{len(cast)+2}) anchors the world's canonical look without forcing the frame."""
    any_bee = any(_char_meta(n)[1] for n in cast)
    plate_n = len(cast) + 2 if relay else None
    out = f"{dur} seconds, 16:9.\n\n"
    out += f"SUBJECTS: {_v3_subjects(cast)}\n\n"
    out += f"ENVIRONMENT: {_v3_environment(beat, scene, cast, relay=relay, plate_n=plate_n)}\n\n"
    out += f"STYLE: {_v3_style()}\n\n"
    last_i = len(shots) - 1
    for i, s in enumerate(shots):
        camera = s["camera"] + _v3_camera_end(beat, cast, i)
        settle = _v3_settle(beat) if i == last_i else ""
        out += f"SHOT {s['n']} ({s['seconds']}s): {camera}. {s['action']} {_v3_shot_sounds(beat, s['n'])}.{settle}\n\n"
    has_dlg = any(s["speaker"] for s in shots)
    if has_dlg:
        law = ("use ONLY @Audio1 for ALL dialogue — each speaking character mouths its own lines in @Audio1, in "
               "order; no other, different or duplicate voice. ALL vocal sounds — hums, sing-songs, exclamations, "
               "not just spoken lines — are V3 performances inside @Audio1; Seedance never generates a voice-like "
               "sound of any kind (Audio Doctrine, Julian, 2026-07-03).")
        out += f"AUDIO: {law} {_v3_speaker_map(shots, cast)}\n\n"
    else:
        out += ("AUDIO: this beat has no dialogue — generate no speech or voices; Seedance scores ambience and a "
                "light underscore.\n\n")
    out += f"NEGATIVES: {', '.join(_v3_negatives(any_bee))}"
    return out

# ══════════ GOLD STANDARD additions to the JSON emitter (Julian, 2026-07-03) ══════════
# Filed as the worked example for the JSON emitter's goldens AND as T8's Director writing standard (see
# cb_director.py). Every addition below stays MECHANICAL — sourced from existing law/gag-lock/cast data, never
# invented text — matching the v3 spec's zero-LLM promise.
_GAG_LOCKS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "gag_locks.json")
def _v3_gag_locks():
    try:
        return {k: v for k, v in json.load(open(_GAG_LOCKS_PATH)).items() if not k.startswith("_")}
    except Exception:
        return {}

def _gag_lock_for(beat):
    lock_id = beat.get("script_gag_lock_id")
    return _v3_gag_locks().get(lock_id) if lock_id else None

def _v3_rule(beat, cast, any_bee):
    """THE WRITTEN INVARIANT field — something that must hold true for the WHOLE beat, not just one shot. The
    wing law for any beat with an airborne bee; a hold/deadpan invariant (e.g. "her expression does not change
    once") sourced from a gag-lock's own timing_lock when this beat references one, falling back to the beat's
    own pauseHold field (every beat has one authored, gag-lock or not) so the invariant isn't gag-lock-only.
    Mechanical only — never invented; empty when none apply."""
    bits = []
    if any_bee:
        bits.append("Any airborne bee beats its wings rapidly and continuously; wings rest only when landed.")
    tl = str((_gag_lock_for(beat) or {}).get("timing_lock") or "").strip()
    if not tl:
        tl = str(beat.get("pauseHold") or "").strip()
    if tl:
        bits.append(_strip_spoken_words(_delabel(tl, cast, used=set())))
    return " ".join(bits)

def _v3_expression(beat, cast, speaker_role):
    """A per-line EXPRESSION BINDING — only when a gag-lock's own acting_note names this speaker's clause
    (semicolon-separated, one clause per character); never invented for a beat without one. The speaker's own
    NAME is stripped out entirely (not delabeled) — dialogue.speaker already carries identity, an expression is
    pure feeling/face, and rule 5 (identity text never ships) means this field should never repeat it either way."""
    note = str((_gag_lock_for(beat) or {}).get("acting_note") or "").strip()
    if not note:
        return None
    name = next((c for c in cast if _short_role(_char_meta(c)[0]) == speaker_role), None)
    if not name:
        return None
    for clause in note.split(";"):
        if name.lower() in clause.lower():
            clean = re.sub(rf"\bfrom {name}\b", "", clause, flags=re.I)
            clean = re.sub(rf"\b{name}'s\b", "", clean, flags=re.I)
            clean = re.sub(rf"\b{name}\b", "", clean, flags=re.I)
            clean = re.sub(r"\s{2,}", " ", clean).strip(" .,")
            if clean:
                return clean[0].upper() + clean[1:]
    return None

def _v3_camera_end(beat, cast, shot_i):
    """CAMERA END STATE — EVERY shot states explicitly what it ends framing (Julian's reference-stack doctrine,
    2026-07-03: "camera end states on every shot"), so the harvested settle frame and this text always agree on
    what's actually in frame at each cut. Mechanical: whoever THIS shot's own raw cut text actually names (not
    blindly the whole beat's cast — a tight single-character close shouldn't be overclaimed as a two-shot).
    shots and cuts are 1:1 (_v3_shots builds one shot per cut, same order) — shot_i indexes straight into cuts."""
    if not cast:
        return ""
    cuts = beat.get("cuts") or []
    if not cuts:
        return ""
    shot_i = min(shot_i, len(cuts) - 1)   # defensive floor only; shots/cuts are always 1:1 in practice
    raw = str(cuts[shot_i].get("action") or "") + " " + str(cuts[shot_i].get("framing") or "")
    present = [c for c in cast if re.search(rf"\b{re.escape(c)}\b", raw, re.I)]
    who_list = present or cast
    who = " and ".join(_short_role(_char_meta(c)[0]) for c in who_list)
    return f", ending on {who} in frame"

def _v3_constraints(cast):
    """THE CONSTRAINTS LINE — one positive-framed identity/consistency directive, reference-first (rule 5: no
    character description in the text — "per their reference images", never the marks themselves)."""
    if not cast:
        return ""
    who = "both characters'" if len(cast) == 2 else ("each character's" if len(cast) > 2 else "the character's")
    return (f"Maintain {who} design, proportions and markings exactly per their reference images throughout — "
            "no distortion, redesign or rescale.")

def emit_json_v3(beat, scene, shots, dur, cast, relay=False):
    """Worked example B — LIGHT JSON, for any beat with 2+ distinct speakers. duration/aspect/style/references/
    world/rule/shots/constraints/negatives. line is ALWAYS the fixed @Audio1 reference, never the actual words.
    GOLD STANDARD (Julian, 2026-07-03, filed as T8's Director writing standard too): a camera end-state on the
    closing shot, a written invariant ("rule") for the whole beat, a per-line expression binding when a gag-lock
    authors one, a directed living-settle block on the closing shot (Handle Doctrine, superseding the plain
    ambience-resumes tail), and a constraints line — every addition
    mechanical, from existing law/gag-lock/cast data, nothing invented.
    relay=True (RELAY CHAIN, rule 21): @图1 is the harvested settle frame, not a fresh keyframe, and a 4th
    reference (the scene plate) anchors the world's canonical look without forcing the frame."""
    any_bee = any(_char_meta(n)[1] for n in cast)
    if relay:
        refs = {"@图1": "the harvested settle frame from the previous beat's signed clip — use as the first "
                        "frame, the scene continues from exactly this moment"}
    else:
        refs = {"@图1": "the opening keyframe — TRUTH for environment, lighting and continuity"}
    for i, name in enumerate(cast):
        role, _ = _char_meta(name)
        refs[f"@图{i + 2}"] = (f"{role} — identity reference every beat, the anti-drift anchor pulling this "
                              "chain link back to canon")
    plate_n = len(cast) + 2
    if relay:
        refs[f"@图{plate_n}"] = ("the scene's plate: reference for the world's canonical look, palette and light "
                                "only — never forces the frame, the harvested settle already IS the frame")
    out_shots = []
    last_i = len(shots) - 1
    for i, s in enumerate(shots):
        camera = s["camera"] + _v3_camera_end(beat, cast, i)
        action = s["action"] + (_v3_settle(beat) if i == last_i else "")
        shot = {"seconds": s["seconds"], "camera": camera, "action": action}
        if s["speaker"]:
            dlg = {"speaker": s["speaker"], "line": "the line in @Audio1 during this shot",
                   "note": "only this speaker's mouth moves in this shot"}
            expr = _v3_expression(beat, cast, s["speaker"])
            if expr:
                dlg["expression"] = expr
            shot["dialogue"] = dlg
        out_shots.append(shot)
    doc = {
        "duration": dur, "aspect": "16:9", "style": _v3_style(), "references": refs,
        "voices": ("@Audio1 is the ONLY source of all dialogue — animate lips to it exactly; never invent, "
                   "duplicate or generate a different voice. ALL vocal sounds — hums, sing-songs, exclamations, "
                   "not just spoken lines — are V3 performances inside @Audio1; Seedance never generates a "
                   "voice-like sound of any kind (Audio Doctrine, Julian, 2026-07-03)."),
        "world": _v3_environment(beat, scene, cast, relay=relay, plate_n=(plate_n if relay else None)),
    }
    rule = _v3_rule(beat, cast, any_bee)
    if rule:
        doc["rule"] = rule
    doc["shots"] = out_shots
    doc["constraints"] = _v3_constraints(cast)
    doc["negatives"] = _v3_negatives(any_bee)
    return json.dumps(doc, indent=2, ensure_ascii=False)

def for_beat_v3(beat, scene=None, relay=False):
    """THE top-level v3 entry point — builds the shot list once, routes to the emitter that matches the worked
    examples (0-1 distinct speakers -> prose; 2+ -> light JSON), and returns (prompt_text, emitter_label).
    relay=True (RELAY CHAIN, rule 21): this beat opens off its predecessor's harvested settle frame, not its own
    Gate-2b keyframe — threaded into whichever emitter fires."""
    cast = beat.get("openingCast") or beat.get("characters") or []
    shots, dur = _v3_shots(beat, cast)
    if not shots:
        return "", "v3 (empty — no cuts)"
    distinct_speakers = len(set(s["speaker"] for s in shots if s["speaker"]))
    if distinct_speakers >= 2:
        return emit_json_v3(beat, scene, shots, dur, cast, relay=relay), "v3-json"
    return emit_prose_v3(beat, scene, shots, dur, cast, relay=relay), "v3-prose"

# ══════════ THE SINGLE SHIPPING DECISION (spec freeze, 2026-07-02, Julian) ══════════
# for_beat_v3 is now THE definitive builder. for_beat_v2 and for_beat (v1) are RETIRED — kept in this file for
# rollback/reference only, never called except as the should-never-happen fallback chain below, each firing a
# loud, unmissable log line so a silent reversion to a retired builder can never pass unnoticed. EVERY caller that
# needs "the prompt Seedance will actually receive" calls THIS function — never for_beat/for_beat_v2/for_beat_v3
# directly — so preview and fire are provably the SAME call, through the SAME decision, every time.
def shipped_prompt(beat, scene=None, relay=False):
    """Returns (prompt, builder_label, is_v3). is_v3=False means a retired fallback fired — treat that as worth
    investigating, not routine. relay=True (RELAY CHAIN, rule 21) — see for_beat_v3; ignored by the retired v1/v2
    fallbacks (they predate the doctrine and are never expected to fire in practice)."""
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    v3, emitter = for_beat_v3(beat, scene, relay=relay)
    if v3:
        return v3, f"cb_segprompt_v3 ({emitter})", True
    print(f"\n{'!' * 70}\n  FALLBACK TO cb_segprompt v2 (for_beat_v2) — for_beat_v3 returned EMPTY\n"
          f"  for beat {code}. v3 is the definitive builder; this should not\n"
          f"  happen in practice. Investigate the beat's data before trusting\n"
          f"  this render.\n{'!' * 70}\n", flush=True)
    v2 = for_beat_v2(beat, scene)
    if v2:
        return v2, "cb_segprompt_v2 (RETIRED FALLBACK — v3 returned empty, see log)", False
    print(f"\n{'!' * 70}\n  FALLBACK TO cb_segprompt v1 (for_beat) — for_beat_v2 ALSO returned EMPTY\n"
          f"  for beat {code}. Both v3 and v2 are empty; investigate the beat's\n"
          f"  data before trusting this render.\n{'!' * 70}\n", flush=True)
    v1 = for_beat(beat, scene)
    return v1, "cb_segprompt_v1 (RETIRED FALLBACK — v3 and v2 both empty, see log)", False

if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
    code = sys.argv[2] if len(sys.argv) > 2 else "1.B1"
    d = json.load(open(pkg))
    beat = next(b for b in d.get("beats") or d.get("shots") or [] if (b.get("beatCode") or b.get("shotCode")) == code)
    scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(beat.get("sceneNumber"))), None)
    prompt, _builder, _is_v3 = shipped_prompt(beat, scene)
    print(f"===== GATE-3 SEEDANCE PROMPT — {code}  ({len(prompt)} chars) =====\n")
    print(prompt)
