import copy
import hashlib
import json
from types import SimpleNamespace
import pytest
import cb_intake
import cb_lineage
from cb_source_refresh import plan, refresh_source_extraction

SCRIPT = 'sha256:' + hashlib.sha256(b'Exact immutable script').hexdigest()

def fixture():
    events = [dict(i=0, scene=1, type='dialogue', speaker='Hero', text='Hello.'),
              dict(i=1, scene=1, type='action', text='The door opens. Hero looks up.'),
              dict(i=2, scene=1, type='dialogue', speaker='Listener', text='Come in.')]
    cb_intake._annotate_source_events(events, SCRIPT)
    beats = [dict(beatCode='1.B1', sceneNumber=1, storyBeat='An invitation',
                  cuts=[dict(dialogue='Hero: Hello. The door opens.', action=None)]),
             dict(beatCode='1.B2', sceneNumber=1, storyBeat='Accept the invitation',
                  cuts=[dict(action='Hero looks up.',dialogue=None),
                        dict(dialogue='Listener: Come in.', action=None)])]
    return {'beats':beats, 'sourceScript':{'scriptVersionId':SCRIPT, 'sha256':SCRIPT[7:]}}, events


def test_reparse_proves_all_text_and_preserves_creative_fields():
    package, events = fixture(); before = copy.deepcopy(package)
    revised, evidence = plan(package, events, SCRIPT)
    assert package == before
    assert evidence['actionBoundaryAdjustments'] == ['1.B2']
    assert [b['storyBeat'] for b in revised['beats']] == [b['storyBeat'] for b in package['beats']]
    spoken = [c['exactText'] for b in revised['beats'] for c in b['cuts'] if c['sourceType']=='dialogue']
    assert spoken == ['Hello.','Come in.']
    assert cb_lineage.validate_beat_package_source_contract(revised)['ok']
    assert plan(revised, events, SCRIPT)[1]['changed'] is False


def test_refresh_cannot_silently_change_script_content():
    package, events = fixture(); events[0]['text'] = 'Goodbye.'
    with pytest.raises(ValueError, match='ordered source text'):
        plan(package, events, SCRIPT)


def test_refresh_archives_and_rebases_only_proven_extraction(tmp_path, monkeypatch):
    package, events = fixture()
    raw = b'Exact immutable script'
    content = tmp_path / 'script.txt'; content.write_bytes(raw)
    current = dict(contentPath='script.txt', sha256=hashlib.sha256(raw).hexdigest(),
                   scriptVersionId=SCRIPT)
    package['sourceScript'] = current
    package['contentSignature'] = cb_lineage.beat_package_signature(package)
    p = tmp_path / 'cb-output' / 'EpT_story_beat_package.json'; p.parent.mkdir()
    p.write_text(json.dumps(package))
    vision = tmp_path / 'cb-output' / 'creative' / 'EpT_episode_vision.json'; vision.parent.mkdir()
    vision.write_text(json.dumps(dict(lockedIntent='Keep the relationship', inputSignature=
        cb_lineage.dependency_signature('episode-vision', cb_lineage.episode_vision_inputs(
            current['scriptVersionId'], package['contentSignature'], 'canon')))))
    monkeypatch.setattr(cb_intake, 'parse_script', lambda *a, **k: {'events':copy.deepcopy(events)})
    store = SimpleNamespace(current=lambda *a, **k: current)
    report = refresh_source_extraction(tmp_path, 'EpT', store, log=lambda *_:None)
    after = json.loads(vision.read_text()); updated = json.loads(p.read_text())
    assert report['changed'] and content.read_bytes() == raw
    assert after['lockedIntent'] == 'Keep the relationship'
    assert after['sourceExtractionRefresh']['newCreativePassClaimed'] is False
    assert after['inputSignature']['inputs']['beatPackageDigest'] == updated['contentSignature']['digest']
    assert list((tmp_path/'cb-output/archive/source_extraction').glob('*/*beat_package.json'))
    assert refresh_source_extraction(tmp_path,'EpT',store,log=lambda *_:None)['changed'] is False
