# Ep1 · Scene 5 — Production Package (hybrid)
_ · 1 shots · ~28s · validation: FAILED (3 issue(s)) · doctrine: THE_DEFINITIVE_PIPELINE.md_

## Director's statement
- **Feel:** The audience should feel the storm suddenly become real: the funny fast-talker goes quiet, the distant danger is understood, and then the rescue energy kicks in with a comic bump that does not undercut the urgency.
- **Whose scene:** Fuzzby leads the scene because his interruption, pointing, alarm, and messy launch create the dramatic turn; Zenny grounds the scene with steady concern.
- **Emotional change:** The scene moves from windy chatter to shared alarm, then into immediate action toward help.
- **The laugh:** Fuzzby’s urgent hero-launch is interrupted by an instant branch bonk, but he recovers and keeps going.
- **Visual surprise:** The camera discovers the tiny boat through trees and rain after Fuzzby’s silence points the audience outward.
- **Carries forward:** Fuzzby and Zenny are now moving fast toward the beach to alert the bears about the emergency.

## Validation report
- **ERROR** `DIALOGUE_OCCURRENCE_DROPPED` at `shots` — dialogue-occurrence:sha256:34840f880105d941cfcde26d8276af04ca65ed8e129c7161f8416d291bf56c9f — Fuzzby: "I’m just saying, if this turns into a full storm situation, I am extremely—"
- **ERROR** `DIALOGUE_OCCURRENCE_UNKNOWN` at `shots[0](5.B1.S1).dialogueLines[0]` — dialogue-occurrence:sha256:34840f880105d941cfcde26d8276af04ca65ed8e129c7161f8416d291bf56c9
- **ERROR** `DIALOGUE_OCCURRENCE_ORDER_CHANGED` at `shots` — expected ['dialogue-occurrence:sha256:34840f880105d941cfcde26d8276af04ca65ed8e129c7161f8416d291bf56c9f', 'dialogue-occurrence:sha256:fe5f134fa71d3fab878c0dd8ff2d286a165896b952cff4e77ca3bdb06e0e893c', 'dialogue-occurrence:sha256:700cc30aea58a3be7aa5c5e0e11baf4e93fb104e385c8ca470ad120651e7ec24', 'dialogue-occurrence:sha256:4b2a0a9f3594e468c580259e7be2beb5d676ceb2a5e3e8765fe7020e6b475e94', 'dialogue-occurrence:sha256:549b2316295d926a070dc2be601358a05fbd55dca8eb642898ae5d639cfb04ab'], got ['dialogue-occurrence:sha256:34840f880105d941cfcde26d8276af04ca65ed8e129c7161f8416d291bf56c9', 'dialogue-occurrence:sha256:fe5f134fa71d3fab878c0dd8ff2d286a165896b952cff4e77ca3bdb06e0e893c', 'dialogue-occurrence:sha256:700cc30aea58a3be7aa5c5e0e11baf4e93fb104e385c8ca470ad120651e7ec24', 'dialogue-occurrence:sha256:4b2a0a9f3594e468c580259e7be2beb5d676ceb2a5e3e8765fe7020e6b475e94', 'dialogue-occurrence:sha256:549b2316295d926a070dc2be601358a05fbd55dca8eb642898ae5d639cfb04ab']

## 5.B1.S1  ·  28.0s  ·  opener
**Purpose:** A single escalating discovery-and-action chain: Fuzzby’s chatter is cut off by the sight of danger, Zenny confirms the stakes, then Fuzzby turns alarm into action with one comic collision on the way out.
**Opening pose (keyframe truth):** Fuzzby is airborne slightly ahead at screen-center-right, facing screen-right into the wind with mouth just opening to continue speaking; Zenny is airborne behind at screen-left, facing screen-right and closing the distance. Tree branches ahead bend across their path, leaving clear space before any contact.
**Fuzzby** (1-5s): “I’m just saying, if this turns into a full storm situation, I am extremely—” — _Fast, breathless chatter into the wind; the final word cuts off cleanly when he freezes._
**Zenny** (7-7s): “Fuzzby?” — _Small, cautious question after nearly bumping into him; only Zenny’s mouth moves._
**Fuzzby** (13-15s): “…that is NOT a good place to be.” — _Quiet at first, then firmer on NOT; spoken while staring toward the distant boat._
**Zenny** (16-18s): “Someone’s in trouble.” — _Soft, direct, and focused; only Zenny’s mouth moves while Fuzzby holds his stare._
**Fuzzby** (19-21s): “BEARS! BEARS! EMERGENCY BEARS!” — _Sudden loud alarm, projected forward as he starts his launch; only Fuzzby’s mouth moves._
**Payoff:** Fuzzby ricochets off the branch with a clear BONK, wobbles for a beat, then flies on screen-right toward the beach with Zenny following faster behind him as the rain and branches whip past.
**Gag physics (5.B3):** stays visible — Fuzzby, Zenny, the branch, and the flight path remain visible through the launch, impact, rebound, and recovery; the branch contact is not hidden by a cut or obstruction.; contact/weight — Fuzzby’s forward motion carries him directly into the branch; the branch bends at the contact point, his body motion compresses against it, then the stored bend springs him slightly backward before he regains forward motion.; payoff shape — Approach fast, branch bend and BONK, short backward recoil, single shake to clear the wobble, then immediate forward continuation toward screen-right.
**Prompt:**
```
Stylised feature-quality 3D CGI matching @图1. Use @图2 only for Zenny, @图3 only for Fuzzby and @图4 only for the set.

Begin exactly on @图1, the approved opening frame — one continuous storm-side tracking shot from the forest flight path. Start in a medium two-shot moving screen-right with the characters; when Fuzzby stops, the camera eases past him into his eyeline and racks through rain and branches to the distant tiny boat. Hold the boat small in the frame, then drift back to Fuzzby and Zenny for their reactions. On Fuzzby’s shout, whip-pan with his launch, catch the branch impact in the same lateral direction, then continue tracking as both head toward the beach. Fuzzby flies slightly ahead through the wind while talking; he stops abruptly in mid-air, holds still, slowly points out through the trees, widens his eyes, then snaps forward yelling and launches toward the beach. Zenny nearly bumps into him, steadies, follows his gaze, softens her face, then accelerates after him. During the launch, Fuzzby hits a branch, rebounds, shakes once, reorients, and continues forward while Zenny follows behind without speaking. Fuzzby ricochets off the branch with a clear BONK, wobbles for a beat, then flies on screen-right toward the beach with Zenny following faster behind him as the rain and branches whip past.

Use @Audio1 as the only voice. Lip-sync Fuzzby and Zenny. Preserve character identity and relative scale. Keep Fuzzby, Zenny, the branch, and the flight path remain visible through the launch, impact, rebound, and recovery; the branch contact is not hidden by a cut or obstruction. Keep brief post-bonk wobble visible.
```
**Keyframe prompt:**
```
Stylised feature-quality 3D CGI with natural weight. Preserve the exact character designs, proportions, materials, lighting and environment from the references.

The literal OPENING FRAME of the shot, exactly as approved: Fuzzby (@图2, larger bee) is airborne slightly ahead at screen-center-right, facing screen-right into the wind with mouth just opening to continue speaking; Zenny (@图1, smaller bee) is airborne behind at screen-left, facing screen-right and closing the distance. Tree branches ahead bend across their path, leaving clear space before any contact.

@图3 scene plate anchors palette, materials and lighting only — never composition or geography.

Living performance lock: Fuzzby, Zenny has a specific motivated eyeline target and a readable active thought in the eyes. Use a precise asymmetric expression; no vacant forward stare, unfocused eyes, frozen smile, mannequin pose or generic camera-facing expression.

Negative: character redesign, appearance drift from the references, extra characters, on-screen text.
```
