"""Canonical project onboarding and discovery without provider calls."""
from __future__ import annotations

import datetime
import json
import pathlib
import re

import cb_db
import cb_scripts
import studio_profile


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def list_projects(root):
    root = pathlib.Path(root).resolve()
    registry = root / "cb-studio/data/projects.json"
    legacy = _json(registry) if registry.exists() else {"projects": []}
    rows = {p["id"]: dict(p) for p in legacy.get("projects", [])}
    for manifest in sorted((root / "shows").glob("*/profile.json")):
        loaded = studio_profile.load_show_profile(root, manifest.parent.name)
        meta_path = loaded.show_root / "project.json"
        meta = _json(meta_path) if meta_path.exists() else {}
        pid = loaded.profile.showId
        row = {**rows.get(pid, {}), **meta, "id": pid,
               "name": loaded.profile.name,
               "animationType": loaded.profile.animationType,
               "aspectRatio": loaded.profile.aspectRatio,
               "profileFile": str(manifest.relative_to(root)),
               "configBase": str(loaded.canon_paths["characters"].parent.relative_to(root)),
               "showBibleFile": str(loaded.canon_paths["lockedCanon"].relative_to(root)),
               "capabilities": studio_profile.capability_report(loaded)}
        rows[pid] = row
    for row in rows.values():
        canon = root / row.get("configBase", f"projects/{row['id']}") / "characters.json"
        chars = _json(canon) if canon.exists() else {}
        row["characterCount"] = sum(
            isinstance(v, dict) and not k.startswith("_") and k != "sizeClasses"
            for k, v in chars.items())
        episode_path = root / row.get("episodesFile", f"projects/{row['id']}/episodes.json")
        episodes = _json(episode_path) if episode_path.exists() else []
        row["episodeCount"] = len(episodes if isinstance(episodes, list) else episodes.get("episodes", []))
    return list(rows.values())


def create_project(root, data, *, decode_image):
    """Validate first, reserve an exclusive directory, publish its profile last.

    Discovery is based on profiles, so incomplete writes cannot appear as a ready
    project. Existing projects are never overwritten, including concurrent requests.
    """
    root = pathlib.Path(root).resolve()
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 160:
        raise ValueError("Project name must contain between 1 and 160 characters")
    aspect = str(data.get("aspectRatio") or "16:9").strip()
    if aspect not in {"16:9", "9:16", "1:1", "4:3", "2.39:1"}:
        raise ValueError("Choose a supported aspect ratio")
    medium = str(data.get("animationType") or "").strip()
    if not medium:
        raise ValueError("Choose the production medium")
    characters = data.get("characters") or []
    if not isinstance(characters, list) or len(characters) > 100:
        raise ValueError("Characters must be a list of at most 100 entries")
    decoded = []
    seen = set()
    for index, char in enumerate(characters):
        if not isinstance(char, dict):
            raise ValueError("Each character must contain a name and description")
        char_name = str(char.get("name") or "").strip()
        if not char_name or char_name.casefold() in seen:
            raise ValueError("Character names must be present and unique")
        seen.add(char_name.casefold())
        image = decode_image(char["imageData"]) if char.get("imageData") else None
        decoded.append((index, char_name, str(char.get("keyFeatures") or ""), image))
    cover = decode_image(data["coverImageData"]) if data.get("coverImageData") else None
    base_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80].rstrip("-") or "production"
    shows = root / "shows"
    shows.mkdir(parents=True, exist_ok=True)
    reserved = {p["id"] for p in list_projects(root)}
    serial = 1
    while True:
        pid = base_id if serial == 1 else f"{base_id}-{serial}"
        serial += 1
        if pid in reserved or (root / "projects" / pid).exists():
            continue
        target = shows / pid
        try:
            target.mkdir()
            break
        except FileExistsError:
            continue
    for directory in ("canon", "assets", "laws", "episodes/scripts", "episodes/output", "creative", "media"):
        (target / directory).mkdir(parents=True, exist_ok=True)
    chars = {}
    for index, char_name, features, image in decoded:
        entry = {"key_features": features}
        if image:
            blob, ext = image
            asset = target / "assets" / f"character_{index + 1}{ext}"
            cb_db.atomic_write_bytes(root, asset, blob)
            entry["anchor"] = str(asset.relative_to(root))
            entry["refs"] = [entry["anchor"]]
        chars[char_name] = entry
    profile = {
        "showId": pid, "name": name, "animationType": medium,
        "aspectRatio": aspect, "engineAdapter": "studio-generic-v1",
        "canon": {"lockedCanon": "canon/LOCKED_CANON.md",
                  "characters": "canon/characters.json", "locations": "canon/locations.json",
                  "continuity": "canon/continuity.json"},
        "laws": {"style": "laws/style.txt"},
        "episodes": {"scripts": "episodes/scripts", "output": "episodes/output"},
        "creativeRoot": "creative",
    }
    studio_profile.ShowProfile.model_validate(profile)
    for filename, value in (("characters.json", chars), ("locations.json", {}), ("continuity.json", {})):
        cb_db.atomic_write_json(root, target / "canon" / filename, value)
    cb_db.atomic_write_bytes(root, target / "canon/LOCKED_CANON.md",
                             str(data.get("showBible") or "").encode("utf-8"))
    cb_db.atomic_write_bytes(root, target / "laws/style.txt", str(data.get("style") or "").encode("utf-8"))
    cb_db.atomic_write_json(root, target / "episodes/episodes.json", [])
    accent = str(data.get("accentColor") or "").lower()
    meta = {"id": pid, "name": name, "primary": False,
            **{key: str(data.get(key) or "") for key in (
                "premise", "audience", "episodeLength", "voiceProvider", "musicStyle", "style")},
            "animationType": medium, "aspectRatio": aspect,
            "theme": {"accent": accent if re.fullmatch(r"#[0-9a-f]{6}", accent) else "#0b8f87"},
            "configBase": f"shows/{pid}/canon",
            "showBibleFile": f"shows/{pid}/canon/LOCKED_CANON.md",
            "episodesFile": f"shows/{pid}/episodes/episodes.json",
            "mediaBase": f"shows/{pid}/media",
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "setupStatus": "development"}
    if cover:
        blob, ext = cover
        asset = target / "assets" / f"project_key_art{ext}"
        cb_db.atomic_write_bytes(root, asset, blob)
        meta["coverImage"] = meta["episodeCoverImage"] = "/" + str(asset.relative_to(root))
    cb_db.atomic_write_json(root, target / "project.json", meta)
    # Publishing the manifest makes this project discoverable, without a second registry write.
    cb_db.atomic_write_json(root, target / "profile.json", profile)
    return next(row for row in list_projects(root) if row["id"] == pid)


def store_script(root, show_id, episode, script, title, *, source_name="pasted-script", by="Julian"):
    """Store development scripts in the selected tenant, never the active server's show."""
    root = pathlib.Path(root).resolve()
    loaded = studio_profile.load_show_profile(root, show_id)
    store = cb_scripts.ScriptStore(root, show_id=show_id)
    current = store.store(episode, script, title, source_name=source_name, activated_by=by)
    return _script_result(root, loaded, store, current)


def rename_script(root, show_id, episode, title):
    root = pathlib.Path(root).resolve()
    loaded = studio_profile.load_show_profile(root, show_id)
    store = cb_scripts.ScriptStore(root, show_id=show_id)
    current = store.rename_current(episode, title)
    return _script_result(root, loaded, store, current)


def _script_result(root, loaded, store, current):
    show_id = loaded.profile.showId
    episodes = [{"number": int(row["episodeId"][2:]), "title": row["title"],
                 "script": row["displayFile"], "scriptVersionId": row["scriptVersionId"],
                 "status": "Script uploaded", "projectId": show_id}
                for row in store.list_current()]
    cb_db.atomic_write_json(root, loaded.show_root / "episodes/episodes.json", episodes)
    return {"ok": True, "script": current["displayFile"],
            "scriptVersionId": current["scriptVersionId"], "episodes": episodes,
            "projectId": show_id, "zeroSpend": True}
