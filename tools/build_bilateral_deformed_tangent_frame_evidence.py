#!/usr/bin/env python3
"""Build retained Rigging evidence for the exact Animal deformed tangent observer."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import (
    DEFORMED_NORMAL_MODULE_BLOB,
    GEOMETRY_UV_TANGENT_HEAD,
    GEOMETRY_UV_TANGENT_MODULE_BLOB,
    PARENT_RIGGING_HEAD,
    PASS_STATE,
    RIGGING_SOURCE_MODULE_BLOB,
    inspect_bilateral_deformed_tangent_frames,
)
from axm_animal_design.bilateral_source_successor_rigging_rebind import RIG_DONOR_HEAD


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--left-profile", type=Path, required=True)
    parser.add_argument("--bilateral-profile", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--weighting-profile", type=Path, required=True)
    parser.add_argument("--geometry-uv-tangent-head", required=True)
    parser.add_argument("--parent-rigging-head", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--geometry-uv-tangent-module-blob", required=True)
    parser.add_argument("--deformed-normal-module-blob", required=True)
    parser.add_argument("--rigging-source-module-blob", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    expected = {
        "geometry_uv_tangent_head": GEOMETRY_UV_TANGENT_HEAD,
        "parent_rigging_head": PARENT_RIGGING_HEAD,
        "rig_donor_head": RIG_DONOR_HEAD,
        "geometry_uv_tangent_module_blob": GEOMETRY_UV_TANGENT_MODULE_BLOB,
        "deformed_normal_module_blob": DEFORMED_NORMAL_MODULE_BLOB,
        "rigging_source_module_blob": RIGGING_SOURCE_MODULE_BLOB,
    }
    observed = {
        "geometry_uv_tangent_head": args.geometry_uv_tangent_head,
        "parent_rigging_head": args.parent_rigging_head,
        "rig_donor_head": args.rig_donor_head,
        "geometry_uv_tangent_module_blob": args.geometry_uv_tangent_module_blob,
        "deformed_normal_module_blob": args.deformed_normal_module_blob,
        "rigging_source_module_blob": args.rigging_source_module_blob,
    }
    if observed != expected:
        raise SystemExit(f"exact dependency identity drift: {observed!r} != {expected!r}")

    source = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    receipt = inspect_bilateral_deformed_tangent_frames(
        source,
        left_profile,
        bilateral_profile,
        plan,
        weighting_profile,
    )
    if receipt["state"] != PASS_STATE:
        raise SystemExit(f"deformed tangent-frame gate is not PASS: {receipt['state']}")

    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "bilateral-deformed-tangent-frame-rigging-receipt.json", receipt)
    _write(
        args.out / "summary.json",
        {
            "state": receipt["state"],
            "exact_head": args.current_rigging_head,
            "geometry_uv_tangent_head": args.geometry_uv_tangent_head,
            "parent_rigging_head": args.parent_rigging_head,
            "rig_donor_head": args.rig_donor_head,
            "total_pose_fields": receipt["total_pose_fields"],
            "render_vertices_per_pose": receipt["render_vertices_per_pose"],
            "total_tangent_vectors_observed": receipt["total_tangent_vectors_observed"],
            "tested_angles_deg": receipt["tested_angles_deg"],
            "bilateral_mirror_evidence": receipt["bilateral_mirror_evidence"],
            "truth_boundary": receipt["truth_boundary"],
        },
    )
    shutil.copyfile(args.rig_plan, args.out / "exact-rig-plan.json")
    shutil.copyfile(args.weighting_profile, args.out / "exact-weighting-profile.json")
    (args.out / "exact-head.txt").write_text(args.current_rigging_head + "\n", encoding="utf-8")
    (args.out / "exact-geometry-uv-tangent-head.txt").write_text(args.geometry_uv_tangent_head + "\n", encoding="utf-8")
    (args.out / "parent-rigging-head.txt").write_text(args.parent_rigging_head + "\n", encoding="utf-8")
    (args.out / "rig-donor-head.txt").write_text(args.rig_donor_head + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
