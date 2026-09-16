#!/usr/bin/env python3
"""Build a source-pinned Materials probe for bilateral topology shading review.

This does not change Animal source geometry or assign a production material. It
serializes the historical and exact-mirror right surfaces with one neutral
lookdev probe so a target renderer can measure whether connectivity alone
changes generated-normal shading.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_mirror_surface_topology import (
    derive_exact_mirror_surface_candidate,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.connected_deformation import digest

SCHEMA = "axm.animal-materials-bilateral-topology-shading-review/v0.1"
EXPECTED_GEOMETRY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_GEOMETRY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--geometry-module-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.geometry_head != EXPECTED_GEOMETRY_HEAD:
        raise SystemExit(f"unexpected Geometry donor head: {args.geometry_head}")
    if args.geometry_module_blob != EXPECTED_GEOMETRY_MODULE_BLOB:
        raise SystemExit(f"unexpected Geometry module blob: {args.geometry_module_blob}")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    rig_plan = _load(args.rig_plan)

    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise SystemExit(f"Geometry prerequisite is not PASS: {prerequisite['state']}")

    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise SystemExit(f"exact mirror topology candidate is not PASS: {topology['state']}")
    if historical_right["positions"] != exact_right["positions"]:
        raise SystemExit("topology review changed source-owned positions")
    if len(historical_right["indices"]) != len(exact_right["indices"]):
        raise SystemExit("topology review changed triangle budget")
    if historical_right["indices"] == exact_right["indices"]:
        raise SystemExit("historical and exact-mirror topology are unexpectedly identical")

    payload = {
        "schema": SCHEMA,
        "exact_geometry_donor_head": args.geometry_head,
        "exact_geometry_module_blob": args.geometry_module_blob,
        "source": {
            "base_source": spec.get("name"),
            "left_candidate_id": left["id"],
            "left_candidate_digest": digest(left),
            "historical_right_candidate_id": historical_right["id"],
            "historical_right_candidate_digest": digest(historical_right),
            "exact_mirror_right_candidate_id": exact_right["id"],
            "exact_mirror_right_candidate_digest": digest(exact_right),
        },
        "budget": {
            "vertex_count": len(historical_right["positions"]),
            "triangle_count": len(historical_right["indices"]) // 3,
            "positions_identical": historical_right["positions"] == exact_right["positions"],
            "index_count_identical": len(historical_right["indices"]) == len(exact_right["indices"]),
        },
        "variants": {
            "historical_right": {
                "positions": historical_right["positions"],
                "indices": historical_right["indices"],
            },
            "exact_mirror_right": {
                "positions": exact_right["positions"],
                "indices": exact_right["indices"],
            },
        },
        "normal_modes": ["face_split", "vertex_smooth"],
        "camera_contexts": ["three_quarter", "grazing"],
        "neutral_probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
        },
        "scope": {
            "single_changed_variable": "right triangle connectivity",
            "positions_held": True,
            "material_held": True,
            "lighting_held": True,
            "camera_per_context_held": True,
            "normal_generation_mode_compared_separately": True,
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_or_textures_checked": False,
            "authored_normals_or_tangents_checked": False,
            "deformation_acceptance_claimed": False,
            "runtime_acceptance_claimed": False,
            "visual_quality_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
