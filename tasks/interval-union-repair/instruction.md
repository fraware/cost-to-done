# Repair interval normalization

In `/app/intervals.py`, repair `normalize(intervals)`.

Given a list of (start, end) tuples of exact integers (booleans excluded),
return a new list of sorted, disjoint, maximal nonempty half-open intervals
whose union equals the input. Merge overlapping and touching intervals; discard
empty intervals. Reject reversed intervals, invalid shapes and non-integer
endpoints with ValueError. The outer container must be a list and each interval
must be a tuple of length two. Do not mutate the input. Support arbitrary-size
signed integers and O(n log n) time. Use the Python standard library only.

Keep the public function name and signature. Do not alter the verifier.
