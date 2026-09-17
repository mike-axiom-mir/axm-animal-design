#!/usr/bin/env python3
"""Build Materials lookdev payload comparing transported and reconstructed tangent frames.

This is a receiving/appearance observer only. It consumes the exact Rigging
post-skin reconstruction owner code and the exact Technical-Art transport
artifact. It does not copy the reconstruction into Materials or adopt it for
Technical Art/Runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
    _pose_metrics,
    _select_joint,
    _source_triangle_areas,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import build_bilateral_source_successor_topology_rebind
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.connected_deformation import _sub, _vec3, _weights, digest
from axm_animal_design.transported_frame_reconstruction_constraint import (
    PASS_STATE as RECONSTRUCTION_PASS_STATE,
    _child_weights,
    _collapse_render_positions_to_source,
    inspect_post_skin_owner_frame_reconstruction,
)
from axm_animal_design.transported_tangent_deformation_audit import (
    _decode_glb,
    _orthonormalize_tangent,
    _quat_angle_deg,
    _skin_direction,
    _skin_position,
)

SCHEMA = "axm.animal-materials-transported-frame-lookdev/v0.1"
RIGGING_RECONSTRUCTION_HEAD = "81ab44eab2e13bed95187610a476be2b2c4667a7"
RIGGING_RECONSTRUCTION_MODULE_BLOB = "c9916c62e2081922b8eb7ec0b3cd1c25c019b2f6"
RIGGING_TRANSPORT_AUDIT_MODULE_BLOB = "42f31fc5cb95426e89d22b5ed6c2b0983a22326d"
RIGGING_RECONSTRUCTION_ARTIFACT_ID = 10476642320
RIGGING_RECONSTRUCTION_ARTIFACT_SHA256 = "2d11836cc7c1ada5146752d0b6205d0e4f476cd085ee8be4964e2f024f70fa58"
TECHNICAL_ART_HEAD = "4649d144841fbd1f3f43e9c7deb6f37b91fbd93d"
TECHNICAL_ART_ARTIFACT_ID = 10474385703
TECHNICAL_ART_ARTIFACT_SHA256 = "7fc2a7f5d745da593e8762efa98e13661f84a057b1eb60921d576c366e71d7bb"
TECHNICAL_ART_GLB_SHA256 = "ecb122e3274929c3d99bc8e29a472aaa2657bcb16b13331a4f1972bb6ec6b493"
TECHNICAL_ART_MODULE_BLOB = "90343f493389446f06d58202cb7465c98307458f"
ART_DIRECTION_PACKET_COMMIT = "7e08ae260128a90d9c9af7cfd6c9bc67eb85f680"
REPRESENTATIVE_SAMPLE_INDICES = (0, 10, 20, 30, 40)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _target_direction_to_source(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("target direction must be VEC3")
    x, y, z = (float(component) for component in value)
    length = (x * x + y * y + z * z) ** 0.5
    if length <= 1e-15:
        raise ValueError("target direction has zero length")
    # Inverse of source -> target [-y, z, x].
    return [z / length, -x / length, y / length]


def _source_transport_tangent(target_xyz, target_w):
    xyz = _target_direction_to_source(target_xyz)
    # Technical Art source->target mapping flips tangent handedness across the
    # determinant -1 coordinate boundary, so invert that exact relation here.
    source_w = -float(target_w)
    if abs(abs(source_w) - 1.0) > 1e-6:
        raise ValueError("transported tangent handedness drift")
    return xyz + [source_w]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--weighting-profile", required=True, type=Path)
    parser.add_argument("--technical-art-receipt", required=True, type=Path)
    parser.add_argument("--technical-art-glb", required=True, type=Path)
    parser.add_argument("--rigging-reconstruction-head", required=True)
    parser.add_argument("--rigging-reconstruction-module-blob", required=True)
    parser.add_argument("--rigging-transport-audit-module-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    exact = {
        "Rigging reconstruction head": (args.rigging_reconstruction_head, RIGGING_RECONSTRUCTION_HEAD),
        "Rigging reconstruction module blob": (args.rigging_reconstruction_module_blob, RIGGING_RECONSTRUCTION_MODULE_BLOB),
        "Rigging transport-audit module blob": (args.rigging_transport_audit_module_blob, RIGGING_TRANSPORT_AUDIT_MODULE_BLOB),
    }
    for label, (observed, expected) in exact.items():
        if observed != expected:
            raise SystemExit(f"unexpected {label}: {observed}")

    glb = args.technical_art_glb.read_bytes()
    if hashlib.sha256(glb).hexdigest() != TECHNICAL_ART_GLB_SHA256:
        raise SystemExit("exact Technical Art GLB SHA-256 drift")

    spec = _load(args.source)
    left_profile = _load(args.left_profile)
    bilateral_profile = _load(args.bilateral_profile)
    plan = _load(args.rig_plan)
    weighting_profile = _load(args.weighting_profile)
    transport_receipt = _load(args.technical_art_receipt)
    if digest(plan) != RIG_PLAN_DIGEST:
        raise SystemExit("exact rig-plan digest drift")
    if digest(weighting_profile) != WEIGHTING_PROFILE_DIGEST:
        raise SystemExit("exact weighting-profile digest drift")

    reconstruction_receipt = inspect_post_skin_owner_frame_reconstruction(
        spec,
        left_profile,
        bilateral_profile,
        plan,
        weighting_profile,
        transport_receipt,
        glb,
    )
    if reconstruction_receipt.get("state") != RECONSTRUCTION_PASS_STATE:
        raise SystemExit(f"Rigging reconstruction prerequisite is not PASS: {reconstruction_receipt.get('state')}")

    decoded = _decode_glb(glb)
    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    render_source_indices = [int(value) for value in static_basis["render_source_indices"]]
    source_vertex_count = int(static_basis["source_vertex_count"])
    if int(static_basis["render_vertex_count"]) != 84 or len(static_basis["render_indices"]) != 240:
        raise SystemExit("exact Geometry render domain drift")

    joint = _select_joint(spec, plan, "right")
    owner_source_positions = [tuple(float(value) for value in point) for point in right_candidate["positions"]]
    owner_source_indices = [int(value) for value in right_candidate["indices"]]
    joint_position = _vec3(spec["landmarks"][joint["landmark"]], "joint position")
    child_marker = _vec3(spec["landmarks"][joint["child_landmark"]], "child marker")
    child_direction = _sub(child_marker, joint_position)
    owner_source_weights = _weights(
        owner_source_positions,
        joint_position,
        child_direction,
        float(joint["influence_radius"]),
    )
    owner_source_areas = _source_triangle_areas(owner_source_positions, owner_source_indices)

    document = decoded["document"]
    animated_node = decoded["ANIMATED_NODE"]
    pivot = document["nodes"][animated_node].get("translation")
    if not isinstance(pivot, list) or len(pivot) != 3:
        raise SystemExit("transported child joint pivot missing")
    child_weights = _child_weights(decoded)

    pose_sets = []
    for sample_index in REPRESENTATIVE_SAMPLE_INDICES:
        time_value = float(decoded["TIMES"][sample_index])
        quaternion = decoded["ROTATIONS"][sample_index]
        angle_deg = _quat_angle_deg(quaternion)

        owner_pose = _pose_metrics(
            owner_source_positions,
            owner_source_indices,
            owner_source_areas,
            owner_source_weights,
            joint_position,
            _vec3(joint["axis"], "joint axis"),
            angle_deg,
        )
        if owner_pose.get("status") != "PASS":
            raise SystemExit(f"owner pose is not PASS at sample {sample_index}")
        owner_frame = _derive_posed_tangent_frame(right_candidate, static_basis, owner_pose["positions"])

        skinned_target_positions = [
            _skin_position(position, pivot, quaternion, child_weight)
            for position, child_weight in zip(decoded["POSITION"], child_weights)
        ]
        reconstructed_source_positions, split_residual = _collapse_render_positions_to_source(
            skinned_target_positions,
            render_source_indices,
            source_vertex_count,
        )
        if split_residual > 1e-6:
            raise SystemExit(f"UV split position drift at sample {sample_index}: {split_residual}")
        reconstructed_frame = _derive_posed_tangent_frame(
            right_candidate, static_basis, reconstructed_source_positions
        )

        transported_normals = []
        transported_tangents = []
        for normal, tangent, child_weight in zip(decoded["NORMAL"], decoded["TANGENT"], child_weights):
            target_normal = _skin_direction(normal, quaternion, child_weight)
            target_tangent_raw = _skin_direction(tangent[:3], quaternion, child_weight)
            target_tangent = _orthonormalize_tangent(target_tangent_raw, target_normal)
            transported_normals.append(_target_direction_to_source(target_normal))
            transported_tangents.append(_source_transport_tangent(target_tangent, tangent[3]))

        shared_positions = reconstructed_frame["render_positions"]
        shared_uvs = static_basis["render_uvs"]
        shared_indices = static_basis["render_indices"]
        if len(shared_positions) != 84 or len(transported_normals) != 84:
            raise SystemExit("render attribute count drift")

        pose_sets.append({
            "pose_id": f"right__sample_{sample_index:02d}",
            "side": "right",
            "sample_index": sample_index,
            "time_seconds": time_value,
            "angle_deg": angle_deg,
            "render_positions": shared_positions,
            "render_uvs": shared_uvs,
            "render_indices": shared_indices,
            "frame_variants": {
                "owner_rederived": {
                    "render_normals": owner_frame["render_normals"],
                    "render_tangents": owner_frame["render_tangents"],
                },
                "transported_static_skin": {
                    "render_normals": transported_normals,
                    "render_tangents": transported_tangents,
                },
                "position_reconstructed": {
                    "render_normals": reconstructed_frame["render_normals"],
                    "render_tangents": reconstructed_frame["render_tangents"],
                },
            },
        })

    payload = {
        "schema": SCHEMA,
        "exact_rigging_reconstruction_head": RIGGING_RECONSTRUCTION_HEAD,
        "exact_rigging_reconstruction_module_blob": RIGGING_RECONSTRUCTION_MODULE_BLOB,
        "exact_rigging_transport_audit_module_blob": RIGGING_TRANSPORT_AUDIT_MODULE_BLOB,
        "exact_rigging_reconstruction_artifact_id": RIGGING_RECONSTRUCTION_ARTIFACT_ID,
        "exact_rigging_reconstruction_artifact_sha256": RIGGING_RECONSTRUCTION_ARTIFACT_SHA256,
        "exact_technical_art_head": TECHNICAL_ART_HEAD,
        "exact_technical_art_module_blob": TECHNICAL_ART_MODULE_BLOB,
        "exact_technical_art_artifact_id": TECHNICAL_ART_ARTIFACT_ID,
        "exact_technical_art_artifact_sha256": TECHNICAL_ART_ARTIFACT_SHA256,
        "exact_technical_art_glb_sha256": TECHNICAL_ART_GLB_SHA256,
        "art_direction_owner_frame_baseline_commit": ART_DIRECTION_PACKET_COMMIT,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "reconstruction_prerequisite": reconstruction_receipt,
        "camera_contexts": ["three_quarter", "grazing"],
        "frame_modes": [
            "owner_rederived",
            "transported_static_skin",
            "position_reconstructed",
            "position_reconstructed_flipped_w_negative",
        ],
        "pose_sets": pose_sets,
        "probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
            "normal_probe": "same deterministic periodic tangent-space field as Materials PR #24 owner-frame baseline",
            "u_cycles": 4.0,
            "v_cycles": 3.0,
            "tangent_amplitude": 0.28,
            "bitangent_amplitude": 0.20,
        },
        "scope": {
            "primary_question": "what visible tangent-space shading consequence does the measured static transported direction-frame mismatch have, and does Rigging's position-derived reconstruction recover the accepted owner-frame lookdev baseline",
            "shared_positions_across_frame_modes": True,
            "shared_uvs_across_frame_modes": True,
            "shared_indices_across_frame_modes": True,
            "shared_material_lighting_and_cameras": True,
            "owner_reconstruction_algorithm_copied_into_materials": False,
            "production_normal_map_used": False,
        },
        "truth_boundary": {
            "materials_observes_appearance_only": True,
            "rigging_reconstruction_adopted_by_technical_art": False,
            "runtime_implementation_claimed": False,
            "production_tangent_space_adopted": False,
            "final_art_or_qa_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
