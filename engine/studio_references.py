"""Explainable, episode-local reference suggestions. Selection is a reviewed edit."""
from studio_workspace import StudioError
from studio_review import verified_file


def suggestions(production, context, state, shot):
    pid = context['project']['id']
    earlier = state['shots'][:state['shots'].index(shot)]
    eligible = []
    for source in earlier:
        see = source.get('outcomes', {}).get('see', {})
        files = see.get('files', [])
        if (source['scene'] == shot['scene'] and source.get('location') == shot.get('location')
                and see.get('status') == 'approved' and files and verified_file(production.ws, pid, files[0])):
            eligible.append((source, see, files[0]))
    result = []
    setup = shot.get('cameraSetupId', '').strip()
    matches = [(s, a, f) for s, a, f in eligible if
               ((setup and s.get('cameraSetupId') == setup) or
                (not setup and not s.get('cameraSetupId') and s.get('camera') == shot.get('camera')))]
    for source, see, record in reversed(matches[-3:]):
        result.append({'name': source['id'] + ' approved camera view', **record,
                       'choice': {'shotId': source['id'], 'candidateId': see['id'], 'hash': record['hash'], 'role': 'camera setup'},
                       'reason': 'Same scene and location; ' + ('matching camera setup ' + setup if setup else 'exactly matching camera direction') + '. Controls composition, not character state.'})
    if eligible:
        source, see, record = eligible[0]
        result.append({'name': source['id'] + ' scene anchor', **record,
                       'choice': {'shotId': source['id'], 'candidateId': see['id'], 'hash': record['hash'], 'role': 'scene geography'},
                       'reason': 'First approved opening in this scene and location. Controls geography; use the new shot’s camera and approved character states.'})
    return result


def resolve(production, context, state, shot):
    choice = shot.get('compositionReference')
    if not choice:
        return None
    source = next((s for s in state['shots'][:state['shots'].index(shot)] if s['id'] == choice['shotId']), None)
    see = (source or {}).get('outcomes', {}).get('see', {})
    record = (see.get('files') or [None])[0]
    setup = shot.get('cameraSetupId', '').strip()
    if (not source or source['scene'] != shot['scene'] or source.get('location') != shot.get('location')
            or see.get('status') != 'approved' or see.get('id') != choice['candidateId']
            or not record or record.get('hash') != choice['hash'] or not verified_file(production.ws, context['project']['id'], record)
            or choice['role'] == 'camera setup' and not (
                setup and source.get('cameraSetupId') == setup or
                not setup and not source.get('cameraSetupId') and source.get('camera') == shot.get('camera'))):
        raise StudioError('The selected camera or scene reference changed. Choose a current approved suggestion.', 'reference_changed')
    return {**record, 'name': source['id'] + ' approved ' + choice['role'],
        'role': choice['role'], 'approvalStatus': 'approved', 'version': choice['candidateId'],
        'description': 'Use for composition and geography only. Retain this shot’s own approved character states and its stated camera direction.', 'sourceShotId': choice['shotId']}
