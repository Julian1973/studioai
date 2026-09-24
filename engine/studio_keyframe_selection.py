"""Keep a selected external image separate from a former generated comparison."""
def can_reuse_prompt_change(candidate, expected, actual_hash):
    """Only explicit reuse of intact, screened media with unchanged visual inputs."""
    recorded = candidate.get('inputSignature') or {}
    return bool(candidate.get('source', 'generated') == 'generated'
                and actual_hash and candidate.get('contentHash') == actual_hash
                and (candidate.get('conformanceScreening') or {}).get('status') == 'pass'
                and recorded and expected
                and {k for k in set(recorded) | set(expected)
                     if recorded.get(k) != expected.get(k)} == {'briefHash'})


def retire_comparison(ledger, *, source, at, reviewer):
    if source not in ('uploaded', 'library', 'previousFinalFrame'):
        return False
    rows = ledger.get('keyframeCandidates') or []
    if not rows and not ledger.get('selectedKeyframeCandidateId'):
        return False
    for row in rows:
        ledger.setdefault('keyframeHistory', []).append({**row,
            'outcome': 'superseded-by-source-selection', 'supersededAt': at,
            'supersededBy': source, 'reviewedBy': reviewer})
    ledger.pop('keyframeCandidates', None)
    ledger.pop('selectedKeyframeCandidateId', None)
    return True
