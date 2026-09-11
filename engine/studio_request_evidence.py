"""Evidence at the HTTP boundary, separate from approval and creative success.

Only explicitly scoped production calls are recorded. Bodies (including signed media
URLs) are private; headers and credentials are never part of the record. A receipt
proves a JSON body reached the adapter, not delivery, visual conformance or acting.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
import uuid


_scope = ContextVar('studio_request_evidence', default=None)


class RequestEvidenceError(ValueError):
    # Local mismatch is never transient and must not trigger an adapter retry.
    status_code = 422


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def _leaves(value, path='direction'):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f'{path}/{key}')
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, f'{path}/{index}')
    elif isinstance(value, str) and value.strip():
        yield path, value


def authority_inventory(authorities):
    """Record exact supplied authorities, not a claim that unprovided files were read."""
    rows = []
    for name, value in authorities.items():
        if value is None:
            rows.append({'role':name,'status':'unavailable','hash':None})
        else:
            rows.append({'role':name,'status':'consumed snapshot','hash':digest(value),
                         'version':value.get('version', value.get('revision')) if isinstance(value,dict) else None})
    from studio_creative_authority import resolve
    shot=authorities.get('shot') or {}
    resolution=resolve((shot.get('directorCard') or {}).get('instructions') or [], shot.get('instructionContext') or {})
    return {'sources':rows,'precedence':resolution,
            'boundary':'Hashes identify supplied content. Absent script, skill or reference observations remain unverified.'}


def prompt_text(body):
    if 'prompt' in body:
        return str(body['prompt'])
    return '\n'.join(item.get('text', '') for item in body.get('content', [])
                     if item.get('type') == 'text')


def inclusion_map(direction, prompt):
    """Literal evidence only. Paraphrases require assessment, never an invented pass."""
    rows = []
    for path, value in _leaves(direction):
        variants = (value, json.dumps(value, ensure_ascii=False)[1:-1])
        matched = next((v for v in variants if v in prompt), None)
        rows.append({'requirementId': path, 'sourceHash': digest(value), 'requiredText': value,
                     'status': 'literal-inclusion' if matched else 'unverified',
                     'providerRange': ([prompt.index(matched), prompt.index(matched) + len(matched)]
                                       if matched else None)})
    return {'sourceCoverage': 'source-available' if rows else 'source-unavailable',
            'requirements': rows, 'unverified': [r['requirementId'] for r in rows
                                               if r['status'] == 'unverified'],
            'semanticCompleteness': 'not-assessed', 'screenPerformance': 'unverified'}


@contextmanager
def capture(folder, metadata, *, expected_prompt=None, direction=None, received=None,
            expected_fields=None, expected_media_counts=None):
    state = {'folder': Path(folder), 'metadata': metadata, 'expectedPrompt': expected_prompt,
             'direction': direction or {}, 'received': received,
             'expectedFields': expected_fields or {}, 'expectedMediaCounts': expected_media_counts or {}}
    token = _scope.set(state)
    try:
        yield
    finally:
        _scope.reset(token)


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def observe(send, endpoint, body):
    scope = _scope.get()
    if scope is None or body is None:
        return send()
    # Snapshot before the network call; later body mutation cannot rewrite evidence.
    body = json.loads(json.dumps(body, ensure_ascii=False, allow_nan=False))
    prompt = prompt_text(body)
    expected = scope['expectedPrompt']
    integrity = expected is None or prompt == expected
    mismatches = [key for key, value in scope['expectedFields'].items() if body.get(key) != value]
    counts = {'image': len(body.get('image', [])) if isinstance(body.get('image'), list)
              else int(bool(body.get('image'))), 'audio': 0, 'video': 0}
    for item in body.get('content', []):
        kind = item.get('type', '').removesuffix('_url')
        if kind in counts:
            counts[kind] += 1
    mismatches += [kind + ' references' for kind, value in scope['expectedMediaCounts'].items()
                   if counts.get(kind) != value]
    url = urlsplit(endpoint)
    record = {'schemaVersion': 1, 'id': uuid.uuid4().hex, 'createdAt': time.time(),
              'origin': scope['metadata'], 'endpoint': url.scheme + '://' + url.netloc + url.path,
              'body': body, 'bodyHash': digest(body), 'promptHash': digest(prompt),
              'compiledPromptIntegrity': 'matched' if expected is not None and integrity else
                                         'unverified' if expected is None else 'failed',
              'requestFieldMismatches': mismatches, 'mediaCounts': counts,
              'directionTrace': inclusion_map(scope['direction'], prompt),
              'state': 'prepared-at-http-boundary', 'providerCalled': False}
    from studio_shot_request import build, ShotProductionRequest
    inherited = scope['metadata'].get('productionRequest')
    truth = {'direction': scope['direction'], 'authorityStatus': 'legacy-unverified'}
    stage = str(scope['metadata'].get('stage') or 'WATCH').upper()
    if stage not in {'SEE', 'HEAR', 'WATCH', 'TARGETED_EDIT', 'REVIEW', 'POST'}:
        stage = 'WATCH'
    if inherited:
        # Independently verify the persisted authority snapshot before any HTTP call.
        try:
            authority = ShotProductionRequest.load(inherited)
            truth = authority.data['truth']
            stage = authority.data['stage']
            record['originatingRequestHash'] = authority.request_hash
        except (ValueError, KeyError, TypeError) as exc:
            mismatches.append('production request integrity: ' + str(exc))
    # Bind actual serialized provider content separately from semantic truth.
    # URI/data inputs are retained only in the existing private request record.
    boundary = build(stage, truth, {'endpoint': record['endpoint'], 'bodyHash': record['bodyHash']})
    record['productionRequest'] = boundary.record()
    record['requestHash'] = boundary.request_hash
    from studio_delivery_contract import delivery_snapshot
    from studio_creative_authority import resolve
    source = scope['direction'] or {}
    instructions = source.get('instructions', [])
    if not instructions:
        instructions = (source.get('directorDecisions') or {}).get('instructions', [])
    resolution = resolve(instructions, scope['metadata']) if instructions else None
    if resolution:
        missing = [r['id'] for r in resolution['instructions']
                   if r['resolution'] == 'emitted' and r['required'] and r['text'] not in prompt]
        mismatches.extend('required instruction ' + key for key in missing)
        mismatches.extend(c['reason'] for c in resolution['conflicts'])
    record['deliveryPackage'] = delivery_snapshot(scope['metadata'], source, prompt, body, resolution)
    path = scope['folder'] / (record['id'] + '.json')

    def save():
        _write(path, record)
        if scope['received']:
            scope['received']({k: record[k] for k in
                               ('id', 'bodyHash', 'promptHash', 'state', 'providerCalled')} |
                              {'path': str(path)})

    if not integrity or mismatches:
        record['state'] = 'blocked-before-http'
        save()
        detail = ', '.join(mismatches) if mismatches else 'compiled direction'
        raise RequestEvidenceError(f'Provider request lost or changed {detail}. '
                         'Recompile the current shot; no provider was called.')
    try:
        save()
        record.update(state='submission-unknown', providerCalled=True)
        save()
    except OSError as exc:
        raise RequestEvidenceError('Cannot save provider request evidence; no provider was called.') from exc
    try:
        response = send()
    except BaseException as exc:
        # Transport errors cannot prove whether a paid request was accepted.
        response = getattr(exc, 'response', None)
        if response is not None:
            record.update(state='response-received', httpStatus=getattr(response, 'status_code', None))
            try:
                save()
            except OSError:
                pass  # Keep the actual provider error; the saved attempt remains unknown.
        raise
    record.update(state='response-received', httpStatus=getattr(response, 'status_code', None))
    try:
        save()
    except OSError:
        # Do not discard a task ID after a paid request because the secondary audit
        # update failed. Its pre-submit receipt remains conservatively unknown.
        pass
    return response
