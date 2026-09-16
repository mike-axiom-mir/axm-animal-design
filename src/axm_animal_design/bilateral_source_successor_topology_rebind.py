"""Geometry-owned topology rebind for the bilateral Organic elbow successors.

Organic Form owns both successor shapes and their non-CANON source identities.
This module does not reshape either source. It rebuilds the exact left/right
connected baselines, consumes the exact bilateral Organic successor, and reruns
receiving-domain topology diagnostics so the historical left Geometry PASS is
not silently inherited by symmetry onto the new right source identity.
"""
from __future__ import annotations

import math
from typing import Any

from .connected_deformation import _build_exact_candidate, digest
from .organic_elbow_bilateral_successor import (
    RIGHT_BASELINE_DIGEST,
    RIGHT_BASELINE_ID,
    RIGHT_CHAIN_REGIONS,
    RIGHT_PATH,
    RIGHT_SUCCESSOR_DIGEST,
    RIGHT_SUCCESSOR_ID,
    build_bilateral_elbow_source_successor,
)
from .organic_elbow_source_successor import (
    BASELINE_CANDIDATE_DIGEST as LEFT_BASELINE_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST as LEFT_SUCCESSOR_DIGEST,
)
from .self_intersection import inspect_triangle_self_intersections
from .topology_study import (
    build_connected_chain,
    derive_shared_ring_radii,
    inspect_vertex_fan_connectivity,
)

RECORD_SCHEMA = "axm.animal-bilateral-source-successor-topology-rebind/v0.1"
ORGANIC_BILATERAL_HEAD = "4df3024b4c459675422565501a46f622acf229a9"
HISTORICAL_LEFT_GEOMETRY_HEAD = "eb5ce99798b646b6ab9705c0c914b898173f7cc1"
EXPECTED_MOVED_VERTICES = list(range(11, 21))


def _topology_signature(candidate: dict[str, Any]) -> str:
    """Digest connectivity/count fields only, excluding source-space positions."""
    return digest({
        "indices": candidate["indices"],
        "segments": candidate["segments"],
        "vertex_count": len(candidate["positions"]),
        "triangle_count": len(candidate["indices"]) // 3,
    })


def _moved_vertices(before: dict[str, Any], after: dict[str, Any]) -> list[int]:
    return [
        index
        for index, (left, right) in enumerate(zip(before["positions"], after["positions"]))
        if math.dist(tuple(float(v) for v in left), tuple(float(v) for v in right)) > 1e-12
    ]


def _build_right_baseline(spec: dict[str, Any]) -> dict[str, Any]:
    derived = derive_shared_ring_radii(spec["regions"], RIGHT_CHAIN_REGIONS)
    if tuple(derived["path_landmarks"]) != RIGHT_PATH:
        raise ValueError("right connected source path drift")
    candidate = build_connected_chain(
        RIGHT_BASELINE_ID,
        [spec["landmarks"][name] for name in RIGHT_PATH],
        derived["radii_m"],
        segments=10,
    )
    if digest(candidate) != RIGHT_BASELINE_DIGEST:
        raise ValueError("right connected baseline identity drift")
    return candidate


def _inspect_side(
    side: str,
    baseline: dict[str, Any],
    successor: dict[str, Any],
    expected_successor_digest: str,
) -> dict[str, Any]:
    if digest(successor) != expected_successor_digest:
        raise ValueError(f"{side} source-successor identity drift")

    moved = _moved_vertices(baseline, successor)
    if moved != EXPECTED_MOVED_VERTICES:
        raise ValueError(f"{side} successor moved vertices outside exact elbow ring")

    fans = inspect_vertex_fan_connectivity(successor["positions"], successor["indices"])
    self_intersections = inspect_triangle_self_intersections(
        successor["positions"], successor["indices"]
    )

    baseline_signature = _topology_signature(baseline)
    successor_signature = _topology_signature(successor)
    gates = {
        "connectivity-unchanged-from-side-baseline": baseline["indices"] == successor["indices"],
        "path-unchanged": baseline["path_points"] == successor["path_points"],
        "nominal-radii-unchanged": baseline["radii"] == successor["radii"],
        "segments-unchanged": baseline["segments"] == successor["segments"],
        "vertex-triangle-counts-unchanged": (
            len(baseline["positions"]) == len(successor["positions"])
            and len(baseline["indices"]) == len(successor["indices"])
        ),
        "only-elbow-ring-vertices-moved": moved == EXPECTED_MOVED_VERTICES,
        "topology-signature-unchanged": baseline_signature == successor_signature,
        "one-indexed-fan-per-vertex": fans["disconnected_vertex_fan_count"] == 0,
        "no-isolated-indexed-vertices": fans["isolated_vertex_count"] == 0,
        "no-static-nonadjacent-self-intersections": self_intersections["self_intersection_pair_count"] == 0,
    }

    return {
        "side": side,
        "state": "PASS_SIDE_LOCAL_TOPOLOGY_REBIND" if all(gates.values()) else "FAIL_SIDE_LOCAL_TOPOLOGY_REBIND",
        "baseline_candidate_id": baseline["id"],
        "successor_candidate_id": successor["id"],
        "baseline_candidate_digest": digest(baseline),
        "successor_candidate_digest": digest(successor),
        "baseline_topology_signature": baseline_signature,
        "successor_topology_signature": successor_signature,
        "vertex_count": len(successor["positions"]),
        "triangle_count": len(successor["indices"]) // 3,
        "moved_vertex_indices": moved,
        "vertex_fans": fans,
        "static_self_intersections": self_intersections,
        "gates": {name: "PASS" if passed else "FAIL" for name, passed in gates.items()},
    }


def build_bilateral_source_successor_topology_rebind(
    spec: dict[str, Any],
    left_profile: dict[str, Any],
    bilateral_profile: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Rebind exact left/right Organic source successors to Geometry diagnostics."""
    left_baseline, _ = _build_exact_candidate(spec)
    if digest(left_baseline) != LEFT_BASELINE_DIGEST:
        raise ValueError("left connected baseline identity drift")
    right_baseline = _build_right_baseline(spec)

    left_successor, right_successor, organic_scope = build_bilateral_elbow_source_successor(
        spec, left_profile, bilateral_profile
    )
    if digest(left_successor) != LEFT_SUCCESSOR_DIGEST:
        raise ValueError("left source-successor identity drift after bilateral build")
    if digest(right_successor) != RIGHT_SUCCESSOR_DIGEST:
        raise ValueError("right source-successor identity drift after bilateral build")

    left = _inspect_side("left", left_baseline, left_successor, LEFT_SUCCESSOR_DIGEST)
    right = _inspect_side("right", right_baseline, right_successor, RIGHT_SUCCESSOR_DIGEST)

    bilateral_gates = {
        "organic-bilateral-source-pass": organic_scope["result"] == "PASS_BILATERAL_SOURCE_PROPAGATION_EXACT_MIRROR",
        "left-local-topology-pass": left["state"] == "PASS_SIDE_LOCAL_TOPOLOGY_REBIND",
        "right-local-topology-pass": right["state"] == "PASS_SIDE_LOCAL_TOPOLOGY_REBIND",
        "left-right-topology-signature-match": left["successor_topology_signature"] == right["successor_topology_signature"],
        "exact-mirror-position-residual-zero": organic_scope["mirror"]["maximum_position_residual_m"] == 0.0,
        "exact-mirror-path-residual-zero": organic_scope["mirror"]["maximum_path_residual_m"] == 0.0,
    }
    state = (
        "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND"
        if all(bilateral_gates.values())
        else "FAIL_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND"
    )

    record = {
        "schema": RECORD_SCHEMA,
        "state": state,
        "organic_bilateral_head": ORGANIC_BILATERAL_HEAD,
        "historical_left_geometry_head": HISTORICAL_LEFT_GEOMETRY_HEAD,
        "organic_scope": organic_scope,
        "left": left,
        "right": right,
        "bilateral_gates": {
            name: "PASS" if passed else "FAIL" for name, passed in bilateral_gates.items()
        },
        "truth_boundary": {
            "organic_source_shape_modified": False,
            "historical_left_geometry_pass_silently_inherited": False,
            "right_geometry_pass_inferred_from_symmetry": False,
            "both_sides_retested_locally": True,
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
    return left_successor, right_successor, record
