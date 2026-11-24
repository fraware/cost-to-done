# Repair deterministic dependency ordering

Repair `/app/dependency_order.py`, keeping `build_order(dependencies)`.

Input is a dictionary mapping nonempty string task names to lists of nonempty
string prerequisite names. Each prerequisite must be a declared task. Duplicate
prerequisite entries count as one edge. Return a new list containing every task
exactly once, with prerequisites before dependents; among eligible tasks choose
the lexicographically smallest. Reject invalid input, missing prerequisites and
cycles (including self-cycles) with ValueError. An empty mapping returns [].
Do not mutate input. Use Python's standard library and a heap-based algorithm
with O((V+E) log V) or better time, where E counts input edges.

Keep the public function name and signature. Do not alter the verifier.
