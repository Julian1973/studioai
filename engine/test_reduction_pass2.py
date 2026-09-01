"""Proofs for the Pass 2 authority and duplication boundary."""
import pathlib

import cb_departments
import cb_seedance_transport


ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_runtime_role_map_has_one_owner_per_production_responsibility():
    owners = {
        "story": cb_departments.SKILLS["director"],
        "cinematic-shot-director": cb_departments.SKILLS["cinematography"],
        "keyframes": cb_departments.SKILLS["cinematography"],
        "seedance": cb_departments.SKILLS["animation"],
    }
    assert len({path.resolve() for path in owners.values()}) == 3
    assert owners["cinematic-shot-director"] == owners["keyframes"]
    assert all(path.exists() for path in owners.values())


def test_canon_compatibility_paths_are_links_to_one_physical_source():
    paths = [ROOT / "CRYSTAL_BEARS_LOCKED_CANON.md",
             ROOT / "engine/config/LOCKED_CANON.md"]
    paths.extend(ROOT.glob("skills/*/references/CRYSTAL_BEARS_LOCKED_CANON.md"))
    assert paths
    # T43: engine/config is itself a directory link into the project's canon/, so its
    # LOCKED_CANON.md is an alias through a linked parent rather than a link itself. The
    # invariant is the same either way: every compatibility path is an ALIAS (never a
    # second physical copy) and all of them resolve to the one source.
    assert all(path.resolve() != path.absolute() for path in paths)
    assert len({path.resolve() for path in paths}) == 1
    assert paths[0].resolve() == (ROOT / "projects/crystal-bears/canon/LOCKED_CANON.md").resolve()


def test_seedance_20_transport_is_explicit_legacy_comparison_only():
    assert cb_seedance_transport.MODE == "legacy_compare"
    assert cb_seedance_transport.COMPARISON_MODEL_ID == "fal-seedance-2.0"
