"""Final creative handoff: revise typed direction before the provider compiler.

No media generation or approval. Existing validators remain authoritative.
"""
import hashlib
import json
import os
import cb_llm

VERSION = 'final-direction-1.1.0'

def model_options():
    return {'model': os.environ.get('OPENAI_STUDIO_AGENT_MODEL', 'gpt-6-astra'),
            'reasoning_effort': os.environ.get('OPENAI_STUDIO_AGENT_REASONING', 'high'),
            'max_output_tokens': 10000}

def prompt_director_options():
    """Independent final WATCH review route; does not change SEE/HEAR directors."""
    return {'model': os.environ.get('OPENAI_PROMPT_DIRECTOR_MODEL', 'gpt-5.6-sol'),
            'reasoning_effort': os.environ.get('OPENAI_PROMPT_DIRECTOR_REASONING', 'low'),
            'max_output_tokens': 10000}

SYSTEM = '''You are the final production Director. Refine the supplied typed specialist direction against the current director storyboard, approved coverage, shot purpose, current references and latest user direction. Return the complete same schema, ready for the actual provider compiler. Make the smallest necessary revision; preserve successful direction. Do not invent story beats, change dialogue, timing, identities, reference assignments or approved assets. Translate audience purpose into readable physical acting and motivated camera choices. Correct contradictions instead of appending competing instructions. SEE: establish only the opening instant with visible action-to-prop contact, support surface, playable pose, geography and camera; do not depict later action. HEAR: acting must reach takeRecipes.performedText through allowed v3 tags and punctuation, not remain in prose metadata. Copy explicit performanceOverride verbatim. Keep every word, speaker, occurrence and voice identity. Do not claim listening to audio or watching video: only supplied images can be visually inspected. This review improves direction; it cannot guarantee the generated performance lands.'''

def finalize(stage, result, context, images=None, log=print):
    from studio_scene_plate_authority import REVIEW_RULE
    before = result.model_dump()
    system = SYSTEM + ('\n' + REVIEW_RULE if stage == 'cinematography' else '')
    payload = {'stage':stage, 'currentProduction':context, 'specialistDraft':before}
    revised = cb_llm.structured(system, json.dumps(payload,ensure_ascii=False,default=str),
        type(result), images=images or None, label='final_director_'+stage,
        log=log, **model_options())
    after = revised.model_dump()
    locks = ['shotId']
    if stage == 'cinematography':
        locks += ['charactersInFrame','canonicalStyleVersion','canonicalStyleParagraph']
        if (context.get('shot') or {}).get('authoredOpeningFrameLayout'):
            locks += ['openingFrameLayout']
    for field in locks:
        if after.get(field) != before.get(field):
            raise ValueError('Final Director changed protected '+field)
    if stage == 'voice':
        old_lines, new_lines = before.get('lines', []), after.get('lines', [])
        if len(old_lines) != len(new_lines):
            raise ValueError('Final Director changed dialogue count')
        for old, new in zip(old_lines, new_lines):
            for field in ('exactDialogue','speaker','character','dialogueOccurrenceId',
                          'sourceEventId','startsAtSec','estimatedDurationSec','voiceId'):
                if old.get(field) != new.get(field):
                    raise ValueError('Final Director changed protected voice '+field)
    sha=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
    return revised, {'version':VERSION,'model':model_options()['model'],
        'reasoning':model_options()['reasoning_effort'],'inputHash':sha(payload),
        'outputHash':sha(after),'changed':before!=after,'mediaGenerated':False}
