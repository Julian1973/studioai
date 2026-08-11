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
            headers.append((index, match.group(1).strip(), "bracketed"))
            continue
        stripped = line.strip()
        generic = _generic_marker_name(stripped)
        if generic:
            headers.append((index, generic, "generic"))
    sections = []
    for pos, (start, name, marker_type) in enumerate(headers):
        end = headers[pos + 1][0] if pos + 1 < len(headers) else len(lines)
        if marker_type == "generic":
            body = "\n".join(lines[start:end]).strip()
        else:
            body = "\n".join(lines[start + 1:end]).strip()
        line_text = lines[start].strip()
        section = {
            "name": name,
            "startLine": start + 1,
            "charCount": len(body),
            "wordCount": len(body.split()),
            "empty": not bool(body),
            "markerType": marker_type,
        }
        if name == "Reference":
            section.update(_reference_marker_flags(line_text))
        sections.append(section)
    markers = collections.Counter(item["name"] for item in sections)
    return {
        "charCount": len(text),
        "wordCount": len(text.split()),
        "lineCount": len(lines),
        "sectionOrder": [item["name"] for item in sections],
        "sections": sections,
        "markers": dict(markers),
        "shotCount": len(re.findall(r"(?im)^Shot\s+\d+\s*(?:[-—:]|\.)", text)),
        "endStateCount": len(re.findall(r"(?i)\bEnd state:\s*\S", text)),
        "hasDialogue": bool(re.search(r"\{[^}]+\}", text)),
        "audioPolicy": {
            "noMusic": bool(re.search(r"\bNo music\b", text, re.I)),
            "hasAudioAuthority": bool(re.search(r"AUDIO-(?:AUTHORITY|LOCK)|@Audio1", text, re.I)),
        },
    }


def _generic_marker_name(line: str) -> str | None:
    if not line:
        return None
    if re.match(r"^(?:image_\d+|@(?:Image|图)\s*\d+)\b", line, re.I):
        return "Reference"
    if re.match(r"^ATTRIBUTE OWNERSHIP\s*:", line, re.I):
        return "Attribute Ownership"
    if re.match(r"^Feature-quality stylized 3D CGI\b", line, re.I):
        return "Style"
    if re.match(r"^Dialogue language\s*:", line, re.I):
        return "Dialogue Language"
    if re.match(r"^Shot\s+\d+\s*(?:[-—:]|\.)", line, re.I):
        return "Shot"
    if re.match(r"^End state\s*:", line, re.I):
        return "End State"
    if _is_trailing_negative_line(line):
        return "Negatives"
    return None


def _reference_marker_flags(line: str) -> dict[str, bool]:
    return {
        "hasRole": bool(re.search(
            r"\b(defines?|is the first frame|opening frame|provides?|references?)\b",
            line, re.I)),
        "hasExclusion": bool(re.search(
            r"\b(do not|exclude|ignore|never|only|not use)\b", line, re.I)),
    }


def _is_trailing_negative_line(line: str) -> bool:
    negatives = re.findall(
        r"\bNo (?:music|subtitles?|captions?|on-screen text|watermark|extra characters?|"
        r"narrator|crowd|added speech)\b",
        line,
        re.I,
    )
    return len(negatives) >= 2


def infer_archetype(prompt: str, metadata: dict[str, Any] | None = None) -> str:
    meta = metadata or {}
    explicit = meta.get("archetype") or meta.get("beatArchetype")
    if explicit:
        return str(explicit)
    text = str(prompt or "").lower()
    parsed = parse_prompt_structure(prompt)
    markers = parsed.get("markers") or {}
    if ("moustache" in text or "mustache" in text or
            ("attribute ownership" in markers and "upper lip" in text)):
        return "reveal-and-deadpan-verdict"
    if ("triple twist" in text or "double tuck" in text or "buzz crash" in text or
            ("pops vertically" in text and "eye-roll" in text)):
        return "escalation-into-verdict"
    if ("chase" in text or "pursuit" in text or "near-miss" in text or
            ("three speeds" in text and "maximum load" in text)):
        return "false-triumph-chase"
    if ("storm" in text or "thunder" in text or
            ("turns" in text and "world" in text) or
            ("environment" in text and "both states" in text)):
        return "environment-turn"
    if markers.get("Dialogue Language") and parsed.get("shotCount", 0) >= 2:
        return "dialogue-departure"
    if "vision" in text and "pier" in text:
        return "vision-memory"
    if "crystal-bowl" in text or "crystal bowl" in text or "ritual" in text:
        return "ritual-glow"
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
    raw_records = load_records(bank_path)
    records_by_hash = {}
    duplicate_counts = collections.Counter()
    for record in raw_records:
        prompt_hash = record.get("promptHash") or hashlib.sha256(
            str(record.get("promptText") or "").encode()).hexdigest()
        duplicate_counts[prompt_hash] += 1
        current = {**record}
        current["parsed"] = parse_prompt_structure(current.get("promptText") or "")
        current["archetype"] = infer_archetype(
            current.get("promptText") or "", current.get("metadata") or {})
        current["promptHash"] = prompt_hash
        existing = records_by_hash.get(prompt_hash)
        if not existing or str(current.get("bankedAt") or "") >= str(existing.get("bankedAt") or ""):
            records_by_hash[prompt_hash] = current
    records = list(records_by_hash.values())
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
        "rawRecords": len(raw_records),
        "dedupedBy": "promptHash",
        "duplicatePromptHashes": sum(1 for count in duplicate_counts.values() if count > 1),
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
