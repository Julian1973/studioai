"""Five producer decisions over existing production services.

This stores operation progress only. Plans, approvals, assets, spend tokens and
provider jobs remain owned by the underlying Studio adapter.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import time
import uuid


LABELS = {
    'prepare': 'Prepare Scene',
    'plan': 'Approve Plan & Create Images',
    'images': 'Approve Images & Create Audio',
    'audio': 'Approve Audio & Render',
    'film': 'Approve & Next',
}
STEPS = {
    'prepare': ['prepare_plan'],
    'plan': ['approve_plan', 'create_images', 'review_images'],
    'images': ['approve_images', 'create_audio', 'review_audio'],
    'audio': ['approve_audio', 'align_timing', 'prepare_render', 'submit_render', 'review_film'],
    'film': ['approve_film', 'assemble', 'prepare_next'],
}
PHRASES = {
    'prepare_plan': 'Preparing direction and storyboard',
    'approve_plan': 'Recording your plan decision',
    'create_images': 'Creating opening images', 'review_images': 'Checking opening images',
    'approve_images': 'Recording your image decision',
    'create_audio': 'Creating the voice performance', 'review_audio': 'Checking audio and cues',
    'approve_audio': 'Recording your audio decision', 'align_timing': 'Aligning action and voice',
    'prepare_render': 'Checking the final animation request',
    'submit_render': 'Creating animation', 'review_film': 'Reviewing returned animation',
    'approve_film': 'Recording your film decision', 'assemble': 'Adding the accepted take to the scene',
    'prepare_next': 'Preparing what comes next',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class DecisionRequired(Exception):
    def __init__(self, issue, proposed, preserved=(), evidence=None, retrySafe=False):
        super().__init__(issue)
        self.detail = dict(issue=issue, proposed=proposed, preserved=list(preserved), evidence=evidence, retrySafe=retrySafe)


def scope_key(scope):
    keys = ('projectId', 'episode', 'scene', 'unit')
    if set(scope) != set(keys) or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', str(scope[k])) for k in keys):
        raise ValueError('Select a project, episode, scene and production unit.')
    return digest({k: str(scope[k]) for k in keys})


class Journey:
    def __init__(self, store, adapter):
        self.store, self.adapter = store, adapter

    def view(self, scope):
        key = scope_key(scope)
        # Status reads use atomic persisted snapshots. They must not contend with
        # the execution lease; accept/tick still lock and validate current bindings.
        state = self.store.read(key)
        current = self.adapter.snapshot(scope)
        if state and state.get('operation'):
            op = state['operation']
            if op['status'] in ('running', 'queued'):
                return self._view(state, current, busy=True)
        state = state or dict(scope=scope, revision=0, actions=0, corrections=0, history=[], commands={})
        return self._view(state, current)

    def _view(self, state, current, busy=False):
        phase = current['phase']
        if phase not in LABELS and phase not in ('complete', 'dependency'):
            raise ValueError('The production state cannot be displayed.')
        silent = not current.get('requiresAudio', True)
        label = LABELS.get(phase)
        if phase == 'images' and silent:
            label = 'Approve Images & Render'
        disclosure = deepcopy(current.get('disclosure') or {'limitUsd': 0, 'operations': []})
        limit = disclosure.get('limitUsd', 0)
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit < 0:
            raise ValueError('A finite cost disclosure is required.')
        binding = digest({'scope': state['scope'], 'phase': phase, 'source': current['binding'],
                          'review': current.get('review'), 'disclosure': disclosure})
        op = deepcopy(state.get('operation'))
        retry_safe = bool(op and (op.get('decision') or {}).get('retrySafe'))
        corrected = bool(op and op.get('status') == 'needs-decision' and op.get('blockedBinding')
                         and (op['blockedBinding'] != current['binding'] or retry_safe)
                         and (op.get('pending') != 'submit_render' or retry_safe))
        if corrected:
            op['status'] = 'superseded'
        return dict(scope=state['scope'], revision=state['revision'], phase=phase,
                    corrected=corrected,
                    primary=None if busy or (state.get('operation', {}).get('status') == 'needs-decision' and not corrected) or phase in ('complete', 'dependency') else label,
                    busy=busy, review=current.get('review'), disclosure=disclosure, binding=binding,
                    operation=op, normalActionCount=state['actions'],
                    correctionActionCount=state['corrections'], dependency=current.get('dependency'),
                    next=current.get('next'), concerns=current.get('concerns', []))

    def accept(self, scope, payload, actor):
        key = scope_key(scope)
        command = str(payload.get('commandId') or '')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', command) or not actor:
            raise ValueError('A decision identity is required.')
        with self.store.lock(key):
            state = self.store.read(key) or dict(scope=scope, revision=0, actions=0,
                                                 corrections=0, history=[], commands={})
            if command in state['commands']:
                return deepcopy(state['commands'][command])
            if state.get('operation', {}).get('status') in ('queued', 'running'):
                return {'operationId': state['operation']['id'], 'existing': True}
            current = self.adapter.snapshot(scope)
            view = self._view(state, current)
            if payload.get('expectedRevision') != state['revision'] or payload.get('binding') != view['binding']:
                raise DecisionRequired('This review changed in another window.', 'Review the current version.', current.get('preserved', []))
            phase = view['phase']
            if not view['primary']:
                raise DecisionRequired('This unit is waiting for approved continuity.', 'Approve the preceding result.', current.get('preserved', []))
            if payload.get('action') != phase:
                raise ValueError('Use the current production action.')
            steps = list(STEPS[phase])
            if phase == 'images' and not current.get('requiresAudio', True):
                steps = ['approve_images', 'align_timing', 'prepare_render', 'submit_render', 'review_film']
            op = dict(id=uuid.uuid4().hex, status='queued', phase=phase, steps=steps,
                      completed=[], receipts={}, pending=None, actor=actor,
                      reviewedBinding=current['binding'], review=deepcopy(current.get('review')),
                      grant=deepcopy(view['disclosure']), startedAt=time.time(),
                      message='Starting '+view['primary'], decision=None)
            correction = view['corrected'] or any(h.get('action') == phase for h in state['history'])
            state.update(operation=op, revision=state['revision']+1, actions=state['actions']+(0 if correction else 1),
                         corrections=state['corrections']+(1 if correction else 0))
            result = {'operationId': op['id'], 'revision': state['revision']}
            state['commands'][command] = result
            state['history'].append({'at': time.time(), 'operation': op['id'], 'action': phase,
                                     'actor': actor, 'binding': view['binding'], 'grant': op['grant']})
            self.store.save(key, state)
            return result

    def recover(self, scope):
        """Check the existing receipt/job. This never starts a replacement operation."""
        key = scope_key(scope)
        with self.store.lock(key):
            state = self.store.read(key)
            op = (state or {}).get('operation') or {}
            if op.get('status') == 'needs-decision' and op.get('pending'):
                op.update(status='running', decision=None, message='Checking the saved operation')
                self.store.save(key, state)

    def tick(self, scope):
        """Execute at most one step. Polling can resume a persisted job, never replay it."""
        key = scope_key(scope)
        with self.store.lock(key):
            state = self.store.read(key)
            if not state or state.get('operation', {}).get('status') not in ('queued', 'running'):
                return
            op = state['operation']
            remaining = [s for s in op['steps'] if s not in op['completed']]
            if not remaining:
                op.update(status='complete', message='Ready for your review')
                state['revision'] += 1
                self.store.save(key, state)
                return
            step = remaining[0]
            try:
                if op['pending']:
                    result = self.adapter.reconcile(scope, step, deepcopy(op))
                else:
                    # Persist intent BEFORE dispatch. Unknown acceptance is reconciled,
                    # never silently replayed after process death.
                    op.update(status='running', pending=step, message=PHRASES[step])
                    self.store.save(key, state)
                    result = self.adapter.execute(scope, step, deepcopy(op))
                if not isinstance(result, dict) or result.get('status') not in ('pending', 'complete'):
                    raise ValueError('The production service did not return a supported result.')
                op['receipts'][step] = deepcopy(result)
                if result['status'] == 'complete':
                    op['completed'].append(step)
                    op['pending'] = None
                op['message'] = result.get('message', PHRASES[step])
            except DecisionRequired as exc:
                op.update(status='needs-decision', decision=exc.detail, message=exc.detail['issue'],
                          blockedBinding=self._failure_snapshot(scope).get('binding'))
            except Exception as exc:
                op.update(status='needs-decision', message='Preparation needs attention',
                          blockedBinding=self._failure_snapshot(scope).get('binding'),
                          decision=dict(issue=str(exc), proposed='Review the saved issue and resume this operation.',
                                        preserved=self._failure_snapshot(scope).get('preserved', [])))
            self.store.save(key, state)

    def _failure_snapshot(self, scope):
        # A projection failure must not erase the durable failure of the operation.
        try:
            return self.adapter.snapshot(scope)
        except Exception:
            return {}


class StudioStore:
    """Use the existing Studio database/document transaction layer; no migration."""
    def __init__(self, root):
        self.root = Path(root)

    def lock(self, key):
        import cb_db
        return cb_db.scene_lease(self.root, 'journey', key, 'five-action', wait_seconds=1)

    def path(self, key):
        return self.root / 'cb-output/state/journeys' / (key+'.json')

    def read(self, key):
        import cb_db
        path = self.path(key)
        return cb_db.read_json_document(self.root, path)[0] if path.exists() else None

    def save(self, key, value):
        import cb_db
        cb_db.atomic_write_json(self.root, self.path(key), value)
