"""Bilateral Organic Form successor derived from the selected Animal elbow source shape.

This module preserves the exact reviewed/source-owned left selected-003 elbow and
propagates only its mirrored form parameters to the source-symmetric right elbow.
It is a non-CANON Organic source candidate only. Geometry, Rigging, Animation,
runtime, biology/anatomy and final visual acceptance remain separate gates.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .connected_deformation import digest
from .organic_elbow_source_successor import (
    PROFILE_DIGEST as LEFT_PROFILE_DIGEST,
    PROFILE_ID as LEFT_PROFILE_ID,
    SELECTED_REVIEW_GEOMETRY_DIGEST as LEFT_GEOMETRY_DIGEST,
    SOURCE_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST as LEFT_CANDIDATE_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_ID as LEFT_CANDIDATE_ID,
    build_source_owned_elbow_successor,
)
from .topology_study import build_connected_chain, derive_shared_ring_radii

PROFILE_SCHEMA = "axm.animal-organic-bilateral-form-successor/v0.1"
INSTANCE_SCHEMA = "axm.animal-organic-bilateral-form-successor-instance/v0.1"
PROFILE_ID = "quadruped-front-elbow-bilateral-form-successor-003"
PROFILE_DIGEST = "565b65aa44e4759c2f08f9e7cf4b0650b646700773735aa0351e803fbd0d30d4"
RIGHT_BASELINE_ID = "front-right-connected-chain-001"
RIGHT_BASELINE_DIGEST = "d26650fd9b27e8f90cace24ab1f96f2988eb05c05a88bd9994dffe5c2b8d8901"
RIGHT_SUCCESSOR_ID = "front-right-connected-chain-elbow-source-successor-003"
RIGHT_SUCCESSOR_DIGEST = "262f536e0e522fd3e102cb16464c3757985fbb1dfcb3001df3b1f27b623b0115"
RIGHT_GEOMETRY_DIGEST = "ebf3fa17555f302f678cadd7a3157b17425d23b93b6cd60315e5c8ca9f6d3372"
RIGHT_CHAIN_REGIONS = ("front_upper_R", "front_lower_R", "front_paw_R")
RIGHT_PATH = ("shoulder_R", "elbow_R", "wrist_R", "front_paw_R")
ELBOW_PATH_INDEX = 1
NOMINAL_ELBOW_RADIUS_M = 0.09
BEND_PLANE_RADIUS_M = 0.0885
JOINT_AXIS_WIDTH_SCALE = 1.03
RIGHT_AXIS = (0.0, -1.0, 0.0)
RING_SEGMENT_MAP = (0, 9, 8, 7, 6, 5, 4, 3, 2, 1)
MAX_NEUTRAL_VERTEX_DELTA_M = 0.0028
MAX_OUTWARD_BOUND_EXPANSION_M = 0.003


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
        raise ValueError("bilateral source-successor profile schema mismatch")
    if digest(profile) != PROFILE_DIGEST:
        raise ValueError("bilateral source-successor profile identity drift")
    if profile.get("id") != PROFILE_ID:
        raise ValueError("bilateral source-successor profile id drift")
    if profile.get("base_source") != {
        "name": "quadruped-neutral-001",
        "digest": SOURCE_DIGEST,
    }:
        raise ValueError("bilateral source-successor base source binding drift")
    if profile.get("left_successor") != {
        "profile_id": LEFT_PROFILE_ID,
        "profile_digest": LEFT_PROFILE_DIGEST,
        "candidate_id": LEFT_CANDIDATE_ID,
        "candidate_digest": LEFT_CANDIDATE_DIGEST,
        "geometry_digest": LEFT_GEOMETRY_DIGEST,
    }:
        raise ValueError("bilateral source-successor left dependency drift")
    if profile.get("right_receiver") != {
        "candidate_id": RIGHT_BASELINE_ID,
        "candidate_digest": RIGHT_BASELINE_DIGEST,
        "path_landmarks": list(RIGHT_PATH),
        "segments": 10,
    }:
        raise ValueError("bilateral source-successor right receiver drift")
    if profile.get("right_form_change") != {
        "landmark": "elbow_R",
        "path_index": ELBOW_PATH_INDEX,
        "axis": list(RIGHT_AXIS),
        "nominal_bend_plane_radius_m": NOMINAL_ELBOW_RADIUS_M,
        "bend_plane_radius_m": BEND_PLANE_RADIUS_M,
        "joint_axis_width_scale": JOINT_AXIS_WIDTH_SCALE,
    }:
        raise ValueError("bilateral source-successor right form change drift")
    if profile.get("mirror_contract") != {
        "plane": "Y=0",
        "landmark_pairs": [
            ["shoulder_L", "shoulder_R"],
            ["elbow_L", "elbow_R"],
            ["wrist_L", "wrist_R"],
            ["front_paw_L", "front_paw_R"],
        ],
        "ring_segment_map": list(RING_SEGMENT_MAP),
        "maximum_position_residual_m": 0.0,
    }:
        raise ValueError("bilateral source-successor mirror contract drift")
    if profile.get("ownership") != {
        "source_owner": "organic-form",
        "source_owned_successor": True,
        "canonical": False,
    }:
        raise ValueError("bilateral source-successor ownership drift")


def _build_right_baseline(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    derived = derive_shared_ring_radii(spec["regions"], RIGHT_CHAIN_REGIONS)
    if tuple(derived["path_landmarks"]) != RIGHT_PATH:
        raise ValueError("right source chain no longer resolves expected forelimb path")
    candidate = build_connected_chain(
        RIGHT_BASELINE_ID,
        [spec["landmarks"][name] for name in RIGHT_PATH],
        derived["radii_m"],
        segments=10,
    )
    observed = digest(candidate)
    if observed != RIGHT_BASELINE_DIGEST:
        raise ValueError(f"right baseline connected candidate identity drift: {observed}")
    return candidate, derived


def _mirror_correspondence(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    segments = int(right["segments"])
    if segments != 10 or int(left["segments"]) != segments:
        raise ValueError("bilateral mirror contract requires exact 10-segment receivers")
    if left["radii"] != right["radii"]:
        raise ValueError("bilateral receiver radii drift")
    left_path = [tuple(point) for point in left["path_points"]]
    right_path = [tuple(point) for point in right["path_points"]]
    if len(left_path) != len(right_path):
        raise ValueError("bilateral path count drift")
    path_residuals = [
        math.dist((point[0], -point[1], point[2]), right_path[index])
        for index, point in enumerate(left_path)
    ]

    residuals = [
        math.dist(
            (left["positions"][0][0], -left["positions"][0][1], left["positions"][0][2]),
            right["positions"][0],
        ),
        math.dist(
            (left["positions"][-1][0], -left["positions"][-1][1], left["positions"][-1][2]),
            right["positions"][-1],
        ),
    ]
    mapping = []
    ring_count = len(left_path)
    for ring_index in range(ring_count):
        left_start = 1 + ring_index * segments
        right_start = 1 + ring_index * segments
        for left_segment, right_segment in enumerate(RING_SEGMENT_MAP):
            left_index = left_start + left_segment
            right_index = right_start + right_segment
            left_point = left["positions"][left_index]
            right_point = right["positions"][right_index]
            residuals.append(
                math.dist((left_point[0], -left_point[1], left_point[2]), right_point)
            )
            mapping.append([left_index, right_index])

    max_path = max(path_residuals, default=0.0)
    max_position = max(residuals, default=0.0)
    if max_path > 1e-12 or max_position > 1e-12:
        raise ValueError(
            f"bilateral mirror residual drift: path={max_path}, positions={max_position}"
        )
    return {
        "plane": "Y=0",
        "maximum_path_residual_m": round(max_path, 12),
        "maximum_position_residual_m": round(max_position, 12),
        "ring_segment_map": list(RING_SEGMENT_MAP),
        "vertex_correspondence_count": len(mapping) + 2,
        "ring_vertex_correspondence": mapping,
    }


def build_bilateral_elbow_source_successor(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Return exact left selected-003 plus a mirrored right Organic source candidate."""
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    _validate_profile(bilateral_profile)

    left_candidate, _left_scope = build_source_owned_elbow_successor(spec, left_profile)
    if digest(left_candidate) != LEFT_CANDIDATE_DIGEST:
        raise ValueError("left source-successor identity drift")

    right_baseline, right_radius_derivation = _build_right_baseline(spec)
    if abs(float(right_radius_derivation["radii_m"][ELBOW_PATH_INDEX]) - NOMINAL_ELBOW_RADIUS_M) > 1e-12:
        raise ValueError("source-derived right elbow radius drift")

    joint_position = tuple(float(v) for v in spec["landmarks"]["elbow_R"])
    segments = int(right_baseline["segments"])
    ring_start = 1 + ELBOW_PATH_INDEX * segments
    ring = list(range(ring_start, ring_start + segments))
    before_positions = [tuple(point) for point in right_baseline["positions"]]
    after_positions = [list(point) for point in right_baseline["positions"]]
    bend_ratio = BEND_PLANE_RADIUS_M / NOMINAL_ELBOW_RADIUS_M

    for vertex_index in ring:
        point = before_positions[vertex_index]
        relative = _sub(point, joint_position)
        parallel = _mul(RIGHT_AXIS, _dot(relative, RIGHT_AXIS))
        perpendicular = _sub(relative, parallel)
        adjusted = _add(
            joint_position,
            _add(
                _mul(parallel, JOINT_AXIS_WIDTH_SCALE),
                _mul(perpendicular, bend_ratio),
            ),
        )
        after_positions[vertex_index] = [round(value, 9) for value in adjusted]

    right_candidate = deepcopy(right_baseline)
    right_candidate["id"] = RIGHT_SUCCESSOR_ID
    right_candidate["positions"] = after_positions
    right_candidate["organic_bilateral_source_successor"] = {
        "schema": INSTANCE_SCHEMA,
        "profile_id": PROFILE_ID,
        "profile_digest": PROFILE_DIGEST,
        "base_source_name": "quadruped-neutral-001",
        "base_source_digest": SOURCE_DIGEST,
        "left_source_successor_profile_id": LEFT_PROFILE_ID,
        "left_source_successor_profile_digest": LEFT_PROFILE_DIGEST,
        "left_source_successor_candidate_digest": LEFT_CANDIDATE_DIGEST,
        "mirrored_left_geometry_digest": LEFT_GEOMETRY_DIGEST,
        "mirror_plane": "Y=0",
        "source_owned_successor": True,
        "canonical": False,
    }
    right_candidate["truth_boundary"] = dict(right_candidate["truth_boundary"])
    right_candidate["truth_boundary"].update({
        "organic_form_bilateral_source_successor": True,
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
        raise ValueError("right source successor moved vertices outside exact elbow ring")
    if right_baseline["indices"] != right_candidate["indices"]:
        raise ValueError("right source successor topology drift")
    if right_baseline["path_points"] != right_candidate["path_points"]:
        raise ValueError("right source successor path drift")
    if right_baseline["radii"] != right_candidate["radii"]:
        raise ValueError("right source successor silently rewrote receiver nominal radii")

    right_geometry_digest = _geometry_digest(right_candidate)
    if right_geometry_digest != RIGHT_GEOMETRY_DIGEST:
        raise ValueError(f"right successor geometry identity drift: {right_geometry_digest}")
    observed = digest(right_candidate)
    if observed != RIGHT_SUCCESSOR_DIGEST:
        raise ValueError(f"right source successor identity drift: {observed}")

    mirror = _mirror_correspondence(left_candidate, right_candidate)

    before_bounds = _bounds(before_positions)
    after_bounds = _bounds([tuple(point) for point in after_positions])
    bounds_delta = [
        [round(after_bounds[axis][side] - before_bounds[axis][side], 12) for side in range(2)]
        for axis in range(3)
    ]
    outward_expansions = []
    for axis in range(3):
        outward_expansions.append(max(0.0, before_bounds[axis][0] - after_bounds[axis][0]))
        outward_expansions.append(max(0.0, after_bounds[axis][1] - before_bounds[axis][1]))
    max_outward_expansion = max(outward_expansions)
    max_neutral_delta = max(
        math.dist(before_positions[index], after_positions[index]) for index in moved
    )
    if max_neutral_delta > MAX_NEUTRAL_VERTEX_DELTA_M + 1e-12:
        raise ValueError("right source successor exceeded neutral displacement bound")
    if max_outward_expansion > MAX_OUTWARD_BOUND_EXPANSION_M + 1e-12:
        raise ValueError("right source successor exceeded outward bound-expansion limit")

    scope = {
        "result": "PASS_BILATERAL_SOURCE_PROPAGATION_EXACT_MIRROR",
        "adoption_boundary": "RIGHT_SOURCE_OWNED_SUCCESSOR_NOT_CANON__GEOMETRY_RIGGING_VISUAL_HELD",
        "left_source_successor_candidate_digest": LEFT_CANDIDATE_DIGEST,
        "right_source_successor_candidate_digest": observed,
        "right_geometry_digest": right_geometry_digest,
        "right_moved_vertex_indices": moved,
        "right_moved_vertex_count": len(moved),
        "right_maximum_neutral_vertex_delta_m": round(max_neutral_delta, 12),
        "right_maximum_outward_bound_expansion_m": round(max_outward_expansion, 12),
        "right_bounds_delta_m": bounds_delta,
        "mirror": mirror,
        "source_owned_successor": True,
        "canonical": False,
    }
    return left_candidate, right_candidate, scope
