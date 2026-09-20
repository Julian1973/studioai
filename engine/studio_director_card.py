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


# FEATURE-ANIMATION COVERAGE AND VISUAL STORYTELLING — DIRECT craft, not a pipeline stage.
# The Golden Path is unchanged; every decision below is written into the existing
# sceneCoverage and directorCard.views. Craft source: the Coverage Chair skill.
COVERAGE_KINDS = ('hold', 'establishing', 'master', 'cut_in', 'insert', 'reaction', 'reveal',
                  'world_texture', 'match_on_action', 'transition', 'landing', 'two_shot', 'pov')
COVERAGE_KIND_ALIASES = {'environment': 'world_texture', 'establish': 'establishing', 'payoff': 'landing',
                         'cut-in': 'cut_in', 'cutin': 'cut_in', 'match-on-action': 'match_on_action'}
# Editorial motivation: WHY the image changes, decided before HOW.
CUT_MOTIVATIONS = ('PLACE', 'FEEL', 'SEE', 'KNOW', 'REACT', 'LAUGH', 'FEAR', 'MOVE', 'BREATHE',
                   'REVEAL', 'SOUND', 'CONTRAST')
CUT_MOTIVATION_ALIASES = {
    'emotional change': 'FEEL', 'physical action': 'MOVE', 'new information': 'KNOW',
    'object interaction': 'SEE', 'reaction': 'REACT', 'sound': 'SOUND', 'visual reveal': 'REVEAL',
    'comedy beat': 'LAUGH', 'movement': 'MOVE', 'change of attention': 'SEE',
    'rhythmic contrast': 'CONTRAST', 'geography': 'PLACE', 'atmosphere': 'BREATHE', 'tension': 'FEAR',
    'establish': 'PLACE', 'anticipation': 'FEAR', 'information': 'KNOW', 'emotion': 'FEEL'}
CUT_TIMINGS = ('before', 'on', 'after')
ACTION_PHASES = ('preparation', 'contact', 'completion', 'consequence', 'reaction')
WORLD_FUNCTIONS = ('establish place', 'establish mood', 'create anticipation', 'create contrast',
                   'show scale', 'plant', 'pay off', 'control rhythm', 'create comedy',
                   'create emotion', 'bridge time', 'bridge space')
SCENE_MODES = ('contemplative', 'dialogue', 'warm comedy', 'energetic comedy', 'suspense',
               'action', 'reveal')
SCENE_FUNCTIONS = ('introduce', 'establish', 'connect', 'escalate', 'reveal', 'confront', 'celebrate',
                   'threaten', 'recover', 'transition', 'resolve', 'pay off')
ATTENTION_PRIORITIES = ('character thought', 'character performance', 'physical action', 'object',
                        'reaction', 'relationship', 'world', 'information', 'reveal', 'comedy',
                        'anticipation', 'threat', 'scale', 'beauty', 'stillness')


def canonical_kind(value):
    if value is None:
        return None
    key = str(value).strip().lower().replace(' ', '_')
    return COVERAGE_KIND_ALIASES.get(key, key)


def canonical_motivation(value):
    if value is None:
        return None
    text = str(value).strip()
    if text.upper() in CUT_MOTIVATIONS:
        return text.upper()
    return CUT_MOTIVATION_ALIASES.get(text.lower(), text)

FEATURE_COVERAGE_CONTRACT = '''CONTEXTUAL COVERAGE AND VISUAL STORYTELLING — DIRECT craft, inside DIRECT, one creative authority. The script supplies story truth; DIRECT turns it into an intentional sequence of images. Never character enters, performs the action, says the line, camera watches, next action. Ask what the audience should SEE, what they should FEEL, what they should NOTICE, what they should NOT see yet, whose reaction carries the moment, what physical detail gives the action weight, whether the world needs to breathe, and whether the camera should stay or whether changing the image makes the beat stronger. The objective is not more shots; it is better visual decisions.
NORTH STAR. DIRECT does not seek coverage; it seeks the most expressive sequence of images for the current beat. Change the audience's view only when it improves story, emotion, comedy, information, physicality, atmosphere, anticipation, geography, rhythm or relationship. Otherwise HOLD. A hold is a directing decision, not an absence of one: an emotional transition, a character thinking before speaking, sustained tension, intimate dialogue, a gag that works through anticipation, an uninterrupted physical performance, a reveal the audience must search the frame for. Coverage must never destroy good acting; performance outranks coverage. Never add a view because coverage is expected, because it should feel cinematic, because there has been no cut for a while, because an insert would look nice, or because feature animation uses many shots.
DECISION ORDER. Story, scene, beat, its emotional or comedic or informational value, performance, audience attention, rhythm, then the coverage decision, then camera, lens and composition. Never script, pick shot types, decorate with camera language.
STORY CONTEXT FIRST. Before planning a unit, know what happened immediately before, what the audience already knows, what the characters know and do not know, the current emotional and relationship state, location and established geography, current and planted props, weather and world state, the current pace and the previous unit's rhythm, what this scene sets up and what the next beat needs. Use only the script, approved canon, current production state and current DIRECT authority; invent nothing.
AUDIENCE KNOWLEDGE. Reason from a ledger of what the audience has already been given: location established, geography established, relationships and positions established, prop planted, prop state, weather, mood, information revealed, information withheld, visual motif. Its purpose is to avoid redundant filmmaking: do not establish a place the audience knows and that has not changed; do not insert a prop already planted unless its state now matters; do not cut to the same generic reaction again. Carry this in the current DIRECT context; it is not new persistent state.
SCENE FUNCTION AND BEAT SPINE. Name what the scene is primarily doing (introduce, establish, connect, escalate, reveal, confront, celebrate, threaten, recover, transition, resolve, pay off). For each unit name its spine: start state, the change, landing state. Coverage exists to make that change land. Name the attention priority the camera serves (thought, performance, action, object, reaction, relationship, world, information, reveal, comedy, anticipation, threat, scale, beauty, stillness); do not automatically photograph the speaking character.
HOLD OR CUT, THEN WHY, THEN HOW. If the current composition already carries the beat better than another view would, hold. If cutting, name the motivation before choosing the shot: PLACE (geography, world, scale), FEEL (emotion, relationship), SEE (physical or object detail), KNOW (new information), REACT (consequence, listener), LAUGH (comedy timing), FEAR (anticipation, threat, tension), MOVE (physical momentum), BREATHE (atmosphere, rhythm), REVEAL (control when information is discovered), SOUND (a sound redirects attention), CONTRAST (visual or rhythmic contrast strengthens the beat). A cut without a meaningful motivation is removed. Place the cut before the event for anticipation, on it for energy, after it to let the consequence land.
VOCABULARY, NEVER QUOTAS: hold, establishing, master, cut_in, insert, reaction, reveal, world_texture, match_on_action, transition, landing. No unit must contain any particular type.
ESTABLISHING. Do not start every scene on the principal character. Consider whether place, mood, scale or contrast deserves to be experienced first: sky, birds, weather, landscape, architecture, environmental movement, distant activity, decorations, foreground life, objects, evidence of earlier action, anticipation of what comes. Birds cross a luminous morning sky, their movement carries the eye down, the place appears below, decorations catch the light, the camera descends and discovers the character already there — justified when it establishes peace, place and optimism before the disruption. Never repeat the establishing logic when the audience knows the place and nothing has changed.
WORLD TEXTURE. Environmental or detail imagery makes the world feel alive when each image performs a function: establish place, establish mood, create anticipation, create contrast, show scale, plant information, pay off information, control rhythm, create comedy, create emotion, bridge space, bridge time. If none applies, do not add it. Only entities the world record supplies may appear.
MASTER. Use one when geography genuinely needs establishing or re-establishing: where are we, where is everyone, spatial relationships, where they can move, screen direction. Once established, do not mechanically open every unit with a master; a later unit may begin on a face, a paw, an object, a detail, a reaction or movement already underway, provided the audience stays oriented.
CUT-INS AND INSERTS. Cut in when tighter attention strengthens emotion, decision, recognition, information, intimacy or physical action; show the thought before the line (her gaze stops, half a beat, the smile changes). Insert when a physical or object event matters (a paw closing around a handle, a raindrop hitting cloth, a door handle turning, icing beginning to run); not every prop interaction.
ACTION CHAINS. For a meaningful physical action identify preparation, contact, completion, consequence, reaction and decide which phases deserve emphasis; if the action is incidental business, hold the medium and let the character complete it naturally. The chain must stay complete and readable.
REACTIONS. For every meaningful action or line ask whether the consequence is more interesting than the source; comedy often lives in the reaction, emotion in the listener. A reaction must react to something specific and carry meaning, emotion, comedy, tension, relationship or information; never a generic reaction shot. Listeners act; only the named speaker articulates their dialogue.
PHOTOGRAPH THOUGHT. Attention, recognition, thought, decision, anticipation, action, consequence, reaction. "She looks worried" is description; "she sees the wet mark, her eyes stop, half a beat, she checks whether anyone noticed, she forces the smile back, then she speaks" is direction, and the framing makes the thought readable.
REVEALS AND SOUND. Control when information enters the frame so the audience discovers it with the character (the party continues, the bunting moves differently, she notices, her eyeline rises, cut to the cloud). Sound may lead picture (a bird call, thunder, a cup clink, an off-screen crash, a door) and picture may anticipate sound; scripted dialogue is never rewritten.
DEPTH, SENTENCE, CONTRAST, PROGRESSION, CAMERA. Foreground, midground and background carry depth, relationships, world life, anticipation, visual jokes, scale and secondary action without clutter or stealing the beat. Think in the visual sentence the sequence forms (peaceful birds, beautiful clearing, her confidence, the raindrop, her eyes, the forced smile: everything is perfect, except it isn't). Use contrast deliberately: wide to close, movement to stillness, busy to simple, bright to dark, fast to hold, character to object, speaker to listener, world to intimate detail; never vary for variety. Avoid the same size four times running when dramatic progression calls for change; there is no required template. Camera movement has a reason (discover, follow, reveal, transfer attention, change intimacy or scale, build or release tension), normally one intention per view; static is often stronger; never drift because generation likes motion. Preserve screen side, movement direction, eyelines and the axis; cross it only through a motivated neutral view.
RHYTHM. Shot rhythm follows the beat, never the provider's generation length: inside one unit views may run 0.8, 1.5, 3 or 5 seconds. Tendencies: contemplative holds longer, dialogue moderate, warm comedy responsive reactions, energetic comedy faster where justified, suspense short views with deliberate holds, action fast but readable, reveal or payoff often held after. Direct rhythm in context, never a unit in isolation: what was the pace before, what does the audience need now, what follows; a breath after a fast sequence, shortening cuts through escalation, a longer hold after an emotional reveal, space before a comedy payoff.
OPENING AND LANDING. Every unit enters deliberately (world, detail, movement, reaction, character, object, geography, a sound-motivated image; not automatically the principal character) and lands on something worth cutting from: a reaction, a decision, a completed action, a payoff, a reveal, a new problem, stillness, a comedy button. A generation never merely runs out of seconds.
INTERNAL COVERAGE IS THE DEFAULT. One generation unit, one opening keyframe, one provider request, many authored internal views; WATCH compiles those exact views. Split into another unit only for the provider duration limit, a major location, time or story-state change, coverage the provider cannot reliably execute internally, critical identity precision, complex choreography, a critical insert or reaction needing independent control, or a deliberate editorial boundary. Never split merely because there is a cut. Match-on-action inside a unit is authored normally; across units only when necessary, the new unit's keyframe generated from the declared state (editorial cut, no previous-frame dependency).
CAMERA LAW. Camera height is a story decision measured from the featured character's eye-line, not a number to invent: the engine derives the inches from the character's locked height and the show's shot grammar and places them in the provider's camera line. Write the intent — whose eye-line the camera lives at and why; low and looking up for scale or threat; above the canopy for the world; exactly at the eye-line for stillness — and name the subject (viewpointOwner or visibleEntities) so the law can measure. A subject under two feet tall is photographed from its own eye-line unless the view is about scale, so the world towers around them. Choose size from the ladder (EWS, WS, MWS, MS, MCU, CU, ECU) and write it in framing; lens follows relationship, wider to hold geography and two bodies, longer to press in on a thought. Put a directed camera move, lens relationship, focus and light in the cinematography record; the compiler carries them to the provider.
CAMERA AND LIGHT ARE EMOTIONAL DECISIONS, NEVER SPECS. For every view decide, in this order: what the audience must FEEL at this exact moment; the camera language for this world and beat (organic and breathing for energy, still and composed for weight; the show's own language lives in its shot grammar and the compiler states it once per prompt); the lens, stated in millimetres, chosen by emotion — wide (18–24 mm) for immersion, energy and the world rushing past; 35 mm natural and present; 50 mm honest and still for emotional weight, and when a moment needs weight lock the camera and let the character carry it; 85 mm intimate for reactions, a single tear or smile; long (100–135 mm) compressed and dreamy for isolation and distant wonder; what the light is saying and what in the world motivates it (key colour and direction: front lit is open, rim lit is held by the world, top lit is exposed, backlit silhouette is mystery; the key character gets the light, the secondary gets the fill; never flat, never from nowhere); and the frame — horizontals for openness, verticals for scale and vulnerability, negative space to make a character small in a vast world, a tight frame for intimacy, centring only as a deliberate choice. A move needs a story trigger and a finish (slow dolly in for wonder, pull back for isolation, handheld breathing for energy, crane or tilt up for scale, whip pan for a comedy crash, rack focus to redirect attention); a locked camera is a choice about stillness, never a default. Match the lens to the emotional temperature: wide in a quiet moment feels cheap, telephoto in fast action feels disconnected; eye-level for everything is one tool used as a crutch. Where the show's grammar gives a character their own camera (steadier, more energetic, locked off on a deadpan line), honour it; the engine appends that rule to the character's camera line. Write lens (with the why), movement, focus, light and composition in the view's cinematography record; the compiler carries each to the provider's Camera line word for word; the only edit is that a character's name gains its reference tag.
HOW TO WRITE IT. Inside each view's cinematography record set kind (the vocabulary above), motivation (PLACE, FEEL, SEE, KNOW, REACT, LAUGH, FEAR, MOVE, BREATHE, REVEAL, SOUND, CONTRAST), cutTiming (before, on, after), actionPhase for chains, functions for world texture, and attention (the priority the view serves). A hold is a view whose kind is hold, whose motivation is null (motivations belong to cuts, never to a hold) and whose cutReason says why staying is stronger. Record the scene's entrance, function and mode on sceneCoverage. Reaction views name the listener as viewpointOwner with listenerReaction; world-texture views list no character entity. Keep cutReason, cutTo, staging, action, performance, timing, startState and endState exact as before.
BEFORE PUBLISHING ask: does this feel observed or merely described; can I see the character thinking; does the environment participate; does the audience know where to look; are important physical contacts visible; are reactions specific; is there visual contrast; does the camera have intention; does the sequence breathe; does the ending land; does it read as a visual sentence; would it still communicate with the dialogue muted; is anything here only because coverage was expected. If so, improve or remove before publication. These are creative judgements, never runtime blockers; the software checks only structure.'''

CONTRACT += '\n' + FEATURE_COVERAGE_CONTRACT

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
    entrance: str | None = Field(default=None, description='How and why the scene is entered: through the world (what we see before the characters), a hard cut in, a detail, a sound-motivated image.')
    mode: Literal['contemplative', 'dialogue', 'warm comedy', 'energetic comedy', 'suspense', 'action', 'reveal'] | None = Field(default=None, description='Dramatic mode that sets the rhythm tendency for this scene.')
    function: Literal['introduce', 'establish', 'connect', 'escalate', 'reveal', 'confront', 'celebrate', 'threaten', 'recover', 'transition', 'resolve', 'pay off'] | None = Field(default=None, description='What the scene is primarily doing; creative reasoning, not a gate.')
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



def coverage_issues(view, previous=None):
    """Objective checks on the Phase-1 coverage vocabulary. Never a taste verdict."""
    issues = []
    cinema = view.get('cinematography') or {}
    if not isinstance(cinema, dict):
        return ['cinematography must be a record']
    kind = canonical_kind(cinema.get('kind'))
    if kind is not None and kind not in COVERAGE_KINDS:
        issues.append(f"unknown coverage kind {cinema.get('kind')!r}; use one of {', '.join(COVERAGE_KINDS)}")
    motivation = canonical_motivation(cinema.get('motivation'))
    if motivation is not None and motivation not in CUT_MOTIVATIONS:
        issues.append(f"unknown cut motivation {cinema.get('motivation')!r}; use one of {', '.join(CUT_MOTIVATIONS)}")
    attention = cinema.get('attention')
    if attention is not None and str(attention).lower() not in ATTENTION_PRIORITIES:
        issues.append(f"unknown attention priority {attention!r}; use one of {', '.join(ATTENTION_PRIORITIES)}")
    timing = cinema.get('cutTiming')
    if timing is not None and timing not in CUT_TIMINGS:
        issues.append(f"cutTiming must be one of {', '.join(CUT_TIMINGS)}")
    phase = cinema.get('actionPhase')
    if phase is not None and phase not in ACTION_PHASES:
        issues.append(f"unknown actionPhase {phase!r}; use one of {', '.join(ACTION_PHASES)}")
    functions = cinema.get('functions')
    if functions is not None:
        if not isinstance(functions, list) or any(f not in WORLD_FUNCTIONS for f in functions):
            issues.append(f"functions must list only {', '.join(WORLD_FUNCTIONS)}")
    visible = view.get('visibleEntities')
    if kind == 'world_texture':
        if not functions:
            issues.append('a world-texture view must name at least one function it performs')
        if visible and any(str(e).startswith(('character:', 'char:')) for e in visible):
            issues.append('a world-texture view shows the world, not a character entity')
    if kind == 'hold' and motivation is not None:
        issues.append('a hold has no cut motivation; its cutReason says why staying is stronger')
    if kind == 'reaction' and not (view.get('viewpointOwner') or view.get('listenerReaction')):
        issues.append('a reaction view names the listener (viewpointOwner) or listenerReaction')
    if phase and previous:
        prev_cinema = previous.get('cinematography') or {}
        prev_phase = prev_cinema.get('actionPhase') if isinstance(prev_cinema, dict) else None
        same_beat = view.get('sourceBeat') and view.get('sourceBeat') == previous.get('sourceBeat')
        if same_beat and prev_phase in ACTION_PHASES and ACTION_PHASES.index(phase) < ACTION_PHASES.index(prev_phase):
            issues.append(f"action chain runs backwards: {prev_phase} then {phase} within the same beat")
    return issues


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
        if scene.get('mode') is not None and scene['mode'] not in SCENE_MODES:
            raise ValueError(f"Scene {number} mode must be one of {', '.join(SCENE_MODES)}.")
        previous = None
        for view in scene['views']:
            key = (number, view['viewId'])
            if key in views or any(not str(view.get(k, '')).strip() for k in
                                  ('viewId', 'audienceNeed', 'framing', 'cameraPurpose', 'cutReason', 'continuity', 'productionChoice')):
                raise ValueError('Every coverage view needs a unique ID and a readable story, camera and continuity decision.')
            problems = coverage_issues(view, previous)
            if problems:
                raise ValueError(f"Scene {number} view {view['viewId']}: " + '; '.join(problems))
            views[key] = CoverageView.model_validate(view).model_dump()
            previous = view
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
