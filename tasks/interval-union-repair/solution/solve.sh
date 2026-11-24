#!/usr/bin/env bash
set -euo pipefail
root="${APP_ROOT:-/app}"
cat > "$root/intervals.py" <<'PY'
"""Normalize the union of half-open integer intervals."""


def normalize(intervals):
    if not isinstance(intervals, list):
        raise ValueError("intervals must be a list")
    valid = []
    for interval in intervals:
        if not isinstance(interval, tuple) or len(interval) != 2:
            raise ValueError("interval must be a pair")
        start, end = interval
        if type(start) is not int or type(end) is not int or start > end:
            raise ValueError("invalid endpoints")
        if start < end:
            valid.append(interval)
    result = []
    for start, end in sorted(valid):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result
PY
