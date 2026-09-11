"""WATCH feedback must not invalidate an unchanged SEE opening."""
import ast
from pathlib import Path


def test_watch_feedback_only_invalidates_animation_contract():
    tree = ast.parse(Path(__file__).with_name('cb_safety.py').read_text())
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
              and n.name == 'stage_shot_contract')
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<actual stage_shot_contract>', 'exec'), scope)
    contract = scope['stage_shot_contract']
    shot = {'shotId': 'S2.SH1', 'openingPose': 'seated at pool',
            'referenceSlots': [{'role': 'scene plate', 'path': 'pool.png'}]}
    retake = {**shot, 'watchDirectorFeedbackApproved': 'Use the approved party vision'}
    assert contract(shot, 'cinematography') == contract(retake, 'cinematography')
    assert contract(shot, 'review-keyframe') == contract(retake, 'review-keyframe')
    assert contract(shot, 'animation') != contract(retake, 'animation')
    for changes in ({'openingPose': 'standing'},
                    {'referenceSlots': [{'role': 'scene plate', 'path': 'new.png'}]}):
        assert contract(shot, 'cinematography') != contract({**shot, **changes}, 'cinematography')
