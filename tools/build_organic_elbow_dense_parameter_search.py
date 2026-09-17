#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_balanced_relief import RIG_PLAN_DIGEST, SOURCE_DIGEST
from axm_animal_design.organic_elbow_dense_search import inspect_parameter_search

EXPECTED_WEIGHTING_PROFILE_DIGEST = "a23fdaf47bbf17b3b070faf66d408faaddaa68c4a0487ace8f484851b91482e4"
EXPECTED_RIG_DONOR_HEAD = "04760112deb81a8d145226fe7ee02923107c9916"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _svg(receipt):
    width, height = 1180, 740
    radii = receipt["grid"]["bend_radii_m"]
    scales = receipt["grid"]["joint_axis_width_scales"]
    rows = {(row["bend_plane_radius_m"], row["joint_axis_width_scale"]): row for row in receipt["variants"]}
    x0, y0, cw, ch = 210, 115, 130, 88
    selected = receipt["selected_structural_successor"]
    selected_key = None if selected is None else (selected["bend_plane_radius_m"], selected["joint_axis_width_scale"])
    chunks = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#0c1218"/>',
        '<text x="34" y="38" fill="#eef4f7" font-family="monospace" font-size="20">Organic elbow bounded parameter neighborhood</text>',
        f'<text x="34" y="62" fill="#9eb1bc" font-family="monospace" font-size="11">{receipt["state"]} | structural search only | source adoption held</text>',
    ]
    for col, scale in enumerate(scales):
        chunks.append(f'<text x="{x0+col*cw+8}" y="{y0-18}" fill="#cdd9df" font-family="monospace" font-size="11">Y x{scale:.4f}</text>')
    for row_index, radius in enumerate(radii):
        chunks.append(f'<text x="34" y="{y0+row_index*ch+38}" fill="#cdd9df" font-family="monospace" font-size="11">R {radius:.5f} m</text>')
        for col, scale in enumerate(scales):
            item = rows[(radius, scale)]
            key = (radius, scale)
            fill = "#173126" if item["eligible_structural_successor"] else "#302026"
            stroke = "#ffd36e" if key == selected_key else "#52636d"
            label = "ELIGIBLE" if item["eligible_structural_successor"] else "HOLD"
            x, y = x0 + col*cw, y0 + row_index*ch
            chunks.extend([
                f'<rect x="{x}" y="{y}" width="{cw-8}" height="{ch-8}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="{2.5 if key==selected_key else 1}"/>',
                f'<text x="{x+8}" y="{y+20}" fill="#edf3f6" font-family="monospace" font-size="11">{label}</text>',
                f'<text x="{x+8}" y="{y+39}" fill="#a9bac3" font-family="monospace" font-size="9">area {item["minimum_nonzero_area_margin"]:+.8f}</text>',
                f'<text x="{x+8}" y="{y+55}" fill="#a9bac3" font-family="monospace" font-size="9">edge {item["minimum_nonzero_edge_margin"]:+.8f}</text>',
                f'<text x="{x+8}" y="{y+70}" fill="#8398a3" font-family="monospace" font-size="8">d {item["scope"]["maximum_neutral_vertex_delta_m"]:.7f}m</text>',
            ])
    if selected is not None:
        chunks.append(f'<text x="34" y="{height-47}" fill="#ffd36e" font-family="monospace" font-size="12">selected structural review candidate: R={selected["bend_plane_radius_m"]:.5f}m, Yx{selected["joint_axis_width_scale"]:.4f}, digest {selected["candidate_digest"]}</text>')
    chunks.append(f'<text x="34" y="{height-24}" fill="#9eb1bc" font-family="monospace" font-size="10">25 poses x 2 pinned weighting profiles per variant. Green means bounded structural eligibility only; no visual/anatomy/Rigging/runtime acceptance.</text>')
    chunks.append('</svg>')
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
    if args.rig_donor_head != EXPECTED_RIG_DONOR_HEAD:
        raise ValueError("rig donor head drift")
    if digest(profile) != EXPECTED_WEIGHTING_PROFILE_DIGEST:
        raise ValueError("weighting profile identity drift")

    receipt = inspect_parameter_search(source, plan)
    receipt["donor_provenance"] = {
        "rig_donor_head": args.rig_donor_head,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": EXPECTED_WEIGHTING_PROFILE_DIGEST,
        "relation": "PINNED_SENSITIVITY_INPUT_NOT_RIGGING_ACCEPTANCE",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "dense-parameter-search-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "dense-parameter-search-grid.svg").write_text(_svg(receipt), encoding="utf-8")
    print(receipt["state"])
    selected = receipt["selected_structural_successor"]
    if selected is None:
        print("NO_SELECTED_STRUCTURAL_SUCCESSOR")
    else:
        print(json.dumps({key: selected[key] for key in ("bend_plane_radius_m", "joint_axis_width_scale", "candidate_digest", "minimum_nonzero_area_margin", "minimum_nonzero_edge_margin")}, sort_keys=True))


if __name__ == "__main__":
    main()
