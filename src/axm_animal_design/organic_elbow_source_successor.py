"""Source-owned Organic Form successor for the selected Animal elbow shape.

This module adopts the exact selected-003 review geometry as a new Organic-owned
successor identity without altering the historical quadruped baseline source.
It deliberately remains non-CANON and does not claim Rigging, Animation, runtime,
biology/anatomy, or production readiness.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .connected_deformation import _build_exact_candidate, digest

PROFILE_SCHEMA = "axm.animal-organic-form-successor/v0.1"
INSTANCE_SCHEMA = "axm.animal-organic-form-successor-instance/v0.1"
PROFILE_ID = "quadruped-front-elbow-L-form-successor-003"
PROFILE_DIGEST = "8dbab7764819ebcbf825f6d0650053b108b8773df3644934738e3ec9f4712e66"
SOURCE_DIGEST = "9becd2dea714d662e23386aacabd0fa99abd11ff3c08aad7d242138e654f932b"
BASELINE_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
SELECTED_REVIEW_CANDIDATE_DIGEST = "c68eb89eefed5ca98951ea74bb28e370ab5ce9f7c2cf88d6adcdc48583141be4"
SELECTED_REVIEW_GEOMETRY_DIGEST = "dfc58bebbbd6e3a73b96fa98dc31bbd6deace79bb1c5ed82671a78d8a048246a"
SOURCE_SUCCESSOR_CANDIDATE_ID = "front-left-connected-chain-elbow-source-successor-003"
SOURCE_SUCCESSOR_CANDIDATE_DIGEST = "ace2366d8cd14c00df670b5fe1f0780ab2d01992482455ad5f7c4c9cadffeeba"
NOMINAL_ELBOW_RADIUS_M = 0.09
BEND_PLANE_RADIUS_M = 0.0885
JOINT_AXIS_WIDTH_SCALE = 1.03
ELBOW_PATH_INDEX = 1
EXPECTED_AXIS = (0.0, 1.0, 0.0)
MAX_NEUTRAL_VERTEX_DELTA_M = 0.0028
MAX_POSITIVE_BOUND_EXPANSION_M = 0.003


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _add(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _mul(a, scalar):
    return tuple(a[i] * scalar for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _bounds(positions):
    return [
        [round(min(point[axis] for point in positions), 9), round(max(point[axis] for point in positions), 9)]
        for axis in range(3)
    ]


def _geometry_digest(candidate: dict[str, Any]) -> str:
    return digest({
        key: candidate[key]
        for key in ("positions", "indices", "path_points", "radii", "segments")
    })


def _validate_profile(profile: dict[str, Any]) -> None:
    if not isinstance(profile, dict) or profile.get("schema") != PROFILE_SCHEMA:
        raise ValueError("source-successor profile schema mismatch")
    if digest(profile) != PROFILE_DIGEST:
        raise ValueError("source-successor profile identity drift")
    if profile.get("id") != PROFILE_ID:
        raise ValueError("source-successor profile id drift")
    if profile.get("base_source") != {
        "name": "quadruped-neutral-001",
        "digest": SOURCE_DIGEST,
    }:
        raise ValueError("source-successor base source binding drift")
    if profile.get("receiver") != {
        "candidate_id": "front-left-connected-chain-001",
        "candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "path_landmarks": ["shoulder_L", "elbow_L", "wrist_L", "front_paw_L"],
        "segments": 10,
    }:
        raise ValueError("source-successor receiver binding drift")
    if profile.get("form_change") != {
        "landmark": "elbow_L",
        "path_index": ELBOW_PATH_INDEX,
        "axis": [0.0, 1.0, 0.0],
        "nominal_bend_plane_radius_m": NOMINAL_ELBOW_RADIUS_M,
        "bend_plane_radius_m": BEND_PLANE_RADIUS_M,
        "joint_axis_width_scale": JOINT_AXIS_WIDTH_SCALE,
    }:
        raise ValueError("source-successor form change drift")
    if profile.get("review_lineage") != {
        "selected_review_candidate_digest": SELECTED_REVIEW_CANDIDATE_DIGEST,
        "selected_review_geometry_digest": SELECTED_REVIEW_GEOMETRY_DIGEST,
    }:
        raise ValueError("source-successor review lineage drift")
    if profile.get("ownership") != {
        "source_owner": "organic-form",
        "source_owned_successor": True,
        "canonical": False,
    }:
        raise ValueError("source-successor ownership drift")


def build_source_owned_elbow_successor(
    spec: dict[str, Any], profile: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the exact selected-003 shape as a non-CANON Organic source successor."""
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    _validate_profile(profile)

    baseline, radius_derivation = _build_exact_candidate(spec)
    if digest(baseline) != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("baseline connected candidate identity drift")
    if tuple(tuple(point) for point in baseline["path_points"]) != tuple(
        tuple(spec["landmarks"][name])
        for name in profile["receiver"]["path_landmarks"]
    ):
        raise ValueError("source-successor path binding drift")
    if int(baseline["segments"]) != 10:
        raise ValueError("source-successor ring segment count drift")
    if abs(float(radius_derivation["radii_m"][ELBOW_PATH_INDEX]) - NOMINAL_ELBOW_RADIUS_M) > 1e-12:
        raise ValueError("source-derived elbow radius drift")

    axis = tuple(float(v) for v in profile["form_change"]["axis"])
    if axis != EXPECTED_AXIS:
        raise ValueError("source-successor axis drift")
    joint_position = tuple(float(v) for v in spec["landmarks"]["elbow_L"])
    ring_start = 1 + ELBOW_PATH_INDEX * int(baseline["segments"])
    ring = list(range(ring_start, ring_start + int(baseline["segments"])))

    candidate = deepcopy(baseline)
    candidate["id"] = SOURCE_SUCCESSOR_CANDIDATE_ID
    before_positions = [tuple(point) for point in baseline["positions"]]
    after_positions = [list(point) for point in baseline["positions"]]
    bend_ratio = BEND_PLANE_RADIUS_M / NOMINAL_ELBOW_RADIUS_M

    for vertex_index in ring:
        point = before_positions[vertex_index]
        relative = _sub(point, joint_position)
        parallel = _mul(axis, _dot(relative, axis))
        perpendicular = _sub(relative, parallel)
        adjusted = _add(
            joint_position,
            _add(
                _mul(parallel, JOINT_AXIS_WIDTH_SCALE),
                _mul(perpendicular, bend_ratio),
            ),
        )
        after_positions[vertex_index] = [round(value, 9) for value in adjusted]

    candidate["positions"] = after_positions
    candidate["organic_source_successor"] = {
        "schema": INSTANCE_SCHEMA,
        "profile_id": PROFILE_ID,
        "profile_digest": PROFILE_DIGEST,
        "base_source_name": "quadruped-neutral-001",
        "base_source_digest": SOURCE_DIGEST,
        "receiver_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "selected_review_candidate_digest": SELECTED_REVIEW_CANDIDATE_DIGEST,
        "selected_review_geometry_digest": SELECTED_REVIEW_GEOMETRY_DIGEST,
        "source_owned_successor": True,
        "canonical": False,
    }
    candidate["truth_boundary"] = dict(candidate["truth_boundary"])
    candidate["truth_boundary"].update({
        "organic_form_source_successor": True,
        "canonical_source_rewritten": False,
        "canon_claimed": False,
        "rigging_accepted": False,
        "animation_accepted": False,
        "runtime_ready": False,
    })

    moved = [
        index
        for index, (before, after) in enumerate(zip(before_positions, after_positions))
        if math.dist(before, after) > 1e-12
    ]
    if moved != ring:
        raise ValueError("source successor moved vertices outside exact elbow ring")
    if baseline["indices"] != candidate["indices"] or baseline["path_points"] != candidate["path_points"]:
        raise ValueError("source successor topology/path drift")
    if baseline["radii"] != candidate["radii"]:
        raise ValueError("source successor silently rewrote receiver nominal radii")

    geometry_digest = _geometry_digest(candidate)
    if geometry_digest != SELECTED_REVIEW_GEOMETRY_DIGEST:
        raise ValueError(f"selected-003 shape equivalence drift: {geometry_digest}")
    observed = digest(candidate)
    if observed != SOURCE_SUCCESSOR_CANDIDATE_DIGEST:
        raise ValueError(f"source successor identity drift: {observed}")

    before_bounds = _bounds(before_positions)
    after_bounds = _bounds([tuple(point) for point in after_positions])
    bounds_delta = [
        [round(after_bounds[axis_index][side] - before_bounds[axis_index][side], 12) for side in range(2)]
        for axis_index in range(3)
    ]
    max_positive_expansion = max(
        max(0.0, value) for axis_delta in bounds_delta for value in axis_delta
    )
    max_neutral_delta = max(
        math.dist(before_positions[index], after_positions[index]) for index in moved
    )
    if max_neutral_delta > MAX_NEUTRAL_VERTEX_DELTA_M + 1e-12:
        raise ValueError("source successor exceeded neutral displacement bound")
    if max_positive_expansion > MAX_POSITIVE_BOUND_EXPANSION_M + 1e-12:
        raise ValueError("source successor exceeded positive bound-expansion limit")

    scope = {
        "moved_vertex_indices": moved,
        "moved_vertex_count": len(moved),
        "maximum_neutral_vertex_delta_m": round(max_neutral_delta, 12),
        "maximum_positive_bound_expansion_m": round(max_positive_expansion, 12),
        "bounds_delta_m": bounds_delta,
        "geometry_digest": geometry_digest,
        "source_successor_candidate_digest": observed,
        "source_owned_successor": True,
        "canonical": False,
    }
    return candidate, scope
