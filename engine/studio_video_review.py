"""Whole-file Gemini review through the same project job and approval ledger.

The Files and Interactions REST APIs are explicit-credential, bounded and never
retry a model POST. Production supplies verified paths; media cannot invoke tools.
"""
import json
import math
import mimetypes
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit
import uuid

import requests
from pydantic import Field, ValidationError

from studio_transport import MediaReview, provider_error
from studio_workspace import StudioError

HOST = 'https://generativelanguage.googleapis.com'
BASE = HOST + '/v1beta'
SKILL = Path(__file__).resolve().parents[1] / 'skills/video-analysis/SKILL.md'
MAX_BYTES = 512 * 1024 * 1024  # Studio shot-review limit, not Google's maximum.


class VideoReport(MediaReview):
    audioReview: str = Field(max_length=12000)


def review_contract():
    source = SKILL.read_text()
    return source.split('<!-- RUNTIME_REVIEW_START -->', 1)[1].split('<!-- RUNTIME_REVIEW_END -->', 1)[0].strip()


class GeminiVideoClient:
    def __init__(self, key):
        self.key = key

    def request(self, method, url, *, headers=None, **kwargs):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'generativelanguage.googleapis.com'
                or parsed.username or parsed.password or parsed.fragment):
            raise StudioError('Gemini returned an unsupported upload destination.', 'invalid_output')
        try:
            response = requests.request(method, url, headers={'x-goog-api-key': self.key, **(headers or {})},
                                        timeout=(10, 180 if method == 'POST' else 15), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise StudioError('The Gemini response was interrupted. No model request will be retried automatically.',
                              'submission_unknown' if method == 'POST' else 'provider_offline') from None
        if method == 'DELETE' and response.status_code == 404:
            return response
        if not 200 <= response.status_code < 300:
            raise provider_error(response.status_code)
        return response

    @staticmethod
    def data(response):
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (TypeError, ValueError):
            raise StudioError('Gemini returned an unreadable response. No model request was retried.', 'invalid_output') from None

    def upload(self, source, uploads, progress):
        path = Path(source['path'])
        size = path.stat().st_size
        if not 0 < size <= MAX_BYTES:
            raise StudioError('A video-review source exceeds the Studio limit of 512 MB per file.', 'review_size')
        mime = source['mimeType']
        progress('upload', 'Uploading ' + source['label'])
        start = self.request('POST', HOST + '/upload/v1beta/files', headers={
            'X-Goog-Upload-Protocol': 'resumable', 'X-Goog-Upload-Command': 'start',
            'X-Goog-Upload-Header-Content-Length': str(size), 'X-Goog-Upload-Header-Content-Type': mime},
            json={'file': {'display_name': 'Studio review ' + source['type']}})
        upload_url = start.headers.get('X-Goog-Upload-URL')
        if not upload_url:
            raise StudioError('Gemini did not return an upload destination.', 'invalid_output')
        with path.open('rb') as stream:
            progress('upload_finalizing', 'Sending the review source to Gemini')
            value = self.data(self.request('POST', upload_url, headers={
                'Content-Length': str(size), 'X-Goog-Upload-Offset': '0',
                'X-Goog-Upload-Command': 'upload, finalize'}, data=stream)).get('file', {})
        name = value.get('name', '')
        if not re.fullmatch(r'files/[A-Za-z0-9_-]+', name):
            raise StudioError('The upload returned no usable file ID. Cleanup could not be confirmed; check Gemini Files.', 'invalid_output')
        uploads.append({'name': name, 'deleted': False})
        progress('uploaded', 'Uploaded file recorded for cleanup')
        deadline = time.monotonic() + 240
        while value.get('state') != 'ACTIVE':
            if value.get('state') == 'FAILED':
                raise StudioError('Gemini could not process a review source.', 'review_media_failed')
            if value.get('state') not in {'PROCESSING', None, 'STATE_UNSPECIFIED'} or time.monotonic() >= deadline:
                raise StudioError('Gemini did not finish processing the review source in time.', 'review_processing_timeout')
            progress('processing', 'Gemini is processing ' + source['label'])
            time.sleep(2)
            value = self.data(self.request('GET', BASE + '/' + name))
        uri = value.get('uri')
        if uri != BASE + '/' + name:
            raise StudioError('Gemini returned an unexpected file reference.', 'invalid_output')
        return {'type': source['type'], 'uri': uri, 'mime_type': mime}

    def cleanup(self, uploads, progress):
        for uploaded in uploads:
            if uploaded.get('deleted'):
                continue
            name = uploaded.get('name', '')
            try:
                if not re.fullmatch(r'files/[A-Za-z0-9_-]+', name):
                    raise ValueError()
                self.request('DELETE', BASE + '/' + name)
                uploaded['deleted'] = True
            except (StudioError, ValueError):
                uploaded['deleted'] = False
            progress('cleanup', 'Removing temporary Gemini uploads')

    def review(self, model, context, sources, *, fps, contract, uploads, progress):
        try:
            inputs = []
            for source in sources:
                part = self.upload(source, uploads, progress)
                if source['type'] == 'video':
                    part['processing'] = {'type': 'static', 'fps': fps}
                inputs.extend([{'type': 'text', 'text': source['label']}, part])
            inputs.append({'type': 'text', 'text': json.dumps(context, ensure_ascii=False)})
            # This callback persists submission intent before the single billable POST.
            progress('video_analysis', 'Reviewing the supplied video, voice and references with Gemini')
            value = self.data(self.request('POST', BASE + '/interactions', json={
                'model': model, 'input': inputs, 'system_instruction': contract, 'store': False,
                'generation_config': {'max_output_tokens': 6000},
                'response_format': {'type': 'text', 'mime_type': 'application/json', 'schema': VideoReport.model_json_schema()}}))
            if value.get('status') != 'completed':
                raise StudioError('Gemini did not complete the video review. No partial report was applied.', 'invalid_output')
            text = ''.join(part.get('text', '') for step in value.get('steps', [])
                           if step.get('type') == 'model_output' for part in step.get('content', []) if part.get('type') == 'text')
            try:
                report = VideoReport.model_validate_json(text).model_dump()
            except (ValidationError, ValueError, TypeError):
                raise StudioError('Gemini returned an incomplete or invalid review. Current approvals are unchanged.', 'invalid_output') from None
            return {'report': report, 'interactionId': str(value.get('id', ''))[:200],
                    'usage': {k: v for k, v in (value.get('usage') or {}).items()
                              if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0}}
        finally:
            self.cleanup(uploads, progress)


def execute(production, job):
    pid, inputs = job['projectId'], job['reviewInputs']
    ws, transport = production.ws, production.transport
    records = [inputs[k] for k in ('watch', 'see', 'hear', 'previous', 'next') if inputs.get(k)] + inputs['references']
    for record in records:
        production.assert_artifact(pid, {'files': [record]})
    fps = job['binding'].get('videoFps', 4)
    evidence = {'kind': 'video', 'processing': 'static', 'fps': fps, 'frames': [], 'audio': [], 'references': [], 'videos': [], 'joins': [],
                'scope': f'Complete current render, available neighbours and bounded hard-cut auditions, with source audio where present. Gemini samples video at {fps} frames per second; this is not every-frame certification.',
                'omittedApprovedReferences': inputs['omittedApprovedReferences']}
    sources = []
    for name, label, kind in [('watch', 'Current WATCH render', 'video'), ('previous', 'Previous approved shot — incoming cut context', 'video'),
                              ('next', 'Next approved shot — outgoing cut context', 'video'),
                              ('hear', 'Approved HEAR — voice authority', 'audio'), ('see', 'Approved SEE opening', 'image')]:
        if inputs.get(name):
            sources.append((inputs[name], label, kind))
    sources += [(r, r['name'] + ' — ' + r['role'], 'image') for r in inputs['references']]
    from studio_media_review import prepare_join_evidence
    join_evidence = prepare_join_evidence(production, job)
    sources += [(r, r['label'], 'video') for r in join_evidence]
    records += join_evidence
    prepared = []
    production.progress(job, 'review_sources', 'Checking exact video, voice and reference files')
    for record, label, kind in sources:
        path = ws.project_path(pid, record['path'])
        if not 0 < path.stat().st_size <= MAX_BYTES:
            raise StudioError('A review source exceeds the Studio limit of 512 MB per file.', 'review_size')
        mime = mimetypes.guess_type(path.name)[0] or ''
        if kind in {'video', 'audio'}:
            try:
                probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                                                 check=True, capture_output=True, timeout=30).stdout)
                duration = float(probe['format']['duration'])
                if not math.isfinite(duration) or not 0 < duration <= 35 or not any(s['codec_type'] == kind for s in probe['streams']):
                    raise ValueError()
            except (OSError, subprocess.SubprocessError, ValueError, KeyError):
                raise StudioError('Studio media review needs a valid shot or voice file up to 35 seconds.', 'review_duration') from None
            entry = {**record, 'label': label, 'duration': duration}
            if kind == 'video':
                has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])
                entry.update(hasAudio=has_audio, start=0, end=duration)
                evidence['joins' if record in join_evidence else 'videos'].append(entry)
                if record == inputs['watch']:
                    evidence.update(duration=duration, watchHasAudio=has_audio)
            else:
                evidence['audio'].append(entry)
        else:
            transport.verify_media(path, 'image')
            evidence['references'].append({**record, 'label': label})
        # The production engine already emits MP4, WAV and PNG/JPEG. Fail before
        # uploads for an unsupported legacy file; never silently omit its audio.
        mime = {'audio/x-wav': 'audio/wav', 'video/quicktime': 'video/mov'}.get(mime, mime)
        if mime not in {'video/mp4', 'video/mov', 'video/webm', 'audio/wav', 'audio/mpeg', 'image/png', 'image/jpeg', 'image/webp'}:
            raise StudioError('Convert this unsupported review source to MP4, WAV or PNG before reviewing it.', 'invalid_media')
        prepared.append({'path': path, 'type': kind, 'mimeType': mime, 'label': label})
    from studio_director_card import REVIEW_CRITERIA
    context = {'creativeReviewCriteria': REVIEW_CRITERIA, 'project': job['context']['project'], 'projectBible': job['context']['bible'],
               'script': job['context']['script'], 'shot': inputs['shot'], 'directorCardRevision': inputs.get('directorCardRevision'),
               'previousShot': inputs.get('previous'), 'nextShot': inputs.get('next'), 'evidence': evidence}
    if len(json.dumps(context)) > 200000:
        raise StudioError('The review context exceeds the current limit. Use a smaller reference brief.', 'context_limit')
    connection, key = ws.credential(job['binding']['connectionId'], job['binding']['revision'])
    job['reviewUploads'] = []
    def progress(phase, label):
        if phase == 'upload_finalizing':
            job['uploadUnconfirmed'] = True
        elif phase == 'uploaded':
            job['uploadUnconfirmed'] = False
        if phase == 'video_analysis':
            job['reviewSubmitted'] = True
        job['cleanupPending'] = any(not u.get('deleted') for u in job['reviewUploads'])
        production.progress(job, phase, label)
    response = transport.review_video(connection, key, job['binding']['model'], context, prepared, fps=fps,
                                      contract=job['videoReviewContract'], uploads=job['reviewUploads'], progress=progress)
    report = VideoReport.model_validate(response['report']).model_dump()
    if any(not math.isfinite(f['seconds']) or f['seconds'] > evidence['duration'] for f in report['findings']):
        raise StudioError('The video reviewer returned a time outside this shot. No report was applied.', 'invalid_output')
    job['audioReview'] = report['audioReview']
    result = {'id': uuid.uuid4().hex, 'jobId': job['id'], 'fingerprint': inputs['fingerprint'], 'candidateId': inputs['watch']['candidateId'],
              'directorCardRevision': inputs.get('directorCardRevision'),
              'binding': job['binding'], 'at': time.time(), 'evidence': evidence, **report, 'sourceIntegrity': 'verified',
              'reviewContractHash': job['videoReviewContractHash'], 'interactionId': response.get('interactionId'),
              'usage': response.get('usage', {}), 'cleanupPending': job.get('cleanupPending', False),
              'meaning': 'Advisory review of the submitted video and audio. Sampling can miss brief faults. Exact lip sync, emotional success and broadcast readiness still require human review.'}
    try:
        for record in records:
            production.assert_artifact(pid, {'files': [record]})
    except StudioError:
        result['sourceIntegrity'] = 'changed_during_review'
        result['meaning'] += ' A source changed during review; this report is historical.'
    job['reviewResult'] = result
    production.progress(job, 'report_saved', 'Video review saved against this exact render version')
    return result


def cleanup_job(production, job):
    """A user-requested cleanup retries DELETE only, never upload or inference."""
    connection, key = production.ws.credential(job['binding']['connectionId'], job['binding']['revision'])
    uploads = job.get('reviewUploads', [])
    production.transport.cleanup_video_uploads(connection, key, uploads, lambda *_: None)
    with production.ws.db() as db:
        db.execute('BEGIN IMMEDIATE')
        saved = json.loads(db.execute('SELECT data FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
        saved.update(reviewUploads=uploads, cleanupPending=any(not u.get('deleted') for u in uploads))
        if saved.get('reviewResult'):
            saved['reviewResult']['cleanupPending'] = saved['cleanupPending']
        production._job(db, saved)
        state = production._load(db, job['projectId'], job['episode'])
        for shot in state['shots']:
            for report in shot.get('mediaReviews', []):
                if report.get('id') == (saved.get('reviewResult') or {}).get('id'):
                    report['cleanupPending'] = saved['cleanupPending']
        production._message(state, 'agent', 'Gemini upload cleanup still needs attention.' if saved['cleanupPending'] else 'Temporary Gemini uploads deleted. No analysis was repeated.')
        production._save(db, job['projectId'], job['episode'], state)
