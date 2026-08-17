#!/usr/bin/env python3
"""Deterministic provider identity records for intact character turnarounds.

The locked turnaround sheet is the identity authority and is always sent intact. A provider
must see every approved angle, marking and proportion together; production code must never
crop the sheet into separate attachments or silently replace it with derived artwork.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

import cb_canon


IDENTITY_PACK_SCHEMA_VERSION = 1


class IdentityPackError(RuntimeError):
    """The declared provider identity view is missing, malformed or unsafe."""


def _contract_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def materialize_provider_view(
        character: str, pack: dict[str, Any], root: str | pathlib.Path,
        output_dir: str | pathlib.Path, *, usage: str = "keyframe",
        state: str | None = None) -> dict[str, Any]:
    """Return the locked, complete turnaround as one provider attachment.

    The historical function name remains for callers, but no image is materialized and no
    declared crop is used. ``output_dir`` is intentionally ignored.
    """
    del output_dir
    if not isinstance(pack, dict):
        raise IdentityPackError(f"{character}'s provider identity pack is missing")
    if pack.get("schemaVersion") != IDENTITY_PACK_SCHEMA_VERSION:
        raise IdentityPackError(
            f"{character}'s identity pack schema is unsupported")
    state_pack = (pack.get("stateSources") or {}).get(state) if state else None
    if state and not isinstance(state_pack, dict):
        raise IdentityPackError(
            f"{character}'s provider identity pack has no {state!r} state source")
    effective = {**pack, **(state_pack or {})}
    source_raw = effective.get("source")
    if not isinstance(source_raw, str):
        raise IdentityPackError(
            f"{character}'s identity pack has no turnaround source")

    source = cb_canon.resolve_declared_path(source_raw, root)
    source_hash = cb_canon.file_sha256(source)
    if not source_hash:
        raise IdentityPackError(f"{character}'s identity source is missing: {source.name}")

    contract = {
        "schemaVersion": IDENTITY_PACK_SCHEMA_VERSION,
        "character": character,
        "characterState": state or "default",
        "usage": usage,
        "view": "complete-turnaround",
        "source": str(source.resolve()),
        "sourceSha256": source_hash,
        "attachmentMode": "intact-turnaround",
        "coverage": effective.get("coverage") or "declared-turnaround",
    }
    digest = _contract_hash(contract)

    return {
        **contract,
        "contractHash": digest,
        "path": str(source.resolve()),
        "fileName": source.name,
        "derived": False,
        "providerSafe": True,
        "intactTurnaround": True,
        "singleSubject": False,
        "singleCharacterIdentity": True,
        "turnaroundAuthority": True,
        "turnaroundViewCount": len(effective.get("turnaroundViews") or []),
        "turnaroundGroupHash": digest,
        "distinguishingFeatures": list(effective.get("distinguishingFeatures") or []),
        "mustNotBorrow": list(effective.get("mustNotBorrow") or []),
    }


def materialize_provider_views(
        character: str, pack: dict[str, Any], root: str | pathlib.Path,
        output_dir: str | pathlib.Path, *, usage: str = "keyframe",
        state: str | None = None) -> list[dict[str, Any]]:
    """Return exactly one intact turnaround attachment for one character identity."""
    return [materialize_provider_view(
        character, pack, root, output_dir, usage=usage, state=state)]
