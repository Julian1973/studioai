"""Runtime safety layer for the single Crystal Bears production path.

Installed by cb_render after its implementation functions are defined. It makes every paid
handoff consume only current, human-approved specialist work. Package revisions remain audit
provenance; validity is decided from the exact inputs an artefact actually depends on. No
provider is called from this module by itself.
"""
import hashlib
import json
import os
import pathlib
import re
import uuid

import cb_canon
import cb_providers


def install(m):
    original = {name: getattr(m, name) for name in (
        "_resolve_scenelook_prompt", "scenelook_status", "approved_look_prompt",
        "generate_scenelook_plate", "approve_scenelook", "select_scenelook_source",
        "department_status", "prepare_department", "save_department_candidate", "decide_department",
        "_resolve_keyframe_prompt", "_keyframe_input_signature", "voice_shot", "approve_voice", "reject_voice",
        "restore_previous_voice_take", "keyframe_shot", "select_keyframe_source",
        "approve_keyframe", "reassess_keyframe", "_anchor_for", "_resolve_seedance_prompt",
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

    def package_cast(pkg):
        try:
            roster = cb_canon.load_policy(m.ROOT).get("roster") or {}
        except cb_canon.CanonLockError:
            roster = {}
        blob = json.dumps(pkg, ensure_ascii=False).lower().replace("’", "'")
        return sorted(name for name in roster if re.search(
            r"(?<![a-z0-9])" + re.escape(name.lower().replace("’", "'")) +
            r"(?![a-z0-9])", blob))

    def require_canon(pkg, episode, profile=None):
        try:
            lock = cb_canon.require_locked(
                episode, package_cast(pkg), root=m.ROOT)
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

    def ordered_slot_signature(shot, slots_key, anchor, scene, episode):
        slots = sorted(
            (key for key in (shot.get(slots_key) or {}) if key.startswith("@图")),
            key=lambda key: int(key[2:]),
        )
        paths = m._slot_paths(
            shot, slots_key, anchor, scene, episode, m._characters_cfg())
        return [{"slot": key, "role": shot[slots_key][key],
                 "hash": file_sha256(path)}
                for key, path in zip(slots, paths)]

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
                    "sceneLookHash": ((look.get("approved") or {}).get("hash")
                                      if look.get("current") else None),
                    "references": ordered_slot_signature(
                        shot, "keyframeReferenceSlots", None, scene, episode)}
        if stage == "voice":
            characters = m._characters_cfg()
            return {**common,
                    "dialogueHash": json_sha256(shot.get("dialogueLines") or []),
                    "workingPerformanceHash": json_sha256(ledger.get("workingVoice")),
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
            return {**common, "mediaHashes": [file_sha256(path) for path in paths],
                    "generationSignature": animation_generation_signature(
                        pkg, shot, scene, episode)}
        raise m.Refused(f"REFUSED — unknown department stage '{stage}'")

    def department_record_status(pkg, shot_id, stage, scene=None, episode=None):
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        work, _ = m._department_container(pkg, scene, shot_id, stage, episode)
        record = work.get("approved") or {}
        if not record or not record.get("output"):
            return {"approved": False, "current": False, "reason": "not-approved",
                    "record": record, "expectedInputSignature": None}
        try:
            expected = department_input_signature(pkg, stage, shot_id, scene, episode)
        except (m.Refused, OSError, ValueError) as exc:
            return {"approved": True, "current": False, "reason": str(exc),
                    "record": record, "expectedInputSignature": None}
        current = record.get("inputSignature") == expected
        return {"approved": True, "current": current,
                "reason": None if current else "direct-input-signature-mismatch",
                "record": record, "expectedInputSignature": expected}

    def approved_record(pkg, shot_id, stage):
        state = department_record_status(pkg, shot_id, stage)
        rec = state["record"]
        if not state["current"]:
            label = {"cinematography": "Cinematography", "voice": "Voice",
                     "animation": "Animation"}.get(stage, stage.title())
            if state["reason"] == "not-approved":
                prefix, suffix = "", ""
            else:
                prefix = f"{label} direction is stale (STALE direct inputs). "
                suffix = f" ({state['reason']})"
            raise m.Refused(
                f"REFUSED — {prefix}Approve current {label} specialist direction for "
                f"{shot_id} first.{suffix}")
        return rec

    def approved_output(pkg, shot_id, stage):
        return approved_record(pkg, shot_id, stage)["output"]

    def resolve_scenelook_prompt(scene, episode="Ep1"):
        return look_prompt(scene, episode) or m._compile_scenelook_prompt(scene, episode)

    def scene_status(scene, episode="Ep1"):
        rec = m._load_scenelook_rec(scene, episode)
        approved, candidate = rec.get("approved"), rec.get("candidate")
        approved_current = False
        if approved:
            try:
                current_sig = look_input_signature(
                    scene, episode, approved.get("path"), approved.get("referencePath"))
                approved_current = (
                    os.path.exists(approved.get("path") or "") and
                    approved.get("hash") == file_sha256(approved.get("path")) and
                    approved.get("inputSignature") == current_sig)
            except (m.Refused, OSError, ValueError):
                approved_current = False
        if candidate:
            return {"status": "awaiting", "current": approved_current, "approved": approved,
                    "candidate": candidate, "history": rec.get("history", [])}
        if approved:
            return {"status": "approved" if approved_current else "stale",
                    "current": approved_current,
                    "approved": approved, "candidate": None,
                    "history": rec.get("history", [])}
        history = rec.get("history", [])
        status = "rejected" if history and history[-1].get("outcome") == "rejected" else "none"
        return {"status": status, "current": False, "approved": None,
                "candidate": None, "history": history}

    def look_prompt(scene, episode="Ep1"):
        pkg, _ = m.load_pkg(scene, episode)
        state = department_record_status(pkg, None, "look", scene, episode)
        approved = state["record"]
        prompt = ((approved.get("output") or {}).get("providerPrompt") or "").strip()
        return prompt if state["current"] and prompt else None

    def file_sha256(path):
        try:
            return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        except Exception:
            return None

    def look_input_signature(scene, episode, plate_path=None, reference_path=None):
        """Every direct Scene Look input, including the approved specialist prompt and files."""
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
            raise m.Refused("REFUSED — Approve Look Development direction first.")
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
            raise m.Refused("REFUSED — approved Look direction changed after this candidate was generated")
        return original["approve_scenelook"](scene, episode, reviewed_by, log)

    def select_look(scene, mode, episode="Ep1", upload_path=None, library_path=None,
                    reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode)
        if not look_prompt(scene, episode):
            raise m.Refused("REFUSED — Approve Look Development direction first.")
        result = original["select_scenelook_source"](
            scene, mode, episode, upload_path, library_path, reviewed_by, log)
        rec = m._load_scenelook_rec(scene, episode)
        rec["candidate"]["packageRevision"] = pkg.get("revision")
        rec["candidate"]["inputSignature"] = look_input_signature(
            scene, episode, rec["candidate"].get("path"))
        m._save_scenelook_rec(rec, scene, episode)
        return result

    def prepare_department(scene, stage, shot_id=None, episode="Ep1", log=print):
        pkg, _ = current_package(scene, episode)
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
        return {**result, "approvalCurrent": approval["current"],
                "approvalReason": approval["reason"],
                "candidateCurrent": candidate_current}

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
        prompt = str(approved_output(pkg, shot["shotId"], "cinematography")
                     .get("providerPrompt") or "").strip()
        if not prompt:
            raise m.Refused(f"REFUSED — approved Cinematography direction for {shot['shotId']} has no prompt")
        return prompt

    def voice_lines(pkg, shot):
        output = approved_output(pkg, shot["shotId"], "voice")
        lines, locked = output.get("lines") or [], shot.get("dialogueLines") or []
        if len(lines) != len(locked):
            raise m.Refused(f"REFUSED — approved Voice direction for {shot['shotId']} has the wrong line count")
        result = []
        for index, (item, source) in enumerate(zip(lines, locked), start=1):
            performed = str(item.get("performedText") or "").strip()
            if m._norm(item.get("speaker")) != m._norm(source.get("speaker")):
                raise m.Refused(f"REFUSED — Voice direction changed the speaker on line {index}")
            if m.cb_departments._spoken_words(performed) != m.cb_departments._spoken_words(source.get("exactText")):
                raise m.Refused(f"REFUSED — Voice direction changed the locked words on line {index}")
            result.append({
                "dialogueOccurrenceId": source.get("dialogueOccurrenceId"),
                "sourceEventId": source.get("sourceEventId"),
                "speaker": source["speaker"],
                "text": performed,
            })
        return result

    def voice_signature(pkg, shot, lines):
        characters = m._characters_cfg()
        ids = [(characters.get(m._resolve_char(line["speaker"], characters)) or {}).get("voiceId")
               for line in (shot.get("dialogueLines") or [])]
        episode = pkg.get("episode") or pkg.get("episodeId") or "Ep1"
        return {"canonProfileDigest": require_canon(pkg, episode, "voice"),
                "dialogueHash": hashlib.sha256(json.dumps(
                    shot.get("dialogueLines") or [], sort_keys=True,
                    ensure_ascii=False).encode()).hexdigest(),
                "performanceHash": hashlib.sha256(json.dumps(
                    lines, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                "voiceIds": ids}

    def voice_approval_status(pkg, shot, scene=None, episode=None):
        if not shot.get("dialogueLines"):
            return {"required": False, "approved": True, "current": True, "reason": None,
                    "record": {}, "expectedInputSignature": None}
        scene = str(scene if scene is not None else pkg.get("sceneNumber"))
        episode = episode or pkg.get("episode", "Ep1")
        ledger = m._ledger(pkg, shot["shotId"])
        approval = ledger.get("voiceApproval") or {}
        try:
            signature = voice_signature(pkg, shot, voice_lines(pkg, shot))
        except (m.Refused, OSError, ValueError) as exc:
            return {"required": True, "approved": bool(approval.get("approved")),
                    "current": False, "reason": str(exc), "record": approval,
                    "expectedInputSignature": None}
        path = ledger.get("voPath")
        current = bool(
            approval.get("approved") and path and os.path.exists(path) and
            approval.get("path") == path and
            approval.get("inputSignature") == signature and
            approval.get("contentHash") == file_sha256(path))
        return {"required": True, "approved": bool(approval.get("approved")),
                "current": current,
                "reason": None if current else "voice-approval-input-or-content-mismatch",
                "record": approval, "expectedInputSignature": signature}

    def animation_input_signature(pkg, shot, scene, episode):
        """Bind Animation direction to every direct visual and performance input.

        The signature deliberately stores hashes, never media bytes. A changed plate,
        opening frame, character reference, voice take or package contract makes a
        prepared/approved prompt stale without making a provider call.
        """
        ledger = m._ledger(pkg, shot["shotId"])
        anchor = m._anchor_for(pkg, shot)
        refs = m._slot_paths(
            shot, "referenceSlots", anchor, scene, episode, m._characters_cfg())
        look = scene_status(scene, episode)
        voice = voice_approval_status(pkg, shot, scene, episode)
        if shot.get("dialogueLines") and not voice["current"]:
            raise m.Refused(
                f"REFUSED — {shot['shotId']}'s approved voice is missing or stale")
        voice_approval = voice["record"]
        return {
            "canonProfileDigest": require_canon(pkg, episode, "animation"),
            "shotHash": hashlib.sha256(json.dumps(
                shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            "openingFrameHash": file_sha256(anchor),
            "sceneLookHash": ((look.get("approved") or {}).get("hash")
                              if look.get("current") else None),
            "referenceOrder": list((shot.get("referenceSlots") or {}).keys()),
            "referenceHashes": [file_sha256(path) for path in refs],
            "voiceHash": (file_sha256(ledger.get("voPath"))
                          if shot.get("dialogueLines") else None),
            "voiceApprovalSignature": (voice_approval.get("inputSignature")
                                       if shot.get("dialogueLines") else None),
        }

    def animation_generation_signature(pkg, shot, scene, episode, fast=False):
        direction = approved_record(pkg, shot["shotId"], "animation")
        prompt = str((direction.get("output") or {}).get("providerPrompt") or "").strip()
        if not prompt:
            raise m.Refused(
                f"REFUSED — approved Animation direction for {shot['shotId']} has no prompt")
        anchor = m._anchor_for(pkg, shot)
        refs = ordered_slot_signature(shot, "referenceSlots", anchor, scene, episode)
        voice = voice_approval_status(pkg, shot, scene, episode)
        if shot.get("dialogueLines") and not voice["current"]:
            raise m.Refused(
                f"REFUSED — {shot['shotId']}'s approved voice is missing or stale")
        ledger = m._ledger(pkg, shot["shotId"])
        try:
            provider = cb_providers.request_contract(
                fast=fast, duration=int(round(shot.get("durationSec") or 0)),
                resolution="720p", image_count=max(1, len(refs)),
                audio_count=1 if shot.get("dialogueLines") else 0)
        except cb_providers.ProviderCapabilityError as exc:
            raise m.Refused(f"REFUSED — provider capability: {exc}") from exc
        return {
            "canonProfileDigest": require_canon(pkg, episode, "animation"),
            "shotContractHash": json_sha256(shot),
            "animationDirectionSignature": direction.get("inputSignature"),
            "promptHash": hashlib.sha256(prompt.encode()).hexdigest(),
            "openingFrameHash": file_sha256(anchor),
            "references": refs,
            "audioHash": (file_sha256(ledger.get("voPath"))
                          if shot.get("dialogueLines") else None),
            "durationSec": shot.get("durationSec"),
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
        fast = bool((recorded or {}).get("tier") == "fast")
        try:
            expected = animation_generation_signature(
                pkg, shot, scene, episode, fast=fast)
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

    def voice_shot(pkg, path, shot_id, episode="Ep1", log=print):
        m._require_valid(pkg)
        m._require_current_lineage(pkg, pkg.get("sceneNumber"), episode)
        require_canon(pkg, episode, "voice")
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        if not shot.get("dialogueLines"):
            return None
        if (ledger.get("voiceApproval") or {}).get("approved"):
            raise m.Refused(f"REFUSED — {shot_id}'s voice is already approved; reject it first")
        m._require_confirmed_billing("elevenlabs")
        lines, characters, turns = voice_lines(pkg, shot), m._characters_cfg(), []
        for source, performance in zip(shot["dialogueLines"], lines):
            voice_id = (characters.get(m._resolve_char(source["speaker"], characters)) or {}).get("voiceId")
            if not voice_id:
                raise m.Refused(f"REFUSED — no ElevenLabs voiceId for {source['speaker']}")
            turns.append({"text": performance["text"], "voice_id": voice_id})
        m.MEDIA.mkdir(parents=True, exist_ok=True)
        out = m.MEDIA / f"{episode}_{shot_id}_vo_candidate_{uuid.uuid4().hex[:8]}.mp3"
        previous = ledger.get("voPath")
        m.cb_gen.eleven_dialogue(turns, out=str(out),
                                 generation_kind="regeneration" if previous else "generation",
                                 production_route="cb_render")
        if previous and os.path.exists(previous):
            try:
                previous = str(pathlib.Path(previous).relative_to(m.HERE))
            except ValueError:
                previous = str(previous)
            ledger["voicePrevious"] = {"path": previous,
                                         "generatedFrom": ledger.get("voGeneratedFrom"),
                                         "supersededAt": m._now()}
        ledger.update({"voPath": str(out), "voGeneratedFrom": lines,
                       "voInputSignature": voice_signature(pkg, shot, lines),
                       "voPackageRevision": pkg.get("revision")})
        m._save(pkg, path)
        log(f"VOICE — {shot_id}: {len(turns)} approved line(s) -> {out.name} (awaiting approval)")
        return str(out)

    def approve_voice(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, path = current_package(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        signature = voice_signature(pkg, shot, voice_lines(pkg, shot))
        if ledger.get("voInputSignature") != signature:
            raise m.Refused(f"REFUSED — {shot_id}'s voice was not generated from current approved direction")
        result = original["approve_voice"](scene, shot_id, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); ledger = m._ledger(pkg, shot_id)
        ledger["voiceApproval"].update({"packageRevision": pkg.get("revision"),
                                         "inputSignature": signature,
                                         "contentHash": file_sha256(ledger.get("voPath"))})
        m._save(pkg, path)
        return ledger["voiceApproval"]

    def reject_voice(scene, shot_id, correction, episode="Ep1", reviewed_by="Julian", log=print):
        result = original["reject_voice"](scene, shot_id, correction, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); ledger = m._ledger(pkg, shot_id)
        ledger["voInputSignature"] = None; ledger["voPackageRevision"] = None
        m._save(pkg, path)
        return result

    def restore_voice(scene, shot_id, episode="Ep1", log=print):
        """A restored take is current only when its recorded performance exactly matches."""
        current_package(scene, episode)
        result = original["restore_previous_voice_take"](scene, shot_id, episode, log)
        pkg, path = m.load_pkg(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
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
                "sceneLookHash": (status.get("approved") or {}).get("hash") if status.get("current") else None,
                "selectedAssetHash": m._file_md5(candidate.get("path")),
                "source": candidate.get("source")}

    def keyframe_shot(scene, shot_id, episode="Ep1", log=print):
        pkg, _ = current_package(scene, episode)
        result = original["keyframe_shot"](scene, shot_id, episode, log)
        pkg, path = m.load_pkg(scene, episode); ledger = m._ledger(pkg, shot_id)
        candidate = ledger["keyframeCandidate"]
        candidate["packageRevision"] = pkg.get("revision")
        candidate["inputSignature"] = keyframe_signature(
            pkg, m._shot(pkg, shot_id), candidate, scene, episode)
        candidate["contentHash"] = file_sha256(candidate.get("path"))
        m._save(pkg, path)
        return result

    def select_keyframe(scene, shot_id, mode, episode="Ep1", upload_path=None,
                        library_path=None, reviewed_by="Julian", log=print):
        current_package(scene, episode)
        result = original["select_keyframe_source"](
            scene, shot_id, mode, episode, upload_path, library_path, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); shot = m._shot(pkg, shot_id)
        candidate = m._ledger(pkg, shot_id)["keyframeCandidate"]
        candidate["packageRevision"] = pkg.get("revision")
        candidate["inputSignature"] = keyframe_signature(pkg, shot, candidate, scene, episode)
        candidate["contentHash"] = file_sha256(candidate.get("path"))
        m._save(pkg, path)
        return result

    def approve_keyframe(scene, shot_id, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode); shot = m._shot(pkg, shot_id)
        candidate = m._ledger(pkg, shot_id).get("keyframeCandidate") or {}
        expected = keyframe_signature(pkg, shot, candidate, scene, episode)
        if (candidate.get("inputSignature") != expected or
                candidate.get("contentHash") != file_sha256(candidate.get("path"))):
            raise m.Refused(f"REFUSED — {shot_id}'s keyframe inputs changed; regenerate or reselect it")
        result = original["approve_keyframe"](scene, shot_id, episode, reviewed_by, log)
        pkg, path = m.load_pkg(scene, episode); approval = m._ledger(pkg, shot_id)["keyframeApproval"]
        approval.update({"packageRevision": pkg.get("revision"),
                         "contentHash": file_sha256(approval.get("path"))})
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
        current = bool(
            record.get("approved") and path and os.path.exists(path) and
            record.get("inputSignature") == expected and
            record.get("contentHash") == file_sha256(path))
        return {"current": current,
                "reason": None if current else "keyframe-input-or-content-mismatch",
                "expectedInputSignature": expected}

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
        return {"verdict": "carry_forward" if not changed else "regenerate",
                "changed": changed, "existing": existing,
                "currentSignature": current_sig}

    def anchor_for(pkg, shot):
        result = original["_anchor_for"](pkg, shot)
        if shot["sourceType"] == "opener":
            approval = m._ledger(pkg, shot["shotId"]).get("keyframeApproval") or {}
            state = keyframe_record_status(pkg, shot, approval)
        else:
            source_shot = m._shot(pkg, shot["sourceShotId"])
            state = animation_approval_status(pkg, source_shot)
        if not state["current"]:
            raise m.Refused(
                "REFUSED — opening-frame approval is stale against its direct inputs")
        return result

    def seedance_prompt(pkg, shot):
        prompt = str(approved_output(pkg, shot["shotId"], "animation")
                     .get("providerPrompt") or "").strip()
        if not prompt:
            raise m.Refused(f"REFUSED — approved Animation direction for {shot['shotId']} has no prompt")
        return prompt, False

    def check_structure(scene, shot_id, episode="Ep1", log=print):
        try:
            return original["check_seedance_structure"](scene, shot_id, episode, log)
        except m.Refused as exc:
            return {"verdict": "blocked", "blockers": [str(exc)], "warnings": [],
                    "checks": {"promptSource": "missing-current-approved-direction"},
                    "finalPrompt": ""}

    def fire_shot(scene, shot_id, episode="Ep1", candidates=3, fast=False,
                  spend_token=None, dry_run=False, log=print):
        pkg, _ = current_package(scene, episode); shot = m._shot(pkg, shot_id)
        # Billing readiness is a global hard lock on every paid animation action. Surface it
        # before shot-local approvals so a disconnected or unconfirmed account can never be
        # mistaken for a creative-direction problem.
        m._require_confirmed_billing("fal")
        if shot.get("dialogueLines"):
            voice = voice_approval_status(pkg, shot, scene, episode)
            if not voice["current"]:
                raise m.Refused(
                    f"REFUSED — Law 5: {shot_id}'s approved voice does not match current direction")
        seedance_prompt(pkg, shot)
        generation_signature = animation_generation_signature(
            pkg, shot, scene, episode, fast=fast)
        result = original["fire_shot"](
            scene, shot_id, episode, candidates, fast, spend_token, dry_run, log)
        pkg, path = m.load_pkg(scene, episode)
        ledger = m._ledger(pkg, shot_id)
        batch = ledger.get("batch") or {}
        if batch.get("status") != "complete":
            raise m.Refused(
                f"REFUSED — {shot_id}'s provider batch did not finish with a complete contract")
        current_signature = animation_generation_signature(
            pkg, m._shot(pkg, shot_id), scene, episode, fast=fast)
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
                  spend_token=None, dry_run=False, log=print):
        current_package(scene, episode)
        return original["next_shot"](scene, episode, candidates, fast, spend_token, dry_run, log)

    def approve_shot(scene, shot_id, candidate=1, episode="Ep1", reviewed_by="Julian", log=print):
        pkg, _ = current_package(scene, episode)
        shot, ledger = m._shot(pkg, shot_id), m._ledger(pkg, shot_id)
        batch = ledger.get("batch") or {}
        fast = ((batch.get("envelope") or {}).get("tier") == "fast")
        current_signature = animation_generation_signature(
            pkg, shot, scene, episode, fast=fast)
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
    m._require_approved_department_output = approved_output
    m._department_input_signature = department_input_signature
    m._department_record_status = department_record_status
    m._resolve_keyframe_prompt = keyframe_prompt
    m._keyframe_input_signature = keyframe_input_signature
    m._approved_voice_lines = voice_lines
    m._voice_input_signature = voice_signature
    m._voice_approval_status = voice_approval_status
    m._animation_input_signature = animation_input_signature
    m._animation_generation_signature = animation_generation_signature
    m._animation_approval_status = animation_approval_status
    m.voice_shot = voice_shot
    m.approve_voice = approve_voice
    m.reject_voice = reject_voice
    m.restore_previous_voice_take = restore_voice
    m.keyframe_shot = keyframe_shot
    m.select_keyframe_source = select_keyframe
    m.approve_keyframe = approve_keyframe
    m.reassess_keyframe = reassess_keyframe
    m._keyframe_record_input_signature = keyframe_signature
    m._keyframe_record_status = keyframe_record_status
    m._anchor_for = anchor_for
    m._resolve_seedance_prompt = seedance_prompt
    m._approved_seedance_prompt = lambda pkg, shot: seedance_prompt(pkg, shot)[0]
    m.check_seedance_structure = check_structure
    m.fire_shot = fire_shot
    m.next_shot = next_shot
    m.approve_shot = approve_shot
    m.stitch_scene = stitch_scene
