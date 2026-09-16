"""Dense sampled Organic review for the balanced connected-forelimb elbow form.

The balanced form itself is not changed here. This module asks a narrower
follow-up question: does the exact existing review candidate remain
structurally non-worse than the exact baseline across a materially denser pose
schedule under both already-pinned weighting profiles?

The denser schedule is an Organic observational override only. It is not a new
Rigging plan, animation clip, continuous-deformation proof, source adoption,
or runtime claim.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .connected_deformation import _build_exact_candidate, _select_joint, digest
from .organic_elbow_relief import build_elbow_relief_candidate
from .organic_elbow_balanced_relief import (
    BASELINE_CANDIDATE_DIGEST,
    CANDIDATE_DIGEST,
    PREDECESSOR_CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    _probe_candidate,
    build_balanced_elbow_candidate,
)

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-balanced-dense-sweep/v0.1"
POSE_SCHEDULE_DEG = tuple(float(value) for value in range(-60, 61, 5))
WEIGHTING_PROFILES = ("smoothstep-v0", "ease-out-power-0p75-v1")
COMPARISON_TOLERANCE = 1e-9


def _observational_sweep_plan(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Copy the exact rig plan and replace only the observation schedule."""
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    sweep = deepcopy(plan)
    joint = _select_joint(spec, sweep)
    joint["pose_angles_deg"] = list(POSE_SCHEDULE_DEG)
    return sweep


def _metric_comparison(baseline: dict[str, Any], balanced: dict[str, Any]) -> dict[str, Any]:
    min_area_delta = (
        float(balanced["minimum_triangle_area_ratio"])
        - float(baseline["minimum_triangle_area_ratio"])
    )
    max_area_reduction = (
        float(baseline["maximum_triangle_area_ratio"])
        - float(balanced["maximum_triangle_area_ratio"])
    )
    min_edge_gain = (
        float(balanced["minimum_edge_length_ratio"])
        - float(baseline["minimum_edge_length_ratio"])
    )
    max_edge_reduction = (
        float(baseline["maximum_edge_length_ratio"])
        - float(balanced["maximum_edge_length_ratio"])
    )
    nonworse = all(
        value >= -COMPARISON_TOLERANCE
        for value in (min_area_delta, max_area_reduction, min_edge_gain, max_edge_reduction)
    )
    return {
        "balanced_min_area_delta_vs_baseline": round(min_area_delta, 12),
        "balanced_max_area_reduction_vs_baseline": round(max_area_reduction, 12),
        "balanced_min_edge_gain_vs_baseline": round(min_edge_gain, 12),
        "balanced_max_edge_reduction_vs_baseline": round(max_edge_reduction, 12),
        "directionally_nonworse": nonworse,
    }


def inspect_balanced_dense_sweep(spec: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """Sample the unchanged balanced form every five degrees from -60 to +60.

    The gate is intentionally weaker than the earlier sparse-sample material
    improvement floor. Close to neutral, an absolute 0.005 edge improvement is
    neither expected nor meaningful. This pass therefore asks only whether the
    balanced form remains directionally non-worse than the baseline in the four
    retained distortion metrics while keeping the existing structural probe PASS.
    """
    if tuple(sorted(POSE_SCHEDULE_DEG)) != POSE_SCHEDULE_DEG:
        raise ValueError("dense Organic pose schedule must be monotonic")
    if POSE_SCHEDULE_DEG[0] != -60.0 or POSE_SCHEDULE_DEG[-1] != 60.0:
        raise ValueError("dense Organic pose schedule escaped the declared envelope")
    if any(
        abs((POSE_SCHEDULE_DEG[index + 1] - POSE_SCHEDULE_DEG[index]) - 5.0) > 1e-12
        for index in range(len(POSE_SCHEDULE_DEG) - 1)
    ):
        raise ValueError("dense Organic pose schedule must use exact five-degree steps")

    baseline, _ = _build_exact_candidate(spec)
    predecessor, _ = build_elbow_relief_candidate(spec, plan)
    balanced, scope = build_balanced_elbow_candidate(spec, plan)
    if digest(baseline) != BASELINE_CANDIDATE_DIGEST:
        raise ValueError("baseline connected candidate identity drift")
    if digest(predecessor) != PREDECESSOR_CANDIDATE_DIGEST:
        raise ValueError("predecessor Organic candidate identity drift")
    if digest(balanced) != CANDIDATE_DIGEST:
        raise ValueError("balanced Organic candidate identity drift")

    sweep_plan = _observational_sweep_plan(spec, plan)
    forms = {
        "baseline": baseline,
        "predecessor_relief": predecessor,
        "balanced_successor": balanced,
    }
    probes = {
        profile: {
            name: _probe_candidate(candidate, spec, sweep_plan, profile)
            for name, candidate in forms.items()
        }
        for profile in WEIGHTING_PROFILES
    }

    comparisons = []
    structural_pass = True
    directional_nonworse = True
    worst = {
        "minimum_area_delta": None,
        "maximum_area_reduction": None,
        "minimum_edge_gain": None,
        "maximum_edge_reduction": None,
    }
    for profile in WEIGHTING_PROFILES:
        baseline_by_angle = {
            float(row["angle_deg"]): row for row in probes[profile]["baseline"]["poses"]
        }
        predecessor_by_angle = {
            float(row["angle_deg"]): row
            for row in probes[profile]["predecessor_relief"]["poses"]
        }
        balanced_by_angle = {
            float(row["angle_deg"]): row
            for row in probes[profile]["balanced_successor"]["poses"]
        }
        if tuple(baseline_by_angle) != POSE_SCHEDULE_DEG:
            raise ValueError("baseline dense pose receipt schedule drift")
        if tuple(predecessor_by_angle) != POSE_SCHEDULE_DEG:
            raise ValueError("predecessor dense pose receipt schedule drift")
        if tuple(balanced_by_angle) != POSE_SCHEDULE_DEG:
            raise ValueError("balanced dense pose receipt schedule drift")

        for angle in POSE_SCHEDULE_DEG:
            base = baseline_by_angle[angle]
            old = predecessor_by_angle[angle]
            new = balanced_by_angle[angle]
            metric = _metric_comparison(base, new)
            row = {
                "weighting": profile,
                "angle_deg": angle,
                "baseline": {
                    "minimum_triangle_area_ratio": base["minimum_triangle_area_ratio"],
                    "maximum_triangle_area_ratio": base["maximum_triangle_area_ratio"],
                    "minimum_edge_length_ratio": base["minimum_edge_length_ratio"],
                    "maximum_edge_length_ratio": base["maximum_edge_length_ratio"],
                    "status": base["status"],
                    "nonadjacent_self_intersection_pairs": base[
                        "nonadjacent_self_intersection_pairs"
                    ],
                },
                "predecessor": {
                    "minimum_triangle_area_ratio": old["minimum_triangle_area_ratio"],
                    "maximum_triangle_area_ratio": old["maximum_triangle_area_ratio"],
                    "minimum_edge_length_ratio": old["minimum_edge_length_ratio"],
                    "maximum_edge_length_ratio": old["maximum_edge_length_ratio"],
                    "status": old["status"],
                    "nonadjacent_self_intersection_pairs": old[
                        "nonadjacent_self_intersection_pairs"
                    ],
                },
                "balanced": {
                    "minimum_triangle_area_ratio": new["minimum_triangle_area_ratio"],
                    "maximum_triangle_area_ratio": new["maximum_triangle_area_ratio"],
                    "minimum_edge_length_ratio": new["minimum_edge_length_ratio"],
                    "maximum_edge_length_ratio": new["maximum_edge_length_ratio"],
                    "status": new["status"],
                    "collapsed_triangles": new["collapsed_triangles"],
                    "fixed_weight_vertex_max_drift": new[
                        "fixed_weight_vertex_max_drift"
                    ],
                    "rigid_weight_radius_max_drift": new[
                        "rigid_weight_radius_max_drift"
                    ],
                    "nonadjacent_self_intersection_pairs": new[
                        "nonadjacent_self_intersection_pairs"
                    ],
                },
                **metric,
            }
            comparisons.append(row)
            structural_pass &= new["status"] == "PASS"
            directional_nonworse &= metric["directionally_nonworse"]
            values = {
                "minimum_area_delta": metric["balanced_min_area_delta_vs_baseline"],
                "maximum_area_reduction": metric["balanced_max_area_reduction_vs_baseline"],
                "minimum_edge_gain": metric["balanced_min_edge_gain_vs_baseline"],
                "maximum_edge_reduction": metric[
                    "balanced_max_edge_reduction_vs_baseline"
                ],
            }
            for key, value in values.items():
                worst[key] = value if worst[key] is None else min(worst[key], value)

    if structural_pass and directional_nonworse:
        decision = "PASS_BALANCED_ELBOW_DENSE_SWEEP_DIRECTIONALLY_NONWORSE"
    elif not structural_pass:
        decision = "FAIL_BALANCED_ELBOW_DENSE_SWEEP_STRUCTURAL_GATE"
    else:
        decision = "FAIL_BALANCED_ELBOW_DENSE_SWEEP_DIRECTIONAL_NONREGRESSION"

    return {
        "schema": EVIDENCE_SCHEMA,
        "decision": decision,
        "adoption_state": "HOLD_VISUAL_AND_SOURCE_ADOPTION",
        "source_digest": SOURCE_DIGEST,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "baseline_candidate_digest": BASELINE_CANDIDATE_DIGEST,
        "predecessor_candidate_digest": PREDECESSOR_CANDIDATE_DIGEST,
        "balanced_candidate_digest": CANDIDATE_DIGEST,
        "pose_schedule_deg": list(POSE_SCHEDULE_DEG),
        "pose_sample_count_per_profile": len(POSE_SCHEDULE_DEG),
        "weighting_profiles": list(WEIGHTING_PROFILES),
        "scope": scope,
        "observational_schedule_contract": {
            "source_rig_plan_mutated": False,
            "copied_plan_pose_schedule_only": True,
            "sample_envelope_deg": [-60.0, 60.0],
            "sample_step_deg": 5.0,
            "claim": "SAMPLED_ORGANIC_FORM_SENSITIVITY_NOT_NEW_RIGGING_OR_ANIMATION",
        },
        "probes": probes,
        "comparisons": comparisons,
        "worst_directional_margin": {
            key: round(float(value), 12) for key, value in worst.items()
        },
        "gates": {
            "exact_source_identity": "PASS",
            "exact_original_rig_plan_identity": "PASS",
            "exact_baseline_candidate_identity": "PASS",
            "exact_predecessor_candidate_identity": "PASS",
            "exact_balanced_candidate_identity": "PASS",
            "balanced_structural_probe_all_samples": "PASS" if structural_pass else "FAIL",
            "balanced_directionally_nonworse_all_samples": (
                "PASS" if directional_nonworse else "FAIL"
            ),
        },
        "truth_boundary": [
            "the balanced review form is unchanged from the exact prior candidate identity",
            "the five-degree schedule is an Organic observational copy of the exact rig plan, not a new Rigging plan or Animation clip",
            "sampled PASS does not establish continuous interpolation between samples",
            "directionally non-worse compares four retained geometric distortion metrics only and is not anatomy or visual acceptance",
            "no biology, source adoption, final silhouette, Rigging acceptance, Animation, runtime, gameplay, CANON, production readiness, or mastery claim",
        ],
    }
