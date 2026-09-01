# Seedance 2.5 official capability boundary

Use this reference to distinguish verified model capabilities from studio practice and provider-specific controls.

## Verified by ByteDance Seed

As of 26 August 2026, ByteDance's official Seedance 2.5 launch material states that the model:

- generates audio-video clips up to 30 seconds in one pass;
- supports multi-round extension and appending subsequent shots to existing outputs;
- can organise multiple logically connected shots within a generation;
- accepts up to 30 images, 10 video clips and 10 audio clips in one pass;
- supports multimodal character, environment, prop, motion, creative and clay-render referencing;
- supports timestamp-level generation control and targeted video/audio editing;
- supports reference-led camera perspective and green-screen editing;
- improves continuity of main subjects, environments, narrative pacing, shot transitions and audiovisual synchronisation.

ByteDance also acknowledges remaining difficulty with physical plausibility in complex motion and stability in multi-subject interactions. Never describe the model as guaranteeing continuity.

## Official example pattern for extension

ByteDance's published R2V example begins by telling the model to extend the video, continue from the visuals and subjects in the tagged video, and keep subjects, scene, visual style and sound effects consistent. Follow that principle while adding only production-specific state needed by the current beat.

## Provider discipline

The model capability is not the same as a particular interface. Verify current provider documentation or visible controls before asserting:

- the name or existence of an Extend/Continue button;
- how many extension rounds that route permits;
- resolution, aspect ratio, duration or pricing;
- seed support;
- reference-strength controls;
- task-type fields;
- upload trimming or maximum input length;
- API model names, request fields or availability.

Keep provider settings outside the creative prompt. Use null for unknown structured fields.

## Studio methods, not model facts

The following are disciplined production practices rather than official Seedance guarantees:

- one generation equals one dramatic beat;
- one to three shots per beat;
- 6–15 seconds as a conservative recurring-animation working range;
- using the extracted final frame primarily for QA;
- two or three identity anchors at a risk point;
- a 17/20 internal quality threshold;
- refusal to extend an unapproved master;
- one grading pass across a chained sequence.

Present them as recommendations, never official limits.

## Conditional operations

Forward extension is officially demonstrated. Do not call backward extension or two-clip bridging a native Seedance 2.5 feature unless the selected provider exposes and documents it. When asked for either:

1. verify provider support;
2. if supported, follow its actual operation;
3. otherwise construct the result as reference-led generation/editing or separate editorial assembly;
4. declare one sole geography and continuity master;
5. describe the method accurately rather than labelling it native extension.

## Primary sources

- ByteDance Seed, One-take Creation, Flexible Referencing: Introducing Seedance 2.5, 31 July 2026: https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5
- ByteDance Seed, Seedance 2.5 model page: https://seed.bytedance.com/en/seedance2_5
