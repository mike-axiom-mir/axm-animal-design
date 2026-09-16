"""Geometry-owned topology rebind for the Organic elbow source successor.

The Organic Form lane owns the successor shape and identity. This module does not
reshape that source. It binds the exact successor to the existing connected-chain
topology contract and reruns receiving-domain topology diagnostics so historical
Geometry evidence is not silently inherited across a new form identity.
"""
from __future__ import annotations

import math
from typing import Any

from .connected_deformation import _build_exact_candidate, digest
from .organic_elbow_source_successor import (
    SELECTED_REVIEW_GEOMETRY_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
    build_source_owned_elbow_successor,
)
from .self_intersection import inspect_triangle_self_intersections
from .topology_study import inspect_vertex_fan_connectivity

RECORD_SCHEMA = "axm.animal-source-successor-topology-rebind/v0.1"
ORGANIC_SOURCE_HEAD = "7314a8971abb53f8ee6ef226c2496ab6d5da20d7"
BASELINE_CONNECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
EXPECTED_MOVED_VERTICES = list(range(11, 21))


def _topology_signature(candidate: dict[str, Any]) -> str:
    """Digest only connectivity/count fields, excluding source-space positions."""
    return digest({
        "indices": candidate["indices"],
        "segments": candidate["segments"],
        "vertex_count": len(candidate["positions"]),
        "triangle_count": len(candidate["indices"]) // 3,
    })


def build_source_successor_topology_rebind(
    spec: dict[str, Any], profile: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind the exact Organic successor to local Geometry topology diagnostics."""
    baseline, _ = _build_exact_candidate(spec)
    if digest(baseline) != BASELINE_CONNECTED_CANDIDATE_DIGEST:
        raise ValueError("connected baseline candidate identity drift")

    successor, source_scope = build_source_owned_elbow_successor(spec, profile)
    if digest(successor) != SOURCE_SUCCESSOR_CANDIDATE_DIGEST:
        raise ValueError("Organic source-successor identity drift")

    unchanged_connectivity = baseline["indices"] == successor["indices"]
    unchanged_path = baseline["path_points"] == successor["path_points"]
    unchanged_nominal_radii = baseline["radii"] == successor["radii"]
    unchanged_segments = baseline["segments"] == successor["segments"]
    unchanged_counts = (
        len(baseline["positions"]) == len(successor["positions"])
        and len(baseline["indices"]) == len(successor["indices"])
    )

    moved_vertices = [
        index
        for index, (before, after) in enumerate(zip(baseline["positions"], successor["positions"]))
        if math.dist(tuple(float(v) for v in before), tuple(float(v) for v in after)) > 1e-12
    ]
    if moved_vertices != EXPECTED_MOVED_VERTICES:
        raise ValueError("Organic successor moved vertices outside exact elbow ring")

    vertex_fans = inspect_vertex_fan_connectivity(successor["positions"], successor["indices"])
    self_intersections = inspect_triangle_self_intersections(successor["positions"], successor["indices"])

    geometry_digest = digest({
        key: successor[key]
        for key in ("positions", "indices", "path_points", "radii", "segments")
    })
    if geometry_digest != SELECTED_REVIEW_GEOMETRY_DIGEST:
        raise ValueError("source-successor geometry identity drift")

    gates = {
        "exact-organic-successor-identity": digest(successor) == SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
        "selected-review-geometry-identity": geometry_digest == SELECTED_REVIEW_GEOMETRY_DIGEST,
        "connectivity-unchanged-from-connected-baseline": unchanged_connectivity,
        "path-unchanged": unchanged_path,
        "nominal-radii-unchanged": unchanged_nominal_radii,
        "segments-unchanged": unchanged_segments,
        "vertex-triangle-counts-unchanged": unchanged_counts,
        "only-elbow-ring-vertices-moved": moved_vertices == EXPECTED_MOVED_VERTICES,
        "one-indexed-fan-per-vertex": vertex_fans["disconnected_vertex_fan_count"] == 0,
        "no-isolated-indexed-vertices": vertex_fans["isolated_vertex_count"] == 0,
        "no-static-nonadjacent-self-intersections": self_intersections["self_intersection_pair_count"] == 0,
    }
    state = (
        "PASS_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND"
        if all(gates.values())
        else "FAIL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND"
    )

    record = {
        "schema": RECORD_SCHEMA,
        "state": state,
        "organic_source_head": ORGANIC_SOURCE_HEAD,
        "baseline_candidate_digest": BASELINE_CONNECTED_CANDIDATE_DIGEST,
        "source_successor_candidate_digest": SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
        "selected_review_geometry_digest": SELECTED_REVIEW_GEOMETRY_DIGEST,
        "baseline_topology_signature": _topology_signature(baseline),
        "successor_topology_signature": _topology_signature(successor),
        "vertex_count": len(successor["positions"]),
        "triangle_count": len(successor["indices"]) // 3,
        "moved_vertex_indices": moved_vertices,
        "source_scope": source_scope,
        "vertex_fans": vertex_fans,
        "static_self_intersections": self_intersections,
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
        "truth_boundary": {
            "organic_source_shape_modified": False,
            "historical_geometry_pass_silently_inherited": False,
            "connectivity_retested_locally": True,
            "indexed_vertex_fans_retested_locally": True,
            "static_nonadjacent_self_intersections_retested_locally": True,
            "uc_edge_topology_retested_here": False,
            "deformation_retested": False,
            "visual_quality_retested": False,
            "continuous_motion_checked": False,
            "runtime_or_gameplay_checked": False,
            "canon_claimed": False,
        },
    }
    return successor, record
