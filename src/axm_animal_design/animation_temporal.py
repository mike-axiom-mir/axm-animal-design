"""Temporal continuity evidence for an already-authored animation clip.

This module does not author a second rig, weighting profile, controller, or gameplay
state machine.  It consumes the exact Animation motion sampler and measures whether
one retained discrete loop is temporally well-behaved at its authored sample rate.

A PASS is deliberately narrow: it proves bounded sampled continuity, time-reversal
symmetry for the current raised-cosine pulse, exact neutral closure, and absence of a
large per-sample geometric jump relative to the loop's own peak excursion.  It does
not prove perceptual animation quality, continuous renderer playback, interpolation,
locomotion, gameplay, or runtime-controller acceptance.
"""
from __future__ import annotations

import math
from typing import Any

from .animation_motion import build_animation_frame, inspect_animation_motion

EVIDENCE_SCHEMA = "axm.animal-animation-temporal-continuity/v0.1"
POSITION_TOLERANCE_M = 1e-8
ANGLE_TOLERANCE_DEG = 1e-8
STEP_FRACTION_LIMIT = 0.10


def _flatten_positions(frame: dict[str, Any]) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for primitive in frame["surface"]["primitives"]:
        for point in primitive["positions"]:
            points.append((float(point[0]), float(point[1]), float(point[2])))
    return points


def _topology_signature(frame: dict[str, Any]) -> tuple[tuple[str, int, tuple[int, ...]], ...]:
    return tuple(
        (
            str(primitive["id"]),
            len(primitive["positions"]),
            tuple(int(index) for index in primitive["indices"]),
        )
        for primitive in frame["surface"]["primitives"]
    )


def _max_point_distance(
    a: list[tuple[float, float, float]],
    b: list[tuple[float, float, float]],
) -> float:
    if len(a) != len(b):
        raise ValueError("sampled frame vertex counts differ")
    return max((math.dist(left, right) for left, right in zip(a, b)), default=0.0)


def inspect_temporal_continuity(
    spec: dict[str, Any],
    plan: dict[str, Any],
    clip: dict[str, Any],
) -> dict[str, Any]:
    """Measure one exact sampled loop without changing its source motion."""
    motion = inspect_animation_motion(spec, plan, clip)
    if motion["gate"] != "PASS":
        raise ValueError("temporal continuity evidence requires a passing animation-motion gate")

    sample_count = int(motion["sample_count"])
    sample_rate = int(motion["sample_rate_hz"])
    duration = float(motion["duration_seconds"])
    if sample_count < 3 or sample_count % 2 == 0:
        raise ValueError("v0.1 temporal continuity proof requires an odd sample count with one midpoint")
    if abs((sample_count - 1) / sample_rate - duration) > 1e-12:
        raise ValueError("sample count, sample rate, and duration are inconsistent")

    frames = [
        build_animation_frame(spec, plan, clip, index / sample_rate)
        for index in range(sample_count)
    ]
    signatures = [_topology_signature(frame) for frame in frames]
    topology_stable = all(signature == signatures[0] for signature in signatures)
    if not topology_stable:
        raise ValueError("sampled motion changed surface topology")

    positions = [_flatten_positions(frame) for frame in frames]
    neutral = positions[0]
    midpoint = (sample_count - 1) // 2

    neutral_return_residual = _max_point_distance(positions[0], positions[-1])
    peak_excursion = max(_max_point_distance(neutral, row) for row in positions)
    if peak_excursion <= POSITION_TOLERANCE_M:
        raise ValueError("temporal continuity proof requires non-zero motion")

    steps = [
        _max_point_distance(positions[index - 1], positions[index])
        for index in range(1, sample_count)
    ]
    maximum_step = max(steps, default=0.0)
    maximum_step_fraction = maximum_step / peak_excursion

    mirror_position_residual = 0.0
    mirror_angle_residual = 0.0
    for index in range(sample_count):
        mirror = sample_count - 1 - index
        mirror_position_residual = max(
            mirror_position_residual,
            _max_point_distance(positions[index], positions[mirror]),
        )
        left_angles = frames[index]["angles_deg"]
        right_angles = frames[mirror]["angles_deg"]
        if set(left_angles) != set(right_angles):
            raise ValueError("mirrored sampled frames expose different animation tracks")
        mirror_angle_residual = max(
            mirror_angle_residual,
            max((abs(float(left_angles[key]) - float(right_angles[key])) for key in left_angles), default=0.0),
        )

    mirror_step_residual = max(
        (abs(steps[index] - steps[-1 - index]) for index in range(len(steps))),
        default=0.0,
    )

    track_rows: dict[str, dict[str, Any]] = {}
    joint_ids = sorted(frames[0]["angles_deg"])
    for joint_id in joint_ids:
        values = [float(frame["angles_deg"][joint_id]) for frame in frames]
        rising = all(values[index] <= values[index + 1] + ANGLE_TOLERANCE_DEG for index in range(midpoint))
        falling = all(values[index] >= values[index + 1] - ANGLE_TOLERANCE_DEG for index in range(midpoint, sample_count - 1))
        peak_at_midpoint = abs(values[midpoint] - max(values)) <= ANGLE_TOLERANCE_DEG
        track_rows[joint_id] = {
            "start_angle_deg": values[0],
            "peak_angle_deg": values[midpoint],
            "end_angle_deg": values[-1],
            "monotonic_rise": rising,
            "monotonic_fall": falling,
            "peak_at_midpoint": peak_at_midpoint,
        }

    uniform_sample_times = all(
        abs(float(row["time_seconds"]) - index / sample_rate) <= 1e-12
        for index, row in enumerate(motion["sampled_motion"])
    )
    nonzero_adjacent_motion = all(step > 1e-12 for step in steps)
    tracks_phase_clean = all(
        row["monotonic_rise"] and row["monotonic_fall"] and row["peak_at_midpoint"]
        for row in track_rows.values()
    )

    gate = (
        topology_stable
        and uniform_sample_times
        and motion["metrics"]["exact_neutral_start"]
        and motion["metrics"]["exact_neutral_return"]
        and neutral_return_residual <= POSITION_TOLERANCE_M
        and mirror_position_residual <= POSITION_TOLERANCE_M
        and mirror_angle_residual <= ANGLE_TOLERANCE_DEG
        and mirror_step_residual <= POSITION_TOLERANCE_M
        and nonzero_adjacent_motion
        and tracks_phase_clean
        and maximum_step_fraction <= STEP_FRACTION_LIMIT + 1e-12
    )

    review_indices = [0, 5, 10, 15, 20, 25, 30, 35, 40]
    if sample_count != 41:
        review_indices = sorted({0, midpoint, sample_count - 1, *[round((sample_count - 1) * fraction / 8) for fraction in range(1, 8)]})

    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": motion["source_name"],
        "source_digest": motion["source_digest"],
        "neutral_surface_digest": motion["neutral_surface_digest"],
        "rig_plan_digest": motion["rig_plan_digest"],
        "rig_weighting_profile": motion["rig_weighting_profile"],
        "clip_name": motion["clip_name"],
        "clip_digest": motion["clip_digest"],
        "motion_semantics": motion["motion_semantics"],
        "duration_seconds": duration,
        "sample_rate_hz": sample_rate,
        "sample_count": sample_count,
        "sample_interval_seconds": 1.0 / sample_rate,
        "review_sample_indices": review_indices,
        "review_sample_times_seconds": [round(index / sample_rate, 9) for index in review_indices],
        "track_phase_checks": track_rows,
        "metrics": {
            "topology_stable": topology_stable,
            "uniform_sample_times": uniform_sample_times,
            "exact_neutral_start": motion["metrics"]["exact_neutral_start"],
            "exact_neutral_return": motion["metrics"]["exact_neutral_return"],
            "neutral_return_position_residual_m": neutral_return_residual,
            "maximum_time_mirror_position_residual_m": mirror_position_residual,
            "maximum_time_mirror_angle_residual_deg": mirror_angle_residual,
            "maximum_time_mirror_step_residual_m": mirror_step_residual,
            "peak_vertex_excursion_from_neutral_m": peak_excursion,
            "maximum_adjacent_vertex_step_m": maximum_step,
            "maximum_adjacent_step_fraction_of_peak_excursion": maximum_step_fraction,
            "step_fraction_limit": STEP_FRACTION_LIMIT,
            "nonzero_adjacent_motion": nonzero_adjacent_motion,
            "tracks_phase_clean": tracks_phase_clean,
        },
        "adjacent_max_vertex_steps_m": steps,
        "gate": "PASS_LOOP_TEMPORAL_CONTINUITY" if gate else "FAIL_LOOP_TEMPORAL_CONTINUITY",
        "truth": {
            "proves_if_green": "For this exact source, repaired rig, smoothstep-v0 weighting baseline and authored 40 Hz clip sampling, the retained discrete loop has stable topology, uniform sample times, bounded per-sample geometric steps, mirrored rise/fall motion, and exact neutral closure within the stated tolerances.",
            "does_not_prove": "Perceptual animation quality, biological gait, locomotion, contact, balance, interpolation between samples, shaded deformation quality, self-intersection freedom, exported clip transport, target-engine playback, runtime-controller/state-machine integration, gameplay acceptance, performance, CANON, production readiness, or mastery.",
        },
    }
