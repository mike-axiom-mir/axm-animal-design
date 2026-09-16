"""Rigging rebind for Geometry's exact bilateral mirror-surface successor.

This module consumes the exact Geometry PR #13 topology identity and reapplies the
already-proven Animal elbow rig and weighting profile without changing source
positions, joints, weights, pose semantics, or topology.  It exists to close the
previous Rigging surface-metric HOLD by direct remeasurement on the new topology;
it does not grant Animation, visual, runtime, gameplay, or CANON acceptance.
"""
from __future__ import annotations

import math
from typing import Any

from .bilateral_mirror_surface_topology import inspect_exact_mirror_surface_repair
from .bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    DENSE_ANGLES_DEG,
    MIRROR_TOLERANCE,
    REPRESENTATIVE_ANGLES_DEG,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _boundary_comparison,
    _probe_side,
    _validate_weighting_profile,
)
from .connected_deformation import BASELINE_WEIGHTING, digest
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP

EVIDENCE_SCHEMA = "axm.animal-bilateral-mirror-surface-rigging-rebind/v0.1"
GEOMETRY_MIRROR_SURFACE_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
PREVIOUS_BILATERAL_RIGGING_HEAD = "94bc573e2e06ba7a35c9908c141e2f939d4739a8"
ORGANIC_BILATERAL_HEAD = "4df3024b4c459675422565501a46f622acf229a9"
PASS_STATE = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_RIGGING_REBIND_DENSE_SWEEPS"
FAIL_STATE = "FAIL_BILATERAL_EXACT_MIRROR_SURFACE_RIGGING_REBIND_DENSE_SWEEPS"

_METRIC_KEYS = (
    "minimum_triangle_area_ratio",
    "maximum_triangle_area_ratio",
    "minimum_edge_length_ratio",
    "maximum_edge_length_ratio",
)


def _vertex_pairs(candidate: dict[str, Any]) -> list[tuple[int, int]]:
    segments = int(candidate["segments"])
    path_count = len(candidate["path_points"])
    if segments != 10 or path_count != 4 or len(candidate["positions"]) != 42:
        raise ValueError("exact bilateral Rigging mirror comparison requires the 42-vertex 10-segment chain")
    pairs = [(0, 0)]
    for ring_index in range(path_count):
        start = 1 + ring_index * segments
        pairs.extend(
            (start + left_segment, start + right_segment)
            for left_segment, right_segment in enumerate(RING_SEGMENT_MAP)
        )
    pairs.append((len(candidate["positions"]) - 1, len(candidate["positions"]) - 1))
    if len(pairs) != len(candidate["positions"]):
        raise ValueError("exact bilateral Rigging mirror vertex correspondence is incomplete")
    return pairs


def _reflect_y(point):
    return (float(point[0]), -float(point[1]), float(point[2]))


def compare_mirror_probes(left_probe, right_probe, candidate) -> dict[str, Any]:
    """Compare two independently probed sides under the exact Organic correspondence."""
    left_rows = {row["angle_deg"]: row for row in left_probe["poses"]}
    right_rows = {row["angle_deg"]: row for row in right_probe["poses"]}
    if set(left_rows) != set(right_rows):
        raise ValueError("left/right dense angle sets differ")

    pairs = _vertex_pairs(candidate)
    max_pose_residual = 0.0
    max_metric_residual = 0.0
    worst_metric = None
    worst_metric_angle = None
    worst_pose_angle = None

    for angle in sorted(left_rows):
        left = left_rows[angle]
        right = right_rows[angle]
        if left["status"] != "PASS" or right["status"] != "PASS":
            raise ValueError("mirror comparison cannot hide a failed side pose")

        pose_residual = max(
            math.dist(_reflect_y(left["positions"][left_index]), right["positions"][right_index])
            for left_index, right_index in pairs
        )
        if pose_residual > max_pose_residual:
            max_pose_residual = pose_residual
            worst_pose_angle = angle

        for key in _METRIC_KEYS:
            residual = abs(float(left[key]) - float(right[key]))
            if residual > max_metric_residual:
                max_metric_residual = residual
                worst_metric = key
                worst_metric_angle = angle

    passed = max_pose_residual <= MIRROR_TOLERANCE and max_metric_residual <= MIRROR_TOLERANCE
    return {
        "weighting": left_probe["weighting"],
        "sample_count": len(left_rows),
        "maximum_mirrored_pose_residual_m": max_pose_residual,
        "worst_pose_angle_deg": worst_pose_angle,
        "maximum_structural_metric_residual": max_metric_residual,
        "worst_structural_metric": worst_metric,
        "worst_structural_metric_angle_deg": worst_metric_angle,
        "tolerance": MIRROR_TOLERANCE,
        "gate": "PASS_EXACT_MIRRORED_VERTEX_AND_SURFACE_METRICS" if passed else "FAIL_EXACT_MIRRORED_VERTEX_OR_SURFACE_METRICS",
    }


def _summary(probe) -> dict[str, Any]:
    poses = probe["poses"]
    return {
        "gate": probe["gate"],
        "dense_sample_count": probe["dense_sample_count"],
        "weight_counts": probe["weight_counts"],
        "max_weight_sum_error": probe["max_weight_sum_error"],
        "minimum_triangle_area_ratio": min(row["minimum_triangle_area_ratio"] for row in poses),
        "maximum_triangle_area_ratio": max(row["maximum_triangle_area_ratio"] for row in poses),
        "minimum_edge_length_ratio": min(row["minimum_edge_length_ratio"] for row in poses),
        "maximum_edge_length_ratio": max(row["maximum_edge_length_ratio"] for row in poses),
        "maximum_fixed_weight_vertex_drift_m": max(row["fixed_weight_vertex_max_drift_m"] for row in poses),
        "maximum_rigid_weight_radius_drift_m": max(row["rigid_weight_radius_max_drift_m"] for row in poses),
        "maximum_nonadjacent_self_intersection_pairs": max(row["nonadjacent_self_intersection_pairs"] for row in poses),
        "collapsed_triangle_total": sum(row["collapsed_triangles"] for row in poses),
    }


def _representative(probe) -> dict[str, Any]:
    wanted = set(REPRESENTATIVE_ANGLES_DEG)
    return {
        str(int(row["angle_deg"])): {
            key: value for key, value in row.items()
            if key != "self_intersection_broad_phase_pairs"
        }
        for row in probe["poses"]
        if row["angle_deg"] in wanted
    }


def inspect_bilateral_mirror_surface_rigging_rebind(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
) -> dict[str, Any]:
    """Rebind the exact historical rig/profile to Geometry's mirror-surface successor."""
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    observed_profile_digest = _validate_weighting_profile(weighting_profile, plan)
    if observed_profile_digest != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")

    left_candidate, right_candidate, geometry = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, plan
    )
    if geometry.get("state") != "PASS_BILATERAL_EXACT_MIRROR_SURFACE_TOPOLOGY_REPAIR":
        raise ValueError("exact mirror-surface Geometry prerequisite is not a PASS")

    probes: dict[str, dict[str, Any]] = {"left": {}, "right": {}}
    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        probes[side][BASELINE_WEIGHTING] = _probe_side(candidate, spec, plan, side, BASELINE_WEIGHTING)
        probes[side][CANDIDATE_WEIGHTING] = _probe_side(candidate, spec, plan, side, CANDIDATE_WEIGHTING)

    boundary = {
        side: _boundary_comparison(probes[side][BASELINE_WEIGHTING], probes[side][CANDIDATE_WEIGHTING])
        for side in ("left", "right")
    }
    mirror = {
        weighting: compare_mirror_probes(
            probes["left"][weighting], probes["right"][weighting], left_candidate
        )
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    }

    dense_pass = all(
        probes[side][weighting]["gate"] == "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP"
        for side in ("left", "right")
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING)
    )
    weighting_pass = all(
        boundary[side]["gate"] == "PASS_WEIGHTING_REFINEMENT_RECONFIRMED_ON_BILATERAL_SUCCESSOR"
        for side in ("left", "right")
    )
    mirror_pass = all(row["gate"] == "PASS_EXACT_MIRRORED_VERTEX_AND_SURFACE_METRICS" for row in mirror.values())
    passed = dense_pass and weighting_pass and mirror_pass

    return {
        "schema": EVIDENCE_SCHEMA,
        "state": PASS_STATE if passed else FAIL_STATE,
        "lineage": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "organic_bilateral_source_head": ORGANIC_BILATERAL_HEAD,
            "previous_bilateral_rigging_head": PREVIOUS_BILATERAL_RIGGING_HEAD,
            "geometry_mirror_surface_head": GEOMETRY_MIRROR_SURFACE_HEAD,
            "rig_plan_and_profile_file_donor_head": RIG_DONOR_HEAD,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        },
        "geometry_prerequisite_state": geometry["state"],
        "total_dense_pose_observations": 4 * len(DENSE_ANGLES_DEG),
        "left": {
            "baseline_summary": _summary(probes["left"][BASELINE_WEIGHTING]),
            "refined_summary": _summary(probes["left"][CANDIDATE_WEIGHTING]),
            "boundary_weighting_comparison": boundary["left"],
            "representative_poses": {
                BASELINE_WEIGHTING: _representative(probes["left"][BASELINE_WEIGHTING]),
                CANDIDATE_WEIGHTING: _representative(probes["left"][CANDIDATE_WEIGHTING]),
            },
        },
        "right": {
            "baseline_summary": _summary(probes["right"][BASELINE_WEIGHTING]),
            "refined_summary": _summary(probes["right"][CANDIDATE_WEIGHTING]),
            "boundary_weighting_comparison": boundary["right"],
            "representative_poses": {
                BASELINE_WEIGHTING: _representative(probes["right"][BASELINE_WEIGHTING]),
                CANDIDATE_WEIGHTING: _representative(probes["right"][CANDIDATE_WEIGHTING]),
            },
        },
        "bilateral_mirror_evidence": mirror,
        "truth_boundary": {
            "discrete_integer_degree_envelope_only": True,
            "continuous_real_valued_motion_proved": False,
            "source_or_topology_modified_by_rigging": False,
            "rig_or_weights_modified": False,
            "visual_deformation_accepted": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "gameplay_accepted": False,
            "canon_claimed": False,
        },
    }
