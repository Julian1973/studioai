import json
import pathlib

import pytest

import cb_canon
import cb_intake


ROOT = pathlib.Path(__file__).resolve().parents[1]


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
            "sizeRank": 2, "gender": "Male",
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
                "forbiddenPattern": "\\b(?:she|her|hers)\\b",
                "evidencePattern": "\\bher tail\\b", "message": "Pronouns changed.",
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


def test_provider_identity_packs_are_locked_without_invalidating_story(tmp_path):
    policy = _workspace(tmp_path)
    baseline = cb_canon.write_lock(tmp_path, "Tester")
    baseline_status = cb_canon.status(root=tmp_path)
    baseline_story = baseline_status["profileDigests"]["story"]

    _write(tmp_path / "assets" / "keen-provider.png", "provider-safe-keen")
    _write(tmp_path / "shows" / "crystal-bears" / "canon" / "identity_packs.json", {
        "schemaVersion": 1,
        "characters": {
            "Keen": {
                "schemaVersion": 1,
                "source": "assets/keen-provider.png",
                "coverage": "360",
                "providerViews": {
                    "default": {"view": "front", "crop": [0, 0, 1, 1]},
                },
                "turnaroundViews": [
                    {"view": "front", "crop": [0, 0, 0.25, 1]},
                    {"view": "three-quarter", "crop": [0.25, 0, 0.5, 1]},
                    {"view": "side", "crop": [0.5, 0, 0.75, 1]},
                    {"view": "rear", "crop": [0.75, 0, 1, 1]},
                ],
            },
        },
    })
    policy["sources"]["identityPacks"] = (
        "shows/crystal-bears/canon/identity_packs.json")
    policy["profiles"]["animation"] = ["characters", "identityPacks"]
    _write(tmp_path / "shows" / "crystal-bears" / "canon" / "lock_policy.json", policy)

    manifest = cb_canon.write_lock(tmp_path, "Tester")
    current = cb_canon.status(root=tmp_path)

    assert baseline["manifestDigest"] != manifest["manifestDigest"]
    assert current["profileDigests"]["story"] == baseline_story
    assert current["profileDigests"]["animation"] != baseline_story
    assert manifest["identityAssets"] == [{
        "path": "assets/keen-provider.png",
        "roles": ["Keen.source"],
        "sha256": cb_canon.file_sha256(tmp_path / "assets" / "keen-provider.png"),
    }]

    (tmp_path / "assets" / "keen-provider.png").write_text(
        "changed-provider-identity", encoding="utf-8")
    drift = cb_canon.status(root=tmp_path)
    assert drift["current"] is False
    assert any(item.get("owner") == "provider-identity"
               for item in drift["blockers"])


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
        "Zenny's crystal glows.\n\nSqueaky is caught by her tail.\n",
        policy,
    )

    assert report["ok"] is False
    assert {item["code"] for item in report["blockers"]} == {
        "SCRIPT_CANON_CONFLICT", "LOCKED_DIALOGUE_CONFLICT",
        "CHARACTER_PRONOUN_CONFLICT",
    }

    aligned = cb_canon.validate_script(
        "Aida steps forward. She waves. Squeaky watches her. He dips his head.\n",
        policy,
    )
    assert aligned["ok"] is True


def test_locked_dialogue_check_accepts_pdf_wrapped_numbered_lines(tmp_path):
    policy = _workspace(tmp_path)
    report = cb_canon.validate_script(
        "31 AIDA\n"
        "31    With heart open wide, I stand\n"
        "with pride — Rose Quartz, be our guide!\n",
        policy,
    )

    assert report["ok"] is True


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


def test_repository_ep1_human_canon_decisions_are_locked():
    report = cb_canon.status("Ep1", root=ROOT)
    characters = json.loads(
        (ROOT / "shows/crystal-bears/canon/characters.json").read_text(encoding="utf-8"))
    policy = json.loads(
        (ROOT / "shows/crystal-bears/canon/lock_policy.json").read_text(encoding="utf-8"))
    identity_packs = json.loads(
        (ROOT / "shows/crystal-bears/canon/identity_packs.json").read_text(
            encoding="utf-8"))
    script = (ROOT / report["scriptPath"]).read_text(encoding="utf-8")

    # A source-only checkout lacks operator media and must remain blocked. The live
    # production checkout may legitimately contain every signed asset and a fresh lock.
    if report["current"]:
        assert report["episodeReady"] is True
        assert report["blockers"] == []
    else:
        assert report["episodeReady"] is False
        assert any("missing" in str(item).lower() or "differs" in str(item).lower()
                   for item in report["blockers"])
    assert report["scriptCanon"]["ok"] is True
    locked_roster = {
        name for name, record in policy["roster"].items()
        if record.get("status") == "locked"
    }
    assert locked_roster <= set(identity_packs["characters"])
    assert characters["Squeaky"]["gender"] == "Male"
    assert characters["Luna"]["crystalCall"]["call"] == (
        "With quiet and might, I trust my sight — Lepidolite, reveal what’s right!"
    )
    assert characters["Luna"]["crystalCall"]["callStatus"] == "locked"
    luna_status = next(row for row in report["characters"] if row["name"] == "Luna")
    assert "Crystal Call is proposed and still needs human approval" not in luna_status["creativeGaps"]
    luna_contract = next(
        item for item in policy["scriptChecks"]["lockedDialogue"]
        if item["id"] == "Luna-crystal-call"
    )
    assert luna_contract["exactText"] == characters["Luna"]["crystalCall"]["call"]
    assert "With heart open wide, I stand with pride — Rose Quartz, be our guide!" in script
    assert "With open heart and love so bright" not in script
    assert "Zenny’s." not in script
    assert "Zenny's crystal" not in script
