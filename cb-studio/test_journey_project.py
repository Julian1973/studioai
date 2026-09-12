import sys
from pathlib import Path
import socket
import uuid
import pytest
ROOT=Path('/Users/julianjenkins/Desktop/Ai Studio')
sys.path[:0]=[str(Path(__file__).parent),str(ROOT/'engine')]
from test_studio_production import setup
from studio_journey_project import Project, Services
from studio_journey import Journey,StudioStore

@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket,'connect',lambda *a,**k:pytest.fail('External network forbidden'))

@pytest.mark.parametrize('pid',['first','second'])
def test_project_commands_share_five_action_journey(setup,pid):
    _,ws,t,accounts=setup
    services=ws.services(pid)
    services['review']={'connectionId':accounts['openai']['id'],'model':'test-model','audioModel':'test-audio','estimateUsd':.1}
    ws.save_services(pid,services)
    P=Services(ws,transport=t,background=False)
    P.command({'projectId':pid,'episode':'1','action':'budget','amountUsd':10,'commandId':uuid.uuid4().hex,'expectedRevision':0})
    J=Journey(StudioStore(ws.root),Project(ws.root,ws,transport=t,background=False))
    scope={'projectId':pid,'episode':'1','scene':'1','unit':'S1.SH1'}
    for number in range(5):
        v=J.view(scope)
        assert v['primary'],v
        J.accept(scope,{'commandId':uuid.uuid4().hex,'action':v['phase'],'binding':v['binding'],'expectedRevision':v['revision']},'Producer')
        for _ in range(20):
            J.tick(scope)
            if not J.view(scope)['busy']:break
        assert not (J.view(scope).get('operation') or {}).get('decision'),J.view(scope)['operation']
    result=J.view(scope)
    assert result['phase']=='complete' and result['normalActionCount']==5
    assert len([x for x in t.calls if x[0]=='video'])==1


def test_allowance_configuration_does_not_start_competing_legacy_path(setup):
    from studio_production import Production
    _,ws,t,_=setup
    P=Production(ws,transport=t,background=False)
    P.command({'projectId':'first','episode':'1','action':'budget','amountUsd':10,'prepare':False,'commandId':'configure-only','expectedRevision':0})
    assert P.snapshot('first','1')['state']['budget']['allowance']==10000000
    assert P.snapshot('first','1')['state']['shots']==[]
    assert t.calls==[]
    source=(ROOT/'cb-studio/project-production.js').read_text()
    assert 'prepare:!window.StudioJourney' in source
