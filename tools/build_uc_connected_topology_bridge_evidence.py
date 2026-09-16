#!/usr/bin/env python3
"""Build exact Animal connected-Geometry -> current-UC -> GLB transport evidence.

This Technical Art proof deliberately rebuilds the connected candidate from the
exact Geometry revision instead of copying its geometry into the Technical Art
branch. Animal topology/material meaning remains Animal-owned; UC receives only
its existing portable surface contract.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
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

PINNED_GEOMETRY_COMMIT = "feb4b24cd36bcc879173138d240754f71db34834"
PINNED_CANDIDATE_SHA256 = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
PINNED_UC_COMMIT = "9a4ab8156772536526dd75bb2acab81e9b88f517"
REGION_IDS = ("front_upper_L", "front_lower_L", "front_paw_L")
CANDIDATE_ID = "front-left-connected-chain-001"
OUTPUT_NAME = "Quadruped neutral 001 connected forelimb transport"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"could not load module {name} from {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> int:
    geometry_checkout = Path(os.environ.get("AXM_ANIMAL_GEOMETRY_CHECKOUT", ""))
    observed_geometry_commit = os.environ.get("AXM_ANIMAL_GEOMETRY_COMMIT", "")
    observed_uc_commit = os.environ.get("AXM_UC_COMMIT", "")
    if observed_geometry_commit != PINNED_GEOMETRY_COMMIT:
        raise RuntimeError(
            f"AXM_ANIMAL_GEOMETRY_COMMIT must equal pinned Geometry commit {PINNED_GEOMETRY_COMMIT}"
        )
    if observed_uc_commit != PINNED_UC_COMMIT:
        raise RuntimeError(f"AXM_UC_COMMIT must equal pinned UC commit {PINNED_UC_COMMIT}")
    if not geometry_checkout.is_dir():
        raise RuntimeError("AXM_ANIMAL_GEOMETRY_CHECKOUT must point to the exact Geometry checkout")

    donor_src = geometry_checkout / "src" / "axm_animal_design"
    topology = load_module("axm_geometry_topology_exact", donor_src / "topology_study.py")
    organic = load_module("axm_geometry_organic_exact", donor_src / "organic_form.py")
    source_path = geometry_checkout / "examples" / "quadruped_neutral_001.json"
    source_spec = json.loads(source_path.read_text())
    source_evidence = organic.build_form_study(source_spec)

    radius_derivation = topology.derive_shared_ring_radii(source_spec["regions"], REGION_IDS)
    expected_landmarks = ["shoulder_L", "elbow_L", "wrist_L", "front_paw_L"]
    if radius_derivation["path_landmarks"] != expected_landmarks:
        raise RuntimeError("exact Geometry source no longer resolves the expected connected path")
    landmarks = source_spec["landmarks"]
    candidate = topology.build_connected_chain(
        CANDIDATE_ID,
        [landmarks[name] for name in radius_derivation["path_landmarks"]],
        radius_derivation["radii_m"],
        segments=10,
    )
    require_candidate_identity(candidate, PINNED_CANDIDATE_SHA256)

    by_id = {primitive["id"]: primitive for primitive in source_evidence["surface"]["primitives"]}
    if any(identifier not in by_id for identifier in REGION_IDS):
        raise RuntimeError("exact source surface no longer contains the three connected-candidate donor regions")
    source_materials = [by_id[identifier]["material"] for identifier in REGION_IDS]
    if any(material != source_materials[0] for material in source_materials[1:]):
        raise RuntimeError("connected source regions no longer share one exact neutral source material")
    source_material = copy.deepcopy(source_materials[0])
    source_material_sha256 = digest(source_material)

    uc_surface = adapt_geometry_candidate_for_uc(
        candidate,
        name=OUTPUT_NAME,
        material=source_material,
    )

    output_dir = ROOT / "evidence" / "uc_connected_topology"
    output_dir.mkdir(parents=True, exist_ok=True)
    surface_path = output_dir / "quadruped_connected_forelimb_uc_surface_001.json"
    surface_path.write_text(json.dumps(uc_surface, indent=2, sort_keys=True) + "\n")

    glb_path = output_dir / "quadruped_connected_forelimb_uc_bridge_001.glb"
    publish = publish_glb(glb_path, uc_surface, replace=True)
    glb_bytes = glb_path.read_bytes()
    glb_sha256 = hashlib.sha256(glb_bytes).hexdigest()
    if glb_sha256 != publish["sha256"]:
        raise RuntimeError("published GLB digest differs from retained on-disk bytes")

    verification = verify_glb(glb_bytes, expected_spec_digest=publish["specification_sha256"])
    candidate_triangles = len(candidate["indices"]) // 3
    if verification.get("triangles") != candidate_triangles:
        raise RuntimeError(
            f"triangle count changed across current UC bridge: {candidate_triangles} -> {verification.get('triangles')}"
        )

    receipt = build_connected_candidate_bridge_evidence(
        source_digest=source_evidence["source_digest"],
        source_surface_digest=source_evidence["surface_digest"],
        geometry_commit=PINNED_GEOMETRY_COMMIT,
        candidate=candidate,
        expected_candidate_sha256=PINNED_CANDIDATE_SHA256,
        source_material_sha256=source_material_sha256,
        uc_surface=uc_surface,
        uc_commit=PINNED_UC_COMMIT,
        glb_sha256=glb_sha256,
        uc_specification_sha256=publish["specification_sha256"],
        uc_verification=verification,
    )
    receipt["source"]["source_checkout"] = str(geometry_checkout)
    receipt["geometry"]["radius_derivation"] = radius_derivation
    receipt["counts"] = {
        "candidate_vertices": len(candidate["positions"]),
        "candidate_triangles": candidate_triangles,
        "verified_glb_triangles": verification["triangles"],
        "uc_primitives": len(uc_surface["primitives"]),
    }
    receipt["scope"] = {
        "static_geometry_transport": True,
        "transport_only_normals": True,
        "rig_weights_transport": False,
        "skeleton_transport": False,
        "animation_transport": False,
        "target_engine_import": False,
    }
    receipt["paths"] = {
        "geometry_source": str(source_path),
        "uc_surface": str(surface_path.relative_to(ROOT)),
        "glb": str(glb_path.relative_to(ROOT)),
    }

    drifted = copy.deepcopy(candidate)
    drifted["positions"][0][0] = round(drifted["positions"][0][0] + 0.001, 9)
    try:
        require_candidate_identity(drifted, PINNED_CANDIDATE_SHA256)
    except ValueError as exc:
        receipt["negative_controls"] = {
            "geometry_candidate_identity_drift": {
                "status": "PASS_REJECTED",
                "observed_error": str(exc),
            }
        }
    else:
        raise RuntimeError("geometry candidate identity-drift control was incorrectly accepted")

    receipt_path = output_dir / "quadruped_connected_forelimb_uc_bridge_001.evidence.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": receipt["status"],
        "geometry_commit": PINNED_GEOMETRY_COMMIT,
        "candidate_sha256": PINNED_CANDIDATE_SHA256,
        "candidate_vertices": receipt["counts"]["candidate_vertices"],
        "candidate_triangles": receipt["counts"]["candidate_triangles"],
        "uc_commit": PINNED_UC_COMMIT,
        "verified_glb_triangles": receipt["counts"]["verified_glb_triangles"],
        "glb_sha256": glb_sha256,
        "receipt": str(receipt_path.relative_to(ROOT)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
