"""Deterministic opening-frame blocking for the render path.

This module never calls a media provider. It converts a typed DP layout, the current
scene plate and locked visual sources into deterministic 16:9 frames whose pixel
geometry can be inspected before and after a paid keyframe request.
"""
from __future__ import annotations

import copy
import io
import math
import pathlib
from typing import Any

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import linear_sum_assignment


class LayoutError(RuntimeError):
    pass


PRODUCTION_FRAME_RATIO = 16 / 9
PRODUCTION_FRAME_MIN = (1280, 720)
# The widest crop the studio will make on a supplied plate without a human re-framing it:
# a 3:2 image (ChatGPT/Midjourney's default) loses 15% of its height to a 16:9 frame and is
# accepted; a 4:3 loses 25% and is the limit; anything squarer or a portrait is refused.
PLATE_CROP_RATIO_RANGE = (4 / 3, 2.4)


def conform_plate_to_production_frame(source_path, out_path=None):
    """Make a supplied scene plate a production frame (2026-09-02, The Box Monsters S2).

    Julian's plates come from ChatGPT at 2496x1664 (3:2); `render_composition_master`
    refused them ("scene plate must be a widescreen production frame") at the keyframe step,
    after the plate had been approved. The frame is settled ONCE, at intake, so the
    approved plate, the provider's world reference and the composition proof are all the
    same 16:9 image: a centre crop to 16:9, never a stretch, never a letterbox. A plate that
    already is a production frame is copied unchanged. Refuses a plate whose crop would lose
    more than a quarter of its height (squarer than 4:3), a portrait, or one smaller than
    1280x720 after the crop — that needs a human to re-frame, not a silent crop.

    Returns {"path", "cropped", "sourceSize", "size"}.
    """
    source_path = pathlib.Path(source_path)
    out_path = pathlib.Path(out_path) if out_path else source_path
    with Image.open(source_path) as source:
        width, height = source.size
        ratio = width / max(height, 1)
        if 1.70 <= ratio <= 1.85:
            if out_path != source_path:
                out_path.write_bytes(source_path.read_bytes())
            return {"path": str(out_path), "cropped": False,
                    "sourceSize": [width, height], "size": [width, height]}
        low, high = PLATE_CROP_RATIO_RANGE
        if not low <= ratio <= high:
            raise LayoutError(
                f"scene plate is {width}x{height} ({ratio:.2f}:1) — too far from the 16:9 "
                f"production frame to crop; supply a landscape image between 4:3 and 2.4:1")
        if ratio > PRODUCTION_FRAME_RATIO:
            crop_width = int(round(height * PRODUCTION_FRAME_RATIO))
            offset = (width - crop_width) // 2
            box = (offset, 0, offset + crop_width, height)
        else:
            crop_height = int(round(width / PRODUCTION_FRAME_RATIO))
            offset = (height - crop_height) // 2
            box = (0, offset, width, offset + crop_height)
        frame = source.crop(box)
        if frame.width < PRODUCTION_FRAME_MIN[0] or frame.height < PRODUCTION_FRAME_MIN[1]:
            raise LayoutError(
                f"scene plate is {width}x{height}; its 16:9 crop {frame.width}x{frame.height} "
                f"is below the {PRODUCTION_FRAME_MIN[0]}x{PRODUCTION_FRAME_MIN[1]} production minimum")
        if source.mode not in ("RGB", "RGBA"):
            frame = frame.convert("RGB")
        suffix = out_path.suffix.lower()
        fmt = {"jpg": "JPEG", "jpeg": "JPEG", "webp": "WEBP"}.get(suffix.lstrip("."), "PNG")
        if fmt == "JPEG" and frame.mode == "RGBA":
            frame = frame.convert("RGB")
        frame.save(out_path, format=fmt, **({"quality": 95} if fmt == "JPEG" else {}))
        return {"path": str(out_path), "cropped": True,
                "sourceSize": [width, height], "size": [frame.width, frame.height]}


def _front_view_crop(image: Image.Image) -> Image.Image:
    """Take the first full-body view from the canonical four-view turnaround sheet."""
    width, height = image.size
    if width / max(height, 1) < 1.35:
        return image.convert("RGBA")
    return image.crop((
        int(width * 0.015), int(height * 0.12),
        int(width * 0.30), int(height * 0.89),
    )).convert("RGBA")


def _largest_alpha_subject(image: Image.Image) -> Image.Image:
    """Remove detached sheet marks while preserving the connected character silhouette."""
    rgba = np.asarray(image.convert("RGBA")).copy()
    mask = rgba[:, :, 3] > 12
    labelled, count = ndimage.label(mask)
    if count < 1:
        raise LayoutError("turnaround background removal produced no visible subject")
    sizes = np.bincount(labelled.ravel())
    sizes[0] = 0
    subject = labelled == int(sizes.argmax())
    subject = ndimage.binary_dilation(subject, iterations=1)
    rgba[:, :, 3] = np.where(subject, rgba[:, :, 3], 0)
    cleaned = Image.fromarray(rgba, "RGBA")
    bbox = cleaned.getbbox()
    if not bbox:
        raise LayoutError("turnaround subject has no usable alpha bounds")
    return cleaned.crop(bbox)


def character_cutout(turnaround_path: str | pathlib.Path) -> Image.Image:
    """Create a full-body transparent blocking cutout from a locked turnaround."""
    from rembg import remove

    with Image.open(turnaround_path) as source:
        crop = _front_view_crop(source)
    isolated = remove(crop)
    if not isinstance(isolated, Image.Image):
        isolated = Image.open(io.BytesIO(isolated))
    return _largest_alpha_subject(isolated.convert("RGBA"))


def _rendered_character_cutout(character: dict[str, Any], target_axis_height: int,
                               angle: float) -> Image.Image:
    """Build the exact transformed cutout used by layout fitting and rendering."""
    cutout = character_cutout(character["turnaroundPath"])
    resized_width = max(1, int(round(
        cutout.width * target_axis_height / cutout.height)))
    cutout = cutout.resize(
        (resized_width, target_axis_height), Image.Resampling.LANCZOS)
    if angle:
        cutout = cutout.rotate(
            angle, resample=Image.Resampling.BICUBIC, expand=True)
    return cutout


def posed_character_cutout(pose_path: str | pathlib.Path) -> Image.Image:
    """Remove a pose plate's background without treating it as a turnaround sheet.

    Pose references are deliberately generated or uploaded as one isolated full-body
    character. Cropping them with ``_front_view_crop`` would discard a diagonal flight
    pose, which is the exact failure the pose-first workflow exists to prevent.
    """
    from rembg import remove

    with Image.open(pose_path) as source:
        isolated = remove(source.convert("RGBA"))
    if not isinstance(isolated, Image.Image):
        isolated = Image.open(io.BytesIO(isolated))
    return _largest_alpha_subject(isolated.convert("RGBA"))


def _foreground_alpha(image: Image.Image) -> np.ndarray:
    from rembg import remove

    isolated = remove(image.convert("RGBA"))
    if not isinstance(isolated, Image.Image):
        isolated = Image.open(io.BytesIO(isolated))
    return np.asarray(isolated.convert("RGBA"))[:, :, 3]


def validate_layout(layout: dict[str, Any], characters: dict[str, dict[str, Any]]) -> None:
    placements = layout.get("placements") or []
    names = [str(item.get("character") or "") for item in placements]
    if not names or len(names) != len(set(names)):
        raise LayoutError("layout requires one unique placement per character")
    if set(names) != set(characters):
        raise LayoutError(
            "layout cast does not exactly match the shot cast: "
            f"expected {sorted(characters)}, got {sorted(names)}")
    reference = layout.get("referenceCharacter")
    if reference not in characters:
        raise LayoutError("layout reference character is not in the shot cast")
    for name, item in characters.items():
        try:
            if float(item["heightIn"]) <= 0:
                raise ValueError
        except (KeyError, TypeError, ValueError) as exc:
            raise LayoutError(f"{name} has no valid canonical heightIn") from exc

    if layout.get("sameDepth"):
        planes = {int(item.get("depthPlane", 0)) for item in placements}
        scales = {float(item.get("apparentScale", 1.0)) for item in placements}
        if len(planes) != 1 or scales != {1.0}:
            raise LayoutError(
                "same-depth layout must use one depth plane and apparentScale=1.0")

    reference_fraction = float(layout.get("referenceHeightFraction", 0))
    if not 0.18 <= reference_fraction <= 0.55:
        raise LayoutError("referenceHeightFraction must be between 0.18 and 0.55")
    reference_height = float(characters[reference]["heightIn"])
    for placement in placements:
        name = placement["character"]
        apparent = float(placement.get("apparentScale", 1.0))
        fraction = (reference_fraction * float(characters[name]["heightIn"]) /
                    reference_height * apparent)
        centre_y = float(placement["centerY"])
        if centre_y - fraction / 2 < 0.02 or centre_y + fraction / 2 > 0.98:
            raise LayoutError(f"{name} would be vertically cropped by the authored layout")


def fit_frame_safety(layout: dict[str, Any],
                     characters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Clamp centres so transformed cutouts remain inside the production frame."""
    fitted = copy.deepcopy(layout)
    reference = fitted.get("referenceCharacter")
    reference_height = float((characters.get(reference) or {}).get("heightIn") or 0)
    reference_fraction = float(fitted.get("referenceHeightFraction") or 0)
    if reference_height <= 0:
        validate_layout(fitted, characters)
        return fitted
    frame_width, frame_height = 2048, 1152
    desired_reference_pixels = frame_height * reference_fraction
    pixels_per_inch = max(1, int(round(
        desired_reference_pixels / reference_height)))
    for placement in fitted.get("placements") or []:
        name = placement.get("character")
        character = characters.get(name) or {}
        height = float(character.get("heightIn") or 0)
        apparent = float(placement.get("apparentScale", 1.0))
        fraction = reference_fraction * height / reference_height * apparent
        target_axis_height = int(round(pixels_per_inch * height * apparent))
        angle = float(placement.get("bodyAngleDegrees", 0.0))
        transformed = _rendered_character_cutout(
            character, target_axis_height, angle)
        horizontal_half = transformed.width / (2 * frame_width)
        vertical_half = transformed.height / (2 * frame_height)
        x_lower, x_upper = 0.02 + horizontal_half, 0.98 - horizontal_half
        y_lower = max(0.02 + fraction / 2, 0.02 + vertical_half)
        y_upper = min(0.98 - fraction / 2, 0.98 - vertical_half)
        if x_lower > x_upper or y_lower > y_upper:
            raise LayoutError(f"{name} cannot fit in frame at the authored apparent scale")
        placement["centerX"] = round(
            min(max(float(placement["centerX"]), x_lower), x_upper), 4)
        placement["centerY"] = round(
            min(max(float(placement["centerY"]), y_lower), y_upper), 4)
    validate_layout(fitted, characters)
    return fitted


def render_composition_master(
        plate_path: str | pathlib.Path,
        characters: dict[str, dict[str, Any]],
        layout: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Render the exact blocking proof and return PNG bytes plus measured geometry."""
    validate_layout(layout, characters)
    with Image.open(plate_path) as source:
        frame = source.convert("RGBA")
    width, height = frame.size
    if width < 1280 or height < 720 or not 1.70 <= width / height <= 1.85:
        raise LayoutError(
            f"scene plate must be a widescreen production frame; got {width}x{height}")
    target_ratio = 16 / 9
    if width / height > target_ratio:
        crop_width = int(round(height * target_ratio))
        offset = (width - crop_width) // 2
        frame = frame.crop((offset, 0, offset + crop_width, height))
    elif width / height < target_ratio:
        crop_height = int(round(width / target_ratio))
        offset = (height - crop_height) // 2
        frame = frame.crop((0, offset, width, offset + crop_height))
    frame = frame.resize((2048, 1152), Image.Resampling.LANCZOS)
    width, height = frame.size

    reference = layout["referenceCharacter"]
    reference_height = float(characters[reference]["heightIn"])
    desired_reference_pixels = height * float(layout["referenceHeightFraction"])
    pixels_per_inch = max(1, int(round(desired_reference_pixels / reference_height)))
    reference_pixels = int(round(reference_height * pixels_per_inch))
    rendered = []
    ordered = sorted(
        enumerate(layout["placements"]),
        key=lambda pair: (int(pair[1].get("depthPlane", 0)), pair[0]))
    for _, placement in ordered:
        name = placement["character"]
        character = characters[name]
        target_axis_height = int(round(
            pixels_per_inch * float(character["heightIn"]) *
            float(placement.get("apparentScale", 1.0))))
        angle = float(placement.get("bodyAngleDegrees", 0.0))
        cutout = _rendered_character_cutout(character, target_axis_height, angle)

        centre_x = int(round(float(placement["centerX"]) * width))
        centre_y = int(round(float(placement["centerY"]) * height))
        left = centre_x - cutout.width // 2
        top = centre_y - cutout.height // 2
        right, bottom = left + cutout.width, top + cutout.height
        if left < 0 or top < 0 or right > width or bottom > height:
            raise LayoutError(f"{name} would be cropped after its authored body angle")
        frame.alpha_composite(cutout, (left, top))
        rendered.append({
            "character": name,
            "targetStandingHeightPx": target_axis_height,
            "renderedBoundsPx": [left, top, right, bottom],
            "centrePx": [centre_x, centre_y],
            "centreNormalized": [float(placement["centerX"]),
                                 float(placement["centerY"])],
            "bodyAngleDegrees": angle,
            "depthPlane": int(placement.get("depthPlane", 0)),
            "apparentScale": float(placement.get("apparentScale", 1.0)),
        })

    encoded = io.BytesIO()
    frame.convert("RGB").save(encoded, format="PNG", optimize=True)
    return encoded.getvalue(), {
        "frameSize": [width, height],
        "referenceCharacter": reference,
        "referenceStandingHeightPx": reference_pixels,
        "sameDepth": bool(layout.get("sameDepth")),
        "characters": rendered,
    }


def render_posed_integration_frame(
        plate_path: str | pathlib.Path,
        characters: dict[str, dict[str, Any]],
        layout: dict[str, Any],
        pose_paths: dict[str, str | pathlib.Path]) -> tuple[bytes, dict[str, Any]]:
    """Assemble approved character poses over the plate at the authored geometry.

    Unlike :func:`render_composition_master`, this frame contains the approved acting
    poses rather than pasted turnaround figures. It is therefore a creative precursor
    that an image editor may polish, while the turnaround-based composition master stays
    local and remains the independent geometry QA target.
    """
    validate_layout(layout, characters)
    missing = sorted(set(characters) - set(pose_paths))
    if missing:
        raise LayoutError(
            "approved pose reference missing for " + ", ".join(missing))

    with Image.open(plate_path) as source:
        frame = source.convert("RGBA")
    width, height = frame.size
    if width < 1280 or height < 720 or not 1.70 <= width / height <= 1.85:
        raise LayoutError(
            f"scene plate must be a widescreen production frame; got {width}x{height}")
    target_ratio = 16 / 9
    if width / height > target_ratio:
        crop_width = int(round(height * target_ratio))
        offset = (width - crop_width) // 2
        frame = frame.crop((offset, 0, offset + crop_width, height))
    elif width / height < target_ratio:
        crop_height = int(round(width / target_ratio))
        offset = (height - crop_height) // 2
        frame = frame.crop((0, offset, width, offset + crop_height))
    frame = frame.resize((2048, 1152), Image.Resampling.LANCZOS)
    width, height = frame.size

    reference = layout["referenceCharacter"]
    reference_height = float(characters[reference]["heightIn"])
    desired_reference_pixels = height * float(layout["referenceHeightFraction"])
    pixels_per_inch = max(1, int(round(desired_reference_pixels / reference_height)))
    rendered = []
    ordered = sorted(
        enumerate(layout["placements"]),
        key=lambda pair: (int(pair[1].get("depthPlane", 0)), pair[0]))
    for _, placement in ordered:
        name = placement["character"]
        target_height = int(round(
            pixels_per_inch * float(characters[name]["heightIn"]) *
            float(placement.get("apparentScale", 1.0))))
        cutout = posed_character_cutout(pose_paths[name])
        target_width = max(1, int(round(cutout.width * target_height / cutout.height)))
        cutout = cutout.resize((target_width, target_height), Image.Resampling.LANCZOS)

        centre_x = int(round(float(placement["centerX"]) * width))
        centre_y = int(round(float(placement["centerY"]) * height))
        left = centre_x - cutout.width // 2
        top = centre_y - cutout.height // 2
        right, bottom = left + cutout.width, top + cutout.height
        if left < 0 or top < 0 or right > width or bottom > height:
            raise LayoutError(f"{name}'s approved pose would be cropped by the layout")
        frame.alpha_composite(cutout, (left, top))
        rendered.append({
            "character": name,
            "sourcePose": pathlib.Path(pose_paths[name]).name,
            "targetStandingHeightPx": target_height,
            "renderedBoundsPx": [left, top, right, bottom],
            "centrePx": [centre_x, centre_y],
            "centreNormalized": [float(placement["centerX"]),
                                 float(placement["centerY"])],
            "authoredBodyAngleDegrees": float(
                placement.get("bodyAngleDegrees", 0.0)),
            "depthPlane": int(placement.get("depthPlane", 0)),
            "apparentScale": float(placement.get("apparentScale", 1.0)),
        })

    encoded = io.BytesIO()
    frame.convert("RGB").save(encoded, format="PNG", optimize=True)
    return encoded.getvalue(), {
        "frameSize": [width, height],
        "referenceCharacter": reference,
        "sameDepth": bool(layout.get("sameDepth")),
        "characters": rendered,
        "source": "approved-character-poses",
    }


def screen_candidate_geometry(
        candidate_path: str | pathlib.Path,
        composition_record: dict[str, Any]) -> dict[str, Any]:
    """Catch gross position and scale drift locally before a keyframe can be approved.

    This is deliberately a geometry screen, not an identity or artistic-quality verdict.
    It uses foreground segmentation and matches visible components to the authored layout.
    """
    geometry = composition_record.get("geometry") or {}
    expected = geometry.get("characters") or []
    if not expected:
        return {"status": "unavailable", "reason": "composition geometry is missing"}
    try:
        with Image.open(candidate_path) as source:
            image = source.convert("RGBA")
        width, height = image.size
        alpha = _foreground_alpha(image)
    except Exception as exc:
        return {"status": "unavailable", "reason": f"foreground screening failed: {exc}"}

    mask = alpha > 32
    labelled, count = ndimage.label(mask)
    sizes = np.bincount(labelled.ravel())
    objects = ndimage.find_objects(labelled)
    frame_area = width * height
    components = []
    for index, bounds in enumerate(objects, start=1):
        if bounds is None:
            continue
        top, bottom = bounds[0].start, bounds[0].stop
        left, right = bounds[1].start, bounds[1].stop
        box_width, box_height = right - left, bottom - top
        area = int(sizes[index])
        if (area < frame_area * 0.0025 or box_height < height * 0.08 or
                box_width < width * 0.035):
            continue
        components.append({
            "areaPx": area,
            "boundsPx": [left, top, right, bottom],
            "centerNormalized": [(left + right) / 2 / width,
                                 (top + bottom) / 2 / height],
            "heightFraction": box_height / height,
        })
    components.sort(key=lambda item: item["areaPx"], reverse=True)
    components = components[:max(12, len(expected) * 4)]
    if len(components) < len(expected):
        return {
            "status": "fail", "reason": "not enough distinct foreground subjects",
            "expectedSubjects": len(expected), "detectedSubjects": len(components),
            "candidateSize": [width, height],
        }

    master_width, master_height = geometry.get("frameSize") or [2048, 1152]
    costs = np.zeros((len(expected), len(components)), dtype=float)
    for row, target in enumerate(expected):
        expected_x, expected_y = target["centreNormalized"]
        bounds = target["renderedBoundsPx"]
        expected_height = (bounds[3] - bounds[1]) / master_height
        for column, component in enumerate(components):
            actual_x, actual_y = component["centerNormalized"]
            distance = math.hypot(actual_x - expected_x, actual_y - expected_y)
            size_delta = abs(math.log(max(component["heightFraction"], 1e-6) /
                                      max(expected_height, 1e-6)))
            costs[row, column] = distance * 2.0 + size_delta * 0.7
    rows, columns = linear_sum_assignment(costs)
    matches = []
    passed = True
    for row, column in zip(rows, columns):
        target = expected[int(row)]
        component = components[int(column)]
        expected_x, expected_y = target["centreNormalized"]
        actual_x, actual_y = component["centerNormalized"]
        position_delta = math.hypot(actual_x - expected_x, actual_y - expected_y)
        bounds = target["renderedBoundsPx"]
        expected_height = (bounds[3] - bounds[1]) / master_height
        height_scale = component["heightFraction"] / expected_height
        item_passed = position_delta <= 0.12 and 0.75 <= height_scale <= 1.25
        passed = passed and item_passed
        matches.append({
            "character": target["character"],
            "passed": item_passed,
            "positionDelta": round(position_delta, 4),
            "heightScaleAgainstLayout": round(height_scale, 4),
            "expectedCenter": [expected_x, expected_y],
            "actualCenter": [round(actual_x, 4), round(actual_y, 4)],
            "expectedHeightFraction": round(expected_height, 4),
            "actualHeightFraction": round(component["heightFraction"], 4),
            "detectedBoundsPx": component["boundsPx"],
        })
    return {
        "status": "pass" if passed else "fail",
        "reason": ("all subjects are within authored position and size tolerances"
                   if passed else
                   "one or more subjects drifted outside authored position or size tolerances"),
        "candidateSize": [width, height],
        "positionTolerance": 0.12,
        "heightScaleTolerance": [0.75, 1.25],
        "matches": matches,
        "detectedComponentCount": len(components),
        "method": "local-u2net-foreground-geometry-v1",
        "zeroSpend": True,
        "providerCalled": False,
    }
