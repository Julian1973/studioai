"""One typed WATCH execution plan and source-bound, request-local revisions.

No creative inference, file mutation or model calls. Legacy provider prose is an
intake source for immutable audio sections only; it never supplies visual action.
"""
from copy import deepcopy
from collections import Counter
import hashlib
import json
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

VERSION = 'watch-plan@1.0.0'
AUDIO_HEADINGS = ('Dialogue Authority', 'Audio', 'AUDIO AND EXCLUSIONS', 'AUDIO', 'Audio Authority')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class View(Record):
    viewId: str = Field(min_length=1)
    startSec: float = Field(ge=0)
    endSec: float = Field(gt=0)
    entry: Literal['opening', 'cut', 'move', 'hold']
    visibleEntities: list[str] | None = None
    purpose: str = ''
    camera: str = Field(min_length=1)
    action: str = Field(min_length=1)
    performance: str = Field(min_length=1)
    setting: str = ''
    opening: str = ''
    landing: str = Field(min_length=1)
    dialogue: list[str] = Field(default_factory=list)
    holds: list[str] = Field(default_factory=list)


class DialogueOccurrence(Record):
    speaker: str
    text: str
    startSec: float = Field(ge=0)
    endSec: float = Field(gt=0)
    viewId: str
    sourceIndex: int = Field(ge=1)
    placement: Literal['view', 'audio-block']


class WatchPlan(Record):
    version: Literal['watch-plan@1.0.0'] = VERSION
    sourceHash: str
    requestBindingHash: str
    purpose: str = Field(min_length=1)
    views: list[View] = Field(min_length=1)
    opening: str = ''
    causality: str = ''
    landing: str = ''
    geography: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    sound: list[str] = Field(default_factory=list)
    audioBlocks: list[str] = Field(default_factory=list)
    dialogueTiming: list[str] = Field(default_factory=list)
    dialogueOccurrences: list[DialogueOccurrence] = Field(default_factory=list)
    origins: dict[str, str] = Field(default_factory=dict)
    compatibility: Literal['native-specialist', 'project-director-card']

    @model_validator(mode='after')
    def continuous_intervals(self):
        if self.views[0].startSec != 0 or any(a.endSec != b.startSec for a, b in zip(self.views, self.views[1:])):
            raise ValueError('WATCH view intervals must cover the unit without gaps or overlaps')
        if any(v.startSec >= v.endSec for v in self.views):
            raise ValueError('WATCH view intervals must have positive duration')
        if len({v.viewId for v in self.views}) != len(self.views):
            raise ValueError('WATCH views require unique source view IDs')
        return self


class PlanCorrection(Record):
    expectedPlanHash: str = Field(min_length=1)
    path: str = Field(min_length=1, description='Exact /specialist/... origin of an emitted typed plan field; never a prompt span or approved shot field.')
    expected: str
    value: str = Field(min_length=1)
    sourcePath: str = Field(min_length=1, description='JSON pointer into authorities containing the existing approved evidence for this correction.')
    sourceHash: str = Field(min_length=1, description='Digest of the exact current sourcePath value.')
    reason: str = Field(min_length=1)


def pointer(value, path):
    if not path.startswith('/'):
        raise ValueError('A source binding must be an absolute JSON pointer')
    try:
        for key in path[1:].split('/'):
            key = key.replace('~1', '/').replace('~0', '~')
            value = value[int(key)] if isinstance(value, list) else value[key]
        return value
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ValueError('Unknown source binding: ' + path) from exc


def _assign(value, path, replacement):
    parent, _, key = path.rpartition('/')
    target = pointer(value, parent)
    target[int(key) if isinstance(target, list) else key] = replacement


def request_binding(snapshot):
    return digest({k: snapshot.get(k) for k in ('authorities', 'references', 'audio', 'duration', 'settings')})


def _audio_blocks(prompt):
    from studio_seedance_execution import sections
    blocks = [(heading, block) for heading, block in sections(prompt) if heading in AUDIO_HEADINGS]
    if len({heading for heading, _ in blocks}) != len(blocks):
        raise ValueError('Duplicate Audio1 authority sections require source reconciliation')
    return [block for _, block in blocks]


def build_plan(snapshot):
    authority = snapshot.get('authorities') or {}
    shot, specialist = authority.get('shot') or {}, authority.get('specialist') or {}
    card = shot.get('directorCard') or {}
    views = card.get('views') or []
    directed = specialist.get('shotPlan') or []
    if not views:
        raise ValueError('WATCH plan adaptation unavailable: author timed typed coverage before provider compilation')
    from studio_storyboard_prompt import view_timings, validate_view_bindings
    if directed:
        validate_view_bindings(shot, directed)
    intervals = view_timings(shot, len(views))
    if not all(intervals):
        raise ValueError('WATCH plan requires explicit source view intervals; prose and inferred equal timing are unsupported')
    if intervals[-1][1] != float(snapshot['duration']):
        raise ValueError('WATCH plan duration does not match this immutable request')
    origins = {}
    def select(target, choices, default=''):
        for path in choices:
            try:
                value = pointer(authority, path)
            except ValueError:
                continue
            if value is not None and value != '' and value != []:
                origins[target] = path
                return deepcopy(value)
        return deepcopy(default)
    plan = dict(version=VERSION, sourceHash=digest(authority), requestBindingHash=request_binding(snapshot),
        compatibility='native-specialist' if directed else 'project-director-card', origins=origins,
        purpose=select('/purpose', ['/shot/directorCard/audienceFocus', '/specialist/dramaticBeat', '/specialist/generationGoal', '/shot/intent', '/shot/purpose']),
        opening=select('/opening', ['/shot/openingState', '/specialist/stagePlan/0/initialOrCarriedState']),
        causality=select('/causality', ['/specialist/physicalCauseAndEffect']),
        landing=select('/landing', ['/shot/endingState', '/shot/directorCard/handoff', '/specialist/continuityFinish']),
        geography=select('/geography', ['/specialist/geography'], [shot['geography']] if shot.get('geography') else []),
        invariants=select('/invariants', ['/specialist/consistencyContract']),
        sound=[], audioBlocks=_audio_blocks(snapshot.get('prompt', '')), dialogueTiming=[], dialogueOccurrences=[], views=[])
    for key in ('geography', 'invariants'):
        if key == 'invariants' and isinstance(plan[key], str):
            plan[key] = [plan[key]]
        origin = origins.get('/' + key)
        if origin:
            for i in range(len(plan[key])):
                origins[f'/{key}/{i}'] = f'{origin}/{i}'
    from cb_emission_conformance import dialogue_cues, dialogue_placement_line
    lines = shot.get('dialogueLines') or []
    if shot.get('dialogue') and not lines:
        # The project adapter binds measured HEAR timings into dialogueLines. Never
        # invent voice timing from text or allocate it by equal duration.
        raise ValueError('Project WATCH needs measured HEAR dialogueLines before plan adaptation')
    from cb_audio_authority import route_lines
    routed = route_lines(lines)
    spoken_lines = routed['spokenDialogue']
    cues = dialogue_cues(spoken_lines, duration_sec=snapshot['duration']) if spoken_lines else []
    cue_by_source = {line['_sourceDialogueIndex']: cue for line, cue in zip(spoken_lines, cues)}
    sfx_by_source = {cue['sourceDialogueIndex']: cue for cue in routed['seedanceSfxCues']}
    assigned = set()
    audio_occurrences = Counter(re.findall(r'\{([^{}]+)\}', '\n'.join(plan['audioBlocks'])))
    for i, (view, interval) in enumerate(zip(views, intervals)):
        typed = directed[i] if directed else {}
        base, target, native = f'/shot/directorCard/views/{i}', f'/views/{i}', f'/specialist/shotPlan/{i}'
        def field(name, source, fallback, default=''):
            return select(target + '/' + name, [native + '/' + fallback, base + '/' + source], default)
        row = dict(viewId=view['viewId'], startSec=interval[0], endSec=interval[1],
            entry=typed.get('transitionType') if typed.get('transitionType') in ('opening','cut','move','hold') else view.get('entry', 'opening' if i == 0 else 'hold'),
            visibleEntities=deepcopy(view.get('visibleEntities')),
            purpose=field('purpose', 'cameraPurpose', 'purpose'),
            camera=field('camera', 'framing', 'framingLensAndCamera'),
            action=field('action', 'action', 'causalAction'),
            performance=field('performance', 'performance', 'observablePerformance'),
            setting=field('setting', 'staging', 'compositionLightAndMaterials'),
            opening=field('opening', 'startState', 'initialOrCarriedState'),
            landing=field('landing', 'endState', 'landingImage'), dialogue=[], holds=[])
        indexes = typed.get('dialogueLineIndexes') if directed else [number for number, cue in cue_by_source.items() if interval[0] <= cue['startSec'] < interval[1]]
        for pos, number in enumerate(indexes or []):
            if number in assigned or number not in cue_by_source and number not in sfx_by_source:
                raise ValueError('WATCH dialogue occurrence must have one valid typed view owner')
            if number not in cue_by_source:
                assigned.add(number)
                continue
            cue = cue_by_source[number]
            if not interval[0] <= cue['startSec'] < interval[1]:
                raise ValueError('WATCH dialogue owner disagrees with measured Audio1 timing')
            directions = typed.get('dialogueDirections') or []
            in_audio = audio_occurrences[cue['exactText']] > 0
            if in_audio:
                audio_occurrences[cue['exactText']] -= 1
            else:
                row['dialogue'].append(dialogue_placement_line(cue,
                    direction=directions[pos] if pos < len(directions) else '',
                    hold_after=bool(typed.get('holdAfterDialogue', True))))
            plan['dialogueOccurrences'].append(dict(speaker=cue['speaker'], text=cue['exactText'],
                startSec=cue['startSec'], endSec=cue['endSec'], viewId=view['viewId'], sourceIndex=number,
                placement='audio-block' if in_audio else 'view'))
            assigned.add(number)
        clocks = (specialist.get('creativeTranslation') or {}).get('gagClocks') or []
        for clock in clocks:
            beat = clock.get('beatCode')
            owners = [j for j, item in enumerate(directed) if beat in (item.get('gagBeatIds') or [])]
            if owners and owners[-1] == i:
                row['holds'].append(f"Hold: {float(clock['recoveryHoldSec']):.1f}s — {clock['recoveryHold']}")
        plan['views'].append(row)
    if not set(cue_by_source).issubset(assigned):
        raise ValueError('WATCH plan lacks explicit ownership for an approved dialogue occurrence')
    if any(audio_occurrences.values()):
        raise ValueError('Immutable audio block contains unmatched or repeated dialogue occurrences')
    plan['dialogueTiming'] = [f"{cue['speaker']}: {cue['startSec']:g}–{cue['endSec']:g}s." for cue in cues]
    for cue in card.get('soundCues') or []:
        if cue.get('destination') == 'watch':
            plan['sound'].append(f"{cue.get('timing', '')}: {cue['instruction']}")
    for item in specialist.get('timeline') or []:
        if item.get('channel') in ('music', 'sfx'):
            plan['sound'].append(f"{item['startSec']:g}–{item['endSec']:g}s: {item['event']}")
    for cue in routed['seedanceSfxCues']:
        timing = f"{cue['startSec']:g}–{cue['endSec']:g}s" if cue.get('startSec') is not None and cue.get('endSec') is not None else ''
        plan['sound'].append(f"{timing}: {cue.get('character') or ''}: {cue['instruction']}")
    handoff = specialist.get('soundHandoff') or shot.get('soundHandoff') or {}
    for key, label in (('entry', 'Sound entrance'), ('exit', 'Sound exit'), ('carrySound', 'Carry sound'), ('intentionalContrast', 'Intentional contrast')):
        if handoff.get(key):
            plan['sound'].append(f'{label}: {handoff[key]}')
    # Sound ownership remains sourced from an explicit sound contract, never a
    # generic instruction silently added after compilation.
    if specialist.get('audioContract') and not plan['audioBlocks']:
        plan['audioBlocks'] = ['[Audio]\n' + specialist['audioContract']]
    if cues and not plan['audioBlocks']:
        raise ValueError('WATCH plan requires the immutable approved Audio1 provider block')
    return WatchPlan.model_validate(plan).model_dump()


def prepare_plan(snapshot):
    result = deepcopy(snapshot)
    if 'watchPlan' in result:
        plan = WatchPlan.model_validate(result['watchPlan']).model_dump()
        if plan['requestBindingHash'] != request_binding(result) or plan['sourceHash'] != digest(result.get('authorities')):
            raise ValueError('WATCH plan is stale for its source, references, audio or request contract')
        # Rebuild from typed source; a caller cannot insert unbound plan wording.
        if build_plan(result) != plan:
            raise ValueError('WATCH plan differs from its originating typed source')
    else:
        plan = build_plan(result)
    result['watchPlan'] = plan
    binding = dict(version=VERSION, planHash=digest(plan),
        sourceHash=plan['sourceHash'], requestBindingHash=plan['requestBindingHash'],
        origin='request-local projection; approved source records unchanged')
    if 'watchPlanBinding' in result and result['watchPlanBinding'] != binding:
        raise ValueError('WATCH plan binding differs from its current typed source')
    result['watchPlanBinding'] = binding
    return result


def correct_plan(snapshot, corrections):
    """Revise emitted typed origins only, then rebuild from those source fields.

    Approved shot/card, audio, timelines, identities and settings are immutable.
    Every repair is source-bound and needs semantic review of the revised plan.
    """
    original = prepare_plan(snapshot)
    working = deepcopy(original)
    before_hash = digest(original['watchPlan'])
    trace = []
    protected_keys = ('audioBlocks', 'dialogueTiming', 'dialogueOccurrences')
    for raw in corrections:
        correction = PlanCorrection.model_validate(raw).model_dump()
        if correction['expectedPlanHash'] != before_hash:
            raise ValueError('Plan correction belongs to a different plan revision')
        path = correction['path']
        origins = original['watchPlan']['origins']
        if not path.startswith('/specialist/') or path not in origins.values():
            raise ValueError('Correction must address an emitted request-local specialist field; approved source decisions are immutable')
        old = pointer(working['authorities'], path)
        if not isinstance(old, str) or old != correction['expected']:
            raise ValueError('Plan correction expected value does not match its typed origin')
        if re.search(r'(?m)^\s*\[', correction['value']) or re.findall(r'@(?:图|Image|Audio|Video)\d+', old) != re.findall(r'@(?:图|Image|Audio|Video)\d+', correction['value']):
            raise ValueError('Typed correction cannot introduce provider sections or alter resource tags')
        if any(key in correction['sourcePath'].split('/') for key in ('providerPrompt', 'seedancePrompt', 'watchPrompt', 'keyframePrompt', 'seedreamPrompt')):
            raise ValueError('Historical provider prose is not approved correction authority')
        source = pointer(original['authorities'], correction['sourcePath'])
        if not correction['sourcePath'].startswith('/shot/') or digest(source) != correction['sourceHash']:
            raise ValueError('Plan correction needs current approved shot-source evidence')
        _assign(working['authorities'], path, correction['value'])
        trace.append(correction)
    working.pop('watchPlan', None)
    working.pop('watchPlanBinding', None)
    revised = prepare_plan(working)
    if any(revised['watchPlan'][k] != original['watchPlan'][k] for k in protected_keys) or [v['dialogue'] for v in revised['watchPlan']['views']] != [v['dialogue'] for v in original['watchPlan']['views']]:
        raise ValueError('Plan correction changed immutable audio or dialogue placement')
    receipt = dict(kind='request-local typed plan revision', originalPlanHash=before_hash,
        revisedPlanHash=digest(revised['watchPlan']), originalSourceHash=digest(original['authorities']),
        revisedSourceHash=digest(revised['authorities']), corrections=trace,
        approvedSourceMutated=False, requiresPlanReview=True, requiresPayloadReview=True)
    revised.setdefault('watchPlanRevisions', []).append(receipt)
    return revised, receipt


def scope_segment(snapshot, segment):
    """Project an explicit transport range onto whole source coverage views.

    Master script/audio and full approved direction remain in sourceUnit. Only
    request-local numeric clocks and selected occurrence indexes are rebased.
    A transport boundary cannot cut through an authored view or spoken line.
    """
    authority = snapshot.get('authorities') or {}
    shot, specialist = authority.get('shot') or {}, authority.get('specialist') or {}
    duration = float(shot.get('durationSec', shot.get('duration', 0)))
    start, end = segment.get('globalStartSec'), segment.get('globalEndSec')
    if start is None or end is None:
        if float(snapshot['duration']) != duration:
            raise ValueError('Segment needs explicit source globalStartSec/globalEndSec; duration alone cannot select a story sub-plan')
        return deepcopy(snapshot)
    start, end = float(start), float(end)
    if not 0 <= start < end <= duration or abs((end - start) - float(snapshot['duration'])) > .000001:
        raise ValueError('Segment global interval differs from the requested duration')
    if start == 0 and end == duration:
        return deepcopy(snapshot)
    from studio_storyboard_prompt import view_timings, validate_view_bindings
    views = (shot.get('directorCard') or {}).get('views') or []
    directed = specialist.get('shotPlan') or []
    if not views or not directed:
        raise ValueError('Segment projection requires the complete typed source coverage and specialist view bindings')
    intervals = view_timings(shot, len(views))
    validate_view_bindings(shot, directed)
    if not all(intervals):
        raise ValueError('Segment projection requires explicit source view intervals')
    selected = [i for i, (a, b) in enumerate(intervals) if start <= a and b <= end]
    if not selected or intervals[selected[0]][0] != start or intervals[selected[-1]][1] != end:
        raise ValueError('Transport boundary cuts through an approved coverage view; choose an authored view boundary before compilation')
    selected_ids = [views[i]['viewId'] for i in selected]
    if segment.get('sourceViewIds') and segment['sourceViewIds'] != selected_ids:
        raise ValueError('Segment sourceViewIds disagree with its exact authored time range')
    result = deepcopy(snapshot)
    local_authority = result['authorities']
    local_shot, local_direction = deepcopy(shot), deepcopy(specialist)
    # Keep the full original for immutable truth and later returned-media review.
    local_authority['sourceUnit'] = dict(shot=deepcopy(shot), specialist=deepcopy(specialist),
        shotHash=digest(shot), specialistHash=digest(specialist), authoritiesHash=digest(authority),
        segmentIndex=segment.get('segmentIndex'), globalStartSec=start, globalEndSec=end,
        sourceViewIds=selected_ids, sourceViewIndexes=selected, dialogueIndexMap=[])
    receipt = local_authority['sourceUnit']
    lines = shot.get('dialogueLines') or []
    indices = []
    for i, line in enumerate(lines):
        a, b = line.get('startSec'), line.get('endSec')
        if a is None or b is None:
            raise ValueError('Segment projection requires exact master dialogue timing')
        if a < end and b > start:
            if a < start or b > end:
                raise ValueError('Transport boundary cuts through an approved spoken occurrence')
            indices.append(i)
    if 'dialogueLineIndexes' in segment and segment['dialogueLineIndexes'] != indices:
        raise ValueError('Segment dialogue indexes disagree with the measured master intervals')
    if indices:
        audio = snapshot.get('audio') or {}
        if not isinstance(audio, dict) or audio.get('sourceStartSec') != start or audio.get('sourceEndSec') != end or not (audio.get('sourceMd5') or audio.get('sourceHash')):
            raise ValueError('Segment dialogue requires the exact source-bound Audio1 slice interval')
    index_map = {old + 1: new + 1 for new, old in enumerate(indices)}
    local_shot['dialogueLines'] = []
    for local_index, original_index in enumerate(indices):
        line = deepcopy(lines[original_index])
        line['startSec'] -= start; line['endSec'] -= start
        local_shot['dialogueLines'].append(line)
        receipt['dialogueIndexMap'].append(dict(sourceIndex=original_index, localIndex=local_index,
            occurrenceId=line.get('dialogueOccurrenceId'), sourceStartSec=lines[original_index]['startSec'],
            sourceEndSec=lines[original_index]['endSec'], localStartSec=line['startSec'], localEndSec=line['endSec']))
    local_shot['durationSec' if 'durationSec' in shot else 'duration'] = end - start
    local_direction['durationSec'] = end - start
    local_card = deepcopy(shot['directorCard'])
    local_card['views'] = []
    local_direction['shotPlan'] = []
    for local_index, original_index in enumerate(selected):
        view = deepcopy(views[original_index]); a, b = intervals[original_index]
        view.update(atSec=a - start, timing=f'{a-start:g}–{b-start:g}s')
        if local_index == 0:
            view['entry'] = 'opening'
        local_card['views'].append(view)
        row = deepcopy(directed[original_index])
        row['shotNumber'] = local_index + 1
        if local_index == 0:
            row['transitionType'] = 'opening'
        old_indexes = row.get('dialogueLineIndexes') or []
        if any(number not in index_map for number in old_indexes):
            raise ValueError('Selected view owns a dialogue occurrence outside its segment')
        row['dialogueLineIndexes'] = [index_map[number] for number in old_indexes]
        local_direction['shotPlan'].append(row)
    carried, carry_source = {}, {}
    pending = []
    for event in sorted(local_card.get('stateChanges') or [], key=lambda row: row.get('atSec', -1)):
        at = event.get('atSec')
        if at is None:
            raise ValueError('Segment projection requires explicit state-change times')
        entity = event.get('entityId')
        if at <= start and start > 0:
            if not entity or not event.get('afterValues'):
                raise ValueError('Segment entry state lacks a structured source handoff')
            current = carried.setdefault(entity, deepcopy(event.get('beforeValues') or {}))
            current.update(deepcopy(event['afterValues'])); carry_source[entity] = event
        elif start <= at <= end:
            projected = deepcopy(event); projected['atSec'] = at - start
            projected['timing'] = f'{at-start:g}s'
            pending.append(projected)
    carry_records = []
    for entity, values in carried.items():
        event = carry_source[entity]
        carry_records.append(dict(entityId=entity, subject=event.get('subject', entity), atSec=0,
            before=event.get('after', ''), after=event.get('after', ''), beforeValues=deepcopy(values), afterValues=deepcopy(values),
            cause=f'Carry completed source state at {start:g}s; do not replay its cause.', timing='0s',
            actionId='segment-entry:' + str(event.get('actionId') or entity)))
    local_card['stateChanges'] = carry_records + pending
    local_card['soundCues'] = []
    for cue in (shot['directorCard'].get('soundCues') or []):
        if cue.get('destination') != 'watch':
            continue
        interval = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*[–—-]\s*(\d+(?:\.\d+)?)\s*s?\s*', str(cue.get('timing') or ''))
        if not interval:
            raise ValueError('Segment sound cue requires an explicit authored interval')
        a, b = map(float, interval.groups())
        if a < end and b > start:
            if a < start or b > end:
                raise ValueError('Segment boundary cuts through an authored sound cue; direct its split explicitly')
            row = deepcopy(cue); row['timing'] = f'{a-start:g}–{b-start:g}s'; local_card['soundCues'].append(row)
    local_card['characterRoleEvents'] = [event for event in local_card.get('characterRoleEvents') or [] if event.get('viewId') in selected_ids]
    local_shot['directorCard'] = local_card
    # The original content-addressed approval remains intact in sourceUnit. The
    # local derivative is bound by this scoped source receipt, not falsely signed
    # with the full unit's directorCardSource hash.
    local_shot.pop('directorCardSource', None)
    if local_shot.get('storyboardInternalShotPlanApproved'):
        local_shot['storyboardInternalShotPlanApproved'] = [row for row in local_shot['storyboardInternalShotPlanApproved'] if row.get('viewId') in selected_ids]
    stages = []
    for stage in specialist.get('stagePlan') or []:
        a, b = stage.get('startSec'), stage.get('endSec')
        if a is not None and b is not None and start <= a and b <= end:
            row = deepcopy(stage); row.update(startSec=a-start, endSec=b-start); stages.append(row)
    if segment.get('stageNumbers') and [row['stageNumber'] for row in stages] != segment['stageNumbers']:
        raise ValueError('Segment stageNumbers disagree with complete authored stage intervals')
    local_direction['stagePlan'] = stages
    local_direction['timeline'] = []
    for event in specialist.get('timeline') or []:
        a, b = event['startSec'], event['endSec']
        if a < end and b > start:
            if a < start or b > end:
                raise ValueError('Segment boundary cuts through an authored channel event; direct the split explicitly')
            row = deepcopy(event); row.update(startSec=a-start, endSec=b-start); local_direction['timeline'].append(row)
    opening = (local_card['views'][0].get('startState') or (stages[0].get('initialOrCarriedState') if stages else '') or
        (directed[selected[0] - 1].get('landingImage') if selected[0] else shot.get('openingState')))
    if start and not opening:
        raise ValueError('Segment has no authored starting-state handoff')
    if opening:
        local_shot['openingState'] = opening
    local_direction['continuityFinish'] = local_direction['shotPlan'][-1]['landingImage']
    local_shot['endingState'] = local_direction['continuityFinish']
    local_card['handoff'] = local_direction['continuityFinish']
    local_authority.update(shot=local_shot, specialist=local_direction)
    receipt['projectionHash'] = digest(dict(shot=local_shot, specialist=local_direction))
    result.pop('watchPlan', None); result.pop('watchPlanBinding', None)
    return result
