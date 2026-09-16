#!/usr/bin/env python3
"""Verify the target-host explicit logical-quad normal review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

EXPECTED_SCHEMA = "axm.animal-materials-explicit-logical-quad-normal-review/v0.1"
EXPECTED_NORMAL_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
EXPECTED_NORMAL_MODULE_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
EXPECTED_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_TOPOLOGY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
EXPECTED_MODES = ("vertex_generated", "logical_quad_explicit")
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
    if payload.get("exact_normal_donor_head") != EXPECTED_NORMAL_HEAD:
        raise SystemExit("unexpected explicit-normal donor head")
    if payload.get("exact_normal_module_blob") != EXPECTED_NORMAL_MODULE_BLOB:
        raise SystemExit("unexpected explicit-normal module blob")
    if payload.get("exact_topology_donor_head") != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit("unexpected topology donor head")
    if payload.get("exact_topology_module_blob") != EXPECTED_TOPOLOGY_MODULE_BLOB:
        raise SystemExit("unexpected topology module blob")
    budget = payload.get("budget", {})
    if budget.get("positions_identical") is not True:
        raise SystemExit("positions are not held identical")
    if budget.get("index_count_identical") is not True:
        raise SystemExit("triangle budget is not held identical")
    if budget.get("explicit_normal_vectors_identical") is not True:
        raise SystemExit("explicit normal vectors are not held identical across topology variants")
    if int(budget.get("explicit_normal_count", -1)) != int(budget.get("vertex_count", -2)):
        raise SystemExit("explicit normal count does not match vertex count")

    if telemetry.get("normal_donor_head") != EXPECTED_NORMAL_HEAD:
        raise SystemExit("target-host telemetry explicit-normal donor mismatch")
    if telemetry.get("normal_module_blob") != EXPECTED_NORMAL_MODULE_BLOB:
        raise SystemExit("target-host telemetry explicit-normal blob mismatch")
    if telemetry.get("topology_donor_head") != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit("target-host telemetry topology donor mismatch")
    if telemetry.get("topology_module_blob") != EXPECTED_TOPOLOGY_MODULE_BLOB:
        raise SystemExit("target-host telemetry topology blob mismatch")
    if telemetry.get("rendering_method") != "gl_compatibility":
        raise SystemExit(f"unexpected rendering method: {telemetry.get('rendering_method')}")
    if int(telemetry.get("render_count", -1)) != 8:
        raise SystemExit(f"unexpected render count: {telemetry.get('render_count')}")

    presence = {}
    topology_comparisons = {}
    candidate_shift = {}
    for mode in EXPECTED_MODES:
        for context in EXPECTED_CONTEXTS:
            variant_paths = {}
            for variant in EXPECTED_VARIANTS:
                path = args.renders / f"{mode}-{context}-{variant}.png"
                if not path.is_file():
                    raise SystemExit(f"missing render: {path}")
                info = _image_presence(Image.open(path))
                if info["foreground_pixel_count"] < 500:
                    raise SystemExit(f"render appears blank or subject too small: {path}")
                presence[f"{mode}/{context}/{variant}"] = info
                variant_paths[variant] = path
            topology_comparisons[f"{mode}/{context}"] = _compare(
                variant_paths["historical_right"], variant_paths["exact_mirror_right"]
            )

    for context in EXPECTED_CONTEXTS:
        for variant in EXPECTED_VARIANTS:
            candidate_shift[f"{context}/{variant}"] = _compare(
                args.renders / f"vertex_generated-{context}-{variant}.png",
                args.renders / f"logical_quad_explicit-{context}-{variant}.png",
            )

    generated_fractions = [
        topology_comparisons[f"vertex_generated/{context}"]["changed_fraction_gt_1_of_255"]
        for context in EXPECTED_CONTEXTS
    ]
    explicit_fractions = [
        topology_comparisons[f"logical_quad_explicit/{context}"]["changed_fraction_gt_1_of_255"]
        for context in EXPECTED_CONTEXTS
    ]
    generated_max = max(generated_fractions)
    explicit_max = max(explicit_fractions)
    reduction_fraction = None if generated_max == 0.0 else 1.0 - (explicit_max / generated_max)

    if explicit_max == 0.0:
        signal = "EXPLICIT_NORMAL_FIELD_REMOVES_THRESHOLD_TOPOLOGY_DELTA_IN_RETAINED_CONTEXTS"
    elif explicit_max < generated_max:
        signal = "EXPLICIT_NORMAL_FIELD_REDUCES_TOPOLOGY_SHADING_DELTA_IN_RETAINED_CONTEXTS"
    else:
        signal = "EXPLICIT_NORMAL_FIELD_DOES_NOT_REDUCE_TOPOLOGY_SHADING_DELTA_IN_RETAINED_CONTEXTS"

    receipt = {
        "schema": "axm.animal-materials-explicit-logical-quad-normal-review-receipt/v0.1",
        "state": "PASS_TARGET_HOST_EXPLICIT_LOGICAL_QUAD_NORMAL_REVIEW_CAPTURED",
        "signal": signal,
        "materials_head": args.materials_head,
        "exact_normal_donor_head": EXPECTED_NORMAL_HEAD,
        "exact_normal_module_blob": EXPECTED_NORMAL_MODULE_BLOB,
        "exact_topology_donor_head": EXPECTED_TOPOLOGY_HEAD,
        "exact_topology_module_blob": EXPECTED_TOPOLOGY_MODULE_BLOB,
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
        "topology_comparisons": topology_comparisons,
        "exact_candidate_normal_mode_shift": candidate_shift,
        "summary": {
            "maximum_generated_topology_changed_fraction_gt_1_of_255": generated_max,
            "maximum_explicit_topology_changed_fraction_gt_1_of_255": explicit_max,
            "explicit_vs_generated_max_delta_reduction_fraction": reduction_fraction,
        },
        "review_handoff": {
            "materials": "This review tests Geometry PR #16's exact explicit normal field under the neutral Materials harness; it does not assign a production Animal material.",
            "geometry": "Structural normal-field invariants remain Geometry-owned; this receipt only reports target-host shading response.",
            "art_direction_visual_qa": "Judge the retained explicit-normal appearance and whether residual topology response is acceptable; Materials does not convert measured reduction into aesthetic acceptance.",
            "rigging": "Static explicit-normal response does not establish deformed-normal quality under the Rigging envelope.",
            "technical_art": "No UC/GLB transport of this exact explicit field is proven by this review.",
            "runtime": "No target-device frame time, draw-call, shader, memory or import acceptance is claimed.",
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_textures_decals_checked": False,
            "explicit_normal_candidate_tested": True,
            "tangents_checked": False,
            "deformation_acceptance_claimed": False,
            "transport_acceptance_claimed": False,
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
    print(f"generated_max_changed_fraction={generated_max:.9f}")
    print(f"explicit_max_changed_fraction={explicit_max:.9f}")
    if reduction_fraction is not None:
        print(f"max_delta_reduction_fraction={reduction_fraction:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
