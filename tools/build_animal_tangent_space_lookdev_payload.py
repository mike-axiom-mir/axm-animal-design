#!/usr/bin/env python3
"""Build a source-pinned Materials payload for tangent-space Animal lookdev.

Consumes Geometry PR #20's exact UV/normal/tangent render domain and Rigging PR
#22's representative deformed tangent frames.  Materials only assembles a real
renderer diagnostic; it does not author topology, UVs, tangents, rigging or a
production Animal material.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import (
    PASS_STATE as TANGENT_PASS_STATE,
    REPRESENTATIVE_ANGLES_DEG,
    inspect_bilateral_deformed_tangent_frames,
)
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
)
from axm_animal_design.bilateral_uv_tangent_basis import (
    BASIS_ID,
    inspect_bilateral_uv_tangent_basis,
)
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING, digest

SCHEMA = "axm.animal-materials-tangent-space-lookdev/v0.1"
EXPECTED_RIGGING_TANGENT_HEAD = "63c65d57fda0595217f86d971ff8c67f256188be"
EXPECTED_RIGGING_TANGENT_MODULE_BLOB = "fbade964b3305d70775d196232ad2cd4671d0eac"
EXPECTED_GEOMETRY_HEAD = "ca4bb8a2f144231f8755eacc980785d1807b79db"
EXPECTED_GEOMETRY_MODULE_BLOB = "ba0b4e620f132413606177358e47bd32ae4d4965"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--weighting-profile", required=True, type=Path)
    parser.add_argument("--rigging-tangent-head", required=True)
    parser.add_argument("--rigging-tangent-module-blob", required=True)
    parser.add_argument("--geometry-head", required=True)
    parser.add_argument("--geometry-module-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    expected = {
        "Rigging tangent head": (args.rigging_tangent_head, EXPECTED_RIGGING_TANGENT_HEAD),
        "Rigging tangent module blob": (args.rigging_tangent_module_blob, EXPECTED_RIGGING_TANGENT_MODULE_BLOB),
        "Geometry UV/tangent head": (args.geometry_head, EXPECTED_GEOMETRY_HEAD),
        "Geometry UV/tangent module blob": (args.geometry_module_blob, EXPECTED_GEOMETRY_MODULE_BLOB),
    }
    for label, (observed, wanted) in expected.items():
        if observed != wanted:
            raise SystemExit(f"unexpected {label}: {observed}")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact rig-plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting-profile digest drift")

    tangent_receipt = inspect_bilateral_deformed_tangent_frames(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if tangent_receipt["state"] != TANGENT_PASS_STATE:
        raise SystemExit(f"deformed tangent prerequisite is not PASS: {tangent_receipt['state']}")

    left_basis, right_basis, geometry_receipt = inspect_bilateral_uv_tangent_basis(
        spec, left_profile, bilateral_profile
    )
    expected_geometry_state = "PASS_BILATERAL_UV_TANGENT_BASIS_CANDIDATE__FINAL_UV_VISUAL_TRANSPORT_HELD"
    if geometry_receipt["state"] != expected_geometry_state:
        raise SystemExit(f"Geometry UV/tangent prerequisite is not PASS: {geometry_receipt['state']}")
    if int(left_basis["render_vertex_count"]) != 84 or int(right_basis["render_vertex_count"]) != 84:
        raise SystemExit("expected exact 84-vertex seam-aware render domains")
    if left_basis["render_indices"] != right_basis["render_indices"]:
        raise SystemExit("left/right render-index identity drift")

    pose_sets = []
    for side, basis in (("left", left_basis), ("right", right_basis)):
        for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
            side_receipt = tangent_receipt[side][weighting]
            if side_receipt["gate"] != "PASS_DEFORMED_TANGENT_FRAME_DENSE_SWEEP":
                raise SystemExit(f"deformed tangent side prerequisite is not PASS: {side}/{weighting}")
            representative = side_receipt["representative_frames"]
            for angle in REPRESENTATIVE_ANGLES_DEG:
                key = str(int(angle))
                frame = representative[key]
                if len(frame["render_positions"]) != 84:
                    raise SystemExit("representative render-domain count drift")
                if frame["render_uvs"] != basis["render_uvs"]:
                    raise SystemExit(f"fixed UV identity drift: {side}/{weighting}/{angle}")
                if frame["semantic_vertex_keys"] != basis["semantic_vertex_keys"]:
                    raise SystemExit(f"semantic render identity drift: {side}/{weighting}/{angle}")
                safe_weighting = weighting.replace("-", "_").replace(".", "p")
                pose_sets.append({
                    "pose_id": f"{side}__{safe_weighting}__{int(angle):+d}deg",
                    "side": side,
                    "weighting": weighting,
                    "angle_deg": float(angle),
                    "render_positions": frame["render_positions"],
                    "render_normals": frame["render_normals"],
                    "render_uvs": frame["render_uvs"],
                    "render_tangents": frame["render_tangents"],
                    "render_indices": basis["render_indices"],
                    "semantic_vertex_keys": frame["semantic_vertex_keys"],
                })

    payload = {
        "schema": SCHEMA,
        "exact_rigging_tangent_head": args.rigging_tangent_head,
        "exact_rigging_tangent_module_blob": args.rigging_tangent_module_blob,
        "exact_geometry_uv_tangent_head": args.geometry_head,
        "exact_geometry_uv_tangent_module_blob": args.geometry_module_blob,
        "exact_rig_donor_head": RIG_DONOR_HEAD,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "basis_id": BASIS_ID,
        "geometry_prerequisite_state": geometry_receipt["state"],
        "rigging_prerequisite_state": tangent_receipt["state"],
        "budget": {
            "source_vertex_count": 42,
            "render_vertex_count": 84,
            "triangle_count": 80,
            "representative_pose_count": len(pose_sets),
            "side_count": 2,
            "weighting_count": 2,
            "angles_deg": list(REPRESENTATIVE_ANGLES_DEG),
        },
        "pose_sets": pose_sets,
        "camera_contexts": ["three_quarter", "grazing"],
        "shader_modes": ["flat_tangent_control", "periodic_tangent_probe", "flipped_handedness_mutation"],
        "probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
            "normal_probe": "procedural periodic tangent-space field; no external texture asset",
            "u_cycles": 4.0,
            "v_cycles": 3.0,
            "tangent_amplitude": 0.28,
            "bitangent_amplitude": 0.20,
        },
        "scope": {
            "primary_question": "does the exact Geometry/Rigging UV-normal-tangent chain produce a renderer-visible tangent-space response through representative deformation, and does the harness detect tangent-handedness corruption",
            "source_form_held": True,
            "render_domain_held": True,
            "uvs_held": True,
            "normals_held": True,
            "exact_tangents_held_except_deliberate_mutation": True,
            "material_scalars_held": True,
            "lighting_held": True,
            "camera_contexts_held": True,
            "periodic_u_probe_avoids_authored_texture_seam_discontinuity": True,
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "authored_normal_map_used": False,
            "final_uv_layout_or_texel_density_accepted": False,
            "tangent_space_shader_response_captured": True,
            "representative_deformed_tangent_space_response_captured": True,
            "continuous_motion_visual_quality_proven": False,
            "production_skin_tangent_transport_established": False,
            "target_engine_import_equivalence_established": False,
            "final_art_or_qa_acceptance_claimed": False,
            "runtime_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
