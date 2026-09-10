from copy import deepcopy
import pytest
from studio_prompt_director import run, verify, request_snapshot, lifecycle_errors, return_review


def review(**kw):
    return dict(summary='One object is moved; the reaction lands.', audienceBeat='Surprise', camera='Hold then cut on action',
        audio='Approved words unchanged', locked=['audio'], directed=['move one object'], open=['micro-expression'],
        lifecycle=[], findings=[], edits=[], **kw)

def state(at, values, cause='', entity='object-1'):
    return dict(entity=entity, at=at, view=str(at), values=values, cause=cause, source='Director Card')

def snapshot(prompt='Move the object.'):
    return request_snapshot(prompt, {'revision': 2}, [{'role':'scene plate'}], {'hash':'locked'}, 12)

def test_scoped_repair_reaches_final_payload_and_is_re_reviewed():
    before=snapshot('Object stays fixed.\n[Audio]\n@Audio1 exact dialogue {Hello}.')
    calls=[]
    def worker(system, data):
        calls.append(data['prompt'])
        row=review()
        if len(calls)==1:
            row['edits']=[dict(old='Object stays fixed.', new='The same object travels with its holder; its support stays empty.', source='stateChanges', reason='Directed removal supersedes fixed-position default')]
        return row
    final, report=run(before, worker)
    assert len(calls)==2 and calls[1]==final['prompt']
    assert 'stays fixed' not in final['prompt']
    assert final['audio']==before['audio'] and before['prompt'].startswith('Object stays fixed')
    verify(final, report)
    assert report['trace'][0]['status']=='replaced'

@pytest.mark.parametrize('values', [({'location':'A'},{'location':'B'}), ({'condition':'collapsed'},{'condition':'upright'}), ({'mark':'berry'},{'mark':'none'}), ({'attachment':'detached'},{'attachment':'attached'})])
def test_changed_states_require_a_cause(values):
    assert lifecycle_errors([state(0,values[0]),state(2,values[1])])
    assert not lifecycle_errors([state(0,values[0]),state(2,values[1], 'explicit source event')])

def test_same_object_cannot_remain_attached_and_be_carried_at_same_time():
    assert lifecycle_errors([state(1, {'holder':'support'}),state(1, {'holder':'character'}, 'detaches')])

def test_amendment_invalidates_sealed_review():
    final, report=run(snapshot(), lambda *a:review())
    changed=deepcopy(final); changed['authorities']['revision']=3
    with pytest.raises(ValueError,match='STALE'):verify(changed,report)
    changed=deepcopy(final);changed['prompt']='Different beat'
    with pytest.raises(ValueError,match='STALE'):verify(changed,report)


def test_authorised_overlap_survives_and_audio_cannot_be_edited():
    source=snapshot('[Audio]\n@Audio1 A says {Hello}. B laughs nonverbally during the line.')
    final, report=run(source,lambda *a:review())
    assert final["prompt"].startswith(source["prompt"]) and final["audio"]==source["audio"]
    bad=review();bad['edits']=[dict(old='B laughs nonverbally during the line.',new='B remains silent.',source='default',reason='bad')]
    with pytest.raises(ValueError,match='protected'):run(source,lambda *a:bad)


def test_true_audio_conflict_blocks_and_is_grounded():
    source=snapshot('Generate a new spoken line from B.')
    bad=review();bad['findings']=[dict(category='true audio conflict',reason='New dialogue is not approved',evidence=source['prompt'],correction='Resolve against the approved words')]
    final,report=run(source,lambda *a:bad)
    with pytest.raises(ValueError,match='AUDIO'):verify(final,report)


def test_reference_scoping_does_not_pretend_to_inspect_pixels():
    final,report=run(snapshot(),lambda *a:review())
    assert 'fixed environment only' in report['references'][0]['coherenceAuthority']
    assert 'metadata only' in report['visualEvidence']


def test_return_review_is_not_approval_or_listening():
    _,report=run(snapshot(),lambda *a:review())
    result=return_review(report,{'hash':'render1'},[{'failure':'reset'}],method='sampled frames',ranges=[[0,2]],limitations='one fps')
    assert result['audioLipSync']=='unverified' and result['approval']=='not-granted'
    assert result['packageHash']==report['payloadHash']


def test_legacy_seal_reviews_actual_segment_and_fire_rechecks_it(monkeypatch, tmp_path):
    import cb_llm
    from studio_prompt_director import review_legacy_envelope, verify_legacy_envelope
    monkeypatch.setattr(cb_llm,'structured_with_repair',lambda *a,**kw:review())
    env={'prompt':'preview','durationSec':12,'references':[],'audio':{},'executionPlan':{'segments':[{'prompt':'Exact submitted beat','contract':{}}]}}
    review_legacy_envelope(env,{'shotId':'test'}, {}, archive_folder=tmp_path)
    assert env['prompt']=='Exact submitted beat'
    verify_legacy_envelope(env)
    env['executionPlan']['segments'][0]['prompt']='mutated'
    with pytest.raises(ValueError,match='STALE'):verify_legacy_envelope(env)

def test_obsolete_opening_blocks_but_identity_reference_is_scoped():
    source=snapshot()
    source['references']=[{'role':'opening composition','depictedState':{'condition':'upright'},'requiredState':{'condition':'collapsed'}}]
    final,report=run(source,lambda *a:review())
    with pytest.raises(ValueError):verify(final,report)
    assert report['references'][0]['resetRisk']
    source['references'][0]['role']='prop identity'
    final,report=run(source,lambda *a:review())
    verify(final,report)
    assert 'identity/design only' in final['prompt']
