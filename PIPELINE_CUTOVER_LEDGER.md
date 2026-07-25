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

---

## 7. Recorded, not fixed — the S1.SH1 keyframe spend-gate checkpoint (2026-07-17)

Preparing the Gate B disclosure for S1.SH1's opening keyframe (creative-room-2.0 → cb_handover
→ cb_engine) surfaced three real gaps. None fixed here — Julian's own instruction for this
checkpoint was record only, code/creative changes explicitly withheld.

1. **Essential provider protections are not reaching the Seedance brief.** `shot.prohibited`
   (where a CreativeShotCard's `essentialProviderProtections` land, via cb_handover's
   `distil_shot`) only ever feeds `cb_engine.hard_constraints()`, whose output is stored as
   `internalConstraints` in the package — deliberately never concatenated into
   `compile_shot_contract`'s own returned prompt (Option D's own documented design). The
   2026-07-17 consolidation's own `compile_shot_contract` docstring already names this
   plainly rather than silently assuming otherwise. A genuinely required protection
   (e.g. an explicit screen-side lock) does not currently reach the fired prompt through
   ANY path. Whether/how to open a second door for this is undecided — not addressed here.

2. **Dialogue ownership must be validated before a visual creative card can be approved.**
   S1.SH6's own approved `principalPerformance` field quotes its locked dialogue verbatim
   ("...she simply names what she knows: 'A Storm's coming.'") — a genuine Law 6 violation
   in already-APPROVED creative-card content, caught only when `cb_engine.compile_shot_contract`
   (unmodified) refused to compile it. This is a Gate-A-time gap: nothing checks a
   CreativeShotCard's own prose fields (principalPerformance, openingImage, closingImage,
   physicalOrEmotionalChange) for containing the beat's own locked dialogue text BEFORE that
   card is approved — the check currently only fires downstream, at compile time, after the
   human sign-off it should have preceded. Building this validation at source (Gate A, before
   card approval) is exactly what would prevent an S1.SH6-shaped defect from ever reaching an
   approved card again; it is the source-level fix, not a keyframe/prompt patch. NOT built
   this checkpoint.

3. **The creative-room-vNext production package has no bridge into the authorized fire
   route** (found while preparing the disclosure itself, not one of Julian's own named two,
   flagged here for completeness). `cb_gen.generate_image`'s `_require_production_route`
   hard-refuses any call whose `production_route != "cb_render"` — the ONLY authorized path
   is `cb_render.keyframe_shot()`, which reads its package from
   `cb-output/{episode}_scene{N}_production_package.json` in the shape
   `cb_engine.compile_scene_package()` builds (`continuityLedger`, `validation`, shot IDs
   like `1.B1.S1`). That package already exists for Scene 1 and already has a real,
   previously-fired keyframe (`media/shots/Ep1_1.B1.S1_keyframe.png`) — but it is a
   COMPLETELY SEPARATE artifact from the human-approved creative-room storyboard
   (`Ep1_scene1_storyboard.json`, shot IDs like `S1.SH1`) this whole session's work has built
   and tested. `cb_handover.promote_shot()` has never been run with `dry_run=False`; no
   `S1.SH1`-shaped production package exists anywhere on disk. Firing S1.SH1's keyframe for
   real — through the one authorized route — requires writing a `cb_render`-shaped package
   for these shots first. That is a packaging/wiring step, not a prompt or creative change;
   named here as the actual prerequisite to literal generation, distinct from items 1-2 above.

   **CLOSED 2026-07-17, same day, Julian's consolidation-checkpoint directive**:
   `cb_handover.promote_to_canonical()` (the sole promotion boundary) now writes exactly this
   bridge — real, on disk, at `cb-output/Ep1_scene1_production_package.json`, revision 7,
   sole shot `S1.SH1`. The OLD revision-6 package (`1.B1.S1`...`1.B5.S3`) is archived
   byte-identical at `cb-output/archive/Ep1_scene1_production_package_pre_S1.SH1_promotion_
   rev6_20260717.json` — never lost, and the stable fixture home for `test_e2e_fire_route.py`'s
   own revision-6-specific proofs going forward. `cb_render.load_pkg`/`_shot`/`_slot_paths`
   all confirmed, live, to resolve `S1.SH1` from the new package correctly.

   **A FOURTH FINDING, surfaced by actually building this bridge, not assumed away** (found
   2026-07-17, both root causes CLOSED the same day — Julian's structural-correction
   directive):
   `cb_engine.validate_scene_design` — called for real, unmodified, on the promoted S1.SH1 —
   returned `passed: False`. Two genuine, structural causes, neither fixable by inventing data
   or altering Julian's own approved creative-room text (both forbidden): (a)
   `CONTINUITY_CAST_INCOMPLETE` — `distil_shot`'s `continuityIn/Out.characters` list was
   always empty (item 1's own already-documented `typed-continuity` gap, confirmed to ALSO
   break cb_engine's own validator, not just the join-check it was originally named for); (b)
   `FIELD_OVERBUDGET` — S1.SH1's own approved `closingImage` (18 words) exceeded
   `cb_engine.Shot.visualPayoff`'s 15-word discipline, a budget the creative-room storyboard
   schema had no concept of at all.

   **(a) CLOSED** — `cb_creative.ProductionDetail` gained a new, typed `characterContinuity`
   field (character ID, opening state, closing state), authored during Gate 5/6 production
   detailing (`cb_creative.production_detail`, never inferred inside `cb_handover.py`).
   S1.SH1's own Production Detail was regenerated with it via
   `cb_creative.regenerate_production_detail(..., only_shot_id="S1.SH1")` — a scoped,
   single-shot regeneration; every sibling shot's own Production Detail carried forward
   completely untouched. S1.SH1's CreativeShotCard hash is confirmed byte-for-byte unchanged
   across the regeneration (`19c3379cd82e…`, before == after == the hash now stored in the
   live canonical package's `sourceStoryboard.creativeCardHashes.S1.SH1`).
   `cb_handover.distil_shot` now maps this typed field into `cb_engine.ContinuityState.
   characters` mechanically (a per-character state string duplicated across
   `pose`/`expression`/`screenZone`/`facing`, since the storyboard's own typed contract
   authors one descriptive state per direction, not cb_engine's fuller four-field shape —
   never invented, matching this file's own established duplicated-never-invented pattern);
   falls back to the original empty-list behaviour for any shot whose Production Detail has
   not yet been regenerated with it.

   **(b) CLOSED** — the arbitrary, isolated 15-word `visualPayoff` field budget is REMOVED
   from `cb_engine.FIELD_WORD_BUDGETS` outright (Julian: "do not rewrite or shorten the
   approved closing image... rely on the existing overall compiled-provider-brief budget").
   The field still runs the `ABSTRACT_DIRECTION` safety/renderability scan, unweakened; the
   real constraint that matters — the COMPILED provider brief's own word cap
   (`MAX_SHOT_PROMPT_WORDS`) and the `COMPILABILITY` check (an actual `compile_shot_contract`
   call) — is untouched and still enforced on every shot, unconditionally.

   **THE PROMOTION ITSELF WAS ALSO MADE TRANSACTIONAL** (a real, separate structural
   correction, found the same day the fourth finding above was first surfaced): the first
   attempt at closing (a) and (b) — before either fix landed — wrote `promote_to_canonical`'s
   candidate package to the live path UNCONDITIONALLY, regardless of `validation.passed`,
   producing exactly one invalid revision 7 live on disk (`validation.passed: false`,
   `CONTINUITY_CAST_INCOMPLETE` + `FIELD_OVERBUDGET`, both findings above in their raw,
   unfixed form). `promote_to_canonical` now builds and validates the ENTIRE candidate package
   fully in memory before touching the live path at all: a failing candidate writes nothing
   live, returns the failures, leaves the previous valid package completely untouched, and (on
   a real, non-dry-run attempt) preserves itself separately as rejected evidence at a
   distinctly-named archive path — never live, never silently discarded. That original invalid
   attempt is preserved exactly this way, at
   `cb-output/archive/Ep1_scene1_production_package_REJECTED_S1.SH1_rev7_attempt1_validation_
   failed_20260717.json`. `cb_handover.py`'s own import graph was corrected in the same pass —
   it no longer imports `cb_render` (or `cb_gen`) at all; the canonical package's filename
   convention now lives as a pure helper in `cb_engine.py`
   (`cb_engine.canonical_package_path`), which `cb_render._pkg_path` itself delegates to — the
   invariant test forbidding `cb_handover` from importing either rendering or provider code is
   restored, checking both names.

   **RE-PROMOTED FOR REAL, 2026-07-17**: with both root causes closed, S1.SH1 was promoted
   again as revision 7 (superseding the restored, valid revision 6 — the earlier invalid
   attempt was never live, so nothing needed reverting beyond restoring revision 6 as the
   interim state) — `validation.passed: true`, 0 errors, 0 warnings.
   `cb_render.keyframe_shot("1", "S1.SH1", "Ep1")` was run for real against this live package
   (writes redirected to a scratch copy; only `cb_gen.generate_image` stubbed) and passed its
   real, unstubbed `_require_valid` check, real billing gate, real opener/relay check, and real
   character-identity + scene-plate reference resolution — no legacy `1.B1.S1` material
   anywhere in the compiled prompt, no media written, no spend token issued. Storyboard md5 and
   S1.SH1's own CreativeShotCard hash are unchanged throughout. `test_e2e_fire_route.py` now
   carries this as its own explicit golden-path proof
   (`test_golden_path_s1sh1_keyframe_passes_real_require_valid_only_provider_stubbed`, against
   the real live package), separate from its three `test_legacy_*` regression pins against the
   original revision-6/`1.B1.S1` content — the golden path no longer borrows the legacy
   package as its own evidence.

---

## 8. THE SYSTEM FREEZE — Creative Room + keyframe compiler architecture locked (2026-07-17)

Julian's checkpoint verdict, same day as §7: the `openingImage`, reference-role and Gate
4→6 corrections are **accepted as software-wide changes**. This section is the record of
the last correction in that chain and the freeze that follows it.

**THE SIMPLIFICATION — typed absence, not a sentinel string.** §7's own fix for THE
DUPLICATION (continuityIn competing with openingImage for the opening composition) worked
by stamping a literal phrase, `NO_INHERITED_STATE = "N/A — scene opener; no predecessor
shot to inherit from."`, duplicated byte-for-byte across `cb_creative.py` and
`cb_engine.py`, with the compiler recognising that exact string. Julian's ruling: replace
it with typed absence in the schema that already exists — no new field, state, helper
layer or protocol.

- `cb_creative.ProductionDetail.continuityIn` is an unconstrained `str` (no
  `Field(min_length=1)`) — the schema's own pre-existing "nothing here" value is the empty
  string, already used as the fallback default elsewhere in `production_detail()`. The
  mechanical clear for the scene's true first shot now writes `""`, not a sentinel phrase.
- `cb_engine.Shot.continuityIn` is now `Optional[ContinuityState] = None`. `design_scene`
  mechanically clears position 0 to `None` after every LLM call (mirroring
  `cb_creative.production_detail`'s identical pattern); `validate_scene_design` gained two
  checks — `OPENER_CONTINUITY_IN_NOT_CLEARED` (a real continuityIn survived on the scene's
  first shot) and `CONTINUITY_IN_MISSING` (a later shot has nothing inherited, which is
  never legitimate) — so a stale, hand-edited or reloaded package can't silently violate
  the invariant.
- `cb_handover._continuity_state` is the one bridge between the two shapes: an empty
  `continuityIn` prose maps to `None`, scoped to the opening side only —
  `continuityOut` keeps its exact pre-existing behaviour, since "nothing inherited" is
  never a legitimate state for how a shot ends.
- `compile_keyframe_prompt` omits the "Continuity in:" paragraph on a plain `is None`
  check now, not a string comparison.

Every downstream reader of `continuityIn` (`_render_critical`, `_repair_context`, the
relay mark/prop-drift join check) was swept and guarded against the new `None` case —
graceful degradation, never a crash on an already-flagged malformed state. 137 tests green
(1 pre-existing skip), including new coverage for both new validator checks and the
mechanical clear itself.

**A known, deliberately un-touched consequence**: the LIVE canonical package
(`cb-output/Ep1_scene1_production_package.json`, revision 7) still carries real prose in
`shots[0].continuityIn` — written by an earlier stage of the same day's work, before this
simplification existed. It was NOT hand-edited to match the new convention; the live,
approved package stays untouched per Julian's own standing instruction, and this stale
shape will be corrected as a side effect of the NEXT real promotion (§9 below), not by a
patch applied directly to approved production data. Until then, a real fire attempt
against revision 7 would correctly refuse at `_fresh_validation` on
`OPENER_CONTINUITY_IN_NOT_CLEARED` — a safe, fail-closed state, not a silent risk.

**THE FREEZE.** As of this checkpoint, the Creative Room (`cb_creative.py` — Gate 4 shot
conference, Gate 5 performance/voice, Gate 6 adversarial review, `production_detail`,
`CreativeShotCard`/`ProductionDetail`) and the keyframe/motion-brief compiler
(`cb_engine.py` — `compile_keyframe_prompt`, `compile_shot_contract`, the reference-
ownership doctrine, `validate_scene_design`) are **locked**. No further creative or
compiler changes to either module without a fresh, dated ruling — matching this
document's own established practice (§7's own dated corrections, CLAUDE.md rule 18's
forward-only doctrine) rather than open-ended iteration. The next work against this
system is either (a) a real approval/rejection decision on a storyboard candidate already
built under this architecture, or (b) a genuinely new defect found on real rendered
footage — not a speculative refinement.

---

## 9. Gate A candidate export (2026-07-17)

The real Gate 4 → Gate 5 → Gate 6 loop run under the corrected, now-frozen source
contract (§7/§8) converged on a 7-shot sequence for Scene 1 (6 `PLANNED_CUT`, 1
`CONTINUOUS`), using the unchanged selected treatment and unchanged 5-beat architecture
throughout — Gate 6 rejected an earlier 15-shot draft as over-fragmented coverage, then
passed the 7-shot revision on genuine, specific grounds. This candidate is exported and
held for Julian's own review — see the Studio's storyboard-candidate view for the visual,
human-readable presentation. It is explicitly **not** merged into the live approved
storyboard or production package; that only happens on his explicit approval, at which
point the existing `cb_handover.promote_to_canonical` path both promotes it AND — as a
side effect of the fix in §8 — correctly clears `continuityIn` to typed `None`/`""` for
the scene's true opener for the first time under the live data, closing the one known
stale-shape gap noted above.

---

## 10. §7 item 2 CLOSED at source — and one new blocker found attempting the real promotion (2026-07-17)

**§7 item 2 CLOSED.** Verified directly, not assumed: `principalPerformance` (Gate 4's own
human-facing read) quotes the beat's own locked dialogue verbatim on 6 of the real Scene 1's
7 shots — S1.SH1 ("BIZZY-BIZZY-BIZZY…", "Nailed it."), S1.SH2 ("Do I look official?", "Yes
Fuzzby Officially nuts!"), S1.SH3 ("Buzz Crash!!"), S1.SH5 ("…okay that sounded dramatic."),
S1.SH6 ("A Storm's coming."), S1.SH7 ("Good thing I work well under pressure.") — the exact
`principalPerformance`/`compile_shot_contract` combination §7 item 2 already named for
S1.SH6 alone, confirmed here to be systemic, not a one-shot fluke. `physicalPerformance`
(Gate 5's separate, body-first field, authored under an explicit "physical cause and effect
stays readable" instruction that never asks for or permits spoken words) was checked against
the identical 7 shots and carries ZERO dialogue on any of them — `animationTiming` was also
checked and found NOT safe (it references locked dialogue on 2 of 7 shots, since timing prose
legitimately describes when a line lands, e.g. "then let 'Nailed it' arrive too bright and
too soon"). `cb_handover.distil_shot` now sources `performanceAssignment` — the one field
`cb_engine.compile_shot_contract` folds into the provider's visual-performance brief — from
`physicalPerformance`, never `principalPerformance`; a shot with no Gate-5 physical-
performance pass yet refuses loudly (`HandoverRefused`) rather than silently falling back to
the dialogue-risky field. `principalPerformance` itself is retained verbatim in the promoted
record (`principalPerformanceApproved`) — never dropped, only no longer the compiled source.
A new general test, `test_performance_assignment_sources_physical_performance_never_
principal_performance` (`test_cb_handover.py`), proves this across four distinct synthetic
shots, each with its OWN locked line, including a direct regression pin confirming the OLD
mapping would fail every one of them with a real `LAW 6 VIOLATION` from the unmodified
`cb_engine.compile_shot_contract` — never patched to S1.SH1 alone, per instruction.

**A NEW, DISTINCT BLOCKER, found attempting the real S1.SH1 promotion under this fix** (dry
run, live storyboard, unmodified `cb_engine.py`): `cb_engine.validate_scene_design`'s
`FIELD_OVERBUDGET` check — `performanceAssignment` capped at 50 words in
`FIELD_WORD_BUDGETS` — now fires as a hard `ERROR` on S1.SH1 (76 words) and, checked, would
fire identically on all 6 other dialogue-bearing shots (72-92 words each; `physicalPerformance`
was never authored under a 50-word instruction — Gate 5's own prompt asks for "chest leading,
wings overworking..." body detail, ~60-90 words per real shot, per §7 item 2's own
already-recorded observation). The compiled provider brief itself is unaffected and fits
comfortably — `compile_shot_contract`'s own real ceiling, `MAX_SHOT_PROMPT_WORDS=210`, is
satisfied at 161-191 words across all 7 shots, and `_assert_no_spoken_words` raises nothing.

This is the SAME class of problem §7 item 4(b) already found and closed for `visualPayoff`
(an isolated per-field budget rejecting real, approved content for a reason unrelated to the
actual constraint that matters) — but it is **NOT resolved the same way here**, and
deliberately so: `cb_engine.py`'s own `FIELD_WORD_BUDGETS` comment, written the same day as
that closure, states explicitly that `performanceAssignment` "keeps its own budget (not
named in this correction)" — meaning this exact field was already considered for the same
relief and Julian chose to keep its cap in place. Removing it now, even under a directly
analogous rationale, would silently reverse an already-made, already-recorded decision — not
extend a pattern. NOT done. `cb_engine.validate_scene_design`/`FIELD_WORD_BUDGETS` are
UNTOUCHED. The promotion attempt (`dry_run=True`) confirms the live package
(`Ep1_scene1_production_package.json`, revision 7) is untouched and nothing was written —
`promote_to_canonical`'s own transactional guarantee (§7 item 4) held throughout. `S1.SH1`
remains unpromoted under revision 7's existing content; no keyframe generation was attempted,
consistent with steps 6-7 of Julian's own directive never being reachable while promotion
itself refuses. Flagged here for his own decision: raise/remove `performanceAssignment`'s
`FIELD_WORD_BUDGETS` entry to match `visualPayoff`'s own precedent, or hold the line and
require Gate 5's `physicalPerformance` authoring to stay within 50 words going forward (a
real creative-authoring constraint change, not a code one) — both are his call, neither
decided here.

---

## 11. The dog-and-fox misfire, the Scene Look hard-gate, and the unwired lineage checkpoint (2026-07-19)

**THE MISFIRE.** A real, billed ($0.144) Scene Look Plate generation for Scene 1 produced an
unrelated image (a dog and fox in a flower field). Traced via the `.gen.json` sidecar, the
cost ledger, and `_compile_scenelook_prompt`'s own code: the specialist Look Development
candidate was correctly never used (it was still unapproved) — but the FALLBACK canon
compiler found `shows/crystal-bears/canon/locations.json` completely empty (`{"_note": ""}`),
so the entire submitted prompt was just the one-line global style law, paired with one
unlabelled reference photo — a known failure mode for an image-edit model given no real
content to anchor on.

**THE BYPASS FIX (Julian's own itemized instruction, implemented and verified live in the
Studio before this section was written).** `cb_render.approved_look_prompt(scene, episode)`
is now the SOLE permitted source for `generate_scenelook_plate`'s submitted prompt — it reads
`departmentWork.look.approved.output.providerPrompt` and returns `None` if no candidate has
been explicitly approved (a pending/unapproved candidate never counts). `generate_scenelook_
plate` hard-refuses before the billing check if this is `None`: `"REFUSED — Approve Look
Development direction first."` The Studio's own disclosure modal (`app.html`'s `openDisclosure
Modal`, `kind=="scenelook"` branch) mirrors this client-side, showing the exact approved
specialist prompt text that will be submitted, or the refusal message with no Generate button
at all if nothing is approved yet. Confirmed live: Scene 1 (no approved Look direction) shows
the refusal; the failed dog-and-fox generation was preserved in Scene 1's own rejection
history, left for Julian's own review, never silently discarded.

**`locations.json` populated the same night**, closing the fallback's root cause too (belt and
braces — the real live path is now the approved-specialist-prompt-only gate above, but the
canon fallback existed and was empty, and nothing else in the codebase should ever again find
it that way). Populated for all 10 scenes from already-authored material only — Scene 1's own
approved specialist candidate text, archived storyboards for Scenes 2/3/9
(`archive/Episode_1_Complete_Archive_20260718/output/creative/Ep1_scene{2,3,9}_storyboard.
json`), and for Scenes 4-8/10 (which have never had a real storyboard built under this
architecture) the current script plus `EP1_GATE1_STORYBOARD.md`'s 2026-07-05 export plus
`CRYSTAL_BEARS_LOCKED_CANON.md`'s own locked light-arc-by-scene table. Two real naming
inconsistencies found and flagged in the file's own `_provenance.namingFlags`, not silently
resolved: Scene 3 is "KEEN'S ISLAND" in the script but "Crystal Cove pier" in both storyboard
sources; Scene 9 is "GATHERING AREA" in the script but canon's own location list separately
names it "The Learning Circle."

**THE UNWIRED STATE-INTEGRITY CHECKPOINT — the most significant finding of the night.**
Investigating a stale test (`test_golden_path_keyframe_refuses_on_the_actual_current_lineage_
mismatch`, which had flipped from pass to fail purely because the real production package had
since been re-synced) led to tracing `cb_render._require_current_lineage` — the function this
whole test suite extensively documents as "THE STATE-INTEGRITY CHECKPOINT," a hard refusal for
any package built from a superseded storyboard version — and finding it had **zero call sites
anywhere in `cb_render.py`**. Neither `keyframe_shot` nor `fire_shot`, the two real content-
generation entry points, ever called it. A package whose storyboard had moved on could
therefore still generate a real keyframe or fire a real paid animation batch against outdated
content — the exact condition the checkpoint's own doctrine was written to prevent, and the
same class of failure that let a rejected S1.SH1 keyframe once read as "approved" (§7). Wired
`_require_current_lineage(pkg, scene, episode)` into both functions, immediately after
`_require_valid(pkg)` (the existing "cheapest, stored gate first" ordering). Verified: the full
test suite (147 tests across 13 files, previously 133 passed/11 failed/3 errored before
tonight) now runs 147 passed, 1 skipped, 0 failed with this wired in — including every
already-passing suite, confirming no regression from the new gate.

**Two genuinely dead helpers found in the same sweep and removed** (a project-wide grep for
zero-reference functions, the same technique that surfaced the lineage gap — narrowed down
from ~130 naive single-file false positives to 2 real ones by checking every `.py` file, not
just the defining one): `cb_render._spend_disclosure` (superseded by a richer inline
disclosure dict in `fire_shot` built the same night §7's spend-control gate was designed —
never deleted after) and `cb_engine._continuity_summary` (a per-character continuity-state
summarizer with no caller anywhere; `compile_keyframe_prompt` deliberately builds a narrower
lighting/camera-side-only clause instead, per its own extensive docstring, and was never meant
to use this). Removed both; full suite re-run clean after each removal.

**Eight stale test assertions/fixtures fixed, all verified against real, current state, none
guessed at:**
- `test_cb_gen.py`'s two billing-confirmation assertions expected `planConfirmed`/
  `cadenceConfirmed` as `False` — Julian confirmed his real ElevenLabs plan (Pro, monthly) on
  2026-07-18 (`billing_profile.json`'s own `confirmedBy`/`confirmedAt` fields); both flipped to
  `True`, matching the real, live profile.
- `test_e2e_fire_route.py`'s `legacy_scratch_pkg` fixture pointed at an archived package
  (`cb-output/archive/Ep1_scene1_production_package_pre_S1.SH1_promotion_rev6_20260717.json`)
  that no longer existed at its documented canonical path — not lost, swept into a broader
  whole-episode cold-storage archive (`archive/Episode_1_Complete_Archive_20260718/output/
  archive/...`) during an earlier, unrelated project-wide reset. Restored the byte-identical
  (MD5-confirmed) copy to its documented location rather than fabricating a replacement.
- The same fixture's own recorded keyframe/voice media paths (`engine/media/shots/
  Ep1_1.B1.S1_{keyframe.png,vo.mp3}`) had also been swept away by the same reset. The
  keyframe's exact byte content (matching the sealed-brief test's own hardcoded md5,
  `c02dc92c...`) was recovered from the same cold-storage archive and restored into the
  fixture's own scratch media dir — never the real `engine/media/` tree — with `keyframePath`/
  `voPath` repointed there, so this fixture can never again depend on a specific real-world
  path surviving untouched between sessions.
- Both `legacy_scratch_pkg` and `golden_path_scratch_pkg` needed the identical treatment for
  two NEW real production gates that postdate when these fixtures were last written: the
  voice-approval gate (`fire_shot` now refuses a dialogue shot whose voice track exists but
  isn't explicitly approved) and the Scene Look Plate gate (`_plate_path`/
  `_require_current_scenelook`, both reading REAL, LIVE scene-1 state these fixtures never
  redirect). Backfilled voice/keyframe approvals the same way the fixture already did for
  keyframes; bypassed the live-state-dependent Scene Look checks with the same documented
  "out of scope for a mechanics-only regression pin" reasoning already established for the
  lineage check.
- `test_golden_path_script_to_scene_picture`'s keyframe-anchor assertion asserted a literal
  `.endswith("_keyframe.png")` — stale against `approve_keyframe`'s own real, deliberate
  behaviour (it keeps the candidate's own unique-hash filename, never renaming it, matching
  this codebase's "never rename an approved artefact" convention throughout). Corrected to
  check the real invariant: the fired anchor equals the ledger's own recorded `keyframeApproval
  .path`.
- `test_golden_path_keyframe_refuses_on_the_actual_current_lineage_mismatch` used to assert its
  refusal by relying on the real production package genuinely being stale AT THE MOMENT IT WAS
  WRITTEN — meaning the test would flip to failing the instant the very staleness it was
  pinning against got fixed by a later re-promotion (exactly what happened). Rewritten to
  deliberately simulate the mismatch via `monkeypatch.setattr(cb_render, "_current_storyboard_
  md5", ...)`, the same technique its own sibling test already used to simulate the matching
  case — a permanent regression pin, not a bet on real-world drift staying put.
- `cb_render._resolve_keyframe_prompt` crashed with a raw `KeyError` on any relay/non-opener
  shot (`shot["keyframePrompt"]` — only opener shots ever carry this key) — a real, pre-
  existing crash in `evidence_pack`, which calls this for every shot in a scene, not just
  openers. Fixed to `shot.get("keyframePrompt")`, degrading to `None` for a relay shot the same
  honest way a silent shot's missing voice track already does elsewhere in this file.

**Verified untouched**: the real, live Scene 1 Look Development state (`cb-output/
Ep1_scenelook_scene1.json`) — still `approved: None`, the specialist candidate still present,
still `editedBy: Julian`, exactly as he left it; the real production package
(`cb-output/Ep1_scene1_production_package.json`) mtime unchanged; the live Studio server
(port 8765) confirmed still healthy (`{"stale": false, ...}`) and `cb_render.py` still imports
clean after every change. No generation call was fired by any of this work.

**Left for Julian's own call, not decided unilaterally**: whether the Cinematography/Voice/
Animation departments should get the same "must be explicitly approved before firing" hard
gate the Look department now has (an earlier same-session audit confirmed their existing
fallbacks are already real, shot-specific, already-Director-approved content — not the thin/
generic kind that caused tonight's misfire — so this is a genuine design-strictness choice, not
a bug); the Scene 3/Scene 9 naming inconsistencies named above.

---

## THE FOUR-LEVEL MODEL — beat / camera shot / generation clip / editorial output
(Julian's directive, 2026-07-25: "verify whether the canonical model clearly separates a
dramatic beat, a cinematic camera shot, a Seedance generation clip and an editorial output.")

**What was found.** Three of the four levels were already genuinely separate:

| Level | Object | Where it lives |
|---|---|---|
| 1 — dramatic beat | `cb_creative.Beat` (`beatId`), `Shot.beatCode` | Gate 3 |
| 2 — cinematic camera shot | `CreativeShotCard` / `cb_engine.Shot` (`shotId`) | Gate 4 |
| 3 — Seedance generation clip | *was not its own concept* | `cb_render.fire_shot` |
| 4 — editorial output | `cb_post` picture / conformed / masters | Gate 5 |

**The conflict, precisely.** Levels 2 and 3 were conflated. `fire_shot(scene, shot_id)`
renders exactly one `Shot`, and the render ledger, batch state, candidates, rejection
history and cost all key on `shotId` — so one Shot Card *was* one generation clip, always,
with no clip identity of its own. When a generation genuinely needed several ordered camera
shots inside it, the only available expression was `internalCuts: List[str]` — free prose.
Those extra camera shots were therefore **redefined inside the clip**, not referenced: no
`shotId`, no `openingPose`, no `endingBehaviour`, no continuity, no approval of their own,
and the compiler emitted them as bare numbered lines. The production workaround (SH2 →
SH2A/SH2B) went the other way — two Shots, two generations, an editorial join — which is
valid but forces a real cut where a continuous generation may be wanted.

**The smallest compatible separation.** One optional field, not a parallel schema tree:
`composedOf: List[str]` on `CreativeShotCard` and `cb_engine.Shot` — the ordered shotIds of
other Shot Cards that this one generation renders. `cb_engine.resolve_clip_members(shot,
siblings)` is the single place the distinction is read; the compiler emits one segment per
member built from **that member card's own authored fields**, never retyped prose.

Guarantees, each pinned by a permanent test:
- **Empty is the default and changes nothing.** All 5 real Scene-1 shots compile
  byte-identically with and without the new path (verified against the live package,
  md5 `108782ab…`, unchanged).
- **Mutually exclusive with `internalCuts`** — two authorities for the same segments is
  exactly what this field exists to end (`CLIP_MEMBER_CONFLICT`).
- **Unresolvable members raise, never silently drop** — self-reference, nesting, a missing
  ref, duplicate membership and a member claimed by two clips are all validator errors.
- **A member card is not independently fireable** — `_require_own_clip` refuses at both
  paid entry points (`keyframe_shot`, `fire_shot`), naming the clip to fire instead;
  firing a member alone would render and bill the same camera shot twice.
