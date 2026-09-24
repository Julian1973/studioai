import cb_render


def test_reference_rename_with_identical_bytes_keeps_signature_current():
    old = {"cardHash": "same-card", "referenceHashes": {
        "Ep4_S4.SH2_final_frame.png": "same-frame",
        "CB_Fuzzby.jpeg": "same-character",
    }}
    new = {"cardHash": "same-card", "referenceHashes": {
        "Ep4_S4.SH2_c1_final_hash_v2.png": "same-frame",
        "CB_Fuzzby.jpeg": "same-character",
    }}

    assert cb_render._signature_diff(old, new) == []


def test_reference_rename_does_not_hide_changed_image_bytes():
    old = {"referenceHashes": {
        "Ep4_S4.SH2_final_frame.png": "old-frame",
        "CB_Fuzzby.jpeg": "same-character",
    }}
    new = {"referenceHashes": {
        "Ep4_S4.SH2_c1_final_hash_v2.png": "new-frame",
        "CB_Fuzzby.jpeg": "same-character",
    }}

    assert cb_render._signature_diff(old, new) == ["referenceHashes"]


def test_reference_content_swap_still_invalidates_even_when_hash_set_matches():
    old = {"referenceHashes": {"opening.png": "frame", "Fuzzby.jpeg": "character"}}
    new = {"referenceHashes": {"opening.png": "character", "Fuzzby.jpeg": "frame"}}

    assert cb_render._signature_diff(old, new) == ["referenceHashes"]
