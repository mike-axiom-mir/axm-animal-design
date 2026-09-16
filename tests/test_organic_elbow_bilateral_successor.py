from __future__ import annotations

from copy import deepcopy
import json
import unittest
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_bilateral_successor import (
    PROFILE_DIGEST,
    RIGHT_GEOMETRY_DIGEST,
    RIGHT_SUCCESSOR_DIGEST,
    build_bilateral_elbow_source_successor,
)
from axm_animal_design.organic_elbow_source_successor import (
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST as LEFT_SUCCESSOR_DIGEST,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))
LEFT_PROFILE = json.loads((ROOT / "examples" / "quadruped_elbow_source_successor_003.json").read_text(encoding="utf-8"))
BILATERAL_PROFILE = json.loads((ROOT / "examples" / "quadruped_elbow_bilateral_successor_003.json").read_text(encoding="utf-8"))


def _geometry(candidate):
    return {
        key: candidate[key]
        for key in ("positions", "indices", "path_points", "radii", "segments")
    }


class OrganicElbowBilateralSuccessorTests(unittest.TestCase):
    def test_exact_right_successor_is_mirrored_from_left_source_owned_shape(self):
        self.assertEqual(digest(BILATERAL_PROFILE), PROFILE_DIGEST)
        left, right, scope = build_bilateral_elbow_source_successor(
            SOURCE, LEFT_PROFILE, BILATERAL_PROFILE
        )
        self.assertEqual(digest(left), LEFT_SUCCESSOR_DIGEST)
        self.assertEqual(digest(right), RIGHT_SUCCESSOR_DIGEST)
        self.assertEqual(digest(_geometry(right)), RIGHT_GEOMETRY_DIGEST)
        self.assertEqual(scope["result"], "PASS_BILATERAL_SOURCE_PROPAGATION_EXACT_MIRROR")
        self.assertEqual(scope["right_moved_vertex_indices"], list(range(11, 21)))
        self.assertEqual(scope["right_moved_vertex_count"], 10)
        self.assertEqual(scope["right_maximum_neutral_vertex_delta_m"], 0.002608891428)
        self.assertEqual(scope["right_maximum_outward_bound_expansion_m"], 0.002567174)
        self.assertEqual(scope["mirror"]["maximum_path_residual_m"], 0.0)
        self.assertEqual(scope["mirror"]["maximum_position_residual_m"], 0.0)
        self.assertEqual(scope["mirror"]["vertex_correspondence_count"], 42)
        self.assertFalse(scope["canonical"])
        self.assertFalse(right["truth_boundary"]["rigging_accepted"])
        self.assertFalse(right["truth_boundary"]["animation_accepted"])
        self.assertFalse(right["truth_boundary"]["runtime_ready"])

    def test_bilateral_profile_drift_fails_closed(self):
        broken = deepcopy(BILATERAL_PROFILE)
        broken["right_form_change"]["bend_plane_radius_m"] = 0.0884
        with self.assertRaisesRegex(ValueError, "profile identity drift"):
            build_bilateral_elbow_source_successor(SOURCE, LEFT_PROFILE, broken)

    def test_left_dependency_drift_fails_closed(self):
        broken = deepcopy(LEFT_PROFILE)
        broken["form_change"]["joint_axis_width_scale"] = 1.029
        with self.assertRaises(ValueError):
            build_bilateral_elbow_source_successor(SOURCE, broken, BILATERAL_PROFILE)

    def test_base_source_drift_fails_closed(self):
        broken = deepcopy(SOURCE)
        broken["landmarks"]["elbow_R"][1] -= 0.001
        with self.assertRaisesRegex(ValueError, "organic source identity drift"):
            build_bilateral_elbow_source_successor(broken, LEFT_PROFILE, BILATERAL_PROFILE)


if __name__ == "__main__":
    unittest.main()
