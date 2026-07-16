#!/usr/bin/env python3
"""test_cb_prompts.py — regression coverage for cb_prompts.build_keyframe_prompt's
keyframePromptOverride confirmation gate (2026-07-14, CLAUDE.md rules 82/83's named-auteur-
per-chair doctrine — Julian: "keep them for genuine edge cases, but require an explicit
confirmation... flag it visibly so it's never silent").

Before this fix, ANY non-empty keyframePromptOverride shipped VERBATIM the instant it was
present, silently bypassing Eggleston/Lin/Kalache's own compiled composition/style text with
no record a bypass happened. Now it's ignored (falls through to the real compiled DP prompt)
unless the SAME beat also carries keyframePromptOverrideConfirmed: true.

Convention matches test_cb_voice.py / test_cb_qa.py / test_gate_cascade.py: plain Python,
assert-style checks recorded via check(), no pytest/unittest, a main() that prints PASS/FAIL
per case and sys.exit(1) on any failure.

Uses a DEEP COPY of the real production 1.B1 beat + Scene 1 data (never mutates the real
package — cb_pipeline._resolve_pkg()'s own file is only ever read) so build_keyframe_prompt's
real reference-resolution logic (opening_cast/char_identity_refs/master_ref, all reading real
characters.json data) runs unmodified, exactly as it does in production.

    python3 test_cb_prompts.py
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cb_pipeline
import cb_prompts

RESULTS = []  # (name, ok, detail)


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))


def _load_real_1b1_and_scene1():
    """Deep copies only — the real package on disk is read, never written."""
    pkg_path = cb_pipeline._resolve_pkg()
    d = json.load(open(pkg_path))
    beats = d.get("beats") or d.get("shots") or []
    b1 = next(b for b in beats if (b.get("beatCode") or b.get("shotCode")) == "1.B1")
    scenes = d.get("scenes") or []
    sc1 = next(s for s in scenes if s.get("sceneNumber") == 1)
    return copy.deepcopy(b1), copy.deepcopy(sc1)


# ═══════════════════════════════════════════════════════════════════════════════════
# keyframePromptOverride GATED BEHIND EXPLICIT CONFIRMATION
# ═══════════════════════════════════════════════════════════════════════════════════
def test_keyframe_prompt_override_gated_behind_confirmation():
    b1_base, sc1 = _load_real_1b1_and_scene1()

    # Case 3 first (no override at all) — establishes the REAL compiled baseline every
    # other case is compared against.
    b1_absent = copy.deepcopy(b1_base)
    b1_absent.pop("keyframePromptOverride", None)
    b1_absent.pop("keyframePromptOverrideConfirmed", None)
    prompt_absent, refs_absent = cb_prompts.build_keyframe_prompt(b1_absent, sc1)
    check("build_keyframe_prompt: no override at all compiles the real DP prompt (non-trivial length)",
          isinstance(prompt_absent, str) and len(prompt_absent) > 200, len(prompt_absent))

    OVERRIDE_TEXT = "A hand-typed emergency override prompt that must never ship unconfirmed."

    # Case 1 — override present but UNCONFIRMED: must be ignored, falling through to the
    # real compiled DP prompt (matching Case 3's output exactly).
    b1_unconfirmed = copy.deepcopy(b1_base)
    b1_unconfirmed["keyframePromptOverride"] = OVERRIDE_TEXT
    b1_unconfirmed.pop("keyframePromptOverrideConfirmed", None)
    prompt_unconfirmed, refs_unconfirmed = cb_prompts.build_keyframe_prompt(b1_unconfirmed, sc1)
    check("build_keyframe_prompt: an UNCONFIRMED override never appears in the compiled prompt",
          OVERRIDE_TEXT not in prompt_unconfirmed, prompt_unconfirmed[:120])
    check("build_keyframe_prompt: an UNCONFIRMED override compiles IDENTICALLY to no override at all",
          prompt_unconfirmed == prompt_absent and refs_unconfirmed == refs_absent,
          (len(prompt_unconfirmed), len(prompt_absent)))
    check("build_keyframe_prompt: an UNCONFIRMED override still carries real Eggleston/Lin/Kalache "
          "composition text (the real compiler actually ran, not a stub)",
          "COMPOSITION" in prompt_unconfirmed.upper() or "STYLE" in prompt_unconfirmed.upper(),
          prompt_unconfirmed[:300])

    # Case 2 — override present AND confirmed: ships VERBATIM.
    b1_confirmed = copy.deepcopy(b1_base)
    b1_confirmed["keyframePromptOverride"] = OVERRIDE_TEXT
    b1_confirmed["keyframePromptOverrideConfirmed"] = True
    prompt_confirmed, refs_confirmed = cb_prompts.build_keyframe_prompt(b1_confirmed, sc1)
    check("build_keyframe_prompt: a CONFIRMED override ships VERBATIM, byte for byte",
          prompt_confirmed == OVERRIDE_TEXT, prompt_confirmed)
    check("build_keyframe_prompt: a CONFIRMED override still returns the real resolved reference list "
          "('refs still attach' — the override only replaces the TEXT, never the image references)",
          isinstance(refs_confirmed, list) and len(refs_confirmed) > 0, refs_confirmed)


def main():
    test_keyframe_prompt_override_gated_behind_confirmation()

    fails = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        -> {detail}" if not ok and detail else ""))
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} passed.")
    if fails:
        print(f"{len(fails)} FAILURE(S)")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
