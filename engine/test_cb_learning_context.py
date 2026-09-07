import concurrent.futures
import json
from types import SimpleNamespace
from pathlib import Path

import pytest

import cb_learning as L
import cb_learning_context as C
import cb_transactions as T


def evidence(scene="1", shot="S1.SH1", feedback="Let the listener register the surprise.", **kwargs):
    return L.capture_evidence("rejected", feedback, episode="Ep3", scene=scene, shot=shot,
                              context=json.dumps({"characters": ["Keen"]}), **kwargs)


def test_relevant_feedback_reaches_later_scene_but_is_not_a_rule():
    row = evidence()
    context = {"episode": "Ep3", "scene": "2", "shot": {
        "shotId": "S2.SH1", "charactersInFrame": ["Keen"]}}
    assert C.observations(context)[0]["evidenceId"] == row["evidenceId"]
    assert C.observations(context)[0]["relevance"] == "shared-cast"
    assert "not canon" in C.brief(context)
    context["episode"] = "Ep4"
    assert C.observations(context) == []


def test_empty_verdicts_provider_faults_and_unrelated_cast_do_not_become_lessons():
    evidence(feedback="")
    evidence(feedback="Provider timed out", category="technical")
    evidence()
    assert C.observations({"episode": "Ep3", "scene": "2",
                           "characters": ["Zenny"]}) == []


def test_conflicting_observations_are_preserved_and_context_does_not_leak():
    evidence(feedback="More room for the reaction.")
    evidence(feedback="The reaction was too long.")
    import cb_creative
    with C.scene_scope("Ep3", "1", ["Keen"]):
        mind = cb_creative._mind("DIRECTOR", [], "fixture")
        assert "More room for the reaction." in mind
        assert "The reaction was too long." in mind
    assert "More room for the reaction." not in cb_creative._mind("DIRECTOR", [], "fixture")


def test_department_receives_observations_without_mutating_input(monkeypatch):
    row = evidence()
    import cb_departments as D
    captured = []
    monkeypatch.setattr(D.cb_llm, "structured", lambda *args, **kwargs: captured.append(args) or {})
    context = {"episode": "Ep3", "scene": "1"}
    D.prepare_look(context)
    assert row["evidenceId"] in captured[0][1]
    assert "reviewObservations" not in context


def test_concurrent_capture_is_atomic_and_retries_do_not_duplicate():
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda index: evidence(feedback=str(index), decisionKey=str(index)), range(20)))
    evidence(decisionKey="1")
    assert len(L.evidence()) == 20


def test_successful_media_decision_records_evidence_failed_decision_does_not(tmp_path):
    state = {"revision": 1, "shots": [{"shotId": "S1.SH1", "charactersInFrame": ["Keen"]}],
             "ledger": {"candidatePaths": ["fixture.mp4"]}}
    module = SimpleNamespace(HERE=tmp_path / "engine", Refused=RuntimeError,
        load_pkg=lambda *args: (json.loads(json.dumps(state)), Path("unused")),
        _shot=lambda pkg, sid: pkg["shots"][0], _ledger=lambda pkg, sid: pkg["ledger"])
    def reject_shot(scene, shot_id, correction, episode="Ep3", reviewed_by="Julian", log=print):
        if correction == "fail":
            raise RuntimeError("fixture failure")
        state["ledger"]["status"] = "rejected"
        return True
    wrapped = T.protect(module, "reject_shot", reject_shot)
    assert wrapped("1", "S1.SH1", "Let the reaction read.")
    wrapped("1", "S1.SH1", "Let the reaction read.")
    assert len(L.evidence()) == 1
    assert L.evidence()[0]["userFeedbackVerbatim"] == "Let the reaction read."
    with pytest.raises(RuntimeError):
        wrapped("1", "S1.SH1", "fail")
    assert len(L.evidence()) == 1
