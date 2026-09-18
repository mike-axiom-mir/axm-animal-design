"""Rigging continuity proof for Technical Art's JOINTS_0 width adoption.

This module does not author a new rig, weight profile, Animation clip, importer,
Runtime path, or direction-frame policy. It rebinds the existing Animal elbow
skin to one exact newer Technical Art producer identity and proves that changing
JOINTS_0 storage from UNSIGNED_SHORT to UNSIGNED_BYTE leaves the decoded rig
semantics and all 41 authored skinned positions unchanged.

The historical deformed NORMAL/TANGENT transport HOLD remains visible and is not
reclassified by this position/joint-index continuity proof.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

EVIDENCE_SCHEMA = "axm.animal-rigging-joint-index-width-rebind/v0.1"
PASS_STATE = (
    "PASS_TECHNICAL_ART_JOINT_INDEX_WIDTH_RIGGING_REBIND_41_KEYS"
    "__DEFORMED_DIRECTION_FRAME_HOLD_PRESERVED"
)
HOLD_STATE = "HOLD_TECHNICAL_ART_JOINT_INDEX_WIDTH_RIGGING_REBIND"

CONTROL_TECHNICAL_ART_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
CONTROL_ARTIFACT_ID = 10474385703
CONTROL_ARTIFACT_SHA256 = "7fc2a7f5d745da593e8762efa98e13661f84a057b1eb60921d576c366e71d7bb"
CONTROL_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
CONTROL_JOINT_COMPONENT_TYPE = 5123

PRODUCER_TECHNICAL_ART_HEAD = "54c9c11505e798a56619ebc14e9ab41f522eef70"
PRODUCER_ARTIFACT_ID = 10477320699
PRODUCER_ARTIFACT_SHA256 = "bc5fe4798ce0c43d04338114905ccf1ae8cd9a676800e824571b60aef9aff15b"
PRODUCER_GLB_SHA256 = "8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566"
PRODUCER_MODULE_BLOB = "68acd2ad5d335a4c6bcabf3d4d0208d7123c12eb"
PRODUCER_JOINT_COMPONENT_TYPE = 5121
PRODUCER_ADOPTION_STATUS = "PASS_TECHNICAL_ART_PRODUCER_ADOPTS_BOUNDED_JOINT_INDEX_WIDTH"
TRANSPORT_STATUS = "PASS_ANIMAL_GEOMETRY_UV_TANGENT_RENDER_DOMAIN_WITH_SKIN_KEYS_TO_CURRENT_UC_CODEC"

GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
GEOMETRY_BASIS_DIGEST = "b980dac912b685fc5a94e4b97f5db0a49745711c369322753b63dd968c801058"
SOURCE_RIGGING_HEAD = "4acd9286140dd008f2a4f01ff513912497313e4f"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
WEIGHTING_ID = "smoothstep-v0"
ANIMATION_HEAD = "1a8c929ce4372c4b1b1f29e9ac4cadd0cc26ac48"
ANIMATION_GATE = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_41_SAMPLE_MOTION_REBIND"

KEY_COUNT = 41
SOURCE_VERTEX_COUNT = 42
RENDER_VERTEX_COUNT = 84
TRIANGLE_COUNT = 80
JOINT_SLOTS = 4
POSITION_TOLERANCE_M = 1e-6
EXACT_REBIND_TOLERANCE_M = 1e-12
MUTATION_MIN_SIGNAL_M = 1e-2
REPRESENTATIVE_INDICES = (0, 10, 20, 30, 40)

# Historical Rigging #25 result intentionally retained as a HOLD, not recomputed here.
STATIC_NORMAL_DEFORMATION_EXCESS_DEG = 7.541933278181338
STATIC_CORRECTED_TANGENT_DEFORMATION_EXCESS_DEG = 3.6840862372161047

_COMPONENT_FORMAT = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_TYPE_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_SEMANTIC_FIELDS = (
    "POSITION",
    "NORMAL",
    "TANGENT",
    "TEXCOORD_0",
    "JOINTS_0",
    "WEIGHTS_0",
    "INDICES",
    "TIMES",
    "ROTATIONS",
)


def _digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _distance(left, right) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))


def _cross(left, right):
    return [
        float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]),
        float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]),
        float(left[0]) * float(right[1]) - float(left[1]) * float(right[0]),
    ]


def _unit(value):
    length = math.sqrt(sum(float(item) * float(item) for item in value))
    if length <= 1e-15:
        raise ValueError("zero-length quaternion/vector")
    return [float(item) / length for item in value]


def _quat_rotate(vector, quaternion):
    x, y, z, w = _unit(quaternion)
    qv = [x, y, z]
    base = [float(item) for item in vector]
    uv = _cross(qv, base)
    uuv = _cross(qv, uv)
    return [base[index] + 2.0 * (w * uv[index] + uuv[index]) for index in range(3)]


def _quat_angle_deg(quaternion) -> float:
    x, y, z, w = _unit(quaternion)
    angle = math.degrees(2.0 * math.atan2(math.sqrt(x * x + y * y + z * z), w))
    return 360.0 - angle if angle > 180.0 else angle


def _skin_position(position, pivot, quaternion, child_weight: float):
    local = [float(position[index]) - float(pivot[index]) for index in range(3)]
    rotated = _quat_rotate(local, quaternion)
    child = [rotated[index] + float(pivot[index]) for index in range(3)]
    weight = float(child_weight)
    return [
        (1.0 - weight) * float(position[index]) + weight * child[index]
        for index in range(3)
    ]


def _source_position_to_target(value):
    x, y, z = (float(component) for component in value)
    return [-y, z, x]


def decode_rigged_glb(glb: bytes, *, expected_sha256: str) -> dict[str, Any]:
    """Decode only the exact accessor surface needed by this bounded audit."""
    observed_sha256 = _digest_bytes(glb)
    if observed_sha256 != expected_sha256:
        raise ValueError(f"GLB SHA-256 drift: {observed_sha256} != {expected_sha256}")
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
        payload = glb[offset : offset + chunk_length]
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
            output.append(values[0] if width == 1 else list(values))
        return output

    meshes = document.get("meshes", [])
    if len(meshes) != 1 or len(meshes[0].get("primitives", [])) != 1:
        raise ValueError("expected exactly one transported primitive")
    primitive = meshes[0]["primitives"][0]
    attributes = primitive.get("attributes", {})
    required = {"POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"}
    if set(attributes) != required:
        raise ValueError("transported attribute set drift")

    decoded = {name: accessor(int(attributes[name])) for name in required}
    decoded["INDICES"] = accessor(int(primitive["indices"]))
    decoded["component_types"] = {
        name: int(document["accessors"][int(accessor_index)]["componentType"])
        for name, accessor_index in attributes.items()
    }

    animations = document.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected exactly one transported animation channel")
    channel = animations[0]["channels"][0]
    if channel.get("target", {}).get("path") != "rotation":
        raise ValueError("transported animation target path drift")
    sampler = animations[0]["samplers"][int(channel["sampler"])]
    decoded["TIMES"] = accessor(int(sampler["input"]))
    decoded["ROTATIONS"] = accessor(int(sampler["output"]))
    decoded["ANIMATED_NODE"] = int(channel["target"]["node"])
    decoded["document"] = document
    return decoded


def _validate_transport_receipt(receipt: dict[str, Any], *, expected_head: str, expected_glb: str) -> None:
    if receipt.get("status") != TRANSPORT_STATUS:
        raise ValueError("Technical Art transport status drift")
    if receipt.get("technical_art_head") != expected_head:
        raise ValueError("Technical Art transport head drift")
    owners = receipt.get("owners", {})
    geometry = owners.get("geometry", {})
    if geometry.get("head") != GEOMETRY_HEAD or geometry.get("basis_digest") != GEOMETRY_BASIS_DIGEST:
        raise ValueError("Geometry UV/tangent identity drift")
    rigging = owners.get("rigging", {})
    if (
        rigging.get("head") != SOURCE_RIGGING_HEAD
        or rigging.get("rig_donor_head") != RIG_DONOR_HEAD
        or rigging.get("rig_plan_sha256") != RIG_PLAN_DIGEST
        or rigging.get("weighting") != WEIGHTING_ID
    ):
        raise ValueError("source rig/weight identity drift")
    animation = owners.get("animation", {})
    if (
        animation.get("head") != ANIMATION_HEAD
        or animation.get("gate") != ANIMATION_GATE
        or animation.get("key_count") != KEY_COUNT
    ):
        raise ValueError("Animation sampling identity drift")
    transport = receipt.get("transport", {})
    if (
        transport.get("glb_sha256") != expected_glb
        or transport.get("render_vertices") != RENDER_VERTEX_COUNT
        or transport.get("source_vertices") != SOURCE_VERTEX_COUNT
        or transport.get("triangles") != TRIANGLE_COUNT
        or transport.get("authored_keys") != KEY_COUNT
    ):
        raise ValueError("transport shape/key identity drift")


def _validate_adoption_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("status") != PRODUCER_ADOPTION_STATUS:
        raise ValueError("Technical Art joint-width adoption status drift")
    if receipt.get("technical_art_head") != PRODUCER_TECHNICAL_ART_HEAD:
        raise ValueError("Technical Art producer head drift")
    control = receipt.get("source_transport_control", {})
    if (
        control.get("head") != CONTROL_TECHNICAL_ART_HEAD
        or control.get("glb_sha256") != CONTROL_GLB_SHA256
        or int(control.get("joint_component_type", -1)) != CONTROL_JOINT_COMPONENT_TYPE
        or int(control.get("joint_payload_bytes", -1)) != RENDER_VERTEX_COUNT * JOINT_SLOTS * 2
    ):
        raise ValueError("retained 16-bit control identity drift")
    producer = receipt.get("producer_adoption", {})
    if (
        producer.get("glb_sha256") != PRODUCER_GLB_SHA256
        or int(producer.get("component_type", -1)) != PRODUCER_JOINT_COMPONENT_TYPE
        or int(producer.get("minimum_joint_index", -1)) != 0
        or int(producer.get("maximum_joint_index", -1)) != 1
        or int(producer.get("count", -1)) != RENDER_VERTEX_COUNT
        or int(producer.get("slots_per_vertex", -1)) != JOINT_SLOTS
        or int(producer.get("payload_bytes", -1)) != RENDER_VERTEX_COUNT * JOINT_SLOTS
    ):
        raise ValueError("producer JOINTS_0 adoption identity drift")


def _child_weights(decoded: dict[str, Any]) -> list[float]:
    output = []
    for joints, weights in zip(decoded["JOINTS_0"], decoded["WEIGHTS_0"]):
        if len(joints) != JOINT_SLOTS or len(weights) != JOINT_SLOTS:
            raise ValueError("skin rows must be VEC4")
        if abs(sum(float(weight) for weight in weights) - 1.0) > 1e-6:
            raise ValueError("skin row weight sum drift")
        unexpected = sum(float(weight) for joint, weight in zip(joints, weights) if int(joint) not in (0, 1))
        if abs(unexpected) > 1e-8:
            raise ValueError("unexpected weighted joint introduced")
        output.append(sum(float(weight) for joint, weight in zip(joints, weights) if int(joint) == 1))
    if len(output) != RENDER_VERTEX_COUNT:
        raise ValueError("render weight count drift")
    return output


def _validate_owner_inputs(owner_frames: dict[str, Any], geometry_basis: dict[str, Any]) -> tuple[list[dict[str, Any]], list[int]]:
    frames = owner_frames.get("frames")
    if not isinstance(frames, list) or len(frames) != KEY_COUNT:
        raise ValueError("owner frame count drift")
    if owner_frames.get("rigging_head") != SOURCE_RIGGING_HEAD:
        raise ValueError("owner frame Rigging identity drift")
    if geometry_basis.get("source_vertex_count") != SOURCE_VERTEX_COUNT:
        raise ValueError("Geometry source vertex count drift")
    if geometry_basis.get("render_vertex_count") != RENDER_VERTEX_COUNT:
        raise ValueError("Geometry render vertex count drift")
    mapping = geometry_basis.get("render_source_indices")
    if not isinstance(mapping, list) or len(mapping) != RENDER_VERTEX_COUNT:
        raise ValueError("Geometry render/source mapping drift")
    mapping = [int(index) for index in mapping]
    if set(mapping) != set(range(SOURCE_VERTEX_COUNT)):
        raise ValueError("Geometry render/source mapping lost source identity")
    for sample_index, frame in enumerate(frames):
        if int(frame.get("sample_index", -1)) != sample_index:
            raise ValueError("owner frame sample ordering drift")
        positions = frame.get("positions")
        if not isinstance(positions, list) or len(positions) != SOURCE_VERTEX_COUNT:
            raise ValueError("owner source pose count drift")
    return frames, mapping


def inspect_joint_index_width_rigging_rebind(
    *,
    control_glb: bytes,
    producer_glb: bytes,
    control_transport_receipt: dict[str, Any],
    producer_transport_receipt: dict[str, Any],
    adoption_receipt: dict[str, Any],
    owner_frames: dict[str, Any],
    geometry_basis: dict[str, Any],
) -> dict[str, Any]:
    """Directly rebind the exact newer producer to the retained skin/pose boundary."""
    _validate_transport_receipt(
        control_transport_receipt,
        expected_head=CONTROL_TECHNICAL_ART_HEAD,
        expected_glb=CONTROL_GLB_SHA256,
    )
    _validate_transport_receipt(
        producer_transport_receipt,
        expected_head=PRODUCER_TECHNICAL_ART_HEAD,
        expected_glb=PRODUCER_GLB_SHA256,
    )
    _validate_adoption_receipt(adoption_receipt)
    frames, render_source_indices = _validate_owner_inputs(owner_frames, geometry_basis)

    control = decode_rigged_glb(control_glb, expected_sha256=CONTROL_GLB_SHA256)
    producer = decode_rigged_glb(producer_glb, expected_sha256=PRODUCER_GLB_SHA256)
    if control["component_types"]["JOINTS_0"] != CONTROL_JOINT_COMPONENT_TYPE:
        raise ValueError("control JOINTS_0 component width drift")
    if producer["component_types"]["JOINTS_0"] != PRODUCER_JOINT_COMPONENT_TYPE:
        raise ValueError("producer JOINTS_0 component width drift")

    semantic_equality = {field: control[field] == producer[field] for field in _SEMANTIC_FIELDS}
    if not all(semantic_equality.values()):
        drift = [field for field, equal in semantic_equality.items() if not equal]
        raise ValueError(f"decoded rig semantic drift across width adoption: {drift}")

    control_node = int(control["ANIMATED_NODE"])
    producer_node = int(producer["ANIMATED_NODE"])
    if control_node != producer_node:
        raise ValueError("animated joint node identity drift")
    control_pivot = control["document"]["nodes"][control_node].get("translation")
    producer_pivot = producer["document"]["nodes"][producer_node].get("translation")
    if control_pivot != producer_pivot or not isinstance(producer_pivot, list) or len(producer_pivot) != 3:
        raise ValueError("transported joint pivot drift")

    control_child_weights = _child_weights(control)
    producer_child_weights = _child_weights(producer)
    if control_child_weights != producer_child_weights:
        raise ValueError("decoded effective child weights drift")

    maximum_control_producer_position_residual_m = 0.0
    maximum_owner_position_residual_m = 0.0
    owner_worst_sample_index = 0
    rows = []
    for sample_index, (time_value, quaternion, owner_frame) in enumerate(
        zip(producer["TIMES"], producer["ROTATIONS"], frames)
    ):
        if abs(float(time_value) - float(owner_frame["time_seconds"])) > 1e-7:
            raise ValueError("transported key time drift against owner frame")
        control_positions = [
            _skin_position(position, control_pivot, quaternion, child_weight)
            for position, child_weight in zip(control["POSITION"], control_child_weights)
        ]
        producer_positions = [
            _skin_position(position, producer_pivot, quaternion, child_weight)
            for position, child_weight in zip(producer["POSITION"], producer_child_weights)
        ]
        control_producer_residual = max(
            _distance(left, right) for left, right in zip(control_positions, producer_positions)
        )
        expected_owner = [
            _source_position_to_target(owner_frame["positions"][source_index])
            for source_index in render_source_indices
        ]
        owner_residual = max(
            _distance(observed, expected) for observed, expected in zip(producer_positions, expected_owner)
        )
        maximum_control_producer_position_residual_m = max(
            maximum_control_producer_position_residual_m, control_producer_residual
        )
        if owner_residual > maximum_owner_position_residual_m:
            maximum_owner_position_residual_m = owner_residual
            owner_worst_sample_index = sample_index
        rows.append(
            {
                "sample_index": sample_index,
                "time_seconds": float(time_value),
                "angle_deg_from_transport_quaternion": _quat_angle_deg(quaternion),
                "control_vs_producer_position_residual_m": control_producer_residual,
                "producer_vs_owner_position_residual_m": owner_residual,
            }
        )

    peak_sample_index = max(
        range(KEY_COUNT), key=lambda index: _quat_angle_deg(producer["ROTATIONS"][index])
    )
    mutation_render_index = next(
        (
            index
            for index, child_weight in enumerate(producer_child_weights)
            if abs(float(child_weight) - 1.0) <= 1e-12
        ),
        None,
    )
    if mutation_render_index is None:
        raise ValueError("no rigid-child render vertex available for joint-identity negative control")
    peak_quaternion = producer["ROTATIONS"][peak_sample_index]
    baseline_mutation_vertex = _skin_position(
        producer["POSITION"][mutation_render_index], producer_pivot, peak_quaternion, 1.0
    )
    mutated_mutation_vertex = _skin_position(
        producer["POSITION"][mutation_render_index], producer_pivot, peak_quaternion, 0.0
    )
    mutation_signal_m = _distance(baseline_mutation_vertex, mutated_mutation_vertex)
    if mutation_signal_m < MUTATION_MIN_SIGNAL_M:
        raise ValueError("joint-identity mutation did not produce a sufficient pose signal")

    semantic_joint_scalar_count = RENDER_VERTEX_COUNT * JOINT_SLOTS
    rebind_pass = (
        maximum_control_producer_position_residual_m <= EXACT_REBIND_TOLERANCE_M
        and maximum_owner_position_residual_m <= POSITION_TOLERANCE_M
        and semantic_equality["JOINTS_0"]
        and semantic_equality["WEIGHTS_0"]
        and semantic_equality["TIMES"]
        and semantic_equality["ROTATIONS"]
    )
    state = PASS_STATE if rebind_pass else HOLD_STATE
    return {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "exact_identities": {
            "control_technical_art_head": CONTROL_TECHNICAL_ART_HEAD,
            "control_artifact_id": CONTROL_ARTIFACT_ID,
            "control_artifact_sha256": CONTROL_ARTIFACT_SHA256,
            "control_glb_sha256": CONTROL_GLB_SHA256,
            "producer_technical_art_head": PRODUCER_TECHNICAL_ART_HEAD,
            "producer_module_blob": PRODUCER_MODULE_BLOB,
            "producer_artifact_id": PRODUCER_ARTIFACT_ID,
            "producer_artifact_sha256": PRODUCER_ARTIFACT_SHA256,
            "producer_glb_sha256": PRODUCER_GLB_SHA256,
            "geometry_head": GEOMETRY_HEAD,
            "source_rigging_head": SOURCE_RIGGING_HEAD,
            "rig_donor_head": RIG_DONOR_HEAD,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "weighting": WEIGHTING_ID,
            "animation_head": ANIMATION_HEAD,
        },
        "storage_boundary": {
            "control_joint_component_type": CONTROL_JOINT_COMPONENT_TYPE,
            "producer_joint_component_type": PRODUCER_JOINT_COMPONENT_TYPE,
            "decoded_joint_rows_exact": semantic_equality["JOINTS_0"],
            "decoded_joint_scalar_count": semantic_joint_scalar_count,
            "decoded_weight_rows_exact": semantic_equality["WEIGHTS_0"],
            "positions_exact": semantic_equality["POSITION"],
            "normals_exact": semantic_equality["NORMAL"],
            "tangents_exact": semantic_equality["TANGENT"],
            "uvs_exact": semantic_equality["TEXCOORD_0"],
            "indices_exact": semantic_equality["INDICES"],
            "animation_times_exact": semantic_equality["TIMES"],
            "animation_rotations_exact": semantic_equality["ROTATIONS"],
            "joint_pivot_exact": control_pivot == producer_pivot,
        },
        "motion_boundary": {
            "authored_key_count": KEY_COUNT,
            "time_start_seconds": float(producer["TIMES"][0]),
            "time_end_seconds": float(producer["TIMES"][-1]),
            "minimum_angle_deg": min(_quat_angle_deg(value) for value in producer["ROTATIONS"]),
            "maximum_angle_deg": max(_quat_angle_deg(value) for value in producer["ROTATIONS"]),
            "maximum_control_vs_producer_position_residual_m": maximum_control_producer_position_residual_m,
            "maximum_producer_vs_owner_position_residual_m": maximum_owner_position_residual_m,
            "owner_worst_sample_index": owner_worst_sample_index,
            "representative_samples": [rows[index] for index in REPRESENTATIVE_INDICES],
        },
        "negative_controls": {
            "rigid_child_joint_identity_mutation": {
                "sample_index": peak_sample_index,
                "angle_deg": _quat_angle_deg(peak_quaternion),
                "render_vertex_index": mutation_render_index,
                "mutation": "effective child joint weight 1.0 -> parent 0.0",
                "position_signal_m": mutation_signal_m,
                "required_signal_m": MUTATION_MIN_SIGNAL_M,
                "status": "PASS_MUTATION_DETECTED",
            }
        },
        "preserved_hold": {
            "name": "PASS_TRANSPORTED_SKINNED_POSITION_EQUIVALENCE__HOLD_DEFORMED_NORMAL_TANGENT_EQUIVALENCE",
            "static_normal_deformation_excess_deg": STATIC_NORMAL_DEFORMATION_EXCESS_DEG,
            "static_corrected_tangent_deformation_excess_deg": STATIC_CORRECTED_TANGENT_DEFORMATION_EXCESS_DEG,
            "recomputed_in_this_lane": False,
            "reason": (
                "JOINTS_0 width adoption leaves decoded POSITION/NORMAL/TANGENT/UV/JOINTS/WEIGHTS, "
                "animation keys and pivot exact; this lane proves skin-position continuity only and does not "
                "reinterpret the earlier direction-frame HOLD."
            ),
        },
        "truth_boundary": {
            "proves": [
                "the exact newer Technical Art producer's UNSIGNED_BYTE JOINTS_0 decodes to the same 336 joint scalars as the retained UNSIGNED_SHORT control",
                "all exact skin weights, rig-relevant geometry attributes, animation key times/rotations and joint pivot are unchanged across the producer width adoption",
                "the newer producer reproduces the retained control skinned POSITION field at all 41 exact authored keys and remains within the existing owner-position tolerance",
            ],
            "does_not_prove": [
                "deformed NORMAL/TANGENT direction-frame equivalence; the historical Rigging HOLD remains active",
                "a new or improved weighting profile, anatomy, volume preservation or final skin quality",
                "Animation timing/interpolation/playback acceptance",
                "Runtime/controller/device performance or gameplay acceptance",
                "Technical Art adoption of Rigging's post-skin owner-frame reconstruction",
                "final shaded visual acceptance, CANON, production readiness or Rigging mastery",
            ],
            "animation_accepted": False,
            "runtime_or_controller_accepted": False,
            "technical_art_reconstruction_adopted": False,
            "deformed_direction_frame_equivalence_claimed": False,
            "canon_claimed": False,
        },
    }
