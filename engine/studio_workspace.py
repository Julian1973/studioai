"""Workspace connections and project context. No environment-key fallback.

Metadata lives outside the served checkout; credentials live only in the OS vault.
Each job pins a connection revision, so rotation cannot move an in-flight job to
another account. This module imports no show-specific production modules.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid
from functools import lru_cache
from contextlib import contextmanager


PROVIDERS = {
    "openai": {"label": "OpenAI", "base": "https://api.openai.com/v1", "check": "/models", "roles": ["direction", "review"]},
    "gemini": {"label": "Google Gemini · video review", "base": "https://generativelanguage.googleapis.com/v1beta", "check": "/models", "roles": ["review"]},
    "byteplus": {"label": "BytePlus ModelArk · Asia Pacific", "base": "https://ark.ap-southeast.bytepluses.com/api/v3", "check": "/contents/generations/tasks?page_size=1", "roles": ["keyframes", "animation"]},
    "byteplus-eu": {"label": "BytePlus ModelArk · Europe", "base": "https://ark.eu-west.bytepluses.com/api/v3", "check": "/contents/generations/tasks?page_size=1", "roles": ["keyframes", "animation"]},
    "elevenlabs": {"label": "ElevenLabs", "base": "https://api.elevenlabs.io", "check": "/v2/voices?page_size=1", "roles": ["voices"]},
}
ROLES = ("direction", "keyframes", "voices", "animation", "review")


class StudioError(ValueError):
    def __init__(self, message, code="invalid_request"):
        super().__init__(message)
        self.code = code


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@lru_cache(maxsize=256)
def asset_digest(path, modified_ns, size):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def token(value):
    value = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value):
        raise StudioError("Choose a valid project, episode or shot.")
    return value


class NativeVault:
    def __init__(self, workspace):
        self.service = "StudioAI/" + digest(str(workspace))[:24]

    def backend(self):
        try:
            import keyring
            backend = keyring.get_keyring()
            # Never accept a plaintext plugin, null backend or unverified fallback.
            if type(backend).__module__ not in {"keyring.backends.macOS", "keyring.backends.Windows", "keyring.backends.SecretService"}:
                raise RuntimeError()
            return backend
        except Exception:
            raise StudioError("Secure credential storage is unavailable. Enable the operating system keychain before saving a connection.", "vault_unavailable") from None

    def put(self, account, secret):
        try:
            self.backend().set_password(self.service, account, secret)
        except Exception:
            raise StudioError("The key could not be saved in the operating system keychain.", "vault_unavailable") from None

    def get(self, account):
        try:
            value = self.backend().get_password(self.service, account)
        except Exception:
            raise StudioError("Unlock the operating system keychain to use this connection.", "vault_unavailable") from None
        if not value:
            raise StudioError("This connection's key is missing. Reconnect it in Workspace connections.", "missing_key")
        return value


class Workspace:
    def __init__(self, root, *, private=None, vault=None):
        self.root = Path(root).resolve()
        self.private = Path(private or os.environ.get("STUDIO_WORKSPACE_PRIVATE") or
                            Path.home() / ".local/share/studioai" / digest(str(self.root))[:24])
        self.private.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.vault = vault or NativeVault(self.root)
        self.db_path = self.private / "workspace.sqlite3"
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY, revision INTEGER, data TEXT);
                CREATE TABLE IF NOT EXISTS credentials(id TEXT, revision INTEGER, data TEXT, PRIMARY KEY(id, revision));
                CREATE TABLE IF NOT EXISTS services(project TEXT PRIMARY KEY, data TEXT);
                CREATE TABLE IF NOT EXISTS production(project TEXT, episode TEXT, revision INTEGER, data TEXT, PRIMARY KEY(project,episode));
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project TEXT, episode TEXT, state TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS commands(project TEXT, episode TEXT, id TEXT, result TEXT, PRIMARY KEY(project,episode,id));
                CREATE TABLE IF NOT EXISTS library_versions(id TEXT PRIMARY KEY, project TEXT, data TEXT);
                CREATE TABLE IF NOT EXISTS character_states(project TEXT, id TEXT, data TEXT, PRIMARY KEY(project,id));
            """)
        os.chmod(self.db_path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def project(self, project_id):
        pid = token(project_id)
        registry = self.root / "cb-studio/data/projects.json"
        items = json.loads(registry.read_text()).get("projects", []) if registry.exists() else []
        meta = next((p for p in items if p.get("id") == pid), None)
        if not meta:
            raise StudioError("This project is not registered.", "unknown_project")
        return meta

    def project_path(self, pid, relative):
        base = (self.root / "projects" / token(pid)).resolve()
        if base != self.root / "projects" / pid:
            raise StudioError("Project folder escapes this workspace.")
        path = (self.root / str(relative).lstrip("/")).resolve()
        if not path.is_relative_to(base):
            raise StudioError("That file does not belong to the selected project.", "scope_mismatch")
        return path

    def context(self, pid, episode=None):
        meta = self.project(pid)
        if meta.get("setupVersion") != 1:
            return {"project": meta, "legacy": True}
        base = f"projects/{pid}"
        read = lambda name: self.project_path(pid, f"{base}/{name}").read_text()
        assets = {"characters": json.loads(read("characters.json")),
                  "locations": json.loads(read("locations.json")), "props": json.loads(read("props.json"))}
        episodes = json.loads(read("episodes.json"))
        context = {"project": meta, "bible": read("show_bible.md"), "assets": assets, "episodes": episodes}
        with self.db() as db:
            context["characterStates"] = [json.loads(r[0]) for r in db.execute("SELECT data FROM character_states WHERE project=? ORDER BY id", (pid,))]
        context["assetDigests"] = {}
        for item in list(assets["characters"].values()) + assets["locations"] + assets["props"] + context["characterStates"]:
            relative = item.get("anchor") or item.get("image")
            if relative:
                path = self.project_path(pid, relative)
                if path.is_file():
                    stat = path.stat()
                    context["assetDigests"][relative] = asset_digest(str(path), stat.st_mtime_ns, stat.st_size)
                else:
                    context["assetDigests"][relative] = "missing"
        if episode is not None:
            record = next((e for e in episodes if str(e["number"]) == str(episode)), None)
            if not record:
                raise StudioError("This episode does not belong to the selected project.", "scope_mismatch")
            context["episode"] = record
            context["script"] = self.project_path(pid, f"{base}/{record['script']}").read_text()
        context["sourceHash"] = digest({k: v for k, v in context.items() if k != "episodes"})
        return context

    def connections(self):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute("SELECT data FROM connections ORDER BY id")]

    def save_connection(self, payload):
        provider = payload.get("provider")
        if provider not in PROVIDERS:
            raise StudioError("Choose a supported provider.")
        label = str(payload.get("label") or PROVIDERS[provider]["label"]).strip()[:100]
        secret = str(payload.get("key") or "").strip()
        if not 12 <= len(secret) <= 1024 or any(c.isspace() for c in secret):
            raise StudioError("Enter the provider API key in the secure connection field.")
        cid = token(payload.get("id") or uuid.uuid4().hex)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM connections WHERE id=?", (cid,)).fetchone()
            if old and json.loads(old["data"])["provider"] != provider:
                raise StudioError("Create a separate connection to use a different provider.")
            revision = old["revision"] + 1 if old else 1
            self.vault.put(f"{cid}:{revision}", secret)
            public = {"id": cid, "revision": revision, "label": label, "provider": provider,
                      "maskedKey": "••••••••", "status": "unchecked", "enabled": True, "updatedAt": time.time()}
            db.execute("INSERT OR REPLACE INTO connections VALUES(?,?,?)", (cid, revision, json.dumps(public)))
            db.execute("INSERT INTO credentials VALUES(?,?,?)", (cid, revision, json.dumps(public)))
        return public

    def credential(self, cid, revision=None):
        with self.db() as db:
            row = db.execute("SELECT data FROM connections WHERE id=?", (token(cid),)).fetchone()
            if not row:
                raise StudioError("Connect the selected provider in Workspace connections.", "missing_connection")
            connection = json.loads(row[0])
            if revision is not None:
                row = db.execute("SELECT data FROM credentials WHERE id=? AND revision=?", (cid, revision)).fetchone()
                if not row:
                    raise StudioError("The job's original connection revision is unavailable.")
                connection = json.loads(row[0])
            elif not connection["enabled"]:
                raise StudioError("This connection is disabled. Reconnect it before starting work.", "disabled_connection")
        return connection, self.vault.get(f"{cid}:{connection['revision']}")

    def connection_action(self, cid, action):
        if action not in {"check", "disable"}:
            raise StudioError("Choose check or disable.")
        if action == "check":
            connection, key = self.credential(cid)
        else:
            connection = next((c for c in self.connections() if c["id"] == cid), None)
            if not connection:
                raise StudioError("That connection is unavailable.")
        if action == "check":
            from studio_transport import ProviderTransport
            try:
                ProviderTransport().check(connection, key)
                status = "connected"
            except StudioError as exc:
                status = exc.code
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT data FROM connections WHERE id=?", (cid,)).fetchone()[0])
            if current["revision"] != connection["revision"]:
                raise StudioError("The key changed during this check. Check the new connection again.", "stale")
            current.update({"status": status, "checkedAt": time.time()} if action == "check" else {"enabled": False, "status": "disabled"})
            db.execute("UPDATE connections SET data=? WHERE id=?", (json.dumps(current), cid))
        return current

    def services(self, pid):
        self.project(pid)
        with self.db() as db:
            row = db.execute("SELECT data FROM services WHERE project=?", (pid,)).fetchone()
            return json.loads(row[0]) if row else {}

    def update_library(self, payload, decode_image):
        """Versioned library edits; original reference image files are never replaced."""
        pid = token(payload.get("projectId"))
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            context = self.context(pid)
            if context.get("legacy") or context["project"].get("archived"):
                raise StudioError("Use this project's existing library editor.")
            if payload.get("sourceHash") != context["sourceHash"]:
                raise StudioError("The library changed. Reopen it before saving this edit.", "stale")
            group = payload.get("group")
            if group == "states":
                return self.update_character_state(db, context, payload, decode_image)
            if group not in {"bible", "characters", "locations", "props"}:
                raise StudioError("Choose the bible, characters, locations or props.")
            text = str(payload.get("notes") or "").strip()
            if len(text) > 200000:
                raise StudioError("Keep the library entry under 200,000 characters.")
            name = str(payload.get("name") or "").strip()
            if group != "bible" and (not name or len(name) > 100):
                raise StudioError("Give this asset a name under 100 characters.")
            file = self.project_path(pid, f"projects/{pid}/" + ("show_bible.md" if group == "bible" else group + ".json"))
            old = file.read_text()
            image = None
            if payload.get("imageData") and group != "bible":
                blob, ext = decode_image(payload["imageData"])
                image = f"projects/{pid}/assets/{group}-{uuid.uuid4().hex}{ext}"
                self.project_path(pid, image).write_bytes(blob)
            if group == "bible":
                updated = text
            else:
                values = json.loads(old)
                names = list(values) if group == "characters" else [v["name"] for v in values]
                if any(n.casefold() == name.casefold() and n != name for n in names):
                    raise StudioError("Use the existing asset's exact name to update it.")
                entry = values.get(name, {}) if group == "characters" else next((v for v in values if v["name"] == name), None)
                if entry is None:
                    entry = {"name": name}
                    values.append(entry)
                entry["key_features" if group == "characters" else "notes"] = text
                entry["approvalStatus"] = "approved" if payload.get("approve") is True else "draft"
                entry["version"] = uuid.uuid4().hex
                if group == "characters" and "identityTraits" in payload:
                    traits = payload["identityTraits"]
                    if not isinstance(traits, dict) or len(traits) > 30 or any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 80 or len(v) > 300 for k, v in traits.items()):
                        raise StudioError("Use short named identity traits and values.")
                    entry["identityTraits"] = traits
                if image:
                    entry["anchor" if group == "characters" else "image"] = image
                    if group == "characters":
                        entry["refs"] = [image]
                if group == "characters":
                    values[name] = entry
                updated = json.dumps(values, indent=2, ensure_ascii=False)
            db.execute("INSERT INTO library_versions VALUES(?,?,?)", (uuid.uuid4().hex, pid,
                json.dumps({"file": str(file.relative_to(self.root)), "content": old, "at": time.time()})))
            temporary = file.with_name(file.name + "." + uuid.uuid4().hex + ".tmp")
            with temporary.open("w") as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(file)
        return {"ok": True, "context": self.context(pid)}

    def update_character_state(self, db, context, payload, decode_image):
        pid = context["project"]["id"]
        sid = token(payload.get("id") or uuid.uuid4().hex)
        old = next((v for v in context["characterStates"] if v["id"] == sid), None)
        character, name = str(payload.get("character") or ""), str(payload.get("name") or "").strip()
        if character not in context["assets"]["characters"] or not name or len(name) > 100:
            raise StudioError("Choose this project's character and name the state.")
        if old and old["character"] != character:
            raise StudioError("Create a separate state for another character.")
        scenes = payload.get("scenes") or []
        if not isinstance(scenes, list) or any(type(n) is not int or n < 1 for n in scenes):
            raise StudioError("Scene numbers must be positive whole numbers.")
        episode = str(payload.get("episode") or "")
        if episode and not any(str(e["number"]) == episode for e in context["episodes"]):
            raise StudioError("Select an episode from this project.", "scope_mismatch")
        if scenes and not episode:
            raise StudioError("Choose the episode for these scene numbers.")
        image = (old or {}).get("image")
        if payload.get("imageData"):
            blob, ext = decode_image(payload["imageData"])
            image = f"projects/{pid}/assets/state-{uuid.uuid4().hex}{ext}"
            self.project_path(pid, image).write_bytes(blob)
        if not image:
            raise StudioError("Add a reference image for this character state.")
        value = {"id": sid, "character": character, "name": name, "notes": str(payload.get("notes") or "")[:12000],
                 "episode": episode, "scenes": scenes, "image": image, "version": uuid.uuid4().hex,
                 "approvalStatus": "approved" if payload.get("approve") is True else "draft", "updatedAt": time.time()}
        if old:
            db.execute("INSERT INTO library_versions VALUES(?,?,?)", (uuid.uuid4().hex, pid, json.dumps({"state": old, "at": time.time()})))
        db.execute("INSERT OR REPLACE INTO character_states VALUES(?,?,?)", (pid, sid, json.dumps(value)))
        # Return the saved record; the caller fetches context after the transaction commits.
        return {"ok": True, "characterState": value}

    def save_services(self, pid, values):
        self.project(pid)
        clean = {}
        connections = {c["id"]: c for c in self.connections()}
        for role, value in values.items():
            if role not in ROLES or not isinstance(value, dict):
                raise StudioError("Choose direction, keyframes, voices, animation or review.")
            if not value.get("connectionId"):
                continue
            connection = connections.get(value["connectionId"])
            if not connection or role not in PROVIDERS[connection["provider"]]["roles"]:
                raise StudioError(f"Choose a compatible connection for {role}.")
            model = str(value.get("model") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,149}", model):
                raise StudioError(f"Enter the provider model ID for {role}.")
            try:
                from decimal import Decimal
                cost = Decimal(str(value.get("estimateUsd")))
                if not cost.is_finite() or not 0 < cost <= 1000:
                    raise ValueError()
            except Exception:
                raise StudioError(f"Enter a positive per-request budget estimate for {role}.") from None
            if role == "voices" and model != "eleven_v3":
                raise StudioError("The voice adapter currently supports ElevenLabs v3.")
            clean[role] = {"connectionId": connection["id"], "model": model, "estimateUsd": float(cost)}
            if role in {'keyframes','voices','animation'} and value.get('unitUsd') not in (None, ''):
                try:
                    rate = Decimal(str(value['unitUsd']))
                    if not rate.is_finite() or not 0 < rate <= 1000: raise ValueError()
                except Exception:
                    raise StudioError('Enter a positive unit price from your provider account.') from None
                clean[role]['unitUsd'] = float(rate)
            if role == 'direction' and value.get('routing'):
                from studio_model_policy import validate_routes
                clean[role]['routing'] = validate_routes(value['routing'])
            if role == 'review' and connection['provider'] == 'gemini':
                fps = value.get('videoFps', 4)
                if isinstance(fps, bool) or str(fps) not in {'1', '4', '8'}:
                    raise StudioError('Choose standard, detailed or close motion inspection for video review.')
                clean[role]['videoFps'] = int(fps)
            elif role == 'review':
                audio_model = str(value.get('audioModel') or '').strip()
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,149}', audio_model):
                    raise StudioError('Enter an audio-input Chat Completions model ID for media review.')
                clean[role]['audioModel'] = audio_model
            if role == "voices":
                casting = value.get("casting") or {}
                if not isinstance(casting, dict) or any(not re.fullmatch(r"[A-Za-z0-9]{12,64}", str(v)) for v in casting.values()):
                    raise StudioError("Voice casting needs a provider voice ID for each named character.")
                clean[role]["casting"] = {str(k)[:100]: str(v) for k, v in casting.items()}
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO services VALUES(?,?)", (pid, json.dumps(clean)))
        return clean

    def binding(self, pid, role):
        service = self.services(pid).get(role)
        if not service:
            raise StudioError(f"Choose a {role} connection and model in Project services.", "missing_service")
        connection, _ = self.credential(service["connectionId"])
        return {**service, "revision": connection["revision"], "provider": connection["provider"]}
