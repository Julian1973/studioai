"""Shared creative decisions; source records remain in their existing stores."""
import hashlib
import json
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal
from studio_creative_authority import Instruction

# Persisted content-address format: additive optional fields must not invalidate
# every historical approval by changing this envelope version.
VERSION = '1.0.0'


def inherits_previous_state(shot):
    return (shot.get('directorCard') or {}).get('storyTime') not in {'time_jump', 'new_location', 'independent'}

CONTRACT = '''Scene coverage precedes generation planning. Plan audience understanding, featured character acting, reactions, reverses, inserts, reveals and cut reasons before choosing provider clips. A keyframe establishes an opening, not a fixed camera for the scene. Assign each view to a current clip, controlled multi-shot clip, new keyframe/clip, existing edit material, or remove it for a stated story reason. Preserve world geography, identity, eyelines, action phase and prop/effect state across views, not identical composition. Static, centred, quiet and simultaneous choices are valid when intentional; never add variety or motion for its own sake.
When the output schema exposes sceneCoverage and directorCard, populate them for new creative plans; link views by stable viewId. Acting drives framing. For featured speakers and listeners direct intention, attention, readable behaviour, starting/ending pose and timing where relevant. Show thought and physical cause, grounded weight/contact and natural settling; do not prescribe a gesture per word or force all body parts to move. Canon protects identity and established personality while allowing local acting invention. Preserve approved words/audio and measured timing. Populate stateChanges for meaningful prop, mark, effect or environmental changes with before, cause and after. Also populate stable entityId, atSec and structured beforeValues/afterValues; track attachment and support occupancy as separate entities when detaching a unique object. For each view declare atSec and visibleEntities, including changed backgrounds. Mark criticalStateEntities when a reset would break the story. Represent time jumps/dreams/restorations explicitly with stateAtEntry; never copy a prior observed state as an approved intended state. Put each authorised generated character SFX, ambience, effect or music instruction in soundCues with its timing and WATCH or post destination; do not bury generation sound only in soundOwnership prose. Generated character SFX are explicit sound instructions, not imaginary assets. Distinguish direction specified from performance observed. Review actual outputs and adjoining cuts; absent evidence remains unverified.'''

from studio_coverage import CONTRACT as COVERAGE_BOARD_CONTRACT
CONTRACT += '\n' + COVERAGE_BOARD_CONTRACT
CONTRACT += '''\nProduction begins with an approved screenplay; writing is outside this run.
Read the entire screenplay first. Describe only its actual movements; quiet observation,
play, unresolved feeling and no transformation are valid. Never invent a low point or lesson.
For each coverage view author sourceBeat, viewpointOwner, listenerReaction when relevant,
and cinematography: owner, emotional action, camera state, state-change trigger, viewpoint,
lens relationship, composition, movement/hold, focus, light, cut-in reason and exit frame.
Voice has two stages: direct exact words before HEAR approval; after approval interpret the
measured performance for picture, never replace words, delivery or timing.
Author scoped instructions with stable id, source, kind, scope, decisionKey and value when
an explicit precedence decision is needed. Classify hard_truth, creative_direction,
contextual_guardrail, default_behaviour, historic_residue and provider_syntax. Defaults
never suppress current creative direction. Do not copy stale instructions from prior shots.
Every authorised character sound cue identifies character, dramaticPurpose,
providerDependency, timing, instruction and watch/post destination. Offscreen characters
have no visible pose or mouth restriction. Listeners may act; only the named speaker
articulates their dialogue. Preserve approved audio and permit only directed generated SFX.
Resolve comedy, emotion and editorial recommendations in the same shared decisions.
No separate department story, extra user gates, decorative camera moves or forced jokes.
Use characterRoles for concise canonical distinguishing traits and shot-scoped role
ownership where similar characters could be confused. Use characterRoleEvents for
explicit event ownership and preserve those IDs through specialist handoff. Never
invent distinguishing anatomy or turn a local action restriction into global canon.
'''

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

    @field_validator('*')
    @classmethod
    def nonempty_decisions(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError('Authored decisions must be explicit; use purposeful stillness or none where appropriate.')
        return value

class ActingBeat(Decision):
    character: str
    intention: str
    attention: str
    observableBehaviour: str
    startingPose: str
    endingPose: str
    timing: str
    listening: str

class CoverageView(Decision):
    atSec: float | None = Field(default=None, ge=0, description='Story time within this clip for current-state resolution.')
    visibleEntities: list[str] | None = Field(default=None, description='Stable entity IDs exposed by this view; include changed background elements.')
    criticalStateEntities: list[str] = Field(default_factory=list)
    storyRelationship: str | None = None
    stateAtEntry: dict = Field(default_factory=dict, description='Explicit intended entry state for resets, dreams or time jumps.')
    sourceBeat: str | None = None
    viewpointOwner: str | None = None
    listenerReaction: str | None = None
    cinematography: dict = Field(default_factory=dict, description="Per-view dramatic owner, emotional action, camera state, trigger, viewpoint, lens, composition, movement, focus, light and exit; no quotas.")
    viewId: str = Field(description='Unique scene-wide ID for one continuous camera setup or move. A distinct cut or reverse needs a different ID, even within the same story beat or provider clip.')
    audienceNeed: str
    framing: str
    cameraPurpose: str
    cutReason: str
    continuity: str
    productionChoice: Literal['current clip', 'controlled multi-shot clip', 'new keyframe and clip', 'existing media in post', 'remove'] = Field(description='Choose the production method after dramatic coverage.')
    entry: Literal['opening', 'cut', 'move', 'hold'] = 'opening'
    staging: str | None = Field(default=None, description='World positions, depth, eyelines and required prop state for this view. Use only the supplied cast and assets.')
    action: str | None = Field(default=None, description='Visible cause, action and consequence, in order.')
    performance: str | None = Field(default=None, description='Attention, thought expressed through observable behaviour, then landing. Include the listener when relevant.')
    timing: str | None = Field(default=None, description='Planned interval within the assigned clip; approved measured audio remains authoritative.')
    startState: str | None = None
    endState: str | None = None
    cutTo: str | None = Field(default=None, description='What the next view must reveal, or the final landing if this ends the scene.')


class StateChange(Decision):
    actionId: str | None = Field(default=None, description='Stable occurrence ID; the same occurrence must not execute again after a cut.')
    repeatAuthorisation: str | None = None
    entityId: str | None = None
    entityCount: int = Field(default=1, ge=1)
    unique: bool = True
    atSec: float | None = Field(default=None, ge=0)
    beforeValues: dict = Field(default_factory=dict)
    afterValues: dict = Field(default_factory=dict)
    storyRelationship: str = 'continuous'
    subject: str
    before: str
    cause: str
    after: str
    timing: str


class SoundCue(Decision):
    character: str | None = None
    dramaticPurpose: str | None = None
    providerDependency: str | None = None
    kind: Literal['character-sfx', 'effects', 'ambience', 'music']
    instruction: str
    timing: str
    destination: Literal['watch', 'post']


class Playability(Decision):
    minimumDurationSec: float = Field(gt=0, le=120)
    reasoning: str = Field(min_length=1)
    decision: Literal['playable', 'restructure']


class CharacterRole(Decision):
    character: str
    identityTraits: dict[str, str] = Field(default_factory=dict)
    allowedActions: list[str] = Field(default_factory=list)
    prohibitedActions: list[str] = Field(default_factory=list)
    exclusiveActions: list[str] = Field(default_factory=list, description='Exact action clauses owned only by this character in this shot. Not global personality rules.')


class CharacterRoleEvent(Decision):
    eventId: str
    viewId: str
    character: str
    action: str


class SharedIdentityException(Decision):
    characters: list[str]
    authorisation: str = Field(min_length=1, description='Existing explicit approval for intentionally shared identity, not an inferred exception.')

class SceneCoverage(Decision):
    scene: int
    audienceJourney: str
    views: list[CoverageView] = Field(description='Complete ordered camera coverage through the final landing, not a list of macro story phases. A story beat may need several views; clip allocation follows this plan.')

class ShotDirection(Decision):
    instructions: list[Instruction] = Field(default_factory=list)
    audienceFocus: str
    cameraPurpose: str
    editIn: str
    editOut: str
    handoff: str
    intendedState: str
    acting: list[ActingBeat]
    views: list[CoverageView]
    soundOwnership: str
    stateChanges: list[StateChange] = Field(default_factory=list)
    soundCues: list[SoundCue] = Field(default_factory=list)
    storyTime: Literal['same_moment', 'continuous_motion', 'next_beat', 'time_jump', 'new_location', 'independent'] = 'next_beat'
    playability: Playability | None = None
    characterRoles: list[CharacterRole] = Field(default_factory=list)
    characterRoleEvents: list[CharacterRoleEvent] = Field(default_factory=list)
    sharedIdentityExceptions: list[SharedIdentityException] = Field(default_factory=list)


def card(shot, sources=None):
    """Content-addressed revision; never invent observations or approvals."""
    decision = shot.get('directorCard') or legacy_decisions(shot, 'post')
    body = {'schemaVersion': 1, 'contractVersion': VERSION, 'shotId': shot.get('id', shot.get('shotId')),
            'decisions': decision, 'sourceBindings': sources or {},
            'duration': shot.get('duration', shot.get('durationSec'))}
    body['revision'] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return body


def stage_decisions(shot, stage):
    d = shot.get('directorCard') or {}
    if not d:
        return legacy_decisions(shot, stage)
    if stage == 'see':
        return {**{k:d.get(k) for k in ('audienceFocus','cameraPurpose','handoff','storyTime')},
                'openingState': shot.get('openingState', shot.get('openingImageApproved', '')),
                'openingView': ({k:v for k,v in d['views'][0].items() if k in
                                ('viewId', 'framing', 'cameraPurpose', 'staging', 'startState', 'entry', 'viewpointOwner', 'cinematography')}
                                if d.get('views') else None),
                'openingActing': [{k:a.get(k) for k in ('character','attention','startingPose')} for a in d.get('acting',[])],
                'instructions': [i for i in d.get('instructions', []) if i.get('scope', {}).get('stage', 'see') == 'see'],
                'instruction':'Depict only the opening state. Later performance and views are not a montage.'}
    if stage == 'hear':
        # These decisions inform the voice specialist; only validated performedText
        # enters TTS. Visual revisions cannot silently re-perform approved speech.
        return {'audienceFocus': d.get('audienceFocus'), 'acting': d.get('acting', []),
                'spokenPerformance': shot.get('dialogue', []),
                'instruction': 'Translate playable intention and cadence into performedText while preserving every approved spoken word.'}
    return {**d, 'soundCues': [c for c in d.get('soundCues', []) if c.get('destination') == 'watch']} if stage == 'watch' else d


def legacy_decisions(shot, stage):
    """Read existing approved authorities without rewriting or inventing direction.

    Crystal Bears has typed storyboard and performance stores already. This is a
    projection of those records, not a second authorable performance contract.
    """
    common = ('storyIntentApproved', 'cinematographyContractApproved', 'shotTransition')
    selected = common + (('openingImageApproved',) if stage == 'see' else
                         ('performanceContractApproved', 'animationTimingApproved',
                          'comedyContractsApproved', 'emotionContractsApproved') if stage == 'hear' else
                         ('performanceContractApproved', 'performanceBudgetApproved', 'animationTimingApproved',
                          'comedyContractsApproved', 'emotionContractsApproved',
                          'storyboardInternalShotPlanApproved', 'storyboardStagePlanApproved'))
    values = {key: shot[key] for key in selected if shot.get(key)}
    # A transition alone is not evidence that a specialist directed the acting.
    if not any(key in values for key in common[:2] + ('performanceContractApproved',)):
        return {}
    if stage == 'see':
        values['openingImage'] = (shot.get('shotTransition') or {}).get('openingImage', '')
        views = shot.get('storyboardInternalShotPlanApproved') or []
        if views and any(views[0].get(k) for k in ('staging','startState')):
            values['openingCoverage'] = {k: v for k, v in views[0].items() if k in
                                       ('viewId', 'framingAndCamera', 'staging', 'startState')}
        values['instruction'] = 'Compose only the authored opening instant; later acting belongs to WATCH.'
    return {'authority': 'projection of existing approved production records', **values}


def validate_coverage(scenes, shots):
    """Validate authored view allocation, never invent coverage for legacy plans."""
    if not scenes:
        return
    scene_ids, views, assigned = set(), {}, set()
    for scene in scenes:
        scene = scene.model_dump() if hasattr(scene, 'model_dump') else scene
        number = scene['scene']
        if number in scene_ids or not scene['audienceJourney'].strip() or not scene['views']:
            raise ValueError('Scene coverage needs one audience journey and its planned views per scene.')
        scene_ids.add(number)
        for view in scene['views']:
            key = (number, view['viewId'])
            if key in views or any(not str(view.get(k, '')).strip() for k in
                                  ('viewId', 'audienceNeed', 'framing', 'cameraPurpose', 'cutReason', 'continuity', 'productionChoice')):
                raise ValueError('Every coverage view needs a unique ID and a readable story, camera and continuity decision.')
            views[key] = CoverageView.model_validate(view).model_dump()
    for shot in shots:
        shot = shot.model_dump() if hasattr(shot, 'model_dump') else shot
        number = shot.get('scene')
        if number is None:  # Gate 4 is scoped to a single scene.
            number = next(iter(scene_ids)) if len(scene_ids) == 1 else None
        if number not in scene_ids:
            raise ValueError('A generation unit has no preceding scene coverage.')
        d = shot.get('directorCard') or {}
        if not d.get('views'):
            raise ValueError('Allocate planned scene views into the unit Director Card before generation.')
        for view in d['views']:
            key = (number, view['viewId'])
            if key not in views:
                raise ValueError(f"A unit invented scene view {key[1]} in {shot.get('shotId', shot.get('id', 'unnamed unit'))}: author it in scene coverage before allocation.")
            if key in assigned:
                raise ValueError(f"A unit duplicated scene view {key[1]} in {shot.get('shotId', shot.get('id', 'unnamed unit'))}: allocate each viewId exactly once; different camera angles need distinct upstream views.")
            if views[key] != CoverageView.model_validate(view).model_dump():
                raise ValueError(f"A unit changed scene view {key[1]} during clip allocation: preserve the upstream camera and performance decision.")
            assigned.add(key)
    missing = [key for key, view in views.items() if key not in assigned and
               view['productionChoice'] not in {'existing media in post', 'remove'}]
    if missing:
        raise ValueError('Planned scene views were lost during clip allocation: ' + ', '.join(key[1] for key in missing))


def assessment(shot, *, candidate=None, reports=(), join_reviewed=False):
    """Four separate evidence questions. No score is a claim about the film."""
    latest = next((r for r in reversed(list(reports)) if r.get('current') and
                   r.get('candidateId') == (candidate or {}).get('id')), None)
    planning = (shot.get('directorCard') or {}).get('playability') or shot.get('performanceBudgetApproved') or {}
    return {'coverage': 'authored' if shot.get('directorCard') else 'legacy direction',
            'playability': planning.get('decision', 'unverified'),
            'observedResult': 'reviewed with limitations' if latest else 'unverified',
            'audienceReadability': 'human reviewed' if join_reviewed else 'unverified',
            'humanApproval': (candidate or {}).get('status', 'awaiting render'),
            'reviewId': (latest or {}).get('id'),
            'originatingRevision': ((candidate or {}).get('directorCardRevision') or {}).get('revision')}


REVIEW_CRITERIA = {
    'cinematicLanguage': 'Does framing and the cut reveal the intended action, thought or relationship? Is movement or stillness motivated?',
    'acting': 'Do speakers and listeners have readable attention, intention, pose, timing and physical weight? Assess deliberate stillness without penalising it.',
    'dialogue': 'Assess actual audible performance and picture sync only when audio was inspected; input binding alone is not audible verification.',
    'physicalContinuity': 'Compare prop/effect ownership, state, contact and cause with intended state; do not promote output errors to canon.',
    'scope': 'State exact inspected media, sampling and missing audio/neighbours. Review is advisory, never approval.'}
