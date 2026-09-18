#!/usr/bin/env python3
"""Animation-owned dense subframe guard for the exact normalized-u16 skin-weight candidate.

This observer consumes retained Runtime and Rigging evidence. It does not author or
modify a clip, rig, weight quantizer, transport codec, controller, or gameplay state.
It evaluates the exact transported glTF LINEAR rotation channel at deterministic
subframes and asks whether Runtime's exact normalized-u16 weight representation stays
inside Rigging's already-owned positional deformation bound between authored keys.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

SCHEMA = "axm.animal-animation-u16-weight-subframe-guard/v0.1"
RUNTIME_HEAD = "e7874c4a8dca1db48bc66f3546c2134f7d724456"
RUNTIME_ARTIFACT_ID = 10477292250
RUNTIME_ARTIFACT_SHA256 = "76455589e0dde3327f72ebff6a117a2ce12ff57edaaf1d0e61304056d03063c3"
CONTROL_GLB_SHA256 = "8d9bfb80369bda09eaad786a35833cd5e04da5e608211f53648daaa1cde29566"
CANDIDATE_GLB_SHA256 = "81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb"
RIGGING_HEAD = "e4ce8c1f4c3deb55220cf962206d51013d0cfe73"
RIGGING_ARTIFACT_ID = 10478912800
RIGGING_ARTIFACT_SHA256 = "99a48f48fe1a9c622f1f46a27370a7239df7e17a8dcf9d1c9eb0b32f6a57a088"
EXPECTED_RIGGING_STATE = "PASS_RUNTIME_U16_WEIGHT_CANDIDATE_RIGGING_DEFORMATION_REBIND_41_KEYS__STATIC_DIRECTION_FRAME_HOLD_PRESERVED"
ANIMATION_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
SUBFRAMES_PER_AUTHORED_INTERVAL = 8
DENSE_RATE_HZ = 320
DENSE_SAMPLE_COUNT = 321
POSITION_COMPARE_EPS_M = 1e-12
LOOP_EPS_M = 1e-9
MIRROR_EPS_M = 1e-12
NEGATIVE_CONTROL_U16_STEPS = 64
NEGATIVE_CONTROL_TIME_S = 0.3375
NEGATIVE_CONTROL_VERTEX = 23

_FORMATS = {
    5120: ("b", 1),
    5121: ("B", 1),
    5122: ("h", 2),
    5123: ("H", 2),
    5125: ("I", 4),
    5126: ("f", 4),
}
_WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    if len(data) < 20:
        raise ValueError("GLB is truncated")
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("GLB header drift")
    offset = 12
    document = None
    binary = None
    while offset + 8 <= len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        end = offset + length
        if end > len(data):
            raise ValueError("GLB chunk exceeds file")
        payload = data[offset:end]
        offset = end
        if kind == b"JSON":
            document = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind in (b"BIN\x00", b"BIN "):
            binary = payload
    if not isinstance(document, dict) or binary is None:
        raise ValueError("GLB must contain JSON and BIN chunks")
    return document, binary


def _decode_accessor(document: dict[str, Any], binary: bytes, index: int) -> list[Any]:
    accessor = document["accessors"][index]
    view = document["bufferViews"][int(accessor["bufferView"])]
    component_type = int(accessor["componentType"])
    kind = str(accessor["type"])
    if component_type not in _FORMATS or kind not in _WIDTHS:
        raise ValueError("unsupported accessor type in bounded Animation guard")
    fmt, component_size = _FORMATS[component_type]
    width = _WIDTHS[kind]
    packed = component_size * width
    stride = int(view.get("byteStride", packed))
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    result: list[Any] = []
    for row_index in range(int(accessor["count"])):
        values = list(struct.unpack_from("<" + fmt * width, binary, base + row_index * stride))
        if accessor.get("normalized") is True:
            if component_type == 5121:
                values = [value / 255.0 for value in values]
            elif component_type == 5123:
                values = [value / 65535.0 for value in values]
            elif component_type == 5120:
                values = [max(value / 127.0, -1.0) for value in values]
            elif component_type == 5122:
                values = [max(value / 32767.0, -1.0) for value in values]
            else:
                raise ValueError("unexpected normalized accessor component type")
        result.append(values[0] if width == 1 else values)
    return result


def _dot(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right))


def _cross(left: list[float] | tuple[float, ...], right: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    return (
        float(left[1]) * float(right[2]) - float(left[2]) * float(right[1]),
        float(left[2]) * float(right[0]) - float(left[0]) * float(right[2]),
        float(left[0]) * float(right[1]) - float(left[1]) * float(right[0]),
    )


def _quat_unit(value: list[float]) -> list[float]:
    length = math.sqrt(sum(float(component) ** 2 for component in value))
    if length <= 1e-15:
        raise ValueError("zero-length rotation quaternion")
    return [float(component) / length for component in value]


def _quat_slerp(left: list[float], right: list[float], alpha: float) -> list[float]:
    a = _quat_unit(left)
    b = _quat_unit(right)
    dot = _dot(a, b)
    if dot < 0.0:
        b = [-value for value in b]
        dot = -dot
    dot = max(-1.0, min(1.0, dot))
    if dot > 0.9995:
        return _quat_unit([(1.0 - alpha) * a[i] + alpha * b[i] for i in range(4)])
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    return [
        math.sin((1.0 - alpha) * theta) / sin_theta * a[i]
        + math.sin(alpha * theta) / sin_theta * b[i]
        for i in range(4)
    ]


def _quat_rotate(vector: list[float], quaternion: list[float]) -> list[float]:
    x, y, z, w = _quat_unit(quaternion)
    qv = (x, y, z)
    v = tuple(float(component) for component in vector)
    uv = _cross(qv, v)
    uuv = _cross(qv, uv)
    return [v[i] + 2.0 * (w * uv[i] + uuv[i]) for i in range(3)]


def _rotation_at(times: list[float], rotations: list[list[float]], time_s: float) -> list[float]:
    if time_s <= float(times[0]):
        return rotations[0]
    if time_s >= float(times[-1]):
        return rotations[-1]
    left_index = bisect.bisect_right(times, time_s) - 1
    t0 = float(times[left_index])
    t1 = float(times[left_index + 1])
    alpha = (time_s - t0) / (t1 - t0)
    return _quat_slerp(rotations[left_index], rotations[left_index + 1], alpha)


def _child_weight(joints: list[int], weights: list[float]) -> float:
    return sum(float(weight) for joint, weight in zip(joints, weights) if int(joint) == 1)


def _skin_position(position: list[float], pivot: list[float], rotation: list[float], child_weight: float) -> list[float]:
    relative = [float(position[i]) - float(pivot[i]) for i in range(3)]
    rotated = _quat_rotate(relative, rotation)
    child = [rotated[i] + float(pivot[i]) for i in range(3)]
    weight = float(child_weight)
    return [(1.0 - weight) * float(position[i]) + weight * child[i] for i in range(3)]


def _distance(left: list[float], right: list[float]) -> float:
    return math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(left, right)))


def _extract_motion(glb: bytes) -> dict[str, Any]:
    document, binary = _parse_glb(glb)
    meshes = document.get("meshes", [])
    if len(meshes) != 1 or len(meshes[0].get("primitives", [])) != 1:
        raise ValueError("expected exact one-mesh/one-primitive retained Animal GLB")
    primitive = meshes[0]["primitives"][0]
    attrs = primitive.get("attributes", {})
    required = {"POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"}
    if set(attrs) != required:
        raise ValueError("retained attribute set drift")
    animations = document.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected one retained rotation channel")
    channel = animations[0]["channels"][0]
    sampler = animations[0]["samplers"][int(channel["sampler"])]
    if channel.get("target", {}).get("path") != "rotation" or sampler.get("interpolation") != "LINEAR":
        raise ValueError("expected glTF LINEAR rotation channel")
    animated_node = int(channel["target"]["node"])
    nodes = document.get("nodes", [])
    if not 0 <= animated_node < len(nodes):
        raise ValueError("animated node index drift")
    pivot = nodes[animated_node].get("translation")
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise ValueError("animated child pivot missing")
    skins = document.get("skins", [])
    if len(skins) != 1 or skins[0].get("joints") != [1, 2] or animated_node != 2:
        raise ValueError("exact retained two-joint skin identity drift")
    return {
        "positions": _decode_accessor(document, binary, int(attrs["POSITION"])),
        "joints": _decode_accessor(document, binary, int(attrs["JOINTS_0"])),
        "weights": _decode_accessor(document, binary, int(attrs["WEIGHTS_0"])),
        "times": _decode_accessor(document, binary, int(sampler["input"])),
        "rotations": _decode_accessor(document, binary, int(sampler["output"])),
        "pivot": [float(value) for value in pivot],
    }


def _validate_pair(control: dict[str, Any], candidate: dict[str, Any]) -> None:
    for key in ("positions", "joints", "times", "rotations", "pivot"):
        if control[key] != candidate[key]:
            raise ValueError(f"control/candidate {key} identity drift")
    if len(control["positions"]) != 84 or len(control["times"]) != 41:
        raise ValueError("retained render/key counts drift")
    if abs(float(control["times"][0])) > 1e-12 or abs(float(control["times"][-1]) - 1.0) > 1e-6:
        raise ValueError("retained 1.0 s animation duration drift")


def _frame(control: dict[str, Any], candidate: dict[str, Any], time_s: float, *, mutated_candidate_weights: list[list[float]] | None = None) -> dict[str, Any]:
    rotation = _rotation_at(control["times"], control["rotations"], time_s)
    candidate_weights = mutated_candidate_weights if mutated_candidate_weights is not None else candidate["weights"]
    max_delta = 0.0
    max_vertex = -1
    control_positions: list[list[float]] = []
    candidate_positions: list[list[float]] = []
    for index, (position, joints, control_weights, u16_weights) in enumerate(
        zip(control["positions"], control["joints"], control["weights"], candidate_weights)
    ):
        control_pos = _skin_position(position, control["pivot"], rotation, _child_weight(joints, control_weights))
        candidate_pos = _skin_position(position, control["pivot"], rotation, _child_weight(joints, u16_weights))
        delta = _distance(control_pos, candidate_pos)
        control_positions.append(control_pos)
        candidate_positions.append(candidate_pos)
        if delta > max_delta:
            max_delta = delta
            max_vertex = index
    return {
        "time_s": time_s,
        "max_control_candidate_position_delta_m": max_delta,
        "max_delta_vertex": max_vertex,
        "control_positions": control_positions,
        "candidate_positions": candidate_positions,
    }


def build_report(control_glb: bytes, candidate_glb: bytes, rigging_receipt: dict[str, Any], current_animation_head: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256_bytes(control_glb) != CONTROL_GLB_SHA256:
        raise ValueError("Runtime retained FLOAT control GLB SHA-256 drift")
    if sha256_bytes(candidate_glb) != CANDIDATE_GLB_SHA256:
        raise ValueError("Runtime retained normalized-u16 candidate GLB SHA-256 drift")
    if rigging_receipt.get("current_rigging_head") != RIGGING_HEAD:
        raise ValueError("Rigging exact head drift")
    if rigging_receipt.get("state") != EXPECTED_RIGGING_STATE:
        raise ValueError("Rigging scoped state drift")
    identity = rigging_receipt.get("identity", {})
    if identity.get("runtime_head") != RUNTIME_HEAD:
        raise ValueError("Rigging Runtime donor identity drift")
    if identity.get("candidate_glb_sha256") != CANDIDATE_GLB_SHA256 or identity.get("control_glb_sha256") != CONTROL_GLB_SHA256:
        raise ValueError("Rigging retained GLB identities drift")
    if identity.get("weighting") != "smoothstep-v0":
        raise ValueError("Rigging weighting identity drift")
    rig_deformation = rigging_receipt.get("deformation", {})
    rig_bound = float(rig_deformation.get("bound_m", -1.0))
    rig_authored_max = float(rig_deformation.get("max_control_candidate_position_delta_m", -1.0))
    if rig_bound <= 0.0 or rig_authored_max < 0.0:
        raise ValueError("Rigging deformation receipt incomplete")

    control = _extract_motion(control_glb)
    candidate = _extract_motion(candidate_glb)
    _validate_pair(control, candidate)

    rows: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    for dense_index in range(DENSE_SAMPLE_COUNT):
        time_s = dense_index / DENSE_RATE_HZ
        frame = _frame(control, candidate, time_s)
        frames.append(frame)
        rows.append(
            {
                "dense_index": dense_index,
                "time_s": time_s,
                "authored_key": dense_index % SUBFRAMES_PER_AUTHORED_INTERVAL == 0,
                "max_control_candidate_position_delta_m": frame["max_control_candidate_position_delta_m"],
                "max_delta_vertex": frame["max_delta_vertex"],
            }
        )

    dense_max = max(row["max_control_candidate_position_delta_m"] for row in rows)
    dense_max_index = max(range(len(rows)), key=lambda index: rows[index]["max_control_candidate_position_delta_m"])
    authored_rows = [row for row in rows if row["authored_key"]]
    authored_max = max(row["max_control_candidate_position_delta_m"] for row in authored_rows)
    authored_max_residual = abs(authored_max - rig_authored_max)
    time_mirror_residual = max(
        abs(rows[index]["max_control_candidate_position_delta_m"] - rows[-1 - index]["max_control_candidate_position_delta_m"])
        for index in range(len(rows))
    )

    control_loop = max(_distance(a, b) for a, b in zip(frames[0]["control_positions"], frames[-1]["control_positions"]))
    candidate_loop = max(_distance(a, b) for a, b in zip(frames[0]["candidate_positions"], frames[-1]["candidate_positions"]))

    mutated = [list(row) for row in candidate["weights"]]
    joints = [int(value) for value in control["joints"][NEGATIVE_CONTROL_VERTEX]]
    if joints[:2] != [0, 1]:
        raise ValueError("negative-control vertex joint identity drift")
    step = NEGATIVE_CONTROL_U16_STEPS / 65535.0
    if mutated[NEGATIVE_CONTROL_VERTEX][0] <= step:
        raise ValueError("negative-control parent weight is too small")
    mutated[NEGATIVE_CONTROL_VERTEX][0] -= step
    mutated[NEGATIVE_CONTROL_VERTEX][1] += step
    negative_frame = _frame(control, candidate, NEGATIVE_CONTROL_TIME_S, mutated_candidate_weights=mutated)
    negative_signal = float(negative_frame["max_control_candidate_position_delta_m"])
    negative_rejected = negative_signal > rig_bound

    gate = (
        dense_max <= rig_bound
        and authored_max_residual <= POSITION_COMPARE_EPS_M
        and time_mirror_residual <= MIRROR_EPS_M
        and control_loop <= LOOP_EPS_M
        and candidate_loop <= LOOP_EPS_M
        and negative_rejected
    )

    report = {
        "schema": SCHEMA,
        "state": "PASS_U16_WEIGHT_SUBFRAME_TRAJECTORY_WITHIN_RIGGING_BOUND" if gate else "HOLD_U16_WEIGHT_SUBFRAME_TRAJECTORY",
        "current_animation_head": current_animation_head,
        "animation_clip_digest": ANIMATION_CLIP_DIGEST,
        "motion_identity_changed": False,
        "runtime_dependency": {
            "head": RUNTIME_HEAD,
            "artifact_id": RUNTIME_ARTIFACT_ID,
            "artifact_sha256": RUNTIME_ARTIFACT_SHA256,
            "control_glb_sha256": CONTROL_GLB_SHA256,
            "candidate_glb_sha256": CANDIDATE_GLB_SHA256,
        },
        "rigging_dependency": {
            "head": RIGGING_HEAD,
            "artifact_id": RIGGING_ARTIFACT_ID,
            "artifact_sha256": RIGGING_ARTIFACT_SHA256,
            "state": EXPECTED_RIGGING_STATE,
            "authored_key_bound_m": rig_bound,
            "authored_key_max_delta_m": rig_authored_max,
        },
        "transport_interpolation": {
            "channel": "rotation",
            "gltf_interpolation": "LINEAR quaternion slerp",
            "duration_s": 1.0,
            "authored_keys": 41,
            "authored_rate_hz": 40,
            "subframes_per_authored_interval": SUBFRAMES_PER_AUTHORED_INTERVAL,
            "dense_rate_hz": DENSE_RATE_HZ,
            "dense_sample_count": DENSE_SAMPLE_COUNT,
        },
        "metrics": {
            "dense_max_control_candidate_position_delta_m": dense_max,
            "dense_max_sample_index": dense_max_index,
            "dense_max_time_s": rows[dense_max_index]["time_s"],
            "dense_max_vertex": rows[dense_max_index]["max_delta_vertex"],
            "authored_recomputed_max_delta_m": authored_max,
            "authored_recomputed_vs_rigging_receipt_residual_m": authored_max_residual,
            "maximum_time_mirror_error_series_residual_m": time_mirror_residual,
            "control_loop_position_residual_m": control_loop,
            "candidate_loop_position_residual_m": candidate_loop,
        },
        "negative_control": {
            "mutation": f"verifier-only +{NEGATIVE_CONTROL_U16_STEPS} u16 child-weight steps with equal parent subtraction at render vertex {NEGATIVE_CONTROL_VERTEX}",
            "time_s": NEGATIVE_CONTROL_TIME_S,
            "authored_key": False,
            "position_signal_m": negative_signal,
            "rigging_bound_m": rig_bound,
            "rejected": negative_rejected,
            "state": "PASS_FAILS_CLOSED_BETWEEN_AUTHORED_KEYS" if negative_rejected else "FAIL_NEGATIVE_CONTROL_NOT_DETECTED",
        },
        "preserved_hold": {
            "deformed_normal_tangent_direction_frame_equivalence": rigging_receipt.get("preserved_hold", {}).get("state"),
            "technical_art_producer_adoption": False,
            "art_direction_visual_qa_acceptance": False,
            "target_engine_interpolation_equivalence": False,
            "runtime_controller_gameplay_acceptance": False,
        },
        "truth_boundary": {
            "proves_if_green": "For the exact retained FLOAT-control and normalized-u16 Runtime GLBs, deterministic evaluation of the transported glTF LINEAR rotation channel at 321 samples / 320 Hz keeps the normalized-u16 skinned POSITION trajectory inside Rigging's existing 2e-7 m bound, preserves loop closure and time-symmetric error, and detects a material between-key weight mutation.",
            "does_not_prove": "Godot/target-engine interpolation implementation equivalence, production weight adoption, deformed NORMAL/TANGENT correctness, final visual acceptance, wall-clock frame delivery, controller/state-machine behavior, physics/collision/input/gameplay, target-device performance, CANON, production readiness, or mastery.",
        },
    }
    return report, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-glb", required=True)
    parser.add_argument("--candidate-glb", required=True)
    parser.add_argument("--rigging-receipt", required=True)
    parser.add_argument("--current-animation-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    control = Path(args.control_glb).read_bytes()
    candidate = Path(args.candidate_glb).read_bytes()
    receipt = json.loads(Path(args.rigging_receipt).read_text(encoding="utf-8"))
    report, rows = build_report(control, candidate, receipt, args.current_animation_head)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out / "dense-samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "summary.txt").write_text(
        "\n".join(
            [
                report["state"],
                f"animation_head={args.current_animation_head}",
                f"dense_samples={report['transport_interpolation']['dense_sample_count']}",
                f"dense_rate_hz={report['transport_interpolation']['dense_rate_hz']}",
                f"dense_max_position_delta_m={report['metrics']['dense_max_control_candidate_position_delta_m']}",
                f"rigging_bound_m={report['rigging_dependency']['authored_key_bound_m']}",
                f"time_mirror_residual_m={report['metrics']['maximum_time_mirror_error_series_residual_m']}",
                f"control_loop_residual_m={report['metrics']['control_loop_position_residual_m']}",
                f"candidate_loop_residual_m={report['metrics']['candidate_loop_position_residual_m']}",
                f"negative_control_signal_m={report['negative_control']['position_signal_m']}",
                f"negative_control_state={report['negative_control']['state']}",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["state"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
