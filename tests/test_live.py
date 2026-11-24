"""Zero-spend validation and mocked execution tests for the live gateway route."""
from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cost_to_done.core import ReceiptError
from cost_to_done.gateway import PriceSchedule
from cost_to_done.ledger import BudgetLedger
from cost_to_done.live import LiveConfig, execute_live, plan_live
from cost_to_done.live_gateway import build_gateway, read_key


class LiveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        (self.root / "src/cost_to_done").mkdir(parents=True)
        (self.root / "experiments/live").mkdir(parents=True)
        task = self.root / "tasks/allocation-repair"
        (task / "environment").mkdir(parents=True)
        (task / "tests").mkdir()
        for rel in ["src/cost_to_done/live_gateway.py", "experiments/live/compose.yaml", "experiments/live/base-compose-ci.yaml", "experiments/live/Dockerfile.pi",
                    "tasks/allocation-repair/task.toml", "tasks/allocation-repair/environment/Dockerfile",
                    "tasks/allocation-repair/tests/test.sh"]:
            (self.root / rel).write_text("fixture\n")
        self.price = self.root / "pricing.json"
        p = PriceSchedule("test-model-1", "2026-11-20", "https://example.com/pricing", "1.5", "4.5")
        self.price.write_text(json.dumps(vars(p)), encoding="utf-8")
        self.key = Path(self.temp.name) / "upstream-secret.txt"
        self.key.write_text("sk-example-unit-test-key-123456789\n")
        self.key.chmod(0o600)
        self.c = LiveConfig(self.root, task, self.root / "runs", "test-model-1", self.price, self.key, "0.25")

    def test_plan_is_zero_spend_and_does_not_read_provider_key(self):
        self.key.unlink()
        result = plan_live(self.c)
        self.assertEqual(result["status"], "plan_only")
        self.assertFalse(result["provider_hard_cap"])
        self.assertFalse((self.root / "runs").exists())
        self.assertNotIn("sk-example", json.dumps(result))

    def test_command_never_contains_upstream_provider_key(self):
        args = self.c.command(task_copy=Path("/task"), token="ctd-temporary-gateway-token")
        self.assertEqual(args[args.index("--api-key-name")+1], "CTD_GATEWAY_TOKEN")
        self.assertIn("--extra-docker-compose", args)
        self.assertNotIn("sk-example-unit-test", " ".join(args))
        self.assertIn("max_output_tokens=4096", args)
        self.assertEqual(args[args.index("--base-url")+1], "http://ctd_gateway:8866/v1")


    def test_responses_only_gpt6_models_fail_closed_during_zero_spend_planning(self):
        for model in ("gpt-6.1-terra", "gpt-6.2-sol", "gpt-6.2-astra", "gpt-5.4-pro"):
            with self.subTest(model=model):
                self.price.write_text(json.dumps(vars(PriceSchedule(
                    model, "2026-11-23", "https://example.com/pricing", "2", "10"))))
                alternate = LiveConfig(
                    self.root, self.c.task, self.c.jobs_dir, model, self.price,
                    self.key, "0.25")
                with self.assertRaisesRegex(ReceiptError, "Responses API"):
                    plan_live(alternate)
                self.assertFalse(self.c.jobs_dir.exists())

    def test_explicit_responses_plan_and_command(self):
        from dataclasses import replace
        cfg = replace(self.c, api="responses", reasoning_effort="low")
        plan = plan_live(cfg)
        self.assertEqual(plan["api"], "responses")
        self.assertEqual(plan["reasoning_effort"], "low")
        args = cfg.command(task_copy=Path("/task"), token="stub")
        self.assertEqual(args[args.index("--api-format") + 1], "openai_responses")
        self.assertIn("model_api=openai-responses", args)
        self.assertIn("reasoning_effort=low", args)
        self.assertFalse(self.c.jobs_dir.exists())
        with self.assertRaises(ReceiptError):
            plan_live(replace(cfg, api="invalid"))

    def test_gpt54_mini_turns_off_reasoning_for_chat_function_tools(self):
        self.price.write_text(json.dumps(vars(PriceSchedule(
            "gpt-5.4-mini", "2026-11-23", "https://example.com/pricing",
            "0.75", "4.5"))))
        cfg = LiveConfig(self.root, self.c.task, self.c.jobs_dir,
                         "gpt-5.4-mini", self.price, self.key, "0.25")
        self.assertEqual(plan_live(cfg)["status"], "plan_only")
        args = cfg.command(task_copy=Path("/task"), token="stub")
        self.assertIn("reasoning_effort=off", args)

    def test_model_price_mismatch_fails_before_execution(self):
        bad = LiveConfig(self.root, self.c.task, self.c.jobs_dir, "other-model", self.price, self.key, "0.25")
        with self.assertRaisesRegex(ReceiptError, "model"):
            plan_live(bad)

    def test_reject_unqualified_arbitrary_task(self):
        other = self.root / "tasks/arbitrary"
        other.mkdir()
        with self.assertRaisesRegex(ReceiptError, "qualified"):
            plan_live(LiveConfig(self.root, other, self.c.jobs_dir, self.c.model, self.price, self.key, "0.25"))

    def test_reject_symlink_inside_qualified_task(self):
        (self.c.task / "bad").symlink_to(self.key)
        with self.assertRaisesRegex(ReceiptError, "symlink"):
            plan_live(self.c)

    def test_reject_unsafe_existing_job(self):
        (self.c.jobs_dir / self.c.job_name).mkdir(parents=True)
        with self.assertRaisesRegex(ReceiptError, "already exists"):
            plan_live(self.c)

    def test_invalid_budget_rejected(self):
        with self.assertRaises(ReceiptError):
            plan_live(LiveConfig(self.root, self.c.task, self.c.jobs_dir, self.c.model, self.price, self.key, "-0.5"))

    def test_secret_permissions_enforced_for_execution(self):
        self.key.chmod(0o644)
        with self.assertRaisesRegex(ReceiptError, "chmod 600"):
            self.c.validated(check_key=True)

    def test_secret_inside_repo_rejected(self):
        inner = self.root / "provider.txt"
        inner.write_text(self.key.read_text())
        inner.chmod(0o600)
        bad = LiveConfig(self.root, self.c.task, self.c.jobs_dir, self.c.model, self.price, inner, "0.25")
        with self.assertRaisesRegex(ReceiptError, "outside repository"):
            bad.validated(check_key=True)

    def test_execution_needs_explicit_approval(self):
        with self.assertRaisesRegex(ReceiptError, "acknowledgement"):
            execute_live(self.c)
        self.assertFalse(self.c.jobs_dir.exists())

    def test_read_key_refuses_missing_or_broken_mount(self):
        with self.assertRaises(ReceiptError):
            read_key(self.root / "missing-key")
        self.key.write_text("bad key with spaces\n")
        with self.assertRaises(ReceiptError):
            read_key(self.key)

    def test_gateway_construction_uses_one_schedule_and_ledger(self):
        g = build_gateway(key_file=self.key, price_file=self.price,
                          ledger_file=Path(self.temp.name)/"ledger.sqlite3",
                          budget_usd="0.25", gateway_token="g"*48)
        self.assertEqual(g.price.model, "test-model-1")
        self.assertEqual(g.ledger.snapshot().limit, "0.25")
        self.assertEqual(g.max_output_cap, 4096)

    def test_live_execution_scrubs_provider_env_and_does_not_claim_invoice(self):
        """Mock subprocess and inspector: no Harbor, Docker, or external API calls."""
        self.key.write_text("sk-example-unit-test-key-123456789\n")
        self.key.chmod(0o600)
        def fake_run(cmd, *, env, log_file, timeout):
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertEqual(env["CTD_RUN_UID"], str(os.getuid()))
            self.assertEqual(env["CTD_RUN_GID"], str(os.getgid()))
            self.assertNotIn("sk-example-unit-test", " ".join(cmd))
            self.assertEqual(env["CTD_PROVIDER_KEY_FILE"], str(self.key))
            self.assertTrue((Path(env["CTD_EVIDENCE_DIR"])).is_dir())
            ledger = BudgetLedger(Path(env["CTD_EVIDENCE_DIR"])/"ledger.sqlite3", budget_usd="0.25")
            ledger.bind_schedule(PriceSchedule.load(self.price).digest)
            ledger.reserve("mock-req-1", "0.04")
            ledger.settle("mock-req-1", "0.0036")
            log_file.write_text("test stub\n")
            return 0
        fake_result = {"complete": True,"observed_trials": 1,"trials": [{"agent":"pi","model":"test-model-1","provider":"openai","outcome":"pass"}]}
        with mock.patch("cost_to_done.live._preflight"),mock.patch("cost_to_done.live._audit_compose_before_live",return_value={"status":"passed"}),mock.patch("cost_to_done.live._run_process",side_effect=fake_run),mock.patch("cost_to_done.live.inspect_harbor_job",return_value=fake_result),mock.patch.dict(os.environ,{"OPENAI_API_KEY":"must-not-forward","GITHUB_TOKEN":"must-not-forward"}):
            result=execute_live(self.c,acknowledged=True)
        self.assertEqual(result["status"], "completed_with_unverified_rate_card_estimate")
        self.assertEqual(result["gateway_snapshot"]["settled"], "0.0036")
        self.assertFalse(result["provider_invoice_reconciled"])
        self.assertFalse(result["provider_side_hard_cap_verified"])
        self.assertTrue(Path(result["summary_file"]).exists())

    def test_network_template_declares_no_public_agent_or_secret_mount(self):
        """Static structure check; Docker network behavior has separate CI tests."""
        project = Path(__file__).resolve().parents[1]
        compose = (project / "experiments/live/compose.yaml").read_text()
        agent_section = compose.split("  main:",1)[1].split("  ctd_gateway:",1)[0]
        self.assertIn("networks: [ctd_agent_net]", agent_section)
        self.assertNotIn("ctd_provider_key", agent_section)
        self.assertNotIn("ctd_provider_net", agent_section)
        self.assertIn("internal: true", compose)
        self.assertIn("secrets: [ctd_provider_key]", compose)
        self.assertNotIn("ports:", compose)
        self.assertIn("file: ${CTD_PROVIDER_KEY_FILE:", compose)


if __name__=="__main__":
    unittest.main()

class TestLiveCli(unittest.TestCase):
    def test_cli_dry_run_does_not_create_files(self):
        from cost_to_done.cli import main
        from io import StringIO
        import contextlib
        # The CLI's argument routing is exercised without any Docker or API access.
        with mock.patch('cost_to_done.cli.plan_live', return_value={'status':'plan_only'}), \
             mock.patch('cost_to_done.cli.execute_live') as exec_mock:
            out = StringIO()
            with contextlib.redirect_stdout(out):
                status = main(['run-harbor-gateway', '--model','test-model-1',
                               '--price-schedule','pricing.json', '--provider-key-file','/not-created',
                               '--budget-usd','0.25'])
            self.assertEqual(status,0)
            self.assertEqual(json.loads(out.getvalue())['status'],'plan_only')
            exec_mock.assert_not_called()

class TestLiveFailureHandling(unittest.TestCase):
    def test_live_process_failure_is_not_reported_as_paid_result(self):
        """The real gateway must never turn Harbor errors into measured success."""
        t = LiveContractTests()
        t.setUp()
        self.addCleanup(t.temp.cleanup)
        with mock.patch("cost_to_done.live._preflight"), \
             mock.patch("cost_to_done.live._audit_compose_before_live",return_value={"status":"passed"}), \
             mock.patch("cost_to_done.live._run_process", return_value=7):
            result = execute_live(t.c, acknowledged=True)
        self.assertEqual(result["status"], "incomplete_or_uncertain")
        self.assertFalse(result["provider_invoice_reconciled"])

    def test_existing_session_rejected_even_without_job_folder(self):
        t=LiveContractTests()
        t.setUp()
        self.addCleanup(t.temp.cleanup)
        (t.c.jobs_dir / ".sessions" / t.c.job_name).mkdir(parents=True)
        with self.assertRaisesRegex(ReceiptError,"already exists"):
            plan_live(t.c)

    def test_missing_price_schedule_rejected_without_provider_call(self):
        t=LiveContractTests()
        t.setUp()
        self.addCleanup(t.temp.cleanup)
        t.price.unlink()
        with self.assertRaises((ReceiptError, OSError)):
            plan_live(t.c)
