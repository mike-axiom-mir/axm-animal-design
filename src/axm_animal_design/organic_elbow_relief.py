"""Source-preserving Organic Form review candidate for the connected forelimb.

The established connected left forelimb is structurally sound at sampled poses,
but Rigging evidence reports meaningful local edge compression/stretch around the
elbow. This module creates one derived *review-only* neutral-form candidate that
changes only the elbow ring's bend-plane depth while preserving source landmarks,
source regions, topology, joint-axis width, and the exact existing rig semantics.

This is Organic Form evidence, not anatomy, rigging, animation, runtime, or visual
acceptance.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .connected_deformation import (
    CANDIDATE_DIGEST as BASELINE_CANDIDATE_DIGEST,
    DRIFT_TOLERANCE,
    _build_exact_candidate,
    _edge_metrics,
    _rotate_about_axis,
    _select_joint,
    _triangle_double_area,
    _vec3,
    _weights,
    digest,
    inspect_connected_forelimb_deformation,
)
from .self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-relief-evidence/v0.1"
REVIEW_SCHEMA = "axm.animal-elbow-bend-plane-relief-review/v0.1"
CANDIDATE_ID = "front-left-connected-chain-elbow-relief-001"
CANDIDATE_DIGEST = "afe295cadeecf4a15d6f2e8ab44cf83b0b2576cbe5fbd49818732cb62336eb65"
SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
NOMINAL_ELBOW_RADIUS_M = 0.09
BEND_PLANE_RADIUS_M = 0.085
ELBOW_PATH_INDEX = 1


def _add(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _sub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _mul(a, scalar):
    return tuple(a[index] * scalar for index in range(3))


def _dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def _bounds(positions):
    return [
        [round(min(point[axis] for point in positions), 9), round(max(point[axis] for point in positions), 9)]
        for axis in range(3)
    ]


def _ring_indices(candidate: dict[str, Any], path_index: int) -> list[int]:
    segments = int(candidate["segments"])
    start = 1 + path_index * segments
    return list(range(start, start + segments))


def build_elbow_relief_candidate(spec: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build one source-preserving review candidate from the exact connected chain.

    The elbow ring keeps its coordinates parallel to the exact +Y joint axis and
    scales only the perpendicular bend-plane component from 0.090 m to 0.085 m.
    No source landmark, source region, index, path point, or neighboring ring is
    changed.
    """
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")

    baseline, radius_derivation = _build_exact_candidate(spec)
    if digest(baseline) != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("baseline connected candidate identity drift")
    joint = _select_joint(spec, plan)
    axis = _vec3(joint["axis"], "joint axis")
    axis_size = math.sqrt(_dot(axis, axis))
    axis = _mul(axis, 1.0 / axis_size)
    if tuple(round(value, 12) for value in axis) != (0.0, 1.0, 0.0):
        raise ValueError("review candidate is bound to the exact +Y elbow axis")
    if abs(float(radius_derivation["radii_m"][ELBOW_PATH_INDEX]) - NOMINAL_ELBOW_RADIUS_M) > 1e-12:
        raise ValueError("source-derived elbow radius drift")

    candidate = copy.deepcopy(baseline)
    candidate["id"] = CANDIDATE_ID
    ring = _ring_indices(candidate, ELBOW_PATH_INDEX)
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "elbow landmark")
    ratio = BEND_PLANE_RADIUS_M / NOMINAL_ELBOW_RADIUS_M

    baseline_positions = [tuple(point) for point in baseline["positions"]]
    candidate_positions = [list(point) for point in baseline["positions"]]
    for vertex_index in ring:
        point = baseline_positions[vertex_index]
        relative = _sub(point, joint_position)
        parallel = _mul(axis, _dot(relative, axis))
        perpendicular = _sub(relative, parallel)
        adjusted = _add(joint_position, _add(parallel, _mul(perpendicular, ratio)))
        candidate_positions[vertex_index] = [round(value, 9) for value in adjusted]

    candidate["positions"] = candidate_positions
    candidate["organic_review"] = {
        "schema": REVIEW_SCHEMA,
        "source_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "joint_id": joint["id"],
        "joint_axis": list(axis),
        "elbow_ring_vertex_indices": ring,
        "nominal_source_radius_m": NOMINAL_ELBOW_RADIUS_M,
        "bend_plane_radius_m": BEND_PLANE_RADIUS_M,
        "bend_plane_radius_reduction_m": round(NOMINAL_ELBOW_RADIUS_M - BEND_PLANE_RADIUS_M, 12),
        "bend_plane_radius_reduction_fraction": round(
            (NOMINAL_ELBOW_RADIUS_M - BEND_PLANE_RADIUS_M) / NOMINAL_ELBOW_RADIUS_M, 12
        ),
        "axis_parallel_coordinates_preserved": True,
        "source_landmarks_changed": False,
        "source_regions_changed": False,
    }
    candidate["truth_boundary"] = dict(candidate["truth_boundary"])
    candidate["truth_boundary"].update({
        "organic_form_review_candidate": True,
        "canonical_source_rewritten": False,
        "rigging_accepted": False,
        "visual_quality_checked": False,
    })

    observed = digest(candidate)
    if observed != CANDIDATE_DIGEST:
        raise ValueError(f"organic elbow relief candidate identity drift: {observed}")

    moved = [
        index for index, (before, after) in enumerate(zip(baseline_positions, candidate_positions))
        if math.dist(before, after) > 1e-12
    ]
    if moved != ring:
        raise ValueError("candidate moved vertices outside the exact elbow ring")
    if baseline["indices"] != candidate["indices"] or baseline["path_points"] != candidate["path_points"]:
        raise ValueError("candidate topology/path drift")
    if baseline["radii"] != candidate["radii"]:
        raise ValueError("candidate silently rewrote source-derived nominal radii")
    for vertex_index in ring:
        if abs(baseline_positions[vertex_index][1] - candidate_positions[vertex_index][1]) > 1e-12:
            raise ValueError("candidate changed joint-axis-parallel elbow width")

    scope = {
        "moved_vertex_indices": moved,
        "moved_vertex_count": len(moved),
        "maximum_neutral_vertex_delta_m": round(
            max(math.dist(baseline_positions[index], candidate_positions[index]) for index in moved), 12
        ),
        "baseline_bounds_m": _bounds(baseline_positions),
        "candidate_bounds_m": _bounds([tuple(point) for point in candidate_positions]),
        "global_bounds_unchanged": _bounds(baseline_positions) == _bounds([tuple(point) for point in candidate_positions]),
    }
    return candidate, scope


def _inspect_candidate_pose(candidate: dict[str, Any], spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    weights = _weights(positions, joint_position, child_direction, float(joint["influence_radius"]))

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("organic candidate contains a degenerate neutral triangle")
        source_areas.append(area)

    static_self = inspect_triangle_self_intersections(positions, indices)
    if static_self["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("organic candidate has a neutral self-intersection")

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
        poses.append({
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
        })

    return {
        "static_self_intersection_status": static_self["status"],
        "weight_counts": {
            "fixed": sum(1 for _, child in weights if child <= 1e-9),
            "blended": sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9),
            "rigid": sum(1 for _, child in weights if child >= 1.0 - 1e-9),
        },
        "poses": poses,
        "structural_gate": "PASS" if all_pass else "FAIL",
    }


def inspect_elbow_relief_review(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Compare exact baseline and one local Organic Form review candidate."""
    candidate, scope = build_elbow_relief_candidate(spec, plan)
    baseline = inspect_connected_forelimb_deformation(spec, plan)
    candidate_probe = _inspect_candidate_pose(candidate, spec, plan)

    comparisons = []
    edge_gate = True
    for baseline_pose, candidate_pose in zip(baseline["poses"], candidate_probe["poses"]):
        row = {
            "angle_deg": baseline_pose["angle_deg"],
            "baseline_min_area": baseline_pose["minimum_triangle_area_ratio"],
            "candidate_min_area": candidate_pose["minimum_triangle_area_ratio"],
            "min_area_delta": round(
                candidate_pose["minimum_triangle_area_ratio"] - baseline_pose["minimum_triangle_area_ratio"], 9
            ),
            "baseline_max_area": baseline_pose["maximum_triangle_area_ratio"],
            "candidate_max_area": candidate_pose["maximum_triangle_area_ratio"],
            "max_area_delta": round(
                candidate_pose["maximum_triangle_area_ratio"] - baseline_pose["maximum_triangle_area_ratio"], 9
            ),
            "baseline_min_edge": baseline_pose["minimum_edge_length_ratio"],
            "candidate_min_edge": candidate_pose["minimum_edge_length_ratio"],
            "min_edge_delta": round(
                candidate_pose["minimum_edge_length_ratio"] - baseline_pose["minimum_edge_length_ratio"], 9
            ),
            "baseline_max_edge": baseline_pose["maximum_edge_length_ratio"],
            "candidate_max_edge": candidate_pose["maximum_edge_length_ratio"],
            "max_edge_delta": round(
                candidate_pose["maximum_edge_length_ratio"] - baseline_pose["maximum_edge_length_ratio"], 9
            ),
        }
        if baseline_pose["angle_deg"] != 0.0:
            edge_gate &= (
                candidate_pose["minimum_edge_length_ratio"] > baseline_pose["minimum_edge_length_ratio"]
                and candidate_pose["maximum_edge_length_ratio"] < baseline_pose["maximum_edge_length_ratio"]
            )
        comparisons.append(row)

    decision = (
        "PASS_BOUNDED_ELBOW_BEND_PLANE_RELIEF_REVIEW_CANDIDATE"
        if candidate_probe["structural_gate"] == "PASS" and edge_gate and scope["global_bounds_unchanged"]
        else "FAIL_BOUNDED_ELBOW_BEND_PLANE_RELIEF_REVIEW_CANDIDATE"
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "source_digest": digest(spec),
        "baseline_candidate_digest": baseline["candidate_digest"],
        "candidate_digest": digest(candidate),
        "rig_plan_digest": digest(plan),
        "review_contract": candidate["organic_review"],
        "scope": scope,
        "baseline": {
            "decision": baseline["gate"],
            "poses": baseline["poses"],
        },
        "candidate": candidate_probe,
        "comparisons": comparisons,
        "decision": decision,
        "truth_boundary": {
            "source_form_rewritten": False,
            "derived_review_candidate_only": True,
            "same_topology_and_rig_semantics": True,
            "sampled_structural_edge_envelope_compared": True,
            "triangle_area_tradeoff_reported_not_hidden": True,
            "biology_or_anatomy_validated": False,
            "visual_quality_accepted": False,
            "rigging_or_weighting_accepted": False,
            "continuous_motion_checked": False,
            "runtime_checked": False,
            "gameplay_checked": False,
        },
    }
