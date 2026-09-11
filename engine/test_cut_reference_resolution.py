import hashlib
import cb_render as render


def test_cut_final_frame_does_not_use_new_opening(tmp_path, monkeypatch):
    previous = tmp_path / 'previous.png'
    previous.write_bytes(b'previous')
    opening = tmp_path / 'opening.png'
    opening.write_bytes(b'new opening')
    pkg = {'continuityLedger': [{'shotId': 'a', 'status': 'approved',
            'harvestFrame': str(previous), 'approval': {
                'harvestHash': hashlib.sha256(previous.read_bytes()).hexdigest()}}]}
    monkeypatch.setattr(render, 'load_pkg', lambda *a: (pkg, None))
    monkeypatch.setattr(render, '_reference_path_is_approved', lambda p: True)
    shot = {'shotId': 'b', 'shotTransition': {'type': 'cut', 'stateSourceShotId': 'a'}}
    actual = render._slot_path_for_role('previous shot final frame', str(opening),
                                       '1', 'Ep3', {}, shot, 'animation')
    assert actual == str(previous)
    assert actual != str(opening)


def test_cut_state_and_continuation_opening_have_distinct_roles():
    plan = [{'slot': '@图1', 'role': 'opening keyframe'},
            {'slot': '@图2', 'role': 'previous shot final frame'}]
    cut = render._animation_reference_contract(plan, {'shotTransition': {'type': 'cut'}})
    assert [x['role'] for x in cut] == ['opening_frame', 'continuity_state']
    relay = render._animation_reference_contract(plan[1:], {})
    assert relay[0]['role'] == 'opening_frame'


def test_short_dialogue_does_not_match_inside_an_action_word():
    from types import SimpleNamespace as NS
    import cb_departments as d
    shot = {'dialogueLines': [{'speaker': 'A', 'exactText': 'Ow!'}],
            'storyboardInternalShotPlanApproved': [
                {'storyAction': 'Runs toward the tower.'},
                {'storyAction': 'One contact causes “Ow!” and a recoil.'}]}
    views = [NS(dialogueLineIndexes=[], dialogueDirections=[]),
             NS(dialogueLineIndexes=[1], dialogueDirections=[])]
    direction = NS(shotPlan=views, creativeTranslation=None)
    d.carry_approved_gag_clock_text(shot, direction)
    assert views[0].dialogueLineIndexes == []
    assert views[1].dialogueLineIndexes == [1]
