"""Technical-Art transport for Geometry-owned UV/tangent render vertices.

Geometry owns the UV/normal/tangent render domain. Rigging owns weights. Animation
owns keys. This receiver only maps those exact owner payloads into the established
Animal -> UC coordinate/glTF boundary; it does not author Animal domain data.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from typing import Any

from .uc_bridge import SOURCE_COORDINATES, TARGET_COORDINATES, _source_to_uc
from .uc_rigged_animation_bridge import (
    JOINT_ID,
    SOURCE_CANDIDATE_ID,
    WEIGHTING_ID,
    _f32,
    _flatten,
    _pad4,
    _posed,
    _quat,
    _select_right_elbow,
    _translation_matrix,
    _vec3,
    smoothstep_weights,
    source_axis_to_uc,
)

BRIDGE_SCHEMA = "axm.animal-uc-rigged-uv-tangent-bridge/v0.1"
GEOMETRY_BASIS_SCHEMA = "axm.animal-bilateral-uv-tangent-basis/v0.1"
GEOMETRY_BASIS_ID = "quadruped-front-elbow-bilateral-parametric-uv-tangent-basis-001"
TRANSPORT_SURFACE_ID = "animal-selected003-right-mirror-rigged-uv-tangent"
SOURCE_VERTEX_COUNT = 42
RENDER_VERTEX_COUNT = 84
TRIANGLE_COUNT = 80
KEY_COUNT = 41
UNSIGNED_BYTE = 5121
UNSIGNED_SHORT = 5123


@dataclass(frozen=True)
class PackedRiggedTangentGlb:
    bytes: bytes
    document: dict[str, Any]
    positions: list[list[float]]
    normals: list[list[float]]
    tangents: list[list[float]]
    texcoords: list[list[float]]
    joints: list[list[int]]
    weights: list[list[float]]
    indices: list[int]
    render_source_indices: list[int]
    pivot: list[float]
    axis: list[float]
    times: list[float]
    rotations: list[list[float]]


def _unit3(value: Any, label: str) -> list[float]:
    row = _vec3(value, label)
    length = math.sqrt(sum(component * component for component in row))
    if length <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return [component / length for component in row]


def source_direction_to_uc(value: Any, label: str) -> list[float]:
    return _unit3(_source_to_uc(_unit3(value, label), label), f"mapped {label}")


def source_tangent_to_uc(value: Any) -> list[float]:
    """Map tangent XYZ as a polar vector and flip W because det(M)=-1."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("source tangent must be [x,y,z,w]")
    xyz = source_direction_to_uc(value[:3], "tangent")
    handedness = float(value[3])
    if not math.isfinite(handedness) or abs(abs(handedness) - 1.0) > 1e-9:
        raise ValueError("source tangent handedness must be exactly +/-1")
    return [_f32(component) for component in xyz] + [_f32(-handedness)]


def _validate_geometry_basis(basis: dict[str, Any], neutral: list[list[float]]) -> list[int]:
    if basis.get("schema") != GEOMETRY_BASIS_SCHEMA or basis.get("id") != GEOMETRY_BASIS_ID:
        raise ValueError("Geometry UV/tangent basis identity drift")
    if basis.get("side") != "right" or basis.get("source_candidate_id") != SOURCE_CANDIDATE_ID:
        raise ValueError("Geometry right exact-mirror source identity drift")
    if basis.get("source_vertex_count") != SOURCE_VERTEX_COUNT or basis.get("render_vertex_count") != RENDER_VERTEX_COUNT:
        raise ValueError("Geometry source/render vertex-count contract drift")
    if basis.get("triangle_count") != TRIANGLE_COUNT:
        raise ValueError("Geometry triangle-count contract drift")
    for name, width in (("render_positions", 3), ("render_normals", 3), ("render_uvs", 2), ("render_tangents", 4)):
        rows = basis.get(name)
        if not isinstance(rows, list) or len(rows) != RENDER_VERTEX_COUNT:
            raise ValueError(f"Geometry {name} count drift")
        for index, row in enumerate(rows):
            if not isinstance(row, (list, tuple)) or len(row) != width:
                raise ValueError(f"Geometry {name}[{index}] width drift")
            if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in row):
                raise ValueError(f"Geometry {name}[{index}] must be finite numeric data")
    mapping = basis.get("render_source_indices")
    if not isinstance(mapping, list) or len(mapping) != RENDER_VERTEX_COUNT:
        raise ValueError("Geometry render-source mapping count drift")
    if any(type(index) is not int or not 0 <= index < SOURCE_VERTEX_COUNT for index in mapping):
        raise ValueError("Geometry render-source mapping contains invalid source index")
    if len(set(mapping)) != SOURCE_VERTEX_COUNT:
        raise ValueError("Geometry render-domain split collapsed or lost a source vertex")
    render_indices = basis.get("render_indices")
    if not isinstance(render_indices, list) or len(render_indices) != TRIANGLE_COUNT * 3:
        raise ValueError("Geometry render-index count drift")
    if any(type(index) is not int or not 0 <= index < RENDER_VERTEX_COUNT for index in render_indices):
        raise ValueError("Geometry render indices are invalid")
    if not isinstance(neutral, list) or len(neutral) != SOURCE_VERTEX_COUNT:
        raise ValueError("Animation neutral frame must contain exactly 42 source vertices")
    maximum = 0.0
    for render_index, source_index in enumerate(mapping):
        expected = _vec3(neutral[source_index], f"neutral[{source_index}]")
        observed = _vec3(basis["render_positions"][render_index], f"render_positions[{render_index}]")
        maximum = max(maximum, math.dist(expected, observed))
    if maximum > 1e-9:
        raise ValueError(f"Geometry render positions no longer reconstruct the Animation neutral source: {maximum}")
    return [int(index) for index in mapping]


def _reverse_winding(indices: list[int]) -> list[int]:
    output: list[int] = []
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        output.extend((a, c, b))
    return output


def _base_color(source_material: dict[str, Any]) -> list[float]:
    value = source_material.get("base_color")
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("Animal source material base_color must contain four values")
    output = [float(component) for component in value]
    if any(not math.isfinite(component) or not 0.0 <= component <= 1.0 for component in output):
        raise ValueError("Animal source material base_color must stay within 0..1")
    return output


def _joint_index_payload(rows: list[list[int]]) -> tuple[bytes, int]:
    """Pack JOINTS_0 using the smallest legal glTF unsigned component width."""
    flat = [int(value) for value in _flatten(rows)]
    if not flat:
        raise ValueError("JOINTS_0 cannot be empty")
    if min(flat) < 0:
        raise ValueError("JOINTS_0 contains a negative joint index")
    maximum = max(flat)
    if maximum <= 255:
        return struct.pack("<" + "B" * len(flat), *flat), UNSIGNED_BYTE
    if maximum <= 65535:
        return struct.pack("<" + "H" * len(flat), *flat), UNSIGNED_SHORT
    raise ValueError("JOINTS_0 exceeds glTF UNSIGNED_SHORT domain")


def maximum_expanded_owner_frame_residual(*, owner_frames: list[dict[str, Any]], packed: PackedRiggedTangentGlb) -> tuple[float, int | None]:
    if len(owner_frames) != KEY_COUNT:
        raise ValueError("exact Animation owner evidence must contain 41 authored frames")
    maximum = 0.0
    worst: int | None = None
    for sample_index, frame in enumerate(owner_frames):
        if frame.get("sample_index") != sample_index:
            raise ValueError("Animation owner sample ordering drift")
        source_positions = frame.get("positions")
        if not isinstance(source_positions, list) or len(source_positions) != SOURCE_VERTEX_COUNT:
            raise ValueError("Animation owner source vertex count drift")
        expected = [[_f32(value) for value in _source_to_uc(source_positions[source_index], "owner render position")] for source_index in packed.render_source_indices]
        predicted = _posed(packed.positions, packed.weights, packed.pivot, _quat(packed.axis, float(frame["angle_deg"])))
        residual = max(math.dist(left, right) for left, right in zip(predicted, expected))
        if residual > maximum:
            maximum, worst = residual, sample_index
    return maximum, worst


def pack_exact_right_forelimb_rigged_tangent_glb(*, spec: dict[str, Any], plan: dict[str, Any], owner_frames: list[dict[str, Any]], geometry_basis: dict[str, Any], source_material: dict[str, Any], clip_name: str) -> PackedRiggedTangentGlb:
    if len(owner_frames) != KEY_COUNT or owner_frames[0].get("time_seconds") != 0.0 or owner_frames[-1].get("time_seconds") != 1.0:
        raise ValueError("owner frames must preserve the exact 41-key 0..1 second contract")
    neutral = owner_frames[0].get("positions")
    if not isinstance(neutral, list) or len(neutral) != SOURCE_VERTEX_COUNT or owner_frames[-1].get("positions") != neutral:
        raise ValueError("owner frames must preserve exact 42-source-vertex neutral closure")
    mapping = _validate_geometry_basis(geometry_basis, neutral)

    joint = _select_right_elbow(plan, spec)
    landmarks = spec.get("landmarks", {})
    pivot_source = _vec3(landmarks[joint["landmark"]], "right elbow")
    child_source = _vec3(landmarks[joint["child_landmark"]], "right wrist")
    source_joints, source_weights = smoothstep_weights(neutral, joint_position=pivot_source, child_marker=child_source, influence_radius=float(joint["influence_radius"]))

    positions = [[_f32(value) for value in _source_to_uc(row, f"render_positions[{index}]")] for index, row in enumerate(geometry_basis["render_positions"])]
    normals = [[_f32(value) for value in source_direction_to_uc(row, f"render_normals[{index}]")] for index, row in enumerate(geometry_basis["render_normals"])]
    tangents = [source_tangent_to_uc(row) for row in geometry_basis["render_tangents"]]
    texcoords = [[_f32(float(u)), _f32(float(v))] for u, v in geometry_basis["render_uvs"]]
    joints = [[int(value) for value in source_joints[source_index]] for source_index in mapping]
    weights = [[_f32(value) for value in source_weights[source_index]] for source_index in mapping]
    indices = _reverse_winding([int(value) for value in geometry_basis["render_indices"]])
    pivot = [_f32(value) for value in _source_to_uc(pivot_source, "right elbow pivot")]
    axis = source_axis_to_uc(joint["axis"])
    times = [_f32(float(frame["time_seconds"])) for frame in owner_frames]
    rotations = [_quat(axis, float(frame["angle_deg"])) for frame in owner_frames]
    if any(times[index] <= times[index - 1] for index in range(1, len(times))):
        raise ValueError("float32 animation times are not strictly increasing")

    chunks: list[bytes] = []
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []

    def view(data: bytes, target: int | None = None) -> int:
        offset = sum(len(chunk) for chunk in chunks)
        row: dict[str, Any] = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            row["target"] = target
        views.append(row)
        chunks.append(_pad4(data))
        return len(views) - 1

    def accessor(data: bytes, component: int, count: int, kind: str, target: int | None = None, minimum=None, maximum=None) -> int:
        row: dict[str, Any] = {"bufferView": view(data, target), "componentType": component, "count": count, "type": kind}
        if minimum is not None:
            row["min"] = minimum
        if maximum is not None:
            row["max"] = maximum
        accessors.append(row)
        return len(accessors) - 1

    def floats(rows: list[Any]) -> bytes:
        flat = [float(value) for value in _flatten(rows)]
        return struct.pack("<" + "f" * len(flat), *flat)

    def ushorts(rows: list[Any]) -> bytes:
        flat = [int(value) for value in _flatten(rows)]
        return struct.pack("<" + "H" * len(flat), *flat)

    pos_min = [min(row[d] for row in positions) for d in range(3)]
    pos_max = [max(row[d] for row in positions) for d in range(3)]
    joint_payload, joint_component = _joint_index_payload(joints)
    a_pos = accessor(floats(positions), 5126, RENDER_VERTEX_COUNT, "VEC3", 34962, pos_min, pos_max)
    a_nrm = accessor(floats(normals), 5126, RENDER_VERTEX_COUNT, "VEC3", 34962)
    a_tan = accessor(floats(tangents), 5126, RENDER_VERTEX_COUNT, "VEC4", 34962)
    a_uv = accessor(floats(texcoords), 5126, RENDER_VERTEX_COUNT, "VEC2", 34962)
    a_jnt = accessor(joint_payload, joint_component, RENDER_VERTEX_COUNT, "VEC4", 34962)
    a_wgt = accessor(floats(weights), 5126, RENDER_VERTEX_COUNT, "VEC4", 34962)
    a_idx = accessor(ushorts(indices), 5123, TRIANGLE_COUNT * 3, "SCALAR", 34963)
    inverse = [_translation_matrix(0, 0, 0), _translation_matrix(-pivot[0], -pivot[1], -pivot[2])]
    a_inv = accessor(floats(inverse), 5126, 2, "MAT4")
    a_time = accessor(floats(times), 5126, KEY_COUNT, "SCALAR", minimum=[times[0]], maximum=[times[-1]])
    a_rot = accessor(floats(rotations), 5126, KEY_COUNT, "VEC4")
    binary = b"".join(chunks)

    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "AXM Animal Technical Art rigged UV/tangent bridge v0.1"},
        "scene": 0,
        "scenes": [{"name": "Animal right forelimb UV tangent transport proof", "nodes": [0, 1]}],
        "nodes": [{"name": "AnimalRightForelimbRenderDomain", "mesh": 0, "skin": 0}, {"name": "transport-parent", "children": [2]}, {"name": JOINT_ID, "translation": pivot}],
        "meshes": [{"name": TRANSPORT_SURFACE_ID, "primitives": [{"attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "TANGENT": a_tan, "TEXCOORD_0": a_uv, "JOINTS_0": a_jnt, "WEIGHTS_0": a_wgt}, "indices": a_idx, "material": 0, "mode": 4}]}],
        "materials": [{"name": "AnimalNeutralTransportMaterial", "pbrMetallicRoughness": {"baseColorFactor": _base_color(source_material), "metallicFactor": float(source_material["metallic"]), "roughnessFactor": float(source_material["roughness"])}, "doubleSided": False, "alphaMode": "OPAQUE"}],
        "skins": [{"name": "AnimalRightForelimbTwoJointRenderDomainSkin", "inverseBindMatrices": a_inv, "skeleton": 1, "joints": [1, 2]}],
        "animations": [{"name": str(clip_name), "samplers": [{"input": a_time, "output": a_rot, "interpolation": "LINEAR"}], "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {"axm": {
            "bridge_schema": BRIDGE_SCHEMA,
            "source_candidate_id": SOURCE_CANDIDATE_ID,
            "geometry_basis_id": GEOMETRY_BASIS_ID,
            "transport_surface_id": TRANSPORT_SURFACE_ID,
            "source_coordinates": SOURCE_COORDINATES,
            "target_coordinates": TARGET_COORDINATES,
            "source_to_uc_component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "triangle_winding_reversed": True,
            "tangent_xyz_transform": "M * source_tangent_xyz",
            "tangent_handedness_transform": "target_w = det(M) * source_w = -source_w",
            "rotation_axis_transform": "det(M) * M * source_axis",
            "source_vertex_count": SOURCE_VERTEX_COUNT,
            "render_vertex_count": RENDER_VERTEX_COUNT,
            "render_vertex_split_preserved": True,
            "weighting": WEIGHTING_ID,
            "authored_key_count": KEY_COUNT,
            "authored_duration_seconds": 1.0,
            "interpolation": "LINEAR",
            "joint_index_component_type": joint_component,
            "joint_index_width_policy": "smallest legal glTF unsigned component from exact emitted JOINTS_0 domain",
            "continuous_owner_curve_equivalence_claimed": False,
            "deformed_tangent_equivalence_claimed": False,
        }},
    }
    json_chunk = _pad4(json.dumps(document, separators=(",", ":")).encode(), b" ")
    bin_chunk = _pad4(binary)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    output = bytearray(total)
    struct.pack_into("<III", output, 0, 0x46546C67, 2, total)
    struct.pack_into("<II", output, 12, len(json_chunk), 0x4E4F534A)
    output[20:20 + len(json_chunk)] = json_chunk
    at = 20 + len(json_chunk)
    struct.pack_into("<II", output, at, len(bin_chunk), 0x004E4942)
    output[at + 8:at + 8 + len(bin_chunk)] = bin_chunk
    return PackedRiggedTangentGlb(bytes(output), document, positions, normals, tangents, texcoords, joints, weights, indices, mapping, pivot, axis, times, rotations)


def decode_first_primitive(glb: bytes) -> dict[str, Any]:
    if len(glb) < 28 or struct.unpack_from("<I", glb, 0)[0] != 0x46546C67:
        raise ValueError("not a glTF binary container")
    json_length, json_type = struct.unpack_from("<II", glb, 12)
    if json_type != 0x4E4F534A:
        raise ValueError("GLB first chunk is not JSON")
    document = json.loads(glb[20:20 + json_length].decode("utf-8").rstrip(" \x00"))
    binary_at = 20 + json_length
    binary_length, binary_type = struct.unpack_from("<II", glb, binary_at)
    if binary_type != 0x004E4942:
        raise ValueError("GLB second chunk is not BIN")
    binary = glb[binary_at + 8:binary_at + 8 + binary_length]
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    formats = {5126: ("f", 4), 5123: ("H", 2), 5121: ("B", 1)}

    def read_accessor(index: int) -> list[Any]:
        accessor_row = document["accessors"][index]
        view_row = document["bufferViews"][accessor_row["bufferView"]]
        fmt, _ = formats[accessor_row["componentType"]]
        width = widths[accessor_row["type"]]
        offset = int(view_row.get("byteOffset", 0)) + int(accessor_row.get("byteOffset", 0))
        count = int(accessor_row["count"])
        values = struct.unpack_from("<" + fmt * (count * width), binary, offset)
        if width == 1:
            return list(values)
        return [list(values[row * width:(row + 1) * width]) for row in range(count)]

    primitive = document["meshes"][0]["primitives"][0]
    decoded = {name: read_accessor(index) for name, index in primitive["attributes"].items()}
    decoded["INDICES"] = read_accessor(primitive["indices"])
    decoded["document"] = document
    return decoded
