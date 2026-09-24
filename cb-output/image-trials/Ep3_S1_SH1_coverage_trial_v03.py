"""Bounded repair of the first storyboard trial; sources and approvals preserved."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
import cb_gen,cb_render
refs=[str(ROOT/p) for p in [
 'engine/media/Ep3_S1_SH1_coverage_trial_v02.png',
 'cb-seed/assets/final_turnarounds/CB_Keen.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Zenny.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg',
 'engine/media/shots/Ep3_S1.SH1_keyframe_candidate_e867481d.png']]
prompt='''Edit ONLY panel8 (row3, centre column) of Image1 inside <bbox>345 515 658 733</bbox>. Preserve all eleven other panels and every gutter exactly. The deliverable remains the same 3-column 4-row storyboard sheet. Image2 controls Keen identity. Image5 supplies the wood and rope materials of the original machine only; there is NO BERRY at this late moment. Do not change the other panels.
Replace panel8 with a TIGHT LOW SIDE INSERT: fill the panel with Keen's LOWER BACK, SHORT TAIL and the end of the catapult's wooden throwing arm. The EMPTY wooden scoop at the end of the arm is visibly TOUCHING and slightly compressing the top of Keen's short tail at the precise comic impact. The tail remains attached to Keen's lower back. The lower portion of the golden honeycomb is visible at the top edge, still held in his paws; his face and head are cropped out of this close insert. Show only this single clear contact event, no full-body pose. The loose arm has fallen onto the tail after Keen backed against the support. The cup is completely empty and its concave interior is visible. Preserve Keen from Image2, the same warm light and 3D materials. Do not show Keen kicking the machine or stepping over it. No blueberry, wool ball, duplicate tail, stretched tail, arrows, labels or written sound effects. The camera is close enough to make wooden scoop-to-tail contact unmistakable. All other eleven panels stay unchanged.'''
meta=Path(__file__).with_suffix('.json')
if meta.exists(): raise RuntimeError('Trial already recorded; inspect before retry.')
record={'version':'1.0.2','project':'crystal-bears','episode':'Ep3','scene':1,'shotId':'S1.SH1',
 'status':'submitted','parent':'Ep3_S1_SH1_coverage_trial_v02','prompt':prompt,'model':cb_gen.SEEDREAM_MODEL_ID,
 'references':[{'slot':i+1,'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for i,p in enumerate(refs)],
 'humanApproval':False,'productionMutation':False}
meta.write_text(json.dumps(record,indent=2));cb_render._require_confirmed_billing('byteplus')
try:
 record['output']=cb_gen.generate_image(prompt,refs=refs,aspect='4:3',out='Ep3_S1_SH1_coverage_trial_v03.png',image_size='2K',production_route='cb_render')
 record['status']='returned-awaiting-review'
except Exception:
 record['status']='submission-error-inspect-before-retry';raise
finally: meta.write_text(json.dumps(record,indent=2))
print(json.dumps({'status':record['status'],'output':record.get('output')}))
