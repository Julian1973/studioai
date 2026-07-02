# CRYSTAL BEARS — THE WORLD CLASS ROADMAP
*How the studio becomes world class. Sits beside the Studio Bible. The Bible governs how things are made; the Locked Canon governs what Crystal Bears is; this document governs how the machine earns the word world class. Where they touch, canon wins.*

**The principle: clarity before complexity. Nothing new is built until the numbers say the current machine is learning.**

---

## WHAT WORLD CLASS ACTUALLY MEANS

Not a bigger pipeline. The pipeline already exceeds most funded studios. World class is three things the repo does not have yet:

1. **A taste loop.** Every failure teaches the studio, not just the human. Pixar's edge was never software; it was dailies, notes routed to the right department, and a standard that rose weekly because the system learned.
2. **A measured bar.** "Pixar quality" is a feeling until it is a checklist with numbers stored next to the renders. The bar is written down, scored every episode, and never argued with.
3. **A cadence that ships.** Thirteen consistent episodes in front of a commissioner while competitors are still rendering their second. The output contract is broadcaster grade by default.

The studio is world class when Julian's only jobs are the seed, the taste calls at sign off, and the retake diagnoses. Everything else runs on rails. Make yourself unnecessary.

---

## PHASE 0 — THE FLOOR — ✅ DONE 2026-07-02

*A world class studio cannot stand on a floor with holes in it. From the audit of 2 July 2026. Nothing else starts until these are closed.*

| # | Fix | File | Status |
|---|---|---|---|
| 0.1 | A failed ElevenLabs voice track REFUSES the render. No silent fallback to Seedance's native voice, ever. Law 5. | cb_beats.py | ✅ Done |
| 0.2 | Continuity tail doctrine settled: transients resolve WITHIN each take (Julian's ruling). The dead chaining path is removed, not merely un-gated. | cb_beats.py + cb_seedance.py + Studio Bible 3.1/Part 4 | ✅ Done |
| 0.3 | The second master (15 minds, archetypes, compact validators) declared KEPT in the Bible (Julian's ruling). | cb_seedance.py, cb_beats.py, Studio Bible Part 4 | ✅ Done |
| 0.4 | Docstrings match the wiring — the shipped format is the six-section prose, stated everywhere. | cb_beats.py, cb_seedance.py | ✅ Done |
| 0.5 | Bible amendments: WING LAW recorded, duration rule stated once, SEGMENTS retirement complete, CapCut readme voice-swap language removed. | CRYSTAL_BEARS_STUDIO_BIBLE.md, cb_post.py | ✅ Done |
| 0.6 | Ruling on Bo: confirmed as recurring-guest tier, stub entry added. Reference art still pending (Julian). | CRYSTAL_BEARS_LOCKED_CANON.md, config/characters.json | ✅ Done (canon side) |

---

## PHASE 1 — THE TASTE LOOP AND THE VISIBLE BAR (this month)

**1.1 The retake ledger.** Every RetakeOrder is tagged with its layer (keyframe, brief, reference) AND its failure class: floaty, off model, flat comedy, dead eyes, broken continuity, audio mismatch. Stored in the state file next to the forensics. This is the studio's memory of its own mistakes.

**1.2 The monthly chair review.** Once a month the ledger is read back into the chairs. If forty percent of retakes are weight problems, Keane's craft paragraph in the Director's prompt is sharpened, the change is dated, and the Bible records the revision. A bad clip teaching Julian is a cost. A bad clip teaching the studio is an asset.

**1.3 The Six Question Filter becomes the scored exit exam.** Run at Gate 4 on every episode, all six questions, pass or fail per question, stored in the state file. An episode that fails a question does not ship, whatever the render quality. The Five Anti Patterns are checked in the same pass.

**1.4 QA becomes visible.** cb_qa verdicts graduate from log lines to the sign off screen: the keyframe verdict beside the keyframe, the clip verdict beside the clip, the beat's soul (want, need, crystalTruth, kidRead, adultRead, theGame, wordlessHeld) in front of Julian at Gate 1 sign off. Per the gate flow redesign spec: nobody signs what they cannot see.

**1.5 The gate spine ships.** The Pipeline page becomes home: the stepper, one glowing next action, the unapprove cascade visible. The studio should answer "where am I and what is next" in one glance, every time.

---

## PHASE 2 — IDENTITY AT THE MODEL LAYER AND THE SOUND OF THE SHOW (next)

**2.1 Character LoRAs.** train_lora.py stops being a loaded gun nobody fired. One LoRA per bear and bee, trained on the locked turnarounds, versioned in the asset library. References stay law; the LoRA makes identity survive a thousand renders without vigilance. On model stops being a judgement and becomes a lookup.

**2.2 The versioned asset library.** Turnarounds, plates, props: each hashed, each stamped with the canon version. Every episode records the canon version it was built under. No asset without a version; no version without a date.

**2.3 Gate 5 grows up.** Sound is half of Pixar; Bluey's warmth is scored. The Suno pipeline (Crystal Songs, Sparks and Calls, per the catalogue conventions) is wired in as Giacchino's replacement source for weak Seedance cues. The mix ducks under dialogue automatically; loudness masters to broadcast spec without a manual pass. CapCut by ear becomes the exception, not the workflow. An acquisitions person hears the mix before they consciously see the animation.

**2.4 Sample and select, never generate and pray.** Pixar keeps no first takes; with generative models, takes are nearly free. Every beat renders 3 to 5 takes with seed variation; the vision QA scores each against the turnarounds and the Director's brief; the best two reach the sign off screen. Dailies become choosing between good takes instead of diagnosing bad ones. This is the single biggest quality lever available to the studio and it is pure orchestration on machinery that already exists (seeded renders, forensic logs, cb_qa). Retake rate is measured against the SELECTED take.

**2.5 The data flywheel.** Every approved keyframe and every signed clip feeds the character dataset behind the LoRAs, so the models grow more Crystal Bears shaped with every episode. Approved output is the moat: nobody else on earth holds a thousand on model frames of Fuzzby. The flywheel is automatic at sign off, not a chore; a signed deliverable that does not enrich the dataset is a leak.

**2.6 The model port and the golden set.** NB2 and Seedance 2 are tenants, not the landlord. Assume both are superseded within eighteen months: cb_gen becomes a clean port any model can sit behind, and a golden benchmark set (the You Mind segment plus five approved beats) is the audition every new model must beat before it earns the chair. The same set is the studio's regression suite: any change to a chair's prompt, the assembler, or canon reruns the golden set and the score diff ships with the commit. Nothing merges on vibes. The permanent assets are the canon, the prompt doctrine, the state machine and the taste ledger; every model swap must leave all four untouched.

---

## PHASE 3 — THE CONSISTENCY RUN AND THE OPEN DOOR (the proof)

**3.1 The broadcaster handoff pack, automatic.** Every episode signed at Gate 5 produces its pack without being asked: mastered film, stems, the locked screenplay, the filter scorecard, a bible extract, and (per T31, Addendum A) a CHAIN_OF_TITLE.md recording every asset's provenance. Broadcaster grade by default, because the rooms are already open: Paramount Milkshake correspondence, the Kabillion relationship, Kidscreen behind us, Syndicate in negotiation. The machine's output contract is written for the person who can say yes.

**3.2 The three episode run.** Three episodes back to back through the full machine with a falling retake rate and no canon drift between them. This, not any single beautiful clip, is the studio's real test. Consistency at cadence is the thing nobody else in the room can show. (T32, Addendum A: the cross-episode world ledger is what makes canon drift structurally impossible across this run, not just procedurally unlikely.)

---

## THE BENCHMARK LADDER

*Each rung is pass or fail. No rung is skipped. A failed rung fixes the chair or the canon, never the output: Law 3 pointed at the studio itself.*

| Rung | The test | Passes when |
|---|---|---|
| 1 | Our Director vs You Mind, Segment 1 | The generated brief plus assembled prompt matches or beats the benchmark on comedy, weight and Seedance craft |
| 2 | Ep1 end to end | Every gate signed through the machine, voice in every render, filter score 6 of 6 |
| 3 | Ep2 (post Bo ruling) | A second episode with ZERO code changes: only seeds, canon and taste |
| 4 | The consistency run | Three episodes, falling retake rate, one canon version, packs auto produced |
| 5 | The room | An episode pack in front of a commissioner, produced start to finish inside the cadence target |

---

## THE NUMBERS (tracked per episode, stored in the state file)

- **Retake rate**: retakes per signed clip. Must fall episode on episode. The single most important internal number. If it is not falling, the chairs are not learning and the machine is being hand cranked.
- **Filter score**: Six Question exit exam, x of 6. Ship bar is 6.
- **First pass yield**: clips signed without any retake. Should rise as the taste loop compounds.
- **Julian touch time**: hours of human decisions per episode. World class is roughly two hours of taste, not two days of production.
- **On model rate**: QA vision verdicts passed first time, keyframes and clips.
- **Cost per signed minute**: render spend divided by signed runtime, so quality never hides waste. Sample and select raises render spend per clip and must LOWER cost per signed minute by killing retake cycles; if it does not, the take count comes down.
- **Golden set score**: the benchmark suite result, rerun on every chair, assembler or canon change and on every candidate model. The diff travels with the commit.

---

## THE OPERATING RHYTHM

- **Per beat**: Continuity before every sign off, verdicts visible, no BLOCK survives a signature.
- **Per episode (the Nolting screening)**: watch the assembled cut once, file retakes with layer plus failure class, then the exit exam.
- **Per month (the chair review)**: read the ledger, sharpen exactly one chair, date the change in the Bible.
- **Per quarter**: benchmark ladder review; the commercial doors (Milkshake, Kabillion, Syndicate) checked against what the machine can now put in front of them.

---

## THE STANDING RULES

1. Nothing new is built while the retake rate on the current episode is rising.
2. Taste lives in prose; law lives in code; canon lives in data. Anything found living in the wrong layer is moved the day it is found.
3. When the code becomes sharper than the documents, the documents update the same day. The audit found the code ahead of the Bible; that gap is where drift breeds.
4. No output is ever hand patched. The button does not exist. One lawful exception, because the keyframe is upstream: an art directed repaint of a HERO keyframe (the moustache reveal, the crystal moment, the six frames per episode that carry the poster) is a Law 3 compliant structural fix, entered through Gate 2 with a new sign off, never a patch to a render. Human taste is spent where it carries furthest; the machine owns the rest.
5. The studio serves the show. The show serves the child watching, and the parent beside them. Every number above exists for that and nothing else.
6. The model is a tenant; the canon is the landlord. No model earns the chair without beating the golden set, and no dependency on any model's quirks is ever written into canon, doctrine or state. The studio must survive every model swap with its identity intact.
