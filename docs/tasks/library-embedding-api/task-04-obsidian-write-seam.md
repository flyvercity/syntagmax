# [x] Task 4: Obsidian driver write seam (`edit`/`create`/`delete`)

**Spec:** `docs/specs/library-embedding-api.spec.md` (R3; critique X2, E1)

**Depends on:** none (independent of Tasks 1–3).

## Objective

Add a driver-agnostic write interface, implemented for the obsidian driver only, with precise contracts and safe file I/O.

## Implementation

### `src/syntagmax/errors.py`

- Add `class UnsupportedOperation(RMSException)`.

### `src/syntagmax/extractors/extractor.py` (base — raise `UnsupportedOperation`)

- `edit_artifact(self, artifact: Artifact, *, fields: dict[str, str | None] | None = None, body: str | None = None) -> None`
  - a `None` field value **deletes** that YAML attribute key; a non-`None` value sets/replaces it; `body` (when given) replaces `contents`.
- `create_artifact(self, *, target_file: str, atype: str, aid: str, fields: dict, body: str) -> Artifact`
  - `aid` is **required (non-`None`)** this phase; create missing parent dirs; **validate `target_file` resolves within `config.root_dir`** (`Path.resolve()` + `relative_to`), raising `ValueError` on traversal.
- `delete_artifact(self, artifact: Artifact) -> None`
  - remove the artifact's marked fragment; if it was the file's only artifact, delete the file.
- Base class attribute `WRITE_CAPABILITIES: set[str] = set()`.

### Obsidian extractor (`src/syntagmax/extractors/markdown.py` / obsidian driver)

- Implement all three, reusing `update_artifact_attributes` for field edits and the existing marker/YAML writing for body/create/delete.
- Set `WRITE_CAPABILITIES = {'edit', 'create', 'delete'}`.
- **Atomic writes (E1):** write to `tempfile.NamedTemporaryFile(dir=<target dir>, delete=False)` with `encoding='utf-8', newline=''`, then `os.replace(tmp, target)` — never an in-place partial write.

## Test Requirements (`tests/test_write_seam.py`, new)

- Edit a field → re-extract shows new value.
- Edit a field to `None` → YAML key removed on re-extract.
- Edit body/contents → re-extract shows new contents.
- Create a new artifact (explicit `aid`) → re-extract finds it; parent dirs created.
- `create_artifact` with a traversing `target_file` (e.g. `../../evil.md`) raises `ValueError`.
- Delete one of several artifacts → only that fragment gone; delete the sole artifact → file removed.
- A non-obsidian driver (`simple-markdown`/`sidecar`) raises `UnsupportedOperation`.
- Atomicity: no leftover temp files after a successful write.
- **Windows:** round-trip runs on Windows (`os.replace` over an existing file; newline correctness).

## Demo

A short script constructs the obsidian extractor, edits an artifact in `example/`, and prints the re-extracted value.

## Files Modified

- `src/syntagmax/errors.py`
- `src/syntagmax/extractors/extractor.py`
- `src/syntagmax/extractors/markdown.py` (obsidian driver)
- `tests/test_write_seam.py` (new)
