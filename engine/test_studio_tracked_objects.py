import pytest

import studio_tracked_objects as objects


def honeycomb_shot(**overrides):
    shot = {
        "shotId": "S1.SH2B",
        "durationSec": 26,
        "objectLifecycleLocks": [{
            "objectId": "H01",
            "description": "original single whole golden honeycomb",
            "stateIn": "original honeycomb removed from far-tree support and carried by Keen",
            "stateDuring": "same original honeycomb is released by one tail-slap recoil, then bounces and rolls",
            "stateOut": "same original honeycomb lands beside Fuzzby near the catapult; original branch remains empty",
            "prohibitedSubstitutions": [
                "hair comb", "generic comb", "honeycomb-shaped house", "duplicate honeycomb",
                "partial piece", "new substitute honeycomb",
            ],
            "sourceReferences": ["SH2A final state", "scene plate", "prop reference"],
        }],
    }
    shot.update(overrides)
    return shot


def test_legacy_lifecycle_lock_becomes_tracked_object():
    registry = objects.registry_for_shot(honeycomb_shot())
    assert registry[0]["id"] == "H01"
    assert "honeycomb" in registry[0]["name"]
    assert registry[0]["count"] == 1


def test_good_prompt_passes_with_stable_hash():
    shot = honeycomb_shot()
    prompt = (
        "Keen carries the original single whole golden honeycomb. The original branch stays empty. "
        "The original honeycomb bounces and rolls to Fuzzby near the catapult. "
        "No duplicate honeycomb, no hair comb, no honeycomb-shaped house, no partial piece, no new substitute honeycomb."
    )
    first = objects.audit_prompt(prompt, shot)
    second = objects.audit_prompt(prompt, shot)
    assert first["status"] == "READY"
    assert first["objectResolutionHash"] == second["objectResolutionHash"]


@pytest.mark.parametrize('text', [
    'Keen runs with a comb.',
    'Keen carries the whole honeycomb to Fuzzby.',
    'Keen carries the original single whole golden honeycomb.',
])
def test_prose_requires_semantic_review_instead_of_keyword_verdict(text):
    report = objects.audit_prompt(text, honeycomb_shot())
    assert report['status'] == 'READY'  # Registry structure only, not Fire or visual approval.
    assert any('unverified' in row['reason'] for row in report['warnings'])


def test_invalid_count_blocks_for_any_object_name():
    report = objects.audit_prompt('Carry the parcel.', {'trackedProductionObjects':[
        {'id':'P1','name':'parcel','count':0}]})
    assert report['status'] == 'BLOCKED'


def test_negative_substitution_terms_do_not_count_as_positive_failures():
    report = objects.audit_prompt(
        "Keen carries the original single whole golden honeycomb. No duplicate honeycomb, no hair comb, no honeycomb-shaped house.",
        honeycomb_shot(),
    )
    assert not any("duplicate or substitute" in error["reason"] for error in report["errors"])
    assert not any("generic comb" in error["reason"] for error in report["errors"])


def test_provider_clauses_are_concise_not_raw_json():
    clauses = objects.provider_clauses(honeycomb_shot())
    assert clauses
    assert clauses[0].startswith("H01")
    assert "{" not in clauses[0]
    assert "No substitution:" in clauses[0]


def test_apply_provider_clauses_adds_missing_authority():
    prompt = objects.apply_provider_clauses("Keen runs across the creek.", honeycomb_shot())
    assert "[Tracked production objects]" in prompt
    assert "H01 original single whole golden honeycomb" in prompt


def test_recompile_replaces_stale_lifecycle_and_preserves_audio():
    source = ('[Audio]\nKeep @Audio1 unchanged.\n\n'
              '[Tracked production objects]\n- H01 original single whole golden honeycomb: still on tree.\n\n'
              '[Ending]\nPreserve the wink.')
    result = objects.apply_provider_clauses(source, honeycomb_shot())
    assert 'still on tree' not in result
    assert 'lands beside Fuzzby near the catapult' in result
    assert '[Audio]\nKeep @Audio1 unchanged.' in result
    assert '[Ending]\nPreserve the wink.' in result
    assert objects.apply_provider_clauses(result, honeycomb_shot()) == result


def test_declared_plural_count_is_not_compiled_as_one_object():
    shot = {'trackedProductionObjects': [{'id': 'P1', 'name': 'matching parcels', 'count': 2}]}
    result = objects.apply_provider_clauses('', shot)
    assert 'total count of 2' in result
    assert 'same object' not in result


def test_removed_registry_does_not_leave_old_compiled_objects():
    result = objects.apply_provider_clauses(
        '[Purpose]\nQuiet pause.\n\n[Tracked production objects]\n- OLD object', {})
    assert result == '[Purpose]\nQuiet pause.'


def test_dict_lifecycle_locks_keep_object_id():
    shot = {
        "shotId": "S1.SH2B",
        "objectLifecycleLocks": {
            "object:honeycomb.whole": {
                "description": "original single whole golden honeycomb",
                "stateIn": "already carried by Keen",
                "prohibited": ["hair comb", "honeycomb-shaped house", "duplicate honeycomb"],
                "sourceRefs": ["SH2A"],
            }
        },
    }
    registry = objects.registry_for_shot(shot)
    assert registry[0]["id"] == "object:honeycomb.whole"
    assert "hair comb" in registry[0]["prohibitedSubstitutions"]


def test_explicit_h01_deduplicates_legacy_honeycomb_lock():
    shot = honeycomb_shot(trackedProductionObjects=[{
        "id": "H01",
        "name": "original single whole golden honeycomb",
        "description": "original honeycomb",
        "aliases": ["honeycomb", "comb"],
        "legacyIds": ["object:honeycomb.whole"],
        "sourceReferences": ["approved state"],
    }])
    shot["objectLifecycleLocks"] = {
        "object:honeycomb.whole": {"description": "original single whole golden honeycomb"}
    }
    registry = objects.registry_for_shot(shot)
    assert [item["id"] for item in registry].count("H01") == 1
    assert all(item["id"] != "object:honeycomb.whole" for item in registry)
