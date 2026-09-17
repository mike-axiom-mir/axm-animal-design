import unittest

from axm_animal_design.uc_rigged_tangent_bridge import (
    UNSIGNED_BYTE,
    UNSIGNED_SHORT,
    _joint_index_payload,
)


class JointIndexWidthAdoptionTests(unittest.TestCase):
    def test_small_joint_domain_uses_unsigned_byte(self):
        payload, component = _joint_index_payload([[0, 1, 0, 0], [1, 0, 0, 0]])
        self.assertEqual(component, UNSIGNED_BYTE)
        self.assertEqual(payload, bytes([0, 1, 0, 0, 1, 0, 0, 0]))

    def test_domain_above_byte_uses_unsigned_short(self):
        payload, component = _joint_index_payload([[0, 256, 0, 0]])
        self.assertEqual(component, UNSIGNED_SHORT)
        self.assertEqual(len(payload), 8)

    def test_negative_joint_index_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "negative"):
            _joint_index_payload([[0, -1, 0, 0]])

    def test_domain_above_unsigned_short_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "UNSIGNED_SHORT"):
            _joint_index_payload([[0, 65536, 0, 0]])


if __name__ == "__main__":
    unittest.main()
