"""Opening stills must have one source of truth for each kind of state."""

import ast
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import cb_departments
import cb_render


def test_next_beat_owns_movable_props_and_derived_layout_is_not_approved(monkeypatch):
    monkeypatch.setattr(cb_render, "_characters_cfg", lambda: {
        "Sunny": {"heightIn": 50}, "Howey": {"heightIn": 70},
        "Misty": {"heightIn": 65}, "Fuzzby": {"heightIn": 14},
    })
    shot = {
        "shotId": "S4.SH3",
        "openingCharactersInFrame": ["Sunny", "Howey", "Misty", "Fuzzby"],
        "openingPose": "The chain is about to start.",
        "shotTransition": {"type": "cut", "stateSourceShotId": "S4.SH2"},
        "storyboardInternalShotPlanApproved": [{
            "startState": "Objects are unstable but not yet colliding.",
            "staging": "Lantern hangs low near the stool; honey pot waits beyond Misty.",
            "continuity": "Wet floor and fallen garland remain.",
            "purpose": "Read the cause of the chain.",
            "framing": "Crowded wide view.",
            "cinematography": {"lens": "24 mm", "light": "Lantern light wobbles when struck"},
        }],
    }
    direction = cb_render._direct_keyframe_direction(shot)
    assert direction["openingFrameLayoutAuthority"] == "derived_advisory"
    prompt = cb_render._compile_keyframe_integration_prompt(direction, shot, [
        {"slot": "@图1", "role": "Sunny"},
        {"slot": "@图2", "role": "Howey"},
        {"slot": "@图3", "role": "Misty"},
        {"slot": "@图4", "role": "Fuzzby"},
        {"slot": "@图5", "role": "scene plate"},
        {"slot": "@图6", "role": "previous shot final frame"},
    ])
    sections = cb_departments.prompt_sections(prompt)

    assert "fixed set, geography and lighting only" in sections["REFERENCE AUTHORITY"]
    assert "shot opening controls movable prop state" in sections["REFERENCE AUTHORITY"]
    assert "current prop state" not in sections["REFERENCE AUTHORITY"]
    assert "latest visible world and prop state" in sections["REFERENCE AUTHORITY"]
    assert "approved pose" not in sections["SUBJECTS"]
    assert "middle-left" not in sections["SUBJECTS"]
    assert "Fuzzby 14 inches" in sections["SUBJECTS"]
    assert "Sunny 50 inches" in sections["SUBJECTS"]
    assert "not equal screen height" in sections["SUBJECTS"]
    assert sections["OPENING STATE"].startswith("Objects are unstable but not yet colliding.")
    assert "not yet colliding" in sections["DO NOT SHOW YET"]
    assert "Lantern hangs low near the stool" in sections["ENVIRONMENT"]


def test_image_check_must_ground_accessory_claim_on_named_subject(monkeypatch):
    captured = {}

    def review(system, message, schema, **kwargs):
        captured["system"] = system
        return object()

    monkeypatch.setattr(cb_departments.cb_llm, "structured_with_repair", review)
    cb_departments.review_keyframe_conformance({}, ["candidate.png", "reference.png"])
    assert "exact location on the named character" in captured["system"]
    assert "another character's jewellery or a background crystal" in captured["system"]


def test_rescreen_cannot_resign_a_generated_image_against_new_prompt(tmp_path):
    candidate_file = tmp_path / "candidate.png"
    candidate_file.write_bytes(b"saved image")
    original_signature = {"briefHash": "the-brief-actually-sent"}
    candidate = {
        "path": str(candidate_file), "source": "generated",
        "inputSignature": original_signature.copy(), "contentHash": "saved-hash",
    }
    ledger = {"keyframeCandidate": candidate}
    module = SimpleNamespace(
        _shot=lambda *args: {"shotId": "S4.SH3"},
        _ledger=lambda *args: ledger,
        screen_keyframe_conformance=lambda *args, **kwargs: {
            "status": "fail", "reason": "scale", "review": {}},
        _save=lambda *args: None, _now=lambda: "now", Refused=ValueError,
        load_pkg=lambda *args: ({}, "package"),
    )
    tree = ast.parse(Path(__file__).with_name("cb_safety.py").read_text())
    fn = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef) and node.name == "rescreen_keyframe")
    scope = {
        "os": os,
        "m": module, "current_package": lambda *args: ({}, "package"),
        "keyframe_signature": lambda *args: {"briefHash": "new-brief"},
        "file_sha256": lambda *args: "saved-hash",
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "rescreen-policy", "exec"), scope)

    scope["rescreen_keyframe"]("4", "S4.SH3", "Ep4", log=lambda *args: None)
    assert candidate["inputSignature"] == original_signature
    assert candidate["contentHash"] == "saved-hash"
    assert candidate["conformanceScreening"]["status"] == "fail"


def test_human_accept_of_warning_does_not_accept_a_different_brief():
    candidate = {
        "source": "generated", "path": "saved.png",
        "inputSignature": {"briefHash": "actually-sent", "cardHash": "same"},
        "contentHash": "saved-hash",
        "conformanceScreening": {"status": "fail", "reason": "scale"},
    }
    ledger = {"keyframeCandidate": candidate}
    saved = []
    module = SimpleNamespace(
        _shot=lambda *args: {"shotId": "S4.SH3"},
        _ledger=lambda *args: ledger,
        _load_opening_composition_master=lambda *args: None,
        _characters_cfg=lambda: {}, _now=lambda: "now", Refused=ValueError,
        _signature_diff=lambda old, new: [
            key for key in set(old) | set(new) if old.get(key) != new.get(key)],
        _save=lambda *args: saved.append(True),
        load_pkg=lambda *args: ({}, "package"),
    )
    tree = ast.parse(Path(__file__).with_name("cb_safety.py").read_text())
    fn = next(node for node in ast.walk(tree)
              if isinstance(node, ast.FunctionDef) and node.name == "approve_keyframe")
    scope = {
        "m": module, "current_package": lambda *args: ({}, "package"),
        "keyframe_signature": lambda *args: {
            "briefHash": "corrected-brief", "cardHash": "same"},
        "file_sha256": lambda *args: "saved-hash",
        "original": {"approve_keyframe": lambda *args: "approved"},
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "approval-policy", "exec"), scope)

    with pytest.raises(ValueError, match="inputs changed"):
        scope["approve_keyframe"]("4", "S4.SH3", "Ep4")
    assert candidate["inputSignature"]["briefHash"] == "actually-sent"
    assert not saved


def test_approved_image_survives_versioned_compiler_only_change(tmp_path, monkeypatch):
    frame = tmp_path / "approved.png"
    frame.write_bytes(b"human-approved image")
    old_prompt = "[PURPOSE]\nAn approved opening frame."
    old_hash = hashlib.sha256(old_prompt.encode()).hexdigest()
    old_standard = "studio-seedream-opening-brief@2.3.0"
    signature = {
        "cardHash": "unchanged-card", "sceneLookHash": "unchanged-look",
        "referenceHashes": {"plate": "unchanged"},
        "canonProfileDigest": "unchanged-canon",
        "briefHash": old_hash, "promptCompilerStandard": old_standard,
    }
    record = {
        "approved": True, "source": "generated", "path": str(frame),
        "contentHash": cb_render._sha256_file(frame),
        "conformanceScreening": {"status": "pass"},
        "inputSignature": signature,
        "promptContract": {
            "prompt": old_prompt, "promptHash": old_hash,
            "promptStandard": old_standard,
            "directionContract": {"geography": ["unchanged"]},
        },
    }
    shot = {"shotId": "S4.SH2"}
    package = {"continuityLedger": [{"shotId": "S4.SH2"}]}
    expected = {
        **signature, "briefHash": "new-compiler-brief",
        "promptCompilerStandard": cb_render.SEEDREAM_KEYFRAME_PROMPT_STANDARD,
    }
    monkeypatch.setattr(cb_render, "_keyframe_input_signature", lambda *args: expected.copy())
    monkeypatch.setattr(cb_render, "_latest_keyframe_revision_target", lambda *args: "")
    assert cb_render._keyframe_record_status(package, shot, record)["current"]

    expected["cardHash"] = "changed-card"
    assert not cb_render._keyframe_record_status(package, shot, record)["current"]
