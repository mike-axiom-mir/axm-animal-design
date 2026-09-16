#!/usr/bin/env python3
"""Bind the unchanged Animal articulation clip to the exact bilateral Rigging right surface.

This is Animation-owned evidence only. It consumes Rigging PR #12 as an exact donor,
preserves the existing smoothstep-v0 clip, samples both front elbows at all 41 authored
times, checks bilateral posed-vertex symmetry, and emits a right-surface payload for the
existing Godot discrete-sample proof host. It does not adopt Geometry PR #13's newer
right topology successor and does not claim controller/gameplay acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

RIGGING_HEAD = "94bc573e2e06ba7a35c9908c141e2f939d4739a8"
GEOMETRY_HEAD = "f89af95d621c36da3994c6660552da8bbc73fd1b"
ORGANIC_HEAD = "4df3024b4c459675422565501a46f622acf229a9"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
NEWER_GEOMETRY_SUCCESSOR_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
LEFT_SUCCESSOR_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
RIGHT_SUCCESSOR_DIGEST = "262f536e0e522fd3e102cb16464c3757985fbb1dfcb3001df3b1f27b623b0115"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
GATE = "PASS_BILATERAL_RIGHT_41_SAMPLE_MOTION_REBIND__NEWER_TOPOLOGY_HELD"
SCHEMA = "axm.animal-animation-bilateral-right-motion-rebind/v0.1"
FRAME_SCHEMA = "axm.animal-animation-bilateral-right-motion-frames/v0.1"
PAYLOAD_SCHEMA = "axm.animal-animation-godot-discrete-playback-payload/v0.1"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raised_cosine(sample_index: int, interval_count: int) -> float:
    if sample_index in (0, interval_count):
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * sample_index / interval_count)


def godot_point(point: list[float]) -> list[float]:
    x, y, z = (float(point[0]), float(point[1]), float(point[2]))
    return [-y, z, x]


def bounds(frames: list[dict[str, Any]]) -> dict[str, list[float]]:
    points = [point for frame in frames for point in frame["positions"]]
    mins = [min(float(point[axis]) for point in points) for axis in range(3)]
    maxs = [max(float(point[axis]) for point in points) for axis in range(3)]
    return {
        "min": mins,
        "max": maxs,
        "center": [(mins[i] + maxs[i]) / 2.0 for i in range(3)],
        "size": [maxs[i] - mins[i] for i in range(3)],
    }


def sample_side(rig: Any, deformation: Any, spec: dict[str, Any], plan: dict[str, Any], candidate: dict[str, Any], side: str, peak_angle: float) -> list[dict[str, Any]]:
    positions = [tuple(float(value) for value in point) for point in candidate["positions"]]
    indices = [int(value) for value in candidate["indices"]]
    if len(positions) != 42 or len(indices) != 240:
        raise ValueError(f"{side} candidate topology count drift")
    joint = rig._select_joint(spec, plan, side)
    if joint.get("id") != ("front-elbow-L" if side == "left" else "front-elbow-R"):
        raise ValueError(f"{side} joint identity drift")
    if max(abs(float(value)) for value in joint.get("pose_angles_deg", [])) < peak_angle:
        raise ValueError(f"{side} Animation peak exceeds Rigging verification envelope")
    joint_position = deformation._vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = deformation._vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = deformation._sub(child_marker, joint_position)
    axis = deformation._vec3(joint["axis"], "joint axis")
    weights = deformation._weights(positions, joint_position, child_direction, float(joint["influence_radius"]))
    source_areas = rig._source_triangle_areas(positions, indices)

    frames: list[dict[str, Any]] = []
    for sample_index in range(41):
        envelope = raised_cosine(sample_index, 40)
        angle_deg = peak_angle * envelope
        metrics = rig._pose_metrics(positions, indices, source_areas, weights, joint_position, axis, angle_deg)
        if metrics.get("status") != "PASS":
            raise ValueError(f"{side} sample {sample_index} failed Rigging structural gate")
        rounded_positions = [[round(float(value), 12) for value in point] for point in metrics["positions"]]
        frames.append({
            "sample_index": sample_index,
            "time_seconds": round(sample_index / 40.0, 9),
            "envelope": round(envelope, 12),
            "angle_deg": round(angle_deg, 12),
            "positions": rounded_positions,
            "positions_digest": deformation.digest(rounded_positions),
            "collapsed_triangles": int(metrics["collapsed_triangles"]),
            "nonadjacent_self_intersection_pairs": int(metrics["nonadjacent_self_intersection_pairs"]),
            "fixed_weight_vertex_max_drift_m": float(metrics["fixed_weight_vertex_max_drift_m"]),
            "rigid_weight_radius_max_drift_m": float(metrics["rigid_weight_radius_max_drift_m"]),
        })
    if frames[0]["positions"] != frames[-1]["positions"]:
        raise ValueError(f"{side} neutral endpoint closure drift")
    if not math.isclose(float(frames[20]["angle_deg"]), peak_angle, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{side} peak drift")
    return frames


def build(args: argparse.Namespace) -> dict[str, Any]:
    rigging_root = args.rigging_root.resolve()
    rig_donor_root = args.rig_donor_root.resolve()
    if args.rigging_head != RIGGING_HEAD or git_head(rigging_root) != RIGGING_HEAD:
        raise ValueError("bilateral Rigging donor head drift")
    if git_head(rig_donor_root) != RIG_DONOR_HEAD:
        raise ValueError("historical rig-plan donor head drift")

    sys.path.insert(0, str(rigging_root / "src"))
    from axm_animal_design import bilateral_source_successor_rigging_rebind as rig  # type: ignore
    from axm_animal_design import connected_deformation as deformation  # type: ignore
    from axm_animal_design.bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind  # type: ignore

    if rig.GEOMETRY_BILATERAL_HEAD != GEOMETRY_HEAD:
        raise ValueError("Geometry identity drift inside Rigging donor")
    if rig.ORGANIC_BILATERAL_HEAD != ORGANIC_HEAD:
        raise ValueError("Organic identity drift inside Rigging donor")
    if rig.RIG_DONOR_HEAD != RIG_DONOR_HEAD:
        raise ValueError("rig-plan donor identity drift inside Rigging donor")

    spec = load_json(rigging_root / "examples/quadruped_neutral_001.json")
    left_profile = load_json(rigging_root / "examples/quadruped_elbow_source_successor_003.json")
    bilateral_profile = load_json(rigging_root / "examples/quadruped_elbow_bilateral_successor_003.json")
    plan = load_json(rig_donor_root / "examples/quadruped_rig_probe_001.json")
    weighting_profile = load_json(rig_donor_root / "examples/quadruped_weighting_refinement_001.json")
    clip = load_json(args.clip)

    if deformation.digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig-plan digest drift")
    if deformation.digest(clip) != CLIP_DIGEST:
        raise ValueError("Animation clip digest drift")
    if clip.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("Animation must preserve smoothstep-v0; refined weighting is not adopted")
    if clip.get("duration_seconds") != 1.0 or clip.get("sample_rate_hz") != 40:
        raise ValueError("Animation timing drift")
    if clip.get("curve") != "raised-cosine-neutral-to-peak-to-neutral":
        raise ValueError("Animation curve drift")

    tracks = {row.get("joint_id"): row for row in clip.get("tracks", []) if isinstance(row, dict)}
    for joint_id in ("front-elbow-L", "front-elbow-R"):
        if joint_id not in tracks or float(tracks[joint_id].get("peak_angle_deg")) != 18.0:
            raise ValueError(f"{joint_id} authored track drift")

    rigging_receipt = rig.inspect_bilateral_source_successor_rigging_rebind(spec, left_profile, bilateral_profile, plan, weighting_profile)
    for side in ("left", "right"):
        baseline = rigging_receipt[side]["baseline_summary"]
        if baseline.get("gate") != "PASS_BILATERAL_SIDE_DENSE_STRUCTURAL_SWEEP":
            raise ValueError(f"{side} smoothstep Rigging prerequisite is not green")
    mirror = rigging_receipt["bilateral_mirror_evidence"]["smoothstep-v0"]
    if float(mirror["maximum_mirrored_pose_residual_m"]) > 1e-12:
        raise ValueError("Rigging donor does not preserve exact mirrored posed vertices")

    left_candidate, right_candidate, geometry = build_bilateral_source_successor_topology_rebind(spec, left_profile, bilateral_profile)
    left_digest = deformation.digest(left_candidate)
    right_digest = deformation.digest(right_candidate)
    if left_digest != LEFT_SUCCESSOR_DIGEST:
        raise ValueError(f"left successor digest drift: {left_digest}")
    if right_digest != RIGHT_SUCCESSOR_DIGEST:
        raise ValueError(f"right successor digest drift: {right_digest}")

    left_frames = sample_side(rig, deformation, spec, plan, left_candidate, "left", 18.0)
    right_frames = sample_side(rig, deformation, spec, plan, right_candidate, "right", 18.0)
    pairs = rig._vertex_pairs(left_candidate)
    max_mirror_residual = 0.0
    for left_frame, right_frame in zip(left_frames, right_frames):
        if left_frame["sample_index"] != right_frame["sample_index"]:
            raise ValueError("bilateral sample ordering drift")
        for left_index, right_index in pairs:
            lx, ly, lz = left_frame["positions"][left_index]
            rx, ry, rz = right_frame["positions"][right_index]
            max_mirror_residual = max(max_mirror_residual, math.dist((lx, -ly, lz), (rx, ry, rz)))
    if max_mirror_residual > 1e-10:
        raise ValueError(f"Animation bilateral posed-vertex mirror drift: {max_mirror_residual}")

    right_indices = [int(value) for value in right_candidate["indices"]]
    max_collapsed = max(frame["collapsed_triangles"] for frame in right_frames)
    max_intersections = max(frame["nonadjacent_self_intersection_pairs"] for frame in right_frames)
    if max_collapsed != 0 or max_intersections != 0:
        raise ValueError("right Animation samples introduce structural defects")

    args.out.mkdir(parents=True, exist_ok=True)
    frames_doc = {
        "schema": FRAME_SCHEMA,
        "rigging_head": RIGGING_HEAD,
        "geometry_head": GEOMETRY_HEAD,
        "left_candidate_digest": left_digest,
        "right_candidate_digest": right_digest,
        "indices": right_indices,
        "frames": right_frames,
    }
    (args.out / "bilateral_right_motion_frames.json").write_text(json.dumps(frames_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "schema": SCHEMA,
        "gate": GATE,
        "source_identity": {
            "organic_bilateral_head": ORGANIC_HEAD,
            "geometry_bilateral_head": GEOMETRY_HEAD,
            "bilateral_rigging_head": RIGGING_HEAD,
            "rig_plan_donor_head": RIG_DONOR_HEAD,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "left_successor_digest": left_digest,
            "right_successor_digest": right_digest,
            "clip_digest": CLIP_DIGEST,
            "rig_weighting_profile": "smoothstep-v0",
        },
        "motion": {
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "endpoint_inclusive_sample_count": 41,
            "curve": "raised-cosine-neutral-to-peak-to-neutral",
            "front_elbow_peak_deg": 18.0,
            "motion_changed": False,
            "retimed": False,
            "new_keys_authored": False,
            "weighting_changed": False,
        },
        "observed": {
            "maximum_bilateral_mirrored_vertex_residual_m": max_mirror_residual,
            "maximum_right_collapsed_triangles": max_collapsed,
            "maximum_right_nonadjacent_self_intersection_pairs": max_intersections,
            "exact_right_neutral_start_return": right_frames[0]["positions"] == right_frames[40]["positions"],
            "right_peak_sample_index": 20,
            "right_peak_angle_deg": right_frames[20]["angle_deg"],
        },
        "dependency_boundary": {
            "consumed_topology_identity": GEOMETRY_HEAD,
            "newer_geometry_successor_known": NEWER_GEOMETRY_SUCCESSOR_HEAD,
            "newer_geometry_successor_consumed": False,
            "reason": "Geometry PR #13 changes right triangle membership and explicitly requires a fresh Rigging rebind before Animation may consume it.",
        },
        "truth": {
            "proves": [
                "the unchanged bilateral clip can be applied directly to the exact right selected-003 deforming surface proven by Rigging PR #12",
                "all 41 authored right-elbow samples remain structurally green under the exact smoothstep-v0 Rigging implementation",
                "left and right posed vertex fields remain mirrored across Y=0 at all 41 authored Animation sample times",
            ],
            "does_not_prove": [
                "Animation acceptance for Geometry PR #13 or later topology successors",
                "continuous interpolation or C1/C2 motion quality",
                "real-time 40 Hz pacing",
                "exported skeleton or animation-clip transport",
                "runtime controller or state-machine behavior",
                "visual or Art Director acceptance",
                "collision, physics or gameplay acceptance",
                "biological gait or locomotion",
                "target-device performance, CANON or production readiness",
            ],
        },
    }
    (args.out / "bilateral_right_motion_receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    display_frames: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(right_frames[:40]):
        display_frames.append({
            "frame_index": frame_index,
            "sample_index": frame["sample_index"],
            "time_seconds": frame["time_seconds"],
            "surface_digest": frame["positions_digest"],
            "angles_deg": {"front-elbow-R": frame["angle_deg"]},
            "positions": [godot_point(point) for point in frame["positions"]],
            "indices": right_indices,
        })

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "proof_scope": "PINNED_GODOT_BILATERAL_RIGHT_AUTHORED_SAMPLE_APPLICATION_NOT_REALTIME_CONTROLLER",
        "source_identity": receipt["source_identity"],
        "source_playback": {
            "playback_schema": SCHEMA,
            "playback_mode": "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION",
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "display_frame_interval_seconds": 0.025,
            "endpoint_inclusive_source_sample_count": 41,
            "displayed_frame_count_per_cycle": 40,
            "source_gate": GATE,
        },
        "coordinate_bridge": {
            "source": "+X forward, +Y left, +Z up",
            "godot": "+X right, +Y up, +Z forward-axis representation",
            "mapping": "[-source_y, source_z, source_x]",
            "purpose": "proof-host presentation only; no source geometry mutation",
        },
        "topology": {
            "candidate_id": "front-right-connected-chain-elbow-source-successor-003",
            "candidate_digest": right_digest,
            "vertex_count": 42,
            "index_count": 240,
            "triangle_count": 80,
            "geometry_head": GEOMETRY_HEAD,
            "newer_geometry_successor_consumed": False,
        },
        "bounds_godot": bounds(display_frames),
        "frames": display_frames,
        "truth": receipt["truth"],
    }
    args.payload_dir.mkdir(parents=True, exist_ok=True)
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8") + b"\n"
    payload_path = args.payload_dir / "quadruped_animation_payload.json"
    payload_path.write_bytes(payload_bytes)
    summary = {
        "schema": "axm.animal-animation-bilateral-right-godot-payload-summary/v0.1",
        "gate": "PASS_BILATERAL_RIGHT_GODOT_PAYLOAD_BUILD",
        "payload_sha256": sha256(payload_bytes),
        "source_identity": receipt["source_identity"],
        "source_playback": payload["source_playback"],
        "topology": payload["topology"],
        "unique_authored_surface_digests": len({frame["surface_digest"] for frame in display_frames}),
        "bounds_godot": payload["bounds_godot"],
        "dependency_boundary": receipt["dependency_boundary"],
    }
    (args.payload_dir / "quadruped_animation_payload_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"receipt": receipt, "payload_summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rigging-root", type=Path, required=True)
    parser.add_argument("--rig-donor-root", type=Path, required=True)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--payload-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
