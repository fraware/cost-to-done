"""Topological ordering tests using a brute-force small-graph oracle."""
import copy
import itertools
import random
import unittest

from dependency_order import build_order


def exhaustive_order(graph):
    for permutation in itertools.permutations(sorted(graph)):
        indices = {name: i for i, name in enumerate(permutation)}
        if all(indices[p] < indices[name] for name, deps in graph.items() for p in deps):
            return list(permutation)
    return None


class DependencyTests(unittest.TestCase):
    def test_lexical_eligibility_and_duplicates(self):
        self.assertEqual(build_order({"z": ["a"], "b": [], "a": [], "c": ["a", "a"]}),
                         ["a", "b", "c", "z"])
        self.assertEqual(build_order({}), [])

    def test_invalid(self):
        for bad in (None, [], {"": []}, {1: []}, {"a": "b"}, {"a": ["missing"]},
                    {"a": [True]}, {"a": [""]}, {"a": ["a"]}, {"a": ["b"], "b": ["a"]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                build_order(bad)

    def test_seeded_brute_force_oracle(self):
        rng = random.Random(7703)
        names = ["a", "b", "c", "d", "e"]
        for _ in range(100):
            shuffled = rng.sample(names, len(names))
            graph = {name: [p for p in names if rng.random() < .19] for name in shuffled}
            original = copy.deepcopy(graph)
            expected = exhaustive_order(graph)
            if expected is None:
                with self.assertRaises(ValueError):
                    build_order(graph)
            else:
                self.assertEqual(build_order(graph), expected)
            self.assertEqual(graph, original)

    def test_deep_chain_without_recursion(self):
        size = 1600
        names = [f"n{i:04d}" for i in range(size)]
        graph = {name: [names[i-1]] if i else [] for i, name in enumerate(names)}
        self.assertEqual(build_order(dict(reversed(list(graph.items())))), names)
