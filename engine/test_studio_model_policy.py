import copy
import json
from types import SimpleNamespace
import pytest
from studio_model_policy import PRESET, route, usage_record, commitment, summary, validate_routes
from studio_workspace import StudioError
from test_studio_production import setup, command


def response(**changes):
    return SimpleNamespace(model='gpt-5.6-terra', service_tier='default', usage={
        'input_tokens':10000, 'output_tokens':2000,
        'input_tokens_details':{'cached_tokens':4000,'cache_write_tokens':2000}}, **changes)


def test_cache_reads_and_writes_are_not_double_counted():
    value=usage_record(response(),'gpt-5.6-terra')
    assert value['estimatedUsd']==pytest.approx(.0378)
    assert commitment({'estimate':100,'usage':value})==37800
    assert commitment({'estimate':50000,'usage':value})==50000


@pytest.mark.parametrize('change',[{'model':'unknown-model'},{'service_tier':'flex'},{'service_tier':None},
    {'usage':{'input_tokens':2,'output_tokens':4}},
    {'usage':{'input_tokens':1,'output_tokens':2,'input_tokens_details':{'cached_tokens':2,'cache_write_tokens':0}}},
    {'usage':{'input_tokens':200000,'output_tokens':2,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0}}}])
def test_unknown_or_inconsistent_usage_is_never_zero_cost(change):
    r=response()
    for k,v in change.items():setattr(r,k,v)
    assert usage_record(r,'gpt-5.6-terra')['estimatedUsd'] is None


@pytest.mark.parametrize('kind,shot,message,expected',[
    ('plan',None,'','creative'),('revise',{},'Make this funnier','creative'),
    ('chat',{'id':'s'},'Make the reverse more emotional','creative'),
    ('revise',{'id':'s'},'shorten the keyframe prompt','routine'),
    ('revise',{'id':'s'},'shorten the keyframe prompt and remove the character','creative'),
    ('chat',None,'explain the workflow','assistant'),
    ('chat',None,'interpret this story','creative')])
def test_conservative_routing(kind,shot,message,expected):
    b={'model':'original','estimateUsd':3,'routing':PRESET,'revision':7}
    result=route(b,kind,shot,message)
    assert result['route']==expected
    assert result['revision']==7
    assert b['model']=='original'


def test_old_services_remain_pinned():
    b={'model':'custom','estimateUsd':3}
    assert route(b,'plan',None,'')==b


@pytest.mark.parametrize('value',[[],{'creative':{}},{**PRESET,'assistant':{'model':'ok','estimateUsd':'NaN'}},
    {**PRESET,'routine':{'model':'ok','estimateUsd':.0000001}}])
def test_route_validation(value):
    with pytest.raises(StudioError):validate_routes(value)


def enable(ws):
    services=ws.services('first');services['direction']['routing']=copy.deepcopy(PRESET)
    return ws.save_services('first',services)


def test_route_is_reserved_pinned_and_usage_persisted_before_validation(setup):
    p,ws,t,_=setup;enable(ws)
    original=t.direct
    def direct(*args,**kwargs):
        result=original(*args,**kwargs)
        result['_usage']=usage_record(response(),'gpt-5.6-terra')
        return result
    t.direct=direct
    command(p,'budget',amountUsd=10)
    state=p.snapshot('first','1')
    assert state['state']['shots']
    with ws.db() as db:
        job=json.loads(db.execute("SELECT data FROM jobs ORDER BY rowid LIMIT 1").fetchone()[0])
    assert job['binding']['route']=='creative'
    assert job['binding']['model']=='gpt-6-astra'
    assert job['estimate']==2000000
    assert state['costs']['pricedRequests']==1
    assert state['costs']['inputTokens']==10000
    before=len(t.calls)
    command(p,'chat',message='status')
    assert len(t.calls)==before


def test_routine_model_cannot_change_camera_or_approvals(setup):
    p,ws,t,_=setup;enable(ws);command(p,'budget',amountUsd=10)
    before=copy.deepcopy(p.snapshot('first','1')['state']['shots'][0])
    t.reply={'message':'Changed camera','revisedShot':{k:v for k,v in before.items() if k not in {'outcomes','versions','sourceSignature'}}}
    t.reply['revisedShot']['camera']='New camera'
    command(p,'revise',shotId='S1.SH1',stage='see',message='shorten the keyframe prompt')
    after=p.snapshot('first','1')
    assert after['jobs'][0]['status']=='failed'
    assert after['state']['shots'][0]==before


def test_usage_summary_includes_more_than_thirty_requests():
    records=[{'kind':'chat','usage':usage_record(response(),'gpt-5.6-terra')} for _ in range(40)]
    result=summary(records+[{'kind':'watch'},{'kind':'assembly'}])
    assert result['measuredRequests']==40
    assert result['unpricedRequests']==1


def test_readiness_reports_missing_connections_without_generation(setup):
    from studio_model_policy import readiness
    p,ws,t,_=setup
    report=readiness(ws,ws.context('first','1'))
    assert sum(c['status']=='configured' for c in report['checks'])==4
    assert report['checks'][-1]['optional']
    ws.save_services('first',{})
    assert all(c['status']=='missing' for c in readiness(ws,ws.context('first','1'))['checks'])
    assert not t.calls


def test_transport_captures_usage_and_disables_retry(monkeypatch):
    from studio_transport import ProviderTransport
    import openai
    calls=[]
    r=response();r.status='completed';r.output_text=json.dumps({'message':'Ready','revisedShot':None})
    def client(**kwargs):
        assert kwargs['max_retries']==0
        def parse(**body):
            calls.append(body)
            return r
        return SimpleNamespace(responses=SimpleNamespace(create=parse))
    monkeypatch.setattr(openai,'OpenAI',client)
    result=ProviderTransport().direct({},'private-test-key','gpt-5.6-terra','standard',{})
    assert len(calls)==1
    assert calls[0]['service_tier']=='default'
    assert result['_usage']['inputTokens']==10000
    assert 'private-test-key' not in json.dumps(result)


def test_hear_reserves_every_provider_line(setup):
    p,ws,t,_=setup
    command(p,'budget',amountUsd=10)
    with ws.db() as db:
        state=p._load(db,'first','1')
        shot=state['shots'][0]
        shot['outcomes']['see']['status']='approved'
        shot['dialogue'].append(copy.deepcopy(shot['dialogue'][0]))
        job=p.reserve(db,ws.context('first','1'),state,'first','1','hear',shot,'',{})
        assert job['requestCount']==2
        assert job['estimate']==200000
        assert len(job['inputs']['dialogue'])==2
