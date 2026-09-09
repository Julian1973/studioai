"""Authored shot sound intent and advisory join checks, never media approval."""
from pydantic import BaseModel, ConfigDict, Field


class SoundHandoff(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entry: str = ''
    exit: str = ''
    carrySound: str = ''
    entryEnergy: int | None = Field(default=None, ge=0, le=5)
    exitEnergy: int | None = Field(default=None, ge=0, le=5)
    intentionalContrast: str = ''


def sound_instruction(value=None, *, continuation=False, exact_audio=False):
    if exact_audio:
        return 'Retain the complete approved audio bed and its timing; add no new sound or musical transition.'
    direction = SoundHandoff.model_validate(value or {}).model_dump()
    parts = ['Shape the permitted soundtrack as part of the surrounding scene, preserving dialogue and action timing.']
    if continuation:
        parts.append('Carry the established ambience and musical energy into the pickup; do not restart the cue merely because this is a new generation.')
    parts.append('Give the ending an intentional sound handoff. Avoid an unrequested closing crescendo followed by a fresh loud entrance; preserve a story-motivated accent when directed. Do not invent a fixed pause or stretch the performance.')
    for field, label in [('entry', 'Sound entrance'), ('exit', 'Sound exit'), ('carrySound', 'Carry sound'), ('intentionalContrast', 'Intentional contrast')]:
        if direction[field]:
            parts.append(f'{label}: {direction[field]}')
    return '\n'.join(parts)


def join_advisories(previous, current):
    """Compare authored intent only; energy numbers do not measure rendered audio."""
    if not previous:
        return []
    outgoing = previous.get('soundHandoff') or {}
    incoming = current.get('soundHandoff') or {}
    a, b = outgoing.get('exitEnergy'), incoming.get('entryEnergy')
    if (isinstance(a, (int, float)) and isinstance(b, (int, float))
            and a >= 4 and b >= 4):
        intentional = incoming.get('intentionalContrast') or outgoing.get('intentionalContrast')
        return [{'code': 'music_join_review', 'severity': 'warning',
                 'message': ('Intentional high-energy join: audition both sides together. ' + str(intentional)
                             if intentional else 'Both sides are directed at high musical energy. Audition the join and shape the outgoing tail or incoming entrance.'),
                 'basis': 'authored intent, not measured sound', 'previousShotId': previous.get('id') or previous.get('shotId')}]
    return []


POST_JOIN_REVIEW = (
    'Review each outgoing ending and incoming opening together in motion with the complete soundtrack. '
    'Check pickup action, eyelines, geography, camera movement, repeated action, musical energy, phrase endings, ambience and dialogue masking. '
    'Keep the selected approved soundtrack and timed performance. Treat embedded dialogue/music/effects as one mix unless genuine stems exist; '
    'separated stems are provisional and require audition. Do not replace Seedance music merely because it is generated. '
    'Choose a motivated tail, shared bed, delayed entrance, silence or deliberate contrast. No blanket fades or compulsory quiet window. '
    'Use overlap handles only when actual matching action and usable sound exist; a handle does not prove continuity. '
    'Record source outcome IDs/hashes, inspected ranges, actual findings and unresolved work. Uninspected joins remain unverified, never automatically approved.'
)
