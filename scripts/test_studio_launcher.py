import importlib.util
import json
import pathlib


SPEC = importlib.util.spec_from_file_location("studio_workstation_launcher", pathlib.Path(__file__).with_name("studio.py"))
LAUNCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAUNCHER)


def test_doctor_never_discloses_credentials(monkeypatch):
    secret = "private-test-value-do-not-disclose"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    report = LAUNCHER.doctor()
    assert report["providerKeysPresent"]["OPENAI_API_KEY"] is True
    assert secret not in json.dumps(report)
    assert report["zeroSpend"] is True
    assert report["productionQualified"] is False


def test_missing_dependency_refuses_workstation_ready(monkeypatch):
    monkeypatch.setattr(LAUNCHER, "locked_versions", lambda: {"absent-test-package": "1.0"})
    report = LAUNCHER.doctor()
    assert report["workstationReady"] is False
    dependencies = next(row for row in report["checks"] if row["name"] == "dependencies")
    assert dependencies["ready"] is False


def test_missing_show_cannot_be_reported_ready():
    report = LAUNCHER.doctor("nonexistent-production")
    assert report["workstationReady"] is False
    assert report["show"] is None


def test_config_is_literal_and_environment_takes_precedence(monkeypatch, tmp_path):
    config = tmp_path / "engine/.env"
    config.parent.mkdir()
    config.write_text("OPENAI_API_KEY=file-value\nSTUDIO_LITERAL=$(touch never-run)\n")
    monkeypatch.setenv("OPENAI_API_KEY", "environment-value")
    monkeypatch.delenv("STUDIO_LITERAL", raising=False)
    LAUNCHER.load_configuration(tmp_path)
    assert LAUNCHER.os.environ["OPENAI_API_KEY"] == "environment-value"
    assert LAUNCHER.os.environ["STUDIO_LITERAL"] == "$(touch never-run)"
    monkeypatch.delenv("STUDIO_LITERAL")
