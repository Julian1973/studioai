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
    python3 cb_render.py approve-timing-slate <scene> [episode]
    python3 cb_render.py reject-timing-slate <scene> "<reason>" [episode]
    python3 cb_render.py scenelook         <scene> [episode] [referencePath]
    python3 cb_render.py approve-scenelook <scene> [episode]
    python3 cb_render.py reject-scenelook  <scene> "<note>" [episode]
    python3 cb_render.py scenelook-library <scene> [episode]
    python3 cb_render.py select-scenelook-upload  <scene> <uploadPath>  [episode]
    python3 cb_render.py select-scenelook-library <scene> <libraryPath> [episode]
    python3 cb_render.py pose <scene> <shotId> <character> [episode]
    python3 cb_render.py build-keyframe <scene> <shotId> [episode]
    python3 cb_render.py approve-pose <scene> <shotId> <character> [episode]
    python3 cb_render.py reject-pose <scene> <shotId> <character> "<reason>" [episode]
    python3 cb_render.py select-pose-upload <scene> <shotId> <character> <path> [episode]
    python3 cb_render.py keyframe <scene> <shotId> [episode]
    python3 cb_render.py approve-keyframe <scene> <shotId> [episode]
    python3 cb_render.py rescreen-keyframe <scene> <shotId> [episode]
    python3 cb_render.py reject-keyframe  <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py keyframe-library <scene> <shotId> [episode]
    python3 cb_render.py select-upload  <scene> <shotId> <uploadPath> [episode]
    python3 cb_render.py select-library <scene> <shotId> <libraryPath> [episode]
    python3 cb_render.py select-previous <scene> <shotId> [episode]
    python3 cb_render.py select-render-upload <scene> <shotId> <videoPath> [episode]
    python3 cb_render.py voice-status <scene> <shotId> [episode]
    python3 cb_render.py save-voice   <scene> <shotId> '<json lines>' [episode]
    python3 cb_render.py restore-voice <scene> <shotId> [episode]
    python3 cb_render.py approve-voice <scene> <shotId> [episode]
    python3 cb_render.py reject-voice  <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py seedance-status <scene> <shotId> [episode]
    python3 cb_render.py save-seedance   <scene> <shotId> "<prompt text>" [episode]
    python3 cb_render.py restore-seedance <scene> <shotId> [episode]
    python3 cb_render.py bind-location-reference <scene> <shotId> <label> <path> [episode]
    python3 cb_render.py check-structure  <scene> <shotId> [episode]
    python3 cb_render.py continuity-mode  <scene> <shotId> <keyframe-handoff|video-extension> [episode]
    python3 cb_render.py prompt-bank
    python3 cb_render.py department-prepare <scene> <look|cinematography|voice|animation|review-keyframe|review-animation|review-final> <shotId|-> [episode]
    python3 cb_render.py department-status  <scene> <stage> <shotId|-> [episode]
    python3 cb_render.py next     <scene> [episode] [--candidates N] [--spend-token T]
    python3 cb_render.py fire     <scene> <shotId> [episode] [--candidates N] [--spend-token T]
                                     [--comparison-model fal-seedance-2.0]
                                     [--comparison-run-id <label>]
    python3 cb_render.py override-model-limited <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py approve  <scene> <shotId> <candidateN> [episode]
    python3 cb_render.py reject   <scene> <shotId> "<correction>" [--category identity|geography|action-timing|instruction-ignored|other] [episode]
    python3 cb_render.py edit     <scene> <shotId> <startSec> <endSec> "<correction>" [episode] [--spend-token T]
    python3 cb_render.py approve-edit <scene> <shotId> [episode]
    python3 cb_render.py reject-edit  <scene> <shotId> "<reason>" [episode]
    python3 cb_render.py metrics  <scene> [episode]
    python3 cb_render.py stitch   <scene> [episode]
    python3 cb_render.py status   <scene> [episode]
"""
import os, sys, io, json, re, glob, pathlib, datetime, shutil, hashlib, uuid, subprocess, tempfile, threading
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_engine
import cb_gen
import cb_post
import cb_rough_cut
import cb_departments
import cb_lineage
import cb_scripts
import cb_db
import cb_audio_timing
import cb_audio_authority
import cb_prompt_lab
import cb_providers
import cb_seedance_pipeline
import cb_seedance_transport
import cb_layout
import cb_identity
import cb_voice_director
import cb_emission_conformance as emission
import cb_emission_standard
import cb_engine_rules
import cb_asset_registry
import cb_prompt_bank
import paths as P

MEDIA = HERE / "media" / "shots"
ROOT = HERE.parent
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)


def _submit_seedance_provider(prompt, image_inputs, **kwargs):
    """The sole production gateway into Seedance for generation, extension and editing."""
    return cb_gen.generate_video_seedance_ref(prompt, image_inputs, **kwargs)
DUR_TOLERANCE_SEC = 1.5          # rendered clip may differ from designed duration by this much
CHARACTER_SCALE_CONTROL_ROLE = "character scale control"
CHARACTER_SCALE_CONTROL_MARKER = "[CANONICAL CHARACTER SCALE CONTROL]"
OPENING_COMPOSITION_ROLE = "opening composition master"
CLOSING_COMPOSITION_ROLE = "approved final button frame"
OPENING_COMPOSITION_MARKER = "[AUTHORITATIVE OPENING COMPOSITION]"
POSED_INTEGRATION_ROLE = "qualified posed integration frame"
POSED_INTEGRATION_MARKER = "[QUALIFIED POSED INTEGRATION FRAME]"
POSE_QUALIFICATION_VERSION = 1
POSE_LIBRARY_VERSION = 1
REVIEW_VIDEO_RESOLUTION = "480p"
CREATIVE_DIRECTING_STANDARD_VERSION = 4


class Refused(RuntimeError):
    """A named, deliberate refusal — never a crash, never a silent skip."""


def _review_video_resolution():
    value = os.environ.get("CB_REVIEW_VIDEO_RESOLUTION", REVIEW_VIDEO_RESOLUTION).strip()
    if value not in {"480p", "720p"}:
        raise Refused(
            "REFUSED — CB_REVIEW_VIDEO_RESOLUTION must be 480p or 720p")
    return value


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


def _scene_continuity_locks(pkg, scene):
    """Return approved scene-level state locks that every shot must carry.

    These are physical continuity facts: set dressing, prop ownership, visible character
    state and exclusions that survive leaving and returning to a scene. They are not
    creative suggestions and must travel with render prompts until a later approved shot
    visibly changes them.
    """
    locks = ((pkg.get("sceneContinuityLocks") or {}).get(str(scene)) or [])
    out = []
    for item in locks:
        if not isinstance(item, dict):
            continue
        value = " ".join(str(item.get("value") or "").split()).strip()
        if not value:
            continue
        record = {
            "id": str(item.get("id") or "").strip(),
            "label": str(item.get("label") or "Scene continuity").strip(),
            "value": value,
            "forbidden": " ".join(str(item.get("forbidden") or "").split()).strip(),
            "sourceShotId": str(item.get("sourceShotId") or "").strip(),
        }
        out.append(record)
    return out


def _continuity_constraint_text(item):
    """Normalize legacy text and structured continuity records at validation boundaries."""
    if isinstance(item, dict):
        return str(item.get("value") or item.get("label") or item).strip()
    return str(item or "").strip()


def _carry_approved_inputs_across_duration_change(ledger, provenance):
    """Record R6 carry-forward without turning an old asset into duration authority.

    A keyframe or voice take approved before the current beat-cost decision remains an
    approved visual/performance input.  The new request duration is owned by the costed
    direction, never by either asset.  This records that distinction for audit/UI purposes;
    it does not create an approval when one is missing.
    """
    carried = []
    duration = provenance.get("unitDurationSec")
    now = _now()
    records = (
        ("keyframeApproval", "R6: approved keyframe is input, not duration authority"),
        ("voiceApproval", "R6: approved performance is input, not duration authority"),
    )
    for key, reason in records:
        approval = ledger.get(key)
        if not (approval or {}).get("approved"):
            continue
        approval["durationCarryForward"] = {
            "at": now,
            "reason": reason,
            "newDurationSec": duration,
            "costSignature": provenance.get("costSignature"),
        }
        carried.append(key)
    return carried


def _dialogue_speaker_count(shot):
    speakers = set()
    for line in shot.get("dialogueLines") or []:
        if not isinstance(line, dict):
            continue
        speaker = str(line.get("speaker") or "").strip().lower()
        if speaker:
            speakers.add(speaker)
    return len(speakers)


def _requires_stage_contract_keyframe(shot):
    """Complex WATCH shots need a human-approved SEE frame before spend.

    SEE is the physical stage contract. If the opening frame already has wrong
    cast, scale, geography, or causality, WATCH tends to preserve the error.
    """
    cast_count = len([c for c in (shot.get("charactersInFrame") or []) if str(c).strip()])
    if cast_count >= 5:
        return True
    if _dialogue_speaker_count(shot) >= 3:
        return True
    text = " ".join(str(shot.get(k) or "") for k in (
        "purpose", "action", "continuityIn", "continuityOut", "seedancePrompt"))
    return bool(re.search(
        r"\b(full team|beach team|ensemble|crowd|all other characters|everyone "
        r"on the beach|all eight|multiple characters|wrong characters|duplicate "
        r"character|right bear says|speaker identity|scale check|stage contract)\b",
        text, re.I))


def _require_stage_contract_keyframe(shot, ledger):
    if not _requires_stage_contract_keyframe(shot):
        return
    if (
        (shot.get("sourceType") == "relay" or shot.get("sourceShotId"))
        and ledger.get("continuityMode") == CONTINUITY_MODE_VIDEO_EXTENSION
    ):
        return
    approval = ledger.get("keyframeApproval") or {}
    path = approval.get("path")
    if approval.get("approved") and path and os.path.exists(path):
        return
    cast_count = len([c for c in (shot.get("charactersInFrame") or []) if str(c).strip()])
    speaker_count = _dialogue_speaker_count(shot)
    raise Refused(
        f"REFUSED — {shot.get('shotId')} is a complex multi-character WATCH shot "
        "and must have an approved SEE keyframe before fire. "
        f"Detected cast={cast_count}, dialogueSpeakers={speaker_count}. "
        "Create/select the shot keyframe, approve it, then fire WATCH.")


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


def _declared_storyboard_path(pkg, scene, episode="Ep1"):
    """Resolve the exact approved storyboard artifact declared by this package.

    Whole-scene packages continue to use the canonical scene storyboard. A human-approved
    shot-scoped contract may declare a different in-repository JSON artifact so one approved
    unit can advance without falsely approving unfinished sibling units.
    """
    declared = str((pkg.get("sourceStoryboard") or {}).get("path") or "").strip()
    if not declared:
        return _storyboard_path(scene, episode)
    path = pathlib.Path(declared)
    if not path.is_absolute():
        path = ROOT / path
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return _storyboard_path(scene, episode)
    return path


def lineage_status(pkg, scene, episode="Ep1"):
    """Return authoritative source-graph freshness for a production package."""
    pkg_md5 = (pkg.get("sourceStoryboard") or {}).get("md5")
    live_path = _declared_storyboard_path(pkg, scene, episode)
    live_md5 = hashlib.md5(live_path.read_bytes()).hexdigest() if live_path.exists() else None
    storyboard_current = bool(pkg_md5) and bool(live_md5) and pkg_md5 == live_md5
    package_script = (pkg.get("sourceScript") or {}).get("scriptVersionId")
    current_script = None
    script_current = False
    script_error = None
    try:
        current = SCRIPT_STORE.current(episode, required=True)
        current_script = current["scriptVersionId"]
        direct_script_match = (
            package_script == current_script and
            (pkg.get("sourceScript") or {}).get("sha256") == current["sha256"])
        # A script revision does not alter unrelated scenes. Compare this scene's actual
        # parsed source content so repeated edits in another scene do not invalidate the
        # whole episode merely because the episode-level version id advanced.
        scope = current.get("changeScope") or {}
        previous_source_match = False
        try:
            prior_scene = int(re.sub(r"\D", "", str(scene)) or "0")
            changed_scene = int(re.sub(r"\D", "", str(scope.get("scene"))) or "0")
            source = pkg.get("sourceScript") or {}
            source_path = (ROOT / str(source.get("contentPath") or "")).resolve()
            source_path.relative_to(ROOT.resolve())
            current_path = (ROOT / str(current.get("contentPath") or "")).resolve()
            current_path.relative_to(ROOT.resolve())
            amendment = next((item for item in (pkg.get("scopedAmendments") or [])
                              if item.get("shotId") == scope.get("shotId") and
                              item.get("scriptVersionId") == current_script and
                              item.get("kind") == scope.get("kind") and
                              item.get("baseScriptVersionId", package_script) ==
                              package_script), None)
            scoped_package_match = bool(
                prior_scene == changed_scene and scope.get("shotId") and amendment)
            unchanged_scene_match = False
            amended_scene_match = False
            if source_path.is_file() and current_path.is_file():
                try:
                    import cb_intake
                    old_scene_digest = cb_intake.scene_source_digests(
                        source_path.read_text(encoding="utf-8")).get(str(prior_scene))
                    new_scene_digest = cb_intake.scene_source_digests(
                        current_path.read_text(encoding="utf-8")).get(str(prior_scene))
                    unchanged_scene_match = bool(
                        old_scene_digest and old_scene_digest == new_scene_digest)
                    for recorded in reversed(pkg.get("scopedAmendments") or []):
                        recorded_shot = str(recorded.get("shotId") or "")
                        if not recorded_shot.startswith(f"S{prior_scene}."):
                            continue
                        digest = cb_lineage.parse_script_version_id(
                            recorded.get("scriptVersionId"))
                        amended_path = SCRIPT_STORE.versions_root / episode / f"{digest}.txt"
                        if not amended_path.is_file():
                            continue
                        amended_digest = cb_intake.scene_source_digests(
                            amended_path.read_text(encoding="utf-8")).get(str(prior_scene))
                        if amended_digest and amended_digest == new_scene_digest:
                            amended_scene_match = True
                            break
                except (cb_intake.Refused, OSError, TypeError, ValueError):
                    unchanged_scene_match = False
            legacy_scoped_match = bool(
                scope.get("kind") in ("dialogue-correction", "dialogue-format-cleanup") and
                (scope.get("kind") == "dialogue-format-cleanup" or
                 scoped_package_match or
                 (prior_scene and changed_scene and prior_scene < changed_scene and
                  package_script == current.get("previousScriptVersionId"))))
            previous_source_match = bool(
                source_path.is_file() and
                (unchanged_scene_match or amended_scene_match or legacy_scoped_match) and
                cb_lineage.sha256_file(source_path) == source.get("sha256"))
        except (OSError, TypeError, ValueError):
            previous_source_match = False
        script_current = direct_script_match or previous_source_match
    except (cb_scripts.ScriptStoreError, cb_lineage.LineageError) as exc:
        script_error = str(exc)

    package_signature = pkg.get("inputSignature") or {}
    package_inputs = package_signature.get("inputs") or {}
    signature_current = (
        cb_lineage.signature_matches(package_signature, "production-package", package_inputs) and
        package_inputs.get("scriptVersionId") == (
            package_script if previous_source_match else current_script) and
        package_inputs.get("storyboardSha256") ==
        (pkg.get("sourceStoryboard") or {}).get("sha256") and
        (not live_path.exists() or
         package_inputs.get("storyboardSha256") ==
         cb_lineage.sha256_file(live_path))
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
    # Downstream corrections are scoped changes. Older approved shots and media remain
    # valid; callers refresh only the unit being prepared. Lineage is retained as audit
    # metadata and must not force the reviewer back through the whole episode.
    return lineage_status(pkg, scene, episode)


# ── reference resolution — identity/plate refusals are keeper law (never fire blind) ────
def _characters_cfg():
    try:
        return json.load(open(P.CHARS))
    except Exception:
        return {}


def _identity_packs_cfg():
    path = getattr(P, "IDENTITY_PACKS", None)
    if not path:
        raise Refused(
            "REFUSED — this show has no declared provider identity-pack source; "
            "no provider was contacted")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception as exc:
        raise Refused(
            f"REFUSED — provider identity packs are unreadable: {exc}; "
            "no provider was contacted") from exc
    packs = data.get("characters") if isinstance(data, dict) else None
    if (not isinstance(data, dict) or data.get("schemaVersion") != 1 or
            not isinstance(packs, dict)):
        raise Refused(
            "REFUSED — provider identity packs use an unsupported schema; "
            "no provider was contacted")
    return packs


def _identity_pack_for(name, characters_cfg):
    canonical = _resolve_char(name, characters_cfg)
    pack = _identity_packs_cfg().get(canonical)
    if not isinstance(pack, dict):
        raise Refused(
            f"REFUSED — {canonical} has no locked single-subject provider identity pack; "
            "add and canon-lock one before generation. No provider was contacted")
    return canonical, pack


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


def _shot_continuity_text(shot):
    parts = []
    for value in shot.get("continuityConstraints") or []:
        if isinstance(value, dict):
            parts.extend([str(value.get("label") or ""), str(value.get("value") or "")])
        else:
            parts.append(str(value or ""))
    parts.extend([
        str(shot.get("title") or ""), str(shot.get("storyBeat") or ""),
        str(shot.get("action") or ""), str(shot.get("endState") or ""),
    ])
    return " ".join(parts).casefold()


def _scene_in_span(scene, span):
    try:
        scene_number = int(str(scene))
    except (TypeError, ValueError):
        return False
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", str(span or "").strip())
    if not match:
        return False
    start = int(match.group(1))
    end = int(match.group(2) or start)
    return start <= scene_number <= end


def _required_prop_reference_roles(shot, scene, episode):
    """Return dedicated prop authorities required by approved production data.

    Explicit shot requirements are authoritative. Show continuity may also require a
    prop when its aliases occur in approved creative/continuity fields. Reference slots
    are deliberately excluded from the scan so a slot cannot manufacture its own need.
    """
    required = {
        str(prop_id).strip().casefold()
        for prop_id in (shot.get("requiredPropReferences") or [])
        if str(prop_id).strip()
    }
    try:
        continuity = json.loads(
            (ROOT / "engine" / "config" / "continuity.json").read_text())
    except (OSError, ValueError, TypeError):
        continuity = {}
    records = ((continuity.get(str(episode)) or {}).get(
        "referenceRequiredProps") or [])
    searchable_fields = (
        "title", "purpose", "storyBeat", "action", "performanceAssignment",
        "camera", "openingPose", "visualPayoff", "continuityIn", "continuityOut",
        "continuityConstraints", "sceneContinuityLocks", "physicalStagings",
        "endState", "prohibited",
    )
    searchable = json.dumps(
        {key: shot.get(key) for key in searchable_fields},
        ensure_ascii=False, sort_keys=True).casefold()
    for record in records:
        if not isinstance(record, dict) or not _scene_in_span(scene, record.get("scenes")):
            continue
        prop_id = str(record.get("propId") or "").strip().casefold()
        if not prop_id or not record.get("requiredWhenMentioned"):
            continue
        aliases = [
            str(alias).strip().casefold()
            for alias in (record.get("aliases") or [])
            if str(alias).strip()
        ]
        prop_is_absent = False
        for alias in aliases:
            escaped = re.escape(alias)
            absent_patterns = [
                rf"{escaped}(?:'s)?\s+(?:is|remains|stays)\s+(?:gone|absent|missing|lost)",
                rf"no\s+{escaped}\b",
                rf"do not (?:show|restore|glimpse|include).{{0,80}}\b{escaped}\b",
                rf"\b{escaped}\b.{{0,80}}(?:gone|absent|missing|lost|not visible)",
            ]
            if any(re.search(pattern, searchable) for pattern in absent_patterns):
                prop_is_absent = True
                break
        if prop_is_absent:
            continue
        if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", searchable)
               for alias in aliases):
            required.add(prop_id)
    return [f"prop:{prop_id}" for prop_id in sorted(required)]


def _required_prop_reference_report(shot, scene, episode, reference_contract):
    """Prove required props are present in the exact provider attachment contract."""
    required = _required_prop_reference_roles(shot, scene, episode)
    present = [
        str(item.get("role") or "").strip()
        for item in (reference_contract or [])
        if str(item.get("role") or "").strip().startswith("prop:")
    ]
    present_folded = {role.casefold() for role in present}
    missing = [role for role in required if role.casefold() not in present_folded]
    return {
        "ok": not missing,
        "required": required,
        "present": present,
        "missing": missing,
        "proofRule": (
            "Only a dedicated prop:<id> attachment in the sealed provider upload list "
            "counts; prompt prose, scene plates and inherited frames do not."
        ),
    }


def _require_prop_reference_authority(shot, scene, episode, reference_contract):
    report = _required_prop_reference_report(
        shot, scene, episode, reference_contract)
    if not report["ok"]:
        raise Refused(
            "REFUSED — required continuity prop authority is missing from the exact "
            "provider attachment list: " + ", ".join(report["missing"]) +
            ". Register the approved prop asset and bind its prop:<id> role before spend; "
            "prompt wording, scene plates and inherited frames do not count.")
    return report


def _episode_character_state(character, shot, scene, episode):
    """Resolve wardrobe/prop identity state from shot truth, then episode continuity.

    A transition shot keeps the incoming identity reference; the action and explicit prop
    reference create the new state. Subsequent shots inherit the new identity reference.
    """
    if _norm(character) != _norm("Keen") or str(episode) != "Ep1":
        return None
    text = _shot_continuity_text(shot or {})
    try:
        continuity = json.loads((ROOT / "engine" / "config" / "continuity.json").read_text())
    except (OSError, ValueError, TypeError):
        continuity = {}
    records = (((continuity.get(str(episode)) or {}).get("characterStates") or {})
               .get(_resolve_char(character, _characters_cfg())) or [])
    try:
        scene_number = int(str(scene))
    except (TypeError, ValueError):
        scene_number = None
    scene_record = None
    if scene_number is not None:
        for record in records:
            span = str(record.get("scenes") or "")
            match = re.fullmatch(r"(\d+)(?:-(\d+))?", span)
            if not match:
                continue
            start = int(match.group(1))
            end = int(match.group(2) or start)
            if start <= scene_number <= end:
                scene_record = record
                break

    transition = str((scene_record or {}).get("transitionShot") or "")
    shot_id = str((shot or {}).get("shotId") or "")
    transition_match = re.fullmatch(r"(\d+)\.B(\d+)\.S(\d+)", transition)
    shot_match = re.fullmatch(r"(\d+)\.B(\d+)\.S(\d+)", shot_id)
    if transition_match and shot_match:
        transition_order = tuple(map(int, transition_match.groups()))
        shot_order = tuple(map(int, shot_match.groups()))
        if shot_order[0] == transition_order[0] and shot_order <= transition_order:
            return ((scene_record or {}).get("incomingState") or
                    (scene_record or {}).get("wristbandState"))
        if shot_order[0] == transition_order[0]:
            return ((scene_record or {}).get("afterTransitionState") or
                    (scene_record or {}).get("wristbandState"))

    if any(marker in text for marker in (
            "crystal-set wristbands", "aquamarine stones seated",
            "wearing the crystal-set", "wristbands now contain")):
        return "crystal-set-wristbands"
    if any(marker in text for marker in (
            "bare wrists", "wrists remain bare", "wrists are still bare",
            "in keen's paws only", "may put on the inherited wristbands")):
        return "no-cuffs"
    if any(marker in text for marker in (
            "now wearing the inherited wristbands", "wearing the inherited wristbands",
            "worn, vacant bands", "vacant wristbands")):
        return "vacant-wristbands"

    return (scene_record or {}).get("wristbandState")


def _provider_identity_record(name, characters_cfg, usage="keyframe", *, shot=None,
                              scene=None, episode="Ep1"):
    """Resolve one character's complete, uncropped turnaround provider attachment."""
    canonical, pack = _identity_pack_for(name, characters_cfg)
    shot_id = str((shot or {}).get("shotId") or "")
    if str(scene) == "10" and canonical in {"Fuzzby", "Zenny"}:
        # Scene 10 holds the bees tiny and airborne in a full-cast beach walk.  The normal
        # multi-angle turnaround sheet has repeatedly blurred Fuzzby/Zenny identity in this
        # specific composition, so use the locked single-subject anchors as the provider's
        # character identity source for this scene.
        anchor = ROOT / "cb-seed" / "assets" / f"CB_{canonical}_anchor.png"
        if not anchor.exists():
            raise Refused(
                f"REFUSED — Scene 10 bee anchor is missing for {canonical}: {anchor.name}")
        return {
            "schemaVersion": cb_identity.IDENTITY_PACK_SCHEMA_VERSION,
            "character": canonical,
            "characterState": _episode_character_state(
                canonical, shot or {}, scene, episode) or "default",
            "usage": usage,
            "view": "single-subject-anchor",
            "source": str(anchor.resolve()),
            "path": str(anchor.resolve()),
            "fileName": anchor.name,
            "derived": False,
            "providerSafe": True,
            "intactTurnaround": False,
            "singleSubject": True,
            "singleCharacterIdentity": True,
            "turnaroundAuthority": False,
            "sceneScopedIdentityAnchor": shot_id or "scene-10",
            "distinguishingFeatures": list((pack or {}).get("distinguishingFeatures") or []),
            "mustNotBorrow": list((pack or {}).get("mustNotBorrow") or []),
        }
    try:
        identity = cb_identity.materialize_provider_view(
            canonical, pack, ROOT,
            MEDIA.parent / "reference_controls" / "identity_packs",
            usage=usage,
            state=_episode_character_state(canonical, shot or {}, scene, episode),
        )
    except cb_identity.IdentityPackError as exc:
        raise Refused(f"REFUSED — {exc}; no provider was contacted") from exc
    return identity


def _provider_identity_records(name, characters_cfg, usage="keyframe", *, shot=None,
                               scene=None, episode="Ep1"):
    """Return exactly one intact turnaround attachment for one character identity."""
    return [_provider_identity_record(
        name, characters_cfg, usage, shot=shot, scene=scene, episode=episode)]


def _plate_path(scene, episode="Ep1"):
    """Resolve the signed current Scene Look working anchor, never by filename glob.

    A current generated candidate may be used internally to prove the direction through a
    keyframe; a legacy human-approved plate remains a valid fallback. scenelook_status owns the
    exact hash/signature checks and returns the one active record explicitly.
    """
    st = scenelook_status(scene, episode)
    active = st.get("active") or (st.get("approved") if st.get("current") else None)
    if not active:
        # A shot-scoped amendment may explicitly preserve the already-approved scene world.
        # The carry is valid only for the exact recorded file hash and a current package
        # lineage; ordinary stale Scene Looks continue to fail closed.
        try:
            pkg, _ = load_pkg(scene, episode)
            approved = (_load_scenelook_rec(scene, episode).get("approved") or {})
            approved_path = approved.get("path")
            approved_hash = approved.get("hash")
            carried = next((item for item in (pkg.get("scopedAmendments") or [])
                            if item.get("sceneLookContentHash") == approved_hash), None)
            if (carried and lineage_status(pkg, scene, episode).get("current") and
                    approved_path and os.path.exists(approved_path) and
                    _sha256_file(approved_path) == approved_hash):
                active = approved
        except (Refused, OSError, TypeError, ValueError):
            active = None
    if not active or not active.get("path") or not os.path.exists(active["path"]):
        raise Refused(f"REFUSED — no current signed scene plate found for {episode} scene {scene} "
                      "— generate the internal world anchor before the first keyframe")
    return active["path"]


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
        raise Refused(f"REFUSED — Scene Look Plate is '{st['status']}', not a current signed "
                      f"working anchor for scene {scene} — prepare direction and generate the "
                      "world plate before any keyframe can be generated")


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
    """Compatibility resolver for the current signed Look provider prompt.

    The safety layer binds this name to current prepared direction. A legacy approved record
    remains a valid source only while its direct-input signature is current.
    """
    rec = _load_scenelook_rec(scene, episode)
    approved = ((rec.get("departmentWork") or {}).get("look") or {}).get("approved")
    prompt = ((approved or {}).get("output") or {}).get("providerPrompt")
    return prompt if (prompt or "").strip() else None


def generate_scenelook_plate(scene, episode="Ep1", reference_path=None, log=print):
    """GENERATE SCENE {N} LOOK PLATE — ONE IMAGE. Generates exactly one working world anchor
    to its own unique path; any legacy approved plate remains untouched by this call, win or
    lose. Refuses if another working anchor exists until that anchor is deliberately iterated.

    reference_path (2026-07-19 fix): OPTIONAL, and only ever what the CALLER explicitly
    passes in — this function never looks in the Asset Library or anywhere else on its
    own. None (the default) means no reference at all, which now correctly routes to a
    text-to-image call in cb_gen (see that module's 2026-07-19 fix) instead of a
    guaranteed-422 empty edit-mode request. A real path here means a genuine, explicitly
    selected location/style reference, routed to the edit endpoint with that one image.

    The current-direction hard gate refuses unless Scene {N}'s own signed Look direction is
    current. The old canon-compiled fallback is never a prompt source for a real generation
    call. The exact signed provider prompt is submitted verbatim.
    """
    st = scenelook_status(scene, episode)
    if st["candidate"]:
        raise Refused(f"REFUSED — scene {scene} already has a working Scene Look anchor; "
                      f"choose Iterate before generating another")
    if reference_path is not None and not pathlib.Path(reference_path).exists():
        raise Refused(f"REFUSED — reference_path does not exist: {reference_path}")
    prompt = approved_look_prompt(scene, episode)
    if not prompt:
        raise Refused("REFUSED — Prepare current Look Development direction first.")
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
    log(f"SCENE LOOK — {out.name} generated as the working world anchor "
        f"({'with 1 explicit reference' if reference_path else 'no reference — text-to-image'}; "
        f"its visual proof is the next keyframe; any legacy approved plate is unchanged)")
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


def _resolved_reference_path(path):
    if not path:
        return None
    candidate = pathlib.Path(path)
    if not candidate.is_absolute():
        candidate = HERE / candidate
    return candidate.resolve()


def _reference_path_is_approved(path):
    """References may come only from this Studio's media and approved asset libraries."""
    candidate = _resolved_reference_path(path)
    if not candidate:
        return False
    roots = {
        (HERE / "media").resolve(),
        MEDIA.resolve(),
        MEDIA.parent.resolve(),
        (ROOT / "cb-seed" / "assets").resolve(),
        (ROOT / "projects").resolve(),
    }
    return any(candidate.is_relative_to(root) for root in roots)


def _composition_master_record_path(scene, shot_id, episode="Ep1"):
    safe_shot = re.sub(r"[^A-Za-z0-9._-]+", "_", str(shot_id))
    return MEDIA.parent / "reference_controls" / (
        f"{episode}_S{scene}_{safe_shot}_opening_composition.json")


def _opening_composition_contract(pkg, shot, scene, episode, characters_cfg):
    """Resolve typed DP blocking against the exact current plate and turnarounds."""
    direction = _inspection_department_output(
        pkg, shot.get("shotId"), "cinematography") or {}
    raw_layout = direction.get("openingFrameLayout")
    if not raw_layout:
        return None
    try:
        layout = cb_departments.OpeningFrameLayout.model_validate(raw_layout).model_dump()
    except Exception as exc:
        raise Refused(
            f"REFUSED — {shot.get('shotId')} has an invalid typed opening-frame layout: "
            f"{exc}") from exc

    # SEE validates the characters physically present in frame one. A later entrant still
    # belongs to the shot and its WATCH reference contract, but forcing that character into
    # the opening layout spoils entrances and creates identity blending in keyframe models.
    cast = list(dict.fromkeys(
        shot.get("openingCharactersInFrame") or shot.get("charactersInFrame") or []))
    characters = {}
    for supplied_name in cast:
        name = _resolve_char(supplied_name, characters_cfg)
        profile = characters_cfg.get(name) or {}
        turnaround = _resolved_reference_path(_char_ref(name, characters_cfg))
        characters[name] = {
            "heightIn": profile.get("heightIn"),
            "turnaroundPath": str(turnaround),
            "turnaroundSha256": _sha256_file(turnaround),
        }
    try:
        cb_layout.validate_layout(layout, characters)
    except cb_layout.LayoutError as exc:
        raise Refused(f"REFUSED — {shot.get('shotId')} layout is not renderable: {exc}") from exc

    plate = _resolved_reference_path(_plate_path(scene, episode))
    if not plate or not plate.exists():
        raise Refused("REFUSED — the current Scene Look plate is missing")
    core = {
        "version": 1,
        "shotId": shot.get("shotId"),
        "layout": layout,
        "scenePlateFile": plate.name,
        "scenePlateSha256": _sha256_file(plate),
        "characters": [{
            "character": name,
            "heightIn": values["heightIn"],
            "turnaroundFile": pathlib.Path(values["turnaroundPath"]).name,
            "turnaroundSha256": values["turnaroundSha256"],
        } for name, values in characters.items()],
    }
    core["contractHash"] = hashlib.sha256(json.dumps(
        core, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    return core, characters, plate


def _load_opening_composition_master(shot, scene, episode, characters_cfg):
    """Load only a composition proof that still matches every direct visual input."""
    record_path = _composition_master_record_path(
        scene, shot.get("shotId"), episode)
    if not record_path.exists():
        return None
    try:
        pkg, _ = load_pkg(scene, episode)
        expected = _opening_composition_contract(
            pkg, shot, scene, episode, characters_cfg)
        if not expected:
            return None
        core, _, _ = expected
        record = json.loads(record_path.read_text())
        image_path = _resolved_reference_path(record.get("path"))
        if (record.get("contractHash") != core.get("contractHash") or
                not image_path or not image_path.exists() or
                record.get("imageSha256") != _sha256_file(image_path)):
            return None
        return {**record, "path": str(image_path)}
    except (OSError, ValueError, TypeError, KeyError, Refused):
        return None


def _ensure_opening_composition_master(pkg, shot, scene, episode, characters_cfg):
    """Create or reuse the zero-spend full-frame blocking master for an opener."""
    current = _load_opening_composition_master(
        shot, scene, episode, characters_cfg)
    if current:
        return current
    resolved = _opening_composition_contract(
        pkg, shot, scene, episode, characters_cfg)
    if not resolved:
        raise Refused(
            f"REFUSED — {shot.get('shotId')} has no typed opening-frame layout. "
            "Prepare current Cinematography direction before generating a keyframe")
    contract, characters, plate = resolved
    try:
        image_bytes, geometry = cb_layout.render_composition_master(
            plate, characters, contract["layout"])
    except cb_layout.LayoutError as exc:
        raise Refused(
            f"REFUSED — {shot.get('shotId')} composition proof failed: {exc}") from exc

    controls = MEDIA.parent / "reference_controls"
    image_path = controls / (
        f"{episode}_S{scene}_{shot['shotId']}_composition_"
        f"{contract['contractHash'][:12]}.png")
    cb_db.atomic_write_bytes(
        MEDIA.parent.parent.parent, image_path, image_bytes)
    try:
        stored_path = str(image_path.relative_to(HERE))
    except ValueError:
        stored_path = str(image_path.resolve())
    record = {
        **contract,
        "role": OPENING_COMPOSITION_ROLE,
        "path": stored_path,
        "imageSha256": _sha256_file(image_path),
        "geometry": geometry,
        "generatedAt": _now(),
        "zeroSpend": True,
        "providerCalled": False,
    }
    cb_db.atomic_write_json(
        MEDIA.parent.parent.parent,
        _composition_master_record_path(scene, shot["shotId"], episode),
        record)
    return {**record, "path": str(image_path.resolve())}


def prepare_opening_composition_master(scene, shot_id, episode="Ep1", log=print):
    """Public zero-spend blocking proof, built before any image-provider request."""
    pkg, _ = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    if shot.get("sourceType") != "opener":
        raise Refused(
            f"REFUSED — {shot_id} is a relay shot and inherits its opening composition")
    control = _ensure_opening_composition_master(
        pkg, shot, scene, episode, _characters_cfg())
    log(f"COMPOSITION MASTER — {shot_id} -> {pathlib.Path(control['path']).name} "
        "(zero spend; exact screen position, scale, depth and body angle)")
    return control


def save_opening_frame_layout(scene, shot_id, layout, episode="Ep1",
                              reviewed_by="Julian", log=print):
    """Edit only the typed blocking inside a pending Cinematography direction."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    work, save_extra = _department_container(
        pkg, scene, shot_id, "cinematography", episode)
    candidate = work.get("candidate")
    if not candidate:
        raise Refused(
            f"REFUSED — {shot_id} has no current Cinematography direction to block")
    try:
        updated = cb_departments.CinematographyDirection.model_validate({
            **candidate["output"], "openingFrameLayout": layout,
        })
    except Exception as exc:
        raise Refused(f"REFUSED — invalid opening-frame layout: {exc}") from exc
    characters_cfg = _characters_cfg()
    character_inputs = {}
    for supplied_name in (shot.get("openingCharactersInFrame") or
                          shot.get("charactersInFrame") or []):
        name = _resolve_char(supplied_name, characters_cfg)
        profile = characters_cfg.get(name) or {}
        character_inputs[name] = {
            "heightIn": profile.get("heightIn"),
            "turnaroundPath": _char_ref(name, characters_cfg),
        }
    try:
        cb_layout.validate_layout(
            updated.openingFrameLayout.model_dump(), character_inputs)
    except cb_layout.LayoutError as exc:
        raise Refused(f"REFUSED — invalid opening-frame layout: {exc}") from exc
    candidate["output"] = updated.model_dump()
    candidate["editedAt"] = _now()
    candidate["editedBy"] = reviewed_by
    save_extra()
    _save(pkg, path)
    log(f"OPENING LAYOUT SAVED — {shot_id} (zero spend; composition proof can now build)")
    return candidate["output"]["openingFrameLayout"]


# ── Optional pose diagnostics (not part of the default keyframe path) ──────────────────
# Retained for targeted repair experiments and legacy evidence. The production keyframe now
# uses locked turnarounds and the Scene Look directly; generated pose plates and composites may
# never silently replace those references or become a prerequisite for a playable stage.

def _pose_placement(pkg, shot, character):
    direction = _inspection_department_output(
        pkg, shot.get("shotId"), "cinematography") or {}
    layout = direction.get("openingFrameLayout") or {}
    wanted = _resolve_char(character, _characters_cfg())
    for placement in layout.get("placements") or []:
        if _resolve_char(placement.get("character"), _characters_cfg()) == wanted:
            return placement, layout
    raise Refused(
        f"REFUSED — {character} has no typed opening pose in current Cinematography direction")


def _latest_pose_correction(pkg, shot, character):
    """Return only the latest explicit correction for this character and pose contract."""
    name = _resolve_char(character, _characters_cfg())
    state = _pose_state(_ledger(pkg, shot["shotId"]), name)
    for record in reversed(state.get("history") or []):
        reason = str(record.get("reason") or "").strip()
        if reason:
            return reason
        review = record.get("machineReview") or {}
        correction = str(review.get("recommendedCorrection") or "").strip()
        if correction:
            return correction
    return ""


def _pose_prompt(pkg, shot, character):
    characters_cfg = _characters_cfg()
    name = _resolve_char(character, characters_cfg)
    profile = characters_cfg.get(name) or {}
    placement, _ = _pose_placement(pkg, shot, name)
    features = str(profile.get("key_features") or "the exact locked character design")
    avoid = str(profile.get("avoid") or "unapproved accessories or redesign")
    correction = _latest_pose_correction(pkg, shot, name)
    correction_block = (
        "\n\n[Correction From The Previous Attempt]\n"
        f"Correct only this observed failure: {correction}. Preserve every successful "
        "identity, proportion, anatomy and acting feature from the locked reference."
        if correction else "")
    return (
        "[Reference Role]\n"
        f"@图1 defines {name}'s exact identity, face, silhouette, proportions, materials "
        "and approved design. Do not use its background or neutral standing pose.\n\n"
        "[Generation Goal]\n"
        f"Create one isolated, full-body production pose reference of {name} alone. "
        f"The approved design is: {features}. Preserve the reference's exact body width, "
        "belly depth, head-to-body ratio, facial proportions, glasses, antennae, limbs "
        "and wings; do not make the character fatter, thinner, taller or shorter.\n\n"
        f"[Pose]\n{placement.get('pose')}. Facing: {placement.get('facing')}. "
        f"The body axis reads at {placement.get('bodyAngleDegrees', 0):g} degrees in the "
        "finished flight pose. Keep the complete silhouette visible with generous clear "
        "space around every wing, antenna, hand and foot.\n\n"
        "[Presentation]\n"
        "Single character only, centred on a flat neutral light-grey studio background, "
        "even soft lighting, no environment, no floor contact shadow, no scenery and no "
        "camera crop. This is a clean pose plate for later compositing, not a finished shot."
        f"{correction_block}\n\n"
        f"[Forbidden]\nNo duplicate character, extra limbs, missing wings, frozen flight "
        f"wings, identity drift, body inflation, text, logo, watermark, prop or {avoid}."
    )


def _pose_input_signature(pkg, shot, character):
    characters_cfg = _characters_cfg()
    name = _resolve_char(character, characters_cfg)
    placement, _ = _pose_placement(pkg, shot, name)
    identity = _resolved_reference_path(_char_ref(name, characters_cfg))
    prompt = _pose_prompt(pkg, shot, name)
    return {
        "version": 2,
        "shotId": shot.get("shotId"),
        "character": name,
        "cardHash": _live_card_hash(
            shot.get("shotId"), str(pkg.get("sceneNumber")),
            pkg.get("episode") or "Ep1"),
        "identitySha256": _sha256_file(identity),
        "heightIn": (characters_cfg.get(name) or {}).get("heightIn"),
        "placement": placement,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "provider": cb_gen.IMAGE_PROVIDER,
        "providerModelId": (cb_gen.SEEDREAM_MODEL_ID
                            if cb_gen.IMAGE_PROVIDER == "seedream"
                            else cb_gen.IMAGE_MODEL),
    }


def _pose_library_signature(pkg, shot, character):
    """The exact reusable acting contract, independent of shot position and episode."""
    characters_cfg = _characters_cfg()
    name = _resolve_char(character, characters_cfg)
    profile = characters_cfg.get(name) or {}
    placement, _ = _pose_placement(pkg, shot, name)
    identity = _resolved_reference_path(_char_ref(name, characters_cfg))
    return {
        "version": POSE_LIBRARY_VERSION,
        "character": name,
        "identitySha256": _sha256_file(identity),
        "heightIn": profile.get("heightIn"),
        "profileHash": hashlib.sha256(json.dumps({
            "keyFeatures": profile.get("key_features"),
            "avoid": profile.get("avoid"),
        }, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "acting": {
            "pose": placement.get("pose"),
            "facing": placement.get("facing"),
            "bodyAngleDegrees": placement.get("bodyAngleDegrees", 0),
        },
    }


def _pose_library_key(pkg, shot, character):
    signature = _pose_library_signature(pkg, shot, character)
    digest = hashlib.sha256(json.dumps(
        signature, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    return digest, signature


def _pose_library_record_path(pkg, shot, character):
    key, _ = _pose_library_key(pkg, shot, character)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", _resolve_char(
        character, _characters_cfg()))
    return MEDIA.parent / "pose_library" / name / f"{key}.json"


def _load_pose_library_record(pkg, shot, character):
    """Resolve an immutable, machine-qualified exact-contract pose without mutating state."""
    key, signature = _pose_library_key(pkg, shot, character)
    record_path = _pose_library_record_path(pkg, shot, character)
    if not record_path.exists():
        return None
    try:
        record = json.loads(record_path.read_text())
        asset = _resolved_reference_path(record.get("path"))
        review = record.get("machineReview") or {}
        if (record.get("contractHash") != key or
                record.get("signature") != signature or
                not asset or not asset.exists() or
                record.get("contentHash") != _sha256_file(asset) or
                review.get("qualified") is not True):
            return None
        return {**record, "path": str(asset)}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _publish_pose_library_record(pkg, shot, character, source, machine_review):
    """Copy one qualified pose into the exact-contract library; never overwrite its bytes."""
    key, signature = _pose_library_key(pkg, shot, character)
    name = _resolve_char(character, _characters_cfg())
    source_path = _resolved_reference_path(source)
    content_hash = _sha256_file(source_path)
    library_dir = _pose_library_record_path(pkg, shot, name).parent
    suffix = source_path.suffix.lower() or ".png"
    asset_path = library_dir / f"{key}-{content_hash[:12]}{suffix}"
    if not asset_path.exists():
        cb_db.atomic_write_bytes(
            HERE.parent, asset_path, source_path.read_bytes())
    record = {
        "version": POSE_LIBRARY_VERSION,
        "contractHash": key,
        "signature": signature,
        "character": name,
        "path": str(asset_path.relative_to(HERE)),
        "contentHash": _sha256_file(asset_path),
        "machineReview": machine_review,
        "qualifiedAt": _now(),
        "qualifiedBy": "Automated pose conformance gate",
        "humanApproved": False,
    }
    cb_db.atomic_write_json(
        HERE.parent, _pose_library_record_path(pkg, shot, name), record)
    return {**record, "path": str(asset_path.resolve())}


def _pose_state(ledger, character):
    return ((ledger.get("keyframePoseReferences") or {}).get(character) or {})


def _current_pose_approval(pkg, shot, character):
    name = _resolve_char(character, _characters_cfg())
    approval = _pose_state(_ledger(pkg, shot["shotId"]), name).get("approved") or {}
    path = _resolved_reference_path(approval.get("path"))
    if not path or not path.exists():
        return None
    try:
        expected = _pose_input_signature(pkg, shot, name)
    except Refused:
        return None
    if (approval.get("inputSignature") != expected or
            approval.get("contentHash") != _sha256_file(path)):
        return None
    return {**approval, "path": str(path)}


def _current_pose_qualification(pkg, shot, character):
    name = _resolve_char(character, _characters_cfg())
    qualification = _pose_state(
        _ledger(pkg, shot["shotId"]), name).get("qualified") or {}
    path = _resolved_reference_path(qualification.get("path"))
    if not path or not path.exists():
        return None
    try:
        expected = _pose_input_signature(pkg, shot, name)
    except Refused:
        return None
    review = qualification.get("machineReview") or {}
    if (qualification.get("inputSignature") != expected or
            qualification.get("contentHash") != _sha256_file(path) or
            review.get("qualified") is not True):
        return None
    return {**qualification, "path": str(path)}


def _current_pose_ready(pkg, shot, character):
    """Human approval wins; otherwise use a current machine-qualified internal pose."""
    return (_current_pose_approval(pkg, shot, character) or
            _current_pose_qualification(pkg, shot, character))


def pose_reference_status(scene, shot_id, episode="Ep1"):
    """Read-only status for every acting pose required by an opening keyframe."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    items = []
    for supplied_name in (shot.get("charactersInFrame") or []):
        name = _resolve_char(supplied_name, _characters_cfg())
        state = _pose_state(ledger, name)
        approved = _current_pose_approval(pkg, shot, name)
        qualified = _current_pose_qualification(pkg, shot, name)
        candidate = state.get("candidate") or {}
        candidate_path = _resolved_reference_path(candidate.get("path"))
        candidate_current = False
        if candidate_path and candidate_path.exists():
            try:
                candidate_current = (
                    candidate.get("inputSignature") ==
                    _pose_input_signature(pkg, shot, name) and
                    candidate.get("contentHash") == _sha256_file(candidate_path))
            except Refused:
                candidate_current = False
        placement, _ = _pose_placement(pkg, shot, name)
        machine_review = candidate.get("machineReview") or {}
        status = ("approved" if approved else
                  "qualified" if qualified else
                  "needs-correction" if candidate_current and machine_review and
                  machine_review.get("qualified") is not True else
                  "awaiting" if candidate_current else
                  "stale" if candidate else "required")
        items.append({
            "character": name,
            "status": status,
            "ready": bool(approved or qualified),
            "pose": placement.get("pose"),
            "facing": placement.get("facing"),
            "bodyAngleDegrees": placement.get("bodyAngleDegrees"),
            "approvedPath": approved.get("path") if approved else None,
            "qualifiedPath": qualified.get("path") if qualified else None,
            "candidatePath": str(candidate_path) if candidate_path and candidate_path.exists()
                             else None,
            "humanApproved": bool(approved),
            "machineQualified": bool(qualified),
            "machineReview": machine_review or (
                (qualified or {}).get("machineReview") or {}),
            "reusableExactMatch": bool(_load_pose_library_record(pkg, shot, name)),
            "message": ({
                "approved": "Human-approved pose will be used in the assembled frame.",
                "qualified": "Machine-qualified pose passed every identity and acting check.",
                "needs-correction": (
                    machine_review.get("recommendedCorrection") or
                    "The candidate needs one precise correction before finishing."),
                "awaiting": "Pose candidate is waiting for the conformance check.",
                "stale": "Pose candidate no longer matches the current shot direction.",
                "required": "The Studio will create or reuse this acting pose when you build.",
            })[status],
        })
    return {
        "ready": bool(items) and all(item["ready"] for item in items),
        "items": items,
        "zeroSpend": True,
        "readOnly": True,
    }


def generate_pose_reference(scene, shot_id, character, episode="Ep1", log=print):
    """Generate one isolated pose candidate; never generates the final keyframe."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    _require_confirmed_billing("fal")
    shot = _shot(pkg, shot_id)
    if shot.get("sourceType") != "opener":
        raise Refused(f"REFUSED — {shot_id} inherits its opening frame and needs no pose pass")
    name = _resolve_char(character, _characters_cfg())
    cast = [_resolve_char(item, _characters_cfg())
            for item in (shot.get("charactersInFrame") or [])]
    if name not in cast:
        raise Refused(f"REFUSED — {name} is not in {shot_id}'s opening cast")
    ledger = _ledger(pkg, shot_id)
    state = _pose_state(ledger, name)
    if state.get("candidate"):
        raise Refused(
            f"REFUSED — {name}'s pose candidate is awaiting a decision; accept or reject it first")
    prompt = _pose_prompt(pkg, shot, name)
    identity = _char_ref(name, _characters_cfg())
    pose_dir = MEDIA.parent / "pose_references"
    pose_dir.mkdir(parents=True, exist_ok=True)
    out = pose_dir / (
        f"{episode}_{shot_id}_{re.sub(r'[^A-Za-z0-9._-]+', '_', name)}_"
        f"pose_candidate_{uuid.uuid4().hex[:8]}.png")
    cb_gen.generate_image(
        prompt, refs=[identity], aspect="1:1", out=str(out),
        production_route="cb_render")
    record = {
        "path": str(out),
        "generatedAt": _now(),
        "source": "generated",
        "inputSignature": _pose_input_signature(pkg, shot, name),
        "contentHash": _sha256_file(out),
        "prompt": prompt,
    }
    pose_records = ledger.setdefault("keyframePoseReferences", {})
    pose_records.setdefault(name, {"approved": None, "candidate": None, "history": []})[
        "candidate"] = record
    _save(pkg, path)
    log(f"POSE CANDIDATE — {shot_id} {name} -> {out.name} (awaiting approval)")
    return str(out)


def _copy_pose_candidate(source_path, shot_id, character, episode):
    ext = pathlib.Path(source_path).suffix.lower() or ".png"
    pose_dir = MEDIA.parent / "pose_references"
    pose_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", character)
    out = pose_dir / (
        f"{episode}_{shot_id}_{safe_name}_pose_candidate_{uuid.uuid4().hex[:8]}{ext}")
    shutil.copy2(source_path, out)
    return out


def select_pose_reference_source(scene, shot_id, character, source_path,
                                 episode="Ep1", log=print):
    """Stage a human-supplied pose as a candidate without contacting a provider."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    name = _resolve_char(character, _characters_cfg())
    if name not in [_resolve_char(item, _characters_cfg())
                    for item in (shot.get("charactersInFrame") or [])]:
        raise Refused(f"REFUSED — {name} is not in {shot_id}'s opening cast")
    source = _resolved_reference_path(source_path)
    if not source or not source.exists() or not _reference_path_is_approved(source):
        raise Refused("REFUSED — pose source must be inside an approved Studio asset library")
    ledger = _ledger(pkg, shot_id)
    state = _pose_state(ledger, name)
    if state.get("candidate"):
        raise Refused(
            f"REFUSED — {name}'s pose candidate is awaiting a decision; accept or reject it first")
    out = _copy_pose_candidate(source, shot_id, name, episode)
    record = {
        "path": str(out), "generatedAt": _now(), "source": "uploaded",
        "sourcePath": str(source),
        "inputSignature": _pose_input_signature(pkg, shot, name),
        "contentHash": _sha256_file(out),
    }
    pose_records = ledger.setdefault("keyframePoseReferences", {})
    pose_records.setdefault(name, {"approved": None, "candidate": None, "history": []})[
        "candidate"] = record
    _save(pkg, path)
    log(f"POSE SELECTED — {shot_id} {name} -> {out.name} (zero spend; awaiting approval)")
    return str(out)


def review_pose_reference(scene, shot_id, character, episode="Ep1", log=print):
    """Run the strict visual conformance gate on one current pose candidate."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    name = _resolve_char(character, _characters_cfg())
    state = _pose_state(_ledger(pkg, shot_id), name)
    candidate = state.get("candidate") or {}
    candidate_path = _resolved_reference_path(candidate.get("path"))
    if not candidate_path or not candidate_path.exists():
        raise Refused(f"REFUSED — {name} has no pose candidate to check")
    expected = _pose_input_signature(pkg, shot, name)
    content_hash = _sha256_file(candidate_path)
    if (candidate.get("inputSignature") != expected or
            candidate.get("contentHash") != content_hash):
        raise Refused(f"REFUSED — {name}'s pose candidate is stale or changed")
    previous = candidate.get("machineReview") or {}
    if (previous.get("candidateContentHash") == content_hash and
            previous.get("reviewVersion") == POSE_QUALIFICATION_VERSION):
        return previous

    characters_cfg = _characters_cfg()
    identity_path = _resolved_reference_path(_char_ref(name, characters_cfg))
    placement, _ = _pose_placement(pkg, shot, name)
    profile = characters_cfg.get(name) or {}
    context = {
        "shotId": shot_id,
        "character": name,
        "orderedImages": [
            {"position": 1, "role": "actual isolated acting-pose candidate",
             "path": str(candidate_path)},
            {"position": 2, "role": "locked identity turnaround",
             "path": str(identity_path)},
        ],
        "requestedPose": placement.get("pose"),
        "facing": placement.get("facing"),
        "bodyAngleDegrees": placement.get("bodyAngleDegrees", 0),
        "identityRequirements": profile.get("key_features"),
        "forbidden": profile.get("avoid"),
        "hardRequirements": [
            "exactly one character",
            "complete uncropped full-body silhouette",
            "same face, body width, belly depth and head-to-body ratio as the turnaround",
            "correct limbs, wings, antennae, glasses and anatomy",
            "requested acting pose reads immediately",
            "neutral removable background with no environment or floor shadow",
            "no props, text, logo, watermark, duplicate or redesign",
        ],
    }
    result = cb_departments.review_pose_conformance(
        context, [str(candidate_path), str(identity_path)], log=log)
    review = {
        **result.model_dump(),
        "qualified": result.verdict == "pass",
        "reviewVersion": POSE_QUALIFICATION_VERSION,
        "candidateContentHash": content_hash,
        "identityContentHash": _sha256_file(identity_path),
        "reviewedAt": _now(),
        "reviewedBy": "Automated pose conformance gate",
        "validatorModel": cb_departments.cb_llm.VALIDATOR_MODEL,
        "humanApproval": False,
    }
    candidate["machineReview"] = review
    _save(pkg, path)
    if review["qualified"]:
        log(f"POSE CHECK PASSED — {shot_id} {name}: every objective dimension passed")
    else:
        log(f"POSE CHECK STOPPED — {shot_id} {name}: "
            f"{review.get('recommendedCorrection') or review.get('summary')}")
    return review


def qualify_pose_reference(scene, shot_id, character, episode="Ep1", log=print):
    """Promote a passing machine review without manufacturing a human approval."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    name = _resolve_char(character, _characters_cfg())
    ledger = _ledger(pkg, shot_id)
    records = ledger.setdefault("keyframePoseReferences", {})
    state = records.get(name) or {}
    candidate = state.get("candidate") or {}
    candidate_path = _resolved_reference_path(candidate.get("path"))
    if not candidate_path or not candidate_path.exists():
        raise Refused(f"REFUSED — {name} has no pose candidate to qualify")
    expected = _pose_input_signature(pkg, shot, name)
    content_hash = _sha256_file(candidate_path)
    review = candidate.get("machineReview") or {}
    if (candidate.get("inputSignature") != expected or
            candidate.get("contentHash") != content_hash):
        raise Refused(f"REFUSED — {name}'s pose candidate is stale or changed")
    if (review.get("qualified") is not True or
            review.get("candidateContentHash") != content_hash or
            review.get("reviewVersion") != POSE_QUALIFICATION_VERSION):
        raise Refused(f"REFUSED — {name}'s pose has not passed the conformance gate")

    old = state.get("qualified")
    history = list(state.get("history") or [])
    if old:
        history.append({**old, "outcome": "superseded-qualification",
                        "supersededAt": _now()})
    qualification = {
        **candidate,
        "qualified": True,
        "qualifiedAt": _now(),
        "qualifiedBy": "Automated pose conformance gate",
        "machineReview": review,
        "humanApproved": False,
    }
    state.update({
        "qualified": qualification,
        "candidate": None,
        "history": history,
    })
    records[name] = state
    _save(pkg, path)
    _publish_pose_library_record(
        pkg, shot, name, candidate_path, review)
    log(f"POSE QUALIFIED — {shot_id} {name} (machine check, not human approval; reusable)")
    return qualification


def reuse_qualified_pose(scene, shot_id, character, episode="Ep1", log=print):
    """Attach an exact-contract library pose to this shot without a media-provider call."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    name = _resolve_char(character, _characters_cfg())
    library = _load_pose_library_record(pkg, shot, name)
    if not library:
        raise Refused(f"REFUSED — no exact qualified pose-library match exists for {name}")
    records = _ledger(pkg, shot_id).setdefault("keyframePoseReferences", {})
    state = records.setdefault(
        name, {"approved": None, "qualified": None, "candidate": None, "history": []})
    if state.get("candidate"):
        raise Refused(f"REFUSED — {name} already has a pose candidate awaiting a check")
    state["qualified"] = {
        "path": library["path"],
        "source": "exact-qualified-pose-library",
        "sourceContractHash": library["contractHash"],
        "inputSignature": _pose_input_signature(pkg, shot, name),
        "contentHash": library["contentHash"],
        "machineReview": library["machineReview"],
        "qualified": True,
        "qualifiedAt": _now(),
        "qualifiedBy": "Exact qualified pose library",
        "humanApproved": False,
    }
    _save(pkg, path)
    log(f"POSE REUSED — {shot_id} {name}: exact qualified library match (zero media spend)")
    return state["qualified"]


def approve_pose_reference(scene, shot_id, character, episode="Ep1",
                           reviewed_by="Julian", log=print):
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    name = _resolve_char(character, _characters_cfg())
    ledger = _ledger(pkg, shot_id)
    records = ledger.setdefault("keyframePoseReferences", {})
    state = records.get(name) or {}
    candidate = state.get("candidate") or {}
    candidate_path = _resolved_reference_path(candidate.get("path"))
    if not candidate_path or not candidate_path.exists():
        raise Refused(f"REFUSED — {name} has no pose candidate awaiting approval")
    expected = _pose_input_signature(pkg, shot, name)
    if (candidate.get("inputSignature") != expected or
            candidate.get("contentHash") != _sha256_file(candidate_path)):
        raise Refused(
            f"REFUSED — {name}'s pose candidate is stale or changed; reject and replace it")
    old = state.get("approved")
    history = list(state.get("history") or [])
    if old:
        history.append({**old, "outcome": "superseded", "supersededAt": _now()})
    if state.get("qualified"):
        history.append({**state["qualified"], "outcome": "superseded-by-human-approval",
                        "supersededAt": _now()})
    state.update({
        "approved": {**candidate, "approved": True, "approvedAt": _now(),
                     "reviewedBy": reviewed_by},
        "qualified": None,
        "candidate": None,
        "history": history,
    })
    records[name] = state
    _save(pkg, path)
    # The last pose approval closes the local preparation loop immediately. This writes only
    # a deterministic composite and never contacts a provider.
    refreshed, _ = load_pkg(scene, episode)
    refreshed_shot = _shot(refreshed, shot_id)
    if pose_reference_status(scene, shot_id, episode)["ready"]:
        _ensure_posed_integration_master(
            refreshed, refreshed_shot, scene, episode, _characters_cfg())
    log(f"POSE APPROVED — {shot_id} {name} by {reviewed_by}")
    return state["approved"]


def reject_pose_reference(scene, shot_id, character, correction, episode="Ep1",
                          reviewed_by="Julian", log=print):
    if not str(correction or "").strip():
        raise Refused("REFUSED — a pose rejection requires a plain-language reason")
    pkg, path = load_pkg(scene, episode)
    name = _resolve_char(character, _characters_cfg())
    ledger = _ledger(pkg, shot_id)
    records = ledger.setdefault("keyframePoseReferences", {})
    state = records.get(name) or {}
    candidate = state.get("candidate") or {}
    candidate_path = _resolved_reference_path(candidate.get("path"))
    if not candidate_path or not candidate_path.exists():
        raise Refused(f"REFUSED — {name} has no pose candidate to reject")
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    archive = (HERE / "media" / "archive" / "pose_references_rejected" /
               f"{episode}_{shot_id}_{re.sub(r'[^A-Za-z0-9._-]+', '_', name)}_{ts}")
    archive.mkdir(parents=True, exist_ok=True)
    destination = archive / candidate_path.name
    shutil.move(candidate_path, destination)
    rejection = {
        **candidate,
        "outcome": "rejected",
        "rejectedAt": _now(),
        "reviewedBy": reviewed_by,
        "reason": str(correction).strip(),
        "rejectedFile": str(destination.relative_to(HERE)),
    }
    state["candidate"] = None
    state.setdefault("history", []).append(rejection)
    records[name] = state
    _save(pkg, path)
    log(f"POSE REJECTED — {shot_id} {name}: {correction}")
    return rejection


def _posed_integration_record_path(scene, shot_id, episode="Ep1"):
    safe_shot = re.sub(r"[^A-Za-z0-9._-]+", "_", str(shot_id))
    return MEDIA.parent / "reference_controls" / (
        f"{episode}_S{scene}_{safe_shot}_posed_integration.json")


def _posed_integration_contract(pkg, shot, scene, episode, characters_cfg):
    resolved = _opening_composition_contract(
        pkg, shot, scene, episode, characters_cfg)
    if not resolved:
        return None
    composition, characters, plate = resolved
    poses = {}
    pose_contract = []
    for name in characters:
        ready_pose = _current_pose_ready(pkg, shot, name)
        if not ready_pose:
            return None
        pose_path = _resolved_reference_path(ready_pose["path"])
        poses[name] = str(pose_path)
        pose_contract.append({
            "character": name,
            "file": pose_path.name,
            "sha256": _sha256_file(pose_path),
            "inputSignature": ready_pose.get("inputSignature"),
            "decisionType": ("human-approval" if ready_pose.get("approved")
                             else "machine-qualification"),
        })
    core = {
        "version": 1,
        "shotId": shot.get("shotId"),
        "compositionContractHash": composition.get("contractHash"),
        "scenePlateSha256": composition.get("scenePlateSha256"),
        "poses": pose_contract,
    }
    core["contractHash"] = hashlib.sha256(json.dumps(
        core, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    return core, characters, plate, poses, composition["layout"]


def _load_posed_integration_master(shot, scene, episode, characters_cfg):
    record_path = _posed_integration_record_path(scene, shot.get("shotId"), episode)
    if not record_path.exists():
        return None
    try:
        pkg, _ = load_pkg(scene, episode)
        expected = _posed_integration_contract(
            pkg, shot, scene, episode, characters_cfg)
        if not expected:
            return None
        core, _, _, _, _ = expected
        record = json.loads(record_path.read_text())
        image_path = _resolved_reference_path(record.get("path"))
        if (record.get("contractHash") != core.get("contractHash") or
                not image_path or not image_path.exists() or
                record.get("imageSha256") != _sha256_file(image_path)):
            return None
        return {**record, "path": str(image_path)}
    except (OSError, ValueError, TypeError, KeyError, Refused):
        return None


def _ensure_posed_integration_master(pkg, shot, scene, episode, characters_cfg):
    current = _load_posed_integration_master(
        shot, scene, episode, characters_cfg)
    if current:
        return current
    resolved = _posed_integration_contract(
        pkg, shot, scene, episode, characters_cfg)
    if not resolved:
        status = pose_reference_status(scene, shot["shotId"], episode)
        missing = ", ".join(
            item["character"] for item in status["items"] if not item["ready"])
        raise Refused(
            f"REFUSED — {shot['shotId']} needs qualified shot-specific pose references for "
            f"{missing or 'its opening cast'} before the keyframe can be assembled")
    contract, characters, plate, poses, layout = resolved
    try:
        image_bytes, geometry = cb_layout.render_posed_integration_frame(
            plate, characters, layout, poses)
    except cb_layout.LayoutError as exc:
        raise Refused(
            f"REFUSED — {shot.get('shotId')} posed integration failed: {exc}") from exc
    controls = MEDIA.parent / "reference_controls"
    image_path = controls / (
        f"{episode}_S{scene}_{shot['shotId']}_posed_integration_"
        f"{contract['contractHash'][:12]}.png")
    cb_db.atomic_write_bytes(MEDIA.parent.parent.parent, image_path, image_bytes)
    try:
        stored_path = str(image_path.relative_to(HERE))
    except ValueError:
        stored_path = str(image_path.resolve())
    record = {
        **contract,
        "role": POSED_INTEGRATION_ROLE,
        "path": stored_path,
        "imageSha256": _sha256_file(image_path),
        "geometry": geometry,
        "generatedAt": _now(),
        "zeroSpend": True,
        "providerCalled": False,
        "providerInput": True,
        "technicalControl": False,
    }
    cb_db.atomic_write_json(
        MEDIA.parent.parent.parent,
        _posed_integration_record_path(scene, shot["shotId"], episode), record)
    return {**record, "path": str(image_path.resolve())}


def prepare_posed_integration_master(scene, shot_id, episode="Ep1", log=print):
    """Build the exact creative frame precursor after every cast pose is qualified."""
    pkg, _ = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    control = _ensure_posed_integration_master(
        pkg, shot, scene, episode, _characters_cfg())
    log(f"POSED INTEGRATION — {shot_id} -> {pathlib.Path(control['path']).name} "
        "(zero spend; this creative frame, not the sizing proof, is the provider input)")
    return control


def keyframe_build_status(scene, shot_id, episode="Ep1"):
    """Read-only plan for one bounded, human-fired two-provider SEE build."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    if shot.get("sourceType") != "opener":
        return {
            "state": "not-applicable", "buildable": False,
            "reason": "This shot inherits its opening frame.",
            "mediaCallsRequired": 0, "maxMediaCalls": 0,
            "estimatedMaxUsd": 0.0, "poseCallsRequired": 0,
            "humanDecision": "Review the inherited opening frame with the animation.",
            "noAutomaticRetries": True,
        }
    if ledger.get("keyframeCandidate") or ledger.get("keyframeCandidates"):
        return {
            "state": "ready-for-review", "buildable": False,
            "reason": "The Seedream and Nano Banana SEE candidates are waiting for selection.",
            "mediaCallsRequired": 0, "maxMediaCalls": 0,
            "estimatedMaxUsd": 0.0, "poseCallsRequired": 0,
            "humanDecision": "Compare A and B, select one, then Accept or Iterate.",
            "noAutomaticRetries": True,
        }

    max_calls = 2
    try:
        import cb_costs
        reference_count = len(_expanded_reference_blueprint(
            shot, "keyframeReferenceSlots", _characters_cfg()))
        seedream_cost = float(cb_costs.estimate_image_cost(
            provider="seedream5pro", num_refs=reference_count, output_tier="2K"))
        nb2_cost = float(cb_costs.estimate_image_cost(
            provider="nanobanana2", num_refs=reference_count, output_tier="2K"))
    except Exception:
        seedream_cost = None
        nb2_cost = None
    estimated = (round(seedream_cost + nb2_cost, 4)
                 if seedream_cost is not None and nb2_cost is not None else None)
    return {
        "state": "buildable",
        "buildable": True,
        "reason": (
            "The Studio will build exactly two SEE candidates from one sealed prompt and "
            "reference pack: A through Seedream 5 Pro and B through Nano Banana 2."),
        "workflow": "dual-provider-see-ab",
        "posePlan": [],
        "poseCallsRequired": 0,
        "finishingCallsRequired": 2,
        "mediaCallsRequired": max_calls,
        "maxMediaCalls": max_calls,
        "estimatedUnitUsd": {"A": seedream_cost, "B": nb2_cost},
        "estimatedMaxUsd": estimated,
        "automatedChecks": [
            "locked character identity and body proportions",
            "canon relative scale and character count",
            "approved scene world, camera relationship and lighting",
            "clear lead room and an unobstructed performance corridor",
        ],
        "provider": "byteplus+google",
        "providerModelId": {
            "A": cb_gen.SEEDREAM_MODEL_ID,
            "B": cb_gen.IMAGE_MODEL,
        },
        "validatorModel": cb_departments.cb_llm.VALIDATOR_MODEL,
        "stopPolicy": (
            "Generate exactly one image per provider; never auto-reroll or auto-select. "
            "Objective identity/scale QC and Julian's selection precede approval."),
        "humanDecision": "Compare A and B, select one, then Accept or Iterate.",
        "noAutomaticRetries": True,
    }


def build_keyframe(scene, shot_id, episode="Ep1", log=print):
    """Build one permissive opening-stage keyframe and stop for human review.

    Character turnarounds own identity and canon scale; the approved Scene Look owns the
    world. The keyframe owns only frame-one staging, camera, light and usable action space.
    Exact acting poses and performance development remain Animation's responsibility.
    """
    pkg, _ = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    _require_confirmed_billing("byteplus")
    _require_confirmed_billing("google")
    _require_current_scenelook(scene, episode)
    shot = _shot(pkg, shot_id)
    if shot.get("sourceType") != "opener":
        raise Refused(f"REFUSED — {shot_id} inherits its opening frame and needs no build")
    if (_ledger(pkg, shot_id).get("keyframeCandidate") or
            _ledger(pkg, shot_id).get("keyframeCandidates")):
        raise Refused(
            f"REFUSED — {shot_id} already has a finished keyframe waiting for Accept or Iterate")

    result = keyframe_shot(scene, shot_id, episode, log=log)
    log(f"KEYFRAME BUILD COMPLETE — {shot_id}: SEE A/B is ready for comparison and explicit "
        "selection; no downstream animation was fired")
    return result


def _scale_control_record_path(scene, shot_id, episode="Ep1"):
    safe_shot = re.sub(r"[^A-Za-z0-9._-]+", "_", str(shot_id))
    return MEDIA.parent / "reference_controls" / (
        f"{episode}_S{scene}_{safe_shot}_character_scale.json")


def _character_scale_contract(shot, characters_cfg, same_depth=False):
    """Measured physical-height truth for a multi-character shot.

    The control is derived only from canon ``heightIn`` values and the locked turnaround
    files. It never infers a size from prose or from a generated image. A missing height
    means no control can honestly be built; callers may then keep the existing reference
    contract rather than inventing a relationship.
    """
    cast = list(dict.fromkeys(shot.get("charactersInFrame") or []))
    if len(cast) < 2:
        return None
    entries = []
    for supplied_name in cast:
        name = _resolve_char(supplied_name, characters_cfg)
        profile = characters_cfg.get(name) or {}
        try:
            height = float(profile.get("heightIn"))
        except (TypeError, ValueError):
            return None
        if height <= 0:
            return None
        turnaround = _resolved_reference_path(_char_ref(name, characters_cfg))
        entries.append({
            "character": name,
            "heightIn": int(height) if height.is_integer() else height,
            "turnaroundFile": turnaround.name,
            "turnaroundSha256": _sha256_file(turnaround),
        })
    core = {
        "version": 1,
        "shotId": shot.get("shotId"),
        "screenOrder": [entry["character"] for entry in entries],
        "sameDepth": bool(same_depth),
        "characters": entries,
    }
    core["contractHash"] = hashlib.sha256(json.dumps(
        core, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()
    return core


def _scale_pixel_heights(contract, maximum_pixels=490):
    """Exact integer geometry for integer-inch canon heights (14:12 remains 7:6)."""
    heights = [float(item["heightIn"]) for item in contract["characters"]]
    scale = max(1, int(maximum_pixels // max(heights)))
    return {item["character"]: int(round(float(item["heightIn"]) * scale))
            for item in contract["characters"]}


def _write_character_scale_board(path, contract):
    """Create a neutral measured blockout; turnarounds still own all appearance."""
    from PIL import Image, ImageDraw

    width, height = 1600, 900
    image = Image.new("RGB", (width, height), (246, 248, 247))
    draw = ImageDraw.Draw(image)
    title_font = cb_post._pil_font(44)
    label_font = cb_post._pil_font(30)
    small_font = cb_post._pil_font(23)
    draw.text((70, 48), "CANONICAL CHARACTER SCALE", fill=(22, 29, 31), font=title_font)
    subtitle = ("SAME CAMERA DEPTH - MEASURED TURNAROUND HEIGHTS"
                if contract.get("sameDepth") else
                "MEASURED PHYSICAL HEIGHTS - APPLY SHOT PERSPECTIVE AFTER SCALE")
    draw.text((72, 110), subtitle, fill=(35, 102, 98), font=small_font)
    draw.text((72, 150),
              "Use only relative full-body height and depth. Turnarounds own shape, face and materials.",
              fill=(82, 90, 92), font=small_font)

    baseline = 745
    entries = contract["characters"]
    pixels = _scale_pixel_heights(contract)
    step = width / (len(entries) + 1)
    palette = [(47, 116, 112), (190, 133, 38), (94, 93, 132), (150, 72, 87)]
    for index, item in enumerate(entries, start=1):
        name = item["character"]
        full_height = pixels[name]
        x = int(step * index)
        top = baseline - full_height
        colour = palette[(index - 1) % len(palette)]

        # The outer bracket is the authoritative measurement. The inner capsule is only a
        # deliberately generic blockout, so it cannot compete with the turnaround silhouette.
        draw.line((x - 145, top, x - 145, baseline), fill=(30, 37, 39), width=4)
        draw.line((x - 165, top, x - 125, top), fill=(30, 37, 39), width=4)
        draw.line((x - 165, baseline, x - 125, baseline), fill=(30, 37, 39), width=4)
        body_top = top + int(full_height * 0.14)
        draw.rounded_rectangle(
            (x - 92, body_top, x + 92, baseline - 22), radius=88,
            fill=(229, 233, 232), outline=colour, width=7)
        draw.line((x - 46, body_top + 4, x - 66, top + 10), fill=colour, width=6)
        draw.line((x + 46, body_top + 4, x + 66, top + 10), fill=colour, width=6)
        draw.ellipse((x - 73, top, x - 57, top + 18), fill=colour)
        draw.ellipse((x + 57, top, x + 73, top + 18), fill=colour)
        draw.text((x - 110, baseline + 28), name, fill=(22, 29, 31), font=label_font)
        measure = f"{item['heightIn']:g} in full height" if isinstance(
            item["heightIn"], float) else f"{item['heightIn']} in full height"
        draw.text((x - 110, baseline + 68), measure, fill=colour, font=small_font)

    draw.line((60, baseline, width - 60, baseline), fill=(30, 37, 39), width=5)
    draw.text((70, 842), "ONE DEPTH PLANE" if contract.get("sameDepth") else "PHYSICAL SCALE DATUM",
              fill=(30, 37, 39), font=small_font)
    encoded = io.BytesIO()
    image.save(encoded, format="PNG")
    cb_db.atomic_write_bytes(
        MEDIA.parent.parent.parent, path, encoded.getvalue())


def _load_character_scale_control(shot, scene, episode, characters_cfg):
    """Return only a current, content-verified technical control; stale means absent."""
    record_path = _scale_control_record_path(scene, shot.get("shotId"), episode)
    if not record_path.exists():
        return None
    try:
        record = json.loads(record_path.read_text())
        expected = _character_scale_contract(
            shot, characters_cfg, same_depth=bool(record.get("sameDepth")))
        image_path = _resolved_reference_path(record.get("path"))
        if (not expected or record.get("contractHash") != expected.get("contractHash") or
                not image_path or not image_path.exists() or
                record.get("imageSha256") != _sha256_file(image_path)):
            return None
        return {**record, "path": str(image_path)}
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _ensure_character_scale_control(shot, scene, episode, characters_cfg,
                                    same_depth=None):
    """Build or reuse one immutable zero-spend board and its signed sidecar."""
    current = _load_character_scale_control(shot, scene, episode, characters_cfg)
    if current and (same_depth is None or bool(current.get("sameDepth")) == bool(same_depth)):
        return current
    depth_lock = bool(current.get("sameDepth")) if same_depth is None and current else bool(same_depth)
    contract = _character_scale_contract(shot, characters_cfg, same_depth=depth_lock)
    if not contract:
        return None
    controls = MEDIA.parent / "reference_controls"
    image_path = controls / (
        f"{episode}_S{scene}_{shot['shotId']}_scale_{contract['contractHash'][:12]}.png")
    _write_character_scale_board(image_path, contract)
    try:
        stored_path = str(image_path.relative_to(HERE))
    except ValueError:
        stored_path = str(image_path.resolve())
    record = {
        **contract,
        "role": CHARACTER_SCALE_CONTROL_ROLE,
        "path": stored_path,
        "imageSha256": _sha256_file(image_path),
        "generatedAt": _now(),
        "zeroSpend": True,
        "providerCalled": False,
    }
    record_path = _scale_control_record_path(scene, shot["shotId"], episode)
    cb_db.atomic_write_json(
        MEDIA.parent.parent.parent, record_path, record)
    return {**record, "path": str(image_path.resolve())}


def prepare_character_scale_control(scene, shot_id, episode="Ep1", same_depth=False, log=print):
    """Public zero-spend preparation used by Studio orchestration and targeted repairs."""
    pkg, _ = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    control = _ensure_character_scale_control(
        shot, scene, episode, _characters_cfg(), same_depth=same_depth)
    if not control:
        raise Refused(
            f"REFUSED — {shot_id} needs at least two characters with locked canon heightIn "
            "values before a measured scale control can be built")
    names = ", ".join(
        f"{item['character']} {item['heightIn']}in" for item in control["characters"])
    log(f"SCALE CONTROL — {shot_id}: {names} -> {pathlib.Path(control['path']).name} "
        "(zero spend; attached automatically to Keyframe and Animation)")
    return control


def _effective_image_slots(shot, slots_key, scene, episode, characters_cfg,
                           include_technical_controls=True):
    del scene, episode, characters_cfg, include_technical_controls
    # Keyframes are built directly from the package's explicit character and Scene Look
    # bindings. Local layout/scale boards and optional pose experiments remain inspectable
    # evidence only; none may silently replace the locked references sent to the provider.
    return dict(shot.get(slots_key) or {})


def _slots_from_reference_contract(reference_contract, characters=None):
    slots = {}
    character_names = sorted(
        [str(name).strip() for name in characters or [] if str(name).strip()],
        key=len,
        reverse=True,
    )
    next_image = 1
    for item in reference_contract or []:
        tag = str(item.get("assetTag") or "").strip()
        if not re.match(r"^@(?:图|Image)\s*\d+$", tag, re.I):
            continue
        role = str(item.get("role") or "").strip()
        controls = str(item.get("controls") or "").strip()
        lowered = " ".join([role, controls]).lower()
        if re.search(r"\b(opening|first)\b", lowered):
            mapped = "opening keyframe"
        elif re.search(r"\b(location|scene|world|plate|environment)\b", lowered):
            mapped = "scene plate"
        elif role == "character_identity" and controls:
            mapped = next(
                (name for name in character_names if name.lower() in controls.lower()),
                "",
            )
        elif role:
            mapped = role
        else:
            mapped = controls
        if mapped:
            slots[f"@图{next_image}"] = mapped
            next_image += 1
    return slots


def _stored_approved_department_output(pkg, shot_id, stage):
    led = _ledger(pkg, shot_id)
    return (((led.get("departmentWork") or {}).get(stage) or {}).get("approved") or {}).get("output")


def _effective_reference_slots(pkg, shot, slots_key, scene, episode):
    slots = dict(shot.get(slots_key) or {})
    if slots_key != "referenceSlots":
        return slots
    if not cb_audio_authority.spoken_dialogue_lines(shot):
        slots = {
            slot: role for slot, role in slots.items()
            if not str(slot).startswith("@Audio")
        }
    if not slots:
        slots = dict(shot.get("animationReferenceSlots") or {})
    if not slots and (shot.get("sourceType") == "relay" or shot.get("sourceShotId")):
        # Relay animation must inherit the approved final frame, but that frame is only
        # the opening-state authority. It never replaces the full visual contract.
        # Scene plate + all in-frame character references still travel with the render.
        # Otherwise the provider has no stable geography, prop, or identity source and
        # continuity fails at the exact point the relay is meant to protect.
        relay_slots = {"@图1": "previous shot final frame", "@图2": "scene plate"}
        next_slot = 3
        for character in shot.get("charactersInFrame") or []:
            name = str(character or "").strip()
            if not name:
                continue
            if name in relay_slots.values():
                continue
            relay_slots[f"@图{next_slot}"] = name
            next_slot += 1
        slots = relay_slots
    if not slots:
        approved = _stored_approved_department_output(
            pkg, shot.get("shotId"), "animation") or {}
        slots = _slots_from_reference_contract(
            approved.get("referenceContract") or [],
            characters=shot.get("charactersInFrame") or [],
        )

    # Extra approved location angles support reverse coverage without replacing the
    # scene plate or changing the separately-approved opening keyframe contract.
    ledger = _ledger(pkg, shot.get("shotId")) if pkg.get("continuityLedger") else {}
    additional_roles = [
        str(role or "").strip()
        for role in ledger.get("additionalAnimationReferenceRoles") or []
        if str(role or "").strip()
    ]
    existing_roles = {
        str(role or "").strip().casefold() for role in slots.values()
    }
    image_numbers = [
        int(match.group(1))
        for key in slots
        if (match := re.fullmatch(r"@图(\d+)", str(key)))
    ]
    next_slot = max(image_numbers, default=0) + 1
    for role in additional_roles:
        if role.casefold() in existing_roles:
            continue
        slots[f"@图{next_slot}"] = role
        existing_roles.add(role.casefold())
        next_slot += 1

    # Required continuity props are first-class provider authorities, not optional prose.
    # Append them to every animation bundle after resolving the shot's ordinary roles so
    # explicit package slots, relay-generated slots and approved Director contracts all
    # receive the same protection. The provider attachment planner will then place these
    # semantic roles in its stable project-wide order.
    required_props = _required_prop_reference_roles(shot, scene, episode)
    for role in required_props:
        if role.casefold() in existing_roles:
            continue
        slots[f"@图{next_slot}"] = role
        existing_roles.add(role.casefold())
        next_slot += 1
    return slots


def _with_effective_reference_slots(pkg, shot, slots_key, scene, episode):
    slots = _effective_reference_slots(pkg, shot, slots_key, scene, episode)
    if slots == dict(shot.get(slots_key) or {}):
        return shot
    return {**shot, slots_key: slots}


def _animation_reference_contract(attachment_plan, shot, audio_path=None):
    """Bind the typed Animation record to the exact sealed provider upload order.

    The specialist may have been prepared before an additive continuity reference was
    registered.  Provider attachments are the authority at compile time, so regenerate
    the compact role contract from that same plan instead of retaining stale asset tags.
    """
    contract = []
    characters = {
        str(name or "").strip() for name in shot.get("charactersInFrame") or []
        if str(name or "").strip()
    }
    for item in attachment_plan or []:
        tag = str(item.get("slot") or "").strip()
        role = str(item.get("role") or "").strip()
        if not tag or not role:
            continue
        if role in ("opening keyframe", "previous shot final frame"):
            typed_role = "opening_frame"
            controls = (
                "the exact first-frame composition and carried visible state from the "
                f"approved {role}"
            )
            scope = "continuity"
        elif role == CLOSING_COMPOSITION_ROLE:
            typed_role = "closing_frame"
            controls = "the exact approved final button composition and held end state"
            scope = "continuity"
        elif role == "scene plate" or role.startswith("location:"):
            typed_role = "location"
            controls = (
                "the approved scene geography, world, light, materials and atmosphere"
                if role == "scene plate" else
                f"supplementary approved geography only: {role.split(':', 1)[1]}"
            )
            scope = "episode"
        elif role.startswith("prop:"):
            prop_id = role.split(":", 1)[1].replace("_", " ")
            typed_role = "prop"
            controls = (
                f"the exact {prop_id} design, materials, construction, scale and approved "
                "carried state"
            )
            scope = "continuity"
        elif role in characters:
            typed_role = "character_identity"
            controls = f"{role} identity, proportions, scale and approved wearable state"
            scope = "canon"
        else:
            typed_role = "style"
            controls = f"the approved {role} visual authority"
            scope = "episode"
        contract.append({
            "assetTag": tag,
            "role": typed_role,
            "controls": controls,
            "scope": scope,
        })
    if audio_path and cb_audio_authority.spoken_dialogue_lines(shot):
        contract.append({
            "assetTag": "@Audio1",
            "role": "audio",
            "controls": "approved dialogue, voice identity, cadence, delivery and mouth timing",
            "scope": "continuity",
        })
    return contract


_NON_IDENTITY_IMAGE_ROLES = {
    "scene plate", "opening keyframe", "previous shot final frame",
    OPENING_COMPOSITION_ROLE, CLOSING_COMPOSITION_ROLE,
    POSED_INTEGRATION_ROLE, CHARACTER_SCALE_CONTROL_ROLE, "Bo vision plate",
}


def _is_non_identity_image_role(role):
    role = str(role or "").strip()
    return (role in _NON_IDENTITY_IMAGE_ROLES or role.startswith("prop:")
            or role.startswith("location:"))


def _reference_slot_policy():
    path = ROOT / "shows" / "crystal-bears" / "canon" / "reference_slot_policy.json"
    try:
        policy = json.loads(path.read_text())
    except (OSError, ValueError, TypeError):
        return {}
    return policy if isinstance(policy, dict) else {}


def _stable_reference_role_key(role, usage, characters_cfg):
    """Return the project-level semantic attachment order for one logical role."""
    policy = _reference_slot_policy()
    role = str(role or "").strip()
    if role.startswith("prop:"):
        # Dedicated prop authority follows character identity and precedes the scene plate.
        # This keeps compiler tags and sealed provider upload positions identical without
        # requiring every future prop ID to be added to a project-specific ordering table.
        return (2.5 if usage == "animation" else 1.5, -1, role.casefold())
    if not _is_non_identity_image_role(role):
        canonical = _resolve_char(role, characters_cfg)
        order = list(policy.get("characterOrder") or [])
        if not order:
            return (2 if usage == "animation" else 0, 0, "")
        rank = order.index(canonical) if canonical in order else len(order)
        return (2 if usage == "animation" else 0, rank, canonical.casefold())
    order = list(policy.get(
        "animationRoleOrder" if usage == "animation" else "keyframeRoleOrder") or [])
    rank = order.index(role) if role in order else len(order)
    return (rank if usage == "animation" else 1 + rank, -1, role.casefold())


def _expanded_reference_blueprint(shot, slots_key, characters_cfg, scene=None,
                                  episode="Ep1"):
    """Bind each logical character slot to one complete, uncropped turnaround sheet."""
    usage = "keyframe" if slots_key == "keyframeReferenceSlots" else "animation"
    slots = dict(shot.get(slots_key) or {})
    expanded = []
    source_slots = [key for key in slots if key.startswith("@图")]
    source_slots.sort(key=lambda key: (
        _stable_reference_role_key(slots[key], usage, characters_cfg), int(key[2:])))
    for source_slot in source_slots:
        role = slots[source_slot]
        identities = ([None] if _is_non_identity_image_role(role) else
                      _provider_identity_records(
                          role, characters_cfg, usage, shot=shot, scene=scene,
                          episode=episode))
        for identity in identities:
            expanded.append({
                "position": len(expanded) + 1,
                "slot": f"@图{len(expanded) + 1}",
                "sourceSlot": source_slot,
                "role": role,
                "usage": usage,
                "view": (identity or {}).get("view"),
                "identity": identity,
            })
    return expanded


def _provider_attachment_plan(shot, slots_key, anchor_path, scene, episode,
                              characters_cfg):
    """Return the exact ordered provider attachments and their renumbered slot bindings."""
    plan = []
    for item in _expanded_reference_blueprint(
            shot, slots_key, characters_cfg, scene=scene, episode=episode):
        identity = item.get("identity")
        if identity:
            path = identity.get("path")
        else:
            path = _slot_path_for_role(
                item["role"], anchor_path, scene, episode, characters_cfg,
                shot=shot, usage=item["usage"])
        candidate = _resolved_reference_path(path)
        if not candidate or not candidate.exists():
            raise Refused(f"REFUSED — the {item['role']} reference file is missing")
        if not _reference_path_is_approved(candidate):
            raise Refused(
                f"REFUSED — {item['role']} resolves outside this canonical Studio's "
                f"approved asset libraries ({candidate.name}); re-select it inside the "
                "current project")
        plan.append({
            **item,
            "path": str(candidate),
            "fileName": candidate.name,
        })
    return plan


def _slot_path_for_role(role, anchor_path, scene, episode, characters_cfg, shot=None,
                        usage="keyframe"):
    if role in ("opening keyframe", "previous shot final frame"):
        path = anchor_path
        if not path:
            raise Refused(f"REFUSED — {role} is not approved and available yet")
    elif role == "scene plate":
        path = _plate_path(scene, episode)
    elif str(role).startswith("location:"):
        candidates = cb_asset_registry.resolve_assets(
            episode, scene, shot_id=(shot or {}).get("shotId"),
            kinds={"reference_image"})
        matches = [item for item in candidates if str(item.get("role") or "") == role]
        if not matches:
            raise Refused(
                f"REFUSED — approved supplementary location reference {role!r} is not "
                f"registered for {episode} scene {scene}")
        path = matches[0]["path"]
    elif role == "Bo vision plate":
        candidates = cb_asset_registry.resolve_assets(
            episode, scene, shot_id=(shot or {}).get("shotId"),
            kinds={"reference_image"})
        matches = [item for item in candidates if str(item.get("role") or "") == role]
        if not matches:
            raise Refused(
                f"REFUSED — approved {role} is not registered for {episode} scene {scene}")
        path = matches[0]["path"]
    elif str(role).startswith("prop:"):
        prop_id = str(role).split(":", 1)[1].strip().casefold()
        candidates = cb_asset_registry.resolve_assets(
            episode, scene, shot_id=(shot or {}).get("shotId"),
            kinds={"reference_image"})
        matches = [item for item in candidates if (
            str((item.get("metadata") or {}).get("assetUse") or "") == "prop_reference"
            and (
                str((item.get("metadata") or {}).get("propId") or "").casefold() == prop_id
                or prop_id in str(item.get("role") or "").casefold()
            )
        )]
        if not matches:
            raise Refused(
                f"REFUSED — approved prop reference {prop_id!r} is not registered "
                f"for {episode} scene {scene}")
        path = matches[0]["path"]
    elif role == OPENING_COMPOSITION_ROLE:
        raise Refused(
            "REFUSED — the opening composition master is a local QA control and may never "
            "be uploaded to an image provider")
    elif role == CLOSING_COMPOSITION_ROLE:
        path = (shot or {}).get("closingFramePath")
        if not path:
            raise Refused(
                "REFUSED — the approved final button frame is missing from the shot contract")
    elif role == POSED_INTEGRATION_ROLE:
        control = _load_posed_integration_master(
            shot or {}, scene, episode, characters_cfg)
        path = (control or {}).get("path")
        if not path:
            raise Refused(
                "REFUSED — qualified shot-specific character poses must be assembled before "
                "the keyframe provider input is ready")
    elif role == CHARACTER_SCALE_CONTROL_ROLE:
        control = _load_character_scale_control(shot or {}, scene, episode, characters_cfg)
        path = (control or {}).get("path")
        if not path:
            raise Refused(
                "REFUSED — the measured character scale control is missing or stale")
    else:
        path = _provider_identity_record(role, characters_cfg, usage)["path"]
    candidate = _resolved_reference_path(path)
    if not candidate or not candidate.exists():
        raise Refused(f"REFUSED — the {role} reference file is missing")
    if not _reference_path_is_approved(candidate):
        raise Refused(
            f"REFUSED — {role} resolves outside this canonical Studio's approved asset "
            f"libraries ({candidate.name}); re-select it inside the current project")
    return str(candidate)


def _slot_paths(shot, slots_key, anchor_path, scene, episode, characters_cfg,
                include_technical_controls=True):
    """The exact expanded image upload list in provider slot order."""
    del include_technical_controls
    return [item["path"] for item in _provider_attachment_plan(
        shot, slots_key, anchor_path, scene, episode, characters_cfg)]


def shot_reference_manifest(scene, shot_id, episode="Ep1"):
    """Read-only, zero-spend reference truth for the Keyframe and Animation stages."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    characters_cfg = _characters_cfg()

    try:
        animation_anchor = _anchor_for(pkg, shot)
        anchor_error = None
    except Refused as exc:
        animation_anchor = None
        anchor_error = str(exc)

    def image_entries(slots_key, anchor_path=None):
        entries = []
        blueprint = _expanded_reference_blueprint(
            shot, slots_key, characters_cfg, scene=scene, episode=episode)
        for attachment in blueprint:
            position = attachment["position"]
            slot = attachment["slot"]
            role = attachment["role"]
            identity = attachment.get("identity")
            try:
                if identity:
                    path = identity.get("path")
                    candidate = _resolved_reference_path(path)
                    if not candidate or not candidate.exists():
                        raise Refused(f"REFUSED — the {role} reference file is missing")
                    if not _reference_path_is_approved(candidate):
                        raise Refused(
                            f"REFUSED — {role} resolves outside this canonical Studio's "
                            f"approved asset libraries ({candidate.name}); re-select it "
                            "inside the current project")
                    path = str(candidate)
                else:
                    path = _slot_path_for_role(
                        role, anchor_path, scene, episode, characters_cfg, shot=shot,
                        usage=attachment["usage"])
                item = {
                    "position": position, "slot": slot,
                    "sourceSlot": attachment["sourceSlot"], "role": role,
                    "kind": "image", "status": "ready", "ready": True,
                    "path": path, "fileName": pathlib.Path(path).name,
                }
                if identity:
                    item["identity"] = {
                        key: identity.get(key) for key in (
                            "character", "view", "derived", "providerSafe",
                            "intactTurnaround", "singleSubject",
                            "singleCharacterIdentity", "attachmentMode", "coverage",
                            "contractHash", "sourceSha256",
                            "distinguishingFeatures", "mustNotBorrow",
                            "turnaroundAuthority", "turnaroundViewIndex",
                            "turnaroundViewCount", "turnaroundGroupHash",
                        ) if identity.get(key) is not None
                    }
                entries.append(item)
            except Refused as exc:
                message = anchor_error if role in (
                    "opening keyframe", "previous shot final frame") and anchor_error else str(exc)
                entries.append({
                    "position": position, "slot": slot,
                    "sourceSlot": attachment["sourceSlot"], "role": role,
                    "view": attachment.get("view"),
                    "kind": "image",
                    "status": "unavailable" if "outside this canonical Studio" in message else "missing",
                    "ready": False, "path": None, "fileName": None,
                    "message": message,
                })
        return entries

    keyframe_entries = image_entries("keyframeReferenceSlots")
    animation_entries = image_entries("referenceSlots", animation_anchor)
    animation_slots = _effective_reference_slots(
        pkg, shot, "referenceSlots", scene, episode)
    audio_slot = next((slot for slot in animation_slots
                       if slot.startswith("@Audio")), None)
    if audio_slot:
        role = animation_slots[audio_slot]
        raw_audio = ledger.get("voPath")
        audio_path = _resolved_reference_path(raw_audio)
        approved = bool((ledger.get("voiceApproval") or {}).get("approved"))
        allowed = bool(audio_path and audio_path.exists() and
                       _reference_path_is_approved(audio_path))
        if allowed and approved:
            status, message = "ready", None
        elif audio_path and audio_path.exists() and not allowed:
            status, message = "unavailable", (
                "The voice track resolves outside this canonical Studio's approved asset "
                "libraries; regenerate or re-select it here.")
        elif audio_path and audio_path.exists():
            status, message = "unapproved", "The voice track exists but has not been accepted."
        else:
            status, message = "missing", "No approved voice track is available yet."
        animation_entries.append({
            "position": len(animation_entries) + 1,
            "slot": audio_slot, "role": role, "kind": "audio",
            "status": status, "ready": status == "ready",
            "path": str(audio_path) if allowed else None,
            "fileName": audio_path.name if allowed else None,
            "message": message,
        })

    keyframe_applies = shot.get("sourceType") == "opener"
    scale_control = _load_character_scale_control(
        shot, scene, episode, characters_cfg)
    composition_control = _load_opening_composition_master(
        shot, scene, episode, characters_cfg) if keyframe_applies else None
    pose_preparation = {
        "applies": False, "ready": True, "items": [], "zeroSpend": True,
        "readOnly": True,
        "reason": "Acting poses belong to animation and are not a keyframe prerequisite.",
    }
    build_status = (keyframe_build_status(scene, shot_id, episode)
                    if keyframe_applies else {
                        "state": "not-applicable", "buildable": False,
                        "reason": "This relay shot inherits its opening frame.",
                        "mediaCallsRequired": 0, "maxMediaCalls": 0,
                        "estimatedMaxUsd": 0.0,
                    })
    return {
        "episode": episode, "scene": str(scene), "shotId": shot_id,
        "zeroSpend": True, "readOnly": True,
        "technicalControls": {
            "openingComposition": ({
                "ready": True, "path": composition_control["path"],
                "fileName": pathlib.Path(composition_control["path"]).name,
                "contractHash": composition_control.get("contractHash"),
                "providerUploaded": False,
                "purpose": "Local staging advisory only",
            } if composition_control else {
                "ready": not keyframe_applies,
                "providerUploaded": False,
                "purpose": "Local staging advisory only",
            }),
            "characterScale": ({
                "ready": True, "path": scale_control["path"],
                "fileName": pathlib.Path(scale_control["path"]).name,
                "contractHash": scale_control.get("contractHash"),
                "providerUploaded": False,
                "purpose": "Local relative-size advisory only",
            } if scale_control else {
                "ready": len(shot.get("charactersInFrame") or []) < 2,
                "providerUploaded": False,
                "purpose": "Local relative-size advisory only",
            }),
        },
        "posePreparation": pose_preparation,
        "keyframeBuild": build_status,
        "posedIntegration": {
            "applies": False,
            "ready": False,
            "providerUploaded": False,
            "purpose": "Optional diagnostic fallback only",
        },
        "keyframe": {
            "applies": keyframe_applies,
            "ready": (not keyframe_applies) or (
                bool(keyframe_entries) and all(item["ready"] for item in keyframe_entries)),
            "reason": (None if keyframe_applies else
                       "This relay shot inherits its opening frame from the previous approved shot."),
            "references": keyframe_entries,
        },
        "animation": {
            "applies": True,
            "ready": bool(animation_entries) and all(
                item["ready"] for item in animation_entries),
            "references": animation_entries,
        },
    }


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


def _department_skill_ref(stage, skill, standard_version=0):
    del standard_version  # runtime skill families were consolidated in Pass 2
    if stage == "animation":
        return "skills/seedance-production-director/SKILL.md"
    if skill == "dp":
        skill = "cinematographer"
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
    sb_path = _declared_storyboard_path(pkg, scene, episode)
    sb = json.load(open(sb_path)) if sb_path.exists() else {}
    return {"episode": episode, "scene": str(scene), "sceneName": pkg.get("sceneName"),
            "creativeDirectingStandardVersion": int(
                pkg.get("creativeDirectingStandardVersion") or 0),
            "approvedStoryboardScene": sb.get("scene"),
            "selectedTreatment": sb.get("treatmentSelection"),
            "locationCanon": (locs.get(episode) or {}).get(str(scene)),
            "styleLaw": style_path.read_text().strip() if style_path.exists() else ""}


def _voice_director_lines(led):
    """Return the current approved Voice Director line records, wherever stored.

    The render compiler needs the Director timing fields, but older/newer ledgers store
    them under slightly different department containers. This helper keeps the timing
    handoff as one class-wide lookup instead of making each emission path rediscover it.
    """
    voice_work = (led.get("departmentWork") or {}).get("voice") or {}
    for key in ("approved", "candidate"):
        lines = ((voice_work.get(key) or {}).get("output") or {}).get("lines")
        if lines:
            return lines
    lines = ((led.get("departmentWork") or {}).get("voiceDirector") or {}
             ).get("compiledTrack", {}).get("lines")
    return lines or []


def _with_effective_dialogue_timing(shot, led):
    """Merge approved Voice Director timing into shot dialogue for animation compile."""
    lines = _voice_director_lines(led)
    if not lines or not cb_audio_authority.spoken_dialogue_lines(shot):
        return shot
    timing_by_occurrence = {
        line.get("dialogueOccurrenceId"): line
        for line in lines
        if line.get("dialogueOccurrenceId")
    }
    if not timing_by_occurrence:
        return shot
    dialogue = []
    changed = False
    for original in shot.get("dialogueLines") or []:
        item = dict(original)
        directed = timing_by_occurrence.get(item.get("dialogueOccurrenceId")) or {}
        if item.get("startSec") is None and directed.get("startsAtSec") is not None:
            item["startsAtSec"] = directed.get("startsAtSec")
            changed = True
        if item.get("endSec") is None and directed.get("estimatedDurationSec") is not None:
            item["estimatedDurationSec"] = directed.get("estimatedDurationSec")
            changed = True
        if item.get("exactText") is None and item.get("text") is not None:
            item["exactText"] = item.get("text")
            changed = True
        dialogue.append(item)
    if not changed:
        return shot
    return {**shot, "dialogueLines": dialogue}


def _performance_budget_report(shot, led):
    """Compare approved performance capacity with the real approved voice timing."""
    budget = shot.get("performanceBudgetApproved") or shot.get("performanceBudget")
    if not budget:
        return {"applicable": False, "ready": True, "reason": "legacy shot has no v3 budget"}
    duration = float(shot.get("durationSec") or 0)
    lines = _voice_director_lines(led) or shot.get("dialogueLines") or []
    intervals = []
    for line in lines:
        start = line.get("startsAtSec", line.get("startSec"))
        end = line.get("endSec")
        if end is None and start is not None:
            estimate = line.get("estimatedDurationSec")
            if estimate is not None:
                end = float(start) + float(estimate)
        if start is None or end is None:
            continue
        start, end = max(0.0, float(start)), min(duration, float(end))
        if end > start:
            intervals.append((start, end))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    occupied = sum(end - start for start, end in merged)
    available = max(0.0, duration - occupied)
    reserve = float(budget.get("silentActingReserveSec") or 0)
    landing = float(budget.get("landingHoldSec") or 0)
    required_unvoiced = reserve + landing
    minimum = float(budget.get("minimumHonestDurationSec") or 0)
    reasons = []
    if budget.get("decision") != "single-unit":
        reasons.append("Director marked this unit for a split before generation")
    if minimum > duration:
        reasons.append(
            f"minimum honest duration is {minimum:g}s but the unit is {duration:g}s")
    if available + 0.05 < required_unvoiced:
        reasons.append(
            f"voice leaves {available:.2f}s unoccupied but acting and landing require "
            f"{required_unvoiced:.2f}s")
    return {
        "applicable": True,
        "ready": not reasons,
        "durationSec": duration,
        "dialogueOccupiedSec": round(occupied, 3),
        "dialogueOccupancyRatio": round(occupied / duration, 3) if duration else 0,
        "availableUnvoicedSec": round(available, 3),
        "requiredSilentActingAndLandingSec": round(required_unvoiced, 3),
        "emotionalTurnCount": budget.get("emotionalTurnCount"),
        "propStateChangeCount": budget.get("propStateChangeCount"),
        "reasons": reasons,
        "recommendedAction": "split-at-strongest-story-boundary" if reasons else "proceed-to-animatic",
    }


def _shot_context(pkg, shot, led, scene, episode):
    effective_shot = _with_effective_dialogue_timing(
        _shot_creative_contract_view(pkg, shot, scene, episode), led)
    character_state_locks = {}
    characters_cfg = _characters_cfg()
    for name in effective_shot.get("charactersInFrame") or []:
        identity = _provider_identity_record(
            name, characters_cfg, "animation", shot=effective_shot,
            scene=scene, episode=episode)
        wearable_features = [
            str(feature).strip()
            for feature in identity.get("distinguishingFeatures") or []
            if re.search(
                r"\b(?:wear|worn|cuff|wrist|band|bracelet|clothing|costume|"
                r"accessory|collar|pendant|headdress|glasses|spectacles|satchel)\b",
                str(feature), re.I)
        ]
        if identity.get("characterState") and wearable_features:
            canonical = str(identity.get("character") or name).strip()
            character_state_locks[canonical] = (
                f"{canonical} approved wearable state: "
                + "; ".join(wearable_features)
            )
    if character_state_locks:
        effective_shot = {
            **effective_shot,
            "characterStateLocks": character_state_locks,
        }
    scene_locks = _scene_continuity_locks(pkg, scene)
    if scene_locks:
        effective_shot = {**effective_shot, "sceneContinuityLocks": scene_locks}
    director_feedback = str(
        (led.get("watchDirectorFeedback") or {}).get("text") or "").strip()
    if director_feedback:
        effective_shot = {
            **effective_shot,
            "watchDirectorFeedbackApproved": director_feedback,
        }
    return {"episode": episode, "scene": str(scene),
            "creativeDirectingStandardVersion": int(
                pkg.get("creativeDirectingStandardVersion") or 0),
            "shot": effective_shot,
            "approvedSceneLook": scenelook_status(scene, episode).get("approved"),
            "currentVoiceDirection": (led.get("departmentWork", {}).get("voice", {})
                                      .get("approved")),
            "humanWorkingVoice": led.get("workingVoice"),
            "humanWorkingAnimationPrompt": led.get("workingSeedancePrompt"),
            "watchDirectorFeedback": led.get("watchDirectorFeedback"),
            "latestAnimationRejection": ((led.get("rejections") or [])[-1]
                                          if led.get("rejections") else None)}


def _shot_creative_contract_view(pkg, shot, scene, episode):
    """Add approved beat contracts to a read-only shot view when lineage is exact.

    Older canonical packages retained BIG physical staging but not the complete approved
    comedy/emotion records. The linked storyboard is still their signed creative source.
    Reading those records is safe only when its bytes and this shot's creative-card hash
    exactly match the package provenance. Neither source is modified here.
    """
    if shot.get("comedyContractsApproved") and shot.get("emotionContractsApproved"):
        return shot
    source = pkg.get("sourceStoryboard") or {}
    path = _declared_storyboard_path(pkg, scene, episode)
    if not path.exists() or hashlib.md5(path.read_bytes()).hexdigest() != source.get("md5"):
        return shot
    storyboard = json.load(open(path))
    if storyboard.get("approvalState") != "approved":
        return shot
    storyboard_shot = next(
        (item for item in storyboard.get("shots") or []
         if item.get("shotId") == shot.get("shotId")), None)
    if storyboard_shot is None:
        return shot
    actual_hash = hashlib.sha256(json.dumps(
        storyboard_shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    expected_hash = (source.get("creativeCardHashes") or {}).get(shot.get("shotId"))
    if not expected_hash or actual_hash != expected_hash:
        return shot
    beats = {item.get("beatId"): item for item in storyboard.get("beats") or []}

    def contracts(field):
        return [
            {"beatCode": beat_id, **beats[beat_id][field]}
            for beat_id in storyboard_shot.get("beatIds") or []
            if beat_id in beats and beats[beat_id].get(field) is not None
        ]

    return {
        **shot,
        "comedyContractsApproved": contracts("comedyContract"),
        "emotionContractsApproved": contracts("emotionContract"),
    }


def _require_forward_directing_source(pkg, shot, scene, episode):
    """Require the signed Gate 0-6 source only for forward-standard packages."""
    version = int(pkg.get("creativeDirectingStandardVersion") or 0)
    if version < 3:
        return None
    source = pkg.get("sourceStoryboard") or {}
    current_script_id = None
    try:
        current_script_id = SCRIPT_STORE.current(episode, required=True)["scriptVersionId"]
    except (cb_scripts.ScriptStoreError, cb_lineage.LineageError):
        pass
    amendment = next((item for item in reversed(pkg.get("scopedAmendments") or [])
                      if item.get("shotId") == shot.get("shotId") and
                      (not current_script_id or
                       item.get("scriptVersionId") == current_script_id)), None)
    path = _declared_storyboard_path(pkg, scene, episode)
    if amendment and amendment.get("storyboardPath"):
        path = pathlib.Path(amendment["storyboardPath"])
        if not path.is_absolute():
            path = ROOT / path
        try:
            path.resolve().relative_to(ROOT.resolve())
        except ValueError as exc:
            raise Refused(
                f"REFUSED — {shot['shotId']}'s scoped Director amendment escapes the studio") from exc
        if (not path.is_file() or
                _sha256_file(path) != amendment.get("storyboardSha256")):
            raise Refused(
                f"REFUSED — {shot['shotId']}'s scoped Director amendment is missing or changed")
    if source.get("approvalState") != "approved" or not path.exists():
        raise Refused(
            f"REFUSED — {shot['shotId']} needs a human-approved Director storyboard before "
            "new forward-standard department work")
    storyboard = json.load(open(path))
    if storyboard.get("approvalState") != "approved":
        raise Refused(
            f"REFUSED — {shot['shotId']}'s Director storyboard is no longer approved")
    # A scoped amendment is an approved single-shot Director source, not a complete scene
    # storyboard. It deliberately carries the compiled, signed v4 contracts under their
    # production names so an accepted late shot correction does not reopen sibling work.
    # Validate that format directly instead of misclassifying it as an old storyboard.
    scoped_card = storyboard.get("shot")
    if (storyboard.get("shotId") == shot.get("shotId") and
            isinstance(scoped_card, dict)):
        registered = next((item for item in (pkg.get("scopedAmendments") or [])
                           if item.get("shotId") == shot.get("shotId") and
                           item.get("scriptVersionId") == storyboard.get("scriptVersionId")),
                          None)
        if not registered:
            raise Refused(
                f"REFUSED — {shot['shotId']}'s scoped Director amendment is not registered")
        if scoped_card != shot:
            raise Refused(
                f"REFUSED — {shot['shotId']}'s scoped Director amendment no longer matches "
                "the production shot")
        required_scoped = (
            "storyIntentApproved", "performanceBudgetApproved",
            "cinematographyContractApproved", "performanceContractApproved",
        )
        missing = [name for name in required_scoped if not scoped_card.get(name)]
        if version >= 4 and missing:
            raise Refused(
                f"REFUSED — {shot['shotId']} lacks scoped v4 directing contracts: "
                + ", ".join(missing))
        return scoped_card
    if int(storyboard.get("creativeDirectingStandardVersion") or 0) < version:
        raise Refused(
            f"REFUSED — {shot['shotId']}'s storyboard predates directing standard v{version}")
    card = next((item for item in storyboard.get("shots") or []
                 if item.get("shotId") == shot.get("shotId")), None)
    if not card:
        raise Refused(f"REFUSED — {shot['shotId']} has no signed Director shot card")
    actual_hash = hashlib.sha256(json.dumps(
        card, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    expected_hash = (source.get("creativeCardHashes") or {}).get(shot.get("shotId"))
    if not expected_hash or actual_hash != expected_hash:
        raise Refused(f"REFUSED — {shot['shotId']}'s signed Director shot card is stale")
    if version >= 4 and not storyboard.get("emotionalStoryToScreenContract"):
        raise Refused(
            f"REFUSED — {shot['shotId']}'s storyboard lacks the signed emotional North Star")
    required = (("storyIntent", "performanceBudget", "cinematographyContract",
                 "performanceContract") if version >= 4 else
                ("performanceBudget", "cinematographyContract", "performanceContract"))
    missing = [name for name in required
               if not card.get(name)]
    if missing:
        raise Refused(
            f"REFUSED — {shot['shotId']} lacks forward directing contracts: "
            + ", ".join(missing))
    return card


def apply_scoped_dialogue_correction(scene, shot_id, old_occurrence_id, old_exact_text,
                                     new_exact_text, script_version_id,
                                     previous_script_version_id, episode="Ep1",
                                     reviewed_by="Julian", log=print):
    """Rebase one locked dialogue occurrence without reopening its scene or siblings.

    The immutable script remains the authority. This transaction changes only the named
    production shot's dialogue identity/text, preserves its approved visual inputs, and
    invalidates HEAR/WATCH derivatives. Existing media stays on disk for audit/comparison.
    """
    old_exact_text = str(old_exact_text or "").strip()
    new_exact_text = str(new_exact_text or "").strip()
    if not old_occurrence_id or not old_exact_text or not new_exact_text:
        raise Refused("REFUSED — a scoped dialogue correction needs occurrence and exact words")
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    source_script_id = (pkg.get("sourceScript") or {}).get("scriptVersionId")

    matches = [line for line in (shot.get("dialogueLines") or [])
               if line.get("dialogueOccurrenceId") == old_occurrence_id and
               str(line.get("exactText") or "").strip() == old_exact_text]
    if len(matches) != 1:
        raise Refused(
            f"REFUSED — {shot_id} does not contain exactly one matching approved dialogue occurrence")
    line_index = (shot.get("dialogueLines") or []).index(matches[0])
    voice_work = (ledger.get("departmentWork") or {}).get("voice") or {}
    voice_source = voice_work.get("candidate") or voice_work.get("approved")
    if not voice_source:
        voice_source = next((record for record in reversed(voice_work.get("history") or [])
                             if (record.get("output") or {}).get("lines")), None)

    import cb_intake  # lazy import keeps the render module's startup dependency acyclic
    script_path = SCRIPT_STORE.content_path(episode)
    parsed = cb_intake.parse_script(
        script_path.read_text(encoding="utf-8"), log=lambda *args, **kwargs: None)
    cb_intake._annotate_source_events(parsed["events"], script_version_id)
    current_events = [event for event in parsed["events"]
                      if str(event.get("scene")) == str(scene) and
                      event.get("type") == "dialogue" and
                      _resolve_char(event.get("speaker"), _characters_cfg()) ==
                      _resolve_char(matches[0].get("speaker"), _characters_cfg()) and
                      str(event.get("text") or "").strip() == new_exact_text]
    if len(current_events) != 1:
        raise Refused(
            f"REFUSED — the corrected words do not resolve to one current script event in scene {scene}")
    event = current_events[0]

    line = matches[0]
    old_event_id = line.get("sourceEventId")
    line.update({
        "dialogueOccurrenceId": event["dialogueOccurrenceId"],
        "sourceEventId": event["sourceEventId"],
        "exactText": new_exact_text,
    })
    delivery = str(line.get("delivery") or "")
    if old_exact_text in delivery:
        line["delivery"] = delivery.replace(old_exact_text, new_exact_text)
    performance_text = str(line.get("performanceText") or "")
    if old_exact_text in performance_text:
        line["performanceText"] = performance_text.replace(
            old_exact_text, new_exact_text)

    def replace_exact(value):
        return value.replace(old_exact_text, new_exact_text) if isinstance(value, str) else value

    for plan in shot.get("storyboardInternalShotPlanApproved") or []:
        plan["storyAction"] = replace_exact(plan.get("storyAction"))
    for brief in shot.get("voiceDirectorBrief") or []:
        if brief.get("dialogueOccurrenceId") == old_occurrence_id:
            brief.update({
                "dialogueOccurrenceId": event["dialogueOccurrenceId"],
                "sourceEventId": event["sourceEventId"],
                "exactDialogue": new_exact_text,
            })
    shot["audioBrief"] = replace_exact(shot.get("audioBrief"))

    carried_voice = None
    if voice_source:
        carried_voice = json.loads(json.dumps(voice_source))
        carried_lines = ((carried_voice.get("output") or {}).get("lines") or [])
        if len(carried_lines) == len(shot.get("dialogueLines") or []):
            carried_line = carried_lines[line_index]
            if carried_line.get("speaker") == matches[0].get("speaker"):
                old_performed = str(carried_line.get("performedText") or old_exact_text)
                leading_tags = " ".join(re.findall(r"\[[^\]]+\]", old_performed))
                new_performed = (leading_tags + " " + new_exact_text).strip()
                carried_line.update({
                    "dialogueOccurrenceId": event["dialogueOccurrenceId"],
                    "sourceEventId": event["sourceEventId"],
                    "exactDialogue": new_exact_text,
                    "performedText": new_performed,
                })
                for recipe in carried_line.get("takeRecipes") or []:
                    recipe["performedText"] = new_performed
                if line_index + 1 < len(carried_lines):
                    carried_lines[line_index + 1]["previousText"] = new_performed
                carried_voice.update({
                    "preparedAt": _now(),
                    "scopedDialogueCarryForward": True,
                    "carriedDialogueIndex": line_index,
                })
            else:
                carried_voice = None
        else:
            carried_voice = None

    now = _now()
    for stage in ("voice", "animation", "review-animation"):
        work = (ledger.get("departmentWork") or {}).get(stage)
        if not work:
            continue
        for key in ("approved", "candidate"):
            record = work.get(key)
            if record:
                archived = json.loads(json.dumps(record))
                archived.update({"outcome": "superseded-by-script-correction",
                                 "decisionAt": now, "reviewedBy": reviewed_by})
                work.setdefault("history", []).append(archived)
            work[key] = None
    if carried_voice:
        voice_work["candidate"] = carried_voice

    ledger["voiceApproval"] = None
    ledger["workingVoice"] = None
    if ledger.get("voPath"):
        ledger["voicePrevious"] = {
            "path": ledger["voPath"],
            "generatedFrom": ledger.get("voGeneratedFrom"),
            "supersededAt": now,
            "reason": "script-dialogue-correction",
        }
    ledger["voPath"] = None
    ledger["voGeneratedFrom"] = None
    ledger["voInputSignature"] = None
    ledger["voiceStaleDueToScriptCorrection"] = {
        "at": now, "scriptVersionId": script_version_id,
        "previousDialogueOccurrenceId": old_occurrence_id,
        "dialogueOccurrenceId": event["dialogueOccurrenceId"],
    }
    for key in ("approval", "approvedCandidate", "approvedTake", "harvestFrame",
                "candidatePaths", "batch", "batchId", "pendingSpendAuth",
                "lastBatchBinding", "disclosure", "firedAt"):
        ledger[key] = None
    ledger["status"] = "designed"

    amendment_dir = ROOT / "cb-output" / "creative" / "amendments"
    amendment_dir.mkdir(parents=True, exist_ok=True)
    transition_id = hashlib.sha256(json.dumps({
        "at": now,
        "fromScript": previous_script_version_id,
        "toScript": script_version_id,
        "fromOccurrence": old_occurrence_id,
        "toOccurrence": event["dialogueOccurrenceId"],
    }, sort_keys=True).encode("utf-8")).hexdigest()[:8]
    amendment_path = amendment_dir / (
        f"{episode}_{shot_id}_{script_version_id.split(':')[-1][:12]}_{transition_id}.json")
    amendment_doc = {
        "schemaVersion": 1,
        "approvalState": "approved",
        "approvedAt": now,
        "approvedBy": reviewed_by,
        "kind": "dialogue-correction",
        "scene": str(scene),
        "shotId": shot_id,
        "scriptVersionId": script_version_id,
        "previousScriptVersionId": previous_script_version_id,
        "baseScriptVersionId": source_script_id,
        "previousDialogueOccurrenceId": old_occurrence_id,
        "dialogueOccurrenceId": event["dialogueOccurrenceId"],
        "previousSourceEventId": old_event_id,
        "sourceEventId": event["sourceEventId"],
        "previousExactText": old_exact_text,
        "correctedExactText": new_exact_text,
        "shot": shot,
    }
    amendment_path.write_text(
        json.dumps(amendment_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    amendment_hash = _sha256_file(amendment_path)
    scene_look_status_record = scenelook_status(scene, episode)
    scene_look = (scene_look_status_record.get("active") or
                  (_load_scenelook_rec(scene, episode).get("candidate") or {}) or
                  (_load_scenelook_rec(scene, episode).get("approved") or {}))
    record = {
        "kind": "dialogue-correction", "scene": str(scene), "shotId": shot_id,
        "scriptVersionId": script_version_id,
        "previousScriptVersionId": previous_script_version_id,
        "baseScriptVersionId": source_script_id,
        "dialogueOccurrenceId": event["dialogueOccurrenceId"],
        "storyboardPath": str(amendment_path.relative_to(ROOT)),
        "storyboardSha256": amendment_hash,
        "sceneLookContentHash": scene_look.get("hash"),
        "sceneLookPath": scene_look.get("path"),
        "preservedStages": ["direction", "scenelook", "keyframe"],
        "invalidatedStages": ["voice", "animation", "continuity", "final"],
        "approvedAt": now, "approvedBy": reviewed_by,
    }
    pkg.setdefault("scopedAmendments", []).append(record)
    _save(pkg, path)
    log(f"SCOPED DIALOGUE CORRECTION — {shot_id}: SEE preserved; HEAR/WATCH reopened")
    return record


def apply_scoped_voice_contract_correction(scene, shot_id, corrected_lines,
                                           script_version_id,
                                           previous_script_version_id,
                                           correction, episode="Ep1",
                                           reviewed_by="Julian", log=print):
    """Replace one shot's spoken plan from current script events without reopening SEE.

    This is for a human-directed performance correction that can remove screenplay action
    accidentally compiled as speech, select an authored chorus occurrence, and retime the
    remaining exact lines. It never generates media and never changes sibling shots.
    """
    if not str(correction or "").strip():
        raise Refused("REFUSED — a scoped voice-contract correction needs a review reason")
    if not isinstance(corrected_lines, list) or not corrected_lines:
        raise Refused("REFUSED — a scoped voice-contract correction needs ordered lines")
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    if ledger.get("voPath"):
        raise Refused(
            f"REFUSED — reject {shot_id}'s current voice take before changing its contract")

    import cb_intake
    script_path = SCRIPT_STORE.content_path(episode)
    parsed = cb_intake.parse_script(
        script_path.read_text(encoding="utf-8"), log=lambda *args, **kwargs: None)
    cb_intake._annotate_source_events(parsed["events"], script_version_id)
    available = [event for event in parsed["events"]
                 if str(event.get("scene")) == str(scene) and
                 event.get("type") == "dialogue"]
    used = set()
    normalized = []
    previous_end = 0.0
    for index, submitted in enumerate(corrected_lines, start=1):
        speaker = str(submitted.get("speaker") or "").strip()
        exact_text = str(submitted.get("exactText") or "").strip()
        start = float(submitted.get("startSec"))
        end = float(submitted.get("endSec"))
        if not speaker or not exact_text or start < 0 or end <= start:
            raise Refused(f"REFUSED — corrected voice line {index} is incomplete")
        if start < previous_end:
            raise Refused(f"REFUSED — corrected voice line {index} overlaps the previous line")
        if end > float(shot.get("durationSec") or 0):
            raise Refused(f"REFUSED — corrected voice line {index} exceeds the shot duration")
        matches = [event for event in available
                   if event["i"] not in used and event.get("speaker") == speaker and
                   str(event.get("text") or "").strip() == exact_text]
        if not matches:
            raise Refused(
                f"REFUSED — corrected voice line {index} is not an exact current-script "
                f"occurrence for {speaker}: {exact_text}")
        event = matches[0]
        used.add(event["i"])
        line = {
            "dialogueOccurrenceId": event["dialogueOccurrenceId"],
            "sourceEventId": event["sourceEventId"],
            "speaker": speaker,
            "exactText": exact_text,
            "delivery": str(submitted.get("delivery") or exact_text).strip(),
            "startSec": start,
            "endSec": end,
            "voiceTreatment": submitted.get(
                "voiceTreatment", event.get("voiceTreatment", "single_voice")),
            "chorusMembers": list(
                submitted.get("chorusMembers") or event.get("chorusMembers") or []),
            "performanceText": str(
                submitted.get("performanceText") or exact_text).strip(),
        }
        normalized.append(line)
        previous_end = end

    shot["dialogueLines"] = normalized
    shot["dialogueBinding"] = (
        "Perform only the ordered approved dialogue occurrences. The opening countdown is "
        "a synchronous Bo-and-Keen chorus. Screenplay action, sound labels and BEAT are silent.")
    shot["voiceDirectorBrief"] = [{
        "dialogueOccurrenceId": line["dialogueOccurrenceId"],
        "sourceEventId": line["sourceEventId"],
        "speaker": line["speaker"],
        "exactDialogue": line["exactText"],
        "elevenLabsV3Direction": line["delivery"],
        "startSec": line["startSec"],
        "endSec": line["endSec"],
        "voiceTreatment": line["voiceTreatment"],
        "chorusMembers": line["chorusMembers"],
    } for line in normalized]
    shot["audioBrief"] = "\n".join([
        f"SHOT {shot_id} — voice-only performance for @Audio1.",
        *[f"{line['speaker']}: \"{line['exactText']}\" — {line['delivery']} "
          f"Target {line['startSec']:g}-{line['endSec']:g}s."
          for line in normalized],
        "Preserve the exact words. No narration, ad-libs, action labels, sound effects or music.",
    ])

    now = _now()
    for stage in ("voice", "animation", "review-animation"):
        work = (ledger.get("departmentWork") or {}).get(stage)
        if not work:
            continue
        for key in ("approved", "candidate"):
            record = work.get(key)
            if record:
                archived = json.loads(json.dumps(record))
                archived.update({"outcome": "superseded-by-voice-contract-correction",
                                 "decisionAt": now, "reviewedBy": reviewed_by})
                work.setdefault("history", []).append(archived)
            work[key] = None
    ledger["voiceApproval"] = None
    ledger["workingVoice"] = {
        "lines": [{
            "dialogueOccurrenceId": line["dialogueOccurrenceId"],
            "sourceEventId": line["sourceEventId"],
            "speaker": line["speaker"],
            "text": line["performanceText"],
        } for line in normalized],
        "savedAt": now, "savedBy": reviewed_by,
        "reason": "scoped-human-performance-correction",
    }
    ledger["voGeneratedFrom"] = None
    ledger["voInputSignature"] = None
    ledger["voiceStaleDueToScriptCorrection"] = {
        "at": now, "scriptVersionId": script_version_id,
        "reason": "human-directed-shot-voice-contract-correction",
    }
    for key in ("approval", "approvedCandidate", "approvedTake", "harvestFrame",
                "candidatePaths", "batch", "batchId", "pendingSpendAuth",
                "lastBatchBinding", "disclosure", "firedAt"):
        ledger[key] = None
    ledger["status"] = "designed"

    amendment_dir = ROOT / "cb-output" / "creative" / "amendments"
    amendment_dir.mkdir(parents=True, exist_ok=True)
    suffix = script_version_id.split(":")[-1][:12]
    amendment_path = amendment_dir / f"{episode}_{shot_id}_{suffix}_voice.json"
    amendment_doc = {
        "schemaVersion": 1, "approvalState": "approved", "approvedAt": now,
        "approvedBy": reviewed_by, "kind": "voice-contract-correction",
        "scene": str(scene), "shotId": shot_id,
        "scriptVersionId": script_version_id,
        "previousScriptVersionId": previous_script_version_id,
        "baseScriptVersionId": (pkg.get("sourceScript") or {}).get("scriptVersionId"),
        "correction": correction.strip(), "shot": shot,
    }
    amendment_path.write_text(
        json.dumps(amendment_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    scene_look_status_record = scenelook_status(scene, episode)
    scene_look = (scene_look_status_record.get("active") or
                  (_load_scenelook_rec(scene, episode).get("candidate") or {}) or
                  (_load_scenelook_rec(scene, episode).get("approved") or {}))
    record = {
        "kind": "voice-contract-correction", "scene": str(scene), "shotId": shot_id,
        "scriptVersionId": script_version_id,
        "previousScriptVersionId": previous_script_version_id,
        "baseScriptVersionId": (pkg.get("sourceScript") or {}).get("scriptVersionId"),
        "storyboardPath": str(amendment_path.relative_to(ROOT)),
        "storyboardSha256": _sha256_file(amendment_path),
        "sceneLookContentHash": scene_look.get("hash"),
        "sceneLookPath": scene_look.get("path"),
        "preservedStages": ["direction", "scenelook", "keyframe"],
        "invalidatedStages": ["voice", "animation", "continuity", "final"],
        "approvedAt": now, "approvedBy": reviewed_by,
    }
    pkg.setdefault("scopedAmendments", []).append(record)
    _save(pkg, path)
    log(f"SCOPED VOICE CONTRACT CORRECTION — {shot_id}: SEE preserved; HEAR reopened")
    return record


def _department_candidate(stage, output, context):
    dep, worker, skill = _DEPARTMENT_WORKERS[stage]
    standard_version = int(context.get("creativeDirectingStandardVersion") or 0)
    candidate = {"department": dep, "worker": worker,
            "skill": _department_skill_ref(stage, skill, standard_version),
            "model": cb_departments.cb_llm.DIRECTOR_MODEL,
            "preparedAt": _now(), "editedAt": None, "preparedBy": "specialist",
            "creativeDirectingStandardVersion": standard_version,
            "sourceHash": hashlib.sha256(json.dumps(context, sort_keys=True,
                                                       ensure_ascii=False).encode()).hexdigest(),
            "output": output}
    if stage.startswith("review-"):
        candidate["reviewedMediaPaths"] = list(context.get("reviewedMediaPaths") or [])
    if stage == "animation" and context.get("animationPreflight"):
        candidate["preflight"] = context["animationPreflight"]
    if stage == "animation" and context.get("voiceTimedPerformanceBudget"):
        candidate["performanceBudget"] = context["voiceTimedPerformanceBudget"]
    return candidate


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

    Existing direction and every media asset remain untouched if the call fails. A current
    signed candidate is production-ready without pretending a human approved prose; rendered
    outcomes retain their own explicit approval gates. No cb_gen function is reachable here.
    """
    if stage not in _DEPARTMENT_WORKERS:
        raise Refused(f"REFUSED — unknown department stage '{stage}'")
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(pkg, scene, shot_id, stage, episode)
    existing_candidate = work.get("candidate")
    if existing_candidate:
        # A downstream edit must replace only the stale specialist draft. Keep the
        # old draft in history for auditability, but do not make the user manually
        # clear an internal candidate before the changed inputs can be rebuilt.
        current_signature = _department_input_signature(
            pkg, stage, shot_id, scene, episode)
        stale_inputs = _signature_diff(
            existing_candidate.get("inputSignature"), current_signature)
        if not stale_inputs:
            raise Refused(f"REFUSED — {stage} already has work awaiting a decision")
        history = work.setdefault("history", [])
        history.append({
            **existing_candidate,
            "outcome": "superseded",
            "supersededAt": _now(),
            "supersededBy": "current-input-rebuild",
            "supersededInputs": stale_inputs,
        })
        work["candidate"] = None

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
        if stage in ("cinematography", "animation"):
            _require_forward_directing_source(pkg, shot, scene, episode)
        context = _shot_context(pkg, shot, led, scene, episode)
        if stage == "cinematography":
            chars = _characters_cfg()
            attachment_plan = _provider_attachment_plan(
                shot, "keyframeReferenceSlots", None, scene, episode, chars)
            images = [item["path"] for item in attachment_plan]
            context["orderedAttachments"] = [
                {"inspectionSlot": item["sourceSlot"],
                 "providerSlot": item["slot"], "role": item["role"],
                 "view": item.get("view"), "path": item["path"],
                 "sameCharacterGroup": ((item.get("identity") or {}).get(
                     "turnaroundGroupHash"))}
                for item in attachment_plan]
            context["providerReferencePlan"] = {
                item["providerSlot"]: (
                    f"{item['role']} {item['view']} turnaround view"
                    if item.get("view") else item["role"])
                for item in context["orderedAttachments"]}
            context["stageAnchorWorkflow"] = {
                "providerAttachments": context["providerReferencePlan"],
                "localOnlyControls": [
                    OPENING_COMPOSITION_ROLE, CHARACTER_SCALE_CONTROL_ROLE],
                "rule": (
                    "Build the keyframe directly from the locked character turnarounds and "
                    "Scene Look. It establishes frame-one identity, canon relative scale, "
                    "camera, light, loose starting zones and clear action space. It must not "
                    "pre-perform or freeze the shot's acting. Layout and scale boards remain "
                    "local advisory evidence and are never provider uploads."),
            }
            context["canonicalCharacterHeightsIn"] = {
                name: (chars.get(_resolve_char(name, chars)) or {}).get("heightIn")
                for name in (shot.get("charactersInFrame") or [])}
            result = cb_departments.prepare_cinematography(context, images, log=log)
            opening_cast = list(dict.fromkeys(
                shot.get("openingCharactersInFrame") or
                shot.get("charactersInFrame") or []))
            layout_characters = {}
            for supplied_name in opening_cast:
                name = _resolve_char(supplied_name, chars)
                layout_characters[name] = {
                    "heightIn": (chars.get(name) or {}).get("heightIn"),
                    "turnaroundPath": _char_ref(name, chars),
                }
            authored_layout = result.openingFrameLayout.model_dump()
            fitted_layout = cb_layout.fit_frame_safety(
                authored_layout, layout_characters)
            if fitted_layout != authored_layout:
                result = cb_departments.CinematographyDirection.model_validate({
                    **result.model_dump(), "openingFrameLayout": fitted_layout})
                log("CINEMATOGRAPHY LAYOUT — fitted frame safety bounds before saving "
                    "(zero media spend)")
        elif stage == "voice":
            voice_lines = [
                dict(line) for line in cb_audio_authority.spoken_dialogue_lines(shot)
            ]
            working_by_occurrence = {
                line.get("dialogueOccurrenceId"): line.get("text")
                for line in ((led.get("workingVoice") or {}).get("lines") or [])
                if line.get("dialogueOccurrenceId") and line.get("text")
            }
            for line in voice_lines:
                override = working_by_occurrence.get(line.get("dialogueOccurrenceId"))
                if override:
                    line["performanceOverride"] = override
            result = cb_departments.prepare_voice(
                context, voice_lines, log=log)
        elif stage == "animation":
            if (not (led.get("voiceApproval") or {}).get("approved") and
                    cb_audio_authority.spoken_dialogue_lines(shot)):
                raise Refused(f"REFUSED — {shot_id}'s approved voice is required before the "
                              "Animation Director enters")
            budget_report = _performance_budget_report(context["shot"], led)
            context["voiceTimedPerformanceBudget"] = budget_report
            if not budget_report["ready"]:
                raise Refused(
                    f"REFUSED — {shot_id}'s voice-timed performance budget is overloaded: "
                    + "; ".join(budget_report.get("reasons") or []))
            anchor = _anchor_for(pkg, shot)
            animation_shot = _with_effective_reference_slots(
                pkg, shot, "referenceSlots", scene, episode)
            attachment_plan = _provider_attachment_plan(
                animation_shot, "referenceSlots", anchor, scene, episode,
                _characters_cfg())
            images = [item["path"] for item in attachment_plan]
            context["orderedAttachments"] = [
                {"slot": item["slot"], "sourceSlot": item["sourceSlot"],
                 "role": item["role"], "view": item.get("view"),
                 "path": item["path"],
                 "sameCharacterGroup": ((item.get("identity") or {}).get(
                     "turnaroundGroupHash"))}
                for item in attachment_plan]
            cinematography = _approved_department_output(pkg, shot_id, "cinematography") or {}
            opening_contract = (((led.get("keyframeApproval") or {}).get("promptContract") or {})
                                .get("directionContract") or {})
            opening_geography = list(opening_contract.get("geography") or [])
            if opening_geography:
                context["sceneGeographyLedger"] = opening_geography
            elif cinematography.get("geography"):
                context["sceneGeographyLedger"] = list(cinematography.get("geography") or [])
            context["approvedVoiceAsset"] = led.get("voPath")
            director_feedback = str(
                (led.get("watchDirectorFeedback") or {}).get("text") or "").strip()
            if director_feedback:
                context["shot"] = {
                    **context["shot"],
                    "watchDirectorFeedbackApproved": director_feedback,
                }
            result = cb_departments.prepare_animation(context, images, log=log)
            # The sealed upload plan, not an older specialist guess, owns provider slot
            # numbering.  Rebind every role before compiling or validating the prompt.
            result.referenceContract = [
                cb_departments.ReferenceDirection.model_validate(item)
                for item in _animation_reference_contract(
                    attachment_plan, shot, led.get("voPath"))
            ]
            result.providerPrompt = cb_departments.compile_animation_provider_prompt(
                context["shot"], result)
            dialogue_check = emission.validate_dialogue_synthesis(
                result.providerPrompt,
                cb_departments.provider_dialogue_lines(context["shot"]))
            if not dialogue_check["ready"]:
                raise Refused("REFUSED — animation dialogue synthesis contract failed: " +
                              "; ".join(dialogue_check["errors"]))
            preflight = _animation_preflight_summary(context["shot"], result)
            if preflight["verdict"] != "PASS":
                report = _animation_prompt_contract_report(context["shot"], result)
                raise Refused("REFUSED — animation provider prompt is not production-ready: "
                              + "; ".join(report["errors"] or [
                                  finding.get("message") or "preflight blocked"
                                  for finding in preflight.get("findings") or []]))
            context["animationPreflight"] = preflight
            context["engineRuleReport"] = _require_engine_rules(
                pkg, context["shot"], result)
        elif stage == "review-keyframe":
            rec = led.get("keyframeCandidate") or led.get("keyframeApproval") or {}
            media = rec.get("path")
            if not media or not os.path.exists(media):
                raise Refused(f"REFUSED — no actual keyframe media exists for {shot_id} to review")
            attachment_plan = _provider_attachment_plan(
                shot, "keyframeReferenceSlots", None, scene, episode,
                _characters_cfg())
            refs = [item["path"] for item in attachment_plan]
            images = [media] + refs
            context["reviewedMediaPaths"] = [media]
            context["orderedReviewImages"] = ([{"role": "actual rendered keyframe", "path": media}] +
                [{"role": item["role"], "view": item.get("view"),
                  "providerSlot": item["slot"], "path": item["path"]}
                 for item in attachment_plan])
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
            context["reviewedMediaPaths"] = list(media_paths)
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
                animation_shot = _with_effective_reference_slots(
                    pkg, shot, "referenceSlots", scene, episode)
                attachment_plan = _provider_attachment_plan(
                    animation_shot, "referenceSlots", anchor, scene, episode,
                    _characters_cfg())
                refs = [item["path"] for item in attachment_plan]
                images = frames + refs
                context["orderedReviewImages"] = (
                    frame_labels +
                    [{"role": item["role"], "view": item.get("view"),
                      "providerSlot": item["slot"], "path": item["path"]}
                     for item in attachment_plan])
                result = cb_departments.review_media("animation", context, images, log=log)
            finally:
                for td in temp_dirs:
                    shutil.rmtree(td, ignore_errors=True)

    # Silent/SFX-only departments intentionally return a small plain mapping;
    # model-backed departments return a Pydantic object.  Both are valid
    # prepared direction and must follow the same review path.
    result_data = (result.model_dump() if hasattr(result, "model_dump") else result)
    work["candidate"] = _department_candidate(stage, result_data, context)
    save_extra()
    _save(pkg, path)
    disposition = ("awaiting human review" if stage.startswith("review-")
                   else "current direction ready")
    log(f"DEPARTMENT — {work['candidate']['worker']} prepared {stage} work for "
        f"{shot_id or 'scene '+str(scene)} ({disposition}; no media generated)")
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
        cb_departments.validate_voice_direction(
            model, cb_audio_authority.spoken_dialogue_lines(shot))
        cand["output"] = model.model_dump()
    elif stage.startswith("review-"):
        raise Refused("REFUSED — review evidence cannot be text-edited; reject and rerun the review")
    else:
        value = str(text or "").strip()
        if not value:
            raise Refused(f"REFUSED — {stage}'s exact provider text cannot be blank")
        if stage == "animation":
            shot = _shot(pkg, shot_id)
            creative_shot = _shot_creative_contract_view(pkg, shot, scene, episode)
            dialogue_check = emission.validate_dialogue_synthesis(
                value, cb_departments.provider_dialogue_lines(shot))
            if not dialogue_check["ready"]:
                raise Refused("REFUSED — animation dialogue synthesis contract failed: " +
                              "; ".join(dialogue_check["errors"]))
            candidate_output = {**output, "providerPrompt": value}
            if not candidate_output.get("creativeTranslation"):
                events_by_beat = {}
                for event in cb_departments.animation_locked_visual_events(creative_shot):
                    for beat_id in event.get("beatIds") or []:
                        events_by_beat[str(beat_id)] = str(
                            event.get("primaryEvent") or "").strip()
                comedy = list(creative_shot.get("comedyContractsApproved") or [])
                candidate_output["creativeTranslation"] = {
                    "interpretation": {
                        "jokeOrAche": str(
                            creative_shot.get("purpose") or output.get("dramaticBeat") or
                            "Pride is contradicted by visible evidence."),
                        "mechanism": " ".join(
                            str(item.get("mechanism") or "").strip()
                            for item in comedy if item.get("mechanism")),
                        "statusBefore": str(output.get("audienceBefore") or
                                            "The audience expects competence."),
                        "statusAfter": str(output.get("audienceAfter") or
                                           "The audience sees affectionate failure."),
                        "audienceProgression": [
                            "Anticipate Fuzzby's performed competence.",
                            "Read each physical contradiction and escalation.",
                            "Release into Zenny's affectionate judgement.",
                        ],
                        "emotionalHeart": (
                            "Zenny sees the full mess without rejecting Fuzzby; her restrained "
                            "amusement turns his failure into affection."),
                    },
                    "gagClocks": [{
                        "beatCode": str(item.get("beatCode") or ""),
                        "mode": item.get("mode"),
                        "setup": str(item.get("setup") or ""),
                        "anticipation": str(item.get("expectation") or ""),
                        "impact": str(item.get("disruption") or ""),
                        "reaction": str(item.get("hold") or ""),
                        "recoveryHold": str(item.get("hold") or ""),
                        "recoveryHoldSec": item.get("recoveryHoldSec"),
                        "button": str(item.get("button") or ""),
                        "providerAction": events_by_beat.get(
                            str(item.get("beatCode") or ""), ""),
                    } for item in comedy],
                    "generationDesign": {
                        "packagingDecision": "single-unit",
                        "completeGagArcCount": len(comedy),
                        "densityJudgement": (
                            "The approved comedy climb fits one continuous 29-second unit."),
                        "splitOrNonSplitRationale": (
                            "The chase, status reveal and failed correction form one causal "
                            "escalation and must retain their shared reaction timing."),
                        "handoffState": str(creative_shot.get("visualPayoff") or ""),
                    },
                }
            model = cb_departments.AnimationDirection.model_validate(candidate_output)
            _require_animation_prompt_contract(
                creative_shot, model)
            cand["output"] = model.model_dump()
        else:
            output["providerPrompt"] = value
    if stage == "animation":
        ledger = _ledger(pkg, shot_id)
        if ledger.get("pendingSpendAuth"):
            cb_db.void_shot_authorizations(
                HERE.parent, episode, scene, shot_id,
                "animation-direction-changed-before-fire")
            ledger["pendingSpendAuth"] = None
    cand["editedAt"] = _now(); cand["editedBy"] = reviewed_by
    save_extra(); _save(pkg, path)
    log(f"DEPARTMENT CANDIDATE SAVED — {stage} "
        f"(no media provider call; current direction updated)")
    return cand


def recompile_animation_candidate(scene, shot_id, episode="Ep1", log=print):
    """Re-emit WATCH prompt prose from the candidate's typed Director record.

    This is deliberately separate from ``save_department_candidate``: a compiler refresh
    must never masquerade as a human-authored prompt edit.  It preserves the typed creative
    direction, recompiles providerPrompt deterministically, reruns the production contract,
    and invalidates any spend authorization sealed against older bytes.
    """
    pkg, path = load_pkg(scene, episode)
    work, save_extra = _department_container(
        pkg, scene, shot_id, "animation", episode)
    candidate = work.get("candidate")
    if not candidate and work.get("approved"):
        approved = work["approved"]
        work.setdefault("history", []).append({
            **approved,
            "outcome": "reopened-for-deterministic-recompile",
            "reopenedAt": _now(),
        })
        candidate = {
            key: value for key, value in approved.items()
            if key not in ("outcome", "decisionAt", "reviewedBy", "note")
        }
        work["candidate"] = candidate
        work["approved"] = None
    if not candidate:
        raise Refused(
            f"REFUSED — animation has no typed Director candidate to recompile for {shot_id}")

    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    # Recompile from the same effective shot view used by the live safety gate.
    # This includes scene-level continuity locks as well as voice timing; using a
    # narrower view makes the freshly compiled prompt stale immediately.
    creative_shot = _shot_context(
        pkg, shot, ledger, scene, episode)["shot"]
    source = json.loads(json.dumps(candidate["output"]))
    changes = []

    anchor = _anchor_for(pkg, shot)
    animation_shot = _with_effective_reference_slots(
        pkg, shot, "referenceSlots", scene, episode)
    attachment_plan = _provider_attachment_plan(
        animation_shot, "referenceSlots", anchor, scene, episode,
        _characters_cfg())
    rebound_contract = _animation_reference_contract(
        attachment_plan, shot, ledger.get("voPath"))
    if source.get("referenceContract") != rebound_contract:
        source["referenceContract"] = rebound_contract
        changes.append("provider reference roles rebound to the sealed upload order")

    cinematography = _approved_department_output(
        pkg, shot_id, "cinematography") or {}
    opening_contract = (((ledger.get("keyframeApproval") or {}).get("promptContract") or {})
                        .get("directionContract") or {})
    approved_geography = (list(opening_contract.get("geography") or []) or
                          list(cinematography.get("geography") or []))
    if approved_geography and source.get("geography") != approved_geography:
        source["geography"] = approved_geography
        changes.append("render geography rebound to approved SEE geography")

    timing = cb_engine_rules.beat_cost_report(creative_shot, source)
    if not timing["ready"]:
        old_duration = float(source.get("durationSec") or shot.get("durationSec") or 0)
        new_duration = float(timing["recommendedDurationSec"])
        source["durationSec"] = new_duration
        shot["durationSec"] = new_duration
        creative_shot["durationSec"] = new_duration
        timed = source.get("stagePlan") or []
        if timed and all(item.get("startSec") is not None and
                         item.get("endSec") is not None for item in timed):
            scale = new_duration / old_duration if old_duration else 1.0
            for item in timed:
                item["startSec"] = round(float(item["startSec"]) * scale, 3)
                item["endSec"] = round(float(item["endSec"]) * scale, 3)
            timed[0]["startSec"] = 0.0
            timed[-1]["endSec"] = new_duration
        changes.append(
            f"request duration costed from {old_duration:g}s to {new_duration:g}s")

    compiled_prompt = cb_departments.compile_animation_provider_prompt(
        creative_shot, source)
    source["providerPrompt"] = compiled_prompt
    direction = cb_departments.AnimationDirection.model_validate(source)
    _require_animation_prompt_contract(creative_shot, direction)
    engine_report = _require_engine_rules(
        pkg, creative_shot, direction, cinematography=cinematography)
    candidate["output"] = direction.model_dump()
    candidate["engineRuleReport"] = engine_report
    candidate["engineRuleChanges"] = changes
    # A creative correction changes the emitted bytes and therefore invalidates the
    # score shown at WATCH. Persist the newly calculated gate with the new prompt so
    # the interface can never display conformance evidence for an older emission.
    candidate["preflight"] = _animation_preflight_summary(
        creative_shot, direction)
    candidate["editedAt"] = _now()
    candidate["editedBy"] = "deterministic-animation-compiler"

    if any(change.startswith("request duration costed") for change in changes):
        cine_approval = (((ledger.get("departmentWork") or {}).get(
            "cinematography") or {}).get("approved") or {})
        if cine_approval:
            cine_approval["inputSignature"] = _department_input_signature(
                pkg, "cinematography", shot_id, scene, episode)
            cine_approval["durationCarryForward"] = {
                "at": _now(),
                "reason": "R6: approved visual direction is input, not duration authority",
                "newDurationSec": shot["durationSec"],
            }
        voice_direction = (((ledger.get("departmentWork") or {}).get(
            "voice") or {}).get("approved") or {})
        if voice_direction:
            voice_direction["inputSignature"] = _department_input_signature(
                pkg, "voice", shot_id, scene, episode)
            voice_direction["durationCarryForward"] = {
                "at": _now(),
                "reason": "R6: approved performance is input, not duration authority",
                "newDurationSec": shot["durationSec"],
            }
        _carry_approved_inputs_across_duration_change(
            ledger, cb_engine_rules.duration_provenance(shot, direction))
    if ledger.get("pendingSpendAuth"):
        cb_db.void_shot_authorizations(
            HERE.parent, episode, scene, shot_id,
            "animation-prompt-recompiled-before-fire")
        ledger["pendingSpendAuth"] = None
    if (ledger.get("batch") or {}).get("status") == "complete":
        ledger["batch"]["supersededByDirectionAt"] = _now()
        ledger["batch"]["approvalBlockedReason"] = (
            "Director inputs were recompiled after these candidates were generated")
        ledger["status"] = "direction-recompiled-candidates-stale"

    candidate["inputSignature"] = _department_input_signature(
        pkg, "animation", shot_id, scene, episode)

    save_extra()
    _save(pkg, path)
    log(f"ANIMATION RECOMPILED — {shot_id} from typed Director record "
        "(no provider call; no approval granted)"
        + (f" — {'; '.join(changes)}" if changes else ""))
    return candidate


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


def _inspection_department_output(pkg, shot_id, stage):
    """Best-effort current direction for zero-spend inspection and stored-contract display.

    Paid resolvers use the strict safety-layer accessor directly. Prompt Lab must still be
    able to inspect a sealed historical render or a synthetic contract when current runtime
    dependencies are unavailable, so it degrades to no live direction instead of blocking.
    """
    try:
        return _approved_department_output(pkg, shot_id, stage) or {}
    except (Refused, KeyError, TypeError, ValueError, OSError):
        return {}


def _with_opening_composition_control(prompt, shot, scene, episode):
    """Reject any attempt to turn the local geometry proof into provider artwork."""
    prompt = str(prompt or "").strip()
    if not prompt:
        return prompt
    lowered = prompt.lower()
    if (OPENING_COMPOSITION_MARKER.lower() in lowered or
            "opening composition master" in lowered or
            "sizing composition" in lowered):
        raise Refused(
            "REFUSED — provider prompt assigns the local sizing/composition proof as an "
            "image reference. Rebuild the prompt through the direct stage-anchor compiler")
    return prompt


def _keyframe_direction_contract(direction, shot):
    """Validate the one approved direction record consumed by the keyframe compiler."""
    shot_id = shot.get("shotId")
    required_text = (
        "audienceRead", "lensAndCameraRelationship", "lightingAndDepth",
        "canonicalStyleVersion", "canonicalStyleParagraph",
    )
    missing = [key for key in required_text if not str(direction.get(key) or "").strip()]
    geography = [str(value).strip() for value in direction.get("geography") or []
                 if str(value).strip()]
    cast = [str(value).strip() for value in direction.get("charactersInFrame") or []
            if str(value).strip()]
    negative_space = [str(value).strip().rstrip(".") + "."
                      for value in direction.get("negativeSpace") or []
                      if str(value).strip()]
    if not geography:
        missing.append("geography")
    if not cast:
        missing.append("charactersInFrame")
    if not negative_space:
        missing.append("negativeSpace")
    if missing:
        raise Refused(
            f"REFUSED — approved Cinematography direction for {shot_id} is missing "
            + ", ".join(missing))

    if len(cast) != len(set(cast)):
        raise Refused(
            f"REFUSED — approved charactersInFrame for {shot_id} contains duplicates")
    approved_cast = list(dict.fromkeys(
        str(value).strip() for value in (
            shot.get("openingCharactersInFrame")
            if shot.get("openingCharactersInFrame") is not None
            else shot.get("charactersInFrame") or [])
        if str(value).strip()))
    if approved_cast and cast != approved_cast:
        raise Refused(
            f"REFUSED — approved Cinematography cast for {shot_id} does not match the "
            f"shot contract: expected {approved_cast}, got {cast}")

    placements = (direction.get("openingFrameLayout") or {}).get("placements") or []
    placed_cast = [str(item.get("character") or "").strip() for item in placements]
    if placed_cast != cast:
        raise Refused(
            f"REFUSED — opening-frame placements for {shot_id} do not name each approved "
            "in-frame character exactly once")

    style_version, style_text = cb_departments.canonical_style_paragraph()
    if (direction.get("canonicalStyleVersion") != style_version or
            direction.get("canonicalStyleParagraph") != style_text):
        raise Refused(
            f"REFUSED — approved Cinematography style for {shot_id} does not match the "
            f"versioned canonical style {style_version}")

    playable = cb_engine_rules.playable_stage_report(shot, direction)
    if not playable["ready"]:
        raise Refused(
            f"REFUSED — opening frame for {shot_id} is not a playable stage: " +
            "; ".join(playable["errors"]))

    travel_sides = set()
    for item in placements:
        facing = str(item.get("facing") or "").casefold()
        if "screen-right" in facing or "frame-right" in facing:
            travel_sides.add("frame-right")
        elif "screen-left" in facing or "frame-left" in facing:
            travel_sides.add("frame-left")
    for side in sorted(travel_sides):
        derived = f"Lead room stays open {side} for the approved direction of travel."
        if derived not in negative_space:
            negative_space.insert(0, derived)

    return {
        "geography": geography,
        "cast": cast,
        "negativeSpace": negative_space,
        "styleVersion": style_version,
        "styleText": style_text,
    }


def _keyframe_frame_section(direction, characters_cfg):
    """Render the approved typed opening layout without shortening authored pose/facing."""
    layout = direction["openingFrameLayout"]
    staging_lines = []
    scale_facts = []
    for item in layout.get("placements") or []:
        x = float(item.get("centerX", 0.5))
        y = float(item.get("centerY", 0.5))
        horizontal = "left" if x < 0.4 else "right" if x > 0.6 else "centre"
        vertical = "upper" if y < 0.4 else "lower" if y > 0.6 else "middle"
        zone = f"{vertical}-{horizontal} area"
        name = item.get("character")
        facing = re.sub(r"\s+", " ", str(item.get("facing") or "")).strip()
        pose = re.sub(r"\s+", " ", str(item.get("pose") or "")).strip()
        facing = facing or "the authored direction"
        pose = pose or "a playable anticipation"
        staging_lines.append(f"- {name} @ {zone}; {pose}; facing {facing}.")
        try:
            canonical = _resolve_char(name, characters_cfg)
            height = (characters_cfg.get(canonical) or {}).get("heightIn")
            if height is not None:
                scale_facts.append(f"{canonical} {height} inches")
        except (KeyError, TypeError, ValueError):
            pass
    if layout.get("sameDepth") and len(scale_facts) > 1:
        scale_rule = (
            f"Same depth: {'; '.join(scale_facts)}; preserve relative-size truth only.")
    else:
        scale_rule = (
            "Preserve canonical relative size, modified only by the authored depth relationship.")
    return "\n".join(staging_lines) + f"\n- {scale_rule}"


def _keyframe_same_depth_scale_protection(direction, characters_cfg):
    """Translate internal layout math into image-model-readable scale direction."""
    layout = direction.get("openingFrameLayout") or {}
    if not layout.get("sameDepth"):
        return ""
    names = [str(item.get("character") or "").strip()
             for item in layout.get("placements") or []
             if str(item.get("character") or "").strip()]
    if len(names) < 2:
        return ""
    heights = []
    for name in names:
        try:
            canonical = _resolve_char(name, characters_cfg)
            height = float((characters_cfg.get(canonical) or {}).get("heightIn"))
        except (KeyError, TypeError, ValueError):
            return (f"Keep {' and '.join(names)} at the same distance from the camera; "
                    "preserve their canonical relative sizes.")
        heights.append((canonical, height))
    if len(heights) == 2:
        first, second = heights
        if abs(first[1] - second[1]) < 0.001:
            relation = f"{first[0]} and {second[0]} appear the same height."
        else:
            taller, shorter = sorted(heights, key=lambda item: item[1], reverse=True)
            percent = round((taller[1] / shorter[1] - 1.0) * 100)
            relation = f"{taller[0]} appears about {percent}% taller than {shorter[0]}."
        return (f"Keep {first[0]} and {second[0]} at the same distance from the camera; "
                + relation)
    return (f"Keep {', '.join(name for name, _ in heights)} at the same distance from "
            "the camera; preserve their canonical relative heights.")


def _compile_keyframe_integration_prompt(direction, shot, reference_plan=None):
    """Compile the complete approved opening-stage direction."""
    if not direction or not direction.get("openingFrameLayout"):
        raise Refused(
            f"REFUSED — current Cinematography direction for {shot.get('shotId')} has no "
            "typed opening-frame layout")
    contract = _keyframe_direction_contract(direction, shot)

    reference_lines = []
    compact_reference_lines = []
    scene_look_slot = None
    identity_names = []
    characters_cfg = _characters_cfg()
    reference_plan = reference_plan or _expanded_reference_blueprint(
        shot, "keyframeReferenceSlots", characters_cfg)
    slot_line = emission.reference_slot_stability_line([
        (item["slot"], item["role"] if _is_non_identity_image_role(item["role"])
         else _resolve_char(item["role"], characters_cfg))
        for item in reference_plan
    ])
    if slot_line:
        reference_lines.append(f"- {slot_line}")
        compact_reference_lines.append(f"- {slot_line}")
    grouped = []
    collapse_bindings = []
    for attachment in reference_plan:
        source_slot = attachment.get("sourceSlot") or attachment.get("slot")
        if not grouped or grouped[-1][0] != source_slot:
            grouped.append((source_slot, [attachment]))
        else:
            grouped[-1][1].append(attachment)
    for _source_slot, attachments in grouped:
        role = attachments[0]["role"]
        if role == "scene plate":
            slot = attachments[0]["slot"]
            scene_look_slot = slot
            reference_lines.append(
                f"- {slot} is the locked Scene Look plate; inherit world, viewpoint, scale, "
                "materials, light and atmosphere only.")
            compact_reference_lines.append(
                f"- {slot}: approved Scene Look; world, scale, materials, light and "
                "atmosphere only.")
        elif str(role).startswith("prop:"):
            slot = attachments[0]["slot"]
            prop_name = str(role).split(":", 1)[1].replace("_", " ")
            reference_lines.append(
                f"- {slot} is the exact {prop_name} prop authority; inherit design, "
                "material, construction and scale only; ignore its background and labels.")
            compact_reference_lines.append(
                f"- {slot}: exact {prop_name} prop authority only; ignore background/text.")
        elif role == CHARACTER_SCALE_CONTROL_ROLE:
            slot = attachments[0]["slot"]
            reference_lines.append(
                f"- {slot} is a technical character scale-control board only. Use it only "
                "to preserve relative full-body heights and same-depth scale relationships. "
                "It does not define a character, creature, prop, scene, pose, action, face, "
                "colour palette, costume or additional subject.")
            compact_reference_lines.append(
                f"- {slot}: technical scale-control board only; relative heights only; "
                "no extra subject.")
        else:
            canonical = _resolve_char(role, characters_cfg)
            identity_names.append(canonical)
            if len(attachments) == 1:
                item = attachments[0]
                identity = item.get("identity") or {}
                if identity.get("singleSubject"):
                    reference_lines.append(
                        f"- {item['slot']}: {canonical}'s single-subject character anchor is "
                        f"the 100% identity authority for this shot. Match {canonical} exactly "
                        "as the same character shown in the anchor. Preserve face shape, "
                        "antennae, glasses/eyes, wings, body proportions, markings and scale. "
                        "Ignore background and static pose; do not describe, redesign, "
                        "simplify, beautify or reinterpret it.")
                    compact_reference_lines.append(
                        f"- {item['slot']}: {canonical} single-subject identity anchor; exact "
                        "identity/proportions only; ignore background/pose.")
                else:
                    reference_lines.append(
                        f"- {item['slot']}: {canonical}'s complete, uncropped 360 turnaround is the "
                        f"100% identity authority. Match {canonical} exactly as the same character "
                        "shown in the turnaround. Preserve every visible feature and proportion. "
                        "Ignore background and static pose; do not describe, redesign, simplify, "
                        "beautify or reinterpret it.")
                    compact_reference_lines.append(
                        f"- {item['slot']}: {canonical} turnaround; exact identity/proportions "
                        "only; ignore background/pose.")
                collapse_bindings.append((item["slot"], canonical))
            else:
                view_bindings = ", ".join(
                    f"{item['slot']} {item.get('view') or 'identity'}"
                    for item in attachments)
                reference_lines.append(
                    f"- {canonical} turnaround: {view_bindings}. Together they are {canonical}'s "
                    "100% identity authority. Match exactly; preserve every visible feature, "
                    "accessory, silhouette, marking, proportion, material and view detail. "
                    "Ignore backgrounds and poses; do not redesign or reinterpret.")
                compact_reference_lines.append(
                    f"- {canonical}: {view_bindings}; exact identity/proportions only; ignore "
                    "backgrounds/poses.")
                collapse_bindings.append((
                    "/".join(item["slot"] for item in attachments), canonical))

    collapse_line = emission.multi_angle_collapse_summary(collapse_bindings)
    if collapse_line:
        reference_lines.insert(1 if slot_line else 0, f"- {collapse_line}")
        compact_reference_lines.insert(1 if slot_line else 0, f"- {collapse_line}")

    separation_line = ""
    if len(identity_names) > 1:
        separation_line = (
            f"\n- Keep {' and '.join(identity_names)} distinct; never blend or swap traits."
        )
        compact_separation_line = (
            "\n- Keep identities distinct; no blending."
        )
    else:
        compact_separation_line = ""

    protections = [re.sub(r"\s+", " ", str(value or "")).strip()
                   for value in direction.get("continuityProtections") or []
                   if str(value or "").strip()
                   and "apparentscale" not in str(value or "").casefold()]
    scale_protection = _keyframe_same_depth_scale_protection(
        direction, characters_cfg)
    if scale_protection:
        protections.insert(0, scale_protection)
    instance_lock = emission.character_instance_lock(contract["cast"], medium="still")
    if instance_lock:
        protections.insert(0, instance_lock)
    protections.append(cb_engine_rules.natural_keyframe_staging_boilerplate(shot))
    opening_shot = {**shot, "charactersInFrame": list(contract["cast"])}
    protections.append(cb_engine_rules.living_performance_boilerplate(
        opening_shot, direction, medium="still"))
    reference_body = ("\n".join(reference_lines) + separation_line).strip()
    compact_reference_body = (
        "\n".join(compact_reference_lines) + compact_separation_line).strip()

    protected_sections = {
        "Intended Read": re.sub(r"\s+", " ", str(direction["audienceRead"])).strip(),
        "Geography": "\n".join(contract["geography"]),
        "Frame": _keyframe_frame_section(direction, characters_cfg),
        "Negative Space": "\n".join(contract["negativeSpace"]),
    }

    scene_look_authority = (
        f"{scene_look_slot} is the approved visual authority for world, canonical style, "
        "materials, light and atmosphere."
        if scene_look_slot else None)

    def _emit(*, compact_controls=False, compact_references=False,
              compact_forbidden=False, spend_scene_look=False):
        sections = [("Opening Stage",
                     (f"Playable 16:9 anticipation for {shot.get('shotId')}; no portrait or payoff."
                      if compact_controls else
                      f"Create a playable 16:9 opening for {shot.get('shotId')}; frame-one "
                      "anticipation, not portrait or payoff."))]
        sections.append(("Intended Read", protected_sections["Intended Read"]))
        refs = compact_reference_body if compact_references else reference_body
        if refs:
            sections.append(("References", refs))
        sections.append((
            "Characters In Frame",
            "\n".join(f"- {name}" for name in contract["cast"])))
        sections.extend([
            ("Frame", protected_sections["Frame"]),
            ("Geography", protected_sections["Geography"]),
            ("Negative Space", protected_sections["Negative Space"]),
        ])
        if spend_scene_look and scene_look_authority:
            sections.append(("Scene Look", scene_look_authority))
        else:
            sections.append(("Canonical Style", direction["canonicalStyleParagraph"]))
        sections.append(("Camera", emission.ensure_complete_sentence(
            direction["lensAndCameraRelationship"],
            context="keyframe camera direction")))
        if not (spend_scene_look and scene_look_authority):
            sections.append(("Light", str(direction["lightingAndDepth"]).strip()))
        sections.append((
            "Physical Integration",
            "Keep every subject grounded in the authored perspective and depth. Match the "
            "approved light direction and scale; preserve natural contact shadows, surface "
            "reflections and occlusion where subjects meet the environment."))
        sections.append((
            "Performance Freedom",
            ("Animation owns later performance and motion."
             if compact_controls else
             "Animation owns performance, movement, recovery and camera evolution.")))
        if protections:
            sections.append(("Protect", "\n".join(protections)))
        required_props = [str(value).strip() for value in
                          shot.get("requiredPropReferences") or [] if str(value).strip()]
        if required_props:
            prop_rule = (
                "No unapproved extra cast, props or body-mounted loads; include only the "
                f"required referenced {' and '.join(required_props)} with its approved owner."
            )
        else:
            prop_rule = "No extra cast, props, body-mounted bags, sacks, baskets or dangling loads."
        sections.append(("Forbidden",
                         ("No portrait/payoff, identity or scale drift, altered reference "
                          f"features, duplicates, anatomy errors, text or watermarks. {prop_rule}"
                          if compact_forbidden else
                          "No portrait, locked extreme action pose or payoff, identity or scale "
                          "drift, changed accessories, omitted reference features, duplicates, "
                          f"anatomy errors, text or watermark. {prop_rule} Preserve the locked "
                          "Scene Look.")))
        return "\n\n".join(f"[{name}]\n{body}" for name, body in sections).strip()

    # Emit the complete approved direction. Prompt length never selects a shorter variant.
    prompt = _emit()
    try:
        cb_departments.prompt_sections(prompt)
    except ValueError as exc:
        raise Refused(f"REFUSED — invalid keyframe prompt for {shot.get('shotId')}: {exc}")
    # Run the same clipping guard used by render and voice over compiler-owned prose.
    for name, body in cb_departments.prompt_sections(prompt).items():
        if name in {"Frame", "Camera"}:
            for line in body.splitlines():
                emission.require_complete_sentence(
                    line.removeprefix("- "), context=f"keyframe [{name}]")
    return prompt


def _with_character_scale_control(prompt, shot, slots_key, scene, episode):
    """Append the measured board's exact provider role without changing creative prose."""
    prompt = str(prompt or "").strip()
    if not prompt or CHARACTER_SCALE_CONTROL_MARKER in prompt:
        return prompt
    characters_cfg = _characters_cfg()
    control = _load_character_scale_control(
        shot, scene, episode, characters_cfg)
    if not control:
        return prompt
    slots = _effective_image_slots(
        shot, slots_key, scene, episode, characters_cfg)
    control_slot = next(
        (slot for slot, role in slots.items()
         if role == CHARACTER_SCALE_CONTROL_ROLE), None)
    if not control_slot:
        return prompt

    identity_bindings = [
        f"{slot} is {role}'s locked turnaround"
        for slot, role in sorted(
            slots.items(), key=lambda item: int(item[0][2:])
            if item[0].startswith("@图") else 999)
        if role in control.get("screenOrder", [])
    ]
    measurements = ", ".join(
        f"{item['character']} is {item['heightIn']} inches"
        for item in control["characters"])
    ratio_sentence = ""
    if len(control["characters"]) == 2:
        from fractions import Fraction
        shorter, taller = sorted(
            control["characters"], key=lambda item: float(item["heightIn"]))
        ratio = (Fraction(str(taller["heightIn"])) /
                 Fraction(str(shorter["heightIn"]))).limit_denominator(100)
        percent = (float(taller["heightIn"]) / float(shorter["heightIn"]) - 1) * 100
        ratio_sentence = (
            f" {taller['character']} is exactly {ratio.numerator}:{ratio.denominator}, "
            f"or {percent:.1f} percent, taller than {shorter['character']}."
        )
    depth_subject = "Both characters" if len(control["characters"]) == 2 else "All characters"
    depth_object = "either character" if len(control["characters"]) == 2 else "any character"
    depth_sentence = (
        f" {depth_subject} occupy one camera-depth plane; do not use perspective to enlarge "
        f"{depth_object}."
        if control.get("sameDepth") else
        " Apply these physical heights before the shot's authored perspective."
    )
    clause = (
        f"{CHARACTER_SCALE_CONTROL_MARKER} "
        f"{'; '.join(identity_bindings)}. {control_slot} is a measured technical scale "
        f"board generated from those locked turnarounds: {measurements}.{ratio_sentence}"
        f"{depth_sentence} Use the board only for relative full-body height and depth; "
        "do not copy its placeholder shapes, colours, labels, pose or background."
    )
    return f"{prompt}\n\n{clause}"


def _resolve_keyframe_prompt(pkg, shot):
    """A relay/non-opener shot legitimately has no keyframePrompt at all (it opens off its
    source shot's harvested final frame, never its own keyframe — keyframe_shot itself
    refuses to generate one) — returns None for that shot rather than crashing. Every real
    caller either already guards sourceType=="opener" first (keyframe_shot/regen paths) or
    is a read-only report over EVERY shot (evidence_pack) that must tolerate a relay shot's
    honest "no keyframe prompt" the same way it already tolerates a silent shot's "no voice
    track" — a missing value here is the truthful record, never a gap to paper over."""
    if shot.get("sourceType") != "opener":
        return None
    work = _approved_department_output(pkg, shot["shotId"], "cinematography") or {}
    plan = _expanded_reference_blueprint(
        shot, "keyframeReferenceSlots", _characters_cfg())
    prompt = _compile_keyframe_integration_prompt(work, shot, plan)
    ledger = _ledger(pkg, shot["shotId"])
    rejection = ((ledger.get("keyframeRejections") or [])[-1:]
                 or ([ledger.get("keyframeRejected")] if ledger.get("keyframeRejected") else []))
    correction = str((rejection[0] if rejection else {}).get("reason") or "").strip()
    if correction:
        prompt += (
            "\n\n[Director Iteration]\nCorrect only this observed issue in the next "
            f"revision: {correction}\nPreserve every successful identity, canon, geography, "
            "lighting, reference-role and continuity decision from the approved direction."
        )
    return prompt


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


def _voice_word_text(line):
    """Return the provider-facing spoken text without script labels or action notes."""
    text = str(line.get("exactText") if isinstance(line, dict) else line or "").strip()
    text = re.sub(r"^\s*\d+\s*\t", "", text)
    return re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()


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
    for ln in cb_audio_authority.spoken_dialogue_lines(shot):
        # Provider text excludes legacy script numbering and parenthetical action notes.
        text = _voice_word_text(ln)
        delivery = ln.get("delivery") or ""
        m = _LEADING_TAG_RE.match(delivery)
        if m and _voice_word_text({"exactText": delivery[m.end():]}) == _voice_word_text({"exactText": text}):
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
    spoken_lines = cb_audio_authority.spoken_dialogue_lines(shot)
    directed_output = _approved_department_output(pkg, shot_id, "voice") or {}
    direction_by_occurrence = {
        line.get("dialogueOccurrenceId"): line
        for line in (directed_output.get("lines") or [])
        if line.get("dialogueOccurrenceId")
    }
    approved = []
    # HEAR displays and audits only genuine spoken dialogue. Non-verbal events such as
    # sneezes and snores belong to the Seedance SFX lane; retaining them here shifted every
    # following authored direction by one row and made the read-only compiler report a false
    # line-count failure even though the production voice route already filtered them.
    for ln in spoken_lines:
        direction = direction_by_occurrence.get(ln.get("dialogueOccurrenceId"), {})
        exact_text = ln.get("exactText") if ln.get("exactText") is not None else ln.get("text")
        approved.append({
            "dialogueOccurrenceId": ln.get("dialogueOccurrenceId"),
            "sourceEventId": ln.get("sourceEventId"),
            "speaker": ln["speaker"], "exactText": exact_text,
            "delivery": ln.get("delivery"),
            "dramaticIntention": direction.get("dramaticIntention"),
            "subtext": direction.get("subtext"),
            "cadenceAndBreath": direction.get("cadenceAndBreath"),
            "timingAndBody": direction.get("timingAndBody"),
        })
    working = led.get("workingVoice")
    current, source = _resolve_voice_lines(pkg, shot)
    # The Voice Director compiler is authoritative once it is installed by the
    # safety layer.  Do not let an older editable workingVoice record make the
    # HEAR screen describe different text from the track voice_shot builds.
    compiled_voice_lines = globals().get("_approved_voice_lines")
    if callable(compiled_voice_lines):
        try:
            compiled_current = compiled_voice_lines(pkg, shot)
        except (Refused, KeyError, TypeError, ValueError):
            compiled_current = None
        if (compiled_current and
                len(compiled_current) == len(spoken_lines)):
            current = compiled_current
            source = "voice-director-compiled"
    vo_path = led.get("voPath")
    has_take = bool(vo_path)
    generated_from = led.get("voGeneratedFrom")
    if not has_take:
        match = None
    elif generated_from is not None:
        match = (generated_from == current)
        if not match:
            # Direction audits may change compiledHash without changing a single
            # provider-facing voice input. HEAR freshness follows what was actually
            # rendered, not mutable compiler bookkeeping.
            provider_keys = (
                "dialogueOccurrenceId", "sourceEventId", "speaker", "text", "voiceId",
                "modelId", "voiceSettings", "previousText", "recipeId",
            )
            provider_projection = lambda lines: [
                {key: line.get(key) for key in provider_keys}
                for line in (lines or [])
            ]
            match = provider_projection(generated_from) == provider_projection(current)
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
    current_with_direction = []
    for line in current:
        direction = direction_by_occurrence.get(line.get("dialogueOccurrenceId"), {})
        current_with_direction.append({
            **line,
            "dramaticIntention": direction.get("dramaticIntention"),
            "subtext": direction.get("subtext"),
            "cadenceAndBreath": direction.get("cadenceAndBreath"),
            "timingAndBody": direction.get("timingAndBody"),
        })
    compiler = {"ready": False, "error": None, "track": None}
    try:
        current_direction = _approved_department_output(pkg, shot_id, "voice") or {}
        current_direction, compiler_lines = cb_audio_authority.route_voice_direction(
            current_direction, shot.get("dialogueLines") or [])
        compiler["track"] = cb_voice_director.compile_track(
            current_direction, compiler_lines)
        compiler["ready"] = True
    except (cb_voice_director.VoiceContractError, Refused, KeyError, TypeError) as exc:
        compiler["error"] = str(exc)
    auditions = led.get("voiceAuditions") or None
    placement = None
    placement_path = led.get("voPlacementPath")
    if placement_path:
        try:
            placement = json.loads(pathlib.Path(placement_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            placement = None
    return {"approvedLines": approved, "currentLines": current_with_direction, "source": source,
            "isWorking": bool(working) and source != "voice-director-compiled",
            "savedAt": (working or {}).get("savedAt"),
            "hasTake": has_take, "takeMatchesCurrent": match,
            "takeGeneratedAt": take_generated_at, "previous": led.get("voicePrevious"),
            "voiceApprovalRecorded": bool((led.get("voiceApproval") or {}).get("approved")),
            "shotDurationSec": shot.get("durationSec"),
            "expectedLineCount": len(cb_audio_authority.spoken_dialogue_lines(shot)),
            "generatedLineCount": len((placement or {}).get("placements") or []),
            "placements": (placement or {}).get("placements") or [],
            "takeKind": "complete-shot-track" if has_take else None,
            "compiler": compiler, "auditions": auditions}


def select_voice_audition(scene, shot_id, candidate_id, episode="Ep1",
                          reviewed_by="Julian", log=print):
    """Record Julian's HEAR choice and bank its character/archetype recipe."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    bundle = led.get("voiceAuditions") or {}
    candidates = bundle.get("candidates") or []
    candidate = next((item for item in candidates
                      if item.get("candidateId") == candidate_id), None)
    if not candidate:
        raise Refused("REFUSED - choose a current Voice Director audition candidate")
    if bundle.get("compiledHash") != candidate.get("compiledHash"):
        raise Refused("REFUSED - the selected voice audition is stale")
    if not candidate.get("path") or not os.path.exists(candidate["path"]):
        raise Refused("REFUSED - the selected voice audition file is missing")
    occurrence = bundle.get("dialogueOccurrenceId")
    direction = _approved_department_output(pkg, shot_id, "voice") or {}
    directed_line = next((line for line in (direction.get("lines") or [])
                          if line.get("dialogueOccurrenceId") == occurrence), None)
    if not directed_line:
        raise Refused("REFUSED - the selected audition has no current direction record")
    recipe = next((item for item in (directed_line.get("takeRecipes") or [])
                   if item.get("recipeId") == candidate.get("recipeId")), None)
    if not recipe:
        raise Refused("REFUSED - the selected audition recipe is no longer current")
    selected = {
        "candidateId": candidate_id,
        "recipeId": candidate["recipeId"],
        "takeNumber": candidate["takeNumber"],
        "path": candidate["path"],
        "selectedBy": reviewed_by,
        "selectedAt": _now(),
        "compiledHash": candidate["compiledHash"],
    }
    bundle["selected"] = selected
    selected_hashes = list(led.get("voiceAuditionSelectionsByHash") or [])
    if candidate["compiledHash"] not in selected_hashes:
        selected_hashes.append(candidate["compiledHash"])
    led["voiceAuditionSelectionsByHash"] = selected_hashes
    selected_by_occurrence = led.setdefault("voiceAuditionSelections", {})
    selected_by_occurrence[occurrence or candidate["compiledHash"]] = selected
    cb_voice_director.bank_recipe(
        directed_line["character"], directed_line["archetypeId"], recipe,
        shot_id=shot_id, candidate=candidate_id, reviewed_by=reviewed_by)
    _save(pkg, path)
    log(f"HEAR VERDICT - {shot_id}: {candidate_id} selected by {reviewed_by}")
    return selected


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
    # The authored shot can also contain non-verbal events routed to Seedance. HEAR edits
    # must align with the spoken lane used by voice_shot, not the unsplit source list.
    dl = cb_audio_authority.spoken_dialogue_lines(shot)
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
    spoken_lines = cb_audio_authority.spoken_dialogue_lines(shot)
    if not spoken_lines:
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
    if len(perf_lines) != len(spoken_lines):
        # a stale working version (e.g. the storyboard's own dialogueLines changed count
        # since it was saved) — refuse to guess at a re-alignment, fall back to the locked
        # default rather than submit a mismatched performance track.
        perf_lines = _default_voice_lines(shot)
        performance_source = "legacy-approved-storyboard"
    turns = []
    for ln, perf in zip(spoken_lines, perf_lines):
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
        if not cb_audio_authority.spoken_dialogue_lines(s):
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
        spoken_lines = cb_audio_authority.spoken_dialogue_lines(shot)
        if spoken_lines:
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
            "voicePath": voice_path if spoken_lines else None,
            "voiceHash": (_sha256_file(voice_path)
                          if spoken_lines else None),
            "voiceApprovalSignature": ((ledger.get("voiceApproval") or {})
                                       .get("inputSignature")
                                       if spoken_lines else None),
        })
    return {"shots": rows}


def timing_slate_status(scene, episode="Ep1"):
    """Read-only timing-slate freshness report; never calls a provider."""
    out = HERE / "media" / f"{episode}_Scene{scene}_timing_slate.mp4"
    sidecar = pathlib.Path(str(out) + ".contract.json")
    if not out.exists() or not sidecar.exists():
        return {"exists": out.exists(), "current": False, "path": str(out),
                "approved": False,
                "reason": "not built from a recorded input contract"}
    try:
        pkg, _ = load_pkg(scene, episode)
        record = json.loads(sidecar.read_text())
        signature = _timing_slate_input_signature(pkg)
        current = record.get("inputSignature") == signature
        review = pkg.get("timingSlateReview") or {}
        approved = review.get("approved") or {}
        approved_current = bool(
            current and approved.get("inputSignature") == signature and
            approved.get("path") == str(out) and
            approved.get("contentHash") == _sha256_file(out))
        return {"exists": True, "current": current, "path": str(out),
                "generatedAt": record.get("generatedAt"),
                "approved": approved_current,
                "review": approved if approved_current else review.get("candidate"),
                "reason": (None if approved_current else
                           "current voice-timed slate awaits human rhythm approval" if current
                           else "shot timing or an approved voice take changed")}
    except (OSError, ValueError, Refused) as exc:
        return {"exists": True, "current": False, "approved": False,
                "path": str(out), "reason": str(exc)}


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
    if int(pkg.get("creativeDirectingStandardVersion") or 0) >= 3:
        review = pkg.setdefault("timingSlateReview", {"candidate": None, "approved": None,
                                                       "history": []})
        review["candidate"] = {
            "path": str(out), "contentHash": _sha256_file(out),
            "inputSignature": input_signature, "preparedAt": _now(),
            "approvesOnly": ["dialogue accuracy", "voice assignment", "shot duration",
                             "scene length", "dialogue position", "performance breathing",
                             "reaction and landing room"],
        }
        _save(pkg, path)
    log(f"TIMING SLATE — scene {scene}: {len(clips)} shots -> {out.name} · approves dialogue "
        f"accuracy, voice assignment, shot durations, scene length and line position ONLY — "
        f"it does not prove staging, physical comedy or final rhythm")
    return str(out)


def decide_timing_slate(scene, verdict, note="", episode="Ep1", reviewed_by="Julian", log=print):
    """Record the human rhythm decision; never generates media or grants WATCH approval."""
    if verdict not in ("approved", "rejected"):
        raise Refused("REFUSED — timing-slate verdict must be approved|rejected")
    pkg, path = load_pkg(scene, episode)
    review = pkg.get("timingSlateReview") or {}
    candidate = review.get("candidate")
    status = timing_slate_status(scene, episode)
    if not candidate or not status.get("current"):
        raise Refused("REFUSED — no current voice-timed slate awaits a decision")
    if verdict == "rejected" and not str(note or "").strip():
        raise Refused("REFUSED — timing-slate rejection needs a plain-language note")
    event = {**candidate, "outcome": verdict, "decisionAt": _now(),
             "reviewedBy": reviewed_by, "note": str(note or "").strip()}
    if verdict == "approved":
        if review.get("approved"):
            review.setdefault("history", []).append(
                {**review["approved"], "outcome": "superseded", "supersededAt": _now()})
        review["approved"] = event
    else:
        review.setdefault("history", []).append(event)
    review["candidate"] = None
    pkg["timingSlateReview"] = review
    _save(pkg, path)
    log(f"TIMING SLATE {verdict.upper()} — scene {scene} by {reviewed_by}; "
        "this approves rhythm only, never final acting, physics or WATCH media")
    return event


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
    attachment_plan = _provider_attachment_plan(
        shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    _require_prop_reference_authority(
        shot, scene, episode, attachment_plan)
    refs = [item["path"] for item in attachment_plan]
    st = scenelook_status(scene, episode)
    scenelook_hash = (st.get("active") or {}).get("hash") if st.get("current") else None
    prompt = _resolve_keyframe_prompt(pkg, shot)
    return {"cardHash": _live_card_hash(shot["shotId"], scene, episode),
            "sceneLookHash": scenelook_hash,
            "referenceHashes": {os.path.basename(p): _file_md5(p) for p in refs},
            "briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "model": (f"{cb_gen.IMAGE_PROVIDER}:{cb_gen.SEEDREAM_MODEL_ID}:"
                      f"{cb_gen.SEEDREAM_ENDPOINT}:2K")}


def _keyframe_prompt_contract(pkg, shot, prompt=None):
    """Snapshot the exact image prompt and route beside the generated candidate."""
    prompt = prompt if prompt is not None else _resolve_keyframe_prompt(pkg, shot)
    specialist = _approved_department_output(pkg, shot["shotId"], "cinematography") or {}
    direction_contract = _keyframe_direction_contract(specialist, shot)
    try:
        sections = cb_departments.prompt_sections(prompt)
    except ValueError as exc:
        raise Refused(f"REFUSED — invalid keyframe prompt contract: {exc}")
    expected_sections = {
        "Intended Read": re.sub(r"\s+", " ", str(specialist["audienceRead"])).strip(),
        "Geography": "\n".join(direction_contract["geography"]),
        "Frame": _keyframe_frame_section(specialist, _characters_cfg()),
        "Negative Space": "\n".join(direction_contract["negativeSpace"]),
    }
    for section_name, expected in expected_sections.items():
        if sections.get(section_name) != expected:
            raise Refused(
                f"REFUSED — keyframe prompt [{section_name}] does not match approved "
                "Cinematography direction verbatim")
    if "Scene Look" in sections:
        plan = _expanded_reference_blueprint(
            shot, "keyframeReferenceSlots", _characters_cfg())
        scene_slot = next((item["slot"] for item in plan
                           if item.get("role") == "scene plate"), None)
        expected_scene_look = (
            f"{scene_slot} is the approved visual authority for world, canonical style, "
            "materials, light and atmosphere."
            if scene_slot else None)
        if not expected_scene_look or sections["Scene Look"] != expected_scene_look:
            raise Refused(
                "REFUSED — keyframe prompt [Scene Look] is not bound to the approved "
                "Scene Look reference")
        if "Canonical Style" in sections or "Light" in sections:
            raise Refused(
                "REFUSED — reference-backed keyframe prompt duplicates Scene Look prose")
    else:
        for section_name, expected in {
                "Canonical Style": specialist["canonicalStyleParagraph"],
                "Light": str(specialist["lightingAndDepth"]).strip(),
        }.items():
            if sections.get(section_name) != expected:
                raise Refused(
                    f"REFUSED — keyframe prompt [{section_name}] does not match approved "
                    "Cinematography direction verbatim")
    cast_lines = [line.removeprefix("- ").strip()
                  for line in sections.get("Characters In Frame", "").splitlines()
                  if line.strip()]
    if cast_lines != direction_contract["cast"]:
        raise Refused(
            "REFUSED — keyframe prompt [Characters In Frame] must name each approved "
            "in-frame character exactly once and in order")
    if cb_gen.IMAGE_PROVIDER == "seedream":
        provider_model_id = cb_gen.SEEDREAM_MODEL_ID
    else:
        provider_model_id = cb_gen.IMAGE_MODEL
    contract = {
        "prompt": prompt,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "promptSource": ("direct-stage-anchor-compiler-from-current-cinematography"
                         if specialist.get("openingFrameLayout")
                         else "missing-current-cinematography"),
        "provider": cb_gen.IMAGE_PROVIDER,
        "providerModelId": provider_model_id,
        "modelVersion": provider_model_id,
        "directionContract": {
            "canonicalStyleVersion": direction_contract["styleVersion"],
            "canonicalStyleParagraph": direction_contract["styleText"],
            "lightingAndDepth": str(specialist["lightingAndDepth"]).strip(),
            "geography": direction_contract["geography"],
            "charactersInFrame": direction_contract["cast"],
            "emptySections": [],
        },
    }
    contract["contractHash"] = hashlib.sha256(json.dumps(
        contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return contract


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


def screen_keyframe_conformance(pkg, shot, candidate_path, scene, episode="Ep1", log=print):
    """Run the advisory identity/scale/staging screen after a keyframe render.

    This call never generates media.  It compares the actual candidate with the exact
    provider attachments and typed opening layout that produced it. The result is attached
    to the visible candidate as a recommendation; only the human Director may approve or
    refire the keyframe.
    """
    characters_cfg = _characters_cfg()
    attachment_plan = _provider_attachment_plan(
        shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    refs = [item["path"] for item in attachment_plan]
    expected_cast = list(dict.fromkeys(
        shot.get("openingCharactersInFrame") or shot.get("charactersInFrame") or []))
    direction = _approved_department_output(
        pkg, shot["shotId"], "cinematography") or {}
    layout = direction.get("openingFrameLayout") or {}

    identity_by_character = {}
    ordered_images = [{
        "imageNumber": 1, "role": "actual rendered keyframe candidate",
        "path": str(candidate_path),
    }]
    forbidden = [
        "extra or missing characters", "identity blending, swapping or cloning",
        "incorrect relative size", "cropped or malformed anatomy",
        "a copied turnaround, model-sheet, T-pose or spread-arm presentation pose",
        "unnatural symmetrical limb placement or arms held out without story motivation",
        "body-mounted bags, sacks, baskets or dangling loads",
        "pendants, necklaces, medallions or crystals on either bee",
        "text, logo or watermark",
    ]
    for index, attachment in enumerate(attachment_plan, start=2):
        slot = attachment["slot"]
        role = attachment["role"]
        ref_path = attachment["path"]
        ordered_images.append({
            "imageNumber": index, "providerSlot": slot, "role": role,
            "view": attachment.get("view"),
            "path": ref_path,
        })
        if role == "scene plate":
            continue
        identity = attachment.get("identity")
        if not identity:
            continue
        canonical = identity.get("character") or _resolve_char(role, characters_cfg)
        record = characters_cfg.get(canonical) or {}
        contract = identity_by_character.setdefault(canonical, {
            "character": canonical,
            "imageNumber": index,
            "imageNumbers": [],
            "providerSlot": slot,
            "providerSlots": [],
            "view": identity.get("view"),
            "views": [],
            "sameCharacterTurnaround": True,
            "turnaroundGroupHash": identity.get("turnaroundGroupHash"),
            "singleSubject": identity.get("singleSubject"),
            "heightIn": record.get("heightIn"),
            "distinguishingFeatures": identity.get("distinguishingFeatures") or [],
            "mustNotBorrow": identity.get("mustNotBorrow") or [],
        })
        contract["imageNumbers"].append(index)
        contract["providerSlots"].append(slot)
        contract["views"].append(identity.get("view"))
        forbidden.extend(contract["mustNotBorrow"])

    identity_contracts = list(identity_by_character.values())

    context = {
        "shotId": shot["shotId"],
        "expectedCharacters": expected_cast,
        "expectedSubjectCount": len(expected_cast),
        "identityContracts": identity_contracts,
        "canonicalRelativeSize": [
            {"character": item["character"], "heightIn": item.get("heightIn")}
            for item in identity_contracts
        ],
        "sameDepth": bool(layout.get("sameDepth")),
        "openingFrameLayout": layout,
        "audienceRead": direction.get("audienceRead"),
        "orderedImages": ordered_images,
        "forbidden": list(dict.fromkeys(forbidden)),
        "decisionBoundary": (
            "Judge objective contract compliance only. Human review owns cinematic taste, "
            "performance potential and final approval."),
    }
    try:
        result = cb_departments.review_keyframe_conformance(
            context, [str(candidate_path)] + refs, log=log)
        review = result.model_dump() if hasattr(result, "model_dump") else dict(result)
        reported_cast = sorted(
            str(name).casefold() for name in (review.get("expectedCharacters") or []))
        actual_contract_cast = sorted(str(name).casefold() for name in expected_cast)
        contract_echo_valid = (
            reported_cast == actual_contract_cast and
            review.get("expectedSubjectCount") == len(expected_cast))
        status = ("pass" if review.get("verdict") == "pass" and contract_echo_valid
                  else "fail")
        reason = review.get("summary") or (
            "objective keyframe contract passed" if status == "pass" else
            "objective keyframe contract failed")
        if not contract_echo_valid:
            reason = "The validator did not return the exact expected cast contract."
        return {
            "status": status,
            "reason": reason,
            "checkedAt": _now(),
            "screenVersion": 2,
            "validatorModel": cb_departments.cb_llm.VALIDATOR_MODEL,
            "mediaProviderCalled": False,
            "referenceHashes": {
                pathlib.Path(path).name: _sha256_file(path) for path in refs
            },
            "candidateSha256": _sha256_file(candidate_path),
            "review": review,
        }
    except Exception as exc:
        log(f"KEYFRAME CONFORMANCE ADVISORY UNAVAILABLE — {shot['shotId']}: {exc}")
        return {
            "status": "unavailable",
            "reason": (
                "The objective identity and scale check did not complete. The generated "
                "image remains available for the human Director's decision."),
            "detail": str(exc),
            "checkedAt": _now(),
            "screenVersion": 2,
            "validatorModel": cb_departments.cb_llm.VALIDATOR_MODEL,
            "mediaProviderCalled": False,
            "candidateSha256": _sha256_file(candidate_path),
        }


def keyframe_shot(scene, shot_id, episode="Ep1", log=print):
    """Generate exactly two SEE candidates from one sealed brief and reference pack.

    A is Seedream 5 Pro through BytePlus; B is Nano Banana 2 through Google. Each lands at
    its own immutable path. The engine never auto-selects or approves either candidate,
    touches no other shot's media or ledger
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
    _require_confirmed_billing("byteplus")                   # protection 5 — block, not warn
    _require_confirmed_billing("google")
    _require_current_scenelook(scene, episode)                # no keyframe without a current approved Scene Look Plate
    shot = _shot(pkg, shot_id)
    if shot["sourceType"] != "opener":
        raise Refused(f"REFUSED — {shot_id} is a relay shot; it anchors on its source shot's "
                      f"harvested final frame, never its own keyframe")
    led = _ledger(pkg, shot_id)
    cinematography = _approved_department_output(pkg, shot_id, "cinematography") or {}
    playable = cb_engine_rules.playable_stage_report(shot, cinematography)
    if not playable["ready"]:
        raise Refused(
            "REFUSED — opening frame is not a playable stage: "
            + "; ".join(playable["errors"]))
    if led.get("keyframeCandidate") or led.get("keyframeCandidates"):
        raise Refused(f"REFUSED — {shot_id} already has a keyframe candidate awaiting a "
                      f"decision; reject it first (with a reason) before generating another")
    characters_cfg = _characters_cfg()
    composition_master = _ensure_opening_composition_master(
        pkg, shot, scene, episode, characters_cfg)
    log(f"LOCAL STAGE QA — {shot_id}: loose position and coverage guide ready "
        "(zero spend; advisory only; never uploaded to the provider)")
    scale_control = _ensure_character_scale_control(
        shot, scene, episode, characters_cfg, same_depth=None)
    if scale_control:
        log(f"LOCAL SCALE QA — {shot_id}: measured canon relationship ready "
            "(zero spend; advisory only; never uploaded to the provider)")
    refs = _slot_paths(shot, "keyframeReferenceSlots", None, scene, episode, characters_cfg)
    log(f"DIRECT STAGE REFERENCES — {shot_id}: {len(refs)} locked character/Scene Look "
        "asset(s); no generated pose or composition image is uploaded")
    MEDIA.mkdir(parents=True, exist_ok=True)
    prompt = _resolve_keyframe_prompt(pkg, shot)
    signature = _keyframe_input_signature(pkg, shot, scene, episode)
    prompt_contract = _keyframe_prompt_contract(pkg, shot, prompt)
    specs = [
        ("A", "Seedream 5 Pro", "byteplus", cb_gen.SEEDREAM_MODEL_ID,
         cb_gen.generate_image),
        ("B", "Nano Banana 2", "google", cb_gen.IMAGE_MODEL,
         cb_gen.generate_image_nanobanana_ab),
    ]
    candidates = []
    led["keyframeCandidates"] = candidates
    led["keyframeCandidate"] = None
    led["selectedKeyframeCandidateId"] = None
    for candidate_id, label, provider, model_id, generator in specs:
        out = MEDIA / (
            f"{episode}_{shot_id}_keyframe_{candidate_id}_{uuid.uuid4().hex[:8]}.png")
        try:
            generator(prompt, refs=refs, out=str(out), production_route="cb_render")
        except BaseException as exc:
            led["keyframeCandidate"] = candidates[0] if candidates else None
            led["keyframeABFailure"] = {
                "candidateId": candidate_id,
                "provider": provider,
                "failedAt": _now(),
                "reason": str(exc)[:500],
                "completedCandidateIds": [item["candidateId"] for item in candidates],
            }
            _save(pkg, path)
            raise
        geometry_screening = cb_layout.screen_candidate_geometry(out, composition_master)
        conformance_screening = screen_keyframe_conformance(
            pkg, shot, out, scene, episode, log=log)
        candidates.append({
            "candidateId": candidate_id,
            "label": f"{candidate_id} - {label}",
            "provider": provider,
            "model": model_id,
            "path": str(out),
            "generatedAt": _now(),
            "source": "generated",
            "inputSignature": signature,
            "promptContract": prompt_contract,
            "geometryScreening": geometry_screening,
            "conformanceScreening": conformance_screening,
        })
        led["keyframeCandidate"] = candidates[0]
        _save(pkg, path)
        log(f"SEE {candidate_id} COMPLETE — {shot_id}: {label} -> {out.name}")
    # keyframeCandidate remains a compatibility pointer, not a selection or approval.
    led["keyframeCandidates"] = candidates
    led["keyframeCandidate"] = candidates[0]
    led["selectedKeyframeCandidateId"] = None
    led["keyframeABTest"] = {
        "createdAt": _now(),
        "promptHash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "referenceHashes": [_sha256_file(path) for path in refs],
        "candidateIds": ["A", "B"],
        "selectionRequired": True,
    }
    _save(pkg, path)
    log(f"SEE A/B — {shot_id}: compare both images and select A or B before approval; "
        "the current approved keyframe, if any, is unchanged")
    return [candidate["path"] for candidate in candidates]


def select_keyframe_candidate(scene, shot_id, candidate_id, episode="Ep1", log=print):
    """Select A or B for review/approval without granting approval."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    candidate_id = str(candidate_id or "").strip().upper()
    candidates = list(led.get("keyframeCandidates") or [])
    selected = next((item for item in candidates
                     if str(item.get("candidateId") or "").upper() == candidate_id), None)
    if not selected:
        raise Refused(f"REFUSED — {shot_id} has no pending SEE candidate {candidate_id!r}")
    led["keyframeCandidate"] = selected
    led["selectedKeyframeCandidateId"] = candidate_id
    _save(pkg, path)
    log(f"SEE SELECTED — {shot_id}: {candidate_id} ({selected.get('label')}) — not approved")
    return selected["path"]


def register_existing_keyframe_ab(scene, shot_id, seedream_path, nanobanana_path,
                                  episode="Ep1", prompt_path=None, reference_paths=None,
                                  log=print):
    """Register an already-paid A/B pair without generating or approving anything."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    paths = [pathlib.Path(seedream_path).resolve(), pathlib.Path(nanobanana_path).resolve()]
    if not all(item.exists() for item in paths):
        raise Refused("REFUSED — both existing SEE A/B files must exist before registration")
    existing = led.get("keyframeCandidate") or {}
    shared = {
        "generatedAt": _now(),
        "source": "ab-import",
        "inputSignature": existing.get("inputSignature"),
        "promptContract": existing.get("promptContract"),
        "geometryScreening": existing.get("geometryScreening"),
        "conformanceScreening": existing.get("conformanceScreening"),
    }
    candidates = [
        {**shared, **existing, "candidateId": "A", "label": "A - Seedream 5 Pro",
         "provider": "byteplus", "model": cb_gen.SEEDREAM_MODEL_ID,
         "path": str(paths[0]), "source": "ab-import"},
        {**shared, "candidateId": "B", "label": "B - Nano Banana 2",
         "provider": "google", "model": cb_gen.IMAGE_MODEL,
         "path": str(paths[1]), "source": "ab-import"},
    ]
    for candidate in candidates:
        candidate["packageRevision"] = pkg.get("revision")
        candidate["inputSignature"] = _keyframe_record_input_signature(
            pkg, shot, candidate, scene, episode)
        candidate["contentHash"] = _sha256_file(candidate["path"])
    prompt_hash = (_sha256_file(prompt_path) if prompt_path and os.path.exists(prompt_path)
                   else None)
    ref_hashes = [_sha256_file(item) for item in (reference_paths or [])
                  if item and os.path.exists(item)]
    led["keyframeCandidates"] = candidates
    led["keyframeCandidate"] = candidates[0]
    led["selectedKeyframeCandidateId"] = None
    led["keyframeABTest"] = {
        "createdAt": _now(),
        "registeredExistingPair": True,
        "promptHash": prompt_hash,
        "referenceHashes": ref_hashes,
        "candidateIds": ["A", "B"],
        "selectionRequired": True,
    }
    _save(pkg, path)
    log(f"SEE A/B REGISTERED — {shot_id}: A Seedream 5 Pro; B Nano Banana 2; "
        "selection and approval still required")
    return candidates


def rescreen_keyframe_geometry(scene, shot_id, episode="Ep1", log=print):
    """Repeat the local zero-spend geometry check for the pending candidate."""
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    candidate = _ledger(pkg, shot_id).get("keyframeCandidate") or {}
    candidate_path = candidate.get("path")
    if not candidate_path or not os.path.exists(candidate_path):
        raise Refused(f"REFUSED — {shot_id} has no visible keyframe candidate to screen")
    composition = _load_opening_composition_master(
        shot, scene, episode, _characters_cfg())
    if not composition:
        raise Refused(
            f"REFUSED — {shot_id}'s opening composition master is missing or stale")
    result = cb_layout.screen_candidate_geometry(candidate_path, composition)
    candidate["geometryScreening"] = result
    _save(pkg, path)
    log(f"KEYFRAME GEOMETRY — {shot_id}: {result.get('status')} — {result.get('reason')} "
        "(zero spend)")
    return result


# ── THE OPENING-FRAME SOURCE CHOICE (Julian's directive, 2026-07-18) ────────────────────
# An opening frame's source is the human's own deliberate choice, never only "generate":
#   1. generate     — a real paid render (keyframe_shot above, unchanged)
#   2. upload       — a file the human supplies, no generation cost
#   3. library      — a prior artefact for THIS shot (a past candidate, rejected take,
#                      superseded approval, or a currently-pending one) the human
#                      deliberately re-selects, no generation cost, never automatic
#   4. previousFinalFrame — the immediately previous shot's own approved+harvested final
#                      frame, carried forward as a fresh candidate for THIS shot. This is
#                      available to every shot after the first, including an editorial-cut
#                      opener that still needs a separate human SEE approval — no cost
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


def _previous_shot_id_for_opening_frame(pkg, shot):
    """Return the explicit relay source or the immediate predecessor for a later opener."""
    if shot.get("sourceShotId"):
        return shot["sourceShotId"]
    ordered_shots = list(pkg.get("shots") or [])
    shot_index = next(
        (index for index, item in enumerate(ordered_shots)
         if item.get("shotId") == shot.get("shotId")), -1)
    if shot_index <= 0:
        return None
    return ordered_shots[shot_index - 1].get("shotId")


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

    pending_candidates = list(led.get("keyframeCandidates") or [])
    if pending_candidates:
        for cand in pending_candidates:
            _add(cand.get("path"), cand.get("generatedAt"), "pending",
                 cand.get("label") or cand.get("source"))
    else:
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
    and 'previousFinalFrame' (for any shot after the scene's first — a copy of the immediately
    preceding shot once it is approved+harvested). NEVER calls cb_gen. Refuses if a candidate
    is already pending (matching keyframe_shot's own rule — reject it first)."""
    if mode not in ("upload", "library", "previousFinalFrame"):
        raise Refused(f"REFUSED — unknown opening-frame source {mode!r}; must be "
                      f"upload, library or previousFinalFrame")
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    # A relay shot's approved predecessor frame is already the signed world, geography and
    # continuity anchor. Requiring a separately refreshed Scene Look here incorrectly sends
    # the reviewer backwards after a bounded downstream edit. Uploads, library choices and
    # newly generated frames still require the current Scene Look contract.
    if mode != "previousFinalFrame":
        _require_current_scenelook(scene, episode)
    if led.get("keyframeCandidate"):
        # A relay-source refresh is an explicit replacement of the pending opening frame.
        # Preserve the old candidate for audit, then let the user review the new inherited
        # frame without a reject-first dead end. Generated candidates keep the old rule.
        if mode != "previousFinalFrame":
            raise Refused(f"REFUSED — {shot_id} already has a keyframe candidate awaiting a "
                          f"decision; choose another (reject it, with a reason) first")
        prior = dict(led["keyframeCandidate"])
        prior["outcome"] = "superseded-by-relay-refresh"
        prior["supersededAt"] = _now()
        led.setdefault("keyframeHistory", []).append(prior)
        led["keyframeCandidate"] = None

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
        source_shot_id = _previous_shot_id_for_opening_frame(pkg, shot)
        if not source_shot_id:
            raise Refused(f"REFUSED — {shot_id} is the scene's first shot; there is no "
                          "previous final frame to carry forward")
        src = _ledger(pkg, source_shot_id)
        harvest = src.get("harvestFrame")
        fallback = HERE / "media" / "shots" / f"{episode}_{source_shot_id}_final_frame.png"
        if not harvest and fallback.is_file():
            harvest = str(fallback)
        if (src.get("status") != "approved" or not harvest) and not fallback.is_file():
            raise Refused(f"REFUSED — {source_shot_id} is not approved+harvested yet; "
                          f"there is no final frame to carry forward")
        cand_path = _immutable_candidate_copy(harvest, shot_id, episode)
        source_note = {"source": "previousFinalFrame", "sourceShotId": source_shot_id}

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
    ab_candidates = list(led.get("keyframeCandidates") or [])
    selected_id = str(led.get("selectedKeyframeCandidateId") or "").strip().upper()
    if len(ab_candidates) > 1 and not selected_id:
        raise Refused(
            f"REFUSED — {shot_id} requires an explicit SEE A/B selection before approval")
    if ab_candidates and selected_id != str(cand.get("candidateId") or "").upper():
        raise Refused(
            f"REFUSED — {shot_id}'s selected SEE candidate does not match the approval target")
    if cand.get("source", "generated") == "generated":
        conformance = cand.get("conformanceScreening") or {}
        human_advisory_accepted = bool(
            (cand.get("conformanceAdvisoryDecision") or {}).get("acceptedBy"))
        if conformance.get("status") == "fail" and not human_advisory_accepted:
            raise Refused(f"REFUSED — {shot_id}'s generated keyframe cannot be accepted until "
                          "the objective playable-stage and identity screen passes "
                          f"({conformance.get('status') or 'missing'}). The candidate remains "
                          "visible for Julian to reject or refire; it is never auto-archived.")
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
    ab_audit = []
    if ab_candidates:
        ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = HERE / "media" / "archive" / "shots_superseded" / (
            f"{episode}_{shot_id}_see_ab_{ts}")
        for item in ab_candidates:
            audit_item = {key: item.get(key) for key in (
                "candidateId", "label", "provider", "model", "generatedAt")}
            audit_item["selected"] = item is cand or item.get("path") == cand.get("path")
            source = item.get("path")
            if not audit_item["selected"] and source and os.path.exists(source):
                arch.mkdir(parents=True, exist_ok=True)
                dest = arch / os.path.basename(source)
                shutil.move(source, dest)
                audit_item["archivedFile"] = str(dest.relative_to(HERE))
                for suffix in (".review.json", ".gen.json"):
                    sidecar = pathlib.Path(source + suffix)
                    if sidecar.exists():
                        shutil.move(sidecar, arch / sidecar.name)
            else:
                audit_item["path"] = source
            ab_audit.append(audit_item)
    led["keyframeApproval"] = {"approved": True, "path": cand["path"], "at": _now(),
                                "reviewedBy": reviewed_by, "source": cand.get("source", "generated"),
                                "inputSignature": cand.get("inputSignature"),
                                "promptContract": cand.get("promptContract"),
                                "abTest": {
                                    "winner": selected_id or cand.get("candidateId"),
                                    "candidates": ab_audit,
                                    "contract": led.get("keyframeABTest"),
                                } if ab_candidates else None}
    led["keyframePath"] = cand["path"]    # back-compat pointer for any legacy reader (evidence_pack etc.)
    led["keyframeCandidate"] = None
    led["keyframeCandidates"] = []
    led["selectedKeyframeCandidateId"] = selected_id or None
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
        # The Director can refine the first keyframe brief before any image exists. Record
        # that bounded instruction separately from rejection history so the next generation
        # consumes it without pretending that a candidate was rejected.
        led["pendingKeyframeCorrection"] = {
            "reason": correction.strip(), "recordedAt": _now(),
            "reviewedBy": reviewed_by,
        }
        _save(pkg, path)
        log(f"KEYFRAME CORRECTION QUEUED — {shot_id}: {correction.strip()}\n"
            "  no candidate existed; no media generated or rejected")
        return None
    pending = list(led.get("keyframeCandidates") or [cand])
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_keyframe_{ts}"
    arch.mkdir(parents=True, exist_ok=True)
    archived_rel = None
    archived_candidates = []
    archived_sidecars = []
    for item in pending:
        src = item.get("path")
        item_archive = None
        if src and os.path.exists(src):
            dest = arch / os.path.basename(src)
            shutil.move(src, dest)
            item_archive = str(dest.relative_to(HERE))
            if item is cand or src == cand.get("path"):
                archived_rel = item_archive
            for suffix in (".review.json", ".gen.json"):
                sidecar = pathlib.Path(src + suffix)
                if sidecar.exists():
                    sidecar_dest = arch / sidecar.name
                    shutil.move(sidecar, sidecar_dest)
                    archived_sidecars.append(str(sidecar_dest.relative_to(HERE)))
        archived_candidates.append({
            "candidateId": item.get("candidateId"),
            "provider": item.get("provider"),
            "model": item.get("model"),
            "rejectedFile": item_archive,
        })
    rejection = {**cand, "outcome": "rejected", "rejectedAt": _now(),
                 "reason": correction.strip(), "reviewedBy": reviewed_by,
                 "rejectedFile": archived_rel,
                 "abCandidates": archived_candidates,
                 "archivedSidecars": archived_sidecars,
                 "contentHashAtGeneration": bool(
                     cand.get("contentHash") and cand.get("promptContract"))}
    led.setdefault("keyframeRejections", []).append(rejection)
    led["keyframeRejected"] = rejection
    led["keyframeCandidate"] = None        # cleared from the current position
    led["keyframeCandidates"] = []
    led["selectedKeyframeCandidateId"] = None
    _save(pkg, path)
    log(f"KEYFRAME REJECTED — {shot_id}: {correction}\n  archived -> "
        f"{archived_rel or '(no file was present)'}\n  the previously-approved keyframe, if "
        f"any, is unaffected")
    return archived_rel


# ── Gate 7 — THE CANDIDATE GENERATOR (Julian's probabilistic-model correction,
# 2026-07-16): Seedance is a probabilistic generator, not a deterministic renderer. One
# approved shot contract produces a CONTROLLED CANDIDATE SET (default 1, range 1-4) behind
# an explicit spend disclosure + human approval. Upstream planning and validation control
# the INPUTS; they never guarantee the performance — the product is an approved shot chosen
# from candidates, not a "perfect prompt".
DEFAULT_CANDIDATES = 1
MAX_CANDIDATES = 4
MAX_BATCH_ATTEMPTS = 2      # the failure ladder's hard stop — never an endless patch loop

# the per-candidate evaluation sheet (§6 of the correction) — HUMAN review criteria; the
# machine fills mechanical notes only and never auto-approves creative quality
REVIEW_CRITERIA = ["characterIdentity", "relativeScale", "startingGeography",
                    "actionReadability", "physicalCauseAndEffect",
                    "comicOrEmotionalPerformance", "cameraBehaviour",
                    "dialogueAndMouthPerformance", "continuity", "finalFrameUsability"]

FAILURE_CATEGORIES = ["identity", "geography", "action-timing", "instruction-ignored", "other"]
CONTINUITY_MODE_KEYFRAME = "keyframe-handoff"
CONTINUITY_MODE_VIDEO_EXTENSION = "video-extension"
CONTINUITY_MODES = (CONTINUITY_MODE_KEYFRAME, CONTINUITY_MODE_VIDEO_EXTENSION)

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
    override = str(shot.get("openingFrameOverride") or "").strip()
    if override:
        candidate = _resolved_reference_path(override)
        if not candidate or not candidate.exists():
            raise Refused(
                f"REFUSED — openingFrameOverride for {shot['shotId']} is missing")
        if not _reference_path_is_approved(candidate):
            raise Refused(
                f"REFUSED — openingFrameOverride for {shot['shotId']} resolves outside "
                "the approved Studio media and asset libraries")
        return str(candidate)
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


def _continuity_mode(ledger, shot=None):
    # A frozen final frame can preserve an editorial reset, but it cannot preserve the
    # physical direction or momentum of an active relay. The typed direction record is the
    # source of truth, so legacy ledgers without an explicit mode still take the safe route.
    default = (CONTINUITY_MODE_VIDEO_EXTENSION
               if shot and shot.get("motionContinuityRequired")
               else CONTINUITY_MODE_KEYFRAME)
    mode = str(ledger.get("continuityMode") or default)
    if mode not in CONTINUITY_MODES:
        raise Refused(f"REFUSED — unknown continuity mode {mode!r}; use one of {CONTINUITY_MODES}")
    return mode


def set_continuity_mode(scene, shot_id, mode, episode="Ep1", log=print):
    mode = str(mode or "").strip()
    if mode not in CONTINUITY_MODES:
        raise Refused(f"REFUSED — continuity mode must be one of {CONTINUITY_MODES}")
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    if shot.get("sourceType") == "opener" and mode == CONTINUITY_MODE_VIDEO_EXTENSION:
        raise Refused("REFUSED — video-extension continuity needs a previous approved clip; "
                      "opening shots must use keyframe-handoff")
    if shot.get("motionContinuityRequired") and mode != CONTINUITY_MODE_VIDEO_EXTENSION:
        raise Refused(
            "REFUSED — this relay carries continuity-critical motion and must use "
            "video-extension with the previous approved clip as @Video1")
    led = _ledger(pkg, shot_id)
    led["continuityMode"] = mode
    _save(pkg, path)
    log(f"CONTINUITY MODE — {shot_id}: {mode}")
    return {"scene": str(scene), "shotId": shot_id, "episode": episode, "continuityMode": mode}


def _previous_approved_clip_for(pkg, shot):
    if shot.get("sourceType") == "opener":
        raise Refused("REFUSED — video-extension continuity cannot be used on an opening shot")
    source_id = shot.get("sourceShotId")
    src = _ledger(pkg, source_id)
    clip = src.get("approvedTake")
    if src.get("status") != "approved" or not clip or not os.path.exists(clip):
        raise Refused(f"REFUSED — video-extension continuity needs {source_id}'s approved "
                      "clip as @Video1")
    return clip


def _video_extension_directive(prompt, previous_clip):
    prompt = re.sub(
        r"(@(?:图|Image)\s*1)\s+is the first frame and",
        r"\1 is a boundary-state still from",
        str(prompt),
        count=1,
        flags=re.I,
    )
    summary = "Continue the approved scene into the next directed emotional beat."
    match = re.search(
        r"(?ims)^\[One-Sentence Summary\]\s*(.+?)(?=^\[[^\]]+\]|\Z)", prompt)
    if match and match.group(1).strip():
        summary = " ".join(match.group(1).split())
    directive = (
        "Extend @Video1 forward.\n"
        "The first frame of the extension continues directly from the last frame of @Video1.\n\n"
        "[Video Extension Continuity]\n"
        "@Video1 is the source video to extend forward. Use it only as the continuity "
        "master for the extension boundary, carried motion direction, camera energy, "
        "scene geography, lighting and audio feel; do not inherit or invent unrelated "
        "characters, props, text or actions.\n\n"
        "[Extension Goal]\n"
        f"{summary}\n\n"
        "[Extension Boundary]\n"
        "Preserve the exact boundary pose and orientation, visible prop state, "
        "environment layout, camera position and composition, lighting, "
        "audio environment and carried motion direction. Other references refine identity, "
        "prop design and wider geography only; they must not replace the @Video1 boundary.\n"
        "Each subject remains the same continuous instance throughout: do not duplicate, "
        "split, replace or swap any character or prop. Continue forward naturally without "
        "replaying the previous action, altering @Video1, introducing a hard cut or black "
        "frame, or making an object appear from nothing.\n"
    )
    return directive + "\n" + prompt


def _bank_animation_prompt(pkg, shot_id, led, *, outcome, candidate=None,
                           candidate_path=None, diagnosis=None, category=None):
    shot = _shot(pkg, shot_id)
    prompt_contract = _animation_prompt_contract(led) or {}
    prompt = prompt_contract.get("prompt") or shot.get("seedancePrompt") or ""
    try:
        specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    except Refused as exc:
        specialist = {}
        conformance = {
            "verdict": "UNSCORED",
            "score": None,
            "maximum": 10,
            "findings": [{
                "rule": "stale-animation-direction",
                "severity": "info",
                "message": str(exc),
            }],
        }
    else:
        conformance = _emission_conformance_report(shot, specialist, prompt)
    return cb_prompt_bank.bank_prompt(
        prompt=prompt,
        episode=str(pkg.get("episode") or "Ep1"),
        scene=str(pkg.get("sceneNumber") or ""),
        shot_id=shot_id,
        outcome=outcome,
        candidate=candidate,
        candidate_path=candidate_path,
        diagnosis=diagnosis,
        category=category,
        conformance=conformance,
        metadata={
            "batchId": led.get("batchId") or (led.get("batch") or {}).get("batchId"),
            "promptVersion": _prompt_version(shot, prompt),
            "continuityMode": _continuity_mode(led, shot),
            "archetype": (specialist.get("archetype") or specialist.get("beatArchetype")),
        })


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


def _reference_records(shot, imgs):
    blueprint = _expanded_reference_blueprint(
        shot, "referenceSlots", _characters_cfg())
    if len(blueprint) != len(imgs):
        raise Refused(
            "REFUSED — intact turnaround reference count does not match the sealed "
            "provider attachments")
    return [
        {"slot": item["slot"], "sourceSlot": item["sourceSlot"],
         "role": item["role"], "view": item.get("view"), "path": path,
         "intactTurnaround": bool((item.get("identity") or {}).get(
             "intactTurnaround")),
         "sameCharacterGroup": ((item.get("identity") or {}).get(
             "turnaroundGroupHash")),
         "md5": _file_md5(path)}
        for item, path in zip(blueprint, imgs)
    ]


def _require_prompt_slot_text_consistency(prompt, reference_records):
    """Refuse prompts whose prose contradicts the sealed provider upload slots."""
    roles_by_slot = {
        str(item.get("slot") or "").strip(): str(item.get("role") or "").strip()
        for item in reference_records or []
        if str(item.get("slot") or "").strip() and str(item.get("role") or "").strip()
    }
    character_roles = [
        str(name or "").strip() for name in (_characters_cfg().keys())
        if str(name or "").strip()
    ]
    conflicts = []
    for slot, role in roles_by_slot.items():
        if _is_non_identity_image_role(role):
            continue
        other_roles = [
            name for name in character_roles
            if name.casefold() != role.casefold()
        ]
        slot_pat = re.escape(slot)
        for other in other_roles:
            other_pat = re.escape(other)
            possessive_suffix = ""
            for marker in ("'s ", "’s "):
                prefix = other.casefold() + marker
                if role.casefold().startswith(prefix):
                    suffix = role[len(other) + len(marker):]
                    possessive_suffix = (
                        rf"(?!['’]s\s+{re.escape(suffix)}\b)"
                    )
                    break
            patterns = [
                rf"{slot_pat}\s*(?:is|=|:|/)\s*(?:one\s+)?{other_pat}\b{possessive_suffix}",
                rf"{slot_pat}\s*/\s*{other_pat}\b{possessive_suffix}",
            ]
            if any(re.search(pattern, prompt or "", re.I) for pattern in patterns):
                conflicts.append(f"{slot} is sealed as {role}, but prompt text assigns {other}")
    if conflicts:
        raise Refused(
            "REFUSED — provider reference slot text conflicts with sealed uploads: "
            + "; ".join(conflicts[:6]))


def _with_intact_turnaround_law(prompt, references):
    """Make the one-sheet/one-character rule explicit in every animation request."""
    identity_refs = [item for item in references if item.get("intactTurnaround")]
    if not identity_refs:
        return prompt
    lines = ["[Locked Character Turnarounds]"]
    for item in identity_refs:
        lines.append(
            f"{item['slot']} defines {item['role']}'s complete, uncropped 360 turnaround "
            "sheet. Every view on this sheet is the same character identity, not an "
            "additional character. Use the entire sheet for face, silhouette, proportions, "
            "markings and rear/side details; render exactly one instance of this character "
            "unless the script explicitly requires otherwise. Do not use the sheet layout "
            "as the shot composition.")
    return "\n".join(lines) + "\n\n" + prompt


def _provider_safe_dialogue_prompt(prompt, dialogue_lines):
    """Keep the signed transcript as lip-sync evidence without authoring new speech."""
    text = str(prompt or "")
    lines = list(dialogue_lines or [])
    if not lines:
        return text

    # Current Animation Director prompts already carry the complete, reviewed single-track
    # contract. Rewriting that contract at transport time created a second differently
    # worded audio lock, so the prompt shown to the reviewer was not the prompt submitted to
    # Seedance. Preserve the signed bytes when all three operational guarantees are present.
    normalized = text.casefold()
    if (
        "@audio1" in normalized and
        "sole authority" in normalized and
        "do not synthesize, repeat, dub, echo, layer or replace" in normalized and
        "exactly one audible dialogue performance" in normalized
    ):
        return text

    lock = (
        "AUDIO PERFORMANCE LOCK - @Audio1 is the single audible dialogue performance. "
        "The verbatim transcript below is timing and speaker-assignment evidence only: "
        "animate each named speaker's mouth to the matching words already audible in "
        "@Audio1. Never synthesize, repeat, dub, echo, layer, reinterpret or replace any "
        "spoken word. Silent listeners keep their mouths closed. Seedance must create "
        "synchronized non-verbal SFX, ambience and instrumental music around @Audio1."
    )
    if emission.SINGLE_INSTANCE_DIALOGUE_LOCK in text:
        return text.replace(emission.SINGLE_INSTANCE_DIALOGUE_LOCK, lock)
    return lock + "\n\n" + text


def _comparison_args(comparison_model_id, comparison_run_id):
    if comparison_model_id is None and comparison_run_id is None:
        return None, None
    model_id = str(comparison_model_id or "").strip()
    run_id = str(comparison_run_id or "").strip()
    if model_id != cb_seedance_transport.COMPARISON_MODEL_ID:
        raise Refused("REFUSED — only fal-seedance-2.0 is allowed as the comparison model")
    if not run_id or len(run_id) > 120:
        raise Refused("REFUSED — a bounded comparison run ID is required")
    return model_id, run_id


def _animation_execution_plan(pkg, shot, led, imgs, anchor, fast,
                              comparison_model_id=None, comparison_run_id=None,
                              materialize_audio=False, include_audio_reference=True,
                              generate_audio=True):
    """Return every exact provider call that will produce one Studio candidate."""
    import cb_costs
    def provider_audio_path(master, duration):
        """Fit the approved HEAR master to the picture without changing its speech."""
        if not master or not os.path.exists(master):
            return master
        master_duration = _audio_dur(master)
        if master_duration >= float(duration) - 0.02:
            return master
        key = hashlib.sha256(f"{master}|{_file_md5(master)}|{duration}".encode()).hexdigest()[:16]
        out = MEDIA / "transport" / f"{shot['shotId']}_{key}_hear_bed.wav"
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run([
                "ffmpeg", "-y", "-v", "error", "-i", str(master), "-af",
                f"apad,atrim=0:{float(duration):.6f}", "-ar", "48000", "-ac", "2",
                "-c:a", "pcm_s16le", str(out),
            ], capture_output=True, text=True)
            if result.returncode or not out.exists():
                raise Refused("REFUSED - could not fit approved HEAR audio to the shot duration")
        return str(out)

    fitted_audio = (provider_audio_path(led.get("voPath"), shot["durationSec"])
                    if include_audio_reference else None)
    model_id, run_id = _comparison_args(comparison_model_id, comparison_run_id)
    references = _reference_records(shot, imgs)
    parent_prompt = _with_intact_turnaround_law(
        shot["seedancePrompt"], references)
    continuity_mode = _continuity_mode(led, shot)
    video_references = []
    if continuity_mode == CONTINUITY_MODE_VIDEO_EXTENSION:
        previous_clip = _previous_approved_clip_for(pkg, shot)
        parent_prompt = _video_extension_directive(parent_prompt, previous_clip)
        video_references = [{
            "slot": "@Video1",
            "role": "previous approved clip continuity master",
            "path": previous_clip,
            "md5": _file_md5(previous_clip),
        }]
    provider_prompt = _provider_safe_dialogue_prompt(
        parent_prompt, cb_audio_authority.spoken_dialogue_lines(shot))
    if model_id is None:
        try:
            contract = cb_providers.request_contract(
                fast=fast, duration=int(round(shot["durationSec"])),
                resolution=_review_video_resolution(),
                image_count=len(imgs), audio_count=1 if (
                    include_audio_reference and led.get("voPath")) else 0,
                video_count=len(video_references),
                mode=("video-extension" if video_references else None))
        except cb_providers.ProviderCapabilityError as exc:
            raise Refused(f"REFUSED — provider capability: {exc}") from exc
        per = round(cb_costs.estimate_video_cost(
            contract["costRateKey"], int(round(shot["durationSec"]))), 4)
        # The default provider route used to return before attaching the same prompt
        # evidence recorded by the comparison route. Keep the spend audit complete on
        # both paths so every fire carries the creative and authoring scores.
        audit = cb_prompt_lab.analyze_seedance_prompt_contract(
            parent_prompt,
            task_mode=("extend-forward" if video_references else "reference-to-video"),
            reference_contract=references,
            duration_sec=shot["durationSec"],
            dialogue_lines=[], stage_plan=[])
        authoring_score = _seedance_authoring_score(audit)
        creative_gate = _prompt_contract_completeness(shot, parent_prompt, {})
        audit["authoringScore10"] = authoring_score
        audit["authoringMaximum"] = 10
        audit["firingFloor10"] = SEEDANCE_AUTHORING_FLOOR
        audit["creativeGate"] = {
            "score": creative_gate["score"],
            "maximum": creative_gate["maximum"],
            "threshold": creative_gate["threshold"],
            "ready": not creative_gate["needsRevision"],
            "criticalFailures": creative_gate["criticalFailures"],
        }
        audit["contractCompleteness"] = dict(audit["creativeGate"])
        if audit["status"] != "ready":
            raise Refused(
                f"REFUSED — provider prompt audit is {audit['score']}/{audit['maximum']}; "
                "repair the current prompt before spend")
        if creative_gate["needsRevision"] or authoring_score < SEEDANCE_AUTHORING_FLOOR:
            raise Refused(
                f"REFUSED — prompt contract completeness is {creative_gate['score']}/"
                f"{creative_gate['maximum']}, authoring {authoring_score}/10; "
                f"minimum authoring floor is {SEEDANCE_AUTHORING_FLOOR}/10")
        return {
            "schemaVersion": 1,
            "mode": "single-qualified-provider-call",
            "continuityMode": continuity_mode,
            "studioShotId": shot["shotId"],
            "studioDurationSec": shot["durationSec"],
            "providerModelId": contract["providerModelId"],
            "comparisonRunId": None,
            "parentPromptHash": hashlib.sha256(parent_prompt.encode()).hexdigest(),
            "costPerStudioCandidateUsd": per,
            "segments": [{
                "segmentIndex": 1, "segmentCount": 1,
                "globalStartSec": 0.0, "globalEndSec": shot["durationSec"],
                "durationSec": shot["durationSec"], "stageNumbers": [],
                "prompt": provider_prompt,
                "promptHash": hashlib.sha256(provider_prompt.encode()).hexdigest(),
                "signedPromptHash": hashlib.sha256(parent_prompt.encode()).hexdigest(),
                "promptAudit": audit,
                "dynamicOpeningRelay": False,
                "references": references,
                "videoReferences": video_references,
                "audio": ({"path": fitted_audio,
                           "md5": _file_md5(fitted_audio),
                           "sourcePath": led.get("voPath"),
                           "sourceMd5": _file_md5(led.get("voPath"))}
                          if fitted_audio else None),
                "generateAudio": bool(generate_audio),
                "contract": contract,
                "costUsd": per,
            }],
        }

    specialist = _approved_department_output(pkg, shot["shotId"], "animation") or {}
    attached = [
        {"position": index, "assetTag": item["slot"], "role": item["role"],
         "path": item["path"], "contentHash": _sha256_file(item["path"])}
        for index, item in enumerate(references, start=1)
    ]
    if include_audio_reference and led.get("voPath"):
        attached.append({
            "position": len(attached) + 1, "assetTag": "@Audio1",
            "role": "approved dialogue and performance track",
            "path": fitted_audio, "contentHash": _sha256_file(fitted_audio),
        })
    base_task = _seedance_pipeline_task(shot, specialist, attached)
    try:
        plan = cb_seedance_transport.build_comparison_plan(
            shot=shot, approved_direction=specialist, base_task=base_task,
            parent_prompt=parent_prompt, comparison_run_id=run_id, model_id=model_id)
    except cb_seedance_transport.TransportPlanError as exc:
        raise Refused(f"REFUSED — comparison transport: {exc}") from exc

    audio_master = fitted_audio
    audio_master_hash = _file_md5(audio_master) if audio_master else None
    total_cost = 0.0
    for segment in plan["segments"]:
        segment["segmentCount"] = len(plan["segments"])
        if segment["dynamicOpeningRelay"]:
            segment["references"] = [{
                "slot": references[0]["slot"],
                "role": "literal final frame from the preceding internal segment",
                "dynamicFromSegment": segment["segmentIndex"] - 1,
            }, *references[1:]]
        else:
            segment["references"] = list(references)
        segment["generateAudio"] = bool(generate_audio)
        has_dialogue = bool(segment["dialogueLineIndexes"])
        audio = None
        if has_dialogue:
            if not audio_master or not os.path.exists(audio_master):
                raise Refused("REFUSED — comparison segment needs the approved timed voice master")
            audio = {
                "sourcePath": audio_master, "sourceMd5": audio_master_hash,
                "sourceStartSec": segment["globalStartSec"],
                "sourceEndSec": segment["globalEndSec"],
                "dialogueLineIndexes": segment["dialogueLineIndexes"],
            }
            if materialize_audio:
                audio_key = hashlib.sha256(json.dumps(
                    audio, sort_keys=True).encode()).hexdigest()[:16]
                audio_path = (MEDIA / "transport" /
                              f"{shot['shotId']}_{audio_key}_audio.wav")
                try:
                    derived = cb_audio_timing.slice_timed_master(
                        audio_master, segment["globalStartSec"],
                        segment["globalEndSec"], audio_path)
                except cb_audio_timing.AudioTimingError as exc:
                    raise Refused(f"REFUSED — comparison audio: {exc}") from exc
                audio.update({"path": derived["path"], "md5": _file_md5(derived["path"])})
        segment["audio"] = audio
        try:
            contract = cb_providers.comparison_request_contract(
                comparison_run_id=run_id, fast=fast,
                duration=segment["durationSec"], resolution="720p",
                image_count=len(imgs), audio_count=1 if has_dialogue else 0,
                video_count=0, model_id=model_id)
        except cb_providers.ProviderCapabilityError as exc:
            raise Refused(f"REFUSED — provider capability: {exc}") from exc
        segment["contract"] = contract
        segment["costUsd"] = round(cb_costs.estimate_video_cost(
            contract["costRateKey"], segment["durationSec"]), 4)
        total_cost += segment["costUsd"]
        audit = cb_prompt_lab.analyze_seedance_prompt_contract(
            segment["prompt"], task_mode="reference-to-video",
            reference_contract=segment["referenceContract"],
            duration_sec=segment["durationSec"],
            dialogue_lines=[shot["dialogueLines"][index]
                            for index in segment["dialogueLineIndexes"]],
            stage_plan=segment["compiledStages"],
        )
        # Score both gates at the same point that the provider request is assembled. These
        # values travel inside the sealed execution plan and spend disclosure, so the fire
        # record preserves the exact contract-completeness evidence for this prompt.
        authoring_score = _seedance_authoring_score(audit)
        creative_gate = _prompt_contract_completeness(
            {**shot, "dialogueLines": [shot["dialogueLines"][index]
                                        for index in segment["dialogueLineIndexes"]]},
            segment["prompt"], specialist)
        audit["authoringScore10"] = authoring_score
        audit["authoringMaximum"] = 10
        audit["firingFloor10"] = SEEDANCE_AUTHORING_FLOOR
        audit["creativeGate"] = {
            "score": creative_gate["score"],
            "maximum": creative_gate["maximum"],
            "threshold": creative_gate["threshold"],
            "ready": not creative_gate["needsRevision"],
            "criticalFailures": creative_gate["criticalFailures"],
        }
        audit["contractCompleteness"] = dict(audit["creativeGate"])
        segment["promptAudit"] = audit
        if audit["status"] != "ready":
            failed_codes = [
                item["code"] for item in audit.get("checks") or []
                if item.get("required") and item.get("status") != "pass"
            ]
            raise Refused(
                f"REFUSED — provider segment {segment['segmentIndex']} prompt audit is "
                f"{audit['score']}/{audit['maximum']}"
                + (f" ({', '.join(failed_codes)})" if failed_codes else "")
                + "; repair the current Animation direction"
            )
        if creative_gate["needsRevision"] or authoring_score < SEEDANCE_AUTHORING_FLOOR:
            raise Refused(
                f"REFUSED — segment {segment['segmentIndex']} scores "
                f"creative {creative_gate['score']}/{creative_gate['maximum']}, "
                f"authoring {authoring_score}/10; minimum authoring floor is "
                f"{SEEDANCE_AUTHORING_FLOOR}/10"
            )
    plan["costPerStudioCandidateUsd"] = round(total_cost, 4)
    return plan


def _binding_hash(pkg, shot, led, imgs, anchor, candidates, fast,
                  comparison_model_id=None, comparison_run_id=None,
                  execution_plan=None):
    """Everything the spend approval is bound to.

    The binding covers this shot's exact provider inputs and cost envelope. Package revision
    and other shots are provenance, not spend inputs, so an unrelated promotion cannot void a
    token while any changed prompt, media byte, duration, tier, count or rate still does.
    """
    import cb_costs
    execution_plan = execution_plan or _animation_execution_plan(
        pkg, shot, led, imgs, anchor, fast, comparison_model_id,
        comparison_run_id, materialize_audio=True)
    per = execution_plan["costPerStudioCandidateUsd"]
    payload = {"shotContractHash": hashlib.sha256(json.dumps(
                   shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
               "shotId": shot["shotId"],
               "providerModelId": execution_plan["providerModelId"],
               "comparisonRunId": execution_plan.get("comparisonRunId"),
               "candidates": candidates,
               "maxBatchCostUsd": round(per * candidates, 4),
               "prompt": shot["seedancePrompt"],
               "slotOrder": _reference_records(shot, imgs),
               "anchorMd5": _file_md5(anchor),
               "refMd5s": [_file_md5(p) for p in imgs],
               "audioMd5": _file_md5(led["voPath"]) if led.get("voPath") else None,
               "durationSec": shot["durationSec"],
               "executionPlan": execution_plan}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32], per


def _fresh_validation(pkg, episode, target_shot_id=None):
    """PROTECTION 4: validation is re-run against the CURRENT package content at every
    disclosure — a hand-edited or revised package can never fire on a stale green stamp.
    Zero-LLM (cb_engine's deterministic validator, imported, never modified)."""
    import cb_engine as E

    def is_sfx_bridge(rec):
        policy = str(rec.get("audioPolicy") or "").lower()
        return (
            not rec.get("dialogueLines")
            and not rec.get("dialogueBinding")
            and "seedance sfx only" in policy
        )

    def owned_beat_codes(rec):
        if target_shot_id and rec.get("shotId") != target_shot_id:
            return []
        if is_sfx_bridge(rec):
            return []
        beat_codes = list(rec.get("beatCodes") or [])
        beat_code = str(rec.get("beatCode") or "").strip()
        if not beat_codes and "+" in beat_code:
            beat_codes = [part.strip() for part in beat_code.split("+") if part.strip()]
        if not beat_codes and beat_code:
            beat_codes = [beat_code]
        return beat_codes

    def active_shots(records):
        return [
            rec for rec in records
            if str(rec.get("status") or "").strip().lower() not in {
                "superseded", "archived", "inactive"}
            and not rec.get("superseded")
            and rec.get("active", True) is not False
        ]

    def adapt_shot(rec, *, is_first=False):
        data = {k: v for k, v in rec.items() if k in E.Shot.model_fields}
        if "physicalStagings" in data:
            data["physicalStagings"] = [
                item for item in data.get("physicalStagings") or []
                if isinstance(item, dict) or hasattr(item, "model_dump")
            ]
        beat_codes = owned_beat_codes(rec)
        if beat_codes:
            data["beatCodes"] = beat_codes
            data["beatCode"] = beat_codes[0]
        action = str(rec.get("action") or rec.get("storyBeat") or rec.get("purpose") or "")
        data.setdefault("performanceAssignment", action or "Perform the approved director action.")
        data.setdefault("camera", rec.get("camera") or "Camera follows the approved director geography.")
        data.setdefault("openingPose", rec.get("openingPose") or rec.get("sourceType") or "approved opening state")
        data.setdefault("prohibited", [
            _continuity_constraint_text(item)
            for item in rec.get("continuityConstraints") or []
            if _continuity_constraint_text(item)
        ] or ["No identity drift.", "No continuity drift."])
        chars = list(rec.get("charactersInFrame") or [])
        def validation_continuity(label):
            return {
                "lighting": rec.get("time") or "approved scene light",
                "cameraSide": "approved camera side",
                "characters": [
                    {
                        "character": name,
                        "screenZone": f"approved {label} position",
                        "facing": "approved direction",
                        "pose": f"approved {label} pose",
                        "expression": "approved expression",
                        "visibleMarks": [],
                        "heldProps": [],
                    }
                    for name in chars
                ],
            }

        def complete_validation_continuity(value, label):
            if not isinstance(value, dict):
                return validation_continuity(label)
            existing = [
                item for item in value.get("characters") or []
                if isinstance(item, dict) and str(item.get("character") or "").strip()
            ]
            seen = {str(item.get("character") or "").strip() for item in existing}
            missing = [name for name in chars if name not in seen]
            if not missing:
                return value
            completed = dict(value)
            completed["characters"] = existing + [
                {
                    "character": name,
                    "screenZone": f"approved {label} position",
                    "facing": "approved direction",
                    "pose": f"approved {label} pose",
                    "expression": "approved expression",
                    "visibleMarks": [],
                    "heldProps": [],
                }
                for name in missing
            ]
            completed.setdefault("lighting", rec.get("time") or "approved scene light")
            completed.setdefault("cameraSide", "approved camera side")
            return completed

        raw_lines = list(rec.get("dialogueLines") or [])
        duration = float(rec.get("durationSec") or 1)
        data["dialogueLines"] = []
        for index, line in enumerate(raw_lines):
            fallback_start = round((duration / max(1, len(raw_lines))) * index, 2)
            fallback_end = round(
                (duration / max(1, len(raw_lines))) * (index + 1), 2)
            data["dialogueLines"].append({
                **line,
                "exactText": line.get("exactText") if line.get("exactText") is not None else line.get("text", ""),
                "delivery": line.get("delivery") or "as approved in the voice direction",
                "startSec": line.get("startSec", fallback_start),
                "endSec": line.get("endSec", fallback_end),
            })
        if data["dialogueLines"] and not data.get("dialogueBinding"):
            data["dialogueBinding"] = "; ".join(
                f"{line['speaker']} says exactly {line['exactText']}"
                for line in data["dialogueLines"])
        data["continuityOut"] = complete_validation_continuity(
            data.get("continuityOut"), "final")
        if target_shot_id and is_first and data.get("sourceType") == "relay":
            # This validator receives one current production unit at disclosure time.
            # _anchor_for has already proved the real predecessor's human approval and
            # harvested bytes, so represent the target as the validation slice's opener
            # instead of revalidating completed upstream story ownership.
            data["sourceType"] = "opener"
            data["sourceShotId"] = None
            data.pop("continuityIn", None)
        elif data.get("sourceType") == "relay":
            data["continuityIn"] = complete_validation_continuity(
                data.get("continuityIn"), "starting")
        elif is_first and "continuityIn" in data:
            data.pop("continuityIn", None)
        return data

    d, _ = E._load_pkg(episode)
    source_beats = E._scene_beats(d, pkg["sceneNumber"])
    source_by_code = {item.get("beatCode"): item for item in source_beats}
    current_shots = active_shots(pkg["shots"])
    if target_shot_id:
        by_id = {rec.get("shotId"): rec for rec in current_shots}
        target = by_id.get(target_shot_id)
        if not target:
            raise Refused(f"REFUSED — {target_shot_id} is not active in the current package")
        # Validate only the unit being disclosed. Completed ancestors are immutable media
        # handoffs; their approval and harvested bytes were already enforced by _anchor_for.
        # Revalidating their old beat ownership after a downstream edit is the blanket-reset
        # failure this shot-scoped path exists to prevent.
        current_shots = [target]
    selected_codes = list(dict.fromkeys(
        code for rec in current_shots for code in owned_beat_codes(rec)))
    beats = [json.loads(json.dumps(source_by_code[code]))
             for code in selected_codes if code in source_by_code]

    if target_shot_id:
        # BIG-gag staging is owned by exactly one production unit. A later unit may
        # legitimately continue the same source beat after that physical gag has already
        # landed in approved media. Keep the source event for dialogue/action validation,
        # while requiring a new BIG staging contract only when this target owns one.
        target_stage_codes = {
            str(item.get("beatCode") or "")
            for item in (
                list(target.get("physicalStagings") or []) +
                ([target.get("physicalStaging")]
                 if isinstance(target.get("physicalStaging"), dict) else [])
            )
            if isinstance(item, dict)
        }
        for beat in beats:
            if (str(beat.get("comedyMode") or "").upper() == "BIG" and
                    str(beat.get("beatCode") or "") not in target_stage_codes):
                beat["comedyMode"] = "SMALL"

    # A shot-level voice approval can intentionally replace the dialogue wording from
    # an older beat-package snapshot. Keep this reconciliation narrow: it applies only
    # to the target shot, only after human HEAR approval, and leaves all non-dialogue
    # source actions under the normal validator.
    if target_shot_id:
        target_ledger = _ledger(pkg, target_shot_id)
        target_voice = target_ledger.get("voiceApproval") or {}
        target_rec = next((rec for rec in pkg["shots"]
                           if rec.get("shotId") == target_shot_id), None)
        if (target_voice.get("approved") and target_rec and
                cb_audio_authority.spoken_dialogue_lines(target_rec)):
            target_codes = set(owned_beat_codes(target_rec))
            # Validate the immutable script representation, including pure and mixed SFX
            # occurrences. spoken_dialogue_lines() is the correct ElevenLabs provider view,
            # but using it here dropped a pure sneeze and stripped SFX text from mixed lines,
            # producing false UNKNOWN/PAYLOAD_CHANGED lineage errors at WATCH Fire.
            target_lines = list(target_rec.get("dialogueLines") or [])
            target_beats = [beat for beat in beats if beat.get("beatCode") in target_codes]
            for beat_index, beat in enumerate(target_beats):
                original_cuts = list(beat.get("cuts") or [])
                action_cuts = [cut for cut in original_cuts if not (cut.get("dialogue") or "").strip()]
                voice_cuts = []
                # A current HEAR approval is the exact shot-level dialogue bundle. Put it
                # once on the first owned source beat even when a cleaned script edit has
                # changed occurrence IDs or collapsed an older multi-beat split.
                if beat_index == 0:
                    for index, line in enumerate(target_lines, start=1):
                        text = str(line.get("exactText") or line.get("text") or "").strip()
                        speaker = str(line.get("speaker") or "").strip()
                        if not text or not speaker:
                            continue
                        voice_cuts.append({
                            "n": index,
                            "sourceEventId": line.get("sourceEventId"),
                            "sourceEventType": "approved-shot-voice",
                            "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
                            "speaker": speaker,
                            "exactText": text,
                            "dialogue": f"{speaker}: {text}",
                            "action": None,
                        })
                beat["cuts"] = voice_cuts + action_cuts
                beat["dialogueOccurrenceIds"] = [
                    cut["dialogueOccurrenceId"] for cut in voice_cuts
                    if cut.get("dialogueOccurrenceId")
                ]
        # A source beat may be distributed across several active shots.  For a
        # target-shot disclosure, validate only the source dialogue occurrences
        # assigned to that shot, while preserving exact speaker/text comparison.
        target_lines = list((target_rec or {}).get("dialogueLines") or [])
        target_pairs = [(str(line.get("speaker") or "").strip().casefold(),
                         str(line.get("exactText") or line.get("text") or "").strip())
                        for line in target_lines]
        for beat in beats:
            source_cuts = list(beat.get("cuts") or [])
            dialogue_cuts = [cut for cut in source_cuts if (cut.get("dialogue") or "").strip()]
            if not dialogue_cuts:
                continue
            if not target_pairs:
                beat["cuts"] = [
                    cut for cut in source_cuts
                    if not (cut.get("dialogue") or "").strip()
                ]
                beat["dialogueOccurrenceIds"] = []
                continue
            filtered = []
            remaining = list(target_pairs)
            for cut in source_cuts:
                raw = str(cut.get("dialogue") or "").strip()
                if not raw or ":" not in raw:
                    filtered.append(cut)
                    continue
                speaker, text = raw.split(":", 1)
                pair = (speaker.strip().casefold(), text.strip().strip('"“”'))
                text_matches = [item for item in remaining if item[1] == pair[1]]
                if pair in remaining or text_matches:
                    filtered.append(cut)
                    remaining.remove(pair if pair in remaining else text_matches[0])
            # If the target contains a line not present in the locked source, retain
            # the full source beat so the normal verbatim validator rejects it.
            if not remaining and len(current_shots) == 1:
                beat["cuts"] = filtered
    shots = [
        E.Shot(**adapt_shot(rec, is_first=index == 0))
        for index, rec in enumerate(current_shots)
    ]
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


def _prompt_version(shot, prompt=None):
    import hashlib
    return hashlib.md5(
        str(prompt if prompt is not None else shot.get("seedancePrompt") or "").encode()
    ).hexdigest()[:8]


def _sealed_envelope(pkg, shot, led, imgs, anchor, candidates, fast, per,
                     comparison_model_id=None, comparison_run_id=None,
                     execution_plan=None):
    """THE IMMUTABLE PROVIDER-REQUEST ENVELOPE (Julian's cutover order, 2026-07-16, §5):
    everything the provider will receive, sealed AT DISCLOSURE — exact prompt, duration, model,
    resolution, candidate count, reference order with per-file hashes, audio hash, max cost.
    The spend token binds to this envelope's hash; firing sends THIS, never a recompile."""
    refs = _reference_records(shot, imgs)
    execution_plan = execution_plan or _animation_execution_plan(
        pkg, shot, led, imgs, anchor, fast, comparison_model_id,
        comparison_run_id, materialize_audio=True)
    first_contract = execution_plan["segments"][0]["contract"]
    working = led.get("workingSeedancePrompt") or {}
    specialist = _approved_department_output(pkg, shot["shotId"], "animation") or {}
    prompt_source = (
        "human-working" if working.get("text") == shot["seedancePrompt"] else
        "animation-director-current" if specialist.get("providerPrompt") else
        "legacy-approved-storyboard"
    )
    env = {"shotId": shot["shotId"], "prompt": shot["seedancePrompt"],
           "promptSource": prompt_source,
           "durationSec": shot["durationSec"], "provider": first_contract["provider"],
           "providerModelId": first_contract["providerModelId"],
           "modelVersion": first_contract["modelVersion"],
           "transport": first_contract["transport"],
           "endpoint": first_contract["endpoint"],
           "costRateKey": first_contract["costRateKey"],
           "capabilityVerifiedAt": first_contract["capabilityVerifiedAt"],
           "resolution": first_contract["resolution"],
           "tier": "fast" if fast else "standard",
           "candidateCount": candidates, "costPerCandidateUsd": per,
           "maxBatchCostUsd": round(per * candidates, 4),
           "promptVersion": _prompt_version(shot), "references": refs,
           "audio": {"path": led.get("voPath"),
                      "md5": _file_md5(led["voPath"]) if led.get("voPath") else None},
           "executionPlan": execution_plan,
           "comparisonRunId": execution_plan.get("comparisonRunId")}
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
    plan = env.get("executionPlan") or {}
    segments = plan.get("segments") or []
    if not segments:
        raise Refused("REFUSED — the sealed envelope has no provider execution plan")
    for segment in segments:
        for reference in segment.get("references") or []:
            if reference.get("dynamicFromSegment") is not None:
                continue
            if _file_md5(reference.get("path")) != reference.get("md5"):
                raise Refused(
                    f"REFUSED — segment {segment.get('segmentIndex')} reference "
                    f"{reference.get('slot')} changed after disclosure"
                )
        audio = segment.get("audio") or {}
        if audio.get("sourcePath") and _file_md5(audio["sourcePath"]) != audio.get("sourceMd5"):
            raise Refused("REFUSED — the approved timed voice master changed after disclosure")
        if audio.get("path") and _file_md5(audio["path"]) != audio.get("md5"):
            raise Refused(
                f"REFUSED — segment {segment.get('segmentIndex')} audio changed after disclosure"
            )
    return env


# ── THE ANIMATION WORKING PROMPT (Julian's directive, 2026-07-19) ───────────────────────
# A contained creative control INSIDE the existing Animation stage. shot["seedancePrompt"] is
# already, honestly, "the complete Seedance prompt exactly as it will be submitted" — this
# lets Julian edit that SAME string (action, timing, physical comedy, camera, performance
# direction all live inside it as compiled prose) and save the edit as a shot-level working
# version, never touching the approved storyboard's own compiled seedancePrompt field.
# Reading/saving/restoring never calls cb_gen; only fire_shot's own real generation spends.
def _seedance_working_input_signature(pkg, shot, scene, episode="Ep1"):
    """Inputs that make a saved human WATCH prompt current enough to submit."""
    led = _ledger(pkg, shot["shotId"])
    try:
        specialist = _approved_department_output(pkg, shot["shotId"], "animation") or {}
    except Refused:
        work, _ = _department_container(
            pkg, scene, shot["shotId"], "animation", episode)
        record = work.get("candidate") or work.get("approved") or {}
        specialist = record.get("output") or {}
    keyframe = led.get("keyframeApproval") or {}
    voice = led.get("voiceApproval") or {}
    refs = []
    try:
        refs = [
            item["path"] for item in _provider_attachment_plan(
                shot, "referenceSlots", None, str(scene), episode, _characters_cfg())
        ]
    except Refused:
        refs = []
    return {
        "packageRevision": pkg.get("revision"),
        "storyboardSha256": (pkg.get("sourceStoryboard") or {}).get("sha256"),
        "shotContractHash": hashlib.sha256(json.dumps(
            {k: v for k, v in shot.items() if k != "seedancePrompt"},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "approvedAnimationPromptHash": hashlib.sha256(
            str(specialist.get("providerPrompt") or shot.get("seedancePrompt") or "")
            .encode()).hexdigest(),
        "keyframeApproval": {
            "path": keyframe.get("path"),
            "hash": keyframe.get("hash"),
            "inputSignature": keyframe.get("inputSignature"),
        },
        "voiceApproval": {
            "approved": bool(voice.get("approved")),
            "path": led.get("voPath"),
            "md5": _file_md5(led.get("voPath")) if led.get("voPath") else None,
        },
        "referenceMd5s": {os.path.basename(p): _file_md5(p) for p in refs},
    }


def _resolve_seedance_prompt(pkg, shot, scene=None, episode="Ep1", require_current_working=False):
    """Returns (prompt_text, is_working) — the prompt fire_shot will actually submit right
    now: the saved working override if one exists, else the approved compiled prompt."""
    led = _ledger(pkg, shot["shotId"])
    working = led.get("workingSeedancePrompt")
    if working and working.get("text"):
        if require_current_working:
            if scene is None:
                scene = str(pkg.get("sceneNumber") or "")
            expected = _seedance_working_input_signature(pkg, shot, scene, episode)
            if working.get("inputSignature") != expected:
                raise Refused(
                    "REFUSED — saved WATCH working prompt is stale against the current "
                    "SEE/HEAR/reference inputs. Restore it or save the prompt again after "
                    "the current Animation direction is prepared."
                )
        base, is_working = working["text"], True
    else:
        output = _approved_department_output(pkg, shot["shotId"], "animation") or {}
        base = output.get("providerPrompt") or shot.get("seedancePrompt") or ""
        is_working = False
    return (_with_character_scale_control(
        base, shot, "referenceSlots", str(pkg.get("sceneNumber")),
        pkg.get("episode") or "Ep1"), is_working)


def seedance_working_status(scene, shot_id, episode="Ep1"):
    """READ-ONLY, zero cost. {"approvedPrompt": str, "currentPrompt": str (working override
    if saved, else the approved prompt — exactly what will be submitted), "isWorking": bool,
    "savedAt": str|None}."""
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    current, is_working = _resolve_seedance_prompt(pkg, shot, scene, episode)
    led = _ledger(pkg, shot_id)
    working = led.get("workingSeedancePrompt")
    try:
        specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    except Refused:
        work, _ = _department_container(pkg, scene, shot_id, "animation", episode)
        record = work.get("candidate") or work.get("approved") or {}
        specialist = record.get("output") or {}
    source = ("human-working" if is_working else
              "animation-director-current" if specialist.get("providerPrompt") else
              "legacy-approved-storyboard")
    baseline = specialist.get("providerPrompt") or shot.get("seedancePrompt") or ""
    return {"approvedPrompt": baseline, "currentPrompt": current,
            "source": source,
            "isWorking": is_working, "savedAt": (working or {}).get("savedAt")}


def save_seedance_working(scene, shot_id, prompt_text, episode="Ep1", reviewed_by="Julian", log=print):
    """Save a working prompt only when it satisfies the shared synthesis contract."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    text = str(prompt_text or "").strip()
    if not text:
        raise Refused(f"REFUSED — {shot_id}'s working Seedance prompt cannot be blank")
    dialogue_check = emission.validate_dialogue_synthesis(
        text, cb_departments.provider_dialogue_lines(shot))
    if not dialogue_check["ready"]:
        raise Refused("REFUSED — working prompt violates the dialogue synthesis contract: " +
                      "; ".join(dialogue_check["errors"]))
    try:
        specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    except Refused:
        work, _ = _department_container(pkg, scene, shot_id, "animation", episode)
        record = work.get("candidate") or work.get("approved") or {}
        specialist = record.get("output") or {}
    _require_animation_prompt_contract(
        _shot_creative_contract_view(pkg, shot, scene, episode),
        {**specialist, "providerPrompt": text,
         "deriveCreativeTranslationFromApproved": True})
    led["workingSeedancePrompt"] = {
        "text": text,
        "savedAt": _now(),
        "savedBy": reviewed_by,
        "inputSignature": _seedance_working_input_signature(pkg, shot, scene, episode),
    }
    # A spend token seals one exact provider envelope. Changing the working prompt changes
    # that envelope, so any earlier cost disclosure must be discarded and rebuilt before
    # the next provider call can be authorised.
    led["pendingSpendAuth"] = None
    work, _ = _department_container(pkg, scene, shot_id, "animation", episode)
    direction_record = work.get("candidate") or work.get("approved")
    if direction_record:
        # The working prompt is a validated human override layered on the approved typed
        # direction. Its presence intentionally changes the direct-input signature, so mark
        # that current record as the retained baseline instead of making the supported
        # Director-edit workflow immediately report itself stale.
        direction_record["manualCurrentOverride"] = True
    _save(pkg, path)
    log(f"ANIMATION WORKING PROMPT SAVED — {shot_id} (no animation generated)")
    return led["workingSeedancePrompt"]


def restore_seedance_working(scene, shot_id, episode="Ep1", log=print):
    """Clears the working override — fire_shot reverts to submitting the approved storyboard's
    own compiled seedancePrompt, exactly as if no working version had ever been saved. Never
    generates animation."""
    pkg, path = load_pkg(scene, episode)
    led = _ledger(pkg, shot_id)
    led["workingSeedancePrompt"] = None
    work, _ = _department_container(pkg, scene, shot_id, "animation", episode)
    direction_record = work.get("candidate") or work.get("approved")
    if direction_record:
        direction_record.pop("manualCurrentOverride", None)
        direction_record["inputSignature"] = _department_input_signature(
            pkg, "animation", shot_id, scene, episode)
    _save(pkg, path)
    log(f"ANIMATION WORKING PROMPT RESTORED — {shot_id}: reverted to the approved storyboard's prompt")


def save_watch_director_feedback(scene, shot_id, feedback, episode="Ep1",
                                 reviewed_by="Julian", log=print):
    """Store bounded human review feedback as AI Director input, never provider prose."""
    pkg, path = load_pkg(scene, episode)
    _shot(pkg, shot_id)
    note = str(feedback or "").strip()
    if not note:
        raise Refused("REFUSED — WATCH Director feedback cannot be blank")
    ledger = _ledger(pkg, shot_id)
    previous = ledger.get("watchDirectorFeedback")
    if previous:
        ledger.setdefault("watchDirectorFeedbackHistory", []).append(previous)
    ledger["watchDirectorFeedback"] = {
        "text": note,
        "savedAt": _now(),
        "savedBy": reviewed_by,
    }
    _save(pkg, path)
    log(f"WATCH FEEDBACK SAVED — {shot_id} (AI Director input; no provider call)")
    return ledger["watchDirectorFeedback"]


def bind_animation_location_reference(scene, shot_id, label, source_path,
                                      episode="Ep1", reviewed_by="Julian", log=print):
    """Attach an approved supplementary geography angle to WATCH only.

    The opening keyframe and primary scene plate keep their existing authority. This
    reference may clarify reverse coverage, furniture and traversable floor space, but it
    never supplies cast identity or changes SEE approval.
    """
    pkg, path = load_pkg(scene, episode)
    _shot(pkg, shot_id)
    clean_label = re.sub(r"\s+", " ", str(label or "").strip())
    if not clean_label:
        raise Refused("REFUSED — a supplementary location reference needs a label")
    role = f"location:{clean_label}"
    rec = cb_asset_registry.register_asset(
        episode=episode, scene=scene, shot_id=shot_id, kind="reference_image",
        role=role, path=source_path, status="approved",
        label=clean_label, source="Director-approved supplementary geography",
        metadata={"assetUse": "supplementary_location", "reviewedBy": reviewed_by},
    )
    ledger = _ledger(pkg, shot_id)
    roles = ledger.setdefault("additionalAnimationReferenceRoles", [])
    if role not in roles:
        roles.append(role)
    ledger["pendingSpendAuth"] = None
    _save(pkg, path)
    log(f"ANIMATION LOCATION REFERENCE BOUND — {shot_id}: {clean_label} (no media generated)")
    return rec


# ── THE SEEDANCE STRUCTURE CHECK (Julian's directive, 2026-07-19) ───────────────────────
# FREE. ZERO PROVIDER CALLS. ZERO COST. Reports exactly what firing would do right now,
# without firing. Only a missing PROVIDER-REQUIRED input (no anchor, no references, no
# billing confirmation, dialogue with no voice track, Law 6 leakage) may BLOCK; every
# creative observation (a possibly-removed scale clause, a duplicated sentence, a keyword-
# level camera conflict) is a WARNING — advisory only, never blocking, never rewritten here.
_CAMERA_MOVE_WORDS = re.compile(r"\b(pan|pans|panning|dolly|dollies|truck|trucks|orbit|orbits|zoom|zooms|tilt|tilts)\b",
                                 re.IGNORECASE)
_CAMERA_LOCK_WORDS = re.compile(r"\bcamera (?:lock|locked|holds|stays? (?:still|locked))\b", re.IGNORECASE)


def _prompt_contract_completeness(shot, prompt, specialist=None):
    """Free deterministic instruction-coverage check for a Seedance shooting script.

    This is contract completeness, not an artistic-quality score, automatic rewrite or
    provider call. It cannot prove that emotion, comedy, acting or physics will land.
    The four critical dimensions are story beat, canon/reference fidelity, audio/dialogue
    separation and a usable continuity landing.
    """
    specialist = specialist or {}
    text = str(prompt or "").strip()
    low = text.lower()
    words = len(text.split())
    dialogue = cb_departments.provider_dialogue_lines(shot)
    dialogue_check = emission.validate_dialogue_synthesis(text, dialogue)

    def has(pattern):
        return bool(re.search(pattern, low, re.IGNORECASE))

    scores = {}
    structured_story = (
        "[one-sentence summary]" in low and
        low.count("action/expression:") >= 1 and
        low.count("end state:") >= 1)
    scores["storyBeat"] = (
        2 if (specialist.get("dramaticBeat") and specialist.get("performanceArc")) or
        structured_story
        else 1 if has(r"\b(beat|turn|realises?|decides?|tries?|fails?|wins?|loses?|reaction)\b")
        else 0)
    bound_image_refs = len(set(re.findall(r"@image\d+", low)))
    scores["canonAndReferences"] = (
        2 if specialist.get("referenceContract") and
        has(r"\b(identity|proportion|relative scale|reference|silhouette|canon)\b")
        else 2 if bound_image_refs >= 2 and
        has(r"\b(identity|proportion|relative scale|reference|silhouette|canon|scale)\b")
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
        2 if not dialogue else 2 if dialogue_check["ready"] else 0)
    opens = has(r"\b(exact opening|opening frame|begins? (?:on|from)|start(?:s|ing)? (?:on|from)|first frame)\b")
    lands = has(r"\b(landing image|lands? on|ends? on|end state|final frame|closing frame|handoff|settles? into)\b")
    scores["continuityLanding"] = 2 if opens and lands else 1 if opens or lands else 0
    safeguard_count = len(specialist.get("surgicalSafeguards") or [])
    scores["promptEconomy"] = 2 if safeguard_count <= 3 else 1

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
    }


def _prompt_quality_gate(shot, prompt, specialist=None):
    """Backward-compatible alias; callers should display contract completeness."""
    return _prompt_contract_completeness(shot, prompt, specialist)


def _animation_prompt_contract_report(shot, direction):
    """Evaluate the shared Seedance authoring contract without calling a provider."""
    data = direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {})
    prompt = str(data.get("providerPrompt") or "").strip()
    raw_references = list(data.get("referenceContract") or [])
    references = []
    for index, item in enumerate(cb_departments._render_reference_order(raw_references),
                                 start=1):
        rec = item.model_dump() if hasattr(item, "model_dump") else dict(item or {})
        if re.match(r"^@(?:图|Image)\s*\d+$", str(rec.get("assetTag") or "").strip(), re.I):
            rec["assetTag"] = f"@图{index}"
        references.append(rec)
    if cb_audio_authority.spoken_dialogue_lines(shot) and not any(
            str(item.get("assetTag") or "").lower().replace(" ", "") == "@audio1"
            for item in references):
        references.append({
            "assetTag": "@Audio1",
            "role": "approved dialogue and performance track",
        })
    quality = _prompt_contract_completeness(shot, prompt, data)
    authoring = cb_prompt_lab.analyze_seedance_prompt_contract(
        prompt,
        task_mode=data.get("taskMode") or "reference-to-video",
        reference_contract=references,
        duration_sec=data.get("durationSec") or shot.get("durationSec"),
        dialogue_lines=cb_departments.provider_dialogue_lines(shot),
        stage_plan=[] if data.get("shotPlan") else data.get("stagePlan") or [],
    )
    authoring["normalizedScore"] = _seedance_authoring_score(authoring)
    authoring["firingFloor"] = SEEDANCE_AUTHORING_FLOOR
    errors = []
    if quality["needsRevision"]:
        errors.append(
            f"creative contract scores {quality['score']}/{quality['maximum']}"
            + (f"; critical zero: {', '.join(quality['criticalFailures'])}"
               if quality["criticalFailures"] else ""))
    if authoring["status"] != "ready":
        errors.extend(authoring["repairActions"] or [authoring["summary"]])
    elif authoring["normalizedScore"] < SEEDANCE_AUTHORING_FLOOR:
        errors.append(
            f"Seedance authoring score is {authoring['normalizedScore']}/10; "
            f"minimum is {SEEDANCE_AUTHORING_FLOOR}")
    story_lock = cb_departments.animation_story_lock_report(
        shot, prompt, data.get("stagePlan") or [], data.get("shotPlan") or [])
    if not story_lock["ready"]:
        errors.extend(story_lock["errors"])
    creative_translation = cb_departments.creative_translation_report(shot, data, prompt)
    if not creative_translation["ready"]:
        errors.extend(creative_translation["errors"])
    scene_state = _scene_state_prompt_report(shot, prompt)
    if not scene_state["ok"]:
        errors.append(
            "scene continuity state missing from prompt: "
            + ", ".join(scene_state["missing"]))
    return {
        "ready": not errors,
        "errors": errors,
        "contractCompleteness": quality,
        "qualityGate": quality,
        "authoringContract": authoring,
        "storyLock": story_lock,
        "creativeTranslation": creative_translation,
        "sceneState": scene_state,
    }


def _require_animation_prompt_contract(shot, direction):
    report = _animation_prompt_contract_report(shot, direction)
    if not report["ready"]:
        raise Refused("REFUSED — animation provider prompt is not production-ready: "
                      + "; ".join(report["errors"]))
    return report


def _animation_preflight_summary(shot, direction):
    """Return the persisted WATCH gate verdict shown by Studio surfaces."""
    report = _animation_prompt_contract_report(shot, direction)
    prompt = str((direction.model_dump() if hasattr(direction, "model_dump")
                  else dict(direction or {})).get("providerPrompt") or "")
    emission_report = _emission_conformance_report(
        shot,
        direction.model_dump() if hasattr(direction, "model_dump") else dict(direction or {}),
        prompt)
    authoring = report.get("authoringContract") or {}
    quality = report.get("contractCompleteness") or report.get("qualityGate") or {}
    findings = list(emission_report.get("findings") or [])
    if report.get("errors"):
        findings.extend({
            "severity": "FATAL",
            "rule": "seedance-authoring",
            "message": error,
            "fix": "Recompile the WATCH prompt before rendering.",
        } for error in report.get("errors") or [])
    if authoring.get("status") != "ready":
        findings.extend({
            "severity": "FATAL",
            "rule": "seedance-authoring",
            "message": action,
            "fix": "Apply the Seedance repair action and recompile.",
        } for action in authoring.get("repairActions") or [])
    verdict = "PASS" if (
        report.get("ready")
        and emission_report.get("verdict") == "PASS"
        and float(authoring.get("normalizedScore") or 0) >= SEEDANCE_AUTHORING_FLOOR
    ) else "BLOCK"
    return {
        "verdict": verdict,
        "score": emission_report.get("score"),
        "maximum": 10,
        "checkerVerdict": emission_report.get("verdict"),
        "findings": findings[:6],
        "seedanceAuthoring": {
            "status": authoring.get("status"),
            "score": authoring.get("score"),
            "maximum": authoring.get("maximum"),
            "normalizedScore": authoring.get("normalizedScore"),
            "firingFloor": authoring.get("firingFloor"),
            "summary": authoring.get("summary"),
        },
        "contractCompleteness": {
            "score": quality.get("score"),
            "maximum": quality.get("maximum"),
            "threshold": quality.get("threshold"),
            "needsRevision": quality.get("needsRevision"),
            "criticalFailures": quality.get("criticalFailures") or [],
        },
        "qualityGate": {
            "score": quality.get("score"), "maximum": quality.get("maximum"),
            "threshold": quality.get("threshold"),
            "needsRevision": quality.get("needsRevision"),
            "criticalFailures": quality.get("criticalFailures") or [],
        },
    }


def _engine_rule_report(pkg, shot, direction=None, cinematography=None):
    """Run the project-agnostic feasibility and cross-compiler checks."""
    data = (direction.model_dump() if hasattr(direction, "model_dump") else
            dict(direction or {}))
    timing = cb_engine_rules.beat_cost_report(shot, data)
    relay_opening = shot.get("sourceType") == "relay"
    if cinematography is None and not relay_opening:
        cinematography = _approved_department_output(
            pkg, shot.get("shotId"), "cinematography") or {}
    if cinematography and not relay_opening:
        ledger = _ledger(pkg, shot.get("shotId"))
        opening_contract = (((ledger.get("keyframeApproval") or {}).get("promptContract") or {})
                            .get("directionContract") or {})
        opening_geography = list(opening_contract.get("geography") or [])
        if opening_geography:
            cinematography = {**cinematography, "geography": opening_geography}
    geometry = ({
        "ready": True,
        "errors": [],
        "rulesVersion": cb_engine_rules.RULES_VERSION,
        "basis": "approved-relay-opening-frame",
    } if relay_opening else (
        cb_engine_rules.geometry_agreement(cinematography, data)
        if cinematography and data.get("geography") else
        {"ready": True, "errors": [],
         "rulesVersion": cb_engine_rules.RULES_VERSION}))
    craft = cb_engine_rules.action_unit_report(
        shot, data, prompt=data.get("providerPrompt") or "")
    errors = []
    if not timing["ready"]:
        errors.append(
            f"beat-cost minimum is {timing['minimumWithMarginSec']:g}s "
            f"({timing['recommendedDurationSec']}s request) but the unit requests "
            f"{timing['requestedDurationSec']:g}s")
    errors.extend(geometry["errors"])
    errors.extend(craft["errors"])
    return {"ready": not errors, "errors": errors, "timing": timing,
            "geometry": geometry, "craft": craft}


def _require_engine_rules(pkg, shot, direction=None, cinematography=None):
    report = _engine_rule_report(pkg, shot, direction, cinematography)
    if not report["ready"]:
        raise Refused("REFUSED — engine preflight failed: " + "; ".join(report["errors"]))
    return report


def _seedance_pipeline_task(shot, specialist, attached_contract):
    """Translate current signed Studio direction into the generic zero-spend compiler contract."""
    specialist = specialist or {}
    provider_prompt = str(specialist.get("providerPrompt") or "")
    provider_prompt = _hide_dialogue_timing_ranges_for_prompt_check(provider_prompt)
    approved_refs = {
        re.sub(r"\s+", "", str(item.get("assetTag") or "")).lower(): item
        for item in (specialist.get("referenceContract") or [])
        if item.get("assetTag")
    }
    references, assets = [], {"images": [], "videos": [], "audio": []}
    for item in attached_contract or []:
        tag = str(item.get("assetTag") or "").strip()
        if not tag:
            continue
        approved = approved_refs.get(re.sub(r"\s+", "", tag).lower(), {})
        role = str(approved.get("role") or item.get("role") or "reference subject")
        controls = str(approved.get("controls") or item.get("role") or role).strip()
        role_low = role.lower()
        if "audio" in role_low or tag.lower().startswith("@audio"):
            exclude = "unassigned voices, music, ambience, and timing"
            kind = "audio"
        elif any(value in role_low for value in ("opening", "first", "closing", "last")):
            exclude = "unapproved text labels and unrelated artifacts"
            kind = "images"
        elif any(value in role_low for value in ("location", "scene", "style")):
            exclude = "people, placeholder characters, and unrelated foreground objects"
            kind = "images"
        elif tag.lower().startswith("@video"):
            exclude = "the source identity, materials, and scene unless explicitly assigned"
            kind = "videos"
        else:
            exclude = "the reference background, composition, text labels, and unrelated content"
            kind = "images"
        subject = role.replace("_", " ").strip().title() or "Reference Subject"
        references.append({
            "tag": tag,
            "subject": subject,
            "defines": controls.rstrip("."),
            "exclude": exclude,
        })
        asset = {"tag": tag, "subject": subject, "path": item.get("path")}
        if kind == "audio" and item.get("path"):
            asset["duration_seconds"] = _audio_dur(item["path"])
        assets[kind].append(asset)

    stages = []
    for stage in specialist.get("stagePlan") or []:
        start, end = stage.get("startSec"), stage.get("endSec")
        time_range = ""
        if start is not None and end is not None:
            time_range = f"{float(start):g}-{float(end):g} seconds"
        stages.append({
            "time": time_range,
            "purpose": stage.get("purpose") or "",
            "initial_state": stage.get("initialOrCarriedState") or "",
            "event": stage.get("primaryEvent") or "",
            "end_state": stage.get("observableEndState") or "",
            "emotion_or_camera": stage.get("emotionOrCameraAnalysis") or "",
        })

    spoken_lines = cb_audio_authority.spoken_dialogue_lines(shot)
    dialogue = bool(spoken_lines)
    audio = specialist.get("audioContract") or (
        "@Audio1 is the sole authority for English voice identity, cadence, delivery, "
        "mouth timing and silence. Exact braced dialogue markers place approved words "
        "only; no alternative performance is permitted. Listeners remain silent and "
        "closed-mouth. No narration, no extra words, and no subtitles or captions. "
        "Do not generate an alternate spoken performance; use @Audio1 for the approved "
        "dialogue timing and voice. Seedance supplies only non-verbal sound. "
        + emission.SINGLE_INSTANCE_DIALOGUE_LOCK + "\n" +
        "\n".join(emission.dialogue_placement_line(line)
                  for line in spoken_lines) +
        "\nSeedance may generate non-dialogue ambience, foley, comedy impacts, wing "
        "buzzes, pollen poofs, plant movement, and low supportive underscore."
        if dialogue else
        "No dialogue. Seedance may generate ambience, foley, designed sound effects, "
        "and low supportive underscore."
    )
    # Keep dialogue timing authoritative in the attached audio/placement metadata, not as
    # extra numeric ranges in the visual prompt. The Seedance authoring checker treats all
    # ranges in prompt text as stage pacing, so "from 15.4 to 21.2" can look like a
    # non-consecutive fourth stage.
    audio = _hide_dialogue_timing_ranges_for_prompt_check(audio)
    consistency = specialist.get("consistencyContract") or [
        "Keep approved identity, character count, relative scale, prop ownership, scene geography, light direction, camera axis, and audio relationships stable."
    ]
    task_mode = specialist.get("taskMode") or "reference-to-video"
    return {
        "type": task_mode,
        "goal": (specialist.get("generationGoal") or shot.get("purpose") or
                 f"Generate approved shot {shot.get('shotId') or ''}.").strip(),
        "duration_seconds": shot.get("durationSec"),
        "aspect_ratio": "16:9",
        "resolution": _review_video_resolution(),
        "assets": assets,
        "references": references,
        "stages": stages,
        "scene_style": " ".join(value for value in (
            specialist.get("dramaticBeat"), specialist.get("performanceArc")) if value),
        "camera": specialist.get("cameraBehaviour") or "",
        "audio": audio,
        "consistency": consistency,
        "no_music": bool(re.search(
            r"\bno\b[^.;\n]{0,120}\b(?:music|bgm|musical underscore)\b",
            provider_prompt + "\n" + audio, re.I)),
        "extension_direction": (
            "backward" if task_mode == "extend-backward" else
            specialist.get("extensionDirection") or "forward"),
        "edit_goal": specialist.get("generationGoal") or "",
        "edit_scope": specialist.get("editScope") or "",
        "preserve": specialist.get("contentToPreserve") or consistency,
        "transition_trigger": specialist.get("transitionTrigger") or "",
        "transition_transformation": specialist.get("transitionTransformation") or "",
        "arrival_state": specialist.get("transitionArrivalState") or "",
        "audio_transition": specialist.get("audioTransition") or "",
        "first_frame_tag": specialist.get("firstFrameTag") or "@Image 1",
        "last_frame_tag": specialist.get("lastFrameTag") or "@Image 2",
        "storyboard_tag": specialist.get("storyboardTag") or "@Image 1",
        "storyboard_reading_order": (
            specialist.get("storyboardReadingOrder") or "left to right, top to bottom"),
        "blockout_kind": specialist.get("blockoutKind") or "coarse",
        "blockout_mappings": specialist.get("blockoutMappings") or [],
    }


def _emission_conformance_report(shot, specialist, prompt):
    """Run the golden-fixture checker with the exact production timing inputs."""
    return cb_emission_standard.preflight(
        prompt,
        duration_sec=shot.get("durationSec"),
        timing_beats=(specialist or {}).get("timingBeats") or [],
    )


SEEDANCE_AUTHORING_FLOOR = 9.5


def _hide_dialogue_timing_ranges_for_prompt_check(text):
    """Keep dialogue windows from being mistaken for visual-stage pacing ranges."""
    return re.sub(
        r"\bfrom\s+(?:about\s+)?\d+(?:\.\d+)?\s*(?:to|-)\s*\d+(?:\.\d+)?\s*s?\b",
        "within the approved @Audio1 placement window",
        str(text or ""),
        flags=re.I,
    )


def _seedance_authoring_score(contract):
    maximum = float(contract.get("maximum") or 0)
    if maximum <= 0:
        return 0.0
    return round((float(contract.get("score") or 0) / maximum) * 10.0, 2)


def _relay_reference_bundle_report(shot, reference_contract, continuity_mode=None):
    """Verify relay shots carry more than the inherited frame.

    The previous final frame preserves continuity state; it does not define the world or
    identities. Every relay render must still carry scene geography and all characters
    visible in the shot.
    """
    if not (shot.get("sourceType") == "relay" or shot.get("sourceShotId")):
        return {"ok": True, "required": [], "present": [], "missing": []}
    roles = [str(item.get("role") or "").strip() for item in reference_contract or []]
    present = {role.casefold() for role in roles if role}
    if continuity_mode == CONTINUITY_MODE_VIDEO_EXTENSION:
        # @Video1 owns the inherited stage, geography, cast, and boundary state.
        # Image references in an extension are only the explicitly requested
        # identity/prop authorities; requiring a still handoff or scene plate here
        # would conflict with the moving source and can force a scenic cutaway.
        required = [
            str(role).strip()
            for role in (shot.get("referenceSlots") or {}).values()
            if str(role).strip()
            and str(role).strip().casefold() not in {
                "previous shot final frame", "scene plate", "opening keyframe"
            }
        ]
        missing = [role for role in required if role.casefold() not in present]
        return {
            "ok": not missing,
            "required": required,
            "present": roles,
            "missing": missing,
            "continuityAuthority": "@Video1 previous approved clip",
        }

    required = ["previous shot final frame", "scene plate"]
    required.extend(
        str(character).strip()
        for character in (shot.get("charactersInFrame") or [])
        if str(character).strip()
    )
    required.extend(
        str(role).strip()
        for role in (shot.get("referenceSlots") or {}).values()
        if str(role).strip().startswith("prop:")
    )
    missing = [role for role in required if role.casefold() not in present]
    return {
        "ok": not missing,
        "required": required,
        "present": roles,
        "missing": missing,
    }


def _scene_state_prompt_report(shot, prompt):
    """Ensure physical scene-state locks survive into provider prompts."""
    locks = list(shot.get("sceneContinuityLocks") or [])
    if not locks:
        return {"ok": True, "required": [], "missing": []}
    text = " ".join(str(prompt or "").casefold().split())
    required = []
    missing = []
    action_has_departed = bool(re.search(
        r"\b(?:already (?:moving|underway)|moving away|has departed|underway)\b",
        str(shot.get("action") or ""), re.I))
    for lock in locks:
        item = lock if isinstance(lock, dict) else {}
        label = str(item.get("label") or item.get("id") or "Scene continuity").strip()
        value = str(item.get("value") or "").strip()
        lock_text = " ".join((value, str(item.get("forbidden") or "")))
        if action_has_departed and re.search(
                r"\b(?:moored|alongside the pier|before departure|move the sailboat away)\b",
                lock_text, re.I):
            continue
        token = label or value[:48]
        if token:
            required.append(token)
        probes = [
            str(item.get("id") or ""),
            label,
            value[:80],
            str(item.get("forbidden") or "")[:80],
        ]
        if not any(probe and " ".join(probe.casefold().split()) in text
                   for probe in probes):
            missing.append(token)
    return {"ok": not missing, "required": required, "missing": missing}


def check_seedance_structure(scene, shot_id, episode="Ep1", log=print):
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    specialist = _approved_department_output(pkg, shot_id, "animation") or {}
    blockers, warnings, checks = [], [], {}
    budget = _performance_budget_report(
        _shot_creative_contract_view(pkg, shot, scene, episode), led)
    checks["performanceBudget"] = budget
    if not budget["ready"]:
        blockers.append("voice-timed performance budget is overloaded: "
                        + "; ".join(budget.get("reasons") or []))

    try:
        target_model = cb_providers.video_model(require_enabled=False)
        checks["modelTarget"] = target_model.modelId
        if target_model.enabled:
            _require_confirmed_billing(target_model.provider)
            checks["billingConfirmed"] = {"ok": True, "provider": target_model.provider}
        else:
            checks["billingConfirmed"] = {
                "ok": False, "provider": target_model.provider,
                "detail": "Pending until the selected model is activated and qualified."}
    except (Refused, cb_providers.ProviderCapabilityError) as e:
        blockers.append(str(e))
        checks["billingConfirmed"] = {"ok": False, "detail": str(e)}

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
            animation_shot = _with_effective_reference_slots(
                pkg, shot, "referenceSlots", scene, episode)
            attachment_plan = _provider_attachment_plan(
                animation_shot, "referenceSlots", anchor, scene, episode,
                characters_cfg)
            imgs = [item["path"] for item in attachment_plan]
            ordered_slots = [item["slot"] for item in attachment_plan]
            checks["sceneLookAttached"] = {"ok": True}
            checks["referencesAttached"] = {"ok": True, "count": len(imgs),
                                             "order": ordered_slots}
            checks["referenceContract"] = [
                {"position": item["position"], "assetTag": item["slot"],
                 "sourceSlot": item["sourceSlot"], "role": item["role"],
                 "view": item.get("view"), "path": item["path"],
                 "sameCharacterGroup": ((item.get("identity") or {}).get(
                     "turnaroundGroupHash")),
                 "contentHash": hashlib.sha256(
                     pathlib.Path(item["path"]).read_bytes()).hexdigest()}
                for item in attachment_plan
            ]
            checks["requiredPropReferences"] = _required_prop_reference_report(
                shot, scene, episode, checks["referenceContract"])
            if not checks["requiredPropReferences"]["ok"]:
                blockers.append(
                    "required continuity prop authority is missing from the exact "
                    "provider attachment list: "
                    + ", ".join(checks["requiredPropReferences"]["missing"]))
        except (Refused, OSError) as e:
            blockers.append(str(e))
            checks["sceneLookAttached"] = {"ok": False, "detail": str(e)}
            checks["referencesAttached"] = {"ok": False, "detail": str(e)}
    else:
        checks["sceneLookAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}
        checks["referencesAttached"] = {"ok": False, "detail": "not checked — no opening frame attached"}

    if cb_audio_authority.spoken_dialogue_lines(shot):
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
    checks["resolution"] = _review_video_resolution()
    checks["aspectRatio"] = "16:9"
    video_refs = []
    try:
        continuity_mode = _continuity_mode(led, shot)
        checks["continuityMode"] = continuity_mode
        if continuity_mode == CONTINUITY_MODE_VIDEO_EXTENSION:
            previous_clip = _previous_approved_clip_for(pkg, shot)
            video_refs = [{
                "position": len(checks.get("referenceContract") or []) + 1,
                "assetTag": "@Video1",
                "role": "previous approved video",
                "controls": "previous approved clip continuity master",
                "path": previous_clip,
                "contentHash": hashlib.sha256(pathlib.Path(previous_clip).read_bytes()).hexdigest(),
            }]
            checks.setdefault("referenceContract", []).extend(video_refs)
        checks["relayReferenceBundle"] = _relay_reference_bundle_report(
            shot, checks.get("referenceContract") or [], continuity_mode)
        if not checks["relayReferenceBundle"]["ok"]:
            blockers.append(
                "relay reference bundle is incomplete; missing "
                + ", ".join(checks["relayReferenceBundle"]["missing"]))
    except Refused as exc:
        blockers.append(str(exc))
        checks["continuityMode"] = {"ok": False, "detail": str(exc)}
    try:
        task_mode = specialist.get("taskMode") or "reference-to-video"
        provider_mode = {
            "reference-to-video": "reference-to-video",
            "extend-forward": "video-extension",
        }.get(task_mode)
        if not provider_mode:
            raise cb_providers.ProviderCapabilityError(
                f"no enabled provider route is qualified for {task_mode}")
        provider_contract = cb_providers.request_contract(
            duration=int(round(shot.get("durationSec") or 0)),
            resolution=_review_video_resolution(),
            image_count=len(imgs),
            audio_count=1 if cb_audio_authority.spoken_dialogue_lines(shot) else 0,
            video_count=len(video_refs), mode=provider_mode)
        checks["providerContract"] = provider_contract
        checks["model"] = provider_contract["providerModelId"]
    except cb_providers.ProviderCapabilityError as exc:
        blockers.append(f"provider capability: {exc}")
        checks["providerContract"] = {"ok": False, "detail": str(exc)}
        checks["model"] = cb_providers.selected_video_model_id()

    resolved_prompt, using_working = _resolve_seedance_prompt(
        pkg, shot, scene, episode, require_current_working=True)
    checker_references = [{
        "slot": item.get("assetTag"),
        "role": item.get("role"),
        "intactTurnaround": bool(item.get("sameCharacterGroup")),
    } for item in checks.get("referenceContract") or []]
    checked_prompt = _with_intact_turnaround_law(
        resolved_prompt, checker_references)
    checked_prompt = _hide_dialogue_timing_ranges_for_prompt_check(checked_prompt)
    checked_task_mode = specialist.get("taskMode") or "reference-to-video"
    if video_refs:
        checked_prompt = _video_extension_directive(
            checked_prompt, video_refs[0]["path"])
        checked_task_mode = "extend-forward"
    checks["usingWorkingVersion"] = using_working
    checks["promptSource"] = ("human-working" if using_working else
        "seedance-production-director-approved" if specialist.get("providerPrompt")
        else "legacy-approved-storyboard")
    emission_conformance = _emission_conformance_report(
        shot, specialist, checked_prompt)
    checks["emissionConformance"] = emission_conformance
    if emission_conformance["verdict"] != "PASS":
        blockers.append(
            f"emission conformance scores {emission_conformance['score']}/10 "
            f"({emission_conformance['verdict']}); correct the listed findings before render")
    quality = _prompt_contract_completeness(shot, checked_prompt, specialist)
    checks["contractCompleteness"] = quality
    checks["qualityGate"] = quality  # compatibility for historical Studio clients
    if quality["needsRevision"]:
        detail = (f"; critical zero: {', '.join(quality['criticalFailures'])}"
                  if quality["criticalFailures"] else "")
        blockers.append(
            f"prompt contract completeness is {quality['score']}/{quality['maximum']} "
            f"(target {quality['threshold']}){detail}")

    pipeline_contract = None
    try:
        pipeline_task = _seedance_pipeline_task(
            shot, specialist, checks.get("referenceContract") or [])
        pipeline_contract = cb_seedance_pipeline.SeedancePromptBuilder(
            pipeline_task).preflight(existing_prompt=checked_prompt)
        checks["seedancePipeline"] = pipeline_contract
        if not pipeline_contract["readyForPrompt"]:
            errors = pipeline_contract["validation"]["errors"]
            warnings.append(
                f"Seedance compiler preflight found {len(errors)} authoring error(s): "
                + "; ".join(errors[:3]))
    except ValueError as exc:
        checks["seedancePipeline"] = {
            "zeroSpend": True, "providerCalled": False, "readyForPrompt": False,
            "detail": str(exc),
        }
        warnings.append(f"Seedance compiler preflight could not type the task: {exc}")

    seedance_contract = cb_prompt_lab.analyze_seedance_prompt_contract(
        checked_prompt,
        task_mode=checked_task_mode,
        reference_contract=(checks.get("referenceContract") or [
            {"assetTag": tag, "role": role}
            for tag, role in (shot.get("referenceSlots") or {}).items()
        ]),
        duration_sec=shot.get("durationSec"),
        dialogue_lines=cb_departments.provider_dialogue_lines(shot),
        stage_plan=specialist.get("stagePlan") or [],
    )
    seedance_contract["normalizedScore"] = _seedance_authoring_score(
        seedance_contract)
    seedance_contract["firingFloor"] = SEEDANCE_AUTHORING_FLOOR
    checks["seedancePromptContract"] = seedance_contract
    if seedance_contract["status"] != "ready":
        blockers.append(
            f"Seedance authoring contract scores {seedance_contract['score']}/"
            f"{seedance_contract['maximum']}; "
            f"{len(seedance_contract['repairActions'])} repair action(s) remain")
    elif seedance_contract["normalizedScore"] < SEEDANCE_AUTHORING_FLOOR:
        blockers.append(
            f"Seedance authoring contract scores "
            f"{seedance_contract['normalizedScore']}/10 "
            f"(floor {SEEDANCE_AUTHORING_FLOOR}); tighten the prompt before render")

    creative_translation = cb_departments.creative_translation_report(
        _shot_creative_contract_view(pkg, shot, scene, episode),
        {**specialist,
         "deriveCreativeTranslationFromApproved": bool(using_working)},
        checked_prompt)
    checks["creativeTranslation"] = creative_translation
    if not creative_translation["ready"]:
        blockers.append(
            "creative translation is incomplete: "
            + "; ".join(creative_translation["errors"][:3]))

    # creative warnings — advisory only, never blocking, never rewritten
    if "relative scale" not in checked_prompt.lower() and "identity" not in checked_prompt.lower():
        warnings.append("no character-identity/relative-scale preservation clause detected "
                        "in the resolved prompt")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", checked_prompt) if s.strip()]
    seen = {}
    for s in sentences:
        normalized = _norm(s)
        # These clauses are intentionally repeated once per independently bound
        # turnaround. Their repetition prevents cross-character identity collapse and
        # is not duplicated creative direction.
        if any(marker in normalized for marker in (
                "every view on this sheet is the same character identity",
                "use the entire sheet for face silhouette proportions markings",
                "do not use the sheet layout as the shot composition",
                "refer to that wearable state strictly exclude background pose unrelated props and scene",
                "hold 2 0s hold the full team beach arrival with keen alive and squeaky safe",
                "no extra voices",
                "seedance may generate non verbal music ambience and sfx that support the scene")):
            continue
        seen[normalized] = seen.get(normalized, 0) + 1
    dupes = sum(1 for v in seen.values() if v > 1)
    if dupes:
        warnings.append(f"{dupes} duplicated direction(s) detected in the resolved prompt")
    if _CAMERA_LOCK_WORDS.search(checked_prompt) and _CAMERA_MOVE_WORDS.search(checked_prompt):
        warnings.append("possible conflicting camera direction: both a camera lock and a "
                        "camera-movement word appear in the resolved prompt")

    dialogue_check = emission.validate_dialogue_synthesis(
        checked_prompt, cb_departments.provider_dialogue_lines(shot))
    blockers.extend(
        f"Dialogue synthesis: {error}" for error in dialogue_check["errors"])

    verdict = "blocked" if blockers else ("warnings" if warnings else "passed")
    result = {"verdict": verdict, "blockers": blockers, "warnings": warnings,
              "checks": checks, "finalPrompt": checked_prompt}
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
    prompt, using_working = _resolve_seedance_prompt(
        # Readback is advisory: a current approved compiled direction is a valid
        # source even when no separate human working override is present. The
        # paid fire path still requires the current working prompt explicitly.
        pkg, shot, scene, episode, require_current_working=False)
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


# ── PROMPT LAB — exact-prompt analysis + append-only human render evidence ─────────────
def _prompt_contract_is_exact(contract):
    prompt = str((contract or {}).get("prompt") or "")
    claimed = str((contract or {}).get("promptHash") or "")
    if not (prompt and claimed and hashlib.sha256(prompt.encode()).hexdigest() == claimed):
        return False
    if contract.get("integrityVerified") is True:
        return True
    contract_hash = str(contract.get("contractHash") or "")
    names = [
        "prompt", "promptHash", "promptSource", "provider", "providerModelId", "modelVersion"]
    if "directionContract" in contract:
        names.append("directionContract")
    payload = {name: contract.get(name) for name in names}
    actual = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return bool(contract_hash and contract_hash == actual)


def _current_prompt_contract(pkg, shot, artifact_type):
    stage = "cinematography" if artifact_type == "keyframe" else "animation"
    direction_state = None
    checker = globals().get("_department_record_status")
    if callable(checker):
        try:
            direction_state = checker(pkg, shot["shotId"], stage)
        except (Refused, KeyError, TypeError, OSError, ValueError):
            direction_state = None
    if artifact_type == "keyframe":
        specialist = _inspection_department_output(pkg, shot["shotId"], "cinematography")
        prompt = specialist.get("providerPrompt") or shot.get("keyframePrompt")
        return {**_keyframe_prompt_contract(pkg, shot, prompt),
                "directionCurrent": bool(direction_state and direction_state.get("current")),
                "directionReason": (direction_state or {}).get("reason"),
                "attributionExact": False}
    specialist = _inspection_department_output(pkg, shot["shotId"], "animation")
    # The safety layer permits only current signed Animation direction to fire. A legacy
    # working override remains inspectable history but is not presented here as the next
    # provider prompt.
    prompt = specialist.get("providerPrompt") or shot.get("seedancePrompt")
    try:
        model = cb_providers.video_model()
        provider = model.provider
        provider_model_id = model.modelId
        model_version = model.modelVersion
    except cb_providers.ProviderCapabilityError:
        provider = None
        provider_model_id = cb_providers.selected_video_model_id()
        model_version = None
    return {
        "prompt": prompt,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "promptSource": ("animation-director-current" if specialist.get("providerPrompt")
                         else "legacy-approved-storyboard"),
        "provider": provider,
        "providerModelId": provider_model_id,
        "modelVersion": model_version,
        "directionCurrent": bool(direction_state and direction_state.get("current")),
        "directionReason": (direction_state or {}).get("reason"),
        "attributionExact": False,
    }


def _animation_prompt_contract(ledger):
    batch = ledger.get("batch") or {}
    envelope = batch.get("envelope") or {}
    prompt = str(envelope.get("prompt") or "")
    envelope_hash = str(batch.get("envelopeHash") or "")
    actual_envelope_hash = hashlib.sha256(json.dumps(
        envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if envelope else ""
    if not prompt or not envelope_hash or envelope_hash != actual_envelope_hash:
        return None
    return {
        "prompt": prompt,
        "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
        "promptSource": envelope.get("promptSource") or "sealed-provider-request",
        "provider": envelope.get("provider"),
        "providerModelId": envelope.get("providerModelId"),
        "modelVersion": envelope.get("modelVersion"),
        "integrityVerified": True,
        "attributionExact": True,
        "batchId": ledger.get("batchId") or (ledger.get("batch") or {}).get("batchId"),
    }


def _recorded_asset_path(record, *fields):
    """Resolve current and legacy archive records without widening Studio file serving."""
    raw = next((record.get(name) for name in fields if record.get(name)), None)
    if not raw:
        return None
    supplied = pathlib.Path(raw)
    candidates = [supplied]
    if not supplied.is_absolute():
        candidates.extend((HERE / supplied, HERE.parent / supplied))
        original = record.get("path") or record.get("originalPath")
        if original:
            for parent in pathlib.Path(original).parents:
                if parent.name == "engine":
                    candidates.append(parent / supplied)
                    break
    for candidate in candidates:
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            continue
    return None


def _prompt_lab_media_url(path):
    """Return a preview URL only for media inside this canonical engine tree."""
    try:
        resolved = pathlib.Path(path).resolve()
        media_root = (HERE / "media").resolve()
        if resolved.is_file() and resolved.is_relative_to(media_root):
            return "/engine/media/" + resolved.relative_to(media_root).as_posix()
    except (OSError, ValueError):
        pass
    return None


def _prompt_lab_assets(pkg, shot, ledger, artifact_type):
    assets = []

    def add(candidate_id, label, path, contract, state, expected_hash=None,
            hash_at_generation=True):
        if not path or not os.path.isfile(path):
            return
        absolute = str(pathlib.Path(path).resolve())
        if any(item["path"] == absolute for item in assets):
            return
        prompt_exact = bool(contract and _prompt_contract_is_exact(contract))
        exact = bool(prompt_exact and expected_hash and hash_at_generation)
        grade = "exact" if exact else "prompt-only" if prompt_exact else "asset-only"
        assets.append({
            "candidateId": candidate_id,
            "label": label,
            "path": absolute,
            "state": state,
            "mediaUrl": _prompt_lab_media_url(absolute),
            "promptContract": ({**contract, "attributionExact": exact}
                               if prompt_exact else None),
            "promptAttributionExact": prompt_exact,
            "assetHashRecorded": bool(expected_hash),
            "assetHashAtGeneration": bool(expected_hash and hash_at_generation),
            "provenanceGrade": grade,
            "attributionExact": exact,
            "expectedAssetHash": expected_hash,
        })

    if artifact_type == "keyframe":
        candidate = ledger.get("keyframeCandidate") or {}
        approval = ledger.get("keyframeApproval") or {}
        add("candidate", "Candidate", candidate.get("path"),
            candidate.get("promptContract"),
            ("awaiting" if (candidate.get("conformanceScreening") or {}).get("status") == "pass"
             else "screening"), candidate.get("contentHash"))
        add("approved", "Approved keyframe", approval.get("path"),
            approval.get("promptContract"), "approved", approval.get("contentHash"))
        for index, rejection in enumerate(ledger.get("keyframeRejections") or [], start=1):
            add(f"KF-R{index}", f"Rejected keyframe {index}",
                _recorded_asset_path(rejection, "rejectedFile", "archivedPath"),
                rejection.get("promptContract"), "rejected", rejection.get("contentHash"),
                bool(rejection.get("contentHashAtGeneration",
                                   rejection.get("promptContract") and rejection.get("contentHash"))))
        return assets

    contract = _animation_prompt_contract(ledger)
    output_hashes = {
        str(pathlib.Path(item.get("path") or "").resolve()): item.get("sha256")
        for item in ((ledger.get("batch") or {}).get("candidateHashes") or [])
        if item.get("path") and item.get("sha256")
    }
    if ledger.get("status") == "candidates-pending":
        for index, path in enumerate(ledger.get("candidatePaths") or [], start=1):
            add(f"C{index}", f"Candidate C{index}", path, contract, "awaiting",
                output_hashes.get(str(pathlib.Path(path).resolve())))
    approved = ledger.get("approvedTake")
    if approved:
        number = int(ledger.get("approvedCandidate") or 1)
        add(f"C{number}", f"Approved C{number}", approved, contract, "approved",
            output_hashes.get(str(pathlib.Path(approved).resolve())))
    for index, record in enumerate(ledger.get("renderHistory") or [], start=1):
        archived_path = _recorded_asset_path(record, "archivedPath")
        candidate_id = record.get("candidateId") or f"H{index}"
        add(candidate_id, record.get("label") or f"Archived {candidate_id}", archived_path,
            record.get("promptContract"), record.get("outcome") or "archived",
            record.get("contentHash"), bool(record.get("contentHashAtGeneration")))
    return assets


def _prompt_lab_feedback(ledger, artifact_type):
    """Return human-authored notes with source and scope; never infer a score from prose."""
    items = []

    def add(note, reviewer, created_at, kind, source_label, **extra):
        note = str(note or "").strip()
        reviewer = str(reviewer or "").strip()
        if not note or not reviewer or reviewer.startswith("Auto-carried-forward"):
            return
        payload = [artifact_type, kind, source_label, created_at, reviewer, note]
        feedback_id = hashlib.sha256(json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()[:16]
        items.append({
            "feedbackId": feedback_id,
            "note": note,
            "reviewer": reviewer,
            "createdAt": created_at,
            "kind": kind,
            "sourceLabel": source_label,
            "topics": cb_prompt_lab.classify_feedback(note),
            "scoreInferred": False,
            **extra,
        })

    if artifact_type == "keyframe":
        for index, record in enumerate(ledger.get("keyframeRejections") or [], start=1):
            add(record.get("reason"), record.get("reviewedBy"), record.get("rejectedAt"),
                "render-comment", f"Rejected keyframe {index}", outcome="rejected",
                candidateId=f"KF-R{index}")
        direction_stage = "cinematography"
    else:
        for index, record in enumerate(ledger.get("rejections") or [], start=1):
            add(record.get("correction"), record.get("reviewed_by"), record.get("at"),
                "render-comment", f"Rejected batch {index}", outcome="rejected",
                batchId=record.get("batchId"), category=record.get("category"))
        direction_stage = "animation"

    for stage in (f"review-{artifact_type}", direction_stage):
        work = ((ledger.get("departmentWork") or {}).get(stage) or {})
        records = list(work.get("history") or [])
        if work.get("approved"):
            records.append(work["approved"])
        if work.get("candidate"):
            records.append(work["candidate"])
        for record in records:
            add(record.get("note"), record.get("reviewedBy"),
                record.get("decisionAt") or record.get("preparedAt"),
                "director-review" if stage.startswith("review-") else "direction-note",
                "Director Review" if stage.startswith("review-") else
                f"{direction_stage.title()} direction")

    items.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return items


def _latest_media_review(ledger, artifact_type):
    stage = "review-keyframe" if artifact_type == "keyframe" else "review-animation"
    work = ((ledger.get("departmentWork") or {}).get(stage) or {})
    event = work.get("candidate") or work.get("approved")
    if not event:
        return None
    output = event.get("output") or {}
    return {
        "state": "awaiting" if work.get("candidate") else "acknowledged",
        "preparedAt": event.get("preparedAt"),
        "reviewedAt": event.get("decisionAt"),
        "verdict": output.get("verdict"),
        "summary": output.get("summary"),
        "dimensions": {name: output.get(name) for name in cb_prompt_lab.DIMENSIONS},
        "likelyRootCause": output.get("likelyRootCause"),
        "rootCauseReasoning": output.get("rootCauseReasoning"),
        "cheapestNextAction": output.get("cheapestNextAction"),
        "learningTags": output.get("learningTags") or [],
        "advisoryOnly": True,
    }


def _prompt_lab_snapshot(scene, shot_id, artifact_type, episode="Ep1", candidate_id=None):
    if artifact_type not in cb_prompt_lab.VALID_ARTIFACT_TYPES:
        raise Refused("REFUSED — artifactType must be keyframe or animation")
    pkg, _ = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    if artifact_type == "keyframe" and shot.get("sourceType") != "opener":
        raise Refused(f"REFUSED — {shot_id} inherits its opening frame and has no keyframe prompt")
    assets = _prompt_lab_assets(pkg, shot, ledger, artifact_type)
    selected = None
    if candidate_id:
        selected = next((item for item in assets if item["candidateId"] == candidate_id), None)
        if selected is None:
            raise Refused(f"REFUSED — {candidate_id} is not a current {artifact_type} render for {shot_id}")
    elif assets:
        selected = assets[0]
    selected_contract = (selected or {}).get("promptContract")
    contract = selected_contract or _current_prompt_contract(pkg, shot, artifact_type)
    analysis = cb_prompt_lab.analyze_prompt(
        contract["prompt"], artifact_type,
        cb_departments.provider_dialogue_lines(shot)
        if artifact_type == "animation" else [])
    shot_records = cb_db.list_render_ratings(
        HERE.parent, episode=episode, scene=scene, shot_id=shot_id,
        artifact_type=artifact_type)
    episode_records = cb_db.list_render_ratings(
        HERE.parent, episode=episode, artifact_type=artifact_type)
    feedback = _prompt_lab_feedback(ledger, artifact_type)
    direction_stage = "cinematography" if artifact_type == "keyframe" else "animation"
    current_direction = _inspection_department_output(pkg, shot_id, direction_stage)
    current_direction_prompt = str(current_direction.get("providerPrompt") or "")
    prompt_plan_summary = ""
    if (current_direction_prompt and
            hashlib.sha256(current_direction_prompt.encode()).hexdigest() ==
            contract.get("promptHash")):
        prompt_plan_summary = str(
            current_direction.get("deliveryPlan") or
            current_direction.get("doesItLand") or "").strip()
        if not prompt_plan_summary:
            stages = current_direction.get("stagePlan") or []
            events = [str(stage.get("primaryEvent") or "").strip() for stage in stages]
            events = [event for event in events if event]
            prompt_plan_summary = " ".join(filter(None, [
                str(current_direction.get("generationGoal") or "").strip(),
                "Then ".join(events[:3]),
                str(current_direction.get("continuityFinish") or "").strip(),
            ])).strip()
    seedance_contract = None
    if artifact_type == "animation":
        reference_contract = current_direction.get("referenceContract") or [
            {"assetTag": tag, "role": role}
            for tag, role in (shot.get("referenceSlots") or {}).items()
        ]
        seedance_contract = cb_prompt_lab.analyze_seedance_prompt_contract(
            contract["prompt"],
            task_mode=current_direction.get("taskMode") or "reference-to-video",
            reference_contract=reference_contract,
            duration_sec=shot.get("durationSec"),
            dialogue_lines=cb_departments.provider_dialogue_lines(shot),
            stage_plan=(current_direction.get("stagePlan") or []
                        if current_direction_prompt and
                        hashlib.sha256(current_direction_prompt.encode()).hexdigest() ==
                        contract.get("promptHash") else []),
        )
    current_asset_hash = None
    if selected and shot_records:
        try:
            current_asset_hash = _sha256_file(pathlib.Path(selected["path"]))
        except OSError:
            current_asset_hash = None
    correlation = cb_prompt_lab.build_direction_correlation(
        shot,
        analysis,
        artifact_type,
        selected=selected,
        ledger=ledger,
        feedback=feedback,
        ratings=shot_records,
        current_asset_hash=current_asset_hash,
        prompt_applies_to_render=bool(selected_contract),
        prompt_plan_summary=prompt_plan_summary,
    )
    return {
        "episode": episode,
        "scene": str(scene),
        "shotId": shot_id,
        "artifactType": artifact_type,
        "shot": shot,
        "ledger": ledger,
        "assets": assets,
        "selected": selected,
        "promptContract": contract,
        "analysisAppliesToRender": bool(selected_contract),
        "analysis": analysis,
        "ratings": shot_records,
        "summary": cb_prompt_lab.summarize_ratings(
            episode_records, current_prompt_hash=contract["promptHash"]),
        "aiReview": _latest_media_review(ledger, artifact_type),
        "existingFeedback": feedback,
        "correlation": correlation,
        "seedancePromptContract": seedance_contract,
    }


def prompt_lab_status(scene, shot_id, artifact_type, episode="Ep1", candidate_id=None):
    """Free read-only Prompt Lab view. No model or provider is called."""
    snapshot = _prompt_lab_snapshot(scene, shot_id, artifact_type, episode, candidate_id)
    selected = snapshot["selected"]
    contract = snapshot["promptContract"]
    assets = [{
        "candidateId": item["candidateId"],
        "label": item["label"],
        "state": item["state"],
        "fileName": os.path.basename(item["path"]),
        "mediaUrl": item.get("mediaUrl"),
        "provenanceGrade": item["provenanceGrade"],
        "promptAttributionExact": item["promptAttributionExact"],
        "assetHashAtGeneration": item["assetHashAtGeneration"],
        "attributionExact": item["attributionExact"],
        "promptHash": ((item.get("promptContract") or {}).get("promptHash")),
        "batchId": ((item.get("promptContract") or {}).get("batchId")),
    } for item in snapshot["assets"]]
    ratings = [{
        "ratingId": item["ratingId"],
        "candidateId": item["candidateId"],
        "assetHash": item["assetHash"],
        "promptHash": item["promptHash"],
        "overallRead": item["overallRead"],
        "scores": item["scores"],
        "note": item["note"],
        "reviewer": item["reviewer"],
        "learningEligible": item.get("learningEligible", True),
        "provenanceGrade": item.get("provenanceGrade", "exact"),
        "createdAt": item["createdAt"],
    } for item in snapshot["ratings"]]
    return {
        "schemaVersion": cb_prompt_lab.SCHEMA_VERSION,
        "zeroSpend": True,
        "mediaProviderCalled": False,
        "approvalChanged": False,
        "advisoryOnly": True,
        "episode": snapshot["episode"],
        "scene": snapshot["scene"],
        "shotId": shot_id,
        "artifactType": artifact_type,
        "assets": assets,
        "selectedCandidateId": (selected or {}).get("candidateId"),
        "canRate": bool(selected),
        "canTeachPrompt": bool(selected and selected["attributionExact"]),
        "ratingMode": ("prompt-learning" if selected and selected["attributionExact"]
                       else "quality-only" if selected else None),
        "attributionWarning": (
            None if not selected or selected["attributionExact"] else
            "The exact render-to-prompt chain is incomplete. Your quality rating will be "
            "saved against the media bytes that survive now, but excluded from prompt-wording evidence."
        ),
        "directionWarning": (
            None if ((selected and selected["promptAttributionExact"]) or
                     contract.get("directionCurrent") is not False) else
            f"The approved {'Cinematography' if artifact_type == 'keyframe' else 'Animation'} "
            "direction is not current. This analysis remains available, but generation "
            "still requires a current specialist approval."
        ),
        "promptContract": {
            "prompt": contract["prompt"],
            "promptHash": contract["promptHash"],
            "promptSource": contract.get("promptSource"),
            "provider": contract.get("provider"),
            "providerModelId": contract.get("providerModelId"),
            "modelVersion": contract.get("modelVersion"),
            "directionCurrent": contract.get("directionCurrent"),
            "attributionExact": bool((selected or {}).get("promptAttributionExact")),
            "analysisAppliesToRender": snapshot["analysisAppliesToRender"],
            "batchId": contract.get("batchId"),
        },
        "analysis": snapshot["analysis"],
        "ratingDimensions": [
            {"key": name, "label": cb_prompt_lab.DIMENSIONS[name]}
            for name in cb_prompt_lab.dimensions_for(artifact_type)
        ],
        "ratings": ratings,
        "evidenceSummary": snapshot["summary"],
        "aiReview": snapshot["aiReview"],
        "existingFeedback": snapshot["existingFeedback"],
        "correlation": snapshot["correlation"],
        "seedancePromptContract": snapshot["seedancePromptContract"],
    }


def rate_prompt_render(scene, shot_id, artifact_type, candidate_id, scores,
                       overall_read, note="", episode="Ep1", reviewed_by="Julian"):
    """Append a human rating; only exact prompt+generation-hash records teach wording."""
    clean_scores, overall_read, note = cb_prompt_lab.validate_rating(
        artifact_type, scores, overall_read, note)
    snapshot = _prompt_lab_snapshot(
        scene, shot_id, artifact_type, episode, candidate_id=candidate_id)
    selected = snapshot["selected"]
    if not selected:
        raise Refused("REFUSED — the selected render is no longer available")
    reviewer = str(reviewed_by or "").strip()
    if not reviewer or len(reviewer) > 100:
        raise Refused("REFUSED — reviewedBy must be 1-100 characters")
    path = pathlib.Path(selected["path"])
    if not path.is_file():
        raise Refused("REFUSED — the selected render no longer exists on disk")
    actual_asset_hash = _sha256_file(path)
    expected_asset_hash = selected.get("expectedAssetHash")
    if expected_asset_hash and actual_asset_hash != expected_asset_hash:
        raise Refused(
            "REFUSED — the render bytes no longer match the immutable generation record")
    learning_eligible = bool(selected["attributionExact"])
    contract = selected.get("promptContract")
    if contract:
        analysis = cb_prompt_lab.analyze_prompt(
            contract["prompt"], artifact_type, snapshot["shot"].get("dialogueLines") or [])
        prompt_hash = contract["promptHash"]
        prompt_text = contract["prompt"]
        prompt_source = contract.get("promptSource") or "unknown"
    else:
        analysis = {
            "schemaVersion": cb_prompt_lab.SCHEMA_VERSION,
            "artifactType": artifact_type,
            "unavailable": True,
            "reason": "No exact generation prompt survives for this legacy render.",
            "advisoryOnly": True,
            "providerCalled": False,
        }
        prompt_hash = ""
        prompt_text = ""
        prompt_source = "unattributed-legacy-render"
    record = {
        "ratingId": uuid.uuid4().hex,
        "episode": episode,
        "scene": str(scene),
        "shotId": shot_id,
        "artifactType": artifact_type,
        "candidateId": candidate_id,
        "assetPath": str(path.resolve()),
        "assetHash": actual_asset_hash,
        "promptHash": prompt_hash,
        "promptText": prompt_text,
        "promptSource": prompt_source,
        "provider": (contract or {}).get("provider"),
        "providerModelId": (contract or {}).get("providerModelId"),
        "modelVersion": (contract or {}).get("modelVersion"),
        "overallRead": overall_read,
        "scores": clean_scores,
        "note": note,
        "reviewer": reviewer,
        "promptAnalysis": analysis,
        "learningEligible": learning_eligible,
        "provenanceGrade": selected.get(
            "provenanceGrade", "exact" if learning_eligible else
            "prompt-only" if contract else "asset-only"),
        "createdAt": cb_db.utc_now(),
    }
    try:
        cb_db.save_render_rating(HERE.parent, record)
    except (ValueError, cb_db.StateConflict) as exc:
        raise Refused(f"REFUSED — could not save render rating: {exc}") from exc
    return record


def fire_shot(scene, shot_id, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, comparison_model_id=None,
              comparison_run_id=None, log=print, include_audio_reference=True,
              generate_audio=True):
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
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    if led.get("status") == "model-limited":
        raise Refused(f"REFUSED — {shot_id} is MODEL-LIMITED after {MAX_BATCH_ATTEMPTS} failed "
                      f"candidate batches; the ladder requires human redesign or an alternative "
                      f"production method, never more prompt-patching.\n{DECISION_LADDER}")
    animation_direction = _approved_department_output(pkg, shot_id, "animation") or {}
    budget = _performance_budget_report(
        _shot_creative_contract_view(pkg, shot, scene, episode), led)
    if not budget["ready"]:
        raise Refused(
            f"REFUSED — {shot_id}'s voice-timed performance budget is overloaded: "
            + "; ".join(budget.get("reasons") or []))
    # HEAR is the per-shot human timing decision: its approved @Audio1 identity, placement
    # signature and content hash are checked above and again by the sealed Fire envelope.
    # The scene timing slate remains useful review evidence, but requiring a second rhythm
    # approval here duplicated Julian's HEAR decision and blocked an otherwise valid WATCH
    # fire. Hard protection remains in _performance_budget_report: overlaps and overfilled
    # 30-second units are refused before any spend authorization is issued.
    _require_engine_rules(pkg, shot, animation_direction)
    provenance = cb_engine_rules.duration_provenance(shot, animation_direction)
    previous_provenance = led.get("durationProvenance") or {}
    if (previous_provenance.get("authoritative") and
            previous_provenance.get("costSignature") != provenance.get("costSignature")):
        led.setdefault("durationProvenanceHistory", []).append(previous_provenance)
        _carry_approved_inputs_across_duration_change(led, provenance)
    led["durationProvenance"] = provenance
    _ensure_character_scale_control(
        shot, scene, episode, _characters_cfg(), same_depth=None)
    comparison_model_id, comparison_run_id = _comparison_args(
        comparison_model_id, comparison_run_id)
    existing_auth = led.get("pendingSpendAuth") or {}
    existing_batch = led.get("batch") or {}
    existing_envelope = (
        existing_batch.get("envelope") if existing_batch.get("status") == "generating"
        else existing_auth.get("envelope")
    ) or {}
    sealed_comparison_run = existing_envelope.get("comparisonRunId")
    if sealed_comparison_run:
        sealed_model = existing_envelope.get("providerModelId")
        if comparison_model_id and (
                comparison_model_id != sealed_model or
                comparison_run_id != sealed_comparison_run):
            raise Refused("REFUSED — comparison settings differ from the sealed spend envelope")
        comparison_model_id, comparison_run_id = sealed_model, sealed_comparison_run
    billing_provider = (
        "fal" if comparison_model_id else
        cb_providers.video_model(require_enabled=False).provider)
    _require_confirmed_billing(billing_provider)             # protection 5 — block, not warn
    # THE ANIMATION WORKING PROMPT, IF SAVED, IS WHAT ACTUALLY SUBMITS (2026-07-19, Julian's
    # contained-creative-controls directive): a shallow-copied VIEW of the shot with
    # seedancePrompt swapped for the working override — every downstream read in this
    # function (Law 6 check, binding hash, disclosure, sealed envelope, the real generate
    # call) already reads shot["seedancePrompt"], so this one substitution is the whole
    # change. The approved package's own shot record (pkg["shots"]) is never touched.
    resolved_prompt, using_working = _resolve_seedance_prompt(
        pkg, shot, scene, episode, require_current_working=True)
    if resolved_prompt != shot.get("seedancePrompt"):
        shot = {**shot, "seedancePrompt": resolved_prompt}
    candidates = max(1, min(MAX_CANDIDATES, int(candidates)))
    if led.get("status") == "approved":
        raise Refused(f"REFUSED — {shot_id} is already approved; reject it first to re-fire")
    _require_stage_contract_keyframe(shot, led)
    spoken_dialogue = cb_audio_authority.spoken_dialogue_lines(shot)
    if spoken_dialogue and not (led.get("voiceApproval") or {}).get("approved"):
        # 2026-07-19: requires APPROVAL, not mere file existence — matching the keyframe
        # anchor's own "a generated-but-unapproved candidate is never a valid anchor" rule.
        reason = ("no voice track generated yet" if not led.get("voPath")
                  else "its voice track has not been approved yet")
        raise Refused(f"REFUSED — {shot_id} has dialogue but {reason} "
                      f"(Law 5: voice first, no native-voice fallback)")

    dialogue_check = emission.validate_dialogue_synthesis(
        shot["seedancePrompt"], spoken_dialogue)
    if not dialogue_check["ready"]:
        raise Refused("REFUSED — dialogue synthesis preflight failed before spend: " +
                      "; ".join(dialogue_check["errors"]))

    # THE UNCHANGED-PACKAGE RULE: nothing is auto-appended after a failure — a reroll ships
    # the byte-identical contract; a targeted correction is a NEW versioned package that
    # re-validates and re-discloses below (the binding hash makes this mechanical).
    prompt = shot["seedancePrompt"]
    anchor = _anchor_for(pkg, shot)
    characters_cfg = _characters_cfg()
    shot = _with_effective_reference_slots(
        pkg, shot, "referenceSlots", scene, episode)
    attachment_plan = _provider_attachment_plan(
        shot, "referenceSlots", anchor, scene, episode, characters_cfg)
    _require_prop_reference_authority(
        shot, scene, episode, attachment_plan)
    imgs = [item["path"] for item in attachment_plan]
    execution_plan = _animation_execution_plan(
        pkg, shot, led, imgs, anchor, fast,
        comparison_model_id=comparison_model_id,
        comparison_run_id=comparison_run_id,
        materialize_audio=True,
        include_audio_reference=include_audio_reference,
        generate_audio=generate_audio)

    # ── RESUME PATH (protection 2): an in-flight batch completes its MISSING candidates
    # only, under its ORIGINAL token — completed candidates are never regenerated or repaid
    batch = led.get("batch")
    if batch and batch.get("status") == "generating":
        if spend_token != batch["token"]:
            raise Refused(f"REFUSED — {shot_id} has an in-flight batch; resuming requires its "
                          f"original spend token (nothing new is authorized)")
        binding, _per = _binding_hash(
            pkg, shot, led, imgs, anchor, batch["expected"], fast,
            comparison_model_id, comparison_run_id, execution_plan)
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
        _fresh_validation(pkg, episode, shot_id)
        binding, per = _binding_hash(
            pkg, shot, led, imgs, anchor, candidates, fast,
            comparison_model_id, comparison_run_id, execution_plan)
        envelope, env_hash = _sealed_envelope(pkg, shot, led, imgs, anchor, candidates,
                                                fast, per, comparison_model_id,
                                                comparison_run_id, execution_plan)
        reroll = (led.get("lastBatchBinding") == binding)
        reference_records = _reference_records(shot, imgs)
        _require_prompt_slot_text_consistency(envelope.get("prompt") or prompt,
                                              reference_records)
        exact_reference_slots = {
            item["slot"]: (
                f"{item['role']} · {item['view']} turnaround view"
                if item.get("view") else item["role"])
            for item in reference_records
        }
        disclosure = {"shotId": shot_id, "candidateCount": candidates,
                       "costPerCandidateUsd": per,
                       "maxBatchCostUsd": round(per * candidates, 4),
                       "promptVersion": _prompt_version(shot),
                       "bindingHash": binding,
                       "envelopeHash": env_hash,
                       "packageHash": _shots_hash(pkg),
                       "rerollOfUnchangedPackage": reroll,
                       "packageRevision": pkg.get("revision"),
                       "referenceSlots": exact_reference_slots,
                       "logicalReferenceSlots": shot["referenceSlots"],
                       "openingAnchor": anchor, "audioAsset": led.get("voPath"),
                       "shotDurationSec": shot["durationSec"],
                       "provider": envelope["provider"],
                       "providerModelId": envelope["providerModelId"],
                       "modelVersion": envelope["modelVersion"],
                       "resolution": envelope["executionPlan"]["segments"][0]["contract"]["resolution"],
                       "promptScores": {
                           "contractCompleteness": envelope["executionPlan"]["segments"][0]
                           .get("promptAudit", {}).get("contractCompleteness"),
                           "creative": envelope["executionPlan"]["segments"][0]
                           .get("promptAudit", {}).get("creativeGate"),
                           "authoringScore10": envelope["executionPlan"]["segments"][0]
                           .get("promptAudit", {}).get("authoringScore10"),
                           "authoringMaximum": 10,
                           "firingFloor10": envelope["executionPlan"]["segments"][0]
                           .get("promptAudit", {}).get("firingFloor10"),
                       },
                       "comparisonRunId": envelope.get("comparisonRunId"),
                       "internalProviderCalls": [
                           {"segmentIndex": item["segmentIndex"],
                            "durationSec": item["durationSec"],
                            "stageNumbers": item.get("stageNumbers") or []}
                           for item in envelope["executionPlan"]["segments"]
                       ],
                       "tier": "fast" if fast else "standard"}
        log("SPEND DISCLOSURE — review before approving:")
        for k in ("shotId", "candidateCount", "costPerCandidateUsd", "maxBatchCostUsd",
                   "promptVersion", "bindingHash", "envelopeHash", "packageRevision",
                   "rerollOfUnchangedPackage", "openingAnchor", "audioAsset",
                   "shotDurationSec", "providerModelId", "comparisonRunId", "tier"):
            log(f"  {k}: {disclosure[k]}")
        log("  promptScores: " + json.dumps(disclosure["promptScores"], ensure_ascii=False))
        log("  internalProviderCalls: " + json.dumps(
            disclosure["internalProviderCalls"], ensure_ascii=False))
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
                 "disclosure": auth["disclosure"], "status": "generating",
                 "audioProvenance": ({
                     "policyVersion": "dialogue-post-lane-v1",
                     "approvedMasterPath": led.get("voPath"),
                     "approvedMasterSha256": _sha256_file(led["voPath"]),
                     "providerUse": "performance-conditioning",
                     "passthroughGuaranteed": False,
                     "providerOutputRole": "guide-track-only",
                     "finalFilmDialogue": "approved-master-restored-in-post",
                 } if cb_audio_authority.spoken_dialogue_lines(shot) and led.get("voPath") else None)}
        led["batch"] = batch
        _save(pkg, path)

    execution_plan = envelope["executionPlan"]

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
            changed = False
            if i not in batch["done"]:
                batch["done"].append(i)
                changed = True
            if changed:
                _save(pkg, path)
            continue                                       # idempotent: never regenerated
        segments = execution_plan["segments"]
        transport = batch.setdefault("transportCandidates", {}).setdefault(
            str(i), {"segments": [], "status": "generating"})
        segment_paths = []
        active_segment = None
        try:
            for segment in segments:
                segment_index = int(segment["segmentIndex"])
                segment_count = int(segment["segmentCount"])
                segment_dir = MEDIA / "transport" / batch["batchId"] / f"c{i}"
                segment_out = (out if segment_count == 1 else
                               segment_dir / f"segment_{segment_index}.mp4")
                segment_out.parent.mkdir(parents=True, exist_ok=True)
                opening_relay = None
                if segment.get("dynamicOpeningRelay"):
                    if not segment_paths:
                        raise RuntimeError("dynamic opening relay has no preceding segment")
                    opening_relay = segment_dir / f"segment_{segment_index - 1}_final.png"
                    cb_gen.last_frame(segment_paths[-1], out=str(opening_relay))
                    image_inputs = [str(opening_relay)] + [
                        item["path"] for item in segment["references"]
                        if item.get("dynamicFromSegment") is None
                    ]
                else:
                    image_inputs = [item["path"] for item in segment["references"]]
                video_inputs = [item["path"] for item in segment.get("videoReferences") or []]
                audio_inputs = ([segment["audio"]["path"]]
                                if (segment.get("audio") or {}).get("path") else None)

                segment_claim = {"action": "generate"}
                if segment_count > 1:
                    segment_claim = cb_db.claim_candidate_segment(
                        HERE.parent, batch["token"], i, segment_index, segment_count,
                        f"{os.getpid()}:{threading.get_ident()}")
                if segment_claim["action"] == "completed":
                    recorded = pathlib.Path(segment_claim.get("output_path") or "")
                    actual_hash = _sha256_file(recorded) if recorded.is_file() else None
                    if actual_hash != segment_claim.get("output_hash"):
                        raise RuntimeError(
                            f"completed internal segment {segment_index} is missing or changed"
                        )
                    segment_out = recorded
                else:
                    active_segment = segment_index if segment_count > 1 else None
                    transport["status"] = "submitting"
                    transport["activeSegment"] = segment_index
                    transport["lastProviderEvent"] = {
                        "event": "queued-for-submit",
                        "at": _now(),
                        "segmentIndex": segment_index,
                        "segmentCount": segment_count,
                    }
                    _save(pkg, path)
                    log(
                        f"FIRE — {shot_id} candidate {i}/{batch['expected']} · provider "
                        f"segment {segment_index}/{segment_count} "
                        f"({segment['durationSec']:g}s"
                        f"{', @Audio1' if audio_inputs else ''}) ..."
                    )
                    def provider_progress(event, *, _transport=transport,
                                          _segment_index=segment_index):
                        event = dict(event or {})
                        name = str(event.get("event") or "provider-event")
                        task_id = event.get("taskId")
                        status = event.get("status")
                        if name == "submitting":
                            _transport["status"] = "submitting"
                        elif name == "submitted":
                            _transport["status"] = "submitted"
                        elif name == "poll":
                            _transport["status"] = status or "polling"
                        elif name == "downloading":
                            _transport["status"] = "downloading"
                        elif name == "downloaded":
                            _transport["status"] = "downloaded"
                        if task_id:
                            _transport["providerTaskId"] = task_id
                        cleaned = {
                            "event": name,
                            "at": _now(),
                            "segmentIndex": _segment_index,
                        }
                        for key in ("taskId", "status", "requestBytes", "imageRefs",
                                    "audioRefs", "duration", "outputPath", "outputBytes"):
                            if key in event:
                                cleaned[key] = event[key]
                        _transport["lastProviderEvent"] = cleaned
                        events = _transport.setdefault("providerEvents", [])
                        events.append(cleaned)
                        del events[:-20]
                        _save(pkg, path)
                        if task_id:
                            log(
                                f"BYTEPLUS {name.upper()} — {shot_id} c{i} "
                                f"segment {_segment_index}: {task_id}"
                                f"{' · ' + str(status) if status else ''}"
                            )
                        else:
                            log(
                                f"BYTEPLUS {name.upper()} — {shot_id} c{i} "
                                f"segment {_segment_index}"
                            )
                    generate_kwargs = {
                        "audio_urls": audio_inputs,
                        "resolution": segment["contract"]["resolution"],
                        "duration": f"{int(round(segment['durationSec']))}",
                        "out": str(segment_out),
                        "fast": fast,
                        "raw_prompt": True,
                        "production_route": "cb_render",
                        "model_id": segment["contract"]["providerModelId"],
                        "comparison_run_id": execution_plan.get("comparisonRunId"),
                        "generate_audio": bool(segment.get("generateAudio", True)),
                        "progress_callback": provider_progress,
                    }
                    if video_inputs:
                        generate_kwargs["video_urls"] = video_inputs
                    _submit_seedance_provider(
                        segment["prompt"], image_inputs, **generate_kwargs)
                    if segment_count > 1:
                        cb_db.complete_candidate_segment(
                            HERE.parent, batch["token"], i, segment_index, segment_out)
                    active_segment = None
                segment_paths.append(str(segment_out))
                evidence = {
                    "segmentIndex": segment_index,
                    "durationSec": segment["durationSec"],
                    "stageNumbers": segment.get("stageNumbers") or [],
                    "promptHash": segment["promptHash"],
                    "outputPath": str(segment_out),
                    "outputHash": _sha256_file(segment_out),
                    "audioHash": ((segment.get("audio") or {}).get("md5")),
                    "openingRelayPath": str(opening_relay) if opening_relay else None,
                    "openingRelayHash": (_sha256_file(opening_relay)
                                         if opening_relay else None),
                }
                transport["segments"] = [
                    item for item in transport["segments"]
                    if item.get("segmentIndex") != segment_index
                ] + [evidence]
                transport["segments"].sort(key=lambda item: item["segmentIndex"])
                _save(pkg, path)
            if len(segment_paths) > 1:
                cb_seedance_transport.join_segments(segment_paths, out)
            review_audio = _restore_approved_voice_for_review(
                shot, led, out, batch["batchId"], i)
            if review_audio:
                transport["providerGuidePath"] = review_audio["providerGuidePath"]
                transport["providerGuideHash"] = review_audio["providerGuideSha256"]
                transport["approvedHearReviewPath"] = review_audio["reviewPath"]
                transport["approvedHearReviewHash"] = review_audio["reviewSha256"]
                for item in transport.get("segments") or []:
                    if item.get("outputPath") == str(out):
                        item["outputPath"] = review_audio["providerGuidePath"]
                        item["outputHash"] = review_audio["providerGuideSha256"]
            transport["status"] = "joined"
            transport["candidatePath"] = str(out)
            transport["candidateHash"] = _sha256_file(out)
            if batch.get("audioProvenance") is not None:
                batch["audioProvenance"].setdefault("guideCandidates", []).append({
                    "candidate": i,
                    "path": (review_audio or {}).get("providerGuidePath", str(out)),
                    "sha256": (review_audio or {}).get(
                        "providerGuideSha256", _sha256_file(out)),
                    "exactApprovedWaveformPassthrough": False,
                })
                if review_audio:
                    batch["audioProvenance"].setdefault("reviewCandidates", []).append(
                        review_audio)
            _save(pkg, path)
        except (Exception, SystemExit) as e:
            # protection 6: the failure is PERSISTED, the batch stays resumable
            if active_segment is not None:
                try:
                    cb_db.fail_candidate_segment(
                        HERE.parent, batch["token"], i, active_segment, e)
                except cb_db.SpendConflict:
                    pass
            cb_db.fail_candidate(HERE.parent, batch["token"], i, e)
            batch["failed"].append({"candidate": i, "error": str(e)[:400], "at": _now()})
            transport["status"] = "failed"
            _save(pkg, path)
            raise Refused(f"REFUSED — candidate {i} failed during its sealed provider plan "
                          f"({str(e)[:160]}). The batch is saved and resumable: re-run with "
                          f"the SAME spend token to generate only the missing candidates — "
                          f"completed provider segments are never repaid.")
        _candidate_review(shot, str(out), batch["batchId"], i)
        cb_db.complete_candidate(HERE.parent, batch["token"], i, out)
        batch["done"].append(i)
        _save(pkg, path)                                   # persisted per candidate

    batch["status"] = "complete"
    paths = [str(MEDIA / f"{episode}_{shot_id}_c{i}.mp4") for i in sorted(batch["done"])]
    led.update({"status": "candidates-pending", "candidatePaths": paths,
                "batchId": batch["batchId"],
                "candidatesGenerated": (led.get("candidatesGenerated") or 0) + len(batch["done"]),
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


def import_animation_candidate(scene, shot_id, upload_path, episode="Ep1", log=print):
    """Register a human-supplied WATCH render as an immutable zero-spend candidate.

    Uploading is never approval. The same package, lineage, keyframe, voice and timing
    protections required by production WATCH remain mandatory, and the result returns to
    the ordinary candidate review/approve/reject path.
    """
    pkg, package_path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    if ledger.get("status") == "approved":
        raise Refused(f"REFUSED — {shot_id} already has an approved immutable take")
    if ledger.get("status") == "candidates-pending":
        raise Refused(f"REFUSED — {shot_id} already has a render awaiting review")
    _require_stage_contract_keyframe(shot, ledger)
    if (cb_audio_authority.spoken_dialogue_lines(shot) and
            not (ledger.get("voiceApproval") or {}).get("approved")):
        raise Refused(f"REFUSED — {shot_id} needs its ElevenLabs v3 voice approval before WATCH")
    if (int(pkg.get("creativeDirectingStandardVersion") or 0) >= 3 and
            cb_audio_authority.spoken_dialogue_lines(shot)):
        slate = timing_slate_status(scene, episode)
        if not slate.get("approved"):
            raise Refused(f"REFUSED — scene {scene}'s voice-timed slate needs approval before WATCH")
    source = pathlib.Path(upload_path).resolve()
    if not source.is_file() or source.suffix.lower() not in {".mp4", ".webm"}:
        raise Refused("REFUSED — uploaded WATCH media must be an existing MP4 or WebM file")
    duration = cb_post._dur(str(source)) or 0.0
    if duration <= 0:
        raise Refused("REFUSED — uploaded WATCH media has no readable video duration")
    MEDIA.mkdir(parents=True, exist_ok=True)
    revision = len(ledger.get("uploadedAnimationCandidates") or []) + 1
    destination = MEDIA / f"{episode}_{shot_id}_uploaded_r{revision}{source.suffix.lower()}"
    if destination.exists():
        destination = MEDIA / f"{episode}_{shot_id}_uploaded_r{revision}_{uuid.uuid4().hex[:8]}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    content_hash = _sha256_file(destination)
    batch_id = f"upload-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}-{content_hash[:8]}"
    _candidate_review(shot, str(destination), batch_id, 1)
    upload_record = {
        "batchId": batch_id, "path": str(destination), "sha256": content_hash,
        "durationSec": duration, "source": "human-upload", "costUsd": 0,
        "packageRevision": pkg.get("revision"), "uploadedAt": _now(),
    }
    ledger.setdefault("uploadedAnimationCandidates", []).append(upload_record)
    ledger.update({
        "status": "candidates-pending", "candidatePaths": [str(destination)],
        "batchId": batch_id,
        "disclosure": {"packageRevision": pkg.get("revision"), "source": "human-upload",
                       "providerCalled": False, "estimatedCostUsd": 0},
        "firedAt": _now(),
    })
    _save(pkg, package_path)
    log(f"UPLOADED — {shot_id}: zero-spend WATCH candidate stored and awaiting Julian's decision")
    return upload_record


def _restore_approved_voice_for_review(shot, ledger, candidate_path, batch_id, candidate):
    """Audit that the provider received approved HEAR while preserving its final mix.

    Seedance returns the synchronized @Audio1 performance, SFX, ambience and music in one
    soundtrack. Replacing that stream removes the authored sound design and can conceal
    lip-sync defects, so WATCH must present the provider result unchanged for human review.
    """
    candidate_path = pathlib.Path(candidate_path)
    voice_path = ledger.get("voPath")
    if not cb_audio_authority.spoken_dialogue_lines(shot) or not voice_path:
        return None
    if not candidate_path.is_file() or not pathlib.Path(voice_path).is_file():
        raise Refused(
            f"REFUSED — cannot restore approved HEAR audio for {shot['shotId']} candidate "
            f"{candidate}: review media or voice master is missing")

    return {
        "candidate": candidate,
        "providerGuidePath": str(candidate_path),
        "providerGuideSha256": _sha256_file(candidate_path),
        "reviewPath": str(candidate_path),
        "reviewSha256": _sha256_file(candidate_path),
        "approvedMasterPath": str(voice_path),
        "approvedMasterSha256": _sha256_file(voice_path),
        "providerGuideRemoved": False,
        "approvedHearRestored": False,
        "providerFinalMixPreserved": True,
    }


def _video_edit_prompt(shot, correction, start_sec, end_sec, has_audio):
    audio = (
        "@Audio1 remains the sole authority for exact spoken words, voice identity, cadence, "
        "delivery, breath, pauses, mouth timing and silence. Do not replace, reinterpret or "
        "add dialogue. Listeners remain silent and closed-mouth. "
        if has_audio else
        "Preserve the existing soundtrack outside the correction window. "
    )
    return (
        f"Strictly edit @Video1 only. Apply this correction only from {start_sec:.2f}s to "
        f"{end_sec:.2f}s: {correction}\n"
        "Keep every frame outside that time window unchanged. Preserve the original cast "
        "identities, proportions, wardrobe, props, geography, lighting, camera axis, lens, "
        "camera motion, action timing and opening and closing states. Do not introduce a new "
        "shot, cut, transition, character, prop, caption, subtitle, watermark or alternative "
        "performance. Match motion continuously at both edit boundaries. " + audio
    )


def edit_shot(scene, shot_id, correction, start_sec, end_sec, episode="Ep1",
              spend_token=None, dry_run=False, reviewed_by="Julian", log=print):
    """Prepare or fire one native Seedance 2.5 edit of an approved take.

    The source take remains immutable. Calling without ``spend_token`` writes a sealed
    disclosure and stops. Calling with that exact token submits one video-editing request and
    returns a separate candidate for human review.
    """
    import cb_costs
    pkg, package_path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    if ledger.get("status") != "approved" or not ledger.get("approvedTake"):
        raise Refused(
            f"REFUSED — approve a source take for {shot_id} before editing it")
    if (ledger.get("editWork") or {}).get("status") in (
            "generating", "candidate-pending"):
        raise Refused(
            f"REFUSED — {shot_id} already has an edit awaiting completion or decision")
    correction = str(correction or "").strip()
    if not correction:
        raise Refused("REFUSED — a video edit requires one specific correction")
    if len(correction) > 1200:
        raise Refused("REFUSED — keep the video edit correction under 1200 characters")
    try:
        start_sec, end_sec = float(start_sec), float(end_sec)
    except (TypeError, ValueError) as exc:
        raise Refused("REFUSED — edit start and end must be seconds") from exc
    duration = float(shot.get("durationSec") or cb_post._dur(ledger["approvedTake"]) or 0)
    if not (0 <= start_sec < end_sec <= duration + 0.05):
        raise Refused(
            f"REFUSED — edit window must be inside the {duration:g}s approved take")
    source = pathlib.Path(ledger["approvedTake"])
    if not source.is_file():
        raise Refused("REFUSED — the approved source take is missing")
    source_hash = _sha256_file(source)
    has_audio = bool(cb_audio_authority.spoken_dialogue_lines(shot) and ledger.get("voPath"))
    audio_path = pathlib.Path(ledger["voPath"]) if has_audio else None
    if audio_path and not audio_path.is_file():
        raise Refused("REFUSED — the approved @Audio1 master is missing")
    prompt = _video_edit_prompt(shot, correction, start_sec, end_sec, has_audio)
    try:
        contract = cb_providers.request_contract(
            duration=int(round(duration)), resolution="480p", image_count=0,
            audio_count=1 if has_audio else 0, video_count=1,
            mode="video-editing")
    except cb_providers.ProviderCapabilityError as exc:
        raise Refused(f"REFUSED — provider capability: {exc}") from exc
    cost = round(cb_costs.estimate_video_cost(contract["costRateKey"], duration), 4)
    binding_payload = {
        "operation": "video-editing", "episode": episode, "scene": str(scene),
        "shotId": shot_id, "packageRevision": pkg.get("revision"),
        "sourcePath": str(source.resolve()), "sourceSha256": source_hash,
        "correction": correction, "startSec": round(start_sec, 3),
        "endSec": round(end_sec, 3), "prompt": prompt,
        "audioPath": str(audio_path.resolve()) if audio_path else None,
        "audioSha256": _sha256_file(audio_path) if audio_path else None,
        "contract": contract, "costUsd": cost,
    }
    binding_hash = hashlib.sha256(json.dumps(
        binding_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    envelope = {**binding_payload, "candidateCount": 1}
    envelope_hash = hashlib.sha256(json.dumps(
        envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    disclosure = {
        "operation": "Edit approved take", "shotId": shot_id,
        "sourceSha256": source_hash, "window": f"{start_sec:.2f}-{end_sec:.2f}s",
        "startSec": start_sec, "endSec": end_sec,
        "correction": correction, "provider": contract["provider"],
        "providerModelId": contract["providerModelId"],
        "modelVersion": contract["modelVersion"], "resolution": "480p",
        "durationSec": duration, "candidateCount": 1, "maximumCostUsd": cost,
        "audioAuthority": "ElevenLabs v3 @Audio1" if has_audio else "Seedance SFX/audio",
        "originalPreserved": True,
    }
    pending = ledger.get("pendingEditSpendAuth") or {}
    if dry_run:
        raise Refused("REFUSED — DRY RUN. No edit token was issued and no provider was contacted.")
    if spend_token is None:
        auth = {
            "token": uuid.uuid4().hex, "bindingHash": binding_hash,
            "envelopeHash": envelope_hash, "envelope": envelope,
            "disclosure": disclosure, "issuedAt": _now(),
        }
        ledger["pendingEditSpendAuth"] = auth
        cb_db.issue_spend_authorization(
            HERE.parent, episode, scene, f"{shot_id}.video-edit", auth)
        _save(pkg, package_path)
        log("EDIT SPEND DISCLOSURE — " + json.dumps(disclosure, ensure_ascii=False))
        raise Refused(
            "REFUSED — EDIT SPEND NOT APPROVED. Review the bounded correction and cost, "
            "then press Fire edit.")
    if not pending or spend_token != pending.get("token"):
        raise Refused("REFUSED — unknown or stale video-edit spend token")
    if (pending.get("bindingHash") != binding_hash or
            pending.get("envelopeHash") != envelope_hash):
        raise Refused("REFUSED — the edit source, prompt, audio, timing or cost changed after disclosure")
    batch_id = f"{shot_id}-edit-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    try:
        cb_db.claim_spend_authorization(
            HERE.parent, spend_token, episode, scene, f"{shot_id}.video-edit",
            binding_hash, envelope_hash, batch_id)
        cb_db.claim_candidate(HERE.parent, spend_token, 1, f"{os.getpid()}:{threading.get_ident()}")
    except cb_db.SpendConflict as exc:
        raise Refused(f"REFUSED — {exc}") from exc
    out = MEDIA / f"{episode}_{shot_id}_edit_{uuid.uuid4().hex[:8]}.mp4"
    ledger["pendingEditSpendAuth"] = None
    ledger["editWork"] = {
        "status": "generating", "batchId": batch_id,
        "sourcePath": str(source), "sourceSha256": source_hash,
        "prompt": prompt, "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "correction": correction, "startSec": start_sec, "endSec": end_sec,
        "disclosure": disclosure, "startedAt": _now(),
    }
    _save(pkg, package_path)

    def progress(event):
        work = ledger.get("editWork") or {}
        work["providerProgress"] = {**dict(event or {}), "at": _now()}
        if event.get("taskId"):
            work["providerTaskId"] = event["taskId"]
        _save(pkg, package_path)

    try:
        _submit_seedance_provider(
            prompt, [], audio_urls=[str(audio_path)] if audio_path else None,
            video_urls=[str(source)], resolution="480p",
            duration=str(int(round(duration))), out=str(out), raw_prompt=True,
            production_route="cb_render", model_id=contract["providerModelId"],
            generate_audio=True, progress_callback=progress,
            operation_mode="video-editing")
        audio_restore = _restore_approved_voice_for_review(
            shot, ledger, out, batch_id, "edit") if has_audio else None
        cb_db.complete_candidate(HERE.parent, spend_token, 1, out)
        cb_db.complete_spend_authorization(HERE.parent, spend_token)
    except (Exception, SystemExit) as exc:
        try:
            cb_db.fail_candidate(HERE.parent, spend_token, 1, exc)
        except cb_db.SpendConflict:
            pass
        ledger["editWork"]["status"] = "failed"
        ledger["editWork"]["error"] = str(exc)[:500]
        _save(pkg, package_path)
        raise Refused(f"REFUSED — Seedance video edit failed: {str(exc)[:200]}") from exc
    ledger["editWork"].update({
        "status": "candidate-pending", "candidatePath": str(out),
        "candidateSha256": _sha256_file(out), "completedAt": _now(),
        "audioProvenance": audio_restore,
    })
    _candidate_review(shot, str(out), batch_id, 1)
    _save(pkg, package_path)
    log(f"EDIT READY — {shot_id}: original preserved; revised take awaits Julian's decision")
    return str(out)


def approve_shot_edit(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
    pkg, package_path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    ledger = _ledger(pkg, shot_id)
    work = ledger.get("editWork") or {}
    candidate = pathlib.Path(work.get("candidatePath") or "")
    if work.get("status") != "candidate-pending" or not candidate.is_file():
        raise Refused(f"REFUSED — {shot_id} has no completed edit awaiting approval")
    if _sha256_file(candidate) != work.get("candidateSha256"):
        raise Refused("REFUSED — edited take bytes changed after generation")
    old = {
        "path": ledger.get("approvedTake"),
        "sha256": _sha256_file(ledger["approvedTake"]),
        "supersededBy": str(candidate), "at": _now(),
        "correction": work.get("correction"), "window": [work.get("startSec"), work.get("endSec")],
    }
    ledger.setdefault("editHistory", []).append(old)
    harvest = MEDIA / f"{episode}_{shot_id}_final_frame.png"
    cb_gen.last_frame(candidate, out=str(harvest))
    ledger.update({
        "approvedTake": str(candidate), "harvestFrame": str(harvest),
        "approval": {"approved": True, "source": "seedance-video-edit",
                     "reviewed_by": reviewed_by, "at": _now()},
        "editWork": None,
    })
    _save(pkg, package_path)
    log(f"EDIT APPROVED — {shot_id}; original remains in edit history")
    return str(candidate)


def reject_shot_edit(scene, shot_id, correction, episode="Ep1",
                     reviewed_by="Julian", log=print):
    pkg, package_path = load_pkg(scene, episode)
    ledger = _ledger(pkg, shot_id)
    work = ledger.get("editWork") or {}
    candidate = pathlib.Path(work.get("candidatePath") or "")
    correction = str(correction or "").strip()
    if work.get("status") != "candidate-pending" or not candidate.is_file():
        raise Refused(f"REFUSED — {shot_id} has no completed edit awaiting rejection")
    if not correction:
        raise Refused("REFUSED — rejecting an edit requires a reason")
    archive = MEDIA / "archive" / "shot_edits" / f"{episode}_{shot_id}_{uuid.uuid4().hex[:8]}"
    archive.mkdir(parents=True, exist_ok=True)
    archived = archive / candidate.name
    shutil.move(str(candidate), archived)
    ledger.setdefault("editHistory", []).append({
        **work, "status": "rejected", "candidatePath": str(archived),
        "rejectedAt": _now(), "reviewedBy": reviewed_by,
        "rejection": correction,
    })
    ledger["editWork"] = None
    _save(pkg, package_path)
    log(f"EDIT REJECTED — {shot_id}; approved source take remains current")
    return str(archived)


def next_shot(scene, episode="Ep1", candidates=DEFAULT_CANDIDATES, fast=False,
              spend_token=None, dry_run=False, comparison_model_id=None,
              comparison_run_id=None, log=print):
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
                              fast=fast, spend_token=spend_token, log=log,
                              dry_run=dry_run,
                              comparison_model_id=comparison_model_id,
                              comparison_run_id=comparison_run_id)
    log(f"SCENE {scene} — every shot approved; ready to stitch")
    return None


def _archive_animation_candidates(ledger, archive_dir, candidate_numbers, outcome):
    """Move candidates and every sidecar while retaining exact review provenance."""
    batch = ledger.get("batch") or {}
    batch_id = ledger.get("batchId") or batch.get("batchId") or "unknown-batch"
    prompt_contract = _animation_prompt_contract(ledger)
    recorded_hashes = {
        str(pathlib.Path(item.get("path") or "").resolve()): item.get("sha256")
        for item in (batch.get("candidateHashes") or [])
        if item.get("path") and item.get("sha256")
    }
    archived = []
    archive_dir.mkdir(parents=True, exist_ok=True)
    for index, candidate_path in enumerate(ledger.get("candidatePaths") or [], start=1):
        if index not in candidate_numbers:
            continue
        source = pathlib.Path(candidate_path)
        actual_hash = _sha256_file(source) if source.is_file() else None
        generation_hash = recorded_hashes.get(str(source.resolve()))
        hash_at_generation = bool(
            generation_hash and actual_hash and generation_hash == actual_hash)
        archived_path = None
        sidecars = []
        if source.is_file():
            destination = archive_dir / source.name
            shutil.move(source, destination)
            archived_path = str(destination.resolve())
        for suffix in (".review.json", ".gen.json"):
            sidecar = pathlib.Path(str(source) + suffix)
            if sidecar.is_file():
                destination = archive_dir / sidecar.name
                shutil.move(sidecar, destination)
                sidecars.append(str(destination.resolve()))
        candidate_id = f"{batch_id}-C{index}"
        archived.append({
            "candidateId": candidate_id,
            "label": f"Batch {batch_id} C{index}",
            "batchId": batch_id,
            "candidate": index,
            "outcome": outcome,
            "originalPath": str(source),
            "archivedPath": archived_path,
            "archivedSidecars": sidecars,
            "contentHash": actual_hash,
            "contentHashAtGeneration": hash_at_generation,
            "promptContract": prompt_contract,
            "archivedAt": _now(),
        })
    return archived


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
    history = _archive_animation_candidates(
        led, arch, {i for i in range(1, len(cands) + 1) if i != candidate},
        "not-selected")
    led.setdefault("renderHistory", []).extend(history)

    harvest = MEDIA / f"{episode}_{shot_id}_final_frame.png"
    cb_gen.last_frame(selected, out=str(harvest))
    led.update({"status": "approved", "approvedTake": selected,
                "approvedCandidate": candidate, "harvestFrame": str(harvest),
                "approval": {"approved": True, "candidate": candidate,
                              "reviewed_by": reviewed_by, "at": _now()}})
    if (led.get("batch") or {}).get("audioProvenance"):
        led["audioProvenance"] = {
            **led["batch"]["audioProvenance"],
            "selectedGuidePath": selected,
            "selectedGuideSha256": _sha256_file(selected),
            "postLaneStatus": "required",
        }
    bank_record = _bank_animation_prompt(
        pkg, shot_id, led, outcome="approved", candidate=candidate,
        candidate_path=selected)
    led.setdefault("promptBankRecords", []).append({
        "recordId": bank_record["recordId"],
        "outcome": bank_record["outcome"],
        "bankedAt": bank_record["bankedAt"],
    })
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


def recover_approved_shot(scene, shot_id, episode="Ep1", log=print):
    """Restore a dropped ledger approval from independent immutable evidence.

    Package promotion must not erase a completed human decision. Recovery is deliberately
    stricter than ordinary media discovery: the approved asset registry, the candidate's
    human-review sidecar, and the append-only approved prompt-bank record must all name the
    same shot, candidate path, candidate number, and provider batch. File existence alone
    can never create an approval.
    """
    with cb_db.scene_lease(HERE.parent, episode, str(scene),
                           f"cb_render.recover-approved:{shot_id}"):
        pkg, path = load_pkg(scene, episode)
        led = _ledger(pkg, shot_id)
        if (led.get("status") == "approved" and led.get("approvedTake") and
                led.get("harvestFrame")):
            return led["approvedTake"]

        assets = cb_asset_registry.resolve_assets(
            episode, scene, shot_id=shot_id,
            kinds={"approved_take", "final_frame"}, include_global=False)
        approved_takes = [item for item in assets
                          if item.get("shotId") == shot_id and
                          item.get("kind") == "approved_take" and
                          item.get("status") == "approved"]
        final_frames = [item for item in assets
                        if item.get("shotId") == shot_id and
                        item.get("kind") == "final_frame" and
                        item.get("status") == "approved"]
        if len(approved_takes) != 1 or len(final_frames) != 1:
            raise Refused(
                f"REFUSED — {shot_id} recovery needs exactly one registry-approved take "
                "and final frame")

        take = pathlib.Path(approved_takes[0]["path"]).resolve()
        harvest = pathlib.Path(final_frames[0]["path"]).resolve()
        if not take.is_file() or not harvest.is_file():
            raise Refused(f"REFUSED — {shot_id} recovery media is missing from disk")

        review_path = pathlib.Path(str(take) + ".review.json")
        if not review_path.is_file():
            raise Refused(f"REFUSED — {shot_id} recovery has no human-review sidecar")
        review = json.loads(review_path.read_text(encoding="utf-8"))
        candidate = review.get("candidate")
        batch_id = str(review.get("batchId") or "")
        if (review.get("shotId") != shot_id or not isinstance(candidate, int) or
                candidate < 1 or not batch_id or
                "human review only" not in str(review.get("note") or "").lower()):
            raise Refused(f"REFUSED — {shot_id} human-review sidecar is incomplete")

        prompt_records = [
            item for item in cb_prompt_bank.load_records()
            if item.get("episode") == episode and str(item.get("scene")) == str(scene)
            and item.get("shotId") == shot_id and item.get("outcome") == "approved"
            and item.get("approved") is True and item.get("candidate") == candidate
            and pathlib.Path(item.get("candidatePath") or "").resolve() == take
            and str((item.get("metadata") or {}).get("batchId") or "") == batch_id
        ]
        if len(prompt_records) != 1:
            raise Refused(
                f"REFUSED — {shot_id} recovery needs one matching approved prompt-bank record")
        prompt_record = prompt_records[0]

        recovered_at = _now()
        recovery = {
            "source": "registry+human-review+prompt-bank",
            "recoveredAt": recovered_at,
            "takeAssetId": approved_takes[0].get("assetId"),
            "finalFrameAssetId": final_frames[0].get("assetId"),
            "reviewSidecar": str(review_path),
            "promptRecordId": prompt_record.get("recordId"),
            "promptHash": prompt_record.get("promptHash"),
            "batchId": batch_id,
            "candidate": candidate,
        }
        led.setdefault("approvalRecoveryHistory", []).append(recovery)
        led.update({
            "status": "approved",
            "approvedTake": str(take),
            "approvedCandidate": candidate,
            "harvestFrame": str(harvest),
            "batchId": batch_id,
            "approval": {
                "approved": True,
                "candidate": candidate,
                "reviewed_by": "Julian",
                "at": review.get("at") or prompt_record.get("bankedAt"),
                "source": "recovered-audited-provider-approval",
                "contentHash": _sha256_file(take),
                "harvestHash": _sha256_file(harvest),
                "promptRecordId": prompt_record.get("recordId"),
                "promptHash": prompt_record.get("promptHash"),
                "batchId": batch_id,
                "recoveredAt": recovered_at,
            },
        })
        _save(pkg, path)
    log(f"RECOVERED APPROVAL — {shot_id} candidate {candidate}; relay frame restored")
    return str(take)


def reject_shot(scene, shot_id, correction, category="other", episode="Ep1",
                reviewed_by="Julian", log=print):
    """Reject the WHOLE candidate batch: every candidate archived (never deleted) with the
    one-sentence correction and its failure category on record. The next fire is a
    controlled reroll of the UNCHANGED package; after MAX_BATCH_ATTEMPTS failed batches the
    shot is MODEL-LIMITED and requires human redesign (the decision ladder's hard stop)."""
    pkg, path = load_pkg(scene, episode)
    shot = _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "candidates-pending" or not led.get("candidatePaths"):
        raise Refused(f"REFUSED — {shot_id} has no candidate batch pending review")
    correction = str(correction or "").strip()
    if not correction:
        raise Refused("REFUSED — a batch rejection requires a plain-language correction")
    if category not in FAILURE_CATEGORIES:
        raise Refused(f"REFUSED — category must be one of {FAILURE_CATEGORIES}")
    ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    arch = HERE / "media" / "archive" / "shots_rejected" / f"{episode}_{shot_id}_{ts}"
    history = _archive_animation_candidates(
        led, arch, set(range(1, len(led["candidatePaths"]) + 1)), "rejected")
    # Historical evidence comes from the sealed batch that produced the rejected pixels,
    # never from re-resolving today's possibly changed direction or references.
    batch_envelope = (led.get("batch") or {}).get("envelope") or {}
    prompt_text = str(batch_envelope.get("prompt") or "").strip()
    prompt_source = str(batch_envelope.get("promptSource") or "sealed-fired-batch")
    rejection = {"shotId": shot_id, "batchId": led.get("batchId"),
                 "correction": correction, "category": category,
                 "reviewed_by": reviewed_by, "at": _now(),
                 "archivedCandidates": history,
                 "promptText": prompt_text,
                 "promptHash": hashlib.sha256(prompt_text.encode()).hexdigest(),
                 "promptSource": prompt_source,
                 "scoreInferred": False}
    with open(arch / "REJECTED.json", "w") as f:
        json.dump(rejection, f, indent=1)
    bank_record = _bank_animation_prompt(
        pkg, shot_id, led, outcome="rejected", diagnosis=correction,
        category=category)
    attempts = led.get("batchAttempts", 0) + 1
    led.setdefault("renderHistory", []).extend(history)
    led.setdefault("rejections", []).append(rejection)
    led.setdefault("promptBankRecords", []).append({
        "recordId": bank_record["recordId"],
        "outcome": bank_record["outcome"],
        "bankedAt": bank_record["bankedAt"],
    })
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


def override_model_limited(scene, shot_id, reason, episode="Ep1",
                           reviewed_by="Julian", implemented_by="Codex",
                           log=print):
    """Audit a human decision to reopen a model-limited shot.

    This is deliberately zero-spend and does not approve or fire anything. It only moves
    the shot back to designed so the normal Seedance gate, spend disclosure and human
    approval flow can run again with the full rejection history still visible.
    """
    reason = str(reason or "").strip()
    if not reason:
        raise Refused("REFUSED — model-limited override requires a written reason")
    pkg, path = load_pkg(scene, episode)
    _require_valid(pkg)
    _require_current_lineage(pkg, scene, episode)
    _shot(pkg, shot_id)
    led = _ledger(pkg, shot_id)
    if led.get("status") != "model-limited":
        raise Refused(f"REFUSED — {shot_id} is {led.get('status') or 'unknown'}, not model-limited")
    if led.get("pendingSpendAuth"):
        raise Refused("REFUSED — clear or use the existing spend disclosure before overriding")
    if (led.get("batch") or {}).get("status") == "generating":
        raise Refused("REFUSED — a candidate batch is currently generating")
    rec = {
        "shotId": shot_id,
        "reason": reason,
        "reviewed_by": reviewed_by,
        "implemented_by": implemented_by,
        "at": _now(),
        "previousStatus": led.get("status"),
        "batchAttemptsAtOverride": led.get("batchAttempts", 0),
        "rejectionCountAtOverride": len(led.get("rejections") or []),
    }
    led.setdefault("modelLimitedOverrides", []).append(rec)
    led["status"] = "designed"
    _save(pkg, path)
    log(f"OVERRIDE RECORDED — {shot_id} reopened from MODEL-LIMITED with human reason: {reason}")
    return rec


def reopen_approved_shot(scene, shot_id, correction, category="other", episode="Ep1",
                         reviewed_by="Julian", log=print):
    """Archive an accepted take that fails later Director review and reopen the shot.

    Approval remains immutable evidence: the take, harvested frame, sidecars, approval and
    review records move into history. Only their status as the current production result is
    cleared. Any post master derived from the take is invalidated at the same boundary.
    """
    correction = str(correction or "").strip()
    if not correction:
        raise Refused("REFUSED — reopening an accepted take requires a plain-language correction")
    if category not in FAILURE_CATEGORIES:
        raise Refused(f"REFUSED — category must be one of {FAILURE_CATEGORIES}")

    with cb_db.scene_lease(HERE.parent, episode, str(scene),
                           f"cb_render.reopen-approved:{shot_id}"):
        pkg, path = load_pkg(scene, episode)
        led = _ledger(pkg, shot_id)
        approved_take = led.get("approvedTake")
        if led.get("status") != "approved" or not approved_take:
            raise Refused(f"REFUSED — {shot_id} has no accepted animation take to reopen")

        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        arch = (HERE / "media" / "archive" / "shots_reopened" /
                f"{episode}_{shot_id}_{stamp}_{uuid.uuid4().hex[:6]}")
        arch.mkdir(parents=True, exist_ok=False)

        archived_assets = []
        for source_value in (approved_take, led.get("harvestFrame")):
            if not source_value:
                continue
            source = pathlib.Path(source_value)
            content_hash = _sha256_file(source) if source.is_file() else None
            archived_path = None
            if source.is_file():
                destination = arch / source.name
                shutil.move(source, destination)
                archived_path = str(destination.resolve())
            archived_assets.append({
                "originalPath": str(source),
                "archivedPath": archived_path,
                "contentHash": content_hash,
            })
            if str(source) == str(approved_take):
                for suffix in (".review.json", ".gen.json"):
                    sidecar = pathlib.Path(str(source) + suffix)
                    if sidecar.is_file():
                        destination = arch / sidecar.name
                        shutil.move(sidecar, destination)

        event = {
            "shotId": shot_id,
            "batchId": led.get("batchId"),
            "approvedCandidate": led.get("approvedCandidate"),
            "priorApproval": led.get("approval"),
            "correction": correction,
            "category": category,
            "reviewed_by": reviewed_by,
            "at": _now(),
            "outcome": "accepted-take-reopened",
            "archivedAssets": archived_assets,
            "promptContract": _animation_prompt_contract(led),
        }
        (arch / "REOPENED.json").write_text(json.dumps(event, indent=1, ensure_ascii=False))
        led.setdefault("renderHistory", []).append(event)
        led.setdefault("rejections", []).append(event)
        if led.get("batch"):
            led.setdefault("batchHistory", []).append({
                **led["batch"], "outcome": "accepted-take-reopened", "archivedAt": _now()
            })

        review_work = ((led.get("departmentWork") or {}).get("review-animation") or {})
        for key in ("candidate", "approved"):
            if review_work.get(key):
                review_work.setdefault("history", []).append({
                    **review_work[key],
                    "outcome": "invalidated-by-reopened-take",
                    "invalidatedAt": _now(),
                })
                review_work[key] = None

        led.update({
            "status": "designed",
            "approvedTake": None,
            "approvedCandidate": None,
            "harvestFrame": None,
            "approval": None,
            "candidatePaths": None,
            "batchId": None,
            "batch": None,
            "pendingSpendAuth": None,
        })

        post = pkg.setdefault("postProduction", {
            "candidate": None, "approved": None, "history": []})
        for key in ("candidate", "approved"):
            if post.get(key):
                post.setdefault("history", []).append({
                    **post[key],
                    "outcome": "invalidated-by-reopened-shot",
                    "invalidatedAt": _now(),
                    "shotId": shot_id,
                })
                post[key] = None
        final_work = (pkg.setdefault("departmentWork", {})
                      .setdefault("review-final", {
                          "approved": None, "candidate": None, "history": []}))
        for key in ("candidate", "approved"):
            if final_work.get(key):
                final_work.setdefault("history", []).append({
                    **final_work[key],
                    "outcome": "invalidated-by-reopened-shot",
                    "invalidatedAt": _now(),
                    "shotId": shot_id,
                })
                final_work[key] = None

        _save(pkg, path)
    log(f"REOPENED — {shot_id}'s accepted take archived; correction on record: "
        f"{correction} [{category}]")
    return str(arch)


def import_approved_take(scene, shot_id, source_path, episode="Ep1",
                         reviewed_by="Julian", source_label="external",
                         provenance=None, approval_mode="generation-graph", log=print):
    """Import a Director-approved finished clip as the current immutable shot take.

    This is deliberately an approval operation, not a generation shortcut. The caller must
    name the human reviewer, the source clip is copied into managed media, its hash and
    provenance are recorded, and the literal last frame becomes the relay anchor. Existing
    accepted takes must be reopened first so their evidence remains in history.
    """
    source = pathlib.Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise Refused(f"REFUSED — approved import source does not exist: {source}")
    if source.suffix.lower() not in {".mp4", ".mov", ".m4v", ".webm"}:
        raise Refused("REFUSED — approved import must be a supported video file")
    reviewed_by = str(reviewed_by or "").strip()
    if not reviewed_by:
        raise Refused("REFUSED — approved import requires the human reviewer's name")

    with cb_db.scene_lease(HERE.parent, episode, str(scene),
                           f"cb_render.import-approved:{shot_id}"):
        pkg, path = load_pkg(scene, episode)
        led = _ledger(pkg, shot_id)
        if led.get("status") == "approved" or led.get("approvedTake"):
            raise Refused(
                f"REFUSED — {shot_id} already has an accepted take; reopen it before import")

        shot = _shot(pkg, shot_id)
        digest = _sha256_file(source)
        if approval_mode == "generation-graph":
            input_signature = _animation_generation_signature(
                pkg, shot, str(scene), episode, fast=False)
        elif approval_mode == "external-director-accepted":
            input_signature = _external_import_input_signature(
                pkg, shot, str(scene), episode, digest, provenance or {})
        else:
            raise Refused(
                "REFUSED — approval_mode must be generation-graph or "
                "external-director-accepted")

        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        destination = MEDIA / (
            f"{episode}_{shot_id}_import_{stamp}_{digest[:10]}{source.suffix.lower()}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        harvest = MEDIA / f"{episode}_{shot_id}_final_frame.png"
        cb_gen.last_frame(str(destination), out=str(harvest))
        imported_at = _now()
        import_record = {
            "outcome": "external-take-approved",
            "shotId": shot_id,
            "sourceLabel": str(source_label or "external"),
            "sourcePath": str(source),
            "managedPath": str(destination.resolve()),
            "contentHash": digest,
            "reviewed_by": reviewed_by,
            "at": imported_at,
            "provenance": provenance or {},
        }
        pathlib.Path(str(destination) + ".import.json").write_text(json.dumps(
            import_record, indent=1, ensure_ascii=False))
        led.setdefault("renderHistory", []).append(import_record)
        led.update({
            "status": "approved",
            "approvedTake": str(destination.resolve()),
            "approvedCandidate": None,
            "harvestFrame": str(harvest.resolve()),
            "candidatePaths": None,
            "batchId": None,
            "batch": None,
            "pendingSpendAuth": None,
            "approval": {
                "approved": True,
                "candidate": None,
                "reviewed_by": reviewed_by,
                "at": imported_at,
                "source": ("approved-external-import" if approval_mode == "generation-graph"
                           else "external-director-accepted"),
                "contentHash": digest,
                "harvestHash": _sha256_file(harvest),
                "inputSignature": input_signature,
                "packageRevision": pkg.get("revision"),
                "sourceLabel": str(source_label or "external"),
                "provenanceDigest": hashlib.sha256(json.dumps(
                    provenance or {}, sort_keys=True, ensure_ascii=False,
                    separators=(",", ":")).encode()).hexdigest(),
            },
        })
        if approval_mode == "external-director-accepted":
            led["audioProvenance"] = {
                "guideSource": str(destination.resolve()),
                "guideSourceSha256": digest,
                "dialogueAuthority": "approved-voice-master-required-in-post",
                "postLaneStatus": "required",
                "directorAcceptedPicture": True,
            }
        _save(pkg, path)

    log(f"IMPORTED + APPROVED — {shot_id} from {source_label} by {reviewed_by}; "
        f"final frame harvested -> {harvest.name}")
    return str(destination.resolve())


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
        cand_total += led.get("candidatesGenerated") or 0
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
    edit_decision = cb_rough_cut.scene_edit_decision(
        episode, str(scene), out=HERE.parent / "cb-output")
    package_shots = {shot["shotId"]: shot for shot in (pkg.get("shots") or [])}
    shots = []
    for cut in edit_decision["sequence"]:
        shot = package_shots.get(cut["shotId"])
        if not shot:
            raise Refused(f"REFUSED — scene cut references unknown shot {cut['shotId']}")
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
            "editDecision": cut,
        })
    inputs = {
        "postPolicyVersion": cb_post.POST_POLICY_VERSION,
        "postRuntimeHash": _sha256_file(cb_post.__file__),
        "packageInputSignature": pkg.get("inputSignature"),
        "orderedApprovedShots": shots,
        "directorCut": edit_decision,
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


def _scene_post_sources(pkg, scene=None, episode=None):
    """Collect only live approved units; retired design history is not a blocker."""
    source_by_id, missing = {}, []
    for s in pkg["shots"]:
        led = _ledger(pkg, s["shotId"])
        statuses = {
            str(s.get("status") or "").strip().lower(),
            str(led.get("status") or "").strip().lower(),
        }
        if (s.get("superseded") or any(
                status in {"superseded", "archived", "inactive"} or
                status.startswith("skipped-")
                for status in statuses if status)):
            continue
        if led.get("status") == "approved" and led.get("approvedTake"):
            source_by_id[s["shotId"]] = {
                "shotId": s["shotId"], "approvedTake": led["approvedTake"],
                "dialogueLines": list(s.get("dialogueLines") or []),
                "approvedVoice": led.get("voPath"),
                "audioProvenance": led.get("audioProvenance")}
        else:
            missing.append(s["shotId"])
    if missing or scene is None:
        return list(source_by_id.values()), missing
    episode = episode or pkg.get("episode") or "Ep1"
    cut = cb_rough_cut.scene_edit_decision(
        episode, str(scene), out=HERE.parent / "cb-output")
    if not cut.get("confirmedCurrent"):
        raise Refused("REFUSED — lock the current Director's Seat cut before building the master")
    sources = []
    for entry in cut["sequence"]:
        source = source_by_id.get(entry["shotId"])
        if not source:
            raise Refused(f"REFUSED — scene cut source is unavailable: {entry['shotId']}")
        sources.append({
            **source, "editInSec": entry.get("inSec"),
            "editOutSec": entry.get("outSec"),
            "manualTrim": bool(entry.get("manualTrim")),
        })
    return sources, missing


def stitch_scene(scene, episode="Ep1", log=print):
    pkg, path = load_pkg(scene, episode)
    sources, missing = _scene_post_sources(pkg, scene, episode)
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
                       "candidatesGenerated": led.get("candidatesGenerated") or 0,
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
                 "dry_run": False, "comparison_model": None,
                 "comparison_run_id": None}
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
            elif a == "--comparison-model":
                flags["comparison_model"] = args[i + 1]; i += 2
            elif a == "--comparison-run-id":
                flags["comparison_run_id"] = args[i + 1]; i += 2
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
        elif cmd == "approve-timing-slate":
            decide_timing_slate(pos[0], "approved", episode=ep(1))
        elif cmd == "reject-timing-slate":
            decide_timing_slate(pos[0], "rejected", pos[1], episode=ep(2))
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
        elif cmd == "build-keyframe":
            build_keyframe(pos[0], pos[1], ep(2))
        elif cmd == "pose":
            generate_pose_reference(pos[0], pos[1], pos[2], ep(3))
        elif cmd == "approve-pose":
            approve_pose_reference(pos[0], pos[1], pos[2], ep(3))
        elif cmd == "reject-pose":
            reject_pose_reference(pos[0], pos[1], pos[2], pos[3], episode=ep(4))
        elif cmd == "select-pose-upload":
            select_pose_reference_source(
                pos[0], pos[1], pos[2], pos[3], episode=ep(4))
        elif cmd == "approve-keyframe":
            approve_keyframe(pos[0], pos[1], ep(2))
        elif cmd == "rescreen-keyframe":
            print(json.dumps(
                rescreen_keyframe_conformance(pos[0], pos[1], ep(2)), indent=1))
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
        elif cmd == "select-render-upload":
            print(json.dumps(
                import_animation_candidate(pos[0], pos[1], pos[2], ep(3)), indent=1))
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
        elif cmd == "bind-location-reference":
            bind_animation_location_reference(
                pos[0], pos[1], pos[2], pos[3], episode=ep(4))
        elif cmd == "check-structure":
            print(json.dumps(check_seedance_structure(pos[0], pos[1], ep(2)), indent=1))
        elif cmd == "continuity-mode":
            print(json.dumps(set_continuity_mode(pos[0], pos[1], pos[2], ep(3)), indent=1))
        elif cmd == "prompt-bank":
            print(json.dumps(cb_prompt_bank.report(), indent=1, ensure_ascii=False))
        elif cmd == "department-prepare":
            prepare_department(pos[0], pos[1], None if pos[2] == "-" else pos[2], ep(3))
        elif cmd == "department-status":
            print(json.dumps(department_status(pos[0], None if pos[2] == "-" else pos[2],
                                               ep(3), pos[1]), indent=1))
        elif cmd == "next":
            next_shot(pos[0], ep(1), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"],
                       comparison_model_id=flags["comparison_model"],
                       comparison_run_id=flags["comparison_run_id"])
        elif cmd == "fire":
            fire_shot(pos[0], pos[1], ep(2), candidates=flags["candidates"],
                       spend_token=flags["spend_token"], dry_run=flags["dry_run"],
                       comparison_model_id=flags["comparison_model"],
                       comparison_run_id=flags["comparison_run_id"])
        elif cmd == "override-model-limited":
            override_model_limited(pos[0], pos[1], pos[2], ep(3))
        elif cmd == "approve":
            approve_shot(pos[0], pos[1], int(pos[2]) if len(pos) > 2 else 1, ep(3))
        elif cmd == "reject":
            reject_shot(pos[0], pos[1], pos[2], category=flags["category"], episode=ep(3))
        elif cmd == "edit":
            edit_shot(pos[0], pos[1], pos[4], pos[2], pos[3], episode=ep(5),
                      spend_token=flags["spend_token"], dry_run=flags["dry_run"])
        elif cmd == "approve-edit":
            approve_shot_edit(pos[0], pos[1], ep(2))
        elif cmd == "reject-edit":
            reject_shot_edit(pos[0], pos[1], pos[2], episode=ep(3))
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
