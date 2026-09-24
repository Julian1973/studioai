"""Same-moment new-angle draft handoff for the authorised two-clip test."""
import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'engine'))
import cb_gen,cb_render as R,cb_costs,cb_episode_budget as B
BASE=ROOT/'cb-output/image-trials';MEDIA=ROOT/'engine/media';P='Ep3_S1_two_shot_trial_v03'
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
meta=BASE/f'{P}_keyframe.json'
if meta.exists():raise RuntimeError('Already recorded; no automatic paid retry.')
prev=json.loads((BASE/f'{P}_shot1.json').read_text());assert prev['state']=='returned-awaiting-human-review'
last=MEDIA/f'{P}_last1.png';assert last.is_file()
source=Path(prev['output']);extract=json.loads((BASE/f'{P}_last1.json').read_text());assert extract['sourceSha256']==h(source) and extract['frameSha256']==h(last)
refs=[last,MEDIA/'Ep3_S1_plate_candidate_c66c0c33.jpeg',MEDIA/'shots/Ep3_S1.SH1_keyframe_candidate_e867481d.png',ROOT/'cb-seed/assets/final_turnarounds/CB_Keen.jpeg',ROOT/'cb-seed/assets/final_turnarounds/CB_Zenny.jpeg',ROOT/'cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg',MEDIA/'asset-registry/Ep3_S1_woodland_catapult.jpeg']
prompt='''Create one 16:9 CGI opening keyframe for the NEXT camera shot at the SAME STORY MOMENT as Image 1. This is a clean editorial cut to a different viewpoint, with absolutely no character or prop advancing in time.
Image 1 is the actual final frame of the preceding draft clip: it controls the visible current state, especially Zenny on her leaf with purple juice. Offscreen positions and props remain as established in Image 3 after the berry has fired: catapult EMPTY, Fuzzby still on the hanging comb. Its camera composition must change, but its physical state must not.
Image 2 controls the established Buzzing Nook environment, tree and creek landmark relationships, morning light and ground support; it must not reset current character or prop states.
Image 3 supplies the original set depth, distances and finished CGI material treatment only, not the initial loaded berry or initial character poses.
Image 4 defines @KEEN identity only. Image 5 defines @ZENNY identity only. Image 6 defines @FUZZBY identity only. Preserve each exact reference identity, proportions and details; do not reproduce turnaround layouts.
Image 7 supplies only wooden catapult construction and rope materials. Exclude its wool ball. The throwing cup is visibly EMPTY.
Camera: cut approximately 35 degrees along the same near bank, remaining on the established side of the creek/action axis. Compose a medium-wide three-quarter rear view beside Keen, with his shoulder and the empty catapult on the near bank framing the view toward the distant original honeycomb tree and Zenny leaf across the creek. Keep the route between them clearly visible. The angle is new; the creek and trees are not mirrored. Do not move the far tree or leaf nearer to Keen for convenience.
State: Keen is still beside his original near-bank machine, paws EMPTY, noticing the opportunity. He has not begun crossing. Fuzzby is still on the whole hanging honeycomb at the far tree; the honeycomb has not been grabbed. Zenny remains seated on her original far-bank leaf with the residual purple berry mark. There is no intact blueberry anywhere. Match the actual preceding frame wherever it establishes more precise pose or placement.
Style: original stylised 3D CGI, tactile plush/materials and warm volumetric woodland morning light matching the source. The glistening golden removable honeycomb remains separate from architectural honey houses. Preserve physical contacts, scale and fixed landmark relationships under the camera change. Clean single full-screen frame, no storyboard, text, split view, inset or transition morph.'''
record={'version':'1.0.0','project':'crystal-bears','episode':'Ep3','scene':1,'shotId':'S1.SH2','trial':True,'humanApproval':False,'joinType':'PLANNED_CUT','sourceFinalFrame':extract,'references':[{'slot':i+1,'path':str(p),'sha256':h(p)} for i,p in enumerate(refs)],'prompt':prompt,'state':'submitting','model':cb_gen.SEEDREAM_MODEL_ID,'estimateUsd':cb_costs.estimate_image_cost(num_refs=len(refs))}
meta.write_text(json.dumps(record,indent=2));R._require_confirmed_billing('byteplus')
try:
 with B.quote('Ep3',record['estimateUsd'],'two-shot-new-angle-keyframe'):
  out=cb_gen.generate_image(prompt,refs=[str(p) for p in refs],aspect='16:9',out=f'{P}_opening2.png',image_size='2K',production_route='cb_render')
 record.update(state='returned-awaiting-review',output=str(out),outputSha256=h(out))
finally:meta.write_text(json.dumps(record,indent=2))
print(json.dumps({'state':record['state'],'output':record.get('output')}),flush=True)
