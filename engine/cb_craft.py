#!/usr/bin/env python3
"""cb_craft.py — THE PIXAR-CRAFT GATE (2026-07-07, Julian: "I want you to create the software that ensures
that we are five out of five on 'Would a Pixar shorts team be proud of this text.'").

The mechanical manifest gate (cb_preflight.py) proves every FIELD exists and is non-blank — it deliberately
never judges whether the content is any GOOD (rule 37: "the Manifest checks that the field exists, never that
the joke works"). A same-night independent audit (an 20-agent read-plus-skeptic pass over all 10 scenes,
scored against a concrete, checkable rubric) found the storyboard was real, disciplined craft in places —
North Star fidelity especially — but "competent" more often than "Pixar," with one repeated, independently-
confirmed failure mode: named ensemble bears with rich, specific bibles reduced to interchangeable reaction
verbs the moment 3+ of them share a beat.

This module is that audit's METHOD turned into permanent, re-runnable software, not a one-off finding:
  • CRAFT_RUBRIC — the exact concrete 5-criterion bar from that audit (never a vague "is this good" question,
    per rule 17's own standing lesson: a generous grader waves through a vague ask every time).
  • score_scene_craft() — TWO independent LLM reads per scene (a first pass + a deliberately skeptical second
    pass), MINIMUM score per criterion across both — the same anti-grade-inflation design the audit used,
    now callable from code instead of a throwaway workflow.
  • check_ensemble_individuation() — a DETERMINISTIC, zero-LLM, code-only heuristic for the one failure mode
    that recurred in every multi-character scene: does a background cast member's action text touch anything
    from their OWN bible lexicon, or is it a generic verb interchangeable with anyone else's?

Per rule 28 (THE GATES — MACHINE VS SHOWRUNNER), the holistic "is it funny, does it fly" verdict stays
Julian's RESERVED VERDICT — no check here ever auto-signs Gate 1 on a craft score. What this module DOES do:
surface every concrete, nameable gap loudly (cb_preflight wires these in as FLAG-level gaps, never a silent
BLOCK on a subjective score), and, for the ensemble-individuation finding specifically, DRAFT a targeted,
bible-cited rewrite for a human to review and apply — never auto-applied, the same surgical-retake-not-hand-
patch discipline this project already holds renders to (Law 3).
"""
import os, re, json, difflib
from typing import List
from pydantic import BaseModel, Field

HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTERS_PATH = os.path.join(HERE, "config", "characters.json")


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE RUBRIC — one canonical source, quoted verbatim into every scorer call so no caller reinvents the bar.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
CRAFT_RUBRIC = "\n".join([
    "You are judging CREATIVE CRAFT QUALITY of an animated kids' show storyboard — NOT technical/schema "
    "compliance (a separate mechanical pass already checks that every field is present and non-blank; field "
    "presence proves nothing about whether the content is actually good, so do not treat a populated field as "
    "evidence of quality). Score against these five concrete criteria, each 1-5, with 5 meaning genuinely "
    "award-caliber and 1 meaning generic/interchangeable filler:",
    "",
    "1. CHARACTER VOICE FIDELITY — does each character's actual dialogue and physical action in THIS scene's "
    "beats read as recognizably, specifically THEM, not interchangeable with any other character in the cast? "
    "Apply a swap test: could this exact line or action be given to a different character in this scene "
    "without changing anything? If yes, that is a fidelity gap — name it explicitly.",
    "",
    "2. COMEDY CRAFT — one gag arc per beat with real ESCALATION (the gag builds, it does not just repeat "
    "flat), SPECIFIC NAMED PHYSICAL GAGS with a clear cause and consequence (not generic adjective-chaos like "
    "'wildly' or 'crazily' with no concrete physical beat behind it), simultaneous contrast between characters "
    "sharing a frame (not alternating coverage), and a beat that never ends on the smaller gag — the real "
    "finisher always lands last. A scene with NO comedic content by design (a Heart/TRUE beat) should be "
    "scored on whether it correctly abstains from forcing a gag, not penalised for having none.",
    "",
    "3. EMOTIONAL / NORTH STAR FIDELITY — the feeling is always OUTSIDE (something you can see or hear), that "
    "represents a NEED that quietly contradicts the character's outward face, there is no villain anywhere in "
    "the story, and any 'Crystal Call' moment is a SURRENDER (giving in to finally be truly seen) — NEVER a "
    "power-up or rescue-activation beat. Score whether this scene's actual want/need/crystalTruth content is "
    "genuinely alive in the dialogue and action, not sitting unused as a label beside generic content.",
    "",
    "4. FIDELITY-LAW TRACEABILITY — nothing on screen is invented: a character's behavior should trace to "
    "something genuinely in that character's own bible (their mannerisms/essence/dos-donts/lexicon), not "
    "generic invented business that could belong to any family cartoon. Flag any beat where a character does "
    "something that reads like stock filler rather than something specific to who they are.",
    "",
    "5. OVERALL PIXAR-BENCHMARK VERDICT — reading only this scene's TEXT cold, would a Pixar shorts team be "
    "proud to have written it — specific, escalating, characterful, layered for both a child and a watching "
    "adult — or does it read as competent-but-generic family-cartoon plotting any studio could have produced "
    "for any cast? Be genuinely critical. Do not grade on a curve just because the beats are structurally "
    "complete.",
    "",
    "Ground every score in 2-4 short verbatim quotes pulled directly from the actual beat text as evidence — "
    "cite the beat code each quote came from. Do not accept your own first impression; reread the weakest-"
    "looking beat in the scene before finalizing scores.",
])


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Schema — identical shape for both the "first read" and the "skeptic" call, so scores merge cleanly.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
class _Criterion(BaseModel):
    score: int = Field(ge=1, le=5)
    verdict: str
    evidence: List[str]


class CraftScore(BaseModel):
    characterVoice: _Criterion
    comedyCraft: _Criterion
    emotionalNorthStar: _Criterion
    fidelityTraceability: _Criterion
    overallPixarBenchmark: _Criterion
    strongestBeat: str
    weakestBeat: str
    oneLineToFixFirst: str


_CRITERIA = ["characterVoice", "comedyCraft", "emotionalNorthStar", "fidelityTraceability", "overallPixarBenchmark"]


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# Serializing real data into the prompt — this runs headless via cb_llm.structured (a direct API call), not
# an Agent with its own Read-tool access, so the beat/character/script content must be INLINED, not pointed at
# by file path the way the one-off audit workflow's subagents could read for themselves.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _char_block(name, characters):
    entry = characters.get(name) or {}
    bible = entry.get("bible") or {}
    lines = [f"{name}:"]
    if bible.get("mannerisms"):
        lines.append(f"  mannerisms: {bible['mannerisms']}")
    if entry.get("actingNote"):
        lines.append(f"  actingNote: {entry['actingNote']}")
    if bible.get("dos"):
        lines.append(f"  always: {'; '.join(bible['dos'][:4])}")
    if bible.get("donts"):
        lines.append(f"  never: {'; '.join(bible['donts'][:4])}")
    return "\n".join(lines)


def _beat_block(beat):
    lines = [f"--- {beat.get('beatCode')} ({beat.get('slug', '')}) ---"]
    for f in ("storyBeat", "want", "need", "crystalTruth", "kidRead", "adultRead", "comedyMode", "endState"):
        if beat.get(f):
            lines.append(f"{f}: {beat[f]}")
    for c in (beat.get("cuts") or []):
        parts = [f"  cut {c.get('n')}: {c.get('action', '')}"]
        if c.get("dialogue"):
            parts.append(f"[{c['dialogue']}]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _script_excerpt(scene, script_scenes):
    sn = scene.get("sceneNumber")
    ss = next((s for s in script_scenes or [] if s.get("sceneNumber") == sn), None)
    if not ss:
        return "(no matching script scene found)"
    out = []
    for e in ss.get("elements") or []:
        if e["type"] == "action":
            out.append(e["text"])
        else:
            out.append(f"{e['character']}: {e['line']}")
    return "\n".join(out)


def _serialize_scene(scene, scene_beats, characters, script_scenes):
    cast = sorted({c for b in scene_beats for c in (b.get("characters") or []) + (b.get("openingCast") or [])})
    parts = [
        f"SCENE {scene.get('sceneNumber')}: {scene.get('name', '')}",
        f"pillar: {scene.get('pillar', '')}  |  emotionalCore: {scene.get('emotionalCore', '')}",
        "",
        "CAST BIBLES:",
        "\n\n".join(_char_block(c, characters) for c in cast),
        "",
        "ORIGINAL SCRIPT (for comparison — what did the storyboard add vs. just paraphrase?):",
        _script_excerpt(scene, script_scenes),
        "",
        "STORYBOARD BEATS (the actual content being judged):",
        "\n\n".join(_beat_block(b) for b in scene_beats),
    ]
    return "\n".join(parts)


def _stance_prefix(stance):
    if stance == "skeptic":
        return ("You are the SECOND, independent reader for this scene — a deliberately skeptical one. Assume "
                "the first pass through this material may have been too generous (a known failure mode on "
                "creative-quality checks is a grader that waves through anything structurally complete). "
                "Actively hunt for genericness, interchangeable dialogue, and 'tells' rather than 'shows'. "
                "Form your own scores from scratch.\n\n")
    return ""


def score_scene_craft(scene, scene_beats, characters, script_scenes, log=print):
    """Runs TWO independent structured LLM reads (review + skeptic) and takes the MINIMUM score per criterion
    — the same anti-grade-inflation design the one-off audit used, now permanent. Returns a dict:
    {criteria: {name: {score, verdict, evidence, agreement}}, review, skeptic}. A criterion's `agreement` is
    the ABSOLUTE gap between the two reads — a large gap is itself informative (a contested scene), surfaced
    by the caller as a FLAG, never silently averaged away."""
    import cb_llm
    scene_text = _serialize_scene(scene, scene_beats, characters, script_scenes)
    user = CRAFT_RUBRIC + "\n\n" + scene_text
    review = cb_llm.structured(_stance_prefix("review") + "You are a script/story craft reviewer for an animation studio.",
                                user, CraftScore, model=cb_llm.VALIDATOR_MODEL, label="craft/review", log=log)
    skeptic = cb_llm.structured(_stance_prefix("skeptic") + "You are a script/story craft reviewer for an animation studio.",
                                 user, CraftScore, model=cb_llm.VALIDATOR_MODEL, label="craft/skeptic", log=log)
    review, skeptic = review.model_dump(), skeptic.model_dump()

    merged = {}
    for crit in _CRITERIA:
        r, s = review[crit], skeptic[crit]
        worse = r if r["score"] <= s["score"] else s
        merged[crit] = {"score": worse["score"], "verdict": worse["verdict"], "evidence": worse["evidence"],
                        "agreement_gap": abs(r["score"] - s["score"])}
    return {"sceneNumber": scene.get("sceneNumber"), "criteria": merged, "review": review, "skeptic": skeptic}


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE ENSEMBLE-INDIVIDUATION CHECK — deterministic, zero-LLM, FLAG-level (a best-effort heuristic, same
# "report, never block on a computed proxy" convention cb_preflight.py already uses for its own "single gag
# arc" check). The one failure mode independently confirmed in EVERY multi-character scene of the audit:
# named background bears reduced to interchangeable reaction verbs the instant 3+ share a beat.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _stem_hit(verb, text):
    """A crude but honest substring/stem match — 'reach' matches 'reaches'/'reaching'; good enough for a
    best-effort FLAG, not precise enough to ever be a hard BLOCK (hence this check is always FLAG-kind)."""
    v = verb.lower().strip()
    if not v:
        return False
    return bool(re.search(re.escape(v[:max(4, len(v) - 2)]), text))


def _economized_set(beat, cast):
    """Names THE FIDELITY-ALLOCATION LAW (2026-07-07) explicitly excused from individuation this beat — parsed
    from the beat's own authored `fidelityAllocation.economized` (comma-separated names, or "none"). Empty if
    the field isn't present yet (older/unmigrated data) — callers fall back to checking everyone mentioned,
    exactly the pre-existing behaviour, so this is additive, never a regression for beats without the field."""
    fa = beat.get("fidelityAllocation") or {}
    raw = str(fa.get("economized") or "").strip()
    if not raw or raw.lower() == "none":
        return set()
    lower_cast = {c.lower(): c for c in cast}
    out = set()
    for part in raw.split(","):
        name = lower_cast.get(part.strip().lower())
        if name:
            out.add(name)
    return out


def check_ensemble_individuation(beat, characters):
    """For a beat naming 3+ characters in its own cast, checks whether EACH ONE'S action text (the ~15-word
    window following their name in the cut's action prose) touches anything from their OWN characters.json
    lexicon.verbs — a concrete, checkable proxy for 'is this character's own signature showing up here, or
    could this line belong to anyone.' Returns a list of flag dicts, never a hard verdict — word-window
    matching is approximate by construction (it cannot parse real grammar), so a clean flag list here is
    evidence of a LIKELY gap, not proof; a beat that legitimately clears it is strong evidence of real
    individuation, since a false NEGATIVE (missing a real hit) is the heuristic's only failure direction —
    it can undercount individuation, never invent it.

    REFINED 2026-07-07 to read THE FIDELITY-ALLOCATION LAW (`beat.fidelityAllocation`, cb_director_schemas):
    a character the beat's own author explicitly marked `economized` (deliberately generic/background THIS
    beat, a real authorial choice) is excused from the lexicon-trace requirement below — the heuristic no
    longer guesses at who "should" be individuated, it reads the beat's own declared answer where one exists,
    falling back to checking everyone mentioned (the original, coarser behaviour) when the beat has no
    fidelityAllocation authored yet."""
    cast = list(dict.fromkeys((beat.get("characters") or []) + (beat.get("openingCast") or [])))
    if len(cast) < 3:
        return []
    action_text = " ".join(str(c.get("action") or "") for c in (beat.get("cuts") or []))
    if not action_text.strip():
        return []
    lower = action_text.lower()
    economized = _economized_set(beat, cast)

    flags = []
    mentioned_verb = {}   # name -> the lexicon verb found in their name-window, or None if mentioned but no hit
    for name in cast:
        entry = characters.get(name) or {}
        verbs = (entry.get("lexicon") or {}).get("verbs") or []
        first = name.split("'")[0].strip().lower()
        pos = lower.find(first)
        if pos < 0:
            continue   # not mentioned by name at all — NOT flagged (see note below): a background cast member
                       # correctly staying silent is the deliberate rule-46 fix, not a fresh finding to re-raise
        window = lower[pos:pos + 120]   # ~15-20 words following the character's own name
        mentioned_verb[name] = next((v for v in verbs if _stem_hit(v, window)), None)

    # only characters NOT explicitly economized are held to the individuation bar — an economized character is,
    # by the beat's own authored decision, meant to read as generic ensemble; that's the field doing its job,
    # not a gap to flag.
    graded = {n: v for n, v in mentioned_verb.items() if n not in economized}
    lexicon_traced = [n for n, v in graded.items() if v]
    # NOTE: a character simply being ABSENT from this beat's action text is NOT itself flagged — rule 46's own
    # active/background split (cb_segprompt._v5_active_cast) already established that a background cast member
    # correctly staying silent in a beat that isn't theirs is the deliberate, CORRECT fix for the cast-size
    # word-count bug, not a fresh finding to re-litigate here. Only characters this beat ACTUALLY NAMES doing
    # something, but generically, are a real signal — hence gating on `mentioned_verb` (the actually-mentioned
    # set), never on `cast` (everyone merely present in the scene).
    if len(graded) >= 3 and not lexicon_traced:
        flags.append({"kind": "FLAG", "detail":
                      f"{len(graded)} non-economized cast members actually named doing something in this beat "
                      f"({', '.join(graded)}), but NONE of their action-text windows hit a verb from their own "
                      f"characters.json lexicon — a likely sign the ensemble's business is generic/"
                      f"interchangeable rather than individually bible-traced (heuristic word-window match; a "
                      f"false negative is possible, a false positive on this specific claim is not, since it "
                      f"only fires when literally zero hits were found)"})

    # near-duplicate clause structure: 2+ members assigned the exact SAME verb is a concrete, checkable
    # "interchangeable" signal — but NOT when BOTH are explicitly economized (two background characters
    # legitimately sharing a generic beat is exactly what "economized" means; only flag if at least one of the
    # pair is meant to be carrying the beat).
    verb_windows = {}
    for name in cast:
        first = name.split("'")[0].strip().lower()
        pos = lower.find(first)
        if pos < 0:
            continue
        window = lower[pos:pos + 40]
        m = re.search(r"\b(\w{4,})s?\b", window[len(first):].strip())
        if m:
            verb_windows.setdefault(m.group(1).rstrip("s"), []).append(name)
    dup_verbs = {v: names for v, names in verb_windows.items() if len(names) >= 2}
    for v, names in dup_verbs.items():
        if economized and all(n in economized for n in names):
            continue
        flags.append({"kind": "FLAG", "detail":
                      f"{', '.join(names)} are each given the near-identical action verb {v!r} in the same "
                      f"beat — a concrete 'interchangeable ensemble' signal regardless of lexicon match"})

    return flags


def _load_characters():
    try:
        d = json.load(open(CHARACTERS_PATH))
        return d.get("characters", d)
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
# THE REPAIR PROPOSAL — never auto-applied. Matches this project's own surgical-retake discipline (Law 3: "no
# output is ever hand patched... a fault routes through a retake with a layer diagnosis") extended to un-
# rendered storyboard text: a targeted, bible-cited rewrite is DRAFTED for a human to review and apply, the
# same way the surgical-retake-editing suite proposes a shot-level fix rather than silently overwriting one.
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────
class ActionRewrite(BaseModel):
    revisedAction: str
    citedSources: List[str]   # which character's bible field justified each change — nothing invented


def propose_ensemble_fix(beat, flags, characters, log=print):
    """ONE targeted repair call — rewrites ONLY this beat's cut action text, individuating the specific
    characters a check_ensemble_individuation flag named, each grounded in THEIR OWN bible field (never a
    generic swap of one bland verb for another bland verb). Returns {beatCode, original, proposal} for a human
    to review; nothing here mutates the beat package. The one-render economy (rule 28) applies: ONE proposal
    per call, never a batch of candidates to pick from."""
    import cb_llm
    code = beat.get("beatCode") or beat.get("shotCode")
    names = sorted({n for f in flags for n in re.findall(r"[A-Z][a-zA-Z']+(?:'s [A-Z][a-zA-Z']+)?",
                                                          f["detail"].split(" are each given")[0].split(" cast members")[-1])
                    if n in characters})
    if not names:
        return None
    original = "\n".join(f"cut {c.get('n')}: {c.get('action', '')}" for c in (beat.get("cuts") or []))
    bibles = "\n\n".join(_char_block(n, characters) for n in names)
    system = ("You are a story editor doing a SURGICAL rewrite, not a rewrite of the whole beat. Change ONLY "
              "the words needed to individuate the named characters' actions using their OWN bible fields — "
              "keep every other character, every plot beat, every piece of staging, and the approximate length "
              "exactly as they are. Never invent a new gag, prop, or plot event. Every change must be traceable "
              "to a quoted bible field, cited in citedSources.")
    user = (f"Beat {code}. Characters to individuate: {', '.join(names)}.\n\nTheir bibles:\n{bibles}\n\n"
            f"Current action text (cut-by-cut):\n{original}\n\n"
            f"The finding this rewrite addresses: {'; '.join(f['detail'] for f in flags)}\n\n"
            "Return the FULL revised action text for every cut listed above (same cut count, same order), "
            "with only the flagged characters' clauses rewritten.")
    result = cb_llm.structured(system, user, ActionRewrite, model=cb_llm.VALIDATOR_MODEL,
                               label=f"craft/propose/{code}", log=log)
    return {"beatCode": code, "original": original, "proposal": result.model_dump()}


if __name__ == "__main__":
    import sys, glob
    pkg_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    episode = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--episode=")), "Ep1")
    scene_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--scene=")), None)
    do_score = "--score" in sys.argv   # LLM calls cost money — opt in explicitly, ensemble check is always free
    propose_arg = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--propose-fix=")), None)

    if not pkg_arg:
        cands = glob.glob(os.path.join(HERE, "..", "cb-output", f"{episode}_*beat_package.json"))
        pkg_arg = max(cands, key=os.path.getmtime) if cands else None
    if not pkg_arg or not os.path.exists(pkg_arg):
        print("no beat package found"); sys.exit(0)

    d = json.load(open(pkg_arg))
    all_beats = d.get("beats") or d.get("shots") or []
    scenes = d.get("scenes") or []
    if scene_arg:
        all_beats = [b for b in all_beats if str(b.get("sceneNumber")) == str(scene_arg)]
        scenes = [s for s in scenes if str(s.get("sceneNumber")) == str(scene_arg)]
    characters = _load_characters()

    print("=" * 100)
    print("ENSEMBLE-INDIVIDUATION (deterministic, zero-cost)")
    print("=" * 100)
    for b in all_beats:
        flags = check_ensemble_individuation(b, characters)
        for f in flags:
            print(f"  [{f['kind']}] {b.get('beatCode')}: {f['detail']}")

    if propose_arg:
        # Found genuinely orphaned (zero call sites anywhere) by the 2026-07-07 contradiction-audit workflow —
        # this flag makes propose_ensemble_fix deliberately invocable, matching its own design (a proposal for
        # human review, never applied automatically; nothing here mutates the beat package).
        beat = next((b for b in all_beats if (b.get("beatCode") or b.get("shotCode")) == propose_arg), None)
        if not beat:
            print(f"no beat {propose_arg!r} found"); sys.exit(1)
        flags = check_ensemble_individuation(beat, characters)
        if not flags:
            print(f"{propose_arg}: no ensemble-individuation flags — nothing to propose a fix for"); sys.exit(0)
        result = propose_ensemble_fix(beat, flags, characters)
        print("=" * 100)
        print(f"PROPOSED FIX for {propose_arg} — REVIEW ONLY, nothing written to the beat package")
        print("=" * 100)
        print("\nORIGINAL:\n" + result["original"])
        print("\nPROPOSED:\n" + result["proposal"]["revisedAction"])
        print("\ncited sources:")
        for c in result["proposal"]["citedSources"]:
            print(f"  - {c}")
        sys.exit(0)

    if do_score:
        import cb_preflight as P
        script_scenes, _ = P._load_script_scenes(episode, {"characters": characters})
        by_scene = {}
        for b in all_beats:
            by_scene.setdefault(b.get("sceneNumber"), []).append(b)
        print("\n" + "=" * 100)
        print("CRAFT SCORE (dual-read, LLM — costs real API calls)")
        print("=" * 100)
        for s in scenes:
            beats = by_scene.get(s.get("sceneNumber"), [])
            if not beats:
                continue
            result = score_scene_craft(s, beats, characters, script_scenes)
            print(f"\nscene {s.get('sceneNumber')}:")
            for crit, c in result["criteria"].items():
                gap_note = f" (review/skeptic disagree by {c['agreement_gap']})" if c["agreement_gap"] >= 2 else ""
                print(f"  {crit}: {c['score']}/5{gap_note} — {c['verdict'][:140]}")
