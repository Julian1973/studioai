#!/usr/bin/env python3
"""test_cb_handover.py — the mocked, ZERO-SPEND storyboard→production handover proof
(Julian's directive, 2026-07-17). Proves the creative room is not disconnected from
production, without touching cb_engine.py, cb_render.py or the provider boundary:

  1. only a HUMAN-APPROVED storyboard can be promoted;
  2. the approved storyboard is the SOLE creative source of the new shot package;
  3. the handover distils ONLY the six approved categories;
  4. showrunner analysis / rejected interpretations / canons / constraint walls never
     enter the provider brief;
  5. promotion creates a NEW revision and makes every earlier authorisation stale;
  6. an unapproved storyboard cannot alter the current production package;
  7. the dry run makes no provider call, generates no media, issues no token.

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


def _sb_shot(shot_id, beat_id, transition, placement="", protections=None):
    return {"shotId": shot_id, "beatId": beat_id, "transitionType": transition,
            "requiresNewKeyframe": transition == "PLANNED_CUT",
            "purpose": "Land the leaf gag cleanly.",
            "intendedDurationRange": "5-8s",
            "openingComposition": "Bee-height corridor, the broad leaf dominating foreground",
            "openingCharacterState": "Fuzzby canted forward mid-flight; Zenny still on her petal.",
            "blocking": "Fuzzby frame-left toward the leaf; Zenny frame-right on the petal.",
            "principalPerformance": ("Fuzzby overshoots the flower, grazes the leaf and the "
                                      "leaf springs him backward in a pollen burst."),
            "secondaryPerformance": "Zenny turns her head once and holds.",
            "animationAndPhysics": "The leaf bends under his weight, stores force, releases.",
            "gazeAndExpression": "Fuzzby wide-eyed, Zenny level.",
            "audiencePointOfView": "We see the mistake before he names it success.",
            "shotSize": "Wide", "cameraHeight": "Bee height", "cameraAngle": "Corridor side",
            "lensFeeling": "Playful width", "depthAndParallax": "Pollen cups stack into depth.",
            "cameraBehaviour": "The camera waits at the leaf, then follows the ricochet",
            "lightingAndAtmosphere": "Warm golden morning light with drifting pollen.",
            "dialoguePlacement": placement, "soundRelationship": "Wingbeats under the chant.",
            "closingComposition": "Fuzzby low in frame but airborne, leaf still trembling",
            "closingCharacterState": "Fuzzby steadying; Zenny unmoved.",
            "cutMotivation": "New comic point of view.",
            "continuityIn": "Approved prose: warm light, Fuzzby left, Zenny right on petal.",
            "continuityOut": "Approved prose: leaf trembling, pollen drifting, sides held.",
            "essentialProviderProtections": protections if protections is not None
                                             else ["Zenny stays on her petal"]}


def _storyboard(state="approved"):
    return {"episodeId": "Ep1", "sceneNumber": 1, "approvalState": state,
            "humanNote": "lovely — go",
            "scene": {"sceneId": "S1", "location": "Crystal Cove meadow"},
            "vision": {"theme": CANON_MARKER},
            "showrunnerJudgement": JUDGEMENT_MARKER,
            "internalRevisions": [{"note": JUDGEMENT_MARKER}],
            "escalation": None,
            "beats": [{"beatId": "1.B1", "participatingCharacters": ["Fuzzby", "Zenny"],
                        "exactDialogue": ["FUZZBY: Nailed it."],
                        "selectedDirectorialInterpretation": "Self-awarded mastery",
                        "selectionReason": "character truth first",
                        "interpretations": [
                            {"name": "Self-awarded mastery", "dramaticConstruction": "kept",
                             "characterBehaviour": "kept", "audienceExperience": "kept"},
                            {"name": "B", "dramaticConstruction": REJECTED_MARKER,
                             "characterBehaviour": REJECTED_MARKER,
                             "audienceExperience": REJECTED_MARKER},
                            {"name": "C", "dramaticConstruction": REJECTED_MARKER,
                             "characterBehaviour": REJECTED_MARKER,
                             "audienceExperience": REJECTED_MARKER}]}],
            "shots": [_sb_shot("1.B1.S1", "1.B1", "PLANNED_CUT"),
                       _sb_shot("1.B1.S2", "1.B1", "CONTINUOUS",
                                placement="Fuzzby's verdict lands after the settle.")],
            "voicePerformances": [
                {"speaker": "FUZZBY", "exactDialogue": "Nailed it.",
                 "dramaticIntention": "Claim admiration before the crash is classified.",
                 "physicalActionRelationship": "Enters only after the rebound settles.",
                 "expectedTiming": "just after the rebound"}]}


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
                / "Ep1_scene1_storyboard.json")            # process-v1, rejected (EX-005)
    real_sb = live if live.exists() else archived
    sb = json.load(open(real_sb))
    assert sb["approvalState"] != "approved"          # nothing is approved yet — by design
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
    assert s1["camera"] == sb["shots"][0]["cameraBehaviour"]
    assert sb["shots"][0]["openingComposition"] in s1["openingPose"]
    assert sb["shots"][0]["openingCharacterState"] in s1["openingPose"]
    assert s1["visualPayoff"] == sb["shots"][0]["closingComposition"]
    assert s1["continuityProseIn"] == sb["shots"][0]["continuityIn"]               # retained
    assert "OLD-CREATIVE-SOURCE-MARKER" not in json.dumps(pkg)   # nothing of rev 6 survives
    assert pkg["sourceStoryboard"]["md5"] == _md5(sb_p)          # provenance binds the source


# ── req 3: only the six categories, structure honoured ────────────────────────────────
def test_distils_only_the_six_categories_and_shot_structure():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)       # dry run is enough here
    s1, s2 = pkg["shots"]
    assert s1["sourceType"] == "opener" and s1.get("keyframePrompt")
    assert s2["sourceType"] == "relay" and s2["sourceShotId"] == "1.B1.S1"
    assert s2.get("keyframePrompt") is None or "keyframePrompt" not in s2
    assert s1["prohibited"] == ["Zenny stays on her petal"]      # ≤3 essential protections
    assert s1["durationSec"] == 5.0                              # low bound of "5-8s"
    for s in (s1, s2):                                           # Option D lean brief holds
        assert s["promptWords"] <= cb_engine.MAX_SHOT_PROMPT_WORDS
        assert "Begin exactly on @图1" in s["seedancePrompt"]
    assert pkg["handover"]["integrationGaps"]                    # the gap is DECLARED, never silent


def test_protections_capped_at_three():
    sb_p, pkg_p = _tmp()
    sb = json.load(open(sb_p))
    sb["shots"][0]["essentialProviderProtections"] = ["one", "two", "three", "four"]
    json.dump(sb, open(sb_p, "w"))
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    assert pkg["shots"][0]["prohibited"] == ["one", "two", "three"]


# ── req 4: creative-room internals never reach production or the brief ────────────────
def test_internals_never_enter_package_or_brief():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, dry_run=False, log=lambda *a, **k: None)
    dump = json.dumps(pkg, ensure_ascii=False)
    for banned in (JUDGEMENT_MARKER, REJECTED_MARKER, CANON_MARKER, "Hard constraints:",
                    "showrunnerJudgement", "internalRevisions", "selectionReason"):
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
    import cb_render                                             # test-only import: pure hashes
    assert cb_render._shots_hash(pkg) != cb_render._shots_hash(old)
    # _binding_hash embeds _shots_hash + the prompt (cb_render, PROTECTION 1) — a token bound
    # to revision 6 can never verify against the promoted shots; the fire path's existing
    # binding-mismatch refusal enforces it with zero new provider-boundary code.
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
    assert "import cb_gen" not in src and "import cb_render" not in src
    assert "_fal_" not in src and "generate_video" not in src and "eleven_" not in src


def test_verbatim_dialogue_lands_once_on_the_placement_shot():
    sb_p, pkg_p = _tmp()
    pkg = H.promote(sb_p, pkg_p, log=lambda *a, **k: None)
    s1, s2 = pkg["shots"]
    assert s1["dialogueLines"] == []                             # placement names S2
    assert len(s2["dialogueLines"]) == 1
    ln = s2["dialogueLines"][0]
    assert ln["exactText"] == "Nailed it."                       # verbatim, never reworded
    assert "Nailed it" not in ln["delivery"]                     # delivery carries no words
    assert "Nailed it" not in s2["seedancePrompt"]               # Law 6 holds through handover


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
