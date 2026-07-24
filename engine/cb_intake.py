#!/usr/bin/env python3
"""cb_intake.py — THE DIRECTOR'S SCRIPT INTAKE (2026-07-19).

The one missing first stage of the pipeline: turns a newly uploaded, locked raw script
into the episode vision + ordered scene/beat breakdown candidate cb_creative.py's own
Gates 0-6 already consume. No second schema is invented here — the field names below and
their on-disk location were reverse-engineered directly from cb_creative.py's own
_script_package/_script_beats/_locked_dialogue/episode_vision reads, and cross-checked
against the archived, human-approved Episode 1 beat package
(archive/Episode_1_Complete_Archive_20260718/output/Ep1_Final_Episode_one_beat_package.json).

MECHANICAL, never the LLM: scene order, scene boundaries, every spoken line (speaker +
exact text, in source order) and the per-scene cast (regex-matched against the canon
character roster). The Director (crystal-bears-director skill, loaded live via
cb_departments.load_runtime_skill) decides only WHERE a scene's own beats begin and
authors the creative content — storyBeat/want/need/kidRead/adultRead/emotionalIntent,
plus the whole-episode vision, title, logline and lead bear. Its own reproduction of
dialogue text is never trusted: every cut's dialogue is rebuilt from the mechanical parse
after the call, and the whole candidate is refused — never saved — if dialogue coverage
isn't exact (every locked line present exactly once, unchanged, in source order).

Two-stage, matching every other department in this studio: prepare_intake() produces a
visible CANDIDATE only — no canonical file, nothing else changes, no image/voice/video
provider is ever called. decide_intake(verdict="approve") is the ONLY thing that writes
the canonical beat package (unlocking cb_creative.py's own scene/storyboard process) and
the matching episode-vision file. verdict="reject" archives the candidate (never deletes)
and leaves no canonical package.

    python3 cb_intake.py status Ep1
    python3 cb_intake.py run    Ep1
    python3 cb_intake.py decide Ep1 approve
    python3 cb_intake.py decide Ep1 reject "<note>"
"""
import datetime
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cb_departments

SCRIPTS = ROOT / "shows" / "crystal-bears" / "episodes" / "scripts"
OUT = ROOT / "cb-output"
CREATIVE_OUT = OUT / "creative"
EPISODES_JSON = ROOT / "cb-studio" / "data" / "episodes.json"
CHARACTERS_JSON = ROOT / "shows" / "crystal-bears" / "canon" / "characters.json"
ARCHIVE_DIR = OUT / "archive" / "story_intake_rejected"


class Refused(RuntimeError):
    """A named, deliberate refusal — never a crash, never a silent skip."""


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _md5_text(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


# ── locate the registered script (requirement 2: read from its REGISTERED path) ─────────
def _episode_record(episode):
    if not EPISODES_JSON.exists():
        raise Refused(f"no episodes registered — {EPISODES_JSON} not found")
    eps = json.loads(EPISODES_JSON.read_text())
    num = int(re.sub(r"\D", "", str(episode)) or "0")
    for e in eps:
        if int(e.get("number", -1)) == num:
            return e
    raise Refused(f"no episode registered for {episode}")


def script_path_for(episode):
    rec = _episode_record(episode)
    name = rec.get("script")
    if not name:
        raise Refused(f"{episode} has no registered script yet — upload one first")
    p = SCRIPTS / name
    if not p.exists():
        raise Refused(f"registered script not found on disk: {p}")
    return p


def candidate_path(episode):
    return CREATIVE_OUT / f"{episode}_story_intake_CANDIDATE.json"


def canonical_package_glob(episode):
    return sorted(OUT.glob(f"{episode}_*beat_package.json"))


def episode_vision_path(episode):
    return CREATIVE_OUT / f"{episode}_episode_vision.json"


# ── scene roster — the Scene Board's ONLY source of "which scenes exist" ────────────────
def scene_roster(episode="Ep1"):
    """Read-only view of the CANONICAL beat package's own scenes, for the Studio's Scene
    Board. The approved beat package is authoritative for how many scenes exist, their
    order/numbers, headings/locations and included beats — this function never reads or
    writes /api/loclib's reusable location manifest, and never invents scene data of its
    own. Returns hasPackage=False (scenes=[]) until story intake has been approved."""
    pkgs = canonical_package_glob(episode)
    if not pkgs:
        return {"episode": episode, "hasPackage": False, "package": None, "scenes": []}
    pkg_path = pkgs[-1]
    pkg = json.loads(pkg_path.read_text())
    by_scene = {}
    for b in pkg.get("beats", []):
        sn = b.get("sceneNumber")
        if sn is None:
            continue
        by_scene.setdefault(sn, []).append(b)
    scenes = []
    for sn in sorted(by_scene):
        beats = sorted(by_scene[sn], key=lambda b: str(b.get("beatCode", "")))
        first = beats[0]
        scenes.append({
            "sceneNumber": sn,
            "location": first.get("location", ""),
            "time": first.get("time", ""),
            "beatCount": len(beats),
            "beatCodes": [b.get("beatCode") for b in beats],
        })
    return {"episode": episode, "hasPackage": True, "package": pkg_path.name,
            "scenes": scenes}


# ── mechanical script parser — scene order, dialogue and cast are LOCKED evidence ───────
_SCENE_RE = re.compile(r"^\s*(INT\.?\s*/\s*EXT\.?|INT\.?|EXT\.?)\s+(.+?)\s+(\d+)\s*$")
_TRANSITION_RE = re.compile(
    r"^\s*(FADE IN|FADE OUT|CUT TO|DISSOLVE TO|SMASH CUT TO|MATCH CUT TO)\.?:?\s*$",
    re.IGNORECASE)
_PAREN_ONLY_RE = re.compile(r"^\s*\(.*\)\s*$")
_CONTD_RE = re.compile(r"\s*\(CONT'D\)\s*$", re.IGNORECASE)
_APOS_RE = re.compile("[‘’ʼ′]")   # curly/prime apostrophe variants


def _norm_apos(s):
    """Screenplay text commonly uses a curly apostrophe (’) where canon data (e.g.
    characters.json's "Keen's Mum" key) uses a straight one — normalize BOTH to the same
    form before any name match, or every 'KEEN’S MUM' cue silently fails to match and
    falls through into action text (found live parsing the real script, 2026-07-19)."""
    return _APOS_RE.sub("'", s)


def _load_roster():
    chars = json.loads(CHARACTERS_JSON.read_text())
    return [k for k, v in chars.items()
            if isinstance(v, dict) and not k.startswith("_") and k != "sizeClasses"]


def _cue_regex(names):
    alts = sorted({_norm_apos(n).upper() for n in names} | {"ALL"}, key=len, reverse=True)
    return re.compile(r"^\s*(?:\d+\s*)?(" + "|".join(re.escape(a) for a in alts) +
                       r")\s*(?:\(CONT'D\))?\s*$", re.IGNORECASE)


def parse_script(text, roster=None, log=print):
    """Mechanical, deterministic, never touches meaning. Returns
    {scenes: [{sceneNumber, headerRaw, location, time}],
     events: [{i, scene, type: "action"|"dialogue", speaker, text}], dialogueCount,
     frontMatter: [str, ...]}.

    CORRECTION (2026-07-19, the Scene-0 finding): text appearing before the first real
    scene heading is the screenplay's own document metadata (title page, "Created by"/
    "Written by" credits, production company, draft-date stamp) — never a story event,
    and never Scene 0. `cur_scene` used to default to the int 0 before any heading was
    seen, so this front matter was silently tagged scene=0 and later authored into a
    real, spurious beat (S00-B01-TITLE-INVITATION, traced and removed from the live Ep1
    package the same day). `cur_scene` now starts as None; nothing is appended to
    `events` while it's still None — front matter is collected separately (frontMatter,
    informational only) and logged, never routed into scene/beat data."""
    roster = roster or _load_roster()
    cue_re = _cue_regex(roster)
    name_by_upper = {_norm_apos(n).upper(): n for n in roster}
    name_by_upper["ALL"] = "ALL"
    # A KNOWN, NARROW screenplay-formatting quirk in this exact script (previously found
    # and fixed the identical way in the now-retired cb_script.py, see CLAUDE.md's own
    # audit record): a trailing ACTION sentence sometimes directly follows a dialogue line
    # with NO blank line separating them (e.g. "Hi… I'm Keen.\nFuzzby zooms right into
    # Keen's face."), which would otherwise be swallowed into the preceding character's own
    # dialogue text. Detected mechanically — a sentence starting with another roster
    # character's own name, immediately followed by an ordinary (lowercase) word — never a
    # semantic judgment; the heuristic name-checks the ROSTER, not any specific sentence, so
    # it generalizes to any script. Every firing is logged, never silent.
    action_bleed_re = re.compile(
        r"^(" + "|".join(re.escape(_norm_apos(n)) for n in roster) + r")\s+[a-z]")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    scenes, events, front_matter = [], [], []
    cur_scene = None   # None until the first real scene heading is matched
    action_buf = []

    def flush_action():
        nonlocal action_buf
        joined = " ".join(x.strip() for x in action_buf if x.strip())
        action_buf = []
        if not joined:
            return
        if cur_scene is None:
            front_matter.append(joined)
            return
        events.append({"i": len(events), "scene": cur_scene, "type": "action",
                       "speaker": None, "text": joined})

    n = len(lines)
    li = 0
    while li < n:
        raw = lines[li]
        stripped = raw.strip()
        if not stripped:
            flush_action()
            li += 1
            continue
        m = _SCENE_RE.match(raw.rstrip())
        if m:
            flush_action()
            cur_scene = int(m.group(3))
            loc_time = re.sub(r"\s+", " ", m.group(2)).strip()
            parts = re.split(r"\s*[–—-]\s*", loc_time)
            location = parts[0].strip() if parts else loc_time
            time_of_day = parts[-1].strip() if len(parts) > 1 else ""
            scenes.append({"sceneNumber": cur_scene, "headerRaw": stripped,
                           "location": location, "time": time_of_day})
            li += 1
            continue
        if _TRANSITION_RE.match(stripped):
            flush_action()
            li += 1
            continue
        cm = cue_re.match(_norm_apos(raw).rstrip())
        if cm:
            flush_action()
            speaker_raw = _CONTD_RE.sub("", cm.group(1)).strip().upper()
            speaker = name_by_upper.get(speaker_raw, speaker_raw)
            li += 1
            if li < n and _PAREN_ONLY_RE.match(lines[li].strip()) and lines[li].strip():
                li += 1   # a delivery-only parenthetical — never dialogue text
            text_lines = []
            while (li < n and lines[li].strip()
                   and not _SCENE_RE.match(lines[li].rstrip())
                   and not cue_re.match(_norm_apos(lines[li]).rstrip())):
                if _PAREN_ONLY_RE.match(lines[li].strip()):
                    li += 1
                    continue
                cand = lines[li].strip()
                bleed = action_bleed_re.match(_norm_apos(cand)) if text_lines else None
                if bleed:
                    log(f"ACTION-BLEED GUARD fired — stopped {speaker}'s dialogue before "
                        f"a directly-following, no-blank-line action sentence naming "
                        f"{bleed.group(1)}: {cand!r}")
                    break
                text_lines.append(cand)
                li += 1
            dlg = " ".join(text_lines).strip()
            if not dlg:
                continue
            if cur_scene is None:
                # a cue-shaped line before any real scene heading — front matter, not a
                # character speaking. Not expected in a real script, kept for robustness.
                front_matter.append(f"{speaker}: {dlg}")
                continue
            events.append({"i": len(events), "scene": cur_scene, "type": "dialogue",
                           "speaker": speaker, "text": dlg})
            continue
        action_buf.append(raw)
        li += 1
    flush_action()

    dialogue_count = sum(1 for e in events if e["type"] == "dialogue")
    if not scenes:
        raise Refused("mechanical script parse found no scene headers (expects "
                      "'INT./EXT. LOCATION - TIME  <number>') — nothing generated")
    if dialogue_count == 0:
        raise Refused("mechanical script parse found no dialogue cues against the canon "
                      "character roster — check the script's format before proceeding")
    if front_matter:
        log(f"FRONT MATTER — {len(front_matter)} paragraph(s) before the first scene "
            f"heading discarded as document metadata, never Scene 0: "
            + " | ".join(front_matter))
    return {"scenes": scenes, "events": events, "dialogueCount": dialogue_count,
            "frontMatter": front_matter}


def cast_per_scene(parsed, roster=None):
    roster = roster or _load_roster()
    upper_to_name = {_norm_apos(n).upper(): n for n in roster}
    by_scene = {}
    for sc in parsed["scenes"]:
        by_scene[sc["sceneNumber"]] = set()
    for e in parsed["events"]:
        blob = _norm_apos((e.get("text") or "")).upper()
        found = {upper_to_name[u] for u in upper_to_name
                 if re.search(r"\b" + re.escape(u) + r"\b", blob)}
        if e.get("type") == "dialogue" and e.get("speaker") in roster:
            found.add(e["speaker"])
        by_scene.setdefault(e["scene"], set()).update(found)
    return {str(k): sorted(v) for k, v in by_scene.items()}


# ── beat-split validation/repair — guarantees a complete, ordered, gap-free partition ───
def _repair_beat_splits(beats, parsed):
    """Beats are grouped by scene, sorted by their own firstEventIndex, deduplicated, and
    each scene's first beat is snapped to that scene's true first event index. This makes
    a complete, non-overlapping, order-preserving partition GUARANTEED BY CONSTRUCTION —
    the LLM only ever chooses split POINTS, never index ranges, so there is no invalid
    shape to reject; a poorly-chosen split point degrades to a slightly odd beat boundary,
    never a missing or duplicated event."""
    scene_first_idx = {}
    for e in parsed["events"]:
        scene_first_idx.setdefault(e["scene"], e["i"])
    scene_last_idx = {}
    for e in parsed["events"]:
        scene_last_idx[e["scene"]] = e["i"]

    by_scene = {}
    for b in beats:
        by_scene.setdefault(b.sceneNumber, []).append(b)

    out = []
    for scene_num in sorted(scene_first_idx):
        blist = sorted(by_scene.get(scene_num, []), key=lambda b: b.firstEventIndex)
        if not blist:
            continue
        seen_idx = set()
        clean = []
        for b in blist:
            if b.firstEventIndex in seen_idx:
                continue
            seen_idx.add(b.firstEventIndex)
            clean.append(b)
        clean[0].firstEventIndex = scene_first_idx[scene_num]
        for i, b in enumerate(clean):
            lo = b.firstEventIndex
            hi = (clean[i + 1].firstEventIndex - 1) if i + 1 < len(clean) \
                else scene_last_idx[scene_num]
            out.append({"beat": b, "lo": lo, "hi": hi, "sceneNumber": scene_num})
    return out


def _build_cuts(events, lo, hi):
    cuts = []
    n = 0
    for e in events:
        if lo <= e["i"] <= hi:
            n += 1
            if e["type"] == "dialogue":
                cuts.append({"n": n, "dialogue": f"{e['speaker']}: {e['text']}",
                            "action": None})
            else:
                cuts.append({"n": n, "dialogue": None, "action": e["text"]})
    return cuts


def dialogue_coverage_report(events, beats):
    """PROOF artifact: every mechanically-parsed dialogue line must appear in the
    candidate's own cuts exactly once, unchanged, in source order. Never trusts the LLM's
    text — compares the CANDIDATE'S OWN cuts (already mechanically rebuilt) back against
    the original parse, so this also catches a bug in the rebuild step itself."""
    want = [(e["i"], e["speaker"], e["text"]) for e in events if e["type"] == "dialogue"]
    got = []
    for b in beats:
        for c in b["cuts"]:
            if c.get("dialogue"):
                spk, _, txt = c["dialogue"].partition(":")
                got.append((spk.strip(), txt.strip()))
    want_pairs = [(spk, txt) for _, spk, txt in want]
    ok = (got == want_pairs)
    return {"ok": ok, "totalDialogueLines": len(want_pairs),
            "coveredExactly": sum(1 for a, b in zip(got, want_pairs) if a == b),
            "candidateLines": len(got),
            "issues": [] if ok else [
                f"mismatch at position {i}: source={w!r} candidate={g!r}"
                for i, (w, g) in enumerate(zip(want_pairs, got)) if w != g
            ][:20] + ([f"length differs: source has {len(want_pairs)}, "
                       f"candidate has {len(got)}"] if len(want_pairs) != len(got) else [])}


# ── prepare / status / decide — the visible candidate lifecycle ────────────────────────
def prepare_intake(episode="Ep1", log=print):
    if candidate_path(episode).exists():
        raise Refused(f"REFUSED — {episode} already has a story-intake candidate "
                      "awaiting a decision")
    if canonical_package_glob(episode):
        raise Refused(f"REFUSED — {episode} already has a canonical beat package; "
                      "story intake is a one-time first stage")
    spath = script_path_for(episode)
    text = spath.read_text(encoding="utf-8")
    roster = _load_roster()
    parsed = parse_script(text, roster, log=log)
    cast_by_scene = cast_per_scene(parsed, roster)

    log(f"MECHANICAL PARSE — {len(parsed['scenes'])} scene(s), "
        f"{parsed['dialogueCount']} locked dialogue line(s), "
        f"{len(parsed['events'])} event(s) total")

    direction = cb_departments.prepare_story(parsed["events"], cast_by_scene, log=log)

    ranged = _repair_beat_splits(direction.beats, parsed)
    scene_by_num = {s["sceneNumber"]: s for s in parsed["scenes"]}
    beats_out = []
    for row in ranged:
        b, lo, hi, scene_num = row["beat"], row["lo"], row["hi"], row["sceneNumber"]
        sc = scene_by_num.get(scene_num, {})
        cuts = _build_cuts(parsed["events"], lo, hi)
        beats_out.append({
            "sceneNumber": scene_num,
            "beatCode": b.beatCode,
            "location": sc.get("location", ""),
            "time": sc.get("time", ""),
            "characters": cast_by_scene.get(str(scene_num), []),
            "storyBeat": b.storyBeat, "want": b.want, "need": b.need,
            "kidRead": b.kidRead, "adultRead": b.adultRead,
            "emotionalIntent": b.emotionalIntent,
            "cuts": cuts,
        })

    coverage = dialogue_coverage_report(parsed["events"], beats_out)
    if not coverage["ok"]:
        raise Refused("REFUSED — dialogue coverage is not exact; no candidate saved. "
                      + "; ".join(coverage["issues"][:5]))

    candidate = {
        "episode": episode,
        "builtAt": _now(),
        "scriptPath": str(spath.relative_to(ROOT)),
        "scriptMd5": _md5_text(text),
        "director": {"skill": "crystal-bears-director",
                    "loaded": bool(cb_departments.load_runtime_skill("director"))},
        "title": direction.title, "logline": direction.logline,
        "leadBear": direction.leadBear,
        "episodeVision": direction.episodeVision.model_dump(),
        "scenes": parsed["scenes"],
        "beats": beats_out,
        "dialogueCoverage": coverage,
        "approvalState": "awaiting-human-approval",
    }
    CREATIVE_OUT.mkdir(parents=True, exist_ok=True)
    json.dump(candidate, open(candidate_path(episode), "w"), indent=1, ensure_ascii=False)
    log(f"STORY INTAKE CANDIDATE — {len(beats_out)} beat(s) across "
        f"{len(parsed['scenes'])} scene(s); dialogue coverage exact "
        f"({coverage['totalDialogueLines']}/{coverage['totalDialogueLines']}) -> "
        f"{candidate_path(episode).name}")
    return candidate


def intake_status(episode="Ep1"):
    out = {"episode": episode, "hasScript": False, "scriptName": None,
          "directorSkillLoaded": False, "hasCandidate": False, "candidate": None,
          "hasCanonicalPackage": bool(canonical_package_glob(episode)),
          "canonicalPackage": (canonical_package_glob(episode) or [None])[-1]
                              and canonical_package_glob(episode)[-1].name}
    try:
        out["directorSkillLoaded"] = bool(cb_departments.load_runtime_skill("director"))
    except Exception:
        out["directorSkillLoaded"] = False
    try:
        spath = script_path_for(episode)
        out["hasScript"] = True
        out["scriptName"] = spath.name
    except Refused:
        pass
    cpath = candidate_path(episode)
    if cpath.exists():
        out["hasCandidate"] = True
        out["candidate"] = json.loads(cpath.read_text())
    return out


def decide_intake(episode="Ep1", verdict="approve", note="", reviewed_by="Julian",
                  log=print):
    if verdict not in ("approve", "reject"):
        raise Refused("REFUSED — verdict must be approve|reject")
    cpath = candidate_path(episode)
    if not cpath.exists():
        raise Refused(f"REFUSED — {episode} has no story-intake candidate awaiting a "
                      "decision")
    candidate = json.loads(cpath.read_text())

    if verdict == "reject":
        note = str(note or "").strip()
        if not note:
            raise Refused("REFUSED — rejection needs a plain-language note")
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")
        dest = ARCHIVE_DIR / f"{episode}_{stamp}.json"
        candidate["rejection"] = {"note": note, "reviewedBy": reviewed_by, "at": _now()}
        json.dump(candidate, open(dest, "w"), indent=1, ensure_ascii=False)
        cpath.unlink()
        log(f"STORY INTAKE REJECTED — {episode} by {reviewed_by}: {note} "
            f"(candidate archived to {dest.name}; no canonical package written)")
        return {"outcome": "rejected", "archivedTo": str(dest.relative_to(ROOT)),
                "note": note}

    # verdict == "approve" — THE ONLY WRITE OF THE CANONICAL ARTIFACTS
    if canonical_package_glob(episode):
        raise Refused(f"REFUSED — {episode} already has a canonical beat package; "
                      "refusing to overwrite it")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", candidate["title"]).strip("_") or "episode"
    pkg = {
        "title": candidate["title"], "episode": int(re.sub(r"\D", "", episode) or "0"),
        "logline": candidate["logline"], "leadBear": candidate["leadBear"],
        "format": "11-min episode", "unit": "beat",
        "beats": candidate["beats"],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    pkg_path = OUT / f"{episode}_{slug}_beat_package.json"
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)

    vision_pkg = {"episodeId": episode, "title": candidate["title"],
                 "sourceScriptVersion": _md5_text(json.dumps(pkg, sort_keys=True)),
                 "canonVersion": "1.0", **candidate["episodeVision"],
                 "showrunnerJudgement": "", "approvalState": "approved",
                 "provenance": {"role": "director-intake", "at": _now(),
                                "reviewedBy": reviewed_by}}
    CREATIVE_OUT.mkdir(parents=True, exist_ok=True)
    json.dump(vision_pkg, open(episode_vision_path(episode), "w"), indent=1,
              ensure_ascii=False)

    candidate["approvalState"] = "approved"
    candidate["approval"] = {"reviewedBy": reviewed_by, "at": _now(),
                             "canonicalPackage": pkg_path.name}
    json.dump(candidate, open(cpath, "w"), indent=1, ensure_ascii=False)

    log(f"STORY INTAKE APPROVED — {episode} by {reviewed_by}: {pkg_path.name} + "
        f"{episode_vision_path(episode).name} written; cb_creative.py's scene/storyboard "
        f"process is now unlocked")
    return {"outcome": "approved", "canonicalPackage": str(pkg_path.relative_to(ROOT)),
            "episodeVision": str(episode_vision_path(episode).relative_to(ROOT))}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    ep = sys.argv[2] if len(sys.argv) > 2 else "Ep1"
    if cmd == "status":
        print(json.dumps(intake_status(ep), indent=1, ensure_ascii=False))
    elif cmd == "scenes":
        print(json.dumps(scene_roster(ep), indent=1, ensure_ascii=False))
    elif cmd == "run":
        prepare_intake(ep)
    elif cmd == "decide":
        verdict_arg = sys.argv[3] if len(sys.argv) > 3 else ""
        note_arg = sys.argv[4] if len(sys.argv) > 4 else ""
        decide_intake(ep, verdict_arg, note=note_arg)
    else:
        print(__doc__)
        sys.exit(1)
