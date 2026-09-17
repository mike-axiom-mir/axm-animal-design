#!/usr/bin/env python3
"""Retain exact Geometry UV/tangent + existing Animal skin/key transport evidence."""
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

from axm_animal_design.organic_form import build_form_study
from axm_animal_design.uc_rigged_tangent_bridge import (
    BRIDGE_SCHEMA,
    GEOMETRY_BASIS_ID,
    GEOMETRY_BASIS_SCHEMA,
    KEY_COUNT,
    RENDER_VERTEX_COUNT,
    SOURCE_VERTEX_COUNT,
    TRIANGLE_COUNT,
    decode_first_primitive,
    maximum_expanded_owner_frame_residual,
    pack_exact_right_forelimb_rigged_tangent_glb,
)

GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
GEOMETRY_MODULE_PATH = "src/axm_animal_design/bilateral_uv_tangent_basis.py"
GEOMETRY_MODULE_BLOB = "ba0b4e620f132413606177358e47bd32ae4d4965"
GEOMETRY_GATE = "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD"
ANIMATION_HEAD = "1a8c929ce4372c4b1b1f29e9ac4cadd0cc26ac48"
ANIMATION_GATE = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_41_SAMPLE_MOTION_REBIND"
RIGGING_HEAD = "4acd9286140dd008f2a4f01ff513912497313e4f"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIG_PLAN_SHA256 = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
UC_HEAD = "2a798836378d47a787221597aa8fece0fd637e6a"
UC_CODEC_PATH = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
UC_CODEC_BLOB = "b1f2e68bb6c6800af5496decc95a8044d141edc9"
OUTPUT_SCHEMA = "axm.animal-current-uc-rigged-uv-tangent-transport-evidence/v0.1"
OUTPUT_STATUS = "PASS_ANIMAL_GEOMETRY_UV_TANGENT_RENDER_DOMAIN_WITH_SKIN_KEYS_TO_CURRENT_UC_CODEC"
POSE_TOLERANCE_M = 1e-6


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def git_blob(path: Path, file_path: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", f"HEAD:{file_path}"], text=True).strip()


def require_checkout(path: Path, expected: str, label: str) -> None:
    observed = git_head(path)
    if observed != expected:
        raise ValueError(f"{label} checkout drift: expected {expected}, observed {observed}")


def source_material(spec: dict[str, Any]) -> dict[str, Any]:
    evidence = build_form_study(spec)
    by_id = {row["id"]: row for row in evidence["surface"]["primitives"]}
    ids = ("front_upper_R", "front_lower_R", "front_paw_R")
    materials = [by_id[identifier]["material"] for identifier in ids]
    if any(value != materials[0] for value in materials[1:]):
        raise ValueError("right forelimb neutral material is no longer uniform")
    return copy.deepcopy(materials[0])


def inspect_with_uc_codec(uc_root: Path, glb_path: Path) -> dict[str, Any]:
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


def assert_roundtrip(decoded: dict[str, Any], packed) -> None:
    expected = {
        "POSITION": packed.positions,
        "NORMAL": packed.normals,
        "TANGENT": packed.tangents,
        "TEXCOORD_0": packed.texcoords,
        "JOINTS_0": packed.joints,
        "WEIGHTS_0": packed.weights,
        "INDICES": packed.indices,
    }
    for name, wanted in expected.items():
        if decoded.get(name) != wanted:
            raise ValueError(f"GLB decoded {name} no longer matches the exact Technical Art payload")
    attrs = decoded["document"]["meshes"][0]["primitives"][0]["attributes"]
    if set(attrs) != {"POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"}:
        raise ValueError("GLB primitive attribute set drift")


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

    require_checkout(args.rigging_root, RIGGING_HEAD, "Rigging")
    require_checkout(args.rig_donor_root, RIG_DONOR_HEAD, "rig donor")
    require_checkout(args.uc_root, UC_HEAD, "Universal Creation")
    observed_uc_blob = git_blob(args.uc_root, UC_CODEC_PATH)
    if observed_uc_blob != UC_CODEC_BLOB:
        raise ValueError(f"UC rigged codec blob drift: {observed_uc_blob}")

    geometry_receipt = load_json(args.geometry_evidence / "geometry-uv-tangent-evidence.json")
    basis = load_json(args.geometry_evidence / "right-uv-tangent-basis.json")
    if geometry_receipt.get("state") != GEOMETRY_GATE:
        raise ValueError("Geometry UV/tangent owner gate is not the exact expected PASS")
    if geometry_receipt.get("exact_geometry_head") != GEOMETRY_HEAD:
        raise ValueError("Geometry evidence exact-head drift")
    if basis.get("schema") != GEOMETRY_BASIS_SCHEMA or basis.get("id") != GEOMETRY_BASIS_ID:
        raise ValueError("Geometry basis schema/id drift")
    basis_digest = canonical_digest(basis)

    owner_receipt = load_json(args.animation_evidence / "bilateral_mirror_surface_motion_receipt.json")
    frames_doc = load_json(args.animation_evidence / "bilateral_mirror_surface_motion_frames.json")
    if owner_receipt.get("gate") != ANIMATION_GATE:
        raise ValueError("Animation owner gate is not the exact expected PASS")
    frames = frames_doc.get("frames")
    if not isinstance(frames, list) or len(frames) != KEY_COUNT:
        raise ValueError("Animation owner evidence must contain exactly 41 frames")

    spec = load_json(args.rigging_root / "examples" / "quadruped_neutral_001.json")
    plan = load_json(args.rig_donor_root / "examples" / "quadruped_rig_probe_001.json")
    if canonical_digest(plan) != RIG_PLAN_SHA256:
        raise ValueError("exact rig-plan donor digest drift")

    packed = pack_exact_right_forelimb_rigged_tangent_glb(
        spec=spec,
        plan=plan,
        owner_frames=frames,
        geometry_basis=basis,
        source_material=source_material(spec),
        clip_name="quadruped-articulation-loop-001 front-elbow-R UV tangent render-domain keys",
    )
    owner_residual, worst_sample = maximum_expanded_owner_frame_residual(owner_frames=frames, packed=packed)
    if owner_residual > POSE_TOLERANCE_M:
        raise ValueError(f"expanded render-domain skin/key positions exceed owner tolerance: {owner_residual}")

    args.out.mkdir(parents=True, exist_ok=True)
    glb_path = args.out / "animal_selected003_right_mirror_rigged_uv_tangent_41key.glb"
    glb_path.write_bytes(packed.bytes)
    decoded = decode_first_primitive(packed.bytes)
    assert_roundtrip(decoded, packed)

    uc_inspection = inspect_with_uc_codec(args.uc_root, glb_path)
    if uc_inspection.get("pass") is not True:
        raise ValueError(f"current UC rigged codec rejected UV/tangent skinned GLB: {uc_inspection.get('errors')}")
    if uc_inspection.get("vertices") != RENDER_VERTEX_COUNT or uc_inspection.get("triangles") != TRIANGLE_COUNT:
        raise ValueError("current UC codec render-domain geometry count drift")
    if uc_inspection.get("skin", {}).get("joints") != 2:
        raise ValueError("current UC codec skin joint-count drift")
    animation = uc_inspection.get("animation", {})
    if animation.get("channels") != 1 or animation.get("frames") != KEY_COUNT:
        raise ValueError("current UC codec animation channel/key-count drift")
    if uc_inspection.get("weightSumsPass") is not True or uc_inspection.get("jointIndicesPass") is not True:
        raise ValueError("current UC codec weight/joint validation failed")
    if uc_inspection.get("deformation", {}).get("pass") is not True:
        raise ValueError("current UC codec CPU deformation observer failed")

    collapsed = copy.deepcopy(basis)
    collapsed["render_positions"] = collapsed["render_positions"][:-1]
    collapsed["render_normals"] = collapsed["render_normals"][:-1]
    collapsed["render_uvs"] = collapsed["render_uvs"][:-1]
    collapsed["render_tangents"] = collapsed["render_tangents"][:-1]
    collapsed["render_source_indices"] = collapsed["render_source_indices"][:-1]
    collapsed["render_vertex_count"] = RENDER_VERTEX_COUNT - 1
    try:
        pack_exact_right_forelimb_rigged_tangent_glb(
            spec=spec, plan=plan, owner_frames=frames, geometry_basis=collapsed,
            source_material=source_material(spec), clip_name="negative-collapse",
        )
    except ValueError as exc:
        collapse_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("deliberate 84->83 render-domain collapse unexpectedly passed")

    tangent_drift = copy.deepcopy(basis)
    tangent_drift["render_tangents"][0][3] = -float(tangent_drift["render_tangents"][0][3])
    tangent_drift_digest = canonical_digest(tangent_drift)
    if tangent_drift_digest == basis_digest:
        raise ValueError("tangent-handedness mutation did not change owner basis digest")

    report = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "technical_art_head": args.technical_art_head,
        "scope": "exact Geometry-owned right UV/normal/tangent render domain + existing right-elbow skin/41 authored keys -> GLB -> current UC generic rigged codec",
        "owners": {
            "geometry": {"head": GEOMETRY_HEAD, "module_blob": GEOMETRY_MODULE_BLOB, "gate": GEOMETRY_GATE, "basis_digest": basis_digest},
            "rigging": {"head": RIGGING_HEAD, "rig_donor_head": RIG_DONOR_HEAD, "rig_plan_sha256": RIG_PLAN_SHA256, "weighting": "smoothstep-v0"},
            "animation": {"head": ANIMATION_HEAD, "gate": ANIMATION_GATE, "key_count": KEY_COUNT, "duration_seconds": 1.0},
        },
        "transport": {
            "bridge_schema": BRIDGE_SCHEMA,
            "source_vertices": SOURCE_VERTEX_COUNT,
            "render_vertices": RENDER_VERTEX_COUNT,
            "triangles": TRIANGLE_COUNT,
            "skin_joints": 2,
            "animation_channels": 1,
            "authored_keys": KEY_COUNT,
            "attributes": ["POSITION", "NORMAL", "TANGENT", "TEXCOORD_0", "JOINTS_0", "WEIGHTS_0"],
            "render_source_mapping_preserved": True,
            "source_to_uc_component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "triangle_winding_reversed": True,
            "normal_and_tangent_xyz_rule": "M * source_direction",
            "tangent_w_rule": "det(M) * source_w = -source_w",
            "rotation_axis_rule": "det(M) * M * source_axis",
            "glb_sha256": sha256_bytes(packed.bytes),
            "glb_bytes": len(packed.bytes),
            "decoded_attribute_roundtrip": "PASS_EXACT_FLOAT32_PAYLOAD",
            "maximum_expanded_authored_key_position_residual_m": owner_residual,
            "worst_authored_key_sample_index": worst_sample,
            "pose_tolerance_m": POSE_TOLERANCE_M,
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "head": UC_HEAD,
            "codec_path": UC_CODEC_PATH,
            "codec_blob": observed_uc_blob,
            "product_modified": False,
            "inspection": uc_inspection,
        },
        "negative_controls": {
            "render_domain_84_to_83_collapse": collapse_control,
            "owner_tangent_handedness_mutation": {
                "status": "PASS_REJECTED_BY_EXACT_OWNER_DIGEST",
                "owner_digest": basis_digest,
                "mutated_digest": tangent_drift_digest,
            },
            "uc_codec_blob_gate": "PASS_EXACT_BLOB",
        },
        "truth_boundary": {
            "proves": [
                "Geometry's exact 84-vertex structural UV/explicit-normal/explicit-tangent render domain crosses the Technical Art coordinate boundary without vertex-domain collapse",
                "UVs remain numerically unchanged while normals/tangent XYZ follow the ordinary direction transform, tangent W flips for the orientation-reversing basis, and triangle winding is reversed",
                "the existing 42-source-vertex right-elbow skin weights are duplicated only through Geometry's exact source->render map and coexist with TEXCOORD_0/TANGENT plus the existing 41 authored keys",
                "the emitted GLB decodes to the exact float32 Technical Art payload and current UC's unchanged generic rigged codec accepts its skin, weights, animation and CPU deformation observation",
            ],
            "does_not_prove": [
                "final texture UV placement, texel density, texture maps or lookdev",
                "tangent-space normal-map shaded appearance",
                "deformed tangent-frame equivalence; Rigging's separate observer owns structural deformation evidence",
                "continuous animation interpolation equivalence",
                "whole-animal or four-joint export, target-engine import/playback, runtime/controller/gameplay or performance",
                "CANON, production readiness or Technical Art mastery",
            ],
        },
    }
    (args.out / "uc_rigged_uv_tangent_transport_receipt.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "uc_codec_inspection.json").write_text(json.dumps(uc_inspection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out / "geometry-right-basis.json").write_text(json.dumps(basis, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for name, value in (
        ("technical-art-head.txt", args.technical_art_head),
        ("geometry-head.txt", GEOMETRY_HEAD),
        ("geometry-module-blob.txt", GEOMETRY_MODULE_BLOB),
        ("geometry-basis-digest.txt", basis_digest),
        ("animation-head.txt", ANIMATION_HEAD),
        ("rigging-head.txt", RIGGING_HEAD),
        ("uc-head.txt", UC_HEAD),
        ("uc-codec-blob.txt", observed_uc_blob),
        ("glb-sha256.txt", sha256_bytes(packed.bytes)),
    ):
        (args.out / name).write_text(value + "\n", encoding="utf-8")
    (args.out / "README.txt").write_text(
        "AXM Animal Technical Art retained rigged UV/tangent transport evidence.\n"
        "Geometry owns UVs/normals/tangents and the 42->84 render split. Rigging owns weights. Animation owns keys.\n"
        "Technical Art only transports the exact owner payload through the explicit coordinate/GLB boundary and current UC generic codec.\n"
        "No final lookdev, deformed tangent equivalence, engine playback, performance, CANON or production-readiness claim is made.\n",
        encoding="utf-8",
    )
    print(OUTPUT_STATUS)
    print(f"render_vertices={RENDER_VERTEX_COUNT}")
    print(f"triangles={TRIANGLE_COUNT}")
    print(f"keys={KEY_COUNT}")
    print(f"glb_sha256={sha256_bytes(packed.bytes)}")
    print(f"max_owner_position_residual_m={owner_residual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
