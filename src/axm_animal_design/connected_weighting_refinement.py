"""Compare the established weighting refinement on the exact connected forelimb.

This module closes one deliberately-held Rigging gap: the existing
``ease-out-power-0p75-v1`` candidate improved sampled deformation metrics on the
older disconnected form-study surface, while the newer connected forelimb proof
only exercised the accepted ``smoothstep-v0`` baseline.  The comparison here
keeps source, connected topology, joint, axis, influence radius and sampled pose
angles fixed and changes only the child-weight falloff profile.

The result is bounded structural Rigging evidence.  It is not visual acceptance,
continuous deformation, animation, runtime, anatomy, or gameplay evidence.
"""
from __future__ import annotations

import math
from typing import Any

from .connected_deformation import (
    BASELINE_WEIGHTING,
    CANDIDATE_DIGEST,
    DRIFT_TOLERANCE,
    _add,
    _build_exact_candidate,
    _dot,
    _edge_metrics,
    _mul,
    _rotate_about_axis,
    _select_joint,
    _sub,
    _triangle_double_area,
    _unit,
    _vec3,
    digest,
    inspect_connected_forelimb_deformation,
)
from .self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-connected-weighting-refinement-evidence/v0.1"
PROFILE_SCHEMA = "axm.animal-weighting-refinement/v0.1"
PROFILE_NAME = "quadruped-weighting-refinement-001"
CANDIDATE_WEIGHTING = "ease-out-power-0p75-v1"
CANDIDATE_EXPONENT = 0.75
EXPECTED_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
COMPARISON_TOLERANCE = 1e-12
STRICT_IMPROVEMENT_TOLERANCE = 1e-9


def _validate_profile(profile: dict[str, Any], spec: dict[str, Any], plan: dict[str, Any]) -> str:
    if not isinstance(profile, dict) or profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("weighting refinement profile schema mismatch")
    if profile.get("name") != PROFILE_NAME:
        raise ValueError("weighting refinement profile identity mismatch")
    if profile.get("source_name") != spec.get("name"):
        raise ValueError("weighting refinement source identity mismatch")
    plan_digest = digest(plan)
    if profile.get("baseline_plan_digest") != plan_digest:
        raise ValueError("weighting refinement rig-plan identity mismatch")
    if profile.get("baseline_profile") != BASELINE_WEIGHTING:
        raise ValueError("weighting refinement baseline profile drift")
    if profile.get("candidate_profile") != CANDIDATE_WEIGHTING:
        raise ValueError("weighting refinement candidate profile drift")
    exponent = profile.get("candidate_exponent")
    if isinstance(exponent, bool) or not isinstance(exponent, (int, float)):
        raise ValueError("weighting refinement candidate exponent must be numeric")
    if not math.isclose(float(exponent), CANDIDATE_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("weighting refinement candidate exponent drift")
    profile_digest = digest(profile)
    if profile_digest != EXPECTED_PROFILE_DIGEST:
        raise ValueError(f"weighting refinement profile digest drift: {profile_digest}")
    return profile_digest


def _candidate_weights(positions, joint_position, child_direction, influence_radius):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t ** CANDIDATE_EXPONENT
        rows.append((1.0 - child, child))
    return rows


def _probe_candidate(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    candidate, _ = _build_exact_candidate(spec)
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    weights = _candidate_weights(positions, joint_position, child_direction, float(joint["influence_radius"]))

    max_weight_sum_error = max(abs(parent + child - 1.0) for parent, child in weights)
    fixed_vertices = sum(1 for _, child in weights if child <= 1e-9)
    blended_vertices = sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9)
    rigid_vertices = sum(1 for _, child in weights if child >= 1.0 - 1e-9)

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("connected candidate contains a degenerate source triangle")
        source_areas.append(area)

    poses = []
    all_pass = max_weight_sum_error <= 1e-12
    for angle in joint["pose_angles_deg"]:
        posed = []
        fixed_drift = 0.0
        rigid_radius_drift = 0.0
        for point, (_, child_weight) in zip(positions, weights):
            rotated = _rotate_about_axis(point, joint_position, axis, angle)
            current = _add(point, _mul(_sub(rotated, point), child_weight))
            posed.append(current)
            if child_weight <= 1e-9:
                fixed_drift = max(fixed_drift, math.dist(point, current))
            if child_weight >= 1.0 - 1e-9:
                rigid_radius_drift = max(
                    rigid_radius_drift,
                    abs(math.dist(point, joint_position) - math.dist(current, joint_position)),
                )

        posed_areas = []
        collapsed = 0
        for offset in range(0, len(indices), 3):
            a, b, c = (posed[indices[offset]], posed[indices[offset + 1]], posed[indices[offset + 2]])
            area = _triangle_double_area(a, b, c)
            posed_areas.append(area)
            if area <= 1e-12:
                collapsed += 1
        area_ratios = [after / before for after, before in zip(posed_areas, source_areas)]
        min_edge_ratio, max_edge_ratio = _edge_metrics(positions, posed, indices)
        self_intersection = inspect_triangle_self_intersections(posed, indices)
        neutral_max_drift = max(math.dist(before, after) for before, after in zip(positions, posed)) if angle == 0 else None
        finite = all(math.isfinite(value) for point in posed for value in point)
        status = (
            "PASS"
            if finite
            and collapsed == 0
            and fixed_drift <= DRIFT_TOLERANCE
            and rigid_radius_drift <= DRIFT_TOLERANCE
            and self_intersection["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS"
            and (neutral_max_drift is None or neutral_max_drift <= DRIFT_TOLERANCE)
            else "FAIL"
        )
        all_pass &= status == "PASS"
        poses.append({
            "angle_deg": float(angle),
            "status": status,
            "positions": [[round(value, 9) for value in point] for point in posed],
            "collapsed_triangles": collapsed,
            "minimum_triangle_area_ratio": round(min(area_ratios), 9),
            "maximum_triangle_area_ratio": round(max(area_ratios), 9),
            "minimum_edge_length_ratio": round(min_edge_ratio, 9),
            "maximum_edge_length_ratio": round(max_edge_ratio, 9),
            "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
            "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
            "neutral_max_vertex_drift": None if neutral_max_drift is None else round(neutral_max_drift, 12),
            "nonadjacent_self_intersection_status": self_intersection["status"],
            "nonadjacent_self_intersection_pairs": self_intersection["self_intersection_pair_count"],
        })

    return {
        "weighting": CANDIDATE_WEIGHTING,
        "candidate_digest": digest(candidate),
        "weight_counts": {"fixed": fixed_vertices, "blended": blended_vertices, "rigid": rigid_vertices},
        "max_weight_sum_error": round(max_weight_sum_error, 12),
        "poses": poses,
        "gate": "PASS_CONNECTED_FORELIMB_CANDIDATE_WEIGHTING" if all_pass else "FAIL_CONNECTED_FORELIMB_CANDIDATE_WEIGHTING",
    }


def inspect_connected_weighting_refinement(
    spec: dict[str, Any],
    plan: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Compare the exact existing weighting candidate on the exact connected mesh."""
    profile_digest = _validate_profile(profile, spec, plan)
    baseline = inspect_connected_forelimb_deformation(spec, plan)
    candidate = _probe_candidate(spec, plan)

    if baseline["candidate_digest"] != CANDIDATE_DIGEST or candidate["candidate_digest"] != CANDIDATE_DIGEST:
        raise ValueError("connected topology identity drift during weighting comparison")
    if baseline["weighting"] != BASELINE_WEIGHTING or candidate["weighting"] != CANDIDATE_WEIGHTING:
        raise ValueError("weighting comparison profile identity drift")
    if baseline["weight_counts"] != candidate["weight_counts"]:
        raise ValueError("candidate weighting changed fixed/blended/rigid vertex partition")

    candidate_by_angle = {row["angle_deg"]: row for row in candidate["poses"]}
    comparisons = []
    comparison_pass = baseline["gate"] == "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION" and candidate["gate"] == "PASS_CONNECTED_FORELIMB_CANDIDATE_WEIGHTING"
    for base_pose in baseline["poses"]:
        angle = base_pose["angle_deg"]
        candidate_pose = candidate_by_angle.get(angle)
        if candidate_pose is None:
            raise ValueError("candidate weighting pose schedule drift")
        max_vertex_delta = max(
            math.dist(tuple(before), tuple(after))
            for before, after in zip(base_pose["positions"], candidate_pose["positions"])
        )
        row = {
            "angle_deg": angle,
            "baseline_status": base_pose["status"],
            "candidate_status": candidate_pose["status"],
            "baseline_minimum_triangle_area_ratio": base_pose["minimum_triangle_area_ratio"],
            "candidate_minimum_triangle_area_ratio": candidate_pose["minimum_triangle_area_ratio"],
            "minimum_triangle_area_ratio_delta": round(candidate_pose["minimum_triangle_area_ratio"] - base_pose["minimum_triangle_area_ratio"], 9),
            "baseline_maximum_triangle_area_ratio": base_pose["maximum_triangle_area_ratio"],
            "candidate_maximum_triangle_area_ratio": candidate_pose["maximum_triangle_area_ratio"],
            "maximum_triangle_area_ratio_reduction": round(base_pose["maximum_triangle_area_ratio"] - candidate_pose["maximum_triangle_area_ratio"], 9),
            "baseline_minimum_edge_length_ratio": base_pose["minimum_edge_length_ratio"],
            "candidate_minimum_edge_length_ratio": candidate_pose["minimum_edge_length_ratio"],
            "minimum_edge_length_ratio_delta": round(candidate_pose["minimum_edge_length_ratio"] - base_pose["minimum_edge_length_ratio"], 9),
            "baseline_maximum_edge_length_ratio": base_pose["maximum_edge_length_ratio"],
            "candidate_maximum_edge_length_ratio": candidate_pose["maximum_edge_length_ratio"],
            "maximum_edge_length_ratio_reduction": round(base_pose["maximum_edge_length_ratio"] - candidate_pose["maximum_edge_length_ratio"], 9),
            "baseline_self_intersections": base_pose["nonadjacent_self_intersection_pairs"],
            "candidate_self_intersections": candidate_pose["nonadjacent_self_intersection_pairs"],
            "maximum_baseline_to_candidate_vertex_delta_m": round(max_vertex_delta, 12),
        }

        if angle == 0.0:
            row["comparison"] = "PASS_NEUTRAL_IDENTICAL" if max_vertex_delta <= DRIFT_TOLERANCE else "FAIL_NEUTRAL_DRIFT"
            comparison_pass &= row["comparison"] == "PASS_NEUTRAL_IDENTICAL"
        else:
            improvements = (
                row["minimum_triangle_area_ratio_delta"],
                row["maximum_triangle_area_ratio_reduction"],
                row["minimum_edge_length_ratio_delta"],
                row["maximum_edge_length_ratio_reduction"],
            )
            non_worse = all(value >= -COMPARISON_TOLERANCE for value in improvements)
            strictly_better = any(value > STRICT_IMPROVEMENT_TOLERANCE for value in improvements)
            no_new_intersections = candidate_pose["nonadjacent_self_intersection_pairs"] <= base_pose["nonadjacent_self_intersection_pairs"]
            row["comparison"] = (
                "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT"
                if non_worse and strictly_better and no_new_intersections
                else "HOLD_CONNECTED_WEIGHTING_REFINEMENT"
            )
            comparison_pass &= row["comparison"] == "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT"
        comparisons.append(row)

    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": spec["name"],
        "connected_candidate_id": baseline["candidate_id"],
        "connected_candidate_digest": baseline["candidate_digest"],
        "rig_plan_digest": baseline["rig_plan_digest"],
        "weighting_profile_digest": profile_digest,
        "baseline_weighting": BASELINE_WEIGHTING,
        "candidate_weighting": CANDIDATE_WEIGHTING,
        "candidate_exponent": CANDIDATE_EXPONENT,
        "weight_counts": baseline["weight_counts"],
        "baseline_gate": baseline["gate"],
        "candidate_gate": candidate["gate"],
        "comparisons": comparisons,
        "gate": (
            "PASS_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT"
            if comparison_pass
            else "HOLD_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT"
        ),
        "truth_boundary": {
            "exact_connected_topology_compared": True,
            "exact_existing_rig_plan_reused": True,
            "only_weight_falloff_profile_changed": True,
            "sampled_pose_self_intersection_checked": True,
            "continuous_motion_between_samples_checked": False,
            "volume_preservation_checked": False,
            "visual_quality_checked": False,
            "animation_checked": False,
            "target_runtime_checked": False,
            "candidate_source_adopted": False,
            "gameplay_checked": False,
        },
    }
