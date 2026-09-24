"""Retire an unconfirmed local WATCH attempt without hiding provider evidence."""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cb_render as R

pkg, path = R.load_pkg("2", "Ep4")
ledger = R._ledger(pkg, "S2.SH1")
batch = ledger.get("batch") or {}
if batch.get("status") != "generating":
    raise RuntimeError(f"S2.SH1 has no generating batch to retire (status={batch.get('status')!r})")
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
retirement = {
    "retired": True,
    "retiredBy": "Julian",
    "retiredAt": now,
    "reason": "User retired the unconfirmed WATCH submission before refire.",
    "providerOutcome": "unconfirmed",
    "providerEvidence": [str(p) for p in (ROOT / "engine/media/shots").glob(
        "Ep4_S2.SH1_c1.mp4.*provider-task.json")],
    "newProviderSubmissionAllowed": False,
}
batch["status"] = "retired-unreconciled"
batch["retirement"] = retirement
ledger["batch"] = batch
ledger["retiredSubmission"] = retirement
ledger["submissionUnresolved"] = True
R._save(pkg, path)
print(json.dumps({"retired": True, "providerOutcome": "unconfirmed", "newProviderSubmissionAllowed": False}, indent=2))
