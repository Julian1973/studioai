#!/usr/bin/env python3
"""Regression coverage for cb_director_pass.direct_beat's read_only contract (2026-07-15).

THE BUG: a UI preview click (the Studio's beat-prompt/voice-prompt cards) shares direct_beat with the real
render path. Before this fix, ANY caller — read-only preview included — paid for a live, real, ~40-60s LLM
call the instant a beat's cuts[] text changed and its cache went stale, which then blew past serve.py's 40s
subprocess timeout and surfaced to the user as "nothing loads," silently spending real API cost along the way.

THE FIX: read_only=True never calls the LLM — it returns whatever is cached (fresh OR stale), or None if no
cache exists at all. read_only=False (the real render path, unchanged) still regenerates on a stale/missing
cache exactly as before.

Run: python3 test_cb_director_pass.py   (no real API calls — cb_llm.structured is never reached when it
matters, and every case is proven via a tripwire that fails loudly if it ever is)
"""
import os, json, shutil, tempfile

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"PASS  {name}")
    else:
        FAIL += 1; print(f"FAIL  {name}  {detail}")

import cb_director_pass as CDP

_BEAT = {"beatCode": "9.B9", "cuts": [{"action": "a bee flies."}]}
_SC = {"name": "Scratch Scene"}
_ARGS = (_BEAT, _SC, "COMEDY_PHYSICAL", "LEAF_CRASH_REBOUND", "some rule text", ["Fuzzby"], 15, "a test", [], "EpTest")


def _scratch_cache_dir():
    d = tempfile.mkdtemp(prefix="cb_director_pass_test_")
    CDP._CACHE_DIR = d
    return d


def _tripwire_llm():
    """A cb_llm.structured stand-in that FAILS the test outright if ever called — proves read_only really
    never reaches the LLM, rather than merely returning early enough that a slow real call happens to still
    look like a pass."""
    def _boom(*a, **kw):
        raise AssertionError("cb_llm.structured was called — read_only must NEVER reach the LLM")
    return _boom


print("=== read_only=True, NO cache at all: fails open (None), never calls the LLM ===")
d = _scratch_cache_dir()
try:
    import cb_llm
    orig = cb_llm.structured
    cb_llm.structured = _tripwire_llm()
    try:
        r = CDP.direct_beat(*_ARGS, read_only=True)
        check("returns None (fail-open shape)", r is None)
    finally:
        cb_llm.structured = orig
finally:
    shutil.rmtree(d, ignore_errors=True)


print("=== read_only=True, a FRESH cache exists (fingerprint matches): returns it, never calls the LLM ===")
d = _scratch_cache_dir()
try:
    fp = CDP._fingerprint(_BEAT, "COMEDY_PHYSICAL", "LEAF_CRASH_REBOUND", ["Fuzzby"], [], "some rule text")
    cp = CDP._cache_path("EpTest", "9.B9")
    json.dump({"_fingerprint": fp, "_version": CDP.DIRECTOR_PASS_VERSION,
               "result": {"expression": "fresh-cached-expression", "voice_direction": []}}, open(cp, "w"))
    import cb_llm
    orig = cb_llm.structured
    cb_llm.structured = _tripwire_llm()
    try:
        r = CDP.direct_beat(*_ARGS, read_only=True)
        check("returns the cached result", isinstance(r, dict) and r.get("expression") == "fresh-cached-expression", r)
    finally:
        cb_llm.structured = orig
finally:
    shutil.rmtree(d, ignore_errors=True)


print("=== read_only=True, a STALE cache exists (fingerprint mismatch — the exact real-world bug case): "
      "returns the stale cache as-is, never regenerates, never calls the LLM ===")
d = _scratch_cache_dir()
try:
    cp = CDP._cache_path("EpTest", "9.B9")
    json.dump({"_fingerprint": "this-will-never-match-anything", "_version": CDP.DIRECTOR_PASS_VERSION,
               "result": {"expression": "stale-cached-expression", "voice_direction": ["stale line"]}}, open(cp, "w"))
    import cb_llm
    orig = cb_llm.structured
    cb_llm.structured = _tripwire_llm()
    try:
        r = CDP.direct_beat(*_ARGS, read_only=True)
        check("returns the STALE cached result (not None, not regenerated)",
              isinstance(r, dict) and r.get("expression") == "stale-cached-expression", r)
        check("voice_direction survives from the stale cache too",
              r.get("voice_direction") == ["stale line"], r)
    finally:
        cb_llm.structured = orig
finally:
    shutil.rmtree(d, ignore_errors=True)


print("=== read_only=False (the default — the real render path), a STALE cache: DOES call the LLM (unchanged "
      "behaviour — a real render must always get fresh direction on real content changes) ===")
d = _scratch_cache_dir()
try:
    cp = CDP._cache_path("EpTest", "9.B9")
    json.dump({"_fingerprint": "this-will-never-match-anything", "_version": CDP.DIRECTOR_PASS_VERSION,
               "result": {"expression": "stale-cached-expression"}}, open(cp, "w"))
    import cb_llm
    orig = cb_llm.structured
    called = []
    def _mock(system, user, schema, label=None):
        called.append(label)
        class _R:
            def model_dump(self):
                return {"expression": "freshly-regenerated", "voice_direction": []}
        return _R()
    cb_llm.structured = _mock
    try:
        r = CDP.direct_beat(*_ARGS, read_only=False)
        check("DID call the LLM (the real-render contract, unchanged)", len(called) == 1, called)
        check("returns the freshly-regenerated result, not the stale one",
              isinstance(r, dict) and r.get("expression") == "freshly-regenerated", r)
    finally:
        cb_llm.structured = orig
finally:
    shutil.rmtree(d, ignore_errors=True)


print(f"\n{PASS}/{PASS+FAIL} passed.")
if FAIL:
    raise SystemExit(f"{FAIL} FAILURE(S)")
print("ALL PASS")
