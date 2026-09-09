import copy
import pytest
from studio_shot_remix import build, validate, prompt
from studio_workspace import StudioError


def fixture():
    frame = {'path': 'projects/a/end.png', 'hash': 'abc'}
    previous = {'id': 's1', 'scene': 1, 'outcomes': {'watch': {'id': 'w1', 'status': 'approved', 'ending': frame}}}
    shot = {'id': 's2', 'scene': 1, 'transition': 'cut', 'seeCutType': 'same_moment_camera_cut', 'camera': 'Reverse medium'}
    state = {'shots': [previous, shot]}
    return state, shot, [{**frame, 'role': 'previous state'}]


def test_same_moment_contract_reaches_prompt_without_reset():
    state, shot, refs = fixture()
    record = build({'project': {'id': 'a'}}, state, shot, refs)
    assert record['sourceWatchId'] == 'w1'
    assert record['timeAdvance'].startswith('none')
    assert 'Reverse medium' in prompt(record)
    assert 'never override later approved action' in prompt(record)


def test_changed_approved_parent_cannot_be_approved_or_sent_to_watch():
    state, shot, refs = fixture()
    record = build({'project': {'id': 'a'}}, state, shot, refs)
    class Production:
        def assert_artifact(self, pid, artifact): self.checked = artifact
    p = Production()
    validate(p, 'a', state, record)
    assert p.checked['files'] == refs
    state['shots'][0]['outcomes']['watch']['ending']['hash'] = 'changed'
    with pytest.raises(StudioError): validate(p, 'a', state, record)


def test_new_scene_and_missing_ending_are_not_verified_continuity():
    state, shot, refs = fixture()
    record = build({'project': {'id': 'a'}}, state, shot, [])
    assert record['continuityEvidence'] == 'planned-only-no-approved-ending'
    assert record['sourceWatchId'] is None
    shot['scene'] = 2
    assert build({'project': {'id': 'a'}}, state, shot, refs) is None


def test_contract_is_a_snapshot_not_mutable_reference_alias():
    state, shot, refs = fixture()
    record = build({'project': {'id': 'a'}}, state, shot, refs)
    refs[0]['hash'] = 'later'
    assert record['sourceFrame']['hash'] == 'abc'
    assert record['references'][0]['hash'] == 'abc'


from test_studio_production import setup, command, approve


def test_changed_handoff_blocks_sealed_watch_without_spending(setup):
    p, ws, transport, _ = setup
    command(p, 'budget', amountUsd=20)
    for stage in ('see', 'hear', 'request', 'watch'):
        approve(p, stage)
    current = p.snapshot('first', '1')['state']['shots'][1]
    assert current['outcomes']['see']['shotRemix']['sourceWatchId']
    for stage in ('see', 'hear'):
        current = p.snapshot('first', '1')['state']['shots'][1]
        command(p, 'approve', shotId=current['id'], reviewId=current['outcomes'][stage]['id'])
    current = p.snapshot('first', '1')['state']['shots'][1]
    request_id = current['outcomes']['request']['id']
    with ws.db() as db:
        state = p._load(db, 'first', '1')
        state['shots'][0]['outcomes']['watch']['id'] = 'replacement-parent'
        p._save(db, 'first', '1', state)
    calls = len([c for c in transport.calls if c[0] == 'video'])
    command(p, 'approve', shotId=current['id'], reviewId=request_id)
    after = p.snapshot('first', '1')
    assert len([c for c in transport.calls if c[0] == 'video']) == calls
    assert 'watch' not in after['state']['shots'][1]['outcomes']
    assert after['state']['budget']['reserved'] == 0
