import math
import unittest

from axm_animal_design.uc_bridge import _source_to_uc
from axm_animal_design.uc_rigged_animation_bridge import (
    maximum_owner_frame_residual,
    smoothstep_weights,
    source_axis_to_uc,
)


class UcRiggedAnimationBridgeTests(unittest.TestCase):
    def test_rotation_axis_uses_axial_transform_across_handedness_flip(self):
        self.assertEqual(source_axis_to_uc([0.0, 1.0, 0.0]), [1.0, -0.0, -0.0])
        # A direction vector would map to -X; a rotation axis must pick up det(M)=-1.
        self.assertEqual(_source_to_uc([0.0, 1.0, 0.0], "direction"), [-1.0, 0.0, 0.0])

    def test_smoothstep_weights_are_normalized_and_bounded(self):
        positions = [
            [0.0, -0.10, 0.0],
            [0.0, 0.00, 0.0],
            [0.0, 0.055, 0.0],
            [0.0, 0.11, 0.0],
            [0.0, 0.20, 0.0],
        ]
        joints, weights = smoothstep_weights(
            positions,
            joint_position=[0.0, 0.0, 0.0],
            child_marker=[0.0, 1.0, 0.0],
            influence_radius=0.11,
        )
        self.assertEqual(joints, [[0, 1, 0, 0]] * len(positions))
        for row in weights:
            self.assertAlmostEqual(sum(row), 1.0, places=12)
            self.assertTrue(all(0.0 <= value <= 1.0 for value in row))
        self.assertEqual(weights[0][:2], [1.0, 0.0])
        self.assertEqual(weights[1][:2], [1.0, 0.0])
        self.assertAlmostEqual(weights[2][1], 0.5, places=12)
        self.assertEqual(weights[3][:2], [0.0, 1.0])
        self.assertEqual(weights[4][:2], [0.0, 1.0])

    def test_owner_frame_residual_preserves_positive_rotation_after_basis_reflection(self):
        # One fully child-weighted source vertex rotates +90 degrees about source +Y.
        # Source [1,0,0] -> [0,0,-1].  Under the Animal->UC map these are
        # [0,0,1] -> [0,-1,0].  The axial transform must therefore rotate about +X.
        frames = []
        for index in range(41):
            angle = 90.0 * index / 40.0
            radians = math.radians(angle)
            source = [[math.cos(radians), 0.0, -math.sin(radians)]]
            frames.append({
                "sample_index": index,
                "time_seconds": index / 40.0,
                "angle_deg": angle,
                "positions": source,
            })
        residual, worst = maximum_owner_frame_residual(
            owner_frames=frames,
            uc_positions=[[0.0, 0.0, 1.0]],
            weights=[[0.0, 1.0, 0.0, 0.0]],
            uc_pivot=[0.0, 0.0, 0.0],
            uc_axis=source_axis_to_uc([0.0, 1.0, 0.0]),
        )
        self.assertLess(residual, 2e-7)
        self.assertIn(worst, (None, *range(41)))


if __name__ == "__main__":
    unittest.main()
