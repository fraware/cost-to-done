"""Prepare pinned upstream CPython regression controls without inference.

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
    "cpython-statistics-92531": {
        "issue": 92531,
        "module": "statistics",
        "starter": ("5bc2390229bbcb4f13359e867fd8a140a1d5496b", "54f4e132651897eee86f5253c465fc1b391061e3"),
        "reference": ("e01eeb7b4b8d00b9f5c6acb48957f46ac4e252c0", "2d66b0522f19d52632c0f24d73df7c93d9b326bc"),
        "license": "02a5145f0e38520d5187b8f775fa7dee091976f8",
        "instruction": (
            "Repair Lib/statistics.py: median_grouped must return a float for "
            "singleton numeric data, consistently with its interpolation result. "
            "Preserve grouped interpolation and empty-input error behavior."
        ),
        "tests": '''import unittest
from decimal import Decimal
from fractions import Fraction
from Lib import statistics as subject


class Regression(unittest.TestCase):
    def test_single_integer(self):
        result = subject.median_grouped([23])
        self.assertIs(type(result), float)
        self.assertEqual(result, 23.0)

    def test_single_fraction(self):
        result = subject.median_grouped([Fraction(15, 19)])
        self.assertIs(type(result), float)
        self.assertAlmostEqual(result, 15 / 19)

    def test_single_decimal(self):
        result = subject.median_grouped([Decimal("0.28")])
        self.assertIs(type(result), float)
        self.assertAlmostEqual(result, 0.28)

    def test_interpolation_and_empty(self):
        self.assertAlmostEqual(subject.median_grouped([1, 2, 2, 3]), 2.0)
        with self.assertRaises(subject.StatisticsError):
            subject.median_grouped([])
''',
    },
    "cpython-ipaddress-110196": {
        "issue": 110196,
        "module": "ipaddress",
        "starter": ("b845a9e145b2f133270aa07836c7e6a385066c00", "f5aba434fd4253f778852fcfb2adbd4983019682"),
        "reference": ("767f416feb551f495bacfff1e9ba1e6672c2f24e", "68ddfbeb4bc212808841c3b7ff2cc941123055a0"),
        "license": "f26bcf4d2de6eb136e31006ca3ab447d5e488adf",
        "instruction": (
            "Repair Lib/ipaddress.py so IPv6 address serialization and copying "
            "preserve the scope identifier. Preserve ordinary IPv6 addresses."
        ),
        "tests": '''import copy
import pickle
import unittest
from Lib import ipaddress as subject


class Regression(unittest.TestCase):
    def test_pickle(self):
        addr = subject.IPv6Address("2001:db8::%scope")
        self.assertEqual(pickle.loads(pickle.dumps(addr)), addr)

    def test_copy(self):
        addr = subject.IPv6Address("fe80::1%eth0")
        self.assertEqual(copy.copy(addr), addr)

    def test_deepcopy(self):
        addr = subject.IPv6Address("fe80::1%zone")
        self.assertEqual(copy.deepcopy(addr), addr)

    def test_unscoped(self):
        addr = subject.IPv6Address("2001:db8::1")
        self.assertEqual(pickle.loads(pickle.dumps(addr)), addr)
''',
    },
    "cpython-fractions-119189": {
        "issue": 119189,
        "module": "fractions",
        "starter": ("dae0375bd97f3821c5db1602a0653a3c5dc53c5b", "f91b4f35eff37083c64f8427bceefff9672c2883"),
        "reference": ("b9965ef282d6662145d2e05b080c811132ce6fde", "95adccd86e33a0e9f611c01553de42e8cbde713d"),
        "license": "14603b95c2e23b5a4cd6ff93f50348d1817f7638",
        "instruction": (
            "Repair Lib/fractions.py so exponentiation with an unsupported "
            "right operand defers to the operand's reflected operation "
            "with the original Fraction. Preserve supported rational, float "
            "and complex exponentiation."
        ),
        "tests": '''import unittest
from Lib import fractions as subject


class Exponent:
    def __rpow__(self, base):
        return base


class Regression(unittest.TestCase):
    def test_reflected_power(self):
        base = subject.Fraction(3, 2)
        self.assertIs(base ** Exponent(), base)

    def test_not_implemented(self):
        # A direct dunder call used to raise instead of deferring.
        try:
            result = subject.Fraction(3, 2).__pow__(object())
        except TypeError:
            self.fail("unsupported operand raised instead of deferring")
        self.assertIs(result, NotImplemented)

    def test_integer_power(self):
        self.assertEqual(subject.Fraction(3, 2) ** 2,
                         subject.Fraction(9, 4))

    def test_float_and_complex(self):
        base = subject.Fraction(3, 2)
        self.assertEqual(base ** 2.0, 2.25)
        self.assertAlmostEqual(base ** 2j, 1.5 ** 2j)
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
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: python -m scripts.prepare_external_controls NEW_DIRECTORY [CASE]")
    names = list(CASES) if len(sys.argv) == 2 else [sys.argv[2]]
    if any(name not in CASES for name in names):
        raise SystemExit("unknown public control case")
    root = Path(sys.argv[1]).absolute()
    root.mkdir(mode=0o700, exist_ok=False)
    for name in names:
        prepare(root, name, CASES[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
