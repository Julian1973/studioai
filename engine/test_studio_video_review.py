"""Real ledger, real synthetic media, fake Google HTTP: never uploads production."""
import copy
import json
from types import SimpleNamespace

import pytest
import requests

from studio_video_review import BASE, HOST, GeminiVideoClient, VideoReport
from studio_workspace import StudioError
from test_studio_production import setup, command, approve
from test_studio_improvements import configure, render_candidate, review
from test_studio_review import finish


class Google:
    def __init__(self):
        self.calls = []
        self.files = {}
        self.deletion_fails = False
        self.model_error = None
        self.upload_error = False
        self.state = 'ACTIVE'
        self.status = 'completed'
        self.destination = None
        self.on_model = lambda: None
        self.report = {'summary': 'The full synthetic video is blue.', 'audioReview': 'The supplied soundtrack is silent.',
                       'findings': [{'seconds': .5, 'category': 'performance', 'observation': 'No movement is visible in this synthetic clip.',
                                     'suggestion': 'Review the intended hesitation.', 'confidence': 'high'}],
                       'limitations': ['Synthetic provider report for workflow testing.']}

    def __call__(self, method, url, *, headers, **kwargs):
        body = kwargs.get('json')
        content = kwargs.get('data')
        self.calls.append({'method': method, 'url': url, 'key': headers['x-goog-api-key'], 'body': copy.deepcopy(body),
                           'bytes': content.read() if content is not None else None})
        assert kwargs['allow_redirects'] is False
        code, value, response_headers = 200, {}, {}
        if url == HOST + '/upload/v1beta/files':
            response_headers['X-Goog-Upload-URL'] = self.destination or HOST + '/upload/session'
        elif url == HOST + '/upload/session':
            if self.upload_error:
                raise requests.Timeout('fake timeout with a secret that must never be logged')
            name = f'files/source{len(self.files)}'
            self.files[name] = {'name': name, 'uri': BASE + '/' + name, 'state': self.state}
            value = {'file': self.files[name]}
        elif method == 'DELETE':
            code = 503 if self.deletion_fails else 200
        elif method == 'GET':
            value = self.files[url.removeprefix(BASE + '/')]
        elif url == BASE + '/interactions':
            self.on_model()
            if self.model_error:
                raise self.model_error
            value = {'id': 'review-interaction', 'status': self.status,
                     'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': json.dumps(self.report)}]}],
                     'usage': {'total_tokens': 42}}
        else:
            raise AssertionError((method, url))
        return SimpleNamespace(status_code=code, headers=response_headers, json=lambda: value)


@pytest.fixture
def google_setup(setup, monkeypatch):
    p, ws, t, accounts = setup
    accounts['gemini'] = ws.save_connection({'provider': 'gemini', 'key': 'gemini-private-test-key'})
    ws.save_services('first', {**ws.services('first'), 'review': {
        'connectionId': accounts['gemini']['id'], 'model': 'test-video-model', 'estimateUsd': .2}})
    google = Google()
    monkeypatch.setattr('studio_video_review.requests.request', google)
    return p, ws, t, accounts, google


def test_whole_video_audio_contract_and_references_reach_google_and_stay_version_bound(google_setup):
    p, ws, t, accounts, google = google_setup
    finish(p)
    before = p.snapshot('first', '1')['state']
    review(p, 'S1.SH2')
    state = p.snapshot('first', '1')['state']
    report = state['shots'][1]['mediaReviews'][0]
    assert report['evidence']['kind'] == 'video'
    assert len(report['evidence']['videos']) == 2
    assert report['evidence']['duration'] == 2 and report['evidence']['watchHasAudio']
    assert report['usage']['total_tokens'] == 42
    assert not report['cleanupPending']
    assert state['shots'][1]['outcomes'] == before['shots'][1]['outcomes']
    assert state['shots'][0] == before['shots'][0]
    assert state['budget']['committed'] == before['budget']['committed'] + 200000
    assert state['budget']['reserved'] == 0
    assert not p.snapshot('second', '1')['state']['shots']
    posted = next(c['body'] for c in google.calls if c['url'] == BASE + '/interactions')
    assert posted['model'] == 'test-video-model' and posted['store'] is False
    assert posted['generation_config']['max_output_tokens'] == 6000
    assert 'approved HEAR' in posted['system_instruction']
    assert 'tools' not in posted
    assert posted['response_format']['schema'] == VideoReport.model_json_schema()
    videos = [part for part in posted['input'] if part['type'] == 'video']
    assert len(videos) == 2 and all(v['processing'] == {'type': 'static', 'fps': 4} for v in videos)
    assert any(part['type'] == 'audio' for part in posted['input'])
    assert any(part['type'] == 'image' for part in posted['input'])
    assert 'second world only' not in json.dumps(posted)
    uploads = [c['bytes'] for c in google.calls if c['bytes'] is not None]
    for source in report['evidence']['videos'] + report['evidence']['audio'] + report['evidence']['references']:
        assert ws.project_path('first', source['path']).read_bytes() in uploads
    assert len([c for c in google.calls if c['method'] == 'DELETE']) == len(uploads)
    assert p.snapshot('first', '1')['review']['inspections']['S1.SH2']['mediaReviews'][0]['current']
    from studio_post_contract import project_brief
    current = p.snapshot('first', '1')
    brief = project_brief(p, ws.context('first', '1'), current['state'], current['review']['timeline'])
    assert brief['shots'][1]['mediaReviews'][0]['id'] == report['id']
    assert 'gemini-private-test-key' not in json.dumps(current)


@pytest.mark.parametrize('status', ['in_progress', 'failed', None])
def test_incomplete_review_does_not_attach_or_block_watch(google_setup, status):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    google.status = status
    before = p.snapshot('first', '1')['state']['budget']['committed']
    review(p)
    current = p.snapshot('first', '1')
    assert current['jobs'][0]['status'] == 'failed'
    assert not current['state']['shots'][0].get('mediaReviews')
    assert current['state']['budget']['committed'] == before + 200000
    assert not current['jobs'][0]['cleanupPending']
    approve(p, 'watch')


def test_cleanup_failure_is_visible_and_retry_only_deletes(google_setup):
    p, ws, t, accounts, google = google_setup
    render_candidate(p); google.deletion_fails = True
    result = review(p)
    current = p.snapshot('first', '1')
    assert current['jobs'][0]['cleanupPending']
    assert current['state']['shots'][0]['mediaReviews'][0]['cleanupPending']
    before = current['state']['budget']
    with pytest.raises(StudioError):
        command(p, 'cleanup_review_uploads', pid='second', jobId=result['jobId'])
    count = len(google.calls); google.deletion_fails = False
    command(p, 'cleanup_review_uploads', jobId=result['jobId'])
    assert google.calls[count:] and all(c['method'] == 'DELETE' for c in google.calls[count:])
    current = p.snapshot('first', '1')
    assert not current['jobs'][0]['cleanupPending']
    assert not current['state']['shots'][0]['mediaReviews'][0]['cleanupPending']
    assert current['state']['budget'] == before


def test_unknown_model_post_is_not_retried_and_submission_intent_is_durable(google_setup):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    def check_submission():
        with ws.db() as db:
            job = json.loads(db.execute("SELECT data FROM jobs WHERE state='running'").fetchone()[0])
        assert job['reviewSubmitted'] and job['reviewUploads']
    google.on_model = check_submission
    google.model_error = requests.Timeout('provider response lost')
    result = review(p)
    assert p.snapshot('first', '1')['jobs'][0]['status'] == 'failed'
    with pytest.raises(StudioError, match='closed'):
        command(p, 'resume', jobId=result['jobId'])
    assert len([c for c in google.calls if c['url'] == BASE + '/interactions']) == 1
    assert all(u['deleted'] for u in saved_job(ws, result)['reviewUploads'])


def saved_job(ws, result):
    with ws.db() as db:
        return json.loads(db.execute('SELECT data FROM jobs WHERE id=?', (result['jobId'],)).fetchone()[0])


@pytest.mark.parametrize('failure', ['upload_lost', 'processing_failed', 'processing_timeout', 'foreign_destination'])
def test_pre_inference_failure_releases_budget_and_never_leaks_a_key(google_setup, monkeypatch, failure):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    if failure == 'upload_lost': google.upload_error = True
    if failure == 'processing_failed': google.state = 'FAILED'
    if failure == 'processing_timeout':
        google.state = 'PROCESSING'
        times = iter([0, 241]); monkeypatch.setattr('studio_video_review.time.monotonic', lambda: next(times))
    if failure == 'foreign_destination': google.destination = 'https://elsewhere.invalid/steal'
    before = p.snapshot('first', '1')['state']['budget']['committed']
    result = review(p)
    current = p.snapshot('first', '1')
    assert current['jobs'][0]['status'] == 'failed'
    assert current['state']['budget']['committed'] == before
    assert current['state']['budget']['reserved'] == 0
    assert not any(c['url'] == BASE + '/interactions' for c in google.calls)
    assert not any('elsewhere.invalid' in c['url'] for c in google.calls)
    assert 'gemini-private-test-key' not in json.dumps(current)
    if failure == 'upload_lost': assert current['jobs'][0]['uploadUnconfirmed']
    assert all(u['deleted'] for u in saved_job(ws, result)['reviewUploads'])


def test_stale_sources_and_bad_timestamps_never_become_current_evidence(google_setup):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    google.report['findings'][0]['seconds'] = 3  # Valid schema, outside actual two-second render.
    review(p)
    assert not p.snapshot('first', '1')['state']['shots'][0].get('mediaReviews')
    google.report['findings'][0]['seconds'] = .5
    record = p.snapshot('first', '1')['state']['shots'][0]['outcomes']['watch']['files'][0]
    google.on_model = lambda: ws.project_path('first', record['path']).write_bytes(b'changed')
    review(p)
    report = p.snapshot('first', '1')['review']['inspections']['S1.SH1']['mediaReviews'][0]
    assert not report['current'] and report['sourceIntegrity'] == 'changed_during_review'


def test_review_account_rotation_stays_pinned_and_no_environment_key_is_used(google_setup, monkeypatch):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    launch = p.launch; p.launch = lambda _: None
    result = review(p); p.launch = launch
    ws.save_connection({'id': accounts['gemini']['id'], 'provider': 'gemini', 'key': 'replacement-private-key'})
    monkeypatch.setenv('GEMINI_API_KEY', 'unrelated-environment-account')
    command(p, 'resume', jobId=result['jobId'])
    assert google.calls and all(c['key'] == 'gemini-private-test-key' for c in google.calls)


def test_new_google_review_can_follow_sampled_review_of_same_render(google_setup):
    p, ws, t, accounts, google = google_setup
    google_setting = ws.services('first')['review']
    configure(p, ws, accounts); render_candidate(p); review(p)
    ws.save_services('first', {**ws.services('first'), 'review': google_setting})
    review(p)
    assert len(p.snapshot('first', '1')['state']['shots'][0]['mediaReviews']) == 2
    with pytest.raises(StudioError, match='already has'): review(p)


def test_gemini_services_are_review_only_and_chat_rejects_keys(google_setup):
    p, ws, t, accounts, google = google_setup
    setting = ws.services('first')['review']
    assert setting['videoFps'] == 4 and 'audioModel' not in setting
    with pytest.raises(StudioError, match='compatible'):
        ws.save_services('first', {'direction': setting})
    for fps in [0, 'NaN', True, 30]:
        with pytest.raises(StudioError): ws.save_services('first', {'review': {**setting, 'videoFps': fps}})
    with pytest.raises(StudioError, match='API keys'):
        command(p, 'chat', message='AIza' + 'x' * 35)


def test_queued_video_review_rechecks_sources_before_any_upload(google_setup):
    p, ws, t, accounts, google = google_setup
    render_candidate(p)
    launch = p.launch; p.launch = lambda _: None
    result = review(p); p.launch = launch
    source = p.snapshot('first', '1')['state']['shots'][0]['outcomes']['watch']['files'][0]
    ws.project_path('first', source['path']).write_bytes(b'changed before submission')
    command(p, 'resume', jobId=result['jobId'])
    assert not google.calls
    assert p.snapshot('first', '1')['jobs'][0]['status'] == 'failed'


def test_silent_video_does_not_claim_an_audio_stream(google_setup):
    p, ws, t, accounts, google = google_setup
    ws.project_path('first', 'projects/first/scripts/part-1.txt').write_text('Hero waits.')
    command(p, 'budget', amountUsd=10); approve(p, 'see'); approve(p, 'request'); review(p)
    report = p.snapshot('first', '1')['state']['shots'][0]['mediaReviews'][0]
    assert not report['evidence']['watchHasAudio'] and not report['evidence']['audio']
    posted = next(c['body'] for c in google.calls if c['url'] == BASE + '/interactions')
    assert not any(part['type'] == 'audio' for part in posted['input'])
