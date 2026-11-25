"""Synthetic planner and authorization tests; no provider calls."""
from __future__ import annotations

import copy
import hashlib
import os
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from cost_to_done.core import ReceiptError
from cost_to_done.upstream_pilot import STARTERS, MODELS, trusted_upstream_dispatch, validate_upstream_starter
from scripts.run_upstream_pilot import SCOPE, build_plan, summarize, validate_plan


def token(label):
    return hashlib.sha256(label.encode()).hexdigest()


def make_plan():
    return build_plan({name: token(name) for name in STARTERS},
                      {model: token(model) for model in MODELS}, "a"*40)


def make_record(plan, trial, *, passed=True):
    task, model = trial["task"], trial["model"]
    return {
        "trial_id": trial["id"], "scope": SCOPE, "plan_sha256": plan["plan_sha256"],
        "model": model, "task_input_sha256": STARTERS[task],
        "qualification_sha256": plan["qualification_digests"][task],
        "price_schedule_sha256": plan["price_schedule_digests"][model],
        "repository_execution_scope": "fixed_public_upstream_pilot",
        "trial_status": "completed_with_unverified_rate_card_estimate",
        "api": "responses", "reasoning_effort": "low", "mock_only": False,
        "ledger_observed": True, "provider_invoice_reconciled": False,
        "provider_spend_limit_verified": False, "verifier_independently_reexecuted": False,
        "harbor_trial_outcome": "pass" if passed else "fail",
        "gateway_pending": 0, "gateway_uncertain": 0, "gateway_breached": False,
        "gateway_recorded_calls": 1, "gateway_rate_card_estimate_usd": "0.01",
        "harbor_task_checksum": token(task),
        "harbor_raw_result_sha256": token(trial["id"]),
    }


class UpstreamPilotTests(unittest.TestCase):
    def test_guard_checks_all_fields(self):
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "fraware/cost-to-done",
               "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "GITHUB_RUN_ATTEMPT": "1", "CTD_UPSTREAM_PILOT_AUTHORIZED": "1",
               "GITHUB_WORKFLOW_REF": "fraware/cost-to-done/.github/workflows/upstream-paid-pilot.yml@refs/heads/main"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(trusted_upstream_dispatch())
        for key in env:
            with self.subTest(key=key), patch.dict(os.environ, {**env, key: "invalid"}, clear=True):
                self.assertFalse(trusted_upstream_dispatch())

    def test_allowlist_rejects_changed_task(self):
        name = next(iter(STARTERS))
        with patch("cost_to_done.upstream_pilot._manifest",
                   return_value={"task": name, "task_input_sha256": STARTERS[name]}):
            self.assertEqual(validate_upstream_starter(Path("unused"))["task"], name)
        for task in ("arbitrary-task", name):
            with patch("cost_to_done.upstream_pilot._manifest",
                       return_value={"task": task, "task_input_sha256": "0"*64}):
                with self.assertRaises(ReceiptError):
                    validate_upstream_starter(Path("unused"))

    def test_exact_support_and_balanced_order(self):
        plan = make_plan()
        validate_plan(plan)
        self.assertEqual(plan["planned_trials"], 16)
        self.assertEqual(plan["aggregate_admission_allowance_usd"], "16")
        rows = plan["trials"]
        self.assertEqual(len({r["id"] for r in rows}), 16)
        self.assertEqual(set(Counter((r["task"], r["model"]) for r in rows).values()), {2})
        self.assertEqual(set(Counter(r["model"] for r in rows[::2]).values()), {4})
        for start in range(0, 16, 2):
            self.assertEqual(rows[start]["task"], rows[start+1]["task"])
            self.assertEqual(rows[start]["repetition"], rows[start+1]["repetition"])
        mutated = copy.deepcopy(plan)
        mutated["trials"].pop()
        with self.assertRaises(ReceiptError):
            validate_plan(mutated)

    def test_complete_cost_includes_failures(self):
        plan = make_plan()
        model = sorted(MODELS)[0]
        records = [make_record(plan, t, passed=t["model"] != model or t["repetition"] == 1)
                   for t in plan["trials"]]
        result = summarize(plan, records)
        self.assertTrue(result["complete_matched_accounting"])
        self.assertEqual(result["configurations"][0]["cost_per_completion"],
                         {"numerator_usd": "0.08", "denominator": 4})
        self.assertEqual(result["configurations"][1]["cost_per_completion"],
                         {"numerator_usd": "0.08", "denominator": 8})

    def test_missing_uncertain_and_mismatched_withhold_ratios(self):
        plan = make_plan()
        records = [make_record(plan, t) for t in plan["trials"]]
        for observations in (records[:1], records[:-1], []):
            result = summarize(plan, observations)
            self.assertFalse(result["complete_matched_accounting"])
            self.assertTrue(all(x["cost_per_completion"] is None for x in result["configurations"]))
        records[0]["gateway_uncertain"] = 1
        self.assertFalse(summarize(plan, records)["complete_matched_accounting"])
        records[0]["gateway_uncertain"] = 0
        records[0]["harbor_task_checksum"] = "0"*64
        self.assertFalse(summarize(plan, records)["complete_matched_accounting"])

    def test_reject_duplicate_or_wrong_trial(self):
        plan = make_plan()
        records = [make_record(plan, t) for t in plan["trials"]]
        records[1]["harbor_raw_result_sha256"] = records[0]["harbor_raw_result_sha256"]
        with self.assertRaises(ReceiptError):
            summarize(plan, records)
        with self.assertRaises(ReceiptError):
            summarize(plan, records[1:])
