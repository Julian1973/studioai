#!/usr/bin/env python3
"""cb_preflight.py — THE MANIFEST enforcement tool (CLAUDE.md rule 37, MANIFEST.md, 2026-07-06, Julian's
ruling — "blanks BLOCK on both contracts... a missing field halts with the field named").

ONE command: checks the CURRENT beat package against BOTH contracts (TECHNICAL, CREATIVE) — per beat, per
scene, per character, per package — and prints a PASS/FAIL gap table, every gap named. This tool only
REPORTS — it never fires, retakes, signs, or edits anything. `manifest_ok(pkg_path, scene, episode)` is the
importable choke-point every gate-arming call site (cb_pipeline.approve, cb_beats.fire_next_beat,
cb_replicator.walk_scene, cb-studio/serve.py's fire/approve endpoints) calls before proceeding — see
MANIFEST.md's "Gate ordering in code" section.

    python3 cb_preflight.py [package.json] [--episode=EpN] [--scene=N]

Deliberately CHEAP and LOCAL: no vision/LLM calls (this runs on every gate-arming check, potentially many
times per session) — structural/text checks only. Deeper vision-based QA (cb_qa.check_plate's crystal-shape
verdict, cb_qa.check_clip's identity/anatomy checks) already runs at its own natural build/render points
elsewhere in the pipeline; this tool does not re-trigger them.
"""
import os, sys, json, re, glob

HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_PATH = os.path.join(HERE, "config", "characters.json")

# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Package resolution — same glob convention as cb_pipeline._resolve_pkg / cb_golden._resolve_pkg_path, never
# a hardcoded filename or episode.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _resolve_pkg(episode=None):
    pattern = f"{episode}_*beat_package.json" if episode else "*beat_package.json"
    cands = glob.glob(os.path.join(HERE, "..", "cb-output", pattern))
    if not cands and episode:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", f"{episode}_*shot_package.json"))
    if not cands:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", "*shot_package.json"))
    return max(cands, key=os.path.getmtime) if cands else None


class Gap:
    """One named finding. kind: 'BLOCK' (a required field is blank/missing) | 'FLAG' (advisory — a computed
    check with no fixed bar, or a best-effort heuristic) | 'STRUCTURAL' (already impossible to violate by
    construction, reported so 'every gap named' doesn't quietly skip it)."""
    __slots__ = ("scope", "code", "field", "kind", "detail")
    def __init__(self, scope, code, field, kind, detail=""):
        self.scope = scope      # "beat" | "scene" | "character" | "package"
        self.code = code        # beat code, scene number, character name, or "package"
        self.field = field
        self.kind = kind
        self.detail = detail
    def line(self):
        tag = {"BLOCK": "BLOCK", "FLAG": "FLAG ", "STRUCTURAL": "OK   "}[self.kind]
        d = f" — {self.detail}" if self.detail else ""
        return f"  [{tag}] {self.scope} {self.code}: {self.field}{d}"


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per beat
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
_HOLD_RE = re.compile(r"(\d+(?:\.\d+)?)[\s-]*second")

def check_beat_technical(beat, is_scene_opener):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    gaps = []

    if _blank(beat.get("endState")):
        gaps.append(Gap("beat", code, "endState", "BLOCK", "this beat's own settle text — required on every beat"))
    if _blank(beat.get("endStateStill")):
        gaps.append(Gap("beat", code, "endStateStill", "BLOCK", "static-photograph counterpart to endState — required on every beat"))
    if _blank(beat.get("carryMarks")):
        gaps.append(Gap("beat", code, "carryMarks", "BLOCK", "short phrase naming what persists — required on every beat"))

    jt = beat.get("junctionType")
    if is_scene_opener:
        pass   # the scene's first beat has no predecessor to join from — junctionType doesn't apply
    elif _blank(jt):
        gaps.append(Gap("beat", code, "junctionType", "BLOCK",
                         "not authored (code safely defaults to intentional_next_shot per rule 31, but the "
                         "Manifest wants it declared, not relied on as a silent default)"))

    ph = beat.get("pauseHold")
    if _blank(ph):
        gaps.append(Gap("beat", code, "pauseHold", "BLOCK", "must state a concrete hold duration"))
    else:
        m = _HOLD_RE.search(str(ph))
        if not m:
            gaps.append(Gap("beat", code, "pauseHold", "BLOCK", f"no concrete duration stated in {ph!r}"))
        elif float(m.group(1)) > 1.5:
            gaps.append(Gap("beat", code, "pauseHold", "BLOCK", f"states {m.group(1)}s — staging law caps holds at <=1.5s"))

    if not is_scene_opener and jt != "seamless_continuation":
        oo = beat.get("opensOn") or {}
        if not (isinstance(oo, dict) and oo.get("who") and oo.get("action")):
            gaps.append(Gap("beat", code, "opensOn", "BLOCK", "required for an intentional_next_shot beat (the default) — {who, action}"))

    if _blank(beat.get("actingContrast")):
        gaps.append(Gap("beat", code, "actingContrast", "BLOCK", "required on every beat"))

    # THE DELIVERY LAW (rule 53, 2026-07-08): a cut with dialogue must have a non-blank delivery note —
    # cb_segprompt._v5_cut_speaker_note now quotes it verbatim into the shipped prompt as acting direction;
    # a blank delivery on a spoken cut silently degrades to a bare "{Name} speaks." — the exact flat
    # placeholder this law exists to replace.
    for c in (beat.get("cuts") or []):
        if str(c.get("dialogue") or "").strip() and _blank(c.get("delivery")):
            gaps.append(Gap("beat", code, "delivery", "BLOCK",
                            f"cut {c.get('n')} has dialogue but no delivery note — required acting direction, "
                            f"never the words (see cb_director_schemas.Cut.delivery's worked-example bar)"))

    # stagingProhibited WELL-FORMEDNESS (found missing in the 2026-07-08 software-wide audit): the field is
    # genuinely OPTIONAL (unlike carryMarks/actingContrast, most beats correctly have none authored) — this
    # is NOT a presence check. But cb_segprompt._v5_negative_line reads it directly into the shipped Negative
    # line the moment it exists, so a malformed value (not a list, or a list containing a blank entry) would
    # either crash the emitter or silently ship an empty/garbled negative — checked here, at data-authoring
    # time, rather than only surfacing as a render-time failure.
    sp = beat.get("stagingProhibited")
    if sp is not None:
        if not isinstance(sp, list):
            gaps.append(Gap("beat", code, "stagingProhibited", "BLOCK", f"must be a list of strings, got {type(sp).__name__}"))
        elif any(_blank(x) for x in sp):
            gaps.append(Gap("beat", code, "stagingProhibited", "BLOCK", "contains a blank entry — every item must be a real, non-empty phrase"))

    speakers = [s for s in (beat.get("speakers") or []) if s]
    dlg_all = []
    for c in (beat.get("cuts") or []):
        d = (c.get("dialogue") or "").strip()
        if d:
            sp = d.split(":", 1)[0].strip().title()
            if sp and sp.lower() != "all":   # a group_chorus line ("ALL: ...") isn't tied to one speaker's order
                dlg_all.append(sp)
    first_order = []   # distinct speakers, in FIRST-APPEARANCE order — alternating dialogue (A, B, A) is normal
    for sp in dlg_all:
        if sp not in first_order:
            first_order.append(sp)
    if speakers and first_order:
        # speakers[] may legitimately list more names than get an individual line (a chorus participant covered
        # only by an "ALL:" line, say) — only the RELATIVE ORDER of names that DO speak individually is checked,
        # never the full list length, so a chorus-only participant listed alongside them is not a false mismatch.
        norm_speakers = [s.strip().title() for s in speakers]
        speakers_subset = [s for s in norm_speakers if s in first_order]
        missing_names = [s for s in first_order if s not in norm_speakers]
        if missing_names:
            gaps.append(Gap("beat", code, "speaker order", "BLOCK",
                            f"{missing_names} speak(s) individually in cuts[] but is not listed in speakers[]={speakers}"))
        elif speakers_subset != first_order:
            gaps.append(Gap("beat", code, "speaker order", "BLOCK",
                            f"speakers={speakers} orders its individual speakers as {speakers_subset}, but cuts[] "
                            f"has them speak in this order: {first_order}"))
    elif first_order and not speakers:
        gaps.append(Gap("beat", code, "speaker order", "BLOCK", f"cuts[] has dialogue ({first_order}) but speakers[] is empty"))

    # single gag arc — best-effort structural heuristic only (cb_qa.py's own comments admit this cannot be
    # a real semantic guarantee: "Law 1's other half... this lint cannot cover at all").
    holds_stated = len(re.findall(r"\bone hold\b", str(ph or "").lower()))
    gag_locks = 1 if beat.get("script_gag_lock_id") else 0
    if _blank(ph) or gag_locks == 0:
        gaps.append(Gap("beat", code, "single gag arc", "FLAG",
                        "heuristic only (no pauseHold and/or no script_gag_lock_id to anchor on) — cannot confirm a single arc"))

    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per scene
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_scene_technical(scene, episode, gate="1"):
    """The plate is NEVER a manifest BLOCK, in any gate scope (Julian's ruling, 2026-07-06 — "NO plates yet —
    plates are Stage 2, after Gate 1 carries my signature"): its own crystal-shape/no-characters QA already
    runs automatically at Gate-2a build time (cb_qa.check_plate) — a SEPARATE, already-enforced mechanism —
    so the manifest only ever reports whether it exists yet, informationally, never gating a sign-off on it.
    The `gate` param is kept for forward compatibility (a future Gate-2+-only check could use it) but does not
    currently change this function's behaviour."""
    sn = str(scene.get("sceneNumber"))
    gaps = []

    plate_path = os.path.join(HERE, "media", f"{episode}_S{sn}_plate.png")
    if not os.path.exists(plate_path):
        gaps.append(Gap("scene", sn, "plate", "STRUCTURAL",
                        "not built yet — expected at this stage (plates are Stage 2, after Gate 1 is signed); "
                        "its own QA (cb_qa.check_plate) runs automatically once it exists, never gated here"))
    else:
        gaps.append(Gap("scene", sn, "plate", "STRUCTURAL",
                        "plate file exists — its own crystal-shape/no-characters QA already runs at Gate-2a build time (cb_qa.check_plate), not re-triggered here"))

    if _blank(scene.get("ambientBed")):
        gaps.append(Gap("scene", sn, "ambientBed", "BLOCK", "required on every scene"))
    else:
        gaps.append(Gap("scene", sn, "ambientBed", "STRUCTURAL",
                        "present — word-for-word identity across every beat in the scene is already guaranteed by construction (rule 35), not re-checked"))

    # THE SCENE-LOOK LAW (rule 53, 2026-07-08): required on every scene, same pattern as ambientBed —
    # cb_segprompt._v5_scene_look reads it verbatim into every beat's shipped Block 1. Added the same day
    # the universal style law was leaned (rule 52, decision 4) and scene atmosphere moved OUT of it — a
    # scene with no sceneLook now ships beats with ZERO atmosphere language at all, a real content gap, not
    # a cosmetic one.
    if _blank(scene.get("sceneLook")):
        gaps.append(Gap("scene", sn, "sceneLook", "BLOCK", "required on every scene (the light/mood line every beat inherits — see cb_segprompt._v5_scene_look)"))
    else:
        gaps.append(Gap("scene", sn, "sceneLook", "STRUCTURAL", "present"))

    # FIXED 2026-07-06 (found live during Scene 1's real walk — 1.B2 hard-stopped on a stale scene cache that
    # this manifest check had reported CLEAN moments earlier): this used to shell out to a script named
    # "sync_scenes.py" with cwd=HERE (engine/) — but the real file lives at repo-root tools/sync_scenes.py, not
    # engine/sync_scenes.py, so the subprocess always failed to even find the script. subprocess.run doesn't
    # raise on a nonzero exit unless check=True, so the try/except here never caught it either — the failure's
    # own message went to STDERR (never inspected), stdout stayed empty, and `f"scene {sn}:" in (r.stdout or "")`
    # was always False, silently skipping the BLOCK entirely. Fixed by calling cb_prompts.scene_cache_stale()
    # directly — the SAME function cb_beats.py already correctly uses to catch this at fire time — instead of
    # shelling out to a script by a fragile relative path at all.
    try:
        import cb_prompts
        stale = cb_prompts.scene_cache_stale(episode, sn, pkg_path=_resolve_pkg(episode))
        if stale:
            gaps.append(Gap("scene", sn, "locations cache sync", "BLOCK", stale))
    except Exception as e:
        gaps.append(Gap("scene", sn, "locations cache sync", "FLAG", f"could not run cb_prompts.scene_cache_stale ({str(e)[:80]})"))

    try:
        import cb_qa
        pkg_path = _resolve_pkg(episode)
        vocab = cb_qa.check_scene_vocabulary(pkg_path, sn, episode)
        if not vocab["ok"]:
            gaps.append(Gap("scene", sn, "banned vocabulary", "BLOCK", vocab["verdict"]))
    except Exception as e:
        gaps.append(Gap("scene", sn, "banned vocabulary", "FLAG", f"vocab check failed to run ({str(e)[:80]})"))

    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per scene, DIALOGUE VERBATIM FIDELITY (2026-07-07, the Pixar-craft-audit find)
#
# cb_director.enforce_verbatim already snaps every beat's dialogue to the writer's exact script lines — but ONLY
# once, inside direct()'s own authoring run. A beat package that is later hand-edited (a manifest-authoring pass,
# a manual scrub, a future Studio edit) has NO standing check re-comparing its shipped dialogue against the
# script — the gap that let Scene 9 ship three real drifts (AIDA's two lines replaced with invented paraphrases
# despite their own script_truth_lock fields explicitly claiming verbatim use, and Keen's Crystal Call dropping
# the word "Crystal") that survived undetected until an independent craft audit found them by direct comparison.
# This closes it the same way rule 46/47 closed the manifest-repair-path gap: a RE-RUNNABLE check, not a one-shot
# authoring-time guarantee — callable at ANY time cb_preflight runs (every gate-arming call site), so a future
# drift (manual or Director-authored) is always caught, not just the drift that happened to exist at Gate 1 fire
# time. This is a HARD, MECHANICAL, ZERO-LLM comparison — not a craft/taste judgment — the script is the ground
# truth per this project's own Faithful Director law, so a mismatch here is never a subjective call.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
SCRIPTS_DIR = os.path.join(HERE, "..", "cb-studio", "data", "scripts")

def _script_roster(characters=None):
    chars = characters if characters is not None else (json.load(open(CHARACTERS_PATH)) if os.path.exists(CHARACTERS_PATH) else {})
    base = chars.get("characters", chars) if isinstance(chars, dict) else {}
    names = {k.upper() for k in (base.keys() if isinstance(base, dict) else [])}
    return names | {"ALL", "KEEN'S MUM", "HOWIE", "HOWEY"}


def _norm_dialogue_words(s):
    """Word-only normalisation — mirrors cb_director._norm_line exactly (drop [V3 tags], a leading NAME:, and
    punctuation) so 'matches the script' means the same thing here as it does at authoring time."""
    s = re.sub(r"\[[^\]]*\]", "", s or "")
    s = re.sub(r"^[A-Z' .]+:\s*", "", s.strip())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def _beat_sort_key(code):
    """Natural sort on the trailing beat number ('3.B10' -> 10, never a lexicographic '3.B10' < '3.B9' bug —
    cb_director.py's enforce_verbatim/​_force_include both carry the same warning; this is new code, so it must
    not reintroduce the class of bug they already guard against."""
    m = re.search(r"[Bb](\d+)\s*$", str(code or ""))
    return int(m.group(1)) if m else 0


def _resolve_script(episode):
    cands = glob.glob(os.path.join(SCRIPTS_DIR, f"{episode}_*.txt"))
    return max(cands, key=os.path.getmtime) if cands else None


def check_scene_dialogue_verbatim(scene, scene_beats, script_scenes, roster):
    """HARD BLOCK — compare this scene's shipped cut dialogue, IN BEAT/CUT ORDER, against the script's own
    dialogue_lines() for this scene, IN ORDER (cb_script.dialogue_lines is the deterministic ground truth — no
    LLM, so it can never itself drift).

    Uses difflib's LCS alignment, NOT a blind positional zip — found live, 2026-07-07: a positional zip cascades
    a false mismatch onto every subsequent line once ANY one line is legitimately dropped or genuinely rewritten
    (Scene 3's deliberate, Julian-approved cut of Mum's "I still feel him... every day" line shifted every later
    index by one, making 3.B4 through 3.B8's already-CORRECT lines all read as 'wrong' purely because they'd
    slid one slot out of phase with a naive index compare — the same class of self-inflicted cascade
    enforce_verbatim's own docstring already warns about for beat ORDER, now shown to apply to line-position
    drift too). difflib.SequenceMatcher finds the true longest common subsequence first, so a genuinely-matching
    line anywhere later in the scene is still recognised as a match, and only the REAL insertions/deletions/
    rewrites are reported."""
    import difflib
    sn = scene.get("sceneNumber")
    gaps = []

    script_scene = next((s for s in script_scenes if s.get("sceneNumber") == sn), None)
    if script_scene is None:
        gaps.append(Gap("scene", str(sn), "dialogue verbatim", "FLAG",
                        f"no matching scene {sn} found in the parsed script — cannot verify dialogue fidelity "
                        f"(check the script file resolved, and that its scene numbering matches the beat package)"))
        return gaps
    import cb_script
    script_lines = cb_script.dialogue_lines([script_scene])   # [(sceneNumber, CHAR, line), ...] for this scene only

    ordered = sorted(scene_beats, key=lambda b: _beat_sort_key(b.get("beatCode") or b.get("shotCode")))
    slots = []   # (beatCode, cut_n, dialogue_str) for every cut with spoken dialogue, in true beat/cut order
    for b in ordered:
        code = b.get("beatCode") or b.get("shotCode")
        for c in (b.get("cuts") or []):
            d = (c.get("dialogue") or "").strip()
            if d:
                slots.append((code, c.get("n"), d))

    script_norm = [_norm_dialogue_words(f"{ch}: {ln}") for (_sn, ch, ln) in script_lines]
    ship_norm = [_norm_dialogue_words(d) for (_c, _n, d) in slots]

    sm = difflib.SequenceMatcher(None, script_norm, ship_norm, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        script_slice = [f"{script_lines[k][1]}: {script_lines[k][2]}" for k in range(i1, i2)]
        ship_slice = [f"{slots[k][0]} cut {slots[k][1]}: {slots[k][2]!r}" for k in range(j1, j2)]
        if tag == "replace" and (i2 - i1) == (j2 - j1) == 1:
            # a genuine 1:1 rewrite — the common, actionable case (Scene 9's "We saw you dive" class of bug).
            code, cut_n, shipped = slots[j1]
            gaps.append(Gap("beat", code, "dialogue verbatim", "BLOCK",
                            f"cut {cut_n} ships {shipped!r}, but the locked script line at this position is "
                            f"{script_slice[0]!r} — a rewritten/invented line, not a verbatim one"))
        elif tag == "delete":
            gaps.append(Gap("scene", str(sn), "dialogue verbatim", "BLOCK",
                            f"MISSING from the shipped beats — the script has {script_slice} with no matching "
                            f"cut anywhere in this scene (a dropped line, unless deliberately cut to wordless "
                            f"action — confirm before treating this as a bug, per this project's own T2 ruling "
                            f"that a deliberate creative cut is not the same as an accidental drop)"))
        elif tag == "insert":
            gaps.append(Gap("scene", str(sn), "dialogue verbatim", "BLOCK",
                            f"EXTRA/invented — {ship_slice} appear in the shipped beats with no corresponding "
                            f"script line anywhere in this scene"))
        else:   # an uneven replace block (a merge/split) — report both sides without over-claiming a 1:1 pairing
            gaps.append(Gap("scene", str(sn), "dialogue verbatim", "BLOCK",
                            f"TEXT DRIFT — script has {script_slice} where the shipped beats instead have "
                            f"{ship_slice} (not a clean 1:1 substitution, so no single 'expected line' can be "
                            f"named per beat — review both sides together)"))

    return gaps


def fix_scene_dialogue_verbatim(scene, scene_beats, script_scenes, log=print):
    """The MECHANICAL auto-fix for the check above — safe to apply automatically (zero LLM, zero creative
    judgment) for exactly the case the check itself calls unambiguous: a genuine 1:1 line REPLACE, where the
    diff can name a single script line that a single shipped cut should become, with no risk of misattributing
    content across a shift. Uses the SAME difflib alignment as check_scene_dialogue_verbatim, deliberately — an
    earlier version of this function used a naive positional zip, which (unlike the check, already fixed to use
    difflib) would have MISCORRECTED every beat after a legitimate drop/insert by force-shifting the wrong line
    onto the wrong cut; a fixer that's less precise than its own check is a real hazard, not just an inconsistency.
    Mutates `scene_beats` in place and returns how many cuts were corrected. Deliberately does NOT touch a
    delete/insert/uneven-replace finding — those need a human decision (was a line deliberately cut to wordless
    action, or genuinely dropped; where does an extra line belong), same as enforce_verbatim's own dropped-line
    path, which only force-appends as a last resort, never silently mid-scene."""
    import difflib, cb_script
    sn = scene.get("sceneNumber")
    script_scene = next((s for s in script_scenes if s.get("sceneNumber") == sn), None)
    if script_scene is None:
        return 0
    script_lines = cb_script.dialogue_lines([script_scene])
    ordered = sorted(scene_beats, key=lambda b: _beat_sort_key(b.get("beatCode") or b.get("shotCode")))
    slots = []   # the actual cut dicts, in order — mutated in place
    for b in ordered:
        for c in (b.get("cuts") or []):
            if (c.get("dialogue") or "").strip():
                slots.append(c)

    script_norm = [_norm_dialogue_words(f"{ch}: {ln}") for (_sn, ch, ln) in script_lines]
    ship_norm = [_norm_dialogue_words(c.get("dialogue")) for c in slots]
    sm = difflib.SequenceMatcher(None, script_norm, ship_norm, autojunk=False)

    fixed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace" and (i2 - i1) == (j2 - j1) == 1:
            cut = slots[j1]
            _, char, line = script_lines[i1]
            want = f"{char}: {line}"
            log(f"      ⋯ dialogue-verbatim fix: scene {sn} cut {cut.get('n')} → {char}: \"{line[:52]}\"", flush=True)
            cut["dialogue"] = want
            fixed += 1
        elif tag != "equal":
            log(f"      ⋯ dialogue-verbatim fix: scene {sn} — NOT auto-fixing a {tag} at script[{i1}:{i2}] / "
                f"shipped[{j1}:{j2}] (not a clean 1:1 line, needs a human decision).", flush=True)
    return fixed


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per character
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_characters_technical(all_beats):
    gaps = []
    cast = set()
    for b in all_beats:
        cast.update(b.get("characters") or [])
        cast.update(b.get("openingCast") or [])
    try:
        chars = json.load(open(CHARACTERS_PATH))
    except Exception:
        chars = {}
    for name in sorted(cast):
        entry = chars.get(name) or {}
        bible = entry.get("bible") or {}
        # RETIRED (Julian's ruling, 2026-07-06, THE FIDELITY LAW — "characters.json's actingRule field is
        # retired or becomes a pointer"): actingRule was a hand-condensed summary, not a verbatim quote from
        # the character's own store, and v5 no longer reads it at all. The real v5 source is actingNote
        # (pure movement/comedy, appearance-free — Fuzzby/Zenny) falling back to bible.mannerisms (the 9
        # bears) — see cb_segprompt._v5_acting_dna_source. A blank actingRule is no longer a gap; a missing
        # actingNote/mannerisms pair is.
        if _blank(entry.get("actingNote")) and _blank(bible.get("mannerisms")):
            gaps.append(Gap("character", name, "actingNote/mannerisms", "BLOCK",
                            "no movement-and-comedy register field found (actingNote or bible.mannerisms) — "
                            "required by the v5 engine's Acting DNA block (GATE3_ANIMATION_DOCTRINE.md §3) "
                            "for every character who appears"))
        # GATE3_ANIMATION_DOCTRINE.md §3 REVERSAL (2026-07-06, found on read): dos/donts no longer feed the
        # SHIPPED PROMPT at all ("Never in a prompt... writer-room guidance (dos/donts live at Gate 1 as
        # review criteria)") — v5's emitter does not read them. Still required here because Gate 1's own
        # review still needs them; a blank one is a Gate-1 data gap, not a Gate-3 compile blocker.
        if not (bible.get("dos") or []):
            gaps.append(Gap("character", name, "bible.dos", "BLOCK",
                            "the Always list — Gate-1 review criteria (GATE3_ANIMATION_DOCTRINE.md §3), not read by the v5 prompt"))
        if not (bible.get("donts") or []):
            gaps.append(Gap("character", name, "bible.donts", "BLOCK",
                            "the Never list — Gate-1 review criteria (GATE3_ANIMATION_DOCTRINE.md §3), not read by the v5 prompt"))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# TECHNICAL CONTRACT — per beat, THE V5 WORD BUDGET (Julian, 2026-07-06)
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
WORD_BUDGET_BLOCK = 650   # hard BLOCK — raised 2026-07-07 (rule 52) from 400
WORD_BUDGET_TARGET = 400  # flag-only target — raised 2026-07-07 (rule 52) from 250

def check_beat_word_count(beat, scene, is_scene_opener, prev_carry_marks, scene_beats=None, episode="Ep1"):
    """Hard BLOCK / target word budget (Julian, 2026-07-06, THE V5 ENGINE — "Hard 400-word BLOCK in
    preflight, 250 target, word count printed on every emit"; RAISED 2026-07-07, rule 52, Julian's own call
    after being shown the real numbers — "what do you think" — to 650/400: the 400/250 pair predates the
    shot-list restoration (rule 45, which already flagged beats "legitimately run[ning] into the 500s-600s")
    and decision 1's anti-hold-safe relay wording (+39 words on every relay beat before any beat-specific
    content) — both real, deliberate content additions, not bloat. The cap now reflects what a full
    continuity+performance beat actually costs, while still catching genuine runaway content: 1.B2's real
    572-word compile (2 characters, both relay fields authored, 2 delivery notes) has real headroom under
    the new cap rather than sitting 172 words over one calibrated for a lighter, pre-restoration prompt
    shape). Compiles THIS beat's actual v5 prompt the same way cb_beats.run/gate3_dryrun would at fire time
    (same relay/junction resolution — FIXED 2026-07-08, contradiction sweep: this used to derive relay from a
    cheap `not is_scene_opener` proxy rather than the real cb_scene.relay_source_for status every other call
    site uses, and was producing wrong word counts for real beats as a result) and counts its words — never
    a separate, hand-maintained estimate.
    WORD_BUDGET_BLOCK+ is a BLOCK; WORD_BUDGET_TARGET-BLOCK is a FLAG (still fireable, over the aspirational
    target); under TARGET is clean, reported as STRUCTURAL. A beat whose own data is too incomplete for the
    emitter to even compile (a missing carryMarks/actingDNA/storyBeat/endState) surfaces as its own named
    BLOCK here too, rather than silently skipping the word check."""
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    import cb_segprompt as CS, cb_qa
    # THE RELAY-PROXY FIX (found in the 2026-07-08 contradiction sweep): this used to derive relay from
    # `not is_scene_opener` — a cheap proxy that silently disagreed with cb_scene.relay_source_for (the real
    # production logic every other live call site uses, cb_beats.py/cb_qa.py), since a non-opener beat whose
    # predecessor has no rendered clip yet is status="no_predecessor_clip", NOT a relay. Confirmed live: this
    # was producing WRONG word-count FLAGs for 1.B3/1.B5 in the real preflight report (421/409 words under
    # the wrong relay=True assumption vs the true 372/360 under relay=False, today's actual predecessor
    # state). Now computed the same way cb_beats.run/gate3_dryrun/cb_qa.check_gate3_lint all do.
    relay = not is_scene_opener
    if scene_beats is not None:
        import cb_scene
        _, _relay_status, _ = cb_scene.relay_source_for(scene_beats, code, episode)
        relay = _relay_status == "relay"
    try:
        prompt, _builder, _is_def = CS.shipped_prompt(beat, scene, relay=relay,
                                                       prev_carry_marks=prev_carry_marks)
    except cb_qa.ManifestFieldMissing as e:
        return [Gap("beat", code, "v5 word count", "BLOCK", f"prompt could not be compiled — {e}")]
    wc = CS._v5_word_count(prompt)
    if wc > WORD_BUDGET_BLOCK:
        return [Gap("beat", code, "word count", "BLOCK", f"{wc} words — exceeds the {WORD_BUDGET_BLOCK}-word hard cap")]
    if wc > WORD_BUDGET_TARGET:
        return [Gap("beat", code, "word count", "FLAG", f"{wc} words — over the {WORD_BUDGET_TARGET}-word target (not gated)")]
    return [Gap("beat", code, "word count", "STRUCTURAL", f"{wc} words — within the {WORD_BUDGET_TARGET}-word target")]


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# CREATIVE CONTRACT — per beat, ENSEMBLE INDIVIDUATION (2026-07-07, THE PIXAR-CRAFT GATE, cb_craft.py)
#
# Deterministic, zero-LLM, so it belongs here alongside the rest of cb_preflight's cheap/local checks — the
# same "no vision/LLM calls" promise this module's own module docstring already makes. cb_craft.py's OTHER
# half, score_scene_craft (a real dual-read LLM call per scene), deliberately does NOT wire in here: it costs
# real API calls, and cb_preflight runs on every gate-arming check, potentially many times a session — the
# exact reason cb_qa's own vision checks (check_plate, check_clip) already live OUTSIDE this module, run at
# their own natural point instead. score_scene_craft is invoked explicitly (cb_craft.py's own CLI, or a future
# Studio button), never auto-triggered by a manifest check. This one IS auto-wired — it costs nothing.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_beat_ensemble(beat, characters):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    import cb_craft
    return [Gap("beat", code, "ensemble individuation", f["kind"], f["detail"])
            for f in cb_craft.check_ensemble_individuation(beat, characters)]


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# CREATIVE CONTRACT — per beat / per scene / per package
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def check_beat_creative(beat):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    gaps = []
    hl = beat.get("humourLayer")
    if hl is None:
        gaps.append(Gap("beat", code, "humourLayer", "BLOCK",
                        "NEW field (1-4), not yet authored anywhere — presence-only check, never a quality judgment "
                        "(whether the humour actually lands at that layer stays Julian's reserved verdict, rule 28)"))
    elif not (isinstance(hl, int) and 1 <= hl <= 4):
        gaps.append(Gap("beat", code, "humourLayer", "BLOCK", f"present but not an integer 1-4 ({hl!r})"))
    for f, label in (("kidRead", "kidRead"), ("adultRead", "adultRead"), ("want", "want"), ("need", "need")):
        if _blank(beat.get(f)):
            gaps.append(Gap("beat", code, label, "BLOCK", "required on every beat"))
    if _blank(beat.get("emotionMechanic")):
        gaps.append(Gap("beat", code, "emotionMechanic", "BLOCK",
                        "NEW field, not yet authored anywhere — presence-only check, same reserved-verdict caveat as humourLayer"))
    fa = beat.get("fidelityAllocation") or {}
    primary = str(fa.get("primary") or "").strip()
    if not primary or primary.lower() == "none":
        gaps.append(Gap("beat", code, "fidelityAllocation.primary", "BLOCK",
                        "THE FIDELITY-ALLOCATION LAW (2026-07-07) — required on every beat, must be an actual "
                        "character name, never blank/none; the code mechanically defaults it from speakers/cast "
                        "if the Director drops it (cb_director._finalize_beat_manifest_fields), so a BLOCK here "
                        "means even that fallback found nothing to work with"))
    elif not str(fa.get("secondary") or "").strip():
        gaps.append(Gap("beat", code, "fidelityAllocation.secondary", "BLOCK", "required — a name, or explicit \"none\""))
    elif not str(fa.get("economized") or "").strip():
        gaps.append(Gap("beat", code, "fidelityAllocation.economized", "BLOCK", "required — names, or explicit \"none\""))
    return gaps


def check_scene_creative(scene, scene_beats, pillar_mate_beats=None):
    """pillar_mate_beats: every beat across the WHOLE package sharing this scene's own pillar (including this
    scene's own beats) — FIXED 2026-07-07 (front-to-back audit, found live on Scene 2): the "laugh beat per
    non-Heart pillar" law (CRYSTAL_BEARS_LOCKED_CANON.md §2) is a PILLAR-level guarantee — the Five Emotional
    Pillars are TIMECODE segments of the whole episode, and more than one scene can share one (Scene 1 and
    Scene 2 both fall in "The Everyday Spark," 0:00-2:00). The check used to require a comedyMode=BIG beat in
    EVERY SCENE individually, which wrongly BLOCKed Scene 2 (a single quiet vision beat with no comedic
    content of its own) even though its own pillar-mate, Scene 1, already delivers five BIG comedy beats —
    the pillar's own laugh requirement was already met, just not by Scene 2 itself. Reclassifying Scene 2's
    pillar to dodge the check would have been dishonest (pillar is a timecode fact, not a content tag); the
    check itself was wrong to demand a redundant laugh in every scene sharing an already-satisfied pillar.
    Falls back to this scene's own beats only if the caller doesn't pass pillar-mates (keeps the function
    usable standalone, e.g. from a test or a single-scene tool)."""
    sn = str(scene.get("sceneNumber"))
    gaps = []

    fz = {"fuzzby": 0, "zenny": 0}
    for b in scene_beats:
        cast = [c.lower() for c in ((b.get("characters") or []) + (b.get("openingCast") or []))]
        if "fuzzby" in cast:
            fz["fuzzby"] += 1
        if "zenny" in cast:
            fz["zenny"] += 1
    if fz["fuzzby"] or fz["zenny"]:
        gaps.append(Gap("scene", sn, "Fuzzby/Zenny ratio", "FLAG",
                        f"computed {fz['fuzzby']}:{fz['zenny']} beats — no stated target ratio exists yet to pass/fail against"))

    pillar = str(scene.get("pillar") or (scene_beats[0].get("pillar") if scene_beats else "") or "").strip().lower()
    is_heart = "heart" in pillar
    if not is_heart:
        laugh_pool = pillar_mate_beats if pillar_mate_beats is not None else scene_beats
        has_laugh_beat = any(str(b.get("comedyMode") or "").upper() == "BIG" for b in laugh_pool)
        if not has_laugh_beat:
            gaps.append(Gap("scene", sn, "laugh beat per non-Heart pillar", "BLOCK",
                            f"pillar={pillar!r} (not Heart) but no beat anywhere in this pillar (this scene or "
                            f"its pillar-mates) has comedyMode=BIG"))

    if _blank(scene.get("parentLine")):
        gaps.append(Gap("scene", sn, "parentLine", "BLOCK", "NEW field, not yet authored anywhere"))

    return gaps


def check_package_creative(pkg):
    gaps = []
    if _blank(pkg.get("northStarAnswers")):
        gaps.append(Gap("package", "package", "northStarAnswers", "BLOCK",
                        "the North Star 'six questions' do not exist as a literal six anywhere in canon "
                        "(CRYSTAL_BEARS_LOCKED_CANON.md states 4 test questions + 8 craft laws) — field missing "
                        "AND the exact six questions need Julian's own definition before this check can mean "
                        "more than 'a field exists'"))
    return gaps


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE FULL RUN
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _load_script_scenes(episode, characters, log=print):
    """Parsed once per run() call, not per scene — cb_script.parse is cheap but there's no reason to repeat it
    10x. Returns (script_scenes, roster) or (None, roster) if no script file resolves / parsing fails, so a
    missing script degrades to a FLAG (check_scene_dialogue_verbatim reports it per scene) rather than crashing
    the whole preflight run."""
    roster = _script_roster(characters)
    path = _resolve_script(episode)
    if not path:
        log(f"  (no script file found for {episode} in {SCRIPTS_DIR} — dialogue-verbatim check will FLAG, not BLOCK)", flush=True)
        return None, roster
    try:
        import cb_script
        return cb_script.parse(open(path).read(), roster), roster
    except Exception as e:
        log(f"  (script parse failed for {episode}: {str(e)[:100]} — dialogue-verbatim check will FLAG, not BLOCK)", flush=True)
        return None, roster


def run(pkg_path, episode="Ep1", scene_filter=None, gate="1", log=print):
    """gate='1' (default): Gate 1's own manifest scope — everything except the scene plate (Stage 2, per
    Julian's 2026-07-06 ruling). gate='2' or later: the full manifest, plate included."""
    d = json.load(open(pkg_path))
    all_beats = d.get("beats") or d.get("shots") or []
    scenes = d.get("scenes") or []
    if scene_filter:
        all_beats = [b for b in all_beats if str(b.get("sceneNumber")) == str(scene_filter)]
        scenes = [s for s in scenes if str(s.get("sceneNumber")) == str(scene_filter)]

    try:
        characters = json.load(open(CHARACTERS_PATH)) if os.path.exists(CHARACTERS_PATH) else {}
    except Exception:
        characters = {}
    script_scenes, roster = _load_script_scenes(episode, characters, log=log)

    gaps = []
    by_scene = {}
    for b in all_beats:
        by_scene.setdefault(str(b.get("sceneNumber")), []).append(b)
    scene_by_sn = {str(s.get("sceneNumber")): s for s in scenes}
    for sn, beats in by_scene.items():
        # natural sort on the trailing beat number — NOT a plain string sort ("3.B10" < "3.B9" lexicographically,
        # the exact bug class cb_director.py's enforce_verbatim/_force_include already warn about and avoid).
        beats.sort(key=lambda b: _beat_sort_key(b.get("beatCode") or b.get("shotCode")))
        opener_code = beats[0].get("beatCode") or beats[0].get("shotCode")
        for i, b in enumerate(beats):
            code = b.get("beatCode") or b.get("shotCode")
            is_opener = (code == opener_code)
            gaps.extend(check_beat_technical(b, is_scene_opener=is_opener))
            gaps.extend(check_beat_creative(b))
            prev_marks = beats[i - 1].get("carryMarks") if i > 0 else None
            gaps.extend(check_beat_word_count(b, scene_by_sn.get(sn), is_opener, prev_marks,
                                               scene_beats=beats, episode=episode))
            gaps.extend(check_beat_ensemble(b, characters))

    # Pillar -> every beat across every scene sharing it (rule: the laugh-per-pillar law is pillar-scoped,
    # not scene-scoped — see check_scene_creative's own docstring).
    beats_by_pillar = {}
    for s in scenes:
        sn = str(s.get("sceneNumber"))
        beats = by_scene.get(sn, [])
        pillar = str(s.get("pillar") or (beats[0].get("pillar") if beats else "") or "").strip().lower()
        beats_by_pillar.setdefault(pillar, []).extend(beats)

    for s in scenes:
        sn = str(s.get("sceneNumber"))
        beats = by_scene.get(sn, [])
        pillar = str(s.get("pillar") or (beats[0].get("pillar") if beats else "") or "").strip().lower()
        gaps.extend(check_scene_technical(s, episode, gate=gate))
        gaps.extend(check_scene_creative(s, beats, pillar_mate_beats=beats_by_pillar.get(pillar)))
        if script_scenes is not None:
            gaps.extend(check_scene_dialogue_verbatim(s, beats, script_scenes, roster))
        else:
            gaps.append(Gap("scene", sn, "dialogue verbatim", "FLAG",
                            f"no parsed script available for {episode} — dialogue fidelity NOT verified this run"))

    gaps.extend(check_characters_technical(all_beats))
    if not scene_filter:
        gaps.extend(check_package_creative(d))

    return gaps, all_beats, scenes


def _beat_pass(code, gaps):
    return not any(g.kind == "BLOCK" and g.scope == "beat" and g.code == code for g in gaps)


def print_report(gaps, all_beats, scenes):
    blocks = [g for g in gaps if g.kind == "BLOCK"]
    flags = [g for g in gaps if g.kind == "FLAG"]
    structural = [g for g in gaps if g.kind == "STRUCTURAL"]

    print("=" * 100)
    print("THE MANIFEST — cb_preflight gap table (CLAUDE.md rule 37 / MANIFEST.md)")
    print("=" * 100)

    print(f"\n--- PER-BEAT PASS/FAIL ({len(all_beats)} beats) ---")
    codes = [b.get("beatCode") or b.get("shotCode") for b in all_beats]
    for code in codes:
        beat_gaps = [g for g in gaps if g.scope == "beat" and g.code == code]
        beat_blocks = [g for g in beat_gaps if g.kind == "BLOCK"]
        status = "PASS" if not beat_blocks else f"FAIL ({len(beat_blocks)} block{'s' if len(beat_blocks) != 1 else ''})"
        print(f"  {code}: {status}")
        for g in beat_gaps:
            if g.kind != "STRUCTURAL":
                print(f"      {g.line().strip()}")

    print(f"\n--- PER-SCENE ({len(scenes)} scenes) ---")
    for s in scenes:
        sn = str(s.get("sceneNumber"))
        scene_gaps = [g for g in gaps if g.scope == "scene" and g.code == sn]
        scene_blocks = [g for g in scene_gaps if g.kind == "BLOCK"]
        status = "PASS" if not scene_blocks else f"FAIL ({len(scene_blocks)} block{'s' if len(scene_blocks) != 1 else ''})"
        print(f"  scene {sn}: {status}")
        for g in scene_gaps:
            print(f"      {g.line().strip()}")

    char_gaps = [g for g in gaps if g.scope == "character"]
    if char_gaps:
        print(f"\n--- PER-CHARACTER ---")
        for g in char_gaps:
            print(f"  {g.line().strip()}")

    pkg_gaps = [g for g in gaps if g.scope == "package"]
    if pkg_gaps:
        print(f"\n--- PER-PACKAGE ---")
        for g in pkg_gaps:
            print(f"  {g.line().strip()}")

    print(f"\n--- SUMMARY BY FIELD (every gap named, rolled up) ---")
    by_field = {}
    for g in blocks + flags:
        by_field.setdefault((g.field, g.kind), []).append(f"{g.scope} {g.code}")
    for (field, kind), where in sorted(by_field.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
        print(f"  [{kind}] {field}: {len(where)} — {', '.join(where[:12])}{' ...' if len(where) > 12 else ''}")

    beats_pass = sum(1 for code in codes if _beat_pass(code, gaps))
    print(f"\n{'=' * 100}")
    print(f"TOTALS: {beats_pass}/{len(all_beats)} beats clean on both contracts. "
          f"{len(blocks)} BLOCK, {len(flags)} FLAG, {len(structural)} STRUCTURAL (already code-enforced, not re-checked).")
    print("No retakes, no fires until the package passes both manifests whole (Julian's ruling, 2026-07-06).")
    print("=" * 100)


def manifest_ok(pkg_path, scene=None, episode="Ep1", gate="1"):
    """THE CHOKE-POINT every gate-arming call site imports and calls before proceeding (MANIFEST.md's "Gate
    ordering in code"). Returns (ok: bool, block_count: int, gaps: list[Gap]) scoped to ONE scene if given,
    else the whole package. ok=True only when zero BLOCK-kind gaps exist in scope. gate='1' (default) is
    Gate 1's own scope (excludes the plate, Stage 2); pass gate='2' or later once a plate is expected to exist."""
    gaps, _, _ = run(pkg_path, episode=episode, scene_filter=scene, gate=gate)
    blocks = [g for g in gaps if g.kind == "BLOCK"]
    return (not blocks), len(blocks), gaps


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    episode = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--episode=")), "Ep1")
    scene_filter = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--scene=")), None)
    gate = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--gate=")), "1")
    pkg_path = args[0] if args else _resolve_pkg(episode)
    if not pkg_path or not os.path.exists(pkg_path):
        print("no production loaded — no beat package found in cb-output/")
        sys.exit(0)
    os.chdir(HERE)

    if "--preview-dialogue-fix" in sys.argv:
        # DRY RUN ONLY, deliberately — this module's own docstring promises "this tool only REPORTS — it never
        # fires, retakes, signs, or edits anything," so fix_scene_dialogue_verbatim (built + proven safe on a
        # scratch copy, per CLAUDE.md rule 48) is called here on an IN-MEMORY COPY that is never written back.
        # Found genuinely orphaned (zero call sites anywhere) by the 2026-07-07 contradiction-audit workflow —
        # this flag makes it a deliberately-invocable preview instead of dead code, without breaking the
        # report-only contract. Applying a fix for real is a separate, explicit action outside this tool.
        import copy
        d = json.load(open(pkg_path))
        beats = d.get("beats") or d.get("shots") or []
        scenes = d.get("scenes") or []
        if scene_filter:
            beats = [b for b in beats if str(b.get("sceneNumber")) == str(scene_filter)]
            scenes = [s for s in scenes if str(s.get("sceneNumber")) == str(scene_filter)]
        beats = copy.deepcopy(beats)
        by_scene = {}
        for b in beats:
            by_scene.setdefault(b.get("sceneNumber"), []).append(b)
        try:
            characters = json.load(open(CHARACTERS_PATH)) if os.path.exists(CHARACTERS_PATH) else {}
        except Exception:
            characters = {}
        script_scenes, _ = _load_script_scenes(episode, characters, log=lambda *a, **k: None)
        if script_scenes is None:
            print("no parsed script available — cannot preview a dialogue fix"); sys.exit(0)
        total = 0
        for s in scenes:
            total += fix_scene_dialogue_verbatim(s, by_scene.get(s.get("sceneNumber"), []), script_scenes, log=print)
        print(f"\n{total} cut(s) WOULD be corrected (preview only — the real package on disk is unchanged).")
        sys.exit(0)

    gaps, all_beats, scenes = run(pkg_path, episode=episode, scene_filter=scene_filter, gate=gate)
    print_report(gaps, all_beats, scenes)
    sys.exit(1 if any(g.kind == "BLOCK" for g in gaps) else 0)
