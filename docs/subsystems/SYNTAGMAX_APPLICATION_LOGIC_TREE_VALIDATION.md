# Syntagmax Application Logic — Tree and Validation Subsystem

> Covers artifact identity/state, parent-link resolution, hierarchy construction, metamodel-driven artifact validation, and trace validation. Source: `artifact.py`, `tree.py`, `analyse.py`.

## 1. Artifact model

An `Artifact` contains:

- `driver`, `record`, `atype`, `aid`;
- `location` (`FileLocation`, `LineLocation`, or `NotebookLocation`);
- `fields` with scalar/list values;
- `pids` (raw parent IDs);
- `parent_links` (`pid`, nominal revision, suspicious flag);
- `children` and `ancestors` sets;
- Git `revisions`.

`latest_revision` selects the newest revision timestamp. `contents()` returns the body field or `<empty>`.

Location forms:

- `FileLocation(file, sidecar?)` for file/sidecar artifacts;
- `LineLocation(file, start/end)` for text/Markdown sections;
- `NotebookLocation(file, start/end, cell)` for notebook cells.

`ArtifactBuilder` enforces location, atype, and AID presence. It uses the metamodel to detect multiple/reference/enum fields:

- multiple fields are stored as lists;
- comma-separated multiple references are split;
- comma-separated multiple enum values are split;
- duplicate scalar fields raise `ValidationError`;
- missing configured multiple fields are initialized to empty lists at build time.

## 2. Parent-link population

`populate_pids(config, artifacts, errors)` is skipped when no metamodel exists.

For every metamodel reference marked `to parent`:

1. Read the field value.
2. Normalize scalar/list/comma-separated references.
3. Split `AID@REVISION` into ID and nominal revision.
4. Resolve the parent from the artifact map when present.
5. For timestamp trace mode without an explicit revision, use nominal revision `older`.
6. Add one `ParentLink` and raw ID to `pids`.
7. Repeated parent IDs with conflicting nominal revisions produce a reference error.

Missing parent IDs are retained as links/IDs so validation and suppressed-tracing behavior can report them later.

## 3. Tree construction

`build_tree()`:

- creates parent→child edges only for IDs present in the artifact map;
- treats artifacts with no `pids` as top-level;
- with `suppress_tracing`, also treats artifacts whose pids are all unresolved as top-level;
- inserts synthetic artifact `ROOT` with `ROOT` type/ID and `<ROOT>` location;
- attaches top-level IDs to `ROOT`;
- recursively populates descendant ancestor sets.

Cycle/depth behavior:

- a reference already present in an ancestor set is a circular-reference error;
- recursion deeper than `MAX_TREE_DEPTH = 20` is also reported as circular/deep structure;
- traversal stops after the first returned structure error.

## 4. Artifact validator

`ArtifactValidator` indexes metamodel artifact definitions and trace rules. It validates each non-ROOT artifact.

### 4.1 Artifact type

- Unknown `atype` produces an attribute-category error and stops validation for that artifact.
- With no metamodel, no schema/attribute/trace rules are applied.

### 4.2 Active rules

- Conditional rules are evaluated against artifact fields.
- A rule is active when it has no condition or its condition evaluates true.
- Inactive conditional attributes are not required and are not treated as allowed fields.
- Any artifact field not present in active rules is an extra-attribute error.

### 4.3 Presence and multiplicity

- Any active mandatory rule requires the field to exist.
- `multiple=true` requires a list and validates every item.
- `multiple=false` rejects lists and validates the scalar.
- Missing optional fields are accepted.

### 4.4 Value types

- `integer`: Python `int` is accepted; other values must convert with `int()`.
- `boolean`: Python bool is accepted; otherwise default strings are `true/false`, `yes/no`, `1/0`, or metamodel custom values.
- `enum`: value must equal one allowed value.
- `reference`: value must be a string; ID before `@` must exist and have a known artifact type.
- `string`: builder stores normalized textual values; detailed string checks are delegated to extraction/metamodel semantics.

Reference errors become warnings instead of report errors when `suppress_tracing` is enabled.

### 4.5 ID schemas

- An active ID rule with a schema is compiled and cached per `(schema, atype)`.
- The artifact ID must match the compiled pattern.
- Mismatch is a schema-category error.

## 5. Trace validation

For each active trace rule on the source artifact:

1. Collect actual parents other than `ROOT`.
2. Build allowed target-type set from rule targets.
3. Report every parent whose type is not declared by an active trace rule.
4. For matching parents, validate trace mode:
   - `timestamp`: link must be implicit/`older`; explicit revision is invalid;
   - `commit`: link must contain an explicit revision, not `None`/`older`.
5. Mandatory rules require at least one matching parent type.
6. Conditions are evaluated on the source artifact.

With tracing suppressed, `_validate_traces()` is skipped; malformed/unknown references may instead be logged as warnings during type checking.

## 6. Root invariant

After validation, analysis checks that exactly one artifact has type `ROOT`. Failure is a structure error. The synthetic root normally guarantees one unless tree construction is bypassed or altered.

## 7. Error location contract

`ReportError` receives input record, artifact ID/type, file path, and line range from the artifact location. This metadata drives grouped report output and optional path links.

## 8. Status

- **Confirmed:** artifact fields/links, synthetic root, parent revision parsing, cycle limit, active-rule logic, extra/missing/multiplicity/type checks, ID schema checks, trace mode checks.
- **`UNVERIFIED`:** exact behavior for malformed non-string reference values under every extractor and whether all intentional backward-compatible no-metamodel paths are covered by tests.
