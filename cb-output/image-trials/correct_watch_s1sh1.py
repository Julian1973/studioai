import sys,re,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'engine'))
import cb_render as R
p,_=R.load_pkg('1','Ep3');l=R._ledger(p,'S1.SH1');d=(l['departmentWork']['animation'].get('candidate') or l['departmentWork']['animation']['approved'])['output'];text=d['providerPrompt']
Path('cb-output/image-trials/Ep3_S1_SH1_watch_before_correction.txt').write_text(text)
def section(name,value):
 global text
 pattern=r'\['+re.escape(name)+r'\]\n.*?(?=\n\[|\Z)'
 text,count=re.subn(pattern,'['+name+']\n'+value+'\n',text,flags=re.S)
 assert count==1,(name,count)
section('One-Sentence Summary','Keen’s overconfident oversized-blueberry launch splats the meditating Zenny; Fuzzby wakes into ridiculous upside-down laughter, giving Keen the chance to snatch the honeycomb, before the catapult punishes Keen and collapses beneath his attempt to save face.')
text=re.sub(r'Geography: [^\n]+','Geography: Inherit the exact approved @图1 opening: Keen and loaded catapult on the near left bank; across the visible creek corridor, Fuzzby sleeps ON the hanging honeycomb at the back-right tree, with Zenny meditating ON the nearby leaf. Preserve that distance and those landmarks. The oversized blueberry is already seated in the rearward cup. Follow its flight toward the back tree; do not teleport bees into the foreground. Later Keen must visibly cross to the honeycomb to snatch it.',text)
section('Opening Motion Bridge','Begin on the exact approved opening, already cocked and aimed. Keen releases at once. Camera accelerates alongside the oversized blueberry over the creek toward the back tree and catches its splat on Zenny before her approved line begins at 1.1s. No fresh aiming pause or opening reset.')
section('Timed Action Phases — One Continuous Render','''One continuous render with motivated camera movement, preserving the approved audio timing.
Phase 1 (0–5.66s): Release immediately. Track the oversized blueberry across the established distance and land with the SPLAT on Zenny before 1.1s. Keen ducks behind cover in the near bank background. Fuzzby jolts awake ON the honeycomb, attempts a pompous upright pose, overbalances and tips upside down over its edge, gripping it with his feet; wings flutter uselessly as he bursts into excessive silent-to-dialogue-safe laughter. Zenny barely twitches, calmly licks the juice and delivers her approved line while Fuzzby keeps wobbling upside down. Zenny: {OK, Fuzzby, calm down. It’s not that funny.} Her mouth timing follows @Audio1 from 1.1 to 5.66s. The honeycomb stays attached and supports Fuzzby until Keen snatches it. Camera settles where Zenny’s face and Fuzzby’s foolishness read together.
Phase 2 (5.66–16.5s): Fuzzby struggles back onto the honeycomb, laughing so hard he misses Keen approaching. Visibly track Keen’s hurried approach across the established distance. Keen: {Uh-oh—} at the approved 7.9–9.02s. He snatches the honeycomb; Fuzzby drops with BUZZ-CRASH, harmlessly landing in a sprawled heap. Keen recoils back into the catapult’s reach; its loaded branch snaps against his tail. Keen: {Ow!} at 10–11.28s. The honeycomb flies from Keen’s grasp, bounces on a rock, rolls over a log and stops in front of Fuzzby. Keep the mechanical chain visible and spatially plausible, never teleport the catapult or bees. Hold just enough for Fuzzby to lift his head, see the honey, then look at Keen.
Phase 3 (16.5–24s): Fuzzby abruptly composes himself from his ridiculous heap for the dry verdict, with a little residual wing tremble. Fuzzby: {Nice machine.} at 16.5–17.94s. Keen: {It almost worked.} at 18.19–20.27s, matching the approved performance unchanged. Only after Keen’s line does the catapult collapse with CLATTER. Keen sighs and walks away. Zenny calmly wipes any remaining juice, closes her eyes and resumes meditation. Finish on her settled stillness against the comic wreckage, with Fuzzby beside the recovered honeycomb. Do not freeze the living characters.''')
section('CHANNEL TIMING','''action: 0–1.1s: immediate release, camera follows blueberry, splat on Zenny.
action: 1.1–5.66s: Fuzzby’s upside-down wake-up foolishness against Zenny’s approved line.
action: 5.66–16.5s: Keen approaches, snatches honeycomb, Fuzzby falls, rebound hits Keen, honeycomb bounces and rolls.
action: 16.5–20.27s: approved comic exchange without overlapping speakers.
action: 20.27–24s: catapult collapse, Keen exit, Zenny’s calm reset.''')
text=text.replace('The berry stain appears on Zenny and persists through the landing.','The berry splat appears on Zenny before her line; she licks and later wipes it away as scripted.')
text=text.replace('Safeguard: the berry stain readable on Zenny through the final hold.','Safeguard: preserve the cause and effect of the splat, licking and final wipe.')
text=text.replace('End on Zenny calm again with berry still visible; Keen withdrawn low in frame; Fuzzby awake and amused beside the honeycomb; ruined catapult behind Keen under warm morning light.','End on Zenny clean-faced and meditating again; Keen walks away, Fuzzby beside the recovered honeycomb, collapsed catapult in its established position under warm morning light.')
text=re.sub(r'(Zenny|Keen|Fuzzby): \{', r'Spoken action: \1: {', text)
Path('cb-output/image-trials/Ep3_S1_SH1_watch_corrected.txt').write_text(text)
R.save_seedance_working('1','S1.SH1',text,'Ep3',reviewed_by='Julian — directed shot correction')
print('Saved corrected WATCH prompt')
