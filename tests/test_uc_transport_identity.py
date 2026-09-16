from __future__ import annotations

import unittest

from axm_animal_design.uc_transport_identity import project_candidate_transport_id


class UCTransportIdentityTests(unittest.TestCase):
    def test_projection_changes_only_transport_id(self) -> None:
        candidate = {
            "id": "domain-owned-candidate-name-that-may-be-longer-than-a-receiver-allows",
            "positions": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "indices": [0, 1, 2],
        }
        projected, mapping = project_candidate_transport_id(candidate, portable_group_id="animal-right-mirror-003")
        self.assertEqual(candidate["id"], "domain-owned-candidate-name-that-may-be-longer-than-a-receiver-allows")
        self.assertEqual(projected["id"], "animal-right-mirror-003")
        self.assertEqual(projected["positions"], candidate["positions"])
        self.assertEqual(projected["indices"], candidate["indices"])
        self.assertFalse(mapping["source_candidate_mutated"])
        self.assertTrue(mapping["positions_preserved"])
        self.assertTrue(mapping["indices_preserved"])

    def test_projection_rejects_nonportable_receiver_id(self) -> None:
        candidate = {"id": "source", "positions": [[0.0, 0.0, 0.0]], "indices": [0, 0, 0]}
        with self.assertRaises(ValueError):
            project_candidate_transport_id(candidate, portable_group_id="bad receiver id with spaces")
        with self.assertRaises(ValueError):
            project_candidate_transport_id(candidate, portable_group_id="a" * 81)


if __name__ == "__main__":
    unittest.main()
