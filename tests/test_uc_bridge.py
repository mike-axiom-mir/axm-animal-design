import copy
import hashlib
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from axm_animal_design.organic_form import build_form_study
from axm_animal_design.uc_bridge import (
    SOURCE_COORDINATES,
    TARGET_COORDINATES,
    adapt_form_evidence_for_uc,
    adapt_geometry_candidate_for_uc,
    build_bridge_evidence,
    build_candidate_source_primitive,
    require_candidate_identity,
)

SPEC = json.loads((ROOT / "examples/quadruped_neutral_001.json").read_text())
NEUTRAL_MATERIAL = {"base_color": [0.72, 0.72, 0.70, 1.0], "metallic": 0.0, "roughness": 0.78}


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _digest(value):
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


class UCSurfaceBridgeTests(unittest.TestCase):
    def test_exact_quadruped_adapts_without_mutating_source(self):
        evidence = build_form_study(SPEC)
        before = copy.deepcopy(evidence)
        uc_surface = adapt_form_evidence_for_uc(evidence)
        self.assertEqual(evidence, before)
        self.assertEqual(uc_surface["schema"], "axm.surface-3d/v0.1")
        self.assertEqual(uc_surface["name"], evidence["name"])
        self.assertEqual(len(uc_surface["primitives"]), evidence["counts"]["regions"])
        self.assertNotIn("units", uc_surface)
        for primitive in uc_surface["primitives"]:
            self.assertRegex(primitive["material"]["color"], r"^#[0-9A-F]{8}$")
            self.assertNotIn("base_color", primitive["material"])

    def test_coordinate_mapping_and_winding_preserve_face_normal_agreement(self):
        evidence = build_form_study(SPEC)
        source = evidence["surface"]["primitives"][0]
        target = adapt_form_evidence_for_uc(evidence)["primitives"][0]
        self.assertEqual(target["positions"][0], [-source["positions"][0][1], source["positions"][0][2], source["positions"][0][0]])
        self.assertEqual(target["indices"][:3], [source["indices"][0], source["indices"][2], source["indices"][1]])
        for offset in range(0, min(len(target["indices"]), 90), 3):
            ia, ib, ic = target["indices"][offset:offset + 3]
            a, b, c = target["positions"][ia], target["positions"][ib], target["positions"][ic]
            face = _cross(_sub(b, a), _sub(c, a))
            for index in (ia, ib, ic):
                self.assertGreater(_dot(face, target["normals"][index]), 0.0)

    def test_bridge_fails_closed_on_unknown_coordinates_or_units(self):
        evidence = build_form_study(SPEC)
        wrong_axis = copy.deepcopy(evidence)
        wrong_axis["coordinate_system"] = "+Z forward, +Y up"
        with self.assertRaisesRegex(ValueError, "coordinate system"):
            adapt_form_evidence_for_uc(wrong_axis)
        wrong_units = copy.deepcopy(evidence)
        wrong_units["surface"]["units"] = "cm"
        with self.assertRaisesRegex(ValueError, "units='m'"):
            adapt_form_evidence_for_uc(wrong_units)

    def test_bridge_receipt_keeps_exact_cross_repo_identity_and_nonclaims(self):
        evidence = build_form_study(SPEC)
        surface = adapt_form_evidence_for_uc(evidence)
        verification = {"passed": True, "triangles": evidence["counts"]["triangles"]}
        receipt = build_bridge_evidence(
            evidence,
            surface,
            uc_commit="640bd7dc177b90e023aad879b4c00051df7f4ee3",
            glb_sha256="a" * 64,
            uc_specification_sha256="b" * 64,
            uc_verification=verification,
        )
        self.assertEqual(receipt["status"], "PASS_EXACT_CROSS_REPO_SURFACE_TO_GLB")
        self.assertEqual(receipt["source"]["coordinate_system"], SOURCE_COORDINATES)
        self.assertEqual(receipt["bridge"]["target_coordinates"], TARGET_COORDINATES)
        self.assertTrue(receipt["bridge"]["handedness_change"])
        self.assertTrue(receipt["bridge"]["triangle_winding_reversed"])
        self.assertIn("does not prove visual quality", receipt["truth"])

    def test_geometry_candidate_gets_transport_only_normals_and_exact_uc_mapping(self):
        candidate = {
            "id": "connected-test",
            "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "indices": [0, 1, 2],
        }
        before = copy.deepcopy(candidate)
        primitive = build_candidate_source_primitive(candidate, material=NEUTRAL_MATERIAL)
        self.assertEqual(candidate, before)
        self.assertEqual(len(primitive["normals"]), 3)
        self.assertEqual(primitive["normals"], [[0.0, 0.0, 1.0]] * 3)
        self.assertEqual(primitive["colors"], [NEUTRAL_MATERIAL["base_color"]] * 3)

        surface = adapt_geometry_candidate_for_uc(
            candidate,
            name="connected candidate transport",
            material=NEUTRAL_MATERIAL,
        )
        group = surface["primitives"][0]
        self.assertEqual(group["positions"], [[-0.0, 0.0, 0.0], [-0.0, 0.0, 1.0], [-1.0, 0.0, 0.0]])
        self.assertEqual(group["indices"], [0, 2, 1])
        self.assertEqual(group["normals"], [[-0.0, 1.0, 0.0]] * 3)
        self.assertEqual(group["material"]["color"], "#B8B8B3FF")

    def test_geometry_candidate_identity_fails_closed_on_position_drift(self):
        candidate = {
            "id": "connected-test",
            "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "indices": [0, 1, 2],
        }
        expected = _digest(candidate)
        self.assertEqual(require_candidate_identity(candidate, expected), expected)
        drifted = copy.deepcopy(candidate)
        drifted["positions"][0][0] = 0.001
        with self.assertRaisesRegex(ValueError, "geometry candidate identity drift"):
            require_candidate_identity(drifted, expected)

    def test_transport_normal_builder_rejects_degenerate_candidate(self):
        candidate = {
            "id": "degenerate",
            "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            "indices": [0, 1, 2],
        }
        with self.assertRaisesRegex(ValueError, "degenerate triangle"):
            build_candidate_source_primitive(candidate, material=NEUTRAL_MATERIAL)


if __name__ == "__main__":
    unittest.main()
