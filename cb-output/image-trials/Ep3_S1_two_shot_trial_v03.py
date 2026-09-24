"""Authorised two-clip experiment; no live approval or source replacement."""
import sys,json,hashlib,wave,copy,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'engine'))
import cb_gen,cb_render as R,cb_seedance_pipeline as P,cb_episode_budget as B,cb_costs,cb_asset_registry,cb_emission_standard
from PIL import Image
BASE=ROOT/'cb-output/image-trials';MEDIA=ROOT/'engine/media';PREFIX='Ep3_S1_two_shot_trial_v03'
prior=json.loads((BASE/'Ep3_S1_SH1_storyboard_render_trial_v02.json').read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2));tmp.replace(p)
def refs_record(paths):return [{'path':str(p),'sha256':digest(p)} for p in paths]
def prepare():
 manifest=BASE/(PREFIX+'.json')
 if manifest.exists():return json.loads(manifest.read_text())
 for r in prior['sources']:assert digest(r['path'])==r['sha256']
 board=Image.open(prior['sources'][6]['path']);w,h=board.size
 for n,ids in [(1,range(5)),(2,range(5,12))]:
  out=Image.new('RGB',(1280,360*((len(ids)+1)//2)),'white')
  for j,i in enumerate(ids):
   x,y=i%3,i//3
   box=(int(x*w/3),int(y*h/4),int((x+1)*w/3),int((y+1)*h/4))
   out.paste(board.crop(box).resize((640,360)),((j%2)*640,(j//2)*360))
  out.save(MEDIA/f'{PREFIX}_board{n}.png')
 source=Path(prior['sources'][-1]['path'])
 with wave.open(str(source),'rb') as f:params=f.getparams();raw=f.readframes(f.getnframes())
 stride=params.nchannels*params.sampwidth;rate=params.framerate
 # Copy sample ranges unchanged with protective margins; reposition only silence.
 lines=prior['task']['audio']
 timings=[[(3.1,7.78,5.0,'ZENNY',"OK, Fuzzby, calm down. It’s not that funny.")],[(11.9,13.14,8.0,'KEEN','Uh-oh—'),(14,15.4,12.0,'KEEN','Ow!'),(20.5,22.06,18.0,'FUZZBY','Nice machine.'),(22.19,24.39,20.0,'KEEN','It almost worked.')]]
 audio_records=[]
 for n,(dur,segments) in enumerate(zip([12,26],timings),1):
  buf=bytearray(dur*rate*stride);ledger=[]
  for start,end,new,speaker,words in segments:
   a=round((start-.12)*rate);b=round((end+.12)*rate);dst=round((new-.12)*rate)
   piece=raw[a*stride:b*stride];buf[dst*stride:dst*stride+len(piece)]=piece
   assert bytes(buf[dst*stride:dst*stride+len(piece)])==piece
   ledger.append({'speaker':speaker,'exactText':words,'startSec':new,'endSec':round(new+end-start,3),'sourceStartSec':start,'sourceEndSec':end,'sampleRange':[a,b],'copiedSamplesSha256':hashlib.sha256(piece).hexdigest()})
  path=MEDIA/'shots'/f'{PREFIX}_audio{n}.wav'
  with wave.open(str(path),'wb') as f:f.setparams(params);f.writeframes(buf)
  audio_records.append({'path':str(path),'sha256':digest(path),'duration':dur,'dialogue':ledger,'status':'derived-trial-not-new-human-approval'})
 d={'version':'1.0.0','project':'crystal-bears','episode':'Ep3','scene':1,'parentTrial':'Ep3_S1_SH1_storyboard_render_trial_v02','humanApproval':False,'preservesCurrentProduction':True,'audioSource':str(source),'audioSourceSha256':digest(source),'audio':audio_records,'joinType':'PLANNED_CUT','cutAuthority':'outgoing exact final frame = dynamic continuity only; newly generated keyframe = incoming exact opening','status':'prepared','userAuthorization':'Two returned shots requested; draft-source handoff and both generation actions authorised in this task.'}
 save(manifest,d);return d

def video(n):
 d=prepare();meta=BASE/f'{PREFIX}_shot{n}.json'
 if meta.exists():raise RuntimeError('Already recorded. Inspect state; never resubmit automatically.')
 task=copy.deepcopy(prior['task']);a=d['audio'][n-1];assert digest(a['path'])==a['sha256'];duration=a['duration']
 images=[x['path'] for x in prior['sources'][:6]]+[str(MEDIA/f'{PREFIX}_board{n}.png')]
 if n==2:
  review=json.loads((BASE/f'{PREFIX}_keyframe_review.json').read_text());assert review['usableForAuthorisedTrial']
  images[0]=str(MEDIA/f'{PREFIX}_opening2.png');images.append(str(MEDIA/f'{PREFIX}_last1.png'))
 task['duration_seconds']=duration;task['assets']={'images':[{'path':p,'tag':f'@Image {i+1}'} for i,p in enumerate(images)],'audio':[{'path':a['path'],'tag':'@Audio1','duration_seconds':duration}]}
 task['storyboard_reading_order']='left to right, top to bottom, two columns; ignore the final blank cell';task['references']=copy.deepcopy(prior['task']['references'][:7]);task['references'][6]['defines']=f'ordered coverage views for THIS clip only, left to right, top to bottom; ignore the final blank cell; camera and action guide, not initial state'
 if n==2:task['references'].append({'tag':'@Image 8','subject':'Previous clip final frame','defines':'same-moment world-space continuity: character positions, eyelines, prop ownership, marks, light and action phase','exclude':'opening camera composition, a repeated shot, a morph or motion reference'})
 task['references'].append(copy.deepcopy(prior['task']['references'][-1]))
 audio_contract='@Audio1 is the sole authority for voice identity, cadence, timing and silence. Spoken lines appear only where assigned, in the locked order, with no extra dialogue. The non-speaking characters remain silent throughout each other’s lines.'
 dialogue='\n'.join(f"{l['speaker']} at {l['startSec']:g}s–{l['endSec']:g}s: {{{l['exactText']}}}" for l in a['dialogue'])
 task['audio']='Dialogue language: English.\n'+audio_contract+'\n'+dialogue+'\nUse the supplied recorded performances exactly at these local timings. Only the named speaker articulates each line. Fuzzby’s nonverbal laughter is generated Seedance SFX, not additional speech: sustain it through the cut to Zenny and underneath her response at a lower level. Natural woodland ambience, wing buzz and physical effects; a gentle playful score stays low and does not restart loudly at cuts.'
 if n==1:
  task['goal']='Keen’s confident berry launch hits the wrong target. Zenny’s restraint contrasts with Fuzzby’s unbroken laughter; Keen spots an opportunity but has not acted on it yet.'
  stages=[('0–3s. Wide exact @Image 1 opening. Keen releases once. Follow alongside and slightly behind the berry across the creek, keeping Zenny ahead until FIRST contact on her forehead. One splat, no overshoot or spatial reset. The catapult cup is now empty.','Zenny remains on the far leaf with berry juice. Keen stays beside the near-bank empty machine.'),('3–5s. Cut to Fuzzby waking on the suspended honeycomb and exploding into rocking belly-led laughter. Keen ducks beside his machine.','Fuzzby stays on the comb; laughter continues into the next view.'),('5–9.68s. Cut to Zenny’s settled close-up for her exact recorded response. She licks the juice with composed restraint. Fuzzby’s offscreen laugh continues uninterrupted beneath her words, gently lowered for clarity.','Zenny settles with a small purple mark. Comb still hangs, Fuzzby still on it.'),('9.68s–end. Cut back to the established wide geography. Keen peeks from beside the near-bank machine and glances towards distracted Fuzzby on the far-tree honeycomb; a small intent smile. He does not cross yet. Settle this wide so the entire spatial handoff is readable.','Keen beside EMPTY near-bank catapult, paws empty. Zenny on original far-bank leaf with mark; Fuzzby on WHOLE hanging honeycomb at far tree. Original route and distances unchanged. No wink, grab or collapse yet.')]
  task['consistency']=['Only the single launched berry; cup remains empty after release.','Keen near bank; Zenny and Fuzzby at the distant tree across the creek. No character crosses during this clip.','Fuzzby keeps his perch on the whole comb; honey houses remain architecture. Only Zenny has purple juice.']
  task['camera']='Follow @Image 7 coverage left to right, top to bottom for launch, impact, laugh and response. End with the explicit wide handoff described below. Use full-screen moving CGI, not a board. Same launch axis: Zenny remains ahead of the berry until impact; cuts change camera, never geography.'
 else:
  task['goal']='Keen exploits the distraction, takes the whole honeycomb, and returns to his machine; a visible mechanical accident delivers the prize to Fuzzby. Zenny’s knowing wink restores calm.'
  stages=[('0–6s. Start EXACTLY at new-angle @Image 1, same moment as @Image 8. Keen steps from his established near-bank position, crosses the visible stepping route to the far tree, and lifts the WHOLE hanging comb in both paws. Fuzzby loses support and drops harmlessly to the moss, fluttering. Show the crossing and grab in a coherent wide travelling view.','Keen at the far tree holding the whole comb; original branch empty. Fuzzby has lost his perch.'),('6–10s. Follow Keen returning along the SAME stepping route towards his original catapult with the honeycomb. His backward glance at Fuzzby’s drop earns the exact recorded Uh-oh at 8s. Fuzzby recovers and follows with fluttering wings.','Keen back beside near-bank machine with the comb. Fuzzby arrives nearby; Zenny stays at far leaf.'),('10–15s. Cut to a readable side view then the contact insert. Keen backs into the loose catapult support; that contact dislodges it, causing the EMPTY throwing arm to fall onto his short tail at the recorded Ow at 12s. His recoil releases the comb. It bounces once and rolls along the short log to Fuzzby on the near bank.','Whole comb stops at Fuzzby; Keen paws empty. Machine wobbles; original branch empty; cup empty.'),('15–22.21s. Let Fuzzby notice the unexpected prize and look to Keen. Medium Fuzzby for Nice machine at 18s; reverse to Keen for It almost worked at 20s. Keen tries a trace of dignity, then deflates. AFTER his reply the loosened machine collapses with one wooden clatter.','Fuzzby beside comb, Keen beside collapsed empty machine. All action ends before the final button.'),('22.21s–end. Cut to a SETTLED close-up of Zenny on her original leaf, purple mark remaining. Meet camera with both eyes open, close ONE eye for a clear knowing wink while the other stays open, reopen it; then close both eyes and hold peaceful meditation to the end. Camera is still before the wink; no extra joke.','Zenny meditates on her original leaf with eyes closed and purple mark. Near bank: Keen and collapsed machine, Fuzzby with whole comb. No new action.')]
  task['consistency']=['@Image 1 owns the NEW opening angle. @Image 8 supplies ONLY the preceding dynamic state; never start at @Image 8 or morph into @Image 1.','Preserve the original creek, stepping route, far tree and actual distances. Follow the crossing and return; no teleporting or mirrored geography.','One WHOLE comb: branch to Keen to ground beside Fuzzby. Empty branch after grab. Machine cup stays EMPTY throughout.','Only Zenny has purple juice. Fuzzby flutters whenever airborne.']
  task['camera']='Start on the new opening keyframe @Image 1 as an immediate same-moment editorial cut from the previous clip. Follow @Image 7 left-to-right, top-to-bottom for subsequent action/coverage, preserving current world state from @Image 8. The previous frame is not an opening frame. Motivated wide crossing, contact insert, dialogue reverses, then still Zenny close-up. No transition morph, opening replay or reset.'
 if n==1:
  stages[-1]=('After her line, stay in the SAME locked Zenny close-up through the end. She quietly settles on her original leaf with the purple mark still visible. No wink yet. Fuzzby’s offscreen laugh tapers naturally. No return to an empty scene plate or establishing shot.', 'Zenny on her original far-bank leaf, berry mark intact. Offscreen state remains: Keen beside the near-bank empty catapult with empty paws; Fuzzby on the whole hanging comb. Nothing has moved, no grab yet.')
  images=images[:5]+[images[6]]
  task['assets']['images']=[{'path':p,'tag':f'@Image {i+1}'} for i,p in enumerate(images)]
  task['references']=task['references'][:5]+[task['references'][6],task['references'][-1]]
  task['references'][5]['tag']='@Image 6'
  task['storyboard_tag']='@Image 6'
  task['camera']='Follow @Image 6 coverage left to right, top to bottom, ignoring the final blank cell. Start from @Image 1; launch, impact, laugh, then remain in Zenny’s full-screen close-up through her response and ending. No new establishing view after her response. Cuts change camera, never geography.'
 task['stages']=[{'purpose':f'View {i+1}','event':x,'end_state':y} for i,(x,y) in enumerate(stages)]
 prompt=P.build_seedance_prompt(task);val=P.validate_seedance_task(task);qual=P.qualify_provider_request(task);score=cb_emission_standard.preflight(prompt,duration_sec=duration)
 assert val['ok'] and qual['ready'],(val,qual)
 assert score['verdict']=='PASS',score
 for l in a['dialogue']:assert prompt.count('{'+l['exactText']+'}')==1
 contract=cb_gen.cb_providers.request_contract(fast=False,duration=duration,resolution=task['resolution'],image_count=len(images),audio_count=1,video_count=0);cost=cb_costs.estimate_video_cost(contract['costRateKey'],duration)
 rec={'project':'crystal-bears','episode':'Ep3','scene':1,'trial':True,'shotId':f'S1.SH{n}','humanApproval':False,'preservesCurrentProduction':True,'state':'prepared','task':task,'prompt':prompt,'promptSha256':hashlib.sha256(prompt.encode()).hexdigest(),'references':refs_record(images+[a['path']]),'audio':a,'validation':val,'provider':qual,'promptPreflight':score,'estimateUsd':cost}
 save(meta,rec);(BASE/f'{PREFIX}_shot{n}.prompt.txt').write_text(prompt)
 R._require_confirmed_billing('byteplus');rec['state']='submitting';save(meta,rec)
 def progress(e):
  rec['progress']={k:v for k,v in e.items() if k in ['event','taskId','status','outputPath','outputBytes']}
  if e.get('taskId'):rec['providerTaskId']=e['taskId']
  if e.get('status'):rec['state']=e['status']
  save(meta,rec)
 with B.quote('Ep3',cost,'two-shot-storyboard-trial'):
  out=cb_gen.generate_video_seedance_ref(prompt,images,audio_urls=[a['path']],duration=duration,resolution=task['resolution'],out=f'shots/{PREFIX}_shot{n}.mp4',raw_prompt=True,production_route='cb_render',model_id=contract.get('modelId'),progress_callback=progress,generate_audio=True)
 rec.update(state='returned-awaiting-human-review',output=str(out));save(meta,rec)
 asset=cb_asset_registry.register_asset(episode='Ep3',scene=1,shot_id=f'S1.SH{n}',kind='candidate_take',role=f'two-shot-trial-v01-{n}',path=out,status='candidate',label=f'Two-shot trial · Shot {n} · {duration}s',source='User-authorised two-shot experiment',metadata={'trialManifest':str(meta),'promptSha256':rec['promptSha256'],'providerTaskId':rec.get('providerTaskId')})
 rec['assetId']=asset['assetId'];save(meta,rec);print(json.dumps({'state':rec['state'],'output':str(out)}),flush=True)
if __name__=='__main__':
 if sys.argv[1]=='prepare':print(json.dumps(prepare()))
 else:
  try:video(int(sys.argv[1]))
  except Exception as exc:
   errors=[];e=exc
   while e is not None:
    errors.append({'type':type(e).__name__,'message':str(e)[:1400]});e=e.__cause__
   save(BASE/f'{PREFIX}_error.json',{'errors':errors});raise
