"""Carry approved PCM performances into a revised unit without another TTS call.

The source approval applies to the performance, not a newly invented delivery.
Every copied sample, occurrence, placement and explicit reuse instruction is recorded.
"""
import copy
import hashlib
import json
import wave
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def binding(shot):
    return digest({k: shot.get(k) for k in
                   ('shotId', 'durationSec', 'dialogueLines', 'voiceDirectorBrief')})


def _pcm(path):
    with wave.open(str(path), 'rb') as source:
        if source.getcomptype() != 'NONE':
            raise ValueError('Approved voice reuse requires uncompressed PCM audio.')
        return source.getparams(), source.readframes(source.getnframes())


def derive(source_shot, source_ledger, target_shot, out, authorization):
    if not str(authorization or '').strip():
        raise ValueError('Reuse requires an explicit instruction to preserve the approved performance.')
    approval = source_ledger.get('voiceApproval') or {}
    source_path = source_ledger.get('voPath')
    placement_path = source_ledger.get('voPlacementPath')
    if (not approval.get('approved') or approval.get('path') != source_path or
            sha(source_path) != approval.get('contentHash') or
            sha(placement_path) != approval.get('placementContentHash')):
        raise ValueError('The source is not the unchanged approved voice and timing bundle.')
    source_lines = {x['dialogueOccurrenceId']: x for x in source_shot['dialogueLines']}
    requests = {x['dialogueOccurrenceId']: x for x in source_ledger['voGeneratedFrom']}
    placed = {x['dialogueOccurrenceId']: x for x in
              json.loads(Path(placement_path).read_text())['placements']}
    params, pcm = _pcm(source_path)
    stride = params.nchannels * params.sampwidth
    sr = params.framerate
    frames = round(float(target_shot['durationSec']) * sr)
    output = bytearray(frames * stride)
    pieces, timings, selected, seen = [], [], [], set()
    previous_end = 0
    for index, line in enumerate(target_shot['dialogueLines']):
        oid = line['dialogueOccurrenceId']
        if oid in seen or oid not in source_lines or oid not in placed or oid not in requests:
            raise ValueError('Every reused occurrence must identify one approved source performance.')
        seen.add(oid)
        original = source_lines[oid]
        if any(line.get(k) != original.get(k) for k in ('speaker', 'exactText', 'sourceEventId')):
            raise ValueError('Reusing a performance cannot change its words, speaker or source event.')
        p = placed[oid]
        start = float(p['targetStartSec']); end = float(p['targetEndSec'])
        target = float(line['startSec']); window = float(line['endSec'])
        if target < 0 or target + end - start > window + 1 / sr or window > frames / sr:
            raise ValueError('The unchanged performance does not fit the revised timing window.')
        # Copy the already-cleaned waveform plus available silence. Never borrow
        # a neighbouring performance as an audio handle.
        earlier = [float(v['targetEndSec']) for v in placed.values() if float(v['targetStartSec']) < start]
        later = [float(v['targetStartSec']) for v in placed.values() if float(v['targetStartSec']) > start]
        lead = min(.12, start - max(earlier, default=0), target - previous_end / sr)
        tail = min(.12, min(later, default=len(pcm) / stride / sr) - end,
                   window - (target + end - start))
        lead, tail = max(0, lead), max(0, tail)
        a, b = round((start - lead) * sr), round((end + tail) * sr)
        dest = round((target - lead) * sr)
        if a < 0 or b * stride > len(pcm) or dest < previous_end or dest + b - a > frames:
            raise ValueError('Approved voice reuse would overlap or clip a performance.')
        chunk = pcm[a * stride:b * stride]
        output[dest * stride:(dest + b - a) * stride] = chunk
        previous_end = dest + b - a
        pieces.append(dict(dialogueOccurrenceId=oid, sourceStartFrame=a,
                           sourceEndFrame=b, targetStartFrame=dest,
                           copiedSamplesSha256=hashlib.sha256(chunk).hexdigest()))
        timings.append(dict(dialogueIndex=index, dialogueOccurrenceId=oid,
                            sourceStartSec=start, sourceEndSec=end,
                            targetStartSec=target, targetEndSec=target + end - start,
                            approvedWindowEndSec=window, edgeFadeSec=0,
                            sourceHandleSec=lead))
        selected.append(copy.deepcopy(requests[oid]))
    if not selected:
        raise ValueError('No approved spoken performance was selected.')
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise ValueError('Voice reuse outputs must have a new immutable path.')
    with wave.open(str(out), 'wb') as wav:
        wav.setparams(params); wav.writeframes(output)
    timing = out.with_suffix('.source-dialogue.json')
    timing.write_text(json.dumps(dict(schemaVersion=1, provider='approved-performance-reuse',
        audioPath=source_path, audioSha256=sha(source_path), inputCount=len(selected),
        isolatedDialogueAssembly=True, voiceSegments=[dict(
            dialogueInputIndex=i, voiceId=selected[i]['voiceId'],
            startTimeSec=p['sourceStartSec'], endTimeSec=p['sourceEndSec'])
            for i, p in enumerate(timings)]), indent=2) + '\n')
    placement = out.with_suffix(out.suffix + '.timing.json')
    placement.write_text(json.dumps(dict(schemaVersion=1, rawAudioPath=source_path,
        rawAudioSha256=sha(source_path), dialogueTimingPath=str(timing),
        dialogueTimingSha256=sha(timing), durationSec=frames / sr,
        placements=timings, outputPath=str(out), outputSha256=sha(out)), indent=2) + '\n')
    record = dict(schemaVersion=1, authorization=authorization,
                  sourceShotId=source_shot['shotId'], sourceApproval=copy.deepcopy(approval),
                  sourcePath=source_path, sourceSha256=sha(source_path),
                  targetBinding=binding(target_shot), requests=selected,
                  requestsHash=digest(selected), pieces=pieces,
                  outputPath=str(out), outputSha256=sha(out),
                  newPerformanceGenerated=False, newHumanAuditionClaimed=False)
    return dict(voPath=str(out), voRawPath=source_path, voTimingPath=str(timing),
                voPlacementPath=str(placement), voGeneratedFrom=selected,
                voicePerformanceReuse=record)


def current_requests(ledger, shot):
    record = ledger.get('voicePerformanceReuse') or {}
    if not record or record.get('targetBinding') != binding(shot):
        return None
    if (not record.get('authorization') or not record.get('sourceApproval', {}).get('approved') or
            digest(record['requests']) != record.get('requestsHash') or
            sha(record['sourcePath']) != record.get('sourceSha256') or
            ledger.get('voPath') != record.get('outputPath') or
            sha(record['outputPath']) != record.get('outputSha256')):
        raise ValueError('Approved performance reuse no longer matches its recorded source or output.')
    return copy.deepcopy(record['requests'])


def apply(render, scene, shot_id, episode, source_package_path, source_shot_id,
          authorization, log=print):
    """Native production operation for an explicitly authorised split/retime."""
    import uuid
    source = json.loads(Path(source_package_path).read_text())
    pkg, path = render.load_pkg(scene, episode)
    if source.get('episode') != pkg.get('episode') or source.get('sceneNumber') != pkg.get('sceneNumber'):
        raise ValueError('Performance reuse is scoped to the same episode and scene.')
    render._require_valid(pkg)
    render._require_current_lineage(pkg, scene, episode)
    target = render._shot(pkg, shot_id)
    ledger = render._ledger(pkg, shot_id)
    source_shot = render._shot(source, source_shot_id)
    source_ledger = render._ledger(source, source_shot_id)
    signature = render._voice_input_signature(pkg, target, [x for x in source_ledger['voGeneratedFrom']
        if x['dialogueOccurrenceId'] in {d['dialogueOccurrenceId'] for d in target['dialogueLines']}])
    old_signature = source_ledger['voiceApproval']['inputSignature']
    for key in ('canonProfileDigest', 'voiceCardsHash', 'voiceRegistersHash',
                'voiceRulebookHash', 'voiceCompilerVersion', 'pronunciationOverrides'):
        if signature.get(key) != old_signature.get(key):
            raise ValueError('The current voice authority differs from the approved source: ' + key)
    source_requests = {x['dialogueOccurrenceId']: x for x in source_ledger['voGeneratedFrom']}
    source_ids = [voice for line in target['dialogueLines'] for voice in
                  source_requests[line['dialogueOccurrenceId']].get('voiceIds',
                      [source_requests[line['dialogueOccurrenceId']]['voiceId']])]
    if source_ids != signature['voiceIds']:
        raise ValueError('The approved source voice no longer matches the current cast.')
    output = render.MEDIA / f'{episode}_{shot_id}_voice_reuse_{uuid.uuid4().hex[:8]}.wav'
    bundle = derive(source_shot, source_ledger, target, output, authorization)
    if ledger.get('voPath'):
        ledger.setdefault('voiceReuseHistory', []).append({k: copy.deepcopy(ledger.get(k)) for k in
            ('voPath', 'voRawPath', 'voTimingPath', 'voPlacementPath', 'voGeneratedFrom', 'voiceApproval')})
    signature = render._voice_input_signature(pkg, target, bundle['voGeneratedFrom'])
    ledger.update(bundle)
    ledger.update(voInputSignature=signature, voPackageRevision=pkg.get('revision'))
    ledger['voiceApproval'] = dict(approved=True, path=bundle['voPath'], at=render._now(),
        reviewedBy=source_ledger['voiceApproval'].get('reviewedBy'),
        sourceApprovedAt=source_ledger['voiceApproval'].get('at'),
        reuseAuthorization=authorization, newHumanAuditionClaimed=False,
        packageRevision=pkg.get('revision'), inputSignature=signature,
        contentHash=sha(bundle['voPath']), rawContentHash=sha(bundle['voRawPath']),
        timingContentHash=sha(bundle['voTimingPath']), placementContentHash=sha(bundle['voPlacementPath']))
    render._save(pkg, path)
    log(f'APPROVED PERFORMANCE REUSED — {shot_id}: {len(bundle["voGeneratedFrom"])} unchanged takes; timing updated; no TTS call')
    return bundle
