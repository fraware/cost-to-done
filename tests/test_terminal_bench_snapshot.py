"""Aggregate analysis tests; upstream trial-level completeness is never inferred."""
from __future__ import annotations

import json
import unittest
from scripts.analyze_terminal_bench import extract, read_json


def record(cost=349.16, successes=203, n_trials=330, **extra):
    return json.dumps({"leaderboard": "4-1-0", "source_filter": {"model_name": "openai/test"},
                       "metrics": {"total_cost_usd": cost, "successes": successes,
                                   "n_trials": n_trials}, **extra}).encode()


class AggregateTests(unittest.TestCase):
    def test_exact_ratio_and_unknown_completeness(self):
        row = extract("x", "blob", record())
        self.assertEqual(row["reported_inference_cost_per_success_usd"], "1.720000")
        self.assertFalse(row["trial_cost_completeness_verified"])

    def test_missing_and_zero_cost(self):
        for cost in (None, 0, -1, True):
            with self.subTest(cost=cost):
                self.assertIsNone(extract("x", "blob", record(cost=cost))[
                    "reported_inference_cost_per_success_usd"])

    def test_zero_success_and_invalid_counts(self):
        for successes in (0, 331, True):
            with self.subTest(successes=successes):
                self.assertIsNone(extract("x", "blob", record(successes=successes))[
                    "reported_inference_cost_per_success_usd"])

    def test_duplicate_identifiers_withhold_ratio(self):
        row = extract("x", "blob", record(successes=1, n_trials=2, trials=["a", "a"]))
        self.assertEqual(row["state"], "trial_identifier_mismatch")
        self.assertIsNone(row["reported_inference_cost_per_success_usd"])

    def test_wrong_target_and_duplicate_json(self):
        self.assertIsNone(extract("x", "blob", b'{"leaderboard":"4-0-0"}'))
        with self.assertRaises(ValueError):
            read_json(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            read_json(b'{"a":NaN}')
