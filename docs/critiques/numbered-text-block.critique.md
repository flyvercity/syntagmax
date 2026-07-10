# Spec Critique: Non-Artifact Block Identification

## Executive Summary
This document presents a critique of the `docs/specs/numbered-text-block.spec.md` specification based on the dual Product and Engineering lenses framework.

Overall, the proposal is highly valuable and solves a real gap in requirement and comment referencing. However, the specification contains several critical gaps in parsing logic, architecture compatibility, and edge-case handling that must be resolved before proceeding to implementation. 

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Product Lens Findings

### 1a. User Value Assessment
* **Anchor Generation in Output:** The specification mentions "IDs are not surfaced in published output for now." If these IDs are not included in the published markdown (e.g., as HTML anchor attributes or Markdown labels), users cannot actually use them for cross-referencing in output documents. The implementation should surface these IDs as HTML anchors (`<a id="...">` or `{#id}`) in the published output.

### 1b. Edge Cases & User Experience
* **Auto-generated ID Instability:** Because auto-generated IDs are derived from a hash of the content (`marker + content + filepath`), any minor edit to the text (like correcting a typo) will silently change the ID. Any external links pointing to the old ID will break. The documentation must clearly warn users that auto-generated IDs are unstable and that stable anchors require explicit IDs.
* **Identical Unmarked Blocks Conflict:** If a user includes two identical unmarked blocks (e.g., `[COM]Check this` twice in the same file), they will generate the exact same hash/ID. If global uniqueness is checked across all blocks, this will crash the build with a duplicate ID validation error, which is a poor user experience for a standard document.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
* **Breaking API Signature change:** The spec proposes modifying `build_block_tree()` to return `(BlockTree, list[str])`. This breaks backward compatibility with other callers (such as `tests/test_publish.py` and `tests/test_obsidian_attachment_path.py`). A better design is to keep the return type as `BlockTree` and store validation errors as a list on the `BlockTree` object itself (`tree.errors`).

### 2b. Failure Mode Analysis
* **Regex Filtering of Invalid IDs:** The proposed regex patterns `[a-zA-Z0-9_.\-]+` only match valid ID characters. If a user enters an invalid ID (e.g. `[COM invalid!id]`), the pattern will fail to match entirely, meaning the block will be treated as unmarked text rather than triggering an extraction error as required. The regex must capture any text up to the closing bracket/terminator and validate it programmatically in Python.
* **Lookahead Termination in Unclosed Blocks:** In `_split_unclosed_paired()`, the lookahead regex terminates on the next block matching `\n\s*\[(?:{escaped})(?:\s+\d+)?\]`. If this lookahead pattern is not updated to match the new ID format, an unclosed block followed by a block with a new alphanumeric ID will fail to terminate correctly, leading to parser bugs.

### 2c. Performance & Scalability
* **UUID Definition:** The spec describes the 8-hex-char SHA-256 digest as a "deterministic UUID." An 8-character hex string is a short 32-bit hash, which carries a non-trivial risk of collision across large projects. A proper deterministic UUID (e.g., UUIDv5) should be used, or the terminology should be corrected to "short hash."

---

## Cross-Lens Insights
* **Scope vs. Reliability:** The requirement of global uniqueness validation should only apply to *user-provided (explicit)* IDs. Since auto-generated IDs are not meant for stable cross-references, we should not enforce global uniqueness on them. This reduces the risk of builds failing due to duplicate placeholder text while keeping the technical implementation simpler and safer.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 | User Value Assessment | IDs not surfaced in published output, preventing cross-referencing | Render IDs as HTML/Markdown anchors in `publish.py` when publishing |
| P2 | Product | 🎯 | Edge Cases & UX | Auto-generated ID changes on content edits, breaking references | Document that auto-generated IDs are unstable; reference anchors should use explicit IDs |
| E1 | Engineering | 🎯 | Architecture Soundness | Breaking signature change on `build_block_tree` | Store validation errors inside `BlockTree.errors` instead of changing the function signature |
| E2 | Engineering | 🎯 | Failure Modes | Regex only matches valid IDs, ignoring invalid ones rather than reporting them | Regex should capture any text in the ID slot, and Python code should validate the format |
| E3 | Engineering | 🎯 | Failure Modes | Lookahead pattern in `_split_unclosed_paired` not updated | Update the lookahead regex inside `_split_unclosed_paired` to support alphanumeric IDs |
| E4 | Engineering | 💡 | Architecture Soundness | 8-hex-char hash incorrectly called "deterministic UUID" | Use standard UUIDv5 or correct terminology to "short hash" |
| E5 | Engineering | 🎯 | Edge Cases | Identical unmarked blocks crash build due to duplicate auto-generated IDs | Only enforce uniqueness check on explicit (user-specified) IDs; ignore auto-generated ones |
| E6 | Engineering | 💡 | Testing Strategy | Existing test files calling `build_block_tree` not listed in affected tests | Add `tests/test_publish.py` and `tests/test_obsidian_attachment_path.py` to the impact list |

