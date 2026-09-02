"""T71 — the project's delivery FORMAT and the writer's own shot plan (2026-09-02).

Julian: "The Box Monsters will always be designed to be made up of 30 second shots and they
will be 7 mins so 15 shots" and, watching the first scene direction of a script that already
carried its own shot breakdown, "should it really be this long as it's a short script that is
already broken down."

Two facts live here, both read through the project — never a literal in the engine:

* `format_profile()` — `profile.json`'s optional `format` block (`paths.FORMAT`): the length of
  every production unit, the script style, the audience.  A project that declares none keeps the
  full Creative Room and the engine's natural 4-30s packing (Crystal Bears is byte-identical).

* `writer_shot_plan(pkg, scene_num)` — when the approved beat package came from a TREATMENT
  script (`SCENE 01: TITLE` / `Shot 01: Title` / production lines), the writer's shot headings
  are read straight out of the scene's own beats and become the production units: one unit per
  writer shot, in order, each carrying the beats whose events sit under that heading.  A scene
  with no shot headings gets no plan (None) and the Creative Room designs the sequence itself.

The fast path in `cb_creative.run_scene` uses both: the writer's breakdown IS the treatment, so
the three whole-scene treatments and the showrunner's selection are skipped; the shot conference
must return exactly the writer's units at the project's shot length; the adversarial review runs
once and may not restructure them.
"""
from __future__ import annotations

import re

import paths as P

SHOT_HEADING_RE = re.compile(r"^\s*Shot\s+(\d{1,3})\s*[:.\-–—]\s*(.+?)\s*$", re.IGNORECASE)


def format_profile():
    """The project's declared format (a `project_profile.FormatProfile`) or None."""
    return getattr(P, "FORMAT", None)


def shot_seconds():
    """The fixed production-unit length the project declares, or None (natural packing)."""
    fmt = format_profile()
    return int(fmt.shotSeconds) if fmt and fmt.shotSeconds else None


def uses_treatment_script():
    fmt = format_profile()
    return bool(fmt and fmt.scriptStyle == "treatment")


def _scene_beats(pkg, scene_num):
    beats = [b for b in (pkg.get("beats") or []) if str(b.get("sceneNumber")) == str(scene_num)]
    beats.sort(key=lambda b: int(
        (b.get("sourceEventRange") or {}).get("firstEventIndex", 0) or 0))
    return beats


def writer_shot_plan(pkg, scene_num):
    """The writer's own shots for one scene, read from the approved beat package.

    Returns a list of {shotNumber, title, beatIds, headingEventIndex} in script order, or None
    when the scene's beats carry no `Shot NN:` heading (a screenplay-style scene).  A beat is
    assigned to the last heading at or before its first event; a beat that begins before the
    scene's first heading (its production lines) belongs to the first shot.  A beat that
    contains more than one heading straddles the writer's shots: it stays whole, assigned to
    the first heading it contains, and the straddle is reported in `notes` so the Director's
    log says so — the engine never splits a signed source beat.
    """
    beats = _scene_beats(pkg, scene_num)
    if not beats:
        return None
    headings = []          # (eventIndex, shotNumber, title, beatCode)
    for b in beats:
        for cut in b.get("cuts") or []:
            text = cut.get("action") or ""
            m = SHOT_HEADING_RE.match(text)
            if m:
                headings.append((int(cut.get("sourceEventIndex") or 0), int(m.group(1)),
                                 m.group(2).strip(), b.get("beatCode")))
    if not headings:
        return None
    headings.sort()
    plan = [{"shotNumber": n, "title": title, "beatIds": [], "headingEventIndex": idx,
             "notes": []} for idx, n, title, _ in headings]
    for b in beats:
        inside = [i for i, h in enumerate(headings) if h[3] == b.get("beatCode")]
        if inside:
            # a beat that contains a heading STARTS that shot (its scene production lines or
            # the previous shot's Final Frame may sit before the heading inside the same beat)
            owner = inside[0]
        else:
            first = int((b.get("sourceEventRange") or {}).get("firstEventIndex", 0) or 0)
            owner = 0
            for i, (idx, *_rest) in enumerate(headings):
                if idx <= first:
                    owner = i
        plan[owner]["beatIds"].append(b.get("beatCode"))
        if len(inside) > 1:
            names = ", ".join(f"Shot {headings[i][1]:02d}" for i in inside)
            plan[owner]["notes"].append(
                f"{b.get('beatCode')} carries {names} in one source beat; it stays whole in "
                f"Shot {plan[owner]['shotNumber']:02d}")
    empty = [p for p in plan if not p["beatIds"]]
    for p in empty:
        p["notes"].append("no source beat begins under this heading; its material is carried "
                          "by the neighbouring unit")
    return [p for p in plan if p["beatIds"]]


def unit_shot_id(scene_num, shot_number):
    return f"S{scene_num}.SH{int(shot_number):02d}"


def format_contract_text(scene_num, plan, seconds):
    """The hard, literal contract the shot conference receives on the fast path."""
    lines = [
        f"PROJECT FORMAT CONTRACT (locked by the showrunner — not a creative choice): every "
        f"production unit in this project is EXACTLY {seconds} seconds. The writer has already "
        f"broken this scene into shots; those shots ARE the production units, in this order, "
        f"and nothing may merge, split, reorder or renumber them:",
    ]
    for item in plan:
        lines.append(
            f"  - {unit_shot_id(scene_num, item['shotNumber'])} \"{item['title']}\" carries "
            f"beatIds {item['beatIds']} · targetDurationSec {seconds}")
    lines.append(
        f"Return EXACTLY {len(plan)} CreativeShotCards with those shotIds and beatIds. "
        f"targetDurationSec is {seconds} on every card. Each unit opens on its own keyframe "
        f"(transitionType PLANNED_CUT). providerBoundaryReason is duration_limit on every "
        f"card except the last, which is scene_end. Fill the {seconds} seconds with honest, "
        f"living performance — the writer's action, the silent acting around it, the "
        f"environment's pressure, the landing — never with invented story events and never "
        f"with dead air. Author stagePlan (2-3 causal stages) and internalShotPlan (1-3 "
        f"motivated views) INSIDE each {seconds}-second unit.")
    return "\n".join(lines)


def enforce_units(shots, scene_num, plan, seconds):
    """Coerce the mechanical fields to the contract and report what the Director changed.

    shotId, targetDurationSec, transitionType and the provider boundary are the FORMAT's —
    they are set here regardless of what the model returned.  beatIds are the writer's; a
    unit whose beatIds differ from the plan is a real disagreement and is returned in
    `problems` for the one permitted repair call, never silently rewritten.
    """
    problems = []
    if len(shots) != len(plan):
        problems.append(f"the format needs exactly {len(plan)} unit(s) "
                        f"({', '.join(unit_shot_id(scene_num, p['shotNumber']) for p in plan)}); "
                        f"got {len(shots)}")
        return shots, problems
    for shot, item in zip(shots, plan):
        want_id = unit_shot_id(scene_num, item["shotNumber"])
        if list(shot.beatIds) != list(item["beatIds"]):
            problems.append(f"{want_id} must carry beatIds {item['beatIds']}; got {list(shot.beatIds)}")
        shot.shotId = want_id
        shot.targetDurationSec = seconds
        shot.transitionType = "PLANNED_CUT"
        shot.providerBoundaryReason = "duration_limit"
        if not shot.providerBoundaryExplanation:
            shot.providerBoundaryExplanation = (
                f"project format: every unit is a fixed {seconds}-second shot")
        if shot.performanceBudget and shot.performanceBudget.minimumHonestDurationSec > seconds:
            shot.performanceBudget.minimumHonestDurationSec = seconds
    shots[-1].providerBoundaryReason = "scene_end"
    return shots, problems


def writer_treatment(pkg, scene_num, plan, seconds):
    """The writer's own breakdown, restated as the ONE scene treatment (no model call).

    Every field is drawn from material the showrunner has already approved — the writer's shot
    headings and production lines, and Story & Direction's storyBeat / want / need / kidRead /
    adultRead / emotionalIntent for the scene's beats.  Nothing is invented: where the writer
    left a choice to the floor (camera, rhythm), the field says so and hands it to the shot
    conference INSIDE the fixed units.
    """
    beats = _scene_beats(pkg, scene_num)
    by_code = {b.get("beatCode"): b for b in beats}
    first = beats[0] if beats else {}
    scene = next((s for s in (pkg.get("scenes") or [])
                  if str(s.get("sceneNumber")) == str(scene_num)), {}) or {}
    meta = scene.get("meta") or {}
    location = first.get("location") or scene.get("location") or f"Scene {scene_num}"
    finals = []
    for b in beats:
        for cut in b.get("cuts") or []:
            text = cut.get("action") or ""
            if text.lower().startswith("final frame"):
                finals.append(text.split(":", 1)[-1].strip())
    shots_line = "; ".join(
        f"Shot {p['shotNumber']:02d} \"{p['title']}\" ({seconds}s): "
        + " ".join(str(by_code.get(c, {}).get("storyBeat") or "").strip() for c in p["beatIds"])
        for p in plan)
    joined = lambda key: " ".join(str(b.get(key) or "").strip() for b in beats if b.get(key))
    return {
        "name": f"The writer's breakdown — {location}",
        "audienceExperience": joined("kidRead") or joined("storyBeat"),
        "emotionalPointOfView": joined("emotionalIntent") or joined("need"),
        "comicOrDramaticMechanism": joined("want") + (" " + joined("need") if joined("need") else ""),
        "characterPerformanceStrategy": joined("adultRead") or joined("emotionalIntent"),
        "visualGrammar": (f"Fixed {seconds}-second shots, one keyframe each, as the writer "
                          f"broke them down: {shots_line}"),
        "cameraCharacterRelationship": ("Chosen by the shot conference inside each fixed unit; "
                                        "the writer names the frame, not the camera."),
        "movementVersusStillness": ("Each unit holds its full length: the written action, then "
                                    "the silent acting and landing the writer's Final Frame asks "
                                    "for — never dead air, never invented events."),
        "depthAndEnvironment": (meta.get("clean plate") or scene.get("location") or location),
        "rhythmAndEscalation": " -> ".join(p["title"] for p in plan),
        "cutPhilosophy": (f"A cut only at the writer's shot boundaries; every {seconds}-second "
                          "unit is one continuous provider request."),
        "openingImage": meta.get("character keyframe") or meta.get("clean plate") or
                        str(first.get("storyBeat") or "")[:300],
        "closingImage": finals[-1] if finals else str(beats[-1].get("storyBeat") or "")[:300],
        "cinematographerChallenge": ("Make each fixed unit feel written for its length: the "
                                     "camera earns the seconds the format gives it."),
    }


def writer_selection(treatment, plan):
    return {
        "selectedTreatment": treatment["name"],
        "combinedFrom": [],
        "governingAudienceExperience": treatment["audienceExperience"],
        "rationale": ("Project format: the script already carries the shot breakdown; the "
                      "writer's treatment is the scene's treatment (T71 fast path)."),
        "rejectionChecks": ("No alternative treatments were generated — the showrunner locked "
                            f"the format at {len(plan)} fixed unit(s) for this scene."),
    }
