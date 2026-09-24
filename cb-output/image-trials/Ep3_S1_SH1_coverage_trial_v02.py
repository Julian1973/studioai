"""Bounded repair of the first storyboard trial; sources and approvals preserved."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
import cb_gen,cb_render
refs=[str(ROOT/p) for p in [
 'engine/media/Ep3_S1_SH1_coverage_trial_v01.png',
 'cb-seed/assets/final_turnarounds/CB_Keen.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Zenny.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg',
 'engine/media/shots/Ep3_S1.SH1_keyframe_candidate_e867481d.png']]
prompt='''Precisely edit the storyboard in Image1. Preserve the exact THREE-column FOUR-row layout and the untouched panels. No text, captions or arrows. Image1 is the base sheet, Image2 controls @Keen identity, Image3 controls @Zenny identity, Image4 controls @Fuzzby identity. Image5 establishes original scene geography and original wooden catapult construction; its loaded blueberry exists ONLY at the story opening, never in a later panel. Keep the same original 3D animation style, warm lighting, framing borders and colours.
Repair only the six specified panels. Count panels left-to-right, top-to-bottom. Do not change panels 1,2,3,4,5 or11.

Panel6, row2 column3 <bbox>670 285 990 505</bbox>: Keen has just lifted the WHOLE golden comb clear of the branch in both paws. Fuzzby is directly above the comb, feet unsupported as his perch disappears; wings spread and startled, starting a short harmless drop. Preserve original far-bank tree and Zenny's separate leaf in the scene. No honeycomb remains on the branch; no duplicate comb.

Panel7, row3 column1 <bbox>10 515 335 733</bbox>: Keen is MOVING back toward his near-bank catapult holding the comb in both paws, one foot stepping across the creek's low stone, looking back with sudden concern. He is NOT sitting. Fuzzby behind has landed safely in moss and is spreading wings to follow. Show geographical travel and weight, not teleportation.

Panel8, row3 column2 <bbox>345 515 658 733</bbox>: REPLACE this panel with a clear side view of the accident at the near-bank catapult. Keen still holds the whole comb in BOTH paws. His hip has nudged its loose wooden support and the unrestrained wooden throwing arm has swung down onto his short tail: show the ARM TOUCHING THE TAIL, his startled recoil and the loosened support. The cup at the arm end is conspicuously EMPTY. DELETE the blueberry/wool ball currently in this panel. Only the initial launch panel contains an intact berry. The machine is wobbling but not yet collapsed. Do not invent rope entrapment or stretch the tail. This panel must make the physical cause unmistakable.

Panel9, row3 column3 <bbox>670 515 990 733</bbox>: the whole honeycomb has rolled onto the NEAR bank in front of Fuzzby, beside the original catapult location. Fuzzby has flown across to catch up and is now landing on moss beside it. Keep the creek beyond them and the EMPTY former honeycomb branch at the far tree. Zenny remains on her far-tree leaf. No character or prop duplicates. Do not leave Fuzzby at the distant tree while the honey is at the near bank.

Panel10, row4 column1 <bbox>10 745 335 985</bbox>: replace the mistaken bee with exact @Fuzzby from Image4, standing beside the WHOLE golden honeycomb clearly visible immediately at his feet, looking UP toward Keen with amused satisfaction. Fuzzby has NO PURPLE JUICE anywhere: only Zenny was struck. Preserve Fuzzby's own face, body, antennae and glasses from Image4; no Zenny trait blending. Same near-bank light and ground as panel9.

Panel12, row4 column3 <bbox>670 745 990 985</bbox>: exact @Zenny from Image3 stays seated cross-legged on her original leaf. Preserve a small remaining PURPLE BERRY STREAK on her cheek/forehead after wiping. One eye clearly open and the other clearly closed for ONE knowing wink, not two half-closed eyes. Her body is peacefully settled. This is the last expression before returning to meditation; no extra movement or gag.

Preserve every other accepted element. Keep one honeycomb moving from branch to Keen to ground beside Fuzzby; no piece breaks off. No blueberry returns after panel2. Three identities only, no generic substitutions. The repair must clarify cause, ownership, geography and acting; no new set or mechanical redesign.'''
meta=Path(__file__).with_suffix('.json')
if meta.exists(): raise RuntimeError('Trial already recorded; inspect before retry.')
record={'version':'1.0.1','project':'crystal-bears','episode':'Ep3','scene':1,'shotId':'S1.SH1',
 'status':'submitted','parent':'Ep3_S1_SH1_coverage_trial_v01','prompt':prompt,'model':cb_gen.SEEDREAM_MODEL_ID,
 'references':[{'slot':i+1,'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for i,p in enumerate(refs)],
 'humanApproval':False,'productionMutation':False}
meta.write_text(json.dumps(record,indent=2));cb_render._require_confirmed_billing('byteplus')
try:
 record['output']=cb_gen.generate_image(prompt,refs=refs,aspect='4:3',out='Ep3_S1_SH1_coverage_trial_v02.png',image_size='2K',production_route='cb_render')
 record['status']='returned-awaiting-review'
except Exception:
 record['status']='submission-error-inspect-before-retry';raise
finally: meta.write_text(json.dumps(record,indent=2))
print(json.dumps({'status':record['status'],'output':record.get('output')}))
