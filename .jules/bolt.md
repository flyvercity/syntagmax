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

## 2026-09-05 - Optimizing ArtifactValidator in hot analysis loops
**Learning:**
In `ArtifactValidator` (`analyse.py`), validating thousands of artifacts repeatedly incurred heavy CPU and allocation overhead from:
1. Re-evaluating `_evaluate_condition` when `condition` is `None`. Short-circuiting `if cond is None` avoids method call overhead.
2. Re-constructing `metamodel` dictionaries on every condition evaluation pass. Caching `self._metamodel_dict` in `__init__` eliminates dict creation.
3. Allocating generator objects in `any(r['presence'] == 'mandatory' for r in active_rules)` and temporary set objects in `actual_names - set(active_rules_by_name.keys())`. Replacing them with explicit `for` loops and direct dictionary key containment checks (`extra not in active_rules_by_name`) avoids temporary allocations entirely.
4. Re-constructing `truthy` and `falsy` sets and string coercion for `bool` and `int` fields. Precomputing default boolean sets at module level and fast-pathing `isinstance(val, bool)` and `type(val) is int` yields a ~1.39x speedup (28% execution time reduction).
**Action:** In high-frequency validation loops, precompute static sets/dicts, avoid generator expressions in hot loops, and fast-path native Python types to bypass coercion and set allocation.
