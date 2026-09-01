#!/usr/bin/env python3
"""Mechanical pre-flight for the rendered-and-accepted emission standard v1."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable

EMISSION_FIRING_FLOOR = 9.5


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    message: str
    fix: str
    deduction: float


def _project_emission_checks() -> dict:
    """laws/emission_checks.json for the active project, or {} (T49)."""
    try:
        import project_laws
        return project_laws.emission_checks()
    except Exception:
        return {}


def _project_preflight() -> dict:
    pf = _project_emission_checks().get("preflight")
    return pf if isinstance(pf, dict) else {}


def _project_archetype_checks(archetype: str) -> list:
    items = (_project_emission_checks().get("archetypes") or {}).get(archetype) or []
    return [i for i in items if isinstance(i, dict)]


def _has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text, re.I | re.M | re.S))


def _shots(text: str) -> list[str]:
    starts = list(re.finditer(
        r"(?im)^(?:Shot|Phase)\s+\d+\s*(?:[-—:]|\.)", text))
    return [
        text[item.start():(starts[index + 1].start() if index + 1 < len(starts) else len(text))]
        for index, item in enumerate(starts)
    ]


def preflight(prompt: str, *, duration_sec: float | None = None,
              timing_beats: Iterable[dict] | None = None) -> dict:
    findings: list[Finding] = []
    typed_timing_beats = None if timing_beats is None else list(timing_beats)

    def add(severity: str, rule: str, message: str, fix: str, deduction: float):
        findings.append(Finding(severity, rule, message, fix, deduction))

    shots = _shots(prompt)
    dialogue = "{" in prompt and "}" in prompt
    if not _has(prompt, r"(?im)End state:\s*\S"):
        add("FATAL", "ending-state", "No ending state appears in the unit.",
            "End every shot with a describable frame.", 2.0)
    if dialogue and not _has(prompt, r"Dialogue language:\s*\w+"):
        add("FATAL", "dialogue-language", "Dialogue is present without a declared language.",
            "Declare the dialogue language before the shot sequence.", 2.0)

    reference_lines = [line.strip() for line in prompt.splitlines()
                       if re.match(r"(?:@(?:图|Image)\s*\d+|image_\d+)\b", line.strip(), re.I)]
    for line in reference_lines:
        if not _has(
                line,
                r"defines|owns|first frame|opening frame|"
                r"previous shot's approved final frame|previous shot final frame|"
                r"use it only for"):
            add("FATAL", "reference-role", f"Reference has no explicit role: {line[:80]}",
                "Give every reference exactly one positive role.", 2.0)
            break
        if not _has(line, r"do not|exclude|never|ignore|no\s+"):
            add("FATAL", "reference-exclusion", f"Reference has no exclusion: {line[:80]}",
                "Give every reference a negative scope.", 2.0)
            break

    # T49: the words that mark a salient new feature are the PROJECT's own (laws/emission_checks.json).
    _pf = _project_preflight()
    feature = bool(_pf.get("featureIntroducers")) and _has(prompt, str(_pf["featureIntroducers"]))
    if feature and not _has(prompt, r"ATTRIBUTE OWNERSHIP"):
        add("FATAL", "R16", "A salient feature is introduced without an ownership block.",
            "Name the feature owner and explicitly keep every other character clean.", 2.0)

    if duration_sec is not None and typed_timing_beats:
        costs = {
            "travel": 1.8, "dodge": 1.0, "impact": 0.8, "load_release": 2.3,
            "aerial": 1.8, "tumble": 1.2, "settle": 1.0, "self_check": 1.2,
            "reaction": 1.2, "turn": 2.0, "environment_turn": 2.0,
            "reveal": 1.5, "business": 1.5, "hold": 2.0,
        }
        minimum = sum(costs.get(str(beat.get("type")), 0) * int(beat.get("count", 1))
                      for beat in typed_timing_beats) * 1.15
        if minimum > float(duration_sec) + 0.001:
            add("FATAL", "beat-cost", f"Beats need {minimum:.2f}s but unit requests {duration_sec:g}s.",
                "Increase the request duration or split the unit; never trim the direction.", 2.0)

    travel = (
        any(str(beat.get("type") or "").casefold() == "travel"
            for beat in typed_timing_beats)
        if typed_timing_beats is not None
        else _has(prompt, r"\bchase\b|\bpursuit\b|covers real ground|travelling deep")
    )
    traversal_parts = (
        r"three (?:parallax )?speeds", r"(?:passes|pass).*?(?:vanish|disappear).*?behind",
        r"pulls ahead.*?(?:shrink|smaller).*?camera surges", r"off[- ]centre|frame edge",
        r"wipe.*?(?:lens|frame)",
    )
    if travel and not all(_has(prompt, part) for part in traversal_parts):
        add("FIX", "R9", "Travel lacks the complete traversal grammar.",
            "Emit three depth speeds, passing landmarks, scale change, recovery and lens wipes.", 0.75)
    repeated = bool(re.search(
        r"three[^\n.]{0,100}(?:contacts?|impacts?|collisions?)|"
        r"first[^\n.]{0,120}(?:contact|impact|collision)[^\n.]{0,120}"
        r"second[^\n.]{0,120}(?:contact|impact|collision)|"
        r"clips?[^\n.]{0,100}first[^\n.]{0,120}clips?[^\n.]{0,100}second",
        prompt, re.I | re.M))
    if repeated and not _has(prompt, r"worse than|larger than|increas|doubles|escalat"):
        add("FIX", "R10", "Repeated contacts do not explicitly increase.",
            "Separate each contact and state its larger consequence.", 0.75)
    if _has(prompt, r"double .*tuck|triple twist|compound aerial"):
        aerial_shots = [shot for shot in shots if _has(shot, r"double .*tuck|triple twist|compound aerial")]
        if len(aerial_shots) != 1 or not _has(aerial_shots[0], r"full (?:aerial |motion )?arc|every rotation"):
            add("FIX", "R11", "The compound move is not isolated and tracked as one full arc.",
                "Give the compound aerial its own shot and track the complete move.", 0.75)
    if dialogue and _has(prompt, r"(?im)^Dialogue placement:"):
        add("FIX", "R15", "Dialogue is emitted in a detached placement block.",
            "Put each line inside the shot where it is spoken.", 0.75)
    if dialogue and not _has(prompt, r"(?:hold|pose)[^.\n]{0,160}full beat after [^.\n]{0,30}line"):
        # The deterministic dialogue emitter owns the final per-line hold decision and
        # suppresses it for immediate launch/impact/interruption actions. A specialist
        # draft omitting the prose is therefore a review note, not a reason to discard
        # otherwise valid direction before the compiler can apply the typed rule.
        add("POLISH", "button-hold", "No protected post-line hold is visible in the specialist draft.",
            "The deterministic emitter must add holds to non-immediate recognition/reaction lines.", 0.25)
    if _pf.get("retroactivePride") and _has(prompt, str(_pf["retroactivePride"])) and not _has(
            prompt, r"(?:checks?|checking|eyes dart|looks? (?:left|down)|pats? (?:himself|his))"):
        add("FIX", "R12", "Retroactive pride has no self-check before the emotion.",
            "Show the character verify their state before performing pride.", 0.75)
    if _has(prompt, r"Story lock:|Gag action \(|Physics \("):
        add("FIX", "R18", "The shot action is restated in compiler supplement fields.",
            "Let the shot sequence be the story; emit each action once.", 0.75)
    if not (
        _has(prompt, r"\bNo music\b")
        or _has(prompt, r"Seedance may generate non-verbal music, ambience and SFX")
        or _has(prompt, r"Seedance 2\.5 must provide instrumental music, ambience and non-verbal SFX")
    ):
        add("FIX", "audio-policy", "Music/SFX policy is absent.",
            "State either No music or the approved Seedance non-verbal music/SFX policy.",
            0.75)

    # Length is not a creative-quality signal and is not evaluated here.
    if _has(prompt, r"softens") and not _has(prompt, r"from .* into|eye-roll .* into|as .* come.* back"):
        add("POLISH", "turn-states", "An emotional turn does not name both states and movement.",
            "Name the starting state, visible movement and landing state.", 0.25)

    score = max(0.0, 10.0 - sum(item.deduction for item in findings))
    return {
        "score": round(score, 2),
        "firingFloor": EMISSION_FIRING_FLOOR,
        "verdict": "PASS" if score >= EMISSION_FIRING_FLOOR else "BLOCK",
        "findings": [asdict(item) for item in findings],
        "clean": not findings,
    }


def manifest_checks(archetype: str, prompt: str) -> dict:
    shots = _shots(prompt)
    checks: list[tuple[str, bool]] = []

    def check(label: str, pattern: str | None = None, value: bool | None = None):
        checks.append((label, bool(value if value is not None else _has(prompt, pattern or ""))))

    check("2-4 named shots with end states", value=2 <= len(shots) <= 4 and
          all(_has(shot, r"End state:\s*\S") for shot in shots))
    # T49: the per-archetype checks are the PROJECT's own (laws/emission_checks.json → archetypes);
    # the engine only evaluates them. A project with no checks for an archetype runs the structural
    # check above and nothing else.
    for item in _project_archetype_checks(archetype):
        label = str(item.get("label") or "check")
        if "shotCount" in item:
            check(label, value=len(shots) == int(item["shotCount"]))
        elif "shot" in item:
            i = int(item["shot"])
            ok = len(shots) > i and _has(shots[i], str(item.get("pattern") or ""))
            if ok and item.get("brace"):
                ok = "{" in shots[i]
            if ok and item.get("andPattern"):
                ok = _has(shots[i], str(item["andPattern"]))
            check(label, value=ok)
        elif "notPattern" in item:
            check(label, value=not _has(prompt, str(item["notPattern"])))
        else:
            check(label, str(item.get("pattern") or ""))
    passed = sum(1 for _, ok in checks if ok)
    return {
        "archetype": archetype,
        "passed": passed,
        "total": len(checks),
        "ready": passed == len(checks),
        "checks": [{"name": name, "passed": ok} for name, ok in checks],
    }
