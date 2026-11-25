"""Synthetic design-structure tests; no model calls or real task evidence."""
import copy
import hashlib
import unittest
from collections import Counter

from cost_to_done.core import ReceiptError
from scripts.plan_flagship import build_plan, validate_plan


def token(label):
    return hashlib.sha256(label.encode()).hexdigest()


def specification():
    strata = ["algorithm", "state", "parsing", "integration"]
    return {
        "schema_version": 1, "seed": 20261124,
        "screening_log_sha256": token("screening"),
        "harness_sha256": token("harness"),
        "retry_policy_sha256": token("retry"),
        "analysis_protocol_sha256": token("analysis"),
        "allowance_per_trial_usd": "1.25", "max_total_usd": "375",
        "tasks": [
            {"id": f"task-{i:02d}", "repository_group": f"repo-{i // 4}",
             "stratum": strata[i % 4],
             **{field: token(f"{field}-{i}") for field in
                ("task_input_sha256", "qualification_sha256",
                 "permission_record_sha256", "holdout_record_sha256")}}
            for i in range(20)],
        "configurations": [
            {"id": f"config-{i}", "model": f"fictional-model-{i}",
             **{field: token(f"{field}-{i}") for field in
                ("configuration_sha256", "price_schedule_sha256",
                 "route_qualification_sha256")}}
            for i in range(5)],
    }


class FlagshipPlanTests(unittest.TestCase):
    def test_complete_matched_support_and_balanced_orders(self):
        plan = build_plan(specification())
        validate_plan(plan)
        rows = plan["trials"]
        self.assertEqual(len(rows), 300)
        self.assertEqual(len({r["trial_id"] for r in rows}), 300)
        counts = Counter((r["task"], r["configuration"], r["repetition"]) for r in rows)
        self.assertEqual(len(counts), 300)
        self.assertEqual(set(counts.values()), {1})
        positions = Counter((r["configuration"], r["position"]) for r in rows)
        self.assertEqual(len(positions), 25)
        self.assertEqual(set(positions.values()), {12})
        pairs = Counter()
        for start in range(0, 300, 5):
            block = rows[start:start + 5]
            self.assertEqual(len({(r["task"], r["repetition"]) for r in block}), 1)
            self.assertEqual(len({r["configuration"] for r in block}), 5)
            pairs.update((a["configuration"], b["configuration"])
                         for a, b in zip(block, block[1:]))
        self.assertEqual(len(pairs), 20)
        self.assertEqual(set(pairs.values()), {12})
        self.assertEqual(plan["estimated_admission_total_usd"], "375")
        self.assertIs(plan["paid_execution_authorized"], False)
        self.assertIs(plan["commitments_independently_verified"], False)

    def test_input_order_invariance(self):
        spec = specification()
        original = build_plan(spec)
        spec["tasks"].reverse()
        spec["configurations"].reverse()
        self.assertEqual(original, build_plan(spec))

    def test_insufficient_budget(self):
        spec = specification()
        spec["max_total_usd"] = "374.999999999999"
        with self.assertRaises(ReceiptError):
            build_plan(spec)

    def test_reject_duplicate_task_commitment(self):
        spec = specification()
        spec["tasks"][1]["task_input_sha256"] = spec["tasks"][0]["task_input_sha256"]
        with self.assertRaises(ReceiptError):
            build_plan(spec)

    def test_reject_missing_permission(self):
        spec = specification()
        del spec["tasks"][0]["permission_record_sha256"]
        with self.assertRaises(ReceiptError):
            build_plan(spec)

    def test_reject_unbalanced_sampling_frame(self):
        spec = specification()
        spec["tasks"][4]["repository_group"] = "repo-0"
        with self.assertRaises(ReceiptError):
            build_plan(spec)

    def test_reject_mutated_schedule_and_authorization(self):
        original = build_plan(specification())
        for field, value in (("paid_execution_authorized", True),
                             ("planned_trial_count", 299)):
            plan = copy.deepcopy(original)
            plan[field] = value
            with self.assertRaises(ReceiptError):
                validate_plan(plan)
        plan = copy.deepcopy(original)
        plan["trials"][0]["configuration"] = plan["trials"][1]["configuration"]
        with self.assertRaises(ReceiptError):
            validate_plan(plan)
