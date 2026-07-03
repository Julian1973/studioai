#!/usr/bin/env python3
"""tools/field_audit.py — T33, the field-to-frame leak hunter.

Every field the Director writes into a beat (cb_director_schemas.py's Beat/Cut/Performance/BeatContinuity/BeatCheck
Pydantic models — read live via Pydantic introspection, so this never drifts from the schema) gets grepped across
every CONSUMER file in engine/ (everything except the write side: cb_director.py, cb_director_schemas.py,
cb_writer.py, cb_llm.py). A field with ZERO hits outside the write side is a confirmed LEAK — the same bug class as
the startState/shotSize find (2026-07-02): rich content the Director writes that nothing downstream ever reads.

This is the MECHANICAL first pass only: a zero-hit field is unambiguously a leak, but a field WITH hits still needs a
human/LLM judgment call on whether those hits actually shape a generated artifact (keyframe/Seedance/voice/QA) or are
merely bookkeeping — see FIELD_TO_FRAME_AUDIT.md for that full classification. Re-run this after adding any field to
the schema, or when hunting a newly-found leak pattern across every module (CLAUDE.md hard rule 11).

    python3 tools/field_audit.py            # print every field + hit count, LEAK-flagged
    python3 tools/field_audit.py --leaks    # print ONLY the zero-hit fields
"""
import sys, os, re, glob, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
WRITE_SIDE = {"cb_director.py", "cb_director_schemas.py", "cb_writer.py", "cb_llm.py"}


def _load_schemas():
    spec = importlib.util.spec_from_file_location("cb_director_schemas", os.path.join(ENGINE, "cb_director_schemas.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def schema_fields():
    """Every leaf field name across the models the Director's beat package is built from — deduped, in schema order."""
    S = _load_schemas()
    models = [S.Beat, S.Cut, S.Performance, S.BeatContinuity, S.BeatCheck]
    seen, out = set(), []
    for model in models:
        for name in model.model_fields:
            if name not in seen:
                seen.add(name); out.append(name)
    return out


def consumer_files():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ENGINE, "*.py"))
                  if os.path.basename(p) not in WRITE_SIDE)


def hits_for(field, files):
    """Every (file, line_no, line_text) where `field` appears as a quoted dict key or bare attribute — a
    conservative pattern (it can miss an exotic access form) but a real hit here is never a false LEAK verdict."""
    pat = re.compile(r'["\']' + re.escape(field) + r'["\']|\.' + re.escape(field) + r'\b')
    out = []
    for fn in files:
        path = os.path.join(ENGINE, fn)
        try:
            lines = open(path, encoding="utf-8").readlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if pat.search(line):
                out.append((fn, i, line.strip()))
    return out


def main():
    leaks_only = "--leaks" in sys.argv
    fields = schema_fields()
    files = consumer_files()
    leaks = []
    for f in fields:
        hits = hits_for(f, files)
        if not hits:
            leaks.append(f)
            print(f"LEAK   {f}  (0 hits across {len(files)} consumer files)")
        elif not leaks_only:
            by_file = sorted({h[0] for h in hits})
            print(f"       {f}  ({len(hits)} hits — {', '.join(by_file)})")
    print()
    print(f"{len(fields)} fields checked, {len(leaks)} zero-hit (mechanical leak candidates).")
    print("A non-zero hit count is NOT proof of a real consumption — see FIELD_TO_FRAME_AUDIT.md for the judged")
    print("CONSUMED / STRUCTURAL / PARTIAL / LEAK classification this script's raw grep can't make on its own.")


if __name__ == "__main__":
    main()
