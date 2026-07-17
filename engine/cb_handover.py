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
    2. the principal character performance (principalPerformance, verbatim — the LEAN
                                             Seedance-facing field; Gate 5's own richer
                                             physicalPerformance/animationTiming detail is
                                             retained in the package, never injected into
                                             the compiled provider brief — Option D doctrine)
    3. the principal camera intention      (cameraRelationship, verbatim)
    4. the approved voice/audio relationship (assigned VoicePerformances + locked dialogue)
    5. continuity in/out                   (ProductionDetail's own prose, verbatim, plus the
                                            typed degraded mapping — see INTEGRATION_GAPS)
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

dry_run=True (the default) computes and returns everything and writes NOTHING.
"""
import datetime
import hashlib
import json
import pathlib
import re
import shutil

import cb_engine

HERE = pathlib.Path(__file__).resolve().parent
CHARS = HERE.parent / "shows" / "crystal-bears" / "canon" / "characters.json"

APPROVED_STATE = "approved"          # what /api/storyboard-approve writes at top level

# Keys of the storyboard that are CREATIVE-ROOM INTERNAL and must never reach production:
NEVER_PROMOTED = ("showrunnerJudgement", "internalRevisions", "escalation", "vision",
                   "interpretations", "treatments", "treatmentSelection",
                   "rejectedApproachSummaries", "canonCompletionProposal")

# Genuinely essential protections: provider-facing. rejectionChecks/audienceExperience/
# transitionReason etc. are creative reasoning, not protections, and are never promoted.

INTEGRATION_GAPS = (
    "typed-continuity (2026-07-17 correction, item 3 — PARTIALLY CLOSED): the storyboard's "
    "own ProductionDetail.characterContinuity field (character id + opening/closing state, "
    "authored at Gate 5/6 in cb_creative.production_detail — never inferred here) is now "
    "used, per shot, whenever the storyboard carries it. Where it is populated, the "
    "promoted shot's continuityIn/Out.characters list is genuinely typed per named "
    "character (state duplicated across pose/expression/screenZone/facing — cb_engine."
    "CharacterState's four required sub-fields against one authored string per direction, "
    "the same 'duplicated, never invented' doctrine already applied to lighting/cameraSide "
    "below — never four independently invented details). Where it is NOT yet populated "
    "(a shot whose Production Detail predates this correction, or was never regenerated), "
    "the ORIGINAL gap still applies exactly as before: lighting and cameraSide both carry "
    "the same whole-shot prose verbatim, plus the full text again as "
    "continuityProseIn/Out for review, with an EMPTY typed characters list — the "
    "join-check's per-character visible-marks protection stays inactive for THAT shot "
    "until its own Production Detail is regenerated with typed continuity.",
    "dialogue-timing: ProductionDetail's dialogueTiming is directing prose describing WHEN "
    "a line lands within the shot, not numeric windows; promoted DialogueLines carry the "
    "whole-shot window (0..durationSec) as the documented 'approximate window inside the "
    "shot'.",
    "gate5-detail-not-forwarded (Option D, by design, not a gap needing a fix): a "
    "CreativeShotCard's own physicalPerformance/animationTiming (Gate 5's richer approved "
    "detail, ~60 words each for a real shot) are retained verbatim in the promoted record "
    "but deliberately NOT concatenated into the compiled Seedance brief's "
    "performanceAssignment — doing so reliably blows cb_engine.MAX_SHOT_PROMPT_WORDS (210) "
    "on real shots. The lean brief carries principalPerformance alone; the richer detail "
    "lives in the package, per Option D's own 'not sent to Seedance is not dropped from "
    "the production contract' doctrine.",
)

# The provider (fal/Seedance) takes ONE integer-second duration end to end — confirmed by
# direct code read, not assumed: cb_gen.generate_video_seedance's own `duration=8` default is
# cast via str(duration), and cb_render.py's own fire call passes
# duration=str(int(round(envelope["durationSec"]))). A creative-approved RANGE (e.g. "5-7s")
# is normalized to its MIDPOINT, rounded to the nearest whole second — Julian's own stated
# rule for this checkpoint (2026-07-17): "If Seedance requires a fixed duration, 6s is the
# valid production normalization" for a 5-7s range.
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)")


def normalize_duration_for_provider(rng):
    """'5-7s' -> 6.0 (midpoint, rounded); a malformed/missing range refuses rather than
    inventing a number. Clamped to cb_engine's own hard shot bounds."""
    m = _DURATION_RE.search(str(rng or ""))
    if not m:
        raise HandoverRefused(f"un-parseable intendedDurationRange: {rng!r}")
    lo, hi = float(m.group(1)), float(m.group(2))
    if not (0 < lo <= hi):
        raise HandoverRefused(f"non-credible intendedDurationRange: {rng!r}")
    mid = round((lo + hi) / 2)
    return float(min(max(mid, cb_engine.MIN_SHOT_SEC), cb_engine.MAX_SHOT_SEC))


class HandoverRefused(Exception):
    """Raised BEFORE any write when the storyboard is not human-approved (or malformed)."""


def _md5(path):
    return hashlib.md5(pathlib.Path(path).read_bytes()).hexdigest()


def _mentions(name, text):
    return re.search(rf"\b{re.escape(name)}\b", text or "", re.IGNORECASE) is not None


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
    """THE ONLY door a VoicePerformance passes through on its way to a shot (2026-07-17
    correction — a beat with multiple shots, e.g. beat 1.B1 -> S1.SH1 + S1.SH2 in the real
    package, was silently duplicating every line onto EVERY shot in the beat before this
    fix). Each line lands on exactly ONE shot, resolved in two tiers:
      1. PRIMARY — the shot whose own ProductionDetail.dialogueTiming QUOTES this specific
         line's own exact text (mechanical substring match). This is the strong signal: a
         shot's dialogueTiming prose names which line it stages.
      2. FALLBACK — bare speaker-name mention (word-boundary), used only when NO sibling
         shot's dialogueTiming quotes the line's own text; falls back further to the beat's
         LAST shot if no shot names the speaker either.
    2026-07-17, second correction, found live: tier-2-only matching broke on the real
    S1.SH1/S1.SH2 beat — BOTH shots' dialogueTiming mention 'FUZZBY' by bare name (S1.SH1's
    covers only the chant, S1.SH2's covers only 'Nailed it.'), so speaker-name matching alone
    routed both lines to S1.SH1 (the first-sorted shot). Verified against the real dry-run
    output: 'Nailed it.' now correctly resolves to S1.SH2, not S1.SH1."""
    beat_vps = [vp for vp in voices
               if any(vp["exactDialogue"].strip() in d for d in beat_dialogue)]
    placement = {sid: [] for sid in beat_shot_ids}
    for vp in beat_vps:
        line = vp["exactDialogue"].strip()
        target = next((sid for sid in beat_shot_ids
                       if line and line in (pd_by_shot.get(sid, {}).get("dialogueTiming") or "")),
                      None)
        if target is None:
            target = next((sid for sid in beat_shot_ids
                           if _mentions(vp["speaker"], pd_by_shot.get(sid, {}).get("dialogueTiming"))),
                          beat_shot_ids[-1])
        placement[target].append(vp)
    return placement


def _dialogue_lines(vps, duration):
    """delivery carries the approved elevenLabsV3Direction VERBATIM (2026-07-17 correction,
    Julian's voice-mapping directive) — the executable Voice Director instruction, never an
    abstract summary. Previously fell back through physicalActionRelationship then
    dramaticIntention (an abstract dramatic READ, not a performable instruction) whenever the
    exact dialogue text happened to appear inside the candidate delivery string — that
    fallback chain is exactly what silently replaced the real V3 direction with an
    abstraction. Falls back to physicalActionRelationship ONLY when a VP genuinely has no V3
    direction authored yet (DialogueLine.delivery is a required, non-blank field) — never
    falls back to dramaticIntention."""
    lines = []
    for vp in vps:
        delivery = (vp.get("elevenLabsV3Direction") or vp.get("physicalActionRelationship") or "").strip()
        text = vp["exactDialogue"].strip()
        lines.append({"speaker": vp["speaker"], "exactText": text, "delivery": delivery,
                      "startSec": 0.0, "endSec": float(duration)})
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
    return [{"speaker": vp["speaker"], "exactDialogue": vp["exactDialogue"].strip(),
             "elevenLabsV3Direction": (vp.get("elevenLabsV3Direction") or "").strip(),
             "expectedTiming": (vp.get("expectedTiming") or "").strip(),
             "physicalActionRelationship": (vp.get("physicalActionRelationship") or "").strip()}
            for vp in vps]


def _continuity_state(prose, char_continuity, cast, which):
    """2026-07-17 correction (item 3): uses the storyboard's own typed per-character
    continuity — cb_creative.ProductionDetail.characterContinuity, AUTHORED at Gate 5/6,
    never inferred here — whenever the shot's own Production Detail carries it. A
    mechanical field-mapping only: characterId -> character, openingState/closingState ->
    the SAME single string duplicated across pose/expression/screenZone/facing (cb_engine.
    CharacterState requires all four as separate non-blank fields; the storyboard's typed
    contract deliberately authors ONE descriptive state per direction, not four — so this
    duplicates verbatim rather than inventing four distinct sub-fields, the identical
    'duplicated, never invented' doctrine already applied to lighting/cameraSide below).
    Filtered to this shot's own cast, mechanically — never trusts a name the storyboard's
    own beat data doesn't list as participating (defense-in-depth, not authoring).
    Falls back to the pre-existing whole-shot-prose-only behaviour (characters=[]) for any
    shot whose Production Detail has not yet been regenerated with typed continuity — the
    declared INTEGRATION_GAPS state, honestly preserved for every shot this correction
    does not touch.

    2026-07-17 correction (system-freeze checkpoint, THE SIMPLIFICATION): replaces the old
    NO_INHERITED_STATE sentinel-string recognition with typed absence. cb_creative.
    production_detail now stamps an empty continuityIn ("") for the scene's true first
    shot rather than a sentinel phrase (the schema's own pre-existing 'nothing here' value
    — see that function's own correction #3). This is the ONE place that empty string
    becomes cb_engine's typed None, scoped to which=='opening' only: continuityOut is
    never legitimately empty for 'no inherited state' reasons (every shot ends in a real
    state) and keeps its exact pre-existing behaviour, unchanged."""
    if which == "opening" and not (prose or "").strip():
        return None
    typed = [c for c in (char_continuity or []) if c.get("characterId") in (cast or [])]
    if not typed:
        return cb_engine.ContinuityState(lighting=prose, cameraSide=prose, characters=[])
    chars = []
    for c in typed:
        state = (c["openingState"] if which == "opening" else c["closingState"])
        chars.append(cb_engine.CharacterState(
            character=c["characterId"], screenZone=state, facing=state,
            pose=state, expression=state, visibleMarks=[], heldProps=[]))
    return cb_engine.ContinuityState(lighting=prose, cameraSide=prose, characters=chars)


def distil_shot(sb_shot, pd, cast, shot_voices, prev, characters_cfg):
    """ONE storyboard Creative Shot Card + its Production Detail + its ALREADY-PLACED
    voice performances (via place_voices_for_beat) -> ONE cb_engine.Shot (the protected,
    typed production contract) + the retained approved prose. Every creative field is the
    storyboard's own, verbatim — never re-authored, never invented."""
    duration = normalize_duration_for_provider(pd["intendedDurationRange"])
    opener = pd["requiresNewKeyframe"]
    char_continuity = pd.get("characterContinuity")

    shot = cb_engine.Shot(
        shotId=sb_shot["shotId"], beatCode=sb_shot["beatIds"][0], durationSec=duration,
        purpose=sb_shot["purpose"],
        performanceAssignment=sb_shot["principalPerformance"],
        camera=sb_shot["cameraRelationship"],
        openingPose=sb_shot["openingImage"],
        sourceType="opener" if opener else "relay",
        sourceShotId=None if opener else prev,
        cutInMotivation=sb_shot.get("transitionReason"),
        dialogueBinding=(f"{shot_voices[0]['speaker']}'s vocal beat performs per the "
                         f"approved voice design.") if shot_voices else None,
        dialogueLines=_dialogue_lines(shot_voices, duration),
        visualPayoff=sb_shot["closingImage"],
        physicalStaging=None,
        prohibited=list(pd.get("essentialProviderProtections") or [])[:3],
        charactersInFrame=_characters_in_frame(sb_shot, cast),
        continuityIn=_continuity_state(pd["continuityIn"], char_continuity, cast, "opening"),
        continuityOut=_continuity_state(pd["continuityOut"], char_continuity, cast, "closing"))
    retained = {"continuityProseIn": pd["continuityIn"], "continuityProseOut": pd["continuityOut"],
                "dialogueTimingProse": pd.get("dialogueTiming"),
                "referenceRolesProse": pd.get("referenceRoles"),
                "physicalPerformanceApproved": sb_shot.get("physicalPerformance"),
                "animationTimingApproved": sb_shot.get("animationTiming"),
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
            beats[bid]["exactDialogue"], pd_by_shot))

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

    expected = sum(len(b["exactDialogue"]) for b in sb["beats"])
    if line_count != expected:
        raise HandoverRefused(f"REFUSED — verbatim dialogue count broke in handover: storyboard "
                              f"has {expected} locked line(s), promoted package carries {line_count}.")
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
            bid, sids, sb.get("voicePerformances", []), beats[bid]["exactDialogue"], pd_by_shot)
        # Partition-completeness check, across ALL of this beat's own shots (siblings'
        # placement only, never their creative content) — verifies no line was lost or
        # duplicated by place_voices_for_beat, BEFORE narrowing to just this one shot's
        # own share below. A per-shot count alone can't catch this: a beat legitimately
        # splits its lines unevenly across siblings (e.g. real beat 1.B1: 1 line on
        # S1.SH1, 1 on S1.SH2), so "this shot's count == the whole beat's count" is the
        # wrong invariant and broke on the very first real multi-shot beat tested
        # (2026-07-17).
        placed = [vp for lst in bmap.values() for vp in lst]
        if len(placed) != len(beats[bid]["exactDialogue"]) or len(set(id(vp) for vp in placed)) != len(placed):
            raise HandoverRefused(
                f"REFUSED — verbatim dialogue partition broke in single-shot handover: beat "
                f"{bid} has {len(beats[bid]['exactDialogue'])} locked line(s), placement "
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
                                       beats[bid]["exactDialogue"], pd_by_shot)
        placed = [vp for lst in bmap.values() for vp in lst]
        if len(placed) != len(beats[bid]["exactDialogue"]) or len(set(id(vp) for vp in placed)) != len(placed):
            raise HandoverRefused(
                f"REFUSED — verbatim dialogue partition broke promoting {shot_id}: beat {bid} "
                f"has {len(beats[bid]['exactDialogue'])} locked line(s), placement across its "
                f"own shots carries {len(placed)}.")
        placement.update(bmap)
    cast = _cast_for_shot(sb_shot, beats)
    # 2026-07-17 correction: the CREATIVE CARD's own hash, alone — not combined with
    # ProductionDetail. These are two separate artifacts with two separate invariants: the
    # Creative Card must stay byte-identical across a Gate-5/6 production-detail-only
    # regeneration (proven separately, cb_creative._shots_hash); ProductionDetail is
    # LEGITIMATELY allowed to change when regenerated (e.g. gaining typed
    # characterContinuity). A combined hash would falsely report drift the moment
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
    promoted_lines = [f"{ln['speaker']}: {ln['exactText']}"
                       for rec in shots_out for ln in rec["dialogueLines"]]
    validation_beats = [{"cuts": [{"dialogue": d} for d in promoted_lines]}]
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
    if old_pkg_exists:
        old_pkg = json.load(open(pkg_path))
        old_rev = int(old_pkg.get("revision") or 0)
    new_rev = old_rev + 1
    stamp = datetime.datetime.now().strftime("%Y%m%d")

    errs = [i for i in report["issues"] if i["severity"] == "ERROR"]
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
                        "beatsScopeNote": "the verbatim-dialogue cross-check and the "
                            "BIG-comedy physicalStaging requirement did not run against a "
                            "real beats list (schema gap, PIPELINE_CUTOVER_LEDGER.md §7) — "
                            "verbatim dialogue for this promotion is separately guaranteed "
                            "by _scoped_shot's own partition-completeness assertion.",
                        "validatedAt": _now(), "revision": new_rev},
        "reviewCriteria": {"canon": "characters and world accurate vs references",
                            "physics": "clip QA — identity, anatomy, frozen/morph",
                            "continuity": "join check — position/state/light vs the prior shot",
                            "direction": "does the joke land — Julian's own reserved verdict, "
                                          "never a machine check"},
        "sourceBeatPackage": None,
        "sourceStoryboard": {"path": str(storyboard_path), "md5": _md5(storyboard_path),
                              "approvalState": sb["approvalState"],
                              "humanNote": sb.get("humanNote", ""),
                              "creativeCardHashes": card_hashes},
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
        json.dump(new_pkg, open(rejected, "w"), indent=1, ensure_ascii=False)
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
    json.dump(new_pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)
    log(f"CANONICAL PROMOTION — {', '.join(shot_ids)} -> {pkg_path.name} revision {new_rev}.")
    return new_pkg, archived


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
