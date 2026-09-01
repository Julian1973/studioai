#!/usr/bin/env python3
"""T46/T47 — cast vocabulary, species/physiology and forbidden elements are PROJECT data.

The engine must (1) give the same answers for Crystal Bears it gave when the words lived in code,
and (2) give EMPTY vocabularies — never Crystal Bears words — for a project that declares none."""
import json
import pathlib
import re

import pytest

import paths as P
import project_laws as L

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def no_vocabulary(monkeypatch):
    monkeypatch.setattr(P, "CAST_VOCABULARY", None)
    monkeypatch.setattr(P, "FORBIDDEN_ELEMENTS", None)
    L.reload()
    yield
    L.reload()


def test_crystal_bears_vocabulary_matches_what_the_code_used_to_say():
    assert set(L.cast_names()) == {"Fuzzby", "Zenny", "Aida", "Sunny", "Luna", "Misty", "Amie", "Howey",
                                   "Keen", "Squeaky", "Bo"}
    assert L.pronunciation_overrides() == {"Aida": "Ada"}
    assert re.search(L.appearance_regex(), "a plump yellow bee", re.I)
    assert not re.search(L.appearance_regex(), "wings and antennae", re.I)      # deliberately excluded
    bans = L.proximity_bans()
    assert bans and bans[0]["term"] == "crystal" and set(bans[0]["characters"]) == {"Fuzzby", "Zenny"}
    assert L.keyframe_forbidden(True)[-1] == "pendants, necklaces, medallions or crystals on either bee"
    assert "pendants" not in " ".join(L.keyframe_forbidden(False))
    assert L.animation_negatives("winged")[0][0] == "no_crystals_on_bees"


def test_species_is_evidence_first_then_the_project_map():
    chars = json.load(open(P.CHARS, encoding="utf-8"))
    assert L.species_of("Fuzzby", chars["Fuzzby"]) == "bee"
    assert L.species_of("Squeaky", chars["Squeaky"]) == "dolphin"
    assert L.species_of("Bo", chars["Bo"]) == "squirrel"
    assert L.species_of("Keen", chars["Keen"]) == "bear"
    # a record with typed species wins outright; a record with prose is never overruled by the map
    assert L.species_of("Bo", {"species": "Otter"}) == "otter"
    assert L.species_of("Bo", {"size": "small squirrel child"}) == "squirrel"
    # a record with NO prose falls back to the project's map, then "character"
    assert L.species_of("Bo", {}) == "squirrel"
    assert L.species_of("Nobody", {}) == "character"


def test_wings_come_from_physiology_then_the_legacy_signals():
    chars = json.load(open(P.CHARS, encoding="utf-8"))
    assert L.has_wings("Fuzzby", chars["Fuzzby"]) and L.has_wings("Zenny", chars["Zenny"])
    assert not L.has_wings("Keen", chars["Keen"])
    assert L.has_wings("X", {"isBee": True})
    assert L.has_wings("Bo", chars["Bo"])   # legacy: 'bee wings' in Bo's `avoid` — recorded, not fixed (T61)


def test_a_project_without_a_vocabulary_gets_no_names_at_all(no_vocabulary):
    assert L.cast_names() == []
    assert L.names_regex() is None and L.appearance_regex() is None
    assert L.pronunciation_overrides() == {}
    assert L.proximity_bans() == []
    assert L.keyframe_forbidden(True) == []
    assert L.animation_negatives("winged") == []
    assert L.species_of("Anyone", {"size": "a tall heron"}) == "character"   # no fallback terms either
    assert L.review_question("performance", "generic?") == "generic?"


def test_no_cast_name_is_spelled_in_live_engine_code():
    """The words the engine used to know by heart may now appear only in project data, tests and
    dated history/comments — never in a live code path."""
    names = r"\b(Fuzzby|Zenny|Squeaky|Howey)\b"
    allow = {"engine/FULL_AUDIT_2026-07-11_findings.json"}
    offenders = []
    for f in list(ROOT.glob("engine/*.py")) + list(ROOT.glob("dailies/*.py")):
        rel = f.relative_to(ROOT).as_posix()
        if "/test_" in "/" + rel or rel in allow:
            continue
        in_doc = False
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            stripped = line.strip()
            if stripped.count('"""') % 2 == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#"):
                continue
            code = line.split("#", 1)[0]
            if re.search(names, code):
                offenders.append(f"{rel}:{n}: {stripped[:100]}")
    # Remaining live sites are Phase-3 tickets (T48 continuity rule, T49 emission checks, T50 prompts, T51 gaps).
    owned = ("cb_scene_package.py",            # T48 continuity carry rule
             "cb_emission_standard.py",         # T49 emission checks
             "cb_creative.py", "cb_director_chat.py",   # T50 system prompts
             "cb_canon.py",                     # T51 gap strings
             "cb_readback.py", "import_scene1_director_records.py", "recut_scene",  # T51 one-off scripts
             )
    unexplained = [o for o in offenders if not any(k in o for k in owned)]
    assert not unexplained, "cast names in live engine code:\n" + "\n".join(unexplained)
