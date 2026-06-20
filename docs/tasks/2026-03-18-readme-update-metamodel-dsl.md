# README.md Update - Metamodel DSL and VS Code Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `README.md` to document the Metamodel DSL and the companion VS Code Extension.

**Architecture:** Documentation update (Markdown).

**Tech Stack:** Markdown.

---

### Task 1: Update Header and Link VS Code Extension

**Files:**
- Modify: `README.md:1-10`

- [ ] **Step 1: Update the title and add the VS Code Extension link**

Replace:
```markdown
# Syntagmax - Git-Based Requirements Management System

Fully git-friendly lightweight requirements management system with tracing model verification, change detection, and propagation.
```

With:
```markdown
# Syntagmax - Git-Based Requirements Management System

Fully git-friendly lightweight requirements management system with tracing model verification, change detection, and propagation.

**Companion VS Code Extension:** [syntagmax-vscode](https://github.com/flyvercity/syntagmax-vscode)
```

- [ ] **Step 2: Commit changes**

```bash
git add README.md
git commit -m "docs: add VS Code extension link to README"
```

### Task 2: Add Metamodel Configuration Documentation

**Files:**
- Modify: `README.md` (Configuration sections)

- [ ] **Step 1: Add `metamodel` to Top-level options table**

Insert into the table after `metrics`:
`| `metamodel` | No | Metamodel configuration |`

- [ ] **Step 2: Add `[metamodel]` subsection**

Insert after the `Metrics ([metrics])` section:
```markdown
### Metamodel (`[metamodel]`)

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `filename` | No | — | Path to the `.model` file defining the project's metamodel. |
```

- [ ] **Step 3: Update the Example configuration**

Update the `rms.toml` example to include:
```toml
[metamodel]
filename = "project.model"
```

- [ ] **Step 4: Commit changes**

```bash
git add README.md
git commit -m "docs: add metamodel configuration to README"
```

### Task 3: Document Metamodel DSL

**Files:**
- Modify: `README.md` (Add new section)

- [ ] **Step 1: Create "Metamodel DSL" section**

Insert after the configuration section:
```markdown
## Metamodel DSL

Syntagmax allows defining a custom metamodel for artifacts and their attributes using a simple DSL. This metamodel is used for static validation of requirements and other artifacts.

### Example

```model
artifact REQ:
    attribute status is mandatory enum [draft, active, retired]
    attribute verify is optional string
    attribute priority is mandatory integer
```

### Syntax Reference

| Rule | Description |
|------|-------------|
| `artifact <NAME>:` | Defines a new artifact type. Rules must be indented. |
| `attribute <ATTR> is <presence> <type>` | Defines an attribute rule. |

**Presence:** `mandatory` or `optional`.

**Types:**
- `string`: Any text.
- `integer`: A whole number.
- `boolean`: `true` or `false`.
- `enum [<values>]`: A fixed set of allowed values (comma-separated).
```

- [ ] **Step 2: Commit changes**

```bash
git add README.md
git commit -m "docs: document Metamodel DSL in README"
```

### Task 4: Final Cleanup and Improvements Update

**Files:**
- Modify: `README.md` (Required Improvements)

- [ ] **Step 1: Update "Required Improvements" section**

```markdown
## Required Improvements

- Implement automatic change propagation
- Enhance AI-based analysis and tracing
- Expand VS Code extension features (LSP support)
```

- [ ] **Step 2: Commit changes**

```bash
git add README.md
git commit -m "docs: update required improvements in README"
```
