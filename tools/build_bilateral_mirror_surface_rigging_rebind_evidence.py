#!/usr/bin/env python3
"""Build retained Rigging evidence on the exact bilateral mirror-surface topology."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.bilateral_mirror_surface_rigging_rebind import (
    GEOMETRY_MIRROR_SURFACE_HEAD,
    PASS_STATE,
    PREVIOUS_BILATERAL_RIGGING_HEAD,
    compare_mirror_probes,
    inspect_bilateral_mirror_surface_rigging_rebind,
)
from axm_animal_design.bilateral_mirror_surface_topology import inspect_exact_mirror_surface_repair
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    MIRROR_TOLERANCE,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _probe_side,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING, digest


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_obj(path: Path, positions, indices):
    lines = ["# AXM Animal exact-mirror Rigging pose; structural evidence only"]
    lines += [f"v {point[0]:.9f} {point[1]:.9f} {point[2]:.9f}" for point in positions]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _historical_topology_negative_control(spec, left_profile, bilateral_profile, plan):
    left, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    rows = {}
    for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
        left_probe = _probe_side(left, spec, plan, "left", weighting)
        right_probe = _probe_side(historical_right, spec, plan, "right", weighting)
        rows[weighting] = compare_mirror_probes(left_probe, right_probe, left)
        if rows[weighting]["maximum_mirrored_pose_residual_m"] > MIRROR_TOLERANCE:
            raise SystemExit("historical topology control unexpectedly broke exact mirrored posed vertices")
        if rows[weighting]["maximum_structural_metric_residual"] <= MIRROR_TOLERANCE:
            raise SystemExit("historical topology control unexpectedly satisfies exact mirrored surface metrics")
        if rows[weighting]["gate"] != "FAIL_EXACT_MIRRORED_VERTEX_OR_SURFACE_METRICS":
            raise SystemExit("historical topology control did not fail the exact surface mirror gate")
    return {
        "control_id": "historical-right-triangle-connectivity",
        "result": "PASS_NEGATIVE_CONTROL_REPRODUCES_PREVIOUS_SURFACE_METRIC_HOLD",
        "profiles": rows,
    }


def _weighting_identity_negative_control(spec, left_profile, bilateral_profile, plan, weighting_profile):
    drifted = copy.deepcopy(weighting_profile)
    drifted["candidate_exponent"] = 0.74
    try:
        inspect_bilateral_mirror_surface_rigging_rebind(
            spec, left_profile, bilateral_profile, plan, drifted
        )
    except ValueError as exc:
        if "candidate exponent drift" not in str(exc):
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
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--previous-rigging-head", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--current-rigging-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if args.geometry_head != GEOMETRY_MIRROR_SURFACE_HEAD:
        raise SystemExit("exact mirror-surface Geometry head drift")
    if args.previous_rigging_head != PREVIOUS_BILATERAL_RIGGING_HEAD:
        raise SystemExit("previous bilateral Rigging head drift")
    if args.rig_donor_head != RIG_DONOR_HEAD:
        raise SystemExit("Rigging donor head drift")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact Rigging plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting profile digest drift")

    receipt = inspect_bilateral_mirror_surface_rigging_rebind(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if receipt["state"] != PASS_STATE:
        raise SystemExit(f"exact mirror-surface Rigging rebind failed: {receipt['state']}")

    historical_control = _historical_topology_negative_control(
        spec, left_profile, bilateral_profile, plan
    )
    weighting_control = _weighting_identity_negative_control(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )

    left_candidate, right_candidate, geometry = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, plan
    )
    receipt["exact_current_rigging_head"] = args.current_rigging_head
    receipt["geometry_prerequisite"] = {
        "head": args.geometry_head,
        "state": geometry["state"],
        "positions_modified": False,
        "right_topology_modified_by_geometry": True,
    }
    receipt["negative_controls"] = [historical_control, weighting_control]
    receipt["handoffs"] = {
        "geometry": "Exact mirrored topology now directly retains the existing rig/profile structural PASS across the sampled envelope. Geometry still owns whether the topology advances and any topology tradeoff.",
        "materials_visual": "Geometry's diagonal flips can change generated normals/tangent-space shading; this Rigging result does not overrule Materials, Visual QA or Art Direction review.",
        "animation": "Animation must explicitly bind its own clip/interpolation/playback evidence to this exact source + Geometry + Rigging identity before making a motion claim.",
        "runtime": "No exported skeleton/skin, engine controller, target-host playback or target-device performance is established here.",
    }
    receipt["non_claims"] = [
        "The one-degree -60..+60 samples are finite observations, not mathematical proof for every real-valued intermediate angle.",
        "No anatomy, muscle behavior, volume preservation, skin sliding or final visual deformation quality is accepted.",
        "No Animation timing, interpolation, clip, playback or motion acceptance is established.",
        "No exported skeleton/skin, engine/controller, runtime playback, target-device performance or gameplay is established.",
        "No CANON, production-readiness, game-readiness or Rigging-mastery claim is made.",
    ]

    args.out.mkdir(parents=True, exist_ok=True)
    _dump(args.out / "bilateral-mirror-surface-rigging-rebind-receipt.json", receipt)
    _dump(args.out / "geometry-prerequisite-record.json", geometry)
    (args.out / "rig-plan.json").write_text(args.rig_plan.read_text(encoding="utf-8"), encoding="utf-8")
    (args.out / "weighting-profile.json").write_text(
        args.weighting_profile.read_text(encoding="utf-8"), encoding="utf-8"
    )

    for side, candidate in (("left", left_candidate), ("right", right_candidate)):
        indices = candidate["indices"]
        for weighting, poses in receipt[side]["representative_poses"].items():
            safe = weighting.replace("-", "_")
            for angle, row in poses.items():
                _write_obj(
                    args.out / f"{side}-{safe}-{int(angle):+d}deg.obj",
                    row["positions"],
                    indices,
                )

    (args.out / "README.txt").write_text(
        "AXM Animal Rigging rebind on Geometry PR #13 exact mirror-surface topology.\n"
        "The rig, weights, source positions and motion semantics are unchanged.\n"
        "Representative OBJ files are structural review specimens only.\n"
        "No Animation, visual, runtime, gameplay, CANON or production acceptance is implied.\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "state": receipt["state"],
        "total_dense_pose_observations": receipt["total_dense_pose_observations"],
        "baseline_mirror": receipt["bilateral_mirror_evidence"][BASELINE_WEIGHTING],
        "refined_mirror": receipt["bilateral_mirror_evidence"][CANDIDATE_WEIGHTING],
        "historical_topology_control": historical_control,
        "weighting_identity_control": weighting_control,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
