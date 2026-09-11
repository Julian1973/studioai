"""Project-scoped source selections for text Directors, never media prompt boilerplate.

The manifest selects existing material, not a second bible. Full source hashes record
provenance; the dependency fingerprint covers only the sections read by this stage.
Nothing here grants approvals, changes canon locks or imports a neighbouring show's IP.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
VERSION = "creative-context-1.0.0"
AUDIT_PROVENANCE_FIELDS = {
    "originalSha256", "sourceSha256", "sha256", "md5", "sourcePath",
    "modifiedTime", "modifiedAt", "retrievedDate", "retrievedAt", "fetchedAt", "updatedAt",
}
STAGES = {"story": "story", "storyboard": "story", "plan": "story",
          "direction": "story", "chat": "story", "revise": "story",
          "see": "see", "look": "see", "scenelook": "see", "keyframe": "see",
          "cinematography": "see", "hear": "hear", "voice": "hear",
          "watch": "watch", "request": "watch", "animation": "watch",
          "review-animation": "watch", "review-keyframe": "see",
          "review": "review", "continuity": "review", "post": "post", "final": "post"}
POLICY = (
    "Use selected passages as source-grounded craft context. The current approved screenplay "
    "owns words/events; locked project canon and approved original references own identity/world; "
    "the current scoped user direction and signed shot record own execution. Reference-context "
    "bibles and research playbooks do not supersede those authorities or silently resolve their "
    "documented conflicts. Translate relevant principles into specific physical performance, "
    "composition, attention and timing in the typed direction. Creator names are provenance, "
    "never sufficient execution instructions or media-prompt text. Do not copy full source "
    "passages into media prompts. Recommendations, example shots, timing quotas and workflow "
    "suggestions create no canon, compulsory retake, numerical quality gate or new approval."
)


def _sha(value):
    raw = value if isinstance(value, bytes) else json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize_stage(stage):
    try:
        return STAGES[str(stage).lower()]
    except KeyError:
        raise ValueError(f"Unknown creative source stage: {stage}") from None


def project_id(context, default=None):
    """Explicit tenant disagreement fails instead of falling back to Crystal Bears."""
    project = context.get("project") or {}
    scope = context.get("learningScope") or {}
    candidates = [context.get("projectId"), context.get("showId"),
                  project.get("id"), project.get("showId"), scope.get("projectId")]
    ids = {str(value) for value in candidates if value}
    if len(ids) > 1:
        raise ValueError("Creative source project scope disagrees")
    pid = next(iter(ids), default)
    if not pid or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", pid):
        raise ValueError("Creative sources require an explicit project ID")
    return pid


def _section(text, selector):
    if selector.get("heading"):
        heading = selector["heading"]
        found = re.search(r"(?m)^" + re.escape(heading) + r"\s*$", text)
        if not found:
            raise ValueError(f"Creative source heading is missing: {heading}")
        level = len(heading) - len(heading.lstrip("#"))
        tail = text[found.end():]
        end = re.search(r"(?m)^#{1," + str(level) + r"} ", tail)
        return (heading + tail[:end.start()] if end else heading + tail).strip()
    if selector.get("start"):
        start = selector["start"]
        if text.count(start) != 1:
            raise ValueError(f"Creative source marker must be unique: {start}")
        value = text.split(start, 1)[1]
        end = selector.get("end")
        if end and end not in value:
            raise ValueError(f"Creative source end marker is missing: {end}")
        return (start + (value.split(end, 1)[0] if end else value)).strip()
    if selector.get("whole"):
        return text.strip()
    raise ValueError("Creative source requires an explicit section selector")


def _source_path(root, pid, row):
    raw = Path(row["path"])
    path = (root / raw).resolve()
    own = root / ("shows/crystal-bears" if pid == "crystal-bears" else f"projects/{pid}")
    if own.resolve() != own:
        raise ValueError("Creative source project folder aliases another location")
    # Crystal's explicitly registered repository craft references are private to that show.
    allowed = path.is_relative_to(own) or (pid == "crystal-bears" and
        path.is_relative_to((root / "skills").resolve()))
    if raw.is_absolute() or not path.is_relative_to(root) or not allowed:
        raise ValueError("Creative source path escapes the selected project")
    return path


def build_context(project_id, stage, *, root=None, supplied_bible=None):
    root = Path(root or ROOT).resolve()
    pid = globals()["project_id"]({"projectId": project_id})
    stage = normalize_stage(stage)
    base = root / ("shows/crystal-bears/creative" if pid == "crystal-bears" else f"projects/{pid}")
    manifest_path = base / "creative_sources.json"
    if base.resolve() != base or not manifest_path.resolve().is_relative_to(base):
        raise ValueError("Creative source manifest escapes the selected project")
    if pid == "crystal-bears" and not manifest_path.is_file():
        raise ValueError("Crystal Bears creative source manifest is missing")
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"projectId": pid, "sources": []}
    if manifest.get("projectId") != pid:
        raise ValueError("Creative source manifest belongs to a different project")
    if manifest_path.is_file() and manifest.get("schemaVersion") != 1:
        raise ValueError("Unsupported creative source manifest schema")
    rows = [row for row in manifest.get("sources", []) if stage in row["stages"]]
    # New projects use only their own supplied bible unless they explicitly register more.
    if pid != "crystal-bears" and not any(row.get("id") == "project-bible" for row in rows):
        path = root / f"projects/{pid}/show_bible.md"
        if path.is_file() or supplied_bible:
            rows.insert(0, {"id": "project-bible", "path": f"projects/{pid}/show_bible.md",
                           "authority": "project-source", "selector": {"whole": True},
                           "provenance": {"origin": "project show_bible.md"}})
    sources = []
    seen = set()
    for row in rows:
        if row["id"] in seen:
            raise ValueError("Duplicate selected creative source ID")
        seen.add(row["id"])
        if row.get("authority") not in {"project-source", "locked-canon", "craft-guidance", "reference-context"}:
            raise ValueError("Unknown creative source authority")
        path = _source_path(root, pid, row)
        if row["id"] == "project-bible" and supplied_bible is not None:
            raw = supplied_bible.encode("utf-8")
        else:
            raw = path.read_bytes()
        selected = _section(raw.decode("utf-8"), row["selector"])
        if not selected:
            raise ValueError(f"Creative source is empty: {row['id']}")
        if len(selected) > int(row.get("maxChars", 14000)):
            raise ValueError(f"Creative source {row['id']} needs narrower explicit section selectors")
        sources.append({"id": row["id"], "path": row["path"],
                        "authority": row["authority"], "selector": row["selector"],
                        "provenance": row.get("provenance", {}),
                        "sourceSha256": _sha(raw), "contentSha256": _sha(selected.encode()),
                        "text": selected})
    if sum(len(row["text"]) for row in sources) > 28000:
        raise ValueError("Selected creative context exceeds the stage budget; narrow source sections")
    # Audit-only whole-file hashes are deliberately excluded from dependency identity.
    dependencies = []
    for row in sources:
        dependency = {k: value for k, value in row.items() if k not in {"sourceSha256", "text"}}
        dependency['provenance'] = {k: value for k, value in row['provenance'].items()
                                    if k not in AUDIT_PROVENANCE_FIELDS}
        dependencies.append(dependency)
    fingerprint = _sha({"version": VERSION, "projectId": pid, "stage": stage,
                        "authorityPolicy": POLICY, "sources": dependencies})
    return {"version": VERSION, "projectId": pid, "stage": stage,
            "authorityPolicy": POLICY, "sources": sources, "fingerprint": fingerprint}


def receipt(bundle):
    """Small durable evidence of what the text call actually read."""
    return {**{key: bundle[key] for key in ("version", "projectId", "stage", "fingerprint")},
            "sources": [{k: v for k, v in row.items() if k != "text"} for row in bundle["sources"]]}


def bind_context(context, stage, *, root=None, default_project=None):
    pid = project_id(context, default_project)
    bundle = build_context(pid, stage, root=root, supplied_bible=context.get("bible"))
    return {**context, "creativeAuthority": bundle}


def for_role(role, *, root=None):
    """Legacy Creative Room is explicitly Crystal Bears, never a generic fallback."""
    stage = "hear" if "VOICE" in role.upper() else "story"
    return build_context("crystal-bears", stage, root=root)
