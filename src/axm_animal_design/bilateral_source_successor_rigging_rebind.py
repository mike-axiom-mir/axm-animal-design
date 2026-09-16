"""Rigging rebind for the exact bilateral Animal elbow source successors.

This module consumes Geometry's explicit left/right source-successor topology
rebind and reapplies the exact historical Rigging plan plus the exact historical
weighting-refinement profile.  It authors no new rig, does not reshape either
Organic source successor, and does not claim Animation or runtime acceptance.
"""
from __future__ import annotations

import math
from typing import Any

from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .connected_deformation import (
    BASELINE_WEIGHTING,
    DRIFT_TOLERANCE,
    _add,
    _edge_metrics,
    _mul,
    _rotate_about_axis,
    _sub,
    _triangle_double_area,
    _unit,
    _vec3,
    _weights,
    digest,
)
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP
from .self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-bilateral-source-successor-rigging-rebind/v0.1"
GEOMETRY_BILATERAL_HEAD = "f89af95d621c36da3994c6660552da8bbc73fd1b"
ORGANIC_BILATERAL_HEAD = "4df3024b4c459675422565501a46f622acf229a9"
HISTORICAL_LEFT_RIGGING_HEAD = "b48bb957622ed5c82a24ca4fcb471f7ee9b5147a"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
CANDIDATE_WEIGHTING = "ease-out-power-0p75-v1"
CANDIDATE_EXPONENT = 0.75
DENSE_ANGLES_DEG = tuple(float(value) for value in range(-60, 61))
REPRESENTATIVE_ANGLES_DEG = (-60.0, -30.0, 0.0, 30.0, 60.0)
COMPARISON_TOLERANCE = 1e-12
STRICT_IMPROVEMENT_TOLERANCE = 1e-9
MIRROR_TOLERANCE = 1e-9


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


def _select_joint(spec: dict[str, Any], plan: dict[str, Any], side: str) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("schema") != "axm.animal-rig-deformation-plan/v0.1":
        raise ValueError("rig plan schema mismatch")
    if plan.get("source_name") != spec.get("name"):
        raise ValueError("rig plan source identity mismatch")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")

    suffix = "L" if side == "left" else "R"
    joint_id = f"front-elbow-{suffix}"
    matches = [
        joint for joint in plan.get("joints", [])
        if isinstance(joint, dict) and joint.get("id") == joint_id
    ]
    if len(matches) != 1:
        raise ValueError(f"rig plan must contain exactly one {joint_id}")
    joint = matches[0]
    required = {
        "landmark": f"elbow_{suffix}",
        "parent_landmark": f"shoulder_{suffix}",
        "child_landmark": f"wrist_{suffix}",
        "parent_region": f"front_upper_{suffix}",
        "child_region": f"front_lower_{suffix}",
        "downstream_regions": [f"front_paw_{suffix}"],
        "axis": [0.0, 1.0, 0.0],
        "influence_radius": 0.11,
        "pose_angles_deg": [-60.0, 0.0, 60.0],
    }
    for key, expected in required.items():
        if joint.get(key) != expected:
            raise ValueError(f"{joint_id}.{key} drifted from the pinned Rigging contract")
    bend = [row for row in spec.get("bend_zones", []) if row.get("landmark") == f"elbow_{suffix}"]
    if len(bend) != 1 or float(bend[0].get("reserve_radius", 0.0)) + 1e-12 < 0.11:
        raise ValueError(f"source {joint_id} bend reserve no longer covers the exact rig influence radius")
    return joint


def _candidate_weights(positions, joint_position, child_direction, influence_radius):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        relative = _sub(point, joint_position)
        longitudinal = sum(relative[index] * direction[index] for index in range(3))
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
        if angle_deg == 0.0 else None
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


def _probe_side(candidate, spec, plan, side: str, weighting: str):
    joint = _select_joint(spec, plan, side)
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
        "side": side,
        "joint_id": joint["id"],
        "axis": list(joint["axis"]),
        "influence_radius_m": influence_radius,
        "weighting": weighting,
        "weights": weights,
        "weight_counts": counts,
        "max_weight_sum_error": max_weight_sum_error,
        "dense_sample_count": len(rows),
        "poses": rows,
        "gate": "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP" if passed else "FAIL_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP",
    }


def _boundary_comparison(baseline, refined):
    base_by_angle = {row["angle_deg"]: row for row in baseline["poses"]}
    refined_by_angle = {row["angle_deg"]: row for row in refined["poses"]}
    rows = []
    all_pass = True
    for angle in (-60.0, 0.0, 60.0):
        base = base_by_angle[angle]
        candidate = refined_by_angle[angle]
        max_vertex_delta = max(
            math.dist(before, after)
            for before, after in zip(base["positions"], candidate["positions"])
        )
        row = {
            "angle_deg": angle,
            "baseline_minimum_triangle_area_ratio": base["minimum_triangle_area_ratio"],
            "candidate_minimum_triangle_area_ratio": candidate["minimum_triangle_area_ratio"],
            "minimum_triangle_area_ratio_delta": candidate["minimum_triangle_area_ratio"] - base["minimum_triangle_area_ratio"],
            "baseline_maximum_triangle_area_ratio": base["maximum_triangle_area_ratio"],
            "candidate_maximum_triangle_area_ratio": candidate["maximum_triangle_area_ratio"],
            "maximum_triangle_area_ratio_reduction": base["maximum_triangle_area_ratio"] - candidate["maximum_triangle_area_ratio"],
            "baseline_minimum_edge_length_ratio": base["minimum_edge_length_ratio"],
            "candidate_minimum_edge_length_ratio": candidate["minimum_edge_length_ratio"],
            "minimum_edge_length_ratio_delta": candidate["minimum_edge_length_ratio"] - base["minimum_edge_length_ratio"],
            "baseline_maximum_edge_length_ratio": base["maximum_edge_length_ratio"],
            "candidate_maximum_edge_length_ratio": candidate["maximum_edge_length_ratio"],
            "maximum_edge_length_ratio_reduction": base["maximum_edge_length_ratio"] - candidate["maximum_edge_length_ratio"],
            "maximum_baseline_to_candidate_vertex_delta_m": max_vertex_delta,
        }
        if angle == 0.0:
            row["comparison"] = "PASS_NEUTRAL_IDENTICAL" if max_vertex_delta <= DRIFT_TOLERANCE else "FAIL_NEUTRAL_DRIFT"
        else:
            improvements = (
                row["minimum_triangle_area_ratio_delta"],
                row["maximum_triangle_area_ratio_reduction"],
                row["minimum_edge_length_ratio_delta"],
                row["maximum_edge_length_ratio_reduction"],
            )
            non_worse = all(value >= -COMPARISON_TOLERANCE for value in improvements)
            strictly_better = any(value > STRICT_IMPROVEMENT_TOLERANCE for value in improvements)
            row["comparison"] = "PASS_NONWORSE_WITH_STRICT_IMPROVEMENT" if non_worse and strictly_better else "HOLD_WEIGHTING_PREFERENCE"
        all_pass &= row["comparison"].startswith("PASS_")
        rows.append(row)
    return {
        "rows": rows,
        "gate": "PASS_WEIGHTING_REFINEMENT_RECONFIRMED_ON_BILATERAL_SUCCESSOR" if all_pass else "HOLD_WEIGHTING_REFINEMENT_PREFERENCE_ON_BILATERAL_SUCCESSOR",
    }


def _vertex_pairs(candidate):
    segments = int(candidate["segments"])
    path_count = len(candidate["path_points"])
    if segments != 10 or path_count != 4 or len(candidate["positions"]) != 42:
        raise ValueError("bilateral mirror comparison requires exact 42-vertex 10-segment chain")
    pairs = [(0, 0)]
    for ring_index in range(path_count):
        start = 1 + ring_index * segments
        pairs.extend((start + left_segment, start + right_segment) for left_segment, right_segment in enumerate(RING_SEGMENT_MAP))
    pairs.append((len(candidate["positions"]) - 1, len(candidate["positions"]) - 1))
    if len(pairs) != len(candidate["positions"]):
        raise ValueError("bilateral mirror correspondence count drift")
    return pairs


def _mirror_y(point):
    return (point[0], -point[1], point[2])


def _bilateral_comparison(left_probe, right_probe, left_candidate):
    pairs = _vertex_pairs(left_candidate)
    max_weight_residual = max(
        abs(left_probe["weights"][left_index][1] - right_probe["weights"][right_index][1])
        for left_index, right_index in pairs
    )
    right_by_angle = {row["angle_deg"]: row for row in right_probe["poses"]}
    rows = []
    max_pose_residual = 0.0
    max_metric_residual = 0.0
    all_pass = max_weight_residual <= MIRROR_TOLERANCE
    metric_keys = (
        "minimum_triangle_area_ratio",
        "maximum_triangle_area_ratio",
        "minimum_edge_length_ratio",
        "maximum_edge_length_ratio",
    )
    for left_row in left_probe["poses"]:
        angle = left_row["angle_deg"]
        right_row = right_by_angle[angle]
        pose_residual = max(
            math.dist(_mirror_y(left_row["positions"][left_index]), right_row["positions"][right_index])
            for left_index, right_index in pairs
        )
        metric_residual = max(abs(left_row[key] - right_row[key]) for key in metric_keys)
        max_pose_residual = max(max_pose_residual, pose_residual)
        max_metric_residual = max(max_metric_residual, metric_residual)
        passed = (
            pose_residual <= MIRROR_TOLERANCE
            and metric_residual <= MIRROR_TOLERANCE
            and left_row["status"] == "PASS"
            and right_row["status"] == "PASS"
        )
        all_pass &= passed
        rows.append({
            "angle_deg": angle,
            "maximum_mirrored_vertex_residual_m": pose_residual,
            "maximum_structural_metric_residual": metric_residual,
            "status": "PASS" if passed else "FAIL",
        })
    return {
        "mirror_plane": "Y=0",
        "same_authored_angle_compared": True,
        "vertex_correspondence_count": len(pairs),
        "dense_sample_count": len(rows),
        "maximum_weight_residual": max_weight_residual,
        "maximum_mirrored_pose_residual_m": max_pose_residual,
        "maximum_structural_metric_residual": max_metric_residual,
        "gate": "PASS_DENSE_BILATERAL_MIRROR_DEFORMATION_EQUIVALENCE" if all_pass else "FAIL_DENSE_BILATERAL_MIRROR_DEFORMATION_EQUIVALENCE",
        "rows": rows,
    }


def _summary(probe):
    return {
        "gate": probe["gate"],
        "joint_id": probe["joint_id"],
        "axis": probe["axis"],
        "influence_radius_m": probe["influence_radius_m"],
        "dense_sample_count": probe["dense_sample_count"],
        "weight_counts": probe["weight_counts"],
        "max_weight_sum_error": probe["max_weight_sum_error"],
        "minimum_area_ratio_over_sweep": min(row["minimum_triangle_area_ratio"] for row in probe["poses"]),
        "maximum_area_ratio_over_sweep": max(row["maximum_triangle_area_ratio"] for row in probe["poses"]),
        "minimum_edge_ratio_over_sweep": min(row["minimum_edge_length_ratio"] for row in probe["poses"]),
        "maximum_edge_ratio_over_sweep": max(row["maximum_edge_length_ratio"] for row in probe["poses"]),
        "maximum_fixed_drift_m": max(row["fixed_weight_vertex_max_drift_m"] for row in probe["poses"]),
        "maximum_rigid_radius_drift_m": max(row["rigid_weight_radius_max_drift_m"] for row in probe["poses"]),
        "maximum_self_intersection_pairs": max(row["nonadjacent_self_intersection_pairs"] for row in probe["poses"]),
    }


def _representative(probe):
    by_angle = {row["angle_deg"]: row for row in probe["poses"]}
    return {
        str(int(angle)): {
            **{key: value for key, value in by_angle[angle].items() if key != "positions"},
            "positions": [[round(value, 9) for value in point] for point in by_angle[angle]["positions"]],
        }
        for angle in REPRESENTATIVE_ANGLES_DEG
    }


def inspect_bilateral_source_successor_rigging_rebind(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
) -> dict[str, Any]:
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    weighting_digest = _validate_weighting_profile(weighting_profile, plan)
    left_candidate, right_candidate, geometry = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if geometry["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("bilateral Geometry prerequisite is not PASS")

    probes = {}
    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        baseline = _probe_side(candidate, spec, plan, side, BASELINE_WEIGHTING)
        refined = _probe_side(candidate, spec, plan, side, CANDIDATE_WEIGHTING)
        probes[side] = {"baseline": baseline, "refined": refined}

    left_boundary = _boundary_comparison(probes["left"]["baseline"], probes["left"]["refined"])
    right_boundary = _boundary_comparison(probes["right"]["baseline"], probes["right"]["refined"])
    baseline_mirror = _bilateral_comparison(probes["left"]["baseline"], probes["right"]["baseline"], left_candidate)
    refined_mirror = _bilateral_comparison(probes["left"]["refined"], probes["right"]["refined"], left_candidate)

    all_dense_pass = all(
        probes[side][profile]["gate"] == "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP"
        for side in ("left", "right") for profile in ("baseline", "refined")
    )
    all_weighting_pass = all(
        result["gate"] == "PASS_WEIGHTING_REFINEMENT_RECONFIRMED_ON_BILATERAL_SUCCESSOR"
        for result in (left_boundary, right_boundary)
    )
    all_mirror_pass = all(
        result["gate"] == "PASS_DENSE_BILATERAL_MIRROR_DEFORMATION_EQUIVALENCE"
        for result in (baseline_mirror, refined_mirror)
    )
    passed = all_dense_pass and all_weighting_pass and all_mirror_pass

    return {
        "schema": EVIDENCE_SCHEMA,
        "state": "PASS_BILATERAL_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP" if passed else "FAIL_BILATERAL_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP",
        "source_name": spec.get("name"),
        "geometry_bilateral_head": GEOMETRY_BILATERAL_HEAD,
        "organic_bilateral_head": ORGANIC_BILATERAL_HEAD,
        "historical_left_rigging_head": HISTORICAL_LEFT_RIGGING_HEAD,
        "rig_donor_head": RIG_DONOR_HEAD,
        "rig_plan_digest": digest(plan),
        "weighting_profile_digest": weighting_digest,
        "verification_envelope_deg": [-60.0, 60.0],
        "dense_step_deg": 1.0,
        "dense_pose_count_per_side_profile": len(DENSE_ANGLES_DEG),
        "total_dense_pose_observations": len(DENSE_ANGLES_DEG) * 4,
        "geometry_prerequisite_state": geometry["state"],
        "left": {
            "baseline_summary": _summary(probes["left"]["baseline"]),
            "refined_summary": _summary(probes["left"]["refined"]),
            "boundary_weighting_comparison": left_boundary,
            "representative_poses": {
                BASELINE_WEIGHTING: _representative(probes["left"]["baseline"]),
                CANDIDATE_WEIGHTING: _representative(probes["left"]["refined"]),
            },
        },
        "right": {
            "baseline_summary": _summary(probes["right"]["baseline"]),
            "refined_summary": _summary(probes["right"]["refined"]),
            "boundary_weighting_comparison": right_boundary,
            "representative_poses": {
                BASELINE_WEIGHTING: _representative(probes["right"]["baseline"]),
                CANDIDATE_WEIGHTING: _representative(probes["right"]["refined"]),
            },
        },
        "bilateral_mirror_evidence": {
            BASELINE_WEIGHTING: baseline_mirror,
            CANDIDATE_WEIGHTING: refined_mirror,
        },
        "truth_boundary": {
            "organic_source_shape_modified": False,
            "geometry_topology_modified": False,
            "new_rig_authored": False,
            "historical_rig_plan_reused_exactly": True,
            "historical_weighting_profile_reused_exactly": True,
            "historical_left_rigging_pass_silently_transferred_to_right": False,
            "both_sides_dense_deformation_retested": True,
            "sampled_nonadjacent_self_intersections_retested": True,
            "continuous_real_valued_motion_proved": False,
            "visual_quality_checked": False,
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "gameplay_checked": False,
            "canon_claimed": False,
        },
    }
