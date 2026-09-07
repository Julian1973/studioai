# Seedream 5 Pro Technical Reference

Source basis: user-supplied BytePlus Seedream 5.0 Pro preview and layer-decomposition parameters, cross-checked against the current Seedream 5 Pro image-director specification. Preview values may change; the active provider documentation wins.

## Confirmed production capabilities

- text and image generation/editing with strong spatial and regional understanding;
- multi-image fusion and identity/feature preservation workflows;
- interactive editing using points, boxes, lassos, arrows, sketches and annotated regions where the host exposes them;
- improved film/TV image production and complex layout handling;
- optional layer decomposition from one approved source image;
- multilingual text/layout capability, although story keyframes should normally contain no generated text.

These capabilities improve control; they do not remove the need for canonical references, human approval or bounded repair.

## Host separation

Keep creative direction separate from technical payloads. BytePlus, ModelArk, Volcengine, Dreamina and third-party hosts may expose different model IDs, input limits, sizes and editing controls.

Before emitting technical fields, verify:

- active host and endpoint;
- model ID/alias;
- supported reference count;
- supported generation/edit operation;
- resolution tiers and aspect ratio handling;
- output format;
- coordinate syntax;
- layer-decomposition availability.

Do not invent a button, field, seed, strength, CFG value or hidden quality setting.

## Current working guidance

For the currently documented ModelArk/BytePlus workflows:

- generation may accept text-only, one image or several reference images;
- the documented multi-image workflow supports up to 10 references;
- standard output tiers include 1K, 1.5K and 2K;
- use 1.5K for economical review and 2K for approved final keyframes where available;
- standard generation returns one image per request in the verified workflow;
- use JPEG for ordinary flattened review images and PNG when lossless edges or transparency matter;
- save accepted results and metadata immediately because returned URLs may expire.

Reverify exact values when production moves to a different host or model revision.

## Coordinate-led editing

Documented coordinate tags include:

- point: `<point>x y</point>`
- box: `<bbox>x1 y1 x2 y2</bbox>`

The documented canvas uses a normalised 0-999/1000-style coordinate space depending on the workflow. Confirm the active endpoint before emitting coordinates. Always include the semantic target and invariant list; coordinates alone are not a preservation contract.

## Keyframe defaults

- story frame: 16:9;
- draft/review: 1.5K where supported;
- approved master: 2K where supported;
- flattened keyframe: JPEG or PNG according to downstream need;
- no text, caption, UI, watermark or logo unless explicitly required;
- one independently approved image per keyframe/shot record.

## Claims not to make without re-verification

- universal 4K output;
- a universal reference count across hosts;
- guaranteed character consistency across a series;
- guaranteed pixel-perfect edits;
- guaranteed transparent output from ordinary generation;
- web search availability;
- batch-consistent image sets from one request;
- fixed price, latency or quota;
- layer decomposition eliminating Seedance drift.
