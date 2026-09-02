#!/usr/bin/env python3
"""THE PROJECT PROFILE — the one authority for where a project's files live.

T44 (RESTRUCTURE_SPEC_PROJECTS.md, 2026-09-01): the software is the pipeline; a show is a PROJECT —
a folder under projects/<id>/ that owns its show bible, canon, laws, assets, chairs' taste and
episodes. This module loads and validates a project's profile.json and hands the engine every path
it may read. No engine module builds a project path by hand; it imports from `paths`, which reads
this. (studio_profile.py is a one-release re-export shim of this module — same names, same objects.)

Selecting the active project, in order:
    1. env STUDIO_PROJECT (STUDIO_SHOW is honoured as an alias for one release)
    2. the one projects/<id>/profile.json that declares "default": true
    3. if exactly one project exists, that one
Anything else is an error that names the projects it found — never a silent fallback to a hard-coded
show id.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


SHOW_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# T55 (2026-09-01): the adapter whitelist is gone. The engine is ONE pipeline for every project; a
# profile's `engineAdapter` is an optional historical label (the first project's reads
# "crystal-bears-v1") and never gates anything. What gates production is CONTENT: the required project
# files, each named by path when missing (capability_report → missingRequiredContent), and the
# project's own `capabilities` flags (what this project chooses to produce).
DEFAULT_CAPABILITIES = {"keyframes": True, "animation": True, "voice": True, "music": True, "post": True}
PROJECTS_DIR = "projects"


class ShowProfileError(RuntimeError):
    pass


ProjectProfileError = ShowProfileError


class CanonProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lockedCanon: str = Field(min_length=1)
    characters: str = Field(min_length=1)
    locations: str = Field(min_length=1)
    continuity: str = Field(min_length=1)
    episodeArc: Optional[str] = None
    gagLocks: Optional[str] = None
    identityPacks: Optional[str] = None
    bannedVocabulary: Optional[str] = None
    voiceCards: Optional[str] = None
    sfxLibrary: Optional[str] = None
    sfxDir: Optional[str] = None
    beatCosts: Optional[str] = None
    lockPolicy: Optional[str] = None
    canonLock: Optional[str] = None
    referenceSlotPolicy: Optional[str] = None


class WingLaw(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)
    appliesWhen: Optional[str] = None


class LawsProfile(BaseModel):
    # Laws are per-project by nature; a new project may declare laws this schema has not met yet.
    model_config = ConfigDict(extra="allow")

    style: Optional[str] = None
    wingLaw: Optional[WingLaw] = None
    forbiddenElements: Optional[str] = None
    emissionChecks: Optional[str] = None
    castVocabulary: Optional[str] = None
    continuityRules: Optional[str] = None


class CreativeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str = Field(default="creative", min_length=1)
    learning: Optional[str] = None
    exemplars: Optional[str] = None
    dailiesLibrary: Optional[str] = None
    voiceRegisters: Optional[str] = None
    voiceRulebook: Optional[str] = None
    voicePlaybook: Optional[str] = None
    designRoster: Optional[str] = None    # the studio Design tab's cast/locations/props presentation (T50)


class AssetsProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root: str = Field(min_length=1)


class EpisodeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scripts: str = Field(min_length=1)
    output: str = Field(min_length=1)
    index: Optional[str] = None
    # T57/T58: rendered media (plates, keyframes, takes, post) for THIS project. Undeclared = the
    # engine's legacy shared engine/media (the first project keeps it for one release — identity
    # digests hash absolute media paths); every new project declares its own.
    media: Optional[str] = None


class FormatProfile(BaseModel):
    """T71 (2026-09-02, Julian: "The Box Monsters will always be designed to be made up of 30
    second shots and they will be 7 mins so 15 shots"): the project's fixed delivery format.
    `shotSeconds` is the length of every production unit when the writer has already broken
    the script into shots (the treatment format); `scriptStyle` says which script shape the
    project writes in. A project that declares no format keeps the full Creative Room and the
    engine's natural 4-30s unit packing — Crystal Bears is byte-identical."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    note: Optional[str] = Field(default=None, alias="_note")
    shotSeconds: Optional[int] = Field(default=None, ge=4, le=30)
    shotSecondsMax: Optional[int] = Field(default=None, ge=4, le=30)
    aspect: Optional[str] = None
    fps: Optional[int] = Field(default=None, ge=1, le=120)
    audience: Optional[str] = None
    scriptStyle: Optional[Literal["treatment", "screenplay"]] = None
    episodeMinutes: Optional[float] = Field(default=None, gt=0)
    shotsPerEpisode: Optional[int] = Field(default=None, ge=1)


class ShowProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    showId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    animationType: str = Field(min_length=1)
    aspectRatio: str = Field(min_length=1)
    engineAdapter: Optional[str] = None      # historical label only (T55) — never a gate
    capabilities: Dict[str, bool] = Field(default_factory=dict)   # T55: what this project produces
    default: bool = False
    showrunner: Optional[str] = None    # the person who signs the gates — named in chair contracts (T52)
    format: Optional[FormatProfile] = None   # T71: fixed shot length / script style, or none
    canon: CanonProfile
    laws: LawsProfile = Field(default_factory=LawsProfile)
    episodes: EpisodeProfile
    creative: Optional[CreativeProfile] = None
    creativeRoot: str = "creative"            # legacy spelling; creative.root wins when both are set
    assets: Optional[AssetsProfile] = None
    showBible: Optional[str] = None
    docs: Optional[str] = None
    chairs: Optional[str] = None
    note: Optional[str] = Field(default=None, alias="_note")

    @model_validator(mode="after")
    def valid_identity(self):
        if not SHOW_ID_RE.fullmatch(self.showId):
            raise ValueError("showId must be a lowercase hyphenated token")
        return self

    @property
    def projectId(self) -> str:
        return self.showId


ProjectProfile = ShowProfile


def validate_show_id(value: str) -> str:
    value = str(value or "").strip()
    if not SHOW_ID_RE.fullmatch(value):
        raise ShowProfileError("STUDIO_PROJECT must be a lowercase hyphenated project ID")
    return value


validate_project_id = validate_show_id


def _safe_resolve(base: pathlib.Path, relative: str, label: str) -> pathlib.Path:
    """The declared path must sit INSIDE the project lexically (no ".." climbing out). Symlinks are
    not followed here on purpose: a project may keep large media on another drive behind a link
    (projects/<id>/assets → cb-seed/assets today, an external volume tomorrow); the project still
    owns the NAME. Callers that need the physical file resolve() it themselves."""
    candidate_path = pathlib.Path(str(relative or ""))
    if not str(relative or "").strip() or candidate_path.is_absolute():
        raise ShowProfileError(f"{label} must be a non-empty relative path")
    base = base.resolve()
    candidate = pathlib.Path(os.path.normpath(str(base / candidate_path)))
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ShowProfileError(f"{label} escapes the project directory") from exc
    return candidate


def _repo_root(repo_root=None) -> pathlib.Path:
    return pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent.parent).resolve()


def list_project_ids(repo_root=None) -> List[str]:
    """Every projects/<id>/profile.json on disk, sorted. Reads nothing but the directory."""
    root = _repo_root(repo_root) / PROJECTS_DIR
    if not root.is_dir():
        return []
    return sorted(p.parent.name for p in root.glob("*/profile.json")
                  if SHOW_ID_RE.fullmatch(p.parent.name))


ACTIVE_PROJECT_FILE = pathlib.Path("cb-studio") / "data" / "active-project.json"


def active_project_setting(repo_root=None) -> Optional[str]:
    """T59: the production the studio last switched to (cb-studio/data/active-project.json), or None.
    Per-machine runtime state — never project data, never committed."""
    path = _repo_root(repo_root) / ACTIVE_PROJECT_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = str((raw or {}).get("id") or "").strip()
    if not pid or not SHOW_ID_RE.fullmatch(pid):
        return None
    return pid if (_repo_root(repo_root) / PROJECTS_DIR / pid / "profile.json").exists() else None


def set_active_project(project_id: str, repo_root=None) -> str:
    pid = validate_show_id(project_id)
    if not (_repo_root(repo_root) / PROJECTS_DIR / pid / "profile.json").exists():
        raise ShowProfileError(f"no such project: {pid}")
    path = _repo_root(repo_root) / ACTIVE_PROJECT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": pid}, indent=2) + "\n", encoding="utf-8")
    return pid


def default_project_id(repo_root=None) -> str:
    """The project the engine works on when nobody said otherwise — see the module docstring.
    Order: STUDIO_PROJECT env → the studio's active-project setting (T59) → the one profile that
    declares "default": true → the only project → error."""
    env = os.environ.get("STUDIO_PROJECT") or os.environ.get("STUDIO_SHOW")
    if env:
        return validate_show_id(env)
    chosen = active_project_setting(repo_root)
    if chosen:
        return chosen
    root = _repo_root(repo_root) / PROJECTS_DIR
    ids = list_project_ids(repo_root)
    defaults = []
    for pid in ids:
        try:
            raw = json.loads((root / pid / "profile.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if raw.get("default") is True:
            defaults.append(pid)
    if len(defaults) == 1:
        return defaults[0]
    if len(defaults) > 1:
        raise ShowProfileError(
            f"more than one project declares \"default\": true ({', '.join(defaults)}) — "
            "set STUDIO_PROJECT or fix the profiles")
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise ShowProfileError(f"no projects found under {root} — nothing to work on")
    raise ShowProfileError(
        f"several projects exist ({', '.join(ids)}) and none declares \"default\": true — "
        "set STUDIO_PROJECT=<id> or mark one profile as the default")


@dataclass(frozen=True)
class LoadedShowProfile:
    repo_root: pathlib.Path
    show_root: pathlib.Path
    profile_path: pathlib.Path
    profile: ShowProfile
    profile_digest: str

    # ---- naming: project_* is the vocabulary from T44 on; show_* stays for one release ----
    @property
    def project_root(self) -> pathlib.Path:
        return self.show_root

    @property
    def project_id(self) -> str:
        return self.profile.showId

    def resolve(self, relative: str, label: str = "project profile path") -> pathlib.Path:
        return _safe_resolve(self.show_root, relative, label)

    def resolve_optional(self, relative: Optional[str], label: str) -> Optional[pathlib.Path]:
        return self.resolve(relative, label) if relative else None

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

    @property
    def media_path(self) -> Optional[pathlib.Path]:
        return self.resolve_optional(self.profile.episodes.media, "episodes.media")

    @property
    def episodes_index_path(self) -> pathlib.Path:
        rel = self.profile.episodes.index or f"{self.profile.episodes.scripts}/../episodes.json"
        return self.resolve(rel, "episodes.index")

    @property
    def creative_root(self) -> pathlib.Path:
        rel = self.profile.creative.root if self.profile.creative else self.profile.creativeRoot
        return self.resolve(rel, "creative.root")

    def creative_path(self, key: str) -> Optional[pathlib.Path]:
        """creative.<key> if declared, else None. Keys: learning, exemplars, dailiesLibrary,
        voiceRegisters, voiceRulebook, voicePlaybook."""
        c = self.profile.creative
        rel = getattr(c, key, None) if c else None
        return self.resolve_optional(rel, f"creative.{key}")

    @property
    def assets_root(self) -> Optional[pathlib.Path]:
        return self.resolve_optional(self.profile.assets.root if self.profile.assets else None,
                                     "assets.root")

    @property
    def laws_paths(self) -> dict[str, pathlib.Path]:
        out = {}
        laws = self.profile.laws
        for key in ("style", "forbiddenElements", "emissionChecks", "castVocabulary", "continuityRules"):
            rel = getattr(laws, key, None)
            if rel:
                out[key] = self.resolve(rel, f"laws.{key}")
        if laws.wingLaw:
            out["wingLaw"] = self.resolve(laws.wingLaw.file, "laws.wingLaw.file")
        return out

    @property
    def show_bible_path(self) -> Optional[pathlib.Path]:
        return self.resolve_optional(self.profile.showBible, "showBible")

    @property
    def chairs_path(self) -> Optional[pathlib.Path]:
        return self.resolve_optional(self.profile.chairs, "chairs")

    @property
    def docs_path(self) -> Optional[pathlib.Path]:
        return self.resolve_optional(self.profile.docs, "docs")


LoadedProjectProfile = LoadedShowProfile


def load_show_profile(repo_root=None, show_id=None) -> LoadedShowProfile:
    root = _repo_root(repo_root)
    selected = validate_show_id(show_id) if show_id is not None else default_project_id(root)
    shows_root = (root / PROJECTS_DIR).resolve()
    show_root = (shows_root / selected).resolve()
    try:
        show_root.relative_to(shows_root)
    except ValueError as exc:
        raise ShowProfileError("selected project escapes the projects directory") from exc
    profile_path = show_root / "profile.json"
    try:
        raw_bytes = profile_path.read_bytes()
        raw = json.loads(raw_bytes)
        profile = ShowProfile.model_validate(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ShowProfileError(f"project profile is missing or invalid: {profile_path}") from exc
    if profile.showId != selected:
        raise ShowProfileError(
            f"project profile identity mismatch: selected {selected}, found {profile.showId}")
    loaded = LoadedShowProfile(
        repo_root=root, show_root=show_root, profile_path=profile_path,
        profile=profile, profile_digest=hashlib.sha256(raw_bytes).hexdigest())

    # Validate every declared content path at load time — a path that escapes the project is an
    # error even if the file is never read.
    loaded.canon_paths
    loaded.scripts_path
    loaded.output_path
    loaded.episodes_index_path
    loaded.creative_root
    for key in ("learning", "exemplars", "dailiesLibrary", "voiceRegisters", "voiceRulebook",
                "voicePlaybook"):
        loaded.creative_path(key)
    loaded.assets_root
    loaded.laws_paths
    loaded.show_bible_path
    loaded.docs_path
    loaded.chairs_path
    return loaded


load_project_profile = load_show_profile


def capability_report(loaded: LoadedShowProfile) -> dict:
    required = {
        "lockedCanon": loaded.canon_paths["lockedCanon"],
        "characters": loaded.canon_paths["characters"],
        "locations": loaded.canon_paths["locations"],
        "continuity": loaded.canon_paths["continuity"],
        "scripts": loaded.scripts_path,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    missing_paths = [f"{name}: {_display_path(loaded, path)}" for name, path in required.items()
                     if not path.exists()]
    capabilities = {**DEFAULT_CAPABILITIES, **(loaded.profile.capabilities or {})}
    return {
        "showId": loaded.profile.showId,
        "projectId": loaded.profile.showId,
        "name": loaded.profile.name,
        "engineAdapter": loaded.profile.engineAdapter,
        # T55: there is no adapter to install — the one engine serves every project. Kept as a key
        # for older readers; it is simply "the project declares what it needs".
        "adapterReady": True,
        "capabilities": capabilities,
        "profileDigest": loaded.profile_digest,
        "profilePath": str(loaded.profile_path),
        "tenantRoot": str(loaded.show_root),
        "projectRoot": str(loaded.show_root),
        "missingRequiredContent": missing,
        "missingRequiredPaths": missing_paths,
        "productionReady": not missing,
        "zeroSpend": True,
    }


def _display_path(loaded: LoadedShowProfile, path: pathlib.Path) -> str:
    try:
        return path.relative_to(loaded.repo_root).as_posix()
    except (ValueError, AttributeError):
        return str(path)


def __getattr__(name):
    # DEFAULT_SHOW_ID is computed, never a constant: the registry (projects/*/profile.json) decides.
    if name in ("DEFAULT_SHOW_ID", "DEFAULT_PROJECT_ID"):
        return default_project_id()
    raise AttributeError(name)
