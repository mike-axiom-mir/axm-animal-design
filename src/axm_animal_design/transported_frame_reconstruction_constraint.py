"""Rigging-owned post-skin direction-frame reconstruction constraint.

This module advances the exact transported-frame HOLD without changing source
geometry, rig hierarchy, weights, UVs, Animation keys, Technical-Art GLB bytes,
or Runtime implementation. It asks one bounded follow-up question:

Can the exact Rigging owner normal/tangent frame be reconstructed from the
already-transported *skinned positions* plus the fixed Geometry topology/UV
identity, instead of skinning the static NORMAL/TANGENT directions themselves?

The reconstruction is a structural constraint witness only. It is not silently
promoted into Technical Art, an importer, shader, Runtime, Animation or CANON.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from .bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from .bilateral_source_successor_rigging_rebind import (
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _pose_metrics,
    _select_joint,
    _source_triangle_areas,
)
from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .bilateral_uv_tangent_basis import derive_uv_tangent_basis
from .connected_deformation import BASELINE_WEIGHTING, _sub, _vec3, _weights, digest
from .transported_tangent_deformation_audit import (
    HOLD_STATE as TRANSPORT_HOLD_STATE,
    PASS_STATE as TRANSPORT_PASS_STATE,
    KEY_COUNT,
    POSITION_TOLERANCE_M,
    RENDER_VERTEX_COUNT,
    _angle_deg,
    _decode_glb,
    _distance,
    _dot,
    _quat_angle_deg,
    _skin_position,
    inspect_transported_tangent_deformation,
)

EVIDENCE_SCHEMA = "axm.animal-post-skin-owner-frame-reconstruction/v0.1"
PASS_STATE = "PASS_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_41_KEYS"
HOLD_STATE = "HOLD_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION"
DIRECTION_TOLERANCE_DEG = 1e-3
ORTHOGONALITY_TOLERANCE = 1e-9
SPLIT_POSITION_TOLERANCE_M = 1e-6
MUTATION_DELTA_M = 1e-3
MUTATION_MIN_DIRECTION_SIGNAL_DEG = 5e-2
MUTATION_SOURCE_INDEX = 11


def _target_position_to_source(value):
    """Inverse of Animal -> UC target mapping [-y, z, x]."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("target position must be a 3D point")
    x, y, z = (float(component) for component in value)
    return [z, -x, y]


def _child_weights(decoded: dict[str, Any]) -> list[float]:
    output = []
    for joints, weights in zip(decoded["JOINTS_0"], decoded["WEIGHTS_0"]):
        if len(joints) != 4 or len(weights) != 4:
            raise ValueError("transported skin rows must be VEC4")
        if abs(sum(float(value) for value in weights) - 1.0) > 1e-6:
            raise ValueError("transported skin weight sum drift")
        child = sum(float(weight) for joint_id, weight in zip(joints, weights) if int(joint_id) == 1)
        other = sum(float(weight) for joint_id, weight in zip(joints, weights) if int(joint_id) not in (0, 1))
        if abs(other) > 1e-8:
            raise ValueError("transported GLB introduced an unexpected joint")
        output.append(child)
    if len(output) != RENDER_VERTEX_COUNT:
        raise ValueError("transported child-weight count drift")
    return output


def _collapse_render_positions_to_source(
    render_positions_target,
    render_source_indices,
    source_vertex_count: int,
):
    if len(render_positions_target) != len(render_source_indices):
        raise ValueError("render/source mapping count drift")
    groups: dict[int, list[list[float]]] = {index: [] for index in range(source_vertex_count)}
    for render_position, source_index in zip(render_positions_target, render_source_indices):
        source_index = int(source_index)
        if source_index not in groups:
            raise ValueError("render source index out of range")
        groups[source_index].append([float(value) for value in render_position])

    collapsed = []
    maximum_split_residual_m = 0.0
    for source_index in range(source_vertex_count):
        rows = groups[source_index]
        if not rows:
            raise ValueError(f"source vertex {source_index} has no transported render representative")
        reference = rows[0]
        for row in rows[1:]:
            maximum_split_residual_m = max(maximum_split_residual_m, _distance(reference, row))
        collapsed.append(_target_position_to_source(reference))
    return collapsed, maximum_split_residual_m


def _frame_residual(reconstructed, owner):
    maximum_position_residual_m = 0.0
    maximum_normal_angle_deg = 0.0
    maximum_tangent_angle_deg = 0.0
    maximum_normal_tangent_dot_abs = 0.0
    handedness_mismatch_count = 0
    for reconstructed_position, owner_position in zip(
        reconstructed["render_positions"], owner["render_positions"]
    ):
        maximum_position_residual_m = max(
            maximum_position_residual_m,
            _distance(reconstructed_position, owner_position),
        )
    for reconstructed_normal, owner_normal, reconstructed_tangent, owner_tangent in zip(
        reconstructed["render_normals"],
        owner["render_normals"],
        reconstructed["render_tangents"],
        owner["render_tangents"],
    ):
        maximum_normal_angle_deg = max(
            maximum_normal_angle_deg,
            _angle_deg(reconstructed_normal, owner_normal),
        )
        maximum_tangent_angle_deg = max(
            maximum_tangent_angle_deg,
            _angle_deg(reconstructed_tangent[:3], owner_tangent[:3]),
        )
        maximum_normal_tangent_dot_abs = max(
            maximum_normal_tangent_dot_abs,
            abs(_dot(reconstructed_normal, reconstructed_tangent[:3])),
        )
        if float(reconstructed_tangent[3]) != float(owner_tangent[3]):
            handedness_mismatch_count += 1
    return {
        "maximum_position_residual_m": maximum_position_residual_m,
        "maximum_normal_angle_deg": maximum_normal_angle_deg,
        "maximum_tangent_angle_deg": maximum_tangent_angle_deg,
        "maximum_normal_tangent_dot_abs": maximum_normal_tangent_dot_abs,
        "handedness_mismatch_count": handedness_mismatch_count,
    }


def inspect_post_skin_owner_frame_reconstruction(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
    transport_receipt: dict[str, Any],
    glb: bytes,
) -> dict[str, Any]:
    """Prove a bounded pose-derived direction-frame reconstruction witness."""
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")

    transport_audit = inspect_transported_tangent_deformation(
        spec,
        left_profile,
        bilateral_profile,
        plan,
        weighting_profile,
        transport_receipt,
        glb,
    )
    if transport_audit.get("state") not in {TRANSPORT_HOLD_STATE, TRANSPORT_PASS_STATE}:
        raise ValueError("transported deformation prerequisite is not position-safe")
    if transport_audit["position_uv_handedness"]["gate"] != "PASS":
        raise ValueError("transported position/UV/handedness prerequisite is not PASS")
    if transport_audit["direction_frames"]["equivalence_gate"] != "HOLD":
        raise ValueError("exact retained static-direction transport HOLD is no longer present")

    decoded = _decode_glb(glb)
    if len(decoded["ROTATIONS"]) != KEY_COUNT or len(decoded["POSITION"]) != RENDER_VERTEX_COUNT:
        raise ValueError("transported GLB key/render count drift")

    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
    source_vertex_count = int(static_basis["source_vertex_count"])
    if len(render_source_indices) != RENDER_VERTEX_COUNT:
        raise ValueError("Geometry render-source mapping drift")

    joint = _select_joint(spec, plan, "right")
    owner_source_positions = [tuple(float(value) for value in point) for point in right_candidate["positions"]]
    owner_source_indices = [int(value) for value in right_candidate["indices"]]
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    owner_source_weights = _weights(
        owner_source_positions,
        joint_position,
        child_direction,
        float(joint["influence_radius"]),
    )
    owner_source_areas = _source_triangle_areas(owner_source_positions, owner_source_indices)

    document = decoded["document"]
    animated_node = decoded["ANIMATED_NODE"]
    nodes = document.get("nodes", [])
    if not 0 <= animated_node < len(nodes):
        raise ValueError("animated node index drift")
    pivot = nodes[animated_node].get("translation")
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise ValueError("transported child joint pivot missing")
    child_weights = _child_weights(decoded)

    maximum_split_residual_m = 0.0
    maximum_reconstructed_position_residual_m = 0.0
    maximum_reconstructed_normal_angle_deg = 0.0
    maximum_reconstructed_tangent_angle_deg = 0.0
    maximum_reconstructed_normal_tangent_dot_abs = 0.0
    handedness_mismatch_count = 0
    rows = []
    owner_frames = []
    skinned_render_positions_by_key = []

    for sample_index, (time_value, quaternion) in enumerate(zip(decoded["TIMES"], decoded["ROTATIONS"])):
        angle_deg = _quat_angle_deg(quaternion)
        owner_pose = _pose_metrics(
            owner_source_positions,
            owner_source_indices,
            owner_source_areas,
            owner_source_weights,
            joint_position,
            _vec3(joint["axis"], "joint axis"),
            angle_deg,
        )
        if owner_pose.get("status") != "PASS":
            raise ValueError(f"owner pose is not PASS at transported key {sample_index}")
        owner_frame = _derive_posed_tangent_frame(
            right_candidate, static_basis, owner_pose["positions"]
        )
        owner_frames.append(owner_frame)

        skinned_render_positions = [
            _skin_position(position, pivot, quaternion, child_weight)
            for position, child_weight in zip(decoded["POSITION"], child_weights)
        ]
        skinned_render_positions_by_key.append(skinned_render_positions)
        reconstructed_source_positions, split_residual = _collapse_render_positions_to_source(
            skinned_render_positions,
            render_source_indices,
            source_vertex_count,
        )
        reconstructed_frame = _derive_posed_tangent_frame(
            right_candidate, static_basis, reconstructed_source_positions
        )
        residual = _frame_residual(reconstructed_frame, owner_frame)

        maximum_split_residual_m = max(maximum_split_residual_m, split_residual)
        maximum_reconstructed_position_residual_m = max(
            maximum_reconstructed_position_residual_m,
            residual["maximum_position_residual_m"],
        )
        maximum_reconstructed_normal_angle_deg = max(
            maximum_reconstructed_normal_angle_deg,
            residual["maximum_normal_angle_deg"],
        )
        maximum_reconstructed_tangent_angle_deg = max(
            maximum_reconstructed_tangent_angle_deg,
            residual["maximum_tangent_angle_deg"],
        )
        maximum_reconstructed_normal_tangent_dot_abs = max(
            maximum_reconstructed_normal_tangent_dot_abs,
            residual["maximum_normal_tangent_dot_abs"],
        )
        handedness_mismatch_count += residual["handedness_mismatch_count"]
        rows.append(
            {
                "sample_index": sample_index,
                "time_seconds": float(time_value),
                "angle_deg_from_transport_quaternion": angle_deg,
                "split_position_residual_m": split_residual,
                **residual,
            }
        )

    reconstruction_pass = (
        maximum_split_residual_m <= SPLIT_POSITION_TOLERANCE_M
        and maximum_reconstructed_position_residual_m <= POSITION_TOLERANCE_M
        and maximum_reconstructed_normal_angle_deg <= DIRECTION_TOLERANCE_DEG
        and maximum_reconstructed_tangent_angle_deg <= DIRECTION_TOLERANCE_DEG
        and maximum_reconstructed_normal_tangent_dot_abs <= ORTHOGONALITY_TOLERANCE
        and handedness_mismatch_count == 0
    )

    # Fail-closed sensitivity: move the exact elbow-ring source vertex by 1 mm at
    # peak deformation by perturbing every UV-split render representative equally.
    # This avoids introducing a fake seam split while proving the reconstruction
    # responds to real posed-shape drift.
    counts = Counter(render_source_indices)
    if counts[MUTATION_SOURCE_INDEX] <= 0:
        raise ValueError("mutation source vertex is absent from render mapping")
    peak_sample = max(range(KEY_COUNT), key=lambda index: _quat_angle_deg(decoded["ROTATIONS"][index]))
    mutated_render_positions = [list(value) for value in skinned_render_positions_by_key[peak_sample]]
    mutated_render_indices = [
        index for index, source_index in enumerate(render_source_indices)
        if source_index == MUTATION_SOURCE_INDEX
    ]
    for render_index in mutated_render_indices:
        mutated_render_positions[render_index][0] += MUTATION_DELTA_M
    mutated_source_positions, mutated_split_residual = _collapse_render_positions_to_source(
        mutated_render_positions,
        render_source_indices,
        source_vertex_count,
    )
    mutated_frame = _derive_posed_tangent_frame(
        right_candidate, static_basis, mutated_source_positions
    )
    mutated_residual = _frame_residual(mutated_frame, owner_frames[peak_sample])
    mutation_direction_signal_deg = max(
        mutated_residual["maximum_normal_angle_deg"],
        mutated_residual["maximum_tangent_angle_deg"],
    )
    if mutated_split_residual > SPLIT_POSITION_TOLERANCE_M:
        raise ValueError("coherent mutation unexpectedly broke UV-split position identity")
    if mutation_direction_signal_deg < MUTATION_MIN_DIRECTION_SIGNAL_DEG:
        raise ValueError("1 mm posed-shape mutation did not produce a sufficient direction-frame signal")

    state = PASS_STATE if reconstruction_pass else HOLD_STATE
    representative_indices = [0, 10, 20, 30, 40]
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "premise": {
            "transport_audit_state": transport_audit["state"],
            "static_direction_transport_gate": transport_audit["direction_frames"]["equivalence_gate"],
            "static_normal_deformation_excess_deg": transport_audit["direction_frames"]["normal_deformation_excess_deg"],
            "static_corrected_tangent_deformation_excess_deg": transport_audit["direction_frames"]["corrected_tangent_deformation_excess_deg"],
            "transported_weighting": BASELINE_WEIGHTING,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        },
        "motion_boundary": {
            "authored_key_count": KEY_COUNT,
            "time_start_seconds": float(decoded["TIMES"][0]),
            "time_end_seconds": float(decoded["TIMES"][-1]),
            "minimum_angle_deg": min(_quat_angle_deg(value) for value in decoded["ROTATIONS"]),
            "maximum_angle_deg": max(_quat_angle_deg(value) for value in decoded["ROTATIONS"]),
            "representative_samples": [rows[index] for index in representative_indices],
        },
        "reconstruction": {
            "method": "REBUILD_SOURCE_POSE_FROM_TRANSPORTED_SKINNED_POSITIONS_THEN_REDERIVE_GEOMETRY_OWNER_FRAME",
            "render_vertex_count": RENDER_VERTEX_COUNT,
            "source_vertex_count": source_vertex_count,
            "maximum_uv_split_position_residual_m": maximum_split_residual_m,
            "split_position_tolerance_m": SPLIT_POSITION_TOLERANCE_M,
            "maximum_owner_position_residual_m": maximum_reconstructed_position_residual_m,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "maximum_owner_normal_angle_deg": maximum_reconstructed_normal_angle_deg,
            "maximum_owner_tangent_angle_deg": maximum_reconstructed_tangent_angle_deg,
            "direction_tolerance_deg": DIRECTION_TOLERANCE_DEG,
            "maximum_normal_tangent_dot_abs": maximum_reconstructed_normal_tangent_dot_abs,
            "orthogonality_tolerance": ORTHOGONALITY_TOLERANCE,
            "tangent_handedness_mismatch_count": handedness_mismatch_count,
            "gate": "PASS" if reconstruction_pass else "HOLD",
        },
        "all_41_key_samples": rows,
        "negative_controls": {
            "coherent_posed_shape_mutation": {
                "source_vertex": MUTATION_SOURCE_INDEX,
                "render_representatives": mutated_render_indices,
                "peak_sample": peak_sample,
                "delta_m": MUTATION_DELTA_M,
                "uv_split_position_residual_m": mutated_split_residual,
                "maximum_owner_normal_angle_deg": mutated_residual["maximum_normal_angle_deg"],
                "maximum_owner_tangent_angle_deg": mutated_residual["maximum_tangent_angle_deg"],
                "direction_signal_deg": mutation_direction_signal_deg,
                "minimum_required_signal_deg": MUTATION_MIN_DIRECTION_SIGNAL_DEG,
                "status": "PASS_MUTATION_DETECTED",
            }
        },
        "truth_boundary": {
            "source_modified": False,
            "rig_modified": False,
            "weights_modified": False,
            "uv_modified": False,
            "animation_modified": False,
            "technical_art_glb_modified": False,
            "geometry_owner_frame_algorithm_modified": False,
            "receiver_reconstruction_is_measurement_only": True,
            "post_skin_owner_frame_reconstruction_established": reconstruction_pass,
            "technical_art_adopted_reconstruction": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "shaded_visual_quality_accepted": False,
            "canon_claimed": False,
        },
    }
