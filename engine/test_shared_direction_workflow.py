"""Shared structured workflow tests. Mock reviews do not validate AI judgment."""
from copy import deepcopy
import socket
import pytest
from studio_dynamic_state import review_plan, resolve
from studio_prompt_director import request_snapshot, run, verify
from test_studio_prompt_director import review
from studio_seedance_execution import final_check

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))


def shot(actor, obj, a, b):
    return {'shotId': 'test', 'durationSec': 12, 'directorCard': {
        'stateChanges': [
            {'entityId': actor, 'actionId': 'depart', 'atSec': 2, 'beforeValues': {'location': a, 'support': obj},
             'afterValues': {'location': b, 'support': None}, 'cause': 'Approved editorial ellipsis after departure'},
            {'entityId': obj, 'actionId': 'handover', 'atSec': 4, 'beforeValues': {'owner': actor},
             'afterValues': {'owner': 'recipient'}, 'cause': 'Visible handover'},
        ], 'views': [{'viewId': 'arrival', 'atSec': 6, 'visibleEntities': [actor, obj]}]}}


def timed_shot(value=None, duration=12):
    value=deepcopy(value or shot('Ada','parcel','dock','train'))
    value['durationSec']=duration
    value['purpose']='Read the departure and handover in a shared space.'
    value['directorCard']['views']=[{
        'viewId':'shared-action','atSec':0,'timing':f'0-{duration}s','entry':'opening',
        'framing':'A held medium view of the dock and train door.',
        'action':'Ada leaves the dock and hands the parcel to its recipient.',
        'performance':'Ada chooses the departure, then releases the parcel with care.',
        'endState':'Ada is aboard; the recipient owns the parcel.'}]
    return value

@pytest.mark.parametrize('names', [('Fuzzby','H01','tree','bank'), ('Ada','parcel','dock','train'), ('Robot','orb','moon','cabin')])
def test_state_handover_and_departure_are_name_independent(names):
    s = shot(*names)
    report = resolve({'shot': s}, [])
    assert not report['errors']
    assert report['planReview']['closingState'][names[0]]['support'] is None
    assert report['planReview']['closingState'][names[1]]['owner'] == 'recipient'
    assert names[0] in ' '.join(report['clauses'])

@pytest.mark.parametrize('field,wrong', [('location','elsewhere'), ('support','other-object')])
def test_contradictory_carried_state_without_reset_blocks(field,wrong):
    s = shot('Ada','parcel','dock','train')
    s['directorCard']['stateChanges'].append({'entityId':'Ada','atSec':8,
        'beforeValues':{field:wrong}, 'afterValues':{field:'end'}, 'cause':'next action'})
    assert any('before-state' in e for e in review_plan(s)['errors'])

@pytest.mark.parametrize('repeat', [False,True])
def test_occurrence_replay_needs_explicit_intention(repeat):
    s=shot('Ada','parcel','dock','train')
    e=deepcopy(s['directorCard']['stateChanges'][0]);e.update(atSec=8,beforeValues={'location':'train','support':None})
    if repeat:e['repeatAuthorisation']='Approved deliberate replay'
    s['directorCard']['stateChanges'].append(e)
    assert bool(review_plan(s)['errors']) is not repeat

@pytest.mark.parametrize('mutation', ['prompt','audio','references','duration','authorities'])
def test_changes_after_mock_review_invalidate_seal(mutation):
    s=timed_shot()
    final, report=run(request_snapshot('Show the departure then the handover.',{'shot':s},[],{},12),lambda *a:review())
    verify(final,report)
    changed=deepcopy(final)
    changed[mutation]={'changed':True} if mutation in ('audio','authorities') else [] if mutation=='references' else 13 if mutation=='duration' else 'Changed action'
    if mutation=='references':changed[mutation]=[{'role':'new image'}]
    with pytest.raises(ValueError,match='STALE'):verify(changed,report)


def test_audio_must_fit_current_duration():
    s=shot('Ada','parcel','dock','train');s['dialogueLines']=[{'startSec':9,'endSec':13}]
    assert any('audio exceeds' in e for e in review_plan(s)['errors'])


def test_reference_tag_must_resolve_actual_manifest():
    snap=request_snapshot('Use @图2.',{'shot':{}},[{'slot':'@图1'}],{},12)
    assert any('Reference tags' in e for e in final_check(snap,{'applied':False})[1])


def test_native_compiler_rejects_structured_camera_conflict():
    from cb_departments import compile_animation_provider_prompt
    s=shot('Ada','parcel','dock','train')
    s['directorCard']['views'][0]['cinematography']={'cameraState':'locked','movement':'orbit'}
    with pytest.raises(ValueError,match='locked camera conflicts'):
        compile_animation_provider_prompt(s,{})


def test_approved_plan_change_recompiles_current_state():
    s=shot('Ada','parcel','dock','train')
    first=resolve({'shot':s},[])
    s['directorCard']['stateChanges'][1]['afterValues']['owner']='new-recipient'
    second=resolve({'shot':s},[])
    assert first['sourceHash'] != second['sourceHash']
    assert 'owner: new-recipient' in ' '.join(second['clauses'])
    assert 'owner: recipient.' not in ' '.join(second['clauses'])


def test_source_plan_review_precedes_final_prompt_review():
    calls=[]
    def reviewer(system,data):
        calls.append(deepcopy(data))
        return review()
    final, report=run(request_snapshot('Show the departure.',{'shot':timed_shot()},[],{},12),reviewer,review_plan_first=True)
    verify(final,report)
    assert 'prompt' not in calls[0] and 'prompt' in calls[1]
    assert report['planningReview'] is not None
    assert report['authorityInventory']['sources'][0]['hash']


def test_conflicting_source_authorities_stop_before_any_reviewer():
    s=shot('Ada','parcel','dock','train')
    s['directorCard']['instructions']=[dict(id=str(i),text=f'Position {v}',source='approved',kind='hard_truth',decisionKey='position',value=v) for i,v in enumerate(['A','B'])]
    _,report=run(request_snapshot('Show it.',{'shot':s},[],{},12),lambda *a:pytest.fail('No reviewer call'))
    assert report['verdict']=='BLOCKED: SOURCE AUTHORITY CONFLICT'


def test_returned_review_inherits_same_plan_and_diagnosis():
    from studio_prompt_director import return_review
    s=timed_shot()
    final,report=run(request_snapshot('Show the departure.',{'shot':s},[],{},12),lambda *a:review())
    result=return_review(report,{'id':'candidate','hash':'bytes'},[],method='fixture',ranges=['0-12'],failure_class='model-output')
    assert result['intendedPlan']==final['watchPlan']
    assert result['intendedPlan']['views'][0]['action']==s['directorCard']['views'][0]['action']
    assert result['failureClass']=='model-output'
    assert result['approval']=='not-granted'


@pytest.mark.parametrize('condition', ['unknown-hold','stale-see','no-watch','review-only','qualified-watch'])
def test_requalification_uses_current_evidence_without_clearing_hold(condition):
    from types import SimpleNamespace
    from studio_keyframe_director import snapshot,assess,recovery_ready
    source=snapshot({}, {}, {'path':'fixture'}, [])
    see=assess(source,lambda *a:dict(verdict='READY',summary='fixture',camera='fixture',geography='fixture',pose='fixture',propsEffects='fixture',actionFeasibility='fixture',correctiveAction='none'))
    block={'status':'BLOCKED','kind':'review-requalification','requiredReviews':['see-action-readiness','watch-coherence']}
    ledger={'productionBlock':block,'keyframePath':'fixture','seeActionReadiness':see}
    runtime=SimpleNamespace(_see_readiness_source=lambda *a:source)
    token='test'
    if condition=='unknown-hold':block['kind']='other'
    if condition=='stale-see':see['inputHash']='stale'
    if condition=='review-only':token=None
    if condition=='qualified-watch':
        final,report=run(request_snapshot('A held view.',{'shot':timed_shot(duration=5)},[],{},5),lambda *a:review())
        ledger['pendingSpendAuth']={'envelope':{'prompt':final['prompt'],'references':[],'audio':{},'durationSec':5,
            'executionPlan':{'segments':[{'prompt':final['prompt'],'contract':{},'promptDirectorSnapshot':final,'promptDirector':report}]}}}
    before=deepcopy(ledger)
    assert recovery_ready(runtime,{}, {},ledger,'1','test',spend_token=token)==(condition in ('review-only','qualified-watch'))
    assert ledger==before


def test_current_authority_excludes_archives_and_shadowed_fields_without_mutation():
    from studio_prompt_director import current_shot_authority
    from copy import deepcopy
    shot={'storyIntent':{'beat':'old'},'storyIntentApproved':{'beat':'current'},
          'watchDirectorFeedbackHistory':[{'old':'another action'}],
          'unrecognisedCurrentRule':'Preserve this requirement'}
    original=deepcopy(shot)
    result=current_shot_authority(shot)
    assert shot==original
    assert 'storyIntent' not in result and 'watchDirectorFeedbackHistory' not in result
    assert result['storyIntentApproved']=={'beat':'current'}
    assert result['unrecognisedCurrentRule']=='Preserve this requirement'
