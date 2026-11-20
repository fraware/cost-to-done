# Repair the cent allocator

The function `allocate_cents(total_cents, weights)` in `/app/allocate.py` distributes a nonnegative integer number of cents in proportion to integer weights. Its current implementation rounds each share independently and loses cents or over-allocates.

Fix the function without changing its signature or introducing external dependencies.

**Contract**

- `total_cents` is a nonnegative `int` (a `bool` is invalid).
- `weights` is a nonempty list of nonnegative `int` values (booleans are invalid), and at least one weight is positive.
- Invalid inputs raise `ValueError`.
- Allocate *all* cents, including cases where `total_cents` is zero.
- The allocation is proportional according to the **largest-remainder method** using exact integer arithmetic. Start with each floor share, then distribute leftover cents to the largest fractional remainders.
- Equal fractional remainders break ties by the *earlier input index*.
- The returned list has the same length and order as `weights`, and each element is a nonnegative `int`.

Example: `allocate_cents(10, [1, 1, 1]) == [4, 3, 3]`.
