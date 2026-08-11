#!/usr/bin/env python3
"""Append-only prompt bank for approved and rejected render emissions."""
from __future__ import annotations

import argparse
import collections
import datetime as _dt
import hashlib
import json
import pathlib
import re
from typing import Any

import cb_emission_standard

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_BANK_PATH = ROOT / "cb-output" / "prompt-bank" / "prompt_bank.jsonl"
SCHEMA_VERSION = 1


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_prompt_structure(prompt: str) -> dict[str, Any]:
    """Parse prompt sections at bank time, without changing the submitted text."""
    text = str(prompt or "")
    lines = text.splitlines()
    headers = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s*\[([^\]\n]+)\]\s*$", line)
        if match:
            headers.append((index, match.group(1).strip()))
    sections = []
    for pos, (start, name) in enumerate(headers):
        end = headers[pos + 1][0] if pos + 1 < len(headers) else len(lines)
        body = "\n".join(lines[start + 1:end]).strip()
        sections.append({
            "name": name,
            "startLine": start + 1,
            "charCount": len(body),
            "wordCount": len(body.split()),
            "empty": not bool(body),
        })
    return {
        "charCount": len(text),
        "wordCount": len(text.split()),
        "lineCount": len(lines),
        "sectionOrder": [item["name"] for item in sections],
        "sections": sections,
        "shotCount": len(re.findall(r"(?im)^Shot\s+\d+\s*(?:[-—:]|\.)", text)),
        "hasDialogue": bool(re.search(r"\{[^}]+\}", text)),
        "audioPolicy": {
            "noMusic": bool(re.search(r"\bNo music\b", text, re.I)),
            "hasAudioAuthority": bool(re.search(r"AUDIO-(?:AUTHORITY|LOCK)|@Audio1", text, re.I)),
        },
    }


def infer_archetype(prompt: str, metadata: dict[str, Any] | None = None) -> str:
    meta = metadata or {}
    explicit = meta.get("archetype") or meta.get("beatArchetype")
    if explicit:
        return str(explicit)
    text = str(prompt or "").lower()
    if "moustache" in text or "mustache" in text:
        return "reveal-and-deadpan-verdict"
    if "triple twist" in text or "double tuck" in text or "buzz crash" in text:
        return "escalation-into-verdict"
    if "chase" in text or "pursuit" in text or "near-miss" in text:
        return "false-triumph-chase"
    if "storm" in text or "turns" in text and "world" in text:
        return "environment-turn"
    return "unclassified"


def _record_id(record: dict[str, Any]) -> str:
    payload = json.dumps({
        "schemaVersion": record["schemaVersion"],
        "episode": record["episode"],
        "scene": record["scene"],
        "shotId": record["shotId"],
        "outcome": record["outcome"],
        "candidate": record.get("candidate"),
        "promptHash": record["promptHash"],
        "bankedAt": record["bankedAt"],
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def bank_prompt(*, prompt: str, episode: str, scene: str, shot_id: str,
                artifact_type: str = "animation", outcome: str,
                candidate: int | None = None, candidate_path: str | None = None,
                diagnosis: str | None = None, category: str | None = None,
                metadata: dict[str, Any] | None = None,
                conformance: dict[str, Any] | None = None,
                bank_path: pathlib.Path | str = DEFAULT_BANK_PATH) -> dict[str, Any]:
    if outcome not in {"approved", "rejected"}:
        raise ValueError("prompt bank outcome must be approved or rejected")
    parsed = parse_prompt_structure(prompt)
    archetype = infer_archetype(prompt, metadata)
    conformance = conformance or cb_emission_standard.preflight(prompt)
    record = {
        "schemaVersion": SCHEMA_VERSION,
        "recordId": "",
        "bankedAt": _now(),
        "episode": str(episode),
        "scene": str(scene),
        "shotId": str(shot_id),
        "artifactType": artifact_type,
        "outcome": outcome,
        "approved": outcome == "approved",
        "diagnosis": diagnosis if outcome == "rejected" else None,
        "category": category,
        "candidate": candidate,
        "candidatePath": candidate_path,
        "promptHash": hashlib.sha256(str(prompt).encode()).hexdigest(),
        "promptText": str(prompt),
        "parsed": parsed,
        "archetype": archetype,
        "conformance": {
            "score": conformance.get("score"),
            "verdict": conformance.get("verdict"),
            "firingFloor": conformance.get("firingFloor"),
            "findings": conformance.get("findings") or [],
        },
        "metadata": metadata or {},
    }
    record["recordId"] = _record_id(record)
    path = pathlib.Path(bank_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def load_records(bank_path: pathlib.Path | str = DEFAULT_BANK_PATH) -> list[dict[str, Any]]:
    path = pathlib.Path(bank_path)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def report(bank_path: pathlib.Path | str = DEFAULT_BANK_PATH) -> dict[str, Any]:
    records = load_records(bank_path)
    section_orders = collections.Counter(
        " > ".join(record.get("parsed", {}).get("sectionOrder") or ["(none)"])
        for record in records)
    lengths = [int(record.get("parsed", {}).get("charCount") or 0) for record in records]
    buckets = collections.Counter()
    for length in lengths:
        lower = (length // 500) * 500
        buckets[f"{lower}-{lower + 499}"] += 1
    by_arch = collections.defaultdict(lambda: {"approved": 0, "rejected": 0, "total": 0})
    for record in records:
        item = by_arch[record.get("archetype") or "unclassified"]
        item["total"] += 1
        item[record.get("outcome") or "rejected"] += 1
    win_rate = {
        key: {**value, "winRate": round(value["approved"] / value["total"], 3)
              if value["total"] else 0.0}
        for key, value in sorted(by_arch.items())
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "bankPath": str(pathlib.Path(bank_path)),
        "records": len(records),
        "sectionOrderFrequency": dict(section_orders.most_common()),
        "charCountDistribution": {
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "average": round(sum(lengths) / len(lengths), 1) if lengths else 0,
            "buckets": dict(sorted(buckets.items())),
        },
        "archetypeWinRate": win_rate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="report", choices=["report"])
    parser.add_argument("--bank-path", default=str(DEFAULT_BANK_PATH))
    args = parser.parse_args(argv)
    print(json.dumps(report(args.bank_path), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
