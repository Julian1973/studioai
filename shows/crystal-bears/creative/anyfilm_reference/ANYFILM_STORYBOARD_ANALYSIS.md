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

## Working agreement

AnyFilm is the generation engine and storyboard author; our studio is the canon authority
and QA bench. Their storyboard structure is adopted as-is (it is better than ours); every
clip prompt passes our gates (canon, dialogue-verbatim, light vocabulary, identity
references) before money is spent; footage is judged by our retake discipline.
