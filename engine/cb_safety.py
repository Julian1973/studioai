"""Runtime safety layer for the single production path.

Installed by cb_render after its implementation functions are defined. Paid handoffs consume
only current, signed specialist direction. Direction is machine-authored production input, not
a claim that a human approved prose they cannot meaningfully judge. Human approval remains on
observable media: keyframes, performances, animation takes and final masters. Package revisions
remain audit provenance; validity is decided from the exact inputs an artefact actually depends
on. No provider is called from this module by itself.
"""
import hashlib
import json
import math
import os
import pathlib
import re
import uuid

import cb_audio_timing
import cb_audio_authority
import cb_canon
import cb_providers


def selected_voice_recipe(recipes, selected, candidates, current_compiled_hash=None):
    """Resolve a human HEAR choice by audible recipe, not mutable audit metadata."""
    selected_candidate = next(
        (item for item in candidates or []
         if item.get("candidateId") == selected.get("candidateId")), {})
    selected_text = selected_candidate.get("performedText") or selected.get("performedText")
    for recipe in recipes or []:
        if recipe.get("recipeId") != selected.get("recipeId"):
            continue
        same_compiler_record = selected.get("compiledHash") == current_compiled_hash
        same_provider_text = (
            str(selected_text or "") ==
            str(recipe.get("performedText") or ""))
        if same_compiler_record or same_provider_text:
            return recipe
    return None


def install(m):
    original = {name: getattr(m, name) for name in (
        "_resolve_scenelook_prompt", "scenelook_status", "approved_look_prompt",
        "generate_scenelook_plate", "approve_scenelook", "select_scenelook_source",
        "department_status", "prepare_department", "save_department_candidate", "decide_department",
        "_resolve_keyframe_prompt", "_keyframe_input_signature", "voice_shot", "approve_voice", "reject_voice",
        "restore_previous_voice_take", "keyframe_shot", "select_keyframe_source",
        "approve_keyframe", "reject_keyframe", "reassess_keyframe", "_anchor_for", "_resolve_seedance_prompt",
        "check_seedance_structure", "fire_shot", "next_shot", "approve_shot",
        "stitch_scene")}

    stage_profiles = {
        "look": "look",
        "cinematography": "cinematography",
        "voice": "voice",
        "animation": "animation",
        "review-keyframe": "review",
        "review-animation": "review",
        "review-final": "post",
    }
    direction_stages = {"look", "cinematography", "voice", "animation"}
    package_cast_cache = {}

    def package_cast(pkg):
        cached = package_cast_cache.get(id(pkg))
        if cached and cached[0] is pkg:
            return cached[1]
        try:
            roster = cb_canon.load_policy(m.ROOT).get("roster") or {}
        except cb_canon.CanonLockError:
            roster = {}
        declared = set()
        for shot in pkg.get("shots") or []:
            declared.update(str(name) for name in (shot.get("charactersInFrame") or []))
            declared.update(
                str(line.get("speaker")) for line in (shot.get("dialogueLines") or [])
                if line.get("speaker")
            )
            declared.update(
                str(item.get("character")) for item in (shot.get("characterTruthsApproved") or [])
                if item.get("character")
            )
        if declared:
            by_normalized = {
                str(name).lower().replace("’", "'"): name for name in roster
            }
            result = sorted({
                by_normalized[name.lower().replace("’", "'")]
                for name in declared
                if name.lower().replace("’", "'") in by_normalized
            })
        else:
            # Compatibility for pre-contract packages only. Current production packages
            # declare their cast structurally and never need an expensive whole-document scan.
            blob = json.dumps(pkg, ensure_ascii=False).lower().replace("’", "'")
            result = sorted(name for name in roster if re.search(
                r"(?<![a-z0-9])" + re.escape(name.lower().replace("’", "'")) +
                r"(?![a-z0-9])", blob))
        if len(package_cast_cache) > 64:
            package_cast_cache.clear()
        package_cast_cache[id(pkg)] = (pkg, result)
        return result

    def require_canon(pkg, episode, profile=None):
        try:
            # whole-scene cast: a stub role elsewhere in the scene never blocks a shot
            # that does not use it; the shot's own identity/voice checks refuse by name
            lock = cb_canon.require_locked(
                episode, package_cast(pkg), root=m.ROOT, allow_incomplete_cast=True)
        except cb_canon.CanonLockError as exc:
            raise m.Refused(str(exc)) from exc
        if profile:
            digest = (lock.get("profileDigests") or {}).get(profile)
            if not digest:
                raise m.Refused(f"REFUSED — canon profile is unavailable: {profile}")
            return digest
        return lock

    def current_package(scene, episode):
        m._require_show_adapter()
        pkg, path = m.load_pkg(scene, episode)
        m._require_valid(pkg)
        m._require_current_lineage(pkg, scene, episode)
        require_canon(pkg, episode)
        return pkg, path

    def json_sha256(value):
        return hashlib.sha256(json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()

    def stage_runtime_signature(stage):
        keys = {
            "look": ("cinematography",),
            "cinematography": ("cinematography", "dp"),
            "voice": ("voice",),
            "animation": ("animation",),
            "review-keyframe": ("review",),
            "review-animation": ("review",),
            "review-final": ("post",),
        }[stage]
        return {
            "model": m.cb_departments.cb_llm.DIRECTOR_MODEL,
            "skillHashes": {
                key: file_sha256(m.cb_departments.SKILLS[key]) for key in keys
            },
        }

    def ordered_slot_signature(shot, slots_key, anchor, scene, episode,
                               include_technical_controls=True):
        del include_technical_controls
        characters = m._characters_cfg()
        plan = m._provider_attachment_plan(
            shot, slots_key, anchor, scene, episode, characters)
        return [{"slot": item["slot"], "sourceSlot": item["sourceSlot"],
                 "role": item["role"], "view": item.get("view"),
                 "sameCharacterGroup": ((item.get("identity") or {}).get(
                     "turnaroundGroupHash")),
                 "hash": file_sha256(item["path"])}
                for item in plan]

    def department_input_signature(pkg, stage, shot_id, scene, episode):
        """The stable, direct inputs to one specialist decision.

        This deliberately excludes packageRevision and the specialist's own output. A revision
        can therefore carry an unchanged approval forward, while a changed shot, plate,
        reference, voice asset, worker model or runtime skill invalidates only its dependants.
        """
        runtime = stage_runtime_signature(stage)
        canon_digest = require_canon(pkg, episode, stage_profiles[stage])
        if stage == "look":
            return {"stage": stage, **runtime, "canonProfileDigest": canon_digest,
                    "sceneContextHash": json_sha256(m._scene_context(pkg, scene, episode))}

        if stage == "review-final":
            post = m.post_status(pkg, scene, episode)
            selected = (post["candidate"] if post["candidate"]["current"] else
                        post["approved"] if post["approved"]["current"] else None)
            if selected is None:
                raise m.Refused("REFUSED — no current QC-passed post master exists")
            manifest = selected["manifest"]
            return {"stage": stage, **runtime, "canonProfileDigest": canon_digest,
                    "postManifestDigest": manifest.get("manifestDigest"),
                    "postInputSignature": manifest.get("inputSignature"),
                    "masterOutputHashes": {
                        name: asset.get("sha256")
                        for name, asset in (manifest.get("outputs") or {}).items()}}

        shot = m._shot(pkg, shot_id)
        ledger = m._ledger(pkg, shot_id)
        common = {"stage": stage, **runtime, "canonProfileDigest": canon_digest,
                  "shotContractHash": json_sha256(shot)}
        if stage == "cinematography":
            look = scene_status(scene, episode)
            return {**common,
                    "sceneLookHash": ((look.get("active") or {}).get("hash")
                                      if look.get("current") else None),
                    "references": ordered_slot_signature(
                        shot, "keyframeReferenceSlots", None, scene, episode,
                        include_technical_controls=False)}
        if stage == "voice":
            characters = m._characters_cfg()
            return {**common,
                    "dialogueHash": json_sha256(shot.get("dialogueLines") or []),
                    "workingPerformanceHash": json_sha256(ledger.get("workingVoice")),
                    "voiceCardsHash": file_sha256(m.cb_voice_director.VOICE_CARDS_PATH),
                    "voiceRegistersHash": file_sha256(m.cb_voice_director.REGISTERS_PATH),
                    "voiceRulebookHash": file_sha256(m.cb_voice_director.RULEBOOK_PATH),
                    "voiceCompilerVersion": m.cb_voice_director.COMPILER_VERSION,
                    "voiceIds": [
                        (characters.get(m._resolve_char(line["speaker"], characters)) or {})
                        .get("voiceId")
                        for line in (shot.get("dialogueLines") or [])
                    ]}
        if stage == "animation":
            return {**common, **animation_input_signature(
                pkg, shot, scene, episode), **runtime, "stage": stage}
        if stage == "review-keyframe":
            record = ledger.get("keyframeCandidate") or ledger.get("keyframeApproval") or {}
            return {**common, "mediaHash": file_sha256(record.get("path")),
                    "references": ordered_slot_signature(
                        shot, "keyframeReferenceSlots", None, scene, episode)}
        if stage == "review-animation":
            paths = (
                [ledger["approvedTake"]]
                if ledger.get("status") == "approved" and ledger.get("approvedTake")
                else list(ledger.get("candidatePaths") or [])
            )
            if not paths and ledger.get("approvedTake"):
                paths = [ledger["approvedTake"]]
            approval = ledger.get("approval") or {}
            if approval.get("source") == "external-director-accepted":
                return {**common, "mediaHashes": [file_sha256(path) for path in paths],
                        "externalImportApprovalSignature": approval.get("inputSignature"),
                        "externalImportContentHash": approval.get("contentHash"),
                        "generationSignature": None}
            return {**common, "mediaHashes": [file_sha256(path) for path in paths],
                    "generationSignature": animation_generation_signature(
                        pkg, shot, scene, episode)}
        raise m.Refused(f"REFUSED — unknown department stage '{stage}'")

    def department_record_status(pkg, shot_id, stage, scene=None, episode=None):
        """Resolve the current operational record for one department stage.

        A freshly prepared direction is operational when its direct-input signature is current.
        Review stages still require a human-approved record because they judge rendered evidence.
        Legacy approved direction remains valid and is preferred only when there is no newer
        current prepared record.
        """
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        work, _ = m._department_container(pkg, scene, shot_id, stage, episode)
        try:
            expected = department_input_signature(pkg, stage, shot_id, scene, episode)
        except (m.Refused, OSError, ValueError) as exc:
            record = work.get("candidate") or work.get("approved") or {}
            return {"approved": bool(work.get("approved")),
                    "prepared": bool(work.get("candidate")),
                    "current": False, "reason": str(exc), "record": record,
                    "source": None, "expectedInputSignature": None}

        sources = ([
            ("prepared", work.get("candidate") or {}),
            ("approved-legacy", work.get("approved") or {}),
        ] if stage in direction_stages else [
            ("human-approved", work.get("approved") or {}),
        ])
        existing = [(source, record) for source, record in sources
                    if record and record.get("output")]
        current_source, current_record = next(
            ((source, record) for source, record in existing
             if record.get("inputSignature") == expected),
            (None, None),
        )
        if not current_record and stage == "cinematography" and shot_id:
            # Dialogue and voice-performance amendments explicitly preserve SEE.  The
            # shot contract hash includes dialogue, so an otherwise identical DP record
            # must not become stale merely because HEAR wording or cadence changed.
            amendment = next((item for item in reversed(pkg.get("scopedAmendments") or [])
                              if item.get("shotId") == shot_id and
                              item.get("kind") in ("dialogue-correction",
                                                   "voice-contract-correction") and
                              "direction" in (item.get("preservedStages") or [])), None)
            if amendment:
                current_source, current_record = next(
                    ((source, record) for source, record in existing
                     if set(m._signature_diff(record.get("inputSignature"), expected)) <=
                     {"shotContractHash"}),
                    (None, None),
                )
        contract_error = None
        if current_record and stage == "voice":
            try:
                shot = m._shot(pkg, shot_id)
                projected, spoken_lines = m.cb_audio_authority.route_voice_direction(
                    current_record.get("output") or {}, shot.get("dialogueLines") or [])
                direction = m.cb_departments.VoiceDirection.model_validate(
                    projected)
                m.cb_departments.validate_voice_direction(
                    direction, spoken_lines)
            except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                contract_error = str(exc)
                current_source, current_record = None, None
        if current_record and stage == "animation":
            output = current_record.get("output") or {}
            if not str(output.get("providerPrompt") or "").strip():
                contract_error = "animation-provider-prompt-missing"
                current_source, current_record = None, None
            else:
                try:
                    shot = m._shot(pkg, shot_id)
                    creative_shot = m._shot_context(
                        pkg, shot, m._ledger(pkg, shot_id), scene, episode)["shot"]
                    direction = m.cb_departments.AnimationDirection.model_validate(output)
                    compiled = m.cb_departments.compile_animation_provider_prompt(
                        creative_shot, direction)
                    if compiled != output.get("providerPrompt"):
                        contract_error = "animation-compiler-output-stale"
                        current_source, current_record = None, None
                except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                    contract_error = f"animation-compiler-contract-failed: {exc}"
                    current_source, current_record = None, None
        record = current_record or (existing[0][1] if existing else {})
        if current_record:
            return {"approved": bool(work.get("approved")),
                    "prepared": bool(work.get("candidate")),
                    "current": True, "reason": None, "record": current_record,
                    "source": current_source, "expectedInputSignature": expected}
        return {"approved": bool(work.get("approved")),
                "prepared": bool(work.get("candidate")),
                "current": False,
                "reason": ((f"voice-contract-invalid: {contract_error}")
                           if contract_error and stage == "voice" else
                           f"animation-contract-invalid: {contract_error}"
                           if contract_error and stage == "animation" else
                           "direct-input-signature-mismatch" if existing else
                           "not-prepared" if stage in direction_stages else "not-approved"),
                "record": record, "source": None,
                "expectedInputSignature": expected}

    def current_direction_record(pkg, shot_id, stage):
        state = department_record_status(pkg, shot_id, stage)
        rec = state["record"]
        if not state["current"]:
            if (stage in ("voice", "animation") and rec.get("manualCurrentOverride") and
                    (rec.get("output") or {})):
                return rec
            label = {"cinematography": "Cinematography", "voice": "Voice",
                     "animation": "Animation"}.get(stage, stage.title())
            if state["reason"] in ("not-prepared", "not-approved"):
                prefix, suffix = "", ""
            else:
                prefix = f"{label} direction is stale (STALE direct inputs). "
                suffix = f" ({state['reason']})"
            raise m.Refused(
                f"REFUSED — {prefix}Prepare current {label} specialist direction for "
                f"{shot_id} first.{suffix}")
        return rec

    def current_direction_output(pkg, shot_id, stage):
        return current_direction_record(pkg, shot_id, stage)["output"]

    def resolve_scenelook_prompt(scene, episode="Ep1"):
        return look_prompt(scene, episode) or m._compile_scenelook_prompt(scene, episode)

    def scene_status(scene, episode="Ep1"):
        rec = m._load_scenelook_rec(scene, episode)
        approved, candidate = rec.get("approved"), rec.get("candidate")
        def plate_current(record):
            if not record:
                return False
            try:
                current_sig = look_input_signature(
                    scene, episode, record.get("path"), record.get("referencePath"))
                return bool(
                    os.path.exists(record.get("path") or "") and
                    record.get("hash") == file_sha256(record.get("path")) and
                    record.get("inputSignature") == current_sig)
            except (m.Refused, OSError, ValueError):
                return False

        approved_current = plate_current(approved)
        candidate_current = plate_current(candidate)
        if candidate:
            active = candidate if candidate_current else approved if approved_current else None
            return {"status": "working" if candidate_current else "awaiting",
                    "current": bool(active), "active": active,
                    "activeSource": ("working" if candidate_current else
                                     "approved" if approved_current else None),
                    "candidateCurrent": candidate_current,
                    "approvedCurrent": approved_current,
                    "approved": approved, "candidate": candidate,
                    "history": rec.get("history", [])}
        if approved:
            return {"status": "approved" if approved_current else "stale",
                    "current": approved_current,
                    "active": approved if approved_current else None,
                    "activeSource": "approved" if approved_current else None,
                    "candidateCurrent": False, "approvedCurrent": approved_current,
                    "approved": approved, "candidate": None,
                    "history": rec.get("history", [])}
        history = rec.get("history", [])
        status = "rejected" if history and history[-1].get("outcome") == "rejected" else "none"
        return {"status": status, "current": False, "approved": None,
                "candidate": None, "active": None, "activeSource": None,
                "candidateCurrent": False, "approvedCurrent": False,
                "history": history}

    def look_prompt(scene, episode="Ep1"):
        pkg, _ = m.load_pkg(scene, episode)
        state = department_record_status(pkg, None, "look", scene, episode)
        direction = state["record"]
        prompt = ((direction.get("output") or {}).get("providerPrompt") or "").strip()
        return prompt if state["current"] and prompt else None

    def file_sha256(path):
        try:
            return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        except Exception:
            return None

    def look_input_signature(scene, episode, plate_path=None, reference_path=None):
        """Every direct Scene Look input, including current signed direction and files."""
        pkg, _ = m.load_pkg(scene, episode)
        prompt = look_prompt(scene, episode) or ""
        return {"canonProfileDigest": require_canon(pkg, episode, "look"),
                "briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
                "referenceHashes": ({pathlib.Path(reference_path).name: file_sha256(reference_path)}
                                    if reference_path else {}),
                "plateHash": file_sha256(plate_path) if plate_path else None}

    def generate_look(scene, episode="Ep1", reference_path=None, log=print):
        pkg, _ = current_package(scene, episode)
        if not look_prompt(scene, episode):
            raise m.Refused("REFUSED — Prepare current Look Development direction first.")
        result = original["generate_scenelook_plate"](
            scene, episode, reference_path=reference_path, log=log)
        rec = m._load_scenelook_rec(scene, episode)
        rec["candidate"]["packageRevision"] = pkg.get("revision")
        rec["candidate"]["inputSignature"] = look_input_signature(
            scene, episode, rec["candidate"].get("path"), reference_path)
        m._save_scenelook_rec(rec, scene, episode)
        return result

    def approve_look(scene, episode="Ep1", reviewed_by="Julian", log=print):
        current_package(scene, episode)
        rec = m._load_scenelook_rec(scene, episode)
        candidate = rec.get("candidate") or {}
        expected = look_input_signature(
            scene, episode, candidate.get("path"), candidate.get("referencePath"))
        if candidate.get("inputSignature") != expected:
            raise m.Refused("REFUSED — current Look direction changed after this candidate was generated")
        return original["approve_scenelook"](scene, episode, reviewed_by, log)

    def select_look(scene, mode, episode="Ep1", upload_path=None, library_path=None,
                    reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode)
        if not look_prompt(scene, episode):
            # Selecting a real library/upload plate is already the user's explicit Scene
            # World action. Prepare and sign the zero-media-spend specialist brief behind
            # that action instead of exposing another departmental gate in the UI.
            prepare_department(scene, "look", None, episode, log)
            decide_department(
                scene, "look", "approved", None,
                "Automatically prepared for the selected Scene Look source.", episode,
                "StudioAI", log)
            pkg, _ = current_package(scene, episode)
        result = original["select_scenelook_source"](
            scene, mode, episode, upload_path, library_path, reviewed_by, log)
        rec = m._load_scenelook_rec(scene, episode)
        rec["candidate"]["packageRevision"] = pkg.get("revision")
        rec["candidate"]["inputSignature"] = look_input_signature(
            scene, episode, rec["candidate"].get("path"))
        m._save_scenelook_rec(rec, scene, episode)
        return result

    def prepare_department(scene, stage, shot_id=None, episode="Ep1", log=print):
        pkg, path = current_package(scene, episode)
        if stage == "animation":
            cinematography = department_record_status(
                pkg, shot_id, "cinematography", scene, episode)
            if not cinematography["current"]:
                log("WATCH PREPARATION — refreshing Cinematography direction first "
                    "(no media generation or provider spend)")
                prepare_department(
                    scene, "cinematography", shot_id, episode, log)
                pkg, path = current_package(scene, episode)
        work, save_extra = m._department_container(
            pkg, scene, shot_id, stage, episode)
        existing = work.get("candidate") or {}
        if existing and stage in direction_stages:
            expected = department_input_signature(
                pkg, stage, shot_id, scene, episode)
            if stage == "voice" and existing.get("scopedDialogueCarryForward"):
                try:
                    shot = m._shot(pkg, shot_id)
                    projected, spoken_lines = m.cb_audio_authority.route_voice_direction(
                        existing.get("output") or {}, shot.get("dialogueLines") or [])
                    direction = m.cb_departments.VoiceDirection.model_validate(projected)
                    m.cb_departments.validate_voice_direction(direction, spoken_lines)
                    existing["inputSignature"] = expected
                    existing["packageRevision"] = pkg.get("revision")
                    existing.pop("scopedDialogueCarryForward", None)
                    existing.pop("carriedDialogueIndex", None)
                    save_extra(); m._save(pkg, path)
                    log("VOICE DIRECTION — carried the current acting direction across "
                        "the scoped word change; no model or media provider called")
                    return existing
                except (KeyError, TypeError, ValueError, RuntimeError):
                    pass
            invalidation_reason = None
            if existing.get("inputSignature") != expected:
                invalidation_reason = "direct inputs changed before replacement preparation"
            elif stage == "voice":
                try:
                    shot = m._shot(pkg, shot_id)
                    projected, spoken_lines = m.cb_audio_authority.route_voice_direction(
                        existing.get("output") or {}, shot.get("dialogueLines") or [])
                    direction = m.cb_departments.VoiceDirection.model_validate(
                        projected)
                    m.cb_departments.validate_voice_direction(
                        direction, spoken_lines)
                except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                    invalidation_reason = f"voice contract failed: {exc}"
            elif stage == "animation":
                try:
                    shot = m._shot(pkg, shot_id)
                    creative_shot = m._shot_context(
                        pkg, shot, m._ledger(pkg, shot_id), scene, episode)["shot"]
                    output = existing.get("output") or {}
                    direction = m.cb_departments.AnimationDirection.model_validate(output)
                    compiled = m.cb_departments.compile_animation_provider_prompt(
                        creative_shot, direction)
                    if compiled != output.get("providerPrompt"):
                        invalidation_reason = "deterministic animation compiler changed"
                except (KeyError, TypeError, ValueError, RuntimeError) as exc:
                    invalidation_reason = f"animation compiler contract failed: {exc}"
            if invalidation_reason:
                work.setdefault("history", []).append({
                    **existing,
                    "outcome": "invalidated",
                    "invalidatedAt": m._now(),
                    "invalidationReason": invalidation_reason,
                })
                work["candidate"] = None
                save_extra(); m._save(pkg, path)
                log(f"DEPARTMENT INVALIDATED — archived stale {stage} direction before "
                    "preparing its replacement (no media generated)")
        original["prepare_department"](scene, stage, shot_id, episode, log)
        pkg, path = m.load_pkg(scene, episode)
        work, save_extra = m._department_container(pkg, scene, shot_id, stage, episode)
        work["candidate"]["packageRevision"] = pkg.get("revision")
        work["candidate"]["inputSignature"] = department_input_signature(
            pkg, stage, shot_id, scene, episode)
        save_extra(); m._save(pkg, path)
        return work["candidate"]

    def require_current_candidate(scene, stage, shot_id, episode):
        pkg, _ = current_package(scene, episode)
        work, _ = m._department_container(pkg, scene, shot_id, stage, episode)
        candidate = work.get("candidate") or {}
        if not candidate:
            raise m.Refused(f"REFUSED — {stage} has no specialist candidate awaiting a decision")
        expected = department_input_signature(pkg, stage, shot_id, scene, episode)
        if candidate.get("inputSignature") != expected:
            raise m.Refused(
                f"REFUSED — the {stage} candidate is stale because its direct inputs changed")
        return pkg

    def department_status(scene, shot_id=None, episode="Ep1", stage=None):
        result = original["department_status"](scene, shot_id, episode, stage)
        if not stage:
            return result
        pkg, _ = m.load_pkg(scene, episode)
        approval = department_record_status(pkg, shot_id, stage, scene, episode)
        candidate = result.get("candidate") or {}
        candidate_current = False
        if candidate:
            try:
                candidate_current = candidate.get("inputSignature") == (
                    department_input_signature(pkg, stage, shot_id, scene, episode))
            except (m.Refused, OSError, ValueError):
                candidate_current = False
        return {**result, "approvalCurrent": bool(
                    approval["current"] and approval.get("source") in
                    ("approved-legacy", "human-approved")),
                "approvalReason": approval["reason"],
                "candidateCurrent": candidate_current,
                "directionReady": approval["current"],
                "directionSource": approval.get("source")}

    def save_department(scene, stage, text=None, lines=None, shot_id=None,
                        episode="Ep1", reviewed_by="Julian", log=print):
        require_current_candidate(scene, stage, shot_id, episode)
        return original["save_department_candidate"](
            scene, stage, text, lines, shot_id, episode, reviewed_by, log)

    def decide_department(scene, stage, verdict, shot_id=None, note="", episode="Ep1",
                          reviewed_by="Julian", log=print):
        require_current_candidate(scene, stage, shot_id, episode)
        return original["decide_department"](
            scene, stage, verdict, shot_id, note, episode, reviewed_by, log)

    def keyframe_prompt(pkg, shot):
        direction = current_direction_output(pkg, shot["shotId"], "cinematography")
        prompt = m._compile_keyframe_integration_prompt(direction, shot)
        pending = (m._ledger(pkg, shot["shotId"]).get("pendingKeyframeCorrection") or {})
        correction = str(pending.get("reason") or "").strip()
        if correction:
            prompt += (
                "\n\n[Director Iteration]\nCorrect only this observed issue in the next "
                f"revision: {correction}\nPreserve every successful identity, canon, "
                "geography, lighting, reference-role and continuity decision from the "
                "current signed direction."
            )
        return prompt

    def voice_lines(pkg, shot):
        output = current_direction_output(pkg, shot["shotId"], "voice")
        output, locked = cb_audio_authority.route_voice_direction(
            output, shot.get("dialogueLines") or [])
        if not locked:
            return []
        ledger = m._ledger(pkg, shot["shotId"])
        try:
            track = m.cb_voice_director.compile_track(output, locked)
        except m.cb_voice_director.VoiceContractError as exc:
            raise m.Refused(str(exc)) from exc
        working_by_occurrence = {
            line.get("dialogueOccurrenceId"): line
            for line in ((ledger.get("workingVoice") or {}).get("lines") or [])
            if line.get("dialogueOccurrenceId")
        }
        selected = ((ledger.get("voiceAuditions") or {}).get("selected") or {})
        selections = ledger.get("voiceAuditionSelections") or {}
        audition_candidates = ((ledger.get("voiceAuditions") or {}).get("candidates") or [])
        generated_by_occurrence = {
            line.get("dialogueOccurrenceId"): line
            for line in (ledger.get("voGeneratedFrom") or [])
            if line.get("dialogueOccurrenceId")
        }
        result = []
        for item, source in zip(track["lines"], locked):
            recipes = item.get("takeRecipes") or []
            occurrence_id = source.get("dialogueOccurrenceId")
            line_selected = dict(selections.get(occurrence_id) or selected)
            # The audition panel contains candidates for only its currently displayed
            # line. Preserve earlier human choices across a direction refresh by using
            # the accepted provider request snapshot as their audible-text evidence.
            generated_line = generated_by_occurrence.get(occurrence_id) or {}
            if generated_line.get("text") and not line_selected.get("performedText"):
                line_selected["performedText"] = generated_line["text"]
            recipe = selected_voice_recipe(
                recipes, line_selected, audition_candidates, item.get("compiledHash"))
            if len(recipes) > 1 and recipe is None:
                exact_text = source.get("exactText") if source.get("exactText") is not None else source.get("text")
                raise m.Refused(
                    f"REFUSED - choose a HEAR audition for {exact_text} first")
            recipe = recipe or next((value for value in recipes if value.get("primary")), recipes[0])
            # Julian's explicit HEAR edit is the final audible text authority. The Voice
            # Director still owns voice identity, settings, context runway and recipe
            # provenance, but may not silently restore tags or punctuation that the human
            # removed to correct a glitch or cadence fault.
            working_line = working_by_occurrence.get(source.get("dialogueOccurrenceId"))
            provider_text = m.cb_gen._eleven_voice_text(
                (working_line or {}).get("text") or recipe["performedText"])
            result.append({
                "dialogueOccurrenceId": source.get("dialogueOccurrenceId"),
                "sourceEventId": source.get("sourceEventId"),
                "speaker": source["speaker"],
                "text": provider_text,
                "voiceId": item["voiceId"],
                "modelId": item["modelId"],
                "voiceSettings": item["voiceSettings"],
                "previousText": m.cb_gen._eleven_voice_text(item["previousText"]),
                "compiledHash": item["compiledHash"],
                "recipeId": recipe["recipeId"],
                "voiceTreatment": item.get("voiceTreatment", "single_voice"),
                "chorusMembers": item.get("chorusMembers") or [],
                "voiceIds": item.get("voiceIds") or [item["voiceId"]],
            })
        return result

    def voice_signature(pkg, shot, lines):
        characters = m._characters_cfg()
        generated_by_occurrence = {
            line.get("dialogueOccurrenceId"): line for line in (lines or [])
            if line.get("dialogueOccurrenceId")
        }
        ids = []
        for line in (shot.get("dialogueLines") or []):
            generated = generated_by_occurrence.get(line.get("dialogueOccurrenceId")) or {}
            if generated.get("voiceTreatment") == "group_chorus":
                ids.extend(generated.get("voiceIds") or [])
            else:
                ids.append((characters.get(
                    m._resolve_char(line["speaker"], characters)) or {}).get("voiceId"))
        episode = pkg.get("episode") or pkg.get("episodeId") or "Ep1"
        return {"canonProfileDigest": require_canon(pkg, episode, "voice"),
                "dialogueHash": hashlib.sha256(json.dumps(
                    shot.get("dialogueLines") or [], sort_keys=True,
                    ensure_ascii=False).encode()).hexdigest(),
                "performanceHash": hashlib.sha256(json.dumps(
                    lines, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                "voiceCardsHash": file_sha256(m.cb_voice_director.VOICE_CARDS_PATH),
                "voiceRegistersHash": file_sha256(m.cb_voice_director.REGISTERS_PATH),
                "voiceRulebookHash": file_sha256(m.cb_voice_director.RULEBOOK_PATH),
                "voiceCompilerVersion": m.cb_voice_director.COMPILER_VERSION,
                "pronunciationOverrides": m.cb_gen.ELEVEN_PRONUNCIATION_OVERRIDES,
                "voiceIds": ids}

    def voice_provider_projection(lines):
        """Only fields capable of changing the audible provider request belong here."""
        keys = (
            "dialogueOccurrenceId", "sourceEventId", "speaker", "text", "voiceId",
            "modelId", "voiceSettings", "previousText", "recipeId",
        )
        return [{key: line.get(key) for key in keys} for line in lines or []]

    def voice_approval_status(pkg, shot, scene=None, episode=None):
        if not cb_audio_authority.spoken_dialogue_lines(shot):
            return {"required": False, "approved": True, "current": True, "reason": None,
                    "record": {}, "expectedInputSignature": None}
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        ledger = m._ledger(pkg, shot["shotId"])
        approval = ledger.get("voiceApproval") or {}
        # The accepted media bundle is the authority after HEAR. A later duration-only
        # visual edit may make an unapproved Voice Director draft stale, but it cannot
        # retroactively invalidate the exact provider request Julian heard and accepted.
        # Rebuild freshness from that recorded request when current draft resolution fails.
        try:
            current_lines = voice_lines(pkg, shot)
        except (m.Refused, OSError, ValueError):
            current_lines = ledger.get("voGeneratedFrom") or []
        try:
            signature = voice_signature(pkg, shot, current_lines)
        except (m.Refused, OSError, ValueError) as exc:
            return {"required": True, "approved": bool(approval.get("approved")),
                    "current": False, "reason": str(exc), "record": approval,
                    "expectedInputSignature": None}
        path = ledger.get("voPath")
        raw_path = ledger.get("voRawPath")
        timing_path = ledger.get("voTimingPath")
        placement_path = ledger.get("voPlacementPath")
        approved_signature = approval.get("inputSignature") or {}
        signature_without_performance = {
            key: value for key, value in signature.items() if key != "performanceHash"}
        approved_without_performance = {
            key: value for key, value in approved_signature.items()
            if key != "performanceHash"}
        provider_equivalent = (
            signature_without_performance == approved_without_performance and
            voice_provider_projection(ledger.get("voGeneratedFrom") or []) ==
            voice_provider_projection(current_lines))
        signature_matches = approved_signature == signature or provider_equivalent
        current = bool(
            approval.get("approved") and path and os.path.exists(path) and
            raw_path and os.path.exists(raw_path) and
            timing_path and os.path.exists(timing_path) and
            placement_path and os.path.exists(placement_path) and
            approval.get("path") == path and
            signature_matches and
            approval.get("contentHash") == file_sha256(path) and
            approval.get("rawContentHash") == file_sha256(raw_path) and
            approval.get("timingContentHash") == file_sha256(timing_path) and
            approval.get("placementContentHash") == file_sha256(placement_path))
        return {"required": True, "approved": bool(approval.get("approved")),
                "current": current,
                "reason": None if current else "voice-approval-input-or-content-mismatch",
                "providerEquivalentContract": provider_equivalent,
                "record": approval, "expectedInputSignature": signature}

    def animation_input_signature(pkg, shot, scene, episode):
        """Bind Animation direction to every direct visual and performance input.

        The signature deliberately stores hashes, never media bytes. A changed plate,
        opening frame, character reference, voice take or package contract makes a
        prepared/approved prompt stale without making a provider call.
        """
        ledger = m._ledger(pkg, shot["shotId"])
        anchor = m._anchor_for(pkg, shot)
        shot = m._with_effective_reference_slots(
            pkg, shot, "referenceSlots", scene, episode)
        plan = m._provider_attachment_plan(
            shot, "referenceSlots", anchor, scene, episode, m._characters_cfg())
        refs = [item["path"] for item in plan]
        look = scene_status(scene, episode)
        voice = voice_approval_status(pkg, shot, scene, episode)
        has_spoken_dialogue = bool(cb_audio_authority.spoken_dialogue_lines(shot))
        if has_spoken_dialogue and not voice["current"]:
            raise m.Refused(
                f"REFUSED — {shot['shotId']}'s approved voice is missing or stale")
        voice_approval = voice["record"]
        opening_contract = (((ledger.get("keyframeApproval") or {}).get("promptContract") or {})
                            .get("directionContract") or {})
        return {
            "canonProfileDigest": require_canon(pkg, episode, "animation"),
            "shotHash": hashlib.sha256(json.dumps(
                shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "openingFrameHash": file_sha256(anchor),
            "openingStageContractHash": json_sha256(opening_contract),
            "sceneLookHash": ((look.get("active") or {}).get("hash")
                              if look.get("current") else None),
            "referenceOrder": [item["slot"] for item in plan],
            "referenceBindings": [
                {"slot": item["slot"], "sourceSlot": item["sourceSlot"],
                 "role": item["role"], "view": item.get("view"),
                 "sameCharacterGroup": ((item.get("identity") or {}).get(
                     "turnaroundGroupHash"))}
                for item in plan],
            "referenceHashes": [file_sha256(path) for path in refs],
            "voiceHash": (file_sha256(ledger.get("voPath"))
                          if has_spoken_dialogue else None),
            "voiceApprovalSignature": (voice_approval.get("inputSignature")
                                       if has_spoken_dialogue else None),
            "directorFeedbackHash": json_sha256({
                "workingPrompt": ledger.get("workingSeedancePrompt"),
                "watchFeedback": ledger.get("watchDirectorFeedback"),
                "latestRejection": ((ledger.get("rejections") or [])[-1]
                                    if ledger.get("rejections") else None),
            }),
        }

    def animation_generation_signature(pkg, shot, scene, episode, fast=False,
                                       comparison_model_id=None,
                                       comparison_run_id=None,
                                       include_audio_reference=True,
                                       generate_audio=True):
        direction = current_direction_record(pkg, shot["shotId"], "animation")
        # The working prompt is the prompt the director has actually iterated.
        # The signature must audit the same text that fire_shot will send; using
        # only the older approved compiler output makes the gate score a
        # different prompt from the one shown in the studio.
        ledger = m._ledger(pkg, shot["shotId"])
        working = ledger.get("workingSeedancePrompt") or {}
        prompt = str(
            working.get("text")
            or (direction.get("output") or {}).get("providerPrompt")
            or ""
        ).strip()
        if not prompt:
            raise m.Refused(
                f"REFUSED — current Animation direction for {shot['shotId']} has no prompt")
        anchor = m._anchor_for(pkg, shot)
        shot = m._with_effective_reference_slots(
            pkg, shot, "referenceSlots", scene, episode)
        refs = ordered_slot_signature(shot, "referenceSlots", anchor, scene, episode)
        voice = voice_approval_status(pkg, shot, scene, episode)
        has_spoken_dialogue = bool(cb_audio_authority.spoken_dialogue_lines(shot))
        if has_spoken_dialogue and not voice["current"]:
            raise m.Refused(
                f"REFUSED — {shot['shotId']}'s approved voice is missing or stale")
        try:
            plan = m._animation_execution_plan(
                pkg, {**shot, "seedancePrompt": prompt}, ledger,
                m._slot_paths(shot, "referenceSlots", anchor, scene, episode,
                              m._characters_cfg()),
                anchor, fast, comparison_model_id, comparison_run_id,
                materialize_audio=False,
                include_audio_reference=include_audio_reference,
                generate_audio=generate_audio)
        except (cb_providers.ProviderCapabilityError,
                m.cb_seedance_transport.TransportPlanError) as exc:
            raise m.Refused(f"REFUSED — provider capability: {exc}") from exc
        provider = plan["segments"][0]["contract"]
        return {
            "canonProfileDigest": require_canon(pkg, episode, "animation"),
            "shotContractHash": json_sha256(shot),
            "animationDirectionSignature": direction.get("inputSignature"),
            "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "audioReferencePolicy": ("guide" if include_audio_reference else
                                     ("native" if generate_audio else "post-only")),
            "openingFrameHash": file_sha256(anchor),
            "references": refs,
            "audioHash": (file_sha256(ledger.get("voPath"))
                          if has_spoken_dialogue else None),
            "durationSec": shot.get("durationSec"),
            "comparisonModelId": comparison_model_id,
            "comparisonRunId": comparison_run_id,
            "executionPlanHash": json_sha256(plan),
            "provider": provider["provider"],
            "providerModelId": provider["providerModelId"],
            "modelVersion": provider["modelVersion"],
            "transport": provider["transport"],
            "endpoint": provider["endpoint"],
            "resolution": provider["resolution"],
            "capabilityVerifiedAt": provider["capabilityVerifiedAt"],
            "tier": "fast" if fast else "standard",
        }

    def animation_approval_status(pkg, shot, scene=None, episode=None):
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        ledger = m._ledger(pkg, shot["shotId"])
        approval = ledger.get("approval") or {}
        recorded = approval.get("inputSignature")
        if approval.get("source") == "external-director-accepted":
            try:
                expected = external_import_input_signature(
                    pkg, shot, scene, episode, approval.get("contentHash"),
                    {"digest": approval.get("provenanceDigest")})
            except (m.Refused, OSError, ValueError) as exc:
                return {"approved": bool(approval.get("approved")), "current": False,
                        "reason": str(exc), "record": approval,
                        "expectedInputSignature": None}
            take = ledger.get("approvedTake")
            harvest = ledger.get("harvestFrame")
            current = bool(
                ledger.get("status") == "approved" and approval.get("approved") and
                take and harvest and os.path.exists(take) and os.path.exists(harvest) and
                recorded == expected and approval.get("contentHash") == file_sha256(take) and
                approval.get("harvestHash") == file_sha256(harvest))
            return {"approved": bool(approval.get("approved")), "current": current,
                    "reason": None if current else
                    "external-animation-approval-input-or-content-mismatch",
                    "record": approval, "expectedInputSignature": expected}
        fast = bool((recorded or {}).get("tier") == "fast")
        comparison_model_id = (recorded or {}).get("comparisonModelId")
        comparison_run_id = (recorded or {}).get("comparisonRunId")
        try:
            expected = animation_generation_signature(
                pkg, shot, scene, episode, fast=fast,
                comparison_model_id=comparison_model_id,
                comparison_run_id=comparison_run_id)
        except (m.Refused, OSError, ValueError) as exc:
            return {"approved": bool(approval.get("approved")), "current": False,
                    "reason": str(exc), "record": approval,
                    "expectedInputSignature": None}
        take = ledger.get("approvedTake")
        harvest = ledger.get("harvestFrame")
        current = bool(
            ledger.get("status") == "approved" and approval.get("approved") and
            take and harvest and os.path.exists(take) and os.path.exists(harvest) and
            recorded == expected and approval.get("contentHash") == file_sha256(take) and
            approval.get("harvestHash") == file_sha256(harvest))
        return {"approved": bool(approval.get("approved")), "current": current,
                "reason": None if current else "animation-approval-input-or-content-mismatch",
                "record": approval, "expectedInputSignature": expected}

    def external_import_input_signature(pkg, shot, scene, episode, source_hash, provenance):
        """Current graph for a human-accepted finished clip imported from another surface.

        It deliberately binds picture approval to canon, shot contract and the bytes of the
        opening image that actually fed the finished clip, without claiming the clip was
        generated by the current provider request or voice bundle.  A later preflight rule
        must not retroactively prevent the Director from accepting already-rendered picture.
        Dialogue remains a required post lane recorded by import_approved_take.
        """
        provenance_digest = ((provenance or {}).get("digest") if isinstance(provenance, dict)
                             and set(provenance) == {"digest"} else
                             json_sha256(provenance or {}))
        ledger = m._ledger(pkg, shot["shotId"])
        if shot.get("sourceType") == "opener":
            opening_path = (ledger.get("keyframeApproval") or {}).get("path")
        else:
            source_shot = shot.get("sourceShot") or shot.get("sourceShotId")
            source_ledger = m._ledger(pkg, source_shot)
            opening_path = source_ledger.get("harvestFrame")
        if not opening_path or not os.path.isfile(opening_path):
            raise m.Refused(
                "REFUSED — the finished clip's opening-image evidence is missing")
        return {
            "policyVersion": "external-director-accepted-v1",
            "canonProfileDigest": require_canon(pkg, episode, "animation"),
            "shotContractHash": json_sha256(shot),
            "openingFrameHash": file_sha256(opening_path),
            "sourceContentHash": source_hash,
            "provenanceDigest": provenance_digest,
        }

    def voice_shot(pkg, path, shot_id, episode="Ep1", log=print):
        m._require_valid(pkg)
        m._require_current_lineage(pkg, pkg.get("sceneNumber"), episode)
        require_canon(pkg, episode, "voice")
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        direction = current_direction_output(pkg, shot_id, "voice")
        direction, spoken_lines = cb_audio_authority.route_voice_direction(
            direction, shot.get("dialogueLines") or [])
        if not spoken_lines:
            return None
        m._require_confirmed_billing("elevenlabs")
        try:
            compiled_track = m.cb_voice_director.compile_track(direction, spoken_lines)
        except m.cb_voice_director.VoiceContractError as exc:
            raise m.Refused(str(exc)) from exc

        selected = ((ledger.get("voiceAuditions") or {}).get("selected") or {})
        selections = ledger.get("voiceAuditionSelections") or {}
        selected_hashes = set(ledger.get("voiceAuditionSelectionsByHash") or [])
        if selected.get("compiledHash"):
            selected_hashes.add(selected["compiledHash"])
        selected_occurrences = set()
        for occurrence_id, choice in selections.items():
            if choice.get("compiledHash"):
                selected_hashes.add(choice["compiledHash"])
            selected_occurrences.add(occurrence_id)

        def _line_has_hear_selection(line):
            if line.get("compiledHash") in selected_hashes:
                return True
            choice = selections.get(line.get("dialogueOccurrenceId"))
            if not choice:
                return False
            return selected_voice_recipe(
                line.get("takeRecipes") or [], choice, [], line.get("compiledHash")) is not None

        audition_line = next(
            (line for line in compiled_track["lines"]
             if len(line.get("takeRecipes") or []) > 1
             and not _line_has_hear_selection(line)),
            None)
        selection_current = bool(audition_line is None)
        if audition_line and not selection_current:
            requests = m.cb_voice_director.emit_v3_requests(audition_line, max_requests=2)
            run_id = uuid.uuid4().hex[:8]
            bundle = {
                "status": "generating", "runId": run_id,
                "dialogueOccurrenceId": audition_line["dialogueOccurrenceId"],
                "character": audition_line["character"],
                "archetypeId": audition_line["archetype"]["archetypeId"],
                "compiledHash": audition_line["compiledHash"],
                "postDirectionAudit": audition_line["postDirectionAudit"],
                "candidateCount": len(requests), "candidates": [],
                "startedAt": m._now(), "selected": None,
            }
            ledger["voiceAuditions"] = bundle
            m._save(pkg, path)
            for index, request in enumerate(requests, start=1):
                candidate_id = f"{run_id}-{request['recipeId']}-{request['takeNumber']}"
                out = m.MEDIA / f"{episode}_{shot_id}_hear_{candidate_id}.mp3"
                body = request["body"]
                log(
                    f"VOICE DIRECTOR - {shot_id}: audition {index}/{len(requests)} "
                    f"{request['label']} take {request['takeNumber']}")
                m.cb_gen.eleven_tts(
                    body["text"], request["voiceId"], model_id=body["model_id"],
                    out=str(out), stability=body["voice_settings"]["stability"],
                    similarity_boost=body["voice_settings"]["similarity_boost"],
                    style=body["voice_settings"]["style"],
                    previous_text=request.get("contextRunway"), production_route="cb_render")
                bundle["candidates"].append({
                    "candidateId": candidate_id,
                    "requestId": request["requestId"],
                    "recipeId": request["recipeId"],
                    "label": request["label"],
                    "primary": request["primary"],
                    "takeNumber": request["takeNumber"],
                    "performedText": body["text"],
                    "path": str(out),
                    "compiledHash": audition_line["compiledHash"],
                })
                m._save(pkg, path)
            bundle["status"] = "ready_for_hear_verdict"
            bundle["completedAt"] = m._now()
            m._save(pkg, path)
            log(f"VOICE DIRECTOR - {shot_id}: {len(requests)} auditions ready for Julian")
            return str(bundle["candidates"][0]["path"])

        approval = ledger.get("voiceApproval") or {}
        if approval.get("approved"):
            scene_id = str(pkg.get("scene") or pkg.get("sceneNumber") or "")
            # Compare like with like: the approval carries voice_signature(...) and only
            # voice_approval_status knows its equivalence rules. Before 2026-09-03 (evening) this
            # compared it against department_input_signature (a different shape), so EVERY
            # regenerate superseded a current approval with a false reason on record.
            try:
                approval_current = bool(
                    voice_approval_status(pkg, shot, scene_id, episode).get("current"))
            except Exception:
                approval_current = True
            if not approval_current:
                # The approval is stale against the current signed inputs (a canon re-lock, a
                # recast, new direction). Accept would refuse it and nothing could replace it:
                # supersede it here, on the record, and build the current track (2026-09-03).
                history = list(ledger.get("supersededVoiceApprovals") or [])
                history.append({**approval, "supersededAt": m._now(),
                                "supersededReason": "direct voice inputs changed since approval"})
                ledger["supersededVoiceApprovals"] = history
                ledger["voiceApproval"] = {**approval, "approved": False,
                                           "supersededAt": m._now()}
                m._save(pkg, path)
                log(f"VOICE APPROVAL SUPERSEDED - {shot_id}: the approved track no longer matches "
                    "the current signed voice inputs; building the current track")
            else:
                raise m.Refused(
                    f"REFUSED - {shot_id}'s complete voice track is already approved; "
                    "auditions may be heard, but reject the approved track before replacing it")
        lines, turns = voice_lines(pkg, shot), []
        for performance in lines:
            turns.append({"text": performance["text"], "voice_id": performance["voiceId"]})
        m.MEDIA.mkdir(parents=True, exist_ok=True)
        take_id = uuid.uuid4().hex[:8]
        raw_out = m.MEDIA / f"{episode}_{shot_id}_vo_raw_candidate_{take_id}.mp3"
        out = m.MEDIA / f"{episode}_{shot_id}_vo_candidate_{take_id}.wav"
        previous = ledger.get("voPath")
        failed = ledger.get("voicePlacementFailure") or {}
        reusable_raw = pathlib.Path(failed.get("rawPath") or "")
        reusable_timing = pathlib.Path(failed.get("timingPath") or "")
        reuse_failed_take = bool(
            failed.get("generatedFrom") == lines and reusable_raw.is_file() and
            reusable_timing.is_file())
        if reuse_failed_take:
            raw_out, timing_path = reusable_raw, reusable_timing
            log(f"VOICE — {shot_id}: recovering the existing paid take; no provider call")
        else:
            stability = min(float(item.get("voiceSettings", {}).get("stability", 0.3))
                            for item in lines)
            m.cb_gen.eleven_dialogue(
                turns, out=str(raw_out), stability=stability,
                generation_kind="regeneration" if previous else "generation",
                production_route="cb_render")
            timing_path = cb_audio_timing.dialogue_timing_path(raw_out)
            raw_out, timing_path = m.cb_gen.replace_group_chorus_segments(
                raw_out, timing_path, lines, production_route="cb_render")
            raw_out, timing_path = pathlib.Path(raw_out), pathlib.Path(timing_path)
        timing_by_occurrence = {
            line.get("dialogueOccurrenceId"): line
            for line in (compiled_track.get("lines") or [])
            if line.get("dialogueOccurrenceId")
        }
        timed_dialogue_lines = []
        for original in spoken_lines:
            timed = dict(original)
            directed = timing_by_occurrence.get(original.get("dialogueOccurrenceId")) or {}
            if timed.get("startSec") is None and directed.get("startsAtSec") is not None:
                timed["startsAtSec"] = directed.get("startsAtSec")
            if timed.get("endSec") is None and directed.get("estimatedDurationSec") is not None:
                timed["estimatedDurationSec"] = directed.get("estimatedDurationSec")
            timed_dialogue_lines.append(timed)
        try:
            placement = cb_audio_timing.render_timed_dialogue_master(
                raw_out, timing_path, timed_dialogue_lines,
                shot.get("durationSec"), out)
        except cb_audio_timing.AudioTimingError as exc:
            current_duration = float(shot.get("durationSec") or 0)
            cascade = None
            try:
                required_duration = cb_audio_timing.minimum_master_duration(
                    raw_out, timing_path, timed_dialogue_lines)
            except cb_audio_timing.AudioTimingError:
                cascade = cb_audio_timing.cascade_retime_for_natural_performance(
                    raw_out, timing_path, timed_dialogue_lines)
                required_duration = cascade["requiredDurationSec"]
            if cascade and required_duration <= current_duration + 0.001:
                retimed_duration = current_duration
            else:
                try:
                    retimed_duration = cb_audio_timing.natural_master_duration(
                        required_duration)
                except cb_audio_timing.AudioTimingError:
                    retimed_duration = None
            if retimed_duration is not None:
                if cascade:
                    timed_dialogue_lines = cascade["lines"]
                shot["durationSec"] = retimed_duration
                ledger.setdefault("durationRetimes", []).append({
                    "at": m._now(),
                    "fromSec": current_duration,
                    "toSec": retimed_duration,
                    "reason": (
                        "Preserve the approved final dialogue take without clipping or "
                        "time compression, using the available landing room."),
                    "source": "ElevenLabs-v3-natural-performance",
                    "providerCalled": False,
                    "dialogueStartChanges": (cascade or {}).get("changes", []),
                })
                for stage in ("cinematography", "voice"):
                    work = ((ledger.get("departmentWork") or {}).get(stage) or {})
                    record = work.get("candidate") or work.get("approved")
                    if record and record.get("output"):
                        record["inputSignature"] = department_input_signature(
                            pkg, stage, shot_id, pkg.get("sceneNumber"), episode)
                        record["durationCarryForward"] = {
                            "at": m._now(), "fromSec": current_duration,
                            "newDurationSec": retimed_duration,
                            "reason": "Approved direction carried across timing-only retime",
                        }
                animation_work = ((ledger.get("departmentWork") or {}).get("animation") or {})
                if animation_work.get("candidate"):
                    animation_work.setdefault("history", []).append({
                        **animation_work["candidate"],
                        "outcome": "invalidated",
                        "invalidatedAt": m._now(),
                        "invalidationReason": "voice timing extended the shot duration",
                    })
                    animation_work["candidate"] = None
                placement = cb_audio_timing.render_timed_dialogue_master(
                    raw_out, timing_path, timed_dialogue_lines,
                    retimed_duration, out)
                if retimed_duration > current_duration + 0.001:
                    timing_message = (
                        f"expanded {current_duration:g}s to {retimed_duration:g}s")
                else:
                    timing_message = f"retimed dialogue within the {current_duration:g}s slate"
                log(
                    f"VOICE TIMING — {shot_id}: {timing_message}; "
                    "reused the existing paid take")
            else:
                ledger["voicePlacementFailure"] = {
                    "rawPath": str(raw_out), "timingPath": str(timing_path),
                    "generatedFrom": lines,
                    "inputSignature": voice_signature(pkg, shot, lines),
                    "error": str(exc), "at": m._now(),
                }
                m._save(pkg, path)
                raise m.Refused(
                    f"REFUSED — {shot_id}'s approved voice performance could not fit its "
                    f"approved timing windows: {exc}"
                ) from exc
        if previous and os.path.exists(previous):
            try:
                previous = str(pathlib.Path(previous).relative_to(m.HERE))
            except ValueError:
                previous = str(previous)
            ledger["voicePrevious"] = {
                "path": previous,
                "rawPath": ledger.get("voRawPath"),
                "timingPath": ledger.get("voTimingPath"),
                "placementPath": ledger.get("voPlacementPath"),
                "generatedFrom": ledger.get("voGeneratedFrom"),
                "supersededAt": m._now(),
            }
        ledger.update({"voPath": str(out), "voGeneratedFrom": lines,
                       "voRawPath": str(raw_out),
                       "voTimingPath": str(timing_path),
                       "voPlacementPath": placement["contractPath"],
                       "voicePlacementFailure": None,
                       "voInputSignature": voice_signature(pkg, shot, lines),
                       "voPackageRevision": pkg.get("revision")})
        m._save(pkg, path)
        log(f"VOICE — {shot_id}: {len(turns)} approved line(s) -> {out.name} (awaiting approval)")
        return str(out)

    def approve_voice(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, path = current_package(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        current_lines = voice_lines(pkg, shot)
        signature = voice_signature(pkg, shot, current_lines)
        generated_signature = ledger.get("voInputSignature") or {}
        same_nonperformance_inputs = {
            key: value for key, value in generated_signature.items()
            if key != "performanceHash"
        } == {
            key: value for key, value in signature.items()
            if key != "performanceHash"
        }
        same_provider_request = (
            voice_provider_projection(ledger.get("voGeneratedFrom") or []) ==
            voice_provider_projection(current_lines))
        if generated_signature != signature and not (
                same_nonperformance_inputs and same_provider_request):
            raise m.Refused(f"REFUSED — {shot_id}'s voice was not generated from current signed direction")
        for field in ("voPath", "voRawPath", "voTimingPath", "voPlacementPath"):
            value = ledger.get(field)
            if not value or not os.path.exists(value):
                raise m.Refused(
                    f"REFUSED — {shot_id}'s timestamped voice bundle is incomplete ({field})")
        result = original["approve_voice"](scene, shot_id, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); ledger = m._ledger(pkg, shot_id)
        ledger["voiceApproval"].update({"packageRevision": pkg.get("revision"),
                                         "inputSignature": signature,
                                         "contentHash": file_sha256(ledger.get("voPath")),
                                         "rawContentHash": file_sha256(ledger.get("voRawPath")),
                                         "timingContentHash": file_sha256(
                                             ledger.get("voTimingPath")),
                                         "placementContentHash": file_sha256(
                                             ledger.get("voPlacementPath"))})
        m._save(pkg, path)
        return ledger["voiceApproval"]

    def reject_voice(scene, shot_id, correction, episode="Ep1", reviewed_by="Julian", log=print):
        before, _ = m.load_pkg(scene, episode)
        bundle = {key: m._ledger(before, shot_id).get(key) for key in (
            "voRawPath", "voTimingPath", "voPlacementPath")}
        result = original["reject_voice"](scene, shot_id, correction, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); ledger = m._ledger(pkg, shot_id)
        if ledger.get("voiceRejections"):
            ledger["voiceRejections"][-1]["timingBundle"] = bundle
        ledger["voRawPath"] = None
        ledger["voTimingPath"] = None
        ledger["voPlacementPath"] = None
        ledger["voInputSignature"] = None; ledger["voPackageRevision"] = None
        m._save(pkg, path)
        return result

    def restore_voice(scene, shot_id, episode="Ep1", log=print):
        """A restored take is current only when its recorded performance exactly matches."""
        current_package(scene, episode)
        before, _ = m.load_pkg(scene, episode)
        previous = dict(m._ledger(before, shot_id).get("voicePrevious") or {})
        result = original["restore_previous_voice_take"](scene, shot_id, episode, log)
        pkg, path = m.load_pkg(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        ledger["voRawPath"] = previous.get("rawPath")
        ledger["voTimingPath"] = previous.get("timingPath")
        ledger["voPlacementPath"] = previous.get("placementPath")
        lines = voice_lines(pkg, shot)
        if ledger.get("voGeneratedFrom") == lines:
            ledger["voInputSignature"] = voice_signature(pkg, shot, lines)
            ledger["voPackageRevision"] = pkg.get("revision")
        else:
            ledger["voInputSignature"] = None
            ledger["voPackageRevision"] = None
        m._save(pkg, path)
        return result

    def keyframe_input_signature(pkg, shot, scene, episode):
        return {**original["_keyframe_input_signature"](pkg, shot, scene, episode),
                "canonProfileDigest": require_canon(
                    pkg, episode, "cinematography")}

    def keyframe_signature(pkg, shot, candidate, scene, episode):
        canon_digest = require_canon(pkg, episode, "cinematography")
        if candidate.get("source", "generated") == "generated":
            return m._keyframe_input_signature(pkg, shot, scene, episode)
        status = scene_status(scene, episode)
        return {"cardHash": m._live_card_hash(shot["shotId"], scene, episode),
                "canonProfileDigest": canon_digest,
                "sceneLookHash": (status.get("active") or {}).get("hash") if status.get("current") else None,
                "selectedAssetHash": m._file_md5(candidate.get("path")),
                "source": candidate.get("source")}

    def keyframe_shot(scene, shot_id, episode="Ep1", log=print):
        pkg, _ = current_package(scene, episode)
        result = original["keyframe_shot"](scene, shot_id, episode, log)
        pkg, path = m.load_pkg(scene, episode); shot = m._shot(pkg, shot_id)
        ledger = m._ledger(pkg, shot_id)
        candidates = list(ledger.get("keyframeCandidates") or [])
        if not candidates and ledger.get("keyframeCandidate"):
            candidates = [ledger["keyframeCandidate"]]
        if not candidates:
            return result
        for candidate in candidates:
            candidate["packageRevision"] = pkg.get("revision")
            candidate["inputSignature"] = keyframe_signature(
                pkg, shot, candidate, scene, episode)
            candidate["contentHash"] = file_sha256(candidate.get("path"))
            candidate["conformanceScreening"] = candidate.get("conformanceScreening") or \
                m.screen_keyframe_conformance(
                    pkg, shot, candidate.get("path"), scene, episode, log)
        selected_id = ledger.get("selectedKeyframeCandidateId")
        ledger["keyframeCandidate"] = next(
            (item for item in candidates if item.get("candidateId") == selected_id),
            candidates[0])
        m._save(pkg, path)
        for candidate in candidates:
            screening = candidate["conformanceScreening"]
            if screening.get("status") == "fail":
                review = screening.get("review") or {}
                correction = (review.get("recommendedCorrection") or
                              screening.get("reason") or
                              "The keyframe failed objective identity and scale checks.")
                log(f"KEYFRAME QC WARNING — {shot_id} SEE {candidate.get('candidateId')}: "
                    f"{correction}; candidate remains available for the human Director's "
                    "Accept or Refire decision")
        return result

    def select_keyframe(scene, shot_id, mode, episode="Ep1", upload_path=None,
                        library_path=None, reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode)
        # Source selection mutates the ledger. Validate SEE direction before copying or
        # superseding a candidate so a refused action cannot change production state.
        current_direction_output(pkg, shot_id, "cinematography")
        result = original["select_keyframe_source"](
            scene, shot_id, mode, episode, upload_path, library_path, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); shot = m._shot(pkg, shot_id)
        candidate = m._ledger(pkg, shot_id)["keyframeCandidate"]
        composition = m._load_opening_composition_master(
            shot, scene, episode, m._characters_cfg())
        candidate["geometryScreening"] = (
            m.cb_layout.screen_candidate_geometry(candidate.get("path"), composition)
            if composition else {
                "status": "unavailable",
                "reason": "No current local stage guide; human review owns this imported stage.",
                "zeroSpend": True,
                "providerCalled": False,
            })
        candidate["packageRevision"] = pkg.get("revision")
        candidate["inputSignature"] = keyframe_signature(pkg, shot, candidate, scene, episode)
        candidate["contentHash"] = file_sha256(candidate.get("path"))
        candidate["conformanceScreening"] = m.screen_keyframe_conformance(
            pkg, shot, candidate.get("path"), scene, episode, log)
        m._save(pkg, path)
        screening = candidate["conformanceScreening"]
        if screening.get("status") != "pass":
            log(f"KEYFRAME ADVISORY — {shot_id}: {screening.get('reason') or 'objective check did not pass'}; "
                "the imported candidate remains available for the human Director's decision")
        return result

    def rescreen_keyframe(scene, shot_id, episode="Ep1", log=print):
        """Retry only the objective check; it never regenerates media or spends media credits."""
        pkg, path = current_package(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        record = ledger.get("keyframeCandidate") or ledger.get("keyframeApproval")
        if not record or not record.get("path") or not os.path.exists(record.get("path")):
            raise m.Refused(f"REFUSED — {shot_id} has no keyframe media to screen")
        screening = m.screen_keyframe_conformance(
            pkg, shot, record["path"], scene, episode, log)
        record["conformanceScreening"] = screening
        # A zero-cost rescreen is also the recovery path for imported candidates whose
        # earlier selection was interrupted after the file copy. Re-seal the unchanged
        # file against current SEE inputs so it can return to the human approval screen.
        record["packageRevision"] = pkg.get("revision")
        record["inputSignature"] = keyframe_signature(pkg, shot, record, scene, episode)
        record["contentHash"] = file_sha256(record.get("path"))
        m._save(pkg, path)
        if (ledger.get("keyframeCandidate") is record and
                record.get("source", "generated") == "generated" and
                screening.get("status") == "fail"):
            review = screening.get("review") or {}
            correction = (review.get("recommendedCorrection") or screening.get("reason") or
                          "The keyframe failed objective identity and scale checks.")
            log(
                f"KEYFRAME QC WARNING — {shot_id}: {correction}; "
                "candidate remains available for the human Director's Accept or Refire decision"
            )
        return screening

    def approve_keyframe(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, path = current_package(scene, episode); shot = m._shot(pkg, shot_id)
        ledger = m._ledger(pkg, shot_id)
        ab_candidates = list(ledger.get("keyframeCandidates") or [])
        selected_id = str(ledger.get("selectedKeyframeCandidateId") or "").strip().upper()
        if len(ab_candidates) > 1 and not selected_id:
            raise m.Refused(
                f"REFUSED — {shot_id} requires an explicit SEE A/B selection before approval")
        composition = m._load_opening_composition_master(
            shot, scene, episode, m._characters_cfg())
        candidate = ledger.get("keyframeCandidate") or {}
        screening = candidate.get("geometryScreening") or {
            "status": "unavailable",
            "reason": ("local stage guide is missing or stale" if not composition else
                       "local stage screen was not run"),
        }
        # Layout screening is diagnostic evidence, not creative authority. The keyframe is
        # intentionally a permissive stage for animation, so an explicit human Accept may
        # override loose position/coverage warnings. Input lineage and file integrity remain
        # hard gates below.
        candidate["geometryScreening"] = screening
        candidate["geometryAdvisoryDecision"] = {
            "acceptedBy": reviewed_by,
            "acceptedAt": m._now(),
            "statusAtDecision": screening.get("status"),
            "reasonAtDecision": screening.get("reason"),
        }
        conformance = candidate.get("conformanceScreening") or {}
        if conformance.get("status") != "pass":
            # The automated screen is evidence, not the Director. A deliberate human Accept
            # keeps the failed/unknown check attached to lineage instead of silently blocking
            # or rejecting the candidate.
            candidate["packageRevision"] = pkg.get("revision")
            candidate["inputSignature"] = keyframe_signature(
                pkg, shot, candidate, scene, episode)
            candidate["contentHash"] = file_sha256(candidate.get("path"))
            candidate["conformanceAdvisoryDecision"] = {
                "acceptedBy": reviewed_by,
                "acceptedAt": m._now(),
                "statusAtDecision": conformance.get("status") or "unavailable",
                "reasonAtDecision": (conformance.get("reason") or
                                     "Objective identity and scale advice was unavailable."),
            }
        expected = keyframe_signature(pkg, shot, candidate, scene, episode)
        signature_diff = set(m._signature_diff(candidate.get("inputSignature"), expected))
        visual_carry = next(
            (item for item in reversed(pkg.get("scopedAmendments") or [])
             if item.get("shotId") == shot_id and
             item.get("kind") in ("dialogue-correction", "voice-contract-correction") and
             "keyframe" in (item.get("preservedStages") or []) and
             item.get("sceneLookContentHash") == expected.get("sceneLookHash")),
            None,
        )
        if visual_carry and signature_diff <= {"cardHash"}:
            # Re-seal unchanged visual evidence against the current dialogue-only shot
            # record. This changes provenance metadata only; approval remains the explicit
            # human action below and no provider is contacted.
            candidate["inputSignature"] = expected
        if (candidate.get("inputSignature") != expected or
                candidate.get("contentHash") != file_sha256(candidate.get("path"))):
            raise m.Refused(f"REFUSED — {shot_id}'s keyframe inputs changed; regenerate or reselect it")
        m._save(pkg, path)
        result = original["approve_keyframe"](scene, shot_id, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); approval = m._ledger(pkg, shot_id)["keyframeApproval"]
        approval.update({"packageRevision": pkg.get("revision"),
                         "contentHash": file_sha256(approval.get("path")),
                         "conformanceScreening": conformance,
                         "conformanceAdvisoryDecision": candidate.get(
                             "conformanceAdvisoryDecision")})
        m._save(pkg, path)
        return result

    def keyframe_record_status(pkg, shot, record, scene=None, episode=None):
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        if not record:
            return {"current": False, "reason": "not-approved",
                    "expectedInputSignature": None}
        try:
            expected = keyframe_signature(pkg, shot, record, scene, episode)
        except (m.Refused, OSError, ValueError) as exc:
            return {"current": False, "reason": str(exc),
                    "expectedInputSignature": None}
        path = record.get("path")
        human_advisory_accepted = bool(
            (record.get("conformanceAdvisoryDecision") or {}).get("acceptedBy"))
        conformance_current = bool(
            (record.get("conformanceScreening") or {}).get("status") == "pass" or
            human_advisory_accepted)
        stored_signature = record.get("inputSignature") or {}
        signatures_match = stored_signature == expected
        signature_diff = set(m._signature_diff(stored_signature, expected))
        human_lineage_carry = bool(
            (record.get("lineageCarryForward") or {}).get("reviewedBy"))
        amendment = (m._ledger(pkg, shot["shotId"]).get("scopedAmendment") or {})
        scoped_dialogue_carry = bool(
            amendment.get("kind") == "dialogue-correction" and
            amendment.get("keyframeContentHash") == record.get("contentHash") and
            signature_diff.issubset({"cardHash", "sceneLookHash"}) and
            stored_signature.get("selectedAssetHash") ==
            expected.get("selectedAssetHash") and
            stored_signature.get("canonProfileDigest") ==
            expected.get("canonProfileDigest"))
        if not signatures_match and scoped_dialogue_carry:
            signatures_match = True
        # A human may explicitly keep an approved image as visual truth after its
        # compiled brief changes. This covers compiler-only rewrites without weakening
        # asset, canon, Scene Look, reference, or file-integrity checks.
        if (not signatures_match and human_lineage_carry and
                signature_diff == {"briefHash"}):
            signatures_match = True
        # Compiler improvements must not rewrite the provenance of an image Julian already
        # approved. If only the compiled brief hash changed, retain the historical prompt
        # and prove that its protected Director sections still match current direction.
        # Changes to references, canon, Scene Look, media bytes or protected creative fields
        # continue to invalidate the approval normally.
        if (not signatures_match and
                record.get("source", "generated") == "generated" and
                signature_diff == {"briefHash"}):
            prompt_contract = record.get("promptContract") or {}
            historical_prompt = str(prompt_contract.get("prompt") or "")
            historical_hash = hashlib.sha256(historical_prompt.encode()).hexdigest()
            try:
                historical_contract = m._keyframe_prompt_contract(
                    pkg, shot, historical_prompt)
                signatures_match = bool(
                    historical_prompt and
                    stored_signature.get("briefHash") == historical_hash and
                    prompt_contract.get("promptHash") == historical_hash and
                    historical_contract.get("directionContract"))
            except (m.Refused, KeyError, TypeError, ValueError):
                signatures_match = False
        current = bool(
            record.get("approved") and path and os.path.exists(path) and
            signatures_match and
            record.get("contentHash") == file_sha256(path) and
            conformance_current)
        return {"current": current,
                "reason": None if current else (
                    "keyframe-conformance-not-passed"
                    if not conformance_current
                    else "keyframe-input-or-content-mismatch"),
                "expectedInputSignature": expected}

    def keyframe_stage_contract_report(record):
        """WATCH gate: SEE is physical stage evidence, not just a pretty frame.

        Automated stage review remains useful evidence, but an explicit human approval of
        that exact warning is the production decision. Requiring a second hidden override
        after approval makes SEE appear complete while WATCH still refuses the same frame.
        File integrity, input lineage, canon and reference checks remain hard elsewhere.
        """
        override = record.get("stageContractOverride") or {}
        if override.get("acceptedBy"):
            return {"ready": True, "reason": None}
        advisory = record.get("conformanceAdvisoryDecision") or {}
        if advisory.get("acceptedBy"):
            return {"ready": True, "reason": None}
        screening = record.get("conformanceScreening") or {}
        status = str(screening.get("status") or "").strip().lower()
        if status == "pass":
            return {"ready": True, "reason": None}
        review = screening.get("review") or {}
        evidence = " ".join(str(value or "") for value in (
            screening.get("reason"),
            review.get("summary"),
            review.get("recommendedCorrection"),
            (review.get("relativeScaleAndGeography") or {}).get("visibleEvidence"),
            (review.get("relativeScaleAndGeography") or {}).get("correction"),
            (review.get("actionReadyComposition") or {}).get("visibleEvidence"),
            (review.get("actionReadyComposition") or {}).get("correction"),
            (record.get("conformanceAdvisoryDecision") or {}).get("reasonAtDecision"),
        )).casefold()
        physical_stage_terms = (
            "causality", "geography", "action-ready", "action ready", "playable",
            "stage", "staging", "physical relationship", "attached", "tether",
            "towline", "mooring", "rope", "net", "strand", "tail", "rescue path",
            "dive path", "corridor", "gunwale", "hull", "boat", "prop",
            "trigger", "relationship", "position", "placement", "layout",
        )
        if any(term in evidence for term in physical_stage_terms):
            reason = (
                screening.get("reason") or review.get("summary") or
                "approved SEE frame failed physical stage conformance"
            )
            return {"ready": False, "reason": reason}
        return {"ready": True, "reason": None}

    def reassess_keyframe(scene, shot_id, episode="Ep1"):
        pkg, _ = m.load_pkg(scene, episode)
        shot = m._shot(pkg, shot_id)
        ledger = m._ledger(pkg, shot_id)
        existing = ledger.get("keyframeApproval") or ledger.get("keyframeCandidate")
        if not existing:
            return {"verdict": "none", "changed": [], "existing": None,
                    "currentSignature": None}
        try:
            current_sig = keyframe_signature(pkg, shot, existing, scene, episode)
        except (m.Refused, OSError, ValueError) as exc:
            return {"verdict": "regenerate", "changed": ["unresolvable-input"],
                    "reason": str(exc), "existing": existing, "currentSignature": None}
        changed = m._signature_diff(existing.get("inputSignature"), current_sig)
        if existing.get("contentHash") != file_sha256(existing.get("path")):
            changed.append("contentHash")
        human_advisory_accepted = bool(
            (existing.get("conformanceAdvisoryDecision") or {}).get("acceptedBy"))
        if ((existing.get("conformanceScreening") or {}).get("status") != "pass" and
                not human_advisory_accepted):
            changed.append("conformanceScreening")
        return {"verdict": "carry_forward" if not changed else "regenerate",
                "changed": changed, "existing": existing,
                "currentSignature": current_sig}

    def anchor_for(pkg, shot):
        result = original["_anchor_for"](pkg, shot)
        if shot["sourceType"] == "opener":
            approval = m._ledger(pkg, shot["shotId"]).get("keyframeApproval") or {}
            state = keyframe_record_status(pkg, shot, approval)
        else:
            # For relay shots, original["_anchor_for"] has already enforced the hard
            # requirement: the source shot is human-approved and has a harvested final
            # frame. That harvested frame is a state handoff into the next shot, not a
            # demand that the source shot's old render prompt graph still be current after
            # later scene-plate/geography corrections. The current shot's references,
            # scene plate and compiler prompt own the next emission.
            return result
        if not state["current"]:
            raise m.Refused(
                "REFUSED — opening-frame approval is stale against its direct inputs")
        return result

    def seedance_prompt(pkg, shot, scene=None, episode="Ep1", require_current_working=False):
        # A saved Director iteration is provider authority only after save_seedance_working
        # has validated its dialogue and production contracts and bound it to the current
        # SEE/HEAR/reference signature. Keep the typed Animation Director record as the
        # auditable baseline, then allow that current human override to supply the bytes.
        direction = current_direction_output(pkg, shot["shotId"], "animation")
        ledger = m._ledger(pkg, shot["shotId"])
        working = ledger.get("workingSeedancePrompt") or {}
        prompt = str(working.get("text") or direction.get("providerPrompt") or "").strip()
        if not prompt:
            raise m.Refused(f"REFUSED — current Animation direction for {shot['shotId']} has no prompt")
        if working.get("text"):
            current_scene = str(scene or pkg.get("sceneNumber") or "")
            current_episode = episode or pkg.get("episode") or "Ep1"
            expected = m._seedance_working_input_signature(
                pkg, shot, current_scene, current_episode)
            if working.get("inputSignature") != expected:
                raise m.Refused(
                    "REFUSED — saved WATCH working prompt is stale against the current "
                    "SEE/HEAR/reference inputs. Restore it or save it again after preparing "
                    "the current Animation direction."
                )
        return (m._with_character_scale_control(
            prompt, shot, "referenceSlots", str(scene or pkg.get("sceneNumber")),
            episode or pkg.get("episode") or "Ep1"), bool(working.get("text")))

    def approved_seedance_prompt(pkg, shot):
        prompt = str(current_direction_output(pkg, shot["shotId"], "animation")
                     .get("providerPrompt") or "").strip()
        if not prompt:
            raise m.Refused(
                f"REFUSED — Prepare current Animation direction for {shot['shotId']} first")
        return m._with_character_scale_control(
            prompt, shot, "referenceSlots", str(pkg.get("sceneNumber")),
            pkg.get("episode") or "Ep1")

    def check_structure(scene, shot_id, episode="Ep1", log=print):
        try:
            return original["check_seedance_structure"](scene, shot_id, episode, log)
        except m.Refused as exc:
            return {"verdict": "blocked", "blockers": [str(exc)], "warnings": [],
                    "checks": {"promptSource": "missing-current-approved-direction"},
                    "finalPrompt": ""}

    def fire_shot(scene, shot_id, episode="Ep1", candidates=3, fast=False,
                  spend_token=None, dry_run=False, comparison_model_id=None,
                  comparison_run_id=None, log=print, include_audio_reference=True,
                  generate_audio=True):
        pkg, _ = current_package(scene, episode); shot = m._shot(pkg, shot_id)
        ledger = m._ledger(pkg, shot_id)
        if ledger.get("status") == "model-limited":
            raise m.Refused(
                f"REFUSED — {shot_id} is MODEL-LIMITED after {m.MAX_BATCH_ATTEMPTS} failed "
                "candidate batches; human redesign is required before another fire")
        stage_report = keyframe_stage_contract_report(
            ledger.get("keyframeApproval") or {})
        if not stage_report["ready"]:
            raise m.Refused(
                "REFUSED — WATCH blocked because the approved SEE frame does not prove "
                "the physical stage contract. SEE is the render's opening causality "
                f"evidence, so text cannot safely override it: {stage_report['reason']}")
        if shot.get("sourceType") != "relay" and ledger.get("keyframeApproval"):
            # A SEE approval signed on earlier inputs (canon re-lock, new direction, replaced
            # reference) must never anchor a paid render (2026-09-03 audit: nothing checked it).
            kf_status = keyframe_record_status(
                pkg, shot, ledger.get("keyframeApproval") or {}, scene, episode)
            if not kf_status.get("current"):
                raise m.Refused(
                    "REFUSED — the approved SEE frame is stale against its direct inputs "
                    f"({kf_status.get('reason')}); rebuild or re-confirm the opening frame "
                    "before WATCH")
        stored = ((ledger.get("batch") or {}).get("envelope") or
                  (ledger.get("pendingSpendAuth") or {}).get("envelope") or {})
        if stored.get("comparisonRunId"):
            if comparison_model_id and (
                    comparison_model_id != stored.get("providerModelId") or
                    comparison_run_id != stored.get("comparisonRunId")):
                raise m.Refused(
                    "REFUSED — comparison settings differ from the sealed spend envelope")
            comparison_model_id = stored.get("providerModelId")
            comparison_run_id = stored.get("comparisonRunId")
        # Billing readiness is a global hard lock on every paid animation action. Surface it
        # before shot-local approvals so a disconnected or unconfirmed account can never be
        # mistaken for a creative-direction problem.
        try:
            billing_provider = (
                "fal" if comparison_model_id else
                cb_providers.video_model(require_enabled=False).provider)
        except cb_providers.ProviderCapabilityError as exc:
            raise m.Refused(f"REFUSED — provider capability: {exc}") from exc
        m._require_confirmed_billing(billing_provider)
        if cb_audio_authority.spoken_dialogue_lines(shot):
            voice = voice_approval_status(pkg, shot, scene, episode)
            if not voice["current"]:
                raise m.Refused(
                    f"REFUSED — Law 5: {shot_id}'s approved voice does not match current direction")
        seedance_prompt(pkg, shot)
        generation_signature = animation_generation_signature(
            pkg, shot, scene, episode, fast=fast,
            comparison_model_id=comparison_model_id,
            comparison_run_id=comparison_run_id,
            include_audio_reference=include_audio_reference,
            generate_audio=generate_audio)
        result = original["fire_shot"](
            scene, shot_id, episode, candidates, fast, spend_token, dry_run,
            comparison_model_id, comparison_run_id, log, include_audio_reference,
            generate_audio)
        pkg, path = m.load_pkg(scene, episode)
        ledger = m._ledger(pkg, shot_id)
        batch = ledger.get("batch") or {}
        if batch.get("status") != "complete":
            raise m.Refused(
                f"REFUSED — {shot_id}'s provider batch did not finish with a complete contract")
        current_signature = animation_generation_signature(
            pkg, m._shot(pkg, shot_id), scene, episode, fast=fast,
            comparison_model_id=comparison_model_id,
            comparison_run_id=comparison_run_id,
            include_audio_reference=include_audio_reference,
            generate_audio=generate_audio)
        if current_signature != generation_signature:
            raise m.Refused(
                f"REFUSED — {shot_id}'s direct generation inputs changed while its batch ran")
        batch["inputSignature"] = generation_signature
        batch["candidateHashes"] = [
            {"path": candidate_path, "sha256": file_sha256(candidate_path)}
            for candidate_path in (ledger.get("candidatePaths") or [])
        ]
        m._save(pkg, path)
        return result

    def next_shot(scene, episode="Ep1", candidates=3, fast=False,
                  spend_token=None, dry_run=False, comparison_model_id=None,
                  comparison_run_id=None, log=print):
        current_package(scene, episode)
        return original["next_shot"](
            scene, episode, candidates, fast, spend_token, dry_run,
            comparison_model_id, comparison_run_id, log)

    def approve_shot(scene, shot_id, candidate=1, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        batch = ledger.get("batch") or {}
        fast = ((batch.get("envelope") or {}).get("tier") == "fast")
        envelope = batch.get("envelope") or {}
        comparison_model_id = (
            envelope.get("providerModelId") if envelope.get("comparisonRunId") else None)
        comparison_run_id = envelope.get("comparisonRunId")
        current_signature = animation_generation_signature(
            pkg, shot, scene, episode, fast=fast,
            comparison_model_id=comparison_model_id,
            comparison_run_id=comparison_run_id)
        recorded_hashes = batch.get("candidateHashes") or []
        current_hashes = [
            {"path": candidate_path, "sha256": file_sha256(candidate_path)}
            for candidate_path in (ledger.get("candidatePaths") or [])
        ]
        if (batch.get("status") != "complete" or
                batch.get("inputSignature") != current_signature or
                not recorded_hashes or recorded_hashes != current_hashes):
            raise m.Refused(
                f"REFUSED — {shot_id}'s candidate batch is stale, incomplete or changed on disk")
        result = original["approve_shot"](scene, shot_id, candidate, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); approval = m._ledger(pkg, shot_id)["approval"]
        ledger = m._ledger(pkg, shot_id)
        approval.update({"packageRevision": pkg.get("revision"),
                         "inputSignature": current_signature,
                         "contentHash": file_sha256(ledger.get("approvedTake")),
                         "harvestHash": file_sha256(ledger.get("harvestFrame")),
                         "batchId": batch.get("batchId")})
        m._save(pkg, path)
        return result

    def stitch_scene(scene, episode="Ep1", log=print):
        pkg, _ = current_package(scene, episode)
        for shot in pkg.get("shots") or []:
            ledger = m._ledger(pkg, shot["shotId"])
            approval = animation_approval_status(pkg, shot, scene, episode)
            if not approval["current"]:
                raise m.Refused(
                    f"REFUSED — {shot['shotId']} is unapproved: "
                    "no current approved animation take")
            review = department_record_status(
                pkg, shot["shotId"], "review-animation", scene, episode)
            if not review["current"]:
                raise m.Refused(
                    f"REFUSED — {shot['shotId']} has no current Director Review approval")
        return original["stitch_scene"](scene, episode, log)

    m._resolve_scenelook_prompt = resolve_scenelook_prompt
    m.scenelook_status = scene_status
    m._scenelook_record_input_signature = look_input_signature
    m.approved_look_prompt = look_prompt
    m.generate_scenelook_plate = generate_look
    m.approve_scenelook = approve_look
    m.select_scenelook_source = select_look
    m.department_status = department_status
    m.prepare_department = prepare_department
    m.save_department_candidate = save_department
    m.decide_department = decide_department
    m._current_department_output = current_direction_output
    # Compatibility aliases for older call sites. These now mean current signed direction;
    # they never manufacture or imply a human approval.
    m._require_approved_department_output = current_direction_output
    m._approved_department_output = current_direction_output
    m._department_input_signature = department_input_signature
    m._department_record_status = department_record_status
    m._resolve_keyframe_prompt = keyframe_prompt
    m._keyframe_input_signature = keyframe_input_signature
    m._keyframe_stage_contract_report = keyframe_stage_contract_report
    m._approved_voice_lines = voice_lines
    m._voice_input_signature = voice_signature
    m._voice_approval_status = voice_approval_status
    m._voice_signature = voice_signature
    m._animation_input_signature = animation_input_signature
    m._animation_input_signature = animation_input_signature
    m._animation_generation_signature = animation_generation_signature
    m._animation_approval_status = animation_approval_status
    m._external_import_input_signature = external_import_input_signature
    m.voice_shot = voice_shot
    m.approve_voice = approve_voice
    m.reject_voice = reject_voice
    m.restore_previous_voice_take = restore_voice
    m.keyframe_shot = keyframe_shot
    m.select_keyframe_source = select_keyframe
    m.rescreen_keyframe_conformance = rescreen_keyframe
    m.approve_keyframe = approve_keyframe
    m.reassess_keyframe = reassess_keyframe
    m._keyframe_record_input_signature = keyframe_signature
    m._keyframe_record_status = keyframe_record_status
    m._anchor_for = anchor_for
    m._resolve_seedance_prompt = seedance_prompt
    m._approved_seedance_prompt = approved_seedance_prompt
    m.check_seedance_structure = check_structure
    m.fire_shot = fire_shot
    m.next_shot = next_shot
    m.approve_shot = approve_shot
    m.stitch_scene = stitch_scene
