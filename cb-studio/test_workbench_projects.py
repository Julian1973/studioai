"""Workbench notes must follow the selected production without crossing shows."""
import importlib.util
import pathlib
from types import SimpleNamespace


def test_selected_show_notes_are_isolated_and_survive_reopen(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "studio_workbench_projects_test", pathlib.Path(__file__).with_name("serve.py"))
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)
    monkeypatch.setattr(server, "WORKBENCH_STATE_FILE", tmp_path / "workbench.json")
    monkeypatch.setattr(server, "ACTIVE_SHOW", SimpleNamespace(
        profile=SimpleNamespace(showId="new-production")))

    fresh = server._project_workbench_state()
    assert fresh["project"] == "new-production"
    assert fresh["activeBeatId"] is None
    server._save_project_workbench_state({
        "retakeNotes": {"S1.SH1:2": "A quieter performance"},
        "activeBeatId": "arrival",
    })
    server._save_project_workbench_state({
        "project": "crystal-bears",
        "retakeNotes": {"S1.SH1:2": "Preserve the comedy"},
    })

    reopened = server._project_workbench_state()
    assert reopened["activeBeatId"] == "arrival"
    assert reopened["retakeNotes"]["S1.SH1:2"] == "A quieter performance"
    assert server._project_workbench_state("crystal-bears")["retakeNotes"]["S1.SH1:2"] == "Preserve the comedy"
