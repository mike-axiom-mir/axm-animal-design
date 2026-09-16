"""Geometry-only repair for the bilateral Animal elbow surface correspondence hold.

Rigging proved exact mirrored posed vertices for the current bilateral Organic
successors while triangulated deformation extrema remained non-mirrored.  This
module preserves every source-owned vertex position and changes only the right
triangle connectivity so each right face is the orientation-correct reflected
counterpart of one left face under the exact Organic mirror correspondence.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .bilateral_source_successor_rigging_rebind import (
    BASELINE_WEIGHTING,
    CANDIDATE_WEIGHTING,
    MIRROR_TOLERANCE,
    _bilateral_comparison,
    _probe_side,
)
from .bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from .connected_deformation import digest
from .organic_elbow_bilateral_successor import RING_SEGMENT_MAP
from .self_intersection import inspect_triangle_self_intersections
from .topology_study import inspect_vertex_fan_connectivity

RECORD_SCHEMA = "axm.animal-bilateral-mirror-surface-topology/v0.1"
CANDIDATE_ID = "front-right-connected-chain-elbow-source-successor-003-mirror-surface-topology-001"
RIGGING_BILATERAL_HEAD = "94bc573e2e06ba7a35c9908c141e2f939d4739a8"
GEOMETRY_BILATERAL_HEAD = "f89af95d621c36da3994c6660552da8bbc73fd1b"
ORGANIC_BILATERAL_HEAD = "4df3024b4c459675422565501a46f622acf229a9"


def _vertex_map(candidate: dict[str, Any]) -> dict[int, int]:
    segments = int(candidate["segments"])
    path_count = len(candidate["path_points"])
    if segments != 10 or path_count != 4 or len(candidate["positions"]) != 42:
        raise ValueError("exact bilateral mirror topology requires the 42-vertex 10-segment receiver")
    mapping = {0: 0, len(candidate["positions"]) - 1: len(candidate["positions"]) - 1}
    for ring_index in range(path_count):
        start = 1 + ring_index * segments
        for left_segment, right_segment in enumerate(RING_SEGMENT_MAP):
            mapping[start + left_segment] = start + right_segment
    if len(mapping) != len(candidate["positions"]):
        raise ValueError("bilateral mirror vertex mapping is incomplete")
    return mapping


def _triangles(indices: list[int]) -> list[tuple[int, int, int]]:
    if len(indices) % 3:
        raise ValueError("triangle index list is incomplete")
    return [tuple(indices[offset:offset + 3]) for offset in range(0, len(indices), 3)]


def exact_mirrored_right_indices(left_candidate: dict[str, Any]) -> list[int]:
    """Reflect left faces to right correspondence and reverse winding.

    Reflection across Y=0 changes handedness, so reversing each mapped triangle
    restores the original outward orientation convention on the right surface.
    """
    mapping = _vertex_map(left_candidate)
    output: list[int] = []
    for a, b, c in _triangles(list(left_candidate["indices"])):
        output.extend((mapping[a], mapping[c], mapping[b]))
    return output


def _face_correspondence(left_candidate: dict[str, Any], right_candidate: dict[str, Any]) -> dict[str, Any]:
    expected = exact_mirrored_right_indices(left_candidate)
    observed = list(right_candidate["indices"])
    expected_faces = _triangles(expected)
    observed_faces = _triangles(observed)
    exact_records = sum(1 for left, right in zip(expected_faces, observed_faces) if left == right)
    exact_unoriented_sets = sum(
        1 for left, right in zip(expected_faces, observed_faces) if frozenset(left) == frozenset(right)
    )
    return {
        "triangle_count": len(expected_faces),
        "exact_triangle_record_matches": exact_records,
        "exact_unoriented_triangle_matches": exact_unoriented_sets,
        "all_exact": observed == expected,
    }


def derive_exact_mirror_surface_candidate(
    left_candidate: dict[str, Any], right_source_candidate: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a rollbackable right topology successor with unchanged positions."""
    before_positions = deepcopy(right_source_candidate["positions"])
    before_indices = list(right_source_candidate["indices"])
    candidate = deepcopy(right_source_candidate)
    candidate["id"] = CANDIDATE_ID
    candidate["indices"] = exact_mirrored_right_indices(left_candidate)
    candidate["geometry_mirror_surface_topology"] = {
        "schema": RECORD_SCHEMA,
        "source_candidate_id": right_source_candidate["id"],
        "source_candidate_digest": digest(right_source_candidate),
        "rigging_hold_head": RIGGING_BILATERAL_HEAD,
        "mirror_plane": "Y=0",
        "positions_modified": False,
        "indices_modified": True,
        "canonical": False,
    }
    candidate["truth_boundary"] = dict(candidate["truth_boundary"])
    candidate["truth_boundary"].update({
        "geometry_exact_mirror_surface_candidate": True,
        "organic_source_rewritten": False,
        "rigging_accepted_for_this_topology": False,
        "visual_quality_checked": False,
        "canon_claimed": False,
    })

    before_faces = _triangles(before_indices)
    after_faces = _triangles(candidate["indices"])
    before_sets = {frozenset(face) for face in before_faces}
    after_sets = {frozenset(face) for face in after_faces}
    common_sets = len(before_sets & after_sets)
    longitudinal_quads = (len(candidate["path_points"]) - 1) * int(candidate["segments"])

    fans = inspect_vertex_fan_connectivity(candidate["positions"], candidate["indices"])
    intersections = inspect_triangle_self_intersections(candidate["positions"], candidate["indices"])
    correspondence = _face_correspondence(left_candidate, candidate)
    gates = {
        "positions-byte-semantics-unchanged": candidate["positions"] == before_positions,
        "path-unchanged": candidate["path_points"] == right_source_candidate["path_points"],
        "radii-unchanged": candidate["radii"] == right_source_candidate["radii"],
        "segments-unchanged": candidate["segments"] == right_source_candidate["segments"],
        "vertex-count-unchanged": len(candidate["positions"]) == len(right_source_candidate["positions"]),
        "triangle-count-unchanged": len(candidate["indices"]) == len(before_indices),
        "exact-mirrored-face-correspondence": correspondence["all_exact"],
        "one-indexed-fan-per-vertex": fans["disconnected_vertex_fan_count"] == 0,
        "no-isolated-indexed-vertices": fans["isolated_vertex_count"] == 0,
        "no-static-nonadjacent-self-intersections": intersections["self_intersection_pair_count"] == 0,
    }
    return candidate, {
        "state": "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE" if all(gates.values()) else "FAIL_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE",
        "source_right_candidate_digest": digest(right_source_candidate),
        "candidate_digest": digest(candidate),
        "vertex_count": len(candidate["positions"]),
        "triangle_count": len(candidate["indices"]) // 3,
        "longitudinal_quad_count": longitudinal_quads,
        "unchanged_unoriented_triangle_sets": common_sets,
        "replaced_unoriented_triangle_sets": len(before_sets) - common_sets,
        "face_correspondence": correspondence,
        "vertex_fans": fans,
        "static_self_intersections": intersections,
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
    }


def inspect_exact_mirror_surface_repair(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
    plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Measure before/after bilateral surface-metric equivalence with the exact rig."""
    left_source, right_source, prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    if prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise ValueError("bilateral Geometry prerequisite is not PASS")

    baseline_face_correspondence = _face_correspondence(left_source, right_source)
    candidate, topology = derive_exact_mirror_surface_candidate(left_source, right_source)
    if topology["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise ValueError("exact mirror surface candidate failed local Geometry gates")

    comparisons = {}
    for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
        left_probe = _probe_side(left_source, spec, plan, "left", weighting)
        before_probe = _probe_side(right_source, spec, plan, "right", weighting)
        after_probe = _probe_side(candidate, spec, plan, "right", weighting)
        before = _bilateral_comparison(left_probe, before_probe, left_source)
        after = _bilateral_comparison(left_probe, after_probe, left_source)
        comparisons[weighting] = {
            "before": before,
            "after": after,
            "metric_residual_reduction": (
                before["maximum_structural_metric_residual"] - after["maximum_structural_metric_residual"]
            ),
        }

    gates = {
        "historical-right-face-correspondence-is-not-exact": not baseline_face_correspondence["all_exact"],
        "candidate-face-correspondence-is-exact": topology["face_correspondence"]["all_exact"],
        "baseline-weighting-exact-surface-mirror": comparisons[BASELINE_WEIGHTING]["after"]["gate"] == "PASS_DENSE_BILATERAL_MIRROR_DEFORMATION_EQUIVALENCE",
        "refined-weighting-exact-surface-mirror": comparisons[CANDIDATE_WEIGHTING]["after"]["gate"] == "PASS_DENSE_BILATERAL_MIRROR_DEFORMATION_EQUIVALENCE",
        "baseline-weighting-metric-residual-within-tolerance": comparisons[BASELINE_WEIGHTING]["after"]["maximum_structural_metric_residual"] <= MIRROR_TOLERANCE,
        "refined-weighting-metric-residual-within-tolerance": comparisons[CANDIDATE_WEIGHTING]["after"]["maximum_structural_metric_residual"] <= MIRROR_TOLERANCE,
    }
    record = {
        "schema": RECORD_SCHEMA,
        "state": "PASS_BILATERAL_EXACT_MIRROR_SURFACE_TOPOLOGY_REPAIR" if all(gates.values()) else "FAIL_BILATERAL_EXACT_MIRROR_SURFACE_TOPOLOGY_REPAIR",
        "organic_bilateral_head": ORGANIC_BILATERAL_HEAD,
        "geometry_bilateral_head": GEOMETRY_BILATERAL_HEAD,
        "rigging_bilateral_head": RIGGING_BILATERAL_HEAD,
        "historical_right_face_correspondence": baseline_face_correspondence,
        "candidate_topology": topology,
        "deformation_comparisons": comparisons,
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
        "truth_boundary": {
            "organic_source_positions_modified": False,
            "right_triangle_connectivity_modified": True,
            "rig_plan_modified": False,
            "weighting_modified": False,
            "visual_quality_checked": False,
            "continuous_motion_proved": False,
            "runtime_or_gameplay_checked": False,
            "canon_claimed": False,
        },
    }
    return left_source, candidate, record
