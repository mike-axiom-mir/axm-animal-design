#!/usr/bin/env python3
"""Build exact Geometry evidence for the Organic elbow source successor rebind."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.self_intersection import inspect_triangle_self_intersections
from axm_animal_design.source_successor_topology_rebind import (
    ORGANIC_SOURCE_HEAD,
    build_source_successor_topology_rebind,
)
from axm_uc.mesh_topology import inspect_mesh_topology

EVIDENCE_SCHEMA = "axm.animal-source-successor-topology-rebind-evidence/v0.1"
UC_COMMIT = "b434a349cf159b392148b4dc9d68146573531a60"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source = _load(args.source)
    profile = _load(args.profile)
    candidate, local = build_source_successor_topology_rebind(source, profile)

    uc_topology = inspect_mesh_topology(
        candidate["positions"], candidate["indices"], weld_tolerance=1e-6
    )
    uc_gates = {
        "one-triangle-component": uc_topology["triangle_component_count"] == 1,
        "no-boundary-edges": uc_topology["boundary_edge_count"] == 0,
        "no-nonmanifold-edges": uc_topology["nonmanifold_edge_count"] == 0,
        "shared-edge-orientation-consistent": uc_topology["orientation_conflict_edge_count"] == 0,
        "no-collapsed-triangles": uc_topology["collapsed_triangle_count"] == 0,
    }

    flipped_indices = list(candidate["indices"])
    flipped_indices[1], flipped_indices[2] = flipped_indices[2], flipped_indices[1]
    winding_negative = inspect_mesh_topology(
        candidate["positions"], flipped_indices, weld_tolerance=1e-6
    )
    winding_negative_detected = winding_negative["orientation_conflict_edge_count"] > 0

    crossing_positions = [
        [0.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],
        [0.0, 2.0, 0.0],
        [0.5, 0.5, -1.0],
        [0.5, 0.5, 1.0],
        [1.5, 0.5, 0.0],
    ]
    crossing_negative = inspect_triangle_self_intersections(
        crossing_positions, [0, 1, 2, 3, 4, 5]
    )
    crossing_negative_detected = crossing_negative["self_intersection_pair_count"] == 1

    all_gates = {
        "local-rebind-pass": local["state"] == "PASS_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND",
        **uc_gates,
        "winding-negative-control-detected": winding_negative_detected,
        "crossing-negative-control-detected": crossing_negative_detected,
    }
    state = (
        "PASS_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
        if all(all_gates.values())
        else "FAIL_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND"
    )

    receipt = {
        "schema": EVIDENCE_SCHEMA,
        "state": state,
        "scope": "exact Organic source-owned selected-003 successor at neutral source space",
        "organic_source_prerequisite_head": ORGANIC_SOURCE_HEAD,
        "uc_donor": {
            "repository": "mike-axiom-mir/axm-universal-creation",
            "commit": UC_COMMIT,
            "module": "src/axm_uc/mesh_topology.py",
            "role": "generic edge-topology observer only",
        },
        "candidate": {
            "id": candidate["id"],
            "vertex_count": len(candidate["positions"]),
            "triangle_count": len(candidate["indices"]) // 3,
            "source_successor_candidate_digest": local["source_successor_candidate_digest"],
            "selected_review_geometry_digest": local["selected_review_geometry_digest"],
            "baseline_topology_signature": local["baseline_topology_signature"],
            "successor_topology_signature": local["successor_topology_signature"],
            "moved_vertex_indices": local["moved_vertex_indices"],
        },
        "local_geometry_rebind": local,
        "uc_edge_topology": uc_topology,
        "negative_controls": {
            "single_triangle_winding_flip": {
                "detected": winding_negative_detected,
                "orientation_conflict_edge_count": winding_negative["orientation_conflict_edge_count"],
            },
            "crossing_nonadjacent_triangle_pair": {
                "detected": crossing_negative_detected,
                "self_intersection_pair_count": crossing_negative["self_intersection_pair_count"],
            },
        },
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in all_gates.items()},
        "handoff": {
            "organic_form": "source-owned successor identity is consumed unchanged; no source edit requested",
            "rigging": "rebind and rerun deformation evidence against this source-successor identity before transferring deformation claims",
            "visual_qa": "no new visual acceptance is implied by neutral-source topology PASS",
        },
        "non_claims": [
            "no source-shape improvement or anatomy/biology correctness",
            "no continuous or sampled deformation acceptance",
            "no ring-phase candidate adoption",
            "no normals, tangents, UV or material readiness",
            "no runtime, collision or gameplay readiness",
            "no CANON, production readiness, game readiness or Geometry mastery",
        ],
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-successor-topology-candidate.json").write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "source-successor-topology-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if state != "PASS_SOURCE_SUCCESSOR_EXACT_TOPOLOGY_REBIND":
        raise SystemExit("source-successor topology rebind evidence failed")

    print(json.dumps({
        "state": state,
        "vertices": len(candidate["positions"]),
        "triangles": len(candidate["indices"]) // 3,
        "triangle_components": uc_topology["triangle_component_count"],
        "boundary_edges": uc_topology["boundary_edge_count"],
        "nonmanifold_edges": uc_topology["nonmanifold_edge_count"],
        "orientation_conflicts": uc_topology["orientation_conflict_edge_count"],
        "collapsed_triangles": uc_topology["collapsed_triangle_count"],
        "static_self_intersections": local["static_self_intersections"]["self_intersection_pair_count"],
        "moved_vertex_indices": local["moved_vertex_indices"],
        "winding_negative_conflicts": winding_negative["orientation_conflict_edge_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
