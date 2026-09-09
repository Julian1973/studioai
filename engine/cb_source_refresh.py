"""Refresh derived script extraction without rewriting script or creative direction.

An unchanged script hash does not prove an old parser's dialogue boundaries are
current. Prove the entire ordered source text, then rebind its typed events before
any creative provider call. Existing production media are never edited here.
"""
import bisect
import copy
import hashlib
import json
from pathlib import Path

import cb_db
import cb_lineage


def _text(value):
    return ' '.join(str(value or '').split())


def rebind(beats, events, script_version):
    import cb_intake
    old = [_text(' '.join(c.get('dialogue') or c.get('action') or ''
                         for c in b.get('cuts', []))) for b in beats]
    new = [_text((e['speaker'] + ': ' if e['type'] == 'dialogue' else '') + e['text'])
           for e in events]
    if not old or not new or ' '.join(old) != ' '.join(new):
        raise ValueError('Current extraction changes the ordered source text; a mechanical refresh cannot author that change.')
    event_offsets, offset = [], 0
    for text in new:
        event_offsets.append(offset); offset += len(text) + 1
    starts, offset, adjusted = [], 0, []
    for beat, text in zip(beats, old):
        index = bisect.bisect_left(event_offsets, offset)
        if index and (index == len(event_offsets) or event_offsets[index] != offset):
            if events[index - 1]['type'] != 'action':
                raise ValueError('A revised beat boundary would divide spoken dialogue.')
            adjusted.append(beat['beatCode'])
        starts.append(index); offset += len(text) + 1
    revised = copy.deepcopy(beats)
    for beat, lo, hi in zip(revised, starts, starts[1:] + [len(events)]):
        if lo >= hi or any(str(e['scene']) != str(beat['sceneNumber']) for e in events[lo:hi]):
            raise ValueError('Current extraction cannot preserve the existing nonempty scene/beat partition.')
        beat['cuts'] = cb_intake._build_cuts(events, lo, hi - 1)
    revised = cb_intake._backfill_source_occurrences(revised, events, script_version)
    return revised, {'orderedTextSha256': hashlib.sha256(' '.join(new).encode()).hexdigest(),
                     'actionBoundaryAdjustments': adjusted,
                     'scriptTextChanged': False, 'creativeFieldsChanged': False}


def plan(package, events, script_version):
    beats, evidence = rebind(package['beats'], events, script_version)
    result = copy.deepcopy(package)
    result['beats'] = beats
    result['sourceContract'] = cb_lineage.beat_package_source_contract(script_version, beats)
    result['contentSignature'] = cb_lineage.beat_package_signature(result)
    changed = result['contentSignature'] != package.get('contentSignature')
    return result, {**evidence, 'changed': changed,
                    'previousContentDigest': (package.get('contentSignature') or {}).get('digest'),
                    'currentContentDigest': result['contentSignature']['digest']}


def refresh_source_extraction(root, episode, script_store, log=print):
    import cb_intake
    root = Path(root)
    paths = sorted((root / 'cb-output').glob(f'{episode}_*beat_package.json'),
                   key=lambda p: p.stat().st_mtime)
    if not paths:
        return {'changed': False}  # Normal intake owns a missing package.
    current = script_store.current(episode, required=True)
    script = root / current['contentPath']
    raw = script.read_bytes()
    if hashlib.sha256(raw).hexdigest() != current['sha256']:
        raise ValueError('Immutable script bytes changed before extraction refresh.')
    parsed = cb_intake.parse_script(raw.decode('utf-8'), cb_intake._load_roster(), log=lambda *a: None)
    cb_intake._annotate_source_events(parsed['events'], current['scriptVersionId'])
    path = paths[-1]
    package, package_digest = cb_db.read_json_document(root, path)
    if (package.get('sourceScript') or {}).get('scriptVersionId') != current['scriptVersionId']:
        return {'changed': False}  # Normal script-version validation must refuse this.
    updated, evidence = plan(package, parsed['events'], current['scriptVersionId'])
    if not evidence['changed']:
        return evidence
    stamp = cb_intake._now().replace(':', '').replace('-', '')
    archive = root / 'cb-output' / 'archive' / 'source_extraction' / f'{episode}_{stamp}'
    archive.mkdir(parents=True, exist_ok=False)
    cb_db.atomic_write_json(root, archive / path.name, package)
    evidence.update(at=cb_intake._now(), sourceScriptSha256=current['sha256'],
                    parser='cb_intake.parse_script',
                    reason='Reclassify current exact script text into speech and action before scene direction.')
    updated['sourceExtractionRefresh'] = evidence
    cb_db.atomic_write_json(root, path, updated, expected_digest=package_digest)
    # A proven extraction-only refresh preserves the existing episode direction;
    # record the rebase explicitly instead of pretending it was newly authored.
    vision_path = root / 'cb-output' / 'creative' / f'{episode}_episode_vision.json'
    if vision_path.exists():
        vision, vision_digest = cb_db.read_json_document(root, vision_path)
        old_inputs = (vision.get('inputSignature') or {}).get('inputs') or {}
        expected_old = cb_lineage.episode_vision_inputs(current['scriptVersionId'],
            package['contentSignature'], old_inputs.get('canonProfileDigest'))
        if old_inputs == expected_old:
            cb_db.atomic_write_json(root, archive / vision_path.name, vision)
            vision['sourceExtractionRefresh'] = {**evidence, 'newCreativePassClaimed': False,
                                                 'previousInputSignature': vision['inputSignature']}
            new_inputs = cb_lineage.episode_vision_inputs(current['scriptVersionId'],
                updated['contentSignature'], old_inputs.get('canonProfileDigest'))
            vision['inputSignature'] = cb_lineage.dependency_signature('episode-vision', new_inputs)
            cb_db.atomic_write_json(root, vision_path, vision, expected_digest=vision_digest)
    log('SOURCE EXTRACTION — refreshed speech/action boundaries from unchanged script bytes; originals archived; no provider call')
    return evidence
