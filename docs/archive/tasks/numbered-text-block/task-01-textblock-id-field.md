# Task 1: Add `id` field to `TextBlock` dataclass

## Objective

Extend `TextBlock` in `blocks.py` to carry an optional block ID and track whether it was explicitly provided by the user.

## Context

`TextBlock` currently has two fields: `content: str` and `marker: str | None`. This task adds the infrastructure for block identification that all subsequent tasks depend on.

## Target File

`src/syntagmax/blocks.py`

## Implementation

Add two new fields to the `TextBlock` dataclass:

```python
@dataclass
class TextBlock(Block):
    content: str
    marker: str | None = None
    id: str | None = None
    explicit_id: bool = False
```

- `id` — the block identifier (either user-provided or auto-generated short hash)
- `explicit_id` — `True` when the user wrote an ID in the source document; `False` when the ID was auto-generated

Both fields have defaults so all existing code creating `TextBlock(content=..., marker=...)` continues to work without modification.

## Acceptance Criteria

1. `TextBlock` has `id: str | None = None` field
2. `TextBlock` has `explicit_id: bool = False` field
3. All existing tests pass without modification (fields default to `None`/`False`)
4. New unit test confirms:
   - `TextBlock(content='x')` has `id=None` and `explicit_id=False`
   - `TextBlock(content='x', marker='COM', id='com-1', explicit_id=True)` stores all fields correctly

## Dependencies

None — this is the foundation task.

## Parallelization

Can run in parallel with Tasks 5, 6, 7, and 10.
