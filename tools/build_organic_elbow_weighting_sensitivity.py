#!/usr/bin/env python3
"""Cross-check the Organic elbow-relief form against the exact newer Rigging weighting donor.

This is a receiving/sensitivity proof only. It does not adopt the weighting profile,
rewrite Organic source, or claim visual/deformation/runtime acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from axm_animal_design.connected_deformation import (
    BASELINE_WEIGHTING,
    CANDIDATE_DIGEST as BASELINE_CONNECTED_DIGEST,
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
    digest,
)
from axm_animal_design.organic_elbow_relief import (
    CANDIDATE_DIGEST as ELBOW_RELIEF_DIGEST,
    build_elbow_relief_candidate,
)
from axm_animal_design.self_intersection import inspect_triangle_self_intersections

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-weighting-sensitivity/v0.1"
EXPECTED_CONNECTED_RIGGING_HEAD = "5625c9f796a75e8b441458c51093e55519490611"
EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"
EXPECTED_RIG_PLAN_DIGEST = "b1f39ef8cd127edf9288b89ebd1f1fc14e6a3ceb8b0db58fa0ba9b12bc892aa8"
EXPECTED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
EXPECTED_WEIGHTING_NAME = "ease-out-power-0p75-v1"
EXPECTED_EXPONENT = 0.75
METRIC_TOLERANCE = 1e-9


def _candidate_weights(positions, joint_position, child_direction, influence_radius, exponent):
    direction = _unit(child_direction, "child direction")
    rows = []
    for point in positions:
        longitudinal = _dot(_sub(point, joint_position), direction)
        t = max(0.0, min(1.0, longitudinal / influence_radius))
        child = t ** exponent
        rows.append((1.0 - child, child))
    return rows


def _probe_mesh(mesh: dict[str, Any], spec: dict[str, Any], plan: dict[str, Any], exponent: float) -> dict[str, Any]:
    joint = _select_joint(spec, plan)
    positions = [tuple(point) for point in mesh["positions"]]
    indices = list(mesh["indices"])
    landmarks = spec["landmarks"]
    joint_position = _vec3(landmarks[joint["landmark"]], "joint position")
    child_marker = _vec3(landmarks[joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    axis = _vec3(joint["axis"], "joint axis")
    weights = _candidate_weights(
        positions,
        joint_position,
        child_direction,
        float(joint["influence_radius"]),
        exponent,
    )

    source_areas = []
    for offset in range(0, len(indices), 3):
        a, b, c = (positions[indices[offset]], positions[indices[offset + 1]], positions[indices[offset + 2]])
        area = _triangle_double_area(a, b, c)
        if area <= 1e-12:
            raise ValueError("sensitivity input contains a degenerate neutral triangle")
        source_areas.append(area)

    static_self = inspect_triangle_self_intersections(positions, indices)
    if static_self["status"] != "PASS_NO_NONADJACENT_SELF_INTERSECTIONS":
        raise ValueError("sensitivity input contains a neutral self-intersection")

    poses = []
    all_pass = True
    for angle in joint["pose_angles_deg"]:
        posed = []
        fixed_drift = 0.0
        rigid_radius_drift = 0.0
        for point, (_, child_weight) in zip(positions, weights):
            rotated = _rotate_about_axis(point, joint_position, axis, angle)
            current = _add(point, _mul(_sub(rotated, point), child_weight))
            posed.append(current)
            if child_weight <= 1e-9:
                fixed_drift = max(fixed_drift, math.dist(point, current))
            if child_weight >= 1.0 - 1e-9:
                rigid_radius_drift = max(
                    rigid_radius_drift,
                    abs(math.dist(point, joint_position) - math.dist(current, joint_position)),
                )

        posed_areas = []
        collapsed = 0
        for offset in range(0, len(indices), 3):
            a, b, c = (posed[indices[offset]], posed[indices[offset + 1]], posed[indices[offset + 2]])
            area = _triangle_double_area(a, b, c)
            posed_areas.append(area)
            collapsed += int(area <= 1e-12)
        area_ratios = [after / before for after, before in zip(posed_areas, source_areas)]
        min_edge, max_edge = _edge_metrics(positions, posed, indices)
        self_state = inspect_triangle_self_intersections(posed, indices)
        neutral_drift = max(math.dist(a, b) for a, b in zip(positions, posed)) if angle == 0 else None
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
        poses.append({
            "angle_deg": float(angle),
            "status": status,
            "positions": [[round(value, 9) for value in point] for point in posed],
            "collapsed_triangles": collapsed,
            "minimum_triangle_area_ratio": round(min(area_ratios), 9),
            "maximum_triangle_area_ratio": round(max(area_ratios), 9),
            "minimum_edge_length_ratio": round(min_edge, 9),
            "maximum_edge_length_ratio": round(max_edge, 9),
            "fixed_weight_vertex_max_drift": round(fixed_drift, 12),
            "rigid_weight_radius_max_drift": round(rigid_radius_drift, 12),
            "neutral_max_vertex_drift": None if neutral_drift is None else round(neutral_drift, 12),
            "nonadjacent_self_intersection_pairs": self_state["self_intersection_pair_count"],
        })

    return {
        "weight_counts": {
            "fixed": sum(1 for _, child in weights if child <= 1e-9),
            "blended": sum(1 for _, child in weights if 1e-9 < child < 1.0 - 1e-9),
            "rigid": sum(1 for _, child in weights if child >= 1.0 - 1e-9),
        },
        "poses": poses,
        "structural_gate": "PASS" if all_pass else "FAIL",
    }


def _metric_row(pose: dict[str, Any]) -> tuple[float, float, float, float]:
    return (
        float(pose["minimum_triangle_area_ratio"]),
        float(pose["maximum_triangle_area_ratio"]),
        float(pose["minimum_edge_length_ratio"]),
        float(pose["maximum_edge_length_ratio"]),
    )


def _validate_donor_replay(local_baseline: dict[str, Any], donor_receipt: dict[str, Any]) -> list[dict[str, Any]]:
    if donor_receipt.get("gate") != "PASS_CONNECTED_TOPOLOGY_WEIGHTING_REFINEMENT":
        raise ValueError("connected Rigging donor is not a passing weighting receipt")
    if donor_receipt.get("connected_candidate_digest") != BASELINE_CONNECTED_DIGEST:
        raise ValueError("connected Rigging donor topology identity drift")
    if donor_receipt.get("rig_plan_digest") != EXPECTED_RIG_PLAN_DIGEST:
        raise ValueError("connected Rigging donor plan identity drift")
    if donor_receipt.get("weighting_profile_digest") != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise ValueError("connected Rigging donor weighting profile drift")
    if donor_receipt.get("candidate_weighting") != EXPECTED_WEIGHTING_NAME:
        raise ValueError("connected Rigging donor weighting name drift")
    if not math.isclose(float(donor_receipt.get("candidate_exponent")), EXPECTED_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("connected Rigging donor exponent drift")

    local_by_angle = {pose["angle_deg"]: pose for pose in local_baseline["poses"]}
    replay = []
    for row in donor_receipt["comparisons"]:
        angle = float(row["angle_deg"])
        local = local_by_angle.get(angle)
        if local is None:
            raise ValueError("local weighting replay pose schedule drift")
        donor_metrics = (
            float(row["candidate_minimum_triangle_area_ratio"]),
            float(row["candidate_maximum_triangle_area_ratio"]),
            float(row["candidate_minimum_edge_length_ratio"]),
            float(row["candidate_maximum_edge_length_ratio"]),
        )
        local_metrics = _metric_row(local)
        max_residual = max(abs(a - b) for a, b in zip(local_metrics, donor_metrics))
        if max_residual > METRIC_TOLERANCE:
            raise ValueError(f"local receiving replay diverges from exact Rigging donor at {angle}: {max_residual}")
        replay.append({"angle_deg": angle, "maximum_metric_residual": round(max_residual, 12)})
    return replay


def _edges(indices):
    out = set()
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        for first, second in ((a, b), (b, c), (c, a)):
            out.add(tuple(sorted((first, second))))
    return sorted(out)


def _overlay_svg(baseline: dict[str, Any], relief: dict[str, Any], indices: list[int]) -> str:
    width, height = 1220, 450
    panel_w = 385
    edges = _edges(indices)
    all_positions = [
        point
        for receipt in (baseline, relief)
        for pose in receipt["poses"]
        for point in pose["positions"]
    ]
    xs = [point[0] for point in all_positions]
    zs = [point[2] for point in all_positions]
    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    span_x = max(max_x - min_x, 1e-9)
    span_z = max(max_z - min_z, 1e-9)
    scale = min(300.0 / span_x, 300.0 / span_z)
    panels = []

    for panel_index, base_pose in enumerate(baseline["poses"]):
        relief_pose = relief["poses"][panel_index]
        origin_x = 15 + panel_index * 400
        origin_y = 365
        base_lines = []
        relief_lines = []
        for first, second in edges:
            for pose, collection, stroke, opacity in (
                (base_pose, base_lines, "#90a4b8", "0.45"),
                (relief_pose, relief_lines, "#f0c36a", "0.94"),
            ):
                a = pose["positions"][first]
                b = pose["positions"][second]
                ax = origin_x + 22 + (a[0] - min_x) * scale
                ay = origin_y - (a[2] - min_z) * scale
                bx = origin_x + 22 + (b[0] - min_x) * scale
                by = origin_y - (b[2] - min_z) * scale
                collection.append(
                    f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" '
                    f'stroke="{stroke}" stroke-width="1.15" opacity="{opacity}"/>'
                )
        title = f'{base_pose["angle_deg"]:+.0f} deg'
        details = (
            f'base minE {base_pose["minimum_edge_length_ratio"]:.3f} / maxE {base_pose["maximum_edge_length_ratio"]:.3f}  '
            f'relief minE {relief_pose["minimum_edge_length_ratio"]:.3f} / maxE {relief_pose["maximum_edge_length_ratio"]:.3f}'
        )
        panels.append(
            f'<rect x="{origin_x}" y="18" width="{panel_w}" height="395" rx="8" fill="#10151b" stroke="#394653"/>'
            f'<text x="{origin_x + 14}" y="46" fill="#f4f6f8" font-family="monospace" font-size="16">{title}</text>'
            f'<text x="{origin_x + 14}" y="69" fill="#9fb1c3" font-family="monospace" font-size="10">{details}</text>'
            + "".join(base_lines)
            + "".join(relief_lines)
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#0a0e12"/>'
        '<text x="20" y="432" fill="#90a4b8" font-family="monospace" font-size="11">baseline form + exact ease-out-power-0p75-v1</text>'
        '<text x="330" y="432" fill="#f0c36a" font-family="monospace" font-size="11">0.085 m elbow relief + same weighting</text>'
        '<text x="675" y="432" fill="#73879a" font-family="monospace" font-size="11">X/Z structural aid only; not visual-quality acceptance.</text>'
        + "".join(panels)
        + '</svg>\n'
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--donor-receipt", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--connected-rigging-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise SystemExit("rig-plan donor head drift")
    if args.connected_rigging_head != EXPECTED_CONNECTED_RIGGING_HEAD:
        raise SystemExit("connected Rigging donor head drift")

    source_path = Path(args.source)
    plan_path = Path(args.rig_plan)
    profile_path = Path(args.weighting_profile)
    donor_path = Path(args.donor_receipt)
    out = Path(args.out)

    spec = json.loads(source_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    donor = json.loads(donor_path.read_text(encoding="utf-8"))

    if digest(plan) != EXPECTED_RIG_PLAN_DIGEST:
        raise SystemExit("rig-plan digest drift")
    if digest(profile) != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("weighting-profile digest drift")
    if profile.get("candidate_profile") != EXPECTED_WEIGHTING_NAME:
        raise SystemExit("weighting-profile name drift")
    exponent = float(profile.get("candidate_exponent"))
    if not math.isclose(exponent, EXPECTED_EXPONENT, rel_tol=0.0, abs_tol=1e-12):
        raise SystemExit("weighting-profile exponent drift")
    if profile.get("baseline_profile") != BASELINE_WEIGHTING:
        raise SystemExit("weighting-profile baseline drift")

    baseline_mesh, _ = _build_exact_candidate(spec)
    if digest(baseline_mesh) != BASELINE_CONNECTED_DIGEST:
        raise SystemExit("baseline connected topology identity drift")
    relief_mesh, scope = build_elbow_relief_candidate(spec, plan)
    if digest(relief_mesh) != ELBOW_RELIEF_DIGEST:
        raise SystemExit("Organic relief identity drift")

    baseline = _probe_mesh(baseline_mesh, spec, plan, exponent)
    relief = _probe_mesh(relief_mesh, spec, plan, exponent)
    donor_replay = _validate_donor_replay(baseline, donor)

    if baseline["weight_counts"] != relief["weight_counts"]:
        raise SystemExit("Organic form changed weighting partition")

    comparisons = []
    edge_benefit = baseline["structural_gate"] == "PASS" and relief["structural_gate"] == "PASS"
    area_tradeoff_present = False
    for base_pose, relief_pose in zip(baseline["poses"], relief["poses"]):
        if base_pose["angle_deg"] != relief_pose["angle_deg"]:
            raise SystemExit("pose schedule drift")
        angle = base_pose["angle_deg"]
        row = {
            "angle_deg": angle,
            "baseline_minimum_triangle_area_ratio": base_pose["minimum_triangle_area_ratio"],
            "relief_minimum_triangle_area_ratio": relief_pose["minimum_triangle_area_ratio"],
            "minimum_triangle_area_ratio_delta": round(relief_pose["minimum_triangle_area_ratio"] - base_pose["minimum_triangle_area_ratio"], 9),
            "baseline_maximum_triangle_area_ratio": base_pose["maximum_triangle_area_ratio"],
            "relief_maximum_triangle_area_ratio": relief_pose["maximum_triangle_area_ratio"],
            "maximum_triangle_area_ratio_reduction": round(base_pose["maximum_triangle_area_ratio"] - relief_pose["maximum_triangle_area_ratio"], 9),
            "baseline_minimum_edge_length_ratio": base_pose["minimum_edge_length_ratio"],
            "relief_minimum_edge_length_ratio": relief_pose["minimum_edge_length_ratio"],
            "minimum_edge_length_ratio_delta": round(relief_pose["minimum_edge_length_ratio"] - base_pose["minimum_edge_length_ratio"], 9),
            "baseline_maximum_edge_length_ratio": base_pose["maximum_edge_length_ratio"],
            "relief_maximum_edge_length_ratio": relief_pose["maximum_edge_length_ratio"],
            "maximum_edge_length_ratio_reduction": round(base_pose["maximum_edge_length_ratio"] - relief_pose["maximum_edge_length_ratio"], 9),
            "baseline_self_intersections": base_pose["nonadjacent_self_intersection_pairs"],
            "relief_self_intersections": relief_pose["nonadjacent_self_intersection_pairs"],
        }
        if angle == 0.0:
            row["edge_comparison"] = "PASS_NEUTRAL_RATIOS"
            edge_benefit &= all(abs(value - 1.0) <= METRIC_TOLERANCE for value in _metric_row(base_pose))
            edge_benefit &= all(abs(value - 1.0) <= METRIC_TOLERANCE for value in _metric_row(relief_pose))
        else:
            min_edge_better = row["minimum_edge_length_ratio_delta"] > METRIC_TOLERANCE
            max_edge_better = row["maximum_edge_length_ratio_reduction"] > METRIC_TOLERANCE
            no_new_intersections = row["relief_self_intersections"] <= row["baseline_self_intersections"]
            row["edge_comparison"] = (
                "PASS_STRICT_EDGE_ENVELOPE_IMPROVEMENT"
                if min_edge_better and max_edge_better and no_new_intersections
                else "HOLD_EDGE_ENVELOPE"
            )
            edge_benefit &= row["edge_comparison"] == "PASS_STRICT_EDGE_ENVELOPE_IMPROVEMENT"
            area_tradeoff_present |= row["minimum_triangle_area_ratio_delta"] < -METRIC_TOLERANCE
        comparisons.append(row)

    decision = (
        "PASS_ELBOW_RELIEF_EDGE_BENEFIT_PERSISTS_UNDER_WEIGHTING_REFINEMENT"
        if edge_benefit and scope["global_bounds_unchanged"]
        else "HOLD_ELBOW_RELIEF_WEIGHTING_SENSITIVITY"
    )
    adoption_state = (
        "HOLD_COMBINED_ADOPTION_MIN_AREA_TRADEOFF_AND_VISUAL_REVIEW"
        if decision.startswith("PASS_") and area_tradeoff_present
        else "HOLD_COMBINED_ADOPTION"
    )

    receipt = {
        "schema": EVIDENCE_SCHEMA,
        "decision": decision,
        "adoption_state": adoption_state,
        "lineage": {
            "organic_pr8_baseline_connected_digest": BASELINE_CONNECTED_DIGEST,
            "organic_pr8_relief_digest": ELBOW_RELIEF_DIGEST,
            "connected_rigging_pr6_head": EXPECTED_CONNECTED_RIGGING_HEAD,
            "rigging_pr2_donor_head": EXPECTED_RIG_DONOR_HEAD,
            "rig_plan_digest": EXPECTED_RIG_PLAN_DIGEST,
            "weighting_profile_digest": EXPECTED_WEIGHTING_PROFILE_DIGEST,
            "weighting_profile": EXPECTED_WEIGHTING_NAME,
            "candidate_exponent": EXPECTED_EXPONENT,
        },
        "scope": scope,
        "donor_receiving_replay": donor_replay,
        "weight_counts": baseline["weight_counts"],
        "baseline_form_under_candidate_weighting": baseline,
        "elbow_relief_under_candidate_weighting": relief,
        "comparisons": comparisons,
        "area_tradeoff_present": area_tradeoff_present,
        "truth_boundary": {
            "organic_source_rewritten": False,
            "organic_review_candidate_changed": False,
            "rigging_weighting_adopted": False,
            "exact_external_rigging_receipt_replayed": True,
            "same_weighting_applied_to_both_forms": True,
            "sampled_structural_edge_benefit_checked": True,
            "triangle_area_tradeoff_reported_not_hidden": True,
            "visual_quality_accepted": False,
            "anatomy_or_biology_validated": False,
            "continuous_deformation_checked": False,
            "runtime_or_gameplay_checked": False,
        },
        "non_claims": [
            "No source-form migration is authorized by this sensitivity PASS.",
            "No Rigging weighting adoption or ownership transfer is implied.",
            "The minimum-triangle-area regression at nonzero samples remains a held tradeoff, not a hidden pass.",
            "No visual, anatomical, biological, continuous-deformation, animation, runtime, gameplay, CANON, production-readiness or mastery claim is made.",
        ],
    }

    out.mkdir(parents=True, exist_ok=True)
    (out / "organic-elbow-weighting-sensitivity-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "baseline-ease-vs-relief-ease-overlay.svg").write_text(
        _overlay_svg(baseline, relief, list(baseline_mesh["indices"])), encoding="utf-8"
    )
    (out / "weighting-profile.json").write_text(profile_path.read_text(encoding="utf-8"), encoding="utf-8")
    (out / "connected-rigging-donor-receipt.json").write_text(
        donor_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    if decision != "PASS_ELBOW_RELIEF_EDGE_BENEFIT_PERSISTS_UNDER_WEIGHTING_REFINEMENT":
        raise SystemExit("Organic elbow weighting-sensitivity gate held")
    if adoption_state != "HOLD_COMBINED_ADOPTION_MIN_AREA_TRADEOFF_AND_VISUAL_REVIEW":
        raise SystemExit("expected retained area/visual hold was not preserved")

    print(json.dumps({
        "decision": decision,
        "adoption_state": adoption_state,
        "comparisons": comparisons,
        "donor_receiving_replay": donor_replay,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
