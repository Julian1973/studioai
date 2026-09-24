"""Explicitly authorised experimental take; preserves the live shot and approvals."""
import sys,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
import cb_gen,cb_render as R,cb_seedance_pipeline as P,cb_episode_budget as B,cb_costs,cb_asset_registry

base=Path(__file__).with_suffix('')
meta=base.with_suffix('.json')
pkg,_=R.load_pkg('1','Ep3')
shot=next(x for x in pkg['shots'] if x['shotId']=='S1.SH1')
led=next(x for x in pkg['continuityLedger'] if x['shotId']=='S1.SH1')
images=[led['keyframeApproval']['path'],str(ROOT/'cb-seed/assets/final_turnarounds/CB_Zenny.jpeg'),
str(ROOT/'cb-seed/assets/final_turnarounds/CB_Fuzzby.jpeg'),str(ROOT/'cb-seed/assets/final_turnarounds/CB_Keen.jpeg'),
str(ROOT/'engine/media/asset-registry/Ep3_S1_woodland_catapult.jpeg'),str(ROOT/'engine/media/Ep3_S1_plate_candidate_c66c0c33.jpeg'),
str(ROOT/'engine/media/Ep3_S1_SH1_coverage_trial_v03.png')]
audio=led['voiceApproval']['path']
assert hashlib.sha256(Path(audio).read_bytes()).hexdigest()=='65cae1ecd1d741143b3b41f0cc6de8b5023ae047a713641692c16832126d9b82'
assert all(Path(p).is_file() for p in images)
work=led['departmentWork']['animation'];audio_contract=(work.get('approved') or work.get('candidate'))['output']['audioContract']
actions=[
('Wide, start from the EXACT full composition of @Image 1, already loaded and aiming. Keen commits immediately, one eye narrowed, tongue out. Never start zoomed into the blueberry.','Keen starts releasing the loaded arm; Zenny on her far leaf, Fuzzby asleep on top of the distant suspended comb.'),
('Follow the ONE oversized blueberry rapidly across the creek from Keen toward Zenny, preserving the satisfying travelling berry camera. The cup becomes empty at release.','The blueberry reaches Zenny; the near-bank catapult stays empty thereafter.'),
('Cut close to the impact on Zenny’s forehead. A purple splat, tiny eye twitch and dignified still body make the misfire readable. Keen ducks beside his machine offscreen.','Zenny remains seated on the same leaf with purple juice on her forehead and cheek; the intact berry is gone.'),
('Cut upward to Fuzzby waking on the hanging comb, surprised and then bursting into exuberant belly-led laughter. Wings buzz, body rocks with laughter; this is generated character SFX, never spoken words.','Fuzzby laughs on the comb, distracted; the audience understands the opportunity.'),
('Cut to Zenny’s composed close-up for her exact first @Audio1 line. She licks juice with calm restraint, addresses Fuzzby, then settles. Keep her listening/meditation purposeful.','Zenny remains on the original leaf with a small remaining purple mark. Fuzzby is distracted.'),
('Cut wide enough to show Keen cross the stepping route to the far tree. He quickly lifts the WHOLE golden comb clear in both paws, exploiting the laughter. Fuzzby’s feet lose their support; wings flutter as he drops harmlessly to soft moss.','Keen holds the whole comb, the original branch is EMPTY, and Fuzzby has lost his perch. No piece breaks off.'),
('Track Keen retreating across the same route with the comb. His glance back earns the exact Uh-oh line from @Audio1 after the drop. Fuzzby recovers and flies after him with continuous wing motion while airborne.','Keen returns beside the original near-bank catapult holding his prize. Fuzzby follows into the near-bank action area.'),
('Cut tight to the tail/mechanism insert. Keen’s backward hip contact dislodges the loose support; the empty wooden throwing arm falls and taps his SHORT tail. Show cause then contact, synchronized to his exact Ow from @Audio1. Cut briefly to his startled recoil. No unexplained reset, rope trap or self-reloading.','The recoil lifts the comb out of Keen’s paws; the catapult is destabilised and wobbling, its cup EMPTY.'),
('Follow the whole honeycomb bouncing once on the low rock and rolling along the short log toward Fuzzby, now on the near bank. Allow the absurd delivery to register.','One whole comb stops immediately in front of Fuzzby. Keen has empty paws; the original hanging branch remains empty.'),
('Cut medium to Fuzzby looking from his unexpected honey to Keen and delivering his exact Nice machine line from @Audio1. His smug delight contrasts with Keen’s embarrassment.','Fuzzby stands beside the comb; he has NO berry stain. He listens silently as Keen answers.'),
('Reverse medium to Keen for his exact It almost worked line from @Audio1: a small hopeful attempt at dignity gives way to deflation. AFTER the line, the loosened catapult collapses with a single wooden clatter.','Keen stands embarrassed beside the collapsed EMPTY machine; Fuzzby has the whole comb. No new stunt.'),
('Cut to Zenny on her original leaf. She gives ONE clear knowing wink, closes both eyes and resumes peaceful meditation. A tiny residual purple mark remains. Land the contrast without dragging the ending.','Final close-up: Zenny peacefully meditating on her original leaf, eyes closed, residual berry mark. No further dialogue, wink or gag.'),
]
roles=[('Approved opening frame','exact opening composition, initial world positions and finished visual style','Do not use it to repeat the opening state or prevent subsequent planned camera cuts.'),
('Zenny','Zenny identity and relative proportions','Do not copy the turnaround layout or Fuzzby identity.'),
('Fuzzby','Fuzzby identity and relative proportions','Do not copy the turnaround layout or Zenny identity.'),
('Keen','Keen identity and relative proportions','Do not copy turnaround poses or background.'),
('Catapult','wooden catapult materials and construction','Do not copy its wool ball; after launch the cup stays empty.'),
('Buzzing Nook','established scene environment and landmarks','Do not steal or redesign the architectural honey houses; the removable comb is the separate prop from the opening frame.'),
('Coverage board','twelve views in reading order and approximate framing','Do not reproduce the grid, gutters or a still-image slideshow; animate the causal transitions and preserve the canonical reference identities.')]
exclusions=['repeated opening poses or a fixed camera for the entire sequence',
 'turnaround layouts or Fuzzby identity','turnaround layouts or Zenny identity',
 'turnaround poses or sheet backgrounds','the wool ball or a reloaded cup after launch',
 'architectural honey houses as the removable prop','the grid, gutters, still-image holds or any identity drift in the board']
references=[{'tag':f'@Image {i+1}','subject':r[0],'defines':r[1],'exclude':exclusions[i]} for i,r in enumerate(roles)]
references.append({'tag':'@Audio1','subject':'Approved spoken performance','defines':'exact dialogue, speaker identity, performance, cadence and measured lip-sync timing','exclude':'replacement, time-stretched, paraphrased or invented speech'})
dialogue='\n'.join(f"{x['speaker']} at {x['startSec']:g}s–{x['endSec']:g}s: {{{x['exactText']}}}" for x in shot['dialogueLines'])
task={'type':'storyboard_grid','goal':'Keen successfully steals the honeycomb during Fuzzby’s laughter, but his own unstable catapult sends the prize back to Fuzzby; Zenny’s wink lands the final joke.',
'duration_seconds':30,'resolution':R._review_video_resolution(),'storyboard_tag':'@Image 7',
'storyboard_reading_order':'left to right, top to bottom, three columns by four rows',
'references':references,'assets':{'images':[{'path':p,'tag':f'@Image {i+1}'} for i,p in enumerate(images)],'audio':[{'path':audio,'tag':'@Audio1','duration_seconds':R._audio_dur(audio)}]},
'stages':[{'purpose':f'Coverage view {i+1}','event':a,'end_state':b} for i,(a,b) in enumerate(actions)],
'scene_style':'Original stylised 3D feature animation matching the approved opening frame: warm woodland morning light, tactile materials and glistening golden honey. Deliberate comic pace and character-specific acting.',
'camera':'Follow @Image 7 as the storyboard, panel by panel, left to right and top to bottom. Preserve its shot order, action progression and camera coverage. Begin at @Image 1 in full. Rapid launch, travelling berry follow, motivated cuts, clear mechanism insert, matched reaction reverses, then Zenny’s intimate locked button. Animate each view as full-screen moving film; never reproduce the storyboard grid or gutters. The board supplies coverage, not a mandate to pause on twelve static tableaux. The early launch, impact and wake establish the gag before Zenny’s first recorded line. Let remaining action flow around the exact recorded speech. Maintain world positions, creek crossing direction and eyelines through changes of angle.',
'consistency':['Only Keen, Zenny and Fuzzby; each retains its own reference identity.','Keen starts near-bank camera-left, Zenny and the hanging comb start at the far tree. Show the crossing route and return; no teleporting.',
'One whole comb: branch, Keen’s paws, rolling on ground, finally beside Fuzzby. The original branch stays empty after the successful grab.',
'One blueberry launch only; the catapult cup remains EMPTY thereafter. Only Zenny carries purple berry juice; Fuzzby and Keen stay clean.',
'Fuzzby flutters his wings whenever airborne. Zenny’s restrained listening, wink and meditation are intentional acting.'],
'audio':'Dialogue language: English.\n'+audio_contract+'\n'+dialogue+'\nThese are the exact measured windows of the unchanged approved @Audio1 recording. Only the named speaker articulates each line; no repetitions or additional spoken voices. Fuzzby’s exuberant NONVERBAL LAUGHTER is explicitly generated SFX by Seedance, outside the spoken track, alongside wing buzz, berry whoosh/splat, wooden tail tap and final clatter. Keep the dialogue intelligible. Seedance may generate non-verbal music, ambience and SFX. Natural woodland ambience and light playful underscore may support the action, settling beneath Zenny’s final meditation; no abrupt musical climax.'}
# Three user-authorised corrections; all other inputs and performances retained.
actions[1] = ('Follow the ONE oversized blueberry across the creek toward Zenny. Keep the camera alongside and slightly behind the travelling berry, with Zenny always AHEAD of it on her fixed far-bank leaf until contact. Never show Zenny behind the berry and then ahead again. The cup becomes empty at release.', 'The berry approaches Zenny for its FIRST and ONLY contact; the near-bank catapult remains empty.')
actions[2] = ('Match the incoming berry direction into the close impact view: its first contact is Zenny’s forehead, immediately becoming purple splat. No overshoot, reversal, repeated approach or second impact. Zenny stays on her original distant leaf; use camera movement or a matched cut to reach her, never relocate her. Her eye twitches; Keen ducks beside his machine offscreen.', 'Zenny remains seated on the same far-bank leaf with purple juice; the intact berry is gone.')
actions[3] = (actions[3][0] + ' Begin one continuous nonverbal laughing performance that carries audibly across the next picture cut and underneath Zenny’s line; do not stop or restart the laugh at the cut.', actions[3][1])
actions[4] = (actions[4][0] + ' Fuzzby’s offscreen laughter continues underneath her entire line at a lower level, then tapers naturally. Whenever visible, his laughing body and wing movement continue.', actions[4][1])
actions[11] = ('Cut to Zenny on her original leaf and SETTLE the close-up before the gesture. She meets the camera with both eyes visibly open, closes ONE eye in a clear small knowing wink while the other stays open, then opens it again. Only afterward close both eyes and hold peaceful meditation through the ending. Do not hide the wink inside the camera move or merge it into an ordinary blink. Retain the tiny purple mark.', actions[11][1])
task['stages'] = [{'purpose':f'Coverage view {i+1}', 'event':a, 'end_state':b} for i,(a,b) in enumerate(actions)]
task['audio'] += ' Carry Fuzzby’s generated nonverbal laugh continuously across the wake-to-Zenny picture cut and under her approved line, lowering its level for intelligibility without stopping it; taper naturally afterward. Preserve @Audio1 unchanged.'

prompt=P.build_seedance_prompt(task)
validation=P.validate_seedance_task(task);provider=P.qualify_provider_request(task)
if not validation['ok'] or not provider['ready']: raise RuntimeError(json.dumps({'validation':validation,'provider':provider}))
assert audio_contract in prompt
for line in shot['dialogueLines']: assert prompt.count('{'+line['exactText']+'}')==1
contract=cb_gen.cb_providers.request_contract(fast=False,duration=30,resolution=task['resolution'],image_count=7,audio_count=1,video_count=0)
cost=cb_costs.estimate_video_cost(contract['costRateKey'],30)
sources=[{'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in images+[audio]]
record={'version':'1.0.0','project':'crystal-bears','episode':'Ep3','scene':1,'shotId':'S1.SH1','trial':True,
'humanApproval':False,'sourceDirection':'User authorised restored successful whole-honeycomb grab, visible loose-arm tail accident, fast paced 30-second storyboard trial.',
'supersedesForThisTrialOnly':'honey-piece mechanics','preservesCurrentProduction':True,'sources':sources,
'task':task,'prompt':prompt,'promptSha256':hashlib.sha256(prompt.encode()).hexdigest(),'compiler':'cb_seedance_pipeline.build_seedance_prompt/storyboard_grid',
'skill':'sd25-pe v0.3.3 storyboard-grid template; seedance-production-director','validation':validation,'provider':provider,
'estimateUsd':cost,'candidateCount':1,'state':'prepared','parentTrial':'Ep3_S1_SH1_storyboard_render_trial_v01','corrections':['single berry trajectory to first contact','continuous Fuzzby SFX laugh under Zenny','settled readable wink then meditation']}
import cb_emission_standard
record['promptPreflight']=cb_emission_standard.preflight(prompt,duration_sec=30)
previous=json.loads((base.parent/'Ep3_S1_SH1_storyboard_render_trial_v01.json').read_text())
assert sources==previous['sources'], 'Reference inputs changed since baseline'
assert task['duration_seconds']==previous['task']['duration_seconds']
assert dialogue in prompt and audio_contract in prompt
if '--fire' not in sys.argv:
 if meta.exists(): raise RuntimeError('Prepared trial exists; inspect before replacing.')
 meta.write_text(json.dumps(record,indent=2));base.with_suffix('.prompt.txt').write_text(prompt)
 print(json.dumps({'state':'prepared','estimateUsd':cost,'resolution':task['resolution'],'references':len(sources),'warnings':validation['warnings']}));sys.exit(0)
saved=json.loads(meta.read_text())
assert saved['state']=='prepared' and saved['promptSha256']==record['promptSha256'] and saved['sources']==sources
R._require_confirmed_billing('byteplus')
saved['state']='submitting';meta.write_text(json.dumps(saved,indent=2))
def progress(event):
 saved['progress']={k:v for k,v in event.items() if k in ['event','taskId','status','outputPath','outputBytes']}
 if event.get('event')=='submitted': saved['state']='submitted';saved['providerTaskId']=event['taskId']
 meta.write_text(json.dumps(saved,indent=2))
with B.quote('Ep3',cost,'storyboard-render-trial'):
 output=cb_gen.generate_video_seedance_ref(prompt,images,audio_urls=[audio],duration=30,resolution=task['resolution'],
 out='shots/Ep3_S1_SH1_storyboard_render_trial_v02.mp4',raw_prompt=True,production_route='cb_render',
 model_id=contract['modelId'] if 'modelId' in contract else None,progress_callback=progress,generate_audio=True)
saved.update(state='returned-awaiting-human-review',output=str(output));meta.write_text(json.dumps(saved,indent=2))
asset=cb_asset_registry.register_asset(episode='Ep3',scene=1,shot_id='S1.SH1',kind='candidate_take',role='storyboard-render-trial-v02',
 path=output,status='candidate',label='Storyboard corrections v02 · 30s',source='User-authorised storyboard trial',
 metadata={'trialManifest':str(meta),'directorSource':saved['sourceDirection'],'promptSha256':saved['promptSha256'],'providerTaskId':saved.get('providerTaskId')})
saved['assetId']=asset['assetId'];meta.write_text(json.dumps(saved,indent=2))
print(json.dumps({'state':saved['state'],'output':saved['output']}))
