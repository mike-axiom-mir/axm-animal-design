#!/usr/bin/env python3
"""Build exact Geometry evidence for bilateral Organic elbow source successors."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_source_successor_topology_rebind import (
    HISTORICAL_LEFT_GEOMETRY_HEAD,
    ORGANIC_BILATERAL_HEAD,
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.self_intersection import inspect_triangle_self_intersections
from axm_uc.mesh_topology import inspect_mesh_topology

EVIDENCE_SCHEMA = "axm.animal-bilateral-source-successor-topology-rebind-evidence/v0.1"
UC_COMMIT = "b434a349cf159b392148b4dc9d68146573531a60"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _uc_observe(candidate):
    observed = inspect_mesh_topology(candidate["positions"], candidate["indices"], weld_tolerance=1e-6)
    gates = {
        "one-triangle-component": observed["triangle_component_count"] == 1,
        "no-boundary-edges": observed["boundary_edge_count"] == 0,
        "no-nonmanifold-edges": observed["nonmanifold_edge_count"] == 0,
        "shared-edge-orientation-consistent": observed["orientation_conflict_edge_count"] == 0,
        "no-collapsed-triangles": observed["collapsed_triangle_count"] == 0,
    }
    return observed, gates


def _winding_negative(candidate):
    flipped = list(candidate["indices"])
    flipped[1], flipped[2] = flipped[2], flipped[1]
    observed = inspect_mesh_topology(candidate["positions"], flipped, weld_tolerance=1e-6)
    return {
        "detected": observed["orientation_conflict_edge_count"] > 0,
        "orientation_conflict_edge_count": observed["orientation_conflict_edge_count"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    left, right, local = build_bilateral_source_successor_topology_rebind(
        source, left_profile, bilateral_profile
    )

    left_uc, left_uc_gates = _uc_observe(left)
    right_uc, right_uc_gates = _uc_observe(right)
    left_winding = _winding_negative(left)
    right_winding = _winding_negative(right)

    crossing_positions = [
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
        [0.5, 0.5, -1.0],
        [0.5, 0.5, 1.0],
        [1.5, 0.5, 0.0],
    ]
    crossing = inspect_triangle_self_intersections(
        crossing_positions, [0, 1, 2, 3, 4, 5]
    )
    crossing_detected = crossing["self_intersection_pair_count"] == 1

    gates = {
        "local-bilateral-rebind-pass": local["state"] == "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND",
        **{f"left-uc-{name}": value for name, value in left_uc_gates.items()},
        **{f"right-uc-{name}": value for name, value in right_uc_gates.items()},
        "left-winding-negative-control-detected": left_winding["detected"],
        "right-winding-negative-control-detected": right_winding["detected"],
        "crossing-negative-control-detected": crossing_detected,
    }
    state = (
        "PASS_BILATERAL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
        if all(gates.values())
        else "FAIL_BILATERAL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
    )

    receipt = {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "scope": "exact Organic selected-003 bilateral source successors at neutral source space",
        "organic_bilateral_prerequisite_head": ORGANIC_BILATERAL_HEAD,
        "historical_left_geometry_head": HISTORICAL_LEFT_GEOMETRY_HEAD,
        "uc_donor": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "commit": UC_COMMIT,
            "module": "src/axm_uc/mesh_topology.py",
            "role": "generic edge-topology observer only",
        },
        "local_geometry_rebind": local,
        "uc_edge_topology": {"left": left_uc, "right": right_uc},
        "negative_controls": {
            "left_single_triangle_winding_flip": left_winding,
            "right_single_triangle_winding_flip": right_winding,
            "crossing_nonadjacent_triangle_pair": {
                "detected": crossing_detected,
                "self_intersection_pair_count": crossing["self_intersection_pair_count"],
            },
        },
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
        "handoff": {
            "organic_form": "both source-owned successors consumed unchanged; no source edit requested",
            "rigging": "right-side weighting/deformation must explicitly rebind to this exact right successor before transfer",
            "animation": "no bilateral motion acceptance transfers from left-only evidence",
            "visual_qa": "exact mirror plus neutral topology PASS is not bilateral deformation or visual acceptance",
        },
        "non_claims": [
            "no anatomy/biology correctness",
            "no sampled or continuous deformation acceptance",
            "no weighting or animation acceptance",
            "no final normals, tangents, UV or material readiness",
            "no runtime, collision or gameplay readiness",
            "no CANON, production readiness, game readiness or Geometry mastery",
        ],
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "left-source-successor-topology-candidate.json").write_text(
        json.dumps(left, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "right-source-successor-topology-candidate.json").write_text(
        json.dumps(right, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "bilateral-source-successor-topology-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if state != "PASS_BILATERAL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND":
        raise SystemExit("bilateral source-successor topology rebind evidence failed")

    print(json.dumps({
        "state": state,
        "left_vertices": len(left["positions"]),
        "right_vertices": len(right["positions"]),
        "left_triangles": len(left["indices"]) // 3,
        "right_triangles": len(right["indices"]) // 3,
        "left_static_self_intersections": local["left"]["static_self_intersections"]["self_intersection_pair_count"],
        "right_static_self_intersections": local["right"]["static_self_intersections"]["self_intersection_pair_count"],
        "left_uc_orientation_conflicts": left_uc["orientation_conflict_edge_count"],
        "right_uc_orientation_conflicts": right_uc["orientation_conflict_edge_count"],
        "mirror_position_residual_m": local["organic_scope"]["mirror"]["maximum_position_residual_m"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
