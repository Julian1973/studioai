"""Provider storyboard presentation from existing direction, never a new story plan.

Times come from authored coverage. Identity bindings come from the ordered reference
contract. Neither is guessed from a target duration or a model's reference example.
"""
import math
import re

VERSION = 'storyboard-emission-1.0'


def validate_view_bindings(shot, views):
    expected = (shot.get('directorCard') or {}).get('views') or []
    if not expected:
        return
    ids = [v.get('viewId') for v in expected]
    if [v.get('sourceViewId') for v in views] != ids:
        raise ValueError('Animation coverage must preserve each current sourceViewId in order.')
    for view in views:
        for field in ('framingLensAndCamera', 'causalAction', 'observablePerformance',
                      'compositionLightAndMaterials', 'landingImage'):
            value = str(view.get(field) or '').strip().rstrip('.').casefold()
            if value in ('', 'no extra view', 'no additional view', 'same as above', 'n/a', 'tbd', 'none'):
                raise ValueError(f"Animation view {view.get('sourceViewId')} has placeholder {field}.")


def view_timings(shot, count):
    """Return explicit, validated view intervals; un-timed legacy plans stay un-timed."""
    views = (shot.get('directorCard') or {}).get('views') or []
    if not views:
        return [None] * count
    from studio_director_handoff import errors
    faults = errors(shot)
    if faults:
        raise ValueError('; '.join(faults))
    if len(views) != count:
        raise ValueError('Storyboard emission needs the current approved coverage view count.')
    rows = []
    for view in views:
        match = re.fullmatch(
            r'\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*[-–—]\s*'
            r'(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*',
            str(view.get('timing') or ''))
        if not match:
            # Do not invent equal duration views or convert ordinal IDs into seconds.
            rows.append(None)
            continue
        start, end = map(float, match.groups())
        at = view.get('atSec', start)
        duration = float(shot.get('durationSec', shot.get('duration')))
        if (not all(math.isfinite(v) for v in (start, end, duration)) or
                not 0 <= start < end <= duration or at != start):
            raise ValueError('Storyboard interval disagrees with the current shot timing.')
        rows.append((start, end))
    if all(row is not None for row in rows) and rows:
        if (rows[0][0] != 0 or rows[-1][1] != duration or
                any(a[1] != b[0] for a, b in zip(rows, rows[1:]))):
            raise ValueError('Storyboard intervals must cover the shot without gaps or overlaps.')
    return rows


def subjects_for_view(bindings, view, spoken_names=(), *, visible_entities=None):
    """Link named subjects locally without rewriting a single spoken word.

    Declared coverage visibility takes precedence over prose mentions, including
    negative reminders and offscreen speech. Legacy unknown visibility retains
    name-based selection. Neither route guesses about pixels.
    """
    authored = '\n'.join(str(view.get(k) or '') for k in (
        'framingLensAndCamera', 'causalAction', 'observablePerformance',
        'compositionLightAndMaterials', 'landingImage'))
    names = {str(name).casefold() for name in spoken_names}
    active = []
    for tag, name in bindings:
        if not name or name == 'character identity':
            continue
        from studio_character_roles import character_id
        visible = ({character_id(entity).removeprefix('character:').casefold()
                    for entity in visible_entities} if visible_entities is not None else None)
        if (name.casefold() in visible if visible is not None else
                name.casefold() in names or
                re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', authored, re.I)):
            active.append(f'{name} from {tag}')
    return 'Subjects: ' + '; '.join(dict.fromkeys(active)) + '.' if active else ''


def labelled_view(number, kind, timing, parts):
    header = f'{kind} {number}:'
    if timing:
        header += f' {timing[0]:g}–{timing[1]:g}s'
    return header + '\n' + '\n'.join(part for part in parts if part)
