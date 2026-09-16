#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.connected_deformation import (
    CANDIDATE_DIGEST,
    _build_exact_candidate,
    digest,
    inspect_connected_forelimb_deformation,
)
from axm_animal_design.connected_weighting_refinement import (
    CANDIDATE_WEIGHTING,
    EXPECTED_PROFILE_DIGEST,
    _probe_candidate,
    inspect_connected_weighting_refinement,
)

EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
PREDECESSOR_CONNECTED_RIG_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"
GEOMETRY_PR4_HEAD = "feb4b24cd36bcc879173138d240754f71db34834"
SOURCE_PR1_HEAD = "179fc6dc1a38de477e433a3842c4793e748928fb"


def _edges(indices):
    out = set()
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        for first, second in ((a, b), (b, c), (c, a)):
            out.add(tuple(sorted((first, second))))
    return sorted(out)


def _comparison_svg(baseline, candidate, indices):
    width, height = 1220, 450
    panel_w = 385
    edges = _edges(indices)
    all_positions = [
        point
        for receipt in (baseline, candidate)
        for pose in receipt["poses"]
        for point in pose["positions"]
    ]
    xs = [point[0] for point in all_positions]
    zs = [point[2] for point in all_positions]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    span_x = max(max_x - min_x, 1e-9)
    span_z = max(max_z - min_z, 1e-9)
    scale = min(300.0 / span_x, 300.0 / span_z)
    panels = []

    for panel_index, base_pose in enumerate(baseline["poses"]):
        cand_pose = candidate["poses"][panel_index]
        origin_x = 15 + panel_index * 400
        origin_y = 365
        base_lines = []
        candidate_lines = []
        for first, second in edges:
            for pose, collection, stroke, opacity in (
                (base_pose, base_lines, "#90a4b8", "0.48"),
                (cand_pose, candidate_lines, "#f0c36a", "0.92"),
            ):
                a = pose["positions"][first]
                b = pose["positions"][second]
                ax = origin_x + 22 + (a[0] - min_x) * scale
                ay = origin_y - (a[2] - min_z) * scale
                bx = origin_x + 22 + (b[0] - min_x) * scale
                by = origin_y - (b[2] - min_z) * scale
                collection.append(
                    f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
                    f'stroke="{stroke}" stroke-width="1.15" opacity="{opacity}"/>'
                )
        title = f'{base_pose["angle_deg"]:+.0f} deg'
        details = (
            f'base minA {base_pose["minimum_triangle_area_ratio"]:.3f} / minE {base_pose["minimum_edge_length_ratio"]:.3f}  '
            f'cand minA {cand_pose["minimum_triangle_area_ratio"]:.3f} / minE {cand_pose["minimum_edge_length_ratio"]:.3f}'
        )
        panels.append(
            f'<rect x="{origin_x}" y="18" width="{panel_w}" height="395" rx="8" fill="#10151b" stroke="#394653"/>'
            f'<text x="{origin_x + 14}" y="46" fill="#f4f6f8" font-family="monospace" font-size="16">{title}</text>'
            f'<text x="{origin_x + 14}" y="69" fill="#9fb1c3" font-family="monospace" font-size="10">{details}</text>'
            + "".join(base_lines)
            + "".join(candidate_lines)
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#0a0e12"/>'
        '<text x="20" y="432" fill="#90a4b8" font-family="monospace" font-size="11">smoothstep-v0 baseline</text>'
        '<text x="210" y="432" fill="#f0c36a" font-family="monospace" font-size="11">ease-out-power-0p75-v1 candidate</text>'
        '<text x="470" y="432" fill="#73879a" font-family="monospace" font-size="11">Exact X/Z wire overlay; structural comparison only, not perceptual acceptance.</text>'
        + "".join(panels)
        + '</svg>\n'
    )


def _retained_negative_control(spec, plan, profile):
    drifted = copy.deepcopy(profile)
    drifted["candidate_exponent"] = 0.74
    try:
        inspect_connected_weighting_refinement(spec, plan, drifted)
    except ValueError as exc:
        reason = str(exc)
        if "candidate exponent drift" not in reason:
            raise SystemExit(f"negative weighting-profile control failed for unexpected reason: {reason}")
        return {
            "control_id": "candidate-exponent-drift",
            "result": "HOLD_WEIGHTING_PROFILE_IDENTITY_DRIFT",
            "reason": reason,
        }
    raise SystemExit("negative weighting-profile control unexpectedly passed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    plan_path = Path(args.rig_plan)
    profile_path = Path(args.weighting_profile)
    out = Path(args.out)
    spec = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise SystemExit("rig donor head drift")
    observed_plan_digest = digest(plan)
    if observed_plan_digest != EXPECTED_RIG_PLAN_DIGEST:
        raise SystemExit(f"rig plan digest drift: {observed_plan_digest}")
    observed_profile_digest = digest(profile)
    if observed_profile_digest != EXPECTED_PROFILE_DIGEST:
        raise SystemExit(f"weighting profile digest drift: {observed_profile_digest}")

    comparison = inspect_connected_weighting_refinement(spec, plan, profile)
    baseline = inspect_connected_forelimb_deformation(spec, plan)
    candidate = _probe_candidate(spec, plan)
    if comparison["connected_candidate_digest"] != CANDIDATE_DIGEST:
        raise SystemExit("geometry candidate digest drift")
    if candidate["weighting"] != CANDIDATE_WEIGHTING:
        raise SystemExit("candidate weighting identity drift")

    negative_control = _retained_negative_control(spec, plan, profile)
    receipt = {
        **comparison,
        "lineage": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "source_pr1_head": SOURCE_PR1_HEAD,
            "geometry_pr4_head": GEOMETRY_PR4_HEAD,
            "connected_rig_predecessor_head": PREDECESSOR_CONNECTED_RIG_HEAD,
            "connected_candidate_digest": CANDIDATE_DIGEST,
            "rigging_pr2_donor_head": EXPECTED_RIG_DONOR_HEAD,
            "rig_plan_digest": EXPECTED_RIG_PLAN_DIGEST,
            "weighting_profile_digest": EXPECTED_PROFILE_DIGEST,
            "rig_plan_path": "examples/quadruped_rig_probe_001.json",
            "weighting_profile_path": "examples/quadruped_weighting_refinement_001.json",
        },
        "negative_control": negative_control,
        "decision": comparison["gate"],
        "non_claims": [
            "No continuous interpolation between -60/0/+60 degree samples is proved.",
            "No volume preservation, skin sliding, muscle behaviour or anatomy is proved.",
            "No Art Director or Visual Observer acceptance is inherited from the numeric comparison.",
            "No Geometry PR #7 ring-phase candidate or Organic PR #8 elbow-relief candidate is consumed or adopted.",
            "No Animation timing, clip, engine playback, runtime controller or target-device behaviour is tested.",
            "No gameplay, collision-system, performance, CANON, production-readiness or mastery claim is made.",
        ],
    }

    connected_candidate, _ = _build_exact_candidate(spec)
    out.mkdir(parents=True, exist_ok=True)
    (out / "connected-weighting-refinement-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "connected-weighting-refinement-overlay.svg").write_text(
        _comparison_svg(baseline, candidate, connected_candidate["indices"]), encoding="utf-8"
    )
    (out / "source.json").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "rig-plan.json").write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "weighting-profile.json").write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")

    if comparison["gate"] != "PASS_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT":
        raise SystemExit("connected weighting refinement gate held")

    print(json.dumps({
        "decision": comparison["gate"],
        "connected_candidate_digest": comparison["connected_candidate_digest"],
        "rig_plan_digest": comparison["rig_plan_digest"],
        "weighting_profile_digest": comparison["weighting_profile_digest"],
        "weight_counts": comparison["weight_counts"],
        "comparisons": comparison["comparisons"],
        "negative_control": negative_control,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
