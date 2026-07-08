#!/usr/bin/env python3
"""make_sheet.py — build a professional character MODEL SHEET from a trained LoRA.

Renders FACE CLOSE-UP + FRONT + BACK + LEFT + RIGHT views via the character LoRA and composites them into a
standard model-sheet template: each directional view is SCALED to the character's TRUE height on a shared
height scale (so size is consistent across the cast), plus a data block (name/age/height/weight/gender).

Output: cb-seed/assets/CB_<Name>_sheet.png  — also usable as the character's `turn4` identity reference.
Heights come from config/characters.json (heightIn). Bears share a 6'6" scale; bees share an 8" scale.

Usage:  python3 make_sheet.py fuzzby
"""
import sys, os, io, json
import cb_gen, fal_client, requests            # cb_gen loads FAL_KEY
from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
INK = (45, 43, 38); GRID = (120, 116, 105); FAINT = (175, 170, 158); CREAM = (236, 233, 224)

def _font(sz, bold=False):
    names = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]
             if bold else ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"])
    for p in names:
        try: return ImageFont.truetype(p, sz)
        except Exception: pass
    return ImageFont.load_default()

def _gen(lora, prompt, size, scale=1.1):
    r = fal_client.subscribe("fal-ai/flux-lora", arguments={
        "prompt": prompt, "loras": [{"path": lora, "scale": scale}],
        "image_size": size, "num_inference_steps": 30, "guidance_scale": 3.5, "num_images": 1}, with_logs=False)
    return Image.open(io.BytesIO(requests.get(r["images"][0]["url"], timeout=120).content)).convert("RGB")

def _bbox(im, thr=28):
    bg = Image.new("RGB", im.size, im.getpixel((3, 3)))
    mask = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > thr else 0)
    return mask.getbbox() or (0, 0, im.width, im.height)

def _on_cream(im):
    """Place a grey-bg render onto the cream sheet: matte the near-uniform background to cream."""
    bg = im.getpixel((3, 3))
    base = Image.new("RGB", im.size, bg)
    mask = ImageChops.difference(im, base).convert("L").point(lambda p: 255 if p > 22 else 0)
    out = Image.new("RGBA", im.size, CREAM + (255,))
    out.paste(im, (0, 0), mask)
    return out

def make(character):
    character = character.lower(); trigger = "cb" + character
    chars = json.load(open(os.path.join(HERE, "config", "characters.json")))
    key = next((k for k in chars if k.lower() == character), None)
    cc = chars[key]; desc = cc.get("key_features", "")
    heightIn = cc.get("heightIn", 60); hlabel = cc.get("height", "")
    gender = "Male" if "male" in (cc.get("cadence", "") + cc.get("size", "")).lower() and "female" not in cc.get("cadence", "").lower() else ("Female" if "female" in cc.get("cadence", "").lower() else "")
    lora = json.load(open(os.path.join(HERE, "..", "cb-seed", "training", f"{character}_lora.json")))["lora_url"]
    base = (f"{trigger}, {desc}, brown stubby arms at the sides (no fingers), plain flat light-grey studio "
            "background, flat even lighting, premium 3D CGI Pixar, centered")
    print("rendering views (face + 4 directional)...", flush=True)
    face = _gen(lora, f"{base}, FACE CLOSE-UP portrait, head and shoulders, facing the camera", "square_hd")
    dirs = [("FRONT", "FRONT view facing camera, full body standing straight and still"),
            ("BACK", "BACK view from directly behind, full body, face not visible"),
            ("LEFT PROFILE", "exact LEFT-SIDE PROFILE, full body turned 90 degrees to face left"),
            ("RIGHT PROFILE", "exact RIGHT-SIDE PROFILE, full body turned 90 degrees to face right")]
    views = {nm: _gen(lora, f"{base}, {d}, full body in frame head to feet", "portrait_4_3") for nm, d in dirs}

    W, H = 1500, 820
    sheet = Image.new("RGB", (W, H), CREAM); dr = ImageDraw.Draw(sheet)
    facew = 320; base_y = H - 70; scale_top = 95
    smax, step, unit = (78, 12, "ft") if heightIn >= 24 else (8, 1, "in")
    def y_for(inch): return int(base_y - (inch / smax) * (base_y - scale_top))

    # FACE CLOSE UP panel + data block
    dr.text((facew // 2, 22), "FACE CLOSE UP", font=_font(20, True), fill=INK, anchor="mm")
    dr.rectangle([14, 40, facew - 14, 430], outline=GRID, width=2)
    fim = face.crop(_bbox(face)); fim.thumbnail((facew - 50, 360))
    sheet.paste(_on_cream(fim), (14 + (facew - 28 - fim.width) // 2, 50), _on_cream(fim))
    dy = 470
    for lab, val in [("NAME", key.upper()), ("AGE", ""), ("HEIGHT", hlabel), ("WEIGHT", ""), ("GENDER", gender)]:
        dr.text((26, dy), f"{lab}:", font=_font(19, True), fill=INK)
        dr.text((150, dy), val, font=_font(19), fill=INK)
        dr.line([150, dy + 25, facew - 26, dy + 25], fill=FAINT, width=1)
        dy += 50

    panels = [d[0] for d in dirs]; pw = (W - facew) // len(panels)
    for i, nm in enumerate(panels):
        x = facew + i * pw
        dr.line([x, 30, x, H - 20], fill=FAINT, width=1)
        dr.text((x + pw // 2, 50), nm, font=_font(18, True), fill=INK, anchor="mm")
        sx = x + pw - 46
        for inch in range(0, smax + 1, step):
            yy = y_for(inch); dr.line([sx, yy, sx + 12, yy], fill=GRID, width=1)
            lab = f"{inch // 12}'" if unit == "ft" else f'{inch}\"'
            dr.text((sx + 16, yy), lab, font=_font(12), fill=GRID, anchor="lm")
        dr.line([x + 12, base_y, sx + 12, base_y], fill=GRID, width=2)  # baseline 0
        im = views[nm]; cim = im.crop(_bbox(im))
        target_h = base_y - y_for(heightIn); s = target_h / cim.height
        cim = cim.resize((max(1, int(cim.width * s)), max(1, int(cim.height * s))))
        maxw = pw - 80
        if cim.width > maxw:
            s2 = maxw / cim.width; cim = cim.resize((maxw, int(cim.height * s2)))
        cx = x + (pw - 46 - cim.width) // 2
        glyph = _on_cream(cim); sheet.paste(glyph, (max(x + 6, cx), base_y - cim.height), glyph)

    safe = key.replace("'", "").replace(" ", "")
    out = os.path.join(HERE, "..", "cb-seed", "assets", f"CB_{safe}_sheet.png")
    sheet.save(out); sheet.save(os.path.join(HERE, "media", f"CB_{safe}_sheet.png"))
    print("saved", out, sheet.size)
    return out

if __name__ == "__main__":
    if len(sys.argv) < 2: raise SystemExit("usage: python3 make_sheet.py <character>")
    make(sys.argv[1])
