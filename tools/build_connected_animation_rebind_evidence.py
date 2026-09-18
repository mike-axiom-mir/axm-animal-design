#!/usr/bin/env python3
"""Build Animation-owned evidence for the existing clip on the exact connected forelimb.

This tool intentionally does not copy a deformation solver. It imports the exact
Rigging PR #6 donor implementation from a separately checked-out, revision-pinned
repository tree and samples that implementation at the existing Animation clip's
41 authored times. The result is bounded motion evidence for one connected left
forelimb candidate only; it is not source adoption, rig acceptance, runtime-
controller acceptance, locomotion, or gameplay evidence.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

CONNECTED_RIGGING_DONOR_HEAD = "f4614ab2f691cd5c5d12b88fabc38ef848acd24e"
EXPECTED_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
SCHEMA = "axm.animal-animation-connected-forelimb-motion-rebind/v0.1"
DRIFT_TOLERANCE = 1e-9
SYMMETRY_TOLERANCE = 1e-12


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _raised_cosine(sample_index: int, interval_count: int) -> float:
    if sample_index in (0, interval_count):
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * sample_index / interval_count)


def _project_strip(frames: list[dict[str, Any]], indices: list[int], output: Path) -> None:
    selected_indices = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    selected = [frames[index] for index in selected_indices]
    all_points = [point for frame in selected for point in frame["positions"]]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_z = min(point[2] for point in all_points)
    max_z = max(point[2] for point in all_points)
    span_x = max(max_x - min_x, 1e-9)
    span_z = max(max_z - min_z, 1e-9)
    pane_w, pane_h, pad = 190.0, 230.0, 20.0
    usable_w, usable_h = pane_w - 2 * pad, pane_h - 55.0
    scale = min(usable_w / span_x, usable_h / span_z)
    width = pane_w * len(selected)
    height = pane_h

    edges: set[tuple[int, int]] = set()
    for offset in range(0, len(indices), 3):
        tri = indices[offset : offset + 3]
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.add(tuple(sorted((a, b))))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" viewBox="0 0 {width:.0f} {height:.0f}">',
        '<rect width="100%" height="100%" fill="#111"/>',
        '<style>text{font-family:monospace;font-size:12px;fill:#ddd}.edge{stroke:#ddd;stroke-width:1;fill:none}.peak{stroke-width:1.5}</style>',
    ]
    for pane, frame in enumerate(selected):
        x0 = pane * pane_w
        parts.append(f'<rect x="{x0 + 1:.1f}" y="1" width="{pane_w - 2:.1f}" height="{pane_h - 2:.1f}" fill="none" stroke="#333"/>')
        points = frame["positions"]
        projected = []
        for point in points:
            sx = x0 + pad + (point[0] - min_x) * scale
            sy = 25.0 + (max_z - point[2]) * scale
            projected.append((sx, sy))
        klass = "edge peak" if frame["sample_index"] == 20 else "edge"
        for a, b in sorted(edges):
            ax, ay = projected[a]
            bx, by = projected[b]
            parts.append(f'<line class="{klass}" x1="{ax:.3f}" y1="{ay:.3f}" x2="{bx:.3f}" y2="{by:.3f}"/>')
        parts.append(
            f'<text x="{x0 + 8:.1f}" y="{height - 29:.1f}">i={frame["sample_index"]:02d} t={frame["time_seconds"]:.3f}s</text>'
        )
        parts.append(
            f'<text x="{x0 + 8:.1f}" y="{height - 13:.1f}">elbow={frame["angle_deg"]:.6f}°</text>'
        )
    parts.append('</svg>')
    output.write_text("\n".join(parts) + "\n")


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.connected_donor_head != CONNECTED_RIGGING_DONOR_HEAD:
        raise ValueError(
            f"connected Rigging donor head mismatch: {args.connected_donor_head} != {CONNECTED_RIGGING_DONOR_HEAD}"
        )

    donor_src = args.connected_donor_root.resolve() / "src"
    if not donor_src.is_dir():
        raise ValueError(f"connected donor src directory missing: {donor_src}")
    sys.path.insert(0, str(donor_src))
    from axm_animal_design import connected_deformation as cd  # type: ignore

    spec = _load(args.source)
    plan = _load(args.rig_plan)
    clip = _load(args.clip)

    source_digest = cd.digest(spec)
    rig_digest = cd.digest(plan)
    clip_digest = cd.digest(clip)
    if source_digest != EXPECTED_SOURCE_DIGEST:
        raise ValueError(f"source identity drift: {source_digest}")
    if rig_digest != EXPECTED_RIG_PLAN_DIGEST:
        raise ValueError(f"rig-plan identity drift: {rig_digest}")
    if clip_digest != EXPECTED_CLIP_DIGEST:
        raise ValueError(f"clip identity drift: {clip_digest}")

    if clip.get("schema") != "axm.animal-animation-motion-clip/v0.1":
        raise ValueError("clip schema drift")
    if clip.get("motion_semantics") != "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION":
        raise ValueError("clip truth label drift")
    if clip.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("connected motion proof must stay on accepted smoothstep-v0 baseline")
    if clip.get("curve") != "raised-cosine-neutral-to-peak-to-neutral":
        raise ValueError("clip curve drift")
    duration = float(clip.get("duration_seconds"))
    sample_rate = int(clip.get("sample_rate_hz"))
    if duration != 1.0 or sample_rate != 40:
        raise ValueError("clip timing drift; expected exact 1.0 s / 40 Hz")
    interval_count = int(round(duration * sample_rate))
    if interval_count != 40:
        raise ValueError("clip interval-count drift")

    tracks = {row.get("joint_id"): row for row in clip.get("tracks", []) if isinstance(row, dict)}
    track = tracks.get("front-elbow-L")
    if not track or float(track.get("peak_angle_deg")) != 18.0:
        raise ValueError("front-elbow-L track drift; expected exact +18° peak")

    candidate, radius_derivation = cd._build_exact_candidate(spec)
    candidate_digest = cd.digest(candidate)
    if candidate_digest != EXPECTED_CANDIDATE_DIGEST:
        raise ValueError(f"connected candidate identity drift: {candidate_digest}")
    joint = cd._select_joint(spec, plan)
    if max(abs(float(value)) for value in joint["pose_angles_deg"]) < 18.0:
        raise ValueError("Animation peak exceeds Rigging-probed envelope")

    positions = [tuple(float(v) for v in point) for point in candidate["positions"]]
    indices = [int(value) for value in candidate["indices"]]
    landmarks = spec["landmarks"]
    joint_position = cd._vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = cd._vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = cd._sub(child_marker, joint_position)
    axis = cd._vec3(joint["axis"], "joint axis")
    weights = cd._weights(positions, joint_position, child_direction, float(joint["influence_radius"]))

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        area = cd._triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("connected source candidate contains a collapsed triangle")
        source_areas.append(area)
    source_self = cd.inspect_triangle_self_intersections(positions, indices)
    if source_self["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("connected source candidate no longer passes static self-intersection gate")

    frames: list[dict[str, Any]] = []
    worst_min_area = math.inf
    worst_max_area = 0.0
    worst_min_edge = math.inf
    worst_max_edge = 0.0
    max_fixed_drift = 0.0
    max_rigid_radius_drift = 0.0
    max_vertex_displacement = 0.0
    all_structural_pass = True

    for sample_index in range(interval_count + 1):
        time_seconds = sample_index / sample_rate
        envelope = _raised_cosine(sample_index, interval_count)
        angle = 18.0 * envelope
        if sample_index in (0, interval_count):
            posed = list(positions)
        else:
            posed = []
            for point, (_, child_weight) in zip(positions, weights):
                rotated = cd._rotate_about_axis(point, joint_position, axis, angle)
                posed.append(cd._add(point, cd._mul(cd._sub(rotated, point), child_weight)))

        fixed_drift = 0.0
        rigid_radius_drift = 0.0
        vertex_displacement = 0.0
        for before, after, (_, child_weight) in zip(positions, posed, weights):
            vertex_displacement = max(vertex_displacement, math.dist(before, after))
            if child_weight <= 1e-9:
                fixed_drift = max(fixed_drift, math.dist(before, after))
            if child_weight >= 1.0 - 1e-9:
                rigid_radius_drift = max(
                    rigid_radius_drift,
                    abs(math.dist(before, joint_position) - math.dist(after, joint_position)),
                )

        area_ratios = []
        collapsed = 0
        for tri_index, offset in enumerate(range(0, len(indices), 3)):
            a, b, c = (posed[indices[offset]], posed[indices[offset + 1]], posed[indices[offset + 2]])
            area = cd._triangle_double_area(a, b, c)
            if area <= 1e-12:
                collapsed += 1
            area_ratios.append(area / source_areas[tri_index])
        min_edge, max_edge = cd._edge_metrics(positions, posed, indices)
        self_result = cd.inspect_triangle_self_intersections(posed, indices)
        finite = all(math.isfinite(value) for point in posed for value in point)
        status = (
            finite
            and collapsed == 0
            and fixed_drift <= DRIFT_TOLERANCE
            and rigid_radius_drift <= DRIFT_TOLERANCE
            and self_result["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS"
        )
        all_structural_pass &= status
        worst_min_area = min(worst_min_area, min(area_ratios))
        worst_max_area = max(worst_max_area, max(area_ratios))
        worst_min_edge = min(worst_min_edge, min_edge)
        worst_max_edge = max(worst_max_edge, max_edge)
        max_fixed_drift = max(max_fixed_drift, fixed_drift)
        max_rigid_radius_drift = max(max_rigid_radius_drift, rigid_radius_drift)
        max_vertex_displacement = max(max_vertex_displacement, vertex_displacement)

        rounded_positions = [[round(value, 12) for value in point] for point in posed]
        frames.append(
            {
                "sample_index": sample_index,
                "time_seconds": round(time_seconds, 9),
                "envelope": round(envelope, 12),
                "angle_deg": round(angle, 12),
                "positions": rounded_positions,
                "positions_digest": cd.digest(rounded_positions),
                "collapsed_triangles": collapsed,
                "minimum_triangle_area_ratio": round(min(area_ratios), 12),
                "maximum_triangle_area_ratio": round(max(area_ratios), 12),
                "minimum_edge_length_ratio": round(min_edge, 12),
                "maximum_edge_length_ratio": round(max_edge, 12),
                "fixed_weight_vertex_max_drift_m": round(fixed_drift, 15),
                "rigid_weight_radius_max_drift_m": round(rigid_radius_drift, 15),
                "maximum_vertex_displacement_m": round(vertex_displacement, 12),
                "nonadjacent_self_intersection_pairs": int(self_result["self_intersection_pair_count"]),
                "status": "PASS" if status else "FAIL",
            }
        )

    max_mirror_position_residual = 0.0
    max_mirror_angle_residual = 0.0
    for index in range(interval_count + 1):
        mirror = interval_count - index
        max_mirror_angle_residual = max(
            max_mirror_angle_residual,
            abs(frames[index]["angle_deg"] - frames[mirror]["angle_deg"]),
        )
        for left_point, right_point in zip(frames[index]["positions"], frames[mirror]["positions"]):
            max_mirror_position_residual = max(
                max_mirror_position_residual,
                math.dist(left_point, right_point),
            )

    max_adjacent_vertex_step = 0.0
    for index in range(1, len(frames)):
        previous = frames[index - 1]["positions"]
        current = frames[index]["positions"]
        for a, b in zip(previous, current):
            max_adjacent_vertex_step = max(max_adjacent_vertex_step, math.dist(a, b))

    visible_wrap_step = max(
        math.dist(a, b) for a, b in zip(frames[39]["positions"], frames[0]["positions"])
    )
    authored_final_step = max(
        math.dist(a, b) for a, b in zip(frames[39]["positions"], frames[40]["positions"])
    )
    wrap_step_residual = abs(visible_wrap_step - authored_final_step)

    rise_angles = [frames[index]["angle_deg"] for index in range(0, 21)]
    fall_angles = [frames[index]["angle_deg"] for index in range(20, 41)]
    monotonic_rise = all(a <= b + 1e-12 for a, b in zip(rise_angles, rise_angles[1:]))
    monotonic_fall = all(a + 1e-12 >= b for a, b in zip(fall_angles, fall_angles[1:]))
    exact_neutral_start = frames[0]["positions"] == [[round(v, 12) for v in p] for p in positions]
    exact_neutral_return = frames[40]["positions"] == frames[0]["positions"]
    peak_is_exact = abs(frames[20]["angle_deg"] - 18.0) <= 1e-12
    material_motion = frames[20]["maximum_vertex_displacement_m"] > 0.001

    gate_pass = (
        all_structural_pass
        and exact_neutral_start
        and exact_neutral_return
        and peak_is_exact
        and material_motion
        and monotonic_rise
        and monotonic_fall
        and max_mirror_position_residual <= SYMMETRY_TOLERANCE
        and max_mirror_angle_residual <= SYMMETRY_TOLERANCE
        and wrap_step_residual <= SYMMETRY_TOLERANCE
    )

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    frames_payload = {
        "schema": "axm.animal-animation-connected-forelimb-motion-frames/v0.1",
        "candidate_id": candidate["id"],
        "candidate_digest": candidate_digest,
        "indices": indices,
        "frames": frames,
    }
    (out / "connected_forelimb_motion_frames.json").write_text(json.dumps(frames_payload, indent=2) + "\n")
    _project_strip(frames, indices, out / "connected_forelimb_motion_strip.svg")

    receipt = {
        "schema": SCHEMA,
        "state": "PASS_CONNECTED_FORELIMB_EXACT_CLIP_MOTION" if gate_pass else "FAIL_CONNECTED_FORELIMB_EXACT_CLIP_MOTION",
        "source_identity": {
            "source_name": spec.get("name"),
            "source_digest": source_digest,
            "rig_plan_digest": rig_digest,
            "clip_name": clip.get("name"),
            "clip_digest": clip_digest,
            "rig_weighting_profile": clip.get("rig_weighting_profile"),
            "motion_semantics": clip.get("motion_semantics"),
        },
        "connected_rigging_donor": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "git_head": args.connected_donor_head,
            "candidate_id": candidate["id"],
            "candidate_digest": candidate_digest,
            "radius_derivation": radius_derivation,
            "joint_id": joint["id"],
            "joint_axis": list(axis),
            "influence_radius_m": float(joint["influence_radius"]),
            "rig_probe_angles_deg": list(joint["pose_angles_deg"]),
        },
        "animation": {
            "duration_seconds": duration,
            "sample_rate_hz": sample_rate,
            "endpoint_inclusive_sample_count": len(frames),
            "visible_samples_per_cycle": 40,
            "curve": clip.get("curve"),
            "front_elbow_left_peak_angle_deg": 18.0,
            "retimed": False,
            "retargeted": False,
            "weighting_changed": False,
            "clip_changed": False,
        },
        "metrics": {
            "candidate_vertices": len(positions),
            "candidate_triangles": len(indices) // 3,
            "all_41_samples_structurally_pass": all_structural_pass,
            "exact_neutral_start": exact_neutral_start,
            "exact_neutral_return": exact_neutral_return,
            "exact_peak_at_sample_20": peak_is_exact,
            "material_peak_motion": material_motion,
            "peak_maximum_vertex_displacement_m": frames[20]["maximum_vertex_displacement_m"],
            "maximum_adjacent_vertex_step_m": round(max_adjacent_vertex_step, 12),
            "visible_wrap_step_m": round(visible_wrap_step, 12),
            "authored_final_step_m": round(authored_final_step, 12),
            "wrap_step_residual_m": round(wrap_step_residual, 15),
            "maximum_mirrored_position_residual_m": round(max_mirror_position_residual, 15),
            "maximum_mirrored_angle_residual_deg": round(max_mirror_angle_residual, 15),
            "monotonic_rise": monotonic_rise,
            "monotonic_fall": monotonic_fall,
            "worst_minimum_triangle_area_ratio": round(worst_min_area, 12),
            "worst_maximum_triangle_area_ratio": round(worst_max_area, 12),
            "worst_minimum_edge_length_ratio": round(worst_min_edge, 12),
            "worst_maximum_edge_length_ratio": round(worst_max_edge, 12),
            "maximum_fixed_weight_vertex_drift_m": round(max_fixed_drift, 15),
            "maximum_rigid_weight_radius_drift_m": round(max_rigid_radius_drift, 15),
            "maximum_vertex_displacement_any_sample_m": round(max_vertex_displacement, 12),
            "samples_with_collapse": sum(1 for frame in frames if frame["collapsed_triangles"] != 0),
            "samples_with_self_intersection": sum(
                1 for frame in frames if frame["nonadjacent_self_intersection_pairs"] != 0
            ),
        },
        "truth_boundary": {
            "exact_existing_animation_timing_reused": True,
            "exact_connected_rigging_donor_reused": True,
            "all_authored_sample_times_tested_on_connected_candidate": True,
            "target_engine_playback_tested": False,
            "continuous_between_sample_interpolation_tested": False,
            "volume_preservation_tested": False,
            "perceptual_deformation_quality_tested": False,
            "biological_gait_or_locomotion_claimed": False,
            "runtime_controller_or_state_machine_tested": False,
            "gameplay_tested": False,
            "source_adoption_claimed": False,
            "canon_or_production_readiness_claimed": False,
        },
        "gate": "PASS_EXACT_CONNECTED_FORELIMB_41_SAMPLE_MOTION_REBIND" if gate_pass else "FAIL_EXACT_CONNECTED_FORELIMB_41_SAMPLE_MOTION_REBIND",
    }
    (out / "connected_forelimb_motion_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--connected-donor-root", type=Path, required=True)
    parser.add_argument("--connected-donor-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = build(args)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt["gate"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
