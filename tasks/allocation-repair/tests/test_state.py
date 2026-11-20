"""Executable acceptance tests; kept separate from the agent image."""
import unittest

from allocate import allocate_cents


class AllocationRepairTests(unittest.TestCase):
    def test_largest_remainder_and_tie_order(self):
        self.assertEqual(allocate_cents(10, [1, 1, 1]), [4, 3, 3])
        self.assertEqual(allocate_cents(2, [1, 1, 1]), [1, 1, 0])
        self.assertEqual(allocate_cents(7, [0, 1, 2]), [0, 2, 5])

    def test_preservation_and_exact_large_integers(self):
        amount = 10 ** 35 + 7
        weights = [10 ** 30 + 1, 10 ** 30, 3, 0]
        result = allocate_cents(amount, weights)
        self.assertEqual(sum(result), amount)
        self.assertEqual(result[3], 0)
        self.assertTrue(all(type(value) is int and value >= 0 for value in result))
        base = [amount * weight // sum(weights) for weight in weights]
        self.assertTrue(all(x in (b, b + 1) for x, b in zip(result, base)))

    def test_zero_total(self):
        self.assertEqual(allocate_cents(0, [0, 10, 0]), [0, 0, 0])

    def test_invalid_inputs(self):
        for total, weights in [(-1, [1]), (True, [1]), (1.5, [1]),
                               (5, []), (5, [0, 0]), (5, [True, 1]),
                               (5, [-1, 2]), (5, (1, 2)), (5, [0.5, 1])]:
            with self.subTest(total=total, weights=weights):
                with self.assertRaises(ValueError):
                    allocate_cents(total, weights)


if __name__ == "__main__":
    unittest.main()
