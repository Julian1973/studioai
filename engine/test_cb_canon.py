import json

import pytest

import cb_canon
import cb_intake


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        path.write_text(json.dumps(value), encoding="utf-8")
    else:
        path.write_text(str(value), encoding="utf-8")


def _workspace(tmp_path):
    canon = tmp_path / "shows" / "crystal-bears" / "canon"
    _write(canon / "LOCKED_CANON.md", "# Locked show\n")
    _write(tmp_path / "assets" / "keen.png", b"keen".decode())
    _write(tmp_path / "assets" / "squeaky.png", b"squeaky".decode())
    _write(tmp_path / "assets" / "cove.png", b"cove".decode())
    _write(canon / "characters.json", {
        "Keen": {
            "anchor": "assets/keen.png", "key_features": "aquamarine bear",
            "bible": {"pillar": "careful courage"}, "cadence": "measured",
            "sizeRank": 1, "voiceId": "keen-voice",
        },
        "Squeaky": {
            "anchor": "assets/squeaky.png", "key_features": "dolphin",
            "bible": {"pillar": "playful guide"}, "cadence": "clicks",
            "sizeRank": 2,
        },
        "Bo": {"_status": "declared stub"},
    })
    _write(canon / "locations.json", {"Ep1": {"1": {
        "look": "bright cove", "lighting": "warm day", "master": "assets/cove.png",
    }}})
    _write(tmp_path / "cb-seed" / "assets" / "locations" / "_manifest.json", {})
    _write(canon / "performance.json", {"characters": {
        "Keen": {"provenance": "fixture", "acting": "quiet"},
        "Squeaky": {"provenance": "fixture", "acting": "physical"},
    }})
    policy = {
        "schemaVersion": 1,
        "showId": "crystal-bears",
        "sources": {
            "showBible": "shows/crystal-bears/canon/LOCKED_CANON.md",
            "characters": "shows/crystal-bears/canon/characters.json",
            "locations": "shows/crystal-bears/canon/locations.json",
            "locationAssetManifest": "cb-seed/assets/locations/_manifest.json",
            "characterPerformance": "shows/crystal-bears/canon/performance.json",
        },
        "profiles": {
            "story": ["showBible", "characters", "locations"],
        },
        "roster": {
            "Keen": {"tier": "principal", "status": "locked",
                     "voiceMode": "elevenlabs-v3"},
            "Squeaky": {"tier": "guest", "status": "locked",
                        "voiceMode": "nonverbal-sfx"},
            "Bo": {"tier": "guest", "status": "stub", "voiceMode": "unassigned"},
        },
        "characterAliases": {"HOWIE": "Howey"},
        "scriptChecks": {
            "forbiddenPatterns": [{
                "id": "no-crystal", "pattern": "Zenny['’]s crystal",
                "message": "Zenny has no crystal.",
            }],
            "lockedDialogue": [{
                "id": "call", "speaker": "Aida", "triggerPattern": "Rose Quartz",
                "exactText": "Rose Quartz, be our guide!", "message": "Call changed.",
            }],
            "pronounContracts": [{
                "id": "pronouns", "character": "Squeaky",
                "forbiddenPattern": "\\b(?:he|him|his)\\b",
                "evidencePattern": "\\bhis tail\\b", "message": "Pronouns changed.",
            }],
        },
        "compatibilityCopies": [],
        "skillCanonCopiesGlob": "",
    }
    _write(canon / "lock_policy.json", policy)
    return policy


def test_lock_tracks_sources_assets_and_character_readiness(tmp_path):
    _workspace(tmp_path)
    manifest = cb_canon.write_lock(tmp_path, "Tester")
    result = cb_canon.status(root=tmp_path)

    assert result["current"] is True
    assert manifest["manifestDigest"] == result["manifestDigest"]
    assert result["sourceCount"] == 5
    assert {row["name"] for row in result["characters"] if row["productionReady"]} == {
        "Keen", "Squeaky"}
    assert next(row for row in result["characters"] if row["name"] == "Bo")["status"] == "stub"


def test_changed_source_and_asset_make_lock_stale(tmp_path):
    _workspace(tmp_path)
    cb_canon.write_lock(tmp_path, "Tester")
    (tmp_path / "assets" / "keen.png").write_text("changed", encoding="utf-8")
    (tmp_path / "shows" / "crystal-bears" / "canon" /
     "LOCKED_CANON.md").write_text("changed", encoding="utf-8")

    result = cb_canon.status(root=tmp_path)

    assert result["current"] is False
    codes = {item["code"] for item in result["blockers"]}
    assert {"CANON_SOURCE_DRIFT", "CANON_ASSET_DRIFT"} <= codes


def test_stub_blocks_only_an_episode_that_casts_it(tmp_path):
    _workspace(tmp_path)
    cb_canon.write_lock(tmp_path, "Tester")

    assert cb_canon.status("Ep1", ["Keen", "Squeaky"], tmp_path)["episodeReady"] is True
    blocked = cb_canon.status("Ep1", ["Bo"], tmp_path)
    assert blocked["episodeReady"] is False
    assert blocked["episodeBlockers"][0]["code"] == "CAST_CANON_INCOMPLETE"


def test_script_semantics_are_checked_against_locked_contracts(tmp_path):
    policy = _workspace(tmp_path)
    report = cb_canon.validate_script(
        "1 AIDA\nA different Rose Quartz call.\n\n"
        "Zenny's crystal glows.\n\nSqueaky is caught by his tail.\n",
        policy,
    )

    assert report["ok"] is False
    assert {item["code"] for item in report["blockers"]} == {
        "SCRIPT_CANON_CONFLICT", "LOCKED_DIALOGUE_CONFLICT",
        "CHARACTER_PRONOUN_CONFLICT",
    }


def test_script_parser_maps_declared_alias_and_refuses_unknown_cue(monkeypatch):
    monkeypatch.setattr(cb_intake, "_character_aliases", lambda: {"HOWIE": "Howey"})
    parsed = cb_intake.parse_script(
        "EXT. COVE - DAY 1\n\n1 HOWIE\nHe jumped in?!\n",
        roster=["Howey"], log=lambda *_: None,
    )
    assert parsed["events"][-1]["speaker"] == "Howey"

    with pytest.raises(cb_intake.Refused, match="unknown numbered character cue"):
        cb_intake.parse_script(
            "EXT. COVE - DAY 1\n\n2 MYSTERY\nHello.\n",
            roster=["Howey"], log=lambda *_: None,
        )
