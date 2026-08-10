# GOLDEN FIXTURES — Scene 1

Four emissions that were rendered and accepted by the director. They are the
compiler's acceptance test, not documents to paste.

`beat_1_chase.txt` is linked to its accepted Flova render by
`ACCEPTED_RENDER_PROVENANCE.json`. Julian identified this as the best shot produced to
date and the target formula for the compiler. The prompt and render hashes are part of
the fixture contract; neither may be silently replaced.

## The contract

For each fixture:
  input   = the typed Director beat record for that unit
  output  = the compiler's emission
  test    = the emission must score >= 9.0 on the Part 5 pre-flight AND must
            contain every structural element listed in that fixture's manifest

A compiler change that lowers any fixture's score is a REGRESSION and blocks
the push. The fixtures are versioned; a fixture is replaced only when a new
render beats it and the director says so.

## Why these four

They cover the four proven archetypes and, between them, exercise every rule
in the Emission Standard:

  beat_1_chase          false-triumph-chase   R8 R9 R10 R11 R12 R13 R14 R15 R19
  beat_2_moustache      reveal-and-deadpan-verdict   R15 R16 R19 R20
  beat_3_crash          escalation-into-verdict      R10 R16 R20
  beat_4_storm          environment-turn             R20 + environment ordering

## The anti-throttle rules

These are the specific ways the compiler has degraded a good emission before:

1. Emitting stale direction fields alongside a new shot plan (R17) — a "story
   lock" describing the old action next to shots describing the new one.
2. Stating the same action in three fields in different words (R18).
3. Carrying `no cuts` / `no handheld` into an action unit (R14).
4. Applying hold boilerplate to shots that contain no button.
5. Geography contradicting staging law (R17 + canon injection).
6. Trimming prose to fit a budget instead of returning the decision to the
   director.

Every one of those is a check. None of them may be "fixed" by weakening a
fixture.
