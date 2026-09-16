"""Rigging-owned deformed tangent-frame observer for the exact Animal elbow rig.

This module does not author a new UV policy, tangent policy, rig, weighting rule,
topology, normal policy, animation, or runtime implementation. It consumes
Geometry PR #20's exact structural UV/tangent basis, keeps those UV coordinates
fixed as surface attributes, poses the already-proven bilateral elbow rig, reuses
Geometry PR #16's exact logical-quad normal derivation on each posed surface, and
re-derives a tangent frame from posed positions + the unchanged UVs.

The result is bounded structural evidence over the existing integer-angle Rigging
envelope. It is not production tangent transport and it does not accept shaded
motion, Animation playback, Technical-Art transport, or Runtime behaviour.
"""
from __future__ import annotations

import math
from typing import Any

from .bilateral_deformed_logical_quad_normals import (
    PASS_STATE as DEFORMED_NORMAL_PASS_STATE,
    _posed_candidate,
    inspect_bilateral_deformed_logical_quad_normals,
)
from .bilateral_logical_quad_normals import derive_logical_quad_normals
from .bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from .bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    DENSE_ANGLES_DEG,
    MIRROR_TOLERANCE,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _probe_side,
    _validate_weighting_profile,
)
from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .bilateral_uv_tangent_basis import (
    BASIS_ID,
    RECORD_SCHEMA as UV_TANGENT_RECORD_SCHEMA,
    derive_uv_tangent_basis,
    inspect_bilateral_uv_tangent_basis,
)
from .connected_deformation import BASELINE_WEIGHTING, digest

EVIDENCE_SCHEMA = "axm.animal-bilateral-deformed-tangent-frame-observer/v0.1"
PASS_STATE = "PASS_BILATERAL_DEFORMED_TANGENT_FRAME_DENSE_SWEEPS"
GEOMETRY_UV_TANGENT_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
PARENT_RIGGING_HEAD = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
GEOMETRY_UV_TANGENT_MODULE_BLOB = "ba0b4e620f132413606177358e47bd32ae4d4965"
DEFORMED_NORMAL_MODULE_BLOB = "b8df083310727dcd05e7476b2158a081a5c25c8f"
RIGGING_SOURCE_MODULE_BLOB = "f0cdcd7bf2452e73070efc872f53274a5ae3bcba"
TANGENT_TOLERANCE = 1e-9
EPSILON = 1e-12
REPRESENTATIVE_ANGLES_DEG = (-60.0, -30.0, 0.0, 30.0, 60.0)


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(len(a)))


def _mul(a, scalar):
    return tuple(float(value) * float(scalar) for value in a)


def _dot(a, b):
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _length(value):
    return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    length = _length(value)
    if length <= EPSILON:
        raise ValueError(f"{label} has zero length")
    return _mul(value, 1.0 / length)


def _distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _reflect_y(value):
    return [float(value[0]), -float(value[1]), float(value[2])]


def _triangle_tangent(p0, p1, p2, uv0, uv1, uv2):
    e1 = _sub(p1, p0)
    e2 = _sub(p2, p0)
    duv1 = _sub(uv1, uv0)
    duv2 = _sub(uv2, uv0)
    determinant = duv1[0] * duv2[1] - duv1[1] * duv2[0]
    if abs(determinant) <= EPSILON:
        raise ValueError("fixed Geometry UV basis contains a UV-degenerate posed triangle")
    reciprocal = 1.0 / determinant
    tangent = _mul(
        _sub(_mul(e1, duv2[1]), _mul(e2, duv1[1])),
        reciprocal,
    )
    bitangent = _mul(
        _sub(_mul(e2, duv1[0]), _mul(e1, duv2[0])),
        reciprocal,
    )
    return tangent, bitangent


def _derive_posed_tangent_frame(
    candidate: dict[str, Any],
    static_basis: dict[str, Any],
    posed_positions: list[list[float]],
) -> dict[str, Any]:
    """Re-derive tangents on one pose while keeping Geometry's UV basis fixed."""
    if static_basis.get("schema") != UV_TANGENT_RECORD_SCHEMA:
        raise ValueError("static UV/tangent basis schema drift")
    if static_basis.get("id") != BASIS_ID:
        raise ValueError("static UV/tangent basis identity drift")
    if len(posed_positions) != int(static_basis["source_vertex_count"]):
        raise ValueError("posed source-vertex count drift")

    posed_candidate = _posed_candidate(candidate, posed_positions)
    source_normals = derive_logical_quad_normals(posed_candidate)["normals"]
    render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
    render_positions = [
        [float(value) for value in posed_positions[source_index]]
        for source_index in render_source_indices
    ]
    render_normals = [
        [float(value) for value in source_normals[source_index]]
        for source_index in render_source_indices
    ]
    render_uvs = [
        [float(value) for value in uv]
        for uv in static_basis["render_uvs"]
    ]
    render_indices = [int(value) for value in static_basis["render_indices"]]
    if len(render_indices) % 3:
        raise ValueError("render index count drift")

    tangent_accum = [(0.0, 0.0, 0.0) for _ in render_positions]
    bitangent_accum = [(0.0, 0.0, 0.0) for _ in render_positions]
    for offset in range(0, len(render_indices), 3):
        ia, ib, ic = render_indices[offset:offset + 3]
        tangent, bitangent = _triangle_tangent(
            render_positions[ia],
            render_positions[ib],
            render_positions[ic],
            render_uvs[ia],
            render_uvs[ib],
            render_uvs[ic],
        )
        for vertex in (ia, ib, ic):
            tangent_accum[vertex] = _add(tangent_accum[vertex], tangent)
            bitangent_accum[vertex] = _add(bitangent_accum[vertex], bitangent)

    tangents = []
    maximum_tangent_unit_length_error = 0.0
    maximum_tangent_normal_dot_abs = 0.0
    for index, (normal_value, tangent_sum, bitangent_sum) in enumerate(
        zip(render_normals, tangent_accum, bitangent_accum)
    ):
        normal = _unit(normal_value, f"posed normal[{index}]")
        projected = _sub(tangent_sum, _mul(normal, _dot(normal, tangent_sum)))
        tangent = _unit(projected, f"posed tangent[{index}]")
        handedness_probe = _dot(_cross(normal, tangent), bitangent_sum)
        if abs(handedness_probe) <= EPSILON:
            raise ValueError(f"posed tangent[{index}] has ambiguous handedness")
        tangent4 = [
            float(tangent[0]),
            float(tangent[1]),
            float(tangent[2]),
            1.0 if handedness_probe > 0.0 else -1.0,
        ]
        tangents.append(tangent4)
        maximum_tangent_unit_length_error = max(
            maximum_tangent_unit_length_error,
            abs(_length(tangent4[:3]) - 1.0),
        )
        maximum_tangent_normal_dot_abs = max(
            maximum_tangent_normal_dot_abs,
            abs(_dot(normal, tangent4[:3])),
        )

    return {
        "render_positions": render_positions,
        "render_normals": render_normals,
        "render_uvs": render_uvs,
        "render_tangents": tangents,
        "render_indices": render_indices,
        "render_source_indices": render_source_indices,
        "semantic_vertex_keys": list(static_basis["semantic_vertex_keys"]),
        "maximum_tangent_unit_length_error": maximum_tangent_unit_length_error,
        "maximum_tangent_normal_dot_abs": maximum_tangent_normal_dot_abs,
    }


def _frame_residual(frame: dict[str, Any], static_basis: dict[str, Any], field: str, *, xyz_only: bool = False) -> float:
    current = frame[field]
    baseline = static_basis[field]
    if len(current) != len(baseline):
        raise ValueError(f"{field} count drift")
    maximum = 0.0
    for left, right in zip(current, baseline):
        if xyz_only:
            maximum = max(maximum, _distance(left[:3], right[:3]))
        else:
            maximum = max(maximum, _distance(left, right))
    return maximum


def _probe_tangent_sweep(candidate, spec, plan, side: str, weighting: str):
    static_basis = derive_uv_tangent_basis(candidate, side=side)
    structural = _probe_side(candidate, spec, plan, side, weighting)
    if structural["gate"] != "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP":
        raise ValueError(f"{side}/{weighting} structural prerequisite is not PASS")

    frames_by_angle: dict[float, dict[str, Any]] = {}
    previous_frame = None
    minimum_adjacent_sample_tangent_dot = 1.0
    maximum_tangent_unit_length_error = 0.0
    maximum_tangent_normal_dot_abs = 0.0
    maximum_uv_residual = 0.0
    handedness_drift_count = 0
    neutral_static_tangent_max_residual = None
    neutral_static_normal_max_residual = None
    representative_frames = {}

    static_tangents = static_basis["render_tangents"]
    static_uvs = static_basis["render_uvs"]
    for pose in structural["poses"]:
        angle = float(pose["angle_deg"])
        frame = _derive_posed_tangent_frame(candidate, static_basis, pose["positions"])
        frames_by_angle[angle] = frame
        maximum_tangent_unit_length_error = max(
            maximum_tangent_unit_length_error,
            float(frame["maximum_tangent_unit_length_error"]),
        )
        maximum_tangent_normal_dot_abs = max(
            maximum_tangent_normal_dot_abs,
            float(frame["maximum_tangent_normal_dot_abs"]),
        )
        for current_uv, static_uv in zip(frame["render_uvs"], static_uvs):
            maximum_uv_residual = max(maximum_uv_residual, _distance(current_uv, static_uv))
        handedness_drift_count += sum(
            1
            for current, static in zip(frame["render_tangents"], static_tangents)
            if float(current[3]) != float(static[3])
        )
        if previous_frame is not None:
            for previous, current in zip(previous_frame["render_tangents"], frame["render_tangents"]):
                minimum_adjacent_sample_tangent_dot = min(
                    minimum_adjacent_sample_tangent_dot,
                    _dot(previous[:3], current[:3]),
                )
        previous_frame = frame

        if angle == 0.0:
            neutral_static_tangent_max_residual = _frame_residual(
                frame,
                static_basis,
                "render_tangents",
                xyz_only=True,
            )
            neutral_static_normal_max_residual = _frame_residual(
                frame,
                static_basis,
                "render_normals",
            )
        if angle in REPRESENTATIVE_ANGLES_DEG:
            representative_frames[str(int(angle))] = {
                "angle_deg": angle,
                "render_positions": frame["render_positions"],
                "render_normals": frame["render_normals"],
                "render_uvs": frame["render_uvs"],
                "render_tangents": frame["render_tangents"],
                "semantic_vertex_keys": frame["semantic_vertex_keys"],
            }

    if neutral_static_tangent_max_residual is None or neutral_static_normal_max_residual is None:
        raise ValueError("dense sweep did not include neutral pose")
    passed = (
        maximum_tangent_unit_length_error <= TANGENT_TOLERANCE
        and maximum_tangent_normal_dot_abs <= TANGENT_TOLERANCE
        and maximum_uv_residual <= TANGENT_TOLERANCE
        and handedness_drift_count == 0
        and neutral_static_tangent_max_residual <= TANGENT_TOLERANCE
        and neutral_static_normal_max_residual <= TANGENT_TOLERANCE
        and minimum_adjacent_sample_tangent_dot > 0.0
    )
    return {
        "side": side,
        "weighting": weighting,
        "dense_pose_count": len(frames_by_angle),
        "render_vertices_per_pose": int(static_basis["render_vertex_count"]),
        "tangent_vectors_observed": len(frames_by_angle) * int(static_basis["render_vertex_count"]),
        "maximum_tangent_unit_length_error": maximum_tangent_unit_length_error,
        "maximum_tangent_normal_dot_abs": maximum_tangent_normal_dot_abs,
        "maximum_uv_residual": maximum_uv_residual,
        "handedness_drift_count": handedness_drift_count,
        "minimum_adjacent_sample_tangent_dot": minimum_adjacent_sample_tangent_dot,
        "neutral_static_tangent_max_residual": neutral_static_tangent_max_residual,
        "neutral_static_normal_max_residual": neutral_static_normal_max_residual,
        "static_basis_digest": digest(static_basis),
        "representative_frames": representative_frames,
        "gate": "PASS_DEFORMED_TANGENT_FRAME_DENSE_SWEEP" if passed else "FAIL_DEFORMED_TANGENT_FRAME_DENSE_SWEEP",
    }, frames_by_angle, static_basis


def _bilateral_frame_comparison(left_frames, right_frames, left_static, right_static):
    left_keys = list(left_static["semantic_vertex_keys"])
    right_keys = list(right_static["semantic_vertex_keys"])
    if len(set(left_keys)) != len(left_keys) or len(set(right_keys)) != len(right_keys):
        raise ValueError("semantic render-vertex keys must be unique")
    right_index_by_key = {key: index for index, key in enumerate(right_keys)}
    if set(left_keys) != set(right_keys):
        raise ValueError("left/right semantic render-vertex key identity drift")

    maximum_mirrored_position_residual_m = 0.0
    maximum_mirrored_normal_residual = 0.0
    maximum_uv_residual = 0.0
    maximum_mirrored_tangent_xyz_residual = 0.0
    tangent_handedness_mismatch_count = 0
    for angle in DENSE_ANGLES_DEG:
        left = left_frames[float(angle)]
        right = right_frames[float(angle)]
        for left_index, key in enumerate(left_keys):
            right_index = right_index_by_key[key]
            maximum_mirrored_position_residual_m = max(
                maximum_mirrored_position_residual_m,
                _distance(_reflect_y(left["render_positions"][left_index]), right["render_positions"][right_index]),
            )
            maximum_mirrored_normal_residual = max(
                maximum_mirrored_normal_residual,
                _distance(_reflect_y(left["render_normals"][left_index]), right["render_normals"][right_index]),
            )
            maximum_uv_residual = max(
                maximum_uv_residual,
                _distance(left["render_uvs"][left_index], right["render_uvs"][right_index]),
            )
            maximum_mirrored_tangent_xyz_residual = max(
                maximum_mirrored_tangent_xyz_residual,
                _distance(_reflect_y(left["render_tangents"][left_index][:3]), right["render_tangents"][right_index][:3]),
            )
            if float(right["render_tangents"][right_index][3]) != -float(left["render_tangents"][left_index][3]):
                tangent_handedness_mismatch_count += 1

    passed = (
        maximum_mirrored_position_residual_m <= MIRROR_TOLERANCE
        and maximum_mirrored_normal_residual <= MIRROR_TOLERANCE
        and maximum_uv_residual <= MIRROR_TOLERANCE
        and maximum_mirrored_tangent_xyz_residual <= MIRROR_TOLERANCE
        and tangent_handedness_mismatch_count == 0
    )
    return {
        "maximum_mirrored_position_residual_m": maximum_mirrored_position_residual_m,
        "maximum_mirrored_normal_residual": maximum_mirrored_normal_residual,
        "maximum_uv_residual": maximum_uv_residual,
        "maximum_mirrored_tangent_xyz_residual": maximum_mirrored_tangent_xyz_residual,
        "tangent_handedness_mismatch_count": tangent_handedness_mismatch_count,
        "gate": "PASS_EXACT_MIRRORED_DEFORMED_TANGENT_FRAMES" if passed else "FAIL_EXACT_MIRRORED_DEFORMED_TANGENT_FRAMES",
    }


def inspect_bilateral_deformed_tangent_frames(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
) -> dict[str, Any]:
    """Inspect the exact Geometry tangent basis across the exact Rigging envelope."""
    observed_weighting_digest = _validate_weighting_profile(weighting_profile, plan)
    if observed_weighting_digest != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile digest drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")

    left_candidate, historical_right, topology_prerequisite = build_bilateral_source_successor_topology_rebind(
        spec,
        left_profile,
        bilateral_profile,
    )
    right_candidate, mirror_topology = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_left, static_right, static_record = inspect_bilateral_uv_tangent_basis(
        spec,
        left_profile,
        bilateral_profile,
    )
    if static_record.get("state") != "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD":
        raise ValueError("Geometry UV/tangent structural prerequisite is not PASS")

    normal_receipt = inspect_bilateral_deformed_logical_quad_normals(
        spec,
        left_profile,
        bilateral_profile,
        plan,
        weighting_profile,
    )
    if normal_receipt.get("state") != DEFORMED_NORMAL_PASS_STATE:
        raise ValueError("deformed logical-quad normal prerequisite is not PASS")

    side_receipts = {"left": {}, "right": {}}
    frames = {"left": {}, "right": {}}
    static = {"left": None, "right": None}
    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            receipt, frames_by_angle, static_basis = _probe_tangent_sweep(
                candidate,
                spec,
                plan,
                side,
                weighting,
            )
            side_receipts[side][weighting] = receipt
            frames[side][weighting] = frames_by_angle
            if static[side] is None:
                static[side] = static_basis
            elif digest(static[side]) != digest(static_basis):
                raise ValueError(f"{side} static tangent basis changed between weighting probes")

    bilateral = {}
    for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
        bilateral[weighting] = _bilateral_frame_comparison(
            frames["left"][weighting],
            frames["right"][weighting],
            static["left"],
            static["right"],
        )

    all_side_pass = all(
        side_receipts[side][weighting]["gate"] == "PASS_DEFORMED_TANGENT_FRAME_DENSE_SWEEP"
        for side in ("left", "right")
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    )
    all_mirror_pass = all(
        bilateral[weighting]["gate"] == "PASS_EXACT_MIRRORED_DEFORMED_TANGENT_FRAMES"
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    )
    state = PASS_STATE if all_side_pass and all_mirror_pass else "HOLD_DEFORMED_TANGENT_FRAME_OBSERVER"
    total_pose_fields = 4 * len(DENSE_ANGLES_DEG)
    total_tangent_vectors_observed = sum(
        side_receipts[side][weighting]["tangent_vectors_observed"]
        for side in ("left", "right")
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    )

    return {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "geometry_uv_tangent_head": GEOMETRY_UV_TANGENT_HEAD,
        "parent_rigging_head": PARENT_RIGGING_HEAD,
        "geometry_uv_tangent_module_blob": GEOMETRY_UV_TANGENT_MODULE_BLOB,
        "deformed_normal_module_blob": DEFORMED_NORMAL_MODULE_BLOB,
        "rigging_source_module_blob": RIGGING_SOURCE_MODULE_BLOB,
        "rig_donor_head": RIG_DONOR_HEAD,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "basis_id": BASIS_ID,
        "static_geometry_record_digest": digest(static_record),
        "topology_prerequisite_digest": digest(topology_prerequisite),
        "mirror_topology_digest": digest(mirror_topology),
        "deformed_normal_prerequisite_state": normal_receipt["state"],
        "tested_angles_deg": list(DENSE_ANGLES_DEG),
        "total_pose_fields": total_pose_fields,
        "render_vertices_per_pose": int(static_left["render_vertex_count"]),
        "total_tangent_vectors_observed": total_tangent_vectors_observed,
        "left": side_receipts["left"],
        "right": side_receipts["right"],
        "bilateral_mirror_evidence": bilateral,
        "truth_boundary": {
            "source_or_topology_modified_by_rigging": False,
            "rig_or_weights_modified": False,
            "geometry_uv_policy_modified": False,
            "geometry_normal_policy_modified": False,
            "geometry_structural_tangent_basis_consumed": True,
            "fixed_uvs_preserved_across_pose_observer": True,
            "deformed_tangent_frame_observer_established": True,
            "production_skin_tangent_transport_established": False,
            "tangent_space_normal_map_rendered": False,
            "shaded_deformed_visual_quality_accepted": False,
            "animation_accepted": False,
            "technical_art_transport_accepted": False,
            "runtime_or_controller_accepted": False,
            "canon_claimed": False,
        },
    }
