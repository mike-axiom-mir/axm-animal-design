#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

CONTROL_MODE = "UNINDEXED_TANGENT_READY_CONTROL"
CANDIDATE_MODE = "INDEXED_TANGENT_READY_CANDIDATE"
CONTEXTS = ("three_quarter", "grazing")


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-receipt", required=True)
    parser.add_argument("--candidate-receipt", required=True)
    parser.add_argument("--control-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    control = load(args.control_receipt)
    candidate = load(args.candidate_receipt)
    for name, receipt, mode in (
        ("control", control, CONTROL_MODE),
        ("candidate", candidate, CANDIDATE_MODE),
    ):
        if receipt.get("state") != "PASS_RUNTIME_ANIMAL_TANGENT_INDEX_OBSERVATION":
            fail(f"{name} observation not PASS")
        if receipt.get("mode") != mode:
            fail(f"{name} mode drift")

    identity_fields = (
        "runtime_head",
        "exact_rigging_parent_head",
        "exact_geometry_basis_head",
        "basis_id",
        "source_candidate_id",
        "source_candidate_digest",
    )
    for field in identity_fields:
        if control.get(field) != candidate.get(field):
            fail(f"identity drift: {field}")

    cr = control["representation"]
    rr = candidate["representation"]
    expected = {
        "source_vertex_count": 42,
        "render_vertex_count": 84,
        "source_triangle_count": 80,
        "stored_primitive_count": 80,
    }
    for field, value in expected.items():
        if int(cr.get(field, -1)) != value or int(rr.get(field, -1)) != value:
            fail(f"representation drift: {field}")

    if int(cr.get("stored_vertex_count", -1)) != 240 or int(cr.get("stored_index_count", -1)) != 0:
        fail("control must remain 240 unindexed triangle-corner vertices")
    if int(rr.get("stored_vertex_count", -1)) != 84 or int(rr.get("stored_index_count", -1)) != 240:
        fail("candidate must remain exact 84 render vertices / 240 indices")

    control_bytes = int(cr["logical_position_normal_uv_tangent_index_bytes"])
    candidate_bytes = int(rr["logical_position_normal_uv_tangent_index_bytes"])
    if control_bytes != 11520 or candidate_bytes != 4992:
        fail(f"logical payload drift: {control_bytes} -> {candidate_bytes}")
    reduction = control_bytes - candidate_bytes
    if reduction != 6528:
        fail("logical reduction drift")

    context_reports = {}
    for context in CONTEXTS:
        cctx = control["contexts"].get(context)
        rctx = candidate["contexts"].get(context)
        if not cctx or not rctx:
            fail(f"missing context: {context}")
        cs = cctx["runtime"]
        rs = rctx["runtime"]
        for field, value in (("objects_in_frame", 1), ("primitives_in_frame", 80), ("draw_calls_in_frame", 1)):
            if int(cs.get(field, -1)) != value or int(rs.get(field, -1)) != value:
                fail(f"{context} renderer count drift: {field}")
        if int(rs["texture_mem_bytes"]) != int(cs["texture_mem_bytes"]):
            fail(f"{context} texture-memory drift")
        buffer_delta = int(rs["buffer_mem_bytes"]) - int(cs["buffer_mem_bytes"])
        if buffer_delta >= 0:
            fail(f"{context} indexed candidate did not reduce observed buffer memory: {buffer_delta}")

        cimg = Path(args.control_root) / cctx["filename"]
        rimg = Path(args.candidate_root) / rctx["filename"]
        if cimg.read_bytes() != rimg.read_bytes():
            fail(f"{context} A/B PNGs are not byte-identical")
        context_reports[context] = {
            "draw_call_delta": int(rs["draw_calls_in_frame"]) - int(cs["draw_calls_in_frame"]),
            "object_delta": int(rs["objects_in_frame"]) - int(cs["objects_in_frame"]),
            "primitive_delta": int(rs["primitives_in_frame"]) - int(cs["primitives_in_frame"]),
            "texture_mem_delta_bytes": int(rs["texture_mem_bytes"]) - int(cs["texture_mem_bytes"]),
            "buffer_mem_control_bytes": int(cs["buffer_mem_bytes"]),
            "buffer_mem_candidate_bytes": int(rs["buffer_mem_bytes"]),
            "buffer_mem_delta_bytes": buffer_delta,
            "control_png_sha256": sha256(cimg),
            "candidate_png_sha256": sha256(rimg),
            "png_byte_identical": True,
        }

    report = {
        "schema": "axm.runtime-animal-tangent-index-budget-report/v0.1",
        "state": "PASS_ANIMAL_TANGENT_READY_INDEXED_PAYLOAD_REDUCTION",
        "decision": "PRESERVE_GEOMETRY_RENDER_DOMAIN_SEAMS__INDEX_84_TANGENT_READY_VERTICES__DO_NOT_COLLAPSE_TO_42_SOURCE_VERTICES",
        "runtime_head": control["runtime_head"],
        "exact_rigging_parent_head": control["exact_rigging_parent_head"],
        "exact_geometry_basis_head": control["exact_geometry_basis_head"],
        "basis_id": control["basis_id"],
        "representation": {
            "control_stored_vertices": 240,
            "control_indices": 0,
            "candidate_stored_vertices": 84,
            "candidate_indices": 240,
            "triangles": 80,
            "stored_vertex_reduction": 156,
            "stored_vertex_reduction_fraction": 156 / 240,
            "logical_control_bytes": control_bytes,
            "logical_candidate_bytes": candidate_bytes,
            "logical_reduction_bytes": reduction,
            "logical_reduction_fraction": reduction / control_bytes,
        },
        "contexts": context_reports,
        "visual_tradeoff": "NONE_OBSERVED__TWO_FIXED_CAMERA_PNG_PAIRS_BYTE_IDENTICAL",
        "truth_boundary": {
            "final_uv_or_tangent_visual_acceptance": False,
            "tangent_space_normal_map_visual_acceptance": False,
            "deformed_shaded_acceptance": False,
            "transport_or_import_acceptance": False,
            "target_device_cpu_gpu_fps_vram_heap_acceptance": False,
            "arbitrary_mesh_indexing_safety": False,
            "uc_extraction": False,
            "canon": False,
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(report["state"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
