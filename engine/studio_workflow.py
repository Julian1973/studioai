"""Shared direction handoffs, cost forecasts and human-approved project learning."""
import json
import re
import time
import uuid
from decimal import Decimal
from studio_workspace import StudioError, digest


def voice_performance_text(line):
    """One provider-facing performance, shared by validation, review and submission."""
    from cb_emission_conformance import dialogue_words
    text = str(line.get('performedText') or '').strip()
    if not text:
        delivery = line.get('delivery', 'neutral')
        text = line['text'] if delivery == 'neutral' else f'[{delivery}] ' + line['text']
    spoken = re.sub(r'\[[^\]]*\]', '', text)
    if dialogue_words(spoken) != dialogue_words(line['text']):
        raise StudioError('Voice direction changed the script words. Existing approved audio is preserved.', 'invalid_performance')
    return text


def clean_note(value):
    value = str(value or '').strip()
    if not value or len(value) > 2000:
        raise StudioError('Write a learning note of 1–2,000 characters.')
    if re.search(r'\b(?:sk-[A-Za-z0-9_-]{12,}|ark-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,})', value):
        raise StudioError('Keep API keys in Workspace connections.', 'secret_in_chat')
    return value


def estimate(binding, kind, shot, *, duration=None):
    """Conservative configured forecast, not usage or invoice evidence."""
    if not binding or binding.get('estimateUsd') is None:
        return None
    lines = shot.get('dialogue', []) if shot else []
    count = len(lines) if kind == 'hear' else 1
    floor = Decimal(str(binding['estimateUsd'])) * count
    rate = binding.get('unitUsd')
    if rate is None:
        return float(floor)
    units = (sum(len(voice_performance_text(d)) for d in lines) / 1000
             if kind == 'hear' else (duration or shot.get('duration', 0)) if kind == 'watch' else 1)
    return float(max(floor, Decimal(str(rate)) * Decimal(str(units))))


def handoff(shot, stage, refs):
    common = ('intent', 'emotion', 'camera', 'cameraSetupId', 'geography', 'transition', 'openingState')
    fields = common if stage == 'see' else common + ('performance', 'endingState', 'beatPlan')
    result = {'stage': stage, 'durationSec': shot.get('duration'), 'direction': {k:shot.get(k) for k in fields},
              'references': [{'slot':f'@Image{i+1}', **{k:r.get(k) for k in ('name','role','hash','version')}} for i,r in enumerate(refs)],
              'instruction': ('Depict ONE opening instant. The openingState and camera define this frame. Do not illustrate later beats, ending poses, montage or multiple panels.' if stage == 'see'
                              else 'Animate from the approved opening through the timed beats to endingState. Preserve approved audio performance and reference authority.')}
    from cb_production_contracts import shot_handoff_instruction
    result['visualHandoff'] = shot_handoff_instruction(
        {'shotTransition': {'type': shot.get('transition')}}, still=stage == 'see')
    if stage == 'see':
        result['performanceContextNotDepicted'] = {k:shot.get(k) for k in ('performance','endingState','beatPlan')}
        result['direction']['openingBeat'] = [beat for beat in shot.get('beatPlan', []) if beat.get('at') == 0]
    if stage != 'see':
        from studio_scene_handoff import sound_instruction
        result['soundHandoff'] = shot.get('soundHandoff')
        result['soundInstruction'] = sound_instruction(shot.get('soundHandoff'), continuation=shot.get('transition') == 'continuation')
    from studio_director_card import stage_decisions
    result['directorDecisions'] = stage_decisions(shot, stage)
    result['fingerprint'] = digest(result)
    return result


def learning_command(production, db, context, state, shot, payload):
    action = payload['action']
    if action == 'retire_learning':
        note = next((n for n in state.get('learning', []) if n['id'] == payload.get('learningId')), None)
        if not note:
            raise StudioError('This learning belongs to another episode or is unavailable.', 'scope_mismatch')
        note.update(status='retired', retiredAt=time.time())
        return 'Learning retired. Its evidence remains in history.'
    stage = payload.get('stage')
    artifact = (shot or {}).get('outcomes', {}).get(stage, {})
    if stage not in {'see','hear','watch'} or artifact.get('status') != 'approved' or artifact.get('id') != payload.get('candidateId'):
        raise StudioError('Choose the exact approved picture, voice or render supporting this learning.', 'approval_required')
    production.assert_artifact(context['project']['id'], artifact)
    text = clean_note(payload.get('note'))
    records = state.setdefault('learning', [])
    if any(n['status']=='active' and n['candidateId']==artifact['id'] and n['note']==text for n in records):
        return 'This learning is already saved.'
    records.append({'id':uuid.uuid4().hex, 'status':'active', 'note':text, 'stage':stage, 'shotId':shot['id'],
                    'candidateId':artifact['id'], 'files':artifact['files'], 'sourceSignature':shot.get('sourceSignature'),
                    'at':time.time(), 'authority':'human-approved learning; advisory, never canon'})
    return 'Project learning saved against this approved outcome. It will inform future direction in this project.'


def approved_learning(production, db, pid):
    result=[]
    for row in db.execute('SELECT episode,data FROM production WHERE project=? ORDER BY rowid DESC', (pid,)):
        state=json.loads(row['data'])
        for note in state.get('learning', []):
            if note.get('status')!='active':continue
            try:production.assert_artifact(pid, {'files':note['files']})
            except (StudioError,KeyError):continue
            result.append({**note,'episode':row['episode']})
    return sorted(result, key=lambda n:n.get("at",0), reverse=True)[:60]


def chat_command(message, shot, payload):
    """Unambiguous natural commands share the button ledger and version tokens."""
    normalized = message.lower().strip(' .!')
    action = {'apply the change':'apply_revision','apply this change':'apply_revision','apply revision':'apply_revision',
              'discard the change':'discard_revision','discard this change':'discard_revision',
              'undo that change':'undo_revision','undo the last change':'undo_revision',
              'prepare the next outcome':'continue','show me the next outcome':'continue',
              'approve and continue':'approve','reject this':'reject'}.get(normalized)
    if not action:return None
    if action in {'apply_revision','discard_revision'}:
        proposal=(shot or {}).get('proposal') or {}
        if not payload.get('proposalId') or payload['proposalId']!=proposal.get('id'):
            raise StudioError('Open the current revision preview before applying or discarding it.', 'stale')
    return action
