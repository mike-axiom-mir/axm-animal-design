#!/usr/bin/env python3
"""Build a bounded 16-bit -> 8-bit JOINTS_0 import-budget A/B."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.runtime_joint_index_width_budget import (
    UNSIGNED_BYTE,
    UNSIGNED_SHORT,
    compact_joints_0_to_unsigned_byte,
    parse_glb,
    sha256_bytes,
)

TECHNICAL_ART_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
TECHNICAL_ART_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
TECHNICAL_ART_GLB_BYTES = 11148
TECHNICAL_ART_TRANSPORT_MODULE_BLOB = "90343f493389446f06d58202cb7465c98307458f"
UC_HEAD = "2a798836378d47a787221597aa8fece0fd637e6a"
UC_CODEC_PATH = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
UC_CODEC_BLOB = "b1f2e68bb6c6800af5496decc95a8044d141edc9"
UC_GODOT_PROBE_PATH = "src/axm_uc/data/engine/godot_probe.gd"
UC_GODOT_PROBE_BLOB = "7784a49655192bd395e8cba6065a6dfeb809df35"
RENDER_VERTEX_COUNT = 84
TRIANGLE_COUNT = 80
SKIN_JOINT_COUNT = 2
JOINT_SLOTS_PER_VERTEX = 4
OUTPUT_SCHEMA = "axm.runtime-animal-joint-index-width-budget/v0.1"
BUILD_STATE = "PASS_ANIMAL_JOINT_INDEX_WIDTH_COMPACTION_PAYLOAD_AND_UC_RECEIVER"


def _git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def _git_blob(path: Path, file_path: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", f"HEAD:{file_path}"], text=True).strip()


def _uc_inspect(uc_root: Path, glb_path: Path) -> dict[str, Any]:
    codec = (uc_root / UC_CODEC_PATH).resolve()
    script = r"""
const fs = require('fs');
const codec = require(process.argv[1]);
const bytes = new Uint8Array(fs.readFileSync(process.argv[2]));
process.stdout.write(JSON.stringify(codec.inspect(bytes)));
"""
    output = subprocess.check_output(["node", "-e", script, str(codec), str(glb_path.resolve())], text=True)
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("UC codec inspection did not return an object")
    return value


def _require_uc_semantics(value: dict[str, Any], label: str) -> None:
    if value.get("pass") is not True:
        raise ValueError(f"{label} UC inspection failed: {value.get('errors')}")
    if value.get("vertices") != RENDER_VERTEX_COUNT or value.get("triangles") != TRIANGLE_COUNT:
        raise ValueError(f"{label} UC geometry count drift")
    if value.get("skin", {}).get("joints") != SKIN_JOINT_COUNT:
        raise ValueError(f"{label} UC skin joint-count drift")
    if value.get("weightSumsPass") is not True or value.get("jointIndicesPass") is not True:
        raise ValueError(f"{label} UC skin validation failed")
    if value.get("deformation", {}).get("pass") is not True:
        raise ValueError(f"{label} UC deformation observation failed")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-glb", type=Path, required=True)
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--runtime-head", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.technical_art_head != TECHNICAL_ART_HEAD:
        raise ValueError("Technical Art exact-head drift")
    if _git_head(args.uc_root) != UC_HEAD:
        raise ValueError("Universal Creation checkout drift")
    if _git_blob(args.uc_root, UC_CODEC_PATH) != UC_CODEC_BLOB:
        raise ValueError("UC generic rigged codec blob drift")
    if _git_blob(args.uc_root, UC_GODOT_PROBE_PATH) != UC_GODOT_PROBE_BLOB:
        raise ValueError("UC Godot GLB probe blob drift")

    control_bytes = args.control_glb.read_bytes()
    if sha256_bytes(control_bytes) != TECHNICAL_ART_GLB_SHA256:
        raise ValueError("Technical Art control GLB SHA-256 drift")
    if len(control_bytes) != TECHNICAL_ART_GLB_BYTES:
        raise ValueError("Technical Art control GLB byte-size drift")

    compaction = compact_joints_0_to_unsigned_byte(control_bytes)
    candidate_bytes = compaction.candidate_bytes
    control_parts = parse_glb(control_bytes)
    candidate_parts = parse_glb(candidate_bytes)
    control_accessor = control_parts.document["accessors"][compaction.accessor_index]
    candidate_accessor = candidate_parts.document["accessors"][compaction.accessor_index]
    if int(control_accessor["componentType"]) != UNSIGNED_SHORT:
        raise ValueError("control JOINTS_0 component type drift")
    if int(candidate_accessor["componentType"]) != UNSIGNED_BYTE:
        raise ValueError("candidate JOINTS_0 was not compacted to UNSIGNED_BYTE")

    joint_rows = compaction.joint_rows
    if len(joint_rows) != RENDER_VERTEX_COUNT or any(len(row) != JOINT_SLOTS_PER_VERTEX for row in joint_rows):
        raise ValueError("exact Animal JOINTS_0 row/domain shape drift")
    joint_values = [value for row in joint_rows for value in row]
    if max(joint_values) >= SKIN_JOINT_COUNT:
        raise ValueError("exact Animal JOINTS_0 references a joint outside the two-joint skin")

    expected_control_joint_payload = RENDER_VERTEX_COUNT * JOINT_SLOTS_PER_VERTEX * 2
    expected_candidate_joint_payload = RENDER_VERTEX_COUNT * JOINT_SLOTS_PER_VERTEX
    if compaction.control_joint_payload_bytes != expected_control_joint_payload:
        raise ValueError("control JOINTS_0 payload byte count drift")
    if compaction.candidate_joint_payload_bytes != expected_candidate_joint_payload:
        raise ValueError("candidate JOINTS_0 payload byte count drift")
    if len(candidate_bytes) >= len(control_bytes):
        raise ValueError("candidate GLB did not reduce total import bytes")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    control_out = args.out_dir / "control-u16-joints.glb"
    candidate_out = args.out_dir / "candidate-u8-joints.glb"
    control_out.write_bytes(control_bytes)
    candidate_out.write_bytes(candidate_bytes)

    control_uc = _uc_inspect(args.uc_root, control_out)
    candidate_uc = _uc_inspect(args.uc_root, candidate_out)
    _require_uc_semantics(control_uc, "control")
    _require_uc_semantics(candidate_uc, "candidate")

    semantic_keys = ("vertices", "triangles", "weightSumsPass", "jointIndicesPass", "skin", "animation", "deformation")
    semantic_differences = {
        key: {"control": control_uc.get(key), "candidate": candidate_uc.get(key)}
        for key in semantic_keys
        if control_uc.get(key) != candidate_uc.get(key)
    }
    if semantic_differences:
        raise ValueError(f"current UC semantic inspection changed after JOINTS_0 compaction: {semantic_differences}")

    clip_name = str(control_parts.document["animations"][0]["name"])
    request = {
        "width": 960,
        "height": 720,
        "poses": [
            {"clip": clip_name, "time_s": 0.0},
            {"clip": clip_name, "time_s": 0.5},
            {"clip": clip_name, "time_s": 1.0},
        ],
        "views": [
            {"clip": clip_name, "time_s": 0.5, "yaw": 0.72, "elevation": 0.32},
            {"clip": clip_name, "time_s": 0.5, "yaw": -0.58, "elevation": 0.16},
        ],
        "playback": None,
    }
    (args.out_dir / "request.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "uc-control.json").write_text(json.dumps(control_uc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "uc-candidate.json").write_text(json.dumps(candidate_uc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload_saved = compaction.control_joint_payload_bytes - compaction.candidate_joint_payload_bytes
    total_saved = len(control_bytes) - len(candidate_bytes)
    report = {
        "schema": OUTPUT_SCHEMA,
        "state": BUILD_STATE,
        "runtime_head": args.runtime_head,
        "technical_art": {
            "head": TECHNICAL_ART_HEAD,
            "transport_module_blob": TECHNICAL_ART_TRANSPORT_MODULE_BLOB,
            "control_glb_sha256": TECHNICAL_ART_GLB_SHA256,
            "control_glb_bytes": len(control_bytes),
        },
        "universal_creation": {
            "head": UC_HEAD,
            "codec_blob": UC_CODEC_BLOB,
            "godot_probe_blob": UC_GODOT_PROBE_BLOB,
            "product_modified": False,
        },
        "representation": {
            "render_vertices": RENDER_VERTEX_COUNT,
            "joint_slots_per_vertex": JOINT_SLOTS_PER_VERTEX,
            "skin_joint_count": SKIN_JOINT_COUNT,
            "maximum_joint_index": max(joint_values),
            "control_component_type": UNSIGNED_SHORT,
            "candidate_component_type": UNSIGNED_BYTE,
            "control_joint_payload_bytes": compaction.control_joint_payload_bytes,
            "candidate_joint_payload_bytes": compaction.candidate_joint_payload_bytes,
            "joint_payload_saved_bytes": payload_saved,
            "joint_payload_reduction_fraction": payload_saved / compaction.control_joint_payload_bytes,
            "control_glb_bytes": len(control_bytes),
            "candidate_glb_bytes": len(candidate_bytes),
            "total_glb_saved_bytes": total_saved,
            "total_glb_reduction_fraction": total_saved / len(control_bytes),
            "candidate_glb_sha256": sha256_bytes(candidate_bytes),
            "decoded_joint_rows_identical": True,
            "non_joint_accessor_payload_hashes_identical": compaction.non_joint_accessor_hashes_control == compaction.non_joint_accessor_hashes_candidate,
        },
        "current_uc_receiver": {
            "control_pass": control_uc.get("pass") is True,
            "candidate_pass": candidate_uc.get("pass") is True,
            "selected_semantics_identical": True,
        },
        "visual_review_boundary": {
            "state": "PENDING_REAL_GODOT_IMPORT_RENDER_A_B",
            "note": "This build step changes storage width only. Art/QA tradeoff is not zero until the real Godot import/render A/B is retained and compared.",
        },
        "truth_boundary": {
            "proves_so_far": [
                "the exact retained Animal Technical Art GLB uses a 16-bit JOINTS_0 accessor although its joint-index domain is only 0..1",
                "an 8-bit JOINTS_0 candidate preserves every decoded joint index and every non-JOINTS accessor payload byte",
                "the current pinned UC generic rigged codec accepts both control and candidate with identical selected geometry/skin/animation/deformation inspection",
            ],
            "does_not_prove": [
                "real Godot target-host import or rendered visual equivalence until the follow-on A/B verifier passes",
                "deformed normal/tangent equivalence; Rigging PR #25 owns that separate measured HOLD",
                "target-device CPU/GPU/FPS/VRAM/heap improvement",
                "generic safety for skins with joint indices above 255",
                "automatic Technical Art or UC adoption",
                "CANON or production readiness",
            ],
        },
    }
    (args.out_dir / "build-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "runtime-head.txt").write_text(args.runtime_head + "\n", encoding="utf-8")
    (args.out_dir / "technical-art-head.txt").write_text(TECHNICAL_ART_HEAD + "\n", encoding="utf-8")
    (args.out_dir / "control-sha256.txt").write_text(_sha256_file(control_out) + "\n", encoding="utf-8")
    (args.out_dir / "candidate-sha256.txt").write_text(_sha256_file(candidate_out) + "\n", encoding="utf-8")
    print(BUILD_STATE)
    print(json.dumps(report["representation"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
