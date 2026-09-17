from __future__ import annotations

import struct
import unittest

from axm_animal_design.runtime_joint_index_width_budget import (
    UNSIGNED_BYTE,
    compact_joints_0_to_unsigned_byte,
    decode_accessor,
    pack_glb,
    parse_glb,
)


def _fixture(joint_rows: list[list[int]]) -> bytes:
    positions = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    if len(joint_rows) != len(positions):
        raise ValueError("fixture row count drift")
    position_bytes = struct.pack("<" + "f" * 6, *(value for row in positions for value in row))
    joint_bytes = struct.pack("<" + "H" * 8, *(value for row in joint_rows for value in row))
    binary = position_bytes + joint_bytes
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(position_bytes), "byteLength": len(joint_bytes), "target": 34962},
        ],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 2, "type": "VEC3"},
            {"bufferView": 1, "componentType": 5123, "count": 2, "type": "VEC4"},
        ],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "JOINTS_0": 1}, "mode": 4}]}],
    }
    return pack_glb(document, binary)


class RuntimeJointIndexWidthBudgetTests(unittest.TestCase):
    def test_compacts_unsigned_short_joint_indices_without_value_drift(self):
        control = _fixture([[0, 1, 0, 0], [1, 0, 0, 0]])
        result = compact_joints_0_to_unsigned_byte(control)
        candidate = parse_glb(result.candidate_bytes)

        self.assertEqual(result.control_joint_payload_bytes, 16)
        self.assertEqual(result.candidate_joint_payload_bytes, 8)
        self.assertEqual(result.joint_rows, [[0, 1, 0, 0], [1, 0, 0, 0]])
        self.assertEqual(
            candidate.document["accessors"][result.accessor_index]["componentType"],
            UNSIGNED_BYTE,
        )
        self.assertEqual(
            [[int(value) for value in row] for row in decode_accessor(candidate, result.accessor_index)],
            result.joint_rows,
        )
        self.assertEqual(result.non_joint_accessor_hashes_control, result.non_joint_accessor_hashes_candidate)

    def test_rejects_joint_index_outside_unsigned_byte_domain(self):
        control = _fixture([[0, 256, 0, 0], [1, 0, 0, 0]])
        with self.assertRaisesRegex(ValueError, "exceeds UNSIGNED_BYTE domain"):
            compact_joints_0_to_unsigned_byte(control)


if __name__ == "__main__":
    unittest.main()
