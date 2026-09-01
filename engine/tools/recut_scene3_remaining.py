#!/usr/bin/env python3
"""Apply Julian's approved Scene 3 recut without rewriting approved earlier shots."""

from __future__ import annotations

import copy
import datetime as dt
import json
import pathlib
import shutil


ROOT = pathlib.Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "engine"))
import paths as P  # noqa: E402 — the project profile is the only path authority (T45)
PACKAGE = ROOT / P.OUTPUT_REL / "Ep1_scene3_production_package.json"


def _shot(package: dict, shot_id: str) -> dict:
    return next(shot for shot in package["shots"] if shot["shotId"] == shot_id)


def _ledger(package: dict, shot_id: str) -> dict:
    return next(row for row in package["continuityLedger"] if row["shotId"] == shot_id)


def _merge_provenance(target: dict, tail: dict) -> None:
    first = target["sourceEventRange"]
    last = tail["sourceEventRange"]
    target["sourceEventRange"] = {
        "firstEventIndex": first["firstEventIndex"],
        "lastEventIndex": last["lastEventIndex"],
        "firstEventId": first["firstEventId"],
        "lastEventId": last["lastEventId"],
        "eventCount": first["eventCount"] + last["eventCount"],
    }
    target["sourceEventIds"] = list(dict.fromkeys(
        [*target.get("sourceEventIds", []), *tail.get("sourceEventIds", [])]))
    target["dialogueOccurrenceIds"] = list(dict.fromkeys([
        *target.get("dialogueOccurrenceIds", []),
        *tail.get("dialogueOccurrenceIds", []),
    ]))


def _supersede(shot: dict, ledger: dict, replacement: str) -> None:
    shot["status"] = "superseded"
    shot["supersededBy"] = replacement
    ledger["status"] = "superseded"
    ledger["supersededBy"] = replacement


def main() -> None:
    package = json.loads(PACKAGE.read_text(encoding="utf-8"))
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    archive = ROOT / P.OUTPUT_REL / "archive" / "scene_recuts"
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE, archive / f"Ep1_scene3_before_two-unit_finish_{stamp}.json")

    b5 = _shot(package, "3.B5.S1")
    b6 = _shot(package, "3.B6.S1")
    b7 = _shot(package, "3.B7.S1")
    b8 = _shot(package, "3.B8.S1")

    b5.update({
        "beatCodes": ["3.B5", "3.B6"],
        "title": "Mum and Keen complete their goodbye; Keen pushes off and covers his first wobble",
        "durationSec": 30,
        "purpose": (
            "Carry the emotional goodbye through its physical consequence without a cold cut: "
            "Mum gives Keen a portable sense of home, Keen answers with love, then climbs into "
            "the boat and leaves. His first wobble releases the ache with character comedy without "
            "undoing Mum's tear."
        ),
        "visualPayoff": (
            "After the held cheek-touch and goodbye, Keen pushes away from the pier, wobbles, "
            "recovers and performs confidence for Mum: 'Still got it!'"
        ),
        "storyBeat": (
            "With both vacant cuffs already fitted, Mum's touch turns inheritance into belonging. "
            "Their goodbye is allowed to land before Keen boards the loaded sailboat, pushes off, "
            "waves, wobbles and converts embarrassment into a tiny captain's boast."
        ),
        "emotionalIntent": (
            "One continuous emotional exhale from love and ache into departure and a small laugh. "
            "The comedy releases the goodbye; it never erases it."
        ),
        "kidRead": (
            "Mum and Keen say they love each other, then Keen sails away and pretends his wobble "
            "was deliberate."
        ),
        "adultRead": (
            "The parent gives the child a portable home and then actually lets him leave; his comic "
            "cover-up is the first brave performance she watches from shore."
        ),
        "action": (
            "Continue directly from the approved final frame of 3.B3.S1. Both vacant gold cuffs are "
            "already fitted, one on each wrist; do not repeat or restage the fitting. Keen turns both "
            "wrists once, looks from the blank settings to Mum, and leans into her gentle cheek-touch "
            "for one breath. They meet each other's eyes and exchange the goodbye lines without "
            "rushing. Hold Mum's final 'my brave boy' in their shared look before either character "
            "moves. Then Keen turns toward the already-loaded sailboat. The boat remains alongside "
            "the pier with exactly one active mooring line and no second bow or stern line. He visibly "
            "releases that single rope from its post, brings it fully aboard "
            "and climbs in. He takes the sheet, pulls the boom and tan sail around, and the wind visibly "
            "fills and tensions the sail. Only then does the hull heel slightly, gather way and leave "
            "the pier bow-first toward open water, with the stern following naturally; never slide "
            "sideways or depart stern-first. Mum lifts one paw; Keen waves back. Preserve the emotional medium-wide while "
            "showing three "
            "parallax speeds: foreground rope, post and near water pass fastest; Keen and the boat "
            "move at a middle speed; Mum, the pier and island recede slowest. The mooring post passes "
            "the camera and vanishes behind, with occasional foreground rope or rigging wipes across "
            "the lens. Let the boat pull slightly smaller as it moves away, then let the camera gently "
            "surge to recover Keen. Allow the boat to drift off-centre toward open water before the "
            "camera restores the shared composition with Mum still readable behind him. As "
            "the wind-powered boat gains a little water between them it wobbles unexpectedly. Keen flails once, "
            "catches himself, checks that Mum saw, straightens into borrowed captain confidence and "
            "delivers 'Still got it!' Mum's laugh comes through the tear. End with the boat moving "
            "cleanly away, Mum still visible on the pier, cargo unchanged, and both empty cuffs visible "
            "on Keen's wrists."
        ),
    })
    b5["dialogueLines"] = [*b5["dialogueLines"], *copy.deepcopy(b6["dialogueLines"])]
    b5["continuityConstraints"] = [
        *b5["continuityConstraints"],
        "The pier, sailboat, tan sail, rigging and loaded cargo remain exactly as established until Keen physically pushes off.",
        "The emotional eye-contact hold finishes before Keen turns toward the boat; departure does not interrupt Mum's final line.",
        "Exactly one active mooring line connects the boat to one post; no second bow or stern line exists. Release that single line and bring it fully aboard before controlling the sheet and boom, showing the tan sail fill under wind load, and letting the hull gather way bow-first toward open water with the stern following naturally; no sideways or stern-first departure.",
    ]
    b5["directorRecord"] = {
        key: copy.deepcopy(b5[key])
        for key in ("storyBeat", "emotionalIntent", "kidRead", "adultRead", "action",
                    "dialogueLines", "continuityConstraints")
    }
    _merge_provenance(b5, b6)
    _supersede(b6, _ledger(package, "3.B6.S1"), "3.B5.S1")

    b7.update({
        "beatCodes": ["3.B7", "3.B8"],
        "title": "Squeaky turns the farewell into first adventure as Keen sails toward open water",
        "durationSec": 24,
        "purpose": (
            "Let the world answer Mum's letting-go with a new companion: Squeaky's arrival turns "
            "Keen's startle into delight, then the boat carries that warmth into the bittersweet final "
            "image of Keen facing open water."
        ),
        "visualPayoff": (
            "Squeaky keeps pace beside the sailboat while the pier and Mum grow smaller behind Keen; "
            "Keen turns forward carrying nerves and excitement together."
        ),
        "sourceShotId": "3.B5.S1",
        "charactersInFrame": ["Keen", "Keen's Mum", "Squeaky"],
        "storyBeat": (
            "Mum laughs through a tear, then Squeaky bursts beside the moving boat and becomes Keen's "
            "first companion beyond home. Their playful exchange flows into the widening distance from "
            "the pier, ending with Keen looking ahead: a little nervous, a little excited, a lot of both."
        ),
        "emotionalIntent": (
            "Let play rush in like sunlight after the ache, then leave a bittersweet wake rather than "
            "resetting the emotion. Mum remains visible until distance, not a cut, carries her away."
        ),
        "kidRead": "A friendly dolphin joins Keen, and together they sail toward an adventure.",
        "adultRead": (
            "The world answers the parent's release with companionship; home recedes without "
            "disappearing from the child."
        ),
        "action": (
            "Continue from 3.B5.S1 with the same sailboat already moving away from the same pier, the "
            "same cargo secured, Mum behind Keen and both vacant cuffs still on his wrists. Mum laughs "
            "through her tear. A sudden splash erupts beside the hull and exactly one Squeaky rises from "
            "the water. Keen startles, then lights up. Squeaky chirps and makes one clean playful leap; "
            "Keen leans safely over the side, answers him, and nods as if he understands every chirp. "
            "Keep the boat progressing throughout: near water moves fastest, the pier and Mum drift "
            "smaller behind, and open blue water grows ahead. After their final exchange, Squeaky keeps "
            "pace beside the hull. Keen looks back once toward Mum, then turns forward. Let delight "
            "settle into a truthful mixture of nerves and excitement. End with Keen and Squeaky moving "
            "toward open water, Mum still readable but small on the distant pier, both cuffs vacant and "
            "unchanged, and the original island geography receding behind them."
        ),
    })
    b7["continuityConstraints"] = [
        *b7["continuityConstraints"],
        "Exactly one Squeaky appears and remains a small friendly dolphin beside the moving boat; no other dolphin or character is invented.",
        "The approved pier, Mum, moored-departure axis, sailboat, tan sail, rigging and loaded cargo remain continuous while distance increases.",
    ]
    b7["directorRecord"] = {
        key: copy.deepcopy(b7[key])
        for key in ("storyBeat", "emotionalIntent", "kidRead", "adultRead", "action",
                    "dialogueLines", "continuityConstraints")
    }
    _merge_provenance(b7, b8)
    _supersede(b8, _ledger(package, "3.B8.S1"), "3.B7.S1")

    b5_ledger = _ledger(package, "3.B5.S1")
    b5_ledger["sourceShotId"] = "3.B3.S1"
    b7_ledger = _ledger(package, "3.B7.S1")
    b7_ledger["sourceShotId"] = "3.B5.S1"

    package.setdefault("revisionNotes", []).append({
        "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "reviewedBy": "Julian",
        "change": (
            "Combined B5+B6 into one 30-second goodbye/departure unit and B7+B8 into one "
            "24-second Squeaky/sail-away unit. B6 and B8 are superseded; no approved earlier "
            "take was changed."
        ),
    })
    PACKAGE.write_text(json.dumps(package, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
