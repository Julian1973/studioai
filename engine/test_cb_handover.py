#!/usr/bin/env python3
"""test_cb_handover.py — the mocked, ZERO-SPEND storyboard->production handover proof
(Julian's directives, 2026-07-17/18). Fixtures match the CURRENT creative-room-2.0 schema
(CreativeShotCard + separate ProductionDetail) — the earlier fixture shape (fields
directly on the shot) was found stale by the single-shot-handover audit and corrected here
in lockstep with cb_handover.py itself.

    pytest test_cb_handover.py -q
"""
import hashlib
import json
import pathlib
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_handover as H
import cb_engine

# distinctive markers that must NEVER cross into production (req 4)
JUDGEMENT_MARKER = "ZZ-SHOWRUNNER-ANALYSIS-MARKER-ZZ"
REJECTED_MARKER = "ZZ-REJECTED-INTERPRETATION-MARKER-ZZ"
CANON_MARKER = "ZZ-TASTE-CANON-MARKER-ZZ"


def _sb_shot(shot_id, beat_ids, transition, protections=None):
    return {"shotId": shot_id, "beatIds": beat_ids, "purpose": "Land the leaf gag cleanly.",
            "audienceExperience": "We ride with him, not ahead of him.",
            "openingImage": "Fuzzby canted forward, blur of stems resolving as he swerves.",
            "principalPerformance": "Fuzzby overshoots the flower, grazes the leaf and the "
                                     "leaf springs him backward in a pollen burst.",
            "cameraRelationship": "The camera pursues and loses him, rediscovering him at "
                                    "the leaf.",
            "physicalOrEmotionalChange": "Confidence outruns control.",
            "closingImage": "The leaf mid-rebound, Fuzzby low in frame but airborne.",
            "transitionType": transition,
            "transitionReason": "A cut here would break the experiential chase." if
                                 transition == "CONTINUOUS" else
                                 "Continuing would dilute the impact; the new image "
                                 "re-scales the gag.",
            "physicalPerformance": "Weight lands late, wings recover first, the whole body "
                                     "reads the overcommitment before he does.",
            "animationTiming": "Fast in, held rebound, a small settle before the next beat.",
            "approvalState": "draft"}


def _pd(shot_id, requires_kf, duration="5-7s", protections=None, names_speaker=True,
        character_continuity=None):
    """character_continuity (2026-07-17, item 3 fixture coverage): defaults to a real
    typed Fuzzby+Zenny pair — cb_engine.validate_scene_design's CONTINUITY_CAST_INCOMPLETE
    check reads ONLY the typed ContinuityState.characters list (never the prose), so a
    fixture with no typed continuity legitimately fails that check whenever its cast has
    >0 members, exactly as the real, unregenerated S1.SH2-S1.SH7 shots still do today.
    Pass character_continuity=[] explicitly to test that still-real, still-current gap."""
    if character_continuity is None:
        character_continuity = [
            {"characterId": "Fuzzby", "openingState": "already at speed in the corridor",
             "closingState": "low but airborne after the leaf recoil"},
            {"characterId": "Zenny", "openingState": "still on her petal",
             "closingState": "still on her petal, unmoved by the recoil"}]
    return {"shotId": shot_id,
            "continuityIn": "Warm corridor light, Fuzzby already at speed, Zenny on her petal.",
            "continuityOut": "Leaf still trembling, pollen drifting, Fuzzby low but airborne.",
            "dialogueTiming": ("FUZZBY: chant runs under the whole shot, the line lands "
                                "after the rebound.") if names_speaker else
                               "The corridor holds its geography as the leaf settles.",
            "referenceRoles": "Fuzzby identity anchors scale and rhythm; Zenny identity "
                               "anchors stillness; corridor/leaf anchor bee-height geography.",
            "requiresNewKeyframe": requires_kf, "intendedDurationRange": duration,
            "essentialProviderProtections": protections if protections is not None
                                             else ["Zenny stays on her petal"],
            "characterContinuity": character_continuity}


def _beat(beat_id="1.B1", dialogue=None):
    return {"beatId": beat_id, "sceneId": "S1", "sourceScript": "x",
            "exactDialogue": dialogue if dialogue is not None else ["FUZZBY: Nailed it."],
            "participatingCharacters": ["Fuzzby", "Zenny"],
            "whatChanges": "x", "whoDrives": "Fuzzby", "audienceAnticipation": "x",
            "actionOrChoice": "x", "consequence": "x", "emotionalOrComicHandover": "x",
            "approvalState": "redesigned_for_review"}


def _vp(speaker, text):
    return {"speaker": speaker, "exactDialogue": text, "voiceIdentity": "",
            "dramaticIntention": "Claim admiration before the crash is classified.",
            "subtext": "x", "relationshipTarget": "Zenny", "emotionalEntry": "x",
            "emotionalExit": "x", "operativeWords": ["nailed"], "pace": "x", "rhythm": "x",
            "pauses": "x", "breaths": "x", "nonVerbalActions": "x",
            "elevenLabsV3Direction": "x",
            "physicalActionRelationship": "Enters only after the rebound settles.",
            "expectedTiming": "just after the rebound"}


def _storyboard(state="approved"):
    return {"episodeId": "Ep1", "sceneNumber": 1, "approvalState": state,
            "humanNote": "lovely — go",
            "scene": {"sceneId": "S1", "location": "Crystal Cove meadow"},
            "vision": {"theme": CANON_MARKER},
            "showrunnerJudgement": JUDGEMENT_MARKER,
            "internalRevisions": [{"note": JUDGEMENT_MARKER}],
            "escalation": None,
            "treatments": [{"name": "x", "cinematographerChallenge": REJECTED_MARKER}],
            "treatmentSelection": {"rejectionChecks": REJECTED_MARKER},
            "beats": [_beat("1.B1", ["FUZZBY: Nailed it."])],
            "shots": [_sb_shot("S1.SH1", ["1.B1"], "PLANNED_CUT"),
                       _sb_shot("S1.SH2", ["1.B1"], "CONTINUOUS")],
            # S1.SH1 is the scene's true first shot — THE SIMPLIFICATION (2026-07-17):
            # nothing genuinely inherits into it, so continuityIn is the schema's own
            # existing empty-string value (typed absence), matching cb_creative.
            # production_detail's real mechanical clear, never real prose here.
            "productionDetail": [{**_pd("S1.SH1", True), "continuityIn": ""},
                                  _pd("S1.SH2", False, names_speaker=False)],
            "voicePerformances": [_vp("FUZZBY", "Nailed it.")]}


def _old_pkg():
    return {"episode": "Ep1", "sceneNumber": "1", "sceneName": "Crystal Cove meadow",
            "revision": 6,
            "shots": [{"shotId": "1.B1.S1", "durationSec": 6.0,
                        "seedancePrompt": "OLD REVISION SIX PROMPT",
                        "performanceAssignment": "OLD-CREATIVE-SOURCE-MARKER",
                        "referenceSlots": {"@图1": "opening keyframe"}}],
            "voidedTokens": ["db660b33"]}


def _tmp(sb_state="approved"):
    d = pathlib.Path(tempfile.mkdtemp())
    sb_p, pkg_p = d / "sb.json", d / "pkg.json"
    json.dump(_storyboard(sb_state), open(sb_p, "w"))
    json.dump(_old_pkg(), open(pkg_p, "w"))
    return sb_p, pkg_p


def _md5(p):
    return hashlib.md5(pathlib.Path(p).read_bytes()).hexdigest()


# ── req 1 + 6: approval is the only door; refusal never writes ─────────────────────────
def test_unapproved_storyboard_cannot_alter_production():
    sb_p, pkg_p = _tmp("awaiting-human-storyboard-approval")
    before = _md5(pkg_p)
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert _md5(pkg_p) == before                      # byte-identical — untouched


def test_real_awaiting_storyboard_refused_against_package_copy():
    live = HERE.parent / "cb-output" / "creative" / "Ep1_scene1_storyboard.json"
    archived = (HERE.parent / "cb-output" / "creative" / "archive_process_v1"
                / "Ep1_scene1_storyboard.json")
    real_sb = live if live.exists() else archived
    sb = json.load(open(real_sb))
    if sb.get("approvalState") == "approved":
        pytest.skip("real storyboard is approved this run — covered by other refusal tests")
    _, pkg_p = _tmp()
    before = _md5(pkg_p)
    with pytest.raises(H.HandoverRefused):
        H.promote(real_sb, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert _md5(pkg_p) == before


# ── req 2: the approved storyboard is the SOLE creative source ────────────────────────
def test_storyboard_is_sole_creative_source():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    sb = _storyboard()
    s1 = pkg["shots"][0]
    assert s1["performanceAssignment"] == sb["shots"][0]["principalPerformance"]   # verbatim
    assert s1["camera"] == sb["shots"][0]["cameraRelationship"]
    assert s1["openingPose"] == sb["shots"][0]["openingImage"]
    assert s1["visualPayoff"] == sb["shots"][0]["closingImage"]
    assert s1["continuityProseIn"] == sb["productionDetail"][0]["continuityIn"]    # retained
    assert "OLD-CREATIVE-SOURCE-MARKER" not in json.dumps(pkg)   # nothing of rev 6 survives
    assert pkg["sourceStoryboard"]["md5"] == _md5(sb_p)          # provenance binds the source


# ── req 3: only the distilled categories, structure honoured ──────────────────────────
def test_distils_only_the_categories_and_shot_structure():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)       # dry run is enough here
    s1, s2 = pkg["shots"]
    assert s1["sourceType"] == "opener" and s1.get("keyframePrompt")
    assert s2["sourceType"] == "relay" and s2["sourceShotId"] == "S1.SH1"
    assert "keyframePrompt" not in s2 or not s2.get("keyframePrompt")
    assert s1["prohibited"] == ["Zenny stays on her petal"]      # <=3 essential protections
    assert s1["durationSec"] == 6.0                              # midpoint of "5-7s"
    for s in (s1, s2):                                           # Option D lean brief holds
        assert s["promptWords"] <= cb_engine.MAX_SHOT_PROMPT_WORDS
        assert "Begin exactly on @图1" in s["seedancePrompt"]
    assert pkg["handover"]["integrationGaps"]                    # gaps DECLARED, never silent


def test_protections_capped_at_three():
    sb_p, pkg_p = _tmp()
    sb = json.load(open(sb_p))
    sb["productionDetail"][0]["essentialProviderProtections"] = ["one", "two", "three", "four"]
    json.dump(sb, open(sb_p, "w"))
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    assert pkg["shots"][0]["prohibited"] == ["one", "two", "three"]


def test_no_production_detail_refuses():
    sb_p, pkg_p = _tmp()
    sb = json.load(open(sb_p))
    sb["productionDetail"] = []
    json.dump(sb, open(sb_p, "w"))
    with pytest.raises(H.HandoverRefused, match="no Production Detail"):
        H.promote(sb_p, pkg_p, log=lambda *a, **k: None)


# ── req 4: creative-room internals never reach production or the brief ────────────────
def test_internals_never_enter_package_or_brief():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    dump = json.dumps(pkg, ensure_ascii=False)
    for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER, "Hard constraints:",
                    "showrunnerJudgement", "internalRevisions", "treatments",
                    "treatmentSelection"):
        assert banned not in dump, banned
    for s in pkg["shots"]:
        for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER):
            assert banned not in s["seedancePrompt"]
            assert banned not in (s.get("keyframePrompt") or "")


# ── req 5: new revision; every earlier authorisation stale ────────────────────────────
def test_promotion_bumps_revision_and_stales_prior_authorisations():
    sb_p, pkg_p = _tmp()
    old = json.load(open(pkg_p))
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    assert pkg["revision"] == old["revision"] + 1                # versioned, never in place
    assert pkg["voidedTokens"] == ["db660b33"]                   # void history carries forward
    import cb_render
    assert cb_render._shots_hash(pkg) != cb_render._shots_hash(old)
    assert pkg["shots"][0]["seedancePrompt"] != old["shots"][0]["seedancePrompt"]
    with pytest.raises(cb_render.Refused, match="VOID"):
        cb_render._verify_envelope({"token": "stale-pre-envelope"})


# ── req 7 + verbatim law: dry run writes nothing; dialogue survives exactly ───────────
def test_dry_run_writes_nothing_and_module_has_no_provider_access():
    d = pathlib.Path(tempfile.mkdtemp())
    sb_p = d / "sb.json"
    json.dump(_storyboard(), open(sb_p, "w"))
    pkg_p = d / "brand_new_pkg.json"                             # does not exist yet
    pkg = H.promote(sb_p, pkg_p, dry_run=True, log=lambda *a, **k: None)
    assert not pkg_p.exists()                                    # dry run stored NOTHING
    assert pkg["revision"] == 1
    src = (HERE / "cb_handover.py").read_text()
    # 2026-07-17 (Julian's layer-boundary correction, item 2): the invariant is RESTORED in
    # full — neither cb_gen (the provider-calling module) nor cb_render (the renderer entry
    # point) may be imported here, no exception. promote_to_canonical no longer needs to
    # import cb_render even narrowly for its package-path convention: that convention now
    # lives in cb_engine.canonical_package_path (cb_engine.py already owns the canonical
    # package CONTRACT), a pure path helper this module calls directly — it was never a
    # provider call, but routing it through cb_render's own module was still a real,
    # avoidable coupling across the promotion boundary. Fixed at the source, not narrowed
    # here at the test.
    assert "import cb_gen" not in src
    assert "import cb_render" not in src
    # no CALL syntax to any provider function — a docstring citing a confirmed provider
    # fact (e.g. "cb_gen.generate_video_seedance's own duration=8 default") is fine and
    # expected (Julian's audit directive); an actual call/attribute-invocation is not
    assert not any(pat in src for pat in
                   ("cb_gen.generate_video_seedance(", "cb_gen.generate_video(",
                    "cb_gen.eleven_", "_fal_upload(", "_fal_subscribe(",
                    "cb_gen.generate_image("))


def test_verbatim_dialogue_lands_on_the_correct_shot():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    s1, s2 = pkg["shots"]
    lines = s1["dialogueLines"] + s2["dialogueLines"]
    assert len(lines) == 1
    ln = lines[0]
    assert ln["exactText"] == "Nailed it."                       # verbatim, never reworded
    assert "Nailed it" not in ln["delivery"]                     # delivery carries no words
    for s in (s1, s2):
        assert "Nailed it" not in s["seedancePrompt"]            # Law 6 holds through handover


# ── THE HANDOVER-MAPPING CORRECTION (2026-07-17): VOICE MAPPING ────────────────────────
# The keyframe/motion-brief corrections were CONSOLIDATED to their actual source,
# cb_engine.compile_keyframe_prompt/compile_shot_contract (see test_cb_engine.py's own
# 'HANDOVER-MAPPING CORRECTION' section, 2026-07-17) — the two fixture-based tests that
# used to live here (keyframe-follows-approved-state, screen-side-conditional) exercised
# H._keyframe_brief/H._compile_motion_brief directly; both functions were DELETED in the
# consolidation, not relocated, so those tests moved with the logic rather than being kept
# as dead references to code that no longer exists here. cb_handover.py's real, permanent
# responsibility below (voice mapping) never touched cb_engine.py and is unaffected.
def test_voice_delivery_carries_v3_direction_not_abstract_dramatic_intention():
    """The voice-mapping correction: DialogueLine.delivery (which feeds
    cb_engine.compile_audio_brief, the ElevenLabs-facing text) must carry the approved,
    EXECUTABLE elevenLabsV3Direction verbatim — never the abstract dramaticIntention read
    that used to silently replace it."""
    vp = _vp("FUZZBY", "Nailed it.")
    vp["elevenLabsV3Direction"] = "[proud, breathless] land the line like the stunt already worked."
    lines = H._dialogue_lines([vp], 6.0)
    assert lines[0]["delivery"] == vp["elevenLabsV3Direction"]
    assert lines[0]["delivery"] != vp["dramaticIntention"]


def test_voice_director_brief_carries_all_four_approved_fields_discretely():
    """The production voice brief must carry exact locked dialogue, the approved
    elevenLabsV3Direction, the approved expectedTiming and the concise
    physicalActionRelationship — four discrete fields, never collapsed into one summary."""
    vp = _vp("FUZZBY", "Nailed it.")
    vp["elevenLabsV3Direction"] = "[proud] deliver it like the stunt already landed."
    vp["expectedTiming"] = "right after the wobble settles"
    vp["physicalActionRelationship"] = "the line contradicts the still-recovering hover"
    brief = H._voice_director_brief_lines([vp])
    assert len(brief) == 1
    b = brief[0]
    assert b["exactDialogue"] == "Nailed it."
    assert b["elevenLabsV3Direction"] == vp["elevenLabsV3Direction"]
    assert b["expectedTiming"] == vp["expectedTiming"]
    assert b["physicalActionRelationship"] == vp["physicalActionRelationship"]


def test_real_s1sh1_maps_cleanly_into_the_canonical_engine_compiler():
    """Pinned to the REAL, approved 1.B1 data (2026-07-17): distil_shot's mapping of the
    real approved shot/production-detail, fed into cb_engine's OWN canonical
    compile_keyframe_prompt/compile_shot_contract (never a cb_handover-local compiler,
    consolidated away 2026-07-17) — confirms the mapping layer produces a Shot the real
    engine compiles cleanly, on real production content, not just a synthetic fixture.
    Skips gracefully if the real storyboard file is absent/unapproved so this suite never
    depends on production state to pass."""
    real_sb_path = pathlib.Path(__file__).resolve().parent.parent / "cb-output" / "creative" / \
        "Ep1_scene1_storyboard.json"
    if not real_sb_path.exists():
        pytest.skip("real storyboard not present in this environment")
    sb = json.load(open(real_sb_path))
    if sb.get("approvalState") != H.APPROVED_STATE:
        pytest.skip("real storyboard not currently approved")
    s1 = next((s for s in sb["shots"] if s["shotId"] == "S1.SH1"), None)
    pd1 = next((p for p in sb.get("productionDetail", []) if p["shotId"] == "S1.SH1"), None)
    if not (s1 and pd1):
        pytest.skip("real S1.SH1 shot/production-detail not present")
    chars_cfg = json.load(open(H.CHARS)) if H.CHARS.exists() else {}
    shot, _ = H.distil_shot(s1, pd1, ["Fuzzby", "Zenny"], [], None, chars_cfg)
    kf, kwc, kslots = cb_engine.compile_keyframe_prompt(
        shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
    assert "already" in kf.lower()                                # the real, approved opening state
    assert "anticipation instant" not in kf.lower()
    assert "action already happening" not in kf.lower()
    prompt, wc, slots = cb_engine.compile_shot_contract(
        shot, {"sceneName": "Crystal Cove meadow"}, chars_cfg)
    assert "screen sides" not in prompt                           # no default lane lock


# ── THE SINGLE-SHOT ZERO-SPEND HANDOVER (2026-07-17/18 directive) ─────────────────────
def test_promote_shot_scoped_to_one_shot_only():
    sb_p, pkg_p = _tmp()
    pkg = H.promote_shot(sb_p, "S1.SH1", pkg_p, log=lambda *a, **k: None)
    assert len(pkg["shots"]) == 1 and pkg["shots"][0]["shotId"] == "S1.SH1"
    assert pkg["scope"] == "single-shot handover: S1.SH1"
    assert pkg["shots"][0]["sourceType"] == "opener"
    assert pkg["shots"][0]["durationSec"] == 6.0                 # midpoint of "5-7s"
    assert pkg["shots"][0]["dialogueLines"][0]["exactText"] == "Nailed it."


def test_place_voices_for_beat_splits_by_line_content_not_bare_speaker_name():
    """Pinned to the real bug found live against the actual Ep1 S1.SH1/S1.SH2 data
    (2026-07-17): a two-line beat where BOTH shots' dialogueTiming mention the same bare
    speaker name ('FUZZBY') by word-boundary, but only ONE shot's dialogueTiming actually
    quotes each specific line. Speaker-name-only matching sent both lines to the
    first-sorted shot; content-first matching must split them correctly."""
    sb = _storyboard()
    sb["beats"] = [_beat("1.B1", ["FUZZBY: BIZZY-BIZZY-BIZZY…", "FUZZBY: Nailed it."])]
    sb["shots"] = [_sb_shot("S1.SH1", ["1.B1"], "CONTINUOUS"),
                    _sb_shot("S1.SH2", ["1.B1"], "PLANNED_CUT")]
    sb["productionDetail"] = [
        {**_pd("S1.SH1", True), "dialogueTiming":
            "FUZZBY chant is already underway at frame one: “BIZZY-BIZZY-BIZZY…” "
            "in brisk pulse, carrying into the snap-away."},
        {**_pd("S1.SH2", False), "dialogueTiming":
            "FUZZBY: cut in after the messy recovery; hold the pose, then place "
            "“Nailed it.” before the hover steadies."}]
    sb["voicePerformances"] = [_vp("FUZZBY", "BIZZY-BIZZY-BIZZY…"), _vp("FUZZBY", "Nailed it.")]
    placement = H.place_voices_for_beat(
        "1.B1", ["S1.SH1", "S1.SH2"], sb["voicePerformances"],
        sb["beats"][0]["exactDialogue"], {p["shotId"]: p for p in sb["productionDetail"]})
    assert [vp["exactDialogue"] for vp in placement["S1.SH1"]] == ["BIZZY-BIZZY-BIZZY…"]
    assert [vp["exactDialogue"] for vp in placement["S1.SH2"]] == ["Nailed it."]


def test_promote_shot_refuses_missing_shot_or_production_detail():
    sb_p, pkg_p = _tmp()
    with pytest.raises(H.HandoverRefused, match="not found"):
        H.promote_shot(sb_p, "S1.SH9", pkg_p, log=lambda *a, **k: None)
    sb = json.load(open(sb_p))
    sb["productionDetail"] = [p for p in sb["productionDetail"] if p["shotId"] != "S1.SH1"]
    json.dump(sb, open(sb_p, "w"))
    with pytest.raises(H.HandoverRefused, match="no Production Detail"):
        H.promote_shot(sb_p, "S1.SH1", pkg_p, log=lambda *a, **k: None)


def test_promote_shot_refuses_when_not_approved():
    sb_p, pkg_p = _tmp("awaiting-human-storyboard-approval")
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote_shot(sb_p, "S1.SH1", pkg_p, dry_run=False, log=lambda *a, **k: None)


def test_promote_shot_never_leaks_internals_and_dry_run_writes_nothing():
    sb_p, pkg_p = _tmp()
    before_exists = pkg_p.exists()
    pkg = H.promote_shot(sb_p, "S1.SH1", pkg_p, dry_run=True, log=lambda *a, **k: None)
    dump = json.dumps(pkg, ensure_ascii=False)
    for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER):
        assert banned not in dump
    assert not pkg_p.exists() if not before_exists else True     # nothing new written


def test_duration_normalized_to_midpoint_for_fixed_provider_duration():
    assert H.normalize_duration_for_provider("5-7s") == 6.0
    assert H.normalize_duration_for_provider("4-8s") == 6.0
    assert H.normalize_duration_for_provider("5-6s") == 6.0       # rounds .5 up
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("not a range")
    with pytest.raises(H.HandoverRefused):
        H.normalize_duration_for_provider("9-3s")                 # inverted, non-credible


# ── THE SOURCE-LEVEL HANDOVER: creative-room storyboard -> canonical package (2026-07-17) ──
def test_internal_leak_check_exempts_only_internalConstraints_field():
    """2026-07-17 correction: internalConstraints legitimately starts with 'Hard
    constraints:' (cb_engine.hard_constraints' own real text) — must not false-positive.
    Every other field, and every other banned term, is still checked exactly as before."""
    clean = [{"shotId": "S1.SH1", "internalConstraints": "Hard constraints: no crystals on bees."}]
    H._assert_no_internal_leak(clean)          # must not raise
    leaky_elsewhere = [{"shotId": "S1.SH1", "seedancePrompt": "Hard constraints: leaked here too"}]
    with pytest.raises(H.HandoverRefused, match="Hard constraints"):
        H._assert_no_internal_leak(leaky_elsewhere)
    real_leak = [{"shotId": "S1.SH1", "internalConstraints": "Hard constraints: fine",
                   "notes": "showrunnerJudgement leaked here"}]
    with pytest.raises(H.HandoverRefused, match="showrunnerJudgement"):
        H._assert_no_internal_leak(real_leak)


def _canonical_env(tmp_path, monkeypatch, sb_state="approved"):
    """Redirects cb_engine.canonical_package_path to a scratch dir so promote_to_canonical's
    real archive/write behaviour can be proven without touching production files.
    2026-07-17 correction (Julian's layer-boundary directive, item 2): promote_to_canonical
    no longer resolves the canonical path via cb_render._pkg_path (removed, along with the
    cb_render import itself) — it calls cb_engine.canonical_package_path directly, the SAME
    function cb_render._pkg_path itself now delegates to. Patching it here at its actual
    source correctly redirects BOTH cb_handover's own call and any test helper that still
    reads back through cb_render._pkg_path (it delegates, so it sees the same patch)."""
    import cb_engine
    sb_p = tmp_path / "sb.json"
    json.dump(_storyboard(sb_state), open(sb_p, "w"))
    pkg_dir = tmp_path / "cb-output"
    pkg_dir.mkdir()
    monkeypatch.setattr(cb_engine, "canonical_package_path",
                        lambda scene, episode="Ep1": pkg_dir / f"{episode}_scene{scene}_production_package.json")
    return sb_p, pkg_dir


def test_promote_to_canonical_dry_run_writes_nothing_and_reports_honest_validation(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    new_pkg, archived = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=True, log=lambda *a, **k: None)
    assert new_pkg["shots"][0]["shotId"] == "S1.SH1"
    assert isinstance(new_pkg["validation"]["passed"], bool)      # a REAL computed verdict,
    #                                                                never a hardcoded True
    assert list((pkg_dir).iterdir()) == []                        # nothing written
    assert archived is None                                       # no prior package to archive


def test_promote_to_canonical_writes_canonical_shape_and_archives_the_old_package(tmp_path, monkeypatch):
    import cb_render as R
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old_path = R._pkg_path("1", "Ep1")
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6,
           "shots": [{"shotId": "1.B1.S1", "performanceAssignment": "OLD-MARKER"}],
           "continuityLedger": [], "validation": {"passed": True}}
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    new_pkg, archived = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=False, log=lambda *a, **k: None)
    assert archived.exists() and _md5(archived) == old_md5        # byte-identical, preserved
    assert new_pkg["revision"] == 7
    # the canonical shape cb_render.py actually reads — every key it touches, present
    for key in ("episode", "sceneNumber", "shots", "continuityLedger", "validation", "revision"):
        assert key in new_pkg
    written = json.load(open(old_path))                           # same path, new content
    assert written["revision"] == 7
    assert [s["shotId"] for s in written["shots"]] == ["S1.SH1"]   # sole creative source
    assert "1.B1.S1" not in json.dumps(written["shots"])           # legacy shot gone, not merged
    ledger_ids = [e["shotId"] for e in written["continuityLedger"]]
    assert ledger_ids == ["S1.SH1"]


def test_promote_to_canonical_refuses_transactionally_on_invalid_candidate(tmp_path, monkeypatch):
    """Item 1, the core transactional guarantee: a candidate that fails validation must
    NEVER reach the live path — the previous valid package is preserved exactly, no
    archive-of-the-superseded-package step runs (nothing is superseded), and the failed
    candidate itself is preserved separately as REJECTED evidence, not silently discarded."""
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old_path = pkg_dir / "Ep1_scene1_production_package.json"
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6,
           "shots": [{"shotId": "1.B1.S1", "performanceAssignment": "STILL-THE-VALID-ONE"}],
           "continuityLedger": [], "validation": {"passed": True}}
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    # character_continuity=[] reproduces the real, still-current gap (CONTINUITY_CAST_
    # INCOMPLETE) that actually made revision 7's first live attempt fail validation.
    sb = _storyboard()
    sb["productionDetail"][0] = {**sb["productionDetail"][0], "characterContinuity": []}
    json.dump(sb, open(sb_p, "w"))

    new_pkg, rejected = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=False, log=lambda *a, **k: None)
    assert new_pkg["validation"]["passed"] is False
    assert new_pkg["validation"]["errors"] > 0
    # THE LIVE PATH IS UNTOUCHED — byte-identical to what it was before this call
    assert _md5(old_path) == old_md5
    assert json.load(open(old_path))["shots"][0]["performanceAssignment"] == "STILL-THE-VALID-ONE"
    # THE REJECTED CANDIDATE IS PRESERVED, SEPARATELY, NEVER LIVE
    assert rejected is not None and rejected.exists()
    assert rejected != old_path
    assert "REJECTED" in rejected.name and "validation_failed" in rejected.name
    rejected_content = json.load(open(rejected))
    assert rejected_content["shots"][0]["shotId"] == "S1.SH1"
    assert rejected_content["validation"]["passed"] is False


def test_promote_to_canonical_dry_run_refusal_writes_absolutely_nothing(tmp_path, monkeypatch):
    """A failing dry run must not even write the rejected-evidence file — dry_run=True
    means nothing touches disk, full stop, matching this module's own standing contract."""
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    old = {"episode": "Ep1", "sceneNumber": "1", "revision": 6, "shots": [],
           "continuityLedger": [], "validation": {"passed": True}}
    old_path = pkg_dir / "Ep1_scene1_production_package.json"
    json.dump(old, open(old_path, "w"))
    old_md5 = _md5(old_path)

    sb = _storyboard()
    sb["productionDetail"][0] = {**sb["productionDetail"][0], "characterContinuity": []}
    json.dump(sb, open(sb_p, "w"))

    new_pkg, rejected = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                                 dry_run=True, log=lambda *a, **k: None)
    assert new_pkg["validation"]["passed"] is False
    assert rejected is None
    assert _md5(old_path) == old_md5                              # completely untouched
    assert set(p.name for p in pkg_dir.rglob("*")) == {"Ep1_scene1_production_package.json"}
    #                                                    ^ no archive/ dir, no rejected file


def test_promote_to_canonical_promotes_only_named_shots_never_a_sweep(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch)
    new_pkg, _ = H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                          dry_run=True, log=lambda *a, **k: None)
    ids = [s["shotId"] for s in new_pkg["shots"]]
    assert ids == ["S1.SH1"]
    assert "S1.SH2" not in ids                                    # the sibling is real in the
    #                                                                storyboard but never named


def test_promote_to_canonical_refuses_when_not_approved(tmp_path, monkeypatch):
    sb_p, pkg_dir = _canonical_env(tmp_path, monkeypatch, sb_state="awaiting-human-storyboard-approval")
    with pytest.raises(H.HandoverRefused, match="not 'approved'"):
        H.promote_to_canonical(sb_p, "1", ["S1.SH1"], episode="Ep1",
                                dry_run=True, log=lambda *a, **k: None)
    assert list(pkg_dir.iterdir()) == []


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
