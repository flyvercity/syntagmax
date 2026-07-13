# Non-Artifact Block Identification — Task Summary

**Spec:** `docs/specs/numbered-text-block.spec.md`

## Task Overview

| # | Task | File(s) | Depends On |
|---|------|---------|-----------|
| 1 | Add `id` field to TextBlock | `blocks.py` | — |
| 2 | Closed paired marker IDs | `markdown.py` | 1, 6, 7, 9 |
| 3 | Unclosed paired marker IDs | `markdown.py` | 1, 6, 7, 9 |
| 4 | Line-prefix marker IDs | `markdown.py` | 1, 6, 7, 9 |
| 5 | Fallback terminator regex | `markdown.py` | — |
| 6 | ID validation helper | `markdown.py` | — |
| 7 | Deterministic short hash | `markdown.py` | — |
| 8 | Uniqueness validation | `publish.py`, `cli.py` | 1 |
| 9 | Filepath threading | `markdown.py` | 1 |
| 10 | Documentation | `obsidian.md` | — |

## Dependency Graph

```
         ┌─────┐  ┌─────┐  ┌─────┐  ┌──────┐
         │  5  │  │  6  │  │  7  │  │  10  │   ← Wave 1 (no deps)
         └─────┘  └──┬──┘  └──┬──┘  └──────┘
                     │        │
    ┌─────┐          │        │
    │  1  │ ─────────┼────────┼──────────────── ← Wave 1 (no deps)
    └──┬──┘          │        │
       │             │        │
  ┌────┼─────────────┼────────┼───┐
  │    │             │        │   │
  ▼    │             │        │   ▼
┌───┐  │             │        │  ┌───┐
│ 8 │  │             │        │  │ 9 │        ← Wave 2 (needs 1)
└───┘  │             │        │  └─┬─┘
       │             │        │    │
       │             ▼        ▼    ▼
       │           ┌─────────────────┐
       │           │   2,  3,  4     │        ← Wave 3 (needs 1, 6, 7, 9)
       │           └─────────────────┘
       │
```

## Execution Plan

### Wave 1 — No dependencies (fully parallel)

Run simultaneously:
- **Task 1** — TextBlock dataclass (foundation, fast)
- **Task 5** — Fallback terminator regex (standalone, fast)
- **Task 6** — ID validation helper (standalone, fast)
- **Task 7** — Deterministic hash function (standalone, fast)
- **Task 10** — Documentation update (standalone)

### Wave 2 — Depends on Task 1

Run after Wave 1 completes:
- **Task 8** — Uniqueness validation in `build_block_tree()`
- **Task 9** — Filepath threading through splitting pipeline

Tasks 8 and 9 can run in parallel with each other.

### Wave 3 — Core integration (depends on 1, 6, 7, 9)

Run after Wave 2 completes:
- **Task 2** — Closed paired marker IDs
- **Task 3** — Unclosed paired marker IDs
- **Task 4** — Line-prefix marker IDs

Tasks 2, 3, and 4 modify different methods in the same file. They can be run in parallel if using separate branches, or sequentially if working on a single branch.

## Merge Order

Recommended merge sequence to minimize conflicts:

1. Tasks 1, 5, 6, 7, 10 (all independent, merge in any order)
2. Task 9 (changes method signatures that Tasks 2/3/4 depend on)
3. Task 8 (changes `publish.py` and `cli.py`, independent of extraction)
4. Tasks 2, 3, 4 (all modify `markdown.py`, merge sequentially)

## Integration Testing

After all tasks are merged, run the full test suite:

```bash
uv run pytest tests/test_marked_fragments.py tests/test_empty_line_terminator.py tests/test_publish.py -v
```

Key integration scenarios to verify:
- End-to-end extraction with mixed ID/no-ID blocks
- Publishing a project with duplicate explicit IDs (should error)
- Publishing a project with duplicate content but no explicit IDs (should succeed)
- Fallback termination by `[COM some-id]` followed by artifact extraction

## File Conflict Risk

| File | Tasks modifying it | Risk |
|------|-------------------|------|
| `blocks.py` | 1 only | None |
| `markdown.py` | 2, 3, 4, 5, 6, 7, 9 | **High** — merge sequentially |
| `publish.py` | 8 only | None |
| `cli.py` | 8 only | None |
| `obsidian.md` | 10 only | None |

**Recommendation:** Tasks 5, 6, 7, 9 modify different sections of `markdown.py` (module-level functions vs method signatures vs regex inside a method). Merge them in Wave 1/2 order. Tasks 2, 3, 4 each modify a different method but may conflict on imports — merge sequentially or in a single PR.
