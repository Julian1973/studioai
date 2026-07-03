# Crystal Bears — Keyframe DEFINITION OF DONE

The single standard every keyframe must satisfy **before Julian sees it**. The QA (`cb_qa.check_done_frame`)
checks each item automatically, on **both** the start frame **and** the end frame of every shot. A scene is not
"done" until every frame passes. Consolidated from the build-out of Ep1 Scene 1 (2026‑06‑22).

> **THIS IS THE FOUNDATION.** The keyframe — one OPENING frame per beat — is the single image the whole clip is built from (Seedance animates forward from it). Get it wrong and everything downstream is wrong. So the bar is **world‑class, feature‑film Pixar 3D‑CGI, stunningly beautiful** — not merely "correct." **Gate 2b now runs this QA automatically (report‑only — never overwrites)** so you only sign off a spot‑on set. (Beat‑native: one opening keyframe per beat — no end frame.)

### The five that guard the foundation (added 2026‑06‑24 — the world‑class bar)
- **BELOW_BAR** — a world‑class, feature‑film‑grade frame: beautiful motivated lighting, polished believable materials, real layered depth, cinematic composition. Flag anything flat, dull, cheap, plasticky, muddy or AI‑mushy.
- **WEAK_POSE** — the character is in a clear, ACTING opening pose that reads in silhouette and carries the beat's feeling (Glen Keane). Flag stiff, neutral, blank, T‑posed or just‑standing.
- **ADDED_PROP** — the character has nothing on its body its turnaround doesn't show (immutability). Flag any added accessory, item or prop bolted onto the body — it will flicker and vanish in the clip.
- **SIZE_MISMATCH** — relative scale is correct (e.g. Fuzzby > Zenny); a smaller character never renders as large as or larger than a bigger one.
- **PLATE_DRIFT** — the environment, layout, camera and composition match the locked scene plate; the world is not re‑invented.

### The sixth (added 2026‑07‑03, Julian — "if the first scene is them flying through the meadow, then they need to be flying through the meadow")
- **ACTION_STATE_MISMATCH** — when the beat's own action text names an active locomotion verb (flying, chasing, diving, zigzagging, weaving, dipping, bouncing, etc. — deliberately excludes "hover", the default bee state), the frame must SHOW that state, not just gesture at it. For a flying character this is checked concretely: wings must be ASYMMETRIC (one raised, one lowered, mid‑downstroke), never both spread flat and symmetrical; the body must lean forward and down into the direction of travel, legs tucked or trailing, never hanging vertical like a puppet at rest. Found live: the "CRISP WINGS" rule (frozen, sharp, non‑blurred — still correct, for identity‑lock clarity) was being satisfied by a symmetric, static‑looking hover pose, which read as floating in place rather than already in flight — forcing Seedance to invent a standstill‑to‑motion transition instead of just continuing existing motion. `cb_prompts.build_keyframe_prompt`'s WINGS/FLIGHT‑ENERGY law and this QA check now ask for and verify the SAME concrete criteria.

## A. Structure (how every frame is built)
1. **Two reference inputs, by role.** Image 1 = the SCENE shot (the locked plate). Image 2 = the all‑characters
   SHEET. Nothing else attached for a normal shot (no size chart — the sheet carries relative scale; a third
   line‑up image causes collage drift).
2. **Start AND end frames use the same structure** — both begin from scene shot + character sheet. The end frame
   additionally gets the start frame as a labelled MOTION ANCHOR (one small delta, static objects don't move).
3. **Reference‑first.** The prompt POINTS AT the references and directs only staging / camera / light / crystal /
   mood. It never re‑describes the bear or the scene.

## B. Per‑frame checklist (the QA gate)
1. **ANATOMY** — every character has correct, complete anatomy: the exact number of arms, legs, wings, paws, eyes,
   antennae (cartoon bee = 2 arms, 2 legs, 1 pair wings, 2 antennae). No extra / missing / duplicated / merged /
   melted limb or feature.
2. **IDENTITY** — every character matches the character sheet exactly: face, fur, proportions, glasses, markings,
   and relative size (Fuzzby the bigger bee with spectacles + tan nose; Zenny smaller with round glasses, long
   eyelashes, blush).
3. **CAST** — only the characters the shot's action names are in frame. No added character, animal, person, or extra.
4. **SCENE / GEOMETRY** — the set, layout, terrain and screen‑direction match the scene reference. Nothing added,
   removed or moved (no stray boats/objects). Geometry is locked; only the characters and framing change.
5. **LIGHTING (per beat)** — the light and mood fit THIS shot's beat, not the scene's opening light. Sunny opening,
   storm at the climax. The geometry stays; the sky/light/weather follow the story.
6. **SHARPNESS / RESOLUTION** — at least **2K** (≥ 2048 px wide), **16:9**, and the character(s) in crisp, tack‑sharp
   focus. Any blur is only in the far background, never on the characters.
7. **CLEANLINESS (transient props)** — a temporary substance on a character (pollen, dust, dirt, water, food, a
   pollen "moustache") appears ONLY if THIS shot's action names it. Otherwise the face/fur are clean. Never carried
   over from the chain or motion anchor.
8. **ONE COHERENT FRAME** — a single film frame. NOT a collage, split‑screen, character sheet, line‑up or two panels.
9. **NO TEXT** — no captions, words, logos, watermarks or UI.
10. **PERFORMANCE** — the still carries the shot's emotion in the face/body (never a neutral pose); end frame is a
    small, believable evolution of the start.

## C. Quality bar
Premium theatrical 3D‑CGI, Pixar/DreamWorks feature quality. On‑brand Crystal Bears world (crystals subtle, present
but never competing). Warm, emotionally engaging, family‑animation polish.

> If a frame fails any item, the QA flags it by name and the self‑correct loop regenerates that shot with the
> specific fix — it is never shown as "done." The standard is enforced by the machine, not by Julian's eye.
