#!/usr/bin/env python3
"""Build a bounded Godot AnimationPlayer interpolation witness from the exact retained Animal GLB.

This does not author or retime motion. It extracts the already-retained glTF LINEAR
rotation channel and emits exact authored keys plus a dense independently-computed
SLERP reference for target-host comparison.
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

SCHEMA = "axm.animal-animation-godot-quaternion-interpolation-payload/v0.1"
CANDIDATE_GLB_SHA256 = "81c5422f8cf13ca65a253d3b05ebcf88fc0b20601dfb466b3c92f0d5e28dafcb"
ANIMATION_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
RUNTIME_HEAD = "e7874c4a8dca1db48bc66f3546c2134f7d724456"
SAMPLES_PER_INTERVAL = 8
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
    component_type = int(accessor["componentType"])
    kind = str(accessor["type"])
    formats = {5126: ("f", 4)}
    widths = {"SCALAR": 1, "VEC4": 4}
    if component_type not in formats or kind not in widths:
        raise ValueError("unexpected animation accessor type")
    fmt, component_size = formats[component_type]
    width = widths[kind]
    packed = component_size * width
    stride = int(view.get("byteStride", packed))
    base = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    rows: list[Any] = []
    for row_index in range(int(accessor["count"])):
        values = list(struct.unpack_from("<" + fmt * width, binary, base + row_index * stride))
        rows.append(values[0] if width == 1 else values)
    return rows


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
    if time_s <= float(times[0]):
        return unit(quats[0])
    if time_s >= float(times[-1]):
        return unit(quats[-1])
    left = bisect.bisect_right(times, time_s) - 1
    t0 = float(times[left])
    t1 = float(times[left + 1])
    return slerp(quats[left], quats[left + 1], (time_s - t0) / (t1 - t0))


def build(candidate_glb: bytes, head: str) -> dict[str, Any]:
    digest = sha256_bytes(candidate_glb)
    if digest != CANDIDATE_GLB_SHA256:
        raise ValueError("exact Runtime normalized-u16 GLB SHA drift")
    document, binary = parse_glb(candidate_glb)
    animations = document.get("animations", [])
    if len(animations) != 1 or len(animations[0].get("channels", [])) != 1:
        raise ValueError("expected exact one-channel retained animation")
    channel = animations[0]["channels"][0]
    sampler = animations[0]["samplers"][int(channel["sampler"])]
    if channel.get("target", {}).get("path") != "rotation":
        raise ValueError("expected rotation channel")
    if sampler.get("interpolation") != "LINEAR":
        raise ValueError("expected exact glTF LINEAR interpolation")
    times = [float(v) for v in decode_accessor(document, binary, int(sampler["input"]))]
    quats = [[float(v) for v in row] for row in decode_accessor(document, binary, int(sampler["output"]))]
    if len(times) != 41 or len(quats) != 41:
        raise ValueError("authored key count drift")
    if abs(times[0]) > 1e-12 or abs(times[-1] - 1.0) > 1e-6:
        raise ValueError("clip duration drift")
    dense = []
    for sample_index in range(DENSE_SAMPLE_COUNT):
        time_s = sample_index / 320.0
        dense.append({
            "sample_index": sample_index,
            "time_s": time_s,
            "expected_quaternion_xyzw": rotation_at(times, quats, time_s),
            "authored_boundary": sample_index % SAMPLES_PER_INTERVAL == 0,
        })
    return {
        "schema": SCHEMA,
        "current_animation_head": head,
        "source_identity": {
            "runtime_head": RUNTIME_HEAD,
            "candidate_glb_sha256": digest,
            "clip_digest": ANIMATION_CLIP_DIGEST,
            "duration_s": 1.0,
            "authored_rate_hz": 40,
            "authored_key_count": 41,
            "interpolation": "glTF_LINEAR_ROTATION_SLERP_REFERENCE",
            "motion_changed": False,
            "retimed": False,
        },
        "authored_keys": [
            {"index": i, "time_s": times[i], "quaternion_xyzw": unit(quats[i])}
            for i in range(41)
        ],
        "dense_reference": {
            "diagnostic_rate_hz": 320,
            "samples_per_authored_interval": SAMPLES_PER_INTERVAL,
            "sample_count": DENSE_SAMPLE_COUNT,
            "samples": dense,
        },
        "truth_boundary": (
            "Reference-only payload for comparing pinned Godot AnimationPlayer quaternion interpolation against the exact retained glTF LINEAR rotation channel. "
            "It does not claim wall-clock cadence, renderer delivery, Runtime controller/state-machine behavior, gameplay, target-device performance, Art/QA acceptance, CANON or production readiness."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-glb", required=True)
    parser.add_argument("--current-animation-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    payload = build(Path(args.candidate_glb).read_bytes(), args.current_animation_head)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": "PASS_GODOT_QUATERNION_INTERPOLATION_REFERENCE_READY", "payload_sha256": sha256_bytes(out.read_bytes()), "samples": DENSE_SAMPLE_COUNT}, indent=2))


if __name__ == "__main__":
    main()
