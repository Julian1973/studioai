"""Exact branded typography over a silent 30-second presenter video."""
from pathlib import Path
import hashlib
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont

FONT_FILES = ['Bangers-Regular.ttf','NunitoSans-Variable.ttf']
TIMES = [(0,4),(4,8),(8,12),(12,17),(17,21),(21,26),(26,30)]

def check_fonts(root):
    result=[]
    for name in FONT_FILES:
        path=Path(root)/'cb-studio/assets/fonts'/name
        if not path.is_file():
            raise ValueError('Missing official font: '+name)
        ImageFont.truetype(str(path),24)
        result.append({'name':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return result

def make_cards(root,episode,config,out):
    check_fonts(root)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    size=(1708,960);cx=1200;max_width=820
    def font(n,heading):
        f=ImageFont.truetype(str(Path(root)/'cb-studio/assets/fonts'/FONT_FILES[0 if heading else 1]),n)
        if not heading:
            f.set_variation_by_axes([600,100,12,500])
        return f
    def text(image,word,y,n,heading=False):
        draw=ImageDraw.Draw(image)
        while n>22 and draw.textlength(word,font=font(n,heading))>max_width:
            n-=1
        f=font(n,heading);box=draw.textbbox((0,0),word,font=f)
        if box[2]-box[0]>max_width:
            raise ValueError('A credit line is too long. Add a line break in the credits editor.')
        draw.text((cx-(box[2]-box[0])/2-box[0],y-box[1]),word,font=f,
                  fill='white',stroke_width=1,stroke_fill=(0,0,0,110))
    def save(im,name):
        path=out/name
        im.resize((854,480),Image.Resampling.LANCZOS).save(path)
        return path
    header=Image.new('RGBA',size)
    colour=config['background'].lstrip('#')
    rgb=tuple(int(colour[i:i+2],16) for i in (0,2,4))
    if sum(x*y for x,y in zip(rgb,(.2126,.7152,.0722)))>155:
        ImageDraw.Draw(header).rounded_rectangle((755,40,1680,915),radius=30,fill=(0,0,0,100))
    text(header,'The Crystal Bears',98,100,True)
    text(header,f"Episode {episode[2:]} : {config['title']}",230,51,True)
    save(header,'header.png')
    for i,(heading,body) in enumerate(config['cards']):
        im=Image.new('RGBA',size)
        text(im,heading,410,68,True)
        # Preserve wording; wrap long credit prose into up to four readable lines.
        lines=[]
        for line in body.splitlines():
            words=line.split();current=''
            for word in words:
                candidate=(current+' '+word).strip()
                if current and ImageDraw.Draw(im).textlength(candidate,font=font(49,False))>max_width:
                    lines.append(current);current=word
                else:
                    current=candidate
            lines.append(current)
        if len(lines)>4:
            raise ValueError('Too much text on credit card '+str(i+1)+'. Use up to four short lines.')
        for j,line in enumerate(lines):
            text(im,line,515+j*75,49)
        save(im,f'card_{i}.png')
    preview=Image.new('RGBA',(854,480),config['background'])
    preview.alpha_composite(Image.open(out/'header.png'))
    preview.alpha_composite(Image.open(out/'card_0.png'))
    preview.convert('RGB').save(out/'preview.jpg')
    (out/'typography.json').write_text(json.dumps({'episode':episode,'config':config,
                                                'times':TIMES,'fonts':check_fonts(root)},indent=2))
    return out/'preview.jpg'

def compose(root,episode,config,plate,out):
    out=Path(out);cards=out/'cards'
    make_cards(root,episode,config,cards)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'format=duration','-of','json',str(plate)]))
    if float(probe['format']['duration'])<29.95:
        raise ValueError('The provider returned a clip shorter than 30 seconds; review the source before retrying.')
    target=out/'credits_30s_review.mp4'
    command=['ffmpeg','-y','-v','error','-i',str(plate)]
    for p in [cards/'header.png']+[cards/f'card_{i}.png' for i in range(7)]:
        command+=['-loop','1','-framerate','24','-i',str(p)]
    filters=['[0:v]scale=854:480,fps=24,trim=duration=30,setpts=PTS-STARTPTS[base]',
             '[base][1:v]overlay=0:0:shortest=1[v0]']
    for i,(start,end) in enumerate(TIMES):
        f=f'[{i+2}:v]format=rgba,fade=t=in:st={start}:d=0.25:alpha=1'
        if end<30:
            f+=f',fade=t=out:st={end-0.2}:d=0.2:alpha=1'
        filters+=[f+f'[c{i}]',f"[v{i}][c{i}]overlay=0:0:enable='gte(t,{start})*lt(t,{end})':shortest=1[v{i+1}]"]
    command+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v7]',
              '-an','-t','30','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    subprocess.run(command,check=True,timeout=300)
    return target
