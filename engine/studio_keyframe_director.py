"""SEE action readiness, distinct from WATCH audiovisual coherence.
Shares reference-role authority; requires actual candidate pixels for recognition.
"""
from copy import deepcopy
from typing import Literal
from pydantic import BaseModel, Field
from studio_prompt_director import resolve_references
from studio_request_evidence import digest

VERSION='keyframe-director-1.1'
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
is separate. No speech edits. Do not enforce identical composition across camera cuts.'''

def snapshot(shot, direction, candidate, references):
    from studio_dynamic_state import resolve
    dynamic = resolve({'shot': shot}, references)
    return dict(dynamicStateResolution=dynamic,version=VERSION,shot=deepcopy(shot),direction=deepcopy(direction),
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
