"""Conservative task routing and explicitly labelled usage-based cost estimates.

Never retries or escalates a submitted request. Unknown pricing stays unknown.
Rate source: https://developers.openai.com/api/docs/pricing (2026-09-08).
Cache accounting: https://developers.openai.com/api/docs/guides/prompt-caching.
"""
from datetime import date
from decimal import Decimal, ROUND_CEILING
import re

from studio_workspace import StudioError

PRESET = {'creative': {'model': 'gpt-6-astra', 'estimateUsd': 2},
          'routine': {'model': 'gpt-5.6-terra', 'estimateUsd': .5},
          'assistant': {'model': 'gpt-5.6-luna', 'estimateUsd': .1}}
RATES = {'gpt-6-astra': (10, 50), 'gpt-5.6-terra': (2, 12), 'gpt-5.6-luna': (.2, 1.2)}


def validate_routes(value):
    if not isinstance(value, dict) or set(value) != set(PRESET):
        raise StudioError('Set a model and request estimate for creative, routine and assistant work.')
    result = {}
    for role, item in value.items():
        if not isinstance(item, dict) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,149}', str(item.get('model', ''))):
            raise StudioError('Enter a valid model ID for each direction task.')
        try:
            cost = Decimal(str(item.get('estimateUsd')))
            if not cost.is_finite() or not Decimal('.000001') <= cost <= 1000:
                raise ValueError()
        except Exception:
            raise StudioError('Enter a positive request estimate for each direction task.') from None
        result[role] = {'model': item['model'], 'estimateUsd': float(cost)}
    return result


def route(binding, kind, shot, message):
    if kind not in {'plan', 'chat', 'revise'} or not binding.get('routing'):
        return binding
    # Only narrow, exact maintenance requests qualify for a cheaper creative model.
    # Free-form requests, ambiguity, emotion, camera and story remain with the director.
    normalized = message.lower().strip(' .!')
    routine = shot and re.fullmatch(r'(shorten|clarify|format) (the )?(see|keyframe|watch|animation) prompt', normalized)
    task = 'routine' if routine and kind != 'plan' else 'creative'
    if kind == 'chat' and not shot and normalized in {'explain the workflow', 'explain see hear watch', 'how does the studio work'}:
        task = 'assistant'
    selected = binding['routing'][task]
    return {**binding, **selected, 'route': task,
            'routeReason': {'creative': 'Story, performance or creative direction',
                            'routine': 'Prompt wording only; preserve all shot decisions',
                            'assistant': 'Workflow explanation; no production changes'}[task]}


def usage_record(response, requested_model):
    """Allowlist numeric usage; never persist arbitrary response text or keys."""
    usage = getattr(response, 'usage', None)
    if hasattr(usage, 'model_dump'):
        usage = usage.model_dump()
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get('input_tokens_details') or {}
    details = details if isinstance(details, dict) else {}
    record = {'model': str(getattr(response, 'model', None) or requested_model)[:150],
              'serviceTier': str(getattr(response, 'service_tier', None) or 'unknown')[:30],
              'source': 'provider_response', 'estimatedUsd': None}
    for target, raw in [('inputTokens', usage.get('input_tokens')), ('outputTokens', usage.get('output_tokens')),
                        ('cachedTokens', details.get('cached_tokens')), ('cacheWriteTokens', details.get('cache_write_tokens'))]:
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            record[target] = raw
    # Price only the verified short-context standard models, with complete counters.
    # Do not guess alias, long-context, residency, account discount or future prices.
    model = record['model']
    if (model in RATES and record['serviceTier'] == 'default' and date.today() <= date(2026, 12, 31)
            and all(k in record for k in ('inputTokens', 'outputTokens', 'cachedTokens', 'cacheWriteTokens'))
            and record['inputTokens'] <= 100000
            and record['cachedTokens'] + record['cacheWriteTokens'] <= record['inputTokens']):
        rate_in, rate_out = map(lambda v: Decimal(str(v)), RATES[model])
        ordinary = record['inputTokens'] - record['cachedTokens'] - record['cacheWriteTokens']
        cost = (ordinary * rate_in + record['cachedTokens'] * rate_in / 10
                + record['cacheWriteTokens'] * rate_in * Decimal('1.25') + record['outputTokens'] * rate_out) / 1000000
        record.update(estimatedUsd=float(cost), rateDate='2026-09-08',
                      pricingSource='https://developers.openai.com/api/docs/pricing',
                      priceBasis='Standard list price from measured tokens; not a provider invoice')
    return record


def commitment(job):
    value = (job.get('usage') or {}).get('estimatedUsd')
    measured = int((Decimal(str(value)) * 1000000).to_integral_value(rounding=ROUND_CEILING)) if value is not None else 0
    return max(job['estimate'], measured)


def summary(jobs):
    records = [j['usage'] for j in jobs if j.get('usage')]
    priced = [r for r in records if r.get('estimatedUsd') is not None]
    generations = [(j.get('shotId'),j.get('kind')) for j in jobs if j.get('kind') in {'see','hear','watch'}]
    return {'generationJobs': len(generations), 'repeatGenerationJobs': len(generations)-len(set(generations)), 'measuredRequests': len(records), 'pricedRequests': len(priced),
            'estimatedUsd': round(sum(r['estimatedUsd'] for r in priced), 6),
            'unpricedRequests': sum(1 for j in jobs if j.get('kind') != 'assembly' and
                                   (j.get('usage') or {}).get('estimatedUsd') is None),
            'inputTokens': sum(r.get('inputTokens', 0) for r in records),
            'outputTokens': sum(r.get('outputTokens', 0) for r in records)}


def readiness(workspace, context):
    """Read-only setup checks, never a claim of provider/model access or artistic quality."""
    services = workspace.services(context['project']['id'])
    connections = {c['id']: c for c in workspace.connections()}
    checks = []
    for role in ('direction', 'keyframes', 'voices', 'animation', 'review'):
        binding = services.get(role) or {}
        connection = connections.get(binding.get('connectionId'))
        status = 'configured' if connection and connection.get('enabled') else 'missing'
        detail = 'Choose a connection and model in Project services.'
        if status == 'configured':
            detail = ('Connection checked; model generation access is not yet proven.' if connection.get('status') == 'connected'
                      else 'Connection has not passed its latest check. Check it in Workspace connections.')
        checks.append({'role': role, 'status': status, 'optional': role == 'review', 'detail': detail})
    return {'checks': checks, 'meaning': 'Setup checks only. Provider access, balances and final quality require live verification.'}
