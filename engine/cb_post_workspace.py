"""Episode post-production workspace projection and human verdict ledger."""

from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
MEDIA_ROOT = ROOT / "engine" / "media"
POST_ROOT = MEDIA_ROOT / "post95"
STATE_ROOT = ROOT / "cb-output" / "state"


class PostWorkspaceError(ValueError):
    pass


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_url(value: str | None) -> str | None:
    if not value:
        return None
    path = pathlib.Path(value).expanduser().resolve()
    try:
        relative = path.relative_to(MEDIA_ROOT.resolve())
    except ValueError:
        return None
    return "/engine/media/" + relative.as_posix() if path.is_file() else None


def _manifest_path(episode: str) -> pathlib.Path | None:
    folder = POST_ROOT / f"{episode}_episode"
    candidates = list(folder.glob("*_manifest.json"))
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _verdict_path(episode: str) -> pathlib.Path:
    return STATE_ROOT / f"{episode}_post_review.json"


def _verdict_history_path(episode: str) -> pathlib.Path:
    return STATE_ROOT / f"{episode}_post_review_history.jsonl"


def _read_json(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def workspace(episode: str = "Ep1") -> dict[str, Any]:
    manifest_path = _manifest_path(episode)
    if not manifest_path:
        return {
            "episode": episode,
            "available": False,
            "status": "not-built",
            "message": "No post-production candidate has been built yet.",
        }

    manifest = _read_json(manifest_path)
    outputs = manifest.get("outputs") or {}
    master_path = pathlib.Path(outputs.get("master") or "")
    if not master_path.is_file():
        raise PostWorkspaceError("The post manifest exists but its review master is missing.")

    master_hash = _sha256(master_path)
    if manifest.get("masterSha256") and manifest["masterSha256"] != master_hash:
        raise PostWorkspaceError("The post master does not match its manifest hash.")

    verdict = None
    verdict_path = _verdict_path(episode)
    if verdict_path.exists():
        candidate = _read_json(verdict_path)
        if candidate.get("masterSha256") == master_hash:
            verdict = candidate

    stems = [
        {"id": "native", "label": "Dialogue + native SFX", "url": _media_url(outputs.get("nativeDialogueAndSfxStem"))},
        {"id": "music", "label": "Music", "url": _media_url(outputs.get("musicStem"))},
        {"id": "ambience", "label": "Ambience", "url": _media_url(outputs.get("ambienceStem"))},
        {"id": "mix", "label": "Final mix", "url": _media_url(outputs.get("finalMixStem"))},
    ]
    assets = []
    for item in manifest.get("assets") or []:
        assets.append({
            "scene": item.get("scene"),
            "musicUrl": _media_url(item.get("music")),
            "ambienceUrl": _media_url(item.get("ambience")),
        })

    return {
        "episode": episode,
        "available": True,
        "stage": manifest.get("stage") or manifest.get("status") or "post-review-human-signoff-required",
        "status": "approved" if verdict and verdict.get("verdict") == "approved" else "review-required",
        "masterUrl": _media_url(str(master_path)),
        "originalUrl": _media_url(outputs.get("pictureOriginal")),
        "masterSha256": master_hash,
        "durationSec": manifest.get("durationSec"),
        "scope": manifest.get("scope"),
        "shotCount": manifest.get("shotCount"),
        "sceneCount": manifest.get("sceneCount"),
        "cutPolicy": manifest.get("cutPolicy") or {},
        "audioPolicy": manifest.get("audioPolicy") or {},
        "approvalContract": manifest.get("approvalContract") or {},
        "timeline": manifest.get("timeline") or [],
        "mixPolicy": manifest.get("mixPolicy") or {},
        "qc": manifest.get("finalQc") or {},
        "stems": [stem for stem in stems if stem["url"]],
        "sceneCues": assets,
        "verdict": verdict,
        "manifestUpdatedAt": datetime.fromtimestamp(
            manifest_path.stat().st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def record_verdict(episode: str, verdict: str, note: str = "", reviewer: str = "Julian") -> dict[str, Any]:
    current = workspace(episode)
    if not current.get("available"):
        raise PostWorkspaceError("There is no post candidate to review.")
    verdict = verdict.strip().lower()
    if verdict not in {"approved", "rejected"}:
        raise PostWorkspaceError("verdict must be approved or rejected")
    note = note.strip()
    if verdict == "rejected" and not note:
        raise PostWorkspaceError("Return-to-post notes are required.")
    payload = {
        "episode": episode,
        "verdict": verdict,
        "note": note,
        "reviewer": reviewer,
        "masterSha256": current["masterSha256"],
        "stage": current.get("stage"),
        "approvalMeaning": (current.get("approvalContract") or {}).get("approvalMeaning"),
        "reviewedAt": datetime.now(timezone.utc).isoformat(),
    }
    target = _verdict_path(episode)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    history = _verdict_history_path(episode)
    with history.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return workspace(episode)
