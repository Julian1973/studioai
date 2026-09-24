"""Shared writing guidance from sd25-pe 0.3.3; not another approval gate."""
WRITING_BRIEF = '''Write a concise shooting script, not a production-policy document.
Start with the audience purpose. Describe successive views through visible action,
acting, camera choice and the resulting state. Each stage has one primary change;
reaction and listening remain active performances. Cut when the audience needs to
read a new thought, relationship or consequence; an opening keyframe does not lock
the entire clip to one angle. Preserve geography, scale and state across the cut.
Bind each active reference to one explicit role. A prior final frame supplies
incoming state, not the new opening camera; a scene plate supplies fixed geography,
not permanent placement of a movable prop. A storyboard supplies panel order and
approximate composition, not its annotations, line art or placeholder identities.
Keep exact approved Audio1 words, speaker ownership and measured timings unchanged.
Do not invent numeric timings from target duration. Put provider duration, aspect
ratio and resolution in settings. Include only exclusions needed for this shot.
Do not repeat the same rule in several sections, dump internal registries, add
unrelated show laws, or replace an ambiguous story with contradictory instructions.
Make emotion playable: name its trigger, the visible response and the resulting
change, not a pile of micro-expressions. Show the cause before its reaction unless
the approved edit deliberately withholds it. A camera move names its subject,
starting position, trigger and finish; a focus shift names both focal targets.
An insert makes contact, weight and prop ownership readable without adding business.
Reserve authored time for the decisive reaction; do not make every line a cut or
force a camera move where a living hold carries the performance. Slow motion must
not silently stretch approved speech. Keep the final state usable for the next edit.
Use the project's own visual language. Labels such as Pixar-quality, best-in-class
or cinematic do not replace staging, light, material response or acting decisions.
Word budgets are ceilings and diagnostics, never targets to pad toward. Keep all
unique story and performance instructions; remove only actual redundancy. When a
plan is too dense to play, return the specific source decision for revision rather
than dropping a beat or compressing approved dialogue to fit.
If sources conflict, identify the source correction; do not silently alter the story.
The final compiler owns provider emission. No text is appended after final review.'''


def prose(value, label=''):
    """Lossless leaf rendering for authored directions; no JSON ledger in prompts."""
    import re
    if value is None or value == '' or value == [] or value == {}:
        return ''
    if isinstance(value, dict):
        return '\n'.join(filter(None, (prose(v, ' '.join(filter(None, [label,
            re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', k)]))) for k,v in value.items())))
    if isinstance(value, (list,tuple)):
        return '\n'.join(filter(None, (prose(v,label) for v in value)))
    return (label + ': ' if label else '') + str(value)
