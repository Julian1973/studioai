"""Versioned Seedance interchange contracts.

External skills and repositories exchange snake_case records. The production
engine may retain its established camelCase package fields; this module is the
single typed boundary between those vocabularies.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InterchangeModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda name: _to_snake(name),
        populate_by_name=True,
        extra="forbid",
    )


def _to_snake(name: str) -> str:
    out = []
    for char in name:
        if char.isupper():
            out.extend(("_", char.lower()))
        else:
            out.append(char)
    return "".join(out)


class IdentityAnchorSet(InterchangeModel):
    subjectId: str = Field(min_length=1)
    anchors: list[str] = Field(min_length=1, max_length=3)


class ExtensionContract(InterchangeModel):
    schemaVersion: Literal["seedance-extension/v1"] = "seedance-extension/v1"
    mode: Literal["forward", "backward", "bridge"]
    sourceClip: str = Field(min_length=1)
    sourceApproved: bool
    taskType: Literal["extend"]
    alreadyTrue: list[str] = Field(min_length=1)
    continuityCriticalSubjects: list[str] = Field(default_factory=list)
    identityAnchorSets: list[IdentityAnchorSet] = Field(default_factory=list)
    lighting: str = Field(min_length=1)
    audioState: str = Field(min_length=1)
    geographyMaster: str | None = None

    @model_validator(mode="after")
    def extension_is_safe_to_execute(self):
        if not self.sourceApproved:
            raise ValueError("an extension source must be explicitly approved")
        if self.mode == "bridge" and not self.geographyMaster:
            raise ValueError("a bridge must declare one geography_master")
        anchors_by_subject = {item.subjectId for item in self.identityAnchorSets}
        missing = [
            subject for subject in self.continuityCriticalSubjects
            if subject not in anchors_by_subject
        ]
        if missing:
            raise ValueError(
                "continuity-critical subjects need identity anchors: " + ", ".join(missing))
        return self


def load_extension_contract(data: dict) -> ExtensionContract:
    """Accept canonical snake_case or existing camelCase at the repository boundary."""
    return ExtensionContract.model_validate(data)


def dump_extension_contract(contract: ExtensionContract) -> dict:
    """Emit the canonical public interchange vocabulary."""
    return contract.model_dump(by_alias=True, mode="json")
