"""Prepare two pinned upstream CPython regression controls without inference.

Only the declared upstream blobs are downloaded. The local commits are
constructed packaging snapshots, not the upstream Git commits themselves.
The public fixes are development controls, not held-out benchmark tasks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import urlopen

from cost_to_done.repository_task import prepare_repository_task

CASES = {
    "cpython-textwrap-139065": {
        "issue": 139065,
        "module": "textwrap",
        "starter": ("5c942f11cdf5f9d7313200983fa0c58b3bc670a2", "5ae439f5cd3b784594cd87cadc476c65db2453b6"),
        "reference": ("1c598e04361dbfc9cf465f3a02f83715c11b028c", "41366fbf443a4fc46768a6745d0b9e64c1d3b056"),
        "license": "20cf39097c68baa17cc566b64e76d34ebf034044",
        "instruction": (
            "Repair Lib/textwrap.py: when wrapping a long word after a line "
            "whose remaining space is consumed by whitespace, remove trailing "
            "whitespace with the default drop_whitespace setting. Preserve "
            "normal long-word breaking and ordinary wrapping. Modify the "
            "source only; use the standard library."
        ),
        "tests": '''import unittest
from Lib import textwrap as subject


class Regression(unittest.TestCase):
    def test_boundary(self):
        self.assertEqual(subject.wrap("abc abcdefghijk", width=4),
                         ["abc", "abcd", "efgh", "ijk"])

    def test_other_boundary(self):
        self.assertEqual(subject.wrap("hello abcdefghijk", width=6),
                         ["hello", "abcdef", "ghijk"])

    def test_normal_wrapping(self):
        self.assertEqual(subject.wrap("ab cd ef", width=5), ["ab cd", "ef"])

    def test_no_long_word_break(self):
        self.assertEqual(subject.wrap("abc abcdefghijk", width=4,
                                      break_long_words=False),
                         ["abc", "abcdefghijk"])
''',
    },
    "cpython-ipaddress-117566": {
        "issue": 117566,
        "module": "ipaddress",
        "starter": ("eb20a7d12c4b2ab7931074843f8602a48b5b07bd", "22cdfc93d8ad32d7da1b9aacccf504e0fd838630"),
        "reference": ("fb7f79b4da35b75cdc82ff3cf20816d2bf93d416", "8e4d49c859534d816efd70b8e0b14d9da407f14e"),
        "license": "14603b95c2e23b5a4cd6ff93f50348d1817f7638",
        "instruction": (
            "Repair Lib/ipaddress.py so IPv4-mapped IPv6 addresses, networks "
            "and interfaces classify loopback addresses consistently with the "
            "embedded IPv4 address and network. Preserve native IPv6 and "
            "IPv4 loopback classification. Modify the source only."
        ),
        "tests": '''import unittest
from Lib import ipaddress as subject


class Regression(unittest.TestCase):
    def test_mapped_address(self):
        for address in ("::ffff:127.0.0.1", "::ffff:127.100.200.254"):
            with self.subTest(address=address):
                self.assertTrue(subject.ip_address(address).is_loopback)
        self.assertFalse(subject.ip_address("::ffff:128.0.0.1").is_loopback)

    def test_mapped_network(self):
        self.assertTrue(subject.ip_network("::ffff:127.42.0.0/112").is_loopback)
        self.assertFalse(subject.ip_network("::ffff:128.0.0.0/112").is_loopback)

    def test_mapped_interface(self):
        self.assertTrue(subject.ip_interface("::ffff:127.42.1.2/112").is_loopback)
        self.assertFalse(subject.ip_interface("::ffff:127.42.1.2/96").is_loopback)

    def test_native_addresses(self):
        self.assertTrue(subject.ip_address("::1").is_loopback)
        self.assertFalse(subject.ip_address("::2").is_loopback)
        self.assertTrue(subject.ip_address("127.1.2.3").is_loopback)
        self.assertFalse(subject.ip_address("128.1.2.3").is_loopback)
''',
    },
}

MAX_BLOB = 1_000_000
LOCAL_CHECK = """
import json, sys, unittest
sys.path.insert(0, sys.argv[1])
suite = unittest.defaultTestLoader.discover(sys.argv[2], pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
                  "errors": len(result.errors), "skips": len(result.skipped),
                  "expected_failures": len(result.expectedFailures),
                  "unexpected_successes": len(result.unexpectedSuccesses)}))
"""


def fetch_blob(commit: str, path: str, expected: str) -> bytes:
    """Check the downloaded bytes against independently recorded Git tree IDs."""
    url = f"https://raw.githubusercontent.com/python/cpython/{commit}/{path}"
    with urlopen(url, timeout=30) as response:
        data = response.read(MAX_BLOB + 1)
    if len(data) > MAX_BLOB:
        raise ValueError("upstream blob exceeds size bound")
    digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data,
                          usedforsecurity=False).hexdigest()
    if digest != expected:
        raise ValueError(f"upstream Git blob mismatch: {path} at {commit}")
    return data


def git(repo: Path, *args: str) -> None:
    env = dict(os.environ)
    env.update(GIT_AUTHOR_DATE="2026-11-24T00:00:00Z",
               GIT_COMMITTER_DATE="2026-11-24T00:00:00Z",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    subprocess.run(["git", "-C", str(repo), *args], env=env,
                   check=True, timeout=30)


def local_control(task: Path, *, expected: str) -> dict:
    """Reject a negative control that fails through import/runtime errors."""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", LOCAL_CHECK,
         str(task / "environment/workspace"), str(task / "tests")],
        check=True, capture_output=True, text=True, timeout=60,
    )
    result = json.loads(completed.stdout)
    if (result["tests"] != 4 or result["errors"] or result["skips"]
            or result["expected_failures"] or result["unexpected_successes"]
            or (result["failures"] > 0) != (expected == "fail")):
        raise RuntimeError(f"unexpected local control: {result}\n{completed.stderr}")
    return {"outcome": expected, **result}


def prepare(root: Path, name: str, case: dict) -> None:
    directory = root / name
    directory.mkdir()
    repo = directory / "packaging-repo"
    repo.mkdir()
    git(repo, "init", "-q", "--object-format=sha1")
    git(repo, "config", "user.name", "Cost to Done packaging")
    git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "Lib").mkdir()
    (repo / "acceptance").mkdir()
    source_path = f"Lib/{case['module']}.py"
    test_path = "acceptance/test_regression.py"
    (repo / test_path).write_text(case["tests"], encoding="utf-8")
    instruction = directory / "instruction.md"
    instruction.write_text(case["instruction"] + "\n", encoding="utf-8")
    records = {}
    for role, expected in (("starter", "fail"), ("reference", "pass")):
        upstream_commit, source_blob = case[role]
        source = fetch_blob(upstream_commit, source_path, source_blob)
        license_bytes = fetch_blob(upstream_commit, "LICENSE", case["license"])
        (repo / source_path).write_bytes(source)
        (repo / "LICENSE").write_bytes(license_bytes)
        git(repo, "add", source_path, "LICENSE", test_path)
        git(repo, "commit", "-qm", role)
        task = directory / role
        manifest = prepare_repository_task(
            repo, revision="HEAD", name=name, sources=[source_path, "LICENSE"],
            tests=[test_path], instruction=instruction, output=task,
        )
        records[role] = {
            "upstream_commit": upstream_commit, "upstream_source_blob": source_blob,
            "upstream_license_blob": case["license"],
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "packaging_commit": manifest["git_commit"],
            "task_input_sha256": manifest["task_input_sha256"],
            "local_control": local_control(task, expected=expected),
        }
    result = {
        "schema_version": 1, "task": name,
        "scope": "public_upstream_development_controls",
        "upstream_repository": "https://github.com/python/cpython",
        "upstream_issue": case["issue"], "source_path": source_path,
        "held_out": False, "provider_calls": 0, "paid_execution_authorized": False,
        "acceptance_tests": "Cost to Done regression tests derived from public defect semantics",
        "controls": records,
    }
    (directory / "provenance.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m scripts.prepare_external_controls NEW_DIRECTORY")
    root = Path(sys.argv[1]).absolute()
    root.mkdir(mode=0o700, exist_ok=False)
    for name, case in CASES.items():
        prepare(root, name, case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
