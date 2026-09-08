"""Continuous local review movie from pinned approved clips; no provider spending."""
import json
import subprocess

from studio_workspace import StudioError


def execute(production, job):
    pid, timeline = job['projectId'], job['timeline']
    folder = production.ws.project_path(pid, f"projects/{pid}/exports/{job['id']}")
    folder.mkdir(parents=True, exist_ok=True)
    clips = timeline['clips']
    paths = [production.ws.project_path(pid, c['file']['path']) for c in clips]
    for clip in clips:
        production.assert_artifact(pid, {'files':[clip['file']]})
    def run(args):
        try:
            return subprocess.run(args,check=True,capture_output=True,timeout=600)
        except Exception:
            raise StudioError('The continuous preview could not finish. Original shots are preserved; retry this local assembly.', 'assembly_failed') from None
    stream = json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(paths[0])]).stdout)
    video = next(s for s in stream['streams'] if s['codec_type']=='video')
    width, height = int(video['width'])//2*2, int(video['height'])//2*2
    segments=[]
    for index,(clip,path) in enumerate(zip(clips,paths)):
        streams=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',str(path)]).stdout)['streams']
        audio=any(s['codec_type']=='audio' for s in streams)
        output=folder/f'segment-{index:04}.mkv'
        args=['ffmpeg','-v','error','-ss',str(clip['in']),'-i',str(path)]
        if not audio:args+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        args+=['-map','0:v:0','-map','0:a:0' if audio else '1:a:0','-t',str(clip['duration']),
               '-vf',f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24',
               '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-af','apad','-ar','48000','-ac','2','-c:a','pcm_s16le','-y',str(output)]
        run(args);production.transport.verify_media(output,'video');segments.append(output)
    listing=folder/'segments.txt'
    listing.write_text('\n'.join("file '"+path.name+"'" for path in segments)+'\n')
    target=folder/'episode-review.mp4'
    run(['ffmpeg','-v','error','-f','concat','-safe','1','-i',str(listing),'-c:v','copy','-c:a','aac','-movflags','+faststart','-y',str(target)])
    duration=production.transport.verify_media(target,'video')
    if abs(duration-timeline['duration'])>max(.2,len(clips)/24+.05):
        raise StudioError('The assembled duration differs from the approved cut. Review the timing before retrying.','assembly_timing')
    for segment in segments:segment.unlink()
    listing.unlink()
    return {'files':[production.file_record(pid,target)],'fingerprint':timeline['fingerprint'],'duration':duration,
            'width':width,'height':height,'fps':24,'meaning':'Continuous review preview at the first source clip dimensions. Original approved media remains the finishing authority.'}
