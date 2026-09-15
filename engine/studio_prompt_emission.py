"""Common immutable final emission projection; OFF/SHADOW only, never a transport."""
import base64
from pathlib import Path
import os
from studio_shot_request import ShotProductionRequest, digest


def contract(request):
    if not isinstance(request, ShotProductionRequest):
        request=ShotProductionRequest.load(request)
    data=request.data
    execution=data['execution'];truth=data['truth'];settings=execution.get('settings',{})
    emissions=settings.get('emissions') or [dict(prompt=execution['prompt'],
        references=truth.get('references',[]),audioHash=truth.get('audio'),settings=settings)]
    return {'requestHash':request.request_hash,'canonicalTruth':truth,
        'actionIntegrity':[p.get('actionIntegrity') for p in execution.get('reviewedPlans',[])],
        'finalPromptBytes':base64.b64encode(execution['prompt'].encode('utf-8')).decode(),
        'emissions':[{'promptBytes':base64.b64encode((e.get('prompt') or '').encode('utf-8')).decode(),
            'referenceOrderAndHashes':e.get('references',[]),'audio1Hash':e.get('audioHash'),
            'settings':{k:v for k,v in e.items() if k not in ('prompt','references','audioHash')}} for e in emissions],
        'settings':settings}


def differences(left,right,path=''):
    if isinstance(left,dict) and isinstance(right,dict):
        result=[]
        for key in sorted(set(left)|set(right)):
            if key not in left or key not in right:result.append(path+'/'+key)
            else:result.extend(differences(left[key],right[key],path+'/'+key))
        return result
    return [] if left==right else [path or '/']


def record_shadow(root,route,request,*,baseline=None,mode=None):
    mode=(mode if mode is not None else os.environ.get('STUDIO_PROMPT_EMISSION_MODE','OFF')).upper()
    if mode not in ('OFF','SHADOW'):raise ValueError('Final emission supports OFF/SHADOW only; cutover is not authorised')
    if mode=='OFF':return None
    actual=contract(request)
    compared=contract(baseline) if baseline is not None else None
    report={'mode':'SHADOW','route':route,'actual':actual,'baseline':compared,
        'differences':differences(compared,actual) if compared else None,
        'parity':'PASS' if compared==actual else 'FAIL' if compared else 'UNVERIFIED',
        'qualification':'Content parity only; no model or visual qualification',
        'providerCalled':False,'spendReserved':False,'approvalChanged':False}
    # Existing evidence storage; no new production owner or mutable approval.
    import cb_db
    path=Path(root)/'cb-output/evidence/prompt-emission'/f'{digest(report)}.json'
    cb_db.atomic_write_json(Path(root),path,report)
    return str(path)
