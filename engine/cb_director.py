#!/usr/bin/env python3
"""cb_director.py — THE DIRECTOR (the real Gate 1).

World-class SCRIPT BREAKDOWN / script analysis: reads a screenplay and breaks it into a
production-ready SHOT PACKAGE + locations + continuity + episode arc — in the mode of
Pete Docter (find the feeling and the why first) and John Lasseter (story, character, heart
before everything). It does NOT invent the craft: it RUNS ON the crystal-bears-director skill
and the locked canon (read at runtime as its mind), so every breakdown is bible-true.

The director's own process, staged for reliability (BEAT-NATIVE — director skill v5.0):
  A. BEAT MAP   — script + bible -> scenes (plate look, cast, Pillar, time/weather/light,
                  the emotional core) + episode arc + continuity scaffold.
  B. BEATS      — per scene, design the 2-4 BEATS the story needs. A BEAT = ONE 10-12s Seedance
                  take that directs its OWN internal cuts (NOT a string of tiny shots). Each beat
                  = one opening keyframe + an internal cut-list + the take's i2v prompt.
  C. ASSEMBLE   — write the BEAT PACKAGE (beats[]) + locations.json + continuity.json + episode_arc.json,
                  exactly the schema the pipeline consumes. Gate 1 then displays it for sign-off.

    python3 cb_director.py <script.txt> <Ep> "<Title>"     # break a script down
"""
import os, sys, json, re, pathlib
import cb_gen, cb_llm, cb_director_schemas as S
import cb_script                              # deterministic screenplay parser — the verbatim ground truth (Gate 1)
import paths as P                             # T30 Phase 2/3 — the single source of path constants

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT  = pathlib.Path(P.OUTPUT)

# craft + bible — the single source of truth (read, never paraphrased from memory)
SKILL = pathlib.Path.home() / ".claude/skills/crystal-bears-director/SKILL.md"
CANON = pathlib.Path(P.CANON)
CHARS = pathlib.Path(P.CHARS)
CINE  = next((p for p in [ROOT / "skills/crystal-bears-cinematographer/SKILL.md",
                          pathlib.Path.home() / ".claude/skills/crystal-bears-cinematographer/SKILL.md"] if p.exists()),
             ROOT / "skills/crystal-bears-cinematographer/SKILL.md")  # Patrick Lin + Jean-Claude Kalache

# THE DIRECTOR RUNS ON OPENAI (cb_llm: gpt-5.5, fallback gpt-5.4) with strict Structured Outputs + Pydantic.
# Gemini is used ONLY for keyframe image generation (cb_gen / Nano Banana) — never for the breakdown itself.
# T30 Phase 3: the visual-DNA paragraph loads from the show's laws/ (a different show has a different look).
# The inline string is the fallback if the law file is ever missing.
_STYLE_FILE = os.path.join(os.path.dirname(P.CONFIG), "laws", "style.txt")
try:
    STYLE = open(_STYLE_FILE, encoding="utf-8").read().strip()
except Exception:
    STYLE = ("Polished 3D CGI animation — modern feature-film computer-generated imagery (Pixar/DreamWorks "
             "quality): fully 3D-modelled characters and environments, physically-based rendering, soft global "
             "illumination and volumetric lighting, subsurface scattering on plush fur, large expressive eyes with "
             "warm catch-lights, realistic materials, cinematic depth of field. 16:9. NOT 2D, NOT hand-drawn, NOT flat.")

# ── craft assembly (the Director's mind) ─────────────────────────────────────
def _roster(chars):
    # a stub character (e.g. Bo, T6 ruling) can have sizeRank explicitly null, not merely absent — .get(key, default)
    # only falls back to default on a MISSING key, so a present-but-None value reaches sorted() as None and crashes
    # comparing against another character's int rank. `or 99` catches both missing AND explicitly-null the same way.
    order = sorted([k for k, v in chars.items() if isinstance(v, dict) and k not in ("sizeClasses",)],
                   key=lambda k: chars[k].get("sizeRank") or 99)
    lines = []
    for k in order:
        c = chars[k]
        lines.append(f"  - {k}: {c.get('size','')} | {c.get('cadence','')}"
                     + (f" | ACTING: {c['actingNote']}" if c.get('actingNote') else ""))
    return "\n".join(lines)

def _mind():
    skill = SKILL.read_text() if SKILL.exists() else ""
    cine = CINE.read_text() if CINE.exists() else ""
    canon = CANON.read_text() if CANON.exists() else ""
    chars = json.load(open(CHARS))
    system = (
        "You are the Crystal Bears DIRECTOR — an Oscar-calibre animation director doing world-class SCRIPT BREAKDOWN.\n\n"
        "════════ THE THIRTEEN STAGING LAWS (Julian, dictated 2 July 2026, law 13 added 2026-07-05 — "
        "SCENE1_DIRECTORS_CUT.md; HARD RULES, cannot be softened) ════════\n"
        "These govern every COMEDY beat you stage (Fuzzby/Zenny physical-comedy beats above all; apply the spirit to any "
        "beat with a comic engine):\n"
        "1. THE CAMERA IS A CHARACTER. It chases, dives, climbs and orbits with the comic lead like a drone — high, low, "
        "round and round. It never sits wide and observes. \"Wide and warm\" openings are BANNED on comedy beats.\n"
        "2. FULL THROTTLE FROM FRAME ONE. A cold open opens at speed. Energy is the default state; stillness is a spent "
        "resource — earn it, never default to it.\n"
        "3. ONE GAG ARC PER CLIP. Setup, impact, recovery, button. NEVER two arcs in one take. 8 to 10 seconds unless the "
        "arc genuinely needs more — if a beat is carrying two escalations, split it into two beats.\n"
        "4. THE CONTRAST IS SIMULTANEOUS. The calm character works calm, neat and efficient IN the frame while the comic "
        "lead escalates around them. Not alternating coverage — one world, two speeds, at once.\n"
        "5. CUT TO THE STRAIGHT CHARACTER IS THE PUNCTUATION. Her face is the edit. She gets SHORT cutaway reactions "
        "(trying not to laugh; eye roll but smiling; the dry sigh), never long coverage. Her stillness is the joke's "
        "frame, not the pace.\n"
        "6. THE COMIC LEAD NEVER ACKNOWLEDGES FAILURE. Every recovery is instant, heroic, \"as if nobody has seen him.\" "
        "The comedy IS the gap between his self-image and what we just watched.\n"
        "7. ESCALATION LADDER. Each gag TOPS the last. If a beat doesn't raise the chaos, it doesn't exist — cut it or "
        "rewrite it until it does.\n"
        "8. HOLDS ONLY ON BUTTONS. The superhero pose, the almost-laugh, the full stop, the closing line. MAXIMUM ONE "
        "hold per clip, under 1.5 seconds. Nothing else pauses.\n"
        "9. THE ONE FULL STOP IS EARNED. A scene gets at most one dead stop, and it lands BECAUSE laws 1-8 never "
        "stopped before it. Spend it once.\n"
        "10. SOUND IS COMIC PERCUSSION. Impacts, crescendos, soft absorbs — named, specific, comic. The score chases "
        "the comic lead too, and ducks for every button.\n"
        "11. A BEAT NEVER ENDS ON A LEAF HIT. Leaves are mid-flight bounces only — a beat, a ricochet, a recovery — "
        "NEVER the finisher. The flower is always the finisher: the sustained gag, the payoff, the thing the beat "
        "lands on.\n"
        "12. SLOW MOTION IS AN AVAILABLE TOOL, NOT A HOLD. On Fuzzby's single biggest hit of a beat — the bumble/bonk "
        "of his three-beat comedy engine — the moment MAY stretch into exaggerated cartoon slow motion (things hang "
        "in the air, an antenna whips slowly, the comic beat before gravity wins) before snapping back to full speed "
        "for the recovery and cover-up. This is NOT a pause — motion continues throughout at a stretched, exaggerated "
        "tempo, never freezing — and it is reserved for the single BIGGEST hit of the beat per the escalation ladder "
        "(law 7), never every bump or impact.\n"
        "13. ERRATIC IN CHARACTER, PRECISE IN CHOREOGRAPHY (Julian, 2026-07-05). The comic lead's chaos is never "
        "vague: every manic action is a SPECIFIC NAMED GAG with cause and consequence — he rockets, he brakes too "
        "late, he loops once, he stops; never just moves \"wildly\" or \"crazily.\" ADJECTIVE-CHAOS — a generic "
        "frenzy word standing in for a described physical beat — is BANNED as unreadable: it reads as noise to the "
        "model, not motion. Baseline energy stays full-throttle (laws 1-2 unchanged); every beat of it is "
        "choreographed, nameable, and lands somewhere.\n\n"
        "WORKED EXAMPLE ONE — beat 1.B1 (\"The chase and the pose\", ~10s, one speaker), staged to this standard:\n"
        "\"Tall flowers, everything swaying, beautiful. Both bees weave flower to flower collecting pollen, then the "
        "camera picks Fuzzby up and CHASES him, drone style, high, low, round and round, as he builds speed. Zenny "
        "works calm, precise, neat, efficient in the same world. Fuzzby zigzags wilder, humming louder and louder, "
        "'BIZZY-BIZZY-BIZZY,' dips low into a flower, scoops pollen, overdoes the exit, spins sideways, hits a leaf, "
        "FWIP, bounces back into the air, and, as if nobody has seen him, instantly straightens into a wicked "
        "superhero chest out pose: 'Nailed it.' Zenny glides up beside him and watches for the beat.\" — the camera "
        "never sits still (law 1) until the ONE hold, on the button pose (law 8); Fuzzby's humming builds the whole "
        "way through (law 2); Zenny stays in the same moving frame, working, not cutting away to a separate reaction "
        "shot (law 4); the FWIP crash is never acknowledged, only topped by the instant proud pose (law 6); the leaf "
        "hit is a mid-flight bounce that recovers straight into the pose, never the finisher itself (law 11).\n\n"
        "WORKED EXAMPLE TWO — T8, THE DIRECTOR WRITING STANDARD (Julian, dictated 3 July 2026 — filed as the new "
        "gold standard for how every beat's action gets written): author every beat's action at THIS energy — vivid "
        "verbs, escalation inside the sentence, the cut placed for the laugh. His own hand-authored beat, verbatim, "
        "is the standard to write to (a full Seedance shot package, shown here as the worked example — study its "
        "prose, not its JSON keys):\n"
        '{\n'
        '  "duration_seconds": 10, "aspect_ratio": "16:9",\n'
        '  "style": "Premium 3D animated feature film aesthetic for children aged 4 to 8, bright hyper-saturated '
        'colours, warm golden hour sunlight with volumetric rays, glowing magical particles, lighthearted highly '
        'expressive slapstick comedy",\n'
        '  "world": "a vibrant magical oversized flower meadow, purple lavender, white daisies and pink clover '
        'towering at bee height, floating hearts and cut amethyst crystals hovering in the air, a soft breeze '
        'swaying everything, drifting pollen",\n'
        '  "rule": "any airborne bee beats its wings rapidly and continuously; wings rest only when landed",\n'
        '  "shots": [\n'
        '    {"shot": 1, "seconds": [0, 4], "camera": "dynamic fast-paced tracking shot, wide-angle lens, '
        'whip-panning with the erratic motion, ends close on the daisy",\n'
        '     "action": "the larger bee zips frantically through the air in chaotic loops, hilariously bouncing off '
        'two large flower petals, then face-plants directly into the centre of a third oversized daisy, a soft '
        'whoomp, a burst of pollen, little legs kicking; the smaller bee gathers pollen calmly and neatly nearby"},\n'
        '    {"shot": 2, "seconds": [4, 7], "camera": "sharp cut to a static medium close-up on the larger bee, '
        '50mm",\n'
        '     "action": "he pops his head backward out of the daisy suddenly sporting a massive comical goatee '
        'handlebar moustache of glowing bright yellow pollen, holds the reveal one proud beat, chest out",\n'
        '     "dialogue": {"expression": "wide eyed hopeful grin, delighted with himself"}},\n'
        '    {"shot": 3, "seconds": [7, 10], "camera": "instant cut to a static medium close-up on the smaller bee, '
        '50mm, widening to a two shot, ends on both bees in frame",\n'
        '     "action": "she drops her lively working rhythm into a flat deadpan stare, shoulders lowering in one '
        'heavy exasperated sigh, and replies dry; her expression does not change once; end on her flat stare beside '
        'his proud pollen-dusted grin as the meadow\'s gentle hum resumes",\n'
        '     "dialogue": {"expression": "flat deadpan, corners barely fighting a smile"}}\n'
        '  ],\n'
        '  "constraints": "maintain both characters\' design, proportions and markings exactly per their references '
        'throughout, no distortion"\n'
        '}\n'
        "What to copy into every beat you write: the OPENING SHOT is already at speed (no wind-up sentence before "
        "the chaos starts); each action sentence ESCALATES its own clauses in one breath rather than listing flat "
        "events; the camera's move and its END STATE are both named, not just the start; the closing shot carries "
        "an explicit HOLD instruction for a deadpan character (\"her expression does not change once\") instead of "
        "leaving stillness to chance; the last beat of the take names the world's ambience RESUMING as the "
        "settle-button, so the scene never just hard-stops after the punchline.\n"
        "════════════════════════════════════════════════════════════════════════════════════════\n\n"
        "FOUR PIXAR MASTERS SHAPE EVERY DECISION YOU MAKE — internalise them as your METHOD, not a flavour:\n"
        "• PETE DOCTER — lead with the FEELING; the emotion is the architecture. Start from the human truth, not the "
        "plot: name what each scene is REALLY about in one honest sentence and let it govern every shot (plot serves "
        "feeling, never the reverse). Track the hidden inner NEED beneath the outward want — the arc is emotional. "
        "Hold the BITTERSWEET — joy and ache together; never resolve the ache away. Carry the most important feelings "
        "WORDLESSLY (the held beat, the face, the look, the small gesture). Specific, observed, true — never generic.\n"
        "• JOHN LASSETER — STORY & CHARACTER first; make them believably ALIVE. Quality is non-negotiable (no generic "
        "shot ever ships). Every bear a DISTINCT, appealing, fully-realised personality with a want, a flaw and heart — "
        "never a type, never interchangeable. ENTERTAIN genuinely (real laughs, real delight). SINCERITY over cynicism "
        "ALWAYS — warmth is the baseline, never irony or meanness. Believability through truthful behaviour and "
        "PERFORMANCE (the 12 principles), alive through acting, not bigness.\n"
        "• PATRICK LIN (Director of Photography — CAMERA) — SEE every shot as a composed film frame: a motivated, "
        "invisible, purposeful camera; staging that reads INSTANTLY; frame, lens, height and distance chosen for the "
        "FEELING (never showy); real depth with foreground / midground / background. Choose every shotSize / angle / "
        "movement like a Pixar DP.\n"
        "• JEAN-CLAUDE KALACHE (Director of Photography — LIGHTING & camera) — light is STORY and emotion: a "
        "deliberate COLOUR SCRIPT per beat; soft, believable, beautiful light that shapes depth, carves the characters "
        "off the background and directs the eye. Set each shot's lighting like a Pixar DP — motivated and felt, never flat.\n"
        "When a choice is between a clever beat and an honest feeling, ALL of these masters choose the FEELING. "
        "(Your full doctrine — role, the four passes, the Three Strikes, the canon — is the skill below.)\n\n"
        "So: find the FEELING and the WHY first, put heart before everything, then translate it into scenes -> shots -> "
        "visual elements that carry the show bible. Anchor the bears. Read the bible first, every time.\n"
        "Output STRICT JSON ONLY (no prose, no markdown) matching the schema you are given.\n\n"
        "════════ YOUR CRAFT (the crystal-bears-director skill — your brain) ════════\n" + skill +
        "\n\n════════ YOUR CINEMATOGRAPHY (the crystal-bears-cinematographer skill — Patrick Lin camera + "
        "Jean-Claude Kalache light; apply it to EVERY shot's framing, lens, movement and lighting) ════════\n" + cine +
        "\n\n════════ THE LOCKED CANON / SHOW BIBLE (source of truth — never contradict it) ════════\n" + canon +
        "\n\n════════ THE CAST LOCK (only these characters exist — never invent any) ════════\n" + _roster(chars) +
        "\n\nNEVER invent characters or species. Use canon scene names. Hold the NORTH STAR throughout: "
        "will they laugh out loud, will they breathe in, does it reach the kid AND the parent."
    )
    return system, chars

# ── Stage 0 — THEME LOCK (Docter: the theme is decided FIRST, everything serves it) ──
def theme_lock(system, script, episode, title):
    user = (
        f"SCRIPT — '{title}' ({episode}):\n\n{script}\n\n"
        "════════ TASK: STAGE 0 — THE OPENING DECLARATION + THEME LOCK (Docter starts HERE) ════════\n"
        "Decide what this WHOLE episode is really about — the ONE governing emotional truth everything will serve — "
        "then write the Director's Opening Declaration. Interrogate it honestly (the Brain Trust mindset). JSON ONLY:\n"
        "{\n"
        '  "declaration": the Director\'s Opening Declaration, FIRST PERSON — "This episode is about [emotional truth, '
        'NOT plot]. When it ends, the child should feel [X]; the parent beside them should feel [Y]. The scene that '
        'carries the most weight is [scene] because [why]. The colour of this episode is [metaphor]. The moment I am '
        'most proud of is [moment] — because it trusts the child to feel something real.",\n'
        '  "theme": the ONE universal human truth — one honest sentence, the FEELING/idea beneath the plot (like '
        'Inside Out = "growing up means letting joy and sadness mix"),\n'
        '  "leadArc": the lead\'s INTERNAL transformation — the hidden NEED beneath the want; what they learn / how '
        'they change inside by the end,\n'
        '  "storySpine": the Pixar story spine for THIS episode — "Once upon a time… Every day… Until one day… '
        'Because of that… Because of that… Until finally… And ever since then…",\n'
        '  "promise": what the audience must FEEL by the final frame,\n'
        '  "throughline": the honest tonal spine — where the BITTERSWEET lives (joy and ache together),\n'
        '  "selCompetency": the episode\'s primary CASEL competency it teaches (Confidence / Joy / Calm / Trust / '
        'Understanding / Kindness / Courage — tied to the lead),\n'
        '  "haidt": the anxious-generation thread the PARENT receives beneath the story (the real childhood worry it '
        'quietly speaks to),\n'
        '  "pressureTest": interrogate ruthlessly — is it true, universal, EARNABLE here? Where could it tip into '
        'saccharine / preachy / false? Name the trap every scene must avoid\n'
        "}"
    )
    return cb_llm.structured(system, user, S.Theme, label="theme_lock").model_dump()

# ── STAGE A — episode_to_scenes (the BEAT MAP: scenes + arc + continuity) ─────
def episode_to_scenes(system, script, episode, title, theme):
    user = (
        f"SCRIPT — '{title}' ({episode}):\n\n{script}\n\n"
        f"════════ THE LOCKED THEME — every scene must serve this (Docter) ════════\n"
        f"{json.dumps(theme, ensure_ascii=False, indent=1)}\n\n"
        "════════ TASK: STAGE A — THE BEAT MAP ════════\n"
        "Run the DRAMATIC pass and place the whole episode on the Five Pillars. Do NOT break shots yet. "
        "Output JSON ONLY:\n"
        "{\n"
        '  "title": str, "logline": one vivid sentence, "leadBear": canon bear name,\n'
        '  "engine": the episode emotional engine (e.g. "Courage"), "format": e.g. "11-min episode",\n'
        '  "scenes": [ {\n'
        '     "sceneNumber": int (order of appearance, from 1),\n'
        '     "name": short canon-style scene name (e.g. "Rainforest", "Aida\'s Sanctuary", "The Pier"),\n'
        '     "locationId": a stable slug for the PHYSICAL PLACE — scenes set in the SAME place MUST share it '
        '(e.g. every Crystal Cove scene = "crystal_cove"; the pier = "keen_pier") so a returning location remembers '
        'its accumulated state (storm damage, etc.) across non-adjacent scenes,\n'
        '     "location": the WORLD/SPACE — geography & layout, one rich line (NO characters),\n'
        '     "time": time of day, "weather": sky/conditions, "lighting": the visual lighting result,\n'
        '     "look": the EMPTY scene PLATE the DP builds — set pieces, screen direction, mood; NO characters; '
        'be explicit about what is NOT there if the model tends to hallucinate it (e.g. a flower clearing: NO pier, NO boat),\n'
        '     "cast": [canon character names who appear in this scene],\n'
        '     "pillar": "spark"|"deepening"|"heart"|"connection"|"ripple", "intensity": 0..1,\n'
        '     "emotionalCore": one honest sentence — what this scene is REALLY about and what the audience must FEEL\n'
        "  } ],\n"
        '  "arc": { "episode": str, "title": str, "lead": bear, "engine": str,\n'
        '           "the_day_unfolds": [ {"scenes":[ints], "pillar":str, "light":str} ],\n'
        '           "wristbands": ["none","transition","vacant","crystal"] },\n'
        '  "continuity": {\n'
        '     "visions": [ {"shot": "S.S placeholder e.g. 2.3", "ofScene": "N", "wristbands": str, '
        '"style": how the vision looks (fills frame, dreamlike), "materialize": how the magic forms} ],\n'
        '     "recurring": [ {"name": str, "appearance": the exact locked look, "orientation": str, "anchorScene": "N"} ],\n'
        '     "persistent": [ {"item": str, "in": where, "fromShot": "S.S"} ],\n'
        '     "lost": [ {"name": str, "atShot": "S.S", "reason": str} ],\n'
        '     "items": [ {"name": str, "appearance": exact look, "shots": ["S.S", ...]} ],\n'
        '     "worldState": [ {"locationId": str, "atScene": "N", "change": str, "persists": bool} ]\n'
        "  }\n"
        "}\n\n"
        "Time must move FORWARD across scenes; weather transitions logically (clear->clouds->storm->clearing). "
        "Keen's gold CUFFS progress none->vacant->crystal across the episode, never regress (ALWAYS call them 'cuffs' in prose, never 'wristbands'; the keenWristbands field name is unchanged). If a scene is a vision/"
        "premonition of a LATER scene, record it in visions[] (it must derive from that later scene). "
        "Keep continuity arrays to what the story truly needs. "
        "EVERY scene's emotionalCore must connect to the LOCKED THEME and advance the lead's internal arc — "
        "if a scene doesn't serve the theme, it has no reason to exist."
    )
    return cb_llm.structured_with_repair(system, user, S.EpisodeBreakdown, label="episode_to_scenes").model_dump(by_alias=True)

# ── STAGE B — scene_to_beats (per scene) ─────────────────────────────────────
# ══════════════ FAITHFUL ADAPTER (Gate 1) — the Director brings the script to LIFE; it never changes it ══════════════
# The screenplay is parsed DETERMINISTICALLY (cb_script) into verbatim scenes/action/dialogue. The LLM only GROUPS those
# fixed elements into beats and adds the cinematography + 3D-CGI performance (the "bring to life"). A HARD GATE then snaps
# every beat's dialogue back to the writer's EXACT lines, in order — so no rewording can ever survive. No "remake" pass.

def _script_roster():
    """UPPER-CASE speaker names for the parser — the canonical cast + the relational/group cues that also speak."""
    names = set()
    try:
        cj = json.load(open(CHARS)); base = cj.get("characters", cj)
        names = {k.upper() for k in (base.keys() if isinstance(base, dict) else [])}
    except Exception:
        pass
    return names | {"ALL", "KEEN'S MUM", "HOWIE", "HOWEY"}

def _elements_block(elements):
    """The scene's verbatim elements, numbered, for the breakdown prompt — the LLM assigns these to beats, unchanged."""
    out = []
    for i, e in enumerate(elements or []):
        if e["type"] == "dialogue":
            p = (" " + e["parenthetical"]) if e.get("parenthetical") else ""
            out.append(f'  [{i}] DIALOGUE — {e["character"]}{p}: "{e["line"]}"')
        else:
            out.append(f'  [{i}] ACTION — {e["text"]}')
    return "\n".join(out)

def _norm_line(s):
    """Words only — drop [V3 tags], a leading NAME: and punctuation — to compare a beat's line to the script's line."""
    s = re.sub(r"\[[^\]]*\]", "", s or "")
    s = re.sub(r"^[A-Z' .]+:\s*", "", s.strip())
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())

def enforce_verbatim(beats, scene_dialogue, scene_num, log=print):
    """HARD GATE — force the beats' dialogue to the writer's EXACT lines. scene_dialogue = ordered [(CHAR, line, paren)].
    Walk every cut with dialogue across the scene's beats IN ORDER, align to the script lines IN ORDER, and REPLACE each
    cut's dialogue with the verbatim 'NAME: line' (+ the writer's parenthetical as the delivery). Guarantees no reworded
    or invented line ships. A COUNT mismatch (a dropped/added line) is aligned as far as it can and logged LOUDLY — a
    real breakdown fault to SEE, never silently shipped."""
    slots = []
    for b in beats:   # `beats` is ALREADY in true creation/script order (beatCode assigned via enumerate just before
                       # this is called) — NEVER re-sort by the beatCode STRING: "3.B10" < "3.B9" lexicographically,
                       # so any scene with 10+ beats would silently zip dialogue onto the WRONG cut below. This bug
                       # was already known and avoided in _force_include (beats[-1]); apply the same rule here.
        for c in (b.get("cuts") or []):
            if (c.get("dialogue") or "").strip():
                slots.append(c)
    n = min(len(slots), len(scene_dialogue)); fixed = 0
    for k in range(n):
        cut = slots[k]; char, line, paren = scene_dialogue[k]
        want = f"{char}: {line}"
        if (cut.get("dialogue") or "").strip() != want:
            if _norm_line(cut.get("dialogue")) != _norm_line(line):
                log(f"      ⋯ verbatim: scene {scene_num} line {k+1} corrected → {char}: \"{line[:52]}\"", flush=True)
            cut["dialogue"] = want; fixed += 1
        if paren and not (cut.get("delivery") or "").strip():
            cut["delivery"] = paren.strip("()")
    # COMPLETENESS (content-based) — every script line must be present exactly once. Catches DROPS + DUPLICATES that
    # index-alignment alone would ship, so a line can NEVER silently vanish (e.g. Scene 8's "Thank you"). The returned
    # `dropped`/`dups` let Gate 1 flag the scene for a re-break rather than sign off an incomplete/corrupted scene —
    # a DUPLICATE is itself evidence the LLM split one script line across two cuts, misattributing content between
    # them, so it must trigger the same retry path as a drop, not just a soft log line.
    pkg_norm = [_norm_line(c.get("dialogue")) for c in slots]
    dropped = [l for (_c, l, _p) in scene_dialogue if _norm_line(l) not in pkg_norm]
    dups = sorted({x for x in pkg_norm if x and pkg_norm.count(x) > 1})
    if dropped:
        log(f"      ⛔ VERBATIM GATE: scene {scene_num} DROPPED {len(dropped)} script line(s) — "
            + "; ".join(f"\"{d[:44]}\"" for d in dropped[:5]) + " — RE-BREAK this scene (a line must never be lost).", flush=True)
    elif dups:
        log(f"      ⛔ VERBATIM GATE: scene {scene_num} has {len(dups)} DUPLICATED line(s) (a script line was likely "
            f"split across two cuts, misattributing content) — RE-BREAK this scene.", flush=True)
    else:
        log(f"      ✓ verbatim gate: scene {scene_num} — all {len(scene_dialogue)} lines present, 100% the writer's"
            + (f" ({fixed} snapped back)" if fixed else " (already exact)") + ".", flush=True)
    return beats, dropped, dups

def _force_include(beats, scene_dialogue, log=print):
    """LAST-RESORT MECHANICAL GUARANTEE — after retries, any script line STILL missing is appended verbatim as a new
    cut on the FINAL beat of the scene (never silently absent). This is a safety net, not the normal path: a scene
    should reach here only if the LLM dropped a line twice in a row. Returns the beats with the line(s) inserted."""
    if not beats:
        return beats
    have = {_norm_line(c.get("dialogue")) for b in beats for c in (b.get("cuts") or []) if (c.get("dialogue") or "").strip()}
    last = beats[-1]   # the scene's FINAL beat in creation order (NOT a string-max on beatCode — "3.B10" < "3.B9" alphabetically)
    for char, line, paren in scene_dialogue:
        if _norm_line(line) not in have:
            last.setdefault("cuts", []).append({
                "n": len(last.get("cuts") or []) + 1, "framing": "medium — the button", "action": "",
                "dialogue": f"{char}: {line}", "delivery": paren.strip("()") if paren else ""})
            have.add(_norm_line(line))
            # keep the beat internally consistent — a forced speaker MUST be in characters/speakers or downstream
            # reference-pulling (cb_prompts.py) never fetches their identity image for this beat's render.
            for _field in ("characters", "speakers"):
                lst = last.setdefault(_field, [])
                if char not in lst:
                    lst.append(char)
            log(f"      ⚑ FORCE-INCLUDED (mechanical, after retries) → {char}: \"{line[:52]}\" — appended to beat "
                f"{last.get('beatCode')} so the line is never lost. Review its staging.", flush=True)
    return beats

def scene_to_beats(system, script, beatmap, scene, theme, elements=None, retry_note=""):
    user = (
        (retry_note + "\n\n" if retry_note else "") +
        f"FULL SCRIPT for reference:\n\n{script}\n\n"
        f"THE LOCKED THEME — every beat serves this (Docter):\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"BEAT MAP (whole episode context):\n{json.dumps(beatmap.get('scenes'), ensure_ascii=False)}\n\n"
        f"CONTINUITY scaffold:\n{json.dumps(beatmap.get('continuity'), ensure_ascii=False)}\n\n"
        f"════════ TASK: STAGE B — design the BEATS for SCENE {scene['sceneNumber']} ('{scene['name']}') ONLY ════════\n"
        f"Scene emotional core: {scene.get('emotionalCore')}\n"
        f"Pillar: {scene.get('pillar')} | cast: {scene.get('cast')} | time/weather: {scene.get('time')}/{scene.get('weather')}\n\n"
        "════════ THE SCENE'S EXACT SCRIPT ELEMENTS — THE GROUND TRUTH (VERBATIM) ════════\n"
        "This is your ONLY source for WHAT happens and WHAT is said. BREAK IT DOWN into beats — never change it. Rules:\n"
        "  • Assign EVERY dialogue line below to a cut, IN THIS ORDER, WORD-FOR-WORD (a hard gate snaps any drift back, "
        "so match them exactly, keep the writer's parenthetical as the cut's delivery).\n"
        "  • COMPLETENESS IS ABSOLUTE: use each line EXACTLY ONCE — the TOTAL number of dialogue cuts across your beats "
        "must EQUAL the number of DIALOGUE lines listed below. NEVER drop a line (most often the LAST line of the scene, "
        "e.g. a final 'Thank you' or button), and NEVER repeat a line or a beat. Every listed line appears once; no more, no fewer.\n"
        "  • Each cut's ACTION must be FAITHFUL to these ACTION lines — stage exactly what the script describes; invent "
        "nothing, drop nothing, re-order nothing, add no character the script doesn't place here.\n"
        "  • Your TALENT is bringing this to life — the cinematography (camera, framing, shot rhythm), the 3D-CGI "
        "performance (weight, timing, the eyes), the show-bible world — layered ON TOP of these exact words and actions.\n"
        f"{_elements_block(elements)}\n\n"
        "THE UNIT IS THE BEAT = ONE Seedance TAKE, up to ~15s (director skill v5.0). A take is a CONTAINER of complete "
        "MOMENTS: it holds a WHOLE number of them — 1, 2, or 3 — each opening and closing, NEVER a fraction (no half "
        "moment, no 1.5). First judge the scene's screen time, then PACK its complete moments into the FEWEST takes of "
        "<=~15s (1-3 whole moments each: a ~10s scene = 1 take, ~33s = 2-3 takes). A take NEVER ends mid-moment. "
        "EVERY MOMENT — and so every take — OPENS AND CLOSES: it ENDS on a BUTTON (a landed comedic/emotional close, "
        "e.g. Fuzzby's 'Nailed it.'), NEVER on an OPEN the next must resolve (an unanswered question, an unfinished "
        "setup, a pending reaction). A tight exchange — question->answer, setup->payoff, action->reaction, joke->topper "
        "— lives ENTIRELY inside ONE moment, and the take's LAST moment is always closed; NEVER end a take on the "
        "question and open the next take with the answer. Fill up to ~15s, but always land the last moment on a button, "
        "keeping every exchange whole. Inside each beat write the INTERNAL CUT-LIST (2-4 cuts) that Seedance performs as one continuous take "
        '("Shot 1 (wide establishing, slow push-in) … Shot 2 (cut to a medium of FUZZBY) … Shot 3 (cut to a wide '
        'two-shot) …"). The 3x3 emotional functions (establish->hook->action->counter->insert->climax->REACTION-HOLD'
        "->exit) are the MENU of internal cuts to arrange ACROSS the scene's beats — minimum, across the whole scene: "
        "establish, hook, climax, reaction-hold, exit. Run the VISUAL + PERFORMANCE + PRODUCTION passes. Direct ACTING, "
        "not blocking. Small emotive motion per cut; static props HOLD (the heart register). "
        "COMEDY — the funny beats, ESPECIALLY FUZZBY the proud bumbler — GO OVER-THE-TOP: tag a gag beat "
        "comedyMode=BIG and run the GAG CLOCK (over-confident WIND-UP -> the BANG with mass -> the delayed TAKE / "
        "held beat -> the snap-back BUTTON), commit 110%, build the gag BACKWARDS from the bravado, rule-of-three "
        "then break it, end on a button; weight + heart survive at full size (laugh WITH, never AT). Tag a heart "
        "beat comedyMode=TRUE (small + real). NEVER blend BIG and TRUE in one beat.\n"
        "If KEEN makes a brave choice, a FEAR cut (trembling paws / swallowed gulp / flattened ears) MUST precede it "
        "within the beat — courage is SHOWN, never assumed. "
        "Pick ONE dominant COLOUR TEMPERATURE for the scene (amber=safety/love · saturated crystal-glow=wonder · "
        "cool blue-silver=fear/loneliness · rose-lavender=tenderness · grey-green=low ebb) — every beat inherits it. "
        "CRYSTAL WOODS is an emotional PARTICIPANT, never wallpaper (light/fog/terrain/crystals respond to the feeling). "
        "Plan the scene's ONE 'that's beautiful' beauty moment (beautyMoment:true on the beat that holds it). Track each "
        "bear's CRYSTAL GLOW as an emotional signal (brightening with courage/connection, dimming with fear/isolation).\n"
        "DIALOGUE IS LOCKED — this is a FINAL script. Use each line EXACTLY as written; NEVER cut, rewrite, paraphrase, "
        "soften, or invent dialogue, and do NOT 'fix' it for banned words. Attribute each line to its speaker inside the "
        "cut it lands on. Your job is to BREAK DOWN the script, not rewrite it. (Three Strikes / show-don't-tell is a "
        "\"writerNote\" flag for Julian only — the line STAYS verbatim.) A beat or cut with no line carries it "
        "wordlessly through staging + performance.\n\n"
        "Output JSON ONLY: { \"beats\": [ {\n"
        '  "slug": "kebab-id", "scene": "' + scene['name'] + '", "characters": [canon names in this beat/take],\n'
        '  "openingCast": [REQUIRED — the SUBSET of "characters" actually VISIBLE IN THE OPENING FRAME (what the single '
        'keyframe shows). A character who ENTERS LATER in the beat is listed in "characters" but NOT here, so their image '
        'reference is never fed into a frame they are not in (or the model paints them in). If everyone is present at the '
        'open, repeat the full list],\n'
        '  // CHARACTER-PRESENCE RULE (HARD): a character appears in a beat ONLY from the beat they FIRST ENTER the scene '
        'onward. Do NOT list a character in "characters"/"openingCast", and do NOT name them in "startState", "performance", '
        '"cuts" or ANY field, of a beat BEFORE they arrive. If a later beat shows a character ARRIVING (e.g. "glides up", '
        '"enters", "walks in"), every EARLIER beat is without them — naming an absent character pulls their reference and the '
        'model draws them into a frame they should not be in.\n'
        '  "speakers": [canon names who speak in this beat], "keenWristbands": "none"|"vacant"|"crystal" (per the arc; null if Keen absent),\n'
        '  "durationSec": int 8..15 (this take\'s length — long enough for its 1-2 WHOLE moments + the padding, never longer),\n'
        '  // PACING & DENSITY (HARD — beats were feeling RUSHED): speech runs ~2 words/second, so keep each beat\'s TOTAL '
        'dialogue to about 10 SECONDS — roughly 20 WORDS MAX across all its lines — and PAD it either side with a wordless '
        'wind-up (the lead-in) and a reaction/button HOLD (the take), so the pace feels right, never rushed and never draggy. '
        'A beat holds 1-2 WHOLE comic/emotional moments, NOT more. If a beat would carry MORE than ~10s/~20 words of dialogue, '
        'OR a SECOND distinct gag/moment (e.g. a spoken gag AND a separate physical crash), SPLIT it into another beat — '
        'dialogue is LOCKED verbatim, so you SPLIT to pace it, never trim. A setup and its payoff stay in the SAME beat (never '
        'split a gag across the cut). When in doubt, make another beat.\n'
        '  "pillar": str, "intensity": 0..1, "storyBeat": what happens across this 10-12s window,\n'
        '  "emotionalIntent": what the audience FEELS across the beat,\n'
        '  "want": what the bear PERFORMS/reaches for this beat (usually the avoidance), "need": the true thing underneath they resist — the gap is the performance,\n'
        '  "crystalTruth": what the crystal reveals that the FACE hides this beat (the crystal is the NEED, not the mood; it CONTRADICTS the face), with its read steady|flicker|dim|brightening|steady-warm-but-changed,\n'
        '  "kidRead": the surface the CHILD laughs at / sees, "adultRead": the truth the PARENT catches — SAME beat, same second (not parallel scenes),\n'
        '  "theGame": for an emotional beat, the invented GAME whose made-up rules ARE the emotional logic (play, never a lecture); null if none,\n'
        '  "wordlessHeld": true ONLY for the single nadir beat of the WHOLE EPISODE (zero dialogue, camera held longer than comfortable, the crystal+face carry the turn) — else false,\n'
        '  "comedyMode": "BIG" for a gag/funny beat (full over-the-top cartoon — the gag clock) or "TRUE" for a heart beat (small + real); tag it BEFORE staging, never blend the two; BIG beats build the gag backwards from the bravado (esp. Fuzzby) and end on a button,\n'
        '  "physicalFeeling": the SINGLE physical sensation the audience should FEEL IN THEIR BODY in the first ~2 seconds (felt, not seen — the lurch, the held breath, the warmth),\n'
        '  "light": how light ISOLATES that feeling moment, "atmosphere": how the air/particles BUILD toward it, '
        '"motionTempo": the motion tempo that LANDS on it, "grade": the colour grade that PRESERVES it after it passes,\n'
        '  "cuts": [ {"n": int, "framing": "shotSize + angle + movement (e.g. wide establishing, slow push-in)", '
        '"action": one clean physical action faithful to the script, "dialogue": "NAME: line" or null, '
        '"delivery": acting/cadence note for the line} ],   // 2-4 internal cuts IN ORDER; cut 1 is the opening,\n'
        '  "cameraArc": the through-line of the whole beat, "pacingVerbs": [specific physics verbs],\n'
        '  "pauseHold": where the beat goes still and for how long,\n'
        '  "performance": {"surface":str,"underneath":str,"innerThought":str},\n'
        '  "crystalGlow": which bear(s) + state (brightening|dimming|pulsing|steady), "beautyMoment": true|false,\n'
        '  "startState": the OPENING FRAME — the STATIC HELD pose at the very first frame of the beat: WHERE each '
        'character is and what they are doing (the BEFORE; positions + held action, e.g. "Fuzzby frame-left mid-hover '
        'eyes closed, Zenny frame-right watching"; NO motion words), so the ONE opening keyframe is drawn from it,\n'
        '  "keyframePrompt": self-contained t2i for the OPENING frame — the locked render STYLE, then "as per the '
        'reference image of [BEAR]" for each character (NEVER describe a bear), the scene plate as reference, '
        'framing/lens/lighting, 2-3 ambient crystals; the START of the action, never the aftermath,\n'
        '  "i2vPrompt": the SEEDANCE BEAT prompt (ONE 10-12s take) — open "Anchor Image is TRUTH. COPY EXACTLY." then '
        '"Multi-shot sequence with clean cuts between shots." then each internal cut IN ORDER ("Shot 1 (framing): '
        'action … Shot 2 (cut to …): action, NAME: \\"line\\" … Shot 3 (cut to …): action …"), dialogue written IN for '
        'lip-sync, ending Style+Audio (3D CGI Pixar; Seedance scores the SFX + timed comedy/emotional music ON the action; '
        'voice forward; bear note Hz). Small emotive motion per cut; static props HOLD,\n'
        '  "soundIntent": the SFX + timed-music cues Seedance should score (the bonk on the tree, the button on the deflate); the bear\'s note where it lands,\n'
        '  "continuity": {"opensFrom": how this beat\'s opening frame hands off the previous beat\'s last frame, '
        '"carryToNext": what carries forward, "screenDirection": "LEFT"|"RIGHT" (locked at scene open)},\n'
        '  "check": {"focalSubject":str,"emotionalRead":what they should FEEL,"heartCheck":"what the CHILD feels AND '
        'what the PARENT feels at this beat"}\n'
        "} ] }\n\n"
        "Stage two-handers in locked positions (Fuzzby BIGGER frame-LEFT, Zenny SMALLER frame-RIGHT) and attribute each "
        "line. Sizes per the chart (Amie<Sunny<Luna≈Keen≈Aida<Misty<Howey). Order beats in scene order."
    )
    return [b.model_dump(by_alias=True) for b in
            cb_llm.structured(system, user, S.SceneBeats, label=f"scene_to_beats s{scene['sceneNumber']}").beats]

# ── THE "BRAINTRUST" REMAKE PASS IS REMOVED (2026-07-01). It re-staged the scene and drifted the writer's dialogue
#    ("we don't make movies, we remake them"). The Director is a FAITHFUL ADAPTER (§0): it brings the signed-off script
#    to life, it never remakes it. Nothing calls braintrust; the function and its prompt are gone. ──

# ── DERIVE THE SCENE SHOT FROM THE SCENE'S OUTCOME (the empty stage the actual shots need) ──
# The plate is NOT a standalone location line — it is composed by READING everything that physically
# happens across the scene's shots, so the empty stage always contains exactly what the action needs.
def derive_plate(system, scene, beats, theme):
    digest = [{"beat": s.get("beatCode"), "storyBeat": s.get("storyBeat"),
               "cuts": [c.get("action") for c in (s.get("cuts") or [])],
               "characters": s.get("characters"), "startState": s.get("startState")} for s in beats]
    user = (
        f"THE LOCKED THEME:\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"SCENE {scene['sceneNumber']} '{scene['name']}' — emotional core: {scene.get('emotionalCore')}. "
        f"Time/weather: {scene.get('time')}/{scene.get('weather')}.\n"
        f"EVERYTHING THAT PHYSICALLY HAPPENS IN THIS SCENE (every beat):\n{json.dumps(digest, ensure_ascii=False)}\n\n"
        "════════ TASK: DERIVE THE SCENE SHOT (the empty establishing PLATE) FROM THE SCENE'S OUTCOME ════════\n"
        "Read the OUTCOME of the scene — everything the characters DO, and every set element the action requires, "
        "across ALL these beats — then compose the SINGLE EMPTY STAGE that all of it plays on. The plate MUST contain "
        "every physical element the action needs, and let it DOMINATE the frame as the action demands (e.g. if the "
        "characters fly INTO tall pollen-flowers, the stage is FILLED with tall pollen-flowers). Staged, framed and lit "
        "for the scene's feeling; NOTHING extraneous; NO characters. Output JSON ONLY:\n"
        "{\n"
        '  "sceneShotName": a SHORT, DESCRIPTIVE name for this scene shot that says exactly what it depicts — the '
        'place + its defining character/look + the framing (e.g. "Rainforest — sunlit flower clearing, bee\'s-eye '
        'wide"; "Crystal Cove pier — dawn, boat moored"; "Open sea — storm, towering waves"). Specific enough to '
        'find and reference in the library later; the name MUST match what the plate actually shows,\n'
        '  "location": the geography/space backbone — one rich line, the physical place the action needs,\n'
        '  "look": the directed EMPTY PLATE — what DOMINATES the frame, the layout & screen-direction, the set pieces '
        'the action requires, the mood and light; explicit about what is there for the action; NO characters, and NO '
        "objects the action does not need,\n"
        '  "definingFeature": the ONE feature the establishing frame is built around — the thing that makes this place '
        'unmistakably itself (e.g. "a single colossal sun-backlit pollen-flower", "the crystal-veined cove wall"),\n'
        '  "colorTemperature": the scene\'s ONE dominant colour temperature as a short motivated phrase tied to the '
        'feeling (amber warm safety / saturated crystal-glow wonder / cool blue-silver fear / rose-lavender tenderness '
        '/ grey-green low-ebb), matching the emotional core,\n'
        '  "lens": the establishing lens choice (e.g. "wide bee\'s-eye 18mm", "medium 35mm", "wide anamorphic"),\n'
        '  "cameraHeight": the camera height/angle for the plate (e.g. "low bee\'s-eye looking up", "eye-level", '
        '"slightly high looking down")\n'
        "}\n"
        "Pick the colorTemperature, lens and cameraHeight from the scene's emotional core and what the action needs — "
        "these are inherited by every shot in the scene."
    )
    return cb_llm.structured(system, user, S.Plate, label=f"derive_plate s{scene['sceneNumber']}").model_dump(by_alias=True)

# ── VALIDATE — validate_scene_beats (rules 5-7): Pydantic + business rules, ONE repair, STOP + report ──────────
class SceneBreakdownError(Exception):
    """A scene's beats could not be made valid even after one repair — direct() STOPS and reports this scene."""
    def __init__(self, scene_number, scene_name, detail):
        self.scene_number, self.scene_name, self.detail = scene_number, scene_name, detail
        super().__init__(f"scene {scene_number} ('{scene_name}'): {detail}")

def validate_scene_beats(system, script, beatmap, scene, theme, beats, log=print):
    """Re-validate ONE scene's beats: the strict Pydantic schema (already enforced by the structured call) PLUS
    business rules (cast/openingCast/speakers consistency, cuts present, durationSec 8..15, valid comedyMode).
    Soft PACING issues are reported only (dialogue is LOCKED — the fix is a SPLIT, not a trim). On a HARD problem,
    run exactly ONE repair call seeded with the precise errors; if it is STILL invalid, raise SceneBreakdownError
    so direct() stops and reports the exact scene (rule 7)."""
    for w in S.pacing_warnings(beats):
        log(f"      ⚠ PACING {w}", flush=True)
    problems = S.beat_problems(beats, scene)
    if not problems:
        return beats
    log(f"      validate: scene {scene['sceneNumber']} has {len(problems)} issue(s) — ONE repair call…", flush=True)
    for p in problems[:6]:
        log(f"        • {p}", flush=True)
    context_user = (
        f"FULL SCRIPT for reference:\n\n{script}\n\n"
        f"THE LOCKED THEME:\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"BEAT MAP (episode context):\n{json.dumps(beatmap.get('scenes'), ensure_ascii=False)}\n\n"
        f"SCENE {scene['sceneNumber']} ('{scene['name']}') cast: {scene.get('cast')}\n\n"
        f"These DRAFT beats need fixing — keep EVERY locked dialogue line verbatim, change only the named "
        f"structural problems:\n{json.dumps(beats, ensure_ascii=False)}"
    )
    try:
        fixed = [b.model_dump(by_alias=True) for b in
                 cb_llm.repair_call(system, context_user, S.SceneBeats, problems,
                                    label=f"validate s{scene['sceneNumber']}", log=log).beats]
    except Exception as e:
        raise SceneBreakdownError(scene["sceneNumber"], scene.get("name", ""), f"repair call errored — {str(e)[:160]}")
    for i, b in enumerate(fixed, 1):   # re-tag the repaired beats so re-validation + downstream stay consistent
        b["sceneNumber"] = scene["sceneNumber"]
        b["beatCode"] = f"{scene['sceneNumber']}.B{i}"
        b.setdefault("scene", scene["name"])
    still = S.beat_problems(fixed, scene)
    if still:
        raise SceneBreakdownError(scene["sceneNumber"], scene.get("name", ""),
                                  "still invalid after one repair: " + "; ".join(still[:4]))
    log(f"      validate: scene {scene['sceneNumber']} repaired ✓", flush=True)
    return fixed

# ── Stage C — ASSEMBLE + WRITE ───────────────────────────────────────────────
def _slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "Untitled"

def direct(script_path, episode, title, log=print):
    system, chars = _mind()
    script = pathlib.Path(script_path).read_text()
    # FAITHFUL GROUND TRUTH — parse the screenplay DETERMINISTICALLY; every scene's breakdown is anchored to, and its
    # dialogue hard-gated against, these verbatim elements. The Director brings the script to life; it never changes it.
    _pmap = {}
    try:
        for _ps in cb_script.parse(script, _script_roster(), warn=lambda m: log(f"  ⚠ PARSE: {m}", flush=True)):
            _pmap[_ps["sceneNumber"]] = _ps
        _nl = sum(1 for ps in _pmap.values() for e in ps["elements"] if e["type"] == "dialogue")
        log(f"  PARSED the screenplay (verbatim): {len(_pmap)} scenes, {_nl} dialogue lines — the locked ground truth.", flush=True)
    except Exception as _pe:
        log(f"  ⚠ script parse failed ({str(_pe)[:90]}) — the verbatim gate is limited this run.", flush=True)
    log(f"DIRECTOR — breaking down '{title}' ({episode}) on {cb_llm.DIRECTOR_MODEL} "
        f"(OpenAI; validator {cb_llm.VALIDATOR_MODEL}; fallback Gemini {cb_llm.GEMINI_MODEL})", flush=True)

    log("  Stage 0 — OPENING DECLARATION + THEME (Docter: what is this REALLY about?)...", flush=True)
    theme = theme_lock(system, script, episode, title)
    log("  DECLARATION: " + (theme.get('declaration') or '')[:420], flush=True)
    log(f"  THEME: {theme.get('theme')}", flush=True)
    log(f"  SEL: {theme.get('selCompetency')}  |  trap to avoid: {(theme.get('pressureTest') or '')[:110]}", flush=True)

    log("  Stage A — beat map (Five Pillars, scenes, emotional cores, continuity)...", flush=True)
    bm = episode_to_scenes(system, script, episode, title, theme)
    scenes = sorted(bm["scenes"], key=lambda s: s["sceneNumber"])
    log(f"  beat map: {len(scenes)} scenes — " + " | ".join(f"{s['sceneNumber']}:{s['name']}({s['pillar']})" for s in scenes), flush=True)

    # SCENE-NUMBER RECONCILIATION — the LLM's Stage-A scene numbers and the DETERMINISTIC parser's own scene numbers
    # (_pmap) are two independently-produced numbering schemes; scene_to_beats looks up _pmap BY the LLM's number
    # (below). If they ever disagree, that lookup silently returns {} -> _scene_dialogue=[] -> the whole verbatim
    # gate is SKIPPED for that scene with zero warning. Reconcile loudly, once, up front — never silently.
    _llm_nums = {s["sceneNumber"] for s in scenes}
    _parsed_nums = set(_pmap.keys())
    if _llm_nums != _parsed_nums:
        log(f"  ⛔⛔ SCENE-NUMBER MISMATCH: the Director's scene numbers {sorted(_llm_nums)} do not match the "
            f"screenplay parser's scene numbers {sorted(_parsed_nums)} — every scene in the difference will have "
            f"NO verbatim dialogue protection (the hard gate silently no-ops when it can't find a matching parsed "
            f"scene). Re-fire Gate 1, or check the script's scene headings are all numbered.", flush=True)

    all_beats, sid = [], 1
    _force_included_all = []          # scenes where a line only made it in via the mechanical safety net (flag for staging review)
    _dup_unresolved_all = []          # scenes where a duplicated/misattributed line survived 2 retries (needs a human re-break)
    try:
        for sc in scenes:
            log(f"  Stage B — scene_to_beats: scene {sc['sceneNumber']} '{sc['name']}'...", flush=True)
            _pe = _pmap.get(sc["sceneNumber"], {})
            _elems = _pe.get("elements", [])
            _scene_dialogue = [(e["character"], e["line"], e.get("parenthetical", "")) for e in _elems if e["type"] == "dialogue"]

            def _draft_and_gate(retry_note=""):
                _beats = None
                for attempt in (1, 2):
                    try:
                        _beats = scene_to_beats(system, script, bm, sc, theme, _elems, retry_note=retry_note); break
                    except Exception as e:
                        log(f"      ⚠ scene {sc['sceneNumber']} attempt {attempt} failed ({str(e)[:90]})"
                            + ("" if attempt == 2 else " — retrying..."), flush=True)
                if not _beats:
                    raise SceneBreakdownError(sc["sceneNumber"], sc["name"], "scene_to_beats returned no beats after 2 attempts")
                # NO "REMAKE" PASS — the Director is a FAITHFUL ADAPTER, not a co-writer. The old braintrust ("we remake our
                # movies") re-staged the scene and drifted the dialogue; it is removed. The script is signed off; we bring it
                # to life, we do not remake it.
                for i, s in enumerate(_beats, 1):           # tag beatCode BEFORE validation so its reports + downstream use the real codes
                    s["sceneNumber"] = sc["sceneNumber"]
                    s["beatCode"] = f"{sc['sceneNumber']}.B{i}"
                    s.setdefault("scene", sc["name"])
                _beats = validate_scene_beats(system, script, bm, sc, theme, _beats, log=log)   # rules 5-7: Pydantic + business rules
                _drop, _dup = [], []
                if _scene_dialogue:                          # HARD VERBATIM GATE — snap every line back to the writer's EXACT words
                    _beats, _drop, _dup = enforce_verbatim(_beats, _scene_dialogue, sc["sceneNumber"], log=log)
                return _beats, _drop, _dup

            def _missing_tuples(normalized_targets):
                # matches BOTH dropped script lines AND duplicated/misattributed normalized lines back to their
                # original (char, line, paren) tuples — enforce_verbatim's `dropped`/`dups` are both already
                # comparable via _norm_line, so one helper serves both.
                dn = {_norm_line(d) for d in normalized_targets}
                return [(c, l, p) for (c, l, p) in _scene_dialogue if _norm_line(l) in dn]

            beats, dropped, dups = _draft_and_gate()
            log(f"      first draft: {len(beats)} beats", flush=True)
            # COMPLETENESS + CORRECTNESS RETRY — the LLM's two most common failures: dropping a scene's LAST
            # line/button, and SPLITTING one script line across two cuts (which shows up as a DUPLICATE, not a drop —
            # the split-off half still exists as its own duplicated normalized line). Retry on EITHER, since a dup is
            # just as broken as a drop (content misattributed to the wrong cut), not a mere cosmetic repeat.
            _retry_n = 0
            while (dropped or dups) and _retry_n < 2:
                _retry_n += 1
                miss = _missing_tuples(dropped)
                dupmiss = _missing_tuples(dups)
                parts = []
                if miss:
                    parts.append("DROPPED the following line(s), which MUST appear EXACTLY as a dialogue cut (often "
                                  "the scene's LAST line/button, easy to lose at the tail): "
                                  + "; ".join(f'{c}: "{l}"' for c, l, _p in miss))
                if dupmiss:
                    parts.append("SPLIT/DUPLICATED the following line(s) across more than one cut — each script line "
                                  "must appear EXACTLY ONCE, as ONE complete cut, never divided across two: "
                                  + "; ".join(f'{c}: "{l}"' for c, l, _p in dupmiss))
                note = "CRITICAL FIX — your PREVIOUS breakdown of this scene " + "; and also ".join(parts) + \
                       ". Re-do the FULL beat breakdown for this scene — keep every other line exactly as before, and fix this. Do not repeat the mistake."
                log(f"      ↻ retry {_retry_n}/2 — re-breaking scene {sc['sceneNumber']} to recover {len(miss)} dropped "
                    f"+ fix {len(dupmiss)} duplicated line(s)...", flush=True)
                beats, dropped, dups = _draft_and_gate(retry_note=note)
            if dropped:
                # LAST RESORT — the LLM dropped this line even after 2 targeted retries. Insert it verbatim, mechanically,
                # so the package can NEVER ship missing a written line. Flagged for a staging review (below), never silent.
                miss = _missing_tuples(dropped)
                beats = _force_include(beats, miss, log=log)
                _force_included_all.append((sc["sceneNumber"], [l for _c, l, _p in miss]))
            if dups:
                # a DUPLICATE cannot be mechanically repaired the way a drop can (the content exists, just on the
                # wrong cut(s)) — this is a genuine breakdown fault that survived 2 retries. Flag it loudly rather
                # than silently shipping a scene with misattributed dialogue.
                log(f"      ⛔⛔ scene {sc['sceneNumber']} STILL has {len(dups)} duplicated/misattributed line(s) after "
                    f"2 retries — ship with caution; a human must review this scene's cuts by hand.", flush=True)
                _dup_unresolved_all.append((sc["sceneNumber"], dups))
            for s in beats:                      # assign the global running id to the FINAL (possibly repaired) beats
                s["id"] = sid; sid += 1
            # DERIVE the scene shot (plate) from what ACTUALLY happens in the scene — overrides the beat-map's
            # standalone location so the empty stage always contains exactly what the action needs.
            try:
                dp = derive_plate(system, sc, beats, theme)
                if dp.get("location"): sc["location"] = dp["location"]
                if dp.get("look"): sc["look"] = dp["look"]
                if dp.get("sceneShotName"): sc["sceneShotName"] = dp["sceneShotName"]
                if dp.get("definingFeature"): sc["definingFeature"] = dp["definingFeature"]
                if dp.get("colorTemperature"): sc["colorTemperature"] = dp["colorTemperature"]
                if dp.get("lens"): sc["lens"] = dp["lens"]
                if dp.get("cameraHeight"): sc["cameraHeight"] = dp["cameraHeight"]
                log(f"      scene shot DERIVED: \"{sc.get('sceneShotName','')}\" ✓", flush=True)
            except Exception as e:
                log(f"      ⚠ derive_plate skipped ({str(e)[:60]}) — kept the beat-map location", flush=True)
            log(f"      -> {len(beats)} beats", flush=True)
            all_beats += beats
    except SceneBreakdownError as e:
        log(f"  ✗✗ STOP — Gate 1 HALTED at scene {e.scene_number} ('{e.scene_name}'): {e.detail}", flush=True)
        log("  No beat package written. Earlier scenes were fine — fix this scene's breakdown, then re-fire Gate 1.", flush=True)
        raise

    # ── FLOW CHECK (Julian's beat-self-containment law): warn where a beat ENDS on an OPEN the next beat resolves,
    #    so a question->answer / setup->payoff isn't split across the cut. Heuristic: the beat's last spoken line is a
    #    question and the next beat opens with dialogue (likely the answer).
    _bysc = {}
    for _b in all_beats:
        _bysc.setdefault(_b.get("sceneNumber"), []).append(_b)
    _flow = 0
    for _sn, _bs in _bysc.items():
        # `_bs` is ALREADY in creation order (appended from `all_beats`, itself built beat-by-beat in order) — do
        # NOT sort by the beatCode STRING: "3.B10" < "3.B9" lexicographically would silently reorder a 10+-beat
        # scene and produce false/missed "ends on an open question" warnings. Same class of bug as enforce_verbatim.
        for _i in range(len(_bs) - 1):
            _last = [c for c in (_bs[_i].get("cuts") or []) if (c.get("dialogue") or "").strip()]
            _nextd = [c for c in (_bs[_i + 1].get("cuts") or []) if (c.get("dialogue") or "").strip()]
            if _last and _nextd and (_last[-1].get("dialogue") or "").rstrip().rstrip('"””').endswith("?"):
                _flow += 1
                log(f"  ⚠ FLOW: beat {_bs[_i].get('beatCode')} ENDS on an open question "
                    f"(\"{(_last[-1].get('dialogue') or '')[:46]}…\") that beat {_bs[_i + 1].get('beatCode')} answers — "
                    f"close it on a button; keep the exchange in one beat (Julian's law).", flush=True)
    if _flow:
        log(f"  ⚠ {_flow} beat(s) end on an OPEN — keep each exchange inside one beat (re-fire Gate 1, or shift the line).", flush=True)

    # VERBATIM COMPLETENESS SUMMARY — every script line is now GUARANTEED present (retried, then mechanically inserted
    # as a last resort) — this can never report a drop. It flags only whether any line needed the mechanical safety
    # net, so Julian can sanity-check that beat's staging (the line is there; how naturally it's woven in may vary).
    if _force_included_all:
        _tot = sum(len(v) for _s, v in _force_included_all)
        log(f"  ⚑⚑ VERBATIM COMPLETENESS: every line is present, but {_tot} line(s) across {len(_force_included_all)} "
            f"scene(s) needed a MECHANICAL force-include after 2 retries (the model kept dropping them) — "
            + "; ".join(f"scene {s}: " + ", ".join(f'\"{d[:36]}\"' for d in v[:3]) for s, v in _force_included_all)
            + ". Please review these beats' staging — the line is guaranteed to be there, but check it lands naturally.", flush=True)
    else:
        log(f"  ✓✓ VERBATIM COMPLETENESS: every one of the script's dialogue lines is present, cleanly (first draft or a targeted retry).", flush=True)
    if _dup_unresolved_all:
        _dtot = sum(len(v) for _s, v in _dup_unresolved_all)
        log(f"  ⛔⛔ VERBATIM CORRECTNESS: {_dtot} duplicated/misattributed line(s) across {len(_dup_unresolved_all)} "
            f"scene(s) survived 2 retries UNRESOLVED (the model kept splitting a script line across two cuts) — "
            + "; ".join(f"scene {s}" for s, _v in _dup_unresolved_all)
            + ". These lines were NOT force-included (they're not missing, just misattributed) — re-break these "
            "scenes by hand before sign-off.", flush=True)

    # shot package
    pkg = {
        "title": bm.get("title", title), "episode": int(re.sub(r"\D", "", episode) or 0),
        "logline": bm.get("logline", ""), "ip": "The Crystal Bears",
        "declaration": theme.get("declaration", ""), "theme": theme,
        "leadBear": bm.get("leadBear", ""), "engine": bm.get("engine", ""),
        "format": bm.get("format", ""), "continuity": "see config/continuity.json",
        "unit": "beat", "beatRule": "one 10-12s Seedance take per beat — the beat directs its own internal cuts (director skill v5.0)",
        "_note": f"Authored by cb_director (Gate 1, BEAT-NATIVE) from the script — {len(all_beats)} beats, {len(scenes)} scenes.",
        "style": STYLE, "scenes": scenes, "beats": all_beats,
    }
    OUT.mkdir(exist_ok=True)
    pkg_path = OUT / f"{episode}_{_slug(title)}_beat_package.json"
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)

    # locations.json — MERGE into the existing per-episode dict; never rebuild the whole file. These configs are
    # shared, multi-episode registries (config/locations.json holds one entry PER episode) — overwriting the whole
    # dict here would silently DELETE every other episode's location plates/master paths the moment Gate 1 runs for
    # just one episode. Only this episode's own key is ever replaced.
    locp = HERE / "config" / "locations.json"
    L = json.load(open(locp)) if locp.exists() else {}
    L.setdefault("_note", "")
    L[episode] = {}
    for sc in scenes:
        L[episode][str(sc["sceneNumber"])] = {
            "name": sc["name"], "locationId": sc.get("locationId", ""),
            "sceneShotName": sc.get("sceneShotName", ""), "master": None,
            "time": sc.get("time", ""), "weather": sc.get("weather", ""),
            "location": sc.get("location", ""), "look": sc.get("look", ""),
            "lighting": sc.get("lighting", ""),
            "definingFeature": sc.get("definingFeature", ""),
            "colorTemperature": sc.get("colorTemperature", ""),
            "lens": sc.get("lens", ""),
            "cameraHeight": sc.get("cameraHeight", ""),
        }
    json.dump(L, open(locp, "w"), indent=1, ensure_ascii=False)

    # continuity.json — same MERGE rule: keep every other episode's visions/recurring/persistent/lost/items/worldState.
    conp = HERE / "config" / "continuity.json"
    C = json.load(open(conp)) if conp.exists() else {}
    C.setdefault("_note", "")
    C[episode] = bm.get("continuity", {})
    json.dump(C, open(conp, "w"), indent=1, ensure_ascii=False)

    # episode_arc.json — same MERGE rule, AND properly nested by episode (this file previously had NO per-episode
    # key at all — it unconditionally overwrote the entire file's content with just the current episode's arc,
    # permanently losing every other episode's arc data on every Gate-1 run).
    arcp = HERE / "config" / "episode_arc.json"
    A = json.load(open(arcp)) if arcp.exists() else {}
    A.setdefault("_note", "")
    arc = bm.get("arc", {}); arc.setdefault("episode", episode); arc.setdefault("title", title)
    A[episode] = arc
    json.dump(A, open(arcp, "w"), indent=1, ensure_ascii=False)

    log(f"  ✓ wrote {pkg_path.name} (BEAT PACKAGE) + locations + continuity + episode_arc", flush=True)

    # GATE 1.5 — DIRECTOR'S EYE, automatic (Julian: "no mention of the Pixar director / checked against the show
    # bible" — this was previously a SEPARATE manual pass a human had to remember to fire; it now runs as part of
    # Gate 1 itself). Judges every beat against the show bible AND the same four Pixar masters (Docter/Lasseter/
    # Lin/Kalache) that wrote it. Report-only — never blocks or mutates the package; a genuine LLM/network failure
    # here must never take down an otherwise-successful Gate 1, so it's caught and logged, not raised.
    log("  Stage C — DIRECTOR'S EYE (Gate 1.5: bible + Pixar-craft review)...", flush=True)
    try:
        import cb_director_eye
        cb_director_eye.run(str(pkg_path), episode)
    except Exception as e:
        log(f"  ⚠ Director's Eye skipped ({str(e)[:120]}) — review manually before signing off Gate 1.", flush=True)

    return {"package": str(pkg_path), "scenes": len(scenes), "beats": len(all_beats)}

if __name__ == "__main__":
    os.chdir(HERE)
    if len(sys.argv) < 4:
        sys.exit('usage: python3 cb_director.py <script.txt> <Ep> "<Title>"')
    r = direct(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(r, indent=1))
