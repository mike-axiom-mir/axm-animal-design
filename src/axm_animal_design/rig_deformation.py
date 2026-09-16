"""Bounded rig/deformation evidence for explicit animal-form studies.

This module exercises declared bend zones with a small deterministic two-transform
linear-blend-skinning probe.  PASS is structural evidence for the exact source,
plan and sampled poses only.  It is not animation, anatomy, runtime, or visual-
quality acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .organic_form import build_form_study

PLAN_SCHEMA = "axm.animal-rig-deformation-plan/v0.1"
EVIDENCE_SCHEMA = "axm.animal-rig-deformation-evidence/v0.1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _vec3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    out = []
    for i, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{label}[{i}] must be finite")
        out.append(float(item))
    return tuple(out)


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _mul(a, scalar):
    return tuple(a[i] * scalar for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a):
    return math.sqrt(_dot(a, a))


def _unit(a, label):
    size = _length(a)
    if size <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return _mul(a, 1.0 / size)


def _rotate_about_axis(point, origin, axis, angle_deg):
    """Rodrigues rotation around an exact authored joint axis."""
    v = _sub(point, origin)
    k = _unit(axis, "joint axis")
    angle = math.radians(float(angle_deg))
    c, s = math.cos(angle), math.sin(angle)
    rotated = _add(_add(_mul(v, c), _mul(_cross(k, v), s)), _mul(k, _dot(k, v) * (1.0 - c)))
    return _add(origin, rotated)


def _triangle_double_area(a, b, c):
    return _length(_cross(_sub(b, a), _sub(c, a)))


def _edge_metrics(before, after, indices):
    edges = set()
    for offset in range(0, len(indices), 3):
        tri = indices[offset:offset + 3]
        for first, second in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.add(tuple(sorted((first, second))))
    ratios = []
    for first, second in edges:
        base = math.dist(before[first], before[second])
        posed = math.dist(after[first], after[second])
        if base > 1e-12:
            ratios.append(posed / base)
    return min(ratios), max(ratios)


def _validate_plan(spec, plan, primitives):
    if not isinstance(plan, dict) or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError(f"plan must use {PLAN_SCHEMA}")
    if plan.get("source_name") != spec.get("name"):
        raise ValueError("plan source_name must match form study name")
    joints = plan.get("joints")
    if not isinstance(joints, list) or not 1 <= len(joints) <= 16:
        raise ValueError("plan joints must contain 1..16 entries")
    landmarks = spec.get("landmarks", {})
    bend_by_landmark = {row.get("landmark"): row for row in spec.get("bend_zones", [])}
    seen = set()
    checked = []
    for joint in joints:
        identifier = joint.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("joint ids must be unique non-empty text")
        seen.add(identifier)
        landmark = joint.get("landmark")
        parent_landmark = joint.get("parent_landmark")
        child_landmark = joint.get("child_landmark")
        if any(name not in landmarks for name in (landmark, parent_landmark, child_landmark)):
            raise ValueError(f"{identifier} references unknown landmarks")
        parent_region = joint.get("parent_region")
        child_region = joint.get("child_region")
        if parent_region not in primitives or child_region not in primitives:
            raise ValueError(f"{identifier} references unknown mesh regions")
        axis = _vec3(joint.get("axis"), f"{identifier}.axis")
        _unit(axis, f"{identifier}.axis")
        influence = joint.get("influence_radius")
        if isinstance(influence, bool) or not isinstance(influence, (int, float)) or not math.isfinite(influence) or influence <= 0:
            raise ValueError(f"{identifier}.influence_radius must be > 0")
        reserve = bend_by_landmark.get(landmark)
        if reserve is None:
            raise ValueError(f"{identifier} requires a declared bend zone")
        reserve_radius = float(reserve["reserve_radius"])
        if float(influence) > reserve_radius + 1e-12:
            raise ValueError(f"{identifier}.influence_radius exceeds declared bend reserve")
        angles = joint.get("pose_angles_deg")
        if not isinstance(angles, list) or not angles or len(angles) > 9:
            raise ValueError(f"{identifier}.pose_angles_deg must contain 1..9 values")
        parsed_angles = []
        for angle in angles:
            if isinstance(angle, bool) or not isinstance(angle, (int, float)) or not math.isfinite(angle):
                raise ValueError(f"{identifier} pose angle must be finite")
            if abs(float(angle)) > 120.0:
                raise ValueError(f"{identifier} pose angle exceeds bounded probe range")
            parsed_angles.append(float(angle))
        checked.append({**joint, "axis": axis, "influence_radius": float(influence), "pose_angles_deg": parsed_angles})
    return checked


def _weights(positions, joint_position, child_direction, influence_radius):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t * t * (3.0 - 2.0 * t)
        parent = 1.0 - child
        rows.append((parent, child))
    return rows


def inspect_rig_deformation(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Exercise exact declared joints over bounded LBS poses and return evidence."""
    form = build_form_study(spec)
    primitives = {row["id"]: row for row in form["surface"]["primitives"]}
    joints = _validate_plan(spec, plan, primitives)
    landmarks = {name: _vec3(value, f"landmark {name}") for name, value in spec["landmarks"].items()}
    joint_reports = []
    all_pass = True

    for joint in joints:
        joint_position = landmarks[joint["landmark"]]
        child_marker = landmarks[joint["child_landmark"]]
        child_direction = _sub(child_marker, joint_position)
        primitive = primitives[joint["child_region"]]
        before = [tuple(point) for point in primitive["positions"]]
        indices = list(primitive["indices"])
        weights = _weights(before, joint_position, child_direction, joint["influence_radius"])
        max_weight_sum_error = max(abs((parent + child) - 1.0) for parent, child in weights)
        blended_vertices = sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9)
        fixed_vertices = sum(1 for _, child in weights if child <= 1e-9)
        rigid_vertices = sum(1 for _, child in weights if child >= 1.0 - 1e-9)
        poses = []
        source_areas = []
        for offset in range(0, len(indices), 3):
            a, b, c = (before[indices[offset]], before[indices[offset + 1]], before[indices[offset + 2]])
            source_areas.append(_triangle_double_area(a, b, c))
        if min(source_areas) <= 1e-12:
            raise ValueError(f"{joint['id']} source child region contains degenerate triangles")

        for angle in joint["pose_angles_deg"]:
            after = []
            fixed_drift = 0.0
            rigid_radius_drift = 0.0
            for point, (_, child_weight) in zip(before, weights):
                rotated = _rotate_about_axis(point, joint_position, joint["axis"], angle)
                posed = _add(point, _mul(_sub(rotated, point), child_weight))
                after.append(posed)
                if child_weight <= 1e-9:
                    fixed_drift = max(fixed_drift, math.dist(point, posed))
                if child_weight >= 1.0 - 1e-9:
                    rigid_radius_drift = max(
                        rigid_radius_drift,
                        abs(math.dist(point, joint_position) - math.dist(posed, joint_position)),
                    )
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
            distal = _rotate_about_axis(child_marker, joint_position, joint["axis"], angle)
            finite = all(math.isfinite(value) for point in after for value in point)
            status = "PASS" if finite and collapsed == 0 and fixed_drift <= 1e-9 and rigid_radius_drift <= 1e-9 else "FAIL"
            all_pass &= status == "PASS"
            poses.append({
                "angle_deg": angle,
                "status": status,
                "collapsed_triangles": collapsed,
                "minimum_triangle_area_ratio": round(min(area_ratios), 9),
                "minimum_edge_length_ratio": round(min_edge_ratio, 9),
                "maximum_edge_length_ratio": round(max_edge_ratio, 9),
                "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
                "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
                "distal_marker_position": [round(value, 9) for value in distal],
            })
        joint_status = "PASS" if all(row["status"] == "PASS" for row in poses) and max_weight_sum_error <= 1e-12 else "FAIL"
        all_pass &= joint_status == "PASS"
        joint_reports.append({
            "id": joint["id"],
            "landmark": joint["landmark"],
            "parent_region": joint["parent_region"],
            "child_region": joint["child_region"],
            "axis": list(joint["axis"]),
            "influence_radius": joint["influence_radius"],
            "weighting": "parent-identity + child-rotation smoothstep linear blend",
            "weight_counts": {"fixed": fixed_vertices, "blended": blended_vertices, "rigid": rigid_vertices},
            "max_weight_sum_error": round(max_weight_sum_error, 12),
            "poses": poses,
            "status": joint_status,
        })

    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": spec["name"],
        "source_digest": form["source_digest"],
        "surface_digest": form["surface_digest"],
        "plan_digest": _digest(plan),
        "joint_count": len(joint_reports),
        "pose_count": sum(len(row["poses"]) for row in joint_reports),
        "joints": joint_reports,
        "gate": "PASS" if all_pass else "FAIL",
        "truth": {
            "proves": "Exact declared joint probes preserve normalized two-transform weights, fixed anchors, rigid-radius invariants, finite coordinates and non-collapsed source-linked triangles across the sampled authored pose angles.",
            "does_not_prove": "Biological correctness, production skin weighting, self-intersection freedom, volume preservation, perceptual deformation quality, animation quality, locomotion, target-engine playback, collision, gameplay, performance, or mastery.",
        },
    }
