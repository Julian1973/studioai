from copy import deepcopy
from pathlib import Path
import cb_engine_rules as rules
import studio_prompt_director as director
from test_studio_seedance_execution import compact_source


def test_measured_audio_moves_dialogue_owner_without_false_r15(compact_source):
    estimated=deepcopy(compact_source['authorities']['shot'])
    measured=deepcopy(estimated)
    measured['dialogueLines'][0].update(startSec=4.2,endSec=5.2)
    prompt=director.compile_native_source(measured,compact_source['references'],compact_source['audio'])
    old=rules.action_unit_report(estimated,director.native_rule_inputs(estimated,prompt),prompt)
    current=rules.action_unit_report(measured,director.native_rule_inputs(measured,prompt),prompt)
    assert any('R15' in error for error in old['errors'])
    assert not any('R15' in error for error in current['errors'])
    # Still reject a genuinely missing written line; the guard was not disabled.
    broken=prompt.replace('{Here you are.}','{Different words.}')
    report=rules.action_unit_report(measured,director.native_rule_inputs(measured,broken),broken)
    assert any('R15' in error for error in report['errors'])


def test_fire_and_readiness_both_validate_projected_authority():
    root=Path(__file__).parent
    render=(root/'cb_render.py').read_text()
    assert 'rule_shot = watch_shot(shot, led)' in render
    assert 'native_rule_inputs(rule_shot, resolved_prompt)' in render
    assert '_require_engine_rules(pkg, rule_shot, animation_direction' in render
    facade=(root/'cb_studio_director.py').read_text()
    assert 'native_rule_inputs(source, prompt), cinematography={})' in facade


def test_cross_cut_dialogue_keeps_one_line_and_carries_visible_mouth_timing(compact_source):
    shot=deepcopy(compact_source['authorities']['shot'])
    shot['dialogueLines'][0].update(startSec=3.5,endSec=5.2)
    shot['directorCard']['views'][0]['visibleEntities']=[]
    shot['directorCard']['views'][1]['visibleEntities']=['char.Mira']
    before=deepcopy(shot)
    prompt=director.compile_native_source(shot,compact_source['references'],compact_source['audio'])
    assert prompt.count('{Here you are.}') == 1
    assert '3.5–4s in this view' in prompt
    assert 'The speaker remains offscreen' in prompt
    assert '4–5.2s in this view' in prompt
    assert 'Match visible speech articulation to @Audio1.' in prompt
    assert 'Do not restart or repeat the line.' in prompt
    assert shot == before
    report=rules.action_unit_report(shot,director.native_rule_inputs(shot,prompt),prompt)
    assert not any('R15' in error for error in report['errors'])


def test_directed_checkpoints_and_sound_ownership_reach_provider_without_rewriting(compact_source):
    shot=deepcopy(compact_source['authorities']['shot'])
    card=shot['directorCard']
    card['stateChanges']=[dict(atSec=5.4, cause='After the line ends, the drop hits the lantern.')]
    card['soundOwnership']='Quiet clearing ambience, then a small lantern tap.'
    before=deepcopy(shot)
    prompt=director.compile_native_source(shot,compact_source['references'],compact_source['audio'])
    first, second=prompt.split('Shot 2:',1)
    assert 'Directed checkpoint at 5.4s' not in first
    assert 'Directed checkpoint at 5.4s: After the line ends, the drop hits the lantern.' in second
    assert card['soundOwnership'] in prompt
    assert shot == before


def test_watch_rejects_direct_checkpoint_before_measured_line_end():
    from studio_watch_plan import _validate_causal_audio_checkpoints
    shot = {'dialogueLines': [dict(speaker='Sunny', exactText='Just watch!', endSec=29.5)]}
    card = {'stateChanges': [dict(entityId='character:Sunny', atSec=15.5,
        cause="After Sunny finishes 'Just watch!', she turns to the wall.")]}
    import pytest
    with pytest.raises(ValueError, match='DIRECT_AUDIO_TIMING_CONFLICT'):
        _validate_causal_audio_checkpoints(shot, card)
    card['stateChanges'][0]['atSec'] = 29.5
    _validate_causal_audio_checkpoints(shot, card)
