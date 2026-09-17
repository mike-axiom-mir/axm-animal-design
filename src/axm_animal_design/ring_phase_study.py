"""Bounded angular ring-phase variants for an existing connected-chain mesh.

The helper intentionally derives from a completed ``build_connected_chain`` result.
It does not replace the source landmarks/radii, add topology, or claim deformation
or visual acceptance.  It only rotates each existing path ring around its local
transport tangent while preserving indices and endpoint poles.
"""
from __future__ import annotations

import copy
import math
from typing import Any

from .topology_study import _tangents


def _vec3(value: Any, label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    out = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{label}[{index}] must be a finite number")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{label}[{index}] must be a finite number")
        out.append(number)
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
    direction = _unit(axis, "ring tangent")
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    rotated = _add(
        _add(_mul(value, c), _mul(_cross(direction, value), s)),
        _mul(direction, _dot(direction, value) * (1.0 - c)),
    )
    return _add(origin, rotated)


def derive_ring_phase_candidate(
    baseline: dict[str, Any],
    *,
    identifier: str,
    phase_degrees: float,
) -> dict[str, Any]:
    """Rotate existing connected-chain rings without changing their connectivity.

    ``phase_degrees`` is bounded to one segment pitch because a full pitch returns
    the same regular polygon vertex set under cyclic relabelling.  The baseline is
    left untouched and remains the rollback/source geometry identity.
    """
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be a connected-chain mesh object")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("identifier must be non-empty text")
    if isinstance(phase_degrees, bool) or not isinstance(phase_degrees, (int, float)):
        raise ValueError("phase_degrees must be a finite number")
    phase_degrees = float(phase_degrees)
    if not math.isfinite(phase_degrees):
        raise ValueError("phase_degrees must be a finite number")

    try:
        segments = baseline["segments"]
        positions = baseline["positions"]
        indices = baseline["indices"]
        path_points = baseline["path_points"]
        radii = baseline["radii"]
    except KeyError as exc:
        raise ValueError(f"baseline missing connected-chain field {exc.args[0]}") from exc

    if type(segments) is not int or not 6 <= segments <= 64:
        raise ValueError("baseline segments must be an integer in 6..64")
    if not isinstance(path_points, list) or len(path_points) < 2:
        raise ValueError("baseline path_points must contain at least two points")
    points = tuple(_vec3(point, f"path_points[{index}]") for index, point in enumerate(path_points))
    if not isinstance(radii, list) or len(radii) != len(points):
        raise ValueError("baseline radii must match path_points")
    expected_vertices = 2 + len(points) * segments
    if not isinstance(positions, list) or len(positions) != expected_vertices:
        raise ValueError("baseline vertex layout is not the connected-chain ring layout")
    vertices = tuple(_vec3(point, f"positions[{index}]") for index, point in enumerate(positions))
    if not isinstance(indices, list) or not indices or len(indices) % 3:
        raise ValueError("baseline indices must contain complete triangles")

    pitch = 360.0 / segments
    if not 0.0 < phase_degrees < pitch:
        raise ValueError(f"phase_degrees must be > 0 and < one segment pitch ({pitch})")

    tangents = _tangents(points)
    candidate_positions = [list(point) for point in vertices]
    for ring_index, (origin, tangent) in enumerate(zip(points, tangents)):
        start = 1 + ring_index * segments
        for offset in range(segments):
            rotated = _rotate_about_axis(vertices[start + offset], origin, tangent, phase_degrees)
            candidate_positions[start + offset] = [round(value, 9) for value in rotated]

    candidate = copy.deepcopy(baseline)
    candidate["id"] = identifier
    candidate["positions"] = candidate_positions
    candidate["source_mesh_id"] = baseline.get("id")
    candidate["ring_phase_degrees"] = phase_degrees
    candidate["ring_phase_segment_pitch_degrees"] = pitch
    candidate["truth_boundary"] = dict(candidate.get("truth_boundary", {}))
    candidate["truth_boundary"].update({
        "ring_phase_candidate": True,
        "source_connected_chain_preserved_separately": True,
        "deformation_tested": False,
        "visual_quality_checked": False,
    })
    return candidate
