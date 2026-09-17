#!/usr/bin/env python3
"""Build bounded real-target input from exact Animal owner reconstruction code.

The owner reconstruction algorithm is invoked from a pinned Rigging checkout in a
separate Python process. Technical Art only maps the returned owner frame through
the already-established Animal -> UC target boundary and validates the receiving
packet. Universal Creation remains the generic GLB receiver and is not modified.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.uc_bridge import _source_to_uc
from axm_animal_design.uc_direction_frame_target_host_adapter import (
    PACKET_STATE,
    build_target_host_packet,
    require_runtime_product_ready,
)
from axm_animal_design.uc_rigged_tangent_bridge import (
    source_direction_to_uc,
    source_tangent_to_uc,
)

EXPECTED_RIGGING_HEAD = "81ab44eab2e13bed95187610a476be2b2c4667a7"
EXPECTED_RIGGING_RECONSTRUCTION_BLOB = "c9916c62e2081922b8eb7ec0b3cd1c25c019b2f6"
EXPECTED_SOURCE_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
EXPECTED_ADOPTION_EVIDENCE_SCHEMA = "axm.animal-current-uc-direction-frame-reconstruction-contract-evidence/v0.1"
EXPECTED_ADOPTION_STATE = "PASS_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_CONTRACT_ADOPTED__HOLD_TARGET_RUNTIME_IMPLEMENTATION"
UC_CODEC_PATH = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
POSITION_TOLERANCE_M = 1e-6
BUILD_SCHEMA = "axm.animal-direction-frame-target-host-build-evidence/v0.1"
BUILD_STATE = "PASS_OWNER_RECONSTRUCTION_TO_TECHNICAL_ART_TARGET_HOST_PACKET_READY"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def git_blob(root: Path, path: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", f"HEAD:{path}"], text=True).strip()


def inspect_with_uc_codec(uc_root: Path, glb_path: Path) -> dict[str, Any]:
    script = r"""
const fs = require('fs');
const codec = require(process.argv[1]);
const bytes = new Uint8Array(fs.readFileSync(process.argv[2]));
process.stdout.write(JSON.stringify(codec.inspect(bytes)));
"""
    output = subprocess.check_output(
        ["node", "-e", script, str((uc_root / UC_CODEC_PATH).resolve()), str(glb_path.resolve())],
        text=True,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("UC codec inspection must return an object")
    return value


OWNER_SCRIPT = r'''
import json
import sys
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.transported_frame_reconstruction_constraint import (
    _child_weights,
    _collapse_render_positions_to_source,
    _decode_glb,
)
from axm_animal_design.transported_tangent_deformation_audit import (
    _quat_angle_deg,
    _skin_position,
)

root = Path(sys.argv[1])
glb_path = Path(sys.argv[2])
load = lambda name: json.loads((root / "examples" / name).read_text(encoding="utf-8"))
spec = load("quadruped_neutral_001.json")
left_profile = load("quadruped_elbow_source_successor_003.json")
bilateral_profile = load("quadruped_elbow_bilateral_successor_003.json")
left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
    spec, left_profile, bilateral_profile
)
right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
static_basis = derive_uv_tangent_basis(right_candidate, side="right")
decoded = _decode_glb(glb_path.read_bytes())
render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
source_vertex_count = int(static_basis["source_vertex_count"])
document = decoded["document"]
animated_node = decoded["ANIMATED_NODE"]
pivot = document["nodes"][animated_node]["translation"]
weights = _child_weights(decoded)
frames = []
for sample_index, (time_value, quaternion) in enumerate(zip(decoded["TIMES"], decoded["ROTATIONS"])):
    skinned_target = [
        _skin_position(position, pivot, quaternion, child_weight)
        for position, child_weight in zip(decoded["POSITION"], weights)
    ]
    source_positions, split_residual = _collapse_render_positions_to_source(
        skinned_target, render_source_indices, source_vertex_count
    )
    owner_frame = _derive_posed_tangent_frame(right_candidate, static_basis, source_positions)
    frames.append({
        "sample_index": sample_index,
        "time_seconds": float(time_value),
        "angle_deg": _quat_angle_deg(quaternion),
        "uv_split_position_residual_m": float(split_residual),
        "source_render_positions": owner_frame["render_positions"],
        "source_render_normals": owner_frame["render_normals"],
        "source_render_tangents": owner_frame["render_tangents"],
        "target_skinned_positions": skinned_target,
    })
print(json.dumps({
    "frames": frames,
    "texcoords": decoded["TEXCOORD_0"],
    "indices": decoded["INDICES"],
    "render_source_indices": render_source_indices,
}, separators=(",", ":"), allow_nan=False))
'''


def invoke_exact_owner(rigging_root: Path, glb_path: Path) -> dict[str, Any]:
    env = dict(**__import__("os").environ)
    env["PYTHONPATH"] = str((rigging_root / "src").resolve())
    output = subprocess.check_output(
        [sys.executable, "-c", OWNER_SCRIPT, str(rigging_root.resolve()), str(glb_path.resolve())],
        text=True,
        env=env,
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("owner reconstruction subprocess must return an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-receipt", type=Path, required=True)
    parser.add_argument("--rigging-root", type=Path, required=True)
    parser.add_argument("--source-glb", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--uc-head", required=True)
    parser.add_argument("--uc-codec-blob", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if git_head(args.rigging_root) != EXPECTED_RIGGING_HEAD:
        raise ValueError("exact Rigging reconstruction owner head drift")
    owner_blob = git_blob(args.rigging_root, "src/axm_animal_design/transported_frame_reconstruction_constraint.py")
    if owner_blob != EXPECTED_RIGGING_RECONSTRUCTION_BLOB:
        raise ValueError("exact Rigging reconstruction module blob drift")
    if git_head(args.uc_root) != args.uc_head:
        raise ValueError("current UC checkout drift")
    observed_uc_blob = git_blob(args.uc_root, UC_CODEC_PATH)
    if observed_uc_blob != args.uc_codec_blob:
        raise ValueError("current UC codec blob drift")

    glb_bytes = args.source_glb.read_bytes()
    glb_sha256 = digest_bytes(glb_bytes)
    if glb_sha256 != EXPECTED_SOURCE_GLB_SHA256:
        raise ValueError("exact Technical Art source GLB identity drift")

    adoption_evidence = load_json(args.contract_receipt)
    if adoption_evidence.get("schema") != EXPECTED_ADOPTION_EVIDENCE_SCHEMA:
        raise ValueError("predecessor Technical Art adoption evidence schema drift")
    if adoption_evidence.get("state") != EXPECTED_ADOPTION_STATE:
        raise ValueError("predecessor Technical Art adoption evidence state drift")
    contract = adoption_evidence.get("contract")
    if not isinstance(contract, dict):
        raise ValueError("predecessor Technical Art adoption evidence omitted nested contract")

    uc_inspection = inspect_with_uc_codec(args.uc_root, args.source_glb)
    owner = invoke_exact_owner(args.rigging_root, args.source_glb)
    owner_frames = owner.get("frames")
    if not isinstance(owner_frames, list) or len(owner_frames) != 41:
        raise ValueError("exact owner reconstruction did not return all 41 authored keys")
    texcoords = owner.get("texcoords")
    indices = owner.get("indices")
    if not isinstance(texcoords, list) or not isinstance(indices, list):
        raise ValueError("owner subprocess omitted transported UV/index identity")

    target_frames: list[dict[str, Any]] = []
    maximum_target_position_residual_m = 0.0
    for row in owner_frames:
        mapped_positions = [
            [float(value) for value in _source_to_uc(position, "owner reconstructed render position")]
            for position in row["source_render_positions"]
        ]
        mapped_normals = [
            source_direction_to_uc(normal, "owner reconstructed normal")
            for normal in row["source_render_normals"]
        ]
        mapped_tangents = [source_tangent_to_uc(tangent) for tangent in row["source_render_tangents"]]
        transported_positions = row["target_skinned_positions"]
        residual = max(
            __import__("math").dist(left, right)
            for left, right in zip(mapped_positions, transported_positions)
        )
        maximum_target_position_residual_m = max(maximum_target_position_residual_m, residual)
        target_frames.append(
            {
                "sample_index": int(row["sample_index"]),
                "time_seconds": float(row["time_seconds"]),
                "angle_deg": float(row["angle_deg"]),
                "positions": mapped_positions,
                "normals": mapped_normals,
                "tangents": mapped_tangents,
                "texcoords": copy.deepcopy(texcoords),
                "indices": [int(value) for value in indices],
                "uv_split_position_residual_m": float(row["uv_split_position_residual_m"]),
            }
        )
    if maximum_target_position_residual_m > POSITION_TOLERANCE_M:
        raise ValueError(
            f"owner reconstructed target positions exceed transported skinned POSITION gate: {maximum_target_position_residual_m}"
        )

    packet = build_target_host_packet(
        contract,
        frames=target_frames,
        exact_technical_art_head=args.technical_art_head,
        exact_source_glb_sha256=glb_sha256,
        exact_rigging_head=EXPECTED_RIGGING_HEAD,
        exact_rigging_reconstruction_module_blob=owner_blob,
        current_uc_head=args.uc_head,
        current_uc_codec_blob=observed_uc_blob,
        current_uc_inspection=uc_inspection,
    )
    if packet.get("state") != PACKET_STATE:
        raise ValueError("Technical Art target-host packet did not reach exact READY state")

    try:
        require_runtime_product_ready(packet)
    except ValueError as exc:
        runtime_hold_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("reference target-host packet silently promoted itself to Runtime readiness")

    corrupted_frames = copy.deepcopy(target_frames)
    corrupted_frames[17]["tangents"][3][3] = 0.0
    try:
        build_target_host_packet(
            contract,
            frames=corrupted_frames,
            exact_technical_art_head=args.technical_art_head,
            exact_source_glb_sha256=glb_sha256,
            exact_rigging_head=EXPECTED_RIGGING_HEAD,
            exact_rigging_reconstruction_module_blob=owner_blob,
            current_uc_head=args.uc_head,
            current_uc_codec_blob=observed_uc_blob,
            current_uc_inspection=uc_inspection,
        )
    except ValueError as exc:
        tangent_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("deliberate tangent-handedness corruption unexpectedly passed")

    args.out.mkdir(parents=True, exist_ok=True)
    packet_path = args.out / "technical-art-target-host-packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    build_receipt = {
        "schema": BUILD_SCHEMA,
        "state": BUILD_STATE,
        "technical_art_head": args.technical_art_head,
        "rigging_owner": {
            "head": EXPECTED_RIGGING_HEAD,
            "reconstruction_module_blob": owner_blob,
            "algorithm_copied_into_technical_art": False,
        },
        "source_glb": {"sha256": glb_sha256, "bytes": len(glb_bytes)},
        "universal_creation": {
            "head": args.uc_head,
            "codec_blob": observed_uc_blob,
            "product_modified": False,
            "inspection_pass": uc_inspection.get("pass"),
        },
        "adapter": {
            "authored_keys": len(target_frames),
            "maximum_reconstructed_to_transported_position_residual_m": maximum_target_position_residual_m,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "target_host_reference": "Godot ArrayMesh",
        },
        "negative_controls": {
            "runtime_promotion": runtime_hold_control,
            "tangent_handedness_corruption": tangent_control,
        },
        "truth_boundary": packet["truth_boundary"],
    }
    (args.out / "technical-art-target-host-build-receipt.json").write_text(
        json.dumps(build_receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (args.out / "technical-art-head.txt").write_text(args.technical_art_head + "\n", encoding="utf-8")
    (args.out / "rigging-head.txt").write_text(EXPECTED_RIGGING_HEAD + "\n", encoding="utf-8")
    (args.out / "rigging-reconstruction-module-blob.txt").write_text(owner_blob + "\n", encoding="utf-8")
    (args.out / "uc-head.txt").write_text(args.uc_head + "\n", encoding="utf-8")
    (args.out / "uc-codec-blob.txt").write_text(observed_uc_blob + "\n", encoding="utf-8")
    (args.out / "source-glb-sha256.txt").write_text(glb_sha256 + "\n", encoding="utf-8")
    print(json.dumps(build_receipt, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
