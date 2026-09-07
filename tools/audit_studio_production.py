"""Read-only production audit. Writes only its requested evidence JSON; no providers."""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import pathlib
import re
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))


def digest(path):
    p = pathlib.Path(path) if path else None
    return hashlib.sha256(p.read_bytes()).hexdigest() if p and p.is_file() else None


def audit():
    import cb_render as render
    import cb_state
    import cb_prompt_lab
    import cb_departments

    db = sqlite3.connect(f"file:{ROOT / 'cb-output/state/studio.sqlite3'}?mode=ro", uri=True)
    counts = dict(db.execute("select status,count(*) from studio_jobs group by status"))
    span = db.execute("select min(started),max(started) from studio_jobs").fetchone()
    reasons = collections.Counter()
    for step, log in db.execute("select step,log from studio_jobs where status='failed'"):
        lines = [s for s in (log or '').splitlines() if 'REFUSED' in s or 'Error:' in s]
        msg = lines[-1] if lines else step or 'unspecified'
        # Retain only refusal categories, never raw provider responses or credentials.
        if not msg.startswith('REFUSED'):
            reasons['other failure (inspect locally)'] += 1
            continue
        msg = re.sub(r'--spend-token [a-f0-9]+', '--spend-token [redacted]', msg)
        msg = re.sub(r'S\d+\.SH\d+', 'SHOT', msg)
        msg = re.sub(r'[a-f0-9]{24,}', '[hash]', msg)
        reasons[msg[:500]] += 1
    db.close()
    scenes = []
    before = {}
    for path in sorted((ROOT / 'cb-output').glob('Ep2_scene*_production_package.json')):
        before[str(path)] = digest(path)
        pkg = json.loads(path.read_text())
        scene = str(pkg['sceneNumber'])
        state = cb_state.production_state(scene, 'Ep2')
        projected = {s['shotId']: s for s in state.get('shots', [])}
        rows = []
        for shot in pkg['shots']:
            ledger = render._ledger(pkg, shot['shotId'])
            approval = ledger.get('approval') or {}
            take_hash = digest(ledger.get('approvedTake'))
            frame_hash = digest(ledger.get('harvestFrame'))
            view = projected.get(shot['shotId'], {})
            rows.append({
                'shotId': shot['shotId'], 'ledgerStatus': ledger.get('status'),
                'approvedTakeExists': take_hash is not None,
                'takeHashMatchesApproval': bool(take_hash and take_hash == approval.get('contentHash')),
                'frameHashMatchesApproval': bool(frame_hash and frame_hash == approval.get('harvestHash')),
                'projectedLabel': view.get('label'),
                'readyToAnimate': view.get('readyToAnimate'),
            })
        lineage = render.lineage_status(pkg, scene, 'Ep2')
        scenes.append({'scene': scene, 'lineageCurrent': lineage['current'],
                       'lineageReasons': lineage['reasonCodes'],
                       'stages': state.get('stages'), 'shots': rows})
    parameter_examples = {
        s: [m.group(0) for m in cb_prompt_lab._REQUEST_PARAMETER_WORDS.finditer(s)]
        for s in ['The music reaches a tonic resolution.', 'Render at 480p resolution.']
    }
    timing_text = ('The camera rises from 18–26 seconds. The music builds from '
                   '18–26 seconds. The wide settles from 26–30 seconds.')
    timing_ranges = cb_prompt_lab._TIME_RANGE.findall(timing_text)
    synthetic_shot = {'storyboardStagePlanApproved': [
        {'stageNumber': 1, 'primaryEvent': 'The camera rises from 18–26 seconds.',
         'observableEndState': 'Wide garden.'}]}
    story_report = cb_departments.animation_story_lock_report(
        synthetic_shot, 'The camera rises from 18 seconds until 26 seconds. Wide garden.')
    pkg, _ = render.load_pkg('8', 'Ep2')
    shot = render._shot(pkg, 'S8.SH2')
    sig1 = render._seedance_working_input_signature(pkg, shot, '8', 'Ep2')
    revised = copy.deepcopy(pkg)
    revised['revision'] = int(revised.get('revision') or 0) + 1
    sig2 = render._seedance_working_input_signature(revised, render._shot(revised, 'S8.SH2'), '8', 'Ep2')
    sizes = {}
    for rel in ['engine/cb_render.py', 'engine/cb_safety.py', 'engine/cb_state.py',
                'engine/cb_departments.py', 'cb-studio/serve.py', 'cb-studio/app.html',
                'cb-studio/director.js']:
        sizes[rel] = len((ROOT / rel).read_text().splitlines())
    unchanged = all(digest(p) == h for p, h in before.items())
    return {'capturedAt': datetime.now(timezone.utc).isoformat(),
            'scope': 'Local retained job history and current Episode 2 packages; not all historical conversations',
            'jobCounts': counts, 'jobEpochSpan': span,
            'failedRefusalCategories': reasons.most_common(), 'scenes': scenes,
            'reproductions': {'musicalResolutionFalsePositive': parameter_examples,
                             'independentTimingRangesParsedAsOneSequence': timing_ranges,
                             'equivalentVisualTimingStoryLock': story_report,
                             'metadataOnlyRevisionChangesWorkingPromptSignature': sig1 != sig2},
            'sourceLines': sizes, 'productionPackagesUnchangedByAudit': unchanged}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    evidence = audit()
    out = pathlib.Path(args.output).resolve()
    if out.suffix != '.json':
        parser.error('output must be an audit JSON file')
    if out == (ROOT / 'cb-output/state/studio.sqlite3') or out.name.endswith('_production_package.json'):
        parser.error('output must not replace production state')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'evidencePath': str(out), 'jobCounts': evidence['jobCounts'],
                      'productionPackagesUnchangedByAudit': evidence['productionPackagesUnchangedByAudit']}))
