"""Bounded weighting refinement evidence for the exact quadruped rig probe.

This module compares one candidate child-region weight profile against the retained
smoothstep baseline while preserving the exact organic source, joint plan, sampled
angles, downstream rigid inheritance, and chain-continuity contract. A PASS is a
numeric deformation-risk reduction for this exact study only; it is not visual,
anatomical, animation, runtime, or production-skinning acceptance.
"""
from __future__ import annotations

import math
from typing import Any

from .organic_form import build_form_study
from .rig_deformation import (
    CHAIN_GAP_TOLERANCE,
    _add,
    _collapsed_triangles,
    _digest,
    _dot,
    _edge_metrics,
    _minimum_vertex_gap,
    _mul,
    _rotate_about_axis,
    _sub,
    _triangle_double_area,
    _unit,
    _validate_plan,
    _vec3,
    inspect_rig_deformation,
)

REFINEMENT_SCHEMA = "axm.animal-weighting-refinement/v0.1"
EVIDENCE_SCHEMA = "axm.animal-weighting-refinement-evidence/v0.1"
BASELINE_PROFILE = "smoothstep-v0"
CANDIDATE_PROFILE = "ease-out-power-0p75-v1"
CANDIDATE_EXPONENT = 0.75
METRIC_TOLERANCE = 1e-9


def _profile_value(t: float, profile: str) -> float:
    t = max(0.0, min(1.0, float(t)))
    if profile == BASELINE_PROFILE:
        return t * t * (3.0 - 2.0 * t)
    if profile == CANDIDATE_PROFILE:
        return t ** CANDIDATE_EXPONENT
    raise ValueError(f"unsupported weighting profile: {profile}")


def _profile_weights(positions, joint_position, child_direction, influence_radius, profile):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = _profile_value(t, profile)
        rows.append((1.0 - child, child))
    return rows


def _validate_candidate(candidate: dict[str, Any], spec: dict[str, Any], plan: dict[str, Any]) -> None:
    if not isinstance(candidate, dict) or candidate.get("schema") != REFINEMENT_SCHEMA:
        raise ValueError(f"candidate must use {REFINEMENT_SCHEMA}")
    if candidate.get("source_name") != spec.get("name"):
        raise ValueError("candidate source_name must match form study")
    if candidate.get("baseline_plan_digest") != _digest(plan):
        raise ValueError("candidate baseline_plan_digest must match exact rig plan")
    if candidate.get("baseline_profile") != BASELINE_PROFILE:
        raise ValueError(f"candidate baseline_profile must be {BASELINE_PROFILE}")
    if candidate.get("candidate_profile") != CANDIDATE_PROFILE:
        raise ValueError(f"candidate_profile must be {CANDIDATE_PROFILE}")
    exponent = candidate.get("candidate_exponent")
    if isinstance(exponent, bool) or not isinstance(exponent, (int, float)) or not math.isfinite(exponent):
        raise ValueError("candidate_exponent must be finite")
    if abs(float(exponent) - CANDIDATE_EXPONENT) > 1e-12:
        raise ValueError(f"candidate_exponent must be exactly {CANDIDATE_EXPONENT}")


def _source_areas(positions, indices):
    rows = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        rows.append(_triangle_double_area(a, b, c))
    if not rows or min(rows) <= 1e-12:
        raise ValueError("candidate child region contains degenerate source triangles")
    return rows


def _pose_candidate(
    before,
    indices,
    weights,
    joint_position,
    axis,
    angle,
    downstream_source,
    chain_ids,
    source_chain_gaps,
):
    after = []
    fixed_drift = 0.0
    rigid_radius_drift = 0.0
    for point, (_, child_weight) in zip(before, weights):
        rotated = _rotate_about_axis(point, joint_position, axis, angle)
        posed = _add(point, _mul(_sub(rotated, point), child_weight))
        after.append(posed)
        if child_weight <= 1e-9:
            fixed_drift = max(fixed_drift, math.dist(point, posed))
        if child_weight >= 1.0 - 1e-9:
            rigid_radius_drift = max(
                rigid_radius_drift,
                abs(math.dist(point, joint_position) - math.dist(posed, joint_position)),
            )

    source_areas = _source_areas(before, indices)
    posed_areas = []
    collapsed = 0
    for offset in range(0, len(indices), 3):
        a, b, c = (after[indices[offset]], after[indices[offset + 1]], after[indices[offset + 2]])
        area = _triangle_double_area(a, b, c)
        posed_areas.append(area)
        if area <= 1e-12:
            collapsed += 1
    area_ratios = [posed / source for posed, source in zip(posed_areas, source_areas)]
    min_edge_ratio, max_edge_ratio = _edge_metrics(before, after, indices)

    posed_positions = {chain_ids[0]: after}
    downstream_reports = []
    downstream_ok = True
    for region_id in chain_ids[1:]:
        source_region = downstream_source[region_id]
        region_before = source_region["positions"]
        region_after = [_rotate_about_axis(point, joint_position, axis, angle) for point in region_before]
        posed_positions[region_id] = region_after
        region_collapsed, _ = _collapsed_triangles(region_after, source_region["indices"])
        region_min_edge_ratio, region_max_edge_ratio = _edge_metrics(
            region_before, region_after, source_region["indices"]
        )
        region_radius_drift = max(
            abs(math.dist(point, joint_position) - math.dist(posed, joint_position))
            for point, posed in zip(region_before, region_after)
        )
        status = "PASS" if region_collapsed == 0 and region_radius_drift <= 1e-9 else "FAIL"
        downstream_ok &= status == "PASS"
        downstream_reports.append({
            "region": region_id,
            "collapsed_triangles": region_collapsed,
            "minimum_edge_length_ratio": round(region_min_edge_ratio, 9),
            "maximum_edge_length_ratio": round(region_max_edge_ratio, 9),
            "rigid_radius_max_drift": round(region_radius_drift, 12),
            "status": status,
        })

    continuity_reports = []
    continuity_ok = True
    for parent_id, descendant_id in zip(chain_ids, chain_ids[1:]):
        key = f"{parent_id}->{descendant_id}"
        source_gap = source_chain_gaps[key]
        posed_gap = _minimum_vertex_gap(posed_positions[parent_id], posed_positions[descendant_id])
        gap_drift = abs(posed_gap - source_gap)
        status = "PASS" if gap_drift <= CHAIN_GAP_TOLERANCE else "FAIL"
        continuity_ok &= status == "PASS"
        continuity_reports.append({
            "from_region": parent_id,
            "to_region": descendant_id,
            "source_minimum_vertex_gap": round(source_gap, 12),
            "posed_minimum_vertex_gap": round(posed_gap, 12),
            "absolute_gap_drift": round(gap_drift, 12),
            "tolerance": CHAIN_GAP_TOLERANCE,
            "status": status,
        })

    finite = all(math.isfinite(value) for point in after for value in point)
    status = (
        "PASS"
        if finite
        and collapsed == 0
        and fixed_drift <= 1e-9
        and rigid_radius_drift <= 1e-9
        and downstream_ok
        and continuity_ok
        else "FAIL"
    )
    return {
        "angle_deg": float(angle),
        "status": status,
        "collapsed_triangles": collapsed,
        "minimum_triangle_area_ratio": round(min(area_ratios), 9),
        "minimum_edge_length_ratio": round(min_edge_ratio, 9),
        "maximum_edge_length_ratio": round(max_edge_ratio, 9),
        "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
        "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
        "downstream_regions": downstream_reports,
        "chain_continuity": continuity_reports,
    }


def compare_weighting_profiles(spec: dict[str, Any], plan: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Compare one explicit candidate weight profile against the exact retained rig plan."""
    _validate_candidate(candidate, spec, plan)
    baseline = inspect_rig_deformation(spec, plan)
    if baseline["gate"] != "PASS":
        raise ValueError("baseline rig plan must PASS before refinement comparison")

    form = build_form_study(spec)
    primitives = {row["id"]: row for row in form["surface"]["primitives"]}
    joints = _validate_plan(spec, plan, primitives)
    landmarks = {name: _vec3(value, f"landmark {name}") for name, value in spec["landmarks"].items()}
    baseline_by_joint = {row["id"]: row for row in baseline["joints"]}

    joint_reports = []
    all_pass = True
    nonzero_comparisons = []

    for joint in joints:
        joint_position = landmarks[joint["landmark"]]
        child_marker = landmarks[joint["child_landmark"]]
        child_direction = _sub(child_marker, joint_position)
        primitive = primitives[joint["child_region"]]
        before = [tuple(point) for point in primitive["positions"]]
        indices = list(primitive["indices"])
        weights = _profile_weights(
            before,
            joint_position,
            child_direction,
            joint["influence_radius"],
            CANDIDATE_PROFILE,
        )
        max_weight_sum_error = max(abs((parent + child) - 1.0) for parent, child in weights)
        fixed_vertices = sum(1 for _, child in weights if child <= 1e-9)
        blended_vertices = sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9)
        rigid_vertices = sum(1 for _, child in weights if child >= 1.0 - 1e-9)

        downstream_source = {}
        for region_id in joint["downstream_regions"]:
            row = primitives[region_id]
            region_positions = [tuple(point) for point in row["positions"]]
            region_indices = list(row["indices"])
            collapsed, minimum_area = _collapsed_triangles(region_positions, region_indices)
            if collapsed or minimum_area <= 1e-12:
                raise ValueError(f"{joint['id']} downstream region {region_id} contains degenerate triangles")
            downstream_source[region_id] = {"positions": region_positions, "indices": region_indices}

        chain_ids = [joint["child_region"], *joint["downstream_regions"]]
        source_positions = {
            joint["child_region"]: before,
            **{key: value["positions"] for key, value in downstream_source.items()},
        }
        source_chain_gaps = {
            f"{parent_id}->{descendant_id}": _minimum_vertex_gap(
                source_positions[parent_id], source_positions[descendant_id]
            )
            for parent_id, descendant_id in zip(chain_ids, chain_ids[1:])
        }

        baseline_joint = baseline_by_joint[joint["id"]]
        baseline_pose_by_angle = {float(row["angle_deg"]): row for row in baseline_joint["poses"]}
        poses = []
        joint_pass = max_weight_sum_error <= 1e-12
        for angle in joint["pose_angles_deg"]:
            candidate_pose = _pose_candidate(
                before,
                indices,
                weights,
                joint_position,
                joint["axis"],
                angle,
                downstream_source,
                chain_ids,
                source_chain_gaps,
            )
            baseline_pose = baseline_pose_by_angle[float(angle)]
            if abs(float(angle)) <= 1e-12:
                comparison_status = "PASS_NEUTRAL_EQUIVALENT" if (
                    candidate_pose["minimum_triangle_area_ratio"] == baseline_pose["minimum_triangle_area_ratio"]
                    and candidate_pose["minimum_edge_length_ratio"] == baseline_pose["minimum_edge_length_ratio"]
                    and candidate_pose["maximum_edge_length_ratio"] == baseline_pose["maximum_edge_length_ratio"]
                ) else "FAIL_NEUTRAL_DRIFT"
            else:
                area_gain = candidate_pose["minimum_triangle_area_ratio"] - baseline_pose["minimum_triangle_area_ratio"]
                max_edge_reduction = baseline_pose["maximum_edge_length_ratio"] - candidate_pose["maximum_edge_length_ratio"]
                min_edge_gain = candidate_pose["minimum_edge_length_ratio"] - baseline_pose["minimum_edge_length_ratio"]
                comparison_status = "PASS_IMPROVED" if (
                    area_gain > METRIC_TOLERANCE
                    and max_edge_reduction > METRIC_TOLERANCE
                    and min_edge_gain >= -METRIC_TOLERANCE
                ) else "FAIL_NOT_UNIFORMLY_IMPROVED"
                nonzero_comparisons.append({
                    "joint": joint["id"],
                    "angle_deg": float(angle),
                    "baseline_minimum_triangle_area_ratio": baseline_pose["minimum_triangle_area_ratio"],
                    "candidate_minimum_triangle_area_ratio": candidate_pose["minimum_triangle_area_ratio"],
                    "minimum_triangle_area_ratio_gain": round(area_gain, 9),
                    "baseline_minimum_edge_length_ratio": baseline_pose["minimum_edge_length_ratio"],
                    "candidate_minimum_edge_length_ratio": candidate_pose["minimum_edge_length_ratio"],
                    "minimum_edge_length_ratio_gain": round(min_edge_gain, 9),
                    "baseline_maximum_edge_length_ratio": baseline_pose["maximum_edge_length_ratio"],
                    "candidate_maximum_edge_length_ratio": candidate_pose["maximum_edge_length_ratio"],
                    "maximum_edge_length_ratio_reduction": round(max_edge_reduction, 9),
                    "status": comparison_status,
                })
            candidate_pose["baseline"] = {
                "minimum_triangle_area_ratio": baseline_pose["minimum_triangle_area_ratio"],
                "minimum_edge_length_ratio": baseline_pose["minimum_edge_length_ratio"],
                "maximum_edge_length_ratio": baseline_pose["maximum_edge_length_ratio"],
            }
            candidate_pose["comparison_status"] = comparison_status
            poses.append(candidate_pose)
            joint_pass &= candidate_pose["status"] == "PASS" and comparison_status.startswith("PASS")

        all_pass &= joint_pass
        joint_reports.append({
            "id": joint["id"],
            "landmark": joint["landmark"],
            "child_region": joint["child_region"],
            "downstream_regions": list(joint["downstream_regions"]),
            "axis": list(joint["axis"]),
            "influence_radius": joint["influence_radius"],
            "baseline_profile": BASELINE_PROFILE,
            "candidate_profile": CANDIDATE_PROFILE,
            "candidate_exponent": CANDIDATE_EXPONENT,
            "weight_counts": {"fixed": fixed_vertices, "blended": blended_vertices, "rigid": rigid_vertices},
            "max_weight_sum_error": round(max_weight_sum_error, 12),
            "poses": poses,
            "status": "PASS" if joint_pass else "FAIL",
        })

    worst_baseline_area = min(row["baseline_minimum_triangle_area_ratio"] for row in nonzero_comparisons)
    worst_candidate_area = min(row["candidate_minimum_triangle_area_ratio"] for row in nonzero_comparisons)
    worst_baseline_max_edge = max(row["baseline_maximum_edge_length_ratio"] for row in nonzero_comparisons)
    worst_candidate_max_edge = max(row["candidate_maximum_edge_length_ratio"] for row in nonzero_comparisons)
    worst_baseline_min_edge = min(row["baseline_minimum_edge_length_ratio"] for row in nonzero_comparisons)
    worst_candidate_min_edge = min(row["candidate_minimum_edge_length_ratio"] for row in nonzero_comparisons)

    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": spec["name"],
        "source_digest": form["source_digest"],
        "surface_digest": form["surface_digest"],
        "baseline_plan_digest": _digest(plan),
        "candidate_contract_digest": _digest(candidate),
        "baseline_profile": BASELINE_PROFILE,
        "candidate_profile": CANDIDATE_PROFILE,
        "candidate_exponent": CANDIDATE_EXPONENT,
        "joint_count": len(joint_reports),
        "sampled_pose_count": sum(len(row["poses"]) for row in joint_reports),
        "nonzero_comparison_count": len(nonzero_comparisons),
        "joints": joint_reports,
        "nonzero_pose_comparisons": nonzero_comparisons,
        "worst_case": {
            "minimum_triangle_area_ratio": {
                "baseline": worst_baseline_area,
                "candidate": worst_candidate_area,
                "gain": round(worst_candidate_area - worst_baseline_area, 9),
            },
            "maximum_edge_length_ratio": {
                "baseline": worst_baseline_max_edge,
                "candidate": worst_candidate_max_edge,
                "reduction": round(worst_baseline_max_edge - worst_candidate_max_edge, 9),
            },
            "minimum_edge_length_ratio": {
                "baseline": worst_baseline_min_edge,
                "candidate": worst_candidate_min_edge,
                "gain": round(worst_candidate_min_edge - worst_baseline_min_edge, 9),
            },
        },
        "gate": "PASS_SCOPED_WEIGHTING_REFINEMENT" if all_pass else "FAIL_WEIGHTING_REFINEMENT",
        "truth": {
            "proves": (
                "For the exact retained quadruped source and exact retained joint plan, the explicit 0.75-power "
                "candidate preserves neutral/fixed/rigid/downstream continuity invariants and improves the recorded "
                "triangle-area and edge-length risk metrics at every sampled nonzero +/-60 degree elbow/knee pose."
            ),
            "does_not_prove": (
                "Perceptual deformation quality, volume preservation, self-intersection freedom, anatomical correctness, "
                "production skinning, connected-topology behavior, animation quality, exported rig data, target-runtime "
                "playback, gameplay, performance, Art Director acceptance, CANON, or mastery."
            ),
        },
    }
