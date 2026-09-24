import json,subprocess,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'cb-output/image-trials';MEDIA=ROOT/'engine/media';P='Ep3_S1_two_shot_trial_v03';n=int(sys.argv[1]);v=MEDIA/'shots'/f'{P}_shot{n}.mp4'
def run(args):return subprocess.check_output(args)
d=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(v)]));stream=next(s for s in d['streams'] if s['codec_type']=='video');count=int(stream['nb_read_frames']);out=MEDIA/f'{P}_last{n}.png'
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-vf',f'select=eq(n\\,{count-1})','-frames:v','1','-y',str(out)],check=True)
r={'source':str(v),'sourceSha256':hashlib.sha256(v.read_bytes()).hexdigest(),'frameIndex':count-1,'framePath':str(out),'frameSha256':hashlib.sha256(out.read_bytes()).hexdigest(),'duration':d['format']['duration'],'frameRate':stream['r_frame_rate'],'dimensions':[stream['width'],stream['height']],'audioPresent':any(s['codec_type']=='audio' for s in d['streams']),'humanApproval':False,'basis':'Exact final decoded frame from new authorised draft clip; not an approved production shot.'}
(BASE/f'{P}_last{n}.json').write_text(json.dumps(r,indent=2))
# Sampled visual evidence only; not a substitute for audiovisual review.
subprocess.run(['ffmpeg','-v','error','-i',str(v),'-vf','fps=1,scale=426:-1,tile=4x7','-frames:v','1','-y',str(MEDIA/f'{P}_review{n}.jpg')],check=True)
print(json.dumps(r))
