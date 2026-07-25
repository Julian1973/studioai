#!/usr/bin/env python3
"""cb_render.py — THE SHOT RENDER LOOP (THE_DEFINITIVE_PIPELINE.md Gates 4-8, hybrid v2).

Consumes ONE artifact: the scene production package cb_engine.py compiles and validates.
Everything the render model must never decide was decided upstream; this module only
executes, checks, and stops for Julian.

The loop, per the spec's own gate order (voice BEFORE images — timing drives pictures):
  Gate 4  voice_scene()     one ElevenLabs text-to-dialogue call per dialogue shot, the
                            exact verbatim words from the shot's own typed dialogueLines
  Gate 5  animatic_scene()  every shot held for its real duration with its real voice —
                            the rhythm test before any expensive image or video
  Gate 6  keyframe_shot()   the opener's anticipation frame, reference-first
  Gate 7  fire_shot()       a CONTROLLED CANDIDATE BATCH per shot (default 3, range 1-4)
                            behind a spend disclosure + explicit human approval — Seedance
                            is a PROBABILISTIC generator; upstream planning controls the
                            inputs, it never guarantees the performance. Identical
                            keyframe/references/audio/prompt/settings across the batch.
  Gate 8  approve/reject    Julian selects ONE candidate (others archived) — approval
                            harvests its literal final frame as the next relay's anchor;
                            batch rejection follows THE FAILURE DECISION LADDER, hard-
                            stopping at 2 failed batches (model-limited: human redesign)
  stitch_scene()            approved clips hard-cut in order (cuts were DESIGNED upstream)

HARD REFUSALS (never a silent degrade): a package whose validation failed cannot fire;
a relay cannot fire before its source shot is approved and harvested; a missing character
reference, plate or keyframe refuses with the artifact named; a shot pending review cannot
be re-fired. Law 6 is re-asserted at fire time as defense in depth.

All paid calls live in cb_gen (cost ledger + .gen.json sidecars fire there); this module
adds a .review.json human checklist per candidate. The unit tests over this module prove
ORCHESTRATION, VALIDATION, SPENDING CONTROL and STATE TRANSITIONS only — they are never
evidence of creative render quality, which no test can prove (rule 28: no check
approximates "is it funny").

    python3 cb_render.py voice    <scene> [episode]
    python3 cb_render.py animatic <scene> [episode]
    python3 cb_render.py scenelook         <scene> [episode] [referencePath]
    python3 cb_render.py approve-scenelook <scene> [episode]
    python3 cb_render.py reject-scenelook  <scene> "<note>" [episode]
    python3 cb_render.py scenelook-library <scene> [episode]
    python3 cb_render.py select-scenelook-upload  <scene> <uploadPath>  [episode]
    python3 cb_render.py select-scenelook-library <scene> <libraryPath> [episode]
    python3 cb_render.py keyframe <scene> <shotId> [episode]
    python3 cb_render.py approve-keyframe <scene> <shotId> [episode]
    python3 cb_render.py reject-keyframe  <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py keyframe-library <scene> <shotId> [episode]
    python3 cb_render.py select-upload  <scene> <shotId> <uploadPath> [episode]
    python3 cb_render.py select-library <scene> <shotId> <libraryPath> [episode]
    python3 cb_render.py select-previous <scene> <shotId> [episode]
    python3 cb_render.py voice-status <scene> <shotId> [episode]
    python3 cb_render.py save-voice   <scene> <shotId> '<json lines>' [episode]
    python3 cb_render.py restore-voice <scene> <shotId> [episode]
    python3 cb_render.py approve-voice <scene> <shotId> [episode]
    python3 cb_render.py reject-voice  <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py seedance-status <scene> <shotId> [episode]
    python3 cb_render.py save-seedance   <scene> <shotId> "<prompt text>" [episode]
    python3 cb_render.py restore-seedance <scene> <shotId> [episode]
    python3 cb_render.py check-structure  <scene> <shotId> [episode]
    python3 cb_render.py department-prepare <scene> <look|cinematography|voice|animation|review-keyframe|review-animation|review-final> <shotId|-> [episode]
    python3 cb_render.py department-status  <scene> <stage> <shotId|-> [episode]
    python3 cb_render.py next     <scene> [episode] [--candidates N] [--spend-token T]
    python3 cb_render.py fire     <scene> <shotId> [episode] [--candidates N] [--spend-token T]
    python3 cb_render.py approve  <scene> <shotId> <candidateN> [episode]
    python3 cb_render.py reject   <scene> <shotId> "<correction>" [--category identity|geography|action-timing|instruction-ignored|other] [episode]
    python3 cb_render.py redesign-eligibility  <scene> <shotId> [episode]
    python3 cb_render.py acknowledge-redesign  <scene> <shotId> [episode]
    python3 cb_render.py metrics  <scene> [episode]
    python3 cb_render.py stitch   <scene> [episode]
    python3 cb_render.py status   <scene> [episode]
"""
import os, sys, json, re, glob, pathlib, datetime, shutil, hashlib, uuid, subprocess, tempfile
from collections import Counter
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_corpus
import cb_engine
import cb_gen
import cb_post
import cb_departments
import paths as P

MEDIA = HERE / "media" / "shots"
DUR_TOLERANCE_SEC = 1.5          # rendered clip may differ from designed duration by this much


class Refused(RuntimeError):
    """A named, deliberate refusal — never a crash, never a silent skip."""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


# ── package + ledger ────────────────────────────────────────────────────────────────────
def _pkg_path(scene, episode="Ep1"):
    """2026-07-17 (Julian's layer-boundary directive, item 2): delegates to cb_engine's
    canonical_package_path — the one place the canonical package's filename convention
    lives (cb_engine.py already owns the package CONTRACT). Name and signature unchanged
    so every existing internal caller of _pkg_path needs no changes."""
    return cb_engine.canonical_package_path(scene, episode)


def load_pkg(scene, episode="Ep1"):
    p = _pkg_path(scene, episode)
    if not p.exists():
        raise Refused(f"no production package at {p.name} — run cb_engine.py {scene} {episode} first")
    return json.load(open(p)), p


def _save(pkg, path):
    json.dump(pkg, open(path, "w"), indent=1, ensure_ascii=False)


def _shot(pkg, shot_id):
    for s in pkg["shots"]:
        if s["shotId"] == shot_id:
            return s
    raise Refused(f"no shot {shot_id} in the package")


def _ledger(pkg, shot_id):
    for e in pkg["continuityLedger"]:
        if e["shotId"] == shot_id:
            return e
    raise Refused(f"no ledger entry for {shot_id}")


def _require_valid(pkg):
    if not (pkg.get("validation") or {}).get("passed"):
        raise Refused("REFUSED — the production package failed design validation; "
                      "fix the design, never fire past a red validator")



def _approved_formula_meta(pkg, scene, shot_id, episode):
    """Which formula was in the writer's mind when this shot's animation prompt was
    authored. Stored on the approved department output at prepare time; read back here so
    the corpus can answer "which formulas are actually working" rather than guessing from
    the beat's form after the fact. Best-effort by design — a fire is never blocked
    because its provenance could not be read."""
    try:
        dept = ((pkg.get("departments") or {}).get(shot_id) or {}).get("animation") or {}
        meta = (dept.get("output") or {}).get("_formula")
        if meta:
            return meta
        shot = next((s for s in pkg.get("shots", []) if s.get("shotId") == shot_id), {})
        di = shot.get("dramaticIntent") or {}
        import cb_formulas
        _, m = cb_formulas.formula_block(di.get("primaryForm"), di.get("secondaryColour"))
        return m
    except Exception:
        return {}


def _require_own_clip(pkg, shot_id):
    """THE CLIP/CARD SEPARATION AT THE FIRE DOOR (2026-07-25). A Shot Card named by
    another card's composedOf is a MEMBER of that generation clip, not a clip of its own —
    firing it alone would render the same camera shot twice and pay for it twice. Fire the
    owning clip instead. No-op for every existing package (nothing declares composedOf)."""
    owner = cb_engine.clip_owner_of(shot_id, pkg.get("shots") or [])
    if owner:
        raise Refused(f"REFUSED — {shot_id} is a member Shot Card of generation clip "
                      f"{owner}; fire {owner}, which renders it in order. Firing a member "
                      f"alone would render and bill the same camera shot twice.")


# ── LINEAGE — the current storyboard version → matching canonical package revision ──────
# (Julian's state-integrity checkpoint, 2026-07-17): a package's own sourceStoryboard.md5
# is a claim about what it was BUILT from, captured once at compile time. It goes stale the
# moment the live storyboard file changes underneath it (a correction, a new approval). This
# is the ONE place that claim is checked against the live file's ACTUAL current bytes —
# never by filesystem existence of a rendered asset, which proves nothing about lineage.
def _storyboard_path(scene, episode="Ep1"):
    return HERE.parent / "cb-output" / "creative" / f"{episode}_scene{scene}_storyboard.json"


def _current_storyboard_md5(scene, episode="Ep1"):
    p = _storyboard_path(scene, episode)
    if not p.exists():
        return None
    return hashlib.md5(p.read_bytes()).hexdigest()


def lineage_status(pkg, scene, episode="Ep1"):
    """{"current": bool, "packageStoryboardMd5", "liveStoryboardMd5", "packageRevision"} —
    "current" is True only when the package recorded a storyboard hash AND the live
    storyboard file exists AND the two match byte-for-byte. Any other combination (no
    package, no recorded hash, no live file, or a mismatch) is NOT current — a package built
    from a superseded storyboard version must never be treated as current just because it
    exists on disk."""
    pkg_md5 = (pkg.get("sourceStoryboard") or {}).get("md5")
    live_md5 = _current_storyboard_md5(scene, episode)
    return {"current": bool(pkg_md5) and bool(live_md5) and pkg_md5 == live_md5,
            "packageStoryboardMd5": pkg_md5, "liveStoryboardMd5": live_md5,
            "packageRevision": pkg.get("revision")}


def _require_current_lineage(pkg, scene, episode):
    """HARD REFUSAL, same tier as _require_valid: a package bound to a superseded storyboard
    version can generate nothing new. Fixing this requires recompiling the package from the
    current approved storyboard — a deliberate, separate action, never silently done here."""
    lin = lineage_status(pkg, scene, episode)
    if not lin["current"]:
        raise Refused(f"REFUSED — this production package (revision {lin['packageRevision']}) "
                      f"was compiled from a superseded storyboard version "
                      f"(package md5 {str(lin['packageStoryboardMd5'])[:8]} != current storyboard "
                      f"md5 {str(lin['liveStoryboardMd5'])[:8]}). The storyboard has moved on "
                      f"since this package was built; recompile the package from the current "
                      f"approved storyboard before generating anything new — never fire against "
                      f"a stale package.")


# ── reference resolution — identity/plate refusals are keeper law (never fire blind) ────
def _characters_cfg():
    try:
        return json.load(open(P.CHARS))
    except Exception:
        return {}


def _resolve_char(name, characters_cfg):
    """Exact key first, then exact case-insensitive/apostrophe-normalized match ("FUZZBY" ->
    "Fuzzby") — never substring (the Keen/Keen's-Mum lesson). The design LLM authors
    dialogue speakers in script caps; canon keys are canonical case. Found by the first
    real-provider validation run (2026-07-16), invisible to the mocked golden path."""
    if name in characters_cfg:
        return name
    want = _norm(name)
    for k in characters_cfg:
        if _norm(k) == want:
            return k
    return name


def _char_ref(name, characters_cfg):
    rel = (characters_cfg.get(_resolve_char(name, characters_cfg)) or {}).get("anchor")
    path = (HERE / rel) if rel else None
    if not path or not path.exists():
        raise Refused(f"REFUSED — no resolvable identity reference for {name} "
                      f"(characters.json anchor: {rel}) — identity comes only from references")
    return str(path)


def _plate_path(scene, episode="Ep1"):
    """2026-07-18 (Julian's production-safety directive, item 3 — direct-input lineage):
    the CURRENTLY APPROVED plate is read from the Scene Look sidecar's own 'approved' record,
    NEVER by globbing the media folder. Under the two-phase candidate lifecycle below, a
    pending (unapproved) candidate's file sits at its OWN uniquely-named path in the SAME
    folder — a glob would risk matching it, silently anchoring a keyframe on an unreviewed
    candidate instead of the one genuinely approved artefact. This is also why a keyframe
    action can never disturb the plate: it only ever READS this pointer, never writes it."""
    st = scenelook_status(scene, episode)
    if not st["approved"] or not st["approved"].get("path") or not os.path.exists(st["approved"]["path"]):
        raise Refused(f"REFUSED — no APPROVED scene plate found for {episode} scene {scene} "
                      f"— the world anchor must be generated and approved first "
                      f"(generate-scenelook, then approve-scenelook)")
    return st["approved"]["path"]


# ── SCENE LOOK — the scene-level gate between Storyboard and Shot Production (Julian's
# 2026-07-18 directive, TWICE): the plate establishes environment/location identity, world
# scale, palette, materials/texture, lighting, weather/atmosphere and overall visual feeling
# ONLY — never shot composition, camera position, character pose or movement (those stay
# owned by each approved storyboard shot). Persisted SEPARATELY from the production package
# (cb-output/{ep}_scenelook_scene{N}.json).
#
# THE 2026-07-18 PRODUCTION-SAFETY CORRECTION (Julian's directive, the same night a failed
# regeneration attempt archived the approved, already-reviewed plate before its replacement
# had actually been produced — the file vanished from disk with the sidecar still claiming
# an approval, recovered only by hand from the archive folder): the ORIGINAL design archived
# the live plate FIRST, then generated its replacement — unsafe the instant generation itself
# can fail. Replaced with a TWO-PHASE, NON-DESTRUCTIVE candidate lifecycle:
#   1. The approved plate and its approval record are NEVER touched by a new generation.
#   2. A new generation writes to its OWN uniquely-named candidate path — never the approved
#      file's path, never a shared conventional filename.
#   3. If generation raises, NOTHING is written to the sidecar at all — since the approved
#      record was never read-then-cleared, there is nothing to roll back.
#   4. A successful candidate is presented as 'awaiting' — the approved plate stays 'current'
#      and fully usable (_plate_path above still resolves it) throughout.
#   5. Only on APPROVAL of the new candidate is the OLD approved file archived (moved, never
#      deleted) and the candidate promoted to 'approved'. Rejecting a candidate archives only
#      the candidate itself; the previously-approved plate is completely unaffected.
#
# THE SECOND HALF OF THE SAME DIRECTIVE (item 3, direct-input lineage): validity is no longer
# "did the whole storyboard's md5 change" — the plate's own brief is a pure function of
# locations.json + style.txt and has never actually depended on the storyboard at all, so
# tying its staleness to the storyboard md5 was already the wrong signal (rule 11's own
# 'sweep the pattern' lesson, found the hard way). "current" now means: does the approved
# plate's OWN recorded input signature (the compiled brief's hash) still match what the SAME
# compiler would produce right now. An SH6-only storyboard edit can never touch this, because
# it was never a real input to begin with.
def _scenelook_path(scene, episode="Ep1"):
    return HERE.parent / "cb-output" / f"{episode}_scenelook_scene{scene}.json"


def _sha256_file(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _scenelook_input_signature(scene, episode="Ep1"):
    """THE PLATE'S DIRECT INPUTS (item 3): the compiled brief text (itself sourced only from
    locations.json + style.txt — never the storyboard) plus approved references (none exist
    for the plate today; the key is kept so a future reference addition has somewhere to
    land without a second signature scheme)."""
    return {"briefHash": hashlib.sha256(_resolve_scenelook_prompt(scene, episode).encode()).hexdigest(),
            "referenceHashes": {}}


def _load_scenelook_rec(scene, episode="Ep1"):
    """Returns the CURRENT-SHAPE record ({'approved', 'candidate', 'history'}), migrating an
    older flat record ({'status','platePath','plateHash',...}) in memory — never writing the
    migration back on a plain read; only a real mutation (generate/approve/reject) persists
    the new shape, so a read-only status check can never have a side effect. A legacy
    'approved' entry (from before input signatures existed) is backfilled with the CURRENT
    signature — honest, not a guess: the plate's brief is a pure function of already-
    unchanged canon files, so 'what it was approved against' and 'what the compiler produces
    right now' are provably the same text for any record that predates this correction."""
    sc_path = _scenelook_path(scene, episode)
    if not sc_path.exists():
        return {"approved": None, "candidate": None, "history": []}
    rec = json.load(open(sc_path))
    if "approved" in rec or "candidate" in rec:
        return rec   # already the current shape
    # legacy flat shape migration
    approved = None
    history = list(rec.get("history") or [])
    if rec.get("status") == "approved" and rec.get("platePath"):
        approved = {"path": rec["platePath"], "hash": rec.get("plateHash"),
                    "inputSignature": _scenelook_input_signature(scene, episode),
                    "approvedAt": rec.get("approvedAt"), "reviewedBy": rec.get("reviewedBy")}
    return {"approved": approved, "candidate": None, "history": history}


def _save_scenelook_rec(rec, scene, episode="Ep1"):
    sc_path = _scenelook_path(scene, episode)
    sc_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(rec, open(sc_path, "w"), indent=1, ensure_ascii=False)


def scenelook_status(scene, episode="Ep1"):
    """{"status": "none"|"awaiting"|"approved"|"stale"|"rejected", "current": bool,
    "approved": {...}|None, "candidate": {...}|None, "history": [...]} — NEVER inferred from
    a file's mere existence at a conventional path. "awaiting" means a candidate is pending a
    decision (the approved plate, if any, is UNCHANGED and still separately available via
    "approved"). "stale" means the approved plate's own input signature no longer matches
    what the compiler produces right now (locations.json or style.txt changed) — never
    triggered by an unrelated storyboard/shot edit."""
    rec = _load_scenelook_rec(scene, episode)
    approved, candidate = rec.get("approved"), rec.get("candidate")
    current_sig = _scenelook_input_signature(scene, episode)
    if candidate:
        return {"status": "awaiting", "current": False, "approved": approved,
                "candidate": candidate, "history": rec.get("history", [])}
    if approved:
        approved_ok = os.path.exists(approved.get("path") or "")
        sig_current = approved.get("inputSignature") == current_sig
        status = "approved" if (approved_ok and sig_current) else "stale"
        return {"status": status, "current": (status == "approved"), "approved": approved,
                "candidate": None, "history": rec.get("history", [])}
    hist = rec.get("history", [])
    last = hist[-1] if hist else None
    status = "rejected" if (last and last.get("outcome") == "rejected") else "none"
    return {"status": status, "current": False, "approved": None, "candidate": None,
            "history": hist}


def _require_current_scenelook(scene, episode="Ep1"):
    """HARD REFUSAL, same tier as _require_valid — no keyframe can be generated (Julian:
    'every keyframe requires ... current approved Scene Look Plate'). Checked entirely
    against the plate's OWN direct-input signature — never the storyboard/package."""
    st = scenelook_status(scene, episode)
    if st["status"] != "approved" or not st["current"]:
        raise Refused(f"REFUSED — Scene Look Plate is '{st['status']}', not a current approval "
                      f"for scene {scene} — the environment/palette/lighting anchor must be "
                      f"approved (approve-scenelook) before any keyframe can be generated")


def _compile_scenelook_prompt(scene, episode="Ep1"):
    """THE FIDELITY LAW, applied to the plate: every clause is quoted VERBATIM from the
    scene's own canon locations.json entry (look/lighting/weather/colorTemperature/
    definingFeature — already-authored environment truth, nothing invented here) plus the
    show's own global style law. Deliberately EXCLUDES that same entry's lens/cameraHeight
    fields — camera framing is a shot-composition concern, never the plate's job (Julian's
    own scope line, and locations.json's own "look" text already says as much: "No
    characters, no homes, no extra props")."""
    loc_path = HERE.parent / "shows" / "crystal-bears" / "canon" / "locations.json"
    style_path = HERE.parent / "shows" / "crystal-bears" / "laws" / "style.txt"
    locs = json.load(open(loc_path)) if loc_path.exists() else {}
    entry = (locs.get(episode) or {}).get(str(scene)) or {}
    style = style_path.read_text().strip() if style_path.exists() else ""
    parts = [style] if style else []
    for key in ("look", "lighting", "weather", "colorTemperature", "definingFeature"):
        v = (entry.get(key) or "").strip()
        if v:
            parts.append(v)
    if not parts:
        raise Refused(f"REFUSED — no canon environment data found for {episode} scene {scene} "
                      f"in locations.json — the Scene Look Plate must be built from already-"
                      f"authored environment truth, never invented")
    return " ".join(parts)


def _resolve_scenelook_prompt(scene, episode="Ep1"):
    """Exact plate prompt: approved Look worker output, otherwise the legacy canon compiler.

    Reads the raw sidecar rather than scenelook_status/_load_scenelook_rec so the direct-input
    signature can call it without a migration/signature recursion.
    """
    base = _compile_scenelook_prompt(scene, episode)
    path = HERE.parent / "cb-output" / f"{episode}_scenelook_scene{scene}.json"
    if not path.exists():
        return base
    try:
        rec = json.load(open(path))
        output = (((rec.get("departmentWork") or {}).get("look") or {})
                  .get("approved") or {}).get("output") or {}
        return output.get("providerPrompt") or base
    except Exception:
        return base


def approved_look_prompt(scene, episode="Ep1"):
    """The Look Development specialist's own approved providerPrompt, verbatim, or None if
    no direction has been approved yet (a pending/unapproved candidate never counts — the
    exact bypass that let a near-empty canon fallback fire the 2026-07-19 dog-and-fox
    misfire). This is the ONLY prompt source generate_scenelook_plate is now allowed to use."""
    rec = _load_scenelook_rec(scene, episode)
    approved = ((rec.get("departmentWork") or {}).get("look") or {}).get("approved")
    prompt = ((approved or {}).get("output") or {}).get("providerPrompt")
    return prompt if (prompt or "").strip() else None


# ── THE SCENE LOOK WORKING PROMPT (Julian's directive, 2026-07-19 — "I want to be able to
# edit the prompts to the APIs in every section and save them"): the Scene Look sibling of
# THE KEYFRAME/VOICE/ANIMATION WORKING PROMPT controls above. Scene Look already had an edit
# path (Brief Look Development, edit the specialist's own candidate, then approve) — but
# unlike the other three generative stages, there was no way to tweak the text AFTER
# approval without re-running the whole specialist consult. This adds that same direct,
# no-LLM-call edit-and-save layer on top of an existing approval. It does NOT weaken THE
# APPROVED-SPECIALIST HARD GATE above — a working override can only ever be saved once a
# real Look Development approval already exists, and generate_scenelook_plate still refuses
# outright with no approval at all, exactly as before.
def scenelook_working_status(scene, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedPrompt": str|None, "currentPrompt": str|None (working
    override if saved, else the approved Look Development prompt — exactly what will be
    submitted), "isWorking": bool, "savedAt": str|None}. Both prompt fields are None until a
    Look Development brief has been approved at least once — there is nothing to edit before
    that."""
    rec = _load_scenelook_rec(scene, episode)
    approved_prompt = approved_look_prompt(scene, episode)
    working = rec.get("workingPrompt")
    is_working = bool(working and working.get("text"))
    current = working["text"] if is_working else approved_prompt
    return {"approvedPrompt": approved_prompt, "currentPrompt": current,
            "isWorking": is_working, "savedAt": (working or {}).get("savedAt")}


def save_scenelook_working(scene, prompt_text, episode="Ep1", reviewed_by="Julian", log=print):
    """Saves a scene-level WORKING Scene Look prompt — the approved specialist brief's own
    providerPrompt is never touched, never rewritten. NEVER calls cb_gen — this is a save, not
    a generation. Requires an approved Look Development brief to already exist (the same hard
    gate generate_scenelook_plate itself enforces) — a working edit is layered ON TOP of an
    approval, never a way to skip needing one."""
    if not approved_look_prompt(scene, episode):
        raise Refused("REFUSED — Approve Look Development direction first; a working edit "
                      "can only be layered on top of an already-approved brief.")
    text = str(prompt_text or "").strip()
    if not text:
        raise Refused(f"REFUSED — scene {scene}'s working Scene Look prompt cannot be blank")
    rec = _load_scenelook_rec(scene, episode)
    rec["workingPrompt"] = {"text": text, "savedAt": _now(), "savedBy": reviewed_by}
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK WORKING PROMPT SAVED — scene {scene} ({len(text.split())} words, no "
        f"plate generated)")
    return rec["workingPrompt"]


def restore_scenelook_working(scene, episode="Ep1", log=print):
    """Clears the working override — generate_scenelook_plate reverts to submitting the
    approved Look Development brief's own providerPrompt, exactly as if no working version
    had ever been saved. Never generates a plate."""
    rec = _load_scenelook_rec(scene, episode)
    rec["workingPrompt"] = None
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK WORKING PROMPT RESTORED — scene {scene}: reverted to the approved brief")


def _resolve_scenelook_prompt_for_fire(scene, episode="Ep1"):
    """The exact prompt generate_scenelook_plate submits: a saved working override if present,
    else the approved Look Development specialist's own providerPrompt. Callable only once the
    hard gate in generate_scenelook_plate has already confirmed an approval exists."""
    rec = _load_scenelook_rec(scene, episode)
    working = rec.get("workingPrompt")
    if working and working.get("text"):
        return working["text"]
    return approved_look_prompt(scene, episode)


def generate_scenelook_plate(scene, episode="Ep1", reference_path=None, log=print):
    """GENERATE SCENE {N} LOOK PLATE — ONE IMAGE. Generates exactly one plate CANDIDATE to
    its own unique path; the currently-approved plate (if any) and its approval record are
    completely untouched by this call, win or lose (2026-07-18 production-safety
    correction). Refuses if a candidate is already pending a decision (reject it first).
    Never auto-approved: a successful generation always lands as 'awaiting'.

    reference_path (2026-07-19 fix): OPTIONAL, and only ever what the CALLER explicitly
    passes in — this function never looks in the Asset Library or anywhere else on its
    own. None (the default) means no reference at all, which now correctly routes to a
    text-to-image call in cb_gen (see that module's 2026-07-19 fix) instead of a
    guaranteed-422 empty edit-mode request. A real path here means a genuine, explicitly
    selected location/style reference, routed to the edit endpoint with that one image.

    THE APPROVED-SPECIALIST HARD GATE (2026-07-19 — closing the bypass that produced the
    dog-and-fox misfire): this call now REFUSES outright unless Scene {N}'s own Look
    Development specialist direction has been APPROVED first — never a pending/unapproved
    candidate, and never the old canon-compiled fallback (_resolve_scenelook_prompt /
    _compile_scenelook_prompt are untouched and still used elsewhere for staleness
    signatures, but are no longer a prompt SOURCE for a real generation call). The exact
    approved providerPrompt is what gets submitted, verbatim — nothing rebuilt, reworded or
    truncated on the way to cb_gen — UNLESS Julian has saved a working override on top of
    that approval (THE SCENE LOOK WORKING PROMPT, below), in which case that edited text is
    what's actually sent instead (_resolve_scenelook_prompt_for_fire)."""
    st = scenelook_status(scene, episode)
    if st["candidate"]:
        raise Refused(f"REFUSED — scene {scene} already has a Scene Look candidate awaiting "
                      f"a decision; reject it first, or approve it, before generating another")
    if reference_path is not None and not pathlib.Path(reference_path).exists():
        raise Refused(f"REFUSED — reference_path does not exist: {reference_path}")
    if not approved_look_prompt(scene, episode):
        raise Refused("REFUSED — Approve Look Development direction first.")
    # 2026-07-19: resolves through a saved WORKING override if Julian has edited-and-saved
    # one on top of the approval (scenelook_working_status/save_scenelook_working, above) —
    # the hard gate itself is unchanged, still requiring a real approval to exist at all.
    prompt = _resolve_scenelook_prompt_for_fire(scene, episode)
    _require_confirmed_billing("fal")
    (HERE / "media").mkdir(parents=True, exist_ok=True)
    out = HERE / "media" / f"{episode}_S{scene}_plate_candidate_{uuid.uuid4().hex[:8]}.png"
    refs = [str(reference_path)] if reference_path else []
    cb_gen.generate_image(prompt, refs=refs, out=str(out), production_route="cb_render")
    # ONLY reached on a successful generation — the approved record above was never read for
    # mutation, so a failure here (an exception from generate_image) leaves the sidecar file
    # byte-for-byte as it was before this call, and the approved plate untouched on disk.
    rec = _load_scenelook_rec(scene, episode)
    rec["candidate"] = {"path": str(out), "hash": _sha256_file(out),
                        "inputSignature": _scenelook_input_signature(scene, episode),
                        "referencePath": str(reference_path) if reference_path else None,
                        "generatedAt": _now()}
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK — {out.name} generated as a CANDIDATE ({'with 1 explicit reference' if reference_path else 'no reference — text-to-image'}; "
        f"awaiting approval — the previously-approved plate, if any, is unchanged and still "
        f"current) — approve-scenelook or reject-scenelook")
    return str(out)


def approve_scenelook(scene, episode="Ep1", reviewed_by="Julian", log=print):
    """Promotes the pending candidate to 'approved'. Only NOW — never before — is a
    previously-approved plate archived (moved, never deleted); the new candidate becomes
    the current plate without any file ever being renamed or moved into place."""
    rec = _load_scenelook_rec(scene, episode)
    cand = rec.get("candidate")
    if not cand:
        # THE STALE RE-BLESS (2026-07-25, Julian live-blocked — "then i cant move forward
        # becasue scene look isnt approved"): an approved plate whose own input brief
        # (locations.json/style.txt) changed after approval reads as 'stale', and the
        # Studio's own stale-state button ("Apply (current brief)") lands HERE — where the
        # old candidate-only contract could only refuse, leaving no path to say "the same
        # image still holds under the new brief." Re-approving with no candidate now
        # re-stamps the approved plate's signature to the CURRENT brief — the human's own
        # explicit re-bless of the identical, unchanged image; never a silent auto-heal.
        appr = rec.get("approved")
        if appr and os.path.exists(appr.get("path") or ""):
            cur_sig = _scenelook_input_signature(scene, episode)
            if appr.get("inputSignature") == cur_sig:
                raise Refused(f"REFUSED — Scene Look for scene {scene} is already approved "
                              f"and current; nothing awaits approval")
            appr["inputSignature"] = cur_sig
            appr["reapprovedAt"] = _now()
            appr["reviewedBy"] = reviewed_by
            _save_scenelook_rec(rec, scene, episode)
            log(f"SCENE LOOK RE-BLESSED — {os.path.basename(appr['path'])} re-approved by "
                f"{reviewed_by} against the current brief (same image, signature re-stamped)")
            return appr["path"]
        raise Refused(f"REFUSED — Scene Look for scene {scene} has no candidate awaiting approval")
    old = rec.get("approved")
    if old and old.get("path") and os.path.exists(old["path"]):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "scenelook_superseded" / ts
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / os.path.basename(old["path"])
        shutil.move(old["path"], dest)
        rec.setdefault("history", []).append({**old, "outcome": "superseded",
                                               "supersededAt": _now(),
                                               "archivedFile": str(dest.relative_to(HERE))})
    rec["approved"] = {**cand, "approvedAt": _now(), "reviewedBy": reviewed_by}
    rec["candidate"] = None
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK APPROVED — {os.path.basename(cand['path'])} by {reviewed_by}")
    return cand["path"]


def reject_scenelook(scene, note, episode="Ep1", reviewed_by="Julian", log=print):
    """Rejection ARCHIVES the CANDIDATE only (moved, never deleted) — never the currently-
    approved plate, which stays live, approved and current exactly as it was."""
    if not (note or "").strip():
        raise Refused("REFUSED — a Scene Look rejection requires a plain-language note")
    rec = _load_scenelook_rec(scene, episode)
    cand = rec.get("candidate")
    if not cand:
        raise Refused(f"REFUSED — Scene Look for scene {scene} has no candidate to reject")
    archived_rel = None
    if cand.get("path") and os.path.exists(cand["path"]):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "scenelook_rejected" / ts
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / os.path.basename(cand["path"])
        shutil.move(cand["path"], dest)
        archived_rel = str(dest.relative_to(HERE))
    rec.setdefault("history", []).append({**cand, "outcome": "rejected", "rejectedAt": _now(),
                                           "reviewedBy": reviewed_by, "rejectedNote": note.strip(),
                                           "rejectedArchivedFile": archived_rel})
    rec["candidate"] = None
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK REJECTED — {note}\n  archived -> {archived_rel or '(no file was present)'}"
        f"\n  the previously-approved plate (if any) is unaffected")
    return archived_rel


def unapprove_scenelook(scene, episode="Ep1", note="", reviewed_by="Julian", log=print):
    """UNDO THE SCENE LOOK APPROVAL — Julian's own redo door (2026-07-25, his direct ask:
    "I should be able to unassign and do that phase again"). The approved plate moves BACK
    to being the pending CANDIDATE (awaiting a fresh decision) — never deleted, never
    archived by this call; re-approving it restores it unchanged, rejecting/replacing it
    follows the existing candidate flow. Mirrors unapprove_department's reversible-action
    semantics: un-approving is always safe and never destroys work."""
    rec = _load_scenelook_rec(scene, episode)
    appr = rec.get("approved")
    if not appr:
        raise Refused(f"REFUSED — Scene Look for scene {scene} has no approval to undo")
    if rec.get("candidate"):
        raise Refused(f"REFUSED — Scene Look for scene {scene} already has a candidate "
                      f"awaiting a decision; decide that first (approve/reject), then "
                      f"un-approve if still needed")
    rec.setdefault("history", []).append({**appr, "outcome": "unapproved",
                                           "unapprovedAt": _now(), "reviewedBy": reviewed_by,
                                           "unapprovedNote": (note or "").strip() or None})
    cand = {k: v for k, v in appr.items() if k not in ("approvedAt", "reviewedBy")}
    rec["candidate"] = cand
    rec["approved"] = None
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK UN-APPROVED by {reviewed_by} — {os.path.basename(appr.get('path',''))} "
        f"is back to AWAITING your decision (re-approve, reject, upload, pick from library, "
        f"or generate fresh); nothing was deleted")
    return True


def select_scenelook_source(scene, mode, episode="Ep1", upload_path=None, library_path=None,
                              reviewed_by="Julian", log=print):
    """THE NON-GENERATION SCENE LOOK SOURCES (2026-07-19 — "still not letting me upload a
    library image, i select it then it wants to generate"): mirrors select_keyframe_source's
    own zero-cost pattern exactly. 'upload' (a human-supplied file, preserved unchanged at
    its own permanent path AND copied to an immutable scene-owned candidate) and 'library'
    (a copy of any reusable reference — a scenelook_reference_library item, a location-
    manifest plate, a house image, an uploaded scene ref; the source file itself is never
    touched) both become the CANDIDATE DIRECTLY. NEVER calls cb_gen — no provider call, no
    cost, no disclosure needed. Refuses if a candidate is already pending (matching
    generate_scenelook_plate's own rule — reject it first)."""
    if mode not in ("upload", "library"):
        raise Refused(f"REFUSED — unknown Scene Look source {mode!r}; must be upload or library")
    st = scenelook_status(scene, episode)
    if st["candidate"]:
        raise Refused(f"REFUSED — scene {scene} already has a Scene Look candidate awaiting "
                      f"a decision; reject it first, or approve it, before selecting another")
    if mode == "upload":
        if not upload_path or not os.path.exists(upload_path):
            raise Refused("REFUSED — no uploaded file found to select")
        # PRESERVE THE ORIGINAL ASSET — a permanent copy, distinct from and never touched by
        # the scene's own immutable candidate copy made below.
        preserved_dir = HERE / "media" / "uploads"
        preserved_dir.mkdir(parents=True, exist_ok=True)
        ext = pathlib.Path(upload_path).suffix or ".png"
        preserved = preserved_dir / f"{episode}_S{scene}_scenelook_upload_{uuid.uuid4().hex[:8]}{ext}"
        shutil.copy2(upload_path, preserved)
        src_for_copy = str(preserved)
        source_note = {"source": "uploaded", "preservedOriginal": str(preserved)}
    else:  # library
        if not library_path or not os.path.exists(library_path):
            raise Refused("REFUSED — the selected library item no longer exists on disk")
        src_for_copy = library_path
        source_note = {"source": "library", "libraryOriginal": library_path}
    (HERE / "media").mkdir(parents=True, exist_ok=True)
    ext = pathlib.Path(src_for_copy).suffix or ".png"
    out = HERE / "media" / f"{episode}_S{scene}_plate_candidate_{uuid.uuid4().hex[:8]}{ext}"
    shutil.copy2(src_for_copy, out)
    rec = _load_scenelook_rec(scene, episode)
    rec["candidate"] = {"path": str(out), "hash": _sha256_file(out),
                        "inputSignature": _scenelook_input_signature(scene, episode),
                        "referencePath": None, "generatedAt": _now(), **source_note}
    _save_scenelook_rec(rec, scene, episode)
    log(f"SCENE LOOK SELECTED — {out.name} ({source_note['source']}, no generation cost) — "
        f"awaiting approval — the previously-approved plate, if any, is unchanged and still "
        f"current) — approve-scenelook or reject-scenelook")
    return str(out)


def scenelook_reference_library(scene, episode="Ep1"):
    """READ-ONLY, zero cost: every prior Scene Look artefact for THIS scene the human may
    deliberately choose to feed in as a REFERENCE for a fresh generation (2026-07-19 UX
    fix — exposing the button, not a redesign). Unlike keyframe_library_for_shot's
    'library' choice (which becomes the candidate directly, no generation), a Scene Look
    library pick is never used as the plate itself — it is always passed to
    generate_scenelook_plate as reference_path, same as an uploaded image, so a real
    provider call still fires and the disclosure modal still applies. Lists the currently-
    pending candidate (if any), the currently-approved plate (if any), and every
    rejected/superseded history entry whose archived file still exists on disk — each
    checked for its own file's existence, an archived record whose file was separately
    removed is silently omitted, never offered as a dead link. Never auto-selects or
    mutates anything; this only lists. Scoped to THIS scene's own history only — a future
    cross-scene/cross-episode reuse library is a separate, larger feature, not built here."""
    rec = _load_scenelook_rec(scene, episode)
    items = []

    def _add(path, at, outcome, note=None):
        if path and os.path.exists(path):
            items.append({"path": str(path), "at": at, "outcome": outcome, "note": note})

    cand = rec.get("candidate")
    if cand:
        _add(cand.get("path"), cand.get("generatedAt"), "pending", None)
    appr = rec.get("approved")
    if appr:
        _add(appr.get("path"), appr.get("approvedAt"), "approved", None)
    for h in (rec.get("history") or []):
        if h.get("outcome") == "rejected":
            rel = h.get("rejectedArchivedFile")
            _add(str(HERE / rel) if rel else None, h.get("rejectedAt"), "rejected", h.get("rejectedNote"))
        elif h.get("outcome") == "superseded":
            rel = h.get("archivedFile")
            _add(str(HERE / rel) if rel else None, h.get("supersededAt"), "superseded", None)
    items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return items


def _slot_paths(shot, slots_key, anchor_path, scene, episode, characters_cfg):
    """The image upload list, in the package's own persisted slot order — the order is the
    contract; a fire that reorders references invalidates every inline @图N binding."""
    out = []
    for slot in sorted((k for k in shot[slots_key] if k.startswith("@图")),
                       key=lambda k: int(k[2:])):
        role = shot[slots_key][slot]
        if role in ("opening keyframe", "previous shot final frame"):
            out.append(anchor_path)
        elif role == "scene plate":
            out.append(_plate_path(scene, episode))
        elif role.startswith("pollen effect target"):
            # THE EFFECT-TARGET REFERENCE (Julian's split-generation block, 2026-07-23):
            # a material/colour-only reference — here, the correct loose golden pollen
            # texture harvested from an archived take — prepared per shot at a fixed,
            # deterministic path. The prompt text declares its scope (material and colour
            # only, never composition/pose/camera); this resolver only locates the file.
            p = str(MEDIA / f"{episode}_{shot['shotId']}_effect_target.png")
            if not os.path.exists(p):
                raise Refused(f"REFUSED — {shot['shotId']} declares an effect-target "
                              f"reference but no prepared frame exists at {p}")
            out.append(p)
        elif role.startswith("face state"):
            # THE FACE-STATE REFERENCE (Julian, 2026-07-23 — "create the perfect fuzzby face
            # with the moustache and goatee and then use that as the reference"): a prepared
            # image of the character's exact intended face state (e.g. golden pollen
            # moustache AND golden goatee), fighting the model's own image-prior composites
            # with an image instead of words — 9 takes proved text loses that fight. Same
            # fixed-path pattern as the effect target above.
            p = str(MEDIA / f"{episode}_{shot['shotId']}_face_state.png")
            if not os.path.exists(p):
                raise Refused(f"REFUSED — {shot['shotId']} declares a face-state "
                              f"reference but no prepared frame exists at {p}")
            out.append(p)
        else:
            out.append(_char_ref(role, characters_cfg))
    return out


# ── LIVE DEPARTMENTS — specialist prepares → Julian edits/approves → existing renderer ──
# These records live inside the existing scene/shot ledgers.  They are not another package,
# another compiler or another gate state.  A worker call creates only a visible candidate;
# approving it changes which exact provider text the existing render function resolves.
_DEPARTMENT_WORKERS = {
    "look": ("Look Development", "Cinematographer / DP", "cinematographer"),
    "cinematography": ("Cinematography", "Cinematographer / DP", "cinematographer"),
    "voice": ("Voice", "Voice Director", "voice-director"),
    "animation": ("Animation", "Animation Director / Camera", "camera"),
    "review-keyframe": ("Director Review", "Director Review / Continuity Supervisor", "continuity"),
    "review-animation": ("Director Review", "Director Review / Continuity Supervisor", "continuity"),
    "review-final": ("Final & Post", "Post Supervisor", "post"),
}


def _department_container(pkg, scene, shot_id, stage, episode="Ep1"):
    """Return (container, save_fn). Look work is scene-level; everything else is per shot."""
    if stage == "look":
        rec = _load_scenelook_rec(scene, episode)
        work = rec.setdefault("departmentWork", {}).setdefault(stage,
            {"approved": None, "candidate": None, "history": []})
        return work, lambda: _save_scenelook_rec(rec, scene, episode)
    if stage == "review-final":
        work = pkg.setdefault("departmentWork", {}).setdefault(stage,
            {"approved": None, "candidate": None, "history": []})
        return work, lambda: None
    if not shot_id:
        raise Refused(f"REFUSED — department '{stage}' requires a shotId")
    led = _ledger(pkg, shot_id)
    work = led.setdefault("departmentWork", {}).setdefault(stage,
        {"approved": None, "candidate": None, "history": []})
    return work, lambda: None


def department_status(scene, shot_id=None, episode="Ep1", stage=None):
    """Read-only department roster + candidate/approval state. Never calls an LLM."""
    pkg, _ = load_pkg(scene, episode)
    if stage:
        if stage not in _DEPARTMENT_WORKERS:
            raise Refused(f"unknown department stage '{stage}'")
        work, _ = _department_container(pkg, scene, shot_id, stage, episode)
        dep, worker, skill = _DEPARTMENT_WORKERS[stage]
        # THE FIVE-ITEM COMPULSORY CHECKLIST (2026-07-19, item 6): read alongside the raw
        # candidate/approval state so the Studio panel can show it without a second round
        # trip — never gates anything itself, that's still _require_approved_department's
        # job at the actual paid-route choke point.
        readiness = department_readiness(pkg, scene, stage, shot_id, episode)
        return {"stage": stage, "department": dep, "worker": worker,
                "skill": f"crystal-bears-{skill}", "readiness": readiness, **work}
    out = []
    for rec in cb_departments.roster():
        item = dict(rec)
        mapped = {"look": "look", "cinematography": "cinematography", "voice": "voice",
                  "animation": "animation"}.get(rec["id"])
        if mapped:
            try:
                work, _ = _department_container(pkg, scene, shot_id, mapped, episode)
                item["state"] = ("awaiting" if work.get("candidate") else
                                 "approved" if work.get("approved") else "ready")
            except Refused:
                item["state"] = "locked"
        out.append(item)
    return {"departments": out}


def _scene_context(pkg, scene, episode):
    loc_path = HERE.parent / "shows/crystal-bears/canon/locations.json"
    style_path = HERE.parent / "shows/crystal-bears/laws/style.txt"
    locs = json.load(open(loc_path)) if loc_path.exists() else {}
    sb_path = _storyboard_path(scene, episode)
    sb = json.load(open(sb_path)) if sb_path.exists() else {}
    return {"episode": episode, "scene": str(scene), "sceneName": pkg.get("sceneName"),
            "approvedStoryboardScene": sb.get("scene"),
            "selectedTreatment": sb.get("treatmentSelection"),
            "locationCanon": (locs.get(episode) or {}).get(str(scene)),
            "styleLaw": style_path.read_text().strip() if style_path.exists() else ""}


# THE DEPENDENCY-SIGNATURE VERSION (2026-07-20, Julian — "one bounded legacy-approval
# revalidation path"; corrected the same day, FINAL COMPLETION DIRECTIVE — "correct the
# dependency graph permanently"): bumped ONLY when the actual SET of inputs a department's
# freshness signature legitimately depends on is deliberately corrected (never for an
# ordinary content change, which the existing sourceHash equality check already covers on
# its own). v1 = the formula in force before 2026-07-20, where Cinematography's context
# wrongly included Voice's own approved output and working-prompt drafts (the self-reference
# bug fixed the same day). v2 = a same-day intermediate fix that excluded those three fields
# but still hashed the ENTIRE shot record, the whole approved-Scene-Look object and an
# undifferentiated orderedAttachments collection — still too broad, and still capable of
# flagging Cinematography stale over a field it never actually consumed (exactly the false
# positive the FINAL COMPLETION DIRECTIVE names). v3 = THE PERMANENT FIX: every generative
# stage's freshness signature is now built from an EXPLICIT, NAMED, stage-specific
# dependency projection (_cinematography_dependency_context/_voice_dependency_context/
# _animation_dependency_context, below) that lists exactly the fields that stage may depend
# upon — never the broad shot/ledger/approval objects a future storyboard/UI field could
# silently leak through. An approval's own stored `signatureVersion` records which formula
# produced its `sourceHash`; a mismatch against this constant is what triggers the legacy-
# revalidation path in department_legacy_status/revalidate_department below — never treated
# as an ordinary "stale, re-prepare and re-approve" case, since re-preparing would mean
# rerunning the specialist over creative content that never actually changed.
_DEPT_SIGNATURE_VERSION = 3

# ── THE CHARGE VERSION (2026-07-25) ────────────────────────────────────────────────────
# THE GAP THIS CLOSES, found by Julian asking a plain question — "is shot 2 now the right
# direction and prompt?" It was not, and nothing in the system could tell: the freshness
# signature is built from SHOT DATA (keyframe, audio, references, staging fields), so it
# correctly answers "did the material change?" and is structurally blind to "did the
# INSTRUCTIONS we gave the writer change?". Tonight's uncaging rewrote the animation
# writer's entire charge — ceilings gone, vocabulary bans lifted, the brief reframed
# around what the shot does to the viewer — and every previously-approved direction still
# read `current`, because its inputs genuinely hadn't moved. It would have fired
# pre-uncaging text under a post-uncaging engine and nobody would have known.
#
# Bumping this marks every existing animation/cinematography direction STALE, which forces
# an ordinary re-prepare + re-approve under the new charge. That is the correct semantic —
# NOT _DEPT_SIGNATURE_VERSION, whose own doctrine reserves a bump for "the signature
# FORMULA changed" and routes it to legacy revalidation specifically to avoid rerunning a
# specialist over creative content that never changed. Here the content didn't change but
# the instructions did, and rerunning the specialist is exactly what we want.
#
# BUMP THIS whenever a department's system prompt / craft curriculum / formula gate
# materially changes what the writer is being asked to do.
_DEPT_CHARGE_VERSION = 3      # v2 = the no-straitjacket charge (2026-07-25)


def _shot_context(pkg, shot, led, scene, episode, stage=None, legacy_version=None):
    """THE SELF-REFERENCE FIX (2026-07-19, found while seeding a test fixture for the
    department-gate hardening, then confirmed as a REAL production bug, not a test
    artefact): currentVoiceDirection/humanWorkingVoice/humanWorkingAnimationPrompt are
    genuine, legitimate cross-department inputs — e.g. Animation's own direction should
    depend on what Voice actually decided — but a stage's OWN currently-approved output or
    OWN saved working override must NEVER be folded into ITS OWN freshness/preparation
    signature. Without this, the instant a Voice Direction was approved, this same context
    builder (called both at prepare-time, to compute the sourceHash that gets stored, and
    again at every later freshness check) would recompute currentVoiceDirection as non-None
    where it was None when first hashed — making EVERY real approval go stale against its
    own sourceHash on the very next check, a guaranteed false-positive that would have
    silently broken every voice/animation fire in production, not just tests.

    legacy_version is None for every REAL caller (prepare_department's own specialist call,
    and the normal current-freshness check) — it only ever takes a value when the legacy-
    revalidation path (department_legacy_status) deliberately reconstructs an OLDER formula's
    exact context shape, purely to test whether an existing approval's stored sourceHash is
    explained by stale FORMULA SCOPE rather than genuine content drift. legacy_version=1
    reproduces the pre-2026-07-20 shape (cinematography keeps the three self-referential
    fields) — never used by any paid-generation route."""
    ctx = {"episode": episode, "scene": str(scene), "shot": shot,
           "approvedSceneLook": scenelook_status(scene, episode).get("approved"),
           "currentVoiceDirection": (led.get("departmentWork", {}).get("voice", {})
                                     .get("approved")),
           "humanWorkingVoice": led.get("workingVoice"),
           "humanWorkingAnimationPrompt": led.get("workingSeedancePrompt")}
    if stage == "voice":
        ctx.pop("currentVoiceDirection", None)
        ctx.pop("humanWorkingVoice", None)
    elif stage == "animation":
        ctx.pop("humanWorkingAnimationPrompt", None)
    elif stage == "cinematography" and legacy_version != 1:
        # THE KEYFRAME HAS NO LEGITIMATE DEPENDENCY ON VOICE OR ANIMATION (2026-07-20,
        # Julian, live in the Studio — "there is no way for me to approve and generate
        # things"): the Cinematographer/DP composes a STILL IMAGE (the opening frame); it
        # has zero legitimate reason to reference what Voice's own performance direction
        # says, or what a human working-edit exists for Voice's/Animation's own prompt
        # drafts. Before this fix, approving Voice Direction alone flipped Cinematography's
        # own freshness signature — a real, confirmed false-positive STALE cascade (the
        # exact self-reference bug class the voice/animation branches above were already
        # fixed for in the department-gate hardening pass, just never extended to this
        # stage, the one with the fewest legitimate cross-department dependencies of all).
        # This context feeds BOTH the real specialist call (prepare_department) and the
        # freshness fingerprint (department_freshness) via the same _shot_context call —
        # removing these fields fixes the content leak into the DP's own prompt AND the
        # spurious staleness in one place. Skipped only when legacy_version==1, i.e. the
        # revalidation path is deliberately reconstructing the OLD (v1) shape to compare
        # against an existing approval's stored hash — never for a real specialist call.
        ctx.pop("currentVoiceDirection", None)
        ctx.pop("humanWorkingVoice", None)
        ctx.pop("humanWorkingAnimationPrompt", None)
    return ctx


# ── THE EXPLICIT STAGE-SPECIFIC DEPENDENCY PROJECTIONS (2026-07-20, FINAL COMPLETION
# DIRECTIVE, item 1 — "Replace broad freshness inputs ... with explicit stage-specific
# projections"): each function below is an ALLOW-LIST, not an exclude-list — it names every
# field a stage's freshness/staleness signature may depend upon, and nothing else. This is
# the PERMANENT replacement for feeding the whole shot record / whole approved-object /
# undifferentiated attachment collection into _department_signature. These functions are
# used ONLY to compute what gets HASHED for staleness purposes — they are never what a
# specialist actually reads (that stays _shot_context's own richer, unchanged context,
# still built inside prepare_department for the real LLM call; a specialist benefiting from
# more surrounding context is fine, it is STALENESS that must never be triggered by a field
# a stage doesn't actually depend on).
def _cinematography_dependency_context(pkg, shot, scene, episode):
    """Cinematography Direction may depend ONLY upon: the shot's own locked visual-brief/
    staging fields it actually composes from; the current approved Scene Look's own content
    hash (never its approval metadata/timestamps/reviewer); and the current character/
    environment reference files' own byte content (never merely their path). It must NOT
    depend upon a generated keyframe candidate/approval, Voice Direction/approval/audio
    status, Animation Direction/status, review records, candidate/rejection/cost ledgers,
    timestamps, UI state, another department's working draft, or downstream relay/stitching
    state — none of those are read here, so none of them can ever leak in by a future field
    being added elsewhere to `shot` or the ledger. continuityOut (the shot's ENDING state) is
    deliberately excluded too — Cinematography composes the OPENING frame only; a shot's
    ending state is Animation's own concern, never this stage's."""
    visual_brief = {
        "shotId": shot["shotId"],
        "purpose": shot["purpose"],
        "openingPose": shot["openingPose"],
        "camera": shot["camera"],
        "visualPayoff": shot["visualPayoff"],
        "physicalStaging": shot.get("physicalStaging"),
        "prohibited": shot.get("prohibited") or [],
        "charactersInFrame": shot.get("charactersInFrame") or [],
        "continuityIn": shot.get("continuityIn"),
    }
    st = scenelook_status(scene, episode)
    scene_look_hash = (st["approved"] or {}).get("hash") if st["status"] == "approved" else None
    chars = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, chars)
    references = [
        {"slot": k, "role": shot["keyframeReferenceSlots"][k], "path": p}
        for k, p in zip(sorted((k for k in shot["keyframeReferenceSlots"] if k.startswith("@图")),
                               key=lambda k: int(k[2:])), refs)]
    return {"episode": episode, "scene": str(scene), "visualBrief": visual_brief,
            "approvedSceneLookHash": scene_look_hash, "references": references}


def _voice_dependency_context(pkg, shot, scene, episode):
    """Voice Direction may depend ONLY upon: the shot's own LOCKED dialogue (speaker +
    exact words), the shot's own already-approved DIRECTION per line (delivery — the
    storyboard's Voice Performance role's own V3-tagged performance this stage now
    compiles from, per THE DELIVERY-IS-COMPILATION FIX, 2026-07-21), and the approved voice
    configuration for every speaking character (their canonical ElevenLabs voiceId — a
    genuine input, since a re-cast voice must re-stale the direction). It must NOT depend
    on Cinematography or Animation approval activity, a keyframe, review records, cost
    ledgers, timestamps or UI state — none of those are read here.

    delivery was DELIBERATELY excluded here before 2026-07-21 ("never Voice's own performed
    re-reading of them") — a real gap once found: that reasoning confused THIS delivery-time
    Voice Direction with the storyboard's own earlier Voice Performance role, which is where
    delivery is actually authored. Now that prepare_voice genuinely compiles from delivery
    (never re-invents it), a storyboard-time edit to the acting direction MUST re-stale an
    already-approved Voice Direction compiled from the old text — omitting it here would let
    a stale, superseded performance direction sail through as still-current."""
    chars = _characters_cfg()
    speakers = sorted({ln.get("speaker") for ln in (shot.get("dialogueLines") or [])
                       if ln.get("speaker")})
    voice_config = {s: (chars.get(_resolve_char(s, chars)) or {}).get("voiceId") for s in speakers}
    return {"episode": episode, "scene": str(scene), "shotId": shot["shotId"],
            "lockedDialogue": [{"speaker": ln.get("speaker"), "exactText": ln.get("exactText"),
                                "delivery": ln.get("delivery")}
                               for ln in (shot.get("dialogueLines") or [])],
            "approvedVoiceConfig": voice_config}


def _animation_dependency_context(pkg, shot, led, scene, episode):
    """Animation Direction may depend upon: the CURRENT approved keyframe (content hash),
    the CURRENT approved audio take (content hash), the shot's own locked physical-
    performance fields, the current reference images (content hash), the current approved
    Scene Look (content hash), and this shot's own timing — these are its legitimate
    dependencies, named explicitly by the FINAL COMPLETION DIRECTIVE. It must NOT depend on
    Cinematography's own direction text/candidate/approval-activity, review records, cost
    ledgers, timestamps or UI state — a keyframe/audio ARE Cinematography's/Voice's outputs,
    never their own in-progress direction objects, so depending on the rendered artefact
    itself (not the department record that produced it) is exactly what the directive means
    by 'a downstream output... is not an input capable of staling' its own upstream stage,
    applied here in the other direction: Animation legitimately depends on what Cinematography
    and Voice PRODUCED, never on their own live approval state."""
    anchor = _anchor_for(pkg, shot)
    chars = _characters_cfg()
    refs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, chars)
    references = [
        {"slot": k, "role": shot["referenceSlots"][k], "path": p}
        for k, p in zip(sorted((k for k in shot["referenceSlots"] if k.startswith("@图")),
                               key=lambda k: int(k[2:])), refs)]
    st = scenelook_status(scene, episode)
    scene_look_hash = (st["approved"] or {}).get("hash") if st["status"] == "approved" else None
    physical_performance = {
        "openingPose": shot["openingPose"], "physicalStaging": shot.get("physicalStaging"),
        "performanceAssignment": shot.get("performanceAssignment"),
        "dialogueBinding": shot.get("dialogueBinding"),
        "continuityOut": shot.get("continuityOut"),
        # The shot's own LOCKED dialogue (speaker + exact words, never the performed
        # re-reading — that's Voice's own output) is a legitimate part of "locked physical
        # performance": Animation needs to know the shape of the lip-sync/timing task
        # (how many lines, roughly how long each runs) even though Law 6 forbids ever
        # echoing the words themselves in providerPrompt. If the underlying dialogue
        # changes without the approved audio asset being regenerated to match, that
        # mismatch is a genuine drift Animation's own freshness must catch too — not only
        # Voice's.
        "lockedDialogue": [{"speaker": ln.get("speaker"), "exactText": ln.get("exactText")}
                          for ln in (shot.get("dialogueLines") or [])],
        # THE DELIVERY-IS-COMPILATION FIX'S OWN DEPENDENCY CLOSURE (2026-07-21): Animation
        # Direction is now built by translating cb_engine.compile_shot_contract's own
        # deterministic output (_canonical_compiled_brief) — and that compiler genuinely
        # reads camera/visualPayoff/prohibited/charactersInFrame/continuityIn too (directly,
        # and via hard_constraints/_render_critical/_lip_sync_sentence/
        # _conditional_constraints — traced field-by-field, not guessed). None of these five
        # were previously part of this dependency projection (they were never inputs to the
        # OLD, freely-authoring specialist call), so a storyboard edit to any of them used to
        # go completely undetected by this freshness check — the exact "an upstream input
        # changed without staling the approval" bug class this whole dependency-graph system
        # exists to prevent. Added here, never widened further than what's actually read.
        # THE CHARGE IS AN INPUT. What we ASK the writer to do is as much a dependency of
        # its output as the material it writes about.
        #
        # ⚠ PLACEMENT IS WRONG AND MUST NOT BE "TIDIED" CASUALLY (2026-07-25). This belongs
        # at the context's TOP level, not nested inside physicalPerformance — it is not a
        # performance field. It is left here deliberately: S1.SH2's approved direction was
        # signed with it in exactly this position, and moving it changes the signature,
        # which silently stales that approval. Removing it did exactly that, live, while
        # Julian was mid-fire — the third such invalidation in one session, each one
        # landing as "the prompt is unavailable again" on his screen with no cause he could
        # see. Relocating it is a real migration: bump _DEPT_SIGNATURE_VERSION in the same
        # commit so existing approvals route through revalidate_department_signature
        # instead of silently going stale, and prove it with a test first.
        "chargeVersion": _DEPT_CHARGE_VERSION,
        "camera": shot.get("camera"), "visualPayoff": shot.get("visualPayoff"),
        "prohibited": shot.get("prohibited") or [],
        "charactersInFrame": shot.get("charactersInFrame") or [],
        "continuityIn": shot.get("continuityIn"),
        # THE CUT-PACE STALENESS FIX (2026-07-21, Julian — "it doesn't fire, or it dies
        # silently, or the compiler never reads it. That has to stop."): cutPace/
        # internalCuts/transitionType/cutInMotivation are the FIRST thing compile_shot_
        # contract reads (they decide whether the compiled brief is a single continuous
        # take or Seedance's own Shot 1:/Shot 2:/... multi-cut grammar) — but this
        # dependency projection, hashed to decide whether an APPROVED Animation Direction
        # is still current, never named them. A Director changing a shot's cut-pace
        # after Animation Direction was already approved would silently pass every
        # freshness check, and _resolve_seedance_prompt would keep firing the STALE
        # providerPrompt compiled under the old pace — the exact "we discussed it and it
        # doesn't fire" bug class this fix closes. Traced field-by-field against the
        # compiler's own read list, same discipline as every other field in this dict.
        "cutPace": shot.get("cutPace"), "internalCuts": shot.get("internalCuts") or [],
        "transitionType": shot.get("transitionType"),
        "cutInMotivation": shot.get("cutInMotivation"),
    }
    return {"episode": episode, "scene": str(scene), "shotId": shot["shotId"],
            "approvedAnchor": anchor, "approvedVoiceAsset": led.get("voPath"),
            "physicalPerformance": physical_performance, "references": references,
            "approvedSceneLookHash": scene_look_hash, "durationSec": shot.get("durationSec"),
            "measuredAudioDurationSec": (_audio_dur(led.get("voPath")) if led.get("voPath")
                                        else None),
            "fireDurationSec": _handle_duration(led.get("voPath"), shot.get("durationSec"))}


# ── THE CORE LAW (Julian's directive, 2026-07-19 — "NO CURRENT APPROVED DEPARTMENT
# DIRECTION = NO DISCLOSURE AUTHORISATION = NO PROVIDER CALL") ─────────────────────────
# Confirmed forensic root cause: _resolve_seedance_prompt() silently fell back to
# shot["seedancePrompt"] (the storyboard's own compiled prose, authored before any
# specialist ever reviewed the shot) whenever no approved Animation Direction existed —
# five real Seedance candidates ($15.47) fired this way with the Animation Director never
# having run. Every function in this section exists to make that class of bug structurally
# impossible: the hard gate below is the ONE choke point every paid route calls FIRST,
# before any envelope, disclosure or provider call is even considered.
_STAGE_SKILL_TEXT = {
    # Mirrors EXACTLY what each real prepare_* call in this file actually loads (verified
    # against cb_departments.py source, not guessed) — "the correct department skill was
    # genuinely loaded through load_runtime_skill()" (item 2) means hashing what THAT call
    # loads, not a name asserted elsewhere.
    "look": lambda: cb_departments.load_runtime_skill("cinematography"),
    "cinematography": lambda: (cb_departments.load_runtime_skill("cinematography") + "\n\n"
                                + cb_departments.load_runtime_skill("dp")),
    "voice": lambda: cb_departments.load_runtime_skill("voice"),
    "animation": lambda: cb_departments.load_runtime_skill("animation"),
    "review-keyframe": lambda: cb_departments.load_runtime_skill("review"),
    "review-animation": lambda: cb_departments.load_runtime_skill("review"),
    "review-final": lambda: cb_departments.load_runtime_skill("post"),
}


def _department_skill_hash(stage):
    """The hash of the EXACT runtime skill text load_runtime_skill would hand this stage's
    own prepare_* call right now. None only if the skill file is missing/malformed
    (load_runtime_skill's own RuntimeError) — never invented, never a guessed placeholder."""
    getter = _STAGE_SKILL_TEXT.get(stage)
    if not getter:
        return None
    try:
        return hashlib.sha256(getter().encode()).hexdigest()[:16]
    except Exception:
        return None


def _engine_path(p):
    """Resolve a possibly-relative media path against the ENGINE directory, never the
    caller's cwd. Every relative "media/..." path in this codebase is written relative to
    engine/, but the Studio server runs from cb-studio/ — so any os.path.isfile/ffprobe on
    a bare relative path silently answers differently depending on WHICH process asks.
    That made department sourceHashes cwd-dependent: a direction approved in one process
    was permanently STALE to the other, on byte-identical data. See _walk_for_signature."""
    if not p or not isinstance(p, str):
        return p
    return p if os.path.isabs(p) else os.path.join(str(HERE), p)


def _walk_for_signature(v):
    """Shared recursive walk for both _department_signature (whole-context hash) and
    _department_signature_fields (per-key breakdown, below) — any string value that is a
    real file path on disk is replaced by {path, contentMd5} so a same-path-different-
    content change (a regenerated keyframe, a new voice take, a swapped turnaround) is a
    REAL detected change, the exact class of drift a bare hash of the context dict (a hash
    of PATHS, not bytes) would silently miss."""
    if isinstance(v, dict):
        return {k: _walk_for_signature(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_walk_for_signature(x) for x in v]
    if isinstance(v, str):
        # CWD-INDEPENDENT PATH RESOLUTION (2026-07-25). A bare os.path.isfile() on a
        # RELATIVE path silently makes this whole signature depend on the calling process's
        # working directory: engine/ resolves "media/shots/x.mp3" and hashes its bytes;
        # cb-studio/ (where serve.py actually runs) does not, and hashes the bare string
        # instead. Same package, same approval, two different sourceHashes — so a direction
        # approved through one process was PERMANENTLY STALE to the other, with the UI
        # reporting only "an upstream input changed" and no way to see that nothing had.
        # Found live, costing an evening: S1.SH2's approved 810-word Animation direction
        # read as current in-process and refused at the server on the identical data.
        # Resolving against HERE (the engine dir every relative media/ path in this codebase
        # is written relative to) makes the signature a property of the DATA, never of who
        # happens to be asking — and reproduces the engine-cwd hash, so approvals signed
        # before this fix stay valid instead of being invalidated by it.
        cand = _engine_path(v)
        if os.path.isfile(cand):
            return {"path": v, "contentMd5": _file_md5(cand)}
    return v


def _department_signature(context):
    """A content-hash-aware signature of a department's own input context — see
    _walk_for_signature. Unchanged in shape/behaviour by the 2026-07-20 legacy-revalidation
    work below: every existing caller/test comparing two _department_signature results for
    equality continues to work exactly as before."""
    walked = _walk_for_signature(context)
    return hashlib.sha256(json.dumps(walked, sort_keys=True, ensure_ascii=False,
                                      default=str).encode()).hexdigest()


def _department_signature_fields(context):
    """A PER-TOP-LEVEL-KEY breakdown of the same content-hash-aware walk _department_
    signature uses — additive diagnostic detail, never a replacement for sourceHash's own
    whole-context equality check. Exists solely so a genuine content drift (as opposed to a
    formula-scope/version change) can be pinpointed to the exact field that changed, the
    "identify the exact changed field" requirement of the legacy-revalidation path
    (2026-07-20). A record created before this field existed simply won't have one — see
    department_legacy_status's own honest handling of that gap."""
    walked = _walk_for_signature(context)
    if not isinstance(walked, dict):
        return {}
    return {k: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False,
                                          default=str).encode()).hexdigest()
            for k, v in walked.items()}


def _output_signature(output):
    """A hash of a department candidate's own OUTPUT content (the approved provider prompt/
    lines/etc.) — distinct from sourceHash, which only ever covers the INPUT context. Exists
    so the legacy-revalidation path (2026-07-20) can refuse to revalidate an approval whose
    output was somehow altered after the fact (tampering, or a bug elsewhere writing directly
    into the ledger) — a class of drift the input-only sourceHash was never designed to
    catch. A record created before this field existed has nothing to compare against; see
    department_legacy_status's own honest handling of that gap."""
    return hashlib.sha256(json.dumps(output, sort_keys=True, ensure_ascii=False,
                                      default=str).encode()).hexdigest()


def _department_candidate(stage, output, context, scene=None, shot_id=None, pkg=None):
    dep, worker, skill = _DEPARTMENT_WORKERS[stage]
    return {"department": dep, "worker": worker,
            "skill": f"skills/crystal-bears-{skill}/SKILL.md",
            "skillHash": _department_skill_hash(stage),
            "model": cb_departments.cb_llm.DIRECTOR_MODEL,
            "scene": str(scene) if scene is not None else None,
            "shotId": shot_id,
            "packageRevision": (pkg or {}).get("revision"),
            "preparedAt": _now(), "editedAt": None, "preparedBy": "specialist",
            "sourceHash": _department_signature(context),
            # THE LEGACY-REVALIDATION FIELDS (2026-07-20), additive, never changing the
            # meaning of sourceHash itself: signatureVersion records which dependency-scope
            # formula produced this sourceHash (see _DEPT_SIGNATURE_VERSION's own docstring);
            # sourceFields/outputHash exist purely so a FUTURE formula correction can
            # pinpoint genuine drift and detect output tampering, exactly the diagnostic
            # capability this record's own predecessors never had.
            "signatureVersion": _DEPT_SIGNATURE_VERSION,
            "sourceFields": _department_signature_fields(context),
            "outputHash": _output_signature(output),
            "output": output}


def _department_context_for_freshness(pkg, scene, stage, shot_id=None, episode="Ep1"):
    """THE PERMANENT DEPENDENCY-GRAPH FIX (2026-07-20, FINAL COMPLETION DIRECTIVE, item 1):
    the STALENESS/SIGNATURE basis for each generative stage — look/cinematography/voice/
    animation — built EXCLUSIVELY from that stage's own explicit, named dependency
    projection (_scene_context for look; _cinematography_dependency_context/
    _voice_dependency_context/_animation_dependency_context for the other three, above).
    This is deliberately a DIFFERENT (narrower) object than what prepare_department hands
    the real specialist (_shot_context) — a specialist may reasonably benefit from a
    richer surrounding view of the shot; STALENESS must never be triggered by a field a
    stage doesn't actually depend on. Deliberately does not cover review-*/post: dailies
    review reads already-rendered media via ffmpeg frame extraction (expensive, outside
    this hardening's paid-GENERATION scope) and already refuses outright when its target
    media doesn't exist."""
    if stage == "look":
        return _scene_context(pkg, scene, episode)
    if stage not in ("cinematography", "voice", "animation"):
        raise Refused(f"REFUSED — '{stage}' has no paid-generation freshness context "
                       f"(review/post stages gate on their own rendered-media checks)")
    if not shot_id:
        raise Refused(f"REFUSED — department '{stage}' requires a shotId")
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    if stage == "cinematography":
        # A RELAY SHOT HAS NO CINEMATOGRAPHY DIRECTION OF ITS OWN (2026-07-19, found while
        # producing the Scene-1 blocker report): keyframe_shot itself already refuses a
        # relay shot outright ("it anchors on its source shot's harvested final frame,
        # never its own keyframe") — only an opener ever fires a real keyframe-generation
        # route, so only an opener ever has a genuine "keyframeReferenceSlots" to attach.
        if shot.get("sourceType") != "opener":
            raise Refused(f"REFUSED — {shot_id} is a relay shot; Cinematography direction "
                          f"applies only to the scene's opener (a relay opens from its "
                          f"source shot's harvested frame, never its own keyframe)")
        return _cinematography_dependency_context(pkg, shot, scene, episode)
    if stage == "voice":
        return _voice_dependency_context(pkg, shot, scene, episode)
    return _animation_dependency_context(pkg, shot, led, scene, episode)


def department_freshness(pkg, scene, stage, shot_id=None, episode="Ep1", _approved=None):
    """READ-ONLY, zero cost, zero LLM. {"hasApproval": bool, "current": bool,
    "changed": [str]}. Recomputes the CURRENT input signature the exact same way
    preparation would build it right now and compares it to the approved record's own
    stored sourceHash — an approval is 'current' only if every relevant upstream input
    (file CONTENT, not just path) is unchanged since it was approved. Matches this
    project's own established input-signature pattern (_keyframe_input_signature/
    _scenelook_input_signature) rather than a field-by-field diff that could itself drift
    out of sync with what actually changed."""
    work, _ = _department_container(pkg, scene, shot_id, stage, episode)
    approved = _approved if _approved is not None else work.get("approved")
    if not approved:
        return {"hasApproval": False, "current": False, "changed": ["no approval exists"]}
    try:
        context = _department_context_for_freshness(pkg, scene, stage, shot_id, episode)
    except Refused as e:
        return {"hasApproval": True, "current": False,
                "changed": [f"required input missing: {e}"]}
    current_sig = _department_signature(context)
    if current_sig == approved.get("sourceHash"):
        return {"hasApproval": True, "current": True, "changed": []}
    return {"hasApproval": True, "current": False,
            "changed": ["an upstream input (reference image, audio take, approved Scene "
                        "Look, or storyboard field) changed since this direction was "
                        "approved — re-prepare and re-approve"]}


def _output_tamper_check(approved):
    """READ-ONLY. (ok: bool, note: str|None). Verifies the approved OUTPUT content itself
    (the provider prompt/lines/etc. — never the INPUT context sourceHash already covers)
    hasn't been altered since approval. A record predating outputHash tracking (2026-07-20)
    has nothing to verify against — proceeds on trust, honestly flagged, rather than
    permanently refusing revalidation for every pre-existing approval in the show."""
    stored = approved.get("outputHash")
    if not stored:
        return True, ("this record predates output-tamper tracking — cannot verify its "
                       "prior state, proceeding on trust")
    current = _output_signature(approved.get("output") or {})
    if current != stored:
        return False, ("the approved output content itself has changed since it was "
                        "approved — this is not a formula-scope issue and cannot be "
                        "revalidated")
    return True, None


# ── SEALED-EVIDENCE LEGACY REVALIDATION (2026-07-20, FINAL COMPLETION DIRECTIVE, item 2) ──
# Julian's own correction to the prior (2026-07-20, earlier the same day) legacy-signature-
# RECONSTRUCTION approach: "The claim that a 'genuinely consumed input changed' is not
# proven: the legacy record has no field-level tracking and therefore cannot distinguish an
# actual upstream-input change from a signature-formula or dependency-scope change." A
# reconstructed old-formula hash can never prove a NEGATIVE (nothing relevant changed) for a
# record that never recorded its own inputs field-by-field. What CAN prove it: a keyframe's
# own SEALED inputSignature (_keyframe_input_signature, recorded at generation time and RE-
# VERIFIED byte-for-byte at Julian's own keyframe approval — approve_keyframe's own
# inputSignature-mismatch refusal, above — a real, independent, human-witnessed chain of
# custody). If the prompt _resolve_keyframe_prompt currently resolves to hashes identically
# to that sealed evidence, the CURRENTLY approved Cinematography Direction is proven
# byte-identical to the one that produced (and was re-checked against, at approval) a
# keyframe Julian already signed off — never a generic "the hash formula changed" inference.
def _cinematography_keyframe_seal(pkg, scene, shot_id, episode="Ep1"):
    """READ-ONLY. The keyframe's own sealed input-signature, if one exists and the keyframe
    is actually approved. Returns {"available": bool, "reason": str|None, "sealed": dict|None,
    "reviewedBy": str|None, "keyframePath": str|None}."""
    led = _ledger(pkg, shot_id)
    kf = led.get("keyframeApproval")
    if not kf or not kf.get("approved"):
        return {"available": False,
                "reason": "no approved keyframe exists for this shot yet — sealed evidence "
                          "requires an approved keyframe to seal against",
                "sealed": None, "reviewedBy": None, "keyframePath": None}
    sealed = kf.get("inputSignature")
    if not sealed:
        return {"available": False,
                "reason": "the approved keyframe predates sealed input-signature tracking — "
                          "no evidence exists to revalidate against; re-prepare and re-approve "
                          "instead",
                "sealed": None, "reviewedBy": kf.get("reviewedBy"), "keyframePath": kf.get("path")}
    return {"available": True, "reason": None, "sealed": sealed,
            "reviewedBy": kf.get("reviewedBy"), "keyframePath": kf.get("path")}


def _cinematography_prompt_ungated(pkg, shot, led, scene, episode):
    """Resolves the keyframe prompt EXACTLY as _resolve_keyframe_prompt does (a saved
    working override if present, else the approved Cinematography output's own
    providerPrompt) but WITHOUT first requiring the approval to pass THE CORE LAW's
    ordinary freshness gate (_require_approved_department/department_freshness). Used
    ONLY by the sealed-evidence legacy-revalidation path below, which exists precisely to
    evaluate an approval the ordinary ('is this hash still current under the corrected
    formula') ​gate may legitimately consider stale — that staleness is exactly the
    question sealed evidence is being asked to independently resolve, so this comparison
    must never itself be gated on the answer it's trying to determine."""
    work, _ = _department_container(pkg, scene, shot["shotId"], "cinematography", episode)
    approved = work.get("approved")
    if not approved or not ((approved.get("output") or {}).get("providerPrompt") or "").strip():
        raise Refused(f"REFUSED — {shot['shotId']} has no approved Cinematography Direction "
                      f"to compare against")
    working = led.get("workingKeyframePrompt")
    if working and working.get("text"):
        return working["text"]
    return approved["output"]["providerPrompt"]


def cinematography_legacy_evidence(pkg, scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost, zero LLM, zero provider call. Compares the CURRENTLY approved
    Cinematography Direction's own resolved keyframe prompt/reference/Scene-Look state
    against the sealed evidence recorded when this shot's approved keyframe was generated
    AND independently re-verified byte-for-byte at Julian's own keyframe approval. Strictly
    stronger than a reconstructed legacy-formula hash: it proves the actual COMPILED OUTPUT
    Cinematography currently resolves to is byte-identical to what was already approved and
    rendered — 'the approved keyframe is the output of Cinematography Direction, not an
    input capable of staling that same direction' (Julian, 2026-07-20).

    Returns {"available": bool, "reason": str|None, "allMatch": bool|None,
    "briefMatches": bool|None, "referenceMatches": bool|None, "sceneLookMatches": bool|None,
    "mismatch": dict|None, "reviewedBy": str|None, "keyframePath": str|None}. When available
    is False, reason names exactly why (never a generic message). When allMatch is False,
    mismatch names the EXACT mismatching file/prompt/field — never a generic hash mismatch."""
    seal = _cinematography_keyframe_seal(pkg, scene, shot_id, episode)
    if not seal["available"]:
        return {"available": False, "reason": seal["reason"], "allMatch": None,
                "briefMatches": None, "referenceMatches": None, "sceneLookMatches": None,
                "mismatch": None, "reviewedBy": seal["reviewedBy"], "keyframePath": None}
    sealed = seal["sealed"]
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    try:
        current_prompt = _cinematography_prompt_ungated(pkg, shot, led, scene, episode) or ""
    except Refused as e:
        return {"available": False,
                "reason": f"cinematography has no current approval to compare against: {e}",
                "allMatch": None, "briefMatches": None, "referenceMatches": None,
                "sceneLookMatches": None, "mismatch": None, "reviewedBy": seal["reviewedBy"],
                "keyframePath": seal["keyframePath"]}
    current_brief_hash = hashlib.sha256(current_prompt.encode()).hexdigest()
    brief_matches = current_brief_hash == sealed.get("briefHash")
    chars = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, chars)
    current_ref_hashes = {os.path.basename(p): _file_md5(p) for p in refs}
    sealed_ref_hashes = sealed.get("referenceHashes") or {}
    ref_matches = current_ref_hashes == sealed_ref_hashes
    st = scenelook_status(scene, episode)
    current_scenelook_hash = (st["approved"] or {}).get("hash") if st["status"] == "approved" else None
    scenelook_matches = current_scenelook_hash == sealed.get("sceneLookHash")
    mismatch = None
    if not (brief_matches and ref_matches and scenelook_matches):
        mismatch = {}
        if not brief_matches:
            mismatch["cinematographyDirection"] = (
                "the current approved Cinematography Direction's compiled keyframe prompt no "
                "longer matches the prompt hash sealed at keyframe generation/approval")
        if not ref_matches:
            changed = sorted(set(current_ref_hashes) | set(sealed_ref_hashes))
            changed = [k for k in changed if current_ref_hashes.get(k) != sealed_ref_hashes.get(k)]
            mismatch["referenceFiles"] = changed
        if not scenelook_matches:
            mismatch["sceneLook"] = ("the approved Scene Look hash no longer matches the one "
                                     "sealed at keyframe generation/approval")
    return {"available": True, "reason": None,
            "allMatch": brief_matches and ref_matches and scenelook_matches,
            "briefMatches": brief_matches, "referenceMatches": ref_matches,
            "sceneLookMatches": scenelook_matches, "mismatch": mismatch,
            "reviewedBy": seal["reviewedBy"], "keyframePath": seal["keyframePath"]}


# STAGES WITH A KNOWN SEALED-EVIDENCE REVALIDATION PATH — bounded on purpose (2026-07-20,
# Julian: "one bounded legacy-approval revalidation path"), never a generic mechanism for an
# unnamed future change. Only cinematography has an artefact (the approved keyframe) whose
# own sealed input-signature can independently prove the currently-approved direction is
# unchanged; a future stage would need its own equivalent sealed-evidence function before
# being added here, never a widened, unbounded facility.
_LEGACY_EVIDENCE_BY_STAGE = {"cinematography": cinematography_legacy_evidence}


def department_legacy_status(pkg, scene, stage, shot_id=None, episode="Ep1"):
    """READ-ONLY, zero cost, zero LLM, zero provider call. Determines whether an EXISTING
    approved department direction's staleness (if any) is attributable ONLY to the 2026-07-
    20 dependency-graph correction — never a creative-content change — and is therefore
    eligible for revalidation (binding the unchanged approval to the corrected formula)
    rather than requiring a full re-prepare/re-approve cycle that would rerun the specialist
    over content that never actually changed.

    Eligibility for a legacy (pre-v3) approval is decided by STAGE-SPECIFIC SEALED EVIDENCE
    (_LEGACY_EVIDENCE_BY_STAGE), never by reconstructing an old context-hash formula and
    comparing hashes — a reconstructed hash can prove drift happened, but (for a record that
    predates field-level tracking) it can never prove the negative Julian's own correction
    requires: 'nothing Cinematography actually depends on changed.' Sealed evidence proves
    that directly, from an independent, human-witnessed source (the keyframe's own approval
    chain), never a generic legacy-hash mismatch.

    Returns {"eligible": bool, "reason": str, "approvedSignatureVersion": int|None,
    "currentSignatureVersion": int, "changedField": str|None, "newSourceHash": str|None,
    "newSourceFields": dict|None, "newOutputHash": str|None}. The new* fields are populated
    only when eligible=True — revalidate_department copies them directly onto the approved
    record rather than recomputing, since both calls share the same just-loaded pkg."""
    empty_new = {"newSourceHash": None, "newSourceFields": None, "newOutputHash": None}

    def _refuse(reason, changed_field=None, approved_version=None):
        return {"eligible": False, "reason": reason,
                "approvedSignatureVersion": approved_version,
                "currentSignatureVersion": _DEPT_SIGNATURE_VERSION,
                "changedField": changed_field, **empty_new}

    work, _ = _department_container(pkg, scene, shot_id, stage, episode)
    approved = work.get("approved")
    if not approved:
        return _refuse("no approved direction exists to revalidate")
    approved_version = approved.get("signatureVersion")  # None = predates versioning
    if approved_version == _DEPT_SIGNATURE_VERSION:
        return _refuse("already current — no legacy signature mismatch",
                       approved_version=approved_version)
    # THE OUTPUT-TAMPER CHECK RUNS FIRST, ON PURPOSE: a directly-altered approved output is a
    # different failure class from an upstream-input change (sourceHash is INPUT-only by
    # design — see _department_signature's own docstring) and deserves its own specific,
    # decisive diagnosis rather than surfacing as a confusing "sealed evidence mismatch" (a
    # tampered output would ALSO fail the sealed-evidence brief-hash comparison below, since
    # _resolve_keyframe_prompt reads the live, tampered output — but that would misreport a
    # direct-edit tamper as if it were an upstream reference/Scene-Look drift).
    ok, note = _output_tamper_check(approved)
    if not ok:
        return _refuse(note, approved_version=approved_version)
    evidence_fn = _LEGACY_EVIDENCE_BY_STAGE.get(stage)
    if not evidence_fn:
        return _refuse("no sealed-evidence revalidation path exists for this stage — treat "
                       "this as a normal stale approval and re-prepare/re-approve instead",
                       approved_version=approved_version)
    ev = evidence_fn(pkg, scene, shot_id, episode)
    if not ev["available"]:
        return _refuse(ev["reason"], approved_version=approved_version)
    if not ev["allMatch"]:
        # Name the EXACT mismatching file/prompt/field from the sealed-evidence comparison —
        # never a generic "the hash formula changed" message.
        parts = [f"{k}: {v}" for k, v in (ev["mismatch"] or {}).items()]
        reason = ("sealed evidence shows a genuine change since the approved keyframe was "
                  "generated/approved — " + "; ".join(parts))
        changed_field = ",".join(sorted((ev["mismatch"] or {}).keys())) or None
        return _refuse(reason, changed_field=changed_field, approved_version=approved_version)
    # Sealed evidence confirms the currently-approved direction is byte-identical to the one
    # that produced (and was re-verified against, at Julian's own approval) an already-signed
    # keyframe — never a reconstructed inference. Compute the CORRECTED-formula signature
    # fresh so the approval can be bound to it without ever re-running the specialist.
    try:
        current_context = _department_context_for_freshness(pkg, scene, stage, shot_id, episode)
    except Refused as e:
        return _refuse(f"required input missing: {e}", approved_version=approved_version)
    new_fields = {"newSourceHash": _department_signature(current_context),
                  "newSourceFields": _department_signature_fields(current_context),
                  "newOutputHash": _output_signature(approved.get("output") or {})}
    reason = ("Sealed keyframe evidence confirms the approved Cinematography Direction is "
             "unchanged since it was generated and approved (reviewed by "
             f"{ev['reviewedBy']}).")
    if note:
        reason += f" (note: {note})"
    return {"eligible": True, "reason": reason, "approvedSignatureVersion": approved_version,
            "currentSignatureVersion": _DEPT_SIGNATURE_VERSION, "changedField": None,
            **new_fields}


def revalidate_department(scene, stage, shot_id=None, episode="Ep1", reviewed_by="Julian",
                          log=print):
    """Zero LLM, zero provider, zero media-generation calls (Julian's explicit 2026-07-20
    requirement). Binds an EXISTING, human-approved, content-unchanged department direction
    to the corrected dependency-signature formula — never reruns a specialist, never creates
    a replacement direction, never alters the prompt/keyframe/audio/references/creative
    content in any way. Refuses outright unless department_legacy_status reports this exact
    record eligible right now (re-derived fresh against the just-loaded pkg, never a cached
    read from an earlier call). The original approval's own preparedAt/decisionAt/reviewedBy
    are left completely untouched — only sourceHash/sourceFields/outputHash/signatureVersion
    change, and a new, separate revalidation-audit event is appended alongside history,
    never replacing it."""
    pkg, path = load_pkg(scene, episode)
    status = department_legacy_status(pkg, scene, stage, shot_id, episode)
    if not status["eligible"]:
        raise Refused(f"REFUSED — revalidation refused: {status['reason']}")
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    approved = work.get("approved")
    if not approved:
        raise Refused("REFUSED — no approved direction exists to revalidate")
    old_hash, old_version = approved.get("sourceHash"), approved.get("signatureVersion")
    approved["sourceHash"] = status["newSourceHash"]
    approved["sourceFields"] = status["newSourceFields"]
    approved["outputHash"] = status["newOutputHash"]
    approved["signatureVersion"] = _DEPT_SIGNATURE_VERSION
    event = {"reviewedBy": reviewed_by, "at": _now(),
             "oldSourceHash": old_hash, "newSourceHash": status["newSourceHash"],
             "oldSignatureVersion": old_version, "newSignatureVersion": _DEPT_SIGNATURE_VERSION,
             "note": ("Revalidated — dependency-rule correction only; no content, prompt, "
                      "keyframe, audio or reference changed. Zero provider/LLM calls made.")}
    work.setdefault("revalidations", []).append(event)
    save_extra(); _save(pkg, path)
    log(f"DEPARTMENT REVALIDATED — {stage} by {reviewed_by} (signature-version only; "
        f"zero media/LLM calls, prompt/content unchanged)")
    return event


# ── THE HISTORY-MATCH DISCOVERY (2026-07-20, found investigating the REAL S1.SH1 record
# against the sealed-evidence mechanism above, not invented): the sealed evidence proved the
# CURRENTLY approved Cinematography Direction for S1.SH1 does NOT match the prompt hash
# sealed at its keyframe's generation/approval — but a SUPERSEDED entry in the shot's own
# history DOES match exactly. In other words: a LATER decision (most likely an attempt to
# repair the self-reference staleness bug by simply re-running the specialist) superseded
# the exact direction that actually produced and was approved against the live keyframe —
# precisely the 'no refiring an unchanged specialist direction merely to repair technical
# lineage' mistake this whole directive exists to prevent. This is a DIFFERENT, more
# consequential action than revalidate_department above (it changes WHICH text is live, not
# merely its version stamp) so it is a separate function with its own distinct name/label —
# never silently folded into "Revalidate unchanged direction," which must always mean
# exactly what it says.
def cinematography_history_match(pkg, scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. When the sealed keyframe evidence is available, checks whether
    any SUPERSEDED entry in this shot's own Cinematography history is the one the sealed
    evidence actually proves generated (and was re-verified against, at approval) the
    approved keyframe. Returns {"found": bool, "historyIndex": int|None,
    "decisionAt": str|None, "reviewedBy": str|None}."""
    seal = _cinematography_keyframe_seal(pkg, scene, shot_id, episode)
    if not seal["available"]:
        return {"found": False, "historyIndex": None, "decisionAt": None, "reviewedBy": None}
    sealed_hash = (seal["sealed"] or {}).get("briefHash")
    work, _ = _department_container(pkg, scene, shot_id, "cinematography", episode)
    for i, h in enumerate(work.get("history") or []):
        prompt = (h.get("output") or {}).get("providerPrompt") or ""
        if prompt and hashlib.sha256(prompt.encode()).hexdigest() == sealed_hash:
            return {"found": True, "historyIndex": i, "decisionAt": h.get("decisionAt"),
                    "reviewedBy": h.get("reviewedBy")}
    return {"found": False, "historyIndex": None, "decisionAt": None, "reviewedBy": None}


def restore_cinematography_from_history(scene, shot_id, episode="Ep1", reviewed_by="Julian",
                                        log=print):
    """Zero LLM, zero provider, zero media-generation calls. Restores a SUPERSEDED
    Cinematography history entry as the current approved direction — used ONLY for the
    discovered case where sealed keyframe evidence proves an OLDER, already-superseded
    record (never the live 'approved' one) is what actually generated and was approved
    against this shot's live keyframe. Never invents content: the restored text is the
    exact, already-recorded historical output. The about-to-be-superseded current approval
    is itself preserved in history (never discarded), exactly as an ordinary re-approval
    already does. Refuses outright unless cinematography_history_match reports a match right
    now (re-derived fresh, never cached)."""
    pkg, path = load_pkg(scene, episode)
    match = cinematography_history_match(pkg, scene, shot_id, episode)
    if not match["found"]:
        raise Refused("REFUSED — no historical Cinematography record for this shot matches "
                      "the sealed keyframe evidence; there is nothing proven to restore")
    work, save_extra = _department_container(pkg, scene, shot_id, "cinematography", episode)
    hist = list(work.get("history") or [])
    restore = hist[match["historyIndex"]]
    current = work.get("approved")
    if current:
        hist.append({**current, "outcome": "superseded", "supersededAt": _now(),
                    "supersededReason": ("restored an earlier record proven by sealed "
                                        "keyframe evidence to be the one that actually "
                                        "generated and was approved against the live "
                                        "keyframe")})
    shot = _shot(pkg, shot_id)
    context = _cinematography_dependency_context(pkg, shot, scene, episode)
    restored_output = restore.get("output") or {}
    new_approved = {**restore, "outcome": "approved",
                    "sourceHash": _department_signature(context),
                    "sourceFields": _department_signature_fields(context),
                    "outputHash": _output_signature(restored_output),
                    "signatureVersion": _DEPT_SIGNATURE_VERSION}
    work["approved"] = new_approved
    work["history"] = hist
    event = {"reviewedBy": reviewed_by, "at": _now(),
             "restoredFromHistoryIndex": match["historyIndex"],
             "restoredDecisionAt": restore.get("decisionAt"),
             "restoredReviewedBy": restore.get("reviewedBy"),
             "note": ("Restored from history — sealed keyframe evidence proves this record, "
                      "not the one that superseded it, is what generated and was approved "
                      "against the current live keyframe. Zero LLM/provider calls made; no "
                      "content was invented, only an already-recorded historical output was "
                      "brought back as current.")}
    work.setdefault("restorations", []).append(event)
    save_extra(); _save(pkg, path)
    log(f"CINEMATOGRAPHY RESTORED FROM HISTORY — {shot_id} by {reviewed_by} (sealed-evidence "
        f"match; zero media/LLM calls)")
    return event


class DepartmentNotApproved(Refused):
    """A Refused specifically for 'no current approved department direction' — still
    caught by every existing `except Refused` handler, but distinguishable by tests/UI
    that need to name this specific failure apart from any other refusal."""
    pass


def _auto_heal_stale_department_if_previously_approved(pkg, scene, stage, shot_id, episode, log=print):
    """THE STORYBOARD-EDIT AUTO-CARRY-FORWARD (2026-07-22, Julian's directive — "stop all
    the gate restrictions... they are what is causing the issues" — scoped, per his own
    confirmed choice, to ONLY the redundant re-approval click at FIRE TIME, never Law 6,
    never the duration/cutPace validators, and never `prepare_department`'s own explicit
    contract, which many tests exercise directly expecting a manual decide_department()
    afterward — see the reverted first attempt's regression, caught live before landing.

    Cinematography/Animation/Voice are, since the 2026-07-17 retool (tasks #418/#419/#424),
    faithful MECHANICAL COMPILATIONS of the storyboard's own already-approved creative
    decisions — never independent authorship of a new creative choice. When the storyboard
    changes (a real, common, expected event now that "the magic happens at storyboard time,"
    per this project's own design) and this exact (scene, stage, shot) already has a PRIOR
    human approval on record, the specialist's fresh recompile is auto-approved through the
    SAME decide_department() path a manual click uses — fully visible and reversible in the
    department's own history, never a silent bypass, attributed honestly to what actually
    made the call. A stage's FIRST-EVER approval still requires a real human look: this
    function does nothing when `approved` is absent, only when it exists but is stale.

    Called ONLY from the three real fire-time resolvers (_resolve_keyframe_prompt/
    _resolve_voice_lines/_resolve_seedance_prompt) — never from prepare_department itself,
    and never from the working-prompt savers, which operate on an already-approved
    direction by their own separate contract. Mutates the caller's own `pkg` dict IN PLACE
    (pkg.clear()+pkg.update(...)) after healing, so the caller's later _save(pkg, path)
    never clobbers the freshly-written approval with a stale in-memory copy — the exact
    race a naive implementation would hit, since prepare_department/decide_department each
    do their own load/save cycle on a separate copy of the package."""
    work, _save_fn = _department_container(pkg, scene, shot_id, stage, episode)
    approved = work.get("approved")
    if not approved:
        return  # never approved before — a first review still requires a real human look
    fresh = department_freshness(pkg, scene, stage, shot_id, episode, _approved=approved)
    if fresh["current"]:
        return  # nothing stale, nothing to heal
    log(f"DEPARTMENT AUTO-HEAL — {stage} direction for {shot_id or scene} is stale "
        f"({'; '.join(fresh['changed'])}); re-compiling and auto-carrying-forward the prior "
        f"approval (storyboard-edit friction removed per Julian's 2026-07-22 directive)")
    prepare_department(scene, stage, shot_id=shot_id, episode=episode, log=log)
    decide_department(scene, stage, "approved", shot_id=shot_id, episode=episode,
                      reviewed_by="Auto-carried-forward (2026-07-22 directive) — mechanical "
                                  "recompile of already-approved storyboard content; no new "
                                  "creative decision for this specific recompile to review",
                      log=log)
    fresh_pkg, _ = load_pkg(scene, episode)
    pkg.clear()
    pkg.update(fresh_pkg)


def _require_approved_department(pkg, scene, stage, shot_id=None, episode="Ep1",
                                  action_label=None):
    """THE hard gate (Core Law). Returns (approved_record, output_dict) if — and only
    if — a real, CURRENT, human-approved specialist direction exists for this exact
    stage/scene/shot. Raises DepartmentNotApproved otherwise. A stale approval (see
    department_freshness above) is treated identically to no approval at all — re-
    preparing and re-approving is the only path forward, never a silent reuse."""
    if stage not in _DEPARTMENT_WORKERS:
        raise Refused(f"REFUSED — unknown department stage '{stage}'")
    dep, worker, _skill = _DEPARTMENT_WORKERS[stage]
    label = action_label or f"generation on stage '{stage}'"
    work, _save_fn = _department_container(pkg, scene, shot_id, stage, episode)
    approved = work.get("approved")
    output = (approved or {}).get("output") or {}
    # THE VOICE SCHEMA GAP (2026-07-19, found live seeding a test fixture, then confirmed
    # against cb_departments.VoiceDirection's own schema): every OTHER department's output
    # carries a providerPrompt field — voice's own schema has no such field at all, it
    # carries "lines" (a list of per-line VoiceLineDirection records) instead. Checking for
    # providerPrompt unconditionally would make an approved Voice Direction NEVER pass this
    # gate, ever — a second, distinct bug from the freshness self-reference fix above, this
    # one in the "has real content" check itself, not the staleness comparison.
    has_content = bool(output.get("lines")) if stage == "voice" else bool(
        (output.get("providerPrompt") or "").strip())
    if not approved or not has_content:
        raise DepartmentNotApproved(
            f"REFUSED — {label} requires an APPROVED {dep} direction from the {worker} "
            f"first. CORE LAW: no approved department direction = no disclosure "
            f"authorisation = no provider call. Prepare the {worker}'s specialist consult "
            f"for stage '{stage}', then approve it, before firing.")
    fresh = department_freshness(pkg, scene, stage, shot_id, episode, _approved=approved)
    if not fresh["current"]:
        raise DepartmentNotApproved(
            f"REFUSED — {label}'s approved {dep} direction is STALE ("
            f"{'; '.join(fresh['changed'])}). Re-prepare and re-approve before firing; a "
            f"stale direction is never silently reused.")
    return approved, output


def department_readiness(pkg, scene, stage, shot_id=None, episode="Ep1"):
    """READ-ONLY, zero cost, zero LLM. THE FIVE-ITEM COMPULSORY CHECKLIST (item 6 of the
    department-gate directive):
      1. prepared          — a candidate or approval exists at all.
      2. directionCurrent  — an approval exists AND its own recorded inputs still match
                              what they'd resolve to right now (department_freshness).
      3. approvalCurrent   — Julian has actually signed this OFF (an approval, not merely
                              a pending candidate) and that sign-off is still current. In
                              this codebase items 2 and 3 are, honestly, the SAME fact
                              viewed from two angles — staleness is only ever defined
                              relative to an approved record, there is no separate notion
                              of "the department's own view" independent of Julian's
                              sign-off — kept as two checklist rows because that is how
                              Julian's own directive named them, not because the code
                              tracks two independent signals.
      4. inputsCurrent     — the department's real upstream inputs (references, anchor,
                              approved voice/scene-look, etc.) resolve cleanly right now,
                              independent of whether anything has been approved yet.
      5. readyForDisclosure — the actual, full gate: would _require_approved_department
                              let a paid route past right now.
    Every item is read from the SAME real gate machinery every paid route actually calls —
    this reports what would happen right now, never a second, looser opinion. Review/post
    stages (review-keyframe/review-animation/review-final) have no provider-prompt concept
    at all — they are advisory assessments, never resolved into a paid disclosure — so this
    checklist does not apply to them; the panel shows its own simpler prepared/approved
    state for those instead (see departmentPanelHTML)."""
    if stage in ("review-keyframe", "review-animation", "review-final"):
        work, _ = _department_container(pkg, scene, shot_id, stage, episode)
        prepared = bool(work.get("candidate") or work.get("approved"))
        return {"applicable": False, "prepared": prepared,
                "directionCurrent": None, "approvalCurrent": bool(work.get("approved")),
                "inputsCurrent": None, "readyForDisclosure": None,
                "reasons": {"inputs": None, "ready": None}}
    # A RELAY SHOT HAS NO CINEMATOGRAPHY DIRECTION OF ITS OWN (2026-07-19, found while
    # producing the Scene-1 blocker report): only an opener ever fires the real keyframe-
    # generation route (keyframe_shot itself refuses a relay shot outright) — matching the
    # review-*/post pattern above, this checklist simply doesn't apply to a relay shot's
    # cinematography stage at all, rather than showing five red rows for a gate the shot
    # will never pass through.
    if stage == "cinematography" and shot_id:
        shot = _shot(pkg, shot_id)
        if shot.get("sourceType") != "opener":
            work, _ = _department_container(pkg, scene, shot_id, stage, episode)
            return {"applicable": False, "prepared": bool(work.get("candidate") or work.get("approved")),
                    "directionCurrent": None, "approvalCurrent": None,
                    "inputsCurrent": None, "readyForDisclosure": None,
                    "reasons": {"inputs": None, "ready": None}}
    work, _ = _department_container(pkg, scene, shot_id, stage, episode)
    prepared = bool(work.get("candidate") or work.get("approved"))
    has_approval = bool(work.get("approved"))
    inputs_current, input_reason = True, None
    try:
        if stage == "look":
            _scene_context(pkg, scene, episode)
        else:
            _department_context_for_freshness(pkg, scene, stage, shot_id, episode)
    except Refused as e:
        inputs_current, input_reason = False, str(e)
    fresh = department_freshness(pkg, scene, stage, shot_id, episode)
    direction_current = bool(fresh["hasApproval"] and fresh["current"])
    ready, ready_reason = False, None
    try:
        _require_approved_department(pkg, scene, stage, shot_id, episode,
                                     action_label=f"{stage} readiness check")
        ready = True
    except Refused as e:
        ready_reason = str(e)
    # THE LEGACY-REVALIDATION SIGNAL (2026-07-20): computed only when an approval exists and
    # isn't already fully current — zero-cost, read-only, never affects readyForDisclosure's
    # own gate (a legacy-signature mismatch still correctly refuses firing until Julian
    # explicitly revalidates or re-approves). The Studio panel reads this to decide whether
    # to show "Revalidate unchanged direction — £0.00" instead of the generic re-prepare path.
    legacy = (department_legacy_status(pkg, scene, stage, shot_id, episode)
              if has_approval and not direction_current else None)
    # THE HISTORY-MATCH SIGNAL (2026-07-20), cinematography-only, computed ONLY when
    # ordinary revalidation is NOT eligible — the rarer, more consequential case where a
    # LATER decision superseded the exact direction sealed keyframe evidence proves
    # actually generated/was-approved-against the live keyframe (found on the real
    # S1.SH1 record). Never confused with legacyRevalidation's own "nothing changed"
    # guarantee — the Studio panel shows a distinctly-labelled "Restore from history"
    # control for this signal, never the "Revalidate unchanged direction" one.
    history_match = None
    if (stage == "cinematography" and has_approval and not direction_current
            and legacy is not None and not legacy.get("eligible")):
        history_match = cinematography_history_match(pkg, scene, shot_id, episode)
    return {"applicable": True, "prepared": prepared, "directionCurrent": direction_current,
            "approvalCurrent": has_approval and direction_current,
            "inputsCurrent": inputs_current, "readyForDisclosure": ready,
            "reasons": {"inputs": input_reason, "ready": ready_reason},
            "legacyRevalidation": legacy, "historyMatch": history_match}


# ── THE TIMING-VS-DIALOGUE PROVISION (Julian's directive, 2026-07-19) ───────────────────
# Law 6 forbids spoken WORDS leaking into a visual/provider prompt — the voice lives in
# @Audio1, never in typed text Seedance might read as new speech to generate. But a
# director-authored prompt describing LIP-SYNC TIMING/CADENCE against the master clock of
# an uploaded @Audio1 track — e.g. "match the exact cadence of the words verbatim: 'Nailed
# it.'" — is not asking Seedance to SPEAK; it is telling the model how to move a mouth
# already being driven by real audio. Julian's own worked example failed the old, blunt
# substring check for exactly this reason. This is the "software wide provision for
# timing not dialog" he asked for: ONE shared, reusable classifier, used everywhere Law 6
# is enforced, that allows a quoted dialogue phrase ONLY when it appears as a genuine
# timing/cadence reference — never a bare/standalone restatement of the line.
_TIMING_CUE_RE = re.compile(
    r"(cadence of|timed? to|timing of|match(?:ing)? (?:the )?(?:exact )?(?:words|cadence)|"
    r"lip[- ]?sync|mouth (?:movements?|timing)|master clock|in sync with)",
    re.IGNORECASE)
_AUDIO_TAG_RE = re.compile(r"@Audio\d*", re.IGNORECASE)


def _is_timing_reference_not_dialogue_leak(prompt_text, dialogue_phrase):
    """Returns True ONLY when dialogue_phrase appears inside prompt_text as a genuine
    lip-sync TIMING/CADENCE reference, never as new spoken content for the provider to
    generate. Concrete, checkable criteria (never a vague judgment call, per this
    project's own standing rule): (1) the exact phrase appears inside a quoted span
    (" " or ' '); (2) a timing/cadence/lip-sync keyword from _TIMING_CUE_RE appears in the
    same sentence, within 60 characters BEFORE the quote; (3) an explicit @AudioN tag
    appears anywhere in the prompt, confirming a real audio track — not a Seedance-
    generated voice — is the actual vocal source. All three must hold; missing any one
    fails closed (treated as a Law 6 leak, the safe default)."""
    if not _AUDIO_TAG_RE.search(prompt_text or ""):
        return False
    for quote_re in (re.compile(r'"([^"]*)"'), re.compile(r"'([^']*)'")):
        for m in quote_re.finditer(prompt_text or ""):
            if _norm(m.group(1)) != _norm(dialogue_phrase):
                continue
            window_start = max(0, m.start() - 60)
            window = prompt_text[window_start:m.start()]
            if _TIMING_CUE_RE.search(window):
                return True
    return False


def _check_no_dialogue_leak(prompt_text, dialogue_lines, *, refuse_prefix="REFUSED"):
    """THE ONE shared Law 6 enforcement point (replacing three independent ad-hoc
    substring checks that used to live separately in prepare_department's animation
    branch, save_department_candidate's animation branch, and save_seedance_working).
    Raises Refused naming the exact offending line the instant a locked line's words
    appear in prompt_text WITHOUT qualifying as a timing reference (see
    _is_timing_reference_not_dialogue_leak above)."""
    p = _norm(prompt_text)
    for ln in dialogue_lines or []:
        locked = _norm(ln["exactText"])
        if len(locked.split()) < 2 or locked not in p:
            continue
        if _is_timing_reference_not_dialogue_leak(prompt_text, ln["exactText"]):
            continue
        raise Refused(f"{refuse_prefix} — LAW 6: spoken words found in the compiled prompt "
                      f"(\"{ln['exactText']}\") without qualifying as a lip-sync timing "
                      f"reference (quote it, name a cadence/timing/lip-sync keyword "
                      f"immediately before it, and keep @Audio1 in the prompt) — the voice "
                      f"lives in @Audio1, never typed as speech for the provider to generate.")


# ── THE DRIFT-VOCABULARY BAN (2026-07-24, Julian — "we cannot have any dead links or old
# prompt styles"): S1.SH3 fired a pre-house-template prompt carrying "sunset backlight"/
# "warm saturated sunset light" — the exact vocabulary the whole S1.SH2 campaign proved
# drags Seedance into golden-hour drift (9 takes; only the high-key/white-sun recipe held).
# Light vocabulary belongs to the shot's own SET_CONSTRAINTS (scene-authored), NEVER a
# global constant or leftover prose — these words are banned from any prompt that ships.
# (Restored 2026-07-24 same day: the Gold Build's tempo-map deletion accidentally cut this
# adjacent block — caught immediately by the standing test suite, which is exactly its job.)
_DRIFT_VOCAB_RE = re.compile(
    r"\b(sunset|sunrise|dawn|golden[- ]hour|dusk|twilight|late[- ]afternoon|"
    r"amber (?:light|glow)|pink-orange|warm saturated)\b", re.IGNORECASE)


def _check_no_drift_vocab(prompt_text, *, refuse_prefix="REFUSED"):
    """ADVISORY (demoted from a hard refusal, 2026-07-25, Julian's no-straitjacket ruling).

    These eleven words were banned outright after a real, documented drift campaign
    (S1.SH2, regressed on S1.SH3) — that evidence stands and this WARNS loudly. But the
    real protection against a shot drifting off the locked look was never a word blacklist:
    it is the scene plate reference plus the scene's own authored lighting field, both of
    which still ship on every prompt. Banning "dusk", "twilight" and "amber glow" outright
    also bans eleven legitimate pieces of cinematic light vocabulary from a children's
    adventure that literally contains a storm at sea and a sunrise.

    ⚠ FLAGGED FOR JULIAN: this is the one demotion tonight that reverses a ruling you made
    from watching real footage. It is a warning now, not a refusal. Every fire is recorded
    in the verdict corpus, so if drift returns we will see it in your own verdicts and can
    restore the block WITH the new evidence rather than on memory. Say the word and it goes
    straight back to a refusal."""
    hits = sorted({m.group(0).lower() for m in _DRIFT_VOCAB_RE.finditer(prompt_text or "")})
    if hits:
        print(f"  ⚠ DRIFT-VOCAB WARNING ({refuse_prefix}): {', '.join(hits)} — these words "
              f"caused the documented sunset/golden-hour drift. The plate and the scene's "
              f"own lighting field are what actually hold the look; check this shot's light "
              f"reads as the scene states it before approving.")
    return hits

def _ending_requires_hold(shot):
    """Does this shot's approved ending need the clean-frame harvest window?

    THE UNIVERSAL-HOLD RETIREMENT (Julian's directive, 2026-07-25): "Closing holds are
    required only when approved by the Shot Card." check_formula_structure previously
    demanded a HOLD tail on EVERY prompt — a literal universal enforced in code, which
    refused a real action variant purely for finishing in movement.

    DELEGATES to cb_engine.ending_requires_hold rather than re-deciding here: the
    directive requires one authority per decision, and the ending vocabulary belongs to
    the schema module. A shot with no decision (legacy) keeps the historical requirement,
    so nothing loosens by accident."""
    if not shot:
        return True
    try:
        import cb_engine as _E
        return _E.ending_requires_hold(shot)
    except Exception:
        # never let a schema-side problem turn into a silent bypass of the hold check
        return True


# Inline "SPEAKER: line" dialogue — forbidden under Law 6 whenever @Audio1 carries the
# voice. Same pattern check_craft_components uses for its own advisory.
_INLINE_SPEAKER_RE = re.compile(r"^[A-Z][A-Z'’ ]{1,30}: \S", re.M)
_SHOT_LABEL_RE = re.compile(r"\bShot (\d+):")
_HOLD_TAIL_RE = re.compile(r"\bHOLD\b[\s\S]{0,200}?about 2 seconds", re.IGNORECASE)
_HOLD_PHRASE_RE = re.compile(r"about 2 seconds(?: of silence)?", re.IGNORECASE)
_DURATION_TEXT_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*(?:s|sec|secs|second|seconds)\b",
                               re.IGNORECASE)


# THE STASIS LOAD CHECK (2026-07-25, from an external craft review of S1.SH2's shipped
# prompt: "technically detailed and continuity-conscious, but dramatically immobilised...
# the prompt repeatedly tells Seedance to settle, anchor and hold. The model is therefore
# doing exactly what it is being asked to do.").
#
# CALIBRATED ON REAL DATA, NOT AN INVENTED NUMBER — the discipline rule 17 demands. The
# APPROVED SH1 keeper runs at 1.94 stasis terms per 100 words; the rejected-as-laboured
# SH2 runs at 3.21, 65% higher, and leans on "two-shot" four times — a word the proven
# keeper never uses once. So the threshold sits between two measured real prompts, one
# known good and one known laboured, instead of being guessed.
#
# ADVISORY, NEVER A BLOCK. Julian removed the suffocating guardrails deliberately; a
# machine refusing a prompt on rhythm is exactly how a pipeline produces compliant work
# nobody wants to watch. This names what it measured and lets the reviewer decide.
STASIS_TERMS = ("hold", "holds", "holding", "held", "settle", "settles", "settled",
                "settling", "anchor", "anchors", "anchored", "still", "stillness",
                "motionless", "steady", "static", "freeze", "frozen", "remains", "remain",
                "stays", "stay", "stationary", "two-shot", "locked", "unmoving", "fixed")
STASIS_PER_100_KEEPER = 1.94      # measured: SH1_KEEPER_EXEMPLAR.txt, the approved take
STASIS_PER_100_ADVISE = 2.60      # between the keeper and the laboured SH2 (3.21)
_FIXED_RE = r"\b(anchored|welded|rooted|stationary|never leaves)\b"
# INDEPENDENT travel only. "travels WITH the flower" is the anchor doing its job,
# not a contradiction — the approved SH1 keeper says exactly that, and the first
# draft of this check flagged the proven winner because of it. A check that fails
# the known-good take is worse than none: it teaches everyone to ignore it.
_TRAVEL_RE = (r"\b(hovers beside|hovering beside|flies beside|flying beside|"
              r"flies alongside|falls into formation|leaves the flower|"
              r"crosses the meadow|travels through)\b")
_TRAVEL_WITH_RE = r"\btravels?\s+(?:physically\s+)?with\b"


def check_stasis_load(prompt_text, shot=None, characters=()):
    """READ-ONLY, zero cost. Returns a list of advisory strings — never blocks.

    Four concrete, checkable things (never "does this feel laboured", which a generous
    grader waves through every time):

      1. stasis density against the measured keeper baseline;
      2. one framing noun repeated enough to read as a lock ("two-shot" x4);
      3. a character told BOTH to stay fixed AND to travel — the spatial contradiction
         that makes keeping everyone close and slow the model's safest available answer;
      4. camera leadership conflict: the camera follows one character while another is
         pinned, with both required to stay readable.
    """
    out = []
    txt = prompt_text or ""
    words = len(txt.split()) or 1
    low = txt.lower()

    hits = [w for w in STASIS_TERMS
            for _ in re.findall(r"\b" + re.escape(w) + r"\b", low)]
    density = len(hits) / words * 100
    if density > STASIS_PER_100_ADVISE:
        common = ", ".join(f"{w} x{n}" for w, n in Counter(hits).most_common(5))
        out.append(
            f"STASIS LOAD {density:.2f} settle/hold terms per 100 words — the approved SH1 "
            f"keeper runs at {STASIS_PER_100_KEEPER}. Heaviest: {common}. Every one of these "
            f"is an instruction the model will obey; a shot told repeatedly to settle will "
            f"settle.")

    for term in ("two-shot", "held", "hold", "anchored", "motionless"):
        n = len(re.findall(r"\b" + re.escape(term) + r"\b", low))
        if n >= 3:
            out.append(f"REPEATED SAFEGUARD '{term}' x{n} — restating the same lock does not "
                       f"make it safer, it makes it the shot's dominant instruction.")

    for name in (characters or ()):
        if not name:
            continue
        sents = [x for x in re.split(r"(?<=[.;])\s+", txt) if name.lower() in x.lower()]
        fixed = [x for x in sents if re.search(_FIXED_RE, x.lower())]
        travel = [x for x in sents
                  if re.search(_TRAVEL_RE, x.lower())
                  and not re.search(_TRAVEL_WITH_RE, x.lower())]
        # Must be DIFFERENT sentences, or it is one coherent instruction counted twice.
        if fixed and travel and any(f is not t for f in fixed for t in travel):
            out.append(
                f"GEOGRAPHY CONTRADICTION on {name} — described as fixed in one place and "
                f"travelling in another. Fixed: \u201c{fixed[0].strip()[:90]}\u2026\u201d "
                f"Travelling: \u201c{travel[0].strip()[:90]}\u2026\u201d The model resolves "
                f"a contradiction by choosing the safest reading, which is usually less motion.")

    # A REAL CAST NAME ONLY. The first draft matched "the camera follows at a readable
    # distance" and reported the leader as "at" — a preposition shown to Julian as a
    # character. Match against the actual cast, never a bare \\w+.
    names = [n for n in (characters or ()) if n]
    led = next((n for n in names if re.search(
        r"camera (?:follows|tracks|chases)\s+" + re.escape(n.lower()), low)), None)
    if led:
        pinned = [n for n in names
                  if n.lower() != led.lower() and re.search(
                      _FIXED_RE, " ".join(x for x in re.split(r"(?<=[.;])\s+", txt)
                                          if n.lower() in x.lower()).lower())]
        if pinned:
            out.append(
                f"CAMERA LEADERSHIP CONFLICT — the camera follows {led} while "
                f"{', '.join(pinned)} is pinned in place, and both must stay readable. The "
                f"cheapest way for the model to satisfy that is to keep them close together "
                f"and reduce travel.")
    return out


def check_formula_structure(prompt_text, dialogue_lines, *, refuse_prefix="REFUSED", shot=None):
    """THE THREE LAWS THAT STILL BLOCK, AND NOTHING ELSE (Julian's ruling, 2026-07-25 —
    "remove a lot of the guardrails that suffocate the creative prompting"). What remains
    a hard refusal is exactly the voice pipeline, which is the one place this studio is
    measurably ahead of the field and the one place a mistake is unrecoverable:

        1. dialogue present -> the audio-law header opens the prompt
        2. dialogue present -> @Audio1 declared the sole source of voice and timing
        3. dialogue words NEVER inline (Law 6)

    Everything else this gate used to refuse — shot labelling, Cut-to bookkeeping, the
    closing hold, duration prose, an 800-word ceiling — is now RETURNED AS ADVISORY. Those
    were form and taste, and a machine refusing a prompt on taste is how a pipeline ends up
    producing compliant work that no one wants to watch. The reviewer sees the advisories;
    the writer is not caged by them.

    Also THE STALE-FORMAT DOOR — any pre-Gold prompt shape (the old lean brief, tempo-map bodies,
    [STYLE_HEADER] experiments, source-material briefs) fails these checks by
    construction and can never reach the provider again.

    THE SH1 KEEPER STANDARD (Julian's ruling, 2026-07-25, proven over eleven live A/B
    fires — see PROMPT_CRAFT_STANDARD.md's dated section + SH1_KEEPER_EXEMPLAR.txt):
    dialogue is satisfied by declaring @Audio1 the sole source (words never inline);
    the HOLD tail accepts the keeper's own 'for two seconds after the audio finishes'
    wording; the size refusal is the 800-word backstop (spend, not count — the AnyFilm
    band stays the advisory target in check_craft_components). The legacy inline-
    verbatim Gold form remains valid for prompts that never reference @Audio1."""
    text = str(prompt_text or "")
    problems, advisories = [], []
    has_dialogue = bool(dialogue_lines)
    if has_dialogue and not text.lstrip().startswith("ENGLISH DIALOGUE ONLY"):
        problems.append("dialogue present but the prompt does not open with the exact "
                        "header 'ENGLISH DIALOGUE ONLY, spoken in English.'")
    # THE NO-STRAITJACKET PASS (Julian's ruling, 2026-07-25 — "remove a lot of the
    # guardrails that suffocate the creative prompting"). Shot labelling and Cut-to
    # bookkeeping are FORM, not law: a single unbroken take is a legitimate, sometimes
    # superior answer, and refusing it because it carries no "Shot 1:" heading forces
    # every shot in the show into one skeleton. Advisory now — the reviewer sees it, the
    # writer is not caged by it.
    shots = _SHOT_LABEL_RE.findall(text)
    n = len(set(shots))
    if not shots:
        advisories.append("no 'Shot 1:' labelling — fine for a single continuous take, "
                          "worth a look if this shot was meant to cut internally")
    if n >= 2 and text.count("Cut to.") < n - 1:
        advisories.append(f"{n} labelled shots but {text.count('Cut to.')} 'Cut to.' "
                          f"transition(s) — check the cuts read as intended")
    # THE UNIVERSAL-HOLD RETIREMENT (2026-07-25): a hold is demanded only when the SHOT
    # CARD asks for one. A shot that declares endingBehaviour="continue_in_motion" — an
    # action beat, a transition — is expected to finish moving and is not refused for it.
    if _ending_requires_hold(shot) and not _HOLD_TAIL_RE.search(text):
        advisories.append("missing the closing HOLD tail ('Hold ... for two seconds after "
                        "the audio finishes' or 'HOLD … about 2 seconds') — the "
                        "clean-frame harvest window. If this shot is MEANT to finish in "
                        "movement, declare its real ending on the Shot "
                        "Card (continue_in_motion / cut_on_action / visual_transition) "
                        "rather than bypassing this check")
    stripped = _HOLD_PHRASE_RE.sub("", text)
    dur = _DURATION_TEXT_RE.findall(stripped)
    if dur:
        advisories.append(f"duration text in the prompt ({', '.join(sorted(set(d.strip() for d in dur))[:3])}) "
                        f"— duration is an API parameter, never prompt text")
    # Verbatim check normalizes smart punctuation (curly vs straight apostrophes/quotes,
    # en/em dashes, ellipsis) — the exactText field and the authored card legitimately
    # differ only in typographic form; that is not a missing line. (Found live on S1.SH4's
    # gold prompt: "A Storm\u2019s coming" vs "A Storm\u0027s coming".)
    def _norm_punct(s):
        s = (s.replace("\u2019", "'").replace("\u2018", "'")
               .replace("\u201c", '"').replace("\u201d", '"')
               .replace("\u2013", "-").replace("\u2014", "-").replace("\u2026", "..."))
        return re.sub(r"\s+", " ", s)
    # THE SH1 KEEPER STANDARD (Julian's ruling, 2026-07-25 — "use this as the standard
    # for all our prompts"): dialogue words NEVER appear in the prompt; @Audio1 is
    # declared the sole source of dialogue, wording, voice, performance and timing, and
    # the performance is timed by naming the audio's own spoken sections. A prompt that
    # references @Audio1 satisfies the dialogue law with ZERO inline lines. The LEGACY
    # inline-verbatim form (the S1.SH3-era Gold formula) remains valid for prompts that
    # don't reference @Audio1 — those must still carry every locked line word for word.
    norm = _norm_punct(text)
    if has_dialogue and "@Audio1" not in text:
        problems.append("dialogue exists but the prompt never declares @Audio1 as the sole "
                        "source of dialogue, wording, voice, performance and timing — THE "
                        "SH1 KEEPER STANDARD (and Law 5: the voice lives in the render, "
                        "never a native-voice fallback). The retired inline-verbatim form "
                        "is no longer accepted")
    if has_dialogue and _INLINE_SPEAKER_RE.search(text):
        problems.append("inline SPEAKER: dialogue in the prompt — under the keeper standard "
                        "the spoken words never appear; @Audio1 carries them and the prompt "
                        "times the performance by naming the audio's own spoken sections")
    # THE SIZE LAW, AS SPEND (Julian's rulings, 2026-07-25 — first "look at the other
    # prompts from AnyFilm" (420-word hard cap), then THE SH1 KEEPER STANDARD the same
    # day: the proven keeper prompt is 722 words and every one buys physics — leanness is
    # zero WASTED words, not a number. The AnyFilm band (~250-350, delivered average 244)
    # stays the TARGET, surfaced as an advisory flag in check_craft_components; the hard
    # refusal moves to 800 as the real backstop against genuine runaway scaffolding.
    # THE SIZE CEILING IS RETIRED (2026-07-25). Every numeric ceiling this project has
    # ever set was later found to be cutting the wrong thing — most recently a physics
    # description truncated to its flatter half to fit a budget. The proven keeper is 722
    # words because every one buys physics; a hypothetical 900-word prompt that also spends
    # every word on physics is not worse, and no gate can tell the difference by counting.
    # Waste is surfaced as an advisory in check_craft_components and judged by a human.
    if problems:
        raise Refused(f"{refuse_prefix} — THE FORMULA GATE: " + "; ".join(problems))
    # THE STASIS LOAD (2026-07-25). Advisory, like everything else here — but this is
    # the one that catches a prompt that is technically perfect and dramatically
    # immobilised, the exact failure an external craft review found in S1.SH2.
    cast = []
    if shot:
        # charactersInFrame is a plain list of names in the real package; tolerate the
        # dict shape too rather than assuming either (checked live before writing this).
        cast = [c if isinstance(c, str) else (c.get("name") if isinstance(c, dict) else None)
                for c in (shot.get("charactersInFrame") or shot.get("characters") or [])]
        cast = [c for c in cast if c]
    advisories += check_stasis_load(prompt_text, shot=shot, characters=cast)
    return advisories


def check_craft_components(prompt_text):
    """ADVISORY ONLY — never blocks, never trims (the No-Straitjacket Law). Flags a card
    missing one of the register's load-bearing craft components so the reviewer sees the
    gap; the ten-component standard lives in PROMPT_CRAFT_STANDARD.md."""
    text = str(prompt_text or "")
    flags = []
    if not re.search(r"\b\d{2,3}mm\b", text):
        flags.append("no focal length (NNmm) named")
    if not re.search(r"\b(foreground|midground|background|bokeh|soft focus)\b", text, re.I):
        flags.append("no depth-staging language")
    if not re.search(r"\b(light|sun|sky|shadow|rim|catchlight|glow|backlit|backlight|grey)\b",
                     text, re.I):
        flags.append("no light state written")
    if not re.search(r"\b(static|locked|push(?:es|ing)?|crane|tracking|handheld|orbit(?:s|ing)?"
                     r"|pan|drift(?:s|ing)?|follow(?:s|ing)?|bank(?:s|ing)?|swings?|races?)\b",
                     text, re.I):
        flags.append("no camera movement named")
    # THE SH1 KEEPER STANDARD advisories (2026-07-25) — never block, only inform:
    wc = len(text.split())
    if wc > 420:
        # THE ESCAPE CLAUSE IS GONE (2026-07-25). This used to end "...fine for a
        # multi-beat physical chain ONLY if every word buys physics" — a test no
        # prompt has ever failed, because any sentence can be argued to buy physics.
        # It licensed 810 words of continuity safeguards on a shot an external craft
        # review then called dramatically immobilised. State the measured gap instead
        # and name what actually fills it.
        flags.append(f"{wc} words — AnyFilm DELIVERS 244 per clip; our own run "
                     f"716-810. Measured, that gap is not extra physics: it is "
                     f"continuity safeguards, restated framing locks and repeated "
                     f"stillness language. Ask which sentences were added out of "
                     f"worry, and cut those.")
    if "@Audio1" in text and re.search(r"^[A-Z][A-Z'’ ]{1,30}: \S", text, re.M):
        flags.append("inline SPEAKER: dialogue alongside @Audio1 — the keeper standard "
                     "is audio-only (dialogue words never in the prompt)")
    if re.search(r"\b\d{1,3}[-–]degree\b|\bscreen direction\b", text, re.I):
        flags.append("abstract geometry language (degrees / screen direction) — the "
                     "model acts on physical cause-and-consequence, never a compass "
                     "(v4's confirmed failure mode)")
    return flags


def _review_frames(video_path, max_frames=4):
    """Extract up to six chronological frames for the real vision review call, evenly
    spaced across the CLIP'S OWN ACTUAL DURATION (2026-07-22, found live reviewing S1.SH1
    — the previous implementation used `fps=1/2` (one frame every 2s) and then took only
    the FIRST `max_frames` of that stream. For any clip longer than `2 * max_frames`
    seconds — every real shot in this show, all ~14-15s — that silently covers only the
    first ~8 seconds and never samples the back half at all. The Director Review /
    Continuity Supervisor came back BLOCKED on S1.SH1's real, human-approved take because
    it was never shown the clip, crash, landing pose, or final dolly-in on Zenny — not
    because any of those were missing from the actual footage. Fixed to probe the real
    duration first (cb_post._dur, the same ffprobe helper every other duration read in
    this codebase already uses) and seek to `max_frames` evenly-spaced timestamps
    spanning the WHOLE clip, so a review of a multi-beat shot actually sees every beat.

    THE SECOND HALF OF THE SAME FIX (found immediately re-verifying the first): a
    midpoint-of-each-bucket scheme (duration*(i+0.5)/n) leaves the LAST sample short of
    the true end by duration/(2n) — for a 15s clip at n=4 that is ~1.9s, exactly long
    enough to miss a shot's own final held beat (S1.SH1's tight dolly-in close on Zenny's
    reaction lands in the last ~2s and was still invisible to the reviewer under the
    first version of this fix). Endpoint-inclusive spacing instead — first sample near
    true 0, last sample near the true end, evenly spaced between — so the opening AND
    closing beats are both guaranteed coverage, not just whichever bucket midpoints
    happen to land near them. A small inset avoids seeking to the literal 0.0s or EOF
    frame, which can read as black/transitional rather than real content."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-review-"))
    duration = cb_post._dur(str(video_path)) or 0.0
    if duration <= 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(f"REFUSED — could not read a duration for {video_path}; "
                      "no review frames extracted")
    n = max(1, int(max_frames))
    inset = min(0.5, duration * 0.05)
    span = max(0.0, duration - 2 * inset)
    if n == 1:
        timestamps = [duration / 2]
    else:
        timestamps = [inset + span * i / (n - 1) for i in range(n)]
    frames = []
    for i, ts in enumerate(timestamps):
        out = tmp / f"frame_{i:02d}.jpg"
        proc = subprocess.run(["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", str(video_path),
                               "-vf", "scale=960:-2", "-frames:v", "1", str(out)],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise Refused(f"REFUSED — could not extract review frame at {ts:.1f}s from "
                          f"{video_path}: {proc.stderr[-240:]}")
        frames.append(out)
    frames = sorted(frames)
    if not frames:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(f"REFUSED — no visible frames could be extracted from {video_path}")
    return tmp, [str(p) for p in frames]


def _canonical_compiled_brief(pkg, shot, stage, characters_cfg):
    """THE DELIVERY-IS-COMPILATION FIX (2026-07-21, Julian's own ruling — "the script-to-
    storyboard is where the magic happens... the rest is just delivery... it is ensuring
    that we deliver that through a prompt"): builds the canonical, storyboard-faithful
    brief text via cb_engine's own already-hardened, zero-LLM compiler
    (compile_keyframe_prompt for the still opening frame, compile_shot_contract for the
    full shot) — this is now Cinematography/Animation's SOURCE OF TRUTH, replacing the raw
    JSON dump of the shot's own fields that used to invite the specialist to reconstruct
    composition fresh instead of translating what the storyboard already decided.

    Reconstructs a real cb_engine.Shot from the persisted production package's own dict —
    the SAME shape cb_handover.distil_shot produces when the package is built, so this
    round-trips faithfully; extra keys the package carries beyond cb_engine.Shot's own
    schema (referenceSlots, seedancePrompt, etc.) are dropped explicitly, never trusted to
    Pydantic's own default extra-field handling. Fails loud, never silently degrades — a
    package whose own shot record doesn't reconstruct as a valid canonical Shot is a real
    data-integrity problem, not something to paper over with a fallback."""
    fields = {k: v for k, v in shot.items() if k in cb_engine.Shot.model_fields}
    try:
        shot_obj = cb_engine.Shot(**fields)
    except Exception as e:
        raise Refused(f"REFUSED — {shot.get('shotId')}'s own package record doesn't "
                      f"reconstruct as a valid canonical Shot ({e}) — the compiled "
                      f"delivery brief cannot be built")
    scene_dict = {"sceneName": pkg.get("sceneName", "")}
    compiler = (cb_engine.compile_keyframe_prompt if stage == "cinematography"
                else cb_engine.compile_shot_contract)
    text, wc, slots = compiler(shot_obj, scene_dict, characters_cfg)
    return text, wc, slots


def prepare_department(scene, stage, shot_id=None, episode="Ep1", log=print):
    """Run one real specialist once and store an awaiting-approval candidate.

    Existing approved work and every media asset remain untouched if the call fails or a
    replacement candidate is prepared.  No cb_gen function is reachable from this path.

    REFIRE ALWAYS JUST WORKS (2026-07-20, Julian — "every stage should have an approve and
    reject and refire button"): a pending candidate is no longer a hard refusal here — it is
    superseded into history (never silently discarded) and a fresh one is prepared, matching
    the Studio's own candidate-screen "Refire" button, which has always claimed exactly this
    behaviour ("no reason needed... a pending candidate never has to be rejected first just
    to try again") without the backend actually honouring it until now."""
    if stage not in _DEPARTMENT_WORKERS:
        raise Refused(f"REFUSED — unknown department stage '{stage}'")
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    if work.get("candidate"):
        work.setdefault("history", []).append({**work["candidate"], "outcome": "superseded_by_refire",
                                                "supersededAt": _now()})
        work["candidate"] = None

    temp_dir = None
    if stage == "look":
        context = _scene_context(pkg, scene, episode)
        result = cb_departments.prepare_look(context, log=log)
    elif stage == "review-final":
        media = HERE / "media" / f"{episode}_Scene{scene}_shots_picture.mp4"
        if not media.exists():
            raise Refused(f"REFUSED — no actual assembled scene exists for scene {scene} to review")
        temp_dir, frames = _review_frames(str(media), 6)
        try:
            context = {**_scene_context(pkg, scene, episode), "shots": pkg.get("shots") or [],
                       "orderedReviewImages": [
                           {"role": f"actual assembled-scene frame {i+1}", "path": p}
                           for i, p in enumerate(frames)]}
            result = cb_departments.review_media("final", context, frames, log=log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        shot = _shot(pkg, shot_id)
        led = _ledger(pkg, shot_id)
        context = _shot_context(pkg, shot, led, scene, episode, stage=stage)
        if stage == "cinematography":
            # SAME GUARD AS _department_context_for_freshness (2026-07-19): a relay shot
            # has no keyframeReferenceSlots at all — refuse cleanly here too, at the actual
            # authoring entry point, rather than a raw KeyError.
            if shot.get("sourceType") != "opener":
                raise Refused(f"REFUSED — {shot_id} is a relay shot; Cinematography "
                              f"direction applies only to the scene's opener (a relay "
                              f"opens from its source shot's harvested frame, never its "
                              f"own keyframe)")
            chars = _characters_cfg()
            images = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, chars)
            context["orderedAttachments"] = [
                {"slot": k, "role": shot["keyframeReferenceSlots"][k], "path": p}
                for k, p in zip(sorted((k for k in shot["keyframeReferenceSlots"] if k.startswith("@图")),
                                       key=lambda k: int(k[2:])), images)]
            brief, brief_wc, _ = _canonical_compiled_brief(pkg, shot, "cinematography", chars)
            result = cb_departments.prepare_cinematography(context, images, brief, log=log)
            # THE DRIFT-VOCABULARY BAN, at authoring (2026-07-24) — same wall as animation's.
            _check_no_drift_vocab(result.providerPrompt,
                                  refuse_prefix="REFUSED — Cinematographer's own candidate; "
                                                "no candidate saved")
        elif stage == "voice":
            result = cb_departments.prepare_voice(context, shot.get("dialogueLines") or [], log=log)
        elif stage == "animation":
            if not (led.get("voiceApproval") or {}).get("approved") and shot.get("dialogueLines"):
                raise Refused(f"REFUSED — {shot_id}'s approved voice is required before the "
                              "Animation Director enters")
            anchor = _anchor_for(pkg, shot)
            achars = _characters_cfg()
            images = _slot_paths(shot, "referenceSlots", anchor, scene, episode, achars)
            context["orderedAttachments"] = [
                {"slot": k, "role": shot["referenceSlots"][k], "path": p}
                for k, p in zip(sorted((k for k in shot["referenceSlots"] if k.startswith("@图")),
                                       key=lambda k: int(k[2:])), images)]
            context["approvedVoiceAsset"] = led.get("voPath")
            brief, brief_wc, _ = _canonical_compiled_brief(pkg, shot, "animation", achars)
            # THE FORENSIC FIX'S OWN NUMBERS, IN THE REAL ANIMATION DIRECTOR'S CONTEXT TOO
            # (item 4 — matching _department_context_for_freshness's identical fields exactly,
            # 2026-07-19 found-while-verifying: without this, this context and the freshness
            # recompute's context were TWO DIFFERENT SHAPES — meaning every real, approved
            # Animation Direction would report STALE the very next time anyone checked
            # freshness, since department_freshness's own hash could never match a sourceHash
            # computed from a context missing these two keys. A guaranteed, permanent
            # production outage for the whole Animation route, caught before it ever shipped.
            context["measuredAudioDurationSec"] = _audio_dur(led.get("voPath")) if led.get("voPath") else None
            context["fireDurationSec"] = _handle_duration(led.get("voPath"), shot.get("durationSec"))
            result = cb_departments.prepare_animation(context, images, brief, log=log)
            # THE FORMULA GATE (Gold Build, 2026-07-24): the register writer's card must
            # BE the formula — dialogue inline verbatim, labelled shots, the HOLD tail.
            # Replaces the retired leak-check + tempo-map pair on this path.
            check_formula_structure(result.providerPrompt, shot.get("dialogueLines") or [], shot=shot,
                                    refuse_prefix="REFUSED — Animation Director's own candidate; "
                                                  "no candidate saved")
            for _flag in check_craft_components(result.providerPrompt):
                log(f"  CRAFT FLAG (advisory) — {_flag}")
            # THE DRIFT-VOCABULARY BAN, at authoring (2026-07-24): the LLM can invent
            # "sunset light" from pure meadow association even with a clean context —
            # confirmed live on S1.SH1's own regeneration. A dirty candidate is refused
            # here, never saved, so it can never be approved and never reaches a fire.
            _check_no_drift_vocab(result.providerPrompt,
                                  refuse_prefix="REFUSED — Animation Director's own candidate; "
                                                "no candidate saved")
        elif stage == "review-keyframe":
            rec = led.get("keyframeCandidate") or led.get("keyframeApproval") or {}
            media = rec.get("path")
            if not media or not os.path.exists(media):
                raise Refused(f"REFUSED — no actual keyframe media exists for {shot_id} to review")
            refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode,
                               _characters_cfg())
            images = [media] + refs
            context["orderedReviewImages"] = ([{"role": "actual rendered keyframe", "path": media}] +
                [{"role": role, "path": p} for role, p in
                 zip((shot["keyframeReferenceSlots"][k] for k in sorted(
                     (k for k in shot["keyframeReferenceSlots"] if k.startswith("@图")),
                     key=lambda k: int(k[2:]))), refs)])
            result = cb_departments.review_media("keyframe", context, images, log=log)
        else:
            media_paths = list(led.get("candidatePaths") or [])
            if not media_paths and led.get("approvedTake"):
                media_paths = [led["approvedTake"]]
            if not media_paths or any(not os.path.exists(p) for p in media_paths):
                raise Refused(f"REFUSED — no actual animation media exists for {shot_id} to review")
            temp_dirs, frames, frame_labels = [], [], []
            try:
                per_candidate = 2 if len(media_paths) > 1 else 4
                for i, media in enumerate(media_paths, start=1):
                    td, fs = _review_frames(media, per_candidate)
                    temp_dirs.append(td); frames.extend(fs)
                    frame_labels.extend({"role": f"actual C{i} animation frame {n+1}",
                                         "candidateId": f"C{i}", "path": p}
                                        for n, p in enumerate(fs))
                anchor = _anchor_for(pkg, shot)
                refs = _slot_paths(shot, "referenceSlots", anchor, scene, episode,
                                   _characters_cfg())
                images = frames + refs
                context["orderedReviewImages"] = (
                    frame_labels +
                    [{"role": shot["referenceSlots"][k], "path": p} for k, p in
                     zip(sorted((k for k in shot["referenceSlots"] if k.startswith("@图")),
                                key=lambda k: int(k[2:])), refs)])
                result = cb_departments.review_media("animation", context, images, log=log)
            finally:
                for td in temp_dirs:
                    shutil.rmtree(td, ignore_errors=True)

    # THE SIGNATURE BASIS IS THE EXPLICIT NARROW PROJECTION, NEVER THE BROAD LLM-FACING
    # `context` (2026-07-20, FINAL COMPLETION DIRECTIVE, item 1): prepare-time sourceHash
    # and every later freshness recheck (department_freshness/department_legacy_status,
    # via the SAME _department_context_for_freshness call) must be computed from the
    # identical object, or a symmetric equality check is meaningless. `context` above stays
    # the richer object the specialist actually saw; sig_context is what gets hashed.
    if stage in ("cinematography", "voice", "animation"):
        sig_context = _department_context_for_freshness(pkg, scene, stage, shot_id, episode)
    else:
        sig_context = context
    work["candidate"] = _department_candidate(stage, result.model_dump(), sig_context,
                                                scene=scene, shot_id=shot_id, pkg=pkg)
    save_extra()
    _save(pkg, path)
    log(f"DEPARTMENT — {work['candidate']['worker']} prepared {stage} work for "
        f"{shot_id or 'scene '+str(scene)} (awaiting Julian; no media generated)")

    # AUTO-APPROVE A CLEAN DIRECTOR REVIEW PASS ONLY (2026-07-20, Julian — "i just want to
    # see the good stuff thats passed"): Director Review is the one department that grades
    # ITSELF (MediaReview.verdict + findings[]) — the other four (cinematography, voice,
    # animation, look) just write a direction with no self-assessed confidence signal to key
    # an auto-trust off, so they are deliberately untouched by this and still always stop for
    # a human decision. When the review comes back `recommend-approve` with zero BLOCK-
    # severity findings, there is nothing left for Julian to decide — approve it through the
    # SAME decide_department() path a human Approve click uses (never a shortcut), so the
    # event is fully visible and reversible in history exactly like any other approval, just
    # attributed to the reviewer that actually made the call rather than claimed as Julian's
    # own. Any `revise`/`block` verdict, or even one BLOCK finding, is untouched here and
    # still stops for a human exactly as it did before this change (confirmed live against
    # S1.SH1's own real `revise` verdict with 1 BLOCK finding, which correctly did NOT
    # auto-approve).
    if stage.startswith("review-"):
        findings = getattr(result, "findings", None) or []
        clean = (getattr(result, "verdict", None) == "recommend-approve" and
                 not any(getattr(f, "severity", None) == "BLOCK" for f in findings))
        if clean:
            decide_department(scene, stage, "approved", shot_id=shot_id, episode=episode,
                              reviewed_by="Director Review (auto — clean pass, no BLOCK "
                                          "findings)", log=log)

    return work["candidate"]


def save_department_candidate(scene, stage, text=None, lines=None, shot_id=None,
                              episode="Ep1", reviewed_by="Julian", log=print):
    """Edit the visible candidate only.  Saving never generates or approves."""
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    cand = work.get("candidate")
    if not cand:
        raise Refused(f"REFUSED — {stage} has no specialist candidate to edit")
    output = cand["output"]
    if stage == "voice":
        if not isinstance(lines, list):
            raise Refused("REFUSED — voice edits require the complete ordered line list")
        shot = _shot(pkg, shot_id)
        model = cb_departments.VoiceDirection.model_validate({**output, "lines": lines})
        cb_departments.validate_voice_direction(model, shot.get("dialogueLines") or [])
        cand["output"] = model.model_dump()
    elif stage.startswith("review-"):
        raise Refused("REFUSED — review evidence cannot be text-edited; reject and rerun the review")
    else:
        value = str(text or "").strip()
        if not value:
            raise Refused(f"REFUSED — {stage}'s exact provider text cannot be blank")
        if stage == "animation":
            shot = _shot(pkg, shot_id)
            check_formula_structure(value, shot.get("dialogueLines") or [], shot=shot,
                                    refuse_prefix="REFUSED — edited Animation candidate")
            _check_no_drift_vocab(value, refuse_prefix="REFUSED — edited Animation candidate")
        output["providerPrompt"] = value
    cand["editedAt"] = _now(); cand["editedBy"] = reviewed_by
    save_extra(); _save(pkg, path)
    log(f"DEPARTMENT CANDIDATE SAVED — {stage} (no provider call, not approved)")
    return cand


def decide_department(scene, stage, verdict, shot_id=None, note="", episode="Ep1",
                      reviewed_by="Julian", log=print):
    """Approve or reject a specialist candidate.  Never generates or mutates source canon."""
    if verdict not in ("approved", "rejected"):
        raise Refused("REFUSED — department verdict must be approved|rejected")
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    cand = work.get("candidate")
    if not cand:
        raise Refused(f"REFUSED — {stage} has no specialist candidate awaiting a decision")
    event = {**cand, "outcome": verdict, "decisionAt": _now(),
             "reviewedBy": reviewed_by, "note": str(note or "").strip()}
    if verdict == "approved":
        if work.get("approved"):
            work.setdefault("history", []).append({**work["approved"], "outcome": "superseded",
                                                    "supersededAt": _now()})
        work["approved"] = event
    else:
        if not event["note"]:
            raise Refused("REFUSED — rejection needs a plain-language note")
        work.setdefault("history", []).append(event)
    work["candidate"] = None
    save_extra(); _save(pkg, path)
    log(f"DEPARTMENT {verdict.upper()} — {stage} by {reviewed_by} (no media generated)")
    return event


def unapprove_department(scene, stage, shot_id=None, episode="Ep1", note="", reviewed_by="Julian",
                         log=print):
    """THE ALWAYS-AVAILABLE 'REJECT' FOR AN ALREADY-APPROVED DIRECTION (2026-07-20, Julian —
    "every stage should have an approve and reject and refire button"): decide_department's
    own 'rejected' verdict only ever resolves a PENDING CANDIDATE — there was previously no
    way to reject/undo a direction that's already approved without going through Refire
    first, breaking the uniform three-button model Julian is asking for. Moves the current
    approval to history (never deleted) and clears it — the shot returns to 'nothing
    approved yet,' ready for a fresh Refire. Requires a plain-language note, the same
    convention as every other rejection in this file. Refuses if a candidate is pending
    (resolve that first — Approve or Reject it) or if nothing is approved to reject."""
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    if work.get("candidate"):
        raise Refused(f"REFUSED — {stage} has a candidate awaiting a decision; "
                      f"resolve that first (Approve or Reject it)")
    approved = work.get("approved")
    if not approved:
        raise Refused(f"REFUSED — {stage} has no approved direction to reject")
    note = str(note or "").strip()
    if not note:
        raise Refused("REFUSED — rejecting an approved direction requires a plain-language note")
    work.setdefault("history", []).append({**approved, "outcome": "rejected", "rejectedAt": _now(),
                                           "reviewedBy": reviewed_by, "rejectedNote": note})
    work["approved"] = None
    save_extra(); _save(pkg, path)
    log(f"DEPARTMENT UN-APPROVED — {stage} by {reviewed_by}: {note}")
    return {"stage": stage, "shotId": shot_id, "rejectedNote": note}


def _approved_department_output(pkg, shot_id, stage):
    led = _ledger(pkg, shot_id)
    return (((led.get("departmentWork") or {}).get(stage) or {}).get("approved") or {}).get("output")


def _resolve_keyframe_prompt(pkg, shot, scene, episode="Ep1", allow_auto_heal=True):
    """A relay/non-opener shot legitimately has no keyframePrompt at all (it opens off its
    source shot's harvested final frame, never its own keyframe — keyframe_shot itself
    refuses to generate one) — returns None for that shot rather than crashing or gating;
    THE CORE LAW only applies to the paid-generation case (an opener), never to a shot that
    was never going to have a keyframe of its own in the first place.

    THE CORE LAW, HARD-ENFORCED for opener shots (2026-07-19, item 3 of the department-gate
    directive, closing the same class of fallback the forensic trace found on the Animation
    route): raises DepartmentNotApproved unless a CURRENT, human-approved Cinematography
    direction exists — NO fallback to shot["keyframePrompt"] (the storyboard's own compiled
    prose, authored before the DP ever reviewed the shot). A saved working override, if one
    exists, is layered ON TOP of that approval, never a substitute for it — save_keyframe_
    working itself requires the approval to already exist before it will save one.

    allow_auto_heal=False (2026-07-22, Julian's full-audit directive — a real bug found live:
    every READ-ONLY status/signature caller of this function was silently triggering a real
    LLM specialist re-prepare + auto-approve via _auto_heal_stale_department_if_previously_
    approved, contradicting those functions' own "zero cost"/"read-only" docstrings just by
    being opened in the Studio UI. The auto-heal itself is correct and wanted — Julian's own
    prior directive was "just the staleness re-approval step" — but it belongs ONLY at the
    moment a real generation is about to fire (keyframe_shot), never at a mere status check.
    Every read-only caller (keyframe_working_status, _keyframe_input_signature, evidence_
    pack) now passes allow_auto_heal=False; keyframe_shot itself keeps the default True."""
    if shot["sourceType"] != "opener":
        return None
    if allow_auto_heal:
        _auto_heal_stale_department_if_previously_approved(pkg, scene, "cinematography", shot["shotId"], episode)
    approved, output = _require_approved_department(
        pkg, scene, "cinematography", shot["shotId"], episode,
        action_label=f"{shot['shotId']}'s keyframe prompt resolution")
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingKeyframePrompt")
    if working and working.get("text"):
        return working["text"]
    return output["providerPrompt"]


# ── THE KEYFRAME WORKING PROMPT (Julian's directive, 2026-07-19) ────────────────────────
# The keyframe sibling of THE ANIMATION WORKING PROMPT above and THE VOICE PERFORMANCE
# WORKING VERSION further below — the same contained creative control, inside the existing
# Cinematography/Keyframe stage rather than a new one. keyframe_shot already resolves its
# fired prompt through _resolve_keyframe_prompt (edited above to prefer this working
# override); reading/saving/restoring here never calls cb_gen — only keyframe_shot's own
# real generation spends.
def keyframe_working_status(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedPrompt": str|None, "currentPrompt": str|None (working
    override if saved, else the approved prompt — exactly what keyframe_shot will submit),
    "isWorking": bool, "savedAt": str|None}. approvedPrompt/currentPrompt are both None for a
    relay shot (it has no keyframe prompt at all, by design — see _resolve_keyframe_prompt).
    For an opener with no CURRENT approved Cinematography direction, this propagates
    DepartmentNotApproved exactly like seedance_working_status does for the same missing-
    approval case — the existing route/UI (keyframePanelHTML's kw.error branch) already
    turns that into a clear on-screen message."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    if shot["sourceType"] != "opener":
        return {"approvedPrompt": None, "currentPrompt": None, "source": "none",
                "isWorking": False, "savedAt": None}
    current = _resolve_keyframe_prompt(pkg, shot, scene, episode, allow_auto_heal=False)
    led = _ledger(pkg, shot_id)
    working = led.get("workingKeyframePrompt")
    is_working = bool(working and working.get("text"))
    specialist = _approved_department_output(pkg, shot_id, "cinematography") or {}
    source = "human-working" if is_working else "cinematographer-approved"
    return {"approvedPrompt": specialist.get("providerPrompt"), "currentPrompt": current,
            "source": source, "isWorking": is_working, "savedAt": (working or {}).get("savedAt")}


def save_keyframe_working(scene, shot_id, prompt_text, episode="Ep1", reviewed_by="Julian", log=print):
    """Saves a shot-level WORKING keyframe prompt — the approved storyboard's own compiled
    keyframePrompt (and the Cinematographer's own approved providerPrompt) are never touched,
    never rewritten. NEVER calls cb_gen — this is a save, not a generation. Refused for a
    relay shot: it has no keyframe of its own to work on. REFUSES outright (2026-07-19, item
    3) unless a CURRENT, approved Cinematography direction already exists for this shot — a
    working edit can only be layered ON TOP of an already-approved brief, matching the
    identical gate save_seedance_working/save_scenelook_working now hold."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    if shot["sourceType"] != "opener":
        raise Refused(f"REFUSED — {shot_id} is a relay shot; it has no keyframe prompt of "
                      f"its own to save a working version of")
    led = _ledger(pkg, shot_id)
    _require_approved_department(pkg, scene, "cinematography", shot_id, episode,
                                  action_label=f"saving {shot_id}'s working keyframe prompt")
    text = str(prompt_text or "").strip()
    if not text:
        raise Refused(f"REFUSED — {shot_id}'s working keyframe prompt cannot be blank")
    led["workingKeyframePrompt"] = {"text": text, "savedAt": _now(), "savedBy": reviewed_by}
    _save(pkg, path)
    log(f"KEYFRAME WORKING PROMPT SAVED — {shot_id} ({len(text.split())} words, no image generated)")
    return led["workingKeyframePrompt"]


def restore_keyframe_working(scene, shot_id, episode="Ep1", log=print):
    """Clears the working override — keyframe_shot reverts to submitting the approved
    Cinematographer's providerPrompt (or the legacy authored keyframePrompt), exactly as if
    no working version had ever been saved. Never generates an image."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    led["workingKeyframePrompt"] = None
    _save(pkg, path)
    log(f"KEYFRAME WORKING PROMPT RESTORED — {shot_id}: reverted to the approved prompt")


# ── Gate 4 — voice, the exact words, one in-context call per dialogue shot ──────────────
def _vo_path(shot_id, episode):
    return MEDIA / f"{episode}_{shot_id}_vo.mp3"


# ── THE VOICE PERFORMANCE WORKING VERSION (Julian's directive, 2026-07-19) ──────────────
# A contained creative control INSIDE the existing Voice stage — not a new stage. The text
# actually submitted to ElevenLabs per dialogue line is, today, plainly the locked exactText
# (voice_shot below has never embedded delivery/tags into it). A working override lets Julian
# compose the real per-line performance text (acting direction, cadence, [bracketed] v3
# audio tags) himself; the locked exactText stays visible, separately, read-only, at all
# times — this mechanism never touches it. Reading/saving/restoring never calls cb_gen; only
# voice_shot's own real generation ever spends anything.
_LEADING_TAG_RE = re.compile(r"^\s*((?:\[[^\]]+\]\s*)+)")


def _default_voice_lines(shot):
    """The CURRENT, real, no-override performance lines. For every real dialogue line in
    this production package, the authored 'delivery' field is confirmed to be exactly
    '[tag] exactText' (2026-07-19 audit — every line, every shot, no exception found) — so
    the emotion/cadence tag the Director already authored is genuinely part of the intended
    performance, not invented here. Defaults to 'delivery' WHENEVER it verifiably decomposes
    into a leading [bracketed tag] plus the exact locked words unchanged; falls back to the
    bare locked words the instant that check fails for any single line, rather than risk
    ever submitting altered dialogue. This default is the starting point for editing, not a
    silent rewrite — Julian can freely change or remove the tag afterward."""
    out = []
    for ln in shot.get("dialogueLines") or []:
        text = ln["exactText"]
        delivery = ln.get("delivery") or ""
        m = _LEADING_TAG_RE.match(delivery)
        if m and delivery[m.end():].strip() == text.strip():
            text = m.group(1).strip() + " " + text
        out.append({"speaker": ln["speaker"], "text": text})
    return out


def _resolve_voice_lines(pkg, shot, episode="Ep1", allow_auto_heal=True):
    """Exact ElevenLabs input. THE CORE LAW, HARD-ENFORCED (2026-07-19, item 3 of the
    department-gate directive — the same class of fallback confirmed on the Animation
    route): raises DepartmentNotApproved unless a CURRENT, human-approved Voice Direction
    exists for this exact shot — no fallback to _default_voice_lines (the locked dialogue's
    own plain/tag-decomposed text, derived before the Voice Director ever reviewed it,
    however carefully). A saved working override, if one exists, is layered ON TOP of that
    approval, never a substitute for it — save_voice_working requires the approval to
    already exist before it will save one. scene is read from pkg itself (pkg["sceneNumber"]
    always matches the scene load_pkg was called with) so every existing caller — none of
    which currently pass scene explicitly — needed no signature change beyond episode.

    allow_auto_heal=False (2026-07-22, Julian's full-audit directive): see the identical note
    on _resolve_keyframe_prompt — a read-only status caller (voice_performance_status) must
    never silently trigger a real LLM re-prepare + auto-approve; only voice_shot (the real
    fire path) keeps the default True."""
    scene = pkg["sceneNumber"]
    if allow_auto_heal:
        _auto_heal_stale_department_if_previously_approved(pkg, scene, "voice", shot["shotId"], episode)
    approved, output = _require_approved_department(
        pkg, scene, "voice", shot["shotId"], episode,
        action_label=f"{shot['shotId']}'s voice performance resolution")
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingVoice")
    if working and working.get("lines"):
        return working["lines"], "human-working"
    return [{"speaker": x["speaker"], "text": x["performedText"]}
            for x in output["lines"]], "voice-director-approved"


def voice_performance_status(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedLines": [{"speaker","exactText","delivery"}...],
    "currentLines": [{"speaker","text"}...] (working override if saved, else the plain
    default), "isWorking": bool, "savedAt": str|None, "hasTake": bool, "takeMatchesCurrent":
    bool|None} — "currentLines" is exactly what voice_shot will submit if fired right now.
    "takeMatchesCurrent" answers "does the take on disk (if any) actually reflect this text?"
    — None when there's no take to ask the question about, OR when the take predates the
    voGeneratedFrom snapshot field (2026-07-19) and there's no other evidence either way (no
    working version has ever been saved, so nothing could have diverged since generation);
    True/False otherwise, resolved in two tiers: (1) an exact snapshot match/mismatch against
    voGeneratedFrom when the take was built after that field existed; (2) for an older take
    with a working version saved on top of it, a REAL comparison of the take file's own mtime
    against the working version's savedAt timestamp — a genuine "was this take built before or
    after the edit" fact, not a guess, and the same evidence that first diagnosed this bug (a
    10:40 take vs a 10:55 edit). Never guesses False just because a snapshot is missing —
    that would train the user to ignore a banner that fires on every pre-existing take.
    Also returns "takeGeneratedAt" (ISO timestamp of the live take file's own mtime, None
    if no take) — labels the take on screen as "generated at X," distinct from "savedAt"
    (when the TEXT was last edited), so it's never ambiguous which one is newer (2026-07-19,
    Julian — "we need to give some information this is the new one") — and "previous", the
    old-vs-new comparison slot: {"path" (HERE-relative, servable under /engine/...),
    "supersededAt"} for the take THIS one most recently replaced, or None."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    approved = [{"speaker": ln["speaker"], "exactText": ln["exactText"], "delivery": ln.get("delivery")}
                for ln in (shot.get("dialogueLines") or [])]
    working = led.get("workingVoice")
    # THE CORE LAW (2026-07-19): propagates DepartmentNotApproved exactly like
    # seedance_working_status/keyframe_working_status do for the identical missing-approval
    # case — the existing route/UI (voicePanelHTML's vw.error branch) already turns that
    # into a clear on-screen message.
    current, source = _resolve_voice_lines(pkg, shot, episode, allow_auto_heal=False)
    vo_path = led.get("voPath")
    has_take = bool(vo_path)
    generated_from = led.get("voGeneratedFrom")
    if not has_take:
        match = None
    elif generated_from is not None:
        match = (generated_from == current)
    elif not working:
        match = True  # no edit ever recorded — nothing could have diverged since generation
    else:
        # legacy take, predates the snapshot field, but a working edit exists on top of it —
        # fall back to a real mtime-vs-savedAt comparison rather than guessing.
        try:
            take_mtime = os.path.getmtime(vo_path)
            saved_at = working.get("savedAt")
            match = not (saved_at and datetime.datetime.fromisoformat(saved_at).timestamp() > take_mtime)
        except (OSError, ValueError):
            match = None  # can't prove it either way — stay silent, never alarm on a guess
    take_generated_at = None
    if has_take:
        try:
            take_generated_at = datetime.datetime.fromtimestamp(
                os.path.getmtime(vo_path)).isoformat(timespec="seconds")
        except OSError:
            take_generated_at = None
    # THE MISSING AUDIO PLAYER (2026-07-20, Julian — "I can't see where the new voice
    # is"): this function has always computed take_generated_at from vo_path but never
    # actually returned vo_path (or a servable form of it) to the client — voicePanelHTML
    # could show a "Current take — generated at X" LABEL but had no path to build an
    # <audio> element from, matching the SAME already-solved shape "previous" uses
    # (HERE-relative, servable under /engine/...). Computed the identical way, so the
    # current and previous takes render with the same kind of player.
    current_take_path = None
    if has_take:
        try:
            current_take_path = str(pathlib.Path(vo_path).resolve().relative_to(HERE.resolve()))
        except (ValueError, OSError):
            current_take_path = None  # not under HERE/media — can't build a safe relative URL
    return {"approvedLines": approved, "currentLines": current, "source": source,
            "isWorking": bool(working), "savedAt": (working or {}).get("savedAt"),
            "hasTake": has_take, "takeMatchesCurrent": match,
            "takeGeneratedAt": take_generated_at, "currentTakePath": current_take_path,
            "previous": led.get("voicePrevious")}


def save_voice_working(scene, shot_id, lines, episode="Ep1", reviewed_by="Julian", log=print):
    """Saves a shot-level WORKING performance version — the approved dialogueLines (the
    locked words) are never touched, never rewritten, never re-ordered. lines must be the
    same length as the shot's own dialogueLines, same speaker per position (only the
    submitted TEXT per line may differ from exactText — acting direction/cadence/tags
    composed directly into it); a mismatch refuses rather than silently reordering or
    dropping a line. REFUSES outright (2026-07-19, item 3) unless a CURRENT, approved Voice
    Direction already exists for this shot — a working edit can only be layered ON TOP of
    an already-approved performance, matching the identical gate every other working-prompt
    save in this file now holds. NEVER calls cb_gen — this is a save, not a generation."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    _require_approved_department(pkg, scene, "voice", shot_id, episode,
                                  action_label=f"saving {shot_id}'s working voice performance")
    dl = shot.get("dialogueLines") or []
    if len(lines) != len(dl):
        raise Refused(f"REFUSED — {shot_id} has {len(dl)} approved dialogue line(s); "
                      f"the working version must have exactly that many, in the same order")
    clean = []
    for i, (ln, dl_ln) in enumerate(zip(lines, dl)):
        text = str(ln.get("text") or "").strip()
        if not text:
            raise Refused(f"REFUSED — working line {i+1} has no performance text")
        speaker = ln.get("speaker") or dl_ln["speaker"]
        if _resolve_char(speaker, _characters_cfg()) != _resolve_char(dl_ln["speaker"], _characters_cfg()):
            raise Refused(f"REFUSED — working line {i+1}'s speaker ({speaker}) does not match "
                          f"the approved line's speaker ({dl_ln['speaker']}); reorder/relabel refused")
        clean.append({"speaker": dl_ln["speaker"], "text": text})
    led["workingVoice"] = {"lines": clean, "savedAt": _now(), "savedBy": reviewed_by}
    _save(pkg, path)
    log(f"VOICE WORKING VERSION SAVED — {shot_id}: {len(clean)} line(s) (no audio generated)")
    return led["workingVoice"]


def restore_voice_working(scene, shot_id, episode="Ep1", log=print):
    """Clears the working override — voice_shot reverts to submitting exactText verbatim,
    the same as if no working version had ever been saved. Never generates audio."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    led["workingVoice"] = None
    _save(pkg, path)
    log(f"VOICE WORKING VERSION RESTORED — {shot_id}: reverted to the approved dialogue's plain text")


def _stretch_natural_pause(audio_path, min_onset_sec, log=print):
    """Widens the SINGLE largest pre-existing silence in a dialogue take so the SPEECH
    THAT FOLLOWS IT starts no earlier than min_onset_sec — never touches a word of the
    actual vocal performance, only the silence between two turns. Built for
    cb_engine.DialogueLine.minOnsetSec (2026-07-22, Julian's real-footage diagnosis:
    S1.SH1's "Nailed it." never landed on screen because the picture's own physical
    climax — bounce-chain, backflip, landing, confusion — takes several real seconds
    regardless of how long ElevenLabs happens to render the chant that precedes it;
    confirmed live across two real generations of the SAME take, whose chant rendered at
    2.4s in one and 3.9s in the other. Anchoring to an ABSOLUTE onset time, not a fixed
    ADDED gap, is what survives that variance — a fixed added gap would still leave the
    line landing at a different, unpredictable point in the picture each time it's rolled.
    Detects the gap via ffmpeg silencedetect and takes the LARGEST one found, on the
    narrow theory that a short multi-turn take's biggest pause is its real inter-line
    boundary — a deliberately scoped heuristic for exactly this shape of take, not a
    general alignment claim. No-op (returns False, changes nothing) if the line already
    starts at or after the target or no usable gap is found — a wrong guess at the split
    point would corrupt real speech, so this only ever acts on real evidence."""
    dur = cb_post._dur(audio_path)
    if dur <= 0:
        return False
    r = subprocess.run(["ffmpeg", "-i", audio_path, "-af",
                        "silencedetect=noise=-30dB:d=0.15", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", r.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", r.stderr)]
    pairs = list(zip(starts, ends))
    if not pairs:
        log(f"  (no natural pause detected in {audio_path} — minOnsetSec left unstretched)")
        return False
    gap_start, gap_end = max(pairs, key=lambda p: p[1] - p[0])
    needed = min_onset_sec - gap_end
    if needed <= 0.05:
        return False
    tmp_silence = audio_path + ".silence.mp3"
    tmp_out = audio_path + ".stretched.mp3"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", f"{needed:.3f}", "-q:a", "9", tmp_silence],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", audio_path, "-i", tmp_silence, "-i", audio_path,
                    "-filter_complex",
                    f"[0:a]atrim=0:{gap_start:.3f},asetpts=PTS-STARTPTS[a];"
                    f"[1:a]asetpts=PTS-STARTPTS[b];"
                    f"[2:a]atrim=start={gap_start:.3f},asetpts=PTS-STARTPTS[c];"
                    f"[a][b][c]concat=n=3:v=0:a=1[out]",
                    "-map", "[out]", tmp_out],
                   check=True, capture_output=True)
    os.replace(tmp_out, audio_path)
    os.remove(tmp_silence)
    log(f"  STRETCHED the take's own natural pause at {gap_start:.1f}s so the following "
        f"line now starts at {min_onset_sec:.1f}s (was {gap_end:.1f}s) — no word of the "
        f"performance touched")
    return True


def voice_shot(pkg, path, shot_id, episode="Ep1", log=print):
    shot = _shot(pkg, shot_id)
    if not shot.get("dialogueLines"):
        return None
    _require_confirmed_billing("elevenlabs")               # protection 5 — block, not warn
    characters_cfg = _characters_cfg()
    led = _ledger(pkg, shot_id)
    # AN APPROVED TAKE IS NEVER SILENTLY CLOBBERED (2026-07-19): matching keyframe/scenelook's
    # own "reject first" discipline — voice has no candidate/history mechanism of its own
    # (it writes to one fixed path), so the ONLY protection against overwriting an approved
    # take is refusing outright until it's explicitly rejected.
    if (led.get("voiceApproval") or {}).get("approved"):
        raise Refused(f"REFUSED — {shot_id}'s voice take is already approved; reject it "
                      f"first (with a reason) before generating another")
    # THE WORKING VERSION, IF ANY, IS WHAT ACTUALLY SUBMITS (2026-07-19): a saved override
    # is the whole point of editing it. THE CORE LAW's own hard gate lives inside
    # _resolve_voice_lines — raises DepartmentNotApproved unless a CURRENT, approved Voice
    # Direction exists; no fallback to the plain locked exactText.
    working = led.get("workingVoice")
    perf_lines, performance_source = _resolve_voice_lines(pkg, shot, episode)
    if len(perf_lines) != len(shot["dialogueLines"]):
        # a stale working version or approved direction (e.g. the storyboard's own
        # dialogueLines changed count since it was prepared/saved) — refuse outright rather
        # than silently falling back to the locked default and submitting a performance the
        # Voice Director never actually reviewed against the CURRENT dialogue (2026-07-19,
        # item 3: no silent fallback on any paid production route, ever).
        raise Refused(f"REFUSED — {shot_id}'s resolved performance ({performance_source}) has "
                      f"{len(perf_lines)} line(s) but the shot's locked dialogue now has "
                      f"{len(shot['dialogueLines'])}; re-prepare and re-approve the Voice "
                      f"Direction (or re-save the working version) against the current "
                      f"dialogue before firing — a stale count is never silently realigned.")
    turns = []
    for ln, perf in zip(shot["dialogueLines"], perf_lines):
        vid = (characters_cfg.get(_resolve_char(ln["speaker"], characters_cfg)) or {}).get("voiceId")
        if not vid:
            raise Refused(f"REFUSED — no ElevenLabs voiceId for {ln['speaker']} "
                          f"(Law 5: the voice lives in the render; no fallback)")
        turns.append({"text": perf["text"], "voice_id": vid})
    # DISCLOSURE PARITY WITH fire_shot (2026-07-22, Julian's full-audit directive): the exact
    # same transparency gap fire_shot's disclosure log was fixed for tonight — this bare
    # "(working version)" suffix named THAT an override was active but never who saved it,
    # when, or what the actual performance text is, before spending real ElevenLabs money.
    if working:
        log(f"  ⚠⚠⚠ USING A SAVED WORKING VOICE VERSION (saved by {working.get('savedBy','?')} "
            f"on {working.get('savedAt','?')}) — this REPLACES the Voice Director's current "
            f"approved performance below.")
    log("  --- THE EXACT LINES ABOUT TO BE SUBMITTED TO ELEVENLABS ---")
    for t in turns:
        log(f"  | {t['text']}")
    log("  --- end of lines ---")
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = _vo_path(shot_id, episode)
    kind = "regeneration" if led.get("voPath") else "generation"
    # OLD VS NEW, KEPT FOR COMPARISON (2026-07-19, Julian — "show the old one and the new
    # one to see the difference, then get rid of one or the other"): a regeneration used to
    # silently overwrite the one fixed take path with no trace of what it replaced. The
    # about-to-be-superseded file is archived (moved, never deleted) BEFORE the new one is
    # written, and recorded as a single voicePrevious slot — not an unbounded history, just
    # "what this take replaced" — so the Studio can play both and restore_previous_voice_take
    # can bring the old one back if it wins the comparison.
    if kind == "regeneration" and os.path.exists(out):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "shots_superseded" / f"{episode}_{shot_id}_voice_{ts}"
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / out.name
        shutil.move(str(out), str(dest))
        led["voicePrevious"] = {"path": str(dest.relative_to(HERE)),
                                 "generatedFrom": led.get("voGeneratedFrom"),
                                 "supersededAt": _now()}
    cb_gen.eleven_dialogue(turns, out=str(out), generation_kind=kind,
                            production_route="cb_render")
    # THE PACE STRETCH (2026-07-22, Julian's real-footage diagnosis — "he doesn't perform
    # the nailed it either"): a director-authored minOnsetSec on any dialogueLine widens
    # the take's own single largest natural pause so that line's onset lands at or after
    # the picture's own real climax, in place — never a re-synthesis, never a word of the
    # actual performance touched. A no-op for every shot that doesn't set it (every shot
    # today except the one this was built for).
    onsets = [ln.get("minOnsetSec") for ln in shot["dialogueLines"] if ln.get("minOnsetSec")]
    if onsets:
        _stretch_natural_pause(str(out), max(onsets), log=log)
    led["voPath"] = str(out)
    # THE STALE-TAKE FLAG (2026-07-19, Julian — "I don't feel the acting from the direction
    # changed anything"): traced live to a real, confirmed gap — editing and saving a working
    # version never regenerates audio (correctly, by design), but nothing told the user the
    # take on screen was built BEFORE their edit existed. Snapshotting exactly which lines
    # produced THIS take lets voice_performance_status compare it to whatever's current and
    # say so plainly, instead of leaving "did my edit do anything?" as a guess from timestamps.
    led["voGeneratedFrom"] = perf_lines
    # THE DURABLE "WHAT WAS ACTUALLY SUBMITTED" RECORD (2026-07-22, Julian's directive —
    # "ensure the prompts I see in the studio are the exact prompts that go to the API"):
    # mirrors the identical record keyframe_shot now writes to led["lastKeyframeEnvelope"].
    # A live status panel can only ever preview the CURRENT resolved lines — it cannot prove
    # what a PAST take actually used. `turns` is exactly what cb_gen.eleven_dialogue was
    # just called with, above, never re-derived. NAMED GAP, not silently claimed complete:
    # this route still has no cryptographic disclose-then-confirm seal like fire_shot/
    # keyframe_shot's — voice_scene's whole-scene batch loop calls voice_shot per shot with
    # no token dance today, and retrofitting that batch semantics safely is a genuinely
    # separate piece of work, deliberately not attempted in the same pass as this record.
    led["lastVoiceEnvelope"] = {"voPath": str(out), "turns": turns, "firedAt": _now()}
    _save(pkg, path)
    log(f"VOICE — {shot_id}: {len(turns)} line(s){' (working version)' if working else ''} -> {out.name}")
    return str(out)


def voice_scene(scene, episode="Ep1", log=print):
    """Builds a voice track for every dialogue shot that either has none yet, OR whose
    existing take is a CONFIRMED stale mismatch against its current working-version text
    (voice_performance_status's takeMatchesCurrent is False — the "no" answer only,
    never a guess: None/True both leave an existing take alone). THE FIX (2026-07-19,
    "I fired but it's not populating with the latest version"): this used to skip ANY
    shot with a voPath at all, regardless of whether that take reflected the current
    text — meaning the Studio's own "↻ Regenerate" button, which calls this same
    function scene-wide, silently no-op'd on every shot that already had SOME take,
    including one just proven stale by the banner sitting right above the button that
    fired it. Re-checked per shot, not once for the whole scene, since a scene's shots
    go stale independently of each other."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    done, skipped = [], []
    for s in pkg["shots"]:
        if not s.get("dialogueLines"):
            continue
        led = _ledger(pkg, s["shotId"])
        if led.get("voPath"):
            status = voice_performance_status(scene, s["shotId"], episode)
            if status.get("takeMatchesCurrent") is not False:
                continue  # has a take, and it's not a CONFIRMED mismatch — leave it alone
        # ONE SHOT'S MISSING/STALE DEPARTMENT APPROVAL NEVER SINKS THE WHOLE SCENE SWEEP
        # (2026-07-19): a per-item isolation, matching cb_retake.process_retakes' own fix for
        # the identical class of bug — a single bad shot used to crash the batch, losing
        # every OTHER shot's already-completed work. THE CORE LAW's gate still refuses that
        # one shot; it just no longer takes the rest of the scene down with it.
        try:
            done.append(voice_shot(pkg, path, s["shotId"], episode, log=log))
        except DepartmentNotApproved as e:
            skipped.append({"shotId": s["shotId"], "reason": str(e)})
            log(f"VOICE — scene {scene}: {s['shotId']} skipped — {e}")
    log(f"VOICE — scene {scene}: {len(done)} shot track(s) built"
        + (f", {len(skipped)} skipped (no current approved Voice Direction)" if skipped else ""))
    return done


def regen_voice_shot(scene, shot_id, episode="Ep1", log=print):
    """THE EXPLICIT PER-SHOT FORCE (2026-07-19, Julian — "I've just regenerated voice b1
    and I don't know if it's gone, if it's done, if the one on the screen is it"): traced
    live to a real, confirmed gap — the Studio's "↻ Regenerate" button (both places it
    appears) always fired the scene-wide voice_scene() above with no shotId, and that
    function's own job is to skip anything not CONFIRMED stale (the fix from earlier the
    same day). So clicking Regenerate on a shot whose take already matches its text — the
    exact case here — silently did nothing: a real job ran, completed, and rebuilt zero
    shots, with no distinct message telling the user that's what happened. "Regenerate" is
    a direct, explicit request for THIS shot; it must never be silently absorbed by a
    gap-fill sweep's own staleness gate. voice_shot() itself has no staleness gate at all —
    it always fires for whatever shot_id it's given — this is just that same single-shot
    call, exposed as its own CLI-facing entry point distinct from voice_scene's sweep, so
    the front door can call it directly instead of going through the scene-wide function
    that would silently no-op it."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    out = voice_shot(pkg, path, shot_id, episode, log=log)
    if out is None:
        raise Refused(f"REFUSED — {shot_id} has no dialogue lines to voice")
    return out


# ── THE VOICE APPROVAL STEP (Julian, 2026-07-19 — "does it appear to listen to and
# approve?"): every OTHER stage in this render loop (keyframe, animation) already requires
# an explicit human approval before its output may anchor anything downstream; voice never
# had one — any generated file, listened to or not, silently satisfied animation's own
# readiness check. Closed here, matching the existing pattern exactly: approve/reject on the
# ledger, animation's own gate (fire_shot, below) now requires the approval, not mere file
# existence.
def approve_voice(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    vo = led.get("voPath")
    if not vo or not os.path.exists(vo):
        raise Refused(f"REFUSED — {shot_id} has no voice track to approve")
    led["voiceApproval"] = {"approved": True, "path": vo, "at": _now(), "reviewedBy": reviewed_by}
    _save(pkg, path)
    log(f"VOICE APPROVED — {shot_id} by {reviewed_by}")
    return led["voiceApproval"]


def unapprove_voice(scene, shot_id, episode="Ep1", note="", reviewed_by="Julian", log=print):
    """UNDO A VOICE APPROVAL (2026-07-25, same ruling as unapprove_keyframe) — clears the
    approval only; the take itself stays on disk exactly as it was, back to awaiting your
    ear (re-approve, reject with a note, or regenerate)."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    appr = led.get("voiceApproval")
    if not appr or not appr.get("approved"):
        raise Refused(f"REFUSED — {shot_id} has no voice approval to undo")
    led.setdefault("voiceHistory", []).append({**appr, "outcome": "unapproved",
                                                "unapprovedAt": _now(), "reviewedBy": reviewed_by,
                                                "unapprovedNote": (note or "").strip() or None})
    led["voiceApproval"] = None
    _save(pkg, path)
    log(f"VOICE UN-APPROVED — {shot_id} by {reviewed_by}; the take stays on disk, back to "
        f"AWAITING your decision")
    return True


def reject_voice(scene, shot_id, correction, episode="Ep1", reviewed_by="Julian", log=print):
    """Archives the current take (moved, never deleted — the same discipline every other
    stage's rejection already follows) and clears voPath/voiceApproval so the shot can be
    regenerated. Always requires a plain-language reason, on record."""
    if not (correction or "").strip():
        raise Refused("REFUSED — a voice rejection requires a plain-language reason")
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    vo = led.get("voPath")
    if not vo:
        raise Refused(f"REFUSED — {shot_id} has no voice track to reject")
    archived_rel = None
    if os.path.exists(vo):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_voice_{ts}"
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / os.path.basename(vo)
        shutil.move(vo, dest)
        archived_rel = str(dest.relative_to(HERE))
    rejection = {"outcome": "rejected", "rejectedAt": _now(), "reason": correction.strip(),
                 "reviewedBy": reviewed_by, "rejectedFile": archived_rel}
    led.setdefault("voiceRejections", []).append(rejection)
    led["voPath"] = None
    led["voiceApproval"] = None
    led["voGeneratedFrom"] = None
    # a formal reject is a bigger, explicit decision than a quiet regeneration — the
    # old-vs-new comparison slot no longer applies to whatever comes next, so it's cleared
    # rather than left pointing at a take from before this rejected one.
    led["voicePrevious"] = None
    _save(pkg, path)
    log(f"VOICE REJECTED — {shot_id}: {correction}\n  archived -> "
        f"{archived_rel or '(no file was present)'}")
    return archived_rel


def restore_previous_voice_take(scene, shot_id, episode="Ep1", log=print):
    """THE "ACTUALLY, THE OLD ONE WAS BETTER" ACTION (2026-07-19): swaps the CURRENT take
    back out for whatever it most recently superseded (voicePrevious) — the other half of
    the old-vs-new comparison voice_shot's own pre-overwrite archival now supports. Never a
    destructive swap: the take being displaced BY this restore is itself archived in turn
    (never simply deleted), so a second restore can undo the first. Distinct from
    restore_voice_working (which reverts the TEXT to the approved default, no audio
    involved) — this one swaps actual audio files. Refuses if there's nothing to restore, or
    if the current take is already approved (matching voice_shot's own reject-first rule)."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    prev = led.get("voicePrevious")
    if not prev:
        raise Refused(f"REFUSED — {shot_id} has no previous take to restore")
    if (led.get("voiceApproval") or {}).get("approved"):
        raise Refused(f"REFUSED — {shot_id}'s voice take is already approved; reject it "
                      f"first (with a reason) before restoring an earlier one")
    prev_abs = HERE / prev["path"]
    if not prev_abs.exists():
        raise Refused(f"REFUSED — {shot_id}'s previous take file is missing on disk "
                      f"({prev['path']}) — nothing to restore")
    cur_path = led.get("voPath")
    cur_generated_from = led.get("voGeneratedFrom")
    archived_rel = None
    if cur_path and os.path.exists(cur_path):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "shots_superseded" / f"{episode}_{shot_id}_voice_{ts}"
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / os.path.basename(cur_path)
        shutil.move(cur_path, str(dest))
        archived_rel = str(dest.relative_to(HERE))
    live_path = _vo_path(shot_id, episode)
    MEDIA.mkdir(parents=True, exist_ok=True)
    shutil.move(str(prev_abs), str(live_path))
    led["voPath"] = str(live_path)
    led["voGeneratedFrom"] = prev.get("generatedFrom")
    led["voicePrevious"] = ({"path": archived_rel, "generatedFrom": cur_generated_from,
                              "supersededAt": _now()} if archived_rel else None)
    _save(pkg, path)
    log(f"VOICE RESTORED — {shot_id}: reverted to the take superseded on "
        f"{prev.get('supersededAt')}")
    return led["voPath"]


# ── Gate 5 — THE TIMING SLATE (reclassified, Julian's probabilistic-model correction,
# 2026-07-16): a dialogue and shot-duration timing slate, NOT a creative animatic. It
# supports approval of exactly five things — dialogue accuracy, character voice assignment,
# broad shot duration, overall scene length, intended dialogue position — and must never be
# presented as proof of physical comedy, staging, animation, geography or final rhythm.
def animatic_scene(scene, episode="Ep1", log=print):
    """Builds the TIMING SLATE (function name kept for CLI/Studio compatibility)."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    MEDIA.mkdir(parents=True, exist_ok=True)
    clips = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        img = led.get("keyframePath") or _slate(s, episode)
        vo = led.get("voPath")
        dur = max(float(s["durationSec"]), (_audio_dur(vo) + 0.5) if vo else 0.0)
        clip = MEDIA / f"{episode}_{s['shotId']}_timing_slate.mp4"
        _hold(img, dur, vo, str(clip))
        clips.append(str(clip))
    out = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    result = cb_post.assemble_picture(clips, str(out))
    if not result:
        raise Refused("timing-slate assembly failed — see ffmpeg output above")
    log(f"TIMING SLATE — scene {scene}: {len(clips)} shots -> {out.name} · approves dialogue "
        f"accuracy, voice assignment, shot durations, scene length and line position ONLY — "
        f"it does not prove staging, physical comedy or final rhythm")
    return str(out)


def _slate(shot, episode):
    """A plain title card for a shot with no keyframe yet — PIL, reusing cb_post's proven
    font fallback (never ffmpeg drawtext; that availability bug was already fixed once)."""
    from PIL import Image, ImageDraw
    out = MEDIA / f"{episode}_{shot['shotId']}_slate.png"
    img = Image.new("RGB", (1280, 720), (24, 26, 32))
    d = ImageDraw.Draw(img)
    font = cb_post._pil_font(44)
    d.text((60, 280), shot["shotId"], fill=(240, 240, 240), font=font)
    d.text((60, 350), (shot.get("purpose") or "")[:70], fill=(170, 180, 200),
           font=cb_post._pil_font(28))
    img.save(out)
    return str(out)


def _audio_dur(p):
    # _engine_path, not the bare path: measuring 0.0 from cb-studio/ and the real duration
    # from engine/ put a different measuredAudioDurationSec into the department signature
    # depending on which process asked — the second half of the same cwd bug.
    return cb_post._dur(_engine_path(p)) or 0.0


def _hold(img, dur, audio, out):
    # every hold carries a real audio stream (silent when no voice) — the scene assembler's
    # concat maps [i:a] on EVERY clip; and -t bounds the output (never -shortest, which would
    # truncate a 6s hold to its 2s voice track). Found by the first real animatic assembly.
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", img]
    if audio:
        cmd += ["-i", audio]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-t", f"{dur:.2f}", "-r", "24", "-pix_fmt", "yuv420p",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-af", "apad", "-c:a", "aac", out]
    import subprocess as sp
    r = sp.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise Refused(f"timing-slate hold failed for {out}: {r.stderr.decode()[-300:]}")
    return out


# ── Gate 6 — the opener keyframe (anticipation, reference-first) ────────────────────────
# THE KEYFRAME LIFECYCLE (Julian's state-integrity checkpoint, 2026-07-17, corrected
# 2026-07-18 — production-safety + direct-input lineage): a generated keyframe is a
# CANDIDATE, never automatically the shot's approved truth. It enters the ledger as
# keyframeCandidate (awaiting a decision); approve_keyframe/reject_keyframe below are the
# only ways it becomes keyframeApproval (usable as a fire anchor) or keyframeRejected
# (archived, history-only, never able to approve or unlock anything).
#
# THE 2026-07-18 CORRECTION, TWO PARTS:
#  (1) NON-DESTRUCTIVE TWO-PHASE LIFECYCLE — a new candidate is generated to its OWN unique
#      path; the shot's currently-approved keyframe (if any) is never touched, moved or
#      overwritten by a fresh generation, win or lose. Only on APPROVAL of the new candidate
#      is the old approved file archived — the exact same discipline just applied to the
#      Scene Look Plate above, after a failed plate regeneration archived the approved file
#      before its replacement existed.
#  (2) DIRECT-INPUT LINEAGE (item 3) — validity is no longer "does the whole storyboard/
#      package md5 match": it is "does THIS shot's own card hash (read fresh from the live
#      storyboard, never the package), the approved Scene Look hash, the reference file
#      hashes, the compiled brief text and the model/settings still match what this
#      candidate was actually generated from." An edit to a DIFFERENT shot (S1.SH6, say)
#      changes none of these for S1.SH1 — so it can never invalidate S1.SH1's own candidate
#      or approval, the exact blanket-invalidation bug this correction closes.
def _live_card_hash(shot_id, scene, episode="Ep1"):
    """This shot's OWN creative-card hash, read directly from the LIVE approved storyboard —
    never from a (possibly stale) production package. Identical hashing to
    cb_handover._scoped_shot's own card_hash, so it can be compared against a package's
    cached sourceStoryboard.creativeCardHashes[shot_id] or stored on a candidate/approval
    and re-checked later, independent of any OTHER shot's own edits."""
    p = _storyboard_path(scene, episode)
    if not p.exists():
        return None
    sb = json.load(open(p))
    sb_shot = next((s for s in sb.get("shots", []) if s.get("shotId") == shot_id), None)
    if sb_shot is None:
        return None
    return hashlib.sha256(json.dumps(sb_shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _keyframe_input_signature(pkg, shot, scene, episode="Ep1"):
    """THE KEYFRAME'S DIRECT INPUTS (item 3): this shot's own card hash, the approved Scene
    Look plate's hash (None if not currently approved), every reference file's content hash,
    the compiled keyframe-brief text's hash, and the model/settings that would render it.
    Package revision plays no role here at all — it remains provenance evidence elsewhere
    (lineage_status), never a validity gate."""
    characters_cfg = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    st = scenelook_status(scene, episode)
    scenelook_hash = (st["approved"] or {}).get("hash") if st["status"] == "approved" else None
    prompt = _resolve_keyframe_prompt(pkg, shot, scene, episode, allow_auto_heal=False) or ""
    return {"cardHash": _live_card_hash(shot["shotId"], scene, episode),
            "sceneLookHash": scenelook_hash,
            "referenceHashes": {os.path.basename(p): _file_md5(p) for p in refs},
            "briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "model": _image_model_label()}


def _image_model_label():
    """THE PROVIDER-AWARE MODEL LABEL (2026-07-22, alongside the BytePlus ModelArk switch): this
    used to hardcode cb_gen.SEEDREAM_ENDPOINT (fal.ai's own endpoint id) into every keyframe's
    staleness signature regardless of cb_gen.SEEDREAM_HOST — the same "disclosure/signature must
    reflect the LIVE provider, not a frozen assumption" gap already found and fixed for video's
    _binding_hash/_sealed_envelope. IMAGE_PROVIDER == "nanobanana" is unaffected by SEEDREAM_HOST
    (a distinct model family, always direct-Gemini)."""
    if cb_gen.IMAGE_PROVIDER == "nanobanana":
        return f"nanobanana:{cb_gen.IMAGE_MODEL}:2K"
    if cb_gen.SEEDREAM_HOST == "fal":
        return f"seedream:{cb_gen.SEEDREAM_ENDPOINT}:2K"
    return f"seedream:{cb_gen.BYTEPLUS_SEEDREAM_MODEL}:2K"


def _signature_diff(old, new):
    """The list of top-level keys where two input signatures differ — empty means every
    direct input this artefact depends on is unchanged; the artefact is still current."""
    keys = sorted(set(old or {}) | set(new or {}))
    return [k for k in keys if (old or {}).get(k) != (new or {}).get(k)]


def reassess_keyframe(scene, shot_id, episode="Ep1"):
    """READ-ONLY, GENERATES NOTHING (item 4): compares an existing keyframe candidate's or
    approval's recorded direct-input signature against what those SAME inputs resolve to
    right now. Returns {"verdict": "carry_forward"|"regenerate"|"none", "changed": [...],
    "existing": {...}|None, "currentSignature": {...}|None} — "carry_forward" means the
    existing candidate/approval and its recorded decision are still valid evidence and may
    be carried forward transactionally, with no new render; "regenerate" names exactly which
    input(s) changed.

    THE NON-GENERATED-SOURCE FIX (2026-07-22, found live in the Studio — Julian: "I know
    it's saying it's already approved... but then they're saying waiting for approval.
    What's it waiting for approval for?"): approve_keyframe's OWN docstring already states
    the correct rule — a candidate chosen via a non-generation source (uploaded, from this
    shot's own library/history, or carried from the previous shot's final frame) "has no
    compiled-brief inputs to drift from; it is approved on the strength of the human's own
    deliberate choice... rather than input-signature-checked." This function never actually
    implemented that distinction: it unconditionally diffed inputSignature against the
    current signature regardless of source. A non-generated approval always carries
    inputSignature=None BY DESIGN (keyframe_shot only ever stamps a real signature onto a
    GENERATED candidate) — comparing None against anything reports every field as
    "changed," so any uploaded/library/carried-forward keyframe was PERMANENTLY flagged
    "regenerate," forever, no matter what — the exact confirmed cause of S1.SH1's top-
    ribbon "awaiting"/stale flag sitting directly beside its own "✓ Approved" panel.
    Fixed to skip the signature diff entirely for a non-generated source, matching
    approve_keyframe's own already-correct rule — a real generated candidate is still
    checked exactly as before."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    existing = led.get("keyframeApproval") or led.get("keyframeCandidate")
    if not existing:
        return {"verdict": "none", "changed": [], "existing": None, "currentSignature": None}
    if existing.get("source", "generated") != "generated":
        # Never even resolves the current signature for a non-generated source — that
        # resolution itself requires an approved Cinematography Direction to exist
        # (_keyframe_input_signature -> _resolve_keyframe_prompt's own CORE LAW gate), a
        # real precondition a shot approved purely by upload/library/carry-forward has no
        # obligation to satisfy. Computing it here just to immediately discard it would
        # make this READ-ONLY function needlessly fail on a perfectly valid, already-
        # approved non-generated shot.
        return {"verdict": "carry_forward", "changed": [], "existing": existing,
                "currentSignature": None}
    current_sig = _keyframe_input_signature(pkg, shot, scene, episode)
    diff = _signature_diff(existing.get("inputSignature"), current_sig)
    return {"verdict": "carry_forward" if not diff else "regenerate",
            "changed": diff, "existing": existing, "currentSignature": current_sig}


def _keyframe_provider_key():
    """Which cb_costs.RATES entry actually prices the CURRENT keyframe provider, mirroring
    _video_provider_rate_key's own "the disclosure must reflect the provider active RIGHT
    NOW" doctrine — hardcoding one host here would show Julian a false rate the instant
    IMAGE_PROVIDER/SEEDREAM_HOST changes."""
    if cb_gen.IMAGE_PROVIDER == "nanobanana":
        return "nanobanana2"
    return "seedream5pro_byteplus" if cb_gen.SEEDREAM_HOST == "byteplus" else "seedream5pro"


def _keyframe_binding_hash(pkg, shot, refs, prompt):
    """THE SEAL, KEYFRAME EDITION (2026-07-22, Julian — "are you sure the right prompt
    launched... your mistakes have cost me money"): fire_shot has carried a cryptographic
    disclose-then-confirm seal since 2026-07-16 (protection 1: the exact package hash,
    provider, prompt, every reference file's own content hash — anything that changes
    between disclosure and generation invalidates the token). keyframe_shot had NONE of
    this: it resolved a prompt (with auto-heal free to recompile a genuinely NEW one from a
    changed storyboard) and fired in the same breath, with only a printed log line standing
    between "resolved" and "spent" — never a structural guarantee that what was shown is
    what was sent. This is that same seal, applied to the keyframe route for the first
    time, mirroring _binding_hash's contract exactly (package hash, provider/rate, the
    resolved prompt text, reference slot order, every reference file's content hash)."""
    import cb_costs
    key = _keyframe_provider_key()
    rate = cb_costs.estimate_image_cost(provider=key)
    payload = {"packageHash": _shots_hash(pkg), "shotId": shot["shotId"],
               "provider": cb_gen.IMAGE_PROVIDER, "providerKey": key, "costUsd": rate,
               "prompt": prompt, "slotOrder": shot["keyframeReferenceSlots"],
               "refMd5s": [_file_md5(p) for p in refs]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32], rate


def _keyframe_sealed_envelope(pkg, shot, refs, prompt, rate):
    """THE IMMUTABLE PROVIDER-REQUEST ENVELOPE, KEYFRAME EDITION — mirrors _sealed_envelope's
    video contract (§5): everything the provider will receive, sealed AT DISCLOSURE. The
    spend token binds to this envelope's hash; firing sends THIS, never a recompile. Shares
    the "references"/"audio" shape _verify_envelope already checks generically (audio is
    always None here — a keyframe has no audio input) so the identical seal-check function
    verifies both routes without duplication."""
    img_slots = [t for t in shot["keyframeReferenceSlots"] if t != "@Audio1"]
    refs_list = [{"slot": t, "role": shot["keyframeReferenceSlots"][t], "path": p, "md5": _file_md5(p)}
                 for t, p in zip(img_slots, refs)]
    env = {"shotId": shot["shotId"], "prompt": prompt, "provider": cb_gen.IMAGE_PROVIDER,
           "costUsd": rate, "packageRevision": pkg.get("revision"),
           "references": refs_list, "audio": {"path": None, "md5": None}}
    h = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return env, h


def _auto_confirm_keyframe(scene, shot_id, episode, log):
    """Drives keyframe_shot's own disclose-then-confirm seal in one call — used ONLY by
    advance_shot (see its own docstring, right above its call site, for why auto-confirming
    here is correct and not a bypass: Julian's keyframe stop was always "look at the image
    after," never "approve the spend before," so this simply keeps that existing behaviour
    while the seal's real guarantee — disclosed equals sent — is satisfied trivially by
    firing both halves back-to-back against the same in-memory state). Never used by any
    Studio route directly; the Studio's own JS auto-continue drives the identical two-step
    dance itself, from the browser, for the exact same reason."""
    first_refusal = None
    try:
        keyframe_shot(scene, shot_id, episode, log=log)
    except Refused as e:
        first_refusal = e
    pkg, _ = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    auth = led.get("pendingKeyframeSpendAuth")
    if not auth:
        # a genuine, earlier-stage refusal (no approved Cinematography direction, no scene
        # look, an already-pending candidate, etc.) — never reached the seal at all.
        # Re-raise the ORIGINAL, specific reason rather than inventing a generic one.
        raise first_refusal
    return keyframe_shot(scene, shot_id, episode, spend_token=auth["token"], log=log)


def keyframe_shot(scene, shot_id, episode="Ep1", spend_token=None, dry_run=False, log=print):
    """GENERATE {shotId} OPENING KEYFRAME — ONE IMAGE, behind the SAME disclose-then-confirm
    seal fire_shot's video route has carried since 2026-07-16 (2026-07-22, Julian's direct
    "ensure the prompts I see in the studio are the exact prompts that go to the API"
    directive — this route had NO seal until this fix, see _keyframe_binding_hash's own
    docstring for the full forensic reasoning). The first call (no spend_token) resolves,
    discloses and REFUSES with a single-use token bound to the exact prompt + every
    reference file's content hash; the second call (with that token) re-verifies nothing
    drifted and fires the SEALED envelope's own prompt, never a fresh recompile. Generates
    exactly one keyframe CANDIDATE; touches no other shot's media or ledger entry, and never
    archives, replaces, regenerates or otherwise modifies the Scene Look Plate (2026-07-18
    correction). The shot's currently-approved keyframe, if any, is left completely
    untouched until this new candidate is itself approved."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_own_clip(pkg, shot_id)     # a member card is not its own clip
    _require_current_lineage(pkg, scene, episode)           # THE STATE-INTEGRITY CHECKPOINT
    # (2026-07-19 fix — confirmed via test_e2e_fire_route.py that this was defined and
    # extensively tested but had ZERO real call sites anywhere in this file; a package built
    # from a superseded storyboard could generate a real keyframe against outdated content,
    # the exact condition this checkpoint's own doctrine was written to prevent. Wired here
    # and into fire_shot below — the two real content-generation entry points.)
    _require_confirmed_billing("fal")                       # protection 5 — block, not warn
    _require_current_scenelook(scene, episode)                # no keyframe without a current approved Scene Look Plate
    shot = _shot(pkg, shot_id)
    if shot["sourceType"] != "opener":
        raise Refused(f"REFUSED — {shot_id} is a relay shot; it anchors on its source shot's "
                      f"harvested final frame, never its own keyframe")
    led = _ledger(pkg, shot_id)
    if led.get("keyframeCandidate"):
        raise Refused(f"REFUSED — {shot_id} already has a keyframe candidate awaiting a "
                      f"decision; reject it first (with a reason) before generating another")
    # THE CORE LAW's own hard gate (2026-07-19): raises DepartmentNotApproved unless a
    # CURRENT, human-approved Cinematography direction exists for this exact shot — checked
    # BEFORE any reference is resolved or any provider call is even considered.
    prompt = _resolve_keyframe_prompt(pkg, shot, scene, episode)
    # THE DRIFT-VOCABULARY BAN (2026-07-24) — same ship-point check as fire_shot's.
    _check_no_drift_vocab(prompt, refuse_prefix=f"REFUSED — {shot_id} keyframe")
    characters_cfg = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)

    working_kf = led.get("workingKeyframePrompt")
    binding, rate = _keyframe_binding_hash(pkg, shot, refs, prompt)
    envelope, env_hash = _keyframe_sealed_envelope(pkg, shot, refs, prompt, rate)
    log("SPEND DISCLOSURE — review before approving:")
    log(f"  shotId: {shot_id}")
    log(f"  costUsd: {rate}")
    log(f"  bindingHash: {binding}")
    log(f"  envelopeHash: {env_hash}")
    log(f"  provider: {cb_gen.IMAGE_PROVIDER}")
    log(f"  packageRevision: {pkg.get('revision')}")
    # DISCLOSURE PARITY WITH fire_shot (2026-07-22, Julian's full-audit directive): the same
    # "which prompt actually fired" transparency gap fire_shot's disclosure log was fixed for
    # tonight existed here too — a saved workingKeyframePrompt override silently shadows the
    # Cinematographer's approved output with zero visible trace before spending real money on
    # a Seedream call. Checked directly off the already-loaded ledger (no resolver signature
    # change needed — _resolve_keyframe_prompt has no is_working return, unlike its Seedance
    # sibling).
    if working_kf and working_kf.get("text"):
        log(f"  ⚠⚠⚠ USING A SAVED WORKING OVERRIDE (saved by {working_kf.get('savedBy','?')} "
            f"on {working_kf.get('savedAt','?')}) — this REPLACES the Cinematographer's "
            f"current approved output below.")
    log("  --- THE EXACT KEYFRAME PROMPT ABOUT TO BE SUBMITTED (not a hash — the real words) ---")
    for line in prompt.splitlines():
        log(f"  | {line}")
    log("  --- end of prompt text ---")

    if dry_run:
        log("SEALED PROVIDER-REQUEST ENVELOPE (dry run — no token issued, nothing stored):")
        log(json.dumps(envelope, indent=1, ensure_ascii=False))
        log(f"ENVELOPE SHA-256: {env_hash}")
        raise Refused("REFUSED — DRY RUN. No spend token was issued and no state changed.")

    auth = led.get("pendingKeyframeSpendAuth")
    if spend_token is None:
        led["pendingKeyframeSpendAuth"] = {"token": uuid.uuid4().hex, "bindingHash": binding,
                                             "envelope": envelope, "envelopeHash": env_hash,
                                             "issuedAt": _now()}
        _save(pkg, path)
        raise Refused("REFUSED — SPEND NOT APPROVED. A single-use spend token has been "
                      "issued, bound to the sealed envelope above; re-run with "
                      f"--spend-token {led['pendingKeyframeSpendAuth']['token']} "
                      "(Studio: 'Approve spend & generate').")
    if not auth or spend_token != auth["token"]:
        raise Refused("REFUSED — unknown or already-used spend token; request a new "
                      "disclosure")
    if auth["bindingHash"] != binding:
        raise Refused("REFUSED — the spend token is STALE: the package, references, "
                      "prompt or provider changed after the disclosure. Request a new "
                      "disclosure and approval.")
    # THE SEAL (§5): firing sends the DISCLOSED envelope verbatim — never a recompile.
    sealed = _verify_envelope(auth)
    led["pendingKeyframeSpendAuth"] = None                  # single-use: consumed NOW

    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / f"{episode}_{shot_id}_keyframe_candidate_{uuid.uuid4().hex[:8]}.png"
    cb_gen.generate_image(sealed["prompt"], refs=[r["path"] for r in sealed["references"]],
                           out=str(out), production_route="cb_render")
    # ONLY reached on a successful generation — led["keyframeCandidate"] (and any existing
    # keyframeApproval) is never touched before this line, so a failure above leaves the
    # ledger, and any approved keyframe, byte-for-byte as they were.
    led["keyframeCandidate"] = {"path": str(out), "generatedAt": _now(), "source": "generated",
                                 "inputSignature": _keyframe_input_signature(pkg, shot, scene, episode)}
    # THE DURABLE "WHAT WAS ACTUALLY SUBMITTED" RECORD (2026-07-22, Julian's directive): a
    # live preview panel can only ever show the CURRENT prompt — it cannot prove what a
    # PAST generation actually used, and the auto-continue flow means a human may never
    # read the disclosure log line by line. This persists the exact sealed envelope onto
    # the ledger, keyed to the candidate it produced, so the Studio can show a durable
    # "exact prompt submitted, fired at TIMESTAMP" record for this specific candidate,
    # forever checkable, never a forward-looking preview.
    led["lastKeyframeEnvelope"] = {"candidatePath": str(out), "envelope": sealed,
                                     "envelopeHash": env_hash, "firedAt": _now()}
    _save(pkg, path)
    log(f"KEYFRAME — {shot_id} -> {out.name} (awaiting approval — the current approved "
        f"keyframe, if any, is unchanged) — approve-keyframe or reject-keyframe")
    return str(out)


# ── THE OPENING-FRAME SOURCE CHOICE (Julian's directive, 2026-07-18) ────────────────────
# An opening frame's source is the human's own deliberate choice, never only "generate":
#   1. generate     — a real paid render (keyframe_shot above, unchanged)
#   2. upload       — a file the human supplies, no generation cost
#   3. library      — a prior artefact for THIS shot (a past candidate, rejected take,
#                      superseded approval, or a currently-pending one) the human
#                      deliberately re-selects, no generation cost, never automatic
#   4. previousFinalFrame — the previous shot's own approved+harvested final frame, carried
#                      forward as a fresh candidate for THIS shot (only when this shot is
#                      NOT a scene opener) — no generation cost
# Every one of 2-4 NEVER calls a generation provider; each only ever COPIES an existing file
# into a new, immutable, shot-owned candidate path. The result always lands as
# keyframeCandidate, awaiting the exact same approve/"choose another" decision as a
# generated one — selection is never approval.
def _immutable_candidate_copy(src_path, shot_id, episode):
    """Copies src_path into a NEW, uniquely-named candidate file under MEDIA. The file at
    src_path is never modified, moved or deleted by this call."""
    ext = pathlib.Path(src_path).suffix or ".png"
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / f"{episode}_{shot_id}_keyframe_candidate_{uuid.uuid4().hex[:8]}{ext}"
    shutil.copy2(src_path, out)
    return str(out)


def keyframe_library_for_shot(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost: every prior opening-frame artefact for THIS shot the human may
    deliberately choose to reuse — the currently-pending candidate (if any, so it never
    silently vanishes once a fresh source-choice screen is opened), the currently-approved
    keyframe (if any, so re-confirming it is a real, listed choice too), every rejected
    candidate, and every superseded (once-approved, later replaced) approval. Each item is
    checked for its own file's existence — an archived record whose file was separately
    removed is silently omitted, never offered as a dead link. Never auto-selects or
    mutates anything; this only lists."""
    pkg, _ = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    items = []

    def _add(path, at, outcome, note=None):
        if path and os.path.exists(path):
            items.append({"path": path, "at": at, "outcome": outcome, "note": note})

    cand = led.get("keyframeCandidate")
    if cand:
        _add(cand.get("path"), cand.get("generatedAt"), "pending", cand.get("source"))
    appr = led.get("keyframeApproval")
    if appr:
        _add(appr.get("path"), appr.get("at"), "approved", None)
    for r in (led.get("keyframeRejections") or []):
        _add(r.get("rejectedFile"), r.get("rejectedAt"), "rejected", r.get("reason"))
    for h in (led.get("keyframeHistory") or []):
        _add(h.get("archivedFile"), h.get("supersededAt"), "superseded", None)
    items.sort(key=lambda x: x.get("at") or "", reverse=True)
    return items


def select_keyframe_source(scene, shot_id, mode, episode="Ep1", upload_path=None,
                             library_path=None, reviewed_by="Julian", log=print):
    """THE NON-GENERATION OPENING-FRAME CHOICES: 'upload' (a human-supplied file, preserved
    unchanged at its own permanent path AND copied to an immutable shot-owned candidate),
    'library' (a copy of one of this shot's own prior artefacts, per keyframe_library_for_shot
    above — the source file there is itself already immutable archive/media, never touched),
    and 'previousFinalFrame' (only for a non-opener shot — a copy of the shot it relays off,
    once THAT shot is itself approved+harvested). NEVER calls cb_gen. Refuses if a candidate
    is already pending (matching keyframe_shot's own rule — reject it first)."""
    if mode not in ("upload", "library", "previousFinalFrame"):
        raise Refused(f"REFUSED — unknown opening-frame source {mode!r}; must be "
                      f"upload, library or previousFinalFrame")
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    _require_current_scenelook(scene, episode)   # world anchor law applies to every source
    if led.get("keyframeCandidate"):
        raise Refused(f"REFUSED — {shot_id} already has a keyframe candidate awaiting a "
                      f"decision; choose another (reject it, with a reason) first")

    if mode == "upload":
        if not upload_path or not os.path.exists(upload_path):
            raise Refused("REFUSED — no uploaded file found to select")
        # PRESERVE THE ORIGINAL ASSET — a permanent copy, distinct from and never touched by
        # the shot's own immutable production candidate copy made below.
        preserved_dir = HERE / "media" / "uploads"
        preserved_dir.mkdir(parents=True, exist_ok=True)
        ext = pathlib.Path(upload_path).suffix or ".png"
        preserved = preserved_dir / f"{episode}_{shot_id}_upload_{uuid.uuid4().hex[:8]}{ext}"
        shutil.copy2(upload_path, preserved)
        cand_path = _immutable_candidate_copy(str(preserved), shot_id, episode)
        source_note = {"source": "uploaded", "preservedOriginal": str(preserved)}
    elif mode == "library":
        if not library_path or not os.path.exists(library_path):
            raise Refused("REFUSED — the selected library item no longer exists on disk")
        cand_path = _immutable_candidate_copy(library_path, shot_id, episode)
        source_note = {"source": "library", "libraryOriginal": library_path}
    else:  # previousFinalFrame
        if shot["sourceType"] == "opener":
            raise Refused(f"REFUSED — {shot_id} is a scene opener; there is no previous "
                          f"shot's final frame to use. This choice only applies to a "
                          f"continuous (relay) shot.")
        src = _ledger(pkg, shot["sourceShotId"])
        if src.get("status") != "approved" or not src.get("harvestFrame"):
            raise Refused(f"REFUSED — {shot['sourceShotId']} is not approved+harvested yet; "
                          f"there is no final frame to carry forward")
        cand_path = _immutable_candidate_copy(src["harvestFrame"], shot_id, episode)
        source_note = {"source": "previousFinalFrame", "sourceShotId": shot["sourceShotId"]}

    led["keyframeCandidate"] = {"path": cand_path, "generatedAt": _now(), **source_note}
    _save(pkg, path)
    log(f"OPENING FRAME SELECTED — {shot_id}: {source_note['source']} -> "
        f"{os.path.basename(cand_path)} (awaiting approval — the current approved keyframe, "
        f"if any, is unchanged) — approve-keyframe or reject-keyframe")
    return cand_path


def approve_keyframe(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
    """Promotes the pending candidate to approved. A GENERATED candidate's validity is
    checked against the shot's OWN direct inputs at approval time (its own card hash, the
    approved Scene Look hash, its own reference hashes, the compiled brief, model/settings)
    — never the whole storyboard or package revision. A candidate chosen via one of the
    2026-07-18 non-generation sources (uploaded, from this shot's own library/history, or
    carried from the previous shot's final frame — select_keyframe_source above) has no
    compiled-brief inputs to drift from; it is approved on the strength of the human's own
    deliberate choice, tagged plainly by its 'source' field rather than input-signature-
    checked. Only NOW is a previously-approved keyframe archived (moved, never deleted,
    never overwritten in place); nothing is ever renamed into a shared path."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    cand = led.get("keyframeCandidate")
    if not cand:
        raise Refused(f"REFUSED — {shot_id} has no keyframe candidate awaiting approval")
    if cand.get("source", "generated") == "generated":
        current_sig = _keyframe_input_signature(pkg, shot, scene, episode)
        if cand.get("inputSignature") != current_sig:
            diff = _signature_diff(cand.get("inputSignature"), current_sig)
            raise Refused(f"REFUSED — {shot_id}'s direct input(s) changed since this candidate "
                          f"was generated ({', '.join(diff)}); a candidate can never be approved "
                          f"against inputs it wasn't actually generated from. Regenerate against "
                          f"the current inputs.")
    old = led.get("keyframeApproval")
    if old and old.get("path") and os.path.exists(old["path"]):
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "shots_superseded" / f"{episode}_{shot_id}_{ts}"
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / os.path.basename(old["path"])
        shutil.move(old["path"], dest)
        led.setdefault("keyframeHistory", []).append({**old, "outcome": "superseded",
                                                        "supersededAt": _now(),
                                                        "archivedFile": str(dest.relative_to(HERE))})
    led["keyframeApproval"] = {"approved": True, "path": cand["path"], "at": _now(),
                                "reviewedBy": reviewed_by, "source": cand.get("source", "generated"),
                                "inputSignature": cand.get("inputSignature")}
    led["keyframePath"] = cand["path"]    # back-compat pointer for any legacy reader (evidence_pack etc.)
    led["keyframeCandidate"] = None
    _save(pkg, path)
    log(f"KEYFRAME APPROVED — {shot_id} by {reviewed_by}")
    return cand["path"]


def unapprove_keyframe(scene, shot_id, episode="Ep1", note="", reviewed_by="Julian", log=print):
    """UNDO A KEYFRAME APPROVAL (2026-07-25, Julian: "i need to be able to unapprove each
    section") — the approved frame moves BACK to being the pending CANDIDATE (awaiting a
    fresh decision: re-approve, reject with a note, or replace). Nothing is deleted or
    archived by this call; the same reversible-action semantics as unapprove_scenelook/
    unapprove_department."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    appr = led.get("keyframeApproval")
    if not appr or not appr.get("approved"):
        raise Refused(f"REFUSED — {shot_id} has no keyframe approval to undo")
    if led.get("keyframeCandidate"):
        raise Refused(f"REFUSED — {shot_id} already has a keyframe candidate awaiting a "
                      f"decision; decide that first, then un-approve if still needed")
    led.setdefault("keyframeHistory", []).append({**appr, "outcome": "unapproved",
                                                    "unapprovedAt": _now(),
                                                    "reviewedBy": reviewed_by,
                                                    "unapprovedNote": (note or "").strip() or None})
    led["keyframeCandidate"] = {"path": appr["path"], "source": appr.get("source", "generated"),
                                 "inputSignature": appr.get("inputSignature"),
                                 "generatedAt": appr.get("at")}
    led["keyframeApproval"] = None
    led["keyframePath"] = None
    _save(pkg, path)
    log(f"KEYFRAME UN-APPROVED — {shot_id} by {reviewed_by}; the frame is back to AWAITING "
        f"your decision (re-approve, reject, or regenerate); nothing was deleted")
    return True


def reject_keyframe(scene, shot_id, correction, episode="Ep1", reviewed_by="Julian", log=print):
    """Rejection ARCHIVES the CANDIDATE only (moved, never copied) — never a previously-
    approved keyframe, which stays live, approved and current exactly as it was. The next
    keyframe_shot() call is then unblocked."""
    if not (correction or "").strip():
        raise Refused("REFUSED — a keyframe rejection requires a plain-language reason")
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    cand = led.get("keyframeCandidate")
    if not cand:
        raise Refused(f"REFUSED — {shot_id} has no keyframe candidate to reject")
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_keyframe_{ts}"
    arch.mkdir(parents=True, exist_ok=True)
    archived_rel = None
    src = cand.get("path")
    if src and os.path.exists(src):
        dest = arch / os.path.basename(src)
        shutil.move(src, dest)                      # MOVED, not copied — the candidate's own path is cleared
        archived_rel = str(dest.relative_to(HERE))
    rejection = {**cand, "outcome": "rejected", "rejectedAt": _now(),
                 "reason": correction.strip(), "reviewedBy": reviewed_by,
                 "rejectedFile": archived_rel}
    led.setdefault("keyframeRejections", []).append(rejection)
    led["keyframeRejected"] = rejection
    led["keyframeCandidate"] = None        # cleared from the current position
    _save(pkg, path)
    log(f"KEYFRAME REJECTED — {shot_id}: {correction}\n  archived -> "
        f"{archived_rel or '(no file was present)'}\n  the previously-approved keyframe, if "
        f"any, is unaffected")
    return archived_rel


# ── Gate 7 — THE CANDIDATE GENERATOR (Julian's probabilistic-model correction,
# 2026-07-16): Seedance is a probabilistic generator, not a deterministic renderer. One
# approved shot contract produces a CONTROLLED CANDIDATE SET (default 3, range 1-4) behind
# an explicit spend disclosure + human approval. Upstream planning and validation control
# the INPUTS; they never guarantee the performance — the product is an approved shot chosen
# from candidates, not a "perfect prompt".
DEFAULT_CANDIDATES = 3
MAX_CANDIDATES = 4
# THE ITERATION BUDGET (Julian's ruling, 2026-07-25 — "I just want it to be locked down,
# I don't care about cost"). Raised from 2 after benchmarking the AnyFilm pipeline's own
# honest numbers: 2-3 generations per approved clip as BASELINE, 5-7 for complex physics
# (underwater, storms, multi-character coordination), ~108 video generations for a
# 44-clip episode. Our previous ceiling of 2 was stricter than the practice we were
# measuring ourselves against — it was calibrated for cost control at a moment when a
# fire was expensive and learning was cheap. That trade is now reversed: learning is the
# bottleneck. 7 still ends the loop; it is not an endless patch loop, just an honest one.
MAX_BATCH_ATTEMPTS = 7

# THE FIX LADDER (same ruling, from AnyFilm's own measured distribution of what actually
# fixes a rejected clip):
#     30%  re-roll the IDENTICAL prompt      — ~60% success; generation variance alone
#     45%  edit ONE element                  — a named continuity/eyeline/lighting fix
#     20%  rewrite the clip                  — structural: blocking, pacing, tone
#      5%  split the clip                    — too many story beats in one generation
# The first tier is the one we never had. Treating every failure as a diagnosis problem
# means roughly a third of our re-fires were solving nothing — the same prompt would have
# landed on the next roll. `reject_shot(category=...)` records which tier was used so the
# corpus can tell us whether that 30/45/20/5 split holds for THIS show.
FIX_TIERS = ("reroll_identical", "edit_one_element", "rewrite_clip", "split_clip")

# THE HANDLE DOCTRINE, RESTORED AT SHOT LEVEL (2026-07-19, Julian: "we want 15 second clips
# with 2 seconds at the end to have for editing"). The old beat-level pipeline (archived,
# rule 20 of the studio's own CLAUDE.md) always rendered at a fixed HANDLE_TOTAL=15s split
# 13s action + 2s settle; the cutover to shots (2026-07-16/17) replaced that with a per-shot
# 4-8s design-time estimate (cb_engine.MIN_SHOT_SEC/MAX_SHOT_SEC) and never re-derived it
# against the REAL recorded voice take before firing a paid render (the S1.SH1 bug: a
# 9.68s real V3 take fired against a 7.0s-designed clip, no crash, dialogue simply cut off).
# fire_shot below is the one place that matters: it overrides the design-time durationSec
# with max(HANDLE_TOTAL, real_audio_duration + HANDLE_SETTLE) before any downstream read
# (binding hash, sealed envelope, disclosure, the actual provider call) ever sees it.
HANDLE_TOTAL = 15.0
HANDLE_SETTLE = 2.0


def _handle_duration(vo_path, shot_duration=None):
    """The actual fire duration for a shot: at least the shot's OWN authored duration, and
    always at least HANDLE_SETTLE (2s) of editing room past the real recorded voice track's
    length, whichever is longer.

    THE 15s FLOOR RETIRED AS A DEFAULT (Julian's split-generation directive, 2026-07-23 —
    "Do not default either generation to 15 seconds. Propose the shortest natural duration
    for each."): the old unconditional HANDLE_TOTAL floor forced every shot to 15s
    regardless of its authored durationSec — real waste on a 7s crash gag ($4.55 vs $2.12)
    and, worse, 8 extra seconds the model must fill with invented content. shot_duration
    is the shot's own durationSec; when provided it IS the floor. When None (older callers
    that don't know the shot), the previous HANDLE_TOTAL behaviour is preserved exactly."""
    real = _audio_dur(vo_path) if vo_path else 0.0
    floor = float(shot_duration) if shot_duration else float(HANDLE_TOTAL)
    # THE DURATION-MATCHED MASTER (2026-07-24, found retiming S1.SH3 to 7s: a padded
    # @Audio1 master built to exactly the shot's own durationSec ALREADY CONTAINS its
    # leading silence and settle tail — adding HANDLE_SETTLE on top of it produced a video
    # 2s longer than its own audio, an undefined tail the provider fills however it likes.
    # SH2's 15s master only escaped this because the 15s provider cap happened to clamp
    # the +2 back down). A master within 0.15s of the floor IS the fire duration, exactly.
    if real and abs(real - floor) <= 0.15:
        return round(min(floor, float(cb_engine.MAX_SHOT_SEC)), 1)
    # THE PROVIDER CAP (2026-07-23, found live: a 15.0s padded @Audio1 master + the 2s
    # settle produced duration=17, which BytePlus/Seedance rejected outright with a 400 at
    # task creation — the model's own hard ceiling is 15s, the same bound cb_engine.
    # MAX_SHOT_SEC already encodes for authored durations). A duration-matched audio master
    # already CONTAINS its own settle tail, so clamping never cuts real content.
    return round(min(max(floor, real + HANDLE_SETTLE), float(cb_engine.MAX_SHOT_SEC)), 1)

# the per-candidate evaluation sheet (§6 of the correction) — HUMAN review criteria; the
# machine fills mechanical notes only and never auto-approves creative quality
REVIEW_CRITERIA = ["characterIdentity", "relativeScale", "startingGeography",
                    "actionReadability", "physicalCauseAndEffect",
                    "comicOrEmotionalPerformance", "cameraBehaviour",
                    "dialogueAndMouthPerformance", "continuity", "finalFrameUsability"]

# 2026-07-19: THREE-WAY duplication, not two — confirmed by audit. Keep in sync with
# cb-studio/app.html's REJECT_CATS AND cb-studio/serve.py's REJECT_CATEGORIES, both of
# which only cross-referenced each other before this — this copy, under a different name,
# was never accounted for by either comment.
# "variance" added 2026-07-25: the take is not WRONG, the roll was unlucky (timing a
# beat early, an expression a shade off, placement inside tolerance but not ideal). It
# routes to the reroll_identical fix tier — the same prompt again, which lands ~60% of
# the time. Every other category names a real defect that needs a real change.
FAILURE_CATEGORIES = ["variance", "identity", "geography", "action-timing",
                      "instruction-ignored", "other"]

DECISION_LADDER = """THE FAILURE DECISION LADDER (after reviewing a candidate set):
  1. One candidate succeeds            -> approve it (approve <scene> <shotId> <N>)
  2. Failures vary randomly            -> ONE controlled reroll, UNCHANGED package
  3. Identity/opening geography fails consistently -> correct the keyframe or references
  4. Action/physical timing fails consistently     -> simplify or divide the shot (redesign)
  5. Model repeatedly ignores an instruction       -> remove conflicts, shorten the prompt
  6. Two failed batches                -> STOP: shot is model-limited; human redesign or an
                                          alternative production method. No prompt-patching."""


def _anchor_for(pkg, shot):
    led = _ledger(pkg, shot["shotId"])
    if shot["sourceType"] == "opener":
        # A GENERATED-BUT-UNAPPROVED CANDIDATE CAN NEVER ANCHOR A FIRE (2026-07-17 state-
        # integrity checkpoint, corrected 2026-07-18 — direct-input lineage): file existence
        # alone used to be enough here — the exact class of bug that let a rejected S1.SH1
        # keyframe read as "approved" and unlock Voice. An explicit keyframeApproval is the
        # only valid anchor. This no longer also requires the approval's packageRevision to
        # match the CURRENT package revision — that tie was itself the blanket-invalidation
        # bug this correction closes (an unrelated shot's edit bumps the package revision
        # without touching this shot's own approved keyframe at all). The keyframe's own
        # direct-input validity is enforced once, at approve_keyframe time; an approval that
        # already passed that check stays a valid anchor regardless of what else in the
        # package changes later — package revision is provenance evidence, never a gate.
        appr = led.get("keyframeApproval")
        kf = appr and appr.get("path")
        if not appr or not kf or not os.path.exists(kf):
            raise Refused(f"REFUSED — {shot['shotId']} has no APPROVED keyframe (a generated-"
                          f"but-unapproved candidate is never a valid anchor) — "
                          f"cb_render.py keyframe {shot['beatCode'].split('.')[0]} "
                          f"{shot['shotId']}, then approve-keyframe once it's reviewed")
        return kf
    src = _ledger(pkg, shot["sourceShotId"])
    if src.get("status") != "approved" or not src.get("harvestFrame"):
        raise Refused(f"REFUSED — {shot['shotId']} relays off {shot['sourceShotId']}, which is "
                      f"not approved+harvested yet (status: {src.get('status')}) — "
                      f"Julian's eye comes first, always")
    return src["harvestFrame"]


def _require_confirmed_billing(provider):
    """PROTECTION 5 (Julian, 2026-07-16): an unconfirmed billing profile HARD-BLOCKS paid
    generation — a refusal, never a warning. One-line confirmation in billing_profile.json
    (planConfirmed + cadenceConfirmed) unblocks the provider."""
    import cb_costs
    prof = cb_costs.load_billing_profile(provider)
    if not prof or not (prof.get("planConfirmed") and prof.get("cadenceConfirmed")):
        raise Refused(f"REFUSED — billing profile for '{provider}' is UNCONFIRMED "
                      f"(engine/billing_profile.json: planConfirmed/cadenceConfirmed). Paid "
                      f"generation is hard-blocked until Julian confirms the plan and cadence.")


def _file_md5(path):
    try:
        return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()
    except Exception:
        return "missing"


def _shots_hash(pkg):
    """The exact package hash (protection 1/4): every shot's full authored+compiled content."""
    return hashlib.sha256(json.dumps(pkg["shots"], sort_keys=True,
                                      ensure_ascii=False).encode()).hexdigest()[:16]


def _video_provider_rate_key(fast, resolution="720p"):
    """THE PROVIDER-AWARE COST KEY (2026-07-22, alongside the BytePlus ModelArk switch): the disclosure
    envelope must reflect cb_gen.VIDEO_PROVIDER at the moment of disclosure — hardcoding "fal" here would
    have shown Julian a false provider/rate the instant the default flipped to byteplus, breaking THE CORE
    LAW (nothing fires without an honest disclosure of what will actually happen). BytePlus's own price is
    still unconfirmed (see cb_costs.RATES's own comment on seedance_byteplus_ark_per_sec) so it uses one
    flat rate regardless of fast/standard tier, unlike fal's own split rate.
    2026-07-23 (Julian: "lets run the tests at the lesser amount"): 480p test-iteration tier gets its own
    area-proportional rate key on the byteplus route; fal's rate table has no 480p entry, so a non-720p
    resolution on that route keeps the 720p rate (an over-estimate — never an under-disclosure)."""
    if cb_gen.VIDEO_PROVIDER == "byteplus":
        return ("seedance_byteplus_ark_480p_per_sec" if str(resolution) == "480p"
                else "seedance_byteplus_ark_per_sec")
    return "seedance_fast_per_sec" if fast else "seedance_standard_per_sec"


def _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast, resolution="720p"):
    """Everything the spend approval is bound to (protection 1): the exact package hash,
    provider, model/tier, candidate count, cost rate, max batch cost — plus the CONTENT
    hashes of the anchor, every reference file and the audio, the slot order, duration and
    settings. Any change between disclosure and generation produces a different hash and
    invalidates the token."""
    import cb_costs
    key = _video_provider_rate_key(fast, resolution)
    rate, _, _ = cb_costs.RATES[key]
    per = round(cb_costs.estimate_video_cost(key, int(round(shot["durationSec"]))), 4)
    payload = {"packageHash": _shots_hash(pkg),
               "shotId": shot["shotId"],
               "provider": cb_gen.VIDEO_PROVIDER,
               "model": f"seedance-ref2vid-{'fast' if fast else 'standard'}",
               "resolution": str(resolution),
               "candidates": candidates, "ratePerSecUsd": rate,
               "maxBatchCostUsd": round(per * candidates, 4),
               "prompt": shot["seedancePrompt"],
               "slotOrder": shot["referenceSlots"],
               "anchorMd5": _file_md5(anchor),
               "refMd5s": [_file_md5(p) for p in imgs],
               "audioMd5": _file_md5(led["voPath"]) if led.get("voPath") else None,
               "durationSec": shot["durationSec"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32], per


_DROP_MSG_RE = re.compile(r'^locked line not assigned to any shot — (.+?): "(.*)"$')


def _demote_pending_beat_line_drops(report, beats, pkg, episode):
    """THE SEQUENTIAL-PRODUCTION CORRECTION (2026-07-20, Julian — "This is why we have
    scenes and shots. Shot 1 has to be shot one then we move shot 2 etc, not all at
    once."): validate_scene_design's DIALOGUE_LINE_DROPPED check was built for a
    whole-scene, all-shots-designed-at-once validation — it treats the SCENE's full
    beat set as the expected universe but only sees whatever's CURRENTLY PROMOTED into
    this package. That's correct at design time (cb_engine.design_scene really does
    produce every shot for a scene in one pass) but a false alarm for this pipeline's
    real, deliberate one-shot-at-a-time promotion model: firing an already-complete
    shot must never be blocked just because a SIBLING shot for the same beat — or a
    later beat's shots entirely — hasn't been promoted yet.

    A line is only a genuine drop if no shot, promoted or still sitting in the
    storyboard as a draft, will ever claim it. A beat counts as PENDING (non-blocking)
    unless every one of its own storyboard shots is already promoted into this
    package — that covers both "some of this beat's shots exist but aren't promoted"
    (S1.SH2/SH3 today) and "this beat has no shots designed at all yet" (a later
    beat nobody has touched). Only a beat that's fully promoted yet still missing a
    line is a real, code-level authoring bug worth hard-blocking on."""
    import cb_engine as E
    drops = [i for i in report["issues"] if i["code"] == "DIALOGUE_LINE_DROPPED"]
    if not drops:
        return report
    sb_path = _storyboard_path(pkg["sceneNumber"], episode)
    if not sb_path.exists():
        return report
    sb_shots = json.load(open(sb_path)).get("shots") or []
    promoted_ids = {s.get("shotId") for s in pkg["shots"]}
    beat_shot_ids = {}
    for s in sb_shots:
        for bid in (s.get("beatIds") or []):
            beat_shot_ids.setdefault(bid, []).append(s.get("shotId"))
    complete_beats = {bid for bid, sids in beat_shot_ids.items()
                       if sids and all(sid in promoted_ids for sid in sids)}
    chars_cfg = _characters_cfg()
    pending_lines = set()
    for b in beats:
        if b.get("beatCode") in complete_beats:
            continue
        for c in (b.get("cuts") or []):
            dlg = (c.get("dialogue") or "").strip()
            if dlg and ":" in dlg:
                spk, txt = dlg.split(":", 1)
                if txt.strip():
                    pending_lines.add((E._norm(E._canon_speaker(spk.strip(), chars_cfg)),
                                        E._norm(txt.strip().strip('"“”').strip())))
    if not pending_lines:
        return report
    kept, demoted = [], []
    for i in report["issues"]:
        if i["code"] != "DIALOGUE_LINE_DROPPED":
            kept.append(i)
            continue
        m = _DROP_MSG_RE.match(i["message"])
        key = ((E._norm(E._canon_speaker(m.group(1), chars_cfg)), E._norm(m.group(2)))
               if m else None)
        if key and key in pending_lines:
            demoted.append({**i, "severity": "WARNING",
                            "message": i["message"] + " — PENDING, not dropped: this "
                            "beat's shots are not all promoted into the package yet "
                            "(sequential one-shot-at-a-time production)."})
        else:
            kept.append(i)
    if not demoted:
        return report
    issues = kept + demoted
    return {**report, "issues": issues,
            "passed": not any(x["severity"] == "ERROR" for x in issues)}


def _beats_for_fresh_validation(pkg, episode):
    """Reads the beats this package's own validation must check against, from the ONE real
    source of truth — the storyboard that actually produced it — never a same-named-episode
    file discovered by an unrelated glob. Resolved via _storyboard_path(pkg["sceneNumber"],
    episode) first (the SAME resolution _demote_pending_beat_line_drops already uses, right
    below, and the one existing tests already know how to monkeypatch), falling back to
    pkg["sourceStoryboard"]["path"] (the package's own recorded provenance — the only
    source available to a hand-constructed test package that never went through the real
    per-scene file convention).

    THE WRONG-PIPELINE-STAGE FIX (2026-07-22, found live in the Studio — Julian: "I can't
    fire because I've just got this... REFUSED... MISSING_PHYSICAL_STAGING at beat
    S01-B01-POLLEN-CHAOS."): _fresh_validation used to build its beats via
    cb_engine._load_pkg(episode) + _scene_beats() — a glob against
    cb-output/{episode}_*beat_package.json. CORRECTED 2026-07-22 (this comment originally,
    and wrongly, called that file "a stale orphaned leftover from the retired 43-beat
    pipeline" — it is not: Ep1_The_Adventure_Begins_beat_package.json is the CURRENT,
    live, actively-maintained script→beat breakdown that cb_creative._script_package()
    reads as Gate 0's own script input, and that cb_engine.design_scene()/repair_package()
    still read today to author any scene that hasn't yet been promoted into its own
    per-scene storyboard — confirmed still edited this week (its own pre-comedyMode
    archive copy is dated the same day this bug was found). The real bug was a
    pipeline-STAGE mismatch, not a dead file: this whole-episode beat package is the
    EARLY, story-beat-level breakdown (one entry per story beat, e.g.
    "S01-B01-POLLEN-CHAOS" with comedyMode=BIG, genuinely authored, not a fossil);
    _fresh_validation needs the LATER, shot-level breakdown for the specific scene being
    fired — the storyboard produced once that scene's beats are actually directed into
    shots (Scene 1's own Ep1_scene1_storyboard.json). Reading the early-stage file's
    story-beat comedyMode as if it were this scene's shot-level authoring wrongly applied
    a check meant for a directed shot to an undirected story beat that merely happens to
    share an ID convention with it. The block Julian hit was real (the check genuinely
    fired) but computed from the wrong pipeline stage — the confirmed cause of "I can't
    fire because of a check on something that isn't even mine."

    Fixed to read the real storyboard's own beats and reshape them into exactly the two
    shapes validate_scene_design/_demote_pending_beat_line_drops actually read:
    beatCode (from the storyboard's own beatId), comedyMode (as genuinely authored — None
    on every real Scene 1 beat today, so MISSING_PHYSICAL_STAGING correctly never fires
    until a beat is actually marked BIG), and cuts[].dialogue (from the storyboard's own
    exactDialogue, already "Speaker: text" — the same shape _expected_lines() reads)."""
    sb_path = _storyboard_path(pkg["sceneNumber"], episode)
    if not sb_path.exists():
        alt = (pkg.get("sourceStoryboard") or {}).get("path")
        sb_path = pathlib.Path(alt) if alt else None
        if not sb_path or not sb_path.exists():
            return []
    sb = json.load(open(sb_path))
    return [{"beatCode": b.get("beatId"), "comedyMode": b.get("comedyMode"),
             "cuts": [{"dialogue": d} for d in (b.get("exactDialogue") or [])]}
            for b in (sb.get("beats") or [])]


def _fresh_validation(pkg, episode):
    """PROTECTION 4: validation is re-run against the CURRENT package content at every
    disclosure — a hand-edited or revised package can never fire on a stale green stamp.
    Zero-LLM (cb_engine's deterministic validator, imported, never modified).

    A scene-wide DIALOGUE_LINE_DROPPED for a beat whose sibling shots simply haven't
    been promoted yet is demoted to an advisory WARNING — see
    _demote_pending_beat_line_drops. Every other check (drop on a FULLY promoted beat,
    duplicate, not-verbatim, speaker/timing/continuity integrity) stays a full,
    unweakened hard block, exactly as before."""
    import cb_engine as E
    beats = _beats_for_fresh_validation(pkg, episode)
    fields = set(E.Shot.model_fields)
    shots = [E.Shot(**{k: v for k, v in rec.items() if k in fields}) for rec in pkg["shots"]]
    design = E.SceneShotList(statement=E.DirectorStatement(**pkg.get("directorStatement", {
        k: "n/a" for k in ("audienceFeeling", "whoseScene", "emotionalChange", "theLaugh",
                            "visualSurprise", "carryForward")})), shots=shots)
    report = E.validate_scene_design(design, beats, _characters_cfg())
    report = _demote_pending_beat_line_drops(report, beats, pkg, episode)
    if not report["passed"]:
        errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
        raise Refused(f"REFUSED — fresh validation of the CURRENT package failed with "
                      f"{len(errs)} error(s) (first: {errs[0]['code']} at {errs[0]['path']}). "
                      f"A revised package requires fresh validation before any spend.")
    return report


def _prompt_version(shot):
    import hashlib
    return hashlib.md5(shot["seedancePrompt"].encode()).hexdigest()[:8]


def _sealed_envelope(pkg, shot, led, imgs, anchor, candidates, fast, per, resolution="720p"):
    """THE IMMUTABLE PROVIDER-REQUEST ENVELOPE (Julian's cutover order, 2026-07-16, §5):
    everything the provider will receive, sealed AT DISCLOSURE — exact prompt, duration, model,
    resolution, candidate count, reference order with per-file hashes, audio hash, max cost.
    The spend token binds to this envelope's hash; firing sends THIS, never a recompile.

    FIXED 2026-07-22 (found writing keyframe_shot's own mirror of this seal): img_slots used
    to be built by plain dict iteration, relying on shot["referenceSlots"]'s own insertion
    order already matching @图1/@图2/... numeric order — true in practice (nothing ever
    reorders these dicts after the Director writes them) but never actually GUARANTEED, and
    _slot_paths (the function that produced `imgs`, this function's own zip partner) has
    always sorted explicitly. A silently-reordered dict would zip a reference's role/slot
    label to the WRONG file's md5 in the sealed envelope — the seal would still be internally
    self-consistent (nothing else re-derives this order to catch the mismatch) but would
    misrepresent which file backs which slot. Sorted explicitly now, matching _slot_paths's
    own contract exactly rather than an unenforced assumption."""
    img_slots = sorted((t for t in shot["referenceSlots"] if t.startswith("@图")),
                       key=lambda t: int(t[2:]))
    refs = [{"slot": t, "role": shot["referenceSlots"][t], "path": p, "md5": _file_md5(p)}
            for t, p in zip(img_slots, imgs)]
    # provider/model/endpoint reflect cb_gen.VIDEO_PROVIDER at disclosure time (2026-07-22) — the
    # underlying model is the same Seedance 2.0 either way, only the host + its own endpoint/model-id
    # naming differ; see _video_provider_rate_key's own comment for why this must never be hardcoded.
    if cb_gen.VIDEO_PROVIDER == "byteplus":
        _model = "dreamina-seedance-2-0-fast-260128" if fast else "dreamina-seedance-2-0-260128"
        _endpoint = cb_gen.BYTEPLUS_ARK_TASKS_URL
    else:
        _model = "bytedance/seedance-2.0"
        _endpoint = ("bytedance/seedance-2.0/fast/reference-to-video" if fast
                     else "bytedance/seedance-2.0/reference-to-video")
    env = {"shotId": shot["shotId"], "prompt": shot["seedancePrompt"],
           "durationSec": shot["durationSec"], "provider": cb_gen.VIDEO_PROVIDER,
           "model": _model,
           "endpoint": _endpoint,
           "resolution": str(resolution), "tier": "fast" if fast else "standard",
           "candidateCount": candidates, "costPerCandidateUsd": per,
           "maxBatchCostUsd": round(per * candidates, 4),
           "packageRevision": pkg.get("revision"),
           "promptVersion": _prompt_version(shot), "references": refs,
           "audio": {"path": led.get("voPath"),
                      "md5": _file_md5(led["voPath"]) if led.get("voPath") else None}}
    import hashlib
    h = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return env, h


def _verify_envelope(auth):
    """The fire-time seal check: the stored envelope re-hashes to the bound hash and every
    referenced file is byte-identical to what was disclosed. Returns the envelope."""
    import hashlib
    env = auth.get("envelope")
    if not env:
        raise Refused("REFUSED — the presented token predates the sealed-envelope protocol "
                      "and is VOID; request a new disclosure.")
    h = hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if h != auth.get("envelopeHash"):
        raise Refused("REFUSED — sealed-envelope integrity check failed; request a new "
                      "disclosure.")
    for r in env["references"]:
        if _file_md5(r["path"]) != r["md5"]:
            raise Refused(f"REFUSED — {r['slot']} ({r['role']}) changed on disk after the "
                          f"disclosure; the token is STALE. Request a new disclosure.")
    if env["audio"]["path"] and _file_md5(env["audio"]["path"]) != env["audio"]["md5"]:
        raise Refused("REFUSED — the audio asset changed after the disclosure; the token is "
                      "STALE. Request a new disclosure.")
    return env


# ── THE ANIMATION WORKING PROMPT (Julian's directive, 2026-07-19) ───────────────────────
# A contained creative control INSIDE the existing Animation stage. shot["seedancePrompt"] is
# already, honestly, "the complete Seedance prompt exactly as it will be submitted" — this
# lets Julian edit that SAME string (action, timing, physical comedy, camera, performance
# direction all live inside it as compiled prose) and save the edit as a shot-level working
# version, never touching the approved storyboard's own compiled seedancePrompt field.
# Reading/saving/restoring never calls cb_gen; only fire_shot's own real generation spends.
def _resolve_seedance_prompt(pkg, shot, scene, episode="Ep1", allow_auto_heal=True):
    """Returns (prompt_text, is_working) — the prompt fire_shot will actually submit right
    now. THE CORE LAW, HARD-ENFORCED (2026-07-19, Julian's department-gate directive, from
    confirmed forensic evidence: this exact function silently fell back to
    shot["seedancePrompt"] and let five real Seedance candidates fire, $15.47, with the
    Animation Director never having run). Raises DepartmentNotApproved unless a CURRENT,
    human-approved Animation Direction exists for this exact shot — NO fallback to the
    storyboard's own compiled seedancePrompt, and no fallback to an unapproved manual
    working prompt (save_seedance_working itself now refuses to save one until an approval
    already exists underneath it — see below). A working override, once saved, is layered
    ON TOP of that approval, never a way to skip needing one.

    allow_auto_heal=False (2026-07-22, Julian's full-audit directive): see the identical note
    on _resolve_keyframe_prompt — a read-only status/check caller (seedance_working_status,
    check_seedance_structure, evidence_pack) must never silently trigger a real LLM re-
    prepare + auto-approve; only fire_shot (the real spend path) keeps the default True."""
    if allow_auto_heal:
        _auto_heal_stale_department_if_previously_approved(pkg, scene, "animation", shot["shotId"], episode)
    approved, output = _require_approved_department(
        pkg, scene, "animation", shot["shotId"], episode,
        action_label=f"{shot['shotId']}'s animation prompt resolution")
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingSeedancePrompt")
    if working and working.get("text"):
        return working["text"], True
    return output["providerPrompt"], False


def seedance_working_status(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedPrompt": str, "currentPrompt": str (working override
    if saved, else the approved prompt — exactly what will be submitted), "isWorking": bool,
    "savedAt": str|None}. Propagates DepartmentNotApproved (a Refused subclass) exactly like
    every other read here does when its own required input is missing — the existing route
    (/api/shot-seedance-status) and UI (seedancePanelHTML's sw.error branch) already turn
    that into a clear on-screen message, the same precedent this file's whole working-prompt
    layer already established for a missing Scene Look/keyframe approval."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    current, is_working = _resolve_seedance_prompt(pkg, shot, scene, episode, allow_auto_heal=False)
    led = _ledger(pkg, shot_id)
    working = led.get("workingSeedancePrompt")
    specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    source = "human-working" if is_working else "animation-director-approved"
    return {"approvedPrompt": specialist.get("providerPrompt"), "currentPrompt": current,
            "source": source,
            "isWorking": is_working, "savedAt": (working or {}).get("savedAt")}


def save_seedance_working(scene, shot_id, prompt_text, episode="Ep1", reviewed_by="Julian",
                          dialogueInPromptConfirmed=False, log=print):
    """Saves a shot-level WORKING Seedance prompt — the approved storyboard's own compiled
    seedancePrompt is never touched, never rewritten. REFUSES outright (2026-07-19, item 3
    of the department-gate directive) unless a CURRENT, approved Animation Direction already
    exists for this shot — a working edit can only be layered ON TOP of an already-approved
    brief, never a way to hand-author a paid-route prompt with no department review behind
    it at all. Also refuses (never silently strips) a prompt that would violate Law 6, using
    the same timing-vs-dialogue-aware classifier every other Law 6 check in this file now
    shares. NEVER calls cb_gen — this is a save, not a generation.

    dialogueInPromptConfirmed (2026-07-23, Julian's directed experiment — 'we have had theses
    laws and they are not working lets trial the exact prompt and see what happens'): the ONE
    lawful bypass of the Law-6 leak check, matching the keyframePromptOverrideConfirmed /
    voiceScriptConfirmed explicit-confirmation pattern exactly. Never a default, never
    silent — the save is banner-logged and the confirmation + reviewer recorded on the
    ledger, so a dialogue-bearing prompt can only ever ship as a deliberate, on-the-record
    director decision. The known risk it accepts: the model may generate its own voice for
    the quoted words, competing with or replacing @Audio1."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    _require_approved_department(pkg, scene, "animation", shot_id, episode,
                                  action_label=f"saving {shot_id}'s working Seedance prompt")
    text = str(prompt_text or "").strip()
    if not text:
        raise Refused(f"REFUSED — {shot_id}'s working Seedance prompt cannot be blank")
    # THE FORMULA GATE (Gold Build, 2026-07-24): dialogue-in-prompt is now the LAW, not a
    # confirmed experiment — the 2026-07-23 dialogueInPromptConfirmed bypass is retired
    # (parameter kept for caller compatibility, ignored). Every working prompt must BE the
    # formula, with every dialogue line inline and verbatim.
    # THE FORMULA-EXPERIMENT DOOR (2026-07-25, Julian's directed test — "here is a prompt i
    # have put togehter run it as is... lets do a couple of tests"): the Gold Build retired
    # the old dialogueInPromptConfirmed bypass, but the DIRECTOR'S OWN hand-authored
    # experiment is the one lawful exception the confirmation pattern has always existed
    # for (keyframePromptOverrideConfirmed / voiceScriptConfirmed). formulaExperimentConfirmed
    # downgrades FORMULA failures to banner-logged, ledger-recorded ACCEPTED RISKS — never
    # silent, never a default; the drift-vocabulary ban below stays a hard refusal always.
    formula_experiment = bool(dialogueInPromptConfirmed)
    experiment_risks = []
    try:
        check_formula_structure(text, shot.get("dialogueLines") or [], shot=shot,
                                refuse_prefix=f"REFUSED — {shot_id}'s working Seedance prompt")
    except Refused as e:
        if not formula_experiment:
            raise
        experiment_risks.append(str(e))
        log(f"⚠⚠⚠ FORMULA EXPERIMENT ACTIVE — {shot_id}'s working prompt deviates from the "
            f"formula, per the director-confirmed experiment ({reviewed_by}). Accepted risks:")
        for r in experiment_risks:
            log(f"  | {r}")
    for _flag in check_craft_components(text):
        log(f"  CRAFT FLAG (advisory) — {_flag}")
    # THE DRIFT-VOCABULARY BAN (2026-07-24) — refused at save, so a bad working prompt
    # never even sits on the ledger waiting to fire.
    _check_no_drift_vocab(text, refuse_prefix=f"REFUSED — {shot_id}'s working Seedance prompt")
    led["workingSeedancePrompt"] = {"text": text, "savedAt": _now(), "savedBy": reviewed_by,
                                     "dialogueInPromptConfirmed": bool(dialogueInPromptConfirmed),
                                     "formulaExperimentRisks": experiment_risks or None}
    _save(pkg, path)
    log(f"ANIMATION WORKING PROMPT SAVED — {shot_id} ({len(text.split())} words, no "
        f"animation generated)")
    return led["workingSeedancePrompt"]


def restore_seedance_working(scene, shot_id, episode="Ep1", log=print):
    """Clears the working override — fire_shot reverts to submitting the approved storyboard's
    own compiled seedancePrompt, exactly as if no working version had ever been saved. Never
    generates animation."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    led["workingSeedancePrompt"] = None
    _save(pkg, path)
    log(f"ANIMATION WORKING PROMPT RESTORED — {shot_id}: reverted to the approved storyboard's prompt")


# ── THE SEEDANCE STRUCTURE CHECK (Julian's directive, 2026-07-19) ───────────────────────
# FREE. ZERO PROVIDER CALLS. ZERO COST. Reports exactly what firing would do right now,
# without firing. Only a missing PROVIDER-REQUIRED input (no anchor, no references, no
# billing confirmation, dialogue with no voice track, Law 6 leakage) may BLOCK; every
# creative observation (a possibly-removed scale clause, a duplicated sentence, a keyword-
# level camera conflict) is a WARNING — advisory only, never blocking, never rewritten here.
_CAMERA_MOVE_WORDS = re.compile(r"\b(pan|pans|panning|dolly|dollies|truck|trucks|orbit|orbits|zoom|zooms|tilt|tilts)\b",
                                 re.IGNORECASE)
_CAMERA_LOCK_WORDS = re.compile(r"\bcamera (?:lock|locked|holds|stays? (?:still|locked))\b", re.IGNORECASE)


def check_seedance_structure(scene, shot_id, episode="Ep1", log=print):
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    blockers, warnings, checks = [], [], {}

    try:
        _require_confirmed_billing("fal")
        checks["billingConfirmed"] = {"ok": True}
    except Refused as e:
        blockers.append(str(e)); checks["billingConfirmed"] = {"ok": False, "detail": str(e)}

    anchor = None
    try:
        anchor = _anchor_for(pkg, shot)
        checks["openingFrameAttached"] = {"ok": True, "path": anchor}
    except Refused as e:
        blockers.append(str(e)); checks["openingFrameAttached"] = {"ok": False, "detail": str(e)}

    characters_cfg = _characters_cfg()
    if anchor:
        try:
            imgs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, characters_cfg)
            checks["sceneLookAttached"] = {"ok": True}
            checks["referencesAttached"] = {"ok": True, "count": len(imgs),
                                             "order": list(shot["referenceSlots"].keys())}
        except Refused as e:
            blockers.append(str(e))
            checks["sceneLookAttached"] = {"ok": False, "detail": str(e)}
            checks["referencesAttached"] = {"ok": False, "detail": str(e)}
    else:
        checks["sceneLookAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}
        checks["referencesAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}

    if shot.get("dialogueLines"):
        # 2026-07-19: audio readiness now means APPROVED, not merely generated — matching
        # keyframe/animation's own "an unapproved artefact is never a valid anchor" rule.
        vo_approved = bool((led.get("voiceApproval") or {}).get("approved"))
        checks["audioAttached"] = {"ok": vo_approved, "required": True, "path": led.get("voPath")}
        if not vo_approved:
            reason = ("no voice track generated yet" if not led.get("voPath")
                      else "a voice track exists but has not been approved yet")
            blockers.append(f"{shot_id} has dialogue but {reason} "
                            f"(Law 5: voice first, no native-voice fallback)")
    else:
        checks["audioAttached"] = {"ok": True, "required": False, "detail": "no dialogue in this shot"}

    checks["durationSec"] = shot.get("durationSec")
    checks["resolution"] = "720p"
    checks["aspectRatio"] = "16:9"
    checks["model"] = "bytedance/seedance-2.0"

    # THE CORE LAW, CHECKED HERE TOO (2026-07-19): this is a report, never a crash — a
    # missing/stale Animation Direction is recorded as the single most important BLOCKER
    # this whole check exists to catch, not an exception that kills the report.
    resolved_prompt = None
    try:
        resolved_prompt, using_working = _resolve_seedance_prompt(pkg, shot, scene, episode, allow_auto_heal=False)
        checks["usingWorkingVersion"] = using_working
        checks["promptSource"] = "human-working" if using_working else "animation-director-approved"
        checks["animationDirectionApproved"] = {"ok": True}
    except DepartmentNotApproved as e:
        blockers.append(str(e))
        checks["animationDirectionApproved"] = {"ok": False, "detail": str(e)}
        checks["usingWorkingVersion"] = False
        checks["promptSource"] = "NONE — no approved Animation Direction, no disclosure authorisation"

    if resolved_prompt:
        # creative warnings — advisory only, never blocking, never rewritten
        if "relative scale" not in resolved_prompt.lower() and "identity" not in resolved_prompt.lower():
            warnings.append("no character-identity/relative-scale preservation clause detected "
                            "in the resolved prompt")
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", resolved_prompt) if s.strip()]
        seen = {}
        for s in sentences:
            seen[_norm(s)] = seen.get(_norm(s), 0) + 1
        dupes = sum(1 for v in seen.values() if v > 1)
        if dupes:
            warnings.append(f"{dupes} duplicated direction(s) detected in the resolved prompt")
        if _CAMERA_LOCK_WORDS.search(resolved_prompt) and _CAMERA_MOVE_WORDS.search(resolved_prompt):
            warnings.append("possible conflicting camera direction: both a camera lock and a "
                            "camera-movement word appear in the resolved prompt")

        # LAW 6 is provider-required, not creative — a leak here blocks, it does not warn.
        # Uses the shared timing-vs-dialogue-aware classifier (Julian's "software wide
        # provision for timing not dialog") so a legitimate lip-sync cadence reference is
        # never mistaken for a Law 6 violation here either.
        try:
            check_formula_structure(resolved_prompt, shot.get("dialogueLines") or [], shot=shot,
                                    refuse_prefix="FORMULA")
        except Refused as e:
            blockers.append(str(e))
        warnings.extend(f"craft component (advisory): {f}"
                        for f in check_craft_components(resolved_prompt))

    verdict = "blocked" if blockers else ("warnings" if warnings else "passed")
    result = {"verdict": verdict, "blockers": blockers, "warnings": warnings,
              "checks": checks, "finalPrompt": resolved_prompt}
    log(f"SEEDANCE STRUCTURE CHECK — {shot_id}: {verdict.upper()} ({len(blockers)} blocker(s), "
        f"{len(warnings)} warning(s)) — no provider call made, no cost")
    return result


def fire_shot(scene, shot_id, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              resolution="720p", spend_token=None, dry_run=False, log=print):
    """Generate one CONTROLLED CANDIDATE BATCH behind Julian's six spend protections
    (2026-07-16): (1) approval is SERVER-SIDE, SINGLE-USE and bound to the exact package
    hash + provider + model + candidate count + cost rate + max batch cost — anything that
    changes between disclosure and generation invalidates the token; (2) the batch is
    RESUMABLE and IDEMPOTENT — a resume generates only missing candidates, never repaying
    completed ones; (4) an unchanged reroll is verified against the identical binding, and
    any revision re-validates from scratch; (5) an unconfirmed billing profile hard-blocks;
    (6) every candidate and every failure is persisted, nothing deleted."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)                                     # the stored gate, cheapest first
    _require_own_clip(pkg, shot_id)     # a member card is not its own clip
    _require_current_lineage(pkg, scene, episode)           # THE STATE-INTEGRITY CHECKPOINT —
    # see keyframe_shot's identical fix (2026-07-19) for why this call was missing entirely.
    _require_confirmed_billing("fal")                       # protection 5 — block, not warn
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    # THE ANIMATION WORKING PROMPT, IF SAVED, IS WHAT ACTUALLY SUBMITS (2026-07-19, Julian's
    # contained-creative-controls directive): a shallow-copied VIEW of the shot with
    # seedancePrompt swapped for the working override — every downstream read in this
    # function (Law 6 check, binding hash, disclosure, sealed envelope, the real generate
    # call) already reads shot["seedancePrompt"], so this one substitution is the whole
    # change. The approved package's own shot record (pkg["shots"]) is never touched.
    # THE CORE LAW's own hard gate: raises DepartmentNotApproved (a Refused subclass) unless
    # a CURRENT, human-approved Animation Direction exists for this exact shot — no fallback
    # to shot["seedancePrompt"], no fallback to an unapproved working prompt. This call is
    # what makes the confirmed forensic bug ($15.47, five candidates, Animation Director
    # never run) structurally impossible from here on.
    resolved_prompt, using_working = _resolve_seedance_prompt(pkg, shot, scene, episode)
    if resolved_prompt != shot["seedancePrompt"]:
        shot = {**shot, "seedancePrompt": resolved_prompt}
    candidates = max(1, min(MAX_CANDIDATES, int(candidates)))
    # THE ACKNOWLEDGED REDESIGN CYCLE'S ONE-CANDIDATE CAP, ENFORCED HERE — THE DISCLOSURE-
    # AND-FIRING ROUTE ITSELF (2026-07-20), never only in the Studio interface. Checked
    # before any binding hash, envelope, or spend token is ever built — a request for more
    # than the cycle's own candidateLimit refuses immediately, before cost authorisation or
    # provider invocation. redesignCycle is set only by acknowledge_redesign and is never
    # cleared automatically — once a shot has recovered from model-limited via this path,
    # every fire against it stays capped at REDESIGN_CANDIDATE_LIMIT for the remainder of
    # its current (non-approved) lifecycle, the conservative reading of "the new
    # acknowledged cycle permits one candidate only."
    redesign_cycle = led.get("redesignCycle")
    if redesign_cycle and led.get("status") != "approved":
        limit = redesign_cycle.get("candidateLimit", REDESIGN_CANDIDATE_LIMIT)
        if candidates > limit:
            raise Refused(f"REFUSED — {shot_id} is in an acknowledged redesign test cycle "
                          f"({redesign_cycle.get('cycleId')}), which permits at most "
                          f"{limit} candidate(s) for its first controlled test; "
                          f"{candidates} were requested. Fire with --candidates {limit} "
                          f"(or fewer).")
    if led.get("status") == "model-limited":
        raise Refused(f"REFUSED — {shot_id} is MODEL-LIMITED after {MAX_BATCH_ATTEMPTS} failed "
                      f"candidate batches; the ladder requires human redesign or an alternative "
                      f"production method, never more prompt-patching.\n{DECISION_LADDER}")
    if led.get("status") == "approved":
        raise Refused(f"REFUSED — {shot_id} is already approved; reject it first to re-fire")
    if shot.get("dialogueLines") and not (led.get("voiceApproval") or {}).get("approved"):
        # 2026-07-19: requires APPROVAL, not mere file existence — matching the keyframe
        # anchor's own "a generated-but-unapproved candidate is never a valid anchor" rule.
        reason = ("no voice track generated yet" if not led.get("voPath")
                  else "its voice track has not been approved yet")
        raise Refused(f"REFUSED — {shot_id} has dialogue but {reason} "
                      f"(Law 5: voice first, no native-voice fallback)")

    # LAW 6, re-asserted at the last moment before money — the shared timing-vs-dialogue
    # classifier, matching every other Law 6 check in this file (2026-07-19).
    # 2026-07-23 (Julian's directed experiment): honoured EXCEPT when the saved working
    # prompt carries an explicit, on-the-record dialogueInPromptConfirmed — the same
    # confirmation save_seedance_working banner-logged and recorded; the fire re-announces
    # it rather than silently re-blocking what the director explicitly ordered.
    # THE FORMULA GATE AT FIRE — the stale-format door (Gold Build, 2026-07-24): the
    # resolved prompt must BE the house formula, unconditionally. Any pre-Gold shape (old
    # lean brief, tempo-map body, [STYLE_HEADER] experiment, source-material brief) fails
    # here and can never be presented to the API.
    # (2026-07-25) THE FORMULA-EXPERIMENT DOOR, HONOURED AT FIRE: a working prompt saved
    # with the director's explicit on-the-record confirmation (save_seedance_working's
    # dialogueInPromptConfirmed + recorded formulaExperimentRisks) is RE-ANNOUNCED here,
    # never silently re-blocked — exactly the contract the comment above already states
    # for the original 2026-07-23 experiment. Only the exact saved text qualifies; any
    # other deviation still refuses hard.
    _wk = led.get("workingSeedancePrompt") or {}
    _confirmed_exp = (bool(_wk.get("dialogueInPromptConfirmed"))
                      and (_wk.get("text") or "").strip() == str(shot["seedancePrompt"]).strip())
    try:
        check_formula_structure(shot["seedancePrompt"], shot.get("dialogueLines") or [], shot=shot,
                                refuse_prefix=f"REFUSED — {shot_id}'s resolved prompt")
    except Refused as _fe:
        if not _confirmed_exp:
            raise
        log(f"⚠⚠⚠ FORMULA EXPERIMENT ACTIVE — {shot_id} fires with a director-confirmed "
            f"off-formula prompt (saved by {_wk.get('savedBy','?')} on {_wk.get('savedAt','?')}). "
            f"Accepted risks re-announced:")
        for _line in str(_fe).split("; "):
            log(f"  | {_line}")

    # THE HANDLE DOCTRINE, RESTORED AT SHOT LEVEL (2026-07-19, Julian: "we want 15 second
    # clips with 2 seconds at the end to have for editing" — raised after S1.SH1's real V3
    # take (9.68s) overran its own 7.0s-designed clip with zero crash or warning). Root
    # cause: shot["durationSec"] is a DESIGN-TIME estimate authored at Gate-1, before any
    # real voice exists (cb_engine.py's 4-8s schema range) — it was never reconciled against
    # the REAL recorded take's actual length before firing the paid render. cb_engine's own
    # "a line can't end past the shot" validator never caught this because S1.SH1's two
    # authored dialogueLines both had startSec=0/endSec=durationSec — satisfying the check
    # by construction, even though two lines can't sensibly share the same whole window; it
    # was an estimate, not a real timed transcript. The exact same audio-aware
    # max(designed, real+buffer) correction already existed one function away, in
    # animatic_scene's own Gate-5 timing slate (_audio_dur(vo)+0.5) — it simply never
    # reached this, the real fire path. Fixed at the ONE choke point every downstream read
    # (_binding_hash, _sealed_envelope, the disclosure log, generate_video_seedance_ref's own
    # duration= argument) already shares: shot["durationSec"] is overridden here, once,
    # before any of them run — HANDLE_TOTAL/HANDLE_SETTLE are the same 15s/2s split this
    # project's own archived beat-level doctrine used, restored now at shot granularity.
    # A resumed (already-disclosed) batch is unaffected — it replays its own sealed
    # envelope's original duration via _verify_envelope, never recomputes.
    fire_duration = _handle_duration(led.get("voPath"), shot.get("durationSec"))
    if fire_duration != shot["durationSec"]:
        shot = {**shot, "durationSec": fire_duration}

    # THE UNCHANGED-PACKAGE RULE: nothing is auto-appended after a failure — a reroll ships
    # the byte-identical contract; a targeted correction is a NEW versioned package that
    # re-validates and re-discloses below (the binding hash makes this mechanical).
    prompt = shot["seedancePrompt"]
    anchor = _anchor_for(pkg, shot)
    characters_cfg = _characters_cfg()
    imgs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, characters_cfg)

    # ── RESUME PATH (protection 2): an in-flight batch completes its MISSING candidates
    # only, under its ORIGINAL token — completed candidates are never regenerated or repaid
    batch = led.get("batch")
    if batch and batch.get("status") == "generating":
        if spend_token != batch["token"]:
            raise Refused(f"REFUSED — {shot_id} has an in-flight batch; resuming requires its "
                          f"original spend token (nothing new is authorized)")
        binding, _per = _binding_hash(pkg, shot, led, imgs, anchor, batch["expected"], fast,
                                       resolution=(batch.get("envelope") or {}).get("resolution", "720p"))
        if binding != batch["bindingHash"]:
            raise Refused(f"REFUSED — the package changed mid-batch (binding mismatch); the "
                          f"in-flight authorization is void. Request a new disclosure.")
        # a resume ships the SAME sealed envelope the original approval bound (§5)
        envelope = _verify_envelope(batch)
        prompt = envelope["prompt"]
        fast = (envelope["tier"] == "fast")
        candidates = batch["expected"]
    else:
        if led.get("status") == "candidates-pending":
            raise Refused(f"REFUSED — {shot_id} has a candidate batch pending Julian's review "
                          f"(approve one candidate or reject the batch first)")
        # PROTECTION 4: fresh validation of the CURRENT package, every disclosure
        _fresh_validation(pkg, episode)
        binding, per = _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast,
                                      resolution=resolution)
        envelope, env_hash = _sealed_envelope(pkg, shot, led, imgs, anchor, candidates,
                                                fast, per, resolution=resolution)
        # THE DRIFT-VOCABULARY BAN, at the ship point (2026-07-24): the literal text about
        # to be disclosed and fired — working override or compiled, no path around it.
        _check_no_drift_vocab(envelope["prompt"], refuse_prefix=f"REFUSED — {shot_id}")
        reroll = (led.get("lastBatchBinding") == binding)
        disclosure = {"shotId": shot_id, "candidateCount": candidates,
                       "resolution": str(resolution),
                       "costPerCandidateUsd": per,
                       "maxBatchCostUsd": round(per * candidates, 4),
                       "promptVersion": _prompt_version(shot),
                       "usingWorkingPrompt": using_working,
                       "bindingHash": binding,
                       "envelopeHash": env_hash,
                       "packageHash": _shots_hash(pkg),
                       "rerollOfUnchangedPackage": reroll,
                       "packageRevision": pkg.get("revision"),
                       "referenceSlots": shot["referenceSlots"],
                       "openingAnchor": anchor, "audioAsset": led.get("voPath"),
                       "shotDurationSec": shot["durationSec"],
                       "tier": "fast" if fast else "standard"}
        log("SPEND DISCLOSURE — review before approving:")
        # THE PROMPT-TEXT TRANSPARENCY FIX (2026-07-22, Julian, live — "are you sure the
        # right prompt launched, show me the prompt that was sent"): forensic proof showed
        # S1.SH1 actually fired on a stale workingSeedancePrompt Julian saved on 2026-07-20,
        # two days before the full 5-shot restage, silently shadowing the fresh Animation
        # Director prompt — using_working was already computed above but never surfaced
        # here; this disclosure printed only an opaque promptVersion hash, never the literal
        # words about to be submitted, and never said a working override was even in play.
        # check_seedance_structure/seedance_working_status already did this correctly (both
        # print the resolved text plus an explicit "usingWorkingVersion"/"working version"
        # flag) — this was the one real spend-authorisation disclosure that didn't match
        # that standard. Fixed at the source: an unmissable banner when a working override
        # is shadowing the approved output, and the full resolved prompt text printed here,
        # every time — never just a hash again.
        if using_working:
            saved = (led.get("workingSeedancePrompt") or {})
            log(f"  ⚠⚠⚠ USING A SAVED WORKING OVERRIDE (saved by {saved.get('savedBy','?')} "
                f"on {saved.get('savedAt','?')}) — this REPLACES the Animation Director's "
                f"current approved output below. If the storyboard/restage has moved on "
                f"since this override was saved, it is now STALE; restore-seedance-working "
                f"clears it back to the fresh approved prompt.")
        for k in ("shotId", "candidateCount", "costPerCandidateUsd", "maxBatchCostUsd",
                   "promptVersion", "usingWorkingPrompt", "bindingHash", "envelopeHash",
                   "packageRevision", "rerollOfUnchangedPackage", "openingAnchor",
                   "audioAsset", "shotDurationSec", "tier"):
            log(f"  {k}: {disclosure[k]}")
        log(f"  referenceSlots (upload order): {json.dumps(disclosure['referenceSlots'])}")
        log("  --- THE EXACT PROMPT TEXT ABOUT TO BE SUBMITTED (not a hash — the real words) ---")
        for line in shot["seedancePrompt"].splitlines():
            log(f"  | {line}")
        log("  --- end of prompt text ---")

        auth = led.get("pendingSpendAuth")
        if dry_run:
            log("SEALED PROVIDER-REQUEST ENVELOPE (dry run — no token issued, nothing stored):")
            log(json.dumps(envelope, indent=1, ensure_ascii=False))
            log(f"ENVELOPE SHA-256: {env_hash}")
            raise Refused("REFUSED — DRY RUN. No spend token was issued and no state changed.")
        if spend_token is None:
            # issue (or re-issue) the server-side single-use token, bound to the SEALED envelope
            led["pendingSpendAuth"] = {"token": uuid.uuid4().hex,
                                        "bindingHash": binding,
                                        "envelope": envelope, "envelopeHash": env_hash,
                                        "disclosure": disclosure, "issuedAt": _now()}
            _save(pkg, path)
            raise Refused("REFUSED — SPEND NOT APPROVED. A single-use spend token has been "
                          "issued, bound to the sealed envelope above; re-run with "
                          f"--spend-token {led['pendingSpendAuth']['token']} "
                          "(Studio: 'Approve spend & fire').")
        # validate the presented token: server-issued, single-use, envelope-exact
        if not auth or spend_token != auth["token"]:
            raise Refused("REFUSED — unknown or already-used spend token; request a new "
                          "disclosure")
        if auth["bindingHash"] != binding:
            raise Refused("REFUSED — the spend token is STALE: the package, references, "
                          "audio, cost or settings changed after the disclosure. Request a "
                          "new disclosure and approval.")
        # THE SEAL (§5): firing sends the DISCLOSED envelope verbatim — never a recompile,
        # never another prompt, never another duration. Verified file-by-file.
        envelope = _verify_envelope(auth)
        prompt = envelope["prompt"]
        fast = (envelope["tier"] == "fast")
        candidates = envelope["candidateCount"]
        led["pendingSpendAuth"] = None                     # single-use: consumed NOW
        pv = auth["disclosure"]["promptVersion"]
        if led.get("lastPromptVersion") and led["lastPromptVersion"] != pv:
            led["promptRevisions"] = led.get("promptRevisions", 0) + 1
        led["lastPromptVersion"] = pv
        batch = {"token": spend_token, "bindingHash": binding,
                 "envelope": envelope, "envelopeHash": auth["envelopeHash"],
                 "batchId": f"{shot_id}-b{led.get('batchAttempts', 0) + 1}-"
                             f"{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}",
                 "expected": candidates, "done": [], "failed": [],
                 "disclosure": auth["disclosure"], "status": "generating"}
        led["batch"] = batch
        _save(pkg, path)

    image_urls = [cb_gen._fal_upload(x) for x in imgs]     # uploaded once per invocation
    audio_urls = [cb_gen._fal_upload(led["voPath"])] if led.get("voPath") else None

    MEDIA.mkdir(parents=True, exist_ok=True)
    for i in range(1, batch["expected"] + 1):
        if i in batch["done"]:
            continue                                       # idempotent: never regenerated
        out = MEDIA / f"{episode}_{shot_id}_c{i}.mp4"
        log(f"FIRE — {shot_id} candidate {i}/{batch['expected']} ({shot['sourceType']}, "
            f"{shot['durationSec']}s{', @Audio1' if audio_urls else ''}) ...")
        try:
            cb_gen.generate_video_seedance_ref(prompt, image_urls,
                                                audio_urls=audio_urls,
                                                resolution=envelope["resolution"],
                                                duration=str(int(round(envelope["durationSec"]))),
                                                out=str(out), fast=fast, raw_prompt=True, production_route="cb_render")
        except Exception as e:
            # protection 6: the failure is PERSISTED, the batch stays resumable
            batch["failed"].append({"candidate": i, "error": str(e)[:400], "at": _now()})
            _save(pkg, path)
            raise Refused(f"REFUSED — candidate {i} failed at the provider "
                          f"({str(e)[:160]}). The batch is saved and resumable: re-run with "
                          f"the SAME spend token to generate only the missing candidates — "
                          f"completed candidates are never repaid.")
        _candidate_review(shot, str(out), batch["batchId"], i)
        batch["done"].append(i)
        _save(pkg, path)                                   # persisted per candidate

    batch["status"] = "complete"
    paths = [str(MEDIA / f"{episode}_{shot_id}_c{i}.mp4") for i in sorted(batch["done"])]
    led.update({"status": "candidates-pending", "candidatePaths": paths,
                "batchId": batch["batchId"],
                "candidatesGenerated": led.get("candidatesGenerated", 0) + len(batch["done"]),
                "disclosure": batch["disclosure"],
                "lastBatchBinding": batch["bindingHash"], "firedAt": _now()})
    _save(pkg, path)

    # THE VERDICT CORPUS (2026-07-25): every real fire is recorded whole — prompt + hash,
    # reference and audio hashes, provider/model/resolution, the formula that was in the
    # writer's mind, cost and the clips. Julian's verdict lands against it at approve/
    # reject. This pairing is the asset the SH1 formula was found from; nothing survived
    # to make the next one cheaper until now. Never raises — evidence-keeping must not be
    # able to fail a fire it is only observing.
    cb_corpus.record_fire(
        episode=episode, scene=scene, shot_id=shot_id, prompt=prompt,
        refs=[{"role": (shot.get("referenceSlots") or {}).get(pth) or f"slot{i}",
               "path": pth} for i, pth in enumerate(imgs, 1)],
        audio_path=led.get("voPath"),
        provider=(batch.get("disclosure") or {}).get("provider"),
        model=(batch.get("disclosure") or {}).get("model"),
        resolution=resolution, candidates=len(paths),
        expected_cost=(batch.get("disclosure") or {}).get("maxBatchCost"),
        clips=paths,
        formula=_approved_formula_meta(pkg, scene, shot_id, episode))

    log(f"FIRE — {shot_id}: {len(paths)} candidate(s) rendered · STOPPED for Julian's "
        f"review. Approve ONE (approve {scene} {shot_id} <n>) or reject the batch. "
        f"No candidate is ever auto-approved.")
    return paths


def _candidate_review(shot, clip, batch_id, index):
    """The per-candidate review sheet (§6): the ten human criteria, all null — supporting
    human review only; the machine NEVER auto-approves creative quality. Machine notes hold
    only what is mechanically checkable (duration)."""
    real = cb_post._dur(clip) or 0.0
    notes = []
    if abs(real - float(shot["durationSec"])) > DUR_TOLERANCE_SEC:
        notes.append(f"duration {real:.1f}s vs designed {shot['durationSec']}s")
    review = {"shotId": shot["shotId"], "batchId": batch_id, "candidate": index,
              "at": _now(),
              "criteria": {c: None for c in REVIEW_CRITERIA},
              "note": "human review only — the machine never approves creative quality",
              "machineNotes": notes}
    with open(clip + ".review.json", "w") as f:
        json.dump(review, f, indent=1)
    return review


def next_shot(scene, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, resolution="720p", log=print):
    """Fire a candidate batch for the next fireable shot in order, then STOP."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        if led.get("status") == "candidates-pending":
            raise Refused(f"REFUSED — {s['shotId']} has a candidate batch pending Julian's "
                          f"review; nothing advances past it")
        if led.get("status") == "model-limited":
            raise Refused(f"REFUSED — {s['shotId']} is model-limited and blocks the walk; "
                          f"it needs human redesign before the scene can continue")
        if led.get("status") != "approved" or (led.get("batch") or {}).get("status") == "generating":
            return fire_shot(scene, s["shotId"], episode, candidates=candidates,
                              fast=fast, spend_token=spend_token, log=log, dry_run=dry_run,
                              resolution=resolution)
    log(f"SCENE {scene} — every shot approved; ready to stitch")
    return None


# ── Gate 8 — Julian selects ONE candidate; approval harvests the relay anchor ───────────
def unapprove_shot(scene, shot_id, episode="Ep1", note="", reviewed_by="Julian", log=print):
    """UNDO AN ANIMATION-TAKE APPROVAL (2026-07-25, same ruling) — the approved take goes
    BACK to being a pending candidate batch of one (re-approve it, or reject the batch and
    re-fire). The take file and its harvested final frame stay on disk untouched; nothing
    is deleted. NOTE: any LATER shot already fired off this take's harvested frame is not
    rewound by this call — un-approve those separately if their anchor must change."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    appr = led.get("approval")
    if led.get("status") != "approved" or not appr or not appr.get("approved"):
        raise Refused(f"REFUSED — {shot_id} has no approved animation take to undo")
    take = led.get("approvedTake")
    if not take or not os.path.exists(take):
        raise Refused(f"REFUSED — {shot_id}'s approved take file is missing on disk; "
                      f"cannot return it to a reviewable candidate state")
    led.setdefault("approvalHistory", []).append({**appr, "outcome": "unapproved",
                                                   "unapprovedAt": _now(),
                                                   "reviewedBy": reviewed_by,
                                                   "unapprovedNote": (note or "").strip() or None,
                                                   "take": take})
    led.update({"status": "candidates-pending", "candidatePaths": [take],
                "approvedTake": None, "approvedCandidate": None, "approval": None})
    _save(pkg, path)
    log(f"ANIMATION UN-APPROVED — {shot_id} by {reviewed_by}; the take is back as candidate "
        f"1 of 1 AWAITING your decision (approve 1, or reject the batch); nothing deleted")
    return True


def approve_shot(scene, shot_id, candidate=1, episode="Ep1", reviewed_by="Julian", log=print):
    """Select ONE candidate from the pending batch. The unselected candidates are archived
    (never deleted); the selected take's literal final frame is harvested as the next
    relay's anchor."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "candidates-pending" or not led.get("candidatePaths"):
        raise Refused(f"REFUSED — {shot_id} has no candidate batch pending review")
    cands = led["candidatePaths"]
    candidate = int(candidate)
    if not 1 <= candidate <= len(cands):
        raise Refused(f"REFUSED — candidate must be 1..{len(cands)} for {shot_id}")
    selected = cands[candidate - 1]

    # archive the unselected candidates + their review sheets (never deleted)
    cb_corpus.record_verdict(shot_id=shot_id, kept=True, episode=episode, scene=scene,
                             verdict=f"approved candidate {candidate}", reviewed_by=reviewed_by)
    arch = HERE / "media" / "archive" / "shots_candidates" / led["batchId"]
    arch.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(cands, 1):
        if i == candidate:
            continue
        for ext in ("", ".review.json"):
            if os.path.exists(c + ext):
                shutil.move(c + ext, arch / os.path.basename(c + ext))

    harvest = MEDIA / f"{episode}_{shot_id}_final_frame.png"
    cb_gen.last_frame(selected, out=str(harvest))
    led.update({"status": "approved", "approvedTake": selected,
                "approvedCandidate": candidate, "harvestFrame": str(harvest),
                "approval": {"approved": True, "candidate": candidate,
                              "reviewed_by": reviewed_by, "at": _now()}})
    _save(pkg, path)
    # off-machine backup of the approved take — ported from cb_beats (the 2026-07-08
    # operational-risk fix); fail-soft, never blocks an approval
    try:
        root = str(HERE.parent)
        if root not in sys.path:
            sys.path.insert(0, root)   # tools/ lives at repo root (same resolution cb_beats uses)
        import tools.backup_media as _backup
        _backup.backup_one(os.path.abspath(selected))
        _backup.backup_one(os.path.abspath(str(harvest)))
    except Exception as e:
        log(f"  (backup skipped: {e})")
    log(f"APPROVED — {shot_id} candidate {candidate} by {reviewed_by}; "
        f"final frame harvested -> {harvest.name}; unselected candidates archived")
    return str(harvest)


def reject_shot(scene, shot_id, correction, category="other", episode="Ep1",
                reviewed_by="Julian", log=print):
    """Reject the WHOLE candidate batch: every candidate archived (never deleted) with the
    one-sentence correction and its failure category on record. The next fire is a
    controlled reroll of the UNCHANGED package; after MAX_BATCH_ATTEMPTS failed batches the
    shot is MODEL-LIMITED and requires human redesign (the decision ladder's hard stop)."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "candidates-pending" or not led.get("candidatePaths"):
        raise Refused(f"REFUSED — {shot_id} has no candidate batch pending review")
    if category not in FAILURE_CATEGORIES:
        raise Refused(f"REFUSED — category must be one of {FAILURE_CATEGORIES}")
    # Second-resolution timestamps collide when two rejections land in the same second —
    # the second would archive INTO the first's directory and its REJECTED.json would
    # overwrite the first correction, losing a real verdict. Same bug class already fixed
    # for cb_beats.record_approval; closed here too now that the iteration budget makes
    # rapid successive rejections normal rather than rare.
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    base = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_{ts}"
    arch, n = base, 1
    while arch.exists():
        arch = base.with_name(f"{base.name}_{n}")
        n += 1
    arch.mkdir(parents=True, exist_ok=True)
    for c in led["candidatePaths"]:
        for ext in ("", ".review.json"):
            if os.path.exists(c + ext):
                shutil.move(c + ext, arch / os.path.basename(c + ext))
    # A rejection is worth more to the corpus than an approval — it names what went wrong
    # in Julian's own words, against the exact prompt that produced it.
    cb_corpus.record_verdict(shot_id=shot_id, kept=False, episode=episode, scene=scene,
                             verdict=correction, category=category, reviewed_by=reviewed_by)
    # WHICH FIX TIER THIS REJECTION CALLS FOR (2026-07-25). Recorded, not enforced —
    # the corpus needs it to tell us whether AnyFilm's measured 30/45/20/5 distribution
    # holds for THIS show. `variance` is the tier we never had: nothing is wrong with the
    # prompt, the roll was unlucky, and the correct next action is the identical prompt
    # again. Treating that as a diagnosis problem is how a third of re-fires solve nothing.
    tier = ("reroll_identical" if category == "variance" else
            "edit_one_element" if category in ("identity", "geography") else
            "rewrite_clip" if category == "action-timing" else "edit_one_element")
    rejection = {"shotId": shot_id, "batchId": led.get("batchId"),
                 "correction": correction, "category": category, "fixTier": tier,
                 "reviewed_by": reviewed_by, "at": _now()}
    with open(arch / "REJECTED.json", "w") as f:
        json.dump(rejection, f, indent=1)
    attempts = led.get("batchAttempts", 0) + 1
    led.setdefault("rejections", []).append(rejection)
    led.update({"batchAttempts": attempts, "candidatePaths": None, "batchId": None})
    if attempts >= MAX_BATCH_ATTEMPTS:
        led["status"] = "model-limited"
        _save(pkg, path)
        log(f"REJECTED — {shot_id} batch archived. {attempts} failed batches: shot is now "
            f"MODEL-LIMITED. Human redesign or an alternative production method required.\n"
            f"{DECISION_LADDER}")
    else:
        led["status"] = "designed"
        _save(pkg, path)
        log(f"REJECTED — {shot_id} batch archived ({attempts}/{MAX_BATCH_ATTEMPTS} attempts). "
            f"Correction on record: {correction} [{category}]\n{DECISION_LADDER}")
    return str(arch)


# ── STATE-INTEGRITY REPAIR (Julian's directive, 2026-07-20) ─────────────────────────────
# Found live: a package-promotion race (see the freshness guard cb_handover.promote_to_
# canonical gained the same night) let a stale, pre-rejection ledger snapshot silently
# overwrite S1.SH1's real rejection history — the live package still claimed candidatePaths
# for files that reject_shot had already archived, with zero rejections on record, even
# though Julian had genuinely rejected them. This section repairs THAT class of drift —
# reconciling the live ledger against its own already-durable, on-disk REJECTED.json
# archive — never a new creative decision, never a provider call, never a hand-edited JSON.
_REJECTION_ARCHIVE_RE = re.compile(r"^(?P<episode>.+)_(?P<shot>.+)_(\d{8}T\d{6})$")


def _shot_rejection_archives(episode, shot_id):
    """Every real, on-disk REJECTED.json record for this shot's PLAIN candidate-batch
    rejections (never the _voice_/_keyframe_-suffixed archive folders reject_voice/
    reject_keyframe write — a different history entirely, matched here as a NON-match since
    those folder names carry an extra "_voice_"/"_keyframe_" token between shot_id and the
    timestamp that this pattern's own trailing \\d{8}T\\d{6} anchor can't span across).
    Sorted chronologically by the record's own `at` field, oldest first. Read-only — never
    invents, never mutates a record; a record whose own shotId doesn't match shot_id is
    silently skipped (defends against a hypothetical future shot-id collision in the
    timestamp-only folder name, never trusted on folder name alone)."""
    root = HERE / "media" / "archive" / "shots_rejected"
    if not root.exists():
        return []
    prefix = f"{episode}_{shot_id}_"
    # optional _N disambiguator: two rejections in the same second get _1, _2 ...
    # (added with the archive-collision fix, 2026-07-25 — without it this scan
    # silently skipped every collided archive and under-reported real evidence)
    ts_re = re.compile(r"^\d{8}T\d{6}(?:_\d+)?$")
    found = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not d.name.startswith(prefix):
            continue
        rest = d.name[len(prefix):]
        if not ts_re.match(rest):
            continue                                  # e.g. "voice_20260718T104005" — skip
        rj = d / "REJECTED.json"
        if not rj.exists():
            continue
        try:
            rec = json.loads(rj.read_text())
        except Exception:
            continue
        if rec.get("shotId") == shot_id:
            rec["_archiveDir"] = str(d)
            found.append(rec)
    found.sort(key=lambda r: r.get("at") or "")
    return found


def audit_shot_integrity(scene, episode="Ep1", log=print):
    """THE STANDING DEAD-LINK + OLD-PROMPT AUDIT (2026-07-24, Julian — "we cannot have any
    dead links or old prompt styles i asked you to do an audit and this is what you brought
    back nothing"): the earlier Studio audit checked buttons/state/workflows and never
    audited the CONTENT already sitting on the ledger — S1.SH3 then fired a pre-template
    prompt with sunset vocabulary. This closes that scope gap as a permanent, re-runnable
    command, not a one-off pass:
      DEAD LINKS  — every file path a shot's live state references must exist on disk
                    (voPath, harvestFrame, approvedTake, candidatePaths, keyframe approval,
                    every resolvable reference slot).
      OLD PROMPTS — every LIVE prompt text (compiled seedancePrompt/keyframePrompt, working
                    overrides, APPROVED department providerPrompts — never append-only
                    history) is scanned for the banned drift vocabulary (_DRIFT_VOCAB_RE).
    Read-only; returns the findings list (empty == clean). CLI: `audit <scene>`."""
    pkg, _path = load_pkg(scene, episode)
    findings = []

    def _dead(shot_id, label, p):
        if p and not os.path.exists(str(p)):
            findings.append(f"{shot_id}: DEAD LINK — {label}: {p}")

    def _vocab(shot_id, label, text):
        hits = sorted({m.group(0).lower() for m in _DRIFT_VOCAB_RE.finditer(text or "")})
        if hits:
            findings.append(f"{shot_id}: OLD PROMPT VOCAB — {label}: {', '.join(hits)}")

    characters_cfg = _characters_cfg()
    for shot in pkg["shots"]:
        sid = shot["shotId"]
        led = _ledger(pkg, sid)
        _dead(sid, "voPath", led.get("voPath"))
        _dead(sid, "harvestFrame", led.get("harvestFrame"))
        _dead(sid, "approvedTake", led.get("approvedTake"))
        for c in (led.get("candidatePaths") or []):
            _dead(sid, "candidate", c)
        _dead(sid, "keyframeApproval.path", (led.get("keyframeApproval") or {}).get("path"))
        for slots_field in ("referenceSlots", "keyframeReferenceSlots"):
            if shot.get(slots_field):
                try:
                    anchor = _anchor_for(pkg, shot) if slots_field == "referenceSlots" else None
                    for p in _slot_paths(shot, slots_field, anchor, scene, episode, characters_cfg):
                        _dead(sid, f"{slots_field} ref", p)
                except Refused:
                    # a Refused here is the pipeline's own sequencing gate speaking (e.g. a
                    # relay shot whose predecessor isn't approved+harvested yet) — correct
                    # order-of-operations state, never a dead link
                    pass
                except Exception as e:
                    findings.append(f"{sid}: DEAD LINK — {slots_field} unresolvable: {e}")
        _vocab(sid, "compiled seedancePrompt", shot.get("seedancePrompt"))
        _vocab(sid, "compiled keyframePrompt", shot.get("keyframePrompt"))
        _vocab(sid, "workingSeedancePrompt", (led.get("workingSeedancePrompt") or {}).get("text"))
        wkf = led.get("workingKeyframePrompt")
        _vocab(sid, "workingKeyframePrompt",
               wkf.get("text") if isinstance(wkf, dict) else wkf)
        for stage, work in (led.get("departmentWork") or {}).items():
            for tier in ("approved", "candidate"):
                out = ((work or {}).get(tier) or {}).get("output") or {}
                if isinstance(out, dict) and out.get("providerPrompt"):
                    _vocab(sid, f"{stage} {tier} providerPrompt", out["providerPrompt"])

    # scene-level: the Scene Look's own department work (the plate prompt) gets the same scan
    for stage, work in ((pkg.get("sceneLook") or {}).get("departmentWork") or {}).items():
        for tier in ("approved", "candidate"):
            out = ((work or {}).get(tier) or {}).get("output") or {}
            if isinstance(out, dict):
                for fld in ("providerPrompt", "paletteAndLighting"):
                    if out.get(fld):
                        _vocab("SCENELOOK", f"{stage} {tier} {fld}", out[fld])

    if findings:
        log(f"AUDIT — scene {scene}: {len(findings)} finding(s)")
        for f in findings:
            log("  ✗ " + f)
    else:
        log(f"AUDIT — scene {scene}: CLEAN (no dead links, no drift vocabulary in any live prompt)")
    return findings


def reconcile_shot_history(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
    """THE CANONICAL STATE-INTEGRITY REPAIR — reconciles a shot's live continuityLedger
    against its OWN already-recorded, on-disk rejection archive when the two have drifted
    apart (the promotion race above). This is NOT a new creative decision and calls NO
    provider — every rejection it can recover ALREADY happened and is ALREADY durably
    recorded in engine/media/archive/shots_rejected/; this only makes the ledger honest
    about it again, through the same load_pkg/_save every other real state transition in
    this file already uses — never a hand-edited JSON.

    Verifies, before trusting a single record: batchId (cross-checked, per record, below),
    timestamp ordering, shotId, reviewer, and — for whichever archive folder(s) the shot's
    CURRENTLY-dangling candidatePaths belong to — that the exact files the live ledger
    claims still exist really do exist, safely, inside that folder (never silently
    dropping a live pointer without confirming the thing it pointed at was actually
    relocated, not lost).

    Refuses (no write) if:
      - no rejection archive exists for this shot at all;
      - the live ledger already reflects every archived rejection (idempotent — re-running
        this after a successful reconciliation finds nothing new and refuses rather than
        duplicating history);
      - the live candidatePaths point at files that are demonstrably NEITHER at their
        original location NOR anywhere in this shot's own rejection archive — real
        potential data loss, never silently written over.

    batchAttempts counts DISTINCT rejected batchIds, not raw REJECTED.json records — the
    SAME clobber bug this repairs also let one real batch (S1.SH1-b1-20260720T212657) get
    rejected twice tonight (Julian's own verdict re-entered after the first rejection was
    silently undone) before this fix existed; that is one rejected batch, not two, and is
    counted as one toward MAX_BATCH_ATTEMPTS. Every recovered record is still preserved
    verbatim in led["rejections"] — nothing about the double-entry is hidden, only the
    THRESHOLD COUNT is de-duplicated by batch."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)

    archived = _shot_rejection_archives(episode, shot_id)
    if not archived:
        raise Refused(f"REFUSED — no rejection archive records exist for {shot_id}; "
                      f"there is nothing to reconcile")

    already = {(r.get("batchId"), r.get("at")) for r in (led.get("rejections") or [])}
    missing = [r for r in archived if (r.get("batchId"), r.get("at")) not in already]
    if not missing:
        raise Refused(f"REFUSED — {shot_id}'s live ledger already reflects every one of the "
                      f"{len(archived)} rejection record(s) on record; nothing to reconcile")

    missing_batch_ids = {r.get("batchId") for r in missing}
    dangling = (led.get("candidatePaths") is not None and
                led.get("batchId") in missing_batch_ids)

    if dangling:
        # Confirm every dangling path is genuinely SAFE to drop the pointer to — either it
        # was legitimately moved (gone from its original spot, present in one of THIS shot's
        # own archive folders) or it never existed in the first place (a candidate slot the
        # batch simply never filled). If a path is missing from BOTH places, that's real,
        # unexplained data loss — refuse rather than silently clear the only record of it.
        archive_names = set()
        for r in archived:
            d = r.get("_archiveDir")
            if d and os.path.isdir(d):
                archive_names.update(os.listdir(d))
        unsafe = []
        for p in (led.get("candidatePaths") or []):
            if os.path.exists(p):
                continue                              # still at its original spot — fine
            if os.path.basename(p) in archive_names:
                continue                              # confirmed relocated to the archive
            unsafe.append(p)
        if unsafe:
            raise Refused(
                f"REFUSED — {shot_id}'s live candidatePaths name file(s) that are neither at "
                f"their original location nor findable in any of this shot's own rejection "
                f"archives: {unsafe}. This looks like real data loss, not a relocated "
                f"candidate — reconciliation refuses rather than silently dropping the only "
                f"record of where they were meant to be.")

    before = {"status": led.get("status"), "candidatePaths": led.get("candidatePaths"),
              "batchId": led.get("batchId"), "batchAttempts": led.get("batchAttempts"),
              "rejectionsCount": len(led.get("rejections") or [])}

    led.setdefault("rejections", [])
    for r in missing:
        clean = {k: v for k, v in r.items() if k != "_archiveDir"}
        led["rejections"].append(clean)
    led["rejections"].sort(key=lambda r: r.get("at") or "")

    distinct_batches = sorted({r.get("batchId") for r in led["rejections"]})
    led["batchAttempts"] = len(distinct_batches)
    if dangling:
        led["candidatePaths"] = None
        led["batchId"] = None
    if led["batchAttempts"] >= MAX_BATCH_ATTEMPTS:
        led["status"] = "model-limited"

    audit = {
        "at": _now(), "reviewedBy": reviewed_by, "action": "reconcile_shot_history",
        "recoveredRejections": [{"batchId": r.get("batchId"), "at": r.get("at"),
                                  "category": r.get("category")} for r in missing],
        "distinctRejectedBatches": distinct_batches,
        "before": before,
        "after": {"status": led.get("status"), "candidatePaths": led.get("candidatePaths"),
                   "batchId": led.get("batchId"), "batchAttempts": led.get("batchAttempts"),
                   "rejectionsCount": len(led["rejections"])},
        "reason": ("a package-promotion race (cb_handover.promote_to_canonical reading a "
                   "stale, pre-rejection ledger snapshot near the start of a slow compile, "
                   "then writing it back after a newer reject_shot call had already saved "
                   "over it) silently overwrote this shot's real rejection history. Recovered "
                   "here from the durable, already-verified on-disk REJECTED.json archive "
                   "records — no rejection is invented; every one recovered here is "
                   "cross-checked (shotId, batchId, timestamp ordering, and — for whichever "
                   "batch was live-dangling — that its candidate files are genuinely findable "
                   "in the archive) before being trusted. Zero provider calls; every cost, "
                   "approval, keyframe and department record is left completely untouched."),
    }
    led.setdefault("stateReconciliationLog", []).append(audit)

    _save(pkg, path)
    log(f"RECONCILED — {shot_id}: recovered {len(missing)} rejection record(s) across "
        f"{len(distinct_batches)} distinct batch(es); status {before['status']!r} -> "
        f"{led.get('status')!r}; dangling candidatePaths/batchId cleared: {dangling}. "
        f"Zero provider calls, zero dollars spent.")
    return audit


# ── THE BOUNDED REDESIGN-RECOVERY ACTION (Julian's directive, 2026-07-20) ───────────────
# A shot that is MODEL-LIMITED (two rejected candidate batches, the decision ladder's own
# hard stop, above) has exactly ONE way forward: this action. It is not a generic reset,
# override or force-unlock — every eligibility condition below must hold, all at once, or
# it refuses with the full list of what's missing. Makes ZERO provider calls, spends ZERO
# dollars, generates NOTHING; it only records that Julian has reviewed a GENUINELY CHANGED,
# CURRENTLY APPROVED set of inputs against the exact inputs the last rejected batch actually
# used, and opens one new attempt cycle permitting exactly one candidate for its first
# controlled test.
REDESIGN_CANDIDATE_LIMIT = 1


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text):
    """SHA-256 of a UTF-8 string. Never Python's built-in hash() — that's process-salted
    and not stable across runs, useless as a comparable signature."""
    return _sha256_bytes((text or "").encode("utf-8"))


def _optional_sha256_file(path):
    """SHA-256 of a file's actual bytes; None if the file is missing/unreadable — a missing
    input is reported as missing historical/current evidence, never silently skipped or
    guessed at. Named DISTINCTLY from the pre-existing _sha256_file (line 266, which raises
    on a missing file — an incompatible contract this new helper deliberately differs from)
    so it can never silently shadow that existing function for any other caller."""
    if not path:
        return None
    try:
        return _sha256_bytes(pathlib.Path(path).read_bytes())
    except Exception:
        return None


def _canon_json_bytes(obj):
    """Deterministic UTF-8 canonical JSON: sorted keys, stable (no whitespace-dependent)
    separators — the same structure always hashes to the same bytes, regardless of dict
    insertion order or json.dumps' default spacing."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _redesign_signature(components):
    """The one hashing function both old_signature and new_signature go through — SHA-256
    over the canonicalised component dict. Never Python's hash()."""
    return _sha256_bytes(_canon_json_bytes(components))


def _redesign_ref_slot_num(slot):
    try:
        return int(slot[2:])
    except Exception:
        return 10 ** 6


def _historical_redesign_components(led):
    """old_signature's inputs — EXCLUSIVELY from the sealed batch record of the most recent
    rejected batch (led["batch"] — reject_shot never clears led["batch"] itself, only the
    current-position pointers candidatePaths/batchId, so this still holds the last fired
    batch's own sealed envelope+disclosure at the moment a shot goes model-limited). NEVER
    reconstructed from mutable current package fields — every component here is read from
    that one historical, immutable record. Returns (components|None, missing_evidence).

    The keyframe/opening-anchor path is read from disclosure.openingAnchor — the exact
    anchor _anchor_for resolved at fire time — rather than guessed by reference-slot
    position: a shot's own referenceSlots is not guaranteed to declare an explicit
    "opening keyframe"/"previous shot final frame" role at all (found live building this
    very function's own test coverage — a real bug, fixed before it ever shipped), so
    assuming slot @图1 is always the anchor silently computed the wrong hash whenever that
    convention didn't hold. Falls back to a role-matched reference entry only if
    openingAnchor itself is missing from the historical record."""
    batch = led.get("batch") or {}
    envelope = batch.get("envelope")
    if not envelope:
        return None, ["no sealed provider-request envelope is on record for the previous "
                      "rejected batch — the historical evidence needed to compute "
                      "old_signature does not exist"]
    missing = []
    refs = envelope.get("references") or []
    if not refs:
        missing.append("the historical sealed envelope has no reference list recorded")
    refs_sorted = sorted(refs, key=lambda r: _redesign_ref_slot_num(r.get("slot", "")))
    anchor_path = (batch.get("disclosure") or {}).get("openingAnchor")
    if not anchor_path:
        anchor_ref = next((r for r in refs_sorted
                          if r.get("role") in ("opening keyframe", "previous shot final frame")),
                         None)
        anchor_path = anchor_ref.get("path") if anchor_ref else None
    keyframe_sha = _optional_sha256_file(anchor_path) if anchor_path else None
    if not keyframe_sha:
        missing.append("the historical batch record has no recoverable opening-anchor "
                       "path (disclosure.openingAnchor, or a role-matched reference), or "
                       "the file it names is missing on disk — cannot verify "
                       "old_signature's keyframe component")
    prompt = envelope.get("prompt")
    if not prompt:
        missing.append("the historical sealed envelope has no prompt recorded")
    audio = envelope.get("audio") or {}
    audio_path = audio.get("path")
    if audio_path:
        audio_sha = _optional_sha256_file(audio_path)
        if not audio_sha:
            missing.append(f"the historical audio asset ({audio_path}) is missing on "
                           f"disk — cannot verify old_signature's audio component")
    else:
        audio_sha = "NO_DIALOGUE"
    duration = envelope.get("durationSec")
    if duration is None:
        missing.append("the historical sealed envelope has no durationSec recorded")
    ref_mapping = {}
    for r in refs_sorted:
        slot = r.get("slot")
        sha = _optional_sha256_file(r.get("path"))
        if not sha:
            missing.append(f"historical reference {slot} ({r.get('role')}) is missing on "
                           f"disk — cannot verify old_signature's reference mapping")
        ref_mapping[slot] = {"role": r.get("role"), "sha256": sha}
    pkg_rev = envelope.get("packageRevision")
    if pkg_rev is None:
        missing.append("the historical sealed envelope has no packageRevision recorded")
    components = {"keyframeSha256": keyframe_sha, "animationPromptSha256": _sha256_text(prompt),
                  "audioSha256": audio_sha, "durationSec": duration,
                  "referenceMapping": ref_mapping, "packageRevision": pkg_rev}
    return components, missing


def _current_redesign_components(pkg, shot, scene, episode="Ep1"):
    """new_signature's inputs — built from the CURRENT, live-resolved approved state:
    the approved keyframe, the current+approved Animation Direction, the approved voice
    take (or NO_DIALOGUE if the shot carries none), the fire-time Handle Doctrine duration,
    the current canonical reference mapping, and the package revision. Every component is
    required to be CURRENT and APPROVED — a merely-generated-but-unapproved candidate is
    never a valid input here, matching this whole file's own standing anchor rule. Returns
    (components|None-fields-for-missing-parts, missing_evidence:list[str])."""
    led = _ledger(pkg, shot["shotId"])
    missing = []

    kf_appr = led.get("keyframeApproval")
    kf_path = kf_appr.get("path") if kf_appr and kf_appr.get("path") else None
    keyframe_sha = _optional_sha256_file(kf_path) if kf_path else None
    if not keyframe_sha:
        missing.append("no current APPROVED keyframe exists on disk for this shot")

    anim_prompt_sha = None
    try:
        _, anim_output = _require_approved_department(
            pkg, scene, "animation", shot["shotId"], episode,
            action_label=f"{shot['shotId']}'s redesign-signature check")
        anim_prompt_sha = _sha256_text(anim_output.get("providerPrompt"))
        # THE WORKING-OVERRIDE SIGNATURE FIX (2026-07-25, found live blocking Julian's own
        # hand-authored redesign test): the historical side hashes the sealed envelope's
        # ACTUAL fired prompt, so the current side must hash what would ACTUALLY fire now —
        # a saved working override replaces the approved output at fire time, and a director
        # rewriting the whole prompt by hand is the clearest possible "genuinely changed
        # input." Hashing only the approved department output made that invisible.
        working = led.get("workingSeedancePrompt")
        if working and (working.get("text") or "").strip():
            anim_prompt_sha = _sha256_text(working["text"].strip())
    except Refused as e:
        missing.append(f"Animation Direction is not currently approved: {e}")

    vo_path = None
    if shot.get("dialogueLines"):
        vo_appr = led.get("voiceApproval")
        vo_path = vo_appr.get("path") if vo_appr and vo_appr.get("approved") else None
        audio_sha = _optional_sha256_file(vo_path) if vo_path else None
        if not audio_sha:
            missing.append("no current APPROVED voice take exists on disk for this "
                           "dialogue shot")
    else:
        audio_sha = "NO_DIALOGUE"

    duration = _handle_duration(vo_path, shot.get("durationSec"))

    ref_mapping = None
    try:
        anchor = _anchor_for(pkg, shot)
        characters_cfg = _characters_cfg()
        imgs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, characters_cfg)
        img_slots = sorted((k for k in shot["referenceSlots"] if k.startswith("@图")),
                           key=lambda k: int(k[2:]))
        ref_mapping = {}
        for slot, p in zip(img_slots, imgs):
            sha = _optional_sha256_file(p)
            if not sha:
                missing.append(f"current reference {slot} ({shot['referenceSlots'][slot]}) "
                               f"is missing on disk")
            ref_mapping[slot] = {"role": shot["referenceSlots"][slot], "sha256": sha}
    except Refused as e:
        missing.append(f"current references cannot be resolved: {e}")

    components = {"keyframeSha256": keyframe_sha, "animationPromptSha256": anim_prompt_sha,
                  "audioSha256": audio_sha, "durationSec": duration,
                  "referenceMapping": ref_mapping, "packageRevision": pkg.get("revision")}
    return components, missing


def _shot_historical_spend(episode, shot_id):
    """Total logged spend across every candidate this shot has ever fired — the SAME
    cost_ledger.jsonl basename-prefix convention metrics() already uses, read-only, never
    invented when the ledger file doesn't exist (returns 0.0, a real total of zero entries,
    not None — this shot may simply never have logged a cost yet in this environment)."""
    total = 0.0
    lf = HERE / "cost_ledger.jsonl"
    if not lf.exists():
        return 0.0
    base = f"{episode}_{shot_id}_c"
    for line in open(lf):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        out = rec.get("out")
        if out and os.path.basename(str(out)).startswith(base):
            total += rec.get("cost_usd") or 0.0
    return round(total, 4)


def _canonical_json_hash(data):
    """Deterministic SHA-256 over CANONICAL JSON (sorted keys, stable compact separators)
    — pure serialization/formatting differences (key order, indentation, whitespace) never
    change this hash; only genuine content differences do. Distinct from the raw-byte md5
    _current_storyboard_md5/lineage_status already use — that existing mechanism is
    untouched by this function (still what _require_current_lineage's own working check
    enforces); this is new, additive evidence used only by revalidate_lineage_technical
    below, proving content equivalence rather than replacing the existing byte check."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ── PATH A — THE TECHNICAL-ONLY LINEAGE REVALIDATION (Julian's bounded lineage directive,
# 2026-07-21). Use ONLY once a structured field-level diff has already proven every real
# story/dialogue/beat/timing/performance/camera/character/reference/continuity field is
# UNCHANGED between the previously-approved storyboard snapshot and the live storyboard
# file — that classification decision belongs to the caller (or a human), never invented
# here; this function only trusts a supplied evidence-diff file's own recorded verdict.
def revalidate_lineage_technical(scene, episode="Ep1", evidence_diff_path=None,
                                 reviewed_by="Julian", log=print):
    """Preserves EVERYTHING that already exists in the package — the original Story &
    Direction content, its reviewer/approval timestamp/decision, the validated handover
    content, every media approval/rejection record, every cost record — untouched. Updates
    ONLY the canonical lineage binding the existing schema already reads
    (pkg["sourceStoryboard"]["md5"], the exact field _require_current_lineage checks) to
    the live storyboard file's current raw-byte md5, plus a new, additive
    canonicalLineageHash (sha256 over canonical JSON — immune to pure formatting/key-order
    drift, the "canonical SHA-256 lineage hash" Path A's own directive names). Appends one
    lineage-revalidation audit event. Atomic write, reread-and-verified before returning.
    Makes zero external calls, zero provider calls, zero LLM calls, zero spend.

    Refuses if: no live storyboard file exists; the lineage is already current (nothing to
    revalidate); or evidence_diff_path is supplied but its own recorded classification is
    not "Technical" (never trusts an unsupported claim of technical-only equivalence — a
    Semantic or Unresolved diff must go through human review, Path B, never this path)."""
    pkg, path = load_pkg(scene, episode)
    if not pkg.get("sourceStoryboard"):
        raise Refused(f"REFUSED — {scene}/{episode} package has no sourceStoryboard record; "
                      f"nothing to revalidate")
    old_md5 = pkg["sourceStoryboard"].get("md5")
    live_path = _storyboard_path(scene, episode)
    if not live_path.exists():
        raise Refused(f"REFUSED — no live storyboard file at {live_path.name}; cannot revalidate")
    if evidence_diff_path:
        try:
            evidence = json.load(open(evidence_diff_path))
        except Exception as e:
            raise Refused(f"REFUSED — evidence_diff_path {evidence_diff_path} could not be "
                          f"read/parsed: {e}")
        cls = evidence.get("overallClassification")
        if cls != "Technical":
            raise Refused(f"REFUSED — the supplied evidence diff's own recorded "
                          f"classification is {cls!r}, not 'Technical'; a Semantic or "
                          f"Unresolved mismatch must go through human review (Path B), "
                          f"never an automatic technical-only revalidation.")
    live_bytes = live_path.read_bytes()
    new_md5 = hashlib.md5(live_bytes).hexdigest()
    if old_md5 == new_md5:
        raise Refused(f"REFUSED — lineage is already current (md5 {new_md5[:8]}...); "
                      f"nothing to revalidate")
    new_canonical_hash = _canonical_json_hash(json.loads(live_bytes))
    audit = {
        "at": _now(), "reviewedBy": reviewed_by, "action": "lineage-revalidation",
        "oldLineageHash": old_md5, "newLineageHash": new_md5,
        "newCanonicalLineageHash": new_canonical_hash,
        "classification": "technical-only",
        "evidenceDiffPath": str(evidence_diff_path) if evidence_diff_path else None,
        "reason": ("a structured field-level diff proved every creative/story/dialogue/"
                   "beat/timing/performance/camera/character/reference/continuity field is "
                   "unchanged between the previously-approved storyboard snapshot and the "
                   "live storyboard file — only serialization/formatting or administrative "
                   "metadata differs. The Story & Direction content, its reviewer, approval "
                   "timestamp/decision, the validated handover, every media approval/"
                   "rejection record and every cost record are preserved untouched; only "
                   "the canonical lineage binding is updated to match the live file."),
    }
    pkg["sourceStoryboard"]["md5"] = new_md5
    pkg["sourceStoryboard"]["canonicalLineageHash"] = new_canonical_hash
    pkg.setdefault("lineageRevalidationLog", []).append(audit)
    _save(pkg, path)
    reread = json.load(open(path))
    assert reread["sourceStoryboard"]["md5"] == new_md5, "post-write reread verification failed"
    assert reread["lineageRevalidationLog"][-1] == audit, "post-write reread verification failed"
    log(f"LINEAGE REVALIDATED (technical-only) — {scene}/{episode}: "
        f"{(old_md5 or '')[:8]}... -> {new_md5[:8]}...; zero external calls.")
    return audit


def redesign_eligibility(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost, zero provider calls, zero LLM. The full eligibility check
    (§1 of Julian's directive), every condition evaluated and EVERY blocker reported
    together — never a partial refusal that hides a second problem behind the first:
      - the shot's current status is model-limited;
      - every candidate from the previous attempt cycle remains preserved+rejected;
      - a genuinely changed input package exists (new_signature != old_signature);
      - the changed keyframe/Animation Direction/audio/other required inputs are CURRENT
        and explicitly APPROVED (never a candidate, never a stale approval);
      - old_signature comes exclusively from the last rejected batch's sealed envelope;
      - no generation job or spend authorisation is currently pending on this shot.
    Returns a dict describing exactly what activation would show Julian (§3/§5), even when
    ineligible — the blockers list is the whole point of this function."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    blockers = []

    if led.get("status") != "model-limited":
        blockers.append(f"{shot_id}'s current status is '{led.get('status')}', not "
                        f"'model-limited' — this action only exists to recover from that "
                        f"exact hard stop, never a general reset")

    rejections = led.get("rejections") or []
    if not rejections:
        blockers.append("no rejection history is on record for this shot — there is no "
                        "previous attempt cycle to recover from")
    rejected_batch_ids = [r["batchId"] for r in rejections if r.get("batchId")]
    archived = list((HERE / "media" / "archive" / "shots_rejected")
                    .glob(f"{episode}_{shot_id}_*/REJECTED.json"))
    if len(archived) < len(rejections):
        blockers.append(f"only {len(archived)} of {len(rejections)} previous rejection(s) "
                        f"have a preserved archive on disk — the previous attempt cycle's "
                        f"evidence is incomplete")

    if led.get("pendingSpendAuth"):
        blockers.append("a spend authorisation is currently pending on this shot — "
                        "resolve it (fire with its token, or let a fresh disclosure "
                        "supersede it) before acknowledging a redesign")
    batch = led.get("batch") or {}
    if batch.get("status") == "generating":
        blockers.append("a generation job is currently in flight for this shot")

    old_components, old_missing = _historical_redesign_components(led)
    blockers.extend(old_missing)
    new_components, new_missing = _current_redesign_components(pkg, shot, scene, episode)
    blockers.extend(new_missing)

    old_sig = _redesign_signature(old_components) if old_components else None
    new_sig = _redesign_signature(new_components) if not new_missing else None

    changed_inputs = []
    if old_components and new_components and not new_missing:
        for key in ("keyframeSha256", "animationPromptSha256", "audioSha256",
                    "durationSec", "packageRevision"):
            if old_components.get(key) != new_components.get(key):
                changed_inputs.append(key)
        if old_components.get("referenceMapping") != new_components.get("referenceMapping"):
            changed_inputs.append("referenceMapping")
        if old_sig == new_sig:
            blockers.append("the current approved inputs are IDENTICAL to the last "
                            "rejected batch's own inputs (old_signature == new_signature) "
                            "— nothing has actually changed; re-firing an unchanged "
                            "package is exactly what the model-limited stop exists to "
                            "prevent")

    historical_spend = _shot_historical_spend(episode, shot_id)
    per_candidate_est = None
    try:
        import cb_costs
        key = _video_provider_rate_key(fast=False)
        cb_costs.RATES[key]
        per_candidate_est = round(
            cb_costs.estimate_video_cost(key, int(round(shot.get("durationSec") or HANDLE_TOTAL))), 4)
    except Exception:
        per_candidate_est = None

    return {"eligible": not blockers, "blockers": blockers,
            "oldSignature": old_sig, "newSignature": new_sig,
            "changedInputs": sorted(set(changed_inputs)),
            "previousCycleId": batch.get("batchId"),
            "rejectedBatchIds": rejected_batch_ids,
            "historicalSpendUsd": historical_spend,
            "nextCandidateLimit": REDESIGN_CANDIDATE_LIMIT,
            "nextCandidateEstimateUsd": per_candidate_est,
            "model": "bytedance/seedance-2.0",
            "durationSec": shot.get("durationSec")}


def acknowledge_redesign(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
    """THE ONLY WAY OUT OF MODEL-LIMITED (§3/§4). Re-runs redesign_eligibility in full and
    refuses with the complete blocker list unless every condition holds — never a generic
    reset/override/force-unlock. Makes ZERO provider calls, generates NOTHING, spends
    NOTHING: it appends one redesign-acknowledgement event (timestamp, reviewer, shot,
    previous/new cycle ids, old/new signature, changed-input summary, previous rejected
    batch ids, historical spend at acknowledgement, the one-candidate limit) and opens
    exactly one new attempt cycle. Every previous batch/rejection/review/cost-ledger entry
    and every generated/archived media file is left completely untouched — nothing here
    deletes, resets, renumbers or rewrites history; only led["status"]/["batchAttempts"]
    move, so the EXISTING fire_shot/reject_shot machinery (itself unchanged) can run again,
    with MAX_BATCH_ATTEMPTS now scoped to this fresh cycle rather than the shot's whole
    lifetime. Because cb_render.py's own _save() never touches pkg["revision"] (only
    cb_engine.py's promotion step does — confirmed by grep before this was written), this
    write cannot bump packageRevision and therefore cannot invalidate the very signature
    it just recorded as current."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    elig = redesign_eligibility(scene, shot_id, episode)
    if not elig["eligible"]:
        raise Refused("REFUSED — redesign acknowledgement is not available for "
                      f"{shot_id}:\n  - " + "\n  - ".join(elig["blockers"]))

    new_cycle_id = f"{shot_id}-redesign-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"
    event = {"at": _now(), "reviewedBy": reviewed_by, "shotId": shot_id,
             "previousCycleId": elig["previousCycleId"], "newCycleId": new_cycle_id,
             "oldSignature": elig["oldSignature"], "newSignature": elig["newSignature"],
             "changedInputs": elig["changedInputs"],
             "previousRejectedBatchIds": elig["rejectedBatchIds"],
             "historicalSpendUsdAtAcknowledgement": elig["historicalSpendUsd"],
             "nextCandidateLimit": REDESIGN_CANDIDATE_LIMIT}
    led.setdefault("redesignAcknowledgements", []).append(event)
    # opens exactly one new attempt cycle — batchAttempts resets to 0 WITHIN this cycle
    # (MAX_BATCH_ATTEMPTS now scoped per cycle, never the shot's permanent lifetime),
    # status returns to "designed" so the UNCHANGED fire_shot/reject_shot path can run
    # again. led["batch"]/led["rejections"] are NEVER touched here — every previous batch
    # and rejection stays exactly as it was, forever.
    led["status"] = "designed"
    led["batchAttempts"] = 0
    led["redesignCycle"] = {"cycleId": new_cycle_id, "candidateLimit": REDESIGN_CANDIDATE_LIMIT,
                            "openedAt": event["at"], "acknowledgedNewSignature": elig["newSignature"]}
    _save(pkg, path)
    log(f"REDESIGN ACKNOWLEDGED — {shot_id}: one new test cycle opened ({new_cycle_id}), "
        f"{REDESIGN_CANDIDATE_LIMIT} candidate permitted, zero cost incurred, zero "
        f"provider calls made. {len(elig['rejectedBatchIds'])} previously rejected "
        f"batch(es) and all cost history remain on record, untouched.")
    return event


# ── THE THREE-STOP LOOP (Julian's direct ruling, 2026-07-21 — "we have to take all the
# straightjackets off and allow the magic to be delivered, not flagged or straightjacketed"
# — following his prior turn's own framing: script -> storyboard -> keyframe -> Seedance
# prompt -> video -> edit, with exactly THREE places that need a human eye: the storyboard,
# the keyframe, the clip). Every mechanical gate below this line still exists and still
# protects real money and real state (nothing here removes _require_current_lineage,
# department source-hashing, the redesign-eligibility signature, or the one-render
# economy) — what changes is WHO resolves them. advance_shot resolves every one of them
# itself, silently, and only ever returns something for a human to look at when it's one
# of the three real creative moments.


def advance_shot(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print, _recursed=False):
    """Call this whenever a shot needs to move forward — the ONE function that replaces
    manually reasoning about lineage/department-freshness/redesign-eligibility as separate
    gates. It never spends real money on its own (rendering a clip still needs its own
    explicit, real fire_shot call with a confirmed spend token — real money is never
    silent) and it never approves a keyframe or a clip on your behalf — those two, plus the
    storyboard read, are the three moments that stay genuinely yours.

    Returns a dict with a "status" naming exactly what's true right now:
      - "needs-story-review"  — the storyboard itself needs your read (stop 1); nothing
                                  past it can move until you approve or send it back.
      - "needs-story-fix"     — the storyboard doesn't compile cleanly; the Producer/
                                  Director need to revise it — not a re-approval.
      - "needs-new-direction" — this shot failed twice on the SAME direction; nothing has
                                  genuinely changed, so it needs real creative revision,
                                  never an automatic retry on identical inputs.
      - "keyframe-ready-for-your-eye" — stop 2: a keyframe exists and is waiting on you.
      - "clip-ready-for-your-eye"     — stop 3: a candidate batch exists and is waiting on
                                  you (this function never fires one itself).
      - "ready-to-render"     — every mechanical gate is clear; the only remaining step is
                                  a real, explicit, spend-confirmed fire_shot call.
    Never raises for a condition it can resolve itself — only for something genuinely
    outside its own authority (e.g. no package exists at all, which load_pkg already
    raises Refused for)."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)

    # 1) LINEAGE — a stale package is a mechanical fact, never a creative decision.
    # Auto-recompile from the current, ALREADY-APPROVED storyboard; never refuse silently.
    lin = lineage_status(pkg, scene, episode)
    if not lin["current"]:
        sb_path = _storyboard_path(scene, episode)
        if not sb_path.exists():
            return {"status": "needs-story-review", "shotId": shot_id,
                    "reason": "no storyboard exists yet for this scene"}
        sb = json.load(open(sb_path))
        if sb.get("approvalState") != "approved":
            return {"status": "needs-story-review", "shotId": shot_id,
                    "reason": "the storyboard is waiting on your read — that's stop one"}
        import cb_handover
        shot_ids = [s["shotId"] for s in pkg.get("shots", []) if s.get("shotId")]
        try:
            new_pkg, archived = cb_handover.promote_to_canonical(
                str(sb_path), scene, shot_ids, episode, dry_run=False, log=log)
        except cb_handover.HandoverRefused as e:
            return {"status": "needs-story-review", "shotId": shot_id, "reason": str(e)}
        if not (new_pkg.get("validation") or {}).get("passed"):
            issues = [i for i in (new_pkg.get("validation") or {}).get("issues", [])
                     if i.get("severity") == "ERROR"]
            return {"status": "needs-story-fix", "shotId": shot_id,
                    "reason": "the current storyboard doesn't compile cleanly yet — this "
                              "needs the Producer/Director to revise it, not a re-approval",
                    "detail": issues[0]["message"] if issues else None}
        log(f"ADVANCE — {shot_id}: the storyboard had moved on since this package was "
            f"built; recompiled to revision {new_pkg.get('revision')} automatically.")
        pkg, path = load_pkg(scene, episode)
        shot = _shot(pkg, shot_id)

    # A shot already sitting at candidates-pending has ALREADY cleared every department —
    # a real batch could never have fired otherwise. Short-circuit straight to stop three
    # before touching anything else: department resolution below makes real specialist
    # calls, which must never run just to look at a shot that's already waiting on you.
    led = _ledger(pkg, shot_id)
    if led.get("status") == "candidates-pending":
        return {"status": "clip-ready-for-your-eye", "shotId": shot_id,
                "candidatePaths": led.get("candidatePaths")}

    def _auto_direction(stage):
        """Prepares + auto-approves a department DIRECTION only — never one of the three
        creative stops, so never surfaced as one. Returns True if it did anything."""
        status = department_status(scene, shot_id, episode, stage)
        r = status["readiness"]
        if not r["applicable"] or (r["directionCurrent"] and r["approvalCurrent"]):
            return False
        prepare_department(scene, stage, shot_id, episode, log=log)
        decide_department(scene, stage, "approved", shot_id,
                          note="on-story, on-bible — approved automatically as part of "
                               "the production line, not a separate creative stop",
                          episode=episode, reviewed_by="system", log=log)
        log(f"ADVANCE — {shot_id}: {stage} direction refreshed automatically.")
        return True

    # THE MODEL-LIMITED REDESIGN-LADDER BYPASS, CLOSED (2026-07-22, Julian's full-audit
    # directive — a real bug found live): redesign_eligibility (step 6 below) decides
    # whether a model-limited shot's block clears by comparing the LAST REJECTED batch's
    # captured signature against a freshly-computed "current" one — but _auto_direction can
    # itself refresh+auto-approve a department direction earlier in this SAME call (steps 2/
    # 4/5), which changes that very signature as a byproduct of THIS invocation, not a real,
    # independent creative change since the rejection. Comparing against a signature this
    # call just manufactured would let a same-call artifact silently clear
    # DECISION_LADDER's own "two failed batches -> human redesign, never more prompt-
    # patching" hard stop. Tracked here and checked before step 6 runs.
    any_direction_refreshed = False

    # 2) CINEMATOGRAPHY — an opener's own still-composition direction; a relay shot has none
    # (department_status reports it as not-applicable) and is skipped automatically.
    try:
        if _auto_direction("cinematography"):
            any_direction_refreshed = True
    except Refused as e:
        return {"status": "needs-department-input", "shotId": shot_id, "stage": "cinematography",
                "reason": str(e)}

    # 3) THE KEYFRAME — stop two, for an opener only. THIS MUST HAPPEN BEFORE ANIMATION IS
    # EVER PREPARED: Animation's own real prerequisite (_anchor_for) hard-requires an
    # APPROVED keyframe for an opener shot, and approving a keyframe is genuinely Julian's
    # own call — it can never be resolved automatically, so advance_shot must stop here
    # and return, not attempt to push an opener shot any further this call.
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if shot["sourceType"] == "opener":
        if led.get("keyframeCandidate"):
            return {"status": "keyframe-ready-for-your-eye", "shotId": shot_id,
                    "path": led["keyframeCandidate"]["path"]}
        if not (led.get("keyframeApproval") or {}).get("approved"):
            try:
                # THE KEYFRAME SPEND SEAL, AUTO-CONFIRMED HERE (2026-07-22, Julian's
                # keyframe-prompt-integrity directive): keyframe_shot now requires the same
                # disclose-then-confirm spend-token contract fire_shot's video route has
                # carried since 2026-07-16 (see keyframe_shot's/_keyframe_binding_hash's own
                # docstrings for the forensic reasoning). That seal's job is guaranteeing
                # WHAT'S DISCLOSED IS WHAT'S SENT — it was never meant to add a NEW human
                # pause before a keyframe fires; Julian's own 2026-07-21 ruling already
                # named the keyframe stop as "look at the resulting image," never "approve
                # the spend first" (unlike fire_shot's video route, the pipeline's one
                # genuinely large spend, which stays gated behind step 7's own separate,
                # explicit confirm below). Firing both halves back-to-back, in this same
                # call, with the same in-memory state, satisfies the seal's real security
                # property trivially (nothing can drift between disclosure and confirm) —
                # this is not a bypass of the seal, it's the seal doing its job silently
                # for a step that was always meant to be silent.
                out = _auto_confirm_keyframe(scene, shot_id, episode, log)
            except Refused as e:
                return {"status": "needs-department-input", "shotId": shot_id,
                        "reason": str(e)}
            return {"status": "keyframe-ready-for-your-eye", "shotId": shot_id, "path": out}

    # 4) VOICE — direction, THEN the actual take. Animation needs the take GENERATED AND
    # APPROVED (led["voiceApproval"]), not merely the direction approved — Julian never
    # named "listen to the voice take" as one of his three stops, and a real ElevenLabs
    # take costs cents, not dollars, so this resolves fully in the background exactly like
    # a department direction does, matching the real production order _seed_animation_
    # prereqs already establishes (prepare+approve direction, then voice_shot+approve_voice).
    try:
        if _auto_direction("voice"):
            any_direction_refreshed = True
    except Refused as e:
        return {"status": "needs-department-input", "shotId": shot_id, "stage": "voice",
                "reason": str(e)}
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if shot.get("dialogueLines") and not (led.get("voiceApproval") or {}).get("approved"):
        try:
            voice_shot(pkg, path, shot_id, episode, log=log)
            approve_voice(scene, shot_id, episode, reviewed_by="system", log=log)
            log(f"ADVANCE — {shot_id}: voice take generated and approved automatically.")
        except Refused as e:
            return {"status": "needs-department-input", "shotId": shot_id, "stage": "voice",
                    "reason": str(e)}

    # 5) ANIMATION — now genuinely unblocked: the keyframe (if this is an opener) is
    # approved, and the voice take (if this shot speaks) is generated and approved.
    try:
        if _auto_direction("animation"):
            any_direction_refreshed = True
    except Refused as e:
        return {"status": "needs-department-input", "shotId": shot_id, "stage": "animation",
                "reason": str(e)}

    # 6) MODEL-LIMITED — auto-clear it the instant the real inputs have genuinely changed;
    # never make a human click through a ceremony for something the system can already
    # tell is safe. If nothing has actually changed, this is a REAL creative wall, not a
    # straightjacket — retrying identical inputs cannot produce a different result.
    #
    # THE SAME-CALL SIGNATURE BYPASS, CLOSED (2026-07-22): redesign_eligibility compares the
    # last REJECTED batch's captured signature against a freshly-computed "current" one — if
    # any_direction_refreshed is True, that "current" signature may just be a byproduct of
    # THIS call's own steps 2/4/5 auto-refreshing a department direction moments ago, not a
    # real, independent creative change since the rejection. Evaluating it now would let a
    # same-call artifact silently clear DECISION_LADDER's hard stop. Instead, recurse ONCE
    # (guarded by _recursed) — the recursive call's own steps 2/4/5 will find everything
    # already current (no further refresh), so its step 6 compares against genuinely settled
    # state. This is never an infinite loop: _auto_direction only returns True on an actual
    # state change, and a state change is idempotent — the second pass can refresh nothing.
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    if led.get("status") == "model-limited" and any_direction_refreshed and not _recursed:
        log(f"ADVANCE — {shot_id}: a department direction was just refreshed automatically; "
            f"re-checking the model-limited block against settled state before deciding "
            f"whether it genuinely clears.")
        return advance_shot(scene, shot_id, episode, reviewed_by, log, _recursed=True)
    if led.get("status") == "model-limited":
        elig = redesign_eligibility(scene, shot_id, episode)
        if not elig["eligible"]:
            return {"status": "needs-new-direction", "shotId": shot_id,
                    "reason": "this shot failed twice on the same direction — nothing has "
                              "genuinely changed yet, so it needs real creative revision, "
                              "never an automatic retry", "blockers": elig["blockers"]}
        acknowledge_redesign(scene, shot_id, episode, reviewed_by=reviewed_by, log=log)
        log(f"ADVANCE — {shot_id}: the block cleared automatically — the real inputs had "
            f"genuinely changed since the last attempt.")
        pkg, path = load_pkg(scene, episode)
        led = _ledger(pkg, shot_id)

    # 7) THE FINAL STOP: a real, explicit, spend-confirmed fire_shot call is the only step
    # advance_shot never takes on its own — the biggest single spend in the pipeline stays
    # a genuine human decision, never silent.
    if led.get("status") == "candidates-pending":
        return {"status": "clip-ready-for-your-eye", "shotId": shot_id,
                "candidatePaths": led.get("candidatePaths")}
    return {"status": "ready-to-render", "shotId": shot_id}


def metrics(scene, episode="Ep1", log=print):
    """§7 — does the pipeline actually work? Per-scene production metrics from the ledger
    and cost ledger. The architecture is successful only if these improve over real
    production; a metric that cannot be computed is null, never invented."""
    pkg, _ = load_pkg(scene, episode)
    costs = {}
    lf = HERE / "cost_ledger.jsonl"
    if lf.exists():
        for line in open(lf):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("out"):
                costs.setdefault(os.path.basename(str(rec["out"])), 0.0)
                costs[os.path.basename(str(rec["out"]))] += rec.get("cost_usd") or 0.0
    approved, cand_total, batches, revisions, cats = 0, 0, 0, 0, {}
    approved_secs, approved_cost = 0.0, 0.0
    times = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        cand_total += led.get("candidatesGenerated", 0)
        batches += led.get("batchAttempts", 0) + (1 if led.get("status") in
                    ("candidates-pending", "approved") else 0)
        revisions += led.get("promptRevisions", 0)
        for r in led.get("rejections", []):
            cats[r.get("category", "other")] = cats.get(r.get("category", "other"), 0) + 1
        if led.get("status") == "approved":
            approved += 1
            approved_secs += float(s["durationSec"])
            base = f"{episode}_{s['shotId']}_c"
            approved_cost += sum(v for k, v in costs.items() if k.startswith(base))
            if led.get("firedAt") and (led.get("approval") or {}).get("at"):
                try:
                    t0 = datetime.datetime.fromisoformat(led["firedAt"])
                    t1 = datetime.datetime.fromisoformat(led["approval"]["at"])
                    times.append((t1 - t0).total_seconds())
                except Exception:
                    pass
    out = {"scene": str(scene), "at": _now(),
           "approvedShots": approved, "totalShots": len(pkg["shots"]),
           "candidatesGenerated": cand_total,
           "candidatesPerApprovedShot": round(cand_total / approved, 2) if approved else None,
           "costPerApprovedSecondUsd": round(approved_cost / approved_secs, 4)
               if approved_secs and approved_cost else None,
           "meanSecondsToApproval": round(sum(times) / len(times), 1) if times else None,
           "failureCategories": cats,
           "promptRevisions": revisions,
           "shotRedesigns": sum(1 for s in pkg["shots"]
                                 if _ledger(pkg, s["shotId"]).get("status") == "model-limited"),
           "identityFailures": cats.get("identity", 0),
           "continuityFailures": cats.get("geography", 0)}
    dest = HERE.parent / "cb-output" / f"{episode}_scene{scene}_metrics.json"
    json.dump(out, open(dest, "w"), indent=1)
    log(json.dumps(out, indent=1))
    return out


# ── Gate 9 handoff — the scene picture (cuts were designed; the join is a hard cut) ─────
def stitch_scene(scene, episode="Ep1", log=print):
    """JOIN ON LIVE MOTION (2026-07-21, checked and scoped specifically for THIS pipeline's
    own shot grammar — never a blind reuse of the old beat-pipeline's machinery): still a
    hard cut (Law: no in-scene dissolves), but with the tiny, universal edge-frame trim
    (cb_post.EDGE_FRAMES, ~4 frames/0.17s off every clip's opening ease-in and, for every
    clip but the last, its closing ease-out) instead of a raw frame-for-frame butt-join.

    Explicitly does NOT use cb_post.assemble_conformed's own settle_trim default
    (cb_post._settle_trim, reading the archived beat-pipeline's Handle Doctrine, ~2s) — that
    default assumes every clip carries a fixed settle-padding tail, a convention this
    pipeline's shots never had (cb_engine.MIN_SHOT_SEC/MAX_SHOT_SEC: 4-8s camera views, not
    15s padded beats). Trusting it here would cut real content — on a 4s shot, close to
    half of it. settle_trim is pinned to 0.0 explicitly, every call, so only the bounded,
    safe edge-frame polish ever applies, never a multi-second content trim.

    The raw, untrimmed butt-join is kept alongside as _shots_picture_RAW.mp4 — the
    deliberate comparison baseline, matching this codebase's own established convention for
    every other conformed/raw pair. Its own failure is logged, never fatal — it is evidence,
    not the primary output."""
    pkg, path = load_pkg(scene, episode)
    clips, missing = [], []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        if led.get("status") == "approved" and led.get("approvedTake"):
            clips.append(led["approvedTake"])
        else:
            missing.append(s["shotId"])
    if missing:
        raise Refused(f"REFUSED — cannot stitch scene {scene}: unapproved shots {missing}")
    out = HERE / "media" / f"{episode}_Scene{scene}_shots_picture.mp4"
    if len(clips) > 1:
        raw_out = HERE / "media" / f"{episode}_Scene{scene}_shots_picture_RAW.mp4"
        if not cb_post.assemble_picture(clips, str(raw_out)):
            log(f"STITCH — raw comparison baseline failed for scene {scene} (non-fatal, "
                f"see ffmpeg output above); continuing with the conformed join")
        result = cb_post.assemble_conformed(clips, str(out), settle_trim=0.0)
    else:
        result = cb_post.assemble_picture(clips, str(out))
    if not result:
        raise Refused("stitch failed — see ffmpeg output above")
    log(f"STITCH — scene {scene}: {len(clips)} approved shots -> {out.name} "
        f"(cb_post mix/captions/masters take it from here)")
    return str(out)


def evidence_pack(scene, episode="Ep1", log=print):
    """THE EVIDENCE PACK (Julian's cutover directive, 2026-07-16): for every shot, one
    record of input → compiled instruction → provider request → returned assets → state
    transitions → costs → approvals → harvested frame — plus the stitched output. Written
    to cb-output/{episode}_scene{scene}_evidence/ as JSON + a readable index.md. Collects
    only what exists; missing pieces are named MISSING, never invented."""
    pkg, _ = load_pkg(scene, episode)
    out_dir = HERE.parent / "cb-output" / f"{episode}_scene{scene}_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    # cost entries, keyed by output filename (cb_gen logs every paid call with out=)
    costs = {}
    ledger_file = HERE / "cost_ledger.jsonl"
    if ledger_file.exists():
        for line in open(ledger_file):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            key = os.path.basename(str(rec.get("out") or ""))
            if key:
                costs.setdefault(key, []).append(rec)

    def _asset(p):
        if not p:
            return None
        exists = os.path.exists(p)
        entry = {"path": p, "exists": exists,
                 "bytes": os.path.getsize(p) if exists else None}
        side = p + ".gen.json"
        if os.path.exists(side):
            try:
                entry["providerRequest"] = json.load(open(side))
            except Exception:
                entry["providerRequest"] = "unreadable sidecar"
        entry["costEntries"] = costs.get(os.path.basename(p), [])
        return entry

    def _seedance_prompt_for_evidence(s):
        # THE CORE LAW (2026-07-19): this is a READ-ONLY forensic report — it must show
        # what WOULD be submitted right now, never crash the whole pack because one shot
        # has no approved Animation Direction yet. A blocked shot is reported as MISSING
        # with the exact refusal reason, matching this pack's own stated convention
        # ("missing pieces are named MISSING, never invented").
        try:
            return _resolve_seedance_prompt(pkg, s, scene, episode, allow_auto_heal=False)[0]
        except DepartmentNotApproved as e:
            return f"MISSING — {e}"

    def _keyframe_prompt_for_evidence(s):
        # Same discipline as above, for the Cinematography/keyframe route: a relay shot
        # correctly returns None (no keyframe of its own, by design); an opener shot with
        # no current approved Cinematography direction is reported as MISSING, never a crash.
        try:
            return _resolve_keyframe_prompt(pkg, s, scene, episode, allow_auto_heal=False)
        except DepartmentNotApproved as e:
            return f"MISSING — {e}"

    cases = []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        take = led.get("approvedTake") or (led.get("candidatePaths") or [None])[0]
        review = None
        if take and os.path.exists(str(take) + ".review.json"):
            review = json.load(open(str(take) + ".review.json"))
        cases.append({
            "shotId": s["shotId"], "sourceType": s["sourceType"],
            "sourceShotId": s.get("sourceShotId"),
            "input": {"beatCode": s["beatCode"], "purpose": s["purpose"],
                       "dialogueLines": s.get("dialogueLines") or [],
                       "openingPose": s["openingPose"]},
            "compiledInstruction": {"seedancePrompt": _seedance_prompt_for_evidence(s),
                                     "promptWords": s["promptWords"],
                                     "referenceSlots": s["referenceSlots"],
                                     "keyframePrompt": _keyframe_prompt_for_evidence(s),
                                     "audioBrief": s.get("audioBrief")},
            "assets": {"voice": _asset(led.get("voPath")),
                        "keyframe": _asset((led.get("keyframeApproval") or {}).get("path")
                                            or led.get("keyframePath")),
                        "candidates": [_asset(c) for c in (led.get("candidatePaths") or [])],
                        "take": _asset(led.get("approvedTake")),
                        "harvestFrame": _asset(led.get("harvestFrame"))},
            "state": {"status": led.get("status"),
                       "batchAttempts": led.get("batchAttempts", 0),
                       "candidatesGenerated": led.get("candidatesGenerated", 0),
                       "disclosure": led.get("disclosure"),
                       "approval": led.get("approval"),
                       "rejections": led.get("rejections") or [],
                       "machineReview": review,
                       "departmentWork": led.get("departmentWork") or {}},
        })

    stitched = HERE / "media" / f"{episode}_Scene{scene}_shots_picture.mp4"
    animatic = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    if not animatic.exists():   # the pre-reclassification name (the frozen 2026-07-16 slate)
        animatic = HERE / "media" / f"{episode}_Scene{scene}_animatic.mp4"
    pack = {"episode": episode, "scene": str(scene), "generatedAt": _now(),
            "validation": pkg.get("validation"),
            "shots": cases,
            "timingSlate": _asset(str(animatic)) if animatic.exists() else None,
            "stitchedOutput": _asset(str(stitched)) if stitched.exists() else None}
    json.dump(pack, open(out_dir / "evidence.json", "w"), indent=1, ensure_ascii=False)

    md = [f"# Evidence pack — {episode} scene {scene} ({_now()})",
          f"Design validation: {'PASSED' if (pkg.get('validation') or {}).get('passed') else 'FAILED'}\n"]
    for c in cases:
        st = c["state"]
        md.append(f"## {c['shotId']} · {c['sourceType']}"
                  + (f" ← {c['sourceShotId']}" if c["sourceShotId"] else ""))
        md.append(f"- status: **{st['status'] or 'designed'}**"
                  + (f" · approved by {st['approval']['reviewed_by']} at {st['approval']['at']}"
                     if st.get("approval") else "")
                  + (f" · rejected: “{st['rejection']['correction']}”" if st.get("rejection") else ""))
        for k, a in c["assets"].items():
            if k == "candidates":
                present = [x for x in (a or []) if x and x.get("exists")]
                md.append(f"- candidates: {len(present)} pending" if present
                          else "- candidates: none pending (selected/archived or not fired)")
                continue
            md.append(f"- {k}: " + ("MISSING" if not a else
                      f"`{os.path.basename(a['path'])}` ({a['bytes']} bytes)"
                      + (f" · £-logged {len(a['costEntries'])} cost entr(y/ies)" if a["costEntries"] else "")
                      + (" · provider request recorded" if a.get("providerRequest") else "")))
        notes = (st.get("machineReview") or {}).get("machineNotes")
        if notes:
            md.append(f"- machine notes: {'; '.join(notes)}")
        md.append("")
    md.append(f"Stitched output: "
              + (f"`{os.path.basename(str(stitched))}`" if stitched.exists() else "MISSING"))
    (out_dir / "index.md").write_text("\n".join(md))
    log(f"EVIDENCE — {out_dir.name}/evidence.json + index.md ({len(cases)} shots)")
    return str(out_dir)


def status(scene, episode="Ep1", log=print):
    pkg, _ = load_pkg(scene, episode)
    lin = lineage_status(pkg, scene, episode)
    rows = [f"LINEAGE — package revision {lin['packageRevision']}: "
            f"{'CURRENT' if lin['current'] else 'STALE (superseded storyboard version)'}"]
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        kf = ("approved" if led.get("keyframeApproval") else
              "awaiting" if led.get("keyframeCandidate") else
              "rejected" if led.get("keyframeRejected") else "-")
        rows.append(f"{s['shotId']:<10} {s['sourceType']:<7} {led.get('status','designed'):<18} "
                    f"vo={'y' if led.get('voPath') else '-'} "
                    f"kf={kf} "
                    f"cands={len(led.get('candidatePaths') or [])} "
                    f"batches={led.get('batchAttempts', 0)} "
                    f"harvest={'y' if led.get('harvestFrame') else '-'}")
    log("\n".join(rows))
    return rows


if __name__ == "__main__":
    os.chdir(HERE)
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    try:
        # shared flags: --candidates N (1-4), --approve-spend, --category X
        flags = {"candidates": DEFAULT_CANDIDATES, "spend_token": None, "category": "other",
                 "dry_run": False, "resolution": "720p"}
        pos = []
        i = 1
        while i < len(args):
            a = args[i]
            if a == "--candidates":
                flags["candidates"] = int(args[i + 1]); i += 2
            elif a == "--spend-token":
                flags["spend_token"] = args[i + 1]; i += 2
            elif a == "--category":
                flags["category"] = args[i + 1]; i += 2
            elif a == "--dry-run":
                flags["dry_run"] = True; i += 1
            elif a == "--resolution":
                # THE RESOLUTION CHOICE, THREADED THROUGH THE CLI (2026-07-23, Studio wiring):
                # fire_shot has carried resolution= since the 480p test-tier rate landed in
                # cb_costs/_video_provider_rate_key — this flag only exposes that existing
                # parameter to the Studio's subprocess route. The binding hash/sealed envelope
                # already cover resolution, so a token disclosed at one resolution can never
                # silently fire at another (that machinery is untouched here).
                flags["resolution"] = args[i + 1]; i += 2
            else:
                pos.append(a); i += 1
        ep = lambda n: pos[n] if len(pos) > n else "Ep1"
        if cmd == "voice":
            voice_scene(pos[0], ep(1))
        elif cmd in ("animatic", "slate"):
            animatic_scene(pos[0], ep(1))
        elif cmd == "scenelook":
            generate_scenelook_plate(pos[0], ep(1),
                                     reference_path=(pos[2] if len(pos) > 2 else None))
        elif cmd == "approve-scenelook":
            approve_scenelook(pos[0], ep(1))
        elif cmd == "reject-scenelook":
            reject_scenelook(pos[0], pos[1], episode=ep(2))
        elif cmd == "unapprove-scenelook":
            unapprove_scenelook(pos[0], ep(1))
        elif cmd == "scenelook-library":
            print(json.dumps(scenelook_reference_library(pos[0], ep(1)), indent=1))
        elif cmd == "select-scenelook-upload":
            select_scenelook_source(pos[0], "upload", ep(2), upload_path=pos[1])
        elif cmd == "select-scenelook-library":
            select_scenelook_source(pos[0], "library", ep(2), library_path=pos[1])
        elif cmd == "keyframe":
            keyframe_shot(pos[0], pos[1], ep(2), spend_token=flags["spend_token"],
                          dry_run=flags["dry_run"])
        elif cmd == "unapprove-keyframe":
            unapprove_keyframe(pos[0], pos[1], ep(2))
        elif cmd == "approve-keyframe":
            approve_keyframe(pos[0], pos[1], ep(2))
        elif cmd == "reject-keyframe":
            reject_keyframe(pos[0], pos[1], pos[2], episode=ep(3))
        elif cmd == "keyframe-library":
            print(json.dumps(keyframe_library_for_shot(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "select-upload":
            select_keyframe_source(pos[0], pos[1], "upload", ep(3), upload_path=pos[2])
        elif cmd == "select-library":
            select_keyframe_source(pos[0], pos[1], "library", ep(3), library_path=pos[2])
        elif cmd == "select-previous":
            select_keyframe_source(pos[0], pos[1], "previousFinalFrame", ep(2))
        elif cmd == "voice-status":
            print(json.dumps(voice_performance_status(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "save-voice":
            save_voice_working(pos[0], pos[1], json.loads(pos[2]), episode=ep(3))
        elif cmd == "restore-voice":
            restore_voice_working(pos[0], pos[1], episode=ep(2))
        elif cmd == "restore-voice-take":
            restore_previous_voice_take(pos[0], pos[1], episode=ep(2))
        elif cmd == "regen-voice":
            regen_voice_shot(pos[0], pos[1], episode=ep(2))
        elif cmd == "unapprove-voice":
            unapprove_voice(pos[0], pos[1], ep(2))
        elif cmd == "approve-voice":
            approve_voice(pos[0], pos[1], ep(2))
        elif cmd == "reject-voice":
            reject_voice(pos[0], pos[1], pos[2], episode=ep(3))
        elif cmd == "seedance-status":
            print(json.dumps(seedance_working_status(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "save-seedance":
            save_seedance_working(pos[0], pos[1], pos[2], episode=ep(3))
        elif cmd == "restore-seedance":
            restore_seedance_working(pos[0], pos[1], episode=ep(2))
        elif cmd == "check-structure":
            print(json.dumps(check_seedance_structure(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "department-prepare":
            prepare_department(pos[0], pos[1], None if pos[2] == "-" else pos[2], ep(3))
        elif cmd == "department-status":
            print(json.dumps(department_status(pos[0], None if pos[2] == "-" else pos[2],
                                               ep(3), pos[1]), indent=1))
        elif cmd == "next":
            next_shot(pos[0], ep(1), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"],
                       resolution=flags["resolution"])
        elif cmd == "fire":
            fire_shot(pos[0], pos[1], ep(2), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"],
                       resolution=flags["resolution"])
        elif cmd == "unapprove-shot":
            unapprove_shot(pos[0], pos[1], ep(2))
        elif cmd == "approve":
            approve_shot(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1, ep(3))
        elif cmd == "reject":
            reject_shot(pos[0], pos[1], pos[2], category=flags["category"], episode=ep(3))
        elif cmd == "redesign-eligibility":
            print(json.dumps(redesign_eligibility(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "acknowledge-redesign":
            acknowledge_redesign(pos[0], pos[1], ep(2))
        elif cmd == "stitch":
            stitch_scene(pos[0], ep(1))
        elif cmd == "advance":
            # THE THREE-STOP LOOP'S FRONT DOOR (Julian's ruling, 2026-07-21 — "take all the
            # straightjackets off and allow the magic to be delivered, not flagged or
            # straightjacketed"): resolves every mechanical gate on its own and prints
            # exactly what (if anything) needs a human's eye, as one JSON line the Studio's
            # job log parses — see cb-studio/serve.py's SHOT_CMDS and app.html's shJobHTML.
            print(json.dumps(advance_shot(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "status":
            status(pos[0], ep(1))
        elif cmd == "metrics":
            metrics(pos[0], ep(1))
        elif cmd == "evidence":
            evidence_pack(pos[0], ep(1))
        elif cmd == "audit":
            findings = audit_shot_integrity(pos[0], ep(1))
            sys.exit(1 if findings else 0)
        else:
            print(f"unknown command {cmd}"); sys.exit(1)
    except Refused as e:
        print(str(e)); sys.exit(1)
