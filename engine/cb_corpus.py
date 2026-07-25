#!/usr/bin/env python3
"""cb_corpus.py — THE VERDICT CORPUS (Julian's directive, 2026-07-25).

The most valuable data this studio produces is Julian's own verdict on a real render, and
until this module existed it was thrown away every session. Prompts were compiled, clips
were fired, he said "not great" or "it's perfect" in chat, and the pairing evaporated. The
SH1 keeper formula was found from eleven such pairings held in one session's head; nothing
survived to make the twelfth cheaper.

This is an append-only ledger of (what we fired, what came back, what he said). Two record
kinds, never mutated:

    fire    — one per real generation: the exact prompt, its hash, the reference stack and
              their hashes, the audio hash, provider/model/resolution, the formula that was
              in the writer's mind, cost, and the provider's own task ids.
    verdict — one per human decision, referencing a fire by id: kept or rejected, and his
              words. A rejection is as valuable as an approval — more, usually.

Why append-only: a corpus you can edit is a corpus you can flatter. Rewriting history to
match a later theory is exactly how eleven honest fires would have become one tidy lie.

What this is FOR, concretely: when a dramatic form has no proven formula, `for_form()`
returns every fire ever made on that kind of material with its verdict attached. That is
the evidence a new formula is derived from — the same way SH1's was, but written down.
"""
import datetime
import hashlib
import json
import pathlib

import os

HERE = pathlib.Path(__file__).resolve().parent
_DEFAULT_DIR = HERE.parent / "shows" / "crystal-bears" / "creative" / "corpus"


def _dir():
    """Resolved at CALL time, never import time. CB_CORPUS_DIR redirects the whole corpus
    — used by engine/conftest.py to point the entire test session at a scratch directory.

    This exists because of a real incident, caught the hour this module was written: the
    standing suite fires through the REAL fire_shot with mocked providers, so wiring the
    corpus into that path immediately wrote 90 synthetic records into the production
    corpus. A corpus polluted by test fixtures is worse than no corpus — it would teach
    the next formula from data that never rendered. Same bug class as this project's
    earlier cost-ledger pollution."""
    return pathlib.Path(os.environ.get("CB_CORPUS_DIR") or _DEFAULT_DIR)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def sha(text_or_bytes):
    """Short content hash. A prompt's identity, so two fires can be compared exactly."""
    if text_or_bytes is None:
        return None
    b = (text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str)
         else bytes(text_or_bytes))
    return hashlib.sha256(b).hexdigest()[:16]


def file_sha(path):
    """Hash a reference/audio file by content — a path proves nothing, bytes do."""
    try:
        p = pathlib.Path(path)
        if not p.is_file():
            return None
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return None                      # never let evidence-keeping break a real fire


def _append(record):
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    with (d / "fires.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def record_fire(*, episode, scene, shot_id, prompt, refs=None, audio_path=None,
                provider=None, model=None, resolution=None, candidates=None,
                task_ids=None, expected_cost=None, actual_cost=None, clips=None,
                formula=None, variant_label=None, notes=None):
    """One real generation, recorded whole. Returns the fireId.

    Never raises: a failure to record evidence must not fail the fire it is recording —
    but it prints, so a silent gap in the corpus can't accumulate unnoticed."""
    try:
        fid = f"{shot_id}-{sha(prompt or '')}-{_now().replace(':', '')}"
        rec = {
            "kind": "fire", "fireId": fid, "at": _now(),
            "episode": episode, "scene": scene, "shotId": shot_id,
            "variantLabel": variant_label,
            "formula": formula or {},
            "promptSha": sha(prompt), "promptWords": len((prompt or "").split()),
            "prompt": prompt,
            "refs": [{"role": r.get("role"), "path": r.get("path"),
                      "sha": file_sha(r.get("path"))} for r in (refs or [])],
            "audioSha": file_sha(audio_path), "audioPath": audio_path,
            "provider": provider, "model": model, "resolution": resolution,
            "candidates": candidates, "providerTaskIds": list(task_ids or []),
            "expectedCost": expected_cost, "actualCost": actual_cost,
            "clips": list(clips or []), "notes": notes,
        }
        _append(rec)
        return fid
    except Exception as e:                                      # pragma: no cover
        print(f"[corpus] WARNING — fire not recorded for {shot_id}: {e}")
        return None


def record_verdict(*, shot_id, verdict, kept, fire_id=None, reviewed_by="Julian",
                   category=None, episode=None, scene=None):
    """Julian's own words on a real render. `kept` is the decision; `verdict` is why.

    fire_id may be omitted — the most recent unjudged fire for this shot is used, which is
    what actually happens in practice (fire, watch, decide). Recorded either way."""
    try:
        fid = fire_id or latest_fire_id(shot_id)
        rec = {"kind": "verdict", "at": _now(), "fireId": fid, "shotId": shot_id,
               "episode": episode, "scene": scene, "kept": bool(kept),
               "verdict": verdict, "category": category, "reviewedBy": reviewed_by}
        _append(rec)
        return rec
    except Exception as e:                                      # pragma: no cover
        print(f"[corpus] WARNING — verdict not recorded for {shot_id}: {e}")
        return None


def read_all():
    f = _dir() / "fires.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue                     # one corrupt line never hides the rest
    return out


def latest_fire_id(shot_id):
    fires = [r for r in read_all() if r.get("kind") == "fire" and r.get("shotId") == shot_id]
    return fires[-1]["fireId"] if fires else None


def judged():
    """Every fire with its verdict attached, oldest first — the actual training set."""
    recs = read_all()
    verdicts = {}
    for r in recs:
        if r.get("kind") == "verdict" and r.get("fireId"):
            verdicts[r["fireId"]] = r          # last verdict on a fire wins (a re-review)
    return [{**f, "verdict": verdicts.get(f["fireId"])}
            for f in recs if f.get("kind") == "fire"]


def for_form(form_key):
    """Every fire ever made on this dramatic form, with verdicts. This is the evidence a
    new formula is derived from — call it before authoring a discovery fire."""
    return [f for f in judged() if (f.get("formula") or {}).get("formKey") == form_key]


def summary():
    js = judged()
    kept = [f for f in js if (f.get("verdict") or {}).get("kept")]
    rejected = [f for f in js if f.get("verdict") and not f["verdict"]["kept"]]
    unjudged = [f for f in js if not f.get("verdict")]
    by_form = {}
    for f in js:
        k = (f.get("formula") or {}).get("formKey") or "(unresolved)"
        b = by_form.setdefault(k, {"fires": 0, "kept": 0})
        b["fires"] += 1
        b["kept"] += 1 if (f.get("verdict") or {}).get("kept") else 0
    lines = [f"VERDICT CORPUS — {len(js)} fire(s): {len(kept)} kept, "
             f"{len(rejected)} rejected, {len(unjudged)} awaiting a verdict"]
    for k, b in sorted(by_form.items()):
        lines.append(f"  {k:<22} {b['fires']:>3} fired, {b['kept']:>3} kept")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
