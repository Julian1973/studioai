"""Deterministic Seedance prompt compilation and zero-spend preflight.

This module turns a typed creative task into a provider-ready prompt contract. It does
not call a model, contact a media provider, alter an approval, or authorize spend.
Provider capability is checked separately against ``cb_providers`` so product guidance
can never silently become an executable route.
"""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

import cb_providers


SeedanceTaskType = Literal[
    "text_to_video",
    "reference_based_generation",
    "thirty_second_video",
    "ultra_long_video",
    "video_extension",
    "video_editing",
    "seamless_transition",
    "first_last_frame",
    "storyboard_grid",
    "blockout_render",
]

SEEDANCE_TASK_TYPES = (
    "text_to_video",
    "reference_based_generation",
    "thirty_second_video",
    "ultra_long_video",
    "video_extension",
    "video_editing",
    "seamless_transition",
    "first_last_frame",
    "storyboard_grid",
    "blockout_render",
)

TASK_TYPE_ALIASES = {
    "text-to-video": "text_to_video",
    "reference-to-video": "reference_based_generation",
    "reference_based": "reference_based_generation",
    "thirty-second-video": "thirty_second_video",
    "30-second-video": "thirty_second_video",
    "ultra-long-video": "ultra_long_video",
    "extend-forward": "video_extension",
    "extend-backward": "video_extension",
    "video-edit": "video_editing",
    "transition": "seamless_transition",
    "first-last-frame": "first_last_frame",
    "storyboard-grid": "storyboard_grid",
    "blockout-render": "blockout_render",
}

PROMPT_LAB_TASK_MODES = {
    "text_to_video": "text-to-video",
    "reference_based_generation": "reference-to-video",
    "thirty_second_video": "thirty-second-video",
    "ultra_long_video": "ultra-long-video",
    "video_editing": "video-edit",
    "seamless_transition": "transition",
    "first_last_frame": "first-last-frame",
    "storyboard_grid": "storyboard-grid",
    "blockout_render": "blockout-render",
}

SEEDANCE_LIMITS = {
    "images": {"max_count": 30, "recommended_subjects": (1, 8)},
    "videos": {
        "max_count": 10,
        "max_combined_duration_seconds": 30,
        "recommended_subjects": (1, 5),
        "recommended_clip_length_seconds": (5, 10),
    },
    "audio": {
        "max_count": 10,
        "max_combined_duration_seconds": 30,
        "recommended_clip_length_seconds": (5, 10),
    },
    "combined": {"max_count": 50},
    "video_editing": {
        "recommended_source_video_seconds": 20,
        "recommended_reference_images": (1, 5),
    },
}

DEFAULT_FORBIDDEN: tuple[str, ...] = ()

COMMON_RETRY_ISSUES = (
    "character face changed",
    "clothing changed",
    "extra character appeared",
    "reference background leaked into output",
    "unwanted subtitles appeared",
    "unwanted BGM appeared",
    "timing was too fast",
    "stage skipped",
    "object appeared out of thin air",
    "hard cut at transition",
    "motion deformed",
    "hands or fingers distorted",
    "style drifted",
)

PRE_SUBMISSION_CHECKLIST = (
    "Task type is classified.",
    "All references are explicitly bound by role.",
    "Each character, product, or prop has a unique name.",
    "Reference exclusions are stated.",
    "Prompt follows Subject + Action + Scene + Style + Camera + Audio.",
    "Long videos are divided into stages or timestamps.",
    "Each stage has one primary change.",
    "Each stage has a visible end state.",
    "Character identity, clothing, prop ownership, and spatial relationships are consistent.",
    "Video edits define the sole editing master.",
    "Video edits define edit scope and preserve-list.",
    "Extensions anchor the boundary frame.",
    "Transitions define trigger, camera movement, transformation, arrival state, and audio crossover.",
    "Emotions are paired with visible cues.",
    "Forbidden list is tailored to the task.",
    "No unsupported capabilities are assumed.",
)

_TAG_PATTERN = re.compile(r"^@(Image|Video|Audio|Figure|\u56fe)\s*\d+$", re.I)
_TIME_RANGE_PATTERN = re.compile(
    r"^\s*(\d+(?::\d{1,2}(?:\.\d+)?)?|\d+(?:\.\d+)?)\s*"
    r"(?:-|\u2013|\u2014|to)\s*"
    r"(\d+(?::\d{1,2}(?:\.\d+)?)?|\d+(?:\.\d+)?)"
    r"\s*(?:s|sec(?:ond)?s?)?\s*$",
    re.I,
)
_REQUEST_PARAMETER_PATTERNS = (
    re.compile(r"\b\d+(?:\.\d+)?[- ]second\b", re.I),
    re.compile(r"(?<!\d)(?:16:9|9:16|1:1)(?!\d)", re.I),
    re.compile(r"\b(?:480p|720p|1080p|2160p|4k)\b", re.I),
    re.compile(r"\bSeedance\s+\d+(?:\.\d+)?\b", re.I),
)


class ReferenceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tag: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    defines: str = Field(min_length=1)
    exclude: str = Field(
        default="irrelevant background and unrelated content",
        min_length=1,
    )

    @field_validator("tag")
    @classmethod
    def valid_tag(cls, value):
        value = str(value).strip()
        if not _TAG_PATTERN.match(value):
            raise ValueError("reference tag must look like @Image 1, @Video 1, @Audio 1, or @\u56fe1")
        return value


class CharacterProfile(BaseModel):
    """A human or stylized subject profile without forcing human fields on an IP character."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    kind: Literal["human", "stylized_character", "creature", "object"] = "stylized_character"
    age_ethnicity: str = Field(
        default="",
        validation_alias=AliasChoices("age_ethnicity", "ageEthnicity"),
    )
    skin: str = ""
    facial_details: str = Field(
        default="",
        validation_alias=AliasChoices("facial_details", "facialDetails"),
    )
    gaze_performance: str = Field(
        default="",
        validation_alias=AliasChoices("gaze_performance", "gazePerformance"),
    )
    hair: str = ""
    clothing: str = ""
    build_aura: str = Field(
        default="",
        validation_alias=AliasChoices("build_aura", "buildAura"),
    )
    canon_appearance: str = Field(
        default="",
        validation_alias=AliasChoices("canon_appearance", "canonAppearance"),
    )
    materials_and_motion: str = Field(
        default="",
        validation_alias=AliasChoices("materials_and_motion", "materialsAndMotion"),
    )


class SeedanceStage(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    time: str = ""
    purpose: str = ""
    initial_state: str = Field(
        default="",
        validation_alias=AliasChoices("initial_state", "initialState", "initialOrCarriedState"),
    )
    event: str = Field(
        min_length=1,
        validation_alias=AliasChoices("event", "primary_event", "primaryEvent"),
    )
    end_state: str = Field(
        min_length=1,
        validation_alias=AliasChoices("end_state", "endState", "observableEndState"),
    )
    emotion_or_camera: str = Field(
        default="",
        validation_alias=AliasChoices(
            "emotion_or_camera", "emotionOrCamera", "emotionOrCameraAnalysis"
        ),
    )


class SeedanceTask(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: SeedanceTaskType
    goal: str = Field(min_length=1)
    duration_seconds: Optional[float] = Field(
        default=None,
        gt=0,
        validation_alias=AliasChoices("duration_seconds", "durationSec", "duration"),
    )
    aspect_ratio: str = Field(
        default="16:9",
        validation_alias=AliasChoices("aspect_ratio", "aspectRatio"),
    )
    resolution: str = "720p"
    model_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("model_id", "modelId"),
    )
    assets: dict[str, Any] = Field(default_factory=dict)
    references: list[ReferenceBinding] = Field(default_factory=list)
    characters: list[CharacterProfile] = Field(default_factory=list)
    stages: list[SeedanceStage] = Field(default_factory=list)
    scene_style: str = Field(
        default="",
        validation_alias=AliasChoices("scene_style", "sceneStyle"),
    )
    camera: str = ""
    audio: str = (
        "Natural ambience, foley, designed non-dialogue sound effects, and low supportive "
        "underscore are allowed unless the task explicitly forbids them."
    )
    consistency: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    no_music: bool = Field(
        default=False,
        validation_alias=AliasChoices("no_music", "noMusic"),
    )
    extension_direction: Literal["forward", "backward"] = Field(
        default="forward",
        validation_alias=AliasChoices("extension_direction", "extensionDirection", "direction"),
    )
    source_video_tag: str = Field(
        default="@Video 1",
        validation_alias=AliasChoices("source_video_tag", "sourceVideoTag"),
    )
    edit_goal: str = Field(
        default="",
        validation_alias=AliasChoices("edit_goal", "editGoal"),
    )
    edit_scope: str = Field(
        default="",
        validation_alias=AliasChoices("edit_scope", "editScope"),
    )
    preserve: list[str] = Field(default_factory=list)
    before_video_tag: str = Field(
        default="@Video 1",
        validation_alias=AliasChoices("before_video_tag", "beforeVideoTag"),
    )
    after_video_tag: str = Field(
        default="@Video 2",
        validation_alias=AliasChoices("after_video_tag", "afterVideoTag"),
    )
    transition_trigger: str = Field(
        default="",
        validation_alias=AliasChoices("transition_trigger", "transitionTrigger"),
    )
    transition_transformation: str = Field(
        default="",
        validation_alias=AliasChoices("transition_transformation", "transitionTransformation"),
    )
    arrival_state: str = Field(
        default="",
        validation_alias=AliasChoices("arrival_state", "arrivalState"),
    )
    audio_transition: str = Field(
        default="",
        validation_alias=AliasChoices("audio_transition", "audioTransition"),
    )
    first_frame_tag: str = Field(
        default="@Image 1",
        validation_alias=AliasChoices("first_frame_tag", "firstFrameTag"),
    )
    last_frame_tag: str = Field(
        default="@Image 2",
        validation_alias=AliasChoices("last_frame_tag", "lastFrameTag"),
    )
    continuous_action: str = Field(
        default="",
        validation_alias=AliasChoices("continuous_action", "continuousAction"),
    )
    storyboard_tag: str = Field(
        default="@Image 1",
        validation_alias=AliasChoices("storyboard_tag", "storyboardTag"),
    )
    storyboard_reading_order: str = Field(
        default="left to right, top to bottom",
        validation_alias=AliasChoices("storyboard_reading_order", "storyboardReadingOrder"),
    )
    blockout_kind: Literal["coarse", "fine"] = Field(
        default="coarse",
        validation_alias=AliasChoices("blockout_kind", "blockoutKind"),
    )
    blockout_mappings: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("blockout_mappings", "blockoutMappings"),
    )


def _normalise_task_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    key = str(value).strip().lower().replace(" ", "_")
    if key in SEEDANCE_TASK_TYPES:
        return key
    key = key.replace("_", "-")
    return TASK_TYPE_ALIASES.get(key)


def classify_seedance_task(payload: dict[str, Any]) -> dict[str, Any]:
    """Classify a request deterministically; explicit supported types always win."""
    raw = dict(payload or {})
    explicit_value = raw.get("type") or raw.get("task_type") or raw.get("taskType")
    explicit = _normalise_task_type(explicit_value)
    if explicit_value and not explicit:
        raise ValueError(f"unsupported Seedance task type: {explicit_value}")
    if explicit:
        direction = str(raw.get("extension_direction") or raw.get("direction") or "").lower()
        if str(explicit_value).lower() == "extend-backward":
            direction = "backward"
        elif str(explicit_value).lower() == "extend-forward":
            direction = "forward"
        return {
            "type": explicit,
            "reason": "The request supplied an explicit supported task type.",
            "explicit": True,
            "extensionDirection": direction or None,
        }

    text = " ".join(str(raw.get(key) or "") for key in (
        "goal", "request", "instruction", "edit_goal", "editGoal"
    )).lower()
    duration = raw.get("duration_seconds", raw.get("durationSec", raw.get("duration")))
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    tests = (
        ("blockout_render", bool(raw.get("blockout_kind") or raw.get("blockoutKind") or
                                 "blockout" in text), "A blockout source or render instruction is present."),
        ("storyboard_grid", bool(raw.get("storyboard_tag") or raw.get("storyboardTag") or
                                 "storyboard grid" in text), "A storyboard grid is present."),
        ("first_last_frame", bool((raw.get("first_frame_tag") or raw.get("firstFrameTag")) and
                                  (raw.get("last_frame_tag") or raw.get("lastFrameTag")) or
                                  "first and last frame" in text),
         "First-frame and last-frame anchors are present."),
        ("seamless_transition", bool(raw.get("after_video_tag") or raw.get("afterVideoTag") or
                                     "seamless transition" in text or "connect @video" in text),
         "Before and after video transition inputs are present."),
        ("video_editing", bool(raw.get("edit_scope") or raw.get("editScope") or
                               raw.get("edit_goal") or raw.get("editGoal") or
                               re.search(r"\b(edit|replace|remove|recolor|recolour)\b", text)),
         "A bounded edit target or scope is present."),
        ("video_extension", bool(raw.get("extension_direction") or raw.get("extensionDirection") or
                                 re.search(r"\bextend(?:ing|s|ed)?\b", text)),
         "A forward or backward extension is requested."),
        ("ultra_long_video", bool(duration is not None and duration > 30),
         "The requested duration exceeds the standard 30-second window."),
        ("thirty_second_video", bool(duration is not None and duration > 15),
         "The requested duration needs the staged 16-30 second form."),
        ("reference_based_generation", bool(raw.get("references") or raw.get("assets")),
         "Reference materials are present."),
    )
    for task_type, matched, reason in tests:
        if matched:
            return {"type": task_type, "reason": reason, "explicit": False,
                    "extensionDirection": None}
    return {
        "type": "text_to_video",
        "reason": "No editing, extension, transition, anchor, blockout, or reference input was found.",
        "explicit": False,
        "extensionDirection": None,
    }


def _duration_of(item: Any) -> float:
    if not isinstance(item, dict):
        return 0.0
    value = item.get("duration_seconds", item.get("durationSec", item.get("duration", 0)))
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _subject_count(items: list[Any]) -> int:
    subjects = set()
    explicit = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        subject = item.get("subject") or item.get("name")
        if subject:
            subjects.add(str(subject).strip().lower())
        try:
            explicit = max(explicit, int(item.get("subject_count", item.get("subjectCount", 0)) or 0))
        except (TypeError, ValueError):
            pass
    return max(len(subjects), explicit)


def asset_validation_report(assets: dict[str, Any], task_type: Optional[str] = None) -> dict[str, Any]:
    assets = assets or {}
    images = list(assets.get("images") or [])
    videos = list(assets.get("videos") or [])
    audio = list(assets.get("audio") or [])
    errors, warnings = [], []
    video_duration = sum(_duration_of(item) for item in videos)
    audio_duration = sum(_duration_of(item) for item in audio)
    combined = len(images) + len(videos) + len(audio)

    if len(images) > 30:
        errors.append("Seedance 2.5 supports up to 30 images.")
    if len(videos) > 10:
        errors.append("Seedance 2.5 supports up to 10 videos.")
    if video_duration > 30.001:
        errors.append("Reference videos must not exceed 30 seconds combined.")
    if len(audio) > 10:
        errors.append("Seedance 2.5 supports up to 10 audio clips.")
    if audio_duration > 30.001:
        errors.append("Reference audio must not exceed 30 seconds combined.")
    if combined > 50:
        errors.append("Seedance 2.5 supports up to 50 combined reference materials.")

    image_subjects = _subject_count(images)
    video_subjects = _subject_count(videos)
    if image_subjects > 8:
        warnings.append("More than 8 image-reference subjects may reduce identity stability.")
    if video_subjects > 5:
        warnings.append("More than 5 video-reference subjects may reduce motion stability.")
    for label, items in (("video", videos), ("audio", audio)):
        outside = [_duration_of(item) for item in items
                   if _duration_of(item) and not 5 <= _duration_of(item) <= 10]
        if outside:
            warnings.append(
                f"{len(outside)} {label} reference clip(s) fall outside the recommended 5-10 second range.")

    normalised_type = _normalise_task_type(task_type) if task_type else None
    if normalised_type == "video_editing":
        source_duration = max((_duration_of(item) for item in videos), default=0)
        if source_duration > 20:
            warnings.append("Video-editing source footage over 20 seconds may reduce edit stability.")
        if not 1 <= len(images) <= 5:
            warnings.append("Video editing is most stable with 1-5 reference images.")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {"images": len(images), "videos": len(videos), "audio": len(audio),
                   "combined": combined},
        "durations": {"videos": video_duration, "audio": audio_duration},
        "subjectCounts": {"images": image_subjects, "videos": video_subjects},
        "limits": SEEDANCE_LIMITS,
    }


def validate_seedance_assets(assets: dict[str, Any]) -> list[str]:
    """Compatibility helper matching the guide's simple validation signature."""
    return asset_validation_report(assets)["errors"]


def _tag_kind(tag: str) -> str:
    low = str(tag).lower()
    if low.startswith("@audio"):
        return "audio"
    if low.startswith("@video"):
        return "video"
    return "image"


def format_reference_binding(reference: ReferenceBinding | dict[str, Any]) -> str:
    ref = reference if isinstance(reference, ReferenceBinding) else ReferenceBinding.model_validate(reference)
    subject = ref.subject if ref.subject.startswith("<") else f"<{ref.subject}>"
    return f"{ref.tag} defines {subject}'s {ref.defines}. Do not use {ref.exclude}."


def build_character_profile(character: CharacterProfile | dict[str, Any]) -> str:
    item = character if isinstance(character, CharacterProfile) else CharacterProfile.model_validate(character)
    if item.kind == "human":
        fields = (
            ("Age / ethnicity", item.age_ethnicity),
            ("Skin", item.skin),
            ("Facial details", item.facial_details),
            ("Gaze and performance", item.gaze_performance),
            ("Hair", item.hair),
            ("Clothing", item.clothing),
            ("Build and aura", item.build_aura),
        )
    else:
        fields = (
            ("Canon appearance", item.canon_appearance or item.facial_details),
            ("Observable performance", item.gaze_performance),
            ("Materials and motion", item.materials_and_motion),
            ("Clothing or fixed details", item.clothing),
            ("Build and presence", item.build_aura),
        )
    body = "\n".join(f"{label}: {value}" for label, value in fields if value)
    return f"[Subject Profile: {item.name}]\n{body}".strip()


def _parse_time_point(value: str) -> float:
    if ":" not in value:
        return float(value)
    minutes, seconds = value.split(":", 1)
    return float(minutes) * 60 + float(seconds)


def _parse_time_range(value: str) -> Optional[tuple[float, float]]:
    match = _TIME_RANGE_PATTERN.match(str(value or ""))
    if not match:
        return None
    return _parse_time_point(match.group(1)), _parse_time_point(match.group(2))


def timeline_validation_report(stages: list[SeedanceStage], duration_seconds=None) -> dict[str, Any]:
    errors, warnings = [], []
    ranges = []
    for index, stage in enumerate(stages, start=1):
        if not stage.event.strip():
            errors.append(f"Stage {index} needs one primary visible event.")
        if not stage.end_state.strip():
            errors.append(f"Stage {index} needs an explicit visible end state.")
        if stage.time:
            parsed = _parse_time_range(stage.time)
            if parsed is None:
                errors.append(f"Stage {index} has an invalid time range: {stage.time}")
            else:
                start, end = parsed
                if start >= end:
                    errors.append(f"Stage {index} must end after it starts.")
                ranges.append((index, start, end))

    if ranges and len(ranges) != len(stages):
        errors.append("Either time every stage or omit timing from every stage.")
    if len(ranges) > 1:
        for current, previous in zip(ranges[1:], ranges[:-1]):
            if current[1] < previous[2] - 0.001:
                errors.append(f"Stage {current[0]} overlaps Stage {previous[0]}.")
            elif current[1] > previous[2] + 0.001:
                errors.append(f"Stage {current[0]} leaves a gap after Stage {previous[0]}.")
    if ranges and duration_seconds is not None:
        duration = float(duration_seconds)
        if abs(ranges[0][1]) > 0.001:
            errors.append("The first timed stage must begin at 0 seconds.")
        if abs(ranges[-1][2] - duration) > 0.05:
            errors.append("Timed stages must cover the complete requested duration.")
    if duration_seconds and float(duration_seconds) > 10 and not stages:
        errors.append("Videos over 10 seconds need stages or timestamp ranges.")
    if duration_seconds and float(duration_seconds) > 15 and stages and not ranges:
        warnings.append("For 16-30 second work, timestamped stages provide stronger pacing control.")
    return {"ok": not errors, "errors": errors, "warnings": warnings,
            "timed": bool(ranges), "ranges": ranges}


def format_stage(stage: SeedanceStage | dict[str, Any]) -> str:
    item = stage if isinstance(stage, SeedanceStage) else SeedanceStage.model_validate(stage)
    prefix = f"{item.time}: " if item.time else ""
    initial = f"Initial state: {item.initial_state} " if item.initial_state else ""
    return f"{prefix}{initial}{item.event} End state: {item.end_state}".strip()


def _task_model(task: SeedanceTask | dict[str, Any]) -> SeedanceTask:
    if isinstance(task, SeedanceTask):
        return task
    raw = dict(task or {})
    classification = classify_seedance_task(raw)
    raw["type"] = classification["type"]
    if classification.get("extensionDirection") and not (
            raw.get("extension_direction") or raw.get("extensionDirection") or raw.get("direction")):
        raw["extension_direction"] = classification["extensionDirection"]
    if raw["type"] == "thirty_second_video" and not any(
            key in raw for key in ("duration_seconds", "durationSec", "duration")):
        raw["duration_seconds"] = 30
    return SeedanceTask.model_validate(raw)


def _unique(items: list[str]) -> list[str]:
    seen, output = set(), []
    for item in items:
        clean = str(item).strip().rstrip(".")
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
    return output


def build_forbidden_list(task: SeedanceTask | dict[str, Any]) -> str:
    item = _task_model(task)
    forbidden = list(DEFAULT_FORBIDDEN)
    if item.no_music:
        forbidden.extend(("no unwanted background music", "no BGM"))
    if len(item.references) > 1:
        forbidden.append("do not mix identities between references")
    if item.references:
        forbidden.append("do not use reference backgrounds unless explicitly assigned")
    if any(character.kind == "human" for character in item.characters):
        forbidden.extend(("no clone faces", "no distorted hands or extra fingers"))
    if item.type == "video_extension":
        forbidden.extend(("no hard cuts at the extension boundary",
                          "no objects appearing out of thin air", "no duplicate subjects"))
    if item.type == "video_editing":
        forbidden.append("do not modify anything outside the edit scope")
    if item.type == "seamless_transition":
        forbidden.extend(("do not modify the original source videos",
                          "no black frames, flickering, or frame skipping"))
    if item.type == "storyboard_grid":
        forbidden.extend(("do not reproduce storyboard text labels",
                          "do not retain line-art styling unless explicitly requested"))
    if item.type == "blockout_render":
        forbidden.extend(("no gray blockout materials", "no path lines or coordinate axes",
                          "no controllers or camera cones"))
    forbidden.extend(item.forbidden)
    unique = _unique(forbidden)
    return ", ".join(unique) + "." if unique else ""


def _strip_request_parameters(value: str) -> str:
    result = str(value or "")
    for pattern in _REQUEST_PARAMETER_PATTERNS:
        result = pattern.sub("", result)
    result = re.sub(r"\s+", " ", result)
    result = re.sub(r"\s+([,.;:])", r"\1", result)
    return result.strip()


def _consistency_text(task: SeedanceTask) -> str:
    values = task.consistency or [
        "Keep character identity, count, clothing, prop ownership, scene geography, lighting logic, camera axis, and audio relationships consistent."
    ]
    return " ".join(value.rstrip(".") + "." for value in values)


def _reference_section(task: SeedanceTask) -> list[str]:
    if not task.references:
        return []
    return ["[Reference Roles]", *(format_reference_binding(ref) for ref in task.references)]


def _profile_section(task: SeedanceTask) -> list[str]:
    if not task.characters:
        return []
    return ["[Subject Profiles]", *(build_character_profile(character)
                                     for character in task.characters)]


def _style_camera_timeline(task: SeedanceTask) -> list[str]:
    sections = []
    if task.scene_style:
        sections.extend(("[Scene and Visual Style]", task.scene_style))
    if task.camera:
        sections.extend(("[Camera]", task.camera))
    if task.stages:
        sections.append("[Timeline]")
        for index, stage in enumerate(task.stages, start=1):
            heading = f"[Stage {index}" + (f" | {stage.time}" if stage.time else "") + "]"
            sections.append(heading)
            if stage.initial_state:
                sections.append(f"Initial state: {stage.initial_state}")
            elif index > 1:
                sections.append("Continue from the previous stage: preserve the preceding visible end state.")
            sections.append(f"Primary event: {stage.event}")
            if stage.emotion_or_camera:
                sections.append(f"Emotion / camera analysis: {stage.emotion_or_camera}")
            sections.append(f"End state: {stage.end_state}")
    return sections


def build_seedance_prompt(task: SeedanceTask | dict[str, Any]) -> str:
    item = _task_model(task)
    goal = _strip_request_parameters(item.goal)
    sections: list[str] = []

    if item.type in {"text_to_video", "reference_based_generation"}:
        sections.extend(_reference_section(item))
        sections.extend(_profile_section(item))
        sections.extend(("[Generation Goal]", goal))
        sections.extend(_style_camera_timeline(item))
        sections.extend(("[Maintain Consistency]", _consistency_text(item)))
    elif item.type in {"thirty_second_video", "ultra_long_video"}:
        sections.extend(_reference_section(item))
        sections.extend(_profile_section(item))
        sections.extend(("[Generation Goal]", goal))
        if item.scene_style or item.camera:
            sections.extend(("[Global Scene Setting]",
                             " ".join(value for value in (item.scene_style, item.camera) if value)))
        for index, stage in enumerate(item.stages, start=1):
            heading = f"[Stage {index}" + (f" | {stage.time}" if stage.time else "") + "]"
            sections.append(heading)
            if stage.initial_state:
                sections.append(f"Initial state: {stage.initial_state}")
            sections.append(f"Primary event: {stage.event}")
            if stage.emotion_or_camera:
                sections.append(f"Emotion / camera analysis: {stage.emotion_or_camera}")
            sections.append(f"End state: {stage.end_state}")
        sections.extend(("[Maintain Consistency]", _consistency_text(item)))
    elif item.type == "video_extension":
        direction = item.extension_direction
        boundary_source = "last" if direction == "forward" else "first"
        boundary_output = "first" if direction == "forward" else "last"
        sections.extend(_reference_section(item))
        sections.extend((
            "[Extension Goal]",
            f"{item.source_video_tag} is the source video to extend {direction}.",
            f"Extend {item.source_video_tag} {direction}. The {boundary_output} frame of the extended segment directly connects to the {boundary_source} frame of {item.source_video_tag}.",
            "Maintain the source boundary's subject pose and orientation, prop positions, background layout, camera position and composition, lighting, motion direction, and audio state.",
            "[New Event]",
            goal,
            "[Maintain Consistency]",
            _consistency_text(item) + " Keep each subject as the same continuous instance throughout.",
        ))
        sections.extend(_style_camera_timeline(item))
    elif item.type == "video_editing":
        sections.extend((
            "[Edit Goal]",
            _strip_request_parameters(item.edit_goal or item.goal),
            "[Source Video Role]",
            f"{item.source_video_tag} is the sole editing master. It defines the characters, scene, actions, composition, camera movement, occlusion relationships, audio, timing, and event order.",
        ))
        sections.extend(_reference_section(item))
        sections.extend((
            "[Edit Scope]",
            item.edit_scope or "Modify only the explicitly named target and time range.",
            "[Content to Preserve]",
            " ".join(item.preserve) or _consistency_text(item),
        ))
    elif item.type == "seamless_transition":
        sections.extend((
            "[Transition Goal]",
            f"{item.before_video_tag} is the before-transition clip. {item.after_video_tag} is the after-transition clip. Connect them without modifying either source clip.",
            "[Transition Trigger]", item.transition_trigger,
            "[Camera and Visual Transformation]",
            " ".join(value for value in (item.camera, item.transition_transformation) if value),
            "[Arrival State]", item.arrival_state,
            "[Audio Transition]", item.audio_transition or item.audio,
        ))
    elif item.type == "first_last_frame":
        sections.extend((
            "[Generation Goal]", goal,
            "[First and Last Frame Roles]",
            f"{item.first_frame_tag} is the first frame. It defines the opening composition, subject position, pose, prop state, scene, and camera direction.",
            f"{item.last_frame_tag} is the last frame. It defines the ending composition, subject position, pose, prop state, scene, and camera direction.",
        ))
        sections.extend(_reference_section(item))
        sections.extend((
            "[Continuous Action]", item.continuous_action or goal,
            "The video begins naturally from the first frame and reaches the assigned last frame through one continuous event.",
            "[Maintain Consistency]", _consistency_text(item),
        ))
        sections.extend(_style_camera_timeline(item))
    elif item.type == "storyboard_grid":
        sections.extend((
            "[Storyboard Role]",
            f"{item.storyboard_tag} provides the storyboard grid for shot order and approximate composition. Read it {item.storyboard_reading_order}. Do not use its line-art style, text labels, or placeholder characters.",
        ))
        sections.extend(_reference_section(item))
        sections.extend(_profile_section(item))
        sections.extend(("[Generation Goal]", goal, "[Shot Plan]"))
        for index, stage in enumerate(item.stages, start=1):
            sections.append(f"Shot {index}: {stage.event} End state: {stage.end_state}")
        if item.scene_style:
            sections.extend(("[Scene and Visual Style]", item.scene_style))
        if item.camera:
            sections.extend(("[Camera]", item.camera))
        sections.extend(("[Maintain Consistency]", _consistency_text(item)))
    else:
        kind = item.blockout_kind
        inheritance = (
            "motion paths, subject blocking, camera position and movement, cuts, lighting changes, sound rhythm, and spatial relationships"
            if kind == "coarse" else
            "subject structure, action, spatial layout, camera position and movement, and cuts"
        )
        exclusions = (
            "Do not use its blockout appearance, gray materials, production markers, or empty scene."
            if kind == "coarse" else
            "Do not use its original gray materials, production markers, or empty background."
        )
        sections.extend((
            "[Blockout Role]",
            f"{item.source_video_tag} is a {kind} blockout reference. Preserve only {inheritance}. {exclusions}",
            *item.blockout_mappings,
        ))
        sections.extend(_reference_section(item))
        sections.extend(_profile_section(item))
        sections.extend(("[Generation Goal]", goal))
        sections.extend(_style_camera_timeline(item))
        sections.extend(("[Maintain Consistency]", _consistency_text(item)))

    if item.type not in {"seamless_transition"}:
        sections.extend(("[Audio]", item.audio))
    forbidden_text = build_forbidden_list(item)
    if forbidden_text:
        sections.extend(("[Forbidden]", forbidden_text))
    return "\n".join(str(section).strip() for section in sections if str(section).strip())


def _reference_counts(task: SeedanceTask) -> dict[str, int]:
    counts = {"images": 0, "videos": 0, "audio": 0}
    for key in counts:
        counts[key] = len(task.assets.get(key) or [])
    if not any(counts.values()):
        for ref in task.references:
            counts[_tag_kind(ref.tag) + "s"] += 1
    return counts


def validate_seedance_task(task: SeedanceTask | dict[str, Any]) -> dict[str, Any]:
    item = _task_model(task)
    errors, warnings = [], []
    assets = asset_validation_report(item.assets, item.type)
    errors.extend(assets["errors"])
    warnings.extend(assets["warnings"])

    tags = [ref.tag.lower().replace(" ", "") for ref in item.references]
    if len(tags) != len(set(tags)):
        errors.append("Every reference tag must be unique.")
    required_refs = item.type not in {"text_to_video", "thirty_second_video", "ultra_long_video"}
    if required_refs and not item.references:
        errors.append(f"{item.type} requires explicitly bound references.")

    timeline = timeline_validation_report(item.stages, item.duration_seconds)
    errors.extend(timeline["errors"])
    warnings.extend(timeline["warnings"])

    duration = item.duration_seconds
    if duration is None:
        errors.append("A generation duration is required in request settings.")
    elif item.type in {"text_to_video", "reference_based_generation", "first_last_frame",
                      "storyboard_grid", "blockout_render", "video_editing",
                      "seamless_transition"} and not 4 <= duration <= 30:
        errors.append("This Seedance task requires a 4-30 second standard request duration.")
    elif item.type == "thirty_second_video" and not 16 <= duration <= 30:
        errors.append("A thirty-second staged task must be 16-30 seconds.")
    elif item.type == "ultra_long_video" and not 30 <= duration <= 180:
        errors.append("Ultra-Long authoring requires a 30-180 second duration.")
    elif item.type == "video_extension" and not 4 <= duration <= 30:
        errors.append("Each extension pass must request 4-30 seconds of new material.")

    if item.type == "video_editing":
        if not item.edit_scope:
            errors.append("Video editing requires an exact edit scope.")
        if not item.preserve:
            errors.append("Video editing requires an explicit preserve-list.")
    if item.type == "video_extension" and not item.source_video_tag:
        errors.append("Video extension requires a source-video tag.")
    if item.type == "seamless_transition":
        for value, label in ((item.transition_trigger, "trigger"),
                             (item.transition_transformation, "visual transformation"),
                             (item.arrival_state, "arrival state"),
                             (item.audio_transition, "audio crossover")):
            if not value:
                errors.append(f"Seamless transition requires a {label}.")
    if item.type == "first_last_frame":
        normalised = {tag.lower().replace(" ", "") for tag in tags}
        for tag, label in ((item.first_frame_tag, "first frame"),
                           (item.last_frame_tag, "last frame")):
            if tag.lower().replace(" ", "") not in normalised:
                errors.append(f"The {label} tag {tag} must have an explicit reference binding.")
    if item.type == "storyboard_grid" and item.storyboard_tag.lower().replace(" ", "") not in tags:
        errors.append("The storyboard grid must have an explicit reference binding.")
    if item.type == "blockout_render":
        if item.source_video_tag.lower().replace(" ", "") not in tags:
            errors.append("The blockout source video must have an explicit reference binding.")
        if not item.blockout_mappings:
            warnings.append("Map every blockout subject or primitive to its final subject.")

    names = [character.name.strip().lower() for character in item.characters]
    if len(names) != len(set(names)):
        errors.append("Every character profile must have a unique name.")
    if not item.consistency:
        warnings.append("Use a task-specific consistency contract for identity, ownership, geography, and audio.")
    if item.no_music and "music" not in item.audio.lower() and "bgm" not in item.audio.lower():
        warnings.append("State the no-music sound directive explicitly in the audio contract.")

    return {"ok": not errors, "errors": _unique(errors), "warnings": _unique(warnings),
            "assets": assets, "timeline": timeline}


def qualify_provider_request(task: SeedanceTask | dict[str, Any]) -> dict[str, Any]:
    """Check the executable registry only; this function performs no network or provider call."""
    item = _task_model(task)
    counts = _reference_counts(item)
    if item.type != "reference_based_generation":
        return {
            "checked": True,
            "ready": False,
            "providerCalled": False,
            "reason": f"No enabled provider route is qualified for {item.type}.",
            "mode": None,
        }
    if item.duration_seconds is None:
        return {"checked": True, "ready": False, "providerCalled": False,
                "reason": "Provider qualification needs a duration.", "mode": "reference-to-video"}
    try:
        model = cb_providers.validate_video_request(
            mode="reference-to-video",
            duration=item.duration_seconds,
            resolution=item.resolution,
            image_count=counts["images"],
            audio_count=counts["audio"],
            video_count=counts["videos"],
            model_id=item.model_id,
        )
    except cb_providers.ProviderCapabilityError as exc:
        return {"checked": True, "ready": False, "providerCalled": False,
                "reason": str(exc), "mode": "reference-to-video"}
    return {
        "checked": True,
        "ready": True,
        "providerCalled": False,
        "reason": "The request fits the enabled, verified provider contract.",
        "mode": "reference-to-video",
        "providerModelId": model.modelId,
        "provider": model.provider,
        "modelVersion": model.modelVersion,
        "capabilityVerifiedAt": model.verifiedAt,
        "capabilitySource": model.sourceUrl,
    }


def _checklist(task: SeedanceTask, validation: dict[str, Any], provider: dict[str, Any]) -> list[dict[str, Any]]:
    refs_required = task.type not in {"text_to_video", "thirty_second_video", "ultra_long_video"}
    values = OrderedDict([
        (PRE_SUBMISSION_CHECKLIST[0], task.type in SEEDANCE_TASK_TYPES),
        (PRE_SUBMISSION_CHECKLIST[1], bool(task.references) or not refs_required),
        (PRE_SUBMISSION_CHECKLIST[2], len({item.name.lower() for item in task.characters}) == len(task.characters)),
        (PRE_SUBMISSION_CHECKLIST[3], all(bool(ref.exclude) for ref in task.references)),
        (PRE_SUBMISSION_CHECKLIST[4], bool(task.goal and task.audio)),
        (PRE_SUBMISSION_CHECKLIST[5], not task.duration_seconds or task.duration_seconds <= 10 or bool(task.stages)),
        (PRE_SUBMISSION_CHECKLIST[6], all(bool(stage.event) for stage in task.stages)),
        (PRE_SUBMISSION_CHECKLIST[7], all(bool(stage.end_state) for stage in task.stages)),
        (PRE_SUBMISSION_CHECKLIST[8], bool(task.consistency)),
        (PRE_SUBMISSION_CHECKLIST[9], task.type != "video_editing" or bool(task.source_video_tag)),
        (PRE_SUBMISSION_CHECKLIST[10], task.type != "video_editing" or bool(task.edit_scope and task.preserve)),
        (PRE_SUBMISSION_CHECKLIST[11], task.type != "video_extension" or bool(task.source_video_tag)),
        (PRE_SUBMISSION_CHECKLIST[12], task.type != "seamless_transition" or all((
            task.transition_trigger, task.transition_transformation, task.arrival_state,
            task.audio_transition))),
        (PRE_SUBMISSION_CHECKLIST[13], all(bool(stage.emotion_or_camera) for stage in task.stages) if task.stages else True),
        (PRE_SUBMISSION_CHECKLIST[14], bool(build_forbidden_list(task))),
        (PRE_SUBMISSION_CHECKLIST[15], provider["checked"]),
    ])
    return [{"item": label, "passed": bool(passed)} for label, passed in values.items()]


class SeedancePromptBuilder:
    def __init__(self, task: SeedanceTask | dict[str, Any]):
        self.classification = classify_seedance_task(
            task.model_dump() if isinstance(task, SeedanceTask) else dict(task or {}))
        self.task = _task_model(task)

    def validation_report(self) -> dict[str, Any]:
        return validate_seedance_task(self.task)

    def validate(self) -> list[str]:
        return self.validation_report()["errors"]

    def build(self) -> str:
        errors = self.validate()
        if errors:
            raise ValueError("Invalid Seedance task: " + "; ".join(errors))
        return build_seedance_prompt(self.task)

    def preflight(self, existing_prompt: Optional[str] = None) -> dict[str, Any]:
        validation = self.validation_report()
        provider = qualify_provider_request(self.task)
        prompt = str(existing_prompt or "").strip()
        source = "approved-existing" if prompt else "deterministic-compiler"
        if not prompt and validation["ok"]:
            prompt = build_seedance_prompt(self.task)
        request_settings = {
            "durationSec": self.task.duration_seconds,
            "aspectRatio": self.task.aspect_ratio,
            "resolution": self.task.resolution,
            "modelId": self.task.model_id or cb_providers.selected_video_model_id(),
        }
        checklist = _checklist(self.task, validation, provider)
        return {
            "zeroSpend": True,
            "providerCalled": False,
            "approvalChanged": False,
            "classification": self.classification,
            "taskType": self.task.type,
            "promptLabTaskMode": (
                "extend-" + self.task.extension_direction
                if self.task.type == "video_extension" else
                PROMPT_LAB_TASK_MODES[self.task.type]
            ),
            "promptSource": source,
            "approvedPromptPreserved": bool(existing_prompt),
            "providerPrompt": prompt,
            "promptHash": hashlib.sha256(prompt.encode()).hexdigest() if prompt else None,
            "requestSettings": request_settings,
            "validation": validation,
            "checklist": checklist,
            "providerQualification": provider,
            "readyForPrompt": validation["ok"] and bool(prompt),
            "readyForProvider": validation["ok"] and provider["ready"] and bool(prompt),
        }


def analyze_retry(issues: list[str], *, has_source_video=True) -> dict[str, Any]:
    normalised = [str(issue).strip() for issue in issues if str(issue).strip()]
    lower = " ".join(normalised).lower()
    structural = any(term in lower for term in ("timing", "stage skipped", "too fast"))
    boundary = any(term in lower for term in ("hard cut", "out of thin air", "boundary"))
    if structural:
        action = "regenerate_defective_segment"
        reason = "Timing or event order needs a bounded regeneration of the defective segment."
    elif boundary:
        action = "repair_boundary"
        reason = "The successful source should be preserved while only the boundary is rebuilt."
    elif has_source_video:
        action = "video_editing"
        reason = "The listed defect is local and the successful source footage can remain the editing master."
    else:
        action = "regenerate_defective_segment"
        reason = "No editable source was supplied, so only the defective generation unit should be rerun."
    return {
        "action": action,
        "reason": reason,
        "issues": normalised,
        "preserveSuccessfulParts": True,
        "fullEpisodeRegeneration": False,
        "humanApprovalRequired": True,
        "zeroSpendPlanning": True,
        "providerCalled": False,
    }


def build_retry_prompt(original_prompt: str, issues: list[str]) -> str:
    analysis = analyze_retry(issues)
    issue_lines = "\n".join(f"- {issue}" for issue in analysis["issues"])
    return (
        "[Retry Correction]\n"
        "Use the original prompt below, but correct only the listed issues:\n"
        f"{issue_lines}\n"
        "[Original Prompt]\n"
        f"{str(original_prompt).strip()}\n"
        "[Preserve]\n"
        "Preserve every successful character, prop, action, camera, lighting, audio, and timing relationship not named above.\n"
        "[Additional Constraints]\n"
        "Do not introduce new characters, props, camera movements, subtitles, dialogue, or background music unless explicitly requested. Human review is required before any further action."
    )
