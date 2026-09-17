#!/usr/bin/env python3
"""Measure owner reconstruction versus a compiled Runtime receiving plan."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import statistics
import time
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_rigging_rebind import _select_joint
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.connected_deformation import _sub, _vec3
from axm_animal_design.runtime_post_skin_frame_plan import (
    compare_frames,
    compile_post_skin_frame_plan,
    reconstruct_frame_from_target_render_positions,
)
from axm_animal_design.transported_frame_reconstruction_constraint import (
    PASS_STATE as OWNER_PASS_STATE,
    _child_weights,
    _collapse_render_positions_to_source,
    inspect_post_skin_owner_frame_reconstruction,
)
from axm_animal_design.transported_tangent_deformation_audit import (
    KEY_COUNT,
    TECHNICAL_ART_ARTIFACT_ID,
    TECHNICAL_ART_ARTIFACT_SHA256,
    TECHNICAL_ART_GLB_SHA256,
    TECHNICAL_ART_HEAD,
    TECHNICAL_ART_MODULE_BLOB,
    _decode_glb,
    _skin_position,
)

RESULT_SCHEMA = "axm.animal-runtime-post-skin-frame-plan-evidence/v0.1"
PASS_STATE = (
    "PASS_ANIMAL_POST_SKIN_FRAME_PLAN_COMPILED_EXACT_41KEY_FRAME_IDENTITY__"
    "PROOF_HOST_CPU_REDUCTION__HOLD_TARGET_RUNTIME_BILATERAL_SHADED_DEVICE"
)
MIN_MEDIAN_REDUCTION_PERCENT = 10.0
BENCHMARK_ROUNDS = 17
WARMUP_ROUNDS = 3


def _load(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return int(ordered[index])


def _build_right_candidate(spec, left_profile, bilateral_profile):
    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    return right_candidate


def _skinned_render_positions(decoded, child_weights):
    document = decoded["document"]
    animated_node = decoded["ANIMATED_NODE"]
    nodes = document.get("nodes", [])
    if not 0 <= animated_node < len(nodes):
        raise ValueError("animated node index drift")
    pivot = nodes[animated_node].get("translation")
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise ValueError("transported child joint pivot missing")
    return [
        [
            _skin_position(position, pivot, quaternion, child_weight)
            for position, child_weight in zip(decoded["POSITION"], child_weights)
        ]
        for quaternion in decoded["ROTATIONS"]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--left-profile", type=Path, required=True)
    parser.add_argument("--bilateral-profile", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--weighting-profile", type=Path, required=True)
    parser.add_argument("--technical-art-receipt", type=Path, required=True)
    parser.add_argument("--technical-art-glb", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--technical-art-module-blob", required=True)
    parser.add_argument("--technical-art-artifact-id", type=int, required=True)
    parser.add_argument("--technical-art-artifact-sha256", required=True)
    parser.add_argument("--owner-rigging-head", required=True)
    parser.add_argument("--runtime-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    expected = {
        "technical_art_head": TECHNICAL_ART_HEAD,
        "technical_art_module_blob": TECHNICAL_ART_MODULE_BLOB,
        "technical_art_artifact_id": TECHNICAL_ART_ARTIFACT_ID,
        "technical_art_artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
    }
    observed = {
        "technical_art_head": args.technical_art_head,
        "technical_art_module_blob": args.technical_art_module_blob,
        "technical_art_artifact_id": args.technical_art_artifact_id,
        "technical_art_artifact_sha256": args.technical_art_artifact_sha256,
    }
    if observed != expected:
        raise SystemExit(f"exact Technical Art dependency identity drift: {observed!r} != {expected!r}")
    if args.owner_rigging_head != "81ab44eab2e13bed95187610a476be2b2c4667a7":
        raise SystemExit("exact owner Rigging reconstruction head drift")

    glb = args.technical_art_glb.read_bytes()
    glb_sha256 = hashlib.sha256(glb).hexdigest()
    if glb_sha256 != TECHNICAL_ART_GLB_SHA256:
        raise SystemExit("exact Technical Art GLB digest drift")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    rig_plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    transport_receipt = _load(args.technical_art_receipt)

    owner_receipt = inspect_post_skin_owner_frame_reconstruction(
        spec,
        left_profile,
        bilateral_profile,
        rig_plan,
        weighting_profile,
        transport_receipt,
        glb,
    )
    if owner_receipt.get("state") != OWNER_PASS_STATE:
        raise SystemExit(f"owner reconstruction prerequisite is not PASS: {owner_receipt.get('state')}")

    right_candidate = _build_right_candidate(spec, left_profile, bilateral_profile)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    compile_started = time.perf_counter_ns()
    runtime_plan = compile_post_skin_frame_plan(right_candidate, static_basis)
    compile_ns = time.perf_counter_ns() - compile_started

    decoded = _decode_glb(glb)
    if len(decoded["ROTATIONS"]) != KEY_COUNT:
        raise SystemExit("transported key count drift")
    child_weights = _child_weights(decoded)
    skinned_by_key = _skinned_render_positions(decoded, child_weights)
    render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
    source_vertex_count = int(static_basis["source_vertex_count"])

    maximum_split_residual_m = 0.0
    maximum_position_component_abs = 0.0
    maximum_normal_component_abs = 0.0
    maximum_tangent_component_abs = 0.0
    handedness_mismatches = 0
    exact_key_count = 0
    control_frames = []
    candidate_frames = []

    for sample_index, skinned_positions in enumerate(skinned_by_key):
        control_source, control_split = _collapse_render_positions_to_source(
            skinned_positions,
            render_source_indices,
            source_vertex_count,
        )
        control = _derive_posed_tangent_frame(right_candidate, static_basis, control_source)
        candidate, candidate_split = reconstruct_frame_from_target_render_positions(
            runtime_plan,
            skinned_positions,
        )
        maximum_split_residual_m = max(
            maximum_split_residual_m,
            float(control_split),
            float(candidate_split),
        )
        if control_split != candidate_split:
            raise SystemExit(f"compiled split residual drift at key {sample_index}")
        delta = compare_frames(control, candidate)
        maximum_position_component_abs = max(
            maximum_position_component_abs,
            float(delta["maximum_position_component_abs"]),
        )
        maximum_normal_component_abs = max(
            maximum_normal_component_abs,
            float(delta["maximum_normal_component_abs"]),
        )
        maximum_tangent_component_abs = max(
            maximum_tangent_component_abs,
            float(delta["maximum_tangent_component_abs"]),
        )
        handedness_mismatches += int(delta["tangent_handedness_mismatch_count"])
        if delta["exact_frame_arrays"]:
            exact_key_count += 1
        control_frames.append(control)
        candidate_frames.append(candidate)

    if exact_key_count != KEY_COUNT:
        raise SystemExit(
            "compiled Runtime frame plan is not exact across all keys: "
            f"{exact_key_count}/{KEY_COUNT}"
        )

    def baseline_sweep() -> None:
        for skinned_positions in skinned_by_key:
            source_positions, _ = _collapse_render_positions_to_source(
                skinned_positions,
                render_source_indices,
                source_vertex_count,
            )
            _derive_posed_tangent_frame(right_candidate, static_basis, source_positions)

    def candidate_sweep() -> None:
        for skinned_positions in skinned_by_key:
            reconstruct_frame_from_target_render_positions(runtime_plan, skinned_positions)

    for _ in range(WARMUP_ROUNDS):
        baseline_sweep()
        candidate_sweep()

    baseline_ns: list[int] = []
    candidate_ns: list[int] = []
    for round_index in range(BENCHMARK_ROUNDS):
        ordered = (
            ((baseline_sweep, baseline_ns), (candidate_sweep, candidate_ns))
            if round_index % 2 == 0
            else ((candidate_sweep, candidate_ns), (baseline_sweep, baseline_ns))
        )
        for function, bucket in ordered:
            started = time.perf_counter_ns()
            function()
            bucket.append(time.perf_counter_ns() - started)

    baseline_median_ns = int(statistics.median(baseline_ns))
    candidate_median_ns = int(statistics.median(candidate_ns))
    if baseline_median_ns <= 0:
        raise SystemExit("invalid baseline timing")
    median_reduction_percent = (
        (baseline_median_ns - candidate_median_ns) / float(baseline_median_ns) * 100.0
    )
    if median_reduction_percent < MIN_MEDIAN_REDUCTION_PERCENT:
        raise SystemExit(
            f"compiled plan median reduction {median_reduction_percent:.3f}% is below "
            f"{MIN_MEDIAN_REDUCTION_PERCENT:.1f}% gate"
        )

    # Fail-closed plan-integrity sensitivity. Rebind one source vertex to a
    # neighbouring source's exact render representatives and require the frame
    # comparison to stop being exact at the peak authored key.
    mutated_plan = copy.deepcopy(runtime_plan)
    mutated_plan["source_groups"][11] = list(runtime_plan["source_groups"][12])
    peak_index = max(
        range(KEY_COUNT),
        key=lambda index: abs(float(owner_receipt["motion_boundary"]["representative_samples"][2]["angle_deg_from_transport_quaternion"]))
        if index == 20 else abs(index - 20) * -1.0,
    )
    # The authored clip's retained peak is key 20; keep that identity explicit.
    peak_index = 20
    mutated_frame, mutated_split = reconstruct_frame_from_target_render_positions(
        mutated_plan,
        skinned_by_key[peak_index],
    )
    mutation_delta = compare_frames(control_frames[peak_index], mutated_frame)
    mutation_signal = max(
        float(mutation_delta["maximum_position_component_abs"]),
        float(mutation_delta["maximum_normal_component_abs"]),
        float(mutation_delta["maximum_tangent_component_abs"]),
    )
    if mutation_delta["exact_frame_arrays"] or mutation_signal <= 1e-6:
        raise SystemExit("compiled-plan source-group mutation was not detected")

    result = {
        "schema": RESULT_SCHEMA,
        "state": PASS_STATE,
        "identity": {
            "runtime_head": args.runtime_head,
            "owner_rigging_head": args.owner_rigging_head,
            "technical_art_head": TECHNICAL_ART_HEAD,
            "technical_art_module_blob": TECHNICAL_ART_MODULE_BLOB,
            "technical_art_artifact_id": TECHNICAL_ART_ARTIFACT_ID,
            "technical_art_artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
            "technical_art_glb_sha256": glb_sha256,
        },
        "scope": {
            "side": "right",
            "authored_key_count": KEY_COUNT,
            "source_vertex_count": runtime_plan["source_vertex_count"],
            "render_vertex_count": runtime_plan["render_vertex_count"],
            "triangle_count": runtime_plan["render_index_count"] // 3,
            "logical_quad_count": len(runtime_plan["logical_quads"]),
            "tangent_triangle_count": len(runtime_plan["tangent_triangles"]),
        },
        "before": {
            "path": "owner evidence implementation",
            "per_update_work": [
                "rebuild source representative groups",
                "deep-copy posed candidate",
                "rebuild pose-local path metadata",
                "rebuild logical quad/cap index traversal",
                "derive evidence-grade normal record including candidate digest",
                "recompute static UV deltas and determinant reciprocal for every render triangle",
                "derive exact owner normals/tangents",
            ],
        },
        "after": {
            "path": "compiled Runtime receiving plan",
            "one_time_compile_ns": compile_ns,
            "compiled_source_groups": len(runtime_plan["source_groups"]),
            "compiled_logical_quads": len(runtime_plan["logical_quads"]),
            "compiled_cap_wedges": len(runtime_plan["start_cap_wedges"]) + len(runtime_plan["end_cap_wedges"]),
            "compiled_tangent_triangles": len(runtime_plan["tangent_triangles"]),
            "per_update_work_retained": [
                "collapse actual skinned positions",
                "derive pose-local ring centres",
                "derive owner normals from current posed geometry",
                "derive tangent/bitangent vectors from current posed edges",
                "Gram-Schmidt tangent against current normal",
                "preserve current tangent handedness",
            ],
        },
        "equivalence": {
            "exact_frame_array_keys": exact_key_count,
            "total_keys": KEY_COUNT,
            "maximum_split_position_residual_m": maximum_split_residual_m,
            "maximum_position_component_abs": maximum_position_component_abs,
            "maximum_normal_component_abs": maximum_normal_component_abs,
            "maximum_tangent_component_abs": maximum_tangent_component_abs,
            "tangent_handedness_mismatch_count": handedness_mismatches,
            "visual_tradeoff": "NONE_OBSERVED_RECEIVER_FRAME_ARRAYS_EXACT_ALL_41_KEYS__FRESH_SHADED_RENDER_NOT_RUN",
        },
        "proof_host_timing": {
            "clock": "time.perf_counter_ns",
            "rounds": BENCHMARK_ROUNDS,
            "warmup_rounds": WARMUP_ROUNDS,
            "keys_per_round": KEY_COUNT,
            "baseline_median_sweep_ns": baseline_median_ns,
            "candidate_median_sweep_ns": candidate_median_ns,
            "median_reduction_percent": median_reduction_percent,
            "baseline_p95_sweep_ns": _percentile(baseline_ns, 0.95),
            "candidate_p95_sweep_ns": _percentile(candidate_ns, 0.95),
            "baseline_total_ns": sum(baseline_ns),
            "candidate_total_ns": sum(candidate_ns),
            "target_device_claimed": False,
        },
        "negative_control": {
            "mutation": "source vertex 11 rebound to compiled representatives for source vertex 12",
            "peak_key": peak_index,
            "mutated_split_residual_m": mutated_split,
            "maximum_component_signal": mutation_signal,
            "status": "PASS_MUTATION_DETECTED",
        },
        "truth_boundary": {
            "rigging_owner_semantics_changed": False,
            "technical_art_contract_changed": False,
            "universal_creation_modified": False,
            "right_all_41_authored_keys_proved": True,
            "bilateral_runtime_proved": False,
            "continuous_interpolated_playback_proved": False,
            "fresh_shaded_render_proved": False,
            "real_target_runtime_implemented": False,
            "target_device_cpu_gpu_fps_vram_proved": False,
            "art_direction_acceptance_claimed": False,
            "visual_qa_acceptance_claimed": False,
            "canon_claimed": False,
            "production_ready": False,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "runtime-post-skin-frame-plan-result.json", result)
    _write(args.out / "compiled-runtime-frame-plan.json", runtime_plan)
    _write(args.out / "exact-owner-reconstruction-receipt.json", owner_receipt)
    (args.out / "exact-runtime-head.txt").write_text(args.runtime_head + "\n", encoding="utf-8")
    (args.out / "exact-owner-rigging-head.txt").write_text(args.owner_rigging_head + "\n", encoding="utf-8")
    (args.out / "exact-technical-art-glb-sha256.txt").write_text(glb_sha256 + "\n", encoding="utf-8")

    print(PASS_STATE)
    print(f"exact_keys={exact_key_count}/{KEY_COUNT}")
    print(f"baseline_median_sweep_ns={baseline_median_ns}")
    print(f"candidate_median_sweep_ns={candidate_median_ns}")
    print(f"median_reduction_percent={median_reduction_percent:.6f}")
    print(f"mutation_signal={mutation_signal}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
