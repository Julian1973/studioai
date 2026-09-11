"""Keep a selected external image separate from a former generated comparison."""
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
