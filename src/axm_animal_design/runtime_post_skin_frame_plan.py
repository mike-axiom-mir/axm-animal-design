"""Runtime-oriented compiled plan for Animal post-skin direction-frame reconstruction.

Rigging owns the reconstruction semantics. Technical Art owns the receiving
contract. This module changes neither. It compiles only the *static* parts of the
already-proved owner reconstruction so a receiving runtime does not rebuild
layout/topology/UV derivative metadata on every pose update.

This is Animal-local evidence machinery until a real target-runtime consumer is
separately implemented and accepted. Universal Creation is not modified here.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from . import bilateral_deformed_tangent_frames as tangent_owner
from . import bilateral_logical_quad_normals as normal_owner
from .bilateral_uv_tangent_basis import BASIS_ID, RECORD_SCHEMA as UV_TANGENT_RECORD_SCHEMA

PLAN_SCHEMA = "axm.animal-runtime-post-skin-frame-plan/v0.1"
PLAN_ID = "quadruped-front-elbow-post-skin-owner-frame-plan-001"


def _int_list(values: Sequence[Any], label: str) -> list[int]:
    output: list[int] = []
    for index, value in enumerate(values):
        if type(value) is not int:
            raise ValueError(f"{label}[{index}] must be an integer")
        output.append(value)
    return output


def compile_post_skin_frame_plan(
    candidate: dict[str, Any],
    static_basis: dict[str, Any],
) -> dict[str, Any]:
    """Compile immutable receiving facts used by every reconstructed pose.

    The owner implementation deliberately re-validates and re-derives several
    static facts because it is an evidence observer. A runtime receiver does not
    need to repay that cost every frame when candidate topology, UVs and the
    render/source mapping are identity-pinned.
    """
    positions, _path, segments, ring_count = normal_owner._layout(candidate)
    if static_basis.get("schema") != UV_TANGENT_RECORD_SCHEMA:
        raise ValueError("static UV/tangent basis schema drift")
    if static_basis.get("id") != BASIS_ID:
        raise ValueError("static UV/tangent basis identity drift")

    render_source_indices = _int_list(
        static_basis.get("render_source_indices", []),
        "render_source_indices",
    )
    render_indices = _int_list(static_basis.get("render_indices", []), "render_indices")
    render_uvs = [
        [float(value) for value in uv]
        for uv in static_basis.get("render_uvs", [])
    ]
    source_vertex_count = int(static_basis.get("source_vertex_count", -1))
    if source_vertex_count != len(positions):
        raise ValueError("static basis source-vertex count drift")
    if len(render_source_indices) != len(render_uvs):
        raise ValueError("render mapping / UV count drift")
    if len(render_indices) % 3:
        raise ValueError("render index count drift")
    if any(index < 0 or index >= len(render_source_indices) for index in render_indices):
        raise ValueError("render index out of range")

    source_groups: list[list[int]] = [[] for _ in range(source_vertex_count)]
    for render_index, source_index in enumerate(render_source_indices):
        if source_index < 0 or source_index >= source_vertex_count:
            raise ValueError("render source index out of range")
        source_groups[source_index].append(render_index)
    if any(not group for group in source_groups):
        raise ValueError("compiled render/source mapping leaves a source vertex unrepresented")

    logical_quads: list[list[int]] = []
    for ring in range(ring_count - 1):
        for segment in range(segments):
            a = normal_owner._ring_index(ring, segment, segments)
            b = normal_owner._ring_index(ring, segment + 1, segments)
            c = normal_owner._ring_index(ring + 1, segment, segments)
            d = normal_owner._ring_index(ring + 1, segment + 1, segments)
            logical_quads.append([a, b, c, d, ring, ring + 1])

    start_cap_wedges = [
        [
            0,
            normal_owner._ring_index(0, segment, segments),
            normal_owner._ring_index(0, segment + 1, segments),
        ]
        for segment in range(segments)
    ]
    last_ring = ring_count - 1
    end_pole = len(positions) - 1
    end_cap_wedges = [
        [
            end_pole,
            normal_owner._ring_index(last_ring, segment, segments),
            normal_owner._ring_index(last_ring, segment + 1, segments),
        ]
        for segment in range(segments)
    ]

    tangent_triangles: list[dict[str, Any]] = []
    for offset in range(0, len(render_indices), 3):
        ia, ib, ic = render_indices[offset:offset + 3]
        uv0, uv1, uv2 = render_uvs[ia], render_uvs[ib], render_uvs[ic]
        duv1 = tangent_owner._sub(uv1, uv0)
        duv2 = tangent_owner._sub(uv2, uv0)
        determinant = duv1[0] * duv2[1] - duv1[1] * duv2[0]
        if abs(determinant) <= tangent_owner.EPSILON:
            raise ValueError("fixed Geometry UV basis contains a UV-degenerate triangle")
        tangent_triangles.append(
            {
                "indices": [ia, ib, ic],
                "duv1": [float(duv1[0]), float(duv1[1])],
                "duv2": [float(duv2[0]), float(duv2[1])],
                "reciprocal_determinant": float(1.0 / determinant),
            }
        )

    return {
        "schema": PLAN_SCHEMA,
        "id": PLAN_ID,
        "source_vertex_count": source_vertex_count,
        "segments": segments,
        "ring_count": ring_count,
        "render_vertex_count": len(render_source_indices),
        "render_index_count": len(render_indices),
        "logical_quads": logical_quads,
        "start_cap_wedges": start_cap_wedges,
        "end_cap_wedges": end_cap_wedges,
        "source_groups": source_groups,
        "render_source_indices": render_source_indices,
        "render_uvs": render_uvs,
        "render_indices": render_indices,
        "semantic_vertex_keys": list(static_basis.get("semantic_vertex_keys", [])),
        "tangent_triangles": tangent_triangles,
        "truth_boundary": {
            "rigging_owner_algorithm_changed": False,
            "technical_art_contract_changed": False,
            "source_geometry_changed": False,
            "uvs_changed": False,
            "runtime_static_facts_compiled_once": True,
            "target_runtime_implementation_claimed": False,
        },
    }


def _pose_local_path_points(plan: dict[str, Any], posed_positions: Sequence[Sequence[float]]) -> list[list[float]]:
    segments = int(plan["segments"])
    ring_count = int(plan["ring_count"])
    points: list[list[float]] = []
    for ring in range(ring_count):
        ring_points = [
            posed_positions[normal_owner._ring_index(ring, segment, segments)]
            for segment in range(segments)
        ]
        points.append(
            [
                sum(float(point[axis]) for point in ring_points) / float(segments)
                for axis in range(3)
            ]
        )
    return points


def _derive_owner_normals_compiled(
    plan: dict[str, Any],
    posed_positions: Sequence[Sequence[float]],
) -> list[list[float]]:
    positions = [tuple(float(value) for value in point) for point in posed_positions]
    if len(positions) != int(plan["source_vertex_count"]):
        raise ValueError("posed source-vertex count drift")
    path = [tuple(value) for value in _pose_local_path_points(plan, positions)]
    accumulated = [(0.0, 0.0, 0.0) for _ in positions]

    for a, b, c, d, ring_a, ring_b in plan["logical_quads"]:
        raw = normal_owner._newell((positions[a], positions[b], positions[d], positions[c]))
        radial_hint = (0.0, 0.0, 0.0)
        for vertex, center in (
            (a, path[ring_a]),
            (b, path[ring_a]),
            (c, path[ring_b]),
            (d, path[ring_b]),
        ):
            radial_hint = normal_owner._add(radial_hint, normal_owner._sub(positions[vertex], center))
        if normal_owner._dot(raw, radial_hint) < 0.0:
            raw = normal_owner._mul(raw, -1.0)
        if normal_owner._length(raw) <= 1e-14:
            raise ValueError("compiled logical quad became degenerate")
        for vertex in (a, b, c, d):
            accumulated[vertex] = normal_owner._add(accumulated[vertex], raw)

    start_pole = 0
    start_outward = normal_owner._unit(
        normal_owner._sub(positions[start_pole], path[0]),
        "compiled start cap outward",
    )
    for pole, current, nxt in plan["start_cap_wedges"]:
        raw = normal_owner._cross(
            normal_owner._sub(positions[nxt], positions[pole]),
            normal_owner._sub(positions[current], positions[pole]),
        )
        if normal_owner._dot(raw, start_outward) < 0.0:
            raw = normal_owner._mul(raw, -1.0)
        if normal_owner._length(raw) <= 1e-14:
            raise ValueError("compiled start cap wedge became degenerate")
        for vertex in (pole, nxt, current):
            accumulated[vertex] = normal_owner._add(accumulated[vertex], raw)

    end_pole = len(positions) - 1
    end_outward = normal_owner._unit(
        normal_owner._sub(positions[end_pole], path[-1]),
        "compiled end cap outward",
    )
    for pole, current, nxt in plan["end_cap_wedges"]:
        raw = normal_owner._cross(
            normal_owner._sub(positions[nxt], positions[current]),
            normal_owner._sub(positions[pole], positions[current]),
        )
        if normal_owner._dot(raw, end_outward) < 0.0:
            raw = normal_owner._mul(raw, -1.0)
        if normal_owner._length(raw) <= 1e-14:
            raise ValueError("compiled end cap wedge became degenerate")
        for vertex in (current, nxt, pole):
            accumulated[vertex] = normal_owner._add(accumulated[vertex], raw)

    return [
        normal_owner._rounded_unit(value, f"compiled normal[{index}]")
        for index, value in enumerate(accumulated)
    ]


def derive_frame_from_source_positions(
    plan: dict[str, Any],
    posed_positions: Sequence[Sequence[float]],
) -> dict[str, Any]:
    """Reconstruct the exact owner frame while reusing compiled static facts."""
    if plan.get("schema") != PLAN_SCHEMA or plan.get("id") != PLAN_ID:
        raise ValueError("runtime post-skin frame plan identity drift")
    source_normals = _derive_owner_normals_compiled(plan, posed_positions)
    render_source_indices = plan["render_source_indices"]
    render_positions = [
        [float(value) for value in posed_positions[source_index]]
        for source_index in render_source_indices
    ]
    render_normals = [
        [float(value) for value in source_normals[source_index]]
        for source_index in render_source_indices
    ]
    render_uvs = plan["render_uvs"]

    tangent_accum = [(0.0, 0.0, 0.0) for _ in render_positions]
    bitangent_accum = [(0.0, 0.0, 0.0) for _ in render_positions]
    for triangle in plan["tangent_triangles"]:
        ia, ib, ic = triangle["indices"]
        duv1 = triangle["duv1"]
        duv2 = triangle["duv2"]
        reciprocal = float(triangle["reciprocal_determinant"])
        e1 = tangent_owner._sub(render_positions[ib], render_positions[ia])
        e2 = tangent_owner._sub(render_positions[ic], render_positions[ia])
        tangent = tangent_owner._mul(
            tangent_owner._sub(
                tangent_owner._mul(e1, duv2[1]),
                tangent_owner._mul(e2, duv1[1]),
            ),
            reciprocal,
        )
        bitangent = tangent_owner._mul(
            tangent_owner._sub(
                tangent_owner._mul(e2, duv1[0]),
                tangent_owner._mul(e1, duv2[0]),
            ),
            reciprocal,
        )
        for vertex in (ia, ib, ic):
            tangent_accum[vertex] = tangent_owner._add(tangent_accum[vertex], tangent)
            bitangent_accum[vertex] = tangent_owner._add(bitangent_accum[vertex], bitangent)

    tangents: list[list[float]] = []
    maximum_tangent_unit_length_error = 0.0
    maximum_tangent_normal_dot_abs = 0.0
    for index, (normal_value, tangent_sum, bitangent_sum) in enumerate(
        zip(render_normals, tangent_accum, bitangent_accum)
    ):
        normal = tangent_owner._unit(normal_value, f"compiled posed normal[{index}]")
        projected = tangent_owner._sub(
            tangent_sum,
            tangent_owner._mul(normal, tangent_owner._dot(normal, tangent_sum)),
        )
        tangent = tangent_owner._unit(projected, f"compiled posed tangent[{index}]")
        handedness_probe = tangent_owner._dot(
            tangent_owner._cross(normal, tangent),
            bitangent_sum,
        )
        if abs(handedness_probe) <= tangent_owner.EPSILON:
            raise ValueError(f"compiled posed tangent[{index}] has ambiguous handedness")
        tangent4 = [
            float(tangent[0]),
            float(tangent[1]),
            float(tangent[2]),
            1.0 if handedness_probe > 0.0 else -1.0,
        ]
        tangents.append(tangent4)
        maximum_tangent_unit_length_error = max(
            maximum_tangent_unit_length_error,
            abs(tangent_owner._length(tangent4[:3]) - 1.0),
        )
        maximum_tangent_normal_dot_abs = max(
            maximum_tangent_normal_dot_abs,
            abs(tangent_owner._dot(normal, tangent4[:3])),
        )

    return {
        "render_positions": render_positions,
        "render_normals": render_normals,
        "render_uvs": render_uvs,
        "render_tangents": tangents,
        "render_indices": plan["render_indices"],
        "render_source_indices": render_source_indices,
        "semantic_vertex_keys": plan["semantic_vertex_keys"],
        "maximum_tangent_unit_length_error": maximum_tangent_unit_length_error,
        "maximum_tangent_normal_dot_abs": maximum_tangent_normal_dot_abs,
    }


def collapse_target_render_positions(
    plan: dict[str, Any],
    render_positions_target: Sequence[Sequence[float]],
) -> tuple[list[list[float]], float]:
    """Collapse UV splits with a precompiled source->render representative map."""
    if len(render_positions_target) != int(plan["render_vertex_count"]):
        raise ValueError("target render-position count drift")
    collapsed: list[list[float]] = []
    maximum_split_residual_m = 0.0
    for source_index, group in enumerate(plan["source_groups"]):
        if not group:
            raise ValueError(f"compiled source vertex {source_index} has no representative")
        reference = [float(value) for value in render_positions_target[group[0]]]
        for render_index in group[1:]:
            row = render_positions_target[render_index]
            maximum_split_residual_m = max(
                maximum_split_residual_m,
                tangent_owner._distance(reference, row),
            )
        # Exact inverse of Animal -> UC target mapping [-y, z, x].
        collapsed.append([reference[2], -reference[0], reference[1]])
    return collapsed, maximum_split_residual_m


def reconstruct_frame_from_target_render_positions(
    plan: dict[str, Any],
    render_positions_target: Sequence[Sequence[float]],
) -> tuple[dict[str, Any], float]:
    source_positions, split_residual = collapse_target_render_positions(plan, render_positions_target)
    return derive_frame_from_source_positions(plan, source_positions), split_residual


def compare_frames(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Measure representation-neutral frame-array differences."""
    maximum_position_component_abs = 0.0
    maximum_normal_component_abs = 0.0
    maximum_tangent_component_abs = 0.0
    handedness_mismatches = 0
    for before, after in zip(control["render_positions"], candidate["render_positions"]):
        maximum_position_component_abs = max(
            maximum_position_component_abs,
            *(abs(float(a) - float(b)) for a, b in zip(before, after)),
        )
    for before, after in zip(control["render_normals"], candidate["render_normals"]):
        maximum_normal_component_abs = max(
            maximum_normal_component_abs,
            *(abs(float(a) - float(b)) for a, b in zip(before, after)),
        )
    for before, after in zip(control["render_tangents"], candidate["render_tangents"]):
        maximum_tangent_component_abs = max(
            maximum_tangent_component_abs,
            *(abs(float(a) - float(b)) for a, b in zip(before[:3], after[:3])),
        )
        if float(before[3]) != float(after[3]):
            handedness_mismatches += 1
    static_identity = all(
        control[key] == candidate[key]
        for key in ("render_uvs", "render_indices", "render_source_indices", "semantic_vertex_keys")
    )
    exact_frame_arrays = (
        control["render_positions"] == candidate["render_positions"]
        and control["render_normals"] == candidate["render_normals"]
        and control["render_tangents"] == candidate["render_tangents"]
        and static_identity
    )
    return {
        "exact_frame_arrays": exact_frame_arrays,
        "static_identity": static_identity,
        "maximum_position_component_abs": maximum_position_component_abs,
        "maximum_normal_component_abs": maximum_normal_component_abs,
        "maximum_tangent_component_abs": maximum_tangent_component_abs,
        "tangent_handedness_mismatch_count": handedness_mismatches,
    }
