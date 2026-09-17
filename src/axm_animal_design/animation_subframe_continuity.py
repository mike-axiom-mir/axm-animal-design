"""Dense subframe continuity witness for one already-authored Animation clip.

This module does not author a new clip, rig, weighting profile, controller, renderer,
or gameplay state machine. It evaluates the exact current Animation source curve through
the existing rig deformation implementation at deterministic subframes between the 41
authored samples.

A green result is deliberately narrow: it proves that this exact analytic source curve
and existing deformation path remain symmetric, loop-closed and free of a hidden
between-key discontinuity at the retained subframe density. It does not prove target-
engine interpolation, wall-clock pacing, production transport, perceptual quality, or
runtime/gameplay acceptance.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from .animation_motion import (
    _angles_for_time,
    _pose_surface,
    _validate_clip,
    build_animation_frame,
    inspect_animation_motion,
)

EVIDENCE_SCHEMA = "axm.animal-animation-subframe-continuity/v0.1"
DEFAULT_SUBFRAMES_PER_AUTHORED_INTERVAL = 8
POSITION_TOLERANCE_M = 1e-9
ANGLE_TOLERANCE_DEG = 1e-9
DERIVATIVE_TOLERANCE = 1e-9

AngleModifier = Callable[[float, dict[str, float], dict[str, Any]], dict[str, float]]


def _flatten_positions(surface: dict[str, Any]) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for primitive in surface["primitives"]:
        points.extend(
            (float(point[0]), float(point[1]), float(point[2]))
            for point in primitive["positions"]
        )
    return points


def _topology_signature(surface: dict[str, Any]) -> tuple[tuple[str, int, tuple[int, ...]], ...]:
    return tuple(
        (
            str(primitive["id"]),
            len(primitive["positions"]),
            tuple(int(index) for index in primitive["indices"]),
        )
        for primitive in surface["primitives"]
    )


def _max_point_distance(
    left: list[tuple[float, float, float]],
    right: list[tuple[float, float, float]],
) -> float:
    if len(left) != len(right):
        raise ValueError("subframe vertex counts differ")
    return max((math.dist(a, b) for a, b in zip(left, right)), default=0.0)


def _max_angle_distance(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        raise ValueError("subframe animation tracks differ")
    return max((abs(float(left[key]) - float(right[key])) for key in left), default=0.0)


def _source_velocity_deg_s(
    validated: dict[str, Any],
    time_seconds: float,
) -> dict[str, float]:
    duration = float(validated["duration_seconds"])
    phase_velocity = (math.pi / duration) * math.sin(2.0 * math.pi * time_seconds / duration)
    return {
        row["joint_id"]: float(row["peak_angle_deg"]) * phase_velocity
        for row in validated["tracks"]
    }


def _source_acceleration_deg_s2(
    validated: dict[str, Any],
    time_seconds: float,
) -> dict[str, float]:
    duration = float(validated["duration_seconds"])
    phase_acceleration = (2.0 * math.pi * math.pi / (duration * duration)) * math.cos(
        2.0 * math.pi * time_seconds / duration
    )
    return {
        row["joint_id"]: float(row["peak_angle_deg"]) * phase_acceleration
        for row in validated["tracks"]
    }


def _max_abs(values: dict[str, float]) -> float:
    return max((abs(float(value)) for value in values.values()), default=0.0)


def _run_subframe_audit(
    spec: dict[str, Any],
    plan: dict[str, Any],
    clip: dict[str, Any],
    *,
    subframes_per_authored_interval: int,
    angle_modifier: AngleModifier | None = None,
    label: str = "exact-source",
) -> dict[str, Any]:
    motion = inspect_animation_motion(spec, plan, clip)
    if motion["gate"] != "PASS":
        raise ValueError("subframe continuity requires a passing Animation motion gate")

    if isinstance(subframes_per_authored_interval, bool) or not isinstance(subframes_per_authored_interval, int):
        raise ValueError("subframes_per_authored_interval must be an integer")
    if not 2 <= subframes_per_authored_interval <= 32:
        raise ValueError("subframes_per_authored_interval must be within 2..32")

    validated = _validate_clip(spec, plan, clip)
    duration = float(validated["duration_seconds"])
    authored_rate = int(validated["sample_rate_hz"])
    authored_intervals = int(validated["sample_count"]) - 1
    dense_rate = authored_rate * subframes_per_authored_interval
    dense_count = authored_intervals * subframes_per_authored_interval + 1

    surfaces: list[dict[str, Any]] = []
    positions: list[list[tuple[float, float, float]]] = []
    angle_rows: list[dict[str, float]] = []
    sample_rows: list[dict[str, Any]] = []

    for dense_index in range(dense_count):
        time_seconds = dense_index / dense_rate
        angles = _angles_for_time(validated, time_seconds)
        if angle_modifier is not None:
            angles = angle_modifier(time_seconds, dict(angles), validated)
        angles = {key: float(value) for key, value in sorted(angles.items())}
        surface = _pose_surface(spec, plan, angles)
        points = _flatten_positions(surface)
        surfaces.append(surface)
        positions.append(points)
        angle_rows.append(angles)
        sample_rows.append(
            {
                "dense_index": dense_index,
                "time_seconds": round(time_seconds, 9),
                "authored_sample_boundary": dense_index % subframes_per_authored_interval == 0,
                "angles_deg": {key: round(value, 12) for key, value in angles.items()},
                "maximum_source_speed_deg_s": _max_abs(_source_velocity_deg_s(validated, time_seconds)),
            }
        )

    signatures = [_topology_signature(surface) for surface in surfaces]
    topology_stable = all(signature == signatures[0] for signature in signatures)

    authored_position_rebind_residual = 0.0
    authored_angle_rebind_residual = 0.0
    for authored_index in range(authored_intervals + 1):
        dense_index = authored_index * subframes_per_authored_interval
        time_seconds = authored_index / authored_rate
        authored_frame = build_animation_frame(spec, plan, clip, time_seconds)
        authored_position_rebind_residual = max(
            authored_position_rebind_residual,
            _max_point_distance(positions[dense_index], _flatten_positions(authored_frame["surface"])),
        )
        authored_angle_rebind_residual = max(
            authored_angle_rebind_residual,
            _max_angle_distance(angle_rows[dense_index], authored_frame["angles_deg"]),
        )

    loop_position_residual = _max_point_distance(positions[0], positions[-1])
    loop_angle_residual = _max_angle_distance(angle_rows[0], angle_rows[-1])

    mirror_position_residual = 0.0
    mirror_angle_residual = 0.0
    for dense_index in range(dense_count):
        mirror_index = dense_count - 1 - dense_index
        mirror_position_residual = max(
            mirror_position_residual,
            _max_point_distance(positions[dense_index], positions[mirror_index]),
        )
        mirror_angle_residual = max(
            mirror_angle_residual,
            _max_angle_distance(angle_rows[dense_index], angle_rows[mirror_index]),
        )

    bilateral_angle_residual = 0.0
    for left, right in (("front-elbow-L", "front-elbow-R"), ("hind-knee-L", "hind-knee-R")):
        if left in angle_rows[0] or right in angle_rows[0]:
            if left not in angle_rows[0] or right not in angle_rows[0]:
                raise ValueError("bilateral track pair is incomplete")
            bilateral_angle_residual = max(
                bilateral_angle_residual,
                max(abs(row[left] - row[right]) for row in angle_rows),
            )

    dense_steps = [
        _max_point_distance(positions[index - 1], positions[index])
        for index in range(1, dense_count)
    ]
    authored_steps = [
        _max_point_distance(
            positions[(index - 1) * subframes_per_authored_interval],
            positions[index * subframes_per_authored_interval],
        )
        for index in range(1, authored_intervals + 1)
    ]
    maximum_dense_step = max(dense_steps, default=0.0)
    maximum_authored_step = max(authored_steps, default=0.0)

    midpoint = dense_count // 2
    track_ids = sorted(angle_rows[0])
    monotonic_rise = all(
        all(angle_rows[index][joint_id] <= angle_rows[index + 1][joint_id] + ANGLE_TOLERANCE_DEG for index in range(midpoint))
        for joint_id in track_ids
    )
    monotonic_fall = all(
        all(angle_rows[index][joint_id] >= angle_rows[index + 1][joint_id] - ANGLE_TOLERANCE_DEG for index in range(midpoint, dense_count - 1))
        for joint_id in track_ids
    )

    start_velocity = _source_velocity_deg_s(validated, 0.0)
    midpoint_velocity = _source_velocity_deg_s(validated, duration / 2.0)
    end_velocity = _source_velocity_deg_s(validated, duration)
    start_acceleration = _source_acceleration_deg_s2(validated, 0.0)
    end_acceleration = _source_acceleration_deg_s2(validated, duration)
    loop_acceleration_residual = _max_angle_distance(start_acceleration, end_acceleration)

    exact_source_gate = (
        topology_stable
        and authored_position_rebind_residual <= POSITION_TOLERANCE_M
        and authored_angle_rebind_residual <= ANGLE_TOLERANCE_DEG
        and loop_position_residual <= POSITION_TOLERANCE_M
        and loop_angle_residual <= ANGLE_TOLERANCE_DEG
        and mirror_position_residual <= POSITION_TOLERANCE_M
        and mirror_angle_residual <= ANGLE_TOLERANCE_DEG
        and bilateral_angle_residual <= ANGLE_TOLERANCE_DEG
        and _max_abs(start_velocity) <= DERIVATIVE_TOLERANCE
        and _max_abs(midpoint_velocity) <= DERIVATIVE_TOLERANCE
        and _max_abs(end_velocity) <= DERIVATIVE_TOLERANCE
        and loop_acceleration_residual <= DERIVATIVE_TOLERANCE
        and monotonic_rise
        and monotonic_fall
        and maximum_dense_step > 0.0
        and maximum_authored_step > 0.0
    )

    return {
        "schema": EVIDENCE_SCHEMA,
        "label": label,
        "source_name": motion["source_name"],
        "source_digest": motion["source_digest"],
        "neutral_surface_digest": motion["neutral_surface_digest"],
        "rig_plan_digest": motion["rig_plan_digest"],
        "rig_weighting_profile": motion["rig_weighting_profile"],
        "clip_name": motion["clip_name"],
        "clip_digest": motion["clip_digest"],
        "motion_semantics": motion["motion_semantics"],
        "duration_seconds": duration,
        "authored_sample_rate_hz": authored_rate,
        "authored_sample_count": authored_intervals + 1,
        "subframes_per_authored_interval": subframes_per_authored_interval,
        "dense_sample_rate_hz": dense_rate,
        "dense_sample_count": dense_count,
        "metrics": {
            "topology_stable": topology_stable,
            "maximum_authored_sample_position_rebind_residual_m": authored_position_rebind_residual,
            "maximum_authored_sample_angle_rebind_residual_deg": authored_angle_rebind_residual,
            "loop_position_residual_m": loop_position_residual,
            "loop_angle_residual_deg": loop_angle_residual,
            "maximum_time_mirror_position_residual_m": mirror_position_residual,
            "maximum_time_mirror_angle_residual_deg": mirror_angle_residual,
            "maximum_dense_bilateral_angle_residual_deg": bilateral_angle_residual,
            "maximum_dense_adjacent_vertex_step_m": maximum_dense_step,
            "maximum_authored_adjacent_vertex_step_m": maximum_authored_step,
            "dense_to_authored_max_step_ratio": maximum_dense_step / maximum_authored_step,
            "maximum_start_source_velocity_deg_s": _max_abs(start_velocity),
            "maximum_midpoint_source_velocity_deg_s": _max_abs(midpoint_velocity),
            "maximum_end_source_velocity_deg_s": _max_abs(end_velocity),
            "loop_source_acceleration_residual_deg_s2": loop_acceleration_residual,
            "monotonic_rise": monotonic_rise,
            "monotonic_fall": monotonic_fall,
        },
        "samples": sample_rows,
        "gate": (
            "PASS_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY_WITNESS"
            if exact_source_gate
            else "HOLD_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY"
        ),
        "truth": {
            "proves_if_green": "For this exact source, rig, smoothstep-v0 weighting and unchanged raised-cosine clip, deterministic 8x-style subframe evaluation through the existing deformation implementation preserves all authored samples, exact loop closure, bilateral/time symmetry, monotonic rise/fall and zero analytic source velocity at start/midpoint/end within the stated tolerances.",
            "does_not_prove": "Target-engine interpolation, production skeleton/skin transport, Technical Art receiver adoption, wall-clock frame pacing, renderer sampling, perceptual animation quality, collision/physics/input/gameplay, target-device performance, CANON, production readiness, or mastery.",
        },
    }


def inspect_subframe_continuity(
    spec: dict[str, Any],
    plan: dict[str, Any],
    clip: dict[str, Any],
    *,
    subframes_per_authored_interval: int = DEFAULT_SUBFRAMES_PER_AUTHORED_INTERVAL,
) -> dict[str, Any]:
    """Audit the exact current source curve between authored samples without changing it."""
    return _run_subframe_audit(
        spec,
        plan,
        clip,
        subframes_per_authored_interval=subframes_per_authored_interval,
        angle_modifier=None,
        label="exact-source",
    )


def inspect_hidden_between_key_negative_control(
    spec: dict[str, Any],
    plan: dict[str, Any],
    clip: dict[str, Any],
    *,
    subframes_per_authored_interval: int = DEFAULT_SUBFRAMES_PER_AUTHORED_INTERVAL,
    bump_peak_deg: float = 0.05,
) -> dict[str, Any]:
    """Inject a narrow between-key bump that is exactly zero at every authored sample.

    The mutation exists only to prove that the dense audit contributes information beyond
    the retained 41 authored samples. It is never returned as an Animation candidate.
    """
    if not math.isfinite(float(bump_peak_deg)) or not 0.0 < float(bump_peak_deg) <= 0.5:
        raise ValueError("bump_peak_deg must be finite and within (0, 0.5]")

    def modifier(time_seconds: float, angles: dict[str, float], validated: dict[str, Any]) -> dict[str, float]:
        sample_rate = int(validated["sample_rate_hz"])
        start = 13.0 / sample_rate
        end = 14.0 / sample_rate
        if start < time_seconds < end:
            phase = (time_seconds - start) / (end - start)
            bump = float(bump_peak_deg) * (math.sin(math.pi * phase) ** 2)
            if "front-elbow-L" not in angles:
                raise ValueError("negative control requires front-elbow-L")
            angles["front-elbow-L"] += bump
        return angles

    report = _run_subframe_audit(
        spec,
        plan,
        clip,
        subframes_per_authored_interval=subframes_per_authored_interval,
        angle_modifier=modifier,
        label="hidden-between-key-negative-control",
    )
    report["negative_control"] = {
        "mutation": "front-elbow-L narrow sin^2 bump inside authored interval 13->14 only",
        "peak_bump_deg": float(bump_peak_deg),
        "authored_samples_preserved": (
            report["metrics"]["maximum_authored_sample_position_rebind_residual_m"] <= POSITION_TOLERANCE_M
            and report["metrics"]["maximum_authored_sample_angle_rebind_residual_deg"] <= ANGLE_TOLERANCE_DEG
        ),
        "expected_gate": "HOLD_DENSE_SUBFRAME_SOURCE_CURVE_CONTINUITY",
    }
    return report
