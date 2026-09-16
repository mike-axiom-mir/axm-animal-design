#!/usr/bin/env python3
"""Build exact Animal mirror-surface skin + authored-key transport evidence.

The owner Animation lane must first emit its exact 41-sample mirror-surface evidence.
This Technical Art tool consumes that retained producer result, re-expresses only the
already-established right-elbow skin/weights as glTF, and asks the pinned current UC
rigged glTF codec to inspect the emitted bytes. It does not author Animal motion or
promote Animal semantics into UC.
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

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_form import build_form_study
from axm_animal_design.uc_rigged_animation_bridge import (
    BRIDGE_SCHEMA,
    SOURCE_CANDIDATE_ID,
    WEIGHTING_ID,
    maximum_owner_frame_residual,
    mutated_weight_residual,
    pack_exact_right_forelimb_glb,
)

ANIMATION_HEAD = "1a8c929ce4372c4b1b1f29e9ac4cadd0cc26ac48"
RIGGING_HEAD = "4acd9286140dd008f2a4f01ff513912497313e4f"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
GEOMETRY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
UC_HEAD = "ae76436052a13e2d9214ba527c9b84e1cffc622c"
UC_CODEC_PATH = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
UC_CODEC_BLOB = "b1f2e68bb6c6800af5496decc95a8044d141edc9"
ANIMATION_GATE = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_41_SAMPLE_MOTION_REBIND"
RIGHT_CANDIDATE_SHA256 = "086ffe6f48af0cc3506871a4754b7395ba4c1fa3155eb4f420854a37e92181db"
RIG_PLAN_SHA256 = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
CLIP_SHA256 = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
OUTPUT_SCHEMA = "axm.animal-current-uc-rigged-animation-transport-evidence/v0.1"
OUTPUT_STATUS = "PASS_ANIMAL_EXACT_MIRROR_RIGHT_FORELIMB_SKINNED_41_KEY_GLB_TO_CURRENT_UC_CODEC"
POSE_TOLERANCE_M = 1e-6


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def git_blob(path: Path, file_path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", f"HEAD:{file_path}"], text=True
    ).strip()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def source_material(spec: dict[str, Any]) -> dict[str, Any]:
    evidence = build_form_study(spec)
    by_id = {row["id"]: row for row in evidence["surface"]["primitives"]}
    ids = ("front_upper_R", "front_lower_R", "front_paw_R")
    if any(identifier not in by_id for identifier in ids):
        raise ValueError("neutral source evidence no longer contains the right forelimb donor regions")
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
    output = subprocess.check_output(
        ["node", "-e", script, str(codec), str(glb_path.resolve())], text=True
    )
    value = json.loads(output)
    if not isinstance(value, dict):
        raise ValueError("UC codec inspection did not return an object")
    return value


def require_exact_checkout(path: Path, expected: str, label: str) -> None:
    observed = git_head(path)
    if observed != expected:
        raise ValueError(f"{label} checkout drift: expected {expected}, observed {observed}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation-evidence", type=Path, required=True)
    parser.add_argument("--rigging-root", type=Path, required=True)
    parser.add_argument("--rig-donor-root", type=Path, required=True)
    parser.add_argument("--uc-root", type=Path, required=True)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rigging_root = args.rigging_root.resolve()
    rig_donor_root = args.rig_donor_root.resolve()
    uc_root = args.uc_root.resolve()
    require_exact_checkout(rigging_root, RIGGING_HEAD, "Rigging")
    require_exact_checkout(rig_donor_root, RIG_DONOR_HEAD, "rig donor")
    require_exact_checkout(uc_root, UC_HEAD, "Universal Creation")
    observed_codec_blob = git_blob(uc_root, UC_CODEC_PATH)
    if observed_codec_blob != UC_CODEC_BLOB:
        raise ValueError(f"UC rigged codec blob drift: {observed_codec_blob}")

    receipt_path = args.animation_evidence / "bilateral_mirror_surface_motion_receipt.json"
    frames_path = args.animation_evidence / "bilateral_mirror_surface_motion_frames.json"
    if not receipt_path.is_file() or not frames_path.is_file():
        raise ValueError("exact Animation owner receipt and frames are required")
    owner_receipt = load_json(receipt_path)
    frames_doc = load_json(frames_path)
    if owner_receipt.get("gate") != ANIMATION_GATE:
        raise ValueError("Animation owner gate is not the exact expected PASS")
    identity = owner_receipt.get("source_identity", {})
    if identity.get("geometry_mirror_surface_head") != GEOMETRY_HEAD:
        raise ValueError("Animation Geometry identity drift")
    if identity.get("bilateral_mirror_surface_rigging_head") != RIGGING_HEAD:
        raise ValueError("Animation Rigging identity drift")
    if identity.get("rig_plan_donor_head") != RIG_DONOR_HEAD:
        raise ValueError("Animation rig donor identity drift")
    if identity.get("rig_plan_digest") != RIG_PLAN_SHA256:
        raise ValueError("Animation rig-plan digest drift")
    if identity.get("right_exact_mirror_successor_digest") != RIGHT_CANDIDATE_SHA256:
        raise ValueError("Animation exact-mirror candidate identity drift")
    if identity.get("clip_digest") != CLIP_SHA256:
        raise ValueError("Animation clip identity drift")
    if identity.get("rig_weighting_profile") != WEIGHTING_ID:
        raise ValueError("Animation weighting identity drift")
    motion = owner_receipt.get("motion", {})
    if motion.get("duration_seconds") != 1.0 or motion.get("sample_rate_hz") != 40 or motion.get("endpoint_inclusive_sample_count") != 41:
        raise ValueError("Animation authored timing contract drift")
    if motion.get("front_elbow_peak_deg") != 18.0:
        raise ValueError("Animation right-elbow amplitude drift")
    if frames_doc.get("rigging_head") != RIGGING_HEAD or frames_doc.get("geometry_head") != GEOMETRY_HEAD:
        raise ValueError("Animation frame document lineage drift")
    if frames_doc.get("right_candidate_digest") != RIGHT_CANDIDATE_SHA256:
        raise ValueError("Animation frame document candidate drift")
    frames = frames_doc.get("frames")
    indices = frames_doc.get("indices")
    if not isinstance(frames, list) or len(frames) != 41:
        raise ValueError("Animation frame document must contain 41 frames")
    if not isinstance(indices, list) or len(indices) != 240:
        raise ValueError("Animation frame document must contain 240 indices")

    spec = load_json(rigging_root / "examples" / "quadruped_neutral_001.json")
    plan = load_json(rig_donor_root / "examples" / "quadruped_rig_probe_001.json")
    if digest(plan) != RIG_PLAN_SHA256:
        raise ValueError("exact donor rig plan digest drift")
    material = source_material(spec)

    packed = pack_exact_right_forelimb_glb(
        spec=spec,
        plan=plan,
        owner_frames=frames,
        indices=[int(value) for value in indices],
        source_material=material,
        clip_name="quadruped-articulation-loop-001 front-elbow-R authored keys",
    )
    owner_residual, worst_sample = maximum_owner_frame_residual(
        owner_frames=frames,
        uc_positions=packed.uc_positions,
        weights=packed.weights,
        uc_pivot=packed.uc_pivot,
        uc_axis=packed.uc_axis,
    )
    if owner_residual > POSE_TOLERANCE_M:
        raise ValueError(f"encoded skin/key deformation drift exceeds tolerance: {owner_residual}")

    args.out.mkdir(parents=True, exist_ok=True)
    glb_path = args.out / "animal_selected003_right_mirror_rigged_41key.glb"
    glb_path.write_bytes(packed.bytes)
    glb_sha256 = sha256_bytes(packed.bytes)
    uc_inspection = inspect_with_uc_codec(uc_root, glb_path)
    if uc_inspection.get("pass") is not True:
        raise ValueError(f"current UC rigged codec rejected emitted GLB: {uc_inspection.get('errors')}")
    if uc_inspection.get("vertices") != 42 or uc_inspection.get("triangles") != 80:
        raise ValueError("current UC rigged codec geometry count drift")
    if uc_inspection.get("skin", {}).get("joints") != 2:
        raise ValueError("current UC rigged codec skin joint-count drift")
    animation = uc_inspection.get("animation", {})
    if animation.get("channels") != 1 or animation.get("frames") != 41:
        raise ValueError("current UC rigged codec animation channel/key-count drift")
    if abs(float(animation.get("durationSeconds", -1.0)) - 1.0) > 1e-7:
        raise ValueError("current UC rigged codec duration drift")
    if uc_inspection.get("weightSumsPass") is not True or uc_inspection.get("jointIndicesPass") is not True:
        raise ValueError("current UC rigged codec weight/joint validation failed")
    deformation = uc_inspection.get("deformation", {})
    if deformation.get("pass") is not True or deformation.get("changed") is not True:
        raise ValueError("current UC rigged codec CPU deformation observer did not pass")

    # Fail-closed controls: source-rest drift and receiver-side weight drift.
    drifted_frames = copy.deepcopy(frames)
    drifted_frames[0]["positions"][0][0] = float(drifted_frames[0]["positions"][0][0]) + 0.001
    try:
        pack_exact_right_forelimb_glb(
            spec=spec,
            plan=plan,
            owner_frames=drifted_frames,
            indices=[int(value) for value in indices],
            source_material=material,
            clip_name="negative-control",
        )
    except ValueError as exc:
        source_drift_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise ValueError("+1 mm neutral-source drift unexpectedly passed exact endpoint closure gate")

    wrong_weight_residual = mutated_weight_residual(owner_frames=frames, packed=packed)
    if wrong_weight_residual <= POSE_TOLERANCE_M:
        raise ValueError("deliberate receiver-side weight drift unexpectedly remained within owner-frame tolerance")
    weight_drift_control = {
        "status": "PASS_REJECTED",
        "maximum_owner_frame_residual_m": wrong_weight_residual,
        "required_tolerance_m": POSE_TOLERANCE_M,
    }

    report = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "technical_art_head": args.technical_art_head,
        "scope": "exact Animal right mirror-surface forelimb -> two-joint skinned GLB -> current UC generic rigged codec",
        "owners": {
            "geometry": {"head": GEOMETRY_HEAD, "candidate_id": SOURCE_CANDIDATE_ID, "candidate_sha256": RIGHT_CANDIDATE_SHA256},
            "rigging": {"head": RIGGING_HEAD, "rig_donor_head": RIG_DONOR_HEAD, "rig_plan_sha256": RIG_PLAN_SHA256, "weighting": WEIGHTING_ID},
            "animation": {"head": ANIMATION_HEAD, "gate": ANIMATION_GATE, "clip_sha256": CLIP_SHA256, "key_count": 41, "duration_seconds": 1.0},
        },
        "transport": {
            "bridge_schema": BRIDGE_SCHEMA,
            "source_vertices": 42,
            "source_triangles": 80,
            "skin_joints": 2,
            "animation_channels": 1,
            "authored_keys": 41,
            "source_to_uc_component_map": "[x_forward,y_left,z_up] -> [-y_left,z_up,x_forward]",
            "rotation_axis_rule": "det(M) * M * source_axis",
            "source_axis": [0.0, 1.0, 0.0],
            "uc_axis": packed.uc_axis,
            "triangle_winding_reversed": True,
            "transport_only_normals": True,
            "glb_sha256": glb_sha256,
            "glb_bytes": len(packed.bytes),
            "maximum_authored_key_pose_residual_m": owner_residual,
            "worst_authored_key_sample_index": worst_sample,
            "pose_tolerance_m": POSE_TOLERANCE_M,
            "glb_interpolation_label": "LINEAR",
            "continuous_owner_curve_equivalence_claimed": False,
        },
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "head": UC_HEAD,
            "codec_path": UC_CODEC_PATH,
            "codec_blob": observed_codec_blob,
            "product_modified": False,
            "inspection": uc_inspection,
        },
        "negative_controls": {
            "neutral_source_plus_1mm": source_drift_control,
            "receiver_weight_drift": weight_drift_control,
            "uc_codec_blob_gate": "PASS_EXACT_BLOB",
        },
        "truth_boundary": {
            "proves": [
                "the exact Animation-owned right forelimb neutral topology can be encoded with the exact existing smoothstep-v0 right-elbow weights as a two-joint glTF skin",
                "all 41 authored right-elbow key poses reproduce the Animation-owned sampled positions within the retained numeric tolerance after the explicit handedness-aware coordinate transform",
                "current UC's existing generic rigged glTF codec accepts the emitted skin, joint indices, normalized weights, 41-key rotation channel and CPU deformation samples",
            ],
            "does_not_prove": [
                "whole-animal skeleton or four-joint skin export",
                "hind-leg animation transport",
                "continuous raised-cosine equivalence between authored keys; the GLB sampler is LINEAR",
                "final authored normals, tangents, UVs or shaded visual acceptance",
                "target-engine import or playback",
                "runtime controller or state-machine behavior",
                "collision, physics, gameplay or target-device performance",
                "CANON, production readiness or Technical Art mastery",
            ],
        },
    }
    (args.out / "uc_rigged_animation_transport_receipt.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "uc_codec_inspection.json").write_text(
        json.dumps(uc_inspection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.out / "technical-art-head.txt").write_text(args.technical_art_head + "\n", encoding="utf-8")
    (args.out / "animation-head.txt").write_text(ANIMATION_HEAD + "\n", encoding="utf-8")
    (args.out / "rigging-head.txt").write_text(RIGGING_HEAD + "\n", encoding="utf-8")
    (args.out / "uc-head.txt").write_text(UC_HEAD + "\n", encoding="utf-8")
    (args.out / "uc-codec-blob.txt").write_text(observed_codec_blob + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
