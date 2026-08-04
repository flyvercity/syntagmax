# [ ] Task 1: Introduce `ReportError` Dataclass and Error Constants

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Create the `ReportError` dataclass with category constants and a backward-compatible `__str__` method. Add `ReportConfig` Pydantic model to `config.py`.

## Implementation

### `src/syntagmax/report.py`

- Define category constants: `CAT_SCHEMA`, `CAT_ATTRIBUTE`, `CAT_REFERENCE`, `CAT_TRACE`, `CAT_DUPLICATE`, `CAT_EXTRACTION`, `CAT_STRUCTURE`.
- Define `GLOBAL_INPUT = '__global__'` sentinel.
- Define `CANONICAL_CATEGORY_ORDER` list for consistent rendering order.
- Create `ReportError` dataclass with fields: `message`, `category`, `input_record`, `artifact_id`, `artifact_type`, `file_path`, `line_range`.
- Implement `from_any(err: ReportError | str)` classmethod for defensive coercion of plain strings.
- Implement `__str__()` that reproduces the legacy plain-text format, with graceful fallback for partial metadata (renders `(type።id)` when `file_path` is absent).

### `src/syntagmax/config.py`

- Add `ReportConfig(BaseModel)` with `path_as_links: bool = False` and `wiki_links: bool = False`.
- Add `report: ReportConfig = Field(default_factory=ReportConfig)` to `ConfigFile`.
- Expose `self.report` on `Config` class in `_read_config`.

## Test Requirements

- `ReportError('msg', 'attribute', 'sw-reqs', 'REQ-001', 'REQ', 'reqs/file.md', (10, 20)).__str__()` produces `"msg (REQ።REQ-001።reqs/file.md:10-20)"`
- `ReportError('msg', 'attribute', 'sw-reqs', 'REQ-001', 'REQ').__str__()` produces `"msg (REQ።REQ-001)"` (no file_path fallback)
- `ReportError('root error', 'structure').__str__()` produces `"root error"`
- `ReportError.from_any('plain string')` returns `ReportError(message='plain string', category=CAT_STRUCTURE)`
- `ReportError.from_any(existing_error)` returns the same object.
- `ConfigFile` validates with `[report]` section present and absent.
- `ReportConfig(path_as_links=True, wiki_links=True)` instantiates correctly.

## Demo

Unit tests pass, `ReportError` objects can be created and stringified.

## Files Modified

- `src/syntagmax/report.py`
- `src/syntagmax/config.py`
- `tests/test_report_error.py` (new)
