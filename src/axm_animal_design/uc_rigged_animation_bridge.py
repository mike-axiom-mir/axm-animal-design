"""Bounded Animal -> UC rigged-animation transport owned by Technical Art.

Animal topology, rigging, weighting and motion stay in their source lanes. This
module only projects one exact right-forelimb proof surface into glTF 2.0 with a
minimal two-joint skin and the already-authored 41 elbow keys, then exposes exact
pose-comparison helpers for cross-repo verification.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from typing import Any

from .uc_bridge import (
    SOURCE_COORDINATES,
    TARGET_COORDINATES,
    _source_to_uc,
    adapt_geometry_candidate_for_uc,
)

BRIDGE_SCHEMA = "axm.animal-uc-rigged-animation-bridge/v0.1"
SOURCE_CANDIDATE_ID = (
    "front-right-connected-chain-elbow-source-successor-003-mirror-surface-topology-001"
)
TRANSPORT_SURFACE_ID = "animal-selected003-right-mirror-rigged"
JOINT_ID = "front-elbow-R"
WEIGHTING_ID = "smoothstep-v0"


@dataclass(frozen=True)
class PackedRiggedGlb:
    bytes: bytes
    document: dict[str, Any]
    weights: list[list[float]]
    joints: list[list[int]]
    uc_positions: list[list[float]]
    uc_normals: list[list[float]]
    uc_indices: list[int]
    uc_pivot: list[float]
    uc_axis: list[float]
    quaternions: list[list[float]]
    times: list[float]


def _f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _vec3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must be [x,y,z]")
    output = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{label}[{index}] must be finite")
        output.append(float(item))
    return output


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [a[i] - b[i] for i in range(3)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(a[i] * b[i] for i in range(3))


def _unit(value: list[float], label: str) -> list[float]:
    size = math.sqrt(_dot(value, value))
    if size <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return [item / size for item in value]


def source_axis_to_uc(axis: Any) -> list[float]:
    """Transform a rotation axis through the Animal -> UC reflection.

    The component map has determinant -1. Rotation axes are axial vectors, so the
    correct map is det(M)*M*axis, not the ordinary direction-vector transform.
    """
    mapped = _source_to_uc(axis, "rotation axis")
    return [round(-item, 9) for item in _unit(mapped, "mapped rotation axis")]


def _select_right_elbow(plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != "axm.animal-rig-deformation-plan/v0.1":
        raise ValueError("rig plan schema mismatch")
    if plan.get("source_name") != spec.get("name"):
        raise ValueError("rig plan/source identity mismatch")
    matches = [row for row in plan.get("joints", []) if isinstance(row, dict) and row.get("id") == JOINT_ID]
    if len(matches) != 1:
        raise ValueError(f"rig plan must contain exactly one {JOINT_ID}")
    joint = matches[0]
    pinned = {
        "landmark": "elbow_R",
        "parent_landmark": "shoulder_R",
        "child_landmark": "wrist_R",
        "parent_region": "front_upper_R",
        "child_region": "front_lower_R",
        "downstream_regions": ["front_paw_R"],
        "axis": [0.0, 1.0, 0.0],
        "influence_radius": 0.11,
    }
    for key, expected in pinned.items():
        if joint.get(key) != expected:
            raise ValueError(f"{JOINT_ID}.{key} drifted from the exact transport prerequisite")
    return joint


def smoothstep_weights(
    source_positions: list[list[float]],
    *,
    joint_position: list[float],
    child_marker: list[float],
    influence_radius: float,
) -> tuple[list[list[int]], list[list[float]]]:
    """Re-express Rigging's existing two-transform smoothstep weights for glTF."""
    direction = _unit(_sub(child_marker, joint_position), "child direction")
    if not math.isfinite(influence_radius) or influence_radius <= 0.0:
        raise ValueError("influence radius must be finite and positive")
    joints: list[list[int]] = []
    weights: list[list[float]] = []
    for index, raw in enumerate(source_positions):
        point = _vec3(raw, f"source_positions[{index}]")
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t * t * (3.0 - 2.0 * t)
        joints.append([0, 1, 0, 0])
        weights.append([1.0 - child, child, 0.0, 0.0])
    return joints, weights


def _quat(axis: list[float], angle_deg: float) -> list[float]:
    direction = _unit(axis, "quaternion axis")
    half = math.radians(float(angle_deg)) / 2.0
    sine = math.sin(half)
    return [_f32(direction[0] * sine), _f32(direction[1] * sine), _f32(direction[2] * sine), _f32(math.cos(half))]


def _quat_rotate(q: list[float], v: list[float]) -> list[float]:
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2.0 * (y * vz - z * vy), 2.0 * (z * vx - x * vz), 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


def _posed(
    positions: list[list[float]],
    weights: list[list[float]],
    pivot: list[float],
    quaternion: list[float],
) -> list[list[float]]:
    output = []
    for position, row in zip(positions, weights):
        parent, child = float(row[0]), float(row[1])
        local = [position[i] - pivot[i] for i in range(3)]
        rotated = _quat_rotate(quaternion, local)
        child_position = [pivot[i] + rotated[i] for i in range(3)]
        output.append([parent * position[i] + child * child_position[i] for i in range(3)])
    return output


def maximum_owner_frame_residual(
    *,
    owner_frames: list[dict[str, Any]],
    uc_positions: list[list[float]],
    weights: list[list[float]],
    uc_pivot: list[float],
    uc_axis: list[float],
) -> tuple[float, int | None]:
    if len(owner_frames) != 41:
        raise ValueError("exact Animation owner evidence must contain 41 authored frames")
    maximum = 0.0
    worst: int | None = None
    for expected_index, frame in enumerate(owner_frames):
        if frame.get("sample_index") != expected_index:
            raise ValueError("Animation owner sample ordering drift")
        source_positions = frame.get("positions")
        if not isinstance(source_positions, list) or len(source_positions) != len(uc_positions):
            raise ValueError("Animation owner frame vertex count drift")
        target = [[_f32(item) for item in _source_to_uc(point, "owner position")] for point in source_positions]
        predicted = _posed(uc_positions, weights, uc_pivot, _quat(uc_axis, float(frame["angle_deg"])))
        residual = max(math.dist(a, b) for a, b in zip(predicted, target))
        if residual > maximum:
            maximum, worst = residual, expected_index
    return maximum, worst


def _flatten(rows: list[Any]) -> list[Any]:
    output: list[Any] = []
    for row in rows:
        output.extend(row if isinstance(row, (list, tuple)) else [row])
    return output


def _pad4(data: bytes, fill: bytes = b"\x00") -> bytes:
    return data + fill * ((-len(data)) % 4)


def _translation_matrix(x: float, y: float, z: float) -> list[float]:
    return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]


def _color(value: str) -> list[float]:
    text = str(value)
    if not text.startswith("#") or len(text) not in (7, 9):
        raise ValueError("transport material color must be #RRGGBB or #RRGGBBAA")
    channels = [int(text[offset:offset + 2], 16) / 255.0 for offset in (1, 3, 5)]
    alpha = int(text[7:9], 16) / 255.0 if len(text) == 9 else 1.0
    return channels + [alpha]


def pack_exact_right_forelimb_glb(
    *,
    spec: dict[str, Any],
    plan: dict[str, Any],
    owner_frames: list[dict[str, Any]],
    indices: list[int],
    source_material: dict[str, Any],
    clip_name: str,
) -> PackedRiggedGlb:
    """Pack the exact 42v/80t right forelimb with two joints and 41 rotation keys."""
    if len(owner_frames) != 41 or owner_frames[0].get("time_seconds") != 0.0 or owner_frames[-1].get("time_seconds") != 1.0:
        raise ValueError("owner frames must preserve the exact 41-key 0..1 second contract")
    neutral = owner_frames[0].get("positions")
    if not isinstance(neutral, list) or len(neutral) != 42 or owner_frames[-1].get("positions") != neutral:
        raise ValueError("owner frames must preserve exact 42-vertex neutral closure")
    if not isinstance(indices, list) or len(indices) != 240 or any(type(i) is not int or not 0 <= i < 42 for i in indices):
        raise ValueError("exact right forelimb must contain 240 valid indices")

    joint = _select_right_elbow(plan, spec)
    landmarks = spec.get("landmarks", {})
    pivot_source = _vec3(landmarks[joint["landmark"]], "right elbow")
    child_source = _vec3(landmarks[joint["child_landmark"]], "right wrist")
    joints, weights = smoothstep_weights(
        neutral,
        joint_position=pivot_source,
        child_marker=child_source,
        influence_radius=float(joint["influence_radius"]),
    )

    portable = adapt_geometry_candidate_for_uc(
        {"id": TRANSPORT_SURFACE_ID, "positions": neutral, "indices": indices},
        name="Animal selected-003 right mirror rigged transport",
        material=source_material,
    )
    primitive = portable["primitives"][0]
    positions = [[_f32(v) for v in row] for row in primitive["positions"]]
    normals = [[_f32(v) for v in row] for row in primitive["normals"]]
    encoded_weights = [[_f32(v) for v in row] for row in weights]
    encoded_joints = [[int(v) for v in row] for row in joints]
    encoded_indices = [int(v) for v in primitive["indices"]]
    pivot = [_f32(v) for v in _source_to_uc(pivot_source, "right elbow pivot")]
    axis = source_axis_to_uc(joint["axis"])
    times = [_f32(float(frame["time_seconds"])) for frame in owner_frames]
    rotations = [_quat(axis, float(frame["angle_deg"])) for frame in owner_frames]
    if any(times[i] <= times[i - 1] for i in range(1, len(times))):
        raise ValueError("float32 animation times are not strictly increasing")

    chunks: list[bytes] = []
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []

    def view(data: bytes, target: int | None = None) -> int:
        offset = sum(len(chunk) for chunk in chunks)
        index = len(views)
        chunks.append(_pad4(data))
        row: dict[str, Any] = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            row["target"] = target
        views.append(row)
        return index

    def accessor(data: bytes, component: int, count: int, kind: str, target: int | None = None, minimum=None, maximum=None) -> int:
        row: dict[str, Any] = {"bufferView": view(data, target), "componentType": component, "count": count, "type": kind}
        if minimum is not None:
            row["min"] = minimum
        if maximum is not None:
            row["max"] = maximum
        accessors.append(row)
        return len(accessors) - 1

    def floats(rows: list[Any]) -> bytes:
        flat = [float(v) for v in _flatten(rows)]
        return struct.pack("<" + "f" * len(flat), *flat)

    def ushorts(rows: list[Any]) -> bytes:
        flat = [int(v) for v in _flatten(rows)]
        return struct.pack("<" + "H" * len(flat), *flat)

    pos_min = [min(row[d] for row in positions) for d in range(3)]
    pos_max = [max(row[d] for row in positions) for d in range(3)]
    a_pos = accessor(floats(positions), 5126, 42, "VEC3", 34962, pos_min, pos_max)
    a_nrm = accessor(floats(normals), 5126, 42, "VEC3", 34962)
    a_jnt = accessor(ushorts(encoded_joints), 5123, 42, "VEC4", 34962)
    a_wgt = accessor(floats(encoded_weights), 5126, 42, "VEC4", 34962)
    a_idx = accessor(ushorts(encoded_indices), 5123, 240, "SCALAR", 34963)
    inverse = [_translation_matrix(0, 0, 0), _translation_matrix(-pivot[0], -pivot[1], -pivot[2])]
    a_inv = accessor(floats(inverse), 5126, 2, "MAT4")
    a_time = accessor(floats(times), 5126, 41, "SCALAR", minimum=[times[0]], maximum=[times[-1]])
    a_rot = accessor(floats(rotations), 5126, 41, "VEC4")

    binary = b"".join(chunks)
    material = primitive["material"]
    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "AXM Animal Technical Art rigged bridge v0.1"},
        "scene": 0,
        "scenes": [{"name": "Animal right forelimb transport proof", "nodes": [0, 1]}],
        "nodes": [
            {"name": "AnimalRightForelimb", "mesh": 0, "skin": 0},
            {"name": "transport-parent", "children": [2]},
            {"name": JOINT_ID, "translation": pivot},
        ],
        "meshes": [{"name": TRANSPORT_SURFACE_ID, "primitives": [{
            "attributes": {"POSITION": a_pos, "NORMAL": a_nrm, "JOINTS_0": a_jnt, "WEIGHTS_0": a_wgt},
            "indices": a_idx, "material": 0, "mode": 4,
        }]}],
        "materials": [{"name": "AnimalNeutralTransportMaterial", "pbrMetallicRoughness": {
            "baseColorFactor": _color(material["color"]),
            "metallicFactor": float(material["metallic"]),
            "roughnessFactor": float(material["roughness"]),
        }, "doubleSided": False, "alphaMode": "OPAQUE"}],
        "skins": [{"name": "AnimalRightForelimbTwoJointTransportSkin", "inverseBindMatrices": a_inv, "skeleton": 1, "joints": [1, 2]}],
        "animations": [{"name": str(clip_name), "samplers": [{"input": a_time, "output": a_rot, "interpolation": "LINEAR"}], "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {"axm": {
            "bridge_schema": BRIDGE_SCHEMA,
            "source_candidate_id": SOURCE_CANDIDATE_ID,
            "transport_surface_id": TRANSPORT_SURFACE_ID,
            "source_coordinates": SOURCE_COORDINATES,
            "target_coordinates": TARGET_COORDINATES,
            "source_to_uc_component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "rotation_axis_transform": "det(M) * M * source_axis",
            "triangle_winding_reversed": True,
            "weighting": WEIGHTING_ID,
            "transport_only_normals": True,
            "authored_key_count": 41,
            "authored_duration_seconds": 1.0,
            "interpolation": "LINEAR",
            "continuous_owner_curve_equivalence_claimed": False,
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
    return PackedRiggedGlb(bytes(output), document, encoded_weights, encoded_joints, positions, normals, encoded_indices, pivot, axis, rotations, times)


def mutated_weight_residual(*, owner_frames: list[dict[str, Any]], packed: PackedRiggedGlb) -> float:
    """Deliberate receiver-side weight drift negative control."""
    changed = []
    for row in packed.weights:
        child = min(1.0, float(row[1]) + 0.05 * (1.0 - float(row[1])))
        changed.append([_f32(1.0 - child), _f32(child), 0.0, 0.0])
    residual, _ = maximum_owner_frame_residual(
        owner_frames=owner_frames,
        uc_positions=packed.uc_positions,
        weights=changed,
        uc_pivot=packed.uc_pivot,
        uc_axis=packed.uc_axis,
    )
    return residual
