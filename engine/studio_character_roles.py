"""Manifest-bound character roles, shared by native and project Prompt Director.

This checks explicit records and literal identity/ownership claims. It does not
recognise faces in pixels, infer actions from arbitrary prose, or certify a take.
No provider, approvals, or source-media writes occur here.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

VERSION = 'character-role-integrity-1.1'
TAG = r'@(?:图|Image)\d+'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode()).hexdigest()


def character_id(value):
    value = str(value or '').strip()
    if value.startswith('char:'):
        value = 'character:' + value[len('char:'):]
    if value.startswith('character.'):
        value = 'character:' + value[len('character.'):]
    return value if value.startswith('character:') else 'character:' + value


def _name(value):
    return str(value).removeprefix('character:')


def _dialogue(shot):
    return [dict(speaker=character_id(line.get('speaker', '')),
                 text=line.get('exactText', line.get('text', '')),
                 startSec=line.get('startSec'), endSec=line.get('endSec'),
                 occurrenceId=line.get('dialogueOccurrenceId'))
            for line in shot.get('dialogueLines', shot.get('dialogue', [])) or []]


def resolve(snapshot):
    """Resolve current source roles against the actual, ordered image manifest."""
    shot = snapshot.get('authorities', {}).get('shot', {})
    card = shot.get('directorCard') or {}
    cast = list(dict.fromkeys(character_id(n) for n in
                shot.get('charactersInFrame', shot.get('characters', [])) or []))
    authored = {character_id(r['character']): r for r in card.get('characterRoles', [])}
    for cid in authored:
        if cid not in cast:
            cast.append(cid)
    errors, warnings, rows = [], [], []

    def fault(code, expected, actual):
        errors.append(dict(code=code, expected=deepcopy(expected), actual=deepcopy(actual)))

    references = snapshot.get('references') or []
    edit_scope = snapshot.get('authorities', {}).get('editScope') or {}
    source_preservation = None
    # A bounded edit uploads its approved source video, not fresh cast images.
    # Keep its existing source-preservation review usable, but explicitly do NOT
    # classify it as a qualified new character-identity replacement route.
    if (edit_scope.get('outsideWindow') == 'preserve approved source' and
            edit_scope.get('audio') == 'immutable' and len(references) == 1 and
            str(references[0].get('role', '')).startswith('approved source video')):
        ref = references[0]
        expected = edit_scope.get('sourceSha256')
        path = Path(ref.get('path') or '')
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            actual = 'missing'
        if not expected or actual != expected or ref.get('sha256') != expected:
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', {'approvedSourceVideoHash': expected}, {'currentHash': actual})
        source_preservation = dict(sourceVideo=deepcopy(ref), editScope=deepcopy(edit_scope),
            characters=cast, acting=deepcopy(card.get('acting', [])),
            stateTransitions=deepcopy(card.get('stateChanges', [])),
            identityReplacementQualified=False)
        warnings.append('Bounded source-video preservation only. New canonical identity replacement is unqualified; no image identity tags are invented.')
        cast = []
    identities = {}
    for index, ref in enumerate(references, 1):
        role = str(ref.get('role', ''))
        if role in {'character identity', 'character_identity'}:
            name = ref.get('canonicalCharacterId') or ref.get('name')
        elif ref.get('intactTurnaround') or ref.get('sameCharacterGroup') or character_id(role) in cast:
            name = ref.get('canonicalCharacterId') or role
        else:
            continue
        if not name:
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', 'named identity', ref)
            continue
        cid = character_id(name)
        tag = ref.get('slot') or f'@Image{index}'
        # A sourceSlot is historical authoring provenance, never the upload index.
        if not re.fullmatch(TAG, tag) or int(re.search(r'\d+$', tag)[0]) != index:
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', f'image upload {index}', tag)
        key = next((k for k in ('sha256', 'hash', 'md5') if ref.get(k)), None)
        binding = dict(tag=tag, path=ref.get('path'),
                       hash=ref.get(key) if key else None,
                       hashAlgorithm='md5' if key == 'md5' else 'sha256')
        if not binding['path'] or not binding['hash']:
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', 'file and content hash', binding)
        # Absolute native paths can be checked here. Project paths are checked
        # against the workspace's file records by its existing artifact gate.
        path = Path(binding['path'] or '')
        if path.is_absolute():
            try:
                actual = hashlib.new(binding['hashAlgorithm'], path.read_bytes()).hexdigest()
            except OSError:
                actual = 'missing'
            if actual != binding['hash']:
                fault('CHARACTER_REFERENCE_ROLE_MISMATCH', binding, {'currentHash': actual})
        # The identity registry's own record is separate from a caller's role label.
        canonical = ref.get('canonicalIdentity')
        if canonical and (character_id(canonical.get('character')) != cid or
                          canonical.get('path') != binding['path'] or
                          canonical.get('hash') != binding['hash']):
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', canonical, {'character': cid, **binding})
        identities.setdefault(cid, []).append((binding, ref))
        if cid not in cast:
            cast.append(cid)

    cues = _dialogue(shot)
    for cid in cast:
        bindings = identities.get(cid, [])
        if len(bindings) != 1:
            fault('CHARACTER_REFERENCE_ROLE_MISMATCH', {'character': cid, 'identityCount': 1},
                  {'identityCount': len(bindings)})
            continue
        binding, ref = bindings[0]
        role = authored.get(cid, {})
        views = []
        for view in card.get('views', []):
            visible = view.get('visibleEntities')
            if visible is not None and cid not in visible:
                continue
            views.append(dict(viewId=view.get('viewId'), timing=view.get('timing'),
                              visible=True if visible is not None else 'unverified'))
        states = [deepcopy(s) for s in card.get('stateChanges', [])
                  if character_id(s.get('entityId') or s.get('subject')) == cid]
        acting = [deepcopy(a) for a in card.get('acting', [])
                  if character_id(a.get('character')) == cid]
        rows.append(dict(characterId=cid, name=_name(cid), identity=binding,
                         traits=deepcopy(role.get('identityTraits') or ref.get('traits') or {}),
                         allowedActions=deepcopy(role.get('allowedActions', [])),
                         prohibitedActions=deepcopy(role.get('prohibitedActions', [])),
                         exclusiveActions=deepcopy(role.get('exclusiveActions', [])),
                         acting=acting, stateTransitions=states, views=views,
                         dialogue=[c for c in cues if c['speaker'] == cid]))
    for i, row in enumerate(rows):
        for other in rows[i + 1:]:
            if row['identity']['hash'] == other['identity']['hash']:
                exceptions = card.get('sharedIdentityExceptions', [])
                authorisations = snapshot.get('authorities', {}).get('identityAuthorisations', [])
                pair = {row['characterId'], other['characterId']}
                permitted = any(set(e.get('characters', [])) == pair and any(
                    a.get('id') == e.get('authorisation') and a.get('authorisedBy') and
                    set(a.get('characters', [])) == pair and
                    a.get('shotId') == shot.get('shotId', shot.get('id'))
                    for a in authorisations) for e in exceptions)
                if not permitted:
                    fault('CHARACTER_IDENTITY_SOURCE_SHARED', 'distinct approved identities',
                          [row['characterId'], other['characterId'], row['identity']])
    if not cast:
        warnings.append('No recurring character records supplied; identity coverage is unverified.')
    elif not authored:
        warnings.append('Roles derived from existing acting, state and dialogue records; no explicit exclusive-action contract.')
    matrix = dict(version=VERSION, characters=rows, dialogue=cues,
                  sourcePreservation=source_preservation,
                  viewOrder=[v['viewId'] for v in card.get('views', [])],
                  sourceHash=digest(shot), manifestHash=digest(references),
                  audioBinding=deepcopy(snapshot.get('audio')), audioBindingHash=digest(snapshot.get('audio')),
                  errors=errors, warnings=warnings,
                  recognition='explicit records and literal claims only; no pixel recognition')
    return matrix


def audit(snapshot, matrix=None):
    matrix = deepcopy(matrix) if matrix is not None else resolve(snapshot)
    prompt = snapshot.get('prompt', '')
    rows = matrix['characters']
    errors = matrix['errors']

    def fault(code, expected, actual):
        errors.append(dict(code=code, expected=expected, actual=actual))

    for row in rows:
        name = re.escape(row['name'])
        alias = re.escape(row['name'].upper().replace(' ', '_') + '_ID')
        patterns = [rf'\b{name}\s+from\s+({TAG})',
                    rf'\b(?:{name}|{alias})\s+(?:is\s+|=\s*)?({TAG})',
                    rf'({TAG})\s*(?:=|:)\s*(?:one\s+)?{name}(?!\w)',
                    rf'({TAG})\s+defines\s+(?:exactly one\s+)?{name}(?!\w)']
        for pattern in patterns:
            for match in re.finditer(pattern, prompt, re.I):
                if re.search(r'\d+$', match[1])[0] != re.search(r'\d+$', row['identity']['tag'])[0]:
                    fault('CHARACTER_REFERENCE_ROLE_MISMATCH',
                          {'character': row['characterId'], **row['identity']}, match[0])
        # Literal subject/verb clauses from the authored exclusive action record.
        # No semantic paraphrase detection is claimed. Negated clauses do not match.
        for action in row['exclusiveActions']:
            for other in rows:
                if other is row:
                    continue
                pattern = rf'(?<!\w){re.escape(other["name"])}\s+(?:(?:from\s+)?{TAG}\s+)?{re.escape(action)}(?!\w)'
                for match in re.finditer(pattern, prompt, re.I):
                    fault('CHARACTER_ACTION_OWNER_MISMATCH',
                          {'character': row['characterId'], 'action': action}, match[0])
        for action in row['prohibitedActions']:
            pattern = rf'(?<!\w){name}\s+(?:(?:from\s+)?{TAG}\s+)?{re.escape(action)}(?!\w)'
            for match in re.finditer(pattern, prompt, re.I):
                fault('CHARACTER_ACTION_OWNER_MISMATCH', {'prohibitedFor': row['characterId'], 'action': action}, match[0])

    shot = snapshot.get('authorities', {}).get('shot', {})
    authored_cues = matrix['dialogue']
    specialist = snapshot.get('authorities', {}).get('specialist', {})
    for event in specialist.get('timeline', []):
        if event.get('channel') != 'dialogue':
            continue
        matches = [c for c in authored_cues if c['text'] == event.get('event') and
                   (c['startSec'] is None or c['startSec'] == event.get('startSec'))]
        if matches and character_id(event.get('performer')) not in {c['speaker'] for c in matches}:
            fault('CHARACTER_DIALOGUE_OWNER_MISMATCH', matches, event)
    for cue in authored_cues:
        # Detect explicit speech ownership, never infer a speaker from a bare quote.
        for row in rows:
            if row['characterId'] == cue['speaker']:
                continue
            pattern = rf'(?<!\w){re.escape(row["name"])}\s+(?:(?:from\s+)?{TAG}\s+)?(?:says|delivers)\s+[{{“"]{re.escape(cue["text"])}[}}”"]'
            for match in re.finditer(pattern, prompt, re.I):
                fault('CHARACTER_DIALOGUE_OWNER_MISMATCH', cue, match[0])
    expected_events = (shot.get('directorCard') or {}).get('characterRoleEvents', [])
    actual_events = specialist.get('characterRoleEvents', [])
    if expected_events and specialist:
        expected_by_id = {e.get('eventId'): e for e in expected_events}
        actual_by_id = {e.get('eventId'): e for e in actual_events}
        if set(expected_by_id) != set(actual_by_id):
            fault('CHARACTER_ACTION_OWNER_MISMATCH', expected_events, actual_events)
        for event_id, event in actual_by_id.items():
            original = expected_by_id.get(event_id)
            if original is None:
                continue
            expected_character = character_id(original.get('character') or original.get('owner'))
            actual_character = character_id(event.get('character') or event.get('owner'))
            if expected_character != actual_character:
                fault('CHARACTER_ACTION_OWNER_MISMATCH', original, event)
    matrix['status'] = 'BLOCKED' if errors else 'WARN' if matrix['warnings'] else 'PASS'
    matrix['matrixHash'] = digest({k: v for k, v in matrix.items() if k != 'matrixHash'})
    return matrix


def clauses(matrix):
    lines = []
    for row in matrix['characters']:
        identity = row['identity']
        traits = row['traits']
        features = traits.get('distinguishingFeatures', []) if isinstance(traits, dict) else []
        if isinstance(features, str):
            features = [features]
        if not features:
            features = [str(v) for k, v in traits.items() if k != 'mustNotBorrow']
        description = '; '.join(features)
        lines.append(f'{row["characterId"]} = {identity["tag"]} ({Path(identity["path"]).name})' +
                     (f': {description}.' if description else '.'))
        if row['allowedActions']:
            lines.append('Assigned actions: ' + '; '.join(row['allowedActions']) + '.')
    if len(matrix['characters']) > 1:
        lines.append('Keep each named identity with its assigned action, voice, prop and ending; do not swap characters.')
    if lines:
        lines.insert(0, '[CHARACTER ROLE INTEGRITY]')
    return '\n'.join(lines)


def bind_visual_names(prompt, matrix):
    """Bind names where the action is described; leave spoken/audio text verbatim.

    Only labelled visual fields are eligible. Existing mappings are validated by
    audit(), never silently repaired here. Literal dialogue is protected even if
    a visual field happens to quote it.
    """
    visual = {'Camera', 'Action', 'Performance', 'Setting / light / materials',
              'End state', 'World/state', 'Subjects/action', 'Constraints'}
    protected = r'(\{[^{}]*\}|[“\"][^“”\"\n]+[”\"])'
    active = False
    result = []
    for line in prompt.splitlines(keepends=True):
        label = re.match(r'^([A-Za-z][A-Za-z /-]*):', line)
        if label:
            active = label[1] in visual
        elif line.startswith('[') or re.match(r'^(?:Shot|Phase) \d+:', line) or not line.strip():
            active = False
        if active:
            parts = re.split(protected, line)
            for i in range(0, len(parts), 2):
                for row in matrix['characters']:
                    name = re.escape(row['name'])
                    pattern = rf'(?<![\w:@]){name}(?!\w)(?!\s*(?:from\s+)?\(?@(?:图|Image)\d+)'
                    parts[i] = re.sub(pattern, lambda m: m[0] + ' ' + row['identity']['tag'], parts[i])
            line = ''.join(parts)
        result.append(line)
    return ''.join(result)


def emit(prompt, matrix):
    """Add canonical anchors to existing sections without rewriting any dialogue."""
    text = clauses(matrix)
    if not text:
        return prompt
    marker = '[TIMED ACTION]' if '[TIMED ACTION]' in prompt else '[Shot Sequence]'
    if marker in prompt:
        prompt = prompt.replace(marker, text + '\n\n' + marker, 1)
    else:
        prompt += '\n' + text
    return bind_visual_names(prompt, matrix)
