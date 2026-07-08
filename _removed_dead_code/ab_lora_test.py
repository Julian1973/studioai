#!/usr/bin/env python3
"""ab_lora_test.py — STANDALONE A/B: render a couple of Scene-1 beats via Flux+LoRA (img2img from the
existing plate) so we can judge LoRA character-lock + the Flux-vs-Nano look/seam BEFORE any pipeline surgery.
Touches nothing in the live pipeline. Reads weights+trigger straight from cb-seed/training/<char>_lora.json.

    python3 ab_lora_test.py
Outputs media/AB_<beat>_flux.png next to the current Nano media/Ep1_<beat>_*.png for side-by-side.
"""
import os, sys, glob, json, pathlib, requests
import cb_gen  # loads .env -> FAL_KEY
import fal_client

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MEDIA = HERE / "media"
TRAIN = ROOT / "cb-seed" / "training"

def lora(char):
    """{trigger, url} from the trained side-car, or None if not trained yet."""
    f = TRAIN / f"{char}_lora.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    url = d.get("lora_url") or (d.get("raw", {}).get("diffusers_lora_file", {}) or {}).get("url")
    return {"trigger": d.get("trigger"), "url": url} if url else None

def char_cfg(name):
    cfg = json.loads((HERE / "config" / "characters.json").read_text())
    return cfg.get(name, {})

def render(beat_code, cast, prompt, plate, scale):
    """One Flux+LoRA img2img render anchored to the plate. cast = [char names with trained LoRAs]."""
    loras = []
    for c in cast:
        lo = lora(c)
        if not lo:
            print(f"  ! {c} has no trained LoRA yet — skipping {beat_code}"); return None
        loras.append({"path": lo["url"], "scale": scale})
    args = {
        "prompt": prompt,
        "loras": loras,
        "image_url": fal_client.upload_file(str(plate)),
        "strength": 0.45,               # hold the plate, paint the bee(s)
        "image_size": "landscape_16_9",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "output_format": "png",
    }
    print(f"  {beat_code}: Flux+LoRA img2img ({len(loras)} LoRA) — rendering…", flush=True)
    res = fal_client.subscribe("fal-ai/flux-lora/image-to-image", arguments=args)
    url = res["images"][0]["url"]
    out = MEDIA / f"AB_{beat_code}_flux.png"
    out.write_bytes(requests.get(url, timeout=300).content)
    print(f"     -> {out}", flush=True)
    return str(out)

def main():
    pkg = max(glob.glob(str(ROOT / "cb-output" / "Ep1_*beat_package.json")), key=os.path.getmtime)
    beats = {b.get("beatCode"): b for b in json.load(open(pkg)).get("beats", [])}
    plate = MEDIA / "Ep1_S1_plate.png"
    if not plate.exists():
        sys.exit(f"no Scene-1 plate at {plate}")
    fz, zn = lora("Fuzzby"), lora("Zenny")
    print(f"LoRAs ready -> Fuzzby: {'yes' if fz else 'NO'} | Zenny: {'yes' if zn else 'NO'}")

    # --- TEST 1: solo Fuzzby (1.B1) ---
    b1 = beats.get("1.B1")
    if b1 and fz:
        ft = fz["trigger"]
        p = (f"{ft}, a plump fuzzy yellow-and-black cartoon bumblebee with round wire-frame glasses and a tan nose, "
             f"{b1.get('startState','hovering, proud')}. Golden sunlit rainforest with giant flowers and floating pollen. "
             f"Full body, single character, premium 3D animation, cinematic, no text.")
        render("1.B1", ["Fuzzby"], p, plate, scale=0.85)

    # --- TEST 2: both bees (1.B3) — the hard one ---
    b3 = beats.get("1.B3")
    if b3 and fz and zn:
        p = (f"{fz['trigger']} the bigger yellow-and-black bumblebee with wire-frame glasses and a tan nose on the LEFT, "
             f"and {zn['trigger']} the smaller bee with round black glasses, long eyelashes and rosy blush cheeks on the RIGHT. "
             f"{b3.get('startState','both hovering in a sunlit rainforest')}. Golden rainforest, floating pollen. "
             f"Both characters full body, premium 3D animation, cinematic, no text.")
        render("1.B3", ["Fuzzby", "Zenny"], p, plate, scale=0.75)

    print("DONE — compare AB_*.png against the current Ep1_1.B*.png")

if __name__ == "__main__":
    main()
