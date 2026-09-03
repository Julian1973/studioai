#!/usr/bin/env python3
"""Generate a four-view character reference sheet for a role that has none.

The first brick of the "Lock cast -> Generate a reference" remedy (SELF_HEALING_REFUSALS.md R1).
A scripted role with a voice but no identity reference cannot be rendered: identity comes only
from references, so the studio refuses. This proposes the reference.

What it takes from canon, verbatim, and what it does not:
  * the character's own `key_features` sentence  - the project's words, never rewritten;
  * the project's style law                       - the world it must belong to;
  * an existing approved sheet                    - for STYLE, SCALE and WORLD only, with an
                                                    explicit instruction never to borrow its
                                                    character's face, hair, clothing or build.
Canon defines role and temperament for these roles, not appearance. The provider therefore
PROPOSES the appearance and the showrunner's approval is what makes it canon - the same
machine-proposes / human-approves shape as SEE. Nothing here writes canon; the sheet lands in
the project's media as a candidate. Promotion into assets/ and the canon lock is a separate,
human step (tools/lock_character_sheet.py).

    python tools/generate_character_sheet.py Teacher [--extra "one line of direction"]
"""
from __future__ import annotations

import argparse
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

import paths as P            # noqa: E402
import cb_gen                # noqa: E402
import cb_costs              # noqa: E402

ROUTE = "cb_render"          # the sanctioned production route sentinel

SHEET_SPEC = (
    "Four-view character turnaround reference sheet of ONE character, full figure, standing in a "
    "relaxed neutral pose, on a plain flat light-grey background with even studio lighting and no "
    "cast shadow on the backdrop. Four evenly spaced columns at identical scale and identical "
    "eye-line: column 1 front view, column 2 three-quarter view, column 3 side profile, column 4 "
    "three head-and-shoulders expression studies of the same character. No text, no labels, no "
    "captions, no watermark, no colour chart, no second character."
)


def _canon():
    chars = json.load(io.open(P.CHARS, encoding="utf-8"))
    style = io.open(P.STYLE_LAW, encoding="utf-8").read().strip()
    return chars, style


def _style_anchor(chars, exclude):
    """An already-approved sheet to carry the world's rendering treatment, preferring a
    turnaround over a single anchor. Returns (path, character name) or (None, None)."""
    for key in ("turn4", "anchor"):
        for name, rec in chars.items():
            if name == exclude or not isinstance(rec, dict):
                continue
            rel = rec.get(key)
            if rel and (ROOT / rel).is_file():
                return ROOT / rel, name
    return None, None


def _transport_copy(path, max_edge=1280, budget_bytes=600_000):
    """A light copy of a reference for the wire. BytePlus inlines every image reference as
    base64, so a 2 MB sheet becomes a ~2.7 MB body and this endpoint resets the connection on
    it (observed 2026-09-03, twice, from two processes). Canon still records the SOURCE file;
    only the bytes on the wire are reduced. Returns the original when it is already small."""
    path = pathlib.Path(path)
    if path.stat().st_size <= budget_bytes:
        return str(path)
    from PIL import Image
    img = Image.open(path).convert("RGB")
    scale = min(1.0, max_edge / max(img.size))
    if scale < 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    out = pathlib.Path(P.MEDIA) / "transport" / f"styleref_{path.stem}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=88, optimize=True)
    print(f"  style reference       : {path.name} {path.stat().st_size/1e6:.1f} MB "
          f"-> {out.name} {out.stat().st_size/1e3:.0f} KB for transport")
    return str(out)


def build_prompt(name, chars, style, anchor_name=None, extra=""):
    rec = chars.get(name) or {}
    features = str(rec.get("key_features") or "").strip()
    if not features:
        raise SystemExit(
            f"REFUSED - {name} has no key_features in canon; there is nothing of the project's "
            "own to build the sheet from. Write the character's line in characters.json first.")
    parts = [SHEET_SPEC, "", f"THE CHARACTER (this project's canon, verbatim): {features}"]
    if extra.strip():
        parts.append(f"DIRECTION: {extra.strip()}")
    parts += [
        "",
        f"STYLE LAW (verbatim, non-negotiable): {style}",
    ]
    if anchor_name:
        parts.append(
            f"The attached reference sheet is {anchor_name} from this same production. Match its "
            "rendering treatment, material feel, palette discipline, lens and sheet layout exactly "
            "- the same world, the same show. Use it for STYLE, SCALE and WORLD ONLY: never copy "
            f"{anchor_name}'s face, hair, clothing, build or proportions. This is a different "
            "character who must be instantly distinguishable.")
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--extra", default="", help="one line of directorial guidance")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt and spend nothing")
    args = ap.parse_args()

    chars, style = _canon()
    if args.name not in chars:
        raise SystemExit(f"REFUSED - {args.name} is not in this project's canon roster")
    anchor, anchor_name = _style_anchor(chars, exclude=args.name)
    prompt = build_prompt(args.name, chars, style, anchor_name, args.extra)

    refs = [_transport_copy(anchor)] if anchor else []
    print(f"CHARACTER SHEET - {args.name}")
    print(f"  style/scale reference : {anchor_name or '(none - text only)'}")
    print(f"  estimated cost        : ${cb_costs.estimate_image_cost(len(refs) or 1):.3f}")
    print(f"  prompt ({len(prompt.split())} words):\n{prompt}\n")
    if args.dry_run:
        print("DRY RUN - nothing was generated and nothing was spent.")
        return 0

    out_rel = f"charsheet_{args.name.lower().replace(' ', '_').replace(chr(39), '')}_candidate.png"
    path = cb_gen.generate_image(prompt, refs=refs, out=out_rel, production_route=ROUTE)
    print(f"\nSHEET WRITTEN -> {path}")
    rel = pathlib.Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    print(f"VIEW IT       -> http://127.0.0.1:8765/{rel}")
    print("\nThis is a CANDIDATE. Nothing in canon changed. Approve it, then run:")
    print(f"  python tools/lock_character_sheet.py {args.name} --from \"{path}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
