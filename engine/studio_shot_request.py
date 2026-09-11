"""Immutable projections of existing production authorities, never an editable store.

Hashing proves content identity, not visual recognition or creative quality. Historical
media without a request remains usable and explicitly legacy-unverified.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import tempfile

VERSION = 1


class Stage(str, Enum):
    SEE = 'SEE'
    HEAR = 'HEAR'
    WATCH = 'WATCH'
    TARGETED_EDIT = 'TARGETED_EDIT'
    REVIEW = 'REVIEW'
    POST = 'POST'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@dataclass(frozen=True)
class ShotProductionRequest:
    # Bytes, rather than frozen dataclasses containing mutable dictionaries.
    _bytes: bytes

    @property
    def data(self):
        return json.loads(self._bytes)

    @property
    def request_hash(self):
        return hashlib.sha256(self._bytes).hexdigest()

    @property
    def truth_hash(self):
        return digest(self.data['truth'])

    def record(self):
        return {'schemaVersion': VERSION, 'requestHash': self.request_hash,
                'truthHash': self.truth_hash, 'snapshot': self.data}

    @classmethod
    def load(cls, record):
        if not isinstance(record, dict) or not isinstance(record.get('snapshot'), dict):
            raise ValueError('Production request has no immutable snapshot')
        snapshot = record['snapshot']
        if snapshot.get('schemaVersion') != VERSION:
            raise ValueError('Unsupported production request schema; retain history and prepare a current request')
        if not isinstance(snapshot.get('truth'), dict) or not isinstance(snapshot.get('execution'), dict):
            raise ValueError('Production request needs structured truth and execution')
        Stage(snapshot.get('stage'))
        request = cls(canonical(record['snapshot']))
        if record.get('requestHash') != request.request_hash or record.get('truthHash') != request.truth_hash:
            raise ValueError('Production request integrity mismatch; rebuild from current authorities')
        return request


def build(stage, truth, execution):
    """Callers supply stage-relevant authority content, never UI or storage revisions."""
    return ShotProductionRequest(canonical({'schemaVersion': VERSION,
        'stage': Stage(stage).value, 'truth': truth, 'execution': execution}))


def references(records):
    """Order is semantic. Paths and storage-local IDs are lineage, not truth."""
    return [{k: r.get(k) for k in ('slot', 'role', 'subjectId', 'authorityScope')}
            | {'contentHash': r.get('sha256') or r.get('hash') or r.get('md5'),
               'hashAlgorithm': 'sha256' if r.get('sha256') or r.get('hash') else 'md5' if r.get('md5') else 'unverified'}
            for r in records or []]


def project(stage, *, scope, source, direction, dialogue=(), refs=(), audio=None,
            opening=None, objects=None, continuity=None, prompt='', settings=None,
            edit_scope=None, creative_context=None, reviewed_plans=None):
    """Shared stage projection. No artificial SEE->HEAR or HEAR->SEE dependency."""
    stage = Stage(stage)
    truth = {'scope': scope, 'source': source, 'direction': direction}
    if stage in (Stage.HEAR, Stage.WATCH, Stage.TARGETED_EDIT):
        truth['dialogue'] = dialogue
    if stage != Stage.HEAR:
        truth.update(references=references(refs), objects=objects, continuity=continuity)
    if stage in (Stage.WATCH, Stage.TARGETED_EDIT):
        truth.update(audio=audio, opening=opening)
    if stage == Stage.TARGETED_EDIT:
        if not edit_scope or not edit_scope.get('sourceSha256'):
            raise ValueError('A targeted edit needs its source hash and declared edit scope')
    if creative_context:
        truth['creativeAuthority'] = {k: creative_context[k] for k in
            ('version', 'projectId', 'stage', 'fingerprint') if k in creative_context}
    if reviewed_plans:
        # Compiler/review receipts describe this execution. Only the semantic
        # plan belongs to creative truth; model/routing hashes are not new story.
        truth['reviewedDirection'] = [{k: v for k, v in (p.get('plan') or {}).items()
            if k not in {'sourceHash', 'requestBindingHash', 'origins', 'compatibility',
                         'audioBlocks'}} for p in reviewed_plans]
    execution = {'prompt': prompt, 'settings': settings or {}}
    if creative_context:
        execution['creativeSourceEvidence'] = creative_context
    if reviewed_plans:
        execution['reviewedPlans'] = reviewed_plans
    if stage == Stage.TARGETED_EDIT:
        # Edit operation and media source differ; the underlying approved story
        # remains the same truth as WATCH. Both are covered by requestHash.
        execution['editScope'] = edit_scope
    return build(stage, truth, execution)


def reviewed_plan(record):
    """Retain the plan actually reviewed for this emission, never today's shot.

    The Prompt Director verifies plan fidelity before submission. This projection
    makes its originating plan available to returned-media review and post.
    It does not claim that a rendered image/video was inspected.
    """
    snapshot = record.get('promptDirectorSnapshot') or {}
    if not snapshot:
        return None
    authority = snapshot.get('authorities') or {}
    return {'plan': snapshot.get('watchPlan'),
            'binding': snapshot.get('watchPlanBinding'),
            'revisions': snapshot.get('watchPlanRevisions', []),
            'sourceUnit': authority.get('sourceUnit'),
            'direction': authority.get('specialist') or authority.get('shot'),
            'creativeAuthority': authority.get('creativeAuthority'),
            'sourceBindings': authority.get('sourceBindings'),
            'promptHash': digest(record.get('prompt', snapshot.get('prompt', ''))),
            'reviewHash': digest(record.get('promptDirector') or {}),
            'status': 'typed-plan' if snapshot.get('watchPlan') else 'legacy-authority-snapshot'}


def native_envelope(envelope):
    """Adapt the already reviewed native authority snapshot without re-authoring it."""
    card = envelope.get('directorCardRevision') or {}
    segments = (envelope.get('executionPlan') or {}).get('segments') or []
    # The exact individual emissions, not the summary prompt, bind the render.
    emissions = [{'prompt': s.get('prompt'), 'duration': s.get('durationSec'),
                  'references': references(s.get('references') or []),
                  'audioHash': (s.get('audio') or {}).get('md5'),
                  'contract': {k: (s.get('contract') or {}).get(k) for k in
                               ('provider', 'providerModelId', 'resolution', 'transport')},
                  'generateAudio': s.get('generateAudio')}
                 for s in segments]
    sources = envelope.get('sourceBindings') or {}
    plans = [p for segment in segments if (p := reviewed_plan(segment))]
    snapshots = [(s.get('promptDirectorSnapshot') or {}).get('authorities', {}) for s in segments]
    shot = next(((s.get('sourceUnit') or {}).get('shot') or s['shot']
                 for s in snapshots if s.get('shot')), {})
    refs = envelope.get('references') or []
    opening = [r for r in refs if 'opening' in str(r.get('role', '')).lower()]
    return project(Stage.WATCH, scope={**(envelope.get('learningScope') or {}), 'shotId': envelope.get('shotId')},
        source={'script': sources.get('script'), 'canon': sources.get('canon')},
        direction=card.get('decisions', {}), refs=refs,
        dialogue=shot.get('dialogueLines', shot.get('dialogue', [])),
        opening=references(opening),
        continuity={k: shot[k] for k in ('openingState', 'endingState', 'geography',
                    'shotTransition', 'continuityIn', 'continuityOut') if k in shot},
        audio={'contentHash': (envelope.get('audio') or {}).get('md5'), 'algorithm': 'md5'},
        objects=envelope.get('trackedProductionObjects'),
        creative_context=sources.get('creativeAuthority'), reviewed_plans=plans,
        prompt=envelope.get('prompt', ''), settings={'emissions': emissions,
            'candidateCount': envelope.get('candidateCount'), 'tier': envelope.get('tier')})


def from_project_job(job, prompt=None):
    from studio_director_card import stage_decisions
    stage = Stage(job['kind'].upper())
    shot = job['shot']
    request = job.get('inputs', {}).get('request') or {}
    plan = reviewed_plan(request)
    reviewed_shot = ((request.get('promptDirectorSnapshot') or {}).get('authorities') or {}).get('shot') or {}
    return project(stage,
        scope={'projectId': job['projectId'], 'episode': job['episode'], 'shotId': job['shotId']},
        source={'sourceHash': job.get('sourceHash')},
        direction=stage_decisions(shot, job['kind']),
        dialogue=reviewed_shot.get('dialogueLines', shot.get('dialogue', []))
                 if stage == Stage.WATCH else job.get('inputs', {}).get('dialogue', []),
        refs=request.get('images', job.get('references', [])),
        audio=references(request.get('audio', [])),
        opening=references((shot.get('outcomes', {}).get('see') or {}).get('files', [])),
        objects=shot.get('trackedObjects'),
        creative_context=job.get('creativeAuthority') or request.get('creativeAuthority'),
        reviewed_plans=[plan] if plan else None,
        continuity={k: shot.get(k) for k in ('openingState', 'endingState', 'geography', 'transition')},
        prompt=prompt if prompt is not None else request.get('prompt', ''),
        settings={'model': job.get('binding', {}).get('model'),
                  'duration': request.get('duration', shot.get('duration')),
                  'ratio': request.get('ratio'), 'resolution': request.get('resolution')})


def project_watch(context, shot, request):
    return from_project_job({'kind':'watch', 'shot':shot, 'inputs':{'request':request},
        'projectId':context['project']['id'], 'episode':context.get('episode'),
        'shotId':shot['id'], 'sourceHash':context.get('sourceHash'),
        'binding':request['binding'], 'references':request['images']}, request['prompt'])


def origin(record):
    """Never manufacture old request lineage from today's mutable shot."""
    value = record.get('productionRequest')
    if not value:
        return {'status': 'legacy-unverified', 'originatingRequestHash': None}
    request = ShotProductionRequest.load(value)
    return {'status': 'origin-verified', 'originatingRequestHash': request.request_hash,
            'truthHash': request.truth_hash}


def originating_review_context(record):
    """Read-only evidence for media review and edit handoff, from sealed history."""
    lineage = origin(record)
    if lineage['status'] != 'origin-verified':
        return {**lineage, 'reviewScope': 'No originating request; current context is not historical evidence'}
    request = ShotProductionRequest.load(record['productionRequest'])
    data = request.data
    return {**lineage, 'stage': data['stage'], 'truth': data['truth'],
            'execution': data['execution'],
            'reviewScope': 'Compare actual returned media with this originating request',
            'observed': False, 'approved': False}


@contextmanager
def pinned_media(groups, bindings=None):
    """Copy and hash the same stream; transport never reopens a mutable source.

    A separate private copy is used instead of a hardlink. Remote URLs remain the
    transport's responsibility and are not falsely described as byte-qualified.
    """
    bindings = bindings or {}
    with tempfile.TemporaryDirectory(prefix='studio-request-') as folder:
        result = {}
        for kind, inputs in groups.items():
            result[kind] = []
            expected = bindings.get(kind) or []
            for index, raw in enumerate(inputs or []):
                if str(raw).startswith(('https://', 'http://', 'data:')):
                    result[kind].append(raw)
                    continue
                path = Path(raw)
                slot = Path(folder) / f'{kind}-{index}'
                slot.mkdir()
                target = slot / path.name
                sha, md5 = hashlib.sha256(), hashlib.md5()
                with path.open('rb') as src, target.open('xb') as dst:
                    while chunk := src.read(1024 * 1024):
                        sha.update(chunk); md5.update(chunk); dst.write(chunk)
                ref = expected[index] if index < len(expected) else {}
                wanted = ref.get('sha256') or ref.get('hash')
                if (wanted and wanted != sha.hexdigest()) or (ref.get('md5') and ref['md5'] != md5.hexdigest()):
                    raise ValueError(f'{kind} reference {index + 1} changed after review; no provider was called')
                target.chmod(0o400)
                result[kind].append(str(target))
        yield result
