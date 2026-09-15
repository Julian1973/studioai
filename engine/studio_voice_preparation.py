"""Direction-time Voice specialist preparation; cached drafts are never approvals."""
from copy import deepcopy
import hashlib
import json

import cb_audio_authority as A
import cb_departments as D
import cb_voice_director as V

VERSION = 1
VOICE_FIELDS = (
    'shotId', 'durationSec', 'dialogueLines', 'voiceDirectorBrief',
    'voicePerformanceSource',
    'principalPerformanceApproved', 'physicalPerformanceApproved',
    'animationTimingApproved', 'performanceContractApproved',
    'performanceBudgetApproved', 'storyIntentApproved',
    'dialogueTimingProse', 'targetDurationSecApproved',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def inputs(shot):
    """Voice dependencies only: a scene plate cannot invalidate a performance."""
    cards = V.voice_cards()
    speakers = {line.get('speaker') for line in shot.get('dialogueLines') or []}
    for line in shot.get('dialogueLines') or []:
        speakers.update(line.get('chorusMembers') or [])
    return {
        'version': VERSION, 'compiler': V.COMPILER_VERSION,
        'shot': {key: deepcopy(shot.get(key)) for key in VOICE_FIELDS},
        'voices': {key: value for key, value in cards.get('characters', {}).items()
                   if key in speakers},
        'registers': V.archetype_registers(), 'rulebook': V.rulebook(),
    }


def checked(output, lines):
    result = D.VoiceDirection.model_validate(deepcopy(output))
    D.validate_voice_direction(result, lines)
    for directed, locked in zip(result.lines, lines):
        exact = locked.get('exactText', locked.get('text'))
        if directed.exactDialogue != exact:
            raise ValueError('Voice preparation changed exact dialogue text')
    track = V.compile_track(result.model_dump(), lines)
    return result, track


def current(shot, lines=None):
    """Read-only: a stale draft is unavailable, never silently resealed."""
    saved = shot.get('preparedVoice') or {}
    if not saved:
        return None
    if saved.get('inputHash') != digest(inputs(shot)):
        return None
    if saved.get('status') != 'READY':
        raise ValueError(saved.get('reason') or 'Voice prompt preparation incomplete')
    if digest(saved.get('output')) != saved.get('outputHash'):
        raise ValueError('Prepared Voice output integrity mismatch')
    locked = lines if lines is not None else A.spoken_dialogue_lines(shot)
    result, track = checked(saved['output'], locked)
    if track != saved.get('compiledTrack'):
        return None
    return result


def prepare(shot, *, context=None, previous=None, log=print):
    """Only the existing text specialist may run here; never the audio provider."""
    reusable = {**shot, 'preparedVoice': previous or shot.get('preparedVoice')}
    existing = current(reusable)
    if existing is not None:
        return deepcopy(reusable['preparedVoice'])
    source = inputs(shot)
    lines = A.spoken_dialogue_lines(shot)
    from studio_source_segmentation import spoken
    for line in lines:
        spoken(line)  # same source boundary gate as HEAR, before any model call
    result = D.prepare_voice({**(context or {}), 'shotId': shot['shotId'],
                              'shot': deepcopy(shot)}, lines, log=log)
    output = result.model_dump() if hasattr(result, 'model_dump') else result
    result, track = checked(output, lines)
    if result.shotId != shot['shotId']:
        raise ValueError('Voice specialist returned a different shot identity')
    output = result.model_dump()
    return {'status': 'READY', 'inputHash': digest(source),
            'outputHash': digest(output), 'output': output,
            'compiledTrack': track,
            'providerRequests': [request for line in track['lines']
                                 for request in V.emit_v3_requests(line)],
            'approvalState': 'draft', 'audioGenerated': False}


def prepare_storyboard(storyboard, *, previous=None, log=print):
    """Distil through the existing handover mapper without promoting any material."""
    import cb_handover as H
    characters = json.loads(H.CHARS.read_text())
    prepared = storyboard['preparedVoice'] = {}
    previous_shot = None
    for card in storyboard['shots']:
        sid = card['shotId']
        shot, retained, _ = H._scoped_shot(storyboard, sid, characters, previous_shot)
        projected = {**shot.model_dump(), **retained}
        try:
            prepared[sid] = prepare(projected, context={
                'episode': storyboard['episodeId'], 'scene': storyboard['sceneNumber']},
                previous=(previous or {}).get(sid), log=log)
        except Exception as exc:
            prepared[sid] = {'status': 'BLOCKED', 'reason': str(exc),
                             'inputHash': digest(inputs(projected)),
                             'approvalState': 'draft', 'audioGenerated': False}
            raise
        previous_shot = sid
    return prepared
