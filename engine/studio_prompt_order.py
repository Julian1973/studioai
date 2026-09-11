"""Stable section ordering; never paraphrases dialogue or creative clauses."""
import re

def purpose_first(prompt):
    sections=[x for x in re.split(r'(?m)(?=^\[[^\n]+\]\s*$)',prompt) if x.strip()]
    def rank(section):
        heading=section.split('\n',1)[0].strip().lower()
        if 'audience purpose' in heading or heading == '[purpose]':return -1
        if heading == '[story beat]':return 0
        if heading in ('[opening state]', '[causality]', '[continuity out]', '[must preserve]'):return 2
        if any(x in heading for x in ('generation goal','audience purpose','video goal','video purpose','one-sentence summary','extension goal')):return 0
        if any(x in heading for x in ('opening motion bridge','shot sequence','timed action','stage sequence','camera consciousness','living performance','coverage staging','action ownership','directed nonverbal','directed beats and acting','director decisions')):return 1
        if any(x in heading for x in ('reference','environment','continuity','attribute ownership','global settings','locked character')):return 2
        return 3
    return '\n\n'.join(x.strip() for x in sorted(sections,key=rank))


def compile_order(prompt, direction):
    if '[Audience Purpose]' not in prompt and '[PURPOSE]' not in prompt:
        values=[str(direction.get(k) or '').strip() for k in ('dramaticBeat','audienceBefore','audienceAfter')]
        purpose='\n'.join(f'{label}: {value}' for label,value in zip(('Story beat','Audience before','Audience after'),values) if value)
        if purpose:prompt='[Audience Purpose]\n'+purpose+'\n\n'+prompt
    return purpose_first(prompt)
