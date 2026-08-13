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

## 2026-07-01 - Dynamic regex compilation and Lark parser cached generation
**Learning:**
1. Re-compiling regular expressions on every class instantiation in Python is highly redundant and consumes valuable CPU cycles. Caching them dynamically using module-level functions decorated with `@functools.lru_cache` provides a significant boost.
2. Instantiating Lark parsers with custom string grammars dynamically on every object instantiation (e.g. `Lark(grammar, parser='lalr')`) is incredibly expensive because Lark parses the grammar itself and compiles the LALR parser states. Caching the completed `Lark` parser instance on the parameterizing string (e.g. `marker`) reduces instantiation time from 31 seconds to 0.18 seconds (a 167x speedup).
**Action:** Always pre-compile regular expressions or use `@functools.lru_cache` to cache compiled patterns. Cache heavy parser libraries (like `Lark`) that are stateless and parameterizable to avoid redundant parser state generation.
