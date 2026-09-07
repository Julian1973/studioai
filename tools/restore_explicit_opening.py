#!/usr/bin/env python3
"""Record an explicit human approval for an orphaned legacy opening take."""
import argparse
import hashlib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "engine"))

import cb_gen
import cb_render


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("shot")
    ap.add_argument("take")
    ap.add_argument("episode")
    args = ap.parse_args()

    take = pathlib.Path(args.take).resolve()
    if not take.is_file() or take.suffix.lower() != ".mp4":
        raise SystemExit("take must be an existing MP4")
    pkg, package_path = cb_render.load_pkg(args.scene, args.episode)
    ledger = cb_render._ledger(pkg, args.shot)
    if ledger.get("status") == "approved" and ledger.get("approvedTake"):
        raise SystemExit(f"{args.shot} already has an approved take")

    harvest = HERE / "engine" / "media" / f"{args.episode}_{args.shot}_final_frame.png"
    cb_gen.last_frame(str(take), out=str(harvest))
    content_hash = sha256(take)
    harvest_hash = sha256(harvest)
    old_batch = ledger.get("batchId")
    ledger.setdefault("approvalRecoveryHistory", []).append({
        "source": "explicit-human-approval-of-orphaned-candidate",
        "at": cb_render._now(),
        "candidate": 2,
        "take": str(take),
        "takeHash": content_hash,
        "oldBatchId": old_batch,
        "note": "Julian explicitly approved the opening-shot candidate for post recovery.",
    })
    ledger.update({
        "status": "approved",
        "approvedTake": str(take),
        "approvedCandidate": 2,
        "harvestFrame": str(harvest),
        "approval": {
            "approved": True,
            "candidate": 2,
            "reviewed_by": "Julian",
            "at": cb_render._now(),
            "source": "explicit-human-approval-of-orphaned-candidate",
            "contentHash": content_hash,
            "harvestHash": harvest_hash,
            "batchId": old_batch,
            "packageRevision": pkg.get("revision"),
        },
        "candidatePaths": [],
        "disclosure": None,
        "firedAt": ledger.get("firedAt") or cb_render._now(),
    })
    cb_render._save(pkg, package_path)
    print(f"APPROVED — {args.shot} candidate 2 restored for post; final frame {harvest.name}")


if __name__ == "__main__":
    main()
