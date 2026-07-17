# Bug Hunter Scan Report — 2026-07-09

## Scan Metadata

| Field | Value |
|-------|-------|
| Date | 2026-07-09 |
| Mode | local-sequential (full project) |
| Files scanned | 40 source files |
| Files filtered | 38 (docs/config/tests) |
| Tech stack | Python 3.13, Click CLI, Pydantic, FastMCP, GitPython, lark, ruamel.yaml |
| Architecture | Single-service CLI tool — requirements management system with git integration |

## Pipeline Summary

```
Triage:    78 total files | FILE_BUDGET: 60 | Strategy: extended
Recon:     mapped 40 files → 0 CRITICAL | 0 HIGH | 40 MEDIUM | 33 CONTEXT-ONLY
Hunters:   5 findings reported (5 self-debunked removed during analysis)
Skeptics:  challenged 5 | disproved: 0, accepted: 5
Referee:   confirmed 4 real bugs → Critical: 0 | Medium: 4 | Low: 0
```

## Confirmed Bugs

### BUG-2 — Trace matrix includes wrong-type parents (Medium)

- **File**: `src/syntagmax/trace.py:76-80`
- **Confidence**: 95%
- **Auto-fix eligible**: Yes

**Claim**: `build_trace_matrix()` in forward direction includes ALL parent pids in `linked_ids` regardless of whether they match the requested `parent_type`. The if/else structure is functionally unconditional — both branches append the pid.

**Evidence**:
```python
for pid in lead.pids:
    if pid in artifacts and artifacts[pid].atype == parent_type:
        linked_ids.append(pid)
    else:
        # Unresolved reference or wrong-type parent - include raw ID so broken links are visible
        linked_ids.append(pid)
```

**Runtime trigger**: Run `syntagmax trace --child REQ --parent SYS` on a project where REQ artifacts have parent references to both SYS and DOC types. The CSV output ParentID column will include DOC artifact IDs even though only SYS was requested.

**Fix**: Only append when the parent type matches. For unresolved references, either skip them or emit them in a separate column. Unmatched-type parents should not appear in the linked_id column — this breaks the left-outer-join semantics.

---

### BUG-1 — Transitive ancestors not propagated (Medium)

- **File**: `src/syntagmax/tree.py:94-101`
- **Confidence**: 75%
- **Auto-fix eligible**: Yes

**Claim**: `gather_ansestors()` does not propagate ancestors transitively. In a 3+ level hierarchy A→B→C, `C.ansestors` will contain only `{B}` but NOT `{A}`. The function adds `ref` to each child's ansestors set, then recurses, but never propagates the parent's own ancestors down to grandchildren.

**Evidence**:
```python
def gather_ansestors(artifacts: ArtifactMap, ref: str, depth: int = 0) -> str | None:
    if depth > MAX_TREE_DEPTH:
        return f'Circular reference detected with {artifacts[ref].aid}'

    for child in artifacts[ref].children:
        artifacts[child].ansestors.add(ref)
        err = gather_ansestors(artifacts, child, depth + 1)

        if err:
            return err

    return None
```

**Runtime trigger**: Any code that checks whether a distant ancestor is in `artifact.ansestors` will get `False`. Currently the `ansestors` field is populated but not consumed in the codebase, making this a latent correctness bug.

**Fix**: Before recursing, also add `artifacts[ref].ansestors` to the child's set:
```python
artifacts[child].ansestors.add(ref)
artifacts[child].ansestors.update(artifacts[ref].ansestors)
```

---

### BUG-4 — Duplicate ParentLinks from multiple rules (Medium)

- **File**: `src/syntagmax/tree.py:59-73`
- **Confidence**: 70%
- **Auto-fix eligible**: Yes

**Claim**: `populate_pids()` processes all metamodel rules for a reference attribute without deduplicating, causing duplicate `ParentLink` entries when multiple rules match (e.g., conditional + unconditional rules for the same reference field).

**Evidence**: The inner loop iterates all rules for an attribute. The check `if aid not in a.pids: a.pids.append(aid)` prevents duplicate pids, but `a.parent_links.append(ParentLink(...))` is unconditional — it always appends regardless of whether a link to that pid already exists.

**Runtime trigger**: Define a metamodel with both conditional and unconditional rules for a parent reference attribute. Impact analysis will report duplicate suspicious links and the tree renderer will show duplicate parents.

**Fix**: Either evaluate conditions before processing (matching `ArtifactValidator`'s approach), or deduplicate `parent_links` by checking if a link with the same `pid` already exists before appending.

---

### BUG-5 — Parser consumes unrelated YAML blocks (Medium)

- **File**: `src/syntagmax/extractors/markdown.py:455-456`
- **Confidence**: 80%
- **Auto-fix eligible**: Yes

**Claim**: When `[/MARKER]` terminator is absent, the markdown parser searches for `` ```yaml `` in the ENTIRE remaining document. An unrelated `` ```yaml `` block later in the file will be incorrectly consumed as this artifact's metadata, creating a malformed segment.

**Evidence**:
```python
yaml_search_end = slash_req_pos if slash_req_pos != -1 else len(markdown)
yaml_start_pos = markdown.find('```yaml', start_pos, yaml_search_end)
```

**Runtime trigger**: Create a markdown file with `[REQ]` on line 1 (no `[/REQ]` terminator), then plain text, then an unrelated `` ```yaml `` block. The parser consumes everything from `[REQ]` to the closing ` ``` ` of the unrelated block as a single artifact.

**Fix**: When `[/MARKER]` is absent, do NOT fall back to searching the entire file. Instead, immediately emit an "Unterminated requirement" error and advance past the opening marker. Only search for `` ```yaml `` within a bounded window (e.g., up to the next `[MARKER]` occurrence or a reasonable line limit).

---

## Coverage

✅ Full queued coverage achieved — all 40 scannable source files were read and analysed.

## Summary

| Metric | Value |
|--------|-------|
| Total confirmed | 4 |
| Critical | 0 |
| Medium | 4 |
| Low | 0 |
| Dismissed | 1 |
| False positive rate | 0% |
| Security issues | 0 |
