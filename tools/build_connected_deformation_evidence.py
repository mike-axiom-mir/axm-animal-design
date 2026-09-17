#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.connected_deformation import (
    CANDIDATE_DIGEST,
    _build_exact_candidate,
    digest,
    inspect_connected_forelimb_deformation,
)

EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
GEOMETRY_PR4_HEAD = "feb4b24cd36bcc879173138d240754f71db34834"
SOURCE_PR1_HEAD = "179fc6dc1a38de477e433a3842c4793e748928fb"


def _edges(indices):
    out = set()
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        for first, second in ((a, b), (b, c), (c, a)):
            out.add(tuple(sorted((first, second))))
    return sorted(out)


def _pose_strip_svg(receipt, indices):
    width, height = 1200, 430
    panel_w = 380
    panels = []
    edges = _edges(indices)
    all_positions = [point for pose in receipt["poses"] for point in pose["positions"]]
    xs = [point[0] for point in all_positions]
    zs = [point[2] for point in all_positions]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    span_x = max(max_x - min_x, 1e-9)
    span_z = max(max_z - min_z, 1e-9)
    scale = min(300.0 / span_x, 300.0 / span_z)

    for panel_index, pose in enumerate(receipt["poses"]):
        origin_x = 20 + panel_index * 395
        origin_y = 350
        lines = []
        for first, second in edges:
            a = pose["positions"][first]
            b = pose["positions"][second]
            ax = origin_x + 20 + (a[0] - min_x) * scale
            ay = origin_y - (a[2] - min_z) * scale
            bx = origin_x + 20 + (b[0] - min_x) * scale
            by = origin_y - (b[2] - min_z) * scale
            lines.append(
                f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
                'stroke="#d7e3ee" stroke-width="1" opacity="0.82"/>'
            )
        title = f'{pose["angle_deg"]:+.0f} deg — {pose["status"]}'
        details = (
            f'min area {pose["minimum_triangle_area_ratio"]:.3f} | '
            f'edge {pose["minimum_edge_length_ratio"]:.3f}..{pose["maximum_edge_length_ratio"]:.3f} | '
            f'self-x {pose["nonadjacent_self_intersection_pairs"]}'
        )
        panels.append(
            f'<rect x="{origin_x}" y="20" width="{panel_w}" height="380" rx="8" fill="#10151b" stroke="#394653"/>'
            f'<text x="{origin_x + 14}" y="48" fill="#f4f6f8" font-family="monospace" font-size="16">{title}</text>'
            f'<text x="{origin_x + 14}" y="72" fill="#9fb1c3" font-family="monospace" font-size="11">{details}</text>'
            + "".join(lines)
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#0a0e12"/>'
        '<text x="20" y="420" fill="#73879a" font-family="monospace" font-size="11">'
        'Exact connected forelimb candidate; X/Z wire projection only. Structural pose evidence, not visual acceptance.'
        '</text>'
        + "".join(panels)
        + '</svg>\n'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    plan_path = Path(args.rig_plan)
    out = Path(args.out)
    spec = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise SystemExit("rig donor head drift")
    observed_plan_digest = digest(plan)
    if observed_plan_digest != EXPECTED_RIG_PLAN_DIGEST:
        raise SystemExit(f"rig plan digest drift: {observed_plan_digest}")

    evidence = inspect_connected_forelimb_deformation(spec, plan)
    if evidence["candidate_digest"] != CANDIDATE_DIGEST:
        raise SystemExit("geometry candidate digest drift")

    receipt = {
        **evidence,
        "lineage": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "source_pr1_head": SOURCE_PR1_HEAD,
            "geometry_pr4_head": GEOMETRY_PR4_HEAD,
            "geometry_candidate_digest": CANDIDATE_DIGEST,
            "rigging_pr2_donor_head": EXPECTED_RIG_DONOR_HEAD,
            "rig_plan_digest": EXPECTED_RIG_PLAN_DIGEST,
            "rig_plan_path": "examples/quadruped_rig_probe_001.json",
        },
        "decision": (
            "PASS_EXACT_CONNECTED_FORELIMB_SAMPLED_DEFORMATION"
            if evidence["gate"] == "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION"
            else "FAIL_EXACT_CONNECTED_FORELIMB_SAMPLED_DEFORMATION"
        ),
        "non_claims": [
            "No continuous interpolation between -60/0/+60 degree samples is proved.",
            "No volume preservation or muscle/skin plausibility is proved.",
            "No Art Director or Visual Observer acceptance is inherited.",
            "No Animation timing, clip, locomotion, engine playback or runtime controller is tested.",
            "No gameplay, collision, performance, CANON, production-readiness or mastery claim is made.",
        ],
    }

    candidate, _ = _build_exact_candidate(spec)
    out.mkdir(parents=True, exist_ok=True)
    (out / "connected-forelimb-deformation-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "connected-forelimb-pose-strip.svg").write_text(
        _pose_strip_svg(receipt, candidate["indices"]), encoding="utf-8"
    )
    (out / "source.json").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "rig-plan.json").write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")

    if evidence["gate"] != "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION":
        raise SystemExit("connected forelimb deformation gate failed")

    summary = {
        "decision": receipt["decision"],
        "candidate_digest": receipt["candidate_digest"],
        "rig_plan_digest": receipt["rig_plan_digest"],
        "weight_counts": receipt["weight_counts"],
        "poses": [
            {
                "angle_deg": pose["angle_deg"],
                "min_area": pose["minimum_triangle_area_ratio"],
                "min_edge": pose["minimum_edge_length_ratio"],
                "max_edge": pose["maximum_edge_length_ratio"],
                "self_intersections": pose["nonadjacent_self_intersection_pairs"],
                "status": pose["status"],
            }
            for pose in receipt["poses"]
        ],
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
