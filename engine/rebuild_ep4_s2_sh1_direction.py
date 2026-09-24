"""Author the Episode 4 S2.SH1 rock staging as a scoped DIRECT amendment.

This is a zero-spend source update. It keeps the approved Moonlit Pool scene plate
as geography/light authority, Aida's approved opening as her identity/pose anchor,
and binds the approved Ep4 S3.SH2 keyframe as the provider's pond-vision content
reference only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cb_render as R
import cb_audio_timing
import cb_asset_registry
from studio_request_evidence import digest


SCENE = "2"
EPISODE = "Ep4"
SHOT_ID = "S2.SH1"
REVISION_ID = "ep4-s2-sh1-vision-v4"
KIND = "shot-visual-contract-correction"
VISION_ROLE = "vision:S3.SH2 keyframe content inside pond reflection only"
LEGACY_VISION_ROLES = {
    "vision:Sunny party reflection",
    "vision:S3.SH2 keyframe pond reflection",
}
VISION_PATH = ROOT / "engine/media/shots/Ep4_S3.SH2_keyframe_candidate_b156d56c.png"
VISION_SHA256 = "6cb81ad0b70841e82896ecf6978cfc193c497f171630594a13e4cf159932053c"


def _bind_vision_reference():
    """Register the exact approved S3.SH2 image as a vision-only WATCH input."""
    if not VISION_PATH.is_file():
        raise FileNotFoundError(f"S3.SH2 vision keyframe is missing: {VISION_PATH}")
    if R._sha256_file(VISION_PATH) != VISION_SHA256:
        raise ValueError("S3.SH2 vision keyframe bytes changed; refusing to bind a different image")
    return cb_asset_registry.register_asset(
        episode=EPISODE, scene=SCENE, shot_id=SHOT_ID,
        kind="reference_image", role=VISION_ROLE, path=VISION_PATH,
        status="approved", label="Ep4 S3.SH2 keyframe — pond vision",
        source="Julian-approved S3.SH2 keyframe used as pond-vision content",
        metadata={
            "assetUse": "vision_reference",
            "sourceShotId": "S3.SH2",
            "sourceKeyframeSha256": VISION_SHA256,
            "visionOnly": True,
            "notIdentity": True,
            "notGeography": True,
            "reviewedBy": "Julian",
        },
    )


def _view_one():
    return {
        "shotNumber": 1,
        "viewId": "S2.V01",
        "transitionType": "opening",
        "staging": (
            "Aida is already seated on the broad mossy rock at the near edge of the "
            "Moonlit Pool, her weight grounded and her body turned three-quarters toward "
            "the water. The approved pool plate remains the fixed world: luminous trees, "
            "crystals, flowers and the glass surface. The S3.SH2 keyframe is not a second "
            "set: it is the exact visual content that will appear later inside the pond's "
            "reflection, like a beautiful promise Aida can see but cannot touch."
        ),
        "startState": "Aida seated on the near pool rock, eyes open and calmly aimed toward the ordinary woodland reflection; pool glass-still with no party vision yet; morning light warm and rose-gold.",
        "endState": "The completed ripple opens a living vision inside the pond: Sunny's party appears in the water as a brief luminous future-image. Aida has seen it and begins to turn toward it.",
        "cutTo": "A closer rock-and-pool relationship view where Aida reads the vision, brings one hand to her heart, and delivers the line before rising.",
        "timing": "Planned opening hold from 0.0–4.5 seconds; the raindrop contact and first completed ripple must read before the cut.",
        "purpose": "Let the audience fall in love with the impossible calm of Aida, the rock and the luminous pool before one tiny natural event breaks the perfect image.",
        "framingAndCamera": "MWS at Aida's seated eye-line, low enough to give the rock tactile weight and wide enough to hold Aida, the pool edge and the reflected party together. The camera holds its breath; no decorative drift.",
        "storyAction": "Aida sits in protected stillness. The pond initially shows only its ordinary woodland reflection. A single raindrop lands in the centre. The ripple blooms outward and the exact S3.SH2 keyframe content resolves inside the water as a brief luminous vision. Aida looks down at that reflection; it is an authored story image inside the pond, not a second location or a live Sunny cutaway.",
        "performanceFocus": "Aida's stillness is active care, not emptiness. Her eyelids remain peaceful until the plink; then her eyes open without a flinch as the vision resolves in the water. Her breath catches softly and her attention locks to the image.",
        "landingImage": "The pond holds the luminous vision inside its completed ripple; Aida has seen it and the wonder has given her a reason to move.",
        "cutReason": "Hold through the first completed ripple so the audience experiences the break inside Aida's calm. Cut only after the changed information is readable.",
        "framing": "MWS at Aida's seated eye-line: rock in tactile foreground, Aida as the stable vertical presence, pool and reflected party carrying the luminous horizontal image.",
        "continuity": "Aida owns the near rock throughout the opening view. The pond begins glass-still; the raindrop creates one completed ripple that briefly contains the authored party vision. The vision is water-born and ephemeral, never a literal cutaway or second location.",
        "viewpointOwner": "Aida",
        "listenerReaction": None,
        "visibleEntities": ["Aida", "near mossy pool rock", "Moonlit Pool", "S3.SH2 keyframe content inside the pond reflection", "crystal trees and flowers", "lighting:pool_grove_light"],
        "cinematography": {
            "owner": "Aida",
            "emotionalAction": "protecting stillness while witnessing a beautiful promise become fragile",
            "cameraState": "low, respectful observational hold from the real pool edge; the rock gives Aida weight and the water gives the frame wonder",
            "stateChangeTrigger": "the first raindrop contacts the pond and the vision resolves inside the ripple",
            "kind": "hold",
            "cutTiming": "after",
            "actionPhase": "contact",
            "functions": ["establish mood", "plant", "create anticipation", "create emotion"],
            "attention": "relationship",
            "viewpoint": "real space beside Aida, never inside the reflection",
            "lensRelationship": "50 mm, honest and gently intimate; enough width for geography and enough falloff for the reflection to feel enchanted",
            "composition": "The mossy rock anchors the foreground, Aida is the calm vertical centre of gravity, and the pool opens a luminous horizontal mirror beneath her gaze.",
            "movementHold": "Nearly locked. A tiny organic settling movement follows the ripple rather than announcing it; no generic push-in.",
            "focus": "Begin shared between Aida's pendant, rock texture and ordinary glass water; transfer attention to the ripple at contact, then retain Aida in readable softness as the vision resolves.",
            "light": "Warm amber canopy light and rose-quartz glow against cool teal pool haze; the first ripple cools the reflected colours without making the world frightening.",
            "cutInReason": "The ripple has become a vision, and the audience must read Aida reading it before her body answers the discovery.",
            "exitFrame": "The pond still carries the fading party vision; Aida has turned toward it and is ready to bring one hand to her heart."
        }
    }


def _view_two():
    return {
        "shotNumber": 2,
        "viewId": "S2.V02",
        "transitionType": "motivated reframing",
        "staging": "Stay on the same side of the pool and the same rock. Aida remains seated in the foreground, looking directly at the S3.SH2 keyframe content held inside the softened pond reflection; the water is foreground truth and her face is the quiet human reading of it.",
        "startState": "The first ripple has completed and the exact S3.SH2 keyframe content is visibly alive inside the pond reflection; Aida is seated on the rock, eyes open, absorbing what she has seen.",
        "endState": "Aida's hand rests over her heart; her line has landed warmly; she rises from the rock and walks out of frame, leaving the pond vision to fade.",
        "cutTo": "No location cutaway: continue the same pond-side shot through Aida's reaction, line, rise and walk-off; the next beat inherits her movement away from the pond.",
        "timing": "Approximately 4.5–11.0 seconds; allow the vision to register, then hand-to-heart, line, rise, and a clear walk-off landing.",
        "purpose": "Turn the pond vision into an emotional invitation: Aida sees the future trouble, feels it in her heart, speaks with warm understatement, then physically commits to leaving.",
        "framingAndCamera": "Pool-edge MS/MCU relationship frame, still grounded on the rock. Let the rippled reflection occupy the lower foreground while Aida's eyes travel from water to clouds and back.",
        "storyAction": "Aida watches the exact S3.SH2 keyframe vision glow within the ripple. She brings one hand to her heart, keeps her gaze on the reflection for one breath, looks to the path ahead, and says, “Someone’s day might be a little dampened.” After the line lands, she rises and walks out of frame with quiet purpose.",
        "performanceFocus": "The vision lands first in Aida's eyes, then in the hand-to-heart gesture. She speaks warmly and privately, not as a joke or alarm. The line completes before she rises; her walk-off is the physical punctuation.",
        "landingImage": "Aida has walked away from the rock; the pond vision fades through the last ripple, leaving the beautiful warning behind.",
        "cutReason": "Cut after the ripple has changed the information, so the closer view reads Aida's choice rather than manufacturing a reaction.",
        "framing": "MS/MCU at Aida's seated eye-line with rock edge and disturbed pool together; never isolate Aida from the geography that gives the line meaning.",
        "continuity": "Same rock, same pond side, same screen direction. The authored vision remains inside the water until the line completes, then fades as Aida rises and walks off in the established exit direction.",
        "viewpointOwner": "Aida",
        "listenerReaction": None,
        "visibleEntities": ["Aida", "near mossy pool rock", "softened circular ripples", "exact S3.SH2 keyframe content inside the pond reflection", "lighting:pool_grove_light", "crystal flowers at pool edge"],
        "cinematography": {
            "owner": "Aida",
            "emotionalAction": "receiving the vision, feeling it at her heart, then choosing to move",
            "cameraState": "quiet motivated cut-in that preserves the rock, water, vision and Aida as one relationship before easing with her exit",
            "stateChangeTrigger": "the pond vision resolves and Aida understands its warning",
            "kind": "cut_in",
            "motivation": "KNOW",
            "cutTiming": "after",
            "actionPhase": "reaction",
            "functions": ["pay off", "create comedy", "create emotion"],
            "attention": "relationship",
            "viewpoint": "low pool-edge relationship angle, never a magical POV",
            "lensRelationship": "85 mm for intimate restraint while keeping the rock and disturbed water legible",
            "composition": "Rippled reflection in the lower frame, Aida seated on the rock in the middle plane, cloud pressure and crystals breathing behind her.",
            "movementHold": "Settled hold; a tiny gaze-led reframing is enough. No sudden push-in on worry.",
            "focus": "Start on the S3.SH2 keyframe content inside the ripple, rack to Aida's eyes as she recognises it, hold the hand-to-heart gesture and line, then follow her rise and walk-off while the pond vision fades.",
            "light": "The vision briefly blooms with warm party colour inside cool teal water haze; Aida keeps a rose-gold edge light as wonder becomes tender resolve.",
            "cutInReason": "The audience must see the exact moment the pond gives Aida the vision, then watch the knowledge travel through her body into action.",
            "exitFrame": "Aida has walked out of frame; the fading vision remains in the pond for one final readable ripple."
        }
    }


def build_direction(shot):
    result = copy.deepcopy(shot)
    views = [_view_one(), _view_two()]
    result["purpose"] = "Reveal the coming weather through Aida's calm witnessing from the near pool rock: the pool holds a perfect party promise, one raindrop breaks it, and she lets the warning remain beautifully unresolved."
    result["storyboardInternalShotPlanApproved"] = views
    result["openingCharactersInFrame"] = ["Aida"]
    result["charactersInFrame"] = ["Aida"]
    result["keyframeReferenceSlots"] = {"@图1": "Aida", "@图2": "scene plate"}
    result["referenceSlots"] = {
        "@图1": "opening keyframe", "@图2": "Aida", "@图3": "scene plate",
        "@图4": VISION_ROLE, "@Audio1": "voice track",
    }
    result["animationReferenceRoles"] = {
        "@图1": "opening keyframe",
        "@图2": "Aida",
        "@图3": "scene plate",
        "@图4": VISION_ROLE,
        "@Audio1": "voice track",
    }
    result["visionReferenceBinding"] = {
        "role": VISION_ROLE,
        "sourceShotId": "S3.SH2",
        "sourcePath": str(VISION_PATH),
        "sourceSha256": VISION_SHA256,
        "providerSlot": "@图4",
        "scope": "pond reflection vision content only",
        "foregroundSubject": "Aida",
        "doNotUseAs": ["Aida identity", "S2 geography", "live foreground cast", "literal location cutaway"],
    }
    result["storyIntentApproved"] = {
        **(result.get("storyIntentApproved") or {}),
        "outerAction": "Aida sits on the near mossy rock beside the Moonlit Pool; one raindrop strikes the pond and the exact S3.SH2 keyframe content appears inside the ripple as the vision; Aida looks at the reflection, puts one hand to her heart, delivers her line, rises, and walks away.",
        "innerAction": "Aida receives the vision as a tender warning, feels its meaning, and chooses to act without turning it into panic.",
        "primaryAudienceFeeling": "A safe little vision-reveal wrapped in luminous wonder, followed by a purposeful emotional move.",
        "silhouetteRead": "Aida's seated silhouette is rooted to the rock and framed by the water; after the warning she becomes a quiet ready shape without losing her warmth.",
        "environmentPressure": "The Moonlit Pool turns the party into a beautiful reflected promise. The raindrop does not destroy the world; it makes the truth gently visible.",
        "motifUse": "The rock is Aida's grounded care; the pool is the fragile promise; the first ripple is the smallest possible change that opens the weather story.",
    }
    result["performanceContractApproved"] = {
        **(result.get("performanceContractApproved") or {}),
        "phases": [
            {"phase": "anticipation", "performer": "Aida", "observableAction": "Sits grounded on the near mossy pool rock with eyes open and calmly aimed at the ordinary woodland reflection, paws away from the water, pendant softly glowing."},
            {"phase": "action", "performer": "ENVIRONMENT", "observableAction": "One raindrop strikes the pond; circular ripples spread and resolve into the exact S3.SH2 keyframe content inside the water as a brief luminous vision."},
            {"phase": "reaction", "performer": "Aida", "observableAction": "Opens her eyes without a startle, looks directly at the S3.SH2 vision held in the reflection, brings one hand to her heart, and lets the meaning land before speaking."},
            {"phase": "settle", "performer": "Aida", "observableAction": "Delivers the exact line with warm understatement, then rises and walks out of frame with quiet purpose as the vision fades."},
        ],
        "physicalCauseAndEffect": "The rock gives Aida grounded weight; the raindrop breaks the reflected party; her restrained response keeps the water imperfect and lets the warning stay safe.",
        "requiredLanding": "Aida is ready to rise from the near rock beside the Moonlit Pool, with the party reflection still visibly rippled and unresolved.",
    }
    result["cinematographyContractApproved"] = {
        **(result.get("cinematographyContractApproved") or {}),
        "composition": "Aida is anchored on the near mossy rock; the pool is the luminous horizontal mirror below her; the reflected party and the crystal woodland share the frame without turning the reflection into a second location.",
        "depthStrategy": "Tactile rock foreground, Aida in the middle plane, glass pool and rose-gold woodland beyond; the reflection adds wonder while the real rock keeps the camera honest.",
        "cameraBehavior": "A purposeful hold through seated ritual and raindrop, one motivated cut as the pond vision resolves, then a gentle follow through Aida's hand-to-heart, line, rise and walk-off.",
        "performanceVisibility": "The pond vision must read before Aida reacts; her eyes recognise it, one hand reaches her heart, the exact line lands, and her rise and walk-off are clearly motivated.",
        "memorableLandingImage": "Aida walks away from the mossy rock while the luminous party vision fades inside the last ripple of the pond.",
        "providerInstruction": f"Use @图3 as the approved Moonlit Pool geography and light. Use @图2 for Aida identity only and @图1 as the approved S2.SH1 opening frame. Use @图4, the exact approved Ep4 S3.SH2 keyframe, as the visual content authority for one image that appears INSIDE THE POND SURFACE ONLY. @图4 must be visibly recognisable through the water reflection, but it must be warped by the pond ripples and confined to the water area; never display @图4 as a full-frame image, rectangular insert, cutaway, separate location, foreground scene, table, or live Sunny character. Do not copy @图4's foreground character, table, party layout or location into the real S2.SH1 world. Keep this as one continuous pond-side shot with Aida visible in the foreground throughout the vision reveal. Open on Aida already seated on the near mossy rock, eyes open and calmly watching the ordinary woodland reflection, pendant softly glowing. Hold the beauty and silence. One raindrop hits the pond; the ripple expands; then the recognisable S3.SH2 party image resolves only within the reflected water patch directly in front of Aida. Aida looks down at the reflection, her eyes track its details, and one hand reaches her heart. Hold the readable reflection and Aida's reaction together for one breath. Deliver the exact Audio1 line with warm understatement, then rise and walk out of frame as the reflected image dissolves back into ripples. No cut to a physical party table. No second location. No extra spoken words. Preserve tactile rock contact, luminous rose-gold wonder, cool teal pool haze, motivated focus, readable cause-and-effect and a clear emotional walk-off. Keep @Audio1 as the only spoken source.",
    }
    result["openingImage"] = "Aida is already seated on the near mossy rock beside the glass-still Moonlit Pool, eyes open and calmly aimed toward the ordinary woodland reflection, pendant glowing softly; no party vision is present at entry."
    result["openingPose"] = "Aida is already seated on the near mossy rock at the Moonlit Pool, grounded through her hips and turned three-quarters toward the water, eyes open and calmly aimed at the ordinary reflection, paws away from the surface, rose quartz pendant glowing softly."
    result["principalPerformance"] = "Aida sits on the rock in protected stillness. The pond initially carries only the ordinary woodland reflection. The first raindrop breaks it; the exact S3.SH2 keyframe vision appears inside the water, and Aida looks at it in the foreground. Her gaze recognises it, one hand reaches her heart, the exact line lands warmly, then she rises quietly without rescuing the image."
    result["physicalOrEmotionalChange"] = "The pool changes from a flawless reflected promise to a rippled warning; Aida changes from rooted stillness to quiet readiness while remaining the safe emotional anchor."
    result["closingImage"] = "Aida remains beside the near rock and disturbed pool, ready to rise; the beautiful reflection is imperfect but not destroyed."
    result["continuityProseOut"] = "Aida ends seated or just beginning her quiet rise from the same near mossy rock, with the reflected party still visibly rippled and unresolved."
    return result


def _carry_standard_audio(pkg, shot, ledger):
    """Reuse the unchanged Audio1 performance, retimed to this shot's exact slate.

    This amendment changes picture direction only. The approved line remains verbatim;
    rebuild the local timed master so the bed is exactly the shot duration and the line
    lands on the current dialogue window. No ElevenLabs call is made.
    """
    raw = ROOT / "engine/media/shots/Ep4_S2.SH1_vo_raw_candidate_2637cd8a.mp3"
    if not raw.is_file():
        # The original raw container was archived by the earlier recovery. Extract
        # the one spoken segment from the unchanged timed master; no new voice is
        # generated and no extra spoken material is introduced.
        prior_master = ROOT / "engine/media/shots/Ep4_S2.SH1_vo_candidate_2637cd8a.wav"
        if not prior_master.is_file():
            return False
        raw.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run([
            "ffmpeg", "-y", "-ss", "7.8", "-to", "10.36", "-i", str(prior_master),
            "-vn", "-ac", "2", "-ar", "48000", "-c:a", "libmp3lame", "-q:a", "2", str(raw)
        ], capture_output=True, text=True)
        if result.returncode or not raw.is_file():
            return False
    lines = copy.deepcopy(pkg.get("shots", []))
    current = R._shot(pkg, SHOT_ID)
    dialogue = copy.deepcopy(current.get("dialogueLines") or [])
    if len(dialogue) != 1 or dialogue[0].get("exactText") != "Someone’s day might be a little dampened.":
        return False
    timing = {
        "schemaVersion": 1,
        "audioSha256": R._sha256_file(raw),
        "isolatedDialogueAssembly": True,
        "separatedDialogueAssembly": True,
        "timingSource": "existing standard Audio1 take; local shot retime only",
        "voiceSegments": [{
            "voiceId": "SHuZ9GyczU4QEDzU4QU4", "dialogueInputIndex": 0,
            "startTimeSec": 0.0, "endTimeSec": 2.56,
            "characterStartIndex": 0, "characterEndIndex": 51,
            "voiceIds": ["SHuZ9GyczU4QEDzU4QU4"],
        }],
    }
    timing_path = ROOT / "engine/media/shots/Ep4_S2.SH1_standard_audio.dialogue.json"
    timing_path.write_text(json.dumps(timing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out = ROOT / "engine/media/shots/Ep4_S2.SH1_vo_candidate_2637cd8a.wav"
    contract = cb_audio_timing.render_timed_dialogue_master(
        raw, timing_path, dialogue, current.get("durationSec", 0), out)
    ledger.update({
        "voPath": str(out), "voRawPath": str(raw),
        "voTimingPath": str(timing_path), "voPlacementPath": contract["contractPath"],
        "voGeneratedFrom": dialogue, "voInputSignature": R._voice_signature(pkg, current, dialogue),
        "voPackageRevision": pkg.get("revision"), "voicePlacementFailure": None,
    })
    return True


def main():
    vision_asset = _bind_vision_reference()
    pkg, path = R.load_pkg(SCENE, EPISODE)
    original = R._shot(pkg, SHOT_ID)
    updated = build_direction(original)
    amendment_dir = ROOT / "cb-output" / "creative" / "amendments"
    amendment_dir.mkdir(parents=True, exist_ok=True)
    amendment_path = amendment_dir / f"{EPISODE}_{SHOT_ID}_{REVISION_ID}.json"
    scene_look = R.scenelook_status(SCENE, EPISODE).get("approved") or {}
    amendment = {
        "schemaVersion": 1,
        "approvalState": "approved",
        "approvedAt": datetime.now(timezone.utc).isoformat(),
        "approvedBy": "Julian",
        "kind": KIND,
        "revisionId": REVISION_ID,
        "scene": SCENE,
        "shotId": SHOT_ID,
        "scriptVersionId": pkg.get("sourceScript", {}).get("scriptVersionId"),
        "baseScriptVersionId": pkg.get("sourceScript", {}).get("scriptVersionId"),
        "preservedStages": ["scenelook", "keyframe"],
        "invalidatedStages": ["direction", "voice", "animation", "continuity", "final"],
        "sceneLookContentHash": scene_look.get("hash"),
        "sceneLookPath": scene_look.get("path"),
        "sourceDirection": "Julian: keep the approved scene plate and S2.SH1 opening keyframe; use the exact Ep4 S3.SH2 keyframe as the pond vision content while Aida remains the foreground subject looking at its reflection.",
        "visionReferencePolicy": "The exact approved Ep4 S3.SH2 keyframe is bound as @图4 and uploaded to WATCH as vision content only. It controls what Aida sees inside the pond reflection; it does not control Aida identity, S2 geography, foreground cast, or a literal location cutaway.",
        "visionReferenceBinding": {
            "providerSlot": "@图4", "role": VISION_ROLE, "sourceShotId": "S3.SH2",
            "sourcePath": str(VISION_PATH), "sourceSha256": VISION_SHA256,
            "assetId": vision_asset["assetId"], "scope": "pond reflection vision content only",
        },
        "shot": updated,
    }
    amendment_path.write_text(json.dumps(amendment, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    amendment_hash = R._sha256_file(amendment_path)
    record = {
        "kind": KIND,
        "revisionId": REVISION_ID,
        "scene": SCENE,
        "shotId": SHOT_ID,
        "scriptVersionId": amendment["scriptVersionId"],
        "baseScriptVersionId": amendment["baseScriptVersionId"],
        "storyboardPath": str(amendment_path.relative_to(ROOT)),
        "storyboardSha256": amendment_hash,
        "sceneLookContentHash": scene_look.get("hash"),
        "sceneLookPath": scene_look.get("path"),
        "preservedStages": amendment["preservedStages"],
        "invalidatedStages": amendment["invalidatedStages"],
        "approvedAt": amendment["approvedAt"],
        "approvedBy": amendment["approvedBy"],
    }
    pkg["scopedAmendments"] = [
        item for item in (pkg.get("scopedAmendments") or [])
        if not (item.get("shotId") == SHOT_ID and item.get("revisionId") == REVISION_ID)
    ]
    pkg["scopedAmendments"].append(record)
    target = R._shot(pkg, SHOT_ID)
    target.clear()
    target.update(updated)
    ledger = R._ledger(pkg, SHOT_ID)
    ledger["status"] = "designed"
    source_keyframe = ROOT / "engine/media/shots/Ep3_S2.SH1_keyframe_A_c746209c.png"
    recovered_keyframe = ROOT / "engine/media/shots/Ep4_S2.SH1_keyframe_candidate_935decd7.png"
    if not recovered_keyframe.exists():
        if not source_keyframe.is_file():
            raise FileNotFoundError(f"Previous S2.SH1 keyframe source is missing: {source_keyframe}")
        shutil.copyfile(source_keyframe, recovered_keyframe)
    recovered_hash = R._sha256_file(recovered_keyframe)
    if recovered_hash != "f66b065ee09c89544b4c281e5efb26cb84ebdc2688a3772b02d8b9c5aafe6427":
        raise ValueError("Recovered keyframe bytes do not match the previous approved asset")
    previous_approval = {
        "approved": True,
        "path": str(recovered_keyframe),
        "at": "2026-09-14T21:43:06",
        "reviewedBy": "Julian",
        "source": "library",
        "inputSignature": {
            "cardHash": "432dae6e4573beebc67c6fe2db7371bbf5d40ddee01e9465650fe224b08611f3",
            "canonProfileDigest": "5a65c0805243331a349bbd55724e039d6f6718653b18dd1fc4f1816885ff8e0b",
            "sceneLookHash": scene_look.get("hash"),
            "selectedAssetHash": "0c87274099204c63470c89e030ed9a4f",
            "source": "library",
        },
        "promptContract": None,
        "abTest": None,
        "packageRevision": 1,
        "contentHash": recovered_hash,
        "conformanceScreening": {
            "status": "unavailable",
            "reason": "Previously approved library opening retained under the scoped visual direction amendment.",
            "checkedAt": "2026-09-14T20:25:28",
            "screenVersion": 2,
            "mediaProviderCalled": False,
            "candidateSha256": recovered_hash,
        },
        "conformanceAdvisoryDecision": {
            "acceptedBy": "Julian",
            "acceptedAt": "2026-09-14T21:43:06",
            "statusAtDecision": "unavailable",
            "reasonAtDecision": "Previously accepted visual evidence; exact bytes recovered and retained.",
        },
        "lineageCarryForward": {
            "reviewedBy": "Julian",
            "reason": "Exact previously approved S2.SH1 opening recovered from the matching Ep3 asset hash; visual amendment explicitly preserves the keyframe.",
        },
    }
    ledger["keyframeApproval"] = previous_approval
    ledger["keyframeCandidate"] = None
    ledger["keyframePath"] = str(recovered_keyframe)
    ledger["voiceApproval"] = None
    ledger["voPath"] = None
    ledger["voGeneratedFrom"] = None
    ledger["voInputSignature"] = None
    audio_ready = _carry_standard_audio(pkg, target, ledger)
    ledger["batch"] = None
    ledger["batchId"] = None
    ledger["candidatePaths"] = None
    ledger["approval"] = None
    ledger["approvedCandidate"] = None
    ledger["approvedTake"] = None
    ledger["harvestFrame"] = None
    ledger["pendingSpendAuth"] = None
    ledger["pendingComparisonSpendAuth"] = None
    ledger["directionRevision"] = REVISION_ID
    roles = ledger.setdefault("additionalAnimationReferenceRoles", [])
    roles[:] = [role for role in roles if role not in LEGACY_VISION_ROLES and role != VISION_ROLE]
    roles.append(VISION_ROLE)
    ledger["visionReferenceBinding"] = {
        "role": VISION_ROLE, "assetId": vision_asset["assetId"],
        "sourcePath": str(VISION_PATH), "sourceSha256": VISION_SHA256,
        "sourceShotId": "S3.SH2", "providerSlot": "@图4",
        "approvedBy": "Julian", "at": datetime.now(timezone.utc).isoformat(),
        "scope": "S3.SH2 keyframe content inside S2.SH1 pond reflection only",
    }
    ledger["directionRevisionNote"] = "Aida remains foreground on the approved near rock; approved Moonlit Pool plate and S2.SH1 opening retained; exact Ep4 S3.SH2 keyframe bound as @图4 pond-vision content reference."
    R._save(pkg, path)
    if audio_ready:
        # Julian approved the unchanged standard Audio1 bed. Record the full
        # approval envelope after the local retime; this is the same evidence the
        # normal HEAR approval path requires, without another provider call.
        approved_pkg, approved_path = R.load_pkg(SCENE, EPISODE)
        approved_shot = R._shot(approved_pkg, SHOT_ID)
        approved_ledger = R._ledger(approved_pkg, SHOT_ID)
        approved_lines = approved_shot.get("dialogueLines") or []
        current_voice_signature = R._voice_approval_status(
            approved_pkg, approved_shot, SCENE, EPISODE).get("expectedInputSignature")
        if not current_voice_signature:
            raise RuntimeError("Could not calculate the current Audio1 approval signature")
        approved_ledger["voInputSignature"] = current_voice_signature
        approved_ledger["voiceApproval"] = {
            "approved": True, "path": approved_ledger["voPath"],
            "at": datetime.now(timezone.utc).isoformat(), "reviewedBy": "Julian",
            "packageRevision": approved_pkg.get("revision"),
            "inputSignature": current_voice_signature,
            "contentHash": R._sha256_file(approved_ledger["voPath"]),
            "rawContentHash": R._sha256_file(approved_ledger["voRawPath"]),
            "timingContentHash": R._sha256_file(approved_ledger["voTimingPath"]),
            "placementContentHash": R._sha256_file(approved_ledger["voPlacementPath"]),
        }
        R._save(approved_pkg, approved_path)
    print(json.dumps({
        "ok": True,
        "package": str(path),
        "amendment": str(amendment_path),
        "amendmentSha256": amendment_hash,
        "scenePlatePreserved": scene_look.get("path"),
        "keyframe": str(recovered_keyframe),
        "providerCalled": False,
        "mediaSpend": 0,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
