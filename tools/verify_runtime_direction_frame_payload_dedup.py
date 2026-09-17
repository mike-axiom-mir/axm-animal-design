#!/usr/bin/env python3
import json
import math
import sys
from pathlib import Path

EXPECTED_SCHEMA = "axm.animal-runtime-direction-frame-payload-dedup/v0.1"
EXPECTED_STATE = "PASS_ANIMAL_EXACT_KEY_VERTEX_PAYLOAD_DEDUP__LOWER_CACHE__41_RENDER_PAIRS_IDENTICAL__HOLD_DEVICE_ART"


def fail(message: str) -> None:
    raise SystemExit(message)


def main(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != EXPECTED_SCHEMA:
        fail("schema drift")
    if data.get("state") != EXPECTED_STATE:
        fail("state is not bounded PASS")

    scope = data["scope"]
    if scope.get("side") != "right" or scope.get("authored_keys") != 41:
        fail("scope drift")
    if scope.get("vertices_per_frame") != 84 or scope.get("indices_per_frame") != 240:
        fail("render domain drift")
    if scope.get("representation_only") is not True:
        fail("candidate no longer representation-only")

    cache = data["cache_budget"]
    per_key = int(cache["raw_vertex_bytes_per_key"])
    full_count = int(cache["full_cache_payload_count"])
    unique_count = int(cache["unique_payload_count"])
    full_bytes = int(cache["full_cache_bytes"])
    dedup_bytes = int(cache["deduplicated_cache_bytes"])
    saved_bytes = int(cache["saved_cache_bytes"])
    saved_percent = float(cache["saved_cache_percent"])
    mapping = cache["key_to_unique"]
    if per_key <= 0 or full_count != 41:
        fail("invalid full-cache budget")
    if not (0 < unique_count < full_count):
        fail("dedup did not reduce payload count")
    if full_bytes != per_key * full_count:
        fail("full-cache byte accounting mismatch")
    if dedup_bytes != per_key * unique_count:
        fail("dedup byte accounting mismatch")
    if saved_bytes != full_bytes - dedup_bytes or saved_bytes <= 0:
        fail("saved-byte accounting mismatch")
    expected_percent = saved_bytes / full_bytes * 100.0
    if not math.isclose(saved_percent, expected_percent, rel_tol=0.0, abs_tol=1e-9):
        fail("saved-percent accounting mismatch")
    if len(mapping) != 41 or min(mapping) < 0 or max(mapping) >= unique_count:
        fail("key-to-unique map drift")
    if cache.get("exact_byte_reconstruction_all_keys") is not True:
        fail("dedup payloads do not reconstruct every key exactly")
    if cache.get("map_storage_bytes_not_included") is not True:
        fail("map-overhead truth boundary missing")

    receiver = data["receiver"]
    expected_equal = [
        ("arraymesh_resources_control", 1),
        ("arraymesh_resources_candidate", 1),
        ("surface_constructions_control", 1),
        ("surface_constructions_candidate", 1),
        ("surface_rebuilds_per_playback_control", 0),
        ("surface_rebuilds_per_playback_candidate", 0),
        ("vertex_region_updates_per_playback_control", 41),
        ("vertex_region_updates_per_playback_candidate", 41),
    ]
    for key, expected in expected_equal:
        if int(receiver[key]) != expected:
            fail(f"receiver lifecycle drift: {key}")
    if receiver.get("same_motion_envelope_aabb") is not True or receiver.get("persistent_identity") is not True:
        fail("persistent receiver/culling identity drift")

    render = data["render_equivalence"]
    if int(render["render_pairs"]) != 41 or int(render["byte_identical_pairs"]) != 41:
        fail("render pair identity weakened")
    if int(render["total_changed_pixels"]) != 0 or int(render["maximum_channel_delta"]) != 0:
        fail("render delta detected")
    if render.get("observer_sensitive") is not True or int(render["observer_sensitivity_key0_vs_key20_changed_pixels"]) <= 0:
        fail("render observer is not demonstrably live")

    timing = data["proof_host_timing"]
    if int(timing["warmup_rounds"]) != 5 or int(timing["measured_rounds"]) != 31 or int(timing["keys_per_round"]) != 41:
        fail("timing protocol drift")
    for key in ("full_cache_median_sweep_us", "dedup_cache_median_sweep_us", "full_cache_p95_sweep_us", "dedup_cache_p95_sweep_us"):
        if float(timing[key]) <= 0:
            fail(f"invalid timing observation: {key}")
    if timing.get("timing_is_observation_not_acceptance_gate") is not True or timing.get("target_device_claimed") is not False:
        fail("timing truth boundary drift")

    visual = data["visual_tradeoff"]
    if visual.get("measured") != "NONE_OBSERVED_41_OF_41_DEBUG_RENDER_PAIRS_BYTE_IDENTICAL":
        fail("visual tradeoff result drift")
    if visual.get("fresh_production_shaded_render_run") is not False:
        fail("production shading overclaim")

    truth = data["truth_boundary"]
    required_false = [
        "technical_art_packet_changed",
        "universal_creation_modified",
        "pass41_surface_update_representation_changed",
        "continuous_interpolated_playback_proved",
        "bilateral_runtime_proved",
        "production_shaded_equivalence_proved",
        "target_device_cpu_gpu_fps_vram_proved",
        "art_direction_acceptance_claimed",
        "visual_qa_acceptance_claimed",
        "canon_claimed",
        "production_ready",
    ]
    for key in required_false:
        if truth.get(key) is not False:
            fail(f"truth boundary overclaim: {key}")
    if truth.get("cache_representation_only") is not True:
        fail("cache representation boundary missing")

    print("PASS: exact-key vertex payload dedup evidence verified")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("usage: verify_runtime_direction_frame_payload_dedup.py <result.json>")
    main(sys.argv[1])
