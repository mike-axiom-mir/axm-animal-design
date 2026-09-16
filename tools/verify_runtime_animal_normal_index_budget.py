#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

CONTROL_MODE = "UNINDEXED_EXPLICIT_NORMAL_CONTROL"
CANDIDATE_MODE = "INDEXED_EXPLICIT_NORMAL_CANDIDATE"
EXPECTED_PARENT = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
CONTEXTS = ("three_quarter", "grazing")


def load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def image_delta(a_path: Path, b_path: Path) -> dict:
    with Image.open(a_path).convert("RGB") as a, Image.open(b_path).convert("RGB") as b:
        if a.size != b.size:
            raise ValueError(f"image size mismatch: {a.size} != {b.size}")
        diff = ImageChops.difference(a, b)
        changed_pixels = 0
        max_channel_delta = 0
        for pixel in diff.getdata():
            if pixel != (0, 0, 0):
                changed_pixels += 1
                max_channel_delta = max(max_channel_delta, *pixel)
        return {
            "width": a.width,
            "height": a.height,
            "changed_pixels": changed_pixels,
            "max_channel_delta": max_channel_delta,
            "control_sha256": sha256(a_path),
            "candidate_sha256": sha256(b_path),
            "byte_identical": a_path.read_bytes() == b_path.read_bytes(),
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--control-receipt", required=True)
    p.add_argument("--candidate-receipt", required=True)
    p.add_argument("--control-root", required=True)
    p.add_argument("--candidate-root", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    control = load(args.control_receipt)
    candidate = load(args.candidate_receipt)
    if control.get("state") != "PASS_RUNTIME_ANIMAL_EXPLICIT_NORMAL_INDEX_OBSERVATION":
        raise SystemExit("control observation is not PASS")
    if candidate.get("state") != "PASS_RUNTIME_ANIMAL_EXPLICIT_NORMAL_INDEX_OBSERVATION":
        raise SystemExit("candidate observation is not PASS")
    if control.get("mode") != CONTROL_MODE or candidate.get("mode") != CANDIDATE_MODE:
        raise SystemExit("A/B mode identity drift")
    if control.get("exact_geometry_normal_parent_head") != EXPECTED_PARENT or candidate.get("exact_geometry_normal_parent_head") != EXPECTED_PARENT:
        raise SystemExit("exact Geometry normal parent drift")
    for key in ("runtime_head", "source_candidate_id", "source_candidate_digest", "normal_field_id", "normal_field_source_candidate_digest", "tangent_policy"):
        if control.get(key) != candidate.get(key):
            raise SystemExit(f"A/B identity drift for {key}")

    c = control["representation"]
    n = candidate["representation"]
    expected_control = {
        "surface_count": 1,
        "source_vertex_count": 42,
        "source_index_count": 240,
        "source_triangle_count": 80,
        "stored_vertex_count": 240,
        "stored_index_count": 0,
        "stored_primitive_count": 80,
        "logical_position_normal_index_bytes": 5760,
    }
    expected_candidate = {
        "surface_count": 1,
        "source_vertex_count": 42,
        "source_index_count": 240,
        "source_triangle_count": 80,
        "stored_vertex_count": 42,
        "stored_index_count": 240,
        "stored_primitive_count": 80,
        "logical_position_normal_index_bytes": 1968,
    }
    for key, value in expected_control.items():
        if int(c.get(key, -1)) != value:
            raise SystemExit(f"control {key} drift: {c.get(key)} != {value}")
    for key, value in expected_candidate.items():
        if int(n.get(key, -1)) != value:
            raise SystemExit(f"candidate {key} drift: {n.get(key)} != {value}")

    logical_delta = int(n["logical_position_normal_index_bytes"]) - int(c["logical_position_normal_index_bytes"])
    if logical_delta != -3792:
        raise SystemExit(f"unexpected logical payload delta: {logical_delta}")
    vertex_delta = int(n["stored_vertex_count"]) - int(c["stored_vertex_count"])
    if vertex_delta != -198:
        raise SystemExit(f"unexpected stored vertex delta: {vertex_delta}")

    visual = {}
    runtime_deltas = {}
    observed_buffer_deltas = []
    for context in CONTEXTS:
        if context not in control["contexts"] or context not in candidate["contexts"]:
            raise SystemExit(f"missing context {context}")
        cr = control["contexts"][context]["runtime"]
        nr = candidate["contexts"][context]["runtime"]
        deltas = {key: int(nr[key]) - int(cr[key]) for key in (
            "objects_in_frame", "primitives_in_frame", "draw_calls_in_frame", "texture_mem_bytes", "buffer_mem_bytes"
        )}
        if deltas["objects_in_frame"] != 0 or deltas["primitives_in_frame"] != 0 or deltas["draw_calls_in_frame"] != 0 or deltas["texture_mem_bytes"] != 0:
            raise SystemExit(f"runtime counter drift in {context}: {deltas}")
        if deltas["buffer_mem_bytes"] > 0:
            raise SystemExit(f"indexed candidate increased observed buffer memory in {context}: {deltas['buffer_mem_bytes']}")
        observed_buffer_deltas.append(deltas["buffer_mem_bytes"])
        runtime_deltas[context] = deltas

        a = Path(args.control_root) / control["contexts"][context]["filename"]
        b = Path(args.candidate_root) / candidate["contexts"][context]["filename"]
        d = image_delta(a, b)
        if d["changed_pixels"] != 0 or d["max_channel_delta"] != 0:
            raise SystemExit(f"visual regression in {context}: {d}")
        visual[context] = d

    state = (
        "PASS_ANIMAL_EXPLICIT_NORMAL_INDEXED_PAYLOAD_REDUCTION_WITH_OBSERVED_BUFFER_REDUCTION"
        if all(delta < 0 for delta in observed_buffer_deltas)
        else "PASS_ANIMAL_EXPLICIT_NORMAL_INDEXED_PAYLOAD_REDUCTION_BUFFER_NEUTRAL_ON_PROOF_HOST"
    )
    report = {
        "schema": "axm.runtime-animal-explicit-normal-index-budget-report/v0.1",
        "state": state,
        "decision": "INDEX_SOURCE_OWNED_EXPLICIT_NORMAL_SURFACE__PRESERVE_ATTRIBUTE_BOUNDARIES__ART_REVIEW_NO_OBSERVED_PIXEL_DELTA",
        "runtime_head": control["runtime_head"],
        "exact_geometry_normal_parent_head": EXPECTED_PARENT,
        "source_candidate_id": control["source_candidate_id"],
        "source_candidate_digest": control["source_candidate_digest"],
        "normal_field_id": control["normal_field_id"],
        "normal_field_source_candidate_digest": control["normal_field_source_candidate_digest"],
        "tangent_policy": control["tangent_policy"],
        "control_representation": c,
        "candidate_representation": n,
        "stored_vertex_delta": vertex_delta,
        "stored_vertex_reduction_percent": round((-vertex_delta / int(c["stored_vertex_count"])) * 100.0, 6),
        "logical_payload_delta_bytes": logical_delta,
        "logical_payload_reduction_percent": round((-logical_delta / int(c["logical_position_normal_index_bytes"])) * 100.0, 6),
        "runtime_counter_deltas": runtime_deltas,
        "visual_comparison": visual,
        "visual_tradeoff": "NONE_OBSERVED__TWO_FIXED_CAMERA_PNG_PAIRS_BYTE_IDENTICAL",
        "truth_boundary": {
            "exact_static_right_surface_only": True,
            "explicit_geometry_normal_candidate_visual_preference_claimed": False,
            "tangents_or_uvs_tested": False,
            "deformed_normal_quality_tested": False,
            "animation_tested": False,
            "target_device_cpu_gpu_fps_tested": False,
            "arbitrary_attribute_indexing_safety_claimed": False,
            "uc_extraction_claimed": False,
            "canon_claimed": False,
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
