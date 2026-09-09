"""SEE source authority and lineage; generation and approval use the production ledger."""
from copy import deepcopy
from studio_workspace import StudioError


def build(context, state, shot, references):
    from studio_director_card import inherits_previous_state
    if not inherits_previous_state(shot):
        return None
    index = state['shots'].index(shot)
    if not index or state['shots'][index - 1]['scene'] != shot['scene']:
        return None
    previous = state['shots'][index - 1]
    watch = previous.get('outcomes', {}).get('watch', {})
    ending = next((r for r in references if r.get('role') == 'previous state'), None)
    mode = 'continuous_movement_handoff' if shot.get('transition') == 'continuation' else 'next_beat_opening'
    if shot.get('seeCutType', 'auto') != 'auto':
        mode = shot['seeCutType']
    return {
        'version': '0.1.0', 'projectId': context['project']['id'],
        'episode': str(context.get('episode', {}).get('number', '')),
        'scene': shot['scene'], 'previousShotId': previous['id'], 'newShotId': shot['id'],
        'cutType': mode, 'timeAdvance': 'none; retain the exact handoff action phase' if mode == 'same_moment_camera_cut' else 'only the stated opening beat', 'modeBasis': 'Existing shot transition and opening direction; editable through shot direction.',
        'camera': shot.get('camera', ''), 'openingDirection': shot.get('openingState') or shot.get('seePrompt', ''),
        'previousEndingDirection': previous.get('endingState', ''),
        'sourceWatchId': watch.get('id') if ending else None,
        'sourceFrame': deepcopy(ending), 'references': deepcopy(references),
        'continuityEvidence': 'approved-ending-attached' if ending else 'planned-only-no-approved-ending',
        'visualJudgment': 'unverified',
        'limitations': ['Unseen geography is provisional until reviewed against scene references.',
                        'A still image does not establish continuous motion.',
                        'Opening direction may advance only the stated beat; do not reset prior action.'],
        'authority': {'location geography': 'Fixed world, scale, landmarks and lighting logic.',
                      'previous state': 'Latest approved visible pose, prop ownership and action phase.',
                      'scene geography': 'Sequence baseline; never override later approved action.',
                      'camera setup': 'Composition only; use current character state.',
                      'character identity': 'Identity and design, not an old pose.',
                      'prop continuity': 'Canonical prop design, not ownership from an older image.'},
    }


def validate(production, pid, state, record):
    if not record:
        return
    if record.get('projectId') != pid:
        raise StudioError('This Shot Remix belongs to another project.', 'scope_mismatch')
    target = next((s for s in state['shots'] if s['id'] == record['newShotId']), None)
    previous = next((s for s in state['shots'] if s['id'] == record['previousShotId']), None)
    if not target or not previous or target['scene'] != previous['scene'] or state['shots'].index(target) != state['shots'].index(previous) + 1:
        raise StudioError('The Shot Remix scene or shot order changed. Prepare a current opening.', 'reference_changed')
    watch = (previous or {}).get('outcomes', {}).get('watch', {})
    if record.get('sourceWatchId') and (watch.get('id') != record['sourceWatchId'] or watch.get('status') != 'approved'
            or any(watch.get('ending', {}).get(k) != record['sourceFrame'].get(k) for k in ('path', 'hash'))):
        raise StudioError('The Shot Remix handoff changed. Prepare a new SEE candidate against the current approved ending.', 'reference_changed')
    if not record.get('sourceWatchId') and watch.get('status') == 'approved' and watch.get('ending'):
        raise StudioError('An approved ending is now available. Prepare SEE against that handoff before approving.', 'reference_changed')
    for ref in record['references']:
        if ref.get('sourceShotId'):
            source = next((s for s in state['shots'] if s['id'] == ref['sourceShotId']), {})
            see = source.get('outcomes', {}).get('see', {})
            if see.get('id') != ref.get('version') or see.get('status') != 'approved':
                raise StudioError('The selected sequence reference changed. Prepare a current opening.', 'reference_changed')
    production.assert_artifact(pid, {'files': record['references']})


def prompt(record):
    import json
    return '\nSEE Shot Remix source contract:\n' + json.dumps(record, ensure_ascii=False) + '\nPreserve world positions and the action axis across the new camera. Do not mirror the world. Render one opening frame, not a montage. Treat unknown surfaces as provisional; do not claim they were verified.'
