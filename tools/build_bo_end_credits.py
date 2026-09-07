from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "engine/media/credits_sequence"
TMP = Path("/tmp/bo_end_credits_cards")
TMP.mkdir(exist_ok=True)
bo_path = ROOT / "cb-seed/assets/final_turnarounds/CB_Bo_with_satchel.png"
music = OUT_DIR / "Crystal_Bears_Ep1_End_Credits_Keen_30s_instrumental.wav"
output = OUT_DIR / "Ep1_EC01_Bo_RED_CREDITS_REVIEW_v1.mp4"

font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
title_font = ImageFont.truetype(font_path, 64)
label_font = ImageFont.truetype(font_path, 34)
body_font = ImageFont.truetype(font_path, 38)

source = Image.open(bo_path).convert("RGBA")
# Front-view Bo only; remove the white turnaround ground before compositing.
bo = source.crop((0, 120, 315, 790))
pixels = bo.load()
for y in range(bo.height):
    for x in range(bo.width):
        r, g, b, a = pixels[x, y]
        if r > 180 and g > 180 and b > 180 and max(r, g, b) - min(r, g, b) < 30:
            pixels[x, y] = (255, 255, 255, 0)
bo.thumbnail((650, 720), Image.Resampling.LANCZOS)

cards = [
    [("THE CRYSTAL BEARS", title_font, "white"), ("EPISODE 1", label_font, "#FFD9A0"), ("THE ADVENTURE BEGINS", body_font, "white")],
    [("CREATED BY", label_font, "#FFD9A0"), ("Lloyd Knight and Julian Jenkins", body_font, "white")],
    [("WRITTEN BY", label_font, "#FFD9A0"), ("Lloyd Knight and Pete Young", body_font, "white")],
    [("VOICE CAST", label_font, "#FFD9A0"), ("Lloyd Knight - Pete Young - Julian Jenkins", body_font, "white")],
    [("ANIMATION AND VISUAL PRODUCTION", label_font, "#FFD9A0"), ("Julian Jenkins - Lloyd Knight - Pete Young", body_font, "white")],
    [("MUSIC AND SOUND", label_font, "#FFD9A0"), ("Julian Jenkins and Lloyd Knight", body_font, "white")],
]

for i, lines in enumerate(cards):
    im = Image.new("RGB", (1920, 1080), "#780018")
    draw = ImageDraw.Draw(im)
    draw.rectangle((0, 0, 1920, 1080), fill="#A8183A")
    draw.rectangle((0, 0, 1920, 1080), outline="#D45A6E", width=3)
    im.paste(bo, (230, 220), bo)
    y = 300
    for text, fnt, colour in lines:
        draw.text((1030, y), text, font=fnt, fill=colour)
        y += 90
    im.save(TMP / f"card_{i:02d}.png")

concat = TMP / "concat.txt"
concat.write_text("".join(f"file '{(TMP / f'card_{i:02d}.png').as_posix()}'\nduration 5\n" for i in range(6)) + f"file '{(TMP / 'card_05.png').as_posix()}'\n")
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat),
    "-i", str(music), "-t", "30", "-r", "24", "-map", "0:v", "-map", "1:a",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
    str(output),
], check=True)
print(output)
