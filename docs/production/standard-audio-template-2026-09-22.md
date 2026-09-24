# Standard dialogue and sound template

The available Episode 1–4 production packages were inspected: 20 packages,
57 current/submitted prompt records. This is not a claim that every historical
archive or rendered soundtrack has been listened to. Episode 4 S1.SH1 supplies
the reference pattern; S3's authored camera, staging and look remain unchanged.

## New compilations

### Frozen authority wording

`crystal-bears-s1-audio-v1` now contains the exact submitted Ep4 S1.SH1
`Dialogue Authority` wording, verified against its saved batch envelope.
SHA-256: `23640f82b6b45fc1d959566b0bd535b077d4d1cba39ab56e7b7cb5a878f4b163`.
Episode 2 saved prompt records also repeatedly contain the same core sole-authority,
once-in-braces, named-speaker and mouth-timing pattern, with historical variants
and scene-specific sound additions. They are not all byte-identical.

The version and fingerprint are regression-pinned in `test_standard_audio_template.py`.
Change this wording only through an explicitly approved template-version migration.
Creative rewrites must retain the audio block; native compilation records its version
and hash in evidence. Dialogue words, measured timing and scene-specific sound cues
remain separate variable inputs. Silent shots and explicitly approved exact-audio-only
contracts keep their distinct policies. Existing sealed requests retain their original
bytes rather than receiving an unreviewed transport-time rewrite.

This is a source-backed template baseline, not proof of error-free provider output.

- Approved HEAR / Audio1 owns spoken words, speaker, performance and measured timing.
- Emit each dialogue occurrence once, verbatim in braces, attributed to its speaker
  in the view where it starts. Repeated words in different approved occurrences
  remain distinct occurrences, not duplicates to discard.
- Carry existing speech across cuts. Only the visible active speaker articulates;
  an offscreen voice never becomes a listener's mouth movement.
- Action and camera instructions describe the performance without quoting a
  second version of dialogue or speaking editorial placeholders.
- Seedance supplies directed nonverbal effects, ambience and instrumental music.
  Sound cues must not become dialogue, narration, lyrics or an extra voice layer.
- Existing explicit full-Audio1-bed contracts in the legacy compiler retain their
  opt-out of generated sound. Historical sealed prompts are not rewritten.

Both legacy and native dialogue compilers share `STANDARD_DIALOGUE_AUDIO_AUTHORITY`
in `engine/cb_emission_conformance.py`. Authored sound cues remain in the Sound
section; this template does not invent missing musical or dramatic decisions.

The same contract now also supplies general-project WATCH preparation, comparison
segments, fallback prompt preparation, and video-edit requests. Video edits retain
their bounded correction window and existing sound outside that window. Already
sealed, complete historical requests are not rewritten during submission.

This is a software-wide structure, not a fixed cinematic recipe: DIRECT still owns
camera, geography, beats and sound choices; HEAR owns the measured dialogue bed.
The shared contract forbids shifting Audio1 to fit action, speaking SFX labels,
restarting words at cuts, or adding a vocal tail. Explicit no-music/no-SFX direction
is retained. The general-project workflow test checks that the exact reviewed
prompt, including this contract and once-only transcript, reaches the fake provider.

## Review and assembly

New returned mixes are preserved byte-for-byte for WATCH review. Do not replace
the whole soundtrack with dialogue-only Audio1 and do not overlay Audio1 a second
time. New `provider-final-mix-v1` provenance carries the approved complete mix into
scene assembly. Older explicitly dialogue-restoration post records retain their
existing policy; no production media or historical approvals are migrated here.

The provider is conditioned by Audio1, not guaranteed to return identical audio.
Provenance explicitly records that limitation. Lip-sync, dialogue accuracy, effects
and music still require human review. Prompt checks cannot certify those qualities.

No provider submission, production approval or paid generation is part of this change.

## Verification

120 focused tests passed across standard audio template, WATCH frontdoor, Seedance
execution, scene post, emission conformance and audio authority. These include
byte-preserving review, no dialogue-only replacement during new-policy assembly,
camera-authority preservation and cross-cut dialogue handling.

Broader checks are not green: emission-standard tests have five missing-fixture
failures; department and golden-path suites have twenty failures involving retired
department APIs, reference expectations, missing assets and timed-DIRECT fixtures.
Those results do not certify the entire Studio workflow. No new rendered output
was generated or listened to as part of verification.
