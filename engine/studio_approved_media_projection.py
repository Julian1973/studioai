"""Project verified approved media facts into WATCH without modifying approvals.

Placement receipts, rather than estimated script timings, own spoken intervals.
An approved vision reference controls its depicted content only, not the set.
"""
import copy
import hashlib
import json
from pathlib import Path


def watch_shot(shot, ledger, *, require_current_direction=True):
    result = copy.deepcopy(shot)
    approval = ledger.get('voiceApproval') or {}
    receipt_path = ledger.get('voPlacementPath')
    if not approval.get('approved') or not receipt_path:
        return result
    from studio_director_handoff import errors as direct_errors, source as direct_source
    from studio_request_evidence import digest as direct_digest
    faults = direct_errors(shot) if require_current_direction else []
    if faults:
        raise ValueError('DIRECTOR_REVISION_REQUIRED: ' + faults[0])
    original_source = direct_digest(direct_source(shot))
    original_card = direct_digest(shot.get('directorCard') or {})
    prior_projection = (shot.get('approvedAudioTimingAuthority') or {}).get('directProjection') or {}
    if (prior_projection.get('projectedSourceHash') == original_source and
            prior_projection.get('projectedDirectionHash') == original_card):
        original_source = prior_projection['originalSourceHash']
        original_card = prior_projection['originalDirectionHash']
    receipt = json.loads(Path(receipt_path).read_text())
    audio = Path(approval['path'])
    if str(audio) != receipt.get('outputPath') or hashlib.sha256(audio.read_bytes()).hexdigest() != receipt.get('outputSha256'):
        raise ValueError('Approved Audio1 does not match its placement receipt.')
    timing = Path(receipt['dialogueTimingPath'])
    if hashlib.sha256(timing.read_bytes()).hexdigest() != receipt.get('dialogueTimingSha256'):
        raise ValueError('Audio1 dialogue timing receipt changed.')
    placements = receipt.get('placements') or []
    lines = result.get('dialogueLines') or []
    by_id = {p['dialogueOccurrenceId']: p for p in placements if p.get('dialogueOccurrenceId')}
    if by_id and len(by_id) != len(placements):
        # Some placements are identified and some are not, or an ID repeats: ambiguous.
        raise ValueError('Audio1 placement occurrences must be unique and explicit.')
    if not by_id:
        # A receipt written before dialogue occurrence IDs existed binds by dialogue index.
        # That is only unambiguous when there is one placement per line, in order, and no
        # speaker repeats the same words within the shot.
        if len(placements) != len(lines) or any(
                p.get('dialogueIndex') not in (None, i) for i, p in enumerate(placements)):
            raise ValueError('Audio1 placement occurrences must be unique and explicit.')
        if len({(str(l.get('speaker')), str(l.get('exactText'))) for l in lines}) != len(lines):
            raise ValueError('Repeated dialogue needs explicit Audio1 occurrence IDs.')
    def occurrence_key(index, line):
        return line.get('dialogueOccurrenceId') or f'{shot.get("shotId")}.dialogue.{index + 1}'
    prior = {p.get('dialogueOccurrenceId'):p for p in (result.get('approvedAudioTimingAuthority') or {}).get('intervals', [])}
    changes = []
    for index, line in enumerate(lines):
        placement = by_id.get(line.get('dialogueOccurrenceId')) if by_id else placements[index]
        if placement is None:
            raise ValueError('Approved Audio1 has no placement for dialogue occurrence ' + str(line.get('dialogueOccurrenceId')))
        start, end = float(placement['targetStartSec']), float(placement['targetEndSec'])
        if not 0 <= start < end <= float(shot['durationSec']):
            raise ValueError('Approved dialogue falls outside the current shot duration.')
        key = occurrence_key(index, line)
        changes.append({'dialogueOccurrenceId': key,
                        'estimated': prior.get(key, {}).get('estimated', {'startSec':line.get('startSec'),'endSec':line.get('endSec')}),
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
        event['dialogueOccurrenceId'] = occurrence_key(result['dialogueLines'].index(line), line)
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
    result['approvedAudioTimingAuthority']['directProjection'] = {
        'originalSourceHash': original_source, 'originalDirectionHash': original_card,
        'projectedSourceHash': direct_digest(direct_source(result)),
        'projectedDirectionHash': direct_digest(result.get('directorCard') or {}),
        'kind': 'verified Audio1 timing projection; not direction approval'}
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
