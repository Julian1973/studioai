"""Shared reference-state checks. Declared evidence is not visual recognition."""
import re

VERSION = 'prompt-authority-1.0.0'


def canonical_tag(value):
    match = re.fullmatch(r'@(Image|图|Figure|Audio|Video)\s*(\d+)', str(value).strip(), re.I)
    if not match:
        return str(value).strip().casefold()
    kind = match[1].casefold()
    return ('image' if kind in {'image', '图', 'figure'} else kind) + ':' + str(int(match[2]))


def reference_state_report(references):
    """Compare explicitly supplied state observations, never infer pixels from prose.

    requiredState is a shot requirement; depictedState is source-bound reviewed metadata.
    Absent observations remain unverified, not an invented pass or a new approval gate.
    """
    conflicts, unverified = [], []
    for ref in references:
        tag = ref.get('tag', ref.get('slot', ref.get('assetTag', ref.get('name', 'reference'))))
        required = ref.get('requiredState') or {}
        observed = ref.get('depictedState') or {}
        for field, expected in required.items():
            actual = observed.get(field)
            if actual is None or actual == '':
                unverified.append({'tag': tag, 'field': field, 'required': expected})
            elif str(actual).strip().casefold() != str(expected).strip().casefold():
                conflicts.append({'tag': tag, 'field': field, 'required': expected, 'depicted': actual,
                                  'action': 'Replace or correct the conflicting reference, then recompile.'})
    return {'version': VERSION, 'ok': not conflicts, 'conflicts': conflicts,
            'unverified': unverified, 'visualFidelity': 'not-assessed-by-this-check'}
