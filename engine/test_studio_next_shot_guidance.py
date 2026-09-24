from contextlib import contextmanager
from copy import deepcopy

from studio_next_shot_guidance import Recommendation, recommend


def _records(transition="cut"):
    current_id = "S4.SH3"
    next_shot = {
        "shotId": "S4.SH4",
        "purpose": "Sunny performs the forced dance.",
        "openingPose": "Sunny grips honey-stuck Fuzzby.",
        "camera": "Keep the slide path and cushion impact readable.",
        "sourceType": "opener" if transition == "cut" else "relay",
        "sourceShotId": None if transition == "cut" else current_id,
        "shotTransition": {
            "type": transition,
            "stateSourceShotId": current_id,
            "reason": "The key event is Sunny choosing forced fun.",
            "openingImage": "Sunny grips honey-stuck Fuzzby in the party space.",
            "camera": "Hold the slide path and cushion impact readable.",
        },
    }
    current = {
        "shotId": current_id,
        "purpose": "Sunny chooses to keep the party going.",
        "visualPayoff": "Sunny looks to the watching friends.",
        "continuityOut": "The party decorations remain wet.",
    }
    package = {
        "revision": 3,
        "shots": [current, next_shot],
        "continuityLedger": [],
    }
    ledger = {
        "shotId": current_id,
        "status": "approved",
        "approvedTake": "approved.mp4",
        "harvestFrame": "approved-final.png",
        "approval": {"packageRevision": 3, "inputSignature": {"signed": True}},
    }
    return package, current, next_shot, ledger


def _install(monkeypatch, package, current, ledger, answer=None):
    import studio_journey_native
    import cb_director_chat
    import cb_episode_budget
    import cb_llm

    monkeypatch.setattr(studio_journey_native, "read",
                        lambda root, scope: (package, {}, current, ledger))
    monkeypatch.setattr(cb_director_chat, "CHAT_MODEL", "gpt-6-luna")
    calls = []
    monkeypatch.setattr(cb_llm, "structured", lambda *args, **kwargs: calls.append((args, kwargs)) or answer)

    @contextmanager
    def quote(*args, **kwargs):
        yield

    monkeypatch.setattr(cb_episode_budget, "quote", quote)
    return calls


def _scope():
    return {"projectId": "crystal-bears", "episode": "Ep4", "scene": "4", "unit": "S4.SH3"}


def test_cut_recommendation_is_bound_to_card_and_does_not_mutate_package(monkeypatch):
    package, current, _next, ledger = _records("cut")
    original = deepcopy(package)
    calls = _install(monkeypatch, package, current, ledger,
                     Recommendation(mode="hard-cut", why="The new directed opening changes the view."))

    result = recommend(type("Server", (), {"ROOT": "."})(), _scope())

    assert result["mode"] == "hard-cut"
    assert result["source"] == "Luna · approved direction"
    assert result["textOnly"] is True
    assert len(calls) == 1
    assert calls[0][1]["model"] == "gpt-6-luna"
    assert calls[0][1]["max_output_tokens"] == 120
    assert "Do not change it" in calls[0][0][0]
    assert package == original


def test_exact_relay_keeps_previous_approved_frame(monkeypatch):
    package, current, _next, ledger = _records("continuation")
    _install(monkeypatch, package, current, ledger,
             Recommendation(mode="exact-frame-relay", why="The approved frame already starts this action."))

    result = recommend(type("Server", (), {"ROOT": "."})(), _scope())

    assert result["mode"] == "exact-frame-relay"
    assert "exact approved final frame" in result["label"]


def test_stale_approval_routes_to_watch_without_calling_luna(monkeypatch):
    package, current, _next, ledger = _records("cut")
    ledger["approval"]["packageRevision"] = 2
    calls = _install(monkeypatch, package, current, ledger)

    result = recommend(type("Server", (), {"ROOT": "."})(), _scope())

    assert result["ready"] is False
    assert result["mode"] == "review-see"
    assert result["source"] == "Studio approval check"
    assert not calls


def test_luna_cannot_override_the_signed_transition(monkeypatch):
    package, current, _next, ledger = _records("cut")
    _install(monkeypatch, package, current, ledger,
             Recommendation(mode="exact-frame-relay", why="Use the old image."))

    result = recommend(type("Server", (), {"ROOT": "."})(), _scope())

    assert result["mode"] == "hard-cut"
    assert result["source"] == "Approved Director Card"
    assert "Hard cut" in result["reason"]


def test_unbound_transition_opens_see_for_review_without_model_call(monkeypatch):
    package, current, next_shot, ledger = _records("cut")
    next_shot["shotTransition"]["stateSourceShotId"] = "S4.SH1"
    calls = _install(monkeypatch, package, current, ledger)

    result = recommend(type("Server", (), {"ROOT": "."})(), _scope())

    assert result["mode"] == "review-see"
    assert result["ready"] is True
    assert "does not name S4.SH3" in result["reason"]
    assert not calls


def test_production_journey_exposes_guidance_action(monkeypatch):
    import studio_journey_http
    import studio_next_shot_guidance

    expected = {"mode": "hard-cut", "ready": True}
    monkeypatch.setattr(studio_next_shot_guidance, "recommend",
                        lambda server, scope: expected)
    server = type("Server", (), {"ROOT": "."})()

    result = studio_journey_http.request(
        server, {"scope": _scope(), "command": "next-shot-guidance"})

    assert result == {"ok": True, "guidance": expected}
