"""Offline content and route tests. These do not qualify image understanding."""
from copy import deepcopy
import pytest
from studio_shot_request import Stage, project, ShotProductionRequest, origin


def request(stage='WATCH', **changes):
    values = dict(scope={'projectId':'film','episode':'1','shotId':'S1.SH1'},
        source={'scriptHash':'a'}, direction={'action':'Reach, hesitate, accept.'},
        dialogue=[{'speaker':'A','text':'Thank you.','start':2,'end':3}],
        refs=[{'path':'/old/a','hash':'ref-a','role':'opening'}],
        audio={'hash':'voice-a'}, opening={'hash':'image-a'}, prompt='Act.',
        settings={'duration':8})
    values.update(changes)
    return project(stage, **values)


def test_deep_immutable_no_aliases():
    source={'action':['Reach']}
    r=request(direction=source)
    before=r.record()
    source['action'].append('Drop')
    r.data['truth']['direction']['action'].append('Run')
    r.record()['snapshot']['truth']['direction']['action'].append('Hide')
    assert r.record()==before


@pytest.mark.parametrize('stage', ['SEE','HEAR'])
def test_independent_stages_do_not_depend_on_approved_other_stage(stage):
    a=request(stage)
    b=request(stage,audio={'hash':'new-voice'},opening={'hash':'new-opening'})
    assert a.request_hash==b.request_hash


def test_hear_excludes_visual_references_and_props():
    assert request('HEAR').request_hash==request('HEAR',refs=[],objects={'cup':'broken'}).request_hash


@pytest.mark.parametrize('field,value', [('audio',{'hash':'new'}),('opening',{'hash':'new'}),
    ('dialogue',[{'speaker':'B','text':'Thank you.'}]),('settings',{'duration':9}),
    ('prompt','Different act.'),('direction',{'action':'Decline'})])
def test_watch_binds_each_relevant_change(field,value):
    assert request().request_hash!=request(**{field:value}).request_hash


def test_truth_is_independent_of_execution_and_storage_path():
    a=request()
    b=request(prompt='Equivalent new wording.', refs=[{'path':'/archive/a','hash':'ref-a','role':'opening'}])
    assert a.truth_hash==b.truth_hash
    assert a.request_hash!=b.request_hash
    assert a.request_hash==request(refs=[{'path':'/archive/a','hash':'ref-a','role':'opening'}]).request_hash


def test_reference_order_and_role_are_semantic():
    refs=[{'hash':'a','role':'identity'},{'hash':'b','role':'plate'}]
    assert request(refs=refs).request_hash!=request(refs=refs[::-1]).request_hash


def test_edit_scope_and_source_bound():
    with pytest.raises(ValueError,match='source hash'):
        request('TARGETED_EDIT')
    scope={'sourceSha256':'v1','startSec':1,'endSec':2,'correction':'lighting only'}
    a=request('TARGETED_EDIT',edit_scope=scope)
    assert a.request_hash!=request().request_hash
    assert a.request_hash!=request('TARGETED_EDIT',edit_scope={**scope,'endSec':3}).request_hash
    assert a.truth_hash==request().truth_hash
    assert a.data['execution']['editScope']==scope


def test_native_request_binds_reviewed_plan_exact_dialogue_and_opening():
    from studio_shot_request import native_envelope, originating_review_context
    line={'speaker':'Actor','text':'One exact line.','startSec':2,'endSec':3}
    authority={'shot':{'dialogueLines':[line], 'openingState':'Standing at the table.',
                      'geography':'Table remains by the door.'},
               'specialist':{'dramaticBeat':'A small thoughtful choice.'}}
    snapshot={'authorities':authority, 'watchPlan':{'views':[{'action':'Set down the cup.'}]},
              'watchPlanBinding':{'sourceHash':'source-a'}, 'prompt':'Act.'}
    env={'shotId':'S1.SH1','prompt':'Act.',
         'references':[{'slot':'Image 1','role':'opening keyframe','md5':'frame-a'}],
         'sourceBindings':{'creativeAuthority':{'fingerprint':'bible-a'}},
         'executionPlan':{'segments':[{'prompt':'Act.','promptDirectorSnapshot':snapshot}]}}
    first=native_envelope(env)
    truth=first.data['truth']
    assert truth['dialogue']==[line]
    assert truth['opening'][0]['contentHash']=='frame-a'
    assert truth['continuity']['openingState']=='Standing at the table.'
    assert truth['reviewedDirection'][0]==snapshot['watchPlan']
    assert first.data['execution']['reviewedPlans'][0]['plan']==snapshot['watchPlan']
    env['executionPlan']['segments'][0]['promptDirectorSnapshot']['watchPlan']['views'][0]['action']='Walk away.'
    assert first.request_hash!=native_envelope(env).request_hash
    historical=originating_review_context({'productionRequest':first.record()})
    assert historical['truth']['reviewedDirection'][0]['views'][0]['action']=='Set down the cup.'
    assert historical['observed'] is False and historical['approved'] is False


def test_creative_authority_content_changes_invalidate_new_request_only():
    previous=request(creative_context={'fingerprint':'before'})
    revised=request(creative_context={'fingerprint':'after'})
    assert previous.truth_hash!=revised.truth_hash
    assert ShotProductionRequest.load(previous.record()).truth_hash==previous.truth_hash


def test_native_segments_preserve_master_dialogue_and_local_execution_clocks():
    from studio_shot_request import native_envelope
    master=[{'speaker':'A','exactText':'First.','startSec':1,'endSec':2},
            {'speaker':'B','exactText':'Last.','startSec':9,'endSec':10}]
    local={**master[1],'startSec':1,'endSec':2}
    snapshot={'authorities':{'shot':{'dialogueLines':[local]},
              'sourceUnit':{'shot':{'dialogueLines':master},'globalStartSec':8}},
              'watchPlan':{'dialogueOccurrences':[local]}}
    record=native_envelope({'executionPlan':{'segments':[{'promptDirectorSnapshot':snapshot}]}}).data
    assert record['truth']['dialogue']==master
    assert record['execution']['reviewedPlans'][0]['plan']['dialogueOccurrences']==[local]


def test_review_execution_metadata_is_not_a_new_story():
    plan={'views':[{'action':'Reach.'}], 'requestBindingHash':'model-one'}
    a=request(reviewed_plans=[{'plan':plan, 'reviewHash':'first'}])
    b=request(reviewed_plans=[{'plan':{**plan,'requestBindingHash':'model-two'},'reviewHash':'second'}])
    assert a.truth_hash==b.truth_hash
    assert a.request_hash!=b.request_hash
    assert a.data['execution']['reviewedPlans'][0]['plan']['requestBindingHash']=='model-one'


def test_unselected_bible_edit_is_audit_change_not_shot_truth_change():
    a=request(creative_context={'fingerprint':'same-selected-passages',
              'sources':[{'sourceSha256':'whole-file-before'}]})
    b=request(creative_context={'fingerprint':'same-selected-passages',
              'sources':[{'sourceSha256':'whole-file-after'}]})
    assert a.truth_hash==b.truth_hash
    assert a.request_hash!=b.request_hash


def test_loading_requires_supported_structured_snapshot():
    for value in ({}, {'snapshot':{}}, {'snapshot':{'schemaVersion':999}}):
        with pytest.raises(ValueError):
            ShotProductionRequest.load(value)


def test_origin_never_uses_current_mutable_plan():
    old=request().record()
    assert origin({'productionRequest':old,'direction':{'action':'new'}})['originatingRequestHash']==old['requestHash']
    assert origin({'direction':{'action':'new'}})['status']=='legacy-unverified'
    broken=deepcopy(old)
    broken['snapshot']['execution']['prompt']='silently changed'
    with pytest.raises(ValueError): ShotProductionRequest.load(broken)


def test_nan_is_rejected():
    with pytest.raises(ValueError): request(settings={'duration':float('nan')})


def test_transport_reads_pinned_bytes_after_source_replacement(tmp_path):
    import hashlib
    from pathlib import Path
    from studio_shot_request import pinned_media
    source=tmp_path/'voice.wav'; source.write_bytes(b'approved voice')
    expected=hashlib.sha256(source.read_bytes()).hexdigest()
    with pinned_media({'audio':[source]}, {'audio':[{'hash':expected}]}) as inputs:
        pinned=Path(inputs['audio'][0])
        source.write_bytes(b'replacement voice')
        assert pinned.read_bytes()==b'approved voice'
    assert not pinned.exists()
    with pytest.raises(ValueError,match='changed after review'):
        with pinned_media({'audio':[source]}, {'audio':[{'hash':expected}]}):
            pytest.fail('Mismatched source reached transport')


def test_bad_request_creates_durable_block_before_http(tmp_path):
    import json
    from studio_request_evidence import capture, observe, RequestEvidenceError
    saved=request().record()
    saved['snapshot']['execution']['prompt']='tampered'
    calls=[]
    with capture(tmp_path, {'productionRequest':saved}):
        with pytest.raises(RequestEvidenceError):
            observe(lambda:calls.append(True),'https://provider.test/tasks',{'prompt':'Act.'})
    [report]=[json.loads(p.read_text()) for p in tmp_path.glob('*.json')]
    assert not calls
    assert report['state']=='blocked-before-http' and report['providerCalled'] is False


def test_scene_planner_never_selects_newer_wrong_script_package(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    import cb_engine
    folder=tmp_path/'cb-output'; folder.mkdir()
    right=folder/'Ep3_old_name_beat_package.json'
    right.write_text(json.dumps({'sourceScript':{'scriptVersionId':'current'},'beats':[]}))
    wrong=folder/'Ep3_new_name_beat_package.json'
    wrong.write_text(json.dumps({'sourceScript':{'scriptVersionId':'wrong'},'beats':[]}))
    monkeypatch.setattr(cb_engine,'HERE',tmp_path/'engine')
    monkeypatch.setattr(cb_engine,'SCRIPT_STORE',SimpleNamespace(current=lambda *a,**k:{'scriptVersionId':'current'}))
    assert cb_engine._load_pkg('Ep3')[1]==right
    right.unlink()
    with pytest.raises(ValueError,match='current script'): cb_engine._load_pkg('Ep3')
