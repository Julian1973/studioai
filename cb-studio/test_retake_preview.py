"""Offline retake projection and actual HTTP route regression checks."""
import hashlib
import json
import subprocess
import sqlite3
from pathlib import Path

import pytest
from studio_retake_preview import prepare, QUALIFICATION
from test_production_recovery import load_server, Http


@pytest.fixture
def case(tmp_path):
    image=tmp_path/'image.png'; image.write_bytes(b'opening')
    audio=tmp_path/'audio.wav'; audio.write_bytes(b'approved audio')
    shot={'shotId':'S2.SH1','durationSec':16}
    led={'shotId':'S2.SH1','keyframeApproval':{'approved':True,'path':str(image)},
         'voiceApproval':{'approved':True,'path':str(audio)},
         'watchRetake':{'note':'fix vision','sourceBatchId':'prior','stage':'prior timeout'},
         'watchRetakeHistory':[{'stage':'timeout','providerTaskIds':[]}]}
    pkg={'revision':4,'shots':[shot],'continuityLedger':[led]}
    path=tmp_path/'cb-output/Ep3_scene2_production_package.json';path.parent.mkdir()
    def save():path.write_text(json.dumps(pkg))
    save()
    return tmp_path,pkg,led,path,save


def run(case,**kw):return prepare(case[0],'Ep3','2','S2.SH1','fix vision',**kw)


def test_missing_review_is_specific_and_read_only(case):
    before=case[3].read_bytes(); c=run(case)
    assert c['state']=='STALE' and 'Prompt Director' in c['issue']
    assert c['see']=='current' and c['audio1']=='current / immutable'
    assert c['lineage']['watchRetakeHistory'][0]['stage']=='timeout'
    assert c['providerCalled'] is False and c['spendReserved'] is False
    assert case[3].read_bytes()==before
    assert c['qualification']==QUALIFICATION and c['issue']!=QUALIFICATION


@pytest.mark.parametrize('key,stage',[('keyframeApproval','SEE'),('voiceApproval','HEAR')])
def test_missing_approval(case,key,stage):
    case[2][key]['approved']=False;case[4]()
    c=run(case);assert c['state']=='BLOCKED PENDING' and stage in c['issue']


def test_submission_uncertainty(case):
    case[2]['submissionUncertain']=True;case[4]()
    assert run(case)['state']=='RECOVERY REQUIRED'


def test_lineage_change(case):
    assert run(case,expected_batch_id='other')['state']=='STALE'


def test_database_timeout_events_are_retained_without_writes(case):
    db=case[0]/'cb-output/state/studio.sqlite3';db.parent.mkdir()
    with sqlite3.connect(db) as c:
        c.execute('CREATE TABLE production_operations(data_json TEXT)')
        c.execute('CREATE TABLE production_operation_events(operation_id TEXT,event_id INT,at REAL,data_json TEXT)')
        c.execute('INSERT INTO production_operations VALUES(?)',(json.dumps({'episode':'Ep3','scene':'2','shotId':'S2.SH1','operationId':'prior','kind':'retake-render','state':'needs-attention'}),))
        c.execute('INSERT INTO production_operation_events VALUES(?,?,?,?)',('prior',1,123,json.dumps({'failure':'timeout','providerCalled':False})))
    before=db.read_bytes();card=run(case)
    assert card['lineage']['events'][0]['event']['failure']=='timeout'
    assert db.read_bytes()==before
    assert not Path(str(db)+'-wal').exists()


def test_early_exception_returns_card(case,monkeypatch):
    def fail(*a,**kw):raise PermissionError('Fixture evidence unreadable')
    monkeypatch.setattr(Path,'read_bytes',fail)
    c=run(case)
    assert c['state']=='BLOCKED PENDING' and c['providerCalled'] is False


def test_cached_block_exposes_primary_issue(case):
    root,pkg,led,path,save=case
    refs=[{'slot':'@图1','path':led['keyframeApproval']['path']},
          {'slot':'@Audio1','path':led['voiceApproval']['path']}]
    for r in refs:r['md5']=hashlib.md5(Path(r['path']).read_bytes()).hexdigest()
    rec={'snapshot':{'authorities':{'shot':pkg['shots'][0]},'references':refs,'prompt':'Exact prompt'},
         'review':{'verdict':'BLOCKED','findings':[{'reason':'Dialogue end times disagree.','correction':'Reconcile the measured interval.'}]}}
    report=root/'cb-output/state/prompt-director/review.json';report.parent.mkdir(parents=True);report.write_text(json.dumps(rec))
    led['watchRetake']['stage']=f'(review: {report})';save()
    c=run(case)
    assert c['state']=='BLOCKED PENDING' and c['issue']=='Dialogue end times disagree.'
    assert c['evidence']['shotProductionRequest']['requestHash']
    assert c['evidence']['referenceManifest']==refs
    assert c['lineage']['watchRetakeHistory'][0]['stage']=='timeout'


def test_http_dispatch_never_starts_worker(case,monkeypatch):
    server=load_server(case[0],monkeypatch,'retake_readonly_http')
    def forbidden(*a,**kw):raise AssertionError('Worker/provider/spend path called')
    monkeypatch.setattr(server,'_start',forbidden)
    monkeypatch.setattr(server,'shot_run_job',forbidden)
    with Http(server) as http:
        status,body=http.request('POST','/api/shot-run',{'cmd':'PREPARE_RETAKE','episode':'Ep3','scene':'2','shotId':'S2.SH1','correction':'fix vision'})
    assert status==200 and body['retakePreparation']['operation']=='PREPARE_RETAKE'


def test_ui_routing_and_qualification():
    source=Path(__file__).with_name('app.html').read_text()
    section=source.split('async function prepareWatchRetake(')[1].split('function openKeyframeRetake(')[0]
    assert "cmd:'PREPARE_RETAKE'" in section
    assert "shRun('retake'" not in section
    assert 'PREPARING RETAKE PACKAGE' in section
    assert "RETAKE_PREPARATIONS[key]=j.retakePreparation" in section
    assert QUALIFICATION in source
    assert 'View qualification boundary' in source
    assert '${retakePreparationHTML()}' in source


def test_preview_never_submits_and_fire_keeps_existing_token_gate():
    source=Path(__file__).with_name('app.html').read_text()
    section=source.split('function reviewRetakePreparation(')[1].split('function openWatchRetake(')[0]
    assert "state!=='READY FOR RETAKE REVIEW'" in section
    assert "shRun('fire'" not in section and 'spendToken' not in section
    server=Path(__file__).with_name('serve.py').read_text()
    assert '--spend-token' in server


def test_browser_progress_result_and_explicit_fire():
    source=Path(__file__).with_name('app.html').read_text()
    functions='const RETAKE_PREPARATIONS ='+source.split('const RETAKE_PREPARATIONS =',1)[1].split('function openKeyframeRetake(',1)[0]
    harness=r'''
const assert=require('node:assert/strict');
const SH_EP='Ep3',SH_SC=2,PSHOT_I=0,BASE='';
const pShots=()=>[{shotId:'S2.SH1'}],_esc=x=>String(x??'');
const elements={sheet:{innerHTML:''},railwrap:{innerHTML:''},modal:{classList:{add(){}}}};
const document={getElementById:id=>elements[id]};
let fires=0,resolveFetch,requested;
const shLedger=()=>({pendingSpendAuth:{envelopeHash:'bound'}});
const shApproveSpendFire=()=>fires++,closeM=()=>{},showToast=()=>{};
const renderWorkspaceBody=()=>{},renderStageRail=()=>retakePreparationHTML();
const fetch=async(url,opts)=>{requested=JSON.parse(opts.body);return await new Promise(resolve=>resolveFetch=resolve)};
'''+functions+r'''
(async()=>{
 const pending=prepareWatchRetake('S2.SH1','fix vision','prior');
 assert.equal(requested.cmd,'PREPARE_RETAKE');
 assert.match(retakePreparationHTML(),/PREPARING RETAKE PACKAGE/);
 assert.equal(fires,0);
 resolveFetch({ok:true,json:async()=>({retakePreparation:{state:'BLOCKED PENDING',issue:'Timing conflict',scope:{shot:'S2.SH1'},see:'current',audio1:'current / immutable',providerCallStatus:'no provider call made'}})});
 await pending;
 assert.match(retakePreparationHTML(),/Timing conflict/);
 assert.doesNotMatch(retakePreparationHTML(),/Review prepared request/);
 fireReviewedRetake();assert.equal(fires,0);
 const c=RETAKE_PREPARATIONS[retakePreparationKey('S2.SH1')];
 Object.assign(c,{state:'READY FOR RETAKE REVIEW',envelopeHash:'bound',evidence:{promptDirector:{snapshot:{prompt:'exact'}}},spendDisclosure:{total:1}});
 assert.match(retakePreparationHTML(),/Review prepared request/);
 reviewRetakePreparation();assert.equal(fires,0);
 assert.match(elements.sheet.innerHTML,/Approve spend &amp; Fire/);
 c.envelopeHash='stale';fireReviewedRetake();assert.equal(fires,0);
 c.envelopeHash='bound';fireReviewedRetake();assert.equal(fires,1);
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run(['/usr/local/bin/node','-e',harness],check=True,capture_output=True,text=True)
