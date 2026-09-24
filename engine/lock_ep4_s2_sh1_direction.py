"""Lock the approved S2.SH1 Director authority after a completed handoff."""
from __future__ import annotations

import datetime
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cb_render as R


pkg, path = R.load_pkg("2", "Ep4")
shot = R._shot(pkg, "S2.SH1")
ledger = R._ledger(pkg, "S2.SH1")
handoff = ledger.get("directorCardHandoff") or {}
direction_hash = handoff.get("directionHash")
if not direction_hash:
    raise RuntimeError("S2.SH1 has no completed Director handoff to lock")
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
lock = {
    "locked": True,
    "lockedBy": "Julian",
    "lockedAt": now,
    "revisionId": ledger.get("directionRevision"),
    "directionHash": direction_hash,
    "sourceHash": handoff.get("sourceHash"),
    "scope": "S2.SH1 Director authority through WATCH compilation",
    "preserved": ["scene plate", "opening keyframe", "Audio1"],
    "requiredSequence": [
        "raindrop hits pond",
        "vision appears inside ripple",
        "Aida recognises vision",
        "hand to heart",
        "exact Audio1 line",
        "rise and walk off",
        "vision fades in final ripple",
    ],
}
ledger["directionLock"] = lock
ledger["directionRevisionNote"] = (
    "LOCKED: pond-ripple vision, hand-to-heart, exact Audio1 line, rise and walk-off. "
    "Scene plate, opening keyframe and Audio1 preserved."
)
shot["directorDirectionLocked"] = True
shot["directorDirectionLock"] = lock
R._save(pkg, path)
print({"locked": True, "revisionId": lock["revisionId"], "directionHash": direction_hash})
