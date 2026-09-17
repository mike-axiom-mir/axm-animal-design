#!/usr/bin/env python3
"""Fail-closed verifier for rendered Animal persistent vertex-buffer Runtime evidence."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

SCHEMA = "axm.animal-runtime-direction-frame-dynamic-render/v0.1"
STATE = "PASS_ANIMAL_GODOT_PERSISTENT_VERTEX_BUFFER_UPDATE__41_TO_0_SURFACE_REBUILDS__41_RENDER_PAIRS_IDENTICAL__HOLD_DEVICE_ART"
KEYS = 41


def obj(v, name):
    if not isinstance(v, dict):
        raise ValueError(f"{name} must be object")
    return v


def num(v, name):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
        raise ValueError(f"{name} must be finite numeric")
    return float(v)


def verify_readback(m):
    if m.get("frames") != KEYS:
        raise ValueError("baseline readback key count drift")
    if num(m.get("maximum_position_vector_delta"), "position") > 1e-6:
        raise ValueError("baseline position tolerance exceeded")
    if num(m.get("maximum_normal_vector_delta"), "normal") > 0.00025 or num(m.get("maximum_normal_angle_deg"), "normal angle") > 0.015:
        raise ValueError("baseline normal tolerance exceeded")
    if num(m.get("maximum_tangent_vector_delta"), "tangent") > 0.00025 or num(m.get("maximum_tangent_angle_deg"), "tangent angle") > 0.015:
        raise ValueError("baseline tangent tolerance exceeded")
    if num(m.get("maximum_uv_delta"), "uv") > 1e-6 or m.get("tangent_w_mismatch_count") != 0 or m.get("index_mismatch_count") != 0:
        raise ValueError("baseline uv/tangent-w/index mismatch")


def verify(result):
    if result.get("schema") != SCHEMA or result.get("state") != STATE:
        raise ValueError("exact bounded render PASS missing")
    target = obj(result.get("target_host"), "target_host")
    if target.get("engine") != "Godot" or "4.7.2" not in str(target.get("version", "")):
        raise ValueError("Godot target-host version drift")
    scope = obj(result.get("scope"), "scope")
    if scope.get("side") != "right" or scope.get("authored_keys") != KEYS or scope.get("vertices_per_frame") != 84 or scope.get("indices_per_frame") != 240:
        raise ValueError("bounded Animal scope drift")
    if scope.get("static_uv_and_indices") is not True:
        raise ValueError("static UV/index precondition missing")

    before = obj(result.get("before"), "before")
    after = obj(result.get("after"), "after")
    if before.get("arraymesh_resources_per_playback") != 1 or before.get("surface_rebuilds_per_41_key_playback") != KEYS or before.get("surface_constructions_per_41_key_playback") != KEYS:
        raise ValueError("pass-40 baseline representation drift")
    if after.get("arraymesh_resources_per_playback") != 1 or after.get("surface_rebuilds_per_41_key_playback") != 0 or after.get("surface_constructions_to_establish_receiver") != 1:
        raise ValueError("persistent-surface candidate representation drift")
    if after.get("vertex_region_updates_per_key") != 1 or after.get("vertex_region_updates_per_playback") != KEYS:
        raise ValueError("vertex-region update count drift")
    if num(after.get("surface_rebuild_reduction_percent"), "surface rebuild reduction") != 100.0:
        raise ValueError("surface rebuild reduction arithmetic drift")
    expected = 40.0 / 41.0 * 100.0
    if abs(num(after.get("surface_construction_reduction_percent"), "surface construction reduction") - expected) > 1e-9:
        raise ValueError("surface construction reduction arithmetic drift")
    for key in ("persistent_arraymesh_identity", "persistent_surface_identity", "dynamic_update_flag_retained", "uv_and_index_buffers_untouched"):
        if after.get(key) is not True:
            raise ValueError(f"candidate invariant failed: {key}")

    cache = obj(result.get("engine_packed_vertex_cache"), "engine_packed_vertex_cache")
    per_key = cache.get("raw_vertex_bytes_per_key")
    if not isinstance(per_key, int) or isinstance(per_key, bool) or per_key <= 0:
        raise ValueError("invalid raw vertex byte count")
    if cache.get("cached_raw_vertex_bytes_all_41_keys") != per_key * KEYS:
        raise ValueError("raw vertex cache byte accounting drift")
    if cache.get("manual_private_encoding_used") is not False or cache.get("payload_size_matches_candidate") is not True or cache.get("preparation_in_timed_sweeps") is not False:
        raise ValueError("engine-packed payload boundary drift")

    verify_readback(obj(result.get("baseline_target_host_readback"), "baseline_target_host_readback"))
    diagnostic = obj(result.get("region_update_cpu_readback_diagnostic"), "region_update_cpu_readback_diagnostic")
    if diagnostic.get("used_as_acceptance_gate") is not False or "CPU-side" not in str(diagnostic.get("reason", "")):
        raise ValueError("stale CPU readback limitation not preserved")

    rendered = obj(result.get("render_equivalence"), "render_equivalence")
    if rendered.get("render_pairs") != KEYS or rendered.get("byte_identical_pairs") != KEYS:
        raise ValueError("not all 41 rendered pairs are identical")
    if rendered.get("total_changed_pixels") != 0 or rendered.get("maximum_channel_delta") != 0:
        raise ValueError("render delta detected")
    if rendered.get("debug_shader_exercises_position_normal_and_tangent") is not True:
        raise ValueError("render observer does not exercise required vertex inputs")
    if rendered.get("observer_sensitive") is not True or rendered.get("observer_sensitivity_key0_vs_key20_changed_pixels", 0) <= 0:
        raise ValueError("render observer sensitivity not established")
    if rendered.get("retained_keys") != [0, 10, 20, 30, 40]:
        raise ValueError("retained render key set drift")

    timing = obj(result.get("proof_host_timing"), "proof_host_timing")
    if timing.get("warmup_rounds") != 5 or timing.get("measured_rounds") != 31 or timing.get("keys_per_round") != KEYS:
        raise ValueError("timing protocol drift")
    bm = num(timing.get("baseline_median_sweep_us"), "baseline median")
    cm = num(timing.get("candidate_median_sweep_us"), "candidate median")
    bp = num(timing.get("baseline_p95_sweep_us"), "baseline p95")
    cp = num(timing.get("candidate_p95_sweep_us"), "candidate p95")
    if min(bm, cm, bp, cp) <= 0 or cm > bm:
        raise ValueError("candidate did not retain bounded median win")
    if timing.get("target_device_claimed") is not False:
        raise ValueError("proof-host timing relabelled as target-device evidence")

    envelope = obj(result.get("motion_envelope"), "motion_envelope")
    if envelope.get("custom_aabb_used") is not True or envelope.get("all_41_keys_included") is not True:
        raise ValueError("full-motion culling envelope missing")
    if num(envelope.get("envelope_vs_median_frame_volume_ratio"), "AABB ratio") <= 1.0:
        raise ValueError("expected conservative culling tradeoff not measured")
    if "looser" not in str(envelope.get("tradeoff", "")):
        raise ValueError("culling tradeoff text missing")

    visual = obj(result.get("visual_tradeoff"), "visual_tradeoff")
    if visual.get("measured") != "NONE_OBSERVED_41_OF_41_POSITION_NORMAL_TANGENT_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL":
        raise ValueError("measured visual result drift")
    if visual.get("fresh_production_shaded_render_run") is not False or visual.get("art_review_state") != "HOLD_PRODUCTION_SHADED_VISUAL_AND_CULLING_ENVELOPE_REVIEW":
        raise ValueError("Art/production visual hold drift")

    failed = result.get("failed_predecessors_preserved")
    if not isinstance(failed, list) or len(failed) != 2:
        raise ValueError("failed predecessor chain not preserved")
    if failed[0].get("head") != "fbc9c8a86daa299c6a3bf2b9aa421cf30b01df41" or failed[0].get("artifact") != 10516719596:
        raise ValueError("manual-packing failure identity drift")
    if failed[1].get("head") != "79c3fead177996e7b825885701c877c81a1f46c7" or failed[1].get("artifact") != 10518260489:
        raise ValueError("engine-packed stale-readback failure identity drift")

    truth = obj(result.get("truth_boundary"), "truth_boundary")
    if truth.get("persistent_surface_vertex_buffer_update_proved_by_render") is not True:
        raise ValueError("render-backed persistent vertex-buffer proof missing")
    for key in (
        "technical_art_packet_changed", "universal_creation_modified", "production_shaded_equivalence_proved",
        "bilateral_runtime_proved", "continuous_interpolated_playback_proved", "target_device_cpu_gpu_fps_vram_proved",
        "art_direction_acceptance_claimed", "visual_qa_acceptance_claimed", "canon_claimed", "production_ready",
    ):
        if truth.get(key) is not False:
            raise ValueError(f"truth boundary overclaims {key}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("result", type=Path)
    args = p.parse_args()
    verify(json.loads(args.result.read_text(encoding="utf-8")))
    print(STATE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
