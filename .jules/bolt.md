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

## 2026-07-28 - Memoizing ID schema regular expression compilation
**Learning:**
Compiling ID schemas into regex patterns involves multiple string manipulations (replacement, regex escaping, and list joining) followed by `re.compile`. In projects with thousands of requirements matching repetitive schemas (e.g., `REQ-{num:3}`), calling `compile_id_schema` on every ID extraction or validation creates redundant string formatting and regex object creation overhead. Applying `@functools.lru_cache(maxsize=128)` yields a ~4x performance improvement on number extraction routines.
**Action:** Always memoize regex compilation functions or pre-compile regex patterns at module/class levels when schema strings or arguments are repeated across large loops or dataset processing pipelines.

## 2026-08-19 - Short-circuiting redundant ancestral propagation during tree building
**Learning:**
In `gather_ancestors`, calling `gather_ancestors(artifacts, ref)` across all artifact keys causes subtrees to be recursively re-traversed repeatedly. If updating a child's ancestor set (`artifacts[child].ancestors`) does not increase its length, no new ancestors were introduced, and all of the child's descendants already possess those ancestors. Short-circuiting recursive calls when `len(child.ancestors)` remains unchanged reduces tree building time by >80% (~5x speedup) on large artifact graphs.
**Action:** In recursive set/ancestor propagation algorithms over graphs, track set length before update and only recurse into children if new elements were actually added.
