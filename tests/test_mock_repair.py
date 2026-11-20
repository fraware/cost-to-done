"""Verify the scripted model fixture and its tool-call protocol."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

MODULE = Path(__file__).parent / "harbor" / "mock_repair.py"
spec = importlib.util.spec_from_file_location("ctd_mock_repair", MODULE)
assert spec is not None and spec.loader is not None
mock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock)


class ScriptedRepairTests(unittest.TestCase):
    def test_reference_is_valid_and_passes_independent_task_cases(self):
        space = {}
        exec(mock.REPAIR_SOURCE, space)
        allocate = space["allocate_cents"]
        self.assertEqual(allocate(10, [1, 1, 1]), [4, 3, 3])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])
        self.assertEqual(allocate(7, [0, 1, 2]), [0, 2, 5])
        amount = 10**35 + 7
        self.assertEqual(sum(allocate(amount, [10**30 + 1, 10**30, 3, 0])), amount)
        self.assertEqual(allocate(0, [0, 10, 0]), [0, 0, 0])
        for amount, weights in [(-1, [1]), (True, [1]), (5, []), (5, [0, 0]), (5, [-1, 2]), (5, (1, 2))]:
            with self.subTest(amount=amount, weights=weights):
                with self.assertRaises(ValueError):
                    allocate(amount, weights)

    def test_first_turn_only_calls_declared_tool(self):
        first, reason = mock.scripted_reply({"messages": [{"role": "user", "content": "repair"}],
                                             "tools": [{"function": {"name": "write"}}]})
        self.assertEqual(reason, "tool_calls")
        call = first["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "write")
        self.assertEqual(call["id"], mock.CALL_ID)
        self.assertEqual(json.loads(call["function"]["arguments"])["path"], "/app/allocate.py")

    def test_bash_fallback(self):
        first, reason = mock.scripted_reply({"messages": [{"role": "user", "content": "repair"}],
                                             "tools": [{"function": {"name": "bash"}}]})
        self.assertEqual(reason, "tool_calls")
        self.assertEqual(first["tool_calls"][0]["function"]["name"], "bash")

    def test_second_turn_must_include_matching_tool_result(self):
        with self.assertRaises(ValueError):
            mock.scripted_reply({"messages": [{"role": "tool", "tool_call_id": "wrong", "content": "ok"}]})
        final, reason = mock.scripted_reply({"messages": [{"role": "tool", "tool_call_id": mock.CALL_ID, "content": "ok"}]})
        self.assertEqual(reason, "stop")
        self.assertIn("applied", final["content"])

    def test_missing_editor_fails_closed(self):
        with self.assertRaises(ValueError):
            mock.scripted_reply({"messages": [{"role": "user", "content": "repair"}], "tools": []})


if __name__ == "__main__":
    unittest.main()
