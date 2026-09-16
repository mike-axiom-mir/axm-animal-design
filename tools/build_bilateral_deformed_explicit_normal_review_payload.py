#!/usr/bin/env python3
"""Build a source-pinned Materials payload for deformed explicit-normal lookdev.

This extends the static Materials review onto representative poses from the exact
Rigging PR #18 envelope. Geometry/Rigging remain authoritative for topology,
weights and normal derivation; this tool only assembles a renderer review payload.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from axm_animal_design.bilateral_deformed_logical_quad_normals import (
    PASS_STATE as RIGGING_PASS_STATE,
    inspect_bilateral_deformed_logical_quad_normals,
)
from axm_animal_design.bilateral_logical_quad_normals import (
    NORMAL_FIELD_ID,
    derive_logical_quad_normals,
)
from axm_animal_design.bilateral_mirror_surface_topology import inspect_exact_mirror_surface_repair
from axm_animal_design.bilateral_source_successor_rigging_rebind import (
    CANDIDATE_WEIGHTING,
    RIG_DONOR_HEAD,
    RIG_PLAN_DIGEST,
    WEIGHTING_PROFILE_DIGEST,
)
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.connected_deformation import BASELINE_WEIGHTING, digest

SCHEMA = "axm.animal-materials-deformed-explicit-normal-review/v0.1"
EXPECTED_RIGGING_HEAD = "91e2fd01be63df807c035b39f7ec824a4a5a60b8"
EXPECTED_RIGGING_MODULE_BLOB = "b8df083310727dcd05e7476b2158a081a5c25c8f"
EXPECTED_STATIC_MATERIALS_HEAD = "a2cd0a6135a7c8502aef9572f7079a3dd2632103"
EXPECTED_NORMAL_HEAD = "79e1667f6cc91e2ec8e41f01df18b6933c9c876d"
EXPECTED_NORMAL_MODULE_BLOB = "14a1ba3a1e4c96270197f4f449505113f7bf3e6e"
EXPECTED_TOPOLOGY_HEAD = "bdbb51303bd1b96866b06a71730ccc328bf4f2f6"
EXPECTED_TOPOLOGY_MODULE_BLOB = "9a0ebcc6169445996756bb446a87e3baf8b9cc33"
REPRESENTATIVE_ANGLES = (-60.0, -30.0, 0.0, 30.0, 60.0)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _ring_index(ring: int, segment: int, segments: int) -> int:
    return 1 + ring * segments + (segment % segments)


def _posed_candidate(candidate: dict, positions: list[list[float]]) -> dict:
    posed = copy.deepcopy(candidate)
    posed["positions"] = [list(map(float, point)) for point in positions]
    segments = int(posed["segments"])
    ring_count = len(posed["path_points"])
    points = []
    for ring in range(ring_count):
        ring_points = [posed["positions"][_ring_index(ring, segment, segments)] for segment in range(segments)]
        points.append([
            sum(point[axis] for point in ring_points) / float(segments)
            for axis in range(3)
        ])
    posed["path_points"] = points
    return posed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--left-profile", required=True, type=Path)
    parser.add_argument("--bilateral-profile", required=True, type=Path)
    parser.add_argument("--rig-plan", required=True, type=Path)
    parser.add_argument("--weighting-profile", required=True, type=Path)
    parser.add_argument("--rigging-head", required=True)
    parser.add_argument("--rigging-module-blob", required=True)
    parser.add_argument("--normal-head", required=True)
    parser.add_argument("--normal-module-blob", required=True)
    parser.add_argument("--topology-head", required=True)
    parser.add_argument("--topology-module-blob", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    expected = {
        "rigging head": (args.rigging_head, EXPECTED_RIGGING_HEAD),
        "rigging module blob": (args.rigging_module_blob, EXPECTED_RIGGING_MODULE_BLOB),
        "normal head": (args.normal_head, EXPECTED_NORMAL_HEAD),
        "normal module blob": (args.normal_module_blob, EXPECTED_NORMAL_MODULE_BLOB),
        "topology head": (args.topology_head, EXPECTED_TOPOLOGY_HEAD),
        "topology module blob": (args.topology_module_blob, EXPECTED_TOPOLOGY_MODULE_BLOB),
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

    rigging = inspect_bilateral_deformed_logical_quad_normals(
        spec, left_profile, bilateral_profile, plan, weighting_profile
    )
    if rigging["state"] != RIGGING_PASS_STATE:
        raise SystemExit(f"Rigging prerequisite is not PASS: {rigging['state']}")

    left, historical_right, topology_prerequisite = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    exact_left, exact_right, exact_geometry = inspect_exact_mirror_surface_repair(
        spec, left_profile, bilateral_profile, plan
    )
    if topology_prerequisite["state"] != "PASS_BILATERAL_SOURCE_SUCCESSOR_LOCAL_TOPOLOGY_REBIND":
        raise SystemExit("historical topology prerequisite is not PASS")
    if exact_geometry["state"] != "PASS_EXACT_MIRROR_SURFACE_TOPOLOGY_CANDIDATE":
        raise SystemExit("exact-mirror topology prerequisite is not PASS")
    if historical_right["positions"] != exact_right["positions"]:
        raise SystemExit("historical/exact right positions are not identical")
    if len(historical_right["indices"]) != len(exact_right["indices"]):
        raise SystemExit("historical/exact right triangle budget drift")
    if historical_right["indices"] == exact_right["indices"]:
        raise SystemExit("historical/exact right topology unexpectedly identical")
    if exact_left["positions"] != left["positions"]:
        raise SystemExit("left source identity drift")

    pose_sets = []
    for weighting in (BASELINE_WEIGHTING, CANDIDATE_WEIGHTING):
        mirror = rigging["bilateral_mirror_evidence"][weighting]
        if mirror["gate"] != "PASS_EXACT_MIRRORED_POSES_AND_DEFORMED_NORMALS":
            raise SystemExit(f"bilateral provenance is not PASS for {weighting}")
        right_representative = rigging["right"][weighting]["representative_poses"]
        left_representative = rigging["left"][weighting]["representative_poses"]
        for angle in REPRESENTATIVE_ANGLES:
            key = str(int(angle))
            right_row = right_representative[key]
            left_row = left_representative[key]
            if right_row["status"] != "PASS" or left_row["status"] != "PASS":
                raise SystemExit(f"representative Rigging pose is not PASS: {weighting} {angle}")

            historical_posed = _posed_candidate(historical_right, right_row["positions"])
            exact_posed = _posed_candidate(exact_right, right_row["positions"])
            historical_field = derive_logical_quad_normals(historical_posed)
            exact_field = derive_logical_quad_normals(exact_posed)
            if historical_field["id"] != NORMAL_FIELD_ID or exact_field["id"] != NORMAL_FIELD_ID:
                raise SystemExit("unexpected explicit normal-field identity")
            if historical_field["normals"] != exact_field["normals"]:
                raise SystemExit(f"posed explicit normals lost topology invariance: {weighting} {angle}")
            if historical_field["normals"] != right_row["normals"]:
                raise SystemExit(f"posed Materials normal payload diverges from Rigging receipt: {weighting} {angle}")
            if historical_field["tangent_policy"] != "NOT_DEFINED_NO_UV_BASIS":
                raise SystemExit("unexpected tangent policy")

            safe_weighting = weighting.replace("-", "_").replace(".", "p")
            pose_sets.append({
                "pose_id": f"{safe_weighting}__{int(angle):+d}deg",
                "weighting": weighting,
                "angle_deg": angle,
                "positions": right_row["positions"],
                "explicit_normals": right_row["normals"],
                "left_mirror_positions": left_row["positions"],
                "left_mirror_normals": left_row["normals"],
                "structural_pose_status": right_row["structural_pose_status"],
                "minimum_ring_outward_radial_dot": right_row["minimum_ring_outward_radial_dot"],
                "mirror_provenance": mirror,
            })

    payload = {
        "schema": SCHEMA,
        "exact_rigging_donor_head": args.rigging_head,
        "exact_rigging_module_blob": args.rigging_module_blob,
        "exact_static_materials_head": EXPECTED_STATIC_MATERIALS_HEAD,
        "exact_normal_donor_head": args.normal_head,
        "exact_normal_module_blob": args.normal_module_blob,
        "exact_topology_donor_head": args.topology_head,
        "exact_topology_module_blob": args.topology_module_blob,
        "exact_rig_donor_head": RIG_DONOR_HEAD,
        "rig_plan_digest": RIG_PLAN_DIGEST,
        "weighting_profile_digest": WEIGHTING_PROFILE_DIGEST,
        "rigging_prerequisite_state": rigging["state"],
        "source": {
            "base_source": spec.get("name"),
            "right_candidate_id": exact_right["id"],
            "right_candidate_digest": digest(exact_right),
            "normal_field_id": NORMAL_FIELD_ID,
        },
        "budget": {
            "vertex_count": len(exact_right["positions"]),
            "triangle_count": len(exact_right["indices"]) // 3,
            "historical_exact_positions_identical": historical_right["positions"] == exact_right["positions"],
            "historical_exact_index_count_identical": len(historical_right["indices"]) == len(exact_right["indices"]),
            "representative_pose_count": len(pose_sets),
            "weighting_count": 2,
            "angles_deg": list(REPRESENTATIVE_ANGLES),
        },
        "topologies": {
            "historical_right": historical_right["indices"],
            "exact_mirror_right": exact_right["indices"],
        },
        "pose_sets": pose_sets,
        "normal_modes": ["vertex_generated", "logical_quad_explicit"],
        "camera_contexts": ["three_quarter", "grazing"],
        "neutral_probe_material": {
            "albedo_srgb": [0.46, 0.49, 0.53, 1.0],
            "metallic": 0.0,
            "roughness": 0.5,
        },
        "scope": {
            "primary_question": "does the explicit logical-quad field continue to reduce historical-vs-exact topology shading sensitivity on representative exact Rigging poses",
            "source_positions_per_pose_held_across_topology_variants": True,
            "triangle_budget_held": True,
            "material_held": True,
            "lighting_held": True,
            "camera_per_context_held_across_all_poses": True,
            "both_established_weightings_retained": True,
            "bilateral_pose_and_normal_provenance_retained": True,
            "tangents_held_as": "NOT_DEFINED_NO_UV_BASIS",
        },
        "truth_boundary": {
            "production_material_assigned": False,
            "uvs_or_textures_checked": False,
            "representative_deformed_shading_captured": True,
            "continuous_deformation_visual_quality_proven": False,
            "tangents_checked": False,
            "production_skin_normal_transport_established": False,
            "runtime_acceptance_claimed": False,
            "final_visual_acceptance_claimed": False,
            "canon_claimed": False,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
