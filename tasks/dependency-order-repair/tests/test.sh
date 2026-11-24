#!/usr/bin/env bash
set -u
mkdir -p /logs/verifier
cd /app || exit 2
# A failing test is a graded failure, not an infrastructure exception.
if PYTHONPATH=/app python3 -m unittest discover -s /tests -p 'test_*.py' -v; then
  printf '1\n' > /logs/verifier/reward.txt
else
  printf '0\n' > /logs/verifier/reward.txt
fi
