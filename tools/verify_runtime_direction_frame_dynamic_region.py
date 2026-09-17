#!/usr/bin/env python3
"""Fail-closed verifier for the bounded Animal persistent dynamic-region Runtime probe."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "axm.animal-runtime-direction-frame-dynamic-region/v0.1"
STATE = "PASS_ANIMAL_GODOT_DYNAMIC_VERTEX_DIRECTION_REGION_UPDATE__SURFACE_REBUILDS_41_TO_0__HOLD_SHADED_DEVICE"
EXPECTED_KEYS = 41
EXPECTED_VERTICES = 84
EXPECTED_INDICES = 240
EXPECTED_SURFACE_REDUCTION_PERCENT = 40.0 / 41.0 * 100.0


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


def _verify_readback(metrics: dict, label: str, *, require_exact: bool = False) -> None:
    if metrics.get("frames") != EXPECTED_KEYS:
        raise ValueError(f"{label} readback frame count drift")
    position = _finite(metrics.get("maximum_position_vector_delta"), f"{label} position delta")
    normal = _finite(metrics.get("maximum_normal_vector_delta"), f"{label} normal delta")
    normal_angle = _finite(metrics.get("maximum_normal_angle_deg"), f"{label} normal angle")
    tangent = _finite(metrics.get("maximum_tangent_vector_delta"), f"{label} tangent delta")
    tangent_angle = _finite(metrics.get("maximum_tangent_angle_deg"), f"{label} tangent angle")
    uv = _finite(metrics.get("maximum_uv_delta"), f"{label} UV delta")
    if position > 1e-6 or normal > 0.00025 or normal_angle > 0.015 or tangent > 0.00025 or tangent_angle > 0.015 or uv > 1e-6:
        raise ValueError(f"{label} exceeds retained Technical Art receiving tolerances")
    if metrics.get("tangent_w_mismatch_count") != 0 or metrics.get("index_mismatch_count") != 0:
        raise ValueError(f"{label} tangent/index mismatch")
    if require_exact and any(value != 0.0 for value in (position, normal, normal_angle, tangent, tangent_angle, uv)):
        raise ValueError(f"{label} is not exact-array identical")


def verify(result: dict) -> None:
    if result.get("schema") != SCHEMA:
        raise ValueError("Runtime dynamic-region schema drift")
    if result.get("state") != STATE:
        raise ValueError("Runtime dynamic-region state is not the exact bounded PASS")

    target = _mapping(result.get("target_host"), "target_host")
    if target.get("engine") != "Godot":
        raise ValueError("target host is not Godot")

    scope = _mapping(result.get("scope"), "scope")
    if scope.get("side") != "right" or scope.get("authored_keys") != EXPECTED_KEYS:
        raise ValueError("bounded right-side 41-key scope drift")
    if scope.get("vertices_per_frame") != EXPECTED_VERTICES or scope.get("indices_per_frame") != EXPECTED_INDICES:
        raise ValueError("vertex/index domain drift")
    if scope.get("topology_changes") is not False or scope.get("uv_or_index_changes") is not False:
        raise ValueError("dynamic candidate changed fixed topology/static attributes")

    before = _mapping(result.get("before"), "before")
    after = _mapping(result.get("after"), "after")
    if before.get("arraymesh_resource_constructions_to_establish_receiver") != 1:
        raise ValueError("pass-40 baseline must already preserve one ArrayMesh")
    if before.get("surface_constructions_to_establish_41_key_receiver") != EXPECTED_KEYS:
        raise ValueError("baseline surface-construction count drift")
    if before.get("surface_rebuilds_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("baseline does not reproduce the remaining pass-40 surface cost")
    if after.get("arraymesh_resource_constructions_to_establish_receiver") != 1:
        raise ValueError("candidate lost persistent ArrayMesh identity")
    if after.get("surface_constructions_to_establish_41_key_receiver") != 1:
        raise ValueError("candidate does not establish one persistent surface")
    if after.get("surface_rebuilds_per_41_key_playback") != 0:
        raise ValueError("candidate still rebuilds surfaces during playback")
    if after.get("update_vertex_region_calls_per_key") != 2 or after.get("update_vertex_region_calls_per_41_key_playback") != EXPECTED_KEYS * 2:
        raise ValueError("candidate dynamic-region call count drift")
    for key in (
        "persistent_arraymesh_identity",
        "persistent_surface_identity",
        "dynamic_update_flag_retained",
        "position_and_direction_regions_only",
        "uv_and_index_regions_unchanged",
    ):
        if after.get(key) is not True:
            raise ValueError(f"candidate lost required invariant: {key}")
    reduction = _finite(after.get("surface_construction_reduction_percent"), "surface construction reduction")
    if abs(reduction - EXPECTED_SURFACE_REDUCTION_PERCENT) > 1e-9:
        raise ValueError("surface-construction reduction arithmetic drift")

    layout = _mapping(result.get("buffer_layout"), "buffer_layout")
    vertex_stride = layout.get("vertex_stride_bytes")
    direction_stride = layout.get("normal_tangent_stride_bytes")
    position_bytes = layout.get("position_region_bytes_per_key")
    direction_bytes = layout.get("direction_region_bytes_per_key")
    bytes_per_key = layout.get("dynamic_region_bytes_per_key")
    bytes_per_playback = layout.get("dynamic_region_bytes_per_41_key_playback")
    cached_bytes = layout.get("cached_dynamic_payload_bytes")
    for value, label in (
        (vertex_stride, "vertex stride"),
        (direction_stride, "direction stride"),
        (position_bytes, "position region bytes"),
        (direction_bytes, "direction region bytes"),
        (bytes_per_key, "dynamic bytes per key"),
        (bytes_per_playback, "dynamic bytes per playback"),
        (cached_bytes, "cached payload bytes"),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")
    if position_bytes != vertex_stride * EXPECTED_VERTICES:
        raise ValueError("position-region byte accounting drift")
    if direction_bytes != direction_stride * EXPECTED_VERTICES:
        raise ValueError("direction-region byte accounting drift")
    if bytes_per_key != position_bytes + direction_bytes:
        raise ValueError("dynamic byte-per-key arithmetic drift")
    if bytes_per_playback != bytes_per_key * EXPECTED_KEYS or cached_bytes != bytes_per_playback:
        raise ValueError("cached/playback byte accounting drift")

    envelope = _mapping(result.get("motion_envelope"), "motion_envelope")
    if envelope.get("custom_aabb_used") is not True or envelope.get("all_41_keys_included") is not True:
        raise ValueError("persistent surface lacks full-motion culling envelope")
    for key in (
        "envelope_volume",
        "minimum_frame_aabb_volume",
        "median_frame_aabb_volume",
        "maximum_frame_aabb_volume",
        "envelope_vs_median_frame_volume_ratio",
    ):
        if _finite(envelope.get(key), f"motion_envelope.{key}") <= 0.0:
            raise ValueError(f"motion_envelope.{key} must be positive")
    if "conservative" not in str(envelope.get("tradeoff", "")):
        raise ValueError("culling-envelope tradeoff was not retained")

    readback = _mapping(result.get("readback"), "readback")
    _verify_readback(_mapping(readback.get("surface_rebuild_baseline"), "surface rebuild baseline"), "surface rebuild baseline")
    _verify_readback(_mapping(readback.get("dynamic_region_candidate"), "dynamic region candidate"), "dynamic region candidate")
    _verify_readback(_mapping(readback.get("candidate_vs_baseline"), "candidate vs baseline"), "candidate vs baseline", require_exact=True)

    timing = _mapping(result.get("proof_host_timing"), "proof_host_timing")
    baseline_median = _finite(timing.get("baseline_median_sweep_us"), "baseline median")
    candidate_median = _finite(timing.get("candidate_median_sweep_us"), "candidate median")
    baseline_p95 = _finite(timing.get("baseline_p95_sweep_us"), "baseline p95")
    candidate_p95 = _finite(timing.get("candidate_p95_sweep_us"), "candidate p95")
    ratio_gate = _finite(timing.get("median_ratio_gate"), "median ratio gate")
    if min(baseline_median, candidate_median, baseline_p95, candidate_p95) <= 0.0:
        raise ValueError("timing observations must be positive")
    if candidate_median > baseline_median * ratio_gate:
        raise ValueError("dynamic-region candidate did not beat the surface-rebuild median")
    if timing.get("warmup_rounds") != 5 or timing.get("measured_rounds") != 31 or timing.get("keys_per_round") != EXPECTED_KEYS:
        raise ValueError("timing protocol drift")
    if timing.get("target_device_claimed") is not False:
        raise ValueError("proof-host timing was relabelled as target-device evidence")

    visual = _mapping(result.get("visual_tradeoff"), "visual_tradeoff")
    if visual.get("receiver_array_result") != "EXACT_ARRAY_IDENTITY_ALL_41_KEYS":
        raise ValueError("visual receiving-array identity is not exact")
    if visual.get("fresh_shaded_render_run") is not False:
        raise ValueError("fresh shaded rendering was overclaimed")
    if visual.get("art_review_state") != "HOLD_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW":
        raise ValueError("Art review hold drift")

    truth = _mapping(result.get("truth_boundary"), "truth_boundary")
    for key in (
        "technical_art_packet_changed",
        "owner_reconstructed_positions_normals_tangents_changed",
        "universal_creation_modified",
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
    for key in (
        "persistent_arraymesh_resource_proved",
        "persistent_surface_buffer_update_proved",
        "dynamic_region_update_proved",
        "static_uv_index_proved",
    ):
        if truth.get(key) is not True:
            raise ValueError(f"truth boundary failed to prove {key}")


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
