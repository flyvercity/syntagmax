# Bolt's Journal

⚡ Bolt's Philosophy:
- Speed is a feature
- Every millisecond counts
- Measure first, optimize second
- Don't sacrifice readability for micro-optimizations

## 2025-02-15 - Initial Setup
**Learning:** Establishing the journal to log key lessons.
**Action:** Always document performance insights here.

## 2026-06-25 - Single-key dictionary key retrieval and boolean condition evaluations
**Learning:**
1. Retrieving keys from single-key dictionaries using `list(d.keys())[0]` in Python incurs unnecessary overhead due to creating an intermediate list object. Using `next(iter(d))` is almost twice as fast and uses less memory.
2. In hot paths that evaluate conditions, converting boolean objects to strings and checking set membership is expensive. Performing an early type-check `isinstance(value, bool)` bypassed string coercion and reduced execution time by over 3x.
**Action:** Use `next(iter(d))` when looking up the first/only key of a dictionary, and insert early-return/short-circuit type checks (e.g., boolean checks) on hot paths to avoid expensive type conversion logic.
