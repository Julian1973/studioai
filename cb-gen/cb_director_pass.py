#!/usr/bin/env python3
"""THE DIRECTOR'S PASS — the missing soul of Gate 3.

Before cb_seedance writes the render prompt, an actual PIXAR DIRECTOR reads each character's BIBLE (essence,
vulnerability, emotionalDNA, mannerisms, relationships, staging, comedyEngine, onPoint, dos/donts) + the right
Pixar MIND for the beat's director_mode + the NORTH STAR, and DIRECTS this beat: the specific acting, the
expressions (eyes spinning on the crash; edging behind Zenny when the storm breaks), the comic/emotional timing,
and a real CAMERA breakdown (sweeping follow through the flowers, close-up on the eyes, cut to the reaction).

It returns a structured DirectorPass that cb_seedance folds into the compact's performance / camera / action_timeline,
REPLACING the generic mode-templated, flat, single-locked-shot directing that made the recent renders boring.

LLM-driven (cb_llm / OpenAI gpt-5.5, the same engine as the Gate-1 Director) — direction, NOT rendering.
Gated by CB_DIRECTOR_PASS (1=on). Fails OPEN: any error -> returns None and cb_seedance falls back to the old fields.
"""
import os, json
import cb_prompts as P

# ── the right Pixar MIND per director_mode (who is in the chair for this beat) ──────────────────────────────────
PIXAR_MINDS = {
 "COMEDY_PHYSICAL": "John Lasseter (real weight, squash & stretch — the gag has MASS), Tex Avery (go BIG, push the scale), "
                    "Chuck Jones (timing — the held beat and the delayed take). Lead with the BODY; the crash is the gift.",
 "COMEDY_DEADPAN":  "Chuck Jones + the Bluey dry wit — the straight character barely moves; the laugh is contrast and the held deadpan stare.",
 "COMEDY_RELEASE":  "Lasseter + Joe Brumm — tension snaps into a warm, slightly absurd laugh; relief you can feel.",
 "TENDER_LEAVING":  "Pete Docter (Up, Inside Out) — emotion in the eyes, the breath, the held pause; a small body doing a big feeling.",
 "QUIET_KNOWING":   "Pete Docter — stillness, a knowing look, the wordless beat that says everything.",
 "ADVENTURE_WONDER":"Docter + Andrew Stanton — wide-eyed discovery, the eager lean, the world opening up.",
 "RISING_UNEASE":   "Docter + Brumm — the WORLD shifts first; the character notices; they get smaller, quieter, watchful.",
 "STORM_PANIC":     "Pete Docter — fear is real but child-safe; they seek safety in EACH OTHER; eyes wide, body small, breath quick.",
 "EMERGENCY_DISCOVERY":"Stanton — comic chatter cut dead by a hard stop; the distant danger lands; urgency without chaos.",
 "RESCUE_JEOPARDY": "Andrew Stanton (Finding Nemo water) + Lasseter weight — clear geography, real force, effort you feel in the body.",
 "COURAGE_CHOICE":  "Docter — they SEE the danger, understand the risk, and choose to act anyway; the choice is bigger than the fear.",
 "RELIEF_RELEASE":  "Brumm + Docter — the danger breaks; a breath, a laugh, movement toward safety and each other.",
 "ARRIVAL_WONDER":  "Docter — arrival, new faces, a gentle welcome, awe; the music swells, the eyes widen.",
 "BELONGING_HOME":  "Joe Brumm (Bluey) — gratitude, a pause, quiet acceptance; the ordinary made tender.",
 "MAGIC_CEREMONY":  "Pete Docter — recognition, a crystal state-change, inner confidence; the magic is SURRENDER, never a power blast; group warmth.",
}
_DEFAULT_MIND = "Pete Docter + John Lasseter + Joe Brumm — character first, feeling on the outside, never flat or generic."

NORTH_STAR = ("Take Inside Out to the next level: put the FEELING on the OUTSIDE. The audience SEES and HEARS the inner "
              "state — through staging, expression, body and the crystal — and the body reveals (or masks) the want vs the "
              "need. No villain; the drama is emotional and physical. Bluey-level co-watch: the child laughs at the body, "
              "the adult feels the truth underneath.")

def _mind_for(mode):
    return PIXAR_MINDS.get((mode or "").upper(), _DEFAULT_MIND)

def _bible_brief(name):
    """Pull the character's bible into a compact directing brief (only the fields a director acts on)."""
    b = (P.CHARACTERS.get(name) or {}).get("bible") or {}
    if not isinstance(b, dict):
        return f"{name}: (no bible — direct from the reference image only)"
    def g(k, n=420):
        v = b.get(k)
        if isinstance(v, list): v = " · ".join(str(x) for x in v)
        v = str(v or "").strip()
        return (v[:n] + "…") if len(v) > n else v
    rows = [("ESSENCE", g("essence")), ("WHO THEY ARE", g("whoTheyAre")), ("VULNERABILITY", g("vulnerability")),
            ("EMOTIONAL DNA", g("emotionalDNA")), ("MANNERISMS", g("mannerisms")), ("RELATIONSHIPS", g("relationships")),
            ("STAGING", g("staging")), ("COMEDY ENGINE", g("comedyEngine")), ("VOICE", g("voice", 200)),
            ("ON-POINT TEST", g("onPoint")), ("DO", g("dos")), ("DON'T", g("donts"))]
    return f"=== {name} ===\n" + "\n".join(f"  {k}: {v}" for k, v in rows if v)

def _schema():
    """The DirectorPass Pydantic schema — defined lazily so importing this module never requires pydantic."""
    from pydantic import BaseModel, Field
    from typing import List
    class DirectedShot(BaseModel):
        time: str = Field(description="time window within the beat, e.g. '0-2s', '5-7s'")
        action: str = Field(description="the SPECIFIC, character-true physical action + expression in this shot — drawn from who they ARE, never generic; the body leads")
        camera: str = Field(description="the shot size + camera MOVE — bold and cinematic (e.g. 'wide sweeping follow chasing Fuzzby low through the flower lane', 'snap to a tight close-up on his eyes spinning', 'cut to Zenny — locked, deadpan')")
        point: str = Field(description="the single comic or emotional point THIS shot lands")
    class VoiceLine(BaseModel):
        speaker: str = Field(description="the character who speaks this line")
        acted_line: str = Field(description="the LOCKED dialogue words for this line with ElevenLabs V3 audio tags placed for the CADENCE and emotional ARC — proud on one part, a whisper/wobble/crack on another, the delivery riding the beat. Use ONLY these canon tags: [proudly] [excited] [deadpan] [nervous] [calm] [cheerfully] [curious] [sorrowful] [frustrated] [tired] [playfully] [regretful] [whispers] [singing]. NEVER change, add or drop a WORD — only place tags (a tag at each point the delivery shifts).")
        note: str = Field(description="one or more adjectives describing the delivery + cadence (e.g. 'proud and pompous, building, then a small swallowed wobble of doubt on the last word')")
    class DirectorPass(BaseModel):
        performance: str = Field(description="the acting truth for the lead character in THIS beat, drawn from their bible (essence/vulnerability/comedyEngine) — specific to them, never a generic mode note")
        expression: str = Field(description="the specific face / eye / body expressions that sell the inner state (the close-up-worthy detail)")
        camera_approach: str = Field(description="the overall camera philosophy for this beat — dynamic, character-following, cinematic; sweep and follow and close in; never flat or static unless the emotional beat demands stillness")
        shots: List[DirectedShot] = Field(description="the timed shot breakdown — the camera + acting, beat by beat, covering the whole duration")
        comedy_or_heart_note: str = Field(description="the engine driving this beat — the precise gag mechanism (for comedy) or the emotional truth (for heart)")
        serves_the_why: str = Field(description="how THIS beat's directing serves its PURPOSE: the WANT played on the surface, the NEED bleeding through underneath, and the two-level read — what the child sees vs what the adult feels")
        voice_direction: List[VoiceLine] = Field(description="how each spoken line is ACTED in the ElevenLabs voice — the locked words with V3 tags for the cadence and emotional arc (proud → wobble → whisper as the beat demands), so the voice plays the want vs need; [] if no dialogue this beat")
    return DirectorPass

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_director_pass")
# bump when the director PROMPT/logic changes — it invalidates every cached direction so renders are never stale
DIRECTOR_PASS_VERSION = "v4-voice-acting-2026-06-30"

def _cache_path(episode, code):
    return os.path.join(_CACHE_DIR, f"{episode}_{code}.json")

def _fingerprint(beat, mode, archetype, characters, dialogue_lines):
    """A hash of EVERYTHING the direction depends on — the version + mode + archetype + the beat's why/action/dialogue
    + each present character's FULL bible. If ANY of these changes, the cached direction is stale and is re-run, so a
    render can never ship old directing."""
    import hashlib
    parts = [DIRECTOR_PASS_VERSION, str(mode), str(archetype), "|".join(characters or [])]
    for k in ("want", "need", "crystalTruth", "kidRead", "adultRead", "theGame", "emotionalIntent", "pillar",
              "startState", "audience_feeling_target", "emotional_function", "storyBeat"):
        parts.append(str(beat.get(k) or ""))
    parts.append(" ".join(str((c or {}).get("action", "")) for c in (beat.get("cuts") or [])))
    parts += list(dialogue_lines or [])
    for n in (characters or []):
        b = (P.CHARACTERS.get(n) or {}).get("bible")
        parts.append(json.dumps(b, sort_keys=True, ensure_ascii=False) if isinstance(b, dict) else str(b))
    return hashlib.md5("||".join(parts).encode("utf-8")).hexdigest()

def cached_voice_direction(episode, code):
    """Pure cache read (NO LLM): the director's voice_direction for an already-directed beat, else None. The
    SOFTWARE-WIDE safety net — any voice path picks up the director's acting even if it didn't pass it explicitly."""
    try:
        cached = json.load(open(_cache_path(episode, code)))
        if isinstance(cached, dict):
            return (cached.get("result") or {}).get("voice_direction")
    except Exception:
        pass
    return None

def direct_beat(beat, sc, mode, archetype, archetype_rules, characters, duration, emotional_function, dialogue_lines, episode="Ep1"):
    """Run the Director's Pass for one beat. CACHED per (episode, beat) so previews/dry-runs don't re-call the LLM —
    CB_DIRECTOR_PASS_REFRESH=1 forces a fresh direction. Returns the DirectorPass dict, or None (fail-open) when off /
    on any error (cb_seedance then falls back to the old mode-template fields)."""
    if os.environ.get("CB_DIRECTOR_PASS", "1") in ("", "0", "false", "False", "no"):
        return None
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    cp = _cache_path(episode, code)
    fp = _fingerprint(beat, mode, archetype, characters, dialogue_lines)
    refresh = os.environ.get("CB_DIRECTOR_PASS_REFRESH", "") not in ("", "0", "false", "False", "no")
    if os.path.exists(cp) and not refresh:
        try:
            cached = json.load(open(cp))
            if isinstance(cached, dict) and cached.get("_fingerprint") == fp:
                return cached.get("result")            # FRESH — version + inputs + bibles all unchanged
            # else: STALE (director logic / bible / why / script changed) — fall through and re-direct
        except Exception:
            pass
    try:
        import cb_llm
        cut_actions = " ".join(str((c or {}).get("action", "")).strip() for c in (beat.get("cuts") or []) if c)
        bibles = "\n\n".join(_bible_brief(n) for n in characters) or "(no named characters)"
        dlg = "\n".join(dialogue_lines) if dialogue_lines else "(no dialogue this beat)"
        def _w(k, n=320):
            v = str(beat.get(k) or "").strip(); return (v[:n] + "…") if len(v) > n else (v or "—")
        _why = ("THE WHY OF THIS BEAT — serve this ABOVE ALL (play the WANT on the surface, let the NEED bleed through):\n"
                f"  WANT (the face they play): {_w('want')}\n"
                f"  NEED (the truth underneath): {_w('need')}\n"
                f"  CRYSTAL TRUTH (what the feeling reveals): {_w('crystalTruth')}\n"
                f"  THE KID SEES: {_w('kidRead')}\n"
                f"  THE ADULT FEELS: {_w('adultRead')}\n"
                f"  THE GAME (the playful frame): {_w('theGame')}\n"
                f"  EMOTIONAL INTENT (what the audience should feel): {_w('emotionalIntent')}\n"
                f"  PILLAR (the SEL purpose this serves): {_w('pillar')}")
        system = (
            "You are the EPISODE DIRECTOR of 'The Crystal Bears' — a Pixar-grade animated comedy-with-heart for ages 4-8 "
            "(the Bluey co-watch + Inside Out emotional craft). For THIS beat you direct as:\n"
            f"  {_mind_for(mode)}\n\n"
            f"THE NORTH STAR: {NORTH_STAR}\n\n"
            "YOUR JOB: read the character as a real, SPECIFIC person (their bible is given) and DIRECT this beat — the "
            "acting, the expressions, the comic/emotional timing, and a real CAMERA breakdown. Make it FUNNY, ALIVE and "
            "CHARACTER-TRUE the way the best Pixar would. The BODY leads. The camera is a storyteller — it sweeps, follows, "
            "closes in on the eyes, cuts to the reaction; every shot lands a comic or emotional point. NEVER flat, rigid, "
            "static or generic. Honour the physical staging spine and never violate its prohibitions. NEVER change the "
            "dialogue — it is locked. When a character speaks, write it in that shot's action as: '<Name> speaks here, "
            "voiced ONLY by @Audio1 — lip-sync precisely to @Audio1 (its exact words and timing)'. Reference @Audio1 as the "
            "voice and do NOT write the spoken words — the words live in @Audio1 alone, so Seedance never generates a "
            "duplicate voice. Name the speaker; never 'a voice'.\n\nABOVE ALL, SERVE THE WHY: this beat exists for a reason (given below). Every "
            "choice — acting, expression, camera — must play the character's WANT on the surface while the NEED bleeds "
            "through underneath, so the child laughs at / thrills at / is moved by the body, and the adult feels the "
            "truth beneath it (the two-level kid-read vs adult-read). That gap between want and need IS the feeling on "
            "the outside — land it.\n\nALSO DIRECT THE VOICE: for every spoken line, ACT it — give the LOCKED words with V3 audio "
            "tags placed for the cadence and emotional arc (proud on the launch, a swallowed wobble of doubt on the "
            "cover-up, a whisper where the beat drops), all driven by the want vs need. One OR MORE tags per line, placed "
            "where the delivery shifts; never change, add or drop a word. Output structured directing.")
        user = (
            f"BEAT {code} — scene: {sc.get('name','')}\n"
            f"Director mode: {mode}  ·  feeling target: {beat.get('audience_feeling_target') or emotional_function}\n"
            f"Duration: {duration}s\n"
            f"{_why}\n"
            f"PHYSICAL STAGING SPINE (archetype {archetype} — honour it, never violate the prohibitions):\n  {archetype_rules}\n"
            f"Script action (re-direct it richer + character-true; keep the staged event): {cut_actions or '(none)'}\n"
            f"LOCKED dialogue (verbatim — direct around it, never reword):\n{dlg}\n\n"
            f"THE CHARACTER(S) — direct THEM, specifically, from who they are:\n{bibles}\n\n"
            "Now DIRECT this beat to the standard of the best Pixar physical comedy / heart: bold, specific, funny/true, "
            "with a real camera breakdown (sweep, follow, close-ups, cut to reactions). Cover the full duration.")
        out = cb_llm.structured(system, user, _schema(), label=f"director_pass_{code}").model_dump()
        out["directed_by"] = _mind_for(mode); out["director_mode"] = mode    # surface WHO directed (for the UI)
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            json.dump({"_fingerprint": fp, "_version": DIRECTOR_PASS_VERSION, "result": out},
                      open(cp, "w"), ensure_ascii=False, indent=1)
        except Exception:
            pass
        return out
    except SystemExit:
        raise
    except Exception as e:
        print(f"  director_pass: skipped ({str(e)[:120]}) — falling back to mode templates", flush=True)
        return None
