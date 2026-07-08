#!/usr/bin/env python3
"""FAITHFUL SCREENPLAY PARSER — Gate 1's ground truth.

Reads a signed-off screenplay and extracts, DETERMINISTICALLY (no LLM, so it can NEVER reword, drop or invent), the
exact SCENES, ACTION lines and DIALOGUE. The Director's job downstream is to GROUP these verbatim elements into beats
and bring them to life with cinematography + 3D-CGI animation — it never types a word of the script itself, so the
dialogue and staging can only ever be the writer's. This module is the reason "100% to the script" is a guarantee, not
a hope.

parse(script_text, roster) -> [
  { "sceneNumber": int, "heading": str, "location": str, "time": str,
    "elements": [ {"type":"action","text": "<verbatim>"} |
                  {"type":"dialogue","character":"FUZZBY","parenthetical":"(dry)"|"","line":"<verbatim>"} ] }
]
roster = the UPPER-CASE cast names (so a cue is detected by matching a real character, never guessed).
"""
import re

TRANSITIONS = {"FADE IN:", "FADE IN", "FADE OUT.", "FADE OUT:", "FADE OUT", "CUT TO:", "SMASH CUT:",
               "DISSOLVE TO:", "MATCH CUT:", "THE END", "CONTINUED:", "BACK TO SCENE"}

def _is_scene_heading(line):
    s = line.strip()
    return bool(re.match(r"^(INT|EXT|INT\./EXT|EXT\./INT)[\.\s]", s, re.I))

def _scene_number(line):
    m = re.search(r"(\d+)\s*$", line.strip())
    return int(m.group(1)) if m else None

def _scene_loc_time(line):
    # "EXT. DEEP WITHIN THE RAINFOREST – DAY   3" -> location, time
    s = re.sub(r"\s*\d+\s*$", "", line.strip())               # drop the trailing scene number
    s = re.sub(r"^(INT|EXT|INT\./EXT|EXT\./INT)[\.\s]+", "", s, flags=re.I)
    parts = re.split(r"\s[–—-]\s", s)                         # split on en-dash / em-dash / hyphen
    time = parts[-1].strip() if len(parts) > 1 else ""
    loc = " – ".join(p.strip() for p in parts[:-1]) if len(parts) > 1 else s.strip()
    return loc.strip(), time.strip()

def _cue_name(line, roster):
    """If `line` is a DIALOGUE CUE (optional number, an EXACT roster name, optional (CONT'D)), return the character;
    else None. Exact-match against the roster is what stops markers like 'CRYSTAL CALL SEQUENCE.' or
    'AIDA'S INNER VISION —' being mistaken for a speaker."""
    s = line.strip()
    s = re.sub(r"^\s*\d+\s+", "", s)                          # leading scene/cue number
    s = re.sub(r"\s*\(\s*CONT'?[’'`´]?D\s*\)\s*$", "", s, flags=re.I)   # (CONT'D) — any apostrophe style
    s = re.sub(r"\s*\(.*?\)\s*$", "", s)                      # a trailing (parenthetical) on the cue line
    key = _na(s.strip().upper())                             # normalise apostrophes so KEEN'S MUM (curly ') matches the roster
    return key if key in roster else None

def _na(s):
    """Normalise every apostrophe/backtick variant to a straight ' — so 'KEEN’S MUM' (curly) matches 'KEEN'S MUM'."""
    return re.sub(r"[’'`´ʼ]", "'", s or "")

def _norm(s):
    return " ".join((s or "").split())

_ALT_MARKERS = {"ALT", "ALT.", "ALTERNATE", "ALTERNATIVE", "OPTION", "OPT", "OR"}
_CUE_SHAPE = re.compile(r"^\s*\d*\s*([A-Z][A-Z' ]{1,24})(?:\s*\(.*\))?\s*$")
_NAME_START = re.compile(r"^([A-Z][A-Za-z']*)\b(.*)$")

def parse(script_text, roster, warn=None):
    """warn(msg) is called (if given) when a line LOOKS like a speaker cue (short, ALL-CAPS, its own line) but
    doesn't match the roster — an unrecognized/misspelled character name would otherwise vanish silently into the
    surrounding action text, with nothing downstream able to detect the loss."""
    roster = {_na(r.strip().upper()) for r in roster} | {"ALL"}
    lines = script_text.replace("\r\n", "\n").split("\n")
    scenes = []
    cur = None            # current scene
    i = 0
    _warned = set()        # dedupe — a recurring scene-structure marker (UNDERWATER, SHORE POV) shouldn't repeat
    # skip everything before the first scene heading (title page, FADE IN)
    while i < len(lines) and not _is_scene_heading(lines[i]):
        i += 1
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if _is_scene_heading(raw):
            loc, time = _scene_loc_time(raw)
            cur = {"sceneNumber": _scene_number(raw), "heading": _norm(raw), "location": loc, "time": time, "elements": []}
            scenes.append(cur); i += 1; continue
        if cur is None:
            i += 1; continue
        up = line.upper().rstrip(".:")
        if not line or up in {t.rstrip(".:") for t in TRANSITIONS}:
            i += 1; continue
        cue = _cue_name(raw, roster)
        if cue:
            # collect the parenthetical(s) + dialogue lines until a blank line / next cue / next scene heading
            i += 1
            paren, dlines = [], []
            while i < len(lines):
                nl = lines[i]; ns = nl.strip()
                if not ns or _is_scene_heading(nl) or _cue_name(nl, roster):
                    break
                pm = re.match(r"^\((.*)\)$", ns)
                if pm:
                    tag = pm.group(1).strip().upper()
                    if not dlines:                            # a parenthetical BEFORE the words -> a delivery direction, keep it
                        paren.append(ns); i += 1; continue
                    if tag in _ALT_MARKERS:                    # an ALT/OPTION marker mid-speech: the writer hasn't
                        i += 1; break                          # locked ONE final line — stop here, never blend the
                                                                # alternate text into the verbatim ground truth
                    i += 1; continue                           # any other mid-line direction (e.g. "(beat)") -> strip, keep collecting
                if dlines and re.search(r"[.!?][\"'’”]*$", dlines[-1]):
                    m = _NAME_START.match(ns)
                    if m and _na(m.group(1).upper()) in (roster - {"ALL"}) and m.group(2).strip():
                        # a new sentence starting with a roster character's own name, directly after a completed
                        # line of dialogue, with NO blank line in the source to separate them — almost always
                        # third-person ACTION narration bleeding into the dialogue block (the writer's source
                        # formatting simply omitted the blank line before the next action paragraph), never more
                        # speech — a real speaker doesn't open a fresh sentence by naming themselves or another
                        # character as its bare grammatical subject straight after a full stop. Found live
                        # 2026-07-07: this exact gap let cb_script swallow "Fuzzby zooms right into Keen's face."
                        # and "Aida smiles." onto the end of KEEN's preceding line, so the "ground truth" dialogue
                        # a downstream verbatim check compares against was itself polluted with action prose.
                        # ("ALL" excluded — a common English word, not just a roster name, so it would false-fire
                        # constantly if left in.) Stop collecting dialogue here; `ns` becomes its own action line.
                        if warn:
                            warn(f"scene {cur['sceneNumber']}: dialogue for {cue} stops before {ns[:44]!r} — reads "
                                 f"like action narration glued on with no blank line in the source, not more speech.")
                        break
                dlines.append(ns); i += 1
            line_text = _norm(" ".join(dlines))
            if line_text:
                cur["elements"].append({"type": "dialogue", "character": cue,
                                        "parenthetical": " ".join(paren), "line": line_text})
            continue
        # a line that LOOKS like a cue (short, ALL-CAPS, its own line) but isn't in the roster — surface it loudly
        # instead of letting it (and everything that would have been its dialogue) silently vanish into ACTION text.
        _shape = _CUE_SHAPE.match(raw.strip())
        if _shape and warn:
            nm = _na(_shape.group(1).strip())
            if nm not in roster and nm not in _warned:
                _warned.add(nm)
                warn(f"'{nm}' (scene {cur['sceneNumber']}) reads like a speaker cue but isn't in the roster — usually "
                     f"a harmless scene-structure marker (SHOT/POV/INTERCUT/a sub-location like UNDERWATER), but if "
                     f"it's actually a character, add them to the roster or their dialogue is silently lost into "
                     f"action text.")
        # otherwise: an ACTION paragraph (gather consecutive non-blank, non-cue, non-heading lines)
        block = []
        while i < len(lines):
            nl = lines[i]; ns = nl.strip()
            if not ns or _is_scene_heading(nl) or _cue_name(nl, roster):
                break
            block.append(ns); i += 1
        text = _norm(" ".join(block))
        if text:
            cur["elements"].append({"type": "action", "text": text})
    return scenes

def dialogue_lines(scenes):
    """Every spoken line, in order — the verbatim set the Director's output is checked against."""
    out = []
    for sc in scenes:
        for e in sc["elements"]:
            if e["type"] == "dialogue":
                out.append((sc["sceneNumber"], e["character"], e["line"]))
    return out

if __name__ == "__main__":
    import sys, json
    roster = ["FUZZBY", "ZENNY", "KEEN", "KEEN'S MUM", "AIDA", "HOWEY", "HOWIE", "MISTY",
              "LUNA", "SUNNY", "AMIE", "ALL"]
    txt = open(sys.argv[1]).read() if len(sys.argv) > 1 else ""
    sc = parse(txt, roster)
    print(json.dumps(sc, ensure_ascii=False, indent=2))
