#!/usr/bin/env python3
"""
cb_writer.py — GATE 0, THE WRITERS' ROOM.

Turns a SEED into a finished, FUNNY, heartfelt, dialogue-LOCKED social-emotional-learning episode SCRIPT for
ages 4-8 — then SELF-SCORES it /10 on four factors (Show Bible / serves the why / characters on point /
layered humour). It runs ON the crystal-bears-writer skill (the room of five minds — Docter, Brumm, Stanton,
Nee, Woolverton — and the eight passes, the North Star, the Five Pillars, the Show Bibles, the scorecard).

It WRITES the script. It does NOT break it down — that is Gate 1 (cb_director). The output drops into exactly
the place Gate 1 reads, so the finished script flows straight into the pipeline.

  python3 cb_writer.py <seed.json> [Ep]        # write from a seed JSON file (the studio fires this)

Writes:
  ../cb-studio/data/scripts/<Ep>_<Title>.txt          the LOCKED screenplay (what Gate 1 ingests)
  ../cb-studio/data/scripts/<Ep>_<Title>.score.json   front-matter spine + structured scenes + the SCORECARD
"""
import os, re, sys, json, pathlib, requests
import cb_gen
import paths as P                             # T30 Phase 2/3 — the single source of path constants

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = pathlib.Path(P.SCRIPTS)
SKILL = next((p for p in [pathlib.Path.home() / ".claude/skills/crystal-bears-writer/SKILL.md",
                          ROOT / "skills/crystal-bears-writer/SKILL.md"] if p.exists()),
             ROOT / "skills/crystal-bears-writer/SKILL.md")
CANON = pathlib.Path(P.CANON)
CHARS = pathlib.Path(P.CHARS)
WRITER_MODEL = "gemini-3.1-pro-preview"   # the strongest reasoning model — the room writes here
BAR = 8.0                                  # the scorecard gate: nothing ships below this on any factor

# ── model plumbing (mirrors cb_director) ─────────────────────────────────────
def _gen(system, user, temperature=0.85, max_tokens=65536):
    url = f"{cb_gen.GLA}/v1beta/models/{WRITER_MODEL}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens,
                             "responseMimeType": "application/json"},
    }
    r = requests.post(url, headers={"x-goog-api-key": cb_gen.GEMINI_KEY, "Content-Type": "application/json"},
                      json=body, timeout=600)
    if r.status_code != 200:
        raise SystemExit(f"Writer model error {r.status_code}: {r.text[:400]}")
    j = r.json()
    try:
        return j["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise SystemExit(f"Writer parse error — no text. Finish: {j.get('candidates',[{}])[0].get('finishReason')} | {str(j)[:300]}")

def _repair_truncated(s):
    """Close a JSON reply cut off by the token cap (open string, dangling comma, missing ]/}) — recover the complete elements."""
    stack = []; in_str = esc = False
    for ch in s:
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch in "{[": stack.append(ch)
            elif ch in "}]" and stack: stack.pop()
    out = (s + ('"' if in_str else "")).rstrip()
    if out.endswith(","): out = out[:-1].rstrip()
    for ch in reversed(stack):
        out += "}" if ch == "{" else "]"
    return out

def _loadjson(text, what="output"):
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t).rsplit("```", 1)[0].strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    start = next((k for k, ch in enumerate(t) if ch in "{["), -1)
    body = t[start:] if start >= 0 else t
    if start >= 0:
        try:
            return json.JSONDecoder().raw_decode(body)[0]       # first complete value (handles "Extra data")
        except Exception:
            pass
        try:
            return json.loads(_repair_truncated(body))          # recover a TRUNCATED reply
        except Exception:
            pass
    m = re.search(r"[\{\[].*[\}\]]", t, re.S)
    if m:
        try:
            return json.JSONDecoder().raw_decode(m.group(0))[0]
        except Exception:
            pass
    raise SystemExit(f"Writer returned non-JSON {what} ({len(t)} chars). Head: {t[:200]!r} … Tail: {t[-160:]!r}")

# ── the room's mind (the writer skill + canon + the cast) ────────────────────
def _roster(chars):
    order = sorted([k for k, v in chars.items() if isinstance(v, dict) and k not in ("sizeClasses",)],
                   key=lambda k: chars[k].get("sizeRank", 99))
    out = []
    for k in order:
        c = chars[k]
        b = c.get("bible") if isinstance(c.get("bible"), dict) else {}
        ess = b.get("essence", "") or c.get("essence", "")
        voice = b.get("voice", "") or c.get("cadence", "")
        out.append(f"  - {k}: {c.get('size','')}" + (f" | essence: {ess}" if ess else "")
                   + (f" | voice: {voice}" if voice else ""))
    return "\n".join(out)

def _mind():
    skill = SKILL.read_text() if SKILL.exists() else ""
    canon = CANON.read_text() if CANON.exists() else ""
    chars = json.load(open(CHARS))
    system = (
        "You are the CRYSTAL BEARS WRITERS' ROOM — five Emmy/Oscar-calibre minds writing the funniest, most "
        "heartfelt social-emotional-learning episode imaginable for ages 4-8. INTERNALISE the five as your "
        "METHOD, not a flavour:\n"
        "• PETE DOCTER (heart) — lead with the FEELING; name the inner NEED beneath the outward want; the crystal "
        "is the Need made visible and it CONTRADICTS the brave face; hold the bittersweet; carry the most "
        "important feeling WORDLESSLY.\n"
        "• JOE BRUMM / Bluey (CHAIR) — the same-second co-watch (the child laughs at one thing, the parent feels "
        "another, in the SAME moment); PLAY is the engine — invent the GAME whose made-up rules ARE the emotional "
        "logic; keep the lesson INVISIBLE; own the SURRENDER beat.\n"
        "• ANDREW STANTON (structure) — the 2+2 firewall: make the audience put two and two together, NEVER hand "
        "them four; the spine that stops heart going shapeless and the lesson going preachy.\n"
        "• CHRIS NEE (curriculum) — the invisible curriculum: a real SEL competency a child never experiences AS a "
        "lesson, cast as a lived experience, tied to the lead's Pillar.\n"
        "• LINDA WOOLVERTON (clarity + LOCK) — a five-year-old feels the exact thing unnamed; every line tightened "
        "for lip-sync, then FROZEN verbatim.\n"
        "You WRITE the script; you do NOT break it into shots (that is the Director, downstream). NO villain — the "
        "antagonist is the feeling. The Crystal Call is a SURRENDER, never a power-up. Honour every character's "
        "Show Bible (essence / voice / do-don't). NEVER describe a bear's physical appearance and never bolt props "
        "onto a body (identity is owned by references downstream); write the crystal as VISIBLE/AUDIBLE ACTION "
        "(glow / flicker / dim / colour + the bear's note). Dialogue you write is FINAL and LOCKED.\n"
        "Output STRICT JSON ONLY (no prose, no markdown) matching the schema you are given.\n\n"
        "════════ YOUR CRAFT (the crystal-bears-writer skill — your brain: the eight passes + the scorecard) ════════\n" + skill +
        "\n\n════════ THE LOCKED CANON / SHOW BIBLE (source of truth — never contradict it) ════════\n" + canon +
        "\n\n════════ THE CAST (only these characters exist — never invent any) ════════\n" + _roster(chars) +
        "\n\nHold the NORTH STAR throughout: will they laugh out loud, will they breathe in, does the crystal tell "
        "the truth the bear can't yet say, does it reach the kid AND the parent in the same second."
    )
    return system, chars

def _seedblock(seed):
    f = lambda k: (seed.get(k) or "").strip() if isinstance(seed.get(k), str) else seed.get(k)
    lines = [
        f"TITLE: {f('title') or '(derive a great one)'}",
        f"TIME — length/format: {f('timeLength') or '11′ episode'}",
        f"TIME — setting (where + when): {f('timeSetting') or '(choose a canon location + time-of-day)'}",
        f"LOGLINE (the situation): {f('logline') or '(derive from the purpose + characters)'}",
        f"PURPOSE — the SEL lesson: {f('purpose') or '(derive a true, age-4-8 social-emotional truth)'}",
        f"PILLAR: {f('pillar') or '(choose the lead bear’s Pillar)'}",
        f"CHARACTERS: {f('characters') or '(cast the lead bear, the witness who sits-with-never-fixes, the comedy duo Fuzzby>Zenny)'}",
        f"TONE / comedy dial: {f('tone') or 'sit between Trolls-joy and Bluey-quiet; warm always'}",
    ]
    if f('want'): lines.append(f"WANT (locked): {f('want')}")
    if f('need'): lines.append(f"NEED (locked): {f('need')}")
    if f('crystalCall'): lines.append(f"CRYSTAL CALL this episode: {f('crystalCall')}")
    if f('continuity'): lines.append(f"CONTINUITY / season note: {f('continuity')}")
    return "\n".join(lines)

# ── PASS 0-3 — the PLAN (Heart Lock -> Lesson Lock -> Game+Spine -> Outline) ──
def plan(system, seed):
    user = (
        "RUN PASSES 0-3 of the writers'-room method on this SEED, then STOP and return the PLAN.\n\n"
        "THE SEED:\n" + _seedblock(seed) + "\n\n"
        "Pass 0 HEART LOCK (Docter): the lead bear's WANT (brave face) vs NEED (the truth the crystal shows) — the "
        "NEED MUST CONTRADICT the want; the one universal feeling; the bittersweet throughline; the kid-feeling and "
        "the parent-feeling the final frame lands. Pass 1 LESSON LOCK (Nee): the ONE SEL competency cast as a child's "
        "real lived experience (never 'a story about kindness'), tied to the Pillar. Pass 2 GAME + SPINE (Brumm w/ "
        "Stanton): the invented GAME whose made-up rules ARE the emotional logic + the Pixar spine mapped to the Five "
        "Pillars (Spark->Deepening->Heart->Connection->Ripple); NO villain. Pass 3 OUTLINE (Stanton): a per-scene "
        "outline — each scene's Pillar, emotional core, the moment the crystal CONTRADICTS the face, and the scene's "
        "kidRead + adultRead (the co-watch, designed in); mark the ONE wordless-held nadir and where the Crystal-Call "
        "SURRENDER lands (AFTER the feeling is fully felt). Beat-LESS — no shot breakdown.\n\n"
        'Return STRICT JSON: {"theme": str, "want": str, "need": str, "crystalTruth": str, "selCompetency": str, '
        '"pillar": str, "theGame": str, "spine": str, "bittersweet": str, "parentThread": str, '
        '"wordlessHeldBeat": str, "crystalCall": str, '
        '"scenes": [{"n": int, "name": str, "location": str, "time": str, "pillar": str, "core": str, '
        '"crystalContradiction": str, "kidRead": str, "adultRead": str}]}'
    )
    return _loadjson(_gen(system, user, temperature=0.8), "plan")

# ── PASS 4-7 — the DRAFT (Draft -> Co-Watch -> Braintrust -> Lock) ───────────
def draft(system, seed, the_plan, critique=None):
    redo = ("\n\nA PRIOR DRAFT SCORED BELOW THE BAR. REMAKE the weak beats (never soften a line into a moral; "
            "remake the BEAT) and lift every flagged factor to >= 8:\n" + json.dumps(critique, ensure_ascii=False)
            ) if critique else ""
    user = (
        "RUN PASSES 4-7 and return the FINISHED, DIALOGUE-LOCKED SCREENPLAY.\n\n"
        "THE SEED:\n" + _seedblock(seed) + "\n\nTHE LOCKED PLAN (passes 0-3):\n" +
        json.dumps(the_plan, ensure_ascii=False) + "\n\n"
        "Pass 4 DRAFT (Brumm w/ Docter): write the full screenplay — scene headings, action, VERBATIM "
        "character-cued dialogue in each bear's Show-Bible voice, speakable by a 5-year-old. Write the crystal as "
        "ACTION (glow/flicker/dim/colour + the bear's note), NEVER narrated; comedy grows FROM the want/need gap; "
        "the wordless nadir has ZERO dialogue; the surrender is a letting-go, never a power-up. Pass 5 CO-WATCH "
        "PUNCH-UP (Brumm): stack >=2 adult reads under the kid gags; catch-and-release (the funny goes quietly true, "
        "then exits within ~2s); the close HOLDS the ache. Pass 6 BRAINTRUST (Stanton chairs all five): attack it — "
        "anti-preach (extract every candidate 'lesson' line; if it survives as a moral, REMAKE the beat), crystal = "
        "the NEED not a mood, emotion is structural (remove the feeling and it must collapse), surrender-not-power-up, "
        "developmental truth for 4-8; loop until clean. Pass 7 LOCK + POLISH (Woolverton): tighten every line for a "
        "5-year-old and for lip-sync, FREEZE verbatim, attach the front-matter spine." + redo + "\n\n"
        "Return STRICT JSON: {\"title\": str, \"logline\": str, \"durationFormat\": str, "
        "\"frontMatter\": {\"theme\": str, \"needArc\": str, \"bittersweet\": str, \"selCompetency\": str, "
        "\"pillar\": str, \"parentThread\": str, \"wordlessHeldBeat\": str, \"runningCallback\": str}, "
        "\"scenes\": [{\"heading\": str, \"location\": str, \"time\": str, \"pillar\": str, \"kidRead\": str, "
        "\"adultRead\": str, \"body\": str}], "
        "\"scriptText\": str}  — scriptText is the WHOLE screenplay as one formatted string (the front-matter spine "
        "as a header block, then every scene heading + action + character-cued dialogue). Dialogue is LOCKED."
    )
    return _loadjson(_gen(system, user, temperature=0.85), "draft")

# ── THE SCORECARD — score the finished script /10 on the four factors ────────
def score(system, seed, the_draft):
    user = (
        "You are the Braintrust scoring the FINISHED script against the four-factor bar. Be a hard, fair judge — "
        "an 8 is the floor for shipping; a 10 is award-winning. Score each /10 with a one-line justification, and "
        "list any weak beats to remake.\n\n"
        "THE SEED (what it had to honour):\n" + _seedblock(seed) + "\n\n"
        "THE SCRIPT:\n" + (the_draft.get("scriptText") or json.dumps(the_draft.get("scenes"), ensure_ascii=False)) + "\n\n"
        "FACTORS:\n"
        "1 SHOW BIBLE — every character unmistakably themselves vs their bible (essence/voice/do-don't); canon "
        "airtight (Five Pillars, Crystal Power System, size chart, immutability); the crystal behaves to spec.\n"
        "2 SERVES THE WHY — the SEL purpose is FELT, never stated; dramatised through the Pillar and the crystal "
        "showing the NEED; remove the feeling and the story collapses. Any on-the-nose/moral line caps this at 6.\n"
        "3 CHARACTERS ON POINT — names off, you still know who's speaking; the witness sits-with (never fixes); the "
        "duo true (Fuzzby > Zenny).\n"
        "4 LAYERED HUMOUR — funny for the 4-year-old AND the parent in the SAME second; >=2 adult reads under kid "
        "gags; catch-and-release; feeling under every gag.\n\n"
        'Return STRICT JSON: {"showBible": {"score": number, "why": str}, "why": {"score": number, "why": str}, '
        '"characters": {"score": number, "why": str}, "humour": {"score": number, "why": str}, '
        '"overall": {"score": number, "why": str}, "weakBeats": [str]}'
    )
    return _loadjson(_gen(system, user, temperature=0.35), "scorecard")

def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_") or "Untitled"

def _min_factor(sc):
    return min((sc.get(k, {}) or {}).get("score", 0) for k in ("showBible", "why", "characters", "humour", "overall"))

# ── the room runs ────────────────────────────────────────────────────────────
def write(seed, episode="Ep1", log=print):
    system, _chars = _mind()
    title_hint = (seed.get("title") or "").strip() or "untitled"
    log(f"WRITERS' ROOM — writing '{title_hint}' ({episode}) on {WRITER_MODEL}", flush=True)

    log("  Passes 0-3 — Heart Lock · Lesson Lock · the Game + Pillar spine · the Outline...", flush=True)
    the_plan = plan(system, seed)
    log(f"  WANT: {the_plan.get('want','')[:90]}", flush=True)
    log(f"  NEED (the crystal truth): {the_plan.get('need','')[:90]}", flush=True)
    log(f"  THE GAME: {the_plan.get('theGame','')[:90]}", flush=True)
    log(f"  Pillar: {the_plan.get('pillar','')} · {len(the_plan.get('scenes',[]))} scenes outlined", flush=True)

    log("  Passes 4-7 — Draft · Co-Watch punch-up · Braintrust · Lock...", flush=True)
    d = draft(system, seed, the_plan)
    log(f"  draft locked: \"{d.get('title','')}\" — {len(d.get('scenes',[]))} scenes", flush=True)

    log("  THE SCORECARD — Show Bible / why / characters / layered humour...", flush=True)
    sc = score(system, seed, d)
    tries = 0
    while _min_factor(sc) < BAR and tries < 2:
        tries += 1
        low = {k: sc[k] for k in ("showBible", "why", "characters", "humour") if (sc.get(k, {}) or {}).get("score", 0) < BAR}
        log(f"  ↻ below the bar ({min((sc.get(k,{}) or {}).get('score',0) for k in ('showBible','why','characters','humour','overall'))}/10) "
            f"— remaking weak beats (pass {tries})...", flush=True)
        d = draft(system, seed, the_plan, critique={"weakBeats": sc.get("weakBeats", []), "factors": low})
        sc = score(system, seed, d)
    log(f"  SCORECARD — Bible {sc.get('showBible',{}).get('score')} · why {sc.get('why',{}).get('score')} · "
        f"characters {sc.get('characters',{}).get('score')} · humour {sc.get('humour',{}).get('score')} · "
        f"OVERALL {sc.get('overall',{}).get('score')}/10", flush=True)
    below_bar = _min_factor(sc) < BAR   # 2 remake passes is best-effort, not a guarantee — this can still be true
    if below_bar:
        log(f"  ⚠⚠ SHIPPING BELOW THE BAR — {_min_factor(sc)}/10 after {tries} remake pass(es); the LLM could not "
            f"clear {BAR}/10 on every factor. Written anyway (so Gate 1 isn't blocked) but flagged 'belowBar' in the "
            f"sidecar — needs a human punch-up pass before this script is treated as truly LOCKED.", flush=True)

    # write into exactly where Gate 1 reads — one script per episode
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    title = (d.get("title") or title_hint).strip()
    slug = _slug(title)
    for old in list(SCRIPTS.glob(f"{episode}_*.txt")) + list(SCRIPTS.glob(f"{episode}_*.score.json")):
        try: old.unlink()
        except Exception: pass
    script_path = SCRIPTS / f"{episode}_{slug}.txt"
    script_path.write_text(d.get("scriptText") or "", )
    sidecar = SCRIPTS / f"{episode}_{slug}.score.json"
    json.dump({
        "title": title, "logline": d.get("logline", ""), "durationFormat": d.get("durationFormat", ""),
        "episode": episode, "pillar": (d.get("frontMatter", {}) or {}).get("pillar", ""),
        "frontMatter": d.get("frontMatter", {}), "scenes": d.get("scenes", []),
        "scorecard": sc, "seed": seed, "model": WRITER_MODEL, "belowBar": below_bar,
        "_note": ("Authored by cb_writer (Gate 0, the Writers' Room). Dialogue is LOCKED — Gate 1 breaks it into beats, never rewrites a line."
                  + (f" ⚠ SHIPPED BELOW THE BAR ({_min_factor(sc)}/10 < {BAR}) after {tries} remake pass(es) — review before treating as final." if below_bar else "")),
    }, open(sidecar, "w"), indent=1, ensure_ascii=False)

    log(f"  ✓ wrote {script_path.name} ({'BELOW-BAR — needs review' if below_bar else 'LOCKED'} screenplay) + "
        f"{sidecar.name} (scorecard) → ready for Gate 1", flush=True)
    return {"script": script_path.name, "scoreFile": sidecar.name, "title": title,
            "scenes": len(d.get("scenes", [])), "scorecard": sc, "belowBar": below_bar}

if __name__ == "__main__":
    os.chdir(HERE)
    if len(sys.argv) < 2:
        sys.exit('usage: python3 cb_writer.py <seed.json> [Ep]')
    seed = json.load(open(sys.argv[1]))
    episode = sys.argv[2] if len(sys.argv) > 2 else (seed.get("episode") or "Ep1")
    r = write(seed, episode)
    print(json.dumps(r, indent=1))
