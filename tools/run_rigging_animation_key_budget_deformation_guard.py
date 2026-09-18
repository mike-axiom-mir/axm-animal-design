#!/usr/bin/env python3
"""Numerically stable launcher for the Animal Rigging key-budget guard.

The owner guard intentionally reproduces Runtime PR #30's quaternion-space metric.
For unit quaternions that metric is exactly one half of the shortest physical
rotation angle. Near identical rotations, computing the physical angle with acos(dot)
loses precision after dot rounds to 1.0. Bind the physical metric to the exact
mathematical identity 2 * Runtime-metric before executing the unchanged guard.

This changes no source, rig, weights, animation channel, Runtime candidate, tolerance,
or authority boundary.
"""
from __future__ import annotations

import build_rigging_animation_key_budget_deformation_guard as guard


def _stable_physical_rotation_error_deg(a, b) -> float:
    return 2.0 * guard._runtime_quaternion_metric_deg(a, b)


guard._physical_rotation_error_deg = _stable_physical_rotation_error_deg


if __name__ == "__main__":
    guard.main()
