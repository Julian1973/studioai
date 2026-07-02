# for_beat_v2 review — Ep1 Scene 1, beats 1.B1–1.B4 (T7)

*Generated for Julian's review only. `for_beat_v2` is NOT routed — `cb_beats.run` and `cb_seedance.get_seedance_prompt`
still call `cb_segprompt.for_beat` (the current shipping v1) exclusively. Nothing below changes what fires. This
runs against the corrected Scene 1 canon (the meadow-world fix, same session).*

## Known issue found while generating these — not fixed, flagging for your call

A text-substitution bug appears in 3 places across these 4 outputs — something ending in a possessive `'s` (a
character name or a quoted dialogue fragment) gets partly replaced by an audio-reference phrase, leaving the `'s`
dangling on the wrong word:

- **1.B1**, AUDIO: `"music drops for Zennythe line in @Audio1 — kept low under the voice"`
- **1.B2**, AUDIO: `"Fuzzbythe line in @Audio1s line, then lands a dry pizzicato tick on the line in @Audio1"`
- **1.B4**, ACTION/PERFORMANCE: `"Hold 0.9 seconds after the line in @Audio1s coming.” before the larger bee's boast"`

This is a real bug in `for_beat_v2`'s delabel/audio-substitution logic (same general bug class as the `_units`/`_pose`
"Fuzzby Fuzzby" find earlier this session, in a different function) — not a one-off. Since `for_beat_v2` is your
call to route or not, I left it as-is rather than patching it ahead of your review; the four prompts below are its
real, current, unmodified output.

## 1.B1 — "The giant flower field is safe, warm and playful..." (13s)

```
13 seconds, 16:9.

REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the character(s) EXACTLY as drawn (no redesign, no morphing, no rescale, no new accessories) and copy the environment and lighting from it. @图2 is the larger, eager, manic bee (frame-LEFT); @图3 is the smaller, calm, deadpan bee (frame-RIGHT). Their turnarounds lock proportions, markings and features. Add ONLY motion and performance. No extra characters, no redesign.

WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.

SCENE: Warm golden morning god-rays isolate the flower corridor; pollen motes sparkle around the larger, eager, manic bee's path while the smaller, calm, deadpan bee remains in cleaner, calmer amber light. Floating pollen, swaying petals, and soft breeze make the air feel edible and safe; leaves at bee-height create playful obstacle rhythm. a ground-level wildflower corridor — lavender, daisies and clover that loom tall at bee-flight height — laced with floating hearts and cut crystals

ACTION / PERFORMANCE: the larger bee is full-throttle hyper, zig-zagging, bumping and snapping back; the smaller bee is smooth and measured, holding the comic contrast. Tall flowers sway gently in the warm breeze as the larger bee and the smaller bee weave between blossoms collecting pollen from flower to flower; the smaller bee's path is smooth and precise while the larger bee zig-zags wildly and loudly hums as he works, wings beating rapidly and continuously while airborne. the larger bee dips low into a flower and scoops up pollen, overdoes the exit, spins sideways into a leaf with a soft FWIP, bounces back into the air, and rapidly straightens into a proud on-parade hover; wings keep flapping fast with motion blur. the larger bee holds his proud hover after the leaf bounce as if the impact were part of the method; the smaller bee remains frame-right in the background line, still working neatly. the smaller bee glides up beside the larger bee and watches him for a beat, perfectly still except for rapid wing flaps; the larger bee sustains the proud pose one blink too long. After the line in @Audio1 hold the smaller bee's silent watch for about 1.2 seconds; music ducks so the still look lands. Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional timing; the performance carried in the eyes, the breath and the weight. The take should feel like: A fizzy upward bounce in the chest that lands as a soft FWIP in the ribs within the first two seconds.

CAMERA: Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they help the storytelling — but keep every character readable and on-model at all times. No chaotic camera. Begin wide and warm to make the world feel huge and safe, chase the larger bee's chaotic confidence into the FWIP, then settle into a locked two-shot so the smaller bee's stillness becomes the quiet topper.

AUDIO: use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other speech. Seedance generates and mixes everything else: Warm morning insects, soft petal rustle, fast continuous bee wings; the larger bee's sing-song rides a light pizzicato motif, FWIP lands with a soft leafy snap and tiny percussion puff, music drops for Zennythe line in @Audio1 — kept low under the voice (no sung lyrics).

NEGATIVES: no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, no on-screen text or subtitles, no logos or watermarks, no foreign-language speech, no crystals on or attached to the bees, no still/frozen/motionless wings on any bee that is airborne, no bee gliding or hovering with static wings
```

## 1.B2 — "Fuzzby escalates from proud professional to pollen-disaster..." (12s)

```
12 seconds, 16:9.

REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the character(s) EXACTLY as drawn (no redesign, no morphing, no rescale, no new accessories) and copy the environment and lighting from it. @图2 is the larger, eager, manic bee (frame-LEFT); @图3 is the smaller, calm, deadpan bee (frame-RIGHT). Their turnarounds lock proportions, markings and features. Add ONLY motion and performance. No extra characters, no redesign.

WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.

SCENE: Warm amber light catches the pollen dust on the larger, eager, manic bee's face so the gag reads instantly, while the smaller, calm, deadpan bee is lit cleanly and evenly for the deadpan line. Pollen motes thicken into a soft golden cloud around the flower, building the sneezy-tickly feeling before the reveal. a ground-level wildflower corridor — lavender, daisies and clover that loom tall at bee-flight height — laced with floating hearts and cut crystals

ACTION / PERFORMANCE: the larger bee rockets into the flower too fast, then freezes for the moustache reveal; the smaller bee's stillness slows time for the punchline. From the prior watch, the larger bee zooms toward another flower, humming louder, and lines himself up with too much confidence while the smaller bee holds a clean hover nearby; both airborne wings beat rapidly and continuously. the larger bee sticks his whole face into the flower; after a beat, he pulls back out completely dusted in pollen like a fuzzy yellow moustache as the smaller bee tries not to laugh. the larger bee presents the pollen moustache with proud seriousness, holding still enough for the audience to read the absurdity while his wings continue fast fluttering. the smaller bee fights the smile for a beat, then lets the smallest dry amusement through while the larger bee waits for praise. Hold the pollen-moustache reveal for about 0.8 seconds before the line in @Audio1, then hold the smaller bee's almost-laugh for 0.7 seconds before her answer. Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional timing; the performance carried in the eyes, the breath and the weight. The take should feel like: A little tickle under the nose that turns into a held giggle in the throat.

CAMERA: Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they help the storytelling — but keep every character readable and on-model at all times. No chaotic camera. Track the larger bee's overconfident acceleration into a pollen-cloud reveal, then go still and honest so the line reads through the smaller bee's controlled face.

AUDIO: use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other speech. Seedance generates and mixes everything else: Continuous fast wing buzz, muffled flower whoomp, soft pollen poof, Fuzzbythe line in @Audio1s line, then lands a dry pizzicato tick on the line in @Audio1 — kept low under the voice (no sung lyrics).

NEGATIVES: no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, no on-screen text or subtitles, no logos or watermarks, no foreign-language speech, no crystals on or attached to the bees, no still/frozen/motionless wings on any bee that is airborne, no bee gliding or hovering with static wings
```

## 1.B3 — "Stung by Zenny's joke, Fuzzby wipes at his face..." (15s)

```
15 seconds, 16:9.

REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the character(s) EXACTLY as drawn (no redesign, no morphing, no rescale, no new accessories) and copy the environment and lighting from it. @图2 is the larger, eager, manic bee (frame-LEFT); @图3 is the smaller, calm, deadpan bee (frame-RIGHT). Their turnarounds lock proportions, markings and features. Add ONLY motion and performance. No extra characters, no redesign.

WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.

SCENE: The beat begins in golden amber, then the distant background cools by the thunder hold, isolating the larger, eager, manic bee's mid-hover pause against a slightly dimmer sky gap. Pollen clouds and petal bounce build the chaos; the air subtly stills for the rumble, with motes hanging for a half-second like the world is listening. a ground-level wildflower corridor — lavender, daisies and clover that loom tall at bee-flight height — laced with floating hearts and cut crystals

ACTION / PERFORMANCE: Fastest the larger bee tempo of the scene: frantic wipe, dive, clip, tumble, pop; then abrupt suspended stillness at the thunder. the larger bee gasps, wipes at his face, somehow smears the pollen worse, then dives again toward another flower as the smaller, calm, deadpan bee watches from frame-right; both airborne wings beat rapidly. the larger bee clips a branch, tumbles end over end through the air with weighted THUP, THUP, THUP impacts, lands upside down inside a blossom, holds a beat with little legs kicking, then pops back up. the smaller bee rolls her eyes, but she is smiling now; the larger bee hums louder, dives into another flower, and pops back out somehow even more covered in pollen than before. the smaller bee watches the larger bee for a beat; a distant rumble of thunder rolls; the larger bee pauses mid-hover, wings still beating rapidly as his confidence catches. Hold the larger bee upside down in the blossom for about 0.8 seconds before the pop-up, then hold the thunder pause for 1.2 seconds before the line. Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional timing; the performance carried in the eyes, the breath and the weight. The take should feel like: A tumbling carnival drop that suddenly catches as a tiny held breath when thunder rolls.

CAMERA: Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they help the storytelling — but keep every character readable and on-model at all times. No chaotic camera. Go with the larger bee's wild overcorrection at full comic intensity, then drain the motion into a locked 50mm hold when thunder enters, letting the first prickle land in the same frame as the pollen mess.

AUDIO: use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other speech. Seedance generates and mixes everything else: Rule-of-three THUPs with real weight, pollen puff on each bounce, tiny triumphant sting on the line in @Audio1; music resumes for his louder humming, then drops out under a low distant thunder rumble, leaving only wings and the small line. — kept low under the voice (no sung lyrics).

NEGATIVES: no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, no on-screen text or subtitles, no logos or watermarks, no foreign-language speech, no crystals on or attached to the bees, no still/frozen/motionless wings on any bee that is airborne, no bee gliding or hovering with static wings
```

## 1.B4 — "After the distant thunder, Zenny looks toward the sky..." (12s)

```
12 seconds, 16:9.

REFERENCE LAW: @图1 (the keyframe) is TRUTH — copy the character(s) EXACTLY as drawn (no redesign, no morphing, no rescale, no new accessories) and copy the environment and lighting from it. @图2 is the larger, eager, manic bee (frame-LEFT); @图3 is the smaller, calm, deadpan bee (frame-RIGHT). Their turnarounds lock proportions, markings and features. Add ONLY motion and performance. No extra characters, no redesign.

WINGS: whenever a bee is AIRBORNE — which is almost the whole time — its wings BEAT rapidly and continuously, a fast visible flap with real motion blur-and-snap, the entire time it is off a surface. A hovering, drifting, gliding or zipping bee is ALWAYS flapping. NEVER a still, frozen or motionless wing while a bee is in the air (a bee that stopped flapping would drop); wings only come to rest when the bee is fully landed or perched on a surface.

SCENE: Warm amber foreground remains on the bees, but a faint cool blue-grey veil slides across the upper flower tops and sky gap to isolate the smaller, calm, deadpan bee's sky glance. Pollen motes slow and thin; the breeze gains a slightly firmer push through petals, but nothing dangerous is visible yet. a ground-level wildflower corridor — lavender, daisies and clover that loom tall at bee-flight height — laced with floating hearts and cut crystals

ACTION / PERFORMANCE: the smaller bee is slow, precise and watchful; the larger, eager, manic bee snaps back into fast bravado and immediately over-shoots into the flower. the smaller bee glances toward the sky as the light shifts slightly; something feels different, but they do not see anything yet; the larger bee remains paused mid-hover beside her, wings rapidly flapping. the larger bee resets into a proud hover, trying to make the pressure sound like an achievement; the shifted light grazes the pollen still on him. the larger bee immediately flies into a flower and gets stuck again; the flower absorbs him with a soft thump while his wings buzz and legs kick; the smaller bee sighs, still frame-right, dry and unsurprised. The flower field holds on the larger bee stuck in the blossom and the smaller bee's small sighing stillness as the light remains subtly shifted and the breeze moves the petals; no storm is visible yet. Hold 0.9 seconds after the line in @Audio1s coming.” before the larger bee's boast, then hold the larger bee stuck and the smaller bee's sigh for about 1.3 seconds as the exit button. Weighty cartoon physics: clear anticipation → impact → follow-through; readable comedy/emotional timing; the performance carried in the eyes, the breath and the weight. The take should feel like: A tiny cool shiver on the back of the neck followed by a soft comic thump of relief.

CAMERA: Seedance directs the camera cinematically — smooth feature-film movement and tasteful cuts where they help the storytelling — but keep every character readable and on-model at all times. No chaotic camera. Start still and attentive with the smaller bee's read of the sky, push into the larger bee's bravado, then release to a wide comic exit that lets the stuck-flower button sit inside a slightly cooler world.

AUDIO: use ONLY @Audio1 for ALL dialogue — the characters speak the words in @Audio1 with precise en-US lip-sync, each mouthing its own lines in @Audio1 in order; generate no other, different or duplicate voice, and no other speech. Seedance generates and mixes everything else: Low distant thunder tail fades into firmer breeze; a faint unresolved note under the smaller bee's line, proud tiny brass-like sting for the larger bee's boast, immediate soft flower thump and muffled wing buzz, then the smaller bee's sigh in near-silence. — kept low under the voice (no sung lyrics).

NEGATIVES: no morphing, no redesign, no rescale, no extra limbs, no flicker, no compression or grain artifacts, no on-screen text or subtitles, no logos or watermarks, no foreign-language speech, no crystals on or attached to the bees, no still/frozen/motionless wings on any bee that is airborne, no bee gliding or hovering with static wings
```

## What's genuinely richer than the shipping v1

- Named-role camera language ("the larger, eager, manic bee" / "the smaller, calm, deadpan bee") instead of generic "the bee" — carries personality into the role-label itself.
- Specific timing beats baked into ACTION/PERFORMANCE ("Hold the pollen-moustache reveal for about 0.8 seconds before the line in @Audio1").
- A real music/SFX plan per beat (pizzicato motifs, THUP impacts, music ducking for a reaction) instead of a generic "light playful underscore."
- `physicalFeeling`/audience-feeling text folded into an explicit "The take should feel like:" line for Seedance.

No routing change made. `for_beat` remains the sole shipping path.
