"""Shared scene-plate authority for still direction, emission and review."""
VERSION = 'scene-plate-authority-1.0'
REVIEW_RULE = '''The approved scene plate is the actual set, not a mood board. Compare
fixed landmark relationships, furniture, structural props, terrain and paths, materials,
scale and lighting against the supplied plate. A similar-looking substitute location
is not compliant. For a scene opening retain plate framing and perspective unless
an explicitly authored coverage/camera change requires a new view. For a new view,
preserve world-space geography; do not demand identical screen coordinates or invent
unseen set details as verified. Current approved story state overrides historical
movable prop positions, effects and weather; never restore removed objects to match
the plate. BLOCK observed set substitutions or unexplained layout changes. Mark
required but unjudgeable set fidelity UNVERIFIED; never claim pixel-perfect fidelity.'''

def clause(slot, shot):
    transition = (shot.get('shotTransition') or {}).get('type')
    camera = ('Reframe only for the authored camera view; preserve world-space landmark '
              'relationships, paths and distances, never mirror or redesign the set.'
              if transition in ('cut', 'continuation') else
              'Use this plate as the opening background, preserving its framing and perspective '
              'unless the approved camera plan explicitly requires reframing the same set.')
    return (f'{slot}: exact approved location authority, not a style or mood reference. '
            'Preserve the existing terrain, fixed landmarks, furniture, structural props, '
            'materials, scale and lighting. '+camera+' Integrate characters with correct '
            'contact, occlusion and shadows. Only current approved story-state changes may '
            'alter movable props, effects or weather; never restore a removed object. '
            'Do not substitute a similar location or add a second table or duplicate set pieces.')
