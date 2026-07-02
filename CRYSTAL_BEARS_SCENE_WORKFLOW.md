# THE CRYSTAL BEARS SCENE WORKFLOW — consistent scenes, by construction

**Companion to `CRYSTAL_BEARS_PROCEDURE.md`.** The PROCEDURE governs *how* we drive the system
(data → prompts, never hand-prompt, gated sign-off). This doc governs *the consistency craft itself* —
how a scene is built so characters, sets and props don't drift. It distils the cross-model consensus
(GPT-5.5 / Opus 4.8 / Gemini 3.1) and the LTX Studio architecture, and maps every principle to the part of
**our** pipeline that already implements it — or the gap we still need to close.

---

## 0. The one principle everything hangs on

> **Consistency is won at the STILL-IMAGE stage, not during video generation.**

Nano Banana is a **layout + continuity department**, not the animator. Its job: locked scene plates,
stable identity, and start/end keyframes. The video model's *only* job is motion between two
already-consistent frames. If a shot drifts, it is almost always because we asked the still stage to
*invent* two independent images instead of *deriving* the second from the first.

Every model agrees on the single highest-leverage move:

> **Make the END frame by deriving it from the START frame — never generate it fresh.**

We already do this (`cb_scene.py` passes the start frame as the base image into `build_end_prompt`).
This doc exists to keep that discipline and harden the rest of it.

---

## 1. The five-layer consistency stack (LTX framing) — mapped to our pipeline

| Layer | What it does | Our implementation | Status |
|------|--------------|--------------------|--------|
| **1. Identity lock** (named persistent refs) | One character = one stored anchor, injected wherever tagged | `config/characters.json` anchors + `char_refs()`; reference-only ("use Image A exactly", never describe) | ✅ **Have** |
| **2. Image conditioning / master-shot** | First frame anchored to a locked master plate; all coverage derives from it | Frozen master per scene (`build_master` → kept); `build_keyframe_prompt(master_path=...)` derives every shot | ✅ **Have** |
| **3. Surgical edit (Retake / inpaint)** | Fix a rendered shot by changing only the bad region | End-from-start uses the start as continuity base; **true masked inpaint not wired** | ◑ **Partial** |
| **4. Structural control** (pose / depth / edge) | Constrain spatial layout (e.g. boat side) from a reference | Not wired (we lock the boat by data + QA instead) | ⬜ **Gap (optional)** |
| **5. Prompt anchoring** (fixed identity block) | A fixed key-features block in every prompt | `identity_line()` reinforces each character's signature traits on every shot | ✅ **Have** |
| **+ QA / continuity checker** | *Detects* drift after generation | `cb_context` (data pre-flight) + `cb_continuity` (data) + `cb_qa` (pixels, vision model) | ✅ **Have — the layer LTX does NOT have. This is our edge.** |

**Read this honestly:** LTX's five layers *reduce the probability* of drift. None eliminates it —
"each generation is stochastic" is true for every model in 2026. Our QA-verify loop is what catches the
drift that slips through and re-rolls it. Prevention + detection together is the whole game; we are the
only one of the two systems that has both.

---

## ★ THE ANCHOR GATE — sign off the foundation before the scene fans out (CORE PROCESS)

A scene is built **foundation-first**. The keyframe stage (Gate 2) splits in two; **nothing derives until
the anchors are signed off and frozen.** This is the answer to "how do we agree and sign off the first
image": you approve the *foundation alone* — cheaply, with full attention — before the scene fans out into
coverage. A flawed foundation is then caught on the anchor, never on a board of six.

**The foundation = three locked elements (separating world from identity completely):**
- **Turnarounds — canonical identity (from the library).** The real per-character turnaround/anchor art for
  the scene's cast, surfaced at the top of the scene. The identity *authority*; not generated. Pulled from
  the character library (future: the Elements library).
- **A1 — Scene PLATE (the world).** A clean establishing **environment plate with NO characters in it** —
  full set, locked lighting / time / weather, hero set-pieces placed (boat, pier, crystals), screen
  direction set; an empty stage. Obtained three ways: **Upload · Pull from Elements · Generate Scene.** It is
  the world authority and is reusable across scenes at the same location. Coverage *places characters into
  it.* (On sign-off it becomes the scene master that every shot derives from.)
- **A2 — Scene-state character sheet (identity in context).** A clean, on-model **group shot of the scene's
  cast in *this* scene's exact state** (wardrobe, wristband state, carried props), neutral staging. Bridges
  the canonical turnarounds to the scene's specific wardrobe/state; auto-included on every derived shot.

Why the plate is character-free: it makes the world an independent, reusable lock (no poses baked in), and
it fully separates the two jobs — the **plate** owns the set, the **turnarounds + sheet** own identity. A
wide establishing frame is a poor place to lock a fine feature (a head-tuft barely resolves at that scale);
the sheet and turnarounds do that instead.

**GATE 2A — anchor sign-off**
1. Build **A1 + A2** only. Nothing else.
2. **I verify both before Julian sees them** — context audit 0-BLOCK → continuity 0-BLOCK → visual QA PASS.
   Only clean anchors reach him; he gets a role-level verdict, not raw flags.
3. **Julian signs off the foundation** (both anchors) against a fixed checklist: **set/world · characters
   on-model · lighting & mood · props + state · screen direction · does it feel like the scene.** Notes →
   re-roll *only* the flagged anchor → re-verify → re-present. Nothing downstream renders.
4. On sign-off **both anchors are FROZEN** — locked forever, never auto-regenerated.

**GATE 2B — coverage (the bits off the anchors)**
5. Every other shot derives from **both** frozen anchors (A1 world + A2 identity) **and** chains from the
   prior shot's end frame — ≤6 refs per the cap.
6. I verify the board (same three checks) → present → Julian signs off coverage → Gate 3 (clips).

**Cross-scene anchor hierarchy.** A recurring location's **first** locked A1 is the reference every later
scene at that location must match (Cove pier: scene 3 → 8 → 10). Order of authority:
**location master → scene A1 → coverage.**

> This formalises §2 (locked asset pack) and §4 (shot construction) into a **gated, signed-off** step. The
> master/plate is no longer built-and-derived in one move (the flaw that made Scene 3 hard to sign off) —
> the foundation is locked on its own first.

---

## ★ STATEFUL LOCATIONS — the world remembers (cumulative cross-scene state)

A location is not a fixed backdrop you re-stamp each visit — it is an **object that remembers.** If a scene
changes a place (storm strews the beach, a cup gets knocked over, something is left behind), the **next time
we return to that place the change is still there.** The longer the episode runs, the more each location has
accumulated. Returning to a location must inherit its **last-seen state**, not its original anchor.

**How it works in our pipeline:**
- **`locationId`** (in `locations.json`) groups the scenes that are the *same place* (e.g. scenes 8 and 10 are
  both `crystal_cove_beach`). The first scene at a `locationId` **establishes** the plate; later scenes **return.**
- **`worldState`** (in `continuity.json`) is the change ledger: `{locationId, atScene, change, persists}` — *at
  scene X, this place changed in way Y, and Y sticks.* (e.g. `crystal_cove_beach` at scene 8: "storm-strewn —
  a tide-line of driftwood and seaweed, wet sand.")
- **Return-derivation** (`cb_prompts.location_history` → `cb_scene.build_plate`): a returning scene's plate is
  built **from the most recent earlier plate of the same `locationId`** (its last state) + the accumulated
  `worldState` changes up to that scene — *not* from the generic anchor. It's shot-chaining, one level up:
  scene-to-scene across non-adjacent visits.
- **The checker** (`cb_continuity` §5) surfaces every returning-location relationship and flags a plate that is
  *older* than its last state (a stale return that didn't inherit the changes).

**The rule, stated plainly:** establish a place once; every return chains from where we last left it, plus
what's happened since. First visit establishes; the world only ever moves forward. (Distinct from `lost` —
which removes a thing forever — and `persistent` — which accumulates an item *inside* a thing; `worldState`
mutates the *place itself*.)

---

## 2. The locked asset pack (set once per scene, reused everywhere)

Every scene begins from a small, curated, **locked** pack — never assembled ad-hoc per shot:

- **One character sheet per character** (front / 3-quarter / profile / full-body where possible) — `characters.json` anchors. *Never replaced mid-production.*
- **One environment master plate** per location + lighting state — the scene's frozen master.
- **Prop / hero-object refs** for recurring items — `continuity.json` `recurring` / `items`.
- **Previous shot's END frame** when a shot continues directly (the chain handshake).

**Asset rules**
1. One approved sheet per character; one approved plate per location+lighting; do not swap mid-scene.
2. Outfit/state variants (e.g. Keen wristbands none→vacant→crystal) = the *same* identity with only the
   changed accessory ref — not a new character.
3. Start and end frames at the **same aspect ratio + resolution** (we use 16:9 throughout).

---

## 3. The curated reference cap — **NEW RULE**

> **Consistency plateaus around ~6 well-chosen references. More refs can REDUCE fidelity** (the model
> dilutes a specific identity across too many signals — the exact mechanism behind a dropped bow/collar).

**Reference hierarchy (priority order when assembling a shot's refs):**
1. **Scene master plate** (environment + lighting + screen direction)
2. **Hero character identity** anchor (the shot's lead)
3. **Second character** anchor
4. **Continuity frame** — previous shot's END (chain) *or* this shot's START (for the end frame)
5. **Hero prop / item ref** active in this shot
6. (room for one more only if essential)

**Procedure rule:** cap a shot's reference stack at **~6**, dropping from the bottom of the hierarchy
first (least-important prop refs go before identity/master). A shot needing >6 is a sign the shot is
overloaded — split it. *Status: we currently sit at 2–5 refs/shot, under the cap, but it is not yet
enforced in `cb_prompts`. → small hardening to add: a priority-ordered cap so future crowd shots can't
silently blow past it.*

---

## 4. Shot construction — board the stills before you animate

Build the whole scene as start/end stills, reviewed, *before* any clip is rendered (cheap to fix here,
expensive to fix after motion). This is exactly our **Gate 2 (keyframes) → sign-off → Gate 3 (clips)**.

1. **Lock the scene plate** — one clean master of the location (layout, light, mood, world styling). → `build_master`, QA-verified before anything derives. *The master must be correct first; a flawed master propagates to every shot (this is what bit Scene 3 — Mum's missing collar on the master).*
2. **Build the START frame** — locked identity + locked plate; prompt only framing, lens, pose, emotion. → `build_keyframe_prompt(master_path=...)`.
3. **Build the END frame FROM the start** — start frame as the direct continuity base; change *only* the one pose/expression/blocking beat. → `build_end_prompt(start)`. Never fresh.
4. **Review the pair** — identity, costume, scale, set geometry, lighting, camera all match; the end reads as *the same shot a few seconds later*. → `cb_qa` + the studio's START↔END wipe slider.
5. **Animate between them** — motion-only prompt (Gate 3). Never re-describe design or rebuild the set.

---

## 5. Start/End frame rules (so the video model interpolates, not jump-cuts)

A start/end pair must read as **one camera take, seconds apart.** Too different → the model invents a cut,
lens switch, or unstable morph instead of motion.

**Good pair:** same camera height + lens, same light direction + colour, same set layout, same identity,
**one** action beat changes.
**Bad pair:** wide→close-up in one interpolation; different set layout; big costume/prop/proportion change;
too many actions at once.

**→ One action beat per shot.** A turn, a look, a step, a hand-raise — then cut and make the next beat the
next shot. Packing "camera move + big blocking + emotional shift" into one start→end is where identity and
set drift appear. (Our `duration` is content-driven 2–15s; keep the *delta* between frames small even when
the hold is long.)

---

## 6. Shot chaining (continuity across a sequence)

For **continuous** action, the **last frame of clip N becomes the start frame of clip N+1** — each shot
inherits the exact latest world state. → `cb_scene` threads `prev_end` as `chain_ref`; `cb_gen lastframe`
extracts the real last frame.

| Shot type | Start source | End source | Method |
|-----------|-------------|-----------|--------|
| Same camera, continuous | prev END frame + locked refs | edit of start | direct chain |
| New angle, same location | locked char + scene plate (+ prev end for context) | edit of start | rebuild on same plate |
| New location | new scene plate + locked refs | edit of start | fresh scene anchor |
| Insert / prop close-up | prop ref + scene plate | edit of start | keep local light + style |

**Do NOT chain across a deliberate CUT** — anchor to the scene master instead (chaining is for continuous
motion only). A vision/dream breaks the chain and derives from its *own* target-scene master.

---

## 7. Animation prompt rules (Gate 3)

Describe **movement, acting, camera motion only.** Do not redesign the character or rebuild the scene —
that reintroduces the ambiguity the frame pair was built to remove. → `build_i2v_prompt` (sectioned:
FRAME CONTINUITY / PHYSICS / CAST / ACTION / PERFORMANCE / BEATS / DIALOGUE / AUDIO / LOCKS).

- One clear motion path / acting beat.
- Short duration (~3–5s ideal for tight start/end adherence; longer only for a held beat).
- Preserve exact start + end compositions.
- Explicitly forbid new objects, new characters, lighting changes, camera jumps (our `LOCKS`).

---

## 8. Failure modes → the lever that fixes them (in OUR system)

| Failure | Cause | Fix (procedure, not hand-prompt) |
|---------|-------|----------------------------------|
| Background morphs mid-shot | start & end generated independently | end-from-start (already enforced); verify the pair in QA |
| Character drifts off-model | wrong ref / too many refs / action too big | one locked sheet; **cap refs at ~6**; shorten the motion |
| Looks like a hard cut | start & end too different | make frames more similar; reduce shot ambition; split the beat |
| Camera inconsistent | end changed framing too much | keep the lens; move a new angle to a new shot |
| Scene gets noisier over time | repeated fresh regeneration | chain from prior end + edit-mode; **don't re-roll, derive** |
| A signature feature drops (bow/collar/tuft) | stochastic variance on a key frame | `identity_line` keeps it in-prompt; **`cb_qa` catches it and the loop re-rolls** until it passes |
| A flawed MASTER poisons the scene | master built before the lock existed | `build_master` rebuild + QA-verify *before* deriving (never auto-overwrite a good master) |

---

## 9. What's DONE vs. the GAPS worth closing

**Already built (validated by this research):** frozen master + QA-verify · master-derive every shot ·
end-from-start · chaining · reference-only identity + `identity_line` · one-ref-per-asset · content-driven
single-beat shots · data-locked sets/props/items · **the three-tier checker (context → continuity → pixels)
that LTX has no equivalent of.**

**Gaps / hardenings (priority order):**
1. **Enforce the ~6 reference cap** with the priority hierarchy in `cb_prompts` (§3). Cheap; prevents future crowd-shot dilution. *We're under it today — make it impossible to exceed.*
2. **Truer edit-mode** for set-stubborn fixes — masked inpaint on the still (NB region edit) rather than re-rolling the whole frame, mirroring LTX Retake's "preserve the majority, change the minimum." *Validate the NB inpaint-vs-regenerate comparison first.*
3. **(Optional) Depth/pose structural control** for hard spatial locks (boat side, character position) if data+QA ever proves insufficient.
4. **(Future, big-investment) Character LoRA** per principal bear (20–30 images, weight-level identity) — the deepest lock, for when volume justifies the training cost.

---

## 10. The mindset

Stop asking the AI to *invent* a scene over and over. Force it to behave like a **controlled layout and
continuity department**: locked references, edit-derived end frames, short action beats, chained handoffs —
then the video model only ever solves for motion between two already-approved states. Prevention does the
heavy lifting; our QA checker catches what slips. That combination is the whole system.
