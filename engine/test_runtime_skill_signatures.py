import hashlib
import json
import subprocess

import cb_departments
import migrate_runtime_skill_signatures as migration
import studio_prompt_structure


def test_runtime_signature_ignores_documentation_but_tracks_contract_edits():
    base = """---\ntitle: worker\n---\n<!-- notes -->\nold docs\n<!-- RUNTIME_WORKER_START -->\nDo the work.\n<!-- RUNTIME_WORKER_END -->\nmore docs\n"""
    docs_changed = base.replace("old docs", "new docs and comments")
    contract_changed = base.replace("Do the work.", "Do the revised work.")

    original = cb_departments.runtime_skill_sha256("voice", base)
    assert cb_departments.runtime_skill_sha256("voice", docs_changed) == original
    assert cb_departments.runtime_skill_sha256("voice", contract_changed) != original
    assert cb_departments.runtime_skill_sha256("voice") == hashlib.sha256(
        cb_departments.load_runtime_skill("voice").encode("utf-8")
    ).hexdigest()


def test_animation_signature_includes_executed_writing_brief(monkeypatch):
    monkeypatch.setattr(studio_prompt_structure, "WRITING_BRIEF", "brief one")
    first = cb_departments.runtime_skill_sha256("animation")
    assert first == hashlib.sha256(
        cb_departments.load_runtime_skill("animation").encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr(studio_prompt_structure, "WRITING_BRIEF", "brief two")
    assert cb_departments.runtime_skill_sha256("animation") != first


def test_signature_fallback_hashes_whole_file_without_readable_markers():
    source = "legacy worker instructions"
    standard = (cb_departments.ROOT / "skills/production-standard.md").read_text().strip()
    prompt = standard + "\n\n" + source
    assert cb_departments.runtime_skill_sha256("voice", source) == hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()


def test_restamp_records_time_reason_and_old_hashes_without_changing_output():
    record = {"output": {"words": ["Approved."]}, "inputSignature": {
        "skillHashes": {"voice": "old-hash"}}}
    before = json.loads(json.dumps(record["output"]))
    migration.restamp_record(record, {"voice": "new-hash"}, "2026-09-24T00:00:00+00:00")
    assert record["signatureMigration"] == {
        "migratedAt": "2026-09-24T00:00:00+00:00",
        "reason": migration.MIGRATION_REASON,
        "previousSkillHashes": {"voice": "old-hash"},
    }
    assert record["output"] == before


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, check=True,
                          capture_output=True, text=True)


def test_migration_only_restamps_unchanged_executable_contract(tmp_path, monkeypatch):
    repo = tmp_path
    skill = repo / "skills" / "voice" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    original = "<!-- notes -->\nold docs\n<!-- RUNTIME_WORKER_START -->\nSpeak clearly.\n<!-- RUNTIME_WORKER_END -->\n"
    skill.write_text(original, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Migration Test")
    _git(repo, "add", "skills/voice/SKILL.md")
    _git(repo, "commit", "-qm", "original skill")
    monkeypatch.setitem(cb_departments.SKILLS, "voice", skill)

    package_dir = repo / "cb-output"
    package_dir.mkdir()
    package_path = package_dir / "sample_production_package.json"
    package = {"continuityLedger": [{"shotId": "S1.SH1", "departmentWork": {
        "voice": {"approved": {"output": {"lines": ["Approved words."]},
            "inputSignature": {"stage": "voice", "skillHashes": {
                "voice": hashlib.sha256(original.encode()).hexdigest()}}}}}}]}
    package_path.write_text(json.dumps(package), encoding="utf-8")

    skill.write_text(original.replace("old docs", "edited docs"), encoding="utf-8")
    _git(repo, "add", "skills/voice/SKILL.md")
    _git(repo, "commit", "-qm", "documentation-only edit")
    plan, counts = migration.build_plan(repo=repo, package_dir=package_dir)
    assert counts["eligible"] == 1
    assert sum(len(item["edits"]) for item in plan.values()) == 1
    saved = json.loads(package_path.read_text())
    assert saved["continuityLedger"][0]["departmentWork"]["voice"]["approved"][
        "output"] == {"lines": ["Approved words."]}

    skill.write_text(skill.read_text().replace("Speak clearly.", "Whisper softly."),
                     encoding="utf-8")
    _git(repo, "add", "skills/voice/SKILL.md")
    _git(repo, "commit", "-qm", "runtime contract edit")
    plan, counts = migration.build_plan(repo=repo, package_dir=package_dir)
    assert counts["runtime_changed"] == 1
    assert not plan
