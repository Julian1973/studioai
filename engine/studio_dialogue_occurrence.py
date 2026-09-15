"""Read-only occurrence identity and exact downstream partition validation.

Only the two complete SHA-256 namespace forms are aliases. No text, position,
partial digest or cross-revision guessing. Authority records are never rewritten.
"""
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import re


def record(value):
    if isinstance(value, str):
        return {'dialogueOccurrenceId': value}
    return value.model_dump() if hasattr(value, 'model_dump') else dict(value)


def identity(value):
    value = str(value or '')
    match = re.fullmatch(r'(?:dialogue-occurrence:)?sha256:([0-9a-f]{64})', value)
    return 'dialogue-occurrence:sha256:' + match[1] if match else value


def _text(row):
    return next((row[key] for key in ('exactText', 'exactDialogue', 'text') if key in row), None)


def text_hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _truth(row):
    text = _text(row)
    return {key: value for key, value in {
        'speaker': row.get('speaker'), 'exactText': text,
        'exactTextHash': row.get('exactTextHash') or (text_hash(text) if text is not None else None),
        'sourceSpan': row.get('sourceSpan'),
        'scriptRevision': row.get('scriptRevision', row.get('scriptVersionId')),
        'sourceEventId': row.get('sourceEventId'), 'sourceEventIndex': row.get('sourceEventIndex'),
        'sourceBeatId': row.get('sourceBeatId'), 'beatId': row.get('beatId'),
    }.items() if value is not None}


def resolve(value, authority):
    """Return an independent canonical record, or None for unknown/ambiguous IDs."""
    target = identity(value)
    candidates = [record(row) for row in authority
                  if target and identity(record(row).get('dialogueOccurrenceId')) == target]
    if not candidates:
        return None
    truths = {json.dumps(_truth(row), sort_keys=True, ensure_ascii=False) for row in candidates}
    if len(truths) != 1:
        return None
    result = deepcopy(candidates[0])
    result['dialogueOccurrenceId'] = target
    # Keep legacy metadata absence explicit; validation hashes bytes without
    # silently adding fields to approved request projections.
    return result


def resolve_id(value, authority):
    result = resolve(value, authority)
    return result['dialogueOccurrenceId'] if result is not None else None


def resolved_ids(values, authority):
    # Unknown values stay visible to the set diagnostic, never silently disappear.
    return [resolve_id(value, authority) or value for value in values]


class OccurrenceSetMismatch(RuntimeError):
    def __init__(self, diagnostic):
        self.diagnostic = diagnostic
        super().__init__('DIALOGUE_OCCURRENCE_SET_MISMATCH ' + json.dumps(diagnostic, ensure_ascii=False, sort_keys=True))


def require_set(expected, actual, *, ordered=True):
    """Check a whole assigned partition. ID-only timing rows need no invented text.

    Any payload fields actually carried downstream must agree byte-for-byte.
    The returned list is a read projection; caller-owned/approved inputs are untouched.
    """
    source = [record(row) for row in expected]
    rows = [record(row) for row in actual]
    expected_ids = [identity(row.get('dialogueOccurrenceId')) for row in source]
    actual_ids = []
    diagnostics = dict(expectedCount=len(source), actualCount=len(rows),
        missingOccurrenceIds=[], extraOccurrenceIds=[], duplicateOccurrenceIds=[],
        speakerMismatch=[], textHashMismatch=[], sourceSpanMismatch=[], scriptRevisionMismatch=[],
        sourceIdentityMismatch=[], ambiguousOccurrenceIds=[])
    for row in source:
        oid = row.get('dialogueOccurrenceId')
        if resolve(oid, source) is None:
            diagnostics['ambiguousOccurrenceIds'].append(oid)
        text = _text(row)
        if text is not None and row.get('exactTextHash', text_hash(text)) != text_hash(text):
            diagnostics['textHashMismatch'].append(oid)
    projected = []
    for row in rows:
        oid = row.get('dialogueOccurrenceId')
        canonical = resolve(oid, source)
        actual_ids.append(canonical['dialogueOccurrenceId'] if canonical else oid)
        copy = deepcopy(row)
        if canonical:
            copy['dialogueOccurrenceId'] = canonical['dialogueOccurrenceId']
            for key, value in metadata(canonical).items():
                if copy.get(key) is None:
                    copy[key] = value
            expected_truth, got_truth = _truth(canonical), _truth(row)
            segmentation = canonical.get('sourceSegmentation')
            if isinstance(segmentation, dict) and segmentation.get('segmentationStatus') == 'VERIFIED':
                # A voiced projection may carry the verified speech instead of raw
                # screenplay. Identity and all other source fields stay protected.
                allowed = (segmentation.get('rawSourceText'), segmentation.get('spokenText'))
                if _text(row) is not None and _text(row) not in allowed:
                    diagnostics['textHashMismatch'].append(canonical['dialogueOccurrenceId'])
                elif _text(row) is not None:
                    got_truth['exactText'] = expected_truth.get('exactText')
                    if not row.get('exactTextHash'):
                        got_truth['exactTextHash'] = expected_truth.get('exactTextHash')
                if row.get('sourceSegmentation') is not None and row['sourceSegmentation'] != segmentation:
                    diagnostics['sourceIdentityMismatch'].append(canonical['dialogueOccurrenceId'])

            for field, key in [('speaker','speakerMismatch'), ('exactText','textHashMismatch'),
                               ('exactTextHash','textHashMismatch'), ('sourceSpan','sourceSpanMismatch'),
                               ('scriptRevision','scriptRevisionMismatch'), ('sourceEventId','sourceIdentityMismatch'),
                               ('sourceEventIndex','sourceIdentityMismatch'), ('sourceBeatId','sourceIdentityMismatch')]:
                if field in got_truth and field in expected_truth and got_truth[field] != expected_truth[field]:
                    diagnostics[key].append(canonical['dialogueOccurrenceId'])
        projected.append(copy)
    ec, ac = Counter(expected_ids), Counter(actual_ids)
    diagnostics['missingOccurrenceIds'] = list((ec-ac).elements())
    diagnostics['extraOccurrenceIds'] = list((ac-ec).elements())
    diagnostics['duplicateOccurrenceIds'] = list(dict.fromkeys([x for x,c in ac.items() if c>1] + [x for x,c in ec.items() if c>1]))
    diagnostics['orderMismatch'] = ordered and expected_ids != actual_ids
    if any(value for key,value in diagnostics.items() if key not in ('expectedCount','actualCount')):
        raise OccurrenceSetMismatch(diagnostics)
    return projected


class Index(Mapping):
    """Alias-aware lookup retaining ambiguity that a dict comprehension would erase."""
    def __init__(self, rows):
        self.rows = [record(row) for row in rows]

    def get(self, key, default=None):
        found = resolve(key, self.rows)
        return found if found is not None else default

    def __getitem__(self, key):
        found = self.get(key)
        if found is None:
            raise KeyError(key)
        return found

    def __iter__(self):
        return iter(dict.fromkeys(identity(row.get('dialogueOccurrenceId')) for row in self.rows))

    def __len__(self):
        return len(list(iter(self)))


def same(left, right, authority):
    a, b = resolve_id(left, authority), resolve_id(right, authority)
    return a is not None and a == b


def metadata(row):
    row = record(row)
    return {key: deepcopy(row[key]) for key in
            ('exactTextHash', 'sourceSpan', 'scriptRevision', 'sourceSegmentation') if row.get(key) is not None}


def from_source_span(speaker, text, script, start):
    """Mint a new project occurrence from a verified source span, never an alias guess."""
    end = start + len(text)
    if script[start:end] != text:
        raise ValueError('Dialogue source span does not contain the exact text')
    truth = dict(speaker=speaker, exactText=text, exactTextHash=text_hash(text),
                 sourceSpan={'start':start,'end':end}, scriptRevision='sha256:'+text_hash(script))
    digest = text_hash(json.dumps(truth, sort_keys=True, ensure_ascii=False))
    return {'dialogueOccurrenceId':'dialogue-occurrence:sha256:'+digest, **truth}


def lookup(mapping, value, default=None):
    """Read an existing ID-keyed selection map without rewriting its stored keys."""
    oid = resolve_id(value, list(mapping))
    matches = [v for k,v in mapping.items() if oid and identity(k) == oid]
    if not matches or any(v != matches[0] for v in matches[1:]):
        return default
    return deepcopy(matches[0])
