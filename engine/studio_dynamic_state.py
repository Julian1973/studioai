"""Derived intended-state view of Director Card events, never an observed-state store.
No image recognition: depictedStates must come from separately recorded evidence.
Unknown image contents remain unknown. Reference order/tags are never silently changed.
"""
from copy import deepcopy
import json
import math
import re
from studio_request_evidence import digest

VERSION='dynamic-state-1.1'
RESET={'time_jump','new_location','independent','flashback','dream','explicit_reset'}

def bound_metadata(binding, content_hash):
    """Only file-bound observations describe pixels; scope alone describes intent."""
    binding = binding or {}
    out = {}
    if binding.get('stateScope'):
        out['stateScope'] = deepcopy(binding['stateScope'])
    if content_hash and binding.get('stateEvidenceHash') == content_hash:
        out.update(depictedStates=deepcopy(binding.get('depictedStates') or {}), stateEvidenceHash=content_hash)
    return out

def scope(ref):
    declared=ref.get('stateScope')
    if declared:return deepcopy(declared)
    role=str(ref.get('role',ref.get('name',''))).lower()
    kind=('fixed_geography' if 'plate' in role or 'location' in role else
          'identity_only' if any(x in role for x in ('character','turnaround','prop','identity')) else
          'opening_state' if 'opening' in role else
          'current_motion_evidence' if 'video' in role else 'historical_context')
    return dict(authority=kind,storyTime='opening' if kind=='opening_state' else 'unspecified',
                controlsDynamicState=kind=='opening_state',startSec=0,endSec=0 if kind=='opening_state' else None)


def _start_time(record, path, repairs):
    """Use authored numeric intervals only. Never derive timing from prose or order."""
    value = record.get('atSec')
    if value is not None:
        return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None
    timing = record.get('timing')
    if not isinstance(timing, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*[-–—]\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*", timing)
    if not match or float(match[1]) >= float(match[2]):
        return None
    value = float(match[1])
    repairs.append(dict(path=path + '/atSec', value=value,
                        source=path + '/timing', sourceValue=timing,
                        action='derive start from explicit authored interval'))
    return value

def resolve(authorities, references):
    shot=authorities.get('shot',authorities)
    card=shot.get('directorCard') or {}
    events=card.get('stateChanges',[])
    views=card.get('views',[])
    errors=[];unverified=[];history=[];initial={};repairs=[];incomplete=set()
    for index,e in enumerate(events):
        at = _start_time(e, f'directorCard/stateChanges/{index}', repairs)
        if at is None or not e.get('entityId') or not e.get('afterValues'):
            unverified.append(f'stateChanges/{index}: structured entity/time/state not available')
            incomplete.add(e.get('entityId'))
            continue
        entity=e['entityId']
        if not e.get('cause'):errors.append(entity+': change has no declared cause')
        if e.get('entityCount',1)!=1 and e.get('unique',True):errors.append(entity+': unique entity has conflicting count')
        history.append(dict(entity=entity,at=at,before=deepcopy(e.get('beforeValues') or {}),
                            after=deepcopy(e['afterValues']),cause=e.get('cause'),source=f'directorCard/stateChanges/{index}',
                            relationship=e.get('storyRelationship','continuous')))
    history.sort(key=lambda e:e['at'])
    for event in history:
        initial.setdefault(event['entity'], deepcopy(event['before']))
    resolved=[dict(deepcopy(r),stateScope=scope(r)) for r in references]
    checks=[];clauses=[]
    for index, v in enumerate(views):
        critical_entities = set(v.get('criticalStateEntities') or [])
        at = _start_time(v, f'directorCard/views/{index}', repairs)
        if at is None or v.get('visibleEntities') is None:
            reason = str(v.get('viewId'))+': visibility/time not declared'
            unverified.append(reason)
            if critical_entities:
                errors.append(reason + '; restore critical view timing/visibility from approved direction and review again')
            continue
        if critical_entities - set(v['visibleEntities']):
            errors.append(v['viewId']+': critical entities missing from declared view visibility')
        if critical_entities.intersection(incomplete) or (critical_entities and None in incomplete):
            errors.append(v['viewId']+': critical state change has incomplete entity/time/state; repair source and review again')
        state=deepcopy(initial); seen=set(); relationship=v.get('storyRelationship') or card.get('storyTime','next_beat')
        if relationship in RESET:
            state=deepcopy(v.get('stateAtEntry') or {})
            if not state:unverified.append(v['viewId']+': new story relationship needs explicit entry state')
        else:
            for e in history:
                if e['at']>at:break
                current=state.setdefault(e['entity'],{})
                if e['relationship'] in RESET:current.clear()
                elif any(k in current and current[k]!=val for k,val in e['before'].items()):
                    errors.append(e['entity']+': event before-state disagrees with carried state')
                current.update(e['after']);seen.add(e['entity'])
        for entity in v['visibleEntities']:
            required=state.get(entity)
            if required is None:
                if entity in v.get('criticalStateEntities', []):
                    errors.append(v['viewId']+'/'+entity+': critical entry state unavailable')
                unverified.append(v['viewId']+'/'+entity+': intended state unavailable');continue
            changed=entity in seen
            current_evidence=[];obsolete=[];unknown=[];conflicts=[];unknown_current=[]
            for n,ref in enumerate(resolved):
                sc=ref['stateScope'];depicted=(ref.get('depictedStates') or {}).get(entity)
                valid_time=sc.get('startSec',0)<=at and (sc.get('endSec') is None or at<=sc['endSec'])
                current=sc.get('controlsDynamicState') and sc.get('authority') in ('current_dynamic_state','current_motion_evidence','opening_state') and valid_time
                if depicted is None:
                    unknown.append(n+1)
                    if current: unknown_current.append(n+1)
                    continue
                matches=all(depicted.get(k)==val for k,val in required.items())
                if matches and current:current_evidence.append(n+1)
                elif not matches:
                    obsolete.append(n+1)
                    ref.setdefault('stateResolutions',[]).append(dict(viewId=v['viewId'],entity=entity,required=required,
                        depicted=depicted,action='re-scope to '+sc['authority'] if not current else 'conflicting current-state evidence'))
                    if current:
                        conflicts.append(n+1)
                        errors.append(v['viewId']+'/'+entity+': current-state reference contradicts required state')
            critical=entity in v.get('criticalStateEntities',[])
            # Authored future action is valid without a future image. Historical
            # and identity references cannot override it. Only a conflicting or
            # unverified reference claiming authority *at this time* is unresolved.
            risk=bool(conflicts or unknown_current)
            if critical and unknown_current:
                errors.append(v['viewId']+'/'+entity+': reference claims current-state authority without observed state evidence')
            if unknown:
                unverified.append(v['viewId']+'/'+entity+': reference contents unverified for slots '+','.join(map(str, unknown)))
            check=dict(viewId=v['viewId'],atSec=at,entity=entity,requiredState=required,revisit=changed,
                       obsoleteReferences=obsolete,currentStateEvidence=current_evidence,unknownReferences=unknown,
                       unresolvedResetRisk=risk,relationship=relationship,
                       stateAuthority='authored intent; not observed outcome',
                       resolution='unresolved current reference' if risk else 'authored state with scoped references')
            checks.append(check)
            if changed or relationship in RESET:
                clauses.append(v['viewId']+f' at {at:g}s: '+entity+' = '+json.dumps(required,sort_keys=True,ensure_ascii=False)+'.')
    if history and not checks:unverified.append('No timed visible view could be resolved')
    return dict(version=VERSION,sourceHash=digest(authorities),kind='intended; not observed or approved output',
                history=history,referencePackage=resolved,revisitChecks=checks,errors=list(dict.fromkeys(errors)),
                unverified=list(dict.fromkeys(unverified)),repairs=repairs,clauses=list(dict.fromkeys(clauses)),
                correctiveAction='; '.join(dict.fromkeys(errors)) if errors else None)
