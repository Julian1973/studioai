#!/usr/bin/env python3
"""Validated, tenant-safe show profiles for the shared animation studio engine."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


DEFAULT_SHOW_ID = "crystal-bears"
SHOW_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SUPPORTED_ENGINE_ADAPTERS = {"crystal-bears-v1"}


class ShowProfileError(RuntimeError):
    pass


class CanonProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lockedCanon: str = Field(min_length=1)
    characters: str = Field(min_length=1)
    locations: str = Field(min_length=1)
    continuity: str = Field(min_length=1)
    episodeArc: Optional[str] = None
    gagLocks: Optional[str] = None


class EpisodeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scripts: str = Field(min_length=1)
    output: str = Field(min_length=1)


class ShowProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    showId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    animationType: str = Field(min_length=1)
    aspectRatio: str = Field(min_length=1)
    engineAdapter: str = Field(min_length=1)
    canon: CanonProfile
    laws: Dict[str, Any]
    episodes: EpisodeProfile
    creativeRoot: str = "creative"
    docs: Optional[str] = None
    chairs: Optional[str] = None
    note: Optional[str] = Field(default=None, alias="_note")

    @model_validator(mode="after")
    def valid_identity(self):
        if not SHOW_ID_RE.fullmatch(self.showId):
            raise ValueError("showId must be a lowercase hyphenated token")
        return self


def validate_show_id(value: str) -> str:
    value = str(value or "").strip()
    if not SHOW_ID_RE.fullmatch(value):
        raise ShowProfileError("STUDIO_SHOW must be a lowercase hyphenated show ID")
    return value


def _safe_resolve(base: pathlib.Path, relative: str, label: str) -> pathlib.Path:
    candidate_path = pathlib.Path(str(relative or ""))
    if not str(relative or "").strip() or candidate_path.is_absolute():
        raise ShowProfileError(f"{label} must be a non-empty relative path")
    base = base.resolve()
    candidate = (base / candidate_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ShowProfileError(f"{label} escapes the show tenant directory") from exc
    return candidate


@dataclass(frozen=True)
class LoadedShowProfile:
    repo_root: pathlib.Path
    show_root: pathlib.Path
    profile_path: pathlib.Path
    profile: ShowProfile
    profile_digest: str

    def resolve(self, relative: str, label: str = "show profile path") -> pathlib.Path:
        return _safe_resolve(self.show_root, relative, label)

    @property
    def canon_paths(self) -> dict[str, pathlib.Path]:
        values = self.profile.canon.model_dump(exclude_none=True)
        return {key: self.resolve(value, f"canon.{key}") for key, value in values.items()}

    @property
    def scripts_path(self) -> pathlib.Path:
        return self.resolve(self.profile.episodes.scripts, "episodes.scripts")

    @property
    def output_path(self) -> pathlib.Path:
        return self.resolve(self.profile.episodes.output, "episodes.output")


def load_show_profile(repo_root=None, show_id=None) -> LoadedShowProfile:
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent.parent).resolve()
    selected = validate_show_id(
        show_id if show_id is not None else os.environ.get("STUDIO_SHOW", DEFAULT_SHOW_ID))
    shows_root = (root / "shows").resolve()
    show_root = (shows_root / selected).resolve()
    try:
        show_root.relative_to(shows_root)
    except ValueError as exc:
        raise ShowProfileError("selected show escapes the shows directory") from exc
    profile_path = show_root / "profile.json"
    try:
        raw_bytes = profile_path.read_bytes()
        raw = json.loads(raw_bytes)
        profile = ShowProfile.model_validate(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ShowProfileError(f"show profile is missing or invalid: {profile_path}") from exc
    if profile.showId != selected:
        raise ShowProfileError(
            f"show profile identity mismatch: selected {selected}, found {profile.showId}")
    loaded = LoadedShowProfile(
        repo_root=root, show_root=show_root, profile_path=profile_path,
        profile=profile, profile_digest=hashlib.sha256(raw_bytes).hexdigest())

    # Validate every declared content path at load time, including optional and nested law files.
    for key, value in profile.canon.model_dump(exclude_none=True).items():
        loaded.resolve(value, f"canon.{key}")
    loaded.resolve(profile.episodes.scripts, "episodes.scripts")
    loaded.resolve(profile.episodes.output, "episodes.output")
    loaded.resolve(profile.creativeRoot, "creativeRoot")
    if profile.docs:
        loaded.resolve(profile.docs, "docs")
    if profile.chairs:
        loaded.resolve(profile.chairs, "chairs")
    style = profile.laws.get("style")
    if style:
        loaded.resolve(style, "laws.style")
    wing = profile.laws.get("wingLaw")
    if isinstance(wing, dict) and wing.get("file"):
        loaded.resolve(wing["file"], "laws.wingLaw.file")
    return loaded


def capability_report(loaded: LoadedShowProfile) -> dict:
    required = {
        "lockedCanon": loaded.canon_paths["lockedCanon"],
        "characters": loaded.canon_paths["characters"],
        "locations": loaded.canon_paths["locations"],
        "continuity": loaded.canon_paths["continuity"],
        "scripts": loaded.scripts_path,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    adapter_ready = loaded.profile.engineAdapter in SUPPORTED_ENGINE_ADAPTERS
    return {
        "showId": loaded.profile.showId,
        "name": loaded.profile.name,
        "engineAdapter": loaded.profile.engineAdapter,
        "adapterReady": adapter_ready,
        "profileDigest": loaded.profile_digest,
        "profilePath": str(loaded.profile_path),
        "tenantRoot": str(loaded.show_root),
        "missingRequiredContent": missing,
        "productionReady": adapter_ready and not missing,
        "zeroSpend": True,
    }
