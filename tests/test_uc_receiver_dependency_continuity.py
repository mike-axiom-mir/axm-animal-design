from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from axm_animal_design.uc_receiver_dependency_continuity import (
    STATE,
    build_continuity_receipt,
    commonjs_dependency_closure,
)


class UcReceiverDependencyContinuityTests(unittest.TestCase):
    def make_receiver(self, root: Path, *, base_text: str = "module.exports = {inspect: () => ({pass: true})};\n", extra_dependency: bool = False) -> None:
        directory = root / "capabilities/platform-hands/shared/asset-hands"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "gltf-codec.js").write_text(base_text, encoding="utf-8")
        extra = "\nrequire('./extra');" if extra_dependency else ""
        (directory / "rigged-gltf-codec.js").write_text(
            "const base = require('./gltf-codec');\nmodule.exports = base;" + extra + "\n",
            encoding="utf-8",
        )
        if extra_dependency:
            (directory / "extra.js").write_text("module.exports = {};\n", encoding="utf-8")

    def test_discovers_transitive_local_receiver_closure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_receiver(root)
            closure = commonjs_dependency_closure(root)
            self.assertEqual(
                set(closure),
                {
                    "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js",
                    "capabilities/platform-hands/shared/asset-hands/gltf-codec.js",
                },
            )
            self.assertTrue(all(len(value) == 40 for value in closure.values()))

    def test_rejects_hidden_dependency_added_after_tested_receiver(self):
        with tempfile.TemporaryDirectory() as tested_temp, tempfile.TemporaryDirectory() as current_temp:
            tested = Path(tested_temp)
            current = Path(current_temp)
            self.make_receiver(tested)
            self.make_receiver(current, extra_dependency=True)
            tested_footprint = commonjs_dependency_closure(tested)
            current_footprint = commonjs_dependency_closure(current)
            with self.assertRaisesRegex(ValueError, "receiver dependency closure drift"):
                build_continuity_receipt(
                    technical_art_head="ta",
                    tested_uc_head="tested",
                    current_uc_head="current",
                    source_glb_sha256="source",
                    tested_footprint=tested_footprint,
                    current_footprint=current_footprint,
                    expected_tested_footprint=tested_footprint,
                    tested_inspection={"pass": True, "vertices": 84},
                    current_inspection={"pass": True, "vertices": 84},
                    tested_is_ancestor_of_current=True,
                )

    def test_rejects_base_dependency_mutation_even_when_wrapper_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tested_temp, tempfile.TemporaryDirectory() as current_temp:
            tested = Path(tested_temp)
            current = Path(current_temp)
            self.make_receiver(tested)
            self.make_receiver(current, base_text="module.exports = {inspect: () => ({pass: false})};\n")
            tested_footprint = commonjs_dependency_closure(tested)
            current_footprint = commonjs_dependency_closure(current)
            wrapper = "capabilities/platform-hands/shared/asset-hands/rigged-gltf-codec.js"
            self.assertEqual(tested_footprint[wrapper], current_footprint[wrapper])
            with self.assertRaisesRegex(ValueError, "changed=.*gltf-codec.js"):
                build_continuity_receipt(
                    technical_art_head="ta",
                    tested_uc_head="tested",
                    current_uc_head="current",
                    source_glb_sha256="source",
                    tested_footprint=tested_footprint,
                    current_footprint=current_footprint,
                    expected_tested_footprint=tested_footprint,
                    tested_inspection={"pass": True},
                    current_inspection={"pass": True},
                    tested_is_ancestor_of_current=True,
                )

    def test_builds_narrow_continuity_receipt(self):
        footprint = {"receiver.js": "a" * 40}
        inspection = {"pass": True, "vertices": 84, "triangles": 80}
        receipt = build_continuity_receipt(
            technical_art_head="ta",
            tested_uc_head="tested",
            current_uc_head="current",
            source_glb_sha256="source",
            tested_footprint=footprint,
            current_footprint=dict(footprint),
            expected_tested_footprint=dict(footprint),
            tested_inspection=inspection,
            current_inspection=dict(inspection),
            tested_is_ancestor_of_current=True,
        )
        self.assertEqual(receipt["state"], STATE)
        self.assertTrue(receipt["truth_boundary"]["uc_receiver_executable_source_closure_identical"])
        self.assertFalse(receipt["truth_boundary"]["godot_target_host_rerun_at_current_uc_head"])
        self.assertFalse(receipt["truth_boundary"]["runtime_product_implementation_established"])


if __name__ == "__main__":
    unittest.main()
