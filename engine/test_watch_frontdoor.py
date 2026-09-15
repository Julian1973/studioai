"""Current WATCH authority, exact emission and non-submission recovery; no network."""
from copy import deepcopy
import hashlib
import json
import socket
from types import SimpleNamespace

import pytest
import cb_recovery as recovery
import studio_prompt_director as PD
import studio_seedance_execution as E
import studio_watch_plan as P
from studio_character_roles import audit
from studio_authored_action import actions, proof
from test_studio_seedance_execution import compact_source
from test_approved_media_projection import media


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: pytest.fail('Network forbidden'))
    import cb_llm
    monkeypatch.setattr(cb_llm, 'structured_with_repair', lambda *a, **k: pytest.fail('Model call forbidden'))


@pytest.fixture
def current(compact_source):
    source = deepcopy(compact_source)
    shot = source['authorities']['shot']
    directed = source['authorities']['specialist']['shotPlan']
    shot['directorCard']['audienceFocus'] = 'A hesitant handoff becomes trust.'
    for view, row in zip(shot['directorCard']['views'], directed):
        view.update(action=row['causalAction'], framing=row['framingLensAndCamera'],
                    performance=row['observablePerformance'], endState=row['landingImage'],
                    staging=row['compositionLightAndMaterials'])
    return source


def test_exact_direct_survives_history_and_specialists(current):
    first, evidence = E.compile_prompt(current, audit(current))
    prior = deepcopy(current)
    current['authorities']['specialist'] = {'shotPlan':[{'causalAction':'Invented replacement'}], 'status':'STALE'}
    current['authorities']['shot']['rejectionHistory'] = [{'status':'FAILED'}]
    current['authorities']['shot']['workingSeedancePrompt'] = 'Old rejected prompt'
    second, after = E.compile_prompt(current, audit(current))
    assert first == second
    assert evidence['actionIntegrity'] == after['actionIntegrity']
    assert after['actionIntegrity']['authoredActionHash'] == after['actionIntegrity']['emittedActionHash']
    assert prior['authorities']['shot']['directorCard'] == current['authorities']['shot']['directorCard']


def test_action_drift_blocks(current):
    prompt, evidence = E.compile_prompt(current, audit(current))
    drift = prompt.replace('Mira extends the cup', 'Mira throws the cup')
    with pytest.raises(ValueError, match='WATCH_AUTHORED_ACTION_DRIFT'):
        proof(drift, actions(current['authorities']['shot']))


def test_missing_direct_action_blocks(current):
    current['authorities']['shot']['directorCard']['views'][0].pop('action')
    with pytest.raises(ValueError, match='WATCH_AUTHORED_TIMED_ACTION_MISSING'):
        E.compile_prompt(current, audit(current))


def test_reference_hash_mismatch_blocks(current):
    current['references'][0]['hash'] = 'wrong'
    with pytest.raises(ValueError, match='hash does not match'):
        E.compile_prompt(current, audit(current))


def test_validator_cannot_rewrite(current):
    from test_studio_prompt_director import review
    def reviewer(*args):
        result = review()
        result['planCorrections'] = [dict(expectedPlanHash='wrong',path='/specialist/shotPlan/0/causalAction',expected='old',value='new',sourcePath='/shot/purpose',sourceHash='wrong',reason='rewrite')]
        return result
    original = deepcopy(current)
    final, report = PD.run(current, reviewer)
    assert report['verdict'] != 'READY TO FIRE'
    assert not report['trace']
    assert current == original
    assert final['authorities']['shot']['directorCard'] == original['authorities']['shot']['directorCard']


@pytest.mark.parametrize('label', ['needs-attention','failed','rejected'])
def test_old_failed_prepare_can_start_new_preparation(tmp_path,label):
    args=['cb_studio_director.py','prepare-render','2','S2.SH1','Ep4']
    old=recovery.register(tmp_path,args)
    recovery.change(tmp_path,old['operationId'],label,'old failure',mediaSubmitted=False,providerTaskIds=[])
    fresh=recovery.register(tmp_path,args)
    assert fresh['operationId'] != old['operationId']
    assert fresh['predecessorOperationId'] == old['operationId']
    assert recovery.get(tmp_path,old['operationId'])['state'] == label


def test_unknown_or_active_submission_blocks(tmp_path):
    op=recovery.register(tmp_path,['cb_studio_director.py','prepare-render','2','S2.SH1','Ep4'])
    recovery.change(tmp_path,op['operationId'],'needs-attention','provider accepted',mediaSubmitted=True,providerTaskIds=['provider-123'])
    with pytest.raises(ValueError,match='provider submission'):
        recovery.require_no_provider_operation(tmp_path,'Ep4','2','S2.SH1')
    assert not recovery.pre_submit_failure(recovery.get(tmp_path,op['operationId']))


def test_specialist_history_does_not_change_fingerprint(tmp_path,current):
    shot=deepcopy(current['authorities']['shot']);shot['shotId']='S2.SH1'
    pkg={'shots':[shot],'continuityLedger':[{'shotId':'S2.SH1'}]}
    desc={'episode':'Ep4','scene':'2','shotId':'S2.SH1','kind':'prepare-render'}
    first=recovery.request_fingerprint(tmp_path,desc,pkg)
    pkg['continuityLedger'][0].update(departmentWork={'cinematography':{'candidate':{'output':{'camera':'old'}}}},workingSeedancePrompt={'text':'old'},watchDirectorFeedback={'text':'old'})
    assert first == recovery.request_fingerprint(tmp_path,desc,pkg)


@pytest.fixture
def s2_source(tmp_path):
    """S2's four approved DIRECT views; synthetic media, no production approval records."""
    shot = {'shotId': 'S2.SH1',
     'durationSec': 13.0,
     'charactersInFrame': ['Aida'],
     'dialogueLines': [{'speaker': 'Aida',
                        'exactText': 'Someone’s day might be a little dampened.',
                        'startSec': 7.8,
                        'endSec': 10.36,
                        'dialogueOccurrenceId': 'dialogue-occurrence:sha256:2ccf5f5a5784f7ac8f8638e45739aa99ffc051f6f822dc609224c57244294524'}],
     'directorCard': {'audienceFocus': 'Sunny’s party is a temporary vision in the water: clear water first, vision '
                                       'appears, raindrop interrupts it, vision disappears completely before Aida '
                                       'speaks.',
                      'views': [{'viewId': 'S2.V01',
                                 'timing': '0–3s',
                                 'atSec': 0.0,
                                 'action': 'Hold clear water for 1.2 seconds. Then Sunny’s party vision appears '
                                           'gradually within the water only; it is fully readable by 3.0 seconds.',
                                 'framing': 'Use the unchanged approved opening composition, Aida at the near left '
                                            'bank and the pool readable. Preserve the camera while the vision '
                                            'appears.',
                                 'performance': 'Attention on the reflection; warm protective stillness; no fixing '
                                                'action, no reaching into the water.',
                                 'endState': 'Aida remains seated. Sunny’s party vision is readable in the still '
                                             'pool.',
                                 'startState': 'Aida sits on the near mossy bank at frame left beside clear, still '
                                               'water. Only the ordinary grove and sky are reflected. No Sunny or '
                                               'party vision is visible at frame one. Match the unchanged approved '
                                               'EP3 opening image.',
                                 'entry': 'opening',
                                 'visibleEntities': ['character:Aida',
                                                     'costume:AidaRobe',
                                                     'environment:clearPool',
                                                     'environment:mossyNearBank',
                                                     'background:ordinaryGrove',
                                                     'background:sky',
                                                     'reflection:ordinaryGroveSky',
                                                     'vision:SunnyPartyInPool'],
                                 'staging': 'Aida sits on the near mossy bank at frame left beside clear, still '
                                            'water. Only the ordinary grove and sky are reflected. No Sunny or party '
                                            'vision is visible at frame one. Match the unchanged approved EP3 opening '
                                            'image.'},
                                {'viewId': 'S2.V02',
                                 'timing': '3–4.5s',
                                 'atSec': 3.0,
                                 'action': 'Raindrop hits. Rings form and begin to warp the bright reflection.',
                                 'framing': 'Close pool-surface view of the raindrop striking inside the reflected '
                                            'party image.. Make the physical cause of the emotional turn readable.',
                                 'performance': 'No visible character performance is required in this insert; Aida’s '
                                                'restraint is expressed by not interrupting the water’s action.',
                                 'endState': 'First ripple rings spread and deform the reflected party.',
                                 'startState': 'Raindrop just above still water; party reflection whole beneath it.',
                                 'entry': 'cut',
                                 'visibleEntities': ['environment:clearPool',
                                                     'vision:SunnyPartyInPool',
                                                     'weather:firstRaindrop',
                                                     'effect:poolRippleRings'],
                                 'staging': 'The raindrop falls into the reflected party area of the pool. The '
                                            'surface contact point stays visible.'},
                                {'viewId': 'S2.V03',
                                 'timing': '4.5–7.8s',
                                 'atSec': 4.5,
                                 'action': 'The rings widen; Sunny and all party objects dissolve completely by 7.0 '
                                           'seconds. Only ordinary grove and sky reflections remain. Aida responds '
                                           'with a tiny delayed breath and softened eyes, briefly checks the sky, '
                                           'then returns her gaze to the water before speaking.',
                                 'framing': 'Pool-dominant view with Aida at the same bank; show the vision vanish '
                                            'completely as the rings settle.',
                                 'performance': 'Aida’s thought is visible through restraint: a tiny delayed breath, '
                                                'a minute softening around the eyes, then continued stillness.',
                                 'endState': 'Sunny’s party vision is completely absent; ordinary grove and sky are '
                                             'reflected in the settling water.',
                                 'startState': 'Ripple rings expanding; party reflection still partly legible.',
                                 'entry': 'cut',
                                 'visibleEntities': ['character:Aida',
                                                     'environment:clearPool',
                                                     'vision:SunnyPartyInPool',
                                                     'effect:poolRippleRings',
                                                     'reflection:ordinaryGroveSky',
                                                     'background:ordinaryGrove',
                                                     'background:sky'],
                                 'staging': 'Aida remains seated beside the pool. The widening rings distort the '
                                            'vision within the water.'},
                                {'viewId': 'S2.V04',
                                 'timing': '7.8–13s',
                                 'atSec': 7.8,
                                 'action': 'Aida says exactly “Someone’s day might be a little dampened.” at '
                                           '7.80–10.36 using the approved audio, then quietly rises, brushes herself '
                                           'down once, and stands calmly.',
                                 'framing': 'Restrained medium/profile view of Aida beside the pool, leaving ordinary '
                                            'water visible and enough framing for her quiet rise.',
                                 'performance': 'Attention remains on the pool before and during the line; the voice '
                                                'is low and sensory. Maintain the softened expression established in '
                                                'the preceding view, with quiet, restrained delivery.',
                                 'endState': 'The Sunny party vision has disappeared completely. Only ordinary grove '
                                             'and sky reflections remain in the clear pool as the small ripples '
                                             'settle. After her approved line Aida quietly rises, brushes herself '
                                             'down once and stands calmly beside the pool.',
                                 'startState': 'Sunny’s party vision is completely absent; ordinary grove and sky are '
                                               'reflected in the settling water.',
                                 'entry': 'cut',
                                 'visibleEntities': ['character:Aida',
                                                     'costume:AidaRobe',
                                                     'environment:clearPool',
                                                     'effect:poolRippleRings',
                                                     'reflection:ordinaryGroveSky',
                                                     'vision:SunnyPartyInPool',
                                                     'environment:mossyNearBank',
                                                     'background:ordinaryGrove',
                                                     'background:sky'],
                                 'staging': 'Aida remains at the same pool edge. No Sunny or party objects are '
                                            'present, in the water or physically beside the pool.'}]}}
    refs=[]
    for index,role in enumerate(('opening keyframe','Aida','scene plate','vision:Sunny party reflection'),1):
        path=tmp_path/f's2-reference-{index}.png'
        path.write_bytes(role.encode())
        refs.append({'slot':f'@图{index}','role':role,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    audio=tmp_path/'s2-approved-audio.wav'
    audio.write_bytes(b'synthetic Audio1 fixture')
    source=PD.request_snapshot(PD.audio_policy(True),{'shot':shot},refs,
        {'path':str(audio),'sha256':hashlib.sha256(audio.read_bytes()).hexdigest()},13,{'provider':'byteplus'})
    source['prompt']=PD.compile_native_source(shot,refs,source['audio'])
    return source


@pytest.fixture
def route(monkeypatch,tmp_path,s2_source):
    """Exercise the real preparation entry; external adapters expose explicit states."""
    current=s2_source
    import cb_render as R
    import cb_providers
    import studio_see_service as SEE
    import studio_director_handoff as H
    shot=deepcopy(current['authorities']['shot']);shot['shotId']='S2.SH1'
    pkg={'shots':[shot],'continuityLedger':[{'shotId':'S2.SH1','keyframeApproval':{'approved':True,'path':'opening.png'}}]}
    state={'direct':[], 'see':True, 'audio':True, 'preview':None}
    monkeypatch.setattr(R,'ROOT',tmp_path)
    monkeypatch.setattr(R,'load_pkg',lambda *a:(pkg,tmp_path/'package.json'))
    monkeypatch.setattr(cb_providers,'video_model',lambda **k:SimpleNamespace(provider='byteplus'))
    monkeypatch.setattr(R,'_require_confirmed_billing',lambda *a:None)
    monkeypatch.setattr(H,'errors',lambda s:state['direct'])
    monkeypatch.setattr(H,'card_issues',lambda s:[])
    monkeypatch.setattr(R,'prepare_department',lambda *a,**k:pytest.fail('Specialist regeneration forbidden'))
    monkeypatch.setattr(R,'review_see_action_readiness',lambda *a,**k:pytest.fail('New recognition forbidden'))
    monkeypatch.setattr(R,'_voice_approval_status',lambda *a:{'current':state['audio'],'reason':'dialogue revision changed'})
    def see(*a,**k):
        if not state['see']:raise ValueError('Opening Keyframe is bound to DIRECT revision X but current DIRECT is Y.')
        return {'ready':True,'approved':True}
    monkeypatch.setattr(SEE,'gate',see)
    def disclose(*a,**k):
        assert k['spend_token'] is None
        prompt, evidence=E.compile_prompt(current,audit(current))
        state['preview']={'prompt':prompt,'actionIntegrity':evidence['actionIntegrity']}
        pkg['continuityLedger'][0]['pendingSpendAuth']={'envelopeHash':'fixture-preview'}
        raise R.Refused('SPEND NOT APPROVED')
    monkeypatch.setattr(R,'fire_shot',disclose)
    return state


def test_s2_route_reaches_preview_without_specialist_or_provider(route):
    import cb_studio_director as D
    D.prepare_render('2','S2.SH1','Ep4')
    assert route['preview']['actionIntegrity']['status'] == 'PASS'
    assert len(route['preview']['actionIntegrity']['views']) == 4
    assert 'Hold clear water for 1.2 seconds.' in route['preview']['prompt']
    assert 'Sunny and all party objects dissolve completely by 7.0 seconds.' in route['preview']['prompt']


@pytest.mark.parametrize('field,value,message',[
 ('direct',['Current DIRECT revision is stale'],'DIRECTOR_REVISION_REQUIRED'),
 ('see',False,'Opening Keyframe is bound to DIRECT revision X'),
 ('audio',False,'Audio1 is not bound'),
])
def test_current_authority_blockers(route,field,value,message):
    import cb_studio_director as D
    import cb_render as R
    route[field]=value
    with pytest.raises(R.Refused,match=message):D.prepare_render('2','S2.SH1','Ep4')
    assert route['preview'] is None


def test_insufficient_authorization_never_calls_provider(tmp_path):
    from studio_journey_worker import spending
    from studio_journey import DecisionRequired
    import cb_episode_budget as B
    op={'id':'fixture','grant':{'limitUsd':0,'operations':['animation'],'maxMediaCalls':1}}
    with spending(tmp_path,op), pytest.raises(DecisionRequired,match='exceed the cost'):
        B.reserve('Ep4',1,'animation')


def test_audio_projection_preserves_direct_binding_and_rejects_later_edits(media):
    from studio_director_handoff import errors, source, VERSION, digest
    from studio_approved_media_projection import watch_shot
    shot, ledger = media
    shot['directorCard']={'views':[{'viewId':'S2.V01','timing':'0–16s','action':'Hold clear water.'}]}
    shot['directorCardSource']={'version':VERSION,'sourceHash':digest(source(shot)),
                                'directionHash':digest(shot['directorCard'])}
    original=deepcopy(shot)
    projected=watch_shot(shot,ledger)
    assert not errors(projected)
    assert shot == original
    assert watch_shot(projected,ledger) == projected
    projected['directorCard']['views'][0]['action']='Different action'
    assert errors(projected)
    with pytest.raises(ValueError,match='DIRECTOR_REVISION_REQUIRED'):
        watch_shot(projected,ledger)


def test_validator_rejects_replacement_payload_without_rewriting(current):
    current['prompt'] = E.compile_prompt(current, audit(current))[0] + '\nInvented action.'
    final, report = PD.run(current, None)
    assert report['verdict'] == 'WATCH_CONFIGURATION_REQUIRED'
    assert final['prompt'] == current['prompt']


def test_retake_requires_direct_revision_without_specialist_or_state_write(monkeypatch):
    import cb_studio_director as D
    import cb_render as R
    import inspect
    monkeypatch.setattr(R, '_save', lambda *a: pytest.fail('No production write'))
    monkeypatch.setattr(R, 'prepare_department', lambda *a: pytest.fail('No specialist call'))
    with pytest.raises(R.Refused, match='DIRECTOR_REVISION_REQUIRED'):
        inspect.unwrap(D.retake_render)('2', 'S2.SH1', 'Change performance', 'Ep4', expected_batch_id='old')


@pytest.mark.parametrize('submitted,allowed', [(False, True), (True, False), (None, False)])
def test_journey_reads_submission_evidence_without_changing_history(tmp_path,submitted,allowed):
    from studio_journey import Journey
    args=['cb_studio_director.py','prepare-render','2','S2.SH1','Ep4']
    old=recovery.register(tmp_path,args)
    recovery.change(tmp_path,old['operationId'],'needs-attention','Historical verdict', mediaSubmitted=submitted,
                    providerTaskIds=['accepted-task'] if submitted else [])
    before=recovery.read_operations(tmp_path)
    journey=Journey(SimpleNamespace(root=tmp_path), None)
    scope={'projectId':'crystal-bears','episode':'Ep4','scene':'2','unit':'S2.SH1'}
    state={'scope':scope,'revision':1,'actions':1,'corrections':0,
           'operation':{'id':'journey-1','status':'needs-decision','pending':'prepare_render',
                        'blockedBinding':'current','receipts':{'prepare_render':{'jobId':old['jobId']}}}}
    view=journey._view(state,{'phase':'audio','binding':'current','review':{},'disclosure':{'limitUsd':1}})
    assert bool(view['primary']) is allowed
    assert recovery.read_operations(tmp_path)==before
    assert state['operation']['status']=='needs-decision'
