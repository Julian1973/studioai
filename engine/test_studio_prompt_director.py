"""Plan-first reviewer guards and immutable payload verification, no network."""
from copy import deepcopy
import socket
import pytest
from studio_prompt_director import run, verify, request_snapshot, lifecycle_errors, return_review


def review(**kw):
    result = dict(summary='One object is moved; the reaction lands.', audienceBeat='Surprise', camera='Hold then cut on action',
        audio='Approved words unchanged', locked=['audio'], directed=['move one object'], open=['micro-expression'],
        lifecycle=[], findings=[], edits=[])
    return {**result, **kw}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))


def state(at, values, cause='', entity='object-1'):
    return dict(entity=entity, at=at, view=str(at), values=values, cause=cause, source='Director Card')


def snapshot(prompt='Move the object.'):
    # Explicit synthetic typed direction; the freeform prompt is retained solely
    # to exercise audio intake and the rejection of historical visual prose.
    shot = dict(shotId='fixture', durationSec=12, purpose='Make the object transfer readable.',
        directorCard={'views': [dict(viewId='view-1', timing='0–12s', atSec=0, visibleEntities=[])]},
        approvedAction='The same object travels with its holder; its support stays empty.')
    direction = dict(shotPlan=[dict(sourceViewId='view-1', transitionType='opening',
        framingLensAndCamera='Hold a medium view of the transfer.', causalAction='Move the object.',
        observablePerformance='The holder checks the empty support.', compositionLightAndMaterials='Keep the established soft light.',
        landingImage='The holder has the single object.', dialogueLineIndexes=[])])
    return request_snapshot(prompt, {'revision': 2, 'shot': shot, 'specialist': direction},
        [{'role': 'scene plate'}], {'hash': 'locked'}, 12)


def test_plan_correction_reaches_final_payload_and_is_re_reviewed():
    import studio_watch_plan as plan
    before = snapshot('[Audio]\n@Audio1 exact approved performance.')
    calls = []
    def worker(system, data):
        calls.append(data)
        row = review()
        if len(calls) == 2:
            row['planCorrections'] = [dict(expectedPlanHash=data['watchPlanBinding']['planHash'],
                path='/specialist/shotPlan/0/causalAction', expected='Move the object.',
                value=data['authorities']['shot']['approvedAction'], sourcePath='/shot/approvedAction',
                sourceHash=plan.digest(data['authorities']['shot']['approvedAction']), reason='Apply the approved object transfer')]
        return row
    final, report = run(before, worker)
    assert len(calls) == 4 and calls[-1]['prompt'] == final['prompt']
    assert 'prompt' not in calls[0] and 'prompt' not in calls[2]
    assert 'support stays empty' in final['prompt']
    assert final['audio'] == before['audio']
    assert final['authorities']['shot'] == before['authorities']['shot']
    verify(final, report)
    assert report['trace'][0]['status'] == 'revised-typed-plan'


@pytest.mark.parametrize('values', [({'location':'A'},{'location':'B'}), ({'condition':'collapsed'},{'condition':'upright'}), ({'mark':'berry'},{'mark':'none'}), ({'attachment':'detached'},{'attachment':'attached'})])
def test_changed_states_require_a_cause(values):
    assert lifecycle_errors([state(0,values[0]),state(2,values[1])])
    assert not lifecycle_errors([state(0,values[0]),state(2,values[1], 'explicit source event')])


def test_same_object_cannot_remain_attached_and_be_carried_at_same_time():
    assert lifecycle_errors([state(1, {'holder':'support'}),state(1, {'holder':'character'}, 'detaches')])


def test_amendment_invalidates_sealed_review():
    final, report = run(snapshot(), lambda *a: review())
    changed = deepcopy(final); changed['authorities']['revision'] = 3
    with pytest.raises(ValueError, match='STALE'): verify(changed, report)


@pytest.mark.parametrize('field,value', [
    ('audio', {'hash': 'replacement'}), ('references', [{'role': 'different opening', 'hash': 'new'}]),
    ('duration', 19), ('settings', {'model': 'different-provider-model'}), ('prompt', 'Different beat')])
def test_review_cannot_be_reused_after_delivery_input_changes(field, value):
    final, report = run(snapshot(), lambda *a: review())
    changed = deepcopy(final); changed[field] = value
    with pytest.raises(ValueError, match='STALE'): verify(changed, report)


def test_authorised_overlap_survives_and_audio_string_edits_are_refused():
    text = '[Audio]\n@Audio1 A says {Hello}. B laughs nonverbally during the line.'
    source = snapshot(text)
    source['authorities']['shot']['dialogueLines'] = [dict(speaker='A', exactText='Hello', startSec=2, endSec=3)]
    source['authorities']['specialist']['shotPlan'][0]['dialogueLineIndexes'] = [1]
    final, report = run(source, lambda *a: review())
    verify(final, report)
    assert text in final['prompt'] and final['audio'] == source['audio']
    def worker(system, data):
        if 'prompt' not in data: return review()
        return review(edits=[dict(old='B laughs nonverbally during the line.', new='B remains silent.', source='default', reason='bad')])
    final, report = run(source, worker)
    assert text in final['prompt'] and 'B remains silent.' not in final['prompt']
    assert report['verdict'].startswith('BLOCKED')


def test_true_audio_conflict_blocks_and_is_grounded():
    source = snapshot()
    source['authorities']['specialist']['shotPlan'][0]['causalAction'] = 'Generate a new spoken line from B.'
    def worker(system, data):
        if 'prompt' not in data: return review()
        return review(findings=[dict(category='true audio conflict', reason='New dialogue is not approved',
            evidence='Generate a new spoken line from B.', correction='Resolve against the approved words')])
    final, report = run(source, worker)
    with pytest.raises(ValueError, match='AUDIO'): verify(final, report)


def test_reference_scoping_does_not_pretend_to_inspect_pixels():
    final, report = run(snapshot(), lambda *a: review())
    assert 'fixed environment only' in report['references'][0]['coherenceAuthority']
    assert 'metadata only' in report['visualEvidence']


def test_return_review_is_not_approval_or_listening():
    _, report = run(snapshot(), lambda *a: review())
    result = return_review(report, {'hash':'render1'}, [{'failure':'reset'}], method='sampled frames', ranges=[[0,2]], limitations='one fps')
    assert result['audioLipSync'] == 'unverified' and result['approval'] == 'not-granted'
    assert result['packageHash'] == report['payloadHash']


def test_legacy_prose_only_seal_is_explicitly_blocked(monkeypatch, tmp_path):
    import cb_llm
    from studio_prompt_director import review_legacy_envelope
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **kw: pytest.fail('No model call'))
    env = {'prompt':'preview', 'durationSec':12, 'references':[], 'audio':{},
        'executionPlan':{'segments':[{'prompt':'Historical submitted beat', 'contract':{}}]}}
    with pytest.raises(ValueError, match='PROVIDER PROMPT COMPILATION'):
        review_legacy_envelope(env, {'shotId':'test'}, {}, archive_folder=tmp_path)
    assert list(tmp_path.glob('*.json'))


def test_obsolete_opening_blocks_but_identity_reference_is_scoped():
    source = snapshot()
    source['references'] = [{'role':'opening composition', 'depictedState':{'condition':'upright'}, 'requiredState':{'condition':'collapsed'}}]
    final, report = run(source, lambda *a: review())
    with pytest.raises(ValueError): verify(final, report)
    assert report['references'][0]['resetRisk']
    source['references'][0]['role'] = 'prop identity'
    final, report = run(source, lambda *a: review())
    verify(final, report)
    assert 'identity/design only' in report['references'][0]['coherenceAuthority']


def test_audio_guard_utility_preserves_full_audio_sections():
    from studio_prompt_director import protected
    prompt = '[Environment]\nThe comb stays fixed. Preserve dialogue timing.\n[Audio]\nKeen at 8s: "Uh-oh".\nKeep all pauses.'
    guards = protected(prompt)
    changed = prompt.replace('The comb stays fixed.', 'The comb travels with Keen.')
    assert all(changed.count(s) == prompt.count(s) for s in guards)
    assert any(prompt.replace('8s', '9s').count(s) != prompt.count(s) for s in guards)


def test_ungrounded_hard_review_cannot_silently_become_ready():
    def worker(system, data):
        if 'prompt' not in data: return review()
        return review(findings=[dict(category='story/state contradiction', reason='Incompatible locations',
            evidence='"Object is here." vs "Object is there."', correction='Resolve location')])
    final, report = run(snapshot(), worker)
    assert report['verdict'].startswith('BLOCKED')
    assert any('lacks exact current-payload evidence' in item for item in report['errors'])


def test_watch_authorities_exclude_other_stage_provider_slot_text(monkeypatch, tmp_path):
    import json, cb_llm
    from studio_prompt_director import review_legacy_envelope
    source = snapshot()
    source['authorities']['shot'].update(keyframePrompt='Old SEE slots', seedreamPrompt='Old still prompt', seedancePrompt='Old video prompt')
    seen = []
    def worker(system, text, *args, **kwargs):
        seen.append(json.loads(text)); return review()
    monkeypatch.setattr(cb_llm, 'structured_with_repair', worker)
    env = dict(prompt=source['prompt'], durationSec=12, references=source['references'], audio=source['audio'],
        executionPlan={'segments':[dict(prompt=source['prompt'], contract={})]})
    review_legacy_envelope(env, source['authorities']['shot'], source['authorities']['specialist'], archive_folder=tmp_path)
    assert not {'keyframePrompt', 'seedreamPrompt', 'seedancePrompt'} & seen[0]['authorities']['shot'].keys()
    assert source['authorities']['shot']['keyframePrompt'] == 'Old SEE slots'


def test_repeated_provider_edits_do_not_bypass_structured_correction_route():
    def worker(system, data):
        if 'prompt' not in data: return review()
        return review(edits=[dict(old='absent text', new='invented text', source='wrong', reason='bad')])
    final, report = run(snapshot(), worker)
    assert 'invented text' not in final['prompt']
    assert report['verdict'].startswith('BLOCKED')
    assert report['trace'][-1]['status'] == 'rejected-provider-string-edit'
