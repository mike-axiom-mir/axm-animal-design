#!/usr/bin/env python3
"""Build a source-pinned Materials probe for the explicit logical-quad normal candidate.

This keeps Animal source positions, topology variants, neutral material, lighting and
camera intent separate from the one scoped question: does Geometry PR #16's explicit
logical-quad normal field reduce the topology-dependent shading delta observed by
Materials PR #14 in a real target renderer?
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_logical_quad_normals import (
    NORMAL_FIELD_ID,
    derive_logical_quad_normals,
    generated_triangle_smooth_normals,
)
from axm_animal_design.bilateral_mirror_surface_topology import (
    derive_exact_mirror_surface_candidate,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.connected_deformation import digest

SCHEMA = "axm.animal-materials-explicit-logical-quad-normal-review/v0.1"
EXPECTED_NORMAL_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
EXPECTED_NORMAL_MODULE_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
EXPECTED_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_TOPOLOGY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
EXPECTED_MATERIALS_BASELINE_HEAD = "96e998e5c793057836e01656aca9f71481439c9b"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--normal-head", required=True)
    parser.add_argument("--normal-module-blob", required=True)
    parser.add_argument("--topology-head", required=True)
    parser.add_argument("--topology-module-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.normal_head != EXPECTED_NORMAL_HEAD:
        raise SystemExit(f"unexpected explicit-normal donor head: {args.normal_head}")
    if args.normal_module_blob != EXPECTED_NORMAL_MODULE_BLOB:
        raise SystemExit(f"unexpected explicit-normal module blob: {args.normal_module_blob}")
    if args.topology_head != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit(f"unexpected topology donor head: {args.topology_head}")
    if args.topology_module_blob != EXPECTED_TOPOLOGY_MODULE_BLOB:
        raise SystemExit(f"unexpected topology module blob: {args.topology_module_blob}")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)

    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise SystemExit(f"topology prerequisite is not PASS: {prerequisite['state']}")

    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise SystemExit(f"exact-mirror topology candidate is not PASS: {topology['state']}")
    if historical_right["positions"] != exact_right["positions"]:
        raise SystemExit("explicit-normal review changed source-owned positions")
    if len(historical_right["indices"]) != len(exact_right["indices"]):
        raise SystemExit("explicit-normal review changed triangle budget")
    if historical_right["indices"] == exact_right["indices"]:
        raise SystemExit("historical and exact-mirror topology are unexpectedly identical")

    historical_field = derive_logical_quad_normals(historical_right)
    exact_field = derive_logical_quad_normals(exact_right)
    if historical_field["id"] != NORMAL_FIELD_ID or exact_field["id"] != NORMAL_FIELD_ID:
        raise SystemExit("unexpected logical-quad normal-field identity")
    if historical_field["normals"] != exact_field["normals"]:
        raise SystemExit("logical-quad explicit normal vectors are not diagonal-invariant")
    if historical_field["tangent_policy"] != "NOT_DEFINED_NO_UV_BASIS":
        raise SystemExit("unexpected historical tangent policy")
    if exact_field["tangent_policy"] != "NOT_DEFINED_NO_UV_BASIS":
        raise SystemExit("unexpected exact tangent policy")

    generated_historical = generated_triangle_smooth_normals(historical_right)
    generated_exact = generated_triangle_smooth_normals(exact_right)
    if generated_historical == generated_exact:
        raise SystemExit("triangle-generated control unexpectedly lost connectivity sensitivity")

    payload = {
        "schema": SCHEMA,
        "exact_normal_donor_head": args.normal_head,
        "exact_normal_module_blob": args.normal_module_blob,
        "exact_topology_donor_head": args.topology_head,
        "exact_topology_module_blob": args.topology_module_blob,
        "materials_baseline_head": EXPECTED_MATERIALS_BASELINE_HEAD,
        "source": {
            "base_source": spec.get("name"),
            "left_candidate_id": left["id"],
            "left_candidate_digest": digest(left),
            "historical_right_candidate_id": historical_right["id"],
            "historical_right_candidate_digest": digest(historical_right),
            "exact_mirror_right_candidate_id": exact_right["id"],
            "exact_mirror_right_candidate_digest": digest(exact_right),
            "normal_field_id": NORMAL_FIELD_ID,
            "historical_normal_field_digest": digest(historical_field),
            "exact_normal_field_digest": digest(exact_field),
        },
        "budget": {
            "vertex_count": len(historical_right["positions"]),
            "triangle_count": len(historical_right["indices"]) // 3,
            "positions_identical": historical_right["positions"] == exact_right["positions"],
            "index_count_identical": len(historical_right["indices"]) == len(exact_right["indices"]),
            "explicit_normal_vectors_identical": historical_field["normals"] == exact_field["normals"],
            "explicit_normal_count": len(exact_field["normals"]),
        },
        "variants": {
            "historical_right": {
                "positions": historical_right["positions"],
                "indices": historical_right["indices"],
                "explicit_normals": historical_field["normals"],
            },
            "exact_mirror_right": {
                "positions": exact_right["positions"],
                "indices": exact_right["indices"],
                "explicit_normals": exact_field["normals"],
            },
        },
        "normal_modes": ["vertex_generated", "logical_quad_explicit"],
        "camera_contexts": ["three_quarter", "grazing"],
        "neutral_probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
        },
        "scope": {
            "primary_question": "historical-vs-exact topology shading delta under generated versus identical explicit logical-quad vertex normals",
            "positions_held": True,
            "triangle_budget_held": True,
            "material_held": True,
            "lighting_held": True,
            "camera_per_context_held": True,
            "explicit_normal_vectors_held_across_topology_variants": True,
            "tangents_held_as": "NOT_DEFINED_NO_UV_BASIS",
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_or_textures_checked": False,
            "explicit_normal_candidate_checked": True,
            "tangents_checked": False,
            "deformation_acceptance_claimed": False,
            "runtime_acceptance_claimed": False,
            "visual_preference_claimed": False,
            "canon_claimed": False,
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
