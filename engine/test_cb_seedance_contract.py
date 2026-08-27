import pytest
from pydantic import ValidationError

import cb_seedance_contract as C


def _record():
    return {
        "schema_version": "seedance-extension/v1",
        "mode": "forward",
        "source_clip": "3.B1.S1_take2",
        "source_approved": True,
        "task_type": "extend",
        "already_true": ["Mum has completed the wave; do not repeat it."],
        "continuity_critical_subjects": ["Keen's Mum"],
        "identity_anchor_sets": [{
            "subject_id": "Keen's Mum",
            "anchors": ["approved face", "approved body proportions"],
        }],
        "lighting": "Warm morning window light from screen-left remains unchanged.",
        "audio_state": "Room tone continues; no unapproved speech.",
        "geography_master": None,
    }


def test_extension_contract_round_trips_canonical_snake_case():
    record = _record()
    assert C.dump_extension_contract(C.load_extension_contract(record)) == record


def test_extension_contract_accepts_existing_camel_case_input():
    record = _record()
    record["sourceClip"] = record.pop("source_clip")
    record["sourceApproved"] = record.pop("source_approved")
    contract = C.load_extension_contract(record)
    assert contract.sourceClip == "3.B1.S1_take2"
    assert C.dump_extension_contract(contract)["source_clip"] == "3.B1.S1_take2"


def test_extension_contract_rejects_unapproved_source():
    record = _record()
    record["source_approved"] = False
    with pytest.raises(ValidationError, match="explicitly approved"):
        C.load_extension_contract(record)


def test_extension_contract_rejects_more_than_three_anchors_per_subject():
    record = _record()
    record["identity_anchor_sets"][0]["anchors"] = ["a", "b", "c", "d"]
    with pytest.raises(ValidationError):
        C.load_extension_contract(record)


def test_bridge_requires_one_geography_master():
    record = _record()
    record["mode"] = "bridge"
    with pytest.raises(ValidationError, match="geography_master"):
        C.load_extension_contract(record)


def test_unknown_interchange_fields_are_rejected():
    record = _record()
    record["reference_strength"] = 0.8
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        C.load_extension_contract(record)
