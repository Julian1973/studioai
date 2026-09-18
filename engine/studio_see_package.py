"""SEE visual proof and human package approval. No model calls or inferred action.

Media remains in the existing Studio libraries. This document binds selected media
to DIRECT and its actual input dependencies; read operations never alter approvals.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
import time
import ast

from studio_authored_action import actions, digest
from studio_journey import scope_key
from studio_storyboard_sheet import panel_binding, source_binding, compile_sheet, ROLE as SHEET
from studio_roots import data_root

VERSION = 'see-package@2'
ENDING = 'OPTIONAL_ENDING_VISUAL_REFERENCE'
CRITICAL = 'CRITICAL_CAUSAL_REFERENCE'


def visible_change(change):
    """Name the authored entity when displaying its structured visible state."""
    value = change.get('afterValues') or change.get('after')
    if isinstance(value, str) and value.strip().startswith('{'):
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass
    if isinstance(value, dict):
        value = '; '.join(str(k).replace('_', ' ') + ': ' + str(v).replace('_', ' ') for k, v in value.items())
    name = change.get('subject') or change.get('entityId') or 'Authored object'
    return str(name).replace('_', ' ') + ' — ' + str(value)


def media(root, value):
    if not value:
        return None
    value = value if isinstance(value, dict) else {'path': str(value)}
    name = value.get('path') or value.get('url', '').lstrip('/')
    path = Path(name)
    path = (path if path.is_absolute() else Path(root) / path).resolve()
    source = Path(root).resolve()
    roots = [(source, '/'),
             ((data_root(source) / 'engine' / 'media').resolve(), '/engine/media/'),
             ((data_root(source) / 'media').resolve(), '/engine/media/'),
             ((data_root(source) / 'cb-seed' / 'assets').resolve(), '/cb-seed/assets/')]
    for base, prefix in roots:
        try:
            relative = path.relative_to(base).as_posix()
            break
        except ValueError:
            continue
    else:
        raise ValueError('SEE media must belong to this Studio.') from None
    if not path.is_file():
        return None
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = value.get('sha256') or value.get('hash')
    stored_path = relative if base == source else str(path)
    return {'path': stored_path, 'url': prefix + relative, 'sha256': actual,
            'current': value.get('current', True) and (not expected or expected == actual)}


def current_tail_issue(shot):
    """Narrow canon check on current DIRECT only; historical sources stay untouched."""
    import re
    card = shot.get('directorCard') or {}
    def values(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from values(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key not in ('source', 'sourceBeatPackage', 'producerTimingRevisions', 'sourceClarifications'):
                    yield from values(item)
    text = '\n'.join(values(card))
    if not re.search(r'\bKeen\b', text, re.I):
        return None
    text = re.sub(r'\b(?:has\s+no|with\s+no|without(?:\s+a)?|not(?:\s+a)?|no)\s+tail\b', '', text, flags=re.I)
    text = re.sub(r"\b(?:must\s+not|does\s+not|do\s+not|don't|never)\s+(?:have|add|give|show|grow)(?:\s+Keen)?(?:\s+a)?\s+tail\b", '', text, flags=re.I)
    text = text.replace('not_a_tail', '')
    if re.search(r'\btail\b', text, re.I):
        return 'KEEN_TAIL_CONTRADICTION: Replace the current DIRECT tail instruction with lower backside/rump/rear haunch before new SEE or WATCH submission.'
    return None


def checkpoints(shot):
    """Project explicit DIRECT states and event times, never invent a panel state."""
    records = actions(shot)
    card = shot.get('directorCard') or {}
    views = card.get('views') or []
    changes = card.get('stateChanges') or []
    result, issues = [], []
    landing = {k: deepcopy(shot.get(k, card.get(k))) for k in
               ('continuity', 'continuityOut', 'mustPreserve', 'mustNotAdvance')}
    for index, (view, action) in enumerate(zip(views, records)):
        start, end = action['startSec'], action['endSec']
        candidates = []
        if index == 0:
            candidates.append(('opening', start, view.get('startState') or view.get('staging') or '', 'opening'))
        elif view.get('startState'):
            candidates.append(('entry', start, view['startState'], 'camera entry'))
        for change_index, change in enumerate(changes):
            at = change.get('atSec')
            if at is None:
                if index == 0:
                    issues.append(f'State change {change_index + 1} needs an explicit DIRECT atSec.')
                continue
            if not isinstance(at, (int, float)) or not math.isfinite(at):
                raise ValueError('DIRECT state-change times must be finite numbers.')
            if start < at <= end:
                state = change.get('afterValues') or change.get('after')
                if not state:
                    issues.append(f'State change {change_index + 1} needs its authored visible after-state.')
                    continue
                candidates.append(('event-' + str(change_index), at, visible_change(change), change.get('cause') or 'state change'))
        if view.get('endState'):
            candidates.append(('landing' if index == len(views)-1 else 'exit', end, view['endState'], 'landing' if index == len(views)-1 else 'view completion'))
        else:
            issues.append(f'{view["viewId"]} needs an explicit DIRECT endState for its visible completion.')
        # Several entities can change in one visible instant. They are one frame,
        # not separate purchased images for an empty hanger, empty support and fall.
        groups = {}
        for candidate in candidates:
            groups.setdefault(candidate[1], []).append(candidate)
        combined = []
        for at, group in sorted(groups.items()):
            main = next((c for c in group if c[0] in ('landing', 'exit', 'opening')), group[0])
            states = list(dict.fromkeys([main[2]] + [c[2] for c in group if c is not main]))
            combined.append((main[0], at, '\n'.join(states), main[3]))
        for suffix, at, state, reason in combined:
            panel = {'id': view['viewId'] + ':' + suffix, 'viewId': view['viewId'],
                     'atSec': at, 'interval': [start, end], 'state': state,
                     'reason': reason, 'framing': view.get('framing'),
                     'staging': view.get('staging'), 'performance': view.get('performance'),
                     'authoredTimedAction': action['text'],
                     'actionHash': digest([start, end, action['text']]),
                     'source': action['origin'], 'reuseOpening': suffix == 'opening',
                     'isFinal': suffix == 'landing', 'roles': ['STORYBOARD_PROOF_PANEL']}
            panel.update(checkpointType={'opening':'OPENING_STATE', 'entry':'CAMERA_TRANSITION',
                         'exit':'ACTION_COMPLETION', 'landing':'LANDING_STATE'}.get(suffix, 'STATE_CHANGE'),
                         mustPreserve=landing.get('mustPreserve'), mustNotAdvance=landing.get('mustNotAdvance'),
                         storyboardRevision=action['storyboardRevision'], directorCardRevision=action['directorCardRevision'])
            # Earlier world changes remain dependencies even across a camera cut.
            visible = {k: v for k, v in panel.items() if k not in ('atSec', 'interval', 'actionHash', 'storyboardRevision', 'directorCardRevision')}
            prior_states = [{k: v for k, v in c.items() if k not in ('atSec', 'timing')}
                            for c in changes if isinstance(c.get('atSec'), (int, float)) and c['atSec'] <= at]
            # Retiming changes package approval, but does not purchase a new still
            # when the authored visible state and its causal inputs are unchanged.
            panel['dependencyHash'] = digest([visible, landing, prior_states])
            result.append(panel)
    return {'panels': result, 'issues': issues, 'landing': landing,
            'authoredActionHash': digest([[r['viewId'], r['startSec'], r['endSec'], r['text']] for r in records]),
            'timingAuthority': 'DIRECT planned timing; approved Audio1 remains voice timing authority'}


class Package:
    def __init__(self, root, scope):
        self.root, self.scope = Path(root), deepcopy(scope)
        self.path = self.root / 'cb-output/state/see-packages' / (scope_key(scope) + '.json')

    def read(self):
        import cb_db
        return cb_db.read_json_document(self.root, self.path)[0] if self.path.exists() else {}

    def save(self, record):
        import cb_db
        cb_db.atomic_write_json(self.root, self.path, record)

    def lock(self):
        import cb_db
        return cb_db.scene_lease(self.root, 'see-package', scope_key(self.scope), 'edit', wait_seconds=1)

    def status(self, shot, plate, opening, references=()):
        saved = self.read()
        storyboard_required = saved.get('storyboardChoice', {}).get('required', True)
        try:
            if storyboard_required:
                plan = checkpoints(shot)
            else:
                # Image review without a storyboard does not require storyboard views.
                # Bind the existing direction unchanged; WATCH validates timed action.
                authored_hash = digest(shot)
                if saved.get('noStoryboardBindingVersion') == 2:
                    try:
                        authored_hash = digest([[r['viewId'], r['startSec'], r['endSec'], r['text']] for r in actions(shot)])
                    except ValueError:
                        # SEE without a storyboard may precede timed action preparation.
                        # Bind authored fields, never a project's approvals or outcomes.
                        if self.scope.get('projectId') == 'crystal-bears':
                            from studio_director_handoff import source
                            authored_hash = digest([source(shot), shot.get('directorCard')])
                        else:
                            from studio_editing import Shot
                            authored_hash = digest({k: shot[k] for k in Shot.model_fields if k in shot})
                plan = {'panels': [], 'issues': [], 'authoredActionHash': authored_hash,
                    'timingAuthority': 'DIRECT planned timing; approved Audio1 remains voice timing authority'}
            if self.scope.get('projectId') == 'crystal-bears':
                issue = current_tail_issue(shot)
                if issue:
                    plan['issues'].append(issue)
        except ValueError as exc:
            message = ('Complete the timed action and visible checkpoint states in DIRECT before building this storyboard.'
                       if str(exc).startswith('WATCH_AUTHORED_TIMED_ACTION_MISSING') else str(exc))
            if not storyboard_required and str(exc).startswith('WATCH_AUTHORED_TIMED_ACTION_MISSING'):
                message = 'Complete the authored timed action in DIRECT before approving SEE.'
            plan = {'panels': [], 'issues': [message], 'authoredActionHash': None}
        plate, opening = media(self.root, plate), media(self.root, opening)
        view = ((shot.get('directorCard') or {}).get('views') or [{}])[0]
        opening_source = digest([plate, {k: view.get(k) for k in ('startState', 'staging', 'framing', 'stateAtEntry')}])
        previous = saved.get('openingBinding') or {}
        if opening and previous.get('media') == [opening['path'], opening['sha256']] and previous.get('source') != opening_source:
            opening['current'] = False
            plan['issues'].append('The opening needs review against the changed scene plate or starting direction. Select or generate the current opening before the storyboard.')
        reference_media = [media(self.root, ref) for ref in references]
        anchor_hash = digest([plate, opening, reference_media])
        panels = []
        for source in plan['panels']:
            panel = deepcopy(source)
            bound = (saved.get('panels') or {}).get(panel['id']) or {}
            image = opening if panel['reuseOpening'] else media(self.root, bound.get('media'))
            expected = digest([anchor_hash, panel['dependencyHash']])
            current = bool(image and image['current'] and (panel['reuseOpening'] or bound.get('inputHash') == expected))
            panel['fidelity'] = ('OPENING_KEYFRAME' if panel['reuseOpening'] else bound.get('fidelity') or ('FINAL_LANDING_PANEL' if panel['isFinal'] else 'CLEAN_STORYBOARD_PANEL'))
            panel.update(media=image, inputHash=expected, status='current' if current else 'stale' if image else 'missing')
            review = saved.get('panelReviews', {}).get(panel['id']) or {}
            reviewed = current and review.get('binding') == panel_binding(panel)
            panel['reviewStatus'] = review['decision'] if reviewed else 'pending'
            if reviewed and review['decision'] == 'rejected':
                panel['status'] = 'rejected'
            panel['review'] = review if reviewed else None
            selected = saved.get('selections', {}).get(panel['id']) or {}
            if current and selected.get('mediaHash') == image['sha256'] and selected.get('inputHash') == expected:
                panel['roles'] += [role for role in selected.get('roles', [])
                                   if role == CRITICAL or role == ENDING and panel['isFinal']]
            panels.append(panel)
        images_ready = bool(plate and plate['current'] and opening and opening['current'] and panels
                     and panels[-1]['isFinal'] and not plan['issues'] and all(p['status'] == 'current' for p in panels))
        sheet = deepcopy(saved.get('providerSheet') or {})
        sheet_media = media(self.root, sheet.get('media'))
        sheet_current = bool(images_ready and all(p['reviewStatus'] == 'approved' for p in panels)
                             and sheet_media and sheet_media['current'] and sheet.get('sourceBinding') ==
                             source_binding({'panels': panels, 'authoredActionHash': plan.get('authoredActionHash')}))
        sheet.update(media=sheet_media, status='current' if sheet_current else 'stale' if sheet else 'missing')
        ready = bool(images_ready and sheet_current)
        if not storyboard_required:
            sheet = {}
            images_ready = ready = bool(plate and plate['current'] and opening and opening['current'] and not plan['issues'])
        binding = digest([VERSION, self.scope, plate, opening, plan.get('authoredActionHash'),
            [[p['id'], p['inputHash'], p['media'], p['roles'], p['reviewStatus']] for p in panels], sheet])
        if not storyboard_required:
            binding = digest([binding, 'without-storyboard', reference_media])
        approved = bool(ready and saved.get('approval', {}).get('binding') == binding)
        return {'version': VERSION, 'scope': self.scope, 'plate': plate, 'opening': opening,
                'storyboardRequired': storyboard_required,
                'storyboardChoice': saved.get('storyboardChoice'),
                'panels': panels, 'issues': plan['issues'], 'ready': ready, 'approved': approved,
                'binding': binding, 'authoredActionHash': plan.get('authoredActionHash'),
                'openingSource': opening_source,
                'imagesReady': images_ready, 'providerSheet': sheet,
                'timingAuthority': plan.get('timingAuthority'),
                'status': 'approved' if approved else 'current' if ready else 'incomplete',
                'approval': saved.get('approval') if approved else None,
                'endingMode': 'soft_visual_guidance', 'job': saved.get('job')}

    def choose_storyboard(self, required, actor):
        if type(required) is not bool or not str(actor or '').strip():
            raise ValueError('Choose whether this shot needs a storyboard and identify the reviewer.')
        import time
        saved = self.read()
        saved['storyboardChoice'] = {'required': required, 'by': actor, 'at': time.time()}
        if not required:
            # A new explicit choice adopts the stable binding. Existing approvals
            # retain their original binding until a creative makes a new choice.
            saved['noStoryboardBindingVersion'] = 2
        saved.pop('approval', None)
        self.save(saved)

    def install(self, status, selected, source):
        """Caller holds lock and obtained status from current authoritative inputs."""
        if source not in ('upload', 'library', 'generate'):
            raise ValueError('Choose Generate, Upload or Library.')
        saved = self.read()
        by_id = {p['id']: p for p in status['panels']}
        updates = {}
        for panel_id, value in selected.items():
            panel = by_id.get(panel_id)
            if not panel or panel['reuseOpening']:
                raise ValueError('The opening panel always reuses the current opening keyframe.')
            item = media(self.root, value)
            if not item or not item['current']:
                raise ValueError('The selected storyboard image is missing or changed.')
            fidelity = value.get('fidelity', 'FINAL_LANDING_PANEL' if panel['isFinal'] else 'CLEAN_STORYBOARD_PANEL') if isinstance(value, dict) else 'CLEAN_STORYBOARD_PANEL'
            if fidelity not in ('ROUGH_BLOCKING_PANEL', 'CLEAN_STORYBOARD_PANEL', 'FINAL_LANDING_PANEL'):
                raise ValueError('Unsupported storyboard fidelity label.')
            updates[panel_id] = {'media': item, 'inputHash': panel['inputHash'], 'source': source, 'fidelity': fidelity}
        saved.setdefault('panels', {}).update(updates)
        opening = status.get('opening')
        if opening and opening['current']:
            saved['openingBinding'] = {'media': [opening['path'], opening['sha256']], 'source': status['openingSource']}
        for panel_id in updates:
            saved.setdefault('selections', {}).pop(panel_id, None)
            saved.setdefault('panelReviews', {}).pop(panel_id, None)
        saved.update(version=VERSION, scope=self.scope)
        self.save(saved)

    def review_panels(self, status, panel_ids, decision, actor, reason=''):
        if decision not in ('approved', 'rejected') or not str(actor).strip():
            raise ValueError('A human reviewer must approve or reject the selected panels.')
        if not panel_ids or len(set(panel_ids)) != len(panel_ids):
            raise ValueError('Choose the panels to review.')
        saved = self.read()
        reviewed = deepcopy(status)
        by_id = {p['id']: p for p in reviewed['panels']}
        for panel_id in panel_ids:
            panel = by_id.get(panel_id)
            if not panel or panel['status'] not in ('current', 'rejected'):
                raise ValueError('Review a current image before recording a panel decision.')
            panel['reviewStatus'] = decision
            panel['status'] = 'current' if decision == 'approved' else 'rejected'
            saved.setdefault('panelReviews', {})[panel_id] = {
                'binding': panel_binding(panel), 'decision': decision, 'by': actor,
                'at': time.time(), 'reason': str(reason)[:2000]}
        # Rejection is immediately authoritative, even if the prior sheet still exists.
        saved.pop('approval', None)
        self.save(saved)

    def compile_grid(self, status):
        if status['issues']:
            raise ValueError('Resolve current DIRECT issues before compiling the grid.')
        saved = self.read()
        saved['providerSheet'] = compile_sheet(self.root, scope_key(self.scope), status)
        self.save(saved)

    def select(self, status, panel_id, role, selected):
        if role == CRITICAL and selected:
            raise ValueError('WATCH uses the storyboard grid. Extra individual anchors require provider testing before enabling them.')
        panel = next((p for p in status['panels'] if p['id'] == panel_id), None)
        if role not in (CRITICAL, ENDING) or not panel or panel['status'] != 'current':
            raise ValueError('Select a current storyboard panel and a supported reference role.')
        if panel['reuseOpening'] or role == ENDING and not panel['isFinal']:
            raise ValueError('Ending guidance must reuse the current final storyboard panel.')
        saved = self.read()
        roles = set(panel['roles']) - {'STORYBOARD_PROOF_PANEL'}
        roles.add(role) if selected else roles.discard(role)
        saved.setdefault('selections', {})[panel_id] = {
            'roles': sorted(roles), 'mediaHash': panel['media']['sha256'], 'inputHash': panel['inputHash']}
        self.save(saved)

    def approve(self, status, binding, actor):
        if not status['ready'] or status['binding'] != binding or not str(actor).strip():
            raise ValueError('Review the current selected SEE assets before approving the complete package.')
        saved = self.read()
        saved['approval'] = {'binding': binding, 'by': actor, 'at': time.time()}
        self.save(saved)


def selected_references(status, *, remaining, supported=True):
    """Fail explicitly, never claim dropped references were sent to a provider."""
    if not status['approved']:
        raise ValueError('Approve the current complete SEE package before WATCH.')
    if status.get('storyboardRequired') is False:
        return []
    sheet = status.get('providerSheet') or {}
    if sheet.get('status') != 'current' or not sheet.get('media'):
        raise ValueError('SEE_STORYBOARD_PROVIDER_SHEET_STALE: approve and compile the current storyboard.')
    refs = [{**sheet['media'], 'panelId': 'provider-sheet', 'roles': [SHEET],
             'atSec': None, 'state': 'Approved chronological storyboard grid: read panels left-to-right, then top-to-bottom in chronological order for composition, camera progression, physical causality and intended landing. Render a full-frame moving scene, never grid lines, labels, timestamps, panel numbers, split-screen, tiled layout, sketch overlays, contact-sheet appearance or a montage of frozen stills. Later panels do not belong in the opening. Exact DIRECT action remains authoritative.',
             'guidance': 'chronological_plot_reference', 'authoredActionHash': status['authoredActionHash'],
             'sourceBinding': sheet['sourceBinding'], 'approvalBinding': status['binding']}]
    for p in status['panels']:
        roles = [r for r in p['roles'] if r == ENDING]
        if roles:
            refs.append({**p['media'], 'panelId': p['id'], 'roles': roles, 'atSec': p['atSec'],
                         'state': p['state'], 'guidance': 'soft_visual_guidance',
                         'approvalBinding': status['binding']})
    if refs and not supported:
        raise ValueError('This provider contract does not support selected storyboard references with Audio1.')
    if len(refs) > remaining:
        raise ValueError(f'Select at most {remaining} storyboard references for this provider request.')
    return refs


def provider_references(status, existing, model_id=None, has_audio=True):
    from cb_providers import video_model
    capability = video_model(model_id)
    maximum = capability.referenceLimits.images
    audio = capability.referenceLimits.audio
    supported = ('reference-to-video' in capability.modes and maximum is not None
                 and (not has_audio or audio is not None and audio >= 1))
    return selected_references(status, remaining=max(0, (maximum or 0)-existing), supported=supported)


def panel_prompt(panel, landing):
    """Single still-state brief, with DIRECT action reproduced as source context."""
    return '\n'.join([
        'Create one storyboard still, not a montage, contact sheet or text overlay.',
        '@Image1 is the current scene plate: world, fixed props, geography and light.',
        '@Image2 is the approved opening composition: preserve identity and physical continuity.',
        'Additional images are identity/prop references, not future actions.',
        f'Checkpoint {panel["id"]} at {panel["atSec"]} seconds; {panel["reason"]}.',
        'Show exactly this single visible state: ' + panel['state'],
        'Framing: ' + str(panel.get('framing') or ''),
        'Geography: ' + str(panel.get('staging') or ''),
        'Performance: ' + str(panel.get('performance') or ''),
        'DIRECT timed action (context only; do not depict every step in this one still):',
        panel['authoredTimedAction'],
        'Continuity and limits: ' + json.dumps(landing, ensure_ascii=False),
        'Never advance into the next beat. Preserve all supplied character designs.'
    ])
