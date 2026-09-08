"""Reviewed copy of an established continuity-ledger project into a new workspace.

Original registries, packages and media remain in place. Historical shot records
stay read-only; new episodes use the project production engine. No approval is
inferred from a filename or from a successful render.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import time
import uuid

from studio_workspace import StudioError, digest, token, asset_digest


MEDIA = {".mp4", ".mov", ".m4v", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp"}


class Migration:
    def __init__(self, workspace):
        self.ws = workspace

    def path(self, value, bases=()):
        if not value or not isinstance(value, str) or '://' in value:
            return None
        raw = Path(value)
        candidates = [raw] if raw.is_absolute() else [self.ws.root / raw] + [self.ws.root / base / raw for base in bases]
        for path in candidates:
            resolved = path.resolve()
            if resolved.is_relative_to(self.ws.root) and resolved.is_file():
                return resolved
        return None

    def plan(self, pid):
        meta = self.ws.project(pid)
        if meta.get("setupVersion") == 1:
            raise StudioError("This project already uses the project workspace.")
        config = meta.get("configBase")
        package_base = meta.get("packageBase") or ("cb-output" if meta.get("primary") else None)
        if not config or not package_base:
            raise StudioError("This project's legacy layout needs an explicit package location before it can be imported.", "migration_layout")
        files, warnings = {}, []
        def record(path):
            stat = path.stat()
            relative = str(path.relative_to(self.ws.root))
            files[relative] = {"path": relative, "hash": asset_digest(str(path), stat.st_mtime_ns, stat.st_size), "bytes": stat.st_size}
            return files[relative]
        def read(value, default=None):
            path = self.path(value)
            if not path:
                return default
            record(path)
            return json.loads(path.read_text()) if path.suffix == '.json' else path.read_text()
        def media(value):
            path = self.path(value, ("cb-gen", config))
            return record(path) if path and path.suffix.lower() in MEDIA else None
        bible = read(meta.get("showBibleFile"), "")
        chars = read(f"{config}/characters.json", {})
        chars = {name: value for name, value in chars.items() if isinstance(value, dict) and (value.get("anchor") or value.get("voiceId"))}
        characters = {}
        for name, item in chars.items():
            anchor = media(item.get("anchor"))
            if anchor and Path(anchor["path"]).suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}:
                anchor = None
            if not anchor:
                warnings.append(f"{name}: visual character reference needs review.")
            characters[name] = {"source": item, "anchor": anchor, "refs": [r for v in item.get("refs", []) if (r := media(v))]}
        episodes = read(meta.get("episodesFile"), [])
        if not isinstance(episodes, list):
            raise StudioError("The episode register has an unsupported layout.")
        migrated_episodes = []
        folder = (self.ws.root / package_base).resolve()
        if not folder.is_relative_to(self.ws.root):
            raise StudioError("The package folder escapes this workspace.")
        for episode in episodes:
            number = token(episode.get("number"))
            script = self.path(episode.get("script"), ("cb-studio/data/scripts", str(Path(meta["episodesFile"]).parent)))
            if not script:
                warnings.append(f"Episode {number}: original script unavailable; preserved records can still be reviewed.")
            script_record = record(script) if script else None
            packages = []
            shots = []
            for path in sorted(folder.glob(f"Ep{number}_scene*_production_package.json")):
                package = json.loads(path.read_text())
                if str(package.get("episode", f"Ep{number}")) not in {number, f"Ep{number}"}:
                    raise StudioError("An episode package names a different episode.", "scope_mismatch")
                source = record(path)
                packages.append(source)
                ledger = {s["shotId"]: s for s in package.get("continuityLedger", [])}
                for planned in package.get("shots", []):
                    sid = token(planned["shotId"])
                    entry = ledger.get(sid, {})
                    approved = media(entry.get("approvedTake"))
                    evidence = entry.get("approval") or {}
                    accepted = bool(approved and entry.get("status") == "approved" and evidence.get("approved") is True and evidence.get("contentHash") == approved["hash"])
                    if entry.get("approvedTake") and not approved:
                        warnings.append(f"Episode {number} {sid}: approved footage is missing; its gap and original record will be preserved.")
                    if approved and not accepted:
                        warnings.append(f"Episode {number} {sid}: footage retained without a matching approval hash; shown as unapproved.")
                    ending = media(entry.get("harvestFrame"))
                    if ending and evidence.get("harvestHash") != ending["hash"]:
                        ending = None
                    # Preserve all recognizable local media in the ledger, including earlier candidates.
                    retained = []
                    def walk(value):
                        if isinstance(value, dict):
                            for child in value.values(): walk(child)
                        elif isinstance(value, list):
                            for child in value: walk(child)
                        elif isinstance(value, str) and Path(value).suffix.lower() in MEDIA:
                            item = media(value)
                            if item and item not in retained: retained.append(item)
                    walk(entry)
                    shots.append({"planned": planned, "ledger": entry, "package": source, "watch": approved,
                                  "approved": accepted, "ending": ending, "retained": retained,
                                  "scene": int(package.get("sceneNumber") or 1)})
            shots.sort(key=lambda s:(s["scene"], next((i for i,p in enumerate(json.loads((self.ws.root/s["package"]["path"]).read_text())["shots"]) if p["shotId"]==s["planned"]["shotId"]),0)))
            if len({s['planned']['shotId'] for s in shots}) != len(shots):
                raise StudioError("Duplicate legacy shot IDs need resolving before import.")
            migrated_episodes.append({"meta": episode, "script": script_record, "packages": packages, "shots": shots})
        # Location formats differ between old shows: keep their source documents intact.
        extra = []
        libraries = {"locations": [], "props": []}
        for name in ("locations.json", "props.json", "identity_packs.json", "voice_cards.json"):
            path = self.path(f"{config}/{name}")
            if path:
                extra.append(record(path))
                if name in {"locations.json", "props.json"}:
                    group = name.split('.')[0]
                    seen = set()
                    def collect(value):
                        if isinstance(value, list):
                            for v in value:collect(v)
                        elif isinstance(value, dict):
                            label = value.get('name')
                            if isinstance(label, str) and label and label not in seen:
                                seen.add(label)
                                reference = media(value.get('image') or value.get('anchor') or value.get('platePath'))
                                libraries[group].append({'name':label, 'notes':value.get('notes') or value.get('location') or value.get('description') or json.dumps(value,ensure_ascii=False), 'reference':reference})
                            else:
                                for v in value.values():collect(v)
                    collect(json.loads(path.read_text()))
        result = {"sourceProject": meta, "bible": bible, "characters": characters, "episodes": migrated_episodes,
                  "files": list(files.values()), "extra": extra, "libraries": libraries, "warnings": warnings}
        result["fingerprint"] = digest(result)
        return result

    def preview(self, pid):
        plan = self.plan(pid)
        return {"projectId": pid, "fingerprint": plan["fingerprint"], "suggestedId": (pid[:80] + "-workspace"),
                "episodes": [{"number": e["meta"]["number"], "title": e["meta"]["title"], "shots": len(e["shots"]), "approvedShots": sum(s["approved"] for s in e["shots"])} for e in plan["episodes"]],
                "characters": len(plan["characters"]), "files": len(plan["files"]), "bytes": sum(f["bytes"] for f in plan["files"]),
                "warnings": plan["warnings"], "meaning": "Create a separate upgraded workspace. Copy source records, media and matching approval evidence; keep historical shots read-only. Original production remains available. New episodes use the new agent."}

    def apply(self, payload):
        from studio_production import initial, Production
        source, target = token(payload.get("projectId")), token(payload.get("targetId"))
        plan = self.plan(source)
        if payload.get("fingerprint") != plan["fingerprint"] or payload.get("reviewed") is not True:
            raise StudioError("Review the current migration report before creating the upgraded workspace.", "stale")
        registry = self.ws.root / "cb-studio/data/projects.json"
        original_registry = registry.read_text()
        projects = json.loads(original_registry)
        if any(p["id"] == target for p in projects["projects"]) or (self.ws.root / "projects" / target).exists():
            raise StudioError("Choose an unused workspace ID. Existing projects will not be replaced.")
        temp = self.ws.root / "projects" / ("migration-" + uuid.uuid4().hex)
        temp.mkdir(parents=True)
        base = self.ws.root / "projects" / target
        published = False
        mapping = {}
        try:
            for name in ("assets", "media", "scripts", "archive"):(temp/name).mkdir()
            for item in plan["files"]:
                src = self.ws.root / item["path"]
                dest = temp / "archive" / (item["hash"] + src.suffix.lower())
                shutil.copyfile(src, dest)
                from studio_production import file_hash
                if file_hash(dest) != item["hash"]:
                    raise StudioError("A source file changed during migration. Preview again.", "stale")
                mapping[item["path"]] = {"path": f"projects/{target}/archive/{dest.name}", "hash": item["hash"]}
            characters = {}
            for name, item in plan["characters"].items():
                value = dict(item["source"])
                value.pop("anchor", None)
                value["refs"] = [mapping[r["path"]]["path"] for r in item["refs"]]
                if item["anchor"]:value["anchor"] = mapping[item["anchor"]["path"]]["path"]
                value["approvalStatus"] = "supplied"
                characters[name] = value
            (temp/"characters.json").write_text(json.dumps(characters, indent=2))
            (temp/"show_bible.md").write_text(plan["bible"])
            for group, values in plan["libraries"].items():
                entries=[]
                for value in values:
                    entry={'name':value['name'],'notes':value['notes'],'approvalStatus':'supplied'}
                    if value['reference']:entry['image']=mapping[value['reference']['path']]['path']
                    entries.append(entry)
                (temp/(group+'.json')).write_text(json.dumps(entries,indent=2))
            (temp/"media-index.json").write_text("[]")
            episode_records, states = [], []
            for e in plan["episodes"]:
                number = str(e["meta"]["number"])
                script_name = f"scripts/episode-{number}.txt"
                (temp/script_name).write_text((self.ws.root/e["script"]["path"]).read_text() if e["script"] else "Preserved production archive. Original screenplay unavailable.")
                episode_records.append({**e["meta"], "script": script_name, "productionArchive": bool(e["shots"])})
                state = initial()
                for old in e["shots"]:
                    planned = old["planned"]
                    sid = planned["shotId"]
                    outcomes = {}
                    if old["watch"]:
                        watch = {"id": "import-" + digest([source,number,sid,old["watch"]])[:24], "status": "approved" if old["approved"] else "candidate",
                                 "files": [mapping[old["watch"]["path"]]], "provenance": old["ledger"].get("approval"), "prompt": planned.get("seedancePrompt", "")}
                        if old["ending"]:
                            watch["ending"] = mapping[old["ending"]["path"]]
                            watch["files"].append(watch["ending"])
                        outcomes["watch"] = watch
                    shot = {"id": sid, "scene": old["scene"], "title": planned.get("purpose") or sid, "duration": planned.get("durationSec", 0),
                            "characters": planned.get("charactersInFrame", []), "props": [], "location": "", "startLine": None, "endLine": None,
                            "dialogue": [{"speaker": d.get("speaker", ""), "text": d.get("exactText", ""), "delivery": "neutral"} for d in planned.get("dialogueLines", [])],
                            "emotion": planned.get("visualPayoff", ""), "performance": planned.get("performanceAssignment", ""), "camera": planned.get("camera", ""),
                            "geography": str(planned.get("continuityProseIn", "")), "transition": "cut", "seePrompt": planned.get("keyframePrompt", ""),
                            "watchPrompt": planned.get("seedancePrompt", ""), "outcomes": outcomes, "versions": [], "importedArchive": True,
                            "legacy": {"projectId": source, "package": mapping[old["package"]["path"]], "record": old["ledger"], "retainedMedia": [mapping[r["path"]] for r in old["retained"]]}}
                    current_files={f['path'] for outcome in outcomes.values() for f in outcome.get('files',[])}
                    for retained in shot['legacy']['retainedMedia']:
                        if retained['path'] in current_files:continue
                        suffix=Path(retained['path']).suffix.lower()
                        kind='see' if suffix in {'.png','.jpg','.jpeg','.webp'} else 'hear' if suffix in {'.mp3','.wav'} else 'watch'
                        shot['versions'].append({'id':'archive-'+retained['hash'][:24],'stage':kind,'status':'archived','files':[retained]})
                    state["shots"].append(shot)
                states.append((number,state))
            (temp/"episodes.json").write_text(json.dumps(episode_records, indent=2))
            (temp/"migration-manifest.json").write_text(json.dumps({"sourceProject": source,"fingerprint":plan["fingerprint"],"files":mapping,"warnings":plan["warnings"],"createdAt":time.time()},indent=2))
            meta = {**plan["sourceProject"], "id": target, "name": plan["sourceProject"]["name"] + " · Workspace", "primary": False, "archived": False,
                    "setupVersion": 1, "configBase": f"projects/{target}", "episodesFile": f"projects/{target}/episodes.json", "showBibleFile":f"projects/{target}/show_bible.md",
                    "mediaBase":f"projects/{target}/media", "migratedFrom":source, "setupGaps":["Review imported library and organise location and prop references"], "coverImage":""}
            meta.pop("packageBase",None)
            with self.ws.db() as db:
                db.execute("BEGIN IMMEDIATE")
                if registry.read_text() != original_registry:
                    raise StudioError("The project list changed. Preview migration again.", "stale")
                for ep,state in states:Production(self.ws)._save(db,target,ep,state)
                temp.rename(base)
                projects["projects"].append(meta)
                pending = registry.with_name("projects-migration-"+uuid.uuid4().hex+".tmp")
                pending.write_text(json.dumps(projects,indent=2))
                pending.replace(registry)
                published = True
            return {"ok":True,"project":meta,"message":"Upgraded workspace created. Historical shots preserve their source evidence; new episodes use the production agent."}
        except Exception:
            if published:registry.write_text(original_registry)
            if base.exists() and not temp.exists():base.rename(temp)
            shutil.rmtree(temp,ignore_errors=True)
            raise
