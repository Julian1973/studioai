#!/usr/bin/env python3
"""Register an exported cut in the existing Studio post workspace (never approve).
Use after the MCP render has finished. Drive verification is a separate receipt.
"""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'engine'))
import cb_finishing as finishing
import cb_post_workspace as post

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--episode', required=True);p.add_argument('--version', required=True)
    p.add_argument('--export', dest='export_path',required=True,type=pathlib.Path)
    p.add_argument('--timeline',required=True)
    p.add_argument('--drive-folder',type=pathlib.Path)
    p.add_argument('--source-manifest',type=pathlib.Path,help='Approved Studio episode.json used to build this Resolve timeline')
    args=p.parse_args()
    if not re.fullmatch(r'Ep\d+',args.episode) or not re.fullmatch(r'[A-Za-z0-9_-]+',args.version):
        p.error('Use Ep<number> and a plain version token.')
    snapshot=finishing.resolve_snapshot()
    if snapshot['timeline'] != args.timeline:
        p.error('The active Resolve timeline does not match the supplied timeline.')
    source=args.export_path.resolve(strict=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(source)]))
    video=next(s for s in probe['streams'] if s['codec_type']=='video')
    if video.get('avg_frame_rate') not in ('30/1','30000/1000'):
        p.error('This vCube profile preserves 30 fps; qualify another profile for a different cadence.')
    frames=int(video.get('nb_frames') or 0)
    if frames != snapshot['endFrame']-snapshot['startFrame']:
        p.error('Export frame count differs from the active timeline. Finish and verify the full render first.')
    digest=post._sha256(source)
    sources = None
    if args.source_manifest:
        source_manifest = args.source_manifest.resolve(strict=True)
        sources = json.loads(source_manifest.read_text())
        if sources.get('episode') != args.episode:
            p.error('The source manifest belongs to another episode.')
        for shot in sources.get('shots', []):
            render = (source_manifest.parent / shot['render']).resolve(strict=True)
            if post._sha256(render) != shot.get('approvedTakeSha256'):
                p.error('A source render changed since its approved post export.')
        sources = {'path':str(source_manifest),'sha256':post._sha256(source_manifest),
                   'shots':sources.get('shots',[]),
                   'meaning':'Supplied approved source records; timeline correspondence still requires inspection.'}
    folder=post.POST_ROOT/f'{args.episode}_episode';folder.mkdir(parents=True,exist_ok=True)
    dest=folder/f'{args.episode}_{args.version}_{digest[:12]}.mp4'
    if not dest.exists():shutil.copy2(source,dest)
    if post._sha256(dest)!=digest:raise RuntimeError('Copied export checksum differs.')
    if args.drive_folder:
        if not args.drive_folder.is_dir():p.error('Drive folder must already exist.')
        cloud=args.drive_folder/dest.name
        if not cloud.exists():shutil.copy2(dest,cloud)
        if post._sha256(cloud)!=digest:raise RuntimeError('Drive staging checksum differs.')
    manifest={'stage':'davinci-final-cut-review','durationSec':float(probe['format']['duration']),
        'masterSha256':digest,'outputs':{'master':str(dest)},'sourceRecords':sources,
        'approvalContract':{'approvalMeaning':'Approval of this exact pre-enhancement cut; enhancement spending is separate.'},
        'finishingWorkflow':{'version':args.version,'resolveProject':snapshot['project'],
            'resolveTimeline':snapshot['timeline'],'resolveSnapshot':snapshot,
            'drive':{'verified':False},'findings':[],
            'audioNote':'Review the full soundtrack and document its source and mix status before sign-off.'}}
    with finishing.lock(args.episode), post.review_lock(args.episode):
        target = folder/f'{args.version}_manifest.json'
        if target.exists():
            p.error('This version is already registered. Use a new version; preserve its review evidence and receipt.')
        finishing.write(target,manifest)
    print(json.dumps({'status':'awaiting-review','masterSha256':digest,'studioUrl':f'http://127.0.0.1:8899/cb-studio/finishing.html?episode={args.episode}'}))
if __name__=='__main__':main()
