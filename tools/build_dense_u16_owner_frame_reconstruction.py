#!/usr/bin/env python3
"""Rigging-owned dense normalized-u16 post-skin owner-frame reconstruction audit.

Consumes exact Runtime FLOAT/u16 GLBs plus exact Animation dense-subframe evidence.
It does not rewrite source geometry, rig hierarchy, weighting semantics, clip timing,
transport code, target runtime, materials, or visual acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _pose_metrics,
    _select_joint,
    _source_triangle_areas,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.connected_deformation import _sub, _vec3, _weights, digest
from axm_animal_design.transported_frame_reconstruction_constraint import (
    DIRECTION_TOLERANCE_DEG,
    ORTHOGONALITY_TOLERANCE,
    SPLIT_POSITION_TOLERANCE_M,
    _collapse_render_positions_to_source,
    _frame_residual,
)
from axm_animal_design.transported_tangent_deformation_audit import (
    POSITION_TOLERANCE_M,
    _quat_angle_deg,
)

SCHEMA = "axm.animal-rigging-dense-u16-owner-frame-reconstruction/v0.1"
PASS_STATE = "PASS_DENSE_U16_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_321_SUBFRAMES__STATIC_DIRECTION_TRANSPORT_HOLD_PRESERVED"
HOLD_STATE = "HOLD_DENSE_U16_POST_SKIN_OWNER_FRAME_RECONSTRUCTION"
ANIMATION_HEAD = "37f5a77d39d221be796ac3b0c3a179fd3c86a8c0"
ANIMATION_ARTIFACT_ID = 10485697941
ANIMATION_ARTIFACT_SHA256 = "496e744f6bd3c8ad3b0648298cceecd7c7170a651f510674a92c957424a954e3"
EXPECTED_ANIMATION_STATE = "PASS_U16_WEIGHT_SUBFRAME_TRAJECTORY_WITHIN_RIGGING_BOUND"
RUNTIME_HEAD = "e7874c4a8dca1db48bc66f3546c2134f7d724456"
RUNTIME_ARTIFACT_ID = 10477292250
RUNTIME_ARTIFACT_SHA256 = "76455589e0dde3327f72ebff6a117a2ce12ff57edaaf1d0e61304056d03063c3"
CONTROL_GLB_SHA256 = "8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566"
CANDIDATE_GLB_SHA256 = "81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb"
PREDECESSOR_RIGGING_HEAD = "e4ce8c1f4c3deb55220cf962206d51013d0cfe73"
RECONSTRUCTION_PREDECESSOR_HEAD = "81ab44eab2e13bed95187610a476be2b2c4667a7"
DENSE_SAMPLE_COUNT = 321
DENSE_RATE_HZ = 320
NEGATIVE_CONTROL_TIME_S = 0.3375
NEGATIVE_CONTROL_RENDER_VERTEX = 23
NEGATIVE_CONTROL_U16_STEPS = 64
RECOMPUTE_EPS_M = 1e-12


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_animation_guard_module(path: Path):
    spec = importlib.util.spec_from_file_location("axm_exact_animation_u16_guard", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load exact Animation guard module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = {
        "RUNTIME_HEAD": RUNTIME_HEAD,
        "RUNTIME_ARTIFACT_ID": RUNTIME_ARTIFACT_ID,
        "RUNTIME_ARTIFACT_SHA256": RUNTIME_ARTIFACT_SHA256,
        "CONTROL_GLB_SHA256": CONTROL_GLB_SHA256,
        "CANDIDATE_GLB_SHA256": CANDIDATE_GLB_SHA256,
        "RIGGING_HEAD": PREDECESSOR_RIGGING_HEAD,
        "DENSE_SAMPLE_COUNT": DENSE_SAMPLE_COUNT,
        "DENSE_RATE_HZ": DENSE_RATE_HZ,
    }
    for name, expected_value in expected.items():
        if getattr(module, name, None) != expected_value:
            raise ValueError(f"Animation guard {name} drift")
    return module


def _prepare_owner(spec, left_profile, bilateral_profile, plan):
    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
    joint = _select_joint(spec, plan, "right")
    source_positions = [tuple(float(value) for value in point) for point in right_candidate["positions"]]
    source_indices = [int(value) for value in right_candidate["indices"]]
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    source_weights = _weights(
        source_positions,
        joint_position,
        child_direction,
        float(joint["influence_radius"]),
    )
    source_areas = _source_triangle_areas(source_positions, source_indices)
    return {
        "right_candidate": right_candidate,
        "static_basis": static_basis,
        "render_source_indices": render_source_indices,
        "source_vertex_count": int(static_basis["source_vertex_count"]),
        "source_positions": source_positions,
        "source_indices": source_indices,
        "joint": joint,
        "joint_position": joint_position,
        "source_weights": source_weights,
        "source_areas": source_areas,
    }


def _reconstruct_frame(owner, render_positions_target):
    source_positions, split_residual = _collapse_render_positions_to_source(
        render_positions_target,
        owner["render_source_indices"],
        owner["source_vertex_count"],
    )
    frame = _derive_posed_tangent_frame(
        owner["right_candidate"], owner["static_basis"], source_positions
    )
    return frame, split_residual


def _skin_positions(anim, motion, rotation, weights):
    return [
        anim._skin_position(
            position,
            motion["pivot"],
            rotation,
            anim._child_weight(joints, row_weights),
        )
        for position, joints, row_weights in zip(
            motion["positions"], motion["joints"], weights
        )
    ]


def build_report(
    spec,
    left_profile,
    bilateral_profile,
    plan,
    weighting_profile,
    control_glb: bytes,
    candidate_glb: bytes,
    animation_receipt: dict[str, Any],
    animation_guard_module_path: Path,
    current_rigging_head: str,
):
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")
    if _sha(control_glb) != CONTROL_GLB_SHA256:
        raise ValueError("FLOAT control GLB SHA drift")
    if _sha(candidate_glb) != CANDIDATE_GLB_SHA256:
        raise ValueError("normalized-u16 candidate GLB SHA drift")

    if animation_receipt.get("schema") != "axm.animal-animation-u16-weight-subframe-guard/v0.1":
        raise ValueError("Animation dense guard schema drift")
    if animation_receipt.get("state") != EXPECTED_ANIMATION_STATE:
        raise ValueError("Animation dense guard state drift")
    if animation_receipt.get("current_animation_head") != ANIMATION_HEAD:
        raise ValueError("Animation exact head drift")
    runtime_dep = animation_receipt.get("runtime_dependency", {})
    if runtime_dep.get("head") != RUNTIME_HEAD:
        raise ValueError("Animation Runtime dependency head drift")
    if runtime_dep.get("artifact_id") != RUNTIME_ARTIFACT_ID:
        raise ValueError("Animation Runtime artifact drift")
    if runtime_dep.get("artifact_sha256") != RUNTIME_ARTIFACT_SHA256:
        raise ValueError("Animation Runtime archive digest drift")
    rig_dep = animation_receipt.get("rigging_dependency", {})
    if rig_dep.get("head") != PREDECESSOR_RIGGING_HEAD:
        raise ValueError("Animation Rigging dependency head drift")
    interp = animation_receipt.get("transport_interpolation", {})
    if int(interp.get("dense_sample_count", -1)) != DENSE_SAMPLE_COUNT:
        raise ValueError("Animation dense sample-count drift")
    if int(interp.get("dense_rate_hz", -1)) != DENSE_RATE_HZ:
        raise ValueError("Animation dense rate drift")
    preserved = animation_receipt.get("preserved_hold", {})
    if preserved.get("deformed_normal_tangent_direction_frame_equivalence") != "HOLD_DEFORMED_STATIC_NORMAL_TANGENT_TRANSPORT_EQUIVALENCE":
        raise ValueError("static direction-frame HOLD was not preserved")

    anim = _load_animation_guard_module(animation_guard_module_path)
    control = anim._extract_motion(control_glb)
    candidate = anim._extract_motion(candidate_glb)
    anim._validate_pair(control, candidate)

    owner = _prepare_owner(spec, left_profile, bilateral_profile, plan)
    if len(owner["render_source_indices"]) != len(control["positions"]):
        raise ValueError("Geometry render/source map count drift")

    maxima = {
        "control_split_m": 0.0,
        "candidate_split_m": 0.0,
        "control_owner_position_m": 0.0,
        "candidate_owner_position_m": 0.0,
        "control_owner_normal_deg": 0.0,
        "candidate_owner_normal_deg": 0.0,
        "control_owner_tangent_deg": 0.0,
        "candidate_owner_tangent_deg": 0.0,
        "candidate_owner_nt_abs": 0.0,
        "candidate_control_position_m": 0.0,
        "candidate_control_normal_deg": 0.0,
        "candidate_control_tangent_deg": 0.0,
    }
    candidate_handedness_mismatches = 0
    candidate_control_handedness_mismatches = 0
    rows = []

    for dense_index in range(DENSE_SAMPLE_COUNT):
        time_s = dense_index / DENSE_RATE_HZ
        rotation = anim._rotation_at(control["times"], control["rotations"], time_s)
        angle_deg = _quat_angle_deg(rotation)
        owner_pose = _pose_metrics(
            owner["source_positions"],
            owner["source_indices"],
            owner["source_areas"],
            owner["source_weights"],
            owner["joint_position"],
            _vec3(owner["joint"]["axis"], "joint axis"),
            angle_deg,
        )
        if owner_pose.get("status") != "PASS":
            raise ValueError(f"owner pose not PASS at dense sample {dense_index}")
        owner_frame = _derive_posed_tangent_frame(
            owner["right_candidate"], owner["static_basis"], owner_pose["positions"]
        )

        control_positions = _skin_positions(anim, control, rotation, control["weights"])
        candidate_positions = _skin_positions(anim, candidate, rotation, candidate["weights"])
        control_frame, control_split = _reconstruct_frame(owner, control_positions)
        candidate_frame, candidate_split = _reconstruct_frame(owner, candidate_positions)
        control_owner = _frame_residual(control_frame, owner_frame)
        candidate_owner = _frame_residual(candidate_frame, owner_frame)
        candidate_control = _frame_residual(candidate_frame, control_frame)

        maxima["control_split_m"] = max(maxima["control_split_m"], control_split)
        maxima["candidate_split_m"] = max(maxima["candidate_split_m"], candidate_split)
        maxima["control_owner_position_m"] = max(maxima["control_owner_position_m"], control_owner["maximum_position_residual_m"])
        maxima["candidate_owner_position_m"] = max(maxima["candidate_owner_position_m"], candidate_owner["maximum_position_residual_m"])
        maxima["control_owner_normal_deg"] = max(maxima["control_owner_normal_deg"], control_owner["maximum_normal_angle_deg"])
        maxima["candidate_owner_normal_deg"] = max(maxima["candidate_owner_normal_deg"], candidate_owner["maximum_normal_angle_deg"])
        maxima["control_owner_tangent_deg"] = max(maxima["control_owner_tangent_deg"], control_owner["maximum_tangent_angle_deg"])
        maxima["candidate_owner_tangent_deg"] = max(maxima["candidate_owner_tangent_deg"], candidate_owner["maximum_tangent_angle_deg"])
        maxima["candidate_owner_nt_abs"] = max(maxima["candidate_owner_nt_abs"], candidate_owner["maximum_normal_tangent_dot_abs"])
        maxima["candidate_control_position_m"] = max(maxima["candidate_control_position_m"], candidate_control["maximum_position_residual_m"])
        maxima["candidate_control_normal_deg"] = max(maxima["candidate_control_normal_deg"], candidate_control["maximum_normal_angle_deg"])
        maxima["candidate_control_tangent_deg"] = max(maxima["candidate_control_tangent_deg"], candidate_control["maximum_tangent_angle_deg"])
        candidate_handedness_mismatches += candidate_owner["handedness_mismatch_count"]
        candidate_control_handedness_mismatches += candidate_control["handedness_mismatch_count"]

        rows.append({
            "dense_index": dense_index,
            "time_s": time_s,
            "angle_deg": angle_deg,
            "authored_key": dense_index % 8 == 0,
            "candidate_owner_position_residual_m": candidate_owner["maximum_position_residual_m"],
            "candidate_owner_normal_angle_deg": candidate_owner["maximum_normal_angle_deg"],
            "candidate_owner_tangent_angle_deg": candidate_owner["maximum_tangent_angle_deg"],
            "candidate_control_position_residual_m": candidate_control["maximum_position_residual_m"],
            "candidate_control_normal_angle_deg": candidate_control["maximum_normal_angle_deg"],
            "candidate_control_tangent_angle_deg": candidate_control["maximum_tangent_angle_deg"],
        })

    recomputed_dense_position_delta = maxima["candidate_control_position_m"]
    animation_dense_position_delta = float(
        animation_receipt["metrics"]["dense_max_control_candidate_position_delta_m"]
    )
    dense_position_recompute_residual = abs(
        recomputed_dense_position_delta - animation_dense_position_delta
    )

    source_index = owner["render_source_indices"][NEGATIVE_CONTROL_RENDER_VERTEX]
    mutated_weights = [list(row) for row in candidate["weights"]]
    affected = [
        index
        for index, mapped in enumerate(owner["render_source_indices"])
        if mapped == source_index
    ]
    step = NEGATIVE_CONTROL_U16_STEPS / 65535.0
    for render_index in affected:
        joints = [int(value) for value in candidate["joints"][render_index]]
        try:
            parent_slot = joints.index(0)
            child_slot = joints.index(1)
        except ValueError as exc:
            raise ValueError("negative-control source representative lacks expected joints") from exc
        if mutated_weights[render_index][parent_slot] <= step:
            raise ValueError("negative-control parent weight too small")
        mutated_weights[render_index][parent_slot] -= step
        mutated_weights[render_index][child_slot] += step

    rotation = anim._rotation_at(
        control["times"], control["rotations"], NEGATIVE_CONTROL_TIME_S
    )
    angle_deg = _quat_angle_deg(rotation)
    owner_pose = _pose_metrics(
        owner["source_positions"],
        owner["source_indices"],
        owner["source_areas"],
        owner["source_weights"],
        owner["joint_position"],
        _vec3(owner["joint"]["axis"], "joint axis"),
        angle_deg,
    )
    owner_frame = _derive_posed_tangent_frame(
        owner["right_candidate"], owner["static_basis"], owner_pose["positions"]
    )
    mutated_positions = _skin_positions(anim, candidate, rotation, mutated_weights)
    mutated_frame, mutated_split = _reconstruct_frame(owner, mutated_positions)
    mutated_residual = _frame_residual(mutated_frame, owner_frame)
    mutation_direction_signal_deg = max(
        mutated_residual["maximum_normal_angle_deg"],
        mutated_residual["maximum_tangent_angle_deg"],
    )
    mutation_rejected = (
        mutated_residual["maximum_position_residual_m"] > POSITION_TOLERANCE_M
        or mutation_direction_signal_deg > DIRECTION_TOLERANCE_DEG
    )

    gate = (
        maxima["control_split_m"] <= SPLIT_POSITION_TOLERANCE_M
        and maxima["candidate_split_m"] <= SPLIT_POSITION_TOLERANCE_M
        and maxima["control_owner_position_m"] <= POSITION_TOLERANCE_M
        and maxima["candidate_owner_position_m"] <= POSITION_TOLERANCE_M
        and maxima["control_owner_normal_deg"] <= DIRECTION_TOLERANCE_DEG
        and maxima["candidate_owner_normal_deg"] <= DIRECTION_TOLERANCE_DEG
        and maxima["control_owner_tangent_deg"] <= DIRECTION_TOLERANCE_DEG
        and maxima["candidate_owner_tangent_deg"] <= DIRECTION_TOLERANCE_DEG
        and maxima["candidate_owner_nt_abs"] <= ORTHOGONALITY_TOLERANCE
        and candidate_handedness_mismatches == 0
        and candidate_control_handedness_mismatches == 0
        and dense_position_recompute_residual <= RECOMPUTE_EPS_M
        and mutation_rejected
    )

    reps = [0, 80, 160, 240, 320]
    report = {
        "schema": SCHEMA,
        "state": PASS_STATE if gate else HOLD_STATE,
        "current_rigging_head": current_rigging_head,
        "identity": {
            "predecessor_rigging_head": PREDECESSOR_RIGGING_HEAD,
            "reconstruction_predecessor_head": RECONSTRUCTION_PREDECESSOR_HEAD,
            "animation_head": ANIMATION_HEAD,
            "animation_artifact_id": ANIMATION_ARTIFACT_ID,
            "animation_artifact_sha256": ANIMATION_ARTIFACT_SHA256,
            "runtime_head": RUNTIME_HEAD,
            "runtime_artifact_id": RUNTIME_ARTIFACT_ID,
            "runtime_artifact_sha256": RUNTIME_ARTIFACT_SHA256,
            "control_glb_sha256": CONTROL_GLB_SHA256,
            "candidate_glb_sha256": CANDIDATE_GLB_SHA256,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
            "weighting": "smoothstep-v0",
        },
        "motion_boundary": {
            "dense_sample_count": DENSE_SAMPLE_COUNT,
            "dense_rate_hz": DENSE_RATE_HZ,
            "time_start_s": 0.0,
            "time_end_s": 1.0,
            "maximum_angle_deg": max(row["angle_deg"] for row in rows),
            "representative_samples": [rows[index] for index in reps],
        },
        "reconstruction": {
            **maxima,
            "candidate_owner_handedness_mismatch_count": candidate_handedness_mismatches,
            "candidate_control_handedness_mismatch_count": candidate_control_handedness_mismatches,
            "animation_dense_position_delta_m": animation_dense_position_delta,
            "recomputed_dense_position_delta_m": recomputed_dense_position_delta,
            "dense_position_recompute_residual_m": dense_position_recompute_residual,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "direction_tolerance_deg": DIRECTION_TOLERANCE_DEG,
            "orthogonality_tolerance": ORTHOGONALITY_TOLERANCE,
        },
        "negative_control": {
            "time_s": NEGATIVE_CONTROL_TIME_S,
            "source_vertex": source_index,
            "render_representatives": affected,
            "mutation": f"coherent +{NEGATIVE_CONTROL_U16_STEPS} u16 child-weight steps with equal parent subtraction",
            "split_residual_m": mutated_split,
            "owner_position_residual_m": mutated_residual["maximum_position_residual_m"],
            "owner_normal_angle_deg": mutated_residual["maximum_normal_angle_deg"],
            "owner_tangent_angle_deg": mutated_residual["maximum_tangent_angle_deg"],
            "direction_signal_deg": mutation_direction_signal_deg,
            "rejected": mutation_rejected,
            "state": "PASS_FAILS_CLOSED_ON_DENSE_WEIGHT_DRIFT" if mutation_rejected else "FAIL_NEGATIVE_CONTROL_NOT_DETECTED",
        },
        "preserved_hold": {
            "state": "HOLD_DEFORMED_STATIC_NORMAL_TANGENT_TRANSPORT_EQUIVALENCE",
            "historical_normal_excess_deg": 7.541933278181338,
            "historical_corrected_tangent_excess_deg": 3.6840862372161047,
            "reclassified": False,
        },
        "truth_boundary": {
            "animation_dense_guard_consumed": True,
            "animation_timing_interpolation_playback_accepted_by_rigging": False,
            "technical_art_target_runtime_implementation_accepted": False,
            "runtime_controller_device_accepted": False,
            "shaded_visual_quality_accepted": False,
            "source_or_rig_rewritten": False,
            "canon_claimed": False,
            "production_ready": False,
        },
    }
    return report, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--left-profile", type=Path, required=True)
    parser.add_argument("--bilateral-profile", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--weighting-profile", type=Path, required=True)
    parser.add_argument("--control-glb", type=Path, required=True)
    parser.add_argument("--candidate-glb", type=Path, required=True)
    parser.add_argument("--animation-receipt", type=Path, required=True)
    parser.add_argument("--animation-guard-tool", type=Path, required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report, rows = build_report(
        _load_json(args.source),
        _load_json(args.left_profile),
        _load_json(args.bilateral_profile),
        _load_json(args.rig_plan),
        _load_json(args.weighting_profile),
        args.control_glb.read_bytes(),
        args.candidate_glb.read_bytes(),
        _load_json(args.animation_receipt),
        args.animation_guard_tool,
        args.current_rigging_head,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "dense-samples.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "exact-rigging-head.txt").write_text(
        args.current_rigging_head + "\n", encoding="utf-8"
    )
    (args.out / "summary.txt").write_text(
        "\n".join(
            [
                report["state"],
                f"dense_samples={report['motion_boundary']['dense_sample_count']}",
                f"dense_rate_hz={report['motion_boundary']['dense_rate_hz']}",
                f"max_angle_deg={report['motion_boundary']['maximum_angle_deg']}",
                f"candidate_owner_position_m={report['reconstruction']['candidate_owner_position_m']}",
                f"candidate_owner_normal_deg={report['reconstruction']['candidate_owner_normal_deg']}",
                f"candidate_owner_tangent_deg={report['reconstruction']['candidate_owner_tangent_deg']}",
                f"candidate_control_position_m={report['reconstruction']['candidate_control_position_m']}",
                f"candidate_control_normal_deg={report['reconstruction']['candidate_control_normal_deg']}",
                f"candidate_control_tangent_deg={report['reconstruction']['candidate_control_tangent_deg']}",
                f"negative_control_state={report['negative_control']['state']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"] == PASS_STATE else 1


if __name__ == "__main__":
    raise SystemExit(main())
