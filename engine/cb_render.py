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
    python3 cb_render.py metrics  <scene> [episode]
    python3 cb_render.py stitch   <scene> [episode]
    python3 cb_render.py status   <scene> [episode]
"""
import os, sys, json, re, glob, pathlib, datetime, shutil, hashlib, uuid, subprocess, tempfile, threading
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_engine
import cb_gen
import cb_post
import cb_departments
import cb_lineage
import cb_scripts
import cb_db
import cb_providers
import paths as P

MEDIA = HERE / "media" / "shots"
ROOT = HERE.parent
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)
DUR_TOLERANCE_SEC = 1.5          # rendered clip may differ from designed duration by this much


class Refused(RuntimeError):
    """A named, deliberate refusal — never a crash, never a silent skip."""


def _require_show_adapter():
    if P.ENGINE_ADAPTER != "crystal-bears-v1":
        raise Refused(
            f"REFUSED — show adapter {P.ENGINE_ADAPTER!r} is not supported by the "
            "Crystal Bears production runtime; no provider was contacted")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _norm(s):
    return re.sub(r"[^a-z0-9']+", " ", (s or "").lower().replace("’", "'")).strip()


# ── package + ledger ────────────────────────────────────────────────────────────────────
_PACKAGE_SNAPSHOTS = {}


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
    pkg, digest = cb_db.read_json_document(HERE.parent, p)
    _PACKAGE_SNAPSHOTS[id(pkg)] = (pkg, digest)
    return pkg, p


def _save(pkg, path):
    snapshot = _PACKAGE_SNAPSHOTS.get(id(pkg))
    expected = snapshot[1] if snapshot and snapshot[0] is pkg else None
    try:
        digest = cb_db.atomic_write_json(HERE.parent, path, pkg, expected_digest=expected)
    except cb_db.StateConflict as exc:
        raise Refused(f"REFUSED — {exc}; reload the scene and retry") from exc
    _PACKAGE_SNAPSHOTS[id(pkg)] = (pkg, digest)


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
    """Return authoritative source-graph freshness for a production package."""
    pkg_md5 = (pkg.get("sourceStoryboard") or {}).get("md5")
    live_md5 = _current_storyboard_md5(scene, episode)
    storyboard_current = bool(pkg_md5) and bool(live_md5) and pkg_md5 == live_md5
    package_script = (pkg.get("sourceScript") or {}).get("scriptVersionId")
    current_script = None
    script_current = False
    script_error = None
    try:
        current = SCRIPT_STORE.current(episode, required=True)
        current_script = current["scriptVersionId"]
        script_current = (package_script == current_script and
                          (pkg.get("sourceScript") or {}).get("sha256") == current["sha256"])
    except (cb_scripts.ScriptStoreError, cb_lineage.LineageError) as exc:
        script_error = str(exc)

    package_signature = pkg.get("inputSignature") or {}
    package_inputs = package_signature.get("inputs") or {}
    signature_current = (
        cb_lineage.signature_matches(package_signature, "production-package", package_inputs) and
        package_inputs.get("scriptVersionId") == current_script and
        package_inputs.get("storyboardSha256") ==
        (pkg.get("sourceStoryboard") or {}).get("sha256") and
        (not _storyboard_path(scene, episode).exists() or
         package_inputs.get("storyboardSha256") ==
         cb_lineage.sha256_file(_storyboard_path(scene, episode)))
    )
    reasons = []
    if not script_current:
        reasons.append("script-version-mismatch")
    if not storyboard_current:
        reasons.append("storyboard-content-mismatch")
    if not signature_current:
        reasons.append("production-signature-mismatch")
    return {"current": script_current and storyboard_current and signature_current,
            "scriptCurrent": script_current, "storyboardCurrent": storyboard_current,
            "signatureCurrent": signature_current, "reasonCodes": reasons,
            "packageScriptVersionId": package_script,
            "currentScriptVersionId": current_script, "scriptError": script_error,
            "packageStoryboardMd5": pkg_md5, "liveStoryboardMd5": live_md5,
            "packageRevision": pkg.get("revision")}


def _require_current_lineage(pkg, scene, episode):
    """HARD REFUSAL, same tier as _require_valid: a package bound to a superseded storyboard
    version can generate nothing new. Fixing this requires recompiling the package from the
    current approved storyboard — a deliberate, separate action, never silently done here."""
    lin = lineage_status(pkg, scene, episode)
    if not lin["current"]:
        raise Refused(
            f"REFUSED — production package revision {lin['packageRevision']} is stale "
            f"({', '.join(lin['reasonCodes'])}). Package script "
            f"{str(lin['packageScriptVersionId'])[:20]} does not form a verified current graph "
            f"with script {str(lin['currentScriptVersionId'])[:20]} and the live storyboard. "
            "Rebuild and approve Story & Direction, then promote it before generating anything.")


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
    if not st["current"]:
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
    truncated on the way to cb_gen."""
    st = scenelook_status(scene, episode)
    if st["candidate"]:
        raise Refused(f"REFUSED — scene {scene} already has a Scene Look candidate awaiting "
                      f"a decision; reject it first, or approve it, before generating another")
    if reference_path is not None and not pathlib.Path(reference_path).exists():
        raise Refused(f"REFUSED — reference_path does not exist: {reference_path}")
    prompt = approved_look_prompt(scene, episode)
    if not prompt:
        raise Refused("REFUSED — Approve Look Development direction first.")
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
    slots = shot.get(slots_key) or {}
    for slot in sorted((k for k in slots if k.startswith("@图")),
                       key=lambda k: int(k[2:])):
        role = slots[slot]
        if role in ("opening keyframe", "previous shot final frame"):
            out.append(anchor_path)
        elif role == "scene plate":
            out.append(_plate_path(scene, episode))
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
    "animation": ("Animation", "Seedance Production Director", "seedance-production-director"),
    "review-keyframe": ("Director Review", "Director Review / Continuity Supervisor", "continuity"),
    "review-animation": ("Director Review", "Director Review / Continuity Supervisor", "continuity"),
    "review-final": ("Final & Post", "Post Supervisor", "post"),
}


def _department_skill_ref(stage, skill):
    if stage == "animation":
        return "skills/seedance-production-director/SKILL.md"
    return f"skills/crystal-bears-{skill}/SKILL.md"


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
        return {"stage": stage, "department": dep, "worker": worker,
                "skill": ("seedance-production-director" if stage == "animation"
                          else f"crystal-bears-{skill}"), **work}
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


def _shot_context(pkg, shot, led, scene, episode):
    return {"episode": episode, "scene": str(scene), "shot": shot,
            "approvedSceneLook": scenelook_status(scene, episode).get("approved"),
            "currentVoiceDirection": (led.get("departmentWork", {}).get("voice", {})
                                      .get("approved")),
            "humanWorkingVoice": led.get("workingVoice"),
            "humanWorkingAnimationPrompt": led.get("workingSeedancePrompt")}


def _department_candidate(stage, output, context):
    dep, worker, skill = _DEPARTMENT_WORKERS[stage]
    return {"department": dep, "worker": worker,
            "skill": _department_skill_ref(stage, skill),
            "model": cb_departments.cb_llm.DIRECTOR_MODEL,
            "preparedAt": _now(), "editedAt": None, "preparedBy": "specialist",
            "sourceHash": hashlib.sha256(json.dumps(context, sort_keys=True,
                                                       ensure_ascii=False).encode()).hexdigest(),
            "output": output}


def _review_frames(video_path, max_frames=4):
    """Extract up to six chronological frames for the real vision review call."""
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="cb-review-"))
    pattern = tmp / "frame_%02d.jpg"
    proc = subprocess.run(["ffmpeg", "-y", "-i", str(video_path), "-vf",
                           "fps=1/2,scale=960:-2", "-frames:v", str(max_frames), str(pattern)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(f"REFUSED — could not extract review frames from {video_path}: "
                      f"{proc.stderr[-240:]}")
    frames = sorted(tmp.glob("frame_*.jpg"))
    if not frames:
        shutil.rmtree(tmp, ignore_errors=True)
        raise Refused(f"REFUSED — no visible frames could be extracted from {video_path}")
    return tmp, [str(p) for p in frames]


def prepare_department(scene, stage, shot_id=None, episode="Ep1", log=print):
    """Run one real specialist once and store an awaiting-approval candidate.

    Existing approved work and every media asset remain untouched if the call fails or a
    replacement candidate is prepared.  No cb_gen function is reachable from this path.
    """
    if stage not in _DEPARTMENT_WORKERS:
        raise Refused(f"REFUSED — unknown department stage '{stage}'")
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    if work.get("candidate"):
        raise Refused(f"REFUSED — {stage} already has work awaiting a decision")

    temp_dir = None
    if stage == "look":
        context = _scene_context(pkg, scene, episode)
        result = cb_departments.prepare_look(context, log=log)
    elif stage == "review-final":
        post = post_status(pkg, scene, episode)
        selected = (post["candidate"] if post["candidate"]["current"] else
                    post["approved"] if post["approved"]["current"] else None)
        if selected is None:
            reason = post["candidate"].get("reason") if post["candidate"]["exists"] else "missing"
            raise Refused(
                f"REFUSED — no current QC-passed post master exists for scene {scene} "
                f"to review ({reason})")
        manifest = selected["manifest"]
        media = pathlib.Path(manifest["outputs"]["master16x9"]["path"])
        temp_dir, frames = _review_frames(str(media), 6)
        try:
            context = {**_scene_context(pkg, scene, episode), "shots": pkg.get("shots") or [],
                       "postManifest": manifest,
                       "postQc": manifest.get("qc"),
                       "orderedReviewImages": [
                           {"role": f"actual mastered-scene frame {i+1}", "path": p}
                           for i, p in enumerate(frames)]}
            result = cb_departments.review_media("final", context, frames, log=log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        shot = _shot(pkg, shot_id)
        led = _ledger(pkg, shot_id)
        context = _shot_context(pkg, shot, led, scene, episode)
        if stage == "cinematography":
            chars = _characters_cfg()
            slots = shot.get("keyframeReferenceSlots") or {}
            images = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, chars)
            context["orderedAttachments"] = [
                {"slot": k, "role": slots[k], "path": p}
                for k, p in zip(sorted((k for k in slots if k.startswith("@图")),
                                       key=lambda k: int(k[2:])), images)]
            result = cb_departments.prepare_cinematography(context, images, log=log)
        elif stage == "voice":
            result = cb_departments.prepare_voice(context, shot.get("dialogueLines") or [], log=log)
        elif stage == "animation":
            if not (led.get("voiceApproval") or {}).get("approved") and shot.get("dialogueLines"):
                raise Refused(f"REFUSED — {shot_id}'s approved voice is required before the "
                              "Animation Director enters")
            anchor = _anchor_for(pkg, shot)
            images = _slot_paths(shot, "referenceSlots", anchor, scene, episode, _characters_cfg())
            context["orderedAttachments"] = [
                {"slot": k, "role": shot["referenceSlots"][k], "path": p}
                for k, p in zip(sorted((k for k in shot["referenceSlots"] if k.startswith("@图")),
                                       key=lambda k: int(k[2:])), images)]
            context["approvedVoiceAsset"] = led.get("voPath")
            result = cb_departments.prepare_animation(context, images, log=log)
            rp = _norm(result.providerPrompt)
            for ln in shot.get("dialogueLines") or []:
                locked = _norm(ln["exactText"])
                if len(locked.split()) >= 2 and locked in rp:
                    raise Refused(f"REFUSED — Animation Director leaked spoken words into "
                                  f"the visual prompt ({ln['exactText']}); no candidate saved")
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
            media_paths = (
                [led["approvedTake"]]
                if led.get("status") == "approved" and led.get("approvedTake")
                else list(led.get("candidatePaths") or [])
            )
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

    work["candidate"] = _department_candidate(stage, result.model_dump(), context)
    save_extra()
    _save(pkg, path)
    log(f"DEPARTMENT — {work['candidate']['worker']} prepared {stage} work for "
        f"{shot_id or 'scene '+str(scene)} (awaiting Julian; no media generated)")
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
            p = _norm(value)
            for ln in shot.get("dialogueLines") or []:
                t = _norm(ln["exactText"])
                if len(t.split()) >= 2 and t in p:
                    raise Refused(f"REFUSED — spoken words belong in @Audio1, not the "
                                  f"animation prompt (found: {ln['exactText']})")
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
    if stage == "review-final":
        post = pkg.setdefault("postProduction", {"candidate": None, "approved": None,
                                                  "history": []})
        candidate = post.get("candidate")
        if candidate:
            state = post_status(pkg, scene, episode)["candidate"]
            if not state["current"]:
                raise Refused(
                    f"REFUSED — post candidate is stale ({state['reason']}); rebuild before decision")
            if verdict == "approved":
                if post.get("approved"):
                    post.setdefault("history", []).append({**post["approved"],
                                                            "outcome": "superseded",
                                                            "supersededAt": _now()})
                post["approved"] = {**candidate, "approvedAt": _now(),
                                     "approvedBy": reviewed_by,
                                     "finalReviewNote": str(note or "").strip()}
            else:
                post.setdefault("history", []).append({**candidate, "outcome": "rejected",
                                                        "rejectedAt": _now(),
                                                        "rejectedBy": reviewed_by,
                                                        "rejectionNote": str(note or "").strip()})
            post["candidate"] = None
    save_extra(); _save(pkg, path)
    # A dailies decision is also governed learning evidence. Preserve the complete structured
    # diagnosis and the human's decision, but never activate it as a rule or alter a prompt.
    if stage.startswith("review-"):
        try:
            import cb_learning
            review = event.get("output") or {}
            cb_learning.capture_evidence(
                "approved" if verdict == "approved" else "rejected",
                event["note"], episode=episode, scene=scene, shot=shot_id,
                role="Director Review / Continuity Supervisor",
                sourceVersion=pkg.get("revision"), category="dailies", scope="shot",
                classification=str(review.get("likelyRootCause") or "unclassified"),
                context=json.dumps({
                    "artifactType": review.get("artifactType"),
                    "verdict": review.get("verdict"),
                    "intendedRead": review.get("intendedRead"),
                    "actualRead": review.get("actualRead"),
                    "rootCauseReasoning": review.get("rootCauseReasoning"),
                    "cheapestNextAction": review.get("cheapestNextAction"),
                    "learningTags": review.get("learningTags") or [],
                }, ensure_ascii=False),
                assetPointers=[x for x in (
                    (event.get("context") or {}).get("orderedReviewImages") or [])
                               if isinstance(x, dict)],
                capturedBy=reviewed_by)
        except Exception as e:
            log(f"LEARNING CAPTURE WARNING — review decision saved, evidence capture failed: {e}")
    log(f"DEPARTMENT {verdict.upper()} — {stage} by {reviewed_by} (no media generated)")
    return event


def _approved_department_output(pkg, shot_id, stage):
    led = _ledger(pkg, shot_id)
    return (((led.get("departmentWork") or {}).get(stage) or {}).get("approved") or {}).get("output")


def _resolve_keyframe_prompt(pkg, shot):
    """A relay/non-opener shot legitimately has no keyframePrompt at all (it opens off its
    source shot's harvested final frame, never its own keyframe — keyframe_shot itself
    refuses to generate one) — returns None for that shot rather than crashing. Every real
    caller either already guards sourceType=="opener" first (keyframe_shot/regen paths) or
    is a read-only report over EVERY shot (evidence_pack) that must tolerate a relay shot's
    honest "no keyframe prompt" the same way it already tolerates a silent shot's "no voice
    track" — a missing value here is the truthful record, never a gap to paper over."""
    work = _approved_department_output(pkg, shot["shotId"], "cinematography") or {}
    return work.get("providerPrompt") or shot.get("keyframePrompt")


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
        out.append({"dialogueOccurrenceId": ln.get("dialogueOccurrenceId"),
                    "sourceEventId": ln.get("sourceEventId"),
                    "speaker": ln["speaker"], "text": text})
    return out


def _resolve_voice_lines(pkg, shot):
    """Exact ElevenLabs input with explicit precedence: Julian edit > approved worker > legacy."""
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingVoice")
    if working and working.get("lines"):
        return working["lines"], "human-working"
    output = _approved_department_output(pkg, shot["shotId"], "voice") or {}
    if output.get("lines"):
        return [{"dialogueOccurrenceId": x.get("dialogueOccurrenceId"),
                 "sourceEventId": x.get("sourceEventId"),
                 "speaker": x["speaker"], "text": x["performedText"]}
                for x in output["lines"]], "voice-director-approved"
    return _default_voice_lines(shot), "legacy-approved-storyboard"


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
    approved = [{"dialogueOccurrenceId": ln.get("dialogueOccurrenceId"),
                 "sourceEventId": ln.get("sourceEventId"),
                 "speaker": ln["speaker"], "exactText": ln["exactText"],
                 "delivery": ln.get("delivery")}
                for ln in (shot.get("dialogueLines") or [])]
    working = led.get("workingVoice")
    current, source = _resolve_voice_lines(pkg, shot)
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
    return {"approvedLines": approved, "currentLines": current, "source": source,
            "isWorking": bool(working), "savedAt": (working or {}).get("savedAt"),
            "hasTake": has_take, "takeMatchesCurrent": match,
            "takeGeneratedAt": take_generated_at, "previous": led.get("voicePrevious")}


def save_voice_working(scene, shot_id, lines, episode="Ep1", reviewed_by="Julian", log=print):
    """Saves a shot-level WORKING performance version — the approved dialogueLines (the
    locked words) are never touched, never rewritten, never re-ordered. lines must be the
    same length as the shot's own dialogueLines, same speaker per position (only the
    submitted TEXT per line may differ from exactText — acting direction/cadence/tags
    composed directly into it); a mismatch refuses rather than silently reordering or
    dropping a line. NEVER calls cb_gen — this is a save, not a generation."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
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
        submitted_id = ln.get("dialogueOccurrenceId")
        if submitted_id and submitted_id != dl_ln.get("dialogueOccurrenceId"):
            raise Refused(f"REFUSED — working line {i+1}'s dialogue occurrence ID changed")
        clean.append({"dialogueOccurrenceId": dl_ln.get("dialogueOccurrenceId"),
                      "sourceEventId": dl_ln.get("sourceEventId"),
                      "speaker": dl_ln["speaker"], "text": text})
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
    # is the whole point of editing it — otherwise the control would be decorative. Falls
    # back to the plain locked exactText exactly as before when nothing has been saved.
    working = led.get("workingVoice")
    perf_lines, performance_source = _resolve_voice_lines(pkg, shot)
    if len(perf_lines) != len(shot["dialogueLines"]):
        # a stale working version (e.g. the storyboard's own dialogueLines changed count
        # since it was saved) — refuse to guess at a re-alignment, fall back to the locked
        # default rather than submit a mismatched performance track.
        perf_lines = _default_voice_lines(shot)
        performance_source = "legacy-approved-storyboard"
    turns = []
    for ln, perf in zip(shot["dialogueLines"], perf_lines):
        vid = (characters_cfg.get(_resolve_char(ln["speaker"], characters_cfg)) or {}).get("voiceId")
        if not vid:
            raise Refused(f"REFUSED — no ElevenLabs voiceId for {ln['speaker']} "
                          f"(Law 5: the voice lives in the render; no fallback)")
        turns.append({"text": perf["text"], "voice_id": vid})
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
    led["voPath"] = str(out)
    # THE STALE-TAKE FLAG (2026-07-19, Julian — "I don't feel the acting from the direction
    # changed anything"): traced live to a real, confirmed gap — editing and saving a working
    # version never regenerates audio (correctly, by design), but nothing told the user the
    # take on screen was built BEFORE their edit existed. Snapshotting exactly which lines
    # produced THIS take lets voice_performance_status compare it to whatever's current and
    # say so plainly, instead of leaving "did my edit do anything?" as a guess from timestamps.
    led["voGeneratedFrom"] = perf_lines
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
    done = []
    for s in pkg["shots"]:
        if not s.get("dialogueLines"):
            continue
        led = _ledger(pkg, s["shotId"])
        if led.get("voPath"):
            status = voice_performance_status(scene, s["shotId"], episode)
            if status.get("takeMatchesCurrent") is not False:
                continue  # has a take, and it's not a CONFIRMED mismatch — leave it alone
        done.append(voice_shot(pkg, path, s["shotId"], episode, log=log))
    log(f"VOICE — scene {scene}: {len(done)} shot track(s) built")
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
def _timing_slate_input_signature(pkg):
    """Bind the slate to current shot timing and approved voice files."""
    rows = []
    for shot in pkg["shots"]:
        ledger = _ledger(pkg, shot["shotId"])
        voice_path = ledger.get("voPath")
        if shot.get("dialogueLines"):
            approval = _voice_approval_status(pkg, shot)
            if not approval.get("current"):
                raise Refused(
                    f"REFUSED — {shot['shotId']} needs a current approved voice take "
                    "before the scene timing slate")
        rows.append({
            "shotId": shot["shotId"],
            "durationSec": shot["durationSec"],
            "dialogueHash": hashlib.sha256(json.dumps(
                shot.get("dialogueLines") or [], sort_keys=True,
                ensure_ascii=False).encode()).hexdigest(),
            "voicePath": voice_path if shot.get("dialogueLines") else None,
            "voiceHash": (_sha256_file(voice_path)
                          if shot.get("dialogueLines") else None),
            "voiceApprovalSignature": ((ledger.get("voiceApproval") or {})
                                       .get("inputSignature")
                                       if shot.get("dialogueLines") else None),
        })
    return {"shots": rows}


def timing_slate_status(scene, episode="Ep1"):
    """Read-only timing-slate freshness report; never calls a provider."""
    out = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    sidecar = pathlib.Path(str(out) + ".contract.json")
    if not out.exists() or not sidecar.exists():
        return {"exists": out.exists(), "current": False, "path": str(out),
                "reason": "not built from a recorded input contract"}
    try:
        pkg, _ = load_pkg(scene, episode)
        record = json.loads(sidecar.read_text())
        current = record.get("inputSignature") == _timing_slate_input_signature(pkg)
        return {"exists": True, "current": current, "path": str(out),
                "generatedAt": record.get("generatedAt"),
                "reason": None if current else "shot timing or an approved voice take changed"}
    except (OSError, ValueError, Refused) as exc:
        return {"exists": True, "current": False, "path": str(out), "reason": str(exc)}


def animatic_scene(scene, episode="Ep1", log=print):
    """Builds the TIMING SLATE (function name kept for CLI/Studio compatibility)."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    input_signature = _timing_slate_input_signature(pkg)
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
    pathlib.Path(str(out) + ".contract.json").write_text(json.dumps({
        "generatedAt": _now(), "inputSignature": input_signature,
        "approvesOnly": ["dialogue accuracy", "voice assignment", "shot duration",
                         "scene length", "dialogue position"],
    }, indent=1, ensure_ascii=False))
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
    return cb_post._dur(p) or 0.0


def _hold(img, dur, audio, out):
    # every hold carries a real audio stream (silent when no voice) — the scene assembler's
    # concat maps [i:a] on EVERY clip; and -t bounds the output (never -shortest, which would
    # truncate a 6s hold to its 2s voice track). Found by the first real animatic assembly.
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", img]
    if audio:
        cmd += ["-i", audio]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    cmd += ["-t", f"{dur:.2f}", "-r", "24", "-pix_fmt", "yuv420p",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                   "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-af", "apad", "-c:a", "aac", "-ar", "48000", "-ac", "2", out]
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
    prompt = _resolve_keyframe_prompt(pkg, shot)
    return {"cardHash": _live_card_hash(shot["shotId"], scene, episode),
            "sceneLookHash": scenelook_hash,
            "referenceHashes": {os.path.basename(p): _file_md5(p) for p in refs},
            "briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "model": f"{cb_gen.IMAGE_PROVIDER}:{cb_gen.SEEDREAM_ENDPOINT}:2K"}


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
    input(s) changed."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    existing = led.get("keyframeApproval") or led.get("keyframeCandidate")
    if not existing:
        return {"verdict": "none", "changed": [], "existing": None, "currentSignature": None}
    current_sig = _keyframe_input_signature(pkg, shot, scene, episode)
    diff = _signature_diff(existing.get("inputSignature"), current_sig)
    return {"verdict": "carry_forward" if not diff else "regenerate",
            "changed": diff, "existing": existing, "currentSignature": current_sig}


def keyframe_shot(scene, shot_id, episode="Ep1", log=print):
    """GENERATE {shotId} OPENING KEYFRAME — ONE IMAGE. Generates exactly one keyframe
    CANDIDATE for shot_id, to its own unique path; touches no other shot's media or ledger
    entry, and never archives, replaces, regenerates or otherwise modifies the Scene Look
    Plate (2026-07-18 correction). The shot's currently-approved keyframe, if any, is left
    completely untouched until this new candidate is itself approved."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
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
    characters_cfg = _characters_cfg()
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / f"{episode}_{shot_id}_keyframe_candidate_{uuid.uuid4().hex[:8]}.png"
    prompt = _resolve_keyframe_prompt(pkg, shot)
    cb_gen.generate_image(prompt, refs=refs, out=str(out), production_route="cb_render")
    # ONLY reached on a successful generation — led["keyframeCandidate"] (and any existing
    # keyframeApproval) is never touched before this line, so a failure above leaves the
    # ledger, and any approved keyframe, byte-for-byte as they were.
    led["keyframeCandidate"] = {"path": str(out), "generatedAt": _now(), "source": "generated",
                                 "inputSignature": _keyframe_input_signature(pkg, shot, scene, episode)}
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
MAX_BATCH_ATTEMPTS = 2      # the failure ladder's hard stop — never an endless patch loop

# the per-candidate evaluation sheet (§6 of the correction) — HUMAN review criteria; the
# machine fills mechanical notes only and never auto-approves creative quality
REVIEW_CRITERIA = ["characterIdentity", "relativeScale", "startingGeography",
                    "actionReadability", "physicalCauseAndEffect",
                    "comicOrEmotionalPerformance", "cameraBehaviour",
                    "dialogueAndMouthPerformance", "continuity", "finalFrameUsability"]

FAILURE_CATEGORIES = ["identity", "geography", "action-timing", "instruction-ignored", "other"]

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


def _animation_provider_contract(shot, imgs, led, fast):
    try:
        return cb_providers.request_contract(
            fast=fast, duration=int(round(shot["durationSec"])), resolution="720p",
            image_count=len(imgs), audio_count=1 if led.get("voPath") else 0)
    except cb_providers.ProviderCapabilityError as exc:
        raise Refused(f"REFUSED — provider capability: {exc}") from exc


def _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast):
    """Everything the spend approval is bound to.

    The binding covers this shot's exact provider inputs and cost envelope. Package revision
    and other shots are provenance, not spend inputs, so an unrelated promotion cannot void a
    token while any changed prompt, media byte, duration, tier, count or rate still does.
    """
    import cb_costs
    contract = _animation_provider_contract(shot, imgs, led, fast)
    key = contract["costRateKey"]
    rate, _, _ = cb_costs.RATES[key]
    per = round(cb_costs.estimate_video_cost(key, int(round(shot["durationSec"]))), 4)
    payload = {"shotContractHash": hashlib.sha256(json.dumps(
                   shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
               "shotId": shot["shotId"],
               "provider": contract["provider"],
               "providerModelId": contract["providerModelId"],
               "modelVersion": contract["modelVersion"],
               "endpoint": contract["endpoint"],
               "resolution": contract["resolution"],
               "candidates": candidates, "ratePerSecUsd": rate,
               "maxBatchCostUsd": round(per * candidates, 4),
               "prompt": shot["seedancePrompt"],
               "slotOrder": shot["referenceSlots"],
               "anchorMd5": _file_md5(anchor),
               "refMd5s": [_file_md5(p) for p in imgs],
               "audioMd5": _file_md5(led["voPath"]) if led.get("voPath") else None,
               "durationSec": shot["durationSec"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32], per


def _fresh_validation(pkg, episode):
    """PROTECTION 4: validation is re-run against the CURRENT package content at every
    disclosure — a hand-edited or revised package can never fire on a stale green stamp.
    Zero-LLM (cb_engine's deterministic validator, imported, never modified)."""
    import cb_engine as E
    d, _ = E._load_pkg(episode)
    beats = E._scene_beats(d, pkg["sceneNumber"])
    fields = set(E.Shot.model_fields)
    shots = [E.Shot(**{k: v for k, v in rec.items() if k in fields}) for rec in pkg["shots"]]
    design = E.SceneShotList(statement=E.DirectorStatement(**pkg.get("directorStatement", {
        k: "n/a" for k in ("audienceFeeling", "whoseScene", "emotionalChange", "theLaugh",
                            "visualSurprise", "carryForward")})), shots=shots)
    report = E.validate_scene_design(design, beats, _characters_cfg())
    if not report["passed"]:
        errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
        raise Refused(f"REFUSED — fresh validation of the CURRENT package failed with "
                      f"{len(errs)} error(s) (first: {errs[0]['code']} at {errs[0]['path']}). "
                      f"A revised package requires fresh validation before any spend.")
    return report


def _prompt_version(shot):
    import hashlib
    return hashlib.md5(shot["seedancePrompt"].encode()).hexdigest()[:8]


def _sealed_envelope(pkg, shot, led, imgs, anchor, candidates, fast, per):
    """THE IMMUTABLE PROVIDER-REQUEST ENVELOPE (Julian's cutover order, 2026-07-16, §5):
    everything the provider will receive, sealed AT DISCLOSURE — exact prompt, duration, model,
    resolution, candidate count, reference order with per-file hashes, audio hash, max cost.
    The spend token binds to this envelope's hash; firing sends THIS, never a recompile."""
    img_slots = [t for t in shot["referenceSlots"] if t != "@Audio1"]
    refs = [{"slot": t, "role": shot["referenceSlots"][t], "path": p, "md5": _file_md5(p)}
            for t, p in zip(img_slots, imgs)]
    contract = _animation_provider_contract(shot, imgs, led, fast)
    env = {"shotId": shot["shotId"], "prompt": shot["seedancePrompt"],
           "durationSec": shot["durationSec"], "provider": contract["provider"],
           "providerModelId": contract["providerModelId"],
           "modelVersion": contract["modelVersion"],
           "transport": contract["transport"],
           "endpoint": contract["endpoint"],
           "costRateKey": contract["costRateKey"],
           "capabilityVerifiedAt": contract["capabilityVerifiedAt"],
           "resolution": "720p", "tier": "fast" if fast else "standard",
           "candidateCount": candidates, "costPerCandidateUsd": per,
           "maxBatchCostUsd": round(per * candidates, 4),
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
def _resolve_seedance_prompt(pkg, shot):
    """Returns (prompt_text, is_working) — the prompt fire_shot will actually submit right
    now: the saved working override if one exists, else the approved compiled prompt."""
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingSeedancePrompt")
    if working and working.get("text"):
        return working["text"], True
    output = _approved_department_output(pkg, shot["shotId"], "animation") or {}
    if output.get("providerPrompt"):
        return output["providerPrompt"], False
    return shot["seedancePrompt"], False


def seedance_working_status(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedPrompt": str, "currentPrompt": str (working override
    if saved, else the approved prompt — exactly what will be submitted), "isWorking": bool,
    "savedAt": str|None}."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    current, is_working = _resolve_seedance_prompt(pkg, shot)
    led = _ledger(pkg, shot_id)
    working = led.get("workingSeedancePrompt")
    specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    source = ("human-working" if is_working else
              "animation-director-approved" if specialist.get("providerPrompt") else
              "legacy-approved-storyboard")
    baseline = specialist.get("providerPrompt") or shot["seedancePrompt"]
    return {"approvedPrompt": baseline, "currentPrompt": current,
            "source": source,
            "isWorking": is_working, "savedAt": (working or {}).get("savedAt")}


def save_seedance_working(scene, shot_id, prompt_text, episode="Ep1", reviewed_by="Julian", log=print):
    """Saves a shot-level WORKING Seedance prompt — the approved storyboard's own compiled
    seedancePrompt is never touched, never rewritten. Refuses (never silently strips) a
    prompt that would violate Law 6 (spoken dialogue words reaching a render prompt) — this
    is a REFUSAL with the reason stated, not a rewrite of Julian's own text. NEVER calls
    cb_gen — this is a save, not a generation."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    text = str(prompt_text or "").strip()
    if not text:
        raise Refused(f"REFUSED — {shot_id}'s working Seedance prompt cannot be blank")
    p = _norm(text)
    for ln in shot.get("dialogueLines") or []:
        t = _norm(ln["exactText"])
        if len(t.split()) >= 2 and t in p:
            raise Refused(f"REFUSED — LAW 6: this prompt contains spoken dialogue words "
                          f"(\"{ln['exactText']}\") — the voice lives in @Audio1, never render "
                          f"prompt text. Not saved; edit and try again.")
    led["workingSeedancePrompt"] = {"text": text, "savedAt": _now(), "savedBy": reviewed_by}
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


def _prompt_quality_gate(shot, prompt, specialist=None):
    """Free deterministic craft check for a Seedance shooting script.

    This is an advisory quality gate, not an automatic rewrite and not a provider call.
    The four critical dimensions are story beat, canon/reference fidelity, audio/dialogue
    separation and a usable continuity landing.
    """
    specialist = specialist or {}
    text = str(prompt or "").strip()
    low = text.lower()
    words = len(text.split())
    dialogue = shot.get("dialogueLines") or []
    leaked_dialogue = any(
        len(_norm(line.get("exactText")).split()) >= 2 and
        _norm(line.get("exactText")) in _norm(text)
        for line in dialogue)

    def has(pattern):
        return bool(re.search(pattern, low, re.IGNORECASE))

    scores = {}
    scores["storyBeat"] = (
        2 if specialist.get("dramaticBeat") and specialist.get("performanceArc")
        else 1 if has(r"\b(beat|turn|realises?|decides?|tries?|fails?|wins?|loses?|reaction)\b")
        else 0)
    scores["canonAndReferences"] = (
        2 if specialist.get("referenceContract") and
        has(r"\b(identity|proportion|relative scale|reference|silhouette|canon)\b")
        else 1 if specialist.get("referenceContract") or
        has(r"\b(identity|proportion|relative scale|reference|silhouette|canon)\b")
        else 0)
    scores["physicalCauseAndEffect"] = (
        2 if has(r"\b(because|causing|which makes|so that|therefore|until|as .*?(?:moves?|falls?|lands?|hits?|pulls?|pushes?))\b")
        and has(r"\b(steps?|turns?|leans?|reaches?|grabs?|pulls?|pushes?|falls?|lands?|hits?|crosses?|moves?|stops?)\b")
        else 1 if has(r"\b(steps?|turns?|leans?|reaches?|grabs?|pulls?|pushes?|falls?|lands?|hits?|crosses?|moves?|stops?)\b")
        else 0)
    scores["cameraAndEdit"] = (
        2 if has(r"\b(\d{2,3}mm|lens|wide|medium|close[- ]?up|camera|dolly|pan|tilt|track|handheld|cut to|match cut|hold)\b")
        and has(r"\b(camera|cut|lens|framing|wide|medium|close[- ]?up)\b")
        else 1 if has(r"\b(camera|cut|lens|framing|wide|medium|close[- ]?up)\b")
        else 0)
    scores["observablePerformance"] = (
        2 if has(r"\b(glance|blink|breath|breathes?|swallows?|flinch|hesitat|jaw|eyes?|shoulders?|posture|expression|reaction)\b")
        and has(r"\b(before|after|then|as|while|holds?|settles?|tightens?|softens?)\b")
        else 1 if has(r"\b(glance|blink|breath|flinch|eyes?|shoulders?|posture|expression|reaction)\b")
        else 0)
    depth = has(r"\b(foreground|midground|background|depth|layer|occlusion|negative space|silhouette)\b")
    visual = has(r"\b(light|lighting|shadow|rim|bounce|glow|material|texture|surface|fur|glass|metal|wood)\b")
    scores["compositionDepth"] = 2 if depth and visual else 1 if depth else 0
    scores["lightMaterialsFinish"] = (
        2 if visual and has(r"\b(cinematic|controlled|subtle|soft|hard|warm|cool|practical|volumetric|specular|diffuse)\b")
        else 1 if visual else 0)
    scores["dialogueAudioSeparation"] = (
        2 if not dialogue else
        2 if "@audio1" in low and not leaked_dialogue else
        1 if not leaked_dialogue else 0)
    opens = has(r"\b(exact opening|opening frame|begins? (?:on|from)|start(?:s|ing)? (?:on|from)|first frame)\b")
    lands = has(r"\b(landing image|lands? on|ends? on|final frame|closing frame|handoff|settles? into)\b")
    scores["continuityLanding"] = 2 if opens and lands else 1 if opens or lands else 0
    safeguard_count = len(specialist.get("surgicalSafeguards") or [])
    scores["promptEconomy"] = (
        2 if 45 <= words <= 320 and safeguard_count <= 3
        else 1 if 25 <= words <= 450 else 0)

    total = sum(scores.values())
    critical = {
        "storyBeat", "canonAndReferences", "dialogueAudioSeparation",
        "continuityLanding"}
    critical_failures = [name for name in critical if scores[name] == 0]
    return {
        "score": total,
        "maximum": 20,
        "threshold": 17,
        "needsRevision": total < 17 or bool(critical_failures),
        "criticalFailures": sorted(critical_failures),
        "dimensions": scores,
        "wordCount": words,
        "advisoryOnly": True,
    }


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
    imgs = []
    try:
        anchor = _anchor_for(pkg, shot)
        checks["openingFrameAttached"] = {"ok": True, "path": anchor}
    except Refused as e:
        blockers.append(str(e)); checks["openingFrameAttached"] = {"ok": False, "detail": str(e)}

    characters_cfg = _characters_cfg()
    if anchor:
        try:
            imgs = _slot_paths(shot, "referenceSlots", anchor, scene, episode, characters_cfg)
            ordered_slots = sorted(
                (slot for slot in (shot.get("referenceSlots") or {}) if slot.startswith("@图")),
                key=lambda slot: int(slot[2:]))
            checks["sceneLookAttached"] = {"ok": True}
            checks["referencesAttached"] = {"ok": True, "count": len(imgs),
                                             "order": ordered_slots}
            checks["referenceContract"] = [
                {"position": index, "assetTag": slot,
                 "role": shot["referenceSlots"][slot], "path": path,
                 "contentHash": hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()}
                for index, (slot, path) in enumerate(zip(ordered_slots, imgs), start=1)
            ]
        except (Refused, OSError) as e:
            blockers.append(str(e))
            checks["sceneLookAttached"] = {"ok": False, "detail": str(e)}
            checks["referencesAttached"] = {"ok": False, "detail": str(e)}
    else:
        checks["sceneLookAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}
        checks["referencesAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}

    if shot.get("dialogueLines"):
        # 2026-07-19: audio readiness now means APPROVED, not merely generated — matching
        # keyframe/animation's own "an unapproved artefact is never a valid anchor" rule.
        vo_path = led.get("voPath")
        vo_approved = bool(
            (led.get("voiceApproval") or {}).get("approved") and
            vo_path and os.path.exists(vo_path))
        checks["audioAttached"] = {"ok": vo_approved, "required": True, "path": led.get("voPath")}
        if not vo_approved:
            reason = ("no voice track generated yet" if not led.get("voPath")
                      else "a voice track exists but has not been approved yet")
            blockers.append(f"{shot_id} has dialogue but {reason} "
                            f"(Law 5: voice first, no native-voice fallback)")
        else:
            contract = checks.setdefault("referenceContract", [])
            contract.append({
                "position": len(contract) + 1, "assetTag": "@Audio1",
                "role": "approved dialogue and performance track", "path": vo_path,
                "contentHash": hashlib.sha256(pathlib.Path(vo_path).read_bytes()).hexdigest(),
            })
    else:
        checks["audioAttached"] = {"ok": True, "required": False, "detail": "no dialogue in this shot"}

    checks["durationSec"] = shot.get("durationSec")
    checks["resolution"] = "720p"
    checks["aspectRatio"] = "16:9"
    try:
        provider_contract = cb_providers.request_contract(
            duration=int(round(shot.get("durationSec") or 0)), resolution="720p",
            image_count=len(imgs),
            audio_count=1 if shot.get("dialogueLines") else 0)
        checks["providerContract"] = provider_contract
        checks["model"] = provider_contract["providerModelId"]
    except cb_providers.ProviderCapabilityError as exc:
        blockers.append(f"provider capability: {exc}")
        checks["providerContract"] = {"ok": False, "detail": str(exc)}
        checks["model"] = cb_providers.selected_video_model_id()

    resolved_prompt, using_working = _resolve_seedance_prompt(pkg, shot)
    specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    checks["usingWorkingVersion"] = using_working
    checks["promptSource"] = ("human-working" if using_working else
        "seedance-production-director-approved" if specialist.get("providerPrompt")
        else "legacy-approved-storyboard")
    quality = _prompt_quality_gate(shot, resolved_prompt, specialist)
    checks["qualityGate"] = quality
    if quality["needsRevision"]:
        detail = (f"; critical zero: {', '.join(quality['criticalFailures'])}"
                  if quality["criticalFailures"] else "")
        warnings.append(
            f"craft gate scores {quality['score']}/{quality['maximum']} "
            f"(target {quality['threshold']}){detail}")

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

    # LAW 6 is provider-required, not creative — a leak here blocks, it does not warn
    p = _norm(resolved_prompt)
    for ln in shot.get("dialogueLines") or []:
        t = _norm(ln["exactText"])
        if len(t.split()) >= 2 and t in p:
            blockers.append(f"LAW 6: the resolved prompt appears to contain spoken dialogue "
                            f"words (\"{ln['exactText']}\")")
            break

    verdict = "blocked" if blockers else ("warnings" if warnings else "passed")
    result = {"verdict": verdict, "blockers": blockers, "warnings": warnings,
              "checks": checks, "finalPrompt": resolved_prompt}
    log(f"SEEDANCE STRUCTURE CHECK — {shot_id}: {verdict.upper()} ({len(blockers)} blocker(s), "
        f"{len(warnings)} warning(s)) — no provider call made, no cost")
    return result


def prompt_readback(scene, shot_id, episode="Ep1", log=print):
    """Ask the advisory readback lens what the approved animation brief will produce.

    This is an optional text/vision model call, never a media generation call and never an
    approval gate. It reads only a current production graph and returns a plain-language
    recommendation that the Studio can show before spend disclosure.
    """
    pkg, _ = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    prompt, using_working = _resolve_seedance_prompt(pkg, shot)
    try:
        anchor = _anchor_for(pkg, shot)
    except Refused:
        anchor = None
    intent_parts = [
        shot.get("purpose"),
        shot.get("performanceAssignment"),
        shot.get("visualPayoff"),
    ]
    intent = " ".join(str(value).strip() for value in intent_parts if value)

    import cb_readback

    reading = cb_readback.read_back(
        prompt,
        shot_id=shot_id,
        form="take",
        images=[anchor] if anchor else None,
        intent=intent,
        log=log,
    )
    return {
        "available": reading is not None,
        "advisoryOnly": True,
        "mediaProviderCalled": False,
        "usingWorkingVersion": using_working,
        "shotId": shot_id,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "openingFrame": anchor,
        "result": reading.model_dump(mode="json") if reading is not None else None,
        "plainText": cb_readback.as_plain_text(reading),
    }


def fire_shot(scene, shot_id, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, log=print):
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
    resolved_prompt, using_working = _resolve_seedance_prompt(pkg, shot)
    if resolved_prompt != shot["seedancePrompt"]:
        shot = {**shot, "seedancePrompt": resolved_prompt}
    candidates = max(1, min(MAX_CANDIDATES, int(candidates)))
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

    # LAW 6, re-asserted at the last moment before money
    p = _norm(shot["seedancePrompt"])
    for ln in shot.get("dialogueLines") or []:
        if len(_norm(ln["exactText"]).split()) >= 2 and _norm(ln["exactText"]) in p:
            raise Refused(f"REFUSED — LAW 6: spoken words found in {shot_id}'s compiled prompt")

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
        binding, _per = _binding_hash(pkg, shot, led, imgs, anchor, batch["expected"], fast)
        if binding != batch["bindingHash"]:
            raise Refused(f"REFUSED — the package changed mid-batch (binding mismatch); the "
                          f"in-flight authorization is void. Request a new disclosure.")
        # a resume ships the SAME sealed envelope the original approval bound (§5)
        envelope = _verify_envelope(batch)
        prompt = envelope["prompt"]
        fast = (envelope["tier"] == "fast")
        candidates = batch["expected"]
        try:
            cb_db.claim_spend_authorization(
                HERE.parent, spend_token, episode, scene, shot_id, binding,
                batch["envelopeHash"], batch["batchId"])
        except cb_db.SpendConflict as exc:
            raise Refused(f"REFUSED — {exc}") from exc
    else:
        if led.get("status") == "candidates-pending":
            raise Refused(f"REFUSED — {shot_id} has a candidate batch pending Julian's review "
                          f"(approve one candidate or reject the batch first)")
        # PROTECTION 4: fresh validation of the CURRENT package, every disclosure
        _fresh_validation(pkg, episode)
        binding, per = _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast)
        envelope, env_hash = _sealed_envelope(pkg, shot, led, imgs, anchor, candidates,
                                                fast, per)
        reroll = (led.get("lastBatchBinding") == binding)
        disclosure = {"shotId": shot_id, "candidateCount": candidates,
                       "costPerCandidateUsd": per,
                       "maxBatchCostUsd": round(per * candidates, 4),
                       "promptVersion": _prompt_version(shot),
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
        for k in ("shotId", "candidateCount", "costPerCandidateUsd", "maxBatchCostUsd",
                   "promptVersion", "bindingHash", "envelopeHash", "packageRevision",
                   "rerollOfUnchangedPackage", "openingAnchor", "audioAsset",
                   "shotDurationSec", "tier"):
            log(f"  {k}: {disclosure[k]}")
        log(f"  referenceSlots (upload order): {json.dumps(disclosure['referenceSlots'])}")

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
            try:
                cb_db.issue_spend_authorization(
                    HERE.parent, episode, scene, shot_id, led["pendingSpendAuth"])
            except cb_db.SpendConflict as exc:
                raise Refused(f"REFUSED — {exc}") from exc
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
        batch_id = (f"{shot_id}-b{led.get('batchAttempts', 0) + 1}-"
                    f"{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}-"
                    f"{uuid.uuid4().hex[:8]}")
        try:
            cb_db.claim_spend_authorization(
                HERE.parent, spend_token, episode, scene, shot_id, binding,
                auth["envelopeHash"], batch_id)
        except cb_db.SpendConflict as exc:
            raise Refused(f"REFUSED — {exc}") from exc
        led["pendingSpendAuth"] = None                     # claimed now; consumed on completion
        pv = auth["disclosure"]["promptVersion"]
        if led.get("lastPromptVersion") and led["lastPromptVersion"] != pv:
            led["promptRevisions"] = led.get("promptRevisions", 0) + 1
        led["lastPromptVersion"] = pv
        batch = {"token": spend_token, "bindingHash": binding,
                 "envelope": envelope, "envelopeHash": auth["envelopeHash"],
                 "batchId": batch_id,
                 "expected": candidates, "done": [], "failed": [],
                 "disclosure": auth["disclosure"], "status": "generating"}
        led["batch"] = batch
        _save(pkg, path)

    image_urls = [cb_gen._fal_upload(x) for x in imgs]     # uploaded once per invocation
    audio_urls = [cb_gen._fal_upload(led["voPath"])] if led.get("voPath") else None

    MEDIA.mkdir(parents=True, exist_ok=True)
    for i in range(1, batch["expected"] + 1):
        out = MEDIA / f"{episode}_{shot_id}_c{i}.mp4"
        try:
            claim = cb_db.claim_candidate(
                HERE.parent, batch["token"], i,
                f"{os.getpid()}:{threading.get_ident()}")
        except cb_db.SpendConflict as exc:
            raise Refused(f"REFUSED — {exc}") from exc
        if claim["action"] == "completed":
            recorded = pathlib.Path(claim["output_path"] or "")
            actual_hash = (_sha256_file(recorded) if recorded.is_file() else None)
            if actual_hash != claim["output_hash"]:
                raise Refused(
                    f"REFUSED — candidate {i}'s transactionally completed artifact is "
                    "missing or changed; automatic repayment is blocked")
            if i not in batch["done"]:
                batch["done"].append(i)
                _save(pkg, path)
            continue                                       # idempotent: never regenerated
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
            cb_db.fail_candidate(HERE.parent, batch["token"], i, e)
            batch["failed"].append({"candidate": i, "error": str(e)[:400], "at": _now()})
            _save(pkg, path)
            raise Refused(f"REFUSED — candidate {i} failed at the provider "
                          f"({str(e)[:160]}). The batch is saved and resumable: re-run with "
                          f"the SAME spend token to generate only the missing candidates — "
                          f"completed candidates are never repaid.")
        _candidate_review(shot, str(out), batch["batchId"], i)
        cb_db.complete_candidate(HERE.parent, batch["token"], i, out)
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
    try:
        cb_db.complete_spend_authorization(HERE.parent, batch["token"])
    except cb_db.SpendConflict as exc:
        raise Refused(f"REFUSED — {exc}") from exc
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
              spend_token=None, dry_run=False, log=print):
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
                              fast=fast, spend_token=spend_token, log=log, dry_run=dry_run)
    log(f"SCENE {scene} — every shot approved; ready to stitch")
    return None


# ── Gate 8 — Julian selects ONE candidate; approval harvests the relay anchor ───────────
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
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_{ts}"
    arch.mkdir(parents=True, exist_ok=True)
    for c in led["candidatePaths"]:
        for ext in ("", ".review.json"):
            if os.path.exists(c + ext):
                shutil.move(c + ext, arch / os.path.basename(c + ext))
    rejection = {"shotId": shot_id, "batchId": led.get("batchId"),
                 "correction": correction, "category": category,
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


# ── Gate 9 — transactional post candidate, then human final-master approval ─────────────
def _post_input_signature(pkg, scene, episode="Ep1"):
    """Exact approved source graph for one post build."""
    shots = []
    for shot in pkg.get("shots") or []:
        ledger = _ledger(pkg, shot["shotId"])
        review = ((ledger.get("departmentWork") or {}).get("review-animation") or {}).get(
            "approved") or {}
        review_evidence = {
            key: review.get(key) for key in (
                "inputSignature", "output", "outcome", "decisionAt", "reviewedBy")
        }
        shots.append({
            "shotId": shot["shotId"],
            "shotContractHash": hashlib.sha256(json.dumps(
                shot, sort_keys=True, ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest(),
            "approvedTake": ledger.get("approvedTake"),
            "approvedTakeHash": (
                _sha256_file(ledger["approvedTake"])
                if ledger.get("approvedTake") and os.path.exists(ledger["approvedTake"])
                else None),
            "animationApprovalInputSignature": (ledger.get("approval") or {}).get(
                "inputSignature"),
            "directorReviewInputSignature": review.get("inputSignature"),
            "directorReviewEvidenceHash": hashlib.sha256(json.dumps(
                review_evidence, sort_keys=True, ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest(),
        })
    inputs = {
        "postPolicyVersion": cb_post.POST_POLICY_VERSION,
        "postRuntimeHash": _sha256_file(cb_post.__file__),
        "packageInputSignature": pkg.get("inputSignature"),
        "orderedApprovedShots": shots,
        "masteringPlatform": cb_post.DEFAULT_PLATFORM,
    }
    return cb_lineage.dependency_signature("scene-post", inputs)


def _post_manifest_current(manifest, expected_signature):
    if not isinstance(manifest, dict) or manifest.get("inputSignature") != expected_signature:
        return False, "direct-input-signature-mismatch"
    if not (manifest.get("qc") or {}).get("passed"):
        return False, "post-qc-not-passed"
    digest_source = {key: value for key, value in manifest.items() if key != "manifestDigest"}
    digest = hashlib.sha256(json.dumps(
        digest_source, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    if manifest.get("manifestDigest") != digest:
        return False, "post-manifest-digest-mismatch"
    manifest_path = manifest.get("manifestPath")
    if not manifest_path or not os.path.exists(manifest_path):
        return False, "post-manifest-file-missing"
    try:
        on_disk = json.load(open(manifest_path))
    except (OSError, ValueError):
        return False, "post-manifest-file-unreadable"
    if on_disk != manifest:
        return False, "post-manifest-file-changed"
    for name, asset in (manifest.get("outputs") or {}).items():
        path = asset.get("path") if isinstance(asset, dict) else None
        if not path or not os.path.exists(path):
            return False, f"post-output-missing:{name}"
        if asset.get("sha256") != _sha256_file(path):
            return False, f"post-output-changed:{name}"
    return True, None


def post_status(pkg, scene=None, episode=None):
    """Read-only state for the immutable post candidate and approved master."""
    scene = str(scene if scene is not None else pkg.get("sceneNumber"))
    episode = episode or pkg.get("episode", "Ep1")
    container = pkg.get("postProduction") or {}
    try:
        expected = _post_input_signature(pkg, scene, episode)
    except (OSError, ValueError, Refused) as exc:
        expected = None
        error = str(exc)
    else:
        error = None

    def status(record):
        manifest = (record or {}).get("manifest")
        if not manifest:
            return {"exists": False, "current": False, "reason": "missing", "record": record}
        if expected is None:
            return {"exists": True, "current": False, "reason": error,
                    "record": record, "manifest": manifest}
        current, reason = _post_manifest_current(manifest, expected)
        return {"exists": True, "current": current, "reason": reason,
                "record": record, "manifest": manifest}

    return {"expectedInputSignature": expected,
            "candidate": status(container.get("candidate")),
            "approved": status(container.get("approved")),
            "history": list(container.get("history") or [])}


def stitch_scene(scene, episode="Ep1", log=print):
    pkg, path = load_pkg(scene, episode)
    sources, missing = [], []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        if led.get("status") == "approved" and led.get("approvedTake"):
            sources.append({"shotId": s["shotId"], "approvedTake": led["approvedTake"],
                            "dialogueLines": list(s.get("dialogueLines") or [])})
        else:
            missing.append(s["shotId"])
    if missing:
        raise Refused(f"REFUSED — cannot stitch scene {scene}: unapproved shots {missing}")
    post = pkg.setdefault("postProduction", {"candidate": None, "approved": None,
                                              "history": []})
    state = post_status(pkg, scene, episode)
    if state["candidate"]["current"]:
        raise Refused("REFUSED — a current post master candidate already awaits review")
    if post.get("candidate"):
        post.setdefault("history", []).append({**post["candidate"],
                                                "outcome": "superseded-stale",
                                                "supersededAt": _now()})
        post["candidate"] = None
        final_work = (pkg.get("departmentWork") or {}).get("review-final") or {}
        if final_work.get("candidate"):
            final_work.setdefault("history", []).append({**final_work["candidate"],
                                                          "outcome": "superseded-stale",
                                                          "supersededAt": _now()})
            final_work["candidate"] = None

    signature = _post_input_signature(pkg, scene, episode)
    try:
        manifest = cb_post.build_scene_post(
            sources, HERE / "media" / "post", episode, str(scene), signature,
            music=str(HERE / "media" / f"{episode}_S{scene}_music.mp3"),
            ambience=str(HERE / "media" / f"{episode}_S{scene}_ambience.mp3"))
    except Exception as exc:
        raise Refused(f"REFUSED — post build failed: {exc}") from exc
    post["candidate"] = {"manifest": manifest, "preparedAt": _now(),
                          "preparedBy": "Post pipeline"}
    _save(pkg, path)
    master = manifest["outputs"]["master16x9"]["path"]
    log(f"POST CANDIDATE — scene {scene}: {len(sources)} approved shots conformed, mixed, "
        f"captioned and QC-passed -> {pathlib.Path(master).name} (awaiting Final & Post review)")
    return master


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
            "compiledInstruction": {"seedancePrompt": _resolve_seedance_prompt(pkg, s)[0],
                                     "promptWords": s["promptWords"],
                                     "referenceSlots": s["referenceSlots"],
                                     "keyframePrompt": _resolve_keyframe_prompt(pkg, s),
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

    post = post_status(pkg, scene, episode)
    selected_post = (post["approved"] if post["approved"]["current"] else
                     post["candidate"] if post["candidate"]["current"] else None)
    post_manifest = selected_post.get("manifest") if selected_post else None
    conformed = ((post_manifest or {}).get("outputs") or {}).get("conformedPicture") or {}
    final_master = ((post_manifest or {}).get("outputs") or {}).get("master16x9") or {}
    animatic = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    if not animatic.exists():   # the pre-reclassification name (the frozen 2026-07-16 slate)
        animatic = HERE / "media" / f"{episode}_Scene{scene}_animatic.mp4"
    pack = {"episode": episode, "scene": str(scene), "generatedAt": _now(),
            "validation": pkg.get("validation"),
            "shots": cases,
            "timingSlate": _asset(str(animatic)) if animatic.exists() else None,
            "stitchedOutput": _asset(conformed.get("path")) if conformed.get("path") else None,
            "finalMaster": _asset(final_master.get("path")) if final_master.get("path") else None,
            "postManifest": post_manifest}
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
    md.append("Conformed picture: " + (
        f"`{os.path.basename(conformed['path'])}`" if conformed.get("path") else "MISSING"))
    md.append("Final 16:9 master: " + (
        f"`{os.path.basename(final_master['path'])}`" if final_master.get("path") else "MISSING"))
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


# Install the production safety contract only after every implementation function exists.
# The wrapper layer refuses stale/unapproved specialist inputs before any paid adapter runs.
import cb_safety as _cb_safety
_cb_safety.install(sys.modules[__name__])
import cb_transactions as _cb_transactions
_cb_transactions.install(sys.modules[__name__])


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
                 "dry_run": False}
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
            else:
                pos.append(a); i += 1
        ep = lambda n: pos[n] if len(pos) > n else "Ep1"
        if cmd == "voice":
            voice_scene(pos[0], ep(1))
        elif cmd == "voice-shot":
            pkg, pkg_path = load_pkg(pos[0], ep(2))
            voice_shot(pkg, pkg_path, pos[1], ep(2))
        elif cmd in ("animatic", "slate"):
            animatic_scene(pos[0], ep(1))
        elif cmd == "scenelook":
            generate_scenelook_plate(pos[0], ep(1),
                                     reference_path=(pos[2] if len(pos) > 2 else None))
        elif cmd == "approve-scenelook":
            approve_scenelook(pos[0], ep(1))
        elif cmd == "reject-scenelook":
            reject_scenelook(pos[0], pos[1], episode=ep(2))
        elif cmd == "scenelook-library":
            print(json.dumps(scenelook_reference_library(pos[0], ep(1)), indent=1))
        elif cmd == "select-scenelook-upload":
            select_scenelook_source(pos[0], "upload", ep(2), upload_path=pos[1])
        elif cmd == "select-scenelook-library":
            select_scenelook_source(pos[0], "library", ep(2), library_path=pos[1])
        elif cmd == "keyframe":
            keyframe_shot(pos[0], pos[1], ep(2))
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
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"])
        elif cmd == "fire":
            fire_shot(pos[0], pos[1], ep(2), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"])
        elif cmd == "approve":
            approve_shot(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1, ep(3))
        elif cmd == "reject":
            reject_shot(pos[0], pos[1], pos[2], category=flags["category"], episode=ep(3))
        elif cmd == "stitch":
            stitch_scene(pos[0], ep(1))
        elif cmd == "status":
            status(pos[0], ep(1))
        elif cmd == "metrics":
            metrics(pos[0], ep(1))
        elif cmd == "evidence":
            evidence_pack(pos[0], ep(1))
        else:
            print(f"unknown command {cmd}"); sys.exit(1)
    except Refused as e:
        print(str(e)); sys.exit(1)
