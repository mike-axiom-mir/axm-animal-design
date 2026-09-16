#!/usr/bin/env python3
"""Bind the unchanged Animal articulation clip to Rigging-owned deformed tangent frames.

This Animation observer consumes the exact Rigging PR #22 tangent-frame donor, preserves
Animation's existing smoothstep-v0 clip, samples both selected-003 front elbows at all
41 authored times, and emits the exact posed render-domain position/normal/UV/tangent
attributes for target-host readback in pinned Godot.

It does not author a new tangent policy, normal policy, UV layout, deformation solver,
rig, weighting rule, animation timing, material, controller, or gameplay behavior.
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

RIGGING_TANGENT_HEAD = "63c65d57fda0595217f86d971ff8c67f256188be"
GEOMETRY_UV_TANGENT_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
PARENT_RIGGING_NORMAL_HEAD = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
GEOMETRY_UV_TANGENT_MODULE_BLOB = "ba0b4e620f132413606177358e47bd32ae4d4965"
DEFORMED_NORMAL_MODULE_BLOB = "b8df083310727dcd05e7476b2158a081a5c25c8f"
RIGGING_SOURCE_MODULE_BLOB = "f0cdcd7bf2452e73070efc872f53274a5ae3bcba"
SCHEMA = "axm.animal-animation-bilateral-deformed-tangent-motion/v0.1"
PAYLOAD_SCHEMA = "axm.animal-animation-godot-tangent-motion-payload/v0.1"
GATE = "PASS_BILATERAL_DEFORMED_TANGENT_41_SAMPLE_MOTION_BIND"
PAYLOAD_GATE = "PASS_BILATERAL_DEFORMED_TANGENT_GODOT_PAYLOAD_BUILD"
TOLERANCE = 1e-9


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def raised_cosine(sample_index: int, interval_count: int) -> float:
    if sample_index in (0, interval_count):
        return 0.0
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * sample_index / interval_count)


def distance(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def reflect_y(value):
    return [float(value[0]), -float(value[1]), float(value[2])]


def dot(a, b) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def godot_vec3(value):
    # Source XYZ -> Godot XYZ. This basis has determinant -1, so tangent handedness flips.
    return [-float(value[1]), float(value[2]), float(value[0])]


def godot_tangent(value):
    xyz = godot_vec3(value[:3])
    return [xyz[0], xyz[1], xyz[2], -float(value[3])]


def build_side_frames(
    tangent: Any,
    rig: Any,
    deformation: Any,
    candidate: dict[str, Any],
    static_basis: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    side: str,
    peak_angle: float,
) -> list[dict[str, Any]]:
    positions = [tuple(float(value) for value in point) for point in candidate["positions"]]
    indices = [int(value) for value in candidate["indices"]]
    joint = rig._select_joint(spec, plan, side)
    expected_joint = "front-elbow-L" if side == "left" else "front-elbow-R"
    if joint.get("id") != expected_joint:
        raise ValueError(f"{side} joint identity drift")
    if max(abs(float(value)) for value in joint.get("pose_angles_deg", [])) < peak_angle:
        raise ValueError(f"{side} Animation peak exceeds Rigging verification envelope")

    joint_position = deformation._vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = deformation._vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = deformation._sub(child_marker, joint_position)
    axis = deformation._vec3(joint["axis"], "joint axis")
    weights = deformation._weights(
        positions, joint_position, child_direction, float(joint["influence_radius"])
    )
    source_areas = rig._source_triangle_areas(positions, indices)

    frames: list[dict[str, Any]] = []
    static_tangents = static_basis["render_tangents"]
    static_uvs = static_basis["render_uvs"]
    for sample_index in range(41):
        envelope = raised_cosine(sample_index, 40)
        angle_deg = peak_angle * envelope
        metrics = rig._pose_metrics(
            positions, indices, source_areas, weights, joint_position, axis, angle_deg
        )
        if metrics.get("status") != "PASS":
            raise ValueError(f"{side} sample {sample_index} failed Rigging structural gate")
        tangent_frame = tangent._derive_posed_tangent_frame(
            candidate, static_basis, metrics["positions"]
        )
        if tangent_frame["render_indices"] != static_basis["render_indices"]:
            raise ValueError(f"{side} render-domain index drift at sample {sample_index}")
        maximum_uv_residual = max(
            (distance(a, b) for a, b in zip(tangent_frame["render_uvs"], static_uvs)),
            default=0.0,
        )
        handedness_drift = sum(
            1
            for current, static in zip(tangent_frame["render_tangents"], static_tangents)
            if float(current[3]) != float(static[3])
        )
        if maximum_uv_residual > TOLERANCE or handedness_drift:
            raise ValueError(f"{side} tangent identity drift at sample {sample_index}")
        if float(tangent_frame["maximum_tangent_unit_length_error"]) > TOLERANCE:
            raise ValueError(f"{side} tangent unit-length drift at sample {sample_index}")
        if float(tangent_frame["maximum_tangent_normal_dot_abs"]) > TOLERANCE:
            raise ValueError(f"{side} tangent/normal orthogonality drift at sample {sample_index}")
        frames.append(
            {
                "sample_index": sample_index,
                "time_seconds": round(sample_index / 40.0, 9),
                "angle_deg": round(angle_deg, 12),
                "render_positions": [[float(v) for v in row] for row in tangent_frame["render_positions"]],
                "render_normals": [[float(v) for v in row] for row in tangent_frame["render_normals"]],
                "render_uvs": [[float(v) for v in row] for row in tangent_frame["render_uvs"]],
                "render_tangents": [[float(v) for v in row] for row in tangent_frame["render_tangents"]],
                "semantic_vertex_keys": list(tangent_frame["semantic_vertex_keys"]),
                "maximum_tangent_unit_length_error": float(tangent_frame["maximum_tangent_unit_length_error"]),
                "maximum_tangent_normal_dot_abs": float(tangent_frame["maximum_tangent_normal_dot_abs"]),
                "maximum_uv_residual": maximum_uv_residual,
                "handedness_drift_count": handedness_drift,
            }
        )
    if frames[0]["render_positions"] != frames[-1]["render_positions"]:
        raise ValueError(f"{side} position endpoint closure drift")
    if frames[0]["render_normals"] != frames[-1]["render_normals"]:
        raise ValueError(f"{side} normal endpoint closure drift")
    if frames[0]["render_tangents"] != frames[-1]["render_tangents"]:
        raise ValueError(f"{side} tangent endpoint closure drift")
    if not math.isclose(float(frames[20]["angle_deg"]), peak_angle, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{side} peak angle drift")
    return frames


def bilateral_metrics(left_frames, right_frames) -> dict[str, Any]:
    maximum_position_residual = 0.0
    maximum_normal_residual = 0.0
    maximum_uv_residual = 0.0
    maximum_tangent_xyz_residual = 0.0
    handedness_mismatch_count = 0
    minimum_adjacent_tangent_dot = 1.0

    previous = {"left": None, "right": None}
    for left, right in zip(left_frames, right_frames):
        left_keys = list(left["semantic_vertex_keys"])
        right_keys = list(right["semantic_vertex_keys"])
        right_by_key = {key: index for index, key in enumerate(right_keys)}
        if set(left_keys) != set(right_keys) or len(right_by_key) != len(right_keys):
            raise ValueError("bilateral semantic render-vertex identity drift")
        for left_index, key in enumerate(left_keys):
            right_index = right_by_key[key]
            maximum_position_residual = max(
                maximum_position_residual,
                distance(reflect_y(left["render_positions"][left_index]), right["render_positions"][right_index]),
            )
            maximum_normal_residual = max(
                maximum_normal_residual,
                distance(reflect_y(left["render_normals"][left_index]), right["render_normals"][right_index]),
            )
            maximum_uv_residual = max(
                maximum_uv_residual,
                distance(left["render_uvs"][left_index], right["render_uvs"][right_index]),
            )
            maximum_tangent_xyz_residual = max(
                maximum_tangent_xyz_residual,
                distance(reflect_y(left["render_tangents"][left_index][:3]), right["render_tangents"][right_index][:3]),
            )
            if float(right["render_tangents"][right_index][3]) != -float(left["render_tangents"][left_index][3]):
                handedness_mismatch_count += 1
        for side, frame in (("left", left), ("right", right)):
            if previous[side] is not None:
                for prior_tangent, current_tangent in zip(
                    previous[side]["render_tangents"], frame["render_tangents"]
                ):
                    minimum_adjacent_tangent_dot = min(
                        minimum_adjacent_tangent_dot,
                        dot(prior_tangent[:3], current_tangent[:3]),
                    )
            previous[side] = frame

    if maximum_position_residual > TOLERANCE:
        raise ValueError(f"bilateral posed position residual drift: {maximum_position_residual}")
    if maximum_normal_residual > TOLERANCE:
        raise ValueError(f"bilateral posed normal residual drift: {maximum_normal_residual}")
    if maximum_uv_residual > TOLERANCE:
        raise ValueError(f"bilateral UV residual drift: {maximum_uv_residual}")
    if maximum_tangent_xyz_residual > TOLERANCE or handedness_mismatch_count:
        raise ValueError("bilateral posed tangent-frame mirror drift")
    if minimum_adjacent_tangent_dot <= 0.0:
        raise ValueError("adjacent authored samples contain a tangent direction flip")

    return {
        "maximum_mirrored_position_residual_m": maximum_position_residual,
        "maximum_mirrored_normal_residual": maximum_normal_residual,
        "maximum_uv_residual": maximum_uv_residual,
        "maximum_mirrored_tangent_xyz_residual": maximum_tangent_xyz_residual,
        "tangent_handedness_mismatch_count": handedness_mismatch_count,
        "minimum_adjacent_authored_sample_tangent_dot": minimum_adjacent_tangent_dot,
    }


def payload_side(side: str, static_basis: dict[str, Any], frames: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "side": side,
        "render_vertex_count": int(static_basis["render_vertex_count"]),
        "render_indices": [int(value) for value in static_basis["render_indices"]],
        "frames": [
            {
                "sample_index": int(frame["sample_index"]),
                "time_seconds": float(frame["time_seconds"]),
                "angle_deg": float(frame["angle_deg"]),
                "positions": [godot_vec3(row) for row in frame["render_positions"]],
                "normals": [godot_vec3(row) for row in frame["render_normals"]],
                "uvs": [[float(v) for v in row] for row in frame["render_uvs"]],
                "tangents": [godot_tangent(row) for row in frame["render_tangents"]],
            }
            for frame in frames
        ],
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    rigging_root = args.rigging_root.resolve()
    rig_donor_root = args.rig_donor_root.resolve()
    if args.rigging_head != RIGGING_TANGENT_HEAD or git_head(rigging_root) != RIGGING_TANGENT_HEAD:
        raise ValueError("deformed-tangent Rigging donor head drift")
    if git_head(rig_donor_root) != RIG_DONOR_HEAD:
        raise ValueError("historical rig-plan donor head drift")

    sys.path.insert(0, str(rigging_root / "src"))
    from axm_animal_design import bilateral_deformed_tangent_frames as tangent  # type: ignore
    from axm_animal_design import bilateral_source_successor_rigging_rebind as rig  # type: ignore
    from axm_animal_design import connected_deformation as deformation  # type: ignore

    if tangent.GEOMETRY_UV_TANGENT_HEAD != GEOMETRY_UV_TANGENT_HEAD:
        raise ValueError("Geometry UV/tangent head drift inside Rigging donor")
    if tangent.PARENT_RIGGING_HEAD != PARENT_RIGGING_NORMAL_HEAD:
        raise ValueError("parent deformed-normal Rigging head drift")
    if tangent.GEOMETRY_UV_TANGENT_MODULE_BLOB != GEOMETRY_UV_TANGENT_MODULE_BLOB:
        raise ValueError("Geometry UV/tangent module blob drift")
    if tangent.DEFORMED_NORMAL_MODULE_BLOB != DEFORMED_NORMAL_MODULE_BLOB:
        raise ValueError("deformed-normal module blob drift")
    if tangent.RIGGING_SOURCE_MODULE_BLOB != RIGGING_SOURCE_MODULE_BLOB:
        raise ValueError("Rigging source module blob drift")

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
        raise ValueError("Animation must preserve smoothstep-v0")
    if clip.get("duration_seconds") != 1.0 or clip.get("sample_rate_hz") != 40:
        raise ValueError("Animation timing drift")
    if clip.get("curve") != "raised-cosine-neutral-to-peak-to-neutral":
        raise ValueError("Animation curve drift")

    tracks = {
        row.get("joint_id"): row
        for row in clip.get("tracks", [])
        if isinstance(row, dict)
    }
    for joint_id in ("front-elbow-L", "front-elbow-R"):
        if joint_id not in tracks or float(tracks[joint_id].get("peak_angle_deg")) != 18.0:
            raise ValueError(f"{joint_id} authored track drift")

    prerequisite = tangent.inspect_bilateral_deformed_tangent_frames(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if prerequisite.get("state") != tangent.PASS_STATE:
        raise ValueError("Rigging deformed tangent-frame prerequisite is not PASS")
    if prerequisite["truth_boundary"].get("animation_accepted") is not False:
        raise ValueError("Rigging donor truth boundary drifted")

    left_candidate, historical_right, _topology = tangent.build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _mirror = tangent.derive_exact_mirror_surface_candidate(
        left_candidate, historical_right
    )
    static_left = tangent.derive_uv_tangent_basis(left_candidate, side="left")
    static_right = tangent.derive_uv_tangent_basis(right_candidate, side="right")

    left_frames = build_side_frames(
        tangent, rig, deformation, left_candidate, static_left, spec, plan, "left", 18.0
    )
    right_frames = build_side_frames(
        tangent, rig, deformation, right_candidate, static_right, spec, plan, "right", 18.0
    )
    bilateral = bilateral_metrics(left_frames, right_frames)

    maximum_tangent_unit_error = max(
        frame["maximum_tangent_unit_length_error"]
        for frame in left_frames + right_frames
    )
    maximum_tangent_normal_dot_abs = max(
        frame["maximum_tangent_normal_dot_abs"]
        for frame in left_frames + right_frames
    )
    maximum_uv_residual = max(
        frame["maximum_uv_residual"] for frame in left_frames + right_frames
    )
    handedness_drift_count = sum(
        frame["handedness_drift_count"] for frame in left_frames + right_frames
    )

    receipt = {
        "schema": SCHEMA,
        "gate": GATE,
        "source_identity": {
            "rigging_deformed_tangent_head": RIGGING_TANGENT_HEAD,
            "geometry_uv_tangent_head": GEOMETRY_UV_TANGENT_HEAD,
            "parent_deformed_normal_rigging_head": PARENT_RIGGING_NORMAL_HEAD,
            "rig_plan_donor_head": RIG_DONOR_HEAD,
            "rig_plan_digest": RIG_PLAN_DIGEST,
            "clip_digest": CLIP_DIGEST,
            "rig_weighting_profile": "smoothstep-v0",
            "geometry_uv_tangent_module_blob": GEOMETRY_UV_TANGENT_MODULE_BLOB,
            "deformed_normal_module_blob": DEFORMED_NORMAL_MODULE_BLOB,
            "rigging_source_module_blob": RIGGING_SOURCE_MODULE_BLOB,
            "left_static_basis_digest": deformation.digest(static_left),
            "right_static_basis_digest": deformation.digest(static_right),
        },
        "motion": {
            "truth_label": clip.get("truth_label"),
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "endpoint_inclusive_sample_count": 41,
            "front_elbow_peak_angle_deg": 18.0,
            "curve": clip.get("curve"),
            "retimed": False,
            "new_keys_authored": False,
            "weighting_changed": False,
        },
        "observed": {
            "render_vertices_per_side_per_sample": int(static_left["render_vertex_count"]),
            "render_triangles_per_side": len(static_left["render_indices"]) // 3,
            "total_authored_pose_frames_observed": len(left_frames) + len(right_frames),
            "maximum_tangent_unit_length_error": maximum_tangent_unit_error,
            "maximum_tangent_normal_dot_abs": maximum_tangent_normal_dot_abs,
            "maximum_uv_residual": maximum_uv_residual,
            "handedness_drift_count": handedness_drift_count,
            "bilateral": bilateral,
            "exact_neutral_position_normal_tangent_roundtrip": True,
        },
        "truth_boundary": {
            "rigging_tangent_policy_modified_by_animation": False,
            "normal_or_uv_policy_modified_by_animation": False,
            "deformation_solver_copied_by_animation": False,
            "exact_rigging_donor_consumed": True,
            "exact_41_sample_animation_envelope_observed": True,
            "target_host_attribute_transport_established": False,
            "shaded_deformed_visual_quality_accepted": False,
            "tangent_space_normal_map_rendered": False,
            "continuous_interpolation_established": False,
            "runtime_controller_or_state_machine_accepted": False,
            "gameplay_accepted": False,
            "canon_claimed": False,
        },
    }

    payload = {
        "schema": PAYLOAD_SCHEMA,
        "gate": PAYLOAD_GATE,
        "source_gate": GATE,
        "source_identity": receipt["source_identity"],
        "coordinate_bridge": {
            "source_to_godot_xyz": "[-source_y, source_z, source_x]",
            "basis_determinant": -1,
            "tangent_handedness_flipped": True,
        },
        "playback": {
            "mode": "DETERMINISTIC_AUTHORED_SAMPLE_ATTRIBUTE_APPLICATION_NOT_REALTIME_PACING",
            "endpoint_inclusive_sample_count": 41,
            "sides": ["left", "right"],
        },
        "left": payload_side("left", static_left, left_frames),
        "right": payload_side("right", static_right, right_frames),
        "truth_boundary": receipt["truth_boundary"],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    args.payload_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out / "bilateral_deformed_tangent_motion_receipt.json", receipt)
    write_json(args.out / "bilateral_deformed_tangent_motion_frames.json", {
        "schema": "axm.animal-animation-bilateral-deformed-tangent-motion-frames/v0.1",
        "left": left_frames,
        "right": right_frames,
    })
    payload_path = args.payload_dir / "tangent_motion_payload.json"
    write_json(payload_path, payload)
    write_json(args.payload_dir / "tangent_motion_payload_summary.json", {
        "gate": PAYLOAD_GATE,
        "payload_sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
        "rigging_deformed_tangent_head": RIGGING_TANGENT_HEAD,
        "clip_digest": CLIP_DIGEST,
        "samples_per_side": 41,
        "render_vertices_per_side": int(static_left["render_vertex_count"]),
        "render_triangles_per_side": len(static_left["render_indices"]) // 3,
    })
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rigging-root", type=Path, required=True)
    parser.add_argument("--rig-donor-root", type=Path, required=True)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--payload-dir", type=Path, required=True)
    args = parser.parse_args()
    receipt = build(args)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
