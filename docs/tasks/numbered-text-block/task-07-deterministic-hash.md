# Task 7: Add deterministic short hash generation for blocks without explicit IDs

## Objective

Provide a helper function that generates a stable, deterministic 8-character hex hash for text blocks without user-provided IDs.

## Context

When a user writes `[COM]text` without an explicit ID, the system needs an internal identifier. The identifier must be deterministic (same input → same output across runs), short, and content-aware.

Auto-generated IDs are NOT validated for global uniqueness (per spec requirement 4).

## Target File

`src/syntagmax/extractors/markdown.py` — new module-level function

## Implementation

```python
import hashlib


def generate_block_id(marker: str, content: str, filepath: str) -> str:
    """Generate a deterministic 8-char hex hash for a text block without an explicit ID.

    The hash is derived from the marker type, block content, and file path to ensure
    stability across runs while avoiding collisions between different blocks.
    """
    data = f'{marker}:{filepath}:{content}'.encode('utf-8')
    return hashlib.sha256(data).hexdigest()[:8]
```

Key design choices:
- SHA-256 for good distribution
- First 8 hex chars = 32 bits of entropy (sufficient for internal tracking)
- Includes `filepath` to differentiate identical blocks in different files
- Includes `marker` to differentiate same text under different marker types
- Format: `marker:filepath:content` with colon separators

## Acceptance Criteria

1. `generate_block_id('COM', 'hello', 'file.md')` always returns the same 8-char string
2. Different file → different hash
3. Different marker → different hash
4. Different content → different hash
5. Return value is exactly 8 characters, all lowercase hex (`[0-9a-f]{8}`)
6. Function is pure — no side effects, no state

## Test File

`tests/test_marked_fragments.py` — new test class `TestBlockIdGeneration`

## Dependencies

None — pure utility function.

## Parallelization

Can run in parallel with all other tasks. No dependencies.
