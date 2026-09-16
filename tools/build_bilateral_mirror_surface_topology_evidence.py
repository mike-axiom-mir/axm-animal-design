#!/usr/bin/env python3
"""Build retained evidence for the bilateral exact-mirror surface topology repair."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_mirror_surface_topology import (
    inspect_exact_mirror_surface_repair,
)
from axm_uc.mesh_topology import inspect_mesh_topology


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_obj(path: Path, candidate: dict):
    lines = [f"# {candidate['id']}"]
    for x, y, z in candidate["positions"]:
        lines.append(f"v {x} {y} {z}")
    indices = candidate["indices"]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--uc-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    rig_plan = _load(args.rig_plan)

    left, candidate, record = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, rig_plan
    )
    if record["state"] != "PASS_BILATERAL_EXACT_MIRROR_SURFACE_TOPOLOGY_REPAIR":
        raise SystemExit(f"Geometry mirror-surface repair did not pass: {record['state']}")

    topology = inspect_mesh_topology(candidate["positions"], candidate["indices"])
    if topology["status"] != "CLOSED_ORIENTED_EDGE_MANIFOLD_CANDIDATE":
        raise SystemExit(f"UC topology observer rejected candidate: {topology['status']}")
    if topology["boundary_edge_count"] or topology["nonmanifold_edge_count"]:
        raise SystemExit("candidate has open or non-manifold edges")
    if topology["orientation_conflict_edge_count"] or topology["collapsed_triangle_count"]:
        raise SystemExit("candidate has orientation conflicts or collapsed triangles")
    if topology["triangle_component_count"] != 1:
        raise SystemExit("candidate is not one edge-connected triangle component")

    flipped = dict(candidate)
    flipped["indices"] = list(candidate["indices"])
    flipped["indices"][1], flipped["indices"][2] = flipped["indices"][2], flipped["indices"][1]
    negative = inspect_mesh_topology(flipped["positions"], flipped["indices"])
    if negative["status"] != "INVALID_EDGE_TOPOLOGY" or negative["orientation_conflict_edge_count"] != 3:
        raise SystemExit("winding negative control did not fail closed with three orientation conflicts")

    receipt = {
        **record,
        "exact_geometry_head": args.geometry_head,
        "rigging_donor_head": args.rigging_head,
        "uc_topology_donor_head": args.uc_head,
        "uc_candidate_topology": topology,
        "negative_control": {
            "kind": "flip-first-triangle-winding",
            "status": negative["status"],
            "orientation_conflict_edge_count": negative["orientation_conflict_edge_count"],
        },
        "review_handoff": {
            "visual_tradeoff": "Vertex positions and silhouette are unchanged, but 30 longitudinal quad diagonals change; generated flat/split normals or tangent-space shading may therefore differ and require direct Visual QA if this topology advances.",
            "rigging": "The dense rig probe is reused only to prove the returned surface-metric hold can be closed by topology. Rigging must explicitly rebind if this new topology identity advances.",
        },
    }

    _dump(args.out / "bilateral-mirror-surface-topology-receipt.json", receipt)
    _dump(args.out / "right-mirror-surface-topology-candidate.json", candidate)
    _write_obj(args.out / "left-source-successor.obj", left)
    _write_obj(args.out / "right-mirror-surface-topology-candidate.obj", candidate)
    (args.out / "README.txt").write_text(
        "Geometry-only exact mirror-surface topology evidence.\n"
        "No Organic source positions, rig parameters or weights are changed.\n"
        "The candidate changes right triangle connectivity only and remains non-CANON.\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
