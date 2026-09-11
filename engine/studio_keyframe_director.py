"""SEE action readiness, distinct from WATCH audiovisual coherence.
Shares reference-role authority; requires actual candidate pixels for recognition.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, Field
from studio_prompt_director import resolve_references
from studio_request_evidence import digest

VERSION='keyframe-director-1.4'
class Assessment(BaseModel):
    verdict: Literal['READY','BLOCKED','UNVERIFIED']
    summary: str
    camera: str
    geography: str
    pose: str
    propsEffects: str
    actionFeasibility: str
    findings: list[str] = Field(default_factory=list)
    correctiveAction: str

SYSTEM='''You are the SEE Keyframe Director. Assess the ACTUAL first image against the
planned opening state and action, not continuous audiovisual storytelling. Remaining
images have the declared scoped reference authority. Can the camera see the planned
cause, do geography/distance and paths support the action, are poses mechanically
possible, are props/effects in their required starting state? Never assume the image
matches its prompt. Return UNVERIFIED when evidence is insufficient. Human approval
is separate. No speech edits. Do not enforce identical composition across camera cuts.
Review observed opening suitability, not proof that a future generated action succeeds.
An opening image need not already depict later contact, detachment, travel or a landing,
nor prove invisible internal forces. Keep those declared intentions distinct from
observed pixels: state that limitation in propsEffects/actionFeasibility. Do not mark
an otherwise supported opening UNVERIFIED solely because a later event has not happened
or hidden mechanics cannot be measured in a still. Later planned views may reveal the
cause; they need not all be visible from the opening camera. Conversely, BLOCK visible
contradictions or an opening that prevents the required action, and use UNVERIFIED
when a necessary visible opening fact (identity, pose, prop state, scale, clearance or
geography) cannot be judged. READY means supported opening, never proven future motion.'''

from studio_scene_plate_authority import REVIEW_RULE
SYSTEM += "\n" + REVIEW_RULE

def snapshot(shot, direction, candidate, references):
    from studio_dynamic_state import resolve
    # The reviewed image is the opening authority. Generation references have
    # their own stage slots and must not inherit the opening image's evidence.
    dynamic = resolve({'shot': shot}, [dict(candidate, role='opening keyframe'), *references])
    return dict(dynamicStateResolution=dynamic,version=VERSION,
                reviewScope={'observed': 'actual opening image suitability',
                    'planned': 'later views and action are intentions, not observed outcomes',
                    'limitations': 'hidden mechanics and future contact remain unverified by a still'},
                shot=deepcopy(shot),direction=deepcopy(direction),
                candidate=deepcopy(candidate),references=resolve_references(references,[]))

def assess(source, reviewer):
    result=Assessment.model_validate(reviewer(SYSTEM,deepcopy(source))).model_dump()
    return dict(**result,version=VERSION,inputHash=digest(source),scope='opening-image action readiness',
                approval='not-granted',recognition='reviewer assessment; not proof of semantic accuracy')

def require(source, report):
    if not report or report.get('version')!=VERSION or report.get('inputHash')!=digest(source):
        raise ValueError('SEE action readiness is missing or stale; review the current opening image and action.')
    if report['verdict']!='READY':
        raise ValueError('SEE action readiness '+report['verdict']+': '+report['summary']+' — '+report['correctiveAction'])
    errors = (source.get('dynamicStateResolution') or {}).get('errors') or []
    if errors:
        raise ValueError('SEE action readiness needs current state: ' + '; '.join(errors))


def recovery_ready(runtime, pkg, shot, ledger, scene, episode, *, spend_token=None, protected_comparison=False):
    """A declared requalification hold can progress through existing reviews.

    This never clears an unrelated hold, grants media approval, calls a provider,
    or permits submission without the normal spend/lineage checks.
    """
    block = ledger.get('productionBlock') or shot.get('productionBlock') or {}
    if block.get('kind') != 'review-requalification':
        return False
    if set(block.get('requiredReviews') or []) != {'see-action-readiness', 'watch-coherence'}:
        return False
    opening = (ledger.get('keyframeApproval') or {}).get('path') or ledger.get('keyframePath')
    if not opening:
        return False
    try:
        current = runtime._see_readiness_source(pkg, shot, ledger, opening, scene, episode)
        require(current, ledger.get('seeActionReadiness'))
        if spend_token:
            from studio_prompt_director import verify_legacy_envelope
            pending = ledger.get('pendingComparisonSpendAuth' if protected_comparison else 'pendingSpendAuth') or {}
            envelope = pending.get('envelope') or {}
            segments = (envelope.get('executionPlan') or {}).get('segments') or []
            if not segments:
                return False
            verify_legacy_envelope(envelope)
    except (ValueError, KeyError, TypeError, OSError):
        return False
    return True
