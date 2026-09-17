#!/usr/bin/env python3
"""Retain exact evidence for the selected-003 Organic source successor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from axm_animal_design.connected_deformation import _build_exact_candidate, digest
from axm_animal_design.organic_elbow_balanced_relief import RIG_PLAN_DIGEST
from axm_animal_design.organic_elbow_dense_search import build_search_variant
from axm_animal_design.organic_elbow_source_successor import (
    PROFILE_DIGEST,
    SOURCE_DIGEST,
    SELECTED_REVIEW_CANDIDATE_DIGEST,
    SELECTED_REVIEW_GEOMETRY_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
    build_source_owned_elbow_successor,
)

EVIDENCE_SCHEMA = "axm.animal-organic-elbow-source-adoption-evidence/v0.1"
EXPECTED_ART_DIRECTION_COMMIT = "880b79b6107b0d117f9a7a32f4fb134022cdf67b"
EXPECTED_VISUAL_QA_COMMIT = "aac10f46a3ead7a77156bffaedb4cd2ecb058561"


def _load(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _geometry(candidate):
    return {
        key: candidate[key]
        for key in ("positions", "indices", "path_points", "radii", "segments")
    }


def _svg_projection(baseline, successor, out: Path):
    width, height = 1000, 620
    points = [tuple(p) for p in baseline["positions"]] + [tuple(p) for p in successor["positions"]]
    projected = [(p[0], p[2]) for p in points]
    xs = [p[0] for p in projected]
    ys = [p[1] for p in projected]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    margin = 55
    scale = min((width - 2 * margin) / max(max_x - min_x, 1e-9),
                (height - 2 * margin) / max(max_y - min_y, 1e-9))

    def canvas(p):
        return (
            margin + (p[0] - min_x) * scale,
            height - (margin + (p[1] - min_y) * scale),
        )

    def edges(candidate):
        result = set()
        idx = candidate["indices"]
        for off in range(0, len(idx), 3):
            a, b, c = idx[off:off + 3]
            for first, second in ((a, b), (b, c), (c, a)):
                result.add(tuple(sorted((first, second))))
        return sorted(result)

    baseline_lines = []
    successor_lines = []
    for a, b in edges(baseline):
        x1, y1 = canvas((baseline["positions"][a][0], baseline["positions"][a][2]))
        x2, y2 = canvas((baseline["positions"][b][0], baseline["positions"][b][2]))
        baseline_lines.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')
    for a, b in edges(successor):
        x1, y1 = canvas((successor["positions"][a][0], successor["positions"][a][2]))
        x2, y2 = canvas((successor["positions"][b][0], successor["positions"][b][2]))
        successor_lines.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>')

    ring_marks = []
    for index in range(11, 21):
        x, y = canvas((successor["positions"][index][0], successor["positions"][index][2]))
        ring_marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.4"/>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="white"/>'
        '<text x="30" y="30" font-family="sans-serif" font-size="17">Animal elbow selected-003 source adoption — source-space X/Z structural overlay</text>'
        '<text x="30" y="52" font-family="sans-serif" font-size="12">Historical connected baseline + exact source-owned selected-003; ring vertices 11..20 marked. Not anatomy or final visual acceptance.</text>'
        f'<g stroke="#999" stroke-width="1.2" fill="none" opacity="0.72">{"".join(baseline_lines)}</g>'
        f'<g stroke="#111" stroke-width="1.4" fill="none" opacity="0.92">{"".join(successor_lines)}</g>'
        f'<g fill="#111">{"".join(ring_marks)}</g>'
        '</svg>'
    )
    ET.fromstring(svg)
    out.write_text(svg, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--rig-plan", required=True)
    parser.add_argument("--art-direction-commit", required=True)
    parser.add_argument("--visual-qa-commit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.art_direction_commit != EXPECTED_ART_DIRECTION_COMMIT:
        raise SystemExit("Art Direction decision identity drift")
    if args.visual_qa_commit != EXPECTED_VISUAL_QA_COMMIT:
        raise SystemExit("Visual QA decision identity drift")

    source = _load(args.source)
    profile = _load(args.profile)
    plan = _load(args.rig_plan)
    if digest(source) != SOURCE_DIGEST:
        raise SystemExit("source identity drift")
    if digest(profile) != PROFILE_DIGEST:
        raise SystemExit("source-successor profile identity drift")
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("Rigging donor identity drift")

    successor, scope = build_source_owned_elbow_successor(source, profile)
    review, _ = build_search_variant(source, plan, 0.0885, 1.03)
    if digest(review) != SELECTED_REVIEW_CANDIDATE_DIGEST:
        raise SystemExit("selected review candidate identity drift")
    if digest(_geometry(review)) != SELECTED_REVIEW_GEOMETRY_DIGEST:
        raise SystemExit("selected review geometry identity drift")
    if _geometry(successor) != _geometry(review):
        raise SystemExit("source-owned successor does not exactly reproduce selected-003 review shape")
    if digest(successor) != SOURCE_SUCCESSOR_CANDIDATE_DIGEST:
        raise SystemExit("source-owned successor identity drift")

    max_residual = max(
        sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)) ** 0.5
        for a, b in zip(successor["positions"], review["positions"])
    )
    if max_residual != 0.0:
        raise SystemExit("source/review position residual is nonzero")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "source-successor.json").write_text(
        json.dumps(successor, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "selected-review-control.json").write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    baseline, _ = _build_exact_candidate(source)
    _svg_projection(baseline, successor, out / "source-successor-structural-overlay.svg")

    receipt = {
        "schema": EVIDENCE_SCHEMA,
        "state": "PASS_SOURCE_OWNED_SELECTED003_EXACT_SHAPE_ADOPTION",
        "adoption_state": "SOURCE_OWNED_SUCCESSOR_NOT_CANON",
        "base_source_digest": SOURCE_DIGEST,
        "source_successor_profile_digest": PROFILE_DIGEST,
        "source_successor_candidate_digest": SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
        "selected_review_candidate_digest": SELECTED_REVIEW_CANDIDATE_DIGEST,
        "selected_review_geometry_digest": SELECTED_REVIEW_GEOMETRY_DIGEST,
        "source_vs_selected_review_max_position_residual_m": max_residual,
        "source_vs_selected_review_geometry_equal": True,
        "scope": scope,
        "direction_provenance": {
            "art_direction_commit": args.art_direction_commit,
            "visual_qa_commit": args.visual_qa_commit,
        },
        "handoff": {
            "geometry": "explicitly bind the new source-successor identity before inheriting any topology claim",
            "rigging": "explicitly rebind and rerun deformation evidence; no weighting acceptance transfers",
            "animation": "existing motion evidence remains bound to its previous form chain until explicit rebind",
            "runtime": "no runtime or target-engine readiness is claimed"
        },
        "non_claims": [
            "no anatomy, biology or veterinary correctness",
            "no CANON or canonical-source claim",
            "no production topology, rigging, skinning or weighting acceptance",
            "no continuous unsampled deformation guarantee",
            "no animation, target-engine, runtime, collision or gameplay readiness",
            "no Organic Form mastery"
        ]
    }
    (out / "source-adoption-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
