#!/usr/bin/env python3
"""cb_lineage_diff.py — THE STRUCTURED STORYBOARD LINEAGE DIFF (Julian's bounded lineage
directive, 2026-07-21). A deterministic, order-sensitive, field-level JSON diff between a
previously-approved storyboard snapshot and the live storyboard file, used to decide
whether a lineage mismatch is Technical (pure formatting/administrative), Semantic (real
creative content changed), or Unresolved (equivalence cannot be proven).

Deliberately conservative: ADMINISTRATIVE_ONLY_KEYS names the ONLY top-level field names
this module will ever auto-treat as non-creative on its own — everything else defaults to
requiring explicit classification by the caller (a human, or an LLM review), matching the
directive's own rule: "if the approved snapshot is insufficient to prove equivalence,
classify as Unresolved — do not guess and do not revalidate." This module never guesses a
Semantic change into Technical; it only ever flags the reverse (a genuinely unchanged
administrative field), and even that only for the small, explicitly-named set below.
"""
import json

# Fields the storyboard schema itself treats as pure bookkeeping — never story/creative
# content. Keep this list SHORT and explicit; adding a field here is a real, deliberate
# decision, never a default. A key not in this set is never auto-classified administrative.
ADMINISTRATIVE_ONLY_KEYS = {
    "builtAt", "engineVersion", "canonVersion", "provenance",
}


def diff(a, b, path="$", out=None):
    """Deterministic, order-sensitive structured diff. Returns a list of
    {"path", "changeType", "approved", "current", "note"?} entries — changeType is one of
    added/removed/modified. Array element order is significant by default (per the
    directive: "array ordering must never be dismissed as technical unless the schema
    proves the array is order-insensitive") — a reordered array shows as per-index
    modified/added/removed entries, exactly as if the values themselves had changed."""
    if out is None:
        out = []
    if type(a) is not type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append({"path": path, "changeType": "modified", "approved": a, "current": b,
                    "note": f"type change {type(a).__name__} -> {type(b).__name__}"})
        return out
    if isinstance(a, dict):
        keys_a, keys_b = set(a.keys()), set(b.keys())
        for k in sorted(keys_a - keys_b):
            out.append({"path": f"{path}.{k}", "changeType": "removed", "approved": a[k], "current": None})
        for k in sorted(keys_b - keys_a):
            out.append({"path": f"{path}.{k}", "changeType": "added", "approved": None, "current": b[k]})
        for k in sorted(keys_a & keys_b):
            diff(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append({"path": path, "changeType": "modified", "approved": f"len={len(a)}",
                        "current": f"len={len(b)}", "note": "array length changed"})
        for i in range(min(len(a), len(b))):
            diff(a[i], b[i], f"{path}[{i}]", out)
        for i in range(min(len(a), len(b)), len(a)):
            out.append({"path": f"{path}[{i}]", "changeType": "removed", "approved": a[i], "current": None})
        for i in range(min(len(a), len(b)), len(b)):
            out.append({"path": f"{path}[{i}]", "changeType": "added", "approved": None, "current": b[i]})
    else:
        if a != b:
            out.append({"path": path, "changeType": "modified", "approved": a, "current": b})
    return out


def _top_level_key(path):
    """'$.builtAt' -> 'builtAt'; '$.shots[0].camera' -> 'shots'. Only meaningful for a
    top-level (depth-1) field; classify_diffs only ever auto-clears a diff entry whose
    ENTIRE path lives under one administrative key."""
    rest = path[2:] if path.startswith("$.") else path.lstrip("$")
    for sep in (".", "["):
        if sep in rest:
            rest = rest.split(sep, 1)[0]
            break
    return rest


def classify_diffs(diffs):
    """Splits diff entries into (administrative, unresolved) — never a third
    'auto-approved creative' bucket, since this module never decides that on its own.
    administrative: every entry whose top-level field is in ADMINISTRATIVE_ONLY_KEYS.
    unresolved: everything else — the caller (human or LLM review) must classify these
    explicitly as Technical, Semantic, or Unresolved; this function never guesses."""
    admin, unresolved = [], []
    for e in diffs:
        (admin if _top_level_key(e["path"]) in ADMINISTRATIVE_ONLY_KEYS else unresolved).append(e)
    return admin, unresolved


def overall_classification(diffs, human_verdict=None):
    """The final Technical/Semantic/Unresolved verdict for a diff set.
    - No diffs at all -> "Technical" (byte/structure-identical content; formatting-only
      changes upstream, if any, are already invisible to a structured diff of parsed JSON).
    - Every diff is administrative-only -> "Technical".
    - Any unresolved diff exists -> the caller's own human_verdict decides Semantic vs
      Unresolved; with no human_verdict supplied, defaults to "Unresolved" — never silently
      Technical, per the directive's own explicit rule against guessing."""
    if not diffs:
        return "Technical"
    admin, unresolved = classify_diffs(diffs)
    if not unresolved:
        return "Technical"
    if human_verdict in ("Semantic", "Unresolved"):
        return human_verdict
    return "Unresolved"


if __name__ == "__main__":
    import sys
    a = json.load(open(sys.argv[1]))
    b = json.load(open(sys.argv[2]))
    d = diff(a, b)
    print(json.dumps({"diffs": d, "classification": overall_classification(d)}, indent=1,
                     ensure_ascii=False))
