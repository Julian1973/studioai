"""Provider-independent voice migration contracts. No network calls or spend.

This foundation is deliberately separate from the existing generation transport.
Only a human-approved, evidence-bound candidate may replace an active voice.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VoiceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: Literal["elevenlabs", "byteplus"]
    model_id: str = Field(min_length=1)
    speaker_id: str = Field(min_length=1)


class VoiceReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate: VoiceBinding
    reference_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    audition_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    score: int = Field(ge=0, le=10, strict=True)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=1)
    replication_rights_confirmed: bool

    @model_validator(mode="after")
    def meaningful_review(self):
        if any(not value.strip() for value in
               (self.reason, self.reviewer, self.reviewed_at)):
            raise ValueError("review requires a reason, reviewer and timestamp")
        if self.decision == "approve" and not self.replication_rights_confirmed:
            raise ValueError("replication rights must be confirmed before approval")
        return self


class VoiceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity_id: str = Field(min_length=1)
    active: VoiceBinding
    history: tuple[VoiceReview, ...] = ()

    def reviewed(self, review: VoiceReview) -> "VoiceIdentity":
        """Return a new version; rejection records feedback without changing routing.

        Callers must persist versions and authenticate the reviewer before activation.
        Scores are evidence, not an automatic approval threshold.
        """
        return VoiceIdentity(
            identity_id=self.identity_id,
            active=review.candidate if review.decision == "approve" else self.active,
            history=(*self.history, review),
        )


def identities_from_voice_cards(show_id: str, cards: dict) -> dict[str, VoiceIdentity]:
    """Import existing ElevenLabs cards without altering production configuration."""
    if not show_id.strip():
        raise ValueError("show ID is required")
    return {
        character: VoiceIdentity(
            identity_id=f"{show_id}/{character}",
            active=VoiceBinding(
                provider="elevenlabs", speaker_id=card["voiceId"],
                model_id=card.get("modelId", cards.get("modelId", "eleven_v3")),
            ),
        )
        for character, card in cards["characters"].items()
    }
