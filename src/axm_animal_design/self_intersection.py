"""Bounded triangle self-intersection diagnostics for one indexed mesh.

This receiving-domain helper checks geometric intersections between triangle pairs
that do not share source vertex indices. Topological neighbours are excluded so
ordinary shared edges/vertices are not misreported as self-intersections.

It is intentionally small and dependency-free. It does not prove deformation,
visual quality, collision suitability, or runtime behaviour.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence


def _num(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return value


def _point(value: Sequence[float], label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    return tuple(_num(item, f"{label}[{index}]") for index, item in enumerate(value))


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


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


def _aabb(triangle):
    return (
        tuple(min(point[axis] for point in triangle) for axis in range(3)),
        tuple(max(point[axis] for point in triangle) for axis in range(3)),
    )


def _aabb_overlap(a, b, epsilon: float) -> bool:
    amin, amax = a
    bmin, bmax = b
    return all(amax[axis] + epsilon >= bmin[axis] and bmax[axis] + epsilon >= amin[axis] for axis in range(3))


def _segment_triangle_intersection(start, end, triangle, epsilon: float) -> bool:
    a, b, c = triangle
    direction = _sub(end, start)
    edge1 = _sub(b, a)
    edge2 = _sub(c, a)
    h = _cross(direction, edge2)
    determinant = _dot(edge1, h)
    if abs(determinant) <= epsilon:
        return False
    inv = 1.0 / determinant
    s = _sub(start, a)
    u = inv * _dot(s, h)
    if u < -epsilon or u > 1.0 + epsilon:
        return False
    q = _cross(s, edge1)
    v = inv * _dot(direction, q)
    if v < -epsilon or u + v > 1.0 + epsilon:
        return False
    t = inv * _dot(edge2, q)
    return -epsilon <= t <= 1.0 + epsilon


def _orient2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment2(a, b, p, epsilon: float) -> bool:
    return (
        min(a[0], b[0]) - epsilon <= p[0] <= max(a[0], b[0]) + epsilon
        and min(a[1], b[1]) - epsilon <= p[1] <= max(a[1], b[1]) + epsilon
        and abs(_orient2(a, b, p)) <= epsilon
    )


def _segments_intersect2(a, b, c, d, epsilon: float) -> bool:
    o1 = _orient2(a, b, c)
    o2 = _orient2(a, b, d)
    o3 = _orient2(c, d, a)
    o4 = _orient2(c, d, b)
    if ((o1 > epsilon and o2 < -epsilon) or (o1 < -epsilon and o2 > epsilon)) and (
        (o3 > epsilon and o4 < -epsilon) or (o3 < -epsilon and o4 > epsilon)
    ):
        return True
    return (
        (abs(o1) <= epsilon and _on_segment2(a, b, c, epsilon))
        or (abs(o2) <= epsilon and _on_segment2(a, b, d, epsilon))
        or (abs(o3) <= epsilon and _on_segment2(c, d, a, epsilon))
        or (abs(o4) <= epsilon and _on_segment2(c, d, b, epsilon))
    )


def _point_in_triangle2(point, triangle, epsilon: float) -> bool:
    a, b, c = triangle
    o1 = _orient2(a, b, point)
    o2 = _orient2(b, c, point)
    o3 = _orient2(c, a, point)
    has_positive = any(value > epsilon for value in (o1, o2, o3))
    has_negative = any(value < -epsilon for value in (o1, o2, o3))
    return not (has_positive and has_negative)


def _project2(point, drop_axis: int):
    return tuple(point[axis] for axis in range(3) if axis != drop_axis)


def _coplanar_triangles_intersect(first, second, normal, epsilon: float) -> bool:
    drop_axis = max(range(3), key=lambda axis: abs(normal[axis]))
    a = tuple(_project2(point, drop_axis) for point in first)
    b = tuple(_project2(point, drop_axis) for point in second)
    for index in range(3):
        a0, a1 = a[index], a[(index + 1) % 3]
        for other in range(3):
            b0, b1 = b[other], b[(other + 1) % 3]
            if _segments_intersect2(a0, a1, b0, b1, epsilon):
                return True
    return _point_in_triangle2(a[0], b, epsilon) or _point_in_triangle2(b[0], a, epsilon)


def _triangles_intersect(first, second, epsilon: float) -> bool:
    n1 = _cross(_sub(first[1], first[0]), _sub(first[2], first[0]))
    n2 = _cross(_sub(second[1], second[0]), _sub(second[2], second[0]))
    len1 = _length(n1)
    len2 = _length(n2)
    if len1 <= epsilon or len2 <= epsilon:
        raise ValueError("self-intersection inspection requires non-degenerate triangles")

    normal_cross = _length(_cross(n1, n2))
    plane_distance = abs(_dot(n1, _sub(second[0], first[0]))) / len1
    if normal_cross <= epsilon * len1 * len2 and plane_distance <= epsilon:
        return _coplanar_triangles_intersect(first, second, n1, epsilon)

    for index in range(3):
        if _segment_triangle_intersection(first[index], first[(index + 1) % 3], second, epsilon):
            return True
        if _segment_triangle_intersection(second[index], second[(index + 1) % 3], first, epsilon):
            return True
    return False


def inspect_triangle_self_intersections(
    positions: Iterable[Sequence[float]],
    indices: Iterable[int],
    *,
    epsilon: float = 1e-9,
    max_examples: int = 16,
) -> dict:
    """Inspect non-topological-neighbour triangle pairs for geometric intersections."""
    try:
        vertices = tuple(_point(value, f"positions[{index}]") for index, value in enumerate(positions))
    except TypeError as exc:
        raise ValueError("positions must be an iterable of 3D points") from exc
    if not vertices:
        raise ValueError("positions must contain at least one vertex")
    try:
        raw_indices = tuple(indices)
    except TypeError as exc:
        raise ValueError("indices must be an iterable of triangle indices") from exc
    if not raw_indices or len(raw_indices) % 3:
        raise ValueError("indices must contain one or more complete triangles")
    if any(type(index) is not int for index in raw_indices):
        raise ValueError("triangle indices must be integers")
    if any(index < 0 or index >= len(vertices) for index in raw_indices):
        raise ValueError("triangle index is out of range")
    epsilon = _num(epsilon, "epsilon")
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")
    if type(max_examples) is not int or max_examples < 0:
        raise ValueError("max_examples must be a non-negative integer")

    triangle_indices = []
    triangles = []
    boxes = []
    for triangle_index in range(len(raw_indices) // 3):
        face = tuple(raw_indices[triangle_index * 3: triangle_index * 3 + 3])
        if len(set(face)) != 3:
            raise ValueError(f"triangle {triangle_index} is collapsed by index")
        triangle = tuple(vertices[index] for index in face)
        area2 = _length(_cross(_sub(triangle[1], triangle[0]), _sub(triangle[2], triangle[0])))
        if area2 <= epsilon:
            raise ValueError(f"triangle {triangle_index} is geometrically degenerate")
        triangle_indices.append(face)
        triangles.append(triangle)
        boxes.append(_aabb(triangle))

    candidate_pairs = 0
    skipped_topological_neighbors = 0
    broad_phase_pairs = 0
    intersections = []
    for left in range(len(triangles)):
        left_vertices = set(triangle_indices[left])
        for right in range(left + 1, len(triangles)):
            candidate_pairs += 1
            if left_vertices.intersection(triangle_indices[right]):
                skipped_topological_neighbors += 1
                continue
            if not _aabb_overlap(boxes[left], boxes[right], epsilon):
                continue
            broad_phase_pairs += 1
            if _triangles_intersect(triangles[left], triangles[right], epsilon):
                intersections.append({"triangle_a": left, "triangle_b": right})

    status = "PASS_NO_NONADJACENT_SELF_INTERSECTIONS" if not intersections else "SELF_INTERSECTIONS_DETECTED"
    return {
        "status": status,
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "epsilon": epsilon,
        "triangle_pair_count": candidate_pairs,
        "skipped_topological_neighbor_pairs": skipped_topological_neighbors,
        "broad_phase_candidate_pairs": broad_phase_pairs,
        "self_intersection_pair_count": len(intersections),
        "examples": intersections[:max_examples],
        "truth_boundary": {
            "nonadjacent_triangle_self_intersection_checked": True,
            "topological_neighbor_contacts_excluded": True,
            "continuous_deformation_checked": False,
            "visual_quality_checked": False,
            "collision_or_gameplay_checked": False,
        },
    }
