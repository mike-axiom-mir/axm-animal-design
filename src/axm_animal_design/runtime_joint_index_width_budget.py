"""Runtime-only GLB joint-index width compactor.

This module does not author rig semantics, weights, animation, topology, UVs,
normals, tangents or materials. It consumes an already-valid GLB and, when the
JOINTS_0 domain is provably <= 255, rebuilds only that accessor from
UNSIGNED_SHORT to UNSIGNED_BYTE while preserving every decoded joint index and
all non-joint buffer-view payloads byte-for-byte.

The optimization is intentionally bounded. Technical Art retains transport
ownership and must explicitly adopt any storage change; Runtime only measures a
candidate representation and fails closed when the joint domain is too large or
unexpected glTF packing is encountered.
"""
from __future__ import annotations

import copy
import hashlib
import json
import struct
from dataclasses import dataclass
from typing import Any

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
UNSIGNED_BYTE = 5121
UNSIGNED_SHORT = 5123
ARRAY_BUFFER = 34962


@dataclass(frozen=True)
class GlbParts:
    document: dict[str, Any]
    binary: bytes


@dataclass(frozen=True)
class JointIndexCompaction:
    control_bytes: bytes
    candidate_bytes: bytes
    control_document: dict[str, Any]
    candidate_document: dict[str, Any]
    accessor_index: int
    buffer_view_index: int
    joint_rows: list[list[int]]
    non_joint_accessor_hashes_control: dict[str, str]
    non_joint_accessor_hashes_candidate: dict[str, str]
    control_joint_payload_bytes: int
    candidate_joint_payload_bytes: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pad4(data: bytes, fill: bytes) -> bytes:
    remainder = len(data) % 4
    if remainder == 0:
        return data
    return data + fill * (4 - remainder)


def parse_glb(data: bytes) -> GlbParts:
    if len(data) < 20:
        raise ValueError("GLB is too small")
    magic, version, total_length = struct.unpack_from("<4sII", data, 0)
    if magic != GLB_MAGIC or version != GLB_VERSION or total_length != len(data):
        raise ValueError("GLB header drift")
    offset = 12
    chunks: list[tuple[int, bytes]] = []
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError("truncated GLB chunk header")
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        end = offset + chunk_length
        if end > len(data):
            raise ValueError("truncated GLB chunk payload")
        chunks.append((chunk_type, data[offset:end]))
        offset = end
    if len(chunks) != 2 or chunks[0][0] != JSON_CHUNK or chunks[1][0] != BIN_CHUNK:
        raise ValueError("expected exactly one JSON chunk followed by one BIN chunk")
    try:
        document = json.loads(chunks[0][1].rstrip(b" \t\r\n\x00").decode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ValueError("invalid GLB JSON chunk") from exc
    if not isinstance(document, dict):
        raise ValueError("GLB JSON root must be an object")
    binary = bytes(chunks[1][1])
    buffers = document.get("buffers")
    if not isinstance(buffers, list) or len(buffers) != 1:
        raise ValueError("bounded compactor requires exactly one GLB buffer")
    declared = int(buffers[0].get("byteLength", -1))
    if declared < 0 or declared > len(binary) or len(binary) - declared > 3:
        raise ValueError("GLB buffer byteLength drift")
    return GlbParts(document=document, binary=binary[:declared])


def pack_glb(document: dict[str, Any], binary: bytes) -> bytes:
    doc = copy.deepcopy(document)
    if not isinstance(doc.get("buffers"), list) or len(doc["buffers"]) != 1:
        raise ValueError("bounded packer requires exactly one buffer")
    doc["buffers"][0]["byteLength"] = len(binary)
    json_bytes = json.dumps(doc, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    json_chunk = _pad4(json_bytes, b" ")
    bin_chunk = _pad4(binary, b"\x00")
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return (
        struct.pack("<4sII", GLB_MAGIC, GLB_VERSION, total)
        + struct.pack("<II", len(json_chunk), JSON_CHUNK)
        + json_chunk
        + struct.pack("<II", len(bin_chunk), BIN_CHUNK)
        + bin_chunk
    )


def _component_layout(component_type: int) -> tuple[str, int]:
    layouts = {
        5120: ("b", 1),
        5121: ("B", 1),
        5122: ("h", 2),
        5123: ("H", 2),
        5125: ("I", 4),
        5126: ("f", 4),
    }
    if component_type not in layouts:
        raise ValueError(f"unsupported glTF componentType {component_type}")
    return layouts[component_type]


def _type_width(kind: str) -> int:
    widths = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
    if kind not in widths:
        raise ValueError(f"unsupported glTF accessor type {kind}")
    return widths[kind]


def accessor_payload(parts: GlbParts, accessor_index: int) -> bytes:
    accessors = parts.document.get("accessors")
    views = parts.document.get("bufferViews")
    if not isinstance(accessors, list) or not isinstance(views, list):
        raise ValueError("GLB accessors/bufferViews missing")
    if not 0 <= accessor_index < len(accessors):
        raise ValueError("accessor index out of range")
    accessor = accessors[accessor_index]
    view_index = int(accessor.get("bufferView", -1))
    if not 0 <= view_index < len(views):
        raise ValueError("accessor bufferView out of range")
    view = views[view_index]
    if int(view.get("buffer", 0)) != 0:
        raise ValueError("bounded compactor supports buffer 0 only")
    _, component_size = _component_layout(int(accessor["componentType"]))
    element_width = _type_width(str(accessor["type"]))
    count = int(accessor["count"])
    byte_length = component_size * element_width * count
    stride = int(view.get("byteStride", byte_length if count == 1 else component_size * element_width))
    if stride != component_size * element_width:
        raise ValueError("interleaved/strided accessors are outside this bounded compactor")
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    end = start + byte_length
    if start < 0 or end > len(parts.binary):
        raise ValueError("accessor payload lies outside GLB binary buffer")
    return parts.binary[start:end]


def decode_accessor(parts: GlbParts, accessor_index: int) -> list[list[int | float]]:
    accessor = parts.document["accessors"][accessor_index]
    fmt, _ = _component_layout(int(accessor["componentType"]))
    width = _type_width(str(accessor["type"]))
    count = int(accessor["count"])
    payload = accessor_payload(parts, accessor_index)
    flat = struct.unpack("<" + fmt * count * width, payload)
    return [list(flat[offset:offset + width]) for offset in range(0, len(flat), width)]


def _primitive(document: dict[str, Any]) -> dict[str, Any]:
    meshes = document.get("meshes")
    if not isinstance(meshes, list) or len(meshes) != 1:
        raise ValueError("bounded compactor requires exactly one mesh")
    primitives = meshes[0].get("primitives")
    if not isinstance(primitives, list) or len(primitives) != 1:
        raise ValueError("bounded compactor requires exactly one primitive")
    primitive = primitives[0]
    if not isinstance(primitive, dict):
        raise ValueError("primitive must be an object")
    return primitive


def _buffer_view_slice(parts: GlbParts, index: int) -> bytes:
    views = parts.document.get("bufferViews")
    if not isinstance(views, list) or not 0 <= index < len(views):
        raise ValueError("bufferView index out of range")
    view = views[index]
    if int(view.get("buffer", 0)) != 0:
        raise ValueError("bounded compactor supports buffer 0 only")
    start = int(view.get("byteOffset", 0))
    length = int(view.get("byteLength", -1))
    end = start + length
    if start < 0 or length < 0 or end > len(parts.binary):
        raise ValueError("bufferView lies outside GLB binary buffer")
    return parts.binary[start:end]


def _non_joint_accessor_hashes(parts: GlbParts, joint_accessor: int) -> dict[str, str]:
    output: dict[str, str] = {}
    for index, _accessor in enumerate(parts.document.get("accessors", [])):
        if index == joint_accessor:
            continue
        output[str(index)] = sha256_bytes(accessor_payload(parts, index))
    return output


def compact_joints_0_to_unsigned_byte(control_bytes: bytes) -> JointIndexCompaction:
    control = parse_glb(control_bytes)
    primitive = _primitive(control.document)
    attributes = primitive.get("attributes")
    if not isinstance(attributes, dict) or "JOINTS_0" not in attributes:
        raise ValueError("primitive has no JOINTS_0 accessor")
    accessor_index = int(attributes["JOINTS_0"])
    accessors = control.document.get("accessors")
    views = control.document.get("bufferViews")
    if not isinstance(accessors, list) or not isinstance(views, list):
        raise ValueError("GLB accessor tables missing")
    accessor = accessors[accessor_index]
    if int(accessor.get("componentType", -1)) != UNSIGNED_SHORT:
        raise ValueError("control JOINTS_0 must be UNSIGNED_SHORT for this bounded A/B")
    if str(accessor.get("type")) != "VEC4" or bool(accessor.get("normalized", False)):
        raise ValueError("JOINTS_0 must be non-normalized VEC4")
    if int(accessor.get("byteOffset", 0)) != 0:
        raise ValueError("JOINTS_0 accessor byteOffset must be zero in this bounded A/B")
    view_index = int(accessor.get("bufferView", -1))
    if not 0 <= view_index < len(views):
        raise ValueError("JOINTS_0 bufferView missing")
    joint_view = views[view_index]
    if int(joint_view.get("target", ARRAY_BUFFER)) != ARRAY_BUFFER:
        raise ValueError("JOINTS_0 bufferView target drift")
    if "byteStride" in joint_view:
        raise ValueError("interleaved JOINTS_0 is outside this bounded A/B")

    decoded = decode_accessor(control, accessor_index)
    joint_rows = [[int(value) for value in row] for row in decoded]
    flat = [value for row in joint_rows for value in row]
    if not flat or min(flat) < 0:
        raise ValueError("JOINTS_0 contains a negative joint index")
    if max(flat) > 255:
        raise ValueError("JOINTS_0 exceeds UNSIGNED_BYTE domain")
    control_joint_payload = accessor_payload(control, accessor_index)
    expected_control_bytes = len(flat) * 2
    if len(control_joint_payload) != expected_control_bytes:
        raise ValueError("JOINTS_0 UNSIGNED_SHORT payload length drift")
    candidate_joint_payload = struct.pack("<" + "B" * len(flat), *flat)

    candidate_document = copy.deepcopy(control.document)
    candidate_document["accessors"][accessor_index]["componentType"] = UNSIGNED_BYTE

    original_views = control.document["bufferViews"]
    candidate_views = candidate_document["bufferViews"]
    rebuilt = bytearray()
    previous_end = 0
    for index, view in enumerate(original_views):
        start = int(view.get("byteOffset", 0))
        length = int(view.get("byteLength", -1))
        if start < previous_end:
            raise ValueError("overlapping or out-of-order bufferViews are outside this bounded A/B")
        if length < 0:
            raise ValueError("bufferView byteLength missing")
        raw = candidate_joint_payload if index == view_index else _buffer_view_slice(control, index)
        candidate_views[index]["byteOffset"] = len(rebuilt)
        candidate_views[index]["byteLength"] = len(raw)
        rebuilt.extend(raw)
        while len(rebuilt) % 4:
            rebuilt.append(0)
        previous_end = start + length

    candidate_binary = bytes(rebuilt)
    candidate_document["buffers"][0]["byteLength"] = len(candidate_binary)
    candidate_bytes = pack_glb(candidate_document, candidate_binary)
    candidate = parse_glb(candidate_bytes)

    candidate_rows = [[int(value) for value in row] for row in decode_accessor(candidate, accessor_index)]
    if candidate_rows != joint_rows:
        raise ValueError("JOINTS_0 decoded values changed during compaction")
    control_hashes = _non_joint_accessor_hashes(control, accessor_index)
    candidate_hashes = _non_joint_accessor_hashes(candidate, accessor_index)
    if control_hashes != candidate_hashes:
        raise ValueError("a non-JOINTS accessor payload changed during compaction")

    return JointIndexCompaction(
        control_bytes=control_bytes,
        candidate_bytes=candidate_bytes,
        control_document=copy.deepcopy(control.document),
        candidate_document=copy.deepcopy(candidate.document),
        accessor_index=accessor_index,
        buffer_view_index=view_index,
        joint_rows=joint_rows,
        non_joint_accessor_hashes_control=control_hashes,
        non_joint_accessor_hashes_candidate=candidate_hashes,
        control_joint_payload_bytes=len(control_joint_payload),
        candidate_joint_payload_bytes=len(candidate_joint_payload),
    )
