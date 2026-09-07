#!/usr/bin/env python3
"""Read-only field-use audit over current typed shot schemas. Zero hits are investigation candidates, not proof of a defect."""
import sys, os, re, glob, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = os.path.join(ROOT, "engine")
# cb_engine owns both schemas and real validation/emission consumers.
WRITE_SIDE = {"cb_llm.py"}


def _load_schemas():
    if ENGINE not in sys.path:
        sys.path.insert(0, ENGINE)
    import cb_engine
    return cb_engine


def schema_fields():
    """Every leaf field name across the models the Director's beat package is built from — deduped, in schema order."""
    S = _load_schemas()
    models = [S.Shot, S.ContinuityState, S.CharacterState]
    seen, out = set(), []
    for model in models:
        for name in model.model_fields:
            if name not in seen:
                seen.add(name); out.append(name)
    return out


def consumer_files():
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(ENGINE, "*.py"))
                  if os.path.basename(p) not in WRITE_SIDE and not os.path.basename(p).startswith("test_"))


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
            print(f"CHECK  {f}  (0 hits across {len(files)} consumer files)")
        elif not leaks_only:
            by_file = sorted({h[0] for h in hits})
            print(f"       {f}  ({len(hits)} hits — {', '.join(by_file)})")
    print()
    print(f"{len(fields)} fields checked, {len(leaks)} zero-hit (mechanical leak candidates).")
    print("A non-zero hit count is NOT proof of a real consumption — inspect the current compiler and request for the actual")
    print("CONSUMED / STRUCTURAL / PARTIAL / LEAK classification this script's raw grep can't make on its own.")


if __name__ == "__main__":
    main()
