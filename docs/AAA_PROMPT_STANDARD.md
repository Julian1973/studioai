# THE AAA PROMPT STANDARD
## Crystal Bears Studio · Beat → Seedance 2.5 · v1.0 (2026-08-09)

> **The prompt is not the director. It is the provider-specific shooting
> instruction produced from already-approved direction.**

This is the studio's quality bar and the knowledge layer of the prompt engine.
Every compiled prompt is checked against this document. It consolidates fifteen
knowledge sources (official ByteDance/Dreamina guides, the sd25-pe API guide,
official launch examples, Runway's official docs, and five practitioner sets)
with the studio's own laws and the lessons of every render fired so far.

Nothing reaches a render without **two stamps**: `COMPILED BY ENGINE vX` and
`PREFLIGHT: PASS`. A hand-written or hand-edited prompt is invalid by
definition, no matter how good it looks.

---

# PART 1 — GOVERNING LAWS

**L1 · Traceability.** Every field in a prompt traces to an approved upstream
decision (script beat, director's intention, keyframe, audio file, continuity
rule). A field with no upstream approval must not exist — that is a sign
direction is incomplete, not a prompt-writing gap. Missing direction is a
compile-time failure, never something the compiler pads over.

**L2 · Identity from references only.** No appearance words near a character
name or role label in scene text. The reference images carry the face, fur,
scale, glasses, wings. Text does the motion; references do the look.
"Reference anything you can show; describe only what you can't."

**L3 · The voice lives in the render (Law 5).** Dialogue beats carry the
locked `@Audio1` track. Never render dialogue without the track; never swap
voice in post; spoken words appear as "the line in @Audio1", never quoted text.

**L4 · A beautiful render missing a mandatory beat is a FAILURE.** The Scene
Execution Contract's visible requirements are the pass bar, not prettiness.
Verdicts: Delivered / Weak / Missing / Contradicted — plus **performance
drift**: visually consistent but dramatically wrong (celebrates boldly where
the character would relax cautiously). Perfect glasses do not excuse a wrong
performance.

**L5 · One dominant event per shot.** If the shot purpose needs "and" more
than once, it is two shots. Split to pace; never trim to fit.

**L6 · Defects go to the system, never hand-fixes.** A bad prompt produces a
defect report against the compiler or preflight, and the fix lands as a
versioned rule. The next prompt is right because the system changed.

**L7 · Spend on coverage, never on hope.** Re-running a broken prompt
unchanged is the only forbidden spend. 480p first; 720p masters only after
the 480p candidate proves the beat.

---

# PART 2 — MODEL & ROUTE FACTS (the envelope)

| Fact | Value |
|---|---|
| Native duration | 4–30s (or Auto). Single generation holds a full scene arc. |
| Resolutions | 480p, 720p (current ceiling) |
| Aspect | Auto, 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 (any ratio 0.4–2.5 via API) |
| Formats | MP4; **MOV for anything that will be edited/extended** (preserves color + audio continuity) |
| References | Up to 50: **30 images, 10 videos (≤30s each), 10 audio** |
| Reference roles (API) | `first_frame`, `last_frame`, `reference_image/video/audio` |
| Creation modes | Reference · Keyframe (first+last) · Edit · Extend |
| Edit mode | Inherits input length + aspect; trigger keywords required; sketch-on-frame becomes `@Image N at ss:SS` (timestamped image binding) |
| Extend mode | Runs **forwards or backwards** — a shot can be grown before its opening |
| Prompt budget | ~5,000 chars route ceiling; **<3,500 chars for narrative** (headroom is not a target) |
| Audio syntax | `(music: …)` `<sfx>` `"dialogue"` `【…】`; negative control guaranteed only for subtitles/audio ("no subtitles", "no BGM") |
| Timestamps | 2.5 responds to timecoded beats. **2.0 does not** — 2.0/Mini are dead for timing work; 2.5-only is evidence-locked. |
| Multi-view refs | 1–5 subjects: multi-view crops fine. >5 subjects: single view per subject, separate images, never collaged sheets. Never write names inside reference images. |
| Cost (fal) | ~$0.47/s @720p, ~$0.22/s @480p |
| Cost (Runway) | 30 cr/s @720p, 20 cr/s @480p, **plus input-video surcharge** (+15/+10 cr/s) — edits and extends cost more than fresh fires; budget the retake ladder accordingly |
| Routes | **fal** (proven in test) · **BytePlus** (pending qualification, fail-closed) · **Runway** (documented candidate; sketch edits + backward extend live there) |

**Route-envelope discipline:** preflight validates every prompt against the
*selected route's* envelope, not the model's brochure. Writing 30 seconds into
a 15-second route does nothing.

---

# PART 3 — THE EMISSION GRAMMAR (what a compiled prompt looks like)

Block order (v1; audio-first vs style-first is an open experiment — see Part 9):

```
[AUDIO-LOCK]        sole dialogue source; who owns which timecoded region;
                    who is visibly silent; explicit ban list (extra voices,
                    narration, ad-libs, hums, subtitles, music)
[REFERENCE ROLES]   one line per asset: "defines only X · ignore its Y"
[SHOT PURPOSE]      one sentence — the single dramatic/comedic job
[GLOBAL SETTINGS]   the canonical STYLE PARAGRAPH (verbatim, versioned) +
                    light source/direction + GEOGRAPHY block + character
                    conduct truths ("Fuzzby plays proud authority, never
                    distress")
[TIMELINE]          timecoded stages; each stage = observable action +
                    causal link to prior stage + camera behaviour +
                    numeric holds + per-stage END STATE
[CAMERA]            one dominant policy, sequenced not blended; explicit
                    exclusions ("no cuts, no shake, no orbit")
[END STATE]         the final frame, readable as the next shot's opening
[CONSTRAINTS]       production facts only: character count, relative scale,
                    no invented props, no style drift, no gag after the
                    button; anti-drift boilerplate; "face stable throughout,
                    no deformation"
[AUDIO]             final confirmation: @Audio1 unchanged; authorised foley
                    below the voice; "Audio: no music, diegetic sound only"
                    unless post-scored silence is wanted
```

### Block rules

**REFERENCE ROLES — positive AND negative scope, always.** The official gold
form: "@Image 1 defines the shoe: exact shape, bone-white midsole, moulded
logo. **Ignore its black studio background.**" Every reference gets a
defines-only list and an ignore list. One reference never silently carries
two jobs (identity + pose). When references disagree, **the prompt names the
winner**: "The setting is described in Shot 5 and is NOT the street in
Image 2." Conflicts are resolved at compile time, never left to the model.
Never cite an image that isn't attached. When a reference is accurate, say
"refer to it strictly" and do not re-describe its content.

**TIMELINE — causal stages with numeric holds.** Each stage names what caused
it from the prior stage. Emotion is what a feeling does to a body: "the jaw
clenches, the fist closes", never "he is angry". Physics has trajectory,
distance, contact and reaction: "plants left hand on the counter, lifts the
tube with both hands, sets it down without sliding" — contact-point
choreography is the antidote to floaty and clip-through in one rule.
**"Briefly" is not a duration.** Comedy buttons and emotional turns get
numeric holds ("Hold: 2.0s minimum for the pose to read"). Sound is inline
per beat, never a list at the end. Never restate the same action in
different words (duplicate-motion signature of LLM drafts).

**END STATE is a required field.** A longer generation needs a destination.
Official idiom, four independent sources: every shot (and every stage)
closes with an explicit end state — final composition, final pose, camera
stop. The end state is the next shot's opening reference.

**CONSTRAINTS are production facts, never quality words.** "One Fuzzby, one
Zenny only." "No person ever appears inside the apartment." "The track is
lateral and one-directional, never reversing." Never "no bad anatomy".
Negatives are farmed: only defects actually observed in our renders join the
list, via the playbook.

**Density.** Narrative units: 3–4 beats per 15s ceiling, ~150–300 focused
words per 30s as the LEAN calibration; our FULL shape is the other rung of
the density ladder (open experiment). Coverage-lane montages deliberately
break the ceiling.

---

# PART 4 — THE CRAFT LAWS

**C1 · WHERE rule + geography ledger.** Stage the blocking explicitly, and fix
scene geography as constants reused verbatim across every shot of a scene:
"Meadow entrance: frame-left/west · Hive: frame-right/east · Zenny enters
from west · Fuzzby faces east during the gag." Generated shots silently flip
screen direction; the audience feels the rearrangement without knowing why.
Verify direction on the opening frame at SEE sign-off.

**C2 · Camera schema.** Starting size + height/angle + **one main move** +
ending size + pace + explicit exclusions. Camera-move budget ~2 per unit.
Static camera on the punchline. Conflicting grammar words ("drone handheld
locked-off orbit") are a preflight block. Plain film terms only — "cinematic
camera" is banned vocabulary.

**C3 · One mechanism per seam.** Each transition gets exactly one hiding
device: occlusion handoff (foreground sweeps past the lens), sound bridge,
match-on-action, or hard cut. Never stack effects into the same half-second.

**C4 · Sound bridges.** Let the next shot's sound begin under the current
shot's close-up (the scrape before its source is revealed); carry a
signature sound across the cut. Audio counts can be cut triggers ("hard cut
on the third ring"). Off-screen sound is a story device: state what is heard
and never shown.

**C5 · Seam state audit.** At every cut, compare shot A's end state with shot
B's opening: prop hand, gaze direction, wardrobe/damage state, light
direction. The relay does this by construction (harvest settle → re-mint →
approve → next beat); CUT transitions get the four-item checklist in
preflight. If shot B continues shot A's action, write the same framing and
eye placement explicitly into both prompts.

**C6 · Designed negative space.** Generators centre subjects by default;
centred beauty composition destroys a planned reveal. If a character enters
frame-left at 4s, the anchor keyframe holds that space empty. This is a SEE
sign-off question.

**C7 · Withhold-then-reveal.** The official wonder-reveal mechanism: keep the
framing low/tight so the reveal object is invisible, then crane/tilt with a
character's gaze to reveal it. Time-ramps (slow-mo orbit, "time snaps back")
and hard cuts between worlds are legal single-fire devices.

**C8 · Small-face rule.** Expressions that must read get framing that lets
them read. No comedy button on a distant face.

**C9 · Lighting is a sourced event.** Named source, position, hardness,
colour contrast, and its change over time ("warm stall light gradually
reaches the right side of her face"). No unexplained colour changes; no
stacked contradictory looks (golden-hour + neon + moonlight).

**C10 · Rhythm through contrast.** Cut between extreme wide and macro, fast
and still; impact frames; the held freeze. The rhythm is written into the
beats, not hoped for.

**C11 · Objects enter frame through visible hand action.** Nothing pops into
existence.

**C12 · Text in frame is broken.** No titles, captions, signage gags in
generation. Overlays are post's job. Strip arrows/annotations/panel numbers
from every reference before firing (text in refs leaks subtitles).

**C13 · Invisible biography becomes visible behaviour.** "She regrets
leaving" is not renderable. "She hesitates at the sign, touches its
scratched edge, then continues without looking back" is.

---

# PART 5 — CHARACTER SYSTEM

**Reference pack per character** (identity + performance, never one
substituting for the other):
1. Canonical identity portrait + multi-view crops (3 face angles as one
   tagged asset).
2. Full-body/costume sheet.
3. **Habit pose** — how they naturally stand (Fuzzby occupies too much
   space; Zenny compact and level).
4. **Reaction strip** — baseline → pressure → release as one connected
   strip (shows how the character *changes*, worth ten unrelated
   expressions).
5. **Prop-interaction reference** — grip, scale, orientation resolved
   before animation ever runs.

**The visual sentence test.** "You can recognise this character from a
distance because ____." If the answer is eye colour or tiny detail, the
design isn't done. Run every bear's pack at thumbnail size.

**Motion vocabulary per character.** Five verbs that belong, five that
don't, plus a motion-amplitude scale. The choreographer draws verbs from the
character's list; a banned verb near a name is a preflight check. "He walks
in" contains no performance — the verb IS the character.

**Signature tic.** One deliberate, repeatable behavioural imperfection per
character. Recognition through repeated behaviour; a reusable observable cue
that belongs to this character alone.

**Anti-drift lines in every prompt:** the KEEP CONSISTENT clause (face, fur,
outfit, colours, lighting style), "face stable throughout, no deformation",
and single-subject declarations ("one Fuzzby, one Zenny only").

**Stability trick:** one locked subject stays stable when everything around
it is allowed to be loose — keep background characters simple, distant,
silhouetted.

**Environment sheet:** 2–3 angles of each location, same authority
discipline as characters.

---

# PART 6 — THE STYLE PARAGRAPH (one look, enforced everywhere)

One canonical paragraph describes the show's look. It is a **versioned
grammar-pack constant**, pasted verbatim into every keyframe mint AND every
render prompt — the same words at every pipeline stage. It is built once
from approved imagery, approved by Julian, and changed only by version bump.

Its spine is render physics, not brand names:

- **Materials:** subsurface scattering on skin/fur · soft fur with individual
  strands catching light · glossy eyes with catchlights · cloth/fabric
  detail · translucency where light passes through wings/petals.
- **Light:** warm amber key with cool blue fill · soft rim light ·
  teal-orange cinematic grade · golden-hour warmth where scripted.
- **Lens:** shallow depth of field with soft bokeh · gentle ambient
  occlusion · subtle film grain · emotionally warm atmosphere.
- **Design:** appealing exaggerated proportions · large expressive eyes ·
  soft rounded features.

**Brand names are a hard BLOCK.** No "Pixar", "Disney", "DreamWorks",
"Ghibli", no renderer names, no living director/artist signatures. The
physics words produce the look; the trademarks produce legal exposure for a
rentable studio. Preflight enforces.

---

# PART 7 — THE TWO LANES

**Lane 1 · SEC lane (locked beats).** Heavy references (identity packs,
environment sheets, keyframes, @Audio1 — typically 8–18 assets). Every beat
contracted with visible requirements. Three Sign-Offs per shot: SEE
(keyframe/harvested frame) → HEAR (voice) → WATCH (render). 2×480p
candidates per comedy fire. This is where the moustache, the "Nailed it",
and the eye-roll live. Nothing invented, everything traced.

**Lane 2 · Coverage lane (invention material).** For chase-chaos texture,
establishing shots, b-roll, finale spectacle — places where invented angles
are welcome. One fast-cut montage prompt from 2–5s of script; tell the model
explicitly: *"I'm cutting this myself in the edit — load the montage with
extra shots and options."* Fire ~10 at 480p; harvest the bangers into the
edit. **Light references** (fewer refs = more model invention; style holds
via the style paragraph + rough environment). Breaks the beat-density
ceiling on purpose. A 10× 15s batch runs ~$15–35 — a budget line item, not
a splurge. Spend on coverage, never on hope.

The lanes never mix: a locked comedy beat is never fired loose; an
establishing flyover is never ceremonied through three sign-offs.

---

# PART 8 — PREFLIGHT (mechanical, versioned, names its law)

Every check is regex/arithmetic against the engine's own dryrun output —
never an LLM opinion. BLOCK stops the fire; NOTE advises.

**Existing checks (v1, in dailies/preflight.py):** identity-text near names ·
spoken words quoted in prompt · dialogue without @Audio · no reference
bindings · duration outside route clamp · dialogue overstuffed (>~2 w/s) ·
bees near "crystal" · negatives section present · banned vocabulary ·
proven-path adherence.

**New checks from this standard (v2):**
1. **Ending state present** — every stage and the shot itself close with an
   explicit end state.
2. **Route envelope and time tiling** — refs/duration/aspect validated against
   the selected route, not the model. Render stages tile the full approved
   duration consecutively, and every approved dialogue region is placed in an
   overlapping stage as an @Audio cue without copying spoken words.
3. **Char budget** — narrative >3,500 chars is a NOTE; >route ceiling BLOCK.
4. **Camera grammar conflict** — more than one dominant move family, or
   banned vague terms ("cinematic camera"), BLOCK.
5. **Brand names** — studio/renderer/artist names in prompt, BLOCK.
6. **Geography block present** — scene shots must carry the scene's
   geography constants verbatim; a mismatch across shots of one scene, BLOCK.
7. **Motion vocabulary** — a character's banned verb near their name, BLOCK.
8. **Numeric holds** — a comedy/emotional stage without a numeric hold, BLOCK.
9. **Shot-purpose "and" count** — more than one "and", NOTE (split candidate).
10. **Reference scope** — any attached ref not named in REFERENCE ROLES with
    both scopes, BLOCK; any @Image cited but not attached, BLOCK.
11. **Duplicate action sentences** — same verb phrase twice in different
    words (LLM-draft signature), BLOCK.
12. **Seam checklist (CUT transitions)** — prop hand / gaze / state / light
    stated at A-end and B-open, NOTE.
13. **Style paragraph verbatim** — hash of the STYLE block must match the
    versioned constant, BLOCK.
14. **Music kill present** — "no music / diegetic only" (or an explicit
    post-score silence clause), BLOCK.
15. **Complete-sentence integrity** — compiler-owned prose may compact only at
    an authored sentence or clause boundary; empty or clipped emitted prose,
    BLOCK on keyframe, render and voice paths.
16. **Approved physical-staging fidelity** — every approved contact-and-weight
    statement owned by a beat must survive verbatim in the matching render
    stage; keyframe and voice must declare the check non-applicable rather than
    inventing staging, BLOCK.

---

# PART 9 — PATTERN CARDS & EXPERIMENTS

**Seed pattern cards** (each: timing envelope, camera policy, density,
seam device, known holds):
1. **chase-escalation** — rising chaos, jagged vs smooth paths, coverage-lane
   friendly; contrast rhythm (C10).
2. **false-triumph** — chaos → settle → proud hold ≥2.0s; camera locks for
   the button; witness in frame.
3. **deadpan-button** — static camera, small face forbidden, numeric hold,
   silence as the punchline's air.
4. **warm-turn** — eye-roll softening to loving smile; amplitude drops,
   light warms (C9 event), hold the change.
5. **wonder-reveal** — withhold via framing → crane/gaze reveal (C7);
   music kill until the reveal lands.
6. **held-ache** — stillness, breath cycles, "a small private half smile
   arrives and settles"; longest holds in the book.

**Extension plays:** controlled reveal · action relay · **backward extend**
(mint the hero gag first, grow the entry behind it) · camera-only edit
(re-photograph an approved performance: "keep characters, actions, style
unchanged; adjust ONLY the camera") · region edit (when 90% is right,
fix the 10% — always ask "is the defect isolated?" before any full refire).

**Experiment cards (open — settled by renders, not opinions):**
- **E1 Density ladder:** LEAN (150–300 words) vs FULL block grammar on the
  same beat, 2×480p each.
- **E2 Block order:** audio-first (dump 15) vs style-first (official
  exemplars).
- **E3 Multi-view crops vs separate singles** for the two-bee units.
- **E4 First-6s identity lock:** does a calm face-steady opening beat
  measurably reduce drift on comedy shots?
- **E5 Runway route qualification:** sketch-edit and backward-extend value
  vs fal cost baseline.

---

# PART 10 — DIAGNOSIS & FARMING

**Diagnose one layer at a time:** take / keyframe / brief / reference — one
layer per refire, never several at once. Region-edit question first.
Retakes are narrow corrections that name exact deltas ("recoil = one small
step; both hands stay on the lantern; hold relief 2.0s") — "same but better"
is banned.

**The farming loop:** every verdict updates the playbook. Accepted takes
bank their recipe as a proven path (LAW for that archetype until a render
dethrones it). Observed defects join the empirical negative list and, where
mechanical, become preflight checks. The best path is a FILE, not a model's
mood.

**Failure classes:** floaty · off_model · clip_through · flat_comedy · seam ·
audio · continuity · stupid_output · policy_refusal · **performance_drift**
(new: right face, wrong acting) · storyboard-graphics-leak (missing
inheritance exclusions) · placeholder-not-mapped.

---

# SOURCES LEDGER
1. Dreamina features transcript · 2. practitioner collection · 3. realism
transcript · 4. Higgsfield transcript · 5. **official sd25-pe API guide** ·
6. **official launch examples (ImagineArt)** · 7. Seedance2.so synthesis ·
8. shot-formula guide · 9. OC character/performance guide · 10. storyboard
guide · 11. OpenArt guide · 12. **Runway official docs + gold exemplar** ·
13. **"200iq" practitioner guide (coverage doctrine)** · 14. CG-register
keyword guide · 15. SEC-aware compiler-spec draft — plus studio laws
(crystal-bears-studio skill), the S1 render post-mortems, and Chrome-Claude
forensics. Full deltas: seedance-prompt-optimizer skill,
`references/official-source-notes.md`.
