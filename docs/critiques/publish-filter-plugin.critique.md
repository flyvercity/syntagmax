# Spec Critique: Pre-Publishing Filter Plugin Hook

- **Target Specification:** [docs/specs/publish-filter-plugin.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/publish-filter-plugin.md)
- **Date:** 2026-07-09
- **Reviewers:** Antigravity (Product & Engineering Lenses)

---

## Executive Summary

The proposed specification introduces a much-needed, simplified per-block filtering API (`filter_block`) that operates on individual blocks rather than the entire `BlockTree`. This is a valuable addition for plugin authors. 

However, there is a fundamental logical contradiction between the stated user goals ("stripping draft artifacts") and the technical constraints (forbidding block list manipulation and treating `None` return values as fatal errors). If the hook cannot return `None` and the list cannot be mutated, blocks cannot be stripped/removed.

Additionally, the hook activation model is inconsistent with the rest of the plugin system: other hooks run automatically for all enabled plugins, whereas this hook requires an explicit, single CLI flag.

We recommend proceeding with updates to resolve the `None` return contradiction and align the execution model.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Product Lens Findings

### 1a. Problem Validation & Scope
- **Finding:** The problem statement is clear, but the scope of "stripping draft artifacts" is blocked by the requirements (see P1).

### 1b. User Value Assessment
* **P1: Block Removal Contradiction (Severity: 🎯 Must-Address)**
  * **Finding:** The spec lists "stripping draft artifacts" as a primary use case. However, Requirement 2 states that the hook "cannot add or remove blocks" and Requirement 3 states that "Returning `None` or a wrong type is a fatal error." If the hook cannot return `None` and cannot mutate lists, it is impossible to strip/remove blocks. The only option is to redact them to empty strings, which leaves unwanted empty blocks/headers in the published output.
  * **Suggestion:** Allow the `filter_block` hook to return `None`. A return value of `None` should indicate that the block is filtered out (omitted) from the document. Update the validation logic to treat `None` as a valid "discard" instruction rather than a fatal error.
* **P2: Hook Activation Inconsistency (Severity: 💡 Recommendation)**
  * **Finding:** Existing hooks like `transform_blocks` and `transform_markdown` run automatically on all enabled plugins in load order. The new hook requires a CLI option `--pre-filter <plugin-name>`, which restricts execution to exactly one plugin and adds CLI friction for users who want to run filters consistently.
  * **Suggestion:** Run all enabled plugins that implement `filter_block` automatically in load order, making the hook behave consistently with other hooks. The CLI option `--pre-filter` can be kept as an optional override/selector if needed, or removed to keep the interface simple.

### 1d. Edge Cases & User Experience
* **P3: Scope Leak / MCP Server Consistency (Severity: 🤔 Question)**
  * **Finding:** The `filter_block` hook runs only during the `publish` command. However, Syntagmax has other query mechanisms, such as the built-in MCP server (`src/syntagmax/mcp/server.py`) which exposes artifacts. If a filter plugin is used to redact confidential/classified information, those redacted blocks will still be visible in cleartext when queried via the MCP server.
  * **Suggestion:** Clarify if this hook should eventually apply to other commands/interfaces or if it is strictly a publishing render concern. If strictly for publishing, add a warning in the documentation highlighting that MCP queries do not apply the publish-time filters.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
* **E1: Mutating Lists During Iteration (Severity: 💡 Recommendation)**
  * **Finding:** Task 1 states "Replace the block in-place in the list." If we allow returning `None` to strip blocks (per P1), in-place mutation of a list while iterating is error-prone or requires complex index tracking.
  * **Suggestion:** Rebuild the `file_record.blocks` list using a list comprehension or filter pattern, which is simpler and safer:
    ```python
    new_blocks = []
    for block in file_record.blocks:
        res = plugin.module.filter_block(block, file_record, config, plugin.params)
        if res is not None:
            if not isinstance(res, Block):
                raise FatalError(...)
            new_blocks.append(res)
    file_record.blocks = new_blocks
    ```

### 2b. Failure Mode Analysis
* **E2: Context-Aware Error Messages (Severity: 💡 Recommendation)**
  * **Finding:** If a block filter raises an exception, the entire execution halts. For large requirement sets, it is critical to know *which* block/file caused the issue.
  * **Suggestion:** Wrap calls to the hook in a try-except block that adds context (e.g. the path of the file containing the block) to the raised `FatalError`.

### 2g. Dependencies & Integration Risks
* **E3: Hook Stage and Naming (Severity: 🤔 Question)**
  * **Finding:** The option is named `--pre-filter`, but it executes *after* the `transform_blocks` hooks. This might lead developers to think it executes before block transforms.
  * **Suggestion:** Consider naming the CLI option `--filter-block` or `--block-filter`, or just let it execute automatically as part of the normal plugin execution pipeline without requiring a dedicated CLI option.

---

## Cross-Lens Synthesis

* **X1: Allow Returning `None` to Omit Blocks (Severity: 🎯 Must-Address)**
  * *Product Perspective:* Crucial to fulfill the goal of stripping draft/unwanted blocks.
  * *Engineering Perspective:* Clean list-filtering implementation in the pipeline loop. Reduces layout rendering complexity by completely omitting blocks instead of rendering empty structures.
* **X2: Uniform Hook Pipeline (Severity: 💡 Recommendation)**
  * *Product Perspective:* A consistent user experience where enabled plugins just work.
  * *Engineering Perspective:* Simplifies `cli.py` and avoids adding command-line clutter/complexity.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | Problem Validation | "Stripping draft artifacts" is impossible because the spec forbids list mutation and bans `None` returns. | Allow returning `None` to omit blocks, and rebuild the blocks list. |
| P2 | Product | 💡 | User Value | Hook requires a manual CLI flag, unlike other hooks that run automatically. | Run `filter_block` automatically for all enabled plugins. |
| P3 | Product | 🤔 | UX / Security | Redacted/filtered blocks are still fully visible when queried via the MCP server. | Clarify scope and document MCP behavior. |
| E1 | Engineering | 💡 | Architecture | Replacing blocks in-place is error-prone if we support block removal. | Rebuild the `file_record.blocks` list using a filtering loop. |
| E2 | Engineering | 💡 | Failure Modes | Plugin exceptions fail the run without identifying which block/file failed. | Include `file_record.path` in the `FatalError` message. |
| E3 | Engineering | 🤔 | Integration | CLI option `--pre-filter` runs *after* block transforms, which is naming-wise confusing. | Rename option or let the filter run automatically. |

---

## Verdict & Offer of Remediation

### Verdict: ⚠️ **PROCEED WITH UPDATES**

To resolve the must-address items, we suggest modifying [docs/specs/publish-filter-plugin.md](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/specs/publish-filter-plugin.md) with the following changes:

#### Suggested Changes to Specification

1. **Update Requirements 1, 2, and 3:**
   ```diff
   -1. A new plugin hook `filter_block(block, file_record, config, params) -> Block` that receives blocks one at a time and returns a (possibly modified) block.
   -2. The hook shall NOT manipulate block lists — it cannot add or remove blocks.
   -3. Returning `None` or a wrong type is a fatal error.
   +1. A new plugin hook `filter_block(block, file_record, config, params) -> Block | None` that receives blocks one at a time and returns a (possibly modified) block, or `None` to omit the block.
   +2. The hook itself cannot directly mutate the list of blocks, but it can filter out a block by returning `None`.
   +3. Returning a value that is neither a `Block` instance nor `None` is a fatal error.
   ```

2. **Update Proposed Solution (run_pre_filter logic):**
   ```diff
   -3. Iterates all `InputBlock` → `FileRecord` → `Block`, calling `filter_block(block, file_record, config, params)` for each.
   -4. Replaces the block in the list with the returned value.
   -5. Validates the return is a `Block` instance; raises `FatalError` otherwise.
   +3. Iterates all `InputBlock` → `FileRecord` → `Block`, calling `filter_block(block, file_record, config, params)` for each.
   +4. Replaces the blocks list in `FileRecord` with only the non-`None` returned blocks.
   +5. Validates the return is a `Block` instance or `None`; raises `FatalError` with file path and block context otherwise.
   ```

3. **Update Plugin API Addition Signature:**
   ```diff
   -def filter_block(block: Block, file_record: FileRecord, config: Config, params: dict) -> Block:
   +def filter_block(block: Block, file_record: FileRecord, config: Config, params: dict) -> Block | None:
   ```

4. **Update Task 1 Guidance and Test Requirements:**
   ```diff
   - - Validate the return is a `Block` instance; raise `FatalError` with plugin name if not.
   - - Wrap exceptions in `FatalError` with traceback at DEBUG (same pattern as other hooks).
   - - Replace the block in-place in the list.
   - - Return the modified tree.
   + - Rebuild each `file_record.blocks` list using only the non-`None` returned blocks.
   + - Validate the return is a `Block` instance or `None`; raise `FatalError` with plugin name and file path if not.
   + - Wrap exceptions in `FatalError` with file/block context and traceback at DEBUG.
   + - Return the modified tree.
   
   **Test requirements:**
   - - Test that returning `None` raises `FatalError`.
   + - Test that returning `None` successfully removes the block from the tree.
   ```

5. **Update Task 3 Example Plugin implementation description:**
   ```diff
   - - If block is an `ArtifactBlock` with `status == 'draft'`, replace its content with "[REDACTED]".
   + - If block is an `ArtifactBlock` with `status == 'draft'`, return `None` to omit it entirely.
   ```
