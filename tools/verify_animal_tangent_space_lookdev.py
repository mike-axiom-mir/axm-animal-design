#!/usr/bin/env python3
"""Verify retained real-render tangent-space Materials evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path

from PIL import Image, ImageChops

EXPECTED_SCHEMA = "axm.animal-materials-tangent-space-lookdev/v0.1"
EXPECTED_TELEMETRY_SCHEMA = "axm.animal-materials-tangent-space-lookdev-telemetry/v0.1"
PASS_STATE = "PASS_TARGET_HOST_TANGENT_SPACE_DIAGNOSTIC_CAPTURED"
MODES = ("flat_tangent_control", "periodic_tangent_probe", "flipped_handedness_mutation")
CONTEXTS = ("three_quarter", "grazing")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_id(value: str) -> str:
    return value.replace("+", "p").replace("-", "m").replace(".", "p")


def _image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _difference(left: Image.Image, right: Image.Image) -> dict:
    if left.size != right.size:
        raise SystemExit(f"image size drift: {left.size} vs {right.size}")
    diff = ImageChops.difference(left, right)
    pixels = list(diff.getdata())
    changed = sum(1 for pixel in pixels if max(pixel) > 1)
    total = len(pixels)
    channel_sum = sum(sum(pixel) for pixel in pixels)
    return {
        "changed_pixels_gt_1lsb": changed,
        "total_pixels": total,
        "changed_fraction_gt_1lsb": changed / total,
        "mean_absolute_channel_delta": channel_sum / (total * 3.0),
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
    if telemetry.get("schema") != EXPECTED_TELEMETRY_SCHEMA:
        raise SystemExit("unexpected telemetry schema")
    if telemetry.get("rigging_tangent_head") != payload.get("exact_rigging_tangent_head"):
        raise SystemExit("telemetry Rigging head drift")
    if telemetry.get("geometry_uv_tangent_head") != payload.get("exact_geometry_uv_tangent_head"):
        raise SystemExit("telemetry Geometry head drift")

    expected_count = len(payload["pose_sets"]) * len(CONTEXTS) * len(MODES)
    if int(telemetry.get("render_count", -1)) != expected_count:
        raise SystemExit(f"unexpected render count: {telemetry.get('render_count')} vs {expected_count}")

    records = []
    periodic_fractions = []
    handedness_fractions = []
    image_digests = {}
    for pose in payload["pose_sets"]:
        pose_id = str(pose["pose_id"])
        safe = _safe_id(pose_id)
        for context in CONTEXTS:
            paths = {
                mode: args.renders / f"{safe}__{context}__{mode}.png"
                for mode in MODES
            }
            for mode, path in paths.items():
                if not path.is_file():
                    raise SystemExit(f"missing retained render: {path}")
                image_digests[path.name] = _digest(path)
            flat = _image(paths["flat_tangent_control"])
            probe = _image(paths["periodic_tangent_probe"])
            flipped = _image(paths["flipped_handedness_mutation"])
            probe_delta = _difference(flat, probe)
            handedness_delta = _difference(probe, flipped)
            if probe_delta["changed_pixels_gt_1lsb"] <= 0:
                raise SystemExit(f"tangent-space probe is renderer-invisible: {pose_id}/{context}")
            if handedness_delta["changed_pixels_gt_1lsb"] <= 0:
                raise SystemExit(f"handedness mutation is renderer-invisible: {pose_id}/{context}")
            periodic_fractions.append(probe_delta["changed_fraction_gt_1lsb"])
            handedness_fractions.append(handedness_delta["changed_fraction_gt_1lsb"])
            records.append({
                "pose_id": pose_id,
                "side": pose["side"],
                "weighting": pose["weighting"],
                "angle_deg": pose["angle_deg"],
                "camera_context": context,
                "flat_vs_periodic_probe": probe_delta,
                "periodic_probe_vs_flipped_handedness_mutation": handedness_delta,
            })

    # Neutral pose continuity: the two weighting identities must be byte-identical
    # at 0 degrees for every side, camera and shader mode.
    neutral_checks = []
    weightings = sorted({str(row["weighting"]) for row in payload["pose_sets"]})
    if len(weightings) != 2:
        raise SystemExit("expected exactly two weighting identities")
    for side in ("left", "right"):
        neutral = {
            str(row["weighting"]): str(row["pose_id"])
            for row in payload["pose_sets"]
            if row["side"] == side and float(row["angle_deg"]) == 0.0
        }
        if set(neutral) != set(weightings):
            raise SystemExit(f"missing neutral weighting controls for {side}")
        for context in CONTEXTS:
            for mode in MODES:
                left_name = f"{_safe_id(neutral[weightings[0]])}__{context}__{mode}.png"
                right_name = f"{_safe_id(neutral[weightings[1]])}__{context}__{mode}.png"
                identical = image_digests[left_name] == image_digests[right_name]
                if not identical:
                    raise SystemExit(f"neutral cross-weighting render drift: {side}/{context}/{mode}")
                neutral_checks.append({
                    "side": side,
                    "camera_context": context,
                    "shader_mode": mode,
                    "byte_identical": True,
                })

    result = {
        "schema": "axm.animal-materials-tangent-space-lookdev-evidence/v0.1",
        "state": PASS_STATE,
        "materials_head": args.materials_head,
        "rigging_tangent_head": payload["exact_rigging_tangent_head"],
        "geometry_uv_tangent_head": payload["exact_geometry_uv_tangent_head"],
        "renderer": {
            "godot_version": telemetry.get("godot_version"),
            "rendering_method": telemetry.get("rendering_method"),
            "render_count": expected_count,
        },
        "measurements": {
            "comparison_count": len(records),
            "periodic_probe_changed_fraction_min": min(periodic_fractions),
            "periodic_probe_changed_fraction_median": statistics.median(periodic_fractions),
            "periodic_probe_changed_fraction_max": max(periodic_fractions),
            "handedness_mutation_changed_fraction_min": min(handedness_fractions),
            "handedness_mutation_changed_fraction_median": statistics.median(handedness_fractions),
            "handedness_mutation_changed_fraction_max": max(handedness_fractions),
            "neutral_cross_weighting_byte_identical_count": len(neutral_checks),
        },
        "comparisons": records,
        "neutral_cross_weighting_checks": neutral_checks,
        "signal": "PERIODIC_TANGENT_SPACE_RESPONSE_AND_HANDEDNESS_MUTATION_ARE_RENDERER_VISIBLE_IN_ALL_RETAINED_CONTEXTS",
        "decision_boundary": "CAPTURE_PASS_ONLY__SEAM_HANDEDNESS_AESTHETIC_ACCEPTANCE_REQUIRES_VISUAL_QA_AND_ART_DIRECTION",
        "truth_boundary": {
            "periodic_probe_is_a_production_normal_map": False,
            "final_uv_layout_or_texel_density_accepted": False,
            "seam_artifact_absence_automatically_proven": False,
            "handedness_correctness_visually_final": False,
            "representative_deformed_tangent_space_response_captured": True,
            "harness_detects_deliberate_tangent_w_corruption": True,
            "continuous_motion_visual_quality_proven": False,
            "production_transport_established": False,
            "target_engine_import_equivalence_established": False,
            "art_direction_or_visual_qa_accepted": False,
            "runtime_accepted": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(PASS_STATE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
