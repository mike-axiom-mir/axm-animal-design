#!/usr/bin/env python3
"""Build retained Rigging evidence for Geometry's explicit logical-quad normals."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.bilateral_deformed_logical_quad_normals import (
    MATERIALS_REVIEW_HEAD,
    NORMAL_GEOMETRY_HEAD,
    NORMAL_MODULE_BLOB,
    PASS_STATE,
    REPRESENTATIVE_ANGLES_DEG,
    RIGGING_MIRROR_MODULE_BLOB,
    RIGGING_MIRROR_SURFACE_HEAD,
    RIGGING_SOURCE_MODULE_BLOB,
    TOPOLOGY_HEAD,
    inspect_bilateral_deformed_logical_quad_normals,
)
from axm_animal_design.bilateral_mirror_surface_topology import inspect_exact_mirror_surface_repair
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
)
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING, digest


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_obj_with_normals(path: Path, positions, normals, indices):
    lines = ["# AXM Animal deformed logical-quad normal specimen; structural evidence only"]
    lines += [f"v {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}" for point in positions]
    lines += [f"vn {normal[0]:.12f} {normal[1]:.12f} {normal[2]:.12f}" for normal in normals]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        lines.append(f"f {a + 1}//{a + 1} {b + 1}//{b + 1} {c + 1}//{c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _weighting_identity_negative_control(spec, left_profile, bilateral_profile, plan, weighting_profile):
    drifted = copy.deepcopy(weighting_profile)
    drifted["candidate_exponent"] = 0.74
    try:
        inspect_bilateral_deformed_logical_quad_normals(
            spec, left_profile, bilateral_profile, plan, drifted
        )
    except ValueError as exc:
        if "candidate exponent drift" not in str(exc) and "weighting profile digest drift" not in str(exc):
            raise SystemExit(f"unexpected weighting identity failure: {exc}")
        return {
            "control_id": "candidate-exponent-0p75-to-0p74",
            "result": "HOLD_WEIGHTING_PROFILE_IDENTITY_DRIFT",
            "reason": str(exc),
        }
    raise SystemExit("weighting identity negative control unexpectedly passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--weighting-profile", required=True, type=Path)
    parser.add_argument("--normal-geometry-head", required=True)
    parser.add_argument("--materials-review-head", required=True)
    parser.add_argument("--topology-head", required=True)
    parser.add_argument("--historical-rigging-head", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    expected = {
        "normal geometry head": (args.normal_geometry_head, NORMAL_GEOMETRY_HEAD),
        "materials review head": (args.materials_review_head, MATERIALS_REVIEW_HEAD),
        "topology head": (args.topology_head, TOPOLOGY_HEAD),
        "historical Rigging head": (args.historical_rigging_head, RIGGING_MIRROR_SURFACE_HEAD),
        "Rigging donor head": (args.rig_donor_head, RIG_DONOR_HEAD),
    }
    for label, (observed, wanted) in expected.items():
        if observed != wanted:
            raise SystemExit(f"{label} drift: {observed}")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact Rigging plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting profile digest drift")

    receipt = inspect_bilateral_deformed_logical_quad_normals(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if receipt["state"] != PASS_STATE:
        raise SystemExit(f"deformed logical-quad normal gate failed: {receipt['state']}")

    negative = _weighting_identity_negative_control(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    left_candidate, right_candidate, geometry = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, plan
    )

    receipt["exact_current_rigging_head"] = args.current_rigging_head
    receipt["exact_dependency_heads"] = {
        "normal_geometry_head": args.normal_geometry_head,
        "materials_static_review_head": args.materials_review_head,
        "topology_head": args.topology_head,
        "historical_rigging_head": args.historical_rigging_head,
        "rig_donor_head": args.rig_donor_head,
    }
    receipt["exact_dependency_blobs"] = {
        "logical_quad_normal_module": NORMAL_MODULE_BLOB,
        "rigging_source_successor_module": RIGGING_SOURCE_MODULE_BLOB,
        "historical_mirror_surface_rigging_module": RIGGING_MIRROR_MODULE_BLOB,
    }
    receipt["negative_controls"] = [negative]
    receipt["geometry_prerequisite"] = {
        "state": geometry["state"],
        "head": args.topology_head,
        "source_positions_rewritten_by_this_rigging_lane": False,
        "topology_rewritten_by_this_rigging_lane": False,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    _dump(args.out / "bilateral-deformed-logical-quad-normal-rigging-receipt.json", receipt)
    _dump(args.out / "geometry-prerequisite-record.json", geometry)
    (args.out / "rig-plan.json").write_text(args.rig_plan.read_text(encoding="utf-8"), encoding="utf-8")
    (args.out / "weighting-profile.json").write_text(
        args.weighting_profile.read_text(encoding="utf-8"), encoding="utf-8"
    )

    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        indices = candidate["indices"]
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            safe_weighting = weighting.replace("-", "_")
            representative = receipt[side][weighting]["representative_poses"]
            for angle in REPRESENTATIVE_ANGLES_DEG:
                row = representative[str(int(angle))]
                _write_obj_with_normals(
                    args.out / f"{side}-{safe_weighting}-{int(angle):+d}deg.obj",
                    row["positions"],
                    row["normals"],
                    indices,
                )

    (args.out / "README.txt").write_text(
        "AXM Animal Rigging deformed logical-quad normal evidence.\n"
        "Geometry owns the normal derivation and topology; Rigging only re-observes that field on exact established poses.\n"
        "The retained OBJ specimens include explicit vn records for structural review.\n"
        "This is finite sampled evidence, not continuous real-angle proof or production skin-normal transport.\n"
        "No tangents, shaded visual acceptance, Animation acceptance, runtime/controller acceptance, gameplay, CANON, or production readiness is implied.\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "state": receipt["state"],
        "total_pose_fields": receipt["total_pose_fields"],
        "total_normal_vectors_observed": receipt["total_normal_vectors_observed"],
        "baseline_mirror": receipt["bilateral_mirror_evidence"][BASELINE_WEIGHTING],
        "refined_mirror": receipt["bilateral_mirror_evidence"][CANDIDATE_WEIGHTING],
        "negative_control": negative,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
