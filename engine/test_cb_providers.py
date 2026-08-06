import json

import pytest

import cb_gen
import cb_providers


def test_registry_targets_25_and_retires_every_20_execution_route(monkeypatch):
    monkeypatch.delenv("CB_VIDEO_MODEL_ID", raising=False)
    registry = cb_providers.load_registry()

    target = cb_providers.video_model(require_enabled=False, registry=registry)
    legacy = cb_providers.video_model(
        "fal-seedance-2.0", require_enabled=False, registry=registry)

    assert target.modelId == "dreamina-seedance-2-5-260628"
    assert not target.enabled
    assert target.status == "qualification-required"
    assert target.transport == "byteplus-async"
    assert target.modes == [
        "reference-to-video", "video-extension", "video-editing"]
    assert target.verifiedAt == "2026-08-04"
    assert target.sourceUrl.endswith("/1520757")
    assert "has not activated the model" in target.disableReason
    assert "pricing" in target.disableReason.lower()
    assert not legacy.enabled and legacy.status == "retired"
    assert "never fall back" in legacy.disableReason
    with pytest.raises(cb_providers.ProviderCapabilityError, match="disabled"):
        cb_providers.video_model(registry=registry)


def test_disabled_or_unknown_selection_refuses_before_a_route_can_be_used(monkeypatch):
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "dreamina-seedance-2-5-260628")
    with pytest.raises(cb_providers.ProviderCapabilityError, match="disabled"):
        cb_providers.request_contract(duration=6, image_count=1)

    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "invented-model")
    with pytest.raises(cb_providers.ProviderCapabilityError, match="unknown"):
        cb_providers.request_contract(duration=6, image_count=1)


def test_retired_seedance_20_is_available_only_to_the_explicit_comparison_contract():
    with pytest.raises(cb_providers.ProviderCapabilityError, match="disabled"):
        cb_providers.request_contract(
            duration=15, resolution="720p", image_count=4, audio_count=1,
            model_id="fal-seedance-2.0")

    contract = cb_providers.comparison_request_contract(
        comparison_run_id="Ep1-S1-seedance-2.0-test", duration=15, resolution="720p",
        image_count=4, audio_count=1, model_id="fal-seedance-2.0")

    assert contract["providerModelId"] == "fal-seedance-2.0"
    assert contract["endpoint"] == "bytedance/seedance-2.0/reference-to-video"
    assert contract["comparisonRunId"] == "Ep1-S1-seedance-2.0-test"


@pytest.mark.parametrize("kwargs, match", [
    ({"model_id": "dreamina-seedance-2-5-260628"}, "only fal-seedance-2.0"),
    ({"duration": 16}, "4-15s"),
    ({"image_count": 10}, "at most 9"),
    ({"audio_count": 4}, "at most 3"),
])
def test_comparison_contract_remains_narrow(kwargs, match):
    request = {
        "comparison_run_id": "Ep1-S1-seedance-2.0-test",
        "duration": 15,
        "resolution": "720p",
        "image_count": 4,
        "audio_count": 1,
        "model_id": "fal-seedance-2.0",
    }
    request.update(kwargs)
    with pytest.raises(cb_providers.ProviderCapabilityError, match=match):
        cb_providers.comparison_request_contract(**request)


@pytest.mark.parametrize("kwargs, match", [
    ({"duration": 16, "image_count": 1}, "duration"),
    ({"duration": 6, "resolution": "4K", "image_count": 1}, "resolution"),
    ({"duration": 6, "image_count": 10}, "images"),
    ({"duration": 6, "image_count": 1, "audio_count": 4}, "audio"),
    ({"duration": 6, "image_count": 1, "video_count": 1}, "video"),
])
def test_request_contract_enforces_verified_limits(kwargs, match, monkeypatch):
    raw = json.loads(cb_providers.REGISTRY_PATH.read_text())
    raw["defaultVideoModelId"] = "fal-seedance-2.0"
    legacy = next(model for model in raw["models"]
                  if model["modelId"] == "fal-seedance-2.0")
    legacy.update({"enabled": True, "status": "production", "disableReason": None})
    registry = cb_providers.ProviderRegistry.model_validate(raw)
    monkeypatch.setattr(cb_providers, "load_registry", lambda path=None: registry)
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "fal-seedance-2.0")
    with pytest.raises(cb_providers.ProviderCapabilityError, match=match):
        cb_providers.request_contract(**kwargs)


def test_capability_report_is_zero_spend_and_secret_free(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "do-not-leak")
    report = cb_providers.capability_report()
    rendered = json.dumps(report)

    assert report["zeroSpend"] is True
    assert report["selectedVideoModelId"] == "dreamina-seedance-2-5-260628"
    assert report["selectionReady"] is False
    assert "not activated" in report["selectionError"]
    assert "do-not-leak" not in rendered


def test_retired_video_reference_fails_before_upload(monkeypatch):
    monkeypatch.setattr(cb_gen, "FAL_KEY", "test-key")
    uploads = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda path: uploads.append(path))

    with pytest.raises(cb_providers.ProviderCapabilityError, match="retired"):
        cb_gen.generate_video_seedance_ref(
            "motion", ["frame.png"], video_urls=["old-guide.mp4"],
            duration=6, production_route="cb_render")

    assert uploads == []


def test_already_uploaded_reference_url_is_not_uploaded_again(monkeypatch):
    uploads = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda path: uploads.append(path) or "uploaded")

    remote = "https://fal.media/files/reference.png"
    assert cb_gen._fal_asset_url(remote) == remote
    assert cb_gen._fal_asset_url("local.png") == "uploaded"
    assert uploads == ["local.png"]


def test_byteplus_25_adapter_builds_and_polls_the_official_async_contract(
        monkeypatch, tmp_path):
    image = tmp_path / "opening.png"
    audio = tmp_path / "voice.mp3"
    output = tmp_path / "result.mp4"
    image.write_bytes(b"PNG-reference")
    audio.write_bytes(b"MP3-reference")
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "test-key")

    requested = {}

    def contract(**kwargs):
        requested.update(kwargs)
        return {
            "providerModelId": "dreamina-seedance-2-5-260628",
            "provider": "byteplus",
            "modelVersion": "2.5-260628",
            "transport": "byteplus-async",
            "mode": "reference-to-video",
            "endpoint": "/api/v3/contents/generations/tasks",
            "resolution": "720p",
            "duration": 30,
            "costRateKey": "seedance_25_byteplus_per_sec",
            "capabilityVerifiedAt": "2026-08-04",
            "capabilitySource": "https://docs.byteplus.com/en/docs/modelark/1520757",
        }

    class Response:
        def __init__(self, payload=None, content=b""):
            self.payload = payload or {}
            self.content = content

        def json(self):
            return self.payload

    posted = {}

    def post(url, **kwargs):
        posted.update({"url": url, **kwargs})
        return Response({"id": "cgt-test-25"})

    polls = iter([
        {"id": "cgt-test-25", "status": "running"},
        {"id": "cgt-test-25", "status": "succeeded",
         "content": {"video_url": "https://media.example/result.mp4"},
         "duration": 30, "usage": {"completion_tokens": 123}},
    ])

    def get(url, **kwargs):
        if url == "https://media.example/result.mp4":
            return Response(content=b"MP4-result")
        return Response(next(polls))

    monkeypatch.setattr(cb_providers, "request_contract", contract)
    monkeypatch.setattr(cb_gen, "_rpost", post)
    monkeypatch.setattr(cb_gen, "_rget", get)
    monkeypatch.setattr(cb_gen.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(cb_gen.cb_costs, "estimate_video_cost", lambda key, seconds: 1.23)
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    result = cb_gen.generate_video_seedance_ref(
        "[Stage 1] Preserve the approved story.", [str(image)], [str(audio)],
        duration=30, out=str(output), raw_prompt=True, production_route="cb_render",
        model_id="dreamina-seedance-2-5-260628")

    assert result == str(output)
    assert output.read_bytes() == b"MP4-result"
    assert requested["model_id"] == "dreamina-seedance-2-5-260628"
    assert posted["url"].endswith("/api/v3/contents/generations/tasks")
    body = posted["json"]
    assert body["model"] == "dreamina-seedance-2-5-260628"
    assert body["duration"] == 30
    assert body["ratio"] == "16:9"
    assert body["content"][0] == {
        "type": "text", "text": "[Stage 1] Preserve the approved story."}
    assert body["content"][1]["role"] == "reference_image"
    assert body["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["content"][2]["role"] == "reference_audio"
    assert body["content"][2]["audio_url"]["url"].startswith("data:audio/mpeg;base64,")
