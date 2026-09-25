#!/usr/bin/env python3
"""Immutable screenplay storage with an auditable current-version pointer."""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import tempfile
import uuid
from typing import Any

import cb_lineage
import studio_profile


_EPISODE_RE = re.compile(r"^Ep([1-9][0-9]*)$")


class ScriptStoreError(RuntimeError):
    pass


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "Untitled"


def _atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = pathlib.Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _atomic_json(path: pathlib.Path, value: Any) -> None:
    _atomic_write(path, (json.dumps(value, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))


class ScriptStore:
    """Store immutable script bytes separately from the mutable active-version pointer."""

    def __init__(self, root: str | pathlib.Path, *, show_id: str | None = None,
                 script_root: str | pathlib.Path | None = None):
        self.root = pathlib.Path(root).resolve()
        if script_root is None:
            loaded = studio_profile.load_show_profile(self.root, show_id=show_id)
            self.show_id = loaded.profile.showId
            self.script_root = loaded.scripts_path
        else:
            self.show_id = studio_profile.validate_show_id(
                show_id or studio_profile.DEFAULT_SHOW_ID)
            self.script_root = pathlib.Path(script_root).resolve()
            try:
                self.script_root.relative_to(self.root)
            except ValueError as exc:
                raise ScriptStoreError("script_root must remain inside the repository") from exc
        self.studio_root = (
            self.root / "cb-studio" / "data" / "scripts"
            if self.show_id == studio_profile.DEFAULT_SHOW_ID
            else self.root / "cb-studio" / "data" / "shows" / self.show_id / "scripts"
        )
        self.versions_root = self.script_root / "_versions"
        self.current_root = self.script_root / "_current"
        self.events_root = self.script_root / "_events"

    @staticmethod
    def normalize_episode(episode: str | int) -> str:
        value = f"Ep{episode}" if isinstance(episode, int) else str(episode or "").strip()
        match = _EPISODE_RE.fullmatch(value)
        if not match:
            raise ScriptStoreError("episode must use the Ep<number> form")
        return f"Ep{int(match.group(1))}"

    def _relative(self, path: pathlib.Path) -> str:
        return str(path.resolve().relative_to(self.root))

    def _current_path(self, episode: str) -> pathlib.Path:
        return self.current_root / f"{episode}.json"

    def _recorded_content_path(self, relative: str) -> pathlib.Path:
        candidate = (self.root / str(relative or "")).resolve()
        try:
            candidate.relative_to(self.script_root.resolve())
        except ValueError as exc:
            raise ScriptStoreError("script pointer escapes the active show's script store") from exc
        return candidate

    def _version_paths(self, episode: str, digest: str) -> tuple[pathlib.Path, pathlib.Path]:
        base = self.versions_root / episode
        return base / f"{digest}.txt", base / f"{digest}.json"

    def store(self, episode: str | int, text: str, title: str, *, source_name: str = "",
              activated_by: str = "Julian", activated_at: str | None = None,
              event_kind: str = "script-uploaded") -> dict:
        episode_id = self.normalize_episode(episode)
        if not isinstance(text, str) or not text.strip():
            raise ScriptStoreError("script text cannot be empty")
        title = str(title or "").strip() or episode_id
        raw = text.encode("utf-8")
        digest = cb_lineage.sha256_bytes(raw)
        version_id = cb_lineage.SCRIPT_VERSION_PREFIX + digest
        content_path, record_path = self._version_paths(episode_id, digest)
        at = activated_at or _now()

        if content_path.exists():
            if content_path.read_bytes() != raw:
                raise ScriptStoreError(f"immutable script object is corrupt: {content_path}")
        else:
            _atomic_write(content_path, raw)

        version_record = {
            "schemaVersion": 1,
            "episodeId": episode_id,
            "scriptVersionId": version_id,
            "algorithm": "sha256",
            "sha256": digest,
            "byteLength": len(raw),
            "contentPath": self._relative(content_path),
            "createdAt": at,
            "sourceName": str(source_name or ""),
        }
        if record_path.exists():
            persisted = json.loads(record_path.read_text(encoding="utf-8"))
            immutable_keys = ("episodeId", "scriptVersionId", "sha256", "byteLength", "contentPath")
            if any(persisted.get(key) != version_record[key] for key in immutable_keys):
                raise ScriptStoreError(f"immutable script record is corrupt: {record_path}")
            version_record = persisted
        else:
            _atomic_json(record_path, version_record)

        previous = self.current(episode_id, verify=True, required=False)
        display_file = f"{episode_id}_{_slug(title)}.txt"
        for base in (self.script_root, self.studio_root):
            _atomic_write(base / display_file, raw)
            _atomic_write(base / f"{episode_id}.title", title.encode("utf-8"))

        activation_id = uuid.uuid4().hex
        event = {
            "schemaVersion": 1,
            "eventId": activation_id,
            "kind": event_kind,
            "episodeId": episode_id,
            "scriptVersionId": version_id,
            "previousScriptVersionId": (previous or {}).get("scriptVersionId"),
            "title": title,
            "displayFile": display_file,
            "activatedAt": at,
            "activatedBy": str(activated_by or ""),
        }
        _atomic_json(self.events_root / episode_id / f"{at.replace(':', '')}_{activation_id}.json", event)
        current = {
            "schemaVersion": 1,
            "episodeId": episode_id,
            "scriptVersionId": version_id,
            "sha256": digest,
            "byteLength": len(raw),
            "contentPath": self._relative(content_path),
            "versionRecordPath": self._relative(record_path),
            "displayFile": display_file,
            "title": title,
            "activationId": activation_id,
            "activatedAt": at,
            "activatedBy": str(activated_by or ""),
            "previousScriptVersionId": (previous or {}).get("scriptVersionId"),
        }
        _atomic_json(self._current_path(episode_id), current)
        # T34: the same identity bytes (a title rename) keep their signed line corrections,
        # so the readable script keeps the corrected words. A new upload is a new identity.
        corrections = self.dialogue_corrections(episode_id).get("corrections") or []
        if corrections:
            corrected = self._recorded_content_path(
                corrections[-1]["effectiveContentPath"]).read_bytes()
            for base in (self.script_root, self.studio_root):
                _atomic_write(base / display_file, corrected)
        return current

    def current(self, episode: str | int, *, verify: bool = True,
                required: bool = True) -> dict | None:
        episode_id = self.normalize_episode(episode)
        pointer_path = self._current_path(episode_id)
        if not pointer_path.exists():
            if required:
                raise ScriptStoreError(f"{episode_id} has no registered immutable script version")
            return None
        current = json.loads(pointer_path.read_text(encoding="utf-8"))
        if current.get("episodeId") != episode_id:
            raise ScriptStoreError(f"script pointer belongs to another episode: {pointer_path}")
        digest = cb_lineage.parse_script_version_id(current.get("scriptVersionId"))
        content_path = self._recorded_content_path(current.get("contentPath"))
        if verify:
            if not content_path.is_file():
                raise ScriptStoreError(f"immutable script content is missing: {content_path}")
            actual = cb_lineage.sha256_file(content_path)
            if actual != digest or current.get("sha256") != digest:
                raise ScriptStoreError(f"immutable script content failed SHA-256 verification: {content_path}")
        return current

    def content_path(self, episode: str | int) -> pathlib.Path:
        current = self.current(episode, verify=True, required=True)
        return self._recorded_content_path(current["contentPath"])

    def rename_current(self, episode: str | int, title: str, *, changed_by: str = "Julian") -> dict:
        current = self.current(episode, verify=True, required=True)
        text = self._recorded_content_path(current["contentPath"]).read_text(encoding="utf-8")
        return self.store(
            current["episodeId"], text, title,
            source_name=current.get("displayFile", ""),
            activated_by=changed_by,
            event_kind="episode-title-renamed",
        )

    def migrate_legacy(self, episode: str | int, path: str | pathlib.Path, title: str,
                       *, migrated_by: str = "Codex migration") -> dict:
        existing = self.current(episode, verify=True, required=False)
        if existing:
            return existing
        legacy = pathlib.Path(path)
        if not legacy.is_file():
            raise ScriptStoreError(f"legacy script does not exist: {legacy}")
        return self.store(
            episode,
            legacy.read_text(encoding="utf-8"),
            title,
            source_name=legacy.name,
            activated_by=migrated_by,
            event_kind="legacy-script-migrated",
        )

    # ── dialogue line corrections (T34, voice contract clauses 1 and 3) ────────────
    # Ruling (Julian, 2026-09-25): "Save corrected words" re-locks ONLY that line's voice.
    # The approved script is therefore the IDENTITY version (the bytes every approval and
    # every dialogueOccurrenceId is bound to) plus an append-only ledger of signed line
    # corrections. Each correction also stores the corrected full text as its own immutable
    # version (history, reading, export) without moving the identity pointer, so no other
    # approval re-locks and every occurrence keeps its ID.

    def _corrections_path(self, episode_id: str) -> pathlib.Path:
        return self.script_root / "_corrections" / f"{episode_id}.json"

    def dialogue_corrections(self, episode: str | int) -> dict:
        """The correction ledger for the episode's current identity version."""
        episode_id = self.normalize_episode(episode)
        current = self.current(episode_id, verify=True, required=False)
        empty = {"schemaVersion": 1, "episodeId": episode_id,
                 "identityScriptVersionId": (current or {}).get("scriptVersionId"),
                 "corrections": []}
        path = self._corrections_path(episode_id)
        if not current or not path.exists():
            return empty
        ledger = json.loads(path.read_text(encoding="utf-8"))
        if ledger.get("identityScriptVersionId") != current["scriptVersionId"]:
            # A new script upload is a new identity; older corrections belong to history.
            return empty
        return ledger

    def corrected_words(self, episode: str | int) -> dict[str, dict]:
        """dialogueOccurrenceId -> its latest correction entry (current words)."""
        latest = {}
        for entry in self.dialogue_corrections(episode).get("corrections") or []:
            latest[entry["dialogueOccurrenceId"]] = entry
        return latest

    def all_corrected_words(self) -> dict[str, dict]:
        """Every episode's current corrections, keyed by dialogueOccurrenceId (occurrence
        IDs are globally unique: they hash their own script version)."""
        latest = {}
        if not self.current_root.exists():
            return latest
        for pointer in sorted(self.current_root.glob("Ep*.json")):
            try:
                latest.update(self.corrected_words(pointer.stem))
            except (OSError, ValueError, ScriptStoreError, cb_lineage.LineageError):
                continue
        return latest

    def apply_corrections(self, lines: list[dict], *, text_key: str = "exactText") -> list[dict]:
        """Overlay approved corrections onto dialogue line records (copies, never in place).
        Each corrected line carries its identity text and the correction that changed it."""
        corrections = self.all_corrected_words()
        out = []
        for line in lines:
            entry = corrections.get(line.get("dialogueOccurrenceId"))
            if entry and line.get(text_key) is not None:
                # idempotent: an already-corrected record keeps its recorded identity text
                identity = line.get("identityText") or (
                    line[text_key] if line[text_key] != entry["toText"] else None)
                line = {**line, text_key: entry["toText"], "correctionId": entry["correctionId"]}
                if identity:
                    line["identityText"] = identity
            out.append(line)
        return out

    def effective_text(self, episode: str | int, dialogue_occurrence_id: str | None,
                       identity_text: str) -> str:
        """The approved words for one occurrence: its identity text unless corrected."""
        if not dialogue_occurrence_id:
            return identity_text
        entry = self.corrected_words(episode).get(dialogue_occurrence_id)
        return entry["toText"] if entry else identity_text

    def record_dialogue_correction(self, episode: str | int, *, dialogue_occurrence_id: str,
                                   speaker: str, from_text: str, to_text: str,
                                   effective_script_text: str, reason: str,
                                   corrected_by: str = "Julian") -> dict:
        """Append one explicit correction and store the corrected full script as an
        immutable history version. The identity pointer never moves."""
        episode_id = self.normalize_episode(episode)
        current = self.current(episode_id, verify=True, required=True)
        reason = str(reason or "").strip()
        if not reason:
            raise ScriptStoreError("a dialogue correction needs a stated reason")
        if str(from_text).strip() == str(to_text).strip():
            raise ScriptStoreError("the corrected words are the same as the approved words")
        at = _now()
        raw = effective_script_text.encode("utf-8")
        digest = cb_lineage.sha256_bytes(raw)
        content_path, record_path = self._version_paths(episode_id, digest)
        if content_path.exists():
            if content_path.read_bytes() != raw:
                raise ScriptStoreError(f"immutable script object is corrupt: {content_path}")
        else:
            _atomic_write(content_path, raw)
        if not record_path.exists():
            _atomic_json(record_path, {
                "schemaVersion": 1, "episodeId": episode_id,
                "scriptVersionId": cb_lineage.SCRIPT_VERSION_PREFIX + digest,
                "algorithm": "sha256", "sha256": digest, "byteLength": len(raw),
                "contentPath": self._relative(content_path), "createdAt": at,
                "sourceName": "dialogue-line-correction",
                "identityScriptVersionId": current["scriptVersionId"],
            })
        ledger = self.dialogue_corrections(episode_id)
        previous = self.corrected_words(episode_id).get(dialogue_occurrence_id)
        entry = {
            "correctionId": uuid.uuid4().hex,
            "dialogueOccurrenceId": dialogue_occurrence_id,
            "speaker": speaker,
            "fromText": from_text,
            "toText": to_text,
            "previousCorrectionId": (previous or {}).get("correctionId"),
            "reason": reason,
            "correctedBy": str(corrected_by or ""),
            "correctedAt": at,
            "effectiveScriptVersionId": cb_lineage.SCRIPT_VERSION_PREFIX + digest,
            "effectiveContentPath": self._relative(content_path),
        }
        ledger = {**ledger, "identityScriptVersionId": current["scriptVersionId"],
                  "corrections": [*(ledger.get("corrections") or []), entry]}
        _atomic_json(self._corrections_path(episode_id), ledger)
        _atomic_json(
            self.events_root / episode_id / f"{at.replace(':', '')}_{entry['correctionId']}.json", {
                "schemaVersion": 1, "eventId": entry["correctionId"],
                "kind": "dialogue-line-corrected", "episodeId": episode_id,
                "scriptVersionId": current["scriptVersionId"],
                "effectiveScriptVersionId": entry["effectiveScriptVersionId"],
                "dialogueOccurrenceId": dialogue_occurrence_id, "speaker": speaker,
                "fromText": from_text, "toText": to_text, "reason": reason,
                "activatedAt": at, "activatedBy": entry["correctedBy"],
            })
        # Humans read the corrected script; the identity bytes stay where approvals point.
        display_file = current.get("displayFile") or f"{episode_id}.txt"
        for base in (self.script_root, self.studio_root):
            _atomic_write(base / display_file, raw)
        return entry

    def effective_script_text(self, episode: str | int) -> str:
        """The readable current script: the identity bytes, or the latest correction's."""
        episode_id = self.normalize_episode(episode)
        corrections = self.dialogue_corrections(episode_id).get("corrections") or []
        if corrections:
            return self._recorded_content_path(
                corrections[-1]["effectiveContentPath"]).read_text(encoding="utf-8")
        return self.content_path(episode_id).read_text(encoding="utf-8")

    def list_current(self) -> list[dict]:
        if not self.current_root.exists():
            return []
        records = []
        for path in sorted(self.current_root.glob("Ep*.json")):
            try:
                records.append(self.current(path.stem, verify=True, required=True))
            except (OSError, ValueError, ScriptStoreError, cb_lineage.LineageError):
                continue
        return records
