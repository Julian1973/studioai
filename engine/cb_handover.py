#!/usr/bin/env python3
"""cb_handover.py — HUMAN GATE A → PRODUCTION (2026-07-17, Julian's handover-proof directive).

Promotes a HUMAN-APPROVED Authoritative Storyboard Package (cb_creative.py's output) into a
NEW, VERSIONED production shot package. The approved storyboard becomes the SOLE creative
source: every creative field in the promoted package traces to the storyboard's own approved
scene/beat/shot/voice direction, distilling ONLY:

    1. the approved opening state          (openingComposition + openingCharacterState)
    2. the principal character performance (principalPerformance, verbatim)
    3. the principal camera intention      (cameraBehaviour, verbatim)
    4. the approved voice/audio relationship (dialoguePlacement + the VoicePerformances)
    5. continuity in/out                   (verbatim prose, plus the typed degraded mapping —
                                            see INTEGRATION_GAPS)
    6. up to three genuinely essential protections (essentialProviderProtections → prohibited)

Showrunner judgements, rejected interpretations, internal revision history, escalations,
taste canons and constraint walls NEVER cross into the promoted package or the provider brief
(asserted at promotion time, and by test_cb_handover.py).

Provider isolation by construction: this module never imports cb_gen or cb_render. Prompt
compilation is delegated to the EXISTING cb_engine compiler — called, never modified. A
promotion bumps the package revision and rewrites the shots, which changes cb_render's
_shots_hash/_binding_hash inputs — every earlier disclosure, sealed envelope and spend token
is therefore stale at the existing fire-time binding check, with zero new code at the
provider boundary.

dry_run=True (the default) computes and returns everything and writes NOTHING.
"""
import hashlib
import json
import pathlib
import re

import cb_engine

HERE = pathlib.Path(__file__).resolve().parent
CHARS = HERE.parent / "shows" / "crystal-bears" / "canon" / "characters.json"

APPROVED_STATE = "approved"          # what /api/storyboard-approve writes at scene level

# Keys of the storyboard that are CREATIVE-ROOM INTERNAL and must never reach production:
NEVER_PROMOTED = ("showrunnerJudgement", "internalRevisions", "escalation", "vision",
                   "interpretations", "selectionReason", "rejectedApproachSummaries")

# The one explicit integration gap (reported, never silently shimmed — Julian's directive:
# stop before altering protected code; cb_engine's typed contract is protected):
INTEGRATION_GAPS = (
    "typed-continuity: the storyboard records continuity in/out as approved PROSE; the "
    "production contract (cb_engine.ContinuityState) requires per-character TYPED state "
    "(screenZone/facing/pose/expression/visibleMarks/heldProps). No mechanical distillation "
    "of prose into typed per-character state exists, so promoted shots carry the approved "
    "prose verbatim (continuityProseIn/Out, for QA and review) with an EMPTY typed characters "
    "list — the join-check's per-character visible-marks protection is inactive for promoted "
    "shots until the storyboard schema gains typed continuity or Julian authorises a "
    "structuring pass.",
    "dialogue-timing: the storyboard's expectedTiming is directing prose, not numeric "
    "windows; promoted DialogueLines carry the whole-shot window (0..durationSec) as the "
    "documented 'approximate window inside the shot'.",
)


class HandoverRefused(Exception):
    """Raised BEFORE any write when the storyboard is not human-approved (or malformed)."""


def _md5(path):
    return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()


def _duration_from_range(rng):
    """'5-8s' → 5.0 — the LOW bound (cost-conservative: Seedance bills per second), clamped
    to the engine's own hard shot bounds. Mechanical, never invented."""
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(rng))]
    if not nums:
        raise HandoverRefused(f"un-parseable intendedDurationRange: {rng!r}")
    return float(min(max(nums[0], cb_engine.MIN_SHOT_SEC), cb_engine.MAX_SHOT_SEC))


def _mentions(name, text):
    return re.search(rf"\b{re.escape(name)}\b", text or "", re.IGNORECASE) is not None


def _characters_in_frame(sb_shot, participants):
    """Who is visible: the beat's participants that the shot's own approved staging prose
    names (word-boundary). Falls back to all participants rather than guessing a subset."""
    prose = " ".join(str(sb_shot.get(k) or "") for k in
                     ("blocking", "openingComposition", "principalPerformance",
                      "secondaryPerformance", "openingCharacterState"))
    named = [c for c in participants if _mentions(c, prose)]
    return named or list(participants)


def _assign_voices(voices, beat, beat_shots):
    """Mechanical voice→shot placement: a beat's VoicePerformance lands on the first of the
    beat's shots whose own approved dialoguePlacement names the speaker; otherwise on the
    beat's final shot. Never dropped — the caller asserts the verbatim line count survives."""
    out = {s["shotId"]: [] for s in beat_shots}
    for vp in voices:
        target = next((s for s in beat_shots
                       if _mentions(vp["speaker"], s.get("dialoguePlacement"))),
                      beat_shots[-1])
        out[target["shotId"]].append(vp)
    return out


def _dialogue_lines(vps, duration):
    lines = []
    for vp in vps:
        delivery = (vp.get("physicalActionRelationship") or vp.get("dramaticIntention") or "").strip()
        text = vp["exactDialogue"].strip()
        if text and text.lower() in delivery.lower():
            delivery = (vp.get("dramaticIntention") or "acting per the approved voice design").strip()
        lines.append({"speaker": vp["speaker"], "exactText": text, "delivery": delivery,
                      "startSec": 0.0, "endSec": float(duration)})
    return lines


def distil_shot(sb_shot, sb_beat, shot_voices, prev, characters_cfg):
    """ONE storyboard shot → ONE cb_engine.Shot (the protected, typed production contract) +
    the retained approved prose. Every creative field is the storyboard's own, verbatim."""
    duration = _duration_from_range(sb_shot["intendedDurationRange"])
    opener = (prev is None) or (sb_shot.get("transitionType") == "PLANNED_CUT"
                                 and sb_shot.get("requiresNewKeyframe"))
    opening = (f"{sb_shot['openingComposition'].strip().rstrip('.')}. "
               f"{sb_shot['openingCharacterState'].strip()}")
    cont = lambda: cb_engine.ContinuityState(
        lighting=sb_shot["lightingAndAtmosphere"], cameraSide=sb_shot["cameraAngle"],
        characters=[])                              # EMPTY by declared gap — see INTEGRATION_GAPS
    shot = cb_engine.Shot(
        shotId=sb_shot["shotId"], beatCode=sb_beat["beatId"], durationSec=duration,
        purpose=sb_shot["purpose"],
        performanceAssignment=sb_shot["principalPerformance"],
        camera=sb_shot["cameraBehaviour"],
        openingPose=opening,
        sourceType="opener" if opener else "relay",
        sourceShotId=None if opener else prev,
        cutInMotivation=sb_shot.get("cutMotivation"),
        dialogueBinding=sb_shot.get("dialoguePlacement") if shot_voices else None,
        dialogueLines=_dialogue_lines(shot_voices, duration),
        visualPayoff=sb_shot["closingComposition"],
        physicalStaging=None,
        prohibited=list(sb_shot.get("essentialProviderProtections") or [])[:3],
        charactersInFrame=_characters_in_frame(sb_shot, sb_beat["participatingCharacters"]),
        continuityIn=cont(), continuityOut=cont())
    retained = {"continuityProseIn": sb_shot.get("continuityIn"),
                "continuityProseOut": sb_shot.get("continuityOut"),
                "selectedInterpretation": sb_beat.get("selectedDirectorialInterpretation")}
    return shot, retained


def promote(storyboard_path, pkg_path, dry_run=True, log=print):
    """The handover. Refuses (no writes, current package untouched) unless the storyboard's
    scene-level approvalState is human-approved. On promotion: a NEW revision of the
    production package whose ONLY creative source is the approved storyboard."""
    sb = json.load(open(storyboard_path))
    if sb.get("approvalState") != APPROVED_STATE:
        raise HandoverRefused(
            f"REFUSED — storyboard {pathlib.Path(storyboard_path).name} is "
            f"'{sb.get('approvalState')}', not '{APPROVED_STATE}'. Only a human-approved "
            f"Authoritative Storyboard Package can be promoted; the current production "
            f"package is untouched.")

    pkg_path = pathlib.Path(pkg_path)
    old = json.load(open(pkg_path)) if pkg_path.exists() else {}
    try:
        characters_cfg = json.load(open(CHARS))
    except Exception:
        characters_cfg = {}
    scene = {"sceneName": sb.get("scene", {}).get("location") or old.get("sceneName", "")}

    beats = {b["beatId"]: b for b in sb["beats"]}
    shots_by_beat = {}
    for s in sb["shots"]:
        shots_by_beat.setdefault(s["beatId"], []).append(s)
    voices_by_beat = {}
    for vp in sb.get("voicePerformances", []):
        line_owner = next((bid for bid, b in beats.items()
                           if any(vp["exactDialogue"].strip() in d for d in b["exactDialogue"])),
                          sb["shots"][0]["beatId"])
        voices_by_beat.setdefault(line_owner, []).append(vp)

    shots_out, total, prev, line_count = [], 0.0, None, 0
    for bid, bshots in shots_by_beat.items():
        placement = _assign_voices(voices_by_beat.get(bid, []), beats[bid], bshots)
        for sb_shot in bshots:
            shot, retained = distil_shot(sb_shot, beats[bid],
                                          placement.get(sb_shot["shotId"], []),
                                          prev, characters_cfg)
            prompt, wc, slots = cb_engine.compile_shot_contract(shot, scene, characters_cfg)
            rec = shot.model_dump()
            rec.update(retained)
            rec["seedancePrompt"], rec["promptWords"], rec["referenceSlots"] = prompt, wc, slots
            rec["audioBrief"] = cb_engine.compile_audio_brief(shot)
            if shot.sourceType == "opener":
                kf, kwc, kslots = cb_engine.compile_keyframe_prompt(shot, scene, characters_cfg)
                rec["keyframePrompt"], rec["keyframePromptWords"] = kf, kwc
                rec["keyframeReferenceSlots"] = kslots
            line_count += len(shot.dialogueLines)
            shots_out.append(rec)
            total += shot.durationSec
            prev = shot.shotId

    expected = sum(len(b["exactDialogue"]) for b in sb["beats"])
    if line_count != expected:
        raise HandoverRefused(f"REFUSED — verbatim dialogue count broke in handover: storyboard "
                              f"has {expected} locked line(s), promoted package carries {line_count}.")

    # req 4 — creative-room internals never cross into production or the provider brief
    dump = json.dumps(shots_out, ensure_ascii=False)
    for banned in ("showrunnerJudgement", "dramaticConstruction", "audienceExperience",
                    "Hard constraints:"):
        if banned in dump:
            raise HandoverRefused(f"REFUSED — creative-room internal content ('{banned}') "
                                  f"leaked into the promoted package.")

    new_rev = int(old.get("revision") or 0) + 1
    pkg = {"episode": sb.get("episodeId", "Ep1"), "sceneNumber": str(sb.get("sceneNumber", "")),
           "sceneName": scene["sceneName"],
           "doctrine": "CREATIVE ROOM vNEXT handover — the approved storyboard is the sole "
                        "creative source (cb_handover.py)",
           "revision": new_rev,
           "revisionNote": f"Promoted from human-approved storyboard "
                            f"{pathlib.Path(storyboard_path).name}; every prior disclosure, "
                            f"sealed envelope and spend token is stale (binding hash changed).",
           "sourceStoryboard": {"path": str(storyboard_path), "md5": _md5(storyboard_path),
                                 "approvalState": sb["approvalState"],
                                 "humanNote": sb.get("humanNote", "")},
           "handover": {"distilled": ["opening state", "principal performance",
                                        "principal camera intention", "voice/audio relationship",
                                        "continuity in/out (prose verbatim + declared typed gap)",
                                        "<=3 essential protections"],
                         "integrationGaps": list(INTEGRATION_GAPS)},
           "shots": shots_out, "totalSec": round(total, 1),
           "voidedTokens": list(old.get("voidedTokens") or [])}
    if dry_run:
        log(f"HANDOVER DRY RUN — would write revision {new_rev} "
            f"({len(shots_out)} shots, ~{round(total)}s); nothing written, no provider call, "
            f"no media, no token.")
        return pkg
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)
    log(f"HANDOVER — wrote {pkg_path.name} revision {new_rev}: {len(shots_out)} shots, "
        f"~{round(total)}s. All prior spend authorisations are stale.")
    return pkg


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        raise SystemExit("usage: cb_handover.py <storyboard.json> <production_package.json> [--write]")
    promote(sys.argv[1], sys.argv[2], dry_run=("--write" not in sys.argv))
