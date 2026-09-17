#!/usr/bin/env python3
"""Build retained evidence for one bounded connected-chain ring-phase sweep."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.ring_phase_study import derive_ring_phase_candidate
from axm_animal_design.self_intersection import inspect_triangle_self_intersections
from axm_animal_design.topology_study import (
    build_connected_chain,
    derive_shared_ring_radii,
    inspect_vertex_fan_connectivity,
)

SCHEMA = "axm.animal-connected-chain-ring-phase-evidence/v0.1"
BASELINE_DIGEST = "6e620ce4b1d810b259011d0d22d38ba7c7eea0e2500177df2bf28e08fe1caf6c"
REGIONS = ("front_upper_L", "front_lower_L", "front_paw_L")
PHASES = (4.5, 9.0, 13.5, 18.0)
SELECTED_PHASE = 4.5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_donor(path: Path):
    spec = importlib.util.spec_from_file_location(
        "axm_animal_design._exact_connected_deformation_donor",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load exact deformation donor {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _probe_candidate(donor, source, plan, candidate, radius_derivation):
    original = donor._build_exact_candidate

    def _candidate_builder(received_source):
        if received_source is not source:
            raise ValueError("evidence adapter received unexpected source object")
        return candidate, radius_derivation

    donor._build_exact_candidate = _candidate_builder
    try:
        return donor.inspect_connected_forelimb_deformation(source, plan)
    finally:
        donor._build_exact_candidate = original


def _pose_map(result):
    return {float(row["angle_deg"]): row for row in result["poses"]}


def _strictly_nonworse(candidate, baseline):
    checks = {}
    for angle in (-60.0, 60.0):
        before = _pose_map(baseline)[angle]
        after = _pose_map(candidate)[angle]
        checks[str(int(angle))] = {
            "minimum_triangle_area_ratio": after["minimum_triangle_area_ratio"] >= before["minimum_triangle_area_ratio"],
            "maximum_triangle_area_ratio": after["maximum_triangle_area_ratio"] <= before["maximum_triangle_area_ratio"],
            "minimum_edge_length_ratio": after["minimum_edge_length_ratio"] >= before["minimum_edge_length_ratio"],
            "maximum_edge_length_ratio": after["maximum_edge_length_ratio"] <= before["maximum_edge_length_ratio"],
        }
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--deformation-donor", required=True)
    parser.add_argument("--rig-plan-ref", required=True)
    parser.add_argument("--deformation-ref", required=True)
    parser.add_argument("--exact-head", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    source_path = Path(args.source)
    plan_path = Path(args.rig_plan)
    donor_path = Path(args.deformation_donor)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    source = json.loads(source_path.read_text())
    plan = json.loads(plan_path.read_text())
    donor = _load_donor(donor_path)

    if source.get("name") != "quadruped-neutral-001":
        raise ValueError("source identity drift")
    derived = derive_shared_ring_radii(source["regions"], REGIONS)
    landmarks = source["landmarks"]
    baseline = build_connected_chain(
        donor.CANDIDATE_ID,
        [landmarks[name] for name in derived["path_landmarks"]],
        derived["radii_m"],
        segments=10,
    )
    if donor.digest(baseline) != BASELINE_DIGEST:
        raise ValueError(f"exact Geometry PR #4 baseline drifted: {donor.digest(baseline)}")
    if donor.CANDIDATE_DIGEST != BASELINE_DIGEST:
        raise ValueError("exact Rigging donor no longer pins the expected Geometry baseline")

    baseline_probe = donor.inspect_connected_forelimb_deformation(source, plan)
    if baseline_probe["candidate_digest"] != BASELINE_DIGEST:
        raise ValueError("exact Rigging donor did not reproduce pinned baseline candidate")
    if baseline_probe["gate"] != "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION":
        raise ValueError("exact baseline deformation prerequisite no longer passes")

    sweep = []
    candidates = {}
    for phase in PHASES:
        identifier = f"front-left-connected-chain-phase-{str(phase).replace('.', 'p')}"
        candidate = derive_ring_phase_candidate(
            baseline,
            identifier=identifier,
            phase_degrees=phase,
        )
        fan = inspect_vertex_fan_connectivity(candidate["positions"], candidate["indices"])
        self_intersection = inspect_triangle_self_intersections(candidate["positions"], candidate["indices"])
        if candidate["indices"] != baseline["indices"]:
            raise ValueError(f"phase {phase} changed index connectivity")
        if candidate["path_points"] != baseline["path_points"] or candidate["radii"] != baseline["radii"]:
            raise ValueError(f"phase {phase} changed source-derived path/radii")
        if candidate["positions"][0] != baseline["positions"][0] or candidate["positions"][-1] != baseline["positions"][-1]:
            raise ValueError(f"phase {phase} moved an endpoint pole")
        if fan["status"] != "PASS_CONNECTED_VERTEX_FANS":
            raise ValueError(f"phase {phase} broke indexed vertex-fan connectivity")
        if self_intersection["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
            raise ValueError(f"phase {phase} introduced static nonadjacent self-intersection")

        probe = _probe_candidate(donor, source, plan, candidate, derived)
        if probe["gate"] != "PASS_CONNECTED_FORELIMB_BOUNDED_DEFORMATION":
            raise ValueError(f"phase {phase} failed the exact sampled deformation prerequisite")
        comparison = _strictly_nonworse(probe, baseline_probe)
        all_nonworse = all(all(row.values()) for row in comparison.values())
        sweep.append({
            "phase_degrees": phase,
            "candidate_id": candidate["id"],
            "candidate_digest": donor.digest(candidate),
            "vertices": len(candidate["positions"]),
            "triangles": len(candidate["indices"]) // 3,
            "fan_status": fan["status"],
            "static_self_intersection_status": self_intersection["status"],
            "sampled_deformation_gate": probe["gate"],
            "sampled_pose_metrics": [
                {
                    key: row[key]
                    for key in (
                        "angle_deg",
                        "collapsed_triangles",
                        "minimum_triangle_area_ratio",
                        "maximum_triangle_area_ratio",
                        "minimum_edge_length_ratio",
                        "maximum_edge_length_ratio",
                        "nonadjacent_self_intersection_pairs",
                    )
                }
                for row in probe["poses"]
            ],
            "nonworse_than_baseline_at_non_neutral_samples": comparison,
            "all_four_envelope_metrics_nonworse_at_both_non_neutral_samples": all_nonworse,
        })
        candidates[phase] = candidate

    selected = next(row for row in sweep if row["phase_degrees"] == SELECTED_PHASE)
    if not selected["all_four_envelope_metrics_nonworse_at_both_non_neutral_samples"]:
        raise ValueError("selected 4.5 degree phase no longer meets bounded non-worsening gate")
    competing = [
        row["phase_degrees"]
        for row in sweep
        if row["phase_degrees"] != SELECTED_PHASE
        and row["all_four_envelope_metrics_nonworse_at_both_non_neutral_samples"]
    ]
    if competing:
        raise ValueError(f"bounded sweep no longer uniquely supports 4.5 degree candidate: {competing}")

    selected_candidate = candidates[SELECTED_PHASE]
    summary = {
        "schema": SCHEMA,
        "status": "PASS_BOUNDED_RING_PHASE_CANDIDATE_4P5_VISUAL_HOLD",
        "exact_head": args.exact_head,
        "source_name": source["name"],
        "source_sha256": _sha256(source_path),
        "geometry_baseline": {
            "candidate_id": baseline["id"],
            "candidate_digest": BASELINE_DIGEST,
            "vertices": len(baseline["positions"]),
            "triangles": len(baseline["indices"]) // 3,
        },
        "exact_rigging_donors": {
            "rig_plan_ref": args.rig_plan_ref,
            "rig_plan_sha256": _sha256(plan_path),
            "deformation_ref": args.deformation_ref,
            "deformation_module_sha256": _sha256(donor_path),
            "joint_id": baseline_probe["joint_id"],
            "influence_radius_m": baseline_probe["influence_radius_m"],
            "weighting": baseline_probe["weighting"],
            "pose_angles_deg": [row["angle_deg"] for row in baseline_probe["poses"]],
        },
        "bounded_sweep": {
            "segment_count": baseline["segments"],
            "segment_pitch_degrees": 360.0 / baseline["segments"],
            "sampled_phases_degrees": list(PHASES),
            "selection_policy": (
                "among this non-exhaustive one-eighth-pitch sweep through half one segment pitch, "
                "retain a candidate only when all four sampled triangle/edge envelope metrics are "
                "non-worse than the exact baseline at both -60 and +60 degrees"
            ),
            "rows": sweep,
        },
        "selected_candidate": {
            "phase_degrees": SELECTED_PHASE,
            "candidate_id": selected_candidate["id"],
            "candidate_digest": donor.digest(selected_candidate),
            "indices_identical_to_baseline": selected_candidate["indices"] == baseline["indices"],
            "path_points_identical_to_baseline": selected_candidate["path_points"] == baseline["path_points"],
            "radii_identical_to_baseline": selected_candidate["radii"] == baseline["radii"],
            "endpoint_poles_identical_to_baseline": (
                selected_candidate["positions"][0] == baseline["positions"][0]
                and selected_candidate["positions"][-1] == baseline["positions"][-1]
            ),
        },
        "truth_boundary": {
            "new_canonical_source_authored": False,
            "baseline_geometry_rewritten": False,
            "connectivity_changed": False,
            "exact_existing_rigging_probe_reused": True,
            "bounded_phase_sweep_exhaustive": False,
            "continuous_motion_checked": False,
            "visual_or_shaded_deformation_checked": False,
            "volume_preservation_checked": False,
            "animation_checked": False,
            "runtime_checked": False,
            "gameplay_or_collision_checked": False,
            "production_retopology_claimed": False,
            "canon_or_mastery_claimed": False,
        },
    }

    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (output / "selected-candidate.json").write_text(
        json.dumps(selected_candidate, indent=2, sort_keys=True) + "\n"
    )
    (output / "baseline-candidate.json").write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    (output / "exact-head.txt").write_text(args.exact_head + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
