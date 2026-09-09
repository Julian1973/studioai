"""Provider-independent timing invariants for every production route."""
import math


def require_aligned_timing(shot_duration, *, direction_duration=None, audio_duration=None):
    duration = float(shot_duration)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Shot duration must be a positive finite number.')
    if direction_duration is not None and abs(float(direction_duration) - duration) > .02:
        raise ValueError('Shot card and animation direction have different durations. Revise the shot before preparing delivery.')
    if audio_duration is not None:
        audio = float(audio_duration)
        if not math.isfinite(audio) or audio <= 0:
            raise ValueError('The approved HEAR duration could not be verified.')
        if audio > duration + .02:
            raise ValueError('Approved HEAR exceeds the shot duration. Update the upstream shot timing and recompile before Fire; audio will not be cropped or squeezed.')
    return duration


def delivery_snapshot(metadata, direction, prompt, body, resolution=None):
    """Immutable-by-hash submission projection, never a new authorable story record."""
    import hashlib
    import json
    from studio_director_card import REVIEW_CRITERIA
    data = {'schemaVersion': '1.0.0', 'operation': 'compiled-submission-snapshot',
            'sourceBindings': metadata, 'direction': direction,
            'compiledPrompt': prompt, 'providerBody': body,
            'instructionResolution': resolution or {'status': 'legacy-prose-unclassified'},
            'reviewCriteria': REVIEW_CRITERIA,
            'reviewStatus': 'not-reviewed', 'approvalStatus': 'not-granted-by-compilation',
            'deliveryEligibility': 'pending-media-and-scoped-review',
            'cost': {'estimate': metadata.get('estimatedCost'),
                     'authorisedCeiling': metadata.get('authorisedCostCeiling'),
                     'actual': None, 'actualStatus': 'unknown-until-billing-evidence'}}
    data['fingerprint'] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                                  allow_nan=False).encode()).hexdigest()
    return data
