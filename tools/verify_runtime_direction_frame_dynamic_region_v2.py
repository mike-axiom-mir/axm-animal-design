#!/usr/bin/env python3
"""Fail-closed verifier for Animal engine-packed persistent vertex-region Runtime evidence."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "axm.animal-runtime-direction-frame-dynamic-region/v0.2"
STATE = "PASS_ANIMAL_GODOT_ENGINE_PACKED_VERTEX_REGION_UPDATE__SURFACE_REBUILDS_41_TO_0__HOLD_SHADED_DEVICE"
EXPECTED_KEYS = 41
EXPECTED_VERTICES = 84
EXPECTED_INDICES = 240
EXPECTED_FAILED_HEAD = "fbc9c8a86daa299c6a3bf2b9aa421cf30b01df41"
EXPECTED_FAILED_RUN = 35267861278
EXPECTED_FAILED_ARTIFACT = 10516719596
EXPECTED_FAILED_SHA = "a00a9af5192bc7c923e1f4a1891faa7880a3c47eec263d82c1e04e664eaf7413"


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


def _verify_readback(metrics: dict, label: str, *, exact: bool = False) -> None:
    if metrics.get("frames") != EXPECTED_KEYS:
        raise ValueError(f"{label}: expected all 41 frames")
    values = {
        "position": _finite(metrics.get("maximum_position_vector_delta"), f"{label} position"),
        "normal": _finite(metrics.get("maximum_normal_vector_delta"), f"{label} normal"),
        "normal_angle": _finite(metrics.get("maximum_normal_angle_deg"), f"{label} normal angle"),
        "tangent": _finite(metrics.get("maximum_tangent_vector_delta"), f"{label} tangent"),
        "tangent_angle": _finite(metrics.get("maximum_tangent_angle_deg"), f"{label} tangent angle"),
        "uv": _finite(metrics.get("maximum_uv_delta"), f"{label} uv"),
    }
    if exact:
        if any(value != 0.0 for value in values.values()):
            raise ValueError(f"{label}: not exact-array identical")
    else:
        if values["position"] > 1e-6:
            raise ValueError(f"{label}: position tolerance exceeded")
        if values["normal"] > 0.00025 or values["normal_angle"] > 0.015:
            raise ValueError(f"{label}: normal tolerance exceeded")
        if values["tangent"] > 0.00025 or values["tangent_angle"] > 0.015:
            raise ValueError(f"{label}: tangent tolerance exceeded")
        if values["uv"] > 1e-6:
            raise ValueError(f"{label}: UV tolerance exceeded")
    if metrics.get("tangent_w_mismatch_count") != 0 or metrics.get("index_mismatch_count") != 0:
        raise ValueError(f"{label}: tangent-W/index mismatch")


def verify(result: dict) -> None:
    if result.get("schema") != SCHEMA or result.get("state") != STATE:
        raise ValueError("exact bounded Runtime PASS missing")

    target = _mapping(result.get("target_host"), "target_host")
    if target.get("engine") != "Godot" or "4.7.2" not in str(target.get("version", "")):
        raise ValueError("target host/version drift")

    scope = _mapping(result.get("scope"), "scope")
    if scope.get("side") != "right" or scope.get("authored_keys") != EXPECTED_KEYS:
        raise ValueError("right-side 41-key scope drift")
    if scope.get("vertices_per_frame") != EXPECTED_VERTICES or scope.get("indices_per_frame") != EXPECTED_INDICES:
        raise ValueError("mesh domain drift")
    if scope.get("topology_changes") is not False or scope.get("uv_or_index_changes") is not False:
        raise ValueError("fixed topology/static UV-index precondition lost")

    before = _mapping(result.get("before"), "before")
    after = _mapping(result.get("after"), "after")
    if before.get("arraymesh_resource_constructions_per_41_key_playback") != 1:
        raise ValueError("baseline must start at pass-40 one-ArrayMesh state")
    if before.get("surface_rebuilds_per_41_key_playback") != EXPECTED_KEYS or before.get("surface_constructions_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("baseline no longer represents 41 surface rebuilds")
    if after.get("arraymesh_resource_constructions_per_41_key_playback") != 1:
        raise ValueError("candidate lost persistent ArrayMesh")
    if after.get("surface_rebuilds_per_41_key_playback") != 0:
        raise ValueError("candidate still rebuilds surfaces")
    if after.get("surface_constructions_to_establish_receiver") != 1:
        raise ValueError("candidate must establish exactly one surface")
    if _finite(after.get("surface_rebuild_reduction_percent"), "surface rebuild reduction") != 100.0:
        raise ValueError("surface rebuild reduction arithmetic drift")
    expected_construction_reduction = 40.0 / 41.0 * 100.0
    if abs(_finite(after.get("surface_construction_reduction_percent"), "surface construction reduction") - expected_construction_reduction) > 1e-9:
        raise ValueError("surface construction reduction arithmetic drift")
    if after.get("vertex_region_updates_per_key") != 1 or after.get("vertex_region_updates_per_41_key_playback") != EXPECTED_KEYS:
        raise ValueError("candidate vertex-region update count drift")
    for key in ("persistent_arraymesh_identity", "persistent_surface_identity", "dynamic_update_flag_retained", "uv_and_index_buffers_untouched"):
        if after.get(key) is not True:
            raise ValueError(f"candidate invariant failed: {key}")

    cache = _mapping(result.get("engine_packed_vertex_cache"), "engine_packed_vertex_cache")
    if cache.get("manual_private_vertex_encoding_reimplemented") is not False:
        raise ValueError("candidate silently reintroduced private manual packing")
    per_key = cache.get("raw_vertex_bytes_per_key")
    all_keys = cache.get("cached_raw_vertex_bytes_all_41_keys")
    initial = cache.get("candidate_initial_vertex_bytes")
    if not isinstance(per_key, int) or isinstance(per_key, bool) or per_key <= 0:
        raise ValueError("raw vertex bytes/key invalid")
    if all_keys != per_key * EXPECTED_KEYS or initial != per_key:
        raise ValueError("engine-packed cache accounting drift")
    if cache.get("payload_size_matches_candidate") is not True:
        raise ValueError("engine-packed payload/candidate layout mismatch")
    if cache.get("preparation_cost_in_timed_playback_sweeps") is not False:
        raise ValueError("preparation cost timing boundary drift")

    envelope = _mapping(result.get("motion_envelope"), "motion_envelope")
    if envelope.get("custom_aabb_used") is not True or envelope.get("all_41_keys_included") is not True:
        raise ValueError("full-motion culling envelope missing")
    for key in ("envelope_volume", "minimum_frame_aabb_volume", "median_frame_aabb_volume", "maximum_frame_aabb_volume", "envelope_vs_median_frame_volume_ratio"):
        if _finite(envelope.get(key), f"motion_envelope.{key}") <= 0.0:
            raise ValueError(f"invalid motion envelope field: {key}")
    if "culling" not in str(envelope.get("tradeoff", "")):
        raise ValueError("culling tradeoff not recorded")

    readback = _mapping(result.get("readback"), "readback")
    _verify_readback(_mapping(readback.get("surface_rebuild_baseline"), "baseline"), "baseline")
    _verify_readback(_mapping(readback.get("engine_packed_region_candidate"), "candidate"), "candidate")
    _verify_readback(_mapping(readback.get("candidate_vs_baseline"), "candidate_vs_baseline"), "candidate_vs_baseline", exact=True)
    if readback.get("candidate_vs_baseline_exact") is not True:
        raise ValueError("exact candidate-vs-baseline flag missing")

    timing = _mapping(result.get("proof_host_timing"), "proof_host_timing")
    if timing.get("warmup_rounds") != 5 or timing.get("measured_rounds") != 31 or timing.get("keys_per_round") != EXPECTED_KEYS:
        raise ValueError("timing protocol drift")
    baseline_median = _finite(timing.get("baseline_median_sweep_us"), "baseline median")
    candidate_median = _finite(timing.get("candidate_median_sweep_us"), "candidate median")
    baseline_p95 = _finite(timing.get("baseline_p95_sweep_us"), "baseline p95")
    candidate_p95 = _finite(timing.get("candidate_p95_sweep_us"), "candidate p95")
    ratio = _finite(timing.get("median_ratio_gate"), "median ratio gate")
    if min(baseline_median, candidate_median, baseline_p95, candidate_p95) <= 0.0:
        raise ValueError("timing observations must be positive")
    if candidate_median > baseline_median * ratio:
        raise ValueError("candidate did not beat baseline median")
    if timing.get("target_device_claimed") is not False:
        raise ValueError("proof-host timing relabelled as target-device evidence")

    visual = _mapping(result.get("visual_tradeoff"), "visual_tradeoff")
    if visual.get("receiver_array_result") != "EXACT_ARRAY_IDENTITY_ALL_41_KEYS":
        raise ValueError("receiver-array visual input identity not exact")
    if visual.get("fresh_shaded_render_run") is not False:
        raise ValueError("fresh shaded A/B overclaimed")
    if visual.get("art_review_state") != "HOLD_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW":
        raise ValueError("Art review hold drift")

    predecessor = _mapping(result.get("failed_predecessor_preserved"), "failed_predecessor_preserved")
    if predecessor.get("runtime_head") != EXPECTED_FAILED_HEAD or predecessor.get("workflow_run") != EXPECTED_FAILED_RUN:
        raise ValueError("failed predecessor identity drift")
    if predecessor.get("artifact_id") != EXPECTED_FAILED_ARTIFACT or predecessor.get("artifact_sha256") != EXPECTED_FAILED_SHA:
        raise ValueError("failed predecessor artifact identity drift")
    if "diverged" not in str(predecessor.get("failure", "")):
        raise ValueError("failed predecessor reason not retained")

    truth = _mapping(result.get("truth_boundary"), "truth_boundary")
    for key in ("persistent_arraymesh_resource_proved", "persistent_surface_buffer_update_proved", "engine_packed_vertex_region_update_proved", "static_uv_index_proved"):
        if truth.get(key) is not True:
            raise ValueError(f"required proof missing: {key}")
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
            raise ValueError(f"truth boundary overclaims: {key}")


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
