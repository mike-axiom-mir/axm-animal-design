"""Geometry-owned topology-invariant smooth-normal candidate for the Animal elbow.

Geometry PR #13 restores exact bilateral face correspondence by changing only the
right-side longitudinal quad diagonals.  Materials/Visual QA subsequently proved
that area-weighted *triangle-derived* smooth normals are not visually neutral
across that connectivity change.  This module tests the smallest Geometry-owned
alternative: derive one smooth normal field from the logical ring/quad surface
and source positions, not from either diagonal choice.

The field is Animal-local and experimental.  It does not author tangents, UVs,
materials, deformation acceptance, visual preference, runtime policy or CANON.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from .bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .connected_deformation import digest
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP

RECORD_SCHEMA = "axm.animal-bilateral-logical-quad-normal-field/v0.1"
NORMAL_FIELD_ID = "quadruped-front-elbow-bilateral-logical-quad-smooth-normal-field-001"
GEOMETRY_MIRROR_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
MATERIALS_REVIEW_HEAD = "96e998e5c793057836e01656aca9f71481439c9b"
ROUND_DIGITS = 12
MIRROR_TOLERANCE = 1e-10
UNIT_TOLERANCE = 1e-10


def _point(value: Sequence[float], label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be a 3D point")
    output = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in output):
        raise ValueError(f"{label} must be finite")
    return output


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _mul(a, scalar: float):
    return tuple(a[i] * scalar for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(value):
    return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    length = _length(value)
    if length <= 1e-14:
        raise ValueError(f"{label} has zero length")
    return _mul(value, 1.0 / length)


def _rounded_unit(value, label: str) -> list[float]:
    unit = _unit(value, label)
    return [round(component, ROUND_DIGITS) for component in unit]


def _newell(points: Iterable[Sequence[float]]) -> tuple[float, float, float]:
    polygon = tuple(_point(point, "polygon point") for point in points)
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least three points")
    nx = ny = nz = 0.0
    for current, nxt in zip(polygon, polygon[1:] + polygon[:1]):
        nx += (current[1] - nxt[1]) * (current[2] + nxt[2])
        ny += (current[2] - nxt[2]) * (current[0] + nxt[0])
        nz += (current[0] - nxt[0]) * (current[1] + nxt[1])
    return nx, ny, nz


def _layout(candidate: dict[str, Any]) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]], int, int]:
    positions = [_point(value, f"positions[{index}]") for index, value in enumerate(candidate.get("positions", []))]
    path = [_point(value, f"path_points[{index}]") for index, value in enumerate(candidate.get("path_points", []))]
    segments = candidate.get("segments")
    if type(segments) is not int or segments < 3:
        raise ValueError("candidate.segments must be an integer >= 3")
    if len(path) < 2:
        raise ValueError("candidate requires at least two path points")
    expected_vertices = 2 + len(path) * segments
    if len(positions) != expected_vertices:
        raise ValueError(
            f"logical-quad normal field requires pole + rings + pole layout: expected {expected_vertices}, got {len(positions)}"
        )
    return positions, path, segments, len(path)


def _ring_index(ring: int, segment: int, segments: int) -> int:
    return 1 + ring * segments + (segment % segments)


def derive_logical_quad_normals(candidate: dict[str, Any]) -> dict[str, Any]:
    """Derive smooth vertex normals from logical quads and cap wedges.

    Longitudinal surface normals are accumulated from the intended four-corner
    ring quads using a Newell polygon normal, so they are invariant to which
    diagonal triangulates each quad.  Endpoint cap wedges retain their actual
    source geometry.  Orientation is corrected against source radial/outward
    hints rather than inferred from candidate triangle winding.
    """
    positions, path, segments, ring_count = _layout(candidate)
    accumulated = [(0.0, 0.0, 0.0) for _ in positions]

    # Longitudinal logical quads.  Boundary order is a -> b -> d -> c.
    for ring in range(ring_count - 1):
        for segment in range(segments):
            a = _ring_index(ring, segment, segments)
            b = _ring_index(ring, segment + 1, segments)
            c = _ring_index(ring + 1, segment, segments)
            d = _ring_index(ring + 1, segment + 1, segments)
            raw = _newell((positions[a], positions[b], positions[d], positions[c]))
            radial_hint = (0.0, 0.0, 0.0)
            for vertex, center in ((a, path[ring]), (b, path[ring]), (c, path[ring + 1]), (d, path[ring + 1])):
                radial_hint = _add(radial_hint, _sub(positions[vertex], center))
            if _dot(raw, radial_hint) < 0.0:
                raw = _mul(raw, -1.0)
            if _length(raw) <= 1e-14:
                raise ValueError(f"logical quad {ring}:{segment} is degenerate")
            for vertex in (a, b, c, d):
                accumulated[vertex] = _add(accumulated[vertex], raw)

    # Start cap wedges.  The pole extends opposite the first path direction.
    start_pole = 0
    start_outward = _unit(_sub(positions[start_pole], path[0]), "start cap outward")
    for segment in range(segments):
        current = _ring_index(0, segment, segments)
        nxt = _ring_index(0, segment + 1, segments)
        raw = _cross(_sub(positions[nxt], positions[start_pole]), _sub(positions[current], positions[start_pole]))
        if _dot(raw, start_outward) < 0.0:
            raw = _mul(raw, -1.0)
        if _length(raw) <= 1e-14:
            raise ValueError(f"start cap wedge {segment} is degenerate")
        for vertex in (start_pole, nxt, current):
            accumulated[vertex] = _add(accumulated[vertex], raw)

    # End cap wedges.  The pole extends past the final path point.
    end_pole = len(positions) - 1
    end_outward = _unit(_sub(positions[end_pole], path[-1]), "end cap outward")
    last_ring = ring_count - 1
    for segment in range(segments):
        current = _ring_index(last_ring, segment, segments)
        nxt = _ring_index(last_ring, segment + 1, segments)
        raw = _cross(_sub(positions[nxt], positions[current]), _sub(positions[end_pole], positions[current]))
        if _dot(raw, end_outward) < 0.0:
            raw = _mul(raw, -1.0)
        if _length(raw) <= 1e-14:
            raise ValueError(f"end cap wedge {segment} is degenerate")
        for vertex in (current, nxt, end_pole):
            accumulated[vertex] = _add(accumulated[vertex], raw)

    normals = [_rounded_unit(value, f"normal[{index}]") for index, value in enumerate(accumulated)]
    unit_errors = [abs(_length(normal) - 1.0) for normal in normals]
    radial_dots = []
    for ring in range(ring_count):
        for segment in range(segments):
            vertex = _ring_index(ring, segment, segments)
            radial = _sub(positions[vertex], path[ring])
            radial_dots.append(_dot(normals[vertex], radial))

    return {
        "schema": RECORD_SCHEMA,
        "id": NORMAL_FIELD_ID,
        "source_candidate_id": candidate.get("id"),
        "source_candidate_digest": digest(candidate),
        "derivation": "logical-ring-quads-newell-plus-source-cap-wedges__independent-of-longitudinal-quad-diagonal",
        "normals": normals,
        "normal_count": len(normals),
        "maximum_unit_length_error": max(unit_errors, default=0.0),
        "minimum_ring_outward_radial_dot": min(radial_dots, default=0.0),
        "tangent_policy": "NOT_DEFINED_NO_UV_BASIS",
        "truth_boundary": {
            "positions_modified": False,
            "indices_modified": False,
            "normals_authored_as_candidate": True,
            "longitudinal_quad_diagonal_used_for_normal_derivation": False,
            "uvs_defined": False,
            "tangents_defined": False,
            "material_quality_checked": False,
            "visual_preference_claimed": False,
            "deformation_normal_quality_checked": False,
            "canon_claimed": False,
        },
    }


def generated_triangle_smooth_normals(candidate: dict[str, Any]) -> list[list[float]]:
    """Reproduce the Materials probe's area-weighted generated vertex normals."""
    positions, _path, _segments, _rings = _layout(candidate)
    indices = list(candidate.get("indices", []))
    if not indices or len(indices) % 3:
        raise ValueError("candidate.indices must contain complete triangles")
    accumulated = [(0.0, 0.0, 0.0) for _ in positions]
    for offset in range(0, len(indices), 3):
        ia, ib, ic = (int(indices[offset]), int(indices[offset + 1]), int(indices[offset + 2]))
        raw = _cross(_sub(positions[ib], positions[ia]), _sub(positions[ic], positions[ia]))
        for vertex in (ia, ib, ic):
            accumulated[vertex] = _add(accumulated[vertex], raw)
    return [_rounded_unit(value, f"generated normal[{index}]") for index, value in enumerate(accumulated)]


def _vector_residual(a: Sequence[float], b: Sequence[float]) -> float:
    return math.dist(tuple(float(value) for value in a), tuple(float(value) for value in b))


def _max_residual(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]) -> float:
    if len(left) != len(right):
        raise ValueError("normal fields have different lengths")
    return max((_vector_residual(a, b) for a, b in zip(left, right)), default=0.0)


def _mirror_map(candidate: dict[str, Any]) -> dict[int, int]:
    positions, _path, segments, ring_count = _layout(candidate)
    if segments != len(RING_SEGMENT_MAP):
        raise ValueError("candidate segment count does not match exact Organic mirror map")
    mapping = {0: 0, len(positions) - 1: len(positions) - 1}
    for ring in range(ring_count):
        for left_segment, right_segment in enumerate(RING_SEGMENT_MAP):
            mapping[_ring_index(ring, left_segment, segments)] = _ring_index(ring, right_segment, segments)
    return mapping


def mirrored_normal_residual(
    left_candidate: dict[str, Any],
    left_normals: Sequence[Sequence[float]],
    right_normals: Sequence[Sequence[float]],
) -> float:
    mapping = _mirror_map(left_candidate)
    residual = 0.0
    for left_index, right_index in mapping.items():
        source = left_normals[left_index]
        expected = (float(source[0]), -float(source[1]), float(source[2]))
        residual = max(residual, _vector_residual(expected, right_normals[right_index]))
    return residual


def inspect_bilateral_logical_quad_normal_field(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build exact Animal surfaces and test one diagonal-invariant normal field."""
    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("bilateral source-successor topology prerequisite is not PASS")
    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise ValueError("exact-mirror topology prerequisite is not PASS")

    left_field = derive_logical_quad_normals(left)
    historical_field = derive_logical_quad_normals(historical_right)
    exact_field = derive_logical_quad_normals(exact_right)

    generated_historical = generated_triangle_smooth_normals(historical_right)
    generated_exact = generated_triangle_smooth_normals(exact_right)
    diagonal_invariance_residual = _max_residual(historical_field["normals"], exact_field["normals"])
    bilateral_mirror_residual = mirrored_normal_residual(left, left_field["normals"], exact_field["normals"])
    generated_connectivity_residual = _max_residual(generated_historical, generated_exact)

    gates = {
        "exact-topology-positions-match-historical": exact_right["positions"] == historical_right["positions"],
        "exact-topology-indices-differ-from-historical": exact_right["indices"] != historical_right["indices"],
        "logical-normal-field-independent-of-right-diagonal-choice": diagonal_invariance_residual <= MIRROR_TOLERANCE,
        "logical-normal-field-is-exact-bilateral-mirror": bilateral_mirror_residual <= MIRROR_TOLERANCE,
        "left-normal-field-unit-length": left_field["maximum_unit_length_error"] <= UNIT_TOLERANCE,
        "right-normal-field-unit-length": exact_field["maximum_unit_length_error"] <= UNIT_TOLERANCE,
        "left-ring-normals-point-outward": left_field["minimum_ring_outward_radial_dot"] > 0.0,
        "right-ring-normals-point-outward": exact_field["minimum_ring_outward_radial_dot"] > 0.0,
        "normal-count-preserves-vertex-count": (
            left_field["normal_count"] == len(left["positions"])
            and exact_field["normal_count"] == len(exact_right["positions"])
        ),
        "tangents-remain-explicitly-held": (
            left_field["tangent_policy"] == "NOT_DEFINED_NO_UV_BASIS"
            and exact_field["tangent_policy"] == "NOT_DEFINED_NO_UV_BASIS"
        ),
    }
    state = (
        "PASS_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_CANDIDATE__TANGENTS_HELD"
        if all(gates.values())
        else "FAIL_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_CANDIDATE"
    )
    record = {
        "schema": RECORD_SCHEMA,
        "state": state,
        "normal_field_id": NORMAL_FIELD_ID,
        "geometry_mirror_head": GEOMETRY_MIRROR_HEAD,
        "materials_review_head": MATERIALS_REVIEW_HEAD,
        "left_candidate_digest": digest(left),
        "historical_right_candidate_digest": digest(historical_right),
        "exact_mirror_right_candidate_digest": digest(exact_right),
        "left_normal_field_digest": digest(left_field),
        "historical_right_normal_field_digest": digest(historical_field),
        "exact_mirror_right_normal_field_digest": digest(exact_field),
        "diagonal_invariance_max_normal_residual": diagonal_invariance_residual,
        "bilateral_mirror_max_normal_residual": bilateral_mirror_residual,
        "triangle_generated_historical_vs_exact_max_normal_residual": generated_connectivity_residual,
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
        "truth_boundary": {
            "topology_changed_by_this_normal_candidate": False,
            "source_form_changed": False,
            "rig_or_weights_changed": False,
            "normal_field_is_candidate_not_canon": True,
            "tangents_or_uvs_authored": False,
            "visual_neutrality_or_preference_claimed": False,
            "deformed_normal_quality_checked": False,
            "runtime_or_gameplay_checked": False,
            "production_readiness_claimed": False,
        },
    }
    return left_field, historical_field, exact_field, record
