# Task 6: Add ID validation helper

## Objective

Provide a shared validation function that checks whether a block ID string contains only valid characters. Used by all three splitting passes (Tasks 2, 3, 4).

## Context

Block IDs must match `[a-zA-Z0-9_-.]` only. The regex in the splitting passes captures any text in the ID slot (`[^\]]+`), so validation happens in Python after capture.

## Target File

`src/syntagmax/extractors/markdown.py` — new module-level function

## Implementation

```python
import re

_VALID_BLOCK_ID_RE = re.compile(r'^[a-zA-Z0-9_.\-]+$')


def _validate_block_id(id_str: str) -> bool:
    """Check if a block ID contains only valid characters [a-zA-Z0-9_-.]."""
    return bool(_VALID_BLOCK_ID_RE.match(id_str))
```

Module-level function (not a method) since it has no instance dependencies.

## Acceptance Criteria

1. `_validate_block_id('com-1')` → `True`
2. `_validate_block_id('note.2')` → `True`
3. `_validate_block_id('my_block')` → `True`
4. `_validate_block_id('UPPER-123')` → `True`
5. `_validate_block_id('a.b-c_d')` → `True`
6. `_validate_block_id('invalid!id')` → `False`
7. `_validate_block_id('has space')` → `False`
8. `_validate_block_id('@bad')` → `False`
9. `_validate_block_id('')` → `False`
10. `_validate_block_id('path/slash')` → `False`

## Test File

`tests/test_marked_fragments.py` — new test class `TestBlockIdValidation`

## Dependencies

None — pure utility function.

## Parallelization

Can run in parallel with all other tasks. No dependencies.
