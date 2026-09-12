"""Project verified approved media facts into WATCH without modifying approvals.

Placement receipts, rather than estimated script timings, own spoken intervals.
An approved vision reference controls its depicted content only, not the set.
"""
import copy
import hashlib
import json
from pathlib import Path


def watch_shot(shot, ledger):
    result = copy.deepcopy(shot)
    approval = ledger.get('voiceApproval') or {}
    receipt_path = ledger.get('voPlacementPath')
    if not approval.get('approved') or not receipt_path:
        return result
    receipt = json.loads(Path(receipt_path).read_text())
    audio = Path(approval['path'])
    if str(audio) != receipt.get('outputPath') or hashlib.sha256(audio.read_bytes()).hexdigest() != receipt.get('outputSha256'):
        raise ValueError('Approved Audio1 does not match its placement receipt.')
    timing = Path(receipt['dialogueTimingPath'])
    if hashlib.sha256(timing.read_bytes()).hexdigest() != receipt.get('dialogueTimingSha256'):
        raise ValueError('Audio1 dialogue timing receipt changed.')
    placements = receipt.get('placements') or []
    by_id = {p['dialogueOccurrenceId']: p for p in placements if p.get('dialogueOccurrenceId')}
    if len(by_id) != len(placements):
        raise ValueError('Audio1 placement occurrences must be unique and explicit.')
    prior = {p['dialogueOccurrenceId']:p for p in (result.get('approvedAudioTimingAuthority') or {}).get('intervals', [])}
    changes = []
    for index, line in enumerate(result.get('dialogueLines') or []):
        placement = by_id.get(line.get('dialogueOccurrenceId'))
        if placement is None:
            raise ValueError('Approved Audio1 has no placement for dialogue occurrence ' + str(line.get('dialogueOccurrenceId')))
        start, end = float(placement['targetStartSec']), float(placement['targetEndSec'])
        if not 0 <= start < end <= float(shot['durationSec']):
            raise ValueError('Approved dialogue falls outside the current shot duration.')
        changes.append({'dialogueOccurrenceId': line['dialogueOccurrenceId'],
                        'estimated': prior.get(line['dialogueOccurrenceId'], {}).get('estimated', {'startSec':line.get('startSec'),'endSec':line.get('endSec')}),
                        'measured': {'startSec':start,'endSec':round(end,6)}})
        line.update(startSec=start,endSec=round(end,6))
    # Legacy cards encode completion as a typed state value. Resolve only an
    # unambiguous speaker + exact line pair; repeated dialogue needs explicit IDs.
    for event in (result.get('directorCard') or {}).get('stateChanges', []):
        status = (event.get('afterValues') or {}).get('spokenLineStatus', '')
        if not status.startswith('completed: '):
            continue
        matches = [line for line in result.get('dialogueLines', [])
                   if line.get('exactText') == status[len('completed: '):]
                   and ('char:' + str(line.get('speaker', '')).casefold()) == str(event.get('entityId','')).casefold()]
        explicit = event.get('dialogueOccurrenceId')
        if explicit:
            matches = [line for line in matches if line.get('dialogueOccurrenceId') == explicit]
        if len(matches) != 1:
            raise ValueError('Dialogue-dependent state event needs an explicit occurrence binding.')
        line = matches[0]
        event['dialogueOccurrenceId'] = line['dialogueOccurrenceId']
        if (event.get('beforeValues') or {}).get('spokenLineStatus') != status:
            event.update(atSec=line['endSec'], timing=f"{line['endSec']:g}s",
                         cause='Approved Audio1 dialogue occurrence completes at its measured placement end.')
        else:
            event['cause'] = 'After the approved Audio1 occurrence completes, perform the authored physical transition.'
    # Voice generation briefs contain estimates, not WATCH timing authority.
    result.pop('audioBrief', None)
    result['approvedAudioTimingAuthority'] = {'placementPath':receipt_path,
        'placementSha256':hashlib.sha256(Path(receipt_path).read_bytes()).hexdigest(),
        'audioSha256':receipt['outputSha256'], 'intervals':changes}
    return result


def reference_records(records, ledger):
    result = copy.deepcopy(records)
    binding = ledger.get('visionReferenceBinding') or {}
    if not binding.get('approvedBy'):
        return result
    for ref in result:
        if ref.get('role') != binding.get('role'):
            continue
        if ref.get('path') != binding.get('sourcePath') or hashlib.sha256(Path(ref['path']).read_bytes()).hexdigest() != binding.get('sourceSha256'):
            raise ValueError('Approved vision reference content has changed.')
        ref['stateScope'] = {'authority':'vision_content', 'controlsDynamicState':True,
                             'storyTime':'authored vision beat only',
                             'scope':binding.get('scope'), 'physicalPresence':False,
                             'controlsGeography':False}
        ref['approvedContentBinding'] = copy.deepcopy(binding)
    return result
