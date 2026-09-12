"""Read-only retake inspection. Never imports a renderer or reserves spend.

The returned evidence is an in-memory projection, not a new approved revision.
Missing semantic reviews are surfaced; this endpoint must not run a model to
manufacture them. Fire remains on the existing separately authorised route.
"""
import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from studio_shot_request import project

QUALIFICATION = ('Software controls are scoped/tested offline. A retake still requires current '
                 'preflight and your explicit Fire approval; no provider call occurs during preparation.')


def _authority(shot):
    result = copy.deepcopy(shot)
    for key in list(result):
        if key.endswith('History') or key == 'splitContinuityRepair' or (
                not key.endswith('Approved') and key + 'Approved' in result):
            result.pop(key)
    # Same historical compiler-output exclusions as review_legacy_envelope.
    for key in ('seedancePrompt', 'keyframePrompt', 'seedreamPrompt', 'referenceSlots', 'keyframeReferenceSlots'):
        result.pop(key, None)
    return result


def prepare(root, episode, scene, shot_id, correction='', expected_batch_id=None):
    try:
        return _prepare(root, episode, scene, shot_id, correction, expected_batch_id)
    except Exception as exc:
        return dict(operation='PREPARE_RETAKE', state='BLOCKED PENDING',
                    scope=dict(project='crystal-bears', episode=episode, scene=scene, shot=shot_id, revision=None),
                    issue='Retake evidence could not be read: ' + str(exc),
                    affectedStages=['REVIEW'], nextAction='Restore the reported evidence and retry read-only preparation.',
                    see='unverified', audio1='unverified', providerCallStatus='no provider call made',
                    providerCalled=False, spendReserved=False, approvalChanged=False,
                    qualification=QUALIFICATION, lineage={}, evidencePath=None,
                    evidence={'failureType':type(exc).__name__, 'reason':str(exc)})


def _prepare(root, episode, scene, shot_id, correction='', expected_batch_id=None):
    root = Path(root).resolve()
    for value in (episode, scene, shot_id):
        if not value or not re.fullmatch(r'[A-Za-z0-9_.-]+', str(value)):
            raise ValueError('Select a valid episode, scene and shot.')
    path = root / 'cb-output' / f'{episode}_scene{scene}_production_package.json'
    card = dict(operation='PREPARE_RETAKE', state='BLOCKED PENDING', issue='',
                scope=dict(project='crystal-bears', episode=episode, scene=scene, shot=shot_id, revision=None),
                affectedStages=['REVIEW'], nextAction='Restore the current shot package.',
                audio1='missing', see='missing', providerCallStatus='no provider call made',
                providerCalled=False, spendReserved=False, approvalChanged=False,
                qualification=QUALIFICATION, evidencePath=str(path), lineage={}, evidence={})

    def stop(state, issue, action, stages):
        card.update(state=state, issue=issue, nextAction=action, affectedStages=stages)
        return card

    try:
        raw = path.read_bytes()
        pkg = json.loads(raw)
        shot = next(s for s in pkg['shots'] if s['shotId'] == shot_id)
        led = next(s for s in pkg['continuityLedger'] if s['shotId'] == shot_id)
    except (OSError, ValueError, KeyError, StopIteration):
        return stop('BLOCKED PENDING', 'Current shot package is unavailable.',
                    'Restore the selected shot package before preparing.', ['REVIEW'])
    card['scope']['revision'] = pkg.get('revision')
    retake = led.get('watchRetake') or {}
    card['lineage'] = copy.deepcopy({k: led.get(k) for k in (
        'batchId', 'watchRetake', 'watchRetakeHistory', 'batchAttempts', 'renderHistory', 'rejections')})
    # Immutable read only when no WAL exists: no schema, journal or lock writes.
    database = root / 'cb-output/state/studio.sqlite3'
    if database.is_file():
        wal = Path(str(database) + '-wal')
        if wal.exists() and wal.stat().st_size:
            return stop('RECOVERY REQUIRED', 'Recovery history has an active database journal.',
                        'Retry preparation when the current state transaction finishes.', ['REVIEW'])
        try:
            with sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True) as conn:
                rows = conn.execute('SELECT data_json FROM production_operations').fetchall()
                operations = [json.loads(row[0]) for row in rows]
                operations = [op for op in operations if op.get('episode') == episode and
                              str(op.get('scene')) == str(scene) and op.get('shotId') == shot_id]
                card['lineage']['operations'] = [{k: op.get(k) for k in (
                    'operationId', 'predecessorOperationId', 'jobId', 'state', 'message',
                    'createdAt', 'updatedAt', 'failure', 'providerTaskIds', 'mediaSubmitted')} for op in operations]
                card['lineage']['events'] = []
                for op in operations:
                    for at, data in conn.execute('SELECT at,data_json FROM production_operation_events WHERE operation_id=? ORDER BY event_id', (op['operationId'],)):
                        card['lineage']['events'].append({'operationId': op['operationId'], 'at': at, 'event': json.loads(data)})
                if any(op.get('kind') == 'submit-watch' and op.get('state') in
                       {'queued', 'running', 'needs-attention', 'recovering'} for op in operations):
                    return stop('RECOVERY REQUIRED', 'A previous submission requires reconciliation.',
                                'Reconcile the existing submission before any new Fire.', ['WATCH'])
        except (sqlite3.Error, OSError, ValueError):
            return stop('RECOVERY REQUIRED', 'Saved recovery history could not be verified.',
                        'Restore readable recovery evidence before another Fire.', ['REVIEW'])
    card['evidence'] = dict(packageHash=hashlib.sha256(raw).hexdigest(),
                            correction=correction, shot=shot,
                            currentState={k: copy.deepcopy(led.get(k)) for k in (
                                'seeActionReadiness', 'departmentWork', 'visionReferenceBinding',
                                'directorCardHandoff', 'voTimingPath', 'voPlacementPath')})
    # Approval evidence is carried exactly, never modified by a WATCH correction.
    for key, label, stage in [('keyframeApproval', 'see', 'SEE'), ('voiceApproval', 'audio1', 'HEAR')]:
        approval = led.get(key) or {}
        file = Path(approval.get('path') or '/')
        if not approval.get('approved') or not file.is_file():
            return stop('BLOCKED PENDING', f'{stage} approved asset is missing.',
                        f'Restore the approved {stage} asset; do not generate a replacement automatically.', [stage])
        card[label] = 'current' if label == 'see' else 'current / immutable'
        card['evidence'][key] = copy.deepcopy(approval)
    batch = led.get('batchId') or retake.get('sourceBatchId')
    if expected_batch_id and expected_batch_id != batch:
        return stop('STALE', 'The selected candidate lineage changed.', 'Reopen the current shot retake.', ['REVIEW'])
    # An unresolved submission must be reconciled before another submission.
    if led.get('submissionUncertain') or retake.get('submissionUncertain'):
        return stop('RECOVERY REQUIRED', 'The prior provider submission is unconfirmed.',
                    'Reconcile the existing submission ID without submitting again.', ['WATCH'])
    match = re.search(r'\(review: (.+?\.json)\)', str(retake.get('stage') or ''))
    report_path = Path(match.group(1)) if match else Path(retake.get('reviewPath') or '/')
    report_root = root / 'cb-output' / 'state' / 'prompt-director'
    if not report_path.resolve().is_relative_to(report_root) or not report_path.is_file():
        return stop('STALE', 'Current Prompt Director evidence needs refreshing.',
                    'Prepare a source-bound Prompt Director review in a separately authorised step.', ['REVIEW'])
    card['evidencePath'] = str(report_path)
    try:
        record = json.loads(report_path.read_bytes())
        snapshot, review = record['snapshot'], record['review']
    except (OSError, ValueError, KeyError):
        return stop('STALE', 'Prompt Director evidence is unreadable.', 'Restore the current review evidence.', ['REVIEW'])
    card['evidence']['promptDirector'] = record
    if correction.strip() != str(retake.get('note') or '').strip():
        return stop('STALE', 'Your proposed correction has not been reviewed in the current plan.',
                    'Review and apply this correction to the shot plan before preparing its Fire request.', ['WATCH', 'REVIEW'])
    from studio_approved_media_projection import watch_shot
    shot = watch_shot(shot, led)
    if snapshot.get('authorities', {}).get('shot') != _authority(shot):
        return stop('STALE', 'The reviewed shot plan differs from the current shot.',
                    'Refresh the reviewed plan against the current shot revision.', ['WATCH', 'REVIEW'])
    refs = snapshot.get('references') or []
    card['evidence']['referenceManifest'] = refs
    for ref in refs:
        asset = Path(ref.get('path') or '/')
        algorithm = 'sha256' if ref.get('sha256') else 'md5' if ref.get('md5') else None
        if not algorithm or not asset.is_file() or hashlib.new(algorithm, asset.read_bytes()).hexdigest() != ref[algorithm]:
            return stop('STALE', f"Reference {ref.get('slot', '?')} content needs verification.",
                        'Refresh the exact reference manifest against current assets.', ['SEE', 'WATCH'])
    # The opening and voice approval must be the assets actually reviewed.
    for key in ('keyframeApproval', 'voiceApproval'):
        approved = led[key]['path']
        audio_path = (snapshot.get('audio') or {}).get('path')
        if approved not in [r.get('path') for r in refs] + [audio_path]:
            return stop('STALE', f'{key} is not bound to the reviewed request.',
                        'Refresh review with the current approved asset.', ['REVIEW'])
    request = project('WATCH', scope=card['scope'], source=shot,
                      direction=snapshot.get('authorities'), refs=refs,
                      audio=snapshot.get('audio'), opening=led['keyframeApproval'],
                      objects=review.get('trackedProductionObjects'),
                      continuity={'geography': shot.get('physicalStaging'), 'dynamicState': review.get('dynamicStateResolution')},
                      prompt=snapshot.get('prompt', ''), reviewed_plans=[{'plan': snapshot.get('watchPlan') or {}}])
    card['evidence']['shotProductionRequest'] = request.record()
    findings = review.get('findings') or []
    if review.get('verdict') != 'READY TO FIRE':
        first = next((f for f in findings if f.get('category') != 'risk'), {})
        return stop('BLOCKED PENDING', first.get('reason') or review.get('summary') or 'Current review has not passed.',
                    first.get('correction') or 'Resolve the current review finding.', ['WATCH', 'REVIEW'])
    try:
        from studio_prompt_director import verify
        verify(snapshot, review)
    except Exception as exc:
        return stop('STALE', 'Exact compiled request review needs refreshing: ' + str(exc),
                    'Refresh the exact payload review before spend disclosure.', ['REVIEW'])
    # Readiness requires a current sealed native request, not this preview alone.
    auth = led.get('pendingSpendAuth') or {}
    if not auth:
        return stop('STALE', 'Current sealed preflight and spend disclosure are missing.',
                    'Prepare a current sealed request and spend disclosure without submitting.', ['REVIEW'])
    try:
        from studio_shot_request import ShotProductionRequest, native_envelope
        from studio_prompt_director import verify_legacy_envelope
        env = auth['envelope']
        if hashlib.sha256(json.dumps(env, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != auth['envelopeHash']:
            raise ValueError('Sealed envelope hash mismatch')
        if ShotProductionRequest.load(env['productionRequest']).request_hash != native_envelope(env).request_hash:
            raise ValueError('Sealed request differs from its execution plan')
        segments = env['executionPlan']['segments']
        if not segments or not any(s.get('promptDirectorSnapshot') == snapshot for s in segments):
            raise ValueError('Sealed request does not contain the current reviewed snapshot')
        verify_legacy_envelope(env)
        if not auth.get('token') or not auth.get('disclosure'):
            raise ValueError('Spend disclosure is incomplete')
    except (ValueError, KeyError, TypeError) as exc:
        return stop('STALE', 'Sealed preflight needs refreshing: ' + str(exc),
                    'Refresh the current request and explicit spend disclosure.', ['REVIEW'])
    card['spendDisclosure'] = auth['disclosure']
    card['envelopeHash'] = auth['envelopeHash']
    return stop('READY FOR RETAKE REVIEW', 'Current request is available for review; Fire still requires explicit approval.',
                'Review the prepared request and its spend disclosure.', ['REVIEW'])
