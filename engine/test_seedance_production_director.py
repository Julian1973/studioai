"""Zero-spend proofs for the Seedance Production Director craft contract."""
import cb_render as R
from cb_departments import AnimationDirection
from pydantic import ValidationError


def test_world_class_shooting_script_clears_the_advisory_craft_gate():
    shot = {"dialogueLines": [{"speaker": "FUZZBY", "exactText": "Nailed it."}]}
    specialist = {
        "dramaticBeat": "Confidence gives way to a private wobble.",
        "performanceArc": "Bright certainty tightens into a tiny flinch.",
        "referenceContract": [{"assetTag": "@Image1", "role": "opening_frame"}],
        "surgicalSafeguards": ["Preserve relative scale"],
    }
    prompt = (
        "Begin on the exact approved opening frame from @Image1, preserving identity, "
        "proportion and relative scale. Medium 40mm framing: the camera makes a restrained "
        "push because Fuzzby's planted paw loads the loose plank, causing his body to move "
        "off balance. His smile holds while his eyes flick down, then his shoulders tighten "
        "after the wobble. @Audio1 supplies the approved voice and timing; only Fuzzby's "
        "mouth moves while the listener stays silent. Warm practical rim light shapes "
        "tactile fur and wood texture across foreground, midground and background depth. "
        "The camera holds on the reaction and lands on a clean off-balance silhouette as "
        "the final frame and continuity handoff."
    )
    prompt = R.cb_departments._apply_animation_provider_shell(prompt, shot)
    result = R._prompt_quality_gate(shot, prompt, specialist)
    assert result["score"] >= 17
    assert result["criticalFailures"] == []
    assert result["needsRevision"] is False


def test_generic_motion_prompt_is_flagged_for_director_revision():
    result = R._prompt_quality_gate(
        {"dialogueLines": []}, "The character moves around. Make it cinematic.", {})
    assert result["score"] < 17
    assert result["needsRevision"] is True
    assert "continuityLanding" in result["criticalFailures"]


def test_animation_direction_requires_declared_creative_latitude():
    base = {
        "shotId": "1.B1.S1",
        "durationSec": 8,
        "taskMode": "reference-to-video",
        "generationGoal": "Generate Fuzzby's confident attempt and comic recovery.",
        "deliveryPlan": "One causal action chain lands on the proud pose long enough to read.",
        "creativeTranslation": {
            "interpretation": {
                "jokeOrAche": "Confidence survives visible evidence against it.",
                "mechanism": "The recovery claims more control than the body has.",
                "statusBefore": "Fuzzby performs authority.",
                "statusAfter": "The flower quietly disproves him.",
                "audienceProgression": ["anticipation", "impact", "affection"],
                "emotionalHeart": "He remains lovable because he keeps trying.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit", "completeGagArcCount": 0,
                "densityJudgement": "One compact causal arc.",
                "splitOrNonSplitRationale": "The action and reaction lose force if separated.",
                "handoffState": "Fuzzby balanced on the flower, chest out.",
            },
        },
        "dramaticBeat": "Boast becomes a private wobble.",
        "audienceBefore": "Amused anticipation.",
        "audienceAfter": "A laugh with affection.",
        "beatOwner": "Fuzzby",
        "performanceArc": "Showmanship cracks, then is instantly covered.",
        "physicalCauseAndEffect": "A clipped flower redirects his flight into the landing.",
        "cameraBehaviour": "The camera follows his confidence, briefly loses him, then finds the pose.",
        "timingAndRhythm": "Fast escalation, clean impact, unhurried reaction.",
        "landingBreath": "Let the proud recovery register before the line.",
        "directionDensity": "open",
        "precisionReasons": [],
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Carry the gag through one elastic performance.",
            "framingLensAndCamera": "Character-led wide follow.",
            "causalAction": "The missed turn creates the collision and recovery.",
            "observablePerformance": "Confidence survives every correction.",
            "compositionLightAndMaterials": "Warm meadow depth and loose pollen.",
            "landingImage": "Fuzzby holds his gymnast finish."
        }],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": ["1.B1"],
            "purpose": "Turn confidence into a physical wobble.",
            "initialOrCarriedState": "Fuzzby begins in the approved pose.",
            "cause": "Fuzzby's missed turn drives him into the flower.",
            "primaryEvent": "The missed turn creates the collision and recovery.",
            "observableEndState": "Fuzzby balances on the flower, chest out.",
            "emotionOrCameraAnalysis": "The unhurried hold lets his denial become the joke."
        }],
        "referenceContract": [],
        "geography": ["The flower lane runs frame-left to frame-right."],
        "consistencyContract": ["Keep Fuzzby's identity and flower ownership stable."],
        "audioContract": "No dialogue; retain the physical action sounds.",
        "continuityFinish": "Fuzzby balanced on the flower, chest out.",
        "surgicalSafeguards": [],
        "providerPrompt": "Begin from the approved frame and follow Fuzzby's confident attempt "
                          "as one mistake compounds into a gymnastic recovery. Let his acting "
                          "find the comic cadence, then hold the proud landing long enough to read."
    }
    direction = AnimationDirection.model_validate({
        **base,
        "performanceFreedom": "Seedance may invent micro-reactions, overlap and recovery rhythm."
    })
    assert direction.directionDensity == "open"
    assert direction.precisionReasons == []

    try:
        AnimationDirection.model_validate(base)
    except ValidationError:
        pass
    else:
        raise AssertionError("performanceFreedom must be an explicit directing choice")

    try:
        AnimationDirection.model_validate({
            **base,
            "performanceFreedom": "Seedance may discover the detailed performance.",
            "directionDensity": "precise",
            "precisionReasons": []
        })
    except ValidationError:
        pass
    else:
        raise AssertionError("precise direction must justify why creative latitude is reduced")

    try:
        AnimationDirection.model_validate({
            **base,
            "durationSec": 30,
            "performanceFreedom": "Seedance may discover the detailed performance.",
        })
    except ValidationError:
        pass
    else:
        raise AssertionError("a 30-second unit must use a complete timestamp stage plan")

    over_legacy_target = AnimationDirection.model_validate({
        **base,
        "performanceFreedom": "Seedance may discover the detailed performance.",
        "providerPrompt": " ".join(["direction"] * 1101),
    })
    assert len(over_legacy_target.providerPrompt.split()) == 1101

    long_form = {
        **base,
        "durationSec": 30,
        "pacingMode": "timestamp",
        "stagePlan": [{
            **base["stagePlan"][0], "startSec": 0.0, "endSec": 30.0,
        }],
        "performanceFreedom": "Seedance may discover the detailed performance.",
        "providerPrompt": " ".join(["direction"] * 1100),
    }
    AnimationDirection.model_validate(long_form)
    long_over_legacy_target = AnimationDirection.model_validate({
        **long_form, "providerPrompt": " ".join(["direction"] * 1400),
    })
    assert len(long_over_legacy_target.providerPrompt.split()) == 1400

    incomplete = AnimationDirection.model_validate({
        **base,
        "performanceFreedom": "Seedance may discover the detailed performance.",
    })
    report = R._animation_prompt_contract_report(
        {"dialogueLines": [], "durationSec": 8}, incomplete)
    assert report["ready"] is False
    assert report["authoringContract"]["status"] == "needs-work"


def test_animation_direction_requires_complete_ordered_timestamp_stages():
    stage = {
        "stageNumber": 1,
        "beatIds": ["1.B1"],
        "purpose": "Land the reaction",
        "startSec": 0,
        "endSec": 8,
        "initialOrCarriedState": "Fuzzby begins in the approved pose.",
        "cause": "Fuzzby's speed loads the flower stem.",
        "primaryEvent": "The flower bends and redirects him.",
        "observableEndState": "He catches himself on the bloom.",
        "emotionOrCameraAnalysis": "The held wide frame makes the recovery readable.",
    }
    base = {
        "shotId": "1.B1.S1", "taskMode": "reference-to-video",
        "durationSec": 8,
        "pacingMode": "timestamp",
        "generationGoal": "Generate the physical joke.",
        "deliveryPlan": "A clear cause and delayed reaction land the beat.",
        "creativeTranslation": {
            "interpretation": {
                "jokeOrAche": "Confidence becomes a visible wobble.",
                "mechanism": "The flower returns the force Fuzzby gives it.",
                "statusBefore": "Fuzzby leads.", "statusAfter": "The flower wins.",
                "audienceProgression": ["anticipation", "impact", "release"],
                "emotionalHeart": "The failure remains gentle and affectionate.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit", "completeGagArcCount": 0,
                "densityJudgement": "One readable action and reaction.",
                "splitOrNonSplitRationale": "The causal chain belongs in one unit.",
                "handoffState": "Caught on the bloom.",
            },
        },
        "dramaticBeat": "Confidence becomes a wobble.",
        "audienceBefore": "Anticipation.", "audienceAfter": "Affectionate laughter.",
        "beatOwner": "Fuzzby", "performanceFreedom": "Seedance may shape the recovery.",
        "performanceArc": "Confidence tightens into surprise.",
        "physicalCauseAndEffect": "The flower bends and rebounds.",
        "cameraBehaviour": "Hold wide for the cause and reaction.",
        "timingAndRhythm": "Fast cause, delayed read.",
        "landingBreath": "Hold the caught pose.", "directionDensity": "guided",
        "precisionReasons": [], "shotPlan": [{
            "shotNumber": 1, "purpose": "Carry the joke.",
            "framingLensAndCamera": "Held wide.", "causalAction": "Flower redirects him.",
            "observablePerformance": "A private flinch.",
            "compositionLightAndMaterials": "Warm meadow depth.",
            "landingImage": "Caught on the bloom."}],
        "stagePlan": [stage], "referenceContract": [],
        "geography": ["The flower lane runs frame-left to frame-right."],
        "consistencyContract": ["Keep identity stable."],
        "audioContract": "No dialogue; preserve ambience.",
        "continuityFinish": "Caught on the bloom.", "surgicalSafeguards": [],
        "providerPrompt": "A structured Seedance prompt long enough for model validation."
    }
    assert AnimationDirection.model_validate(base).stagePlan[0].endSec == 8

    incomplete = {**base, "stagePlan": [{**stage, "endSec": None}]}
    try:
        AnimationDirection.model_validate(incomplete)
    except ValidationError:
        pass
    else:
        raise AssertionError("timestamp pacing must require both boundaries")
