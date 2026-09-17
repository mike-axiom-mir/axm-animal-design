from __future__ import annotations

import unittest

from axm_animal_design.joint_index_width_rigging_rebind import (
    MUTATION_MIN_SIGNAL_M,
    _distance,
    _quat_angle_deg,
    _skin_position,
    _source_position_to_target,
)


class JointIndexWidthRiggingRebindTests(unittest.TestCase):
    def test_source_to_target_boundary_is_explicit(self):
        self.assertEqual(_source_position_to_target([1.0, 2.0, 3.0]), [-2.0, 3.0, 1.0])

    def test_neutral_skin_position_is_invariant(self):
        position = [0.2, 0.3, 0.4]
        pivot = [0.1, 0.2, 0.3]
        identity = [0.0, 0.0, 0.0, 1.0]
        self.assertEqual(_skin_position(position, pivot, identity, 0.0), position)
        self.assertEqual(_skin_position(position, pivot, identity, 1.0), position)

    def test_joint_identity_mutation_is_observable(self):
        position = [0.0, 0.1, 0.0]
        pivot = [0.0, 0.0, 0.0]
        quaternion = [0.15643446504023087, 0.0, 0.0, 0.9876883405951378]
        child = _skin_position(position, pivot, quaternion, 1.0)
        parent = _skin_position(position, pivot, quaternion, 0.0)
        self.assertGreater(_distance(child, parent), MUTATION_MIN_SIGNAL_M)
        self.assertAlmostEqual(_quat_angle_deg(quaternion), 18.0, places=9)


if __name__ == "__main__":
    unittest.main()
