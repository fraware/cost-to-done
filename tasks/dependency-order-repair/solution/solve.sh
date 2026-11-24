#!/usr/bin/env bash
set -euo pipefail
root="${APP_ROOT:-/app}"
cat > "$root/dependency_order.py" <<'PY'
"""Lexicographically minimal topological order."""
import heapq


def build_order(dependencies):
    if not isinstance(dependencies, dict):
        raise ValueError("expected dependency dictionary")
    if any(not isinstance(name, str) or not name for name in dependencies):
        raise ValueError("invalid task name")
    reverse = {name: [] for name in dependencies}
    indegree = {}
    for name, prereqs in dependencies.items():
        if not isinstance(prereqs, list) or any(not isinstance(p, str) or not p or p not in dependencies for p in prereqs):
            raise ValueError("invalid prerequisite")
        unique = set(prereqs)
        indegree[name] = len(unique)
        for p in unique:
            reverse[p].append(name)
    ready = [name for name, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    result = []
    while ready:
        name = heapq.heappop(ready)
        result.append(name)
        for dependent in reverse[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                heapq.heappush(ready, dependent)
    if len(result) != len(dependencies):
        raise ValueError("dependency cycle")
    return result
PY
