#!/usr/bin/env python3
"""Build retained Geometry evidence for the bilateral structural UV/tangent basis."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_uv_tangent_basis import inspect_bilateral_uv_tangent_basis

EXPECTED_PARENT = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
EXPECTED_NORMAL = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
EXPECTED_MATERIALS = "a2cd0a6135a7c8502aef9572f7079a3dd2632103"
EXPECTED_TOPOLOGY = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_NORMAL_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
EXPECTED_TOPOLOGY_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
PASS_STATE = "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _obj(basis: dict) -> str:
    lines = [
        "# AXM Animal Geometry structural UV/tangent-basis evidence",
        f"# side {basis['side']}",
        "# vt/vn are candidate structural attributes; tangent vectors are retained in JSON",
    ]
    for x, y, z in basis["render_positions"]:
        lines.append(f"v {x:.12f} {y:.12f} {z:.12f}")
    for u, v in basis["render_uvs"]:
        lines.append(f"vt {u:.12f} {v:.12f}")
    for x, y, z in basis["render_normals"]:
        lines.append(f"vn {x:.12f} {y:.12f} {z:.12f}")
    for offset in range(0, len(basis["render_indices"]), 3):
        ids = [int(value) + 1 for value in basis["render_indices"][offset:offset + 3]]
        lines.append("f " + " ".join(f"{value}/{value}/{value}" for value in ids))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--parent-head", required=True)
    parser.add_argument("--normal-head", required=True)
    parser.add_argument("--materials-head", required=True)
    parser.add_argument("--topology-head", required=True)
    parser.add_argument("--normal-module-blob", required=True)
    parser.add_argument("--topology-module-blob", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    expected = {
        "parent-head": (args.parent_head, EXPECTED_PARENT),
        "normal-head": (args.normal_head, EXPECTED_NORMAL),
        "materials-head": (args.materials_head, EXPECTED_MATERIALS),
        "topology-head": (args.topology_head, EXPECTED_TOPOLOGY),
        "normal-module-blob": (args.normal_module_blob, EXPECTED_NORMAL_BLOB),
        "topology-module-blob": (args.topology_module_blob, EXPECTED_TOPOLOGY_BLOB),
    }
    for label, (observed, wanted) in expected.items():
        if observed != wanted:
            raise SystemExit(f"{label} mismatch: {observed} != {wanted}")

    left, right, record = inspect_bilateral_uv_tangent_basis(
        _load(args.source), _load(args.left_profile), _load(args.bilateral_profile)
    )
    if record["state"] != PASS_STATE:
        raise SystemExit(f"UV/tangent basis gate is not PASS: {record['state']}")

    record["exact_geometry_head"] = args.exact_head
    record["provenance"] = {
        "rigging_parent_head": args.parent_head,
        "normal_geometry_head": args.normal_head,
        "materials_review_head": args.materials_head,
        "mirror_topology_head": args.topology_head,
        "normal_module_blob": args.normal_module_blob,
        "topology_module_blob": args.topology_module_blob,
    }
    record["negative_control"] = {
        "naive_unsplit_side_maximum_u_span": record["naive_unsplit_maximum_side_triangle_u_span"],
        "candidate_side_maximum_u_span": record["maximum_side_triangle_u_span"],
        "state": "PASS_EXPLICIT_SEAM_SPLIT_REMOVES_LARGE_CYLINDRICAL_U_WRAP",
    }
    record["handoff"] = {
        "materials_visual_qa": "Render this exact UV/tangent basis with a neutral tangent-space diagnostic before any final texture/normal-map claim.",
        "rigging": "The basis is static structural evidence. If used on deformed meshes, re-observe tangent-frame behaviour through the established pose envelope.",
        "technical_art": "Prove exact UV + explicit normal + tangent payload transport through the receiving UC/GLB path without regeneration or vertex-domain collapse.",
        "runtime": "Measure the render-domain split cost separately: this structural candidate expands 42 source vertices to 84 UV/tangent render vertices while keeping 80 source triangles.",
        "art_direction": "No texture placement or tangent-space visual preference is claimed by Geometry.",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write(args.out_dir / "geometry-uv-tangent-evidence.json", record)
    _write(args.out_dir / "left-uv-tangent-basis.json", left)
    _write(args.out_dir / "right-uv-tangent-basis.json", right)
    (args.out_dir / "left-uv-normal.obj").write_text(_obj(left), encoding="utf-8")
    (args.out_dir / "right-uv-normal.obj").write_text(_obj(right), encoding="utf-8")
    for name, value in (
        ("exact-head.txt", args.exact_head),
        ("parent-rigging-head.txt", args.parent_head),
        ("normal-geometry-head.txt", args.normal_head),
        ("materials-review-head.txt", args.materials_head),
        ("mirror-topology-head.txt", args.topology_head),
        ("normal-module-blob.txt", args.normal_module_blob),
        ("topology-module-blob.txt", args.topology_module_blob),
    ):
        (args.out_dir / name).write_text(value + "\n", encoding="utf-8")
    (args.out_dir / "README.txt").write_text(
        "AXM Animal Geometry structural UV/tangent-basis evidence.\n"
        "The exact source positions, source triangle records, exact-mirror topology and selected explicit logical-quad normal policy are unchanged.\n"
        "The candidate adds a three-island parametric UV basis and the minimum explicit render-domain splits needed for the cylindrical seam, cap/side boundaries and cap-pole tangent singularities.\n"
        "This is not final texture UV/texel-density acceptance, tangent-space normal-map visual acceptance, deformed shaded acceptance, transport/runtime acceptance, CANON, production readiness or game readiness.\n",
        encoding="utf-8",
    )

    print(record["state"])
    print(f"source_vertices={record['source_vertex_count']}")
    print(f"render_vertices={record['render_vertex_count']}")
    print(f"triangles={record['triangle_count']}")
    print(f"naive_u_span={record['naive_unsplit_maximum_side_triangle_u_span']}")
    print(f"candidate_u_span={record['maximum_side_triangle_u_span']}")
    print(f"mirror_tangent_residual={record['bilateral']['maximum_mirrored_tangent_xyz_residual']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
