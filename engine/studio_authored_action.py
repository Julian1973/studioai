"""DIRECT wording and timing, shared by WATCH formatters. No inference or writes."""
from copy import deepcopy
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def resolve_timing_choice(text, card, shot, start, end):
    """Resolve an authored alternative only from an unambiguous typed checkpoint.

    This is deterministic lowering, not permission to rewrite creative action.
    Keep source wording and the exact supporting event in the emitted evidence.
    """
    phrase = 'during or just after the line'
    if text.count(phrase) != 1:
        return text, None
    suffix = text.split(phrase, 1)[1]
    events = [e for e in card.get('stateChanges') or []
              if isinstance(e.get('atSec'), (int, float)) and start <= e['atSec'] < end]
    if len(events) != 1:
        return text, None
    event = events[0]
    # A named entity must bind the checkpoint to the action after the alternative.
    noun = re.split(r'[.:]', event.get('entityId') or '')[-1].removesuffix('s')
    if not noun or not re.search(r'\b' + re.escape(noun) + r's?\b', suffix, re.I):
        return text, None
    if not re.search(r'\bafter\b.*\bline\b.*\b(?:ends|completes)\b', event.get('cause') or '', re.I):
        return text, None
    ends = [line.get('endSec') for line in shot.get('dialogueLines') or []
            if isinstance(line.get('endSec'), (int, float)) and start < line['endSec'] <= end]
    if len(ends) != 1 or ends[0] >= event['atSec']:
        return text, None
    replacement = f"at {event['atSec']:g}s, after the line ends at {max(ends):g}s"
    return text.replace(phrase, replacement), dict(
        sourceText=text, sourceTextHash=digest(text), checkpoint=deepcopy(event),
        dialogueEndSec=max(ends), rule='explicit-after-line-checkpoint@1')


def actions(shot, source_unit=None):
    """Bind existing authored coverage; never use specialist or provider prose."""
    from studio_storyboard_prompt import view_timings
    card = shot.get('directorCard') or {}
    views = card.get('views') or []
    unit = shot.get('shotId', shot.get('id'))
    scene = shot.get('sceneId', shot.get('sceneNumber', shot.get('scene')))
    if scene is None:
        match = re.match(r'^S(\d+)\.', str(unit or ''))
        scene = match[1] if match else None
    scene = str(scene) if scene is not None else None
    if not views:
        raise ValueError(f'WATCH_AUTHORED_TIMED_ACTION_MISSING: unit={unit}; DIRECT must author timed views')
    try:
        intervals = view_timings(shot, len(views))
    except (ValueError, TypeError) as exc:
        raise ValueError(f'DIRECTOR_REVISION_REQUIRED: unit={unit}; {exc}') from exc
    if not all(intervals):
        raise ValueError(f'DIRECTOR_REVISION_REQUIRED: unit={unit}; explicit authored action timing required')
    if source_unit:
        original = {r['viewId']: r for r in actions(source_unit['shot'])}
        result = []
        offset = source_unit['globalStartSec']
        for view, (start, end) in zip(views, intervals):
            record = deepcopy(original[view['viewId']])
            original_text = (record.get('timingResolution') or {}).get('sourceText', record['text'])
            if (record['startSec'], record['endSec']) != (start + offset, end + offset) or view.get('action') not in (None, original_text):
                raise ValueError('WATCH_AUTHORED_ACTION_DRIFT: segment changed DIRECT action or timing')
            record.update(origin='/sourceUnit' + record['origin'], emissionStartSec=start, emissionEndSec=end)
            result.append(record)
        return result
    legacy = shot.get('storyboardInternalShotPlanApproved') or []
    result = []
    for view, (start, end) in zip(views, intervals):
        text = view.get('action')
        origin = '/shot/directorCard/views/' + str(len(result)) + '/action'
        # Historical approved storyAction is the existing upstream field copied
        # by the native Director handoff, not a new interpretation of primaryEvent.
        if text is None or text == '':
            candidates = [(i, row) for i, row in enumerate(legacy) if row.get('viewId') == view.get('viewId')]
            if len(candidates) == 1:
                index, old = candidates[0]
                text = old.get('storyAction')
                origin = f'/shot/storyboardInternalShotPlanApproved/{index}/storyAction'
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'WATCH_AUTHORED_TIMED_ACTION_MISSING: unit={unit}; view={view.get("viewId")}; revise DIRECT')
        if re.search(r'(?m)^(?:Shot \d+:|Action:|Performance:|\[)', text):
            raise ValueError(f'DIRECTOR_REVISION_REQUIRED: unit={unit}; action contains ambiguous provider section syntax')
        text, timing_resolution = resolve_timing_choice(text, card, shot, start, end)
        record = dict(sceneId=scene, generationUnitId=unit,
            viewId=view['viewId'], startSec=start, endSec=end, text=text,
            storyboardRevision=(shot.get('sourceStoryboard') or {}).get('sha256') or digest(legacy or views),
            directorCardRevision=digest(card), coverageRevision=digest([(v['viewId'], t) for v,t in zip(views,intervals)]),
            sourceBeatIds=shot.get('beatIds', shot.get('beatCodes', [])), sourceBeat=view.get('sourceBeat'))
        if timing_resolution:
            record['timingResolution'] = timing_resolution
        record['authoredActionHash'] = digest(record)
        record.update(origin=origin, emissionStartSec=start, emissionEndSec=end)
        result.append(record)
    return result


def slot(record, index):
    return f'__DIRECT_ACTION_{index}_{record["authoredActionHash"]}__'


def assemble(prompt, records):
    """Fill formatter slots once, after surrounding syntax has been formatted."""
    for i, record in enumerate(records):
        marker = slot(record, i)
        if prompt.count(marker) != 1:
            raise ValueError(f'WATCH_AUTHORED_ACTION_DRIFT: view={record["viewId"]}; formatter changed action slot')
        prompt = prompt.replace(marker, record['text'])
    return prompt


def proof(prompt, records, stage='final-provider-emission'):
    """Compare the actual timed ACTION bytes, including their emitted intervals."""
    if not records:
        raise ValueError('WATCH_AUTHORED_TIMED_ACTION_MISSING: no DIRECT action bindings')
    headings = list(re.finditer(r'(?m)^(?:Shot|Phase) (\d+): ([0-9.]+)[–—-]([0-9.]+)s$', prompt))
    if len(headings) != len(records):
        raise ValueError(f'WATCH_AUTHORED_ACTION_DRIFT: stage={stage}; timed view count changed')
    emitted = []
    for i, (heading, record) in enumerate(zip(headings, records)):
        block = prompt[heading.end():headings[i+1].start() if i+1 < len(headings) else len(prompt)]
        match = re.search(r'(?ms)^Action: (.*?)\n(?:Performance|Setting / light / materials|End state): ', block)
        actual = match[1] if match else None
        times = (float(heading[2]), float(heading[3]))
        if actual != record['text'] or times != (record['emissionStartSec'], record['emissionEndSec']):
            raise ValueError('WATCH_AUTHORED_ACTION_DRIFT: ' + json.dumps(dict(stage=stage,
                scene=record['sceneId'], unit=record['generationUnitId'], view=record['viewId'],
                expected=record['text'], emitted=actual, expectedHash=record['authoredActionHash'],
                emittedTextHash=digest(actual), emittedTiming=times), ensure_ascii=False))
        context = {k:v for k,v in record.items() if k not in ('origin','authoredActionHash','emissionStartSec','emissionEndSec')}
        context['text'] = actual
        emitted_hash = digest(context)
        if emitted_hash != record['authoredActionHash']:
            raise ValueError('WATCH_AUTHORED_ACTION_DRIFT: authored context hash changed')
        emitted.append(dict(**record, emittedText=actual, emittedActionHash=emitted_hash))
    expected = digest([r['authoredActionHash'] for r in records])
    actual = digest([r['emittedActionHash'] for r in emitted])
    return dict(status='PASS', authoredActionHash=expected, emittedActionHash=actual, views=emitted)
