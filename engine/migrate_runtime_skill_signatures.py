#!/usr/bin/env python3
"""Re-stamp unchanged saved worker fingerprints. Default mode only reports candidates.

This migration never approves work or clears other freshness checks. Each changed approval
record retains its old fingerprints and records the authorized migration reason and time.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import pathlib
import subprocess

import cb_db
import cb_departments


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "cb-output"
STAGE_SKILLS = {
    "look": ("cinematography",),
    "cinematography": ("cinematography", "dp"),
    "voice": ("voice",),
    "animation": ("animation",),
    "review-keyframe": ("review",),
    "review-animation": ("review",),
    "review-final": ("post",),
}
MIGRATION_REASON = (
    "Authorized signature-scheme migration: replace whole-SKILL.md fingerprints with "
    "the exact current load_runtime_skill output; this does not constitute fresh review "
    "or satisfy other approval freshness checks."
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_skill_sources(repo: pathlib.Path, skill_path: pathlib.Path) -> dict[str, str]:
    relative = skill_path.resolve().relative_to(repo.resolve()).as_posix()
    commits = subprocess.run(
        ["git", "rev-list", "--all", "--", relative], cwd=repo,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    sources = {}
    for commit in commits:
        result = subprocess.run(
            ["git", "show", f"{commit}:{relative}"], cwd=repo,
            check=False, capture_output=True,
        )
        if result.returncode == 0:
            raw = result.stdout
            try:
                sources.setdefault(_sha256(raw), raw.decode("utf-8"))
            except UnicodeDecodeError:
                continue
    return sources


def _approved_records(package):
    for shot in package.get("continuityLedger", []) or []:
        for stage, department in (shot.get("departmentWork") or {}).items():
            approved = (department or {}).get("approved")
            if isinstance(approved, dict):
                yield str(shot.get("shotId") or "?"), stage, approved


def _all_records(paths):
    for path in paths:
        raw = path.read_bytes()
        package = json.loads(raw)
        for shot_id, stage, record in _approved_records(package):
            signature = record.get("inputSignature") or {}
            hashes = signature.get("skillHashes")
            if isinstance(hashes, dict) and hashes:
                yield path, raw, package, shot_id, stage, record, signature, hashes


def build_plan(repo=ROOT, package_dir=PACKAGE_DIR):
    """Find approvals whose recorded whole-file skill is provably contract-identical."""
    paths = sorted(pathlib.Path(package_dir).glob("*_production_package.json"))
    records = list(_all_records(paths))
    source_cache = {}
    plan = {}
    counts = {"approvals": len(records), "eligible": 0, "already_current": 0,
              "runtime_changed": 0, "historical_source_missing": 0,
              "stage_or_skill_mismatch": 0}

    for path, raw, package, shot_id, stage, record, signature, old_hashes in records:
        keys = STAGE_SKILLS.get(signature.get("stage") or stage)
        if not keys or set(old_hashes) != set(keys):
            counts["stage_or_skill_mismatch"] += 1
            continue
        status, current_hashes = "eligible", {}
        for key in keys:
            skill_path = cb_departments.SKILLS.get(key)
            if skill_path is None:
                status = "stage_or_skill_mismatch"
                break
            cache_key = str(skill_path.resolve())
            if cache_key not in source_cache:
                source_cache[cache_key] = _git_skill_sources(pathlib.Path(repo), skill_path)
            current_hashes[key] = cb_departments.runtime_skill_sha256(key)
            old_hash = str(old_hashes.get(key) or "")
            if old_hash == current_hashes[key]:
                continue
            historical = source_cache[cache_key].get(old_hash)
            if historical is None:
                status = "historical_source_missing"
                break
            if (cb_departments.runtime_skill_contract_text(key, historical) !=
                    cb_departments.runtime_skill_contract_text(key)):
                status = "runtime_changed"
                break
        if status == "eligible" and all(
            str(old_hashes.get(key)) == current_hashes[key] for key in keys
        ):
            status = "already_current"
        counts[status] += 1
        if status != "eligible":
            continue
        item = plan.setdefault(str(path.resolve()), {
            "path": path, "raw": raw, "package": package, "edits": [], "outputs": []})
        item["edits"].append((shot_id, stage, record, current_hashes))
        item["outputs"].append(copy.deepcopy(record.get("output")))
    return plan, counts


def restamp_record(record, hashes, migrated_at=None):
    previous = copy.deepcopy(record["inputSignature"].get("skillHashes") or {})
    record["inputSignature"]["skillHashes"] = dict(hashes)
    record["signatureMigration"] = {
        "migratedAt": migrated_at or datetime.datetime.now(
            datetime.timezone.utc).isoformat(),
        "reason": MIGRATION_REASON,
        "previousSkillHashes": previous,
    }


def apply_plan(plan):
    count = 0
    for item in plan.values():
        for _shot, _stage, record, hashes in item["edits"]:
            restamp_record(record, hashes)
        outputs = [copy.deepcopy(record.get("output"))
                   for _shot, _stage, record, _hashes in item["edits"]]
        if outputs != item["outputs"]:
            raise RuntimeError("migration attempted to change approved output")
        cb_db.atomic_write_json(
            ROOT, item["path"], item["package"], expected_digest=_sha256(item["raw"]))
        count += len(item["edits"])
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write verified fingerprints and migration audit metadata")
    args = parser.parse_args(argv)
    plan, counts = build_plan()
    print(json.dumps({"mode": "apply" if args.apply else "dry-run", **counts,
                      "candidate_records": sum(len(x["edits"]) for x in plan.values()),
                      "candidate_packages": len(plan),
                      "approval_decisions_changed": False,
                      "other_freshness_gates_cleared": False}, indent=2))
    if args.apply:
        print(json.dumps({"restamped": apply_plan(plan)}, indent=2))
    else:
        for item in plan.values():
            for shot_id, stage, _record, _hashes in item["edits"]:
                print(f"would re-stamp {item['path'].name} {shot_id} {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
