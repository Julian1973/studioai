"""Camera law: camera height and size derived from locked character heights, never described.

Patrick Lin's doctrine, made data. A show opts in with laws/shot_grammar.json (declared in
its profile under laws.shotGrammar, or present at that path). Heights come from
canon/characters.json heightIn. The derivation is deterministic, reads no provider, writes
nothing, and is attached to the WATCH request authority so the compiler can put the
featured character's eye-line, in inches, into the provider's Camera line.

Nothing here is hashed into the Director Card: a card without camera data keeps its
revision. The derived block lives beside the shot in the request authority.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

VERSION = 'camera-law@1.0.0'
NON_CHARACTER_KINDS = {'establishing', 'world_texture', 'transition'}


def load(show_root=None, characters=None):
    """Return (grammar, characters) or (None, {}) when the show has not opted in."""
    try:
        if show_root is None:
            import paths as P
            show_root = Path(P.SHOW)
            characters = characters if characters is not None else json.load(open(P.CHARS))
        show_root = Path(show_root)
        grammar_path = None
        profile_path = show_root / 'profile.json'
        if profile_path.is_file():
            declared = (json.loads(profile_path.read_text()).get('laws') or {}).get('shotGrammar')
            if isinstance(declared, str):
                grammar_path = show_root / declared
            elif isinstance(declared, dict) and declared.get('file'):
                grammar_path = show_root / declared['file']
        if grammar_path is None:
            grammar_path = show_root / 'laws' / 'shot_grammar.json'
        if not grammar_path.is_file():
            return None, {}
        grammar = json.loads(grammar_path.read_text())
        if characters is None:
            chars_path = show_root / 'canon' / 'characters.json'
            characters = json.loads(chars_path.read_text()) if chars_path.is_file() else {}
        return grammar, characters or {}
    except Exception:
        return None, {}


def _height_in(name, characters):
    entry = characters.get(name) if isinstance(characters, dict) else None
    if not isinstance(entry, dict):
        # case-insensitive lookup; canon keys are display names
        for key, value in (characters or {}).items():
            if isinstance(value, dict) and str(key).casefold() == str(name).casefold():
                entry = value
                break
    if not isinstance(entry, dict):
        return None
    value = entry.get('heightIn')
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _species(name, entry_species, grammar):
    by_char = grammar.get('speciesByCharacter') or {}
    if name in by_char:
        return by_char[name]
    return entry_species or 'default'


def _character_name(entity):
    text = str(entity or '').strip()
    for prefix in ('character:', 'char:', 'character.'):
        if text.startswith(prefix):
            return text[len(prefix):]
    if ':' in text:  # prop:, part:, atmosphere: are not characters
        return None
    return text or None


def featured_subject(view, characters):
    """The character whose eye-line the camera measures from, from the card, never guessed.

    Order: viewpointOwner, then the first character in visibleEntities, then the first
    canon character named in framing/staging. None for world views."""
    cinema = view.get('cinematography') if isinstance(view.get('cinematography'), dict) else {}
    kind = str(cinema.get('kind') or '').lower().replace(' ', '_')
    if kind in NON_CHARACTER_KINDS:
        return None
    owner = view.get('viewpointOwner')
    if owner and _height_in(owner, characters) is not None:
        return owner
    for entity in view.get('visibleEntities') or []:
        name = _character_name(entity)
        if name and _height_in(name, characters) is not None:
            return name
    text = ' '.join(str(view.get(k) or '') for k in ('framing', 'staging', 'audienceNeed'))
    for name in characters or {}:
        if name.startswith('_') or not isinstance(characters.get(name), dict):
            continue
        if re.search(r'(?<!\w)' + re.escape(str(name)) + r'(?!\w)', text):
            return name
    return None


def derive(view, grammar, characters):
    """Camera facts for one view: subject, eye-line inches, height instruction, lens by size."""
    if not grammar:
        return None
    subject = featured_subject(view, characters)
    if subject is None:
        return None
    height = _height_in(subject, characters)
    if height is None:
        return None
    entry = characters.get(subject) or {}
    species = _species(subject, entry.get('species'), grammar)
    fraction = (grammar.get('eyeLineFraction') or {}).get(species) or (grammar.get('eyeLineFraction') or {}).get('default', 0.9)
    eye = round(height * float(fraction), 1)
    cinema = view.get('cinematography') if isinstance(view.get('cinematography'), dict) else {}
    attention = str(cinema.get('attention') or '').lower()
    by_attention = grammar.get('heightByAttention') or {}
    instruction = by_attention.get(attention) or by_attention.get('default', "at the featured character's eye-line")
    creature = height < float(grammar.get('creatureEyeLevelBelowIn', 24))
    if creature and attention not in ('scale', 'threat'):
        instruction = "at the subject's own eye-line; the world towers around them"
    size = None
    framing = str(view.get('framing') or '')
    for rung in grammar.get('sizeLadder') or []:
        code = rung.get('size')
        if code and re.search(r'(?<![A-Z])' + re.escape(code) + r'(?![A-Z])', framing):
            size = code
            break
    lens = (grammar.get('lensBySize') or {}).get(size) if size else None
    return dict(version=VERSION, subject=subject, subjectHeightIn=height, eyeLineIn=eye,
                species=species, cameraHeight=instruction, size=size, lens=lens)


def authority_for(shot, grammar=None, characters=None):
    """{viewId: derived} for every view on the shot's Director Card; {} when not opted in."""
    if grammar is None:
        grammar, characters = load()
    if not grammar:
        return {}
    result = {}
    for view in ((shot or {}).get('directorCard') or {}).get('views') or []:
        facts = derive(view, grammar, characters or {})
        if facts and view.get('viewId'):
            result[view['viewId']] = facts
    return result


def camera_height_line(facts):
    """The words the provider receives. Inches are the law; the instruction is the intent."""
    if not facts:
        return ''
    line = f"Camera height: {facts['cameraHeight']} — {facts['subject']}'s eye-line is {facts['eyeLineIn']:g} in above the ground"
    if facts.get('lens'):
        line += f"; {facts['lens']} lens for a {facts['size']}"
    return line + '.'
