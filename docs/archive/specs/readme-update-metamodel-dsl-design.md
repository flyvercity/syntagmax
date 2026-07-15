# Design: README.md Update - Metamodel DSL and VS Code Extension

**Date:** 2026-03-18
**Status:** Draft

## 1. Overview
Update the main `README.md` to reflect recent architectural changes, specifically the introduction of the Metamodel DSL (powered by Lark) and the availability of the companion VS Code extension.

## 2. Proposed Changes

### 2.1. Header and VS Code Extension
- Add a prominent mention and link to the [Syntagmax VS Code Extension](https://github.com/flyvercity/syntagmax-vscode).
- Clarify that the project is in active development.

### 2.2. Configuration Updates
- Add `metamodel` to the "Top-level options" table.
- Add a new "Metamodel (`[metamodel]`)" subsection detailing the `filename` option.
- Update the "Example" configuration to include a `metamodel` entry.

### 2.3. Metamodel DSL Section
Create a new section "Metamodel DSL" that explains:
- Purpose: Defining artifact types and validation rules.
- Syntax:
    - `artifact <NAME>:` block.
    - `attribute <ATTR> is <presence> <type>` rules.
- Supported Types: `string`, `integer`, `boolean`, `enum [value1, value2, ...]`.
- Supported Presence: `mandatory`, `optional`.

### 2.4. Extraction and Parsing
- Update mentions of drivers (drivers now use Lark for unified parsing).
- Ensure "Required Improvements" reflects current priorities.

## 3. Implementation Details
- Use the existing `README.md` structure.
- Ensure all TOML examples are valid and consistent with `src/syntagmax/config.py`.
- Document the DSL based on `src/syntagmax/metamodel.lark`.

## 4. Verification Plan
- Manual review of the rendered Markdown.
- Ensure all links (especially the VS Code extension) are correct.
- Verify that the documented DSL syntax matches the implementation in `metamodel.lark`.
