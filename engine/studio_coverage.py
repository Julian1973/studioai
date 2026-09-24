"""Read-only scene boards projected from the current direction, never a second plan.

No generation, approvals, synthetic pictures or inferred character geography here.
The same projection feeds the desk, specialists and the finishing handoff.
"""
import hashlib
import json
from studio_episode_direction import CONTRACT as EPISODE_DIRECTION_CONTRACT

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
Do not copy example scenes or new mechanics into the selected story.

OUTCOME-FIRST COVERAGE CHAIR — inside DIRECT, not another stage or model call.
Work backward from the audience's emotional change and the final edited scene. Translate
each important beat into observable behaviour, a readable image and an editorial purpose.
Actively explore an expressive alternative to simply filming the speaker: a world entrance,
listener reverse, thought before the line, meaningful hand/prop contact, motivated reveal,
or purposeful hold. Choose what earns its screen time; neither cuts nor holds are quotas.
Use cinematography.pattern optionally to name an organising idea: THE ENTRANCE,
WHERE EVERYONE IS, THE LINE LANDING, THE TWO-SHOT, THE THOUGHT BEFORE THE LINE,
BUSY HANDS, THE PILLOW SHOT, THE DEADPAN, THE CRASH, THE REALISATION, THE REVEAL,
THE CHASE, THE CONFESSION, THE PLANT AND PAYOFF, THE BUTTON, THE RULE OF THREE.
These are exploratory shapes, not compulsory shots or fixed durations. Explain the
specific purpose in audienceNeed and cameraPurpose; a pattern name is not direction.
Protect anticipation, contact, weight, consequence and a listener's changing thought.
An insert of a hand or paw retains identity, scale, material, costume and prop continuity.
Purposeful repetition may build a motif, callback or comic escalation; avoid empty repeats.
Invent staging and cinematic execution within supplied story truth, not new canon, plot,
dialogue, characters or unsupported world assets. Missing downstream images must not
prevent developing coverage; mark unresolved references without claiming production ready.

MEDIUM AND SHOW TASTE. Follow the supplied project's medium and approved visual language.
Animation: readable silhouettes, eye direction, anticipation, weight, follow-through and
character-specific acting; exaggeration only within this show's approved performance style.
Live action: playable actor objectives, subtext, natural listening, physical blocking,
plausible lens placement and motivated practical light. Do not impose cartoon performance
or Crystal Bears camera rules on another project. If medium is unspecified, do not invent it.
Lens/emotion pairings are possibilities, never universal laws: a quiet wide or fast telephoto
may be right. Show-specific height and camera grammar apply only where that show supplies them.
Write framing in framing; write angle, lens, movement (including trigger and finish), focus,
light, composition, atmosphere and time in cinematography when relevant. time describes
screen-time treatment, not weather or a replacement for numeric view timing. Real-time is
valid; slow motion cannot silently stretch approved dialogue or change locked audio timing.

PAPER REEL BEFORE PACKING. Read the entire scene's images, action, dialogue and sound in
order during the existing creative review. Can the audience follow cause and consequence,
feel the change, locate characters, read the contact and enjoy the landing? Remove decorative
shots; strengthen weak staging or reactions. Check plausible time for speech, movement and
holds against measured approved audio when available. Do not invent measurements or squeeze
an impossible performance into a provider slot. Resolve timing in DIRECT before generation.
Plan the scene before allocating provider units. Each unit needs a usable editorial exit,
not an artificial mini-payoff; the emotional arc belongs to the scene. Keep the same views,
script, approved audio and state continuity through SEE, HEAR, WATCH and the final edit.
These craft judgements inform existing review, not new scores, gates or automatic retakes.
Paper direction is not proof of cinematic quality. Judge actual returned media and the
assembled scene through human review; preserve existing spend and approval safeguards.'''


CONTRACT += '\n' + EPISODE_DIRECTION_CONTRACT


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
            'sourceBeat': view.get('sourceBeat'), 'viewpointOwner': view.get('viewpointOwner'),
            'listenerReaction': view.get('listenerReaction'), 'cinematography': view.get('cinematography', {}),
            'staging': view.get('staging') or '',
            'action': view.get('action') or view.get('storyAction', ''),
            'performance': view.get('performance') or view.get('performanceFocus', ''),
            'timing': view.get('timing') or '',
            'startState': view.get('startState') or (shot.get('openingState', shot.get('openingImageApproved', shot.get('openingImage', ''))) if index == 0 else ''),
            'endState': view.get('endState') or view.get('landingImage', ''),
            'cutReason': view.get('cutReason', ''), 'cutTo': view.get('cutTo') or '',
            'continuity': view.get('continuity', ''), 'productionChoice': view.get('productionChoice', 'allocated in existing shot plan'),
            # Feature-animation coverage vocabulary (Phase 1: keys inside cinematography).
            'kind': __import__('studio_director_card').canonical_kind((view.get('cinematography') or {}).get('kind')) if isinstance(view.get('cinematography'), dict) else None,
            'motivation': __import__('studio_director_card').canonical_motivation((view.get('cinematography') or {}).get('motivation')) if isinstance(view.get('cinematography'), dict) else None,
            'attention': (view.get('cinematography') or {}).get('attention') if isinstance(view.get('cinematography'), dict) else None,
            'cutTiming': (view.get('cinematography') or {}).get('cutTiming') if isinstance(view.get('cinematography'), dict) else None,
            'actionPhase': (view.get('cinematography') or {}).get('actionPhase') if isinstance(view.get('cinematography'), dict) else None,
            'functions': (view.get('cinematography') or {}).get('functions') if isinstance(view.get('cinematography'), dict) else None})
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
    entrances = {s['scene']: s.get('entrance') for s in coverage}
    modes = {s['scene']: s.get('mode') for s in coverage}
    functions = {s['scene']: s.get('function') for s in coverage}
    scenes = {}
    for shot in shots:
        scene = shot.get('scene', 1)
        row = scenes.setdefault(scene, {'scene': scene, 'audienceJourney': journeys.get(scene, ''),
                                        'entrance': entrances.get(scene), 'mode': modes.get(scene),
                                        'function': functions.get(scene), 'units': []})
        row['units'].append(unit_board(shot))
    from studio_scene_handoff import episode_sound_plan
    sound = episode_sound_plan(shots)['scenes']
    for row in scenes.values():
        row['soundPlan'] = sound.get(str(row['scene']), [])
        row['revision'] = fingerprint(row)
    return list(scenes.values())


def producer_scene_sequence(direction_card, approval_state=None):
    """Expose the existing scene-direction decision without creating new authority."""
    if not isinstance(direction_card, dict):
        return None
    purpose = direction_card.get('scenePurposeAndEmotionalChange') or {}
    beats = direction_card.get('dramaticBeats') or {}
    shots = direction_card.get('cinematicShotPlan') or []
    return {
        'approvalState': approval_state or 'draft',
        'approved': approval_state == 'approved',
        'purpose': purpose.get('purpose'),
        'dramaticQuestion': purpose.get('dramaticQuestion'),
        'entry': purpose.get('entry'),
        'exit': purpose.get('exit'),
        'beats': {key: beats[key] for key in ('beginning', 'development', 'turn', 'landing')
                  if beats.get(key)},
        'coverage': [
            {key: shot.get(key) for key in ('shotId', 'durationSec', 'purpose', 'landingImage')
             if shot.get(key)}
            for shot in shots if isinstance(shot, dict)
        ],
        'sourceRevision': direction_card.get('inputSignature'),
    }


def staging_instruction(shot, *, opening_only=False):
    """New explicit staging fields supplement existing compilers, not whole scripts."""
    views = (shot.get('directorCard') or {}).get('views') or shot.get('storyboardInternalShotPlanApproved') or []
    if opening_only:
        views = views[:1]
    lines = []
    for panel in views:
        fields = ('staging', 'startState', 'viewpointOwner', 'cinematography') if opening_only else ('staging', 'startState', 'endState', 'cutTo', 'viewpointOwner', 'cinematography', 'performance', 'listenerReaction')
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
