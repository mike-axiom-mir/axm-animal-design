"""Bounded parameter-neighborhood search for the Animal elbow review form.

This module does not adopt a form. It evaluates a small, declared neighborhood
around the existing balanced Organic candidate after the dense sweep exposed a
single tiny minimum-area regression. Selection is structural only and remains a
review handoff to Art Direction / Visual QA and source ownership.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .connected_deformation import _build_exact_candidate, _dot, _mul, _select_joint, _sub, _unit, digest
from .organic_elbow_relief import _bounds, _ring_indices
from .organic_elbow_balanced_relief import (
    BASELINE_CANDIDATE_DIGEST,
    CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
)
from .organic_elbow_balanced_sweep import (
    POSE_SCHEDULE_DEG,
    WEIGHTING_PROFILES,
    _metric_comparison,
    _probe_dense_candidate,
)

SEARCH_SCHEMA = "axm.animal-organic-elbow-dense-parameter-search/v0.1"
NOMINAL_ELBOW_RADIUS_M = 0.09
BEND_RADII_M = (0.0875, 0.08775, 0.088, 0.08825, 0.0885, 0.08875, 0.089)
JOINT_AXIS_WIDTH_SCALES = (1.025, 1.0275, 1.03, 1.0325, 1.035)
MAX_NEUTRAL_VERTEX_DELTA_M = 0.0028
MAX_POSITIVE_BOUND_EXPANSION_M = 0.003
CURRENT_RADIUS_M = 0.0875
CURRENT_AXIS_SCALE = 1.03


def _bound_delta(before, after):
    return [
        [round(after[axis][side] - before[axis][side], 12) for side in range(2)]
        for axis in range(3)
    ]


def build_search_variant(
    spec: dict[str, Any],
    plan: dict[str, Any],
    bend_plane_radius_m: float,
    joint_axis_width_scale: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    if bend_plane_radius_m not in BEND_RADII_M:
        raise ValueError("bend-plane radius outside declared search grid")
    if joint_axis_width_scale not in JOINT_AXIS_WIDTH_SCALES:
        raise ValueError("joint-axis scale outside declared search grid")

    baseline, radius_derivation = _build_exact_candidate(spec)
    if digest(baseline) != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("baseline connected candidate identity drift")
    joint = _select_joint(spec, plan)
    axis = _unit(tuple(float(v) for v in joint["axis"]), "joint axis")
    if tuple(round(value, 12) for value in axis) != (0.0, 1.0, 0.0):
        raise ValueError("search remains bound to exact +Y elbow axis")
    if abs(float(radius_derivation["radii_m"][1]) - NOMINAL_ELBOW_RADIUS_M) > 1e-12:
        raise ValueError("source-derived elbow radius drift")

    candidate = deepcopy(baseline)
    candidate["id"] = (
        f"front-left-connected-chain-elbow-search-r{bend_plane_radius_m:.5f}"
        f"-y{joint_axis_width_scale:.4f}"
    )
    ring = _ring_indices(candidate, 1)
    joint_position = tuple(float(v) for v in spec["landmarks"][joint["landmark"]])
    bend_ratio = bend_plane_radius_m / NOMINAL_ELBOW_RADIUS_M
    baseline_positions = [tuple(point) for point in baseline["positions"]]
    candidate_positions = [list(point) for point in baseline["positions"]]
    for vertex_index in ring:
        point = baseline_positions[vertex_index]
        relative = _sub(point, joint_position)
        parallel = _mul(axis, _dot(relative, axis))
        perpendicular = _sub(relative, parallel)
        adjusted = tuple(
            joint_position[i]
            + parallel[i] * joint_axis_width_scale
            + perpendicular[i] * bend_ratio
            for i in range(3)
        )
        candidate_positions[vertex_index] = [round(value, 9) for value in adjusted]
    candidate["positions"] = candidate_positions
    candidate["organic_search_review"] = {
        "schema": SEARCH_SCHEMA,
        "bend_plane_radius_m": bend_plane_radius_m,
        "joint_axis_width_scale": joint_axis_width_scale,
        "source_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "source_rewritten": False,
        "adopted": False,
    }

    moved = [
        index
        for index, (before, after) in enumerate(zip(baseline_positions, candidate_positions))
        if math.dist(before, after) > 1e-12
    ]
    if moved != ring:
        raise ValueError("search variant moved vertices outside exact elbow ring")
    if baseline["indices"] != candidate["indices"] or baseline["path_points"] != candidate["path_points"]:
        raise ValueError("search variant topology/path drift")
    if baseline["radii"] != candidate["radii"]:
        raise ValueError("search variant silently rewrote nominal source-derived radii")

    before_bounds = _bounds(baseline_positions)
    after_bounds = _bounds([tuple(point) for point in candidate_positions])
    delta = _bound_delta(before_bounds, after_bounds)
    max_bound_expansion = max(max(0.0, value) for axis_delta in delta for value in axis_delta)
    max_neutral_delta = max(
        math.dist(baseline_positions[index], candidate_positions[index]) for index in moved
    )
    scope = {
        "moved_vertex_indices": moved,
        "moved_vertex_count": len(moved),
        "maximum_neutral_vertex_delta_m": round(max_neutral_delta, 12),
        "maximum_positive_bound_expansion_m": round(max_bound_expansion, 12),
        "bounds_delta_m": delta,
        "within_neutral_delta_bound": max_neutral_delta <= MAX_NEUTRAL_VERTEX_DELTA_M + 1e-12,
        "within_positive_bound_expansion": max_bound_expansion <= MAX_POSITIVE_BOUND_EXPANSION_M + 1e-12,
    }
    return candidate, scope


def inspect_parameter_search(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")

    baseline, _ = _build_exact_candidate(spec)
    baseline_probes = {
        profile: _probe_dense_candidate(baseline, spec, plan, profile)
        for profile in WEIGHTING_PROFILES
    }
    baseline_by_profile = {
        profile: {float(row["angle_deg"]): row for row in probe["poses"]}
        for profile, probe in baseline_probes.items()
    }

    rows = []
    for radius in BEND_RADII_M:
        for scale in JOINT_AXIS_WIDTH_SCALES:
            candidate, scope = build_search_variant(spec, plan, radius, scale)
            probes = {
                profile: _probe_dense_candidate(candidate, spec, plan, profile)
                for profile in WEIGHTING_PROFILES
            }
            structural = all(probe["structural_gate"] == "PASS" for probe in probes.values())
            directional = True
            min_area_nonzero = math.inf
            min_edge_nonzero = math.inf
            per_sample = []
            for profile in WEIGHTING_PROFILES:
                candidate_by_angle = {
                    float(item["angle_deg"]): item for item in probes[profile]["poses"]
                }
                for angle in POSE_SCHEDULE_DEG:
                    metric = _metric_comparison(
                        baseline_by_profile[profile][angle], candidate_by_angle[angle]
                    )
                    directional &= metric["directionally_nonworse"]
                    if angle != 0.0:
                        min_area_nonzero = min(
                            min_area_nonzero,
                            metric["balanced_min_area_delta_vs_baseline"],
                            metric["balanced_max_area_reduction_vs_baseline"],
                        )
                        min_edge_nonzero = min(
                            min_edge_nonzero,
                            metric["balanced_min_edge_gain_vs_baseline"],
                            metric["balanced_max_edge_reduction_vs_baseline"],
                        )
                    per_sample.append(
                        {
                            "weighting": profile,
                            "angle_deg": angle,
                            **metric,
                        }
                    )
            bounded = scope["within_neutral_delta_bound"] and scope["within_positive_bound_expansion"]
            eligible = structural and directional and bounded
            rows.append(
                {
                    "bend_plane_radius_m": radius,
                    "joint_axis_width_scale": scale,
                    "candidate_digest": digest(candidate),
                    "scope": scope,
                    "structural_all_samples": structural,
                    "directionally_nonworse_all_samples": directional,
                    "bounded_neutral_form": bounded,
                    "eligible_structural_successor": eligible,
                    "minimum_nonzero_area_margin": round(min_area_nonzero, 12),
                    "minimum_nonzero_edge_margin": round(min_edge_nonzero, 12),
                    "samples": per_sample,
                }
            )

    control = next(
        row
        for row in rows
        if row["bend_plane_radius_m"] == CURRENT_RADIUS_M
        and row["joint_axis_width_scale"] == CURRENT_AXIS_SCALE
    )
    if control["candidate_digest"] != CANDIDATE_DIGEST:
        raise ValueError("parameter search failed to reproduce exact balanced candidate")

    eligible = [row for row in rows if row["eligible_structural_successor"]]
    selected = None
    if eligible:
        selected = max(
            eligible,
            key=lambda row: (
                row["minimum_nonzero_area_margin"],
                row["minimum_nonzero_edge_margin"],
                -row["scope"]["maximum_neutral_vertex_delta_m"],
                -row["bend_plane_radius_m"],
                -row["joint_axis_width_scale"],
            ),
        )

    return {
        "schema": SEARCH_SCHEMA,
        "state": (
            "PASS_BOUNDED_STRUCTURAL_SUCCESSOR_FOUND"
            if selected is not None
            else "BLOCKED_NO_BOUNDED_STRUCTURAL_SUCCESSOR_IN_DECLARED_GRID"
        ),
        "adoption_state": "HOLD_VISUAL_AND_SOURCE_ADOPTION",
        "source_digest": SOURCE_DIGEST,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "baseline_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "current_balanced_candidate_digest": CANDIDATE_DIGEST,
        "pose_schedule_deg": list(POSE_SCHEDULE_DEG),
        "weighting_profiles": list(WEIGHTING_PROFILES),
        "grid": {
            "bend_radii_m": list(BEND_RADII_M),
            "joint_axis_width_scales": list(JOINT_AXIS_WIDTH_SCALES),
            "variant_count": len(rows),
            "maximum_neutral_vertex_delta_m": MAX_NEUTRAL_VERTEX_DELTA_M,
            "maximum_positive_bound_expansion_m": MAX_POSITIVE_BOUND_EXPANSION_M,
        },
        "current_control": control,
        "selected_structural_successor": selected,
        "variants": rows,
        "selection_policy": [
            "require all 25 sampled poses under both pinned weighting profiles to retain structural PASS",
            "require all four retained distortion directions to be non-worse than baseline at every sample",
            "require the prior neutral-displacement and positive-bound-expansion limits",
            "among eligible variants maximize the worst nonzero area margin, then edge margin, then prefer smaller neutral displacement",
            "selection is structural review only and cannot adopt source form or aesthetic direction",
        ],
        "truth_boundary": [
            "the search is restricted to one exact elbow ring and a declared small parameter neighborhood",
            "the exact source, rig plan, topology, path points, nominal radii and all vertices outside the elbow ring remain unchanged",
            "a selected structural successor is not anatomy, biology, visual approval, source adoption, Rigging acceptance, Animation, runtime, gameplay, CANON or production readiness",
        ],
    }
