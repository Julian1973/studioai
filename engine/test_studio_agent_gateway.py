import pytest
from studio_agent_gateway import Gateway, GatewayError, StudioHTTP, scrub


class Client:
    base = 'http://127.0.0.1:8899'
    def __init__(self): self.calls=[]; self.fail=False
    def request(self, method, route, data=None):
        if route == '/api/projects':
            return {'projects': [{'id':'crystal-bears'}, {'id':'other'}]}
        self.calls.append((method,route,data))
        if self.fail: raise GatewayError('uncertain network result')
        return {'ok':True, 'jobId':'existing-studio-job'}


def test_same_native_dispatch_survives_client_restart_without_duplicate(tmp_path):
    client=Client(); gateway=Gateway(client,tmp_path)
    args={'projectId':'crystal-bears','episode':'Ep3','scene':'1','shotId':'S1.SH2',
          'cmd':'fire','spendToken':'sealed-token'}
    first=gateway.execute('shot_command',args,'request-123')
    second=Gateway(client,tmp_path).execute('shot_command',args,'request-123')
    assert first==second and len(client.calls)==1
    assert client.calls[0]==('POST','/api/shot-run',args)
    assert first['completion']=='queued'
    with pytest.raises(GatewayError,match='different inputs'):
        gateway.execute('shot_command',{**args,'shotId':'S1.SH3'},'request-123')


def test_unknown_dispatch_never_auto_resubmits(tmp_path):
    client=Client();client.fail=True;g=Gateway(client,tmp_path)
    args={'projectId':'other','episode':'1','action':'continue','expectedRevision':3}
    with pytest.raises(GatewayError):g.execute('project_command',args,'request-123')
    with pytest.raises(GatewayError,match='not be submitted twice'):
        Gateway(client,tmp_path).execute('project_command',args,'request-123')
    assert len(client.calls)==1


def test_explicit_scope_and_no_foreign_project_enters_legacy_engine(tmp_path):
    c=Client();g=Gateway(c,tmp_path)
    for args in ({'episode':'Ep3'}, {'projectId':'other','episode':'Ep3'},
                 {'projectId':'not-registered','episode':'Ep3'}):
        with pytest.raises(GatewayError):g.read('scene',args)
    assert not c.calls
    with pytest.raises(GatewayError):g.execute('shell',{},'request-123')
    with pytest.raises(GatewayError):g.execute('services',{'projectId':'other','apiKey':'bad'},'request-123')


def test_bridge_does_not_accept_remote_or_credential_urls():
    for url in ('http://evil.test','http://127.0.0.1@evil.test', 'http://127.0.0.1/api',
                'http://localhost/?secret=x'):
        with pytest.raises(GatewayError):StudioHTTP(url)
    assert scrub({'apiKey':'secret','message':'Bearer abcdefgh'})=={'apiKey':'[redacted]','message':'Bearer [redacted]'}
