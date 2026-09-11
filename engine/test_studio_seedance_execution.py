"""Structural/route qualification only. All review verdicts are injected; no network."""
from copy import deepcopy
import hashlib
import json
import re
import socket

import pytest
import cb_departments as D
import studio_prompt_director as PD
import studio_seedance_execution as E
from studio_character_roles import audit
from test_studio_storyboard_prompt import example
from test_studio_prompt_director import review


@pytest.fixture
def compact_source(tmp_path, monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))
    shot, direction = example()
    shot['directorCard']['views'][0]['visibleEntities'] = ['character:Mira', 'character:Oren']
    shot['directorCard']['views'][1]['visibleEntities'] = ['character:Oren']
    direction['shotPlan'][1]['compositionLightAndMaterials'] += ' Mira stays offscreen.'
    refs = []
    for i, name in enumerate(('opening keyframe', 'Oren', 'scene plate', 'Mira'), 1):
        path = tmp_path / f'{i}.jpg'
        path.write_bytes(name.encode())
        refs.append(dict(slot=f'@图{i}', role=name, path=str(path),
                         hash=hashlib.sha256(path.read_bytes()).hexdigest()))
    return PD.request_snapshot(D.compile_animation_provider_prompt(shot, direction),
        dict(shot=shot, specialist=direction), refs, dict(path='fixture.wav', hash='immutable'), 8)


def test_native_compiler_uses_declared_visibility_not_mentions_or_offscreen_speech(compact_source):
    from studio_storyboard_prompt import subjects_for_view
    view = {'causalAction': 'Mira stays offscreen while Oren accepts the cup.'}
    assert subjects_for_view([('@图4', 'Mira'), ('@图2', 'Oren')], view, ['Mira'],
        visible_entities=['character:Oren']) == 'Subjects: Oren from @图2.'
    assert 'Subjects: Oren from @图2.' in compact_source['prompt'].split('Shot 2:', 1)[1]
    assert 'Subjects: Oren from @图2; Mira' not in compact_source['prompt'].split('Shot 2:', 1)[1]


def test_provider_excludes_internal_dump_and_compacts_repeated_anchors(compact_source):
    compact_source['prompt'] += '\n[CURRENT DYNAMIC STATE]\nobject:cup: owner=Oren.\n[REFERENCE STATE AUTHORITY]\nraw expiry record'
    before = deepcopy(compact_source)
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    assert not E.INTERNAL_HEADINGS.intersection(dict(E.sections(prompt)))
    assert 'object:cup: owner=Oren' in evidence['sourcePrompt']
    assert prompt.count('Oren identity/design only') == 1
    assert prompt.count('Mira identity/design only') == 1
    assert '[CHARACTER ROLE INTEGRITY]' not in prompt
    assert compact_source == before


def test_per_view_cast_and_local_role_locks_do_not_activate_absent_character(compact_source):
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    first, second = dict(E.sections(prompt))['TIMED ACTION'].split('Shot 2:', 1)
    assert 'Visible cast: Mira @图4; Oren @图2 only.' in first
    assert 'Keep identities and actions distinct.' in first
    assert 'Visible cast: Oren @图2 only.' in second
    assert 'Mira' not in second
    assert evidence['omittedPassiveReminders']


def test_global_witness_footer_cannot_contaminate_final_single_character_view(compact_source):
    compact_source['prompt'] = compact_source['prompt'].replace(
        'End state: Oren holds the single cup against his chest.',
        'End state: Oren holds the single cup against his chest.\nWitness staging: Mira waits elsewhere.')
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    assert 'Witness staging:' not in prompt
    assert 'Witness staging: Mira waits elsewhere.' in evidence['sourcePrompt']
    assert evidence['legacyVisualProse'].startswith('ignored')


def test_joint_offscreen_cause_is_preserved_and_unknown_visibility_not_guessed(compact_source):
    compact_source['authorities']['specialist']['shotPlan'][1]['causalAction'] = 'Oren cradles the cup because Mira warns him offscreen.'
    prompt, _ = E.compile_prompt(compact_source, audit(compact_source))
    assert 'because Mira @图4 warns him offscreen.' in prompt
    del compact_source['authorities']['shot']['directorCard']['views'][1]['visibleEntities']
    prompt, _ = E.compile_prompt(compact_source, audit(compact_source))
    assert 'because Mira @图4 warns him offscreen.' in prompt
    assert 'Visible cast:' not in dict(E.sections(prompt))['TIMED ACTION'].split('Shot 2:', 1)[1]


def test_required_state_and_immutable_audio_survive_real_compile_and_seal(compact_source, monkeypatch, tmp_path):
    import cb_llm
    calls = []
    def reviewer(system, text, schema, **kwargs):
        calls.append(json.loads(text))
        return review()
    monkeypatch.setattr(cb_llm, 'structured_with_repair', reviewer)
    before = deepcopy(compact_source)
    env = dict(prompt=before['prompt'], references=before['references'], audio=before['audio'], durationSec=8,
               executionPlan={'segments': [dict(prompt=before['prompt'], contract={})]})
    PD.review_legacy_envelope(env, before['authorities']['shot'], before['authorities']['specialist'], archive_folder=tmp_path/'reviews')
    PD.verify_legacy_envelope(env)
    prompt = env['prompt']
    assert prompt == env['executionPlan']['segments'][0]['prompt'] == next(call['prompt'] for call in calls if 'prompt' in call)
    assert next(call for call in calls if 'providerPromptCompilation' in call)['providerPromptCompilation']['applied']
    assert prompt.startswith('[PURPOSE]')
    assert prompt.index('[TIMED ACTION]') < prompt.index('[REFERENCE AUTHORITY]') < prompt.index('[Audio]')
    assert 'Mira @图4 extends the cup and Oren @图2 reaches to accept it.' in prompt
    assert 'Oren @图2 holds the cup; Mira @图4 has released it.' in prompt
    for heading in E.AUDIO_HEADINGS:
        assert dict(E.sections(prompt))[heading] == dict(E.sections(before['prompt']))[heading]
    assert re.findall(r'^Spoken action:.*$', prompt, re.M) == re.findall(r'^Spoken action:.*$', before['prompt'], re.M)
    assert prompt.count('{Here you are.}') == 1
    continuity = dict(E.sections(prompt))['MUST PRESERVE']
    assert 'fixed set geography' in continuity
    assert 'Character and movable-prop positions follow the directed actions and end states.' in continuity
    assert 'Preserve the approved look, world positions' not in continuity
    assert env['audio'] == before['audio'] and env['references'] == before['references']
    record = json.loads(next((tmp_path/'reviews').glob('*.json')).read_text())
    assert record['snapshot']['prompt'] == prompt
    assert record['review']['providerPromptCompilation']['sourcePrompt']
    import cb_prompt_lab
    result = cb_prompt_lab.analyze_seedance_prompt_contract(prompt, task_mode='reference-to-video',
        reference_contract=before['authorities']['specialist']['referenceContract'], duration_sec=8,
        dialogue_lines=before['authorities']['shot']['dialogueLines'])
    for check in result['checks']:
        if check['code'] in ('goal', 'global-settings', 'consistency', 'reference-roles', 'stages', 'stage-direction'):
            assert check['status'] == 'pass', check


@pytest.mark.parametrize('words,status', [(1400,'PASS'),(1600,'PASS'),(1601,'WARN'),(2200,'WARN'),(2201,'BLOCKED')])
def test_configured_word_budget_never_truncates_content(words, status):
    prompt = 'word ' * words
    assert E.budget(prompt, {})['status'] == status
    assert len(prompt.split()) == words


def test_budget_exception_is_bound_to_source_and_exact_prompt():
    prompt = 'word ' * 2300
    auth = {'shot': {'shotId':'S4.SH3', 'revision':4, 'promptBudgetException':True}}
    assert E.budget(prompt, auth)['status'] == 'BLOCKED'
    record = dict(id='explicit-1', authorisedBy='Test human', shotId='S4.SH3',
        sourceHash=E.digest(auth['shot']), promptHash=E.digest(prompt), maxWords=2300)
    auth['promptBudgetAuthorisations'] = [record]
    assert E.budget(prompt, auth)['exceptionId'] == 'explicit-1'
    auth['shot']['revision'] = 5
    assert E.budget(prompt, auth)['status'] == 'BLOCKED'


def test_early_budget_block_is_durable_and_never_calls_reviewer(compact_source, monkeypatch, tmp_path):
    import cb_llm
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('No model call'))
    compact_source['authorities']['specialist']['shotPlan'][1]['causalAction'] += ' word' * 2300
    prompt = compact_source['prompt']
    env = dict(prompt=prompt, references=compact_source['references'], audio=compact_source['audio'], durationSec=8,
        executionPlan={'segments':[dict(prompt=prompt,contract={})]})
    with pytest.raises(ValueError, match='PROVIDER PROMPT COMPILATION'):
        PD.review_legacy_envelope(env, compact_source['authorities']['shot'], compact_source['authorities']['specialist'], archive_folder=tmp_path/'reports')
    record=json.loads(next((tmp_path/'reports').glob('*.json')).read_text()); report=record['review']
    for key in ('version','sourceHash','inputHash','payloadHash','correctiveAction','summary'):
        assert report[key]
    assert report['providerCalled'] is False and report['spendOccurred'] is False
    assert record['snapshot']['references'] == compact_source['references']
    assert report['providerPromptCompilation']['budget']['status'] == 'BLOCKED'


@pytest.mark.parametrize('change', ['audio','metadata','budget'])
def test_review_cannot_reintroduce_dump_change_audio_or_exceed_budget(compact_source, change):
    prompt, evidence = E.compile_prompt(compact_source, audit(compact_source))
    if change == 'audio': prompt=prompt.replace('No narration', 'Some narration', 1)
    elif change == 'metadata': prompt+='\n[CURRENT DYNAMIC STATE]\nRaw internal ledger'
    else: prompt+='\n'+'word '*2300
    _, faults=E.final_check({**compact_source,'prompt':prompt}, evidence)
    assert faults


@pytest.mark.parametrize('prefix', ['character.', 'char:'])
def test_dotted_character_entity_ids_preserve_visible_cast(compact_source, prefix):
    for view in compact_source['authorities']['shot']['directorCard']['views']:
        view['visibleEntities']=[x.replace('character:',prefix) for x in view['visibleEntities']]
    prompt,_=E.compile_prompt(compact_source,audit(compact_source))
    assert 'Visible cast: Mira @图4; Oren @图2 only.' in prompt
    assert 'no characters only' not in prompt


@pytest.mark.parametrize('entity', ['Aida', 'char:aida', 'character:aida', 'character.aida'])
def test_native_known_name_and_lowercase_entity_alias_bind_actual_identity(compact_source, entity):
    # Native S2 uses char:aida while its registered cast/identity uses Aida.
    snapshot = json.loads(json.dumps(compact_source).replace('Oren', 'Aida'))
    snapshot['authorities']['shot']['directorCard']['views'][1]['visibleEntities'] = [
        entity, 'prop:Mira', 'env:pool_surface', 'Unregistered']
    prompt, evidence = E.compile_prompt(snapshot, audit(snapshot))
    second = dict(E.sections(prompt))['TIMED ACTION'].split('Shot 2:', 1)[1]
    assert 'Visible cast: Aida @图2 only.' in second
    assert evidence['views'][1]['cast'] == 'Visible cast: Aida @图2 only.'
    assert 'Visible cast: no characters' not in second
    assert 'Mira' not in second


@pytest.mark.parametrize('entities', [[], ['prop:Oren', 'env:pool_surface', 'Unregistered']])
def test_explicit_view_without_registered_cast_has_unambiguous_grammar(compact_source, entities):
    compact_source['authorities']['shot']['directorCard']['views'][1]['visibleEntities'] = entities
    prompt, _ = E.compile_prompt(compact_source, audit(compact_source))
    second = dict(E.sections(prompt))['TIMED ACTION'].split('Shot 2:', 1)[1]
    assert 'Visible cast: no characters.' in second
    assert 'no characters only' not in second


def test_no_dialogue_compaction_keeps_authored_sound_policy(compact_source):
    compact_source['authorities']['shot']['dialogueLines']=[]
    compact_source['audio']={}
    for view in compact_source['authorities']['specialist']['shotPlan']:
        view['dialogueLineIndexes'] = []
    compact_source['prompt']='[Audio]\nNo dialogue. Generate woodland ambience and a single wooden impact.\n'
    prompt,_=E.compile_prompt(compact_source,audit(compact_source))
    assert '[Audio]\nNo dialogue. Generate woodland ambience and a single wooden impact.' in prompt


def test_native_subjects_accept_both_declared_entity_id_spellings():
    from studio_storyboard_prompt import subjects_for_view
    assert subjects_for_view([('@图1','Mira'),('@图2','Oren')], {},
        visible_entities=['character.Mira']) == 'Subjects: Mira from @图1.'


def test_compact_identity_reference_keeps_authored_nonborrow_traits(compact_source):
    roles=audit(compact_source)
    roles['characters'][0]['traits']={'distinguishingFeatures':['silver hair'],
        'mustNotBorrow':["another actor's freckles",'a red scarf']}
    prompt,_=E.compile_prompt(compact_source,roles)
    assert "must not borrow: another actor's freckles; a red scarf." in prompt
