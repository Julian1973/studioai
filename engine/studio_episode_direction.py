"""Shared episode treatment, not a new production stage or approval authority."""
from copy import deepcopy
import json

from pydantic import BaseModel, ConfigDict, Field


class VisualLanguage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cameraAndDistance: str = Field(min_length=1)
    movementAndStillness: str = Field(min_length=1)
    lightAndColour: str = Field(min_length=1)
    stagingAndPerformance: str = Field(min_length=1)
    editingAndRhythm: str = Field(min_length=1)
    transitionsAndMotifs: str = Field(min_length=1)


CONTRACT = '''EPISODE DIRECTOR'S TREATMENT. Read the whole supplied screenplay before
directing individual scenes. Author visualLanguage as this episode's coherent camera,
light, performance and edit approach, grounded in the project's medium and show bible.
Describe how distance, movement or stillness, colour/light, blocking, rhythm and recurring
images develop across the actual story. Name scene IDs when a deliberate contrast or
transition matters. A held wide may be more expressive than a push-in; choose by audience
experience, not a technique quota or lens/emotion formula. Establish geography only when
needed. Plan performance and the edit before provider packing. Protect thought before
speech, readable contact, listening and the emotional landing where the script earns them.
Use the existing storyArchitecture for sequence objectives, setup/payoff and the ending.
Do not invent events, dialogue, assets, soundtrack or emotional recovery to complete a
treatment. Animation uses character-specific weight and silhouette; live action uses
playable objectives and physical staging within that project's own visual language.
Scene direction translates this treatment into concrete views, action, performance,
lighting and cut decisions. It must not paste a general treatment into every provider
prompt or let an attractive local shot reveal information before its scripted moment.
Develop before audio exists, label timing estimates, then reconcile with measured approved
audio before production. This is creative context, never media approval or permission to
regenerate approved work. Review the resulting scene, not a self-assigned quality score.'''


def context(vision):
    """Lossless creative fields only; exclude audit/source payloads, never slice JSON.

    Keep the whole sequence blueprint so later payoffs and neighbouring scenes remain
    visible. Historical records need no migration and missing fields remain missing.
    """
    keys = ('premise', 'dramaticQuestion', 'theme', 'externalJourney', 'internalJourney',
            'relationshipChanges', 'emotionalCurve', 'comedyCurve', 'setupPayoffMap',
            'visualMotifs', 'sonicMotifs', 'climax', 'resolution', 'intendedFinalFeeling',
            'storyArchitecture', 'visualLanguage', 'emotionalThesis', 'audiencePromise')
    return {key: deepcopy(vision[key]) for key in keys if vision.get(key) is not None}


def prompt_context(vision):
    return json.dumps(context(vision), ensure_ascii=False)
