"""Durable provider-task identity. No secret values are persisted."""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import tempfile


class SubmissionUnknown(RuntimeError):
    pass


def record_path(output):
    return pathlib.Path(str(output) + ".provider-task.json")


def read(output):
    p = record_path(output)
    return json.loads(p.read_text()) if p.exists() else {}


def save(output, record):
    p = record_path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=p.parent, prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, p)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fingerprint(contract, prompt, images, audio, videos, duration, resolution, generate_audio):
    def asset(value):
        value = str(value)
        if not value.startswith(("https://", "http://", "data:")) and pathlib.Path(value).is_file():
            with open(value, "rb") as handle:
                return hashlib.file_digest(handle, "sha256").hexdigest()
        return hashlib.sha256(value.encode()).hexdigest()
    value = {"contract": contract, "prompt": prompt, "images": list(map(asset, images)),
             "audio": list(map(asset, audio)), "videos": list(map(asset, videos)),
             "duration": duration, "resolution": resolution, "generateAudio": generate_audio}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def resumable(output):
    record = read(output)
    return bool(record.get("taskId") and record.get("state") not in ("failed", "expired"))
