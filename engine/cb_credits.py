"""Episode credits: saved choices, sealed one-candidate spend and recoverable review jobs.

Provider submission is owned by cb_render, just like scene production. Credits are
an independent episode artifact and never change scene approvals or source masters.
"""
from contextlib import contextmanager
from pathlib import Path
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
class ProviderFailure(RuntimeError):
    pass


ACTIVE = {'starting', 'submitting', 'queued', 'running', 'downloading', 'compositing'}
DEFAULT_CARDS = [
    ['CREATED BY', 'Lloyd Knight & Julian Jenkins'],
    ['WRITTEN BY', 'Lloyd Knight & Pete Young'],
    ['VOICE CAST', 'Lloyd Knight\nPete Young\nJulian Jenkins'],
    ['ANIMATION & VISUAL PRODUCTION', 'Julian Jenkins\nLloyd Knight\nPete Young'],
    ['MUSIC & SOUND', 'Julian Jenkins & Lloyd Knight'],
    ['WITH THANKS TO', 'Mike Young & Liz Young\nand everyone who believed in the magic.'],
    ['AN ENAID CREATIVE PRODUCTION', '© 2026 Enaid Creative. All rights reserved.'],
]
TIMES = [(0,4),(4,8),(8,12),(12,17),(17,21),(21,26),(26,30)]

def episode_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'Ep[1-9][0-9]{0,3}', value):
        raise ValueError('Choose a valid episode.')
    return value

def folder(episode):
    p = ROOT / 'cb-output/credits' / episode_id(episode)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default

def _write(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    tmp.replace(path)

@contextmanager
def locked(episode):
    with (folder(episode)/'.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield

def _hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def _asset(path):
    p = Path(path).resolve()
    if not p.is_relative_to(ROOT) or not p.is_file():
        raise ValueError('The approved character reference is unavailable.')
    return {'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}

def characters():
    data = _read(ROOT/'shows/crystal-bears/canon/characters.json', {})
    result = []
    for name, info in data.items():
        if not isinstance(info, dict) or not info.get('turnaround'):
            continue
        path = (ROOT/'engine'/str(info.get('render_ref') or info['turnaround'])).resolve()
        if name == 'Bo':
            path = ROOT/'cb-seed/assets/final_turnarounds/CB_Bo_with_satchel.png'
        if path.is_relative_to(ROOT) and path.is_file():
            result.append({'name': name, 'label': 'Bo · with satchel' if name == 'Bo' else name,
                           'reference': '/'+str(path.relative_to(ROOT)),
                           'isBee': bool(info.get('isBee'))})
    return result

def defaults(episode):
    episode_id(episode)
    script = _read(ROOT/f'shows/crystal-bears/episodes/scripts/_current/{episode}.json', {})
    title = re.sub(r'\s+V\d+$', '', script.get('title') or f'Episode {episode[2:]}', flags=re.I)
    return {'title': title, 'character': 'Bo', 'background': '#A41524',
            'cards': [list(row) for row in DEFAULT_CARDS]}

def validate_config(episode, value):
    episode_id(episode)
    if not isinstance(value, dict):
        raise ValueError('Credit choices are required.')
    title = str(value.get('title') or '').strip()
    if not title or len(title)>100 or '\n' in title:
        raise ValueError('Use an episode title of 1–100 characters.')
    character = next((x for x in characters() if x['name']==value.get('character')), None)
    if not character:
        raise ValueError('Choose a character with an available approved reference.')
    colour = str(value.get('background') or '')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', colour):
        raise ValueError('Choose a background colour.')
    cards = value.get('cards')
    if not isinstance(cards, list) or len(cards)!=7:
        raise ValueError('Keep all seven credit cards.')
    clean = []
    for row in cards:
        if not isinstance(row, list) or len(row)!=2 or not all(isinstance(x,str) for x in row):
            raise ValueError('Each credit card needs a heading and names.')
        heading, body = (x.strip() for x in row)
        if not heading or len(heading)>70 or '\n' in heading or not body or len(body)>220 or len(body.splitlines())>4:
            raise ValueError('Use a short heading and up to four lines per credit card.')
        clean.append([heading,body])
    return {'title':title,'character':character['name'],'background':colour.upper(),'cards':clean}, character

def prompt_for(config, character):
    name = config['character']
    movement = ('hover gently in place with natural wingbeats, use expressive wing/body tilts and small aerial bows'
                if character['isBee'] else 'stand with grounded feet, use open-hand presentation gestures, a small bow and one jaunty side-step within the stage mark')
    return f'''Create one continuous 30-second silent 3D animated end-credit presenter plate.
@Image1 is the approved {name} character reference. Its multiple views depict ONE character. Preserve exact identity, proportions, costume and accessories; never reproduce the reference sheet or labels.
Use the established warm tactile Crystal Bears animation aesthetic. Exactly one {name} is visible.
Locked wide 16:9 camera. Seamless studio background and matching floor in colour {config['background']}. Soft frontal light, gentle spotlight and subtle contact shadows. Show the full character and all extremities comfortably inside the LEFT THIRD. Keep every gesture left of the centre line. The RIGHT TWO THIRDS are empty for credits.
{name} is a playful, warm silent presenter: {movement}. Look between the audience and the empty space to frame-right, presenting the changing cards. Mouth stays naturally closed; facial expression remains lively. Keep movement charming, readable and unhurried.
0–4s: welcome the audience, then present the right-hand space.
4–8s: a small courteous bow, rise and present the next card.
8–12s: a playful sequential presenting flourish to the right.
12–17s: a jaunty movement within the left-third stage mark, settle and present proudly.
17–21s: a gentle rhythmic bounce or hover bob, followed by another rightward presenting gesture.
21–26s: an appreciative nod and warm gesture of thanks toward the credits.
26–30s: one slow friendly farewell wave or equivalent wing gesture, settle by 29s and hold the smiling living pose through the end.
No text, lettering, logo, symbols or additional props anywhere: all typography is added separately using the actual font files. No speech, music or sound effects. Character identity and accessories stay stable throughout.'''

def _state(episode):
    return _read(folder(episode)/'current.json', {})

def update(episode, **values):
    with locked(episode):
        state = _state(episode)
        state.update(values, updatedAt=time.time())
        _write(folder(episode)/'current.json', state)
        if state.get('id'):
            _write(folder(episode)/(state['id']+'.json'), state)
        return state

def _alive(pid):
    try:
        os.kill(int(pid),0)
        return True
    except (OSError,TypeError,ValueError):
        return False

def status(episode):
    s = _state(episode)
    public = {k:v for k,v in s.items() if k not in ('envelope','token')}
    if s.get('status')=='prepared':
        public['token'] = s['token']
    public['canResume'] = bool(s.get('status') in ACTIVE|{'interrupted'} and
                               s.get('providerTaskId') and not _alive(s.get('pid')))
    if s.get('status') in ACTIVE and not _alive(s.get('pid')):
        public['status'] = 'interrupted'
        public['error'] = 'The worker stopped. Resume the existing provider job.' if s.get('providerTaskId') else 'Submission was interrupted before a job ID was saved. Check the provider before attempting another render.'
    accepted = _read(folder(episode)/'accepted.json', {})
    return {'ok':True,'episode':episode,'defaults':defaults(episode),'characters':characters(),
            'acceptedVideoUrl':accepted.get('videoUrl'),**public}

def prepare(episode, config):
    import cb_providers, cb_costs, cb_db
    config, character = validate_config(episode, config)
    contract = cb_providers.request_contract(duration=30,resolution='480p',image_count=1,
                                            model_id='dreamina-seedance-2-5-260628')
    billing = cb_costs.load_billing_profile('byteplus') or {}
    if not (billing.get('planConfirmed') and billing.get('cadenceConfirmed')):
        raise ValueError('Confirm BytePlus billing in Studio settings before rendering.')
    from cb_credits_compose import check_fonts
    fonts = check_fonts(ROOT)
    reference = _asset(ROOT/character['reference'].lstrip('/'))
    envelope = {'candidateCount':1,'config':config,'reference':reference,'fonts':fonts,
                'prompt':prompt_for(config,character),'contract':contract,'duration':30,
                'generateAudio':False,'maxBatchCostUsd':round(cb_costs.estimate_video_cost(contract['costRateKey'],30),4)}
    with locked(episode):
        old = _state(episode)
        if old.get('status') in ACTIVE|{'interrupted'}:
            raise ValueError('Finish or recover the current credits job before preparing another.')
        job = uuid.uuid4().hex
        from cb_credits_compose import make_cards
        preview = make_cards(ROOT,episode,config,ROOT/'engine/media/credits_maker'/episode/job/'cards')
        digest = _hash(envelope)
        token = uuid.uuid4().hex
        disclosure = {'candidateCount':1,'duration':30,'resolution':'480p',
                      'provider':'Seedance 2.5','maxBatchCostUsd':envelope['maxBatchCostUsd']}
        cb_db.issue_spend_authorization(ROOT,episode,'credits','EC01',
            {'token':token,'bindingHash':digest,'envelopeHash':digest,'envelope':envelope,'disclosure':disclosure})
        state = {'id':job,'episode':episode,'status':'prepared','config':config,'token':token,
                 'envelopeHash':digest,'envelope':envelope,'disclosure':disclosure,
                 'referenceUrl':character['reference'],'previewUrl':'/'+str(preview.relative_to(ROOT)),'humanReview':'pending','updatedAt':time.time()}
        _write(folder(episode)/'current.json',state)
        _write(folder(episode)/(job+'.json'),state)
    return status(episode)

def _spawn(episode, state, resume=False):
    logfile = folder(episode)/(state['id']+'.log')
    with logfile.open('a') as log:
        proc = subprocess.Popen([sys.executable,'-u',str(ROOT/'engine/cb_credits.py'),'worker',episode,
                                 state['id'], '--resume' if resume else '--new'],
                                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    state['pid'] = proc.pid
    return proc

def fire(episode, token):
    import cb_db
    with locked(episode):
        state = _state(episode)
        if not token or token!=state.get('token'):
            raise ValueError('This render approval has expired. Preview the credits again.')
        if state.get('status') in ACTIVE|{'awaiting_review','accepted'}:
            return {'ok':True,'id':state['id'],'status':state['status']}
        if state.get('status')!='prepared':
            raise ValueError('Prepare a new credits preview before rendering.')
        envelope = state['envelope']
        if _hash(envelope)!=state['envelopeHash'] or _asset(ROOT/envelope['reference']['path'])!=envelope['reference']:
            raise ValueError('The credits or character reference changed. Preview them again.')
        from cb_credits_compose import check_fonts
        if check_fonts(ROOT)!=envelope['fonts']:
            raise ValueError('The font files changed. Preview the credits again.')
        cb_db.claim_spend_authorization(ROOT, state['token'],episode,'credits','EC01',
                                       state['envelopeHash'],state['envelopeHash'],state['id'])
        cb_db.claim_candidate(ROOT,state['token'],1,state['id'])
        state.update(status='starting',updatedAt=time.time())
        _write(folder(episode)/'current.json',state)
        try:
            _spawn(episode,state)
        except Exception as exc:
            state.update(status='failed',error=f'Could not start credits worker: {exc}')
            cb_db.fail_candidate(ROOT,state['token'],1,str(exc))
            _write(folder(episode)/'current.json',state)
            raise
        _write(folder(episode)/'current.json',state)
    return status(episode)

def resume(episode):
    with locked(episode):
        s = _state(episode)
        if not s.get('providerTaskId') or s.get('status') not in ACTIVE|{'interrupted'}:
            raise ValueError('There is no interrupted provider job to resume.')
        if not _alive(s.get('pid')):
            s['status']='starting'
            _spawn(episode,s,True)
            _write(folder(episode)/'current.json',s)
    return status(episode)

def verdict(episode, job, accept):
    with locked(episode):
        s = _state(episode)
        if s.get('id')!=job or s.get('status')!='awaiting_review':
            raise ValueError('Open the current credits candidate before reviewing it.')
        s.update(status='accepted' if accept else 'rejected',humanReview='accepted' if accept else 'rejected',reviewedAt=time.time())
        _write(folder(episode)/'current.json',s)
        _write(folder(episode)/(s['id']+'.json'),s)
        if accept:
            _write(folder(episode)/'accepted.json',s)
    return status(episode)

def _retrieve(episode, state, output):
    """Only GET an already accepted provider job after worker/server interruption."""
    import cb_gen
    endpoint = cb_gen._byteplus_task_url(state['envelope']['contract']['endpoint'])
    headers = {'Authorization':'Bearer '+cb_gen.BYTEPLUS_ARK_KEY}
    deadline = time.monotonic()+3600
    while time.monotonic()<deadline:
        response = cb_gen._rget(endpoint+'/'+state['providerTaskId'],headers=headers,timeout=(20,120))
        response.raise_for_status()
        task = response.json()
        phase = task.get('status')
        if phase=='succeeded':
            update(episode,status='downloading')
            url = (task.get('content') or {}).get('video_url')
            if not url:
                raise ValueError('Provider returned no video URL.')
            response = cb_gen._rget(url,timeout=(20,300));response.raise_for_status()
            output.write_bytes(response.content)
            return
        if phase in ('failed','expired'):
            raise ProviderFailure('Provider job '+str(phase)+': '+str(task.get('error') or ''))
        if phase not in ('queued','running'):
            raise ValueError('Provider job '+str(phase)+': '+str(task.get('error') or ''))
        update(episode,status=phase)
        time.sleep(10)
    raise TimeoutError('Provider is still running; resume this job later.')

def run_worker(episode, job, resume_existing=False):
    import cb_gen, cb_db, cb_costs, cb_render
    s = _state(episode)
    if s.get('id')!=job or s.get('status')!='starting':
        raise ValueError('Credits worker no longer owns this job.')
    envelope = s['envelope']
    if _hash(envelope) != s['envelopeHash']:
        raise ValueError('The sealed credits request has changed.')
    output = ROOT/'engine/media/credits_maker'/episode/job
    output.mkdir(parents=True,exist_ok=True)
    plate = output/'presenter.mp4'
    def progress(event):
        values = {'status':event.get('status') or event['event']}
        if values['status'] in ('submitted','poll'):
            values['status']='queued'
        if values['status']=='downloaded':
            values['status']='compositing'
        if event.get('taskId'):
            values['providerTaskId']=event['taskId']
        update(episode,**values)
    try:
        if resume_existing:
            _retrieve(episode,s,plate)
            # A resumed retrieval must still record its estimated generation cost once.
            if not _state(episode).get('costLogged'):
                cb_costs.log_spend('seedance_ref2vid',envelope['maxBatchCostUsd'],out=str(plate),meta={'provider':'byteplus','providerTaskId':s['providerTaskId']})
                update(episode,costLogged=True)
        else:
            cb_render._submit_seedance_provider(envelope['prompt'],[str(ROOT/envelope['reference']['path'])],
                resolution='480p',duration=30,out=str(plate),raw_prompt=True,production_route='cb_render',
                model_id=envelope['contract']['providerModelId'],generate_audio=False,progress_callback=progress)
            update(episode,costLogged=True)
        update(episode,status='compositing')
        from cb_credits_compose import compose
        result = compose(ROOT,episode,envelope['config'],plate,output)
        cb_db.complete_candidate(ROOT,s['token'],1,str(result))
        cb_db.complete_spend_authorization(ROOT,s['token'])
        update(episode,status='awaiting_review',videoUrl='/'+str(result.relative_to(ROOT)),
               humanReview='pending',error=None)
    except ProviderFailure as exc:
        cb_db.fail_candidate(ROOT,s['token'],1,str(exc))
        update(episode,status='failed',error=str(exc))
    except (TimeoutError,ConnectionError) as exc:
        update(episode,status='interrupted',error=str(exc))
    except Exception as exc:
        # Once a provider ID exists, recovery is retrieval/composition only, never automatic repayment.
        if re.search(r'BytePlus video task (failed|expired):', str(exc)):
            cb_db.fail_candidate(ROOT,s['token'],1,str(exc))
            update(episode,status='failed',error=str(exc))
        elif _state(episode).get('providerTaskId'):
            update(episode,status='interrupted',error=str(exc))
        else:
            update(episode,status='interrupted',error='Submission interrupted; check provider before any new render. '+str(exc))
        raise

if __name__=='__main__':
    if len(sys.argv)!=5 or sys.argv[1]!='worker':
        raise SystemExit('Use the Studio credits maker to prepare and approve a render.')
    import cb_render
    cb_render.render_credits_job(sys.argv[2],sys.argv[3],sys.argv[4]=='--resume')
