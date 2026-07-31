import cb_readback
import cb_render


def test_prompt_readback_uses_current_approved_prompt_and_never_generates(
        monkeypatch, tmp_path):
    frame = tmp_path / "opening.png"
    frame.write_bytes(b"approved-opening-frame")
    approved_prompt = "Fuzzby rebounds from the leaf and recovers his hover."
    package = {
        "episode": "Ep1",
        "sceneNumber": "1",
        "validation": {"passed": True},
        "shots": [{
            "shotId": "S1.SH1",
            "sourceType": "opener",
            "referenceSlots": {},
            "dialogueLines": [],
            "seedancePrompt": "This stale working prompt must never be used.",
            "purpose": "Land the boast-and-bounce joke.",
            "performanceAssignment": "Confidence survives one beat too long.",
            "visualPayoff": "The leaf keeps trembling after he says he meant it.",
        }],
        "continuityLedger": [{"shotId": "S1.SH1"}],
    }
    monkeypatch.setattr(
        cb_render, "load_pkg", lambda *args, **kwargs: (package, tmp_path / "pkg.json")
    )
    monkeypatch.setattr(cb_render, "_require_current_lineage", lambda *args: None)
    monkeypatch.setattr(cb_render, "_anchor_for", lambda *args: str(frame))
    work, _ = cb_render._department_container(
        package, "1", "S1.SH1", "animation", "Ep1")
    work["approved"] = {
        "output": {"providerPrompt": approved_prompt},
        "inputSignature": cb_render._department_input_signature(
            package, "animation", "S1.SH1", "1", "Ep1"),
    }

    captured = {}

    def fake_read_back(prompt, **kwargs):
        captured.update(prompt=prompt, **kwargs)
        return cb_readback.ReadBack(
            shot_says="Fuzzby bounces, recovers and lets the boast hang.",
            delivers="delivers",
            verdict="Fire it. The physical cause and reaction are clear.",
        )

    monkeypatch.setattr(cb_readback, "read_back", fake_read_back)
    result = cb_render.prompt_readback("1", "S1.SH1", "Ep1")

    assert result["available"] is True
    assert result["mediaProviderCalled"] is False
    assert result["result"]["delivers"] == "delivers"
    assert captured["prompt"] == approved_prompt
    assert captured["images"] == [str(frame)]
    assert "boast-and-bounce" in captured["intent"]
