#!/usr/bin/env python3
"""cb_qa.py — the VISUAL continuity checker (the automated cameraman's eye).

The data checker (cb_continuity) validates the rules; the context audit (cb_context) proves everything is
pulled in. This one LOOKS AT THE RENDERED PIXELS: for each keyframe it sends the image + its locked
references (the SET master, character anchors, hero-item refs) to a vision model and asks a strict
continuity supervisor whether the render matches — set identical to the master, characters on-model,
items exactly as their reference. It catches the drifted pier / wrong cuff BEFORE Julian's eye does.

    python3 cb_qa.py [package.json] <scene>

DOCTRINE — every checklist item MUST state CONCRETE, LITERALLY-CHECKABLE visual criteria, never a subjective
question (Julian's Ruling, 2026-07-03). Worked example, ACTION_STATE_MISMATCH's first draft: asking "does this
pose read static, posed, standing still, or passively floating?" is a taste call a generous grader waves through
— it PASSED both of the known-bad 1.B1/1.B2 keyframes clean. Rewritten to ask two concrete things — are the wings
SYMMETRICAL (fail) or ASYMMETRIC/mid-downstroke (pass)? Is the body VERTICAL with legs dangling (fail) or LEANING
FORWARD into the direction of travel (pass)? — and it correctly failed both. Name the specific feature (an angle,
a count, a symmetry, a position) that separates a pass from a fail; never phrase an item as an open judgment call.
"""
import json, os, sys, struct, time, re, subprocess, tempfile, shutil, requests
import cb_gen, cb_prompts as P

class ManifestFieldMissing(Exception):
    """THE MANIFEST (CLAUDE.md rule 37, 2026-07-06 — 'remove every generic fallback; a missing field halts with
    the field named'): raised by prompt-authoring functions instead of silently substituting generic boilerplate
    for a beat's own missing TECHNICAL-contract field (endState, endStateStill, carryMarks, pauseHold, etc.).
    Callers (cb_beats.run/gate3_prepare) catch this as a hard BLOCK naming the field, distinct from a genuine
    emitter crash — a crash still falls back to an older builder; a missing manifest field never does."""
    def __init__(self, field, context=""):
        self.field = field
        self.context = context
        super().__init__(f"MANIFEST FIELD MISSING: {field}" + (f" ({context})" if context else ""))

VISION_MODEL = os.environ.get("CB_VISION_MODEL", "gemini-3.5-flash")   # 2026-07-06: earlier today this model
# returned a stable 403 PERMISSION_DENIED for this key's project (billing/access not yet enabled); Julian
# fixed access mid-session and it now returns a real 200 (confirmed live) — gemini-2.0-flash, the interim
# fallback used while blocked, has since been RETIRED by Google entirely (404 "no longer available") and is
# no longer a viable fallback at all. Override via CB_VISION_MODEL if this ever needs pinning again.
DONE_MIN_WIDTH = 2048   # 2K floor for a finished keyframe (Pro renders 2752 wide; the old flash 1376 fails this)
CLIP_MIN_WIDTH = 1280   # Seedance clips render 720p (1280x720) — the 2K keyframe floor would false-fail EVERY clip

def _img_size(path):
    """(width, height) for a PNG or JPEG, read from the header — no PIL. Returns (w,h) or None.
    (Gemini writes JPEG bytes into our .png files, so this must handle both.)"""
    try:
        with open(path, "rb") as f:
            sig = f.read(2)
            if sig == b"\x89P":                       # PNG: width/height at byte 16
                f.seek(16); return struct.unpack(">II", f.read(8))
            if sig != b"\xff\xd8":                     # not JPEG either
                return None
            while True:                                # JPEG: scan markers for the SOF (frame) segment
                byte = f.read(1)
                if not byte: return None
                if byte != b"\xff": continue
                m = f.read(1)
                while m == b"\xff": m = f.read(1)      # skip fill bytes
                if not m: return None
                mb = m[0]
                if mb in (0xD8, 0xD9) or 0xD0 <= mb <= 0xD7:  # SOI / EOI / RST — no length field
                    continue
                seg = f.read(2)
                if len(seg) < 2: return None
                ln = struct.unpack(">H", seg)[0]
                if mb in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):  # SOFn
                    f.read(1)                          # precision
                    h, w = struct.unpack(">HH", f.read(4))
                    return (w, h)
                f.seek(ln - 2, 1)                      # skip to next marker
    except Exception:
        return None
    return None

def _part(path):
    mime, data = cb_gen._b64(path)
    return {"inline_data": {"mime_type": mime, "data": data}}

def vision_verdict(prompt, images):
    parts = [{"text": prompt}] + [_part(p) for p in images if p and os.path.exists(p)]
    url = f"{cb_gen.GLA}/v1beta/models/{VISION_MODEL}:generateContent"
    last = "(no response)"
    for attempt in range(3):   # transient 429/500/503/timeout under load — back off + retry; NEVER report infra as a content fault
        try:
            r = requests.post(url, headers={"x-goog-api-key": cb_gen.GEMINI_KEY, "Content-Type": "application/json"},
                              json={"contents": [{"parts": parts}]}, timeout=120)
        except requests.exceptions.RequestException as e:
            last = f"(QA request error: {str(e)[:120]})"
            time.sleep(min(20, 4 * (2 ** attempt))); continue
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"], None
            except Exception as e:
                return None, f"(QA parse error: {e})"
        last = f"(QA model error {r.status_code}: {r.text[:120]})"
        if r.status_code not in (429, 500, 503):
            break
        time.sleep(min(20, 4 * (2 ** attempt)))
    return None, last

def check_anatomy(kf, characters):
    """Focused AI-ARTIFACT check (the continuity QA misses these): count each character's limbs/features and flag
    extra / missing / duplicated / merged / malformed parts. A separate pass — it does ONLY this. Returns {ok, verdict}."""
    if not os.path.exists(kf):
        return {"ok": None, "verdict": "(no keyframe)"}
    cast = ", ".join(characters) or "the characters"
    prompt = ("Look ONLY at the ANATOMY of each CHARACTER in this image — ignore the set, colour and style entirely. "
              f"Characters present: {cast}. For EACH one, carefully COUNT the arms, legs, paws/hands, wings, eyes and "
              "antennae. (Cartoon bees: one head, two eyes, two antennae, a pair of wings, two small arms, two small "
              "legs. Bears: two arms, two legs, one head.) Reply 'CLEAN' on line 1 if every character's anatomy is "
              "correct and complete; otherwise 'DEFECT' then ONE short line naming the exact problem (e.g. 'the left "
              "bee has an extra leg'). Be strict — extra, missing, duplicated, merged, fused or malformed limbs/digits/"
              "features are the failure we are hunting.")
    text, err = vision_verdict(prompt, [kf])
    if err:
        return {"ok": None, "verdict": err}
    return {"ok": text.strip().upper().startswith("CLEAN"), "verdict": text.strip()}

JUNCTION_INTENTIONAL = "intentional_next_shot"   # THE DEFAULT — a new gag arc, a fresh camera setup
JUNCTION_SEAMLESS = "seamless_continuation"       # ONLY when the director's own cut explicitly continues

def check_join_state(prev_end_frame, next_open_frame, carry_marks=None):
    """THE STATE-CONTINUITY GATE (Julian's junction-type ruling, CLAUDE.md rule 31, 2026-07-05; extended
    under rule 34, the Coverage Law, same day; STATE tier narrowed under rule 36, 2026-07-05 — "hand-held
    pollen is NOT a carry mark — incidental set dressing, audience-invisible across a cut") — the HARD GATE
    for EVERY join, cut or continuation. STATE now hard-gates ONLY on `carry_marks` — the beat's own
    DECLARED `carryMarks` text (never invented here, just passed through) — present in both frames or
    absent in both, never present in one and gone in the other; ANY OTHER visible prop, held object or
    substance (a bee casually holding pollen, say) is explicitly EXCLUDED from the hard gate and instead
    surfaces as an advisory `flags` entry — logged, never blocking. LIGHT, GEOGRAPHY and COVERAGE are about
    the WORLD's own continuity (not a declared prop) and stay unconditional hard gates, unaffected by this
    narrowing. This is the half of the old single check_join that survives unconditionally; POSITION/framing
    match moved to check_join_frame_identity below, which only applies to a declared `seamless_continuation`
    join. COVERAGE (rule 34) is DISTINCT from GEOGRAPHY: geography asks "is this the same world at all";
    coverage asks whether the beat's OWN opening reads as a continuation within that world (a new angle
    close to where the previous beat left off) rather than a fresh, pulled-back establishing wide or a
    sense of having relocated — "a scene is one continuous spatial bubble... never a relocation, never a
    fresh establishing wide mid-scene." Report-only / advisory, same as every other frame-level check in
    this module. Concrete visual criteria per rule 17 — never a vague "does this flow" question.
    Returns {ok, verdict, flags} — `flags` is a list of advisory-only notes (may be empty) that never affect
    `ok`, even if the model happens to mention them after a BROKEN verdict on another criterion."""
    if not (prev_end_frame and next_open_frame and os.path.exists(prev_end_frame) and os.path.exists(next_open_frame)):
        return {"ok": None, "verdict": "(missing end or open frame — cannot check this join)", "flags": []}
    marks_txt = str(carry_marks or "").strip()
    state_ask = (
        f'1. STATE (HARD GATE — ONLY this specific declared mark matters): does "{marks_txt}" persist between '
        "the two images — present in both or absent in both, not present in one and gone in the other? Judge "
        "ONLY this named mark. Do NOT fail this criterion for any OTHER visible prop, held object or substance "
        "not named above (e.g. a bee casually holding a bit of pollen in its hands) — that is incidental set "
        "dressing, not a continuity requirement, and must NEVER cause a BROKEN verdict on its own.\n"
        if marks_txt else
        "1. STATE (HARD GATE): no specific mark is declared for this beat, so treat STATE as automatically "
        "PASSING regardless of what temporary props/substances you see — do not fail on incidental set dressing "
        "(e.g. a bee casually holding pollen) with nothing formally declared to check it against.\n"
    )
    prompt = (
        "You are shown TWO film frames: Image 1 is the LAST frame of the shot that just ended; Image 2 is the "
        "FIRST frame of the very next shot — which may be a DIFFERENT camera setup (a new gag is allowed to open "
        "on a fresh angle; do not penalise a changed camera or pose by itself). Check four concrete things that "
        "must hold regardless of camera or pose:\n"
        + state_ask +
        "2. LIGHT: is the colour and brightness of the sky/environment roughly continuous (both warm/golden, or "
        "both a cooler dusk-blue, etc.) rather than one clearly warmer, cooler, brighter or darker than the other?\n"
        "3. GEOGRAPHY: is this visibly the SAME world/location — the same set, flowers, terrain and landmarks — "
        "not a different place entirely?\n"
        "4. COVERAGE: does Image 2 read as a new camera angle continuing WITHIN the same immediate space as Image "
        "1 (close to where the characters already were, a plausible next angle on the same patch of the world) — "
        "rather than a fresh, pulled-back ESTABLISHING WIDE that re-introduces the whole location from scratch, "
        "or a sense that the scene has relocated to a different part of the world entirely?\n"
        "Reply 'CONTINUOUS' on line 1 if all four hold (remembering STATE only concerns the ONE declared mark "
        "above, never any other incidental prop). Otherwise reply 'BROKEN' then ONE short line PER broken "
        "criterion, prefixed STATE/LIGHT/GEOGRAPHY/COVERAGE, naming exactly what changed (e.g. 'COVERAGE: image "
        "2 pulls back to a wide establishing shot instead of continuing close on the characters'). THEN, on its "
        "own final line prefixed EXACTLY 'FLAG:', note any OTHER visible prop/substance difference you noticed "
        "that is NOT the declared mark — for the record only, this NEVER changes the CONTINUOUS/BROKEN verdict "
        "above. If there is nothing else to note, write 'FLAG: none'."
    )
    text, err = vision_verdict(prompt, [prev_end_frame, next_open_frame])
    if err:
        return {"ok": None, "verdict": err, "flags": []}
    t = text.strip()
    flags = []
    m = re.search(r"^FLAG:\s*(.*)$", t, flags=re.MULTILINE | re.IGNORECASE)
    if m:
        note = m.group(1).strip()
        if note and note.lower() not in ("none", "none.", "n/a"):
            flags.append(note)
        t = t[:m.start()].rstrip()   # the FLAG line is advisory-only — strip it before judging CONTINUOUS/BROKEN
    return {"ok": t.strip().upper().startswith("CONTINUOUS"), "verdict": t.strip(), "flags": flags}

def check_join_frame_identity(prev_end_frame, next_open_frame):
    """THE FRAME-IDENTITY CHECK — a `seamless_continuation` join ONLY (rule 31): does beat N+1's opening
    frame literally match beat N's ending frame — same screen position/scale per character, same camera
    framing? This is the half of the old single check_join that an `intentional_next_shot` join (the
    default) is no longer held to — a cut is EXPECTED to open on a different camera setup; only a beat
    that declares its shot continues unbroken owes this match. Report-only / advisory, concrete criteria
    per rule 17."""
    if not (prev_end_frame and next_open_frame and os.path.exists(prev_end_frame) and os.path.exists(next_open_frame)):
        return {"ok": None, "verdict": "(missing end or open frame — cannot check this join)"}
    prompt = (
        "You are shown TWO consecutive film frames of an UNBROKEN, single continuing shot: Image 1 is the LAST "
        "frame before the cut; Image 2 is the FIRST frame after it, meant to be the SAME instant continuing. "
        "Check: is each character in the SAME screen half (left/right), at a similar apparent size/distance from "
        "camera and in essentially the SAME pose/framing as in Image 1 — not swapped sides, not suddenly closer "
        "or farther away, not a different camera angle?\n"
        "Reply 'CONTINUOUS' on line 1 if this holds. Otherwise reply 'BROKEN' then ONE short line naming exactly "
        "what changed (e.g. 'the larger bee was frame-left, now frame-right' or 'the camera angle changed')."
    )
    text, err = vision_verdict(prompt, [prev_end_frame, next_open_frame])
    if err:
        return {"ok": None, "verdict": err}
    return {"ok": text.strip().upper().startswith("CONTINUOUS"), "verdict": text.strip()}

def check_join(prev_end_frame, next_open_frame, junction=JUNCTION_INTENTIONAL, carry_marks=None):
    """THE JOIN CHECK, TWO-TIER (Julian's junction-type ruling, CLAUDE.md rule 31, 2026-07-05 — supersedes
    the single POSITION/STATE/LIGHT check this function ran from the original JOIN CONTRACT, 2026-07-03):
    STATE CONTINUITY (check_join_state — declared carry marks only as of rule 36, plus lighting, geography,
    coverage) is the hard gate for EVERY join, no exceptions. FRAME IDENTITY (check_join_frame_identity —
    does the opening frame literally match the settle) is checked ONLY when junction == 'seamless_continuation';
    an 'intentional_next_shot' join (the default — pass nothing, or an unrecognised value, and this is what
    runs) is never held to it, since a new gag arc is expected to open on a different camera setup.
    carry_marks (rule 36, 2026-07-05): the beat's own declared `carryMarks` text — the ONLY thing STATE
    hard-gates on; any other visible prop discrepancy surfaces as an advisory flag instead (see `flags`).
    Returns {ok, verdict, state, frame_identity, flags} — frame_identity is None (not applicable) for an
    intentional_next_shot join, so a caller can tell "not checked" from "checked and passed"; flags is
    check_join_state's advisory-only notes, never affecting `ok`."""
    state = check_join_state(prev_end_frame, next_open_frame, carry_marks=carry_marks)
    frame_identity = check_join_frame_identity(prev_end_frame, next_open_frame) if junction == JUNCTION_SEAMLESS else None
    ok = state["ok"] if frame_identity is None else (state["ok"] and frame_identity["ok"])
    parts = [f"STATE: {state['verdict']}"]
    if frame_identity is not None:
        parts.append(f"FRAME-IDENTITY: {frame_identity['verdict']}")
    return {"ok": ok, "verdict": " | ".join(parts), "state": state, "frame_identity": frame_identity,
            "flags": state.get("flags") or []}

def check_remint(harvested_path, remint_path, turnaround_paths=None):
    """THE RE-MINT DRIFT CHECK (Julian's ruling, 2026-07-03) — the re-mint's only job is a technical cleanup pass
    (compression artifacts, motion blur), never a restage or a redesign. Checks the re-minted frame against the
    HARVESTED frame for POSITION and STATE match, and against the character TURNAROUNDS for IDENTITY match. A
    hit is a hard BLOCK — concrete criteria per rule 17, never a vague "does this still look right" call."""
    if not (harvested_path and remint_path and os.path.exists(harvested_path) and os.path.exists(remint_path)):
        return {"ok": None, "verdict": "(missing harvested or re-minted frame — cannot check)"}
    turnarounds = [p for p in (turnaround_paths or []) if p and os.path.exists(p)]
    prompt = (
        "Image 1 is a HARVESTED frame from an animated take. Image 2 is the SAME frame after a cleanup pass meant "
        "ONLY to remove compression artifacts and motion blur — never to restage or redesign anything.\n"
        "1. POSITION: is each character in the SAME screen half (left/right), the same apparent size/distance, "
        "the same pose and body angle in both images — not moved, not restaged, not reframed?\n"
        "2. STATE: does any visible temporary substance or prop on a character (pollen dusting, dirt, a held "
        "object) match exactly between the two images — nothing added, removed or changed?\n"
        + (f"The remaining {len(turnarounds)} image(s) are the characters' locked identity turnarounds.\n"
           "3. IDENTITY: does each character in Image 2 still match its own turnaround exactly — face, markings, "
           "proportions — with no drift toward a different design?\n" if turnarounds else "") +
        "Reply 'CLEAN' on line 1 if everything holds. Otherwise reply 'DRIFT' then ONE short line PER broken "
        "criterion, prefixed POSITION/STATE/IDENTITY, naming exactly what changed."
    )
    text, err = vision_verdict(prompt, [harvested_path, remint_path] + turnarounds)
    if err:
        return {"ok": None, "verdict": err}
    return {"ok": text.strip().upper().startswith("CLEAN"), "verdict": text.strip()}

# ── PROMPT LAWS AUDIT (PROMPT_LAWS_AUDIT.md, CLAUDE.md rule 28) — flag-only authoring checks ──────────
# Three of the twelve Layer-1 invariant laws were found CONVENTION-ONLY, not code-enforced: Law 4 (the @图1
# content clause must read as a photograph, never directing prose), Law 7 (the locked ambient bed must never
# be restated inside any other field) and Law 8 (camera stays locked on any dialogue shot; one primary move
# per shot otherwise). Each of these is the SAME shape of bug as rule 27's temporal-contradiction find — two
# statements in one prompt that can quietly disagree, because nothing checks a hand-authored field against
# the law stated right next to it. Deterministic keyword/overlap scans, no vision call, no LLM: cheap enough
# to run on every beat before it fires. Advisory only, per Julian's ruling (2026-07-04) — flag, never block;
# wired into cb_beats.render_readiness() as a non-blocking "flags" list.
_TEMPORAL_MARKERS = (
    "end on", "ends on", "ending on", "holds it", "holding it", "held it", "resumes", "resume", "resuming",
    "begins to", "begin to", "starts to", "start to", "straightens into", "settles into", "settling into",
    "camera locked", "then he", "then she", "then they", "after a beat", "before snapping", "snaps back",
    "and holds", "one blink too long",
)
def check_endstate_still(text):
    """LAW 4 DETECTOR — endStateStill must be a static PICTURE description (subjects, poses, positions,
    expressions, setting), never directing prose with temporal verbs or imperatives — that leak is exactly
    what rule 27 found and fixed once already (endState pasted verbatim into @图1's content clause). This
    can't rewrite the prose the way Julian's own worked example does (rule 27 already rejected a mechanical
    transform) — it only detects and flags, so a violation is never shipped un-reviewed."""
    t = str(text or "").strip()
    if not t:
        return {"ok": True, "verdict": "(no endStateStill authored yet)"}
    hits = [m for m in _TEMPORAL_MARKERS if m in t.lower()]
    if hits:
        return {"ok": False, "verdict": f"endStateStill reads like directing prose, not a photograph — "
                f"temporal/imperative language found: {', '.join(hits)}"}
    return {"ok": True, "verdict": "static picture description, no temporal markers found"}

def check_ambience_overlap(atmosphere, ambient_bed):
    """LAW 7 DETECTOR — the beat's own `atmosphere` text must never restate the scene's locked `ambientBed`
    line (the bed is the constant every beat shares word-for-word; per-beat atmosphere/soundIntent is what's
    supposed to change). Same bug CLASS as rule 27's endState/ambience duplication, a different field pair
    that nothing currently guards. Word-overlap heuristic against the FIRST sentence of atmosphere (the same
    slice _v3_environment actually ships, cb_segprompt.py's `atmo` clause) — deterministic, no vision call."""
    a = str(atmosphere or "").strip()
    bed = str(ambient_bed or "").strip()
    if not a or not bed:
        return {"ok": True, "verdict": "(nothing to compare — atmosphere or ambientBed not authored yet)"}
    first = re.split(r"(?<=[.!?])\s+", a)[0]
    def _words(s):
        return [w for w in re.findall(r"[a-z']+", s.lower()) if len(w) > 3]
    bed_words, atmo_words = set(_words(bed)), _words(first)
    if not bed_words or not atmo_words:
        return {"ok": True, "verdict": "(too short to compare)"}
    shared = sorted({w for w in atmo_words if w in bed_words})
    ratio = len(shared) / len(bed_words)
    if ratio >= 0.4:
        return {"ok": False, "verdict": f"beat's atmosphere text overlaps {ratio:.0%} of the scene's locked "
                f"ambientBed wording ({', '.join(shared)}) — restating the bed inside `world` duplicates "
                f"`ambience`; keep atmosphere to what's NEW this beat"}
    return {"ok": True, "verdict": f"atmosphere/ambientBed word overlap {ratio:.0%} — no restatement"}

_CAMERA_MOVE_WORDS = ("push", "pushes", "pushing", "pan", "pans", "panning", "dolly", "dollies", "truck",
                      "trucks", "zoom", "zooms", "zooming", "orbit", "orbits", "orbiting", "whip", "tilt",
                      "tilts", "crane", "cranes", "tracks", "tracking", "sweeps", "sweeping", "swings",
                      "swinging", "chases", "chasing", "drifts", "drifting")
_MOTION_EXEMPT_VOCAL_RE = re.compile(r"\b(hum|hums|humming|sing-song|singsong)\b", re.IGNORECASE)
def _is_motion_exempt_vocal(cut):
    """CAMERA LAW AMENDMENT (Julian's ruling, 2026-07-06, Gate 1 review of 1.B1): Law 8's camera lock applies
    to SPOKEN LINES only — a continuous hum or sing-song vocalization has no shaped mouth performance that
    needs a static frame to read clearly, so it is motion-exempt. Detected from the cut's OWN authored
    `delivery`/`voiceTreatment` text naming it as such (e.g. "fun sing-song rhythm... the hum rising with
    speed") — never inferred from the dialogue text itself (a repeated-syllable heuristic would be exactly
    the kind of fragile, vibes-based signal rule 17 rejects for vision checks; this is the same principle
    applied to a text lint: only a concrete, hand-declared marker counts)."""
    text = f"{cut.get('delivery') or ''} {cut.get('voiceTreatment') or ''}"
    return bool(_MOTION_EXEMPT_VOCAL_RE.search(text))

def check_camera_lock_conflict(beat):
    """LAW 8 DETECTOR — camera must be locked/static on any cut with a SPOKEN line (the beat-level `rule`
    field already states this, per _v3_rule); at most one primary camera-movement per shot otherwise. A cut
    whose dialogue is a hum/sing-song vocalization (per its own delivery/voiceTreatment text — see
    `_is_motion_exempt_vocal`) is exempt from the lock, per Julian's 2026-07-06 ruling. Nothing currently
    checks a dialogue cut's own authored `framing` text against the law stated right next to it in the
    shipped prompt — the same two-statements-can-disagree shape as rule 27's bug, in the camera field
    instead of the content-description field. Deterministic keyword scan over the beat's own cuts, no vision
    call — runs at authoring time, before the emitter ever sees the beat."""
    flags = []
    for i, c in enumerate(beat.get("cuts") or [], start=1):
        framing = str(c.get("framing") or "")
        has_dlg = bool(str(c.get("dialogue") or "").strip()) and not _is_motion_exempt_vocal(c)
        moves = [w for w in _CAMERA_MOVE_WORDS if re.search(r"\b" + re.escape(w) + r"\b", framing.lower())]
        if has_dlg and moves:
            flags.append(f"cut {i}: has dialogue but framing names camera movement ({', '.join(moves)}) — "
                         f"contradicts the beat's own camera-locked-during-dialogue rule")
        elif len(moves) > 1:
            flags.append(f"cut {i}: framing names {len(moves)} distinct camera moves ({', '.join(moves)}) — "
                         f"Law 8 wants one primary move per shot")
    if flags:
        return {"ok": False, "verdict": "; ".join(flags)}
    return {"ok": True, "verdict": "no camera-lock conflicts found"}

def check_settle_distinctiveness(this_end_state, prev_end_state):
    """SETTLE-AUTHORING STRENGTHENING (Julian's ruling, 2026-07-05, lock-in night — "every beat's settle
    must be written as that beat's OWN distinct moment in character... never a restatement of the previous
    beat's pose"): found watching 1.B2's first intentional-cut render, which drifted back toward
    reproducing 1.B1's own anchor pose at the settle instead of performing its own scripted ending. A word-
    overlap heuristic (same style as check_ambience_overlap) between THIS beat's own `endState` and the
    PREVIOUS beat's `endState` — high overlap signals the AUTHORED settle risks reading as a restatement,
    not a distinct moment, before it ever reaches the model. Cannot detect the render-time drift itself
    (that's a generation-time outcome, same limitation as Law 5's anti-hold) — only guards the data that
    feeds it. Advisory only, flag-only per the established Laws 4/7/8 pattern; never invents a rewrite, only
    detects and names the overlap."""
    this_es = str(this_end_state or "").strip()
    prev_es = str(prev_end_state or "").strip()
    if not this_es or not prev_es:
        return {"ok": True, "verdict": "(nothing to compare — this beat or its predecessor has no endState authored yet)"}
    def _words(s):
        return [w for w in re.findall(r"[a-z']+", s.lower()) if len(w) > 3]
    this_words, prev_words = set(_words(this_es)), set(_words(prev_es))
    if not this_words or not prev_words:
        return {"ok": True, "verdict": "(too short to compare)"}
    shared = sorted(this_words & prev_words)
    ratio = len(shared) / min(len(this_words), len(prev_words))
    if ratio >= 0.5:
        return {"ok": False, "verdict": f"this beat's endState overlaps {ratio:.0%} of its predecessor's own "
                f"wording ({', '.join(shared)}) — risks reading as a restatement of the previous beat's pose "
                "rather than this beat's own distinct settle moment"}
    return {"ok": True, "verdict": f"endState word overlap with predecessor {ratio:.0%} — reads as its own moment"}

# THE UNIFIED STEP 4 LINT (GATE3_ANIMATION_DOCTRINE.md §1 Step 4, 2026-07-06 — "The compiled prompt is
# checked before money moves... Fail = the prompt never fires. Fix at data, recompile.") — REPLACES the
# old twelve-Layer-1-law lint (`check_prompt_laws`, retired the same day): that function checked v3/v4-era
# concepts (`endStateStill`'s Law 4, `atmosphere`-vs-`ambientBed` overlap for Law 7) and its own "structural"
# dict named functions already deleted from cb_segprompt.py (`_v3_shots`, `_v3_settle`, `_v3_negatives`) —
# stale documentation of a retired emitter, not a real check of what v5 actually ships. `check_endstate_still`/
# `check_ambience_overlap` below is KEPT (not deleted — a full manifest-field audit against the new doctrine
# is a separate, larger task, out of scope for this pass) but is no longer called by anything; a future
# ticket should determine whether `endStateStill`/`atmosphere` still belong in the TECHNICAL contract at all
# now that v5 doesn't read either field. `check_camera_lock_conflict` was ALSO left disconnected here —
# found and RE-WIRED into check_gate3_lint itself in the 2026-07-08 software-wide sign-off audit (see its
# own call site, item 1.6, below) — it is live again, not merely kept for the record.
_NEGATION_RE = re.compile(r"\b(no|not|never|don't|doesn't|didn't|won't|isn't|aren't|can't|cannot)\b", re.IGNORECASE)

# THE ANTI-SLOP LEXICON (2026-07-07, mined from "Seedance Prompt Engine," a reference tool built on the same
# seedance-20 skill doctrine this project already draws on): generic AI-video filler words that name no
# observable production detail — the rule that earns a word's place here is "if a camera, microphone, light
# meter, or stopwatch cannot detect it, rewrite it as the one concrete thing that does." Found immediately
# useful the day it was built: the v5 tech-close line's own locked constant ("smooth cinematic motion") tripped
# this list — a real, honest finding surfaced by the check, not silently exempted. THAT specific source is
# retired (rule 54, 2026-07-08 — the whole standalone tech line is gone, fps folded into the HEADER instead),
# but the flag still fires from a second locked constant, the style law's own "cinematic lighting" — see
# check_gate3_lint's own scoping (BLOCK in freely-authored prose, FLAG only where a locked constant/style law
# is the source, since only Julian's own edit can rewrite those).
ANTI_SLOP_WORDS = ["cinematic", "epic", "stunning", "beautiful", "dramatic", "dynamic", "magical",
                   "ultra-realistic", "masterpiece", "award-winning", "8K", "high quality", "trending",
                   "atmospheric", "breathtaking", "insanely detailed", "visually striking"]
_ANTI_SLOP_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in ANTI_SLOP_WORDS) + r")\b", re.IGNORECASE)

def check_character_vocabulary(beat):
    """THE CHARACTER VOCABULARY LAW (Julian's ruling, 2026-07-06 — "every verb and adverb in every beat,
    action and camera alike, is drawn from that character's own register... the camera inherits the
    register of whoever it covers... readability enforced by 'readable at speed,' never by softening"):
    each character's `characters.json` entry carries a locked `lexicon` (`verbs` it owns, `banned` words
    that must never appear near its action) — e.g. Fuzzby's is chases/whips/banks/barrels/dives/snaps/
    rockets, banned gently/slowly/softly/calm/careful; Zenny's own stillness words (which happen to
    overlap Fuzzby's banned list) are HER register, never banned for her, only ever banned from crossing
    into HIS action or the camera when it covers him.

    ATTRIBUTION HEURISTIC (stated plainly, not hidden): a cut's action+framing text is checked against a
    character's banned list whenever that character's NAME appears in the same cut's text — this is a
    real, coarse heuristic (a cut naming both characters checks both lists against the same combined
    text), not a grammatical-subject parse. It is what caught the two real, confirmed violations in
    1.B1's own cuts 1-2 live (camera covering Fuzzby's zig-zag/dive described as "gently tracks"); it can
    also flag a genuinely mixed or atmospheric two-shot (e.g. a shared reaction beat) that isn't really
    "covering" either character's action in the chase/deadpan sense the law describes — those get
    reported the same as any other flag, for a human to read and judge, never silently suppressed or
    silently auto-corrected.

    Returns {ok, violations: [{cut, character, word, text}]} — ok is False whenever any cut contains a
    banned word for a character actually named in that same cut."""
    import cb_segprompt as CS
    violations = []
    for i, c in enumerate(beat.get("cuts") or [], 1):
        text = f"{c.get('framing') or ''} {c.get('action') or ''}"
        low = text.lower()
        for name in (beat.get("openingCast") or beat.get("characters") or []):
            if name.lower() not in low:
                continue
            # FIXED 2026-07-08 (contradiction sweep): was CS._CHARS (a snapshot frozen at cb_segprompt's own
            # import time, never re-read) — cb_director.py/cb_craft.py/cb_preflight.py all reload
            # characters.json fresh on every call; this module was the one silently stale outlier, risking
            # enforcement against an out-of-date lexicon in any long-lived process that edits the file
            # mid-session. CS._load_chars() is the same loader, called fresh here instead.
            lex = (CS._load_chars().get(name) or {}).get("lexicon") or {}
            for banned in (lex.get("banned") or []):
                if re.search(rf"\b{re.escape(banned)}\b", text, re.IGNORECASE):
                    violations.append({"cut": i, "character": name, "word": banned, "text": text.strip()})
    return {"ok": not violations, "violations": violations}

def check_keyframe_lint(prompt, chars=None):
    """THE GATE-2 SIBLING OF check_gate3_lint (found missing 2026-07-08 software-wide fix batch): every clip
    prompt (v5, cb_segprompt) is linted for the anti-slop lexicon and the Character Vocabulary Law before it
    fires; the KEYFRAME prompt (cb_prompts.build_keyframe_prompt) — the very first thing rendered for a beat,
    and the seed every relay/re-mint frame downstream inherits — had neither check wired in at all. Zero-cost,
    text-only (no vision call), matching check_gate3_lint's own design: called on the ALREADY-COMPILED prompt
    string, never a separate re-authoring step.

    Scoping (deliberately more precise than check_gate3_lint's own whole-cut heuristic for the vocabulary law):
    build_keyframe_prompt's body joins one `CHARACTER N (Name): ...` paragraph per in-frame character (its own
    `blocks` list, one entry per character) via blank-line joins — so a paragraph beginning "CHARACTER N (Name):"
    is unambiguously THAT character's own freely-authored action/pose text, and only that paragraph's own banned
    words are checked against that same name (no cross-attribution risk between two characters named in the
    same beat, unlike the coarse whole-cut match rule 49 already flagged for check_character_vocabulary).

    Anti-slop severity mirrors check_gate3_lint's own locked-vs-authored split: a hit inside a CHARACTER
    paragraph (freely-authored per-beat prose) is a hard BLOCK; a hit anywhere else (STYLE/REFERENCE IMAGES/
    CONSTRAINTS — largely locked template wording, e.g. STYLE's own "cinematic depth of field") is FLAG-only,
    since only a source edit — not a beat rewrite — could remove it.

    Returns {ok, blockers, flags}. ok=False means this keyframe prompt must never fire as-is."""
    import cb_segprompt as CS
    blockers, flags = [], []
    paras = re.split(r"\n\n+", prompt or "")
    char_para_re = re.compile(r"^CHARACTER\s+\d+\s+\(([^)]+)\):")
    for para in paras:
        m = char_para_re.match(para.strip())
        owner = m.group(1).strip() if m else None
        hits = _ANTI_SLOP_RE.findall(para)
        if hits:
            uniq = sorted(set(h.lower() for h in hits))
            if owner:
                blockers.append(f"anti-slop word(s) in {owner}'s character paragraph: {', '.join(uniq)}")
            else:
                flags.append(f"anti-slop word(s) in locked/template text: {', '.join(uniq)}")
        if owner and (chars is None or owner in chars):
            lex = (CS._load_chars().get(owner) or {}).get("lexicon") or {}
            for banned in (lex.get("banned") or []):
                if re.search(rf"\b{re.escape(banned)}\b", para, re.IGNORECASE):
                    blockers.append(f"Character Vocabulary Law: {owner}'s keyframe paragraph uses {banned!r} "
                                     f"— outside {owner}'s locked register")
    return {"ok": not blockers, "blockers": blockers, "flags": flags}

def check_gate3_lint(pkg_path, beat_code, episode="Ep1"):
    """THE single Step-4 gate: compiles this beat's actual v5 prompt (cb_segprompt.shipped_prompt, the exact
    call cb_beats.run makes) and checks it before anything fires. Returns {ok, blockers, flags, citations,
    word_count, prompt}. ok=False means the prompt must never fire — "fix at data, recompile," never a hand
    patch to the returned prompt text.
    Checks: (1) word budgets — 400 hard, 250 target (flag), the beat-story block's own 80-word fence
    (re-derived independently of emit_v5's internal truncation, so a future emitter bug can't silently ship
    an over-length story block). (2) banned vocabulary, against the SHIPPED TEXT directly (complements
    cb_preflight's source-field check, which reads the beat's own authored fields, not the compiled prompt).
    (3) Law 5 — no actual dialogue words leak into the text. (4) no appearance-prose leak — a character's
    own short `markers` field (its canonical visual tell, e.g. Fuzzby's "round wire-frame glasses") must
    never appear outside the cited Acting DNA block; flag-only (some legitimate action words legitimately
    overlap with markers text, e.g. "wings"), never a hard block, since only Julian's own bible edit can fix
    a genuine leak (THE FIDELITY LAW). (5) no leftover speed adjectives (verifies `_v5_strip_speed_adjectives`
    actually ran clean — a regression guard, not a new rule). (6) no negation outside the Negative line — the
    Acting DNA and Beat Story blocks are EXEMPT (they quote/derive from real authored content that may
    legitimately contain natural negation, e.g. Fuzzby's own bible: "he does NOT inflate his whole body");
    checked only in the purely mechanical blocks (header, style, references, camera/ambience, tech line) that
    should never need it. (7) structural congruence with §4a/§4b's exact reference-block wording. (8) a
    citation map — which store field every block's content traces to — for the record, per THE FIDELITY LAW
    ("every content line traces to a cited source"). (9) THE ANTI-SLOP LEXICON (2026-07-07, mined from a
    seedance-20-doctrine-derived reference tool Julian shared, "Seedance Prompt Engine") — generic AI-video
    filler words (cinematic, stunning, masterpiece, 8K...) that name no observable production detail at all;
    hard-BLOCKED in the Beat Story block (freely-authored dynamic prose, no ruling stands behind a slop word
    there), FLAG-only everywhere else (the style law is a locked constant only Julian's own edit can amend —
    see ANTI_SLOP_WORDS's own module comment for why the style law's "cinematic lighting" already trips
    this; the standalone tech line that used to be the OTHER source of this same flag was retired 2026-07-08,
    rule 54)."""
    import cb_segprompt as CS, cb_scene
    d = json.load(open(pkg_path))
    all_beats = d.get("beats") or d.get("shots") or []
    beat = next((b for b in all_beats if (b.get("beatCode") or b.get("shotCode")) == beat_code), None)
    if beat is None:
        return {"ok": False, "blockers": [f"beat {beat_code} not found in package"], "flags": [],
                "citations": {}, "word_count": 0, "prompt": ""}
    scene = next((s for s in (d.get("scenes") or []) if str(s.get("sceneNumber")) == str(beat.get("sceneNumber"))), None)
    cast = beat.get("openingCast") or beat.get("characters") or []
    scene_beats = [b for b in all_beats if str(b.get("sceneNumber")) == str(beat.get("sceneNumber"))]
    _, relay_status, _ = cb_scene.relay_source_for(scene_beats, beat_code, episode)
    relay = relay_status == "relay"

    blockers, flags = [], []
    try:
        prompt, _builder, _is_def = CS.shipped_prompt(beat, scene, relay=relay)
    except ManifestFieldMissing as e:
        return {"ok": False, "blockers": [f"prompt could not compile — {e}"], "flags": [],
                "citations": {}, "word_count": 0, "prompt": ""}
    if not str(prompt or "").strip():
        return {"ok": False, "blockers": ["compiled prompt is empty"], "flags": [],
                "citations": {}, "word_count": 0, "prompt": ""}

    # (1) word budgets — RAISED 2026-07-07 (rule 52, Julian's own call): 400/250 predated the shot-list
    # restoration (rule 45) and decision 1's anti-hold-safe relay wording (+39 words on every relay beat).
    import cb_preflight as PF
    wc = CS._v5_word_count(prompt)
    if wc > PF.WORD_BUDGET_BLOCK:
        blockers.append(f"word budget: {wc} words exceeds the {PF.WORD_BUDGET_BLOCK}-word hard cap")
    elif wc > PF.WORD_BUDGET_TARGET:
        flags.append(f"word budget: {wc} words over the {PF.WORD_BUDGET_TARGET}-word target")
    # the shot-list block's own 80-word sub-fence is RETIRED (Julian's ruling, 2026-07-06 — a real per-cut
    # shot list needs room for camera + action per cut); the whole-prompt 400-word cap above is the real
    # backstop now. Still re-derive it here so a missing cuts[]/endState surfaces as a named BLOCK.
    try:
        CS._v5_beat_story(beat, cast)
    except ManifestFieldMissing as e:
        blockers.append(f"shot-list block could not be re-derived — {e}")

    # (1.5) THE CHARACTER VOCABULARY LAW (Julian, 2026-07-06) — every character's action/camera-coverage
    # text must draw its verbs from that character's own locked lexicon; a banned word (another
    # character's softer register bleeding into this one's action) is a hard BLOCK, checked against the
    # beat's own authored cuts (the source, not the compiled text — the compiled shot list is a near-
    # verbatim quote of the same words anyway).
    cv = check_character_vocabulary(beat)
    for v in cv["violations"]:
        blockers.append(f"Character Vocabulary Law: cut {v['cut']} uses {v['word']!r} near {v['character']} "
                         f"— outside {v['character']}'s locked register")

    # (1.6) THE CAMERA-LOCK LAW (rule 28 Layer 1 Law 8 / rule 38) — found DISCONNECTED in the 2026-07-08
    # software-wide sign-off audit: check_camera_lock_conflict was built (2026-07-02) and correctly detects
    # a dialogue cut whose own framing names camera movement, but nothing ever called it once the twelve-
    # law lint that used to own this check (check_prompt_laws) was retired the same day the unified Step-4
    # lint (this function) replaced it — the law itself was never re-wired into the replacement. Confirmed
    # live: 1.B2's real compiled prompt has NO stated camera-lock-during-dialogue instruction anywhere (the
    # law used to live in the now-retired tech-line CLOSER, rule 54) and its own Shot 2 names a reveal move
    # on a dialogue cut — exactly what this check exists to catch. A hard BLOCK, matching the severity of
    # every other doctrine-backed check in this function (Law 5, the Vocabulary Law) — this is a stated HARD
    # RULE (CLAUDE.md rule 28), not a style preference.
    clc = check_camera_lock_conflict(beat)
    if not clc["ok"]:
        blockers.append(f"Camera-Lock Law (rule 38): {clc['verdict']}")

    # (2) banned vocabulary, against the shipped text.
    try:
        banned = json.load(open(_BANNED_VOCAB_PATH)).get(episode, {}).get(str(beat.get("sceneNumber")), {}).get("banned") or []
    except Exception:
        banned = []
    low = prompt.lower()
    for term in banned:
        if term.lower() in low:
            blockers.append(f"banned vocabulary present: {term!r}")

    # (3) Law 5 — dialogue words never leak.
    for c in (beat.get("cuts") or []):
        raw = str(c.get("dialogue") or "").strip()
        if not raw:
            continue
        words = raw.split(":", 1)[-1].strip()
        if words and len(words) > 8 and words.lower() in low:
            blockers.append(f"Law 5: dialogue words leaked into the shipped prompt: {words!r}")

    parts = prompt.split("\n\n")
    # FIXED 2026-07-08 (the tech-line CLOSER retirement): emit_v5's shape is now 6 parts, not 7 — HEADER,
    # style, references, actingDNA, story, Negative. The standalone tech line ("24fps, smooth cinematic
    # motion...") is gone; fps folded into the HEADER (rule 54). `acting_idx`/`story_idx` are unchanged
    # (still indices 3/4 — only the LAST block moved, from tech to Negative directly) but `tech_idx` no
    # longer exists at all — removed outright, not left pointing at a stale index (the exact bug class rule
    # 46 already found once for `camera_amb_idx`).
    acting_idx = 3 if len(parts) > 3 else -1   # HEADER, style, references, actingDNA, story, Negative
    story_idx = 4 if len(parts) > 4 else -1
    # Self-check: confirm the part count itself still matches this model — if a future emitter change
    # adds/removes a block, this fires as a named flag instead of the index model silently drifting stale
    # again (exactly what happened to camera_amb_idx, then tech_idx, before each was fixed in turn).
    if len(parts) != 6:
        flags.append(f"block-index model may be stale: expected 6 top-level blocks (HEADER/style/references/actingDNA/story/Negative), found {len(parts)}")

    # (4) appearance-prose leak — a character's own short `markers` field must stay inside Acting DNA only.
    # CS._load_chars() (not CS._CHARS) — see the identical 2026-07-08 fix note at check_character_vocabulary.
    for name in cast:
        markers = str((CS._load_chars().get(name) or {}).get("markers") or "").strip().lower()
        if not markers:
            continue
        for i, p in enumerate(parts):
            if i == acting_idx:
                continue
            if markers in p.lower():
                flags.append(f"possible appearance leak: {name}'s markers text ({markers!r}) found outside the Acting DNA block")

    # (5) no leftover speed adjectives — scoped to the STORY block only (the only block
    # `_v5_strip_speed_adjectives` is ever applied to; the style law and standing negatives legitimately
    # contain words like "hyper" ("bright hyper saturated colours") that this check must not flag).
    if story_idx >= 0 and CS._SPEED_ADJ_RE.search(parts[story_idx]):
        flags.append("a speed adjective survived stripping in the beat-story block — check _v5_strip_speed_adjectives")

    # (6) no negation outside the Negative line — exempt every block that legitimately quotes/derives from
    # real authored prose (style, Acting DNA, Beat Story) PLUS the references block (see below). In practice
    # this leaves only index 0 (HEADER) actually checked — a mechanical, fixed string that never needs
    # negation, so the check is a low-cost regression guard, not a load-bearing lint (found and corrected in
    # the 2026-07-08 sign-off audit: an earlier version of this comment claimed "header, references" were
    # both checked, which was never true — references was already in the exempt set below; only the PROSE
    # here was stale, not the logic).
    # THE ANTI-HOLD-SAFE RELAY WORDING (2026-07-07, decision 1) put deliberate, mechanical negation into the
    # references block itself — "Do not hold the previous pose, replay the previous action..." plus a
    # beat-authored spatialAxis line ("never swap sides") — so the references block (ref_idx) is EXEMPT,
    # same reasoning as style/Acting DNA/Beat Story: this is LAWFUL negation this doctrine now asks for
    # by name, never "invented prohibition language" the check exists to catch.
    style_idx = 1 if len(parts) > 1 else -1
    ref_idx = 2 if len(parts) > 2 else -1
    negative_idx = len(parts) - 1
    exempt = {acting_idx, story_idx, style_idx, ref_idx, negative_idx}
    for i, p in enumerate(parts):
        if i in exempt:
            continue
        if _NEGATION_RE.search(p):
            flags.append(f"negation found in a mechanical block (segment {i}) — check for invented prohibition language")

    # (9) THE ANTI-SLOP LEXICON — hard BLOCK in the Beat Story block only (freely-authored dynamic prose; no
    # ruling stands behind a slop word landing there, so it's always fixable at the data and worth blocking
    # on). FLAG-only everywhere else — a hit in the style law or tech line names a LOCKED constant only
    # Julian's own edit can amend, never something this beat's own authoring caused.
    if story_idx >= 0:
        for m in _ANTI_SLOP_RE.finditer(parts[story_idx]):
            blockers.append(f"anti-slop: {m.group(0)!r} in the beat-story block — rewrite as the one concrete "
                             f"production detail that earns it (light source+direction+behaviour, camera "
                             f"verb+speed+endpoint, or material+texture+motion)")
    for i, p in enumerate(parts):
        if i == story_idx:
            continue
        for m in _ANTI_SLOP_RE.finditer(p):
            flags.append(f"anti-slop word {m.group(0)!r} found in a locked block (segment {i}) — not this "
                         f"beat's own authoring; only a style-law/tech-line edit can remove it")

    # (7) structural congruence with §4a/§4b's exact reference wording.
    ref_block = parts[2] if len(parts) > 2 else ""
    # @Video1 RETIRED (Julian, 2026-07-07 — "the video I don't like it either, I think it confuses things"):
    # rule 26's "FIFTH ANCHOR" is removed from the reference stack entirely, opener and relay alike.
    if "@Video1" in ref_block:
        blockers.append("@Video1 must never appear — retired 2026-07-07, see cb_segprompt.py's module docstring")
    if not relay:
        if "@图1 opening keyframe — begin on this exact composition." not in ref_block:
            blockers.append("references block doesn't match the doctrine's exact opener wording (§4a)")
    else:
        # THE ANTI-HOLD-SAFE RELAY WORDING (2026-07-07, decision 1) — supersedes the "start from this frame"
        # sentence checked here until today; see cb_segprompt._v5_references's docstring for the full ruling.
        if ("@图1 is the approved final frame of the previous beat and must be matched exactly as the first "
                "frame only.") not in ref_block:
            blockers.append("references block doesn't match the doctrine's exact relay wording (§4b)")
        if "Do not hold the previous pose" not in ref_block:
            blockers.append("references block is missing the relay anti-hold counter-instruction (§4b)")
    # THE CAST-SIZE FIX (2026-07-07, closing the long-open word-count ticket): an ACTIVE cast member (named
    # in this beat's own cuts/speakers/opensOn — cb_segprompt._v5_active_cast) still gets the doctrine's
    # exact per-member sentence; a BACKGROUND cast member (present but doing nothing named in this beat) is
    # consolidated into one shared "background cast" line instead — so the check must confirm every cast
    # member's own @图N-plus-name tag is present SOMEWHERE in the block, not that every one of them has its
    # own full repeated "match exactly" sentence.
    active, _background = CS._v5_active_cast(beat, cast)
    for i, name in enumerate(cast):
        tag = f"@图{i + 2} {name}"
        if name in active:
            if f"{tag} — match exactly." not in ref_block:
                blockers.append(f"references block missing the exact binding line for {name!r} (§4a/§4b)")
        elif tag not in ref_block:
            blockers.append(f"references block missing {name!r}'s reference tag entirely (background-cast consolidation)")

    # (8) citation map — every content line traces to a named source (THE FIDELITY LAW).
    # FIXED 2026-07-07 (front-to-back audit): two of these were stale. "beat_story" cited the retired
    # `storyBeat` flattened-summary field — Block 4 has walked the beat's own `cuts[]` + `endState` since
    # the shot-list ruling (cb_segprompt._v5_beat_story's own docstring), never storyBeat. "camera_ambience"
    # cited `scene.ambientBed`, but that whole paragraph was retired the same day (the thunder-leak bug) —
    # no such content exists in the shipped prompt to cite at all, so the entry is removed, not just renamed.
    # A BACKGROUND cast member (THE CAST-SIZE FIX, 2026-07-07) has no Acting DNA line in the shipped prompt
    # at all — citing one for them would be the exact same "cites content that isn't actually there" bug
    # just fixed above for camera_ambience; they're cited as reference-only instead.
    citations = {"style": "laws/style.txt", "references": "engine stack logic (cb_scene.relay_source_for)"}
    if str((scene or {}).get("sceneLook") or "").strip():
        citations["style:sceneLook"] = f"scene {beat.get('sceneNumber')}.sceneLook"
    if relay and str(beat.get("relayOpeningNote") or "").strip():
        citations["references:relayOpeningNote"] = f"beat {beat_code}.relayOpeningNote"
    if str(beat.get("spatialAxis") or "").strip():
        citations["references:spatialAxis"] = f"beat {beat_code}.spatialAxis"
    # THE DELIVERY LAW (rule 53) citation — found missing in the 2026-07-08 software-wide audit (delivery
    # was only implicitly covered by the generic "beat_story" citation below, unlike its sibling optional
    # Layer-2 fields relayOpeningNote/spatialAxis/sceneLook, each of which gets its own key above).
    delivery_cuts = [str(c.get("n")) for c in (beat.get("cuts") or []) if str(c.get("delivery") or "").strip()]
    if delivery_cuts:
        citations["beat_story:delivery"] = f"beat {beat_code}.cuts[{','.join(delivery_cuts)}].delivery"
    for name in cast:
        if name in active:
            _txt, field = CS._v5_acting_dna_source(name)
            citations[f"actingDNA:{name}"] = f"characters.json:{name}.{field}" if field else "MISSING"
        else:
            citations[f"actingDNA:{name}"] = "background cast — reference image only, no Acting DNA line this beat"
    citations["beat_story"] = f"beat {beat_code}.cuts[] + .endState"
    citations["negatives"] = "GATE3_ANIMATION_DOCTRINE.md §2 standing eleven + beat.stagingProhibited"

    return {"ok": not blockers, "blockers": blockers, "flags": flags, "citations": citations,
            "word_count": wc, "prompt": prompt}

# Canonical QA reason codes (machine-readable) + the one-line fix each implies. Merges OUR anatomy check (their DoD
# lacks limb-counting) with the useful codes from the QA-agent spec. The fuzzy camera / staging / shot-type /
# screen-direction checks are deliberately LEFT OUT of the hard gate for now — vision QA can't judge them reliably and
# would false-reject good frames, spinning the regen loop.
DONE_CODES = {
    "LOW_RESOLUTION":         "export at 2K or higher (long edge >= 2048px)",
    "BAD_ASPECT":             "render at 16:9",
    "ANATOMY_DEFECT":         "regenerate with correct, complete anatomy (right number of arms/legs/wings/paws; no extra, missing or merged limbs)",
    "WRONG_CHARACTER":        "match each character to its sheet exactly (face, proportions, markings)",
    "EXTRA_CHARACTER":        "remove any character or creature not named in the shot",
    "BEE_WITH_CRYSTAL":       "remove any crystal from the bee(s) — only bears and the environment carry crystals",
    "WRONG_LOCATION":         "rebuild on the correct scene plate (same place and geometry)",
    "SOFT_FOCUS_FACE":        "render the face and eyes tack-sharp; keep any blur in the far background",
    "FACE_COLLAGE":           "produce one coherent frame and face — no extra eyes, double features, collage or line-up",
    "BAD_CROP":               "reframe so the head and key parts are not chopped",
    "LIGHTING_MISMATCH":      "relight to this beat's mood and colour temperature",
    "TRANSIENT_PROP_DRIFT":   "remove the temporary substance/prop not named in this shot (don't carry it from the previous frame)",
    "CRYSTAL_STATE_MISMATCH": "set the bear's crystal brightness to the expected state for this beat",
    "STYLE_MISMATCH":         "keep premium 3D-CGI Pixar/DreamWorks style (no 2D, painterly or photoreal)",
    "UNSAFE_FACE":            "remove any horror/distortion — faces appealing and safe for ages 4-8",
    "TEXT_IN_FRAME":          "remove all text, captions, logos, watermarks and UI",
    "ADDED_PROP":             "remove anything on the character not in its turnaround — no added accessories, items or props on the body (it will flicker and vanish in the clip)",
    "SIZE_MISMATCH":          "fix the relative scale — each character at its canonical size; the smaller character must never render as large as or larger than the bigger one",
    "WEAK_POSE":              "restage into a clear, acting opening pose that reads in silhouette and carries the feeling — never stiff, neutral, blank or T-posed",
    "ACTION_STATE_MISMATCH":  "restage so the pose ACTIVELY performs the beat's own scripted action (e.g. mid-flight and already in motion, not static, posed or floating in place) — the image must show what the story says is happening",
    "BELOW_BAR":              "lift to world-class feature-film Pixar 3D-CGI — beautiful motivated lighting, polished materials, real depth, cinematic composition; not flat, dull, cheap, plasticky or AI-mushy",
    "PLATE_DRIFT":            "match the locked scene plate's environment, layout, camera and composition — do not re-invent the world or depart from its arrangement",
    # ── Gate-3 CLIP QA (temporal) ─────────────────────────────────────────────────────────────────────
    "CLIP_MISSING":           "clip file missing or empty — re-render the beat",
    "CLIP_WONT_DECODE":       "clip is corrupt / has no video stream — re-render the beat",
    "CLIP_BAD_DURATION":      "clip duration outside ~8-15s — check durationSec and re-render",
    "LOW_RESOLUTION_CLIP":    "clip rendered below the Seedance floor (expected >=1280 wide) — re-render",
    "CLIP_FROZEN":            "the clip barely moves (a near-still) — Seedance didn't animate it; re-render",
    "CLIP_IDENTITY_DRIFT":    "a character drifts off-model during the take — re-render (the keyframe is the locked truth)",
    "CLIP_MORPH":             "a character morphs or swaps identity mid-clip — re-render",
    "CLIP_POP_CHARACTER":     "an uninvited character appears in the take — re-render",
    "CLIP_FLICKER":           "an item pops in/out or strobes within a shot — re-render with a clean motion arc",
    "CLIP_FLOATY":            "motion looks floaty/weightless — re-render with grounded weight (advisory)",
    "CLIP_STATE_MISSING_START": "the beat's named story-state is absent at the start — frame 1 must match the keyframe",
    "CLIP_STATE_DROPPED":     "the beat's named story-state disappears by the end — keep it for the whole take",
    "QA_UNAVAILABLE":         "QA could not run (ffmpeg/vision unavailable) — not a clip fault; check tooling",
    # ── JOIN CONTRACT (Julian, 2026-07-03) — the handoff between beat N and beat N+1 ──────────────────
    "JOIN_DISCONTINUITY":     "beat N's settle (final frame) and beat N+1's opening frame disagree on state, "
                              "light, geography or spatial coverage (all four always checked, rule 34's Coverage "
                              "Law), or — on a declared seamless_continuation join only — position/framing too; "
                              "see check_join()'s per-criterion verdict for which",
    # ── RE-MINT (Julian's ruling, 2026-07-03) — the harvest's NB2 cleanup pass ────────────────────────
    "REMINT_DRIFT":           "the re-minted frame drifted from the harvested frame (position/state) or the "
                              "turnarounds (identity) — see check_remint()'s per-criterion verdict for which; "
                              "re-mint is a cleanup pass only, never a restage",
}
BEES = {"Zenny", "Fuzzby"}

# ── Gate-3 CLIP QA tuning ──────────────────────────────────────────────────────────────────────────────
# A clip is a MOTION artifact: the keyframe gate's pose / sharpness / bar / crop / lighting / style checks false-fire
# on a mid-motion frame, so a sampled clip frame is judged ONLY on these temporal-safe identity/continuity codes.
CLIP_SAFE_CODES = {"ANATOMY_DEFECT", "WRONG_CHARACTER", "EXTRA_CHARACTER", "BEE_WITH_CRYSTAL",
                   "SIZE_MISMATCH", "TRANSIENT_PROP_DRIFT", "CRYSTAL_STATE_MISMATCH",
                   "UNSAFE_FACE", "TEXT_IN_FRAME", "WRONG_LOCATION"}
                   # ADDED_PROP is deliberately OUT: it can't tell a legit keyframe story-state (the pollen moustache)
                   # from a newly-added prop — the keyframe is the truth and Pass B already judges identity vs it.
# Codes that WARRANT a re-render (BLOCK). Everything else is an advisory NOTE — surfaced, never auto-fails a good take,
# never inflates the flag count. Mirrors the BLOCK/NOTE split the continuity checker already uses.
CLIP_BLOCK_CODES = {"CLIP_MISSING", "CLIP_WONT_DECODE", "CLIP_FROZEN", "CLIP_MORPH",
                    "CLIP_IDENTITY_DRIFT", "CLIP_POP_CHARACTER", "EXTRA_CHARACTER",
                    "BEE_WITH_CRYSTAL", "UNSAFE_FACE"}
# ANATOMY_DEFECT is advisory-only (NOTE) for clips: a vision model miscounts a cartoon bee's small / tucked / occluded
# arms in motion too often to AUTO-FAIL a take on it. It still surfaces as a note for the human to judge on the frame.
# These vision codes are noisy on a single frame — only BLOCK when corroborated on >=2 settled frames (first AND last);
# a lone hit is demoted to a NOTE. The cheapest, highest-leverage false-positive killer.
CLIP_CORROBORATE = {"ANATOMY_DEFECT", "CLIP_IDENTITY_DRIFT", "EXTRA_CHARACTER", "WRONG_LOCATION"}
# The beat is ABOUT removing the state if its action uses one of these verbs — then a clean END is correct (no DROP flag).
RESOLVE_VERBS = ("wipe", "sneeze", "shake", "dry", "dries", "drop", "eat", "finish", "clean",
                 "wash", "brush", "rinse", "blow")
SUBSTANCE_WORDS = ("pollen", "moustache", "dust", "dirt", "mud", "water", "wet", "honey", "food",
                   "soaked", "splash", "sticky", "crumbs", "soot", "paint")

def _any_word(words, text):
    """Word-boundary membership (not bare substring) — a bare `w in text` false-positives short verbs/nouns inside
    an unrelated word ("eat" inside "neatly", "dry" inside "drying" is fine but inside "dryad" isn't, "mud" inside
    "mudlark"). Reading the full cuts[] action text (below) widened the search space enough for this to fire in
    practice on real Ep1 beats, so it needs a real boundary check, not the old naive substring test."""
    return any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)
FROZEN_EPS = 1.5   # mean-abs luma diff (0-255) below which consecutive frames count as "identical" → a near-still

def check_done_frame(shot, kf, sc, episode="Ep1", is_end=False, clip_frame=False):
    """Check ONE frame (start or end) against the keyframe DEFINITION OF DONE (KEYFRAME_DONE.md). Returns a structured
    result with canonical reason codes: {ok, reasons:[CODE,...], fix_hint, verdict}.
    Deterministic: resolution + aspect. Vision: anatomy, identity, cast, bee-no-crystal, location, sharpness, collage,
    crop, lighting, transient-prop, crystal-state, style, safe-face, text."""
    tag = "END" if is_end else "START"
    if not os.path.exists(kf):
        return {"ok": None, "reasons": ["MISSING"], "fix_hint": "render this frame", "verdict": f"[{tag}] (no frame)"}
    reasons = []
    sz = _img_size(kf)
    if sz and not clip_frame:   # a 720p clip frame would fail the 2K keyframe floor — clip resolution is checked once in check_clip
        w, h = sz
        if w < DONE_MIN_WIDTH: reasons.append("LOW_RESOLUTION")
        if h and not (1.70 <= w / h <= 1.85): reasons.append("BAD_ASPECT")
    # references by role: scene plate (geometry) + each character's TURNAROUND — the SAME image the build used. (Judging
    # against the front anchor while the build used the turnaround caused false WRONG_CHARACTER flags + endless regens.)
    plate = (sc or {}).get("master")
    refs = []; labels = []
    if plate and os.path.exists(plate) and plate != kf:
        refs.append(plate); labels.append("the SCENE reference (locked set / geometry)")
    chars = [c for c in shot.get("characters", []) if c]; cast = ", ".join(chars) or "(none named)"
    for c in chars:
        cc = P.CHARACTERS.get(c) or {}
        turn = next((r for r in (cc.get("refs") or []) if "turnaround" in r.lower()), None)
        ref = turn if (turn and os.path.exists(turn)) else cc.get("anchor")
        if ref and os.path.exists(ref) and ref not in refs:
            refs.append(ref)
            labels.append(f"the CHARACTER reference for {c} (the TURNAROUND — judge {c}'s identity against this; the "
                          f"render shows {c} at one angle, which is fine, as long as the design matches the turnaround)")
    # scan ALL the beat's text fields, not just "action" — beat-native packages name a story-substance (the pollen
    # moustache, dirt) in storyBeat/startState, so a named state is EXPECTED and must not flag TRANSIENT_PROP_DRIFT.
    # "action" is a CUT-level field on beat-native data (there is no beat-level "action"), so shot.get("action") was
    # always empty here — same bug class as the shotSize/cuts[0] find; join every cut's own action text instead.
    # "endState" was a leftover read from the removed continuity-tail mechanism (T2 ruling) — no such field is ever
    # written, so it always contributed nothing; dropped.
    cuts_action = " ".join(str(c.get("action") or "") for c in (shot.get("cuts") or []))
    a = " ".join([str(shot.get(k) or "") for k in ("storyBeat", "startState")] + [cuts_action]).lower()
    light = (shot.get("light") or shot.get("lighting") or sc.get("lighting") or "").strip()
    substance = _any_word(("pollen", "dust", "dirt", "mud", "water", "wet", "wipe", "smear", "food", "honey", "splash", "soaked"), a)
    bees_present = any(c in BEES for c in chars); bears = [c for c in chars if c not in BEES]
    glow = (shot.get("crystalGlow") or "").strip()
    # ACTION-STATE FIDELITY (Julian, 2026-07-03): "whenever we're bringing the story to life... make sure the images
    # are right — if the first scene is them flying through the meadow, then they need to be flying through the
    # meadow." A pose can pass WEAK_POSE's generic "dynamic, not stiff" bar while still missing the SPECIFIC
    # scripted action — this is exactly the bee-flight bug (both wings spread symmetrically, body hanging static
    # read as "a pose", just the wrong one). Checks the frame against the beat's OWN action text, not a generic
    # dynamism bar. Deliberately excludes "hover"/"hovering" — it's the default state description for nearly every
    # bee beat and isn't inherently wrong (the WING/FLIGHT-ENERGY prompt law is what makes a hover read as active,
    # not this gate); only fires on clearly active locomotion verbs, so a genuinely held/still beat is never flagged.
    _ACTION_VERBS = ("fly", "flying", "flies", "flew", "chase", "chases", "chasing", "chased", "dive", "diving",
                     "dives", "dived", "dove", "run", "running", "runs", "ran", "swim", "swimming", "swims",
                     "climb", "climbing", "climbs", "dash", "dashing", "dashes", "zoom", "zooming", "zooms",
                     "race", "racing", "races", "sprint", "sprinting", "leap", "leaping", "leaps", "jump", "jumping",
                     "jumps", "soar", "soaring", "soars", "glide", "gliding", "glides", "tumble", "tumbling",
                     "tumbles", "zigzag", "zigzags", "zigzagging", "zig-zag", "zig-zags", "zig-zagging", "weave",
                     "weaves", "weaving", "dip", "dips", "dipping", "dart", "darts", "darting", "swoop", "swoops",
                     "swooping", "bounce", "bounces", "bouncing", "dodge", "dodges", "dodging", "buzz", "buzzes",
                     "buzzing", "drift", "drifts", "drifting", "spin", "spins", "spinning", "whirl", "whirls",
                     "whirling", "accelerate", "accelerates", "accelerating", "swerve", "swerves", "swerving")
    action_verb = next((v for v in _ACTION_VERBS if _any_word([v], a)), None)
    items = [
        ("ANATOMY_DEFECT", f"each character ({cast}) has correct COMPLETE anatomy — exact number of arms, legs, wings, "
         "paws, eyes, antennae (cartoon bee = 2 arms, 2 legs, 1 pair wings, 2 antennae). Flag ONLY a CLEARLY extra, "
         "duplicated, merged, fused or melted limb/feature — do NOT flag a limb as 'missing' when it could simply be "
         "tucked against the round body, held in front, hidden behind a prop or another character, or out of frame"),
        ("WRONG_CHARACTER", "each character is clearly the RIGHT KIND of character from the reference — a stylised "
         "cartoon BEE (Fuzzby/Zenny: round body, stripes, glasses, antennae). Flag ONLY a clearly WRONG character or "
         "species (a human, girl, boy, bear, cat, dog or other creature instead of a bee). Do NOT flag subtle styling, "
         "shade or proportion differences on an otherwise-correct bee — that is acceptable variation"),
        ("EXTRA_CHARACTER", f"the ONLY characters in frame are: {cast}; flag any clearly ADDED person, animal or creature"),
        ("WRONG_LOCATION", "the frame is in the SAME PLACE as the scene reference (the rainforest/flower setting). Flag "
         "ONLY a clearly different location (indoors, a city, a beach, a different world) — not minor differences in "
         "which flowers or how the foliage is arranged"),
        ("SOFT_FOCUS_FACE", "the character's face and eyes are crisp and sharp — not soft, blurry or smeared"),
        ("FACE_COLLAGE", "ONE coherent frame and face — no collage, split-screen, character sheet, line-up, extra eyes, "
         "double pupils or patchwork"),
        ("BAD_CROP", "the character fits the frame with a readable silhouette — head and key parts not accidentally chopped"),
        ("LIGHTING_MISMATCH", f"the light/mood fits THIS beat (\"{light}\"); flag only if clearly opposite (sunny when "
         "the beat is a dark storm)"),
        ("STYLE_MISMATCH", "premium 3D-CGI Pixar/DreamWorks style — no 2D, line-art, painterly or photoreal drift"),
        ("UNSAFE_FACE", "faces appealing and safe for ages 4-8 — no horror, melting or disturbing distortion"),
        ("TEXT_IN_FRAME", "no text, captions, words, logos, watermarks or UI"),
    ]
    if not substance:
        items.append(("TRANSIENT_PROP_DRIFT", "the character's face/fur are CLEAN — no pollen, dust, dirt, water, food "
                      "or 'moustache' of substance (this shot's action involves none); flag any present"))
    if bees_present:
        items.append(("BEE_WITH_CRYSTAL", "the bee(s) have NO crystal on their body/chest — bees NEVER wear crystals "
                      "(only bears and the environment have crystals)"))
    if bears and glow:
        items.append(("CRYSTAL_STATE_MISMATCH", f"the bear's crystal brightness matches the expected state (\"{glow}\")"))
    # FOUNDATION-CRITICAL: the keyframe is what the WHOLE clip is built from — hold it to the world-class bar.
    items += [
        ("ADDED_PROP", "the character has NOTHING on its body that its turnaround reference doesn't show — no added "
         "accessories, items, props, bags or attachments on the body; flag anything bolted onto a character its reference lacks"),
        ("WEAK_POSE", "the character is in a clear, ACTING opening pose that reads in SILHOUETTE and carries the beat's "
         "feeling — dynamic and alive; flag a stiff, neutral, blank, T-posed or just-standing pose"),
        ("BELOW_BAR", "this is a WORLD-CLASS, feature-film-grade 3D-CGI frame in the Pixar/DreamWorks register — beautiful "
         "motivated lighting, polished believable materials, real layered depth, cinematic composition; flag ONLY if it is "
         "clearly flat, dull, cheap, plasticky, muddy or has obvious AI artefacts/mush — not for subtle taste"),
    ]
    action_states = shot.get("actionStates") or {}
    if action_verb and bees_present and action_states:
        # PER-CHARACTER ACTION STATE (Julian's ruling, 2026-07-03, re: 1.B1's Fuzzby/Zenny false-positive): a beat
        # can declare EACH character's own expected state — one bee can be the beat's action-state subject while
        # another is a deliberate STILL counterpoint, and the two must not be judged by the same bar. Judge every
        # named character against ITS OWN declared state; fires if ANY character deviates from its own state (a
        # "static-calm" character rendered racing at speed still fails — this is not a blanket exemption).
        per_char = []
        for c in chars:
            state = str(action_states.get(c) or "").strip().lower()
            if state in ("dynamic-flight", "dynamic", "flight"):
                per_char.append(
                    f"{c} (declared DYNAMIC-FLIGHT — caught mid-{action_verb}, already accelerating): wings must be "
                    "ASYMMETRIC (one visibly higher than the other, mid-downstroke — NOT both spread open and "
                    "symmetrical) AND the body must LEAN FORWARD/DOWN into the direction of travel with legs tucked "
                    f"or trailing back (NOT hanging near-vertical with legs dangling straight down like a puppet at "
                    f"rest). Flag {c} under ACTION_STATE_MISMATCH if EITHER condition fails.")
            elif state in ("static-calm", "static", "calm"):
                per_char.append(
                    f"{c} (declared STATIC-CALM — a deliberate still counterpoint, NOT part of this beat's action "
                    f"verb): an upright, hovering or gently-posed body is CORRECT for {c} — symmetrical or naturally "
                    f"fluttering wings are FINE and must NOT be flagged. Flag {c} under ACTION_STATE_MISMATCH ONLY "
                    "if she instead shows the racing signature — body sharply angled forward/down into a flight "
                    "line with a speed/motion trail behind her, i.e. wrongly staged as if she were also the action "
                    "subject.")
        if per_char:
            items.append(("ACTION_STATE_MISMATCH", "Each named character below has its OWN declared action state "
                          "for this beat — judge every character SEPARATELY against its own line, never hold one "
                          "character to another's bar:\n" + "\n".join(per_char)))
    elif action_verb and bees_present:
        # concrete, checkable criteria — the SAME ones cb_prompts.build_keyframe_prompt's WINGS/FLIGHT-ENERGY law
        # asks the generator to produce, so QA verifies the exact thing generation was told to do, not a vague
        # "does this look dynamic enough" taste call the model will wave through. UNIFORM bar — used only when a
        # beat has no per-character actionStates declared (see above); every bee in frame is held to one bar.
        items.append(("ACTION_STATE_MISMATCH", f"look SPECIFICALLY at each bee's WINGS and BODY ANGLE (this beat calls "
                      f"for them caught mid-{action_verb}, already accelerating): (1) WINGS — are both wings spread "
                      "OPEN and SYMMETRICAL (same angle, mirror images of each other)? That is a static hover/rest "
                      "pose and FAILS. A correct pose has the wings ASYMMETRIC — one visibly higher than the other, "
                      "mid-downstroke. (2) BODY — is the body hanging near-VERTICAL with legs dangling straight down "
                      "underneath, like a puppet at rest? That FAILS. A correct pose leans the body FORWARD and DOWN "
                      "into the direction of travel, with legs tucked or trailing back. This PASSES only if BOTH the "
                      "wings are asymmetric AND the body leans forward into the motion — flag ACTION_STATE_MISMATCH "
                      "if EITHER the wings are symmetrical OR the body/legs hang passively"))
    if plate and os.path.exists(plate) and plate != kf:
        items.append(("PLATE_DRIFT", "the environment, layout, camera angle and composition MATCH the SCENE reference (the "
                      "locked plate) — same set in the same arrangement; flag if the world is re-invented or the composition "
                      "clearly departs from the plate"))
    ranked = sorted([c for c in chars if (P.CHARACTERS.get(c) or {}).get("sizeRank") is not None],
                    key=lambda c: -((P.CHARACTERS.get(c) or {}).get("sizeRank") or 0))
    if len(ranked) >= 2:
        items.append(("SIZE_MISMATCH", "the characters' RELATIVE sizes are correct — largest to smallest: "
                      + " > ".join(ranked) + "; flag if a smaller character renders as large as or larger than a bigger one"))
    if clip_frame:   # a MOTION frame: drop the held-keyframe pose / sharpness / bar / crop / lighting / style checks that false-fire mid-motion
        items = [it for it in items if it[0] in CLIP_SAFE_CODES]
    checklist = "\n".join(f"[{code}] {desc}" for code, desc in items)
    imglist = "\n".join(f"IMAGE {i+2} = {lab}" for i, lab in enumerate(labels))
    subject = "a rendered keyframe"
    if clip_frame:
        subject = ("a single FRAME sampled from a rendered ANIMATION CLIP (a motion frame — IGNORE momentary motion "
                   "blur, a mid-action transitional pose or motion smear; judge ONLY identity, anatomy and continuity)")
        if (shot.get("comedyMode") or "").upper() == "BIG":   # the comedy doctrine INTENTIONALLY exaggerates — don't punish it
            subject += (". This is a BIG COMEDY beat: deliberate squash-and-stretch, smears and extreme exaggerated poses "
                        "are CORRECT — a streaked or stretched limb is a smear, NOT a melted/extra limb; an exaggerated "
                        "squashed face is timing, NOT a defect. Flag only a genuinely broken or clearly wrong character")
    q = (f"You are a STRICT animation QA supervisor checking {subject} against a fixed standard. IMAGE 1 is "
         "the frame to judge.\n" + imglist + "\n\nCheck each item below (the [CODE] is its label). Be strict but only "
         "flag REAL breaks, not subtle taste:\n" + checklist +
         "\n\nReply 'PASS' on line 1 if every item holds. Otherwise reply 'FAIL' on line 1, then ONE line per FAILED "
         "item as 'CODE: short reason', using the exact [CODE] label.")
    text, err = vision_verdict(q, [kf] + refs)
    if err and not reasons:
        return {"ok": None, "reasons": ["QA_ERROR"], "fix_hint": err, "verdict": f"[{tag}] {err}"}
    if text and not text.strip().upper().startswith("PASS"):
        up = text.upper()
        for code in DONE_CODES:
            if code in up and code not in reasons:
                reasons.append(code)
    if clip_frame:   # a wrong/off-model character on a CLIP frame is a continuity DRIFT (the keyframe was the locked truth)
        reasons = list(dict.fromkeys("CLIP_IDENTITY_DRIFT" if c == "WRONG_CHARACTER" else c for c in reasons))
    ok = len(reasons) == 0
    fix_hint = "" if ok else "; ".join(DONE_CODES.get(c, c) for c in reasons[:4])
    verdict = f"[{tag}] " + ("PASS" if ok else "FAIL: " + ", ".join(reasons) + (f" — {fix_hint}" if fix_hint else ""))
    return {"ok": ok, "reasons": reasons, "fix_hint": fix_hint, "verdict": verdict}

# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
# GATE-3 CLIP QA — the temporal mirror of check_done_frame (CLIP_DONE.md). A clip is a MOTION artifact, so QA =
# deterministic ffprobe/ffmpeg checks + per-frame identity on the SETTLED frames (first/last, reduced checklist) +
# ONE multi-frame continuity pass (identity stability, morph, story-state start->end, flicker, weight). Advisory,
# BLOCK/NOTE split, corroboration on noisy codes, BIG-comedy licence, and it NEVER crashes the caller.
# ══════════════════════════════════════════════════════════════════════════════════════════════════════════
def _ffprobe(clip):
    """(w, h, duration_s); 'NO_FFPROBE' if the tool is missing; None if it ran but gave nothing parseable."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height:format=duration", "-of", "csv=p=0", clip],
                           capture_output=True, text=True, timeout=30, check=False)
    except FileNotFoundError:
        return "NO_FFPROBE"
    except Exception:
        return None
    nums = [x for x in (r.stdout or "").replace("\n", ",").split(",") if x.strip()]
    try:
        return (int(float(nums[0])), int(float(nums[1])), float(nums[-1]))
    except Exception:
        return None

def _extract(clip, dur, tmp):
    """Pull FIRST, MID and LAST frames to PNG. Returns {name: path} for those that wrote; 'NO_FFMPEG' if absent."""
    out = {}
    jobs = [("first", ["-i", clip, "-frames:v", "1"]),
            ("mid",   ["-ss", f"{max(0.0, dur/2.0):.2f}", "-i", clip, "-frames:v", "1"]),
            ("last",  ["-sseof", "-0.3", "-i", clip, "-update", "1", "-frames:v", "1"])]
    for name, args in jobs:
        p = os.path.join(tmp, f"{name}.png")
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error"] + args + ["-q:v", "2", p],
                           capture_output=True, timeout=60, check=False)
        except FileNotFoundError:
            return "NO_FFMPEG"
        except Exception:
            continue
        if os.path.exists(p) and os.path.getsize(p) > 0:
            out[name] = p
    return out

def _motion_energy(clip, dur, n=16, w=32, h=18):
    """Per-pair mean-abs luma diff (0-255) across n tiny grayscale frames — raw bytes via ffmpeg, no PIL/PNG decode.
    The cheap deterministic backstop: a near-zero result = a frozen near-still. None if unavailable."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", clip,
                            "-vf", f"fps={max(2, n)}/{max(0.1, dur):.3f},scale={w}:{h},format=gray",
                            "-frames:v", str(n), "-f", "rawvideo", "-"],
                           capture_output=True, timeout=60, check=False)
    except Exception:
        return None
    raw = r.stdout or b""; fsz = w * h
    fr = [raw[i*fsz:(i+1)*fsz] for i in range(len(raw)//fsz)]
    if len(fr) < 2:
        return None
    return [sum(abs(a - b) for a, b in zip(f0, f1)) / fsz for f0, f1 in zip(fr, fr[1:])]

def _passB(shot, ordered, comedy_big, next_beat=None):
    """ONE multi-frame continuity+weight vision call. ordered=[keyframe(TRUTH), first, mid, last]. Returns [CLIP_* codes]
    or None if the vision call was unavailable (so the caller can mark QA_UNAVAILABLE, not a content fail)."""
    chars = [c for c in shot.get("characters", []) if c]; cast = ", ".join(chars) or "the characters"
    _start = (shot.get("startState") or "").lower()
    state = next((wd for wd in SUBSTANCE_WORDS if re.search(r"\b" + re.escape(wd) + r"\b", _start)), None)
    # "action" is a CUT-level field (there is no beat-level "action") — read every cut's action text, same fix as
    # check_done_frame's substance scan above.
    cuts_action = " ".join(str(c.get("action") or "") for c in (shot.get("cuts") or []))
    a = (shot.get("storyBeat") or cuts_action or "").lower()
    next_needs = bool(state and re.search(r"\b" + re.escape(state) + r"\b", ((next_beat or {}).get("startState") or "").lower()))
    # carry = the state must still be on him at the END of this take. The NEXT beat needing it OVERRIDES a resolve-verb
    # (B3 'tries to clean his pollen face' but B4 opens 'covered in pollen' → the pollen MUST persist; flag if it drops).
    resolves = _any_word(RESOLVE_VERBS, a) and not next_needs
    big = ("\nThis beat is BIG COMEDY: deliberate squash-and-stretch, motion-smear/streak frames and extreme exaggerated "
           "poses are CORRECT and must PASS. A streaked/stretched limb on a fast frame is a smear, NOT a melted limb; an "
           "exaggerated face squash is timing, NOT a morph. Judge identity ONLY where motion settles (the keyframe, the "
           "first and the last frame), never on a peak-action frame.\n" if comedy_big else "\n")
    lines = [
        f"[CLIP_IDENTITY_DRIFT] Each character ({cast}) stays on-model across the frames vs IMAGE 1 (the keyframe): same "
        "face, colour, glasses, markings, proportions. Flag a character that drifts off-model as the clip plays.",
        "[CLIP_MORPH] No character transforms or swaps identity/species between frames (face does not restructure into a "
        "different character; no bear-bee hybrid appears).",
        f"[CLIP_POP_CHARACTER] No EXTRA character or creature appears who is not one of: {cast}.",
        "[CLIP_FLICKER] No object, prop or body part pops in/out or strobes WITHIN a continuous shot. NOTE: this is a "
        "multi-shot take with internal CUTS — at a cut the whole frame legitimately changes angle and background; do NOT "
        "flag a cut as flicker.",
        "[CLIP_FLOATY] Motion carries WEIGHT — feet keep ground contact, nothing slides/skates or glides with no driver. "
        "(Advisory; do not flag stylised cartoon motion, only genuinely weightless drift.)",
    ]
    if state and not resolves:
        lines.insert(0, f"[CLIP_STATE_DROPPED] The temporary state the beat names — \"{state}\" — is present on the FIRST "
                        "frame AND still present on the LAST frame (the beat carries it). Flag if it disappears, is wiped "
                        "off or dries up by the end.")
    checklist = "\n".join(lines)
    q = ("You are a STRICT animation QA supervisor judging a rendered VIDEO CLIP as an ordered sequence of frames.\n"
         "IMAGE 1 is the SIGNED-OFF KEYFRAME — the locked opening-frame TRUTH the clip was built from (identity, markings "
         "and any story-state are correct here). The following images are clip frames IN TIME ORDER: the START frame, then "
         "a MIDDLE frame, then the LAST frame.\nJudge ACROSS the frames in time order. Check each item ([CODE] is its "
         "label); be strict but only flag REAL breaks across the sequence, never subtle motion, motion blur or taste:"
         + big + checklist +
         "\n\nReply 'PASS' on line 1 if every item holds across the sequence. Otherwise reply 'FAIL' on line 1, then ONE "
         "line per FAILED item as 'CODE: short reason' using the exact [CODE] label.")
    text, err = vision_verdict(q, ordered)
    if err or text is None:
        return None
    if text.strip().upper().startswith("PASS"):
        return []
    out = []
    for ln in text.splitlines()[1:]:           # strict: a CODE only counts at the start of a line (no loose substring)
        m = re.match(r"\s*([A-Z_]+)\s*:", ln)
        if m and m.group(1) in DONE_CODES and m.group(1) not in out:
            out.append(m.group(1))
    return out

def check_clip(shot, clip, keyframe=None, anchors=None, sc=None, episode="Ep1", prompt=None, next_beat=None):
    """Gate-3 CLIP QA. Returns {ok, reasons:[BLOCK,...], notes:[NOTE,...], fix_hint, verdict}. ok=False only on a BLOCK;
    ok=None means QA could not run (tooling/vision) — NEVER a content fail; ok=True passes even with advisory notes."""
    sc = sc or P.scene_cfg(episode, str(shot.get("sceneNumber") or "")) or {}
    blocks, notes = [], []
    def _add(c): (blocks if c in CLIP_BLOCK_CODES else notes).append(c)
    def _unavailable(why):
        return {"ok": None, "reasons": ["QA_UNAVAILABLE"], "notes": notes,
                "fix_hint": why, "verdict": f"[CLIP] QA unavailable — {why}"}
    # ── technical tier (deterministic) ──
    if (not clip) or (not os.path.exists(clip)) or os.path.getsize(clip) == 0:
        return {"ok": False, "reasons": ["CLIP_MISSING"], "notes": [],
                "fix_hint": DONE_CODES["CLIP_MISSING"], "verdict": "[CLIP] FLAG: CLIP_MISSING"}
    probe = _ffprobe(clip)
    if probe == "NO_FFPROBE" or probe is None:
        return _unavailable("ffprobe unavailable")
    w, h, dur = probe
    if w <= 0 or h <= 0:
        return {"ok": False, "reasons": ["CLIP_WONT_DECODE"], "notes": [],
                "fix_hint": DONE_CODES["CLIP_WONT_DECODE"], "verdict": "[CLIP] FLAG: CLIP_WONT_DECODE"}
    if w < CLIP_MIN_WIDTH: notes.append("LOW_RESOLUTION_CLIP")
    if h and not (1.70 <= w / h <= 1.85): notes.append("BAD_ASPECT")
    if not (7.5 <= dur <= 15.5): notes.append("CLIP_BAD_DURATION")
    # ── vision + motion tiers (temp dir always cleaned) ──
    tmp = tempfile.mkdtemp(prefix=f".qa_{(shot.get('beatCode') or 'x').replace('.', '_')}_",
                           dir=os.path.dirname(clip) or ".")
    vis_err = None
    try:
        frames = _extract(clip, dur, tmp)
        if frames == "NO_FFMPEG":
            return _unavailable("ffmpeg unavailable")
        # deterministic motion: a near-still is the one fully-reliable temporal fail (gate to beats that SHOULD move).
        # wordlessHeld beats are DELIBERATELY a still, held moment (no dialogue) — stillness there is correct performance,
        # not a frozen-render defect, so they're exempt regardless of how much storyBeat/action text describes the moment.
        big = (shot.get("comedyMode") or "").upper() == "BIG"
        has_action = bool((shot.get("storyBeat") or shot.get("action") or "").strip())
        en = _motion_energy(clip, dur)
        if en is not None and (big or has_action) and not shot.get("wordlessHeld") and max(en) < FROZEN_EPS:
            blocks.append("CLIP_FROZEN")
        # Pass A: identity/anatomy on the SETTLED frames (first + last), reduced motion-safe checklist
        seen = {}
        for name in ("first", "last"):
            if frames.get(name):
                r = check_done_frame(shot, frames[name], sc, episode, is_end=(name == "last"), clip_frame=True)
                if r.get("ok") is None and ("QA_ERROR" in (r.get("reasons") or [])):
                    vis_err = r.get("fix_hint")
                else:
                    for c in (r.get("reasons") or []): seen[c] = seen.get(c, 0) + 1
        # Pass B: ONE multi-frame continuity + weight call, keyframe as the truth. Its codes join the SAME `seen` tally
        # as Pass A (not a separate immediate _add) so a CLIP_CORROBORATE code only BLOCKs when TWO independent signals
        # agree — e.g. Pass A's first/last-frame check AND Pass B's whole-take check both flag CLIP_IDENTITY_DRIFT.
        if keyframe and os.path.exists(keyframe):
            ordered = [keyframe] + [frames[k] for k in ("first", "mid", "last") if frames.get(k)]
            if len(ordered) >= 3:
                pb = _passB(shot, ordered, big, next_beat=next_beat)
                if pb is None: vis_err = vis_err or "Pass B vision unavailable"
                else:
                    for c in pb: seen[c] = seen.get(c, 0) + 1
        for c, n in seen.items():
            if c in CLIP_CORROBORATE and n < 2: notes.append(c)   # a lone single-signal hit → advisory only
            else: _add(c)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    blocks = list(dict.fromkeys(blocks))
    notes = list(dict.fromkeys(n for n in notes if n not in blocks))
    if not blocks and vis_err and not notes:
        return _unavailable(vis_err)
    ok = len(blocks) == 0
    fix_hint = "; ".join(DONE_CODES.get(c, c) for c in (blocks or notes)[:4])
    if ok:
        verdict = "[CLIP] PASS" + (f" ({len(notes)} note{'' if len(notes)==1 else 's'}: {', '.join(notes)})" if notes else "")
    else:
        verdict = "[CLIP] FLAG: " + ", ".join(blocks) + (f" — {fix_hint}" if fix_hint else "") + \
                  (f"  [notes: {', '.join(notes)}]" if notes else "")
    return {"ok": ok, "reasons": blocks, "notes": notes, "fix_hint": fix_hint, "verdict": verdict}

def check_clips_scene(pkg, scene, episode="Ep1", only=None):
    """Re-QA every rendered clip in a scene (no render) — for the studio re-check + standalone testing. Writes a
    media/{ep}_{code}_{slug}.qa.json sidecar per clip; returns [{shot, ok, verdict}]."""
    import pathlib
    _pkg = json.load(open(pkg))
    beats = [b for b in (_pkg.get("beats") or _pkg.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    sc = P.scene_cfg(episode, str(scene)); out = []
    for i, b in enumerate(beats):
        code = b.get("beatCode") or b.get("shotCode"); slug = b.get("slug", (code or "").replace(".", "_"))
        if only and code != only: continue
        clip = f"media/{episode}_{code}_{slug}.mp4"; kf = f"media/{episode}_{code}_{slug}.png"
        if not os.path.exists(clip): continue
        nb = beats[i+1] if i+1 < len(beats) else None
        v = check_clip(b, clip=clip, keyframe=(kf if os.path.exists(kf) else None), sc=sc, episode=episode, next_beat=nb)
        try: pathlib.Path(f"media/{episode}_{code}_{slug}.qa.json").write_text(json.dumps(v, indent=2))
        except Exception: pass
        out.append({"shot": code, "ok": v["ok"], "verdict": v["verdict"]})
    return out

def check_scene(pkg, scene, episode="Ep1", only=None):
    """Check every shot against the DEFINITION OF DONE — BOTH the start frame and the end frame. Returns one
    aggregated result per shot ({shot, ok, verdict}); the verdict names every failed item so the self-correct
    loop can regenerate with the exact fix."""
    _pkg = json.load(open(pkg))
    shots = [s for s in (_pkg.get("beats") or _pkg.get("shots") or []) if str(s.get("sceneNumber")) == str(scene)]
    for _s in shots:
        _s.setdefault("shotCode", _s.get("beatCode"))
    if only: shots = [s for s in shots if s["shotCode"] == only]
    sc = P.scene_cfg(episode, str(scene))
    out = []
    for s in shots:
        code = s["shotCode"]; slug = s.get("slug", code.replace(".", "_"))
        start = f"media/{episode}_{code}_{slug}.png"; end = f"media/{episode}_{code}_{slug}_end.png"
        if not os.path.exists(start):
            continue
        frames = [check_done_frame(s, start, sc, episode, is_end=False)]
        if os.path.exists(end):
            frames.append(check_done_frame(s, end, sc, episode, is_end=True))
        oks = [f["ok"] for f in frames]
        ok = False if any(o is False for o in oks) else (True if all(o is True for o in oks) else None)
        if ok is False:
            verdict = "FLAG\n  " + "\n  ".join(f["verdict"] for f in frames if f["ok"] is False)
        elif ok is None:
            verdict = "ERR: " + "; ".join(f["verdict"] for f in frames)
        else:
            verdict = "PASS"
        out.append({"shot": code, "ok": ok, "verdict": verdict})
    return out

_BANNED_VOCAB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shows", "crystal-bears",
                                   "canon", "banned_vocabulary.json")

def check_scene_vocabulary(pkg_path, scene_num, episode="Ep1"):
    """THE CONTINUITY BLOCK on banned world vocabulary (Fable's code review, 2026-07-03) — mechanical, text-only,
    no vision call. A scene can carry a list of BANNED words/phrases (canon/banned_vocabulary.json) — vocabulary
    from a name this scene was corrected AWAY from, so its reappearance anywhere is the same ghost recurring
    (e.g. Scene 1's old "Rainforest Pollen Run" / "deep_rainforest_flower_field", corrected to the confirmed
    meadow — found and fixed a third time before this check existed). Checks the scene's own
    name/location/look/sceneShotName/definingFeature fields AND every one of its beats'
    scene/startState/continuity.opensFrom/shot_style text. A hit is a hard BLOCK, never a NOTE."""
    try:
        banned = json.load(open(_BANNED_VOCAB_PATH)).get(episode, {}).get(str(scene_num), {}).get("banned") or []
    except Exception:
        banned = []
    if not banned:
        return {"ok": True, "verdict": "no banned vocabulary registered for this scene"}
    d = json.load(open(pkg_path))
    scene = next((s for s in (d.get("scenes") or []) if str(s.get("sceneNumber")) == str(scene_num)), {})
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene_num)]
    fields = []   # (label, text) pairs — every place the ghost has actually been found hiding
    for k in ("name", "location", "look", "sceneShotName", "definingFeature"):
        if scene.get(k):
            fields.append((f"scenes[{scene_num}].{k}", str(scene[k])))
    for b in beats:
        code = b.get("beatCode") or b.get("shotCode") or "?"
        for k in ("scene", "startState", "shot_style"):
            if b.get(k):
                fields.append((f"{code}.{k}", str(b[k])))
        cont = b.get("continuity") or {}
        if isinstance(cont, dict) and cont.get("opensFrom"):
            fields.append((f"{code}.continuity.opensFrom", str(cont["opensFrom"])))
    hits = []
    for label, text in fields:
        low = text.lower()
        for term in banned:
            if term.lower() in low:
                hits.append(f"{label}: found {term!r}")
    if hits:
        return {"ok": False, "verdict": "BLOCK — banned vocabulary present:\n  " + "\n  ".join(hits)}
    return {"ok": True, "verdict": f"clean — none of {banned!r} present anywhere checked"}

def check_plate(plate_path, location_desc, layout_ref=None):
    """Visual QA for the A1 empty SCENE PLATE: correct environment + (key) NO characters in frame + CRYSTAL
    CANON (Julian's ruling, 2026-07-04, after Scene 1's plate was found showing faceted/cut crystal shapes:
    "every future scene plate is verified against crystal canon... before entering the reference stack"). The
    crystal check names concrete, checkable shape features (rule 17 — never a subjective "does this look
    natural" ask): FACETED/geometric/symmetrical-pointed = FAIL; rough/irregular/geode-like = PASS. World
    crystals are expected on every plate (brand identity) — this checks their SHAPE, never their presence.
    Optionally checks layout vs a world/layout reference. Returns {ok, verdict}."""
    if not os.path.exists(plate_path):
        return {"ok": None, "verdict": f"(no scene plate at {plate_path})"}
    refs = []; labels = []
    if layout_ref and os.path.exists(layout_ref) and layout_ref != plate_path:
        refs.append(layout_ref)
        labels.append("the WORLD/LAYOUT reference — the plate's set, layout and screen-direction should match this")
    imglist = "\n".join(f"IMAGE {i+2} = {lab}" for i, lab in enumerate(labels))
    q = ("You are a STRICT continuity supervisor. IMAGE 1 is an EMPTY SCENE PLATE (an establishing environment). "
         + (imglist + "\n\n" if labels else "")
         + f"Requirements:\n- The scene is: {location_desc}. Its environment, set elements, layout and lighting are correct.\n"
         "- CRITICAL: there are NO characters, NO bears, NO people and NO creatures anywhere in frame — it is an EMPTY set.\n"
         "- CRYSTAL SHAPE: look specifically at any crystals in frame. FAIL if they show FACETED, geometric, "
         "symmetrical-pointed surfaces (sharp flat planes meeting at edges — a cut-gemstone or jewelry-store "
         "look), or if they are laid out in a deliberate, arranged pattern. PASS if they read as rough, "
         "irregular, geode-like natural formations — uneven surfaces, no faceting, scattered rather than "
         "composed. (Their mere presence is correct and expected — only the SHAPE is being judged.)\n"
         + ("- The set, layout and screen-direction match the WORLD/LAYOUT reference.\n" if labels else "")
         + "Reply 'PASS' on line 1 if ALL hold (correct, empty environment, natural-shaped crystals), otherwise "
         "'FLAG' then one short line per break.")
    text, err = vision_verdict(q, [plate_path] + refs)
    if err:
        return {"ok": None, "verdict": err}
    return {"ok": text.strip().upper().startswith("PASS"), "verdict": text.strip()}

def check_charsheet(sheet_path, characters, episode="Ep1"):
    """Visual QA for the A2 character-sheet anchor: each character on the sheet vs its own anchor +
    signature features + relative sizes. Returns {ok, verdict}."""
    if not os.path.exists(sheet_path):
        return {"ok": None, "verdict": f"(no character sheet at {sheet_path})"}
    refs = []; labels = []; reqs = []
    for c in characters:
        cc = P.CHARACTERS.get(c)
        if cc and cc["anchor"] not in refs:
            refs.append(cc["anchor"]); labels.append(f"{c}'s ANCHOR — judge {c} against this")
    for c in characters:
        cc = P.CHARACTERS.get(c)
        feat = f" Signature features that MUST be present: {cc['key_features']}." if cc and cc.get("key_features") else ""
        reqs.append(f"{c} matches {c}'s ANCHOR exactly — design, colour, fur, face, proportions, accessories.{feat}")
    chart = P.size_chart_ref()
    if sum(1 for c in characters if P.CHARACTERS.get(c, {}).get("sizeRank")) >= 2:
        if chart:
            refs.append(chart); labels.append("the SIZE CHART — judge relative HEIGHTS against THIS, not a generic assumption")
            reqs.append("relative HEIGHTS match the SIZE CHART (do NOT assume a big adult-vs-cub gap): Luna, Keen and "
                        "Aida are CLOSE in height; Amie and Sunny are clearly smaller; Misty and Howey are taller. "
                        "Keen is a sturdy young bear close to adult-female height — NOT much smaller than Keen's Mum")
        else:
            reqs.append("relative sizes are consistent with the anchors")
    imglist = "\n".join(f"IMAGE {i+2} = {lab}" for i, lab in enumerate(labels))
    q = ("You are a STRICT character-model supervisor. IMAGE 1 is a character MODEL SHEET — a clean group "
         "line-up. The reference images:\n" + imglist + "\n\nVerify EACH character individually:\n- "
         + "\n- ".join(reqs) +
         "\n\nReply 'PASS' on line 1 if EVERY character is on-model with its signature features, otherwise "
         "'FLAG' then one short line per real break.")
    text, err = vision_verdict(q, [sheet_path] + refs)
    if err:
        return {"ok": None, "verdict": err}
    ok = text.strip().upper().startswith("PASS"); verdict = text.strip()
    an = check_anatomy(sheet_path, characters)   # the FOUNDATION must be anatomically correct — it propagates to every shot
    if an.get("ok") is False:
        ok = False
        verdict = (verdict if verdict.upper().startswith("FLAG") else "FLAG") + \
                  "\n  ANATOMY DEFECT (foundation): " + an["verdict"].replace("DEFECT", "").strip()
    return {"ok": ok, "verdict": verdict}

def run(pkg=None, scene=None, episode="Ep1"):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pkg = pkg or "../cb-output/Ep1_The_Adventure_Begins_shot_package.json"
    res = check_scene(pkg, scene, episode)
    flags = [r for r in res if r["ok"] is False]
    print(f"VISUAL QA — scene {scene}: {len(flags)} FLAG, {sum(1 for r in res if r['ok'])} pass, {len(res)} shots", flush=True)
    for r in res:
        tag = "PASS" if r["ok"] else ("FLAG" if r["ok"] is False else "ERR ")
        first = r["verdict"].splitlines()[0] if r["verdict"] else ""
        print(f"  [{tag}] {r['shot']}: {first if r['ok'] else r['verdict'][:240]}", flush=True)
    return res

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clips":          # CLIP QA: python3 cb_qa.py clips [package.json] <scene>
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        rest = sys.argv[2:]
        pkg = next((a for a in rest if a.endswith(".json")), None) or "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
        scene = next((a for a in rest if not a.endswith(".json")), None)
        res = check_clips_scene(pkg, scene)
        flags = [r for r in res if r["ok"] is False]
        print(f"CLIP QA — scene {scene}: {len(flags)} FLAG, {sum(1 for r in res if r['ok'])} pass, {len(res)} clips", flush=True)
        for r in res:
            print(f"  {r['shot']}: {r['verdict']}", flush=True)
    else:
        run(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith('.json') else None,
            sys.argv[2] if len(sys.argv) > 2 else (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].endswith('.json') else None))
