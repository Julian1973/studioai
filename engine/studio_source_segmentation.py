"""Source-bound segmentation projections. No model calls, guessing or persistence."""
from copy import deepcopy
import hashlib
import re
import studio_dialogue_occurrence as O

ERROR = 'SOURCE_DIALOGUE_SEGMENTATION_UNRESOLVED'

class SegmentationRequired(ValueError):
    pass

def _joined(value):
    return ' '.join(value.split())

def project(occurrence, script, *, boundary=None):
    """Read projection; boundary is trusted structural or human-reviewed evidence.

    Spans are half-open Unicode character offsets in the exact script revision.
    Nothing infers boundaries from English vocabulary or trimmed hash matches.
    """
    row=O.record(occurrence)
    raw=next((row[k] for k in ('rawSourceText','exactText','exactDialogue','text') if k in row), '')
    result={'occurrenceId':row.get('dialogueOccurrenceId'),'speaker':row.get('speaker'),
            'rawSourceText':raw,'spokenText':None,'actionBefore':None,'actionAfter':None,
            'sourceSpan':None,'scriptRevision':'sha256:'+hashlib.sha256(script.encode()).hexdigest(),
            'segmentationStatus':'UNVERIFIED'}
    if boundary is None:
        return result
    evidence=deepcopy(boundary)
    if (not result['occurrenceId'] or not result['speaker'] or evidence.get('scriptRevision')!=result['scriptRevision'] or
        evidence.get('occurrenceId')!=result['occurrenceId'] or
        evidence.get('speaker')!=result['speaker'] or
        evidence.get('authority') not in ('reviewed_source_boundaries','structural_line_types') or
        not evidence.get('evidenceId')):
        raise SegmentationRequired(ERROR+': segmentation evidence is not source-bound')
    cursor=None;parts={}
    for role in ('actionBefore','spokenText','actionAfter'):
        span=evidence.get('spans',{}).get(role)
        if span is None:continue
        if (not isinstance(span,list) or len(span)!=2 or any(type(x) is not int for x in span)
            or not 0<=span[0]<span[1]<=len(script)):
            raise SegmentationRequired(ERROR+': invalid source span')
        if cursor is not None and (span[0]<cursor or script[cursor:span[0]].strip()):
            raise SegmentationRequired(ERROR+': overlapping or omitted source text')
        parts[role]=_joined(script[span[0]:span[1]]);cursor=span[1]
    if not parts.get('spokenText') or _joined(' '.join(parts.values()))!=_joined(raw):
        raise SegmentationRequired(ERROR+': partition does not preserve raw source')
    result.update(parts,sourceSpan=deepcopy(evidence['spans']),segmentationStatus='VERIFIED',evidence=evidence)
    result['spokenTextHash']=hashlib.sha256(result['spokenText'].encode()).hexdigest()
    return result

def spoken(row):
    """Single consumer gate. Legacy source stays readable but cannot author new audio."""
    row=O.record(row);p=row.get('sourceSegmentation')
    if (not isinstance(p,dict) or p.get('segmentationStatus')!='VERIFIED' or
        not p.get('spokenText') or not p.get('speaker') or
        O.identity(p.get('occurrenceId'))!=O.identity(row.get('dialogueOccurrenceId')) or
        p.get('speaker')!=row.get('speaker',row.get('character')) or
        p.get('spokenTextHash')!=hashlib.sha256(p['spokenText'].encode()).hexdigest()):
        raise SegmentationRequired(ERROR+': verified spoken source required')
    raw=next((row[k] for k in ('scriptExactText','rawSourceText','exactText','exactDialogue','text') if k in row),None)
    if raw not in (p['rawSourceText'],p['spokenText']):
        raise SegmentationRequired(ERROR+': source payload changed')
    return p['spokenText']

def voice_projection(row):
    result=deepcopy(O.record(row));text=spoken(result)
    result['scriptExactText']=result['sourceSegmentation']['rawSourceText']
    for key in ('exactText','exactDialogue','text'):
        if key in result:result[key]=text
    return result
