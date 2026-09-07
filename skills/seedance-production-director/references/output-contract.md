# Script-to-screen output contract

Use this contract for batches and application integration. Keep unknown values `null`; never infer provider fields.

```json
{
  "status": "production_ready|provisional|blocked_by_missing_assets",
  "blocking_inputs": ["string"],
  "project_id": "string|null",
  "scene_id": "string",
  "scene_purpose": "string",
  "canon_sources": [
    {
      "source_id": "string",
      "title": "string",
      "version": "string|null",
      "sections_used": ["string"]
    }
  ],
  "clips": [
    {
      "clip_id": "string",
      "operation": "base|native_multishot|forward_extension|targeted_edit|conditional_bridge",
      "provider_operation_verified": false,
      "source_pages_or_lines": ["string"],
      "dramatic_beat": "string",
      "duration_seconds": 15,
      "aspect_ratio": "16:9",
      "shot_count": 3,
      "opening_state": {
        "master_video_asset_tag": "string|null",
        "master_approved": "boolean|null",
        "already_true": ["string"],
        "composition": "string",
        "characters": "string",
        "props": "string",
        "continuity": "string",
        "camera_axis_and_motion": "string",
        "lighting": "string",
        "audio_state": "string"
      },
      "reference_contract": [
        {
          "position": 1,
          "asset_tag": "@Image1",
          "asset_id": "string|null",
          "role": "opening_frame|character_identity|location|prop|style|audio|video|closing_frame",
          "controls": "string",
          "does_not_control": "string",
          "scope": "canon|episode|continuity",
          "verified": true
        }
      ],
      "dialogue": [
        {
          "speaker": "string",
          "text_exact": "string",
          "audio_asset_tag": "@Audio1|null"
        }
      ],
      "audio_timing": {
        "audio_asset_tag": "@Audio1|null",
        "approved_version": "string|null",
        "duration_seconds": "number|null",
        "speaker_turns": [
          {
            "speaker": "string",
            "text_exact": "string|null",
            "in_seconds": "number|null",
            "out_seconds": "number|null"
          }
        ],
        "meaningful_pauses": ["string"],
        "dialogue_occupancy_seconds": "number|null",
        "silent_acting_reserve_seconds": "number|null",
        "tail_reserve_seconds": "number|null"
      },
      "prompt": "paste-ready creative prompt",
      "closing_state": {
        "composition": "string",
        "characters": "string",
        "props": "string",
        "continuity": "string",
        "camera_axis_and_motion": "string",
        "lighting": "string",
        "audio_state": "string",
        "next_clip_anchor": "string"
      },
      "qa": {
        "source": "pass|fail|not_applicable",
        "join": "pass|fail|not_applicable",
        "story": "pass|fail",
        "identity_and_scale": "pass|fail",
        "geography_and_performance": "pass|fail",
        "dialogue_and_sound": "pass|fail|not_applicable",
        "handoff": "pass|fail"
      },
      "surgical_safeguards": ["string"],
      "unresolved": ["string"]
    }
  ]
}
```

Do not emit a production prompt when status is `blocked_by_missing_assets`. Use `provisional` only when the user explicitly requests a planning shell, keep unknown values `null`, and label placeholders visibly.

## Layer boundaries

Maintain three distinct layers:

1. **Creative prompt:** cinematic direction written for the model.
2. **Reference contract:** verified asset bindings and their roles.
3. **Provider request:** model ID, duration, ratio, resolution, seed, audio flags, URLs, and other API fields.

Never claim the provider request was sent unless it comes from an actual request record or log. Never embed credentials or signed asset URLs in an output.

## Batch planning

Before writing prompts, present a compact clip map:

| Clip | Dramatic beat | Shots | Duration | Dialogue/audio | Opening anchor | Closing handoff |
|---|---|---:|---:|---|---|---|

Keep shot IDs stable through revisions. When a user asks to repair one failure, preserve the successful parts of the clip record and change only the affected direction, reference, or provider setting.

## Script development and paired prompt supplement

For script intake before all production assets exist, use `development` at package level. This authorises direction, coverage and asset briefs; it does not mean provider prompts or assets are ready. Preserve the existing production clip fields when compiling animation-ready units. Track readiness separately for each deliverable, so missing audio does not block a verified image brief and a missing keyframe does not block its own creation brief.

Use this additional structure when the user requests script-to-screen or paired image/animation output. String alternatives denote enums, not literal values. Keep unknown values null and actual arrays empty until populated.

```json
{
  "package_status": "development|partially_ready|production_ready|blocked_by_missing_assets",
  "script_version": "string|null",
  "scene_id": "string",
  "scene_intent": "string",
  "selected_screen_idea": "string",
  "selection_reason": "string",
  "proposed_script_changes": [],
  "beats": [
    {
      "beat_id": "string",
      "source_lines": [],
      "viewpoint": "string",
      "want_and_tactic": "string",
      "pressure": "string",
      "emotional_before": "string",
      "trigger": "string",
      "emotional_after": "string",
      "visible_evidence": "string",
      "audience_discovery": "string",
      "comic_mechanism": "string|null",
      "consequence": "string",
      "must_see": "string"
    }
  ],
  "scene_plates": [],
  "shots": [
    {
      "shot_id": "string",
      "beat_ids": [],
      "generation_unit_id": "string|null",
      "editorial_order": 1,
      "story_job": "string",
      "camera": {
        "position_and_height": "string",
        "size_angle_lens_feel": "string",
        "axis_side": "string",
        "focal_subject": "string",
        "movement_and_trigger": "string"
      },
      "opening_state": {},
      "action_and_performance": "string",
      "closing_state": {},
      "cut_trigger": "string",
      "join_type": "continuous|intentional_cut|scene_transition",
      "next_shot_id": "string|null",
      "audio": {
        "asset_id": null,
        "source_in_seconds": null,
        "source_out_seconds": null,
        "speaker": null,
        "listener": null,
        "speech_visible_or_offscreen": null,
        "timing_status": "unmeasured|estimated|measured"
      },
      "image": {
        "asset_role": "opening_keyframe|planning_reference|landing_target|inherited_frame",
        "asset_id": null,
        "source_state_shot_id": null,
        "status": "ready|development|blocked_by_missing_assets|not_required",
        "prompt": null,
        "blocking_inputs": []
      },
      "animation": {
        "status": "ready|development|blocked_by_missing_assets",
        "prompt_owner_generation_unit_id": null,
        "blocking_inputs": []
      },
      "pair_qa": "pass|fail|pending"
    }
  ],
  "generation_units": [],
  "review": {
    "type": "paper_reel|boards_inspected|media_inspected",
    "beat_coverage": "pass|fail|pending",
    "emotional_visibility": "pass|fail|pending",
    "geography": "pass|fail|pending",
    "image_animation_match": "pass|fail|pending",
    "timing": "pass|fail|pending",
    "unresolved": []
  }
}
```

Populate `scene_plates` with plate ID, camera view, canon references, light, readiness, prompt or blocking inputs. Populate `opening_state` and `closing_state` using the existing clip state fields. Populate `generation_units` with the existing clip records when ready; during development record ID, ordered shot IDs, planned operation, status, timing basis and blockers. Store each animation prompt once at its generation unit; shots point to it. Internal IDs do not imply uploaded assets or provider slots.

The earlier prohibition on emitting blocked production prompts applies to animation or image deliverables whose own required inputs are missing. It does not prohibit the scene plan, source-grounded image prompts ready independently of audio, or asset creation briefs. Keep incomplete provider prompts withheld unless explicitly requested as provisional. A multi-shot unit may have one generated opening keyframe and additional planning references; do not require one provider-uploaded opening image per internal cut.
