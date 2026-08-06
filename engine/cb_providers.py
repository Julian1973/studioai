#!/usr/bin/env python3
"""Verified provider capabilities for generation requests.

The registry is operational evidence, not marketing copy. Disabled entries may describe a
route worth qualifying, but no caller can submit through them. This module has no network
or secret access and cannot spend.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


HERE = pathlib.Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "provider_capabilities.json"
REGISTRY_SCHEMA_VERSION = 1
COMPARISON_MODEL_ID = "fal-seedance-2.0"
COMPARISON_ENDPOINT = "bytedance/seedance-2.0/reference-to-video"


class ProviderCapabilityError(RuntimeError):
    """A provider route is absent, disabled, unverified or outside its proven limits."""


class DurationCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minSec: Optional[float] = Field(default=None, gt=0)
    maxSec: Optional[float] = Field(default=None, gt=0)
    supportsAuto: bool = False

    @model_validator(mode="after")
    def ordered(self):
        if self.minSec is not None and self.maxSec is not None and self.minSec > self.maxSec:
            raise ValueError("provider duration minSec exceeds maxSec")
        return self


class ReferenceLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: Optional[int] = Field(default=None, ge=0)
    audio: Optional[int] = Field(default=None, ge=0)
    video: Optional[int] = Field(default=None, ge=0)
    recommendedCombined: Optional[int] = Field(default=None, ge=0)


class VideoModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modelId: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    displayName: str = Field(min_length=1)
    modelVersion: str = Field(min_length=1)
    transport: str = Field(min_length=1)
    enabled: bool
    status: Literal["production", "qualification-required", "unverified", "retired"]
    verifiedAt: str = Field(min_length=1)
    sourceUrl: str = Field(min_length=1)
    endpoints: Dict[str, str]
    modes: List[str]
    duration: DurationCapability
    referenceLimits: ReferenceLimits
    resolutions: List[str]
    nativeAudio: Optional[bool]
    costRateKeys: Dict[str, str]
    fallbackModelId: Optional[str]
    disableReason: Optional[str]

    @model_validator(mode="after")
    def enabled_route_is_complete(self):
        if self.enabled:
            if self.status != "production":
                raise ValueError("enabled provider model must have production status")
            if not self.modes or any(mode not in self.endpoints for mode in self.modes):
                raise ValueError("enabled provider model is missing an endpoint for a mode")
            if any(mode not in self.costRateKeys for mode in self.modes):
                raise ValueError("enabled provider model is missing a cost rate for a mode")
            if self.duration.minSec is None or self.duration.maxSec is None:
                raise ValueError("enabled provider model has unverified duration limits")
            if not self.resolutions:
                raise ValueError("enabled provider model has no verified resolution")
        elif not self.disableReason:
            raise ValueError("disabled provider model must state why it is disabled")
        return self


class ProviderRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: int
    defaultVideoModelId: str
    models: List[VideoModelCapability]

    @model_validator(mode="after")
    def unique_and_default_present(self):
        ids = [model.modelId for model in self.models]
        if len(ids) != len(set(ids)):
            raise ValueError("provider registry contains duplicate model IDs")
        default = next((model for model in self.models
                        if model.modelId == self.defaultVideoModelId), None)
        if default is None:
            raise ValueError("default video model must exist")
        return self


def load_registry(path=None):
    registry_path = pathlib.Path(path or REGISTRY_PATH)
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
        registry = ProviderRegistry.model_validate(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ProviderCapabilityError(
            f"provider capability registry is unreadable: {registry_path}") from exc
    if registry.schemaVersion != REGISTRY_SCHEMA_VERSION:
        raise ProviderCapabilityError("provider capability registry schema is unsupported")
    return registry


def selected_video_model_id(registry=None):
    registry = registry or load_registry()
    return os.environ.get("CB_VIDEO_MODEL_ID", registry.defaultVideoModelId).strip()


def video_model(model_id=None, *, require_enabled=True, registry=None):
    registry = registry or load_registry()
    wanted = str(model_id or selected_video_model_id(registry)).strip()
    model = next((item for item in registry.models if item.modelId == wanted), None)
    if model is None:
        raise ProviderCapabilityError(f"unknown video model: {wanted}")
    if require_enabled and not model.enabled:
        raise ProviderCapabilityError(
            f"video model {wanted} is disabled: {model.disableReason}")
    return model


def _validate_video_request_for_model(model, *, mode, duration, resolution,
                                      image_count=0, audio_count=0, video_count=0):
    """Validate request shape against one already-selected capability record."""
    mode = str(mode)
    if mode not in model.modes or mode not in model.endpoints:
        raise ProviderCapabilityError(
            f"{model.modelId} does not have a verified {mode} route")
    if resolution not in model.resolutions:
        raise ProviderCapabilityError(
            f"{model.modelId} does not verify resolution {resolution}; "
            f"allowed: {', '.join(model.resolutions)}")
    if str(duration) == "auto":
        if not model.duration.supportsAuto:
            raise ProviderCapabilityError(f"{model.modelId} does not verify automatic duration")
    else:
        try:
            seconds = float(duration)
        except (TypeError, ValueError) as exc:
            raise ProviderCapabilityError("video duration must be numeric or 'auto'") from exc
        if seconds < model.duration.minSec or seconds > model.duration.maxSec:
            raise ProviderCapabilityError(
                f"{model.modelId} duration must be {model.duration.minSec:g}-"
                f"{model.duration.maxSec:g}s; got {seconds:g}s")
    counts = {"images": int(image_count), "audio": int(audio_count), "video": int(video_count)}
    for key, count in counts.items():
        limit = getattr(model.referenceLimits, key)
        if count < 0 or limit is None or count > limit:
            raise ProviderCapabilityError(
                f"{model.modelId} accepts at most {limit if limit is not None else 'an unverified number of'} "
                f"{key} reference(s); got {count}")
    if mode.startswith("reference-to-video") and not image_count and not video_count:
        raise ProviderCapabilityError("reference-to-video requires an image or video reference")
    return model


def validate_video_request(*, mode, duration, resolution, image_count=0,
                           audio_count=0, video_count=0, model_id=None):
    """Validate one production request before upload or provider contact."""
    model = video_model(model_id)
    return _validate_video_request_for_model(
        model, mode=mode, duration=duration, resolution=resolution,
        image_count=image_count, audio_count=audio_count, video_count=video_count)


def request_contract(*, fast=False, duration, resolution="720p", image_count=0,
                     audio_count=0, video_count=0, model_id=None):
    mode = "reference-to-video-fast" if fast else "reference-to-video"
    model = validate_video_request(
        mode=mode, duration=duration, resolution=resolution,
        image_count=image_count, audio_count=audio_count, video_count=video_count,
        model_id=model_id)
    return {
        "providerModelId": model.modelId,
        "provider": model.provider,
        "modelVersion": model.modelVersion,
        "transport": model.transport,
        "mode": mode,
        "endpoint": model.endpoints[mode],
        "resolution": resolution,
        "duration": duration,
        "costRateKey": model.costRateKeys.get(mode),
        "capabilityVerifiedAt": model.verifiedAt,
        "capabilitySource": model.sourceUrl,
    }


def comparison_request_contract(*, comparison_run_id, fast=False, duration,
                                resolution="720p", image_count=0,
                                audio_count=0, video_count=0,
                                model_id=None):
    """Qualify one explicit 2.0 comparison call inside the canonical render path.

    Normal model selection remains fail-closed on the unqualified 2.5 target. This function
    permits only the recorded fal 2.0 evidence contract, and only when cb_render has already
    labelled the same-process comparison. It cannot select a fallback or contact a provider.
    """
    comparison_run_id = str(comparison_run_id or "").strip()
    if not comparison_run_id or len(comparison_run_id) > 120:
        raise ProviderCapabilityError("a bounded comparison run ID is required")
    if model_id != COMPARISON_MODEL_ID:
        raise ProviderCapabilityError(
            "the comparison route permits only fal-seedance-2.0")
    model = video_model(model_id, require_enabled=False)
    expected = (
        not model.enabled and model.status == "retired" and model.provider == "fal" and
        model.modelVersion == "2.0" and model.transport == "fal-subscribe" and
        model.endpoints.get("reference-to-video") == COMPARISON_ENDPOINT
    )
    if not expected:
        raise ProviderCapabilityError(
            "the Seedance 2.0 evidence record changed; re-qualify the comparison route")
    mode = "reference-to-video-fast" if fast else "reference-to-video"
    model = _validate_video_request_for_model(
        model, mode=mode, duration=duration, resolution=resolution,
        image_count=image_count, audio_count=audio_count, video_count=video_count)
    return {
        "providerModelId": model.modelId,
        "provider": model.provider,
        "modelVersion": model.modelVersion,
        "transport": model.transport,
        "mode": mode,
        "endpoint": model.endpoints[mode],
        "resolution": resolution,
        "duration": duration,
        "costRateKey": model.costRateKeys.get(mode),
        "capabilityVerifiedAt": model.verifiedAt,
        "capabilitySource": model.sourceUrl,
        "comparisonRunId": comparison_run_id,
    }


def image_to_video_contract(*, duration, resolution="720p", image_count=1,
                            model_id=None):
    model = validate_video_request(
        mode="image-to-video", duration=duration, resolution=resolution,
        image_count=image_count, model_id=model_id)
    return {
        "providerModelId": model.modelId,
        "provider": model.provider,
        "modelVersion": model.modelVersion,
        "transport": model.transport,
        "mode": "image-to-video",
        "endpoint": model.endpoints["image-to-video"],
        "resolution": resolution,
        "duration": duration,
        "costRateKey": model.costRateKeys["image-to-video"],
        "capabilityVerifiedAt": model.verifiedAt,
        "capabilitySource": model.sourceUrl,
    }


def capability_report(registry=None):
    """Return a secret-free status report suitable for preflight and the local UI."""
    registry = registry or load_registry()
    selected = selected_video_model_id(registry)
    rows = []
    for model in registry.models:
        rows.append({
            "modelId": model.modelId,
            "displayName": model.displayName,
            "provider": model.provider,
            "modelVersion": model.modelVersion,
            "enabled": model.enabled,
            "selected": model.modelId == selected,
            "status": model.status,
            "verifiedAt": model.verifiedAt,
            "modes": model.modes,
            "maxDurationSec": model.duration.maxSec,
            "referenceLimits": model.referenceLimits.model_dump(),
            "resolutions": model.resolutions,
            "fallbackModelId": model.fallbackModelId,
            "disableReason": model.disableReason,
            "sourceUrl": model.sourceUrl,
        })
    selection_error = None
    try:
        video_model(selected, registry=registry)
    except ProviderCapabilityError as exc:
        selection_error = str(exc)
    return {
        "schemaVersion": registry.schemaVersion,
        "zeroSpend": True,
        "selectedVideoModelId": selected,
        "selectionReady": selection_error is None,
        "selectionError": selection_error,
        "models": rows,
    }
