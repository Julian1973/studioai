import cb_safety


def test_hear_selection_survives_audit_hash_change_when_provider_text_is_identical():
    recipes = [{"recipeId": "C", "performedText": "[casual] Nailed it."}]
    selected = {"candidateId": "run-C-1", "recipeId": "C", "compiledHash": "old-audit-hash"}
    candidates = [{
        "candidateId": "run-C-1", "recipeId": "C", "compiledHash": "old-audit-hash",
        "performedText": "[casual] Nailed it.",
    }]
    assert cb_safety.selected_voice_recipe(
        recipes, selected, candidates, "new-audit-hash") == recipes[0]


def test_hear_selection_does_not_survive_changed_provider_text():
    recipes = [{"recipeId": "C", "performedText": "[confident] Nailed it."}]
    selected = {"candidateId": "run-C-1", "recipeId": "C", "compiledHash": "old-audit-hash"}
    candidates = [{
        "candidateId": "run-C-1", "recipeId": "C", "compiledHash": "old-audit-hash",
        "performedText": "[casual] Nailed it.",
    }]
    assert cb_safety.selected_voice_recipe(
        recipes, selected, candidates, "new-audit-hash") is None


def test_hear_selection_can_use_accepted_track_text_when_old_candidate_is_not_visible():
    recipes = [{"recipeId": "line-1-primary", "performedText": "[gasps] Whoa!"}]
    selected = {
        "candidateId": "old-line-1-take-2",
        "recipeId": "line-1-primary",
        "compiledHash": "old-audit-hash",
        "performedText": "[gasps] Whoa!",
    }
    # The live audition carousel may now contain only the final line's candidates.
    candidates = [{
        "candidateId": "line-3-take-1",
        "recipeId": "line-3-primary",
        "performedText": "Nice to meet you too.",
    }]
    assert cb_safety.selected_voice_recipe(
        recipes, selected, candidates, "new-audit-hash") == recipes[0]


def test_shot_can_require_isolated_voice_assembly_without_faking_a_chorus():
    shot = {"voiceAssemblyMode": "isolated-lines"}
    lines = [
        {"voiceTreatment": "single_voice", "text": "Do it again!"},
        {"voiceTreatment": "single_voice", "text": "3, 2, 1..."},
    ]

    assert cb_safety.uses_isolated_voice_assembly(shot, lines) is True


def test_normal_multi_speaker_exchange_keeps_contextual_dialogue_route():
    lines = [
        {"voiceTreatment": "single_voice", "text": "Hello."},
        {"voiceTreatment": "single_voice", "text": "Hi."},
    ]

    assert cb_safety.uses_isolated_voice_assembly({}, lines) is False


def test_authored_action_gaps_use_isolated_lines_to_preserve_timing():
    shot = {
        "dialogueLines": [
            {"startSec": 3.0, "endSec": 5.8},
            {"startSec": 8.2, "endSec": 10.4},
            {"startSec": 15.0, "endSec": 20.8},
            {"startSec": 21.4, "endSec": 22.4},
        ]
    }
    lines = [
        {"voiceTreatment": "single_voice", "text": "First."},
        {"voiceTreatment": "single_voice", "text": "Second."},
        {"voiceTreatment": "single_voice", "text": "Third."},
        {"voiceTreatment": "single_voice", "text": "Fourth."},
    ]

    assert cb_safety.uses_isolated_voice_assembly(shot, lines) is True


def test_tightly_timed_exchange_keeps_contextual_dialogue_route():
    shot = {
        "dialogueLines": [
            {"startSec": 1.0, "endSec": 2.0},
            {"startSec": 2.4, "endSec": 3.4},
        ]
    }
    lines = [
        {"voiceTreatment": "single_voice", "text": "Hello."},
        {"voiceTreatment": "single_voice", "text": "Hi."},
    ]

    assert cb_safety.uses_isolated_voice_assembly(shot, lines) is False
