#!/usr/bin/env python3
"""Build exact topology evidence for the front-left connected-chain candidate.

Requires both this repository's ``src`` and Universal Creation's ``src`` on
PYTHONPATH. The CI workflow pins the UC revision explicitly.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from axm_animal_design.organic_form import build_form_study
from axm_animal_design.topology_study import build_connected_chain, derive_shared_ring_radii
from axm_uc.mesh_topology import inspect_mesh_topology

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "quadruped_neutral_001.json"
OUT = ROOT / "evidence" / "topology"
UC_COMMIT = "b434a349cf159b392148b4dc9d68146573531a60"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def flatten(primitives):
    positions = []
    indices = []
    for primitive in primitives:
        base = len(positions)
        positions.extend(primitive["positions"])
        indices.extend(base + index for index in primitive["indices"])
    return positions, indices


def main() -> None:
    spec = json.loads(SOURCE.read_text())
    baseline = build_form_study(spec)
    ids = ("front_upper_L", "front_lower_L", "front_paw_L")
    original = [primitive for primitive in baseline["surface"]["primitives"] if primitive["id"] in ids]
    if [primitive["id"] for primitive in original] != list(ids):
        raise SystemExit("expected front-left baseline regions not found in stable order")

    original_positions, original_indices = flatten(original)
    before = inspect_mesh_topology(original_positions, original_indices, weld_tolerance=1e-6)

    radius_derivation = derive_shared_ring_radii(spec["regions"], ids)
    expected_landmarks = ["shoulder_L", "elbow_L", "wrist_L", "front_paw_L"]
    if radius_derivation["path_landmarks"] != expected_landmarks:
        raise SystemExit("source region chain no longer resolves the expected authored landmark path")

    lm = spec["landmarks"]
    candidate = build_connected_chain(
        "front-left-connected-chain-001",
        [lm[name] for name in radius_derivation["path_landmarks"]],
        radius_derivation["radii_m"],
        segments=10,
    )
    after = inspect_mesh_topology(candidate["positions"], candidate["indices"], weld_tolerance=1e-6)

    gates = {
        "original-three-components-observed": "PASS" if before["triangle_component_count"] == 3 else "FAIL",
        "candidate-one-component": "PASS" if after["triangle_component_count"] == 1 else "FAIL",
        "candidate-no-open-edges": "PASS" if after["boundary_edge_count"] == 0 else "FAIL",
        "candidate-no-nonmanifold-edges": "PASS" if after["nonmanifold_edge_count"] == 0 else "FAIL",
        "candidate-shared-edge-orientation": "PASS" if after["orientation_conflict_edge_count"] == 0 else "FAIL",
        "candidate-no-collapse": "PASS" if after["collapsed_triangle_count"] == 0 else "FAIL",
        "candidate-radii-derived-from-source-regions": (
            "PASS" if candidate["radii"] == radius_derivation["radii_m"] else "FAIL"
        ),
    }
    status = "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"

    receipt = {
        "schema": "axm.animal-connected-chain-topology-evidence/v0.2",
        "status": status,
        "source_name": spec["name"],
        "source_digest": baseline["source_digest"],
        "source_surface_digest": baseline["surface_digest"],
        "source_prerequisite_head": "179fc6dc1a38de477e433a3842c4793e748928fb",
        "donor": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "commit": UC_COMMIT,
            "module": "src/axm_uc/mesh_topology.py",
            "license": "Apache-2.0",
            "runtime_checkout": os.environ.get("AXM_UC_CHECKOUT", "UNRECORDED_LOCAL_PATH"),
        },
        "scope": {
            "baseline_regions": list(ids),
            "candidate": candidate["id"],
            "landmarks": radius_derivation["path_landmarks"],
            "radii_m": candidate["radii"],
            "segments": candidate["segments"],
            "radius_derivation": radius_derivation,
        },
        "before": {
            "vertices": len(original_positions),
            "triangles": len(original_indices) // 3,
            "topology": before,
        },
        "after": {
            "vertices": len(candidate["positions"]),
            "triangles": len(candidate["indices"]) // 3,
            "topology": after,
            "candidate_digest": digest(candidate),
        },
        "delta": {
            "vertices": len(candidate["positions"]) - len(original_positions),
            "triangles": len(candidate["indices"]) // 3 - len(original_indices) // 3,
            "components": after["triangle_component_count"] - before["triangle_component_count"],
        },
        "gates": gates,
        "truth_boundary": {
            "canonical_organic_baseline_modified": False,
            "candidate_is_visual_acceptance": False,
            "candidate_is_deformation_acceptance": False,
            "candidate_is_self_intersection_proof": False,
            "candidate_is_game_ready": False,
            "uc_donor_pass_transferred_without_retest": False,
            "junction_radius_policy_is_source-authored": False,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "front_left_connected_chain.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")
    (OUT / "front_left_connected_chain_topology_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    if status != "PASS":
        raise SystemExit("topology evidence gates failed")
    print(json.dumps({
        "status": status,
        "before_components": before["triangle_component_count"],
        "after_components": after["triangle_component_count"],
        "before_vertices": len(original_positions),
        "after_vertices": len(candidate["positions"]),
        "before_triangles": len(original_indices) // 3,
        "after_triangles": len(candidate["indices"]) // 3,
        "radius_policy": radius_derivation["policy"],
        "wrist_radius_gap_m": radius_derivation["junctions"][1]["authored_radius_gap_m"],
        "candidate_digest": receipt["after"]["candidate_digest"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
