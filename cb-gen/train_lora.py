#!/usr/bin/env python3
"""train_lora.py <character> <trigger_word> — train a Flux character LoRA on fal.ai from the curated
training set in cb-seed/training/<character>/. Saves the LoRA weights URL to cb-seed/training/<character>_lora.json.

This is the production fix for character consistency: the character is TRAINED INTO the model (not referenced),
so it renders on-model every time. One LoRA per character (Fuzzby, Zenny, the bears).

    python3 train_lora.py fuzzby cbfuzzby
"""
import os, sys, json, glob, zipfile, pathlib
import cb_gen  # loads cb-gen/.env -> sets FAL_KEY etc. in os.environ
import fal_client

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

def train(character, trigger, steps=1000):
    src = ROOT / "cb-seed" / "training" / character
    imgs = sorted(glob.glob(str(src / "*.png")) + glob.glob(str(src / "*.jpg")) + glob.glob(str(src / "*.jpeg")))
    if not imgs:
        raise SystemExit(f"no training images in {src}")
    zip_path = ROOT / "cb-seed" / "training" / f"{character}_train.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        for p in imgs:
            z.write(p, os.path.basename(p))
    print(f"[{character}] zipped {len(imgs)} images -> {zip_path.name}", flush=True)
    url = fal_client.upload_file(str(zip_path))
    print(f"[{character}] uploaded training zip", flush=True)
    print(f"[{character}] training Flux LoRA (trigger='{trigger}', steps={steps}) — ~20-30 min...", flush=True)
    result = fal_client.subscribe(
        "fal-ai/flux-lora-fast-training",
        arguments={"images_data_url": url, "trigger_word": trigger, "steps": steps, "is_style": False},
        with_logs=True,
        on_queue_update=lambda u: [print("   ", l.get("message", ""), flush=True)
                                   for l in getattr(u, "logs", []) or []],
    )
    out = {"character": character, "trigger": trigger, "steps": steps,
           "lora_url": (result.get("diffusers_lora_file") or {}).get("url"),
           "config_url": (result.get("config_file") or {}).get("url"), "raw": result}
    dest = ROOT / "cb-seed" / "training" / f"{character}_lora.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"[{character}] DONE — LoRA: {out['lora_url']}", flush=True)
    print(f"[{character}] saved -> {dest}", flush=True)
    return out

if __name__ == "__main__":
    os.chdir(str(HERE))
    train(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
