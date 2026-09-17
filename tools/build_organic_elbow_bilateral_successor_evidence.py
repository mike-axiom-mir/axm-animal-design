from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_bilateral_successor import (
    PROFILE_DIGEST,
    RIGHT_GEOMETRY_DIGEST,
    RIGHT_SUCCESSOR_DIGEST,
    build_bilateral_elbow_source_successor,
)
from axm_animal_design.organic_elbow_source_successor import (
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST as LEFT_SUCCESSOR_DIGEST,
)


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project(point, *, width=760, height=420, margin=35):
    x, y = float(point[0]), float(point[1])
    xmin, xmax = 0.24, 0.69
    ymin, ymax = -0.41, 0.41
    sx = margin + (x - xmin) / (xmax - xmin) * (width - margin * 2)
    sy = height - margin - (y - ymin) / (ymax - ymin) * (height - margin * 2)
    return sx, sy


def _edges(candidate):
    out = set()
    indices = candidate["indices"]
    for offset in range(0, len(indices), 3):
        a, b, c = indices[offset:offset + 3]
        for first, second in ((a, b), (b, c), (c, a)):
            out.add(tuple(sorted((first, second))))
    return sorted(out)


def _svg(left, right, scope):
    width, height = 760, 420
    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect x="0" y="0" width="760" height="420" fill="white"/>',
        '<line x1="35" y1="210" x2="725" y2="210" stroke="#999" stroke-width="1" stroke-dasharray="4 4"/>',
        '<text x="38" y="25" font-family="monospace" font-size="14">Organic bilateral source successor 003 — top view (+X right, +Y up)</text>',
    ]
    for label, candidate, stroke in (
        ("LEFT selected-003 source", left, "#315a9b"),
        ("RIGHT exact mirrored source successor", right, "#a04a3a"),
    ):
        for first, second in _edges(candidate):
            x1, y1 = _project(candidate["positions"][first], width=width, height=height)
            x2, y2 = _project(candidate["positions"][second], width=width, height=height)
            rows.append(
                f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
                f'stroke="{stroke}" stroke-width="0.8" opacity="0.62"/>'
            )
        rows.append(f'<text x="38" y="{45 if "LEFT" in label else 63}" font-family="monospace" font-size="12" fill="{stroke}">{label}</text>')
    rows.append(
        f'<text x="38" y="395" font-family="monospace" font-size="12">'
        f'mirror residual={scope["mirror"]["maximum_position_residual_m"]:.12f} m; '
        f'right moved vertices={scope["right_moved_vertex_count"]}; CANON=false</text>'
    )
    rows.append("</svg>")
    return "\n".join(rows) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--left-profile", required=True)
    parser.add_argument("--bilateral-profile", required=True)
    parser.add_argument("--rigging-successor-head", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    source = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    left, right, scope = build_bilateral_elbow_source_successor(
        source, left_profile, bilateral_profile
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / "bilateral-profile.json", bilateral_profile)
    _write_json(out / "left-source-successor-control.json", left)
    _write_json(out / "right-source-successor.json", right)
    (out / "bilateral-mirror-structural-overlay.svg").write_text(
        _svg(left, right, scope), encoding="utf-8"
    )

    receipt = {
        "schema": "axm.animal-organic-bilateral-source-successor-evidence/v0.1",
        "result": scope["result"],
        "adoption_boundary": scope["adoption_boundary"],
        "profile_digest": PROFILE_DIGEST,
        "left_source_successor_candidate_digest": LEFT_SUCCESSOR_DIGEST,
        "right_source_successor_candidate_digest": RIGHT_SUCCESSOR_DIGEST,
        "right_geometry_digest": RIGHT_GEOMETRY_DIGEST,
        "rigging_successor_prerequisite": {
            "repository": "mike-axiom-mir/axm-animal-design",
            "pr": 10,
            "head": args.rigging_successor_head,
            "external_result_consumed": "PASS_SOURCE_SUCCESSOR_RIGGING_REBIND_DENSE_SWEEP",
            "retested_by_this_organic_proof": False,
        },
        "scope": scope,
        "non_claims": [
            "biology_or_anatomy_correctness",
            "right_side_geometry_or_topology_acceptance",
            "right_side_rigging_or_weighting_acceptance",
            "continuous_deformation_safety",
            "animation_acceptance",
            "runtime_or_gameplay_readiness",
            "canon_or_production_readiness",
            "organic_form_mastery",
        ],
    }
    _write_json(out / "bilateral-source-propagation-receipt.json", receipt)
    print(scope["result"])
    print(scope["adoption_boundary"])
    print("right_successor_digest", digest(right))


if __name__ == "__main__":
    main()
