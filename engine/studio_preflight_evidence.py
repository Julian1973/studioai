"""Durable attempt evidence, including failures before an HTTP request exists."""
from contextvars import ContextVar
from functools import wraps
import inspect,time,uuid
from studio_request_evidence import digest,_write
attempt=ContextVar('production_attempt',default=None)

def review_submission():
    current=attempt.get()
    if current is not None:current["reviewSubmissionAttempted"]=True

def media_submission():
    current=attempt.get()
    if current is not None:
        current['mediaSubmissionAttempted']=True

def protect(runtime,name,fn):
    signature=inspect.signature(fn)
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if attempt.get() is not None:return fn(*args,**kwargs)
        bound=signature.bind_partial(*args,**kwargs);bound.apply_defaults();a=bound.arguments
        scene=a.get('scene');ep=a.get('episode','Ep1');sid=a.get('shot_id')
        pkg={};bindings={};load_error=None
        try:
            pkg,_=runtime.load_pkg(scene,ep)
            led=runtime._ledger(pkg,sid) if sid else {}
            bindings={k:led.get(k) for k in ('keyframeApproval','voiceApproval','voPath','approvedTake','batchId')}
        except Exception as exc:load_error=str(exc)
        record=dict(id=uuid.uuid4().hex,operation=name,scene=scene,episode=ep,shotId=sid,
                    revision=pkg.get('revision'),packageHash=digest(pkg),sourceBindings=bindings,
                    sourceLoadError=load_error,createdAt=time.time(),mediaSubmissionAttempted=False)
        token=attempt.set(record)
        try:return fn(*args,**kwargs)
        except (Exception,SystemExit) as exc:
            record.update(providerCallOccurred=None if record.get('reviewSubmissionAttempted') or record['mediaSubmissionAttempted'] else False,
                          spendOccurred=None if record.get('reviewSubmissionAttempted') or record['mediaSubmissionAttempted'] else False,
                          state='submission-outcome-needs-review' if record['mediaSubmissionAttempted'] else 'blocked-before-media-submission',
                          reason=str(exc),correctiveAction='Resolve the named failure against current inputs and prepare a new sealed request.',
                          mediaProviderCalled=False if not record['mediaSubmissionAttempted'] else None,
                          mediaSpendOccurred=False if not record['mediaSubmissionAttempted'] else None,
                          reviewProviderSpend='not-inferred; consult text/image review usage records')
            _write(runtime.HERE.parent/'cb-output/state/preflight-attempts'/(record['id']+'.json'),record)
            raise
        finally:attempt.reset(token)
    return wrapped

def project_failure(production,payload,exc,job=None):
    pkg={}
    try:
        with production.ws.db() as db:pkg=production._load(db,payload.get('projectId'),str(payload.get('episode')))
    except Exception:pass
    job=job or {}; active=attempt.get() or {}
    submitted=job.get('mediaSubmissionAttempted',False) or active.get('mediaSubmissionAttempted',False)
    reviewed=job.get('reviewSubmissionAttempted',False) or active.get('reviewSubmissionAttempted',False)
    record=dict(id=uuid.uuid4().hex,state='submission-outcome-needs-review' if submitted else 'blocked-before-media-submission',
                reason=str(exc),revision=pkg.get('revision'),packageHash=digest(pkg),
                sourceBindings=job.get('inputs') or {'shotId':payload.get('shotId'),'reviewId':payload.get('reviewId')},
                correctiveAction='Resolve this named failure against current inputs; prepare and review again.',
                mediaProviderCalled=None if submitted else False,mediaSpendOccurred=None if submitted else False,
                providerCallOccurred=None if submitted or reviewed else False,spendOccurred=None if submitted or reviewed else False,
                reviewProviderSpend='not-inferred; consult review usage',projectId=payload.get('projectId'),episode=payload.get('episode'),
                jobId=job.get('id'),createdAt=time.time())
    _write(production.ws.root/'cb-output/state/preflight-attempts'/(record['id']+'.json'),record)
    return record

def project_command(fn):
    @wraps(fn)
    def wrapped(self,payload):
        token=attempt.set({'mediaSubmissionAttempted':False}) if attempt.get() is None else None
        try:return fn(self,payload)
        except (Exception,SystemExit) as exc:
            project_failure(self,payload,exc)
            raise
        finally:
            if token is not None:attempt.reset(token)
    return wrapped
