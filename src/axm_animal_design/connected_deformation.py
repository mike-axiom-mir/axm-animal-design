"""Bounded deformation probe for the exact connected left forelimb candidate.

This module deliberately does not author a new rig. It consumes an existing
animal rig plan, rebuilds the exact Geometry connected-chain candidate from the
source-owned quadruped form, and applies the same smoothstep two-transform LBS
rule used by the established disconnected-surface Rigging lane.

The result is structural deformation evidence for one exact candidate and one
sampled joint envelope. It is not Animation, runtime, anatomy, or visual-quality
acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .self_intersection import inspect_triangle_self_intersections
from .topology_study import build_connected_chain, derive_shared_ring_radii

EVIDENCE_SCHEMA = "axm.animal-connected-forelimb-deformation-evidence/v0.1"
CANDIDATE_ID = "front-left-connected-chain-001"
CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
JOINT_ID = "front-elbow-L"
BASELINE_WEIGHTING = "smoothstep-v0"
CHAIN_REGIONS = ("front_upper_L", "front_lower_L", "front_paw_L")
EXPECTED_PATH = ("shoulder_L", "elbow_L", "wrist_L", "front_paw_L")
DRIFT_TOLERANCE = 1e-9


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _vec3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    out = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{label}[{index}] must be finite")
        out.append(float(item))
    return tuple(out)


def _add(a, b):
    return tuple(a[index] + b[index] for index in range(3))


def _sub(a, b):
    return tuple(a[index] - b[index] for index in range(3))


def _mul(a, scalar):
    return tuple(a[index] * scalar for index in range(3))


def _dot(a, b):
    return sum(a[index] * b[index] for index in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(value):
    return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    size = _length(value)
    if size <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return _mul(value, 1.0 / size)


def _rotate_about_axis(point, origin, axis, angle_deg):
    value = _sub(point, origin)
    direction = _unit(axis, "joint axis")
    angle = math.radians(float(angle_deg))
    c, s = math.cos(angle), math.sin(angle)
    rotated = _add(
        _add(_mul(value, c), _mul(_cross(direction, value), s)),
        _mul(direction, _dot(direction, value) * (1.0 - c)),
    )
    return _add(origin, rotated)


def _triangle_double_area(a, b, c):
    return _length(_cross(_sub(b, a), _sub(c, a)))


def _edge_metrics(before, after, indices):
    edges = set()
    for offset in range(0, len(indices), 3):
        triangle = indices[offset:offset + 3]
        for first, second in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            edges.add(tuple(sorted((first, second))))
    ratios = []
    for first, second in edges:
        base = math.dist(before[first], before[second])
        posed = math.dist(after[first], after[second])
        if base > 1e-12:
            ratios.append(posed / base)
    if not ratios:
        raise ValueError("candidate must contain measurable edges")
    return min(ratios), max(ratios)


def _build_exact_candidate(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(spec, dict) or spec.get("name") != "quadruped-neutral-001":
        raise ValueError("source must be exact quadruped-neutral-001 family")
    if not isinstance(spec.get("regions"), list) or not isinstance(spec.get("landmarks"), dict):
        raise ValueError("source must contain regions and landmarks")

    derived = derive_shared_ring_radii(spec["regions"], CHAIN_REGIONS)
    if tuple(derived["path_landmarks"]) != EXPECTED_PATH:
        raise ValueError("source chain no longer resolves expected connected-forelimb path")
    landmarks = spec["landmarks"]
    candidate = build_connected_chain(
        CANDIDATE_ID,
        [landmarks[name] for name in derived["path_landmarks"]],
        derived["radii_m"],
        segments=10,
    )
    observed = digest(candidate)
    if observed != CANDIDATE_DIGEST:
        raise ValueError(f"connected candidate identity drift: {observed}")
    return candidate, derived


def _select_joint(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("schema") != "axm.animal-rig-deformation-plan/v0.1":
        raise ValueError("rig plan schema mismatch")
    if plan.get("source_name") != spec.get("name"):
        raise ValueError("rig plan source identity mismatch")
    joints = plan.get("joints")
    if not isinstance(joints, list):
        raise ValueError("rig plan joints must be a list")
    matches = [joint for joint in joints if isinstance(joint, dict) and joint.get("id") == JOINT_ID]
    if len(matches) != 1:
        raise ValueError(f"rig plan must contain exactly one {JOINT_ID}")
    joint = matches[0]

    required = {
        "landmark": "elbow_L",
        "parent_landmark": "shoulder_L",
        "child_landmark": "wrist_L",
        "parent_region": "front_upper_L",
        "child_region": "front_lower_L",
        "downstream_regions": ["front_paw_L"],
        "axis": [0.0, 1.0, 0.0],
        "influence_radius": 0.11,
        "pose_angles_deg": [-60.0, 0.0, 60.0],
    }
    for key, expected in required.items():
        if joint.get(key) != expected:
            raise ValueError(f"{JOINT_ID}.{key} drifted from the pinned Rigging contract")

    bend = [row for row in spec.get("bend_zones", []) if row.get("landmark") == "elbow_L"]
    if len(bend) != 1 or float(bend[0].get("reserve_radius", 0.0)) + 1e-12 < 0.11:
        raise ValueError("source elbow bend reserve no longer covers the exact rig influence radius")
    return joint


def _weights(positions, joint_position, child_direction, influence_radius):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t * t * (3.0 - 2.0 * t)
        rows.append((1.0 - child, child))
    return rows


def inspect_connected_forelimb_deformation(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Probe the exact connected left forelimb at the exact sampled elbow poses."""
    candidate, radius_derivation = _build_exact_candidate(spec)
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    weights = _weights(positions, joint_position, child_direction, float(joint["influence_radius"]))

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

    source_self_intersection = inspect_triangle_self_intersections(positions, indices)
    if source_self_intersection["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("connected candidate static self-intersection prerequisite no longer passes")

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
        finite = all(math.isfinite(value) for point in posed for value in point)
        neutral_max_drift = max(math.dist(before, after) for before, after in zip(positions, posed)) if angle == 0 else None
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
            "self_intersection_broad_phase_pairs": self_intersection["broad_phase_candidate_pairs"],
        })

    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": spec["name"],
        "candidate_id": candidate["id"],
        "candidate_digest": digest(candidate),
        "candidate_vertices": len(positions),
        "candidate_triangles": len(indices) // 3,
        "radius_derivation": radius_derivation,
        "rig_plan_digest": digest(plan),
        "joint_id": joint["id"],
        "axis": list(axis),
        "influence_radius_m": float(joint["influence_radius"]),
        "weighting": BASELINE_WEIGHTING,
        "weight_counts": {
            "fixed": fixed_vertices,
            "blended": blended_vertices,
            "rigid": rigid_vertices,
        },
        "max_weight_sum_error": round(max_weight_sum_error, 12),
        "static_self_intersection_status": source_self_intersection["status"],
        "poses": poses,
        "gate": "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION" if all_pass else "FAIL_CONNECTED_FORELIMB_BOUNDED_DEFORMATION",
        "truth_boundary": {
            "exact_connected_candidate_deformed": True,
            "exact_existing_rig_semantics_reused": True,
            "baseline_smoothstep_weighting_only": True,
            "candidate_weighting_refinement_accepted": False,
            "sampled_pose_self_intersection_checked": True,
            "continuous_motion_between_samples_checked": False,
            "volume_preservation_checked": False,
            "visual_quality_checked": False,
            "animation_checked": False,
            "target_runtime_checked": False,
            "gameplay_checked": False,
        },
    }
