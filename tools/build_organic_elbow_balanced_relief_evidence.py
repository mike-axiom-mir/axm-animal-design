#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

from axm_animal_design.connected_deformation import _build_exact_candidate, digest
from axm_animal_design.organic_elbow_relief import build_elbow_relief_candidate
from axm_animal_design.organic_elbow_balanced_relief import (
    BASELINE_CANDIDATE_DIGEST,
    CANDIDATE_DIGEST,
    EASE_OUT_EXPONENT,
    PREDECESSOR_CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    build_balanced_elbow_candidate,
    inspect_balanced_elbow_review,
)

EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
EXPECTED_CONNECTED_RIGGING_HEAD = "5625c9f796a75e8b441458c51093e55519490611"
EXPECTED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
EXPECTED_WEIGHTING_NAME = "ease-out-power-0p75-v1"
METRIC_TOLERANCE = 1e-9
ELBOW_RING = tuple(range(11, 21))
POSE_ANGLES = (-60.0, 0.0, 60.0)
CAMERAS = (
    {
        "id": "outer-three-quarter",
        "eye": (1.48, 1.36, 1.08),
        "target": (0.46, 0.28, 0.42),
        "up": (0.0, 0.0, 1.0),
        "focal": 1.15,
    },
    {
        "id": "bend-profile",
        "eye": (1.62, 0.88, 0.58),
        "target": (0.46, 0.28, 0.42),
        "up": (0.0, 0.0, 1.0),
        "focal": 1.30,
    },
)


def _validate_weighting_donor(receipt: dict[str, Any], local_baseline: dict[str, Any]) -> list[dict[str, Any]]:
    if receipt.get("gate") != "PASS_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT":
        raise ValueError("connected Rigging donor is not a passing weighting receipt")
    if receipt.get("connected_candidate_digest") != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("connected Rigging donor topology identity drift")
    if receipt.get("rig_plan_digest") != RIG_PLAN_DIGEST:
        raise ValueError("connected Rigging donor rig-plan identity drift")
    if receipt.get("weighting_profile_digest") != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise ValueError("connected Rigging donor weighting-profile identity drift")
    if receipt.get("candidate_weighting") != EXPECTED_WEIGHTING_NAME:
        raise ValueError("connected Rigging donor weighting name drift")
    if not math.isclose(float(receipt.get("candidate_exponent")), EASE_OUT_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("connected Rigging donor exponent drift")

    by_angle = {row["angle_deg"]: row for row in local_baseline["poses"]}
    replay = []
    for donor_row in receipt["comparisons"]:
        angle = float(donor_row["angle_deg"])
        local = by_angle.get(angle)
        if local is None:
            raise ValueError("local balanced-review pose schedule drift")
        donor_metrics = (
            float(donor_row["candidate_minimum_triangle_area_ratio"]),
            float(donor_row["candidate_maximum_triangle_area_ratio"]),
            float(donor_row["candidate_minimum_edge_length_ratio"]),
            float(donor_row["candidate_maximum_edge_length_ratio"]),
        )
        local_metrics = (
            float(local["minimum_triangle_area_ratio"]),
            float(local["maximum_triangle_area_ratio"]),
            float(local["minimum_edge_length_ratio"]),
            float(local["maximum_edge_length_ratio"]),
        )
        residual = max(abs(a - b) for a, b in zip(donor_metrics, local_metrics))
        if residual > METRIC_TOLERANCE:
            raise ValueError(f"local ease-out replay diverges from exact Rigging donor at {angle}: {residual}")
        replay.append({"angle_deg": angle, "maximum_metric_residual": round(residual, 12)})
    return replay


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(v):
    return math.sqrt(_dot(v, v))


def _normalize(v):
    length = _length(v)
    if length <= 1e-12:
        raise ValueError("review camera contains zero-length basis")
    return tuple(value / length for value in v)


def _camera_basis(camera):
    eye = tuple(camera["eye"])
    forward = _normalize(_sub(tuple(camera["target"]), eye))
    right = _normalize(_cross(forward, _normalize(tuple(camera["up"]))))
    up = _normalize(_cross(right, forward))
    return eye, right, up, forward


def _project(point, camera):
    eye, right, up, forward = _camera_basis(camera)
    rel = _sub(tuple(point), eye)
    depth = _dot(rel, forward)
    if depth <= 0.05:
        raise ValueError("point behind review camera")
    focal = float(camera["focal"])
    return (focal * _dot(rel, right) / depth, focal * _dot(rel, up) / depth, depth)


def _frame(projected_sets):
    xs = [p[0] for points in projected_sets for p in points]
    ys = [p[1] for points in projected_sets for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    sx = max(max_x - min_x, 1e-9)
    sy = max(max_y - min_y, 1e-9)
    return (min_x - sx * 0.08, max_x + sx * 0.08, min_y - sy * 0.08, max_y + sy * 0.08)


def _mapper(frame, x0, y0, width, height):
    min_x, max_x, min_y, max_y = frame
    sx = max(max_x - min_x, 1e-9)
    sy = max(max_y - min_y, 1e-9)
    scale = min((width - 20) / sx, (height - 38) / sy)
    cx, cy = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5

    def screen(point):
        return (
            x0 + width * 0.5 + (point[0] - cx) * scale,
            y0 + height * 0.55 - (point[1] - cy) * scale,
        )

    return screen


def _shade(a, b, c):
    normal = _cross(_sub(b, a), _sub(c, a))
    if _length(normal) <= 1e-12:
        return 82
    normal = _normalize(normal)
    light = _normalize((0.35, -0.45, 0.82))
    intensity = max(0.0, min(1.0, 0.30 + 0.70 * abs(_dot(normal, light))))
    return int(round(58 + 160 * intensity))


def _panel(positions, indices, camera, frame, x0, y0, width, height, label):
    projected = [_project(point, camera) for point in positions]
    screen = _mapper(frame, x0, y0, width, height)
    faces = []
    for offset in range(0, len(indices), 3):
        ia, ib, ic = indices[offset:offset + 3]
        gray = _shade(tuple(positions[ia]), tuple(positions[ib]), tuple(positions[ic]))
        depth = sum(projected[i][2] for i in (ia, ib, ic)) / 3.0
        coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in (screen(projected[ia]), screen(projected[ib]), screen(projected[ic])))
        faces.append((depth, f'<polygon points="{coords}" fill="rgb({gray},{gray},{gray})" stroke="#20313f" stroke-width="0.48"/>'))
    faces.sort(key=lambda row: row[0], reverse=True)
    ring = "".join(
        f'<circle cx="{screen(projected[i])[0]:.2f}" cy="{screen(projected[i])[1]:.2f}" r="1.75" fill="#ffbf66" stroke="#4b3512" stroke-width="0.35"/>'
        for i in ELBOW_RING
    )
    return (
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="7" fill="#0b1117" stroke="#344754"/>'
        + "".join(face for _, face in faces)
        + ring
        + f'<text x="{x0 + 8}" y="{y0 + 17}" fill="#edf2f5" font-family="monospace" font-size="10.5">{html.escape(label)}</text>'
    )


def _board_svg(review: dict[str, Any], candidate_meshes: dict[str, dict[str, Any]], camera):
    width, height = 1240, 930
    forms = (
        ("baseline", "baseline"),
        ("predecessor 0.085m", "predecessor_relief"),
        ("balanced 0.0875m + Yx1.03", "balanced_successor"),
    )
    probes = review["probes"]["smoothstep-v0"]
    by_form = {name: {p["angle_deg"]: p for p in probes[key]["poses"]} for name, key in forms}
    panels = []
    for col, angle in enumerate(POSE_ANGLES):
        projected_sets = []
        for form_name, _ in forms:
            projected_sets.append([_project(point, camera) for point in by_form[form_name][angle]["positions"]])
        shared = _frame(projected_sets)
        for row, (form_name, key) in enumerate(forms):
            panels.append(
                _panel(
                    by_form[form_name][angle]["positions"],
                    candidate_meshes[key]["indices"],
                    camera,
                    shared,
                    18 + col * 407,
                    44 + row * 286,
                    389,
                    276,
                    f"{form_name} | {angle:+.0f} deg",
                )
            )
    footer = (
        f"Locked true-perspective {camera['id']} review, smoothstep poses. Same frame per angle across all three forms; orange = exact elbow ring. "
        "Balanced successor is review-only; no anatomy, Rigging, source adoption or visual acceptance."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#070b0f"/>'
        f'<text x="18" y="26" fill="#dce6ee" font-family="monospace" font-size="15">Animal balanced elbow relief successor — {html.escape(camera["id"])}</text>'
        + "".join(panels)
        + f'<text x="18" y="918" fill="#7e92a3" font-family="monospace" font-size="9.5">{html.escape(footer)}</text>'
        + '</svg>\n'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--donor-receipt", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--connected-rigging-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise SystemExit("rig donor head drift")
    if args.connected_rigging_head != EXPECTED_CONNECTED_RIGGING_HEAD:
        raise SystemExit("connected Rigging donor head drift")

    source_path = Path(args.source)
    plan_path = Path(args.rig_plan)
    profile_path = Path(args.weighting_profile)
    donor_path = Path(args.donor_receipt)
    spec = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    donor = json.loads(donor_path.read_text(encoding="utf-8"))

    if digest(spec) != SOURCE_DIGEST:
        raise SystemExit("source digest drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("rig plan digest drift")
    if digest(profile) != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("weighting profile digest drift")
    if profile.get("candidate_profile") != EXPECTED_WEIGHTING_NAME:
        raise SystemExit("weighting profile name drift")
    if not math.isclose(float(profile.get("candidate_exponent")), EASE_OUT_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit("weighting profile exponent drift")

    review = inspect_balanced_elbow_review(spec, plan)
    replay = _validate_weighting_donor(donor, review["probes"]["ease-out-power-0p75-v1"]["baseline"])
    review["lineage"] = {
        "repository": "mike-axiom-mir/axm-animal-design",
        "rigging_plan_donor_head": EXPECTED_RIG_DONOR_HEAD,
        "connected_rigging_weighting_head": EXPECTED_CONNECTED_RIGGING_HEAD,
        "weighting_profile_digest": EXPECTED_WEIGHTING_PROFILE_DIGEST,
    }
    review["rigging_donor_receiving_replay"] = replay
    review["non_claims"] = [
        "The canonical animal source JSON remains unchanged.",
        "The predecessor Organic elbow-relief candidate remains historical evidence and is not rewritten.",
        "The balanced candidate is a derived review variant, not source adoption.",
        "The 3% joint-axis support is not an anatomical or biological claim.",
        "The sampled structural improvement is not Rigging or weighting-profile acceptance.",
        "The locked perspective boards are source-space review evidence, not final shaded/rendered Visual QA acceptance.",
        "No continuous deformation, animation adoption, runtime, gameplay, CANON, production-readiness or mastery claim is made.",
    ]

    if review["decision"] != "PASS_BALANCED_ELBOW_RELIEF_REMOVES_MIN_AREA_TRADEOFF_ACROSS_PINNED_WEIGHTINGS":
        raise SystemExit("balanced Organic successor gate held")
    if review["adoption_state"] != "HOLD_VISUAL_AND_SOURCE_ADOPTION":
        raise SystemExit("balanced Organic successor unexpectedly changed adoption state")

    baseline, _ = _build_exact_candidate(spec)
    predecessor, _ = build_elbow_relief_candidate(spec, plan)
    balanced, _ = build_balanced_elbow_candidate(spec, plan)
    if digest(balanced) != CANDIDATE_DIGEST or digest(predecessor) != PREDECESSOR_CANDIDATE_DIGEST:
        raise SystemExit("Organic candidate identity drift")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "balanced-elbow-relief-receipt.json").write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "source.json").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "rig-plan.json").write_text(plan_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "weighting-profile.json").write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "connected-rigging-donor-receipt.json").write_text(donor_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "baseline-connected-forelimb.json").write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "predecessor-elbow-relief-candidate.json").write_text(json.dumps(predecessor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "balanced-elbow-relief-candidate.json").write_text(json.dumps(balanced, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    meshes = {"baseline": baseline, "predecessor_relief": predecessor, "balanced_successor": balanced}
    for camera in CAMERAS:
        (out / f"balanced-elbow-relief-perspective-{camera['id']}.svg").write_text(
            _board_svg(review, meshes, camera), encoding="utf-8"
        )

    print(json.dumps({
        "decision": review["decision"],
        "adoption_state": review["adoption_state"],
        "candidate_digest": review["balanced_candidate_digest"],
        "scope": review["scope"],
        "comparisons": review["comparisons"],
        "rigging_donor_receiving_replay": replay,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
