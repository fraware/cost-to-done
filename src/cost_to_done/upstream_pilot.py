"""Exact upstream development-task allowlist and explicit paid pilot gate.

Pins are taken from successful no-model controls at run 45537928082.
Public historical repairs are not private holdouts. This gate never permits
arbitrary prepared repositories, and it does not establish a billing cap.
"""
from __future__ import annotations

import os
from pathlib import Path

from .core import ReceiptError
from .repository_pilot import MODELS
from .repository_qualification import _manifest

STARTERS = {
    "cpython-statistics-92531": "746b02f201457cadc82431f2459cdbc39ccffe96e5a0ccdafae87563dc6424ea",
    "cpython-ipaddress-110196": "4683e16463d5d4fe6f00442ed0ac8e7544511feb665fda44347eceadee4f1114",
    "cpython-fractions-119189": "88a42ef1476717eff154e0c18d93621763f660c53d1d6eafb2d8d8d5089cdbae",
    "cpython-ipaddress-117566": "62a2159a6ddb5b4f4c84167346ff5f2fe1329d8ae7f4b9c41b516c89ead05966",
}
ALLOWANCE = "1"
REPETITIONS = 2


def trusted_upstream_dispatch() -> bool:
    """Require the dedicated canonical main workflow and its first dispatch."""
    return all(os.environ.get(key) == value for key, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "fraware/cost-to-done",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": "fraware/cost-to-done/.github/workflows/upstream-paid-pilot.yml@refs/heads/main",
        "CTD_UPSTREAM_PILOT_AUTHORIZED": "1",
    }.items())


def validate_upstream_starter(task: Path) -> dict:
    """Bind all staged files, wrapper and packaging identities to a known pin."""
    manifest = _manifest(task)
    if STARTERS.get(manifest["task"]) != manifest["task_input_sha256"]:
        raise ReceiptError("paid upstream pilot accepts only pinned public starter bytes")
    return manifest
