# Specification

## Module for Generating Change Reports Between Revisions

# 1. Purpose

The module is intended for generating a human-readable report of changes in Syntagmax artifact between two Git revisions.

The report must analyze changes not only at the line level but also at the level of artifact and non-artiface blocks (requirements, sections, and other objects supported by the existing extraction mechanism).

The result is a Markdown document suitable for:

* human review;
* storage in Git;
* publication as Markdown.

---

# 2. Goals

The functionality must provide:

* comparison of two Git revisions;
* identification of changed files;
* analysis of artifact changes;
* analysis of block changes not belonging to artifacts;
* generation of a unified Markdown report.

---

# 3. Scope

The module is intended for Doc-as-Code documents stored in a Git repository.

The primary document type is Markdown.

---

# 4. Input Data

The user specifies two Git revisions: `base` and `target`

The following are accepted as revisions:

* commit hash;
* tag;
* branch;
* HEAD;
* HEAD~N.

Examples:

```
HEAD~1 HEAD
```

```
v1.2.0 v1.3.0
```

```
release develop
```

---

# 5. Components Used

The module must use the existing artiface extraction mechanism.

The following workflow is assumed.

```
Git

↓

obtain changed files

↓

extract file contents
for two revisions

↓

artifact analysis
(existing utility)

↓

artifact comparison

↓

plain text (non-artiface) change analysis

↓

Markdown generation
```

The new functionality must not re-implement the document parsers and drivers.

---

# 6. Command

```bash
syntagmax change report <base> <target>
```

Required parameters:

```
--base <git revision>

--target <git revision>
```

Optional parameters:

```
--output <report.md>
```

If the `--output` parameter is absent, the report is printed to default base path (`.syntagmax/reports/change/`). To print to stdout, use `--output console`.

```
--include-non-artifact
```

If `--include-non-artifact` is specified, the non-artifact blocks (text fragments) are also analyzed.

---

# 7. General Report Structure

The report consists of the following sections.

```
# Change Report

Repository information

Summary

Changed files

Detailed changes

Appendix
```

---

# 8. Repository Information Section

Must contain information about the comparison.

Example:

```text
Repository

Base revision:
v1.2.0

Target revision:
v1.3.0

Generated:
2026-07-15 12:35 UTC
```

---

# 9. Summary Section

Must contain aggregated statistics.

The following are mandatory (N is a number):

| Parameter               | Value |
| ----------------------- | ----- |
| Files changed           | N     |
| Files added             | N     |
| Files removed           | N     |
| Input records affected  | N     |
| Artifacts added         | N     |
| Artifacts modified      | N     |
| Artifacts removed       | N     |
| Text fragments modified | N     |

---

# 10. Changed Files Section

For each changed file, brief information is displayed.

Example

```text
docs/system.md

Status: Modified
Objects changed:
5

Text fragments:
2
```

Statuses:

* Added
* Removed
* Modified
* Renamed

---

# 11. File Change Details

Each file is presented as a separate section.

```
## docs/system.md
```

Subsections follow below.

---

# 12. Document Structure Changes

If document sections were changed, a list is displayed.

Example

```text
Modified sections

2 Initialization

3 Diagnostics

Appendix A
```

---

# 13. Object Changes

For each object, a separate block is displayed.

Required fields:

```
Object identifier

Object type

Status
```

Example

```text
Requirement REQ-105

Status: Modified
```

---

# 14. Object Text Changes

If the object text has changed, both versions are displayed.

````markdown
### Text

#### Previous

```text
The controller stores data.
```

#### Current

```text
The controller shall store encrypted data.
```
````

Where possible, Markdown diff blocks may be used.

---

# 15. Object Attribute Changes

Changed attributes are displayed as a table.

| Attribute | Previous | Current  |
| --------- | -------- | -------- |
| Priority  | Low      | High     |
| Status    | Draft    | Approved |

Unchanged attributes are not displayed.

---

# 16. Link Changes

Link changes are displayed as object attribute changes (see previous section).

---

# 17. Changes Outside Objects

This section is mandatory.

Its purpose is to display changes in plain document text that does not belong to logical objects.

Examples:

* introductory text;
* explanations;
* comments;
* descriptions;
* lists;
* tables;
* arbitrary paragraphs.

---

# 18. Plain Text Change Representation

Each changed fragment is displayed separately.

Required fields:

* line range in the original version;
* line range in the new version;
* change type.

Example

````markdown
### Text fragment

Status:
Modified

Old lines:
45-52

New lines:
45-56

#### Previous

```text
System overview.
```

#### Current

```text
System overview and operating modes.
```
````

---

# 19. Added Text

Example

````markdown
### Text fragment

Status:
Added

New lines:
132-145

```text
...
```
````

---

# 20. Removed Text

Example

````markdown
### Text fragment

Status:
Removed

Old lines:
87-94

```text
...
```
````

---

# 21. File Changes

If the file is entirely new:

```
Status: Added
```

The entire document is displayed.

If removed:

```
Status: Removed
```

The content of the previous version is displayed.

---

# 22. Rename Handling

When a Git Rename is detected, the following is displayed:

```
Old name

docs/old.md

New name

docs/new.md
```

---

# 23. Markdown Format

The following must be used:

* headings;
* tables;
* bulleted lists;
* fenced code blocks;
* horizontal rules.

HTML must not be used.

---

# 24. Performance

The system must:

* analyze only changed files;
* extract content switching the main worktree.
* use the existing extraction mechanisms.

---

# 25. Error Handling

The following situations must be handled:

* the specified revision does not exist;
* the file is absent in one of the revisions;
* object analysis cannot be performed;
* corrupted input;

If object analysis is not possible, the file is not excluded from the report. A section must be generated for it containing:

* information about the analysis error;
* changes at the plain text diff level with line ranges indicated.

---

# 26. Implementation Requirements

The module must be implemented as a separate command of the existing CLI utility.

The use of external diff utilities is permitted only for identifying changed files. Content analysis must be performed by the application itself.

---

# 27. Acceptance Criteria

The functionality is considered implemented if the following conditions are met:

1. Comparison of any two Git revisions is supported (commits, tags, branches, relative references).
2. A unified Markdown report is generated.
3. The report contains summary statistics.
4. For each changed file, its status is displayed.
5. For each changed object, the following are displayed:
   * identifier;
   * type;
   * status;
   * text changes;
   * attribute changes;
   * link changes (if any).
6. Changes outside objects are displayed as separate blocks with line ranges indicated for both source and target versions.
7. If object analysis is not possible, plain text change analysis remains available.
8. The report is correctly generated for added, removed, modified, and renamed files.
9. The generated Markdown renders correctly with standard Markdown viewers without using HTML.


# 28. Report File Naming

## 28.1 General Requirements

A report must be generated separately for each analyzed input record (project division).

For each input record, an independent Markdown file is created containing a report only for documents belonging to that record.

A combined report merging multiple sections into a single file is not generated.

## 28.2 File Name Format

The report file name must follow this template:

```text
<section>-<date>.md
```

where:

* `<section>` — the name of the project input record;
* `<date>` — the date the report was generated.

Date format:

```text
YYYYMMDD
```

## 28.3 Section Name Rules

When forming the file name, the `<section>` value must satisfy the following requirements:

* correspond to the project section name;
* contain only characters allowed in file names;
* space characters must be replaced with the "`-`" character;
* characters not allowed in file names must be replaced with "`_`" or removed;
* it is recommended to use a single case (lowercase or original), determined by project conventions.

### Examples

```text
system-20260715.md

software-requirements-20260715.md

flight_control-20260715.md
```

## 28.6 Regeneration

When regenerating a report for the same date, a file with a matching name must be overwritten.

## 28.7 Uniqueness Requirements

Within a single utility run, generated file names must be unique.

Uniqueness is ensured by using different `<section>` values corresponding to project sections.