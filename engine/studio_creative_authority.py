"""Scoped creative instruction resolution; no approvals, generations or canon writes.

Only explicitly structured instructions can be resolved semantically. Legacy prose is
labelled unclassified instead of pretending a keyword scan proved its authority.
"""
from pydantic import BaseModel, Field
from typing import Literal

class Instruction(BaseModel):
    id: str
    text: str
    source: str
    kind: Literal['hard_truth', 'creative_direction', 'contextual_guardrail',
                  'default_behaviour', 'historic_residue', 'provider_syntax']
    scope: dict = Field(default_factory=dict)
    decisionKey: str | None = None
    value: str | None = None
    required: bool = True

PRIORITY = {'hard_truth': 0, 'creative_direction': 1, 'contextual_guardrail': 2,
            'provider_syntax': 2, 'default_behaviour': 3, 'historic_residue': 4}


def applies(scope, context):
    # Missing context is not evidence that an instruction is irrelevant. Preserve its
    # explicit scope in the emitted instruction for provider interpretation.
    return all(key not in context or context[key] == value for key, value in scope.items())


def resolve(instructions, context):
    rows, selected, conflicts = [], [], []
    for raw in instructions:
        item = Instruction.model_validate(raw).model_dump()
        status = ('removed-residue' if item['kind'] == 'historic_residue' else
                  'out-of-scope' if not applies(item['scope'], context) else 'pending')
        rows.append({**item, 'resolution': status})
    for item in sorted((r for r in rows if r['resolution'] == 'pending'), key=lambda r: PRIORITY[r['kind']]):
        peers = [p for p in selected if item['decisionKey'] and p['decisionKey'] == item['decisionKey'] and
                 all(k not in p['scope'] or p['scope'][k] == v for k,v in item['scope'].items())]
        same = next((p for p in selected if p['text'] == item['text']), None)
        if same or any(p['value'] == item['value'] for p in peers):
            item['resolution'] = 'duplicate'
        elif peers and PRIORITY[peers[0]['kind']] == PRIORITY[item['kind']]:
            item['resolution'] = 'conflict'
            conflicts.append({'ids': [peers[0]['id'], item['id']],
                              'reason': 'Current authorities disagree on ' + item['decisionKey']})
        elif peers and peers[0]['kind'] == 'hard_truth' and item['kind'] == 'creative_direction':
            item['resolution'] = 'conflict'
            conflicts.append({'ids': [peers[0]['id'], item['id']],
                              'reason': 'Creative direction conflicts with approved ' + item['decisionKey']})
        elif peers:
            item['resolution'] = 'superseded'
        else:
            item['resolution'] = 'emitted'
            selected.append(item)
    return {'instructions': rows, 'conflicts': conflicts, 'ready': not conflicts,
            'groups': {label: [r['id'] for r in selected if r['kind'] in kinds]
                       for label, kinds in {'LOCKED': {'hard_truth','provider_syntax'},
                                            'DIRECTED': {'creative_direction','contextual_guardrail'},
                                            'OPEN': {'default_behaviour'}}.items()}}


def compile_instructions(prompt, shot, stage):
    context = {**shot.get('instructionContext', {}), 'stage': stage,
               'shotId': shot.get('shotId', shot.get('id'))}
    result = resolve((shot.get('directorCard') or {}).get('instructions', []), context)
    if result['conflicts']:
        raise ValueError('; '.join(r['reason'] for r in result['conflicts']))
    additions = [(('Scope ' + str(r['scope']) + ': ') if r['scope'] else '') + r['text']
                 for r in result['instructions'] if r['resolution'] == 'emitted' and r['text'] not in prompt]
    if additions:
        prompt += '\n\n[SCOPED CREATIVE DIRECTION]\n' + '\n'.join(additions)
    return prompt


def listener_scope(prompt):
    """Scope known compiler-owned defaults; this does not rewrite spoken words."""
    import re
    # Keep quoted/braced dialogue intact. Only rewrite known house-policy clauses.
    pieces = re.split(r'(\{[^{}]*\})', prompt)
    for index in range(0, len(pieces), 2):
        pieces[index] = pieces[index].replace(
            'Listeners remain silent and closed-mouth unless they are the named speaker for that exact line.',
            'Visible listeners do not articulate another speaker’s words; preserve their directed attention and response.')
        pieces[index] = pieces[index].replace(
            'Hold on the non-acting witness;',
            'Preserve the witness’s directed attention and response;')
    return ''.join(pieces)
