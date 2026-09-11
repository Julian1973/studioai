"""Production regressions: history survives draft drift; no duplicate paid POST."""
import hashlib
import json
from types import SimpleNamespace

import pytest
import requests

import cb_costs
import cb_gen
import cb_production_contracts as contracts
import cb_provider_jobs as jobs
import cb_db


def test_accepted_bytes_survive_draft_changes_but_detect_tampering(tmp_path):
    take, frame = tmp_path / 'take.mp4', tmp_path / 'frame.png'
    take.write_bytes(b'accepted film')
    frame.write_bytes(b'landing')
    ledger = {'approvedTake': str(take), 'harvestFrame': str(frame),
              'status': 'stale', 'approval': {'approved': True,
                'contentHash': contracts.file_hash(take),
                'harvestHash': contracts.file_hash(frame)}}
    assert contracts.accepted_asset(ledger)['intact']
    take.write_bytes(b'changed')
    assert not contracts.accepted_asset(ledger)['intact']


def test_metadata_does_not_invalidate_working_signature_but_content_does():
    old = {'packageRevision': 1, 'shotHash': 'a', 'audioHash': 'b'}
    assert contracts.working_signature_matches(old, {**old, 'packageRevision': 2})
    assert not contracts.working_signature_matches(old, {**old, 'audioHash': 'c'})


def test_parallel_timing_and_visual_notation():
    events = [{'channel': c, 'startSec': 18, 'endSec': 26} for c in ['camera', 'music']]
    assert contracts.validate_timeline(events, 30)['ready']
    assert not contracts.validate_timeline(events + [
        {'channel': 'camera', 'startSec': 20, 'endSec': 28}], 30)['ready']
    assert contracts.visual_event_text('Lift 18–26 seconds') == contracts.visual_event_text(
        'Lift 18 seconds until 26 seconds')
    assert contracts.visual_event_text('Lift') != contracts.visual_event_text('Drop')


def test_sound_effect_mix_can_overlap_without_relaxing_bounds_or_camera():
    sounds = [{'channel': 'sfx', 'startSec': 2, 'endSec': 10},
              {'channel': 'sfx', 'startSec': 4, 'endSec': 5}]
    assert contracts.validate_timeline(sounds, 12)['ready']
    assert not contracts.validate_timeline(sounds, 8)['ready']
    assert not contracts.validate_timeline(
        [{**event, 'channel': 'camera'} for event in sounds], 12)['ready']


def test_active_graph_and_expected_spend_outcome():
    pkg = {'shots': [{'shotId': 'a'}, {'shotId': 'b', 'status': 'superseded'}]}
    assert [s['shotId'] for s in contracts.active_shots(pkg)] == ['a']
    assert contracts.command_outcome(1, 'shot:compare', ['SPEND NOT APPROVED']) == 'needs_spend_approval'


def test_outcome_survives_restart(tmp_path):
    cb_db.persist_job(tmp_path, {'jobId': 'quote', 'status': 'done',
                                'outcome': 'needs_spend_approval'})
    assert cb_db.load_jobs(tmp_path)['quote']['outcome'] == 'needs_spend_approval'


@pytest.fixture
def transport(monkeypatch, tmp_path):
    monkeypatch.setattr(cb_gen, 'BYTEPLUS_ARK_KEY', 'test-credential')
    monkeypatch.setattr(cb_gen, 'MEDIA', tmp_path)
    contract = {'providerModelId': 'test-model', 'endpoint': '/api/v3/contents/generations/tasks',
                'mode': 'reference-to-video'}
    def run(**kw):
        return cb_gen._byteplus_generate_video(contract, 'approved action', [], [],
            '480p', 5, 'candidate.mp4', **kw)
    return run


def test_unknown_submission_is_never_automatically_repaid(transport, monkeypatch):
    calls = []
    def post(*args, **kwargs):
        calls.append(kwargs)
        raise requests.Timeout('response lost')
    monkeypatch.setattr(cb_gen, '_rpost', post)
    for _ in range(2):
        with pytest.raises(jobs.SubmissionUnknown):
            transport()
    assert len(calls) == 1
    assert calls[0]['_retry_request'] is False


def test_poll_recovery_and_completed_download_never_submit_again(transport, monkeypatch):
    calls = []
    monkeypatch.setattr(cb_gen, '_rpost', lambda *a, **k:
        calls.append('post') or SimpleNamespace(json=lambda: {'id': 'task-1'}))
    monkeypatch.setattr(cb_gen, '_rget', lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()))
    with pytest.raises(requests.Timeout):
        transport()
    def get(url, **kwargs):
        return SimpleNamespace(content=b'film', json=lambda: {
            'status': 'succeeded', 'content': {'video_url': 'https://test/film'}})
    monkeypatch.setattr(cb_gen, '_rget', get)
    out, task_id, _ = transport()
    assert out.read_bytes() == b'film' and task_id == 'task-1'
    monkeypatch.setattr(cb_gen, '_rget', lambda *a, **k: pytest.fail('completed media needs no network'))
    transport()
    assert calls == ['post']


def test_provider_task_is_bound_to_credential(transport, monkeypatch):
    monkeypatch.setattr(cb_gen, '_rpost', lambda *a, **k: SimpleNamespace(json=lambda: {'id': 'task-1'}))
    monkeypatch.setattr(cb_gen, '_rget', lambda *a, **k: (_ for _ in ()).throw(requests.Timeout()))
    with pytest.raises(requests.Timeout):
        transport()
    monkeypatch.setattr(cb_gen, 'BYTEPLUS_ARK_KEY', 'different-test-credential')
    with pytest.raises(RuntimeError, match='different credential'):
        transport()


def test_spend_ledger_records_resumed_task_once(monkeypatch, tmp_path):
    ledger = tmp_path / 'costs.jsonl'
    monkeypatch.setattr(cb_costs, 'LEDGER_PATH', str(ledger))
    for _ in range(2):
        cb_costs.log_spend('video', 1.0, meta={'provider': 'test', 'providerTaskId': 'same'})
    assert len(ledger.read_text().splitlines()) == 1


def test_every_declared_mutation_has_an_explicit_scene_boundary():
    import cb_render
    import cb_transactions
    for name in cb_transactions.MUTATING_OPERATIONS:
        assert getattr(cb_render, name).__studio_mutation__ == {'command': name, 'scope': 'scene'}


def test_structured_outcome_precedes_legacy_log_wording():
    assert contracts.command_outcome(1, 'shot:compare', [
        'old failure wording', 'STUDIO_OUTCOME {"outcome":"needs_spend_approval"}'
    ]) == 'needs_spend_approval'


def test_previous_database_upgrades_without_losing_jobs(tmp_path):
    import sqlite3
    cb_db.persist_job(tmp_path, {'jobId': 'old', 'status': 'done'})
    with sqlite3.connect(cb_db.state_db_path(tmp_path)) as conn:
        conn.execute('ALTER TABLE studio_jobs DROP COLUMN outcome')
        conn.execute('PRAGMA user_version = 6')
    assert cb_db.load_jobs(tmp_path)['old']['status'] == 'done'
    cb_db.persist_job(tmp_path, {'jobId': 'new', 'status': 'done', 'outcome': 'completed'})
    assert cb_db.load_jobs(tmp_path)['new']['outcome'] == 'completed'


def test_voice_override_does_not_stale_source_direction():
    old = {"dialogueHash": "words", "voiceIds": ["voice"], "workingPerformanceHash": "old", "skillHashes": {"voice": "a"}}
    new = {**old, "workingPerformanceHash": "edited"}
    assert contracts.voice_direction_signature_matches(old, new)
    for key, value in [("dialogueHash", "changed"), ("voiceIds", ["other"]), ("skillHashes", {"voice": "b"})]:
        assert not contracts.voice_direction_signature_matches(old, {**new, key: value})
    assert not contracts.voice_direction_signature_matches(None, new)


def test_action_tracks_are_owned_by_performer():
    events = [dict(channel="action", performer="Keen", startSec=0, endSec=6),
              dict(channel="action", performer="Fuzzby", startSec=2, endSec=8)]
    assert contracts.validate_timeline(events, 10)["ready"]
    assert not contracts.validate_timeline(events + [dict(channel="action", performer="Keen", startSec=3, endSec=5)], 10)["ready"]
    assert not contracts.validate_timeline([dict(channel="camera", performer="Keen", startSec=0,endSec=6), dict(channel="camera",performer="Fuzzby",startSec=2,endSec=8)],10)["ready"]
