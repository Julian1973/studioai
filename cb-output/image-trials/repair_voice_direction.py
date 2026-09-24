import sys,json,datetime
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'engine'))
import cb_render as R
p,path=R.load_pkg('1','Ep3');l=R._ledger(p,'S1.SH1')
Path('cb-output/image-trials/Ep3_S1_before_voice_handoff_repair.json').write_text(json.dumps(p,indent=2))
w=l.get('workingVoice') or {}
assert w.get('reason')=='scoped-human-performance-correction', 'Unexpected human override: preserve it'
assert all(x['text']==next(d['exactText'] for d in R._shot(p,'S1.SH1')['dialogueLines'] if d['dialogueOccurrenceId']==x['dialogueOccurrenceId']) for x in w['lines'])
l.setdefault('voiceWorkingHistory',[]).append({**w,'supersededReason':'Word-only correction incorrectly marked as performance override'})
l['workingVoice']=None
work=l['departmentWork']['voice']
for key in ('candidate','approved'):
 if work.get(key):work.setdefault('history',[]).append({**work[key],'outcome':'rebuild-provider-acting-handoff'});work[key]=None
R._save(p,path)
R.prepare_department('1','voice','S1.SH1','Ep3')
s=R.voice_performance_status('1','S1.SH1','Ep3')
print('SOURCE',s['source'])
for line in s['currentLines']: print(line['speaker'],line['text'])
print('TAKE MATCHES',s['takeMatchesCurrent'])
