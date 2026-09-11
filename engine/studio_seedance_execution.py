"""Compact native Seedance shooting scripts, preserving internal review evidence.

No model, file mutation or generation. This is a structural compiler, not semantic
recognition. It never truncates a beat to meet a word budget or guesses visibility.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

VERSION = 'seedance-execution-2.0.0'
POLICY_PATH = Path(__file__).parent / 'config' / 'seedance_prompt.json'
AUDIO_HEADINGS = ('Dialogue Authority', 'Audio', 'AUDIO AND EXCLUSIONS')
INTERNAL_HEADINGS = {
    'CURRENT DYNAMIC STATE', 'REFERENCE STATE AUTHORITY', 'ACTION OWNERSHIP',
    'ATTRIBUTE OWNERSHIP', 'ENVIRONMENT CONTRACT', 'Opening Motion Bridge',
    'CHANNEL TIMING', 'EDITORIAL HANDOFF', 'Camera Consciousness',
    'CHARACTER ROLE INTEGRITY', 'Locked Character Turnarounds', 'Global Supplement',
    'Human Review Correction',
}
STALE_PROVIDER_HEADINGS = {'Human Review Correction', 'Crystal Energy Law'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sections(prompt):
    matches = list(re.finditer(r'^\[([^\n]+)\][ \t]*\n', prompt, re.M))
    return [(m[1], prompt[m.start():matches[i + 1].start() if i + 1 < len(matches) else len(prompt)].rstrip())
            for i, m in enumerate(matches)]



def _remove_sections(prompt, headings):
    blocked = set(headings)
    matches = list(re.finditer(r'^\[([^\n]+)\][ \t]*\n', prompt, re.M))
    if not matches:
        return prompt, []
    out = []
    cursor = 0
    removed = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prompt)
        heading = match[1]
        if heading in blocked:
            out.append(prompt[cursor:match.start()])
            cursor = end
            removed.append(heading)
    out.append(prompt[cursor:])
    clean = ''.join(out).strip()
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean, removed

def policy():
    values = json.loads(POLICY_PATH.read_text())
    lo, hi, warn, hard = [values[k] for k in ('preferredMinWords', 'preferredMaxWords', 'warnWords', 'maxWords')]
    if not all(isinstance(n, int) and not isinstance(n, bool) for n in (lo, hi, warn, hard)) or not 0 < lo <= hi <= warn <= hard:
        raise ValueError('Invalid Seedance prompt word-budget configuration')
    return values


def budget(prompt, authorities, rules=None):
    rules = rules or policy()
    count = len(prompt.split())
    shot = authorities.get('shot', {})
    exception = next((a for a in authorities.get('promptBudgetAuthorisations', [])
        if isinstance(a, dict) and a.get('authorisedBy') and a.get('id') and
        a.get('shotId') == shot.get('shotId', shot.get('id')) and
        a.get('sourceHash') == digest(shot) and a.get('promptHash') == digest(prompt) and
        isinstance(a.get('maxWords'), int) and not isinstance(a['maxWords'], bool) and a['maxWords'] >= count), None)
    blocked = count > rules['maxWords'] and not exception
    return dict(wordCount=count, policy=deepcopy(rules),
                status='BLOCKED' if blocked else 'WARN' if count > rules['warnWords'] else 'PASS',
                withinPreferred=count <= rules['preferredMaxWords'],
                exceptionId=exception['id'] if exception else None,
                reason=f'{count} words exceeds {rules["maxWords"]}; shorten visual repetition without removing protected content.' if blocked else None)


def supported(snapshot):
    """Typed source availability; never inspect provider prose to infer a plan."""
    shot = (snapshot.get('authorities') or {}).get('shot') or {}
    return bool((shot.get('directorCard') or {}).get('views'))



def _has_audio_asset(snapshot):
    audio = snapshot.get('audio')
    if not audio:
        return False
    if isinstance(audio, dict):
        return any(bool(audio.get(key)) for key in ('path', 'hash', 'sha256', 'url', 'assetTag'))
    if isinstance(audio, list):
        return bool(audio)
    return True


def _no_dialogue_policy(snapshot, prompt):
    shot = snapshot.get('authorities', {}).get('shot', {})
    if shot.get('dialogueLines'):
        return False
    if _has_audio_asset(snapshot):
        return False
    return bool(re.search(r'\b(?:no\s+(?:spoken\s+)?dialogue|no\s+@Audio1|no\s+Audio1|required\s+no\s+voice)\b', prompt, re.I))


def _sentence_has_any(text, words):
    return any(re.search(pattern, text, re.I) for pattern in words)


def _provider_consistency_errors(prompt, snapshot):
    """Only syntax/binding checks here; story interpretation belongs to review."""
    errors = []
    for heading in ('Human Review Correction',):
        if heading in dict(sections(prompt)):
            errors.append('Unresolved appended correction: update the approved plan and recompile')
    tags = set(re.findall(r'@(?:图|Image|image)(\d+)', prompt))
    declared = {re.sub(r'^@(?:图|Image|image)', '', ref.get('slot') or f'@图{i}') for i, ref in enumerate(snapshot.get('references', []), 1)}
    if tags - declared:
        errors.append('Reference tags missing from actual manifest: ' + ', '.join(sorted(tags - declared)))
    if re.search(r'@Audio1\b', prompt) and not _has_audio_asset(snapshot):
        # An explicit absence marker is not an instruction to use audio.
        if not _no_dialogue_policy(snapshot, prompt):
            errors.append('Audio1 is referenced without a bound audio asset')
    return errors

def _passive_offscreen(sentence, absent, visible):
    """Only omit a separate passive/offscreen reminder; never remove a joint action."""
    mentions = lambda name: re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', sentence, re.I)
    return (any(mentions(n) for n in absent) and not any(mentions(n) for n in visible) and
            bool(re.search(r'\b(?:outside the chase lane|offscreen|off-screen|out of frame|stays? on (?:her|his|their) (?:original |far-bank )*leaf|remain outside)\b', sentence, re.I)))


def _reference_lines(snapshot, roles):
    identities = {row['identity']['tag']: row for row in roles.get('characters', [])}
    lines = []
    for i, ref in enumerate(snapshot.get('references', []), 1):
        tag = ref.get('slot') or f'@图{i}'
        role = str(ref.get('role') or ref.get('name') or '')
        low = role.lower()
        if tag in identities:
            row = identities[tag]
            traits = row.get('traits') or {}
            features = traits.get('distinguishingFeatures') or [str(v) for k, v in traits.items() if k != 'mustNotBorrow']
            if isinstance(features, str):
                features = [features]
            description = '; '.join(dict.fromkeys(features))
            lines.append(f'{tag}: {row["name"]} identity/design only' + (f' — {description}' if description else '') + '; one character, not sheet layout.')
            exclusions = traits.get('mustNotBorrow') or []
            if isinstance(exclusions, str):
                exclusions = [exclusions]
            if exclusions:
                lines.append(f'{row["name"]} {tag} must not borrow: ' + '; '.join(dict.fromkeys(exclusions)) + '.')
        elif 'opening' in low or low == 'opening_frame':
            lines.append(f'{tag} is the first frame. Subsequent views follow the sequence.')
        elif 'previous' in low or 'continuity' in low:
            lines.append(f'{tag}: incoming continuity evidence only. Carry explicitly surviving state at 0s; never override opening camera, canonical identity, character roles or later prop ownership.')
        elif any(x in low for x in ('plate', 'location', 'geography')):
            lines.append(f'{tag}: fixed geography/light only; never restore earlier character or movable-prop state.')
        elif low.startswith('vision:'):
            lines.append(f'{tag}: exact pictured vision content on the water surface only. Preserve the depicted subjects and arrangement inside the reflection; do not place them physically at the pool or transfer their setting/weather to it. Appearance timing and ripple distortion follow the sequence.')
        elif 'prop' in low:
            lines.append(f'{tag}: {role} design/materials/scale only; condition and ownership follow the sequence.')
        else:
            # Unknown scopes are kept verbatim for review, not silently reclassified.
            lines.append(f'{tag}: {role}; {ref.get("controls") or "use only its declared reference scope"}.')
    return lines


def compile_prompt(snapshot, roles):
    """The sole final WATCH emitter, driven directly by the bound typed plan."""
    from studio_watch_plan import prepare_plan, digest as plan_digest
    source = snapshot['prompt']
    if 'Human Review Correction' in dict(sections(source)):
        raise ValueError('Unresolved appended correction: update the approved plan and recompile')
    prepared = prepare_plan(snapshot)
    plan = prepared['watchPlan']
    authority = prepared['authorities']
    shot = authority.get('shot') or {}
    evidence = dict(version=VERSION, applied=True, format='typed-plan-only',
        sourcePrompt=source, sourceHash=digest(authority), planHash=plan_digest(plan),
        requestBindingHash=plan['requestBindingHash'], compatibility=plan['compatibility'],
        legacyVisualProse='ignored; typed source owns all visual emission',
        removedSections=[heading for heading, _ in sections(source) if heading in INTERNAL_HEADINGS],
        origins=deepcopy(plan['origins']), views=[], omittedPassiveReminders=[])
    names = {r['characterId']: r['name'] for r in roles.get('characters', [])}
    tags = {r['characterId']: r['identity']['tag'] for r in roles.get('characters', [])}
    output_views = []
    from studio_character_roles import character_id, bind_visual_names
    # Director Cards use both display names and stable entity IDs (e.g. Aida,
    # char:aida). Resolve only exact known aliases, independent of casing, back
    # to the manifest's canonical ID; props and unknown entities are not cast.
    character_aliases = {}
    for cid, name in names.items():
        for alias in (cid, name):
            character_aliases.setdefault(character_id(alias).casefold(), set()).add(cid)
    for i, view in enumerate(plan['views']):
        declared = view['visibleEntities']
        visible = None if declared is None else set()
        for entity in declared or []:
            matches = character_aliases.get(character_id(entity).casefold(), set())
            if len(matches) > 1:
                raise ValueError(f'Ambiguous registered visible character alias: {entity}')
            visible.update(matches)
        active = [cid for cid in names if visible is not None and cid in visible]
        absent = [name for cid, name in names.items() if visible is not None and cid not in visible]
        if declared is None:
            # Unknown is not a visible-cast declaration. Preserve authored action
            # (including an offscreen cause) without inferring on-screen performers.
            cast = ''
        else:
            cast = ('Visible cast: ' + '; '.join(f'{names[cid]} {tags[cid]}' for cid in active) + ' only.'
                    if active else 'Visible cast: no characters.')
        def visual(label, value):
            if not value:
                return ''
            kept = []
            for part in re.split(r'(?<=[.!?])\s+(?=[A-Z])', value):
                if _passive_offscreen(part, absent, [names[cid] for cid in active]):
                    evidence['omittedPassiveReminders'].append(dict(viewId=view['viewId'], text=part))
                else:
                    kept.append(part)
            return label + ': ' + ' '.join(kept) if kept else ''
        transition = ('Cut to this view.' if view['entry'] == 'cut' and i else
                      'Continue within the current camera shot; make the directed camera move.' if view['entry'] == 'move' else
                      'Continue within the current camera shot; hold this motivated view.' if view['entry'] == 'hold' else '')
        parts = [f"Shot {i+1}: {view['startSec']:g}–{view['endSec']:g}s",
            'Camera: ' + view['camera'], transition, cast,
            visual('Purpose', view['purpose']), visual('Starting state', view['opening']),
            visual('Action', view['action']), visual('Performance', view['performance']),
            visual('Setting / light / materials', view['setting']), visual('End state', view['landing']),
            *view['dialogue'], *view['holds'],
            'Keep identities and actions distinct.' if len(active) > 1 else '']
        output_views.append('\n'.join(part for part in parts if part))
        evidence['views'].append(dict(viewId=view['viewId'], visibleEntities=declared, cast=cast))
    continuity = ('Preserve the approved look, fixed set geography, interaction axis and story time across cuts. '
        'Character and movable-prop positions follow the directed actions and end states.')
    pieces = ['[PURPOSE]\n' + plan['purpose'], '[TIMED ACTION]\n' + '\n\n'.join(output_views),
        '[REFERENCE AUTHORITY]\n' + '\n'.join(_reference_lines(prepared, roles)),
        '[OPENING STATE]\n' + plan['opening'] if plan['opening'] else '',
        '[CAUSALITY]\n' + plan['causality'] if plan['causality'] else '',
        '[CONTINUITY OUT]\n' + plan['landing'] if plan['landing'] else '',
        '[MUST PRESERVE]\n' + '\n'.join([continuity, *plan['geography'], *plan['invariants']]),
        *plan['audioBlocks'],
        '[Dialogue timing]\nMatch each exact spoken action to @Audio1:\n' + '\n'.join(plan['dialogueTiming']) if plan['dialogueTiming'] else '',
        '[Sound]\n' + '\n'.join(plan['sound']) if plan['sound'] else '']
    from studio_prompt_aliases import protect_honeycomb_aliases
    from studio_tracked_objects import apply_provider_clauses
    from studio_prompt_order import purpose_first
    prompt = bind_visual_names('\n\n'.join(piece for piece in pieces if piece), roles)
    prompt = purpose_first(apply_provider_clauses(protect_honeycomb_aliases(prompt, shot), shot))
    for block in plan['audioBlocks']:
        if block not in prompt:
            raise ValueError('Compiler changed the immutable Audio1 provider block')
    spoken = [line for view in plan['views'] for line in view['dialogue']] + [line for block in plan['audioBlocks'] for line in re.findall(r'^Spoken action:.*$', block, re.M)]
    if re.findall(r'^Spoken action:.*$', prompt, re.M) != spoken:
        raise ValueError('Compiler changed typed exact spoken-action placement')
    from collections import Counter
    if Counter(re.findall(r'\{([^{}]+)\}', prompt)) != Counter(cue['text'] for cue in plan['dialogueOccurrences']):
        raise ValueError('Compiler changed exact dialogue occurrence counts')
    evidence.update(audioBlocks={heading: digest(block) for heading, block in sections(prompt) if heading in AUDIO_HEADINGS},
        audioPolicy='no-dialogue/no-Audio1' if _no_dialogue_policy(prepared, prompt) else 'preserve-audio-blocks',
        promptHash=digest(prompt), budget=budget(prompt, authority))
    return prompt, evidence


def final_check(snapshot, evidence):
    result = budget(snapshot['prompt'], snapshot.get('authorities', {}))
    errors = [result['reason']] if result['status'] == 'BLOCKED' else []
    if not evidence.get('applied') or evidence.get('version') != VERSION:
        errors.append('WATCH request has no current typed-plan compiler evidence; legacy prose cannot bypass compilation')
    else:
        if evidence.get('sourceHash') != digest(snapshot.get('authorities')):
            errors.append('WATCH compiler evidence belongs to different source direction')
        blocks = dict(sections(snapshot['prompt']))
        if INTERNAL_HEADINGS.intersection(blocks):
            errors.append('Internal control records were reintroduced into the provider prompt')
        if any(heading not in blocks or digest(blocks[heading]) != expected
               for heading, expected in evidence.get('audioBlocks', {}).items()):
            errors.append('Protected Audio1 provider text changed during review')
        if evidence.get('promptHash') != digest(snapshot['prompt']):
            errors.append('Provider prompt differs from its deterministic compiler output')
        try:
            from studio_watch_plan import prepare_plan, digest as plan_digest
            prepared = prepare_plan(snapshot)
            if plan_digest(prepared['watchPlan']) != evidence.get('planHash'):
                errors.append('Provider prompt belongs to a different typed plan revision')
        except ValueError as exc:
            errors.append(str(exc))
    errors.extend(_provider_consistency_errors(snapshot['prompt'], snapshot))
    return result, errors


def recompile_reviewed_emission(snapshot, corrections):
    """Compatibility entrypoint: typed source corrections, never prompt replacements."""
    from studio_watch_plan import correct_plan
    from studio_character_roles import audit
    revised, receipt = correct_plan(snapshot, corrections)
    revised['prompt'], evidence = compile_prompt(revised, audit(revised))
    return revised, {**receipt, 'compilation': evidence}
