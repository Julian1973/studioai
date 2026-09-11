"""Explicit project-authored object aliases; no identity inferred from prompt nouns."""
from __future__ import annotations
import re
from typing import Any

VERSION = 'studio-prompt-aliases-2.0'


def _data(shot):
    return shot if isinstance(shot, dict) else shot.model_dump() if hasattr(shot, 'model_dump') else {}


def protect_object_aliases(prompt: str, shot: Any = None) -> str:
    """Expand only explicit providerAliases. Never rewrite audio or spoken braces.

    Ambiguous aliases are an unresolved source issue, not a guess. Ordinary
    aliases remain reference metadata; they do not authorise changing prose.
    """
    from studio_tracked_objects import registry_for_shot
    mappings = _data(shot).get('providerAliases') or {}
    objects = {obj['id']: obj for obj in registry_for_shot(_data(shot))}
    for alias, object_id in mappings.items():
        if not alias or object_id not in objects:
            raise ValueError('Provider alias lacks a declared canonical object: ' + str(alias))
    if not mappings:
        return str(prompt or '')
    pattern = re.compile(r'(?<!\w)(' + '|'.join(re.escape(a) for a in sorted(mappings, key=len, reverse=True)) + r')(?!\w)')
    chunks = re.split(r'(\{[^{}]*\})', str(prompt or ''))
    heading = ''
    for i in range(0, len(chunks), 2):
        lines=[]
        for line in chunks[i].splitlines(keepends=True):
            match=re.match(r'^\[([^\n]+)\]',line)
            if match: heading=match[1]
            if heading not in ('Audio','Dialogue Authority','AUDIO AND EXCLUSIONS','CHANNEL TIMING') and not line.startswith('Spoken action:'):
                line=pattern.sub(lambda m: objects[mappings[m[0]]]['name'],line)
            lines.append(line)
        chunks[i]=''.join(lines)
    return ''.join(chunks)


def object_lifecycle_prompt_rules(shot: Any) -> dict[str, list[str]]:
    from studio_tracked_objects import registry_for_shot
    result={key:[] for key in ('preserve','exclude','acceptance','forbidden')}
    for obj in registry_for_shot(_data(shot)):
        result['preserve'].append(f"{obj['id']}: {obj['name']}. {obj['description']}")
        if obj['stateIn']:result['preserve'].append(f"Opening only — {obj['id']}: {obj['stateIn']}")
        for item in obj['prohibitedSubstitutions']:
            result['exclude'].append('No substitution: '+item+'.')
            result['forbidden'].append(item)
        result['acceptance'].append(f"Review {obj['id']} identity and visible opening state against bound references; unobserved properties remain unverified.")
    return result


# Compatibility entrypoints for existing callers; both use the same generic implementation.
protect_honeycomb_aliases = protect_object_aliases
honeycomb_lifecycle_prompt_rules = object_lifecycle_prompt_rules
