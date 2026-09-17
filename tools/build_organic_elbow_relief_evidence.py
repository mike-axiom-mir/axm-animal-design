#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

from axm_animal_design.connected_deformation import _build_exact_candidate, digest
from axm_animal_design.organic_elbow_relief import (
    CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    build_elbow_relief_candidate,
    inspect_elbow_relief_review,
)

EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIGGING_PR6_BASE_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"
GEOMETRY_PR4_HEAD = "feb4b24cd36bcc879173138d240754f71db34834"


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _length(a):
    return math.sqrt(_dot(a, a))


def _project(point):
    # Deterministic three-quarter evidence projection only, not a renderer camera.
    x, y, z = point
    return (x + 0.42 * y, z + 0.12 * y, y - 0.18 * x)


def _shaded_mesh_group(positions, indices, x0, y0, width, height, label):
    projected = [_project(point) for point in positions]
    xs = [p[0] for p in projected]
    ys = [p[1] for p in projected]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min((width - 24) / span_x, (height - 54) / span_y)
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5

    def screen(index):
        px, py, _ = projected[index]
        return (x0 + width * 0.5 + (px - cx) * scale, y0 + height * 0.58 - (py - cy) * scale)

    light = (0.35, -0.55, 0.76)
    light_len = _length(light)
    light = tuple(v / light_len for v in light)
    faces = []
    for offset in range(0, len(indices), 3):
        ia, ib, ic = indices[offset:offset + 3]
        a, b, c = positions[ia], positions[ib], positions[ic]
        normal = _cross(_sub(b, a), _sub(c, a))
        nlen = _length(normal)
        if nlen <= 1e-12:
            continue
        normal = tuple(v / nlen for v in normal)
        intensity = max(0.0, min(1.0, 0.34 + 0.66 * abs(_dot(normal, light))))
        gray = int(round(62 + intensity * 150))
        depth = sum(projected[index][2] for index in (ia, ib, ic)) / 3.0
        coords = " ".join(f"{sx:.2f},{sy:.2f}" for sx, sy in (screen(ia), screen(ib), screen(ic)))
        faces.append((depth, f'<polygon points="{coords}" fill="rgb({gray},{gray},{gray})" stroke="#24313c" stroke-width="0.55"/>'))
    faces.sort(key=lambda row: row[0])
    return (
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="9" fill="#0d1319" stroke="#354654"/>'
        + "".join(face for _, face in faces)
        + f'<text x="{x0 + 12}" y="{y0 + 24}" fill="#f2f5f7" font-family="monospace" font-size="14">{html.escape(label)}</text>'
    )


def _comparison_svg(receipt, baseline_candidate, review_candidate):
    width, height = 1240, 780
    panels = []
    poses_by_label = [
        ("baseline", baseline_candidate, receipt["baseline"]["poses"]),
        ("review 0.085m bend-plane", review_candidate, receipt["candidate"]["poses"]),
    ]
    for row_index, (row_label, candidate, poses) in enumerate(poses_by_label):
        for col_index, pose in enumerate(poses):
            panels.append(
                _shaded_mesh_group(
                    [tuple(point) for point in pose["positions"]],
                    candidate["indices"],
                    20 + col_index * 405,
                    50 + row_index * 350,
                    385,
                    320,
                    f'{row_label} | {pose["angle_deg"]:+.0f} deg',
                )
            )
    footer = (
        "Deterministic filled-triangle three-quarter evidence projection. "
        "Source remains unchanged; candidate is review-only. Not target-render, anatomy, or deformation acceptance."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#080c10"/>'
        '<text x="20" y="30" fill="#dfe7ee" font-family="monospace" font-size="17">Animal elbow bend-plane relief — exact baseline vs Organic review candidate</text>'
        + "".join(panels)
        + f'<text x="20" y="760" fill="#7f93a5" font-family="monospace" font-size="11">{html.escape(footer)}</text>'
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
    rig_path = Path(args.rig_plan)
    spec = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(rig_path.read_text(encoding="utf-8"))
    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise SystemExit("rig donor head drift")
    if digest(spec) != SOURCE_DIGEST:
        raise SystemExit("source digest drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("rig plan digest drift")

    receipt = inspect_elbow_relief_review(spec, plan)
    if receipt["candidate_digest"] != CANDIDATE_DIGEST:
        raise SystemExit("organic review candidate digest drift")
    baseline_candidate, _ = _build_exact_candidate(spec)
    review_candidate, _ = build_elbow_relief_candidate(spec, plan)

    receipt["lineage"] = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "rigging_pr6_base_head": RIGGING_PR6_BASE_HEAD,
        "geometry_pr4_head": GEOMETRY_PR4_HEAD,
        "rigging_pr2_donor_head": EXPECTED_RIG_DONOR_HEAD,
    }
    receipt["non_claims"] = [
        "The canonical Organic source JSON is unchanged.",
        "The candidate is a derived review variant, not source adoption.",
        "The smaller bend-plane cross-section is not a biological or anatomical claim.",
        "The sampled edge-ratio improvement is not Rigging, skinning, or volume-preservation acceptance.",
        "The retained SVG is a deterministic evidence projection, not target-engine rendering or Art Direction acceptance.",
        "No continuous animation, runtime, collision, gameplay, CANON, production-readiness, or mastery claim is made.",
    ]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "organic-elbow-relief-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "baseline-connected-forelimb.json").write_text(json.dumps(baseline_candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "review-elbow-relief-candidate.json").write_text(json.dumps(review_candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "baseline-vs-elbow-relief-three-quarter.svg").write_text(
        _comparison_svg(receipt, baseline_candidate, review_candidate), encoding="utf-8"
    )
    (out / "source.json").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "rig-plan.json").write_text(rig_path.read_text(encoding="utf-8"), encoding="utf-8")

    if receipt["decision"] != "PASS_BOUNDED_ELBOW_BEND_PLANE_RELIEF_REVIEW_CANDIDATE":
        raise SystemExit("organic elbow relief review gate failed")

    print(json.dumps({
        "decision": receipt["decision"],
        "candidate_digest": receipt["candidate_digest"],
        "scope": receipt["scope"],
        "comparisons": receipt["comparisons"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
