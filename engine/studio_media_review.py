"""Opt-in review of verified render samples and actual audio, without approval powers."""
import json
import math
import subprocess
import time
import uuid

from studio_editing import fields
from studio_review import verified_file
from studio_transport import MediaReview
from studio_workspace import StudioError, digest


def manifest(production, context, state, shot):
    pid = context['project']['id']
    watch = shot.get('outcomes', {}).get('watch', {})
    if watch.get('status') not in {'candidate', 'approved'} or not watch.get('files'):
        raise StudioError('Prepare a WATCH render before requesting a media review.', 'review_unavailable')
    def record(artifact):
        file = (artifact.get('files') or [None])[0]
        if not verified_file(production.ws, pid, file):
            raise StudioError('A media-review source changed or is missing. Review its current version.', 'stale')
        return {'candidateId': artifact['id'], **file}
    result = {'watch': record(watch), 'shot': fields(shot),
              'sourceSignature': production.source_signature(context, shot), 'references': []}
    for name in ('see', 'hear'):
        value = shot.get('outcomes', {}).get(name, {})
        if value.get('status') == 'approved':
            result[name] = record(value)
    for ref in production.assets(context, shot):
        if ref.get('approvalStatus') == 'approved' and verified_file(production.ws, pid, ref):
            result['references'].append(ref)
    result['omittedApprovedReferences'] = [r['name'] for r in result['references'][5:]]
    result['references'] = result['references'][:5]
    index = state['shots'].index(shot)
    if index:
        previous = state['shots'][index - 1]
        artifact = previous.get('outcomes', {}).get('watch', {})
        if artifact.get('status') == 'approved':
            result['previous'] = {**record(artifact), 'shotId': previous['id'],
                                  'scene': previous['scene'], 'camera': previous['camera'], 'geography': previous['geography']}
    result['fingerprint'] = digest(result)
    return result


def current_reports(production, context, state, shot):
    try:
        fingerprint = manifest(production, context, state, shot)['fingerprint']
    except StudioError:
        fingerprint = None
    return [{**r, 'current': fingerprint == r['fingerprint'] and r.get('sourceIntegrity') == 'verified'} for r in shot.get('mediaReviews', [])]


def reserve(production, db, context, state, shot, payload):
    if not shot:
        raise StudioError('Select a rendered shot to review.')
    from studio_production import money
    pid, ep = context['project']['id'], str(payload['episode'])
    if db.execute("SELECT id FROM jobs WHERE project=? AND episode=? AND state IN ('queued','running','pending','unknown')", (pid, ep)).fetchone():
        raise StudioError('Finish or recover the current job before requesting media review.', 'job_active')
    inputs = manifest(production, context, state, shot)
    if payload.get('reviewId') != inputs['watch']['candidateId']:
        raise StudioError('Review the current render before requesting analysis.', 'stale')
    if any(r['fingerprint'] == inputs['fingerprint'] and r.get('sourceIntegrity') == 'verified' for r in shot.get('mediaReviews', [])):
        raise StudioError('This version already has a media review. Read its report below.', 'review_exists')
    binding = production.ws.binding(pid, 'review')
    cost = money(binding['estimateUsd'])
    budget = state['budget']
    if budget['allowance'] - budget['committed'] - budget['reserved'] < cost:
        raise StudioError('The episode allowance does not cover the configured media-review estimate.', 'budget_required')
    budget['reserved'] += cost
    job = {'id': uuid.uuid4().hex, 'projectId': pid, 'episode': ep, 'shotId': shot['id'],
           'kind': 'media_review', 'status': 'queued', 'binding': binding, 'estimate': cost,
           'sourceHash': context['sourceHash'], 'context': context, 'reviewInputs': inputs,
           'createdAt': time.time(), 'progress': {'phase': 'queued', 'label': 'Media review queued', 'updatedAt': time.time()}}
    import os
    job['pid'] = os.getpid()
    production._job(db, job)
    return job


def execute(production, job):
    pid, inputs = job['projectId'], job['reviewInputs']
    ws, transport = production.ws, production.transport
    production.progress(job, 'review_sources', 'Checking the exact render, approved references and voice')
    records = [inputs[k] for k in ('watch', 'see', 'hear', 'previous') if inputs.get(k)] + inputs['references']
    for record in records:
        production.assert_artifact(pid, {'files': [record]})
    folder = ws.project_path(pid, f"projects/{pid}/media/reviews/{job['id']}")
    folder.mkdir(parents=True, exist_ok=True)
    def run(args):
        try:
            return subprocess.run(args, capture_output=True, check=True, timeout=90)
        except (OSError, subprocess.SubprocessError):
            raise StudioError('The render samples could not be prepared. Current outcomes are preserved.', 'review_media_failed') from None
    def probe(record):
        path = ws.project_path(pid, record['path'])
        data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]).stdout)
        duration = float(data['format']['duration'])
        if not math.isfinite(duration) or not 0 < duration <= 35:
            raise StudioError('Media review supports rendered shots and voices up to 35 seconds.', 'review_duration')
        return path, duration, any(s['codec_type'] == 'audio' for s in data['streams'])
    path, duration, has_audio = probe(inputs['watch'])
    images, audio, evidence = [], [], {'duration': duration, 'frames': [], 'audio': [], 'references': [],
                                     'scope': 'Up to 12 sampled current-shot frames, up to 2 preceding frames, approved references and extracted soundtracks. Not continuous video analysis.'}
    def timestamps(source):
        data = json.loads(run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
            '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(source)]).stdout)
        values = [float(f['best_effort_timestamp_time']) for f in data['frames'] if 'best_effort_timestamp_time' in f]
        if not values or any(not math.isfinite(v) or v < 0 or v > 35 for v in values):
            raise StudioError('The render has no usable frame timestamps.', 'review_media_failed')
        return values
    def frame(source, seconds, label):
        output = folder / f'frame-{len(images):02}.png'
        run(['ffmpeg', '-v', 'error', '-ss', str(max(0, seconds - .001)), '-i', str(source), '-frames:v', '1', '-vf', 'scale=1024:-2', '-y', str(output)])
        transport.verify_media(output, 'image')
        file = production.file_record(pid, output)
        images.append((label, output));evidence['frames'].append({'label': label, 'seconds': seconds, **file})
    production.progress(job, 'sample_frames', 'Extracting timestamped frames from the actual render')
    times = timestamps(path)
    for index in sorted({round((len(times) - 1) * i / 11) for i in range(12)}):
        seconds = times[index]
        frame(path, seconds, f"Current shot {inputs['shot']['id']} at {seconds:.3f}s")
    if inputs.get('previous'):
        previous, length, _ = probe(inputs['previous'])
        previous_times = timestamps(previous)
        for seconds in sorted({min(previous_times, key=lambda t: abs(t - max(0, length - .5))), previous_times[-1]}):
            frame(previous, seconds, f"Preceding approved shot {inputs['previous']['shotId']} at {seconds:.3f}s (incoming join)")
    for label, ref in ([('Approved SEE opening', inputs['see'])] if inputs.get('see') else []) + [(r['name'] + ' — ' + r['role'], r) for r in inputs['references']]:
        images.append((label, ws.project_path(pid, ref['path'])));evidence['references'].append({'label': label, **ref})
    production.progress(job, 'extract_audio', 'Extracting the actual render soundtrack and approved HEAR')
    for name, label in (('watch', 'Actual WATCH soundtrack'), ('hear', 'Approved HEAR performance')):
        if name not in inputs:
            continue
        source, length, audible = probe(inputs[name])
        if not audible:
            continue
        output = folder / f'{name}.wav'
        run(['ffmpeg', '-v', 'error', '-i', str(source), '-vn', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', '-y', str(output)])
        transport.verify_media(output, 'audio')
        audio.append((label, output));evidence['audio'].append({'label': label, 'duration': length, **production.file_record(pid, output)})
    evidence['watchHasAudio'] = has_audio
    evidence['omittedApprovedReferences'] = inputs['omittedApprovedReferences']
    context = {'shot': inputs['shot'], 'previousShot': inputs.get('previous'),
               'projectBible': job['context']['bible'], 'evidence': evidence}
    if len(json.dumps(context)) > 200000:
        raise StudioError('The review context exceeds the current limit. Use a smaller production sequence or reference brief.', 'context_limit')
    connection, key = ws.credential(job['binding']['connectionId'], job['binding']['revision'])
    # Persist each returned report. A lost POST response is uncertain and is never retried automatically.
    if audio:
        job['reviewSubmitted'] = True
        production.progress(job, 'listen', 'Sending extracted soundtracks for audio review')
        job['audioReview'] = transport.review_audio(connection, key, job['binding']['audioModel'], {'shot': inputs['shot'], 'audioSources': evidence['audio']}, audio)
        production.progress(job, 'audio_received', 'Audio report received and saved')
    else:
        job['audioReview'] = 'No audio stream was available in the reviewed sources. No listening request was made.'
    context['audioReview'] = job['audioReview']
    job['reviewSubmitted'] = True
    production.progress(job, 'visual_review', 'Reviewing sampled frames against approved references and the audio report')
    visual = MediaReview.model_validate(transport.review_frames(connection, key, job['binding']['model'], context, images)).model_dump()
    if any(not math.isfinite(f['seconds']) or f['seconds'] > duration for f in visual['findings']):
        raise StudioError('The reviewer returned a timestamp outside this render. The report was not applied.', 'invalid_output')
    result = {'id': uuid.uuid4().hex, 'fingerprint': inputs['fingerprint'], 'candidateId': inputs['watch']['candidateId'],
              'binding': job['binding'], 'at': time.time(), 'evidence': evidence, 'audioReview': job['audioReview'], **visual,
              'sourceIntegrity': 'verified',
              'meaning': 'Advisory media review. Sampling can miss motion faults and cannot certify exact lip sync, emotional success or broadcast readiness.'}
    # Recheck originals after potentially long provider calls.
    try:
        for record in records:
            production.assert_artifact(pid, {'files': [record]})
    except StudioError:
        result['sourceIntegrity'] = 'changed_during_review'
        result['meaning'] += ' A source changed during review. This report is retained as history and must not be applied to current work.'
    job['reviewResult'] = result
    production.progress(job, 'report_saved', 'Media report received; attaching it to this exact version')
    return result
