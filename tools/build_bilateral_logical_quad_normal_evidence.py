#!/usr/bin/env python3
"""Build exact retained Geometry evidence for the bilateral logical-quad normal field."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from axm_animal_design.bilateral_logical_quad_normals import (
    derive_logical_quad_normals,
    inspect_bilateral_logical_quad_normal_field,
)
from axm_animal_design.bilateral_mirror_surface_topology import (
    derive_exact_mirror_surface_candidate,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)

EXPECTED_PARENT_HEAD = "96e998e5c793057836e01656aca9f71481439c9b"
EXPECTED_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_TOPOLOGY_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _obj(candidate: dict, normal_field: dict) -> str:
    lines = [
        "# AXM Animal Geometry logical-quad normal evidence",
        f"# candidate {candidate['id']}",
        f"# normal-field {normal_field['id']}",
        "# normals are Geometry candidates; tangents/UVs are intentionally undefined",
    ]
    for x, y, z in candidate["positions"]:
        lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
    for x, y, z in normal_field["normals"]:
        lines.append(f"vn {x:.12f} {y:.12f} {z:.12f}")
    indices = candidate["indices"]
    for offset in range(0, len(indices), 3):
        a, b, c = (int(indices[offset]) + 1, int(indices[offset + 1]) + 1, int(indices[offset + 2]) + 1)
        lines.append(f"f {a}//{a} {b}//{b} {c}//{c}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--geometry-module-blob", required=True)
    parser.add_argument("--parent-head", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    if args.parent_head != EXPECTED_PARENT_HEAD:
        raise SystemExit(f"unexpected Materials review parent: {args.parent_head}")
    if args.geometry_head != EXPECTED_TOPOLOGY_HEAD:
        raise SystemExit(f"unexpected Geometry topology head: {args.geometry_head}")
    if args.geometry_module_blob != EXPECTED_TOPOLOGY_BLOB:
        raise SystemExit(f"unexpected Geometry topology module blob: {args.geometry_module_blob}")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)

    left, historical_right, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise SystemExit(f"bilateral source topology prerequisite is not PASS: {prerequisite['state']}")
    exact_right, topology = derive_exact_mirror_surface_candidate(left, historical_right)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise SystemExit(f"exact mirror topology prerequisite is not PASS: {topology['state']}")

    left_field, historical_field, exact_field, record = inspect_bilateral_logical_quad_normal_field(
        spec, left_profile, bilateral_profile
    )
    if record["state"] != "PASS_BILATERAL_LOGICAL_QUAD_NORMAL_FIELD_CANDIDATE__TANGENTS_HELD":
        raise SystemExit(f"logical-quad normal field gate is not PASS: {record['state']}")

    # Negative control: the field must respond to source-position drift even though
    # it is intentionally invariant to longitudinal quad diagonal choice.
    mutated = deepcopy(exact_right)
    mutated["positions"][11][0] = round(float(mutated["positions"][11][0]) + 0.001, 9)
    mutated_field = derive_logical_quad_normals(mutated)
    position_drift_residual = max(
        sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)) ** 0.5
        for a, b in zip(exact_field["normals"], mutated_field["normals"])
    )
    if position_drift_residual <= 1e-9:
        raise SystemExit("position-drift control did not change the derived normal field")

    record["exact_geometry_head"] = args.exact_head
    record["materials_review_parent_head"] = args.parent_head
    record["exact_mirror_topology_head"] = args.geometry_head
    record["exact_mirror_topology_module_blob"] = args.geometry_module_blob
    record["negative_control"] = {
        "mutation": "exact-right vertex 11 x +0.001 m",
        "maximum_normal_residual_vs_unmutated": position_drift_residual,
        "state": "PASS_POSITION_FIELD_DEPENDENCY_DETECTED",
    }
    record["handoff"] = {
        "materials_visual_qa": "Render the retained explicit normal-field specimens against the existing generated-normal controls; Geometry makes no aesthetic acceptance claim.",
        "rigging": "If this field advances, re-observe normals after deformation before any dynamic shading claim transfers.",
        "technical_art": "Tangents remain undefined because no UV basis is authored in this candidate; do not fabricate tangent-space readiness.",
        "animation_runtime": "No motion or runtime acceptance transfers from this static normal-field evidence.",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write(args.out_dir / "geometry-normal-evidence.json", record)
    _write(args.out_dir / "left-logical-quad-normal-field.json", left_field)
    _write(args.out_dir / "historical-right-logical-quad-normal-field.json", historical_field)
    _write(args.out_dir / "exact-mirror-right-logical-quad-normal-field.json", exact_field)
    (args.out_dir / "historical-right-with-logical-quad-normals.obj").write_text(
        _obj(historical_right, historical_field), encoding="utf-8"
    )
    (args.out_dir / "exact-mirror-right-with-logical-quad-normals.obj").write_text(
        _obj(exact_right, exact_field), encoding="utf-8"
    )
    (args.out_dir / "exact-head.txt").write_text(args.exact_head + "\n", encoding="utf-8")
    (args.out_dir / "materials-review-parent-head.txt").write_text(args.parent_head + "\n", encoding="utf-8")
    (args.out_dir / "exact-mirror-topology-head.txt").write_text(args.geometry_head + "\n", encoding="utf-8")
    (args.out_dir / "exact-mirror-topology-module-blob.txt").write_text(args.geometry_module_blob + "\n", encoding="utf-8")
    (args.out_dir / "README.txt").write_text(
        "AXM Animal Geometry normal-field evidence.\n"
        "The candidate derives explicit smooth normals from logical ring quads and cap wedges, not longitudinal quad diagonals.\n"
        "Positions, triangle indices, Organic source form, rigging and Materials evidence are unchanged.\n"
        "Tangents and UVs remain explicitly undefined. Final shading preference, deformation-normal quality, runtime, gameplay, CANON and production/game readiness are not claimed.\n",
        encoding="utf-8",
    )

    print(record["state"])
    print(f"diagonal_invariance_max_normal_residual={record['diagonal_invariance_max_normal_residual']}")
    print(f"bilateral_mirror_max_normal_residual={record['bilateral_mirror_max_normal_residual']}")
    print(f"triangle_generated_connectivity_residual={record['triangle_generated_historical_vs_exact_max_normal_residual']}")
    print(f"position_drift_control_residual={position_drift_residual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
