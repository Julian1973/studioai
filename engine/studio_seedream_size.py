"""Explicit Seedream 5 Pro sizes; never transmit an unconstrained tier.

Provider contract: https://docs.byteplus.com/api/docs/ModelArk/1824121
2K sizes below are the provider's published table. 1280x720 / its transpose
are exact 16:9 / 9:16 within the documented explicit-size pixel bounds.
"""
import hashlib
import json
from pathlib import Path

_SIZES = {
    '2K': {'16:9': '2816x1584', '9:16': '1584x2816', '1:1': '2048x2048',
           '4:3': '2368x1776', '3:4': '1776x2368', '3:2': '2496x1664',
           '2:3': '1664x2496', '21:9': '3136x1344'},
    '1K': {'16:9': '1280x720', '9:16': '720x1280', '1:1': '1024x1024',
           '4:3': '1152x864', '3:4': '864x1152', '3:2': '1248x832',
           '2:3': '832x1248', '21:9': '1568x672'},
}

def dimensions(aspect, tier='2K'):
    try:
        return _SIZES[tier][aspect]
    except (KeyError, TypeError):
        raise ValueError(f'SEE_REQUEST_CONFIGURATION_ERROR: unsupported Seedream 5 Pro aspect/size {aspect!r}/{tier!r}; no submission') from None


def crystal_bears_aspect(root):
    projects = json.loads((Path(root) / 'cb-studio/data/projects.json').read_text())['projects']
    aspect = next(p for p in projects if p['id'] == 'crystal-bears').get('aspectRatio')
    # Native composition proofs currently target 16:9; never emit a conflicting request.
    if aspect != '16:9':
        raise ValueError(f'SEE_REQUEST_CONFIGURATION_ERROR: project aspect {aspect!r} conflicts with native composition target 16:9')
    return aspect


def record_request(output, endpoint, body, aspect, tier):
    """Record the real body hash and safe settings before POST; no URLs/credentials."""
    if body.get('size') != dimensions(aspect, tier):
        raise ValueError('SEE_REQUEST_CONFIGURATION_ERROR: sealed size disagrees with aspect')
    output = Path(output)
    if output.exists():
        raise ValueError('SEE_REQUEST_CONFIGURATION_ERROR: refusing to overwrite existing image')
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    evidence = {'provider': 'byteplus', 'model': body['model'], 'endpoint': endpoint,
                'aspect': aspect, 'resolutionTier': tier, 'size': body['size'],
                'aspectMechanism': 'explicit size widthxheight', 'requestHash': digest,
                'settings': {k: body[k] for k in ('output_format', 'response_format', 'watermark', 'optimize_prompt_options') if k in body},
                'status': 'prepared_before_submission', 'providerSubmitted': False}
    path = Path(str(output) + '.request.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2) + '\n')
    return evidence
