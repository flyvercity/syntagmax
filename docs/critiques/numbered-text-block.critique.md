# Spec Critique: Non-Artifact Block Identification

## Executive Summary
This document presents a critique of the `docs/specs/numbered-text-block.spec.md` specification based on the dual Product and Engineering lenses framework.

Overall, the proposal is highly valuable and solves a real gap in requirement and comment referencing. However, the specification contains several critical gaps in parsing logic and edge-case handling that must be resolved before proceeding to implementation. Note that downstream usage (rendering block IDs in published output) is intentionally deferred, and backward compatibility of internal API signatures is disregarded for this phase.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Product Lens Findings

### 1a. User Value Assessment
* **Anchor Generation in Output (Deferred on Purpose):** The specification mentions "IDs are not surfaced in published output for now." While this prevents immediate cross-referencing in output documents, it is understood that downstream usage is intentionally deferred to keep the initial scope minimal.

### 1b. Edge Cases & User Experience
* **Identical Unmarked Blocks Conflict:** If a user includes two identical unmarked blocks (e.g., `[COM]Check this` twice in the same file), they will generate the exact same hash/ID. If global uniqueness is checked across all blocks, this will crash the build with a duplicate ID validation error, which is a poor user experience for a standard document.

---

## Engineering Lens Findings

### 2a. Failure Mode Analysis
* **Regex Filtering of Invalid IDs:** The proposed regex patterns `[a-zA-Z0-9_.\-]+` only match valid ID characters. If a user enters an invalid ID (e.g. `[COM invalid!id]`), the pattern will fail to match entirely, meaning the block will be treated as unmarked text rather than triggering an extraction error as required. The regex must capture any text up to the closing bracket/terminator and validate it programmatically in Python.
* **Lookahead Termination in Unclosed Blocks:** In `_split_unclosed_paired()`, the lookahead regex terminates on the next block matching `\n\s*\[(?:{escaped})(?:\s+\d+)?\]`. If this lookahead pattern is not updated to match the new ID format, an unclosed block followed by a block with a new alphanumeric ID will fail to terminate correctly, leading to parser bugs.

### 2b. Performance & Scalability
* **UUID Definition:** The spec describes the 8-hex-char SHA-256 digest as a "deterministic UUID." An 8-character hex string is a short 32-bit hash, which carries a non-trivial risk of collision across large projects. A proper deterministic UUID (e.g., UUIDv5) should be used, or the terminology should be corrected to "short hash."

---

## Cross-Lens Insights
* **Scope vs. Reliability:** The requirement of global uniqueness validation should only apply to *user-provided (explicit)* IDs. Since auto-generated IDs are not meant for stable cross-references, we should not enforce global uniqueness on them. This reduces the risk of builds failing due to duplicate placeholder text while keeping the technical implementation simpler and safer.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| E1 | Engineering | 🎯 | Failure Modes | Regex only matches valid IDs, ignoring invalid ones rather than reporting them | Regex should capture any text in the ID slot, and Python code should validate the format |
| E2 | Engineering | 🎯 | Failure Modes | Lookahead pattern in `_split_unclosed_paired` not updated | Update the lookahead regex inside `_split_unclosed_paired` to support alphanumeric IDs |
| E3 | Engineering | 💡 | Architecture Soundness | 8-hex-char hash incorrectly called "deterministic UUID" | Use standard UUIDv5 or correct terminology to "short hash" |
| E4 | Engineering | 🎯 | Edge Cases | Identical unmarked blocks crash build due to duplicate auto-generated IDs | Only enforce uniqueness check on explicit (user-specified) IDs; ignore auto-generated ones |

---

## Specific Suggested Edits for Spec Remediation

### Edit 1: Update requirements to prevent identical unmarked block crash & clarify downstream rendering
Replace Section "Requirements" (lines 7-16) with:
```markdown
## Requirements

1. Fragment markers can carry an optional ID: `[COM com-1]text` or `[COM]text` (no ID)
2. IDs contain only `[a-zA-Z0-9_-.]` characters; invalid IDs produce extraction errors
3. If absent, the tool generates a deterministic short hash (first 8 hex chars of SHA-256 of marker + content + file path) for internal tracking.
4. User-provided (explicit) IDs must be unique within a given marker type across the entire project; duplicates are extraction errors. Auto-generated IDs are not validated for uniqueness.
5. The existing `(?:\s+\d+)?` numeric-only pattern is replaced with the new alphanumeric ID format
6. Uniqueness validation of explicit IDs happens in `build_block_tree()`
7. Explicit block IDs are not surfaced in published output for now (downstream usage is deferred).
```

### Edit 2: Update global uniqueness validation to only check explicit IDs
Replace "Task 8: Add global uniqueness validation in `build_block_tree()`" (lines 92-96) with:
```markdown
### Task 8: Add global uniqueness validation in `build_block_tree()`

- **Objective:** After all blocks are collected, check that no two TextBlocks with user-provided (explicit) IDs share the same ID for a given marker type.
- **Implementation:** Modify `build_block_tree()` to return `(BlockTree, list[str])` (tree + errors). Iterate all TextBlocks, group by `(marker, id)` where the ID was explicitly specified by the user, report duplicates. Update callers in `cli.py`.
- **Test:** Two files with user-specified `[COM com-1]` produce a duplicate ID error; two files with `[COM]` (no ID, auto-generated hash) do NOT conflict even if their contents are identical.
```

### Edit 3: Fix lookahead and invalid ID detection in regexes
Replace Tasks 2, 3, and 5 (lines 56-79) with:
```markdown
### Task 2: Update closed paired marker splitting to capture and validate IDs

- **Objective:** Modify `_split_closed_paired()` to parse and validate the optional ID.
- **Implementation:** Change the regex to match any text within the opening tag: `rf'\[({escaped})(?:\s+([^\]]+))?\](.*?)\[/\1\]'`. In Python code, if the ID is present, validate that it matches `^[a-zA-Z0-9_.\-]+$`. If invalid, return an `ErrorBlock` with the message. Otherwise, pass the validated ID to the `TextBlock`.
- **Test:** `[COM com-1]text[/COM]` → `TextBlock(id='com-1')`; `[COM invalid!id]text[/COM]` → `ErrorBlock`.

### Task 4: Update unclosed paired marker splitting to capture and validate IDs

- **Objective:** Modify `_split_unclosed_paired()` to parse and validate the optional ID, and update lookahead logic.
- **Implementation:** Change the regex to match any text in the ID portion, e.g. `rf'\[({escaped})(?:\s+([^\]]+))?\]'`. Update the termination lookahead regex to match `\n\s*\[(?:{escaped})(?:\s+[^\]]+)?\]` so alphanumeric IDs also terminate preceding unclosed blocks. Validate the captured ID in Python; if invalid, return `ErrorBlock`.
- **Test:** `[COM my-id]content\n\n` → `TextBlock(id='my-id')`; lookahead terminates correctly when followed by `[COM next-id]`.

### Task 5: Update fallback terminator regex in `_extract_blocks_from_markdown()`

- **Objective:** The fallback terminator regex for fragment markers at BOL uses `(?:\s+\d+)?` — update to match alphanumeric IDs.
- **Implementation:** Replace `(?:\s+\d+)?` with `(?:\s+[^\]]+)?` in the fallback pattern construction to ensure it terminates on any alphanumeric or invalid ID.
- **Test:** An artifact block terminated by `[COM some-id]` or `[COM invalid!id]` at BOL correctly terminates.
```
