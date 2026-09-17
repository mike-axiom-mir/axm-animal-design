from __future__ import annotations

from copy import deepcopy
import json
import os
import unittest
from pathlib import Path

from axm_animal_design.connected_deformation import digest
from axm_animal_design.organic_elbow_balanced_relief import RIG_PLAN_DIGEST
from axm_animal_design.organic_elbow_dense_search import build_search_variant
from axm_animal_design.organic_elbow_source_successor import (
    PROFILE_DIGEST,
    SOURCE_DIGEST,
    SELECTED_REVIEW_CANDIDATE_DIGEST,
    SELECTED_REVIEW_GEOMETRY_DIGEST,
    SOURCE_SUCCESSOR_CANDIDATE_DIGEST,
    build_source_owned_elbow_successor,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = json.loads((ROOT / "examples" / "quadruped_neutral_001.json").read_text(encoding="utf-8"))
PROFILE = json.loads((ROOT / "examples" / "quadruped_elbow_source_successor_003.json").read_text(encoding="utf-8"))


def _geometry(candidate):
    return {
        key: candidate[key]
        for key in ("positions", "indices", "path_points", "radii", "segments")
    }


def _plan_from_env():
    value = os.environ.get("AXM_RIG_PLAN")
    if not value:
        return None
    return json.loads(Path(value).read_text(encoding="utf-8"))


class OrganicElbowSourceSuccessorTests(unittest.TestCase):
    def test_exact_source_owned_successor_identity_and_scope(self):
        self.assertEqual(digest(SOURCE), SOURCE_DIGEST)
        self.assertEqual(digest(PROFILE), PROFILE_DIGEST)
        candidate, scope = build_source_owned_elbow_successor(SOURCE, PROFILE)
        self.assertEqual(digest(candidate), SOURCE_SUCCESSOR_CANDIDATE_DIGEST)
        self.assertEqual(digest(_geometry(candidate)), SELECTED_REVIEW_GEOMETRY_DIGEST)
        self.assertEqual(scope["moved_vertex_indices"], list(range(11, 21)))
        self.assertEqual(scope["moved_vertex_count"], 10)
        self.assertEqual(scope["maximum_neutral_vertex_delta_m"], 0.002608891428)
        self.assertEqual(scope["maximum_positive_bound_expansion_m"], 0.002567174)
        self.assertTrue(candidate["organic_source_successor"]["source_owned_successor"])
        self.assertFalse(candidate["organic_source_successor"]["canonical"])
        self.assertFalse(candidate["truth_boundary"]["rigging_accepted"])
        self.assertFalse(candidate["truth_boundary"]["animation_accepted"])
        self.assertFalse(candidate["truth_boundary"]["runtime_ready"])

    def test_profile_drift_fails_closed(self):
        broken = deepcopy(PROFILE)
        broken["form_change"]["bend_plane_radius_m"] = 0.0884
        with self.assertRaisesRegex(ValueError, "profile identity drift"):
            build_source_owned_elbow_successor(SOURCE, broken)

    def test_base_source_drift_fails_closed(self):
        broken = deepcopy(SOURCE)
        broken["landmarks"]["elbow_L"][0] += 0.001
        with self.assertRaisesRegex(ValueError, "organic source identity drift"):
            build_source_owned_elbow_successor(broken, PROFILE)

    def test_exact_prior_selected_review_shape_is_reproduced_when_donor_is_available(self):
        plan = _plan_from_env()
        if plan is None or digest(plan) != RIG_PLAN_DIGEST:
            self.skipTest("exact pinned Rigging donor is supplied by evidence workflow")
        source_candidate, _ = build_source_owned_elbow_successor(SOURCE, PROFILE)
        review_candidate, _ = build_search_variant(SOURCE, plan, 0.0885, 1.03)
        self.assertEqual(digest(review_candidate), SELECTED_REVIEW_CANDIDATE_DIGEST)
        self.assertEqual(digest(_geometry(review_candidate)), SELECTED_REVIEW_GEOMETRY_DIGEST)
        self.assertEqual(_geometry(source_candidate), _geometry(review_candidate))


if __name__ == "__main__":
    unittest.main()
