# Script-to-screen output contract

Use this contract for batches and application integration. Keep unknown values `null`; never infer provider fields.

The public interchange vocabulary is snake_case. Versioned extension records are validated by
`engine.cb_seedance_contract.ExtensionContract`; internal application camelCase must cross that
typed adapter rather than being copied or renamed ad hoc.

```json
{
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
