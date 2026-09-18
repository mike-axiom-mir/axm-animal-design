"""Animation-owned temporal audit for a Rigging reconstruction evidence receipt.

This module does not reconstruct normals/tangents, modify the rig, or adopt a
Technical Art receiver. It consumes the exact Rigging reconstruction receipt as
an external evidence packet and asks one Animation-owned question:

Does the reconstruction error remain temporally symmetric and loop-closed over
the exact 41 authored samples of the unchanged articulation pulse?

The result is a sampled evidence boundary only. It is not continuous-motion,
engine playback, controller, gameplay, or production-transport acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

EVIDENCE_SCHEMA = "axm.animal-animation-transport-reconstruction-temporal-stability/v0.1"
PASS_STATE = "PASS_RECONSTRUCTION_TEMPORAL_ERROR_SYMMETRY_AND_LOOP_CLOSURE"
HOLD_STATE = "HOLD_RECONSTRUCTION_TEMPORAL_ERROR_STABILITY"

RIGGING_RECONSTRUCTION_SCHEMA = "axm.animal-post-skin-owner-frame-reconstruction/v0.1"
RIGGING_RECONSTRUCTION_PASS = "PASS_TRANSPORTED_POST_SKIN_OWNER_FRAME_RECONSTRUCTION_41_KEYS"
EXPECTED_SAMPLE_COUNT = 41
EXPECTED_SAMPLE_INTERVAL_SECONDS = 0.025
EXPECTED_DURATION_SECONDS = 1.0
EXPECTED_PEAK_INDEX = 20
EXPECTED_PEAK_ANGLE_DEG = 18.0

TIME_TOLERANCE_SECONDS = 5e-8
ANGLE_TOLERANCE_DEG = 1e-6
MIRROR_SCALAR_TOLERANCE = 1e-12
ADJACENT_POSITION_ERROR_DELTA_LIMIT_M = 1e-10
ADJACENT_DIRECTION_ERROR_DELTA_LIMIT_DEG = 1e-7
ADJACENT_ORTHOGONALITY_ERROR_DELTA_LIMIT = 1e-12

SCALAR_FIELDS = (
    "maximum_position_residual_m",
    "maximum_normal_angle_deg",
    "maximum_tangent_angle_deg",
    "maximum_normal_tangent_dot_abs",
    "split_position_residual_m",
)


def _f(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _max_adjacent_delta(values: list[float]) -> float:
    return max((abs(b - a) for a, b in zip(values, values[1:])), default=0.0)


def _max_mirror_delta(values: list[float]) -> float:
    return max((abs(values[i] - values[-1 - i]) for i in range(len(values))), default=0.0)


def inspect_reconstruction_temporal_stability(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != RIGGING_RECONSTRUCTION_SCHEMA:
        raise ValueError("unexpected Rigging reconstruction schema")
    if receipt.get("state") != RIGGING_RECONSTRUCTION_PASS:
        raise ValueError("Rigging reconstruction prerequisite is not PASS")
    reconstruction = receipt.get("reconstruction")
    if not isinstance(reconstruction, dict) or reconstruction.get("gate") != "PASS":
        raise ValueError("Rigging reconstruction gate is not PASS")
    truth = receipt.get("truth_boundary")
    if not isinstance(truth, dict):
        raise ValueError("Rigging truth boundary missing")
    if truth.get("technical_art_adopted_reconstruction") is not False:
        raise ValueError("receipt no longer preserves Technical Art non-adoption boundary")
    if truth.get("animation_modified") is not False:
        raise ValueError("receipt no longer preserves Animation non-modification boundary")

    rows = receipt.get("all_41_key_samples")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SAMPLE_COUNT:
        raise ValueError("expected exactly 41 authored reconstruction samples")

    sample_indices = [int(row.get("sample_index", -1)) for row in rows]
    if sample_indices != list(range(EXPECTED_SAMPLE_COUNT)):
        raise ValueError("sample index sequence drift")

    times = [_f(row.get("time_seconds"), f"time[{i}]") for i, row in enumerate(rows)]
    angles = [
        _f(row.get("angle_deg_from_transport_quaternion"), f"angle[{i}]")
        for i, row in enumerate(rows)
    ]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("sample times must be strictly increasing")

    interval_residuals = [
        abs((times[i + 1] - times[i]) - EXPECTED_SAMPLE_INTERVAL_SECONDS)
        for i in range(EXPECTED_SAMPLE_COUNT - 1)
    ]
    max_interval_residual = max(interval_residuals, default=0.0)
    max_time_mirror_residual = max(
        abs((times[i] + times[-1 - i]) - EXPECTED_DURATION_SECONDS)
        for i in range(EXPECTED_SAMPLE_COUNT)
    )
    max_angle_mirror_residual = _max_mirror_delta(angles)
    peak_index = max(range(EXPECTED_SAMPLE_COUNT), key=lambda i: angles[i])

    scalar_series: dict[str, list[float]] = {}
    scalar_mirror_residuals: dict[str, float] = {}
    scalar_adjacent_deltas: dict[str, float] = {}
    for field in SCALAR_FIELDS:
        values = [_f(row.get(field), f"{field}[{i}]") for i, row in enumerate(rows)]
        scalar_series[field] = values
        scalar_mirror_residuals[field] = _max_mirror_delta(values)
        scalar_adjacent_deltas[field] = _max_adjacent_delta(values)

    handedness = [int(row.get("handedness_mismatch_count", -1)) for row in rows]

    timing_pass = (
        abs(times[0]) <= TIME_TOLERANCE_SECONDS
        and abs(times[-1] - EXPECTED_DURATION_SECONDS) <= TIME_TOLERANCE_SECONDS
        and max_interval_residual <= TIME_TOLERANCE_SECONDS
        and max_time_mirror_residual <= TIME_TOLERANCE_SECONDS
    )
    motion_identity_pass = (
        max_angle_mirror_residual <= ANGLE_TOLERANCE_DEG
        and peak_index == EXPECTED_PEAK_INDEX
        and abs(angles[0]) <= ANGLE_TOLERANCE_DEG
        and abs(angles[-1]) <= ANGLE_TOLERANCE_DEG
        and abs(angles[EXPECTED_PEAK_INDEX] - EXPECTED_PEAK_ANGLE_DEG) <= ANGLE_TOLERANCE_DEG
    )
    mirror_error_pass = all(
        value <= MIRROR_SCALAR_TOLERANCE for value in scalar_mirror_residuals.values()
    )
    adjacent_error_pass = (
        scalar_adjacent_deltas["maximum_position_residual_m"] <= ADJACENT_POSITION_ERROR_DELTA_LIMIT_M
        and scalar_adjacent_deltas["maximum_normal_angle_deg"] <= ADJACENT_DIRECTION_ERROR_DELTA_LIMIT_DEG
        and scalar_adjacent_deltas["maximum_tangent_angle_deg"] <= ADJACENT_DIRECTION_ERROR_DELTA_LIMIT_DEG
        and scalar_adjacent_deltas["maximum_normal_tangent_dot_abs"] <= ADJACENT_ORTHOGONALITY_ERROR_DELTA_LIMIT
        and scalar_adjacent_deltas["split_position_residual_m"] <= ADJACENT_POSITION_ERROR_DELTA_LIMIT_M
    )
    loop_error_closure_pass = all(
        abs(values[0] - values[-1]) <= MIRROR_SCALAR_TOLERANCE
        for values in scalar_series.values()
    ) and handedness[0] == handedness[-1] == 0
    handedness_pass = all(value == 0 for value in handedness)

    gate = (
        PASS_STATE
        if all(
            (
                timing_pass,
                motion_identity_pass,
                mirror_error_pass,
                adjacent_error_pass,
                loop_error_closure_pass,
                handedness_pass,
            )
        )
        else HOLD_STATE
    )

    return {
        "schema": EVIDENCE_SCHEMA,
        "gate": gate,
        "scope": "SAMPLED_RECONSTRUCTION_ERROR_STABILITY_ONLY",
        "sample_count": EXPECTED_SAMPLE_COUNT,
        "timing": {
            "start_seconds": times[0],
            "end_seconds": times[-1],
            "expected_interval_seconds": EXPECTED_SAMPLE_INTERVAL_SECONDS,
            "maximum_interval_residual_seconds": max_interval_residual,
            "maximum_time_mirror_residual_seconds": max_time_mirror_residual,
            "pass": timing_pass,
        },
        "motion_identity": {
            "peak_index": peak_index,
            "peak_angle_deg": angles[peak_index],
            "maximum_angle_mirror_residual_deg": max_angle_mirror_residual,
            "pass": motion_identity_pass,
        },
        "reconstruction_error_temporal": {
            "maximum_mirror_residual_by_field": scalar_mirror_residuals,
            "maximum_adjacent_delta_by_field": scalar_adjacent_deltas,
            "mirror_pass": mirror_error_pass,
            "adjacent_stability_pass": adjacent_error_pass,
            "loop_error_closure_pass": loop_error_closure_pass,
            "handedness_zero_all_samples": handedness_pass,
        },
        "source_reconstruction": {
            "schema": receipt["schema"],
            "state": receipt["state"],
            "method": reconstruction.get("method"),
            "maximum_owner_position_residual_m": reconstruction.get("maximum_owner_position_residual_m"),
            "maximum_owner_normal_angle_deg": reconstruction.get("maximum_owner_normal_angle_deg"),
            "maximum_owner_tangent_angle_deg": reconstruction.get("maximum_owner_tangent_angle_deg"),
        },
        "truth_boundary": {
            "animation_motion_modified": False,
            "rigging_reconstruction_modified": False,
            "technical_art_receiver_adopted": False,
            "production_transport_equivalence_claimed": False,
            "continuous_motion_claimed": False,
            "runtime_controller_claimed": False,
            "gameplay_claimed": False,
            "perceptual_acceptance_claimed": False,
        },
    }


def build_temporal_spike_negative_control(receipt: dict[str, Any]) -> dict[str, Any]:
    """Inject a sub-Rigging-tolerance asymmetric temporal error spike."""
    mutated = deepcopy(receipt)
    mutated["all_41_key_samples"][13]["maximum_normal_angle_deg"] += 1e-4
    return inspect_reconstruction_temporal_stability(mutated)
