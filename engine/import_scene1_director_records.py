#!/usr/bin/env python3
"""Build the three missing Scene 1 typed Animation Director records.

The human-authored source is ``DIRECTOR_RECORDS_S1.md``. This module encodes that
direction as typed data; provider prose is always emitted by the deterministic compiler.
No provider call or approval occurs here.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
from pathlib import Path

import cb_departments as departments
import cb_emission_standard as standard
import cb_render


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "cb-output" / "Ep1_scene1_production_package.json"
SOURCE = Path("/Users/julianjenkins/Downloads/DIRECTOR_RECORDS_S1.md")
OUTPUT_DIR = ROOT / "cb-output" / "creative" / "director-records" / "scene1-v1"
REPORT = ROOT / "cb-output" / "audits" / "SCENE1_TYPED_DIRECTOR_COMPARISON.json"
REPORT_MD = ROOT / "cb-output" / "audits" / "SCENE1_TYPED_DIRECTOR_COMPARISON.md"
FIXTURES = ROOT / "engine" / "grammar" / "golden-fixtures" / "scene1-v1"

ARCHETYPES = {
    "S1.SH1B": ("beat_2_moustache.txt", "reveal-and-deadpan-verdict"),
    "S1.SH1C": ("beat_3_crash.txt", "escalation-into-verdict"),
    "S1.SH2": ("beat_4_storm.txt", "environment-turn"),
}


def refs():
    return [
        {"assetTag": "@图1", "role": "opening_frame",
         "controls": "Exact final frame of the previous unit and opening continuity state only. Do not redesign identity or repeat preceding action.",
         "scope": "continuity"},
        {"assetTag": "@图2", "role": "character_identity",
         "controls": "Zenny exact identity, slender smaller proportions, clean fur, glasses and wings only. Do not use its pose or background.",
         "scope": "canon"},
        {"assetTag": "@图3", "role": "character_identity",
         "controls": "Fuzzby exact identity, larger proportions, fur, spectacles and wings only. Do not use its pose or background.",
         "scope": "canon"},
        {"assetTag": "@图4", "role": "location",
         "controls": "Flower-corridor geometry, bee-height scale, plant materials, light and atmospheric depth only. Do not use or invent characters.",
         "scope": "canon"},
        {"assetTag": "@Audio1", "role": "audio",
         "controls": "Approved dialogue words, speakers and performance only. No alternative voices, added words, narration or ad-libs.",
         "scope": "episode"},
    ]


def interpretation(joke, mechanism, before, after, progression, heart):
    return {
        "jokeOrAche": joke, "mechanism": mechanism,
        "statusBefore": before, "statusAfter": after,
        "audienceProgression": progression, "emotionalHeart": heart,
    }


def stage(number, beat_ids, purpose, opening, cause, event, ending, analysis,
          start=None, end=None):
    value = {
        "stageNumber": number, "beatIds": beat_ids, "purpose": purpose,
        "initialOrCarriedState": opening, "cause": cause,
        "primaryEvent": event, "observableEndState": ending,
        "emotionOrCameraAnalysis": analysis,
    }
    if start is not None:
        value.update(startSec=start, endSec=end)
    return value


def shot(number, purpose, camera, action, performance, finish, dialogue=(), gags=()):
    return {
        "shotNumber": number, "purpose": purpose,
        "framingLensAndCamera": camera, "causalAction": action,
        "observablePerformance": performance,
        "compositionLightAndMaterials": "Feature-quality tactile fur, translucent wings, responsive petals, separated golden pollen and continuous scene light.",
        "landingImage": finish,
        "dialogueLineIndexes": list(dialogue), "gagBeatIds": list(gags),
    }


def base(shot_id, duration, goal, delivery, creative, dramatic, before, after,
         owner, freedom, arc, physics, camera, rhythm, breath, shot_plan,
         timing_beats, stages, geography, finish, safeguards, ownership=(),
         environment=()):
    return {
        "shotId": shot_id, "durationSec": duration,
        "taskMode": "reference-to-video",
        "pacingMode": "timestamp" if duration > 15 else "storyline",
        "generationGoal": goal, "deliveryPlan": delivery,
        "creativeTranslation": creative, "dramaticBeat": dramatic,
        "audienceBefore": before, "audienceAfter": after, "beatOwner": owner,
        "performanceFreedom": freedom, "performanceArc": arc,
        "physicalCauseAndEffect": physics, "cameraBehaviour": camera,
        "timingAndRhythm": rhythm, "landingBreath": breath,
        "directionDensity": "guided",
        "precisionReasons": [
            "Locked dialogue must remain assigned to its named speaker.",
            "Visible cause, ownership and outgoing continuity are essential story facts.",
        ],
        "shotPlan": shot_plan, "timingBeats": timing_beats,
        "witnessStagingSides": [
            "Fuzzby stages frame-left; Zenny holds frame-right as the witness."
        ],
        "stagePlan": stages, "geography": geography,
        "attributeOwnership": list(ownership),
        "environmentContract": list(environment),
        "referenceContract": refs(),
        "consistencyContract": [
            "Exactly one Fuzzby and one Zenny throughout; no duplicates or blended identities.",
            "Fuzzby remains larger and stages frame-left; Zenny remains smaller, clean and stages frame-right.",
            "Keep the bee-height flower-corridor axis, tactile plant response and continuous light.",
        ],
        "audioContract": "@Audio1 is the sole authority for dialogue identity, cadence and delivery. Named listeners stay silent and closed-mouth. Generate foley only; no music.",
        "continuityFinish": finish,
        "surgicalSafeguards": safeguards,
        "providerPrompt": "Compiler-owned placeholder; deterministic emission replaces this text.",
    }


def records(package):
    shots = {item["shotId"]: item for item in package["shots"]}
    locked = {
        sid: departments.animation_locked_visual_events(shots[sid])
        for sid in ARCHETYPES
    }

    b_end = "Fuzzby proudly moustachioed frame-left, Zenny clean-faced and quietly smiling frame-right, golden pollen drifting between them. Harvest this exact frame as SH1C's opening."
    b_clock = {
        "beatCode": "1.B2", "mode": "BIG",
        "setup": "Fuzzby is still riding the last triumph, face clean.",
        "anticipation": "He launches at the flower far too hard, overshoots, swings back and arrives faster than he can stop.",
        "impact": "The stamens load his upper lip while the cut hides the result.",
        "reaction": "Zenny examines the moustache, suppresses a reaction and answers with warmth.",
        "recoveryHold": "Hold on Zenny's face for a full beat after she finishes.",
        "recoveryHoldSec": 2.0, "button": "Yes Fuzzby. Officially nuts!",
        "retroactive": False,
        "providerAction": locked["S1.SH1B"][0]["primaryEvent"],
    }
    b = base(
        "S1.SH1B", 14,
        "An overcommitted flower dive creates a pollen moustache that Fuzzby proudly presents before Zenny's affectionate deadpan verdict.",
        "Use transfer, reveal and verdict shots so causality, feature ownership, eye-line and the held witness payoff remain individually readable.",
        {"interpretation": interpretation(
            "Fuzzby mistakes visible failure for distinguished status.",
            "Unawareness meets affection: the evidence appears before Zenny judges it.",
            "Fuzzby enters face-clean and still riding his false triumph.",
            "Fuzzby proudly wears the moustache while Zenny's restraint makes the insult land as love.",
            ["His arrival looks too committed.", "The reveal proves a ridiculous moustache.", "Her warm verdict converts mockery into affection."],
            "Zenny tells the truth without rejecting him."),
         "gagClocks": [b_clock],
         "generationDesign": {"packagingDecision": "single-unit", "completeGagArcCount": 1,
            "densityJudgement": "Three clean visual ideas need thirteen seconds: hidden transfer, reveal and verdict.",
            "splitOrNonSplitRationale": "Three motivated cuts protect one continuous status gag.",
            "handoffState": shots["S1.SH1B"]["visualPayoff"]}},
        "The pollen moustache turns an accident into status play and Zenny's restraint defines their relationship.",
        "The audience sees Fuzzby seeking approval while still face-clean.",
        "The audience sees the moustache, then watches Zenny turn a truthful insult into warmth.",
        "1.B2",
        "Seedance may discover pollen drift, wing settling and tiny facial adjustments, but the transfer, reveal order, clean Zenny and eye-line sequence cannot change.",
        "Leftover triumph becomes overcommitted arrival, oblivious pride and a flicker of needing approval; Zenny moves from examination through a suppressed reaction into warm deadpan.",
        "The too-fast arrival presses stamens onto Fuzzby's upper lip while his body remains outside the petals, making the transfer visible and causal.",
        "Bee-height two-shot for transfer, close reveal, then over-shoulder verdict with Fuzzby's moustache foreground and Zenny sharp.",
        "Chaotic arrival, hidden transfer, slow reveal, presented pause, deliberate eye-line, micro-tell, line and long hold.",
        "Hold Zenny's almost-still face until the mouth-corner restraint and affection both read.",
        [
            shot(1, "Hide the causal transfer until the reveal cut.",
                 "Bee-height two-shot; cut before Fuzzby withdraws and before the result is visible.",
                 "Face clean, Fuzzby launches too hard, overshoots, swings back and arrives faster than he can stop. His face jolts into the bloom; stamens press his upper lip while body, legs and wings stay outside.",
                 "Leftover triumph drives an arrival with no stopping distance; Zenny stays clean and outside his route.",
                 "Cut before he withdraws; the pollen result remains hidden."),
            shot(2, "Reveal and present the accidental badge.",
                 "Close-up on Fuzzby withdrawing from the same flower.",
                 "He pulls back wearing two clear upper-lip pollen curls, lifts his chin and presents the moustache as distinguished status.",
                 "He is entirely unaware, proud but with a small hopeful need for approval.",
                 "Fuzzby holds proudly frame-left; the target flower remains visible behind him.", dialogue=(1,)),
            shot(3, "Let Zenny inspect, suppress and deliver the affectionate verdict.",
                 "Over Fuzzby's moustache in soft foreground to Zenny sharp frame-right; hold on her after the line.",
                 "Zenny's face and fur remain completely clean. Her eyes travel to the moustache and back to Fuzzby; one mouth corner tightens in a micro-tell before she speaks.",
                 "Her body stays economical and the verdict remains warm, never mocking or broad.",
                 b_end, dialogue=(2,), gags=("1.B2",)),
        ],
        [{"type": "settle", "count": 1, "source": "leftover triumph"},
         {"type": "business", "count": 2, "source": "arrival and presentation"},
         {"type": "impact", "count": 1, "source": "stamen transfer"},
         {"type": "reveal", "count": 1, "source": "moustache reveal"},
         {"type": "reaction", "count": 1, "source": "Zenny inspection"},
         {"type": "turn", "count": 1, "source": "warm verdict"}],
        [stage(1, ["1.B2"], "Transfer, reveal and verdict", "Fuzzby enters face-clean from the approved previous end state.", "His leftover pride makes him attack the flower too fast.", locked["S1.SH1B"][0]["primaryEvent"], locked["S1.SH1B"][0]["observableEndState"], "Evidence must read before Zenny's affectionate judgement.")],
        ["The same bee-height flower corridor continues without a geography reset.",
         "Fuzzby stages frame-left beside the target flower; Zenny witnesses from frame-right outside his route."],
        locked["S1.SH1B"][0]["observableEndState"],
        ["Do not reveal the moustache before the close-up.", "Keep Fuzzby's body outside the flower.", "Do not transfer pollen to Zenny."],
        ["The pollen moustache belongs to Fuzzby only.", "Zenny's face, lip, fur and body stay completely clean; no pollen touches her."],
    )

    c_end = "Fuzzby is completely pollen-covered and proud frame-left; Zenny stays clean as her eye-roll softens into a genuine loving smile frame-right. Harvest this exact frame as SH2's opening."
    c_clock = {
        "beatCode": "1.B3", "mode": "BIG",
        "setup": "The intact curled moustache from the previous unit remains on Fuzzby.",
        "anticipation": "He confidently wipes once, then stops when he sees yellow pollen on his own paw.",
        "impact": "The wipe worsens the smear and his bolt escalates through two increasingly large contacts into the blossom.",
        "reaction": "Zenny waits until his line finishes, then turns from eye-roll into a loving smile.",
        "recoveryHold": "Hold until Zenny's loving smile fully reads and settles.",
        "recoveryHoldSec": 2.0, "button": "Buzz Crash!!", "retroactive": False,
        "providerAction": locked["S1.SH1C"][0]["primaryEvent"],
    }
    c = base(
        "S1.SH1C", 18,
        "A failed moustache correction escalates through increasingly severe collisions into a blossom, a showman recovery and Zenny's loving verdict.",
        "Separate correction, escalation and verdict so each worsening cause, the button pose and the emotional turn receive their own readable shot.",
        {"interpretation": interpretation(
            "Every attempt to hide failure creates larger evidence.",
            "The confident fix worsens the mark; seeing his own paw triggers a causal bolt and escalating contacts before he performs success.",
            "Fuzzby begins embarrassed but convinced he can fix the moustache.",
            "He ends more covered and more proudly performative while Zenny openly reveals affection.",
            ["The wipe should fix it.", "His own paw proves it is worse and the flight compounds it.", "His claim fails, but Zenny's smile keeps him lovable."],
            "Zenny's eye-roll becoming love states that she adores the whole ridiculous truth."),
         "gagClocks": [c_clock],
         "generationDesign": {"packagingDecision": "continuation-unit", "completeGagArcCount": 1,
            "densityJudgement": "Eighteen seconds protects the failed correction, escalating collision chain, button and reactor turn.",
            "splitOrNonSplitRationale": "Three internal shots keep one causal escalation while isolating the final verdict.",
            "handoffState": shots["S1.SH1C"]["visualPayoff"]}},
        "A grooming correction becomes a larger public failure, which Fuzzby instantly rebrands while Zenny's patience becomes visible love.",
        "The audience sees an intact moustache and expects a simple correction.",
        "The audience sees each correction worsen the evidence and understands Zenny's affection.", "1.B3",
        "Seedance may shape kick rhythm, pollen fall and micro-expression timing, but the self-evidence, increasing contacts, pose-before-line and delayed Zenny cut are locked.",
        "Embarrassment becomes failed confidence, self-evidence, panic and helpless escalation, then instant showmanship; Zenny's patience becomes affection.",
        "The wipe drags pollen wider; seeing it on his paw triggers the bolt; each contact adds rotation before the blossom catches his head and the stored body pops vertically free.",
        "Steady correction medium, side tracking escalation, wide blossom silhouette, then held showman pose and delayed cut to Zenny.",
        "Gasp, wipe, evidence stop, bolt, two separated increasing contacts, blossom, pop, pose, line, then slow reactor turn.",
        "Do not cut to Zenny until Fuzzby's line and held pose have fully landed; then wait for the smile to settle.",
        [
            shot(1, "Make the attempted correction visibly worsen the evidence.", "Steady medium, Fuzzby frame-left and Zenny clean frame-right.",
                 "Fuzzby jolts and wipes one paw across his upper lip, smearing the pollen wider and messier. He stops, looks down at the bright yellow on his own paw, then his expression drops into panic and he bolts.",
                 "Embarrassment becomes confidence for one wipe, then self-evidence turns it into status panic.", "Fuzzby has left frame at speed; Zenny remains still and clean."),
            shot(2, "Escalate two readable contacts into the blossom capture.", "Side tracking at speed, widening for the blossom so his legs remain readable.",
                 "He clips a flower first and spins once. He clips a second harder and the spin doubles, visibly larger than the first. Each contact is separate. He flies headfirst into a blossom; only his head enters while body, wings and kicking legs remain outside.",
                 "He fights each spin too late but never reads as hurt or distressed.", "Held wide on Fuzzby upside down in the blossom, body outside and legs kicking."),
            shot(3, "Land the showman claim before revealing Zenny's loving verdict.", "Hold Fuzzby frame-left for the button; only after the line ends cut to Zenny frame-right.",
                 "Fuzzby pops vertically out in one explosive motion. The full showman pose lands and holds before he speaks. After the line has completely finished, cut to Zenny: her eyes travel over him, one slow eye-roll softens as her eyes come down into a genuine loving smile.",
                 "He replaces panic with total conviction; her reaction moves visibly from resignation into affection.", c_end, dialogue=(1,), gags=("1.B3",)),
        ],
        [{"type": "reaction", "count": 1, "source": "failed correction"},
         {"type": "business", "count": 1, "source": "wipe"},
         {"type": "business", "count": 1, "source": "panic bolt and route transfer"},
         {"type": "impact", "count": 2, "source": "escalating contacts"},
         {"type": "settle", "count": 1, "source": "showman pose"},
         {"type": "reaction", "count": 1, "source": "reactor verdict"},
         {"type": "turn", "count": 1, "source": "eye-roll to love"}],
        [stage(1, ["1.B3"], "Failed correction, escalation and verdict", "Carry the exact moustachioed end state from SH1B.", "The confident wipe drags pollen instead of removing it and starts one causal worsening chain.", locked["S1.SH1C"][0]["primaryEvent"], locked["S1.SH1C"][0]["observableEndState"], "The evidence precedes panic, contacts escalate, and the pose and line land before Zenny's turn reveals love.", 0, 18)],
        ["Continue in the same bee-height flower corridor and preserve the frame-left Fuzzby, frame-right Zenny relationship.", "Keep every collision and the receiving blossom on one readable side-tracking route."],
        locked["S1.SH1C"][0]["observableEndState"],
        ["Do not obscure the widening smear before the bolt.", "Keep Fuzzby's body outside the blossom.", "Do not cut to Zenny before the line finishes."],
        ["All pollen marks, smears and dusting belong to Fuzzby only.", "Zenny's face, lip, fur and body stay completely clean throughout; no pollen touches her."],
    )

    sh2_shot = cb_render._shot_creative_contract_view(package, shots["S1.SH2"], 1, "Ep1")
    approved = {item["beatCode"]: item for item in sh2_shot.get("comedyContractsApproved") or []}
    def approved_clock(code, provider_action, hold_sec):
        item = approved[code]
        return {"beatCode": code, "mode": item["mode"], "setup": item["setup"],
                "anticipation": item["expectation"], "impact": item["disruption"],
                "reaction": "The witness remains economical while the changed world or physical evidence settles.",
                "recoveryHold": item["hold"], "recoveryHoldSec": hold_sec,
                "button": item["button"], "retroactive": False,
                "providerAction": provider_action}
    d_end = "Fuzzby's head remains inside the flower frame-left with body and legs outside; Zenny stays calm and clean frame-right as the cold corridor moves in the wind. No further movement; hold, then slow fade to black."
    d = base(
        "S1.SH2", 15,
        "The unchanged flower corridor turns from warm play-space into storm warning before either bee reacts, then Fuzzby's bravado drives him directly into a flower.",
        "Use world turn, Zenny read and physical contradiction shots so the environment changes first and the final motionless image closes the scene.",
        {"interpretation": interpretation(
            "The comedy yields to story when the world changes independently of Fuzzby's performance.",
            "Light, sky, colour and flower posture turn first; his body betrays fear, Zenny listens, and his cover boast creates the final capture.",
            "Both bees share the warm pollen aftermath.",
            "The corridor is cold and wind-pressed; Fuzzby is stuck while Zenny's care remains beside him.",
            ["The warm world begins to feel wrong.", "Zenny's stillness confirms a real storm.", "Fuzzby's denial creates one final comic contradiction inside the warning."],
            "Zenny's quiet certainty asks Fuzzby to stop performing and stay close."),
         "gagClocks": [
             approved_clock("1.B4", locked["S1.SH2"][0]["primaryEvent"], 2.0),
             approved_clock("1.B5", locked["S1.SH2"][1]["primaryEvent"], 2.0),
         ],
         "generationDesign": {"packagingDecision": "single-unit", "completeGagArcCount": 2,
            "densityJudgement": "Fifteen seconds protects a complete world turn, genuine listening beat, quiet line, boast, impact and final hold.",
            "splitOrNonSplitRationale": "Three motivated shots preserve one tonal turn and its immediate physical consequence.",
            "handoffState": shots["S1.SH2"]["visualPayoff"]}},
        "The same corridor becomes warning-space before Fuzzby's denial produces a final soft capture.",
        "The audience is still enjoying the warm pollen aftermath.",
        "The audience believes the storm is real and sees Zenny's concern beneath the closing joke.", "1.B4+1.B5",
        "Seedance may shape wind, pollen tremble, wing hitch and Zenny's listening micro-movements, but geometry, world-first ordering, dialogue ownership and final hold cannot change.",
        "Warm aftermath cools into warning; Fuzzby's physical betrayal becomes cover, Zenny becomes genuinely still, and his overcorrection ends in fond resignation.",
        "Thunder trembles pollen; cooling light and wind furl the flowers; Fuzzby's wings hitch before he covers; his straight launch compresses the receiving flower around his head.",
        "Medium-wide world turn, close Zenny read, then a clean straight-line launch and motionless closing hold.",
        "World turns completely first, wings hitch, cover line, real listen, quiet warning and hold, then boast, crash, wind, stillness and fade.",
        "After the final capture, remove all performance movement; hold the changed world and relationship before the slow fade.",
        [
            shot(1, "Let the environment change before either character responds.", "Medium-wide holding both bees and identical corridor geometry.",
                 locked["S1.SH2"][0]["primaryEvent"] + " Before either character reacts, thunder trembles the suspended pollen; god-rays thin, sky greys, colour cools, and open flowers furl and droop in the wind. Only then Fuzzby's wings hitch twice, his hover drops, and he exhales into a breezy rebrand.",
                 "His body betrays fear before his cover line; Zenny does not react until the world turn is complete.", "The full corridor is cool and wind-pressed; Fuzzby has covered his dip and Zenny begins to attend upward.", dialogue=(1,), gags=("1.B4",)),
            shot(2, "Make Zenny's listening turn the weather into story.", "Close on Zenny frame-right with the changed corridor still present behind her.",
                 "Zenny becomes still, quiets her wings and genuinely listens. Her gaze travels upward to the storm sky before she names it without drama.",
                 "Concern replaces deadpan; almost no gesture makes her certainty carry weight.", "Zenny remains small, still and sky-aware in the cold light; hold after the line ends.", dialogue=(2,)),
            shot(3, "Contradict the pressure boast and close on the motionless relationship image.", "Return to the two-character axis and hold the complete final tableau before fading.",
                 locked["S1.SH2"][1]["primaryEvent"] + " Fuzzby launches in a perfectly straight line. Fuzzby’s forward force pushes into the flower mouth; petals compress around him and hold his body, with pollen quivering from the impact instead of exploding into harmless sparkle.",
                 "His bravado remains full volume until the soft capture; Zenny's concern settles into fond resignation.", d_end, dialogue=(3,), gags=("1.B5",)),
        ],
        [{"type": "environment_turn", "count": 1, "source": "two-state world turn"},
         {"type": "reaction", "count": 1, "source": "physical betrayal"},
         {"type": "turn", "count": 1, "source": "warning line"},
         {"type": "settle", "count": 1, "source": "overcorrection"},
         {"type": "impact", "count": 1, "source": "flower capture"}],
        [stage(1, ["1.B4"], "World turn and warning", "Carry the pollen-covered warm aftermath from SH1C.", "Distant thunder changes the environment before character response.", locked["S1.SH2"][0]["primaryEvent"], locked["S1.SH2"][0]["observableEndState"], "The world owns the tonal turn; Zenny's stillness makes it real."),
         stage(2, ["1.B5"], "Boast and capture", "Continue in the same geometry after Zenny's warning.", "Fuzzby's cover performance overcommits into a straight launch.", locked["S1.SH2"][1]["primaryEvent"], locked["S1.SH2"][1]["observableEndState"], "The closing joke must retain the storm unease and Zenny's care.")],
        ["The location has identical geometry in both warm and storm states; Fuzzby remains frame-left and Zenny frame-right.", "The receiving flower stays on Fuzzby's straight launch route while the narrow sky gap remains visible above."],
        locked["S1.SH2"][-1]["observableEndState"],
        ["Do not change corridor geometry during the weather turn.", "Do not let a character react before the flowers and light turn.", "Add no movement after the final tableau before fade."],
        ["All pollen coating and smears belong to Fuzzby only.", "Zenny's face, lip, fur and body stay completely clean; no pollen touches her."],
        ["The location is defined in TWO states with identical geometry: warm golden and cool blue-grey storm-lit.", "Geometry remains identical; only light, sky, colour, atmospheric pressure and flower posture change.", "The environment changes completely before either character reacts.", "Open flowers furl and droop as the wind rises; vegetation posture changes, not only illumination."],
    )
    return {"S1.SH1B": b, "S1.SH1C": c, "S1.SH2": d}


def build(apply=False):
    package = json.loads(PACKAGE.read_text())
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    built = {}
    for shot_id, raw in records(package).items():
        creative_shot = cb_render._shot_creative_contract_view(
            package, next(item for item in package["shots"] if item["shotId"] == shot_id),
            1, "Ep1")
        direction = departments.AnimationDirection.model_validate(raw)
        direction.providerPrompt = departments.compile_animation_provider_prompt(
            creative_shot, direction)
        direction = departments.AnimationDirection.model_validate(direction.model_dump())
        built[shot_id] = direction

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {"source": str(SOURCE), "sourceSha256": source_hash, "units": {}}
    for shot_id, direction in built.items():
        fixture_name, archetype = ARCHETYPES[shot_id]
        prompt = direction.providerPrompt
        shot_value = next(item for item in package["shots"] if item["shotId"] == shot_id)
        creative_shot = cb_render._shot_creative_contract_view(
            package, shot_value, 1, "Ep1")
        (OUTPUT_DIR / f"{shot_id}.json").write_text(
            json.dumps(direction.model_dump(), indent=2, ensure_ascii=False) + "\n")
        (OUTPUT_DIR / f"{shot_id}.prompt.txt").write_text(prompt + "\n")
        flight = standard.preflight(
            prompt, duration_sec=direction.durationSec,
            timing_beats=[item.model_dump() for item in direction.timingBeats])
        manifest = standard.manifest_checks(archetype, prompt)
        golden = (FIXTURES / fixture_name).read_text()
        report["units"][shot_id] = {
            "preflight": flight, "manifest": manifest,
            "productionPromptContract": cb_render._animation_prompt_contract_report(
                creative_shot, direction),
            "engineRuleReport": cb_render._engine_rule_report(
                package, creative_shot, direction, cinematography={}),
            "goldenPreflight": standard.preflight(golden),
            "goldenManifest": standard.manifest_checks(archetype, golden),
            "wordCount": len(prompt.split()), "goldenWordCount": len(golden.split()),
        }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    rows = [
        "# Scene 1 Typed Director Comparison", "",
        "No provider calls, renders or approvals were made.", "",
        "| Unit | Duration | Compiled words | Score | Manifest | Golden score | Golden manifest | Contract | Engine |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for shot_id, value in report["units"].items():
        direction = built[shot_id]
        rows.append(
            f"| {shot_id} | {direction.durationSec}s | {value['wordCount']} | "
            f"{value['preflight']['score']}/10 | "
            f"{value['manifest']['passed']}/{value['manifest']['total']} | "
            f"{value['goldenPreflight']['score']}/10 | "
            f"{value['goldenManifest']['passed']}/{value['goldenManifest']['total']} | "
            f"{'PASS' if value['productionPromptContract']['ready'] else 'BLOCK'} | "
            f"{'PASS' if value['engineRuleReport']['ready'] else 'BLOCK'} |")
    rows.extend([
        "", "## Provenance", "",
        f"- Director source: `{SOURCE}`",
        f"- Source SHA-256: `{source_hash}`",
        "- Typed records and compiled prompts: `cb-output/creative/director-records/scene1-v1/`",
        "- SH1B compiles at 14 seconds because its costed minimum with margin is 13.225 seconds.",
        "- Records are prepared candidates only. Julian has not approved or submitted them.",
    ])
    REPORT_MD.write_text("\n".join(rows) + "\n")

    if apply:
        failures = [shot_id for shot_id, value in report["units"].items()
                    if value["preflight"]["verdict"] != "PASS"
                    or not value["manifest"]["ready"]
                    or not value["productionPromptContract"]["ready"]
                    or not value["engineRuleReport"]["ready"]]
        if failures:
            raise RuntimeError(
                "Refusing to install non-conforming Director records: " + ", ".join(failures))
        ledgers = {item["shotId"]: item for item in package["continuityLedger"]}
        for shot_id, direction in built.items():
            shot_value = next(item for item in package["shots"] if item["shotId"] == shot_id)
            shot_value["durationSec"] = direction.durationSec
            ledger = ledgers[shot_id]
            work = ledger.setdefault("departmentWork", {}).setdefault(
                "animation", {"approved": None, "candidate": None, "history": []})
            if work.get("candidate"):
                work.setdefault("history", []).append(work["candidate"])
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            work["candidate"] = {
                "department": "Animation", "worker": "Animation Director",
                "skill": "human-director-record-import-v1", "model": "deterministic",
                "preparedAt": now, "editedAt": now,
                "preparedBy": "Julian Director record import",
                "sourceHash": source_hash, "output": direction.model_dump(),
                "engineRuleReport": report["units"][shot_id]["engineRuleReport"],
            }
        cb_render._save(package, PACKAGE)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(apply=args.apply), indent=2, ensure_ascii=False))
