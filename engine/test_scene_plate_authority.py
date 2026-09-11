from studio_scene_plate_authority import clause, REVIEW_RULE

def test_opening_preserves_set_without_freezing_story_state():
    text=clause('@图3', {})
    assert '@图3: exact approved location authority' in text
    assert 'opening background' in text
    assert 'never restore a removed object' in text

def test_cut_preserves_world_not_screen_composition():
    text=clause('@图5', {'shotTransition':{'type':'cut'}})
    assert 'Reframe only for the authored camera view' in text
    assert 'never mirror or redesign' in text
    assert 'opening background' not in text

def test_see_reviewer_uses_same_authority():
    import studio_keyframe_director as director
    assert REVIEW_RULE in director.SYSTEM
    assert 'UNVERIFIED' in REVIEW_RULE
