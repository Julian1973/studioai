#!/usr/bin/env python3
"""Project-agnostic production rules shared by keyframe, render and post paths."""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import pathlib
import re


HERE = pathlib.Path(__file__).resolve().parent
BEAT_COST_PATH = HERE / "config" / "beat_costs.json"
RULES_VERSION = "engine-rules-v4"


def _norm(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _line_text(line):
    return _norm(line.get("exactText") if line.get("exactText") is not None else line.get("text"))


def load_beat_costs(path=BEAT_COST_PATH):
    data = json.loads(pathlib.Path(path).read_text())
    if not data.get("version") or not data.get("costsSec"):
        raise ValueError("beat-cost data is missing version or costsSec")
    return data


def _number_word(value):
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    return int(value) if str(value).isdigit() else words.get(str(value).casefold(), 1)


def infer_timing_beats(shot, direction):
    """Derive typed costs for legacy direction; new records may supply timingBeats."""
    explicit = list((direction or {}).get("timingBeats") or [])
    if explicit:
        return [{"type": str(item["type"]), "count": int(item.get("count", 1)),
                 "source": item.get("source", "approved Director timingBeats")}
                for item in explicit]
    parts = [shot.get("purpose"), (direction or {}).get("physicalCauseAndEffect")]
    parts.extend((item or {}).get("primaryEvent") for item in
                 (direction or {}).get("stagePlan") or [])
    text = _norm(" ".join(str(item or "") for item in parts)).casefold()
    beats = []

    def add(kind, pattern, source=None):
        if re.search(pattern, text, re.I):
            beats.append({"type": kind, "count": 1,
                          "source": source or f"derived from approved {kind} direction"})

    add("travel", r"\b(chase|pursu|travel|barrel|fly|flight|zoom|accelerat|route)\w*")
    near = re.search(
        r"\b(one|two|three|four|five|\d+)\s+(?:readable\s+)?near[- ]miss(?:es)?\b", text)
    if near:
        beats.append({"type": "dodge", "count": _number_word(near.group(1)),
                      "source": "approved near-miss count"})
    elif re.search(r"\b(dodge|near[- ]miss|evasion)\b", text):
        beats.append({"type": "dodge", "count": 1, "source": "approved dodge"})
    repeated_impacts = re.search(
        r"\b(one|two|three|four|five|\d+)\s+(?:separate|distinct|readable|escalating)?\s*"
        r"(?:impacts?|contacts?|collisions?|flower clips?)\b", text)
    if repeated_impacts:
        beats.append({"type": "impact", "count": _number_word(repeated_impacts.group(1)),
                      "source": "approved repeated-contact count"})
    else:
        add("impact", r"\b(impact|crash|collision|collide|clips?|hits?|contact)\b")
    add("load_release", r"\b(loads?|loaded|recoil|rebound|springy|stores? force|snaps? .*upright)\b")
    add("tumble", r"\b(tumble|rotation|somersault|cartwheel|spins? sideways)\b")
    add("settle", r"\b(settle|recovery|recovers?|landing|upright hover|held pose|holds? .*pose)\b")
    add("reaction", r"\b(reaction|reacts?|eye[- ]roll|double take|mouth corner|flinch)\b")
    add("turn", r"\b(turns?|pivots?|reverses? direction)\b")
    add("aerial", r"\b(aerial|double back|double backward|triple twist|multi-rotation|biles)\b")
    add("self_check", r"\b(self[- ]check|checks? (?:his|her|their|its) (?:body|state|chest)|"
        r"looks? (?:left|around).*looks? (?:right|down)|realises? .*\b(?:fine|unhurt|intact))\b")
    return beats


def travel_traversal_boilerplate(shot, direction):
    """Emit the minimum visible traversal evidence required by R9."""
    if not any(item["type"] == "travel" for item in infer_timing_beats(shot, direction)):
        return ""
    return (
        "Travel traversal: show three parallax speeds: foreground elements pass fastest, "
        "midground landmarks pass the camera and vanish behind, and the distant environment "
        "moves slowest. The subject pulls ahead and appears smaller; the camera surges to "
        "recover it. Let the subject drift off-centre, then reframe to recover it. Use "
        "occasional foreground elements to wipe across the lens."
    )


def sailing_departure_boilerplate(shot, direction):
    """Require visible real-world cause and effect for a wind-powered departure."""
    values = [shot.get("title"), shot.get("purpose"), shot.get("storyBeat"),
              shot.get("action")]
    values.extend(str(value or "") for value in
                  (shot.get("continuityConstraints") or []))
    values.extend([direction.get("physicalCauseAndEffect"),
                   direction.get("continuityFinish")])
    values.extend(str(value or "") for item in (direction.get("shotPlan") or [])
                  for value in (item.values() if isinstance(item, dict) else []))
    text = _norm(" ".join(str(value or "") for value in values)).casefold()
    if not re.search(r"\b(sailboat|sailing boat)\b", text) or not re.search(
            r"\b(untie|mooring|push(?:es|ed|ing)? off|cast(?:s|ing)? off|"
            r"releas(?:e|es|ed|ing) (?:the )?(?:line|rope))\b", text):
        return ""
    return (
        "Wind-powered departure causality: show exactly one active mooring line, visibly "
        "running from one boat attachment point to one cleat or post; no second bow or stern "
        "line exists. The hull remains alongside the pier while that single mooring line is "
        "visibly released from the cleat or post and brought fully aboard. The "
        "sailor then controls the sheet or boom to bring the sail around. Wind visibly fills "
        "and tensions the sail; only after that load does the hull heel slightly, gather way "
        "and move away bow-first toward open water, with the stern following naturally. No "
        "sideways slide, stern-first departure, motor-like drift, teleporting departure, or "
        "boat movement while still tethered."
    )


def sailing_departure_action(action, shot, direction):
    """Place sailing causality inside the internal action that owns departure."""
    text = _norm(action)
    clause = sailing_departure_boilerplate(shot, direction)
    if not clause or not re.search(
            r"\b(untie|mooring|push(?:es|ed|ing)? off|sails? away)\b", text, re.I):
        return text
    if re.search(r"wind.+(?:fills?|loads?|tensions?).+sail", text, re.I) and re.search(
            r"only after.+(?:hull|boat).+(?:heel|gather|move)", text, re.I):
        return text
    return text.rstrip(".") + ". " + clause


def living_performance_boilerplate(shot, direction=None, *, medium="animation"):
    """Keep eyelines and inner life readable through every held story landing."""
    cast = [str(name).strip() for name in shot.get("charactersInFrame") or []
            if str(name).strip()]
    subjects = ", ".join(cast) if cast else "every visible character"
    if medium == "still":
        return (
            f"Living performance lock: {subjects} has a specific motivated eyeline target "
            "and a readable active thought in the eyes. Use a precise asymmetric expression; "
            "no vacant forward stare, unfocused eyes, frozen smile, mannequin pose or generic "
            "camera-facing expression."
        )
    return (
        f"Living performance lock: {subjects} has a specific motivated eyeline target and a "
        "readable active thought throughout. In every hold and final landing preserve subtle "
        "breathing, natural blink timing, focused eyes and a precise asymmetric micro-expression. "
        "The beat owner looks toward the story target; the witness looks toward the beat owner "
        "or visible evidence. No vacant forward stare, unfocused eyes, frozen smile, mannequin "
        "stillness or generic camera-facing expression."
    )


def natural_keyframe_staging_boilerplate(shot):
    """Prevent identity turnarounds from donating their neutral presentation pose."""
    cast = [str(name).strip() for name in shot.get("openingCharactersInFrame") or
            shot.get("charactersInFrame") or [] if str(name).strip()]
    subjects = ", ".join(cast) if cast else "Every visible character"
    return (
        f"Natural staging lock: restage {subjects} from identity reference into the authored "
        "scene action. Each body has believable balance, weight through the feet or supported "
        "hover, relaxed shoulders and naturally bent elbows; arms rest by the body or perform "
        "a motivated story action. Never copy a turnaround's front, side or presentation pose; "
        "no arms held out from the body, T-pose, model-sheet stance, evenly spread limbs or "
        "symmetrical display posture."
    )


def action_unit_report(shot, direction, prompt=""):
    """R8-R16 production grammar checks for action, comedy and dialogue units."""
    data = direction or {}
    internal = [item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in data.get("shotPlan") or []]
    timing = infer_timing_beats(shot, data)
    counts = {item["type"]: int(item.get("count", 1)) for item in timing}
    all_text = _norm(" ".join(
        str(value or "") for item in internal for value in item.values()))
    raw_prompt = str(prompt or data.get("providerPrompt") or "")
    prompt_text = _norm(raw_prompt)
    combined = _norm(all_text + " " + prompt_text)
    errors = []

    action_unit = any(counts.get(kind) for kind in
                      ("travel", "dodge", "impact", "load_release", "tumble", "aerial"))
    if action_unit and not 2 <= len(internal) <= 4:
        errors.append("R8 action unit requires 2-4 motivated internal shots")
    if len(internal) > 1:
        ideas = [_norm(item.get("purpose") or item.get("causalAction")) for item in internal]
        if len(set(value.casefold() for value in ideas)) != len(ideas):
            errors.append("R8 internal shots repeat a motion idea instead of giving each cut one job")

    if counts.get("travel"):
        traversal_checks = {
            "three parallax speeds": r"three (?:parallax )?speeds|foreground.+midground.+distant",
            "landmarks pass and vanish": r"landmarks?.+pass.+(?:vanish|disappear|fall behind)|pass(?:es|ing)?.+camera.+(?:vanish|behind)",
            "subject scale changes": r"pulls? ahead.+(?:shrink|smaller)|camera surges?.+(?:swell|larger)|changes? scale",
            "off-centre recovery": r"(?:off[- ]centre|frame edge|off[- ]center).+(?:recover|reframe|swing)",
            "foreground lens wipes": r"foreground.+wipe.+lens|stems?.+wipe.+lens",
        }
        for label, pattern in traversal_checks.items():
            if not re.search(pattern, combined, re.I):
                errors.append(f"R9 travel direction is missing {label}")
        if re.search(r"\bblur\b", combined, re.I) and not any(
                re.search(pattern, combined, re.I) for pattern in traversal_checks.values()):
            errors.append("R9 motion is described only as blur")

    sailing = sailing_departure_boilerplate(shot, data)
    if sailing:
        sailing_checks = {
            "mooring released before movement": r"mooring (?:line|rope).+(?:released|untied).+(?:before|only after).+(?:hull|boat).+(?:move|gather)",
            "sail is deliberately controlled": r"(?:controls?|pulls?|hauls?).+(?:sheet|boom).+(?:sail|bring)",
            "wind visibly loads the sail": r"wind.+(?:fills?|loads?|tensions?).+sail",
            "loaded sail causes hull response": r"only after.+(?:load|fills?).+(?:hull|boat).+(?:heel|gather|move)",
            "bow leads the departure": r"bow[- ]first.+(?:open water|stern)|bow.+leads?.+stern",
        }
        sailing_text = combined
        for label, pattern in sailing_checks.items():
            if not re.search(pattern, sailing_text, re.I):
                errors.append(f"R16 sailing departure is missing {label}")

    if raw_prompt and not re.search(
            r"Living performance lock:.+motivated eyeline target.+active thought", raw_prompt,
            re.I | re.S):
        errors.append("R17 prompt is missing the living-performance eyeline and inner-life lock")
    if raw_prompt and not re.search(
            r"no vacant forward stare.+unfocused eyes.+frozen smile", raw_prompt, re.I | re.S):
        errors.append("R17 prompt does not forbid vacant landing performance")

    impact_count = counts.get("impact", 0)
    if impact_count > 1:
        ordinal = all(re.search(rf"\b{word}\b", combined, re.I)
                      for word in ("first", "second", "third")[:min(impact_count, 3)])
        escalation = re.search(
            r"each (?:worse|larger|harder|bigger)|worse than|larger than|"
            r"first.+second.+third|spin doubles|gains? more", combined, re.I)
        if not ordinal:
            errors.append("R10 repeated contacts are not individually separated and readable")
        if not escalation:
            errors.append("R10 repeated contacts do not visibly escalate")

    if counts.get("aerial"):
        aerial_shots = [item for item in internal if re.search(
            r"\b(aerial|leap|dive|breach|half[- ]roll|double back|double backward|"
            r"triple twist|multi-rotation|biles)\b",
            _norm(" ".join(str(value or "") for value in item.values())), re.I)]
        if len(aerial_shots) != 1:
            errors.append("R11 compound aerial must own exactly one dedicated internal shot")
        elif not re.search(r"track(?:s|ing)? (?:the )?(?:full|complete) (?:arc|aerial|rotation)",
                           _norm(aerial_shots[0].get("framingLensAndCamera")), re.I):
            errors.append("R11 compound aerial camera does not track the full arc")

    clocks = list(((data.get("creativeTranslation") or {}).get("gagClocks") or []))
    retroactive = any(bool(item.get("retroactive")) for item in clocks)
    if retroactive:
        if not counts.get("self_check"):
            errors.append("R12 retroactive button has no typed self_check beat")
        if not re.search(r"\b(checks?|looks? around|looks? left|looks? right|intact|unhurt|fine)\b",
                         combined, re.I):
            errors.append("R12 retroactive button has no visible self-check performance")

    cast = list(shot.get("charactersInFrame") or [])
    if len(cast) >= 2 and clocks:
        sides = list(data.get("witnessStagingSides") or [])
        if not sides:
            errors.append("R13 two-character gag has no canonical witness staging sides")
        if not re.search(r"\b(witness|non-acting|listener)\b.+\b(still|motionless|holds?)\b|"
                         r"\b(still|motionless)\b.+\b(witness|listener)\b", combined, re.I):
            errors.append("R13 payoff does not hold on the non-acting witness")

    approved_camera = _norm(shot.get("camera"))
    continuous_unit = bool(re.search(
        r"\bone continuous\b|\bcontinuous (?:shot|move|take)\b",
        approved_camera + " " + prompt_text, re.I))
    if (action_unit and not continuous_unit and
            re.search(r"\bno cuts?\b|\bno handheld\b", prompt_text, re.I)):
        errors.append("R14 action unit incorrectly prohibits cuts or handheld camera")

    dialogue = list(shot.get("dialogueLines") or [])
    dialogue_owners = {}
    for internal_shot in internal:
        directions = list(internal_shot.get("dialogueDirections") or [])
        for position, line_index in enumerate(
                internal_shot.get("dialogueLineIndexes") or []):
            dialogue_owners[int(line_index)] = {
                "shot": int(internal_shot.get("shotNumber") or 0),
                "direction": directions[position] if position < len(directions) else "",
                "hold": bool(internal_shot.get("holdAfterDialogue", True)),
            }
    prompt_shots = {
        int(number): body for number, body in re.findall(
            r"Shot\s+(\d+):\s*(.*?)(?=\nShot\s+\d+:|\nWitness staging:|\n\[|\Z)",
            raw_prompt, re.I | re.S)
    }
    for line_number, line in enumerate(dialogue, start=1):
        exact = _line_text(line)
        speaker = _norm(line.get("speaker"))
        owner = dialogue_owners.get(line_number)
        if not owner:
            errors.append(f"R15 dialogue {speaker}: {exact} has no typed internal-shot owner")
            continue
        body = prompt_shots.get(owner["shot"], "")
        marker = (rf"Dialogue placement:\s*{re.escape(speaker)},\s*[^:]+:\s*"
                  rf"\{{{re.escape(exact)}\}}")
        if not owner["direction"] or not re.search(marker, body, re.I):
            errors.append(f"R15 dialogue {speaker}: {exact} has no written in-beat direction")
            continue
        has_hold = bool(re.search(
            r"pose holds (?:for )?a full beat after the line ends", body, re.I))
        if owner["hold"] and not has_hold:
            errors.append(f"R15 dialogue {speaker}: {exact} is missing its ruled post-line hold")
        if not owner["hold"] and has_hold:
            errors.append(f"R15 dialogue {speaker}: {exact} incorrectly delays immediate action")

    return {"ready": not errors, "errors": errors, "rulesVersion": RULES_VERSION,
            "actionUnit": action_unit, "internalShotCount": len(internal),
            "timingBeatCounts": counts}


def beat_cost_report(shot, direction, cost_data=None):
    data = cost_data or load_beat_costs()
    costs = data["costsSec"]
    beats = infer_timing_beats(shot, direction)
    rows = []
    subtotal = 0.0
    for item in beats:
        kind = item["type"]
        if kind not in costs:
            raise ValueError(f"unknown timing beat type {kind!r}")
        unit = float(costs[kind])
        total = unit * int(item.get("count", 1))
        subtotal += total
        rows.append({**item, "unitCostSec": unit, "totalCostSec": round(total, 3)})
    holds = []
    clocks = list(((direction or {}).get("creativeTranslation") or {}).get("gagClocks") or [])
    if not clocks:
        clocks = list(shot.get("comedyContractsApproved") or [])
    for clock in clocks:
        hold = clock.get("recoveryHoldSec")
        if hold is not None:
            value = float(hold)
            subtotal += value
            holds.append({"beatCode": clock.get("beatCode"), "seconds": value})
    minimum = subtotal * (1.0 + float(data["margin"]))
    requested = float((direction or {}).get("durationSec") or shot.get("durationSec") or 0)
    recommended = int(math.ceil(minimum - 1e-9))
    payload = {
        "rulesVersion": RULES_VERSION,
        "costVersion": data["version"],
        "margin": data["margin"],
        "beats": rows,
        "buttonHolds": holds,
        "subtotalSec": round(subtotal, 3),
        "minimumWithMarginSec": round(minimum, 3),
        "recommendedDurationSec": recommended,
        "requestedDurationSec": requested,
        "ready": requested + 1e-9 >= minimum,
    }
    payload["costSignature"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def duration_provenance(shot, direction, *, costed_at=None):
    report = beat_cost_report(shot, direction)
    return {
        "authoritative": True,
        "rulesVersion": RULES_VERSION,
        "costVersion": report["costVersion"],
        "costSignature": report["costSignature"],
        "costedAt": costed_at or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "unitDurationSec": report["requestedDurationSec"],
        "recommendedDurationSec": report["recommendedDurationSec"],
        "ready": report["ready"],
    }


def asset_may_constrain_duration(asset, provenance):
    """An older asset remains a visual input, but cannot constrain a newly costed unit."""
    if not asset or not provenance or not provenance.get("authoritative"):
        return False
    produced = asset.get("generatedAt") or asset.get("at")
    return bool(produced and produced >= provenance.get("costedAt", ""))


def apply_compression_verdict(cost_data, verdict):
    """Only an explicit compression verdict may raise a versioned beat cost."""
    category = str((verdict or {}).get("category") or "").casefold()
    diagnosis = _norm((verdict or {}).get("diagnosis") or (verdict or {}).get("correction"))
    if category != "action-timing" or not re.search(
            r"\b(compress|rushed|too fast|did not read|not enough time)\b", diagnosis, re.I):
        return cost_data, False
    beat_type = str((verdict or {}).get("beatType") or "").strip()
    increase = float((verdict or {}).get("increaseSec") or 0)
    if beat_type not in cost_data.get("costsSec", {}) or increase <= 0:
        raise ValueError("compression verdict requires a known beatType and positive increaseSec")
    updated = json.loads(json.dumps(cost_data))
    updated["costsSec"][beat_type] = round(
        float(updated["costsSec"][beat_type]) + increase, 3)
    updated.setdefault("adjustments", []).append({
        "beatType": beat_type, "increaseSec": increase, "diagnosis": diagnosis,
        "sourceVerdictId": verdict.get("verdictId"),
    })
    return updated, True


def geometry_agreement(cinematography, animation):
    """Block contradictory camera/geography instructions across SEE and WATCH."""
    cine = cinematography or {}
    anim = animation or {}
    errors = []
    cine_geo = [_norm(item) for item in cine.get("geography") or []]
    anim_geo = [_norm(item) for item in anim.get("geography") or []]
    if anim_geo and cine_geo != anim_geo:
        errors.append("keyframe and render geography are not verbatim-identical")
    camera = _norm(anim.get("cameraBehaviour") or cine.get("lensAndCameraRelationship"))
    follow = bool(re.search(r"\b(follow|chase|behind|slightly late|drone)\b", camera, re.I))
    placements = ((cine.get("openingFrameLayout") or {}).get("placements") or [])
    if follow:
        for item in placements:
            facing = _norm(item.get("facing"))
            if re.search(r"\b(toward|faces?) (?:the )?camera\b|\bfront[- ]facing\b", facing, re.I):
                errors.append(
                    f"{item.get('character') or 'subject'} faces camera while the render camera follows travel")
    negative = " ".join(_norm(item) for item in cine.get("negativeSpace") or [])
    route_text = " ".join(
        item for item in cine_geo
        if re.search(
            r"\b(?:travel|route|lead room|moves?|heads?|flies?|walks?|runs?)\s+"
            r"(?:toward|to|into|along|through)\b",
            item, re.I))
    if re.search(r"\b(frame|screen)-right\b", route_text, re.I):
        if not re.search(r"\b(frame|screen)-right\b", negative, re.I):
            errors.append("opening frame has no lead room on the ruled frame-right route")
    if re.search(r"\b(frame|screen)-left\b", route_text, re.I):
        if not re.search(r"\b(frame|screen)-left\b", negative, re.I):
            errors.append("opening frame has no lead room on the ruled frame-left route")
    return {"ready": not errors, "errors": errors, "rulesVersion": RULES_VERSION}


def playable_stage_report(shot, cinematography):
    """Mechanical SEE gate for travel, depth, lead room and route objects."""
    cine = cinematography or {}
    errors = []
    geography = " ".join(_norm(item) for item in cine.get("geography") or [])
    negative = " ".join(_norm(item) for item in cine.get("negativeSpace") or [])
    camera = _norm(cine.get("lensAndCameraRelationship"))
    placements = ((cine.get("openingFrameLayout") or {}).get("placements") or [])
    travelling = bool(re.search(
        r"\b(chase|travel|route|flight|fly|barrel|pursu|toward frame|toward screen)\w*\b",
        _norm(shot.get("purpose")) + " " + geography, re.I))
    if travelling:
        if not re.search(r"\b(depth|ahead|corridor|lane|mid-depth|background)\b", geography, re.I):
            errors.append("opening geography does not provide visible depth ahead")
        if not re.search(r"\b(lead room|open|clear|reserve|lane|corridor)\b", negative, re.I):
            errors.append("opening frame does not reserve lead room for travel")
        for item in placements:
            facing = _norm(item.get("facing"))
            if re.search(r"\b(toward|faces?) (?:the )?camera\b|\bfront[- ]facing\b", facing, re.I):
                errors.append(
                    f"{item.get('character') or 'subject'} faces camera instead of travelling across or away")
    purpose = _norm(shot.get("purpose"))
    required = list(cine.get("requiredRouteElements") or [])
    if not required:
        for token in ("flower", "leaf", "branch", "door", "table", "vehicle", "prop"):
            if re.search(rf"\b{token}s?\b", purpose, re.I):
                required.append(token)
    missing = [item for item in required if not re.search(
        rf"\b{re.escape(str(item))}s?\b", geography, re.I)]
    if missing:
        errors.append("required route elements are absent from geography: " + ", ".join(missing))
    if travelling and re.search(r"\b(follow|chase|behind|drone|slightly late)\b", camera, re.I):
        if any(re.search(r"\b(toward|faces?) (?:the )?camera\b", _norm(item.get("facing")), re.I)
               for item in placements):
            errors.append("opening pose contradicts the ruled follow-camera relationship")
    return {"ready": not errors, "errors": errors, "rulesVersion": RULES_VERSION}


def generic_fix_review(rule_text):
    """Engineering rules cannot name production instances; Director data may."""
    text = _norm(rule_text)
    forbidden = re.findall(r"\bS\d+\.SH\w+\b|\bScene\s+\d+\b|\bShot\s+\d+\b", text, re.I)
    return {"ready": not forbidden, "errors": [
        "engineering fix names a shot or scene instead of the defect class"
    ] if forbidden else [], "matches": forbidden}
