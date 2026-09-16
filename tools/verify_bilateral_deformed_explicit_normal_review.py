#!/usr/bin/env python3
"""Verify representative deformed explicit-normal target-host lookdev evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

EXPECTED_SCHEMA = "axm.animal-materials-deformed-explicit-normal-review/v0.1"
EXPECTED_RIGGING_HEAD = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
EXPECTED_RIGGING_MODULE_BLOB = "b8df083310727dcd05e7476b2158a081a5c25c8f"
EXPECTED_NORMAL_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
EXPECTED_NORMAL_MODULE_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
EXPECTED_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_TOPOLOGY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
EXPECTED_STATIC_MATERIALS_HEAD = "a2cd0a6135a7c8502aef9572f7079a3dd2632103"
EXPECTED_MODES = ("vertex_generated", "logical_quad_explicit")
EXPECTED_CONTEXTS = ("three_quarter", "grazing")
EXPECTED_VARIANTS = ("historical_right", "exact_mirror_right")
EXPECTED_ANGLES = (-60.0, -30.0, 0.0, 30.0, 60.0)
EXPECTED_WEIGHTINGS = ("smoothstep-v0", "ease-out-power-0p75-v1")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_pose_id(value: str) -> str:
    return value.replace("+", "p").replace("-", "m").replace(".", "p")


def _union_threshold_mask(diff: Image.Image, threshold: int = 1) -> Image.Image:
    channels = diff.convert("RGB").split()
    mask = channels[0].point(lambda value: 255 if value > threshold else 0)
    for channel in channels[1:]:
        candidate = channel.point(lambda value: 255 if value > threshold else 0)
        mask = ImageChops.lighter(mask, candidate)
    return mask


def _presence_mask(image: Image.Image, threshold: int = 3) -> Image.Image:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    return _union_threshold_mask(ImageChops.difference(rgb, background), threshold=threshold)


def _image_presence(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    mask = _presence_mask(rgb)
    foreground_pixels = mask.histogram()[255]
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
    changed_mask = _union_threshold_mask(diff, threshold=1)
    changed_pixels = changed_mask.histogram()[255]
    total = control.width * control.height

    foreground = ImageChops.lighter(_presence_mask(control), _presence_mask(candidate))
    foreground_pixels = foreground.histogram()[255]
    changed_foreground = ImageChops.multiply(changed_mask, foreground).histogram()[255]
    luma_diff = ImageChops.difference(control.convert("L"), candidate.convert("L"))
    mean_abs_foreground_luma = ImageStat.Stat(luma_diff, mask=foreground).mean[0] if foreground_pixels else 0.0

    return {
        "control": control_path.name,
        "candidate": candidate_path.name,
        "width": control.width,
        "height": control.height,
        "total_pixels": total,
        "changed_pixels_gt_1_of_255": changed_pixels,
        "changed_fraction_gt_1_of_255": changed_pixels / float(total),
        "changed_bbox": list(changed_mask.getbbox()) if changed_mask.getbbox() else None,
        "foreground_pixels": foreground_pixels,
        "changed_foreground_pixels_gt_1_of_255": changed_foreground,
        "changed_foreground_fraction_gt_1_of_255": (
            changed_foreground / float(foreground_pixels) if foreground_pixels else 0.0
        ),
        "mean_abs_foreground_luma_0_to_255": mean_abs_foreground_luma,
        "mean_abs_rgb_0_to_255": ImageStat.Stat(diff).mean,
        "control_sha256": _sha256(control_path),
        "candidate_sha256": _sha256(candidate_path),
    }


def _filename(pose_id: str, mode: str, context: str, variant: str) -> str:
    return f"{_safe_pose_id(pose_id)}__{mode}__{context}__{variant}.png"


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
    if payload.get("exact_rigging_donor_head") != EXPECTED_RIGGING_HEAD:
        raise SystemExit("unexpected Rigging donor head")
    if payload.get("exact_rigging_module_blob") != EXPECTED_RIGGING_MODULE_BLOB:
        raise SystemExit("unexpected Rigging module blob")
    if payload.get("exact_static_materials_head") != EXPECTED_STATIC_MATERIALS_HEAD:
        raise SystemExit("unexpected static Materials prerequisite")
    if payload.get("exact_normal_donor_head") != EXPECTED_NORMAL_HEAD:
        raise SystemExit("unexpected normal donor head")
    if payload.get("exact_normal_module_blob") != EXPECTED_NORMAL_MODULE_BLOB:
        raise SystemExit("unexpected normal module blob")
    if payload.get("exact_topology_donor_head") != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit("unexpected topology donor head")
    if payload.get("exact_topology_module_blob") != EXPECTED_TOPOLOGY_MODULE_BLOB:
        raise SystemExit("unexpected topology module blob")
    if payload.get("rigging_prerequisite_state") != "PASS_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_DEFORMATION_DENSE_SWEEPS":
        raise SystemExit("Rigging deformed-normal prerequisite is not PASS")

    budget = payload.get("budget", {})
    if budget.get("historical_exact_positions_identical") is not True:
        raise SystemExit("historical/exact positions are not held")
    if budget.get("historical_exact_index_count_identical") is not True:
        raise SystemExit("triangle budget is not held")
    if int(budget.get("representative_pose_count", -1)) != 10:
        raise SystemExit("unexpected representative pose count")
    if tuple(float(value) for value in budget.get("angles_deg", [])) != EXPECTED_ANGLES:
        raise SystemExit("unexpected representative pose angles")

    if telemetry.get("rigging_head") != EXPECTED_RIGGING_HEAD:
        raise SystemExit("target-host Rigging head mismatch")
    if telemetry.get("rigging_module_blob") != EXPECTED_RIGGING_MODULE_BLOB:
        raise SystemExit("target-host Rigging module blob mismatch")
    if telemetry.get("normal_donor_head") != EXPECTED_NORMAL_HEAD:
        raise SystemExit("target-host normal donor mismatch")
    if telemetry.get("normal_module_blob") != EXPECTED_NORMAL_MODULE_BLOB:
        raise SystemExit("target-host normal module blob mismatch")
    if telemetry.get("topology_donor_head") != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit("target-host topology donor mismatch")
    if telemetry.get("topology_module_blob") != EXPECTED_TOPOLOGY_MODULE_BLOB:
        raise SystemExit("target-host topology module blob mismatch")
    if telemetry.get("rendering_method") != "gl_compatibility":
        raise SystemExit(f"unexpected rendering method: {telemetry.get('rendering_method')}")

    pose_sets = payload.get("pose_sets", [])
    observed_weightings = sorted({str(row["weighting"]) for row in pose_sets})
    if observed_weightings != sorted(EXPECTED_WEIGHTINGS):
        raise SystemExit(f"unexpected weighting identities: {observed_weightings}")
    expected_render_count = len(pose_sets) * len(EXPECTED_MODES) * len(EXPECTED_CONTEXTS) * len(EXPECTED_VARIANTS)
    if int(telemetry.get("render_count", -1)) != expected_render_count:
        raise SystemExit(f"unexpected render count: {telemetry.get('render_count')} expected {expected_render_count}")

    presence = {}
    topology_comparisons = {}
    candidate_mode_shift = {}
    pairwise_reductions = []
    reduced_pairs = 0
    total_pairs = 0

    for pose in pose_sets:
        pose_id = str(pose["pose_id"])
        if pose.get("structural_pose_status") != "PASS":
            raise SystemExit(f"payload pose is not structurally PASS: {pose_id}")
        mirror = pose.get("mirror_provenance", {})
        if mirror.get("gate") != "PASS_EXACT_MIRRORED_POSES_AND_DEFORMED_NORMALS":
            raise SystemExit(f"payload pose lost bilateral provenance: {pose_id}")

        by_mode_context = {}
        for mode in EXPECTED_MODES:
            for context in EXPECTED_CONTEXTS:
                paths = {}
                for variant in EXPECTED_VARIANTS:
                    path = args.renders / _filename(pose_id, mode, context, variant)
                    if not path.is_file():
                        raise SystemExit(f"missing render: {path}")
                    info = _image_presence(Image.open(path))
                    if info["foreground_pixel_count"] < 500:
                        raise SystemExit(f"render appears blank or subject too small: {path}")
                    presence[f"{pose_id}/{mode}/{context}/{variant}"] = info
                    paths[variant] = path
                comparison = _compare(paths["historical_right"], paths["exact_mirror_right"])
                topology_comparisons[f"{pose_id}/{mode}/{context}"] = comparison
                by_mode_context[(mode, context)] = comparison

        for context in EXPECTED_CONTEXTS:
            generated = by_mode_context[("vertex_generated", context)]
            explicit = by_mode_context[("logical_quad_explicit", context)]
            generated_fraction = generated["changed_fraction_gt_1_of_255"]
            explicit_fraction = explicit["changed_fraction_gt_1_of_255"]
            reduction = None if generated_fraction == 0.0 else 1.0 - (explicit_fraction / generated_fraction)
            pairwise_reductions.append(reduction if reduction is not None else 0.0)
            if explicit_fraction < generated_fraction:
                reduced_pairs += 1
            total_pairs += 1

            candidate_mode_shift[f"{pose_id}/{context}/exact_mirror_right"] = _compare(
                args.renders / _filename(pose_id, "vertex_generated", context, "exact_mirror_right"),
                args.renders / _filename(pose_id, "logical_quad_explicit", context, "exact_mirror_right"),
            )

    # Both weighting profiles collapse to the exact same neutral pose. Require render identity there.
    neutral_equivalence = {}
    neutral_by_weighting = {
        str(pose["weighting"]): pose
        for pose in pose_sets
        if float(pose["angle_deg"]) == 0.0
    }
    if set(neutral_by_weighting) != set(EXPECTED_WEIGHTINGS):
        raise SystemExit("missing neutral pose for one or both weighting identities")
    for mode in EXPECTED_MODES:
        for context in EXPECTED_CONTEXTS:
            for variant in EXPECTED_VARIANTS:
                a = args.renders / _filename(neutral_by_weighting[EXPECTED_WEIGHTINGS[0]]["pose_id"], mode, context, variant)
                b = args.renders / _filename(neutral_by_weighting[EXPECTED_WEIGHTINGS[1]]["pose_id"], mode, context, variant)
                same = _sha256(a) == _sha256(b)
                neutral_equivalence[f"{mode}/{context}/{variant}"] = same
                if not same:
                    raise SystemExit(f"neutral weighting render drift: {mode} {context} {variant}")

    generated_values = [
        row["changed_fraction_gt_1_of_255"]
        for key, row in topology_comparisons.items()
        if "/vertex_generated/" in key
    ]
    explicit_values = [
        row["changed_fraction_gt_1_of_255"]
        for key, row in topology_comparisons.items()
        if "/logical_quad_explicit/" in key
    ]
    if reduced_pairs == total_pairs:
        signal = "EXPLICIT_NORMAL_FIELD_REDUCES_TOPOLOGY_SHADING_DELTA_IN_ALL_RETAINED_DEFORMED_CONTEXTS"
    elif reduced_pairs > total_pairs // 2:
        signal = "EXPLICIT_NORMAL_FIELD_REDUCES_TOPOLOGY_SHADING_DELTA_IN_MOST_RETAINED_DEFORMED_CONTEXTS"
    else:
        signal = "EXPLICIT_NORMAL_FIELD_DEFORMED_TOPOLOGY_SHADING_RESPONSE_IS_MIXED_OR_NOT_REDUCED"

    receipt = {
        "schema": "axm.animal-materials-deformed-explicit-normal-review-receipt/v0.1",
        "state": "PASS_TARGET_HOST_DEFORMED_EXPLICIT_NORMAL_REVIEW_CAPTURED",
        "signal": signal,
        "materials_head": args.materials_head,
        "exact_rigging_donor_head": EXPECTED_RIGGING_HEAD,
        "exact_rigging_module_blob": EXPECTED_RIGGING_MODULE_BLOB,
        "exact_static_materials_head": EXPECTED_STATIC_MATERIALS_HEAD,
        "exact_normal_donor_head": EXPECTED_NORMAL_HEAD,
        "exact_normal_module_blob": EXPECTED_NORMAL_MODULE_BLOB,
        "exact_topology_donor_head": EXPECTED_TOPOLOGY_HEAD,
        "exact_topology_module_blob": EXPECTED_TOPOLOGY_MODULE_BLOB,
        "source": payload["source"],
        "budget": payload["budget"],
        "neutral_probe_material": payload["neutral_probe_material"],
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "rendering_device_present": telemetry.get("rendering_device"),
        },
        "presence_checks": presence,
        "topology_comparisons": topology_comparisons,
        "exact_candidate_normal_mode_shift": candidate_mode_shift,
        "neutral_weighting_render_equivalence": neutral_equivalence,
        "summary": {
            "retained_pose_context_pairs": total_pairs,
            "pairs_where_explicit_reduces_topology_delta": reduced_pairs,
            "pairwise_reduction_fraction_min": min(pairwise_reductions),
            "pairwise_reduction_fraction_median": statistics.median(pairwise_reductions),
            "pairwise_reduction_fraction_max": max(pairwise_reductions),
            "maximum_generated_topology_changed_fraction_gt_1_of_255": max(generated_values),
            "maximum_explicit_topology_changed_fraction_gt_1_of_255": max(explicit_values),
        },
        "review_handoff": {
            "materials": "Representative exact Rigging poses are now captured under the existing neutral lookdev harness; this does not assign a production Animal material.",
            "rigging": "The renderer consumes PR #18's exact representative posed positions/normals without changing the rig, weights or deformation observer.",
            "geometry": "Historical versus exact-mirror connectivity remains Geometry-owned; this receipt only reports posed target-host shading response.",
            "art_direction_visual_qa": "Review the retained posed renders for highlight/rolloff continuity, seam/facet emergence and whether the static explicit-normal preference survives deformation.",
            "technical_art": "No production skin-normal or GLB transport is proven; the evidence directly constructs target-host arrays from source-pinned payload data.",
            "runtime": "No target-device frame time, shader, memory, import or controller acceptance is claimed.",
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_textures_decals_checked": False,
            "representative_deformed_shading_captured": True,
            "continuous_deformation_visual_quality_proven": False,
            "tangents_checked": False,
            "production_skin_normal_transport_established": False,
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
    print(f"reduced_pairs={reduced_pairs}/{total_pairs}")
    print(f"pairwise_reduction_min={min(pairwise_reductions):.9f}")
    print(f"pairwise_reduction_median={statistics.median(pairwise_reductions):.9f}")
    print(f"pairwise_reduction_max={max(pairwise_reductions):.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
