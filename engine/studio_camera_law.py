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

VERSION = 'camera-law@1.1.0'
NON_CHARACTER_KINDS = {'establishing', 'world_texture', 'transition'}


def load(show_root=None, characters=None):
    """Return (grammar, characters), or (None, {}) when the show has not opted in.

    Opting out is a missing grammar file. A grammar or canon file that exists but cannot be
    read is an error, raised loudly: the camera law must never vanish from a prompt in
    silence."""
    if show_root is None:
        import paths as P
        show_root = Path(P.SHOW)
        if characters is None:
            characters = json.load(open(P.CHARS))
    show_root = Path(show_root)
    grammar_path = None
    profile_path = show_root / 'profile.json'
    if profile_path.is_file():
        try:
            declared = (json.loads(profile_path.read_text()).get('laws') or {}).get('shotGrammar')
        except ValueError as error:
            raise ValueError(f'show profile is not valid JSON: {profile_path}: {error}') from error
        if isinstance(declared, str):
            grammar_path = show_root / declared
        elif isinstance(declared, dict) and declared.get('file'):
            grammar_path = show_root / declared['file']
    if grammar_path is None:
        grammar_path = show_root / 'laws' / 'shot_grammar.json'
    if not grammar_path.is_file():
        return None, {}
    try:
        grammar = json.loads(grammar_path.read_text())
    except ValueError as error:
        raise ValueError(f'shot grammar is not valid JSON: {grammar_path}: {error}') from error
    if not isinstance(grammar, dict):
        raise ValueError(f'shot grammar must be a JSON object: {grammar_path}')
    if characters is None:
        chars_path = show_root / 'canon' / 'characters.json'
        try:
            characters = json.loads(chars_path.read_text()) if chars_path.is_file() else {}
        except ValueError as error:
            raise ValueError(f'canon characters is not valid JSON: {chars_path}: {error}') from error
    return grammar, characters or {}


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
    facts = dict(version=VERSION, subject=subject, subjectHeightIn=height, eyeLineIn=eye,
                 species=species, cameraHeight=instruction, size=size, lens=lens)
    by_character = grammar.get('cameraByCharacter') or {}
    rule = by_character.get(subject)
    if isinstance(rule, str) and rule.strip():
        facts['characterGrammar'] = rule.strip()
    return facts


def world_camera(grammar):
    """The show's camera language and light baseline: stated once per prompt, never per view.

    Both are the studio's cinematographer craft (camera language of the world, motivated
    light) kept as show data so DIRECT and the provider read the same words."""
    if not grammar:
        return None
    language = str(grammar.get('cameraLanguage') or '').strip()
    light = str(grammar.get('lightBaseline') or '').strip()
    if not language and not light:
        return None
    return dict(version=VERSION, cameraLanguage=language, lightBaseline=light)


def world_camera_lines(world):
    """Lines for the provider's MUST PRESERVE block."""
    if not world:
        return []
    lines = []
    if world.get('cameraLanguage'):
        lines.append('Camera language of this world: ' + world['cameraLanguage'])
    if world.get('lightBaseline'):
        lines.append('Light of this world: ' + world['lightBaseline'])
    return lines


def authority_for(shot, grammar=None, characters=None):
    """{viewId: derived, '_world': world camera} for the shot's Director Card; {} when not opted in."""
    if grammar is None:
        grammar, characters = load()
    if not grammar:
        return {}
    result = {}
    for view in ((shot or {}).get('directorCard') or {}).get('views') or []:
        facts = derive(view, grammar, characters or {})
        if facts and view.get('viewId'):
            result[view['viewId']] = facts
    world = world_camera(grammar)
    if world:
        result['_world'] = world
    return result


def camera_height_line(facts):
    """The words the provider receives. Inches are the law; the instruction is the intent;
    a character's own camera grammar (from the show's data) rides on the same line."""
    if not facts:
        return ''
    line = f"Camera height: {facts['cameraHeight']} — {facts['subject']}'s eye-line is {facts['eyeLineIn']:g} in above the ground"
    if facts.get('lens'):
        line += f"; {facts['lens']} lens for a {facts['size']}"
    line += '.'
    if facts.get('characterGrammar'):
        line += f" {facts['subject']}'s camera: {facts['characterGrammar']}."
    return line
