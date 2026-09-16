#!/usr/bin/env python3
"""Bridge the exact bilateral Animal selected-003 source successors through current UC.

Geometry owns both source-successor meshes. Technical Art only regenerates the
pinned producer evidence, adds transport-only normals/materials required by the
existing portable surface contract, applies the established Animal -> UC axis
conversion, and asks current UC to publish/re-verify GLB bytes.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.uc_bridge import (
    adapt_geometry_candidate_for_uc,
    build_connected_candidate_bridge_evidence,
    require_candidate_identity,
)
from axm_uc.procedural_3d import publish_glb, verify_glb

PINNED_GEOMETRY_COMMIT = "f89af95d621c36da3994c6660552da8bbc73fd1b"
PINNED_LEFT_SHA256 = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
PINNED_RIGHT_SHA256 = "262f536e0e522fd3e102cb16464c3757985fbb1dfcb3001df3b1f27b623b0115"
PINNED_PREVIOUS_UC_COMMIT = "2595788885faca5fbe69e1497b55d535aff51259"
PINNED_CURRENT_UC_COMMIT = "ecef151548736628cff62652a36be6eb1c7b1ad6"
PINNED_PROCEDURAL_3D_BLOB = "cdb654d4d0f68a4ca7539d98a985d7a70cf7ee36"
PRODUCER_PASS = "PASS_BILATERAL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
OUTPUT_SCHEMA = "axm.animal-bilateral-source-successor-uc-surface-bridge-evidence/v0.1"
OUTPUT_STATUS = "PASS_BILATERAL_SOURCE_SUCCESSOR_GEOMETRY_TO_CURRENT_UC_GLB"
LEFT_REGIONS = ("front_upper_L", "front_lower_L", "front_paw_L")
RIGHT_REGIONS = ("front_upper_R", "front_lower_R", "front_paw_R")


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def exact_head(checkout: Path) -> str:
    return subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()


def exact_blob(checkout: Path, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", f"HEAD:{path}"], text=True
    ).strip()


def require_env_path(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_dir():
        raise RuntimeError(f"{name} must point to an exact checkout directory")
    return path


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load module {name} from {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def source_material(source_evidence: dict, region_ids: tuple[str, ...]) -> dict:
    by_id = {primitive["id"]: primitive for primitive in source_evidence["surface"]["primitives"]}
    if any(identifier not in by_id for identifier in region_ids):
        raise RuntimeError("exact source surface no longer contains required donor regions")
    materials = [by_id[identifier]["material"] for identifier in region_ids]
    if any(material != materials[0] for material in materials[1:]):
        raise RuntimeError("source-successor donor regions no longer share one neutral material")
    return copy.deepcopy(materials[0])


def emit_side(*, side: str, candidate: dict, expected_sha256: str, material: dict,
              source_evidence: dict, output_dir: Path) -> dict:
    require_candidate_identity(candidate, expected_sha256)
    material_sha256 = digest(material)
    uc_surface = adapt_geometry_candidate_for_uc(
        candidate,
        name=f"Quadruped selected-003 {side} forelimb bilateral source-successor transport",
        material=material,
    )
    surface_path = output_dir / f"quadruped_selected003_{side}_uc_surface.json"
    surface_path.write_text(json.dumps(uc_surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    glb_path = output_dir / f"quadruped_selected003_{side}_uc_bridge.glb"
    publish = publish_glb(glb_path, uc_surface, replace=True)
    glb_bytes = glb_path.read_bytes()
    glb_sha256 = hashlib.sha256(glb_bytes).hexdigest()
    if glb_sha256 != publish["sha256"]:
        raise RuntimeError(f"{side} published GLB digest differs from retained bytes")
    verification = verify_glb(glb_bytes, expected_spec_digest=publish["specification_sha256"])
    triangles = len(candidate["indices"]) // 3
    if verification.get("triangles") != triangles:
        raise RuntimeError(f"{side} triangle count changed across current UC GLB bridge")

    receipt = build_connected_candidate_bridge_evidence(
        source_digest=source_evidence["source_digest"],
        source_surface_digest=source_evidence["surface_digest"],
        geometry_commit=PINNED_GEOMETRY_COMMIT,
        candidate=candidate,
        expected_candidate_sha256=expected_sha256,
        source_material_sha256=material_sha256,
        uc_surface=uc_surface,
        uc_commit=PINNED_CURRENT_UC_COMMIT,
        glb_sha256=glb_sha256,
        uc_specification_sha256=publish["specification_sha256"],
        uc_verification=verification,
    )
    receipt["side"] = side
    receipt["status"] = f"PASS_{side.upper()}_SOURCE_SUCCESSOR_TO_CURRENT_UC_GLB"
    receipt["transport_scope"] = {
        "static_geometry": True,
        "transport_only_normals": True,
        "neutral_source_material": True,
        "skeleton_skin_weights": False,
        "pose_deformation": False,
        "animation_channels": False,
        "target_engine_import": False,
    }
    return receipt


def main() -> int:
    geometry_checkout = require_env_path("AXM_ANIMAL_GEOMETRY_CHECKOUT")
    previous_uc_checkout = require_env_path("AXM_PREVIOUS_UC_CHECKOUT")
    current_uc_checkout = require_env_path("AXM_UC_CHECKOUT")

    if os.environ.get("AXM_ANIMAL_GEOMETRY_COMMIT", "") != PINNED_GEOMETRY_COMMIT:
        raise RuntimeError("Geometry commit environment identity drift")
    if os.environ.get("AXM_PREVIOUS_UC_COMMIT", "") != PINNED_PREVIOUS_UC_COMMIT:
        raise RuntimeError("previous UC commit environment identity drift")
    if os.environ.get("AXM_UC_COMMIT", "") != PINNED_CURRENT_UC_COMMIT:
        raise RuntimeError("current UC commit environment identity drift")
    if exact_head(geometry_checkout) != PINNED_GEOMETRY_COMMIT:
        raise RuntimeError("Geometry checkout HEAD drift")
    if exact_head(previous_uc_checkout) != PINNED_PREVIOUS_UC_COMMIT:
        raise RuntimeError("previous UC checkout HEAD drift")
    if exact_head(current_uc_checkout) != PINNED_CURRENT_UC_COMMIT:
        raise RuntimeError("current UC checkout HEAD drift")

    previous_blob = exact_blob(previous_uc_checkout, "src/axm_uc/procedural_3d.py")
    current_blob = exact_blob(current_uc_checkout, "src/axm_uc/procedural_3d.py")
    if previous_blob != PINNED_PROCEDURAL_3D_BLOB or current_blob != PINNED_PROCEDURAL_3D_BLOB:
        raise RuntimeError("UC procedural_3d blob drift")

    producer_dir = Path(os.environ.get("AXM_GEOMETRY_PRODUCER_EVIDENCE", ""))
    left_path = producer_dir / "left-source-successor-topology-candidate.json"
    right_path = producer_dir / "right-source-successor-topology-candidate.json"
    producer_receipt_path = producer_dir / "bilateral-source-successor-topology-rebind-receipt.json"
    if not left_path.is_file() or not right_path.is_file() or not producer_receipt_path.is_file():
        raise RuntimeError("exact bilateral Geometry producer evidence is required")

    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    if producer_receipt.get("state") != PRODUCER_PASS:
        raise RuntimeError("bilateral Geometry producer did not retain its exact PASS")
    local = producer_receipt.get("local_geometry_rebind", {})
    if local.get("left", {}).get("successor_candidate_digest") != PINNED_LEFT_SHA256:
        raise RuntimeError("bilateral producer left successor identity drift")
    if local.get("right", {}).get("successor_candidate_digest") != PINNED_RIGHT_SHA256:
        raise RuntimeError("bilateral producer right successor identity drift")
    if local.get("organic_scope", {}).get("mirror", {}).get("maximum_position_residual_m") != 0.0:
        raise RuntimeError("source-owned bilateral mirror position residual drift")
    require_candidate_identity(left, PINNED_LEFT_SHA256)
    require_candidate_identity(right, PINNED_RIGHT_SHA256)

    donor_src = geometry_checkout / "src" / "axm_animal_design"
    organic = load_module("axm_bilateral_transport_organic_exact", donor_src / "organic_form.py")
    source_spec = json.loads((geometry_checkout / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))
    source_evidence = organic.build_form_study(source_spec)
    left_material = source_material(source_evidence, LEFT_REGIONS)
    right_material = source_material(source_evidence, RIGHT_REGIONS)
    if digest(left_material) != digest(right_material):
        raise RuntimeError("left/right neutral donor material identity diverged")

    output_dir = ROOT / "evidence" / "uc_bilateral_source_successor_surface"
    output_dir.mkdir(parents=True, exist_ok=True)
    left_receipt = emit_side(
        side="left", candidate=left, expected_sha256=PINNED_LEFT_SHA256,
        material=left_material, source_evidence=source_evidence, output_dir=output_dir,
    )
    right_receipt = emit_side(
        side="right", candidate=right, expected_sha256=PINNED_RIGHT_SHA256,
        material=right_material, source_evidence=source_evidence, output_dir=output_dir,
    )

    drifted_right = copy.deepcopy(right)
    drifted_right["positions"][0][0] = round(float(drifted_right["positions"][0][0]) + 0.001, 9)
    try:
        require_candidate_identity(drifted_right, PINNED_RIGHT_SHA256)
    except ValueError as exc:
        right_drift_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise RuntimeError("right source-successor identity drift was incorrectly accepted")

    receipt = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "technical_art_scope": "current bilateral Geometry producer -> current UC static GLB transport",
        "geometry": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "commit": PINNED_GEOMETRY_COMMIT,
            "producer_state": producer_receipt["state"],
            "producer_receipt_sha256": digest(producer_receipt),
            "left_candidate_sha256": PINNED_LEFT_SHA256,
            "right_candidate_sha256": PINNED_RIGHT_SHA256,
            "source_mirror_position_residual_m": 0.0,
        },
        "left": left_receipt,
        "right": right_receipt,
        "universal_creation": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "previous_proven_surface_commit": PINNED_PREVIOUS_UC_COMMIT,
            "current_commit": PINNED_CURRENT_UC_COMMIT,
            "previous_procedural_3d_blob": previous_blob,
            "current_procedural_3d_blob": current_blob,
            "procedural_3d_blob_unchanged": previous_blob == current_blob,
        },
        "negative_controls": {
            "right_source_successor_candidate_identity_drift": right_drift_control,
            "uc_procedural_blob_drift": {
                "status": "PASS_REJECTED_BY_EXACT_BLOB_GATE",
                "expected_blob": PINNED_PROCEDURAL_3D_BLOB,
            },
        },
        "non_claims": [
            "no skeleton/skin/weight transport",
            "no pose/deformation transport",
            "no GLB animation channels",
            "no target-engine import/playback",
            "no final normals/tangents/UV/material look",
            "no visual/anatomy acceptance",
            "no gameplay/physics/performance acceptance",
            "no CANON or production readiness",
        ],
        "truth": (
            "PASS proves only that Geometry PR #11's exact source-owned LEFT and RIGHT selected-003 static "
            "successors were regenerated through the owning producer, preserved by exact candidate identities, "
            "given transport-only normals plus the unchanged neutral Animal material, converted through the "
            "existing Animal-to-UC coordinate boundary, emitted by current pinned UC as separate GLBs, and "
            "re-verified at the original triangle counts. It does not transfer Rigging, Animation, visual, "
            "runtime, gameplay, CANON or production acceptance."
        ),
    }
    receipt_path = output_dir / "quadruped_bilateral_selected003_uc_bridge.evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": OUTPUT_STATUS,
        "geometry_commit": PINNED_GEOMETRY_COMMIT,
        "left_candidate_sha256": PINNED_LEFT_SHA256,
        "right_candidate_sha256": PINNED_RIGHT_SHA256,
        "left_verified_triangles": left_receipt["universal_creation"]["verification"]["triangles"],
        "right_verified_triangles": right_receipt["universal_creation"]["verification"]["triangles"],
        "current_uc_commit": PINNED_CURRENT_UC_COMMIT,
        "procedural_3d_blob": current_blob,
        "receipt": str(receipt_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
