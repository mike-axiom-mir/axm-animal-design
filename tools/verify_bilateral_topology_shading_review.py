#!/usr/bin/env python3
"""Verify and summarize the target-host bilateral topology shading review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

EXPECTED_SCHEMA = "axm.animal-materials-bilateral-topology-shading-review/v0.1"
EXPECTED_GEOMETRY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_GEOMETRY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
EXPECTED_MODES = ("face_split", "vertex_smooth")
EXPECTED_CONTEXTS = ("three_quarter", "grazing")
EXPECTED_VARIANTS = ("historical_right", "exact_mirror_right")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _union_threshold_mask(diff: Image.Image, threshold: int = 1) -> Image.Image:
    channels = diff.convert("RGB").split()
    mask = channels[0].point(lambda value: 255 if value > threshold else 0)
    for channel in channels[1:]:
        candidate = channel.point(lambda value: 255 if value > threshold else 0)
        mask = ImageChops.lighter(mask, candidate)
    return mask


def _image_presence(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, background)
    mask = _union_threshold_mask(diff, threshold=3)
    histogram = mask.histogram()
    foreground_pixels = histogram[255]
    return {
        "background_reference_rgb": list(rgb.getpixel((0, 0))),
        "foreground_pixel_count": foreground_pixels,
        "foreground_fraction": foreground_pixels / float(rgb.width * rgb.height),
        "foreground_bbox": list(mask.getbbox()) if mask.getbbox() else None,
        "channel_variance": ImageStat.Stat(rgb).var,
    }


def _compare(control_path: Path, candidate_path: Path) -> dict:
    control = Image.open(control_path).convert("RGB")
    candidate = Image.open(candidate_path).convert("RGB")
    if control.size != candidate.size:
        raise SystemExit(f"render size mismatch: {control.size} vs {candidate.size}")
    diff = ImageChops.difference(control, candidate)
    mask = _union_threshold_mask(diff, threshold=1)
    hist = mask.histogram()
    changed_pixels = hist[255]
    total = control.width * control.height
    mean_abs = ImageStat.Stat(diff).mean
    return {
        "control": control_path.name,
        "candidate": candidate_path.name,
        "width": control.width,
        "height": control.height,
        "total_pixels": total,
        "changed_pixels_gt_1_of_255": changed_pixels,
        "changed_fraction_gt_1_of_255": changed_pixels / float(total),
        "changed_bbox": list(mask.getbbox()) if mask.getbbox() else None,
        "mean_abs_rgb_0_to_255": mean_abs,
        "mean_abs_rgb_normalized": [value / 255.0 for value in mean_abs],
        "control_sha256": _sha256(control_path),
        "candidate_sha256": _sha256(candidate_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--renders", required=True, type=Path)
    parser.add_argument("--materials-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    payload = _load(args.payload)
    telemetry = _load(args.telemetry)
    if payload.get("schema") != EXPECTED_SCHEMA:
        raise SystemExit("unexpected payload schema")
    if payload.get("exact_geometry_donor_head") != EXPECTED_GEOMETRY_HEAD:
        raise SystemExit("unexpected Geometry donor head")
    if payload.get("exact_geometry_module_blob") != EXPECTED_GEOMETRY_MODULE_BLOB:
        raise SystemExit("unexpected Geometry module blob")
    if payload.get("budget", {}).get("positions_identical") is not True:
        raise SystemExit("positions are not held identical")
    if payload.get("budget", {}).get("index_count_identical") is not True:
        raise SystemExit("triangle budget is not held identical")
    if telemetry.get("geometry_donor_head") != EXPECTED_GEOMETRY_HEAD:
        raise SystemExit("target-host telemetry donor head mismatch")
    if telemetry.get("geometry_module_blob") != EXPECTED_GEOMETRY_MODULE_BLOB:
        raise SystemExit("target-host telemetry donor blob mismatch")
    if telemetry.get("rendering_method") != "gl_compatibility":
        raise SystemExit(f"unexpected rendering method: {telemetry.get('rendering_method')}")
    if int(telemetry.get("render_count", -1)) != 8:
        raise SystemExit(f"unexpected render count: {telemetry.get('render_count')}")

    presence = {}
    comparisons = {}
    max_changed_fraction = 0.0
    max_mean_abs = 0.0
    for mode in EXPECTED_MODES:
        for context in EXPECTED_CONTEXTS:
            key = f"{mode}/{context}"
            variant_paths = {}
            for variant in EXPECTED_VARIANTS:
                path = args.renders / f"{mode}-{context}-{variant}.png"
                if not path.is_file():
                    raise SystemExit(f"missing render: {path}")
                info = _image_presence(Image.open(path))
                if info["foreground_pixel_count"] < 500:
                    raise SystemExit(f"render appears blank or subject too small: {path}")
                presence[f"{key}/{variant}"] = info
                variant_paths[variant] = path
            result = _compare(variant_paths["historical_right"], variant_paths["exact_mirror_right"])
            comparisons[key] = result
            max_changed_fraction = max(max_changed_fraction, result["changed_fraction_gt_1_of_255"])
            max_mean_abs = max(max_mean_abs, max(result["mean_abs_rgb_normalized"]))

    if max_changed_fraction == 0.0:
        signal = "NO_THRESHOLD_PIXEL_DELTA_IN_RETAINED_CONTEXTS"
    elif max_changed_fraction < 0.005 and max_mean_abs < 0.0025:
        signal = "LOW_RENDERER_DELTA_RETAIN_FOR_REVIEW"
    else:
        signal = "MATERIAL_SHADING_DELTA_REQUIRES_REVIEW"

    receipt = {
        "schema": "axm.animal-materials-bilateral-topology-shading-review-receipt/v0.1",
        "state": "PASS_TARGET_HOST_BILATERAL_TOPOLOGY_SHADING_REVIEW_CAPTURED",
        "signal": signal,
        "materials_head": args.materials_head,
        "exact_geometry_donor_head": EXPECTED_GEOMETRY_HEAD,
        "exact_geometry_module_blob": EXPECTED_GEOMETRY_MODULE_BLOB,
        "source": payload["source"],
        "budget": payload["budget"],
        "neutral_probe_material": payload["neutral_probe_material"],
        "normal_modes": list(EXPECTED_MODES),
        "camera_contexts": list(EXPECTED_CONTEXTS),
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "rendering_device_present": telemetry.get("rendering_device"),
        },
        "presence_checks": presence,
        "comparisons": comparisons,
        "summary": {
            "maximum_changed_fraction_gt_1_of_255": max_changed_fraction,
            "maximum_mean_abs_channel_delta_normalized": max_mean_abs,
        },
        "review_handoff": {
            "materials": "This probe isolates connectivity under one neutral material and two generated-normal modes; it does not assign a production Animal material.",
            "geometry": "If the exact-mirror topology advances, retain this renderer evidence because diagonal choice can alter generated-normal shading even when positions and budgets are unchanged.",
            "art_direction_visual_qa": "Judge any visible shading delta from the retained renders; Materials does not silently aesthetic-accept the topology.",
            "runtime": "No target-device frame time, draw-call, memory, import, or shader-cost acceptance is claimed.",
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_textures_decals_checked": False,
            "authored_normals_tangents_checked": False,
            "deformation_acceptance_claimed": False,
            "target_device_performance_claimed": False,
            "final_visual_acceptance_claimed": False,
            "canon_claimed": False,
            "production_readiness_claimed": False,
            "materials_mastery_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(receipt["state"])
    print(signal)
    print(f"max_changed_fraction={max_changed_fraction:.9f}")
    print(f"max_mean_abs_channel_delta={max_mean_abs:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
