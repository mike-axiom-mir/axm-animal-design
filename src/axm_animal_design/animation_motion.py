"""Bounded continuous motion evidence over an already-declared animal rig.

Animation owns timing and sampled motion here. Rigging remains the authority for joint
axes, influence radii, downstream propagation and deformation probes. The animation
layer deliberately calls that exact rig machinery instead of copying a second skinning
implementation. This first clip pins the existing smoothstep-v0 weighting baseline;
the separate Rigging weighting refinement remains outside Animation acceptance.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any

from .organic_form import EVIDENCE_SCHEMA as FORM_EVIDENCE_SCHEMA
from .organic_form import build_form_study
from . import rig_deformation as rig

CLIP_SCHEMA = "axm.animal-animation-motion-clip/v0.1"
EVIDENCE_SCHEMA = "axm.animal-animation-motion-evidence/v0.1"
FRAME_SCHEMA = "axm.animal-animation-motion-frame/v0.1"
WEIGHTING_PROFILE = "smoothstep-v0"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _validate_clip(spec: dict[str, Any], plan: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(clip, dict) or clip.get("schema") != CLIP_SCHEMA:
        raise ValueError(f"clip must use {CLIP_SCHEMA}")
    if clip.get("source_name") != spec.get("name"):
        raise ValueError("clip source_name must match form study name")
    if clip.get("rig_plan_name") != plan.get("name"):
        raise ValueError("clip rig_plan_name must match rig plan name")
    if clip.get("rig_weighting_profile") != WEIGHTING_PROFILE:
        raise ValueError(f"clip rig_weighting_profile must be {WEIGHTING_PROFILE}")
    if clip.get("curve") != "raised-cosine-neutral-to-peak-to-neutral":
        raise ValueError("unsupported animation curve")
    if clip.get("motion_semantics") != "STYLIZED_ARTICULATION_PULSE_NOT_GAIT_OR_LOCOMOTION":
        raise ValueError("motion_semantics must preserve the bounded non-locomotion truth label")

    duration = _number(clip.get("duration_seconds"), "duration_seconds")
    if not 0.2 <= duration <= 5.0:
        raise ValueError("duration_seconds must be within 0.2..5.0")
    sample_rate = clip.get("sample_rate_hz")
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or not 10 <= sample_rate <= 120:
        raise ValueError("sample_rate_hz must be an integer within 10..120")
    exact_steps = duration * sample_rate
    if abs(exact_steps - round(exact_steps)) > 1e-12:
        raise ValueError("duration_seconds * sample_rate_hz must produce an exact whole sample interval count")

    rig_joints = {row.get("id"): row for row in plan.get("joints", [])}
    tracks = clip.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 16:
        raise ValueError("tracks must contain 1..16 entries")
    seen = set()
    checked_tracks = []
    for row in tracks:
        joint_id = row.get("joint_id")
        if not isinstance(joint_id, str) or not joint_id or joint_id in seen:
            raise ValueError("track joint_id values must be unique non-empty text")
        if joint_id not in rig_joints:
            raise ValueError(f"unknown rig joint: {joint_id}")
        seen.add(joint_id)
        peak = _number(row.get("peak_angle_deg"), f"{joint_id}.peak_angle_deg")
        probed = [abs(float(value)) for value in rig_joints[joint_id].get("pose_angles_deg", [])]
        if not probed:
            raise ValueError(f"{joint_id} has no rig probe angle evidence")
        if abs(peak) > max(probed) + 1e-12:
            raise ValueError(f"{joint_id}.peak_angle_deg exceeds rig-probed angle envelope")
        checked_tracks.append({"joint_id": joint_id, "peak_angle_deg": peak})

    key_times = clip.get("retained_keyframe_times_seconds")
    if not isinstance(key_times, list) or not key_times:
        raise ValueError("retained_keyframe_times_seconds must be a non-empty list")
    checked_key_times = []
    for value in key_times:
        time_value = _number(value, "retained keyframe time")
        if time_value < -1e-12 or time_value > duration + 1e-12:
            raise ValueError("retained keyframe time lies outside clip duration")
        index = time_value * sample_rate
        if abs(index - round(index)) > 1e-12:
            raise ValueError("retained keyframe times must land on sampled frames")
        checked_key_times.append(time_value)
    if checked_key_times != sorted(set(checked_key_times)):
        raise ValueError("retained keyframe times must be unique and sorted")
    if checked_key_times[0] != 0.0 or abs(checked_key_times[-1] - duration) > 1e-12:
        raise ValueError("retained keyframes must include exact clip start and end")

    driven_regions = set()
    for joint_id in sorted(seen):
        joint = rig_joints[joint_id]
        for region_id in [joint["child_region"], *joint.get("downstream_regions", [])]:
            if region_id in driven_regions:
                raise ValueError("animation tracks overlap driven rig regions")
            driven_regions.add(region_id)

    return {
        "duration_seconds": duration,
        "sample_rate_hz": sample_rate,
        "sample_count": int(round(exact_steps)) + 1,
        "tracks": checked_tracks,
        "retained_keyframe_times_seconds": checked_key_times,
    }


def _raised_cosine(time_seconds: float, duration_seconds: float) -> float:
    phase = time_seconds / duration_seconds
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)


def _angles_for_time(validated_clip: dict[str, Any], time_seconds: float) -> dict[str, float]:
    envelope = _raised_cosine(time_seconds, validated_clip["duration_seconds"])
    return {
        row["joint_id"]: row["peak_angle_deg"] * envelope
        for row in validated_clip["tracks"]
    }


def _pose_surface(spec: dict[str, Any], plan: dict[str, Any], angle_by_joint: dict[str, float]) -> dict[str, Any]:
    form = build_form_study(spec)
    surface = copy.deepcopy(form["surface"])
    primitives = {row["id"]: row for row in surface["primitives"]}
    joints = rig._validate_plan(spec, plan, primitives)
    landmarks = {name: rig._vec3(value, f"landmark {name}") for name, value in spec["landmarks"].items()}

    for joint in joints:
        angle = float(angle_by_joint.get(joint["id"], 0.0))
        if abs(angle) <= 1e-15:
            continue
        joint_position = landmarks[joint["landmark"]]
        child_marker = landmarks[joint["child_landmark"]]
        child_direction = rig._sub(child_marker, joint_position)
        primitive = primitives[joint["child_region"]]
        before = [tuple(point) for point in primitive["positions"]]
        weights = rig._weights(before, joint_position, child_direction, joint["influence_radius"])
        primitive["positions"] = [
            rig._add(
                point,
                rig._mul(
                    rig._sub(rig._rotate_about_axis(point, joint_position, joint["axis"], angle), point),
                    child_weight,
                ),
            )
            for point, (_, child_weight) in zip(before, weights)
        ]
        for region_id in joint["downstream_regions"]:
            descendant = primitives[region_id]
            descendant["positions"] = [
                rig._rotate_about_axis(tuple(point), joint_position, joint["axis"], angle)
                for point in descendant["positions"]
            ]
    return surface


def build_animation_frame(spec: dict[str, Any], plan: dict[str, Any], clip: dict[str, Any], time_seconds: float) -> dict[str, Any]:
    """Build one exact posed surface at an authored sample time."""
    validated = _validate_clip(spec, plan, clip)
    time_value = _number(time_seconds, "time_seconds")
    if time_value < -1e-12 or time_value > validated["duration_seconds"] + 1e-12:
        raise ValueError("time_seconds lies outside clip duration")
    sample_index = time_value * validated["sample_rate_hz"]
    if abs(sample_index - round(sample_index)) > 1e-12:
        raise ValueError("time_seconds must land on a sampled frame")
    angles = _angles_for_time(validated, time_value)
    surface = _pose_surface(spec, plan, angles)
    form = build_form_study(spec)
    return {
        "schema": FRAME_SCHEMA,
        "source_name": spec["name"],
        "source_digest": form["source_digest"],
        "neutral_surface_digest": form["surface_digest"],
        "rig_plan_digest": _digest(plan),
        "rig_weighting_profile": WEIGHTING_PROFILE,
        "clip_digest": _digest(clip),
        "time_seconds": round(time_value, 9),
        "sample_index": int(round(sample_index)),
        "angles_deg": {key: round(value, 9) for key, value in sorted(angles.items())},
        "surface": surface,
        "surface_digest": _digest(surface),
    }


def inspect_animation_motion(spec: dict[str, Any], plan: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
    """Sample one bounded loop through the exact rig and retain structural motion evidence."""
    validated = _validate_clip(spec, plan, clip)
    form = build_form_study(spec)
    baseline_rig = rig.inspect_rig_deformation(spec, plan)
    if baseline_rig["gate"] != "PASS":
        raise ValueError("animation requires a structurally passing rig probe")

    sample_rows = []
    path_points = {row["joint_id"]: [] for row in validated["tracks"]}
    worst_min_area_ratio = math.inf
    worst_max_edge_ratio = 0.0
    max_chain_gap_drift = 0.0
    all_pass = True

    for sample_index in range(validated["sample_count"]):
        time_seconds = sample_index / validated["sample_rate_hz"]
        angles = _angles_for_time(validated, time_seconds)
        sample_plan = copy.deepcopy(plan)
        for joint in sample_plan["joints"]:
            joint["pose_angles_deg"] = [angles.get(joint["id"], 0.0)]
        deformation = rig.inspect_rig_deformation(spec, sample_plan)
        frame = build_animation_frame(spec, plan, clip, time_seconds)
        joint_rows = {}
        for joint in deformation["joints"]:
            pose = joint["poses"][0]
            joint_rows[joint["id"]] = {
                "angle_deg": round(pose["angle_deg"], 9),
                "distal_marker_position": pose["distal_marker_position"],
                "minimum_triangle_area_ratio": pose["minimum_triangle_area_ratio"],
                "minimum_edge_length_ratio": pose["minimum_edge_length_ratio"],
                "maximum_edge_length_ratio": pose["maximum_edge_length_ratio"],
                "collapsed_triangles": pose["collapsed_triangles"],
                "chain_continuity": pose["chain_continuity"],
                "status": pose["status"],
            }
            worst_min_area_ratio = min(worst_min_area_ratio, pose["minimum_triangle_area_ratio"])
            worst_max_edge_ratio = max(worst_max_edge_ratio, pose["maximum_edge_length_ratio"])
            for continuity in pose["chain_continuity"]:
                max_chain_gap_drift = max(max_chain_gap_drift, continuity["absolute_gap_drift"])
            if joint["id"] in path_points:
                path_points[joint["id"]].append(tuple(pose["distal_marker_position"]))
        sample_pass = deformation["gate"] == "PASS" and all(row["status"] == "PASS" for row in joint_rows.values())
        all_pass &= sample_pass
        sample_rows.append({
            "sample_index": sample_index,
            "time_seconds": round(time_seconds, 9),
            "envelope": round(_raised_cosine(time_seconds, validated["duration_seconds"]), 9),
            "angles_deg": {key: round(value, 9) for key, value in sorted(angles.items())},
            "surface_digest": frame["surface_digest"],
            "joints": joint_rows,
            "status": "PASS" if sample_pass else "FAIL",
        })

    path_lengths = {
        joint_id: round(sum(math.dist(points[index - 1], points[index]) for index in range(1, len(points))), 9)
        for joint_id, points in path_points.items()
    }
    first_frame = build_animation_frame(spec, plan, clip, 0.0)
    final_frame = build_animation_frame(spec, plan, clip, validated["duration_seconds"])
    exact_neutral_start = first_frame["surface_digest"] == form["surface_digest"]
    exact_neutral_return = final_frame["surface_digest"] == form["surface_digest"]
    distinct_surface_count = len({row["surface_digest"] for row in sample_rows})

    track_by_id = {row["joint_id"]: row for row in validated["tracks"]}
    bilateral_angle_match = True
    for left, right in (("front-elbow-L", "front-elbow-R"), ("hind-knee-L", "hind-knee-R")):
        if left in track_by_id or right in track_by_id:
            bilateral_angle_match &= left in track_by_id and right in track_by_id
            if left in track_by_id and right in track_by_id:
                bilateral_angle_match &= track_by_id[left]["peak_angle_deg"] == track_by_id[right]["peak_angle_deg"]

    moved_paths = all(length > 0.01 for length in path_lengths.values())
    gate = (
        all_pass
        and exact_neutral_start
        and exact_neutral_return
        and distinct_surface_count > 2
        and bilateral_angle_match
        and moved_paths
        and max_chain_gap_drift <= rig.CHAIN_GAP_TOLERANCE
    )
    keyframe_indices = {
        int(round(value * validated["sample_rate_hz"]))
        for value in validated["retained_keyframe_times_seconds"]
    }
    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": spec["name"],
        "source_digest": form["source_digest"],
        "neutral_surface_digest": form["surface_digest"],
        "rig_plan_digest": _digest(plan),
        "rig_weighting_profile": WEIGHTING_PROFILE,
        "clip_name": clip["name"],
        "clip_digest": _digest(clip),
        "motion_semantics": clip["motion_semantics"],
        "duration_seconds": validated["duration_seconds"],
        "sample_rate_hz": validated["sample_rate_hz"],
        "sample_count": validated["sample_count"],
        "retained_keyframe_times_seconds": validated["retained_keyframe_times_seconds"],
        "track_count": len(validated["tracks"]),
        "tracks": validated["tracks"],
        "sampled_motion": sample_rows,
        "retained_keyframes": [row for row in sample_rows if row["sample_index"] in keyframe_indices],
        "metrics": {
            "exact_neutral_start": exact_neutral_start,
            "exact_neutral_return": exact_neutral_return,
            "distinct_surface_count": distinct_surface_count,
            "bilateral_peak_angle_match": bilateral_angle_match,
            "distal_marker_path_lengths_m": path_lengths,
            "worst_minimum_triangle_area_ratio": round(worst_min_area_ratio, 9),
            "worst_maximum_edge_length_ratio": round(worst_max_edge_ratio, 9),
            "maximum_chain_gap_drift_m": round(max_chain_gap_drift, 12),
            "chain_gap_tolerance_m": rig.CHAIN_GAP_TOLERANCE,
        },
        "gate": "PASS" if gate else "FAIL",
        "truth": {
            "proves": "This exact form and repaired rig were continuously sampled through this exact deterministic loop using the existing smoothstep-v0 weighting baseline. The sampled child-region deformation and declared downstream paw propagation remain structurally passing, motion is non-zero, and the complete posed surface returns exactly to the neutral surface identity at loop end.",
            "does_not_prove": "Biological gait, locomotion, foot planting, root motion, balance, perceptual animation quality, acceptance of the separate ease-out weighting candidate, production skinning, self-intersection freedom, volume preservation, target-engine animation playback, runtime-controller integration, collision, gameplay acceptance, performance, or mastery.",
        },
    }


def frame_as_form_evidence(frame: dict[str, Any], name: str) -> dict[str, Any]:
    """Wrap a motion frame for the existing renderer-neutral wire projector only."""
    if frame.get("schema") != FRAME_SCHEMA:
        raise ValueError("animation frame schema mismatch")
    return {"schema": FORM_EVIDENCE_SCHEMA, "name": name, "surface": frame["surface"]}
