"""Apply the requested scorer clarifications without submitting a render."""
import sys
from pathlib import Path
from copy import deepcopy
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import cb_render as R
import studio_director_handoff as H
import cb_emission_conformance as C
from studio_see_package import Package
from cb_recovery import require_no_provider_operation


def run():
    scope = dict(projectId='crystal-bears', episode='Ep4', scene='3', unit='S3.SH2')
    with Package(R.ROOT, scope).lock():
        pkg, path = R.load_pkg('3', 'Ep4')
        shot, ledger = R._shot(pkg, 'S3.SH2'), R._ledger(pkg, 'S3.SH2')
        require_no_provider_operation(R.ROOT, 'Ep4', '3', 'S3.SH2', ledger)
        if ledger['status'] != 'designed':
            raise ValueError('Shot state changed; inspect before revising')
        before = deepcopy(shot)
        candidate = deepcopy(shot)
        card = candidate['directorCard']
        views = card['views']
        assert views[1]['viewId'] == 'S3.v06.berryCupsFill'
        views[1]['cinematography']['angle'] = 'At tabletop and berry-bowl height; Sunny’s mouth stays out of frame.'
        views[4]['entry'] = 'cut'
        views[4]['cutReason'] = 'Cut on Sunny’s pivot into the authored 35 mm view, then follow the pivot with the existing motivated pan.'
        views[5]['entry'] = 'cut'
        views[5]['cutReason'] = 'Cut after the spoken line into the authored 50 mm landing composition, then hold on Sunny and the soggy evidence.'
        for cue in card.get('soundCues', []):
            if cue.get('kind') == 'music':
                cue['instruction'] += ' During the physical droop at 12.24–13.54s, reduce rain and instrumental intensity to leave perceptual space; do not mute, shift or alter Audio1.'
        for old in candidate.get('storyboardInternalShotPlanApproved') or []:
            v = next((v for v in views if v['viewId'] == old.get('viewId')), None)
            if v and v['viewId'] in {views[4]['viewId'], views[5]['viewId']}:
                old['cutReason'] = v['cutReason']
        candidate['directorCardSource'] = dict(candidate['directorCardSource'],
            sourceHash=H.digest(H.source(candidate)), directionHash=H.digest(card))
        assert not H.errors(candidate), H.errors(candidate)
        assert not H.card_issues(candidate), H.card_issues(candidate)
        for key in ('dialogueLines', 'durationSec', 'referenceSlots', 'continuityIn', 'continuityOut'):
            assert candidate.get(key) == before.get(key), key
        for original, revised in zip(before['directorCard']['views'], views):
            for key in ('framing', 'action', 'performance', 'staging', 'startSec', 'endSec'):
                assert original.get(key) == revised.get(key), key
            for key in ('lens', 'movement', 'focus', 'light', 'composition'):
                assert original['cinematography'].get(key) == revised['cinematography'].get(key), key
        prompt, _ = R._resolve_seedance_prompt(pkg, candidate, '3', 'Ep4')
        assert C.STANDARD_DIALOGUE_AUDIO_AUTHORITY in prompt
        insert = prompt.split('Shot 2:')[1].split('Shot 3:')[0]
        assert '45 in above' not in insert
        assert 'Preserve offscreen @Audio1 timing' in insert
        for number in (5, 6):
            assert 'Continue current shot' not in prompt.split(f'Shot {number}:')[1].split('\n\n')[0]
        if ledger.get('pendingSpendAuth'):
            R.cb_db.void_shot_authorizations(R.ROOT, 'Ep4', '3', 'S3.SH2', 'user-approved-scorer-clarifications')
        ledger['pendingSpendAuth'] = None
        ledger.setdefault('directorRevisionHistory', []).append(dict(
            note='User requested scorer clarifications and one render, retaining locked Audio1 and visual style.',
            before=before, acceptedBy='Julian via explicit chat request', at=R._now()))
        shot.clear()
        shot.update(candidate)
        R._save(pkg, path)
        print('DIRECT clarifications saved; Audio1, timing, lenses, moves, lighting, composition and references preserved. No render submitted.')


if __name__ == '__main__':
    run()
