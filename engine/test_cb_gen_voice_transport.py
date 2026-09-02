import base64

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


def test_eleven_tts_uses_ada_pronunciation_without_changing_canon(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "sk_test_key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(
        cb_gen, "_rpost",
        lambda *args, **kwargs: calls.append(kwargs["json"]) or _Response())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    canonical = "Bo, this is Aida."
    cb_gen.eleven_tts(
        canonical, "voice-id", out="take.mp3", production_route="cb_render")

    assert calls[0]["text"] == "Bo, this is ada."
    assert canonical == "Bo, this is Aida."


def test_eleven_dialogue_uses_ada_pronunciation_for_every_turn(monkeypatch, tmp_path):
    calls = []

    class DialogueResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "audio_base64": base64.b64encode(b"MP3").decode(),
                "voice_segments": [{
                    "voice_id": "voice-id", "dialogue_input_index": 0,
                    "start_time_seconds": 0.0, "end_time_seconds": 1.0,
                    "character_start_index": 0, "character_end_index": 16,
                }],
                "alignment": None,
                "normalized_alignment": None,
            }

    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "sk_test_key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(
        cb_gen, "_rpost",
        lambda *args, **kwargs: calls.append(kwargs["json"]) or DialogueResponse())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    canonical = [{"text": "This is Aida.", "voice_id": "voice-id"}]
    cb_gen.eleven_dialogue(
        canonical, out="dialogue.mp3", production_route="cb_render")

    assert calls[0]["inputs"][0]["text"] == "This is ada."
    assert canonical[0]["text"] == "This is Aida."
