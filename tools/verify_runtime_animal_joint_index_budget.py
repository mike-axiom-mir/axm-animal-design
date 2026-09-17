#!/usr/bin/env python3
"""Verify exact Runtime JOINTS_0 width A/B through real Godot import/render."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BUILD_SCHEMA = "axm.runtime-animal-joint-index-width-budget/v0.1"
BUILD_STATE = "PASS_ANIMAL_JOINT_INDEX_WIDTH_COMPACTION_PAYLOAD_AND_UC_RECEIVER"
FINAL_SCHEMA = "axm.runtime-animal-joint-index-width-budget-report/v0.1"
FINAL_STATE = "PASS_ANIMAL_GLB_JOINT_INDEX_WIDTH_COMPACTION_IMPORT_BUDGET"
CONTROL_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
TECHNICAL_ART_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
GODOT_VERSION_PREFIX = "4.7.2"
TOLERANCE = 1e-9


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_backend(receipt: dict[str, Any], label: str) -> None:
    backend = receipt.get("backend")
    if not isinstance(backend, dict):
        raise ValueError(f"{label} missing Godot backend identity")
    if not str(backend.get("version", "")).startswith(GODOT_VERSION_PREFIX):
        raise ValueError(f"{label} Godot version drift: {backend.get('version')}")
    if backend.get("renderer") != "gl_compatibility":
        raise ValueError(f"{label} renderer drift: {backend.get('renderer')}")
    if backend.get("display") == "headless":
        raise ValueError(f"{label} used dummy headless display")


def _numeric_delta(left: Any, right: Any) -> float:
    if isinstance(left, bool) or isinstance(right, bool):
        return 0.0 if left == right else float("inf")
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right))
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return max((_numeric_delta(a, b) for a, b in zip(left, right)), default=0.0)
    if isinstance(left, dict) and isinstance(right, dict) and set(left) == set(right):
        return max((_numeric_delta(left[key], right[key]) for key in left), default=0.0)
    return 0.0 if left == right else float("inf")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    build = _load(args.build_report)
    if build.get("schema") != BUILD_SCHEMA or build.get("state") != BUILD_STATE:
        raise ValueError("Runtime build report identity/state drift")
    if build.get("technical_art", {}).get("head") != TECHNICAL_ART_HEAD:
        raise ValueError("Technical Art exact-head drift")
    representation = build.get("representation", {})
    if representation.get("control_component_type") != 5123:
        raise ValueError("control JOINTS_0 is not UNSIGNED_SHORT")
    if representation.get("candidate_component_type") != 5121:
        raise ValueError("candidate JOINTS_0 is not UNSIGNED_BYTE")
    if representation.get("render_vertices") != 84 or representation.get("joint_slots_per_vertex") != 4:
        raise ValueError("bounded render/joint-slot domain drift")
    if representation.get("maximum_joint_index") != 1:
        raise ValueError("bounded two-joint domain drift")
    if representation.get("control_joint_payload_bytes") != 672 or representation.get("candidate_joint_payload_bytes") != 336:
        raise ValueError("bounded JOINTS_0 payload byte counts drift")
    if representation.get("joint_payload_saved_bytes") != 336:
        raise ValueError("expected exact 336-byte JOINTS_0 payload reduction")
    if representation.get("decoded_joint_rows_identical") is not True:
        raise ValueError("decoded joint-row identity was not preserved")
    if representation.get("non_joint_accessor_payload_hashes_identical") is not True:
        raise ValueError("non-JOINTS accessor payload identity was not preserved")
    if representation.get("candidate_glb_bytes", 0) >= representation.get("control_glb_bytes", 0):
        raise ValueError("candidate GLB is not smaller")
    if build.get("current_uc_receiver", {}).get("selected_semantics_identical") is not True:
        raise ValueError("current UC semantic inspection was not identical")

    control_receipt = _load(args.control_root / "worker-result.json")
    candidate_receipt = _load(args.candidate_root / "worker-result.json")
    _require_backend(control_receipt, "control")
    _require_backend(candidate_receipt, "candidate")
    if control_receipt.get("source_sha256") != CONTROL_SHA256:
        raise ValueError("Godot control source SHA-256 drift")
    if candidate_receipt.get("source_sha256") != representation.get("candidate_glb_sha256"):
        raise ValueError("Godot candidate source SHA-256 drift")

    control_poses = control_receipt.get("poses")
    candidate_poses = candidate_receipt.get("poses")
    if not isinstance(control_poses, list) or len(control_poses) != 3:
        raise ValueError("control did not retain three exact pose observations")
    if not isinstance(candidate_poses, list) or len(candidate_poses) != 3:
        raise ValueError("candidate did not retain three exact pose observations")
    pose_delta = _numeric_delta(control_poses, candidate_poses)
    if pose_delta > TOLERANCE:
        raise ValueError(f"Godot imported pose geometry drift exceeds tolerance: {pose_delta}")
    for label, poses in (("control", control_poses), ("candidate", candidate_poses)):
        if any(int(pose.get("triangles", -1)) != 80 for pose in poses):
            raise ValueError(f"{label} imported triangle count drift")

    binding_delta = _numeric_delta(control_receipt.get("material_bindings"), candidate_receipt.get("material_bindings"))
    if binding_delta != 0.0:
        raise ValueError("Godot imported material-binding identity drift")

    image_names = ("view-00.png", "view-00-coverage.png", "view-01.png", "view-01-coverage.png")
    image_pairs: dict[str, Any] = {}
    for name in image_names:
        control_path = args.control_root / name
        candidate_path = args.candidate_root / name
        if not control_path.is_file() or not candidate_path.is_file():
            raise ValueError(f"missing retained image pair: {name}")
        control_sha = _sha(control_path)
        candidate_sha = _sha(candidate_path)
        if control_sha != candidate_sha:
            raise ValueError(f"retained image pair is not byte-identical: {name}")
        image_pairs[name] = {"control_sha256": control_sha, "candidate_sha256": candidate_sha, "byte_identical": True}

    report = {
        "schema": FINAL_SCHEMA,
        "state": FINAL_STATE,
        "runtime_head": build.get("runtime_head"),
        "technical_art_head": TECHNICAL_ART_HEAD,
        "representation": representation,
        "godot_import": {
            "control_backend": control_receipt.get("backend"),
            "candidate_backend": candidate_receipt.get("backend"),
            "pose_observations_per_mode": len(control_poses),
            "maximum_control_candidate_pose_receipt_delta": pose_delta,
            "material_bindings_identical": True,
        },
        "visual_tradeoff": {
            "state": "NONE_OBSERVED__TWO_FIXED_VIEWS_AND_COVERAGE_IMAGES_BYTE_IDENTICAL",
            "image_pairs": image_pairs,
            "art_director_review_note": "No visual difference was observed in the exact two fixed peak-pose views or their coverage masks. This is a storage-width A/B only; it does not decide Animal tangent-space lookdev or Rigging's deformed direction-frame HOLD.",
        },
        "decision": "ELIGIBLE_TECHNICAL_ART_IMPORT_BUDGET_CANDIDATE__NO_AUTOMATIC_ADOPTION",
        "truth_boundary": {
            "proves": [
                "the exact Animal two-joint GLB can encode JOINTS_0 as UNSIGNED_BYTE instead of UNSIGNED_SHORT while preserving every decoded joint index",
                "all non-JOINTS accessor payload bytes remain unchanged",
                "the pinned current UC generic receiver accepts both files with identical selected semantic inspection",
                "real Godot 4.7.2 GL Compatibility imports both files with matching retained pose geometry and byte-identical fixed-view output",
                "the exact JOINTS_0 payload shrinks by 336 bytes and the complete GLB import payload is smaller by the measured report delta",
            ],
            "does_not_prove": [
                "deformed normal/tangent owner-frame equivalence; Rigging PR #25 separately measures a HOLD there",
                "target-device CPU/GPU frame time, FPS, VRAM or heap improvement",
                "generic safety for joint indices above 255 or arbitrary interleaved/sparse glTF accessors",
                "whole-animal production import acceptance, gameplay or controller behavior",
                "automatic Technical Art/UC producer adoption, CANON or production readiness",
            ],
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(FINAL_STATE)
    print(json.dumps({
        "joint_payload_saved_bytes": representation["joint_payload_saved_bytes"],
        "total_glb_saved_bytes": representation["total_glb_saved_bytes"],
        "total_glb_reduction_fraction": representation["total_glb_reduction_fraction"],
        "pose_delta": pose_delta,
        "visual_state": report["visual_tradeoff"]["state"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
