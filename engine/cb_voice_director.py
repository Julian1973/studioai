#!/usr/bin/env python3
"""Deterministic Voice Director compiler and mechanical preflight.

Creative direction is typed upstream. This module performs no creative inference: it
binds locked script occurrences to canon voices, validates the performance contract,
and emits reproducible ElevenLabs V3 request specifications.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
from copy import deepcopy

import cb_emission_conformance as emission

ROOT = pathlib.Path(__file__).resolve().parent.parent
VOICE_CARDS_PATH = ROOT / "shows/crystal-bears/canon/voice_cards.json"
REGISTERS_PATH = ROOT / "shows/crystal-bears/creative/VOICE_ARCHETYPE_REGISTERS.json"
RULEBOOK_PATH = ROOT / "shows/crystal-bears/creative/VOICE_DIRECTOR_RULEBOOK.json"
PLAYBOOK_PATH = ROOT / "shows/crystal-bears/creative/learning/VOICE_PLAYBOOK.json"
COMPILER_VERSION = "voice-director-v1"

_TAG_RE = re.compile(r"\[([^\]]+)\]")
_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_SEGMENT_RE = re.compile(r"[^.!?…\n]+[.!?…]*|\n+")


class VoiceContractError(RuntimeError):
    pass


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VoiceContractError(f"Voice Director data is unavailable: {path.name}: {exc}") from exc


def voice_cards():
    return _load(VOICE_CARDS_PATH)


def archetype_registers():
    return _load(REGISTERS_PATH)


def rulebook():
    return _load(RULEBOOK_PATH)


def _words(text):
    return [word.casefold() for word in _WORD_RE.findall(_TAG_RE.sub("", str(text or "")))]


def _tags(text):
    return [tag.strip().casefold() for tag in _TAG_RE.findall(str(text or ""))]


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _check(checks, code, passed, message):
    checks.append({"code": code, "passed": bool(passed), "message": message})


def post_direction_audit(line, locked_line, card, register):
    """Run the craft-voice rulebook as objective, track-level checks."""
    checks = []
    questions = line.get("performanceQuestions") or {}
    policy = rulebook()
    rules = policy["mechanicalRules"]
    required_questions = tuple(policy["fivePerformanceQuestions"])
    missing = [key for key in required_questions if not questions.get(key)]
    _check(checks, "five-performance-questions", not missing,
           "All five performance questions are answered." if not missing else
           "Missing performance questions: " + ", ".join(missing))

    _check(checks, "dialogue-occurrence-lock",
           line.get("dialogueOccurrenceId") == locked_line.get("dialogueOccurrenceId"),
           "Dialogue occurrence matches the locked script.")
    _check(checks, "speaker-lock",
           str(line.get("character") or "").casefold() ==
           str(locked_line.get("speaker") or "").casefold(),
           "Character matches the locked script speaker.")
    _check(checks, "exact-dialogue-lock",
           _words(line.get("exactDialogue")) == _words(locked_line.get("exactText")),
           "Exact dialogue preserves every locked script word.")

    recipes = line.get("takeRecipes") or []
    _check(checks, "recipe-count", 1 <= len(recipes) <= 3,
           "Each line has one to three take-direction recipes.")
    palette = {tag.casefold() for tag in card.get("defaultTags", [])}
    palette.update(tag.casefold() for tag in register.get("allowedTags", []))
    banned = {tag.casefold() for tag in card.get("bannedTags", [])}
    for recipe in recipes:
        text = str(recipe.get("performedText") or "")
        recipe_id = recipe.get("recipeId") or "unnamed"
        _check(checks, f"script-fidelity:{recipe_id}",
               _words(text) == _words(locked_line.get("exactText")),
               f"{recipe_id} preserves every locked script word.")
        try:
            emission.require_complete_sentence(
                _TAG_RE.sub("", text), context=f"voice recipe {recipe_id}")
            sentence_complete = True
        except emission.EmissionConformanceError:
            sentence_complete = False
        _check(checks, f"complete-sentence:{recipe_id}", sentence_complete,
               f"{recipe_id} ends as a complete spoken sentence.")
        tags = _tags(text)
        illegal = sorted(set(tags) - palette)
        blocked = sorted(set(tags) & banned)
        _check(checks, f"tag-palette:{recipe_id}", not illegal and not blocked,
               f"{recipe_id} uses only the character and archetype tag palette."
               if not illegal and not blocked else
               f"{recipe_id} has off-palette/banned tags: {', '.join(illegal + blocked)}")
        crowded = []
        for segment in _SEGMENT_RE.findall(text):
            segment_tags = _tags(segment)
            if len(segment_tags) > int(rules["maxTagsPerSegment"]):
                crowded.append(segment.strip())
        _check(checks, f"tag-density:{recipe_id}", not crowded,
               f"{recipe_id} uses no more than two tags per segment.")
        take_count = int(recipe.get("takesCount") or 0)
        _check(checks, f"take-count:{recipe_id}", take_count >= 1,
               f"{recipe_id} has a positive takes count.")
        if len(_words(locked_line.get("exactText"))) <= int(rules["shortLineMaxWords"]):
            has_context = bool(str(line.get("previousText") or "").strip())
            _check(checks, f"short-line-context:{recipe_id}", has_context and
                   take_count >= int(rules["shortLineMinimumTakes"]),
                   f"Short line {recipe_id} includes previous_text runway and at least two takes.")

    all_tags = sorted({tag for recipe in recipes for tag in _tags(recipe.get("performedText"))})
    purposes = {str(key).casefold(): str(value).strip()
                for key, value in (line.get("tagPurposes") or {}).items()}
    missing_purposes = [tag for tag in all_tags if not purposes.get(tag)]
    _check(checks, "tag-purposes", not missing_purposes,
           "Every audio tag has a named dramatic purpose." if not missing_purposes else
           "Tags without dramatic purpose: " + ", ".join(missing_purposes))
    pause_notation = bool(re.search(r"…|—|\[(?:pause|long pause|pauses|hesitates)\]",
                                    " ".join(str(r.get("performedText") or "") for r in recipes), re.I))
    _check(checks, "pause-reasons", not pause_notation or bool(line.get("pauseReasons")),
           "Every pause/hesitation notation has a named reason.")
    _check(checks, "line-duration",
           0 < float(line.get("estimatedDurationSec") or 0) <=
           float(rules["maxLineDurationSec"]),
           "The directed line has a positive duration no longer than 15 seconds.")
    _check(checks, "frame-one-space", float(line.get("startsAtSec") or 0) > 0,
           "Dialogue begins after frame one, preserving the thought-before space.")

    _check(checks, "physical-state", bool(str(line.get("physicalState") or "").strip()),
           "Physical state is explicit.")
    emotional = line.get("emotionalState") or {}
    _check(checks, "emotional-state",
           bool(emotional.get("entry") and emotional.get("exit")),
           "Emotional entry and exit are explicit.")
    _check(checks, "listener", bool(str(line.get("listener") or "").strip()),
           "The listener is explicit.")
    _check(checks, "body-voice-relationship",
           bool(str(line.get("bodyVoiceRelationship") or "").strip()),
           "The body/voice relationship is explicit.")
    _check(checks, "archetype-register",
           line.get("archetypeId") == register.get("archetypeId"),
           "The line is bound to a known beat archetype register.")
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def compile_line(line, locked_line, *, cards=None, registers=None):
    cards = cards or voice_cards()
    registers = registers or archetype_registers()
    character = str(line.get("character") or "")
    card = cards.get("characters", {}).get(character)
    if not card:
        raise VoiceContractError(f"No canon voice card for {character or 'unnamed character'}")
    register = registers.get("registers", {}).get(str(line.get("archetypeId") or ""))
    if not register:
        raise VoiceContractError(
            f"No voice archetype register for {line.get('archetypeId') or 'unset archetype'}")
    audit = post_direction_audit(line, locked_line, card, register)
    failed = [item["message"] for item in audit["checks"] if not item["passed"]]
    if failed:
        raise VoiceContractError("REFUSED - Post-Direction Audit failed: " + " ".join(failed))
    compiled = {
        "schemaVersion": 1,
        "compiler": COMPILER_VERSION,
        "dialogueOccurrenceId": line["dialogueOccurrenceId"],
        "sourceEventId": line.get("sourceEventId") or locked_line.get("sourceEventId"),
        "character": character,
        "voiceId": card["voiceId"],
        "modelId": card.get("modelId", "eleven_v3"),
        "voiceSettings": deepcopy(card["settings"]),
        "cadenceSignature": card["cadenceSignature"],
        "physicalSignature": card["physicalSignature"],
        "exactDialogue": locked_line["exactText"],
        "performanceQuestions": deepcopy(line["performanceQuestions"]),
        "physicalState": line["physicalState"],
        "emotionalState": deepcopy(line["emotionalState"]),
        "listener": line["listener"],
        "bodyVoiceRelationship": line["bodyVoiceRelationship"],
        "previousText": line["previousText"],
        "startsAtSec": line["startsAtSec"],
        "estimatedDurationSec": line["estimatedDurationSec"],
        "pauseReasons": deepcopy(line.get("pauseReasons") or []),
        "tagPurposes": deepcopy(line.get("tagPurposes") or {}),
        "archetype": deepcopy(register),
        "takeRecipes": deepcopy(line["takeRecipes"]),
        "postDirectionAudit": audit,
        "humanVerdictQuestions": deepcopy(rulebook()["humanVerdictQuestions"]),
    }
    compiled["compiledHash"] = _digest(compiled)
    return compiled


def emit_v3_requests(compiled):
    """Emit stable provider request specs in recipe order, then take order."""
    requests = []
    for recipe in compiled["takeRecipes"]:
        for take_number in range(1, int(recipe["takesCount"]) + 1):
            body = {
                "text": recipe["performedText"],
                "model_id": compiled["modelId"],
                "voice_settings": deepcopy(compiled["voiceSettings"]),
            }
            item = {
                "recipeId": recipe["recipeId"],
                "label": recipe.get("label") or recipe["recipeId"],
                "primary": bool(recipe.get("primary")),
                "takeNumber": take_number,
                "voiceId": compiled["voiceId"],
                "contextRunway": compiled["previousText"],
                "transportNotes": [
                    "ElevenLabs eleven_v3 does not accept previous_text; runway is retained "
                    "as audited direction context and is not inserted into locked dialogue."],
                "body": body,
            }
            item["requestId"] = _digest({
                "compiledHash": compiled["compiledHash"], **item})[:20]
            requests.append(item)
    return requests


def compile_track(direction, locked_lines):
    by_occurrence = {
        item.get("dialogueOccurrenceId"): item for item in locked_lines
        if item.get("dialogueOccurrenceId")
    }
    compiled = []
    for index, line in enumerate(direction.get("lines") or []):
        locked = by_occurrence.get(line.get("dialogueOccurrenceId"))
        if locked is None and line.get("dialogueOccurrenceId") is None and index < len(locked_lines):
            positional = locked_lines[index]
            if positional.get("dialogueOccurrenceId") is None:
                locked = positional
        if not locked:
            raise VoiceContractError(
                f"Direction references an unlocked dialogue occurrence: "
                f"{line.get('dialogueOccurrenceId')}")
        compiled.append(compile_line(line, locked))
    if len(compiled) != len(locked_lines):
        raise VoiceContractError(
            f"REFUSED - direction has {len(compiled)} line(s); script locks {len(locked_lines)}")
    track = {"compiler": COMPILER_VERSION, "shotId": direction.get("shotId"),
             "lines": compiled}
    track["compiledHash"] = _digest(track)
    return track


def bank_recipe(character, archetype_id, recipe, *, shot_id, candidate, reviewed_by="Julian"):
    """Persist only an explicit human HEAR verdict; generation never calls this."""
    try:
        playbook = _load(PLAYBOOK_PATH)
    except VoiceContractError:
        playbook = {"schemaVersion": 1, "recipes": {}}
    key = f"{character}::{archetype_id}"
    playbook.setdefault("recipes", {})[key] = {
        "character": character,
        "archetypeId": archetype_id,
        "recipe": deepcopy(recipe),
        "sourceShotId": shot_id,
        "approvedCandidate": candidate,
        "approvedBy": reviewed_by,
    }
    PLAYBOOK_PATH.write_text(json.dumps(playbook, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    return playbook["recipes"][key]
