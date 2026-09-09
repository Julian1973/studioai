import copy

from studio_scene_handoff import sound_instruction, join_advisories
from studio_workflow import handoff
from studio_editing import fields, impact
from test_studio_production import shot, setup


def test_sound_only_edit_preserves_picture_and_voice():
    old = fields(shot(1, 'Hero: Hello.'))
    old['outcomes'] = {k: {'status': 'approved', 'id': k} for k in ['see', 'hear', 'request', 'watch']}
    new = fields(old)
    new['soundHandoff'] = {'entry': 'Continue the quiet motif', 'exit': 'Leave garden ambience',
                           'carrySound': 'wind', 'entryEnergy': 1, 'exitEnergy': 0, 'intentionalContrast': ''}
    assert impact(old, new)['reset'] == ['request', 'watch']
    assert impact(old, new)['preserved'] == ['see', 'hear']
    assert old['outcomes']['watch']['status'] == 'approved'


def test_actual_handoff_prompt_and_fingerprint_include_sound_but_not_in_still():
    s = fields(shot(2, 'Hero: Hello.')); s['transition'] = 'continuation'
    before = handoff(s, 'watch', [])
    s['soundHandoff'] = {'entry': 'Carry the low pulse', 'exit': 'Let the pulse settle'}
    watch = handoff(s, 'watch', [])
    assert 'Carry the low pulse' in watch['soundInstruction']
    assert 'do not restart the cue' in watch['soundInstruction']
    assert watch['fingerprint'] != before['fingerprint']
    still = handoff(s, 'see', [])
    assert 'soundInstruction' not in still
    assert 'camera height and movement' in still['visualHandoff']


def test_high_energy_join_is_advisory_even_when_deliberate():
    a = {'id': 'a', 'soundHandoff': {'exitEnergy': 5}}
    b = {'id': 'b', 'soundHandoff': {'entryEnergy': 4}}
    original = copy.deepcopy((a, b))
    assert join_advisories(a, b)[0]['severity'] == 'warning'
    assert (a, b) == original
    b['soundHandoff']['intentionalContrast'] = 'Smash cut into the chase'
    assert 'Smash cut' in join_advisories(a, b)[0]['message']
    assert join_advisories({}, {}) == []


def test_exact_audio_never_adds_music_even_with_authored_sound_exit():
    instruction = sound_instruction({'exit': 'Add a big musical sting'}, exact_audio=True)
    assert 'Add a big musical sting' not in instruction
    assert 'add no new sound' in instruction



def test_board_warning_and_post_brief_bind_the_actual_approved_pair(setup):
    from test_studio_review import finish
    from studio_post_contract import project_brief
    p, ws, _, _ = setup
    finish(p)
    with ws.db() as db:
        state = p._load(db, 'first', '1')
        state['shots'][0]['soundHandoff'] = {'exitEnergy': 5}
        state['shots'][1]['soundHandoff'] = {'entryEnergy': 4}
        p._save(db, 'first', '1', state)
    current = p.snapshot('first', '1')
    warnings = current['review']['inspections']['S1.SH2']['issues']
    assert any(i['code'] == 'music_join_review' and i['severity'] == 'warning' for i in warnings)
    assert current['review']['summary']['assemblyReady']
    brief = project_brief(p, ws.context('first', '1'), current['state'], current['review']['timeline'])
    join = brief['joins'][0]
    assert join['fromWatch']['id'] == current['state']['shots'][0]['outcomes']['watch']['id']
    assert join['toWatch']['files'] == current['state']['shots'][1]['outcomes']['watch']['files']
    assert join['inspectionStatus'] == 'unverified'
    assert join['advisories'][0]['code'] == 'music_join_review'
