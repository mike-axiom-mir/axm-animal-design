#!/usr/bin/env python3
"""Build bounded geometric self-intersection evidence for the exact Geometry candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from axm_animal_design.self_intersection import inspect_triangle_self_intersections
from axm_animal_design.topology_study import build_connected_chain, derive_shared_ring_radii

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "quadruped_neutral_001.json"
OUT = ROOT / "evidence" / "topology-self-intersection"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def main() -> None:
    spec = json.loads(SOURCE.read_text())
    region_ids = ("front_upper_L", "front_lower_L", "front_paw_L")
    derivation = derive_shared_ring_radii(spec["regions"], region_ids)
    candidate = build_connected_chain(
        "front-left-connected-chain-001",
        [spec["landmarks"][name] for name in derivation["path_landmarks"]],
        derivation["radii_m"],
        segments=10,
    )
    candidate_digest = digest(candidate)
    report = inspect_triangle_self_intersections(candidate["positions"], candidate["indices"])

    negative_positions = [
        [0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 2.0, 0.0],
        [0.5, 0.5, -1.0], [0.5, 0.5, 1.0], [1.5, 0.5, 0.0],
    ]
    negative = inspect_triangle_self_intersections(negative_positions, [0, 1, 2, 3, 4, 5])

    gates = {
        "candidate-identity-unchanged": "PASS" if candidate_digest == EXPECTED_CANDIDATE_DIGEST else "FAIL",
        "candidate-no-nonadjacent-self-intersections": (
            "PASS" if report["self_intersection_pair_count"] == 0 else "FAIL"
        ),
        "crossing-triangle-negative-control-detected": (
            "PASS" if negative["self_intersection_pair_count"] == 1 else "FAIL"
        ),
    }
    status = "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"
    receipt = {
        "schema": "axm.animal-connected-chain-self-intersection-evidence/v0.1",
        "status": status,
        "candidate": "front-left-connected-chain-001",
        "candidate_digest": candidate_digest,
        "expected_candidate_digest": EXPECTED_CANDIDATE_DIGEST,
        "source_name": spec["name"],
        "source_region_ids": list(region_ids),
        "landmarks": derivation["path_landmarks"],
        "radii_m": derivation["radii_m"],
        "segments": candidate["segments"],
        "inspection": report,
        "negative_control": negative,
        "gates": gates,
        "truth_boundary": {
            "exact_static_candidate_self_intersection_checked": True,
            "candidate_geometry_modified": False,
            "continuous_deformation_self_intersection_checked": False,
            "visual_quality_checked": False,
            "rig_or_weighting_checked": False,
            "collision_or_gameplay_checked": False,
            "runtime_or_performance_checked": False,
            "game_ready": False,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "front_left_connected_chain_self_intersection_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    if status != "PASS":
        raise SystemExit("self-intersection evidence gates failed")
    print(json.dumps({
        "status": status,
        "candidate_digest": candidate_digest,
        "triangle_count": report["triangle_count"],
        "triangle_pair_count": report["triangle_pair_count"],
        "skipped_topological_neighbor_pairs": report["skipped_topological_neighbor_pairs"],
        "broad_phase_candidate_pairs": report["broad_phase_candidate_pairs"],
        "self_intersection_pair_count": report["self_intersection_pair_count"],
        "negative_control_intersections": negative["self_intersection_pair_count"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
