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
        "referenceContract": [],
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
