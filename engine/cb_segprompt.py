#!/usr/bin/env python3
"""GATE 3 — the SINGLE SOURCE OF TRUTH for the Seedance video prompt.

GATE3_ANIMATION_DOCTRINE.md (repo root) is the Version of Record (Julian, 2026-07-06 — "This document
supersedes ALL prior Gate 3, prompt-structure, and emitter instructions"). This module implements it exactly:
`emit_v5`/`for_beat_v5`, reached only through `shipped_prompt()`, is the sole builder. HEADER + four blocks +
a Negative line (the standalone tech line CLOSER was retired 2026-07-08 — see CLOSER, below), assembled from
data, zero per-beat authoring, zero invented content — nothing
invented that canon defines; everything is extracted VERBATIM from the character's own existing store
(characters.json) or quoted, never paraphrased (the camera+ambience paragraph named in some older revisions
of this docstring was retired 2026-07-06, see BLOCK 4's own note below — fixed here 2026-07-07 as a real
internal inconsistency, since the rest of this docstring already correctly said it was gone):
  HEADER   duration/aspect/fps/format — "15s, 16:9, 24fps, 3D CGI beat." (fps folded in 2026-07-08 — see
           CLOSER, below — a real behaviour change from the header's own earlier text)
  BLOCK 1  STYLE — the show's style law, verbatim, plus an OPTIONAL scene-look sentence (`_v5_scene_look`).
           LEANED 2026-07-07 (Julian's ruling, decision 4): the universal style law no longer carries
           scene-specific atmosphere ("warm golden hour sunlight," pollen, meadow appearance) — that content
           moved to the scene's own `sceneLook` field, appended here as a second sentence (never a new
           "\n\n" block, so cb_qa.check_gate3_lint's block-index model stays unchanged).
  BLOCK 2  REFERENCES — one terse line per @图N/@Audio1 (doctrine §4a/4b's exact wording — "@图2 Fuzzby —
           match exactly," no species/role label; a scene opener's own keyframe states "begin on this exact
           composition"; a relay beat's @图1 is the FIXED state-reference sentence, never mad-libbed with the
           specific carryMarks text — that specificity is a Step 6 QA concern, cb_qa.check_join_state, never
           a prompt-text concern, since spelling it out would itself be an appearance-description leak).
           THE FIFTH ANCHOR, RETIRED (Julian, 2026-07-07, watching 1.B2's actual footage — "I don't think we
           should use approved... nearby within the same shot... the video I don't like it either, I think it
           confuses things... ref 1 which is the final best frame shot, the character references, then the
           audio"): @Video1 (rule 26's "FIFTH ANCHOR," added 2026-07-04 on fal's own field guidance that a
           video reference keeps motion/audio context better than a still-frame chain) is REMOVED from the
           reference stack entirely — two motion/position signals (a still frame AND a video clip) was reported
           live as confusing, not clarifying. @图1's relay wording also dropped "approved" and "nearby within
           the same space" (flagged as specific confusing phrases). SAME DAY, SECOND PASS (Julian — "I think
           what it does is it picks up the final frame and actually puts the first frame as the last frame...
           we don't have to mention the final shot... it doesn't know the final shot anyway"): the first pass's
           own replacement wording, "begin from this, the final frame of the previous shot," still named the
           reference image's PROVENANCE (that it came from a prior shot's end) rather than just its JOB (where
           this shot starts) — exactly the class of self-referential phrase rule 26/27 already found gets
           misread as a structural instruction about the CURRENT shot rather than a description of the past.
           Simplified to name the job only: "start from this frame" — no mention of "final," "previous shot,"
           or any temporal history the model has no way to verify anyway. `cb_beats.py` no longer builds or
           uploads the previous clip as a video reference for a relay beat's fire.
           THE CAST-SIZE FIX (2026-07-07, closing the long-open word-count ticket): only cast members ACTIVE
           in this beat's own text (`_v5_active_cast` — named in cuts/speakers/opensOn) get the full "match
           exactly" sentence; BACKGROUND cast members (present in the scene but doing nothing named in this
           specific beat — common in large-ensemble scenes 6/8/9/10) are consolidated into one shared line,
           still individually @图N-numbered (the image upload order is untouched) but not each repeating the
           whole sentence. This alone brought the median over-budget ensemble beat under the 400-word cap.
           THE ANTI-HOLD-SAFE RELAY WORDING (2026-07-07, Julian's ruling, decision 1 — superseding the
           "start from this frame" sentence): the relay @图1 line now names its provenance again ("the
           approved final frame of the previous beat") but qualifies it "matched exactly as the first frame
           ONLY" and adds an explicit anti-hold counter-instruction ("Do not hold the previous pose, replay
           the previous action, reset the characters or introduce unexplained repositioning") — addressing
           head-on the exact risk an adversarial check flagged earlier the same night against a similar,
           unqualified frozen-instant example. `beat.relayOpeningNote` (optional) appends one more
           beat-authored sentence naming who starts where and what breaks first; `beat.spatialAxis`
           (optional, decision 3) states a fixed blocking law (who's in which lane, never swap sides).
  BLOCK 3  ACTING DNA — one line per ACTIVE cast member (same split as Block 2), VERBATIM from `actingNote`
           (Fuzzby/Zenny) or falling back to `bible.mannerisms` (the 9 bears, who have none — FLAGGED, not
           silently accepted: some bears' mannerisms mix in appearance detail rule 5 forbids; Julian's own
           bible is the only editor of that content, this function just reports the field it drew from). A
           BACKGROUND cast member gets NO Acting DNA line at all — priming a performance register nothing in
           the shot list ever calls on was the actual bloat; their identity is still fully carried by their
           own reference image in Block 2.
  BLOCK 4  SHOT LIST (Julian's ruling, 2026-07-06, superseding the doctrine's flattened-storyBeat approach
           below) — one "{start}–{end}s — {framing}:" / "action. [speaker note]" two-line pair per authored
           cut, walking the beat's own cuts[] verbatim (camera + specific staging + who speaks, never the
           words, Law 6), ending on endState's living settle. THE SHOT-TIMING LAW (2026-07-08): each shot's
           header now states a mechanical time range (`_v5_shot_time_ranges` — a deterministic, weight-free
           division of HANDLE_TOTAL across N cuts) instead of a bare "Shot N" numeral — Julian, reviewing
           1.B2: "four shots in 15 seconds need time ranges, otherwise Seedance may spend too long on the
           flower entry and rush or omit the wipe." THE DELIVERY LAW (2026-07-07, decision 2): the speaker
           note is "{Name} performs {his/her} vocal beat from @Audio1 {delivery}." when the cut has an
           authored `delivery` field (acting direction — tone/intent, never words), falling back to the
           bare "{Name} speaks." form otherwise — see `_v5_cut_speaker_note`. The prior approach (a single
           flattened storyBeat summary, hard-capped at 80 words) was found live to silently drop every
           cut's camera and named staging — watching 1.B1's actual render, Julian: "where's the action...
           the cut saying what camera it is, what he's doing... where's the story beat?" The doctrine's own
           §2 80-word fence on this block is RETIRED by the same ruling; the whole-prompt hard cap
           (cb_preflight.py) is the real and only backstop now.
  CLOSER   THE STANDALONE TECH LINE IS RETIRED (2026-07-08): "24fps" folded into the HEADER, "smooth
           cinematic motion, shallow depth of field" dropped outright — Julian's own review of 1.B2's
           compile independently reached the same call this session's own `cb_qa.ANTI_SLOP_WORDS` check
           (rule 50) had already flagged that exact phrase for. The prompt now ends on the Negative line —
           the ONLY negation anywhere in the prompt: eleven standing items (doctrine §2) plus the beat's own
           stagingProhibited, merged, terse.

RETIRED this same doctrine (found on read, not previously true): character `bible.dos`/`bible.donts` no
longer feed the prompt at all — §3's own "Never in a prompt" list names them explicitly ("writer-room
guidance (dos/donts live at Gate 1 as review criteria)"), reversing the immediately-prior ruling that had
them feed per-beat staging/negatives. `_v5_character_staging`/`_v5_character_negatives` are deleted.

Word budget: 400 is the TARGET (not enforced here); 650 is a HARD BLOCK, enforced in cb_preflight.py
(cb_preflight.WORD_BUDGET_TARGET/WORD_BUDGET_BLOCK — raised 2026-07-07, rule 52, from 250/400: the old pair
predated the shot-list restoration below and decision 1's anti-hold-safe relay wording, both real content,
not bloat). The
BEAT STORY block's own 80-word sub-fence is RETIRED (2026-07-06, the shot-list ruling above) — a real
per-cut shot list cannot fit multiple cameras + actions in 80 words, and the whole-prompt 400-word cap was
always the real backstop. Every emit prints its own total word count at the call site (this module's own
__main__, cb_beats.run's per-beat log line, cb_beats.gate3_dryrun's returned dict) via `_v5_word_count`.

TWO CONTRADICTIONS FOUND ON READ, FLAGGED (CLAUDE.md rule 43), NOT SILENTLY RESOLVED:
  1. §3's table names the Acting DNA source as `shows/crystal-bears/bible/` — a folder confirmed NOT to
     exist — directly conflicting with Julian's own immediately-prior ruling that characters.json IS the
     character store. Defaulted to characters.json (`actingNote`/`bible.mannerisms`) — tested, working, and
     literally what he pointed at one message earlier.
  2. §2 states "Story block ≤80 words" twice, but §4a's own worked example for that block runs to roughly
     140-150 words. Built to the stated numeric rule (a repeated explicit rule outranks an illustrative
     example that may not have been word-counted).

Governing principles, baked in so they can never drift:
  • NO character DESCRIPTION in the text — identity comes ENTIRELY from @图1 (keyframe/state-reference) +
    @图2/@图3... (turnarounds), name-welded directly to the slot ("@图2 Fuzzby — match exactly").
  • VOICE lives IN the render: @Audio1 is the sole vocal source, driving generation directly — never
    stitched on after (no post voice swap, ever, CLAUDE.md rule 29).
  • The scene plate is a STANDING ANCHOR on every beat, opener or relay (rule 39) — never relay-only.
  • CAMERA is loose but disciplined — locked on the spoken line, free otherwise, species-scaled, never chaotic.
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
    # LEANED 2026-07-07 (Julian's ruling, decision 4) — atmosphere ("warm golden hour sunlight," "pollen")
    # moved out to the scene's own `sceneLook` field (see `_v5_scene_look`); this fallback mirrors style.txt.
    STYLE_LAW = ("Premium 3D CGI children's feature animation for ages 4 to 8; bright controlled colour, "
        "cinematic lighting, clear staging, expressive physical comedy and strong reference-first character "
        "consistency.")

_CHARS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "characters.json")
def _load_chars():
    try:
        d = json.load(open(_CHARS_PATH)); return d.get("characters", d)
    except Exception:
        return {}
_CHARS = _load_chars()

def _strip_spoken_words(text):
    """Law 6 (no spoken words, ever): strips any quoted dialogue fragment out of prose destined for the
    shipped prompt — dialogue lives only in @Audio1, never in the text a video model reads as staging.
    Also eats a directly preceding "with " (found live in 1.B1 cut 2's own framing field — "...pose, with
    'Nailed it.' landing on that stable frame" — a real, authored construction that introduces a quote
    inline) so the strip doesn't leave a dangling preposition ("...pose, with landing on that stable
    frame") once the quote itself is gone."""
    out = re.sub(r'(,?\s*\bwith\b\s+)?["“][^"”]*["”]\.?', "", str(text or ""))
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    return out.strip()

# THE HANDLE DOCTRINE (Julian, 2026-07-03) — "Every shot shoots long so the cutter has meat to trim into."
# Every beat renders at 15s. 13s is the story-action budget (split across the beat's own cuts by weight); the
# final 2s are a DIRECTED LIVING SETTLE appended to the closing action, never dead air — the relay's harvest
# window (the sharpest frame anywhere in those 2s) AND Gate 4's trim handle (the editor cuts into the settle
# per join, CLAUDE.md rule 19) both depend on it.
HANDLE_TOTAL = 15
HANDLE_SETTLE = 2
HANDLE_ACTION = HANDLE_TOTAL - HANDLE_SETTLE

def _style():
    return STYLE_LAW

def _v5_scene_look(scene):
    """Scene-level atmosphere line (Julian's ruling, 2026-07-07, decision 4 — trimming STYLE to a lean,
    universal constant and moving scene-specific atmosphere — warm morning light, pollen, meadow appearance —
    OUT of it and into the scene's own data instead, so a future scene with different light/weather isn't
    stuck reading Scene 1's words). Appended as a second sentence inside BLOCK 1 (joined with a space, never
    its own "\\n\\n" block — cb_qa.check_gate3_lint's block-index model counts blocks by splitting on the
    outer "\\n\\n" separator, and a new block would shift every index after it, the exact stale-index bug
    class rule 46 already found and fixed once). Optional — only appended when a scene has authored
    `sceneLook`; not yet manifest-enforced (a follow-up gate, not built here). Distinct from the scene's
    existing `look` field (the verbose establishing-plate composition text `cb_seedance.py`'s older validator
    reads as `env_desc`, rule 10's kept second layer) — `sceneLook` is a short, prompt-facing atmosphere line
    for v5 specifically, reset every scene boundary same as the plate/ambient bed (the Scene Bubble Law,
    rule 35)."""
    return str((scene or {}).get("sceneLook") or "").strip()

def _v5_possessive(name):
    """he/his or she/her from characters.json's own `gender` field — used only to phrase THE DELIVERY LAW's
    speaker note (see `_v5_cut_speaker_note`). Falls back to they/their for an ungendered or unrecognised
    character rather than guessing."""
    g = str((_CHARS.get(name) or {}).get("gender") or "").strip().lower()
    if g == "male":
        return "his"
    if g == "female":
        return "her"
    return "their"

def _standing_negatives():
    """THE ELEVEN STANDING NEGATIVES (GATE3_ANIMATION_DOCTRINE.md §2, 2026-07-06; the eleventh added by
    Julian's BUDGET RESOLUTION ruling, same day) — always exactly eleven, no longer species-conditional (the
    doctrine's own list states them unconditionally, cast composition notwithstanding — "no crystals on or
    attached to the bees" appears even in an all-bear scene). THE ELEVENTH ITEM is where negation about a
    character's own deflate/slump/dip behaviour now lives — previously stated as prose inside a character's
    own Acting DNA quote (Fuzzby's actingNote: "Any deflate that follows is a small slump or a dip, never the
    whole body shrinking"), which is now filtered OUT of the prompt-facing DNA slice (`_v5_positive_movement_slice`)
    specifically because this standing item covers it — negation belongs in the Negative block, not restated
    inside a quoted character-voice sentence.

    TERSENED (Julian, 2026-07-06, same ruling as the lean acting tag): the OLD best-received render's own
    negative line was a single terse clause ("--no text, watermarks, logos"). Every one of the eleven
    protections below is KEPT — nothing here is dropped, this is wording only, matching that old economy:
    short noun phrases, not full sentences."""
    return [
        "no character morphing/redesign/rescale",
        "no extra characters or props",
        "no on-screen text, subtitles, logos, watermarks",
        "no foreign-language speech",
        "no crystals on the bees",
        "no frozen wings airborne",
        "no 2D/flat animation",
        "no invented voices",
        "no floating/sinking through ground",
        "no body inflation",
        "no full-body deflation (slumps/dips only)",
    ]

# ══════════ JUNCTION TYPE — KEPT FOR RE-MINT SCOPING, NO LONGER A PROMPT-TEXT BRANCH ══════════
# GATE3_ANIMATION_DOCTRINE.md gives every relay beat the SAME @图1 wording (§4b — "differs by exactly one
# line" from the opener, no seamless/intentional split; @Video1 retired 2026-07-07) — so `emit_v5` no longer branches on
# this. But `junctionType` is still a real, separate PRE-FIRE mechanism: whether to run the NB2 re-mint
# cleanup pass on a harvested settle frame before it anchors the next beat (rule 32) is decided by the NEXT
# beat's own declared junction type, independent of what the shipped prompt says. cb_scene.remint_settle_frame,
# cb_beats.py's join-check and fire_next_beat, and cb_golden.py's relay-snapshot coverage all still call
# these — kept here rather than deleted, since removing them would break three other modules for a change
# this doctrine never actually asked for (it only changed the PROMPT shape).
JUNCTION_INTENTIONAL = "intentional_next_shot"   # THE DEFAULT — a new gag arc, a fresh camera setup
JUNCTION_SEAMLESS = "seamless_continuation"       # ONLY when the director's own cut explicitly continues
_JUNCTION_TYPES = (JUNCTION_INTENTIONAL, JUNCTION_SEAMLESS)

def _junction_type(beat):
    """A beat that does not declare a junction type is `intentional_next_shot` by default — never
    `seamless_continuation` by omission."""
    j = str(beat.get("junctionType") or "").strip()
    return j if j in _JUNCTION_TYPES else JUNCTION_INTENTIONAL


# ══════════════════════════════════════ THE V5 ENGINE ══════════════════════════════════════

_V5_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")

def _v5_word_count(text):
    """The word count printed at every emit (this module's __main__, cb_beats.run's log line,
    gate3_dryrun's returned dict) and enforced as a hard BLOCK in cb_preflight.py (cb_preflight.WORD_BUDGET_BLOCK,
    650 as of 2026-07-07 rule 52; WORD_BUDGET_TARGET, 400, is the target, not gated here — an emitter
    compiles what the data says, it never self-censors)."""
    return len(_V5_WORD_RE.findall(str(text or "")))

_SPEED_ADJ_RE = re.compile(
    r"\b(?:high-speed|fast(?:er|est)?|quick(?:ly|er|est)?|rapid(?:ly)?|hyper|manic(?:ally)?|frantic(?:ally)?|"
    r"chaotic(?:ally)?|wild(?:ly)?|erratic(?:ally)?|hasty|hastily|speed(?:y|ily)?|zooming|zooms|zoomed)\b",
    re.IGNORECASE)

def _v5_strip_speed_adjectives(text):
    """Block 4's mechanical transform (Julian, 2026-07-06 — "speed adjectives stripped"), applying rule 33's
    adjective-chaos ban ("a generic frenzy word with no physical beat behind it... is BANNED as unreadable")
    as a real edit rather than just a lint: a generic pace word spends a word of the budget saying nothing a
    video model can act on, when the beat's own named actions (already in storyBeat/endState) do the actual
    work. Collapses the resulting double-spaces/orphaned punctuation-spacing."""
    out = _SPEED_ADJ_RE.sub("", str(text or ""))
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    return out.strip()

def _v5_active_cast(beat, cast):
    """THE ACTIVE/BACKGROUND SPLIT (found via the front-to-back audit, 2026-07-07 — closing the long-open
    "cast-size word-count bug" ticket): a beat's own `cast` list is really "who's present in the scene," not
    "who's doing something in THIS beat" — confirmed by inspecting the 12 beats that were blowing the
    400-word cap: 8.B2 names only 2 of its 10 cast members anywhere in its own cuts/dialogue/opensOn; 9.B1/
    9.B2/9.B4 name 1-2 of 9; several others are similar. Giving every one of those un-named background
    characters their OWN full reference-binding line (Block 2) and acting-DNA line (Block 3) was the actual
    bloat — priming a performance register nothing in the shot list ever calls on, for a character who is
    never shown doing anything distinct in this specific beat.

    `active` = anyone who speaks (`beat.speakers`), is named as the acting subject of any cut's own action/
    framing/dialogue text, or is named in `opensOn.who`. `background` = present in `cast` but named nowhere
    in this beat's own text. Order preserved within each group. Matches a name's own first word too (so
    "Keen's Mum" matches a cut naming "Mum"). This never changes WHICH cast members get a reference IMAGE
    slot or its @图N number (cb_beats.run uploads one image per `cast` entry in this exact order, unchanged)
    — only how many WORDS Blocks 2/3 spend describing a background member's presence."""
    def _mentioned(name, haystack):
        if not name or not haystack:
            return False
        if name.lower() in haystack:
            return True
        first = name.split("'")[0].strip().lower()
        return bool(first) and first in haystack
    text = " ".join(
        str(c.get("action") or "") + " " + str(c.get("framing") or "") + " " + str(c.get("dialogue") or "")
        for c in (beat.get("cuts") or [])
    ).lower()
    opens_on_who = str((beat.get("opensOn") or {}).get("who") or "").lower()
    speakers = {str(s).lower() for s in (beat.get("speakers") or [])}
    active, background = [], []
    for name in cast:
        if name.lower() in speakers or _mentioned(name, text) or _mentioned(name, opens_on_who):
            active.append(name)
        else:
            background.append(name)
    return active, background

def _v5_references(cast, relay, plate_n, beat):
    """Block 2 — GATE3_ANIMATION_DOCTRINE.md §4a/§4b's reference wording:
      • scene opener: @图1 is this beat's own generated keyframe — "begin on this exact composition" is safe
        here (unlike a relay's harvested frame from a DIFFERENT beat, the actual subject of the historical
        rule-26 anti-hold bug, THIS keyframe was purpose-built as this beat's own first frame).
      • relay: @图1 IS THE FIRST-FRAME-ONLY WORDING (Julian's ruling, 2026-07-07, decision 1 — superseding
        the terser "start from this frame" sentence this docstring described until today). Julian's own
        earlier concern (rule 26's second pass) was that NAMING the reference's provenance — "the final
        frame of the previous shot" — got misread as an instruction about THIS shot's own ending, holding
        the anchor pose for the whole clip. Rather than drop provenance language entirely (the fix tried
        then), this wording keeps it ("the approved final frame of the previous beat") but adds the explicit
        qualifier "matched exactly as the first frame ONLY" plus a direct anti-hold counter-instruction ("Do
        not hold the previous pose, replay the previous action, reset the characters or introduce
        unexplained repositioning") — addressing the SAME risk this module flagged (an S01_B02-style example
        Julian shared was adversarially checked and found likely to reproduce rule 26's bug) with an explicit
        fix rather than by avoidance. `beat.relayOpeningNote` (Layer 2, optional) appends one more
        beat-authored sentence naming who starts where and what breaks first — 1.B2 is the first beat to
        carry one. No @Video1 — retired 2026-07-07, see "THE FIFTH ANCHOR, RETIRED".
      • `beat.spatialAxis` (Layer 2, optional, decision 3) — a fixed blocking law for this beat: who occupies
        which lane/side and the standing "never swap sides" rule, when the director has authored one.
      • ACTIVE cast (named in this beat's own cuts/speakers/opensOn — `_v5_active_cast`): one line each,
        terse name-welded binding ("@图2 Fuzzby — match exactly"), no species/role label (dropped per the
        doctrine's own worked example — even terser than rule 5's prior standard).
      • BACKGROUND cast (present but named nowhere in this beat's own text): ONE consolidated line naming
        every remaining @图N slot, still individually numbered (the image upload order is untouched) but not
        each given their own repeated "match exactly" sentence — the cast-size fix (2026-07-07).
      • the scene plate, UNCONDITIONAL every beat (rule 39 — never relay-only).
      • @Audio1 — the sole vocal/performance source."""
    lines = []
    if relay:
        lines.append(
            "@图1 is the approved final frame of the previous beat and must be matched exactly as the first "
            "frame only. Preserve character design, scale, expressions, continuity marks, lighting and local "
            "geography. Immediately after the first frame, begin the new action. Do not hold the "
            "previous pose, replay the previous action, reset the characters or introduce unexplained "
            "repositioning.")
        opening_note = _strip_spoken_words(str(beat.get("relayOpeningNote") or "").strip())
        if opening_note:
            lines.append(opening_note)
    else:
        lines.append("@图1 opening keyframe — begin on this exact composition.")
    spatial_axis = _strip_spoken_words(str(beat.get("spatialAxis") or "").strip())
    if spatial_axis:
        lines.append(spatial_axis)
    active, background = _v5_active_cast(beat, cast)
    for name in active:
        i = cast.index(name)
        lines.append(f"@图{i + 2} {name} — match exactly.")
    if background:
        tags = ", ".join(f"@图{cast.index(name) + 2} {name}" for name in background)
        lines.append(f"{tags} — background cast, match exactly.")
    if plate_n:
        lines.append(f"@图{plate_n} scene plate — lighting, palette, texture throughout.")
    lines.append("@Audio1 — sole source of all vocal sound; animate mouths and full performance to it.")
    return " ".join(lines)

# THE BUDGET RESOLUTION (Julian's ruling, 2026-07-06 — "the DNA slice from characters.json takes the POSITIVE
# movement sentences only... internal commentary in parentheses is never prompt text"). A sentence is dropped
# when it contains negation AND its topic duplicates a standing negative already covering it — that negation
# stays enforced in the Negative block, where negation lawfully lives, never restated inside a quoted
# character-voice sentence. A sentence with negation that does NOT match a known duplicate topic (e.g.
# Zenny's own "never big or busy gestures" — a genuine behavioural fact, not a standing-negative duplicate)
# survives untouched. Kept in sync with `_standing_negatives()` by construction: every topic below maps to
# one of that list's eleven items.
_DUPLICATE_NEGATIVE_TOPICS = {
    "inflat": "no body inflation",
    "sink": "no floating or sinking through ground", "float": "no floating or sinking through ground",
    "shrink": "no full-body deflation — slumps and dips only",
    "deflat": "no full-body deflation — slumps and dips only",
}
_TOPIC_NEGATION_RE = re.compile(r"\b(no|not|never|don't|doesn't|didn't|won't|isn't|aren't)\b", re.IGNORECASE)
# Parenthetical PRODUCTION/IDENTITY commentary (never movement content) — a narrow, documented stoplist,
# never a blanket "strip all parens" rule: Zenny's own "(a slow blink, a flat stare, a tiny head-tilt)" is
# concrete movement enumeration, not commentary, and must survive untouched.
_META_PAREN_WORDS = re.compile(r"\b(render|worked|confirmed|male|female|bigger|smaller|adult|drone)\b", re.IGNORECASE)

# APPEARANCE-LEAK SENTENCES (Julian's ruling, 2026-07-06 — "everything he does... has to be 100% [him]...
# you instantly know the character because of his persona and the way he acts"): the 9 bears' `mannerisms`
# text is mostly concrete, filmable movement — exactly what makes a beat recognizably THAT character rather
# than a generic cub/bear — but a handful of sentences per character describe appearance/wardrobe/colour
# instead of movement, which Law 5 forbids in a shipped prompt. This is a MECHANICAL exclusion at compile
# time only — the bible text itself is untouched; only Julian's own edit of characters.json can actually
# clean these sentences at the source (rule 44). Listed here, verbatim, so the exclusion is auditable
# against the real field, never a silent trim: any sentence not in this list survives untouched.
_MANNERISMS_APPEARANCE_DROP = {
    "Aida": ["Her robes and headdress move slowly with her — she never rushes."],
    "Sunny": ["The flower-bead collar and the little gold tiara catch the light when she spins."],
    "Luna": ["Lavender wave effects ripple softly outward from her when her calm lands."],
    "Misty": ["Her tall frame folds down small and soft to meet a smaller bear at eye level rather than looming."],
    "Amie": [
        ", the purple-gem pendant catching the light",
        "Her hair-gem and teardrop pendant are her tells: they glint when clarity lands.",
    ],
    "Keen's Mum": [
        "Plump and soft-bodied, a natural lean-in for a hug;",
        "the gold scalloped collar at her throat catches the morning light when she dips her head.",
    ],
    "Squeaky": [
        "rolls to show her pale belly,",
        "Big warm expressive eyes do a lot of the acting.",
        "The aqua shimmer on her skin catches light as she moves.",
    ],
}

_DNA_MANNERISMS_MAX_SENTENCES = 2  # Julian's ruling, 2026-07-06: "doesn't have to be massive... but it has
# to be [him]" — the bible text itself consistently flags each character's ONE standout behavioural marker
# with a naming phrase ("signature gesture," "signature directorial moment," "the courage tell lives in");
# capping by SENTENCE COUNT (not a raw word ceiling) is what keeps that flagged sentence from being cut off
# just because an earlier, more generic sentence used up a fixed word budget first. A word ceiling is kept
# only as a defensive backstop against a single freakishly long sentence.
_DNA_MANNERISMS_WORD_BACKSTOP = 70

def _v5_cap_sentences(text, max_sentences, max_words):
    """Keep the first `max_sentences` whole sentences of `text`, subject to a defensive `max_words`
    backstop — never cuts mid-sentence, never rewrites a surviving word. Always keeps at least the first
    sentence even if it alone exceeds the word backstop."""
    sentences = [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if s.strip()]
    if not sentences:
        return text
    kept, total = [sentences[0]], len(sentences[0].split())
    for s in sentences[1:len(sentences)]:
        if len(kept) >= max_sentences:
            break
        n = len(s.split())
        if total + n > max_words:
            break
        kept.append(s)
        total += n
    return " ".join(kept)

def _v5_strip_appearance_leaks(name, text):
    """Remove this character's known appearance/wardrobe-leak substrings (see
    `_MANNERISMS_APPEARANCE_DROP`) before the text is quoted into a prompt. Substring removal, not sentence
    re-authoring — whatever remains is still an exact, unedited quote."""
    for leak in _MANNERISMS_APPEARANCE_DROP.get(name, []):
        text = text.replace(leak, "")
    return re.sub(r"\s{2,}", " ", text).strip()

def _v5_positive_movement_slice(text):
    """Applies THE BUDGET RESOLUTION filter to one character's raw actingNote/mannerisms text: strips
    meta-commentary parentheticals, then drops any sentence whose negation duplicates a standing negative's
    own topic. Never rewrites a surviving sentence's wording — every kept word is still a verbatim quote."""
    def _strip_paren(m):
        return "" if _META_PAREN_WORDS.search(m.group(1)) else m.group(0)
    text = re.sub(r"\(([^)]*)\)", _strip_paren, str(text or ""))
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.;])\s+", text) if s.strip()]
    kept = []
    for s in sentences:
        if _TOPIC_NEGATION_RE.search(s) and any(topic in s.lower() for topic in _DUPLICATE_NEGATIVE_TOPICS):
            continue
        kept.append(s)
    return " ".join(kept).strip()

def _v5_acting_dna_source(name):
    """THE LEAN ACTING TAG (Julian's ruling, 2026-07-06 — "the director's own language just needs to be put
    into a prompt, which is structured"): superseding the earlier cadence+mannerisms-paragraph combination.
    That combination was built to fight genericness, but comparing this project's own oldest, best-received
    render (2026-06-24) against everything produced since showed the real difference wasn't a thin acting
    tag — it was PROMPT LENGTH: a ~130-word original vs. a 565-681-word current one, with a full per-
    character mannerisms paragraph as one of the biggest single contributors. The shot list itself (Block 4,
    walking the beat's own cuts) is where character truth actually lives now — every action verb in it is
    already drawn from that character's own locked lexicon (THE CHARACTER VOCABULARY LAW). A short register
    TAG here is enough to prime tone without competing with the shot list for the model's attention.

    Returns (text, field_citation): `cadence` alone — every character has one, it is already short (10-20
    words) and already a verbatim quote of the character's own store, THE FIDELITY LAW intact. Falls back to
    a 1-sentence mannerisms slice only if `cadence` is somehow missing (defensive; not expected to fire on
    any of the 11 named cast members today). Returns (None, None) if neither field exists — callers raise
    ManifestFieldMissing."""
    c = _CHARS.get(name) or {}
    cadence = _v5_positive_movement_slice(str(c.get("cadence") or "").strip())
    if cadence:
        return cadence, "cadence"
    mannerisms_raw = str((c.get("bible") or {}).get("mannerisms") or "").strip()
    if mannerisms_raw:
        mannerisms = _v5_positive_movement_slice(_v5_strip_appearance_leaks(name, mannerisms_raw))
        mannerisms = _v5_cap_sentences(mannerisms, 1, _DNA_MANNERISMS_WORD_BACKSTOP)
        if mannerisms:
            return mannerisms, "bible.mannerisms (defensive fallback — no cadence authored)"
    return None, None

def _v5_acting_dna(cast, beat):
    """Block 3 — one line per ACTIVE cast member (`_v5_active_cast` — named in this beat's own cuts/
    speakers/opensOn), VERBATIM (positive-sliced) from the character's own EXISTING store (THE FIDELITY LAW
    + THE BUDGET RESOLUTION) — no separate actingDNA field, no paraphrase, no session ever rewrites the
    surviving words. See `_v5_acting_dna_source` for the actingNote/mannerisms fallback, the positive-slice
    filter, and Fuzzby's named cadence exception. Raises ManifestFieldMissing for an ACTIVE cast member with
    neither field authored — a BACKGROUND cast member (present but doing nothing named in this beat) is
    still manifest-checked at the character level (cb_preflight.check_characters_technical requires the
    field for every character who appears in ANY beat), just not required to compile THIS beat's prompt,
    since nothing here would ever quote it (THE CAST-SIZE FIX, 2026-07-07 — closing the long-open word-
    count ticket: identity for a background cast member is still carried by their own @图N reference image,
    Block 2 — only their individual PERFORMANCE-REGISTER tag is dropped when this beat's own text never
    calls on it)."""
    import cb_qa
    lines = []
    active, _background = _v5_active_cast(beat, cast)
    for name in active:
        text, _field = _v5_acting_dna_source(name)
        if not text:
            raise cb_qa.ManifestFieldMissing("actingNote/mannerisms", f"{name}'s character store — required for every character in this beat's cast")
        if text[-1] not in ".!?":   # the positive-slice filter can drop a trailing parenthetical's own
            text += "."             # closing punctuation (e.g. Fuzzby's cadence clause) — never let two
        lines.append(f"{name}: {text}")   # cast members' lines run together with no sentence boundary
    return " ".join(lines)

def _v5_cut_speaker_note(c, beat):
    """THE DELIVERY LAW (Julian's ruling, 2026-07-07, decision 2 — replacing a bare "X speaks." placeholder
    with speaker plus authored delivery intention, e.g. "Fuzzby performs his vocal beat from @Audio1 with
    earnest, hopeful pomp, presenting the pollen moustache as though it were an official uniform."). Law 6
    stays fully intact — un-reopenable, per CLAUDE.md rules 4/28/29 — `delivery` is ACTING DIRECTION (tone,
    intent, physical performance), never the literal words; `_strip_spoken_words` still runs on it as
    defense in depth, same as every other authored field feeding this block. Falls back to the old bare
    "X speaks." form when a cut has no `delivery` authored yet (not every cut needs one), or when more than
    one character speaks in the same cut (the delivery template is written for one speaker at a time)."""
    import cb_voice as V
    dlg = (c.get("dialogue") or "").strip()
    if not dlg:
        return ""
    names = []
    for label, text in V._cut_segments(dlg):
        if text:
            name = V._resolve_speaker(label, beat)
            if name and name not in names:
                names.append(name)
    if not names:
        return ""
    if len(names) == 1:
        name = names[0]
        delivery = _strip_spoken_words(str(c.get("delivery") or "").strip())
        if delivery:
            poss = _v5_possessive(name)
            return f" {name} performs {poss} vocal beat from @Audio1 {delivery}."
        return f" {name} speaks."
    return f" {' then '.join(names)} speaks."

def _v5_shot_time_ranges(n_shots):
    """THE SHOT-TIMING LAW (Julian's ruling, 2026-07-08, reviewing 1.B2 — "four shots in 15 seconds need
    time ranges, otherwise Seedance may spend too long on the flower entry and rush or omit the wipe"):
    a mechanical, deterministic per-shot time budget across the beat's full HANDLE_TOTAL seconds — cumulative
    division with Python's own round() (round-half-to-even), no per-cut authored weight needed, so N shots
    partition the beat with no drift and nothing invented. Verified against Julian's own hand-computed
    worked example (4 shots / 15s total -> 0-4, 4-8, 8-11, 11-15) — this function reproduces those exact
    boundaries. This revives, mechanically, what the v4 template's "Timing: 0-Ns...; N-Ms..." clock (rule 30)
    used to do via the now-deleted `_v3_shots` — lost when the shot list was restored to full per-cut detail
    (rule 45) without carrying the per-shot time budget along with it."""
    bounds = [0] + [round(i * HANDLE_TOTAL / n_shots) for i in range(1, n_shots + 1)]
    return list(zip(bounds[:-1], bounds[1:]))

def _v5_beat_story(beat, cast):
    """Block 4 — THE SHOT LIST (Julian's ruling, 2026-07-06, live footage review of 1.B1 — "where's the
    action... the cut saying what camera it is, what he's doing... where's the story beat?"): walks the
    beat's own authored `cuts[]`, one shot per cut — camera framing + the cut's specific action + who
    speaks (never the words, Law 6) — ending on endState's living settle. Supersedes the prior flattened
    approach (the beat's own `storyBeat` summary sentence, capped at 80 words), which was found live to
    silently drop every cut's camera and named staging (e.g. 1.B1's "zig-zag ladder: left petal pass,
    right stem dodge, low grass skim" and the leaf-FWIP-rebound), leaving Seedance nothing concrete to
    act on beyond one generic sentence. The doctrine's own §2 80-word fence on this block is RETIRED by
    this same ruling — a real per-cut shot list cannot fit three cameras + three actions in 80 words, and
    the true backstop is (and was always) the whole-prompt 400-word hard cap (cb_preflight.py), which
    stays in force. Speed adjectives mechanically stripped from both framing and action (rule 33's
    adjective-chaos ban); spoken words stripped from BOTH (a cut's own `framing` field has been found to
    quote its dialogue inline — e.g. 1.B1 cut 2's framing names 'Nailed it.' landing on the locked frame —
    so Law 6 stripping applies to framing exactly as it does to action). Raises ManifestFieldMissing when
    a beat has no cuts, or no endState — never invented.

    PAGINATION (Julian's ruling, 2026-07-06 — "paginate it... push shot one as its own paragraph... easy to
    read for anybody receiving it"): each shot is its OWN line-group, never run together with the next.
    Joined with a single "\\n" (not the outer block-separator "\\n\\n") so this stays exactly one block
    relative to the rest of the prompt's "\\n\\n".join(parts) structure — cb_qa.check_gate3_lint's
    block-index logic (acting_idx/story_idx) counts blocks by splitting on "\\n\\n" and would misalign if
    this block's own internal separator collided with that outer one.

    THE SHOT-TIMING LAW, SAME RULE (2026-07-08): each shot is now two lines — "{start}–{end}s — {framing}:"
    then the action/speaker-note line — replacing the old single-line "Shot N (framing): action." form.
    "Shot N" numbering is DROPPED, not kept alongside the time range (the same "already the number, don't
    double-count" logic rule 45 applied to the old numeral now applies to the time range instead — it IS
    the shot's own identifier). Time ranges cost almost nothing against the word budget (`_v5_word_count`
    only counts alphabetic runs; digits and the en dash contribute nothing)."""
    import cb_qa
    cuts = beat.get("cuts") or []
    if not cuts:
        raise cb_qa.ManifestFieldMissing("cuts", "this beat's own shot list — required for the v5 shot-list block")
    settle = str(beat.get("endState") or "").strip()
    if not settle:
        raise cb_qa.ManifestFieldMissing("endState", "this beat's own settle text — required for the v5 shot-list block")
    lines = []
    ranges = _v5_shot_time_ranges(len(cuts))
    for (start, end), c in zip(ranges, cuts):
        framing = _v5_strip_speed_adjectives(_strip_spoken_words(str(c.get("framing") or "").strip()))
        action = _v5_strip_speed_adjectives(_strip_spoken_words(str(c.get("action") or "").strip()))
        speaker_note = _v5_cut_speaker_note(c, beat)
        body = ". ".join(p for p in (action.rstrip("."), ) if p) + "." if action else ""
        header = f"{start}–{end}s — {framing}:" if framing else f"{start}–{end}s:"
        lines.append(header)
        lines.append(f"{body}{speaker_note}".strip())
    settle = _v5_strip_speed_adjectives(_strip_spoken_words(settle))
    lines.append("Settle:")
    lines.append(settle)
    return "\n".join(lines)

def _v5_header():
    """HEADER — RETIRED the standalone tech-line CLOSER entirely (Julian's ruling, 2026-07-08, reviewing the
    556-word 1.B2 compile: "This is the version I would run" — his own rewrite folds "24fps" into the header
    and drops "smooth cinematic motion, shallow depth of field" outright). This independently confirms a
    finding this same session's own tooling already made: `cb_qa.ANTI_SLOP_WORDS` (rule 50, 2026-07-07) flags
    that exact phrase as generic AI-video filler on every single beat ("a hit in the style law or tech line
    names a LOCKED constant only Julian's own edit can amend" — his edit is that amendment). "16:9" was
    already deduped here once (rule 52, decision 5); this is the same duplication-removal instinct taken one
    step further — a fixed format spec (duration/aspect/fps) belongs in ONE line, once, not split across a
    HEADER and a separate CLOSER paragraph that adds no real protection beyond restating format."""
    return f"{HANDLE_TOTAL}s, 16:9, 24fps, 3D CGI beat."

_NEGATION_LEAD_RE = re.compile(r"^(no|not|never|don't|doesn't|didn't)\b", re.IGNORECASE)

def _v5_negative_line(beat):
    """The Negative line — the ONLY negation anywhere in the prompt (doctrine §2/§4): the eleven standing
    items plus the beat's own stagingProhibited, merged, terse. `bible.dos`/`bible.donts` do NOT feed this —
    §3's own "Never in a prompt" list names them explicitly ("writer-room guidance... live at Gate 1 as
    review criteria"), reversing the immediately-prior ruling that had them feed per-beat staging/negatives.

    "no " PREFIX ON STAGING ITEMS (2026-07-08, Julian's ruling reviewing 1.B2 — his own worked example
    prefixed every gag-specific item with "No", matching the standing items' own convention): a beat's own
    `stagingProhibited` phrase (authored as a bare noun phrase, e.g. "Fuzzby disappearing into the flower")
    is mechanically prefixed with "no " if it doesn't already start with a negation word — a formatting
    normalisation only, never a content change, so every item in the line reads with the same "no X" cadence
    instead of the standing items alone carrying it."""
    staging = [str(x).strip() for x in (beat.get("stagingProhibited") or []) if str(x).strip()]
    staging = [s if _NEGATION_LEAD_RE.match(s) else f"no {s}" for s in staging]
    negatives = staging + _standing_negatives()
    return "Negative: " + "; ".join(negatives) + "."

def emit_v5(beat, scene, cast, relay):
    """THE V5 ENGINE — the permanent prompt compiler under GATE3_ANIMATION_DOCTRINE.md (the Version of
    Record, 2026-07-06; LEANED 2026-07-06 SAME DAY, "the director's own language just needs to be put into
    a prompt, which is structured"). HEADER + style + references + acting tag + shot list + Negative (the
    standalone tech-line CLOSER retired 2026-07-08 — fps folded into HEADER). Returns the compiled plain-text
    prompt; the CALLER prints the total word count (`_v5_word_count`).

    THE CAMERA+AMBIENCE PARAGRAPH IS RETIRED (found and removed the same day it caused a real bug): it
    stated a whole-beat generic camera sentence that duplicated (and once literally contradicted, Law 8)
    the shot list's own per-cut camera direction, and repeated the scene's constant `ambientBed` text
    verbatim into EVERY beat — including beats set before the ambient event that line described actually
    happens (confirmed live: 1.B1's shipped prompt described "the distant thunder rumble arrives," and
    Seedance rendered thunder into the episode's very first beat, before the storm that line belongs to
    ever arrives in the story). Ambience continuity is a Post/stitch concern (GATE3_ANIMATION_DOCTRINE.md's
    own Stage 7), not something that needs restating as text in every beat's own generation prompt. A
    missing required field (actingNote/mannerisms, storyBeat, endState) raises cb_qa.ManifestFieldMissing,
    uncaught here — the caller's own manifest-aware except block turns that into a named refusal instead of
    a silent degrade."""
    # THE PLATE IS A STANDING ANCHOR, NOT A RELAY-ONLY ONE (rule 39): unconditional, opener beats included.
    plate_n = len(cast) + 2
    # BLOCK 1 — style law + optional scene-look sentence (Julian's ruling, 2026-07-07, decision 4): joined
    # with a space, NOT a new "\n\n" block, so cb_qa.check_gate3_lint's block-index model stays unchanged.
    style_block = _style()
    scene_look = _v5_scene_look(scene)
    if scene_look:
        style_block = style_block + " " + scene_look
    parts = [
        _v5_header(),
        style_block,
        _v5_references(cast, relay, plate_n, beat),
        _v5_acting_dna(cast, beat),
        _v5_beat_story(beat, cast),
        _v5_negative_line(beat),
    ]
    return "\n\n".join(parts)

def for_beat_v5(beat, scene=None, relay=False):
    cast = beat.get("openingCast") or beat.get("characters") or []
    if not (beat.get("cuts") or []):
        return "", "v5 (empty — no cuts)"
    return emit_v5(beat, scene, cast, relay), "v5"

def shipped_prompt(beat, scene=None, relay=False, prev_end_state_still=None, prev_carry_marks=None):
    """Returns (prompt, builder_label, is_definitive). v5 is the SOLE prompt author — every fallback escape
    hatch is deleted, not merely deprecated. An empty v5 result is NOT degraded to a weaker builder; it
    surfaces as an empty prompt, exactly like any other missing-data condition, for the caller's own
    empty-prompt handling (e.g. cb_beats.run's "empty Seedance prompt — skipping") to catch. is_definitive is
    always True — kept in the return signature for call-site compatibility across cb_beats/cb_seedance/
    cb_golden/cb_replicator, none of which need to change their unpacking.
    prev_end_state_still / prev_carry_marks: accepted for call-signature compatibility with every existing
    caller (cb_beats.run, gate3_dryrun, fire_next_beat all pass them) but UNUSED — GATE3_ANIMATION_DOCTRINE.md
    §4b's relay @图1 line is a FIXED sentence, never mad-libbed with the specific carry-mark text (that
    specificity is a Step 6 QA concern, cb_qa.check_join_state, reading the beat's own carryMarks field
    directly — never a prompt-text concern). A missing required field raises cb_qa.ManifestFieldMissing,
    uncaught here — the caller's own manifest-aware except block (rule 37) turns that into a named refusal
    instead of a silent degrade."""
    v5, emitter5 = for_beat_v5(beat, scene, relay=relay)
    return v5, f"cb_segprompt_v5 ({emitter5})", True

if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
    code = sys.argv[2] if len(sys.argv) > 2 else "1.B1"
    d = json.load(open(pkg))
    all_beats = d.get("beats") or d.get("shots") or []
    beat = next(b for b in all_beats if (b.get("beatCode") or b.get("shotCode")) == code)
    scene = next((s for s in d.get("scenes") or [] if str(s.get("sceneNumber")) == str(beat.get("sceneNumber"))), None)
    # THE BASELINE-PROOF RELAY FIX (found in the 2026-07-08 software-wide sign-off audit): this CLI is the
    # exact command CLAUDE.md names as the "Baseline proof" — the documented, standard way to inspect any
    # beat's real shipped prompt. It used to call shipped_prompt(beat, scene) with relay defaulted to False,
    # never computed from the beat's actual predecessor state the way cb_beats.run/gate3_dryrun/fire_next_beat
    # all correctly do via cb_scene.relay_source_for — meaning the one command this project's own doctrine
    # tells everyone to run silently showed the WRONG (opener) branch for any beat whose predecessor already
    # has a signed clip, with no warning. Fixed to compute relay status the same way the real fire path does.
    import cb_scene
    scene_beats = [b for b in all_beats if str(b.get("sceneNumber")) == str(beat.get("sceneNumber"))]
    _, _relay_status, _ = cb_scene.relay_source_for(scene_beats, code, "Ep1")
    relay = _relay_status == "relay"
    prompt, _builder, _is_definitive = shipped_prompt(beat, scene, relay=relay)
    wc = _v5_word_count(prompt)
    import cb_preflight as _PF
    print(f"===== GATE-3 SEEDANCE PROMPT — {code}  (relay={relay}, {len(prompt)} chars, {wc} words — target "
          f"{_PF.WORD_BUDGET_TARGET}, hard block {_PF.WORD_BUDGET_BLOCK}) =====\n")
    print(prompt)
