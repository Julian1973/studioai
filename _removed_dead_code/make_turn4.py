#!/usr/bin/env python3
"""make_turn4.py — build a clean 4-way character TURNAROUND from a trained LoRA.

The system's turnaround factory. The character LoRA renders the character on-model from any angle, so we
generate front / right / back / left, stitch them into one clean model-sheet strip, and save it as the
character's identity reference: cb-seed/assets/CB_<Name>_turn4.png.

cb_prompts._turn4_ref() PREFERS this file for every keyframe. It is the reference that HOLDS identity
where the old busy multi-view grid genericised it (Nano can't lock a face from a row of tiny views — it
averages them into a plain bee/bear). Clean 4-way = identity locked AND every angle available.

Pipeline:  train LoRA (train_lora.py) -> make_turn4.py -> register "turn4" in config/characters.json.

Usage:  python3 make_turn4.py fuzzby
        python3 make_turn4.py zenny "small bee, round glasses, long eyelashes, rosy blush cheeks"
"""
import sys, os, json, io
import cb_gen, fal_client, requests          # cb_gen loads FAL_KEY from .env
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

def make(character, desc=None, trigger=None, scale=1.1):
    character = character.lower()
    trigger = trigger or ("cb" + character)
    lora_f = os.path.join(HERE, "..", "cb-seed", "training", f"{character}_lora.json")
    if not os.path.exists(lora_f):
        raise SystemExit(f"no LoRA for {character} — train it first (train_lora.py); missing {lora_f}")
    lora = json.load(open(lora_f))["lora_url"]
    if not desc:                              # identity tells from the SSOT config
        chars = json.load(open(os.path.join(HERE, "config", "characters.json")))
        key = next((k for k in chars if k.lower() == character), None)
        desc = (chars.get(key, {}) or {}).get("key_features", "") if key else ""
    Cap = "".join(p.capitalize() for p in character.split("_"))
    base = (f"{trigger}, {desc}, brown stubby arms resting at the sides (no fingers), BOTH translucent "
            "wings present, clearly visible and symmetrical (never a single wing, never a missing wing), "
            "full body, standing straight and still, character model-sheet turnaround pose, plain flat "
            "light-grey studio background, flat even lighting, centered, premium 3D CGI Pixar")
    views = [("front", "FRONT view, facing the camera directly, a wing on each side"),
             ("right", "exact RIGHT-SIDE PROFILE view, body turned 90 degrees to face right, both wings visible behind"),
             ("back",  "BACK view seen directly from behind, showing his back with BOTH wings fully spread and "
                       "clearly visible (two wings, one on each side), face not visible"),
             ("left",  "exact LEFT-SIDE PROFILE view, body turned 90 degrees to face left, both wings visible behind")]
    imgs = []
    for name, d in views:
        print(f"[{character}] rendering {name} ...", flush=True)
        r = fal_client.subscribe("fal-ai/flux-lora", arguments={
            "prompt": f"{base}, {d}.", "loras": [{"path": lora, "scale": scale}],
            "image_size": "portrait_4_3", "num_inference_steps": 30, "guidance_scale": 3.5, "num_images": 1,
        }, with_logs=False)
        imgs.append(Image.open(io.BytesIO(requests.get(r["images"][0]["url"], timeout=120).content)).convert("RGB"))
    h = min(i.height for i in imgs)
    imgs = [i.resize((int(i.width * h / i.height), h)) for i in imgs]
    strip = Image.new("RGB", (sum(i.width for i in imgs), h), (210, 210, 210))
    x = 0
    for i in imgs:
        strip.paste(i, (x, 0)); x += i.width
    out = os.path.join(HERE, "..", "cb-seed", "assets", f"CB_{Cap}_turn4.png")
    strip.save(out); strip.save(os.path.join(HERE, "media", f"CB_{Cap}_turn4.png"))
    print(f"[{character}] saved {out}  {strip.size}")
    print(f"  -> now register it in config/characters.json:  \"turn4\": \"../cb-seed/assets/CB_{Cap}_turn4.png\"")
    return out

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 make_turn4.py <character> [identity description]")
    make(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
