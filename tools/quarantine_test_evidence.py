#!/usr/bin/env python3
"""Remove test-generated records from live learning while preserving an audit copy."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = (
    ROOT / "projects" / "crystal-bears" / "creative" / "learning"
    / "EVIDENCE_LIBRARY.json"
)


def _atomic_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = pathlib.Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=1, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def quarantine(library_path: pathlib.Path, quarantine_dir: pathlib.Path) -> dict:
    library_path = library_path.resolve()
    raw = library_path.read_bytes()
    library = json.loads(raw)
    records = list(library.get("records") or [])
    contaminated = [
        record for record in records
        if str(record.get("capturedBy") or "").startswith("TestReviewer")
    ]
    retained = [record for record in records if record not in contaminated]
    if not contaminated:
        return {"changed": False, "removed": 0, "retained": len(retained)}

    now = datetime.datetime.now(datetime.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    quarantine_path = quarantine_dir / f"TEST_EVIDENCE_{stamp}.json"
    archive = {
        "schemaVersion": 1,
        "kind": "test-evidence-quarantine",
        "quarantinedAt": now.isoformat(timespec="seconds"),
        "sourcePath": str(library_path),
        "sourceSha256": hashlib.sha256(raw).hexdigest(),
        "reason": (
            "Records produced by automated tests were written into the live creative "
            "learning store. They are preserved here but are not production evidence."
        ),
        "recordCount": len(contaminated),
        "records": contaminated,
    }
    _atomic_json(quarantine_path, archive)

    library["records"] = retained
    try:
        archive_path = str(quarantine_path.relative_to(ROOT))
    except ValueError:
        archive_path = str(quarantine_path)
    library["quarantine"] = {
        "correctedAt": now.isoformat(timespec="seconds"),
        "removedTestRecords": len(contaminated),
        "archivePath": archive_path,
        "sourceSha256BeforeCorrection": archive["sourceSha256"],
    }
    _atomic_json(library_path, library)
    return {
        "changed": True,
        "removed": len(contaminated),
        "retained": len(retained),
        "archive": str(quarantine_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", type=pathlib.Path, default=DEFAULT_LIBRARY)
    parser.add_argument(
        "--quarantine-dir",
        type=pathlib.Path,
        default=DEFAULT_LIBRARY.parent / "quarantine",
    )
    args = parser.parse_args()
    print(json.dumps(quarantine(args.library, args.quarantine_dir), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
