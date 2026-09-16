"""Rigging rebind of the exact Animal elbow source successor.

This module consumes the Organic-owned selected-003 elbow successor through the
Geometry source-successor topology rebind and reapplies the exact historical
Rigging plan plus the exact historical weighting-refinement profile.  It does
not author a new rig, reshape the source, or claim Animation/runtime acceptance.
"""
from __future__ import annotations

import math
from typing import Any

from .connected_deformation import (
    BASELINE_WEIGHTING,
    DRIFT_TOLERANCE,
    _add,
    _edge_metrics,
    _mul,
    _rotate_about_axis,
    _select_joint,
    _sub,
    _triangle_double_area,
    _unit,
    _vec3,
    _weights,
    digest,
)
from .organic_elbow_source_successor import SOURCE_SUCCESSOR_CANDIDATE_DIGEST
from .self_intersection import inspect_triangle_self_intersections
from .source_successor_topology_rebind import build_source_successor_topology_rebind

EVIDENCE_SCHEMA = "axm.animal-elbow-source-successor-rigging-rebind/v0.1"
GEOMETRY_SUCCESSOR_HEAD = "eb5ce99798b646b6ab9705c0c914b898173f7cc1"
ORGANIC_SUCCESSOR_HEAD = "7314a8971abb53f8ee6ef226c2496ab6d5da20d7"
HISTORICAL_WEIGHTING_HEAD = "5625c9f796a75e8b441458c51093e55519490611"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
CANDIDATE_WEIGHTING = "ease-out-power-0p75-v1"
CANDIDATE_EXPONENT = 0.75
DENSE_ANGLES_DEG = tuple(float(v) for v in range(-60, 61))
REPRESENTATIVE_ANGLES_DEG = (-60.0, -30.0, 0.0, 30.0, 60.0)
COMPARISON_TOLERANCE = 1e-12
STRICT_IMPROVEMENT_TOLERANCE = 1e-9


def _validate_weighting_profile(profile: dict[str, Any], plan: dict[str, Any]) -> str:
    if not isinstance(profile, dict) or profile.get("schema") != "axm.animal-weighting-refinement/v0.1":
        raise ValueError("weighting refinement profile schema mismatch")
    if profile.get("name") != "quadruped-weighting-refinement-001":
        raise ValueError("weighting refinement profile identity mismatch")
    if profile.get("source_name") != "quadruped-neutral-001":
        raise ValueError("weighting refinement source identity mismatch")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if profile.get("baseline_plan_digest") != RIG_PLAN_DIGEST:
        raise ValueError("weighting profile rig-plan binding drift")
    if profile.get("baseline_profile") != BASELINE_WEIGHTING:
        raise ValueError("weighting baseline profile drift")
    if profile.get("candidate_profile") != CANDIDATE_WEIGHTING:
        raise ValueError("weighting candidate profile drift")
    exponent = profile.get("candidate_exponent")
    if isinstance(exponent, bool) or not isinstance(exponent, (int, float)):
        raise ValueError("weighting candidate exponent must be numeric")
    if not math.isclose(float(exponent), CANDIDATE_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("weighting candidate exponent drift")
    observed = digest(profile)
    if observed != WEIGHTING_PROFILE_DIGEST:
        raise ValueError(f"weighting profile digest drift: {observed}")
    return observed


def _candidate_weights(positions, joint_position, child_direction, influence_radius):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = sum(
            _sub(point, joint_position)[index] * direction[index] for index in range(3)
        )
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t ** CANDIDATE_EXPONENT
        rows.append((1.0 - child, child))
    return rows


def _source_triangle_areas(positions, indices):
    areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (
            positions[indices[offset]],
            positions[indices[offset + 1]],
            positions[indices[offset + 2]],
        )
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("source successor contains a degenerate triangle")
        areas.append(area)
    return areas


def _pose_metrics(positions, indices, source_areas, weights, joint_position, axis, angle_deg):
    posed = []
    fixed_drift = 0.0
    rigid_radius_drift = 0.0
    for point, (_, child_weight) in zip(positions, weights):
        rotated = _rotate_about_axis(point, joint_position, axis, angle_deg)
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
        a, b, c = (
            posed[indices[offset]],
            posed[indices[offset + 1]],
            posed[indices[offset + 2]],
        )
        area = _triangle_double_area(a, b, c)
        posed_areas.append(area)
        if area <= 1e-12:
            collapsed += 1

    area_ratios = [after / before for after, before in zip(posed_areas, source_areas)]
    min_edge_ratio, max_edge_ratio = _edge_metrics(positions, posed, indices)
    self_intersection = inspect_triangle_self_intersections(posed, indices)
    neutral_drift = (
        max(math.dist(before, after) for before, after in zip(positions, posed))
        if angle_deg == 0.0
        else None
    )
    finite = all(math.isfinite(value) for point in posed for value in point)
    passed = (
        finite
        and collapsed == 0
        and fixed_drift <= DRIFT_TOLERANCE
        and rigid_radius_drift <= DRIFT_TOLERANCE
        and self_intersection["self_intersection_pair_count"] == 0
        and (neutral_drift is None or neutral_drift <= DRIFT_TOLERANCE)
    )
    return {
        "angle_deg": float(angle_deg),
        "status": "PASS" if passed else "FAIL",
        "minimum_triangle_area_ratio": min(area_ratios),
        "maximum_triangle_area_ratio": max(area_ratios),
        "minimum_edge_length_ratio": min_edge_ratio,
        "maximum_edge_length_ratio": max_edge_ratio,
        "collapsed_triangles": collapsed,
        "fixed_weight_vertex_max_drift_m": fixed_drift,
        "rigid_weight_radius_max_drift_m": rigid_radius_drift,
        "neutral_max_vertex_drift_m": neutral_drift,
        "nonadjacent_self_intersection_pairs": self_intersection["self_intersection_pair_count"],
        "self_intersection_broad_phase_pairs": self_intersection["broad_phase_candidate_pairs"],
        "positions": posed,
    }


def _probe_profile(candidate, spec, plan, weighting):
    joint = _select_joint(spec, plan)
    positions = [tuple(float(value) for value in point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    influence_radius = float(joint["influence_radius"])

    if weighting == BASELINE_WEIGHTING:
        weights = _weights(positions, joint_position, child_direction, influence_radius)
    elif weighting == CANDIDATE_WEIGHTING:
        weights = _candidate_weights(positions, joint_position, child_direction, influence_radius)
    else:
        raise ValueError("unknown weighting profile")

    max_weight_sum_error = max(abs(parent + child - 1.0) for parent, child in weights)
    counts = {
        "fixed": sum(1 for _, child in weights if child <= 1e-9),
        "blended": sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9),
        "rigid": sum(1 for _, child in weights if child >= 1.0 - 1e-9),
    }
    source_areas = _source_triangle_areas(positions, indices)
    rows = [
        _pose_metrics(
            positions,
            indices,
            source_areas,
            weights,
            joint_position,
            axis,
            angle,
        )
        for angle in DENSE_ANGLES_DEG
    ]
    passed = max_weight_sum_error <= 1e-12 and all(row["status"] == "PASS" for row in rows)
    return {
        "weighting": weighting,
        "weight_counts": counts,
        "max_weight_sum_error": max_weight_sum_error,
        "dense_sample_count": len(rows),
        "dense_angles_deg": [DENSE_ANGLES_DEG[0], DENSE_ANGLES_DEG[-1]],
        "poses": rows,
        "gate": (
            "PASS_SOURCE_SUCCESSOR_DENSE_STRUCTURAL_SWEEP"
            if passed
            else "FAIL_SOURCE_SUCCESSOR_DENSE_STRUCTURAL_SWEEP"
        ),
    }


def _comparison_at_boundaries(baseline, candidate):
    base_by_angle = {row["angle_deg"]: row for row in baseline["poses"]}
    cand_by_angle = {row["angle_deg"]: row for row in candidate["poses"]}
    rows = []
    all_pass = True
    for angle in (-60.0, 0.0, 60.0):
        base = base_by_angle[angle]
        cand = cand_by_angle[angle]
        max_vertex_delta = max(
            math.dist(tuple(before), tuple(after))
            for before, after in zip(base["positions"], cand["positions"])
        )
        row = {
            "angle_deg": angle,
            "baseline_minimum_triangle_area_ratio": base["minimum_triangle_area_ratio"],
            "candidate_minimum_triangle_area_ratio": cand["minimum_triangle_area_ratio"],
            "minimum_triangle_area_ratio_delta": (
                cand["minimum_triangle_area_ratio"] - base["minimum_triangle_area_ratio"]
            ),
            "baseline_maximum_triangle_area_ratio": base["maximum_triangle_area_ratio"],
            "candidate_maximum_triangle_area_ratio": cand["maximum_triangle_area_ratio"],
            "maximum_triangle_area_ratio_reduction": (
                base["maximum_triangle_area_ratio"] - cand["maximum_triangle_area_ratio"]
            ),
            "baseline_minimum_edge_length_ratio": base["minimum_edge_length_ratio"],
            "candidate_minimum_edge_length_ratio": cand["minimum_edge_length_ratio"],
            "minimum_edge_length_ratio_delta": (
                cand["minimum_edge_length_ratio"] - base["minimum_edge_length_ratio"]
            ),
            "baseline_maximum_edge_length_ratio": base["maximum_edge_length_ratio"],
            "candidate_maximum_edge_length_ratio": cand["maximum_edge_length_ratio"],
            "maximum_edge_length_ratio_reduction": (
                base["maximum_edge_length_ratio"] - cand["maximum_edge_length_ratio"]
            ),
            "maximum_baseline_to_candidate_vertex_delta_m": max_vertex_delta,
        }
        if angle == 0.0:
            row["comparison"] = (
                "PASS_NEUTRAL_IDENTICAL"
                if max_vertex_delta <= DRIFT_TOLERANCE
                else "FAIL_NEUTRAL_DRIFT"
            )
        else:
            improvements = (
                row["minimum_triangle_area_ratio_delta"],
                row["maximum_triangle_area_ratio_reduction"],
                row["minimum_edge_length_ratio_delta"],
                row["maximum_edge_length_ratio_reduction"],
            )
            non_worse = all(value >= -COMPARISON_TOLERANCE for value in improvements)
            strictly_better = any(value > STRICT_IMPROVEMENT_TOLERANCE for value in improvements)
            row["comparison"] = (
                "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT"
                if non_worse and strictly_better
                else "HOLD_WEIGHTING_PREFERENCE"
            )
        all_pass &= row["comparison"].startswith("PASS_")
        rows.append(row)
    return {
        "rows": rows,
        "gate": (
            "PASS_WEIGHTING_REFINEMENT_RECONFIRMED_ON_SOURCE_SUCCESSOR"
            if all_pass
            else "HOLD_WEIGHTING_REFINEMENT_PREFERENCE_ON_SOURCE_SUCCESSOR"
        ),
    }


def inspect_source_successor_rigging_rebind(
    spec: dict[str, Any],
    source_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
) -> dict[str, Any]:
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    weighting_digest = _validate_weighting_profile(weighting_profile, plan)
    candidate, topology = build_source_successor_topology_rebind(spec, source_profile)
    if topology["state"] != "PASS_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("source-successor topology prerequisite is not PASS")
    observed_candidate_digest = digest(candidate)
    if observed_candidate_digest != SOURCE_SUCCESSOR_CANDIDATE_DIGEST:
        raise ValueError("source-successor candidate identity drift")

    baseline = _probe_profile(candidate, spec, plan, BASELINE_WEIGHTING)
    refined = _probe_profile(candidate, spec, plan, CANDIDATE_WEIGHTING)
    comparison = _comparison_at_boundaries(baseline, refined)
    rebind_pass = (
        baseline["gate"] == "PASS_SOURCE_SUCCESSOR_DENSE_STRUCTURAL_SWEEP"
        and refined["gate"] == "PASS_SOURCE_SUCCESSOR_DENSE_STRUCTURAL_SWEEP"
    )

    representative = {}
    for weighting, probe in ((BASELINE_WEIGHTING, baseline), (CANDIDATE_WEIGHTING, refined)):
        by_angle = {row["angle_deg"]: row for row in probe["poses"]}
        representative[weighting] = {
            str(int(angle)): {
                **{key: value for key, value in by_angle[angle].items() if key != "positions"},
                "positions": [
                    [round(value, 9) for value in point]
                    for point in by_angle[angle]["positions"]
                ],
            }
            for angle in REPRESENTATIVE_ANGLES_DEG
        }

    def summary(probe):
        return {
            "gate": probe["gate"],
            "dense_sample_count": probe["dense_sample_count"],
            "weight_counts": probe["weight_counts"],
            "max_weight_sum_error": probe["max_weight_sum_error"],
            "minimum_area_ratio_over_sweep": min(
                row["minimum_triangle_area_ratio"] for row in probe["poses"]
            ),
            "maximum_area_ratio_over_sweep": max(
                row["maximum_triangle_area_ratio"] for row in probe["poses"]
            ),
            "minimum_edge_ratio_over_sweep": min(
                row["minimum_edge_length_ratio"] for row in probe["poses"]
            ),
            "maximum_edge_ratio_over_sweep": max(
                row["maximum_edge_length_ratio"] for row in probe["poses"]
            ),
            "maximum_fixed_drift_m": max(
                row["fixed_weight_vertex_max_drift_m"] for row in probe["poses"]
            ),
            "maximum_rigid_radius_drift_m": max(
                row["rigid_weight_radius_max_drift_m"] for row in probe["poses"]
            ),
            "maximum_self_intersection_pairs": max(
                row["nonadjacent_self_intersection_pairs"] for row in probe["poses"]
            ),
        }

    return {
        "schema": EVIDENCE_SCHEMA,
        "state": (
            "PASS_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP"
            if rebind_pass
            else "FAIL_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP"
        ),
        "source_name": spec.get("name"),
        "source_successor_candidate_digest": observed_candidate_digest,
        "geometry_successor_head": GEOMETRY_SUCCESSOR_HEAD,
        "organic_successor_head": ORGANIC_SUCCESSOR_HEAD,
        "historical_weighting_head": HISTORICAL_WEIGHTING_HEAD,
        "rig_donor_head": RIG_DONOR_HEAD,
        "rig_plan_digest": digest(plan),
        "weighting_profile_digest": weighting_digest,
        "joint_id": "front-elbow-L",
        "axis": [0.0, 1.0, 0.0],
        "influence_radius_m": 0.11,
        "verification_envelope_deg": [-60.0, 60.0],
        "dense_step_deg": 1.0,
        "dense_pose_count_per_profile": len(DENSE_ANGLES_DEG),
        "total_dense_pose_observations": len(DENSE_ANGLES_DEG) * 2,
        "topology_prerequisite_state": topology["state"],
        "baseline_summary": summary(baseline),
        "refined_summary": summary(refined),
        "boundary_weighting_comparison": comparison,
        "representative_poses": representative,
        "truth_boundary": {
            "organic_source_shape_modified": False,
            "geometry_topology_modified": False,
            "new_rig_authored": False,
            "historical_rig_plan_reused_exactly": True,
            "historical_weighting_profile_reused_exactly": True,
            "dense_discrete_structural_deformation_retested": True,
            "sampled_nonadjacent_self_intersections_retested": True,
            "continuous_real_valued_motion_proved": False,
            "visual_quality_checked": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "gameplay_checked": False,
            "canon_claimed": False,
        },
    }
