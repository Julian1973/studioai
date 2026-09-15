"""Deterministic contact sheet of human-reviewed images; no generative calls."""
from pathlib import Path
import math
import os
import tempfile

from studio_authored_action import digest

ROLE = 'MULTI_GRID_STORYBOARD'
VERSION = 'storyboard-sheet@2'


def panel_binding(panel):
    return digest([panel['id'], panel['inputHash'], panel['media'], panel['atSec'], panel['actionHash']])


def source_binding(status):
    fields = ('id', 'atSec', 'viewId', 'checkpointType', 'inputHash', 'media',
              'reviewStatus', 'review', 'actionHash', 'storyboardRevision', 'directorCardRevision', 'fidelity')
    return digest([VERSION, status['authoredActionHash'],
                   [{key: p.get(key) for key in fields} for p in status['panels']]])


def layout(sizes, max_edge=4096):
    """Local readability budget; not a claim of provider dimension qualification."""
    import statistics
    aspect = statistics.median(w / h for w, h in sizes)
    gap, label_height = 4, 24
    candidates = []
    for columns in range(1, len(sizes) + 1):
        rows = math.ceil(len(sizes) / columns)
        width = min(640, (max_edge - gap) // columns - gap)
        height = min(round(width / aspect), (max_edge - gap) // rows - gap - label_height)
        width = min(width, round(height * aspect))
        if min(width, height) < 160:
            continue
        fitted_short = min(min(w * min(width/w, height/h), h * min(width/w, height/h)) for w, h in sizes)
        if fitted_short < 96:
            continue
        ratio = columns * (width + gap) / (rows * (height + label_height + gap))
        score = abs(math.log(ratio / 1.65)) + (columns * rows - len(sizes)) / len(sizes)
        candidates.append((score, -width * height, columns, rows, width, height))
    if not candidates:
        raise ValueError('Too many panels or incompatible source aspects for a readable single grid. Return to DIRECT or provide compatible framing.')
    _, _, columns, rows, width, height = min(candidates)
    return columns, rows, width, height, label_height, gap


def compile_sheet(root, scope_key, status):
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    panels = status['panels']
    if (not panels or any(p['status'] != 'current' or p.get('reviewStatus') != 'approved' for p in panels)
            or len({p['id'] for p in panels}) != len(panels)
            or [p['atSec'] for p in panels] != sorted(p['atSec'] for p in panels)):
        raise ValueError('Approve every current panel in chronological order before compiling the storyboard sheet.')
    binding = source_binding(status)
    sizes = []
    for panel in panels:
        path = (Path(root)/panel['media']['path']).resolve()
        path.relative_to(Path(root).resolve())
        with Image.open(path) as source:
            sizes.append(source.size)
    columns, rows, width, height, label_height, gap = layout(sizes)
    sheet = Image.new('RGB', (columns*(width+gap)+gap, rows*(height+label_height+gap)+gap), '#101820')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=16)
    manifest = []
    for index, panel in enumerate(panels):
        x = gap+(index % columns)*(width+gap)
        y = gap+(index // columns)*(height+label_height+gap)
        path = (Path(root)/panel['media']['path']).resolve()
        path.relative_to(Path(root).resolve())
        import hashlib
        if hashlib.sha256(path.read_bytes()).hexdigest() != panel['media']['sha256']:
            raise ValueError('Storyboard source image changed during compilation. Review it again.')
        with Image.open(path) as image:
            # Contain preserves the entire frame; padding never invents scene pixels.
            fitted = ImageOps.contain(image.convert('RGB'), (width, height), Image.Resampling.LANCZOS)
            sheet.paste(fitted, (x+(width-fitted.width)//2, y+(height-fitted.height)//2))
        from decimal import Decimal
        timestamp = format(Decimal(str(panel['atSec'])), 'f')
        whole, _, fraction = timestamp.partition('.')
        label = f"P{index+1:02d} | {int(whole):02d}.{fraction.ljust(2, '0')}"
        draw.text((x+8, y+height+4), label, font=font, fill='white')
        manifest.append({'panelId': panel['id'], 'timestamp': panel['atSec'],
                         'viewId': panel.get('viewId'), 'checkpointType': panel.get('checkpointType'),
                         'authoredActionRef': panel.get('viewId'), 'authoredActionHash': panel['actionHash'],
                         'storyboardRevision': panel.get('storyboardRevision'),
                         'directorCardRevision': panel.get('directorCardRevision'),
                         'fidelity': panel.get('fidelity', 'CLEAN_STORYBOARD_PANEL'),
                         'mediaHash': panel['media']['sha256'], 'inputHash': panel['inputHash'],
                         'bounds': [x, y, width, height], 'label': label})
    project = status['scope']['projectId']
    base = Path(root)/('engine/media/see-storyboards' if project == 'crystal-bears' else 'projects/'+project+'/media/see')
    directory = (base/scope_key).resolve()
    directory.relative_to(Path(root).resolve())
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory/(binding+'.png')
    descriptor, temporary = tempfile.mkstemp(dir=directory, suffix='.png')
    os.close(descriptor)
    try:
        sheet.save(temporary, format='PNG')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    from studio_see_package import media
    return {'version': VERSION, 'sourceBinding': binding, 'media': media(root, str(destination)),
            'authoredActionHash': status['authoredActionHash'], 'panels': manifest,
            'columns': columns, 'rows': rows, 'imageCount': 1, 'providerCalls': 0,
            'layoutPolicy': 'source-aspect-readability@1', 'localMaxEdge': 4096}
