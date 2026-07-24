# Seedance Shot-Mode Architecture — Option B Plan

Status: Phases 1–2 APPROVED and in build (Julian, 2026-07-23, via the Anti-Guardrail
Principle directive, point 9). No media generation, no spend, until separately approved.

## THE ANTI-GUARDRAIL PRINCIPLE (Julian, 2026-07-23 — GOVERNS EVERYTHING BELOW)

This architecture is not a compliance system. Its purpose is engineering better Seedance
prompts through controlled creative experimentation, producing approvable outcomes
consistently. The rules, verbatim in intent:

1. Never convert one failed generation automatically into a universal rule or negative.
2. Diagnose failures in this order: positive staging/performance direction → timing and
   shot density → audio performance → reference assignment → only then a narrow negative
   control if genuinely necessary.
3. Rewrite or remove competing prompt language BEFORE adding more. Prompts must not
   accumulate corrections indefinitely.
4. Mode-specific direction is a selectable creative vocabulary, not compulsory boilerplate.
5. Conditional controls are scoped to the relevant shot/failure/experiment, carry their
   evidence, and are retirable when they stop improving results.
6. The Director can always inspect and edit the complete compiled prompt before
   generation (the existing working-prompt mechanism is preserved for exactly this).
7. MODEL-LIMITED is not terminal — it means the present prompt/staging approach reached
   its limit and needs another engineered hypothesis.
8. Tests must demonstrate prompts become LEANER, CLEARER and MATERIALLY DIFFERENT —
   not merely that schemas and validators pass.
9. After Phases 1 and 2, return directly to practical prompt engineering for SH2A and
   SH2B. No additional planning or approval layer.
10. Success is an approvable cinematic result within a predictable number of attempts —
    not the number of rules the system can enforce.

Consequential amendments to the sections below: the shot-density rule surfaces a
DIRECTOR DECISION (hybrid vs split), it does not grow a new blocking layer; failure
controls store their evidence and can be retired; phase-2 tests assert leaner and
materially different compiled output, not just green validators.

Evidence base: four real S1.SH2 takes (~$18.20), each landing some beats and dropping
others; Julian's structured verdict on the Option A take (recorded verbatim in the shot
ledger and `media/archive/shots_rejected/Ep1_S1.SH2_20260723T070127/JULIAN_VERDICT.json`);
the measured voice track (Fuzzby's audible line ≈7.31–8.28s in the clip, under one second
— the rush is baked into @Audio1, which lip-sync must follow).

---

## 1. Current pipeline map (exact files and functions)

```
Script beat (Creative Room storyboard)
  cb_creative.py       gate0_readiness → gate1_treatments → gate2_select → gate3_beats
                       → gate4_shot_conference (Creative Shot Cards: purpose,
                         audienceExperience, openingImage, principalPerformance,
                         cameraRelationship, transitionType/Reason, cutPace, internalCuts)
                       → gate5_performance (physicalPerformance, animationTiming,
                         gagStaysVisible/ContactAndWeight/PayoffShape/Prohibited)
                       → gate5_voice (per-line delivery direction)
                       → gate6_adversarial_review → gate6b_producer_feasibility
                       → production_detail (durationRange, requiresNewKeyframe,
                         continuityIn/Out, characterContinuity,
                         essentialProviderProtections)
        │  approved storyboard JSON (Ep1_scene1_storyboard.json)
        ▼
Handover (mechanical, zero-LLM)
  cb_handover.py       promote_to_canonical → _scoped_shot → distil_shot
                       (storyboard fields → typed cb_engine.Shot, verbatim;
                        _strip_quoted_dialogue rescues animationTiming→tempoDesign,
                        audienceExperience→feltIntent — added 2026-07-23)
        │  canonical production package (Ep1_scene1_production_package.json)
        ▼
Compilation (mechanical, zero-LLM)
  cb_engine.py         compile_shot_contract  → the Seedance brief
                       compile_keyframe_prompt → the keyframe brief
                       hard_constraints / _render_critical / _reference_role_sentence
        │  compiled brief text
        ▼
Delivery specialists (one LLM call each; translate-and-tighten, never re-decide)
  cb_departments.py    prepare_cinematography (opener keyframes only)
                       prepare_voice   → ElevenLabs V3 performance script
                       prepare_animation → final providerPrompt
                         (TEMPO MAP LAW in its system prompt, added 2026-07-23)
        ▼
Gates + fire
  cb_render.py         prepare_department / decide_department (human approval per stage)
                       _check_no_dialogue_leak, _check_tempo_map (save-time refusals)
                       approve_voice (audio gate), keyframe approval, freshness/lineage,
                       check_seedance_structure, fire_shot (disclose-token-fire),
                       reject_shot / redesign_eligibility / acknowledge_redesign
```

## 2. Where the universal one-size-fits-all behaviour enters

- `cb_engine.compile_shot_contract` — ONE assembly shape for every shot: style line →
  opening/transition → internalCuts as "Shot N:" list → contactAndWeight → payoff →
  lip-sync sentence → `hard_constraints` (universal five + capped conditionals) →
  quality line. No branch on what KIND of performance the shot is (beyond opener/relay
  and cutPace).
- `cb_departments.prepare_animation` — ONE system prompt for every shot (now including
  the universal Tempo Map law).
- `cb_creative.gate4/gate5` — authoring prompts have no concept of performance mode; a
  chase and a deadpan exchange are authored with identical instructions.

## 3. Retained unchanged

Everything else: the gate/approval/spend-token machinery, freshness + lineage guards,
Law 6 enforcement, `_check_tempo_map`, the relay/opening-frame source system
(`select_keyframe_source` incl. `previousFinalFrame`), rejection/redesign ladder,
evidence sidecars, the universal five negatives (each observed-failure-derived),
`approve_voice`, and the entire Creative Room gate sequence.

## 4. Minimal-change mode architecture

Modes are a DIRECTOR DECISION made at storyboard time, stored as data, mechanically
compiled — never an LLM classifying at delivery time. Because real shots are hybrid
(the four-take evidence), a shot declares a primary mode plus at most one secondary;
more than two triggers the shot-density rule below.

Mode vocabulary (v1): `KINETIC_ACTION`, `PHYSICAL_COMEDY`, `DIALOGUE_PERFORMANCE`,
`COMEDY_REACTION`, `EMOTIONAL_ACTING`, `WORLD_ESTABLISHING`.
(`CONTINUITY_TRANSITION` is deliberately NOT a mode — that axis already exists as
`sourceType: opener/relay` + `transitionType`, and every shot has it.)

### THE SHOT-DENSITY RULE (Julian's addition, 2026-07-23 — new law)
> When one generation contains more than two substantially different performance
> modes, the Director must explicitly approve either (a) a HYBRID TAKE — proceed
> anyway, on record — or (b) SPLIT-GENERATION STAGING — divide into connected
> relay-chained generations, each ≤2 modes.
Enforced at two points: `gate6b_producer_feasibility` (authoring-time BLOCK finding)
and `cb_handover` promotion (refuses >2 modes without a recorded Director decision).

## 5. Revised schemas (proposed — no code written)

```python
# cb_creative Creative Shot Card + cb_engine.Shot both gain:
performanceModes: List[Literal["KINETIC_ACTION","PHYSICAL_COMEDY",
    "DIALOGUE_PERFORMANCE","COMEDY_REACTION","EMOTIONAL_ACTING",
    "WORLD_ESTABLISHING"]]          # 1-2 entries; order = primary, secondary
modeDensityDecision: Optional[Literal["hybrid_approved","split_staged"]]
    # REQUIRED iff >2 modes were identified at authoring; recorded Director call

# audience purpose — already exists as `purpose` + `audienceExperience`(→feltIntent);
# no new field. The mode system consumes feltIntent as the intention line.

# performance plan — already exists as tempoDesign + internalCuts + physicalStaging;
# mode-specific compilation changes WHICH of these lead the brief (see §6).

# reference assignments — already exist (referenceSlots, one explicit job each);
# unchanged.

# failure-specific controls (replaces most conditional negatives):
class FailureControl(BaseModel):
    control: str                    # the restriction text
    observedFailure: str            # the real generation failure it answers
    scope: Literal["identity","continuity","safety","observed-failure"]
# Universal five stay unconditional (each already observed-failure-derived).
# Mode-conditional extras ship only when their mode is active.
```

### Mode-specific compilation (inside compile_shot_contract — a branch, not a rewrite)
- KINETIC_ACTION / PHYSICAL_COMEDY: physics chain leads (cause → compression →
  rebound → transfer); contactAndWeight and payoffShape are the spine; camera energy
  language allowed; dialogue de-emphasised.
- DIALOGUE_PERFORMANCE / EMOTIONAL_ACTING: speaker ownership + listening behaviour
  lead; near-still camera default; tempo map anchored to the audio's real line
  windows; micro-expression language allowed; big-motion language suppressed.
- COMEDY_REACTION: setup → reveal → reaction ordering enforced; the reveal gets a
  held beat; the reaction beat is never shared with another beat.
- WORLD_ESTABLISHING: scale/depth/atmosphere lead; character direction minimal.

## 6. THE AUDIO-FIRST GATE (Julian's law, 2026-07-23)

@Audio1 is the absolute master track. For any DIALOGUE_PERFORMANCE shot, the voice
take must be Julian-ear-approved — pacing, pauses, performance — BEFORE any video
generation is authorised. Mechanism already exists (`approve_voice`; animation prepare
+ fire both require `voiceApproval.approved`); what changes: the voice DIRECTION is
authored with explicit timing (target line windows, written pauses e.g.
"Yes, Fuzzby. [tiny pause] Officially nuts!") and the measured track is checked
against those windows before it is even presented for approval.

## 7. S1.SH2 redesign — two connected generations (per Julian's spec, verbatim intent)

**SH2A — KINETIC_ACTION + PHYSICAL_COMEDY** (picture and effects only; no dialogue)
- Fast flight and showy spin (proven great — kept).
- Fuzzby remains visible outside the flower; ONLY his face plants into its
  pollen-heavy yellow centre.
- Flower visibly compresses, bends and rebounds; golden pollen bursts and transfers.
- He pulls out wearing a loose GOLDEN-POLLEN handlebar moustache + tiny goatee —
  never black hair, a costume, or an accessory.
- Hold the reveal clearly. Final frame = the moustache-reveal quality gate: if the
  moustache reads wrong, SH2A is rejected cheaply and SH2B never fires.

**SH2B — DIALOGUE_PERFORMANCE + EMOTIONAL_ACTING** (relay from SH2A's approved frame)
- Begins on the approved moustache-reveal frame (moustache arrives as real pixels).
- Fuzzby drops his arms sincerely, asks UNHURRIED: "Do I look official?"
- Zenny listens mouth closed; answers calm, dry, warm:
  "Yes, Fuzzby. [tiny pause] Officially nuts!" — almost motionless, NO smile during
  the verdict.
- Only after completing the line: turns half away; the first tiny private cheek-lift
  escapes; SHOT ENDS on that instant — never developed into a grin.
- New voice takes first, through the audio-first gate.

## 8. Phased implementation (each phase testable, no spend until Julian fires)

1. **Schema + storyboard**: add performanceModes/modeDensityDecision to the Creative
   Shot Card, cb_engine.Shot, and handover mapping. Split S1.SH2 → SH2A/SH2B in the
   storyboard per §7. Tests: schema round-trip; promotion carries modes; density rule
   refuses 3 modes without a decision. (Zero LLM, zero spend.)
2. **Mode-aware compilation**: the branch in compile_shot_contract + mode-scoped
   conditionals; prepare_animation told the active modes. Tests: golden-style compile
   of SH2A vs SH2B proving materially different briefs; tempo-map law still enforced;
   Law 6 unchanged.
3. **Audio-first gate**: authored line windows in voice direction; measured-vs-target
   check surfaced at approval. Test: a track violating its windows is flagged before
   presentation. New Fuzzby/Zenny takes generated (small ElevenLabs cost) and STOPPED
   for Julian's ear.
4. **SH2A fire** (one candidate, on approval) → reveal-frame gate → **SH2B fire**
   (one candidate, on approval). Standard disclose-token-fire discipline throughout.

## 9. Conflicts found between the proposal and current code (named, not hidden)

- `durationSec` floor: MIN_SHOT_SEC/handle duration may force both halves to 15s;
  SH2A/SH2B durations need a deliberate decision (15s each is safe; shorter needs a
  parameter check against the provider).
- The dialogue lines currently live on ONE shot; splitting moves both lines to SH2B —
  the scene-level verbatim-dialogue validator must see the lines once across the
  scene (already alignment-based, expected to pass; verified in phase 1 tests).
- SH2A carries "no dialogue" — Law 5 requires no native voice; SH2A must fire with
  no @Audio1 and an explicit no-voices constraint (existing machinery supports
  audio-less shots; verified in phase 2 tests).
- The tempo-map save-time check applies to ALL animation candidates; SH2A (pure
  kinetic) still benefits and passes; no conflict.
- S1.SH2's model-limited state: the split creates NEW shot IDs (SH2A/SH2B) via a real
  storyboard redesign — the honest path out of model-limited (rung 4), not a reset.
