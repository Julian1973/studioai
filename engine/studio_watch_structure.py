"""Presentation of current WATCH direction; no new story, audio or reference facts.

The producer's production template is compacted for delivery: camera, acting and
landing remain with each timed view. Audio blocks retain their original bytes.
"""
import re

VERSION = 'watch-production-structure@1.0.0'
ALIASES = {
    'Audience Purpose': 'PURPOSE',
    'One-Sentence Summary': 'STORY BEAT',
    'Multimodal Reference Layer': 'REFERENCE AUTHORITY',
    'Shot Sequence': 'TIMED ACTION',
    'Stage Sequence': 'TIMED ACTION',
    'Timed Action Phases — One Continuous Render': 'TIMED ACTION',
    'Camera and Shot Plan': 'TIMED ACTION',
    'Continuity': 'MUST PRESERVE',
}


def apply(prompt, shot, direction):
    # Legacy freeform/edit/extension prompts need their own native structure.
    # Never guess a timed plan or reinterpret a provider edit request here.
    if not re.search(r'^\[(?:Shot Sequence|Stage Sequence|Timed Action Phases — One Continuous Render|Camera and Shot Plan|TIMED ACTION)\]$', prompt, re.M):
        return prompt
    if "[Audience Purpose]" not in prompt and "[PURPOSE]" not in prompt:
        prompt = prompt.replace("[One-Sentence Summary]\n", "[PURPOSE]\n")
    for old, new in ALIASES.items():
        prompt = prompt.replace(f'[{old}]\n', f'[{new}]\n')
    stages = direction.get('stagePlan') or []
    additions = []
    def add(heading, value):
        if isinstance(value, str) and value.strip() and f'[{heading}]' not in prompt:
            additions.append(f'[{heading}]\n' + value.strip())
    # Use authored start/end states. Do not infer from an image or reuse a later
    # landing as the initial state. The per-view actions remain untouched.
    add('OPENING STATE', (stages[0].get('initialOrCarriedState') if stages else None)
        or shot.get('openingState'))
    add('CAUSALITY', direction.get('physicalCauseAndEffect'))
    add('CONTINUITY OUT', direction.get('continuityFinish'))
    if additions:
        prompt += '\n\n' + '\n\n'.join(additions)
    return prompt
