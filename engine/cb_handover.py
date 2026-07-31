#!/usr/bin/env python3
"""cb_handover.py — HUMAN GATE A -> PRODUCTION (2026-07-17, corrected for creative-room-2.0).

READ-ONLY AUDIT FINDING (2026-07-17, single-shot handover directive): this module's
distil_shot()/promote() were built against an EARLIER storyboard field shape (fields
directly on the shot: openingComposition, cameraBehaviour, closingComposition,
intendedDurationRange, continuityIn/Out, lightingAndAtmosphere, cameraAngle). The
whole-scene-treatment rebuild (commit 7d5762e) and the schema checkpoint (commit 35dc12c)
both changed the storyboard's actual shape underneath this module without sweeping it —
its own field lookups would KeyError against the CURRENT CreativeShotCard + separate
ProductionDetail schema, and its own test suite's synthetic fixtures used the same stale
shape, so the tests passed while testing a fiction. Corrected here, in place — the
functions, names and cb_engine-delegation architecture are REUSED, not replaced by a
parallel pipeline.

Promotes a HUMAN-APPROVED Authoritative Storyboard Package (cb_creative.py's output) into a
NEW, VERSIONED production shot package. The approved storyboard becomes the SOLE creative
source: every creative field in the promoted package traces to the storyboard's own approved
scene/beat/shot/voice direction, distilling ONLY:

    1. the approved opening state          (openingImage + the shot's own opening state)
    2. the typed Gate-5 performance contract (deterministically compiled from observable
                                             phases, cause/effect, visible turn, landing and
                                             acting freedom; all review prose stays retained)
    3. the principal camera intention      (cameraRelationship, verbatim)
    4. the approved voice/audio relationship (assigned VoicePerformances + locked dialogue)
    5. continuity in/out                   (complete typed boundary states, mapped directly;
                                            prose is retained for review only)
    6. up to three genuinely essential protections (essentialProviderProtections -> prohibited)

Showrunner judgements, rejected interpretations, internal revision history, escalations,
taste canons and constraint walls NEVER cross into the promoted package or the provider brief
(asserted at promotion time, and by test_cb_handover.py).

Provider isolation by construction: this module never imports cb_gen or cb_render. BOTH
prompt compilers are delegated to cb_engine — compile_shot_contract for the motion brief,
compile_keyframe_prompt for the keyframe — called directly, never wrapped or
post-processed. cb_engine.py remains the sole owner of keyframe and motion-brief
compilation; this module's own job is mapping approved fields onto cb_engine's typed Shot
contract, resolving references, placing dialogue and carrying the Voice Director brief — it
compiles nothing itself. A promotion bumps the package revision and rewrites the shots,
which changes cb_render's _shots_hash/_binding_hash inputs — every earlier disclosure,
sealed envelope and spend token is therefore stale at the existing fire-time binding check,
with zero new code at the provider boundary.

THE 2026-07-17 HANDOVER-MAPPING CORRECTION, IN TWO PASSES:
  PASS ONE (Julian's directive, after the S1.SH1 dry-run proved the pipeline structurally
  sound) found three real mapping defects and fixed them, but the keyframe/motion-brief
  fixes were built as a SECOND compiler inside this module — real, correct output, but
  duplicate compiler responsibility alongside cb_engine.py.
  PASS TWO (Julian's consolidation correction, same day) moved both fixes to their actual
  source, cb_engine.py — the one, narrowly-scoped exception to that file's usual
  protection, limited to the two proven hardcoded defects this audit found:
    1. KEYFRAME MAPPING — cb_engine.compile_keyframe_prompt used to hardcode a universal
       'anticipation instant before the action, never the payoff' framing and ban 'the
       action already happening'. Both were false universals: the approved opening state
       may be motion already underway (S1.SH1) or deliberate stillness (S1.SH6). Fixed
       directly in that function — see its own 2026-07-17 correction note.
    2. MOTION-BRIEF MAPPING — cb_engine.compile_shot_contract used to unconditionally
       append 'and screen sides' to its closing preservation line. That default is now
       gone, unconditionally, with no new detector added anywhere (Julian's own point 4) —
       see that function's own 2026-07-17 correction note, including the honest flag that
       an authored screen-side requirement (shot.prohibited) does not yet reach the
       shipped prompt through any path, a separate, pre-existing, undecided question.
  VOICE MAPPING (unchanged by the consolidation — always this module's own responsibility,
  never cb_engine's): _dialogue_lines used to abstract the approved elevenLabsV3Direction
  away in favour of dramaticIntention. delivery now carries the real V3 direction verbatim,
  and _voice_director_brief_lines exposes exactDialogue/elevenLabsV3Direction/
  expectedTiming/physicalActionRelationship as four discrete approved fields, never
  collapsed into one abstracted string.

THE 2026-07-30 TYPED EXECUTION CUTOVER: principalPerformance, physicalPerformance and
animationTiming are all retained as approved review context, but none is executable. Gate 5
now owns a ShotPerformanceContract whose ordered observable phases, cause/effect, visible
turn, landing and acting freedom compile deterministically through cb_engine. Production
Detail likewise carries complete typed continuity boundaries and per-occurrence numeric
dialogue windows. A storyboard predating any of these fields refuses promotion and must be
regenerated; this module never recreates the missing decisions from prose.

dry_run=True (the default) computes and returns everything and writes NOTHING.
"""
import datetime
import hashlib
import json
import pathlib
import re
import shutil

import cb_engine
import cb_db
import cb_lineage
import cb_scripts

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CHARS = HERE.parent / "shows" / "crystal-bears" / "canon" / "characters.json"
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)

APPROVED_STATE = "approved"          # what /api/storyboard-approve writes at top level


def _require_storyboard_lineage(sb, episode):
    """Prove the approved storyboard still belongs to the active source graph."""
    try:
        current = SCRIPT_STORE.current(episode, required=True)
    except cb_scripts.ScriptStoreError as exc:
        raise HandoverRefused(str(exc)) from exc
    source = sb.get("sourceScript") or {}
    if (source.get("scriptVersionId") != current["scriptVersionId"] or
            source.get("sha256") != current["sha256"]):
        raise HandoverRefused(
            "REFUSED — storyboard belongs to a different or unversioned script; rebuild Story & Direction")

    beat_source = sb.get("sourceBeatPackage") or {}
    beat_record = beat_source.get("contentSignature") or {}
    beat_path = ROOT / str(beat_source.get("path") or "")
    if not beat_path.is_file():
        raise HandoverRefused("REFUSED — storyboard's signed source beat package is missing")
    beat_pkg = json.loads(beat_path.read_text())
    expected_beat = cb_lineage.beat_package_signature(beat_pkg)
    if beat_record != expected_beat or beat_pkg.get("contentSignature") != expected_beat:
        raise HandoverRefused("REFUSED — storyboard's source beat package changed after direction")
    source_report = cb_lineage.validate_beat_package_source_contract(beat_pkg)
    if not source_report["ok"]:
        raise HandoverRefused(
            "REFUSED — storyboard source beat package has no valid exact-event contract: "
            + ", ".join(source_report["issues"][:5]))

    source_beats = [beat for beat in (beat_pkg.get("beats") or [])
                    if str(beat.get("sceneNumber")) == str(sb.get("sceneNumber"))]
    storyboard_beats = list(sb.get("beats") or [])
    if [beat.get("beatId") for beat in storyboard_beats] != [
            beat.get("beatCode") for beat in source_beats]:
        raise HandoverRefused(
            "REFUSED — storyboard dropped, duplicated or reordered source beats")
    for directed, source_beat in zip(storyboard_beats, source_beats):
        for directed_key, source_key in (
                ("sourceBeatId", "sourceBeatId"),
                ("sourceEventIds", "sourceEventIds"),
                ("sourceEventRange", "sourceEventRange"),
                ("sourceEventSignature", "sourceEventSignature")):
            if directed.get(directed_key) != source_beat.get(source_key):
                raise HandoverRefused(
                    f"REFUSED — storyboard beat {directed.get('beatId')} changed "
                    f"its locked {directed_key}")
        expected_occurrences = [{
            "dialogueOccurrenceId": cut["dialogueOccurrenceId"],
            "sourceEventId": cut["sourceEventId"],
            "sourceEventIndex": cut["sourceEventIndex"],
            "beatId": source_beat["beatCode"],
            "sourceBeatId": source_beat["sourceBeatId"],
            "speaker": cut["speaker"],
            "exactText": cut["exactText"],
        } for cut in (source_beat.get("cuts") or [])
          if cut.get("sourceType") == "dialogue"]
        if directed.get("dialogueOccurrences") != expected_occurrences:
            raise HandoverRefused(
                f"REFUSED — storyboard beat {directed.get('beatId')} changed its exact "
                "dialogue occurrences")

    signature = sb.get("inputSignature") or {}
    inputs = signature.get("inputs") or {}
    if (not cb_lineage.signature_matches(signature, "scene-storyboard", inputs) or
            inputs.get("scriptVersionId") != current["scriptVersionId"] or
            inputs.get("beatPackageDigest") != expected_beat["digest"]):
        raise HandoverRefused("REFUSED — storyboard dependency signature is missing or stale")
    return current, expected_beat

# Keys of the storyboard that are CREATIVE-ROOM INTERNAL and must never reach production:
NEVER_PROMOTED = ("showrunnerJudgement", "internalRevisions", "escalation", "vision",
                   "interpretations", "treatments", "treatmentSelection",
                   "rejectedApproachSummaries", "canonCompletionProposal")

# Genuinely essential protections: provider-facing. rejectionChecks/audienceExperience/
# transitionReason etc. are creative reasoning, not protections, and are never promoted.

INTEGRATION_GAPS = (
    "physical-staging: CreativeShotCard does not yet carry cb_engine.PhysicalStaging's "
    "four-field BIG-comedy gag contract. Typed performance cause/effect and landing data "
    "are preserved, but a scene explicitly classified BIG comedy still requires a separate "
    "authored physical-staging contract before validation can pass.",
)

# The provider (fal/Seedance) takes ONE integer-second duration end to end — confirmed by
# direct code read, not assumed: cb_gen.generate_video_seedance's own `duration=8` default is
# cast via str(duration), and cb_render.py's own fire call passes
# duration=str(int(round(envelope["durationSec"]))). A creative-approved RANGE (e.g. "5-7s")
# is normalized to its MIDPOINT, rounded to the nearest whole second — Julian's own stated
# rule for this checkpoint (2026-07-17): "If Seedance requires a fixed duration, 6s is the
# valid production normalization" for a 5-7s range.
def normalize_duration_for_provider(rng):
    """Use the same exact duration policy as creative timing validation."""
    try:
        return cb_engine.normalize_duration_range(rng)
    except ValueError as exc:
        raise HandoverRefused(str(exc)) from exc


class HandoverRefused(Exception):
    """Raised BEFORE any write when the storyboard is not human-approved (or malformed)."""


def _md5(path):
    return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()


def _mentions(name, text):
    return re.search(rf"\b{re.escape(name)}\b", text or "", re.IGNORECASE) is not None


def _validate_storyboard_dialogue_contract(storyboard):
    """Prove the exact occurrence partition before any storyboard can cross Gate A."""
    beats = list(storyboard.get("beats") or [])
    if not beats:
        return []
    occurrences = []
    owner_by_id = {}
    for beat_index, beat in enumerate(beats):
        source_beat_id = beat.get("sourceBeatId")
        source_event_ids = beat.get("sourceEventIds") or []
        source_signature = beat.get("sourceEventSignature") or {}
        if not source_beat_id or not source_event_ids or not source_signature:
            raise HandoverRefused(
                f"REFUSED — beat {beat.get('beatId') or beat_index} has no immutable "
                "source-event contract; rebuild Story & Direction")
        beat_occurrences = list(beat.get("dialogueOccurrences") or [])
        display = [f"{item.get('speaker')}: {item.get('exactText')}"
                   for item in beat_occurrences]
        if list(beat.get("exactDialogue") or []) != display:
            raise HandoverRefused(
                f"REFUSED — beat {beat.get('beatId')} dialogue display no longer mirrors "
                "its typed occurrences")
        for item in beat_occurrences:
            occurrence_id = item.get("dialogueOccurrenceId")
            if (not occurrence_id or not item.get("sourceEventId") or
                    item.get("beatId") != beat.get("beatId") or
                    item.get("sourceBeatId") != source_beat_id or
                    item.get("sourceEventId") not in source_event_ids):
                raise HandoverRefused(
                    f"REFUSED — beat {beat.get('beatId')} carries a malformed dialogue occurrence")
            if occurrence_id in owner_by_id:
                raise HandoverRefused(
                    f"REFUSED — dialogue occurrence {occurrence_id} is duplicated across beats")
            owner_by_id[occurrence_id] = beat.get("beatId")
            occurrences.append(item)

    expected_ids = [item["dialogueOccurrenceId"] for item in occurrences]
    voices = list(storyboard.get("voicePerformances") or [])
    voice_ids = [voice.get("dialogueOccurrenceId") for voice in voices]
    if voice_ids != expected_ids:
        raise HandoverRefused(
            "REFUSED — VoicePerformances dropped, duplicated or reordered dialogue "
            f"occurrences: expected {expected_ids}, got {voice_ids}")
    by_occurrence = {item["dialogueOccurrenceId"]: item for item in occurrences}
    for voice in voices:
        source = by_occurrence[voice["dialogueOccurrenceId"]]
        for voice_key, source_key in (("sourceEventId", "sourceEventId"),
                                      ("beatId", "beatId"),
                                      ("sourceBeatId", "sourceBeatId"),
                                      ("speaker", "speaker"),
                                      ("exactDialogue", "exactText")):
            if voice.get(voice_key) != source.get(source_key):
                raise HandoverRefused(
                    f"REFUSED — VoicePerformance {voice['dialogueOccurrenceId']} changed "
                    f"its locked {voice_key}")

    details = {detail.get("shotId"): detail
               for detail in (storyboard.get("productionDetail") or [])}
    assigned = []
    shots = list(storyboard.get("shots") or [])
    for shot in shots:
        detail = details.get(shot.get("shotId")) or {}
        shot_assignments = list(detail.get("dialogueOccurrenceIds") or [])
        timing_windows = detail.get("dialogueTimings")
        if not isinstance(timing_windows, list):
            raise HandoverRefused(
                f"REFUSED - {shot.get('shotId')} has no typed dialogueTimings contract")
        timing_ids = [window.get("dialogueOccurrenceId")
                      for window in timing_windows if isinstance(window, dict)]
        if len(timing_ids) != len(timing_windows) or timing_ids != shot_assignments:
            raise HandoverRefused(
                f"REFUSED - {shot.get('shotId')} dialogue timing IDs do not exactly match "
                "its occurrence assignments")
        for occurrence_id in shot_assignments:
            if occurrence_id not in owner_by_id:
                raise HandoverRefused(
                    f"REFUSED — {shot.get('shotId')} assigns unknown dialogue occurrence "
                    f"{occurrence_id}")
            if owner_by_id[occurrence_id] not in (shot.get("beatIds") or []):
                raise HandoverRefused(
                    f"REFUSED — {shot.get('shotId')} assigns {occurrence_id} from a beat "
                    "the shot does not carry")
            assigned.append(occurrence_id)
    if assigned != expected_ids:
        raise HandoverRefused(
            "REFUSED — Production Detail dropped, duplicated or reordered dialogue "
            f"occurrences: expected {expected_ids}, got {assigned}")

    inputs = {
        "orderedSourceBeatIds": [beat["sourceBeatId"] for beat in beats],
        "orderedDialogueOccurrenceIds": expected_ids,
        "voiceOccurrenceIds": voice_ids,
        "shotAssignments": {
            detail.get("shotId"): list(detail.get("dialogueOccurrenceIds") or [])
            for detail in (storyboard.get("productionDetail") or [])},
        "shotTimingWindows": {
            detail.get("shotId"): list(detail.get("dialogueTimings") or [])
            for detail in (storyboard.get("productionDetail") or [])},
    }
    expected_contract = {"schemaVersion": 2, **inputs,
                         "inputSignature": cb_lineage.dependency_signature(
                             "scene-dialogue-occurrences", inputs)}
    if storyboard.get("dialogueContract") != expected_contract:
        raise HandoverRefused(
            "REFUSED — storyboard dialogue occurrence signature is missing or stale")
    return occurrences


def _characters_in_frame(sb_shot, participants):
    """Who is visible: the beat's participants that the shot's own approved creative prose
    names (word-boundary, mechanical — never an LLM guess). Falls back to all participants
    rather than guessing a subset."""
    prose = " ".join(str(sb_shot.get(k) or "") for k in
                     ("openingImage", "principalPerformance", "physicalOrEmotionalChange",
                      "closingImage", "physicalPerformance", "animationTiming"))
    named = [c for c in participants if _mentions(c, prose)]
    return named or list(participants)


def _cast_for_shot(sb_shot, beats):
    """A shot's beatIds may span more than one beat (a continuous chain); union their
    participatingCharacters — never invented."""
    owning = [beats[bid] for bid in sb_shot["beatIds"] if bid in beats]
    cast = []
    for b in owning:
        for c in b["participatingCharacters"]:
            if c not in cast:
                cast.append(c)
    return cast


def place_voices_for_beat(beat_id, beat_shot_ids, voices, beat_dialogue, pd_by_shot):
    """Place exact occurrences from typed ProductionDetail assignments, never prose/text."""
    if any(not isinstance(item, dict) or not item.get("dialogueOccurrenceId")
           for item in beat_dialogue):
        raise HandoverRefused(
            f"REFUSED — beat {beat_id} has no typed dialogue occurrence contract")
    expected_ids = [item["dialogueOccurrenceId"] for item in beat_dialogue]
    voice_by_id = {voice.get("dialogueOccurrenceId"): voice for voice in voices
                   if voice.get("dialogueOccurrenceId") in expected_ids}
    if list(voice_by_id) != expected_ids:
        raise HandoverRefused(
            f"REFUSED — beat {beat_id}'s VoicePerformances do not preserve occurrence order")
    placement = {sid: [] for sid in beat_shot_ids}
    for occurrence_id in expected_ids:
        targets = [sid for sid in beat_shot_ids if occurrence_id in
                   (pd_by_shot.get(sid, {}).get("dialogueOccurrenceIds") or [])]
        if len(targets) != 1:
            raise HandoverRefused(
                f"REFUSED — {occurrence_id} must be assigned to exactly one shot in "
                f"{beat_id}; found {targets}")
        placement[targets[0]].append(voice_by_id[occurrence_id])
    return placement


def _dialogue_lines(vps, timing_windows, duration):
    """Map immutable voice occurrences to their signed numeric windows."""
    if not isinstance(timing_windows, list):
        raise HandoverRefused("REFUSED - dialogueTimings must be a list")
    voice_ids = [vp.get("dialogueOccurrenceId") for vp in vps]
    timing_ids = [window.get("dialogueOccurrenceId")
                  for window in timing_windows if isinstance(window, dict)]
    if len(timing_ids) != len(timing_windows) or timing_ids != voice_ids:
        raise HandoverRefused(
            "REFUSED - dialogue timing windows dropped, duplicated or reordered "
            f"occurrences: expected {voice_ids}, got {timing_ids}")
    lines = []
    for vp, window in zip(vps, timing_windows):
        delivery = (vp.get("elevenLabsV3Direction") or vp.get("physicalActionRelationship") or "").strip()
        if not delivery:
            raise HandoverRefused(
                f"REFUSED - {vp.get('dialogueOccurrenceId')} has no executable voice direction")
        text = vp["exactDialogue"].strip()
        try:
            start, end = float(window["startSec"]), float(window["endSec"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HandoverRefused(
                f"REFUSED - malformed dialogue timing for {vp.get('dialogueOccurrenceId')}") from exc
        if start < 0 or start >= end or end > duration:
            raise HandoverRefused(
                f"REFUSED - invalid dialogue timing {start}-{end}s for "
                f"{vp.get('dialogueOccurrenceId')} in a {duration}s shot")
        lines.append({"dialogueOccurrenceId": vp["dialogueOccurrenceId"],
                      "sourceEventId": vp["sourceEventId"],
                      "speaker": vp["speaker"], "exactText": text, "delivery": delivery,
                      "startSec": start, "endSec": end})
    return lines


def _voice_director_brief_lines(vps):
    """THE PRODUCTION VOICE BRIEF (2026-07-17 correction): every placed line's four approved
    pieces, kept discrete and verbatim — never collapsed into one abstracted string. Exact
    locked dialogue, the approved elevenLabsV3Direction (the executable Voice Director
    instruction), the approved expectedTiming, and the concise physicalActionRelationship.
    Distinct from cb_engine.compile_audio_brief (protected, the ElevenLabs-facing text built
    from DialogueLine.delivery alone) — this is the human-readable brief that carries every
    field separately, so expectedTiming and physicalActionRelationship are never lost even
    though the typed DialogueLine contract has no field for either."""
    return [{"dialogueOccurrenceId": vp["dialogueOccurrenceId"],
             "sourceEventId": vp["sourceEventId"],
             "speaker": vp["speaker"], "exactDialogue": vp["exactDialogue"].strip(),
             "elevenLabsV3Direction": (vp.get("elevenLabsV3Direction") or "").strip(),
             "expectedTiming": (vp.get("expectedTiming") or "").strip(),
             "physicalActionRelationship": (vp.get("physicalActionRelationship") or "").strip()}
            for vp in vps]


def _continuity_state(boundary, cast, field_name):
    """Map a complete typed boundary directly. No prose fallback or field duplication."""
    if boundary is None:
        return None
    if not isinstance(boundary, dict):
        raise HandoverRefused(f"REFUSED - {field_name} must be a typed boundary object")
    expected_boundary_keys = {"lighting", "cameraSide", "characters"}
    if set(boundary) != expected_boundary_keys:
        raise HandoverRefused(
            f"REFUSED - {field_name} fields must be exactly {sorted(expected_boundary_keys)}")
    raw_characters = boundary.get("characters")
    if not isinstance(raw_characters, list):
        raise HandoverRefused(f"REFUSED - {field_name}.characters must be a list")
    ids = [character.get("characterId") for character in raw_characters
           if isinstance(character, dict)]
    if (len(ids) != len(raw_characters) or len(ids) != len(set(ids)) or
            set(ids) != set(cast or [])):
        raise HandoverRefused(
            f"REFUSED - {field_name} cast must be exactly {list(cast or [])}; got {ids}")
    expected_character_keys = {"characterId", "screenZone", "facing", "pose",
                               "expression", "visibleMarks", "heldProps"}
    chars = []
    for character in raw_characters:
        if set(character) != expected_character_keys:
            raise HandoverRefused(
                f"REFUSED - {field_name} character fields must be exactly "
                f"{sorted(expected_character_keys)}")
        try:
            chars.append(cb_engine.CharacterState(
                character=character["characterId"],
                screenZone=character["screenZone"], facing=character["facing"],
                pose=character["pose"], expression=character["expression"],
                visibleMarks=character["visibleMarks"], heldProps=character["heldProps"]))
        except Exception as exc:
            raise HandoverRefused(
                f"REFUSED - malformed {field_name} state for {character.get('characterId')}") from exc
    try:
        return cb_engine.ContinuityState(
            lighting=boundary["lighting"], cameraSide=boundary["cameraSide"],
            characters=chars)
    except Exception as exc:
        raise HandoverRefused(f"REFUSED - malformed {field_name}") from exc


def _performance_assignment(contract, beat_ids, cast, shot_id):
    """Validate and deterministically compile Gate 5's typed performance truth."""
    if not isinstance(contract, dict):
        raise HandoverRefused(
            f"REFUSED - {shot_id} has no typed Gate-5 performanceContract")
    expected_keys = {"beatOwner", "playableIntention", "phases",
                     "physicalCauseAndEffect", "visibleEmotionalTurn",
                     "requiredLanding", "performanceFreedom"}
    if set(contract) != expected_keys:
        raise HandoverRefused(
            f"REFUSED - {shot_id}.performanceContract fields are incomplete or unknown")
    if contract.get("beatOwner") not in beat_ids:
        raise HandoverRefused(
            f"REFUSED - {shot_id}.performanceContract belongs to "
            f"{contract.get('beatOwner')}, not one of {beat_ids}")
    phases = contract.get("phases")
    if not isinstance(phases, list) or not 1 <= len(phases) <= 4:
        raise HandoverRefused(
            f"REFUSED - {shot_id}.performanceContract requires one to four phases")
    phase_order = {"anticipation": 0, "action": 1, "reaction": 2, "settle": 3}
    names = [phase.get("phase") for phase in phases if isinstance(phase, dict)]
    expected_phase_keys = {"phase", "performer", "observableAction"}
    if (len(names) != len(phases) or len(names) != len(set(names)) or
            any(name not in phase_order for name in names) or
            names != sorted(names, key=phase_order.__getitem__)):
        raise HandoverRefused(
            f"REFUSED - {shot_id}.performanceContract phases are duplicated or out of order")
    allowed = set(cast or []) | {"ENVIRONMENT"}
    for phase in phases:
        if set(phase) != expected_phase_keys or phase.get("performer") not in allowed:
            raise HandoverRefused(
                f"REFUSED - {shot_id}.performanceContract has an unknown performer or field")
    try:
        return cb_engine.compile_performance_contract(contract)
    except ValueError as exc:
        raise HandoverRefused(f"REFUSED - {shot_id}: {exc}") from exc


def distil_shot(sb_shot, pd, cast, shot_voices, prev, characters_cfg):
    """Map one approved storyboard shot into cb_engine's production contract. Executable
    performance, continuity and dialogue timing come only from typed fields; approved prose
    is retained for provenance and review, never treated as a substitute."""
    duration = normalize_duration_for_provider(pd.get("intendedDurationRange"))
    opener = bool(pd.get("requiresNewKeyframe"))
    performance_contract = sb_shot.get("performanceContract")
    performance_assignment = _performance_assignment(
        performance_contract, sb_shot.get("beatIds") or [], cast, sb_shot["shotId"])
    continuity_in = _continuity_state(
        pd.get("continuityInState"), cast, f"{sb_shot['shotId']}.continuityInState")
    continuity_out = _continuity_state(
        pd.get("continuityOutState"), cast, f"{sb_shot['shotId']}.continuityOutState")
    if continuity_out is None:
        raise HandoverRefused(
            f"REFUSED - {sb_shot['shotId']} has no continuityOutState")

    shot = cb_engine.Shot(
        shotId=sb_shot["shotId"], beatCode=sb_shot["beatIds"][0], durationSec=duration,
        purpose=sb_shot["purpose"],
        performanceAssignment=performance_assignment,
        camera=sb_shot["cameraRelationship"],
        openingPose=sb_shot["openingImage"],
        sourceType="opener" if opener else "relay",
        sourceShotId=None if opener else prev,
        cutInMotivation=sb_shot.get("transitionReason"),
        dialogueBinding=(f"{shot_voices[0]['speaker']}'s vocal beat performs per the "
                         f"approved voice design.") if shot_voices else None,
        dialogueLines=_dialogue_lines(shot_voices, pd.get("dialogueTimings"), duration),
        visualPayoff=sb_shot["closingImage"],
        physicalStaging=None,
        prohibited=list(pd.get("essentialProviderProtections") or [])[:3],
        charactersInFrame=_characters_in_frame(sb_shot, cast),
        continuityIn=continuity_in,
        continuityOut=continuity_out)
    retained = {"continuityProseIn": pd.get("continuityIn", ""),
                "continuityProseOut": pd.get("continuityOut", ""),
                "dialogueTimingProse": pd.get("dialogueTiming"),
                "referenceRolesProse": pd.get("referenceRoles"),
                "principalPerformanceApproved": sb_shot.get("principalPerformance"),
                "physicalPerformanceApproved": sb_shot.get("physicalPerformance"),
                "animationTimingApproved": sb_shot.get("animationTiming"),
                "performanceContractApproved": performance_contract,
                "transitionType": sb_shot.get("transitionType"),
                "voiceDirectorBrief": _voice_director_brief_lines(shot_voices)}
    return shot, retained


def _compile_one(shot, retained, scene, characters_cfg):
    """2026-07-17 CONSOLIDATION (Julian's correction): the two prior handover-mapping fixes
    were built as a second compiler inside this module (a duplicate _keyframe_brief and a
    _compile_motion_brief post-processor) — real, correct output, but duplicate compiler
    responsibility, since cb_engine.py already owns keyframe/motion-brief compilation. Both
    root causes (the universal anticipation/payoff framing, the unconditional 'screen sides'
    line) were the actual hardcoded source defects, now fixed AT SOURCE in
    cb_engine.compile_keyframe_prompt/compile_shot_contract — see those functions' own
    2026-07-17 correction notes. This function goes back to calling them directly; there is
    exactly ONE keyframe compiler and ONE motion compiler in this codebase again."""
    prompt, wc, slots = cb_engine.compile_shot_contract(shot, scene, characters_cfg)
    rec = shot.model_dump()
    rec.update(retained)
    rec["seedancePrompt"], rec["promptWords"], rec["referenceSlots"] = prompt, wc, slots
    rec["audioBrief"] = cb_engine.compile_audio_brief(shot)
    if shot.sourceType == "opener":
        kf, kwc, kslots = cb_engine.compile_keyframe_prompt(shot, scene, characters_cfg)
        rec["keyframePrompt"], rec["keyframePromptWords"] = kf, kwc
        rec["keyframeReferenceSlots"] = kslots
    return rec


def _assert_no_internal_leak(shots_out):
    """'Hard constraints:' is checked EXCEPT inside a shot's own internalConstraints field —
    2026-07-17 correction: that field's real, canonical shape (matching
    cb_engine.compile_scene_package's own output, cb_render.py's REVIEW_CRITERIA doctrine)
    literally IS cb_engine.hard_constraints()'s own text, starting with that exact prefix —
    the LEGITIMATE Option-D internal-contract line, never a creative-room-reasoning leak.
    Every other field, and every other banned term (including 'Hard constraints:' anywhere
    OUTSIDE internalConstraints), is checked exactly as before — this narrows nothing else."""
    scrubbed = [{k: v for k, v in s.items() if k != "internalConstraints"} for s in shots_out]
    dump = json.dumps(scrubbed, ensure_ascii=False)
    for banned in ("showrunnerJudgement", "dramaticConstruction", "audienceExperience",
                    "rejectionChecks", "cinematographerChallenge", "Hard constraints:"):
        if banned in dump:
            raise HandoverRefused(f"REFUSED — creative-room internal content ('{banned}') "
                                  f"leaked into the promoted package.")


def promote(storyboard_path, pkg_path, dry_run=True, log=print):
    """The whole-scene handover. Refuses (no writes, current package untouched) unless the
    storyboard's top-level approvalState is human-approved — the SOLE Gate A authority
    (2026-07-17: never a nested field, this checked and swept clean)."""
    sb = json.load(open(storyboard_path))
    if sb.get("approvalState") != APPROVED_STATE:
        raise HandoverRefused(
            f"REFUSED — storyboard {pathlib.Path(storyboard_path).name} is "
            f"'{sb.get('approvalState')}', not '{APPROVED_STATE}'. Only a human-approved "
            f"Authoritative Storyboard Package can be promoted; the current production "
            f"package is untouched.")
    detail_ids = {detail.get("shotId") for detail in (sb.get("productionDetail") or [])}
    missing_details = [shot.get("shotId") for shot in (sb.get("shots") or [])
                       if shot.get("shotId") not in detail_ids]
    if missing_details:
        raise HandoverRefused(
            f"REFUSED — {missing_details[0]} has no Production Detail; the "
            "schema-checkpoint pass must run before handover.")
    occurrences = _validate_storyboard_dialogue_contract(sb)

    pkg_path = pathlib.Path(pkg_path)
    old = json.load(open(pkg_path)) if pkg_path.exists() else {}
    try:
        characters_cfg = json.load(open(CHARS))
    except Exception:
        characters_cfg = {}
    scene = {"sceneName": sb.get("scene", {}).get("location") or old.get("sceneName", "")}
    beats = {b["beatId"]: b for b in sb["beats"]}
    pd_by_shot = {p["shotId"]: p for p in sb.get("productionDetail", [])}

    shots_by_beat = {}
    for s in sb["shots"]:
        for bid in s["beatIds"]:
            shots_by_beat.setdefault(bid, []).append(s["shotId"])
    placement = {}
    for bid, sids in shots_by_beat.items():
        placement.update(place_voices_for_beat(
            bid, sorted(sids), sb.get("voicePerformances", []),
            beats[bid]["dialogueOccurrences"], pd_by_shot))

    shots_sorted = sorted(sb["shots"], key=lambda s: s["shotId"])
    shots_out, total, prev, line_count = [], 0.0, None, 0
    for sb_shot in shots_sorted:
        pd = pd_by_shot.get(sb_shot["shotId"])
        if pd is None:
            raise HandoverRefused(f"REFUSED — {sb_shot['shotId']} has no Production Detail; "
                                  f"the schema-checkpoint pass must run before handover.")
        cast = _cast_for_shot(sb_shot, beats)
        shot, retained = distil_shot(sb_shot, pd, cast, placement.get(sb_shot["shotId"], []),
                                       prev, characters_cfg)
        rec = _compile_one(shot, retained, scene, characters_cfg)
        line_count += len(shot.dialogueLines)
        shots_out.append(rec)
        total += shot.durationSec
        prev = shot.shotId

    expected = len(occurrences)
    if line_count != expected:
        raise HandoverRefused(f"REFUSED — verbatim dialogue count broke in handover: storyboard "
                              f"has {expected} locked line(s), promoted package carries {line_count}.")
    expected_ids = [item["dialogueOccurrenceId"] for item in occurrences]
    promoted_ids = [line.get("dialogueOccurrenceId") for shot in shots_out
                    for line in (shot.get("dialogueLines") or [])]
    if promoted_ids != expected_ids:
        raise HandoverRefused(
            "REFUSED — dialogue occurrence order broke in handover: expected "
            f"{expected_ids}, got {promoted_ids}")
    _assert_no_internal_leak(shots_out)

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
           "dialogueContract": sb.get("dialogueContract"),
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


def promote_shot(storyboard_path, shot_id, pkg_path, dry_run=True, log=print):
    """THE SINGLE-SHOT ZERO-SPEND HANDOVER (2026-07-17). Consumes ONLY: the approved
    Creative Shot Card for shot_id, its Production Detail, its owning beat's approved cast
    and locked dialogue (never the whole scene), canon/asset references, and the approved
    VoicePerformances matching that dialogue. Reuses distil_shot/_compile_one exactly as
    promote() does — the same distillation contract, scoped to one shot. Sibling shots in
    the same beat are consulted ONLY to resolve which shot a given line belongs to
    (place_voices_for_beat's own mechanism, needed so a beat's OTHER shot's line is never
    mis-assigned here) — their own creative content is never read or exposed."""
    sb = json.load(open(storyboard_path))
    if sb.get("approvalState") != APPROVED_STATE:
        raise HandoverRefused(
            f"REFUSED — storyboard {pathlib.Path(storyboard_path).name} is "
            f"'{sb.get('approvalState')}', not '{APPROVED_STATE}'.")
    sb_shot = next((s for s in sb["shots"] if s["shotId"] == shot_id), None)
    if sb_shot is None:
        raise HandoverRefused(f"REFUSED — {shot_id} not found in the approved storyboard.")
    pd = next((p for p in sb.get("productionDetail", []) if p["shotId"] == shot_id), None)
    if pd is None:
        raise HandoverRefused(f"REFUSED — {shot_id} has no Production Detail; the "
                              f"schema-checkpoint pass must run before handover.")
    _validate_storyboard_dialogue_contract(sb)

    pkg_path = pathlib.Path(pkg_path)
    old = json.load(open(pkg_path)) if pkg_path.exists() else {}
    try:
        characters_cfg = json.load(open(CHARS))
    except Exception:
        characters_cfg = {}
    scene = {"sceneName": sb.get("scene", {}).get("location") or old.get("sceneName", "")}
    beats = {b["beatId"]: b for b in sb["beats"] if b["beatId"] in sb_shot["beatIds"]}
    pd_by_shot = {p["shotId"]: p for p in sb.get("productionDetail", [])}

    placement = {}
    for bid in sb_shot["beatIds"]:
        sids = sorted(s["shotId"] for s in sb["shots"] if bid in s["beatIds"])
        bmap = place_voices_for_beat(
            bid, sids, sb.get("voicePerformances", []),
            beats[bid]["dialogueOccurrences"], pd_by_shot)
        # Partition-completeness check, across ALL of this beat's own shots (siblings'
        # placement only, never their creative content) — verifies no line was lost or
        # duplicated by place_voices_for_beat, BEFORE narrowing to just this one shot's
        # own share below. A per-shot count alone can't catch this: a beat legitimately
        # splits its lines unevenly across siblings (e.g. real beat 1.B1: 1 line on
        # S1.SH1, 1 on S1.SH2), so "this shot's count == the whole beat's count" is the
        # wrong invariant and broke on the very first real multi-shot beat tested
        # (2026-07-17).
        placed = [vp for lst in bmap.values() for vp in lst]
        if (len(placed) != len(beats[bid]["dialogueOccurrences"]) or
                len(set(vp["dialogueOccurrenceId"] for vp in placed)) != len(placed)):
            raise HandoverRefused(
                f"REFUSED — verbatim dialogue partition broke in single-shot handover: beat "
                f"{bid} has {len(beats[bid]['dialogueOccurrences'])} locked line(s), placement "
                f"across its own shots carries {len(placed)}.")
        placement.update(bmap)
    cast = _cast_for_shot(sb_shot, beats)
    shot, retained = distil_shot(sb_shot, pd, cast, placement.get(shot_id, []),
                                   None, characters_cfg)
    rec = _compile_one(shot, retained, scene, characters_cfg)
    _assert_no_internal_leak([rec])

    new_rev = int(old.get("revision") or 0) + 1
    pkg = {"episode": sb.get("episodeId", "Ep1"), "sceneNumber": str(sb.get("sceneNumber", "")),
           "sceneName": scene["sceneName"], "scope": f"single-shot handover: {shot_id}",
           "doctrine": "CREATIVE ROOM vNEXT single-shot handover — the approved storyboard "
                        "is the sole creative source (cb_handover.promote_shot)",
           "revision": new_rev,
           "revisionNote": f"Promoted {shot_id} from human-approved storyboard "
                            f"{pathlib.Path(storyboard_path).name}; every prior disclosure, "
                            f"sealed envelope and spend token for this shot is stale.",
           "sourceStoryboard": {"path": str(storyboard_path), "md5": _md5(storyboard_path),
                                 "approvalState": sb["approvalState"],
                                 "humanNote": sb.get("humanNote", "")},
           "handover": {"distilled": ["opening state", "principal performance",
                                        "principal camera intention", "voice/audio relationship",
                                        "continuity in/out (prose verbatim + declared typed gap)",
                                        "<=3 essential protections"],
                         "integrationGaps": list(INTEGRATION_GAPS)},
           "dialogueContract": sb.get("dialogueContract"),
           "shots": [rec], "totalSec": shot.durationSec,
           "voidedTokens": list(old.get("voidedTokens") or [])}
    if dry_run:
        log(f"SINGLE-SHOT HANDOVER DRY RUN — {shot_id}, revision {new_rev}, "
            f"{shot.durationSec}s; nothing written, no provider call, no media, no token.")
        return pkg
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)
    log(f"SINGLE-SHOT HANDOVER — wrote {pkg_path.name} revision {new_rev}: {shot_id}, "
        f"{shot.durationSec}s.")
    return pkg


def _scoped_shot(storyboard, shot_id, characters_cfg, prev):
    """Distils ONE approved shot into (cb_engine.Shot, retained) — the exact same
    distil_shot/place_voices_for_beat mechanism promote_shot already uses, factored out so
    promote_to_canonical can call it per shot_id without a second compiler or a second
    dialogue-placement rule."""
    sb_shot = next((s for s in storyboard["shots"] if s["shotId"] == shot_id), None)
    if sb_shot is None:
        raise HandoverRefused(f"REFUSED — {shot_id} not found in the approved storyboard.")
    pd = next((p for p in storyboard.get("productionDetail", []) if p["shotId"] == shot_id), None)
    if pd is None:
        raise HandoverRefused(f"REFUSED — {shot_id} has no Production Detail.")
    beats_all = {b["beatId"]: b for b in storyboard["beats"]}
    beats = {bid: beats_all[bid] for bid in sb_shot["beatIds"] if bid in beats_all}
    pd_by_shot = {p["shotId"]: p for p in storyboard.get("productionDetail", [])}
    placement = {}
    for bid in sb_shot["beatIds"]:
        sids = sorted(s["shotId"] for s in storyboard["shots"] if bid in s["beatIds"])
        bmap = place_voices_for_beat(bid, sids, storyboard.get("voicePerformances", []),
                                       beats[bid]["dialogueOccurrences"], pd_by_shot)
        placed = [vp for lst in bmap.values() for vp in lst]
        if (len(placed) != len(beats[bid]["dialogueOccurrences"]) or
                len(set(vp["dialogueOccurrenceId"] for vp in placed)) != len(placed)):
            raise HandoverRefused(
                f"REFUSED — verbatim dialogue partition broke promoting {shot_id}: beat {bid} "
                f"has {len(beats[bid]['dialogueOccurrences'])} locked line(s), placement across its "
                f"own shots carries {len(placed)}.")
        placement.update(bmap)
    cast = _cast_for_shot(sb_shot, beats)
    # 2026-07-17 correction: the CREATIVE CARD's own hash, alone — not combined with
    # ProductionDetail. These are two separate artifacts with two separate invariants: the
    # Creative Card must stay byte-identical across a Gate-5/6 production-detail-only
    # regeneration (proven separately, cb_creative._shots_hash); ProductionDetail is
    # LEGITIMATELY allowed to change when regenerated (e.g. gaining typed boundaries or
    # dialogue windows). A combined hash would falsely report drift the moment
    # ProductionDetail changed for any honest, sanctioned reason.
    card_hash = hashlib.sha256(json.dumps(
        sb_shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    shot, retained = distil_shot(sb_shot, pd, cast, placement.get(shot_id, []), prev, characters_cfg)
    return shot, retained, card_hash


def promote_to_canonical(storyboard_path, scene_num, shot_ids, episode="Ep1", dry_run=True, log=print):
    """THE SOURCE-LEVEL HANDOVER (2026-07-17, Julian's consolidation-checkpoint directive):
    approved Creative Room storyboard -> the ALREADY-EXISTING canonical production package
    format and location cb_render.py consumes (cb_engine.canonical_package_path, which
    cb_render._pkg_path itself delegates to — item 2) -> the existing cb_render fire route.
    No new package schema, filename convention, renderer entry point or provider caller —
    every top-level/shot-level field below matches cb_engine.compile_scene_package's own
    real, live output, name for name, so cb_render.py's existing
    _require_valid/_shot/_ledger/_slot_paths/keyframe_shot all resolve an untouched,
    canonical package exactly as they always have.

    Promotes ONLY the named shot_ids — never a whole-scene sweep. A shot carrying an
    unresolved validation failure (S1.SH6's own Law 6 defect in its own approved
    principalPerformance text, PIPELINE_CUTOVER_LEDGER.md §7 item 2) is simply never named
    in shot_ids here; nothing bypasses it — it stays unpromoted, unresolved, on record.

    TRANSACTIONAL (2026-07-17, Julian's correction, item 1): the ENTIRE candidate package is
    built and its real, unmodified cb_engine.validate_scene_design report computed FULLY IN
    MEMORY before any file at pkg_path is ever touched. Only report["passed"] then decides
    what happens next, in ONE branch, with no path through the code that can write an
    invalid candidate to the live path:
      - VALIDATION FAILS: the live path is left completely untouched (a previously valid
        package there stays exactly as it was — no archive-of-the-superseded-package step
        runs, because nothing is being superseded); no spend-token binding hash changes; no
        authorisation is issued. A real (dry_run=False) attempt still preserves the
        REJECTED candidate itself as evidence, at a distinctly-named path
        (..._REJECTED_<shotIds>_rev<N>_attempt<M>_validation_failed_<date>.json, never
        colliding with a same-day prior rejected attempt) — never live, never silently
        discarded either. A dry run writes nothing at all, including no rejected-evidence
        file, matching this module's own "dry_run=True writes NOTHING" contract everywhere
        else.
      - VALIDATION PASSES: the OLD canonical package at the same path (if any) is archived
        byte-identical to cb-output/archive/ before being overwritten — never deleted. Only
        then is the new, valid package written to the live path. Overwriting pkg["shots"]
        changes cb_render._shots_hash(pkg), the SAME value every prior spend-token binding
        hash (cb_render._binding_hash) is itself derived from — so every prior authorisation
        goes stale by the mechanism cb_render.py already relies on for any other package
        revision; no new tracking system is built for this.

    dry_run=True (the default) computes and returns (new_pkg, archived_or_rejected_or_None)
    and writes NOTHING — the second element is the path the write WOULD land at (archive,
    on a passing dry run) or None (no prior package to archive; or any failing dry run,
    which never computes a rejected-evidence path either since it never writes one)."""
    sb = json.load(open(storyboard_path))
    if sb.get("approvalState") != APPROVED_STATE:
        raise HandoverRefused(
            f"REFUSED — storyboard {pathlib.Path(storyboard_path).name} is "
            f"'{sb.get('approvalState')}', not '{APPROVED_STATE}'. Gate A approval is the "
            f"sole authority; nothing is promoted to the canonical package without it.")
    current_script, source_beat_signature = _require_storyboard_lineage(sb, episode)
    _validate_storyboard_dialogue_contract(sb)

    try:
        characters_cfg = json.load(open(CHARS))
    except Exception:
        characters_cfg = {}
    scene = {"sceneName": sb.get("scene", {}).get("location", "")}

    shots_out, ledger_out, card_hashes = [], [], {}
    prev = None
    for shot_id in shot_ids:
        shot, retained, card_hash = _scoped_shot(sb, shot_id, characters_cfg, prev)
        card_hashes[shot_id] = card_hash
        rec = _compile_one(shot, retained, scene, characters_cfg)
        # THE INTERNAL CONTRACT LINE (Option D, matching compile_scene_package's own shape
        # exactly) — the authored-constraints record, kept in the package for review,
        # deliberately not concatenated into the provider brief (PIPELINE_CUTOVER_LEDGER.md
        # §7 item 1: this is the one door essentialProviderProtections/shot.prohibited
        # already has into the package; whether it should ALSO reach the shipped prompt is
        # a separate, undecided question, not addressed by this handover).
        rec["internalConstraints"] = cb_engine.hard_constraints(shot, characters_cfg)[0]
        shots_out.append(rec)
        ledger_out.append(cb_engine._ledger_entry(shot))
        prev = shot.shotId

    _assert_no_internal_leak(shots_out)

    # THE REAL, UNMODIFIED VALIDATOR (cb_engine.validate_scene_design, called exactly as
    # compile_scene_package itself calls it — no second validator built here).
    #
    # beats=[] was tried first and found WRONG, not merely lenient: _expected_lines([])
    # returns [], so validate_scene_design's own DIALOGUE_NOT_VERBATIM check — "does every
    # line WE HAVE match something in the expected set" — fails EVERY dialogue-bearing shot,
    # since nothing is ever in the (empty) expected set. Fixed by feeding the validator a
    # correctly-SCOPED beats reshape: exactly the lines this call's own shots_out actually
    # carry, reshaped into cb_engine's cuts[]/dialogue shape — a mechanical field-mapping of
    # data ALREADY VERIFIED verbatim above (_scoped_shot's own partition-completeness
    # assertion against the real locked script line), never invented content. This is
    # honestly scoped to a SINGLE-SHOT promotion: whether every line in the shot's OWN beat
    # is accounted for ACROSS THAT BEAT'S SIBLING SHOTS is a whole-scene-promotion question,
    # not this checkpoint's — S1.SH1's sibling S1.SH2 is not being promoted here, on purpose.
    #
    # MISSING_PHYSICAL_STAGING still cannot fire meaningfully — the creative-room storyboard
    # schema has no comedyMode/physicalStaging-equivalent fields at all (distil_shot always
    # sets physicalStaging=None; a genuine, permanent schema gap, not fixable by reshaping
    # data that doesn't exist — PIPELINE_CUTOVER_LEDGER.md §7). Every OTHER check —
    # UNKNOWN_CHARACTER, dialogue timing/overrun, continuity cast completeness, relay-source
    # integrity, the COMPILABILITY check (a REAL compile_shot_contract call), the
    # camera-lock/checklist/abstract-direction WARNINGs — runs exactly as it would for any
    # other package.
    fields = set(cb_engine.Shot.model_fields)
    design_shots = [cb_engine.Shot(**{k: v for k, v in rec.items() if k in fields})
                    for rec in shots_out]
    validation_beats = [{"cuts": [{
        "dialogue": f"{line['speaker']}: {line['exactText']}",
        "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
        "sourceEventId": line.get("sourceEventId"),
        "speaker": line["speaker"],
        "exactText": line["exactText"],
    } for rec in shots_out for line in rec["dialogueLines"]]}]
    na = {k: "n/a — promoted via cb_handover from creative-room-2.0, not cb_engine.design_scene"
          for k in ("audienceFeeling", "whoseScene", "emotionalChange", "theLaugh",
                     "visualSurprise", "carryForward")}
    design = cb_engine.SceneShotList(statement=cb_engine.DirectorStatement(**na), shots=design_shots)
    report = cb_engine.validate_scene_design(design, validation_beats, characters_cfg)

    # 2026-07-17 (Julian's layer-boundary directive, item 2): the canonical package path
    # comes from cb_engine.canonical_package_path — a pure path helper, not a render or
    # provider entry point — never from importing cb_render itself. This module still
    # writes the exact same, already-existing canonical package location cb_render.py's
    # own _pkg_path resolves (both now delegate to the identical cb_engine function).
    pkg_path = cb_engine.canonical_package_path(scene_num, episode)
    old_rev = 0
    old_pkg_exists = pkg_path.exists()
    old_digest = None
    if old_pkg_exists:
        if dry_run:
            old_pkg = json.load(open(pkg_path))
        else:
            old_pkg, old_digest = cb_db.read_json_document(ROOT, pkg_path)
        old_rev = int(old_pkg.get("revision") or 0)
    new_rev = old_rev + 1
    stamp = datetime.datetime.now().strftime("%Y%m%d")

    errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
    storyboard_sha256 = cb_lineage.sha256_file(storyboard_path)
    package_inputs = {
        "scriptVersionId": current_script["scriptVersionId"],
        "beatPackageDigest": source_beat_signature["digest"],
        "storyboardSha256": storyboard_sha256,
        "creativeCardHashes": card_hashes,
    }
    new_pkg = {
        "episode": episode, "sceneNumber": str(scene_num),
        "sceneName": scene["sceneName"],
        "doctrine": "creative-room-2.0 -> cb_handover.promote_to_canonical -> the existing "
                     "cb_render canonical package format (2026-07-17 source-level handover)",
        "directorStatement": na,
        "beatCodes": sorted({rec["beatCode"] for rec in shots_out}),
        "shots": shots_out,
        "totalSec": round(sum(rec["durationSec"] for rec in shots_out), 1),
        "continuityLedger": ledger_out,
        "validation": {"passed": report["passed"],
                        "errors": len(errs),
                        "warnings": len([i for i in report["issues"] if i["severity"] == "WARNING"]),
                        "issues": report["issues"],
                        "beatsScopeNote": "dialogue occurrence identity, exact payload and "
                            "order are validated against this promotion's exact shot scope; "
                            "the BIG-comedy physicalStaging requirement remains a separate "
                            "creative-room schema gap (PIPELINE_CUTOVER_LEDGER.md §7).",
                        "validatedAt": _now(), "revision": new_rev},
        "reviewCriteria": {"canon": "characters and world accurate vs references",
                            "physics": "clip QA — identity, anatomy, frozen/morph",
                            "continuity": "join check — position/state/light vs the prior shot",
                            "direction": "does the joke land — Julian's own reserved verdict, "
                                          "never a machine check"},
        "sourceScript": sb.get("sourceScript"),
        "sourceBeatPackage": sb.get("sourceBeatPackage"),
        "dialogueContract": sb.get("dialogueContract"),
        "sourceStoryboard": {"path": str(storyboard_path), "md5": _md5(storyboard_path),
                              "sha256": storyboard_sha256,
                              "approvalState": sb["approvalState"],
                              "humanNote": sb.get("humanNote", ""),
                              "creativeCardHashes": card_hashes,
                              "inputSignature": sb.get("inputSignature")},
        "inputSignature": cb_lineage.dependency_signature(
            "production-package", package_inputs),
        "revision": new_rev,
        "revisionNote": (
            f"Promoted {', '.join(shot_ids)} from human-approved storyboard "
            f"{pathlib.Path(storyboard_path).name} into the canonical package cb_render.py "
            f"already reads. Revision {old_rev}'s shots/ledger and every prior spend-token "
            f"binding hash derived from them are stale (the package's own shots-hash "
            f"changed)." if report["passed"] else
            f"REFUSED — {len(errs)} validation ERROR(s); this candidate was NEVER written "
            f"to the live package. Revision {old_rev} (if any) remains the live, valid "
            f"canonical package, completely untouched; no spend-token binding hash changed; "
            f"no authorisation issued."),
        "repairLog": [],
    }

    # DEPARTMENT HANDOVER (2026-07-18): carry the existing production ledger forward for
    # each shot whose COMPLETE compiled contract and own creative-card hash are byte-for-byte
    # unchanged.  This makes Storyboard Approval a safe Studio doorway: an SH6 correction
    # cannot erase SH1's approved keyframe, voice work or animation state.  A changed shot
    # receives its fresh ledger entry and must be reviewed again.  There is no heuristic
    # field merge and no blanket package-revision invalidation.
    carried = []
    if old_pkg_exists:
        old_shots = {s.get("shotId"): s for s in (old_pkg.get("shots") or [])}
        old_ledger = {e.get("shotId"): e for e in (old_pkg.get("continuityLedger") or [])}
        old_cards = (old_pkg.get("sourceStoryboard") or {}).get("creativeCardHashes") or {}
        for i, rec in enumerate(shots_out):
            sid = rec.get("shotId")
            if (sid in old_ledger and old_shots.get(sid) == rec and
                    old_cards.get(sid) == card_hashes.get(sid)):
                ledger_out[i] = old_ledger[sid]
                carried.append(sid)
    new_pkg["handover"] = {
        "carriedForwardUnchangedShots": carried,
        "resetChangedShots": [s["shotId"] for s in shots_out if s["shotId"] not in carried],
        "rule": "full compiled shot + own creative card hash must be unchanged"
    }

    # 2026-07-17 (Julian's transactional-promotion directive, item 1): the ENTIRE candidate
    # package is built and validated above, in memory, before this point — nothing below
    # this line has happened yet. From here on, the branch is decided ONCE by
    # report["passed"], and every path it can take either touches the live file or does
    # not; there is no way for an invalid candidate to reach pkg_path.
    if not report["passed"]:
        # REFUSED: the live path is NEVER touched — no write, no archive-of-the-valid-
        # package (there is nothing superseded, since nothing supersedes it), no
        # authorisation. The previous valid package (old_rev, if any) is left completely
        # alone on disk, exactly as it was before this call. The rejected CANDIDATE itself
        # is preserved as evidence — but only for a REAL (non-dry-run) attempt; a dry run
        # writes NOTHING at all, matching this module's own standing "dry_run=True writes
        # NOTHING" contract for every other function here.
        if dry_run:
            log(f"CANONICAL PROMOTION DRY RUN — REFUSED: {len(errs)} validation ERROR(s) "
                f"for {', '.join(shot_ids)}; the live package at {pkg_path.name} "
                f"(revision {old_rev}) would NOT be touched; nothing written.")
            return new_pkg, None
        rejected = pkg_path.parent / "archive" / (
            f"{pkg_path.stem}_REJECTED_{'_'.join(shot_ids)}_rev{new_rev}_attempt1_"
            f"validation_failed_{stamp}.json")
        attempt = 1
        while rejected.exists():                      # never silently clobber a same-day
            attempt += 1                                # prior rejected attempt's own evidence
            rejected = pkg_path.parent / "archive" / (
                f"{pkg_path.stem}_REJECTED_{'_'.join(shot_ids)}_rev{new_rev}_attempt{attempt}_"
                f"validation_failed_{stamp}.json")
        rejected.parent.mkdir(parents=True, exist_ok=True)
        cb_db.atomic_write_json(ROOT, rejected, new_pkg)
        log(f"CANONICAL PROMOTION REFUSED — {len(errs)} validation ERROR(s) for "
            f"{', '.join(shot_ids)}; the live package at {pkg_path.name} (revision "
            f"{old_rev}) is UNTOUCHED; the rejected candidate is preserved as evidence at "
            f"{rejected.relative_to(pkg_path.parent)}; no authorisation issued. First "
            f"error: [{errs[0]['code']}] {errs[0]['path']}: {errs[0]['message']}" if errs
            else f"CANONICAL PROMOTION REFUSED for {', '.join(shot_ids)}; live package "
                 f"untouched; rejected candidate at {rejected.relative_to(pkg_path.parent)}.")
        return new_pkg, rejected

    # PASSED — only now does anything touch the live path.
    archived = None
    if dry_run:
        if old_pkg_exists:
            archived = pkg_path.parent / "archive" / (
                f"{pkg_path.stem}_pre_{'_'.join(shot_ids)}_promotion_rev{old_rev}_{stamp}.json")
        log(f"CANONICAL PROMOTION DRY RUN — {', '.join(shot_ids)} -> revision {new_rev} "
            f"at {pkg_path.name}; nothing written, no archive, no provider call, no token.")
        return new_pkg, archived

    if old_pkg_exists:
        archived = pkg_path.parent / "archive" / (
            f"{pkg_path.stem}_pre_{'_'.join(shot_ids)}_promotion_rev{old_rev}_{stamp}.json")
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pkg_path, archived)
        log(f"ARCHIVED — revision {old_rev}'s canonical package -> "
            f"{archived.relative_to(pkg_path.parent)}")
    try:
        cb_db.atomic_write_json(ROOT, pkg_path, new_pkg, expected_digest=old_digest)
    except cb_db.StateConflict as exc:
        raise HandoverRefused(
            f"REFUSED — canonical package changed during promotion: {exc}") from exc
    cb_db.void_scene_authorizations(
        ROOT, episode, scene_num, f"canonical-promotion-revision-{new_rev}")
    log(f"CANONICAL PROMOTION — {', '.join(shot_ids)} -> {pkg_path.name} revision {new_rev}.")
    return new_pkg, archived


_promote_to_canonical_unlocked = promote_to_canonical


def promote_to_canonical(storyboard_path, scene_num, shot_ids, episode="Ep1", dry_run=True,
                         log=print):
    """Run a live canonical promotion under the same scene lease as render mutations."""
    if dry_run:
        return _promote_to_canonical_unlocked(
            storyboard_path, scene_num, shot_ids, episode, dry_run, log)
    try:
        with cb_db.scene_lease(ROOT, episode, scene_num, "cb_handover.promote_to_canonical"):
            return _promote_to_canonical_unlocked(
                storyboard_path, scene_num, shot_ids, episode, dry_run, log)
    except cb_db.SceneBusy as exc:
        raise HandoverRefused(f"REFUSED — {exc}") from exc


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        raise SystemExit("usage: cb_handover.py <storyboard.json> <production_package.json> "
                         "[--shot <shotId>] [--write]")
    if "--shot" in sys.argv:
        shot_id = sys.argv[sys.argv.index("--shot") + 1]
        promote_shot(sys.argv[1], shot_id, sys.argv[2], dry_run=("--write" not in sys.argv))
    else:
        promote(sys.argv[1], sys.argv[2], dry_run=("--write" not in sys.argv))
