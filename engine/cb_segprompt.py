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
  BLOCK 3  ACTING DNA — one line per ACTIVE cast member (same split as Block 2), VERBATIM from `cadence`
           (FIXED 2026-07-12, full-codebase audit continued: this used to say `actingNote` — stale since
           the lean-acting-tag ruling, 2026-07-06, which superseded the older actingNote/mannerisms-paragraph
           combination with `cadence` alone, every character has one — see `_v5_acting_dna_source`'s own,
           already-correct docstring, which this line simply never caught up to) or falling back to a
           1-sentence `bible.mannerisms` slice only if cadence is somehow missing (defensive; not expected to
           fire on any of the 11 named cast members today — FLAGGED, not silently accepted, when it does:
           some bears' mannerisms mix in appearance detail rule 5 forbids; Julian's own bible is the only
           editor of that content, this function just reports the field it drew from). A BACKGROUND cast
           member gets NO Acting DNA line at all — priming a performance register nothing in the shot list
           ever calls on was the actual bloat; their identity is still fully carried by their own reference
           image in Block 2.
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
           the ONLY negation anywhere in the prompt: twelve standing items (doctrine §2, a twelfth added
           2026-07-13 against a real hallucinated-background-audio failure) plus the beat's own
           stagingProhibited, merged, terse.

RETIRED this same doctrine (found on read, not previously true): character `bible.dos`/`bible.donts` no
longer feed the prompt at all — §3's own "Never in a prompt" list names them explicitly ("writer-room
guidance (dos/donts live at Gate 1 as review criteria)"), reversing the immediately-prior ruling that had
them feed per-beat staging/negatives. `_v5_character_staging`/`_v5_character_negatives` are deleted.

Word budget: 400 is the TARGET (not enforced here); 850 is a HARD BLOCK, enforced in cb_preflight.py
(cb_preflight.WORD_BUDGET_TARGET/WORD_BUDGET_BLOCK — raised 2026-07-07, rule 52, from 250/400 to 400/650;
raised 2026-07-14, rule 84/85, to 400/700 for the Keane expression-line addition; raised again 2026-07-15
after removing the field-local caps that addition (and the physics anchor) had been quietly truncated by —
see `_v5_expression_line`/`_v5_physics_anchor`, both now ship their source content in full). The
BEAT STORY block's own 80-word sub-fence is RETIRED (2026-07-06, the shot-list ruling above) — a real
per-cut shot list cannot fit multiple cameras + actions in 80 words, and the whole-prompt 400-word cap was
always the real backstop. Every emit prints its own total word count at the call site (this module's own
__main__, cb_beats.run's per-beat log line, cb_beats.gate3_dryrun's returned dict) via `_v5_word_count`.

TWO CONTRADICTIONS FOUND ON READ, FLAGGED (CLAUDE.md rule 43), NOT SILENTLY RESOLVED:
  1. §3's table names the Acting DNA source as `shows/crystal-bears/bible/` — a folder confirmed NOT to
     exist — directly conflicting with Julian's own immediately-prior ruling that characters.json IS the
     character store. Defaulted to characters.json (`actingNote`/`bible.mannerisms`, as it stood the day
     this note was written) — tested, working, and literally what he pointed at one message earlier.
     HISTORICAL NOTE (2026-07-12, full-codebase audit continued): the same-day lean-acting-tag ruling
     (2026-07-06) superseded `actingNote` with `cadence` as the primary source (see `_v5_acting_dna_source`
     and Block 3's own note above) — this paragraph is left as the dated record of the read-time decision,
     not rewritten, matching this codebase's own established practice for a superseded entry.
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

def _load_chars():
    # FIXED 2026-07-12 (loose-ends pass): was a hand-rolled `os.path.join(..., "config", "characters.json")`
    # — resolves through the engine/config -> shows/crystal-bears/canon symlink, byte-identical to P.CHARS,
    # but a duplicate path-building formula this module doesn't need since it already imports paths as P.
    try:
        d = json.load(open(P.CHARS)); return d.get("characters", d)
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
# HANDLE_ACTION (= HANDLE_TOTAL - HANDLE_SETTLE) removed 2026-07-08 audit — confirmed zero live callers anywhere
# in engine/ outside this file's own now-deleted definition; the 13s action budget is derived directly from
# HANDLE_TOTAL/HANDLE_SETTLE wherever it's actually needed (e.g. _v5_shot_time_ranges), never read as its own
# named constant.

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
    """THE TWELVE STANDING NEGATIVES (GATE3_ANIMATION_DOCTRINE.md §2, 2026-07-06; the eleventh added by
    Julian's BUDGET RESOLUTION ruling, same day; the TWELFTH added 2026-07-13, diagnosing 1.B3's real
    rendered failure) — always exactly twelve, no longer species-conditional (the doctrine's own list states
    them unconditionally, cast composition notwithstanding — "no crystals on or attached to the bees"
    appears even in an all-bear scene). THE ELEVENTH ITEM is where negation about a character's own
    deflate/slump/dip behaviour now lives — previously stated as prose inside a character's own Acting DNA
    quote (Fuzzby's actingNote: "Any deflate that follows is a small slump or a dip, never the whole body
    shrinking"), which is now filtered OUT of the prompt-facing DNA slice (`_v5_positive_movement_slice`)
    specifically because this standing item covers it — negation belongs in the Negative block, not restated
    inside a quoted character-voice sentence.

    THE TWELFTH ITEM (2026-07-13, real footage diagnosis — 1.B3's rendered clip carried audible background
    foreign-language chatter despite the existing "no foreign-language speech" item): mined from the
    seedance-20 skill's own reference doctrine (`references/migrated/seedance-audio-original.md`'s "Known
    Failure Modes" §1) — Seedance's native audio engine treats an uploaded @Audio1 track as "a reference
    signal, not a playback instruction" and can still generate its OWN background audio on top of it,
    especially when the prompt itself names ambient/SFX/music concepts (this module's own tech line and
    style law do exactly that). "no foreign-language speech" only bans the PRIMARY vocal performance
    reading as foreign — it says nothing about invented BACKGROUND voices/chatter/murmur riding underneath
    the real @Audio1 track, which is the failure actually observed. Paired with a new positive-preservation
    sentence next to @Audio1 itself (`_v5_references`, "No other voices generated") — the doctrine's own
    finding is that explicit preservation instructions are more reliable than a negative alone.

    TERSENED (Julian, 2026-07-06, same ruling as the lean acting tag): the OLD best-received render's own
    negative line was a single terse clause ("--no text, watermarks, logos"). Every one of the original
    eleven protections below is KEPT — nothing here is dropped, this is wording only, matching that old
    economy: short noun phrases, not full sentences.

    THE TENTH ITEM, NARROWED (2026-07-14, Julian: "can we not just look at what is just being said" — caught
    by a plain read of the real compiled 1.B1 prompt, independently confirmed by a code audit): item 10 sat
    unqualified ("no body inflation") while item 11, right next to it, was ALREADY narrowed to
    "(slumps/dips only)" specifically so it wouldn't ban a character's own directed deflate behaviour. The
    same treatment was never applied to inflation — meaning every beat's own PHYSICS line demanding
    "exaggerated squash-and-stretch" (LEAF_CRASH_REBOUND and every other archetype using that phrase) shipped
    in the SAME prompt as an unqualified ban on the very body-shape deformation squash-and-stretch requires.
    Narrowed to mirror item 11's own precedent exactly."""
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
        "no body inflation (temporary impact squash-and-stretch only)",
        "no full-body deflation (slumps/dips only)",
        "no invented background voices",
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
    700 as of 2026-07-14 rule 84/85; WORD_BUDGET_TARGET, 400, is the target, not gated here — an emitter
    compiles what the data says, it never self-censors)."""
    return len(_V5_WORD_RE.findall(str(text or "")))

_SPEED_ADJ_RE = re.compile(
    r"(?<!too )(?<!at full )(?<!and )\b(?:high-speed|fast(?:er|est)?|quick(?:ly|er|est)?|rapid(?:ly)?|hyper|manic(?:ally)?|frantic(?:ally)?|"
    r"chaotic(?:ally)?|wild(?:ly)?|erratic(?:ally)?|hasty|hastily|speedy|speedily|zooming|zooms|zoomed)\b"
    r"(?!\s+than\b)(?!\s+and\s+\S+\s*(?:[,.;:]|$))",
    re.IGNORECASE)
# FIXED 2026-07-13 (found writing physics-forward causal prose per the seedance-motion doctrine, same night):
# `speed(?:y|ily)?` matched a bare "speed" via its own optional suffix — but bare "speed" is almost always a
# NOUN in English ("his own speed bends every stem"), not the vague pace-ADJECTIVE this stripper exists to
# ban (rule 33's adjective-chaos ban). Stripping it left "Fuzzby's own bends every stem he passes" — a
# subjectless, broken clause, the exact bug class rules 71-73 spent a whole night hunting, reproduced live
# in a fresh rewrite written specifically to fix a "clunky, fake" motion complaint. "speedy"/"speedily" (the
# real adjective/adverb forms) are still caught; the bare noun now survives, since a physics-forward sentence
# naming an object's own speed as the CAUSE of a visible consequence is exactly the specific, concrete
# language the seedance-motion doctrine asks for, not adjective-chaos.

def _v5_strip_speed_adjectives(text):
    """Block 4's mechanical transform (Julian, 2026-07-06 — "speed adjectives stripped"), applying rule 33's
    adjective-chaos ban ("a generic frenzy word with no physical beat behind it... is BANNED as unreadable")
    as a real edit rather than just a lint: a generic pace word spends a word of the budget saying nothing a
    video model can act on, when the beat's own named actions (already in storyBeat/endState) do the actual
    work. Collapses the resulting double-spaces/orphaned punctuation-spacing.

    FIXED 2026-07-13 (creativity-vs-rules audit — confirmed live in 6+ beats of the shipping package,
    e.g. real beat 5.B3's actual compiled shot list once read "Fuzzby rockets toward the beach at full and
    immediately flies into the branch"): a single strip broke grammar whenever the matched word was the head
    of a comparative ("faster than X" -> "than X" with nothing to compare) or the object of a fixed
    intensifying preposition phrase ("at full speed" -> "at full" with nothing left to modify) — not just
    when two matches collided adjacently (the earlier-fixed, narrower bug). `_SPEED_ADJ_RE` now excludes a
    match immediately preceded by "too "/"at full " or immediately followed by " than" — these constructions
    carry real comparative meaning worth keeping, not generic filler, so leaving them untouched is also the
    more creatively faithful choice, matching the audit's own recommendation.

    FIXED AGAIN, SAME NIGHT, FOUND WHILE VERIFYING 1.B1 WAS SAFE TO RE-FIRE: a third variant of the identical
    bug — real, currently-signed beat 1.B1's own authored action text ("wingbeats rapid and continuous")
    compiled to the dangling "wingbeats and continuous" once "rapid" was stripped, leaving the coordinating
    "and" with nothing on its left to join. Not the already-guarded two-adjacent-strippable-words case
    (`cb_qa.check_gate3_lint`'s own adjacent-strip BLOCK — "continuous" isn't itself a speed word, so that
    lint never saw this one). `_SPEED_ADJ_RE` now also excludes a match immediately followed by " and " plus
    exactly one more word before the next clause boundary (comma/semicolon/period/end) — the shape of a
    coordinated modifier pair, not a new independent clause (compare "flies fast and lands hard." — "and"
    is followed by two words forming its own verb phrase, so "fast" still correctly strips there)."""
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
        # FIXED 2026-07-13 (creativity-vs-rules audit — the same bug as the possessive-tail fix just below,
        # confirmed live: with cast=['Bo', 'Aida'], the text "Aida crosses the room, opening the box." wrongly
        # marked Bo as ACTIVE purely because "box" contains the substring "bo"). Plain-name matching was a
        # bare substring test with no word boundary — real risk for any short name (Bo, Amie's "Am" root,
        # etc.), not just the possessive-tail case. Now a real word-boundary match, same discipline as below.
        if re.search(r"(?<![a-z])" + re.escape(name.lower()) + r"(?![a-z])", haystack):
            return True
        # A possessive name ("Keen's Mum") is also matched by its own distinguishing common-noun word — the
        # part AFTER the possessive apostrophe ("Mum") — never the part BEFORE it ("Keen", a DIFFERENT
        # character). The old `name.split("'")[0]` took the wrong side: a cut naming Keen (not his mother)
        # wrongly marked her active, and a cut naming "Mum" without "Keen" wrongly marked her background —
        # the exact opposite of what this docstring's own worked example claims (2026-07-08 audit finding).
        # FIXED 2026-07-13 (creativity-vs-rules audit): the tail check used to be a bare substring test with
        # no word boundary, so any word CONTAINING "mum" (e.g. "chrysanthemum," and real, already-shipping
        # production prose like "maximum") would false-positive-match "Keen's Mum" into a scene she has
        # nothing to do with. Now a real word-boundary match.
        if "'" in name:
            tail = name.split("'", 1)[1].lstrip("sS").strip().lower()
            if tail and re.search(r"(?<![a-z])" + re.escape(tail) + r"(?![a-z])", haystack):
                return True
        return False
    text = " ".join(
        str(c.get("action") or "") + " " + str(c.get("framing") or "") + " " + str(c.get("dialogue") or "")
        for c in (beat.get("cuts") or [])
    ).lower()
    opens_on_who = str((beat.get("opensOn") or {}).get("who") or "").lower()
    speakers = {str(s).lower() for s in (beat.get("speakers") or [])}
    forced_active, forced_background = _v5_fidelity_split(beat, cast)
    active, background = [], []
    for name in cast:
        # FIXED 2026-07-13 (creativity-vs-rules audit): the director's own authored fidelityAllocation
        # (rule 50) is a stronger, deliberate signal than an incidental text mention — confirmed live on
        # 6.B4, where Fuzzby/Zenny were explicitly marked `economized` (deliberately de-emphasized) but
        # still shipped full Acting DNA because blocking text happened to name them, while the beat's own
        # designated `secondary` performer (Howey, never individually named in the prose) got nothing —
        # the exact reverse of the beat's own recorded creative intent. `economized` now forces background
        # even when textually mentioned; `primary`/`secondary` now force active even when the prose never
        # names them by name (e.g. only referred to as "the bears").
        if name in forced_background and name not in forced_active:
            background.append(name)
        elif name in forced_active or name.lower() in speakers or _mentioned(name, text) or _mentioned(name, opens_on_who):
            active.append(name)
        else:
            background.append(name)
    return active, background

def _v5_fidelity_split(beat, cast):
    """Parses the beat's own authored `fidelityAllocation` (cb_director_schemas.FidelityAllocation —
    primary/secondary/economized, rule 50) into (forced_active, forced_background) name sets, mirroring
    cb_craft._economized_set's own comma-separated parsing exactly so the two modules never drift apart on
    what "economized" means. Returns empty sets for a beat with no fidelityAllocation authored yet (older/
    unmigrated data) — callers fall back to the pre-existing text-mention heuristic unchanged, so this is
    additive, never a regression."""
    fa = beat.get("fidelityAllocation") or {}
    lower_cast = {c.lower(): c for c in cast}
    forced_active = set()
    for key in ("primary", "secondary"):
        name = lower_cast.get(str(fa.get(key) or "").strip().lower())
        if name:
            forced_active.add(name)
    forced_background = set()
    raw_econ = str(fa.get("economized") or "").strip()
    if raw_econ and raw_econ.lower() != "none":
        for part in raw_econ.split(","):
            name = lower_cast.get(part.strip().lower())
            if name:
                forced_background.add(name)
    return forced_active, forced_background

def _v5_size_clause(cast):
    """SIZE CONTINUITY (found missing 2026-07-13 via a director-fidelity trace investigating why 1.B1's real
    rendered clip shows Zenny growing to match/exceed Fuzzby's size by the clip's end): relative size is
    authored explicitly and redundantly at every upstream stage — characters.json's own sizeRank/size fields,
    each character's `cadence` field's trailing "(bigger, male)"/"(smaller, female)" parenthetical, and the
    Director's Pass's own camera direction ("Fuzzby larger frame-LEFT... Zenny smaller frame-RIGHT") — but it
    never reached the shipped prompt. The one place it could have ridden through automatically, the
    cadence-derived Acting DNA quote, has that parenthetical mechanically stripped by `_META_PAREN_WORDS`
    (built for genuine meta-production commentary like "the render that first worked," which also happens to
    list "bigger"/"smaller"/"male"/"female" — stripping a real character fact along with it). Mirrors
    `cb_prompts.size_line`'s own established wording for keyframes exactly ("X is the BIGGER bee, Y the
    SMALLER") — a relative-size instruction is staging/blocking, the same category as stating screen-left/
    screen-right position, not the appearance description rule 5 forbids (which governs HOW a character
    looks — glasses, colour, markings — never WHERE they sit in scale next to a co-star). This is that same,
    already-precedented mechanism's video-prompt sibling, which never existed here before."""
    ranked = sorted(
        [(name, _CHARS[name]["sizeRank"]) for name in cast if name in _CHARS and _CHARS[name].get("sizeRank")],
        key=lambda x: -x[1],
    )
    if len({r for _, r in ranked}) < 2:
        return ""
    if len(ranked) == 2:
        bigger, smaller = ranked[0][0], ranked[1][0]
        return (f"SIZE: {bigger} renders visibly larger than {smaller} in every shared frame — hold this "
                f"scale relationship throughout, never flattened or reversed.")
    # THE TIE FIX (2026-07-14, found the same "just look at what is being said" pass — Aida and Keen's Mum
    # both carry sizeRank 5 in real canon; the old code emitted a bare " > ".join(...) that asserted a strict
    # ordering the underlying data doesn't support, a false size claim for any beat naming both). Groups by
    # actual rank value first — same rank renders as "X and Y" (tied), distinct ranks still join with ">".
    groups, seen_ranks = [], []
    for name, rank in ranked:
        if seen_ranks and seen_ranks[-1] == rank:
            groups[-1].append(name)
        else:
            groups.append([name])
            seen_ranks.append(rank)
    order = " > ".join(" and ".join(g) for g in groups)
    return f"SIZE: relative scale, largest to smallest — {order}. Hold this ordering throughout (tied names render the same size), never flattened or reversed."

def _v5_has_vocal_content(beat):
    """FIXED 2026-07-12 (full-codebase audit continued): `_v5_references` used to append the "@Audio1 —
    sole source of all vocal sound..." line UNCONDITIONALLY, even for a beat with zero speakers and zero
    cut dialogue — confirmed live against the real production package's 7.B3 (wordlessHeld, speakers=[],
    every cut's dialogue=None), whose shipped prompt still told the model to "animate mouths and full
    performance to" an @Audio1 track that cb_beats.run never uploads for it (cb_voice.build_dialogue_track
    returns None for a wordlessHeld beat — "silence carries it, never a voice," rule 9 — so cb_gen never
    receives an audio_urls entry to attach as @Audio1 at all). This mirrors that same gate here so the
    reference stack the prompt describes matches what actually gets uploaded.

    Defensively normalizes `wordlessHeld` rather than trusting Python's native truthiness on it: the real
    package was found, live, to carry `"wordlessHeld": "false"` as a JSON STRING (not the boolean `false`)
    on 1.B1/1.B2 — both real, already-signed beats with real dialogue — and `bool("false")` is `True` in
    Python, so a naive `if beat.get("wordlessHeld"):` would have wrongly treated both as wordless and
    silently dropped their @Audio1 line, a regression on already-approved production beats. That data-level
    string/bool inconsistency is a separate bug (in the beat package / whatever wrote it) outside this
    module's own scope — flagged, not fixed here. A beat counts as vocal if it isn't declared wordless AND
    either names speakers or any cut carries non-blank dialogue text."""
    wordless = beat.get("wordlessHeld")
    if isinstance(wordless, str):
        wordless = wordless.strip().lower() not in ("", "false", "0", "no", "none")
    if bool(wordless):
        return False
    if beat.get("speakers"):
        return True
    return any(str(c.get("dialogue") or "").strip() for c in (beat.get("cuts") or []))

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
      • FIRST-FRAME-ONLY CONTINUITY, NOT A GEOGRAPHY CONSTRAINT (Julian's ruling, 2026-07-13, diagnosing
        1.B3's real rendered failure — "the stay in space is the first frame then it can go anywhere as its
        the continuity holder not the direction"): the preserve-list used to include "local geography"
        alongside character design/scale/expressions/marks/lighting, stated as an ongoing preservation
        claim rather than scoped to the first frame only. Real footage showed the consequence directly — a
        beat whose own story required travel (dive to a new flower, clip a different branch, tumble, land
        elsewhere) instead looped back to the SAME branch composition it opened on, because the reference
        image was the one thing the model had strong, unambiguous grounding for and the geography clause
        gave it permission to keep returning to it. FIXED: "local geography" is dropped from the
        preserve-list outright (matching the first frame exactly already covers where things are AT THAT
        INSTANT — nothing more needs to say so twice) and a new sentence states the shot is explicitly free
        to travel after that first frame. @图1's job is being the continuity HOLDER for the pickup moment,
        never a director for where the shot goes next — that's what the action text and camera direction
        are for.
      • `beat.spatialAxis` (Layer 2, optional, decision 3) — a fixed blocking law for this beat: who occupies
        which lane/side and the standing "never swap sides" rule, when the director has authored one.
      • ACTIVE cast (named in this beat's own cuts/speakers/opensOn — `_v5_active_cast`): one line each,
        terse name-welded binding ("@图2 Fuzzby — match exactly"), no species/role label (dropped per the
        doctrine's own worked example — even terser than rule 5's prior standard).
      • BACKGROUND cast (present but named nowhere in this beat's own text): ONE consolidated line naming
        every remaining @图N slot, still individually numbered (the image upload order is untouched) but not
        each given their own repeated "match exactly" sentence — the cast-size fix (2026-07-07).
      • the scene plate, UNCONDITIONAL every beat (rule 39 — never relay-only).
      • REFERENCE PRIORITY (added 2026-07-13, external-review verification — CLAUDE.md rule 73's own
        follow-up session), RELAY ONLY: a relay beat's own @图1 clause asks the model to carry forward
        "lighting," which genuinely overlaps the plate's declared job — an opener's @图1 line makes no such
        claim, so there is nothing to arbitrate there and the sentence is correctly omitted. First attempt
        was a general 3-way priority sentence on every beat (~13-22 words); it pushed real beat 1.B2 over
        the 650-word hard cap (655-664 words measured), so it was narrowed to the ~9-word sentence that
        names the ONE actually-diagnosed overlap (lighting) rather than a hypothetical general scheme —
        matching this file's own lean-prompt doctrine (rule 42) and this session's own established
        discipline (rule 73) of fixing the diagnosed problem precisely, not the maximal version an external
        review proposed (a multi-paragraph "REFERENCE AUTHORITY" block), which would reverse rule 42's own
        tested, documented reasoning.
      • @图1's own preserve-list DROPPED "local geography" entirely (2026-07-13, real footage diagnosis on
        1.B3 — see the FIRST-FRAME-ONLY CONTINUITY note below). It never claimed geography as an ongoing
        priority anyway; the fix is at the source.
      • @Audio1 — the sole vocal/performance source, appended ONLY when the beat actually has one
        (`_v5_has_vocal_content` — FIXED 2026-07-12, full-codebase audit continued: this used to be
        unconditional, directing the model to lip-sync against an @Audio1 track that a genuinely wordless
        beat, e.g. 7.B3, never actually gets uploaded). A wordless beat gets a neutral held-silence line
        instead, naming no reference number that was never sent. ADDED 2026-07-13 ("No other voices
        generated."): a real rendered take (1.B3) came back with audible hallucinated background
        foreign-language chatter — Seedance's own audio engine can generate additional voices on top of the
        real @Audio1 reference (seedance-20 skill's audio-guide.md/model-mechanics.md — an audio reference is
        "a signal, not a playback instruction"). Paired with the new twelfth standing negative
        (`_standing_negatives`) — the doctrine's own finding is that an explicit positive-preservation
        instruction next to the reference is more reliable than a negative alone."""
    lines = []
    if relay:
        lines.append(
            "@图1 is the approved final frame of the previous beat and must be matched exactly as the first "
            "frame only. Preserve character design, scale, expressions, continuity marks and lighting. "
            "Immediately after the first frame, begin the new action — free to travel anywhere the story "
            "needs. Do not hold the previous pose, replay the previous action, reset the characters or "
            "introduce unexplained repositioning.")
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
    size_clause = _v5_size_clause(cast)
    if size_clause:
        lines.append(size_clause)
    if plate_n:
        lines.append(f"@图{plate_n} scene plate — lighting, palette, texture throughout.")
        if relay:
            # Scoped to relay only: an opener's @图1 line never claims lighting/geography (it's just "begin
            # on this exact composition"), so there's nothing to arbitrate there. A relay's @图1 line DOES
            # claim "lighting and local geography" (line ~484 above), which genuinely overlaps the plate's
            # own declared job — this one clause resolves that specific, real overlap rather than a
            # hypothetical general priority scheme, keeping the cost to the ~9 words this actually needs.
            lines.append(f"If @图1 and @图{plate_n} disagree on lighting, @图{plate_n} wins.")
    if _v5_has_vocal_content(beat):
        lines.append("@Audio1 — sole source of all vocal sound; animate mouths and full performance to it. "
                      "No other voices generated.")
    else:
        # FIXED 2026-07-12 (full-codebase audit continued): no @Audio1 line at all for a genuinely wordless
        # beat — nothing was uploaded for it (cb_voice.build_dialogue_track returns None), so a reference to
        # it here would have described an input the render never actually receives. Negation is lawful in
        # this block already (the anti-hold-safe relay wording's own "Do not hold the previous pose..." is
        # exempted from cb_qa.check_gate3_lint's negation lint for the same reason — see that check's own
        # comment) so stating the held-silence rule directly here is consistent, not a new exception.
        lines.append("This beat is wordless — hold it in silence; no @Audio1 track exists, do not invent voice, mouth-sync or vocal sound.")
    return " ".join(lines)

# THE BUDGET RESOLUTION (Julian's ruling, 2026-07-06 — "the DNA slice from characters.json takes the POSITIVE
# movement sentences only... internal commentary in parentheses is never prompt text"). A sentence is dropped
# when it contains negation AND its topic duplicates a standing negative already covering it — that negation
# stays enforced in the Negative block, where negation lawfully lives, never restated inside a quoted
# character-voice sentence. A sentence with negation that does NOT match a known duplicate topic (e.g.
# Zenny's own "never big or busy gestures" — a genuine behavioural fact, not a standing-negative duplicate)
# survives untouched. Kept in sync with `_standing_negatives()` by construction: every topic below maps to
# one of that list's items (twelve as of 2026-07-13; this mapping set itself is unaffected by the twelfth,
# which has no character-voice-duplicate topic).
_DUPLICATE_NEGATIVE_TOPICS = {
    "inflat": "no body inflation (temporary impact squash-and-stretch only)",
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

# FIXED 2026-07-12 (full-codebase audit continued): `_DNA_MANNERISMS_MAX_SENTENCES = 2` used to live here,
# with a docstring arguing for a 2-sentence cap ("capping by SENTENCE COUNT... keeps that flagged sentence
# from being cut off") — but it had zero readers anywhere in the repo; the one call site that should have
# used it (`_v5_acting_dna_source`'s mannerisms fallback, below) hardcoded the literal `1` instead, and that
# function's OWN docstring already documents "a 1-sentence mannerisms slice" as the current, intentional
# fallback behaviour (the lean-acting-tag ruling, 2026-07-06, superseding the older 2-sentence design this
# constant was written for). Removed as genuinely dead code rather than reconciled to `2` — the 1-sentence
# cap is the already-correct, already-documented, currently-shipping behaviour; nothing reads this constant
# to change that.
_DNA_MANNERISMS_WORD_BACKSTOP = 70

def _v5_cap_sentences(text, max_sentences, max_words):
    """Keep the first `max_sentences` whole sentences of `text`, subject to a defensive `max_words`
    backstop — never cuts mid-sentence, never rewrites a surviving word. Always keeps at least the first
    sentence even if it alone exceeds the word backstop.

    FIXED 2026-07-13 (creativity-vs-rules audit, confirmed live against Sunny's own real mannerisms text):
    the split regex used to treat a bare semicolon as a sentence boundary — but a semicolon joins two
    clauses of ONE sentence in normal English ("Pure motion — bounding...; she physically cannot hold
    still...") rather than separating two sentences. With `max_sentences=1` this split "Pure motion —
    bounding, skipping, twirling, leaping;" off as if it were the whole first sentence, discarding its own
    second half and shipping a dangling semicolon with nothing after it. Currently dormant in the live
    package (every character has `cadence` authored, so this mannerisms-fallback path never fires today —
    see `_v5_acting_dna_source`), but a real, confirmed bug the moment any character lacks one. Now splits
    only on real sentence-ending punctuation (. ! ?), never a bare semicolon."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
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
    own topic. Never rewrites a surviving sentence's wording — every kept word is still a verbatim quote.

    FIXED 2026-07-13 (creativity-vs-rules audit — same shared bug as `_v5_cap_sentences`, this is the
    PRIMARY path every character's `cadence` runs through): the split regex used to treat a bare semicolon
    as a sentence boundary, so a real semicolon-joined clause (e.g. Zenny's own "deadpan, dry, understated;
    the reaction IS the comedy") could be split into two independent "sentences" and have EITHER HALF
    silently dropped by the negation-duplicate-topic filter below, if that half alone happened to match —
    leaving the surviving half's own semicolon dangling with nothing after it. No real character's current
    `cadence` text happens to trigger this today (confirmed live against all 9 real semicolon-bearing
    cadence fields — none independently match the negation filter), but it was a real, load-bearing
    correctness gap in the ONE function every character's Acting DNA line compiles through, not a
    hypothetical. Now splits only on real sentence-ending punctuation (. ! ?), never a bare semicolon."""
    def _strip_paren(m):
        return "" if _META_PAREN_WORDS.search(m.group(1)) else m.group(0)
    text = re.sub(r"\(([^)]*)\)", _strip_paren, str(text or ""))
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
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
        delivery = _v5_strip_speed_adjectives(_strip_spoken_words(str(c.get("delivery") or "").strip()))
        # FIXED 2026-07-13 (the "one render, sign it off, next beat" walk of Scene 1 — checking 1.B2 before
        # firing surfaced this): the speed-adjective stripper ran on action/framing/endState but never on
        # `delivery` — `check_gate3_lint`'s own (5) regression guard scans the WHOLE story block for a
        # leftover match, so a beat like 1.B2 ("words tumbling out fast") shipped a real generic pace word
        # to the paid API while the check correctly flagged it as a problem the compiler wasn't actually
        # fixing. `delivery` gets the exact same treatment as every other field feeding this block now.
        if delivery:
            # FIXED 2026-07-13 (creativity-vs-rules audit, confirmed live on 33/84 real dialogue cuts —
            # e.g. real beat 8.B3 cut 2 shipped "...childlike welcome rather than ceremony.." with a
            # literal double period): `delivery` is authored prose that often already ends in its own
            # terminal punctuation; the trailing "." was appended unconditionally on top of it. Now
            # strips any trailing terminal punctuation first, matching the sibling guard already used a
            # few lines above in `_v5_acting_dna` for the identical shape of problem.
            delivery = delivery.rstrip(".!?")
            poss = _v5_possessive(name)
            verb = "perform" if name.lower() == "all" else "performs"
            # FIXED 2026-07-14 (Julian: "can we not just look at what is just being said" — a plain read of
            # the real compiled prompt, not another lint pass, caught this): no separator ever sat between
            # "@Audio1" and the delivery text, so every dialogue cut in the show shipped a run-on like "from
            # @Audio1 fun sing-song rhythm" — reads like a dropped word, not a director's note. An em-dash
            # cleanly separates the reference tag from the acting direction that follows it.
            return f" {name} {verb} {poss} vocal beat from @Audio1 — {delivery}."
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

def resolve_physical_archetype(beat, scene):
    """THE SHARED ARCHETYPE RESOLVER (2026-07-14, extracted while building the SFX-sweetening mechanism,
    CLAUDE.md rule 62/82 — Julian: "go with those two things you flagged"): `_v5_archetype_prohibited` and
    `_v5_physics_anchor` each independently duplicated the identical 4-line dmode/style/gag/archetype
    resolution — a real internal duplication this codebase's own rule 11 discipline would normally have
    already deduped, just never had a second caller outside cb_segprompt.py to force the issue until now
    (cb_post.py's new SFX-sweetening step needs the SAME resolution, for the SAME reason: matching whichever
    archetype the negatives/physics-anchor text already resolved to, so a beat's sweetening cue never
    disagrees with its own shipped prompt). Never raises: a resolution failure returns None, exactly as if
    the beat had no archetype at all — this is enrichment, not a required input, matching both callers'
    existing contract."""
    try:
        import cb_seedance
        dmode = cb_seedance.infer_director_mode(beat, scene)
        style = cb_seedance.infer_shot_style(beat, dmode)
        gag = cb_seedance._gag_locks().get(beat.get("script_gag_lock_id")) if beat.get("script_gag_lock_id") else None
        return cb_seedance.infer_physical_archetype(beat, dmode, style, gag)
    except Exception:
        return None

def _v5_expression_line(beat, episode="Ep1"):
    """THE EXPRESSION LINE — Glen Keane's actual supervising-animator craft, closing a real, confirmed gap
    found by a full gate-by-gate trace + adversarial verify (2026-07-14, CLAUDE.md rule 84/85 — "we have to
    go with what we've learned... fired by the correct workflows"): cb_director_pass.direct_beat() computes
    real per-beat camera_approach/shots[]/expression/performance every beat via a genuine LLM call — Keane's
    named supervising-animator direction — but before this fix NOTHING of it reached the shipped prompt
    except voice_direction. The rest (including this field) was computed, cached, and silently discarded.

    Only `expression` is folded in, not the whole DirectorPass: `camera_approach`/`shots[].camera` would
    compete with `beat.cuts[].framing` — the Gate-1-authored per-shot camera direction the shot list already
    ships — exactly the "two signals for one job" failure class rules 24/26 already diagnosed once for
    reference images (two "match the reference" signals pulling against each other). `performance`/
    `comedy_or_heart_note`/`serves_the_why` are each either redundant with an existing block (Acting DNA, the
    Motion Contract lint) or internal creative reasoning Seedance itself doesn't need. `expression` is the one
    genuinely non-redundant field — the specific face/eye/body detail that sells the beat's inner state, real
    "illusion of life" craft (appeal, a held pose worth holding on) that a story-level shot list doesn't
    naturally specify.

    Pure cache read, no LLM call of its own (matching the physics anchor's own "enrichment, never a required
    input" contract): render_readiness() runs before shipped_prompt() on every real fire (cb_beats.run,
    confirmed by code trace) and already triggers direct_beat() for this beat via build_for_beat, so a real
    cached direction normally exists by the time this reads it. If it doesn't (CB_DIRECTOR_PASS=0, an
    uncached preview/CLI call, or the beat hasn't been through readiness yet), this degrades to no line at
    all — never raises, never blocks."""
    # THE 24-WORD CLAUSE CAP, REMOVED (2026-07-15, Julian, live — "the guardrails are there... to bring that
    # beat to life... not guardrails for anything else"): a real audit found this cap firing on 43 of 43
    # real beats, silently discarding an average of 70 words each — ~3,000 words of Keane's own cached
    # animator direction (the "on impact / rebound / recovery" arc that actually sells the comedy) reduced
    # to its first clause on every single beat, unconditionally, with zero relationship to how much of the
    # beat's own real 700-word budget was actually spent (1.B1 alone had 120 spare words at the time this was
    # found). This is the identical fix already proven safe once in this same file — the shot list's own
    # 80-word fence was retired outright for the same reason (rule 45: "a real per-cut shot list cannot fit
    # in a small fixed budget; the whole-prompt cap is the correct backstop") — applied here to the second
    # field caught doing the same thing. The single outer word-budget (cb_preflight.WORD_BUDGET_BLOCK/TARGET)
    # is now the only gate on this field's length, exactly as it already was for the shot list.
    try:
        import cb_director_pass
        code = beat.get("beatCode") or beat.get("shotCode") or "?"
        expr = str(cb_director_pass.cached_expression(episode, code) or "").strip()
        if not expr:
            return ""
        expr = _v5_strip_speed_adjectives(_strip_spoken_words(expr))
        if not expr:
            return ""
        return f"EXPRESSION: {expr}."
    except Exception:
        return ""

# THE FIELD-LOCAL WORD CAP, RETIRED ENTIRELY (2026-07-15, Julian, live — "guardrails... to bring that beat
# to life... not guardrails for anything else"): the cap on this field went 9 -> 24 words (2026-07-13, rule
# 76) after it was CAUGHT dropping the dynamic half of a real beat's physics — "the flower compresses softly
# under his face" shipped, "then springs back with elastic weight as a pollen puff bursts" silently didn't —
# implicated in that beat's own real-footage "reads static" complaint. Widening the number was a patch on
# the same broken mechanism, not a fix: a real audit confirmed even 24 words was STILL cutting the settle/
# recovery half off LEAF_CRASH_REBOUND's own physics_rule on real beats (1.B1, 5.B3), unforced — 1.B1 alone
# had 120 spare words under the real 700-word cap when this fired. The field-local cap is retired outright,
# matching this file's own already-proven fix for the identical failure shape (the shot list's own 80-word
# fence, retired in rule 45 for the same reason) — the single outer word-budget is the only gate now.

def _v5_physics_anchor(beat, scene):
    """THE POSITIVE PHYSICS ANCHOR (2026-07-13, closing the gap the independent craft audit named: "state
    the good outcome once, in the action line, is strictly more reliable than listing sixteen bad outcomes
    and hoping none of them summon the thing they're trying to prevent" — capability judge, cross-corroborated
    by directing/examples/fresh_eyes). `_v5_archetype_prohibited` (rule 62, 2026-07-09) wired the archetype's
    NEGATIVE half (`prohibited_staging`) into the shipped prompt; this is the missing POSITIVE half — the
    same archetype's own already-authored `physics_rule` (concrete, physically specific staging language,
    e.g. "the flower compresses softly under his face, then springs back with elastic weight as a pollen
    puff bursts"), mechanically quoted verbatim in full, never hand-rewritten, never field-capped (the
    field-local cap was retired 2026-07-15 — see the note above this function). Resolves the archetype the
    IDENTICAL way `_v5_archetype_prohibited` already does (dmode/style/gag/archetype), so the two always
    agree on which archetype applies. Deliberately does NOT touch `_v5_negative_line`'s own existing
    archetype-negatives wiring — rule 62 was hard-won and this is additive, not a replacement for it.
    Speed-adjectives are stripped for the same adjective-chaos-ban reason Block 4's own action/framing text
    already gets it (rule 33). Never raises: a resolution failure degrades to "no anchor", exactly as if the
    beat had no archetype at all — this is enrichment, not a required input."""
    try:
        import cb_seedance
        archetype = resolve_physical_archetype(beat, scene)
        physics = cb_seedance.PHYSICAL_ARCHETYPES.get(archetype, {}).get("physics_rule", "")
        if not physics:
            return ""
        physics = _v5_strip_speed_adjectives(physics)
        if not physics:
            return ""
        return f"PHYSICS: {physics}."
    except Exception:
        return ""

def _v5_beat_story(beat, cast, scene=None, episode="Ep1"):
    """Block 4 — THE SHOT LIST (Julian's ruling, 2026-07-06, live footage review of 1.B1 — "where's the
    action... the cut saying what camera it is, what he's doing... where's the story beat?"): walks the
    beat's own authored `cuts[]`, one shot per cut — camera framing + the cut's specific action + who
    speaks (never the words, Law 6) — ending on endState's living settle. Supersedes the prior flattened
    approach (the beat's own `storyBeat` summary sentence, capped at 80 words), which was found live to
    silently drop every cut's camera and named staging (e.g. 1.B1's "zig-zag ladder: left petal pass,
    right stem dodge, low grass skim" and the leaf-FWIP-rebound), leaving Seedance nothing concrete to
    act on beyond one generic sentence. The doctrine's own §2 80-word fence on this block is RETIRED by
    this same ruling — a real per-cut shot list cannot fit three cameras + three actions in 80 words, and
    the true backstop is (and was always) the whole-prompt hard cap (cb_preflight.py) — 650 words as of
    2026-07-07's rule 52 (FIXED 2026-07-12, full-codebase audit continued: this used to say "400-word hard
    cap," stale since the raise; 400 is now only the FLAG-only target, not the block — see this module's
    own top-of-file docstring, already correct). Speed adjectives mechanically stripped from both framing and action (rule 33's
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
    only counts alphabetic runs; digits and the en dash contribute nothing).

    THE PHYSICS ANCHOR (2026-07-13): when the beat resolves a physical archetype, a leading "PHYSICS: ..."
    line (`_v5_physics_anchor`) opens this block — the archetype's own already-authored, concrete physics
    staging quoted and clause-capped, stated positively once instead of relying on the Negative line's
    "no X" phrasing alone (closing the gap an independent craft audit named — see CLAUDE.md rule 75).
    Joined into this same "\\n"-separated block, never a new "\\n\\n" block, for the identical block-index
    reason the shot-timing law above already states.

    THE EXPRESSION LINE (2026-07-14): a second, optional leading line, "EXPRESSION: ...", right after PHYSICS
    — Glen Keane's own cached supervising-animator direction (`_v5_expression_line`), closing the confirmed
    gap where his real per-beat output was computed and then entirely discarded (CLAUDE.md rule 84/85). Same
    "\\n"-internal, never a new "\\n\\n" block, same reasoning."""
    import cb_qa
    cuts = beat.get("cuts") or []
    if not cuts:
        raise cb_qa.ManifestFieldMissing("cuts", "this beat's own shot list — required for the v5 shot-list block")
    settle = str(beat.get("endState") or "").strip()
    if not settle:
        raise cb_qa.ManifestFieldMissing("endState", "this beat's own settle text — required for the v5 shot-list block")
    lines = []
    physics = _v5_physics_anchor(beat, scene)
    if physics:
        lines.append(physics)
    expression = _v5_expression_line(beat, episode)
    if expression:
        lines.append(expression)
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
_LEADING_ARTICLE_RE = re.compile(r"^(a|an)\s+", re.IGNORECASE)

def _v5_archetype_prohibited(beat, scene):
    """THE ARCHETYPE SAFETY NET, WIRED IN (Julian's ruling, 2026-07-09 — "every time we find something like
    this, we need to write it into the software, not just the prompt... solve the problem, not just the
    symptom"): 1.B4 was assigned the physical archetype POLLEN_SMEAR_TUMBLE via cb_seedance's own
    _ARCHETYPE_OVERRIDES map — and that archetype's own `prohibited_staging` field already said, verbatim,
    "disappearing into a flower" — but PHYSICAL_ARCHETYPES has never been read by this module (confirmed by
    grep: zero references anywhere in cb_segprompt.py before this fix). The rich staging doctrine authored
    for exactly this failure mode existed, but never reached the prompt Seedance actually renders — so the
    beat rendered with nobody ever having told the model not to do the thing its own assigned archetype
    already named as prohibited. Hand-patching 1.B4's own stagingProhibited fixed that ONE beat; this
    function makes the fix APPLY AUTOMATICALLY to every beat with a resolved archetype, present and future,
    not just the one that happened to get noticed. `cb_seedance` is imported lazily (it already imports
    FROM cb_segprompt — _strip_spoken_words — so a module-level import here would be circular). Never
    raises: archetype resolution is a best-effort enrichment of the negatives list, not a required input to
    prompt compilation — a resolution failure degrades to "no extra negatives", exactly as if the beat had
    no archetype at all, never breaks the compile."""
    try:
        import cb_seedance
        archetype = resolve_physical_archetype(beat, scene)
        prohibited = cb_seedance.PHYSICAL_ARCHETYPES.get(archetype, {}).get("prohibited_staging", "")
        return [p.strip() for p in prohibited.split(";") if p.strip()]
    except Exception:
        return []

def _v5_negative_line(beat, scene):
    """The Negative line — the ONLY negation anywhere in the prompt (doctrine §2/§4): the twelve standing
    items plus the beat's own stagingProhibited, plus its resolved physical archetype's own prohibited_staging
    (2026-07-09 — see `_v5_archetype_prohibited`), merged, terse, deduped. `bible.dos`/`bible.donts` do NOT
    feed this — §3's own "Never in a prompt" list names them explicitly ("writer-room guidance... live at
    Gate 1 as review criteria"), reversing the immediately-prior ruling that had them feed per-beat
    staging/negatives.

    "no " PREFIX ON STAGING ITEMS (2026-07-08, Julian's ruling reviewing 1.B2 — his own worked example
    prefixed every gag-specific item with "No", matching the standing items' own convention): a beat's own
    `stagingProhibited` phrase (authored as a bare noun phrase, e.g. "Fuzzby disappearing into the flower")
    is mechanically prefixed with "no " if it doesn't already start with a negation word — a formatting
    normalisation only, never a content change, so every item in the line reads with the same "no X" cadence
    instead of the standing items alone carrying it. The archetype's own phrases get the identical treatment.

    FIXED 2026-07-13 (creativity-vs-rules audit, confirmed live on 22/43 real shipping beats): the prefix
    step didn't strip a leading indefinite article first, so a phrase authored/resolved as "a clean face" or
    "an easy pull" shipped as "no a clean face" / "no an easy pull" — grammatically broken in the exact same
    way the CLAUDE.md-documented "at full," bug was, just from a different mechanism. `_LEADING_ARTICLE_RE`
    strips a leading "a "/"an " before the "no " prefix is applied, so the same phrases now ship as "no
    clean face" / "no easy pull," matching the standing negatives' own article-free cadence.

    DEDUPE: a hand-authored stagingProhibited item can legitimately restate the same thing its own archetype
    already names (as happened writing this fix for 1.B4 itself) — a case-insensitive substring check drops
    an archetype phrase that's already covered by a beat-authored one, so the line never repeats itself.

    ARCHETYPE-NEGATIVE SUPPRESSION REVERTED (2026-07-14, real footage diagnosis — Julian, watching 1.B2's
    actual render: "physics issues he disapears into the flower"): the 2026-07-13 change below (rule 75/76)
    unconditionally suppressed the archetype's own `prohibited_staging` phrases whenever ANY physics anchor
    existed, on the theory that the anchor's positive text always covers the same ground. That assumption was
    wrong for at least one real archetype: POLLEN_FACE_PRESS_REVEAL's physics_rule ("the flower compresses
    softly under his face, then springs back with elastic weight as a pollen puff bursts") describes the
    FLOWER's own mechanics — it says nothing about the CHARACTER staying visible. Its own prohibited_staging
    ("full-body flower entry; disappearing/buried-inside; hidden silhouette") is the ONLY thing in this
    compiler that states that constraint at all, and suppressing it left 1.B2's real compiled Negative line
    with no protection against exactly the failure that then happened on the actual render — confirmed by
    extracting and reading the real clip's own frames at ~1.8-2.4s: Fuzzby is 100% gone from the shot, the
    frame shows only a flower. Reverted to rule 62's original, unconditional archetype-negative injection —
    the 2026-07-13 word-budget rationale (below, kept as dated history) is real but was worth less than the
    protection it cost; 1.B1 and 1.B2 both re-verified to still compile comfortably under the 700-word hard
    cap with this reverted.

    ARCHETYPE NEGATIVES SUPPRESSED WHEN A PHYSICS ANCHOR COVERS THE SAME GROUND POSITIVELY (2026-07-13, real
    footage diagnosis, same night as `_v5_physics_anchor`, CLAUDE.md rule 75/76) — SUPERSEDED, SEE ABOVE:
    rule 62's own archetype-prohibited wiring is deliberately kept — this does NOT touch it in general. But
    once a beat resolves a PHYSICS anchor (the archetype's own positive `physics_rule`, now widened to hold
    the real two-clause description), restating the SAME archetype's negative half too is doubly redundant:
    it costs real word budget that direct testing showed causes the physics anchor itself to be trimmed back
    to its flattest, least dynamic clause (the actual root cause of a real "non-movement" complaint on 1.B2's
    real footage — the PHYSICS anchor was forced to keep only "the flower compresses softly under his face"
    and drop "then springs back with elastic weight as a pollen puff bursts" to fit budget). The beat's own
    hand-authored `stagingProhibited` and the twelve standing negatives are UNCHANGED — only the archetype's
    own auto-injected phrases are skipped, and only when a real physics anchor exists to say the positive
    version of the same thing."""
    staging = [str(x).strip() for x in (beat.get("stagingProhibited") or []) if str(x).strip()]
    arch_phrases = _v5_archetype_prohibited(beat, scene)
    staging_low = [s.lower() for s in staging]
    for p in arch_phrases:
        pl = p.lower()
        if not any(pl in s or s in pl for s in staging_low):
            staging.append(p)
            staging_low.append(pl)
    staging = [s if _NEGATION_LEAD_RE.match(s) else f"no {_LEADING_ARTICLE_RE.sub('', s)}" for s in staging]
    negatives = staging + _standing_negatives()
    return "Negative: " + "; ".join(negatives) + "."

def emit_v5(beat, scene, cast, relay, episode="Ep1"):
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
        _v5_beat_story(beat, cast, scene, episode),
        _v5_negative_line(beat, scene),
    ]
    return "\n\n".join(parts)

def for_beat_v5(beat, scene=None, relay=False, episode="Ep1"):
    cast = beat.get("openingCast") or beat.get("characters") or []
    if not (beat.get("cuts") or []):
        return "", "v5 (empty — no cuts)"
    return emit_v5(beat, scene, cast, relay, episode), "v5"

def shipped_prompt(beat, scene=None, relay=False, prev_end_state_still=None, prev_carry_marks=None, episode="Ep1"):
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
    instead of a silent degrade.
    episode (2026-07-14, closing the Gate-3/Keane gap — CLAUDE.md rule 84/85): keyed into
    cb_director_pass.cached_expression (Block 4's optional EXPRESSION line) — the SAME class of episode-
    threading fix this module's own __main__ already made once for relay-frame lookups (rule 59's
    "baseline-proof relay fix"), applied here for the identical reason: a silent 'Ep1' default would
    silently read the WRONG episode's cached direction for any future non-Ep1 package. Every real production
    call site (cb_beats.py, cb_seedance.py, cb_qa.py, cb_preflight.py) already has episode in local scope and
    passes it explicitly; cb_golden.py/tests default to 'Ep1' deliberately, since that IS the only episode
    those modules ever operate on."""
    v5, emitter5 = for_beat_v5(beat, scene, relay=relay, episode=episode)
    return v5, f"cb_segprompt_v5 ({emitter5})", True

if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
    code = sys.argv[2] if len(sys.argv) > 2 else "1.B1"
    episode = sys.argv[3] if len(sys.argv) > 3 else "Ep1"
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
    # episode, not hardcoded "Ep1" — a hardcode here silently looked up the WRONG episode's settle-frame media
    # path for any package other than Ep1's own (2026-07-08 audit finding); the CLI now accepts it as an
    # optional 3rd argument, same convention as every other module's own __main__ (default "Ep1").
    _, _relay_status, _ = cb_scene.relay_source_for(scene_beats, code, episode)
    relay = _relay_status == "relay"
    prompt, _builder, _is_definitive = shipped_prompt(beat, scene, relay=relay, episode=episode)
    wc = _v5_word_count(prompt)
    import cb_preflight as _PF
    print(f"===== GATE-3 SEEDANCE PROMPT — {code}  (relay={relay}, {len(prompt)} chars, {wc} words — target "
          f"{_PF.WORD_BUDGET_TARGET}, hard block {_PF.WORD_BUDGET_BLOCK}) =====\n")
    print(prompt)
