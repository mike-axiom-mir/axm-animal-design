#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.elbow_source_successor_rigging_rebind import (
    GEOMETRY_SUCCESSOR_HEAD,
    HISTORICAL_WEIGHTING_HEAD,
    ORGANIC_SUCCESSOR_HEAD,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    inspect_source_successor_rigging_rebind,
)
from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_source_successor import SOURCE_SUCCESSOR_CANDIDATE_DIGEST
from axm_animal_design.source_successor_topology_rebind import build_source_successor_topology_rebind


def _write_obj(path: Path, positions, indices):
    lines = ["# AXM Animal retained rigging pose; structural evidence only"]
    lines += [f"v {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}" for point in positions]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _negative_controls(spec, source_profile, plan, weighting_profile):
    controls = []

    drifted_weighting = copy.deepcopy(weighting_profile)
    drifted_weighting["candidate_exponent"] = 0.74
    try:
        inspect_source_successor_rigging_rebind(spec, source_profile, plan, drifted_weighting)
    except ValueError as exc:
        if "candidate exponent drift" not in str(exc):
            raise SystemExit(f"unexpected weighting drift failure: {exc}")
        controls.append({
            "control_id": "candidate-exponent-drift",
            "result": "HOLD_WEIGHTING_PROFILE_IDENTITY_DRIFT",
            "reason": str(exc),
        })
    else:
        raise SystemExit("candidate exponent drift unexpectedly passed")

    drifted_source = copy.deepcopy(source_profile)
    drifted_source["form_change"]["bend_plane_radius_m"] = 0.0884
    try:
        inspect_source_successor_rigging_rebind(spec, drifted_source, plan, weighting_profile)
    except ValueError as exc:
        if "profile identity drift" not in str(exc):
            raise SystemExit(f"unexpected source-profile drift failure: {exc}")
        controls.append({
            "control_id": "source-successor-profile-drift",
            "result": "HOLD_SOURCE_SUCCESSOR_IDENTITY_DRIFT",
            "reason": str(exc),
        })
    else:
        raise SystemExit("source successor profile drift unexpectedly passed")

    return controls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-profile", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--historical-weighting-head", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.geometry_head != GEOMETRY_SUCCESSOR_HEAD:
        raise SystemExit("Geometry successor head drift")
    if args.historical_weighting_head != HISTORICAL_WEIGHTING_HEAD:
        raise SystemExit("historical weighting head drift")
    if args.rig_donor_head != RIG_DONOR_HEAD:
        raise SystemExit("Rigging donor head drift")

    source_path = Path(args.source)
    source_profile_path = Path(args.source_profile)
    rig_plan_path = Path(args.rig_plan)
    weighting_profile_path = Path(args.weighting_profile)

    spec = json.loads(source_path.read_text(encoding="utf-8"))
    source_profile = json.loads(source_profile_path.read_text(encoding="utf-8"))
    plan = json.loads(rig_plan_path.read_text(encoding="utf-8"))
    weighting_profile = json.loads(weighting_profile_path.read_text(encoding="utf-8"))

    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact Rigging plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting profile digest drift")

    receipt = inspect_source_successor_rigging_rebind(
        spec,
        source_profile,
        plan,
        weighting_profile,
    )
    if receipt["state"] != "PASS_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP":
        raise SystemExit("source-successor Rigging dense sweep did not pass")

    candidate, topology = build_source_successor_topology_rebind(spec, source_profile)
    if digest(candidate) != SOURCE_SUCCESSOR_CANDIDATE_DIGEST:
        raise SystemExit("source-successor candidate digest drift")
    negatives = _negative_controls(spec, source_profile, plan, weighting_profile)

    receipt["lineage"] = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "organic_source_successor_head": ORGANIC_SUCCESSOR_HEAD,
        "geometry_source_successor_head": GEOMETRY_SUCCESSOR_HEAD,
        "historical_connected_weighting_head": HISTORICAL_WEIGHTING_HEAD,
        "rig_plan_donor_head": RIG_DONOR_HEAD,
        "source_successor_candidate_digest": SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "source_path": "examples/quadruped_neutral_001.json",
        "source_successor_profile_path": "examples/quadruped_elbow_source_successor_003.json",
        "rig_plan_path": "examples/quadruped_rig_probe_001.json",
        "weighting_profile_path": "examples/quadruped_weighting_refinement_001.json",
    }
    receipt["negative_controls"] = negatives
    receipt["non_claims"] = [
        "Dense one-degree samples are finite structural observations, not a mathematical proof for every real-valued intermediate angle.",
        "No visual deformation quality, anatomy, muscle behavior, volume preservation or skin sliding is accepted.",
        "No Animation timing, clip, interpolation, playback or motion-direction acceptance is established.",
        "No exported skeleton/skin, engine controller, runtime playback, target-device performance or gameplay is established.",
        "No CANON, production-readiness or Rigging-mastery claim is made.",
    ]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-successor-rigging-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "source-successor-profile.json").write_text(
        source_profile_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "rig-plan.json").write_text(
        rig_plan_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "weighting-profile.json").write_text(
        weighting_profile_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (out / "geometry-topology-prerequisite.json").write_text(
        json.dumps(topology, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    indices = candidate["indices"]
    for weighting, poses in receipt["representative_poses"].items():
        safe = weighting.replace("-", "_")
        for angle, row in poses.items():
            _write_obj(
                out / f"{safe}-{int(angle):+d}deg.obj",
                row["positions"],
                indices,
            )

    print(json.dumps({
        "state": receipt["state"],
        "weighting_preference": receipt["boundary_weighting_comparison"]["gate"],
        "total_dense_pose_observations": receipt["total_dense_pose_observations"],
        "baseline_summary": receipt["baseline_summary"],
        "refined_summary": receipt["refined_summary"],
        "negative_controls": negatives,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
