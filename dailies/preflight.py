#!/usr/bin/env python3
"""The pre-flight brain — mechanical checks BEFORE any spend.

Runs against the engine's own dryrun output (cb_beats.py dryrun), so it checks the
ACTUAL prompt/audio plan that would fire, not a guess. Every check is mechanical
(regex/arithmetic, never an LLM opinion) and names the law it enforces. BLOCK stops
the fire; NOTE is advisory. A checklist cannot forget — that is the whole point.
"""
import json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"


def _paths():
    """engine/paths — the project profile is the only path authority (T44)."""
    if str(ENGINE) not in sys.path:
        sys.path.insert(0, str(ENGINE))
    import paths
    return paths
PLAYBOOK = pathlib.Path(__file__).resolve().parent / "playbook.json"

# Appearance vocabulary that must NEVER sit near a character (identity law: canon
# CLAUDE.md rule 5 / Bible Law 2 — identity comes only from reference images).
# True IDENTITY descriptors only. Deliberately excluded: wings/antennae (motion anatomy
# — the WING LAW directs their pose), size words (role labels like 'the larger bee' are
# the engine's sanctioned name-avoidance), generic shape words. Word-bounded.
APPEARANCE = r"\b(fur|furry|plush|striped?s?|yellow|golden|black|pink|rose(?:-gold)?|teal|lavender|violet|pearlescent|blue-grey|spectacles|glasses|bulbous|translucent|fuzzy|plump)\b"
NAMES = r"(Fuzzby|Zenny|Aida|Sunny|Luna|Misty|Amie|Howey|Keen|Squeaky|Bo)"
BEES = ("Fuzzby", "Zenny")


def dryrun(pkg: str, beat: str, ep: str = "Ep1") -> dict:
    """Ask the engine to build the beat with NO render — in-process, so we get the
    FULL plan including the prompt (the CLI deliberately withholds it). Uses the
    engine's own gate3_dryrun: 'THE SAME shipped_prompt() call as run() — preview ==
    fire, provably.'"""
    cwd = os.getcwd()
    try:
        os.chdir(ENGINE)
        if str(ENGINE) not in sys.path:
            sys.path.insert(0, str(ENGINE))
        import cb_beats  # noqa: deferred import — needs engine cwd
        return cb_beats.gate3_dryrun(pkg, beat, ep)
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}
    finally:
        os.chdir(cwd)


def _beat_from_package(pkg_path: str, beat: str) -> dict:
    try:
        p = pathlib.Path(pkg_path)
        if not p.is_absolute():
            p = (ENGINE / pkg_path).resolve()
        data = json.loads(p.read_text())
    except Exception:
        return {}
    for b in (data.get("beats") or data.get("shots") or []):
        if (b.get("beatCode") or b.get("shotCode")) == beat:
            return b
    return {}


def checks(plan: dict, beat_meta: dict, playbook: dict) -> list:
    """Return [(severity, check_id, message, source_law)]."""
    findings = []
    prompt = str(plan.get("prompt") or plan.get("_raw") or "")
    dur = float(beat_meta.get("durationSec") or plan.get("durationSec") or 0)
    dialogue_words = 0
    for cut in beat_meta.get("cuts", []) or []:
        dialogue_words += len(str(cut.get("dialogue") or "").split())
    has_dialogue = dialogue_words > 0 or bool(beat_meta.get("speakers"))

    def add(sev, cid, msg, law):
        findings.append((sev, cid, msg, law))

    if plan.get("_error"):
        add("BLOCK", "dryrun-failed", f"engine dryrun failed: {plan['_error'][:300]}", "fire nothing you cannot preview")
        return findings

    # 1. Identity law — appearance words near a character name/label
    for m in re.finditer(NAMES + r"[^.\n]{0,60}" + APPEARANCE, prompt, re.I):
        add("BLOCK", "identity-text", f"appearance word near a character: '…{m.group(0)[:70]}…'",
            "CLAUDE.md r5 / Bible Law 2: identity from reference images ONLY")
    # 2. Spoken words leaked into prompt text (must be 'the line in @Audio1')
    if re.search(r'[""][A-Za-z][^""]{3,}[""]', prompt) and "@Audio" in prompt:
        add("BLOCK", "spoken-words", "quoted dialogue text found in prompt — must be 'the line in @Audio1'",
            "Law 5 + segprompt _strip_spoken_words doctrine")
    # 3. Law 5 — dialogue beat must carry @Audio1
    if has_dialogue and "@Audio" not in prompt:
        add("BLOCK", "law5-no-track", "beat has dialogue but no @Audio reference in the plan",
            "Law 5: the voice lives in the render; no native-voice fallback")
    # 4. References attached
    if not re.search(r"@图|@Image|reference image", prompt, re.I):
        add("BLOCK", "no-references", "no reference-image bindings found in prompt",
            "References are law; text does the motion")
    # 5. Duration clamp (route-aware)
    rule = playbook.get("beat_duration_rule", {"min_s": 8, "max_s": 15})
    if dur and not (rule["min_s"] <= dur <= rule["max_s"]):
        add("BLOCK", "duration", f"durationSec {dur} outside {rule['min_s']}–{rule['max_s']} (route rule)",
            "beat clamp / route-2.5 test plan")
    # 6. Dialogue pacing (~2 words/sec against action budget)
    if dur and dialogue_words and dialogue_words > (dur * 2.4):
        add("BLOCK", "dialogue-overstuffed", f"{dialogue_words} words in {dur}s (> ~2w/s + slack) — SPLIT the beat",
            "pacing law: split to pace, never trim")
    # 7. Bees with crystals
    for bee in BEES:
        if re.search(bee + r"[^.\n]{0,140}crystal", prompt, re.I):
            add("BLOCK", "bee-crystal", f"{bee} appears near 'crystal' — bees have NO crystal", "locked canon §3/§5")
    # 8. Negatives / constraints present
    if not re.search(r"NEGATIVE|Do not|constraints", prompt, re.I):
        add("NOTE", "no-negatives", "no negatives/constraints section detected", "segprompt v3 shape")
    # 9. Banned vocabulary (corrected-away ghosts)
    banned_file = pathlib.Path(_paths().BANNED_VOCABULARY) if _paths().BANNED_VOCABULARY else None
    if banned_file and banned_file.exists():
        try:
            for term in json.loads(banned_file.read_text()):
                t = term if isinstance(term, str) else term.get("term", "")
                if t and re.search(re.escape(t), prompt, re.I):
                    add("BLOCK", "banned-vocab", f"banned term in prompt: '{t}'", "check_scene_vocabulary — a hit is a hard BLOCK")
        except Exception:
            add("NOTE", "banned-vocab-unreadable", "banned_vocabulary.json unreadable — check manually", "canon sync")
    # 10. Proven-path adherence
    proven = playbook.get("proven_paths") or {}
    if proven:
        add("NOTE", "playbook", f"{len(proven)} proven path(s) on file — confirm this shot uses its archetype's recipe verbatim",
        "dailies law 3: a proven path is law")
    return findings


def run(pkg: str, beat: str, ep: str = "Ep1") -> int:
    playbook = json.loads(PLAYBOOK.read_text()) if PLAYBOOK.exists() else {}
    plan = dryrun(pkg, beat, ep)
    meta = _beat_from_package(pkg, beat)
    findings = checks(plan, meta, playbook)
    blocks = [f for f in findings if f[0] == "BLOCK"]
    for sev, cid, msg, law in findings:
        print(f"  [{sev}] {cid}: {msg}\n         law: {law}")
    if not findings:
        print("  clean — no findings")
    print(f"PREFLIGHT: {'REFUSE FIRE — ' + str(len(blocks)) + ' BLOCK(s)' if blocks else 'CLEAR TO FIRE'}")
    return 1 if blocks else 0


def selftest() -> int:
    """Prove the brain catches the classic stupid outputs (no engine, no keys)."""
    bad_plan = {"prompt": 'Fuzzby, a plump yellow bee with spectacles, says "Nailed it" while his crystal glows. '
                          "Zenny hovers. 16:9.", "durationSec": 22}
    bad_meta = {"durationSec": 22, "cuts": [{"dialogue": "word " * 60}], "speakers": ["Fuzzby"]}
    findings = checks(bad_plan, bad_meta, {"beat_duration_rule": {"min_s": 8, "max_s": 15}})
    ids = {f[1] for f in findings}
    expect = {"identity-text", "law5-no-track", "no-references", "duration", "dialogue-overstuffed", "bee-crystal"}
    missing = expect - ids
    print(f"selftest findings: {sorted(ids)}")
    print("SELFTEST:", "PASS" if not missing else f"FAIL — missed {sorted(missing)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        raise SystemExit(selftest())
    if len(sys.argv) < 3:
        print("usage: preflight.py <package.json> <beatCode> [ep] | preflight.py selftest"); raise SystemExit(2)
    raise SystemExit(run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Ep1"))
