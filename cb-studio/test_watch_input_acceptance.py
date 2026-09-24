from types import SimpleNamespace
import pytest
import studio_journey_http as HTTP
import studio_see_service as SEE


@pytest.mark.parametrize('accept', [False, True])
def test_watch_review_uses_existing_see_service_without_generation(monkeypatch,tmp_path,accept):
    calls=[]
    def service(server,data):
        calls.append(data)
        return {'approved':accept,'binding':'current'}
    monkeypatch.setattr(SEE,'request',service)
    monkeypatch.setattr(HTTP,'controller',lambda *a:pytest.fail('No journey or provider action'))
    scope={'projectId':'crystal-bears','episode':'Ep4','scene':'3','unit':'S3.SH1'}
    data={'scope':scope,'command':'accept-watch-inputs' if accept else 'watch-input-review',
          'binding':'reviewed-binding','by':'Julian','withoutStoryboard':True}
    result=HTTP.request(SimpleNamespace(ROOT=tmp_path),data)
    assert result['ok']
    assert calls[0]['command']==('continue-without-storyboard' if accept else 'status')
    if accept:
        assert calls[0]['binding']=='reviewed-binding'
        assert calls[0]['by']=='Julian'


def test_acceptance_requires_explicit_choice_and_propagates_stale_binding(monkeypatch,tmp_path):
    scope={'projectId':'crystal-bears','episode':'Ep4','scene':'3','unit':'S3.SH1'}
    def reject(server,data):
        assert data['binding']=='stale'
        raise ValueError('SEE changed in another window')
    monkeypatch.setattr(SEE,'request',reject)
    data={'scope':scope,'command':'accept-watch-inputs','by':'Julian','binding':'stale'}
    assert HTTP.request(SimpleNamespace(ROOT=tmp_path),data)['ok'] is False
    data['withoutStoryboard']=True
    assert HTTP.request(SimpleNamespace(ROOT=tmp_path),data)['ok'] is False
