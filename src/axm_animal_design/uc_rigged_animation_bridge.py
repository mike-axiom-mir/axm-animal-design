"""Animal-local Technical Art bridge for one exact skinned animation transport.

This module deliberately does not define Animal topology, rigging, weighting, motion,
or visual policy.  It accepts evidence already owned by Geometry/Rigging/Animation,
projects the exact right forelimb into the existing UC/glTF coordinate convention,
and emits a minimal glTF 2.0 skin + rotation-channel GLB for cross-repo validation.

The current bounded contract is intentionally one deforming surface and two joints:
an identity parent plus the existing front-elbow-R child.  It proves transport of the
already-authored 41 keys; it is not a generic Animal rig exporter and does not claim
continuous interpolation, target-engine playback, visual quality, or production use.
"""
from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from typing import Any

from .uc_bridge import SOURCE_COORDINATES, TARGET_COORDINATES, _source_to_uc, adapt_geometry_candidate_for_uc

GLTF_COMPONENT_FLOAT = 5126
GLTF_COMPONENT_UNSIGNED_SHORT = 5123
GLTF_ARRAY_BUFFER = 34962
GLTF_ELEMENT_ARRAY_BUFFER = 34963
GLTF_TRIANGLES = 4

BRIDGE_SCHEMA = "axm.animal-uc-rigged-animation-bridge/v0.1"
SOURCE_CANDIDATE_ID = "front-right-connected-chain-elbow-source-successor-003-mirror-surface-topology-001"
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


def _finite_vec3(value: Any, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{label} must contain exactly three values")
    output = []
    for index, item in enumerate(value):
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ValueError(f"{label}[{index}] must be finite")
        output.append(float(item))
    return output


def _sub(a: list[float], b: list[float]) -> list[float]:
    return [a[index] - b[index] for index in range(3)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(a[index] * b[index] for index in range(3))


def _length(value: list[float]) -> float:
    return math.sqrt(_dot(value, value))


def _unit(value: list[float], label: str) -> list[float]:
    length = _length(value)
    if length <= 1e-12:
        raise ValueError(f"{label} must have non-zero length")
    return [component / length for component in value]


def source_axis_to_uc(axis: Any) -> list[float]:
    """Transform a source-space *axial* vector through the handedness flip.

    Animal -> UC uses an orthogonal transform with determinant -1.  Rotation axes
    are pseudovectors, so they transform as det(M) * M * axis rather than as an
    ordinary direction vector.  This distinction is required to preserve positive
    rotation under the reflected basis.
    """
    mapped = _source_to_uc(axis, "rotation axis")
    return [round(-component, 9) for component in _unit(mapped, "mapped rotation axis")]


def _select_exact_right_elbow(plan: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict) or plan.get("schema") != "axm.animal-rig-deformation-plan/v0.1":
        raise ValueError("rig plan schema mismatch")
    if plan.get("source_name") != spec.get("name"):
        raise ValueError("rig plan/source identity mismatch")
    matches = [row for row in plan.get("joints", []) if isinstance(row, dict) and row.get("id") == JOINT_ID]
    if len(matches) != 1:
        raise ValueError(f"rig plan must contain exactly one {JOINT_ID}")
    joint = matches[0]
    expected = {
        "landmark": "elbow_R",
        "parent_landmark": "shoulder_R",
        "child_landmark": "wrist_R",
        "parent_region": "front_upper_R",
        "child_region": "front_lower_R",
        "downstream_regions": ["front_paw_R"],
        "axis": [0.0, 1.0, 0.0],
        "influence_radius": 0.11,
    }
    for key, value in expected.items():
        if joint.get(key) != value:
            raise ValueError(f"{JOINT_ID}.{key} drifted from the exact transport prerequisite")
    return joint


def smoothstep_weights(
    source_positions: list[list[float]],
    *,
    joint_position: list[float],
    child_marker: list[float],
    influence_radius: float,
) -> tuple[list[list[int]], list[list[float]]]:
    """Re-express the exact established two-transform smoothstep weights for glTF."""
    direction = _unit(_sub(child_marker, joint_position), "child direction")
    if influence_radius <= 0.0 or not math.isfinite(influence_radius):
        raise ValueError("influence radius must be finite and positive")
    joints: list[list[int]] = []
    weights: list[list[float]] = []
    for index, raw in enumerate(source_positions):
        point = _finite_vec3(raw, f"source_positions[{index}]")
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t * t * (3.0 - 2.0 * t)
        parent = 1.0 - child
        joints.append([0, 1, 0, 0])
        weights.append([parent, child, 0.0, 0.0])
    return joints, weights


def _quat_axis_angle(axis: list[float], angle_deg: float) -> list[float]:
    direction = _unit(axis, "quaternion axis")
    half = math.radians(float(angle_deg)) * 0.5
    sine = math.sin(half)
    quat = [direction[0] * sine, direction[1] * sine, direction[2] * sine, math.cos(half)]
    return [_f32(value) for value in quat]


def _quat_rotate(quaternion: list[float], vector: list[float]) -> list[float]:
    x, y, z, w = quaternion
    vx, vy, vz = vector
    # q * v * q^-1, expanded without allocating quaternion objects.
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    return [
        vx + w * tx + (y * tz - z * ty),
        vy + w * ty + (z * tx - x * tz),
        vz + w * tz + (x * ty - y * tx),
    ]


def _predict_skinned_positions(
    positions: list[list[float]],
    weights: list[list[float]],
    *,
    pivot: list[float],
    quaternion: list[float],
) -> list[list[float]]:
    predicted = []
    for position, row in zip(positions, weights):
        parent, child = float(row[0]), float(row[1])
        local = [position[axis] - pivot[axis] for axis in range(3)]
        rotated = _quat_rotate(quaternion, local)
        child_position = [pivot[axis] + rotated[axis] for axis in range(3)]
        predicted.append([
            parent * position[axis] + child * child_position[axis]
            for axis in range(3)
        ])
    return predicted


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
        target = [
            [_f32(value) for value in _source_to_uc(point, f"owner frame {expected_index} position")]
            for point in source_positions
        ]
        quaternion = _quat_axis_angle(uc_axis, float(frame.get("angle_deg")))
        predicted = _predict_skinned_positions(
            uc_positions,
            weights,
            pivot=uc_pivot,
            quaternion=quaternion,
        )
        residual = max(math.dist(a, b) for a, b in zip(predicted, target))
        if residual > maximum:
            maximum = residual
            worst = expected_index
    return maximum, worst


def _pack_array(values: list[Any], fmt: str) -> bytes:
    flat: list[Any] = []
    for row in values:
        if isinstance(row, (list, tuple)):
            flat.extend(row)
        else:
            flat.append(row)
    return struct.pack("<" + fmt * len(flat), *flat)


def _pad4(data: bytes, fill: bytes = b"\x00") -> bytes:
    padding = (-len(data)) % 4
    return data + fill * padding


def _matrix_translation(x: float, y: float, z: float) -> list[float]:
    # Column-major glTF matrix.
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        x, y, z, 1.0,
    ]


def _hex_to_rgba(value: str) -> list[float]:
    text = str(value)
    if len(text) != 7 or not text.startswith("#"):
        raise ValueError("transport material color must be #RRGGBB")
    return [int(text[offset:offset + 2], 16) / 255.0 for offset in (1, 3, 5)] + [1.0]


def pack_exact_right_forelimb_glb(
    *,
    spec: dict[str, Any],
    plan: dict[str, Any],
    owner_frames: list[dict[str, Any]],
    indices: list[int],
    source_material: dict[str, Any],
    clip_name: str,
) -> PackedRiggedGlb:
    """Pack one exact right forelimb into a two-joint glTF skin + 41 rotation keys."""
    if not isinstance(owner_frames, list) or len(owner_frames) != 41:
        raise ValueError("owner_frames must contain the exact 41 endpoint-inclusive samples")
    if owner_frames[0].get("time_seconds") != 0.0 or owner_frames[-1].get("time_seconds") != 1.0:
        raise ValueError("owner_frames must preserve exact 0.0..1.0 second endpoints")
    neutral_positions = owner_frames[0].get("positions")
    if not isinstance(neutral_positions, list) or len(neutral_positions) != 42:
        raise ValueError("exact right forelimb neutral frame must contain 42 vertices")
    if owner_frames[-1].get("positions") != neutral_positions:
        raise ValueError("Animation owner evidence lost exact neutral endpoint closure")
    if not isinstance(indices, list) or len(indices) != 240:
        raise ValueError("exact right forelimb must contain 240 triangle indices")
    if any(type(index) is not int or not 0 <= index < 42 for index in indices):
        raise ValueError("right forelimb indices contain an invalid vertex reference")

    joint = _select_exact_right_elbow(plan, spec)
    landmark_map = spec.get("landmarks")
    if not isinstance(landmark_map, dict):
        raise ValueError("source landmarks are required")
    source_pivot = _finite_vec3(landmark_map[joint["landmark"]], "right elbow landmark")
    source_child = _finite_vec3(landmark_map[joint["child_landmark"]], "right wrist landmark")
    joints, weights = smoothstep_weights(
        neutral_positions,
        joint_position=source_pivot,
        child_marker=source_child,
        influence_radius=float(joint["influence_radius"]),
    )

    candidate = {
        "id": TRANSPORT_SURFACE_ID,
        "positions": neutral_positions,
        "indices": [int(value) for value in indices],
    }
    uc_surface = adapt_geometry_candidate_for_uc(
        candidate,
        name="Animal selected-003 right mirror rigged transport",
        material=source_material,
    )
    primitive = uc_surface["primitives"][0]
    uc_positions = [[_f32(value) for value in row] for row in primitive["positions"]]
    uc_normals = [[_f32(value) for value in row] for row in primitive["normals"]]
    uc_indices = [int(value) for value in primitive["indices"]]
    uc_pivot = [_f32(value) for value in _source_to_uc(source_pivot, "right elbow pivot")]
    uc_axis = source_axis_to_uc(joint["axis"])
    times = [_f32(float(frame["time_seconds"])) for frame in owner_frames]
    quaternions = [_quat_axis_angle(uc_axis, float(frame["angle_deg"])) for frame in owner_frames]

    if any(not times[index] > times[index - 1] for index in range(1, len(times))):
        raise ValueError("authored animation times are not strictly increasing after float32 projection")

    # Re-project weights to the actual encoded float32 payload before evidence comparison.
    encoded_weights = [[_f32(value) for value in row] for row in weights]
    encoded_joints = [[int(value) for value in row] for row in joints]

    chunks: list[bytes] = []
    views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []

    def add_view(data: bytes, target: int | None = None) -> int:
        offset = sum(len(chunk) for chunk in chunks)
        padded = _pad4(data)
        index = len(views)
        chunks.append(padded)
        view: dict[str, Any] = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target is not None:
            view["target"] = target
        views.append(view)
        return index

    def add_accessor(
        data: bytes,
        *,
        component_type: int,
        count: int,
        kind: str,
        target: int | None = None,
        minimum: list[float] | None = None,
        maximum: list[float] | None = None,
    ) -> int:
        view_index = add_view(data, target)
        accessor: dict[str, Any] = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": count,
            "type": kind,
        }
        if minimum is not None:
            accessor["min"] = minimum
        if maximum is not None:
            accessor["max"] = maximum
        accessors.append(accessor)
        return len(accessors) - 1

    mins = [min(row[axis] for row in uc_positions) for axis in range(3)]
    maxs = [max(row[axis] for row in uc_positions) for axis in range(3)]
    pos_accessor = add_accessor(
        _pack_array(uc_positions, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=42, kind="VEC3", target=GLTF_ARRAY_BUFFER, minimum=mins, maximum=maxs,
    )
    normal_accessor = add_accessor(
        _pack_array(uc_normals, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=42, kind="VEC3", target=GLTF_ARRAY_BUFFER,
    )
    joint_accessor = add_accessor(
        _pack_array(encoded_joints, "H"), component_type=GLTF_COMPONENT_UNSIGNED_SHORT,
        count=42, kind="VEC4", target=GLTF_ARRAY_BUFFER,
    )
    weight_accessor = add_accessor(
        _pack_array(encoded_weights, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=42, kind="VEC4", target=GLTF_ARRAY_BUFFER,
    )
    index_accessor = add_accessor(
        _pack_array(uc_indices, "H"), component_type=GLTF_COMPONENT_UNSIGNED_SHORT,
        count=len(uc_indices), kind="SCALAR", target=GLTF_ELEMENT_ARRAY_BUFFER,
    )
    inverse_bind = [
        _matrix_translation(0.0, 0.0, 0.0),
        _matrix_translation(-uc_pivot[0], -uc_pivot[1], -uc_pivot[2]),
    ]
    inverse_accessor = add_accessor(
        _pack_array(inverse_bind, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=2, kind="MAT4",
    )
    time_accessor = add_accessor(
        _pack_array(times, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=len(times), kind="SCALAR", minimum=[times[0]], maximum=[times[-1]],
    )
    rotation_accessor = add_accessor(
        _pack_array(quaternions, "f"), component_type=GLTF_COMPONENT_FLOAT,
        count=len(quaternions), kind="VEC4",
    )

    binary = b"".join(chunks)
    material = primitive["material"]
    document: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": "AXM Animal Technical Art bounded rigged bridge v0.1"},
        "scene": 0,
        "scenes": [{"name": "Animal right forelimb transport proof", "nodes": [0, 1]}],
        "nodes": [
            {"name": "AnimalRightForelimb", "mesh": 0, "skin": 0},
            {"name": "transport-parent", "children": [2]},
            {"name": JOINT_ID, "translation": uc_pivot},
        ],
        "meshes": [{
            "name": TRANSPORT_SURFACE_ID,
            "primitives": [{
                "attributes": {
                    "POSITION": pos_accessor,
                    "NORMAL": normal_accessor,
                    "JOINTS_0": joint_accessor,
                    "WEIGHTS_0": weight_accessor,
                },
                "indices": index_accessor,
                "material": 0,
                "mode": GLTF_TRIANGLES,
            }],
        }],
        "materials": [{
            "name": "AnimalNeutralTransportMaterial",
            "pbrMetallicRoughness": {
                "baseColorFactor": _hex_to_rgba(material["color"]),
                "metallicFactor": float(material["metallic"]),
                "roughnessFactor": float(material["roughness"]),
            },
            "doubleSided": False,
            "alphaMode": "OPAQUE",
        }],
        "skins": [{
            "name": "AnimalRightForelimbTwoJointTransportSkin",
            "inverseBindMatrices": inverse_accessor,
            "skeleton": 1,
            "joints": [1, 2],
        }],
        "animations": [{
            "name": str(clip_name),
            "samplers": [{
                "input": time_accessor,
                "output": rotation_accessor,
                "interpolation": "LINEAR",
            }],
            "channels": [{"sampler": 0, "target": {"node": 2, "path": "rotation"}}],
        }],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
        "extras": {
            "axm": {
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
            },
        },
    }

    json_payload = json.dumps(document, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_chunk = _pad4(json_payload, b" ")
    bin_chunk = _pad4(binary, b"\x00")
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    output = bytearray(total)
    struct.pack_into("<III", output, 0, 0x46546C67, 2, total)
    struct.pack_into("<II", output, 12, len(json_chunk), 0x4E4F534A)
    output[20:20 + len(json_chunk)] = json_chunk
    bin_offset = 20 + len(json_chunk)
    struct.pack_into("<II", output, bin_offset, len(bin_chunk), 0x004E4942)
    output[bin_offset + 8:bin_offset + 8 + len(bin_chunk)] = bin_chunk

    return PackedRiggedGlb(
        bytes=bytes(output),
        document=document,
        weights=encoded_weights,
        joints=encoded_joints,
        uc_positions=uc_positions,
        uc_normals=uc_normals,
        uc_indices=uc_indices,
        uc_pivot=uc_pivot,
        uc_axis=uc_axis,
        quaternions=quaternions,
        times=times,
    )


def mutated_weight_residual(
    *,
    owner_frames: list[dict[str, Any]],
    packed: PackedRiggedGlb,
) -> float:
    """Return residual from a deliberate receiver-side weight drift negative control."""
    mutated = []
    for row in packed.weights:
        child = min(1.0, float(row[1]) + 0.05 * (1.0 - float(row[1])))
        mutated.append([_f32(1.0 - child), _f32(child), 0.0, 0.0])
    residual, _ = maximum_owner_frame_residual(
        owner_frames=owner_frames,
        uc_positions=packed.uc_positions,
        weights=mutated,
        uc_pivot=packed.uc_pivot,
        uc_axis=packed.uc_axis,
    )
    return residual
