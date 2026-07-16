#!/usr/bin/env python3
"""cb_director.py — THE DIRECTOR (the real Gate 1).

World-class SCRIPT BREAKDOWN / script analysis: reads a screenplay and breaks it into a
production-ready SHOT PACKAGE + locations + continuity + episode arc, directed as Pete Docter
(find the feeling and the why first) — the ONE voice who makes the call, per
CRYSTAL_BEARS_STUDIO_BIBLE.md's own Law 1 ("one mind per chair, never a committee"). John
Lasseter (story/character), Patrick Lin (camera) and Jean-Claude Kalache (light) are his named
department heads, executing HIS vision in their craft, never competing voices of their own.
The craft doctrine (the sixteen staging laws, the worked examples, the crew framing) is
hand-authored directly in `_mind()` below and kept current through this project's own iteration
— NOT read from `skills/crystal-bears-director/SKILL.md` at runtime (RETIRED 2026-07-14: that
file was found to be frozen at an early snapshot of the project — it still specified 10-12s
beats and the retired FRAME CHAIN mechanism, directly contradicting the live Handle Doctrine
(15s, rule 20) and the relay/junctionType system (rules 21/31) that superseded it. `_mind()`'s
own text already independently covered everything of value the skill file supplied — this
removes a source of silent, load-bearing contradiction rather than trying to repair a document
nobody edits anymore. The locked canon IS still read at runtime, from the real config store.

The director's own process, staged for reliability (BEAT-NATIVE — director skill v5.0):
  A. BEAT MAP   — script + bible -> scenes (plate look, cast, Pillar, time/weather/light,
                  the emotional core) + episode arc + continuity scaffold.
  B. BEATS      — per scene, design the 2-4 BEATS the story needs. A BEAT = ONE 15s Seedance take
                  (13s action + a 2s directed settle, the Handle Doctrine, rule 20 — corrected
                  2026-07-14, this line's own "10-12s" was the identical staleness rule 307
                  already fixed in `_mind()`) that directs its OWN internal cuts (NOT a string of
                  tiny shots). Each beat = one opening keyframe/relay anchor + an internal cut-list.
  C. ASSEMBLE   — write the BEAT PACKAGE (beats[]) + locations.json + continuity.json + episode_arc.json,
                  exactly the schema the pipeline consumes. Gate 1 then displays it for sign-off.

THE GATE-0 PROVENANCE HARD BLOCK (2026-07-14, Julian: "hard block if the input script has no
record of having passed through Gate 0's own Writer process — no belowBar field, no lock"):
`direct()` refuses outright, before spending a single token, if the script it's about to break
down has no matching `{stem}.score.json` sidecar next to it (cb_writer.write()'s own Gate-0
deliverable, always written alongside its script, always carrying a `belowBar` key) — a script
pasted/uploaded straight into the Studio (`cb-studio/serve.py`'s own `/api/episode` handler
explicitly deletes any such sidecar on upload, precisely because "an uploaded script carries no
Writers'-Room scorecard") never gets a free pass into Gate 1. A below-bar SCORE does not block —
cb_writer's own "written anyway so Gate 1 isn't blocked" design is unchanged; this is a
PROVENANCE gate, not a quality one. Ep1's own founding script predates the automated Writers'
Room and was hand-locked and hand-reviewed long before this mechanism existed, then carried
through a full, extensively produced Gate 1-5 pipeline — a real, verifiable provenance far
stronger than an automated scorecard; it is grandfathered with a hand-authored sidecar recording
that true history (`Ep1_The_Adventure_Begins.score.json`), not a fabricated LLM score.

    python3 cb_director.py <script.txt> <Ep> "<Title>"     # break a script down
"""
import os, sys, json, re, pathlib
import cb_llm, cb_director_schemas as S  # cb_gen removed 2026-07-11 (full-codebase audit, dead-code): unused
import cb_script                              # deterministic screenplay parser — the verbatim ground truth (Gate 1)
import paths as P                             # T30 Phase 2/3 — the single source of path constants

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT  = pathlib.Path(P.OUTPUT)

# bible — the single source of truth (read, never paraphrased from memory). RETIRED 2026-07-14: this module
# used to also read skills/crystal-bears-director/SKILL.md and skills/crystal-bears-cinematographer/SKILL.md
# at runtime and concatenate them into the live system prompt — removed (see the module docstring above) once
# both were confirmed frozen at an early project snapshot, actively contradicting the Handle Doctrine and the
# relay/junctionType system that _mind() below already correctly, independently states.
CANON = pathlib.Path(P.CANON)
CHARS = pathlib.Path(P.CHARS)

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
    # FIXED 2026-07-11 (full-codebase audit, duplication finding): the sort itself now lives once in
    # paths.char_size_order (see its own docstring for the null-safe-sizeRank rationale) — cb_writer.py's own
    # _roster shared this exact block byte-for-byte before this fix.
    order = P.char_size_order(chars)
    lines = []
    for k in order:
        c = chars[k]
        lex = c.get("lexicon") or {}
        lex_note = ""
        if lex.get("verbs") or lex.get("banned"):
            lex_note = (f" | LEXICON: write his/her action and any camera covering him/her using verbs like "
                        f"{', '.join(lex.get('verbs') or [])} — NEVER {', '.join(lex.get('banned') or []) or '(none)'}")
        lines.append(f"  - {k}: {c.get('size','')} | {c.get('cadence','')}"
                     + (f" | ACTING: {c['actingNote']}" if c.get('actingNote') else "")
                     + lex_note)
    return "\n".join(lines)

def _mode_archetype_menu():
    """THE DIRECTOR'S OWN MENU (2026-07-14, restoring the named-auteur-per-chair doctrine —
    CRYSTAL_BEARS_STUDIO_BIBLE.md Law 1, "one mind per chair, never a committee"): director_mode and
    physical_action_archetype used to be inferred mechanically at Gate 3 (cb_seedance.infer_director_mode /
    infer_physical_archetype), AFTER the beat's prose was already written — a classifier guessing at a choice
    nobody actually made. Both resolvers already check for an authored value FIRST, before falling back to
    inference (unchanged, still the safety net for a beat that leaves either null) — so handing the Director
    the real menu here, at the point the beat is invented, turns it into his actual creative decision instead
    of a guess made later from his own words. Reads the SAME two dicts cb_seedance.py's resolvers read — a
    single source of truth, never a second copy that could drift out of sync — via a lazy import (matching
    this module's own convention of never importing cb_seedance at module load time)."""
    import cb_seedance as SD
    modes = "; ".join(f'{k} ({v["feeling"]})' for k, v in SD.DIRECTOR_MODE_GUIDANCE.items())
    archs = "; ".join(f'{k} — {v["visual_payoff_rule"]}' for k, v in SD.PHYSICAL_ARCHETYPES.items())
    return modes, archs

def _mind():
    # FIXED 2026-07-12 (loose-ends pass): canon+chars reading was hand-duplicated here, in cb_writer.py's
    # own _gen(), and in cb_director_eye.py's _show_bible() — now paths.load_show_bible() (P is already the
    # `paths` module import at this module's own top level).
    canon, chars = P.load_show_bible()
    system = (
        "YOU ARE PETE DOCTER, directing Crystal Bears — an Oscar-calibre animation director doing world-class "
        "SCRIPT BREAKDOWN. This is YOUR call, alone. You lead with the FEELING; the emotion is the architecture. "
        "Start from the human truth, not the plot: name what each scene is REALLY about in one honest sentence "
        "and let it govern every shot (plot serves feeling, never the reverse). Track the hidden inner NEED "
        "beneath the outward want — the arc is emotional. Hold the BITTERSWEET — joy and ache together; never "
        "resolve the ache away. Carry the most important feelings WORDLESSLY (the held beat, the face, the "
        "look, the small gesture). Specific, observed, true — never generic.\n\n"
        "════════ THE SIXTEEN STAGING LAWS (Julian, dictated 2 July 2026, law 13 added 2026-07-05, law 14 added "
        "2026-07-06 — SCENE1_DIRECTORS_CUT.md; laws 15-16 added 2026-07-13 — the Motion Contract + the Shot "
        "Budget; HARD RULES, cannot be softened) ════════\n"
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
        "choreographed, nameable, and lands somewhere.\n"
        "14. THE CHARACTER VOCABULARY LAW (Julian, 2026-07-06 — enforced HERE, at the point the script becomes the "
        "storyboard, not patched afterward). Every verb and adverb in every cut's `framing` and `action` text — "
        "camera and character alike — is drawn from THAT character's own locked LEXICON (given per character in "
        "the CAST LOCK below): the verbs listed are what they (and any camera covering them) do; the banned words "
        "listed must NEVER appear in a cut naming them, even in passing, even softened as an aside. The camera "
        "inherits the register of whoever it is covering IN THAT CUT — a wingman-chase for a manic lead, a locked "
        "hold for a deadpan foil — never a generic, softened, or borrowed-register camera note. Readability is "
        "earned by being SPECIFIC (a named move, a named gag), never by softening the verb. A single beat NEVER "
        "mixes one character's registers into another's cut: if Fuzzby is chaotic in cut 1, cut 2 does not "
        "describe him or his camera as steady/gentle/calm just because the shot itself is calmer in pace — find "
        "the word from HIS list that means what you mean (banks, snaps, locks-on-the-crash), never reach for a "
        "word from someone else's register because it happens to read smoother.\n"
        "15. THE MOTION CONTRACT — ONE CAUSE, CHAINED CONSEQUENCES, NEVER A VERB CHECKLIST (2026-07-13, the "
        "CapCut-formula deep-dive — mined directly from this project's own Seedance-20 doctrine, "
        "skills/seedance-motion/SKILL.md): a real structural diff of tonight's own best and worst takes on the "
        "identical beat found the single sharpest difference wasn't length or references, it was this. Write an "
        "impact/action beat as ONE cause with two or three chained, visible CONSEQUENCES inside a single flowing "
        "sentence — never as a list of independently-clocked verbs joined only by commas. WORKED CONTRAST, same "
        "event, both real drafts tonight: WEAK (the checklist that shipped, unread as physics) — \"he bounces off, "
        "spins once in mid-air, stabilizes himself, puffs out his chest proudly, and says the line\" — five separate "
        "beats, none causing the next. STRONG (the rewrite that fixed it) — \"his own momentum shoots him sideways "
        "out of the sunflower and straight into the broad leaf; the leaf snaps under the hit and the impact spins "
        "him a full turn in the air before he catches himself on the rebound, chest already puffing out before his "
        "feet have properly landed\" — one cause (his own momentum), each consequence explicitly produced by the "
        "one before it. The test: could you cut any listed action out without the sentence losing its reason for "
        "the next one happening? If yes, it's a checklist, not a chain — rewrite it.\n"
        "16. THE SHOT BUDGET (2026-07-13, same session, also mined from the platform's own doctrine, "
        "references/multishot-grammar.md — \"shots cost seconds; plan ~4-6s per shot... ask for four shots in 5s "
        "and the model compresses or skips beats\"): this beat's 13-second action window (the Handle Doctrine's "
        "own budget, rule 20) wants 2-3 cuts, not 4 — four cuts averages ~3.25s each, below the platform's own "
        "documented comfort floor, and is the confirmed reason some of tonight's beats read rushed. Author 4 cuts "
        "ONLY when the gag genuinely cannot compress into 3 without cutting a beat the story needs — the default "
        "is 3.\n\n"
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
        "YOUR CREW SERVES YOUR CALL — you direct; they execute (CRYSTAL_BEARS_STUDIO_BIBLE.md Law 1: one mind per "
        "chair, never a committee):\n"
        "• STORY & CHARACTER (John Lasseter's tradition) — make every bear believably ALIVE. Quality is non-"
        "negotiable (no generic shot ever ships). Every bear a DISTINCT, appealing, fully-realised personality "
        "with a want, a flaw and heart — never a type, never interchangeable. ENTERTAIN genuinely (real laughs, "
        "real delight). SINCERITY over cynicism ALWAYS — warmth is the baseline, never irony or meanness. "
        "Believability through truthful behaviour and PERFORMANCE (the 12 principles), alive through acting, "
        "not bigness.\n"
        "• Patrick Lin, your Director of Photography for CAMERA — SEE every shot as a composed film frame: a "
        "motivated, invisible, purposeful camera; staging that reads INSTANTLY; frame, lens, height and distance "
        "chosen for the FEELING you decided above (never showy); real depth with foreground / midground / "
        "background.\n"
        "• Jean-Claude Kalache, your other DP, for LIGHT — light is STORY and emotion: a deliberate COLOUR "
        "SCRIPT per beat; soft, believable, beautiful light that shapes depth, carves the characters off the "
        "background and directs the eye — motivated and felt, never flat.\n"
        "When a choice is between a clever beat and an honest feeling, YOU choose the FEELING, every time, and "
        "your crew follows.\n\n"
        "THIS BEAT'S OWN PHYSICAL COMEDY PATTERN AND EMOTIONAL REGISTER ARE YOUR CALL TOO — not something a "
        "machine infers later by reading your prose back. When you write each beat below, you also choose its "
        "director_mode (the emotional register it plays in) and, when it carries a real physical engine, its "
        "physical_action_archetype (the specific comic-physics pattern it's built from) — the full menu for "
        "both is given in the beat schema. Choose deliberately: this is what lets everyone downstream (the "
        "animator, the compiler) execute YOUR intention, instead of guessing at it after the fact.\n\n"
        "So: find the FEELING and the WHY first, put heart before everything, then translate it into scenes -> shots -> "
        "visual elements that carry the show bible. Anchor the bears. Read the bible first, every time.\n"
        "Output STRICT JSON ONLY (no prose, no markdown) matching the schema you are given.\n\n"
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

def motion_contract_pass(beats, scene, log=print):
    """THE MOTION CONTRACT SELF-CORRECTION LOOP, FINALLY CLOSED (2026-07-15, Julian, live during the first real
    Scene-1 walk of the fresh package — "You know the system. You've got the code. Why are we doing this? We
    just should get it right first time!"): revise_flagged_action (below) was built earlier this same session
    for exactly this purpose and had ZERO callers — the classic built-but-orphaned gap this project's own
    audits keep finding. The Director's prompt states Law 15 (the Motion Contract), the Gate-3 lint flags
    violations downstream, and the correction function sat between them completely unwired — meaning every
    checklist-shaped cut the LLM produced despite the law (an LLM follows a style instruction most of the
    time, never all of the time) reached Julian as a flag HE had to glance at, instead of being corrected at
    the source. This closes the loop: for every authored cut whose action text trips the SAME fragment proxy
    the lint uses (cb_qa.checklist_fragment_count — one shared definition, so fixer and flagger can never
    drift apart), run the Director's own targeted correction, verify the revision actually clears the
    threshold, retry once from the revised text if not, and keep whichever version scores best. Content
    contract unchanged from revise_flagged_action's own: every physical event survives, only the prose SHAPE
    is restructured — never dialogue, framing, or any other field. Fail-soft per cut: a correction-call
    failure keeps the authored text and lets the downstream flag surface it, never crashes the Gate-1 fire.
    Mutates `beats` in place; returns the number of cuts fixed."""
    import cb_qa
    fixed = 0
    for b in beats:
        code = b.get("beatCode") or b.get("slug") or "?"
        for c in (b.get("cuts") or []):
            n0 = cb_qa.checklist_fragment_count(c.get("action"))
            if n0 < cb_qa.CHECKLIST_FLAG_THRESHOLD:
                continue
            best_text, best_n = str(c.get("action") or ""), n0
            for attempt in (1, 2):
                reason = (f"action reads as {best_n} separately-clocked, comma-listed actions — restructure "
                          f"into ONE physical cause with chained consequences (Staging Law 15), keeping every "
                          f"named event")
                try:
                    revised = revise_flagged_action(b, scene, c.get("n"), reason)
                except (Exception, SystemExit) as e:
                    log(f"      ⚠ motion-contract fix failed for {code} cut {c.get('n')} ({str(e)[:80]}) — "
                        f"keeping authored text; the lint flag will surface it", flush=True)
                    break
                n1 = cb_qa.checklist_fragment_count(revised)
                if n1 < best_n:
                    best_text, best_n = revised, n1
                    c["action"] = revised    # revise_flagged_action reads the cut off the beat — apply so a retry refines further
                if best_n < cb_qa.CHECKLIST_FLAG_THRESHOLD:
                    break
            if best_n < n0:
                c["action"] = best_text
                fixed += 1
                status = "clear" if best_n < cb_qa.CHECKLIST_FLAG_THRESHOLD else "improved, still flagged"
                log(f"      ✦ motion-contract fix: {code} cut {c.get('n')} — {n0} fragments -> {best_n} ({status})", flush=True)
    return fixed

def revise_flagged_action(beat, scene, cut_n, flag_reason):
    """THE MOTION CONTRACT SELF-CORRECTION (2026-07-15, Julian — "why aren't the prompts being created
    understanding the flagging system... why do they get to this point" -> "you do it"): Staging Laws 15/16
    (rule 78, the Motion Contract + the Shot Budget) already stop a FRESH Gate-1 fire from ever writing a
    checklist-shaped cut — but a beat authored BEFORE those laws existed still carries the old shape, and
    cb_qa.check_gate3_lint's checklist-verb check correctly flags it. That gap — existing content written
    under an older, weaker authoring standard — was never closed for already-authored beats (rule 78's own
    docstring names this explicitly: "it does not retroactively rewrite the other 42 beats' already-authored
    action text... Whether to re-author existing beats... is Julian's own call").

    This closes it the SAME way rule 78 closed it for future content: through the Director's own voice
    (_mind(), the full Sixteen Staging Laws), not a hand patch from outside the authoring process. Scoped
    narrowly — revises ONLY the one flagged cut's action text, never the beat, never dialogue/framing/any
    other field. Zero invented content is the hard contract: every physical event the ORIGINAL cut named
    must survive in the rewrite, restructured from a checklist into one cause with chained consequences
    (the exact WEAK/STRONG worked example already baked into _mind()'s own Law 15 text). Raises SystemExit
    on a genuine provider failure, matching every other LLM call in this module — no silent fallback."""
    from pydantic import BaseModel, Field
    class RevisedAction(BaseModel):
        rewritten_action: str = Field(description=(
            "the ONE cut's action text, rewritten as one physical cause with two or three chained, visible "
            "consequences — every event the original named must still be present, just restructured out of "
            "checklist form. Never touch dialogue, framing, or invent a new event."))
    cut = next((c for c in (beat.get("cuts") or []) if c.get("n") == cut_n), None)
    if cut is None:
        raise ValueError(f"cut {cut_n} not found on beat {beat.get('beatCode')}")
    chars = beat.get("openingCast") or beat.get("characters") or []
    base_system, _roster_dict = _mind()   # _mind() returns (system_prompt, roster_dict), not a bare string
    system = base_system + (
        "\n\n════════ THIS IS A TARGETED MOTION-CONTRACT CORRECTION, NOT A RE-AUTHORING ════════\n"
        "You already wrote this beat. The automatic lint has flagged ONE cut's action text as reading like a "
        "checklist of separately-clocked events rather than one physical cause with chained consequences "
        "(your own Staging Law 15, the Motion Contract). Rewrite ONLY that cut's action text. Every physical "
        "event the original names must survive in your rewrite — you are restructuring the PROSE SHAPE, "
        "never adding a new gag, prop or action, and never dropping one the original described. Never touch "
        "dialogue, framing, or any other field."
    )
    user = (
        f"BEAT {beat.get('beatCode')} — scene: {scene.get('name','')}\n"
        f"Cast: {', '.join(chars)}\n"
        f"The lint's own reason this was flagged: {flag_reason}\n\n"
        f"THE FLAGGED CUT (n={cut_n}):\n"
        f"  framing: {cut.get('framing','')}\n"
        f"  action (REWRITE THIS, ONLY THIS): {cut.get('action','')}\n\n"
        "Surrounding cuts, for continuity context only — do NOT rewrite these:\n" +
        "\n".join(f"  cut {c.get('n')}: {c.get('action','')}" for c in (beat.get("cuts") or []) if c.get("n") != cut_n) +
        f"\n\nThis beat's own endState (what it settles into): {beat.get('endState','')}\n"
        f"Staging prohibitions this beat must never violate: {beat.get('stagingProhibited') or '(none authored)'}"
    )
    return cb_llm.structured(system, user, RevisedAction,
                              label=f"motion_contract_fix_{beat.get('beatCode')}_{cut_n}").rewritten_action

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
        '     "emotionalCore": one honest sentence — what this scene is REALLY about and what the audience must FEEL,\n'
        '     "ambientBed": ONE locked ambient-sound-bed line for the WHOLE scene (surf, wind, birdsong, rain — '
        'whatever this scene\'s own constant environment actually is). This EXACT line repeats unchanged across '
        'every beat in the scene, so it must describe ONLY the constant environment — never a future story '
        'event that hasn\'t happened yet at this point in the scene (a storm scene\'s FIRST calm beat must not '
        'describe thunder that only arrives later), and never anything beat-specific (a single beat\'s own '
        'foreground SFX belongs to that beat, not here),\n'
        '     "parentLine": ONE sentence — the adult-layer read of the WHOLE scene: what a watching parent '
        'understands or feels here that a 4-year-old doesn\'t yet (the co-watch contract),\n'
        '     "sceneLook": ONE short, already-punctuated atmosphere line for the WHOLE scene — the light '
        'source, its direction and behaviour, texture, mood (e.g. "warm golden morning light through the '
        'flower-meadow corridor, pollen glittering and drifting in the air"). This is READ VERBATIM into '
        'every beat\'s shipped render prompt, appended straight after the show\'s own fixed style line, so '
        'it is the ONLY atmosphere language a beat gets — write it to actually carry the scene\'s look, '
        'grounded in "lighting"/"weather"/"colorTemperature" above but condensed to ONE clean sentence, '
        'never a restatement of "look" (the empty-plate composition) and never a multi-clause paragraph. '
        'Like ambientBed, this is the scene\'s CONSTANT — its dominant, opening atmosphere — not a '
        'beat-by-beat progression (a storm scene\'s pre-storm calm still gets this same line; the storm\'s '
        'own arrival is each beat\'s own action/atmosphere field, not this one). Note: this scene\'s ensemble '
        'throughline (who carries it, who gets the big moment) is NOT authored here — it is derived '
        'automatically, after the fact, from each beat\'s own fidelityAllocation once the beats below are '
        'written (see _derive_performance_throughline); nothing to write for it in this stage,\n'
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
    """UPPER-CASE speaker names for the parser — the canonical cast + the relational/group cues that also speak.
    FIXED 2026-07-11 (full-codebase audit, duplication finding): this used to hand-duplicate cb_preflight's own
    _script_roster byte-for-byte (same regexes, same hardcoded {"ALL", "KEEN'S MUM", "HOWIE", "HOWEY"} set) —
    a real drift risk (e.g. a future name-spelling fix landing in only one copy). Delegates to the one real
    implementation instead."""
    import cb_preflight
    try:
        cj = json.load(open(CHARS))
    except Exception:
        cj = {}
    return cb_preflight._script_roster(cj)

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
    """Words only — drop [V3 tags], a leading NAME: and punctuation — to compare a beat's line to the script's line.
    FIXED 2026-07-11 (full-codebase audit, duplication finding): delegates to cb_preflight._norm_dialogue_words,
    which mirrored this function's exact logic in a second, independently-maintained copy — see _script_roster's
    own note above for the same class of risk."""
    import cb_preflight
    return cb_preflight._norm_dialogue_words(s)

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
                slots.append((b, c))
    n = min(len(slots), len(scene_dialogue)); fixed = 0
    for k in range(n):
        beat, cut = slots[k]; char, line, paren = scene_dialogue[k]
        want = f"{char}: {line}"
        if (cut.get("dialogue") or "").strip() != want:
            if _norm_line(cut.get("dialogue")) != _norm_line(line):
                log(f"      ⋯ verbatim: scene {scene_num} line {k+1} corrected → {char}: \"{line[:52]}\"", flush=True)
            cut["dialogue"] = want; fixed += 1
            # FIXED 2026-07-11 (full-codebase audit, cb_director.py finding #2): a speaker correction here
            # used to leave the OWNING BEAT's own characters/speakers/openingCast untouched — if the script's
            # real speaker differs from what the LLM attributed, downstream reference-pulling (cb_prompts.py's
            # opening_cast) would never fetch the CORRECT speaker's identity image, the same class of gap
            # _force_include already guards against for its own forced-insert path (see its own comment above).
            for _field in ("characters", "speakers", "openingCast"):
                if _field in beat or _field == "characters":
                    lst = beat.setdefault(_field, [])
                    if char not in lst:
                        lst.append(char)
        if paren and not (cut.get("delivery") or "").strip():
            cut["delivery"] = paren.strip("()")
    # COMPLETENESS (content-based) — every script line must be present exactly once. Catches DROPS + DUPLICATES that
    # index-alignment alone would ship, so a line can NEVER silently vanish (e.g. Scene 8's "Thank you"). The returned
    # `dropped`/`dups` let Gate 1 flag the scene for a re-break rather than sign off an incomplete/corrupted scene —
    # a DUPLICATE is itself evidence the LLM split one script line across two cuts, misattributing content between
    # them, so it must trigger the same retry path as a drop, not just a soft log line.
    pkg_norm = [_norm_line(c.get("dialogue")) for (_b, c) in slots]
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

def _scene_character_truth(chars, cast):
    """THE SCENE-SCOPED BIBLE CHECK (Julian's ruling, 2026-07-06 — "you need to see who's in the scene and
    what the scene is about, and then you can build it from there... against the characters and the show
    Bible to ensure the personas and the characters are all on spot... we can't do it too complicated,
    because the best ones have turned out with the least amount of words").

    Found live: 1.B1's shot list was faithful on Fuzzby's LATERAL chaos (zig-zag, dodges) but silent on his
    ALTITUDE chaos (his own bible: "NEVER let Fuzzby hold a level, steady altitude... always overshooting,
    undershooting and porpoising") — the terse system-level cast roster (`_roster()`, size/cadence/
    actingNote, always loaded for all 11 characters) doesn't carry a character's full dos/donts, so a hard,
    always-on rule buried in one character's own list can go unchecked. The fix is scoped, not a system-wide
    bloat: pulled ONLY for the characters actually cast in THIS scene (never all 11 regardless of who's
    in it), and the content itself adds nothing new — every dos/donts line already exists, terse, one rule
    per line, in characters.json. This is Gate 1 AUTHORING context (a one-time per-scene call), not Gate 3
    render text — richer context here does not reopen the shipped-prompt word budget the Director's own
    render prompt (cb_segprompt.py) is held to; the two are deliberately different economies."""
    lines = []
    for name in cast or []:
        c = (chars or {}).get(name) or {}
        bible = c.get("bible") or {}
        dos = [str(x).strip() for x in (bible.get("dos") or []) if str(x).strip()]
        donts = [str(x).strip() for x in (bible.get("donts") or []) if str(x).strip()]
        extra = [str(bible.get(k)).strip() for k in ("motionRule", "wingsInFlight") if bible.get(k)]
        if not (dos or donts or extra):
            continue
        block = [f"  {name}:"]
        for d in dos:
            block.append(f"    ALWAYS: {d}")
        for d in donts:
            block.append(f"    NEVER: {d}")
        for e in extra:
            block.append(f"    HARD RULE: {e}")
        lines.append("\n".join(block))
    if not lines:
        return ""
    return ("════════ CHARACTER TRUTH FOR THIS SCENE'S OWN CAST — CHECK EVERY BEAT AGAINST THIS ════════\n"
            "Every character below is actually in this scene. Every ALWAYS/NEVER/HARD RULE line is a real, "
            "existing rule from that character's own bible — not new, not invented, just easy to miss inside "
            "a longer entry. A staged action that contradicts a NEVER, or fails to concretely SHOW an ALWAYS "
            "(e.g. a rule that a character's altitude is always erratic is not satisfied by a lateral-only "
            "path — the vertical half has to be staged too), is wrong even if it reads fine in isolation. "
            "Check every cut you write against every line below for every character it stages.\n" +
            "\n".join(lines) + "\n")


def _finalize_beat_manifest_fields(beats):
    """DEFENSE IN DEPTH for THE MANIFEST LAYER (rule 46, 2026-07-07): the prompt tells the Director exactly what
    junctionType/opensOn should be for every beat, but an LLM can still drop or misfire a field despite clear
    instructions — this is the SAME belt-and-braces pattern already used elsewhere in this module (e.g. the
    verbatim gate doesn't just ask nicely, it force-includes a dropped line as a last resort). Mutates `beats`
    in place; called AFTER beatCode is assigned (so beat 1 of the scene is identifiable) and BEFORE
    validate_scene_beats, so a repair call (if one fires) sees the corrected values, not the raw LLM output.

    junctionType: mechanical — rule 31's own default ("intentional_next_shot... never seamless_continuation by
    omission") means a missing/invalid value on a NON-opener beat is safely defaulted, never invented prose.
    Left alone (None) for the scene's own first beat, and left alone if the Director explicitly chose
    "seamless_continuation" (a real creative decision, never overridden).

    opensOn: for a non-opener beat with no opensOn (or an incomplete one), derive a minimal-but-real fallback
    from that beat's own cut 1 — the SAME mechanical extraction technique already used when this field was
    first backfilled by hand (2026-07-06), never an invented generic phrase. Left alone (None) for the scene's
    own first beat.

    fidelityAllocation (2026-07-07): unlike junctionType/opensOn, this applies to EVERY beat including the
    scene's own first one — there's always a "who does this beat serve" answer, even for an opener. If missing
    or with a blank primary, derive mechanically from this beat's own speakers/characters (whoever speaks first
    is primary, matching the same "who's actually doing something" logic _v5_active_cast already uses at
    Gate-3 compile time) — never invented, just extracted from data already on the beat."""
    JUNCTION_VALID = {"intentional_next_shot", "seamless_continuation"}
    for i, b in enumerate(beats):
        is_opener = (i == 0)
        if not is_opener:
            if str(b.get("junctionType") or "").strip() not in JUNCTION_VALID:
                b["junctionType"] = "intentional_next_shot"
            oo = b.get("opensOn") or {}
            if not (isinstance(oo, dict) and str(oo.get("who") or "").strip() and str(oo.get("action") or "").strip()):
                cuts = b.get("cuts") or []
                first_action = str(cuts[0].get("action") or "").strip() if cuts else ""
                cast = b.get("openingCast") or b.get("characters") or []
                who = cast[0] if cast else "the cast"
                action = (first_action.split(".")[0].strip() or "already in motion") if first_action else "already in motion"
                b["opensOn"] = {"who": who, "action": action}

        fa = b.get("fidelityAllocation") or {}
        if not str(fa.get("primary") or "").strip() or str(fa.get("primary")).strip().lower() == "none":
            speakers = [s for s in (b.get("speakers") or []) if s]
            cast = b.get("openingCast") or b.get("characters") or []
            ordered = speakers + [c for c in cast if c not in speakers]
            primary = ordered[0] if ordered else "Unknown"
            secondary = next((c for c in ordered if c != primary), "none")
            economized = [c for c in (b.get("characters") or []) if c not in (primary, secondary)]
            b["fidelityAllocation"] = {"primary": primary, "secondary": secondary,
                                       "economized": ", ".join(economized) if economized else "none"}

def _derive_performance_throughline(beats):
    """THE PERFORMANCE THROUGHLINE, MECHANICAL (2026-07-08, Julian's correction of the same-night rule 57
    addition — "the script and the storyboard and beat should deliver that", not a separately hand-authored
    note): the earlier version of this asked the Director to WRITE a scene-level throughline sentence BEFORE
    any beats existed, then fed it back into beat authoring as a plan. Julian's point: the beats themselves,
    once written, already say who carries the scene — there is no reason to ask anyone to type that out
    separately. This function reads it straight off each beat's OWN `fidelityAllocation.primary` (already
    guaranteed present by `_finalize_beat_manifest_fields`, run just before this is ever called) and reports
    the pattern in plain terms — a run of consecutive beats sharing one primary, and where it hands off.
    Zero LLM calls, nothing invented: if the beats don't already show a throughline, this doesn't invent one."""
    # Natural sort on the trailing beat number (cb_preflight._beat_sort_key) — a lexicographic sort on the raw
    # code string would misorder any scene with 10+ beats ('1.B10' < '1.B2'); found in the 2026-07-08 audit
    # inspecting this very function.
    import cb_preflight
    beats = sorted(beats, key=lambda b: cb_preflight._beat_sort_key(b.get("beatCode") or ""))
    runs = []   # [(primary_name, [beatCodes]), ...] — consecutive beats sharing the same primary collapse into one run
    for b in beats:
        code = b.get("beatCode") or "?"
        primary = str((b.get("fidelityAllocation") or {}).get("primary") or "").strip() or "Unknown"
        if runs and runs[-1][0] == primary:
            runs[-1][1].append(code)
        else:
            runs.append((primary, [code]))
    if not runs:
        return "No beats authored yet — nothing to derive."
    if len(runs) == 1:
        name, codes = runs[0]
        span = f"{codes[0]}-{codes[-1]}" if len(codes) > 1 else codes[0]
        return f"{name} carries this scene's focus throughout ({span}) — no hand-off to another character."
    parts = []
    for name, codes in runs:
        span = f"{codes[0]}-{codes[-1]}" if len(codes) > 1 else codes[0]
        parts.append(f"{name} ({span})")
    last_name, last_codes = runs[-1]
    last_span = f"{last_codes[0]}-{last_codes[-1]}" if len(last_codes) > 1 else last_codes[0]
    last_word = "beats" if len(last_codes) > 1 else "beat"
    return (f"This scene's focus moves from " + " to ".join(parts) +
            f" — the moment lands on {last_name} in the closing {last_word} ({last_span}).")

# ── THE TWO-STAGE SPLIT (2026-07-15, Julian's own architectural ruling) ──────────────────────────────────
# "We build a guardrail around each beat to ensure that we deliver what the director wants, not working
# within constraints all of the time... if the magic doesn't happen, then it doesn't happen." The single
# scene_to_beats() call below asks one model to be a world-class creative director AND a compliance officer
# filling out ~50 JSON fields in the same breath — the confirmed, repeated reason the craft rating
# (cb_craft.py) kept finding "competent, not Pixar" beats even when every technical/canon law was honoured.
# These two functions are the fix: STAGE ONE is pure creative authorship, nothing else in the room. STAGE TWO
# is a separate engineering pass that reads what STAGE ONE already decided and labels the technical manifest
# fields faithfully — it does not create, it delivers. direct() below merges their output and THEN runs the
# existing verbatim-gate/repair loop (validate_scene_beats) — correctness-checking still happens, just after
# creative authorship, never competing with it inside one generation call.
def direct_scene_creative(system, script, beatmap, scene, theme, chars=None, elements=None, retry_note=""):
    """STAGE ONE — THE DIRECTOR'S CUT. Pure creative authorship: what happens, how it's staged, what's funny,
    what breaks the heart, what the camera does. No manifest/technical fields anywhere in this call's schema
    or prompt — `system` (from _mind()) already carries the Sixteen Staging Laws, the worked examples and the
    Docter/Lasseter/Lin/Kalache crew framing; this task instruction adds only what a director genuinely needs
    to know to stage THIS scene (the locked dialogue, the beat-unit/pacing math, the comedy/emotion doctrine)
    — never a schema field name."""
    user = (
        (retry_note + "\n\n" if retry_note else "") +
        f"FULL SCRIPT for reference:\n\n{script}\n\n"
        f"THE LOCKED THEME — every beat serves this (Docter):\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"BEAT MAP (whole episode context):\n{json.dumps(beatmap.get('scenes'), ensure_ascii=False)}\n\n"
        f"CONTINUITY scaffold:\n{json.dumps(beatmap.get('continuity'), ensure_ascii=False)}\n\n"
        f"════════ TASK: DIRECT SCENE {scene['sceneNumber']} ('{scene['name']}') ════════\n"
        f"Scene emotional core: {scene.get('emotionalCore')}\n"
        f"Pillar: {scene.get('pillar')} | cast: {scene.get('cast')} | time/weather: {scene.get('time')}/{scene.get('weather')}\n\n"
        f"{_scene_character_truth(chars, scene.get('cast'))}"
        "════════ WHAT YOU ARE ACTUALLY DOING ════════\n"
        "This is not a form to complete. A studio has handed you a locked script and is trusting you to bring "
        "it to life the way Pete Docter, John Lasseter or a DreamWorks A-team would — genuine wonder, genuine "
        "comedy, genuine emotion, staging so specific and alive that a room full of professionals watching the "
        "storyboard reel would gasp, laugh, or go quiet. Every rule below exists to serve THAT, never to "
        "replace it. If a beat is technically compliant but reads as safe, generic, or interchangeable with "
        "any other family cartoon, you have failed at the actual job regardless of whether every field below "
        "is filled in correctly. Reach. Invent the specific physical bit nobody's seen before. Let the camera, "
        "the light and the performance all serve ONE intention per beat, chosen on purpose.\n\n"
        "════════ THE SCENE'S EXACT SCRIPT ELEMENTS — THE GROUND TRUTH (VERBATIM) ════════\n"
        "This is your ONLY source for WHAT happens and WHAT is said — the words a director is handed, never "
        "yours to change. BREAK IT DOWN into beats. Rules:\n"
        "  • Assign EVERY dialogue line below to a cut, IN THIS ORDER, WORD-FOR-WORD (a hard gate snaps any drift "
        "back, so match them exactly, keep the writer's parenthetical as the cut's delivery).\n"
        "  • COMPLETENESS IS ABSOLUTE: use each line EXACTLY ONCE — the TOTAL number of dialogue cuts across your "
        "beats must EQUAL the number of DIALOGUE lines listed below. NEVER drop a line, NEVER repeat one.\n"
        "  • Each cut's ACTION must be FAITHFUL to these ACTION lines — invent nothing the script forbids, drop "
        "nothing it requires, add no character it doesn't place here. Everything ELSE — how it's shot, paced, "
        "escalated, felt — is entirely your own directorial invention.\n"
        f"{_elements_block(elements)}\n\n"
        "THE UNIT IS THE BEAT = ONE Seedance TAKE, up to ~15s. A take is a CONTAINER of complete MOMENTS: it "
        "holds a WHOLE number of them — 1, 2, or 3 — each opening and closing, NEVER a fraction. First judge "
        "the scene's screen time, then PACK its complete moments into the FEWEST takes of <=~15s. A take NEVER "
        "ends mid-moment — it ENDS on a BUTTON, NEVER on an OPEN the next beat must resolve. A tight exchange "
        "(question->answer, setup->payoff, joke->topper) lives ENTIRELY inside ONE beat; never end a beat on the "
        "question and open the next with the answer.\n"
        "COMEDY — the funny beats, ESPECIALLY FUZZBY the proud bumbler — GO OVER-THE-TOP: tag a gag beat "
        "comedyMode=BIG and run the GAG CLOCK (over-confident WIND-UP -> the BANG with mass -> the delayed TAKE / "
        "held beat -> the snap-back BUTTON), commit 110%, build the gag BACKWARDS from the bravado, rule-of-three "
        "then break it, end on a button. Tag a heart beat comedyMode=TRUE (small + real). NEVER blend BIG and "
        "TRUE in one beat.\n"
        "If KEEN makes a brave choice, a FEAR cut (trembling paws / swallowed gulp / flattened ears) MUST precede "
        "it within the beat — courage is SHOWN, never assumed.\n"
        "Pick ONE dominant COLOUR TEMPERATURE for the scene (amber=safety/love · saturated crystal-glow=wonder · "
        "cool blue-silver=fear/loneliness · rose-lavender=tenderness · grey-green=low ebb) — every beat inherits it. "
        "CRYSTAL WOODS is an emotional PARTICIPANT, never wallpaper. Plan the scene's ONE 'that's beautiful' "
        "beauty moment. Track each bear's CRYSTAL GLOW as an emotional signal.\n"
        "DIALOGUE IS LOCKED — this is a FINAL script. Use each line EXACTLY as written; NEVER cut, rewrite, "
        "paraphrase, soften, or invent dialogue. Attribute each line to its speaker inside the cut it lands on. "
        "A beat or cut with no line carries it wordlessly through staging + performance.\n\n"
        "Output JSON ONLY — a director's shot-by-shot treatment for this scene: { \"beats\": [ {\n"
        '  "slug": "kebab-id", "scene": "' + scene['name'] + '", "characters": [canon names in this beat],\n'
        '  "openingCast": [the SUBSET of "characters" actually VISIBLE IN THE OPENING FRAME — a character who '
        'ENTERS LATER is in "characters" but not here],\n'
        '  "speakers": [canon names who speak], "keenWristbands": "none"|"vacant"|"crystal" (per the arc; null if '
        'Keen absent),\n'
        '  "durationSec": int 8..15,\n'
        '  "pillar": str, "intensity": 0..1, "storyBeat": what happens across this window,\n'
        '  "emotionalIntent": what the audience FEELS across the beat,\n'
        '  "want": what the bear PERFORMS/reaches for, "need": the true thing underneath they resist,\n'
        '  "crystalTruth": what the crystal reveals that the FACE hides (the crystal is the NEED, contradicts the '
        'face), "kidRead": what the CHILD laughs at/sees, "adultRead": the truth the PARENT catches — same beat, '
        'same second,\n'
        '  "theGame": for an emotional beat, the invented GAME whose made-up rules ARE the emotional logic; null if '
        'none,\n'
        '  "wordlessHeld": true ONLY for the single nadir beat of the WHOLE EPISODE — else false,\n'
        '  "comedyMode": "BIG"|"TRUE"|null,\n'
        '  "physicalFeeling": the SINGLE physical sensation the audience FEELS IN THEIR BODY in the first ~2s,\n'
        '  "light": how light ISOLATES the feeling, "atmosphere": how the air/particles BUILD toward it, '
        '"motionTempo": the motion tempo that LANDS on it, "grade": the colour grade after it passes,\n'
        '  "cuts": [ {"n": int, "framing": "shotSize + angle + movement", "action": one flowing physical-cause-'
        'and-chained-consequence sentence (never a checklist of separately-clocked verbs), "dialogue": "NAME: '
        'line" or null, "delivery": REQUIRED whenever dialogue is non-null — a CLAUSE naming the specific tone '
        'and physical behaviour carrying the line, starting with "with"/"as", never a generic tag, '
        '"voiceTreatment": null, or "group_chorus" ONLY when 3+ named characters speak this line in unison, or '
        '"underwater_vo" for a submerged/muffled internal VO, "chorusMembers": required list when '
        'voiceTreatment=="group_chorus"} ], // 2-3 cuts, 4 only when the gag genuinely cannot compress,\n'
        '  "cameraArc": the through-line of the whole beat, "pacingVerbs": [specific physics verbs],\n'
        '  "pauseHold": where the beat goes still, machine-readable "N second(s)" (max 1.5),\n'
        '  "performance": {"surface":str,"underneath":str,"innerThought":str},\n'
        '  "crystalGlow": which bear(s) + state, "beautyMoment": true|false,\n'
        '  "startState": the OPENING FRAME — WHERE each character is and what they are doing (the BEFORE; '
        'positions + held action; NO motion words),\n'
        '  "soundIntent": the SFX + timed-music cues this beat should score,\n'
        '  "continuity": {"opensFrom": how this beat\'s opening hands off the previous beat\'s last frame, '
        '"carryToNext": what carries forward, "screenDirection": "LEFT"|"RIGHT"},\n'
        '  "check": {"focalSubject":str,"emotionalRead":str,"heartCheck":str},\n'
        '  "endState": directing prose (1-3 sentences) for THIS beat\'s own distinct ending — a living settle, in '
        'character — the new, distinct final moment (never a restatement of the previous beat\'s pose)\n'
        "} ] }\n\n"
        "Stage two-handers in locked positions (Fuzzby BIGGER frame-LEFT, Zenny SMALLER frame-RIGHT) and attribute "
        "each line. Sizes per the chart (Amie<Sunny<Luna≈Keen≈Aida<Misty<Howey). Order beats in scene order."
    )
    return [b.model_dump(by_alias=True) for b in
            cb_llm.structured(system, user, S.CreativeSceneBeats,
                               label=f"direct_scene_creative s{scene['sceneNumber']}").beats]


def _engineer_mind():
    """STAGE TWO's system prompt — a DIFFERENT persona from _mind()'s Pete Docter, deliberately. The director's
    creative work is already finished by the time this runs; this voice's whole job is engineering delivery of
    that work, never re-directing it."""
    return (
        "You are the studio's technical/script supervisor — NOT the director. The director has already made "
        "every creative decision for these beats: the story, the staging, the comedy, the emotion, the camera. "
        "Your job is pure ENGINEERING — read what the director already wrote and derive/label the technical "
        "fields below FAITHFULLY from it. You never invent new creative content, never second-guess a creative "
        "choice, never soften or 'improve' a line of staging. If something is ambiguous, name the most literal, "
        "grounded reading of what's already on the page — you are compiling, not rewriting."
    )


def deliver_beat_manifest(script, scene, theme, creative_beats):
    """STAGE TWO — THE GUARDRAIL PASS. Reads the already-written creative beats for one scene and derives the
    technical manifest layer (junctionType/opensOn/carryMarks/endStateStill/fidelityAllocation/director_mode/
    physical_action_archetype/humourLayer/emotionMechanic/actingContrast) as a labeling task grounded in
    content that already exists — never a second creative-authorship pass. Runs ONE call per scene (not per
    beat) so the model sees the whole scene's own throughline when deciding fidelityAllocation/director_mode.
    `_finalize_beat_manifest_fields` (defense-in-depth, unchanged) still runs on the merged result afterward —
    this call is the primary source, that function is the safety net for anything it misses."""
    _modes, _archs = _mode_archetype_menu()
    digest = [{"slug": b.get("slug"), "storyBeat": b.get("storyBeat"), "endState": b.get("endState"),
               "characters": b.get("characters"), "speakers": b.get("speakers"), "comedyMode": b.get("comedyMode"),
               "cuts": [{"framing": c.get("framing"), "action": c.get("action")} for c in (b.get("cuts") or [])]}
              for b in creative_beats]
    user = (
        f"THE LOCKED THEME:\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"SCENE {scene['sceneNumber']} ('{scene['name']}') — the director's OWN already-written beats, in order:\n"
        f"{json.dumps(digest, ensure_ascii=False, indent=1)}\n\n"
        "════════ TASK: LABEL THE TECHNICAL MANIFEST FIELDS FOR EACH BEAT ABOVE ════════\n"
        "For EVERY beat listed, in the SAME order, output:\n"
        '{ "beats": [ {\n'
        '  "slug": "MUST match the beat\'s own slug above, exactly",\n'
        '  "endStateStill": the beat\'s own "endState" re-described as a static PHOTOGRAPH: NO temporal verbs '
        '("settles into", "turns to"), NO imperatives, NO camera/ambience — only subjects, poses, positions and '
        'expressions exactly as one frozen frame would show them,\n'
        '  "carryMarks": a SHORT phrase (never a sentence) naming what specifically, visibly persists INTO THIS '
        'BEAT\'S OWN OPENING from the beat immediately before it in the list above (read its "endState") — a held '
        'object, wet fur, a costume state, a physical position. If genuinely nothing persists, say so briefly '
        '("no persisting marks — a clean reset"). This is backward-looking: what THIS beat inherits, not what it '
        'hands off. Null/omit ONLY for the scene\'s own first beat (no predecessor),\n'
        '  "junctionType": "intentional_next_shot" for every beat except the scene\'s own first (null there) — '
        '"seamless_continuation" ONLY if this beat\'s own cut 1 explicitly continues one unbroken take from the '
        'previous beat\'s last cut,\n'
        '  "opensOn": {"who": name, "action": short phrase} — WHO the camera opens on and their immediate mid-'
        'motion state, read directly from this beat\'s own cut 1. Null for the scene\'s own first beat,\n'
        '  "relayOpeningNote": null on most beats — one extra sentence ONLY if carryMarks/opensOn alone leave real '
        'ambiguity about the instant right after the opening frame,\n'
        '  "spatialAxis": null on most beats — one sentence ONLY if this beat genuinely needs a stated left/right '
        'blocking law beyond what startState already shows,\n'
        '  "stagingProhibited": null on most beats — a short list ONLY if this beat\'s specific gag has a real, '
        'specific way to go visibly wrong (e.g. a character vanishing into an object) beyond the standing '
        'negatives,\n'
        '  "actingContrast": one sentence — which characters in this beat play off each other and how (or, for a '
        'solo beat, the internal surface-vs-interior contrast) — read this directly off the cuts already written,\n'
        '  "humourLayer": 1-4 (1=pure physical/visual a toddler reads instantly; 2=a comic beat a 4-8 year old '
        'GETS; 3=dual-register, the adult catches something extra; 4=mostly an adult/craft-level wink) — rate '
        'what\'s ALREADY on the page, do not invent comedy that isn\'t there; a quiet Heart beat can honestly be 1,\n'
        '  "emotionMechanic": one sentence stating the CONCRETE visual/physical mechanism (a glow, a gesture, a '
        'held breath) that ALREADY makes this beat\'s emotion legible — read it off what\'s written, never restate '
        '"emotionalIntent",\n'
        '  "fidelityAllocation": {"primary": name, "secondary": name or "none", "economized": comma-separated '
        'names or "none"} — read who this beat\'s ALREADY-WRITTEN cuts actually give real, specific performance '
        'to (primary), who plays off them (secondary), and who is present but staying generic/background '
        '(economized) — a factual read of what was written, not a new creative call,\n'
        f'  "director_mode": the emotional register this beat\'s ALREADY-WRITTEN content plays in. One of: '
        f'{_modes}. Null only if genuinely no strong emotional engine is present,\n'
        f'  "physical_action_archetype": which pattern this beat\'s ALREADY-STAGED physical comedy matches. One '
        f'of: {_archs}. Choose the one whose own beats match what\'s already in cuts[] above — you are naming the '
        'shape already there, never inventing a new one. Null for a pure dialogue/reaction beat\n'
        "} ] }"
    )
    return [b.model_dump(by_alias=True) for b in
            cb_llm.structured(_engineer_mind(), user, S.SceneManifest,
                               label=f"deliver_beat_manifest s{scene['sceneNumber']}").beats]


def _merge_creative_and_manifest(creative_beats, manifest_beats):
    """Combines STAGE ONE's creative content with STAGE TWO's technical labels into full beat dicts, matching
    the shape every downstream consumer (validate_scene_beats, _finalize_beat_manifest_fields, direct()'s own
    package assembly) already expects. Matched by slug; a manifest entry with no matching creative beat (or
    vice versa) is a real authoring-order bug, not silently dropped — raises loudly so it's caught here, not
    three stages downstream as a mystery missing field."""
    by_slug = {m.get("slug"): m for m in manifest_beats}
    merged = []
    for cb in creative_beats:
        slug = cb.get("slug")
        m = by_slug.get(slug)
        if m is None:
            raise ValueError(f"deliver_beat_manifest returned no entry for creative beat slug={slug!r} — "
                              f"stage two dropped a beat stage one wrote (available slugs: {list(by_slug)})")
        out = dict(cb)
        for k, v in m.items():
            if k == "slug":
                continue
            out[k] = v
        merged.append(out)
    return merged


def scene_to_beats(system, script, beatmap, scene, theme, chars=None, elements=None, retry_note=""):
    _modes, _archs = _mode_archetype_menu()
    user = (
        (retry_note + "\n\n" if retry_note else "") +
        f"FULL SCRIPT for reference:\n\n{script}\n\n"
        f"THE LOCKED THEME — every beat serves this (Docter):\n{json.dumps(theme, ensure_ascii=False)}\n\n"
        f"BEAT MAP (whole episode context):\n{json.dumps(beatmap.get('scenes'), ensure_ascii=False)}\n\n"
        f"CONTINUITY scaffold:\n{json.dumps(beatmap.get('continuity'), ensure_ascii=False)}\n\n"
        f"════════ TASK: STAGE B — design the BEATS for SCENE {scene['sceneNumber']} ('{scene['name']}') ONLY ════════\n"
        f"Scene emotional core: {scene.get('emotionalCore')}\n"
        f"Pillar: {scene.get('pillar')} | cast: {scene.get('cast')} | time/weather: {scene.get('time')}/{scene.get('weather')}\n\n"
        f"{_scene_character_truth(chars, scene.get('cast'))}"
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
        '"delivery": REQUIRED whenever dialogue is non-null (null only for a wordless cut) — ACTING DIRECTION '
        'for how the line is performed: the specific TONE, the physical behaviour that carries it, and (where '
        'it sharpens the moment) what is held back or revealed — NEVER a restatement or paraphrase of the '
        'words themselves, and NEVER a generic one-word tag ("happy"/"sad"/"excited" all fail this). This is '
        'quoted directly into the shipped render prompt as "{Name} performs {his/her} vocal beat from @Audio1 '
        '{delivery}." — so write it as a CLAUSE that completes that sentence naturally, starting with a '
        'preposition like "with" or "as", never a capital letter or a full independent sentence. WORKED '
        'EXAMPLES (the actual bar): "with earnest, hopeful pomp, presenting the pollen moustache as though it '
        'were an official uniform" / "as a dry, affectionate counterpunch, holding back the laugh until the '
        'end of the delivery", '
        '"voiceTreatment": null for an ordinary spoken line (the default — omit or leave null). Set to '
        '"group_chorus" ONLY when 3+ named characters speak this SAME line/cue together in unison (e.g. an '
        '"ALL:" line everyone delivers as one crowd voice, never one character lip-syncing for the group). Set '
        'to "underwater_vo" ONLY for a cut set in a submerged, muffled-vocal moment (an internal/underwater '
        'VO, not a normal surface line). '
        '"chorusMembers": REQUIRED (a list of canon character names, 3 or more) whenever voiceTreatment=='
        '"group_chorus" — exactly who forms the unison; null/omit otherwise. EXCLUDE any character whose own '
        'canon rules forbid chorus participation for this line (e.g. the bees never join a bear chorus — '
        'match the beat\'s own established logic, do not invent a new exclusion rule)'
        '} ],   // 2-3 internal cuts IN ORDER (THE SHOT BUDGET, law 16 above) — 4 ONLY when the gag genuinely '
        'cannot compress into 3 without losing a beat the story needs; cut 1 is the opening,\n'
        '  "cameraArc": the through-line of the whole beat, "pacingVerbs": [specific physics verbs],\n'
        '  "pauseHold": where the beat goes still and MUST state a concrete duration in the exact machine-'
        'readable form "N second(s)" or "N.N second(s)" (e.g. "1.2 second hold on Zenny\'s flat stare"), '
        'NEVER "half a second"/"a beat"/"briefly" with no number — and the stated number must be <=1.5 '
        '(the staging law caps every hold at 1.5s; state the number honestly, never round up past it),\n'
        '  "performance": {"surface":str,"underneath":str,"innerThought":str},\n'
        '  "crystalGlow": which bear(s) + state (brightening|dimming|pulsing|steady), "beautyMoment": true|false,\n'
        '  "startState": the OPENING FRAME — the STATIC HELD pose at the very first frame of the beat: WHERE each '
        'character is and what they are doing (the BEFORE; positions + held action, e.g. "Fuzzby frame-left mid-hover '
        'eyes closed, Zenny frame-right watching"; NO motion words), so the ONE opening keyframe is drawn from it,\n'
        '  "keyframePrompt"/"i2vPrompt": LEGACY, OPTIONAL fields — the real keyframe and Seedance prompts are '
        'compiled mechanically from startState/cuts/plate/turnarounds by cb_prompts.py/cb_segprompt.py, never '
        'from these. If authored at all, keyframePrompt is a rough self-contained t2i sketch of the OPENING '
        'frame (reference-only — never describe a bear) and i2vPrompt is a rough sketch of the beat\'s action '
        'across its cuts — but NEVER write spoken dialogue words into either (Law 6: no generation prompt ever '
        'carries the words a character says, lip-sync included). Leave both blank if there is nothing useful '
        'to add beyond what startState/cuts already say,\n'
        '  "soundIntent": the SFX + timed-music cues Seedance should score (the bonk on the tree, the button on the deflate); the bear\'s note where it lands,\n'
        '  "continuity": {"opensFrom": how this beat\'s opening frame hands off the previous beat\'s last frame, '
        '"carryToNext": what carries forward, "screenDirection": "LEFT"|"RIGHT" (locked at scene open)},\n'
        '  "check": {"focalSubject":str,"emotionalRead":what they should FEEL,"heartCheck":"what the CHILD feels AND '
        'what the PARENT feels at this beat"},\n'
        "  // ── THE MANIFEST LAYER — required on every beat (Gate-3 prompt compiler + QA read these directly) ──\n"
        '  "endState": directing prose (1-3 sentences) for THIS beat\'s own distinct ending — a living settle, in '
        'character, using this beat\'s own cast\'s real acting register. This is NOT a restatement of the PREVIOUS '
        'beat\'s pose — it is a new, distinct final moment (it becomes the anchor the NEXT beat opens from),\n'
        '  "endStateStill": the SAME instant as endState, described as a static photograph: NO temporal verbs '
        '("settles into", "turns to", "begins to"), NO imperatives, NO camera or ambience — only subjects, poses, '
        'positions, and expressions, exactly as one frozen frame would show them (e.g. endState "he holds it one '
        'blink too long" -> endStateStill "frozen mid-hover"),\n'
        '  "carryMarks": a SHORT phrase (never a full sentence) naming what specifically, visibly persists INTO '
        'THIS BEAT\'S OWN OPENING from the beat immediately before it (a held object, wet fur, a costume state, '
        'a physical position) — if genuinely nothing persists, say so explicitly and briefly ("no persisting '
        'marks — a clean reset"). This is backward-looking: describe what THIS beat inherits, not what it '
        'hands off to whatever comes after it — the automatic join-check compares this exact field against the '
        'previous beat\'s own rendered ending, so getting the direction right here is what makes that check '
        'mean anything,\n'
        '  "junctionType": "intentional_next_shot" for EVERY beat except a scene\'s own FIRST beat (which has no '
        'predecessor to join from — leave this null ONLY for beat 1 of a scene). "intentional_next_shot" is the '
        'DEFAULT for every other beat: a new gag arc, a fresh camera setup, NOT a continuation of the exact same '
        'shot. Only use "seamless_continuation" in the rare case where your own cut EXPLICITLY continues one '
        'unbroken take across the beat boundary — never by omission, never as a lazy default,\n'
        '  "opensOn": {"who": name, "action": a SHORT phrase for their immediate mid-motion state} — WHO the camera '
        'opens on and what they\'re doing the instant this beat begins, grounded in this beat\'s own cut 1. '
        'REQUIRED for every beat except a scene\'s own first beat (null there — a scene opener has no such '
        'reaction-bridge to describe),\n'
        '  "relayOpeningNote": OPTIONAL, null on most beats — ONE extra sentence for a relay beat\'s opening-'
        'frame reference, naming what breaks IMMEDIATELY after the anchor frame (who moves first, what pose '
        'is broken) when carryMarks/opensOn alone leave real ambiguity about that instant. Leave null unless '
        'the beat genuinely needs it — this is not a place to restate opensOn in different words,\n'
        '  "spatialAxis": OPTIONAL, null on most beats — a fixed ONE-SENTENCE blocking law for this beat (who '
        'occupies which lane/side of frame, an explicit "never swap sides" if that matters here) — only when '
        'the scene\'s own blocking genuinely benefits from stating a standing spatial rule beyond what '
        'startState already establishes (e.g. a beat where the director wants a locked left/right axis held '
        'across a chase or a two-shot). Leave null for a beat where blocking is already clear from staging,\n'
        '  "stagingProhibited": OPTIONAL, null on most beats — a short list of THIS beat\'s own specific gag-'
        'failure modes to forbid (e.g. "Fuzzby disappearing into the flower", "full-face pollen coating"), '
        'each phrase written WITHOUT its own leading "no" (that gets added mechanically). Only for a beat whose '
        'own physical gag has a real, specific way to go visibly wrong beyond what the twelve standing '
        'negatives already cover — never a restatement of the standing negatives in different words,\n'
        '  "actingContrast": one sentence — which characters in this beat play off each other and how (e.g. manic '
        'vs deadpan, urgency vs stillness). For a SOLO-character beat, describe the INTERNAL contrast within that '
        'one character\'s own performance instead (surface vs interior),\n'
        '  "humourLayer": an integer 1-4, this scale exactly (the studio\'s Layered-Humour model): '
        '1 = pure physical/visual comedy a toddler reads instantly (shape, motion, sound, no timing needed); '
        '2 = a comic beat a 4-8 year old actually GETS (character behaviour, an expected gag lands); '
        '3 = dual-register — lands for the kid AND the watching adult catches something extra (irony, character '
        'insight, a callback); 4 = mostly an adult/craft-level wink (rewards a rewatching co-viewer; the kid may '
        'miss it entirely). Judge each beat honestly by its OWN content — a quiet Heart beat can still be layer 1 '
        '(a small physical truth) even with little comedy,\n'
        '  "emotionMechanic": one sentence stating the CONCRETE visual/physical mechanism that makes this beat\'s '
        'emotion legible on screen (a glow, a specific gesture, a held breath, a physical gag) — never a '
        'restatement of "emotionalIntent",\n'
        '  "fidelityAllocation": {"primary": name, "secondary": name or "none", "economized": comma-separated '
        'names or "none"} — an explicit choice, every beat, of who this beat\'s craft budget actually spends on. '
        '"primary" is the ONE named character this beat genuinely needs precise expression/performance from — '
        'ALWAYS a real name, even a solo beat (that character IS the primary). "secondary" is the ONE character '
        'playing off primary (or "none" for a genuinely solo beat). "economized" names every OTHER character '
        'present in this beat\'s own cast who is deliberately kept generic/background here — not doing anything '
        'distinct, not needing individual performance, staged as an ensemble rather than as themselves. A beat '
        'demanding perfect performance from every named character at once is the failure mode this field exists '
        'to prevent — an ensemble scene should usually have 1-2 primary/secondary characters and the rest '
        'economized, not everyone treated equally,\n'
        f'  "director_mode": YOUR choice of this beat\'s emotional register, made HERE — not guessed at later by '
        f'a machine reading your prose back. One of: {_modes}. Null only for a beat with no strong emotional '
        'engine at all (rare),\n'
        f'  "physical_action_archetype": when this beat carries a real physical/comic engine, YOUR choice of '
        f'which pattern it\'s built from. One of: {_archs}. Choose the one whose own staging beats actually '
        'match what you just wrote in cuts[] above — this is you naming the shape of the gag you already '
        'staged, not inventing a new one. Null for a beat with no physical engine (a pure dialogue/reaction '
        'beat)\n'
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
    _finalize_beat_manifest_fields(fixed)   # FOUND 2026-07-07: the repair call returns entirely NEW beat objects
    # that never passed through this defensive layer (it only ran once, on the ORIGINAL draft, before this
    # function was even called) — if the repair call's own output still has a missing/invalid junctionType or
    # opensOn (a real possibility: the repair prompt below only names the SPECIFIC problems found, so it can
    # leave an unrelated field exactly as broken as before, or introduce a new gap), that's a MECHANICALLY
    # fixable default my own layer already knows how to apply, not something worth halting Gate 1 over. Applying
    # it here, before the final beat_problems() re-check, means a genuinely unrelated repair (e.g. a bad
    # humourLayer) doesn't ALSO cost a hard stop over a field this session already knows how to default safely.
    still = S.beat_problems(fixed, scene)
    if still:
        raise SceneBreakdownError(scene["sceneNumber"], scene.get("name", ""),
                                  "still invalid after one repair: " + "; ".join(still[:4]))
    log(f"      validate: scene {scene['sceneNumber']} repaired ✓", flush=True)
    return fixed

# ── Stage C — ASSEMBLE + WRITE ───────────────────────────────────────────────
def _derive_north_star_answers(all_beats, scenes):
    """THE MANIFEST LAYER, package-scoped (rule 46, 2026-07-07): cb_preflight BLOCKs on this field being
    non-blank. Built ENTIRELY MECHANICALLY from the real, already-authored package data plus the actual canon
    text (CRYSTAL_BEARS_LOCKED_CANON.md §0) — no LLM call, nothing invented, so this costs nothing extra and
    never drifts from what canon actually says (the exact gap cb_preflight.check_package_creative itself
    named: 'canon does not define a literal six questions... the field missing AND the exact six questions
    need Julian's own definition'). Presence-only check downstream; whether the episode actually LANDS this
    test stays the reserved showrunner verdict (rule 28) — this documents structural evidence, never a
    quality verdict."""
    wordless = [b.get("beatCode") for b in all_beats if b.get("wordlessHeld")]
    big_by_pillar = {}
    for b in all_beats:
        pillar = str(b.get("pillar") or "").strip().lower()
        if str(b.get("comedyMode") or "").upper() == "BIG":
            big_by_pillar.setdefault(pillar, []).append(b.get("beatCode"))
    non_heart_pillars = sorted({str(s.get("pillar") or "").strip().lower() for s in scenes} - {"heart"})
    missing_laugh = [p for p in non_heart_pillars if not big_by_pillar.get(p)]
    return {
        "note": "Best-effort package-level answer to the North Star test (CRYSTAL_BEARS_LOCKED_CANON.md §0), "
                "derived mechanically from this package's own data — never invented. Canon states 4 test "
                "questions + 8 craft laws, not a literal 'six questions'; Julian's own definition of the exact "
                "six is still needed before this field can be more than 'answered honestly against what canon "
                "actually says.'",
        "testQuestions": {
            "laughOutLoud": f"Comedy-forward beats tagged comedyMode=BIG: {sum(len(v) for v in big_by_pillar.values())} "
                             f"across the episode ({', '.join(f'{p}: {len(v)}' for p, v in sorted(big_by_pillar.items())) or 'none'}).",
            "breatheIn": (f"Exactly one wordlessHeld beat, the episode's own nadir: {wordless[0]}."
                          if len(wordless) == 1 else
                          f"WARNING — expected exactly ONE wordlessHeld beat (craft law 4); found {len(wordless)}: {wordless}."),
            "crystalTellsTruth": "Checked per beat via each beat's own crystalTruth field (required, non-blank on "
                                  "every beat) — not independently re-verified for contradiction-with-the-face here; "
                                  "see craft law 1 below.",
            "reachesKidAndParent": "Every beat carries both kidRead and adultRead (required fields); every scene "
                                    "carries its own parentLine (required field) — structural coverage confirmed, "
                                    "content quality is Julian's own reserved verdict.",
        },
        "craftLaws": {
            "1_crystalIsNeedNotMood": "Structurally required on every beat via crystalTruth — not independently "
                                        "re-audited for genuine face-contradiction here.",
            "2_wantVsNeedNamedEveryBeat": "Structurally guaranteed — want/need are required fields on every beat.",
            "3_surrenderNotPowerUp": "Not mechanically checkable (a tone judgment) — Julian's own reserved verdict; "
                                      "known past drift pattern: a Crystal Call reading as a power-up activation "
                                      "rather than a sincere settle (see CLAUDE.md rule 46).",
            "4_oneWordlessHeldBeat": (f"Confirmed exactly one: {wordless[0]}." if len(wordless) == 1
                                       else f"NOT satisfied — {len(wordless)} wordlessHeld beat(s) found, expected 1."),
            "5_playIsTheVehicle": "Present via each beat's own optional theGame field where authored — not audited "
                                    "for completeness here.",
            "6_catchAndRelease": "Addressed via each beat's own pauseHold (a single named hold, capped <=1.5s per "
                                   "the staging law) — not independently re-verified per beat here.",
            "7_holdTheAcheBittersweet": "A tone judgment reserved for Julian's own eye — not self-certified here.",
            "8_noteCarriesFeeling": "Not audited — each bear's canon musical note is a Gate-5/post-scoring concern, "
                                     "not a Gate-1 storyboard field.",
        },
        "laughPerNonHeartPillar": (f"All {len(non_heart_pillars)} non-Heart pillar(s) present in this episode have "
                                     f"at least one comedyMode=BIG beat." if not missing_laugh else
                                     f"WARNING — pillar(s) with no comedyMode=BIG beat: {missing_laugh}. "
                                     f"(cb_preflight checks this per-pillar across the whole package, not per scene "
                                     f"in isolation — rule 46.)"),
        "caveat": "Structural/presence evidence only, derived mechanically from this package's own authored "
                  "fields and canon's own text — never a quality verdict. Whether the episode actually LANDS "
                  "this test emotionally is Julian's reserved showrunner verdict (rule 28).",
    }


def direct(script_path, episode, title, log=print):
    script_p = pathlib.Path(script_path)
    script = script_p.read_text()
    # THE GATE-0 PROVENANCE HARD BLOCK — see this module's own docstring for the full ruling. Raises
    # (never sys.exit's itself — matches this codebase's own "never sys.exit itself" convention,
    # cb_pipeline.fire()'s docstring) a plain RuntimeError, distinct from any other exception this
    # function might raise, so a caller (cb_pipeline.gate1()) can catch it specifically and refuse
    # cleanly instead of crashing with a raw traceback.
    sidecar_p = script_p.parent / (script_p.stem + ".score.json")
    if not sidecar_p.exists():
        raise RuntimeError(
            f"GATE 1 REFUSED — no Gate-0 record found for {script_p.name} (expected a sidecar at "
            f"{sidecar_p.name}, same folder). Every script must be produced by the Writers' Room "
            f"(cb_writer.write, Gate 0) before Gate 1 can break it down — a script pasted/uploaded "
            f"directly, bypassing Gate 0, has no scorecard and no record of ever being reviewed "
            f"against the Show Bible/North Star. Run Gate 0 first."
        )
    try:
        _prov = json.loads(sidecar_p.read_text())
    except Exception as e:
        raise RuntimeError(f"GATE 1 REFUSED — {sidecar_p.name} exists but is not valid JSON ({e}); "
                            f"cannot confirm this script's Gate-0 provenance.")
    if "belowBar" not in _prov:
        raise RuntimeError(
            f"GATE 1 REFUSED — {sidecar_p.name} exists but has no 'belowBar' field, so it doesn't "
            f"match the shape cb_writer.write() (Gate 0) produces — cannot confirm this script's "
            f"Gate-0 provenance. Run Gate 0 first, or fix the sidecar's shape if it's a real (if "
            f"differently-authored) Gate-0 record."
        )
    if _prov.get("belowBar"):
        log(f"  ⚠ Gate-0 provenance confirmed, but this script SHIPPED BELOW THE BAR "
            f"({sidecar_p.name}) — review it before treating the resulting storyboard as final.", flush=True)
    system, chars = _mind()
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
                        _beats = scene_to_beats(system, script, bm, sc, theme, chars, _elems, retry_note=retry_note); break
                        # NOTE (2026-07-15): a two-stage split (direct_scene_creative + deliver_beat_manifest,
                        # both still defined below) was built and tested tonight against the "why isn't the
                        # Director producing Pixar-level staging" question. Tested on Scene 1 via cb_craft's
                        # own rubric: no improvement (same-or-worse on 2/5 criteria vs this single-shot path).
                        # Reverted to the proven path for the real, full-episode fire rather than run an
                        # unproven, single-scene-tested architecture change at real cost — Julian's own call
                        # ("even if we're not entirely happy with it, we're gonna run with it") was to stop
                        # iterating on craft process and push the pipeline forward, not to gamble on this.
                        # The two functions are kept, not deleted, in case a future, more careful test (the
                        # multiple-independent-drafts/judge-panel idea discussed the same night) picks this up.
                    except (Exception, SystemExit) as e:
                        # widened to SystemExit too — scene_to_beats() calls straight into cb_llm.structured(),
                        # which deliberately raises SystemExit (a BaseException) on a provider-level failure; a
                        # bare "except Exception" here would let attempt 1's provider hiccup skip the intended
                        # 2-attempt retry entirely instead of logging and trying again (rule 46 bug class).
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
                _finalize_beat_manifest_fields(_beats)      # defense-in-depth defaults for junctionType/opensOn (rule 46)
                _beats = validate_scene_beats(system, script, bm, sc, theme, _beats, log=log)   # rules 5-7: Pydantic + business rules
                _drop, _dup = [], []
                if _scene_dialogue:                          # HARD VERBATIM GATE — snap every line back to the writer's EXACT words
                    _beats, _drop, _dup = enforce_verbatim(_beats, _scene_dialogue, sc["sceneNumber"], log=log)
                # THE MOTION CONTRACT SELF-CORRECTION (2026-07-15, "get it right first time") — after the
                # verbatim gate (dialogue is never touched; only cut action prose is reshaped), any cut still
                # reading as a checklist of separately-clocked actions is corrected through the Director's own
                # voice HERE, at authoring time, instead of surfacing downstream as a Gate-3 flag for Julian
                # to glance at. See motion_contract_pass's own docstring for the full story.
                _mc_fixed = motion_contract_pass(_beats, sc, log=log)
                if _mc_fixed:
                    log(f"      motion contract: {_mc_fixed} cut(s) self-corrected at authoring time", flush=True)
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
            except (Exception, SystemExit) as e:
                # cb_llm.structured() deliberately raises SystemExit (a BaseException, not caught by "except
                # Exception") on any OpenAI provider-level failure — its documented fail-loud design for the
                # primary authoring path. derive_plate() calls straight into it, so this catch must widen to
                # SystemExit too, or a provider hiccup here would abort the whole Gate-1 fire instead of just
                # falling back to the beat-map location as this comment always promised (rule 46 bug class).
                log(f"      ⚠ derive_plate skipped ({str(e)[:60]}) — kept the beat-map location", flush=True)
            sc["performanceThroughline"] = _derive_performance_throughline(beats)   # mechanical, from the beats
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
        "northStarAnswers": _derive_north_star_answers(all_beats, scenes),
    }
    OUT.mkdir(exist_ok=True)
    pkg_path = OUT / f"{episode}_{P.slug(title)}_beat_package.json"
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)

    # locations.json — MERGE into the existing per-episode dict; never rebuild the whole file. These configs are
    # shared, multi-episode registries (config/locations.json holds one entry PER episode) — overwriting the whole
    # dict here would silently DELETE every other episode's location plates/master paths the moment Gate 1 runs for
    # just one episode. Only this episode's own key is ever replaced.
    locp = HERE / "config" / "locations.json"
    L = json.load(open(locp)) if locp.exists() else {}
    L.setdefault("_note", "")
    # FIXED 2026-07-11 (full-codebase audit): this used to hardcode "master": None for EVERY scene on every
    # Gate-1 (re)fire, discarding any previously signed-off Gate-2a plate path unconditionally — including for
    # scenes redirect() didn't materially change, and WITHOUT cascading the corresponding locked.json gate
    # flags the way unapprove()/_relock_if_stale both correctly do when they reset this same field, leaving
    # the two files inconsistent (locked.json still says "2a": approved while the plate path silently vanished).
    # Now preserves each scene's existing master (and other prior fields not being freshly authored here) —
    # a genuine Gate-1 content change is still caught and cascaded correctly by _relock_if_stale's own
    # fingerprint check on the next gate-status read, which resets master IN STEP with the lock flags.
    _prior = L.get(episode, {})
    L[episode] = {}
    for sc in scenes:
        _sn = str(sc["sceneNumber"])
        _prior_master = (_prior.get(_sn) or {}).get("master")
        L[episode][_sn] = {
            "name": sc["name"], "locationId": sc.get("locationId", ""),
            "sceneShotName": sc.get("sceneShotName", ""), "master": _prior_master,
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
    except (Exception, SystemExit) as e:
        # cb_director_eye.run() calls straight into cb_llm.structured(), which deliberately raises SystemExit
        # (a BaseException, NOT caught by "except Exception") on any OpenAI provider-level failure — its
        # documented fail-loud design for the primary authoring path. This runs AFTER the beat package is
        # already written to disk, so a provider hiccup here must degrade to a manual-review note, never take
        # down an otherwise-successful Gate 1 — widened to catch SystemExit too, or this comment's own promise
        # would be defeated (rule 46 bug class).
        log(f"  ⚠ Director's Eye skipped ({str(e)[:120]}) — review manually before signing off Gate 1.", flush=True)

    return {"package": str(pkg_path), "scenes": len(scenes), "beats": len(all_beats)}

if __name__ == "__main__":
    os.chdir(HERE)
    if len(sys.argv) < 4:
        sys.exit('usage: python3 cb_director.py <script.txt> <Ep> "<Title>"')
    r = direct(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(r, indent=1))
