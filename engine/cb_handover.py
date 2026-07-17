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
import hashlib
import json
import pathlib
import re

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
    "typed-continuity: ProductionDetail records continuity in/out as ONE approved PROSE "
    "sentence per direction (not even split into lighting/cameraSide any more, let alone "
    "per-character state); the production contract (cb_engine.ContinuityState) requires "
    "lighting/cameraSide as separate required fields plus a typed per-character list. No "
    "mechanical decomposition of one prose sentence into those categories exists, so "
    "promoted shots carry the SAME approved prose verbatim in BOTH lighting and cameraSide "
    "(duplicated, never invented) plus the full text again as continuityProseIn/Out for "
    "review, with an EMPTY typed characters list — the join-check's per-character "
    "visible-marks protection is inactive for promoted shots until the storyboard schema "
    "gains typed continuity or Julian authorises a structuring pass.",
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


def distil_shot(sb_shot, pd, cast, shot_voices, prev, characters_cfg):
    """ONE storyboard Creative Shot Card + its Production Detail + its ALREADY-PLACED
    voice performances (via place_voices_for_beat) -> ONE cb_engine.Shot (the protected,
    typed production contract) + the retained approved prose. Every creative field is the
    storyboard's own, verbatim — never re-authored, never invented."""
    duration = normalize_duration_for_provider(pd["intendedDurationRange"])
    opener = pd["requiresNewKeyframe"]

    cont = lambda prose: cb_engine.ContinuityState(
        lighting=prose, cameraSide=prose, characters=[])   # duplicated verbatim, never
    #                                                          invented — see INTEGRATION_GAPS
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
        continuityIn=cont(pd["continuityIn"]), continuityOut=cont(pd["continuityOut"]))
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
    dump = json.dumps(shots_out, ensure_ascii=False)
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
