from copy import deepcopy
from pathlib import Path
import subprocess
import pytest
from studio_director_handoff import source, errors, VERSION
from studio_request_evidence import digest
from studio_dynamic_state import resolve
from studio_prompt_director import run, request_snapshot, verify, review_legacy_envelope
from test_studio_prompt_director import review


def legacy():
    return {'shotId': 'old-shot', 'durationSec': 6,
            'storyIntentApproved': {'outerAction': 'Carry the object away.'},
            'storyboardInternalShotPlanApproved': [{'viewId': 'v1', 'storyAction': 'Carry the object away.'}]}


def test_see_preparation_has_no_dependency_on_its_uncreated_opening(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import studio_director_handoff as H
    import cb_llm
    shot, ledger = legacy(), {}
    original = deepcopy(shot)
    calls = []
    monkeypatch.setattr(H, 'refresh_previous_frame', lambda *a: calls.append('continuity'))
    monkeypatch.setattr(H, 'prepare_unit_scope', lambda *a: calls.append('scope'))
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('No opening pixels exist to inspect'))
    runtime = SimpleNamespace(load_pkg=lambda *a: ({}, tmp_path/'pkg.json'),
                              _shot=lambda *a: shot, _ledger=lambda *a: ledger)
    H.prepare_native(runtime, '2', 'old-shot', 'Ep3', stage='cinematography')
    assert calls == ['continuity', 'scope']
    assert shot == original and ledger == {}
    with pytest.raises(ValueError, match='selected opening image'):
        H.prepare_native(runtime, '2', 'old-shot', 'Ep3', stage='animation')


def test_real_legacy_shape_cannot_pass_with_zero_state_coverage():
    shot = legacy()
    final, report = run(request_snapshot('Carry away.', {'shot': shot}, [], {}, 6), lambda *a: review())
    assert 'WATCH plan adaptation unavailable' in ' '.join(report['errors'])
    assert report['providerCalled'] is False
    with pytest.raises(ValueError, match='BLOCKED'):
        verify(final, report)


def test_native_adapter_archives_absent_handoff_even_if_reviewer_says_ready(monkeypatch, tmp_path):
    import cb_llm, json
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **kw: review())
    env = {'prompt': 'Carry away.', 'durationSec': 6, 'references': [], 'audio': {'hash': 'approved'},
           'executionPlan': {'segments': [{'prompt': 'Carry away.', 'contract': {}}]}}
    with pytest.raises(ValueError, match='BLOCKED'):
        review_legacy_envelope(env, legacy(), {}, archive_folder=tmp_path)
    record = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert 'WATCH plan adaptation unavailable' in ' '.join(record['review']['errors'])
    assert record['review']['providerCalled'] is False
    assert record['snapshot']['audio'] == {'hash': 'approved'}


def test_see_ready_reviewer_cannot_override_missing_handoff():
    from studio_keyframe_director import snapshot, assess, require
    s = snapshot(legacy(), {}, {'path': 'test'}, [])
    r = assess(s, lambda *a: dict(verdict='READY', summary='fixture', camera='fixture', geography='fixture',
        pose='fixture', propsEffects='fixture', actionFeasibility='fixture', correctiveAction='none'))
    with pytest.raises(ValueError, match='current state'):
        require(s, r)


def test_see_review_distinguishes_opening_suitability_from_future_motion():
    from studio_keyframe_director import snapshot, assess, require
    s = snapshot({'shotId': 'fixture', 'durationSec': 6}, {}, {'path': 'synthetic'}, [])
    seen = []
    def reviewer(system, payload):
        seen.append((system, payload))
        return dict(verdict='UNVERIFIED', summary='Opening clearance cannot be judged.',
            camera='fixture', geography='unverified clearance', pose='fixture',
            propsEffects='fixture', actionFeasibility='unverified', correctiveAction='Review clearance')
    result = assess(s, reviewer)
    assert seen[0][1]['reviewScope']['observed'] == 'actual opening image suitability'
    assert 'READY means supported opening, never proven future motion.' in seen[0][0]
    # The clarified scope does not convert a reviewer failure into a pass.
    with pytest.raises(ValueError, match='UNVERIFIED'):
        require(s, result)


def test_changed_source_or_translation_invalidates_managed_handoff():
    s = legacy(); s['directorCard'] = {'views': [{'viewId': 'v1'}]}
    s['directorCardSource'] = {'version': VERSION, 'sourceHash': digest(source(s)), 'directionHash': digest(s['directorCard'])}
    assert not errors(s)
    for field, value in [('durationSec', 8), ('watchDirectorFeedbackApproved', 'Preserve changed background')]:
        changed = deepcopy(s); changed[field] = value
        assert errors(changed)
    s['directorCard']['views'][0]['viewId'] = 'different'
    assert errors(s)


def test_missing_legacy_fields_do_not_invent_a_plan():
    assert not errors({'shotId': 'archived-no-plan'})


def test_handoff_transport_schema_is_strict_without_open_dictionaries():
    from openai.lib._parsing._responses import type_to_text_format_param
    from studio_director_handoff import Preparation
    schema = type_to_text_format_param(Preparation)['schema']
    def walk(value):
        if isinstance(value, dict):
            if value.get('type') == 'object':
                assert value.get('additionalProperties') is False
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(schema)


@pytest.mark.parametrize('incomplete_existing', [False, True])
@pytest.mark.parametrize('pending_opening', [False, True])
def test_native_preparation_preserves_sources_and_reuses_current_handoff(monkeypatch, tmp_path, incomplete_existing, pending_opening):
    import cb_llm, hashlib
    from types import SimpleNamespace
    from studio_director_handoff import Preparation, prepare_native
    s = legacy()
    if incomplete_existing:
        s['directorCard'] = {'views':[{'viewId':'v1'}], 'stateChanges':[{'from':'A','to':'B'}]}
    s['storyIntentApproved']['narrativeFunction'] = 'An object leaves its perch.'
    s['storyboardInternalShotPlanApproved'][0].update(
        purpose='Observe the move', framingAndCamera='Wide', staging='At the perch',
        startState='Object at A', endState='Object at B', cutTo='')
    s['referenceSlots'] = {'@图1': 'opening keyframe'}
    s['watchDirectorFeedbackApproved'] = 'Preserve the accepted direction.'
    opening = tmp_path / 'opening.png'; opening.write_bytes(b'synthetic reference')
    ledger = {'keyframeApproval': {'path': str(opening), 'approved': True},
              'voiceApproval': {'path': 'approved.wav', 'hash': 'untouched'}, 'voPath': 'approved.wav'}
    original = deepcopy(s); approval = deepcopy(ledger['voiceApproval']); calls = []
    answer = Preparation.model_validate({'timedViews': [{'viewId': 'v1', 'atSec': 0, 'endSec': 6,
        'visibleEntities': ['object'], 'criticalStateEntities': ['object']}],
        'stateChanges': [{'entityId': 'object', 'atSec': 0, 'before': [],
                         'after': [{'field': 'location', 'value': 'A'}], 'cause': 'Approved opening'},
                        {'entityId': 'object', 'atSec': 3, 'before': [{'field': 'location', 'value': 'A'}],
                         'after': [{'field': 'location', 'value': 'B'}], 'cause': 'Approved carry'}],
        'openingObservedStates': [{'entityId': 'object', 'values': [{'field': 'location', 'value': 'A'}]}],
        'observationLimitations': 'Injected fixture, not visual recognition'})
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: calls.append(k['label']) or answer)
    runtime = SimpleNamespace(ROOT=tmp_path, load_pkg=lambda *a: ({}, tmp_path/'pkg.json'),
        _shot=lambda *a: s, _ledger=lambda *a: ledger, _save=lambda *a: None,
        _file_md5=lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest(),
        _sha256_file=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest())
    if pending_opening:
        ledger.pop('keyframeApproval')
        ledger['keyframeCandidate'] = {'path':str(opening)}
    options = {'opening_image':str(opening)} if pending_opening else {}
    prepare_native(runtime, '1', 'old-shot', 'test', lambda *a: None, **options)
    prepare_native(runtime, '1', 'old-shot', 'test', lambda *a: None, **options)
    if pending_opening:
        assert 'keyframeApproval' not in ledger
        assert ledger['keyframeCandidate']['path'] == str(opening)
    assert len(calls) == 1
    assert s['watchDirectorFeedbackApproved'] == 'Preserve the accepted direction.'
    assert ledger['voiceApproval'] == approval and ledger['voPath'] == 'approved.wav'
    assert s['storyboardInternalShotPlanApproved'] == original['storyboardInternalShotPlanApproved']
    assert s['directorCard']['views'][0]['action'] == original['storyboardInternalShotPlanApproved'][0]['storyAction']
    assert not errors(s)
    s['durationSec'] = 7
    assert errors(s)


def test_last_frame_is_actual_end_and_failed_extraction_preserves_previous(tmp_path):
    import cb_gen
    video = tmp_path / 'source.mkv'
    # Different frame per timestamp: a seek-to-near-end must not pass this test.
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=32x32:r=24:d=1',
                    '-c:v', 'ffv1', str(video)], check=True)
    expected = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
                    'select=eq(n\\,23)', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1'])
    output = tmp_path / 'last.png'; cb_gen.last_frame(video, out=str(output))
    from PIL import Image
    assert Image.open(output).convert('RGB').tobytes() == expected
    before = output.read_bytes()
    with pytest.raises(subprocess.CalledProcessError):
        cb_gen.last_frame(tmp_path / 'absent.mp4', out=str(output))
    assert output.read_bytes() == before


def test_animation_repairs_local_coverage_failure_once_with_exact_source(monkeypatch):
    import cb_departments as d
    context = {'shot': legacy()}; calls = []
    def once(ctx, images, **kw):
        calls.append(deepcopy(ctx))
        if len(calls) == 1:
            raise RuntimeError('Animation Director changed the approved number of motivated internal shots')
        return 'repaired'
    monkeypatch.setattr(d, '_prepare_animation_once', once)
    assert d.prepare_animation(context, [], log=lambda *a: None) == 'repaired'
    assert calls[1]['animationContractRepair']['orderedViewIds'] == ['v1']
    assert 'animationContractRepair' not in context
    calls.clear()
    def failure(*a, **kw):
        calls.append(1); raise RuntimeError('Animation Director weakened source')
    monkeypatch.setattr(d, '_prepare_animation_once', failure)
    with pytest.raises(RuntimeError): d.prepare_animation(context, [], log=lambda *a: None)
    assert len(calls) == 2


def test_see_and_watch_slot_numbers_do_not_share_state_authority():
    import cb_render as r
    shot = {'referenceSlots': {'@图1': 'opening keyframe', '@图2': 'Bee'},
            'keyframeReferenceSlots': {'@图1': 'Bee'},
            'referenceStateBindings': {'@图1': {'stateEvidenceHash': 'opening-bytes'},
                                       '@图2': {'stateEvidenceHash': 'bee-bytes'}}}
    assert r._reference_state_binding(shot, 'keyframeReferenceSlots', '@图1', 'Bee')['stateEvidenceHash'] == 'bee-bytes'
    assert r._reference_state_binding(shot, 'referenceSlots', '@图1', 'opening keyframe')['stateEvidenceHash'] == 'opening-bytes'


def test_see_resolves_actual_opening_observation_not_generation_slot():
    from studio_keyframe_director import snapshot
    shot = {'directorCard': {'stateChanges': [{'entityId': 'prop', 'atSec': 0,
        'afterValues': {'location': 'branch'}, 'cause': 'Opening'}],
        'views': [{'viewId': 'v1', 'atSec': 0, 'visibleEntities': ['prop'], 'criticalStateEntities': ['prop']}]}}
    candidate = {'depictedStates': {'prop': {'location': 'branch'}},
                 'stateScope': {'authority': 'opening_state', 'controlsDynamicState': True, 'startSec': 0, 'endSec': 0}}
    result = snapshot(shot, {}, candidate, [{'role': 'prop:comb'}])
    assert not result['dynamicStateResolution']['errors']
    assert result['dynamicStateResolution']['revisitChecks'][0]['currentStateEvidence'] == [1]


def test_dynamic_state_prose_does_not_create_false_spoken_line_markers():
    shot = {'directorCard': {'stateChanges': [{'entityId': 'object', 'atSec': 1,
        'afterValues': {'location': 'ground', 'owner': 'performer'}, 'cause': 'Visible transfer'}],
        'views': [{'viewId': 'v1', 'atSec': 2, 'visibleEntities': ['object']}]}}
    text = '\n'.join(resolve({'shot': shot}, [])['clauses'])
    assert 'location: ground' in text and 'owner: performer' in text
    assert '{' not in text and '}' not in text
def test_explicit_restore_of_typed_edit_after_rejection_preserves_other_inputs():
    from studio_director_handoff import animation_edit_base, digest, source
    from copy import deepcopy
    shot = {'shotId': 'S2.SH3', 'durationSec': 8}
    signature = {'shotContractHash': 'source', 'audioHash': 'approved-audio',
                 'referenceHashes': ['image'], 'directorFeedbackHash': 'before-rejection'}
    saved = {'output': {'audioContract': 'approved', 'shotPlan': ['accepted action']},
             'typedEditSourceHash': digest(source(shot)), 'inputSignature': signature}
    work = {'candidate': {'output': {'shotPlan': ['unwanted rewrite']}}, 'history': [saved]}
    current = {**signature, 'directorFeedbackHash': 'recorded-rejection'}
    assert animation_edit_base(work, shot, current, digest(saved['output'])) == saved
    assert animation_edit_base(work, shot, current) == work['candidate']
    for key, value in [('audioHash', 'different'), ('referenceHashes', ['replacement']),
                       ('shotContractHash', 'other-source')]:
        changed = {**current, key: value}
        with pytest.raises(ValueError, match='direct inputs changed'):
            animation_edit_base(work, shot, changed, digest(saved['output']))
    with pytest.raises(ValueError, match='authored source'):
        animation_edit_base(work, {**shot, 'durationSec': 12}, current, digest(saved['output']))


def test_unit_scope_revision_preserves_audio_assets_and_coverage():
    from studio_director_handoff import apply_scope_preparation
    s=legacy();s.update(generationUnitScope={'viewIds':['v1']},dialogueLines=[{'exactText':'Keep this.'}],
        keyframeApproval={'hash':'approved'},performanceContractApproved={'requiredLanding':'Parent scene ending'})
    before=deepcopy(s)
    updated, evidence=apply_scope_preparation(s, {'summary':'Scoped ending','corrections':[{
        'path':['performanceContractApproved','requiredLanding'],'before':'Parent scene ending',
        'after':'Object carried away.','sourceViewIds':['v1'],'reason':'This unit ends before the parent ending.'}]})
    assert s==before
    assert updated['dialogueLines']==before['dialogueLines']
    assert updated['keyframeApproval']==before['keyframeApproval']
    assert updated['storyboardInternalShotPlanApproved']==before['storyboardInternalShotPlanApproved']
    assert updated['performanceContractApproved']['requiredLanding']=='Object carried away.'


@pytest.mark.parametrize('path', [['dialogueLines','0','exactText'],['durationSec'],['keyframeApproval','hash']])
def test_unit_scope_cannot_edit_protected_production_inputs(path):
    from studio_director_handoff import apply_scope_preparation
    s=legacy();s['generationUnitScope']={'viewIds':['v1']}
    with pytest.raises(ValueError,match='direction field'):
        apply_scope_preparation(s,{'summary':'fixture','corrections':[{'path':path,'before':'x','after':'y','sourceViewIds':['v1'],'reason':'fixture'}]})


def test_unit_scope_cannot_use_another_units_view():
    from studio_director_handoff import apply_scope_preparation
    s=legacy();s['generationUnitScope']={'viewIds':['v1']}
    with pytest.raises(ValueError,match='coverage provenance'):
        apply_scope_preparation(s,{'summary':'fixture','corrections':[{'path':['storyIntentApproved','outerAction'],
            'before':'Carry the object away.','after':'An invented ending.','sourceViewIds':['v2'],'reason':'fixture'}]})


def test_scope_preparation_source_hash_rejects_changed_inputs():
    from studio_director_handoff import apply_scope_preparation,scope_source,digest
    s=legacy();s['generationUnitScope']={'viewIds':['v1']}
    signature=digest(scope_source(s))
    s['durationSec']=99
    with pytest.raises(ValueError,match='source changed'):
        apply_scope_preparation(s,{'summary':'empty','corrections':[]},expected_source_hash=signature)


def test_unit_scope_requires_clean_recheck_and_bounds_revisions(monkeypatch):
    import studio_director_handoff as h
    s=legacy();s['generationUnitScope']={'viewIds':['v1']}
    calls=[]
    monkeypatch.setattr(h,'_prepare_unit_scope_once',lambda *a: calls.append('review') or False)
    with pytest.raises(ValueError,match='three source revisions'):
        h.prepare_unit_scope(None,None,None,s,{},lambda *a:None)
    assert len(calls)==3
    calls.clear()
    monkeypatch.setattr(h,'_prepare_unit_scope_once',lambda *a: calls.append('review') or len(calls)==2)
    h.prepare_unit_scope(None,None,None,s,{},lambda *a:None)
    assert len(calls)==2


def test_unit_scope_does_not_change_predecessor_identity():
    from studio_director_handoff import apply_scope_preparation
    s=legacy();s['generationUnitScope']={'viewIds':['v1']}
    with pytest.raises(ValueError,match='transition identity'):
        apply_scope_preparation(s,{'summary':'fixture','corrections':[{
            'path':['shotTransition','stateSourceShotId'],'before':'S1.SH1','after':'S2.SH9',
            'sourceViewIds':['v1'],'reason':'fixture'}]})
