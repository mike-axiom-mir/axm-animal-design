from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from axm_animal_design.bilateral_deformed_tangent_frames import _derive_posed_tangent_frame
from axm_animal_design.bilateral_mirror_surface_topology import derive_exact_mirror_surface_candidate
from axm_animal_design.bilateral_source_successor_topology_rebind import (
    build_bilateral_source_successor_topology_rebind,
)
from axm_animal_design.bilateral_uv_tangent_basis import derive_uv_tangent_basis
from axm_animal_design.runtime_post_skin_frame_plan import (
    PLAN_SCHEMA,
    compare_frames,
    compile_post_skin_frame_plan,
    derive_frame_from_source_positions,
    reconstruct_frame_from_target_render_positions,
)

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    return json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))


def _fixture():
    spec = _load("quadruped_neutral_001.json")
    left_profile = _load("quadruped_elbow_source_successor_003.json")
    bilateral_profile = _load("quadruped_elbow_bilateral_successor_003.json")
    left_candidate, historical_right, _ = build_bilateral_source_successor_topology_rebind(
        spec, left_profile, bilateral_profile
    )
    right_candidate, _ = derive_exact_mirror_surface_candidate(left_candidate, historical_right)
    static_basis = derive_uv_tangent_basis(right_candidate, side="right")
    return right_candidate, static_basis


class RuntimePostSkinFramePlanTests(unittest.TestCase):
    def test_compiled_neutral_frame_is_exact_owner_frame(self):
        candidate, static_basis = _fixture()
        owner = _derive_posed_tangent_frame(candidate, static_basis, candidate["positions"])
        plan = compile_post_skin_frame_plan(candidate, static_basis)
        runtime = derive_frame_from_source_positions(plan, candidate["positions"])
        self.assertEqual(plan["schema"], PLAN_SCHEMA)
        self.assertEqual(compare_frames(owner, runtime)["exact_frame_arrays"], True)

    def test_compiled_target_collapse_preserves_owner_frame_and_split_identity(self):
        candidate, static_basis = _fixture()
        owner = _derive_posed_tangent_frame(candidate, static_basis, candidate["positions"])
        plan = compile_post_skin_frame_plan(candidate, static_basis)
        target_render_positions = [
            [-float(position[1]), float(position[2]), float(position[0])]
            for position in owner["render_positions"]
        ]
        runtime, split_residual = reconstruct_frame_from_target_render_positions(
            plan, target_render_positions
        )
        self.assertEqual(split_residual, 0.0)
        self.assertTrue(compare_frames(owner, runtime)["exact_frame_arrays"])

    def test_corrupted_compiled_source_group_is_detectable(self):
        candidate, static_basis = _fixture()
        owner = _derive_posed_tangent_frame(candidate, static_basis, candidate["positions"])
        plan = compile_post_skin_frame_plan(candidate, static_basis)
        target_render_positions = [
            [-float(position[1]), float(position[2]), float(position[0])]
            for position in owner["render_positions"]
        ]
        mutated = copy.deepcopy(plan)
        mutated["source_groups"][11] = list(plan["source_groups"][12])
        runtime, _ = reconstruct_frame_from_target_render_positions(mutated, target_render_positions)
        delta = compare_frames(owner, runtime)
        self.assertFalse(delta["exact_frame_arrays"])
        self.assertGreater(
            max(
                delta["maximum_position_component_abs"],
                delta["maximum_normal_component_abs"],
                delta["maximum_tangent_component_abs"],
            ),
            1e-6,
        )


if __name__ == "__main__":
    unittest.main()
