import cb_gen


class _Response:
    content = b"audio"

    def raise_for_status(self):
        return None


def _run(monkeypatch, tmp_path, model_id):
    calls = []
    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "sk_test_key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(
        cb_gen, "_rpost",
        lambda *args, **kwargs: calls.append(kwargs["json"]) or _Response())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)
    cb_gen.eleven_tts(
        "[confident] Nailed it.", "voice-id", model_id=model_id,
        previous_text="BIZZY-BIZZY-BIZZY...", out="take.mp3",
        production_route="cb_render")
    return calls[0]


def test_eleven_v3_transport_omits_unsupported_previous_text(monkeypatch, tmp_path):
    body = _run(monkeypatch, tmp_path, "eleven_v3")
    assert "previous_text" not in body


def test_compatible_eleven_transport_keeps_previous_text(monkeypatch, tmp_path):
    body = _run(monkeypatch, tmp_path, "eleven_multilingual_v2")
    assert body["previous_text"] == "BIZZY-BIZZY-BIZZY..."
