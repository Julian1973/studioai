"""User-authorised storyboard trial; does not alter approved production records."""
import sys, json, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
import cb_gen, cb_render

paths = [
 'engine/media/shots/Ep3_S1.SH1_keyframe_candidate_e867481d.png',
 'cb-seed/assets/final_turnarounds/CB_Keen.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Zenny.jpeg',
 'cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg',
 'engine/media/Ep3_S1_plate_candidate_c66c0c33.jpeg',
 'engine/media/asset-registry/Ep3_S1_woodland_catapult.jpeg',
]
refs = [str(ROOT / path) for path in paths]
assert all(Path(path).is_file() for path in refs)
prompt = '''Create one clean COLOUR STORYBOARD CONTACT SHEET: exactly TWELVE distinct cinematic panels, THREE columns by FOUR rows, read left to right then top to bottom. Each panel is landscape 16:9; the whole sheet is 4:3. Narrow plain gutters, no lettering, no captions, no dialogue balloons. This is a sequential film coverage plan, not twelve alternative versions of one opening.

REFERENCE AUTHORITY: Image1 is the approved opening composition and scene geography, including the oversized blueberry, separate suspended golden honeycomb and Zenny's leaf. Panel1 closely matches Image1. Image2 is @Keen identity only. Image3 is @Zenny identity only. Image4 is @Fuzzby identity only. Preserve each identity exactly from its own sheet; never combine their traits or copy multiple turnaround poses. Image5 supplies the Buzzing Nook environment only; its architectural honey houses are NOT the removable honeycomb. Image6 supplies wooden catapult construction/material only; Image1 controls its initial orientation and the BLUEBERRY replaces Image6's wool ball. References have different jobs; preserve the foreground-to-background distance of Image1 when returning to wide views.

The story is a successful theft followed by comic loss. The WHOLE separate hanging honeycomb is taken, never a broken piece. The same single comb changes ownership and location. It must disappear from its branch after removal. The houses remain intact. @Keen starts foreground camera-left at the catapult; @Zenny meditates on her original leaf at the far tree; @Fuzzby starts asleep ON TOP of the hanging comb. The creek and stepping route separate near and far action. Views change, world positions do not teleport. Fuzzby is larger than Zenny but both much smaller than Keen, matching the reference identities at their different depths.

PANEL ORDER — one readable instant in each panel:
1. Wide opening exactly staged from Image1: Keen concentrating beside loaded catapult, one eye closed, tongue out; a single comically oversized blueberry sits in its cup. Distant Fuzzby sleeps on golden comb, Zenny meditates on leaf. Establish distance and clear travel corridor.
2. Dynamic berry-follow view looking along the travel path across the creek: the ONE released blueberry is foreground in flight, Zenny is the approaching destination, Keen and the now EMPTY catapult recede behind. Convey fast forward camera travel through perspective, not extra berries or motion duplicates.
3. Close locked composition on Zenny on her leaf: blueberry has JUST splatted on her forehead, purple juice streak down face, one irritated eye twitch. Her seated balance stays composed; no intact berry remains.
4. Upward reaction medium on Fuzzby perched atop the still-hanging comb: awakened, exuberant physical laughter, leaning back with delighted uncontained body reaction. His wings are visibly spread; this is the same bee from Image4.
5. Close on Zenny, same leaf and berry streak: calmly addressing Fuzzby with dry restraint, one gentle lick of juice, attention upward, weight completely settled. The contrast with Fuzzby's energy is the joke.
6. Three-quarter wide from the far bank: Keen has visibly reached the back tree and successfully lifts the WHOLE separate honeycomb clear of its support, both paws supporting its weight. Fuzzby is immediately above it losing his perch, feet just unsupported; no second comb remains hanging. Original leaf and creek locate this viewpoint.
7. Medium tracking view along return route: Keen retreats toward his near-bank machine carrying the whole comb, glancing back with sudden concern. Behind him Fuzzby has landed harmlessly in soft moss at the far tree, surprised and awake, wings opening to follow. Do not place Fuzzby back on the missing comb.
8. Low side mechanism insert: Keen is back at the original catapult carrying the comb. His backward hip contact visibly knocks a loosened wooden support, letting the empty throwing arm swing down onto his short tail. Show contact and Keen's startled physical recoil in one readable composition. This is an accidental loose-arm drop, NO automatic reloading, NO stretched tail, NO rope trap. Catapult still standing but destabilised.
9. Low wide consequence along ground: Keen's recoil has released the WHOLE comb, which is now rolling off a low rock toward Fuzzby. Fuzzby has flown back into this near-bank area and lands facing the approaching honey. Branch stays empty in background; Zenny remains distant on leaf. Keep one comb, no duplicate flight positions.
10. Medium on Fuzzby beside the stopped honeycomb on the near bank, looking up at Keen with amused satisfaction. The honey has come to him; he owns the punchline through a knowing expression and relaxed grounded pose.
11. Reverse medium on Keen, looking toward Fuzzby with sheepish defeated dignity. The empty catapult immediately behind him is beginning to collapse from its loosened support. The comedy is his restrained recognition, not another wild stunt. No berry in any cup.
12. Intimate locked close-up of Zenny on the ORIGINAL leaf. One small knowing wink, residual purple berry streak, settled cross-legged meditation posture. This is the final living beat before both eyes close again. Same warm morning light and original back-tree geography. No new gag.

Visual treatment: original stylised 3D feature animation matching Image1, warm saturated harmonious colours, soft woodland morning light, tactile wood and soft character materials. Golden honey glistens vibrantly throughout. Maintain clear silhouettes, contact, weight, intent, attention and distinct reactions. Wide views explain geography; inserts show causes; closer reactions land the comedy; reverse angles preserve eyelines. Every frame is a different intended story beat, not generic smiling poses.
Preserve character designs, approved starting geography, one single launch, permanently empty catapult after launch, persistent juice on Zenny, one whole honeycomb and its correct changing location. Exclude text, arrows, labels, page titles, extra cast, mixed bee identities, replacement environments, duplicate props, honey-house theft, magically reset machine, wool ball, vacant staring and montage elements inside an individual panel.'''

record = {'version':'1.0.0','project':'crystal-bears','episode':'Ep3','scene':1,'shotId':'S1.SH1',
 'status':'prepared','purpose':'whole-honeycomb 30-second coverage trial',
 'model':cb_gen.SEEDREAM_MODEL_ID,'prompt':prompt,
 'references':[{'slot':i+1,'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for i,p in enumerate(refs)],
 'voiceAuthority':{'path':str(ROOT/'engine/media/shots/Ep3_S1.SH1_vo_30s_revision_v03.wav'),'sha256':'65cae1ecd1d741143b3b41f0cc6de8b5023ae047a713641692c16832126d9b82'},
 'productionMutation':False,'humanApproval':False}
meta=Path(__file__).with_suffix('.json')
if meta.exists():
    raise RuntimeError('Trial already recorded; inspect its state before any new submission.')
meta.write_text(json.dumps(record,indent=2))
cb_render._require_confirmed_billing('byteplus')
record['status']='submitted';meta.write_text(json.dumps(record,indent=2))
try:
    record['output']=cb_gen.generate_image(prompt,refs=refs,aspect='4:3',out='Ep3_S1_SH1_coverage_trial_v01.png',image_size='2K',production_route='cb_render')
    record['status']='returned-awaiting-review'
except Exception:
    record['status']='submission-error-inspect-before-retry'
    raise
finally:
    meta.write_text(json.dumps(record,indent=2))
print(json.dumps({'status':record['status'],'output':record.get('output')}))
