#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_logical_quad_normals import derive_logical_quad_normals
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind
from axm_animal_design.connected_deformation import digest

SCHEMA = "axm.runtime-animal-explicit-normal-index-budget-payload/v0.1"
EXPECTED_PARENT = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--parent-head", required=True)
    parser.add_argument("--runtime-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.parent_head != EXPECTED_PARENT:
        raise SystemExit(f"unexpected exact Geometry parent: {args.parent_head}")

    spec = load(args.source)
    left_profile = load(args.left_profile)
    bilateral_profile = load(args.bilateral_profile)
    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite.get("state") != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise SystemExit("bilateral source-successor prerequisite is not PASS")
    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology.get("state") != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise SystemExit("exact mirror topology prerequisite is not PASS")
    field = derive_logical_quad_normals(exact_right)

    positions = exact_right["positions"]
    indices = exact_right["indices"]
    normals = field["normals"]
    if len(positions) != 42 or len(indices) != 240 or len(normals) != 42:
        raise SystemExit("exact Animal normal-index proof requires 42 vertices / 240 indices / 42 normals")

    payload = {
        "schema": SCHEMA,
        "runtime_head": args.runtime_head,
        "exact_geometry_normal_parent_head": args.parent_head,
        "source_candidate_id": exact_right.get("id"),
        "source_candidate_digest": digest(exact_right),
        "normal_field_id": field.get("id"),
        "normal_field_source_candidate_digest": field.get("source_candidate_digest"),
        "tangent_policy": field.get("tangent_policy"),
        "positions": positions,
        "indices": indices,
        "normals": normals,
        "source_vertex_count": len(positions),
        "source_index_count": len(indices),
        "source_triangle_count": len(indices) // 3,
        "normal_count": len(normals),
        "truth_boundary": {
            "source_positions_modified": False,
            "source_indices_modified": False,
            "normal_values_modified": False,
            "tangents_added": False,
            "runtime_candidate_changes_only_storage_indexing": True,
            "visual_acceptance_claimed": False,
            "target_device_performance_claimed": False,
            "canon_claimed": False,
        },
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("PASS_RUNTIME_ANIMAL_EXPLICIT_NORMAL_INDEX_PAYLOAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
