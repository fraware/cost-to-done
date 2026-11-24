"""Independent tests of exact half-open union and validation."""
import itertools
import random
import unittest

from intervals import normalize


class IntervalTests(unittest.TestCase):
    def test_nested_touching_empty_and_negative(self):
        self.assertEqual(normalize([(0, 10), (2, 3), (10, 12), (-5, -1), (4, 4)]),
                         [(-5, -1), (0, 12)])
        self.assertEqual(normalize([]), [])
        self.assertEqual(normalize([(5, 5)]), [])

    def test_invalid(self):
        for bad in (None, (), [(3, 1)], [(True, 4)], [(1, 2.0)], [[1, 2]], [(1,)], [(1, 2, 3)]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                normalize(bad)

    def test_exact_large_endpoints(self):
        n = 10**90
        self.assertEqual(normalize([(n, n+4), (n+2, n+3), (n+4, n+5)]), [(n, n+5)])

    def test_seeded_union_oracle(self):
        rng = random.Random(194)
        for _ in range(200):
            source = [tuple(sorted((rng.randrange(-8, 9), rng.randrange(-8, 9))))
                      for _ in range(rng.randrange(20))]
            original = source.copy()
            expected = set(itertools.chain.from_iterable(range(a, b) for a, b in source))
            got = normalize(source)
            self.assertEqual(source, original)
            self.assertIsNot(got, source)
            self.assertTrue(all(type(pair) is tuple and len(pair) == 2 and pair[0] < pair[1] for pair in got))
            self.assertTrue(all(a[1] < b[0] for a, b in zip(got, got[1:])))
            self.assertEqual(set(itertools.chain.from_iterable(range(a, b) for a, b in got)), expected)
            self.assertEqual(normalize(got), got)
