"""Rigging-owned audit of Technical-Art transported tangent deformation.

This module does not author a rig, weighting rule, animation, UV, normal/tangent
policy, GLB codec, engine controller, or runtime path. It consumes the exact
existing Animal elbow rig and Geometry tangent basis, plus the exact retained
Technical-Art GLB, and asks one bounded deformation question:

Do the GLB's static skin attributes, after the exact authored joint rotations are
applied, reproduce Rigging's geometry-derived deformed position/normal/tangent
frames at the same 41 authored keys?

A position PASS is kept separate from direction-frame equivalence. A small
post-skin Gram-Schmidt tangent correction is measured as a constraint witness,
not silently promoted into Technical Art or Runtime implementation.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

from .bilateral_deformed_tangent_frames import (
    PASS_STATE as DEFORMED_TANGENT_PASS_STATE,
    _derive_posed_tangent_frame,
    inspect_bilateral_deformed_tangent_frames,
)
from .bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from .bilateral_source_successor_rigging_rebind import (
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _pose_metrics,
    _select_joint,
    _source_triangle_areas,
)
from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .bilateral_uv_tangent_basis import derive_uv_tangent_basis
from .connected_deformation import BASELINE_WEIGHTING, _sub, _vec3, _weights, digest

EVIDENCE_SCHEMA = "axm.animal-transported-tangent-deformation-audit/v0.1"
PASS_STATE = "PASS_TRANSPORTED_SKINNED_TANGENT_FRAME_EQUIVALENCE"
HOLD_STATE = "PASS_TRANSPORTED_SKINNED_POSITION_EQUIVALENCE__HOLD_DEFORMED_NORMAL_TANGENT_EQUIVALENCE"
FAIL_STATE = "FAIL_TRANSPORTED_SKINNED_DEFORMATION_EQUIVALENCE"
TECHNICAL_ART_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
TECHNICAL_ART_ARTIFACT_ID = 10474385703
TECHNICAL_ART_ARTIFACT_SHA256 = "7fc2a7f5d745da593e8762efa98e13661f84a057b1eb60921d576c366e71d7bb"
TECHNICAL_ART_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
TECHNICAL_ART_MODULE_BLOB = "90343f493389446f06d58202cb7465c98307458f"
TECHNICAL_ART_STATUS = "PASS_ANIMAL_GEOMETRY_UV_TANGENT_RENDER_DOMAIN_WITH_SKIN_KEYS_TO_CURRENT_UC_CODEC"
GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
POSITION_TOLERANCE_M = 1e-6
UV_TOLERANCE = 1e-7
DIRECTION_EXCESS_TOLERANCE_DEG = 1e-6
ORTHOGONALITY_TOLERANCE = 1e-9
KEY_COUNT = 41
RENDER_VERTEX_COUNT = 84
TRIANGLE_COUNT = 80

_COMPONENT_FORMAT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_TYPE_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _dot(a, b) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _length(value) -> float:
    return math.sqrt(_dot(value, value))


def _unit(value, label: str):
    length = _length(value)
    if length <= 1e-15:
        raise ValueError(f"{label} has zero length")
    return [float(component) / length for component in value]


def _distance(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _angle_deg(a, b) -> float:
    left = _unit(a, "left direction")
    right = _unit(b, "right direction")
    return math.degrees(math.atan2(_length(_cross(left, right)), _dot(left, right)))


def _quat_unit(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("rotation quaternion must contain four values")
    return _unit(value, "rotation quaternion")


def _quat_rotate(vector, quaternion):
    x, y, z, w = _quat_unit(quaternion)
    qv = (x, y, z)
    v = tuple(float(component) for component in vector)
    uv = _cross(qv, v)
    uuv = _cross(qv, uv)
    return [
        v[index] + 2.0 * (w * uv[index] + uuv[index])
        for index in range(3)
    ]


def _quat_angle_deg(quaternion) -> float:
    x, y, z, w = _quat_unit(quaternion)
    angle = math.degrees(2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), w))
    if angle > 180.0:
        angle = 360.0 - angle
    return angle


def _source_position_to_target(value):
    x, y, z = (float(component) for component in value)
    return [-y, z, x]


def _source_direction_to_target(value):
    return _unit(_source_position_to_target(value), "mapped source direction")


def _source_tangent_to_target(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("source tangent must contain XYZ+W")
    xyz = _source_direction_to_target(value[:3])
    w = float(value[3])
    if abs(abs(w) - 1.0) > 1e-9:
        raise ValueError("source tangent handedness drift")
    return xyz + [-w]


def _decode_glb(glb: bytes) -> dict[str, Any]:
    if hashlib.sha256(glb).hexdigest() != TECHNICAL_ART_GLB_SHA256:
        raise ValueError("Technical Art GLB SHA-256 drift")
    if len(glb) < 20:
        raise ValueError("GLB is truncated")
    magic, version, declared_length = struct.unpack_from("<4sII", glb, 0)
    if magic != b"glTF" or version != 2 or declared_length != len(glb):
        raise ValueError("GLB header drift")
    offset = 12
    document = None
    binary = None
    while offset + 8 <= len(glb):
        chunk_length, chunk_type = struct.unpack_from("<I4s", glb, offset)
        offset += 8
        payload = glb[offset:offset + chunk_length]
        offset += chunk_length
        if chunk_type == b"JSON":
            document = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif chunk_type in (b"BIN\x00", b"BIN "):
            binary = payload
    if not isinstance(document, dict) or binary is None:
        raise ValueError("GLB must contain JSON and BIN chunks")

    def accessor(index: int):
        row = document["accessors"][index]
        view = document["bufferViews"][row["bufferView"]]
        component_type = int(row["componentType"])
        if component_type not in _COMPONENT_FORMAT or row["type"] not in _TYPE_WIDTH:
            raise ValueError("unsupported GLB accessor type")
        fmt, component_size = _COMPONENT_FORMAT[component_type]
        width = _TYPE_WIDTH[row["type"]]
        packed_size = width * component_size
        stride = int(view.get("byteStride", packed_size))
        base = int(view.get("byteOffset", 0)) + int(row.get("byteOffset", 0))
        output = []
        for item_index in range(int(row["count"])):
            values = struct.unpack_from("<" + fmt * width, binary, base + item_index * stride)
            if width == 1:
                output.append(values[0])
            else:
                output.append(list(values))
        return output

    meshes = document.get("meshes", [])
    if len(meshes) != 1 or len(meshes[0].get("primitives", [])) != 1:
        raise ValueError("expected exactly one transported GLB primitive")
    primitive = meshes[0]["primitives"][0]
    attrs = primitive.get("attributes", {})
    required = {"POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"}
    if set(attrs) != required:
        raise ValueError("Technical Art GLB attribute set drift")
    decoded = {name: accessor(int(attrs[name])) for name in required}
    decoded["INDICES"] = accessor(int(primitive["indices"]))

    animations = document.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected exactly one transported animation channel")
    channel = animations[0]["channels"][0]
    sampler = animations[0]["samplers"][int(channel["sampler"])]
    if channel.get("target", {}).get("path") != "rotation":
        raise ValueError("transported animation target path drift")
    decoded["TIMES"] = accessor(int(sampler["input"]))
    decoded["ROTATIONS"] = accessor(int(sampler["output"]))
    decoded["ANIMATED_NODE"] = int(channel["target"]["node"])
    decoded["document"] = document
    return decoded


def _validate_transport_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("status") != TECHNICAL_ART_STATUS:
        raise ValueError("Technical Art retained status drift")
    if receipt.get("technical_art_head") != TECHNICAL_ART_HEAD:
        raise ValueError("Technical Art exact-head drift")
    owners = receipt.get("owners", {})
    if owners.get("geometry", {}).get("head") != GEOMETRY_HEAD:
        raise ValueError("Technical Art Geometry owner head drift")
    rigging = owners.get("rigging", {})
    if rigging.get("rig_plan_sha256") != RIG_PLAN_DIGEST or rigging.get("weighting") != BASELINE_WEIGHTING:
        raise ValueError("Technical Art rig/weight identity drift")
    transport = receipt.get("transport", {})
    if transport.get("glb_sha256") != TECHNICAL_ART_GLB_SHA256:
        raise ValueError("Technical Art retained GLB identity drift")
    if transport.get("render_vertices") != RENDER_VERTEX_COUNT or transport.get("triangles") != TRIANGLE_COUNT:
        raise ValueError("Technical Art render-domain count drift")
    if transport.get("authored_keys") != KEY_COUNT:
        raise ValueError("Technical Art authored-key count drift")


def _skin_position(position, pivot, quaternion, child_weight: float):
    rotated = _quat_rotate([float(position[i]) - float(pivot[i]) for i in range(3)], quaternion)
    child = [rotated[i] + float(pivot[i]) for i in range(3)]
    weight = float(child_weight)
    return [(1.0 - weight) * float(position[i]) + weight * child[i] for i in range(3)]


def _skin_direction(direction, quaternion, child_weight: float):
    rotated = _quat_rotate(direction, quaternion)
    weight = float(child_weight)
    return _unit(
        [(1.0 - weight) * float(direction[i]) + weight * rotated[i] for i in range(3)],
        "skinned direction",
    )


def _orthonormalize_tangent(tangent, normal):
    n = _unit(normal, "skinned normal")
    projected = [float(tangent[i]) - n[i] * _dot(n, tangent) for i in range(3)]
    return _unit(projected, "post-skin tangent")


def inspect_transported_tangent_deformation(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
    weighting_profile: dict[str, Any],
    transport_receipt: dict[str, Any],
    glb: bytes,
) -> dict[str, Any]:
    """Compare exact transported skin deformation against Rigging owner frames."""
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")
    prerequisite = inspect_bilateral_deformed_tangent_frames(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if prerequisite.get("state") != DEFORMED_TANGENT_PASS_STATE:
        raise ValueError("Rigging deformed-tangent prerequisite is not PASS")
    _validate_transport_receipt(transport_receipt)
    decoded = _decode_glb(glb)

    if len(decoded["POSITION"]) != RENDER_VERTEX_COUNT or len(decoded["INDICES"]) != TRIANGLE_COUNT * 3:
        raise ValueError("decoded GLB render-domain counts drift")
    if len(decoded["ROTATIONS"]) != KEY_COUNT or len(decoded["TIMES"]) != KEY_COUNT:
        raise ValueError("decoded GLB key count drift")

    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    if list(static_basis["render_indices"]) != [int(value) for value in decoded["INDICES"]][::1]:
        # Technical Art reverses winding across the determinant -1 coordinate boundary.
        expected = []
        source_indices = [int(value) for value in static_basis["render_indices"]]
        for offset in range(0, len(source_indices), 3):
            a, b, c = source_indices[offset:offset + 3]
            expected.extend((a, c, b))
        if expected != [int(value) for value in decoded["INDICES"]]:
            raise ValueError("transported render-index identity drift")

    joint = _select_joint(spec, plan, "right")
    source_positions = [tuple(float(value) for value in point) for point in right_candidate["positions"]]
    source_indices = [int(value) for value in right_candidate["indices"]]
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    source_weights = _weights(source_positions, joint_position, child_direction, float(joint["influence_radius"]))
    source_areas = _source_triangle_areas(source_positions, source_indices)

    document = decoded["document"]
    animated_node = decoded["ANIMATED_NODE"]
    nodes = document.get("nodes", [])
    if not 0 <= animated_node < len(nodes):
        raise ValueError("animated node index drift")
    pivot = nodes[animated_node].get("translation")
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise ValueError("transported child joint pivot missing")

    child_weights = []
    for joints, weights in zip(decoded["JOINTS_0"], decoded["WEIGHTS_0"]):
        if len(joints) != 4 or len(weights) != 4:
            raise ValueError("transported skin rows must be VEC4")
        if abs(sum(float(value) for value in weights) - 1.0) > 1e-6:
            raise ValueError("transported skin weight sum drift")
        child = sum(float(weight) for joint_id, weight in zip(joints, weights) if int(joint_id) == 1)
        other = sum(float(weight) for joint_id, weight in zip(joints, weights) if int(joint_id) not in (0, 1))
        if abs(other) > 1e-8:
            raise ValueError("transported GLB introduced an unexpected joint")
        child_weights.append(child)

    rows = []
    maximum_position_residual_m = 0.0
    maximum_uv_residual = 0.0
    maximum_normal_vector_residual = 0.0
    maximum_normal_angle_deg = 0.0
    maximum_raw_tangent_vector_residual = 0.0
    maximum_raw_tangent_angle_deg = 0.0
    maximum_corrected_tangent_vector_residual = 0.0
    maximum_corrected_tangent_angle_deg = 0.0
    maximum_raw_normal_tangent_dot_abs = 0.0
    maximum_corrected_normal_tangent_dot_abs = 0.0
    tangent_handedness_mismatch_count = 0
    neutral_normal_angle_deg = 0.0
    neutral_corrected_tangent_angle_deg = 0.0

    for sample_index, (time_value, quaternion) in enumerate(zip(decoded["TIMES"], decoded["ROTATIONS"])):
        angle_deg = _quat_angle_deg(quaternion)
        pose = _pose_metrics(
            source_positions,
            source_indices,
            source_areas,
            source_weights,
            joint_position,
            _vec3(joint["axis"], "joint axis"),
            angle_deg,
        )
        if pose.get("status") != "PASS":
            raise ValueError(f"Rigging source pose is not PASS at transported key {sample_index}")
        owner = _derive_posed_tangent_frame(right_candidate, static_basis, pose["positions"])

        sample = {
            "sample_index": sample_index,
            "time_seconds": float(time_value),
            "angle_deg_from_transport_quaternion": angle_deg,
            "maximum_position_residual_m": 0.0,
            "maximum_normal_angle_deg": 0.0,
            "maximum_raw_tangent_angle_deg": 0.0,
            "maximum_corrected_tangent_angle_deg": 0.0,
            "maximum_raw_normal_tangent_dot_abs": 0.0,
            "maximum_corrected_normal_tangent_dot_abs": 0.0,
        }
        for render_index in range(RENDER_VERTEX_COUNT):
            expected_position = _source_position_to_target(owner["render_positions"][render_index])
            expected_normal = _source_direction_to_target(owner["render_normals"][render_index])
            expected_tangent = _source_tangent_to_target(owner["render_tangents"][render_index])
            expected_uv = [float(value) for value in owner["render_uvs"][render_index]]

            child_weight = child_weights[render_index]
            transported_position = _skin_position(decoded["POSITION"][render_index], pivot, quaternion, child_weight)
            transported_normal = _skin_direction(decoded["NORMAL"][render_index], quaternion, child_weight)
            raw_tangent = _skin_direction(decoded["TANGENT"][render_index][:3], quaternion, child_weight)
            corrected_tangent = _orthonormalize_tangent(raw_tangent, transported_normal)

            position_residual = _distance(transported_position, expected_position)
            normal_vector_residual = _distance(transported_normal, expected_normal)
            normal_angle = _angle_deg(transported_normal, expected_normal)
            raw_tangent_vector_residual = _distance(raw_tangent, expected_tangent[:3])
            raw_tangent_angle = _angle_deg(raw_tangent, expected_tangent[:3])
            corrected_tangent_vector_residual = _distance(corrected_tangent, expected_tangent[:3])
            corrected_tangent_angle = _angle_deg(corrected_tangent, expected_tangent[:3])
            raw_dot = abs(_dot(transported_normal, raw_tangent))
            corrected_dot = abs(_dot(transported_normal, corrected_tangent))
            uv_residual = _distance(decoded["TEXCOORD_0"][render_index], expected_uv)

            if float(decoded["TANGENT"][render_index][3]) != float(expected_tangent[3]):
                tangent_handedness_mismatch_count += 1

            maximum_position_residual_m = max(maximum_position_residual_m, position_residual)
            maximum_uv_residual = max(maximum_uv_residual, uv_residual)
            maximum_normal_vector_residual = max(maximum_normal_vector_residual, normal_vector_residual)
            maximum_normal_angle_deg = max(maximum_normal_angle_deg, normal_angle)
            maximum_raw_tangent_vector_residual = max(maximum_raw_tangent_vector_residual, raw_tangent_vector_residual)
            maximum_raw_tangent_angle_deg = max(maximum_raw_tangent_angle_deg, raw_tangent_angle)
            maximum_corrected_tangent_vector_residual = max(maximum_corrected_tangent_vector_residual, corrected_tangent_vector_residual)
            maximum_corrected_tangent_angle_deg = max(maximum_corrected_tangent_angle_deg, corrected_tangent_angle)
            maximum_raw_normal_tangent_dot_abs = max(maximum_raw_normal_tangent_dot_abs, raw_dot)
            maximum_corrected_normal_tangent_dot_abs = max(maximum_corrected_normal_tangent_dot_abs, corrected_dot)
            sample["maximum_position_residual_m"] = max(sample["maximum_position_residual_m"], position_residual)
            sample["maximum_normal_angle_deg"] = max(sample["maximum_normal_angle_deg"], normal_angle)
            sample["maximum_raw_tangent_angle_deg"] = max(sample["maximum_raw_tangent_angle_deg"], raw_tangent_angle)
            sample["maximum_corrected_tangent_angle_deg"] = max(sample["maximum_corrected_tangent_angle_deg"], corrected_tangent_angle)
            sample["maximum_raw_normal_tangent_dot_abs"] = max(sample["maximum_raw_normal_tangent_dot_abs"], raw_dot)
            sample["maximum_corrected_normal_tangent_dot_abs"] = max(sample["maximum_corrected_normal_tangent_dot_abs"], corrected_dot)

        if sample_index in (0, KEY_COUNT - 1):
            neutral_normal_angle_deg = max(neutral_normal_angle_deg, sample["maximum_normal_angle_deg"])
            neutral_corrected_tangent_angle_deg = max(
                neutral_corrected_tangent_angle_deg,
                sample["maximum_corrected_tangent_angle_deg"],
            )
        rows.append(sample)

    if abs(float(decoded["TIMES"][0])) > 1e-9 or abs(float(decoded["TIMES"][-1]) - 1.0) > 1e-6:
        raise ValueError("transported authored-key time boundary drift")
    if _quat_angle_deg(decoded["ROTATIONS"][0]) > 1e-6 or _quat_angle_deg(decoded["ROTATIONS"][-1]) > 1e-6:
        raise ValueError("transported neutral closure drift")

    position_pass = (
        maximum_position_residual_m <= POSITION_TOLERANCE_M
        and maximum_uv_residual <= UV_TOLERANCE
        and tangent_handedness_mismatch_count == 0
    )
    normal_deformation_excess_deg = max(0.0, maximum_normal_angle_deg - neutral_normal_angle_deg)
    corrected_tangent_deformation_excess_deg = max(
        0.0,
        maximum_corrected_tangent_angle_deg - neutral_corrected_tangent_angle_deg,
    )
    direction_equivalence = (
        normal_deformation_excess_deg <= DIRECTION_EXCESS_TOLERANCE_DEG
        and corrected_tangent_deformation_excess_deg <= DIRECTION_EXCESS_TOLERANCE_DEG
        and maximum_corrected_normal_tangent_dot_abs <= ORTHOGONALITY_TOLERANCE
    )
    state = PASS_STATE if position_pass and direction_equivalence else HOLD_STATE if position_pass else FAIL_STATE

    blended_indices = [index for index, weight in enumerate(child_weights) if 1e-4 < weight < 1.0 - 1e-4]
    if not blended_indices:
        raise ValueError("transported skin contains no blended vertex for negative control")
    peak_sample = max(range(KEY_COUNT), key=lambda index: _quat_angle_deg(decoded["ROTATIONS"][index]))
    probe_index = blended_indices[len(blended_indices) // 2]
    original_weight = child_weights[probe_index]
    mutated_weight = min(0.99, original_weight + 0.05)
    owner_peak_angle = _quat_angle_deg(decoded["ROTATIONS"][peak_sample])
    owner_peak_pose = _pose_metrics(
        source_positions,
        source_indices,
        source_areas,
        source_weights,
        joint_position,
        _vec3(joint["axis"], "joint axis"),
        owner_peak_angle,
    )
    owner_peak = _derive_posed_tangent_frame(right_candidate, static_basis, owner_peak_pose["positions"])
    expected_peak = _source_position_to_target(owner_peak["render_positions"][probe_index])
    original_peak = _skin_position(decoded["POSITION"][probe_index], pivot, decoded["ROTATIONS"][peak_sample], original_weight)
    mutated_peak = _skin_position(decoded["POSITION"][probe_index], pivot, decoded["ROTATIONS"][peak_sample], mutated_weight)
    original_probe_residual = _distance(original_peak, expected_peak)
    mutated_probe_residual = _distance(mutated_peak, expected_peak)
    if mutated_probe_residual <= original_probe_residual + 1e-5:
        raise ValueError("deliberate transported child-weight mutation was not detected")

    representative_indices = [0, 10, 20, 30, 40]
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "technical_art": {
            "head": TECHNICAL_ART_HEAD,
            "artifact_id": TECHNICAL_ART_ARTIFACT_ID,
            "artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
            "module_blob": TECHNICAL_ART_MODULE_BLOB,
            "glb_sha256": TECHNICAL_ART_GLB_SHA256,
        },
        "rigging": {
            "deformed_tangent_prerequisite_state": prerequisite["state"],
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
            "transported_weighting": BASELINE_WEIGHTING,
        },
        "motion_boundary": {
            "authored_key_count": KEY_COUNT,
            "time_start_seconds": float(decoded["TIMES"][0]),
            "time_end_seconds": float(decoded["TIMES"][-1]),
            "minimum_angle_deg": min(_quat_angle_deg(value) for value in decoded["ROTATIONS"]),
            "maximum_angle_deg": max(_quat_angle_deg(value) for value in decoded["ROTATIONS"]),
            "neutral_closure": True,
            "representative_samples": [rows[index] for index in representative_indices],
        },
        "position_uv_handedness": {
            "maximum_position_residual_m": maximum_position_residual_m,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "maximum_uv_residual": maximum_uv_residual,
            "uv_tolerance": UV_TOLERANCE,
            "tangent_handedness_mismatch_count": tangent_handedness_mismatch_count,
            "gate": "PASS" if position_pass else "FAIL",
        },
        "direction_frames": {
            "maximum_normal_vector_residual": maximum_normal_vector_residual,
            "maximum_normal_angle_deg": maximum_normal_angle_deg,
            "neutral_maximum_normal_angle_deg": neutral_normal_angle_deg,
            "normal_deformation_excess_deg": normal_deformation_excess_deg,
            "maximum_raw_tangent_vector_residual": maximum_raw_tangent_vector_residual,
            "maximum_raw_tangent_angle_deg": maximum_raw_tangent_angle_deg,
            "maximum_corrected_tangent_vector_residual": maximum_corrected_tangent_vector_residual,
            "maximum_corrected_tangent_angle_deg": maximum_corrected_tangent_angle_deg,
            "neutral_maximum_corrected_tangent_angle_deg": neutral_corrected_tangent_angle_deg,
            "corrected_tangent_deformation_excess_deg": corrected_tangent_deformation_excess_deg,
            "maximum_raw_normal_tangent_dot_abs": maximum_raw_normal_tangent_dot_abs,
            "maximum_corrected_normal_tangent_dot_abs": maximum_corrected_normal_tangent_dot_abs,
            "post_skin_gram_schmidt_orthogonality_gate": (
                "PASS" if maximum_corrected_normal_tangent_dot_abs <= ORTHOGONALITY_TOLERANCE else "FAIL"
            ),
            "equivalence_gate": "PASS" if direction_equivalence else "HOLD",
        },
        "all_41_key_samples": rows,
        "negative_controls": {
            "child_weight_mutation": {
                "render_vertex": probe_index,
                "peak_sample": peak_sample,
                "original_child_weight": original_weight,
                "mutated_child_weight": mutated_weight,
                "original_position_residual_m": original_probe_residual,
                "mutated_position_residual_m": mutated_probe_residual,
                "status": "PASS_MUTATION_DETECTED",
            },
            "glb_sha256_gate": "PASS_EXACT_SHA256",
            "rig_plan_digest_gate": "PASS_EXACT_DIGEST",
            "weighting_profile_digest_gate": "PASS_EXACT_DIGEST",
        },
        "truth_boundary": {
            "source_modified": False,
            "rig_modified": False,
            "weights_modified": False,
            "animation_modified": False,
            "technical_art_glb_modified": False,
            "post_skin_gram_schmidt_is_measurement_only": True,
            "position_equivalence_established": position_pass,
            "deformed_direction_frame_equivalence_established": direction_equivalence,
            "animation_accepted": False,
            "target_engine_import_or_playback_accepted": False,
            "runtime_or_controller_accepted": False,
            "shaded_visual_quality_accepted": False,
            "canon_claimed": False,
        },
    }
