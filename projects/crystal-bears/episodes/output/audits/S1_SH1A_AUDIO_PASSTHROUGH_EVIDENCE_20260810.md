# S1.SH1A Audio Passthrough Evidence

## Question

Do the two rejected candidates contain dialogue, and is it an exact passthrough of the
approved Take A voice master?

## Assets Examined

- Approved voice master: `engine/media/shots/Ep1_S1.SH1A_vo_candidate_5340d8a2.wav`
- Candidate 1: `engine/media/shots/Ep1_S1.SH1A_c1.mp4`
- Candidate 2: `engine/media/shots/Ep1_S1.SH1A_c2.mp4`

The production ledger records the approved voice asset and its hash as an input to both
candidate requests.

## Speech Evidence

Local speech recognition found the scripted material in both candidates:

- Approved master: `Busy, busy, busy! Busy, busy, busy! Nailed it!`
- Candidate 1: recognisable `Busy...` material and `Nailed it!`
- Candidate 2: repeated approximate `Fizzy...` material and `Nailed it!`

Therefore both candidates contain dialogue. Candidate 2's wording is less faithful.

## Waveform Evidence

After extracting and normalising candidate audio, full-track band-passed waveform
correlation with the approved master was low:

- Candidate 1: `0.074`
- Candidate 2: `0.148`

RMS-envelope correlation was approximately zero. Cross-correlation around the `Nailed it`
region was only `0.267` for Candidate 1 and `0.387` for Candidate 2.

## Finding

Neither candidate is an exact audio passthrough of Take A. The evidence supports that
Seedance regenerated or materially altered the supplied performance as guide audio. It does
not prove the identity of any alternative synthetic voice, so the defensible finding is
`not exact approved waveform`, not an unsupported claim about who or what voiced it.

## Engineering Consequence

Use synthesis emission: exact dialogue text appears once as a placement marker while
`@Audio1` is the sole authority for voice identity, cadence, delivery, mouth timing and
silence. Treat provider dialogue as guide audio and restore the approved master in post.
