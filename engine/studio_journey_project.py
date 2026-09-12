"""Same producer journey, existing project production commands and job ledger."""
import json
from copy import deepcopy
from studio_journey import digest, DecisionRequired
from studio_production import Production, money
from studio_workspace import StudioError


class Services(Production):
    def __init__(self, *args, operation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.operation = operation

    def advance(self, *args):
        # The journey owns sequencing. Individual approvals must not launch the
        # following department again outside its disclosed operation.
        return

    def _job(self, db, job):
        op = self.operation
        if job.get('status') == 'queued':
            if not op:
                raise StudioError('A current producer action is required.')
            jobs = [json.loads(r[0]) for r in db.execute('SELECT data FROM jobs WHERE project=? AND episode=?',(job['projectId'],job['episode']))]
            previous = [j for j in jobs if j.get('journeyOperation')==op['id'] and j['id']!=job['id']]
            if sum(j['estimate'] for j in previous)+job['estimate'] > int(op['grant']['limitUsd']*1000000):
                raise StudioError('This action exceeds its disclosed cost. Review an updated cost before continuing.')
            if job['kind'] in {'see','hear','watch'} and sum(j['kind'] in {'see','hear','watch'} for j in previous)>=op['grant'].get('maxMediaCalls',1):
                raise StudioError('This action already owns a media request. Recover that request instead of submitting again.')
            job['journeyOperation']=op['id']
        return super()._job(db,job)


class Project:
    def __init__(self, root, workspace, *, transport=None, background=True):
        self.root,self.ws,self.transport,self.background = root,workspace,transport,background

    def service(self, op=None):
        return Services(self.ws,transport=self.transport,background=self.background,operation=op)

    def snapshot(self, scope):
        P = self.service()
        snap = P.snapshot(scope['projectId'],scope['episode'])
        state = snap['state']
        shot = next((s for s in state['shots'] if s['id']==scope['unit']),None)
        phase = 'prepare'
        review = {'title':'Scene direction','plan':state.get('sceneCoverage',[]),'images':[],'audio':None,'videos':[],
                  'script':[], 'sourceHash':snap['sourceHash']}
        has_audio = True
        if shot:
            has_audio = bool(shot.get('dialogue'))
            artifacts = {s:P.artifact(shot,s) for s in ('see','hear','request','watch')}
            field = __import__('studio_editing').fields(shot)
            review.update(title=shot.get('title') or shot.get('intent'),direction=shot.get('intent') or shot.get('action'),
                          script=shot.get('dialogue'),source=field,actionPlan=[{'timing':v.get('timing',''),'action':v.get('action','')} for v in shot.get('directorCard',{}).get('views',[])],plan=shot.get('directorCard',{}).get('views',[]))
            def media(item):
                return [{**f,'url':'/' + f['path']} for f in (item or {}).get('files',[])]
            review['images']=media(artifacts['see'])[:1];review['videos']=media(artifacts['watch'])[:1]
            review['audio']=(media(artifacts['hear']) or [None])[0]
            review['outcomes']={s:deepcopy(a) for s,a in artifacts.items()}
            done=lambda stage: bool(artifacts[stage] and artifacts[stage]['status']=='approved')
            phase = ('complete' if done('watch') else 'film' if artifacts['watch'] and artifacts['watch']['status']=='candidate'
                     else 'audio' if done('see') and (artifacts['hear'] or not has_audio)
                     else 'images' if artifacts['see'] else 'plan')
        dependency=None
        if shot:
            from studio_director_card import inherits_previous_state
            index=state['shots'].index(shot)
            if index and inherits_previous_state(shot):
                prior=state['shots'][index-1]
                if prior['scene']==shot['scene'] and (P.artifact(prior,'watch') or {}).get('status')!='approved':
                    dependency='Approve '+prior['id']+' and its ending before this opening.'
                    phase='dependency'
        limit = max(0,(state['budget']['allowance']-state['budget']['reserved']-state['budget']['committed'])/1000000)
        steps = {'prepare':['direction'],'plan':['keyframe'],'images':['voice'] if has_audio else ['direction','animation'],
                 'audio':['direction','animation','review']}.get(phase,[])
        preserved=[s.upper() for s in ('see','hear') if shot and (P.artifact(shot,s) or {}).get('status')=='approved']
        next_scope=None
        if shot and state['shots'].index(shot)+1 < len(state['shots']):
            following=state['shots'][state['shots'].index(shot)+1]
            next_scope={**scope,'scene':str(following['scene']),'unit':following['id']}
        concerns=[]
        if shot and review['videos']:
            from studio_media_review import current_reports
            reports=current_reports(P,self.ws.context(scope['projectId'],scope['episode']),state,shot)
            concerns=[f['observation'] for r in reports if r.get('current') for f in r.get('findings',[])]
            if not any(r.get('current') for r in reports):concerns=['Returned footage has not received a current automated review.']
        return {'concerns':concerns,'phase':phase,'binding':digest(review),'requiresAudio':has_audio,'review':review,
                'disclosure':{'limitUsd':limit if steps else 0,'operations':steps,'maxMediaCalls':1,
                              'basis':'Within the remaining configured episode allowance. No automatic paid rerolls.'},
                'preserved':preserved,'next':next_scope,'dependency':dependency}

    def execute(self, scope, step, op):
        P=self.service(op);pid,ep=scope['projectId'],scope['episode']
        snap=P.snapshot(pid,ep);state=snap['state'];shot=next((s for s in state['shots'] if s['id']==scope['unit']),None)
        if shot and op['review'].get('source') and __import__('studio_editing').fields(shot)!=op['review']['source']:
            raise DecisionRequired('The shot direction changed during this action.','Review its current version.')
        if step=='approve_plan':
            with self.ws.db() as db:
                db.execute('BEGIN IMMEDIATE');current=P._load(db,pid,ep)
                selected=P.selected(current,scope['unit'])
                if __import__('studio_editing').fields(selected)!=op['review']['source']:
                    raise ValueError('Plan changed after review')
                selected['planDecision']={'approved':True,'actor':op['actor'],'operation':op['id'],'source':digest(op['review']['source'])}
                P._save(db,pid,ep,current)
            return {'status':'complete'}
        if step in ('review_images','review_audio','align_timing','assemble','prepare_next'):
            # Existing provider jobs verify returned media; request preparation runs
            # measured voice timing and image readiness before its final compiler.
            return {'status':'complete'}
        if step=='review_film':
            from studio_media_review import manifest
            manifest(P,self.ws.context(pid,ep),state,shot)
            result=P.command({'projectId':pid,'episode':ep,'shotId':scope['unit'],'action':'media_review',
                'commandId':op['id']+'_'+step,'expectedRevision':state['revision'],'reviewId':P.artifact(shot,'watch')['id']})
            return {'status':'pending' if result.get('jobId') else 'complete',**result}
        if step.startswith('approve_'):
            stage={'approve_images':'see','approve_audio':'hear','approve_film':'watch'}[step]
            item=P.artifact(shot,stage)
            if stage=='hear' and not shot['dialogue']:
                return {'status':'complete'}
            if item and item['status']=='approved':return {'status':'complete'}
            expected=(op['review'].get('outcomes') or {}).get(stage)
            if not item or not expected or item['id']!=expected['id']:
                raise DecisionRequired('The media changed after your review.','Review the current candidate.')
            action='approve';extra={'reviewId':item['id']}
        else:
            action={'prepare_plan':'prepare','create_images':'see','create_audio':'hear',
                    'prepare_render':'request','submit_render':'watch'}[step];extra={}
            stage={'see':'see','hear':'hear','request':'request','watch':'watch'}.get(action)
            item=P.artifact(shot,stage) if shot and stage else None
            if step=='create_audio' and item and item['status']=='approved':return {'status':'complete'}
            if step=='submit_render':
                req=P.artifact(shot,'request')
                if not req:raise ValueError('No reviewed animation request')
                # This is the recorded Action 4 authorisation, not a new human
                # judgement of model-written prose. The existing request seal remains.
                if req['status']=='candidate':
                    P.command({'projectId':pid,'episode':ep,'shotId':scope['unit'],'action':'approve',
                        'reviewId':req['id'],'commandId':op['id']+'_request','expectedRevision':state['revision']})
                    state=P.snapshot(pid,ep)['state']
                extra={'reviewId':req['id']}
        result=P.command({'projectId':pid,'episode':ep,'shotId':scope['unit'] if shot else '',
            'action':action,'commandId':op['id']+'_'+step,'expectedRevision':state['revision'],**extra})
        return {'status':'pending' if result.get('jobId') else 'complete',**result}

    def reconcile(self, scope, step, op):
        pid,ep=scope['projectId'],scope['episode'];P=self.service(op)
        command_id=op['id']+'_'+step
        with self.ws.db() as db:
            row=db.execute('SELECT result FROM commands WHERE project=? AND episode=? AND id=?',(pid,ep,command_id)).fetchone()
            if not row:raise DecisionRequired('No completed command receipt is recorded.','Recover this operation before starting another.')
            result=json.loads(row[0]);job_id=result.get('jobId')
            jobrow=db.execute('SELECT data FROM jobs WHERE id=? AND project=? AND episode=?',(job_id,pid,ep)).fetchone() if job_id else None
        if not jobrow:return {'status':'complete'}
        job=json.loads(jobrow[0]);status=job['status']
        if status=='completed':return {'status':'complete','jobId':job_id}
        if status=='pending' and job.get('taskId'):
            # The existing resume branch only polls its confirmed provider task.
            # Bind the poll command to this persisted job state so reconnects dedupe.
            P.command({'projectId':pid,'episode':ep,'shotId':scope['unit'],'action':'resume',
                'jobId':job_id,'commandId':op['id']+'_poll_'+digest(job)[:20]})
            return {'status':'pending','jobId':job_id,'message':'Retrieving the existing provider task'}
        if status in ('running','queued','pending'):
            return {'status':'pending','jobId':job_id,'message':job.get('message') or 'Working'}
        raise DecisionRequired(job.get('message') or 'The provider operation requires recovery.',
            'Resolve the conflicting creative direction.' if job.get('code')=='creative_decision_required' else 'Review and authorise a new attempt.' if status=='failed' else 'Check the existing provider task before another submission.',
            evidence={'jobId':job_id},retrySafe=status=='failed' and job.get('code')!='creative_decision_required')
