#!/usr/bin/env python3
"""GATE 3 — the SINGLE SOURCE OF TRUTH for the Seedance video prompt.

THE DEFINITIVE STRUCTURE (3-model consensus — GPT-5.5 · Claude Opus 4.8 · Gemini 3.1 Pro). The principle: the
REFERENCES ARE LAW (they own identity + look); the TEXT owns only motion, performance beats, camera freedom and audio
rules. Let Seedance do the heavy lifting. Prose-first (fal's own I2V calls are plain prose); this module is the internal
spec that emits that prose.

Six sections, always in this order:
  12s / 16:9  →  REFERENCE LAW  →  SCENE  →  ACTION / PERFORMANCE  →  CAMERA  →  AUDIO  →  NEGATIVES

Rules baked in (so they can never drift):
  • NO character DESCRIPTION in the text — identity comes ENTIRELY from @图1 (keyframe) + @图2/@图3 (turnarounds). The
    highest-ROI fix: kills the "copy exactly" vs "Pixar-quality" contradiction that makes the model redesign faces.
  • ROLE LABELS, not names — "the larger bee" / "the smaller bee" (avoids the name-trap; names still live in @AudioN).
  • VOICE lives IN the render: each speaker "says @AudioN" (the fal-documented pattern → Seedance OUTPUTS the supplied
    11Labs voice), lip-synced, no other speech. generate_audio stays TRUE so Seedance ALSO scores ambience/SFX/underscore.
  • CAMERA is loose — Seedance directs cinematically; we only forbid chaos and demand both bees stay readable + on-model.
  • 12s is action-dense: if a beat drifts past ~7s, split into a 2-clip fallback rather than rewriting.
"""

import os, json
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
    """Generate the DEFINITIVE 6-section Seedance prompt from a Director beat — the signed-off model, for ANY beat of ANY
    episode. `scene` = optional scene-plate dict (look/definingFeature/location). References are law; the faithful dialogue
    lives in @Audio1 (never in the prose)."""
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
    become a reference to the track, so Seedance never renders text or invents a second voice."""
    import re as _re
    return _re.sub("[“\"‘']{1}[^”\"’']{2,80}[”\"’']{1}",
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
    ph = _strip_spoken_words(str(beat.get("pauseHold") or "").strip())
    if ph: bits.append(ph)                                   # the Docter held beat — the laugh lands in stillness
    tail = ("Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional "
            "timing; the performance carried in the eyes, the breath and the weight.")
    pf = str(beat.get("physicalFeeling") or "").strip()
    if pf: tail += " The take should feel like: " + pf
    bits.append(tail)
    return _delabel(" ".join(bits), cast, used=used)

def _audio_v2(beat, cast):
    has = bool(beat.get("speakers")) or any((c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))
    if beat.get("wordlessHeld") is True or not has:
        base = ("this beat has NO character dialogue — generate no speech or voices at all. Seedance generates and "
                "mixes the scene ambience, gentle character SFX and a light underscore that fits the moment (no sung lyrics).")
    else:
        base = ("use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US "
                "lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate "
                "voice, and no other speech. Seedance generates and mixes everything else")
        si = _delabel(_strip_spoken_words(str(beat.get("soundIntent") or "").strip()), cast, used=set(cast))
        base += (": " + si if si else ": the scene ambience, gentle character SFX and a light playful underscore")                 + " — kept low under the voice (no sung lyrics)."
    return base

_SIDES = ["frame-LEFT", "frame-RIGHT", "frame-CENTRE"]

def for_beat_v2(beat, scene=None):
    """The definitive 6-section prompt, now carrying the Director's ACTUAL direction. Same law, richer canvas."""
    dur = int(beat.get("durationSec") or 12); dur = max(8, min(15, dur))
    chars = beat.get("openingCast") or beat.get("characters") or []
    ref_bits, any_bee = [], False
    for i, name in enumerate(chars):
        role, is_bee = _char_meta(name); any_bee = any_bee or is_bee
        side = _SIDES[min(i, 2)] if len(chars) > 1 else None
        ref_bits.append(f"@图{i + 2} is {role}" + (f" ({side})" if side else ""))
    reflaw = _REFLAW_HEAD + ((" " + "; ".join(ref_bits) + ".") if ref_bits else "") + _REFLAW_TAIL
    cam = CAMERA_GENERIC + ((" " + _delabel(str(beat.get("cameraArc")).strip(), chars, used=set(chars))) if beat.get("cameraArc") else "")
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

if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
    code = sys.argv[2] if len(sys.argv) > 2 else "1.B1"
    d = json.load(open(pkg))
    beat = next(b for b in d.get("beats") or d.get("shots") or [] if (b.get("beatCode") or b.get("shotCode")) == code)
    scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(beat.get("sceneNumber"))), None)
    prompt = for_beat(beat, scene)
    print(f"===== GATE-3 SEEDANCE PROMPT — {code}  ({len(prompt)} chars) =====\n")
    print(prompt)
