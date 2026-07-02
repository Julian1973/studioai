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

# ── ROLE LABELS (identity is locked by the refs, NEVER described here) ──────────────────────────────────────────────
ROLE = {"Fuzzby": "the larger bee", "Zenny": "the smaller bee"}   # @图2 = larger/eager · @图3 = smaller/calm

REFERENCE_LAW = ("REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the two bees EXACTLY as drawn (no redesign, no "
    "morphing, no rescale, no new accessories) and copy the environment and lighting from it. @图2 is the LARGER, eager "
    "bee (frame-LEFT); @图3 is the SMALLER, calm, deadpan bee (frame-RIGHT) — their turnarounds lock proportions, "
    "markings and glasses. Add ONLY motion and performance. No extra characters, no redesign.")

CAMERA = ("Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they help the "
    "comedy — but keep BOTH bees readable and on-model at all times. No chaotic camera.")

# WING LAW — a bee in the air ALWAYS has beating wings. Seedance must never render a mid-air bee with still/frozen wings.
WING_LAW = ("WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, "
    "a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, "
    "gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee "
    "that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.")

NEGATIVES = ("no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, no "
    "on-screen text or subtitles, no logos or watermarks, no foreign-language speech, no crystals on or attached to the bees, "
    "no still/frozen/motionless wings on any bee that is airborne, no bee gliding or hovering with static wings.")

SEGMENTS = {
  "1.B1": {
    "scene": ("Warm golden morning deep in the enchanted crystal-woodland — a lane of tall flowers swaying in the warm "
              "breeze, long soft necks and bright open petals heavy with pollen, stretching high above the grass; towering "
              "golden lilies, soft volumetric sun through the canopy, drifting golden pollen, embedded amethyst/pink/teal "
              "crystals belonging to the world only, shallow depth of field."),
    "action": ("FAST, JOYFUL POLLEN FLIGHT — open with BOTH bees already up and WORKING, weaving quickly between the tall "
               "flowers, collecting pollen flower to flower, in constant energetic flight. The smaller, sleeker bee "
               "(frame-right) works with smooth, calm precision — neat, efficient, graceful, gathering pollen in clean "
               "confident arcs. The larger, eager bee (frame-left) does NOT: he zig-zags wildly through the air, humming "
               "loudly, thrilled with himself. He dips low into a flower, scoops a big puff of pollen, then over-commits — "
               "spins sideways and bumps clean into a broad leaf, FWIP, a real weighty bounce, pollen puffing — then "
               "bounces back into the air and straightens up, proud. The smaller bee glides up beside him, still "
               "collecting, and watches him for a beat with a flat, dry look, then asks her question. He FREEZES mid-hover "
               "— wings locking, eyes widening — and turns slowly to face her, deeply, theatrically offended. Keep it "
               "KINETIC and fast: constant weaving flight, the crisp contrast of her grace against his chaos; weighty "
               "cartoon physics on the leaf bump — anticipation, impact, follow-through; readable comedy timing."),
    "camera": "Keep the camera MOVING with the flight — energetic but smooth, following the weave between flowers — then settle as the larger bee freezes at her question.",
    "speakers": ["Fuzzby", "Zenny"],
  },
  "1.B2": {
    "scene": "The same golden-morning flower lane, warm volumetric light, towering golden lilies, drifting pollen, world crystals in the background only.",
    "action": ("The larger, eager bee hovers, chest still puffed with pride. The smaller, calm bee drifts beside him and "
               "asks her question with a flat, genuinely curious look. He freezes — wings locking, eyes widening — then "
               "turns slowly, theatrically offended, and strikes a dramatic heroic pose, one paw thrust out, chin high. The "
               "instant he strikes it he loses balance: he drops straight down, bounces off a soft lily petal with real "
               "compression and spring-back, spins once, rights himself, and hovers again as though nothing happened. A "
               "tiny puff of pollen hangs in the air. The smaller bee blinks once, slowly, utterly dry. He breaks into a "
               "wide, unbothered grin. Weighty cartoon physics: clear anticipation on the pose, a sharp drop with squash on "
               "the bounce, smooth follow-through on the recovery."),
    "camera": "Favour a locked medium two-shot so the drop-and-recover timing plays in a stable frame.",
    "speakers": ["Zenny", "Fuzzby"],
  },
  "1.B3": {
    "scene": "The golden-morning flower lane, towering lilies heavy with pollen, world crystals in the background — with the faintest grey undertone creeping into the frame edges by the end.",
    "action": ("The larger, eager bee, buzzing with self-importance, gestures mid-lecture. He zooms to a golden lily and "
               "plunges his whole face into the pollen-rich centre — a beat of stillness — then pulls back out with his "
               "face absurdly caked in a thick yellow pollen moustache, blinking with total sincerity. The smaller bee "
               "fights not to laugh: her mouth twitches, her eyes crinkle. He gasps, a full-body gasp, wings flaring, "
               "frantically wipes his face and only smears it worse, then dives toward another flower, clips a thin branch, "
               "and tumbles end over end — THUP THUP THUP — bouncing off leaves and petals, pollen puffing at each impact, "
               "landing upside-down inside a large blossom with his legs kicking. A beat. Then POP — he springs upright in "
               "a burst of pollen, hovering triumphantly. The smaller bee rolls her eyes, but she is smiling now — a real, "
               "warm smile. Weighty cartoon physics: distinct impact points and rebounds on the tumble, real weight on the "
               "upside-down hang."),
    "camera": "Push in subtly on the moustache reveal, then widen and hold a locked medium-wide for the tumble and pop-up.",
    "speakers": ["Fuzzby", "Zenny"],
  },
  "1.B4": {
    "scene": ("The flower lane as the light turns: the golden morning cooling to a moody grey-green, lilies swaying harder "
              "in a strengthening breeze, world crystals glowing faintly against the darkening canopy, the first faint "
              "drizzle at the frame edges."),
    "action": ("The larger, eager bee, still humming, dives face-first into a golden lily and comes up caked in yellow pollen. A "
               "distant RUMBLE of thunder rolls through — low, long, resonant. He freezes mid-hover, wings stopping, and "
               "turns his pollen-covered face slowly toward the sky, eyes wide; the light cools in real time, warmth "
               "draining from the frame. The smaller bee glances toward the darkening canopy, calm but alert. He recovers "
               "his bravado, puffs out his pollen-caked chest — then immediately pivots, flies straight into the nearest "
               "lily and gets completely stuck, back legs kicking uselessly, pollen puffing. The smaller bee watches, a "
               "long slow blink, then sighs — a full-body sigh, shoulders dropping, one paw rising to her temple in quiet "
               "exasperation."),
    "camera": "Hold a locked medium-wide and let the darkening sky and swaying stalks do the dramatic work.",
    "speakers": ["Fuzzby", "Zenny"],
  },
}

def _audio_line(speakers):
    # DEFINITIVE (3-model consensus): ONE supplied track. Use ONLY @Audio1 for ALL dialogue — Seedance outputs the
    # supplied 11Labs voice and each character lip-syncs to its own lines in @Audio1, in order. generate_audio scores rest.
    return ("use ONLY @Audio1 for ALL dialogue — the bees speak the words in @Audio1 with precise en-US lip-sync, each "
            "mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other "
            "speech. Seedance generates and mixes everything else: soft meadow ambience, gentle character SFX (wing-buzz, "
            "the little bump and bounce, a proud puff), and a light playful underscore kept low under the voice (no sung lyrics).")

def build(seg_id):
    """The FINAL Seedance video prompt (plain prose) for a segment — the definitive 6-section structure."""
    s = SEGMENTS[seg_id]
    cam = (CAMERA + (" " + s["camera"] if s.get("camera") else ""))
    return ("12 seconds, 16:9.\n\n"
            f"{REFERENCE_LAW}\n\n"
            f"{WING_LAW}\n\n"
            f"SCENE: {s['scene']}\n\n"
            f"ACTION / PERFORMANCE: {s['action']}\n\n"
            f"CAMERA: {cam}\n\n"
            f"AUDIO: {_audio_line(s['speakers'])}\n\n"
            f"NEGATIVES: {NEGATIVES}")

def definitive(code):
    """The DEFINITIVE Gate-3 prose for a locked segment, or None if this beat has no segment. THE single routing point —
    BOTH the studio preview (cb_seedance.get_seedance_prompt) AND the render (cb_beats.run) call this, so the studio can
    never PREVIEW one prompt and FIRE another. If a beat is added/removed from SEGMENTS, both paths change together."""
    return build(code) if code in SEGMENTS else None

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

def refs_for(seg_id, keyframe, fuzzby_sheet, zenny_sheet):
    """Image refs in @图N ORDER: @图1 keyframe, @图2 larger (Fuzzby) sheet, @图3 smaller (Zenny) sheet."""
    return [keyframe, fuzzby_sheet, zenny_sheet]

if __name__ == "__main__":
    import sys
    sid = sys.argv[1] if len(sys.argv) > 1 else "1.B1"
    print(f"===== GATE-3 SEEDANCE PROMPT — {sid}  ({len(build(sid))} chars) =====\n")
    print(build(sid))
