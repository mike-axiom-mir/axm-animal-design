"""Bounded connected-chain topology study for animal geometry.

This module builds one renderer-neutral closed tube through an authored landmark
chain. It is a geometry/topology candidate only: it does not alter the canonical
organic-form baseline, prove deformation quality, or claim visual acceptance.
"""
from __future__ import annotations

import math
from collections import defaultdict
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


def derive_shared_ring_radii(regions: Iterable[dict], region_ids: Sequence[str]) -> dict:
    """Derive shared-ring radii from an ordered source segment chain.

    Endpoints preserve the source segment endpoint radii exactly. When two source
    segments meet at one landmark with different endpoint radii, the connected
    candidate uses their arithmetic mean for that one shared ring and records both
    authored values. This keeps the reconciliation policy explicit instead of
    silently hand-authoring a replacement radius.
    """
    if isinstance(region_ids, (str, bytes)) or not isinstance(region_ids, (list, tuple)) or not region_ids:
        raise ValueError("region_ids must be a non-empty ordered sequence")

    by_id = {}
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            raise ValueError(f"regions[{index}] must be an object")
        identifier = region.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"regions[{index}].id must be non-empty text")
        if identifier in by_id:
            raise ValueError(f"duplicate region id {identifier}")
        by_id[identifier] = region

    selected = []
    for index, identifier in enumerate(region_ids):
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"region_ids[{index}] must be non-empty text")
        if identifier not in by_id:
            raise ValueError(f"unknown region id {identifier}")
        region = by_id[identifier]
        if region.get("kind") != "segment":
            raise ValueError(f"{identifier} must be a segment region")
        a, b = region.get("a"), region.get("b")
        if not isinstance(a, str) or not a or not isinstance(b, str) or not b:
            raise ValueError(f"{identifier} must reference named endpoint landmarks")
        radius_a = _num(region.get("radius_a"), f"{identifier}.radius_a")
        radius_b = _num(region.get("radius_b"), f"{identifier}.radius_b")
        if radius_a <= 0 or radius_b <= 0:
            raise ValueError(f"{identifier} radii must be > 0")
        selected.append({
            "id": identifier,
            "a": a,
            "b": b,
            "radius_a": radius_a,
            "radius_b": radius_b,
        })

    path_landmarks = [selected[0]["a"]]
    radii = [selected[0]["radius_a"]]
    junctions = []
    for left, right in zip(selected, selected[1:]):
        if left["b"] != right["a"]:
            raise ValueError(f"source segment chain is discontinuous: {left['id']} -> {right['id']}")
        incoming = left["radius_b"]
        outgoing = right["radius_a"]
        shared = (incoming + outgoing) * 0.5
        path_landmarks.append(left["b"])
        radii.append(shared)
        junctions.append({
            "landmark": left["b"],
            "incoming_region": left["id"],
            "outgoing_region": right["id"],
            "incoming_radius_m": incoming,
            "outgoing_radius_m": outgoing,
            "shared_ring_radius_m": shared,
            "authored_radius_gap_m": abs(incoming - outgoing),
        })

    path_landmarks.append(selected[-1]["b"])
    radii.append(selected[-1]["radius_b"])
    return {
        "policy": "preserve-endpoints_mean-adjacent-junction-radii",
        "region_ids": list(region_ids),
        "path_landmarks": path_landmarks,
        "radii_m": radii,
        "junctions": junctions,
    }


def inspect_vertex_fan_connectivity(
    positions: Iterable[Sequence[float]],
    indices: Iterable[int],
    *,
    max_examples: int = 16,
) -> dict:
    """Inspect indexed triangle fans around every source vertex.

    This is a deliberately local receiving-domain diagnostic. It detects bow-tie
    style vertices where incident triangles split into multiple edge-connected
    fans, plus isolated indexed vertices. It does not weld positional seams and it
    does not test geometric self-intersection.
    """
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
    if type(max_examples) is not int or max_examples < 0:
        raise ValueError("max_examples must be a non-negative integer")

    faces: list[tuple[int, int, int]] = []
    incident_faces: list[list[int]] = [[] for _ in vertices]
    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)

    for triangle_index in range(len(raw_indices) // 3):
        face = tuple(raw_indices[triangle_index * 3: triangle_index * 3 + 3])
        if len(set(face)) != 3:
            raise ValueError(f"triangle {triangle_index} is collapsed by index")
        faces.append(face)
        for vertex in face:
            incident_faces[vertex].append(triangle_index)
        a, b, c = face
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (start, end) if start < end else (end, start)
            edge_faces[edge].append(triangle_index)

    isolated_vertices = []
    disconnected_fans = []
    max_fan_components = 0

    for vertex, incident in enumerate(incident_faces):
        if not incident:
            isolated_vertices.append(vertex)
            continue

        incident_set = set(incident)
        adjacency = {triangle: set() for triangle in incident}
        for triangle in incident:
            others = [item for item in faces[triangle] if item != vertex]
            for other in others:
                edge = (vertex, other) if vertex < other else (other, vertex)
                for neighbor in edge_faces[edge]:
                    if neighbor != triangle and neighbor in incident_set:
                        adjacency[triangle].add(neighbor)
                        adjacency[neighbor].add(triangle)

        remaining = set(incident)
        components = 0
        while remaining:
            components += 1
            stack = [remaining.pop()]
            while stack:
                current = stack.pop()
                for neighbor in adjacency[current]:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)

        max_fan_components = max(max_fan_components, components)
        if components != 1:
            disconnected_fans.append({
                "vertex": vertex,
                "incident_triangle_count": len(incident),
                "fan_component_count": components,
            })

    status = (
        "PASS_CONNECTED_VERTEX_FANS"
        if not isolated_vertices and not disconnected_fans
        else "DISCONNECTED_OR_ISOLATED_VERTEX_FANS"
    )
    return {
        "status": status,
        "vertex_count": len(vertices),
        "triangle_count": len(raw_indices) // 3,
        "isolated_vertex_count": len(isolated_vertices),
        "disconnected_vertex_fan_count": len(disconnected_fans),
        "max_vertex_fan_components": max_fan_components,
        "examples": {
            "isolated_vertices": isolated_vertices[:max_examples],
            "disconnected_vertex_fans": disconnected_fans[:max_examples],
        },
        "truth_boundary": {
            "indexed_vertex_fan_connectivity_checked": True,
            "positional_seams_welded": False,
            "edge_incidence_checked": False,
            "self_intersection_checked": False,
            "deformation_quality_checked": False,
            "visual_quality_checked": False,
        },
    }


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
