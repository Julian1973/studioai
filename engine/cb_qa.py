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

VISION_MODEL = "gemini-3.5-flash"
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

def check_join(prev_end_frame, next_open_frame):
    """THE JOIN CHECK (Julian's JOIN CONTRACT ruling, 2026-07-03): compares beat N's final frame (its SETTLE) to
    beat N+1's opening frame for the three concrete things a cut must hold across — POSITION, STATE and LIGHT.
    Report-only / advisory, same as the other frame-level checks below; never auto-fails a beat on its own. Concrete
    visual criteria per rule 17 — never a vague "does this flow" question."""
    if not (prev_end_frame and next_open_frame and os.path.exists(prev_end_frame) and os.path.exists(next_open_frame)):
        return {"ok": None, "verdict": "(missing end or open frame — cannot check this join)"}
    prompt = (
        "You are shown TWO consecutive film frames: Image 1 is the LAST frame of the shot that just ended; Image 2 "
        "is the FIRST frame of the very next shot. Check three concrete things across this cut:\n"
        "1. POSITION: is each character in the SAME screen half (left/right) as before, at a similar apparent "
        "size/distance from camera — not swapped sides, not suddenly much closer or much farther away?\n"
        "2. STATE: does any visible temporary substance or prop on a character (pollen dusting, a moustache, dirt, "
        "a held object) match between the two images — present in both or absent in both, not present in one and "
        "gone in the other?\n"
        "3. LIGHT: is the colour and brightness of the sky/environment roughly continuous (both warm/golden, or "
        "both a cooler dusk-blue, etc.) rather than one clearly warmer, cooler, brighter or darker than the other?\n"
        "Reply 'CONTINUOUS' on line 1 if all three hold. Otherwise reply 'BROKEN' then ONE short line PER broken "
        "criterion, prefixed POSITION/STATE/LIGHT, naming exactly what changed (e.g. 'POSITION: the larger bee was "
        "frame-left, now frame-right' or 'STATE: a pollen moustache is visible in image 1, gone in image 2')."
    )
    text, err = vision_verdict(prompt, [prev_end_frame, next_open_frame])
    if err:
        return {"ok": None, "verdict": err}
    return {"ok": text.strip().upper().startswith("CONTINUOUS"), "verdict": text.strip()}

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
    "JOIN_DISCONTINUITY":     "beat N's settle (final frame) and beat N+1's opening frame disagree on position, "
                              "state or light — see check_join()'s per-criterion verdict for which",
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
    if action_verb and bees_present:
        # concrete, checkable criteria — the SAME ones cb_prompts.build_keyframe_prompt's WINGS/FLIGHT-ENERGY law
        # asks the generator to produce, so QA verifies the exact thing generation was told to do, not a vague
        # "does this look dynamic enough" taste call the model will wave through.
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

def check_plate(plate_path, location_desc, layout_ref=None):
    """Visual QA for the A1 empty SCENE PLATE: correct environment + (key) NO characters in frame.
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
         + ("- The set, layout and screen-direction match the WORLD/LAYOUT reference.\n" if labels else "")
         + "Reply 'PASS' on line 1 if ALL hold (correct, empty environment), otherwise 'FLAG' then one short line per break.")
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
