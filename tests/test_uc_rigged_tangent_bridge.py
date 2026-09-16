import copy
import unittest

from axm_animal_design.uc_rigged_tangent_bridge import (
    GEOMETRY_BASIS_ID,
    GEOMETRY_BASIS_SCHEMA,
    RENDER_VERTEX_COUNT,
    SOURCE_CANDIDATE_ID,
    SOURCE_VERTEX_COUNT,
    TRIANGLE_COUNT,
    _validate_geometry_basis,
    source_tangent_to_uc,
)


class RiggedTangentBridgeTests(unittest.TestCase):
    def test_orientation_reversing_basis_flips_tangent_handedness(self):
        # Source +X maps to UC +Z. Tangent W must flip because det(M)=-1.
        self.assertEqual(source_tangent_to_uc([1.0, 0.0, 0.0, 1.0]), [0.0, 0.0, 1.0, -1.0])
        self.assertEqual(source_tangent_to_uc([0.0, 0.0, 1.0, -1.0]), [0.0, 1.0, 0.0, 1.0])

    def test_tangent_handedness_must_be_unit_sign(self):
        with self.assertRaisesRegex(ValueError, "handedness"):
            source_tangent_to_uc([1.0, 0.0, 0.0, 0.5])

    def test_exact_render_domain_count_fails_closed_on_collapse(self):
        neutral = [[float(index), 0.0, 0.0] for index in range(SOURCE_VERTEX_COUNT)]
        mapping = list(range(SOURCE_VERTEX_COUNT)) + [0] * (RENDER_VERTEX_COUNT - SOURCE_VERTEX_COUNT)
        positions = [copy.deepcopy(neutral[index]) for index in mapping]
        basis = {
            "schema": GEOMETRY_BASIS_SCHEMA,
            "id": GEOMETRY_BASIS_ID,
            "side": "right",
            "source_candidate_id": SOURCE_CANDIDATE_ID,
            "source_vertex_count": SOURCE_VERTEX_COUNT,
            "render_vertex_count": RENDER_VERTEX_COUNT,
            "triangle_count": TRIANGLE_COUNT,
            "render_positions": positions,
            "render_normals": [[0.0, 1.0, 0.0] for _ in range(RENDER_VERTEX_COUNT)],
            "render_uvs": [[0.0, 0.0] for _ in range(RENDER_VERTEX_COUNT)],
            "render_tangents": [[1.0, 0.0, 0.0, 1.0] for _ in range(RENDER_VERTEX_COUNT)],
            "render_source_indices": mapping,
            "render_indices": [index % RENDER_VERTEX_COUNT for index in range(TRIANGLE_COUNT * 3)],
        }
        self.assertEqual(len(_validate_geometry_basis(basis, neutral)), RENDER_VERTEX_COUNT)
        collapsed = copy.deepcopy(basis)
        collapsed["render_vertex_count"] = RENDER_VERTEX_COUNT - 1
        with self.assertRaisesRegex(ValueError, "vertex-count"):
            _validate_geometry_basis(collapsed, neutral)


if __name__ == "__main__":
    unittest.main()
