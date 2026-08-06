import pytest
from PIL import Image

import cb_departments
import cb_identity


def _pack(source):
    return {
        "schemaVersion": 1,
        "source": str(source),
        "providerViews": {
            "keyframe": {"view": "front", "crop": [0, 0, 0.5, 1]},
        },
        "distinguishingFeatures": ["tan nose"],
        "mustNotBorrow": ["eyelashes"],
    }


def test_returns_one_intact_content_addressed_turnaround(tmp_path):
    source = tmp_path / "front-back.png"
    image = Image.new("RGB", (200, 100), "blue")
    image.paste(Image.new("RGB", (100, 100), "red"), (0, 0))
    image.save(source)

    first = cb_identity.materialize_provider_view(
        "Fuzzby", _pack(source), tmp_path, tmp_path / "derived")
    second = cb_identity.materialize_provider_view(
        "Fuzzby", _pack(source), tmp_path, tmp_path / "derived")

    assert first["path"] == second["path"]
    assert first["singleSubject"] is False
    assert first["singleCharacterIdentity"] is True
    assert first["intactTurnaround"] is True
    assert first["derived"] is False
    assert first["providerSafe"] is True
    assert first["view"] == "complete-turnaround"
    assert first["distinguishingFeatures"] == ["tan nose"]
    assert first["mustNotBorrow"] == ["eyelashes"]
    with Image.open(first["path"]) as turnaround:
        assert turnaround.size == (200, 100)
        assert turnaround.getpixel((50, 50)) == (255, 0, 0)
        assert turnaround.getpixel((150, 50)) == (0, 0, 255)
    assert not (tmp_path / "derived").exists()


def test_identity_pack_never_uses_declared_crop(tmp_path):
    source = tmp_path / "sheet.png"
    Image.new("RGB", (200, 100), "gray").save(source)
    record = _pack(source)
    record["providerViews"]["keyframe"]["crop"] = [0, 0, 1.2, 1]

    identity = cb_identity.materialize_provider_view(
        "Fuzzby", record, tmp_path, tmp_path / "derived")
    assert identity["path"] == str(source.resolve())
    assert identity["intactTurnaround"] is True
    assert not (tmp_path / "derived").exists()


def test_multiple_declared_views_still_produce_one_intact_attachment(tmp_path):
    source = tmp_path / "front-back.png"
    image = Image.new("RGB", (200, 100), "blue")
    image.paste(Image.new("RGB", (100, 100), "red"), (0, 0))
    image.save(source)
    pack = _pack(source)
    pack["turnaroundViews"] = [
        {"view": "front", "crop": [0, 0, 0.5, 1]},
        {"view": "rear", "crop": [0.5, 0, 1, 1]},
    ]

    records = cb_identity.materialize_provider_views(
        "Fuzzby", pack, tmp_path, tmp_path / "derived", usage="animation")

    assert len(records) == 1
    assert records[0]["view"] == "complete-turnaround"
    assert records[0]["turnaroundViewCount"] == 2
    assert records[0]["intactTurnaround"] is True
    with Image.open(records[0]["path"]) as turnaround:
        assert turnaround.getpixel((50, 50)) == (255, 0, 0)
        assert turnaround.getpixel((150, 50)) == (0, 0, 255)


def test_keyframe_conformance_cannot_pass_with_wrong_cast_or_partial_score():
    dimension = {"score": 2, "visibleEvidence": "Clearly matches."}
    payload = {
        "verdict": "pass",
        "expectedCharacters": ["Fuzzby", "Zenny"],
        "detectedCharacters": ["Fuzzby"],
        "expectedSubjectCount": 2,
        "subjectCount": 1,
        "summary": "Wrong cast.",
        "identityAndDistinguishability": dimension,
        "relativeScaleAndGeography": dimension,
        "anatomyAndSilhouette": dimension,
        "actionReadyComposition": dimension,
        "forbiddenContent": dimension,
    }
    with pytest.raises(ValueError, match="exact cast"):
        cb_departments.KeyframeConformanceReview.model_validate(payload)

    payload["detectedCharacters"] = ["Fuzzby", "Zenny"]
    payload["subjectCount"] = 2
    payload["relativeScaleAndGeography"] = {
        "score": 1, "visibleEvidence": "Scale is ambiguous."}
    with pytest.raises(ValueError, match="every objective dimension"):
        cb_departments.KeyframeConformanceReview.model_validate(payload)
