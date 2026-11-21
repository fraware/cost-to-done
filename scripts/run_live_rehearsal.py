"""CI-only execution of the actual isolated live runner against a fake model."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from cost_to_done.live import LiveConfig, execute_live

FAKE_KEY = "ctd-fake-upstream-key-for-tests-12345678"


def run(root: Path, outputs: Path, key_file: Path) -> dict:
    """Substitute one trusted Compose overlay; refuse real provider secrets."""
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CTD_REHEARSAL_ONLY") != "1":
        raise RuntimeError("CI-only rehearsal guard absent")
    if key_file.read_text(encoding="ascii").strip() != FAKE_KEY:
        raise RuntimeError("rehearsal requires the exact fictional credential")
    if outputs.exists():
        raise RuntimeError("rehearsal output path already exists")
    root = root.resolve(strict=True)
    overlay = root / "tests/live/compose-rehearsal.yaml"
    if overlay.is_symlink() or not overlay.is_file():
        raise RuntimeError("trusted rehearsal overlay missing")

    config = LiveConfig(
        repo_root=root, task=root / "tasks/allocation-repair",
        jobs_dir=outputs, model="test-model-1",
        price_schedule=root / "tests/fixtures/mock-price-schedule.json",
        key_file=key_file, budget_usd="5",
        job_name="rehearsal-scripted", max_turns=3, max_wall_seconds=900,
    )
    production_command = LiveConfig.command

    def with_mock_overlay(self: LiveConfig, *, task_copy: Path, token: str) -> list[str]:
        command = production_command(self, task_copy=task_copy, token=token)
        return [*command, "--extra-docker-compose", str(overlay)]

    with patch.object(LiveConfig, "command", with_mock_overlay):
        result = execute_live(config, acknowledged=True)
    if result["status"] != "completed_with_unverified_rate_card_estimate":
        raise RuntimeError("mock execution incomplete: " + result["status"])
    return {
        "status": "mock-live-rehearsal-complete",
        "mock_only": True,
        "verifier_outcome": result["trial"]["outcome"],
        "fictional_estimate_usd": result["gateway_snapshot"]["settled"],
        "provider_invoice_reconciled": result["provider_invoice_reconciled"],
    }


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: run_live_rehearsal.py ROOT OUTPUT_DIR FAKE_KEY_FILE")
    print(json.dumps(run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), indent=2))
