"""Bounded sampled-playback evidence for an existing Animal motion clip.

This module does not author, retime, interpolate, or control motion. It maps the exact
endpoint-inclusive authored samples onto a repeated display schedule and proves that
omitting the duplicate endpoint from each displayed cycle preserves the authored final
step into the exact neutral seam.
"""
from __future__ import annotations

import math
from typing import Any

from . import animation_motion as motion
from .animation_temporal import inspect_temporal_continuity

EVIDENCE_SCHEMA = "axm.animal-animation-sampled-playback/v0.1"
PLAYBACK_MODE = "DISCRETE_AUTHORED_SAMPLES_NO_INTERPOLATION"
POSITION_TOLERANCE_M = 1e-12


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _build_display_schedule(duration_seconds: float, sample_rate_hz: int, sample_count: int) -> list[float]:
    duration = _number(duration_seconds, "duration_seconds")
    if duration <= 0.0:
        raise ValueError("duration_seconds must be positive")
    if isinstance(sample_rate_hz, bool) or not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    expected_count = int(round(duration * sample_rate_hz)) + 1
    if sample_count != expected_count:
        raise ValueError("sample_count must be endpoint-inclusive for duration * sample_rate_hz")
    return [round(index / sample_rate_hz, 9) for index in range(sample_count - 1)]


def playback_frame_index(time_seconds: float, duration_seconds: float, sample_rate_hz: int) -> int:
    """Return the discrete authored-sample index for a repeated evidence playback time."""
    time_value = _number(time_seconds, "time_seconds")
    duration = _number(duration_seconds, "duration_seconds")
    if time_value < 0.0:
        raise ValueError("time_seconds must be non-negative")
    if duration <= 0.0:
        raise ValueError("duration_seconds must be positive")
    if isinstance(sample_rate_hz, bool) or not isinstance(sample_rate_hz, int) or sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be a positive integer")
    display_count = int(round(duration * sample_rate_hz))
    if display_count <= 0:
        raise ValueError("duration_seconds * sample_rate_hz must contain at least one interval")
    wrapped = math.fmod(time_value, duration)
    # Exact cycle boundaries intentionally map to neutral sample zero.
    if abs(wrapped) <= 1e-12 or abs(wrapped - duration) <= 1e-12:
        return 0
    index = int(math.floor((wrapped + 1e-12) * sample_rate_hz))
    return min(max(index, 0), display_count - 1)


def _flatten_positions(surface: dict[str, Any]) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    primitives = surface.get("primitives")
    if not isinstance(primitives, list):
        raise ValueError("surface primitives must be a list")
    for primitive in sorted(primitives, key=lambda row: str(row.get("id", ""))):
        positions = primitive.get("positions")
        if not isinstance(positions, list):
            raise ValueError("primitive positions must be a list")
        rows.extend((float(point[0]), float(point[1]), float(point[2])) for point in positions)
    return rows


def _maximum_surface_delta(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_points = _flatten_positions(left)
    right_points = _flatten_positions(right)
    if len(left_points) != len(right_points):
        raise ValueError("surface topology changed across playback comparison")
    return max((math.dist(a, b) for a, b in zip(left_points, right_points)), default=0.0)


def inspect_sampled_playback(spec: dict[str, Any], plan: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
    """Prove one exact authored loop can be replayed as a discrete 40 Hz evidence cycle."""
    temporal = inspect_temporal_continuity(spec, plan, clip)
    if temporal["gate"] != "PASS_LOOP_TEMPORAL_CONTINUITY":
        raise ValueError("sampled playback requires a passing temporal-continuity source")

    duration = float(temporal["duration_seconds"])
    sample_rate = int(temporal["sample_rate_hz"])
    sample_count = int(temporal["sample_count"])
    schedule = _build_display_schedule(duration, sample_rate, sample_count)
    if not schedule:
        raise ValueError("display schedule must contain at least one sample")

    penultimate = motion.build_animation_frame(spec, plan, clip, schedule[-1])
    endpoint = motion.build_animation_frame(spec, plan, clip, duration)
    neutral = motion.build_animation_frame(spec, plan, clip, 0.0)
    exact_endpoint_seam = endpoint["surface_digest"] == neutral["surface_digest"]

    wrap_step = _maximum_surface_delta(penultimate["surface"], neutral["surface"])
    authored_last_step = float(temporal["adjacent_max_vertex_steps_m"][-1])
    wrap_step_residual = abs(wrap_step - authored_last_step)
    cycle_duration = len(schedule) / sample_rate

    index_probes = {
        "t0": playback_frame_index(0.0, duration, sample_rate),
        "last_interval_start": playback_frame_index(schedule[-1], duration, sample_rate),
        "just_before_wrap": playback_frame_index(duration - 1e-9, duration, sample_rate),
        "exact_wrap": playback_frame_index(duration, duration, sample_rate),
        "one_interval_after_wrap": playback_frame_index(duration + 1.0 / sample_rate, duration, sample_rate),
        "second_exact_wrap": playback_frame_index(duration * 2.0, duration, sample_rate),
    }
    expected_probes = {
        "t0": 0,
        "last_interval_start": len(schedule) - 1,
        "just_before_wrap": len(schedule) - 1,
        "exact_wrap": 0,
        "one_interval_after_wrap": 1,
        "second_exact_wrap": 0,
    }
    index_probe_pass = index_probes == expected_probes

    gate = (
        exact_endpoint_seam
        and abs(cycle_duration - duration) <= 1e-12
        and wrap_step_residual <= POSITION_TOLERANCE_M
        and index_probe_pass
    )
    return {
        "schema": EVIDENCE_SCHEMA,
        "source_name": temporal["source_name"],
        "source_digest": temporal["source_digest"],
        "neutral_surface_digest": temporal["neutral_surface_digest"],
        "rig_plan_digest": temporal["rig_plan_digest"],
        "rig_weighting_profile": temporal["rig_weighting_profile"],
        "clip_name": temporal["clip_name"],
        "clip_digest": temporal["clip_digest"],
        "motion_semantics": temporal["motion_semantics"],
        "playback_mode": PLAYBACK_MODE,
        "duration_seconds": duration,
        "sample_rate_hz": sample_rate,
        "endpoint_inclusive_source_sample_count": sample_count,
        "displayed_frame_count_per_cycle": len(schedule),
        "display_frame_interval_seconds": round(1.0 / sample_rate, 9),
        "display_schedule_seconds": schedule,
        "metrics": {
            "display_cycle_duration_seconds": cycle_duration,
            "exact_endpoint_seam": exact_endpoint_seam,
            "wrap_step_m": wrap_step,
            "authored_last_adjacent_step_m": authored_last_step,
            "wrap_step_residual_m": wrap_step_residual,
            "position_tolerance_m": POSITION_TOLERANCE_M,
            "index_probe_pass": index_probe_pass,
            "index_probes": index_probes,
        },
        "gate": "PASS_DISCRETE_SAMPLED_PLAYBACK_SEAM" if gate else "FAIL_DISCRETE_SAMPLED_PLAYBACK_SEAM",
        "truth": {
            "proves_if_green": [
                "the exact endpoint-inclusive authored samples can be displayed as one repeated discrete cycle without duplicating the neutral endpoint",
                "the displayed wrap from the last visible sample to sample zero equals the final authored adjacent surface step inside tolerance",
                "exact cycle boundaries deterministically resolve to neutral sample zero",
            ],
            "does_not_prove": [
                "continuous interpolation between authored samples",
                "target-engine animation playback",
                "frame pacing on a target device",
                "runtime controller or state-machine integration",
                "gameplay acceptance",
                "perceptual animation quality or biological gait",
            ],
        },
    }
