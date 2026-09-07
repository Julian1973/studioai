# Layer Decomposition

Use only after an image is approved or when a defined layered workflow genuinely benefits downstream production. It is not the default keyframe-generation method.

## Confirmed BytePlus preview behaviour

- enable with `layer_decomposition: true` on the documented image-generation endpoint;
- exactly one input image is required; multiple inputs return an error;
- output contains one base image plus up to 16 layers;
- if any layer fails, the whole request fails; partial success is not returned;
- a prompt is optional: omit for automatic major-element separation, name elements for semantic separation, or target regions with verified coordinate tags;
- the base image follows the selected output format; separated layers are PNG;
- returned items are ordered by increasing `z_index`, with base fixed at 0;
- layers include `bounding_box`, `name` and `description`;
- bounding boxes include absolute pixel coordinates and normalised per-mille-style coordinates;
- preserve the complete stack order and placement metadata for reassembly.

Preview-documented input constraints include a supported raster format, up to 30 MB, bounded pixel count and broad aspect-ratio range. Verify the current public documentation before implementation.

## Useful Crystal Bears applications

- separate a character or foreground prop for a controlled downstream composite;
- isolate atmospheric foreground, middle-ground character and background plate for parallax tests;
- preserve an approved background while repairing one foreground element;
- create editable marketing or layout variants from approved art;
- deliver transparent elements to a compositor while retaining the original approved flattened keyframe.

## Do not use when

- a normal flattened keyframe is all Seedance needs;
- the proposed layers would encourage moving subjects away from approved shot blocking;
- transparency in the downstream video workflow is unverified;
- the frame has not passed identity, composition and continuity QA;
- the request assumes decomposition will automatically prevent identity drift.

## Layer package record

Preserve:

- source image ID/version and approval state;
- exact decomposition prompt and target regions;
- base image;
- every layer file;
- `z_index`;
- absolute and normalised bounding boxes;
- layer name and description;
- output size and format;
- reassembly canvas dimensions;
- checksum/version for every file;
- recomposition verification result.

Never replace the approved flattened keyframe with a recomposed image until pixel alignment, edges, transparency, stack order and appearance have been verified.

## Unsupported in the preview mode

The preview document states that sequential image generation, sequential-generation options, tools/web search and streaming are unsupported in layer-decomposition mode. Keep those fields out of that payload unless current public documentation supersedes the preview.
