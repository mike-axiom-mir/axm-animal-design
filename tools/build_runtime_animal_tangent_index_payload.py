#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_uv_tangent_basis import inspect_bilateral_uv_tangent_basis

SCHEMA = "axm.runtime-animal-tangent-index-budget-payload/v0.1"
EXPECTED_RIGGING_PARENT = "63c65d57fda0595217f86d971ff8c67f256188be"
EXPECTED_GEOMETRY_BASIS = "ca4bb8a2f144231f8755eacc980785d1807b79db"
EXPECTED_BASIS_STATE = "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD"


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--rigging-parent-head", required=True)
    parser.add_argument("--geometry-basis-head", required=True)
    parser.add_argument("--runtime-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.rigging_parent_head != EXPECTED_RIGGING_PARENT:
        raise SystemExit(f"unexpected exact Rigging parent: {args.rigging_parent_head}")
    if args.geometry_basis_head != EXPECTED_GEOMETRY_BASIS:
        raise SystemExit(f"unexpected exact Geometry UV/tangent head: {args.geometry_basis_head}")

    left_basis, right_basis, record = inspect_bilateral_uv_tangent_basis(
        load(args.source), load(args.left_profile), load(args.bilateral_profile)
    )
    if record.get("state") != EXPECTED_BASIS_STATE:
        raise SystemExit(f"Geometry UV/tangent prerequisite not PASS: {record.get('state')}")

    basis = right_basis
    positions = basis["render_positions"]
    normals = basis["render_normals"]
    uvs = basis["render_uvs"]
    tangents = basis["render_tangents"]
    indices = basis["render_indices"]

    if basis.get("source_vertex_count") != 42:
        raise SystemExit("expected 42 source vertices")
    if basis.get("render_vertex_count") != 84:
        raise SystemExit("expected exact 84-vertex tangent-ready render domain")
    if len(indices) != 240 or basis.get("triangle_count") != 80:
        raise SystemExit("expected exact 240 indices / 80 triangles")
    if not (len(positions) == len(normals) == len(uvs) == len(tangents) == 84):
        raise SystemExit("render attribute count drift")

    # Bounded logical storage model: float32 position(3), normal(3), uv(2), tangent(4), uint32 index.
    vertex_bytes = 48
    control_bytes = len(indices) * vertex_bytes
    candidate_bytes = len(positions) * vertex_bytes + len(indices) * 4
    delta_bytes = candidate_bytes - control_bytes

    payload = {
        "schema": SCHEMA,
        "runtime_head": args.runtime_head,
        "exact_rigging_parent_head": args.rigging_parent_head,
        "exact_geometry_basis_head": args.geometry_basis_head,
        "basis_id": basis.get("id"),
        "source_candidate_id": basis.get("source_candidate_id"),
        "source_candidate_digest": basis.get("source_candidate_digest"),
        "side": basis.get("side"),
        "source_vertex_count": basis["source_vertex_count"],
        "render_vertex_count": basis["render_vertex_count"],
        "render_index_count": len(indices),
        "triangle_count": basis["triangle_count"],
        "render_positions": positions,
        "render_normals": normals,
        "render_uvs": uvs,
        "render_tangents": tangents,
        "render_indices": indices,
        "render_source_indices": basis["render_source_indices"],
        "semantic_vertex_keys": basis["semantic_vertex_keys"],
        "modeled_storage": {
            "vertex_stride_bytes": vertex_bytes,
            "index_stride_bytes": 4,
            "unindexed_control_bytes": control_bytes,
            "indexed_candidate_bytes": candidate_bytes,
            "delta_bytes": delta_bytes,
            "reduction_bytes": -delta_bytes,
            "reduction_fraction": (-delta_bytes) / control_bytes,
        },
        "truth_boundary": {
            "source_geometry_modified": False,
            "render_domain_modified": False,
            "uvs_modified": False,
            "normals_modified": False,
            "tangents_modified": False,
            "triangle_order_modified": False,
            "candidate_changes_only_storage_indexing": True,
            "final_uv_or_tangent_visual_acceptance_claimed": False,
            "deformed_shaded_acceptance_claimed": False,
            "transport_claimed": False,
            "target_device_performance_claimed": False,
            "canon_claimed": False,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("PASS_RUNTIME_ANIMAL_TANGENT_INDEX_PAYLOAD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
