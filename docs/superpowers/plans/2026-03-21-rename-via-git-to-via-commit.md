# Rename "via git" to "via commit" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the `via git` trace modifier to `via commit` in the metamodel DSL grammar, code, and documentation.

**Architecture:** Update the Lark grammar for the metamodel, adjust the transformer logic, and update all tests and documentation that refer to the `via git` syntax.

**Tech Stack:** Python, Lark, Pytest.

---

### Task 1: Update Metamodel Grammar

**Files:**
- Modify: `src/syntagmax/metamodel.lark:21`

- [ ] **Step 1: Update TRACE_MODE in metamodel.lark**

```lark
TRACE_MODE: "commit" | "timestamp"
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/metamodel.lark
git commit -m "dsl: rename 'via git' to 'via commit' in grammar"
```

### Task 2: Update Tests

**Files:**
- Modify: `tests/test_traces.py:50`

- [ ] **Step 1: Update test_trace_parsing in tests/test_traces.py**

```python
<<<<
trace from TEST to REQ is mandatory via git
====
trace from TEST to REQ is mandatory via commit
>>>>
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_traces.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_traces.py
git commit -m "test: update trace tests to use 'via commit'"
```

### Task 3: Update Metamodel Transformation (Optional/Verification)

**Files:**
- Modify: `src/syntagmax/metamodel.py:31` (comment only)

- [ ] **Step 1: Update comment in DSLTransformer.trace**

```python
<<<<
    def trace(self, children):
        # trace: "trace" "from" name "to" target_list "is" PRESENCE ["via" TRACE_MODE] _NL
        mode = str(children[3]) if len(children) > 3 and children[3] is not None else 'timestamp'
====
    def trace(self, children):
        # trace: "trace" "from" name "to" target_list "is" PRESENCE ["via" TRACE_MODE] _NL
        # TRACE_MODE is "commit" or "timestamp"
        mode = str(children[3]) if len(children) > 3 and children[3] is not None else 'timestamp'
>>>>
```

- [ ] **Step 2: Commit**

```bash
git add src/syntagmax/metamodel.py
git commit -m "refactor: update comment in metamodel transformer"
```

### Task 4: Search and Replace any remaining occurrences

**Files:**
- Search: Entire project for `via git`

- [ ] **Step 1: Search for 'via git'**

Run: `grep -r "via git" .`

- [ ] **Step 2: Replace any occurrences found**

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: rename remaining 'via git' occurrences to 'via commit'"
```
