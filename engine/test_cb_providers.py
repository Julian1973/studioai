import json
import hashlib
import pathlib

import pytest

import cb_gen
import cb_providers


def test_crystal_bears_production_images_are_locked_to_seedream_5_pro(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cb_gen, "_generate_image_seedream",
        lambda prompt, refs, aspect, out, image_size: calls.append(
            (prompt, refs, aspect, out, image_size)) or out)

    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "seedream")
    assert cb_gen.generate_image(
        "approved SEE", refs=["fuzzby.png"], out="see.png",
        production_route="cb_render") == "see.png"
    assert calls == [("approved SEE", ["fuzzby.png"], "16:9", "see.png", "2K")]

    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "nanobanana")
    with pytest.raises(RuntimeError, match="locked to Seedream 5 Pro"):
        cb_gen.generate_image(
            "approved SEE", refs=["fuzzby.png"], out="see.png",
            production_route="cb_render")

    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "seedream")
    with pytest.raises(RuntimeError, match="model overrides"):
        cb_gen.generate_image(
            "approved SEE", refs=["fuzzby.png"], out="see.png",
            model="gemini-3.1-flash-image", production_route="cb_render")


def test_seedream_5_pro_uses_official_modelark_contract(monkeypatch, tmp_path):
    fuzzby = tmp_path / "fuzzby.png"
    zenny = tmp_path / "zenny.png"
    output = tmp_path / "see.png"
    fuzzby.write_bytes(b"fuzzby")
    zenny.write_bytes(b"zenny")
    submitted = {}

    class JsonResponse:
        def json(self):
            return {"data": [{"url": "https://modelark.example/result.png"}]}

    class ImageResponse:
        content = b"seedream-image"

    def post(url, **kwargs):
        submitted.update(url=url, **kwargs)
        return JsonResponse()

    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "test-modelark-key")
    monkeypatch.setattr(cb_gen, "_rpost", post)
    monkeypatch.setattr(cb_gen, "_rget", lambda *args, **kwargs: ImageResponse())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    result = cb_gen._generate_image_seedream(
        "Approved production brief.", [str(fuzzby), str(zenny)],
        out=str(output), image_size="2K")

    assert result == str(output)
    assert output.read_bytes() == b"seedream-image"
    assert submitted["url"] == (
        "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations")
    assert submitted["headers"]["Authorization"] == "Bearer test-modelark-key"
    body = submitted["json"]
    assert body["model"] == "dola-seedream-5-0-pro-260628"
    assert body["size"] == "2K"
    assert body["output_format"] == "png"
    assert body["response_format"] == "url"
    assert body["optimize_prompt_options"] == {"mode": "standard"}
    assert body["watermark"] is False
    assert len(body["image"]) == 2
    assert all(value.startswith("data:image/png;base64,") for value in body["image"])
    assert "batch" not in body and "sequential_image_generation" not in body


def test_seedream_5_pro_refuses_more_than_ten_references(monkeypatch):
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "test-modelark-key")
    with pytest.raises(ValueError, match="at most 10"):
        cb_gen._generate_image_seedream("prompt", ["ref.png"] * 11)


def test_registry_targets_live_byteplus_25_and_retires_every_20_execution_route(monkeypatch):
    monkeypatch.delenv("CB_VIDEO_MODEL_ID", raising=False)
    registry = cb_providers.load_registry()

    target = cb_providers.video_model(require_enabled=False, registry=registry)
    legacy = cb_providers.video_model(
        "fal-seedance-2.0", require_enabled=False, registry=registry)

    assert target.modelId == "dreamina-seedance-2-5-260628"
    assert target.enabled
    assert target.status == "production"
    assert target.transport == "byteplus-async"
    assert target.modes == ["reference-to-video", "video-extension", "video-editing"]
    assert target.endpoints["reference-to-video"] == (
        "/api/v3/contents/generations/tasks")
    assert target.duration.maxSec == 30
    assert target.referenceLimits.images == 30
    assert target.referenceLimits.audio == 10
    assert target.verifiedAt == "2026-08-16"
    assert "byteplus.com" in target.sourceUrl
    assert target.disableReason is None
    assert not legacy.enabled and legacy.status == "retired"
    assert "never fall back" in legacy.disableReason
    assert cb_providers.video_model(registry=registry).modelId == (
        "dreamina-seedance-2-5-260628")


def test_disabled_or_unknown_selection_refuses_before_a_route_can_be_used(monkeypatch):
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "byteplus-seedance-2.0")
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
    assert report["selectionReady"] is True
    assert report["selectionError"] is None
    assert "do-not-leak" not in rendered


def test_fal_25_contract_enforces_live_limits():
    contract = cb_providers.request_contract(
        duration=29, resolution="720p", image_count=4, audio_count=1,
        model_id="fal-seedance-2.5")
    assert contract["providerModelId"] == "fal-seedance-2.5"
    assert contract["endpoint"] == "bytedance/seedance-2.5/reference-to-video"
    assert contract["costRateKey"] == "seedance_25_fal_720p_per_sec"

    review_contract = cb_providers.request_contract(
        duration=29, resolution="480p", image_count=4, audio_count=1,
        model_id="fal-seedance-2.5")
    assert review_contract["costRateKey"] == "seedance_25_fal_480p_per_sec"

    with pytest.raises(cb_providers.ProviderCapabilityError, match="4-30s"):
        cb_providers.request_contract(
            duration=31, image_count=1, model_id="fal-seedance-2.5")
    with pytest.raises(cb_providers.ProviderCapabilityError, match="at most 30"):
        cb_providers.request_contract(
            duration=10, image_count=31, model_id="fal-seedance-2.5")


def test_fal_25_refuses_unverified_video_extension_route(monkeypatch, tmp_path):
    image = tmp_path / "frame.png"
    video = tmp_path / "previous.mp4"
    output = tmp_path / "candidate.mp4"
    image.write_bytes(b"image")
    video.write_bytes(b"video-ref")
    monkeypatch.setattr(cb_gen, "FAL_KEY", "test-key")
    uploads = []
    monkeypatch.setattr(
        cb_gen, "_fal_asset_url",
        lambda path: uploads.append(path) or f"https://fal.media/{len(uploads)}")
    submitted = {}

    def subscribe(endpoint, arguments=None, with_logs=False):
        submitted.update({"endpoint": endpoint, "arguments": arguments})
        return {"video": {"url": "https://fal.media/out.mp4"}}

    class Response:
        content = b"render"

    monkeypatch.setattr(cb_gen, "_fal_subscribe", subscribe)
    monkeypatch.setattr(cb_gen, "_rget", lambda *args, **kwargs: Response())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    with pytest.raises(cb_providers.ProviderCapabilityError,
                       match="does not have a verified video-extension route"):
        cb_gen.generate_video_seedance_ref(
            "Continue from @Video1.", [str(image)], video_urls=[str(video)],
            duration=6, out=str(output), raw_prompt=True,
            production_route="cb_render", model_id="fal-seedance-2.5")

    assert submitted == {}
    assert uploads == []


def test_byteplus_25_contract_qualifies_video_extension():
    contract = cb_providers.request_contract(
        mode="video-extension", duration=30, resolution="480p",
        image_count=13, audio_count=1, video_count=1,
        model_id="dreamina-seedance-2-5-260628")

    assert contract["mode"] == "video-extension"
    assert contract["endpoint"] == "/api/v3/contents/generations/tasks"
    assert contract["costRateKey"] == "seedance_25_byteplus_480p_per_sec"


def test_byteplus_25_contract_qualifies_native_video_editing():
    contract = cb_providers.request_contract(
        mode="video-editing", duration=24, resolution="480p",
        image_count=0, audio_count=1, video_count=1,
        model_id="dreamina-seedance-2-5-260628")

    assert contract["mode"] == "video-editing"
    assert contract["endpoint"] == "/api/v3/contents/generations/tasks"
    assert contract["costRateKey"] == "seedance_25_byteplus_480p_per_sec"


def test_video_editing_requires_an_existing_video():
    with pytest.raises(cb_providers.ProviderCapabilityError, match="requires an existing video"):
        cb_gen.generate_video_seedance_ref(
            "Strictly edit @Video1.", [], duration=24, resolution="480p",
            raw_prompt=True, production_route="cb_render",
            model_id="dreamina-seedance-2-5-260628",
            operation_mode="video-editing")


def test_byteplus_local_video_can_use_explicit_temporary_host(monkeypatch, tmp_path):
    video = tmp_path / "approved cut.mp4"
    video.write_bytes(b"video")
    monkeypatch.setenv(
        "CB_BYTEPLUS_VIDEO_BASE_URL", "https://temporary.example.test/media/")

    assert cb_gen._byteplus_asset_url(str(video), "video") == (
        "https://temporary.example.test/media/approved%20cut.mp4")


def test_byteplus_local_video_can_use_hash_bound_sidecar_host(tmp_path):
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"approved-video")
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    sidecar = tmp_path / "approved.mp4.gen.json"
    sidecar.write_text(json.dumps({
        "hostedUrl": "https://media.example.test/approved.mp4",
        "hostedContentHash": digest,
    }))

    assert cb_gen._byteplus_asset_url(str(video), "video") == (
        "https://media.example.test/approved.mp4")


def test_byteplus_rejects_stale_hash_bound_sidecar_host(tmp_path):
    video = tmp_path / "approved.mp4"
    video.write_bytes(b"changed-video")
    sidecar = tmp_path / "approved.mp4.gen.json"
    sidecar.write_text(json.dumps({
        "hostedUrl": "https://media.example.test/approved.mp4",
        "hostedContentHash": "0" * 64,
    }))

    with pytest.raises(ValueError, match="hash does not match"):
        cb_gen._byteplus_asset_url(str(video), "video")


def test_already_uploaded_reference_url_is_not_uploaded_again(monkeypatch):
    uploads = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda path: uploads.append(path) or "uploaded")

    remote = "https://fal.media/files/reference.png"
    assert cb_gen._fal_asset_url(remote) == remote
    assert cb_gen._fal_asset_url("local.png") == "uploaded"
    assert uploads == ["local.png"]


def test_fal_25_adapter_uses_live_schema_without_legacy_bitrate(monkeypatch, tmp_path):
    image = tmp_path / "turnaround.png"
    audio = tmp_path / "approved.wav"
    output = tmp_path / "candidate.mp4"
    image.write_bytes(b"image")
    audio.write_bytes(b"audio")
    monkeypatch.setattr(cb_gen, "FAL_KEY", "test-key")
    uploads = []
    monkeypatch.setattr(
        cb_gen, "_fal_asset_url",
        lambda path: uploads.append(path) or f"https://fal.media/{len(uploads)}")
    submitted = {}

    def subscribe(endpoint, arguments=None, with_logs=False):
        submitted.update({
            "endpoint": endpoint, "arguments": arguments, "with_logs": with_logs})
        return {"video": {"url": "https://fal.media/candidate.mp4"}, "seed": 42}

    class Response:
        content = b"video"

    monkeypatch.setattr(cb_gen, "_fal_subscribe", subscribe)
    monkeypatch.setattr(cb_gen, "_rget", lambda *args, **kwargs: Response())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    result = cb_gen.generate_video_seedance_ref(
        "Use @Image1 and @Audio1.", [str(image)], [str(audio)], duration=29,
        out=str(output), raw_prompt=True, production_route="cb_render",
        model_id="fal-seedance-2.5")

    assert result == str(output)
    assert output.read_bytes() == b"video"
    assert submitted["endpoint"] == "bytedance/seedance-2.5/reference-to-video"
    assert submitted["arguments"] == {
        "prompt": "Use @Image1 and @Audio1.",
        "image_urls": ["https://fal.media/1"],
        "resolution": "720p",
        "duration": "29",
        "aspect_ratio": "16:9",
        "generate_audio": True,
        "audio_urls": ["https://fal.media/2"],
    }


def test_byteplus_25_adapter_builds_and_polls_the_official_async_contract(
        monkeypatch, tmp_path):
    image = tmp_path / "opening.png"
    audio = tmp_path / "voice.wav"
    video = tmp_path / "previous.mp4"
    output = tmp_path / "result.mp4"
    image.write_bytes(b"PNG-reference")
    audio.write_bytes(b"WAV-reference")
    video.write_bytes(b"MP4-reference")
    pathlib.Path(str(video) + ".gen.json").write_text(json.dumps({
        "endpoint": "/api/v3/contents/generations/tasks",
        "providerTaskId": "cgt-prev-25",
    }))
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
        if url.endswith("/cgt-prev-25"):
            return Response({"id": "cgt-prev-25", "status": "succeeded",
                             "content": {"video_url": "https://media.example/previous.mp4"}})
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

    progress_events = []
    result = cb_gen.generate_video_seedance_ref(
        "[Stage 1] Preserve the approved story.", [str(image)], [str(audio)],
        video_urls=[str(video)],
        duration=30, out=str(output), raw_prompt=True, production_route="cb_render",
        model_id="dreamina-seedance-2-5-260628",
        progress_callback=progress_events.append)

    assert result == str(output)
    assert output.read_bytes() == b"MP4-result"
    assert requested["model_id"] == "dreamina-seedance-2-5-260628"
    assert posted["url"].endswith("/api/v3/contents/generations/tasks")
    body = posted["json"]
    assert body["model"] == "dreamina-seedance-2-5-260628"
    assert body["duration"] == 30
    assert "ratio" not in body
    assert body["content"][0] == {
        "type": "text", "text": "[Stage 1] Preserve the approved story."}
    assert body["content"][1]["role"] == "reference_image"
    assert body["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["content"][2]["role"] == "reference_audio"
    assert body["content"][2]["audio_url"]["url"].startswith("data:audio/wav;base64,")
    assert body["content"][3]["role"] == "reference_video"
    assert body["content"][3]["video_url"]["url"] == "https://media.example/previous.mp4"
    assert [event["event"] for event in progress_events] == [
        "submitting", "submitted", "poll", "poll", "downloading", "downloaded"]
    assert progress_events[1]["taskId"] == "cgt-test-25"


def test_byteplus_25_video_editing_uses_provider_duration_sentinel(
        monkeypatch, tmp_path):
    video = tmp_path / "approved.mp4"
    output = tmp_path / "edit.mp4"
    video.write_bytes(b"MP4-reference")
    pathlib.Path(str(video) + ".gen.json").write_text(json.dumps({
        "endpoint": "/api/v3/contents/generations/tasks",
        "providerTaskId": "cgt-prev-25",
    }))
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "test-key")

    def contract(**kwargs):
        return {
            "providerModelId": "dreamina-seedance-2-5-260628",
            "provider": "byteplus",
            "modelVersion": "2.5-260628",
            "transport": "byteplus-async",
            "mode": "video-editing",
            "endpoint": "/api/v3/contents/generations/tasks",
            "resolution": "480p",
            "duration": 30,
            "costRateKey": "seedance_25_byteplus_480p_per_sec",
            "capabilityVerifiedAt": "2026-08-16",
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
        return Response({"id": "cgt-edit-25"})

    polls = iter([
        {"id": "cgt-edit-25", "status": "running"},
        {"id": "cgt-edit-25", "status": "succeeded",
         "content": {"video_url": "https://media.example/edit.mp4"},
         "duration": 30, "usage": {"completion_tokens": 456}},
    ])

    def get(url, **kwargs):
        if url.endswith("/cgt-prev-25"):
            return Response({"id": "cgt-prev-25", "status": "succeeded",
                             "content": {"video_url": "https://media.example/source.mp4"}})
        if url == "https://media.example/edit.mp4":
            return Response(content=b"MP4-edit")
        return Response(next(polls))

    monkeypatch.setattr(cb_providers, "request_contract", contract)
    monkeypatch.setattr(cb_gen, "_rpost", post)
    monkeypatch.setattr(cb_gen, "_rget", get)
    monkeypatch.setattr(cb_gen.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(cb_gen.cb_costs, "estimate_video_cost", lambda key, seconds: 1.23)
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *args, **kwargs: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *args, **kwargs: None)

    result = cb_gen.generate_video_seedance_ref(
        "Strictly edit @Video1 only.", [], video_urls=[str(video)],
        duration=30, resolution="480p", out=str(output), raw_prompt=True,
        production_route="cb_render", model_id="dreamina-seedance-2-5-260628",
        operation_mode="video-editing")

    assert result == str(output)
    body = posted["json"]
    assert body["duration"] == -1
    assert "ratio" not in body
    assert body["content"][1]["role"] == "reference_video"
    assert body["content"][1]["video_url"]["url"] == "https://media.example/source.mp4"
