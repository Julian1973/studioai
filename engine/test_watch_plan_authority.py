"""Real typed compiler/reviewer/seal routes; reviewers injected, network forbidden."""
from copy import deepcopy
import json
import re
import socket

import pytest
import studio_prompt_director as PD
import studio_seedance_execution as E
import studio_watch_plan as P
from studio_character_roles import audit
from test_studio_seedance_execution import compact_source
from test_studio_prompt_director import review


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))


def correction(snapshot, *, value='Oren cradles the cup with both hands.'):
    prepared = snapshot if snapshot.get('watchPlan') else P.prepare_plan(snapshot)
    return dict(expectedPlanHash=P.digest(prepared['watchPlan']),
        path='/specialist/shotPlan/1/causalAction',
        expected=prepared['authorities']['specialist']['shotPlan'][1]['causalAction'], value=value,
        sourcePath='/shot/approvedExecutionCorrection',
        sourceHash=P.digest(prepared['authorities']['shot']['approvedExecutionCorrection']),
        reason='Use the current approved hand position in the request-local execution plan')


def corrected_source(source):
    source['authorities']['shot']['approvedExecutionCorrection'] = 'Oren cradles the cup with both hands.'
    return source


def test_visual_provider_prose_has_zero_compilation_authority(compact_source):
    expected, _ = E.compile_prompt(compact_source, audit(compact_source))
    stale = deepcopy(compact_source)
    stale['prompt'] = stale['prompt'].replace('Oren cradles the cup.', 'Mira destroys the cup.')
    stale['prompt'] += '\n[Invented screenplay]\nThis historical JSON must not be emitted: {"action":"Fly"}'
    actual, evidence = E.compile_prompt(stale, audit(stale))
    assert actual == expected
    assert 'Fly' not in actual and 'destroys' not in actual
    assert evidence['format'] == 'typed-plan-only'
    assert evidence['legacyVisualProse'].startswith('ignored')


def test_typed_execution_refinement_survives_broad_source_card(compact_source):
    view = compact_source['authorities']['shot']['directorCard']['views'][0]
    view.update(framing='Medium framing.', action='Pass the cup.', performance='Hesitation.', endState='Cup passed.')
    prompt, _ = E.compile_prompt(compact_source, audit(compact_source))
    assert 'Hold a medium two-shot at eye height.' in prompt
    assert 'Mira @图4 hesitates, then relaxes her fingers.' in prompt


def test_correction_updates_typed_origin_and_preserves_source_audio_refs_contract(compact_source):
    source = corrected_source(compact_source)
    original = deepcopy(source)
    revised, receipt = P.correct_plan(source, [correction(source)])
    assert revised['authorities']['specialist']['shotPlan'][1]['causalAction'] == revised['watchPlan']['views'][1]['action']
    assert revised['authorities']['shot'] == source['authorities']['shot']
    assert source == original
    for key in ('audio', 'references', 'duration', 'settings'):
        assert revised[key] == original[key]
    assert receipt['originalPlanHash'] != receipt['revisedPlanHash']
    assert receipt['approvedSourceMutated'] is False
    prompt, evidence = E.compile_prompt(revised, audit(revised))
    assert 'Oren @图2 cradles the cup with both hands.' in prompt
    assert all(block in prompt for block in revised['watchPlan']['audioBlocks'])
    assert not E.final_check({**revised, 'prompt': prompt}, evidence)[1]


@pytest.mark.parametrize('phase', ['plan', 'payload'])
def test_review_correction_repeats_plan_review_and_compiles_sealed_exact_output(compact_source, phase):
    source = corrected_source(compact_source)
    seen = []
    def worker(system, data):
        seen.append(deepcopy(data))
        result = review()
        target = len(seen) == (1 if phase == 'plan' else 2)
        if target:
            result['planCorrections'] = [correction(data)]
        return result
    final, report = PD.run(source, worker)
    PD.verify(final, report)
    assert 'prompt' not in seen[0]
    plan_inputs = [item for item in seen if 'prompt' not in item]
    assert len(plan_inputs) == 2
    assert plan_inputs[-1]['watchPlan']['views'][1]['action'].endswith('both hands.')
    assert seen[-1]['prompt'] == final['prompt']
    recompiled, evidence = E.compile_prompt(final, audit(final))
    assert recompiled == final['prompt']
    assert evidence['planHash'] == report['providerPromptCompilation']['planHash']
    assert len(report['planRevisions']) == 1
    assert final['authorities']['shot'] == source['authorities']['shot']
    assert report['trace'][0]['status'] == 'revised-typed-plan'


def test_legacy_envelope_archives_revised_plan_and_exact_submitted_text(compact_source, tmp_path, monkeypatch):
    import cb_llm
    source = corrected_source(compact_source)
    seen = []
    def worker(system, text, schema, **options):
        data = json.loads(text)
        seen.append(data)
        result = review()
        if len(seen) == 2:
            result['planCorrections'] = [correction(data)]
        return result
    monkeypatch.setattr(cb_llm, 'structured_with_repair', worker)
    env = dict(prompt=source['prompt'], references=source['references'], audio=source['audio'], durationSec=8,
        executionPlan={'segments': [dict(prompt=source['prompt'], contract={})]})
    original = deepcopy(source)
    PD.review_legacy_envelope(env, source['authorities']['shot'], source['authorities']['specialist'], archive_folder=tmp_path)
    PD.verify_legacy_envelope(env)
    segment = env['executionPlan']['segments'][0]
    record = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert record['snapshot'] == segment['promptDirectorSnapshot']
    assert record['snapshot']['watchPlan']['views'][1]['action'].endswith('both hands.')
    assert record['snapshot']['authorities']['specialist']['shotPlan'][1]['causalAction'].endswith('both hands.')
    assert record['snapshot']['prompt'] == seen[-1]['prompt'] == env['prompt']
    assert source == original


@pytest.mark.parametrize('change', ['plan_hash', 'source_hash', 'source_path', 'expected', 'approved_path', 'audio_path', 'section', 'tag'])
def test_stale_or_protected_typed_corrections_are_refused(compact_source, change):
    source = corrected_source(compact_source)
    edit = correction(source)
    if change == 'plan_hash': edit['expectedPlanHash'] = 'stale'
    elif change == 'source_hash': edit['sourceHash'] = 'stale'
    elif change == 'source_path': edit['sourcePath'] = '/shot/missing'
    elif change == 'expected': edit['expected'] = 'old guessed text'
    elif change == 'approved_path': edit['path'] = '/shot/directorCard/views/1/action'
    elif change == 'audio_path': edit['path'] = '/specialist/audioContract'
    elif change == 'section': edit['value'] = '[Audio]\nSynthesize new dialogue'
    elif change == 'tag': edit['value'] += ' @Audio1'
    with pytest.raises(ValueError):
        P.correct_plan(source, [edit])


@pytest.mark.parametrize('field', ['authorities', 'references', 'audio', 'duration', 'settings', 'watchPlan'])
def test_plan_binding_detects_each_immutable_input_change(compact_source, field):
    prepared = P.prepare_plan(compact_source)
    if field == 'authorities': prepared[field]['shot']['revision'] = 999
    elif field == 'references': prepared[field].reverse()
    elif field == 'audio': prepared[field]['hash'] = 'new'
    elif field == 'duration': prepared[field] = 12
    elif field == 'settings': prepared[field]['resolution'] = 'new'
    else: prepared[field]['views'][0]['action'] = 'Invented action.'
    with pytest.raises(ValueError): P.prepare_plan(prepared)


def test_prompt_string_edit_cannot_become_ready(compact_source):
    calls = []
    def worker(system, data):
        calls.append(data)
        result = review()
        if 'prompt' in data:
            result['edits'] = [dict(old='Oren @图2 cradles the cup.', new='Oren flies away.', source='old style', reason='not a typed correction')]
        return result
    final, report = PD.run(compact_source, worker)
    assert report['verdict'].startswith('BLOCKED')
    assert 'flies away' not in final['prompt']
    with pytest.raises(ValueError): PD.verify(final, report)


def test_unsupported_prose_route_is_explicit_and_cannot_call_review_or_fire():
    source = PD.request_snapshot('A legacy string', {'shot': {'shotId': 'old'}}, [], {}, 8)
    final, report = PD.run(source, lambda *a: pytest.fail('No semantic call for unsupported plan'))
    assert report['verdict'] == 'BLOCKED: PROVIDER PROMPT COMPILATION'
    assert report['providerPromptCompilation']['compatibility'] == 'blocked; no legacy prose bypass'
    with pytest.raises(ValueError): PD.verify(final, report)


def test_provider_prompt_mutation_cannot_be_resealed_by_unchanged_plan(compact_source):
    final, report = PD.run(compact_source, lambda *a: review())
    changed = deepcopy(final)
    changed['prompt'] = changed['prompt'].replace('cradles the cup', 'drops the cup')
    assert any('deterministic compiler' in fault for fault in E.final_check(changed, report['providerPromptCompilation'])[1])


def test_project_director_card_adapts_without_native_specialist(compact_source):
    source = deepcopy(compact_source)
    shot = source['authorities']['shot']
    directed = source['authorities'].pop('specialist')
    shot['directorCard']['audienceFocus'] = directed['dramaticBeat']
    for view, row in zip(shot['directorCard']['views'], directed['shotPlan']):
        view.update(framing=row['framingLensAndCamera'], action=row['causalAction'],
            performance=row['observablePerformance'], staging=row['compositionLightAndMaterials'],
            endState=row['landingImage'], entry=row['transitionType'])
    final, report = PD.run(source, lambda *a: review())
    PD.verify(final, report)
    assert final['watchPlan']['compatibility'] == 'project-director-card'
    assert final['prompt'].count('{Here you are.}') == 1
    assert final['audio'] == source['audio']


def test_audio_embedded_dialogue_is_kept_once_without_moving_its_protected_bytes(compact_source):
    source = deepcopy(compact_source)
    cue = re.findall(r'^Spoken action:.*$', source['prompt'], re.M)[0]
    source['prompt'] = source['prompt'].replace('[Audio]\n', '[Audio]\n' + cue + '\n')
    prepared = P.prepare_plan(source)
    assert prepared['watchPlan']['dialogueOccurrences'][0]['placement'] == 'audio-block'
    final, report = PD.run(source, lambda *a: review())
    PD.verify(final, report)
    assert final['prompt'].count('{Here you are.}') == 1
    assert cue in dict(E.sections(final['prompt']))['Audio']
    assert all(block in final['prompt'] for block in prepared['watchPlan']['audioBlocks'])


def test_two_segment_scope_rebases_audio_and_preserves_exact_parent_truth(compact_source, tmp_path, monkeypatch):
    import cb_llm
    source = deepcopy(compact_source)
    shot, specialist = source['authorities']['shot'], source['authorities']['specialist']
    shot['dialogueLines'][0]['dialogueOccurrenceId'] = 'approved-line-1'
    shot['dialogueLines'].append(dict(speaker='Oren', exactText='I have it.', startSec=5, endSec=6, dialogueOccurrenceId='approved-line-2'))
    specialist['shotPlan'][1]['dialogueLineIndexes'] = [2]
    stage = specialist['stagePlan'][0]
    specialist['stagePlan'] = [{**stage, 'stageNumber':1, 'startSec':0, 'endSec':4},
        {**stage, 'stageNumber':2, 'startSec':4, 'endSec':8, 'initialOrCarriedState':'Oren holds the cup.', 'observableEndState':'Oren holds the cup against his chest.'}]
    shot['directorCard']['stateChanges'] = [
        dict(entityId='object:cup', subject='cup', actionId='opening-cup', atSec=0, timing='0s', before='Mira holds the cup.', after='Mira holds the cup.', beforeValues={'holder':'Mira'}, afterValues={'holder':'Mira'}, cause='Approved opening state.'),
        dict(entityId='object:cup', subject='cup', actionId='single-transfer', atSec=3, timing='3s', before='Mira holds the cup.', after='Oren holds the cup.', beforeValues={'holder':'Mira'}, afterValues={'holder':'Oren'}, cause='Mira hands the cup to Oren.') ]
    original = deepcopy(source)
    seen = []
    def worker(system, text, schema, **kwargs):
        seen.append(json.loads(text)); return review()
    monkeypatch.setattr(cb_llm, 'structured_with_repair', worker)
    segments = []
    for i, (start, end) in enumerate(((0,4), (4,8))):
        segments.append(dict(segmentIndex=i+1, globalStartSec=start, globalEndSec=end, durationSec=4,
            stageNumbers=[i+1], dialogueLineIndexes=[i], sourceViewIds=[shot['directorCard']['views'][i]['viewId']],
            prompt=source['prompt'], contract={}, references=source['references'],
            audio={**source['audio'], 'sourcePath':'master.wav', 'sourceMd5':'master-immutable', 'sourceStartSec':start, 'sourceEndSec':end}))
    env = dict(prompt=source['prompt'], durationSec=8, references=source['references'], audio=source['audio'], executionPlan={'segments':segments})
    PD.review_legacy_envelope(env, shot, specialist, archive_folder=tmp_path)
    PD.verify_legacy_envelope(env)
    assert source == original
    assert len(seen) == 4 and all('prompt' not in seen[i] for i in (0,2))
    records = [json.loads(path.read_text()) for path in tmp_path.glob('*.json')]
    assert len(records) == 2
    for index, segment in enumerate(env['executionPlan']['segments']):
        snapshot = segment['promptDirectorSnapshot']
        parent = snapshot['authorities']['sourceUnit']
        assert parent['shot']['dialogueLines'] == original['authorities']['shot']['dialogueLines']
        assert parent['shotHash'] == P.digest(parent['shot'])
        assert snapshot['watchPlan']['views'][0]['startSec'] == 0
        assert snapshot['watchPlan']['views'][0]['endSec'] == 4
        assert len(snapshot['watchPlan']['views']) == 1
        assert snapshot['authorities']['shot']['dialogueLines'][0]['dialogueOccurrenceId'] == f'approved-line-{index+1}'
        assert segment['prompt'] == E.compile_prompt(snapshot, audit(snapshot))[0]
        assert any(record['snapshot'] == snapshot for record in records)
    first, second = env['executionPlan']['segments']
    assert first['prompt'].count('{Here you are.}') == 1 and '{I have it.}' not in first['prompt']
    assert second['prompt'].count('{I have it.}') == 1 and '{Here you are.}' not in second['prompt']
    assert 'Oren: 1–2s.' in second['prompt']
    assert second['audio']['sourceStartSec'] == 4 and second['audio']['sourceEndSec'] == 8
    entry = second['promptDirectorSnapshot']['authorities']['shot']['directorCard']['stateChanges'][0]
    assert entry['atSec'] == 0 and entry['beforeValues'] == entry['afterValues'] == {'holder':'Oren'}
    assert 'do not replay' in entry['cause']
    assert entry['actionId'] != 'single-transfer'


@pytest.mark.parametrize('failure', ['view-boundary', 'audio-slice', 'speech-boundary'])
def test_invalid_segment_scope_is_durable_before_any_reviewer(compact_source, tmp_path, monkeypatch, failure):
    import cb_llm
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('No semantic call'))
    source = deepcopy(compact_source)
    segment = dict(segmentIndex=1, globalStartSec=0, globalEndSec=4, durationSec=4,
        dialogueLineIndexes=[0], prompt=source['prompt'], contract={}, audio=source['audio'])
    if failure == 'view-boundary': segment.update(globalEndSec=3, durationSec=3)
    elif failure == 'speech-boundary': source['authorities']['shot']['dialogueLines'][0].update(startSec=3, endSec=5)
    env = dict(prompt=source['prompt'], durationSec=8, references=source['references'], audio=source['audio'], executionPlan={'segments':[segment]})
    with pytest.raises(ValueError, match='PROVIDER PROMPT COMPILATION'):
        PD.review_legacy_envelope(env, source['authorities']['shot'], source['authorities']['specialist'], archive_folder=tmp_path)
    record = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert record['review']['providerPromptCompilation']['compatibility'] == 'blocked segment projection'
    assert record['review']['providerCalled'] is False


def test_project_measurements_bind_repeated_words_by_occurrence_and_recording():
    from studio_prompt_director import project_authorities
    shot = dict(id='S1.SH1', dialogue=[{'speaker':'A', 'text':'Yes.'}, {'speaker':'B', 'text':'Yes.'}],
        outcomes={'hear':dict(id='approved-hear',status='approved',files=[{'hash':'audio-hash'}],
            voiceTiming={'audioSha256':'audio-hash', 'lines':[dict(inputIndex=0,startSec=.2,endSec=.7),dict(inputIndex=1,startSec=1.2,endSec=1.8)]})})
    original = deepcopy(shot)
    context = dict(project={'id':'example'}, sourceHash='script-hash', bible='Project canon')
    authority = project_authorities(context, shot, 'A: Yes.\nB: Yes.')
    lines = authority['shot']['dialogueLines']
    assert [(line['speaker'],line['exactText'],line['startSec']) for line in lines] == [('A','Yes.',.2),('B','Yes.',1.2)]
    assert len({line['dialogueOccurrenceId'] for line in lines}) == 2
    assert shot == original
    shot['outcomes']['hear']['voiceTiming']['lines'].reverse()
    with pytest.raises(ValueError, match='input order'): project_authorities(context,shot,'same words')
