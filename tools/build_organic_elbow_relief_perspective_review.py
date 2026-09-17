#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

REVIEW_SCHEMA = "axm.animal-organic-elbow-relief-perspective-review/v0.1"
EXPECTED_DECISION = "PASS_BOUNDED_ELBOW_BEND_PLANE_RELIEF_REVIEW_CANDIDATE"
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
        raise ValueError("camera basis contains a zero-length vector")
    return tuple(value / length for value in v)


def _camera_basis(camera: dict[str, Any]):
    eye = tuple(camera["eye"])
    target = tuple(camera["target"])
    up_hint = _normalize(tuple(camera["up"]))
    forward = _normalize(_sub(target, eye))
    right = _normalize(_cross(forward, up_hint))
    up = _normalize(_cross(right, forward))
    return eye, right, up, forward


def _project_point(point, camera):
    eye, right, up, forward = _camera_basis(camera)
    rel = _sub(tuple(point), eye)
    depth = _dot(rel, forward)
    if depth <= 0.05:
        raise ValueError(f"point behind/too close to review camera {camera['id']}: depth={depth}")
    focal = float(camera["focal"])
    return (focal * _dot(rel, right) / depth, focal * _dot(rel, up) / depth, depth)


def _project_positions(positions, camera):
    return [_project_point(point, camera) for point in positions]


def _union_frame(projected_sets):
    xs = [point[0] for points in projected_sets for point in points]
    ys = [point[1] for points in projected_sets for point in points]
    if not xs or not ys:
        raise ValueError("empty projected evidence set")
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    pad_x = span_x * 0.10
    pad_y = span_y * 0.10
    return (min_x - pad_x, max_x + pad_x, min_y - pad_y, max_y + pad_y)


def _screen_mapper(frame, x0, y0, width, height):
    min_x, max_x, min_y, max_y = frame
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min((width - 24) / span_x, (height - 48) / span_y)
    cx = (min_x + max_x) * 0.5
    cy = (min_y + max_y) * 0.5

    def screen(projected_point):
        px, py, _ = projected_point
        return (
            x0 + width * 0.5 + (px - cx) * scale,
            y0 + height * 0.54 - (py - cy) * scale,
        )

    return screen


def _shade_triangle(a, b, c):
    normal = _cross(_sub(b, a), _sub(c, a))
    nlen = _length(normal)
    if nlen <= 1e-12:
        return 80
    normal = tuple(value / nlen for value in normal)
    light = _normalize((0.35, -0.45, 0.82))
    intensity = max(0.0, min(1.0, 0.30 + 0.70 * abs(_dot(normal, light))))
    return int(round(56 + 164 * intensity))


def _mesh_svg(positions, indices, projected, frame, x0, y0, width, height, label, accent_ring=True):
    screen = _screen_mapper(frame, x0, y0, width, height)
    faces = []
    for offset in range(0, len(indices), 3):
        ia, ib, ic = indices[offset:offset + 3]
        points_3d = (tuple(positions[ia]), tuple(positions[ib]), tuple(positions[ic]))
        gray = _shade_triangle(*points_3d)
        depth = sum(projected[index][2] for index in (ia, ib, ic)) / 3.0
        coords = " ".join(
            f"{sx:.2f},{sy:.2f}"
            for sx, sy in (screen(projected[ia]), screen(projected[ib]), screen(projected[ic]))
        )
        faces.append(
            (
                depth,
                f'<polygon points="{coords}" fill="rgb({gray},{gray},{gray})" '
                'stroke="#20313f" stroke-width="0.52"/>',
            )
        )
    faces.sort(key=lambda row: row[0], reverse=True)
    ring = ""
    if accent_ring:
        ring_points = [screen(projected[index]) for index in ELBOW_RING]
        ring = "".join(
            f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="2.1" fill="#ffbe5c" '
            'stroke="#402d10" stroke-width="0.45"/>'
            for sx, sy in ring_points
        )
    return (
        f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" rx="8" '
        'fill="#0b1117" stroke="#344754"/>'
        + "".join(face for _, face in faces)
        + ring
        + f'<text x="{x0 + 10}" y="{y0 + 20}" fill="#f0f4f7" '
        f'font-family="monospace" font-size="13">{html.escape(label)}</text>'
    )


def _pose_map(receipt, key):
    poses = receipt[key]["poses"] if key == "baseline" else receipt["candidate"]["poses"]
    result = {float(pose["angle_deg"]): pose for pose in poses}
    if tuple(sorted(result)) != POSE_ANGLES:
        raise ValueError(f"unexpected pose set for {key}: {sorted(result)}")
    return result


def _camera_review(receipt, baseline_candidate, review_candidate, camera):
    baseline_poses = _pose_map(receipt, "baseline")
    candidate_poses = _pose_map(receipt, "candidate")
    rows = []
    for angle in POSE_ANGLES:
        baseline_positions = [tuple(point) for point in baseline_poses[angle]["positions"]]
        candidate_positions = [tuple(point) for point in candidate_poses[angle]["positions"]]
        if len(baseline_positions) != len(candidate_positions):
            raise ValueError("baseline/candidate vertex count drift")
        outside_ring_drift = max(
            math.dist(baseline_positions[index], candidate_positions[index])
            for index in range(len(baseline_positions))
            if index not in ELBOW_RING
        )
        if outside_ring_drift > 1e-9:
            raise ValueError(f"candidate pose drift escaped elbow ring at {angle:+.0f} deg")
        baseline_projected = _project_positions(baseline_positions, camera)
        candidate_projected = _project_positions(candidate_positions, camera)
        frame = _union_frame((baseline_projected, candidate_projected))
        screen = _screen_mapper(frame, 0, 0, 385, 300)
        ring_deltas = [
            math.dist(screen(baseline_projected[index]), screen(candidate_projected[index]))
            for index in ELBOW_RING
        ]
        rows.append(
            {
                "angle_deg": angle,
                "frame": [round(value, 12) for value in frame],
                "outside_elbow_ring_max_world_delta_m": round(outside_ring_drift, 12),
                "elbow_ring_max_screen_delta_px": round(max(ring_deltas), 6),
                "elbow_ring_mean_screen_delta_px": round(sum(ring_deltas) / len(ring_deltas), 6),
            }
        )
    return rows


def _board_svg(receipt, baseline_candidate, review_candidate, camera):
    width, height = 1240, 700
    baseline_poses = _pose_map(receipt, "baseline")
    candidate_poses = _pose_map(receipt, "candidate")
    panels = []
    for col, angle in enumerate(POSE_ANGLES):
        baseline_positions = [tuple(point) for point in baseline_poses[angle]["positions"]]
        candidate_positions = [tuple(point) for point in candidate_poses[angle]["positions"]]
        baseline_projected = _project_positions(baseline_positions, camera)
        candidate_projected = _project_positions(candidate_positions, camera)
        frame = _union_frame((baseline_projected, candidate_projected))
        x0 = 20 + col * 405
        panels.append(
            _mesh_svg(
                baseline_positions,
                baseline_candidate["indices"],
                baseline_projected,
                frame,
                x0,
                48,
                385,
                300,
                f"baseline | {angle:+.0f} deg",
            )
        )
        panels.append(
            _mesh_svg(
                candidate_positions,
                review_candidate["indices"],
                candidate_projected,
                frame,
                x0,
                358,
                385,
                300,
                f"review 0.085m | {angle:+.0f} deg",
            )
        )
    footer = (
        f"Locked true-perspective camera '{camera['id']}'. Each pose shares one frame across baseline/candidate; "
        "orange points mark the exact 10-vertex elbow ring. Source-space review evidence only."
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#070b0f"/>'
        f'<text x="20" y="28" fill="#dce6ee" font-family="monospace" font-size="16">'
        f'Animal elbow relief — locked perspective review — {html.escape(camera["id"])}</text>'
        + "".join(panels)
        + f'<text x="20" y="686" fill="#7e92a3" font-family="monospace" font-size="10.5">'
        f'{html.escape(footer)}</text>'
        + '</svg>\n'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    evidence = Path(args.evidence_dir)
    receipt_path = evidence / "organic-elbow-relief-receipt.json"
    baseline_path = evidence / "baseline-connected-forelimb.json"
    candidate_path = evidence / "review-elbow-relief-candidate.json"
    for path in (receipt_path, baseline_path, candidate_path):
        if not path.exists():
            raise SystemExit(f"missing prerequisite evidence: {path}")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    baseline_candidate = json.loads(baseline_path.read_text(encoding="utf-8"))
    review_candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if receipt.get("decision") != EXPECTED_DECISION:
        raise SystemExit("organic review prerequisite decision drift")
    if baseline_candidate.get("indices") != review_candidate.get("indices"):
        raise SystemExit("baseline/candidate topology drift")

    camera_rows = {}
    for camera in CAMERAS:
        rows = _camera_review(receipt, baseline_candidate, review_candidate, camera)
        camera_rows[camera["id"]] = rows
        (evidence / f"baseline-vs-elbow-relief-perspective-{camera['id']}.svg").write_text(
            _board_svg(receipt, baseline_candidate, review_candidate, camera),
            encoding="utf-8",
        )

    output = {
        "schema": REVIEW_SCHEMA,
        "decision": "PASS_LOCKED_CAMERA_PERSPECTIVE_REVIEW_EVIDENCE",
        "form_identity_changed": False,
        "source_rewritten": False,
        "candidate_rewritten": False,
        "topology_rewritten": False,
        "pose_angles_deg": list(POSE_ANGLES),
        "elbow_ring_vertex_indices": list(ELBOW_RING),
        "cameras": [
            {
                "id": camera["id"],
                "eye": list(camera["eye"]),
                "target": list(camera["target"]),
                "up": list(camera["up"]),
                "focal": camera["focal"],
                "poses": camera_rows[camera["id"]],
            }
            for camera in CAMERAS
        ],
        "truth_boundary": {
            "locked_matched_perspective_comparison": True,
            "exact_elbow_ring_highlighted": True,
            "outside_elbow_ring_pose_drift_rejected": True,
            "target_engine_render": False,
            "art_direction_accepted": False,
            "visual_qa_accepted": False,
            "anatomy_or_biology_validated": False,
            "rigging_accepted": False,
            "runtime_accepted": False,
        },
    }
    (evidence / "perspective-review-receipt.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "decision": output["decision"],
                "cameras": {
                    camera_id: [
                        {
                            "angle_deg": row["angle_deg"],
                            "max_screen_delta_px": row["elbow_ring_max_screen_delta_px"],
                            "outside_ring_drift_m": row["outside_elbow_ring_max_world_delta_m"],
                        }
                        for row in rows
                    ]
                    for camera_id, rows in camera_rows.items()
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
