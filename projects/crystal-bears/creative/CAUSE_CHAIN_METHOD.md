# THE CAUSE-CHAIN COMPILE — script -> storyboard -> keyframe -> prompt, joined up

Julian, 2026-07-26: "the world class director takes a script and brings it to life in an
Emmy/Oscar-winning way with the Pixar-DreamWorks look and Bluey humour — the storyboard
drives the direction of the keyframe and the prompt, so the priority is landing the beat
the way the Director, Producer and Cinematographer wanted."

Derived by 4 parallel researchers + 1 synthesis, from: the seedance-20 platform doctrine,
forensics on the ONE approved prompt vs TWO rejected ones of near-identical length, Docter/
Keane craft translated into promptable form, and the ranked real failure record.

## THE FINDING THAT SETTLES THE LENGTH ARGUMENT

| prompt | words | stop/park phrases | verdict |
|---|---|---|---|
| SH1_KEEPER_EXEMPLAR | 722 | **1** | APPROVED |
| SH2_old_engine | 716 | **9** | rejected |
| SH2_LABOURED | ~710 | **10** | rejected |

Same length. Opposite verdicts. **Length is not the variable — stop-command density is.**
AnyFilm's 244 words are a symptom of their economy, not the cause of their quality.
Cut for what words are DOING, never to hit a budget.

## THE METHOD

THE CAUSE-CHAIN COMPILE — one physical cause, relayed, with the talking on top of the biggest move.

WHAT THE DIRECTOR SUPPLIES (nothing else is authored per beat): feltIntent (why it's funny, what it means), the physical spine, speaker order, ending type. Everything below is how that becomes the prompt.

STEP 1 — REDUCE THE BEAT TO ONE PHYSICAL CAUSE. Every later event must be a consequence of it, not a sibling of it. S1.SH2's cause is Fuzzby's own over-committed dive; the moustache, the preen and Zenny's crack are all downstream of it. If you find two independent causes, you have two shots — split them (SH2A/SH2B), never compress. Cap the take at 4-6 causally chained events: the recorded failure is 8 beats in one 15s take, "every take lands some beats and drops others."

STEP 2 — RELAY THE SENTENCES. Whatever was the OBJECT of the last sentence becomes the SUBJECT of the next, and the world acts on the character wherever it can ("The cup compresses around his face... then springs back and pushes him out"). Test: if you need "then" or "meanwhile" to join two events, the chain is broken — that join is either a missing cause or the real cut point. This replaces the one-idea-per-shot rule outright, which would refuse the only approved prompt we have.

STEP 3 — ONE EVENT PER PARAGRAPH, 30-60 words, break at every change of cause. Past ~70 words a paragraph is holding two events and the model compresses one out. This is the visible form of the "checklist compressed into one stacked sentence" rejection.

STEP 4 — PUT THE BIGGEST TRAVEL ON THE DIALOGUE WINDOW. Dialogue is most of a 15s clip. Whatever the largest physical move is, write it inside "During the [X] spoken section of @Audio1...". Never finish the action and then park to talk — that authors the static back half Julian keeps rejecting as "no real movement, the pace is poor." Where the speaker order forces the line late, give that spoken section its own real travel (a rising display turn, not a hover).

STEP 5 — TIER THE CAST, TEMPORALLY. One character gets the full physical chain. The other gets a continuous named TASK plus micro-corrections running the whole shot, and exactly ONE focused response, placed after the first has stopped moving. Never a state word — "flat", "still", "near-motionless", "barely moves" are freeze commands. And sequence the spend: motion phases get zero facial prose; the take and the reaction get the face while everything else has settled.

STEP 6 — WELD THE SECOND CHARACTER TO AN OBJECT. They never have a position, they have an anchor that moves with them. This is what stops the teleporting.

STEP 7 — WRITE THE TAKE, NOT THE EMOTION. Two devices, both physical: (a) an EYELINE ORDER — where the eyes go, in the sequence a real thought runs; (b) a CONVERSION VERB — FROM-TO with the trigger and the mechanism named ("hurriedly converts that surprise into exaggerated confidence"). A named emotion renders as a held pose; a named change renders as acting. Give the realisation its own gap: the world stops, the character doesn't, then one small event is the penny dropping.

STEP 8 — EVERY ACCENT NEEDS SOMETHING TO LOAD AGAINST, AND EVERY STOP LEAVES ONE PART LATE. Anticipation is a coil, not an adverb. Name the one thing still moving after the mass has settled — antennae, pollen, the stem. Declare a flexing structure as one connected physical unit before it acts.

STEP 9 — DECLARE THE MEDIUM AS A MOTION LICENCE, in the same breath as motion, at the top: "3D CGI feature animation with real weight and elastic squash-and-stretch — bodies compress on impact and overshoot on release." The model's prior is smooth real footage; cartoon accents are discontinuities it will smooth away unless the declared medium makes them the correct output. Repeat the phrase verbatim across shots in a scene.

STEP 10 — CAMERA IS AN EVENT. One declaration line at the top (height, lens, continuous take, begin exactly on @图1). Every later camera move is written inside the paragraph of the action that motivates it. No front-loaded itinerary. No governing composition. The last camera move goes to the WITNESS, leaving the performer in soft background depth — then the hold, what is still settling, and silence.

STEP 11 — CONTINUITY IS ONE WORD, INLINE. "the same", "still", riding inside a sentence already doing action work. Never a dedicated safeguard paragraph.

STEP 12 — DIAGNOSTICS ON THE DRAFT (smoke alarms, not rules to write by). Stop/park phrases: keeper 1 per 722 words, rejects 9 and 10 — target ≤1. Negation density ≤0.9 per 100 words. Longest paragraph ≤70 words. Object-as-subject constructions ≥4. Occurrences of "two-shot": zero. Length is NOT a target: the keeper is 722 words and approved, a reject is 716 and dead. Cut for what words are DOING, never to hit a budget.

RESOLVED DISAGREEMENTS: (1) Length — platform doctrine's 40-110 words is the fast-lane figure for a bare standalone clip; our own A/B at matched length with opposite verdicts is direct evidence on our surface, so stop-command density wins over word count. (2) Camera — the doctrine's "locked frame, hold past comfort" for comedy is adopted only as a momentary device at the button (the keeper's final 2s silent hold), never as a shot-level policy; the keeper's motivated moving camera wins because it is the approved evidence and because the rejects' fault was the parked frame, not the moving one. (3) The 12-word closing meaning sentence — rejected as a standing rule; the keeper won without one, and states meaning welded inside a physical sentence instead ("he is a passenger, not a performer"). Weld it, never trail it. (4) Named SFX as a sync target vs the keeper's zero onomatopoeia — the keeper wins for now; impact is rendered as deformation. One described audible event (never a caps onomatopoeia) is the named next A/B, not a law. (5) Shot count — the Director's "one continuous shot" is honoured and declared explicitly; the constraint that actually matters is events-per-take and causation, not shot count.

## DELETE THESE

- The machine-appended 'Hard constraints:' tail and QUALITY_LINE in cb_engine.py — the approved prompt carries zero standing negatives, the rejected one ends on exactly that list, and every negated concept is still an activation the prompt pays for.
- Every 'mouth alone lip-syncs' / 'mouth movement belongs only to' string — it instructs the model to animate nothing but a mouth across most of a 15s clip and is the most likely direct author of the recorded 'stale emotions and dead delivery' verdict; replace with 'synchronise his mouth, expression and body'.
- The front-loaded camera itinerary (68-97 words in the rejects vs 14 in the keeper) and with it every camera-parking verb governing a span of runtime.
- The dedicated continuity/anchor paragraph and its re-locks — it is built almost entirely from stasis verbs the model obeys literally, and AnyFilm ship AAA footage with no state machine at all.
- Description-by-negation of a still character ('flat and near-motionless', 'barely moves except for wingbeats') — a stationary character gets a task, and the deadpan lives on the face, never in the body.
- The fourth cut in any 15s beat — 3.75s per shot is under the platform's own compression floor and the named symptom is exactly 'a shot's action skipped or compressed'.
- The numeric stasis-ratio rule as an authoring instruction — keep the count as a draft diagnostic, but ban the construct instead, because a ratio cannot distinguish Zenny's stillness (the joke) from a framing lock (the killer).
- The one-idea-per-shot law in DIRECTOR_TASTE_CANON §6 — it would refuse the only prompt Julian has ever approved; causation, not idea count, is the real variable.
- Any further prompt wording aimed at the grey goatee — words have lost 9/9 renders to the image prior; this is an image job (a prepared face-state reference) or a design change, and spending words on it is spending them on nothing.

## HONEST LIMITS

WHAT THIS METHOD CANNOT FIX. The grey goatee and the pink-sunset-mountain composite are a platform limit, not a prompt failure: 9/9 renders across every wording tried, both competing hypotheses tested and falsified, and the transmitted text verified clean. No sentence in this prompt will beat that image prior — the two real answers on record are a prepared face-state reference image or a moustache-only design change, and anyone proposing new wording here should be told it has been tried nine times. Likewise, half the audio failure ("Nailed it" landing as a 0.4s blip on the shot's hard edge) was fixed by padding the master and pulling the onset from 11.5s to 10.0s; prompt words cannot pad an asset. And the reference stack still shows identity and world and nothing of the impact or the payoff — on a crash beat the words alone are buying the one moment the shot exists for, which is why the keeper needed 722 words and why cutting to a budget is the wrong economy.

WHAT REMAINS UNPROVEN UNTIL IT IS FIRED. The whole method rests on n=1 approvals and one A/B pair; it is the best evidence we have, not a demonstrated law. Specifically untested: (a) deleting the standing negatives tail — the inference that stasis verbs and prohibition lists are authoring the "immobilised" footage is strong but the clean test is one fire of an existing shot with the tail stripped and nothing else changed; (b) the named-sound sync target — the platform mechanism says audio and picture denoise jointly so a named SFX is an enforced timing instruction, but the keeper won with zero onomatopoeia, so I left it out; that is one A/B, not a settled question; (c) the locked-frame comedy hold as a whole-shot choice, which contradicts our camera-as-character law and should go to Julian as a test rather than be adopted; (d) the ≤6-events cap and the 30-60-word paragraph target, both derived from two rejections rather than measured.

ONE DIRECTORIAL DECISION I MADE ON THE EVIDENCE, WHICH MAY BE WRONG. I placed Fuzzby's spoken section on the dive approach, not on the preen — because the biggest travel must sit on the dialogue window, and because the delayed take reads stronger silent. If the recorded @Audio1 line is explicitly about the moustache, that section has to move after the reveal, and the display turn must then carry the travel instead — the paragraph is written so it can, but the prompt would need re-ordering, not patching. The prompt also states no per-beat timings deliberately: every recorded attempt at prescribed geometry or clock times lost the pace it was meant to protect.