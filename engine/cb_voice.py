#!/usr/bin/env python3
"""Voice Director IN CODE — the crystal-bears-voice-director skill, made deterministic + runnable.

THE MIND (2026-06-24): the Crystal Bears VOICE DIRECTOR = Andrea ROMANO (cast to the cadence, direct the WANT, never
a line reading — the firewall against the flat-AI read) + Pete DOCTER (the feeling UNDER the line; the read smaller
than the moment) + Joe BRUMM / Bluey (the same-second co-watch), riding the ElevenLabs V3 instrument. Don't read the
line — ACT it, and NEVER change a word: direct only the performance layer (tag = colour, the TEXT does the acting),
play the NEED that leaks under the performed want, drop to a low-energy SURRENDER for Heart/Call/wordless beats, and
when a read is wrong fix the DATA (cadence / emotion→tag map / stability) and re-run — never hand-edit the mp3.

Turns a shot's LOCKED dialogue line + the character's cadence + the shot's intent/performance into a directed
ElevenLabs V3 line — canonical audio tags ([proudly]/[deadpan]/…), the phonetic name lock, and the per-character
voice settings that actually let the tags fire (stability <=~0.40, CRYSTAL_BEARS_LOCKED_CANON.md:144-158) — then
generates it in the character's canonical voice. It NEVER rewords the line (Director rule: dialogue is LOCKED
verbatim); it only ADDS tags + the phonetic spelling. The acted VO feeds Seedance ref2vid (@Audio1); SFX only,
music is post.

Canon: skills/crystal-bears-voice-director/SKILL.md  +  CRYSTAL_BEARS_LOCKED_CANON.md.

    python3 cb_voice.py line <Character> "<raw line>"     # print the directed V3 text
    python3 cb_voice.py say  <Character> "<raw line>" out.mp3
"""
import os, re, sys, json, shutil, subprocess
import cb_gen
import cb_prompts as P

_HERE = os.path.dirname(os.path.abspath(__file__))
_CHARS = json.load(open(os.path.join(_HERE, "config", "characters.json")))

def _char(name):
    if isinstance(_CHARS.get(name), dict):
        return _CHARS[name]
    return (_CHARS.get("characters") or {}).get(name, {})

# Phonetic name lock (SPOKEN text only) — SKILL.md §4
PHONETIC = {"Fuzzby": "Fuzz-bee", "Aida": "Ada", "Amie": "Ah-mee"}

# Per-character V3 stability — MUST stay <=~0.40 or the [tags] stop firing (LOCKED_CANON.md:155).
STABILITY = {"Fuzzby": 0.30, "Sunny": 0.30, "Keen": 0.30, "Amie": 0.35, "Keen's Mum": 0.38,
             "Zenny": 0.38, "Misty": 0.40, "Howey": 0.40, "Luna": 0.40, "Aida": 0.40}

# The character's SIGNATURE lead tag (cadence table, SKILL.md §5).
SIGNATURE = {"Fuzzby": "[proudly]", "Zenny": "[deadpan]", "Sunny": "[excited]", "Luna": "[calm]",
             "Aida": "[calm]", "Misty": "[calm]", "Amie": "[cheerfully]", "Howey": "[calm]",
             "Keen": "[curious]", "Keen's Mum": "[calm]"}

# Strong-signature leads: their cadence is a constant — don't cross-attribute a shot-level emotion to them.
_LEADS = ("Fuzzby", "Zenny")

# Emotion keyword -> canon tag (child-safe; only SKILL.md §3 vocabulary).
_EMO = [
    (("offend", "proud", "pompous", "majest", "boast", "brav", "confiden"), "[proudly]"),
    (("excit", "manic", "energet", "thrill", "eager"), "[excited]"),
    (("deadpan", "dry", "flat", "unimpress"), "[deadpan]"),
    (("nervous", "awkward", "anxious", "worried", "sheepish", "embarrass"), "[nervous]"),
    (("scare", "fright", "afraid", "fear", "cower"), "[nervous]"),
    (("frustrat", "annoy", "indignant"), "[frustrated]"),
    (("calm", "serious", "steady", "settled", "resolv"), "[calm]"),
    (("sad", "sorrow", "downcast", "crest"), "[sorrowful]"),
    (("curious", "wonder", "intrigu"), "[curious]"),
    (("tired", "weary", "exhaust"), "[tired]"),
    (("play", "cheek", "mischiev"), "[playfully]"),
    (("happy", "joy", "cheer", "delight", "beam"), "[cheerfully]"),
    (("regret", "sorry", "apolog"), "[regretful]"),
]

def _emotion_tag(text):
    t = (text or "").lower()
    for keys, tag in _EMO:
        if any(k in t for k in keys):
            return tag
    return None

def phonetic(line):
    out = line
    for name, ph in PHONETIC.items():
        out = re.sub(rf"\b{re.escape(name)}\b", ph, out)
    return out

def _is_tender(shot):
    """Heart / surrender / nadir / Crystal-Call beat — the LOW-ENERGY palette (quieter, slower, never bigger)."""
    if not shot:
        return False
    if shot.get("wordlessHeld"):
        return True
    ei = str(shot.get("emotionalIntent", "")).lower()
    # COMEDY ALWAYS WINS — a comedic beat is never voiced with the tender/quiet palette, even if its PHYSICS use words
    # like 'surrender to gravity' or 'ache' (that's a fall, not a feeling).
    if any(re.search(r"\b" + w + r"\b", ei) for w in ("comedic", "comedy", "funny", "delight", "gag",
                                                       "slapstick", "hubris", "silly", "goofy", "playful")):
        return False
    glow = (shot.get("crystalGlow") or "").lower()
    # tenderness reads off the EMOTIONAL field only (not physicalFeeling=body-physics / storyBeat=plot, which use
    # physical metaphors that collide). WORD-BOUNDARY so 'cry' can't match 'crystal' (which tripped every beat).
    terms = ("surrender", "let go", "lets go", "letting go", "ache", "grief", "cry", "cries", "weep",
             "tender", "comfort", "held breath", "nadir", "heartbreak", "heartbroken", "longing")
    return ("crystal call" in ei or "dimming" in glow
            or any(re.search(r"\b" + re.escape(w) + r"\b", ei) for w in terms))

def settings(character, shot=None):
    """V3 voice settings — STABILITY BAND IS LAW: never above 0.40 (above it the [tags] go silent). Heart /
    surrender / Crystal-Call beats drop to the floor (quieter, more let-go)."""
    st = min(0.40, STABILITY.get(character, 0.35))
    if _is_tender(shot):
        st = max(0.25, round(st - 0.05, 2))
    return {"stability": st, "similarity_boost": 0.9, "style": 0.0}

def _line_for(shot, character):
    """One speaker's own words from the shot dialogue (their LABEL: up to the next LABEL: or end)."""
    dlg = shot.get("dialogue") or ""
    pairs = re.findall(r"([A-Z][A-Z'’ ]{1,22}?):\s*(.*?)(?=\n[A-Z][A-Z'’ ]{1,22}?:|\Z)", dlg, re.S)
    for lab, txt in pairs:
        ll = lab.strip().lower()
        if ll == character.lower() or character.lower() in ll or ll in character.lower():
            return " ".join(txt.split())
    if not pairs and dlg.strip():
        return " ".join(dlg.split())
    return None

_MASKING = ("[proudly]", "[cheerfully]", "[excited]", "[deadpan]", "[playfully]")

def _tags(character, shot):
    if _is_tender(shot):
        return ["[quietly]"]                     # PROTECT THE HELD BEAT / SURRENDER THE CALL — low-energy, even for the leads
    sig = SIGNATURE.get(character)
    if character in _LEADS:
        return [sig] if sig else []
    ctx = ""
    if shot:
        ctx = ((shot.get("intent") or {}).get("emotion") or "") + " " + ((shot.get("performance") or {}).get("surface") or "")
    return [t for t in [_emotion_tag(ctx) or sig] if t][:2]

def _leak(shot, tags):
    """PLAY THE NEED: when a bear performs a WANT (a masking surface — proud/cheerful/excited/deadpan/playful)
    while a NEED leaks under it, drop ONE non-verbal at the end — the breath that betrays the held feeling.
    One leak, placed once; never a second emotion word. (The crystal contradicts the face; so must the voice.)"""
    if not shot or _is_tender(shot):
        return ""
    contradiction = bool(shot.get("crystalTruth") or shot.get("need")
                         or ((shot.get("performance") or {}).get("underneath")))
    if not (contradiction and any(t in _MASKING for t in (tags or []))):
        return ""
    return " [gulps]" if "[proudly]" in (tags or []) else " [exhales]"

def direct_line(character, shot=None, raw=None):
    """Directed V3 text (tags + phonetic + the need-leak) for one character's line. NEVER rewords the locked line —
    only the performance layer around and under it (tag = colour, the TEXT does the acting)."""
    line = raw if raw is not None else _line_for(shot, character)
    if not line:
        return None
    spoken = phonetic(line)
    tags = _tags(character, shot)
    leak = _leak(shot, tags)
    head = (" ".join(tags) + " ") if tags else ""
    return (head + spoken + leak).strip()

def say(character, shot=None, raw=None, out=None, pre=None):
    """Direct + generate one line in the character's canonical V3 voice. pre = a pre-directed line (with its tags
    already in it) — used VERBATIM, bypassing auto-direction, for the manual voice override on the card.
    Returns {character, voiceId, text, stability, out}."""
    text = pre.strip() if (pre and pre.strip()) else direct_line(character, shot=shot, raw=raw)
    if not text:
        return None
    cc = _char(character)
    vid = cc.get("voiceId")
    if not vid:
        raise SystemExit(f"no voiceId for {character!r} in characters.json")
    st = settings(character, shot)
    out = out or f"vo_{re.sub(r'[^A-Za-z0-9]', '', character)}.mp3"
    mp3 = cb_gen.eleven_tts(text, vid, out=out, **st)
    return {"character": character, "voiceId": vid, "text": text, "stability": st["stability"], "out": mp3}

def _canon_names():
    """Every canonical character name (characters.json) — the stale-pool safety net for speaker resolution."""
    base = _CHARS.get("characters") if isinstance(_CHARS.get("characters"), dict) else _CHARS
    return [k for k, v in base.items() if isinstance(v, dict)]

def _cut_segments(dlg):
    """Split a cut's (possibly MULTI-speaker) dialogue into ordered (label, line) segments. Each 'LABEL:' opens a new
    segment; an unlabelled line MERGES into the previous speaker (a script wraps one line across two). THE VOICE-DRIFT
    FIX: a cut can hold more than one speaker (FUZZBY: …\\nZENNY: …). Previously only the FIRST label was parsed, so
    the whole cut — every speaker's line, plus the literal 'ZENNY:' label text — was voiced in that first speaker's
    voice (Zenny's line in Fuzzby's voice). Now every speaker-segment is voiced separately, in its own voice. Only
    ALL-CAPS labels (FUZZBY / KEEN'S MUM) open a segment, so ordinary 'Word:' text is never mistaken for a speaker."""
    dlg = (dlg or "").strip()
    if not dlg:
        return []
    pairs = re.findall(r"([A-Z][A-Z'’ ]{1,22}?):\s*(.*?)(?=\n\s*[A-Z][A-Z'’ ]{1,22}?:|\Z)", dlg, re.S)
    if not pairs:
        return [(None, " ".join(dlg.split()).strip('"“”'))]
    out = []
    for lab, txt in pairs:
        line = " ".join(txt.split()).strip('"“”')
        if line:
            out.append((lab.strip(), line))
    return out

def _upcase_leading_label(line):
    """Normalise a leading 'Name:' speaker label to ALL-CAPS so _cut_segments parses it. A voiceScript is a HUMAN edit
    field, so its labels are naturally Title-case ('Fuzzby:', 'Zenny:') — but _cut_segments only opens a segment on an
    ALL-CAPS label, so a mixed-case label was silently swallowed and the line fell to the FIRST speaker (Zenny voiced as
    Fuzzby, the literal 'Zenny:' spoken). Uppercasing ONLY the leading label (never the dialogue) makes the override
    robust to case. Applies only at line start, so mid-line 'word:' text is never mistaken for a speaker."""
    return re.sub(r"^\s*([A-Za-z][A-Za-z'’ \-]{0,22}?):", lambda m: m.group(1).strip().upper() + ":", line)

def _parse_cut_line(dlg):
    """DEPRECATED single-segment shim (kept for back-compat). Returns the FIRST speaker-segment only — callers that
    may see multi-speaker cuts must use _cut_segments instead, or they re-introduce voice drift."""
    segs = _cut_segments(dlg)
    return segs[0] if segs else (None, "")

def _resolve_speaker(label, shot):
    """Map a cut label (FUZZBY / KEEN'S MUM) to the exact canonical character name. Resolve against the beat's speaker
    pool first, then ALL canon characters (so a label still reaches its true voice even if the beat's speaker list is
    stale). An UNLABELLED line falls back to the sole/first speaker; a LABELLED line NEVER silently borrows another
    character's voice — it resolves to its own name, and say() fails loud if that name has no canonical voiceId."""
    pool = (shot.get("speakers") or P._speakers(shot) or [])
    if not label:
        return pool[0] if pool else None
    ll = label.strip().lower()
    for c in list(pool) + _canon_names():
        cl = c.lower()
        if cl == ll or ll in cl or cl in ll:
            return c
    return label.title()

def _muffle(path):
    """Internal/underwater muffle (low-pass + slight attenuation) on a rendered line, in place. Polish only —
    never let it break the track."""
    tmp = path.rsplit(".", 1)[0] + "_uw.mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", path, "-af", "lowpass=f=850,volume=0.8", tmp],
                       check=True, capture_output=True)
        shutil.move(tmp, path)
    except Exception:
        pass
    return path

def _chorus(line, members, out="vo_chorus.mp3"):
    """GROUP_CHORUS — render `line` in each member's canonical voice and LAYER them (ffmpeg amix) into ONE unison
    group asset (explicitly NOT one character lip-syncing). Returns the mixed mp3 path, or None."""
    rendered = []
    for j, m in enumerate([x for x in (members or []) if x][:4]):   # cap the layer (unison feel; limits API calls)
        if not _char(m).get("voiceId"):                              # skip a member with no canonical V3 voice
            continue
        try:
            r = say(m, raw=line, out=f"_chor{j}_{re.sub(r'[^A-Za-z0-9]', '', m)}.mp3")
        except Exception:
            continue
        if r:
            rendered.append(r["out"])
    if not rendered:
        return None
    final = str(cb_gen.MEDIA / out)
    if len(rendered) == 1:
        shutil.copy(rendered[0], final)
    else:
        ins = []
        for p in rendered:
            ins += ["-i", p]
        subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex",
                        f"amix=inputs={len(rendered)}:duration=longest:normalize=0[out]", "-map", "[out]", final],
                       check=True, capture_output=True)
    return final

def _norm_words(s):
    """Words only — strip V3 [tags] + punctuation — to match a director's acted line back to the locked cut line."""
    s = re.sub(r"\[[^\]]*\]", "", s or "")
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())

def _voice_dir_lookup(voice_direction):
    """(speaker, normalized words) -> the DIRECTOR's acted (V3-tagged) line. Words-keyed, so it only fires when the
    director kept the locked words EXACTLY (a changed word simply misses -> safe fallback to keyword auto-direction)."""
    out = {}
    for v in (voice_direction or []):
        spk = str((v or {}).get("speaker") or "").strip().lower()
        al = str((v or {}).get("acted_line") or "").strip()
        if spk and al:
            out[(spk, _norm_words(al))] = al
    return out

def _pad_min(final):
    """Seedance ref2vid requires audio_urls >= 2.0s — pad a short track with trailing silence."""
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=nw=1:nk=1", final], capture_output=True, text=True).stdout.strip() or "0")
    if d < 2.1:
        tmp = final.rsplit(".", 1)[0] + "_pad.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", final, "-af", "apad=whole_dur=2.5", tmp], check=True, capture_output=True)
        shutil.move(tmp, final)

def _resolve_turns(shot, vd):
    """Resolve the beat's ordered speaker TURNS — {character, voiceId, text, label, treatment, members} — WITHOUT
    synthesising. `text` is the directed V3 line (director's acted line if present, else auto-directed); labelled lines
    resolve to their own canon voice (fails loud on a missing voiceId). Shared by both the Text-to-Dialogue and the
    per-line paths, so the ACTING is identical whichever renders it."""
    turns = []
    def add(speaker, line, pre=None, delivery="", treatment="", label=None):
        if not (speaker and line):
            return
        text = (pre.strip() if (pre and pre.strip())
                else direct_line(speaker, shot={"performance": {"surface": delivery}, "intent": {}}, raw=line))
        if not text:
            return
        vid = _char(speaker).get("voiceId")
        if not vid:
            raise SystemExit(f"no voiceId for {speaker!r} in characters.json")
        turns.append({"character": speaker, "voiceId": vid, "text": text, "label": label, "treatment": treatment})
    vs = (shot.get("voiceScript") or "").strip()
    cut_dlg = [c for c in (shot.get("cuts") or []) if (c.get("dialogue") or "").strip()]
    if vs:                           # MANUAL OVERRIDE — acted lines used VERBATIM (still case-insensitive labels)
        for ln in [l for l in vs.splitlines() if l.strip()]:
            for label, line in _cut_segments(_upcase_leading_label(ln.strip())):
                add(_resolve_speaker(label, shot), line, pre=line, label=label)
    elif cut_dlg:                    # BEAT — each speaker-segment of each cut, in order
        for c in cut_dlg:
            vt = (c.get("voiceTreatment") or "").strip()
            if vt == "group_chorus":     # a unison/crowd asset, never one character lip-syncing
                line = " ".join(t for _, t in _cut_segments(c.get("dialogue")) if t)
                if line:
                    turns.append({"character": "GROUP_CHORUS", "voiceId": None, "text": line, "label": None,
                                  "treatment": "group_chorus", "members": c.get("chorusMembers") or shot.get("speakers") or []})
                continue
            for label, line in _cut_segments(c.get("dialogue")):
                spk = _resolve_speaker(label, shot)
                pre = vd.get((spk.lower(), _norm_words(line))) if spk else None   # the DIRECTOR's acted line, else auto-direct
                add(spk, line, pre=pre, delivery=c.get("delivery", ""), treatment=vt, label=label)
    else:                           # legacy per-shot dialogue — by speaker
        for c in (P._speakers(shot) or []):
            add(c, _line_for(shot, c), label=c)
    return turns

def build_dialogue_track(shot, out="vo.mp3", gap=0.55, voice_direction=None):
    """The beat's dialogue, acted + voiced in canon, as ONE <=15s @Audio1 track. THE OPTIMUM (locked 2026-07-01):
    V3 TEXT-TO-DIALOGUE — the whole beat is generated in ONE in-context pass so the model matches prosody across
    speakers, times the reactions, and lets each line breathe (far better acting than synthesising one-liners alone).
    Each turn keeps its own voice; the [audio tags] lead the delivery. Falls back to per-line synthesis + concat for
    special voiceTreatments (chorus/underwater) or if the dialogue call errors. Returns {track, lines, speakers}."""
    if shot.get("wordlessHeld"):   # the ONE wordless held beat per episode — silence carries it, never a voice (rule 9)
        return None
    vd = _voice_dir_lookup(voice_direction)    # the Director's per-line acted V3 lines (cadence/arc), used as `pre`
    if not vd:                                  # SOFTWARE-WIDE SAFETY NET: no explicit direction passed → load the cached director acting
        try:
            import cb_director_pass as _DP
            _code = str(shot.get("beatCode") or shot.get("shotCode") or "")
            _m = re.match(r"vo_([A-Za-z0-9]+)_", out or "")
            _ep = _m.group(1) if _m else "Ep1"
            if _code:
                vd = _voice_dir_lookup(_DP.cached_voice_direction(_ep, _code))
        except Exception:
            pass
    turns = _resolve_turns(shot, vd)
    # ATTRIBUTION GUARD — every labelled line MUST be voiced by the character its label names, never another voice.
    drift = [f"line labelled '{t.get('label')}' voiced as '{t.get('character')}'" for t in turns
             if t.get("label") and t.get("character") not in ("GROUP_CHORUS", None)
             and not (t["character"].lower() == str(t["label"]).strip().lower()
                      or str(t["label"]).strip().lower() in t["character"].lower()
                      or t["character"].lower() in str(t["label"]).strip().lower())]
    if drift:
        raise SystemExit(f"VOICE ATTRIBUTION DRIFT in {shot.get('beatCode') or shot.get('slug')}: " + "; ".join(drift))
    if not turns:
        return None
    final = str(cb_gen.MEDIA / out)
    specials = any(t["treatment"] in ("group_chorus", "underwater_vo") for t in turns)
    # ── OPTIMUM: V3 Text-to-Dialogue — the whole beat acted TOGETHER, in context (no special treatments) ──
    if not specials:
        try:
            st = 0.25 if _is_tender(shot) else 0.30       # expressive 'Creative' zone; tender beats even lower
            cb_gen.eleven_dialogue([{"text": t["text"], "voice_id": t["voiceId"]} for t in turns], out=out, stability=st)
            _pad_min(final)
            print(f"  voice: V3 Text-to-Dialogue — {len(turns)} turns acted in one in-context pass (stability {st})", flush=True)
            return {"track": final, "builder": "eleven_v3_dialogue", "attribution_ok": True,
                    "lines": [{"character": t["character"], "label": t["label"], "text": t["text"]} for t in turns],
                    "speakers": [t["character"] for t in turns]}
        except Exception as e:
            print(f"  voice: Text-to-Dialogue failed ({str(e)[:110]}) — falling back to per-line synthesis", flush=True)
    # ── FALLBACK: per-line synthesis + concat (special treatments, or the dialogue call errored) ──
    segs = []
    for t in turns:
        if t["treatment"] == "group_chorus":
            ch = _chorus(t["text"], t.get("members"), out=f"_seg{len(segs)}_chorus.mp3")
            if ch:
                segs.append({"character": "GROUP_CHORUS", "label": None, "text": t["text"], "out": ch})
            continue
        r = say(t["character"], shot={"performance": {"surface": ""}, "intent": {}}, pre=t["text"],
                out=f"_seg{len(segs)}_{re.sub(r'[^A-Za-z0-9]', '', t['character'])}.mp3")
        if r:
            if t["treatment"] == "underwater_vo":
                _muffle(r["out"])
            r["label"] = t["label"]; segs.append(r)
    if not segs:
        return None
    if len(segs) == 1:
        shutil.copy(segs[0]["out"], final)
    else:
        ins = []
        for s in segs:
            ins += ["-i", s["out"]]
        n = len(segs)
        fc = "".join(f"[{j}:a]apad=pad_dur={gap}[a{j}];" for j in range(n - 1))
        fc += "".join(f"[a{j}]" if j < n - 1 else f"[{j}:a]" for j in range(n))
        fc += f"concat=n={n}:v=0:a=1[out]"
        subprocess.run(["ffmpeg", "-y", *ins, "-filter_complex", fc, "-map", "[out]", final],
                       check=True, capture_output=True)
    _pad_min(final)
    return {"track": final, "builder": "eleven_v3_perline", "attribution_ok": True,
            "lines": [{"character": s["character"], "label": s.get("label"), "text": s["text"], "out": s.get("out")} for s in segs],
            "speakers": [s["character"] for s in segs]}

def audit_attribution(package_path):
    """ACROSS-THE-BOARD regression check — NO audio generated. For every beat, split every cut into speaker-segments
    and confirm each labelled line resolves to its OWN character with a real canonical voiceId, with no speaker label
    leaking into the spoken text. Catches the whole class of voice drift (multi-speaker collapse, label leak,
    unresolved/voiceless label) before anything is voiced. Returns a list of problem strings ([] = clean)."""
    d = json.load(open(package_path))
    beats = d.get("beats") or d.get("shots") or []
    problems = []
    for b in beats:
        if b.get("wordlessHeld"):
            continue
        code = b.get("beatCode") or b.get("slug") or "?"
        for ci, c in enumerate(b.get("cuts") or [], 1):
            if (c.get("voiceTreatment") or "").strip() == "group_chorus":
                continue
            for label, line in _cut_segments(c.get("dialogue")):
                if not line:
                    continue
                if re.search(r"[A-Z][A-Z'’ ]{1,22}?:", line):
                    problems.append(f"{code} cut{ci}: a speaker label leaked into the spoken text -> \"{line[:48]}\"")
                if not label:
                    continue                                   # unlabelled single line -> the sole speaker (ok)
                sp = _resolve_speaker(label, b)
                if not sp or not _char(sp).get("voiceId"):
                    problems.append(f"{code} cut{ci}: label '{label}' -> '{sp}' has NO canonical voiceId")
    return problems


if __name__ == "__main__":
    os.chdir(_HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "line"
    if cmd == "line":
        print(direct_line(sys.argv[2], raw=sys.argv[3]))
    elif cmd == "say":
        out = sys.argv[4] if len(sys.argv) > 4 else "vo.mp3"
        print(say(sys.argv[2], raw=sys.argv[3], out=out))
    elif cmd == "audit":                 # python3 cb_voice.py audit ../cb-output/<package>.json
        probs = audit_attribution(sys.argv[2])
        print(json.dumps({"ok": not probs, "problems": probs}, indent=1))
