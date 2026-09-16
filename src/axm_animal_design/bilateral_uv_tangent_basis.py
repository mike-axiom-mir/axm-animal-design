"""Geometry-owned UV/tangent-basis candidate for the selected bilateral Animal elbow.

This closes only the structural UV/tangent dependency left by Geometry PR #16.
Source positions and source triangle records stay unchanged.  A small parametric
atlas expands only the render-vertex domain where UV continuity requires a split,
then derives an orthonormal tangent frame from positions + UVs + Geometry's
explicit logical-quad normals.  This is Animal-local evidence, not final texture
UVs, lookdev, transport, runtime, CANON or production readiness.
"""
from __future__ import annotations

import math
from typing import Any, Sequence

from .bilateral_logical_quad_normals import derive_logical_quad_normals
from .bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from .bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind
from .connected_deformation import digest
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP

RECORD_SCHEMA = "axm.animal-bilateral-uv-tangent-basis/v0.1"
BASIS_ID = "quadruped-front-elbow-bilateral-parametric-uv-tangent-basis-001"
PARENT_RIGGING_HEAD = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
NORMAL_GEOMETRY_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
MATERIALS_REVIEW_HEAD = "a2cd0a6135a7c8502aef9572f7079a3dd2632103"
MIRROR_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
ROUND_DIGITS = 12
EPSILON = 1e-12
MIRROR_TOLERANCE = 1e-9
SIDE_V_MIN = 0.30
SIDE_V_MAX = 0.70
START_CAP_CENTER = (0.13, 0.13)
END_CAP_CENTER = (0.87, 0.87)
CAP_RADIUS = 0.11


def _point(value: Sequence[float], label: str) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be a 3D point")
    output = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in output):
        raise ValueError(f"{label} must be finite")
    return output


def _add(a, b): return tuple(a[i] + b[i] for i in range(len(a)))
def _sub(a, b): return tuple(a[i] - b[i] for i in range(len(a)))
def _mul(a, scalar): return tuple(a[i] * scalar for i in range(len(a)))
def _dot(a, b): return sum(a[i] * b[i] for i in range(len(a)))
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _length(value): return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    length = _length(value)
    if length <= EPSILON:
        raise ValueError(f"{label} has zero length")
    return _mul(value, 1.0 / length)


def _rounded(values): return [round(float(value), ROUND_DIGITS) for value in values]


def _triangles(indices: Sequence[int]) -> list[tuple[int, int, int]]:
    values = [int(value) for value in indices]
    if not values or len(values) % 3:
        raise ValueError("candidate.indices must contain complete triangles")
    return [tuple(values[offset:offset + 3]) for offset in range(0, len(values), 3)]


def _layout(candidate: dict[str, Any]):
    positions = [_point(value, f"positions[{index}]") for index, value in enumerate(candidate.get("positions", []))]
    path = [_point(value, f"path_points[{index}]") for index, value in enumerate(candidate.get("path_points", []))]
    segments = candidate.get("segments")
    if type(segments) is not int or segments < 3 or len(path) < 2:
        raise ValueError("candidate requires segments >=3 and at least two path points")
    expected = 2 + len(path) * segments
    if len(positions) != expected:
        raise ValueError(f"expected pole + rings + pole layout with {expected} vertices, got {len(positions)}")
    return positions, path, segments, len(path)


def _ring_index(ring: int, segment: int, segments: int) -> int:
    return 1 + ring * segments + (segment % segments)


def _inverse_ring_segment_map(segments: int) -> tuple[int, ...]:
    if segments != len(RING_SEGMENT_MAP):
        raise ValueError("candidate segment count does not match exact Organic mirror map")
    inverse = [None] * segments
    for semantic_segment, right_segment in enumerate(RING_SEGMENT_MAP):
        inverse[int(right_segment)] = semantic_segment
    if any(value is None for value in inverse):
        raise ValueError("Organic mirror map is incomplete")
    return tuple(int(value) for value in inverse)


def _source_semantics(source_index: int, *, segments: int, ring_count: int, side: str) -> dict[str, Any]:
    end_pole = 1 + ring_count * segments
    if source_index == 0:
        return {"kind": "start_pole", "semantic_source_index": 0}
    if source_index == end_pole:
        return {"kind": "end_pole", "semantic_source_index": end_pole}
    if not 1 <= source_index < end_pole:
        raise ValueError(f"source index {source_index} out of range")
    ring = (source_index - 1) // segments
    raw_segment = (source_index - 1) % segments
    if side == "left":
        semantic_segment = raw_segment
    elif side == "right":
        semantic_segment = _inverse_ring_segment_map(segments)[raw_segment]
    else:
        raise ValueError("side must be left or right")
    return {
        "kind": "ring", "ring": ring, "raw_segment": raw_segment,
        "semantic_segment": semantic_segment,
        "semantic_source_index": _ring_index(ring, semantic_segment, segments),
    }


def _path_fractions(path):
    cumulative = [0.0]
    for left, right in zip(path, path[1:]):
        distance = math.dist(left, right)
        if distance <= EPSILON:
            raise ValueError("path contains coincident neighbours")
        cumulative.append(cumulative[-1] + distance)
    total = cumulative[-1]
    return [value / total for value in cumulative]


def _cap_wedge_start(values, segments: int) -> int:
    unique = set(int(value) for value in values)
    if len(unique) != 2:
        raise ValueError("cap triangle must touch exactly two ring segments")
    for segment in unique:
        if (segment + 1) % segments in unique:
            return segment
    raise ValueError("cap triangle does not contain neighbouring semantic segments")


def _triangle_corner_uvs(face, *, side: str, segments: int, ring_count: int, path_fractions):
    semantics = [_source_semantics(index, segments=segments, ring_count=ring_count, side=side) for index in face]
    kinds = {item["kind"] for item in semantics}
    if "start_pole" in kinds or "end_pole" in kinds:
        if kinds == {"start_pole", "ring"}:
            island, center, pole_kind = "start_cap", START_CAP_CENTER, "start_pole"
        elif kinds == {"end_pole", "ring"}:
            island, center, pole_kind = "end_cap", END_CAP_CENTER, "end_pole"
        else:
            raise ValueError("triangle mixes invalid pole/ring domains")
        ring_items = [item for item in semantics if item["kind"] == "ring"]
        wedge = _cap_wedge_start([item["semantic_segment"] for item in ring_items], segments)
        output = []
        for item in semantics:
            if item["kind"] == pole_kind:
                output.append({"uv": center, "island": island, "split_tag": f"{island}_pole_wedge_{wedge}", "semantic_source_index": item["semantic_source_index"]})
            elif item["kind"] == "ring":
                theta = 2.0 * math.pi * item["semantic_segment"] / segments
                output.append({"uv": (center[0] + CAP_RADIUS*math.cos(theta), center[1] + CAP_RADIUS*math.sin(theta)), "island": island, "split_tag": island, "semantic_source_index": item["semantic_source_index"]})
            else:
                raise ValueError("unexpected cap corner")
        return output
    if kinds != {"ring"}:
        raise ValueError("non-cap triangle must contain ring vertices only")
    rings = sorted({int(item["ring"]) for item in semantics})
    semantic_segments = {int(item["semantic_segment"]) for item in semantics}
    if len(rings) != 2 or rings[1] != rings[0] + 1 or len(semantic_segments) != 2:
        raise ValueError("side triangle must span adjacent rings and segments")
    wrap = (segments - 1 in semantic_segments) and (0 in semantic_segments)
    output = []
    for item in semantics:
        semantic_segment = int(item["semantic_segment"])
        unwrapped = segments if wrap and semantic_segment == 0 else semantic_segment
        output.append({
            "uv": (unwrapped / segments, SIDE_V_MIN + (SIDE_V_MAX-SIDE_V_MIN)*path_fractions[int(item["ring"])]),
            "island": "side", "split_tag": "side", "semantic_source_index": item["semantic_source_index"],
        })
    return output


def _triangle_tangent(p0, p1, p2, uv0, uv1, uv2):
    e1, e2 = _sub(p1, p0), _sub(p2, p0)
    duv1, duv2 = _sub(uv1, uv0), _sub(uv2, uv0)
    determinant = duv1[0]*duv2[1] - duv1[1]*duv2[0]
    if abs(determinant) <= EPSILON:
        raise ValueError("UV-degenerate triangle cannot define a tangent frame")
    reciprocal = 1.0 / determinant
    tangent = _mul(_sub(_mul(e1, duv2[1]), _mul(e2, duv1[1])), reciprocal)
    bitangent = _mul(_sub(_mul(e2, duv1[0]), _mul(e1, duv2[0])), reciprocal)
    return tangent, bitangent, abs(determinant) * 0.5


def derive_uv_tangent_basis(candidate: dict[str, Any], *, side: str) -> dict[str, Any]:
    positions, path, segments, ring_count = _layout(candidate)
    normals = derive_logical_quad_normals(candidate)["normals"]
    path_fractions = _path_fractions(path)
    render_positions, render_normals, render_uvs = [], [], []
    render_source_indices, semantic_keys, render_indices, source_indices, corner_islands = [], [], [], [], []
    vertex_by_key = {}

    for face in _triangles(candidate["indices"]):
        corner_uvs = _triangle_corner_uvs(face, side=side, segments=segments, ring_count=ring_count, path_fractions=path_fractions)
        for source_index, corner in zip(face, corner_uvs):
            uv_value = tuple(round(float(value), ROUND_DIGITS) for value in corner["uv"])
            semantic_key = (int(corner["semantic_source_index"]), uv_value, str(corner["split_tag"]))
            if semantic_key not in vertex_by_key:
                vertex_by_key[semantic_key] = len(render_positions)
                render_positions.append(_rounded(positions[source_index]))
                render_normals.append(_rounded(normals[source_index]))
                render_uvs.append(_rounded(uv_value))
                render_source_indices.append(int(source_index))
                semantic_keys.append(repr(semantic_key))
            render_indices.append(vertex_by_key[semantic_key])
            source_indices.append(int(source_index))
            corner_islands.append(str(corner["island"]))

    tangent_accum = [(0.0,0.0,0.0) for _ in render_positions]
    bitangent_accum = [(0.0,0.0,0.0) for _ in render_positions]
    uv_triangle_areas = []
    for offset in range(0, len(render_indices), 3):
        ia, ib, ic = render_indices[offset:offset+3]
        tangent, bitangent, area = _triangle_tangent(render_positions[ia], render_positions[ib], render_positions[ic], render_uvs[ia], render_uvs[ib], render_uvs[ic])
        uv_triangle_areas.append(area)
        for vertex in (ia, ib, ic):
            tangent_accum[vertex] = _add(tangent_accum[vertex], tangent)
            bitangent_accum[vertex] = _add(bitangent_accum[vertex], bitangent)

    tangents = []
    max_orthogonality_error = max_tangent_unit_error = 0.0
    for index, (normal_value, tangent_sum, bitangent_sum) in enumerate(zip(render_normals, tangent_accum, bitangent_accum)):
        normal = _unit(normal_value, f"normal[{index}]")
        projected = _sub(tangent_sum, _mul(normal, _dot(normal, tangent_sum)))
        tangent = _unit(projected, f"tangent[{index}]")
        handedness_probe = _dot(_cross(normal, tangent), bitangent_sum)
        if abs(handedness_probe) <= EPSILON:
            raise ValueError(f"tangent[{index}] has ambiguous handedness")
        tangent_record = _rounded((*tangent, 1.0 if handedness_probe > 0 else -1.0))
        tangents.append(tangent_record)
        max_orthogonality_error = max(max_orthogonality_error, abs(_dot(normal, tangent_record[:3])))
        max_tangent_unit_error = max(max_tangent_unit_error, abs(_length(tangent_record[:3])-1.0))

    reconstructed = [render_source_indices[index] for index in render_indices]
    side_u_spans, naive_side_u_spans = [], []
    for offset in range(0, len(source_indices), 3):
        if corner_islands[offset:offset+3] != ["side","side","side"]:
            continue
        actual = [render_uvs[render_indices[offset+i]][0] for i in range(3)]
        side_u_spans.append(max(actual)-min(actual))
        naive = []
        for source_index in source_indices[offset:offset+3]:
            item = _source_semantics(source_index, segments=segments, ring_count=ring_count, side=side)
            naive.append(float(item["semantic_segment"])/segments)
        naive_side_u_spans.append(max(naive)-min(naive))

    expected_render_vertices = ring_count*(segments+1) + 4*segments
    return {
        "schema": RECORD_SCHEMA, "id": BASIS_ID, "side": side,
        "source_candidate_id": candidate.get("id"), "source_candidate_digest": digest(candidate),
        "uv_policy": "STRUCTURAL_PARAMETRIC_THREE_ISLAND_ATLAS_NOT_FINAL_TEXTURE_UV",
        "tangent_policy": "EXPLICIT_UV_DERIVED_ORTHONORMAL_TANGENT_FRAME_CANDIDATE",
        "source_vertex_count": len(positions), "render_vertex_count": len(render_positions),
        "expected_render_vertex_count": expected_render_vertices, "triangle_count": len(render_indices)//3,
        "render_positions": render_positions, "render_normals": render_normals, "render_uvs": render_uvs,
        "render_tangents": tangents, "render_indices": render_indices,
        "render_source_indices": render_source_indices, "source_indices_by_corner": source_indices,
        "semantic_vertex_keys": semantic_keys,
        "minimum_uv_triangle_area": min(uv_triangle_areas),
        "maximum_tangent_normal_dot_abs": max_orthogonality_error,
        "maximum_tangent_unit_length_error": max_tangent_unit_error,
        "maximum_side_triangle_u_span": max(side_u_spans),
        "naive_unsplit_maximum_side_triangle_u_span": max(naive_side_u_spans),
        "source_triangle_records_preserved": reconstructed == source_indices == list(candidate["indices"]),
        "source_triangle_positions_preserved": all(render_positions[ri] == _rounded(positions[si]) for ri, si in zip(render_indices, source_indices)),
        "uvs_within_unit_square": all(-EPSILON <= uv[0] <= 1+EPSILON and -EPSILON <= uv[1] <= 1+EPSILON for uv in render_uvs),
        "truth_boundary": {
            "source_positions_modified": False, "source_triangle_records_modified": False,
            "render_vertex_domain_split_for_uvs": True, "source_normals_replaced": False,
            "final_texture_uv_claimed": False, "texel_density_checked": False,
            "tangent_space_normal_map_checked": False, "deformed_shaded_quality_checked": False,
            "transport_checked": False, "runtime_cost_accepted": False, "canon_claimed": False,
        },
    }


def _basis_by_semantic_key(basis):
    output = {}
    for index, key in enumerate(basis["semantic_vertex_keys"]):
        if key in output:
            raise ValueError("semantic render-vertex key is not unique")
        output[key] = {name: basis[field][index] for name, field in (("position","render_positions"),("normal","render_normals"),("uv","render_uvs"),("tangent","render_tangents"))}
    return output


def _residual(a, b): return math.dist(tuple(float(v) for v in a), tuple(float(v) for v in b))


def compare_bilateral_uv_tangent_basis(left_basis, right_basis):
    left, right = _basis_by_semantic_key(left_basis), _basis_by_semantic_key(right_basis)
    if set(left) != set(right):
        raise ValueError("left/right render-domain semantic keys differ")
    maxima = {"position":0.0,"normal":0.0,"uv":0.0,"tangent":0.0}
    handedness_mismatches = 0
    for key in left:
        lvalue, rvalue = left[key], right[key]
        maxima["position"] = max(maxima["position"], _residual((lvalue["position"][0],-lvalue["position"][1],lvalue["position"][2]), rvalue["position"]))
        maxima["normal"] = max(maxima["normal"], _residual((lvalue["normal"][0],-lvalue["normal"][1],lvalue["normal"][2]), rvalue["normal"]))
        maxima["uv"] = max(maxima["uv"], _residual(lvalue["uv"], rvalue["uv"]))
        maxima["tangent"] = max(maxima["tangent"], _residual((lvalue["tangent"][0],-lvalue["tangent"][1],lvalue["tangent"][2]), rvalue["tangent"][:3]))
        if float(rvalue["tangent"][3]) != -float(lvalue["tangent"][3]):
            handedness_mismatches += 1
    return {
        "semantic_render_vertex_count": len(left),
        "maximum_mirrored_position_residual": maxima["position"],
        "maximum_mirrored_normal_residual": maxima["normal"],
        "maximum_uv_residual": maxima["uv"],
        "maximum_mirrored_tangent_xyz_residual": maxima["tangent"],
        "tangent_handedness_mismatch_count": handedness_mismatches,
    }


def inspect_bilateral_uv_tangent_basis(spec, left_profile, bilateral_profile):
    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(spec, left_profile, bilateral_profile)
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("bilateral source-successor topology prerequisite is not PASS")
    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise ValueError("exact-mirror surface topology prerequisite is not PASS")
    left_basis = derive_uv_tangent_basis(left, side="left")
    right_basis = derive_uv_tangent_basis(exact_right, side="right")
    bilateral = compare_bilateral_uv_tangent_basis(left_basis, right_basis)
    expected_side_span = 1.0/int(left["segments"])
    gates = {
        "source-triangle-records-preserved": left_basis["source_triangle_records_preserved"] and right_basis["source_triangle_records_preserved"],
        "source-triangle-positions-preserved": left_basis["source_triangle_positions_preserved"] and right_basis["source_triangle_positions_preserved"],
        "render-domain-split-count-exact": left_basis["render_vertex_count"] == left_basis["expected_render_vertex_count"] == right_basis["render_vertex_count"] == right_basis["expected_render_vertex_count"],
        "zero-uv-degenerate-triangles": left_basis["minimum_uv_triangle_area"] > EPSILON and right_basis["minimum_uv_triangle_area"] > EPSILON,
        "uvs-in-unit-square": left_basis["uvs_within_unit_square"] and right_basis["uvs_within_unit_square"],
        "side-seam-unwrapped": left_basis["maximum_side_triangle_u_span"] <= expected_side_span+MIRROR_TOLERANCE and right_basis["maximum_side_triangle_u_span"] <= expected_side_span+MIRROR_TOLERANCE,
        "naive-unsplit-control-exposes-large-seam-span": left_basis["naive_unsplit_maximum_side_triangle_u_span"] > 0.5 and right_basis["naive_unsplit_maximum_side_triangle_u_span"] > 0.5,
        "tangents-unit": left_basis["maximum_tangent_unit_length_error"] <= MIRROR_TOLERANCE and right_basis["maximum_tangent_unit_length_error"] <= MIRROR_TOLERANCE,
        "tangents-orthogonal-to-explicit-normals": left_basis["maximum_tangent_normal_dot_abs"] <= MIRROR_TOLERANCE and right_basis["maximum_tangent_normal_dot_abs"] <= MIRROR_TOLERANCE,
        "bilateral-render-positions-exact-mirror": bilateral["maximum_mirrored_position_residual"] <= MIRROR_TOLERANCE,
        "bilateral-explicit-normals-exact-mirror": bilateral["maximum_mirrored_normal_residual"] <= MIRROR_TOLERANCE,
        "bilateral-uvs-exact-semantic-match": bilateral["maximum_uv_residual"] <= MIRROR_TOLERANCE,
        "bilateral-tangent-xyz-exact-mirror": bilateral["maximum_mirrored_tangent_xyz_residual"] <= MIRROR_TOLERANCE,
        "bilateral-tangent-handedness-reflection-correct": bilateral["tangent_handedness_mismatch_count"] == 0,
    }
    state = "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD" if all(gates.values()) else "FAIL_BILATERAL_UV_TANGENT_BASIS_CANDIDATE"
    record = {
        "schema": RECORD_SCHEMA, "state": state, "basis_id": BASIS_ID,
        "parent_rigging_head": PARENT_RIGGING_HEAD, "normal_geometry_head": NORMAL_GEOMETRY_HEAD,
        "materials_review_head": MATERIALS_REVIEW_HEAD, "mirror_topology_head": MIRROR_TOPOLOGY_HEAD,
        "source_vertex_count": left_basis["source_vertex_count"], "render_vertex_count": left_basis["render_vertex_count"],
        "render_vertex_overhead": left_basis["render_vertex_count"]-left_basis["source_vertex_count"],
        "triangle_count": left_basis["triangle_count"],
        "minimum_uv_triangle_area": min(left_basis["minimum_uv_triangle_area"],right_basis["minimum_uv_triangle_area"]),
        "maximum_side_triangle_u_span": max(left_basis["maximum_side_triangle_u_span"],right_basis["maximum_side_triangle_u_span"]),
        "naive_unsplit_maximum_side_triangle_u_span": max(left_basis["naive_unsplit_maximum_side_triangle_u_span"],right_basis["naive_unsplit_maximum_side_triangle_u_span"]),
        "maximum_tangent_normal_dot_abs": max(left_basis["maximum_tangent_normal_dot_abs"],right_basis["maximum_tangent_normal_dot_abs"]),
        "maximum_tangent_unit_length_error": max(left_basis["maximum_tangent_unit_length_error"],right_basis["maximum_tangent_unit_length_error"]),
        "bilateral": bilateral, "gates": {name:"PASS" if passed else "FAIL" for name,passed in gates.items()},
        "truth_boundary": {
            "source_geometry_modified": False, "exact_mirror_topology_modified": False,
            "explicit_normal_policy_modified": False, "structural_uv_basis_authored": True,
            "structural_tangent_basis_authored": True, "final_texture_uv_or_texel_density_accepted": False,
            "tangent_space_normal_map_rendered": False, "deformed_shaded_quality_checked": False,
            "technical_art_transport_checked": False, "runtime_storage_or_performance_accepted": False,
            "visual_preference_claimed": False, "canon_claimed": False,
        },
    }
    return left_basis, right_basis, record
