#!/usr/bin/env python3
"""Prove exact Animal Geometry render-domain lineage through UC's neutral observer.

Animal owns the Geometry UV/tangent render domain and its semantic split identity.
This Technical-Art evidence adapter only presents those exact owner fields to the
pinned UC observer and retains the resulting report. It does not mutate Geometry,
choose a representation, or transfer Animal semantics into UC.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

PASS_STATE = "PASS_ANIMAL_EXACT_42_TO_84_RENDER_DOMAIN_PRESERVED_BY_UC_INDEX_ELIGIBILITY_OBSERVER"
GEOMETRY_SCHEMA = "axm.animal-bilateral-uv-tangent-basis/v0.1"
GEOMETRY_ID = "quadruped-front-elbow-bilateral-parametric-uv-tangent-basis-001"
EXPECTED_SOURCE_VERTICES = 42
EXPECTED_RENDER_VERTICES = 84
EXPECTED_TRIANGLES = 80


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _observer(uc_root: Path):
    path = uc_root / "src/axm_uc/indexed_surface_eligibility.py"
    spec = importlib.util.spec_from_file_location("axm_uc_indexed_surface_eligibility_exact", path)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load exact UC indexed-surface observer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def _validate_basis(basis: dict[str, Any]) -> None:
    if basis.get("schema") != GEOMETRY_SCHEMA or basis.get("id") != GEOMETRY_ID or basis.get("side") != "right":
        raise SystemExit("Geometry UV/tangent basis identity drift")
    if basis.get("source_vertex_count") != EXPECTED_SOURCE_VERTICES:
        raise SystemExit("Geometry source vertex-count drift")
    if basis.get("render_vertex_count") != EXPECTED_RENDER_VERTICES:
        raise SystemExit("Geometry render vertex-count drift")
    if basis.get("triangle_count") != EXPECTED_TRIANGLES:
        raise SystemExit("Geometry triangle-count drift")
    for key, expected in (
        ("render_positions", EXPECTED_RENDER_VERTICES),
        ("render_normals", EXPECTED_RENDER_VERTICES),
        ("render_uvs", EXPECTED_RENDER_VERTICES),
        ("render_tangents", EXPECTED_RENDER_VERTICES),
        ("render_source_indices", EXPECTED_RENDER_VERTICES),
        ("semantic_vertex_keys", EXPECTED_RENDER_VERTICES),
        ("render_indices", EXPECTED_TRIANGLES * 3),
        ("source_indices_by_corner", EXPECTED_TRIANGLES * 3),
    ):
        value = basis.get(key)
        if not isinstance(value, list) or len(value) != expected:
            raise SystemExit(f"Geometry {key} count drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-basis", required=True, type=Path)
    parser.add_argument("--uc-root", required=True, type=Path)
    parser.add_argument("--technical-art-head", required=True)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--uc-head", required=True)
    parser.add_argument("--uc-observer-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    basis = _load(args.geometry_basis)
    _validate_basis(basis)
    module, observer_path = _observer(args.uc_root)

    source_identity = f"{basis['source_candidate_id']}:{basis['source_candidate_digest']}"
    lineage = {
        "schema": module.INPUT_SCHEMA,
        "source_identity": source_identity,
        "surface_identity": f"{basis['id']}:right",
        "source": {
            "vertex_count": basis["source_vertex_count"],
            "indices": basis["source_indices_by_corner"],
        },
        "render": {
            "vertex_count": basis["render_vertex_count"],
            "source_vertex_indices": basis["render_source_indices"],
            "protected_split_ids": basis["semantic_vertex_keys"],
            "indices": basis["render_indices"],
            "channels": {
                "POSITION": basis["render_positions"],
                "NORMAL": basis["render_normals"],
                "TEXCOORD_0": basis["render_uvs"],
                "TANGENT": basis["render_tangents"],
            },
        },
    }

    report = module.observe_indexed_surface_eligibility(lineage)
    if report.get("eligibility_state") != "PRESERVE_RENDER_DOMAIN_INDEXING":
        raise SystemExit(f"unexpected eligibility state: {report.get('eligibility_state')}")
    if report.get("render_domain_state") != "RENDER_DOMAIN_SPLIT_REQUIRED":
        raise SystemExit(f"unexpected render-domain state: {report.get('render_domain_state')}")
    candidate = report.get("candidate")
    if not isinstance(candidate, dict) or candidate.get("vertex_count") != EXPECTED_RENDER_VERTICES:
        raise SystemExit("UC observer did not preserve the exact 84-vertex render domain")
    if candidate.get("triangle_count") != EXPECTED_TRIANGLES:
        raise SystemExit("UC observer triangle count drift")
    if report.get("split_observation", {}).get("position_only_weld_safe") is not False:
        raise SystemExit("UC observer failed to expose coincident-position split identity")

    position_only_count = len({
        (int(source_index), tuple(float(value) for value in position))
        for source_index, position in zip(basis["render_source_indices"], basis["render_positions"])
    })
    if position_only_count != EXPECTED_SOURCE_VERTICES:
        raise SystemExit(f"expected exact position-only collapse witness of 42, got {position_only_count}")

    ambiguous = json.loads(json.dumps(lineage))
    del ambiguous["render"]["protected_split_ids"]
    ambiguous_report = module.observe_indexed_surface_eligibility(ambiguous)
    if ambiguous_report.get("eligibility_state") != "HOLD_ATTRIBUTE_SEAM_AMBIGUITY" or ambiguous_report.get("candidate") is not None:
        raise SystemExit("missing protected split declaration did not fail closed")

    unsupported = json.loads(json.dumps(lineage))
    unsupported["render"]["channels"]["MORPH_POSITION_0"] = [[0.0, 0.0, 0.0] for _ in range(EXPECTED_RENDER_VERTICES)]
    unsupported_report = module.observe_indexed_surface_eligibility(unsupported)
    if unsupported_report.get("eligibility_state") != "NOT_EVALUATED_UNSUPPORTED_CHANNEL" or unsupported_report.get("candidate") is not None:
        raise SystemExit("unknown present channel did not fail closed")

    args.out.mkdir(parents=True, exist_ok=True)
    _write(args.out / "animal-render-lineage.json", lineage)
    _write(args.out / "uc-indexed-surface-report.json", report)
    _write(args.out / "negative-missing-protected-splits.json", ambiguous_report)
    _write(args.out / "negative-unsupported-channel.json", unsupported_report)

    receipt = {
        "schema": "axm.animal-uc-indexed-surface-observer-evidence/v0.1",
        "state": PASS_STATE,
        "technical_art_head": args.technical_art_head,
        "geometry_head": args.geometry_head,
        "uc_head": args.uc_head,
        "uc_observer_blob": args.uc_observer_blob,
        "uc_observer_sha256": _sha(observer_path),
        "geometry_source_vertices": EXPECTED_SOURCE_VERTICES,
        "geometry_render_vertices": EXPECTED_RENDER_VERTICES,
        "triangles": EXPECTED_TRIANGLES,
        "position_plus_source_only_unique_vertices": position_only_count,
        "uc_candidate_vertices": candidate["vertex_count"],
        "uc_eligibility_state": report["eligibility_state"],
        "uc_render_domain_state": report["render_domain_state"],
        "uc_position_only_weld_safe": report["split_observation"]["position_only_weld_safe"],
        "negative_missing_protected_splits": ambiguous_report["eligibility_state"],
        "negative_unsupported_channel": unsupported_report["eligibility_state"],
        "authority": {
            "animal_geometry_owns_source_render_mapping_and_semantic_split_identity": True,
            "technical_art_owns_only_cross_repo_contract_evidence": True,
            "uc_owns_only_neutral_observer_semantics": True,
        },
        "truth_boundary": {
            "surface_mutated": False,
            "representation_adopted": False,
            "visual_equality_proven": False,
            "runtime_savings_proven": False,
            "deformed_direction_frame_hold_changed": False,
            "canon_or_production_readiness": False,
        },
    }
    _write(args.out / "receipt.json", receipt)
    (args.out / "technical-art-head.txt").write_text(args.technical_art_head + "\n", encoding="utf-8")
    (args.out / "geometry-head.txt").write_text(args.geometry_head + "\n", encoding="utf-8")
    (args.out / "uc-head.txt").write_text(args.uc_head + "\n", encoding="utf-8")
    (args.out / "uc-observer-blob.txt").write_text(args.uc_observer_blob + "\n", encoding="utf-8")
    manifest = {path.name: _sha(path) for path in sorted(args.out.iterdir()) if path.is_file()}
    _write(args.out / "sha256-manifest.json", manifest)
    print(PASS_STATE)
    print(f"source_vertices={EXPECTED_SOURCE_VERTICES}")
    print(f"position_only_unique={position_only_count}")
    print(f"render_vertices={EXPECTED_RENDER_VERTICES}")
    print(f"uc_candidate_vertices={candidate['vertex_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
