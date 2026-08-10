#!/usr/bin/env python3
"""Compare current Scene 1 emissions with the accepted-render golden fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import cb_emission_standard as standard
import cb_departments
import cb_render


ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "cb-output" / "Ep1_scene1_production_package.json"
FIXTURES = ROOT / "engine" / "grammar" / "golden-fixtures" / "scene1-v1"
OUTPUT = ROOT / "cb-output" / "audits" / "SCENE1_GOLDEN_EMISSION_COMPARISON.json"
MARKDOWN_OUTPUT = ROOT / "cb-output" / "audits" / "SCENE1_GOLDEN_EMISSION_COMPARISON.md"
COMPILED_DIR = ROOT / "cb-output" / "audits" / "scene1-compiled-emissions"

UNITS = {
    "S1.SH1A": ("beat_1_chase.txt", "false-triumph-chase"),
    "S1.SH1B": ("beat_2_moustache.txt", "reveal-and-deadpan-verdict"),
    "S1.SH1C": ("beat_3_crash.txt", "escalation-into-verdict"),
    "S1.SH2": ("beat_4_storm.txt", "environment-turn"),
}


def main() -> int:
    package = json.loads(PACKAGE.read_text())
    shots = {shot["shotId"]: shot for shot in package.get("shots") or []}
    ledgers = {item["shotId"]: item for item in package.get("continuityLedger") or []}
    report = {"standard": "emission-standard-v1", "units": {}}
    for shot_id, (fixture_name, archetype) in UNITS.items():
        shot = shots[shot_id]
        candidate = (((ledgers.get(shot_id) or {}).get("departmentWork") or {})
                     .get("animation") or {}).get("candidate") or {}
        candidate_output = candidate.get("output") or {}
        compile_error = None
        if candidate_output:
            try:
                creative_shot = cb_render._shot_creative_contract_view(
                    package, shot, 1, "Ep1")
                typed = cb_departments.AnimationDirection.model_validate(candidate_output)
                current_prompt = cb_departments.compile_animation_provider_prompt(
                    creative_shot, typed).strip()
                source = "recompiled-typed-animation-direction"
            except Exception as exc:  # The report must expose, not hide, compiler refusal.
                current_prompt = ""
                source = "typed-animation-direction-compile-failed"
                compile_error = f"{type(exc).__name__}: {exc}"
        else:
            current_prompt = str(shot.get("seedancePrompt") or "").strip()
            source = "stored-package-emission-no-typed-direction"
        fixture = (FIXTURES / fixture_name).read_text().strip()
        COMPILED_DIR.mkdir(parents=True, exist_ok=True)
        (COMPILED_DIR / f"{shot_id}.txt").write_text(current_prompt + "\n")
        report["units"][shot_id] = {
            "archetype": archetype,
            "source": source,
            "typedDirectionCurrent": bool(candidate_output),
            "compileError": compile_error,
            "currentWords": len(current_prompt.split()),
            "fixtureWords": len(fixture.split()),
            "currentPreflight": standard.preflight(
                current_prompt,
                duration_sec=(candidate.get("output") or {}).get("durationSec"),
                timing_beats=(candidate.get("output") or {}).get("timingBeats") or [],
            ),
            "fixturePreflight": standard.preflight(fixture),
            "currentManifest": standard.manifest_checks(archetype, current_prompt),
            "fixtureManifest": standard.manifest_checks(archetype, fixture),
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Scene 1 Golden Emission Comparison",
        "",
        "No provider calls were made. Scores are deterministic local pre-flight results.",
        "",
        "| Unit | Provenance | Current | Manifest | Golden | Golden manifest |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for shot_id, unit in report["units"].items():
        lines.append(
            f"| {shot_id} | {unit['source']} | {unit['currentPreflight']['score']}/10 "
            f"{unit['currentPreflight']['verdict']} | "
            f"{unit['currentManifest']['passed']}/{unit['currentManifest']['total']} | "
            f"{unit['fixturePreflight']['score']}/10 | "
            f"{unit['fixtureManifest']['passed']}/{unit['fixtureManifest']['total']} |")
    lines.extend(["", "## Unit Findings", ""])
    for shot_id, unit in report["units"].items():
        lines.append(f"### {shot_id}")
        if unit["compileError"]:
            lines.append(f"- Compiler error: `{unit['compileError']}`")
        if not unit["typedDirectionCurrent"]:
            lines.append(
                "- BLOCKED: no current typed Animation Director record exists; the score "
                "is for legacy stored prompt prose, not a fresh deterministic compile.")
        findings = unit["currentPreflight"]["findings"]
        misses = [item["name"] for item in unit["currentManifest"]["checks"]
                  if not item["passed"]]
        lines.append("- Pre-flight: " + (
            ", ".join(f"{item['rule']} ({item['severity']})" for item in findings)
            if findings else "clean"))
        lines.append("- Missing manifest proof: " + (
            "; ".join(misses) if misses else "none"))
        lines.append("")
    MARKDOWN_OUTPUT.write_text("\n".join(lines).rstrip() + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
