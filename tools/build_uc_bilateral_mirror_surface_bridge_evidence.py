#!/usr/bin/env python3
"""Bridge Animal Geometry #13's exact mirror-surface successor through current UC.

Geometry owns source positions and topology. Technical Art only regenerates the
pinned owner evidence, adds transport-only normals plus the unchanged neutral
Animal material required by the existing portable surface contract, applies the
established Animal -> UC coordinate/winding conversion, and asks current UC to
publish and re-verify GLB bytes.
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

PINNED_GEOMETRY_COMMIT = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
PINNED_LEFT_SHA256 = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
PINNED_HISTORICAL_RIGHT_SHA256 = "262f536e0e522fd3e102cb16464c3757985fbb1dfcb3001df3b1f27b623b0115"
PINNED_RIGHT_MIRROR_SHA256 = "086ffe6f48af0cc3506871a4754b7395ba4c1fa3155eb4f420854a37e92181db"
PINNED_PREVIOUS_UC_COMMIT = "ecef151548736628cff62652a36be6eb1c7b1ad6"
PINNED_CURRENT_UC_COMMIT = "bb090c470379542d38d24eea403832400c84a7b4"
PINNED_PROCEDURAL_3D_BLOB = "cdb654d4d0f68a4ca7539d98a985d7a70cf7ee36"
BASE_PRODUCER_PASS = "PASS_BILATERAL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
MIRROR_PRODUCER_PASS = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_TOPOLOGY_REPAIR"
OUTPUT_SCHEMA = "axm.animal-bilateral-mirror-surface-uc-bridge-evidence/v0.1"
OUTPUT_STATUS = "PASS_BILATERAL_EXACT_MIRROR_SURFACE_TO_CURRENT_UC_GLB"
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


def emit_side(
    *,
    side: str,
    candidate: dict,
    expected_sha256: str,
    material: dict,
    source_evidence: dict,
    output_dir: Path,
) -> dict:
    require_candidate_identity(candidate, expected_sha256)
    material_sha256 = digest(material)
    uc_surface = adapt_geometry_candidate_for_uc(
        candidate,
        name=f"Quadruped selected-003 {side} forelimb exact-mirror topology transport",
        material=material,
    )
    surface_path = output_dir / f"quadruped_selected003_mirror_{side}_uc_surface.json"
    surface_path.write_text(json.dumps(uc_surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    glb_path = output_dir / f"quadruped_selected003_mirror_{side}_uc_bridge.glb"
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
    receipt["status"] = f"PASS_{side.upper()}_EXACT_MIRROR_SURFACE_TO_CURRENT_UC_GLB"
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

    base_dir = Path(os.environ.get("AXM_GEOMETRY_BASE_EVIDENCE", ""))
    mirror_dir = Path(os.environ.get("AXM_GEOMETRY_MIRROR_EVIDENCE", ""))
    left_path = base_dir / "left-source-successor-topology-candidate.json"
    historical_right_path = base_dir / "right-source-successor-topology-candidate.json"
    base_receipt_path = base_dir / "bilateral-source-successor-topology-rebind-receipt.json"
    mirror_right_path = mirror_dir / "right-mirror-surface-topology-candidate.json"
    mirror_receipt_path = mirror_dir / "bilateral-mirror-surface-topology-receipt.json"
    required = (left_path, historical_right_path, base_receipt_path, mirror_right_path, mirror_receipt_path)
    if any(not path.is_file() for path in required):
        raise RuntimeError("exact Geometry base + mirror-surface producer evidence is required")

    left = json.loads(left_path.read_text(encoding="utf-8"))
    historical_right = json.loads(historical_right_path.read_text(encoding="utf-8"))
    base_receipt = json.loads(base_receipt_path.read_text(encoding="utf-8"))
    mirror_right = json.loads(mirror_right_path.read_text(encoding="utf-8"))
    mirror_receipt = json.loads(mirror_receipt_path.read_text(encoding="utf-8"))

    if base_receipt.get("state") != BASE_PRODUCER_PASS:
        raise RuntimeError("bilateral Geometry base producer did not retain its exact PASS")
    base_local = base_receipt.get("local_geometry_rebind", {})
    if base_local.get("left", {}).get("successor_candidate_digest") != PINNED_LEFT_SHA256:
        raise RuntimeError("base producer left successor identity drift")
    if base_local.get("right", {}).get("successor_candidate_digest") != PINNED_HISTORICAL_RIGHT_SHA256:
        raise RuntimeError("base producer historical right successor identity drift")
    if base_local.get("organic_scope", {}).get("mirror", {}).get("maximum_position_residual_m") != 0.0:
        raise RuntimeError("source-owned bilateral mirror position residual drift")

    if mirror_receipt.get("state") != MIRROR_PRODUCER_PASS:
        raise RuntimeError("mirror-surface Geometry producer did not retain its exact PASS")
    candidate_topology = mirror_receipt.get("candidate_topology", {})
    face_correspondence = candidate_topology.get("face_correspondence", {})
    if candidate_topology.get("candidate_digest") != PINNED_RIGHT_MIRROR_SHA256:
        raise RuntimeError("mirror-surface right candidate identity drift")
    if candidate_topology.get("source_right_candidate_digest") != PINNED_HISTORICAL_RIGHT_SHA256:
        raise RuntimeError("mirror-surface producer historical-right prerequisite drift")
    if candidate_topology.get("vertex_count") != 42 or candidate_topology.get("triangle_count") != 80:
        raise RuntimeError("mirror-surface right geometry budget drift")
    if candidate_topology.get("longitudinal_quad_count") != 30:
        raise RuntimeError("mirror-surface longitudinal-quad scope drift")
    if candidate_topology.get("replaced_unoriented_triangle_sets") != 60:
        raise RuntimeError("mirror-surface replaced-triangle scope drift")
    if candidate_topology.get("unchanged_unoriented_triangle_sets") != 20:
        raise RuntimeError("mirror-surface unchanged-triangle scope drift")
    if face_correspondence.get("all_exact") is not True:
        raise RuntimeError("mirror-surface exact face correspondence was not retained")
    if face_correspondence.get("exact_triangle_record_matches") != 80:
        raise RuntimeError("mirror-surface exact triangle correspondence drift")

    require_candidate_identity(left, PINNED_LEFT_SHA256)
    require_candidate_identity(historical_right, PINNED_HISTORICAL_RIGHT_SHA256)
    require_candidate_identity(mirror_right, PINNED_RIGHT_MIRROR_SHA256)
    if historical_right.get("positions") != mirror_right.get("positions"):
        raise RuntimeError("mirror-surface successor unexpectedly moved source-owned right positions")
    if historical_right.get("indices") == mirror_right.get("indices"):
        raise RuntimeError("mirror-surface successor did not retain a distinct topology identity")
    if len(left.get("positions", [])) != 42 or len(left.get("indices", [])) // 3 != 80:
        raise RuntimeError("left source-successor geometry budget drift")
    if len(mirror_right.get("positions", [])) != 42 or len(mirror_right.get("indices", [])) // 3 != 80:
        raise RuntimeError("right mirror-surface geometry budget drift")

    donor_src = geometry_checkout / "src" / "axm_animal_design"
    organic = load_module("axm_mirror_surface_transport_organic_exact", donor_src / "organic_form.py")
    source_spec = json.loads((geometry_checkout / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))
    source_evidence = organic.build_form_study(source_spec)
    left_material = source_material(source_evidence, LEFT_REGIONS)
    right_material = source_material(source_evidence, RIGHT_REGIONS)
    if digest(left_material) != digest(right_material):
        raise RuntimeError("left/right neutral donor material identity diverged")

    output_dir = ROOT / "evidence" / "uc_bilateral_mirror_surface"
    output_dir.mkdir(parents=True, exist_ok=True)
    left_receipt = emit_side(
        side="left",
        candidate=left,
        expected_sha256=PINNED_LEFT_SHA256,
        material=left_material,
        source_evidence=source_evidence,
        output_dir=output_dir,
    )
    right_receipt = emit_side(
        side="right",
        candidate=mirror_right,
        expected_sha256=PINNED_RIGHT_MIRROR_SHA256,
        material=right_material,
        source_evidence=source_evidence,
        output_dir=output_dir,
    )

    drifted_right = copy.deepcopy(mirror_right)
    drifted_right["positions"][0][0] = round(float(drifted_right["positions"][0][0]) + 0.001, 9)
    try:
        require_candidate_identity(drifted_right, PINNED_RIGHT_MIRROR_SHA256)
    except ValueError as exc:
        right_position_drift_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise RuntimeError("right mirror-surface position drift was incorrectly accepted")

    try:
        require_candidate_identity(historical_right, PINNED_RIGHT_MIRROR_SHA256)
    except ValueError as exc:
        stale_topology_control = {"status": "PASS_REJECTED", "observed_error": str(exc)}
    else:
        raise RuntimeError("historical right topology was incorrectly accepted as mirror-surface successor")

    receipt = {
        "schema": OUTPUT_SCHEMA,
        "status": OUTPUT_STATUS,
        "technical_art_scope": "Geometry #13 exact mirror-surface successor -> current UC static GLB transport",
        "geometry": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "commit": PINNED_GEOMETRY_COMMIT,
            "base_producer_state": base_receipt["state"],
            "mirror_producer_state": mirror_receipt["state"],
            "base_producer_receipt_sha256": digest(base_receipt),
            "mirror_producer_receipt_sha256": digest(mirror_receipt),
            "left_candidate_sha256": PINNED_LEFT_SHA256,
            "historical_right_candidate_sha256": PINNED_HISTORICAL_RIGHT_SHA256,
            "right_mirror_surface_candidate_sha256": PINNED_RIGHT_MIRROR_SHA256,
            "right_positions_equal_historical_source_successor": historical_right["positions"] == mirror_right["positions"],
            "right_indices_distinct_from_historical_source_successor": historical_right["indices"] != mirror_right["indices"],
            "exact_mirrored_triangle_records": 80,
            "longitudinal_quads_retriangulated": 30,
            "replaced_unoriented_triangle_sets": 60,
            "unchanged_unoriented_triangle_sets": 20,
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
            "product_code_changed_by_this_lane": False,
        },
        "negative_controls": {
            "right_mirror_surface_position_drift": right_position_drift_control,
            "historical_right_topology_as_successor": stale_topology_control,
            "uc_procedural_blob_drift": {
                "status": "PASS_REJECTED_BY_EXACT_BLOB_GATE",
                "expected_blob": PINNED_PROCEDURAL_3D_BLOB,
            },
        },
        "visual_tradeoff_review": {
            "source_positions_and_silhouette_changed": False,
            "right_longitudinal_quad_diagonals_changed": 30,
            "transport_normals_are_final_authored_normals": False,
            "handoff": (
                "Geometry #13 changes right triangle membership without moving positions. Transport-only averaged "
                "normals can therefore change with topology; Materials PR #14 plus Visual QA / Art Direction retain "
                "authority over shading and perceptual acceptance."
            ),
        },
        "non_claims": [
            "no skeleton/skin/weight transport",
            "no pose/deformation transport",
            "no GLB animation channels",
            "no target-engine import/playback",
            "no final normals/tangents/UV/material look",
            "no visual/anatomy acceptance",
            "no gameplay/physics/performance acceptance",
            "no UC promotion of Animal semantics",
            "no CANON or production readiness",
        ],
        "truth": (
            "PASS proves only that Geometry PR #13's exact LEFT selected-003 source successor and exact RIGHT "
            "mirror-surface topology successor were regenerated through the owning Geometry evidence paths, "
            "identity-gated, given transport-only normals plus the unchanged neutral Animal material, converted "
            "through the existing Animal-to-UC coordinate boundary, emitted by current pinned UC as separate GLBs, "
            "and re-verified at 80 triangles each. It does not transfer Rigging, Animation, visual, runtime, "
            "gameplay, CANON or production acceptance."
        ),
    }
    receipt_path = output_dir / "quadruped_bilateral_mirror_surface_uc_bridge.evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": OUTPUT_STATUS,
        "geometry_commit": PINNED_GEOMETRY_COMMIT,
        "left_candidate_sha256": PINNED_LEFT_SHA256,
        "right_candidate_sha256": PINNED_RIGHT_MIRROR_SHA256,
        "left_verified_triangles": left_receipt["universal_creation"]["verification"]["triangles"],
        "right_verified_triangles": right_receipt["universal_creation"]["verification"]["triangles"],
        "current_uc_commit": PINNED_CURRENT_UC_COMMIT,
        "procedural_3d_blob": current_blob,
        "receipt": str(receipt_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
