from copy import deepcopy
import pytest
from studio_dynamic_state import resolve
from studio_prompt_director import run,verify,request_snapshot
from test_studio_prompt_director import review


def source(field='location',before='A',after='B',critical=False):
    return {'shot':{'directorCard':{'stateChanges':[{'entityId':'object','atSec':2,'beforeValues':{field:before},'afterValues':{field:after},'cause':'authored event'}],
            'views':[{'viewId':'return','atSec':4,'visibleEntities':['object'],'criticalStateEntities':['object'] if critical else []}]}}}

def refs(field='location',value='A'):
    return [{'role':'opening frame','depictedStates':{'object':{field:value}}}]

def test_native_named_turnaround_has_identity_authority_without_role_keywords(tmp_path):
    from studio_dynamic_state import scope
    import hashlib
    path = tmp_path / 'Ada.jpeg'
    path.write_bytes(b'synthetic Ada identity')
    for metadata in ({'intactTurnaround': True}, {'sameCharacterGroup': 'cast-id'}):
        result = scope({'role': 'Ada', **metadata})
        assert result['authority'] == 'identity_only'
        assert not result['controlsDynamicState']
        final, report = run(request_snapshot('Keep Ada in place.', {},
                            [{'role': 'Ada', 'path': str(path), 'hash': hashlib.sha256(path.read_bytes()).hexdigest(), **metadata}], {}, 5), lambda *a: review())
        verify(final, report)
        assert 'Reference 1: identity/design only;' in final['prompt']
        assert 'Reference 1: declared continuation state' not in final['prompt']

def test_finished_locomotion_persists_into_dialogue_view():
    data = {'shot': {'directorCard': {
        'stateChanges': [
            {'entityId': 'actor', 'atSec': 0, 'afterValues': {'locomotion': 'running'}, 'cause': 'chase'},
            {'entityId': 'actor', 'atSec': 10, 'beforeValues': {'locomotion': 'running'},
             'afterValues': {'locomotion': 'standing after recoil'}, 'cause': 'arrival and contact'}],
        'views': [{'viewId': 'reply', 'atSec': 15, 'visibleEntities': ['actor']}]}}}
    result = resolve(data, [])
    assert not result['errors']
    assert result['revisitChecks'][0]['requiredState']['locomotion'] == 'standing after recoil'

@pytest.mark.parametrize('field,before,after',[('attachment','attached','detached'),('condition','upright','collapsed'),('holder','A','B'),('mark','clean','mud')])
def test_changed_state_persists_on_revisit(field,before,after):
    out=resolve(source(field,before,after),refs(field,before))
    check=out['revisitChecks'][0]
    assert check['requiredState']=={field:after} and check['revisit']
    assert check['obsoleteReferences']==[1] and not check['unresolvedResetRisk']
    assert out['referencePackage'][0]['stateScope']['endSec']==0

def test_critical_current_reference_conflict_blocks_even_when_reviewer_says_ready():
    rs=refs()
    rs[0]['stateScope']={'authority':'current_dynamic_state','controlsDynamicState':True,'startSec':0,'endSec':5}
    snap=request_snapshot('Show the return.',source(critical=True),rs,{},5)
    final,report=run(snap,lambda *a:review())
    assert report['verdict'].startswith('BLOCKED')
    with pytest.raises(ValueError):verify(final,report)

def test_current_evidence_resolves_reset_and_is_sealed():
    rs=refs()+[{'role':'current frame','depictedStates':{'object':{'location':'B'}},'stateScope':{'authority':'current_dynamic_state','controlsDynamicState':True,'startSec':2,'endSec':5}}]
    final,report=run(request_snapshot('Show the return.',source(critical=True),rs,{},5),lambda *a:review())
    verify(final,report)
    assert report['dynamicStateResolution']['revisitChecks'][0]['currentStateEvidence']==[2]
    assert 'location: B' in final['prompt']
    amended=deepcopy(final);amended['authorities']['shot']['directorCard']['stateChanges'][0]['afterValues']['location']='C'
    with pytest.raises(ValueError,match='STALE'):verify(amended,report)


def test_partial_opening_observation_does_not_invent_a_conflict_or_a_full_pass():
    data = {'shot': {'directorCard': {
        'stateChanges': [{'entityId': 'mechanism', 'atSec': 0,
            'afterValues': {'position': 'bench', 'springTension': 'loaded'},
            'cause': 'Approved initial state; concealed tension is intended, not observed.'}],
        'views': [{'viewId': 'opening', 'atSec': 0, 'visibleEntities': ['mechanism'],
                   'criticalStateEntities': ['mechanism']}]}}}
    references = [{'role': 'opening frame', 'depictedStates': {'mechanism': {'position': 'bench'}}}]
    out = resolve(data, references)
    assert not out['errors']
    check = out['revisitChecks'][0]
    assert check['currentStateEvidence'] == []
    assert check['obsoleteReferences'] == []
    assert check['partialCurrentStateEvidence'] == [
        {'reference': 1, 'observedFields': ['position'], 'unverifiedFields': ['springTension']}]
    assert any('no observation for springTension' in note for note in out['unverified'])
    # A real observed mismatch still blocks despite other properties being unknown.
    references[0]['depictedStates']['mechanism']['position'] = 'floor'
    assert any('contradicts' in error for error in resolve(data, references)['errors'])
    references[0]['depictedStates']['mechanism'] = {}
    assert any('without observed state evidence' in error for error in resolve(data, references)['errors'])

def test_explicit_time_jump_uses_declared_entry_not_prior_state():
    data=source();v=data['shot']['directorCard']['views'][0];v.update(storyRelationship='time_jump',stateAtEntry={'object':{'location':'C'}})
    out=resolve(data,refs());assert out['revisitChecks'][0]['requiredState']=={'location':'C'}

def test_identity_kept_without_authority_and_unknown_is_unverified():
    r=[{'role':'character turnaround'}];out=resolve(source(),r)
    assert out['referencePackage'][0]['stateScope']['authority']=='identity_only'
    assert not out['referencePackage'][0]['stateScope']['controlsDynamicState']
    assert out['revisitChecks'][0]['unknownReferences']==[1]
    assert r==[{'role':'character turnaround'}]

def test_detachment_includes_empty_support_as_separate_state():
    data=source('attachment','attached','detached');card=data['shot']['directorCard']
    card['stateChanges'].append(dict(entityId='support',atSec=2,beforeValues={'occupied':True},afterValues={'occupied':False},cause='same detachment event'))
    card['views'][0]['visibleEntities'].append('support')
    out=resolve(data,refs('attachment','attached'))
    assert out['revisitChecks'][1]['requiredState']=={'occupied':False}


def test_native_binding_survives_renumbering_and_seals(monkeypatch,tmp_path):
    import cb_render as render
    path=tmp_path/'reference.png';path.write_bytes(b'fixture, not visual evidence')
    monkeypatch.setattr(render,'_characters_cfg',lambda:{})
    monkeypatch.setattr(render,'_with_required_prop_slots',lambda slots,*a:slots)
    shot={'referenceSlots':{'@图4':'scene plate'},'referenceStateBindings':{'@图4':{
        'stateScope':{'authority':'fixed_geography','controlsDynamicState':False},
        'stateEvidenceHash':render._file_md5(str(path)), 'depictedStates':{'object':{'location':'A'}}}}}
    records=render._reference_records(shot,[str(path)])
    assert records[0]['sourceSlot']=='@图4' and records[0]['slot']=='@图1'
    assert records[0]['depictedStates']['object']['location']=='A'
    final,report=run(request_snapshot('Return.',source(critical=True),records,{},5),lambda *a:review())
    verify(final,report)
    assert report['dynamicStateResolution']['revisitChecks'][0]['obsoleteReferences']==[1]
    assert 'Reference scope:' in final['prompt']
    path.write_bytes(b'replacement')
    assert 'depictedStates' not in render._reference_records(shot,[str(path)])[0]


def test_see_shares_same_state_resolution():
    from studio_keyframe_director import snapshot
    data=source()
    result=snapshot(data['shot'],{}, {'path':'fixture'},refs())
    assert result['dynamicStateResolution']==resolve(data,[dict(path='fixture',role='opening keyframe'),*refs()])


def test_critical_future_state_does_not_require_future_image():
    final,report=run(request_snapshot('Show the return.',source(critical=True),[],{},5),lambda *a:review())
    verify(final,report)
    assert report['creativeOutcome']=='unverified'
    assert 'location: B' in final['prompt']


def test_critical_reset_without_entry_state_blocks():
    data=source(critical=True)
    data['shot']['directorCard']['views'][0]['storyRelationship']='dream'
    assert resolve(data,refs())['errors']


@pytest.mark.parametrize('field', ['atSec', 'visibleEntities'])
def test_critical_missing_view_data_cannot_pass_ready_reviewer(field):
    data=source(critical=True)
    data['shot']['directorCard']['views'][0].pop(field)
    final,report=run(request_snapshot('Return.',data,[],{},5),lambda *a:review())
    assert report['dynamicStateResolution']['correctiveAction']
    with pytest.raises(ValueError,match='BLOCKED'):verify(final,report)


def test_explicit_timing_repaired_from_authoritative_interval_with_provenance():
    data=source(critical=True);before=deepcopy(data)
    card=data['shot']['directorCard'];view=card['views'][0];event=card['stateChanges'][0]
    view.pop('atSec');view['timing']='4–5s'
    event.pop('atSec');event['timing']='2–3s'
    original=deepcopy(data)
    final,report=run(request_snapshot('Return.',data,refs(),{},5),lambda *a:review())
    verify(final,report)
    audit=report['dynamicStateResolution']
    assert audit['revisitChecks'][0]['atSec']==4
    assert audit['revisitChecks'][0]['requiredState']=={'location':'B'}
    assert {r['source'] for r in audit['repairs']}=={'directorCard/views/0/timing','directorCard/stateChanges/0/timing'}
    assert data==original and final['authorities']==original
    assert 'return at 4s' in final['prompt']


@pytest.mark.parametrize('timing',['after the grab','4–3s','around 4s',None])
def test_missing_critical_timing_is_not_guessed(timing):
    data=source(critical=True);view=data['shot']['directorCard']['views'][0]
    view.pop('atSec');view['timing']=timing
    assert resolve(data,[])['errors']


def test_incomplete_critical_event_cannot_silently_keep_old_state():
    data=source(critical=True)
    data['shot']['directorCard']['stateChanges'][0].pop('atSec')
    assert resolve(data,[])['errors']


def test_critical_entity_cannot_disappear_from_visibility_checks():
    data=source(critical=True);data['shot']['directorCard']['views'][0]['visibleEntities']=[]
    assert resolve(data,[])['errors']


@pytest.mark.parametrize('role',['prop identity','scene plate','opening frame'])
def test_scoped_reference_does_not_require_future_matching_pixels(role):
    rs=[{'role':role,'depictedStates':{'object':{'location':'A'}}}]
    final,report=run(request_snapshot('Return.',source(critical=True),rs,{},5),lambda *a:review())
    verify(final,report)
    assert report['dynamicStateResolution']['revisitChecks'][0]['resolution']=='authored state with scoped references'
    assert report['creativeOutcome']=='unverified'


def test_unverified_current_authority_still_blocks_critical_view():
    rs=[{'role':'current frame','stateScope':{'authority':'current_dynamic_state','controlsDynamicState':True,'startSec':0,'endSec':5}}]
    final,report=run(request_snapshot('Return.',source(critical=True),rs,{},5),lambda *a:review())
    with pytest.raises(ValueError,match='BLOCKED'):verify(final,report)


@pytest.mark.parametrize('mode', ['missing', 'authored-interval', 'future-state', 'conflicting-current'])
def test_native_review_adapter_persists_block_or_seals_current_state(mode,monkeypatch,tmp_path):
    import json
    import cb_llm
    from studio_prompt_director import review_legacy_envelope,verify_legacy_envelope
    data=source(critical=True);card=data['shot']['directorCard'];rs=refs()
    if mode=='missing':card['views'][0].pop('atSec')
    if mode=='authored-interval':
        card['views'][0].pop('atSec');card['views'][0]['timing']='4–5s'
    if mode=='conflicting-current':
        rs[0]['stateScope']={'authority':'current_dynamic_state','controlsDynamicState':True,'startSec':0,'endSec':5}
    monkeypatch.setattr(cb_llm,'structured_with_repair',lambda *a,**k:review())
    audio={'path':'approved.wav','md5':'immutable-audio'}
    original='[Audience Purpose]\nShow the consequence.\n[Audio]\n@Audio1: "Exact words" at 1s.'
    env=dict(prompt=original,durationSec=5,references=rs,audio=audio,executionPlan={'segments':[{'prompt':original,'contract':{}}]})
    if mode in {'missing','conflicting-current'}:
        with pytest.raises(ValueError,match='BLOCKED'):
            review_legacy_envelope(env,data['shot'],{},archive_folder=tmp_path)
        assert 'promptDirector' not in env['executionPlan']['segments'][0]
    else:
        review_legacy_envelope(env,data['shot'],{},archive_folder=tmp_path)
        verify_legacy_envelope(env)
        assert 'return at 4s' in env['prompt'] and 'location: B' in env['prompt']
    record=json.loads(next(tmp_path.glob('*.json')).read_text())
    assert record['snapshot']['audio']==audio
    assert '[Audio]\n@Audio1: "Exact words" at 1s.' in record['review']['finalPrompt']
    assert record['review']['dynamicStateResolution']['history']
    if mode=='authored-interval':assert record['review']['dynamicStateResolution']['repairs']


def test_native_see_context_keeps_same_file_bound_state_authority(monkeypatch,tmp_path):
    import cb_render as render
    image=tmp_path/'image.png';image.write_bytes(b'synthetic')
    binding={'stateEvidenceHash':render._file_md5(str(image)),
             'depictedStates':{'object':{'location':'A'}},
             'stateScope':{'authority':'fixed_geography','controlsDynamicState':False}}
    monkeypatch.setattr(render,'_provider_attachment_plan',lambda *a:[{'path':str(image),'role':'scene plate','stateBinding':binding}])
    monkeypatch.setattr(render,'_characters_cfg',lambda:{})
    monkeypatch.setattr(render,'_approved_department_output',lambda *a:{})
    shot={**source()['shot'],'shotId':'synthetic'}
    result=render._see_readiness_source({},shot,{},str(image),'1','EpT')
    ref=result['references'][0]
    assert ref['depictedStates']==binding['depictedStates']
    assert ref['stateScope']==binding['stateScope']
