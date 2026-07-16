# PIPELINE CUTOVER LEDGER — "how do I know it's clean and system-wide?"
_2026-07-16 · built from a 6-agent audit (4 mappers + 2 adversarial verifiers), every claim
checked against real code with file:line evidence. Full raw findings preserved in the session
workflow record (run `wf_f89c6831-63a`)._

---

## 1. The honest answer today: it is NOT yet system-wide

Two facts, verified live, zero cost:

1. **The Studio still fires the old pipeline.** Every fire button routes
   `serve.py → cb_pipeline → cb_beats.run → cb_segprompt.emit_v5`. The real compiled prompt
   for 1.B1 from the live beat package is **652 words** — the exact artifact the definitive
   pipeline retired on paper.
2. **The Director Engine is wired to nothing.** `cb_engine` is referenced nowhere in
   `serve.py`, `cb_pipeline.py`, `cb_beats.py`, `cb_replicator.py` or `app.html`, and its
   production package can't even be picked up by accident (its filename doesn't match the
   live package glob).

Two pipelines exist. Only the old one can render. The new one has the right prompts
(142–181 words, your locked anchor contracts, verified 15/15) and no render loop yet.

**The straitjackets are not removed by editing the old pipeline — they're removed by
finishing the new one and archiving the old.** Everything in §3 below dies with the old
path on cutover day; nothing needs to be surgically unpicked.

---

## 2. WHAT STAYS — 36 layers, proven by experience, independent of prompt shape

These protect things that are true in ANY pipeline. None of them constrain the prompt's creativity.

| Protects | The keepers |
|---|---|
| **Script truth** | Dialogue verbatim locks (authoring-time snap + standing re-check), Gate-0 provenance block |
| **Identity** | Reference-first law (no character description, ever), appearance-leak check, size clause, Character Vocabulary lexicons, voice-attribution guards (the Keen-voiced-as-Mum fix), Law-6 spoken-words stripper |
| **Canon** | Crystal World plate check, continuity gate, context gate, laugh-per-pillar, Director's Eye, twelve standing negatives |
| **Money** | One-render economy (fire once, one retry, hard stop), cost ledger + `.gen.json` sidecars, pre-fire refusals (no identity ref / no plate / keyframe-QA-failed = no billed render), Law-5 voice refusal |
| **Provenance** | Approval-as-data + rejection archiving (nothing deleted, ever), gate ordering + fingerprint cascade relock, override-confirmation gates, golden-baseline diff discipline |
| **Craft (human)** | Pixar-craft scorer, ensemble individuation, previz reel before the first paid render — and your reserved verdict, which no check ever approximates |

⚠ Two keepers currently live INSIDE a retiring host (`check_gate3_lint`): the **camera-lock
law** and the **checklist-verb flag**. They must be re-homed before demolition or they're
silently lost. Same for the settle-trim and previz clip-length, which read the retiring 15s
constants — both re-derive from shot durations.

## 3. WHAT COMES OUT — 28 layers, the straitjackets, retired with the old path

All of these exist only to serve or police the 850-word/15-second single-prompt shape:

- **The word-budget apparatus** — the 850-word hard cap, 400 target, and every mirror of it.
  (Note: the cap had crept 400 → 650 → 700 → 850 over two weeks — the clearest evidence the
  old shape kept demanding more words to police itself. The new cap is 210, and ~100 of those
  are your own fixed anchor contract.)
- **The v5 block-shape lints** — block-index model, §4a/§4b structural congruence, citation
  map, negation-by-segment. Twice went stale on their own shape changes.
- **The text-mutating strippers/truncators** — speed-adjective stripper, sentence cappers,
  meta-paren strips. The bug family that broke real prompts four separate times (rules 71–77).
- **The beat-level relay-field family** — `endState`/`endStateStill`/`junctionType`/`opensOn`/
  `relayOpeningNote`/`spatialAxis` as required authored fields. The shot contract's own
  `openingPose`/`endState`/`cutInMotivation` carry these jobs now, per shot, where they belong.
- **The Handle Doctrine** — 15s takes, 2s settles, weighted shot-time ranges. The render unit
  is the 4–8s shot.
- **The beat-level anti-hold @图1 machinery** — superseded by your two locked anchor contracts.
- Assorted shape-servants: settle-distinctiveness, ambience-overlap, reference-position vision
  check, active/background cast split, single-gag-arc heuristic, Fuzzby/Zenny ratio flag.

## 4. YOUR CALLS — 18 layers that rest on your own dated rulings

The big ones (each keeps working until you rule; none blocks the cutover build):

1. **cb_seedance's second validator + 15 director modes + 18 physical archetypes** — you ruled
   this a kept, intentional layer (T3, 2026-07-02). Under the new pipeline the archetype
   physics text does NOT enter shot contracts — your own hand-written reference prompt had
   none, and the shot design's cause-and-consequence prose carries the physics instead. Keep
   the archetypes as *design-time context for the Director Engine* (they already feed it as
   names), retire them as *prompt injections*? Your call.
2. **The Director's Pass** (per-beat Keane staging LLM call) — largely superseded by the
   engine's own design call, which does the same job at scene level in one pass.
3. **The creative manifest fields** — humourLayer, emotionMechanic, want/need, parentLine,
   northStarAnswers, fidelityAllocation, carryMarks, pauseHold, the delivery law. All
   storyboard-level, none touch the shipped prompt. Cheap to keep; your Gate-1 quality bar.
4. **The join-check / harvest / re-mint chain** — adapts naturally to shot level (it's the
   relay mechanism §6 of the doctrine already describes); the question is only whether re-mint
   survives at all under 4–8s shots.

## 5. The gap list — what the new path still needs to render (gates 0–9)

**Delivered (verified real):** director statement · shot list (15 shots, one performance
assignment each) · compiled contracts with your verbatim anchors · continuity ledger seed ·
four review criteria · human review doc · reference slot maps (added today).

**Reusable with a thin adapter (already built, beat-shaped):** voice synthesis (cb_voice) ·
keyframe generation + visual QA (cb_gen/cb_prompts/cb_qa) · relay-frame harvest (cb_scene) ·
three of the four review scores — Canon (identity QA), Physics (clip QA), Continuity
(join check) · timecoded retakes · scene stitch + post (cb_post).

**Missing (build items, in order):**
1. **Per-shot fire function** — upload refs in `referenceSlots` order + audio, send the
   contract via `generate_video_seedance_ref(raw_prompt=True)`, write cost/gen sidecars.
2. **Dialogue-line-to-shot assignment** — the one real DESIGN gap: the shot knows WHO speaks
   and HOW, but the verbatim lines live in the beat. Fix: a `dialogueLines` field on the shot,
   verbatim-gated against the script (same lock as always).
3. **Voice per shot → animatic (Gate 5)** — audio timings test the scene before any image money.
4. **Harvest + ledger update loop** — approved shot → final frame → next relay anchor.
5. **Four-score review sidecar** — the *Direction* score ("does the joke land") stays yours,
   by design; the other three are machine checks re-pointed at shots.
6. **Gate wiring + Studio surface** — the audit found the minimum viable Studio change is
   ~4 small additions (one allow-list line, two POST routes cloning existing wrappers, one
   "Shots" page on the Canvas-tab pattern). The old gates keep working beside it untouched.

**Fixed today, found by this audit:** shot duration now schema-enforced (4–8s, a 12s shot
can't ship silently) · the Keen-inside-"Keen's Mum" binding collision closed before it ever
fired · reference slot maps persisted in the package · a stale docstring. Named and still
open: the engine's own design-call LLM spend isn't in the cost ledger yet (same pre-existing
gap as the Director's Pass); §9's visual finishing (grade/flicker/stabilise) is deliberately
Julian-in-CapCut, not software.

## 6. The cutover order — and the one rule that protects you

1. **Build the render loop** (items 1–5 above) on top of the Scene 1 production package.
2. **First real approved shot** through the new loop — the proof, on footage, not on paper.
3. **Point the Studio at shots** (the ~4-change minimum set; 6 named hazards to defuse, all
   mapped with line numbers).
4. **Then archive the old path** — the RETIRE column of §3, moved to archive, never deleted.

The one rule: **the old pipeline is not switched off before the new one has produced a real
approved shot.** Not sentimentality — if it's archived first, there is zero working pipeline.
The moment step 2 lands, there is no way back to the old way, because the old way is no longer
wired to anything.
