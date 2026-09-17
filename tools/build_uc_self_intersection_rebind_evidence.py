#!/usr/bin/env python3
"""Rebind the exact Animal Geometry candidate to the merged UC self-intersection observer.

This preserves the historical Animal-local receipt and proves only the overlapping
read-only observation on the exact same candidate. It does not retire the local
observer or authorize mesh repair/adoption.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from axm_animal_design.self_intersection import (
    inspect_triangle_self_intersections as inspect_local_self_intersections,
)
from axm_animal_design.topology_study import build_connected_chain, derive_shared_ring_radii
from axm_uc.mesh_self_intersection import (
    DEFAULT_MAX_TRIANGLE_PAIR_CHECKS,
    inspect_triangle_self_intersections as inspect_uc_self_intersections,
)

ROOT = Path(__file__).resolve().parents[1]
UC_ROOT = ROOT.parent / "uc"
SOURCE = ROOT / "examples" / "quadruped_neutral_001.json"
OUT = ROOT / "evidence" / "topology-self-intersection"

UC_REPOSITORY = "mike-axiom-mir/axm-universal-creation"
UC_COMMIT = "41b4d9134e4d2e5f4fadaada2a1d6a56eed92ab0"
UC_MODULE = "src/axm_uc/mesh_self_intersection.py"
UC_MODULE_BLOB = "2de80eada941de54a067b551e51b75a9bde0500b"
EXPECTED_CANDIDATE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
EPSILON = 1e-9


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(UC_ROOT), *args], text=True).strip()


def crossing_control() -> tuple[list[list[float]], list[int]]:
    return (
        [
            [0.0, 0.0, 0.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [0.5, 0.5, -1.0],
            [0.5, 0.5, 1.0],
            [1.5, 0.5, 0.0],
        ],
        [0, 1, 2, 3, 4, 5],
    )


def main() -> None:
    actual_uc_commit = git("rev-parse", "HEAD")
    actual_uc_blob = git("rev-parse", f"HEAD:{UC_MODULE}")

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

    local_report = inspect_local_self_intersections(
        candidate["positions"], candidate["indices"], epsilon=EPSILON
    )
    uc_report = inspect_uc_self_intersections(
        candidate["positions"], candidate["indices"], epsilon=EPSILON
    )

    negative_positions, negative_indices = crossing_control()
    local_negative = inspect_local_self_intersections(
        negative_positions, negative_indices, epsilon=EPSILON
    )
    uc_negative = inspect_uc_self_intersections(
        negative_positions, negative_indices, epsilon=EPSILON
    )

    required_pairs = len(candidate["indices"]) // 3
    required_pairs = required_pairs * (required_pairs - 1) // 2
    if required_pairs <= 1:
        raise AssertionError("candidate must exercise a non-trivial pair budget")
    uc_budget_hold = inspect_uc_self_intersections(
        candidate["positions"],
        candidate["indices"],
        epsilon=EPSILON,
        max_triangle_pair_checks=required_pairs - 1,
    )

    gates = {
        "exact-uc-commit-bound": "PASS" if actual_uc_commit == UC_COMMIT else "FAIL",
        "exact-uc-module-blob-bound": "PASS" if actual_uc_blob == UC_MODULE_BLOB else "FAIL",
        "candidate-identity-unchanged": "PASS" if candidate_digest == EXPECTED_CANDIDATE_DIGEST else "FAIL",
        "local-historical-observer-still-clear": (
            "PASS" if local_report["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS" else "FAIL"
        ),
        "merged-uc-observer-clear": (
            "PASS" if uc_report["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS" else "FAIL"
        ),
        "merged-uc-inspection-complete": "PASS" if uc_report["inspection_complete"] is True else "FAIL",
        "overlapping-intersection-count-matches": (
            "PASS"
            if local_report["self_intersection_pair_count"] == uc_report["self_intersection_pair_count"] == 0
            else "FAIL"
        ),
        "exact-pair-work-accounted": (
            "PASS"
            if local_report["triangle_pair_count"]
            == uc_report["triangle_pair_checks_required"]
            == uc_report["triangle_pair_checks_performed"]
            == required_pairs
            else "FAIL"
        ),
        "topological-neighbor-exclusion-count-matches": (
            "PASS"
            if local_report["skipped_topological_neighbor_pairs"]
            == uc_report["skipped_topological_neighbor_pairs"]
            else "FAIL"
        ),
        "crossing-negative-control-matches": (
            "PASS"
            if local_negative["self_intersection_pair_count"]
            == uc_negative["self_intersection_pair_count"]
            == 1
            and uc_negative["status"] == "SELF_INTERSECTIONS_DETECTED"
            else "FAIL"
        ),
        "uc-budget-hold-fails-closed-before-scan": (
            "PASS"
            if uc_budget_hold["status"] == "HOLD_TRIANGLE_PAIR_BUDGET_EXCEEDED"
            and uc_budget_hold["inspection_complete"] is False
            and uc_budget_hold["triangle_pair_checks_required"] == required_pairs
            and uc_budget_hold["triangle_pair_checks_performed"] == 0
            and uc_budget_hold["self_intersection_pair_count"] is None
            else "FAIL"
        ),
    }
    status = "PASS" if all(value == "PASS" for value in gates.values()) else "FAIL"

    receipt = {
        "schema": "axm.animal-connected-chain-uc-self-intersection-rebind/v0.1",
        "status": status,
        "candidate": "front-left-connected-chain-001",
        "candidate_digest": candidate_digest,
        "expected_candidate_digest": EXPECTED_CANDIDATE_DIGEST,
        "source_name": spec["name"],
        "source_region_ids": list(region_ids),
        "epsilon": EPSILON,
        "shared_observer": {
            "repository": UC_REPOSITORY,
            "commit": actual_uc_commit,
            "expected_commit": UC_COMMIT,
            "module": UC_MODULE,
            "module_blob": actual_uc_blob,
            "expected_module_blob": UC_MODULE_BLOB,
            "default_max_triangle_pair_checks": DEFAULT_MAX_TRIANGLE_PAIR_CHECKS,
        },
        "historical_local_report": local_report,
        "shared_uc_report": uc_report,
        "negative_control": {
            "local": local_negative,
            "shared_uc": uc_negative,
        },
        "budget_hold_control": uc_budget_hold,
        "gates": gates,
        "migration_state": {
            "shared_successor_rebound": status == "PASS",
            "historical_local_receipt_preserved": True,
            "local_implementation_retired": False,
            "mesh_modified": False,
        },
        "truth_boundary": {
            "exact_static_candidate_nonadjacent_self_intersection_rechecked": status == "PASS",
            "adjacent_fold_or_contact_checked": False,
            "continuous_deformation_checked": False,
            "visual_quality_checked": False,
            "rig_or_weighting_checked": False,
            "collision_or_gameplay_checked": False,
            "runtime_or_performance_checked": False,
            "repair_or_adoption_authorized": False,
            "game_ready": False,
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "front_left_connected_chain_uc_self_intersection_rebind_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    if status != "PASS":
        raise SystemExit("UC self-intersection product rebind gates failed")

    print(
        json.dumps(
            {
                "status": status,
                "candidate_digest": candidate_digest,
                "triangle_count": uc_report["triangle_count"],
                "required_pair_checks": required_pairs,
                "skipped_topological_neighbor_pairs": uc_report["skipped_topological_neighbor_pairs"],
                "self_intersection_pair_count": uc_report["self_intersection_pair_count"],
                "negative_control_intersections": uc_negative["self_intersection_pair_count"],
                "budget_hold_pair_checks_performed": uc_budget_hold["triangle_pair_checks_performed"],
                "uc_commit": actual_uc_commit,
                "uc_module_blob": actual_uc_blob,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
