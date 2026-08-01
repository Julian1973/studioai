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
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import cb_departments
import cb_canon
import cb_lineage
import cb_scripts

SCRIPTS = ROOT / "shows" / "crystal-bears" / "episodes" / "scripts"
STUDIO_SCRIPTS = ROOT / "cb-studio" / "data" / "scripts"
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT)
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


def script_record_for(episode):
    rec = _episode_record(episode)
    try:
        current = SCRIPT_STORE.current(episode, required=False)
        if current is None:
            name = rec.get("script")
            if not name:
                raise Refused(f"{episode} has no registered script yet — upload one first")
            legacy = next((p for p in (SCRIPTS / name, STUDIO_SCRIPTS / name) if p.exists()), None)
            if legacy is None:
                raise Refused(f"registered script not found on disk: {name}")
            current = SCRIPT_STORE.migrate_legacy(
                episode, legacy, rec.get("title") or episode,
                migrated_by="cb_intake legacy migration")
        registered = rec.get("scriptVersionId")
        if registered and registered != current["scriptVersionId"]:
            raise Refused(
                f"episode registry points to {registered}, but the immutable script pointer is "
                f"{current['scriptVersionId']} — reindex before intake")
        return current
    except cb_scripts.ScriptStoreError as exc:
        raise Refused(str(exc)) from exc


def script_path_for(episode):
    return ROOT / script_record_for(episode)["contentPath"]


def _script_ref(current):
    return {key: current[key] for key in
            ("episodeId", "scriptVersionId", "sha256", "byteLength", "contentPath")}


def _package_script_version(pkg):
    return ((pkg.get("sourceScript") or {}).get("scriptVersionId") or
            pkg.get("scriptVersionId"))


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
        return {"episode": episode, "hasPackage": False, "package": None, "scenes": [],
                "reason": "story-intake-not-approved"}
    status = intake_status(episode)
    if not status.get("canonicalCurrent"):
        return {"episode": episode, "hasPackage": False, "package": pkgs[-1].name,
                "scenes": [], "reason": "canonical-beat-package-stale",
                "canonicalCurrent": False}
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
            "scenes": scenes, "reason": None, "canonicalCurrent": True}


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


def _character_aliases():
    try:
        return cb_canon.load_policy(ROOT).get("characterAliases") or {}
    except cb_canon.CanonLockError:
        return {}


def _cue_regex(names, aliases=None):
    aliases = aliases or {}
    alts = sorted({_norm_apos(n).upper() for n in names} |
                  {_norm_apos(n).upper() for n in aliases} | {"ALL"},
                  key=len, reverse=True)
    return re.compile(r"^\s*(?:\d+\s*)?(" + "|".join(re.escape(a) for a in alts) +
                       r")\s*(?:\(CONT'D\))?\s*$", re.IGNORECASE)


_NUMBERED_CUE_RE = re.compile(
    r"^\s*\d+\s+([A-Z][A-Z'’]*(?:\s+[A-Z][A-Z'’]*){0,3})"
    r"(?:\s+\(CONT'D\))?\s*$")


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
    aliases = _character_aliases()
    cue_re = _cue_regex(roster, aliases)
    name_by_upper = {_norm_apos(n).upper(): n for n in roster}
    name_by_upper.update({_norm_apos(alias).upper(): canonical
                          for alias, canonical in aliases.items()})
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
        unknown_cue = _NUMBERED_CUE_RE.match(_norm_apos(raw).rstrip())
        if unknown_cue:
            raise Refused(
                "mechanical script parse found an unknown numbered character cue: "
                f"{unknown_cue.group(1)}. Add an explicit canon alias or correct the script; "
                "refusing to silently turn dialogue into action text")
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
    upper_to_name.update({_norm_apos(alias).upper(): canonical
                          for alias, canonical in _character_aliases().items()})
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


def _annotate_source_events(events, script_version_id):
    """Attach identities derived from immutable script bytes and exact event occurrence."""
    for event in events:
        record = cb_lineage.source_event_record(script_version_id, event)
        event["sourceEventId"] = record["sourceEventId"]
        if event["type"] == "dialogue":
            event["dialogueOccurrenceId"] = record["dialogueOccurrenceId"]
    return events


def _build_cuts(events, lo, hi):
    cuts = []
    n = 0
    for e in events:
        if lo <= e["i"] <= hi:
            n += 1
            if e["type"] == "dialogue":
                cuts.append({
                    "n": n,
                    "sourceEventId": e["sourceEventId"],
                    "sourceEventIndex": e["i"],
                    "sourceSceneNumber": e["scene"],
                    "sourceType": "dialogue",
                    "dialogueOccurrenceId": e["dialogueOccurrenceId"],
                    "speaker": e["speaker"],
                    "exactText": e["text"],
                    "dialogue": f"{e['speaker']}: {e['text']}",
                    "action": None,
                })
            else:
                cuts.append({
                    "n": n,
                    "sourceEventId": e["sourceEventId"],
                    "sourceEventIndex": e["i"],
                    "sourceSceneNumber": e["scene"],
                    "sourceType": "action",
                    "dialogueOccurrenceId": None,
                    "speaker": None,
                    "exactText": None,
                    "dialogue": None,
                    "action": e["text"],
                })
    return cuts


def dialogue_coverage_report(events, beats):
    """PROOF artifact: every mechanically-parsed dialogue line must appear in the
    candidate's own cuts exactly once, unchanged, in source order. Never trusts the LLM's
    text — compares the CANDIDATE'S OWN cuts (already mechanically rebuilt) back against
    the original parse, so this also catches a bug in the rebuild step itself."""
    want = [(e["dialogueOccurrenceId"], e["sourceEventId"], e["speaker"], e["text"])
            for e in events if e["type"] == "dialogue"]
    got = []
    for b in beats:
        for c in b["cuts"]:
            if c.get("dialogue"):
                got.append((c.get("dialogueOccurrenceId"), c.get("sourceEventId"),
                            c.get("speaker"), c.get("exactText")))
    ok = (got == want)
    return {"ok": ok, "totalDialogueLines": len(want),
            "coveredExactly": sum(1 for a, b in zip(got, want) if a == b),
            "candidateLines": len(got),
            "issues": [] if ok else [
                f"mismatch at position {i}: source={w!r} candidate={g!r}"
                for i, (w, g) in enumerate(zip(want, got)) if w != g
            ][:20] + ([f"length differs: source has {len(want)}, "
                       f"candidate has {len(got)}"] if len(want) != len(got) else [])}


def source_event_coverage_report(events, beats):
    """Prove every action and dialogue occurrence is partitioned once, unchanged, in order."""
    want = [(
        event["sourceEventId"], event["i"], event["scene"], event["type"],
        event.get("dialogueOccurrenceId"), event.get("speaker"), event["text"])
        for event in events]
    got = []
    for beat in beats:
        for cut in beat.get("cuts") or []:
            source_type = cut.get("sourceType")
            got.append((
                cut.get("sourceEventId"), cut.get("sourceEventIndex"),
                cut.get("sourceSceneNumber"), source_type,
                cut.get("dialogueOccurrenceId"), cut.get("speaker"),
                cut.get("exactText") if source_type == "dialogue" else cut.get("action")))
    ok = got == want
    return {
        "ok": ok,
        "totalSourceEvents": len(want),
        "coveredExactly": sum(1 for actual, expected in zip(got, want)
                              if actual == expected),
        "candidateEvents": len(got),
        "issues": [] if ok else [
            f"mismatch at position {i}: source={expected!r} candidate={actual!r}"
            for i, (expected, actual) in enumerate(zip(want, got))
            if expected != actual
        ][:20] + ([f"length differs: source has {len(want)}, candidate has {len(got)}"]
                  if len(want) != len(got) else []),
    }


# ── prepare / status / decide — the visible candidate lifecycle ────────────────────────
def prepare_intake(episode="Ep1", log=print):
    current = script_record_for(episode)
    spath = ROOT / current["contentPath"]
    text = spath.read_text(encoding="utf-8")
    roster = _load_roster()
    parsed = parse_script(text, roster, log=log)
    _annotate_source_events(parsed["events"], current["scriptVersionId"])
    cast_by_scene = cast_per_scene(parsed, roster)
    episode_cast = sorted({name for names in cast_by_scene.values() for name in names})
    try:
        canon_lock = cb_canon.require_locked(episode, episode_cast, root=ROOT)
        canon_context = cb_canon.story_context(episode_cast, episode, root=ROOT)
    except cb_canon.CanonLockError as exc:
        raise Refused(str(exc)) from exc
    story_inputs = {
        "scriptVersionId": current["scriptVersionId"],
        "canonProfileDigest": canon_lock["profileDigests"]["story"],
    }

    pending = candidate_path(episode)
    if pending.exists():
        prior = json.loads(pending.read_text())
        if cb_lineage.signature_matches(
                prior.get("inputSignature"), "story-intake", story_inputs):
            raise Refused(f"REFUSED — {episode} already has a story-intake candidate "
                          "for this exact script and canon lock awaiting a decision")
        archive = OUT / "archive" / "story_intake_superseded"
        archive.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")
        old_version = str(prior.get("scriptVersionId") or "legacy").replace(":", "_")
        shutil.move(str(pending), archive / f"{episode}_{old_version}_{stamp}.json")
    for existing_path in canonical_package_glob(episode):
        existing = json.loads(existing_path.read_text())
        if cb_lineage.signature_matches(
                existing.get("inputSignature"), "beat-package-input", story_inputs):
            raise Refused(f"REFUSED — {episode} already has a canonical beat package for "
                          "this exact script and canon lock; change a versioned input to rebuild")

    log(f"MECHANICAL PARSE — {len(parsed['scenes'])} scene(s), "
        f"{parsed['dialogueCount']} locked dialogue line(s), "
        f"{len(parsed['events'])} event(s) total")

    direction = cb_departments.prepare_story(
        parsed["events"], cast_by_scene, canon_context, log=log)

    ranged = _repair_beat_splits(direction.beats, parsed)
    scene_by_num = {s["sceneNumber"]: s for s in parsed["scenes"]}
    beats_out = []
    for row in ranged:
        b, lo, hi, scene_num = row["beat"], row["lo"], row["hi"], row["sceneNumber"]
        sc = scene_by_num.get(scene_num, {})
        cuts = _build_cuts(parsed["events"], lo, hi)
        source_events = [event for event in parsed["events"] if lo <= event["i"] <= hi]
        source_signature = cb_lineage.source_beat_event_signature(
            current["scriptVersionId"], source_events)
        source_records = source_signature["inputs"]["orderedEvents"]
        beats_out.append({
            "sceneNumber": scene_num,
            "beatCode": b.beatCode,
            "sourceBeatId": cb_lineage.source_beat_id(source_signature),
            "sourceEventRange": {
                "firstEventIndex": source_records[0]["sourceEventIndex"],
                "lastEventIndex": source_records[-1]["sourceEventIndex"],
                "firstEventId": source_records[0]["sourceEventId"],
                "lastEventId": source_records[-1]["sourceEventId"],
                "eventCount": len(source_records),
            },
            "sourceEventIds": [record["sourceEventId"] for record in source_records],
            "dialogueOccurrenceIds": [
                record["dialogueOccurrenceId"] for record in source_records
                if record["sourceType"] == "dialogue"],
            "sourceEventSignature": source_signature,
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
    source_coverage = source_event_coverage_report(parsed["events"], beats_out)
    if not source_coverage["ok"]:
        raise Refused("REFUSED — source-event partition is not exact; no candidate saved. "
                      + "; ".join(source_coverage["issues"][:5]))
    source_contract = cb_lineage.beat_package_source_contract(
        current["scriptVersionId"], beats_out)

    candidate = {
        "episode": episode,
        "builtAt": _now(),
        "scriptPath": current["contentPath"],
        "scriptVersionId": current["scriptVersionId"],
        "scriptSha256": current["sha256"],
        "sourceScript": _script_ref(current),
        "scriptMd5": _md5_text(text),
        "inputSignature": cb_lineage.dependency_signature("story-intake", story_inputs),
        "canonLock": {
            "manifestDigest": canon_lock["manifestDigest"],
            "profile": "story",
            "profileDigest": canon_lock["profileDigests"]["story"],
            "sourceHashes": canon_context["sourceHashes"],
        },
        "director": {"skill": "crystal-bears-director",
                    "loaded": bool(cb_departments.load_runtime_skill("director"))},
        "title": direction.title, "logline": direction.logline,
        "leadBear": direction.leadBear,
        "episodeVision": direction.episodeVision.model_dump(),
        "scenes": parsed["scenes"],
        "beats": beats_out,
        "sourceContract": source_contract,
        "sourceEventCoverage": source_coverage,
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
                              and canonical_package_glob(episode)[-1].name,
          "scriptVersionId": None, "candidateCurrent": None, "canonicalCurrent": None,
          "canonicalSourceContractCurrent": None,
          "canonicalContentSignatureCurrent": None,
          "canonicalBeatPackageDigest": None,
          "canonicalSourceContractIssues": [],
          "canonLockCurrent": False, "canonEpisodeReady": False,
          "canonLockDigest": None, "canonProfileDigest": None,
          "canonProfileDigests": {},
          "canonBlockers": [], "canonWarnings": []}
    try:
        out["directorSkillLoaded"] = bool(cb_departments.load_runtime_skill("director"))
    except Exception:
        out["directorSkillLoaded"] = False
    try:
        current = script_record_for(episode)
        spath = ROOT / current["contentPath"]
        out["hasScript"] = True
        out["scriptName"] = current.get("displayFile") or spath.name
        out["scriptVersionId"] = current["scriptVersionId"]
    except Refused:
        pass
    try:
        canon = cb_canon.status(episode, root=ROOT)
        out.update({
            "canonLockCurrent": bool(canon.get("current")),
            "canonEpisodeReady": bool(canon.get("episodeReady")),
            "canonLockDigest": canon.get("manifestDigest"),
            "canonProfileDigest": (canon.get("profileDigests") or {}).get("story"),
            "canonProfileDigests": canon.get("profileDigests") or {},
            "canonBlockers": list(canon.get("blockers") or []) +
                             list(canon.get("episodeBlockers") or []),
            "canonWarnings": list(canon.get("warnings") or []),
        })
    except Exception as exc:
        out["canonBlockers"] = [{"code": "CANON_STATUS_ERROR", "message": str(exc)}]
    story_inputs = ({
        "scriptVersionId": out["scriptVersionId"],
        "canonProfileDigest": out["canonProfileDigest"],
    } if out.get("scriptVersionId") and out.get("canonProfileDigest") else None)
    cpath = candidate_path(episode)
    if cpath.exists():
        out["hasCandidate"] = True
        out["candidate"] = json.loads(cpath.read_text())
        out["candidateCurrent"] = bool(
            story_inputs and out["canonLockCurrent"] and out["canonEpisodeReady"] and
            cb_lineage.signature_matches(
                out["candidate"].get("inputSignature"), "story-intake", story_inputs))
    pkgs = canonical_package_glob(episode)
    if pkgs:
        pkg = json.loads(pkgs[-1].read_text())
        expected_content = cb_lineage.beat_package_signature(pkg)
        source_report = cb_lineage.validate_beat_package_source_contract(pkg)
        out["canonicalSourceContractCurrent"] = source_report["ok"]
        out["canonicalSourceContractIssues"] = source_report["issues"]
        out["canonicalContentSignatureCurrent"] = (
            pkg.get("contentSignature") == expected_content)
        out["canonicalBeatPackageDigest"] = expected_content["digest"]
        out["canonicalCurrent"] = bool(
            story_inputs and out["canonLockCurrent"] and out["canonEpisodeReady"] and
            cb_lineage.signature_matches(
                pkg.get("inputSignature"), "beat-package-input", story_inputs) and
            source_report["ok"] and pkg.get("contentSignature") == expected_content)
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
    current = script_record_for(episode)
    # Reparse the immutable script at the approval boundary. A hand-edited candidate cannot
    # change, drop, duplicate or reorder even a non-dialogue event and still be approved.
    current_text = (ROOT / current["contentPath"]).read_text(encoding="utf-8")
    roster = _load_roster()
    parsed = parse_script(current_text, roster, log=lambda *a, **k: None)
    _annotate_source_events(parsed["events"], current["scriptVersionId"])
    cast_by_scene = cast_per_scene(parsed, roster)
    episode_cast = sorted({name for names in cast_by_scene.values() for name in names})
    try:
        canon_lock = cb_canon.require_locked(episode, episode_cast, root=ROOT)
    except cb_canon.CanonLockError as exc:
        raise Refused(str(exc)) from exc
    story_inputs = {
        "scriptVersionId": current["scriptVersionId"],
        "canonProfileDigest": canon_lock["profileDigests"]["story"],
    }
    if not cb_lineage.signature_matches(
            candidate.get("inputSignature"), "story-intake", story_inputs):
        raise Refused(
            "REFUSED — this intake candidate was not generated from the active immutable "
            "script and exact current story-canon lock; run Story & Direction again")
    event_coverage = source_event_coverage_report(parsed["events"], candidate.get("beats") or [])
    dialogue_coverage = dialogue_coverage_report(parsed["events"], candidate.get("beats") or [])
    expected_contract = cb_lineage.beat_package_source_contract(
        current["scriptVersionId"], candidate.get("beats") or [])
    if not event_coverage["ok"] or not dialogue_coverage["ok"]:
        issues = event_coverage["issues"] or dialogue_coverage["issues"]
        raise Refused("REFUSED — intake candidate no longer preserves the immutable script: "
                      + "; ".join(issues[:5]))
    if candidate.get("sourceContract") != expected_contract:
        raise Refused("REFUSED — intake candidate's signed source-event contract is stale or changed")

    existing_paths = canonical_package_glob(episode)
    for existing_path in existing_paths:
        existing = json.loads(existing_path.read_text())
        if cb_lineage.signature_matches(
                existing.get("inputSignature"), "beat-package-input", story_inputs):
            raise Refused(f"REFUSED — {episode} already has a canonical beat package for "
                          "this exact script and canon lock; refusing to overwrite it")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", candidate["title"]).strip("_") or "episode"
    pkg = {
        "title": candidate["title"], "episode": int(re.sub(r"\D", "", episode) or "0"),
        "logline": candidate["logline"], "leadBear": candidate["leadBear"],
        "format": "11-min episode", "unit": "beat",
        "sourceScript": _script_ref(current),
        "sourceContract": expected_contract,
        "inputSignature": cb_lineage.dependency_signature("beat-package-input", story_inputs),
        "canonLock": {
            "manifestDigest": canon_lock["manifestDigest"],
            "profile": "story",
            "profileDigest": canon_lock["profileDigests"]["story"],
            "sourceHashes": cb_canon.source_hashes("story", ROOT),
        },
        "beats": candidate["beats"],
    }
    pkg["contentSignature"] = cb_lineage.beat_package_signature(pkg)
    OUT.mkdir(parents=True, exist_ok=True)
    pkg_path = OUT / f"{episode}_{slug}_beat_package.json"
    if existing_paths:
        archive = OUT / "archive" / "script_versions"
        archive.mkdir(parents=True, exist_ok=True)
        stamp = _now().replace(":", "").replace("-", "")
        for old_path in existing_paths:
            old = json.loads(old_path.read_text())
            old_version = str(_package_script_version(old) or "legacy").replace(":", "_")
            shutil.move(str(old_path), archive / f"{old_path.stem}_{old_version}_{stamp}.json")
    json.dump(pkg, open(pkg_path, "w"), indent=1, ensure_ascii=False)

    vision_inputs = cb_lineage.episode_vision_inputs(
        current["scriptVersionId"], pkg["contentSignature"],
        canon_lock["profileDigests"]["story"])
    vision_pkg = {"episodeId": episode, "title": candidate["title"],
                 "sourceScriptVersion": _md5_text(json.dumps(pkg, sort_keys=True)),
                 "sourceScript": _script_ref(current),
                 "sourceBeatPackageSignature": pkg["contentSignature"],
                 "inputSignature": cb_lineage.dependency_signature(
                     "episode-vision", vision_inputs),
                 "canonLock": pkg["canonLock"],
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


def _backfill_source_occurrences(beats, events, script_version_id):
    """Attach source identities only after old cuts prove an exact event partition."""
    migrated = json.loads(json.dumps(beats))
    cursor = 0
    for beat in migrated:
        start = cursor
        for cut_index, cut in enumerate(beat.get("cuts") or []):
            if cursor >= len(events):
                raise Refused("REFUSED — legacy beat package carries more cuts than the script")
            event = events[cursor]
            if event["type"] == "dialogue":
                expected_display = f"{event['speaker']}: {event['text']}"
                if cut.get("dialogue") != expected_display or cut.get("action") not in (None, ""):
                    raise Refused(
                        f"REFUSED — legacy cut {beat.get('beatCode')}[{cut_index}] does not "
                        f"match immutable dialogue event {cursor}")
            elif cut.get("action") != event["text"] or cut.get("dialogue") not in (None, ""):
                raise Refused(
                    f"REFUSED — legacy cut {beat.get('beatCode')}[{cut_index}] does not "
                    f"match immutable action event {cursor}")
            cut.update({
                "sourceEventId": event["sourceEventId"],
                "sourceEventIndex": event["i"],
                "sourceSceneNumber": event["scene"],
                "sourceType": event["type"],
                "dialogueOccurrenceId": event.get("dialogueOccurrenceId"),
                "speaker": event.get("speaker"),
                "exactText": event["text"] if event["type"] == "dialogue" else None,
            })
            cursor += 1
        source_events = events[start:cursor]
        if not source_events:
            raise Refused(f"REFUSED — legacy beat {beat.get('beatCode')} has no source events")
        signature = cb_lineage.source_beat_event_signature(script_version_id, source_events)
        records = signature["inputs"]["orderedEvents"]
        beat.update({
            "sourceBeatId": cb_lineage.source_beat_id(signature),
            "sourceEventRange": {
                "firstEventIndex": records[0]["sourceEventIndex"],
                "lastEventIndex": records[-1]["sourceEventIndex"],
                "firstEventId": records[0]["sourceEventId"],
                "lastEventId": records[-1]["sourceEventId"],
                "eventCount": len(records),
            },
            "sourceEventIds": [record["sourceEventId"] for record in records],
            "dialogueOccurrenceIds": [
                record["dialogueOccurrenceId"] for record in records
                if record["sourceType"] == "dialogue"],
            "sourceEventSignature": signature,
        })
    if cursor != len(events):
        raise Refused(
            f"REFUSED — legacy beat package carries {cursor} of {len(events)} script events")
    return migrated


def migrate_source_occurrence_contract(episode="Ep1", reviewed_by="Julian",
                                       dry_run=True, log=print):
    """Mechanically enrich proven legacy cuts; never infer or revise creative content."""
    current = script_record_for(episode)
    script_text = (ROOT / current["contentPath"]).read_text(encoding="utf-8")
    parsed = parse_script(script_text, _load_roster(), log=lambda *a, **k: None)
    _annotate_source_events(parsed["events"], current["scriptVersionId"])

    migration_record = {
        "status": "mechanically-proven-exact-event-partition",
        "at": _now(), "reviewedBy": reviewed_by,
    }
    changed, skipped = [], []
    cpath = candidate_path(episode)
    if cpath.exists():
        candidate = json.loads(cpath.read_text())
        try:
            if (candidate.get("approvalState") != "approved" or
                    candidate.get("scriptMd5") != _md5_text(script_text)):
                raise Refused("candidate is not approved byte-matched script evidence")
            candidate_new = json.loads(json.dumps(candidate))
            candidate_new["beats"] = _backfill_source_occurrences(
                candidate.get("beats") or [], parsed["events"], current["scriptVersionId"])
            candidate_new["sourceContract"] = cb_lineage.beat_package_source_contract(
                current["scriptVersionId"], candidate_new["beats"])
            candidate_new["sourceEventCoverage"] = source_event_coverage_report(
                parsed["events"], candidate_new["beats"])
            candidate_new["dialogueCoverage"] = dialogue_coverage_report(
                parsed["events"], candidate_new["beats"])
            candidate_new["sourceContractMigration"] = migration_record
            changed.append((cpath, candidate_new))
        except Refused as exc:
            # The known pre-Scene-0-fix candidate is retained as historical evidence. It
            # cannot authorize or constrain the corrected canonical package.
            skipped.append({"path": str(cpath.relative_to(ROOT)), "reason": str(exc)})
    for pkg_path in canonical_package_glob(episode):
        pkg = json.loads(pkg_path.read_text())
        if _package_script_version(pkg) != current["scriptVersionId"]:
            raise Refused(f"REFUSED — {pkg_path.name} belongs to another script version")
        pkg_new = json.loads(json.dumps(pkg))
        pkg_new["beats"] = _backfill_source_occurrences(
            pkg.get("beats") or [], parsed["events"], current["scriptVersionId"])
        pkg_new["sourceContract"] = cb_lineage.beat_package_source_contract(
            current["scriptVersionId"], pkg_new["beats"])
        pkg_new["contentSignature"] = cb_lineage.beat_package_signature(pkg_new)
        pkg_new["sourceContractMigration"] = migration_record
        report = cb_lineage.validate_beat_package_source_contract(pkg_new)
        if not report["ok"]:
            raise Refused("REFUSED — migrated source contract did not verify: "
                          + ", ".join(report["issues"][:5]))
        changed.append((pkg_path, pkg_new))

    if dry_run:
        log(f"SOURCE CONTRACT MIGRATION DRY RUN — {episode}: {len(changed)} files proven")
        return {"episode": episode, "changed": [str(path.relative_to(ROOT))
                                                  for path, _ in changed],
                "skippedHistoricalEvidence": skipped, "dryRun": True}

    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    backup_dir = OUT / "archive" / "source_contract_migration" / f"{episode}_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    for path, value in changed:
        shutil.copy2(path, backup_dir / path.name)
        temp_path = path.with_suffix(path.suffix + ".source-contract.tmp")
        temp_path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n")
        temp_path.replace(path)
    log(f"SOURCE CONTRACT MIGRATION — {episode}: exact event identities added; originals -> "
        f"{backup_dir.relative_to(ROOT)}")
    return {"episode": episode, "changed": [str(path.relative_to(ROOT))
                                              for path, _ in changed],
            "skippedHistoricalEvidence": skipped,
            "backup": str(backup_dir.relative_to(ROOT)), "dryRun": False}


def migrate_legacy_lineage(episode="Ep1", reviewed_by="Julian", dry_run=True, log=print):
    """Refuse retroactive creative provenance after the canon-lock cutover.

    Byte identity can prove which script a legacy artifact came from, but it cannot prove
    that Story & Direction saw the current show bible, character roster, performance law,
    or taste references. Those artifacts must be rebuilt through the signed intake route.
    """
    raise Refused(
        f"REFUSED — {episode} legacy creative lineage cannot be retroactively signed after "
        "the canon-lock cutover. Archive the old artifacts, then run Story & Direction "
        "again from the active immutable script.")


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
    elif cmd == "migrate-lineage":
        apply = "--apply" in sys.argv[3:]
        print(json.dumps(migrate_legacy_lineage(ep, dry_run=not apply), indent=1,
                         ensure_ascii=False))
    elif cmd == "migrate-source-contract":
        apply = "--apply" in sys.argv[3:]
        print(json.dumps(migrate_source_occurrence_contract(ep, dry_run=not apply), indent=1,
                         ensure_ascii=False))
    else:
        print(__doc__)
        sys.exit(1)
