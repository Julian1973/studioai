# QA Calibration Log

Instances where a vision-QA check's verdict disagreed with Julian's actual sign-off — kept as calibration data for
tuning check strictness over time. Never used to retroactively regenerate already-signed work: a hard rule (Julian,
2026-07-03) is that a QA check applies FORWARD ONLY unless he rules otherwise for a specific case. Logging the
disagreement here is the record; it is not an action item.

## 2026-07-03 — ACTION_STATE_MISMATCH vs the 1.B1 / 1.B2 sign-off

- **Check verdict**: FAIL (`ACTION_STATE_MISMATCH`) on both 1.B1's and 1.B2's keyframes — wings read symmetrical
  and flat, body near-vertical with legs dangling, judged against the concrete wing-asymmetry/body-lean criteria
  in `cb_qa.py`.
- **Julian's sign-off**: PASS — seed 5 picked as the winning take for both beats from the five fired under the
  v3 template; the keyframes and clips stand.
- **Ruling** (Julian, 2026-07-03): "ACTION_STATE_MISMATCH applies FORWARD ONLY; the signed 1.B1 and 1.B2 clips
  and their keyframes stand, log the check's disagreement with my sign-off as calibration data, do not
  regenerate signed work."
- **Why this matters for calibration**: the check is brand new — added the same day, in direct response to this
  exact pose problem, so it is expected to fire on the pose it was built to catch. Julian judged the full
  rendered TAKE (not just the still keyframe) as good enough to sign despite the flagged opening frame. That is
  a genuine signal that a still-frame pose check doesn't always predict whether the completed clip reads as
  intended once it's in motion — worth watching if this pattern repeats (a keyframe FAIL that Julian still signs
  off after seeing the finished clip) before deciding whether to tighten, loosen, or leave the check as is.
