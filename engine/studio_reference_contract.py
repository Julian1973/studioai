"""Shared, deterministic reference coverage; no model calls or creative defaults."""
VERSION = 's1sh1-workflow-1.0.0'


def required_cast(shot):
    # An explicitly empty opening cast is valid (an environment-only opening).
    if 'openingCharactersInFrame' in shot:
        values = shot['openingCharactersInFrame']
    else:
        values = shot.get('charactersInFrame', shot.get('characters', []))
    return list(dict.fromkeys(str(v).strip() for v in values or [] if str(v).strip()))


def complete_identity_slots(slots, cast):
    result = dict(slots or {})
    existing = {str(v).casefold() for v in result.values()}
    numbers = [int(k[2:]) for k in result if k.startswith('@图') and k[2:].isdigit()]
    index = max(numbers, default=0) + 1
    for name in cast:
        if name.casefold() not in existing:
            result[f'@图{index}'] = name
            existing.add(name.casefold())
            index += 1
    return result


def receipt(references):
    """Record roles and identities for review, without claiming visual fidelity."""
    return {'workflowVersion': VERSION, 'visualFidelity': 'requires-human-review',
            'references': [{k: item[k] for k in (
                'slot', 'role', 'name', 'path', 'hash', 'version', 'approvalStatus',
                'authority', 'requiredState', 'depictedState')
                if k in item} for item in references]}
