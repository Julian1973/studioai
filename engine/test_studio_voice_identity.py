import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from studio_voice_identity import VoiceBinding, VoiceIdentity, VoiceReview, identities_from_voice_cards


def review(**changes):
    values = dict(
        candidate=VoiceBinding(provider="byteplus", model_id="seed-audio-1.0", speaker_id="candidate"),
        reference_sha256="a" * 64, audition_sha256="b" * 64,
        score=9, decision="approve", reason="Identity and performance match",
        reviewer="Julian", reviewed_at="2026-10-01T15:20:00+01:00",
        replication_rights_confirmed=True,
    )
    return VoiceReview(**(values | changes))


def original():
    return VoiceIdentity(identity_id="show/Keen", active=VoiceBinding(
        provider="elevenlabs", model_id="eleven_v3", speaker_id="established"))


def test_approval_switches_only_new_version_and_preserves_evidence():
    old = original()
    new = old.reviewed(review())
    assert old.active.provider == "elevenlabs"
    assert new.active.provider == "byteplus"
    assert new.identity_id == old.identity_id
    assert new.history[0].audition_sha256 == "b" * 64
    assert VoiceIdentity.model_validate_json(new.model_dump_json()) == new


def test_rejection_records_score_without_switching_voice():
    old = original()
    new = old.reviewed(review(decision="reject", score=3))
    assert new.active == old.active
    assert new.history[0].score == 3


@pytest.mark.parametrize("changes", [
    {"score": 11}, {"score": -1}, {"score": True}, {"score": 8.5},
    {"reason": " "}, {"audition_sha256": "missing"},
    {"replication_rights_confirmed": False},
])
def test_invalid_or_unqualified_approval_is_rejected(changes):
    with pytest.raises(ValidationError):
        review(**changes)


def test_real_cast_import_preserves_every_existing_voice():
    path = Path(__file__).resolve().parents[1] / "shows/crystal-bears/canon/voice_cards.json"
    cards = json.loads(path.read_text())
    imported = identities_from_voice_cards("crystal-bears", cards)
    assert set(imported) == set(cards["characters"])
    for character, identity in imported.items():
        assert identity.active.speaker_id == cards["characters"][character]["voiceId"]
        assert identity.active.provider == "elevenlabs"
        assert identity.history == ()
