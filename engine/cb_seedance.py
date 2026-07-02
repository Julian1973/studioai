#!/usr/bin/env python3
"""cb_seedance.py — the REPEATABLE SEEDANCE 2 PROMPT CONTRACT (prompt-builder only).

A consistent, software-generated Seedance prompt system that preserves quality, feel, comedy, heart, reference
consistency, character identity, audio ownership and continuity across every BEAT. Two clear outputs:

  1) authoring_json  — the internal structured object the app stores (references, timeline, characters, audio,
                       constraints, continuity, creative mode).
  2) flattened_prompt — the clean natural-language text actually sent to Seedance, in a FIXED section order,
                        target 3,500–3,900 chars incl. negatives, under 4,000 where possible.

This is ADDITIVE — it does NOT replace cb_prompts.seedance_json (kept until this builder is wired + verified) and
touches NOTHING in the render path, voices, locks, security, UI or Gates 1/2a/2b. BEAT stays the production unit.

    build_seedance_authoring_json(beat, scene_context, refs, continuity, episode) -> dict
    flatten_seedance_prompt(authoring_json) -> str
    validate_seedance_prompt(prompt_text, authoring_json) -> {ok, rejects, warnings, length}
    build_for_beat(pkg_path, beat_code, episode) -> {authoring, prompt, report}   # convenience (gathers refs)
"""
import os, re, json, subprocess
import cb_prompts as P
import cb_director_pass

BEES = {k for k, v in P.CHARACTERS.items() if isinstance(v, dict) and "bee" in str(v.get("avoid", "")).lower()}

# ── C. CREATIVE MODES — structure + acting rule injected into the ACTION TIMELINE ────────────────────────────
MODE_GUIDANCE = {
 "COMEDY_SMALL": ("setup → tiny overconfidence → small mistake → recovery lie → dry reaction → hold",
    "Fuzzby moves too much; Zenny barely moves. The joke lands through contrast and stillness. Keep the action simple and readable."),
 "COMEDY_BIG": ("setup → anticipation → overconfident launch → clear mistake → big impact → rebound/tumble → false dignity → Zenny reaction → hold",
    "Stage the crash physically and readably. ONE clear impact, not many vague impacts. Show squash, rebound, follow-through and a final recovery pose. Do not rush the recovery lie."),
 "HEART_TRUE": ("stillness → breath → glance → small physical action → line → reaction → hold",
    "Keep movement minimal. Emotion lives in eyes, breath, posture and pauses. No comedy score, no busy camera. Let the silence work."),
 "STORM_TURN": ("normal rhythm → sound/lighting change → stillness → character notices → mood shift → held reaction",
    "Do not over-animate. Let the environment change first. Characters become smaller and quieter. Music drains rather than swells."),
 "ACTION_RESCUE": ("direction → obstacle → effort → consequence → renewed effort → result → handoff",
    "Keep geography clear. One major action per second maximum. Use body strain, eye direction, paw contact and environmental force. Do not bury dialogue inside chaotic motion."),
 "MAGIC_BEACON": ("stillness → shared intention → gentle glow → combined light → emotional reaction → handoff",
    "Crystals amplify inner qualities. Do not stage the magic like a weapon or power blast unless explicitly required. Use warmth, surrender, shared intention and guidance."),
}

# ── SHOT STYLE — a BEAT may contain multiple INTERNAL SHOTS; the camera serves the gag/emotion (no global one-take) ──
SHOT_STYLE_GUIDANCE = {
 "SINGLE_TAKE": "One continuous take with motivated cinematic camera movement; cut only if uninterrupted physical continuity truly demands it, and do not make it static unless the beat needs stillness.",
 "CINEMATIC_CUTS": "Intentional cinematic coverage; cut only with a clear purpose; preserve identity, screen direction, lighting and props across every cut.",
 "COMEDY_CUTS": "Pixar comedy coverage — wide setup (geography + body scale) → medium/tracking for the overconfidence → wide/impact for the crash → close or medium close-up for the ridiculous visual payoff → reaction shot for the straight character → final wide/medium hold for the laugh. Protect the gag rhythm: setup → anticipation → visual payoff → character misread → reaction line → hold.",
 "HEART_COVERAGE": "Gentle coverage — soft wide establishing → medium emotional acting → close-up on eyes/breath/small gesture → reaction → quiet final hold. Do not overcut; emotion lives in stillness, eyes, posture and breath.",
 "ACTION_COVERAGE": "Clear action geography — wide geography → medium effort → obstacle/impact → reaction/consequence → handoff. Keep screen direction clear; avoid chaotic cutting.",
 "MAGIC_COVERAGE": "Graceful coverage — wide shared space → close-up on intention/face → crystal/light detail if canonically present → group reaction → final warm hold. Crystals amplify inner qualities; never a weapon blast unless explicitly required.",
}
_MODE_TO_STYLE = {"COMEDY_BIG": "COMEDY_CUTS", "COMEDY_SMALL": "COMEDY_CUTS", "HEART_TRUE": "HEART_COVERAGE",
                  "STORM_TURN": "CINEMATIC_CUTS", "ACTION_RESCUE": "ACTION_COVERAGE", "MAGIC_BEACON": "MAGIC_COVERAGE"}

# ── EPISODE DIRECTOR SYSTEM — 15 universal emotional modes ABOVE the character-specific rules. Every beat is
#    classified by WHAT THE AUDIENCE SHOULD FEEL, which drives camera, acting, music, pacing and the prompt. ───────
DIRECTOR_MODE_GUIDANCE = {
 "COMEDY_PHYSICAL": {"feeling": "laughter",
   "structure": "setup → anticipation → mistake → impact → false dignity → reaction → hold",
   "camera": "wide for body comedy, medium for performance, a reaction shot, a final hold",
   "music": "light and bouncy, sparse around the punchlines",
   "performance": "MANIC physical comedy — the lead is frantic, over-eager and over-confident: he flies FAST and erratically, zig-zags, overshoots and careens, then crashes HARD with big exaggerated squash-and-stretch and a springy rebound. NEVER calm, gentle, measured or a 'formal little flourish'. The straight character stays almost still — the joke lands through that contrast and his total lack of self-awareness"},
 "COMEDY_DEADPAN": {"feeling": "dry laughter",
   "structure": "absurd behaviour → still reaction → dry line → hold",
   "camera": "protect the reaction timing; hold just long enough for it to land",
   "music": "minimal and dry — do not over-score",
   "performance": "tiny eye movement, a blink, a small head tilt; minimal body motion"},
 "TENDER_LEAVING": {"feeling": "love, sadness and a brave beginning",
   "structure": "preparation → checking → parent pride mixed with sadness → meaningful gift → promise → goodbye",
   "camera": "gentle coverage, medium close-ups, held eye contact, hands/paws on the wristbands, the parent's tearful smile",
   "music": "warm and restrained, emotional but not melodramatic",
   "performance": "small pauses, swallowed emotion, forced bravery — never staged as action or comedy"},
 "QUIET_KNOWING": {"feeling": "calm, mystery and trust",
   "structure": "stillness → sound/ritual → vision → recognition → decision",
   "camera": "slow, graceful, close detail shots, soft movement",
   "music": "gentle, spiritual, minimal",
   "performance": "eyes, breath, a small paw movement, calm certainty"},
 "ADVENTURE_WONDER": {"feeling": "excitement and innocence",
   "structure": "new world → surprise → curiosity → play → growing confidence",
   "camera": "open, bright, moving with the discovery",
   "music": "light adventure",
   "performance": "big eyes, delighted turns, eager leaning forward"},
 "RISING_UNEASE": {"feeling": "that something is coming",
   "structure": "normal rhythm → small disruption → repeated warning signs → the character notices → mood shift",
   "camera": "wider skies, moving clouds, environmental inserts, a character glance",
   "music": "warmth drains slowly",
   "performance": "do not overplay the danger too early"},
 "STORM_PANIC": {"feeling": "fear and vulnerability",
   "structure": "gust → loss of control → object lost → isolation → fear → self-grounding",
   "camera": "unstable but readable, rain, close-up breathing, wide isolation",
   "music": "tense and low, not too loud",
   "performance": "quick breathing, a tight grip, a frozen pause, then a deliberate calming breath"},
 "EMERGENCY_DISCOVERY": {"feeling": "concern and urgency",
   "structure": "comic chatter → sudden stop → distant danger → realisation → urgency",
   "camera": "cut from the character's face to the distant danger, then back to the reaction",
   "music": "the comedy drains into concern",
   "performance": "the comic lead's comedy drains for one beat; the straight character becomes focused"},
 "RESCUE_JEOPARDY": {"feeling": "fear, urgency and hope",
   "structure": "clear danger → first failed attempt → current worsens → strength fading → pressure rises → final effort",
   "camera": "clear geography, underwater force, close effort, wide danger",
   "music": "tense and pulsing, ducked under dialogue",
   "performance": "strain, a slipping grip, eye focus, bubbles, body resistance"},
 "COURAGE_CHOICE": {"feeling": "courage",
   "structure": "sees danger → understands the risk → no hesitation → acts → commits fully",
   "camera": "hold the decision moment before the action",
   "music": "an emotional lift, not superhero bombast",
   "performance": "fear is present, but the choice is stronger"},
 "RELIEF_RELEASE": {"feeling": "release and joy",
   "structure": "danger peak → escape → breath → laugh/relief → movement toward safety",
   "camera": "burst through the surface, a close gasp, wider movement home",
   "music": "tension breaks into warmth",
   "performance": "coughing, laughing, soaked exhaustion, real relief"},
 "ARRIVAL_WONDER": {"feeling": "wonder and safety",
   "structure": "arrival → surrounded by new faces → curiosity → gentle welcome → awe",
   "camera": "the arriving character's POV, warm faces, the cove reveal",
   "music": "soft magical warmth",
   "performance": "breathless, overwhelmed, a cautious smile"},
 "BELONGING_HOME": {"feeling": "comfort and belonging",
   "structure": "message home → gratitude → emotional pause → acceptance",
   "camera": "close on the character absorbing the kindness, gentle group framing",
   "music": "warm and still",
   "performance": "a small smile, softened shoulders, an emotional pause — eyes moist but not overdone"},
 "MAGIC_CEREMONY": {"feeling": "awe, purpose and homecoming",
   "structure": "recognition → crystal appears → wonder → wristbands receive the gems → inner confidence → group embrace",
   "camera": "graceful coverage, close crystal detail, the receiver's eyes, the group circle",
   "music": "sacred warmth, not bombast",
   "performance": "the magic is inner guidance, NOT a weapon blast — crystals amplify inner qualities"},
 "COMEDY_RELEASE": {"feeling": "joy and relief after the emotion",
   "structure": "emotional resolution → small absurd question → laughter → warm ending",
   "camera": "relaxed, warm, character-friendly",
   "music": "light and playful",
   "performance": "do not undercut the heart too early; the comedy comes after the emotion has landed"},
}

_DIRECTOR_TO_STYLE = {
 "COMEDY_PHYSICAL": "COMEDY_CUTS", "COMEDY_DEADPAN": "COMEDY_CUTS", "TENDER_LEAVING": "HEART_COVERAGE",
 "QUIET_KNOWING": "HEART_COVERAGE", "ADVENTURE_WONDER": "CINEMATIC_CUTS", "RISING_UNEASE": "CINEMATIC_CUTS",
 "STORM_PANIC": "CINEMATIC_CUTS", "EMERGENCY_DISCOVERY": "CINEMATIC_CUTS", "RESCUE_JEOPARDY": "ACTION_COVERAGE",
 "COURAGE_CHOICE": "ACTION_COVERAGE", "RELIEF_RELEASE": "CINEMATIC_CUTS", "ARRIVAL_WONDER": "CINEMATIC_CUTS",
 "BELONGING_HOME": "HEART_COVERAGE", "MAGIC_CEREMONY": "MAGIC_COVERAGE", "COMEDY_RELEASE": "COMEDY_CUTS",
}

# Episode-1 scene → candidate director modes (the arc); the resolver scores candidates by beat-content keywords.
SCENE_DIRECTOR_MODES = {
 1: ["COMEDY_PHYSICAL", "COMEDY_DEADPAN", "RISING_UNEASE"],
 2: ["QUIET_KNOWING"],
 3: ["TENDER_LEAVING", "ADVENTURE_WONDER"],
 4: ["ADVENTURE_WONDER", "RISING_UNEASE", "STORM_PANIC"],
 5: ["EMERGENCY_DISCOVERY"],
 6: ["STORM_PANIC", "COURAGE_CHOICE"],
 7: ["RESCUE_JEOPARDY", "COURAGE_CHOICE", "RELIEF_RELEASE"],
 8: ["ARRIVAL_WONDER", "BELONGING_HOME", "COMEDY_RELEASE"],
 9: ["MAGIC_CEREMONY", "BELONGING_HOME"],
 10: ["COMEDY_RELEASE", "BELONGING_HOME"],
}

_DIR_SIGNALS = {
 "COMEDY_PHYSICAL": ("crash", "plunge", "tumble", "bonk", "spins", "smear", "dive into", "wallop", "fwip", "zoom", "pollen moustache", "slapstick"),
 "COMEDY_DEADPAN": ("deadpan", "dry ", "unimpressed", "eye-roll", "eyeroll", "barely moves", "flat stare", "topper", "officially nuts"),
 "TENDER_LEAVING": ("wristband", "gift", "goodbye", "leaving", "promise", "mum", "proud", "pier", "grown", "hand them", "gives him", "tearful"),
 "QUIET_KNOWING": ("vision", "sanctuary", "ritual", "knowing", "aida", "meditat", "candle", "still water", "inner sight", "calm certainty"),
 "ADVENTURE_WONDER": ("sail", "set off", "new world", "discover", "curious", "play", "wonder", "eager", "horizon", "first time", "explore", "squeaky"),
 "RISING_UNEASE": ("cloud", "wind pick", "weather", "darken", "grey", "chill", "glance up", "sky", "cooler", "something coming"),
 "STORM_PANIC": ("storm", "lost", "gust", "map is lost", "map gone", "isolation", "alone", "panic", "fear", "rain", "capsiz", "overwhelm", "horizon erased", "vulnerab"),
 "EMERGENCY_DISCOVERY": ("spot", "sudden stop", "realis", "distant boat", "in trouble", "something's wrong", "freeze", "alarm", "stops mid"),
 "RESCUE_JEOPARDY": ("underwater", "drift net", "net", "trapped", "current", "drown", "struggle", "sinking", "grip slip", "bubbles", "strain", "tangled"),
 "COURAGE_CHOICE": ("dives in", "decides", "no hesitation", "commit", "brave", "pulls free", "tears free", "choice", "jumps in", "resolve"),
 "RELIEF_RELEASE": ("surface", "burst", "gasp", "breath", "relief", "escape", "break the surface", "cough", "made it"),
 "ARRIVAL_WONDER": ("arriv", "reach", "cove", "welcome", "new faces", "awe", "shore", "crystal cove"),
 "BELONGING_HOME": ("belong", "home", "accept", "gratitude", "message home", "embrace", "not alone", "family", "held safe"),
 "MAGIC_CEREMONY": ("aquamarine", "ceremony", "crystal call", "gems", "crystal-set", "wristbands glow", "beacon", "crystal appears", "homecoming"),
 "COMEDY_RELEASE": ("honey", "absurd", "joke", "light again", "warm ending", "release", "grin", "punchline"),
}

# Audit corrections — GUARANTEE the named beats regardless of keyword noise (the resolver still computes the rest).
_DIRECTOR_OVERRIDES = {
 "1.B1": "COMEDY_PHYSICAL", "1.B3b": "COMEDY_PHYSICAL",
 "3.B3": "TENDER_LEAVING", "4.B4": "STORM_PANIC", "7.B6": "RESCUE_JEOPARDY", "9.B3": "MAGIC_CEREMONY",
}

def infer_director_mode(beat, sc):
    """director_mode-FIRST resolver: beat.director_mode wins; else the Episode-1 scene→mode candidates scored by the
    beat's own content keywords (storyBeat / emotionalIntent / action / dialogue / atmosphere). Replaces the
    comedy-biased creative-mode inference for emotional beats — a tender beat reads tender, a rescue reads rescue."""
    if beat.get("director_mode"):
        return beat["director_mode"]
    code = str(beat.get("beatCode") or beat.get("shotCode") or "")
    if code in _DIRECTOR_OVERRIDES:
        return _DIRECTOR_OVERRIDES[code]
    try:
        scene_n = int(beat.get("sceneNumber") or code.split(".")[0])
    except Exception:
        scene_n = 0
    candidates = SCENE_DIRECTOR_MODES.get(scene_n) or list(DIRECTOR_MODE_GUIDANCE)
    blob = " ".join(str(beat.get(k, "")) for k in ("storyBeat", "emotionalIntent", "physicalFeeling", "grade",
                    "light", "atmosphere", "soundIntent", "want", "need", "kidRead", "adultRead"))
    blob += " " + " ".join((c.get("action", "") + " " + (c.get("dialogue") or "")) for c in (beat.get("cuts") or []))
    blob += " " + str(sc.get("name", ""))
    t = blob.lower()
    best, best_score = candidates[0], -1
    for m in candidates:
        score = sum(1 for kw in _DIR_SIGNALS.get(m, ()) if kw in t)
        if score > best_score:
            best, best_score = m, score
    return best                                  # zero signal → the scene's dominant (first) candidate

def infer_shot_style(beat, mode):
    """beat.shot_style wins; else map from the DIRECTOR mode (15) and fall back to the legacy creative mode (6)."""
    return beat.get("shot_style") or _DIRECTOR_TO_STYLE.get(mode) or _MODE_TO_STYLE.get(mode, "CINEMATIC_CUTS")

def _gag_locks():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "gag_locks.json")
    try:
        return {k: v for k, v in json.load(open(p)).items() if not k.startswith("_")}
    except Exception:
        return {}

def _movement(framing):
    m = re.findall(r"(push[- ]?in|pull[- ]?back|slow track|tracking|follow|pan|tilt|dolly|handheld|locked|static|crane|whip|orbit|rack focus)", framing or "", re.I)
    seen = list(dict.fromkeys(x.lower() for x in m))
    return ", ".join(seen) if seen else "motivated, restrained move only"

def _build_shots(beat, gag, active, dur, mode):
    """Internal shots within the beat. Normal beats = one shot per cut. A GAG-LOCKED beat SPLITS the payoff cut into
    a dedicated REVEAL shot (the locked visual payoff, NO line) placed BEFORE the misread line, so the payoff is
    visible first and stays visible through the reaction line — the gag mechanism is never weakened or delayed."""
    cuts = beat.get("cuts") or []
    speakers = [s for s in (beat.get("speakers") or []) if s]
    chars = beat.get("openingCast") or beat.get("characters") or []
    reactors = [c for c in chars if c not in speakers]
    lead = speakers[0] if speakers else (chars[0] if chars else "")
    specs = []
    for c in cuts:
        action = _clean(c.get("action", "")); framing = _clean(c.get("framing", "")); dlg = _dialogue_lines(c, beat)
        impact = bool(re.search(r"crash|bonk|impact|tumble|slam|smack|wallop|spins? sideways|plunge|swallow", action, re.I))
        payoff = bool(gag and dlg and re.search(r"pull(s|ed)? (back )?out|emerg|out of the flower|present|reveal|dusted|moustache", action, re.I))
        if payoff:
            cv = gag.get("carry_visual", "fuzzy yellow pollen moustache")   # the locked disguise the reveal carries
            specs.append({"action": gag["required_visual_payoff"], "framing": "medium close reveal",
                          "movement": "rack focus / push to the face", "dlg": [], "role": "reveal"})
            for d in dlg:
                spk = d.split(" ", 1)[0]
                if spk == lead:    # the gag's misreader presents himself, the disguise still visible, body outside the flower
                    specs.append({"action": f"{spk} proudly presents himself, the {cv} still clearly across his face, body fully outside the flower.",
                                  "framing": f"medium on {spk}", "movement": "locked", "dlg": [d], "role": "misread"})
                else:              # the straight character lands the punchline; the disguise stays visible on the lead
                    specs.append({"action": f"{spk} holds still, fights a smile, then answers dryly; {lead}'s {cv} stays clearly visible.",
                                  "framing": f"reaction close-up on {spk}", "movement": "locked", "dlg": [d], "role": "react"})
        else:
            specs.append({"action": action, "framing": framing, "movement": _movement(framing), "dlg": dlg,
                          "role": ("impact" if impact else "")})
    weights = [max(1, len(s["action"]) + 2 * sum(len(d) for d in s["dlg"])) for s in specs] or [1]
    tot = sum(weights) or 1; t = 0.0; shots = []
    for i, s in enumerate(specs):
        t1 = active if i == len(specs) - 1 else round(t + active * weights[i] / tot, 1)
        purpose = ("visual payoff (the locked gag reveal)" if s["role"] == "reveal"
                   else "reaction / punchline" if s["role"] == "react"
                   else "character misread" if s["role"] == "misread"
                   else "impact" if s["role"] == "impact"
                   else "setup and geography" if i == 0
                   else "character delivery" if s["dlg"]
                   else "anticipation / action")
        shots.append({"n": i + 1, "t0": round(t, 1), "t1": t1, "framing": s.get("framing") or "medium",
                      "movement": s.get("movement") or _movement(s.get("framing")), "action": _cap(s["action"], 200),
                      "dialogue": s["dlg"], "purpose": purpose, "role": s["role"]})
        t = t1
    is_comedy = mode in ("COMEDY_BIG", "COMEDY_SMALL", "COMEDY_PHYSICAL", "COMEDY_DEADPAN", "COMEDY_RELEASE")
    hold_p = "comedy button — hold for the laugh" if is_comedy else "final hold — let the moment land"
    # COMEDY directing rule: the final hold must keep the visual gag readable at screen size — do not pull too wide.
    hold_framing = ("medium-wide hold framed to keep the visual gag readable at screen size (do not pull too wide)"
                    if is_comedy else "wide hold")
    shots.append({"n": len(shots) + 1, "t0": active, "t1": float(dur), "framing": hold_framing, "movement": "locked",
                  "action": "Hold the final composition — no new action and no new dialogue.", "dialogue": [],
                  "purpose": hold_p, "role": "hold"})
    return shots

# ── D. exact bee lock blocks (Fuzzby / Zenny never receive crystals) ─────────────────────────────────────────
BEE_LOCK = {
 "Fuzzby": "Proud, over-confident, expressive, fast natural wing buzz, same stripe pattern, same antenna shape, same wing shape, same nose, same limbs, same proportions. No crystal, no pendant, no necklace, no medallion, no charm, no badge, no strap, no added accessory.",
 "Zenny": "Calm, precise, unimpressed, controlled wingbeats, still posture, same stripe pattern, same antenna shape, same wing shape, same proportions. No crystal, no pendant, no necklace, no medallion, no charm, no badge, no strap, no added accessory.",
}

def _clean(t):
    fn = getattr(P, "_clean_line", None)
    return (fn(t) if fn else str(t or "").strip())

def _probe(path):
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=20)
        return round(float(out.stdout.strip()), 1)
    except Exception:
        return None

def _strip_crystal(text):
    """For a BEE-ONLY scene: remove crystal / magical-ambience language (incl. plural + 'crystals hum')."""
    if not text:
        return text
    t = re.sub(r"\b(soft |ambient |faint |gentle )*crystals?(\s+(bokeh|hums?|glows?|ambien\w*|shimmer|bloom|note))?",
               "soft ambient", text, flags=re.I)
    t = re.sub(r"\bmagical\b", "natural", t, flags=re.I)
    t = re.sub(r"\b(soft ){2,}", "soft ", t, flags=re.I)        # collapse doubled 'soft'
    return re.sub(r"\s{2,}", " ", t).strip()

def _sanitize_sfx(text, bee_only):
    """Audio rule (F): bee 'humming / sung buzz / vocal buzz' → natural wing buzz; strip crystal for bee scenes."""
    if not text:
        return text
    t = _strip_crystal(text) if bee_only else text
    t = re.sub(r"\b(tiny |soft |vocal |sung )*(sung buzz|vocal buzz|buzz[- ]?voice|humming|hum)\b", "wing buzz", t, flags=re.I)
    return re.sub(r"\s{2,}", " ", t).strip()

def _cap(t, n):
    """Condense a verbose Director field to <= n chars, ending on a clean clause/word boundary (no mid-word cut,
    no dangling comma)."""
    t = (t or "").strip()
    if len(t) <= n:
        return t.rstrip(" ,;")
    cut = t[:n]
    for sep in (". ", "; ", ", "):
        i = cut.rfind(sep)
        if i > n * 0.5:
            return cut[:i].rstrip(" ,;")          # drop the trailing separator + comma
    j = cut.rfind(" ")
    return ((cut[:j] if j > n * 0.5 else cut).rstrip(" ,;-") + "…")

def _decase(line):
    """Sentence-case an all-shouting dialogue line (lip-sync reference text), preserving the words."""
    letters = re.sub(r"[^A-Za-z]", "", line)
    if letters and letters.upper() == letters and len(letters) > 3:
        return line[:1].upper() + line[1:].lower()
    return line

# ── C. deterministic creative-mode inference ────────────────────────────────────────────────────────────────
def infer_creative_mode(beat, sc):
    if beat.get("creativeMode"):
        return beat["creativeMode"]
    cm = str(beat.get("comedyMode") or "").upper()
    blob = " ".join(str(beat.get(k, "")) for k in ("storyBeat", "emotionalIntent", "grade", "light", "atmosphere", "soundIntent"))
    blob += " " + " ".join((c.get("action", "") + " " + (c.get("dialogue") or "")) for c in (beat.get("cuts") or []))
    blob += " " + " ".join(str(sc.get(k, "")) for k in ("name", "weather", "look", "lighting"))
    t = blob.lower()
    has = lambda *ws: any(w in t for w in ws)
    if has("aquamarine", "crystal call", "ceremony", "awards the", "crystal-set", "gems settle", "beacon"):
        return "MAGIC_BEACON"
    if has("underwater", "drift net", "rescue", "swim", "dives", "at sea", "current", "squeaky", "wave crash"):
        return "ACTION_RESCUE"
    if has("thunder", "storm", "lightning", "rain band", "sky darken", "blue-grey", "grey-green") and cm != "BIG":
        return "STORM_TURN"
    if cm == "TRUE":
        return "HEART_TRUE"
    if cm == "BIG":
        return "COMEDY_BIG"
    if has("fuzzby", "zenny", "proud", "deadpan", "dignity", "pompous"):
        return "COMEDY_SMALL"
    return "HEART_TRUE"

def _dialogue_lines(cut, beat):
    """Map a cut's dialogue to NAMED-speaker lip-sync lines (never 'a voice'). A line with no 'NAME:' prefix is a
    CONTINUATION of the previous speaker (a script wraps one line across two), not a new speaker-less line."""
    out = []
    vt = (cut.get("voiceTreatment") or "").strip()
    speakers = [s for s in (beat.get("speakers") or []) if s]
    pairs = []   # [[name, text], ...] — continuations merge into the previous speaker
    for ln in re.split(r"[\r\n]+", (cut.get("dialogue") or "").strip()):
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"\s*([A-Za-z][A-Za-z'’._ ]{0,40}?)\s*:\s*(.+)$", ln)
        if m:
            pairs.append([m.group(1).strip().title(), _clean(m.group(2))])
        elif pairs:                                       # continuation of the previous speaker's line
            pairs[-1][1] = (pairs[-1][1] + " " + _clean(ln)).strip()
        else:                                             # first line, no prefix
            pairs.append([speakers[0] if len(speakers) == 1 else "", _clean(ln)])
    for name, text in pairs:
        line = _decase(text)
        if not line:
            continue
        if vt == "group_chorus":
            out.append(f'GROUP_CHORUS performs the line in broad group unison — broad group mouth movement, no single-character lip-sync: "{line}"')
        elif vt == "underwater_vo":
            out.append(f'{name or "Keen"} delivers "{line}" as internal/muffled underwater voice-over — no precise visible mouth lip-sync; perform through eyes, body strain, bubbles and pulling action')
        elif name:
            out.append(f'{name} lip-syncs exactly to @Audio1: "{line}"')
        else:
            out.append(f'NAMED SPEAKER MISSING — "{line}"')   # validator will flag (never emits "a voice says")
    return out

def _char_lock(name, slot, beat):
    if name in BEE_LOCK:
        return f"{name}:\nExact match to {slot}. {BEE_LOCK[name]}"
    c = P.CHARACTERS.get(name, {}) or {}
    base = (f"{name}:\nExact match to {slot}. Keep the face, body shape, proportions, colours, markings, limbs, "
            "eyes, expression language and scale exactly consistent with the reference.")
    if name == "Keen":
        kw = beat.get("keenWristbands")
        base += (" Keen wears the crystal-set aquamarine wristbands." if kw == "crystal"
                 else " Keen wears the vacant (empty, no-gem) wristbands." if kw == "vacant"
                 else " Keen wears NO wristbands yet.")
    avoid = str(c.get("avoid", "")).rstrip(".")
    base += (f" No added {avoid}." if avoid else
             " Do not add clothing, jewellery, badges, straps, charms, pendants, necklaces, medallions or crystals unless explicitly listed in continuity.")
    return base

# ── PHYSICAL STAGING INTENT — the directing layer for physical/comedy/action beats. A physical gag can pass the
#    emotional validator yet be staged wrong (Fuzzby vanished INTO the flower). This forces the prompt to ANSWER the
#    concrete physical questions: what stays visible, what touches what, what compresses/rebounds, the exact gag
#    shape/payoff, the misread, what makes it worse, what carries forward — and what is prohibited. Beat.* fields
#    win; else it derives from the gag lock + sensible defaults. Returns the flattened intent text ('' when N/A). ──
# ── PHYSICAL ACTION ARCHETYPES — a deterministic library of physical patterns. The generic COMEDY_PHYSICAL
#    default was structurally wrong (it fed a leaf-crash beat moustache-style "face/contact + makes it worse").
#    Each archetype defines the 7 staging rules for ITS pattern; the resolver picks the right one and the staging
#    intent is GENERATED FROM IT, never from a one-size default. NEEDS_EXPLICIT_PHYSICAL_STAGING blocks readiness. ──
PHYSICAL_ARCHETYPES = {
 "LEAF_CRASH_REBOUND": {
   "visibility_rule": "the bee's whole body, wings, legs and silhouette stay fully visible in open air at all times",
   "contact_rule": "flies in too fast and CAREENS side-first into a broad leaf with real force, bouncing hard off it — nothing swallows, hides or contains him",
   "physics_rule": "wildly over-commits the turn and SLAMS side-first into the leaf with a big springy WHAP, exaggerated squash-and-stretch, wings flailing, and a bouncy rebound before he wobbles and freezes mid-air",
   "visual_payoff_rule": "the over-confident crash followed instantly by a heroic 'that was scheduled' recovery pose",
   "recovery_or_escalation_rule": "RECOVERY (false dignity) — he straightens proudly; the button is the cover-up, NOT an escalation",
   "continuity_physical_rule": "ends held in the proud recovery pose; no lasting mess, no pollen disguise",
   "prohibited_staging": "face-first contact; entering/burying inside a flower or leaf; disappearing; hidden silhouette; 'makes it worse' escalation; a pollen moustache (wrong beat)"},
 "POLLEN_FACE_PRESS_REVEAL": {
   "visibility_rule": "the bee's whole body, wings and legs stay fully visible OUTSIDE the flower at all times; the silhouette never vanishes into the bloom",
   "contact_rule": "only his FACE presses into the pollen-heavy centre; the body never enters",
   "physics_rule": "the flower compresses softly under his face, then springs back with elastic weight as a pollen puff bursts",
   "visual_payoff_rule": "he pulls his face back wearing a large yellow pollen HANDLEBAR MOUSTACHE and a small pollen GOATEE — readable shapes, not vague dust — before the line",
   "recovery_or_escalation_rule": "he tries to wipe it but smears it worse — the handlebar stretches wider, the goatee messier; he never wipes it clean",
   "continuity_physical_rule": "the smeared handlebar moustache and messy goatee stay clearly visible to the end and carry into the next beat",
   "prohibited_staging": "full-body flower entry; disappearing/buried-inside; hidden silhouette; vague pollen dusting; a clean face after wiping; losing the moustache/goatee"},
 "POLLEN_SMEAR_TUMBLE": {
   "visibility_rule": "the bee's whole body stays visible through the tumble, which reads in open air",
   "contact_rule": "he clips or glances a blossom/surface mid-dive; he does not vanish into it",
   "physics_rule": "an over-rotated corrective dive with weight — clip, tumble, recover and pop back up",
   "visual_payoff_rule": "the ALREADY-PRESENT handlebar moustache and goatee get smeared messier through the tumble; he pops up still wearing them",
   "recovery_or_escalation_rule": "ESCALATION — the attempt to look composed makes the pollen mess worse",
   "continuity_physical_rule": "ENTERS still wearing the moustache/goatee from the previous beat and EXITS messier; never clean",
   "prohibited_staging": "losing the pollen moustache/goatee before or during the tumble; disappearing into a flower; a clean face"},
 "FLOWER_HIDE_PANIC": {
   "visibility_rule": "even while hiding, the silhouette stays partly readable — head, eyes or body edge peeks out",
   "contact_rule": "ducks behind or into a flower/leaf as cover; the cover is too small to fully hide him",
   "physics_rule": "a quick panicked duck, freeze, then a peek; small nervous shifts",
   "visual_payoff_rule": "the comedy/tension of a hopeless hiding spot — he thinks he's hidden but isn't",
   "recovery_or_escalation_rule": "ESCALATION — he peeks out or is spotted",
   "continuity_physical_rule": "ends crouched by the cover, position held",
   "prohibited_staging": "fully vanishing with no readable silhouette; the cover swallowing him completely"},
 "BOAT_LURCH_MAP_LOSS": {
   "visibility_rule": "Keen and the boat stay clearly framed and readable; the map is the lost object",
   "contact_rule": "the wave and wind act on the boat; the map is torn from Keen's grip and goes overboard",
   "physics_rule": "the boat lurches and tilts in the swell; the map flutters out of reach and is gone; rain drives down",
   "visual_payoff_rule": "the map gone, the horizon erased, Keen gripping the boat edge — isolation",
   "recovery_or_escalation_rule": "ESCALATION into fear/isolation, then a deliberate self-grounding breath",
   "continuity_physical_rule": "ends gripping the boat edge, map gone, rain heavy, horizon erased",
   "prohibited_staging": "Keen falling out or disappearing; comedy; a calm sea; the map still aboard"},
 "UNDERWATER_NET_PULL": {
   "visibility_rule": "clear underwater geography — Keen, Squeaky, the drift net and the surface direction all readable",
   "contact_rule": "Keen grips the net/Squeaky; the current is the force; Squeaky is the trapped object",
   "physics_rule": "pulling effort against the current — strain, the net resists, bubbles, a slipping grip",
   "visual_payoff_rule": "a FAILED first attempt — the net holds, the current worsens, strength fading",
   "recovery_or_escalation_rule": "ESCALATION — pressure rises toward a final effort",
   "continuity_physical_rule": "positions and the still-trapped net state carry forward",
   "prohibited_staging": "magic/ceremony staging; unclear geography; a weapon blast; vague underwater haze; an easy pull"},
 "NET_TEAR_RELEASE": {
   "visibility_rule": "clear geography — the net, the tear point and both characters readable",
   "contact_rule": "Keen's final committed pull tears the drift net",
   "physics_rule": "the net rips, sudden release, foam and disorientation",
   "visual_payoff_rule": "the net tears free — followed immediately by danger again (separation in the foam)",
   "recovery_or_escalation_rule": "RELEASE into immediate consequence, not a clean rescue",
   "continuity_physical_rule": "net torn, characters separated in the foam, carries forward",
   "prohibited_staging": "an easy/clean release; the net dissolving; magic; no final effort"},
 "DOLPHIN_RIDE_SURFACE": {
   "visibility_rule": "the dolphin, both riders and the surface line stay readable",
   "contact_rule": "Keen and Squeaky hold onto the dolphin, which carries them upward",
   "physics_rule": "an upward surge, then a burst through the surface with spray",
   "visual_payoff_rule": "bursting from the water into air — relief and release",
   "recovery_or_escalation_rule": "RELEASE — coughing, gasping, laughing, soaked",
   "continuity_physical_rule": "ends at the surface, soaked, moving toward safety",
   "prohibited_staging": "drowning staging; magic; the dolphin vanishing"},
 "CRYSTAL_WRISTBAND_SET": {
   "visibility_rule": "Keen's wristbands, the crystal detail and his eyes stay readable",
   "contact_rule": "the Aquamarine gems settle gently INTO the vacant wristbands",
   "physics_rule": "a soft settling glow — inner guidance, never a blast; warmth spreads",
   "visual_payoff_rule": "the wristbands become crystal-set with a warm inner light",
   "recovery_or_escalation_rule": "inner confidence rising into a group embrace",
   "continuity_physical_rule": "the wristbands are now crystal-set (ONLY from Scene 9 onward) and carry forward",
   "prohibited_staging": "a weapon blast / beam / shockwave; the gems appearing before Scene 9; bee crystals"},
 "GROUP_HUG_SWAMP": {
   "visibility_rule": "the group framing and the held character at the centre stay readable",
   "contact_rule": "the group gently closes in and embraces the held character",
   "physics_rule": "soft group closeness, a warm settle, no crushing",
   "visual_payoff_rule": "belonging — the character held safe at the centre of the circle",
   "recovery_or_escalation_rule": "emotional RELEASE, warm and still",
   "continuity_physical_rule": "the embrace continues into the next beat",
   "prohibited_staging": "a chaotic pile or crushing; a comedy undercut of the warmth"},
 "DEADPAN_REACTION_HOLD": {
   "visibility_rule": "the reactor's face and eyes stay clearly readable; minimal motion",
   "contact_rule": "none — this is a reaction, not a physical action",
   "physics_rule": "stillness with a tiny tell — a blink, a small head tilt, a held breath",
   "visual_payoff_rule": "the deadpan contrast lands the dry button",
   "recovery_or_escalation_rule": "a held beat just long enough for the dry line to land",
   "continuity_physical_rule": "position held; nothing physically changes",
   "prohibited_staging": "big movement; over-animation; a wide pull that loses the reaction"},
 "DIALOGUE_HOVER_STASIS": {
   "visibility_rule": "the speaking and reacting characters stay readable, hovering naturally",
   "contact_rule": "none — characters hover and talk; no invented physical action",
   "physics_rule": "natural hover with live wing motion and small conversational gestures",
   "visual_payoff_rule": "the line/exchange itself is the beat",
   "recovery_or_escalation_rule": "none — keep it grounded and simple",
   "continuity_physical_rule": "positions held into the next beat",
   "prohibited_staging": "invented physical gags; frozen wings while hovering"},
 "STORM_REACTION_SHIFT": {
   "visibility_rule": "the sky/environment shift and the character's glance both stay readable",
   "contact_rule": "no direct contact — the environment is what changes",
   "physics_rule": "the light cools, the wind picks up, a glance up; the characters become smaller and quieter",
   "visual_payoff_rule": "the mood shift — something is coming",
   "recovery_or_escalation_rule": "a held reaction; do not overplay the danger yet",
   "continuity_physical_rule": "storm pressure is established and carries forward",
   "prohibited_staging": "a full storm too early; panic too early; comedy that undercuts the unease"},
 "CHARACTER_ARRIVAL_STUMBLE": {
   "visibility_rule": "the arriving character and the new space stay readable",
   "contact_rule": "a tentative landing or step, maybe a small stumble; feet/paws find the ground",
   "physics_rule": "a cautious, breathless arrival with a small wobble before footing is found",
   "visual_payoff_rule": "the awe and overwhelm of arriving somewhere new",
   "recovery_or_escalation_rule": "a cautious smile as they find their footing",
   "continuity_physical_rule": "arrived and standing, position held",
   "prohibited_staging": "a confident heroic arrival; a big crash; disappearing"},
 "EMOTIONAL_OBJECT_HANDOFF": {
   "visibility_rule": "the hands/paws, the object and the eyes of both characters stay clearly visible",
   "contact_rule": "the object passes gently from one character's paws to the other",
   "physics_rule": "a slow, held handoff with small pauses and swallowed emotion",
   "visual_payoff_rule": "the object becomes meaningful — the gift moment lands",
   "recovery_or_escalation_rule": "a held, tender beat — never staged as action",
   "continuity_physical_rule": "the receiver now holds/wears the object; it carries forward",
   "prohibited_staging": "a rushed or action handoff; comedy; the object already in its later (e.g. crystal-set) state"},
 "FLOWER_STUCK_BUTTON": {
   "visibility_rule": "the bee's presence stays readable even while stuck — trembling petals, a pollen puff and a peeking paw/antenna betray him; never a blank, empty flower",
   "contact_rule": "he darts into the open flower too fast and gets comically stuck; the flower holds him with a soft, definite thud and wobbling petals",
   "physics_rule": "a soft comic thud (confidence landing face-first into a cushion), petals wobble, then a tiny tremble and a small pollen puff",
   "visual_payoff_rule": "the comic 'stuck' button — the bee trapped in the flower while the straight character's deadpan reaction lands the worry",
   "recovery_or_escalation_rule": "he stays comically stuck (the button) — no escalation; the deadpan sigh and head-tilt close it",
   "continuity_physical_rule": "he remains stuck in the flower at frame edge, unharmed; the mood/storm pressure carries forward",
   "prohibited_staging": "the flower fully swallowing him with no readable silhouette; a blank empty flower; a hard or violent crash"},
 "CRASH_ARRIVAL_HEAP": {
   "visibility_rule": "the arriving character stays fully visible in open air through the whole crash; the group and the shore stay readable",
   "contact_rule": "he rockets in far too fast, fails to stop, pinballs off the surroundings and lands in a heap at the group's feet — nothing hides him",
   "physics_rule": "an out-of-control chaotic arrival — overshoot, pinball, a wet soggy THUMP, then settle as a visible heap",
   "visual_payoff_rule": "the comic crash-landing jolts the safe circle, and the crash accidentally does something significant (e.g. points toward the danger)",
   "recovery_or_escalation_rule": "he lands in a soggy heap, NOT a clean recovery pose; one tiny paw lifts; the group is too worried to laugh",
   "continuity_physical_rule": "he remains a visible heap at the group's feet; whatever the crash pointed at stays pointed; carries forward",
   "prohibited_staging": "disappearing or being buried on impact; a clean heroic landing; the crash hiding him from view"},
 "GROUP_REACTION_WITNESS": {
   "visibility_rule": "the whole group and their eyelines stay readable; the watched event is distant or off-frame, not staged here",
   "contact_rule": "none — no one acts; the action being witnessed has already happened or is far out of reach",
   "physics_rule": "stillness with small held gestures — a lean forward that stops, a paw settling near a crystal, eyes fixed out to sea",
   "visual_payoff_rule": "the collective held breath — shock turning into quiet recognition",
   "recovery_or_escalation_rule": "a held, moved beat; no one takes action",
   "continuity_physical_rule": "the group remains watching, positions held; carries forward",
   "prohibited_staging": "anyone diving, acting or leaving to follow; staging the witnessed action itself; comedy that breaks the held breath"},
}
# Audit corrections — GUARANTEE the named beats; the resolver computes the rest.
_ARCHETYPE_OVERRIDES = {
 "1.B1": "LEAF_CRASH_REBOUND", "1.B3b": "POLLEN_FACE_PRESS_REVEAL", "1.B4": "POLLEN_SMEAR_TUMBLE",
 "3.B3": "EMOTIONAL_OBJECT_HANDOFF", "4.B3": "BOAT_LURCH_MAP_LOSS", "4.B4": "BOAT_LURCH_MAP_LOSS",
 "7.B3": "UNDERWATER_NET_PULL", "7.B6": "UNDERWATER_NET_PULL", "7.B7": "NET_TEAR_RELEASE",
 "7.B8": "DOLPHIN_RIDE_SURFACE", "9.B2": "CRYSTAL_WRISTBAND_SET", "9.B3": "CRYSTAL_WRISTBAND_SET",
}
# Signals are DISTINCTIVE phrases matched against the beat's OWN action only (not continuity carryover), so a
# beat doesn't inherit "storm/crystal/wristband" from a neighbour. Single common words are deliberately avoided.
_ARCH_SIGNALS = {
 "LEAF_CRASH_REBOUND": ("fwip", "spins sideways into", "crashes into a leaf", "bonks", "rebounds with"),
 "POLLEN_FACE_PRESS_REVEAL": ("pollen moustache", "handlebar moustache", "presses into the pollen", "face into the pollen"),
 "POLLEN_SMEAR_TUMBLE": ("smears it worse", "smears the pollen", "corrective dive", "pollen tumble"),
 "FLOWER_HIDE_PANIC": ("ducks behind", "hides behind", "hiding spot", "peeks out"),
 "BOAT_LURCH_MAP_LOSS": ("map is lost", "map gone", "map overboard", "loses the map", "boat lurch", "capsiz"),
 "UNDERWATER_NET_PULL": ("drift net", "tangled in the net", "pulls the net", "trapped underwater", "the net holds"),
 "NET_TEAR_RELEASE": ("tears the net", "the net tears", "rips the net", "tears free"),
 "DOLPHIN_RIDE_SURFACE": ("burst through the surface", "breaks the surface", "rides the dolphin", "surge to the surface", "ride to the surface"),
 "CRYSTAL_WRISTBAND_SET": ("aquamarine gem", "gems settle", "wristbands receive", "wristbands become crystal"),
 "GROUP_HUG_SWAMP": ("group hug", "group embrace", "circle around", "held at the centre"),
 "EMOTIONAL_OBJECT_HANDOFF": ("gives him the wristband", "hands him the wristband", "the wristband gift", "fastens the wristband"),
 "CHARACTER_ARRIVAL_STUMBLE": ("reaches the cove", "steps onto", "stumbles ashore", "arrives at the"),
 "STORM_REACTION_SHIFT": ("a storm's coming", "storm pressure", "wind picks up", "sky darkens", "thunder rumble"),
 "DEADPAN_REACTION_HOLD": ("deadpan", "barely moves", "almost-smile", "dry topper"),
}
# High-risk = IMPACT-class physical words only, WORD-BOUNDARY matched (so "gaze falls", "a tear", "pulls him close"
# don't false-flag). The softer pull/tear/hide/press cases are covered by the explicit overrides + distinctive signals.
_HIGH_RISK_RE = re.compile(r"\b(impact|crash(es|ed)?|plunges?|dives?|tumbles?|bonks?|slams?|wallops?|lurch(es)?|buried|capsiz\w*)\b|spins sideways")
_LOW_RISK_ARCHES = ("DIALOGUE_HOVER_STASIS", "DEADPAN_REACTION_HOLD", "STORM_REACTION_SHIFT", "EMOTIONAL_OBJECT_HANDOFF",
                    "CHARACTER_ARRIVAL_STUMBLE", "GROUP_HUG_SWAMP", "GROUP_REACTION_WITNESS")
NEEDS_EXPLICIT = "NEEDS_EXPLICIT_PHYSICAL_STAGING"

def infer_physical_archetype(beat, dmode, style, gag):
    """CONSERVATIVE: beat.physical_action_archetype wins; else the per-beat override; else the gag lock; else a
    DISTINCTIVE-phrase match in the beat's OWN action. A high-risk physical action with no specific match →
    NEEDS_EXPLICIT_PHYSICAL_STAGING (blocks readiness, flags for human). Low-risk → a stasis/reaction archetype.
    Continuity carryover is NOT scanned, so a beat never inherits a neighbour's storm/crystal/wristband state."""
    if beat.get("physical_action_archetype"):
        return beat["physical_action_archetype"]
    code = str(beat.get("beatCode") or beat.get("shotCode") or "")
    if code in _ARCHETYPE_OVERRIDES:
        return _ARCHETYPE_OVERRIDES[code]
    if gag and beat.get("script_gag_lock_id") == "S1_FUZZBY_POLLEN_MOUSTACHE":
        return "POLLEN_FACE_PRESS_REVEAL"
    action = " ".join((c.get("action", "") + " " + (c.get("dialogue") or "")) for c in (beat.get("cuts") or [])).lower()
    action += " " + " ".join(str(beat.get(k, "")) for k in ("storyBeat", "soundIntent", "physicalFeeling")).lower()
    best, best_score = None, 0
    for arch, kws in _ARCH_SIGNALS.items():
        score = sum(1 for kw in kws if kw in action)
        if score > best_score:
            best, best_score = arch, score
    if best:
        return best
    # high-risk only if a non-NEGATED impact word appears ("not a crash" / "no tumble" don't count)
    if any(not re.search(r"\b(not|no|never)\b", action[max(0, mm.start() - 14):mm.start()]) for mm in _HIGH_RISK_RE.finditer(action)):
        return NEEDS_EXPLICIT                      # high-risk physical, no specific archetype → block, flag for human
    if dmode == "COMEDY_DEADPAN":
        return "DEADPAN_REACTION_HOLD"
    if dmode == "RISING_UNEASE" or (style == "CINEMATIC_CUTS" and "storm" in action):
        return "STORM_REACTION_SHIFT"
    if dmode == "ARRIVAL_WONDER":
        return "CHARACTER_ARRIVAL_STUMBLE"
    return "DIALOGUE_HOVER_STASIS"

def build_physical_staging(beat, gag, archetype, lead):
    """Generate the staging intent FROM the resolved archetype (beat.* rule fields override individual rules).
    Returns '' for NEEDS_EXPLICIT_PHYSICAL_STAGING so the validator blocks it rather than emitting generic staging."""
    if _clean(beat.get("physical_staging_intent") or ""):
        return _clean(beat["physical_staging_intent"])
    arch = PHYSICAL_ARCHETYPES.get(archetype)
    if not arch:
        return ""
    pick = lambda key: _clean(beat.get(key) or "") or _clean(arch.get(key, ""))
    rows = [("Stays visible", pick("visibility_rule")), ("Contact", pick("contact_rule")),
            ("Physics", pick("physics_rule")), ("Payoff", pick("visual_payoff_rule"))]
    if gag and _clean(gag.get("character_misread", "")):
        rows.append(("Misunderstanding", _clean(gag["character_misread"])))
    rows += [("Recovery / escalation", pick("recovery_or_escalation_rule")),
             ("Carries forward", pick("continuity_physical_rule"))]
    body = [f"{k}: {_cap(v, 220)}" for k, v in rows if v]
    proh = _clean(beat.get("prohibited_staging") or "") or _clean(arch.get("prohibited_staging", ""))
    if proh:
        body.append(f"Prohibited staging: {_cap(proh, 360)}")
    return "\n".join(body)

# ── A.1 + B/E — build the AUTHORING JSON (the internal structured object) ────────────────────────────────────
def build_seedance_authoring_json(beat, sc, refs, continuity, episode="Ep1"):
    code = beat.get("beatCode") or beat.get("shotCode") or "?"
    dur = int(beat.get("durationSec") or 11); dur = max(8, min(15, dur))
    # ACTION runs across the beat; the FINAL HOLD is the last ~2.4s (section E: 1.8–2.8s). The supplied dialogue
    # (audio_dur) lip-syncs WITHIN the action span — it is the line length, not where the action ends.
    active = max(float(refs.get("audio_dur") or 0), round(dur - 2.4, 1)); active = min(active, round(dur - 1.8, 1))
    oc = [c for c in (beat.get("openingCast") or beat.get("characters") or []) if c]
    bee_only = bool(oc) and set(oc) <= BEES
    mode = infer_creative_mode(beat, sc)                       # legacy creative mode (kept for back-compat)
    struct, acting = MODE_GUIDANCE.get(mode, MODE_GUIDANCE["HEART_TRUE"])
    dmode = infer_director_mode(beat, sc)                       # PRIMARY — the Episode Director emotional mode
    dg = DIRECTOR_MODE_GUIDANCE.get(dmode, DIRECTOR_MODE_GUIDANCE["QUIET_KNOWING"])
    feeling = _clean(beat.get("audience_feeling_target") or dg["feeling"])
    perf_notes = _cap(_clean(beat.get("performance_notes") or dg["performance"]), 400)
    music_emotion = _clean(beat.get("music_emotion") or "")
    truth_lock = _cap(_clean(beat.get("script_truth_lock") or ""), 200)
    emo_func = _cap(_clean(beat.get("emotional_function") or beat.get("emotionalIntent") or beat.get("storyBeat") or ""), 155)

    # internal SHOTS within the beat (a beat may hold multiple shots) + its shot style (director-mode driven) + gag
    cuts = beat.get("cuts") or []
    gag = _gag_locks().get(beat.get("script_gag_lock_id")) if beat.get("script_gag_lock_id") else None
    style = infer_shot_style(beat, dmode)
    shots = _build_shots(beat, gag, active, dur, dmode)
    music = _cap(_clean(beat.get("musicCue") or beat.get("scoreCue") or music_emotion or dg["music"]), 130)
    # SCRIPT LOCKS — the active locks consolidated for this beat
    wristband_lock = None
    if "Keen" in oc:
        kw = beat.get("keenWristbands")
        wristband_lock = ("Keen wears the crystal-set aquamarine wristbands (only AFTER the Aquamarine ceremony)." if kw == "crystal"
                          else "Keen wears the vacant (empty, no-gem) wristbands (after the pier gift, before the ceremony)." if kw == "vacant"
                          else "Keen wears NO wristbands yet (before the pier gift)." if kw == "none" else None)
    voice_locks = []
    vts = {(c.get("voiceTreatment") or "").strip() for c in cuts}
    if "group_chorus" in vts:
        voice_locks.append("GROUP_CHORUS lines are a unison/crowd asset — broad group mouth movement, never one character lip-syncing.")
    if "underwater_vo" in vts:
        voice_locks.append("Underwater lines are internal/muffled VO — no precise mouth lip-sync; perform through eyes, body strain, bubbles and movement.")
    crystal_lock = ("Fuzzby, Zenny and all bees carry NO crystal or accessory." if ("Fuzzby" in oc or "Zenny" in oc) else None)
    # PHYSICAL STAGING INTENT — the directing layer (beat.* fields win; else derived from the gag lock + defaults)
    lead = ([s for s in (beat.get("speakers") or []) if s] or oc or [""])[0]
    archetype = infer_physical_archetype(beat, dmode, style, gag)
    physical_staging = build_physical_staging(beat, gag, archetype, lead)
    # THE DIRECTOR'S PASS — a Pixar mind reads the character bibles + directs the acting/expression/camera (cached; fail-open)
    _arch_rules = "; ".join(f"{k}: {v}" for k, v in PHYSICAL_ARCHETYPES.get(archetype, {}).items())
    _dlg_lines = [d for c in cuts for d in _dialogue_lines(c, beat)]
    director_pass = cb_director_pass.direct_beat(beat, sc, dmode, archetype, _arch_rules, oc, dur, emo_func, _dlg_lines, episode)
    final_hold = _cap((beat.get("pauseHold") or "Settle into the final composition; only wings, breathing, antenna "
                       "settle, pollen motes and subtle environment settling.").strip(), 140)
    reveal_kf = ({"required": True, "keyframe_type": "REVEAL", "target_time": gag.get("reveal_target_time", "mid-beat"),
                  "purpose": gag["required_visual_payoff"]} if gag and gag.get("required_keyframe_type") == "REVEAL" else None)

    env_desc = _clean(sc.get("look") or sc.get("location") or "")
    atmosphere = _clean(beat.get("atmosphere") or sc.get("weather") or "")
    lighting = _clean(beat.get("light") or sc.get("lighting") or sc.get("colorTemperature") or "")
    if bee_only:
        env_desc, atmosphere, lighting = map(_strip_crystal, (env_desc, atmosphere, lighting))
    env_desc, atmosphere, lighting = _cap(env_desc, 150), _cap(atmosphere, 90), _cap(lighting, 100)

    # character-specific + beat-specific negatives
    char_neg = []
    if "Fuzzby" in oc or "Zenny" in oc:
        char_neg.append("Fuzzby wears no crystal. Zenny wears no crystal. Bees wear no crystals.")
    beat_neg = []
    if dmode in ("COMEDY_PHYSICAL", "COMEDY_DEADPAN", "COMEDY_RELEASE"):
        beat_neg.append("Do not pull so wide on the final comedy hold that the visual gag detail becomes unclear; keep the gag readable at screen size.")
    if bee_only:
        beat_neg.append("No crystal self-glow, hum, aura, beams or magical crystal ambience; no crystal on or near the bees; "
                        "Crystal Cove is crystal-rich so abundant colourful faceted crystals (lit by the scene only) fill the "
                        "world, but keep the bees, flowers, pollen and the gag readable — never crowd the performers or block the gag.")
    storm_blob = (str(beat.get("grade", "")) + str(beat.get("light", "")) + str(beat.get("atmosphere", ""))).lower()
    if mode != "STORM_TURN" and not any(w in storm_blob for w in ("storm", "thunder", "blue-grey", "lightning")):
        beat_neg.append("No storm light, thunder, lightning or darkening sky (the storm has not arrived in this beat).")
    if gag:
        beat_neg += list(gag.get("forbidden_interpretations", []))

    return {
        "episode": episode, "scene_number": beat.get("sceneNumber"),
        "scene_id": f"Scene {beat.get('sceneNumber')}", "beat_id": f"Beat {code}", "beat_code": code,
        "scene_name": sc.get("name", ""), "duration": dur, "active_until": active,
        "creative_mode": mode, "mode_structure": struct, "mode_acting": _cap(acting, 125),
        "director_mode": dmode, "audience_feeling_target": feeling,
        "director_structure": dg["structure"], "director_camera": dg["camera"], "director_music": dg["music"],
        "director_mode_summary": _cap(f"{dg['structure']}. Camera: {dg['camera']}. Music: {dg['music']}.", 330),
        "performance_notes": perf_notes, "music_emotion": music_emotion,
        "emotional_function": emo_func, "script_truth_lock": truth_lock,
        "wristband_lock": wristband_lock, "voice_locks": voice_locks, "crystal_lock": crystal_lock,
        "physical_action_archetype": archetype,
        "physical_staging_intent": physical_staging, "director_pass": director_pass,
        "visibility_rule": beat.get("visibility_rule"), "contact_rule": beat.get("contact_rule"),
        "physics_rule": beat.get("physics_rule"), "visual_payoff_rule": beat.get("visual_payoff_rule"),
        "failed_correction_rule": beat.get("failed_correction_rule"),
        "continuity_physical_rule": beat.get("continuity_physical_rule"),
        "prohibited_staging": beat.get("prohibited_staging"),
        "story_function": emo_func,
        "references": refs, "bee_only": bee_only,
        "continuity_in": _cap(_clean(continuity.get("in") or "Opening beat of the scene."), 175),
        "continuity_out": _cap(_clean(continuity.get("out") or ""), 175),
        "final_hold": final_hold,
        "camera": {"shot": _cap(_clean(beat.get("cameraArc") or (cuts[0].get("framing") if cuts else "") or "Medium two-shot"), 110),
                   "lens": sc.get("lens", ""), "height": sc.get("cameraHeight", ""),
                   "screen_direction": (beat.get("continuity") or {}).get("screenDirection", ""),
                   "lock_time": active, "start_state": _cap(_clean(beat.get("startState") or ""), 125)},
        "characters": oc, "speakers": [s for s in (beat.get("speakers") or []) if s],
        "character_locks": [{"slot": r["slot"], "name": r["name"], "block": _char_lock(r["name"], r["slot"], beat)}
                            for r in refs.get("characters", [])],
        "environment": {"description": env_desc, "lighting": lighting, "atmosphere": atmosphere},
        "shot_style": style, "shot_style_guidance": SHOT_STYLE_GUIDANCE.get(style, ""),
        "script_gag_lock_id": beat.get("script_gag_lock_id"), "gag_lock": gag, "reveal_keyframe": reveal_kf,
        "gag_carry": beat.get("gag_carry"),
        "shots": shots,
        "music": music,
        "sfx": _cap(_sanitize_sfx(_clean(beat.get("soundIntent") or ""), bee_only), 200),
        "character_negatives": char_neg, "beat_negatives": beat_neg,
    }

def _default_music(mode):
    return ("Light playful comedy underscore, small and bouncy, not overpowering." if mode in ("COMEDY_BIG", "COMEDY_SMALL")
            else "Tender, warm orchestral underscore — soft strings, light piano." if mode == "HEART_TRUE"
            else "Low, draining tension underscore that thins out rather than swells." if mode == "STORM_TURN"
            else "Driving but clear action underscore that keeps the geography readable." if mode == "ACTION_RESCUE"
            else "Warm, surrendering choral-and-strings glow — gentle, never a power blast." if mode == "MAGIC_BEACON"
            else "Warm, gentle orchestral underscore.")

# ── A.2 + B — FLATTEN to the clean Seedance text (FIXED section order) ────────────────────────────────────────
def flatten_seedance_prompt(a):
    L = []
    ch = a["references"].get("characters", [])
    reflist = " ".join(f"Use {c['slot']} as {c['name']} identity lock." for c in ch)
    L += ["REFERENCE ROUTING:",
          f"Use @Image1 as the approved {a['scene_name'] or ('Scene '+str(a['scene_number']))} plate and environment lock.",
          "Use @Image2 as the approved beat keyframe and composition/style lock.",
          reflist,
          "Use @Audio1 as the final supplied ElevenLabs V3 dialogue performance.",
          "Every visual choice must match @Image1 and @Image2 while preserving the distinct character identities from the supplied character references.", ""]
    L += ["BEAT:",
          f"{a['episode']} / {a['scene_id']} / {a['beat_id']}.",
          f"Duration: {a['duration']} seconds.",
          f"Emotional function: {a['emotional_function'].rstrip('.')}.", ""]
    L += ["AUDIENCE FEELING TARGET:",
          f"The audience should feel {a['audience_feeling_target'].rstrip('.')}.", ""]
    L += ["DIRECTOR MODE:",
          f"{a['director_mode']}.",
          a.get("director_mode_summary", ""), ""]
    # SCRIPT LOCKS — the locked spine the Director may split into shots but must never mutate
    gag = a.get("gag_lock")
    locks = ["Dialogue is LOCKED verbatim and the line order is fixed. The Director may split shots, but must not "
             "change the gag, the visual payoff, the emotional purpose, the dialogue order, character motivation or "
             "the continuity state."]
    if gag:
        locks.append(f"Gag lock [{a.get('script_gag_lock_id')}]: {gag['required_visual_payoff']} {gag['timing_lock']} "
                     f"Misread — {gag['character_misread']} Reaction — {gag['reaction_line']} ({gag.get('acting_note','')})")
    if a.get("script_truth_lock"):
        locks.append(f"Script truth: {a['script_truth_lock']}")
    if a.get("wristband_lock"):
        locks.append(f"Wristband lock: {a['wristband_lock']}")
    locks += list(a.get("voice_locks", []))
    if a.get("crystal_lock"):
        locks.append(f"Crystal-state lock: {a['crystal_lock']}")
    L += ["SCRIPT LOCKS:"] + locks + [""]
    L += ["CONTINUITY IN:",
          f"Continue from the previous approved beat state: {a['continuity_in']}",
          "Maintain current character positions, scale, lighting state, costume/accessory state, prop state and emotional state.",
          "Do not reset the scene unless this beat begins a new scene.", ""]
    cam = a["camera"]
    L += ["CAMERA AND EDITING:",
          f"{a.get('shot_style','CINEMATIC_CUTS')}. {a.get('shot_style_guidance','')}",
          ", ".join(x for x in [cam["shot"], cam["lens"], cam["height"]] if x) + ".",
          "Use intentional cinematic internal shots if they serve the beat. Cuts are allowed when they improve comedy, emotion, clarity, impact or pacing — every cut must have a purpose.",
          "Every cut must preserve character identity, screen direction, lighting, environment and prop/accessory/pollen continuity. No random cuts, jump cuts, purposeless angle changes or confusing reframes.",
          (f"Screen direction locked {cam['screen_direction']}. " if cam["screen_direction"] else "") + (cam["start_state"] or "Hold the staging from the keyframe."),
          f"The final comedy/emotional hold is locked long enough to land (settle by {cam['lock_time']}s).", ""]
    if a.get("physical_action_archetype"):
        L += ["PHYSICAL ACTION ARCHETYPE:", a["physical_action_archetype"], ""]
    if a.get("physical_staging_intent"):
        L += ["PHYSICAL STAGING INTENT:", a["physical_staging_intent"], ""]
    L += ["SHOT PLAN:",
          f"Director mode ({a['director_mode']}) coverage: {a.get('director_structure','')}."]
    for s in a["shots"]:
        head = f"Shot {s['n']} / {s['t0']}s–{s['t1']}s / {s['framing']}"
        if s.get("movement") and s["movement"] != "motivated, restrained move only":
            head += f" ({s['movement']})"
        L.append(head)
        if s["action"]:
            L.append(s["action"].rstrip(" .,;…") + ".")
        for d in s["dialogue"]:
            L.append(d)
        L.append(f"Purpose: {s['purpose']}.")
    L += [""]
    L += ["PERFORMANCE TRUTH:",
          a.get("performance_notes", ""),
          (f"Camera language: {a.get('director_camera','')}." if a.get("director_camera") else ""), ""]
    L += ["CHARACTER LOCKS:"]
    for cl in a["character_locks"]:
        L.append(cl["block"])
    L += ["For every character: match the approved reference exactly; add no clothing, jewellery, badge, strap, charm, pendant, necklace, medallion or crystal unless continuity lists it.", ""]
    env = a["environment"]
    L += ["ENVIRONMENT LOCK:",
          "Use the approved environment from @Image1 and @Image2.",
          env["description"] + ("." if env["description"] and env["description"][-1] not in ".!?…" else ""),
          f"Lighting state: {env['lighting']}." if env["lighting"] else "",
          f"Atmosphere: {env['atmosphere']}." if env["atmosphere"] else "",
          "Do not add new props, structures, crystals, vehicles or background characters unless explicitly required by this beat.", ""]
    L += ["AUDIO CONTRACT:",
          "Use @Audio1 unchanged as the final supplied ElevenLabs V3 dialogue performance.",
          "Do not generate, replace, imitate, alter, reassign or retime speech.",
          "Lip-sync only the named speaking character to the matching supplied line.",
          "Generated audio may include only music, ambience, Foley and non-dialogue SFX. Duck generated audio under dialogue.",
          "Never generate humming, singing, vocalisations, spoken sound effects, extra dialogue or language not present in @Audio1.", ""]
    L += ["MUSIC AND SFX:", a["music"], (a["sfx"] or "Ambience and Foley appropriate to the scene; no vocal sounds."), ""]
    L += ["STYLE LOCK:",
          "Premium stylised 3D CGI feature animation matching the approved keyframe exactly.",
          "Polished feature-animation materials, expressive character performance, natural depth of field, stable picture, warm cinematic lighting appropriate to the scene.",
          "Prioritise consistency with the approved references over generic 8K, hyper-realistic or Octane language.", ""]
    L += ["POSITIVE CONSTRAINTS:",
          "Purposeful cinematic coverage that serves the beat. Stable character identity across every cut. Readable silhouettes. Consistent proportions. A bee's wings BEAT rapidly and continuously the ENTIRE time it is airborne — hovering, drifting, zipping or holding a pose in the air — a fast visible flap with motion blur-and-snap. Clear physical acting. Readable emotional reaction. Clean composition. Approved environment continuity. @Audio1 supplies all speech.", ""]
    neg = ["No random or purposeless cuts, jump cuts, sudden camera jumps or confusing reframes (purposeful cuts that preserve continuity are allowed).",
           "No morphing, flickering, character drift, duplicated characters or off-model faces.",
           "No extra characters.",
           "No text, subtitles, captions, logos or on-screen sound-effect words.",
           "No generated speech, humming, singing, vocalisations, extra dialogue or spoken sound effects.",
           "No Chinese, Mandarin or non-English speech.",
           "Do not retime, replace, imitate or alter @Audio1.",
           "Do not add clothing, jewellery, badge, strap, charm, pendant, necklace, medallion or crystal unless explicitly required.",
           "Do not render still, frozen, gliding or motionless wings on ANY bee that is airborne — a bee in the air is ALWAYS flapping (one that stopped would drop); wings only come to rest when the bee is fully landed or perched on a surface."]
    neg += a["character_negatives"] + a["beat_negatives"]
    L += ["NEGATIVE CONSTRAINTS:"] + neg + [""]
    L += ["CONTINUITY OUT:",
          f"End the beat in this exact state for the next beat: {a['continuity_out'] or 'hold the final composition described above.'}",
          f"Final hold: {a['final_hold']}",
          "No new action or dialogue after the final hold begins."]
    return "\n".join(x for x in L if x is not None)

# ── H — deterministic VALIDATOR ─────────────────────────────────────────────────────────────────────────────
# Cuts/internal shots are now ALLOWED — only mutation/identity/audio violations reject. (No "cut to"/"camera cuts".)
_REJECT = ["a voice lip-syncs", "a voice says", "someone says", "a character says", "generated humming",
           "generated singing", "vocal buzz", "extra dialogue",
           "hyper-realistic", "photorealistic", "octane render", "new pendant", "new necklace", "new medallion",
           "new crystal", "fuzzby wears crystal", "zenny wears crystal", "named speaker missing"]

# ── STALE-PROMPT DETECTOR — old-builder language that must NEVER reach Seedance, UI preview or export. These are
#    request-scoped + negation-aware via the same scan as _REJECT (so a "no …" negative never self-flags). Adding
#    them here means any path that routes through validate_seedance_prompt (preview/export/dryrun/render) catches them.
_STALE_TERMS = ["continuous unbroken take", "one continuous take", "sung buzz", "tiny sung buzz", "sung buzz rhythm",
                "ambient crystals hum", "crystals hum softly", "cinematic a dense",
                # flower-VANISH staging (the bee comedy "disappears into a flower" violation) — scoped to flower/bloom
                # so legit phrases ("flower meadow", Keen "plunges into the sea") are NOT false-flagged
                "dips into a flower", "dips into the flower", "plunges into the flower", "plunges into the bloom",
                "buried inside the flower", "buried inside the bloom", "disappears into the flower",
                "vanishes into the flower", "swallowed by the flower",
                # speaker-less / generated-voice language (always wrong — the dialogue must name a lip-sync speaker)
                "a voice says", "a voice lip-syncs", "someone says", "a character says",
                "generated humming", "generated singing", "vocal buzz"]

def detect_stale_prompt(prompt):
    """Hard-detect old-builder language / old JSON structure. `prompt` may be the flattened TEXT or a dict.
    Returns a list of stale findings ([] = clean). Used by validate + get_seedance_prompt + the render gate."""
    bad = []
    if isinstance(prompt, dict):
        for k in ("visual_prompt", "timeline"):
            if k in prompt:
                bad.append(f"old JSON structure key '{k}'")
        au = prompt.get("audio")
        if isinstance(au, dict) and au.get("sfx_prompt"):
            bad.append("old JSON structure 'audio.sfx_prompt'")
        cn = prompt.get("constraints")
        if isinstance(cn, dict) and cn.get("negative_prompt"):
            bad.append("old JSON structure 'constraints.negative_prompt'")
        text = json.dumps(prompt, ensure_ascii=False)
    else:
        text = str(prompt or "")
    low = text.lower(); req = low.split("negative constraints:")[0]
    for term in _STALE_TERMS:
        for m in re.finditer(re.escape(term), req):
            st = 1 + max(req.rfind(".", 0, m.start()), req.rfind("\n", 0, m.start()), req.rfind(";", 0, m.start()))
            if not re.search(r"\b(no|not|never|without|avoid|do not|don't)\b", req[st:m.start()]):
                bad.append(f'stale term: "{term}"'); break
    return bad

def validate_seedance_prompt(text, a):
    """Deterministic validator. Forbidden phrases are only REJECTED when REQUESTED (not when negated, e.g. 'no extra
    dialogue' / 'over generic hyper-realistic' / 'wears no crystal') — so the NEGATIVE CONSTRAINTS block and the
    character no-crystal locks never self-flag. Length is advisory (warn), not a hard fail."""
    rejects, warns = [], []
    request = text.split("NEGATIVE CONSTRAINTS:")[0]   # negations live in the NEGATIVE block — exclude it from reject scan
    rlow = request.lower()
    def _negated(idx):
        start = 1 + max(rlow.rfind(".", 0, idx), rlow.rfind("\n", 0, idx), rlow.rfind("!", 0, idx), rlow.rfind(";", 0, idx))
        return bool(re.search(r"\b(no|not|never|without|avoid|do not|don't|over generic|prioritise|wears no)\b", rlow[start:idx]))
    for bad in _REJECT:
        for m in re.finditer(re.escape(bad), rlow):
            if not _negated(m.start()):
                rejects.append(f'forbidden phrase requested: "{bad}"'); break
    crystals_present = any(("crystal" in cl["block"].lower() and "no crystal" not in cl["block"].lower())
                           for cl in a.get("character_locks", [])) or a.get("beat_code", "").startswith("9.")
    for phrase in ("ambient crystal hum", "crystals hum", "crystal hum"):
        if any(not _negated(m.start()) for m in re.finditer(re.escape(phrase), rlow)) and (a.get("bee_only") or not crystals_present):
            rejects.append(f'"{phrase}" requested but no crystals present in this beat'); break
    for m in re.finditer(r"(fuzzby|zenny)[^.\n]{0,28}crystal", rlow):
        if not _negated(m.end() - 7) and "no crystal" not in rlow[m.start():m.end() + 10]:
            rejects.append("a bee appears tied to a crystal"); break
    speakers = set(a.get("speakers") or [])
    if "Zenny" not in speakers and re.search(r"zenny (speaks|lip-syncs|says|delivers)", rlow):
        rejects.append('"Zenny speaks" but Zenny has no assigned line')
    low = text.lower()
    # ── SCRIPT GAG LOCK enforcement (mutation = FAIL) ──
    gag = a.get("gag_lock")
    if gag:
        if "moustache" not in low:
            rejects.append(f'gag {a.get("script_gag_lock_id")}: prompt does not contain "moustache"')
        else:
            mi, di = low.find("moustache"), low.find("do i look official")
            if di < 0:
                rejects.append('gag: the misread line "Do I look official?" is missing')
            elif mi > di:
                rejects.append('gag: the pollen moustache must be stated BEFORE "Do I look official?"')
        # the re-staged gag REQUIRES the readable handlebar+goatee disguise and the body staying outside the flower
        if "goatee" not in low:
            warns.append("gag: the pollen goatee is not described (payoff should be handlebar moustache + goatee)")
        # scan the REQUEST (not the NEGATIVE block, which legitimately says "no buried inside") + negation-aware
        if any(not _negated(m.start()) for m in re.finditer(
                r"buried inside|swallowed by|disappears? into the flower|plunges? into|enters the flower", rlow)):
            rejects.append("gag: Fuzzby must stay OUTSIDE the flower — no entering/burying/plunging/disappearing")
        if any(not _negated(m.start()) for m in re.finditer(r"\b(embarrass\w*|ashamed|shame|sad(ness|ly)?|humiliat\w*|wounded|tearful)\b", rlow)):
            warns.append("gag may be reframed as embarrassment/sadness/shame — keep Fuzzby proud & clueless")
    if a.get("gag_carry"):
        carry = str(a["gag_carry"]).lower().split()[0]
        if carry not in (a.get("continuity_in") or "").lower():
            rejects.append(f'gag carryover: continuity-in must carry "{a["gag_carry"]}" forward')
    # ── PHYSICAL STAGING INTENT enforcement (a physical gag must declare its staging, not just its emotion) ──
    dmode_phys = a.get("director_mode", ""); bcode = a.get("beat_code", "")
    if dmode_phys == "COMEDY_PHYSICAL" and not (a.get("physical_staging_intent") or "").strip():
        rejects.append("COMEDY_PHYSICAL beat has no PHYSICAL STAGING INTENT")
    if bcode == "1.B3b":
        if any(not _negated(m.start()) for m in re.finditer(r"plunges? into|buried inside|enters the flower|disappears? into", rlow)):
            rejects.append("1.B3b: Fuzzby must not plunge into / enter / be buried inside / disappear into the flower")
        if not ("handlebar" in low and "goatee" in low):
            rejects.append("1.B3b must state the handlebar moustache + goatee")
        if "smear" not in low:
            rejects.append("1.B3b must state the failed wipe / smear-worse action")
        co = (a.get("continuity_out") or "").lower()
        if not (("moustache" in co or "goatee" in co) and ("smear" in co or "messy" in co)):
            rejects.append("1.B3b continuity_out must preserve the smeared moustache/goatee")
    # ── PHYSICAL ACTION ARCHETYPE enforcement (scan the STAGED action, not the prohibited/boilerplate text) ──
    arch = a.get("physical_action_archetype", "")
    staged = " ".join((s.get("action", "") + " " + " ".join(s.get("dialogue", []))) for s in a.get("shots", [])).lower()
    scn = bcode.split(".")[0]
    if arch == "NEEDS_EXPLICIT_PHYSICAL_STAGING":
        rejects.append("high-risk physical beat has no resolvable physical_action_archetype (NEEDS_EXPLICIT_PHYSICAL_STAGING)")
    if arch == "LEAF_CRASH_REBOUND" and re.search(r"buried inside|disappears? into|plunges? into|swallow|face[- ]first into|vanish\w* into|makes it worse", staged):
        rejects.append("LEAF_CRASH_REBOUND must not stage face-first contact, flower entry, disappearing or 'makes it worse'")
    if arch == "POLLEN_FACE_PRESS_REVEAL":
        if re.search(r"full[- ]body|body enters the flower|buried inside|disappears? into", staged):
            rejects.append("POLLEN_FACE_PRESS_REVEAL must not stage full-body flower entry / disappearing")
        if not ("handlebar" in low and "goatee" in low):
            rejects.append("POLLEN_FACE_PRESS_REVEAL must state the handlebar moustache + goatee")
    if arch == "POLLEN_SMEAR_TUMBLE":
        cin = (a.get("continuity_in") or "").lower()
        if not (("moustache" in cin or "goatee" in cin) or "pollen" in cin):
            rejects.append("POLLEN_SMEAR_TUMBLE must enter still wearing the pollen moustache/goatee (carried in)")
    if arch == "UNDERWATER_NET_PULL":
        miss = [n for n, kws in (("geography", ("geography", "readable", "where")),
                ("trapped object", ("net", "trapped", "squeaky")),
                ("force direction", ("current", "force", "pull", "drag")),
                ("failed attempt", ("fail", "holds", "resist", "fading", "worsen"))) if not any(w in low for w in kws)]
        if miss:
            rejects.append("UNDERWATER_NET_PULL lacks: " + ", ".join(miss))
    if arch == "NET_TEAR_RELEASE":
        miss = [n for n, kws in (("final effort", ("final", "committed", "effort", "last pull")),
                ("net tear", ("tear", "rips", "torn")),
                ("danger/release", ("release", "danger", "foam", "separat", "free"))) if not any(w in low for w in kws)]
        if miss:
            rejects.append("NET_TEAR_RELEASE lacks: " + ", ".join(miss))
    if arch == "CRYSTAL_WRISTBAND_SET" and scn.isdigit() and int(scn) < 9:
        rejects.append(f"CRYSTAL_WRISTBAND_SET in Scene {scn} — only valid from Scene 9 (ceremony)")
    # BEE-ONLY scenes get no crystal language at all; mixed bee+bear scenes legitimately have the BEARS' crystals —
    # there a bee wearing a crystal is caught by the (fuzzby|zenny)…crystal check above, not this broad one.
    if a.get("bee_only") and any(
            not _negated(m.start()) for m in re.finditer(r"crystal hum|crystal glow|crystal ambience|magical glow|wears a crystal|wears an accessory", rlow)):
        rejects.append("bee-only beat contains crystal hum/glow/ambience or accessory drift")
    # ── shot-style coverage warnings ──
    shots = a.get("shots", []); roles = [s.get("role") for s in shots]
    mode = a.get("creative_mode", ""); style = a.get("shot_style", "")
    reactors = [c for c in a.get("characters", []) if c not in speakers]
    dmode_cov = a.get("director_mode", "")   # comedy-coverage checks key off the DIRECTOR mode, not the legacy creative mode
    if style == "SINGLE_TAKE" and dmode_cov.startswith("COMEDY"):
        warns.append("comedy beat is SINGLE_TAKE — consider COMEDY_CUTS coverage")
    if dmode_cov.startswith("COMEDY") and reactors and "react" not in roles:
        warns.append("comedy beat has no reaction shot")
    if dmode_cov == "COMEDY_PHYSICAL" and "impact" not in roles:
        warns.append("big physical gag has no impact shot")
    if gag and "reveal" not in roles:
        warns.append("reveal gag has no close/medium reveal shot")
    if "hold" not in roles:
        warns.append("no final hold shot")
    # ── EPISODE DIRECTOR — emotional-mode hard fails + warnings ──
    dmode = a.get("director_mode", ""); bc = a.get("beat_code", "")
    if bc == "7.B6" and (dmode in ("MAGIC_BEACON", "MAGIC_CEREMONY") or style == "MAGIC_COVERAGE"):
        rejects.append(f"7.B6 must be rescue/jeopardy, not MAGIC (got {dmode or style})")
    if bc == "3.B3" and (dmode == "ACTION_RESCUE" or style == "ACTION_COVERAGE"):
        rejects.append(f"3.B3 must be TENDER_LEAVING/HEART_COVERAGE, not action (got {dmode}/{style})")
    if bc == "4.B4" and not re.search(r"\b(panic|fear|isolat|alone|lost|afraid|vulnerab)\b", low):
        rejects.append("4.B4 (STORM_PANIC) lacks panic/isolation language")
    danger = r"\b(danger|net|trapped|current|drown|sink|strain|struggl|jeopard)\b"
    if dmode == "TENDER_LEAVING" and (style == "ACTION_COVERAGE" or re.search(r"\b(crash|crashes|tumble|slam|wallop|bonk)\b", low)):
        warns.append("TENDER_LEAVING staged as action — keep it held and gentle")
    if dmode == "STORM_PANIC" and not re.search(r"\b(fear|panic|isolat|alone|breath|grip|lost|rain|gust|overwhelm)\b", low):
        warns.append("STORM_PANIC reads too calm — needs fear/isolation")
    if dmode == "RESCUE_JEOPARDY" and not re.search(danger, low):
        warns.append("RESCUE_JEOPARDY has no clear danger")
    if dmode == "COURAGE_CHOICE" and not re.search(r"\b(decid|choice|chooses|hesitat|commit|resolve)\b", low):
        warns.append("COURAGE_CHOICE has no visible decision moment")
    if dmode == "RELIEF_RELEASE" and not re.search(r"\b(surface|burst|gasp|breath|relief|escape)\b", low):
        warns.append("RELIEF_RELEASE: relief before the danger peaks / no release moment")
    if dmode == "BELONGING_HOME" and not re.search(r"\b(pause|still|quiet|breath|hold|softn)\b", low):
        warns.append("BELONGING_HOME has no emotional pause")
    if dmode == "MAGIC_CEREMONY" and any(not _negated(m.start()) for m in
            re.finditer(r"\b(blast|shockwave|weapon|explos|zap)\b", rlow)):   # negation-aware: skips "never a weapon blast"
        warns.append("MAGIC_CEREMONY feels like a weapon blast — make it inner guidance")
    if dmode == "COMEDY_RELEASE" and re.search(r"\b(grief|sob|cry|mourn|devastat)\b", low):
        warns.append("COMEDY_RELEASE may undercut the emotion too early")
    if dmode == "COMEDY_PHYSICAL" and any(not _negated(m.start()) for m in
            re.finditer(r"\b(embarrass\w*|ashamed|tearful|wounded|sad(ness|ly)?)\b", rlow)):
        warns.append("COMEDY_PHYSICAL turning emotional before the gag lands")
    if dmode == "COMEDY_DEADPAN" and ("react" not in roles or "hold" not in roles):
        warns.append("COMEDY_DEADPAN lacks a reaction/hold")
    if style == "HEART_COVERAGE" and len([s for s in shots if s.get("role") != "hold"]) > 6:
        warns.append("HEART_COVERAGE beat is overcut — fewer, longer shots")
    if style == "ACTION_COVERAGE" and not any("wide" in (s.get("framing", "").lower()) for s in shots):
        warns.append("ACTION_COVERAGE beat has unclear geography — add a wide")
    # ── structural warnings ──
    n = len(text)
    if n > 4000:
        warns.append(f"prompt length {n} > 4000 chars (downstream API has no hard limit — advisory)")
    hold = next((s for s in shots if s.get("role") == "hold"), None)
    if hold and (hold["t1"] - hold["t0"]) < 1.5:
        warns.append(f"final hold {round(hold['t1']-hold['t0'],1)}s < 1.5s")
    for s in shots:
        for d in s.get("dialogue", []):
            if not any(k in d for k in ("lip-syncs", "performs", "voice-over")):
                warns.append("a dialogue line has no named speaker / treatment")
    if not a.get("continuity_out"):
        rejects.append("continuity_out is missing")          # hard fail (STEP 5)
    if "NEGATIVE CONSTRAINTS:" not in text:
        warns.append("beat has no negative constraints")
    if "@Audio1" not in text:
        rejects.append("@Audio1 ownership is missing")        # hard fail (STEP 5)
    if "@Image2" not in text:
        warns.append("beat has no approved keyframe reference")
    if any(c in BEES for c in a.get("characters", [])) and "wing" not in low:
        warns.append("a hovering bee is present but wings are not mentioned")
    rejects += detect_stale_prompt(text)                 # stale old-builder language = hard fail (source-of-truth guard)
    return {"ok": not rejects, "rejects": rejects, "warnings": sorted(set(warns)), "length": n}

# ── COMPACT RENDER PROMPT — authoring_json → validator → compact (~12 fields, ~1.2–2.5k). The 9k flattened prompt
#    is the production bible for the SOFTWARE; this is the disciplined prompt Seedance actually follows. Built from
#    the VALIDATED archetype staging + locks (NOT the raw cut text), so it stays short, clean and lock-preserving. ──
def _psi_parts(a):
    parts = {}
    for ln in (a.get("physical_staging_intent") or "").split("\n"):
        if ":" in ln:
            k, v = ln.split(":", 1); parts[k.strip().lower()] = v.strip()
    return parts

def _short_essence(cl):
    seg = cl.get("block", "").split("match to", 1)[-1]
    seg = seg.split(".", 1)[1].strip() if "." in seg else seg.strip()
    if seg.lower().startswith("keep the face"):
        return ""                                          # generic identity descriptor — just use the name
    return _cap(seg.split(", same ")[0], 70).rstrip(".")

def _t(x):
    """Format a beat time for the timeline (strip trailing .0): 0.0 -> '0', 9.6 -> '9.6', 12.0 -> '12'."""
    return f"{float(x):g}"

def _timeline_line(line):
    """Reformat a named lip-sync line to REFERENCE @Audio1 as the voice WITHOUT writing the words — so Seedance uses the
    supplied ElevenLabs voice AS the speech and never generates a duplicate. GROUP_CHORUS / underwater_vo pass through."""
    m = re.match(r'(.+?) lip-syncs exactly to @Audio1:\s*".*"\s*$', line)
    return f'{m.group(1)} speaks here, voiced ONLY by @Audio1 — lip-sync precisely to @Audio1' if m else line

def compact_seedance_prompt(a):
    """THE final render prompt — COMPACT_TIMED_JSON. The software does the detailed thinking in the authoring JSON;
    this emits the SIMPLE, VISUAL, TIMED, REFERENCE-FIRST object Seedance actually receives. EXACTLY these 11 fields:
    references, subject, scene, action_timeline, camera, performance, physical_staging, audio, style, negative, continuity_out."""
    p = _psi_parts(a)
    bee = bool(a.get("bee_only")) or any(c in BEES for c in a.get("characters", []))
    # 1. references — plate / keyframe / character_refs / dialogue_audio
    ch = a["references"].get("characters", [])
    references = {"scene_plate": "@Image1", "beat_keyframe": "@Image2",
                  "character_refs": {c["name"]: c["slot"] for c in ch}, "dialogue_audio": "@Audio1"}
    # 2. subject — who is present, frame relationship, match refs, no bee accessories
    sd = a["camera"].get("screen_direction", "")
    roles = "; ".join((cl["name"] + (f" ({e})" if (e := _short_essence(cl)) else "")) for cl in a.get("character_locks", []))
    subject = roles + ". Match the supplied character references EXACTLY."
    if sd:  subject += f" Screen direction {sd}."
    if bee: subject += " No crystals or accessories on any bee."
    subject = _cap(subject, 360)
    # 3. scene — location + lighting + atmosphere + Crystal Cove world-crystal rule (bee scenes)
    env = a["environment"]
    scene = _cap(". ".join(x.rstrip(". ") for x in (env.get("description"), env.get("lighting"), env.get("atmosphere")) if x), 250)
    if scene and not scene.endswith("."): scene += "."
    if bee:   # the Crystal Cove world-crystal rule must survive the cap (env is capped first, leaving room)
        scene += (" Subtle non-glowing environmental crystals only as background world texture, off the action path; "
                  "none on or near the bees.")
    scene = _cap(scene, 360)
    # 4-6. DIRECTED — when the Director's Pass ran, the action_timeline, camera and performance come from the Pixar
    # director reading the character bibles + the right mind; otherwise fall back to the mechanical mode-template build.
    dm = a.get("director_mode", "")
    dp = a.get("director_pass")
    if dp and dp.get("shots"):
        action_timeline = [{"time": s.get("time", ""), "action": _cap(s.get("action", ""), 380),
                            "camera": _cap(s.get("camera", ""), 190)}
                           for s in dp["shots"] if s.get("time") and s.get("action")]
        camera = {"coverage": a.get("shot_style", "DIRECTED_COVERAGE"),
                  "movement": _cap(dp.get("camera_approach", ""), 320),
                  "framing_rule": _cap(p.get("stays visible") or "keep the acting + the gag readable; honour the staging spine", 180)}
        performance = _cap((dp.get("performance", "") + " " + dp.get("expression", "")).strip(), 640)
    else:
        action_timeline = []
        for s in a.get("shots", []):
            act = s.get("action", "").rstrip(". ")
            act = (act + ".") if act else ""
            for d in s.get("dialogue", []):
                act += (" " if act else "") + _timeline_line(d)
            action_timeline.append({"time": f'{_t(s["t0"])}-{_t(s["t1"])}s', "action": _cap(act, 340)})
        camera = {"coverage": a.get("shot_style", "CINEMATIC_CUTS"),
                  "movement": _cap(("wide setup, playful follow on the action, then a locked medium-wide hold"
                                    if dm.startswith("COMEDY") else _clean(a.get("director_camera", ""))
                                    or "motivated, restrained coverage; purposeful cuts only"), 170),
                  "framing_rule": _cap(p.get("stays visible") or "keep the acting characters and the key gag readable; final hold long enough to land", 170)}
        perf = _clean(a.get("performance_notes", ""))
        if bee and dm.startswith("COMEDY") and "barely" not in perf.lower() and len(perf) < 120:
            perf += " Fuzzby moves too much; Zenny barely moves."
        performance = _cap(perf, 400)
    # 7. physical_staging — object generated from the resolved archetype + staging intent
    physical_staging = {"archetype": a.get("physical_action_archetype", ""),
                        "visibility": _cap(p.get("stays visible", ""), 200),
                        "contact": _cap(p.get("contact", ""), 240),
                        "physics": _cap(p.get("physics", ""), 240),
                        "payoff": _cap(p.get("payoff", ""), 200),
                        "prohibited": _cap(p.get("prohibited staging", ""), 300)}
    # 8. audio — @Audio1 ownership + non-vocal-only generation + voice treatments
    audio = ("Use @Audio1 unchanged as the final ElevenLabs dialogue. Lip-sync only the named speaker(s) to their supplied lines. "
             "Generate ONLY non-vocal music, ambience, Foley and SFX, ducked under dialogue. No generated speech, humming, singing or vocal buzz.")
    for vl in a.get("voice_locks", []):
        audio += " " + vl
    # 9. style — reference-first
    style = ("Reference-first premium stylised 3D CGI feature animation. Match the approved scene plate, beat keyframe and "
             "character references exactly. Warm cinematic lighting, polished materials, soft fur/skin shading, natural depth of field.")
    # 10. negative — hard avoids (incl. archetype-prohibited staging)
    core = ["no subtitles, captions, logos or on-screen text", "no generated speech, humming, singing or vocalisations",
            "no character drift, off-model faces, duplicated characters, morphing or flicker",
            "purposeful cuts only — no random jump cuts or confusing reframes"]
    neg = core + [n.rstrip(".") for n in (a.get("character_negatives") or [])] + [n.rstrip(".") for n in (a.get("beat_negatives") or [])]
    if physical_staging["prohibited"]:
        neg.append("no prohibited physical staging: " + physical_staging["prohibited"].rstrip("."))
    negative = _cap("; ".join(dict.fromkeys(x.strip() for x in neg if x.strip())), 580)
    # 11. continuity_out — T2 ruling (2026-07-02, Julian): a temporary state resolves WITHIN the take it started in;
    #     it never carries across a take boundary, so there is no continuity_video/previous-clip-tail field anymore.
    return {"references": references, "subject": subject, "scene": scene, "action_timeline": action_timeline,
            "camera": camera, "performance": performance, "physical_staging": physical_staging,
            "audio": _cap(audio, 420), "style": style, "negative": negative,
            "continuity_out": _cap(a.get("continuity_out", ""), 240)}

_COMPACT_FIELDS = ("references", "subject", "scene", "action_timeline", "camera", "performance",
                   "physical_staging", "audio", "style", "negative", "continuity_out")

def validate_compact_prompt(compact, a):
    """Hard-fail if COMPACT_TIMED_JSON lost a required field, lock, structure or carries stale language.
    (Length is advisory toward 1.2–2.8k.)"""
    rej = []; warns = []
    blob = json.dumps(compact, ensure_ascii=False); low = blob.lower()
    # ── structure: exactly the contract fields ──
    for f in _COMPACT_FIELDS:
        if f not in compact:
            rej.append(f"compact missing required field '{f}'")
    refs = compact.get("references", {})
    if not refs.get("character_refs"):
        rej.append("compact lost references.character_refs")
    if refs.get("dialogue_audio") != "@Audio1":
        rej.append("compact lost references.dialogue_audio @Audio1")
    if refs.get("scene_plate") != "@Image1" or refs.get("beat_keyframe") != "@Image2":
        rej.append("compact lost scene_plate/beat_keyframe references")
    # ── action_timeline: non-empty TIMED array, each step has time + visible action ──
    at = compact.get("action_timeline")
    if not isinstance(at, list) or not at:
        rej.append("compact action_timeline missing or empty")
    elif any(not (isinstance(s, dict) and s.get("time") and s.get("action")) for s in at):
        rej.append("compact action_timeline has a step missing time/action")
    # ── physical_staging: object with a real (non-NEEDS_EXPLICIT) archetype + concrete rules ──
    ps = compact.get("physical_staging", {})
    if not isinstance(ps, dict) or not ps.get("archetype"):
        rej.append("compact physical_staging missing archetype")
    elif ps.get("archetype") == NEEDS_EXPLICIT:
        rej.append("compact physical_staging archetype is NEEDS_EXPLICIT_PHYSICAL_STAGING")
    elif not any((ps.get(k) or "").strip() for k in ("visibility", "contact", "physics", "payoff", "prohibited")):
        rej.append("compact physical_staging has no concrete staging rules")
    # ── locks ──
    if "@audio1" not in low or "unchanged" not in low:
        rej.append("compact lost @Audio1 ownership")
    if "no generated speech" not in low:
        rej.append("compact lost the 'no generated speech/vocals' lock")
    if "match the supplied character references" not in low and "match the approved scene plate" not in low:
        rej.append("compact lost the character-reference identity lock")
    if not (compact.get("continuity_out") or "").strip():
        rej.append("compact lost continuity_out")
    if (a.get("bee_only") or any(c in BEES for c in a.get("characters", []))) and "no crystal" not in low:
        rej.append("compact lost the bee no-crystal rule")
    for vl in a.get("voice_locks", []):
        if "GROUP_CHORUS" in vl and "group_chorus" not in low and "group chorus" not in low:
            rej.append("compact lost the GROUP_CHORUS lock")
        if "nderwater" in vl and "underwater" not in low:
            rej.append("compact lost the underwater_vo lock")
    if a.get("gag_lock") and "moustache" not in low:
        rej.append("compact lost the gag payoff (moustache)")
    # ── stale language / old-JSON structure ──
    rej += detect_stale_prompt(compact)
    n = len(blob)
    if n < 1200:
        warns.append(f"compact length {n} < 1200 (very terse)")
    _ceiling = 8500 if (a.get("director_pass") and a["director_pass"].get("shots")) else 3500  # directed shot-breakdowns run richer
    if n > _ceiling:
        warns.append(f"compact length {n} > {_ceiling} (over target)")
    return {"ok": not rej, "rejects": rej, "warnings": warns, "length": n}

# Surgical-repair workflow — METADATA/DOCS ONLY (full video editing NOT implemented yet). When a small section is wrong:
# extract the bad section → fix ONE frame in Nano Banana → regenerate that section from the corrected frame.
SURGICAL_REPAIR_FIELDS = ("failed_clip_path", "bad_section_timecode", "extracted_fix_frame",
                          "nano_banana_corrected_frame", "repair_seedance_prompt", "replacement_clip_path")

def surgical_repair_metadata(beat_code="", **vals):
    """The surgical-repair metadata template (docs/metadata only — no video editing implemented yet)."""
    m = {f: "" for f in SURGICAL_REPAIR_FIELDS}; m["beat_code"] = beat_code
    m.update({k: v for k, v in vals.items() if k in m}); return m

# ── convenience: gather refs for a beat and build everything ─────────────────────────────────────────────────
def build_for_beat(pkg_path, beat_code, episode="Ep1"):
    d = json.load(open(pkg_path))
    beat = next(b for b in (d.get("beats") or d.get("shots") or [])
                if (b.get("beatCode") or b.get("shotCode")) == beat_code)
    sc = P.scene_cfg(episode, str(beat.get("sceneNumber")))
    slug = beat.get("slug") or beat_code.replace(".", "_")
    here = os.path.dirname(os.path.abspath(__file__))
    plate = sc.get("master") or f"media/{episode}_S{beat.get('sceneNumber')}_plate.png"
    keyframe = f"media/{episode}_{beat_code}_{slug}.png"
    oc = [c for c in (beat.get("openingCast") or beat.get("characters") or []) if c]
    char_refs = []
    for i, c in enumerate(oc):
        try:
            r = P.char_identity_ref(c)
        except Exception:
            r = ""
        char_refs.append({"slot": f"@Image{3+i}", "name": c, "ref": os.path.basename(r) if r else ""})
    audio_dur = _probe(os.path.join(here, "media", f"vo_{episode}_{beat_code}.mp3"))
    refs = {"image1_plate": plate, "image2_keyframe": keyframe, "characters": char_refs,
            "audio1": f"vo_{episode}_{beat_code}.mp3", "audio_dur": audio_dur}
    continuity = {"in": (beat.get("continuity") or {}).get("opensFrom", ""),
                  "out": (beat.get("continuity") or {}).get("carryToNext", "")}
    authoring = build_seedance_authoring_json(beat, sc, refs, continuity, episode=episode)
    prompt = flatten_seedance_prompt(authoring)               # the full bible (review/debug)
    report = validate_seedance_prompt(prompt, authoring)
    compact = compact_seedance_prompt(authoring)              # the disciplined render prompt
    compact_report = validate_compact_prompt(compact, authoring)
    return {"authoring": authoring, "prompt": prompt, "report": report,
            "compact": compact, "compact_report": compact_report}

# ── THE SINGLE SEEDANCE PROMPT ENTRY POINT — preview / copy-export / dry-run / render all go through here ─────────
def director_voice_direction(pkg_path, beat_code, episode="Ep1"):
    """THE single source for a beat's DIRECTED ElevenLabs acting — computes (+caches) the Director's Pass and returns
    its voice_direction (the locked words with V3 tags for the cadence/arc). EVERY voice path (Gate-3 render, the
    cascade audio step, the dialogue builder, the studio voice card) pulls from here so the SAME director drives the
    voice everywhere. Returns [] on any failure (safe -> cb_voice keyword fallback)."""
    try:
        dp = build_for_beat(pkg_path, beat_code, episode)["authoring"].get("director_pass")
        return (dp or {}).get("voice_direction") or []
    except Exception:
        return []

def get_seedance_prompt(pkg_path, beat_code, mode="render", episode="Ep1"):
    """THE source of truth for any Seedance prompt shown, copied, exported, dry-run or rendered. For a beat with a
    cb_segprompt segment it returns that DEFINITIVE prose (the signed-off Gate-3 formula, applied at the end of this
    function); otherwise the cb_seedance compact (COMPACT_TIMED_JSON) + readiness validator + stale detector. The old
    cb_prompts.seedance_json JSON builder has been REMOVED — no mode and no env var can reach it. Returns
    {builder, mode, prompt, authoring, readiness_status, hard_fails, warnings}."""
    if mode not in ("render", "preview", "export", "dryrun", "regen"):
        raise ValueError(f"unknown mode {mode!r}")
    # THE ONLY builders are cb_segprompt (definitive prose, applied at the end of this function) and cb_seedance (compact,
    # for beats without a segment). The old cb_prompts.seedance_json JSON path and its SEEDANCE_ALLOW_OLD_BUILDER hatch
    # have been REMOVED — there is no way to reach an old builder from any mode (preview/export/dryrun/regen/render).
    r = build_for_beat(pkg_path, beat_code, episode); a = r["authoring"]
    # COMPACT_TIMED_JSON is the ONLY shipping format for EVERY mode — UI preview = dry-run = export = regen = render.
    # The flattened production-bible prompt is REVIEW/DEBUG ONLY (explicit SEEDANCE_PROMPT_FORMAT=full).
    fmt = os.environ.get("SEEDANCE_PROMPT_FORMAT", "compact")
    is_compact = fmt != "full"
    chosen = r["compact"] if is_compact else r["prompt"]
    chosen_rep = r["compact_report"] if is_compact else r["report"]
    fmt_label = "COMPACT_TIMED_JSON" if is_compact else "FLATTENED_REVIEW"
    # READINESS requires BOTH the authoring/full validator AND the compact validator to pass — a clean compact must
    # NEVER override a failing authoring validator (stale source data must be fixed at the source first).
    arch_ok = bool(a.get("physical_action_archetype")) and a.get("physical_action_archetype") != NEEDS_EXPLICIT
    auth_ok = r["report"]["ok"]; comp_ok = r["compact_report"]["ok"]
    # the opening keyframe must exist + not be blocked before a beat can be READY_TO_RENDER
    here = os.path.dirname(os.path.abspath(__file__))
    kf = (a.get("references") or {}).get("image2_keyframe", "")
    kf_exists = bool(kf) and os.path.exists(kf if os.path.isabs(kf) else os.path.join(here, kf))
    # T2 ruling (2026-07-02, Julian): a temporary state resolves WITHIN the take it started in — it never carries
    # across a take boundary. The continuity-tail chaining/hard-fail machinery that used to gate on this is retired.
    if not auth_ok:
        status = "NEEDS_SOURCE_DATA_FIX"               # authoring fails (e.g. stale cut wording) → fix the source data
    elif not kf_exists:
        status = "NEEDS_KEYFRAME_REVIEW"               # prompt is clean but the opening keyframe isn't built/approved yet
    elif comp_ok and arch_ok and is_compact and a.get("director_mode"):
        status = "READY_TO_RENDER"
    else:
        status = "BLOCKED"
    # ── DEFINITIVE (Gate 3, single source): the signed-off 6-section Seedance prompt, GENERATED from THIS beat by
    #    cb_segprompt.for_beat — the SAME string cb_beats.run sends (both call for_beat), so the studio can never preview
    #    one prompt and fire another. UNIVERSAL: every beat of every episode comes out in the model. build_for_beat above
    #    still runs for validation/readiness; for_beat produces the shipped prose (dialogue lives in @Audio1, not the prose).
    _def = None
    try:
        import cb_segprompt
        _d = json.load(open(pkg_path))
        _beat = next((b for b in (_d.get("beats") or _d.get("shots") or [])
                      if (b.get("beatCode") or b.get("shotCode")) == beat_code), None)
        _scene = None
        if _beat and _d.get("scenes"):
            _sn = str(_beat.get("sceneNumber"))
            _scene = next((s for s in _d["scenes"] if str(s.get("sceneNumber")) == _sn), None)
        if _beat:
            _def = cb_segprompt.for_beat(_beat, _scene)
    except Exception:
        _def = None
    if _def:
        gen_status = ("NEEDS_SOURCE_DATA_FIX" if not auth_ok
                      else "NEEDS_KEYFRAME_REVIEW" if not kf_exists
                      else "READY_TO_RENDER")
        return {"builder": "cb_segprompt (GENERATED 6-section)", "mode": mode, "format": "DEFINITIVE_PROSE",
                "prompt": _def, "raw": True, "compact": _def, "full_prompt": _def, "authoring": a,
                "keyframe_exists": kf_exists,
                "authoring_validator": {"ok": auth_ok, "rejects": r["report"]["rejects"]},
                "compact_validator": {"ok": True, "rejects": [], "length": len(_def)},
                "readiness_status": gen_status,
                "hard_fails": r["report"]["rejects"], "warnings": []}
    return {"builder": "cb_seedance", "mode": mode, "format": fmt_label, "prompt": chosen,
            "compact": r["compact"], "full_prompt": r["prompt"], "authoring": a,
            "keyframe_exists": kf_exists,
            "authoring_validator": {"ok": auth_ok, "rejects": r["report"]["rejects"]},
            "compact_validator": {"ok": comp_ok, "rejects": r["compact_report"]["rejects"], "length": r["compact_report"]["length"]},
            "readiness_status": status,
            "hard_fails": r["report"]["rejects"] + r["compact_report"]["rejects"],
            "warnings": chosen_rep["warnings"]}


if __name__ == "__main__":
    import sys
    pkg = sys.argv[1] if len(sys.argv) > 1 else "../cb-output/Ep1_The_Adventure_Begins_beat_package.json"
    code = sys.argv[2] if len(sys.argv) > 2 else "1.B1"
    r = build_for_beat(pkg, code)
    print(r["prompt"])
    print("\n=== length:", r["report"]["length"], "| ok:", r["report"]["ok"])
