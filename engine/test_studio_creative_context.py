"""Local-only source selection proofs. No model or media provider is invoked."""
import hashlib
import json
from pathlib import Path

import pytest

from studio_creative_context import build_context, bind_context, receipt, project_id


ROOT = Path(__file__).resolve().parent.parent
PRIVATE_SOURCES_AVAILABLE = (ROOT / 'shows/crystal-bears/creative/creative_sources.json').is_file()
private_sources = pytest.mark.skipif(
    not PRIVATE_SOURCES_AVAILABLE, reason='Private show-bible sources are not distributed with the public repository')


def manifest(tmp_path, pid="first"):
    base = tmp_path / "projects" / pid
    base.mkdir(parents=True)
    (base / "show_bible.md").write_text(f"Only {pid} characters and world.")
    (base / "craft.md").write_text("## Opening\nRead the hand and contact surface.\n\n## Movement\nFollow the witness after the impact.\n")
    data = {"schemaVersion": 1, "projectId": pid, "sources": [
        {"id": "opening", "path": f"projects/{pid}/craft.md", "stages": ["see"],
         "authority": "craft-guidance", "selector": {"heading": "## Opening"}},
        {"id": "movement", "path": f"projects/{pid}/craft.md", "stages": ["watch"],
         "authority": "craft-guidance", "selector": {"heading": "## Movement"}}]}
    path = base / "creative_sources.json"
    path.write_text(json.dumps(data))
    return path, data


@private_sources
def test_existing_bible_and_professional_craft_have_real_selected_material():
    bundle = build_context("crystal-bears", "see", root=ROOT)
    rows = {row["id"]: row for row in bundle["sources"]}
    assert "Power does not" in rows["final-bible-promise"]["text"]
    assert "sincere attempt" in rows["compass-humour"]["text"]
    assert "small observable choice" in rows["compass-emotion"]["text"]
    assert "clear silhouettes" in rows["compass-cinema"]["text"]
    assert "character state and camera behaviour" in rows["stover-camera-consciousness"]["text"]
    assert "camera must preserve the body part" in rows["stover-performance-camera"]["text"]
    assert rows["final-bible-promise"]["provenance"]["driveFileId"] == "1VygMCPRQLwcW4UyJ1Xw-FMQgNTAwmsUm"
    assert rows["locked-show-identity"]["authority"] == "locked-canon"
    assert rows["final-bible-promise"]["authority"] == "reference-context"
    assert "do not supersede" in bundle["authorityPolicy"]
    for row in rows.values():
        assert row["sourceSha256"] == hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest()
        assert row["contentSha256"] == hashlib.sha256(row["text"].encode()).hexdigest()


@private_sources
def test_receipt_records_exact_local_selection_without_copying_source_text():
    bundle = build_context("crystal-bears", "cinematography", root=ROOT)
    saved = receipt(bundle)
    assert saved["stage"] == "see"
    assert saved["fingerprint"] == bundle["fingerprint"]
    assert len(saved["sources"]) == len(bundle["sources"])
    assert all("text" not in row for row in saved["sources"])
    assert "sourceSha256" in saved["sources"][0]


def test_watch_only_edit_preserves_see_dependency_and_changes_watch(tmp_path):
    manifest(tmp_path)
    before_see = build_context("first", "see", root=tmp_path)
    before_watch = build_context("first", "watch", root=tmp_path)
    path = tmp_path / "projects/first/craft.md"
    path.write_text(path.read_text().replace("after the impact", "after the witness discovers the result"))
    after_see = build_context("first", "see", root=tmp_path)
    after_watch = build_context("first", "watch", root=tmp_path)
    assert before_see["fingerprint"] == after_see["fingerprint"]
    assert before_watch["fingerprint"] != after_watch["fingerprint"]
    assert before_see["sources"][1]["sourceSha256"] != after_see["sources"][1]["sourceSha256"]
    assert before_see["sources"][1]["contentSha256"] == after_see["sources"][1]["contentSha256"]


def test_refreshed_original_hash_and_dates_are_audit_only_but_source_identity_is_bound(tmp_path):
    path, data = manifest(tmp_path)
    row = data['sources'][0]
    row['provenance'] = {'originalSha256': 'old-original-hash', 'modifiedTime': 'old-time',
                         'retrievedDate': 'old-date', 'driveFileId': 'approved-source-id'}
    path.write_text(json.dumps(data))
    before = build_context('first', 'see', root=tmp_path)
    row['provenance'].update(originalSha256='watch-only-document-update',
                             modifiedTime='new-time', retrievedDate='new-date')
    path.write_text(json.dumps(data))
    refreshed = build_context('first', 'see', root=tmp_path)
    assert before['fingerprint'] == refreshed['fingerprint']
    assert before['sources'][1]['contentSha256'] == refreshed['sources'][1]['contentSha256']
    assert receipt(before) != receipt(refreshed)
    row['provenance']['driveFileId'] = 'different-source-id'
    path.write_text(json.dumps(data))
    assert build_context('first', 'see', root=tmp_path)['fingerprint'] != before['fingerprint']


def test_current_project_never_inherits_crystal_bears_or_other_project(tmp_path):
    manifest(tmp_path, "first")
    manifest(tmp_path, "second")
    bundle = bind_context({"project": {"id": "second"}}, "see", root=tmp_path)["creativeAuthority"]
    assert bundle["projectId"] == "second"
    assert all(row["path"].startswith("projects/second/") for row in bundle["sources"])
    assert "Crystal Bears" not in json.dumps(bundle)
    assert "Only first" not in json.dumps(bundle)
    with pytest.raises(ValueError, match="scope disagrees"):
        project_id({"project": {"id": "second"}, "projectId": "crystal-bears"})


@pytest.mark.parametrize("target", ["projects/second/show_bible.md", "shows/crystal-bears/canon/LOCKED_CANON.md", "/etc/passwd", "../../outside.md"])
def test_manifest_cannot_escape_its_project(tmp_path, target):
    path, data = manifest(tmp_path)
    data["sources"][0]["path"] = target
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escapes"):
        build_context("first", "see", root=tmp_path)


def test_missing_required_source_is_visible_and_long_text_is_not_silently_cut(tmp_path):
    path, data = manifest(tmp_path)
    data["sources"][0]["selector"]["heading"] = "## Deleted source"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="heading is missing"):
        build_context("first", "see", root=tmp_path)
    (tmp_path / "projects/first/show_bible.md").write_text("x" * 14001)
    with pytest.raises(ValueError, match="narrower explicit section"):
        build_context("first", "watch", root=tmp_path)


def test_project_folder_and_manifest_symlinks_cannot_alias_another_tenant(tmp_path):
    manifest(tmp_path, "second")
    (tmp_path / "projects/first").symlink_to(tmp_path / "projects/second", target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        build_context("first", "see", root=tmp_path)


@private_sources
def test_only_production_excerpts_are_selected_not_financial_or_licensing_pages():
    for stage in ("story", "see", "hear", "watch", "review", "post"):
        bundle = build_context("crystal-bears", stage, root=ROOT)
        text = "\n".join(row["text"] for row in bundle["sources"])
        assert "CONFIDENTIAL / ENAID CREATIVE" not in text
        assert "LICENSING & EVERYDAY CONNECTION" not in text
        assert "QA scorecard" not in text
        assert len(text) < 28000
