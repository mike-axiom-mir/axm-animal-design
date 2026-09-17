#!/usr/bin/env python3
"""Retain Technical-Art producer adoption evidence for narrow JOINTS_0 storage.

Runtime PR #26 proved that the exact two-joint Animal GLB can safely represent
JOINTS_0 as UNSIGNED_BYTE. This script does not copy Runtime's post-build GLB
compactor. Instead it runs the Technical-Art producer itself, verifies that the
producer now chooses the smallest legal glTF joint-index width from its exact
emitted domain, and re-runs the unchanged generic UC receiver on current UC.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.uc_rigged_tangent_bridge import (
    UNSIGNED_BYTE,
    UNSIGNED_SHORT,
    _joint_index_payload,
    decode_first_primitive,
)

CURRENT_UC_HEAD = "e6826acbc7296ba77d25534c8d3d3770ff3fa747"
CURRENT_UC_CODEC_BLOB = "b1f2e68bb6c6800af5496decc95a8044d141edc9"
SOURCE_TRANSPORT_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
SOURCE_CONTROL_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
SOURCE_CONTROL_GLB_BYTES = 11148
RUNTIME_DONOR_HEAD = "3b9bcbc6b038e0b6782987134b567350274aacfd"
RUNTIME_DONOR_RESULT = "PASS_ANIMAL_GLB_JOINT_INDEX_WIDTH_COMPACTION_IMPORT_BUDGET"
RUNTIME_DONOR_ARTIFACT_ID = 10475517510
RUNTIME_DONOR_ARCHIVE_SHA256 = "2ce4925affb297644187fe14f26b0d189194125b813d07ded41de5bb37567947"
RUNTIME_CANDIDATE_GLB_SHA256 = "36ae048f6a6d7db8ca3c4a6bcf4f87f3d79fc0d81e89dbe3b2a373782f4e1b6a"
RUNTIME_CANDIDATE_GLB_BYTES = 10812
OUTPUT_SCHEMA = "axm.animal-technical-art-joint-index-width-adoption/v0.1"
OUTPUT_STATUS = "PASS_TECHNICAL_ART_PRODUCER_ADOPTS_BOUNDED_JOINT_INDEX_WIDTH"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_legacy_builder():
    path = ROOT / "tools" / "build_uc_rigged_tangent_bridge_evidence.py"
    spec = importlib.util.spec_from_file_location("axm_uc_rigged_tangent_evidence", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load existing rigged tangent evidence builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _joint_accessor_observation(decoded: dict[str, Any], glb_bytes: bytes) -> dict[str, Any]:
    document = decoded["document"]
    primitive = document["meshes"][0]["primitives"][0]
    accessor_index = int(primitive["attributes"]["JOINTS_0"])
    accessor = document["accessors"][accessor_index]
    view = document["bufferViews"][int(accessor["bufferView"])]
    rows = decoded["JOINTS_0"]
    flat = [int(value) for row in rows for value in row]
    if not flat:
        raise ValueError("emitted JOINTS_0 is empty")
    if min(flat) < 0:
        raise ValueError("emitted JOINTS_0 contains negative values")
    component_type = int(accessor["componentType"])
    payload_bytes = int(view["byteLength"])
    if component_type != UNSIGNED_BYTE:
        raise ValueError(f"Technical Art producer did not adopt UNSIGNED_BYTE JOINTS_0: {component_type}")
    if str(accessor.get("type")) != "VEC4" or bool(accessor.get("normalized", False)):
        raise ValueError("Technical Art JOINTS_0 accessor contract drift")
    if int(accessor.get("count", -1)) != len(rows):
        raise ValueError("Technical Art JOINTS_0 count drift")
    expected_payload = len(flat)
    if payload_bytes != expected_payload:
        raise ValueError(f"UNSIGNED_BYTE JOINTS_0 payload drift: expected {expected_payload}, observed {payload_bytes}")
    if max(flat) != 1:
        raise ValueError(f"exact two-joint emitted domain drift: expected max 1, observed {max(flat)}")
    return {
        "accessor_index": accessor_index,
        "component_type": component_type,
        "component_name": "UNSIGNED_BYTE",
        "count": len(rows),
        "slots_per_vertex": 4,
        "minimum_joint_index": min(flat),
        "maximum_joint_index": max(flat),
        "payload_bytes": payload_bytes,
        "glb_bytes": len(glb_bytes),
        "glb_sha256": sha256_bytes(glb_bytes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-evidence", type=Path, required=True)
    parser.add_argument("--animation-evidence", type=Path, required=True)
    parser.add_argument("--rigging-root", type=Path, required=True)
    parser.add_argument("--rig-donor-root", type=Path, required=True)
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    legacy = _load_legacy_builder()
    legacy.UC_HEAD = CURRENT_UC_HEAD
    legacy.UC_CODEC_BLOB = CURRENT_UC_CODEC_BLOB

    saved_argv = sys.argv[:]
    try:
        sys.argv = [
            str(ROOT / "tools" / "build_uc_rigged_tangent_bridge_evidence.py"),
            "--geometry-evidence", str(args.geometry_evidence),
            "--animation-evidence", str(args.animation_evidence),
            "--rigging-root", str(args.rigging_root),
            "--rig-donor-root", str(args.rig_donor_root),
            "--uc-root", str(args.uc_root),
            "--technical-art-head", args.technical_art_head,
            "--out", str(args.out),
        ]
        result = legacy.main()
    finally:
        sys.argv = saved_argv
    if result not in (None, 0):
        raise RuntimeError(f"existing rigged tangent evidence builder failed with code {result}")

    glb_path = args.out / "animal_selected003_right_mirror_rigged_uv_tangent_41key.glb"
    glb_bytes = glb_path.read_bytes()
    decoded = decode_first_primitive(glb_bytes)
    observed = _joint_accessor_observation(decoded, glb_bytes)

    if observed["payload_bytes"] != 336:
        raise ValueError(f"expected exact 84x4 byte JOINTS_0 payload of 336 B, observed {observed['payload_bytes']}")
    if observed["glb_bytes"] >= SOURCE_CONTROL_GLB_BYTES:
        raise ValueError("producer adoption did not reduce the complete GLB below the retained 16-bit control")

    fallback_payload, fallback_component = _joint_index_payload([[0, 256, 0, 0]])
    if fallback_component != UNSIGNED_SHORT or len(fallback_payload) != 8:
        raise ValueError("width policy did not fall back to UNSIGNED_SHORT above byte domain")
    try:
        _joint_index_payload([[0, 65536, 0, 0]])
    except ValueError as exc:
        overflow_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("joint-index domain above UNSIGNED_SHORT unexpectedly passed")

    transport_receipt = json.loads((args.out / "uc_rigged_uv_tangent_transport_receipt.json").read_text(encoding="utf-8"))
    uc = transport_receipt.get("universal_creation", {})
    if uc.get("head") != CURRENT_UC_HEAD or uc.get("codec_blob") != CURRENT_UC_CODEC_BLOB:
        raise ValueError("current UC identity was not retained by the receiving proof")
    inspection = uc.get("inspection", {})
    if inspection.get("pass") is not True or inspection.get("jointIndicesPass") is not True:
        raise ValueError("current UC did not accept the adopted producer representation")

    report = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "technical_art_head": args.technical_art_head,
        "source_transport_control": {
            "head": SOURCE_TRANSPORT_HEAD,
            "glb_sha256": SOURCE_CONTROL_GLB_SHA256,
            "glb_bytes": SOURCE_CONTROL_GLB_BYTES,
            "joint_component_type": UNSIGNED_SHORT,
            "joint_payload_bytes": 672,
        },
        "runtime_donor": {
            "head": RUNTIME_DONOR_HEAD,
            "result": RUNTIME_DONOR_RESULT,
            "artifact_id": RUNTIME_DONOR_ARTIFACT_ID,
            "archive_sha256": RUNTIME_DONOR_ARCHIVE_SHA256,
            "candidate_glb_sha256": RUNTIME_CANDIDATE_GLB_SHA256,
            "candidate_glb_bytes": RUNTIME_CANDIDATE_GLB_BYTES,
            "candidate_joint_component_type": UNSIGNED_BYTE,
            "candidate_joint_payload_bytes": 336,
            "role": "measurement/evidence donor; Technical Art independently adopts producer-side width selection",
        },
        "producer_adoption": observed,
        "complete_glb_reduction_bytes_vs_retained_control": SOURCE_CONTROL_GLB_BYTES - observed["glb_bytes"],
        "joint_payload_reduction_bytes_vs_retained_control": 672 - observed["payload_bytes"],
        "joint_payload_reduction_fraction": (672 - observed["payload_bytes"]) / 672,
        "current_universal_creation": {
            "head": CURRENT_UC_HEAD,
            "codec_blob": CURRENT_UC_CODEC_BLOB,
            "product_modified": False,
            "inspection_pass": True,
            "joint_indices_pass": True,
        },
        "negative_controls": {
            "byte_domain_overflow_falls_back_to_unsigned_short": "PASS",
            "unsigned_short_domain_overflow": overflow_control,
        },
        "truth_boundary": {
            "proves": [
                "the existing Technical Art producer now chooses glTF UNSIGNED_BYTE for the exact emitted JOINTS_0 domain 0..1 instead of emitting UNSIGNED_SHORT by default",
                "the exact 84x4 JOINTS_0 payload is 336 bytes while decoded joint values remain the same producer-owned rows",
                "the complete producer GLB is smaller than the retained 16-bit control",
                "current UC's unchanged generic rigged-glTF codec accepts the adopted representation without any Animal-specific UC change",
            ],
            "does_not_prove": [
                "deformed normal/tangent direction-frame equivalence; the existing Technical Art HOLD remains authoritative",
                "generic safety for sparse/interleaved/multi-primitive/multi-skin glTF layouts",
                "target-device frame-time, memory, import-time, gameplay, physics or controller improvement",
                "whole-animal production readiness, CANON, Profession Fabric promotion or Technical Art mastery",
            ],
        },
    }
    (args.out / "joint_index_width_adoption_receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
