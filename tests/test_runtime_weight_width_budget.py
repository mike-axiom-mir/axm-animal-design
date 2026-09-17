from __future__ import annotations

import math
import unittest

from axm_animal_design.runtime_weight_width_budget import MAX_U16, quantize_weight_row_u16


class RuntimeWeightWidthBudgetTests(unittest.TestCase):
    def test_endpoints_remain_exact(self) -> None:
        self.assertEqual(quantize_weight_row_u16([1.0, 0.0, 0.0, 0.0]), [MAX_U16, 0, 0, 0])
        self.assertEqual(quantize_weight_row_u16([0.0, 1.0, 0.0, 0.0]), [0, MAX_U16, 0, 0])

    def test_largest_remainder_preserves_integer_sum(self) -> None:
        source = [0.987055003643, 0.012945021503, 0.0, 0.0]
        packed = quantize_weight_row_u16(source)
        self.assertEqual(sum(packed), MAX_U16)
        decoded = [value / MAX_U16 for value in packed]
        self.assertAlmostEqual(sum(decoded), 1.0, places=15)
        self.assertLessEqual(max(abs(left - right) for left, right in zip(source, decoded)), 1.0 / MAX_U16)

    def test_four_way_row(self) -> None:
        packed = quantize_weight_row_u16([0.1, 0.2, 0.3, 0.4])
        self.assertEqual(sum(packed), MAX_U16)

    def test_invalid_rows_fail_closed(self) -> None:
        for row in ([0.5, 0.4, 0.0, 0.0], [1.01, -0.01, 0.0, 0.0], [math.nan, 0.0, 0.0, 0.0]):
            with self.assertRaises(ValueError):
                quantize_weight_row_u16(list(row))


if __name__ == "__main__":
    unittest.main()
