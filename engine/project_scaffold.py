#!/usr/bin/env python3
"""T56 — a new project is created FROM THE TEMPLATE, never by hand.

`studio/templates/project/` is a complete, engine-valid project skeleton with `{{PLACEHOLDER}}`
tokens. `scaffold_project()` copies it to `projects/<id>/`, fills the tokens from the facts the
wizard collected, writes the cast the wizard was given into `canon/characters.json` and the Design
roster, and returns the loaded profile. It refuses to overwrite an existing project and never
touches any other project.

    python3 engine/project_scaffold.py "Box Monsters" --premise "..." --audience "..."
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
from typing import Any, Dict, Iterable, Optional

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TEMPLATE = ROOT / "studio" / "templates" / "project"

PLACEHOLDERS = ("PROJECT_ID", "PROJECT_NAME", "ANIMATION_TYPE", "ASPECT_RATIO", "PREMISE",
                "AUDIENCE", "EPISODE_LENGTH", "SHOWRUNNER")

DEFAULTS = {
    "ANIMATION_TYPE": "Stylized 3D CGI",
    "ASPECT_RATIO": "16:9",
    "PREMISE": "(premise to come)",
    "AUDIENCE": "(audience to come)",
    "EPISODE_LENGTH": "11-min episode",
    "SHOWRUNNER": "the showrunner",
}

_TEXT_SUFFIXES = {".json", ".md", ".txt"}


class ScaffoldError(RuntimeError):
    pass


def project_id_for(name: str, root: pathlib.Path = ROOT) -> str:
    """A unique, profile-valid id from a display name (box-monsters, box-monsters-2, …)."""
    base = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-") or "project"
    pid, n = base, 2
    while (root / "projects" / pid).exists():
        pid = f"{base}-{n}"
        n += 1
    return pid


def _fill(text: str, values: Dict[str, str]) -> str:
    for key in PLACEHOLDERS:
        text = text.replace("{{" + key + "}}", _json_safe(values.get(key, "")))
    return text


def _json_safe(value: str) -> str:
    # placeholders sit inside JSON strings and Markdown alike — escape what would break JSON
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")


def scaffold_project(name: str, *, root: pathlib.Path = ROOT, project_id: Optional[str] = None,
                     facts: Optional[Dict[str, Any]] = None,
                     characters: Optional[Iterable[Dict[str, Any]]] = None,
                     template: pathlib.Path = TEMPLATE) -> Dict[str, Any]:
    """Create projects/<id>/ from the template. Returns {"id", "root", "profile", "written"}."""
    name = str(name or "").strip()
    if not name:
        raise ScaffoldError("a project needs a name")
    if not template.is_dir():
        raise ScaffoldError(f"project template missing: {template}")
    pid = project_id or project_id_for(name, root)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", pid):
        raise ScaffoldError(f"invalid project id {pid!r}")
    dest = root / "projects" / pid
    if dest.exists():
        raise ScaffoldError(f"project {pid!r} already exists — never overwritten")

    facts = dict(facts or {})
    values = {**DEFAULTS, "PROJECT_ID": pid, "PROJECT_NAME": name}
    for key in PLACEHOLDERS:
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), key.lower())
        for candidate in (key, key.lower(), camel):
            if facts.get(candidate):
                values[key] = str(facts[candidate]).strip()
                break

    written = []
    for src in sorted(template.rglob("*")):
        rel = src.relative_to(template)
        target = dest / rel
        if src.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in _TEXT_SUFFIXES:
            target.write_text(_fill(src.read_text(encoding="utf-8"), values), encoding="utf-8")
        else:
            shutil.copy2(src, target)
        written.append(rel.as_posix())

    # the wizard's cast → canon/characters.json + laws/cast_vocabulary.json names + the Design roster
    cast = [c for c in (characters or []) if str((c or {}).get("name") or "").strip()]
    if cast:
        chars_path = dest / "canon" / "characters.json"
        chars = json.loads(chars_path.read_text(encoding="utf-8"))
        roster_path = dest / "creative" / "design_roster.json"
        roster = json.loads(roster_path.read_text(encoding="utf-8"))
        vocab_path = dest / "laws" / "cast_vocabulary.json"
        vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
        for i, c in enumerate(cast, start=1):
            cname = str(c["name"]).strip()
            entry: Dict[str, Any] = {
                "key_features": str(c.get("keyFeatures") or c.get("key_features") or "").strip(),
                "sizeRank": int(c.get("sizeRank") or i),
            }
            for key in ("species", "gender", "cadence", "voiceId", "role"):
                if c.get(key):
                    entry[key] = str(c[key]).strip()
            if c.get("anchor"):
                entry["anchor"] = str(c["anchor"])
                entry["refs"] = [str(c["anchor"])]
            chars[cname] = entry
            vocab.setdefault("names", []).append(cname)
            if entry.get("species"):
                vocab.setdefault("species", {})[cname] = entry["species"]
            roster.setdefault("characters", []).append({
                "name": cname, "scenes": "", "status": "ready" if c.get("anchor") else "draft",
                "role": str(c.get("role") or "").strip(), "identity": entry["key_features"],
                "reference": "Generate Reference Sheet",
                "wardrobes": [], "imageUrl": ("/" + str(c["anchor"])) if c.get("anchor") else "",
            })
        chars_path.write_text(json.dumps(chars, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        vocab_path.write_text(json.dumps(vocab, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        roster_path.write_text(json.dumps(roster, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        policy_path = dest / "canon" / "reference_slot_policy.json"
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        policy["characterOrder"] = [str(c["name"]).strip() for c in cast]
        policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    import project_profile
    loaded = project_profile.load_show_profile(root, pid)   # proves the fresh project is engine-valid
    return {"id": pid, "root": dest, "profile": loaded, "written": written}


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--id")
    for key in PLACEHOLDERS[2:]:
        ap.add_argument("--" + key.lower().replace("_", "-"))
    args = ap.parse_args(argv)
    facts = {k: getattr(args, k.lower()) for k in PLACEHOLDERS[2:] if getattr(args, k.lower())}
    out = scaffold_project(args.name, project_id=args.id, facts=facts)
    print(f"created projects/{out['id']}/ ({len(out['written'])} files) — profile valid: {out['profile'].profile.name}")


if __name__ == "__main__":
    import sys
    _main(sys.argv[1:])
