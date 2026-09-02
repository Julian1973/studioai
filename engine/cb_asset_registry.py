#!/usr/bin/env python3
"""One displayable asset registry for Studio surfaces.

The registry binds every usable asset to episode/scene/shot state once, then
all UI/API surfaces resolve through this module instead of re-reading sidecars.
"""
from __future__ import annotations

import hashlib
import functools
import filelock_compat
import json
import mimetypes
import os
import pathlib
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import paths
import paths as P  # the project profile is the only path authority (T44/T45)

ROOT = pathlib.Path(paths.ROOT).resolve()
MEDIA = pathlib.Path(paths.MEDIA).resolve()
OUTPUT = pathlib.Path(paths.OUTPUT).resolve()
if not (OUTPUT / "Ep1_The_Adventure_Begins_beat_package.json").exists():
    OUTPUT = (ROOT / P.OUTPUT_REL).resolve()
ASSET_ROOT = pathlib.Path(paths.ASSETS).resolve()   # T44: from the project profile
PROJECTS_ROOT = (ROOT / "projects").resolve()
REGISTRY_DIR = OUTPUT / "asset-registry"
REGISTRY_PATH = REGISTRY_DIR / "assets.json"
MANAGED_DIR = MEDIA / "asset-registry"

PROJECT_ASSET_SOURCE = "project-assets"    # T58: was the first project's literal "cb-seed/assets"

DISPLAY_ROOTS = (
    (MEDIA, paths.MEDIA_URL),
    # T58: the project's assets are served at their own path (the first project's assets root
    # resolves to cb-seed/assets for one release, so its URLs are unchanged).
    (ASSET_ROOT, "/" + ASSET_ROOT.relative_to(ROOT.resolve()).as_posix() + "/"),
    (PROJECTS_ROOT, "/projects/"),
)

KINDS = {
    "scene_plate", "opening_plate", "reference_image", "keyframe",
    "keyframe_candidate", "approved_take", "candidate_take", "final_frame",
    "voice",
}


class AssetBindingError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"schemaVersion": 1, "assets": [], "deletedBindingKeys": []}
    raw = REGISTRY_PATH.read_text(encoding="utf-8")
    if not raw.strip():
        return {"schemaVersion": 1, "assets": []}
    data = json.loads(raw)
    data.setdefault("schemaVersion", 1)
    data.setdefault("assets", [])
    data.setdefault("deletedBindingKeys", [])
    return data


def _locked_registry(func):
    """Serialize each registry read-modify-write transaction across server threads/processes."""
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = REGISTRY_PATH.with_suffix(".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            filelock_compat.lock(lock_file)
            try:
                return func(*args, **kwargs)
            finally:
                filelock_compat.unlock(lock_file)
    return wrapped


def _write(data: dict[str, Any]) -> None:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{REGISTRY_PATH.name}.", suffix=".tmp", dir=REGISTRY_DIR)
    tmp = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(REGISTRY_PATH)
    finally:
        tmp.unlink(missing_ok=True)


def url_for_path(path_value: str | pathlib.Path | None) -> str | None:
    if not path_value:
        return None
    try:
        p = pathlib.Path(path_value).expanduser().resolve()
    except Exception:
        return None
    if not p.exists():
        return None
    for root, prefix in DISPLAY_ROOTS:
        try:
            if p.is_relative_to(root):
                return prefix + quote(p.relative_to(root).as_posix())
        except AttributeError:
            if not str(p).startswith(str(root) + "/"):
                continue
            return prefix + quote(str(p)[len(str(root)) + 1:])
    return None


def _display_type(path_value: pathlib.Path) -> str:
    mime = mimetypes.guess_type(str(path_value))[0] or ""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    return "file"


def _asset_id(episode: str, scene: str, shot_id: str | None, kind: str,
              role: str | None, path_value: pathlib.Path) -> str:
    raw = "|".join([episode, scene, shot_id or "", kind, role or "",
                    str(path_value.resolve())])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _binding_key(episode: str, scene: str, shot_id: str | None, kind: str,
                 role: str | None) -> str:
    return "|".join([episode, scene, shot_id or "", kind, role or ""])


def ensure_displayable_copy(source: str | pathlib.Path, label: str) -> pathlib.Path:
    src = pathlib.Path(source).expanduser().resolve()
    if not src.exists():
        raise AssetBindingError(f"Asset source does not exist: {src}")
    if url_for_path(src):
        return src
    MANAGED_DIR.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix or ".asset"
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:10]
    safe = "".join(ch if ch.isalnum() else "_" for ch in label).strip("_") or "asset"
    dst = MANAGED_DIR / f"{safe}_{digest}{suffix}"
    if not dst.exists():
        shutil.copy2(src, dst)
    return dst.resolve()


@_locked_registry
def register_asset(*, episode: str, scene: str | int, kind: str, path: str | pathlib.Path,
                   shot_id: str | None = None, role: str | None = None,
                   status: str = "approved", label: str | None = None,
                   source: str | None = None, metadata: dict[str, Any] | None = None,
                   replace: bool = True, require_displayable: bool = True) -> dict[str, Any]:
    episode = str(episode or "").strip()
    scene = str(scene or "").strip()
    shot_id = str(shot_id).strip() if shot_id else None
    kind = str(kind or "").strip()
    role = str(role or kind).strip()
    if not episode or not scene:
        raise AssetBindingError("Asset binding requires episode and scene.")
    if kind not in KINDS:
        raise AssetBindingError(f"Unsupported asset kind: {kind}")
    p = pathlib.Path(path).expanduser().resolve()
    if not p.exists():
        raise AssetBindingError(f"Asset file does not exist: {p}")
    url = url_for_path(p)
    if require_displayable and not url:
        raise AssetBindingError(f"Asset is not displayable by Studio static routes: {p}")

    data = _read()
    key = _binding_key(episode, scene, shot_id, kind, role)
    if key in set(data.get("deletedBindingKeys") or []):
        raise AssetBindingError(f"Asset binding was deleted for {key}")
    existing = [a for a in data["assets"] if a.get("bindingKey") == key]
    if existing and not replace and pathlib.Path(existing[0]["path"]).resolve() != p:
        raise AssetBindingError(f"Asset binding already exists for {key}")
    registered_at = (
        existing[0].get("registeredAt")
        if existing and pathlib.Path(existing[0].get("path", "")).resolve() == p
        else _now()
    )
    rec = {
        "assetId": _asset_id(episode, scene, shot_id, kind, role, p),
        "bindingKey": key,
        "episode": episode,
        "scene": scene,
        "shotId": shot_id,
        "kind": kind,
        "role": role,
        "status": status,
        "label": label or role.replace("_", " "),
        "path": str(p),
        "url": url,
        "displayType": _display_type(p),
        "source": source or "registry",
        "metadata": metadata or {},
        "registeredAt": registered_at,
    }
    if existing:
        index = next(i for i, item in enumerate(data["assets"])
                     if item.get("bindingKey") == key)
        data["assets"][index] = rec
    else:
        data["assets"].append(rec)
    _write(data)
    return rec


@_locked_registry
def remove_asset(asset_id: str) -> dict[str, Any]:
    asset_id = str(asset_id or "").strip()
    if not asset_id:
        raise AssetBindingError("assetId is required.")
    data = _read()
    before = len(data.get("assets") or [])
    removed = [item for item in data.get("assets") or [] if item.get("assetId") == asset_id]
    data["assets"] = [item for item in data.get("assets") or [] if item.get("assetId") != asset_id]
    if len(data["assets"]) == before:
        raise AssetBindingError(f"No asset binding exists for assetId: {asset_id}")
    deleted = set(data.get("deletedBindingKeys") or [])
    for item in removed:
        if item.get("bindingKey"):
            deleted.add(item["bindingKey"])
    data["deletedBindingKeys"] = sorted(deleted)
    _write(data)
    return {"removed": removed, "assetCount": len(data["assets"])}


@_locked_registry
def update_asset(asset_id: str, *, label: str | None = None, scene: str | int | None = None,
                 kind: str | None = None, role: str | None = None,
                 status: str | None = None, path: str | pathlib.Path | None = None,
                 metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    asset_id = str(asset_id or "").strip()
    if not asset_id:
        raise AssetBindingError("assetId is required.")
    data = _read()
    for index, rec in enumerate(data.get("assets") or []):
        if rec.get("assetId") != asset_id:
            continue
        next_rec = dict(rec)
        if label is not None:
            next_rec["label"] = str(label).strip() or next_rec.get("label") or "Asset"
        if status is not None:
            next_rec["status"] = str(status).strip() or next_rec.get("status") or "draft"
        if role is not None:
            next_rec["role"] = str(role).strip() or next_rec.get("role") or next_rec.get("kind")
        if kind is not None:
            kind = str(kind or "").strip()
            if kind not in KINDS:
                raise AssetBindingError(f"Unsupported asset kind: {kind}")
            next_rec["kind"] = kind
        if scene is not None:
            next_rec["scene"] = str(scene or "").strip() or next_rec.get("scene") or "*"
        if path is not None:
            p = pathlib.Path(path).expanduser().resolve()
            if not p.exists():
                raise AssetBindingError(f"Asset file does not exist: {p}")
            url = url_for_path(p)
            if not url:
                raise AssetBindingError(f"Asset is not displayable by Studio static routes: {p}")
            next_rec["path"] = str(p)
            next_rec["url"] = url
            next_rec["displayType"] = _display_type(p)
            next_rec["assetId"] = _asset_id(
                next_rec.get("episode") or "",
                next_rec.get("scene") or "",
                next_rec.get("shotId"),
                next_rec.get("kind") or "",
                next_rec.get("role"),
                p,
            )
        if metadata is not None:
            current_meta = dict(next_rec.get("metadata") or {})
            current_meta.update({k: v for k, v in metadata.items() if v is not None})
            next_rec["metadata"] = current_meta
        next_rec["bindingKey"] = _binding_key(
            next_rec.get("episode") or "",
            next_rec.get("scene") or "",
            next_rec.get("shotId"),
            next_rec.get("kind") or "",
            next_rec.get("role"),
        )
        next_rec["updatedAt"] = _now()
        data["assets"][index] = next_rec
        _write(data)
        return next_rec
    raise AssetBindingError(f"No asset binding exists for assetId: {asset_id}")


def _register_if_exists(**kwargs: Any) -> dict[str, Any] | None:
    path_value = kwargs.get("path")
    if not path_value or not pathlib.Path(path_value).expanduser().exists():
        return None
    try:
        return register_asset(**kwargs)
    except AssetBindingError:
        return None


def migrate_existing(episode: str = "Ep1") -> dict[str, Any]:
    """Import existing package/sidecar media into the asset registry."""
    created = []
    # Scene look approvals/candidates.
    for path in sorted(OUTPUT.glob(f"{episode}_scenelook_scene*.json")):
        scene = path.stem.split("scene")[-1]
        rec = json.loads(path.read_text(encoding="utf-8"))
        for kind_key, status in (("approved", "approved"), ("candidate", "candidate")):
            item = rec.get(kind_key)
            if isinstance(item, dict) and item.get("path"):
                out = _register_if_exists(
                    episode=episode, scene=scene, kind="scene_plate", path=item["path"],
                    role=f"scene_plate_{status}", status=status,
                    label=f"Scene {scene} {status} scene plate", source=str(path))
                if out:
                    created.append(out["assetId"])
        if rec.get("platePath"):
            out = _register_if_exists(
                episode=episode, scene=scene, kind="scene_plate", path=rec["platePath"],
                role="scene_plate_approved", status="approved",
                label=f"Scene {scene} approved scene plate", source=str(path))
            if out:
                created.append(out["assetId"])

    # Production package ledgers.
    for path in sorted(OUTPUT.glob(f"{episode}_scene*_production_package.json")):
        pkg = json.loads(path.read_text(encoding="utf-8"))
        scene = str(pkg.get("sceneNumber") or path.stem.split("_scene")[-1].split("_")[0])
        for led in pkg.get("continuityLedger") or []:
            sid = led.get("shotId")
            voice_status = (
                "approved" if (led.get("voiceApproval") or {}).get("approved")
                else "candidate")
            mappings = [
                ("voice", "voice_track", led.get("voPath"), voice_status),
                ("approved_take", "approved_take", led.get("approvedTake"), "approved"),
                ("final_frame", "final_frame", led.get("harvestFrame"), "approved"),
                ("keyframe_candidate", "keyframe_candidate", (led.get("keyframeCandidate") or {}).get("path"), "candidate"),
                ("keyframe", "approved_keyframe", (led.get("keyframeApproval") or {}).get("path"), "approved"),
            ]
            for kind, role, p, status in mappings:
                out = _register_if_exists(
                    episode=episode, scene=scene, shot_id=sid, kind=kind, role=role,
                    path=p, status=status, label=f"{sid} {role}", source=str(path))
                if out:
                    created.append(out["assetId"])
            for idx, p in enumerate(led.get("candidatePaths") or [], 1):
                out = _register_if_exists(
                    episode=episode, scene=scene, shot_id=sid, kind="candidate_take",
                    role=f"candidate_{idx}", path=p, status="candidate",
                    label=f"{sid} candidate {idx}", source=str(path))
                if out:
                    created.append(out["assetId"])
            # In-progress render batches can expose completed files before the
            # full batch finishes. Preserve the old transportCandidates surface
            # through the registry instead of making the UI read batch internals.
            transport = ((led.get("batch") or {}).get("transportCandidates") or {})
            current_candidate_paths = {
                str(pathlib.Path(value).expanduser().resolve())
                for value in (led.get("candidatePaths") or []) if value
            }
            for key, item in sorted(transport.items()):
                candidate_path = (item or {}).get("candidatePath")
                if (candidate_path and
                        str(pathlib.Path(candidate_path).expanduser().resolve())
                        in current_candidate_paths):
                    continue
                out = _register_if_exists(
                    episode=episode, scene=scene, shot_id=sid, kind="candidate_take",
                    role=f"transport_candidate_{key}", path=candidate_path,
                    status="candidate", label=f"{sid} transport candidate {key}",
                    source=str(path))
                if out:
                    created.append(out["assetId"])

    # Opening-plate handoff sidecars. Copy external files into managed media if needed.
    for path in sorted(OUTPUT.glob(f"{episode}_scene*_opening_plate.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        scene = str(rec.get("scene") or path.stem.split("_scene")[-1].split("_")[0])
        src = rec.get("sourcePath") or rec.get("path")
        if src and pathlib.Path(src).expanduser().exists():
            managed = ensure_displayable_copy(src, f"{episode}_scene{scene}_opening_plate")
            shot_id = rec.get("shotId")
            pkg_path = OUTPUT / f"{episode}_scene{scene}_production_package.json"
            if not shot_id and pkg_path.exists():
                pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
                shots = pkg.get("shots") or []
                shot_id = (shots[0] or {}).get("shotId") if shots else None
            out = register_asset(
                episode=episode, scene=scene, shot_id=shot_id, kind="opening_plate",
                role="scene_opening_plate", path=managed, status=rec.get("status") or "approved",
                label=f"Scene {scene} opening plate", source=str(path),
                metadata={"originalPath": str(pathlib.Path(src).expanduser().resolve())})
            created.append(out["assetId"])
            also = rec.get("alsoUsedAs") or {}
            if also.get("scene"):
                out = register_asset(
                    episode=str(also.get("episode") or episode), scene=str(also["scene"]),
                    shot_id=also.get("shotId"), kind="opening_plate",
                    role=also.get("role") or "opening_plate", path=managed,
                    status=rec.get("status") or "approved",
                    label=f"Scene {also['scene']} {also.get('role') or 'opening plate'}",
                    source=str(path), metadata={"originalPath": str(pathlib.Path(src).expanduser().resolve())})
                created.append(out["assetId"])

    # Project reference images are global scene resources returned by every scene resolver.
    data = _read()
    before = len(data["assets"])
    data["assets"] = [
        item for item in data["assets"]
        if not (
            item.get("source") in ("cb-seed/assets", PROJECT_ASSET_SOURCE)
            and item.get("kind") == "reference_image"
            and "." not in str(item.get("role") or "")
        )
    ]
    if len(data["assets"]) != before:
        _write(data)
    for root in (ASSET_ROOT,):
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file() and (mimetypes.guess_type(str(p))[0] or "").startswith("image/"):
                    role = p.relative_to(root).as_posix()
                    out = _register_if_exists(
                        episode=episode, scene="*", kind="reference_image", role=role,
                        path=p, status="approved", label=p.stem.replace("_", " "),
                        source=PROJECT_ASSET_SOURCE)
                    if out:
                        created.append(out["assetId"])

    return {"registryPath": str(REGISTRY_PATH), "assetCount": len(_read()["assets"]),
            "registeredOrUpdated": len(created)}


def resolve_assets(episode: str, scene: str | int, shot_id: str | None = None,
                   kinds: set[str] | None = None, include_global: bool = True) -> list[dict[str, Any]]:
    data = _read()
    scene = str(scene)
    out = []
    for rec in data.get("assets") or []:
        if rec.get("episode") != str(episode):
            continue
        if rec.get("scene") not in {scene, *(["*"] if include_global else [])}:
            continue
        if shot_id and rec.get("shotId") not in {None, shot_id}:
            continue
        if kinds and rec.get("kind") not in kinds:
            continue
        if rec.get("url") and pathlib.Path(rec.get("path", "")).exists():
            out.append(dict(rec))
    return sorted(out, key=lambda r: (r.get("scene") == "*", r.get("shotId") or "", r.get("kind") or "", r.get("label") or ""))


def library_for_scene(episode: str, scene: str | int, shot_id: str | None = None) -> list[dict[str, Any]]:
    scene_s = str(scene)
    kinds = {"scene_plate", "opening_plate", "final_frame", "reference_image", "keyframe"}
    items = resolve_assets(episode, scene_s, shot_id=shot_id, kinds=kinds)
    try:
        prev_scene = str(int(scene_s) - 1)
    except ValueError:
        prev_scene = ""
    if prev_scene:
        items.extend(resolve_assets(episode, prev_scene, kinds={"final_frame"}, include_global=False))
    seen = set()
    deduped = []
    for item in items:
        key = item["assetId"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def shot_media_from_registry(pkg: dict[str, Any], scene: str | int, episode: str = "Ep1") -> dict[str, Any]:
    migrate_existing(episode)
    assets = resolve_assets(episode, scene, include_global=False)
    by_shot: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        if asset.get("shotId"):
            by_shot.setdefault(asset["shotId"], []).append(asset)
    out = {}
    for shot in pkg.get("shots") or []:
        sid = shot.get("shotId")
        if not sid:
            continue
        entries = by_shot.get(sid, [])
        def latest(kind: str, status: str | None = None, role_prefix: str | None = None):
            vals = [e for e in entries if e.get("kind") == kind]
            if status:
                vals = [e for e in vals if e.get("status") == status]
            if role_prefix:
                vals = [e for e in vals if str(e.get("role") or "").startswith(role_prefix)]
            return vals[-1] if vals else None
        approved_kf = latest("keyframe", "approved")
        candidate_kf = latest("keyframe_candidate", "candidate")
        approved_take = latest("approved_take", "approved")
        final_frame = latest("final_frame", "approved")
        voice = latest("voice")
        candidates = []
        candidate_paths = set()
        for entry in (e for e in entries if e.get("kind") == "candidate_take"):
            path_key = str(pathlib.Path(entry.get("path") or "").expanduser().resolve())
            if not path_key or path_key in candidate_paths:
                continue
            candidate_paths.add(path_key)
            candidates.append(entry)
        out[sid] = {
            "vo": voice.get("url") if voice else None,
            "keyframe": (candidate_kf or approved_kf or {}).get("url"),
            "keyframeCandidate": candidate_kf.get("url") if candidate_kf else None,
            "keyframeApproved": approved_kf.get("url") if approved_kf else None,
            "clip": approved_take.get("url") if approved_take else None,
            "finalFrame": final_frame.get("url") if final_frame else None,
            "candidates": [{"n": i, "url": c["url"]} for i, c in enumerate(candidates, 1)],
        }
    return out
