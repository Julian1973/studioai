"""BytePlus VOD vCube adapter. Credentials stay in the existing engine/.env.
Contract: Lark P3SZdNRuboYkgkx8alacq7hznNb -> StartExecution (2025-07-01).
No provider calls occur on import, configuration inspection, or cut approval.
"""
import hashlib
import json
import math
import os
from pathlib import Path

DOCUMENTATION = 'https://bytedance.larkoffice.com/docx/P3SZdNRuboYkgkx8alacq7hznNb'

def config():
    # Same secure source as cb_gen; read fresh so credential setup needs no restart.
    values = {}
    path = Path(__file__).with_name('.env')
    if path.exists():
        for line in path.read_text().splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k, v = line.split('=', 1)
                values[k.strip()] = v.strip().strip('\"\'')
    values.update(os.environ)
    def get(*names):
        return next((values[n] for n in names if values.get(n)), '')
    return {'ak': get('BYTEPLUS_VOD_ACCESS_KEY', 'BYTEPLUS_ACCESSKEY'),
            'sk': get('BYTEPLUS_VOD_SECRET_KEY', 'BYTEPLUS_SECRETKEY'),
            'space': get('BYTEPLUS_VOD_SPACE_NAME', 'VOD_SPACE_NAME'),
            'rate': get('BYTEPLUS_VOD_COST_4K_USD_PER_MINUTE'),
            'costsVerified': get('BYTEPLUS_VOD_COSTS_VERIFIED') == 'true'}

def readiness(duration):
    c = config()
    missing = [label for k, label in [('ak','VOD access key'),('sk','VOD secret key'),('space','VOD space')] if not c[k]]
    try:
        rate = float(c['rate'])
        if not math.isfinite(rate) or rate <= 0 or not c['costsVerified']:
            raise ValueError()
        estimate = round(float(duration) / 60 * rate, 4)
    except (ValueError, TypeError):
        estimate = None
        missing.append('verified 4K Pro price')
    return {'provider': 'BytePlus VOD / vCube', 'configured': not missing,
            'missing': missing, 'estimatedUsd': estimate, 'documentation': DOCUMENTATION,
            'settings': 'AIGC · Pro · high definition · 4K · 30 fps · 10-bit',
            'outputReviewRequired': True}

def service():
    from byteplus_sdk.vod.VodService import VodService
    from byteplus_sdk.ApiInfo import ApiInfo
    c = config()
    if not all(c[k] for k in ('ak','sk','space')):
        raise ValueError('BytePlus VOD credentials and space are not configured in engine/.env.')
    sdk = VodService(region='ap-southeast-1')
    sdk.set_ak(c['ak']); sdk.set_sk(c['sk'])
    for action, method in [('StartExecution','POST'), ('GetExecution','GET')]:
        sdk.api_info[action] = ApiInfo(method, '/', {'Action':action,'Version':'2025-07-01'}, {}, {})
    return sdk

def upload(path):
    from byteplus_sdk.vod.models.request.request_vod_pb2 import VodUploadMediaRequest
    req = VodUploadMediaRequest()
    req.SpaceName = config()['space']; req.FilePath = str(path); req.FileExtension = '.mp4'
    resp = service().upload_media(req)
    if resp.ResponseMetadata.Error.Code or not resp.Result.Data.Vid:
        raise RuntimeError('BytePlus upload did not return a successful Vid.')
    return resp.Result.Data.Vid

def payload(vid, cut_hash):
    operation = {'Type':'Task','Task':{'Type':'Enhance','Enhance':{'Type':'Moe','MoeEnhance':{
        'Config':'aigc','Target':{'Res':'4k','Fps':30,'BitDepth':10},
        'VideoStrategy':{'RepairStrength':0,'EnhanceLevel':'Pro'}}}}}
    token = hashlib.sha256((cut_hash + json.dumps(operation, sort_keys=True)).encode()).hexdigest()
    return {'SpaceName':config()['space'], 'Input':{'Type':'Vid','Vid':vid},
            'Operation':operation,'Control':{'ClientToken':token}}

def start(body):
    # SDK v1 json() signs a string, then serializes that string again on send.
    # Send exactly the UTF-8 JSON bytes covered by the signature.
    from byteplus_sdk.auth.SignerV4 import SignerV4
    sdk = service()
    request = sdk.prepare_request(sdk.api_info['StartExecution'], {})
    request.headers['Content-Type'] = 'application/json'
    request.body = json.dumps(body, ensure_ascii=True)
    SignerV4.sign(request, sdk.service_info.credentials)
    response = sdk.session.post(request.build(), headers=request.headers,
        data=request.body.encode('utf-8'),
        timeout=(sdk.service_info.connection_timeout, sdk.service_info.socket_timeout))
    return _result(response.text)

def poll(run_id):
    return _result(service().get('GetExecution', {'RunId':run_id}))

def _result(raw):
    result = json.loads(raw)
    if (result.get('ResponseMetadata') or {}).get('Error'):
        error = result['ResponseMetadata']['Error']
        raise RuntimeError('BytePlus rejected request: ' + str(error.get('Code')) + ': ' + str(error.get('Message')))
    return result.get('Result') or {}
