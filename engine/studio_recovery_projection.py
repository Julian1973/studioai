"""Evidence-only recovery classification. No provider, reservation or approval operations."""
import re

RULES = (
 ('DIALOGUE_OCCURRENCE_SET_MISMATCH','STALE_DEPENDENCY','The downstream dialogue occurrence contract does not preserve the approved assignment.','Inspect missing, extra, duplicate, speaker and exact-text mismatches; repair the contract without guessing words.'),
 ('BIG_COMEDY_STAGING_CARRIER_AMBIGUOUS','NEEDS_DIRECTOR_DECISION','The physical payoff has no unique production-unit carrier.','Review the explicit beat-to-unit payoff assignment.'),
 ('COMEDY CARRIER','NEEDS_DIRECTOR_DECISION','The payoff assignment conflicts with the unit contract.','Review the beat-to-unit payoff assignment.'),
 ('POWER CONTRACT UNKNOWN BEARER','NEEDS_DIRECTOR_DECISION','Power bearer must be one participating character.','Choose the power bearer; keep supporting characters in staging.'),
 ('preceding scene viewId','MISSING_UPSTREAM_STATE','The allocated coverage references no resolved preceding view.','Inspect the allocator’s required view ID and approved coverage.'),
 ('CHARACTER TRUTH','AUTO_FIXABLE','The returned acting contract is incomplete.','Prepare a bounded Director correction; paid text work requires authorisation.'),
 ('DIALOGUE ASSIGNMENT DROPPED DUPLICATED REORDERED','STALE_DEPENDENCY','Dialogue occurrences were dropped, duplicated or reordered.','Repair the exact occurrence assignments against the current dialogue contract; preserve approved words.'),
 ('DIALOGUE ASSIGNMENT UNKNOWN','STALE_DEPENDENCY','A dialogue assignment names an unknown occurrence.','Bind assignments to exact current DialogueOccurrence IDs.'),
 ('DIALOGUE TIMING CONTRACT MISMATCH','STALE_DEPENDENCY','Dialogue timing and occurrence assignments disagree.','Align timing IDs with the exact assigned DialogueOccurrence IDs.'),
 ('DIALOGUE OCCURRENCE MISSING','STALE_DEPENDENCY','A required dialogue occurrence is missing.','Restore the required occurrence from the current dialogue contract.'),
 ('STALE','STALE_DEPENDENCY','An input no longer matches its recorded dependency.','Review the changed input and refresh affected evidence.'),
 ('APITimeoutError','PROVIDER_FAILURE','The text provider response timed out; acceptance and cost may be unknown.','Inspect the original text attempt before authorising another call.'),
)

def _normalise(value):
    # Match spellings only; never replace the preserved source text.
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value))
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


def _classify(value):
    normal = _normalise(value)
    for token, category, cause, action in RULES:
        if _normalise(token) in normal:
            return re.sub(r'[^A-Z0-9]+', '_', token.upper()).strip('_'), category, cause, action
    # Both compact DialogueOccurrence and spaced/underscored contract labels occur.
    if ('DIALOGUE_OCCURRENCE' in normal and
            any(word in normal.split('_') for word in ('MISSING', 'DROPPED', 'DUPLICATED', 'REORDERED'))):
        return ('DIALOGUE_OCCURRENCE_MISSING', 'STALE_DEPENDENCY',
                'Required dialogue occurrences are missing or inconsistent.',
                'Repair exact occurrence assignments against the current dialogue contract; preserve approved words.')
    from studio_producer_language import translate
    reading = translate(value)
    if reading['category'] != 'support':
        category = {'direction': 'NEEDS_DIRECTOR_DECISION', 'audio': 'NEEDS_DIRECTOR_DECISION',
                    'references': 'MISSING_UPSTREAM_STATE', 'request': 'STALE_DEPENDENCY',
                    'money': 'NEEDS_APPROVAL', 'provider': 'PROVIDER_FAILURE',
                    'images': 'MISSING_UPSTREAM_STATE', 'stale': 'STALE_DEPENDENCY',
                    'setup': 'CONFIGURATION'}.get(reading['category'], 'NEEDS_DIRECTOR_DECISION')
        return (reading.get('code') or reading['category'].upper(), category,
                reading['headline'], reading['nextAction'])
    return ('UNKNOWN', 'UNKNOWN', 'The recorded cause is not classified.',
            'Open the recorded evidence for diagnosis.')


def _failure_evidence(raw):
    lines = str(raw).splitlines()
    # Python chained tracebacks end in the active terminal exception. Do not
    # classify quoted traceback source, model receipts or earlier retries instead.
    exceptions = [(i, line) for i, line in enumerate(lines)
                  if re.match(r'^[\w.]+(?:Error|Exception|Refused):', line)]
    if exceptions:
        index, terminal = exceptions[-1]
    else:
        meaningful = [(i, line) for i, line in enumerate(lines)
                      if line.strip() and not re.match(r'^\s*(?:logged \$|DIRECTION_HANDOFF )', line)]
        index, terminal = meaningful[-1] if meaningful else (-1, '')
    earlier = []
    for i, line in enumerate(lines[:index]):
        if (i, line) in exceptions or (not line.startswith(('    ', 'DIRECTION_HANDOFF ')) and
                                      _classify(line)[0] != 'UNKNOWN'):
            earlier.append({'rawError': line, 'errorCode': _classify(line)[0],
                            'classification': _classify(line)[1]})
    return terminal, earlier


def project(*, stage, scene_id, message, attempt_id=None, request_hash=None,
            evidence_ref=None, provider_submitted=None, spend_occurred=None,
            approval_changed=None, text_cost=None, media_cost=None,
            media_failed=False, replay_safe=False):
    raw = str(message)
    terminal, earlier = _failure_evidence(raw)
    code, classification, cause, action = _classify(terminal)
    retry = 'RERUN_PROTECTION_ONLY'
    if provider_submitted is True and media_failed is True and replay_safe is True:
        retry = 'EXPLICIT_GENERATION_RETRY'
    return dict(status='BLOCKED',stage=stage,sceneId=scene_id,errorCode=code,
        classification=classification,primaryCause=cause,technicalDetails=raw,
        rawError=raw,terminalFailure=terminal,contributingEarlierFailures=earlier,
        safeNextAction=action,retryPolicy=retry,providerSubmitted=provider_submitted,
        spendOccurred=spend_occurred,approvalChanged=approval_changed,
        attemptId=attempt_id,requestHash=request_hash,evidenceRef=evidence_ref,
        textOperationCost=text_cost,mediaOperationCost=media_cost,
        protectionCost=0,modelCorrection='Separate paid text operation; authorisation required')

def from_job(job):
    args=job.get('args') or []
    direction=bool(args and str(args[0]).endswith('cb_creative.py'))
    log=str(job.get('log') or job.get('step') or '')
    amounts=[float(x) for x in re.findall(r'logged \$([0-9]+\.[0-9]+)',log)]
    return project(stage='SCENE_DIRECTION_POPULATION' if direction else job.get('gate','UNKNOWN'),
        scene_id=job.get('scene'),message=log,attempt_id=job.get('jobId'),
        request_hash=job.get('requestHash'),evidence_ref=job.get('jobId'),
        provider_submitted=False if direction else None,
        spend_occurred=True if amounts else None,
        text_cost={'recordedUsd':sum(amounts),'complete':False} if amounts else None,
        media_cost=0 if direction else None)

def validate_saved_direction(board, recovery):
    """Free protection never fills missing direction or starts an AI repair."""
    result=dict(recovery)
    if not board:
        result['safeNextAction']='No saved direction is available. Open the failed Director attempt; a correction is paid text work.'
        return result
    import cb_handover
    try:
        cb_handover._validate_supervision_contracts(board)
        if board.get('escalation'):
            result.update(classification='NEEDS_DIRECTOR_DECISION',primaryCause=str(board['escalation']),
                safeNextAction='Review the unresolved Showrunner direction.')
        else:
            result.update(status='PROTECTION_CHECKED',safeNextAction='Review saved direction and its source lineage before handover.',
                          primaryCause='Saved supervision contracts passed; this does not approve the scene.')
    except (ValueError,RuntimeError) as exc:
        failure=project(stage=result['stage'],scene_id=result['sceneId'],message=str(exc))
        earlier=list(result.get('contributingEarlierFailures') or [])
        if result.get('terminalFailure'):
            earlier.append({'rawError':result['terminalFailure'], 'errorCode':result['errorCode'],
                            'classification':result['classification']})
        result.update({key:failure[key] for key in ('status','errorCode','classification',
                      'primaryCause','safeNextAction','terminalFailure')})
        result['contributingEarlierFailures']=earlier
    return result


def from_journey(view):
    op=view.get('operation') or {}
    decision=op.get('decision') or {}
    review=view.get('review') or {}
    result=project(stage=op.get('pending') or view.get('phase'),scene_id=view['scope']['scene'],
        message=decision.get('issue') or view.get('dependency') or 'No stopped operation recorded.',
        attempt_id=op.get('id'),request_hash=(op.get('receipts',{}).get('prepare_render') or {}).get('envelopeHash'),
        evidence_ref=decision.get('evidence'))
    if not decision and not view.get('dependency'):
        result.update(status='CURRENT_OWNER_EVIDENCE',primaryCause='Current production-owner evidence is available.',safeNextAction=view.get('primary') or 'Review the current outcome.')
    result['ownerEvidence']={'see':review.get('seeCurrent'),'audio':review.get('audioCurrent'),
                            'costIssue':review.get('costIssue')}
    return result


def persist_check(root,result):
    """Save validation evidence only; never rewrite direction, approval or media."""
    from pathlib import Path
    from studio_shot_request import digest
    import cb_db
    report={**result,'checkProviderCalled':False,'checkSpendReserved':False,'checkApprovalChanged':False}
    path=Path(root)/'cb-output/evidence/protection'/f'{digest(report)}.json'
    cb_db.atomic_write_json(Path(root),path,report)
    return {**report,'evidenceRef':str(path),'originatingEvidenceRef':result.get('evidenceRef')}
