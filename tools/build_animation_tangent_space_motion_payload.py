#!/usr/bin/env python3
"""Convert exact Animation tangent-motion evidence into the pinned Materials render-review schema.

This is a coordination boundary, not a shader or deformation implementation.  It consumes
Animation's exact 41-sample bilateral tangent-motion packet and prepares the same source-
coordinate render attributes for Materials PR #24's unchanged Godot tangent-space review
host.  No motion, rig, weighting, UV, normal, tangent, shader, or material value is changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MATERIALS_HEAD = "e9d5c451b16bd05d2419248f58bef911f83dc1e8"
MATERIALS_RENDERER_BLOB = "252537d1544aa4e4af20bc78e54a6f886c1b9af0"
RIGGING_TANGENT_HEAD = "63c65d57fda0595217f86d971ff8c67f256188be"
RIGGING_TANGENT_MODULE_BLOB = "fbade964b3305d70775d196232ad2cd4671d0eac"
GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
GEOMETRY_MODULE_BLOB = "ba0b4e620f132413606177358e47bd32ae4d4965"
CLIP_DIGEST = "407903cbc5fe8803fc6a749e128b7736ebf139b414e61f77d9bbd32fc46f427b"
SOURCE_GATE = "PASS_BILATERAL_DEFORMED_TANGENT_41_SAMPLE_MOTION_BIND"
SOURCE_PAYLOAD_GATE = "PASS_BILATERAL_DEFORMED_TANGENT_GODOT_PAYLOAD_BUILD"
MATERIALS_SCHEMA = "axm.animal-materials-tangent-space-lookdev/v0.1"
RECEIPT_SCHEMA = "axm.animal-animation-tangent-space-motion-review-payload/v0.1"
GATE = "PASS_TANGENT_SPACE_SHADED_MOTION_REVIEW_PAYLOAD_BUILD"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--motion-receipt", type=Path, required=True)
    parser.add_argument("--motion-frames", type=Path, required=True)
    parser.add_argument("--motion-payload", type=Path, required=True)
    parser.add_argument("--materials-head", required=True)
    parser.add_argument("--materials-renderer-blob", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()

    if args.materials_head != MATERIALS_HEAD:
        raise ValueError("Materials tangent-space donor head drift")
    if args.materials_renderer_blob != MATERIALS_RENDERER_BLOB:
        raise ValueError("Materials render-review blob drift")

    motion_receipt = load(args.motion_receipt)
    frames = load(args.motion_frames)
    source_payload = load(args.motion_payload)

    if motion_receipt.get("gate") != SOURCE_GATE:
        raise ValueError("Animation tangent-motion prerequisite is not PASS")
    if source_payload.get("gate") != SOURCE_PAYLOAD_GATE:
        raise ValueError("Animation Godot tangent-motion payload prerequisite is not PASS")
    ident = motion_receipt.get("source_identity", {})
    if ident.get("rigging_deformed_tangent_head") != RIGGING_TANGENT_HEAD:
        raise ValueError("Rigging tangent donor drift")
    if ident.get("geometry_uv_tangent_head") != GEOMETRY_HEAD:
        raise ValueError("Geometry UV/tangent donor drift")
    if ident.get("clip_digest") != CLIP_DIGEST:
        raise ValueError("Animation clip digest drift")
    if ident.get("rig_weighting_profile") != "smoothstep-v0":
        raise ValueError("Animation weighting drift")
    motion = motion_receipt.get("motion", {})
    if motion.get("duration_seconds") != 1.0 or motion.get("sample_rate_hz") != 40:
        raise ValueError("Animation timing drift")
    if motion.get("endpoint_inclusive_sample_count") != 41:
        raise ValueError("Animation sample-count drift")
    if float(motion.get("front_elbow_peak_angle_deg", -1.0)) != 18.0:
        raise ValueError("Animation peak drift")

    pose_sets: list[dict[str, Any]] = []
    for side in ("left", "right"):
        side_frames = frames.get(side, [])
        side_payload = source_payload.get(side, {})
        indices = side_payload.get("render_indices", [])
        if len(side_frames) != 41:
            raise ValueError(f"{side} authored frame-count drift")
        if len(indices) != 240:
            raise ValueError(f"{side} render-index count drift")
        for expected_index, frame in enumerate(side_frames):
            if int(frame.get("sample_index", -1)) != expected_index:
                raise ValueError(f"{side} sample ordering drift")
            if len(frame.get("render_positions", [])) != 84:
                raise ValueError(f"{side} render-vertex count drift at {expected_index}")
            if frame.get("handedness_drift_count") != 0:
                raise ValueError(f"{side} tangent handedness drift at {expected_index}")
            pose_sets.append({
                "pose_id": f"animation__{side}__sample_{expected_index:02d}",
                "side": side,
                "weighting": "smoothstep-v0",
                "angle_deg": float(frame["angle_deg"]),
                "sample_index": expected_index,
                "time_seconds": float(frame["time_seconds"]),
                "render_positions": frame["render_positions"],
                "render_normals": frame["render_normals"],
                "render_uvs": frame["render_uvs"],
                "render_tangents": frame["render_tangents"],
                "render_indices": indices,
                "semantic_vertex_keys": frame["semantic_vertex_keys"],
            })

    payload = {
        "schema": MATERIALS_SCHEMA,
        "exact_rigging_tangent_head": RIGGING_TANGENT_HEAD,
        "exact_rigging_tangent_module_blob": RIGGING_TANGENT_MODULE_BLOB,
        "exact_geometry_uv_tangent_head": GEOMETRY_HEAD,
        "exact_geometry_uv_tangent_module_blob": GEOMETRY_MODULE_BLOB,
        "exact_materials_tangent_space_head": MATERIALS_HEAD,
        "exact_materials_render_review_blob": MATERIALS_RENDERER_BLOB,
        "animation_source_gate": SOURCE_GATE,
        "animation_clip_digest": CLIP_DIGEST,
        "budget": {
            "source_vertex_count": 42,
            "render_vertex_count": 84,
            "triangle_count": 80,
            "authored_samples_per_side": 41,
            "pose_set_count": len(pose_sets),
            "side_count": 2,
        },
        "pose_sets": pose_sets,
        "camera_contexts": ["three_quarter", "grazing"],
        "shader_modes": ["periodic_tangent_probe"],
        "probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
            "normal_probe": "procedural periodic tangent-space field; exact Materials PR #24 diagnostic, not production Animal normal map",
            "u_cycles": 4.0,
            "v_cycles": 3.0,
            "tangent_amplitude": 0.28,
            "bitangent_amplitude": 0.20,
        },
        "animation_review": {
            "truth_label": motion_receipt.get("motion", {}).get("truth_label"),
            "duration_seconds": 1.0,
            "sample_rate_hz": 40,
            "endpoint_inclusive_sample_count": 41,
            "front_elbow_peak_angle_deg": 18.0,
            "curve": motion.get("curve"),
            "retimed": False,
            "new_keys_authored": False,
            "weighting_changed": False,
            "discrete_authored_samples_only": True,
        },
        "scope": {
            "primary_question": "does the exact unchanged 41-sample Animation loop remain a reviewable shaded tangent-space sequence when rendered by the exact already-proven Materials PR #24 diagnostic host",
            "source_form_held": True,
            "rig_and_weighting_held": True,
            "render_domain_held": True,
            "uvs_normals_tangents_held": True,
            "materials_shader_donor_held": True,
            "camera_contexts_held": True,
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "authored_normal_map_used": False,
            "final_uv_layout_or_texel_density_accepted": False,
            "discrete_authored_sample_shaded_sequence_captured": True,
            "continuous_interpolation_visual_quality_proven": False,
            "real_time_40hz_pacing_proven": False,
            "production_skin_tangent_transport_established": False,
            "target_engine_import_equivalence_established": False,
            "art_direction_or_visual_qa_acceptance_claimed": False,
            "runtime_controller_or_state_machine_accepted": False,
            "gameplay_accepted": False,
            "canon_claimed": False,
        },
    }
    write(args.out, payload)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "gate": GATE,
        "payload_sha256": sha256(args.out),
        "source_motion_receipt_sha256": sha256(args.motion_receipt),
        "source_motion_frames_sha256": sha256(args.motion_frames),
        "source_motion_payload_sha256": sha256(args.motion_payload),
        "materials_head": MATERIALS_HEAD,
        "materials_render_review_blob": MATERIALS_RENDERER_BLOB,
        "rigging_tangent_head": RIGGING_TANGENT_HEAD,
        "geometry_uv_tangent_head": GEOMETRY_HEAD,
        "clip_digest": CLIP_DIGEST,
        "pose_set_count": len(pose_sets),
        "truth_boundary": payload["truth_boundary"],
    }
    write(args.receipt_out, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
