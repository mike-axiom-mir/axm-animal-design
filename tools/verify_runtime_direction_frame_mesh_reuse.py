#!/usr/bin/env python3
"""Fail-closed verifier for the bounded Animal ArrayMesh resource-reuse probe."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "axm.animal-runtime-direction-frame-mesh-reuse/v0.1"
STATE = "PASS_ANIMAL_GODOT_ARRAYMESH_RESOURCE_REUSE_41_TO_1__HOLD_DYNAMIC_REGION_SHADED_DEVICE"
EXPECTED_KEYS = 41
EXPECTED_VERTICES = 84
EXPECTED_INDICES = 240
EXPECTED_RESOURCE_REDUCTION_PERCENT = 40.0 / 41.0 * 100.0


def _mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _finite(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def verify(result: dict) -> None:
    if result.get("schema") != SCHEMA:
        raise ValueError("Runtime mesh-reuse schema drift")
    if result.get("state") != STATE:
        raise ValueError("Runtime mesh-reuse state is not the exact bounded PASS")

    target = _mapping(result.get("target_host"), "target_host")
    if target.get("engine") != "Godot":
        raise ValueError("target host is not Godot")
    scope = _mapping(result.get("scope"), "scope")
    if scope.get("side") != "right":
        raise ValueError("bounded receiver side drift")
    if scope.get("authored_keys") != EXPECTED_KEYS:
        raise ValueError("authored key count drift")
    if scope.get("vertices_per_frame") != EXPECTED_VERTICES:
        raise ValueError("vertex count drift")
    if scope.get("indices_per_frame") != EXPECTED_INDICES:
        raise ValueError("index count drift")
    if scope.get("topology_changes") is not False or scope.get("uv_or_index_changes") is not False:
        raise ValueError("candidate changed topology/UV/index scope")

    before = _mapping(result.get("before"), "before")
    after = _mapping(result.get("after"), "after")
    if before.get("arraymesh_resource_constructions_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("baseline ArrayMesh construction count drift")
    if after.get("arraymesh_resource_constructions_per_41_key_playback") != 1:
        raise ValueError("candidate does not preserve one ArrayMesh resource")
    if before.get("surface_constructions_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("baseline surface construction count drift")
    if after.get("surface_constructions_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("candidate silently changed the surface-rebuild boundary")
    if after.get("persistent_arraymesh_identity") is not True:
        raise ValueError("persistent ArrayMesh identity not proved")
    if after.get("surface_buffer_rebuild_eliminated") is not False:
        raise ValueError("surface-buffer rebuild was overclaimed")
    reduction = _finite(after.get("resource_construction_reduction_percent"), "resource reduction")
    if abs(reduction - EXPECTED_RESOURCE_REDUCTION_PERCENT) > 1e-9:
        raise ValueError("ArrayMesh construction reduction arithmetic drift")

    readback = _mapping(result.get("readback"), "readback")
    for lane in ("baseline", "candidate"):
        metrics = _mapping(readback.get(lane), f"readback.{lane}")
        if metrics.get("frames") != EXPECTED_KEYS:
            raise ValueError(f"{lane} readback frame count drift")
        if _finite(metrics.get("maximum_position_vector_delta"), f"{lane} position delta") > 1e-6:
            raise ValueError(f"{lane} position readback exceeds bound")
        if _finite(metrics.get("maximum_normal_vector_delta"), f"{lane} normal delta") > 0.00025:
            raise ValueError(f"{lane} normal readback exceeds vector bound")
        if _finite(metrics.get("maximum_normal_angle_deg"), f"{lane} normal angle") > 0.015:
            raise ValueError(f"{lane} normal readback exceeds angle bound")
        if _finite(metrics.get("maximum_tangent_vector_delta"), f"{lane} tangent delta") > 0.00025:
            raise ValueError(f"{lane} tangent readback exceeds vector bound")
        if _finite(metrics.get("maximum_tangent_angle_deg"), f"{lane} tangent angle") > 0.015:
            raise ValueError(f"{lane} tangent readback exceeds angle bound")
        if _finite(metrics.get("maximum_uv_delta"), f"{lane} UV delta") > 1e-6:
            raise ValueError(f"{lane} UV readback exceeds bound")
        if metrics.get("tangent_w_mismatch_count") != 0:
            raise ValueError(f"{lane} tangent handedness mismatch")
        if metrics.get("index_mismatch_count") != 0:
            raise ValueError(f"{lane} index mismatch")

    timing = _mapping(result.get("proof_host_timing"), "proof_host_timing")
    baseline_median = _finite(timing.get("baseline_median_sweep_us"), "baseline median")
    candidate_median = _finite(timing.get("candidate_median_sweep_us"), "candidate median")
    guard = _finite(timing.get("median_regression_guard_ratio"), "median guard")
    if baseline_median <= 0.0 or candidate_median <= 0.0:
        raise ValueError("timing medians must be positive")
    if candidate_median > baseline_median * guard:
        raise ValueError("candidate exceeds retained proof-host timing guard")
    if timing.get("target_device_claimed") is not False:
        raise ValueError("proof-host timing was relabelled as target-device evidence")

    truth = _mapping(result.get("truth_boundary"), "truth_boundary")
    if truth.get("technical_art_packet_changed") is not False:
        raise ValueError("Technical Art packet was changed")
    if truth.get("owner_reconstructed_positions_normals_tangents_changed") is not False:
        raise ValueError("owner frame arrays were changed")
    if truth.get("universal_creation_modified") is not False:
        raise ValueError("Universal Creation was modified")
    if truth.get("persistent_arraymesh_resource_proved") is not True:
        raise ValueError("persistent ArrayMesh resource gate is not proved")
    for key in (
        "persistent_surface_buffer_update_proved",
        "dynamic_region_update_proved",
        "bilateral_runtime_proved",
        "continuous_interpolated_playback_proved",
        "fresh_shaded_render_proved",
        "target_device_cpu_gpu_fps_vram_proved",
        "art_direction_acceptance_claimed",
        "visual_qa_acceptance_claimed",
        "canon_claimed",
        "production_ready",
    ):
        if truth.get(key) is not False:
            raise ValueError(f"truth boundary overclaims {key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    result = json.loads(args.result.read_text(encoding="utf-8"))
    verify(result)
    print(STATE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
