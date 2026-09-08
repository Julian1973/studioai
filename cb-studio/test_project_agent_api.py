"""Authenticated workspace API regressions with an isolated fake credential vault."""
import json
import uuid

from test_local_auth import studio, _request
from test_studio_production import setup as production_setup


def test_workspace_api_scope_credentials_and_shared_commands(studio,monkeypatch,tmp_path):
    module,port=studio
    p,ws,transport,accounts=production_setup.__wrapped__(tmp_path)
    monkeypatch.setattr(module,'ROOT',ws.root)
    import studio_workspace, studio_production
    monkeypatch.setattr(studio_workspace,'Workspace',lambda root:ws)
    monkeypatch.setattr(studio_production,'Production',lambda workspace:p)
    status,_,_=_request(port,'GET','/api/workspace/connections')
    assert status==401
    _,headers,_=_request(port,'GET','/cb-studio/app.html')
    auth={'Cookie':headers['Set-Cookie'].split(';',1)[0],'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json'}
    def get(path):
        status,_,body=_request(port,'GET',path,auth);return status,json.loads(body)
    def post(path,payload,headers=auth):
        status,_,body=_request(port,'POST',path,headers,json.dumps(payload));return status,json.loads(body)
    status,connections=get('/api/workspace/connections')
    assert status==200 and len(connections['connections'])==3
    assert 'test-secret-value' not in json.dumps(connections)
    status,state=get('/api/project-production?projectId=first&episode=1')
    assert status==200 and state['state']['revision']==0
    status,_=get('/api/project-production?projectId=first&episode=99');assert status==400
    payload={'projectId':'first','episode':'1','action':'budget','commandId':uuid.uuid4().hex,'expectedRevision':0,'amountUsd':2}
    status,result=post('/api/project-command',payload)
    assert status==200,result
    status,state=get('/api/project-production?projectId=first&episode=1')
    assert state['state']['shots'][0]['outcomes']['see']['status']=='candidate'
    _,other=get('/api/project-production?projectId=second&episode=1');assert not other['state']['shots']
    status,_=post('/api/project-command',{**payload,'commandId':uuid.uuid4().hex});assert status==409
    status,_=post('/api/workspace/connections',{'provider':'openai','key':'should-not-save-this'},{**auth,'Origin':'https://evil.example'})
    assert status==403
    assert len(ws.connections())==3
    status,result=post('/api/director-chat',{'projectId':'second','episode':'Ep1','scene':'1','stage':'keyframe','message':'approve'})
    assert status==409 and result['code']=='scope_mismatch'
    status,library=get('/api/project-library?projectId=first')
    assert status==200
    status,result=post('/api/project-library',{'projectId':'first','sourceHash':library['context']['sourceHash'],
        'group':'props','name':'Letter','notes':'A folded letter'})
    assert status==200 and result['context']['assets']['props'][0]['name']=='Letter'
    import base64
    status,result=post('/api/project-script-extract',{'projectId':'first','docName':'Opening.txt',
        'docData':base64.b64encode(b'Hero: Hello.').decode()})
    assert status==200 and result['script']=='Hero: Hello.'


def test_provider_connection_errors_do_not_echo_credentials(studio,monkeypatch,tmp_path):
    module,port=studio
    p,ws,transport,accounts=production_setup.__wrapped__(tmp_path)
    import studio_workspace,studio_transport
    monkeypatch.setattr(studio_workspace,'Workspace',lambda root:ws)
    def failure(*args,**kwargs): raise RuntimeError('Authorization: secret-that-must-not-leak')
    monkeypatch.setattr(studio_transport.ProviderTransport,'check',failure)
    _,headers,_=_request(port,'GET','/cb-studio/app.html')
    auth={'Cookie':headers['Set-Cookie'].split(';',1)[0],'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json'}
    status,_,body=_request(port,'POST','/api/workspace/connections',auth,json.dumps({'action':'check','id':accounts['openai']['id']}))
    assert status==500
    assert b'secret-that-must-not-leak' not in body
