"""Balanced Organic Form successor for the connected animal forelimb elbow.

This module preserves the existing source and topology while deriving one new
review-only elbow-ring form candidate.  It exists to test whether a smaller
bend-plane relief plus a small joint-axis width support can keep the earlier
edge-envelope benefit without retaining its minimum-triangle-area regression.

This is bounded Organic Form evidence.  It is not anatomy, source adoption,
Rigging acceptance, animation, runtime, gameplay, or visual-quality approval.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .connected_deformation import (
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
    _weights,
    digest,
)
from .organic_elbow_relief import (
    BASELINE_CANDIDATE_DIGEST,
    CANDIDATE_DIGEST as PREDECESSOR_CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    _bounds,
    _ring_indices,
    build_elbow_relief_candidate,
)
from .self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-balanced-relief-evidence/v0.1"
REVIEW_SCHEMA = "axm.animal-elbow-balanced-relief-review/v0.1"
CANDIDATE_ID = "front-left-connected-chain-elbow-balanced-relief-002"
CANDIDATE_DIGEST = "ed20e6c7e7751146cd05c2069e36ce503821c889dbbb203205fdfd700168fef0"
NOMINAL_ELBOW_RADIUS_M = 0.09
BEND_PLANE_RADIUS_M = 0.0875
JOINT_AXIS_WIDTH_SCALE = 1.03
ELBOW_PATH_INDEX = 1
EASE_OUT_EXPONENT = 0.75
EDGE_IMPROVEMENT_FLOOR = 0.005
MAX_NEUTRAL_VERTEX_DELTA_M = 0.0028
MAX_BOUND_EXPANSION_M = 0.003


def _bound_delta(before, after):
    return [
        [round(after[axis][side] - before[axis][side], 9) for side in range(2)]
        for axis in range(3)
    ]


def build_balanced_elbow_candidate(
    spec: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the exact balanced successor from the unchanged connected chain.

    Only the exact elbow ring is altered.  Relative to the elbow landmark and the
    pinned +Y joint axis, bend-plane (X/Z) components are scaled from 0.090 m to
    0.0875 m while joint-axis (Y) components are scaled by 1.03.  The small Y
    expansion is intentionally reported as a changed bound instead of being hidden.
    """
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")

    baseline, radius_derivation = _build_exact_candidate(spec)
    if digest(baseline) != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("baseline connected candidate identity drift")

    predecessor, _ = build_elbow_relief_candidate(spec, plan)
    if digest(predecessor) != PREDECESSOR_CANDIDATE_DIGEST:
        raise ValueError("predecessor Organic candidate identity drift")

    joint = _select_joint(spec, plan)
    axis = _vec3(joint["axis"], "joint axis")
    axis = _unit(axis, "joint axis")
    if tuple(round(value, 12) for value in axis) != (0.0, 1.0, 0.0):
        raise ValueError("balanced review candidate is bound to the exact +Y elbow axis")
    if abs(float(radius_derivation["radii_m"][ELBOW_PATH_INDEX]) - NOMINAL_ELBOW_RADIUS_M) > 1e-12:
        raise ValueError("source-derived elbow radius drift")

    candidate = copy.deepcopy(baseline)
    candidate["id"] = CANDIDATE_ID
    ring = _ring_indices(candidate, ELBOW_PATH_INDEX)
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "elbow landmark")
    bend_ratio = BEND_PLANE_RADIUS_M / NOMINAL_ELBOW_RADIUS_M

    baseline_positions = [tuple(point) for point in baseline["positions"]]
    candidate_positions = [list(point) for point in baseline["positions"]]
    for vertex_index in ring:
        point = baseline_positions[vertex_index]
        relative = _sub(point, joint_position)
        parallel = _mul(axis, _dot(relative, axis))
        perpendicular = _sub(relative, parallel)
        adjusted = _add(
            joint_position,
            _add(_mul(parallel, JOINT_AXIS_WIDTH_SCALE), _mul(perpendicular, bend_ratio)),
        )
        candidate_positions[vertex_index] = [round(value, 9) for value in adjusted]

    candidate["positions"] = candidate_positions
    candidate["organic_review"] = {
        "schema": REVIEW_SCHEMA,
        "predecessor_candidate_digest": PREDECESSOR_CANDIDATE_DIGEST,
        "source_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "joint_id": joint["id"],
        "joint_axis": list(axis),
        "elbow_ring_vertex_indices": ring,
        "nominal_source_radius_m": NOMINAL_ELBOW_RADIUS_M,
        "bend_plane_radius_m": BEND_PLANE_RADIUS_M,
        "bend_plane_radius_reduction_m": round(NOMINAL_ELBOW_RADIUS_M - BEND_PLANE_RADIUS_M, 12),
        "joint_axis_width_scale": JOINT_AXIS_WIDTH_SCALE,
        "joint_axis_width_change_fraction": round(JOINT_AXIS_WIDTH_SCALE - 1.0, 12),
        "source_landmarks_changed": False,
        "source_regions_changed": False,
    }
    candidate["truth_boundary"] = dict(candidate["truth_boundary"])
    candidate["truth_boundary"].update(
        {
            "organic_form_review_candidate": True,
            "balanced_relief_successor": True,
            "canonical_source_rewritten": False,
            "rigging_accepted": False,
            "visual_quality_checked": False,
        }
    )

    observed = digest(candidate)
    if observed != CANDIDATE_DIGEST:
        raise ValueError(f"balanced Organic candidate identity drift: {observed}")

    moved = [
        index
        for index, (before, after) in enumerate(zip(baseline_positions, candidate_positions))
        if math.dist(before, after) > 1e-12
    ]
    if moved != ring:
        raise ValueError("balanced candidate moved vertices outside the exact elbow ring")
    if baseline["indices"] != candidate["indices"] or baseline["path_points"] != candidate["path_points"]:
        raise ValueError("balanced candidate topology/path drift")
    if baseline["radii"] != candidate["radii"]:
        raise ValueError("balanced candidate silently rewrote source-derived nominal radii")

    baseline_bounds = _bounds(baseline_positions)
    candidate_bounds = _bounds([tuple(point) for point in candidate_positions])
    delta = _bound_delta(baseline_bounds, candidate_bounds)
    max_bound_expansion = max(max(0.0, value) for axis in delta for value in axis)
    maximum_neutral_delta = max(
        math.dist(baseline_positions[index], candidate_positions[index]) for index in moved
    )
    if maximum_neutral_delta > MAX_NEUTRAL_VERTEX_DELTA_M + 1e-12:
        raise ValueError("balanced candidate exceeded bounded neutral displacement")
    if max_bound_expansion > MAX_BOUND_EXPANSION_M + 1e-12:
        raise ValueError("balanced candidate exceeded bounded envelope expansion")

    scope = {
        "moved_vertex_indices": moved,
        "moved_vertex_count": len(moved),
        "maximum_neutral_vertex_delta_m": round(maximum_neutral_delta, 12),
        "baseline_bounds_m": baseline_bounds,
        "candidate_bounds_m": candidate_bounds,
        "bounds_delta_m": delta,
        "global_bounds_unchanged": baseline_bounds == candidate_bounds,
        "maximum_positive_bound_expansion_m": round(max_bound_expansion, 12),
    }
    return candidate, scope


def _power_weights(positions, joint_position, child_direction, influence_radius, exponent):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t ** exponent
        rows.append((1.0 - child, child))
    return rows


def _probe_candidate(
    candidate: dict[str, Any], spec: dict[str, Any], plan: dict[str, Any], weighting: str
) -> dict[str, Any]:
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    if weighting == "smoothstep-v0":
        weights = _weights(positions, joint_position, child_direction, float(joint["influence_radius"]))
    elif weighting == "ease-out-power-0p75-v1":
        weights = _power_weights(
            positions,
            joint_position,
            child_direction,
            float(joint["influence_radius"]),
            EASE_OUT_EXPONENT,
        )
    else:
        raise ValueError(f"unsupported weighting profile: {weighting}")

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("balanced candidate contains a degenerate neutral triangle")
        source_areas.append(area)

    static_self = inspect_triangle_self_intersections(positions, indices)
    if static_self["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("balanced candidate has a neutral self-intersection")

    poses = []
    all_pass = True
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
            collapsed += int(area <= 1e-12)
        area_ratios = [after / before for after, before in zip(posed_areas, source_areas)]
        min_edge, max_edge = _edge_metrics(positions, posed, indices)
        self_state = inspect_triangle_self_intersections(posed, indices)
        neutral_drift = max(math.dist(a, b) for a, b in zip(positions, posed)) if angle == 0 else None
        status = (
            "PASS"
            if collapsed == 0
            and fixed_drift <= DRIFT_TOLERANCE
            and rigid_radius_drift <= DRIFT_TOLERANCE
            and self_state["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS"
            and (neutral_drift is None or neutral_drift <= DRIFT_TOLERANCE)
            else "FAIL"
        )
        all_pass &= status == "PASS"
        poses.append(
            {
                "angle_deg": float(angle),
                "status": status,
                "positions": [[round(value, 9) for value in point] for point in posed],
                "collapsed_triangles": collapsed,
                "minimum_triangle_area_ratio": round(min(area_ratios), 9),
                "maximum_triangle_area_ratio": round(max(area_ratios), 9),
                "minimum_edge_length_ratio": round(min_edge, 9),
                "maximum_edge_length_ratio": round(max_edge, 9),
                "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
                "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
                "neutral_max_vertex_drift": None if neutral_drift is None else round(neutral_drift, 12),
                "nonadjacent_self_intersection_pairs": self_state["self_intersection_pair_count"],
            }
        )

    return {
        "weighting": weighting,
        "weight_counts": {
            "fixed": sum(1 for _, child in weights if child <= 1e-9),
            "blended": sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9),
            "rigid": sum(1 for _, child in weights if child >= 1.0 - 1e-9),
        },
        "poses": poses,
        "structural_gate": "PASS" if all_pass else "FAIL",
    }


def inspect_balanced_elbow_review(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Compare baseline, predecessor and balanced form under both pinned weightings."""
    baseline, _ = _build_exact_candidate(spec)
    predecessor, _ = build_elbow_relief_candidate(spec, plan)
    candidate, scope = build_balanced_elbow_candidate(spec, plan)

    forms = {
        "baseline": baseline,
        "predecessor_relief": predecessor,
        "balanced_successor": candidate,
    }
    profiles = ("smoothstep-v0", "ease-out-power-0p75-v1")
    probes = {
        profile: {name: _probe_candidate(mesh, spec, plan, profile) for name, mesh in forms.items()}
        for profile in profiles
    }

    comparisons = []
    evidence_gate = True
    for profile in profiles:
        baseline_by_angle = {row["angle_deg"]: row for row in probes[profile]["baseline"]["poses"]}
        predecessor_by_angle = {row["angle_deg"]: row for row in probes[profile]["predecessor_relief"]["poses"]}
        candidate_by_angle = {row["angle_deg"]: row for row in probes[profile]["balanced_successor"]["poses"]}
        for angle in (-60.0, 0.0, 60.0):
            base = baseline_by_angle[angle]
            old = predecessor_by_angle[angle]
            new = candidate_by_angle[angle]
            row = {
                "weighting": profile,
                "angle_deg": angle,
                "baseline_minimum_triangle_area_ratio": base["minimum_triangle_area_ratio"],
                "predecessor_minimum_triangle_area_ratio": old["minimum_triangle_area_ratio"],
                "balanced_minimum_triangle_area_ratio": new["minimum_triangle_area_ratio"],
                "balanced_min_area_delta_vs_baseline": round(new["minimum_triangle_area_ratio"] - base["minimum_triangle_area_ratio"], 9),
                "baseline_maximum_triangle_area_ratio": base["maximum_triangle_area_ratio"],
                "predecessor_maximum_triangle_area_ratio": old["maximum_triangle_area_ratio"],
                "balanced_maximum_triangle_area_ratio": new["maximum_triangle_area_ratio"],
                "balanced_max_area_reduction_vs_baseline": round(base["maximum_triangle_area_ratio"] - new["maximum_triangle_area_ratio"], 9),
                "baseline_minimum_edge_length_ratio": base["minimum_edge_length_ratio"],
                "predecessor_minimum_edge_length_ratio": old["minimum_edge_length_ratio"],
                "balanced_minimum_edge_length_ratio": new["minimum_edge_length_ratio"],
                "balanced_min_edge_gain_vs_baseline": round(new["minimum_edge_length_ratio"] - base["minimum_edge_length_ratio"], 9),
                "baseline_maximum_edge_length_ratio": base["maximum_edge_length_ratio"],
                "predecessor_maximum_edge_length_ratio": old["maximum_edge_length_ratio"],
                "balanced_maximum_edge_length_ratio": new["maximum_edge_length_ratio"],
                "balanced_max_edge_reduction_vs_baseline": round(base["maximum_edge_length_ratio"] - new["maximum_edge_length_ratio"], 9),
            }
            if angle == 0.0:
                neutral_ok = all(
                    abs(new[key] - 1.0) <= 1e-9
                    for key in (
                        "minimum_triangle_area_ratio",
                        "maximum_triangle_area_ratio",
                        "minimum_edge_length_ratio",
                        "maximum_edge_length_ratio",
                    )
                )
                row["comparison_gate"] = "PASS_NEUTRAL_RATIOS" if neutral_ok else "FAIL_NEUTRAL_RATIOS"
                evidence_gate &= neutral_ok
            else:
                min_area_nonworse = row["balanced_min_area_delta_vs_baseline"] >= 0.0
                max_area_nonworse = row["balanced_max_area_reduction_vs_baseline"] >= 0.0
                min_edge_material = row["balanced_min_edge_gain_vs_baseline"] >= EDGE_IMPROVEMENT_FLOOR
                max_edge_material = row["balanced_max_edge_reduction_vs_baseline"] >= EDGE_IMPROVEMENT_FLOOR
                structural_ok = new["status"] == "PASS" and new["nonadjacent_self_intersection_pairs"] == 0
                current_ok = min_area_nonworse and max_area_nonworse and min_edge_material and max_edge_material and structural_ok
                row["comparison_gate"] = (
                    "PASS_AREA_NONWORSE_AND_MATERIAL_EDGE_IMPROVEMENT" if current_ok else "HOLD_BALANCED_RELIEF"
                )
                evidence_gate &= current_ok
            comparisons.append(row)

    evidence_gate &= scope["maximum_neutral_vertex_delta_m"] <= MAX_NEUTRAL_VERTEX_DELTA_M
    evidence_gate &= scope["maximum_positive_bound_expansion_m"] <= MAX_BOUND_EXPANSION_M
    evidence_gate &= all(
        probes[profile]["balanced_successor"]["structural_gate"] == "PASS" for profile in profiles
    )

    decision = (
        "PASS_BALANCED_ELBOW_RELIEF_REMOVES_MIN_AREA_TRADEOFF_ACROSS_PINNED_WEIGHTINGS"
        if evidence_gate
        else "HOLD_BALANCED_ELBOW_RELIEF_SUCCESSOR"
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "decision": decision,
        "adoption_state": "HOLD_VISUAL_AND_SOURCE_ADOPTION",
        "source_digest": digest(spec),
        "rig_plan_digest": digest(plan),
        "baseline_candidate_digest": digest(baseline),
        "predecessor_candidate_digest": digest(predecessor),
        "balanced_candidate_digest": digest(candidate),
        "candidate_contract": candidate["organic_review"],
        "selection_contract": {
            "material_edge_improvement_floor": EDGE_IMPROVEMENT_FLOOR,
            "maximum_neutral_vertex_delta_m": MAX_NEUTRAL_VERTEX_DELTA_M,
            "maximum_positive_bound_expansion_m": MAX_BOUND_EXPANSION_M,
            "selection_reason": "close predecessor minimum-area regression while retaining >=0.5 percentage-point edge-envelope gains under both pinned weighting profiles",
            "anatomical_optimum_claimed": False,
        },
        "scope": scope,
        "probes": probes,
        "comparisons": comparisons,
        "truth_boundary": {
            "organic_source_rewritten": False,
            "predecessor_evidence_rewritten": False,
            "exact_same_topology_and_path": True,
            "exact_elbow_ring_only_changed": True,
            "bounded_y_envelope_expansion_reported_not_hidden": True,
            "both_pinned_weighting_sensitivities_checked": True,
            "minimum_area_tradeoff_removed_at_sampled_pose_envelope": True,
            "visual_quality_accepted": False,
            "anatomy_or_biology_validated": False,
            "rigging_or_weighting_accepted": False,
            "continuous_deformation_checked": False,
            "animation_checked": False,
            "runtime_or_gameplay_checked": False,
        },
    }
