import hashlib
import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
AUDIT_PATH = ROOT / "engine" / "grammar" / "sd25_pe_audit.json"
GRAMMAR_PATH = ROOT / "engine" / "grammar_pack.json"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sd25_skill_is_a_pinned_checker_not_a_prompt_writer():
    audit = json.loads(AUDIT_PATH.read_text())
    vendor = audit["vendor"]
    snapshot = ROOT / vendor["snapshotPath"]
    source = snapshot.read_text()

    assert audit["architectureRuling"] == "director-source-deterministic-compilers-only"
    assert audit["role"] == "checker-and-rule-source-only"
    assert audit["productionPromptWriter"] is False
    assert _sha256(snapshot) == vendor["snapshotSha256"]
    assert re.search(
        rf"(?m)^\s*skill_version:\s*{re.escape(vendor['version'])}\s*$", source)


def test_sd25_audit_must_be_redone_for_grammar_or_vendor_change():
    audit = json.loads(AUDIT_PATH.read_text())
    grammar = json.loads(GRAMMAR_PATH.read_text())

    assert audit["auditedGrammarPackVersion"] == grammar["version"]
    assert set(audit["rerunTriggers"]) == {
        "grammar-pack-version-bump",
        "vendored-skill-version-change",
        "vendored-skill-hash-change",
    }
    assert set(audit["emissionPaths"]) == {"keyframe", "render", "voice"}
    assert audit["findings"]
    for finding in audit["findings"]:
        assert finding["disposition"] in {"implemented", "not-applicable", "open"}
        assert finding.get("compilerRule")
        assert finding.get("tests")
        for test_path in finding["tests"]:
            assert (ROOT / test_path).exists()


def test_production_emitters_do_not_load_or_execute_sd25_skill():
    forbidden = (".agents/skills/sd25-pe", "skills@latest", "sd25_pe_audit.json")
    production_emitters = (
        "engine/cb_departments.py",
        "engine/cb_emission_conformance.py",
        "engine/cb_render.py",
        "engine/cb_safety.py",
        "engine/cb_voice_director.py",
    )
    for relative in production_emitters:
        source = (ROOT / relative).read_text()
        assert not any(token in source for token in forbidden), relative
