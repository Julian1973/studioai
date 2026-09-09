"""Real adapter bodies; the network alone is intercepted. No paid calls."""
import json
import stat
from types import SimpleNamespace

import pytest
import requests

from studio_request_evidence import capture, digest, inclusion_map, observe, RequestEvidenceError
from studio_transport import ProviderTransport
from test_studio_production import setup, command, approve


def records(folder):
    return [json.loads(p.read_text()) for p in folder.glob('*.json')]


def test_project_video_captures_actual_body_and_private_assets(tmp_path, monkeypatch):
    seen = []
    def network(method, url, **kwargs):
        seen.append(kwargs['json'])
        return SimpleNamespace(status_code=200, json=lambda: {'id': 'task-1'})
    monkeypatch.setattr(requests, 'request', network)
    image = tmp_path / 'frame.png'; image.write_bytes(b'image')
    audio = tmp_path / 'voice.wav'; audio.write_bytes(b'approved-voice')
    prompt = 'Cut to her reaction. Her eyes flick towards him.'
    with capture(tmp_path / 'receipts', {'route': 'project-command', 'revision': 'r1'},
                 expected_prompt=prompt, direction={'reaction': 'Her eyes flick towards him.'},
                 expected_media_counts={'image': 1, 'audio': 1}, expected_fields={'duration': 8}):
        assert ProviderTransport().video_submit({'provider': 'byteplus'}, 'private-key', 'model-1',
                                               prompt, [image], [audio], 8) == 'task-1'
    [receipt] = records(tmp_path / 'receipts')
    assert receipt['body'] == seen[0]
    assert receipt['bodyHash'] == digest(seen[0])
    assert receipt['state'] == 'response-received'
    assert receipt['directionTrace']['unverified'] == []
    assert receipt['directionTrace']['screenPerformance'] == 'unverified'
    assert 'private-key' not in json.dumps(receipt)
    assert stat.S_IMODE(next((tmp_path / 'receipts').glob('*.json')).stat().st_mode) == 0o600
    changed = dict(seen[0], duration=9)
    assert digest(changed) != receipt['bodyHash']


@pytest.mark.parametrize('omission', ['reaction', 'cut', 'geography', 'prop', 'end', 'dialogue'])
def test_loss_after_compilation_stops_before_http(tmp_path, omission):
    required = {'reaction': 'She conceals embarrassment.', 'cut': 'Cut to the listener.',
                'geography': 'Target remains beyond the stream.', 'prop': 'Cup stays empty.',
                'end': 'She returns to meditation.', 'dialogue': '@Audio1 Zenny 4.1–7.4 seconds.'}
    approved = '\n'.join(required.values())
    damaged = approved.replace(required[omission], '')
    calls = []
    with capture(tmp_path, {'revision': 'r1'}, expected_prompt=approved, direction=required):
        with pytest.raises(RequestEvidenceError, match='no provider was called'):
            observe(lambda: calls.append(True), 'https://provider.test/tasks', {'prompt': damaged})
    assert not calls
    [receipt] = records(tmp_path)
    assert receipt['state'] == 'blocked-before-http'
    assert 'direction/' + omission in receipt['directionTrace']['unverified']


@pytest.mark.parametrize('kind', ['audio', 'image'])
def test_missing_attachment_blocks_real_transport(tmp_path, monkeypatch, kind):
    calls = []
    monkeypatch.setattr(requests, 'request', lambda *a, **k: calls.append(k))
    with capture(tmp_path, {'revision': 'r2'}, expected_media_counts={kind: 1}):
        with pytest.raises(RequestEvidenceError, match=kind + ' references'):
            ProviderTransport().video_submit({'provider': 'byteplus'}, 'secret', 'model', 'Act.', [], [], 8)
    assert not calls


def test_native_http_gateway_preserves_body_and_scope_resets(tmp_path, monkeypatch):
    import cb_gen
    calls = []
    response = SimpleNamespace(status_code=200, raise_for_status=lambda: None)
    monkeypatch.setattr(requests, 'post', lambda url, **kw: calls.append(kw['json']) or response)
    monkeypatch.setattr(cb_gen.episode_budget, 'active', lambda: False)
    body = {'model': 'seedream', 'prompt': 'Opening pose.', 'image': ['asset:first', 'asset:second']}
    with capture(tmp_path, {'route': 'cb_render', 'stage': 'see'}, expected_prompt=body['prompt']):
        cb_gen._rpost('https://provider.test/images', json=body, _retry_request=False)
    assert records(tmp_path)[0]['body'] == calls[0]
    cb_gen._rpost('https://provider.test/images', json=body, _retry_request=False)
    assert len(records(tmp_path)) == 1


def test_unknown_network_outcome_does_not_claim_failure_or_completion(tmp_path):
    def disconnect():
        raise requests.ConnectionError('lost response')
    with capture(tmp_path, {'revision': 'r1'}):
        with pytest.raises(requests.ConnectionError):
            observe(disconnect, 'https://provider.test/tasks?secret=hidden', {'prompt': 'Act.'})
    [receipt] = records(tmp_path)
    assert receipt['state'] == 'submission-unknown'
    assert '?' not in receipt['endpoint']


def test_direction_omitted_before_compilation_is_unverified_not_a_false_pass():
    report = inclusion_map({'acting': 'He fails to conceal worry.'}, 'He smiles.')
    assert report['unverified'] == ['direction/acting']
    assert report['semanticCompleteness'] == 'not-assessed'


def test_project_commands_reach_real_image_and_video_http_builders(setup, monkeypatch):
    from PIL import Image
    production, ws, transport, _ = setup
    real = ProviderTransport()
    posted = []
    def network(method, url, **kwargs):
        posted.append(kwargs['json'])
        data = {'data': [{'url': 'https://media.example/frame.png'}]} if '/images/' in url else {'id': 'task-qualification'}
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(requests, 'request', network)
    monkeypatch.setattr(real, 'download', lambda url, out: Image.new('RGB', (32, 18), 'blue').save(out))
    monkeypatch.setattr(transport, 'image', real.image)
    monkeypatch.setattr(transport, 'video_submit', real.video_submit)
    command(production, 'budget', amountUsd=5)
    approve(production, 'see')
    approve(production, 'hear')
    approve(production, 'request')
    shot = production.snapshot('first', '1')['state']['shots'][0]
    assert len(posted) == 2
    for stage, body in zip(('see', 'watch'), posted):
        receipt = shot['outcomes'][stage]['executionReceipt']
        assert receipt['requestEvidenceScope'] == 'http-json-body'
        [reference] = receipt['providerRequests']
        from pathlib import Path
        saved = json.loads(Path(reference['path']).read_text())
        assert saved['body'] == body
        assert saved['origin']['projectId'] == 'first'
        assert saved['origin']['shotId'] == 'S1.SH1'
        assert saved['bodyHash'] == digest(body)
    assert shot['outcomes']['watch']['executionReceipt']['providerTaskId'] == 'task-qualification'
    assert shot['outcomes']['watch']['providerReturnedFile']['hash']
    # Artificial blue frames and a silent test voice do not qualify creative quality.
    assert shot['outcomes']['watch']['status'] == 'candidate'


def test_native_render_gateway_captures_real_byteplus_body(tmp_path, monkeypatch):
    import cb_gen
    import cb_render
    class Response:
        status_code = 200
        content = b'synthetic-video-not-a-qualified-film'
        def raise_for_status(self):
            pass
        def json(self):
            return {'id': 'native-task-1', 'status': 'succeeded', 'duration': 8,
                    'content': {'video_url': 'https://media.example/render.mp4'}}
    posted = []
    monkeypatch.setattr(requests, 'post', lambda url, **kw: posted.append(kw['json']) or Response())
    monkeypatch.setattr(cb_gen, '_rget', lambda *a, **k: Response())
    monkeypatch.setattr(cb_gen, '_byteplus_asset_url', lambda value, kind: str(value))
    monkeypatch.setattr(cb_gen, 'BYTEPLUS_ARK_KEY', 'test-private-key')
    monkeypatch.setattr(cb_gen.episode_budget, 'active', lambda: False)
    monkeypatch.setattr(cb_gen.cb_costs, 'log_spend', lambda *a, **k: None)
    monkeypatch.setattr(cb_gen.cb_costs, 'write_gen_sidecar', lambda *a, **k: None)
    monkeypatch.setattr(cb_render, 'ROOT', tmp_path)
    prompt = 'Wide view. Cut to her reaction. The cup stays empty.'
    cb_render._submit_seedance_provider(prompt, ['https://media.example/frame.png'],
        audio_urls=['https://media.example/voice.wav'], out=str(tmp_path / 'video.mp4'),
        duration=8, resolution='480p', raw_prompt=True, production_route='cb_render',
        model_id='dreamina-seedance-2-5-260628', request_id='qualification-only',
        direction_evidence={'directorCardRevision': {'revision': 'r1', 'decisions': {'prop': 'The cup stays empty.'}}})
    [receipt] = records(tmp_path / 'cb-output/state/provider-requests')
    assert len(posted) == 1
    assert receipt['body'] == posted[0]
    assert receipt['origin']['directorCardRevision']['revision'] == 'r1'
    assert receipt['directionTrace']['unverified'] == []
    assert receipt['directionTrace']['screenPerformance'] == 'unverified'


def test_pre_http_direction_loss_preserves_project_budget_and_names_error(setup, monkeypatch):
    production, ws, transport, _ = setup
    calls = []
    monkeypatch.setattr(requests, 'request', lambda *a, **k: calls.append(k))
    real = ProviderTransport()
    def damaged_image(connection, key, model, prompt, references, output, **kwargs):
        return real.image(connection, key, model, 'Lost director instructions.', references, output, **kwargs)
    monkeypatch.setattr(transport, 'image', damaged_image)
    command(production, 'budget', amountUsd=5)
    snapshot = production.snapshot('first', '1')
    assert not calls
    assert snapshot['jobs'][0]['code'] == 'production_direction_lost'
    assert 'no provider was called' in snapshot['jobs'][0]['message']
    assert snapshot['state']['budget']['reserved'] == 0
    assert snapshot['state']['budget']['committed'] == 100000  # planning only


@pytest.mark.parametrize('fail_after_http', [False, True])
def test_receipt_storage_failure_never_discards_paid_response(tmp_path, monkeypatch, fail_after_http):
    import studio_request_evidence as evidence
    original = evidence._write
    def write(path, record):
        if not fail_after_http or record['state'] == 'response-received':
            raise OSError('disk full')
        original(path, record)
    monkeypatch.setattr(evidence, '_write', write)
    calls = []
    response = SimpleNamespace(status_code=200, json=lambda: {'id': 'retain-this-task'})
    with capture(tmp_path, {'revision': 'r1'}):
        if fail_after_http:
            assert observe(lambda: calls.append(True) or response, 'https://provider.test/tasks',
                           {'prompt': 'Act.'}) is response
            assert records(tmp_path)[0]['state'] == 'submission-unknown'
        else:
            with pytest.raises(RequestEvidenceError, match='no provider was called'):
                observe(lambda: calls.append(True), 'https://provider.test/tasks', {'prompt': 'Act.'})
            assert not calls


def test_required_direction_omitted_before_sealing_is_blocked(tmp_path):
    instruction = dict(id='reaction', text='She notices the empty cup.', source='director/r2',
                       kind='creative_direction', scope={'stage':'watch'}, required=True)
    calls=[]
    with capture(tmp_path, {'stage':'watch'}, expected_prompt='Incomplete but sealed.',
                 direction={'instructions':[instruction]}):
        with pytest.raises(RequestEvidenceError, match='required instruction reaction'):
            observe(lambda: calls.append(True), 'https://provider.test', {'prompt':'Incomplete but sealed.'})
    assert calls == []
    assert records(tmp_path)[0]['deliveryPackage']['cost']['actual'] is None
