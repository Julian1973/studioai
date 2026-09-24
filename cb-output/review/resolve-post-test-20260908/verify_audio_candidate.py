"""Technical timing/routing checks only; not listening or lip-sync approval."""
import sys,json,subprocess,hashlib
from pathlib import Path
import numpy as np
out=Path(__file__).parent
candidate=Path(sys.argv[1])
reference=out/'Ep2-original-mix-levelled-v03.wav'
def probe(p):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def audio(p,t):
 return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-t','5','-vn','-ac','1','-ar','4000','-f','f32le','-']),dtype=np.float32)
checks=[]
for t in [5,90,180,300,420]:
 a=audio(reference,t).astype(float);b=audio(candidate,t).astype(float)
 n=min(len(a),len(b));a=a[:n];b=b[:n]
 score=[]
 for lag in range(-80,81):
  x=a[max(0,lag):min(n,n+lag)];y=b[max(0,-lag):min(n,n-lag)]
  x=x-x.mean();y=y-y.mean();den=np.linalg.norm(x)*np.linalg.norm(y)
  score.append(float(np.dot(x,y)/den) if den else 0)
 k=int(np.argmax(score)); lag=k-80
 checks.append({'atSeconds':t,'bestLagSamplesAt4k':lag,'correlation':score[k],'gainDB':float(20*np.log10((np.linalg.norm(b)+1e-12)/(np.linalg.norm(a)+1e-12)))})
p=probe(candidate)
r={'candidate':str(candidate),'sha256':hashlib.file_digest(candidate.open('rb'),'sha256').hexdigest(),'bytes':candidate.stat().st_size,'probe':p,'technicalAudioAnchors':checks,'scope':'Encoded candidate vs levelled WAV: technical audio correspondence only. Not perceptual listening or visual lip-sync verification.'}
(out/'original-audio-v03-export-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'bytes':r['bytes'],'sha256':r['sha256'],'anchors':checks,'streams':[{k:s.get(k) for k in ['codec_type','codec_name','width','height','r_frame_rate','duration','nb_frames','sample_rate','channels']} for s in p['streams']]},indent=2))
