#!/usr/bin/env python3
"""Immutable canon registry and zero-spend readiness checks for Crystal Bears.

The lock file records hashes, never media bytes or provider secrets. A source, character
reference, location plate or compatibility copy that changes becomes visible immediately;
re-locking is an explicit command after human review, never a side effect of generation.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import sys
from typing import Any, Iterable


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
POLICY_REL = pathlib.Path("shows/crystal-bears/canon/lock_policy.json")
MANIFEST_REL = pathlib.Path("shows/crystal-bears/canon/CANON_LOCK.json")
SCHEMA_VERSION = 1


class CanonLockError(RuntimeError):
    """The approved canon snapshot is missing, stale or incomplete for the requested work."""


_HASH_CACHE: dict[tuple[str, int, int], str] = {}


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def file_sha256(path: str | pathlib.Path) -> str | None:
    p = pathlib.Path(path)
    try:
        stat = p.stat()
    except OSError:
        return None
    key = (str(p.resolve()), stat.st_mtime_ns, stat.st_size)
    cached = _HASH_CACHE.get(key)
    if cached:
        return cached
    h = hashlib.sha256()
    try:
        with p.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    value = h.hexdigest()
    _HASH_CACHE[key] = value
    return value


def _root(root: str | pathlib.Path | None = None) -> pathlib.Path:
    return pathlib.Path(root or ROOT).resolve()


def _inside(root: pathlib.Path, path: pathlib.Path) -> pathlib.Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CanonLockError(f"canon path escapes the workspace: {path}") from exc
    return resolved


def resolve_declared_path(value: str, root: str | pathlib.Path | None = None) -> pathlib.Path:
    """Resolve both repository-relative paths and legacy engine-relative ../cb-seed paths."""
    base = _root(root)
    raw = pathlib.Path(str(value or ""))
    if not str(raw):
        raise CanonLockError("blank canon asset path")
    path = raw if raw.is_absolute() else ((base / "engine" / raw)
                                          if str(raw).startswith("../") else (base / raw))
    return _inside(base, path)


def _relative(path: pathlib.Path, root: pathlib.Path) -> str:
    return str(path.resolve().relative_to(root)).replace("\\", "/")


def load_policy(root: str | pathlib.Path | None = None) -> dict:
    base = _root(root)
    path = base / POLICY_REL
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CanonLockError(f"canon lock policy is unreadable: {path}") from exc
    if policy.get("schemaVersion") != SCHEMA_VERSION:
        raise CanonLockError("canon lock policy schema is unsupported")
    if not isinstance(policy.get("sources"), dict) or not isinstance(policy.get("roster"), dict):
        raise CanonLockError("canon lock policy is missing sources or roster")
    return policy


def _read_json_source(policy: dict, source_id: str, root: pathlib.Path) -> Any:
    path = resolve_declared_path(policy["sources"][source_id], root)
    return json.loads(path.read_text(encoding="utf-8"))


def _character_assets(name: str, record: dict, root: pathlib.Path) -> list[dict]:
    declared: list[tuple[str, str]] = []

    def add(role: str, value: Any) -> None:
        if isinstance(value, str) and value.strip():
            declared.append((role, value.strip()))

    for field in ("anchor", "turnaround", "turn4", "render_ref", "frontRef", "backRef"):
        add(field, record.get(field))
    for index, value in enumerate(record.get("refs") or [], start=1):
        add(f"refs[{index}]", value)
    for index, value in enumerate(record.get("box") or [], start=1):
        add(f"box[{index}]", value)
    house = record.get("house") or {}
    if isinstance(house, dict):
        for field in ("interior", "interiorMulticam", "exterior", "exteriorMulticam"):
            add(f"house.{field}", house.get(field))
    for state_name, state in (record.get("states") or {}).items():
        if not isinstance(state, dict):
            continue
        for field in ("anchor", "turnaround", "turn4", "render_ref"):
            add(f"states.{state_name}.{field}", state.get(field))
        for index, value in enumerate(state.get("refs") or [], start=1):
            add(f"states.{state_name}.refs[{index}]", value)
    for state_name, values in (record.get("wristband_states") or {}).items():
        for index, value in enumerate(values or [], start=1):
            add(f"wristband_states.{state_name}[{index}]", value)

    grouped: dict[str, dict] = {}
    for role, raw in declared:
        path = resolve_declared_path(raw, root)
        rel = _relative(path, root)
        grouped.setdefault(rel, {"path": rel, "roles": []})["roles"].append(role)
    return [{**item, "roles": sorted(set(item["roles"])), "sha256": file_sha256(root / rel)}
            for rel, item in sorted(grouped.items())]


def _location_assets(policy: dict, locations: dict, root: pathlib.Path) -> list[dict]:
    declared: dict[str, set[str]] = {}

    def add(role: str, value: Any, *, relative_to: pathlib.Path | None = None) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        raw = pathlib.Path(value.strip())
        path = ((relative_to / raw) if relative_to and not raw.is_absolute()
                else resolve_declared_path(value.strip(), root))
        path = _inside(root, path)
        declared.setdefault(_relative(path, root), set()).add(role)

    for episode, scenes in locations.items():
        if str(episode).startswith("_") or not isinstance(scenes, dict):
            continue
        for scene, record in scenes.items():
            if isinstance(record, dict):
                add(f"{episode}.scene{scene}.master", record.get("master"))

    manifest_path = resolve_declared_path(policy["sources"]["locationAssetManifest"], root)
    try:
        library = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        library = {}
    for location_id, record in library.items():
        if isinstance(record, dict):
            add(f"locationLibrary.{location_id}", record.get("file"),
                relative_to=manifest_path.parent)

    return [{"path": rel, "roles": sorted(roles), "sha256": file_sha256(root / rel)}
            for rel, roles in sorted(declared.items())]


def _manifest_payload(manifest: dict) -> dict:
    return {key: manifest.get(key) for key in (
        "schemaVersion", "showId", "policySha256", "sources", "characters",
        "locationAssets",
    )}


def build_manifest(root: str | pathlib.Path | None = None,
                   locked_by: str = "Julian") -> dict:
    base = _root(root)
    policy = load_policy(base)
    policy_path = base / POLICY_REL
    sources = {}
    missing_sources = []
    for source_id, raw in sorted(policy["sources"].items()):
        path = resolve_declared_path(raw, base)
        digest = file_sha256(path)
        sources[source_id] = {"path": _relative(path, base), "sha256": digest}
        if digest is None:
            missing_sources.append(source_id)
    if missing_sources:
        raise CanonLockError("required canon sources are missing: " + ", ".join(missing_sources))

    characters = _read_json_source(policy, "characters", base)
    character_manifest = {}
    missing_assets = []
    for name, rules in policy["roster"].items():
        record = characters.get(name)
        assets = _character_assets(name, record or {}, base) if isinstance(record, dict) else []
        if rules.get("status") == "locked":
            missing_assets.extend(
                f"{name}: {asset['path']}" for asset in assets if asset["sha256"] is None)
        character_manifest[name] = {
            "tier": rules.get("tier"),
            "status": rules.get("status"),
            "voiceMode": rules.get("voiceMode"),
            "assets": assets,
        }
    if missing_assets:
        raise CanonLockError("declared character assets are missing:\n  " +
                             "\n  ".join(missing_assets))

    locations = _read_json_source(policy, "locations", base)
    location_assets = _location_assets(policy, locations, base)
    missing_locations = [asset["path"] for asset in location_assets if asset["sha256"] is None]
    if missing_locations:
        raise CanonLockError("declared location assets are missing: " +
                             ", ".join(missing_locations))

    manifest = {
        "schemaVersion": SCHEMA_VERSION,
        "showId": policy["showId"],
        "lockedAt": _now(),
        "lockedBy": locked_by,
        "policySha256": file_sha256(policy_path),
        "sources": sources,
        "characters": character_manifest,
        "locationAssets": location_assets,
    }
    manifest["manifestDigest"] = _digest(_manifest_payload(manifest))
    return manifest


def write_lock(root: str | pathlib.Path | None = None,
               locked_by: str = "Julian") -> dict:
    base = _root(root)
    manifest = build_manifest(base, locked_by)
    path = base / MANIFEST_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return manifest


def load_manifest(root: str | pathlib.Path | None = None) -> dict:
    path = _root(root) / MANIFEST_REL
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CanonLockError(f"canon lock manifest is unreadable: {path}") from exc
    return manifest


def _copy_body(path: pathlib.Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "<!-- AUTO-GENERATED"
    if text.startswith(marker) and "-->\n\n" in text:
        return text.split("-->\n\n", 1)[1]
    return text


def _source_integrity(policy: dict, manifest: dict, root: pathlib.Path) -> tuple[list, list]:
    blockers, rows = [], []
    recorded = manifest.get("sources") or {}
    for source_id, raw in sorted(policy["sources"].items()):
        path = resolve_declared_path(raw, root)
        expected = (recorded.get(source_id) or {}).get("sha256")
        actual = file_sha256(path)
        current = bool(expected and expected == actual)
        rows.append({"id": source_id, "path": _relative(path, root),
                     "sha256": actual, "current": current})
        if not current:
            blockers.append({
                "code": "CANON_SOURCE_DRIFT",
                "source": source_id,
                "message": f"{source_id} is missing or differs from the approved lock.",
                "action": "Review the source change, synchronize compatibility copies, then re-lock canon.",
            })
    return blockers, rows


def _asset_integrity(manifest: dict, root: pathlib.Path) -> list:
    blockers = []
    records: list[tuple[str, dict]] = []
    for name, item in (manifest.get("characters") or {}).items():
        records.extend((f"character:{name}", asset) for asset in item.get("assets") or [])
    records.extend(("location", asset) for asset in manifest.get("locationAssets") or [])
    for owner, asset in records:
        actual = file_sha256(root / str(asset.get("path") or ""))
        if not actual or actual != asset.get("sha256"):
            blockers.append({
                "code": "CANON_ASSET_DRIFT",
                "owner": owner,
                "path": asset.get("path"),
                "message": f"{owner} asset is missing or changed: {asset.get('path')}",
                "action": "Restore the approved file or review and explicitly re-lock its replacement.",
            })
    return blockers


def _compatibility_integrity(policy: dict, root: pathlib.Path) -> list:
    blockers = []
    for copy in policy.get("compatibilityCopies") or []:
        source = resolve_declared_path(policy["sources"][copy["source"]], root)
        target = resolve_declared_path(copy["path"], root)
        try:
            matches = source.read_bytes() == target.read_bytes()
        except OSError:
            matches = False
        if not matches:
            blockers.append({
                "code": "CANON_COMPATIBILITY_DRIFT",
                "path": copy["path"],
                "message": f"Compatibility copy differs from {copy['source']}: {copy['path']}",
                "action": "Run python3 tools/sync_canon.py after reviewing the canonical source.",
            })
    source_text = resolve_declared_path(policy["sources"]["showBible"], root).read_text(
        encoding="utf-8")
    skill_glob = policy.get("skillCanonCopiesGlob")
    targets = sorted(root.glob(skill_glob)) if skill_glob else []
    for target in targets:
        try:
            matches = _copy_body(target) == source_text
        except OSError:
            matches = False
        if not matches:
            blockers.append({
                "code": "CANON_SKILL_COPY_DRIFT",
                "path": _relative(target, root),
                "message": f"Skill bible copy differs from the canonical show bible: {_relative(target, root)}",
                "action": "Run python3 tools/sync_canon.py.",
            })
    return blockers


def _performance_gap_counts(policy: dict, root: pathlib.Path) -> dict[str, int]:
    try:
        values = _read_json_source(policy, "characterPerformance", root).get("characters") or {}
    except (OSError, ValueError, AttributeError):
        return {}
    counts = {}
    for name, record in values.items():
        if not isinstance(record, dict):
            continue
        counts[name] = sum(
            1 for key, value in record.items()
            if key != "provenance" and value in (None, "")
        )
    return counts


def _character_status(policy: dict, manifest: dict, root: pathlib.Path) -> list[dict]:
    try:
        characters = _read_json_source(policy, "characters", root)
    except (OSError, ValueError):
        characters = {}
    performance_gaps = _performance_gap_counts(policy, root)
    rows = []
    for name, rules in policy["roster"].items():
        record = characters.get(name)
        gaps = []
        if not isinstance(record, dict):
            gaps.append("character record missing")
            record = {}
        if rules.get("status") == "locked":
            if not record.get("anchor"):
                gaps.append("identity anchor missing")
            if not str(record.get("key_features") or "").strip():
                gaps.append("key features missing")
            if not isinstance(record.get("bible"), dict):
                gaps.append("character bible missing")
            if record.get("sizeRank") is None:
                gaps.append("size rank missing")
            if rules.get("voiceMode") == "elevenlabs-v3" and not record.get("voiceId"):
                gaps.append("ElevenLabs voice ID missing")
            if rules.get("voiceMode") == "nonverbal-sfx" and record.get("voiceId"):
                gaps.append("non-verbal character must not have a dialogue voice ID")
            for asset in _character_assets(name, record, root):
                if asset.get("sha256") is None:
                    gaps.append(f"declared asset missing: {asset['path']}")
        else:
            gaps.append(str(record.get("_status") or "declared stub; canon completion required"))

        creative_gaps = []
        call = record.get("crystalCall") or {}
        if call.get("callStatus") == "proposed-pending-approval":
            creative_gaps.append("Crystal Call is proposed and still needs human approval")
        optional_count = performance_gaps.get(name, 0)
        if optional_count:
            creative_gaps.append(
                f"{optional_count} optional performance-overlay fields remain unresolved")
        rows.append({
            "name": name,
            "tier": rules.get("tier"),
            "status": rules.get("status"),
            "voiceMode": rules.get("voiceMode"),
            "productionReady": rules.get("status") == "locked" and not gaps,
            "gaps": gaps,
            "creativeGaps": creative_gaps,
            "assetCount": len(((manifest.get("characters") or {}).get(name) or {}).get("assets") or []),
        })
    unknown = sorted(
        name for name, record in characters.items()
        if not str(name).startswith("_") and name != "sizeClasses" and
        isinstance(record, dict) and name not in policy["roster"]
    )
    rows.extend({"name": name, "tier": "undeclared", "status": "unregistered",
                 "voiceMode": None, "productionReady": False,
                 "gaps": ["character is not declared in the locked roster"],
                 "creativeGaps": [], "assetCount": 0} for name in unknown)
    return rows


def _episode_cast(root: pathlib.Path, episode: str) -> list[str]:
    candidate = root / "cb-output" / "creative" / f"{episode}_story_intake_CANDIDATE.json"
    paths = [candidate] if candidate.exists() else []
    paths.extend(sorted((root / "cb-output").glob(f"{episode}_*beat_package.json"),
                        key=lambda path: path.stat().st_mtime, reverse=True))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cast = sorted({name for beat in data.get("beats") or []
                       for name in beat.get("characters") or [] if name})
        if cast:
            return cast
    return []


def _script_text(root: pathlib.Path, episode: str) -> tuple[str | None, str | None]:
    current = root / "shows" / "crystal-bears" / "episodes" / "scripts" / "_current" / f"{episode}.json"
    try:
        record = json.loads(current.read_text(encoding="utf-8"))
        path = resolve_declared_path(record["contentPath"], root)
        return path.read_text(encoding="utf-8"), _relative(path, root)
    except (OSError, ValueError, KeyError, CanonLockError):
        return None, None


def validate_script(text: str, policy: dict) -> dict:
    blockers, warnings = [], []
    checks = policy.get("scriptChecks") or {}
    for check in checks.get("forbiddenPatterns") or []:
        match = re.search(check["pattern"], text, re.IGNORECASE)
        if match:
            blockers.append({
                "code": "SCRIPT_CANON_CONFLICT",
                "checkId": check["id"],
                "message": check["message"],
                "evidence": match.group(0),
                "action": "Correct the script as a new immutable version or explicitly revise the show canon.",
            })
    for check in checks.get("lockedDialogue") or []:
        trigger = re.search(check["triggerPattern"], text, re.IGNORECASE)
        exact = check["exactText"] in text
        if trigger and not exact:
            lines = text.splitlines()
            line = None
            cue = re.compile(
                rf"^\s*(?:\d+\s*)?{re.escape(check.get('speaker') or '')}"
                rf"(?:\s+\(CONT[’']?D\))?\s*$", re.IGNORECASE)
            for index, raw in enumerate(lines):
                if not cue.match(raw):
                    continue
                spoken = []
                for following in lines[index + 1:]:
                    if not following.strip():
                        break
                    spoken.append(following.strip())
                candidate = " ".join(spoken)
                if re.search(check["triggerPattern"], candidate, re.IGNORECASE):
                    line = candidate
                    break
            line = line or next((raw.strip() for raw in lines
                                 if re.search(check["triggerPattern"], raw, re.IGNORECASE)),
                                trigger.group(0))
            blockers.append({
                "code": "LOCKED_DIALOGUE_CONFLICT",
                "checkId": check["id"],
                "message": check["message"],
                "evidence": line,
                "required": check["exactText"],
                "action": "Choose whether the immutable script or the locked call is authoritative, then version that decision.",
            })
    paragraphs = [part.strip().replace("\n", " ") for part in re.split(r"\n\s*\n", text)]
    for check in checks.get("pronounContracts") or []:
        for paragraph in paragraphs:
            if (re.search(rf"\b{re.escape(check['character'])}\b", paragraph, re.IGNORECASE)
                    and re.search(check.get("evidencePattern") or
                                  check["forbiddenPattern"], paragraph, re.IGNORECASE)):
                blockers.append({
                    "code": "CHARACTER_PRONOUN_CONFLICT",
                    "checkId": check["id"],
                    "message": check["message"],
                    "evidence": paragraph[:260],
                    "action": "Confirm the character's canon pronouns and upload a matching script version.",
                })
                break
    for alias, canonical in (policy.get("characterAliases") or {}).items():
        match = re.search(rf"(?mi)^\s*\d+\s+{re.escape(alias)}(?:\s|$)", text)
        if match:
            warnings.append({
                "code": "SCRIPT_CHARACTER_ALIAS",
                "alias": alias,
                "canonical": canonical,
                "message": f"Script cue {alias} is mapped explicitly to {canonical}; correct the spelling in the next script version.",
            })
    return {"ok": not blockers, "blockers": blockers, "warnings": warnings}


def _location_readiness(policy: dict, root: pathlib.Path, episode: str) -> list[dict]:
    try:
        locations = _read_json_source(policy, "locations", root)
    except (OSError, ValueError):
        locations = {}
    scenes = locations.get(episode) or {}
    rows = []
    for scene, record in sorted(scenes.items(), key=lambda item: int(item[0])):
        master = (record or {}).get("master") if isinstance(record, dict) else None
        master_path = resolve_declared_path(master, root) if master else None
        rows.append({
            "scene": str(scene),
            "locationId": (record or {}).get("locationId") if isinstance(record, dict) else None,
            "textLocked": bool(isinstance(record, dict) and record.get("look") and record.get("lighting")),
            "visualMaster": _relative(master_path, root) if master_path else None,
            "visualMasterCurrent": bool(master_path and master_path.exists()),
        })
    return rows


def status(episode: str | None = None, cast: Iterable[str] | None = None,
           root: str | pathlib.Path | None = None) -> dict:
    base = _root(root)
    try:
        policy = load_policy(base)
        manifest = load_manifest(base)
    except CanonLockError as exc:
        return {"schemaVersion": SCHEMA_VERSION, "showId": "crystal-bears",
                "current": False, "episode": episode, "episodeReady": False,
                "manifestDigest": None, "profileDigests": {}, "sources": [],
                "characters": [], "locations": [], "scriptCanon": None,
                "blockers": [{"code": "CANON_LOCK_MISSING", "message": str(exc),
                              "action": "Review canon, then run python3 engine/cb_canon.py lock."}],
                "warnings": []}

    blockers = []
    expected_manifest = _digest(_manifest_payload(manifest))
    if manifest.get("manifestDigest") != expected_manifest:
        blockers.append({"code": "CANON_MANIFEST_TAMPERED",
                         "message": "The canon manifest's own digest does not match its contents.",
                         "action": "Restore the approved manifest or review and explicitly re-lock canon."})
    if manifest.get("policySha256") != file_sha256(base / POLICY_REL):
        blockers.append({"code": "CANON_POLICY_DRIFT",
                         "message": "The canon lock policy changed after the current lock was approved.",
                         "action": "Review the policy change and explicitly re-lock canon."})
    source_blockers, source_rows = _source_integrity(policy, manifest, base)
    blockers.extend(source_blockers)
    blockers.extend(_asset_integrity(manifest, base))
    blockers.extend(_compatibility_integrity(policy, base))

    character_rows = _character_status(policy, manifest, base)
    cast_names = sorted(set(cast or (_episode_cast(base, episode) if episode else [])))
    by_name = {row["name"]: row for row in character_rows}
    episode_blockers = []
    for name in cast_names:
        row = by_name.get(name)
        if not row:
            episode_blockers.append({
                "code": "CAST_NOT_IN_LOCKED_ROSTER", "character": name,
                "message": f"{name} appears in the episode but is not in the locked roster.",
                "action": "Add and approve the character canon before Story & Direction.",
            })
        elif not row["productionReady"]:
            episode_blockers.append({
                "code": "CAST_CANON_INCOMPLETE", "character": name,
                "message": f"{name} is not production-ready: " + "; ".join(row["gaps"]),
                "action": "Complete and lock the named character record and references.",
            })

    script_canon = None
    script_path = None
    if episode:
        text, script_path = _script_text(base, episode)
        if text is not None:
            script_canon = validate_script(text, policy)
            episode_blockers.extend(script_canon["blockers"])

    locations = _location_readiness(policy, base, episode) if episode else []
    profile_digests = {}
    recorded_sources = manifest.get("sources") or {}
    for profile, source_ids in (policy.get("profiles") or {}).items():
        profile_digests[profile] = _digest({
            source_id: (recorded_sources.get(source_id) or {}).get("sha256")
            for source_id in source_ids
        })
    warnings = list((script_canon or {}).get("warnings") or [])
    warnings.extend({
        "code": "CANON_CREATIVE_GAP", "character": row["name"], "message": gap,
    } for row in character_rows for gap in row["creativeGaps"])
    warnings.extend({
        "code": "LOCATION_VISUAL_MASTER_PENDING", "scene": row["scene"],
        "message": f"Scene {row['scene']} has locked text canon but no approved reusable visual master yet."
    } for row in locations if row["textLocked"] and not row["visualMasterCurrent"])

    current = not blockers
    return {
        "schemaVersion": SCHEMA_VERSION,
        "showId": policy["showId"],
        "current": current,
        "lockedAt": manifest.get("lockedAt"),
        "lockedBy": manifest.get("lockedBy"),
        "manifestDigest": manifest.get("manifestDigest"),
        "profileDigests": profile_digests,
        "sourceCount": len(source_rows),
        "assetCount": sum(row["assetCount"] for row in character_rows) +
                      len(manifest.get("locationAssets") or []),
        "sources": source_rows,
        "characters": character_rows,
        "episode": episode,
        "episodeCast": cast_names,
        "episodeReady": bool(episode and current and not episode_blockers),
        "episodeBlockers": episode_blockers,
        "scriptPath": script_path,
        "scriptCanon": script_canon,
        "locations": locations,
        "blockers": blockers,
        "warnings": warnings,
    }


def require_locked(episode: str | None = None, cast: Iterable[str] | None = None,
                   root: str | pathlib.Path | None = None) -> dict:
    result = status(episode, cast, root)
    issues = list(result.get("blockers") or [])
    if episode:
        issues.extend(result.get("episodeBlockers") or [])
    if issues:
        messages = [str(item.get("message") or item.get("code")) for item in issues[:5]]
        raise CanonLockError("CANON LOCK REFUSED - " + " | ".join(messages))
    return result


def profile_digest(profile: str, *, episode: str | None = None,
                   cast: Iterable[str] | None = None,
                   root: str | pathlib.Path | None = None,
                   require_ready: bool = True) -> str:
    result = require_locked(episode, cast, root) if require_ready else status(episode, cast, root)
    digest = (result.get("profileDigests") or {}).get(profile)
    if not digest:
        raise CanonLockError(f"unknown or unavailable canon profile: {profile}")
    return digest


def source_hashes(profile: str, root: str | pathlib.Path | None = None) -> dict:
    base = _root(root)
    policy = load_policy(base)
    manifest = load_manifest(base)
    ids = (policy.get("profiles") or {}).get(profile)
    if ids is None:
        raise CanonLockError(f"unknown canon profile: {profile}")
    return {source_id: (manifest.get("sources", {}).get(source_id) or {}).get("sha256")
            for source_id in ids}


def story_context(cast: Iterable[str], episode: str,
                  root: str | pathlib.Path | None = None) -> dict:
    """Return the exact textual canon supplied to Story & Direction, not visual media bytes."""
    base = _root(root)
    names = sorted(set(cast))
    lock = require_locked(episode, names, base)
    policy = load_policy(base)
    characters = _read_json_source(policy, "characters", base)

    keep_fields = (
        "bible", "cadence", "actingNote", "gender", "size", "sizeRank", "sizeRef",
        "key_features", "lexicon", "cameraRegister", "crystalCall", "canonicalState",
        "states", "episodeArc", "promptRole", "isBee",
    )
    selected = {
        name: {key: characters[name].get(key) for key in keep_fields
               if characters.get(name, {}).get(key) not in (None, "", [], {})}
        for name in names if isinstance(characters.get(name), dict)
    }
    for name, record in selected.items():
        house = characters[name].get("house") or {}
        descriptions = {key: value for key, value in house.items()
                        if key.endswith("Desc") and value}
        if descriptions:
            record["homeCanon"] = descriptions

    def text(source_id: str) -> str:
        return resolve_declared_path(policy["sources"][source_id], base).read_text(
            encoding="utf-8")

    def data(source_id: str) -> Any:
        return _read_json_source(policy, source_id, base)

    performance = (data("characterPerformance").get("characters") or {})
    performance = {name: performance[name] for name in names if name in performance}
    return {
        "canonProfile": "story",
        "canonProfileDigest": lock["profileDigests"]["story"],
        "sourceHashes": source_hashes("story", base),
        "showBible": text("showBible"),
        "studioBible": text("studioBible"),
        "characters": selected,
        "characterPerformanceOverlay": performance,
        "relationships": data("relationships"),
        "episodeLocations": (data("locations").get(episode) or {}),
        "continuity": data("continuity"),
        "episodeArc": data("episodeArc"),
        "gagLocks": data("gagLocks"),
        "bannedVocabulary": data("bannedVocabulary"),
        "showrunnerTaste": text("showrunnerTaste"),
        "directorTaste": text("directorTaste"),
        "exemplars": data("exemplars"),
    }


def _summary(result: dict) -> str:
    locked = sum(1 for row in result.get("characters") or [] if row.get("productionReady"))
    stubs = [row["name"] for row in result.get("characters") or [] if row.get("status") == "stub"]
    return (f"CANON LOCK {'CURRENT' if result.get('current') else 'BLOCKED'} - "
            f"{result.get('sourceCount', 0)} sources, {result.get('assetCount', 0)} assets, "
            f"{locked} production-ready characters; stubs: {', '.join(stubs) or 'none'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    command = args[0] if args else "status"
    try:
        if command == "lock":
            by = args[1] if len(args) > 1 else "Julian"
            record = write_lock(locked_by=by)
            print(f"CANON LOCKED - {record['manifestDigest']} by {by}")
        elif command == "status":
            episode = args[1] if len(args) > 1 else None
            result = status(episode)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print(_summary(result), file=sys.stderr)
            if not result.get("current") or (episode and not result.get("episodeReady")):
                sys.exit(1)
        elif command == "context":
            if len(args) < 3:
                raise CanonLockError("context requires EPISODE CHARACTER [CHARACTER ...]")
            print(json.dumps(story_context(args[2:], args[1]), indent=2, ensure_ascii=False))
        else:
            raise CanonLockError("command must be lock|status|context")
    except CanonLockError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
