#!/usr/bin/env python3
"""GATE 3 — the SINGLE SOURCE OF TRUTH for the Seedance video prompt.

PURGED 2026-07-06 (Julian's ruling, THE DEFINITIVE BUILD — "the v4 emitter is the SOLE prompt author... no
hand-authored prompt text, anywhere, ever"): v1 (`for_beat`), v2 (`for_beat_v2`) and v3 (`for_beat_v3`, both
its prose and JSON emitters) are DELETED, not merely deprecated — there is no fallback chain left. `emit_v4`/
`for_beat_v4`, reached only through `shipped_prompt()`, is the sole builder. An empty result is never degraded
to a weaker builder; it surfaces as an empty prompt, exactly like any other missing-data condition, for the
caller's own empty-prompt handling to catch. Full history of how v4 was arrived at (the six-attempt frame-one
campaign, the junction-type pivot, the plate-anchor fix) lives in CLAUDE.md's dated rules — this file states
what is true now, not why.

Governing principles, baked in so they can never drift:
  • NO character DESCRIPTION in the text — identity comes ENTIRELY from @图1 (keyframe/state-reference) +
    @图2/@图3... (turnarounds), name-welded directly to the slot ("Fuzzby is the bee from @图2").
  • VOICE lives IN the render: @Audio1 is the sole vocal source, driving generation directly — never
    stitched on after (no post voice swap, ever, CLAUDE.md rule 29).
  • The scene plate is a STANDING ANCHOR on every beat, opener or relay (rule 39) — never relay-only.
  • CAMERA is loose but disciplined — locked during any spoken line (a hum/sing-song is motion-exempt, rule
    38), free otherwise, species-scaled, never chaotic.
  • Every beat renders at HANDLE_TOTAL seconds (13s action + 2s settle, the Handle Doctrine) — a fixed
    constant, never per-beat.
"""

import os, re, json
import paths as P                             # T30 Phase 3 — show-specific "laws" load from the show's tenant dir

# STYLE LAW — the show's confirmed style line, loaded from the show profile (shows/crystal-bears/laws/style.txt,
# declared in profile.json's laws.style key). The inline string is the fallback if the law file is ever missing.
_STYLE_LAW_FILE = os.path.join(os.path.dirname(P.CONFIG), "laws", "style.txt")
try:
    STYLE_LAW = open(_STYLE_LAW_FILE, encoding="utf-8").read().strip()
except Exception:
    STYLE_LAW = ("Premium 3D animated feature film aesthetic for children aged 4 to 8, bright hyper saturated "
        "colours, warm golden hour sunlight with volumetric rays, glowing magical particles, lighthearted highly "
        "expressive slapstick comedy")

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

def _strip_spoken_words(text):
    """Law 6 (no spoken words, ever): strips any quoted dialogue fragment out of prose destined for the
    shipped prompt — dialogue lives only in @Audio1, never in the text a video model reads as staging."""
    return re.sub(r'["“][^"”]*["”]', "", str(text or "")).strip()

# THE HANDLE DOCTRINE (Julian, 2026-07-03) — "Every shot shoots long so the cutter has meat to trim into."
# Every beat renders at 15s. 13s is the story-action budget (split across the beat's own cuts by weight); the
# final 2s are a DIRECTED LIVING SETTLE appended to the closing action, never dead air — the relay's harvest
# window (the sharpest frame anywhere in those 2s) AND Gate 4's trim handle (the editor cuts into the settle
# per join, CLAUDE.md rule 19) both depend on it.
HANDLE_TOTAL = 15
HANDLE_SETTLE = 2
HANDLE_ACTION = HANDLE_TOTAL - HANDLE_SETTLE

def _v3_ambience(scene):
    """THE LOCKED AMBIENT BED (Julian, 2026-07-04 — "the ambient audio description line, word for word
    identical every clip"): the scene's constant background sound, read straight from the scene's own
    authored ambientBed field — never invented, never varying beat to beat (the Scene Bubble Law). Empty
    when the scene has no ambientBed authored yet."""
    if not scene:
        return ""
    return str(scene.get("ambientBed") or "").strip()

def _style():
    return STYLE_LAW

def _standing_negatives(any_bee):
    """The SIX standing negatives, always exactly six: four universal (no morph/redesign/rescale, no extra
    characters/props, no on-screen text, no foreign-language speech) plus two species-appropriate ones (a
    bee cast: no crystals on the bees, no frozen wings airborne; otherwise: no flicker/compression, no
    lighting/palette continuity break)."""
    core = ["no morphing, redesign or rescale of the characters", "no extra characters or props",
            "no on-screen text, subtitles, logos or watermarks", "no foreign-language speech"]
    core += (["no crystals on or attached to the bees", "no still or frozen wings while airborne"] if any_bee
             else ["no flicker or compression artifacts", "no continuity break in lighting or palette"])
    return core[:6]

# ══════════ THE JUNCTION-TYPE PIVOT (Julian's ruling, CLAUDE.md rule 31, 2026-07-05) ══════════
# "The relay has been enforcing the wrong kind of join." Most beats are a NEW GAG ARC — an editorial cut to
# a fresh camera setup, already at the new beat's own energy — not a seamless continuation of the previous
# instant. Every beat declares its OWN junction type; the field lives on the beat itself (`junctionType`),
# never inferred or guessed.
JUNCTION_INTENTIONAL = "intentional_next_shot"   # THE DEFAULT — a new gag arc, a fresh camera setup
JUNCTION_SEAMLESS = "seamless_continuation"       # ONLY when the director's own cut explicitly continues
_JUNCTION_TYPES = (JUNCTION_INTENTIONAL, JUNCTION_SEAMLESS)

def _junction_type(beat):
    """A beat that does not declare a junction type is `intentional_next_shot` by default — never
    `seamless_continuation` by omission (Julian's ruling is explicit on this: omission is never read as
    the stronger, rarer claim)."""
    j = str(beat.get("junctionType") or "").strip()
    return j if j in _JUNCTION_TYPES else JUNCTION_INTENTIONAL

_V4_ORDINALS = ("first", "second", "third", "fourth", "fifth")

def _v4_species(role):
    parts = [p.strip() for p in str(role).split(",")]
    return parts[-1].split()[-1] if parts and parts[-1] else "character"

def _v4_scene_noun(scene):
    """A short location NOUN for the state-carry sentence's lighting clause ("the meadow lighting") — rule 33/34
    (2026-07-05). Mechanical: the scene's own `locationId` (e.g. "crystal_cove_meadow" -> "meadow"), never
    invented. Falls back to "scene" when locationId is missing or unparseable."""
    lid = str((scene or {}).get("locationId") or "").strip()
    if not lid:
        return "scene"
    return lid.rsplit("_", 1)[-1] or "scene"

def _v4_state_carry(cast, marks, scene):
    """THE STATE-REFERENCE clause for an `intentional_next_shot` beat's @图1 — a FIXED CATEGORICAL template:
    identity, temporary marks/wardrobe, lighting, world-position — plus the Coverage Law's explicit spatial
    leash: the new camera setup stays CLOSE to the anchor's position, in the SAME space, never a relocation
    or a fresh establishing wide. `marks` is a SHORT, hand-authored phrase (the `carryMarks` field — never
    the full endStateStill prose) naming what specifically persists ("the pollen on their legs," "the
    smeared moustache"). Raises ManifestFieldMissing instead of a generic phrase when the predecessor hasn't
    authored carryMarks yet — a gate-ordering gap this beat should never have reached in a correctly-
    manifest-gated pipeline, but this function refuses rather than papering over it either way. `scene`
    supplies the lighting noun via `_v4_scene_noun`."""
    import cb_qa
    subjects = " and ".join(cast) if cast else "the characters"
    marks_txt = str(marks or "").strip().rstrip(".")
    if not marks_txt:
        raise cb_qa.ManifestFieldMissing("carryMarks", "previous beat's own field, needed for this beat's @图1 state-carry clause")
    noun = _v4_scene_noun(scene)
    return (f"@图1 is the state reference from the previous beat. Carry everything it shows — "
            f"{subjects}'s appearance, {marks_txt}, the {noun} lighting and their positions in the world — "
            f"but open on a fresh camera setup within the same space, close to where @图1 shows the "
            f"characters. The camera moves; the world does not.")

def _v4_references(beat, scene, cast, relay, plate_n, junction=None, prev_end_state_still=None, prev_carry_marks=None):
    """The reference header — every entry a terse one-liner, names welded to character slots. plate_n is
    ALWAYS given (Julian's ruling, 2026-07-06 rule 39 — the plate is a standing anchor, not relay-only): the
    scene plate anchors the world's canonical look for the WHOLE clip regardless of whether this is the
    scene's own opening beat or a relay beat — a beat's own signed keyframe only shows what's visible in
    that one frame, and the plate covers whatever the camera reveals beyond it.
    junction (rule 31): a `seamless_continuation` relay beat keeps @图1 as the locked opening-frame anchor;
    an `intentional_next_shot` relay beat (the default) gets @图1's STATE-REFERENCE clause instead
    (_v4_state_carry) — the beat opens on its own fresh setup, carrying state only. prev_end_state_still is
    accepted for call-signature parity but UNUSED here — the marks clause comes from `prev_carry_marks`, a
    short phrase, never the full endStateStill sentence.
    @Video1: motion energy and action continuity ONLY. Never camera framing, shot size or composition — the
    camera setup for THIS beat comes from its own direction (the opener/opens-on/camera-discipline
    sentences), never from @Video1's own framing."""
    refs = {}
    if relay:
        if junction == JUNCTION_SEAMLESS:
            refs["@图1"] = ("@图1 is the exact opening composition and visual anchor. Begin on this exact layout, "
                            "camera angle, character scale and lighting.")
        else:
            refs["@图1"] = _v4_state_carry(cast, prev_carry_marks, scene)
        refs["@Video1"] = ("Use @Video1 only for motion energy and action continuity. Do not copy its camera "
                           "framing, shot size, or composition — the camera setup comes from this beat's own "
                           "direction.")
    else:
        refs["@图1"] = "@图1 is the opening keyframe — TRUTH for environment, lighting and continuity."
    for i, name in enumerate(cast):
        refs[f"@图{i + 2}"] = f"Use @图{i + 2} for {name}'s exact appearance."
    if plate_n:
        refs[f"@图{plate_n}"] = f"Use @图{plate_n} for this scene's lighting, palette and environmental texture."
    refs["@Audio1"] = ("@Audio1 is the only dialogue, hums, sing-song rhythm and vocal performance source. It "
                       "controls timing, mouth rhythm, speaker turns and emotional delivery.")
    return refs

def _v4_timing_clock(beat, cast):
    """The continuous prompt's own timing clock — a weighted per-cut duration split (dialogue cuts get real
    screen time), rendered as running-clock prose. The settle is its own trailing HANDLE_SETTLE-second
    segment, never folded into the last cut's own weighted time."""
    cuts = beat.get("cuts") or []
    if not cuts:
        return ""
    raw, weights = [], []
    for c in cuts:
        action = _strip_spoken_words(str(c.get("action") or "").strip()).rstrip(".")   # avoid "...airborne.; 5-9s"
        has_dlg = bool((c.get("dialogue") or "").strip())
        raw.append(action)
        weights.append(max(1, len(action) + (40 if has_dlg else 0)))
    total_w = sum(weights) or 1
    segs, running, n = [], 0, len(raw)
    for i, (a, w) in enumerate(zip(raw, weights)):
        sec = max(1, HANDLE_ACTION - running) if i == n - 1 else max(1, round(HANDLE_ACTION * w / total_w))
        start = running; running += sec
        segs.append(f"{start}-{running}s {a}")
    segs.append(f"{HANDLE_ACTION}-{HANDLE_TOTAL}s settle in character: {_v4_settle_text(beat, cast)}")
    return "Timing: " + "; ".join(segs) + "."

def _v4_settle_text(beat, cast):
    """FUZZBY'S ENERGY RETURNS (rule 33): the settle is IN CHARACTER, not a generic freeze — read from the
    beat's OWN authored `endState` (directing prose for this beat's ending, rule 27) verbatim, so a manic
    character stays visibly manic even at rest. Raises ManifestFieldMissing when endState isn't authored —
    never a generic idle-life fallback (rule 37)."""
    import cb_qa
    es = str(beat.get("endState") or "").strip().rstrip(".")
    if not es:
        raise cb_qa.ManifestFieldMissing("endState", "this beat's own settle text")
    return es

def _v4_speaker_order(beat, cast):
    """An ordered performance sentence built from the SAME cb_voice parser that cuts the real @Audio1 track
    — never drifts from what the track actually contains. Empty when the beat has no dialogue. The ordinal
    sequence walks the FULL turn-by-turn order (repeats included, e.g. Fuzzby-Zenny-Fuzzby renders all three
    turns) — a distinct-name dedupe would silently drop a returning speaker's later turn (rule found live on
    1.B5, 2026-07-06). The "performs only X's lines" declarations stay deduped to `distinct` (still one true
    statement per character regardless of how many turns they get)."""
    import cb_voice as V
    order = []
    for c in (beat.get("cuts") or []):
        dlg = (c.get("dialogue") or "").strip()
        if not dlg:
            continue
        for label, text in V._cut_segments(dlg):
            if text:
                name = V._resolve_speaker(label, beat)
                if name:
                    order.append(name)
    if not order:
        return ""
    distinct = []
    for n in order:
        if n not in distinct:
            distinct.append(n)
    if len(distinct) == 1:
        return f"{distinct[0]} performs only {distinct[0]}'s lines in @Audio1."
    perf = "; ".join(f"{n} performs only {n}'s lines in @Audio1" for n in distinct)
    ords = ", ".join(f"{n}'s line comes {_V4_ORDINALS[min(i, len(_V4_ORDINALS) - 1)]}" for i, n in enumerate(order))
    return f"{perf} — in this beat {ords}."

def _v4_audio_prohibition():
    return "Do not invent extra speech, hums or vocal sounds beyond @Audio1."

def _v4_opens_on(beat):
    """THE COVERAGE LAW's mechanical bridge (rule 34 — "a scene is one continuous spatial bubble"): a beat's
    own declared opening — WHO the camera opens on and their immediate mid-motion state — is a hand-
    authored Layer-2 field (`opensOn`: {"who": <name>, "action": <short mid-motion text>}), never invented,
    wrapped in a fixed "OPEN ON {NAME} mid-motion:" declaration. Empty when a beat hasn't authored this
    field yet — never fabricated."""
    oo = beat.get("opensOn") or {}
    who = str(oo.get("who") or "").strip()
    action = str(oo.get("action") or "").strip().rstrip(".")
    if not (who and action):
        return ""
    return f"OPEN ON {who.upper()} mid-motion: {action}."

def _v4_camera_discipline(cast, opens_on_who=None, camera_arc=None):
    """THE CAMERA-DISCIPLINE LAW (rule 34): species-scaled (mechanical, from the cast — "bee-scale," falling
    back to "character-scale" for a mixed or empty cast) and, when the beat has declared an `opensOn`
    character, names the SPECIFIC eyeline-follow character and the SPECIFIC action character the camera may
    track. Falls back to generic phrasing when there's no opensOn character or the cast isn't exactly a pair.
    CAMERA LAW AMENDMENT (rule 38): the lock is scoped to SPOKEN lines only — a continuous hum or sing-song
    vocalization is motion-exempt (see cb_qa._is_motion_exempt_vocal, the matching QA-side check).
    THE CAMERA ARC OVERRIDE (Julian's ruling, 2026-07-06, watching 1.B1's first take sag flat): when the
    beat has its own authored `cameraArc` — a whole-beat camera description, an existing field the emitter
    never actually read — it REPLACES the generic species-scaled sentence. The generic "small motivated
    moves" line was found, on real footage, to under-specify camera intent badly enough to read as static.
    The camera-lock law is APPENDED regardless of which camera description precedes it — that part is a
    hard rule, never optional."""
    lock_law = ("Camera locked whenever a character speaks a line (a continuous hum or sing-song is not a "
                "lock trigger).")
    if camera_arc:
        return f"{str(camera_arc).strip().rstrip('.')}. {lock_law}"
    species_set = {_v4_species(_char_meta(c)[0]) for c in cast} if cast else set()
    scale = species_set.pop() if len(species_set) == 1 else "character"
    others = [c for c in cast if c != opens_on_who] if opens_on_who else []
    if opens_on_who and len(others) == 1:
        return (f"Camera {scale}-scale and readable throughout — it may follow {opens_on_who}'s eyeline and "
                f"{others[0]}'s action with small motivated moves. {lock_law}")
    return (f"Camera {scale}-scale and readable throughout — it may follow character eyelines and action "
            f"with small motivated moves. {lock_law}")

def _v4_acting_rules(beat, cast):
    """Per-character acting essence, mechanical from each cast member's OWN characters.json bible.actingRule
    (a tightly-scoped one-line field, distinct from the much longer essence/cadence/mannerisms prose), plus
    the beat's own authored `actingContrast` (which characters play off each other and how — a director's
    call, never hardcoded per-cast). Empty when no cast member has an actingRule authored yet — never
    invented."""
    lines = []
    for name in cast:
        rule = str(((_CHARS.get(name) or {}).get("bible") or {}).get("actingRule") or "").strip()
        if rule:
            lines.append(f"{name} is {rule.rstrip('.')}.")
    contrast = str(beat.get("actingContrast") or "").strip()
    if contrast:
        lines.append(contrast)
    return " ".join(lines)

def _v4_continuity(beat):
    """A hand-authored static picture (endStateStill, rule 27 — never auto-derived from endState) plus a
    carry-forward tail naming THIS beat's own authored `carryMarks` (the same short phrase the NEXT beat's
    @图1 state-carry clause will quote) plus the show's universal warm light. Raises ManifestFieldMissing
    instead of a generic tail when carryMarks isn't authored — both endStateStill and carryMarks are
    required TECHNICAL-contract fields on every beat. Empty overall (not a raise) when endStateStill itself
    isn't authored — block-by-omission, unchanged."""
    es = str(beat.get("endStateStill") or "").strip()
    if not es:
        return ""
    marks = str(beat.get("carryMarks") or "").strip().rstrip(".")
    if not marks:
        import cb_qa
        raise cb_qa.ManifestFieldMissing("carryMarks", "this beat's own field, needed for its continuity tail")
    tail = f"{marks[:1].upper()}{marks[1:]}, and the warm light carry into the next beat."
    return f"End with {es.rstrip('.')}. {tail}"

def _v4_prohibited(beat, any_bee):
    """The beat's own authored stagingProhibited (Layer 2, director-named failure modes specific to this
    beat's gag) merged with the six standing negatives (_standing_negatives, unchanged — always exactly six)."""
    staging = [str(x).strip() for x in (beat.get("stagingProhibited") or []) if str(x).strip()]
    return staging + _standing_negatives(any_bee)

def _v4_opener(beat, relay, junction):
    """THE OPENER SENTENCE — branches by junction type (rule 31). An `intentional_next_shot` relay beat
    (the default) states only its own duration/tone — @图1's own reference text (via _v4_state_carry) and
    the beat's own `opensOn` sentence already carry the "fresh camera setup" instruction in full, so a third,
    generic restatement here would be exactly the "reference re-description reads as drift" mechanism this
    doctrine already fixed once. A `seamless_continuation` relay beat (or any non-relay opener beat, which
    has no junction concept at all — it opens from its own generated keyframe) still begins "from @图1's
    exact opening composition.\""""
    mode = str(beat.get("comedyMode") or "").strip().upper()
    tone_word = " comedy" if mode == "BIG" else (" emotional" if mode == "TRUE" else "")
    lead = f"Generate one continuous {HANDLE_TOTAL}-second 3D CGI animated{tone_word} beat."
    if relay and junction == JUNCTION_INTENTIONAL:
        return lead
    return f"{lead} Begin from @图1's exact opening composition."

def emit_v4(beat, scene, cast, relay, prev_end_state_still=None, prev_carry_marks=None, junction=None):
    """THE blessed template's assembler — the sole prompt author (rule 39's "the v4 emitter is the SOLE
    prompt author — no hand-authored prompt text, anywhere, ever"). junction: resolved from the beat's own
    `junctionType` field when not given explicitly. prev_end_state_still is accepted for call-signature
    parity but UNUSED here — @图1's state-carry content comes from `prev_carry_marks` (a short phrase, see
    _v4_state_carry), not the predecessor's full endStateStill sentence. Also assembles the beat's own
    `opensOn` sentence (Coverage Law bridge) and the `acting_rules` field (Fuzzby's energy-return law)."""
    junction = junction or _junction_type(beat)
    any_bee = any(_char_meta(n)[1] for n in cast)
    # THE PLATE IS A STANDING ANCHOR, NOT A RELAY-ONLY ONE (rule 39): unconditional, opener beats included.
    plate_n = len(cast) + 2
    opener = _v4_opener(beat, relay, junction)
    bindings = " ".join(f"{name} is the {_v4_species(_char_meta(name)[0])} from @图{i + 2}."
                        for i, name in enumerate(cast))
    # THE COVERAGE LAW (rule 34) applies ONLY to an intentional_next_shot relay beat — a `seamless_continuation`
    # join is definitionally the SAME shot continuing, not a new camera angle, so there is no eyeline bridge to
    # state; a non-relay opener beat has no predecessor to bridge from either.
    intentional_relay = relay and junction == JUNCTION_INTENTIONAL
    opens_on = _v4_opens_on(beat) if intentional_relay else ""
    clock = _v4_timing_clock(beat, cast)
    speaker_sent = _v4_speaker_order(beat, cast)
    opens_on_who = (str((beat.get("opensOn") or {}).get("who") or "").strip() or None) if intentional_relay else None
    camera = _v4_camera_discipline(cast, opens_on_who, camera_arc=beat.get("cameraArc"))
    prompt_body = " ".join(x for x in
                           [opener, bindings, opens_on, clock, speaker_sent, _v4_audio_prohibition(), camera]
                           if x)
    doc = {
        "duration": HANDLE_TOTAL, "aspect": "16:9", "mode": "reference-to-video",
        "references": _v4_references(beat, scene, cast, relay, plate_n, junction=junction,
                                     prev_end_state_still=prev_end_state_still, prev_carry_marks=prev_carry_marks),
        "style": _style(),
        "ambience": _v3_ambience(scene),
    }
    acting = _v4_acting_rules(beat, cast)
    if acting:
        doc["acting_rules"] = acting
    doc["prompt"] = prompt_body
    doc["continuity"] = _v4_continuity(beat)
    doc["prohibited"] = _v4_prohibited(beat, any_bee)
    return json.dumps(doc, indent=2, ensure_ascii=False)

def for_beat_v4(beat, scene=None, relay=False, prev_end_state_still=None, prev_carry_marks=None):
    cast = beat.get("openingCast") or beat.get("characters") or []
    if not (beat.get("cuts") or []):
        return "", "v4 (empty — no cuts)"
    return emit_v4(beat, scene, cast, relay, prev_end_state_still=prev_end_state_still,
                   prev_carry_marks=prev_carry_marks), "v4"

def shipped_prompt(beat, scene=None, relay=False, prev_end_state_still=None, prev_carry_marks=None):
    """Returns (prompt, builder_label, is_definitive). v4 is the SOLE prompt author (rule 39, 2026-07-06,
    THE DEFINITIVE BUILD) — v3/v2/v1 and every fallback escape hatch are deleted, not merely deprecated. An
    empty v4 result is NOT degraded to a weaker builder; it surfaces as an empty prompt, exactly like any
    other missing-data condition, for the caller's own empty-prompt handling (e.g. cb_beats.run's "empty
    Seedance prompt — skipping") to catch. is_definitive is always True now — kept in the return signature
    for call-site compatibility across cb_beats/cb_seedance/cb_golden/cb_replicator, none of which need to
    change their unpacking. relay=True (RELAY CHAIN, rule 21) — see for_beat_v4. prev_end_state_still:
    accepted for signature compatibility, unused (see emit_v4's note — @图1's state-carry content comes from
    prev_carry_marks now). prev_carry_marks (rules 33/34): the PREVIOUS beat's own authored `carryMarks`,
    threaded to for_beat_v4 for @图1's state-carry clause. A missing required field (endState, carryMarks,
    etc.) raises cb_qa.ManifestFieldMissing, uncaught here — the caller's own manifest-aware except block
    (rule 37) turns that into a named refusal instead of a silent degrade."""
    v4, emitter4 = for_beat_v4(beat, scene, relay=relay, prev_end_state_still=prev_end_state_still,
                              prev_carry_marks=prev_carry_marks)
    return v4, f"cb_segprompt_v4 ({emitter4})", True

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
