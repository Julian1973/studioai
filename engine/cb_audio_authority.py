"""Deterministic routing between ElevenLabs dialogue and Seedance non-verbal audio."""
import re


_TAG = re.compile(r"\[(snor(?:e|es|ing)?|snort(?:s|ing)?|sneez(?:e|es|ing)|laugh(?:s|ing)?|giggl(?:e|es|ing))\]", re.I)
_PERFORMANCE_TAG = re.compile(r"\[[^\]]+\]")
_SCRIPT_NUMBER = re.compile(r"^\s*\d+\s*\t")
_TRAILING_STAGE_NOTE = re.compile(r"\s*\([^)]*\)\s*$")
_STAGE_BEAT = re.compile(r"(?:^|(?<=[.!?…]))\s*BEAT\.\s*", re.I)
_NONVERBAL_ACTION = r"laugh(?:s|ed|ing)?|giggl(?:e|es|ed|ing)|snort(?:s|ed|ing)?|sneez(?:e|es|ed|ing)|snor(?:e|es|ed|ing)"
_SOUND = re.compile(
    r"\b(?:z{3,}|a+h+c+h+o+o+|achoo+|ha(?:\s*ha)+|snor(?:e|es|ing)|"
    r"snort(?:s|ing)?|sneez(?:e|es|ing)|laugh(?:s|ing)?|giggl(?:e|es|ing)|"
    r"o{2,}h{2,}m{2,})\b[!.…]*",
    re.I,
)


def _trailing_nonverbal_action(text, speaker):
    """Split a trailing third-person action accidentally stored as dialogue."""
    actor = str(speaker or "").strip()
    if not actor:
        return text, None
    match = re.search(
        rf"(?:^|(?<=[.!?…]))\s*({re.escape(actor)}\s+(?:{_NONVERBAL_ACTION})[.!?…]*)\s*$",
        text, re.I)
    if not match:
        return text, None
    return text[:match.start(1)].strip(), match.group(1).strip()


def _trailing_screenplay_action(text):
    """Split an all-caps effect followed by third-person screenplay action."""
    match = re.search(
        r"(?:^|(?<=[.!?…]))\s*((?:[A-Z][A-Z'’-]{1,})[.!?…]+\s+"
        r"(?:The|A|An|His|Her|Their)\s+[a-z].*)$", text)
    if not match:
        return text, None
    return text[:match.start(1)].strip(), match.group(1).strip()


def _kind(value):
    text = value.casefold()
    if re.search(r"o{2,}h{2,}m{2,}", text):
        return "meditation mantra chant"
    if "zz" in text or "snor" in text:
        return "snore"
    if "achoo" in text or "choo" in text or "chhoo" in text or "sneez" in text:
        return "sneeze"
    if "snort" in text:
        return "snort"
    return "laughter"


def route_line(line):
    """Keep the script line immutable while deriving provider-facing audio lanes."""
    original = str(line.get("exactText") if line.get("exactText") is not None else line.get("text") or "")
    # Script numbering and trailing parenthetical action are production metadata. They
    # must remain in scriptExactText for provenance, but they are neither spoken text nor
    # independent SFX cues. Explicit authored sound tokens outside the stage note still
    # route to Seedance below.
    provider_text = _SCRIPT_NUMBER.sub("", original).strip()
    provider_text = _TRAILING_STAGE_NOTE.sub("", provider_text).strip()
    provider_text = _STAGE_BEAT.sub(" ", provider_text).strip()
    provider_text, screenplay_action = _trailing_screenplay_action(provider_text)
    provider_text, nonverbal_action = _trailing_nonverbal_action(
        provider_text, line.get("speaker"))
    trailing_action = screenplay_action or nonverbal_action
    tag_matches = list(_TAG.finditer(provider_text))
    sound_matches = list(_SOUND.finditer(provider_text))
    matches = tag_matches + sound_matches
    kinds = list(dict.fromkeys(
        [_kind(trailing_action)] if trailing_action else []
        + [_kind(match.group(0)) for match in matches]))
    if not matches and not trailing_action:
        return {**line, "scriptExactText": original, "exactText": provider_text}, None
    # A leading authored vocal event followed by words is one ordered performance,
    # not two independently timed assets. Keep it verbatim in @Audio1 so Seedance
    # cannot place the words before the sneeze or synthesize a competing voice.
    # Sound-only lines, and trailing/interstitial SFX after spoken words, continue
    # through the non-verbal Seedance lane below.
    first_sound = min((match.start() for match in sound_matches), default=len(provider_text))
    prefix = provider_text[:first_sound]
    semantic_prefix = _PERFORMANCE_TAG.sub(" ", prefix)
    without_sounds = _TAG.sub(" ", _SOUND.sub(" ", provider_text))
    if (tag_matches and re.search(r"[A-Za-z0-9]", without_sounds)):
        return {**line, "scriptExactText": original, "exactText": provider_text,
                "sfxEmbeddedInDialogue": True}, None
    if (sound_matches and not tag_matches
            and not re.search(r"[A-Za-z0-9]", semantic_prefix)
            and re.search(r"[A-Za-z0-9]", without_sounds)):
        return {**line, "scriptExactText": original, "exactText": provider_text,
                "sfxEmbeddedInDialogue": True}, None
    spoken = _TAG.sub(" ", provider_text)
    spoken = _SOUND.sub(" ", spoken)
    spoken = re.sub(r"\s+([,.!?…])", r"\1", spoken)
    spoken = re.sub(r"(?:\s*…\s*){2,}", " … ", spoken)
    # Preserve a trailing ellipsis when a spoken phrase is interrupted by a routed SFX
    # ("Oh, Ah, Hi Fuzzby … ACHOO!"). It is meaningful performance punctuation and tells
    # the Voice Director that the phrase deliberately hands off to Seedance. A sound-only
    # line still collapses to no spoken dialogue.
    spoken = re.sub(r"\s{2,}", " ", spoken).strip(" \t,;:-")
    if not re.search(r"[A-Za-z0-9]", spoken):
        spoken = ""
    cue = None
    if kinds:
        authored_cue = trailing_action or original.strip()
        meditation_note = (
            f' Perform Zenny\'s meditation mantra chant of "Ohhmmmmmm" using the exact '
            f'authored phonetic cue "{authored_cue}" as one continuous, warm, unstrained '
            "ooh-to-mmm tone with no extra syllables."
            if "meditation mantra chant" in kinds else ""
        )
        cue = {
            "dialogueOccurrenceId": line.get("dialogueOccurrenceId"),
            "sourceEventId": line.get("sourceEventId"),
            "sourceDialogueIndex": line.get("_sourceDialogueIndex"),
            "character": line.get("speaker"),
            "kinds": kinds,
            "startSec": line.get("startSec"),
            "endSec": line.get("endSec"),
            "authoredCue": authored_cue,
            "instruction": (
                f"Seedance 2.5 creates the character's natural {' and '.join(kinds)} "
                "as synchronized non-verbal SFX and physical performance. "
                "Do not synthesize words or place this sound in @Audio1."
                + meditation_note
            ),
        }
    spoken_line = None
    if spoken:
        spoken_line = {**line, "scriptExactText": original, "exactText": spoken,
                       "sfxInterrupted": True}
        delivery = str(line.get("delivery") or "")
        if delivery:
            # Delivery is direction, not provider dialogue. Preserve references such as
            # "after the sneeze lands"; deleting sound words corrupts acting guidance.
            spoken_line["delivery"] = delivery
    return spoken_line, cue


def route_lines(lines):
    spoken, cues = [], []
    for source_index, line in enumerate(lines or [], start=1):
        indexed_line = dict(line)
        indexed_line.setdefault("_sourceDialogueIndex", source_index)
        spoken_line, cue = route_line(indexed_line)
        if spoken_line:
            spoken.append(spoken_line)
        if cue:
            cues.append(cue)
    return {"spokenDialogue": spoken, "seedanceSfxCues": cues}


def spoken_dialogue_lines(shot):
    return route_lines(shot.get("dialogueLines") or [])["spokenDialogue"]


def seedance_sfx_cues(shot):
    return route_lines(shot.get("dialogueLines") or [])["seedanceSfxCues"]


def route_voice_direction(direction, original_lines):
    """Project an existing Voice Director record onto the spoken-only provider lane."""
    routed = route_lines(original_lines)
    spoken = routed["spokenDialogue"]
    if not routed["seedanceSfxCues"]:
        return dict(direction), spoken
    by_id = {line.get("dialogueOccurrenceId"): line for line in spoken
             if line.get("dialogueOccurrenceId")}
    projected = []
    for index, item in enumerate(direction.get("lines") or []):
        locked = by_id.get(item.get("dialogueOccurrenceId"))
        if locked is None and index < len(original_lines):
            candidate, _ = route_line(original_lines[index])
            locked = candidate
        if not locked:
            continue
        record = {**item, "exactDialogue": locked["exactText"]}
        performed, _ = route_line({"exactText": item.get("performedText") or locked["exactText"]})
        record["performedText"] = _project_performed_text(
            (performed or {}).get("exactText"), locked["exactText"])
        recipes = []
        for recipe in item.get("takeRecipes") or []:
            recipe_text, _ = route_line({"exactText": recipe.get("performedText") or record["performedText"]})
            recipes.append({**recipe, "performedText": _project_performed_text(
                (recipe_text or {}).get("exactText"), locked["exactText"])})
        if recipes:
            record["takeRecipes"] = recipes
        projected.append(record)
    return {**direction, "lines": projected}, spoken


def _project_performed_text(performed_text, locked_text):
    """Preserve acting tags only when provider words still match the spoken lane."""
    candidate = str(performed_text or "").strip()
    locked = str(locked_text or "").strip()
    candidate_words = re.findall(r"[A-Za-z0-9']+", _PERFORMANCE_TAG.sub(" ", candidate))
    locked_words = re.findall(r"[A-Za-z0-9']+", _PERFORMANCE_TAG.sub(" ", locked))
    if [word.casefold() for word in candidate_words] == [word.casefold() for word in locked_words]:
        return candidate or locked
    safe_tags = [
        match.group(0) for match in _PERFORMANCE_TAG.finditer(candidate)
        if not _TAG.fullmatch(match.group(0))
    ]
    return (("".join(safe_tags) + " ") if safe_tags else "") + locked
