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

## 2026-07-04 — Law 8 camera-lock-conflict detector vs 1.B1's already-signed cut 1

- **Check verdict**: FLAG (`check_camera_lock_conflict`, PROMPT_LAWS_AUDIT.md's Law 8 detector, added this same
  day) — 1.B1's cut 1 has dialogue but its authored `framing` text names a camera-movement word ("push"),
  contradicting the beat-level "camera holds static during dialogue" rule stated in the same shipped prompt.
  1.B2's cut 1 independently flagged too, for the OTHER Law 8 branch — its framing names two distinct
  camera-movement words ("swings", "chases") in one shot, where the law wants one primary move per shot.
- **Status**: 1.B1 is already fully signed (official clip stands, per its earlier sign-off run). Per Julian's
  standing ruling (rule 18, 2026-07-03), this is calibration data only — the check applies forward, 1.B1's
  signed clip is not touched or queued for regeneration because of it. 1.B2 is NOT yet signed (Julian is still
  picking a winner for the just-fired re-render) — its flag is a live, actionable item for that pending
  decision, not calibration data; surfaced in the same render's own log line, not logged here as a separate item.
- **Why this matters for calibration**: this is the check's very first live run against real production data,
  and it found something real on its first pass — both flags describe the actual authored `framing` text
  accurately (verified against the shipped prompt directly). Worth watching whether "push"/"swings"/"chases"
  turn out to be common, harmless authorial habit (camera-arc language describing Seedance's OWN cinematic
  freedom, not a literal locked-camera violation) rather than a genuine law conflict — if this fires on most
  beats going forward, the keyword list or the dialogue/movement distinction may need tightening before it's
  useful signal rather than noise.
