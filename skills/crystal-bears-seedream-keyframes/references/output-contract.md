# Output Contract

Preserve identifiers and signed-off version hashes from screenplay through final edit.

## Keyframe record

```yaml
shot_id: "S##_###"
take_id: "T##_###"
keyframe_id: "KF##_###"
upstream:
  screenplay_version: "exact version/hash"
  director_version: "exact version/hash"
  shot_plan_version: "exact version/hash"
  dramatic_event: "locked event"
  emotional_turn: "from -> to"
  pov_owner: "character"
  audience_question: "question"
  withheld_at_frame_one: "information/action"
  decisive_instant: "exact moment"
reference_ledger:
  - slot: "@Image1"
    asset: "canonical asset ID/path"
    role: "identity|continuity|location|prop|pose|palette"
    controls: "authorised attributes"
    excludes: "forbidden influence"
spatial_state:
  subjects:
    - name: "canonical name"
      screen_side: "left|centre|right"
      depth: "foreground|middle|background"
      scale_relationship: "whole-character relation"
      facing_gaze: "exact relation"
      pose_action_phase: "frame-one state"
      crystal_prop_state: "exact state"
camera:
  framing: "shot size/composition"
  height_angle: "character-relative camera"
  lens_effect: "spatial/emotional result"
  perspective_focus: "depth and focal hierarchy"
motion_readiness:
  begins_after_frame_one: "first action"
  travel_space: "available path"
  not_yet_present: ["later action/payoff/landing"]
production_brief: "copy-ready Seedream brief"
acceptance_tests:
  - "observable pass/fail condition"
approval:
  status: "draft|review|approved|rejected"
  image_path: "saved result"
  image_version: "version/hash"
  known_fragility: "none or precise risk"
seedance_handoff:
  opening_state: "exact visual state"
  action_delta: "what changes in time"
  camera_intent: "inherited shot direction"
  audio_authority: "exact audio IDs"
  required_landing_state: "next handoff"
```

## Human-readable single keyframe pack

```text
KEYFRAME — [ID] — [SHOT/TAKE] — [RATIO/TIER]

UPSTREAM DELIVERY
[locked meaning, POV, decisive instant, withheld information]

REFERENCE AUTHORITY
[@slot = role, controls, exclusions]

SEEDREAM PRODUCTION BRIEF
[copy-ready brief]

ACCEPTANCE GATE
[short objective checklist]

SEEDANCE HANDOFF
[opening state, action delta, camera/audio authority, landing requirement]
```

## Scene batch

Return a compact map first:

`keyframe_id | shot_id | take_id | decisive instant | reference count | operation | status`

Then give one independent record per keyframe. Never combine several shot prompts into one ambiguous brief. Each approved output must be replaceable without rerunning accepted frames.

## Gate states

- `blocked`: incomplete or contradictory upstream contract;
- `ready`: upstream and reference preflight passed;
- `generated`: output exists but is not approved;
- `repair`: bounded correction required;
- `approved`: image and record passed every test;
- `handed_off`: Seedance package received the approved image/version.

Generation is not approval. Approval is not handoff. Record each transition explicitly.
