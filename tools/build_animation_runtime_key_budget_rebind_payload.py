#!/usr/bin/env python3
"""Build exact Animation-owned evidence for Runtime's 19-key Animal representation.

This does not author, retime, simplify, or adopt motion. It compares the exact
41-key Animation control against the exact 19-key Runtime representation and
keeps Runtime's quaternion-space error metric separate from the physical
rotation delta exposed by the current Rigging receiver.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any

SCHEMA = "axm.animal-animation-runtime-key-budget-rebind-payload/v0.1"
CONTROL_GLB_SHA256 = "81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb"
CANDIDATE_GLB_SHA256 = "a8a32b58ad3bad44176a676b00f5cf1c20d1a2ec6da275b683d8f73a69088d6b"
ANIMATION_PREDECESSOR_HEAD = "eb21e0e0fd888bbb5fa41c73a6c0f1c731f662c2"
ANIMATION_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
RUNTIME_HEAD = "13ba20d198d2b7c5e428167745d59927b3084004"
RUNTIME_ARTIFACT_ID = 10525970648
RUNTIME_ARTIFACT_SHA256 = "ad071f58796b606d707168af9619d988a497ba1a745dda8ac62b42e7f814b996"
RIGGING_HEAD = "0bdddceb1ccac52732d0a2c71e877a8f31976305"
RIGGING_ARTIFACT_ID = 10544932693
RIGGING_ARTIFACT_SHA256 = "36b870c7a3fd4c609fd4a1af2d03e444e8004422541a5809607650a45547f485"
RUNTIME_DECLARED_TOLERANCE_DEG = 0.075
EXPECTED_RUNTIME_HALF_ANGLE_MAX_DEG = 0.05472043982868231
EXPECTED_PHYSICAL_ROTATION_MAX_DEG = 0.10944087965736671
EXPECTED_WORST_SAMPLE_INDEX = 152
DENSE_RATE_HZ = 320
DENSE_SAMPLE_COUNT = 321


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_glb(data: bytes) -> tuple[dict[str, Any], bytes]:
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("GLB header drift")
    offset = 12
    document = None
    binary = None
    while offset + 8 <= len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        payload = data[offset:offset + length]
        offset += length
        if kind == b"JSON":
            document = json.loads(payload.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif kind in (b"BIN\x00", b"BIN "):
            binary = payload
    if not isinstance(document, dict) or binary is None:
        raise ValueError("GLB chunks missing")
    return document, binary


def decode_accessor(document: dict[str, Any], binary: bytes, index: int) -> list[Any]:
    accessor = document["accessors"][index]
    view = document["bufferViews"][int(accessor["bufferView"])]
    if accessor.get("sparse") is not None:
        raise ValueError("sparse animation accessor unsupported")
    if int(accessor["componentType"]) != 5126:
        raise ValueError("animation accessor must be FLOAT")
    widths = {"SCALAR": 1, "VEC4": 4}
    width = widths.get(str(accessor["type"]))
    if width is None:
        raise ValueError("unexpected animation accessor type")
    packed = 4 * width
    stride = int(view.get("byteStride", packed))
    if stride != packed:
        raise ValueError("interleaved animation accessor unsupported")
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    rows: list[Any] = []
    for row_index in range(int(accessor["count"])):
        values = list(struct.unpack_from("<" + "f" * width, binary, base + row_index * stride))
        rows.append(values[0] if width == 1 else values)
    return rows


def extract_rotation_channel(data: bytes, expected_sha: str, expected_keys: int) -> tuple[list[float], list[list[float]]]:
    digest = sha256_bytes(data)
    if digest != expected_sha:
        raise ValueError(f"exact GLB identity drift: {digest}")
    document, binary = parse_glb(data)
    animations = document.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected exact one-channel animation")
    channel = animations[0]["channels"][0]
    sampler = animations[0]["samplers"][int(channel["sampler"])]
    if channel.get("target", {}).get("path") != "rotation":
        raise ValueError("expected rotation channel")
    if sampler.get("interpolation") != "LINEAR":
        raise ValueError("expected exact glTF LINEAR interpolation")
    times = [float(value) for value in decode_accessor(document, binary, int(sampler["input"]))]
    quats = [[float(v) for v in row] for row in decode_accessor(document, binary, int(sampler["output"]))]
    if len(times) != expected_keys or len(quats) != expected_keys:
        raise ValueError("animation key count drift")
    if abs(times[0]) > 1e-12 or abs(times[-1] - 1.0) > 1e-6:
        raise ValueError("clip duration drift")
    for a, b in zip(times, times[1:]):
        if not b > a:
            raise ValueError("animation key times not strictly increasing")
    return times, quats


def unit(q: list[float]) -> list[float]:
    length = math.sqrt(sum(float(v) * float(v) for v in q))
    if length <= 1e-15:
        raise ValueError("zero quaternion")
    return [float(v) / length for v in q]


def dot(a: list[float], b: list[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def slerp(a: list[float], b: list[float], alpha: float) -> list[float]:
    qa = unit(a)
    qb = unit(b)
    d = dot(qa, qb)
    if d < 0.0:
        qb = [-v for v in qb]
        d = -d
    d = max(-1.0, min(1.0, d))
    if d > 0.9995:
        return unit([(1.0 - alpha) * qa[i] + alpha * qb[i] for i in range(4)])
    theta = math.acos(d)
    sin_theta = math.sin(theta)
    return [
        math.sin((1.0 - alpha) * theta) / sin_theta * qa[i]
        + math.sin(alpha * theta) / sin_theta * qb[i]
        for i in range(4)
    ]


def rotation_at(times: list[float], quats: list[list[float]], time_s: float) -> list[float]:
    if time_s <= times[0]:
        return unit(quats[0])
    if time_s >= times[-1]:
        return unit(quats[-1])
    left = bisect.bisect_right(times, time_s) - 1
    alpha = (time_s - times[left]) / (times[left + 1] - times[left])
    return slerp(quats[left], quats[left + 1], alpha)


def quaternion_chord(a: list[float], b: list[float]) -> float:
    qa = unit(a)
    qb = unit(b)
    direct = math.sqrt(sum((qa[i] - qb[i]) ** 2 for i in range(4)))
    negated = math.sqrt(sum((qa[i] + qb[i]) ** 2 for i in range(4)))
    return min(direct, negated)


def runtime_half_angle_deg(a: list[float], b: list[float]) -> float:
    chord = min(2.0, quaternion_chord(a, b))
    return math.degrees(2.0 * math.asin(chord * 0.5))


def physical_rotation_deg(a: list[float], b: list[float]) -> float:
    # For unit quaternions the shortest physical relative-rotation angle is
    # exactly twice Runtime's retained qerr metric used by PR #30.
    return 2.0 * runtime_half_angle_deg(a, b)


def build(control_data: bytes, candidate_data: bytes, current_animation_head: str) -> dict[str, Any]:
    if current_animation_head == ANIMATION_PREDECESSOR_HEAD:
        raise ValueError("current Animation head did not advance")
    control_times, control_quats = extract_rotation_channel(control_data, CONTROL_GLB_SHA256, 41)
    candidate_times, candidate_quats = extract_rotation_channel(candidate_data, CANDIDATE_GLB_SHA256, 19)
    if not any(abs(t - 0.5) <= 1e-7 for t in candidate_times):
        raise ValueError("Runtime candidate no longer retains the exact peak key")

    samples = []
    max_half = -1.0
    max_physical = -1.0
    worst_index = -1
    for sample_index in range(DENSE_SAMPLE_COUNT):
        time_s = sample_index / float(DENSE_RATE_HZ)
        control = rotation_at(control_times, control_quats, time_s)
        candidate = rotation_at(candidate_times, candidate_quats, time_s)
        half = runtime_half_angle_deg(control, candidate)
        physical = physical_rotation_deg(control, candidate)
        if physical > max_physical:
            max_physical = physical
            max_half = half
            worst_index = sample_index
        samples.append({
            "sample_index": sample_index,
            "time_s": time_s,
            "control_quaternion_xyzw": control,
            "candidate_quaternion_xyzw": candidate,
            "runtime_half_angle_metric_deg": half,
            "physical_relative_rotation_deg": physical,
            "authored_control_boundary": sample_index % 8 == 0,
        })

    peak_sample = samples[160]
    if worst_index != EXPECTED_WORST_SAMPLE_INDEX:
        raise ValueError(f"worst sample drift: {worst_index}")
    if abs(max_half - EXPECTED_RUNTIME_HALF_ANGLE_MAX_DEG) > 1e-10:
        raise ValueError(f"Runtime metric reproduction drift: {max_half}")
    if abs(max_physical - EXPECTED_PHYSICAL_ROTATION_MAX_DEG) > 2e-10:
        raise ValueError(f"physical rotation reproduction drift: {max_physical}")
    if peak_sample["physical_relative_rotation_deg"] > 1e-10:
        raise ValueError("retained peak key no longer closes exactly")
    if not max_half < RUNTIME_DECLARED_TOLERANCE_DEG:
        raise ValueError("expected Runtime half-angle metric to remain below declared threshold")
    if not max_physical > RUNTIME_DECLARED_TOLERANCE_DEG:
        raise ValueError("expected physical owner angle to remain above nominal threshold")

    return {
        "schema": SCHEMA,
        "state": "HOLD_RUNTIME_19_KEY_ANIMATION_REBIND__REFERENCE_BUILT__OWNER_ANGLE_SEMANTICS_UNRESOLVED",
        "current_animation_head": current_animation_head,
        "source_identity": {
            "animation_predecessor_head": ANIMATION_PREDECESSOR_HEAD,
            "clip_digest": ANIMATION_CLIP_DIGEST,
            "runtime_head": RUNTIME_HEAD,
            "runtime_artifact_id": RUNTIME_ARTIFACT_ID,
            "runtime_artifact_sha256": RUNTIME_ARTIFACT_SHA256,
            "rigging_head": RIGGING_HEAD,
            "rigging_artifact_id": RIGGING_ARTIFACT_ID,
            "rigging_artifact_sha256": RIGGING_ARTIFACT_SHA256,
            "control_glb_sha256": CONTROL_GLB_SHA256,
            "candidate_glb_sha256": CANDIDATE_GLB_SHA256,
            "control_keys": 41,
            "candidate_keys": 19,
            "duration_s": 1.0,
            "source_authored_rate_hz": 40,
            "interpolation": "glTF_LINEAR_ROTATION",
            "motion_retimed": False,
            "source_authored_keys_modified": False,
            "runtime_candidate_modified": False,
        },
        "metric_semantics": {
            "runtime_declared_tolerance_deg": RUNTIME_DECLARED_TOLERANCE_DEG,
            "runtime_metric_name_here": "QUATERNION_SHORTEST_CHORD_HALF_ANGLE_DEG",
            "runtime_metric_max_deg": max_half,
            "physical_relative_rotation_max_deg": max_physical,
            "physical_is_two_times_runtime_metric_for_unit_quaternions": True,
            "worst_sample_index": worst_index,
            "worst_time_s": worst_index / float(DENSE_RATE_HZ),
            "runtime_metric_below_declared_tolerance": max_half < RUNTIME_DECLARED_TOLERANCE_DEG,
            "physical_rotation_above_same_numeric_tolerance": max_physical > RUNTIME_DECLARED_TOLERANCE_DEG,
            "animation_representation_adopted": False,
            "owner_angle_semantics_resolved": False,
        },
        "control_keys": [
            {"index": i, "time_s": control_times[i], "quaternion_xyzw": unit(control_quats[i])}
            for i in range(len(control_times))
        ],
        "candidate_keys": [
            {"index": i, "time_s": candidate_times[i], "quaternion_xyzw": unit(candidate_quats[i])}
            for i in range(len(candidate_times))
        ],
        "dense_reference": {
            "diagnostic_rate_hz": DENSE_RATE_HZ,
            "sample_count": DENSE_SAMPLE_COUNT,
            "samples_per_source_interval": 8,
            "samples": samples,
        },
        "truth_boundary": (
            "Animation-owned comparison of the exact 41-key source representation and exact Runtime 19-key storage candidate. "
            "It preserves the source clip and distinguishes Runtime's retained quaternion half-angle metric from the physical relative-rotation angle. "
            "It does not adopt the Runtime candidate, resolve Rigging/Runtime tolerance policy, or claim wall-clock pacing, Runtime controller/state-machine/input behavior, gameplay, collision/physics, target-device performance, Art/QA acceptance, CANON or production readiness."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-glb", required=True)
    parser.add_argument("--candidate-glb", required=True)
    parser.add_argument("--current-animation-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = build(
        Path(args.control_glb).read_bytes(),
        Path(args.candidate_glb).read_bytes(),
        args.current_animation_head,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "state": payload["state"],
        "payload_sha256": sha256_bytes(out.read_bytes()),
        "runtime_half_angle_max_deg": payload["metric_semantics"]["runtime_metric_max_deg"],
        "physical_relative_rotation_max_deg": payload["metric_semantics"]["physical_relative_rotation_max_deg"],
    }, indent=2))


if __name__ == "__main__":
    main()
