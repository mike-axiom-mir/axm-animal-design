"""Dense sampled Organic review for the balanced connected-forelimb elbow form.

The balanced form itself is not changed here. This module asks a narrower
follow-up question: does the exact existing review candidate remain
structurally non-worse than the exact baseline across a materially denser pose
schedule under both already-pinned weighting profiles?

The denser schedule is owned by this Organic observer and never rewrites the
exact Rigging plan. It is not a new Rigging plan, animation clip,
continuous-deformation proof, source adoption, or runtime claim.
"""
from __future__ import annotations

from typing import Any

from .connected_deformation import (
    DRIFT_TOLERANCE,
    _add,
    _build_exact_candidate,
    _dot,
    _edge_metrics,
    _mul,
    _rotate_about_axis,
    _select_joint,
    _sub,
    _triangle_double_area,
    _unit,
    _vec3,
    _weights,
    digest,
)
from .organic_elbow_relief import build_elbow_relief_candidate
from .organic_elbow_balanced_relief import (
    BASELINE_CANDIDATE_DIGEST,
    CANDIDATE_DIGEST,
    EASE_OUT_EXPONENT,
    PREDECESSOR_CANDIDATE_DIGEST,
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
    _power_weights,
    build_balanced_elbow_candidate,
)
from .self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-balanced-dense-sweep/v0.1"
POSE_SCHEDULE_DEG = tuple(float(value) for value in range(-60, 61, 5))
WEIGHTING_PROFILES = ("smoothstep-v0", "ease-out-power-0p75-v1")
COMPARISON_TOLERANCE = 1e-9


def _probe_dense_candidate(
    candidate: dict[str, Any],
    spec: dict[str, Any],
    plan: dict[str, Any],
    weighting: str,
) -> dict[str, Any]:
    """Replay the existing deformation math on an Organic-owned sample schedule.

    `_select_joint` receives the untouched exact Rigging plan, so all joint,
    axis, influence-radius and original pose-contract checks remain active. Only
    this observer's local loop uses the denser angle schedule.
    """
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in candidate["positions"]]
    indices = list(candidate["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    if weighting == "smoothstep-v0":
        weights = _weights(
            positions,
            joint_position,
            child_direction,
            float(joint["influence_radius"]),
        )
    elif weighting == "ease-out-power-0p75-v1":
        weights = _power_weights(
            positions,
            joint_position,
            child_direction,
            float(joint["influence_radius"]),
            EASE_OUT_EXPONENT,
        )
    else:
        raise ValueError(f"unsupported weighting profile: {weighting}")

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (
            positions[indices[offset]],
            positions[indices[offset + 1]],
            positions[indices[offset + 2]],
        )
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("dense-sweep candidate contains a degenerate neutral triangle")
        source_areas.append(area)

    static_self = inspect_triangle_self_intersections(positions, indices)
    if static_self["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("dense-sweep candidate has a neutral self-intersection")

    poses = []
    all_pass = True
    for angle in POSE_SCHEDULE_DEG:
        posed = []
        fixed_drift = 0.0
        rigid_radius_drift = 0.0
        for point, (_, child_weight) in zip(positions, weights):
            rotated = _rotate_about_axis(point, joint_position, axis, angle)
            current = _add(point, _mul(_sub(rotated, point), child_weight))
            posed.append(current)
            if child_weight <= 1e-9:
                fixed_drift = max(fixed_drift, ((sum((point[i] - current[i]) ** 2 for i in range(3))) ** 0.5))
            if child_weight >= 1.0 - 1e-9:
                before_radius = (sum((point[i] - joint_position[i]) ** 2 for i in range(3))) ** 0.5
                after_radius = (sum((current[i] - joint_position[i]) ** 2 for i in range(3))) ** 0.5
                rigid_radius_drift = max(rigid_radius_drift, abs(before_radius - after_radius))

        posed_areas = []
        collapsed = 0
        for offset in range(0, len(indices), 3):
            a, b, c = (
                posed[indices[offset]],
                posed[indices[offset + 1]],
                posed[indices[offset + 2]],
            )
            area = _triangle_double_area(a, b, c)
            posed_areas.append(area)
            collapsed += int(area <= 1e-12)
        area_ratios = [after / before for after, before in zip(posed_areas, source_areas)]
        min_edge, max_edge = _edge_metrics(positions, posed, indices)
        self_state = inspect_triangle_self_intersections(posed, indices)
        neutral_drift = (
            max(
                (sum((a[i] - b[i]) ** 2 for i in range(3))) ** 0.5
                for a, b in zip(positions, posed)
            )
            if angle == 0.0
            else None
        )
        status = (
            "PASS"
            if collapsed == 0
            and fixed_drift <= DRIFT_TOLERANCE
            and rigid_radius_drift <= DRIFT_TOLERANCE
            and self_state["status"] == "PASS_NO_NONADJACENT_SELF_INTERSECTIONS"
            and (neutral_drift is None or neutral_drift <= DRIFT_TOLERANCE)
            else "FAIL"
        )
        all_pass &= status == "PASS"
        poses.append(
            {
                "angle_deg": angle,
                "status": status,
                "collapsed_triangles": collapsed,
                "minimum_triangle_area_ratio": round(min(area_ratios), 9),
                "maximum_triangle_area_ratio": round(max(area_ratios), 9),
                "minimum_edge_length_ratio": round(min_edge, 9),
                "maximum_edge_length_ratio": round(max_edge, 9),
                "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
                "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
                "neutral_max_vertex_drift": (
                    None if neutral_drift is None else round(neutral_drift, 12)
                ),
                "nonadjacent_self_intersection_pairs": self_state[
                    "self_intersection_pair_count"
                ],
            }
        )

    return {
        "weighting": weighting,
        "weight_counts": {
            "fixed": sum(1 for _, child in weights if child <= 1e-9),
            "blended": sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9),
            "rigid": sum(1 for _, child in weights if child >= 1.0 - 1e-9),
        },
        "poses": poses,
        "structural_gate": "PASS" if all_pass else "FAIL",
    }


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
    """Sample the unchanged balanced form every five degrees from -60 to +60."""
    if digest(spec) != SOURCE_DIGEST:
        raise ValueError("organic source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
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

    forms = {
        "baseline": baseline,
        "predecessor_relief": predecessor,
        "balanced_successor": balanced,
    }
    probes = {
        profile: {
            name: _probe_dense_candidate(candidate, spec, plan, profile)
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
                    "minimum_edge_length_ratio": new["minimum_edge_length_length_ratio"] if "minimum_edge_length_length_ratio" in new else new["minimum_edge_length_ratio"],
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
            "observer_schedule_external_to_rig_plan": True,
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
            "the five-degree schedule belongs only to this Organic observer; the exact Rigging plan remains byte-semantically untouched",
            "sampled PASS does not establish continuous interpolation between samples",
            "directionally non-worse compares four retained geometric distortion metrics only and is not anatomy or visual acceptance",
            "no biology, source adoption, final silhouette, Rigging acceptance, Animation, runtime, gameplay, CANON, production readiness, or mastery claim",
        ],
    }
