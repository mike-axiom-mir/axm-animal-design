#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    GEOMETRY_BILATERAL_HEAD,
    HISTORICAL_LEFT_RIGGING_HEAD,
    ORGANIC_BILATERAL_HEAD,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    inspect_bilateral_source_successor_rigging_rebind,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.connected_deformation import digest

HISTORICAL_WEIGHTING_VERIFICATION_HEAD = "5625c9f796a75e8b441458c51093e55519490611"


def _write_obj(path: Path, positions, indices):
    lines = ["# AXM Animal retained bilateral Rigging pose; structural evidence only"]
    lines += [f"v {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}" for point in positions]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _negative_controls(spec, left_profile, bilateral_profile, plan, weighting_profile):
    controls = []

    drifted_weighting = copy.deepcopy(weighting_profile)
    drifted_weighting["candidate_exponent"] = 0.74
    try:
        inspect_bilateral_source_successor_rigging_rebind(
            spec, left_profile, bilateral_profile, plan, drifted_weighting
        )
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

    drifted_plan = copy.deepcopy(plan)
    for joint in drifted_plan["joints"]:
        if joint.get("id") == "front-elbow-R":
            joint["axis"] = [0.0, -1.0, 0.0]
    try:
        inspect_bilateral_source_successor_rigging_rebind(
            spec, left_profile, bilateral_profile, drifted_plan, weighting_profile
        )
    except ValueError as exc:
        if "rig plan identity drift" not in str(exc):
            raise SystemExit(f"unexpected rig-plan drift failure: {exc}")
        controls.append({
            "control_id": "right-joint-axis-drift",
            "result": "HOLD_RIG_PLAN_IDENTITY_DRIFT",
            "reason": str(exc),
        })
    else:
        raise SystemExit("right joint axis drift unexpectedly passed")

    drifted_bilateral = copy.deepcopy(bilateral_profile)
    drifted_bilateral["right_form_change"]["bend_plane_radius_m"] = 0.0884
    try:
        inspect_bilateral_source_successor_rigging_rebind(
            spec, left_profile, drifted_bilateral, plan, weighting_profile
        )
    except ValueError as exc:
        if "profile identity drift" not in str(exc):
            raise SystemExit(f"unexpected bilateral source drift failure: {exc}")
        controls.append({
            "control_id": "right-source-successor-profile-drift",
            "result": "HOLD_RIGHT_SOURCE_SUCCESSOR_IDENTITY_DRIFT",
            "reason": str(exc),
        })
    else:
        raise SystemExit("right source-successor profile drift unexpectedly passed")

    return controls


def _diagnostic_summary(receipt):
    return {
        "state": receipt["state"],
        "left_baseline": receipt["left"]["baseline_summary"],
        "left_refined": receipt["left"]["refined_summary"],
        "right_baseline": receipt["right"]["baseline_summary"],
        "right_refined": receipt["right"]["refined_summary"],
        "left_weighting_gate": receipt["left"]["boundary_weighting_comparison"]["gate"],
        "right_weighting_gate": receipt["right"]["boundary_weighting_comparison"]["gate"],
        "baseline_mirror_gate": receipt["bilateral_mirror_evidence"]["smoothstep-v0"]["gate"],
        "refined_mirror_gate": receipt["bilateral_mirror_evidence"]["ease-out-power-0p75-v1"]["gate"],
        "baseline_mirror_max_pose_residual_m": receipt["bilateral_mirror_evidence"]["smoothstep-v0"]["maximum_mirrored_pose_residual_m"],
        "refined_mirror_max_pose_residual_m": receipt["bilateral_mirror_evidence"]["ease-out-power-0p75-v1"]["maximum_mirrored_pose_residual_m"],
        "baseline_mirror_max_metric_residual": receipt["bilateral_mirror_evidence"]["smoothstep-v0"]["maximum_structural_metric_residual"],
        "refined_mirror_max_metric_residual": receipt["bilateral_mirror_evidence"]["ease-out-power-0p75-v1"]["maximum_structural_metric_residual"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--historical-left-rigging-head", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.geometry_head != GEOMETRY_BILATERAL_HEAD:
        raise SystemExit("Geometry bilateral head drift")
    if args.historical_left_rigging_head != HISTORICAL_LEFT_RIGGING_HEAD:
        raise SystemExit("historical left Rigging head drift")
    if args.rig_donor_head != RIG_DONOR_HEAD:
        raise SystemExit("Rigging donor head drift")

    source_path = Path(args.source)
    left_profile_path = Path(args.left_profile)
    bilateral_profile_path = Path(args.bilateral_profile)
    rig_plan_path = Path(args.rig_plan)
    weighting_profile_path = Path(args.weighting_profile)

    spec = json.loads(source_path.read_text(encoding="utf-8"))
    left_profile = json.loads(left_profile_path.read_text(encoding="utf-8"))
    bilateral_profile = json.loads(bilateral_profile_path.read_text(encoding="utf-8"))
    plan = json.loads(rig_plan_path.read_text(encoding="utf-8"))
    weighting_profile = json.loads(weighting_profile_path.read_text(encoding="utf-8"))

    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact Rigging plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting profile digest drift")

    receipt = inspect_bilateral_source_successor_rigging_rebind(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    diagnostic = _diagnostic_summary(receipt)
    print("AXM_BILATERAL_RIGGING_DIAGNOSTIC=" + json.dumps(diagnostic, sort_keys=True))
    if receipt["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP":
        raise SystemExit("bilateral source-successor Rigging dense sweep did not pass")

    left_candidate, right_candidate, geometry = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    negatives = _negative_controls(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )

    receipt["lineage"] = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "organic_bilateral_source_head": ORGANIC_BILATERAL_HEAD,
        "geometry_bilateral_source_successor_head": GEOMETRY_BILATERAL_HEAD,
        "historical_left_source_successor_rigging_head": HISTORICAL_LEFT_RIGGING_HEAD,
        "rig_plan_and_profile_file_donor_head": RIG_DONOR_HEAD,
        "historical_weighting_verification_head": HISTORICAL_WEIGHTING_VERIFICATION_HEAD,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "source_path": "examples/quadruped_neutral_001.json",
        "left_source_successor_profile_path": "examples/quadruped_elbow_source_successor_003.json",
        "bilateral_source_successor_profile_path": "examples/quadruped_elbow_bilateral_successor_003.json",
        "rig_plan_path": "examples/quadruped_rig_probe_001.json @ exact Rigging plan/profile file donor",
        "weighting_profile_path": "examples/quadruped_weighting_refinement_001.json @ exact Rigging plan/profile file donor",
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
    (out / "bilateral-source-successor-rigging-rebind-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "bilateral-source-successor-topology-prerequisite.json").write_text(
        json.dumps(geometry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "rig-plan.json").write_text(rig_plan_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "weighting-profile.json").write_text(
        weighting_profile_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        indices = candidate["indices"]
        for weighting, poses in receipt[side]["representative_poses"].items():
            safe = weighting.replace("-", "_")
            for angle, row in poses.items():
                _write_obj(
                    out / f"{side}-{safe}-{int(angle):+d}deg.obj",
                    row["positions"],
                    indices,
                )

    print(json.dumps({
        "state": receipt["state"],
        "total_dense_pose_observations": receipt["total_dense_pose_observations"],
        "left_refined": receipt["left"]["refined_summary"],
        "right_refined": receipt["right"]["refined_summary"],
        "baseline_mirror": receipt["bilateral_mirror_evidence"]["smoothstep-v0"]["gate"],
        "refined_mirror": receipt["bilateral_mirror_evidence"]["ease-out-power-0p75-v1"]["gate"],
        "baseline_mirror_max_pose_residual_m": receipt["bilateral_mirror_evidence"]["smoothstep-v0"]["maximum_mirrored_pose_residual_m"],
        "refined_mirror_max_pose_residual_m": receipt["bilateral_mirror_evidence"]["ease-out-power-0p75-v1"]["maximum_mirrored_pose_residual_m"],
        "negative_controls": negatives,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
