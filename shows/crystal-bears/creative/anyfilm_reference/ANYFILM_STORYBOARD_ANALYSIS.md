# The AnyFilm Ep1 Storyboard — Full Capture + Analysis + What We Adopt

**Captured 2026-07-24** from Julian's own AnyFilm project (app.anyfilm.ai, project "Ep 1"), all
126 shot cards across 10 scenes, extracted live from the storyboard page into
`anyfilm_ep1_storyboard_126shots_20260724.json` (this folder). Julian's ruling: *"we take it
all for us but putting in our learning."* This document is the analysis and the adoption spec.

## The shot ledger

| # | Scene | Shots | Structural read |
|---|-------|-------|-----------------|
| 1 | Deep Within the Rainforest | 16 | 4 movements: world+relationship (1-2), comedy ladder w/ reaction coverage (3-8), the turn in six shots (9-14), overlap+storm reveal (15-16) |
| 2 | Crystal Cove — Aida's Sanctuary | 8 | Ritual → pendant glow → VISION (dream-grade shift, 2 shots) → return → rise → walk-out. The vision is its own visual grammar (soft focus, rose-pink vignette) |
| 3 | Keen's Island — The Pier | 18 | The emotional centerpiece gets the most coverage. Full shot/reverse-shot scene: Mum coverage + Keen coverage alternating, 100mm MACRO inserts on the wristbands (grain, scratches, history), telephoto-compression separation shot as the boat departs, Squeaky's entrance as the tonal relief valve |
| 4 | At Sea | 10 | Joy (1-5, incl. the upside-down map gag) → weather snap (6) → storm build (7-8) → Squeaky in trouble (9) → decision (10) |
| 5 | Rainforest Edge | 8 | The relay: Fuzzby freeze-frame alarm, rack-focus POV to the distant boat, two-word Zenny gravity beat, the SNAP to determination, the blast-off. Note: Fuzzby's freeze is the comedy engine INVERTED for drama — same body, opposite tempo |
| 6 | Crystal Cove — Storm Building | 16 | Fuzzby's crash-arrival gag under dread, then the CRYSTAL CALL as a 7-shot ceremonial sequence (10-16): activation → per-bear montage → unison → the light-beam burst → the beam crossing the sea |
| 7 | Out at Sea — Storm | 20 | The climax gets the most shots. INTERCUT grammar (shore/sea/underwater labeled on the cards), underwater palette shift (muffled blue-grey), 100mm macro on paws/net/wristbands, the courage line spoken in bubbles, net-SNAP release, surface EXPLOSION, the wave-riding hero arrival |
| 8 | Crystal Cove Beach | 12 | Arrival, welcome, Fuzzby-into-Keen's-face comedy, group warmth |
| 9 | Gathering Area | 10 | Ceremony: "You followed your heart… and chose courage" (verbatim), the aquamarine crystal SPLITS into two gems → travels to the wristbands, group hug swamp |
| 10 | Crystal Cove Beach — Continuous | 8 | Comedy epilogue: honey question, Fuzzby ecstasy, machine-gun honey list, the golden pull-back ending |

## The twelve transferable techniques

1. **Expand, don't compress.** One implied script line becomes real screen time (Scene 1's
   storm turn: six shots; Scene 3's wristband handover: four shots incl. two macros). Our
   Director's instinct was compression. Expansion is what makes it feel like television.
2. **One job per shot.** Every card is a single camera setup with one dramatic job.
   Decomposition (storyboard) and generation packing (2-3 shots per 15s clip, "Cut to.")
   are SEPARATE decisions.
3. **Reaction coverage is half the comedy.** Every Fuzzby gag has a dedicated Zenny
   reaction card. Action shot / reaction shot / cut.
4. **Editorial rhyming.** "Same framing as shot N" — repeat a setup, change the emotion
   (S1: 13 rhymes 9, 14 rhymes 10; S3: alternating fixed Mum/Keen setups; S6: 6 rhymes 2).
5. **Lens ladder = emotional distance.** 18mm world/threat bookends · 24-28mm group/action
   wides · 35mm medium-wide · 50mm relationship two-shots · 65mm conversational close ·
   85mm emotion close-ups · 100mm macro for object-history inserts (wristbands, net).
6. **Light is the narrative clock.** Warm amber → "cool blue-grey creeps into the edges" →
   steel-grey, stated per card across a turn. Colour temperature IS the story state.
7. **Sound written into picture cards.** FWIP, THUP-THUP-THUP, the RUMBLE, the sail
   CRACKING — sound design authored at storyboard time.
8. **Named visual-grammar modes.** The VISION (soft focus, warm saturation, rose-pink
   vignette borders), UNDERWATER (muffled blue-grey, bubbles), INTERCUT (labeled
   SHORE:/UNDERWATER: on the card). Modes are declared, not implied.
9. **Micro-expression cards.** A whole shot for "fails slightly at the corner of her
   mouth"; a whole shot for a swallowed throat. Feelings get screen time.
10. **Physical detail as emotional carrier.** The wristbands' "worn leather grain, tiny
    scratches from years of wear" in 100mm macro — objects carry history visually.
11. **Scale storytelling.** Ant-scale bees in shot 1, "tiny golden dots" against the storm
    in shot 16; Keen's boat "tiny against the vast" — smallness vs world states the stakes
    without a word.
12. **Ceremony gets sequence treatment.** The Crystal Call is 7 escalating shots
    (individual → montage → unison → burst → beam-across-the-world), not one beat.

## Our learning, layered on top (the fusion — what WE add that they lack)

1. **THE LIGHT LAW.** Their cards freely use "warm amber," "golden," and Scene 2's clips
   used "golden-hour" — the exact vocabulary that pulled our renders into sunset drift.
   Adopt their light-as-narrative-arc; express it in OUR proven vocabulary at generation
   time (high-key daylight / white sun high / clear blue sky as the day-state baseline;
   the storm turn expressed as concrete sky/shadow states, never time-of-day words).
   Our `_DRIFT_VOCAB_RE` gate stays law for anything we fire ourselves.
2. **IDENTITY ANCHORS.** Their reference chips + face-identity text ≈ our turnaround
   doctrine — but their identity TEXT drifts (Zenny as "lavender-purple bear" is live in
   their character data). Our locked canon (characters.json + turnarounds) is the source
   of truth; their fields get overwritten from ours, never trusted.
   **CONFIRMED VERBATIM (oracle session #7, 2026-07-24), and worse than first thought:**
   their Zenny identity reads in full "Small anthropomorphic bear… covered in soft
   lavender-purple fur," and her ONE wardrobe adds **"Small crystal gem visible at her
   chest"** — a DOUBLE canon violation baked into the identity anchor itself: wrong species
   (she is a bee) AND a worn crystal (bees never wear crystals, the Crystal World Rule).
   Every Zenny reference image their pipeline generates from that text carries both errors.
   Their Fuzzby, meanwhile, has a BLANK identity and desc ("", "") with one stub wardrobe
   ("Fuzzby, everyday outfit") — no identity anchor at all. Net: for the two bees, their
   character layer is unusable; ours replaces it wholesale, not merely "overwrites fields."
   **REFERENCE-METADATA VERDICT (same session):** their project JSON stores ZERO reference
   data — no image URLs, no attachment mapping, no weights/ordering, no approval flags, no
   generation provenance. All reference handling lives in a backend layer the oracle itself
   confirms it cannot see ("I would need… actual API request/response logs. None of these
   exist in the current project JSON."). Two consequences: (a) the oracle is EXHAUSTED as a
   source — it has now stated its own blindness twice; extraction formally closed; (b) our
   provenance stack (reference lineage per fire, .gen.json sidecars, approval history,
   spend ledger) has no equivalent anywhere in their product — a structural advantage on
   top of the four-reference + @Audio1 one.
3. **THE FACE-STATE REFERENCE** (our 10-take-proven weapon). For any persisting facial/body
   state (the golden moustache+goatee), a prepared image of the intended state beats any
   amount of text. Their pipeline has no equivalent — inject ours as an extra reference on
   the affected clips.
4. **VERBATIM DIALOGUE LOCK.** Their clips carry dialogue in-prompt (their native-audio
   formula). Every line must be checked verbatim against our locked script before a clip
   fires — our `check_scene_dialogue_verbatim` discipline, applied to their prompt fields.
5. **DURATION HONESTY.** Their flat 15s/clip is the old trap we just escaped. A 2-shot
   clip with one line doesn't need 15s. Trim clip durations to content (their duration
   slider exists) — pace AND money.
6. **ONE-VARIABLE RETAKES + REJECTION LADDER.** When a clip fails: one controlled reroll,
   then change exactly one variable, never prompt-pile-on. Two failed batches = redesign.
7. **CANON GATES BEFORE SPEND.** Bees never wear/carry crystals; wristbands VACANT until
   Scene 9; crystal shapes rough/organic never faceted; Keen is one character with
   states. Sweep every clip prompt against these before any batch fires.
8. **SCENE-BY-SCENE BATCHING.** Never "Generate All 48." One scene at a time, review,
   then the next — a systemic fault costs one scene, not $316.

## Canon flags found IN the storyboard itself (story-level, not nitpicks)

- **Scene 6, shot 12: "Zenny touches her crystal. It glows."** Zenny is a bee — bees never
  wear or carry crystals (the Crystal World Rule). Notably our OWN Director made the
  identical mistake once (CLAUDE.md rule 45's 6.B4 finding). The card needs Zenny's role in
  the Crystal Call restaged (witness/wind-rider, not crystal-bearer) before Scene 6 fires.
- Scene 6's Crystal Call montage (shot 11) gives each bear a distinct crystal glow — correct
  for bears, and the "surrender, not power-up" canon note should govern its delivery text.
- The wristbands glow amber in Scene 7 (shots 10/13) — this is the one sanctioned
  pre-Scene-9 moment IF it matches the locked script's rescue beat; verify against script
  before firing Scene 7 (in canon the crystals arrive in Scene 9; Scene 7's glow must be
  the script's own moment, not the storyboard's invention).

## The project manifest (oracle session #5, 2026-07-24) — the clip-packing ledger

Julian pulled the oracle's full per-clip manifest of their Ep 1. Higher credibility than the
infrastructure answers because it reads the real project JSON — and it marked every field NOT
in that JSON as UNKNOWN, including "Generation Models: UNKNOWN (not stored in project data)"
— **the oracle's own direct admission that its earlier confident Runway-payload answer was
invented.** Confabulation verdict now confirmed from inside.

What it adds:

1. **The real clip-packing ledger, all 10 scenes: 52 clips over 126 shots.** (We captured 48
   footage prompts from the UI — the 4-clip gap is unresolved; likely uncaptured/regenerated
   clips, note it, don't trust either count as gospel.) Packing shapes observed:
   - **Scene-opening establishing shots often ride ALONE as a 1-shot, no-dialogue clip**
     (Scene 1 clip 0 = shot 0 solo). Brick 1 rule: the establishing wide is its own clip.
   - Dialogue exchanges pack complete (a whole back-and-forth in one clip, e.g. the four-line
     Mum/Keen farewell), confirming the dialogue-boundary packing rule.
   - 2-shot clips are common at scene tails/transitions; 3-shot is the workhorse.
2. **A per-clip dialogue ledger** usable as a verbatim cross-check target: their Scene 1 lines
   match our locked script exactly ("Do I look official?" / "Yes Fuzzby. Officially nuts!" /
   "Buzz Crash!!" / "A Storm's coming." / "Good thing I work well under pressure.").
3. **CANON FLAG — Scene 3, clip 3:** their storyboard has KEEN'S MUM speaking "I still feel
   him… every day." In OUR canon that line was deliberately cut (CLAUDE.md rule 46 — Mum
   never names her grief aloud; the hand lingering on the wristbands carries it). If their
   Scene 3 storyboard is ever used, that clip's dialogue must be restaged wordless before it
   fires — same class as the Zenny-crystal flag above.
3b. **CANON FLAG — Scene 6, clip 3 (oracle session #6, the manifest's Scene-6 extension):
   the Crystal Call incantation is WRONG.** Their AIDA speaks "With open heart and love so
   bright — Rose Quartz Crystal, shine your light!" — locked canon's verbatim incantation
   (CRYSTAL_BEARS_LOCKED_CANON.md line 84) is **"With heart open wide, I stand with pride —
   Rose Quartz, be our guide!"** A paraphrase of a Crystal Call is exactly the drift class
   our own rule-45 sweep fixed in our package (6.B4/9.B2 snapped back to verbatim canon).
   The same clip also has "Everyone — activate your crystal powers." — the identical
   power-up framing our own Director once produced and rule 45 flagged (canon: the Call is
   surrender, never activation). Their Scene 6 dialogue must be snapped to canon verbatim
   before any of it fires. Pattern now confirmed three times: their storyboard is
   script-faithful on ordinary dialogue but drifts on CANON-LOCKED ritual/emotion content —
   run check_scene_dialogue_verbatim + the canon incantations over every scene before spend.
4. Clip-level duration/characters/props/references are NOT stored in their project JSON
   (all UNKNOWN) — their clips derive cast/refs at generation time from the shot arrays,
   confirming the parallel-array schema as the single source of truth. Brick 2 does the same.

## The continuity scoreboard (oracle session #8, 2026-07-24 — their own 10-mechanism audit)

Asked how continuity survives the Scene-1 clip-1→2 boundary, the oracle audited its own
project against ten mechanisms and confirmed, with per-field evidence, that SEVEN are
absent from their product. Scored against what OUR pipeline already does:

| Mechanism | Theirs | Ours |
|---|---|---|
| Previous clip's final frame → next start | ❌ none (no endFrame field anywhere) | ✅ THE HARVEST CHAIN — SH3 fired from SH2's real final frame |
| Storyboard/keyframe reference | ❌ `shotImages` arrays literally EMPTY | ✅ keyframe/opening-frame source choice per shot |
| Seed consistency | ❌ no seed stored | ➖ our provider takes no seed either (known) |
| Character reference images | ❌ text-only (and Zenny's text is off-canon, Fuzzby's blank) | ✅ turnarounds, locked canon |
| Location reference images | ❌ text-only | ✅ the scene plate rides every fire |
| Wardrobe/progressive state | ⚠️ text-only (pollen arc lives in prose) | ✅ face-state reference image (the 10-take-proven weapon) |
| Camera state across boundary | ❌ untracked | ⚠️ deliberate-cut doctrine; not tracked as data (by design) |
| Dialogue timing | ❌ plain strings, no temporal data | ✅ @Audio1 with measured durations drives generation |
| Automated continuity inspection | ❌ none | ✅ join checks, QA sidecars, retake ledger |
| Their verdict on themselves | "relies almost entirely on careful prompt engineering" | — |

The one column where their product genuinely leads remains the AUTHORING layer (storyboard
expansion, the footage formula, the agent UX) — which is exactly what we adopted. The
delivery/continuity layer is ours end to end. NOTE the internal tension with the earlier
oracle claim that "clips start from storyboard stills": in this project's actual JSON the
still arrays are empty — either stills were skipped or they live in backend storage; either
way the frame-handoff verdict (none) stands. This session also re-confirmed, a third time,
that the oracle cannot see its backend — extraction stays CLOSED.

## Working agreement

AnyFilm is the generation engine and storyboard author; our studio is the canon authority
and QA bench. Their storyboard structure is adopted as-is (it is better than ours); every
clip prompt passes our gates (canon, dialogue-verbatim, light vocabulary, identity
references) before money is spent; footage is judged by our retake discipline.
