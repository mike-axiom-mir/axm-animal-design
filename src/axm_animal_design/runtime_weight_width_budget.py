"""Bounded Runtime A/B for compact glTF skin weights.

Rewrites only one non-interleaved FLOAT VEC4 WEIGHTS_0 accessor to normalized
UNSIGNED_SHORT VEC4. Every unrelated accessor payload is required to remain
byte-identical. Technical Art retains producer/adoption authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import struct
from dataclasses import dataclass
from typing import Any

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT = 5126
UNSIGNED_SHORT = 5123
ARRAY_BUFFER = 34962
MAX_U16 = 65535


@dataclass(frozen=True)
class Parts:
    document: dict[str, Any]
    binary: bytes


@dataclass(frozen=True)
class WeightCompaction:
    candidate_bytes: bytes
    accessor_index: int
    control_rows: list[list[float]]
    candidate_rows: list[list[float]]
    quantized_rows: list[list[int]]
    control_payload_bytes: int
    candidate_payload_bytes: int
    max_abs_weight_error: float
    max_row_sum_error: float
    non_weight_hashes_identical: bool


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _pad4(value: bytes, fill: bytes) -> bytes:
    return value + fill * ((-len(value)) % 4)


def parse_glb(value: bytes) -> Parts:
    if len(value) < 20:
        raise ValueError("GLB too small")
    magic, version, total = struct.unpack_from("<4sII", value, 0)
    if magic != b"glTF" or version != 2 or total != len(value):
        raise ValueError("GLB header drift")
    offset = 12
    chunks: list[tuple[int, bytes]] = []
    while offset < len(value):
        length, kind = struct.unpack_from("<II", value, offset)
        offset += 8
        end = offset + length
        if end > len(value):
            raise ValueError("truncated GLB chunk")
        chunks.append((kind, value[offset:end]))
        offset = end
    if len(chunks) != 2 or chunks[0][0] != JSON_CHUNK or chunks[1][0] != BIN_CHUNK:
        raise ValueError("bounded path requires exactly JSON + BIN chunks")
    document = json.loads(chunks[0][1].rstrip(b" \t\r\n\x00").decode("utf-8"))
    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise ValueError("bounded path requires one buffer")
    declared = int(buffers[0].get("byteLength", -1))
    binary = bytes(chunks[1][1])
    if declared < 0 or declared > len(binary) or len(binary) - declared > 3:
        raise ValueError("buffer byteLength drift")
    return Parts(document=document, binary=binary[:declared])


def pack_glb(document: dict[str, Any], binary: bytes) -> bytes:
    doc = copy.deepcopy(document)
    doc["buffers"][0]["byteLength"] = len(binary)
    json_bytes = _pad4(json.dumps(doc, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8"), b" ")
    bin_bytes = _pad4(binary, b"\x00")
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    return struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(json_bytes), JSON_CHUNK) + json_bytes + struct.pack("<II", len(bin_bytes), BIN_CHUNK) + bin_bytes


def _component_size(component_type: int) -> int:
    return {5121: 1, 5123: 2, 5125: 4, 5126: 4}.get(component_type) or (_ for _ in ()).throw(ValueError(f"unsupported componentType {component_type}"))


def _type_width(kind: str) -> int:
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
    if kind not in widths:
        raise ValueError(f"unsupported accessor type {kind}")
    return widths[kind]


def accessor_payload(parts: Parts, accessor_index: int) -> bytes:
    accessor = parts.document["accessors"][accessor_index]
    view = parts.document["bufferViews"][int(accessor["bufferView"])]
    component_size = _component_size(int(accessor["componentType"]))
    width = _type_width(str(accessor["type"]))
    stride = int(view.get("byteStride", component_size * width))
    if stride != component_size * width:
        raise ValueError("interleaved accessors are outside this bounded path")
    length = int(accessor["count"]) * width * component_size
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    end = start + length
    if start < 0 or end > len(parts.binary):
        raise ValueError("accessor lies outside buffer")
    return parts.binary[start:end]


def decode_weights(parts: Parts, accessor_index: int) -> list[list[float]]:
    accessor = parts.document["accessors"][accessor_index]
    width = _type_width(str(accessor["type"]))
    count = int(accessor["count"])
    component = int(accessor["componentType"])
    payload = accessor_payload(parts, accessor_index)
    if component == FLOAT:
        flat = [float(v) for v in struct.unpack("<" + "f" * count * width, payload)]
    elif component == UNSIGNED_SHORT and accessor.get("normalized") is True:
        flat = [float(v) / MAX_U16 for v in struct.unpack("<" + "H" * count * width, payload)]
    else:
        raise ValueError("unsupported WEIGHTS_0 decode contract")
    return [flat[index:index + width] for index in range(0, len(flat), width)]


def quantize_weight_row_u16(row: list[float]) -> list[int]:
    if len(row) != 4 or any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in row):
        raise ValueError("WEIGHTS_0 row must contain four finite values in 0..1")
    total = sum(row)
    if abs(total - 1.0) > 1e-5:
        raise ValueError(f"WEIGHTS_0 row sum drift: {total}")
    normalized = [value / total for value in row]
    scaled = [value * MAX_U16 for value in normalized]
    base = [int(math.floor(value)) for value in scaled]
    remainder = MAX_U16 - sum(base)
    order = sorted(range(4), key=lambda index: (scaled[index] - base[index], -index), reverse=True)
    for index in order[:remainder]:
        base[index] += 1
    if sum(base) != MAX_U16:
        raise ValueError("quantized row failed exact integer-sum contract")
    return base


def compact_weights_0_to_normalized_u16(control_bytes: bytes) -> WeightCompaction:
    control = parse_glb(control_bytes)
    meshes = control.document.get("meshes")
    if not isinstance(meshes, list) or len(meshes) != 1 or len(meshes[0].get("primitives", [])) != 1:
        raise ValueError("bounded path requires one mesh and one primitive")
    primitive = meshes[0]["primitives"][0]
    attributes = primitive.get("attributes")
    if not isinstance(attributes, dict) or "WEIGHTS_0" not in attributes:
        raise ValueError("missing WEIGHTS_0")
    accessor_index = int(attributes["WEIGHTS_0"])
    accessor = control.document["accessors"][accessor_index]
    if int(accessor.get("componentType", -1)) != FLOAT or str(accessor.get("type")) != "VEC4" or bool(accessor.get("normalized", False)):
        raise ValueError("control WEIGHTS_0 must be non-normalized FLOAT VEC4")
    if int(accessor.get("byteOffset", 0)) != 0:
        raise ValueError("bounded path requires zero accessor byteOffset")
    view_index = int(accessor["bufferView"])
    view = control.document["bufferViews"][view_index]
    if int(view.get("target", ARRAY_BUFFER)) != ARRAY_BUFFER or "byteStride" in view:
        raise ValueError("bounded path requires non-interleaved ARRAY_BUFFER weights")

    control_rows = decode_weights(control, accessor_index)
    quantized_rows = [quantize_weight_row_u16(row) for row in control_rows]
    raw = struct.pack("<" + "H" * len(quantized_rows) * 4, *[value for row in quantized_rows for value in row])

    candidate_doc = copy.deepcopy(control.document)
    candidate_accessor = candidate_doc["accessors"][accessor_index]
    candidate_accessor["componentType"] = UNSIGNED_SHORT
    candidate_accessor["normalized"] = True

    rebuilt = bytearray()
    previous_end = 0
    for index, source_view in enumerate(control.document["bufferViews"]):
        start = int(source_view.get("byteOffset", 0))
        length = int(source_view.get("byteLength", -1))
        if start < previous_end or length < 0:
            raise ValueError("overlapping/out-of-order bufferViews are outside this bounded path")
        source = raw if index == view_index else control.binary[start:start + length]
        candidate_doc["bufferViews"][index]["byteOffset"] = len(rebuilt)
        candidate_doc["bufferViews"][index]["byteLength"] = len(source)
        rebuilt.extend(source)
        rebuilt.extend(b"\x00" * ((-len(rebuilt)) % 4))
        previous_end = start + length

    candidate_bytes = pack_glb(candidate_doc, bytes(rebuilt))
    candidate = parse_glb(candidate_bytes)
    candidate_rows = decode_weights(candidate, accessor_index)
    max_error = max(abs(left - right) for control_row, candidate_row in zip(control_rows, candidate_rows) for left, right in zip(control_row, candidate_row))
    max_sum_error = max(abs(sum(row) - 1.0) for row in candidate_rows)

    def hashes(parts: Parts) -> dict[int, str]:
        return {index: sha256_bytes(accessor_payload(parts, index)) for index in range(len(parts.document["accessors"])) if index != accessor_index}

    identical = hashes(control) == hashes(candidate)
    if not identical:
        raise ValueError("non-WEIGHTS accessor payload changed")
    return WeightCompaction(
        candidate_bytes=candidate_bytes,
        accessor_index=accessor_index,
        control_rows=control_rows,
        candidate_rows=candidate_rows,
        quantized_rows=quantized_rows,
        control_payload_bytes=len(accessor_payload(control, accessor_index)),
        candidate_payload_bytes=len(raw),
        max_abs_weight_error=max_error,
        max_row_sum_error=max_sum_error,
        non_weight_hashes_identical=identical,
    )
