"""Rigging-owned deformed-normal observer for the exact Animal elbow rig.

This module does not author a new normal policy, rig, weighting rule, topology, or
animation. It consumes Geometry's exact logical-quad normal derivation and the
established bilateral Rigging plan/weighting profiles, re-derives the normal
field on each discrete posed surface, and records only bounded structural
coherence evidence.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .bilateral_logical_quad_normals import derive_logical_quad_normals
from .bilateral_mirror_surface_topology import inspect_exact_mirror_surface_repair
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
from .connected_deformation import BASELINE_WEIGHTING, digest
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP

EVIDENCE_SCHEMA = "axm.animal-bilateral-deformed-logical-quad-normals/v0.1"
PASS_STATE = "PASS_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_DEFORMATION_DENSE_SWEEPS"
NORMAL_GEOMETRY_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
MATERIALS_REVIEW_HEAD = "a2cd0a6135a7c8502aef9572f7079a3dd2632103"
TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
RIGGING_MIRROR_SURFACE_HEAD = "4acd9286140dd008f2a4f01ff513912497313e4f"
NORMAL_MODULE_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
RIGGING_SOURCE_MODULE_BLOB = "f0cdcd7bf2452e73070efc872f53274a5ae3bcba"
RIGGING_MIRROR_MODULE_BLOB = "038f71f598ab51f47f023b6f33ec1bcc1bedaa7b"
NORMAL_TOLERANCE = 1e-9
REPRESENTATIVE_ANGLES_DEG = (-60.0, -30.0, 0.0, 30.0, 60.0)


def _ring_index(ring: int, segment: int, segments: int) -> int:
    return 1 + ring * segments + (segment % segments)


def _pose_local_path_points(candidate: dict[str, Any], posed_positions: list[list[float]]) -> list[list[float]]:
    segments = int(candidate["segments"])
    ring_count = len(candidate["path_points"])
    points: list[list[float]] = []
    for ring in range(ring_count):
        ring_points = [posed_positions[_ring_index(ring, segment, segments)] for segment in range(segments)]
        points.append([
            sum(point[axis] for point in ring_points) / float(segments)
            for axis in range(3)
        ])
    return points


def _posed_candidate(candidate: dict[str, Any], posed_positions: list[list[float]]) -> dict[str, Any]:
    if len(posed_positions) != len(candidate["positions"]):
        raise ValueError("posed position count drift")
    posed = copy.deepcopy(candidate)
    posed["positions"] = [list(map(float, point)) for point in posed_positions]
    posed["path_points"] = _pose_local_path_points(candidate, posed["positions"])
    return posed


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _dot(a: list[float], b: list[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _reflect_y(value: list[float]) -> list[float]:
    return [float(value[0]), -float(value[1]), float(value[2])]


def _vertex_pairs(candidate: dict[str, Any]) -> list[tuple[int, int]]:
    segments = int(candidate["segments"])
    ring_count = len(candidate["path_points"])
    if segments != 10 or ring_count != 4 or len(candidate["positions"]) != 42:
        raise ValueError("deformed-normal mirror proof requires exact 42-vertex 10-segment elbow chain")
    pairs: list[tuple[int, int]] = [(0, 0)]
    for ring in range(ring_count):
        start = 1 + ring * segments
        pairs.extend(
            (start + left_segment, start + right_segment)
            for left_segment, right_segment in enumerate(RING_SEGMENT_MAP)
        )
    pairs.append((len(candidate["positions"]) - 1, len(candidate["positions"]) - 1))
    return pairs


def _probe_deformed_normal_field(
    candidate: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    side: str,
    weighting: str,
) -> dict[str, Any]:
    structural = _probe_side(candidate, spec, plan, side, weighting)
    static_field = derive_logical_quad_normals(candidate)
    rows: list[dict[str, Any]] = []

    for pose in structural["poses"]:
        posed = _posed_candidate(candidate, pose["positions"])
        field = derive_logical_quad_normals(posed)
        normals = [list(map(float, normal)) for normal in field["normals"]]
        finite = all(math.isfinite(value) for normal in normals for value in normal)
        neutral_residual = None
        if float(pose["angle_deg"]) == 0.0:
            neutral_residual = max(
                _distance(before, after)
                for before, after in zip(static_field["normals"], normals)
            )
        passed = (
            pose["status"] == "PASS"
            and finite
            and field["normal_count"] == len(candidate["positions"])
            and float(field["maximum_unit_length_error"]) <= NORMAL_TOLERANCE
            and float(field["minimum_ring_outward_radial_dot"]) > 0.0
            and (neutral_residual is None or neutral_residual <= NORMAL_TOLERANCE)
        )
        rows.append({
            "angle_deg": float(pose["angle_deg"]),
            "status": "PASS" if passed else "FAIL",
            "positions": [list(map(float, point)) for point in pose["positions"]],
            "normals": normals,
            "normal_count": int(field["normal_count"]),
            "maximum_unit_length_error": float(field["maximum_unit_length_error"]),
            "minimum_ring_outward_radial_dot": float(field["minimum_ring_outward_radial_dot"]),
            "neutral_static_normal_max_residual": neutral_residual,
            "structural_pose_status": pose["status"],
            "collapsed_triangles": int(pose["collapsed_triangles"]),
            "nonadjacent_self_intersection_pairs": int(pose["nonadjacent_self_intersection_pairs"]),
        })

    minimum_adjacent_normal_dot = 1.0
    maximum_adjacent_normal_delta = 0.0
    for previous, current in zip(rows, rows[1:]):
        for before, after in zip(previous["normals"], current["normals"]):
            minimum_adjacent_normal_dot = min(minimum_adjacent_normal_dot, _dot(before, after))
            maximum_adjacent_normal_delta = max(maximum_adjacent_normal_delta, _distance(before, after))

    neutral = next(row for row in rows if row["angle_deg"] == 0.0)
    gate = (
        structural["gate"] == "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP"
        and all(row["status"] == "PASS" for row in rows)
        and minimum_adjacent_normal_dot > 0.0
        and neutral["neutral_static_normal_max_residual"] is not None
        and neutral["neutral_static_normal_max_residual"] <= NORMAL_TOLERANCE
    )
    return {
        "side": side,
        "weighting": weighting,
        "joint_id": structural["joint_id"],
        "influence_radius_m": structural["influence_radius_m"],
        "weight_counts": structural["weight_counts"],
        "dense_pose_count": len(rows),
        "normal_vectors_observed": len(rows) * len(candidate["positions"]),
        "minimum_adjacent_sample_normal_dot": minimum_adjacent_normal_dot,
        "maximum_adjacent_sample_normal_delta": maximum_adjacent_normal_delta,
        "neutral_static_normal_max_residual": neutral["neutral_static_normal_max_residual"],
        "poses": rows,
        "gate": (
            "PASS_DEFORMED_LOGICAL_QUAD_NORMAL_FIELD_DENSE_SWEEP"
            if gate else "FAIL_DEFORMED_LOGICAL_QUAD_NORMAL_FIELD_DENSE_SWEEP"
        ),
    }


def _compare_bilateral_fields(left: dict[str, Any], right: dict[str, Any], left_candidate: dict[str, Any]) -> dict[str, Any]:
    if left["weighting"] != right["weighting"]:
        raise ValueError("bilateral deformed-normal weighting mismatch")
    if len(left["poses"]) != len(right["poses"]):
        raise ValueError("bilateral deformed-normal pose-count mismatch")
    pairs = _vertex_pairs(left_candidate)
    maximum_position_residual = 0.0
    maximum_normal_residual = 0.0
    for left_pose, right_pose in zip(left["poses"], right["poses"]):
        if left_pose["angle_deg"] != right_pose["angle_deg"]:
            raise ValueError("bilateral deformed-normal angle mismatch")
        for left_index, right_index in pairs:
            maximum_position_residual = max(
                maximum_position_residual,
                _distance(_reflect_y(left_pose["positions"][left_index]), right_pose["positions"][right_index]),
            )
            maximum_normal_residual = max(
                maximum_normal_residual,
                _distance(_reflect_y(left_pose["normals"][left_index]), right_pose["normals"][right_index]),
            )
    passed = maximum_position_residual <= MIRROR_TOLERANCE and maximum_normal_residual <= NORMAL_TOLERANCE
    return {
        "weighting": left["weighting"],
        "pose_count": len(left["poses"]),
        "maximum_mirrored_pose_residual_m": maximum_position_residual,
        "maximum_mirrored_normal_residual": maximum_normal_residual,
        "gate": "PASS_EXACT_MIRRORED_POSES_AND_DEFORMED_NORMALS" if passed else "FAIL_EXACT_MIRRORED_POSES_OR_DEFORMED_NORMALS",
    }


def _representative(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_angle = {float(row["angle_deg"]): row for row in rows}
    return {str(int(angle)): by_angle[angle] for angle in REPRESENTATIVE_ANGLES_DEG}


def inspect_bilateral_deformed_logical_quad_normals(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
) -> dict[str, Any]:
    """Re-observe Geometry's explicit normal field under the exact current rig."""
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile digest drift")
    _validate_weighting_profile(weighting_profile, plan)

    left_candidate, right_candidate, geometry = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, plan
    )
    static_left = derive_logical_quad_normals(left_candidate)
    static_right = derive_logical_quad_normals(right_candidate)

    probes: dict[str, dict[str, dict[str, Any]]] = {"left": {}, "right": {}}
    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            probes[side][weighting] = _probe_deformed_normal_field(candidate, spec, plan, side, weighting)

    mirror = {
        weighting: _compare_bilateral_fields(
            probes["left"][weighting], probes["right"][weighting], left_candidate
        )
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    }

    all_probe_pass = all(
        probes[side][weighting]["gate"] == "PASS_DEFORMED_LOGICAL_QUAD_NORMAL_FIELD_DENSE_SWEEP"
        for side in ("left", "right")
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    )
    all_mirror_pass = all(
        row["gate"] == "PASS_EXACT_MIRRORED_POSES_AND_DEFORMED_NORMALS"
        for row in mirror.values()
    )
    state = PASS_STATE if all_probe_pass and all_mirror_pass else "FAIL_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_DEFORMATION_DENSE_SWEEPS"

    total_pose_fields = 4 * len(DENSE_ANGLES_DEG)
    total_normal_vectors = total_pose_fields * len(left_candidate["positions"])
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "identity": {
            "geometry_logical_quad_normal_head": NORMAL_GEOMETRY_HEAD,
            "materials_static_review_head": MATERIALS_REVIEW_HEAD,
            "topology_head": TOPOLOGY_HEAD,
            "historical_exact_mirror_rigging_head": RIGGING_MIRROR_SURFACE_HEAD,
            "historical_rig_plan_donor_head": RIG_DONOR_HEAD,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
            "normal_module_blob": NORMAL_MODULE_BLOB,
            "rigging_source_module_blob": RIGGING_SOURCE_MODULE_BLOB,
            "rigging_mirror_module_blob": RIGGING_MIRROR_MODULE_BLOB,
            "left_source_candidate_digest": static_left["source_candidate_digest"],
            "right_source_candidate_digest": static_right["source_candidate_digest"],
        },
        "method": "RE_DERIVE_GEOMETRY_LOGICAL_QUAD_NORMAL_FIELD_FROM_EXACT_RIG_POSED_POSITIONS_USING_POSE_LOCAL_RING_CENTERS",
        "tangent_policy": static_left["tangent_policy"],
        "geometry_prerequisite_state": geometry["state"],
        "total_pose_fields": total_pose_fields,
        "total_normal_vectors_observed": total_normal_vectors,
        "left": {
            BASELINE_WEIGHTING: {**probes["left"][BASELINE_WEIGHTING], "representative_poses": _representative(probes["left"][BASELINE_WEIGHTING]["poses"])},
            CANDIDATE_WEIGHTING: {**probes["left"][CANDIDATE_WEIGHTING], "representative_poses": _representative(probes["left"][CANDIDATE_WEIGHTING]["poses"])},
        },
        "right": {
            BASELINE_WEIGHTING: {**probes["right"][BASELINE_WEIGHTING], "representative_poses": _representative(probes["right"][BASELINE_WEIGHTING]["poses"])},
            CANDIDATE_WEIGHTING: {**probes["right"][CANDIDATE_WEIGHTING], "representative_poses": _representative(probes["right"][CANDIDATE_WEIGHTING]["poses"])},
        },
        "bilateral_mirror_evidence": mirror,
        "truth_boundary": {
            "source_or_topology_modified_by_rigging": False,
            "rig_or_weights_modified": False,
            "geometry_normal_policy_modified": False,
            "tangent_policy_established": False,
            "production_skin_normal_transport_established": False,
            "continuous_real_angle_normal_field_proven": False,
            "shaded_deformed_visual_quality_accepted": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "canon_claimed": False,
        },
        "handoffs": {
            "geometry_materials_visual": "The exact Geometry logical-quad normal derivation remains structurally coherent across these sampled rig poses; Materials / Visual QA / Art Direction still own shaded deformed-normal judgment and tangent policy.",
            "animation": "This observer changes no clip or timing and does not grant Animation acceptance. Animation must explicitly rebind playback to the exact Geometry #13 / Rigging #15 successor chain.",
            "technical_art_runtime": "No exported skeleton/skin/normal transport, GLB animation channel, engine controller, wall-clock playback, or target-device behavior is established.",
        },
        "non_claims": [
            "The one-degree -60..+60 observations are finite sampled fields, not mathematical proof over every real-valued angle.",
            "Re-deriving normals from posed geometry is an evidence observer, not a production skin-normal transport implementation.",
            "No tangents or UV basis are established.",
            "No shaded deformation quality, anatomy, volume preservation, skin sliding, or final visual acceptance is established.",
            "No Animation timing/playback acceptance or Runtime/controller/gameplay acceptance is established.",
            "No CANON, production readiness, game readiness, or Rigging mastery is claimed.",
        ],
    }
