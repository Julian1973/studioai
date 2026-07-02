#!/usr/bin/env python3
"""DIRECTOR'S EYE — Gate 1.5 (flag & report only, runs AUTOMATICALLY at the end of every Gate 1).

After the Director (Gate 1) writes the beat package, this pass judges EVERY beat against TWO things:
  (1) THE SHOW BIBLE — canon, per-character bibles, the North Star, the Five Pillars/Crystal Power System, the
      comedy doctrine — is every decision TRUE to it?
  (2) PIXAR-CALIBRE 3D-CGI CRAFT — judged explicitly through the SAME four masters that write the beats (Pete
      Docter, John Lasseter, Patrick Lin, Jean-Claude Kalache): is the feeling leading the shot, is every character
      alive and specific, is the camera motivated and composed, is the light telling the story? A beat can be
      perfectly on-bible and still be generic, flat, or badly shot — this pass catches BOTH failure modes.
It does NOT rewrite, invent or change the package — it only judges, per the "faithful adapter, not a co-writer"
rule — the human decides what to act on. The story/craft twin of the technical QA gates (cb_qa).

    python3 cb_director_eye.py <package.json> [episode=Ep1]
"""
import os, sys, json, pathlib
import cb_llm, cb_director_schemas as S

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

def _show_bible():
    """The project's show bible: the canon doc + every character's structured bible."""
    canon = ""
    for cand in (ROOT / "CRYSTAL_BEARS_LOCKED_CANON.md", HERE / "CRYSTAL_BEARS_LOCKED_CANON.md"):
        if cand.exists():
            canon = cand.read_text(); break
    chars = json.load(open(HERE / "config" / "characters.json"))
    base = chars.get("characters", chars)
    bibles = {n: c["bible"] for n, c in base.items() if isinstance(c, dict) and c.get("bible")}
    return canon, bibles

def _project():
    try:
        pj = json.load(open(ROOT / "cb-studio" / "data" / "projects.json"))
        return (pj.get("projects") or [{}])[0]
    except Exception:
        return {}

def _slim(b):
    """Just the Director's DECISIONS for one beat — what the Eye judges."""
    return {
        "beatCode": b.get("beatCode") or b.get("shotCode"),
        "scene": b.get("sceneNumber"),
        "characters": b.get("characters"),
        "action": b.get("storyBeat") or b.get("startState"),
        "cuts": [{"framing": c.get("framing"), "action": c.get("action")} for c in (b.get("cuts") or [])],
        "dialogue": [c.get("dialogue") for c in (b.get("cuts") or []) if c.get("dialogue")],
        "emotionalIntent": b.get("emotionalIntent"), "want": b.get("want"), "need": b.get("need"),
        "cameraArc": b.get("cameraArc"), "light": b.get("light"), "atmosphere": b.get("atmosphere"),
        "crystal": b.get("crystalGlow") or b.get("crystal"),
        "keenCuffs": b.get("keenWristbands"),
        "comedyMode": b.get("comedyMode"),
        "continuity": b.get("continuity"),
    }

SYSTEM = (
    "You are the DIRECTOR'S EYE for a children's animated show — a rigorous, fair reviewer judging a FINISHED beat "
    "breakdown against TWO standards at once. You do NOT rewrite, invent, or add story — you only JUDGE. Flag a "
    "beat ONLY when it genuinely fails a standard; do not nitpick taste.\n\n"
    "STANDARD 1 — THE SHOW BIBLE (ruleType='bible'): you are handed the canon + per-character bibles + premise. "
    "Check, per beat: (1) each character ON-essence / voice / dos / donts / on-point-test; (2) the Five Pillars + "
    "Crystal Power System used correctly (right bear→crystal→colour→state→pillar; bees have NO crystal); (3) the "
    "NORTH STAR — the feeling shown OUTSIDE via the crystal, no villain, the Crystal Call is a SURRENDER not a "
    "power-up; (4) the COMEDY DOCTRINE — BIG when funny / small when true, never mean, laugh WITH not AT; (5) every "
    "beat OPENS and CLOSES (lands a button, never a dangling open the next beat resolves); (6) tone + safety for "
    "the target audience; (7) story + visual continuity across beats; (8) the episode theme is served.\n\n"
    "STANDARD 2 — PIXAR-CALIBRE 3D-CGI CRAFT (ruleType='craft'): judge EVERY beat through the SAME four masters "
    "that are supposed to have written it — flag a beat that fails their standard even if it is on-bible:\n"
    "• PETE DOCTER — does the FEELING lead the shot, is there a hidden inner NEED under the outward want, is the "
    "bittersweet held (not resolved away), is the biggest feeling carried WORDLESSLY where it should be? Flag "
    "anything generic, told-not-shown, or where plot outran feeling.\n"
    "• JOHN LASSETER — is every character a DISTINCT, believable, appealing personality (never a type, never "
    "interchangeable), is it genuinely ENTERTAINING (a real laugh, real delight, the four-year-old test), is the "
    "warmth SINCERE (never cynical or mean)? Flag a flat, generic, or joyless beat.\n"
    "• PATRICK LIN (camera) — is the shot COMPOSED like a film frame — a motivated, purposeful camera, staging that "
    "reads instantly, real depth (foreground/midground/background), framing chosen for the feeling? Flag a showy, "
    "unmotivated, or unreadable camera choice.\n"
    "• JEAN-CLAUDE KALACHE (lighting) — does the light carry STORY and emotion, is there a deliberate colour-script "
    "choice, does it shape depth and direct the eye? Flag flat, motivationless, or emotionally-mismatched lighting.\n\n"
    "For each flag, name the EXACT bible rule OR Pixar-craft principle it breaks (ruleType tells you which), and "
    "give a concrete, minimal fix — never a full rewrite suggestion, a single adjustable note. Return STRICT JSON "
    "only, matching the given schema."
)

def run(pkg_path, episode="Ep1"):
    p = pathlib.Path(pkg_path)
    if not p.exists():
        p = ROOT / "cb-output" / p.name
    d = json.load(open(p))
    beats = d.get("beats") or d.get("shots") or []
    proj = _project()
    canon, bibles = _show_bible()
    user = json.dumps({
        "project": {"name": proj.get("name"), "premise": proj.get("premise"),
                    "audience": proj.get("audience"), "style": proj.get("style")},
        "show_bible_canon": canon,
        "character_bibles": bibles,
        "episode": {"title": d.get("title"), "theme": d.get("theme") or d.get("declaration") or d.get("logline"),
                    "beats": [_slim(b) for b in beats]},
    }, ensure_ascii=False)

    print(f"DIRECTOR'S EYE — '{d.get('title')}' ({episode}): {len(beats)} beats vs the {proj.get('name','show')} "
          f"bible ({len(canon)} chars canon + {len(bibles)} character bibles) AND Pixar-craft (Docter/Lasseter/"
          f"Lin/Kalache)…", flush=True)
    rep = cb_llm.structured(SYSTEM, user, S.EyeReport, label="director_eye").model_dump()

    findings = rep.get("findings", [])
    flagged = [f for f in findings if str(f.get("verdict", "")).upper() == "FLAG" or f.get("flags")]
    bible_flags = sum(1 for f in flagged for fl in (f.get("flags") or []) if fl.get("ruleType") == "bible")
    craft_flags = sum(1 for f in flagged for fl in (f.get("flags") or []) if fl.get("ruleType") == "craft")
    out = HERE / "media" / f"{episode}_director_eye.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2))

    print(f"\n=== DIRECTOR'S EYE REPORT — {len(findings)} beats reviewed, {len(flagged)} flagged "
          f"({bible_flags} bible, {craft_flags} craft) ===", flush=True)
    for f in flagged:
        print(f"\n  ⚠ {f.get('beatCode')}", flush=True)
        for fl in (f.get("flags") or []):
            print(f"     [{fl.get('severity', '?')}/{fl.get('ruleType', '?')}] {fl.get('issue')}", flush=True)
            print(f"        RULE: {fl.get('rule')}", flush=True)
            print(f"        FIX:  {fl.get('fix')}", flush=True)
    if not flagged:
        print("  ✓ every beat is on-bible AND Pixar-calibre — no flags.", flush=True)
    s = rep.get("summary", {})
    print(f"\nSUMMARY: {s.get('flagged', len(flagged))}/{s.get('beatsReviewed', len(findings))} flagged "
          f"— {s.get('verdict', '')}", flush=True)
    print(f"(report saved: media/{episode}_director_eye.json)", flush=True)
    return rep

if __name__ == "__main__":
    os.chdir(HERE)
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Ep1")
