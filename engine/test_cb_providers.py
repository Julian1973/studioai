import json

import pytest

import cb_gen
import cb_providers


def test_registry_has_one_enabled_default_and_keeps_unverified_25_disabled(monkeypatch):
    monkeypatch.delenv("CB_VIDEO_MODEL_ID", raising=False)
    registry = cb_providers.load_registry()

    default = cb_providers.video_model(registry=registry)
    seedance_25 = cb_providers.video_model(
        "byteplus-seedance-2.5", require_enabled=False, registry=registry)

    assert default.modelId == "fal-seedance-2.0"
    assert default.enabled and default.status == "production"
    assert not seedance_25.enabled
    assert seedance_25.status == "unverified"
    assert "official" in seedance_25.disableReason.lower()


def test_disabled_or_unknown_selection_refuses_before_a_route_can_be_used(monkeypatch):
    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "byteplus-seedance-2.5")
    with pytest.raises(cb_providers.ProviderCapabilityError, match="disabled"):
        cb_providers.request_contract(duration=6, image_count=1)

    monkeypatch.setenv("CB_VIDEO_MODEL_ID", "invented-model")
    with pytest.raises(cb_providers.ProviderCapabilityError, match="unknown"):
        cb_providers.request_contract(duration=6, image_count=1)


@pytest.mark.parametrize("kwargs, match", [
    ({"duration": 16, "image_count": 1}, "duration"),
    ({"duration": 6, "resolution": "4K", "image_count": 1}, "resolution"),
    ({"duration": 6, "image_count": 10}, "images"),
    ({"duration": 6, "image_count": 1, "audio_count": 4}, "audio"),
    ({"duration": 6, "image_count": 1, "video_count": 1}, "video"),
])
def test_request_contract_enforces_verified_limits(kwargs, match):
    with pytest.raises(cb_providers.ProviderCapabilityError, match=match):
        cb_providers.request_contract(**kwargs)


def test_capability_report_is_zero_spend_and_secret_free(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "do-not-leak")
    report = cb_providers.capability_report()
    rendered = json.dumps(report)

    assert report["zeroSpend"] is True
    assert report["selectionReady"] is True
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
