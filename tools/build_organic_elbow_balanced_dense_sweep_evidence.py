#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_balanced_relief import (
    RIG_PLAN_DIGEST,
    SOURCE_DIGEST,
)
from axm_animal_design.organic_elbow_balanced_sweep import (
    POSE_SCHEDULE_DEG,
    WEIGHTING_PROFILES,
    inspect_balanced_dense_sweep,
)

EXPECTED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
EXPECTED_WEIGHTING_PROFILE_NAME = "ease-out-power-0p75-v1"
EXPECTED_WEIGHTING_EXPONENT = 0.75
EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate_weighting_profile(profile, rig_donor_head: str):
    if rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise ValueError("rig donor head drift")
    if digest(profile) != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")
    if profile.get("baseline_plan_digest") != RIG_PLAN_DIGEST:
        raise ValueError("weighting profile rig-plan binding drift")
    if profile.get("candidate_profile") != EXPECTED_WEIGHTING_PROFILE_NAME:
        raise ValueError("weighting profile name drift")
    if abs(float(profile.get("candidate_exponent")) - EXPECTED_WEIGHTING_EXPONENT) > 1e-12:
        raise ValueError("weighting profile exponent drift")


def _svg(receipt):
    width, height = 1180, 720
    left, right, top, bottom = 90, 1135, 72, 620
    panel_h = 238
    gap = 42
    metrics = (
        ("balanced_min_area_delta_vs_baseline", "min area delta"),
        ("balanced_max_area_reduction_vs_baseline", "max area reduction"),
        ("balanced_min_edge_gain_vs_baseline", "min edge gain"),
        ("balanced_max_edge_reduction_vs_baseline", "max edge reduction"),
    )
    profile_rows = {
        profile: [row for row in receipt["comparisons"] if row["weighting"] == profile]
        for profile in WEIGHTING_PROFILES
    }
    all_values = [
        float(row[key])
        for rows in profile_rows.values()
        for row in rows
        for key, _ in metrics
    ]
    extent = max(max(abs(value) for value in all_values), 1e-6) * 1.15

    def x(angle):
        return left + (float(angle) + 60.0) / 120.0 * (right - left)

    def y(value, panel_top):
        center = panel_top + panel_h / 2.0
        return center - float(value) / extent * (panel_h * 0.43)

    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0c1218"/>',
        '<text x="36" y="38" fill="#eef4f7" font-family="monospace" font-size="20">Balanced elbow dense sampled non-regression evidence</text>',
        f'<text x="36" y="59" fill="#9eb1bc" font-family="monospace" font-size="11">25 poses/profile, -60..+60 deg in 5 deg steps | exact candidate unchanged | decision: {receipt["decision"]}</text>',
    ]
    palette = ("#67d5ff", "#a6e36d", "#ffc86b", "#e896ff")
    for panel_index, profile in enumerate(WEIGHTING_PROFILES):
        panel_top = top + panel_index * (panel_h + gap)
        center_y = y(0.0, panel_top)
        chunks.extend(
            [
                f'<rect x="{left}" y="{panel_top}" width="{right-left}" height="{panel_h}" rx="8" fill="#111a22" stroke="#304350"/>',
                f'<line x1="{left}" y1="{center_y:.2f}" x2="{right}" y2="{center_y:.2f}" stroke="#6c7d87" stroke-width="1" stroke-dasharray="5 5"/>',
                f'<text x="{left+12}" y="{panel_top+20}" fill="#edf3f6" font-family="monospace" font-size="13">{profile}</text>',
            ]
        )
        for tick in (-60, -30, 0, 30, 60):
            xpos = x(tick)
            chunks.append(f'<line x1="{xpos:.2f}" y1="{panel_top+28}" x2="{xpos:.2f}" y2="{panel_top+panel_h-18}" stroke="#22323c" stroke-width="1"/>')
            chunks.append(f'<text x="{xpos-12:.2f}" y="{panel_top+panel_h-5}" fill="#8296a1" font-family="monospace" font-size="10">{tick:+d}</text>')
        rows = profile_rows[profile]
        for metric_index, (key, label) in enumerate(metrics):
            points = " ".join(f'{x(row["angle_deg"]):.2f},{y(row[key], panel_top):.2f}' for row in rows)
            chunks.append(f'<polyline points="{points}" fill="none" stroke="{palette[metric_index]}" stroke-width="2"/>')
            chunks.append(f'<text x="{left+12+metric_index*245}" y="{panel_top+40}" fill="{palette[metric_index]}" font-family="monospace" font-size="10">{label}</text>')
    chunks.extend(
        [
            f'<text x="{left}" y="{height-34}" fill="#9eb1bc" font-family="monospace" font-size="11">Dashed zero line = exact baseline parity. Values below zero are regressions in this bounded metric convention.</text>',
            f'<text x="{left}" y="{height-17}" fill="#9eb1bc" font-family="monospace" font-size="11">This is sampled structural evidence only: no anatomy, visual acceptance, continuous deformation, Rigging/Animation/runtime or CANON claim.</text>',
            '</svg>',
        ]
    )
    return "\n".join(chunks) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--weighting-profile", required=True)
    parser.add_argument("--rig-donor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source = _load(args.source)
    plan = _load(args.rig_plan)
    profile = _load(args.weighting_profile)
    if digest(source) != SOURCE_DIGEST:
        raise ValueError("source identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise ValueError("rig plan identity drift")
    _validate_weighting_profile(profile, args.rig_donor_head)

    receipt = inspect_balanced_dense_sweep(source, plan)
    receipt["donor_provenance"] = {
        "rig_plan_repository": "mike-axiom-mir/axm-animal-design",
        "rig_plan_head": args.rig_donor_head,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": EXPECTED_WEIGHTING_PROFILE_DIGEST,
        "weighting_profile_name": EXPECTED_WEIGHTING_PROFILE_NAME,
        "weighting_profile_exponent": EXPECTED_WEIGHTING_EXPONENT,
        "relation": "PINNED_SENSITIVITY_INPUT_NOT_RIGGING_ACCEPTANCE",
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "balanced-elbow-dense-sweep-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "balanced-elbow-dense-sweep-margins.svg").write_text(
        _svg(receipt), encoding="utf-8"
    )
    (out / "pose-schedule.json").write_text(
        json.dumps(
            {
                "angles_deg": list(POSE_SCHEDULE_DEG),
                "profiles": list(WEIGHTING_PROFILES),
                "status": "ORGANIC_OBSERVATIONAL_SAMPLING_ONLY",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(receipt["decision"])
    print(json.dumps(receipt["worst_directional_margin"], sort_keys=True))


if __name__ == "__main__":
    main()
