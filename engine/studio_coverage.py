"""Read-only scene boards projected from the current direction, never a second plan.

No generation, approvals, synthetic pictures or inferred character geography here.
The same projection feeds the desk, specialists and the finishing handoff.
"""
import hashlib
import json

VERSION = '1.0.0'
CONTRACT = '''Prepare one scene coverage board from the current approved story and canon.
A CoverageView is one continuous camera setup or motivated camera move, not a whole
story phase, script beat or provider clip. Give every distinct cut, reverse, insert or
reaction angle its own stable viewId. A move and its settling hold may share one view
when the camera is continuous. Plan the complete scene, including dialogue coverage
and the final reaction, before allocating any views to clips. A clip may contain
several views; assign each viewId exactly once. If allocation exposes a missing angle,
return that creative decision to scene coverage; never reuse an ID for different angles.
For each authored CoverageView populate staging, action, performance, timing, startState,
endState and cutTo when relevant. The board shows cinematic views, not a quota of renders.
Describe attention -> visible response -> landing; preserve purposeful stillness. Select
inserts, reverses and camera moves for the information or emotion the audience must read.
Make projectile routes, distances, contact, prop transfer and mechanism triggers visible.
Use only supplied character identities; a species label is not a new extra character.
Plan a readable drawing per view. A storyboard controls coverage; separate approved
references control identity and the established world. Never let a sketch redefine canon.
Any rough layout or 3D blocking is agent-operated, optional support for difficult staging,
not another user task or approval step. Use it as provider input only on a verified route.
Keep the board, SEE opening, performed voice and WATCH action aligned to the same source
revision. Preserve approved audio and explicitly authorised generated SFX separately.
User feedback changes the shared shot plan; do not keep a conflicting private prompt.
Do not copy example scenes or new mechanics into the selected story.'''


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def unit_board(shot):
    """Accept project cards and existing legacy storyboard fields without migration."""
    from studio_director_card import stage_decisions
    d = shot.get('directorCard') or {}
    views = d.get('views') or shot.get('storyboardInternalShotPlanApproved') or shot.get('internalShotPlan') or []
    panels = []
    for index, view in enumerate(views):
        panels.append({
            'number': index + 1, 'viewId': view.get('viewId') or str(view.get('shotNumber', index + 1)),
            'entry': view.get('entry', view.get('transitionType', 'auto')),
            'framing': view.get('framing', view.get('framingAndCamera', '')),
            'purpose': view.get('audienceNeed', view.get('purpose', '')),
            'cameraPurpose': view.get('cameraPurpose', ''),
            'staging': view.get('staging') or '',
            'action': view.get('action') or view.get('storyAction', ''),
            'performance': view.get('performance') or view.get('performanceFocus', ''),
            'timing': view.get('timing') or '',
            'startState': view.get('startState') or (shot.get('openingState', shot.get('openingImageApproved', shot.get('openingImage', ''))) if index == 0 else ''),
            'endState': view.get('endState') or view.get('landingImage', ''),
            'cutReason': view.get('cutReason', ''), 'cutTo': view.get('cutTo') or '',
            'continuity': view.get('continuity', ''), 'productionChoice': view.get('productionChoice', 'allocated in existing shot plan')})
    body = {'version': VERSION, 'shotId': shot.get('id', shot.get('shotId')),
            'scene': shot.get('scene'), 'duration': shot.get('duration', shot.get('durationSec', shot.get('targetDurationSec'))),
            'panels': panels, 'acting': d.get('acting', []),
            'stateChanges': d.get('stateChanges', []), 'soundCues': d.get('soundCues', []),
            'sourceDirection': stage_decisions(shot, 'post'),
            'meaning': 'Authored coverage, not generated artwork or a film-quality verdict.'}
    body['revision'] = fingerprint(body)
    return body


def scene_boards(shots, coverage=()):
    journeys = {s['scene']: s.get('audienceJourney', '') for s in coverage}
    scenes = {}
    for shot in shots:
        scene = shot.get('scene', 1)
        row = scenes.setdefault(scene, {'scene': scene, 'audienceJourney': journeys.get(scene, ''), 'units': []})
        row['units'].append(unit_board(shot))
    for row in scenes.values():
        row['revision'] = fingerprint(row)
    return list(scenes.values())


def staging_instruction(shot, *, opening_only=False):
    """New explicit staging fields supplement existing compilers, not whole scripts."""
    views = (shot.get('directorCard') or {}).get('views') or shot.get('storyboardInternalShotPlanApproved') or []
    if opening_only:
        views = views[:1]
    lines = []
    for panel in views:
        fields = ('staging', 'startState') if opening_only else ('staging', 'startState', 'endState', 'cutTo')
        details = [f'{key}: {panel[key]}' for key in fields if panel.get(key)]
        if details:
            lines.append(f"View {panel.get('viewId') or panel.get('shotNumber')}: " + '; '.join(details))
    return '\n'.join(lines)


def panel_brief(shot):
    """Reusable image brief for an agent; creating it does not claim an image exists."""
    board = unit_board(shot)
    return {'boardRevision': board['revision'], 'shotId': board['shotId'], 'panels': board['panels'],
            'instruction': 'Create a clearly numbered cinematic storyboard in panel order. Depict the exact staging and readable acting in each panel; use separate canonical identity and location references. Keep captions brief. Do not add actors, props or actions. The board is coverage reference, never the exact opening frame or an identity redesign.',
            'status': 'brief-only', 'agentOperated': True}
