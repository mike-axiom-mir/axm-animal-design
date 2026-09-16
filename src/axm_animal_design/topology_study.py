"""Bounded connected-chain topology study for animal geometry.

This module builds one renderer-neutral closed tube through an authored landmark
chain. It is a geometry/topology candidate only: it does not alter the canonical
organic-form baseline, prove deformation quality, or claim visual acceptance.
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


def _length(value):
    return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    length = _length(value)
    if length <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return _mul(value, 1.0 / length)


def _tangents(points):
    tangents = []
    for index in range(len(points)):
        if index == 0:
            raw = _sub(points[1], points[0])
        elif index == len(points) - 1:
            raw = _sub(points[-1], points[-2])
        else:
            raw = _sub(points[index + 1], points[index - 1])
        tangents.append(_unit(raw, f"tangent[{index}]"))
    return tangents


def _frames(tangents):
    first = tangents[0]
    helper = (0.0, 0.0, 1.0) if abs(first[2]) < 0.9 else (0.0, 1.0, 0.0)
    side = _unit(_cross(first, helper), "initial side")
    frames = []
    for index, tangent in enumerate(tangents):
        if index:
            projected = _sub(side, _mul(tangent, _dot(side, tangent)))
            if _length(projected) <= 1e-8:
                helper = (0.0, 0.0, 1.0) if abs(tangent[2]) < 0.9 else (0.0, 1.0, 0.0)
                projected = _cross(tangent, helper)
            side = _unit(projected, f"transported side[{index}]")
        up = _unit(_cross(tangent, side), f"up[{index}]")
        frames.append((side, up))
    return frames


def build_connected_chain(
    identifier: str,
    points: Iterable[Sequence[float]],
    radii: Iterable[float],
    *,
    segments: int = 10,
) -> dict:
    """Build one closed connected tube through >=2 authored path points.

    Interior path points share one ring each, so adjacent spans are topologically
    continuous instead of separate capped primitives. Endpoint poles close the tube.
    The function intentionally emits positions/indices only; material, rigging,
    normals/tangents and visual acceptance remain separate concerns.
    """
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("identifier must be non-empty text")
    points = tuple(_point(value, f"points[{index}]") for index, value in enumerate(points))
    radii = tuple(_num(value, f"radii[{index}]") for index, value in enumerate(radii))
    if len(points) < 2 or len(points) != len(radii):
        raise ValueError("points/radii must have equal length >= 2")
    if any(radius <= 0 for radius in radii):
        raise ValueError("radii must be > 0")
    if type(segments) is not int or not 6 <= segments <= 64:
        raise ValueError("segments must be an integer in 6..64")
    for index in range(len(points) - 1):
        if math.dist(points[index], points[index + 1]) <= 1e-8:
            raise ValueError(f"points[{index}] and points[{index + 1}] coincide")

    tangents = _tangents(points)
    frames = _frames(tangents)

    start_extent = min(radii[0] * 0.5, math.dist(points[0], points[1]) * 0.15)
    end_extent = min(radii[-1] * 0.5, math.dist(points[-2], points[-1]) * 0.15)
    positions = [_sub(points[0], _mul(tangents[0], start_extent))]

    for point, radius, (side, up) in zip(points, radii, frames):
        for segment in range(segments):
            theta = 2.0 * math.pi * segment / segments
            radial = _add(_mul(side, math.cos(theta) * radius), _mul(up, math.sin(theta) * radius))
            positions.append(_add(point, radial))

    end_index = len(positions)
    positions.append(_add(points[-1], _mul(tangents[-1], end_extent)))

    indices: list[int] = []
    first_ring = 1
    for segment in range(segments):
        current = first_ring + segment
        nxt = first_ring + (segment + 1) % segments
        indices.extend([0, nxt, current])

    for ring in range(len(points) - 1):
        start = 1 + ring * segments
        nxt_ring = start + segments
        for segment in range(segments):
            a = start + segment
            b = start + (segment + 1) % segments
            c = nxt_ring + segment
            d = nxt_ring + (segment + 1) % segments
            indices.extend([a, b, c, b, d, c])

    last_ring = 1 + (len(points) - 1) * segments
    for segment in range(segments):
        current = last_ring + segment
        nxt = last_ring + (segment + 1) % segments
        indices.extend([current, nxt, end_index])

    return {
        "id": identifier,
        "positions": [[round(value, 9) for value in point] for point in positions],
        "indices": indices,
        "path_points": [list(point) for point in points],
        "radii": list(radii),
        "segments": segments,
        "truth_boundary": {
            "connected_chain_candidate": True,
            "canonical_source_rewritten": False,
            "deformation_tested": False,
            "visual_quality_checked": False,
            "self_intersection_checked": False,
        },
    }
