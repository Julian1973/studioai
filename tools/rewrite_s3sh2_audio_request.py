"""Apply Julian's requested S3.SH2 audio-direction revision; never submit media."""
from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import cb_render as R
import studio_director_handoff as H
from studio_watch_revision import revised_shot
from studio_see_package import Package
from cb_recovery import require_no_provider_operation


def run(apply=False):
    scope = dict(projectId='crystal-bears', episode='Ep4', scene='3', unit='S3.SH2')
    with Package(R.ROOT, scope).lock():
        pkg, path = R.load_pkg('3', 'Ep4')
        shot, ledger = R._shot(pkg, 'S3.SH2'), R._ledger(pkg, 'S3.SH2')
        if ledger.get('batchId') != 'S3.SH2-b4-20260922T080335-1f7b3202':
            raise ValueError('Reviewed batch changed; inspect before applying')
        require_no_provider_operation(R.ROOT, 'Ep4', '3', 'S3.SH2', ledger)
        views = shot['directorCard']['views']
        replacements = {
            (0, 'performance'): 'Sunny articulates the first approved Audio1 line at 0.3–5.98s and immediately continues into the second at 5.98s, without a false pause or mouth closure between them. Her paws dart and chin stays lifted too high; her path becomes smaller and quicker as objects fail. The action text is never spoken.',
            (1, 'framing'): 'CU/insert along the original berry bowls at tabletop height, with Sunny’s paw entering; her mouth stays out of frame.',
            (1, 'performance'): 'Her paw makes quick, careful contact with the original faceted pink-purple crystal berry bowl; water sloshes around the visible berries. The bowl stays on the table. Sunny’s second Audio1 line continues offscreen to 11.34s; no speaking face is added.',
            (1, 'staging'): 'The original faceted pink-purple crystal bowls retain their rim, silhouette, scale, material and visible red and dark-blue berries. Rainwater rises around the berries; it does not replace them. Preserve positions relative to napkins and vase and Sunny’s established table side. Only wetness, water level and a slight contact-made displacement change.',
            (2, 'action'): 'The established hanging lantern flickers and extinguishes; rain continues over its unchanged faceted housing. Its nonverbal extinguishing hiss belongs to the Sound cues, never dialogue.',
            (2, 'performance'): 'No character face or lip movement appears. The final approved Audio1 line begins offscreen at 11.34s and continues uninterrupted across the next two cuts. The lantern failure remains a physical effect, not a spoken sound label or extra voice.',
            (3, 'performance'): 'Sunny’s body stops rushing, her attention drops, and her head and shoulders lower. This physical droop is not a silence in Audio1: visible articulation continues precisely with the already-running final line, without restarting it. Her posture exposes the hurt while her voice tries to move beyond it.',
            (4, 'action'): 'Sunny lifts sharply, turns toward the established inside direction, and completes the remaining portion of the already-started Audio1 line by 15.98s.',
            (4, 'performance'): 'Her attention breaks from the ruined setup before she has processed it. Visible mouth shapes follow only the remaining Audio1 speech and stop at 15.98s. Her body becomes fast again; command is a coping tactic, not emotional recovery. No repeated opening words or generated vocal tail.',
            (5, 'performance'): 'After 15.98s there is no speech articulation or extra vocalisation. Sunny moves toward the inside direction without looking back. Her forced urgency leaves the emotional weight with the wet, berry-filled bowls, sagging garland and dark lantern.',
        }
        edits = [dict(viewId=views[i]['viewId'], field=field, expected=views[i].get(field,''),
                      value=value, reason='Julian requested the agreed Audio1 and sound rewrite before Fire.')
                 for (i, field), value in replacements.items()]
        candidate = revised_shot(shot, edits)
        card = candidate['directorCard']
        card['soundOwnership'] = 'Audio1 owns the unchanged dialogue bed. Seedance supplies only directed nonverbal effects, ambience and instrumental score below it. Preserve continuous speech across cuts and no voice after 15.98s.'
        card['soundCues'] = [
            dict(kind='ambience', destination='watch', timing='0–18s', instruction='Carry clearing ambience into increasing rain; distinct surface impacts become a fuller rain bed beneath intelligible Audio1.'),
            dict(kind='effects', destination='watch', timing='8.8–11.34s', instruction='Synchronise delicate crystal-rim plinks, small water sloshes and soft paw contact to the visible berry-bowl insert; not empty metal cups.'),
            dict(kind='effects', destination='watch', timing='11.75–12.24s', instruction='One small nonverbal extinguishing hiss resolves with the lantern outage around 12.05s; rain continues. No voice speaks the effect label.'),
            dict(kind='effects', destination='watch', timing='0–18s', instruction='Soft wet footfalls and paw contacts follow visible rescue and pivot actions; no invented gasps or laughter.'),
            dict(kind='music', destination='watch', timing='0–18s', instruction='Restrained instrumental pulse beneath rescue; thin it at the lantern failure and leave space around the physical droop. Modest return beneath the pivot supports effort, not victory. No vocals, exaggerated comedy sting or masking Audio1. Retain the quiet nonverbal tail after speech ends.'),
        ]
        candidate['directorCardSource'] = dict(candidate['directorCardSource'],
            sourceHash=H.digest(H.source(candidate)), directionHash=H.digest(card))
        assert not H.errors(candidate) and not H.card_issues(candidate)
        for field in ('dialogueLines','durationSec','continuityIn','continuityOut'):
            assert candidate[field] == shot[field]
        assert [(v['atSec'],v['timing'],v['cinematography']) for v in card['views']] == [(v['atSec'],v['timing'],v['cinematography']) for v in views]
        prompt, _ = R._resolve_seedance_prompt(pkg, candidate, '3', 'Ep4')
        for line in candidate['dialogueLines']:
            assert prompt.count('{'+line['exactText']+'}') == 1
        assert 'Restrained instrumental pulse' in prompt
        print('Validated typed rewrite:',len(prompt.split()),'words; Audio1, intervals and camera preserved')
        if not apply:
            return
        old = deepcopy(shot)
        R.reject_shot('3','S3.SH2','Lip-sync and SFX issues; apply agreed Audio1 structure, retain approved voice and visual direction.',episode='Ep4',reviewed_by='Codex on Julian request')
        pkg,path=R.load_pkg('3','Ep4')
        ledger,shot=R._ledger(pkg,'S3.SH2'),R._shot(pkg,'S3.SH2')
        ledger.setdefault('directorRevisionHistory',[]).append(dict(before=old,
            note='User requested agreed rewrite and Fire; exact audio unchanged.',
            acceptedBy='Codex on Julian request',edits=edits,soundCues=deepcopy(card['soundCues'])))
        shot.clear();shot.update(candidate)
        R._save(pkg,path)
        print('Applied direction; rejected batch archived. No render submitted.')


if __name__ == '__main__':
    run('--apply' in sys.argv)
