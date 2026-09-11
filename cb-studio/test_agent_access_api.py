import json
import pytest
from test_local_auth import studio, _request
from test_studio_production import setup as production_setup


def test_incident_evidence_is_required_and_scoped(studio, monkeypatch, tmp_path):
    module,port=studio
    _,ws,_,_=production_setup.__wrapped__(tmp_path)
    import studio_workspace
    monkeypatch.setattr(studio_workspace,'Workspace',lambda root:ws)
    _,headers,_=_request(port,'GET','/cb-studio/app.html')
    auth={'Cookie':headers['Set-Cookie'].split(';',1)[0],'Origin':f'http://127.0.0.1:{port}','Content-Type':'application/json'}
    def post(d):
        code,_,body=_request(port,'POST','/api/workflow-incidents',auth,json.dumps(d));return code,json.loads(body)
    base={'projectId':'first','summary':'Missing cue','observed':'Cue absent in request v1','expected':'Cue owned by actor'}
    code,r=post(base);assert code==200,r
    item=r['incident']
    code,_=post({**base,'id':item['id'],'expectedRevision':1,'status':'verified'})
    assert code==400
    code,_=post({**base,'projectId':'second','id':item['id'],'expectedRevision':1})
    assert code==409
    code,r=post({**base,'id':item['id'],'expectedRevision':1,'status':'verified',
                'rootCause':'Compiler discarded action','affectedComponent':'shared compiler',
                'fixReference':'change abc','regressionEvidence':'test x passed',
                'workflowEvidence':'request v2 contains cue','reviewer':'test reviewer'})
    assert code==200 and r['incident']['status']=='verified'
    status,_,_=_request(port,'GET','/api/agent-access');assert status==401
    status,_,body=_request(port,'GET','/api/agent-access',auth)
    assert status==200 and json.loads(body)['config']['mcpServers']['studioai']['command']
