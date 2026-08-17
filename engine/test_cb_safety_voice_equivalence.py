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
