#!/usr/bin/env python3
"""Rebind the existing Animal articulation clip to the exact source-owned elbow successor.

Animation does not author a new rig or weighting profile here. The tool imports
and exercises the exact successor Rigging donor, keeps the established
`smoothstep-v0` Animation weighting, and samples the unchanged 1.0 s / 40 Hz
clip at all 41 authored endpoint-inclusive times.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SUCCESSOR_RIGGING_HEAD = "b48bb957622ed5c82a24ca4fcb471f7ee9b5147a"
GEOMETRY_SUCCESSOR_HEAD = "eb5ce99798b646b6ab9705c0c914b898173f7cc1"
ORGANIC_SUCCESSOR_HEAD = "7314a8971abb53f8ee6ef226c2496ab6d5da20d7"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
HISTORICAL_WEIGHTING_HEAD = "5625c9f796a75e8b441458c51093e55519490611"
EXPECTED_BASE_SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
EXPECTED_SOURCE_PROFILE_DIGEST = "8dbab7764819ebcbf825f6d0650053b108b8773df3644934738e3ec9f4712e66"
EXPECTED_SOURCE_SUCCESSOR_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
EXPECTED_CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
SCHEMA = "axm.animal-animation-source-successor-motion-rebind/v0.1"
FRAME_SCHEMA = "axm.animal-animation-source-successor-motion-frames/v0.1"
GATE = "PASS_SOURCE_SUCCESSOR_41_SAMPLE_MOTION_REBIND"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _raised_cosine(sample_index: int, interval_count: int) -> float:
    if sample_index in (0, interval_count):
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * sample_index / interval_count)


def _write_strip(frames: list[dict[str, Any]], indices: list[int], output: Path) -> None:
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
    scale = min((pane_w - 2 * pad) / span_x, (pane_h - 55.0) / span_z)
    width = pane_w * len(selected)
    edges: set[tuple[int, int]] = set()
    for offset in range(0, len(indices), 3):
        tri = indices[offset : offset + 3]
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.add(tuple(sorted((a, b))))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(pane_h)}" viewBox="0 0 {width:.0f} {pane_h:.0f}">',
        '<rect width="100%" height="100%" fill="#111"/>',
        '<style>text{font-family:monospace;font-size:12px;fill:#ddd}.edge{stroke:#ddd;stroke-width:1;fill:none}.peak{stroke-width:1.5}</style>',
    ]
    for pane, frame in enumerate(selected):
        x0 = pane * pane_w
        projected = []
        for point in frame["positions"]:
            projected.append((x0 + pad + (point[0] - min_x) * scale, 25.0 + (max_z - point[2]) * scale))
        klass = "edge peak" if frame["sample_index"] == 20 else "edge"
        for a, b in sorted(edges):
            ax, ay = projected[a]
            bx, by = projected[b]
            parts.append(f'<line class="{klass}" x1="{ax:.3f}" y1="{ay:.3f}" x2="{bx:.3f}" y2="{by:.3f}"/>')
        parts.append(f'<text x="{x0 + 8:.1f}" y="{pane_h - 29:.1f}">i={frame["sample_index"]:02d} t={frame["time_seconds"]:.3f}s</text>')
        parts.append(f'<text x="{x0 + 8:.1f}" y="{pane_h - 13:.1f}">elbow={frame["angle_deg"]:.6f}°</text>')
    parts.append("</svg>")
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")


def build(args: argparse.Namespace) -> dict[str, Any]:
    if args.successor_donor_head != SUCCESSOR_RIGGING_HEAD:
        raise ValueError("successor Rigging donor head drift")
    donor_src = args.successor_donor_root.resolve() / "src"
    if not donor_src.is_dir():
        raise ValueError(f"successor donor src missing: {donor_src}")
    sys.path.insert(0, str(donor_src))

    from axm_animal_design import elbow_source_successor_rigging_rebind as successor_rig  # type: ignore
    from axm_animal_design.connected_deformation import (  # type: ignore
        BASELINE_WEIGHTING,
        _select_joint,
        _sub,
        _vec3,
        _weights,
        digest,
    )
    from axm_animal_design.source_successor_topology_rebind import (  # type: ignore
        build_source_successor_topology_rebind,
    )

    if successor_rig.GEOMETRY_SUCCESSOR_HEAD != GEOMETRY_SUCCESSOR_HEAD:
        raise ValueError("Geometry successor identity drift inside Rigging donor")
    if successor_rig.ORGANIC_SUCCESSOR_HEAD != ORGANIC_SUCCESSOR_HEAD:
        raise ValueError("Organic successor identity drift inside Rigging donor")
    if successor_rig.RIG_DONOR_HEAD != RIG_DONOR_HEAD:
        raise ValueError("historical rig donor identity drift inside Rigging donor")
    if successor_rig.HISTORICAL_WEIGHTING_HEAD != HISTORICAL_WEIGHTING_HEAD:
        raise ValueError("historical weighting identity drift inside Rigging donor")

    spec = _load(args.source)
    source_profile = _load(args.source_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    clip = _load(args.clip)

    if digest(spec) != EXPECTED_BASE_SOURCE_DIGEST:
        raise ValueError("base source identity drift")
    if digest(source_profile) != EXPECTED_SOURCE_PROFILE_DIGEST:
        raise ValueError("source-successor profile identity drift")
    if digest(plan) != EXPECTED_RIG_PLAN_DIGEST:
        raise ValueError("rig-plan identity drift")
    if digest(weighting_profile) != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting-profile identity drift")
    if digest(clip) != EXPECTED_CLIP_DIGEST:
        raise ValueError("Animation clip identity drift")

    rigging_receipt = successor_rig.inspect_source_successor_rigging_rebind(
        spec, source_profile, plan, weighting_profile
    )
    if rigging_receipt.get("state") != "PASS_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP":
        raise ValueError("successor Rigging prerequisite is not green")
    if rigging_receipt.get("baseline_summary", {}).get("gate") != "PASS_SOURCE_SUCCESSOR_DENSE_STRUCTURAL_SWEEP":
        raise ValueError("smoothstep-v0 successor Rigging baseline is not green")

    if clip.get("schema") != "axm.animal-animation-motion-clip/v0.1":
        raise ValueError("clip schema drift")
    if clip.get("motion_semantics") != "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION":
        raise ValueError("clip truth label drift")
    if clip.get("rig_weighting_profile") != BASELINE_WEIGHTING or BASELINE_WEIGHTING != "smoothstep-v0":
        raise ValueError("Animation rebind must preserve smoothstep-v0; refined weighting is not adopted")
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
        raise ValueError("front-elbow-L track drift")

    candidate, topology = build_source_successor_topology_rebind(spec, source_profile)
    candidate_digest = digest(candidate)
    if candidate_digest != EXPECTED_SOURCE_SUCCESSOR_DIGEST:
        raise ValueError(f"source-successor candidate drift: {candidate_digest}")
    if topology.get("state") != "PASS_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("source-successor topology prerequisite is not green")

    positions = [tuple(float(value) for value in point) for point in candidate["positions"]]
    indices = [int(value) for value in candidate["indices"]]
    if len(positions) != 42 or len(indices) != 240:
        raise ValueError("source-successor connected topology count drift")

    joint = _select_joint(spec, plan)
    if joint.get("id") != "front-elbow-L":
        raise ValueError("front elbow joint selection drift")
    if max(abs(float(value)) for value in joint.get("pose_angles_deg", [])) < 18.0:
        raise ValueError("Animation peak exceeds Rigging verification envelope")
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    weights = _weights(positions, joint_position, child_direction, float(joint["influence_radius"]))
    source_areas = successor_rig._source_triangle_areas(positions, indices)

    frames: list[dict[str, Any]] = []
    for sample_index in range(interval_count + 1):
        envelope = _raised_cosine(sample_index, interval_count)
        angle_deg = 18.0 * envelope
        metrics = successor_rig._pose_metrics(
            positions, indices, source_areas, weights, joint_position, axis, angle_deg
        )
        rounded_positions = [[round(float(value), 12) for value in point] for point in metrics["positions"]]
        frame = {key: value for key, value in metrics.items() if key != "positions"}
        frame.update(
            {
                "sample_index": sample_index,
                "time_seconds": round(sample_index / sample_rate, 9),
                "envelope": round(envelope, 12),
                "angle_deg": round(angle_deg, 12),
                "positions": rounded_positions,
                "positions_digest": digest(rounded_positions),
            }
        )
        frames.append(frame)

    if any(frame.get("status") != "PASS" for frame in frames):
        raise ValueError("one or more authored Animation samples fail successor structural deformation gates")
    if frames[0]["positions"] != frames[-1]["positions"]:
        raise ValueError("endpoint neutral closure drift")
    if not math.isclose(float(frames[20]["angle_deg"]), 18.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("authored peak sample drift")

    max_mirror_position_residual = 0.0
    max_mirror_angle_residual = 0.0
    for index in range(interval_count + 1):
        mirror = interval_count - index
        max_mirror_angle_residual = max(
            max_mirror_angle_residual,
            abs(float(frames[index]["angle_deg"]) - float(frames[mirror]["angle_deg"])),
        )
        for a, b in zip(frames[index]["positions"], frames[mirror]["positions"]):
            max_mirror_position_residual = max(max_mirror_position_residual, math.dist(a, b))

    max_adjacent_vertex_step = 0.0
    for previous, current in zip(frames, frames[1:]):
        for a, b in zip(previous["positions"], current["positions"]):
            max_adjacent_vertex_step = max(max_adjacent_vertex_step, math.dist(a, b))
    visible_wrap_step = max(math.dist(a, b) for a, b in zip(frames[39]["positions"], frames[0]["positions"]))
    authored_final_step = max(math.dist(a, b) for a, b in zip(frames[39]["positions"], frames[40]["positions"]))
    wrap_step_residual = abs(visible_wrap_step - authored_final_step)

    rise = [float(frames[index]["angle_deg"]) for index in range(21)]
    fall = [float(frames[index]["angle_deg"]) for index in range(20, 41)]
    monotonic_rise = all(a <= b + 1e-12 for a, b in zip(rise, rise[1:]))
    monotonic_fall = all(a + 1e-12 >= b for a, b in zip(fall, fall[1:]))
    if not monotonic_rise or not monotonic_fall:
        raise ValueError("authored raised-cosine monotonicity drift")
    if max_mirror_position_residual > 1e-12 or max_mirror_angle_residual > 1e-12:
        raise ValueError("authored rise/fall mirror symmetry drift")
    if wrap_step_residual > 1e-12:
        raise ValueError("visible repeat wrap no longer matches authored final adjacent step")

    output = args.out
    output.mkdir(parents=True, exist_ok=True)
    frames_doc = {
        "schema": FRAME_SCHEMA,
        "source_successor_candidate_digest": candidate_digest,
        "indices": indices,
        "frames": frames,
    }
    (output / "source_successor_motion_frames.json").write_text(
        json.dumps(frames_doc, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    _write_strip(frames, indices, output / "source_successor_motion_strip.svg")

    receipt = {
        "schema": SCHEMA,
        "gate": GATE,
        "source_identity": {
            "base_source_digest": EXPECTED_BASE_SOURCE_DIGEST,
            "source_successor_profile_digest": EXPECTED_SOURCE_PROFILE_DIGEST,
            "source_successor_candidate_digest": candidate_digest,
            "organic_successor_head": ORGANIC_SUCCESSOR_HEAD,
            "geometry_successor_head": GEOMETRY_SUCCESSOR_HEAD,
            "rig_plan_digest": EXPECTED_RIG_PLAN_DIGEST,
            "weighting_profile_digest": EXPECTED_WEIGHTING_PROFILE_DIGEST,
            "clip_digest": EXPECTED_CLIP_DIGEST,
            "rig_weighting_profile": "smoothstep-v0",
            "motion_semantics": clip["motion_semantics"],
        },
        "successor_rigging_donor": {
            "git_head": SUCCESSOR_RIGGING_HEAD,
            "state": rigging_receipt["state"],
            "baseline_gate": rigging_receipt["baseline_summary"]["gate"],
            "refined_weighting_gate": rigging_receipt["refined_summary"]["gate"],
            "refined_weighting_adopted_by_animation": False,
        },
        "motion": {
            "clip_id": clip.get("name"),
            "duration_seconds": duration,
            "sample_rate_hz": sample_rate,
            "endpoint_inclusive_sample_count": len(frames),
            "peak_sample_index": 20,
            "peak_front_elbow_angle_deg": 18.0,
            "curve": clip["curve"],
            "motion_changed": False,
            "retimed": False,
            "retargeted": False,
            "weighting_changed": False,
        },
        "observed": {
            "all_41_samples_structural_pass": True,
            "maximum_nonadjacent_self_intersection_pairs": max(int(frame["nonadjacent_self_intersection_pairs"]) for frame in frames),
            "maximum_collapsed_triangles": max(int(frame["collapsed_triangles"]) for frame in frames),
            "maximum_fixed_weight_vertex_drift_m": max(float(frame["fixed_weight_vertex_max_drift_m"]) for frame in frames),
            "maximum_rigid_weight_radius_drift_m": max(float(frame["rigid_weight_radius_max_drift_m"]) for frame in frames),
            "minimum_triangle_area_ratio_over_clip": min(float(frame["minimum_triangle_area_ratio"]) for frame in frames),
            "maximum_triangle_area_ratio_over_clip": max(float(frame["maximum_triangle_area_ratio"]) for frame in frames),
            "minimum_edge_length_ratio_over_clip": min(float(frame["minimum_edge_length_ratio"]) for frame in frames),
            "maximum_edge_length_ratio_over_clip": max(float(frame["maximum_edge_length_ratio"]) for frame in frames),
            "maximum_adjacent_vertex_step_m": max_adjacent_vertex_step,
            "maximum_rise_fall_position_residual_m": max_mirror_position_residual,
            "maximum_rise_fall_angle_residual_deg": max_mirror_angle_residual,
            "visible_wrap_step_m": visible_wrap_step,
            "authored_final_adjacent_step_m": authored_final_step,
            "wrap_step_residual_m": wrap_step_residual,
            "exact_neutral_start_return": True,
            "monotonic_rise": monotonic_rise,
            "monotonic_fall": monotonic_fall,
        },
        "truth_boundary": {
            "source_successor_rebound": True,
            "clip_or_timing_changed": False,
            "smoothstep_v0_preserved": True,
            "ease_out_power_0p75_adopted": False,
            "all_authored_sample_surfaces_directly_retested": True,
            "continuous_between_sample_interpolation_proved": False,
            "visual_quality_accepted": False,
            "runtime_controller_or_state_machine_accepted": False,
            "real_time_frame_pacing_proved": False,
            "gameplay_accepted": False,
            "canon_claimed": False,
        },
    }
    (output / "source_successor_motion_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-profile", type=Path, required=True)
    parser.add_argument("--rig-plan", type=Path, required=True)
    parser.add_argument("--weighting-profile", type=Path, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--successor-donor-root", type=Path, required=True)
    parser.add_argument("--successor-donor-head", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), sort_keys=True))


if __name__ == "__main__":
    main()
