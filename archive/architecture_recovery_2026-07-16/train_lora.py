#!/usr/bin/env python3
"""train_lora.py <character> <trigger_word> — train a Flux character LoRA on fal.ai from the curated
training set in cb-seed/training/<character>/. Saves the LoRA weights URL to cb-seed/training/<character>_lora.json.

This is the production fix for character consistency: the character is TRAINED INTO the model (not referenced),
so it renders on-model every time. One LoRA per character (Fuzzby, Zenny, the bears).

    python3 train_lora.py fuzzby cbfuzzby
"""
import os, sys, json, glob, zipfile, pathlib
import cb_gen  # loads engine/.env -> sets FAL_KEY etc. in os.environ
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
    # FIXED 2026-07-12 (full-codebase audit continued): this used to call fal_client.upload_file/.subscribe
    # directly — the only call site in the repo bypassing cb_gen's shared _retry()-wrapped fal helpers — so a
    # transient network blip or fal queue hiccup during the ~20-30 min paid GPU training call had zero
    # retry/backoff, unlike every other fal.ai call site in cb_gen.py. The upload now routes through
    # cb_gen._fal_upload (already retry-wrapped); the subscribe call is wrapped directly in cb_gen._retry — the
    # SAME shared backoff logic _fal_subscribe itself wraps around — rather than extending _fal_subscribe's own
    # signature just to add this one caller's on_queue_update log-streaming callback.
    url = cb_gen._fal_upload(str(zip_path))
    print(f"[{character}] uploaded training zip", flush=True)
    print(f"[{character}] training Flux LoRA (trigger='{trigger}', steps={steps}) — ~20-30 min...", flush=True)
    result = cb_gen._retry(
        lambda: fal_client.subscribe(
            "fal-ai/flux-lora-fast-training",
            arguments={"images_data_url": url, "trigger_word": trigger, "steps": steps, "is_style": False},
            with_logs=True,
            on_queue_update=lambda u: [print("   ", l.get("message", ""), flush=True)
                                       for l in getattr(u, "logs", []) or []],
        ),
        what="fal:flux-lora-fast-training",
    )
    out = {"character": character, "trigger": trigger, "steps": steps,
           "lora_url": (result.get("diffusers_lora_file") or {}).get("url"),
           "config_url": (result.get("config_file") or {}).get("url"), "raw": result}
    dest = ROOT / "cb-seed" / "training" / f"{character}_lora.json"
    dest.write_text(json.dumps(out, indent=2))
    print(f"[{character}] saved -> {dest}", flush=True)
    if not out["lora_url"]:
        raise SystemExit(
            f"[{character}] training call completed but returned no usable LoRA file — "
            f"got response keys: {list(result.keys())}. Raw response saved to {dest}."
        )
    print(f"[{character}] DONE — LoRA: {out['lora_url']}", flush=True)
    return out

if __name__ == "__main__":
    os.chdir(str(HERE))
    # FIXED 2026-07-12 (full-codebase audit continued): argv[1]/argv[2] were indexed unconditionally while
    # argv[3] alone got a length guard — running this with 0-1 args raised a raw IndexError instead of a clear
    # usage message, unlike sibling CLI scripts in this directory (cb_director.py, cb_writer.py, cb_retake.py,
    # cb_address.py) which all guard a required positional argv with an explicit usage SystemExit.
    if len(sys.argv) < 3:
        raise SystemExit("usage: python3 train_lora.py <character> <trigger_word> [steps]")
    train(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
