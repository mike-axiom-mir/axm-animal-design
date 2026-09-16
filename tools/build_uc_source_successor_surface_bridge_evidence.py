#!/usr/bin/env python3
"""Bridge the exact Animal selected-003 source-successor surface through current UC.

This Technical Art proof consumes Geometry's own exact source-successor producer
output instead of copying Animal topology/form semantics into this lane or into
Universal Creation. Technical Art contributes only transport attributes and the
existing explicit Animal -> UC coordinate/material adapter.
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

PINNED_GEOMETRY_COMMIT = "eb5ce99798b646b6ab9705c0c914b898173f7cc1"
PINNED_SOURCE_SUCCESSOR_SHA256 = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
PINNED_SELECTED_GEOMETRY_SHA256 = "dfc58bebbbd6e3a73b96fa98dc31bbd6deace79bb1c5ed82671a78d8a048246a"
PINNED_PREVIOUS_UC_COMMIT = "9a4ab8156772536526dd75bb2acab81e9b88f517"
PINNED_CURRENT_UC_COMMIT = "2595788885faca5fbe69e1497b55d535aff51259"
PINNED_PROCEDURAL_3D_BLOB = "cdb654d4d0f68a4ca7539d98a985d7a70cf7ee36"
PRODUCER_PASS = "PASS_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
REGION_IDS = ("front_upper_L", "front_lower_L", "front_paw_L")
OUTPUT_NAME = "Quadruped selected-003 left forelimb source-successor transport"
OUTPUT_SCHEMA = "axm.animal-source-successor-uc-surface-bridge-evidence/v0.1"
OUTPUT_STATUS = "PASS_SOURCE_SUCCESSOR_GEOMETRY_TO_CURRENT_UC_GLB"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def exact_head(checkout: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()


def exact_blob(checkout: Path, path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", f"HEAD:{path}"], text=True
    ).strip()


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load module {name} from {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def require_env_path(name: str) -> Path:
    value = os.environ.get(name, "")
    path = Path(value)
    if not value or not path.is_dir():
        raise RuntimeError(f"{name} must point to an exact checkout directory")
    return path


def main() -> int:
    geometry_checkout = require_env_path("AXM_ANIMAL_GEOMETRY_CHECKOUT")
    previous_uc_checkout = require_env_path("AXM_PREVIOUS_UC_CHECKOUT")
    current_uc_checkout = require_env_path("AXM_UC_CHECKOUT")

    observed_geometry_commit = os.environ.get("AXM_ANIMAL_GEOMETRY_COMMIT", "")
    observed_previous_uc_commit = os.environ.get("AXM_PREVIOUS_UC_COMMIT", "")
    observed_current_uc_commit = os.environ.get("AXM_UC_COMMIT", "")
    if observed_geometry_commit != PINNED_GEOMETRY_COMMIT:
        raise RuntimeError("Geometry commit environment identity drift")
    if observed_previous_uc_commit != PINNED_PREVIOUS_UC_COMMIT:
        raise RuntimeError("previous UC commit environment identity drift")
    if observed_current_uc_commit != PINNED_CURRENT_UC_COMMIT:
        raise RuntimeError("current UC commit environment identity drift")
    if exact_head(geometry_checkout) != PINNED_GEOMETRY_COMMIT:
        raise RuntimeError("Geometry checkout HEAD drift")
    if exact_head(previous_uc_checkout) != PINNED_PREVIOUS_UC_COMMIT:
        raise RuntimeError("previous UC checkout HEAD drift")
    if exact_head(current_uc_checkout) != PINNED_CURRENT_UC_COMMIT:
        raise RuntimeError("current UC checkout HEAD drift")

    previous_blob = exact_blob(previous_uc_checkout, "src/axm_uc/procedural_3d.py")
    current_blob = exact_blob(current_uc_checkout, "src/axm_uc/procedural_3d.py")
    if previous_blob != PINNED_PROCEDURAL_3D_BLOB:
        raise RuntimeError("previous proven UC procedural_3d blob drift")
    if current_blob != PINNED_PROCEDURAL_3D_BLOB:
        raise RuntimeError("current UC procedural_3d blob drift")

    producer_dir = Path(os.environ.get("AXM_GEOMETRY_PRODUCER_EVIDENCE", ""))
    candidate_path = producer_dir / "source-successor-topology-candidate.json"
    producer_receipt_path = producer_dir / "source-successor-topology-rebind-receipt.json"
    if not candidate_path.is_file() or not producer_receipt_path.is_file():
        raise RuntimeError("exact Geometry producer evidence is required")

    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    if producer_receipt.get("state") != PRODUCER_PASS:
        raise RuntimeError("Geometry producer did not retain its exact PASS")
    if producer_receipt.get("candidate", {}).get("source_successor_candidate_digest") != PINNED_SOURCE_SUCCESSOR_SHA256:
        raise RuntimeError("Geometry producer source-successor identity drift")
    if producer_receipt.get("candidate", {}).get("selected_review_geometry_digest") != PINNED_SELECTED_GEOMETRY_SHA256:
        raise RuntimeError("Geometry producer selected-003 geometry identity drift")
    require_candidate_identity(candidate, PINNED_SOURCE_SUCCESSOR_SHA256)

    donor_src = geometry_checkout / "src" / "axm_animal_design"
    organic = load_module("axm_source_successor_organic_exact", donor_src / "organic_form.py")
    source_path = geometry_checkout / "examples" / "quadruped_neutral_001.json"
    source_spec = json.loads(source_path.read_text(encoding="utf-8"))
    source_evidence = organic.build_form_study(source_spec)

    by_id = {primitive["id"]: primitive for primitive in source_evidence["surface"]["primitives"]}
    if any(identifier not in by_id for identifier in REGION_IDS):
        raise RuntimeError("exact source surface no longer contains the three connected donor regions")
    source_materials = [by_id[identifier]["material"] for identifier in REGION_IDS]
    if any(material != source_materials[0] for material in source_materials[1:]):
        raise RuntimeError("source successor donor regions no longer share one neutral material")
    source_material = copy.deepcopy(source_materials[0])
    source_material_sha256 = digest(source_material)

    uc_surface = adapt_geometry_candidate_for_uc(
        candidate,
        name=OUTPUT_NAME,
        material=source_material,
    )

    output_dir = ROOT / "evidence" / "uc_source_successor_surface"
    output_dir.mkdir(parents=True, exist_ok=True)
    surface_path = output_dir / "quadruped_selected003_uc_surface.json"
    surface_path.write_text(json.dumps(uc_surface, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    glb_path = output_dir / "quadruped_selected003_uc_bridge.glb"
    publish = publish_glb(glb_path, uc_surface, replace=True)
    glb_bytes = glb_path.read_bytes()
    glb_sha256 = hashlib.sha256(glb_bytes).hexdigest()
    if glb_sha256 != publish["sha256"]:
        raise RuntimeError("published GLB digest differs from retained bytes")
    verification = verify_glb(glb_bytes, expected_spec_digest=publish["specification_sha256"])
    candidate_triangles = len(candidate["indices"]) // 3
    if verification.get("triangles") != candidate_triangles:
        raise RuntimeError("triangle count changed across current UC GLB bridge")

    receipt = build_connected_candidate_bridge_evidence(
        source_digest=source_evidence["source_digest"],
        source_surface_digest=source_evidence["surface_digest"],
        geometry_commit=PINNED_GEOMETRY_COMMIT,
        candidate=candidate,
        expected_candidate_sha256=PINNED_SOURCE_SUCCESSOR_SHA256,
        source_material_sha256=source_material_sha256,
        uc_surface=uc_surface,
        uc_commit=PINNED_CURRENT_UC_COMMIT,
        glb_sha256=glb_sha256,
        uc_specification_sha256=publish["specification_sha256"],
        uc_verification=verification,
    )
    receipt["schema"] = OUTPUT_SCHEMA
    receipt["status"] = OUTPUT_STATUS
    receipt["source_successor"] = {
        "geometry_producer_commit": PINNED_GEOMETRY_COMMIT,
        "producer_state": producer_receipt["state"],
        "candidate_id": candidate.get("id"),
        "candidate_sha256": PINNED_SOURCE_SUCCESSOR_SHA256,
        "selected_review_geometry_sha256": PINNED_SELECTED_GEOMETRY_SHA256,
        "moved_vertex_indices": producer_receipt.get("candidate", {}).get("moved_vertex_indices"),
        "producer_receipt_sha256": digest(producer_receipt),
        "producer_candidate_sha256": digest(candidate),
    }
    receipt["universal_creation"]["previous_proven_surface_commit"] = PINNED_PREVIOUS_UC_COMMIT
    receipt["universal_creation"]["previous_procedural_3d_blob"] = previous_blob
    receipt["universal_creation"]["current_procedural_3d_blob"] = current_blob
    receipt["universal_creation"]["procedural_3d_blob_unchanged"] = previous_blob == current_blob
    receipt["counts"] = {
        "candidate_vertices": len(candidate["positions"]),
        "candidate_triangles": candidate_triangles,
        "verified_glb_triangles": verification["triangles"],
        "uc_primitives": len(uc_surface["primitives"]),
    }
    receipt["scope"] = {
        "static_source_successor_geometry_transport": True,
        "transport_only_normals": True,
        "source_material_transport": True,
        "rig_weights_transport": False,
        "skeleton_transport": False,
        "pose_transport": False,
        "animation_channel_transport": False,
        "target_engine_import": False,
        "right_side_successor_transport": False,
    }
    receipt["truth"] = (
        "PASS proves only that Geometry's exact source-owned selected-003 LEFT successor was regenerated by its "
        "own producer, preserved by exact digest, given transport-only normals plus the unchanged neutral Animal "
        "material, explicitly converted through the established Animal-to-UC coordinate boundary, emitted by "
        "the current pinned UC GLB generator, and re-verified with the same triangle count. It does not prove "
        "skeleton/skin/weight/pose transport, animation channels, RIGHT-side adoption, engine import/playback, "
        "visual quality, gameplay, performance, CANON or production readiness."
    )

    drifted = copy.deepcopy(candidate)
    drifted["positions"][0][0] = round(float(drifted["positions"][0][0]) + 0.001, 9)
    try:
        require_candidate_identity(drifted, PINNED_SOURCE_SUCCESSOR_SHA256)
    except ValueError as exc:
        receipt["negative_controls"] = {
            "source_successor_candidate_identity_drift": {
                "status": "PASS_REJECTED",
                "observed_error": str(exc),
            },
            "uc_procedural_blob_drift": {
                "status": "PASS_REJECTED_BY_EXACT_BLOB_GATE",
                "expected_blob": PINNED_PROCEDURAL_3D_BLOB,
            },
        }
    else:
        raise RuntimeError("source-successor candidate identity drift was incorrectly accepted")

    receipt_path = output_dir / "quadruped_selected003_uc_bridge.evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": receipt["status"],
        "geometry_commit": PINNED_GEOMETRY_COMMIT,
        "candidate_sha256": PINNED_SOURCE_SUCCESSOR_SHA256,
        "candidate_vertices": receipt["counts"]["candidate_vertices"],
        "candidate_triangles": receipt["counts"]["candidate_triangles"],
        "previous_uc_commit": PINNED_PREVIOUS_UC_COMMIT,
        "current_uc_commit": PINNED_CURRENT_UC_COMMIT,
        "procedural_3d_blob": current_blob,
        "verified_glb_triangles": receipt["counts"]["verified_glb_triangles"],
        "glb_sha256": glb_sha256,
        "receipt": str(receipt_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
