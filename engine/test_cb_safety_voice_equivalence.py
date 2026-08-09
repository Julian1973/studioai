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
